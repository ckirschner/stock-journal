"""Profile version history.

What would corrupt the record here: an edit that goes unrecorded, a version
that can be rewritten after the fact, a reason that can be replaced, or a
deleted profile vanishing without a trace.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from engine import profile_history, profiles


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ledger-history-")
        os.environ["LEDGER_DATA"] = self.tmp
        self.addCleanup(os.environ.pop, "LEDGER_DATA", None)
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        profiles.ensure_profiles()              # seed from the template

    def _graham(self) -> Path:
        return profiles.profiles_dir() / "graham.yaml"

    def test_first_sighting_records_v1_without_nagging(self):
        doc = profile_history.sync()
        self.assertEqual(profile_history.current_version(doc, "graham.yaml"), 1)
        self.assertEqual(profile_history.pending(doc), [])

    def test_a_hand_edit_is_recorded_with_its_diff_and_needs_a_reason(self):
        profile_history.sync()
        p = self._graham()
        p.write_text(p.read_text(encoding="utf-8")
                     .replace("value: 15\n", "value: 14\n", 1),
                     encoding="utf-8")
        doc = profile_history.sync()
        self.assertEqual(profile_history.current_version(doc, "graham.yaml"), 2)
        pend = profile_history.pending(doc)
        self.assertEqual([(c["file"], c["version"]) for c in pend],
                         [("graham.yaml", 2)])
        self.assertIn("pe_3y_avg_eps.buy.value: 15 → 14", pend[0]["changes"])

    def test_reasons_are_write_once(self):
        profile_history.sync()
        p = self._graham()
        p.write_text(p.read_text(encoding="utf-8")
                     .replace("value: 15\n", "value: 14\n", 1),
                     encoding="utf-8")
        profile_history.sync()
        profile_history.explain("graham.yaml", 2, "Tightened after review.")
        with self.assertRaises(ValueError):
            profile_history.explain("graham.yaml", 2, "Changed my mind.")
        doc = profile_history.sync()
        self.assertEqual(profile_history.pending(doc), [])

    def test_a_reason_cannot_be_empty(self):
        profile_history.sync()
        with self.assertRaises(ValueError):
            profile_history.explain("graham.yaml", 1, "   ")

    def test_versions_only_append(self):
        doc1 = profile_history.sync()
        v1 = doc1["profiles"]["graham.yaml"]["versions"][0]
        p = self._graham()
        p.write_text(p.read_text(encoding="utf-8")
                     .replace("value: 15\n", "value: 14\n", 1),
                     encoding="utf-8")
        doc2 = profile_history.sync()
        self.assertEqual(doc2["profiles"]["graham.yaml"]["versions"][0], v1)

    def test_deletion_and_restoration_are_recorded(self):
        profile_history.sync()
        content = self._graham().read_text(encoding="utf-8")
        self._graham().unlink()
        doc = profile_history.sync()
        vs = doc["profiles"]["graham.yaml"]["versions"]
        self.assertIsNone(vs[-1]["content"])
        self.assertIn("Profile removed from disk.", vs[-1]["changes"])
        self._graham().write_text(content, encoding="utf-8")
        doc = profile_history.sync()
        vs = doc["profiles"]["graham.yaml"]["versions"]
        self.assertIsNotNone(vs[-1]["content"])
        self.assertIn("Profile restored to disk.", vs[-1]["changes"])

    def test_an_unparseable_file_is_not_recorded_as_removed(self):
        profile_history.sync()
        p = self._graham()
        good = p.read_text(encoding="utf-8")
        p.write_text("entries:\n  - metric: [broken\n", encoding="utf-8")
        doc = profile_history.sync()
        vs = doc["profiles"]["graham.yaml"]["versions"]
        self.assertEqual(len(vs), 1, "a parse failure is not a deletion")
        p.write_text(good, encoding="utf-8")
        doc = profile_history.sync()
        self.assertEqual(len(doc["profiles"]["graham.yaml"]["versions"]), 1)

    def test_a_non_dict_yaml_file_is_skipped_and_never_crashes_the_diff(self):
        profile_history.sync()
        p = self._graham()
        good = p.read_text(encoding="utf-8")
        p.write_text('"just a string"\n', encoding="utf-8")
        doc = profile_history.sync()          # must not record the scalar
        self.assertEqual(len(doc["profiles"]["graham.yaml"]["versions"]), 1)
        p.write_text(good, encoding="utf-8")
        profile_history.sync()                # and must not crash afterwards

    def test_sync_is_stable_when_nothing_changed(self):
        doc1 = profile_history.sync()
        doc2 = profile_history.sync()
        self.assertEqual(doc1, doc2)


if __name__ == "__main__":
    unittest.main()
