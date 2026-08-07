"""The concurrent-fetch failure class: the library's shared HTTP state dies
when reconfigured under in-flight requests, so configuration is idempotent
and fetches are serialized. Both properties are pinned here — this shipped as
three of four first fetches failing with a NoneType unpack out of the
library's transport."""

import threading
import time

from engine import fetch, gateway


class TestConfigureIdempotence:
    def test_unchanged_configure_never_touches_the_library(self, tmp_path,
                                                           monkeypatch):
        calls = []

        class FakeEdgar:
            @staticmethod
            def set_identity(identity):
                calls.append(identity)

        import sys
        monkeypatch.setitem(sys.modules, "edgar", FakeEdgar())
        monkeypatch.setattr(gateway, "_configured", False)
        monkeypatch.setattr(gateway, "_configured_with", None)
        monkeypatch.setattr(gateway, "_configure_lock", None)

        ident = "Jane Doe jane@example.com"
        gateway.configure(str(tmp_path / "cache"), ident)
        gateway.configure(str(tmp_path / "cache"), ident)
        gateway.configure(str(tmp_path / "cache"), ident)
        # set_identity closes the library's shared HTTP clients; repeating it
        # under a running fetch kills that fetch's requests mid-air.
        assert calls == [ident]

        gateway.configure(str(tmp_path / "cache"), "New Name new@example.com")
        assert len(calls) == 2


class TestFetchGate:
    def test_fetches_run_one_at_a_time(self, monkeypatch):
        running = []
        overlap = []

        def fake_fetch_ticker(ticker, settings, known_cik=None,
                              progress=None, on_resolved=None):
            running.append(ticker)
            if len(running) > 1:
                overlap.append(tuple(running))
            time.sleep(0.05)
            running.remove(ticker)
            return {"ticker": ticker, "errors": []}

        monkeypatch.setattr(fetch, "fetch_ticker", fake_fetch_ticker)
        settings = {"sec_identity": "Jane Doe jane@example.com"}
        for t in ("AAA", "BBB", "CCC"):
            r = fetch.start_fetch(t, settings)
            assert r.get("started")
        deadline = time.time() + 5
        while time.time() < deadline:
            done = [fetch.status_of(t) for t in ("AAA", "BBB", "CCC")]
            if all(s and not s.get("running") for s in done):
                break
            time.sleep(0.02)
        assert overlap == []          # never two fetches inside at once
        for t in ("AAA", "BBB", "CCC"):
            assert fetch.status_of(t).get("stage") == "done"
