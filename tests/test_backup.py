"""Export and import.

Two guarantees, both of which fail quietly. A bundle that imports halfway
leaves a machine holding a mixture of two backups and says it succeeded. And
a bundle that could carry a credential out — or a hostile folder name in —
does its damage without any visible symptom at all.

The credential half is guarded by construction rather than by care: the
exportable set is the journals directory, and secrets live under local/. The
test here is that the arrangement still holds, because the value of "by
construction" is entirely in nobody having to remember.
"""

import json

import pytest
from conftest import entered, journal_for

from engine import backup, hand_entered, journals, secrets, store


def _bundle(tmp_path, name="b.json"):
    return backup.export_bundle(tmp_path / name)


class TestExport:
    def test_a_bundle_carries_every_journal_whole(self, strategies, tmp_path):
        strategies("verdicts")
        a, record = journal_for("verdicts", "First")
        acme = {"ticker": "ACME", "lots": [],
                "notes": [{"date": "x", "text": "hello"}]}
        # Two readings of the same measure, a year apart, because a figure
        # the user revised is the case that would go unnoticed: a bundle
        # carrying only the value in force still looks whole from the
        # outside, and the entry it dropped is the one saying they changed
        # their mind.
        entered(acme, "2024-03-01", fcf_ttm=4.0)
        entered(acme, "2025-03-01", fcf_ttm=5.0)
        a["securities"].append(acme)
        journals.observe_rule_change(a, record, {"cash-floor": 250000})
        journals.explain(a, 1, "Widened on purpose.")
        journals.save(a)
        journals.create("Second", record)

        doc = json.loads(_bundle(tmp_path).read_text(encoding="utf-8"))
        assert doc["bundle_version"] == backup.BUNDLE_VERSION
        by_id = {j["id"]: j for j in doc["journals"]}
        assert len(by_id) == 2
        kept = by_id[a["id"]]
        assert kept["strategy"]["values"] == {"cash-floor": 1000000}
        assert kept["rule_changes"][0]["reason"] == "Widened on purpose."
        assert kept["securities"][0]["notes"][0]["text"] == "hello"
        # Read straight out of the file, so this says what the bundle holds
        # rather than what the engine can make of it: every entry, in order,
        # each still carrying the day it was written. A backup is the copy
        # nobody checks until the original is gone, and a dated record that
        # came back as a single current figure would be indistinguishable
        # from one the user only ever wrote once.
        assert [(e["id"], e["value"], e["recorded"][:10])
                for e in kept["securities"][0]["hand_entered"]] == \
            [("fcf_ttm", 4.0, "2024-03-01"), ("fcf_ttm", 5.0, "2025-03-01")]

    def test_no_credential_can_reach_a_bundle(self, strategies, tmp_path):
        """By construction: the exportable set is the journals directory and
        a secret is not in it. The test is that the arrangement still holds,
        because that is the whole value of by-construction."""
        strategies("verdicts")
        journal_for("verdicts")
        secrets.set_secret("tiingo_api_token", "SECRET-KEY-VALUE")
        secrets.local_set("sec_identity", "Jane Doe jane@example.com")
        text = _bundle(tmp_path).read_text(encoding="utf-8")
        assert "SECRET-KEY-VALUE" not in text
        assert "jane@example.com" not in text

    def test_an_unreadable_journal_is_skipped_not_guessed_at(self,
                                                             strategies,
                                                             tmp_path):
        strategies("verdicts")
        good, record = journal_for("verdicts", "Good")
        bad = journals.create("Bad", record)
        journals.path_for(bad["id"]).write_text("{ truncated",
                                                encoding="utf-8")
        doc = json.loads(_bundle(tmp_path).read_text(encoding="utf-8"))
        assert [j["id"] for j in doc["journals"]] == [good["id"]]


class TestImport:
    def test_a_round_trip_restores_everything(self, strategies, tmp_path):
        strategies("verdicts")
        a, record = journal_for("verdicts", "First")
        acme = {"ticker": "ACME", "lots": []}
        entered(acme, "2024-03-01", fcf_ttm=4.0)
        entered(acme, "2025-03-01", fcf_ttm=5.0)
        a["securities"].append(acme)
        journals.save(a)
        out = _bundle(tmp_path)

        import shutil
        shutil.rmtree(journals.journals_dir())
        assert journals.list_journals() == []

        summary = backup.import_bundle(out, keep_backup=False)
        assert summary["journals"] == 1
        back = journals.load(a["id"])
        assert back["securities"][0]["ticker"] == "ACME"
        assert back["strategy"]["id"] == "verdicts"
        # Restored, the record answers as-of questions again — which is only
        # true if the whole history came home. What a purchase backdated into
        # 2024 is entitled to see is the figure that was on record in 2024,
        # and a restore that kept just the newest entry would answer that
        # question with a number written a year after the fact.
        restored = back["securities"][0]
        early = hand_entered.reading(restored, "fcf_ttm", "2024-06-01")
        assert (early["status"], early.get("value")) == ("known", 4.0), early
        assert hand_entered.reading(restored, "fcf_ttm")["value"] == 5.0

    def test_an_older_bundle_is_refused_rather_than_converted(self, tmp_path):
        """Bundles from before a journal was stamped with one strategy
        describe a program that scored a security under several profiles at
        once. There is no honest answer to which of those a restored journal
        would be stamped with, so there is no conversion."""
        old = tmp_path / "old.json"
        old.write_text(json.dumps({
            "bundle_version": 2, "exported": "2026-01-01",
            "files": {"securities.json": {"securities": []}},
            "profiles": {"graham.yaml": "id: graham"}}), encoding="utf-8")
        with pytest.raises(ValueError, match="version 2"):
            backup.import_bundle(old, keep_backup=False)

    @pytest.mark.parametrize("hostile", ["../escape", "a/b", "", ".hidden"])
    def test_a_hostile_journal_name_writes_nothing_at_all(self, strategies,
                                                          tmp_path, hostile):
        strategies("verdicts")
        kept, _ = journal_for("verdicts", "Kept")
        payload = tmp_path / "hostile.json"
        payload.write_text(json.dumps({
            "bundle_version": backup.BUNDLE_VERSION,
            "exported": "2026-01-01",
            "journals": [{"schema": journals.SCHEMA, "id": hostile,
                          "name": "Bad", "securities": []}]}),
            encoding="utf-8")
        with pytest.raises(ValueError):
            backup.import_bundle(payload, keep_backup=False)
        # all-or-nothing: the journal already here is untouched
        assert [j["id"] for j in journals.list_journals()] == [kept["id"]]

    def test_a_bundle_naming_one_journal_twice_writes_nothing(self,
                                                              strategies,
                                                              tmp_path):
        strategies("verdicts")
        kept, _ = journal_for("verdicts", "Kept")
        payload = tmp_path / "dupe.json"
        one = {"schema": journals.SCHEMA, "id": "twin", "name": "Twin",
               "securities": []}
        payload.write_text(json.dumps({
            "bundle_version": backup.BUNDLE_VERSION,
            "exported": "2026-01-01", "journals": [one, dict(one)]}),
            encoding="utf-8")
        with pytest.raises(ValueError):
            backup.import_bundle(payload, keep_backup=False)
        assert [j["id"] for j in journals.list_journals()] == [kept["id"]]

    def test_the_current_journals_are_backed_up_before_being_replaced(
            self, strategies, tmp_path):
        strategies("verdicts")
        doomed, record = journal_for("verdicts", "Doomed")
        incoming = tmp_path / "in.json"
        incoming.write_text(json.dumps({
            "bundle_version": backup.BUNDLE_VERSION,
            "exported": "2026-01-01",
            "journals": [{"schema": journals.SCHEMA, "id": "fresh",
                          "name": "Fresh", "securities": []}]}),
            encoding="utf-8")
        backup.import_bundle(incoming)
        assert [j["id"] for j in journals.list_journals()] == ["fresh"]
        rescue = list(store.data_dir().glob("pre-import-*.json"))
        assert len(rescue) == 1
        saved = json.loads(rescue[0].read_text(encoding="utf-8"))
        assert [j["id"] for j in saved["journals"]] == [doomed["id"]]


class TestUnreadableJournals:
    def test_an_import_never_deletes_a_journal_it_could_not_back_up(
            self, strategies, tmp_path):
        """The rescue copy skips a journal whose file will not parse, so
        removing it here would destroy the only copy there is — and
        read_json has already promised its owner the file is left exactly
        where it is so they can repair it."""
        strategies("verdicts")
        broken, record = journal_for("verdicts", "Broken")
        broken["securities"].append({"ticker": "ACME", "lots": [
                                         {"id": "l1", "kind": "buy", "seq": 1,
                                          "date": "2026-01-02", "shares": 1.0,
                                          "price": 5.0}]})
        journals.save(broken)
        path = journals.path_for(broken["id"])
        truncated = path.read_text(encoding="utf-8")[:-40]
        path.write_text(truncated, encoding="utf-8")

        incoming = tmp_path / "in.json"
        incoming.write_text(json.dumps({
            "bundle_version": backup.BUNDLE_VERSION,
            "exported": "2026-01-01",
            "journals": [{"schema": journals.SCHEMA, "id": "fresh",
                          "name": "Fresh", "securities": []}]}),
            encoding="utf-8")
        summary = backup.import_bundle(incoming, keep_backup=False)

        assert path.read_text(encoding="utf-8") == truncated
        assert summary["kept_unreadable"] == [broken["id"]]
        assert broken["id"] not in summary["removed"]

    def test_an_import_says_which_journals_it_removed(self, strategies,
                                                      tmp_path):
        """Replacing everything is what import does; saying nothing about it
        leaves the user to notice a journal is missing."""
        strategies("verdicts")
        doomed, record = journal_for("verdicts", "Doomed")
        incoming = tmp_path / "in.json"
        incoming.write_text(json.dumps({
            "bundle_version": backup.BUNDLE_VERSION,
            "exported": "2026-01-01",
            "journals": [{"schema": journals.SCHEMA, "id": "fresh",
                          "name": "Fresh", "securities": []}]}),
            encoding="utf-8")
        summary = backup.import_bundle(incoming)
        assert summary["removed"] == [doomed["id"]]
        assert summary["rescue"]
