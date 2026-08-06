"""The sample data must exercise the bank, not the retired set.

Every value resolves against a bank entry a shipped profile references,
every snapshot names the profile that produced it, and the stories the
sample exists to tell — an expired clock, an unconfirmed breach, an
override on red and one on grey, profiles disagreeing — are asserted, not
assumed.
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


class SampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="ledger-sample-test-")
        os.environ["LEDGER_DATA"] = cls.tmp
        from engine import profiles
        from engine.evaluate import evaluate_buy, evaluate_position
        cls.evaluate_buy = staticmethod(evaluate_buy)
        cls.evaluate_position = staticmethod(evaluate_position)
        cls.profiles = {p["id"]: profiles.resolve_profile(p["file"])
                        for p in profiles.list_profiles()[0]}
        cls.bank_ids = set(profiles.bank_index(
            profiles.load_bank("metric-bank")))
        cls.doc = json.loads(
            (APP_DIR / "data.template" / "sample.json").read_text("utf-8"))
        cls.by_ticker = {s["ticker"]: s for s in cls.doc["securities"]}

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("LEDGER_DATA", None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_speaks_the_bank_vocabulary(self):
        self.assertEqual(self.doc.get("metrics_vocabulary"), "metric-bank/1")
        for s in self.doc["securities"]:
            for mid in s["metrics"]:
                self.assertIn(mid, self.bank_ids, f'{s["ticker"]}: {mid}')
            self.assertNotIn("legacy_metrics", s)

    def test_every_snapshot_names_its_profile(self):
        snaps = 0
        for s in self.doc["securities"]:
            snap = s.get("entry_snapshot")
            if not snap:
                continue
            snaps += 1
            self.assertNotIn("ruleset_version", snap, s["ticker"])
            self.assertIn(snap["profile"]["id"], self.profiles, s["ticker"])
            for mid in snap["metrics"]:
                self.assertIn(mid, self.bank_ids, s["ticker"])
        self.assertGreaterEqual(snaps, 8)

    def test_snapshots_replay_to_their_frozen_verdict(self):
        # The evaluator is pure, so re-running it over the frozen inputs must
        # reproduce the frozen verdict — if not, either the sample is stale
        # or evaluation changed under existing snapshots.
        for s in self.doc["securities"]:
            snap = s.get("entry_snapshot")
            if not snap:
                continue
            prof = self.profiles[snap["profile"]["id"]]
            r = self.evaluate_buy(snap["metrics"], prof)
            self.assertEqual(r["verdict"], snap["result"]["verdict"],
                             s["ticker"])

    def test_the_stories_hold(self):
        today = date(2026, 8, 6)
        pos = lambda t, pid: self.evaluate_position(
            self.by_ticker[t], self.profiles[pid], today)

        self.assertEqual(pos("MERI", "discount_closure")["overall"], "fired")
        self.assertTrue(pos("MERI", "discount_closure")["clock"]["expired"])
        self.assertEqual(pos("CVSW", "lynch")["overall"], "breached")
        self.assertEqual(pos("HLDN", "buffett")["overall"], "clear")

        ktra = self.by_ticker["KTRA"]["override"]
        self.assertTrue(ktra["failed"] and not ktra["missing"])
        lnwd = self.by_ticker["LNWD"]["override"]
        self.assertTrue(lnwd["missing"] and not lnwd["failed"])

        ashw = self.by_ticker["ASHW"]["metrics"]
        verdicts = {pid: self.evaluate_buy(ashw, p)["verdict"]
                    for pid, p in self.profiles.items()}
        self.assertEqual(verdicts["lynch"], "buy")
        self.assertEqual(verdicts["graham"], "no_buy")

        brdg = self.by_ticker["BRDG"]["metrics"]
        for pid, p in self.profiles.items():
            self.assertEqual(self.evaluate_buy(brdg, p)["verdict"],
                             "cant_say", pid)

    def test_exits_cover_both_directions(self):
        orvl = self.by_ticker["ORVL"]["exit"]
        self.assertTrue(orvl["rule_triggered"])
        sbrk = self.by_ticker["SBRK"]["exit"]
        self.assertFalse(sbrk["rule_triggered"])
        self.assertEqual(sbrk["reason"], "Panic")


if __name__ == "__main__":
    unittest.main()
