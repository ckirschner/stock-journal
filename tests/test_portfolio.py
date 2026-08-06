"""Positions and snapshots under profiles.

What would corrupt the journal here: a snapshot that doesn't say which
profile produced it, an override that vanishes when the verdict was grey
rather than red, or an exit that doesn't record which rules judged it.
"""

import os
import shutil
import tempfile
import unittest
from datetime import date

from engine import portfolio, profiles


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ledger-portfolio-")
        os.environ["LEDGER_DATA"] = cls.tmp
        cls.graham = profiles.resolve_profile("graham.yaml")

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("LEDGER_DATA", None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _green_metrics(self):
        return {"pe_3y_avg_eps": 12.0, "price_to_book": 1.2,
                "graham_combined_multiple": 14.4, "current_ratio": 2.4,
                "ltd_to_working_capital": 0.5, "profitable_years_10y": 10,
                "consecutive_annual_loss_years": 0, "altman_z_score": 3.5,
                "eps_growth_10y": 50, "consecutive_dividend_years": 12,
                "debt_to_equity": 0.5, "price_to_net_tangible_assets": 1.5,
                "accruals_ratio": 0.04, "market_cap": 900_000_000,
                "ncav_to_market_cap": 0.3}

    def test_snapshot_freezes_profile_metrics_and_result(self):
        s = portfolio.new_security("grn", "Green Co")
        s["metrics"] = self._green_metrics()
        s["price"] = 20.0
        portfolio.open_position(s, self.graham, 3, 10, 20.0, "2026-01-05")
        snap = s["entry_snapshot"]
        self.assertEqual(snap["profile"]["id"], "graham")
        self.assertEqual(snap["profile"]["version"], 3)
        self.assertEqual(snap["metrics"], self._green_metrics())
        self.assertEqual(snap["result"]["verdict"], "buy")
        self.assertIsNone(s["override"])
        # The snapshot is a copy: later edits must not reach into it.
        s["metrics"]["pe_3y_avg_eps"] = 99.0
        self.assertEqual(snap["metrics"]["pe_3y_avg_eps"], 12.0)

    def test_buying_against_a_red_verdict_records_the_override(self):
        s = portfolio.new_security("red", "Red Co")
        s["metrics"] = dict(self._green_metrics(), price_to_book=4.0,
                            graham_combined_multiple=48.0)
        portfolio.open_position(s, self.graham, 1, 1, 1.0, "2026-01-05",
                                override_reason="I like the story.")
        ov = s["override"]
        self.assertEqual(ov["verdict"], "No buy")
        self.assertIn("price_to_book", ov["failed"])
        self.assertEqual(ov["missing"], [])
        self.assertIn("against signal", s["notes"][-1]["text"])

    def test_buying_on_grey_records_an_override_too(self):
        s = portfolio.new_security("gry", "Grey Co")
        m = self._green_metrics()
        for k in ("profitable_years_10y", "eps_growth_10y",
                  "consecutive_dividend_years"):
            m.pop(k)
        s["metrics"] = m
        portfolio.open_position(s, self.graham, 1, 1, 1.0, "2026-01-05",
                                override_reason="History is elsewhere.")
        ov = s["override"]
        self.assertEqual(ov["verdict"], "Can't say")
        self.assertEqual(ov["failed"], [])
        self.assertIn("profitable_years_10y", ov["missing"])
        self.assertIn("without a signal", s["notes"][-1]["text"])

    def test_close_records_the_governing_profile_and_the_signal(self):
        s = portfolio.new_security("cls", "Close Co")
        s["metrics"] = self._green_metrics()
        portfolio.open_position(s, self.graham, 1, 1, 10.0, "2024-01-05")
        portfolio.close_position(s, self.graham, 1, True, "Hit valuation",
                                 15.0, "2026-07-01", today=date(2026, 7, 1))
        ex = s["exit"]
        self.assertEqual(ex["profile"]["id"], "graham")
        self.assertTrue(ex["governing"])
        # Graham's 24-month clock expired: the rule genuinely triggered.
        self.assertTrue(ex["rule_triggered"])
        self.assertEqual(ex["signal_at_exit"], "Sell signal")
        self.assertEqual(ex["return_pct"], 50.0)

    def test_close_under_a_missing_governing_profile_names_it(self):
        s = portfolio.new_security("gone", "Gone Co")
        s["position"] = {"shares": 1, "cost_basis": 10.0, "opened": "2025-01-01"}
        ref = {"file": "buffett.yaml", "id": "buffett",
               "name": "Buffett", "version": 2}
        portfolio.close_position(s, None, None, False, "Panic", 8.0,
                                 "2026-07-01", missing_profile_ref=ref)
        ex = s["exit"]
        self.assertEqual(ex["profile"]["name"], "Buffett")
        self.assertTrue(ex["governing"])
        self.assertIsNone(ex["rule_triggered"])
        self.assertEqual(ex["signal_at_exit"], "Profile not on disk")
        self.assertIn("Buffett", s["notes"][-1]["text"])

    def test_close_without_a_governing_profile_records_the_absence(self):
        s = portfolio.new_security("leg", "Legacy Co")
        s["position"] = {"shares": 1, "cost_basis": 10.0, "opened": "2020-01-01"}
        portfolio.close_position(s, None, None, False, "Panic", 8.0,
                                 "2026-07-01")
        ex = s["exit"]
        self.assertIsNone(ex["profile"])
        self.assertIsNone(ex["rule_triggered"])
        self.assertIn("no governing profile", s["notes"][-1]["text"].lower())


if __name__ == "__main__":
    unittest.main()
