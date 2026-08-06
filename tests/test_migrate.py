"""Migration behaviour.

What would corrupt the journal here: a value silently dropped, a value
renamed to a measure it never was, a frozen snapshot rewritten, a migration
that cannot be undone, or the retired ruleset history being deleted instead
of archived.
"""

import json
import os
import shutil
import tempfile
import unittest

from engine import migrate, store
from engine.profiles import bank_index, load_bank

OLD_IDS = set(migrate.LEGACY_LABELS)


class MappingTests(unittest.TestCase):
    def test_every_retired_id_is_accounted_for_exactly_once(self):
        resolved, unresolved = set(migrate.RESOLVED), set(migrate.UNRESOLVED)
        self.assertEqual(resolved | unresolved, OLD_IDS)
        self.assertEqual(resolved & unresolved, set())

    def test_resolved_targets_exist_in_the_bank(self):
        bank = set(bank_index(load_bank("metric-bank")))
        for old, m in migrate.RESOLVED.items():
            self.assertIn(m["to"], bank, old)


def old_security():
    return {
        "ticker": "OLD", "name": "Old Co", "bucket": "holdings",
        "added": "2024-01-01", "price": 10.0,
        "metrics": {"pe": 12.0, "roic": 15.5, "net_debt_ebitda": 1.1,
                    "mystery_metric": 7.7},
        "history": {},
        "entry_snapshot": {
            "frozen": "2024-01-01T00:00:00+00:00", "ruleset_version": 3,
            "metrics": {"pe": 11.0, "roic": 14.0},
            "price": 9.0,
            "result": {"verdict": "Buy", "tone": "pass"},
        },
        "override": {"date": "2024-01-01", "verdict": "Avoid",
                     "failed": ["net_debt_ebitda"], "reason": "r"},
        "ev": None, "falsifier": "", "notes": [],
        "position": {"shares": 1, "cost_basis": 9.0, "opened": "2024-01-01"},
        "exit": None,
    }


class TransformTests(unittest.TestCase):
    def setUp(self):
        self.bank_ids = set(bank_index(load_bank("metric-bank")))

    def test_renames_preserves_and_reports(self):
        doc = {"securities": [old_security()]}
        out, report = migrate.migrate_document(doc, self.bank_ids)
        s = out["securities"][0]
        self.assertEqual(s["metrics"],
                         {"pe_ttm": 12.0, "net_debt_to_ebitda": 1.1})
        self.assertEqual(s["legacy_metrics"],
                         {"roic": 15.5, "mystery_metric": 7.7})
        renamed = {r["from"]: r["to"] for r in report["renamed"]}
        self.assertEqual(renamed, {"pe": "pe_ttm",
                                   "net_debt_ebitda": "net_debt_to_ebitda"})
        preserved = {p["id"] for p in report["preserved"]}
        self.assertEqual(preserved, {"roic", "mystery_metric"})

    def test_nothing_recorded_is_lost(self):
        doc = {"securities": [old_security()]}
        out, _ = migrate.migrate_document(doc, self.bank_ids)
        s = out["securities"][0]
        kept = set(s["metrics"]) | set(s["legacy_metrics"])
        self.assertEqual(len(kept), len(doc["securities"][0]["metrics"]))

    def test_snapshot_override_and_exit_are_untouched(self):
        original = old_security()
        doc = {"securities": [original]}
        out, _ = migrate.migrate_document(doc, self.bank_ids)
        s = out["securities"][0]
        self.assertEqual(s["entry_snapshot"], original["entry_snapshot"])
        self.assertEqual(s["override"], original["override"])

    def test_input_is_not_mutated(self):
        doc = {"securities": [old_security()]}
        before = json.loads(json.dumps(doc))
        migrate.migrate_document(doc, self.bank_ids)
        self.assertEqual(doc, before)

    def test_bank_ids_already_in_place_pass_through(self):
        doc = {"securities": [{"ticker": "N", "metrics": {"pe_ttm": 9.0}}]}
        out, report = migrate.migrate_document(doc, self.bank_ids)
        self.assertEqual(out["securities"][0]["metrics"], {"pe_ttm": 9.0})
        self.assertEqual(report["renamed"], [])


class OnDiskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ledger-migrate-")
        os.environ["LEDGER_DATA"] = self.tmp
        self.addCleanup(os.environ.pop, "LEDGER_DATA", None)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _write(self, name, payload):
        (store.data_dir() / name).write_text(json.dumps(payload),
                                             encoding="utf-8")

    def test_full_migration_is_backed_up_reported_and_idempotent(self):
        original = {"securities": [old_security()]}
        os.makedirs(self.tmp, exist_ok=True)
        self._write("securities.json", original)
        self._write("rules.json", {"versions": [{"version": 1}]})

        report = migrate.ensure_migrated()
        self.assertIsNotNone(report)
        self.assertEqual(report["rules_archived"], "rules.legacy.json")

        # Reversible: the backup is byte-for-byte the original document.
        backup = json.loads(
            (store.data_dir() / report["backup"]).read_text(encoding="utf-8"))
        self.assertEqual(backup, original)
        # The retired ruleset history is archived, not deleted.
        self.assertTrue((store.data_dir() / "rules.legacy.json").exists())
        self.assertFalse((store.data_dir() / "rules.json").exists())

        migrated = store.load("securities.json")
        self.assertEqual(migrated.get("metrics_vocabulary"), migrate.VOCABULARY)

        # Idempotent: a second call reads the persisted report and changes
        # nothing.
        again = migrate.ensure_migrated()
        self.assertEqual(again["migrated"], report["migrated"])
        self.assertEqual(store.load("securities.json"), migrated)

    def test_second_corruption_does_not_destroy_the_first_broken_file(self):
        self._write("securities.json", {"securities": []})
        (store.data_dir() / "securities.json").write_text("{corrupt",
                                                          encoding="utf-8")
        store.load("securities.json")
        first = (store.data_dir() / "securities.json.broken")
        self.assertTrue(first.exists())
        original = first.read_text(encoding="utf-8")
        (store.data_dir() / "securities.json").write_text("{worse",
                                                          encoding="utf-8")
        store.load("securities.json")
        self.assertEqual(first.read_text(encoding="utf-8"), original,
                         "the first preserved journal must survive")
        others = list(store.data_dir().glob("securities.json.broken-*"))
        self.assertEqual(len(others), 1)

    def test_hostile_bundle_profile_name_aborts_before_any_write(self):
        import json as _json
        from engine import backup
        self._write("securities.json",
                    {"securities": [], "metrics_vocabulary": migrate.VOCABULARY})
        before = (store.data_dir() / "securities.json").read_text("utf-8")
        bundle = {
            "bundle_version": 2, "exported": "x",
            "files": {"securities.json": {"securities": [{"ticker": "EVIL"}]},
                      "settings.json": {}, "profile_history.json": {}},
            "profiles": {"": "evil", "ok.yaml": "schema: ledger.profile/1\n"},
        }
        src = store.data_dir() / "bundle.json"
        src.write_text(_json.dumps(bundle), encoding="utf-8")
        with self.assertRaises(ValueError):
            backup.import_bundle(src, keep_backup=False)
        self.assertEqual(
            (store.data_dir() / "securities.json").read_text("utf-8"), before,
            "nothing may be written when the bundle is invalid")

    def test_fresh_install_just_stamps_the_vocabulary(self):
        report = migrate.ensure_migrated()      # template seeds an empty file
        self.assertIsNone(report)
        doc = store.load("securities.json")
        self.assertEqual(doc.get("metrics_vocabulary"), migrate.VOCABULARY)
        backups = list(store.data_dir().glob("securities.pre-migration-*"))
        self.assertEqual(backups, [])


if __name__ == "__main__":
    unittest.main()
