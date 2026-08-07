"""The guarantees that keep the API key from leaving by accident.

The tests that matter most here are the leak tests: a secret appearing in an
export bundle, in an error message, or in a request URL must FAIL a test —
inspection goes stale, a failing test does not. The conftest forces the file
fallback for every test, so the real OS keychain is never touched.
"""

import json
import urllib.error

import pytest

from engine import backup, secrets, store, tiingo

KEY = "sk-test-9f8e7d6c5b4a-SECRET"
EMAIL = "jane.doe@example.com"
IDENT = f"Jane Doe {EMAIL}"


class TestFileFallback:
    def test_round_trip_and_delete(self):
        assert secrets.get_secret("tiingo_api_token") is None
        secrets.set_secret("tiingo_api_token", KEY)
        assert secrets.get_secret("tiingo_api_token") == KEY
        assert secrets.delete_secret("tiingo_api_token") is True
        assert secrets.get_secret("tiingo_api_token") is None
        assert secrets.delete_secret("tiingo_api_token") is False

    def test_fallback_file_is_owner_only(self):
        secrets.set_secret("tiingo_api_token", KEY)
        mode = secrets._secrets_path().stat().st_mode & 0o777
        assert mode == 0o600

    def test_storage_admits_it_is_unencrypted(self):
        info = secrets.storage()
        assert info["kind"] == "file"
        assert info["unencrypted"] is True

    def test_empty_value_is_refused(self):
        with pytest.raises(secrets.SecretsError):
            secrets.set_secret("tiingo_api_token", "  ")


class TestMigration:
    def test_plaintext_key_and_identity_move_out_and_old_copies_go(self):
        settings = {"discount_rate": 9.0, "tiingo_api_token": KEY,
                    "sec_identity": IDENT}
        changed = secrets.migrate_from_settings(settings)
        assert changed
        assert "tiingo_api_token" not in settings
        assert "sec_identity" not in settings
        assert settings["discount_rate"] == 9.0          # prefs untouched
        assert secrets.get_secret("tiingo_api_token") == KEY
        assert secrets.local_get("sec_identity") == IDENT
        # a key that ever sat in plaintext carries a rotate notice…
        assert secrets.local_get(secrets.ROTATE_FLAG)

    def test_clean_settings_are_left_alone(self):
        settings = {"discount_rate": 9.0}
        assert secrets.migrate_from_settings(settings) is False


class TestExportNeverCarriesSecrets:
    def _configure_everything(self):
        secrets.set_secret("tiingo_api_token", KEY)
        secrets.local_set("sec_identity", IDENT)
        store.save("securities.json", {"securities": []})
        store.save("settings.json", {"discount_rate": 9.0})

    def test_bundle_contains_neither_key_nor_email(self, tmp_path):
        self._configure_everything()
        path = backup.export_bundle(tmp_path / "bundle.json")
        text = path.read_text(encoding="utf-8")
        assert KEY not in text
        assert EMAIL not in text

    def test_export_is_clean_even_from_unmigrated_settings_plus_import_cleans(
            self, tmp_path):
        """A bundle made BEFORE migration may carry the plaintext key; the
        import path must strip it on arrival rather than resurrect it."""
        store.save("securities.json", {"securities": []})
        store.save("settings.json", {"discount_rate": 9.0,
                                     "tiingo_api_token": KEY,
                                     "sec_identity": IDENT})
        old_bundle = backup.export_bundle(tmp_path / "old.json")
        assert KEY in old_bundle.read_text()             # the historic hazard
        backup.import_bundle(old_bundle, keep_backup=False)
        on_disk = store.load("settings.json")
        assert "tiingo_api_token" not in on_disk
        assert "sec_identity" not in on_disk
        assert secrets.get_secret("tiingo_api_token") == KEY
        # …and the NEXT export is clean
        fresh = backup.export_bundle(tmp_path / "fresh.json")
        text = fresh.read_text()
        assert KEY not in text
        assert EMAIL not in text


class TestKeyNeverInUrlOrErrors:
    def _capture_request(self, monkeypatch, exc=None, body=b"[]"):
        seen = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return body

        def fake_urlopen(req, timeout=0):
            seen["url"] = req.full_url
            seen["auth"] = req.get_header("Authorization")
            if exc is not None:
                raise exc
            return FakeResp()

        monkeypatch.setattr(tiingo.urllib.request, "urlopen", fake_urlopen)
        return seen

    def test_key_travels_in_the_header_never_the_url(self, monkeypatch):
        seen = self._capture_request(
            monkeypatch, body=b'[{"date":"2024-01-02","close":10,"volume":1}]')
        tiingo.fetch_daily("SYN", KEY)
        assert KEY not in seen["url"]
        assert seen["auth"] == f"Token {KEY}"

    def test_rejected_key_error_does_not_contain_the_key(self, monkeypatch):
        err = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
        self._capture_request(monkeypatch, exc=err)
        with pytest.raises(tiingo.PriceSourceError) as e:
            tiingo.fetch_daily("SYN", KEY)
        assert KEY not in str(e.value)

    def test_network_error_reason_is_scrubbed(self, monkeypatch):
        # a hostile/echoing failure path: the reason itself carries the key
        err = urllib.error.URLError(f"proxy rejected token {KEY}")
        self._capture_request(monkeypatch, exc=err)
        with pytest.raises(tiingo.PriceSourceError) as e:
            tiingo.fetch_daily("SYN", KEY)
        assert KEY not in str(e.value)

    def test_verify_key_messages_never_echo_the_key(self, monkeypatch):
        seen = self._capture_request(
            monkeypatch, body=json.dumps(
                {"message": f"you sent {KEY}"}).encode())
        out = tiingo.verify_key(KEY)
        assert out["ok"] is True
        assert KEY not in out["message"]
        assert KEY not in seen["url"]
