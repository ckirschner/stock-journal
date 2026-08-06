"""Loader and resolution behaviour for the metric bank and profiles.

The behaviours covered are the ones that would quietly corrupt the Config
pages rather than crash them: references resolving against the right bank,
missing parameters surfacing instead of vanishing, blank sells surviving as
deliberate blanks, and rows never being dropped.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


class ProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Point the data dir at a scratch copy so real user data is untouched.
        cls.tmp = tempfile.mkdtemp(prefix="ledger-test-")
        os.environ["LEDGER_DATA"] = cls.tmp
        from engine import profiles  # imported after the env var is set
        cls.profiles = profiles

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("LEDGER_DATA", None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_seeds_template_profiles_on_first_run(self):
        found, errors = self.profiles.list_profiles()
        self.assertEqual(errors, [])
        template = sorted(p.name for p in
                          (APP_DIR / "data.template" / "profiles").glob("*.yaml"))
        self.assertEqual(sorted(p["file"] for p in found), template)
        for p in found:
            self.assertTrue(p["id"] and p["name"])

    def test_bank_loads_all_entries(self):
        bank = self.profiles.bank_view()
        self.assertEqual(len(bank["entries"]), 61)
        ids = [e["id"] for e in bank["entries"]]
        self.assertEqual(len(ids), len(set(ids)), "bank ids must be unique")

    def test_every_template_profile_resolves_cleanly(self):
        found, _ = self.profiles.list_profiles()
        for p in found:
            resolved = self.profiles.resolve_profile(p["file"])
            self.assertEqual(resolved["errors"], [],
                             f'{p["file"]}: {resolved["errors"]}')
            for tier in resolved["tiers"]:
                for entry in tier["entries"]:
                    self.assertEqual(entry["errors"], [],
                                     f'{p["file"]}/{entry["metric"]}: {entry["errors"]}')
                    self.assertTrue(entry.get("label"))
                    self.assertTrue(entry.get("description"))

    def test_entry_count_matches_rollup_declarations(self):
        resolved = self.profiles.resolve_profile("graham.yaml")
        counts = {t["key"]: len(t["entries"]) for t in resolved["tiers"]}
        self.assertEqual(counts, {"required": 4, "core": 8, "bonus": 3})

    def test_supplied_null_parameter_is_supplied_not_missing(self):
        resolved = self.profiles.resolve_profile("graham.yaml")
        entry = next(e for t in resolved["tiers"] for e in t["entries"]
                     if e["metric"] == "earnings_yield_to_risk_free_multiple")
        self.assertEqual(entry["errors"], [])
        param = next(p for p in entry["parameters"] if p["id"] == "risk_free_rate")
        self.assertTrue(param["supplied"])
        self.assertIsNone(param["value"])

    def test_blank_sell_is_preserved_with_its_reason(self):
        resolved = self.profiles.resolve_profile("graham.yaml")
        entry = next(e for t in resolved["tiers"] for e in t["entries"]
                     if e["metric"] == "accruals_ratio")
        self.assertEqual(entry["sell"]["form"], "none")
        self.assertTrue(entry["sell"]["why"].strip())

    def test_measured_on_resolves_to_a_bank_label(self):
        resolved = self.profiles.resolve_profile("graham.yaml")
        entry = next(e for t in resolved["tiers"] for e in t["entries"]
                     if e["metric"] == "profitable_years_10y")
        self.assertEqual(entry["sell"]["measured_on"],
                         "consecutive_annual_loss_years")
        self.assertIn("Consecutive", entry["sell"]["measured_on_label"])

    def _write_profile(self, name, body):
        path = self.profiles.ensure_profiles() / name
        path.write_text(body, encoding="utf-8")
        self.addCleanup(path.unlink)
        return name

    def test_unresolved_bank_reference_surfaces_and_row_survives(self):
        f = self._write_profile("broken-ref.yaml", """\
schema: ledger.profile/1
id: broken
name: Broken
bank: metric-bank
settings:
  rollup:
    tiers:
      required: {count: 1, requires: all_green}
entries:
  - metric: not_a_real_metric
    tier: required
    buy: {form: abs, comparator: at_least, value: 1, unit: ratio}
""")
        resolved = self.profiles.resolve_profile(f)
        entries = resolved["tiers"][0]["entries"]
        self.assertEqual(len(entries), 1, "the row must never be skipped")
        self.assertIn("not_a_real_metric", entries[0]["errors"][0])

    def test_unsupplied_required_parameter_surfaces(self):
        f = self._write_profile("missing-param.yaml", """\
schema: ledger.profile/1
id: missing-param
name: Missing param
bank: metric-bank
settings:
  rollup:
    tiers:
      bonus: {count: 1, requires: none}
entries:
  - metric: earnings_yield_to_risk_free_multiple
    tier: bonus
    buy: {form: abs, comparator: at_least, value: 2, unit: times}
""")
        resolved = self.profiles.resolve_profile(f)
        entry = resolved["tiers"][0]["entries"][0]
        self.assertTrue(any("risk_free_rate" in e for e in entry["errors"]))
        param = next(p for p in entry["parameters"] if p["id"] == "risk_free_rate")
        self.assertFalse(param["supplied"])

    def test_missing_bank_surfaces_as_profile_error(self):
        f = self._write_profile("no-bank.yaml", """\
schema: ledger.profile/1
id: no-bank
name: No bank
bank: bank-that-does-not-exist
entries:
  - metric: pe_ttm
    tier: core
    buy: {form: abs, comparator: at_most, value: 15, unit: times}
""")
        resolved = self.profiles.resolve_profile(f)
        self.assertTrue(any("bank-that-does-not-exist" in e
                            for e in resolved["errors"]))

    def test_profile_name_cannot_escape_the_profiles_dir(self):
        with self.assertRaises(ValueError):
            self.profiles.resolve_profile("../rules.json")

    def test_round_trip_load_preserves_comments(self):
        # Editing lands next: the loader must already keep comments intact.
        import io
        path = APP_DIR / "data.template" / "profiles" / "graham.yaml"
        doc = self.profiles.load_yaml(path)
        buf = io.StringIO()
        self.profiles._yaml.dump(doc, buf)
        self.assertIn("# names the bank, not a path", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
