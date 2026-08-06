"""Evaluator behaviour.

The behaviours covered are the ones that would quietly corrupt a verdict
rather than crash: grey counting as a pass or a failure, a tier rollup
resolving when the greys could still change it, a sell firing without its
confirmation, and a delta-versus-entry test guessing when the snapshot
predates the profile system.
"""

import unittest
from datetime import date

from engine.evaluate import (condition_holds, evaluate_buy,
                             evaluate_position)


def entry(metric, buy=None, sell=None, flag=None, parameters=None, errors=None):
    return {"metric": metric, "tier": "", "buy": buy, "sell": sell,
            "flag": flag, "parameters": parameters or [], "errors": errors or []}


def tier(key, requires, entries, min_green=None):
    return {"key": key, "requires": requires, "min_green": min_green,
            "count": len(entries), "entries": entries}


def prof(tiers, sell_confirmation=None, holding_period_exit=None):
    return {"file": "t.yaml", "id": "t", "name": "T", "tiers": tiers,
            "sell_confirmation": sell_confirmation,
            "holding_period_exit": holding_period_exit}


AT_LEAST_5 = {"form": "abs", "comparator": "at_least", "value": 5, "unit": "x"}


class ConditionTests(unittest.TestCase):
    def test_comparators(self):
        c = lambda cmp, v, t=5: condition_holds(
            {"form": "abs", "comparator": cmp, "value": t}, v)
        self.assertTrue(c("at_most", 5))
        self.assertFalse(c("at_most", 5.01))
        self.assertTrue(c("at_least", 5))
        self.assertFalse(c("at_least", 4.99))
        self.assertFalse(c("less_than", 5))
        self.assertTrue(c("less_than", 4.99))
        self.assertFalse(c("greater_than", 5))
        self.assertTrue(c("greater_than", 5.01))

    def test_between_is_inclusive(self):
        b = {"form": "abs", "comparator": "between", "min": 15, "max": 35}
        self.assertTrue(condition_holds(b, 15))
        self.assertTrue(condition_holds(b, 35))
        self.assertFalse(condition_holds(b, 35.1))
        self.assertFalse(condition_holds(b, 14.9))

    def test_missing_value_is_unevaluable_not_false(self):
        self.assertIsNone(condition_holds(AT_LEAST_5, None))

    def test_delta_median_compares_the_stored_value_directly(self):
        # The bank entries these appear on are already median-relative.
        c = {"form": "delta_median", "comparator": "at_least", "value": 1.75}
        self.assertTrue(condition_holds(c, 1.8))
        self.assertFalse(condition_holds(c, 1.7))

    def test_delta_entry_relative_fall(self):
        c = {"form": "delta_entry", "comparator": "falls_by_at_least",
             "value": 33, "unit": "percent_of_entry_value"}
        self.assertTrue(condition_holds(c, 10.0, entry_value=15.0))   # −33.3%
        self.assertFalse(condition_holds(c, 10.1, entry_value=15.0))
        self.assertIsNone(condition_holds(c, 10.0, entry_value=None))

    def test_delta_entry_falls_below(self):
        c = {"form": "delta_entry", "comparator": "falls_below_entry_value"}
        self.assertTrue(condition_holds(c, 9, entry_value=10))
        self.assertFalse(condition_holds(c, 10, entry_value=10))

    def test_relative_fall_from_a_non_positive_base_is_unevaluable(self):
        # With a negative entry value the raw formula would call an
        # improvement a fall. That is not a judgement to make silently.
        c = {"form": "delta_entry", "comparator": "falls_by_at_least",
             "value": 33, "unit": "percent_of_entry_value"}
        self.assertIsNone(condition_holds(c, -7, entry_value=-10))
        self.assertIsNone(condition_holds(c, 0, entry_value=0))

    def test_compound_all_and_any(self):
        both = {"form": "compound", "require": "all", "conditions": [
            {"form": "abs", "comparator": "at_least", "value": 5},
            {"form": "abs", "comparator": "at_most", "value": 10}]}
        self.assertTrue(condition_holds(both, 7))
        self.assertFalse(condition_holds(both, 11))
        either = dict(both, require="any")
        self.assertTrue(condition_holds(either, 11))

    def test_compound_with_unevaluable_leg(self):
        # One leg needs the entry value; without it the compound must not
        # resolve to True or False.
        c = {"form": "compound", "require": "all", "conditions": [
            {"form": "delta_entry", "comparator": "falls_by_at_least",
             "value": 33},
            {"form": "abs", "comparator": "less_than", "value": 12}]}
        self.assertIsNone(condition_holds(c, 10, entry_value=None))
        # ...unless another leg already decides it.
        self.assertFalse(condition_holds(c, 13, entry_value=None))


class BuyRollupTests(unittest.TestCase):
    def test_all_green_pass_fail_indeterminate(self):
        p = prof([tier("required", "all_green",
                       [entry("a", AT_LEAST_5), entry("b", AT_LEAST_5)])])
        self.assertEqual(evaluate_buy({"a": 6, "b": 6}, p)["verdict"], "buy")
        self.assertEqual(evaluate_buy({"a": 6, "b": 4}, p)["verdict"], "no_buy")
        self.assertEqual(evaluate_buy({"a": 6}, p)["verdict"], "cant_say")

    def test_red_beats_grey_in_a_knockout_tier(self):
        # One red and one grey: the red decides; grey cannot soften it.
        p = prof([tier("required", "all_green",
                       [entry("a", AT_LEAST_5), entry("b", AT_LEAST_5)])])
        self.assertEqual(evaluate_buy({"a": 3}, p)["verdict"], "no_buy")

    def test_at_least_three_valued(self):
        p = prof([tier("core", "at_least",
                       [entry(m, AT_LEAST_5) for m in "abcd"], min_green=3)])
        # 3 green, 1 grey: greys can't change the outcome — pass.
        self.assertEqual(evaluate_buy({"a": 6, "b": 6, "c": 6}, p)["verdict"], "buy")
        # 1 green, 1 grey, 2 red: even a green grey couldn't reach 3 — fail.
        self.assertEqual(
            evaluate_buy({"a": 6, "b": 1, "c": 1}, p)["verdict"], "no_buy")
        # 2 green, 2 grey: the greys decide and they are unknown.
        self.assertEqual(evaluate_buy({"a": 6, "b": 6}, p)["verdict"], "cant_say")

    def test_bonus_never_blocks(self):
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5)]),
                  tier("bonus", "none", [entry("b", AT_LEAST_5)])])
        r = evaluate_buy({"a": 6, "b": 1}, p)
        self.assertEqual(r["verdict"], "buy")
        self.assertEqual(r["tiers"][1]["outcome"], "score")

    def test_unset_parameter_makes_the_entry_grey(self):
        e = entry("a", AT_LEAST_5, parameters=[
            {"id": "rate", "label": "Rate", "supplied": True, "value": None}])
        p = prof([tier("required", "all_green", [e])])
        r = evaluate_buy({"a": 99}, p)          # a value exists, but the
        self.assertEqual(r["verdict"], "cant_say")   # computation is unanchored
        self.assertIn("not set", r["tiers"][0]["entries"][0]["reason"])

    def test_config_error_makes_the_entry_grey_with_the_error(self):
        e = entry("a", AT_LEAST_5, errors=["broken reference"])
        p = prof([tier("required", "all_green", [e])])
        r = evaluate_buy({"a": 99}, p)
        self.assertEqual(r["verdict"], "cant_say")
        self.assertIn("broken reference", r["tiers"][0]["entries"][0]["reason"])

    def test_fail_outranks_indeterminate(self):
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5)]),
                  tier("core", "at_least", [entry("b", AT_LEAST_5)], min_green=1)])
        r = evaluate_buy({"a": 1}, p)           # a red, b grey
        self.assertEqual(r["verdict"], "no_buy")

    def test_missing_min_green_is_never_a_silent_pass(self):
        p = prof([tier("core", "at_least",
                       [entry("a", AT_LEAST_5), entry("b", AT_LEAST_5)])])
        r = evaluate_buy({"a": 1, "b": 1}, p)   # every entry red
        self.assertEqual(r["verdict"], "cant_say")
        self.assertIn("min_green", r["tiers"][0]["problem"])
        self.assertIn("min_green", r["causes"][0]["text"])

    def test_unknown_rollup_form_cannot_pass(self):
        p = prof([tier("gate", "atleast", [entry("a", AT_LEAST_5)], min_green=1)])
        r = evaluate_buy({"a": 9}, p)
        self.assertEqual(r["verdict"], "cant_say")
        self.assertIn("atleast", r["tiers"][0]["problem"])


DEFAULT_CONF = {"count": 2, "unit": "consecutive_filings"}


def holding(metrics, snap_metrics=None, legacy=False, opened="2026-01-10"):
    s = {"ticker": "T", "bucket": "holdings", "metrics": metrics,
         "position": {"shares": 1, "cost_basis": 1, "opened": opened}}
    if legacy:
        s["entry_snapshot"] = {"ruleset_version": 3, "metrics": {"old_id": 1}}
    elif snap_metrics is not None:
        s["entry_snapshot"] = {"profile": {"file": "t.yaml"},
                               "metrics": snap_metrics}
    return s


class SellTests(unittest.TestCase):
    def test_breach_needs_confirmation_it_cannot_get(self):
        sell = {"form": "abs", "comparator": "at_least", "value": 2.0}
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5, sell)])],
                 sell_confirmation=DEFAULT_CONF)
        r = evaluate_position(holding({"a": 2.3}), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "breached")
        self.assertIn("consecutive filings", r["signals"][0]["needs"])
        self.assertEqual(r["overall"], "breached")

    def test_inherent_confirmation_fires(self):
        sell = {"form": "abs", "comparator": "at_least", "value": 2,
                "sell_confirmation": {"form": "inherent"}}
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5, sell)])],
                 sell_confirmation=DEFAULT_CONF)
        r = evaluate_position(holding({"a": 2}), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "fired")
        self.assertEqual(r["overall"], "fired")

    def test_sustained_for_replaces_the_default_and_stays_unconfirmed(self):
        sell = {"form": "abs", "comparator": "less_than", "value": 0,
                "sustained_for": {"count": 4, "unit": "quarterly_filings"}}
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5, sell)])],
                 sell_confirmation=DEFAULT_CONF)
        r = evaluate_position(holding({"a": -1}), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "breached")
        self.assertIn("4 consecutive quarterly filings", r["signals"][0]["needs"])

    def test_measured_on_another_metric(self):
        sell = {"form": "abs", "comparator": "at_least", "value": 2,
                "measured_on": "streak",
                "sell_confirmation": {"form": "inherent"}}
        p = prof([tier("core", "at_least",
                       [entry("a", AT_LEAST_5, sell)], min_green=0)])
        r = evaluate_position(holding({"a": 9, "streak": 2}), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "fired")
        r = evaluate_position(holding({"a": 9}), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "unevaluable")

    def test_delta_entry_against_legacy_snapshot_reports_not_guesses(self):
        sell = {"form": "delta_entry", "comparator": "falls_by_at_least",
                "value": 33}
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5, sell)])])
        r = evaluate_position(holding({"a": 5}, legacy=True), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "unevaluable")
        self.assertIn("predates the profile system", r["signals"][0]["needs"])

    def test_delta_entry_with_a_bank_snapshot(self):
        sell = {"form": "delta_entry", "comparator": "falls_by_at_least",
                "value": 33, "sell_confirmation": {"form": "inherent"}}
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5, sell)])])
        r = evaluate_position(holding({"a": 10}, snap_metrics={"a": 20}), p,
                              date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "fired")

    def test_clock_expiry(self):
        hpe = {"form": "fixed_period", "value": 24, "unit": "months"}
        p = prof([tier("core", "none", [])], holding_period_exit=hpe)
        s = holding({}, opened="2024-04-15")
        r = evaluate_position(s, p, date(2026, 4, 15))
        self.assertTrue(r["clock"]["expired"])
        self.assertEqual(r["overall"], "fired")
        r = evaluate_position(s, p, date(2026, 4, 14))
        self.assertFalse(r["clock"]["expired"])
        self.assertEqual(r["overall"], "clear")

    def test_no_threshold_by_choice_is_not_unwatched(self):
        p = prof([tier("core", "at_least",
                       [entry("a", AT_LEAST_5, {"form": "none"})], min_green=0)])
        r = evaluate_position(holding({}), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "no_threshold")
        self.assertEqual(r["overall"], "clear")

    def test_unwatched_when_thresholds_exist_but_none_can_run(self):
        sell = {"form": "abs", "comparator": "at_least", "value": 2}
        p = prof([tier("core", "at_least",
                       [entry("a", AT_LEAST_5, sell)], min_green=0)])
        r = evaluate_position(holding({}), p, date(2026, 8, 6))
        self.assertEqual(r["overall"], "unwatched")

    def test_sell_breach_on_a_negative_entry_base_reports_unevaluable(self):
        sell = {"form": "compound", "require": "all", "conditions": [
            {"form": "delta_entry", "comparator": "falls_by_at_least",
             "value": 33, "unit": "percent_of_entry_value"},
            {"form": "abs", "comparator": "less_than", "value": 12}]}
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5, sell)])])
        # An improvement from -10 to -7 must not read as a breach.
        r = evaluate_position(holding({"a": -7}, snap_metrics={"a": -10}), p,
                              date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "unevaluable")
        self.assertIn("zero or negative", r["signals"][0]["needs"])

    def test_compound_any_resolves_despite_a_missing_entry_value(self):
        sell = {"form": "compound", "require": "any",
                "sell_confirmation": {"form": "inherent"}, "conditions": [
                    {"form": "delta_entry", "comparator": "falls_by_at_least",
                     "value": 33},
                    {"form": "abs", "comparator": "less_than", "value": 12}]}
        p = prof([tier("required", "all_green", [entry("a", AT_LEAST_5, sell)])])
        # No snapshot value, but the abs leg decides on its own.
        r = evaluate_position(holding({"a": 5}, legacy=True), p, date(2026, 8, 6))
        self.assertEqual(r["signals"][0]["status"], "fired")

    def test_flag_measured_on_another_metric(self):
        flag = {"form": "abs", "comparator": "at_least", "value": 2,
                "measured_on": "streak"}
        p = prof([tier("core", "at_least",
                       [entry("a", AT_LEAST_5, None, flag)], min_green=0)])
        r = evaluate_position(holding({"a": 12, "streak": 3}), p, date(2026, 8, 6))
        self.assertEqual(r["flags"][0]["status"], "flagged")
        self.assertEqual(r["flags"][0]["value"], 3)
        r = evaluate_position(holding({"a": 12}), p, date(2026, 8, 6))
        self.assertEqual(r["flags"][0]["status"], "unevaluable")
        self.assertIn("streak", r["flags"][0]["needs"])

    def test_clock_with_an_unsupported_unit_says_so(self):
        hpe = {"form": "fixed_period", "value": 2, "unit": "years"}
        p = prof([tier("core", "none", [])], holding_period_exit=hpe)
        r = evaluate_position(holding({}, opened="2024-01-01"), p,
                              date(2026, 8, 6))
        self.assertFalse(r["clock"]["expired"])
        self.assertIn("years", r["clock"]["problem"])
        self.assertNotIn("opened date", r["clock"]["problem"])

    def test_flag_surfaces_and_never_blocks(self):
        flag = {"form": "delta_entry", "comparator": "falls_below_entry_value",
                "severity": "flag", "never_blocks": True}
        p = prof([tier("core", "at_least",
                       [entry("a", AT_LEAST_5, None, flag)], min_green=0)])
        r = evaluate_position(holding({"a": 8}, snap_metrics={"a": 12}), p,
                              date(2026, 8, 6))
        self.assertEqual(r["flags"][0]["status"], "flagged")
        self.assertEqual(r["overall"], "clear")


if __name__ == "__main__":
    unittest.main()
