"""Sell-threshold confirmation: the behaviours that would fail silently.

A breach confirming a period early, a gap resetting (or advancing) the
count, an unevaluable reading counting as clear, a same-day catch-up batch
counting as several observations, a wrong cadence quietly reinstating
count-filings-as-they-arrive — none of these crash. They produce plausible
wrong signals, so each one is pinned here with deliberately awkward filing
sequences.
"""

from datetime import date

from conftest import balance_face, filing, inst

from engine import portfolio, price_store
from engine.compute import (CADENCE, REGISTRY, Ctx, confirmation_boundaries,
                            confirmation_history)
from engine.evaluate import evaluate_position
from engine.periods import is_absent

# -- builders ---------------------------------------------------------------

ABS2 = {"form": "abs", "comparator": "at_least", "value": 2.0}
DEFAULT_CONF = {"count": 2, "unit": "consecutive_filings"}


def entry(metric, sell=None, flag=None):
    return {"metric": metric, "buy": {"form": "none"}, "sell": sell,
            "flag": flag, "parameters": [], "errors": []}


def prof(entries, sell_confirmation=None):
    p = {"tiers": [{"key": "core", "requires": "none", "entries": entries}]}
    if sell_confirmation:
        p["sell_confirmation"] = sell_confirmation
    return p


def holding(metrics, snap_metrics=None, opened="2024-01-15"):
    return {"ticker": "SYN", "bucket": "holdings", "metrics": metrics,
            "entry_snapshot": {"profile": {"file": "t.yaml"},
                               "metrics": snap_metrics or {}},
            "position": {"shares": 10, "cost_basis": 100.0, "opened": opened}}


def rd(period_end, filed, value, reason=None, form="10-K", accession="A-1",
       priced=None):
    return {"period_end": period_end, "filed": filed, "accession": accession,
            "form": form, "value": value, "reason": reason, "priced": priced}


def hist(cadence, *rows, truncated=False, note=None):
    return {"entry": "a", "cadence": cadence, "readings": list(rows),
            "boundaries_held": len(rows), "truncated": truncated,
            "note": note}


def run(sec, p, histories):
    return evaluate_position(sec, p, date(2026, 8, 7), histories=histories)


# -- the walk ---------------------------------------------------------------

class TestConfirmationWalk:
    def test_breach_on_the_required_run_fires(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", 2.2),
                       rd("2023-12-31", "2024-02-22", 1.0))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "fired"
        assert r["overall"] == "fired"
        conf = sig["confirmation"]
        assert conf["confirmed"] and conf["observed"] == 2
        assert "in a row" in conf["note"]
        # traceable to the specific filings that produced it
        assert [x["period_end"] for x in conf["readings"]] == \
            ["2025-12-31", "2024-12-31"]

    def test_a_gap_neither_advances_nor_resets(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", None,
                          reason="the filing would not extract"),
                       rd("2023-12-31", "2024-02-22", 2.2))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "fired"          # pause is not a reset
        assert sig["confirmation"]["gaps"] == 1  # and not an observation
        states = [x["state"] for x in sig["confirmation"]["readings"]]
        assert states == ["breached", "unobserved", "breached"]

    def test_a_gap_alone_never_confirms(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", None,
                          reason="the filing would not extract"))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert sig["confirmation"]["observed"] == 1
        assert "could not be read" in sig["needs"]

    def test_a_clear_reading_bounds_the_run(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", 1.0),
                       rd("2023-12-31", "2024-02-22", 2.9))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert sig["confirmation"]["observed"] == 1
        assert "clear reading" in sig["needs"]
        # the walk stopped at the clear reading; the older breach is unreached
        states = [x["state"] for x in sig["confirmation"]["readings"]]
        assert states == ["breached", "clear"]

    def test_newest_reading_clear_means_no_run_despite_a_live_breach(self):
        """A price spike today cannot borrow persistence from old filings:
        the newest per-filing reading is clear, so the count is zero."""
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 1.0),
                       rd("2024-12-31", "2025-02-21", 2.2))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert sig["confirmation"]["observed"] == 0
        assert "no run has started" in sig["needs"]

    def test_live_reading_still_gates(self):
        """History full of breaches means nothing when today's reading is
        clear — the signal is clear, not breached, not fired."""
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", 2.2))}
        r = run(holding({"a": 1.5}), p, h)
        assert r["signals"][0]["status"] == "clear"

    def test_without_histories_the_breach_stays_unconfirmed(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        r = run(holding({"a": 2.5}), p, None)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert "consecutive filings" in sig["needs"]
        # the copy claims nothing about what is on disk
        assert "not consulted" in sig["needs"]
        assert sig["confirmation"]["observed"] == 0

    def test_an_empty_history_carries_the_providers_reason(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual", note="no filings are stored for this "
                                      "security — fetch data to begin "
                                      "building its filing history")}
        r = run(holding({"a": 2.5}), p, h)
        assert "no filings are stored" in r["signals"][0]["needs"]

    def test_pre_entry_readings_do_not_count_for_a_delta_entry_test(self):
        """'Fell versus the value at entry' had no truth value before the
        entry existed; filings from before the position opened are out of
        scope for it."""
        sell = {"form": "delta_entry", "comparator": "falls_below_entry_value"}
        p = prof([entry("a", sell=sell)], DEFAULT_CONF)
        sec = holding({"a": 8.0}, snap_metrics={"a": 10.0},
                      opened="2025-06-01")
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 8.0, form="10-Q"),
                       rd("2025-03-31", "2025-04-30", 8.0, form="10-Q"))}
        r = run(sec, p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert sig["confirmation"]["observed"] == 1
        assert sig["confirmation"]["readings"][1]["state"] == "out_of_scope"
        assert "before this position was opened" in sig["needs"]

    def test_an_absolute_threshold_counts_standing_pre_entry_breaches(self):
        """A condition that has already persisted across filings is a fact
        about the security, not noise; buying into one (an override the
        journal recorded) does not restart its clock."""
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        sec = holding({"a": 2.5}, opened="2025-06-01")
        h = {"a": hist("quarterly",
                       rd("2025-03-31", "2025-04-30", 2.4, form="10-Q"),
                       rd("2024-12-31", "2025-02-21", 2.2))}
        r = run(sec, p, h)
        assert r["signals"][0]["status"] == "fired"

    def test_delta_entry_without_an_opened_date_pauses(self):
        sell = {"form": "delta_entry", "comparator": "falls_below_entry_value"}
        p = prof([entry("a", sell=sell)], DEFAULT_CONF)
        sec = holding({"a": 8.0}, snap_metrics={"a": 10.0}, opened=None)
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 8.0, form="10-Q"),
                       rd("2025-03-31", "2025-04-30", 8.0, form="10-Q"))}
        r = run(sec, p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert "opened date" in sig["needs"]

    def test_quarterly_unit_on_an_annual_metric_is_reported_not_hidden(self):
        sell = {**ABS2, "sustained_for": {"count": 4,
                                          "unit": "quarterly_filings"}}
        p = prof([entry("a", sell=sell)])
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", 2.2))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"       # 2 of 4
        assert sig["confirmation"]["unit_mismatch"] is True
        assert "annual reports are what is counted" in sig["needs"]

    def test_next_confirmation_is_estimated_from_report_spacing(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-15", 2.4),
                       rd("2024-12-31", "2025-02-20", 1.0),
                       rd("2023-12-31", "2024-02-18", 1.0))}
        r = run(holding({"a": 2.5}), p, h)
        nxt = r["signals"][0]["confirmation"]["next"]
        # one more qualifying report needed, roughly a year of spacing
        assert nxt["date"].startswith("2027-02")
        assert "estimate" in nxt["basis"]
        assert nxt["date"] in r["signals"][0]["needs"]

    def test_a_single_report_cannot_estimate_and_says_so(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual", rd("2025-12-31", "2026-02-15", 2.4))}
        r = run(holding({"a": 2.5}), p, h)
        nxt = r["signals"][0]["confirmation"]["next"]
        assert "date" not in nxt or not nxt.get("date")
        assert "only one qualifying report" in nxt["unknown"]

    def test_a_malformed_confirmation_count_can_never_confirm(self):
        p = prof([entry("a", sell=ABS2)],
                 {"count": None, "unit": "consecutive_filings"})
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", 2.2))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert "cannot be counted" in sig["needs"]

    def test_inherent_confirmation_still_fires_without_history(self):
        sell = {**ABS2, "sell_confirmation": {"form": "inherent"}}
        p = prof([entry("a", sell=sell)], DEFAULT_CONF)
        r = run(holding({"a": 2.5}), p, None)
        sig = r["signals"][0]
        assert sig["status"] == "fired"
        assert "confirmation" not in sig

    def test_confirmed_across_a_gap_does_not_claim_a_row(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", None,
                          reason="the filing would not extract"),
                       rd("2023-12-31", "2024-02-22", 2.2))}
        r = run(holding({"a": 2.5}), p, h)
        note = r["signals"][0]["confirmation"]["note"]
        assert "in a row" not in note
        assert "no clear reading between them" in note
        assert "could not be read" in note

    def test_a_count_of_one_reads_grammatically(self):
        sell = {**ABS2, "sustained_for": {"count": 1,
                                          "unit": "quarterly_filings"}}
        p = prof([entry("a", sell=sell)])
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 2.4, form="10-Q"))}
        r = run(holding({"a": 2.5}), p, h)
        note = r["signals"][0]["confirmation"]["note"]
        assert "1 quarterly report (" in note
        assert "in a row" not in note

    def test_an_annual_unit_on_a_quarterly_metric_counts_annual_reports(self):
        """The reverse mismatch must not fire years early: only readings on
        annual reports advance the count, and the substitution is said."""
        sell = {**ABS2, "sustained_for": {"count": 2,
                                          "unit": "consecutive_annual_filings"}}
        p = prof([entry("a", sell=sell)])
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 2.4, form="10-Q"),
                       rd("2025-03-31", "2025-05-01", 2.3, form="10-Q"))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"          # two 10-Q breaches ≠ 2
        assert sig["confirmation"]["observed"] == 0
        assert sig["confirmation"]["unit_mismatch"] is True
        assert "annual reports advance the count" in sig["needs"]
        states = [x["state"] for x in sig["confirmation"]["readings"]]
        assert states == ["not_counted", "not_counted"]

    def test_an_annual_unit_confirms_on_the_annual_reports_in_the_history(self):
        sell = {**ABS2, "sustained_for": {"count": 2,
                                          "unit": "consecutive_annual_filings"}}
        p = prof([entry("a", sell=sell)])
        h = {"a": hist("quarterly",
                       rd("2025-03-31", "2025-05-01", 2.4, form="10-Q"),
                       rd("2024-12-31", "2025-02-20", 2.3),
                       rd("2024-09-30", "2024-11-01", 2.2, form="10-Q"),
                       rd("2023-12-31", "2024-02-21", 2.1))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "fired"
        assert sig["confirmation"]["observed"] == 2
        counted = [x["period_end"] for x in sig["confirmation"]["readings"]
                   if x["state"] == "breached"]
        assert counted == ["2024-12-31", "2023-12-31"]

    def test_a_clear_quarterly_reading_still_ends_an_annual_unit_run(self):
        """A mismatch may make confirming slower, never easier."""
        sell = {**ABS2, "sustained_for": {"count": 2,
                                          "unit": "consecutive_annual_filings"}}
        p = prof([entry("a", sell=sell)])
        h = {"a": hist("quarterly",
                       rd("2024-12-31", "2025-02-20", 2.3),
                       rd("2024-09-30", "2024-11-01", 1.0, form="10-Q"),
                       rd("2023-12-31", "2024-02-21", 2.1))}
        r = run(holding({"a": 2.5}), p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert sig["confirmation"]["observed"] == 1
        assert "bounded by a clear reading" in sig["needs"]

    def test_an_absolute_leg_settles_pre_entry_readings_in_a_compound(self):
        """require:any with an entry-dependent leg: a pre-entry reading the
        absolute leg settles still counts — the equivalent abs-only condition
        would, and the compound is not stricter than its strictest leg."""
        sell = {"form": "compound", "require": "any", "conditions": [
            dict(ABS2),
            {"form": "delta_entry", "comparator": "falls_below_entry_value"}]}
        p = prof([entry("a", sell=sell)], DEFAULT_CONF)
        sec = holding({"a": 2.5}, snap_metrics={"a": 3.0},
                      opened="2025-06-01")
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 2.4, form="10-Q"),
                       rd("2025-03-31", "2025-04-30", 2.2, form="10-Q"))}
        r = run(sec, p, h)
        assert r["signals"][0]["status"] == "fired"

    def test_a_pre_entry_reading_an_any_compound_cannot_settle_stops(self):
        """require:any with the abs leg false pre-entry: the compound as a
        whole had no truth value then (the delta leg did not exist), so the
        reading is out of scope — it stops the walk without counting."""
        sell = {"form": "compound", "require": "any", "conditions": [
            dict(ABS2),
            {"form": "delta_entry", "comparator": "falls_below_entry_value"}]}
        p = prof([entry("a", sell=sell)], DEFAULT_CONF)
        sec = holding({"a": 2.5}, snap_metrics={"a": 3.0},
                      opened="2025-06-01")
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 2.4, form="10-Q"),
                       rd("2025-03-31", "2025-04-30", 1.0, form="10-Q"))}
        r = run(sec, p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        assert sig["confirmation"]["readings"][1]["state"] == "out_of_scope"

    def test_a_pre_entry_reading_an_all_compound_settles_clear_bounds(self):
        """require:all with the abs leg false pre-entry IS settled — no
        assignment of the missing leg could make it hold — so the reading
        reads clear and bounds the run."""
        sell = {"form": "compound", "require": "all", "conditions": [
            dict(ABS2),
            {"form": "delta_entry", "comparator": "falls_below_entry_value"}]}
        p = prof([entry("a", sell=sell)], DEFAULT_CONF)
        sec = holding({"a": 2.5}, snap_metrics={"a": 3.0},
                      opened="2025-06-01")
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 2.4, form="10-Q"),
                       rd("2025-03-31", "2025-04-30", 1.0, form="10-Q"))}
        r = run(sec, p, h)
        assert r["signals"][0]["confirmation"]["readings"][1]["state"] == \
            "clear"

    def test_a_computed_but_unjudgeable_reading_is_not_called_unreadable(self):
        """A reading with a value that the condition cannot decide (an
        entry-dependent leg with no snapshot value) is 'undecided', never
        'could not be read' — the number exists and must not be hidden."""
        sell = {"form": "compound", "require": "any", "conditions": [
            {"form": "abs", "comparator": "at_least", "value": 6.0},
            {"form": "delta_entry", "comparator": "falls_by_at_least",
             "value": 20, "unit": "percent_of_entry_value"}]}
        p = prof([entry("a", sell=sell)], DEFAULT_CONF)
        sec = holding({"a": 6.5}, snap_metrics={}, opened="2024-01-15")
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 6.5, form="10-Q"),
                       rd("2025-03-31", "2025-05-01", 5.0, form="10-Q"),
                       rd("2024-12-31", "2025-02-20", 5.5))}
        r = run(sec, p, h)
        sig = r["signals"][0]
        assert sig["status"] == "breached"
        states = [x["state"] for x in sig["confirmation"]["readings"]]
        assert states == ["breached", "undecided", "undecided"]
        assert sig["confirmation"]["undecided"] == 2
        assert sig["confirmation"]["gaps"] == 0
        assert "could not be judged" in sig["needs"]

    def test_clear_stop_after_gaps_does_not_call_the_gap_the_newest(self):
        p = prof([entry("a", sell=ABS2)], DEFAULT_CONF)
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", None,
                          reason="the filing would not extract"),
                       rd("2024-12-31", "2025-02-21", 1.0))}
        r = run(holding({"a": 2.5}), p, h)
        assert "could settle the run" in r["signals"][0]["needs"]

    def test_an_absurd_count_projects_an_honest_unknown_not_a_crash(self):
        p = prof([entry("a", sell=ABS2)],
                 {"count": 100000, "unit": "consecutive_filings"})
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", 2.2))}
        r = run(holding({"a": 2.5}), p, h)
        nxt = r["signals"][0]["confirmation"]["next"]
        assert "beyond any projectable date" in nxt["unknown"]

    def test_annual_forms_stay_in_step_with_periods(self):
        from engine import evaluate, periods
        assert evaluate._ANNUAL_FORMS == periods.ANNUAL_FORMS

    def test_truncated_histories_are_admitted_in_the_note(self):
        p = prof([entry("a", sell=ABS2)],
                 {"count": 4, "unit": "consecutive_filings"})
        h = {"a": hist("quarterly",
                       rd("2025-06-30", "2025-08-01", 2.4, form="10-Q"),
                       rd("2025-03-31", "2025-05-01", 2.2, form="10-Q"),
                       truncated=True)}
        r = run(holding({"a": 2.5}), p, h)
        assert "were examined" in r["signals"][0]["needs"]


# -- boundaries -------------------------------------------------------------

def _f(accession, form, filed, period):
    return filing(accession, form, filed, period, [])


class TestBoundaries:
    def test_each_new_period_is_a_boundary_and_amendments_are_not(self):
        fs = [_f("K1", "10-K", "2025-02-20", "2024-12-31"),
              _f("Q1", "10-Q", "2025-05-10", "2025-03-31"),
              _f("K1A", "10-K/A", "2025-06-01", "2024-12-31"),
              _f("Q2", "10-Q", "2025-08-08", "2025-06-30")]
        got = confirmation_boundaries(fs, "quarterly")
        assert [b["accession"] for b in got] == ["K1", "Q1", "Q2"]

    def test_a_same_day_catch_up_batch_is_one_observation(self):
        """A delinquent filer posting three quarters at once produced one
        moment of new information, not three chances to confirm a breach."""
        fs = [_f("Q1", "10-Q", "2025-06-15", "2024-09-30"),
              _f("Q2", "10-Q", "2025-06-15", "2024-12-31"),
              _f("Q3", "10-Q", "2025-06-15", "2025-03-31")]
        got = confirmation_boundaries(fs, "quarterly")
        assert len(got) == 1
        assert got[0]["period_end"] == "2025-03-31"

    def test_a_late_filed_old_quarter_is_not_a_boundary(self):
        fs = [_f("K1", "10-K", "2025-03-01", "2024-12-31"),
              _f("Q2-OLD", "10-Q", "2025-05-01", "2024-06-30")]
        got = confirmation_boundaries(fs, "quarterly")
        assert [b["accession"] for b in got] == ["K1"]

    def test_annual_cadence_ignores_quarterly_reports(self):
        fs = [_f("K1", "10-K", "2025-02-20", "2024-12-31"),
              _f("Q1", "10-Q", "2025-05-10", "2025-03-31"),
              _f("Q2", "10-Q", "2025-08-08", "2025-06-30"),
              _f("K2", "10-K", "2026-02-19", "2025-12-31")]
        got = confirmation_boundaries(fs, "annual")
        assert [b["accession"] for b in got] == ["K1", "K2"]

    def test_an_amendment_only_annual_period_still_counts_once(self):
        """The original never extracted; the amendment is the first filing to
        deliver that fiscal year, so it is the observation for it — but a
        second amendment adds nothing."""
        fs = [_f("K1", "10-K", "2024-02-20", "2023-12-31"),
              _f("K2A", "10-K/A", "2025-06-01", "2024-12-31"),
              _f("K2AA", "10-K/A", "2025-07-01", "2024-12-31")]
        got = confirmation_boundaries(fs, "annual")
        assert [b["accession"] for b in got] == ["K1", "K2A"]

    def test_undated_filings_are_never_boundaries(self):
        fs = [_f("K1", "10-K", "2025-02-20", "2024-12-31"),
              filing("X", "10-K", None, "2025-12-31", [])]
        got = confirmation_boundaries(fs, "annual")
        assert [b["accession"] for b in got] == ["K1"]


# -- per-filing readings from real stores -----------------------------------

def _quarter(accession, filed, period, ca, cl=100.0):
    extra = [inst("us-gaap:AssetsCurrent", period, ca)]
    if cl is not None:
        extra.append(inst("us-gaap:LiabilitiesCurrent", period, cl))
    return filing(accession, "10-Q", filed, period,
                  balance_face(period, extra=extra))


class TestHistoryReadings:
    def test_readings_are_per_filing_and_newest_first(self):
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
              _quarter("Q2", "2025-08-09", "2025-06-30", 150.0),
              _quarter("Q3", "2025-11-08", "2025-09-30", 110.0)]
        h = confirmation_history(fs, None, ["SYN"], "current_ratio")
        assert h["cadence"] == "quarterly"
        vals = [(r["period_end"], r["value"]) for r in h["readings"]]
        assert vals == [("2025-09-30", 1.1), ("2025-06-30", 1.5),
                        ("2025-03-31", 2.0)]

    def test_a_later_amendment_cannot_rewrite_an_earlier_reading(self):
        """The reading at a boundary is what was observable when that filing
        arrived; a restating amendment filed later is invisible to it."""
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
              _quarter("Q2", "2025-08-09", "2025-06-30", 150.0),
              {**_quarter("Q1A", "2025-09-01", "2025-03-31", 50.0),
               "form": "10-Q/A"}]
        h = confirmation_history(fs, None, ["SYN"], "current_ratio")
        by_period = {r["period_end"]: r for r in h["readings"]}
        assert by_period["2025-03-31"]["value"] == 2.0
        assert by_period["2025-03-31"]["accession"] == "Q1"

    def test_an_uncomputable_boundary_is_an_honest_gap(self):
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
              _quarter("Q2", "2025-08-09", "2025-06-30", 150.0, cl=None),
              _quarter("Q3", "2025-11-08", "2025-09-30", 110.0)]
        h = confirmation_history(fs, None, ["SYN"], "current_ratio")
        bad = [r for r in h["readings"] if r["period_end"] == "2025-06-30"][0]
        assert bad["value"] is None
        assert bad["reason"]

    def test_no_filings_says_so(self):
        h = confirmation_history([], None, ["SYN"], "current_ratio")
        assert h["readings"] == []
        assert "no filings are stored" in h["note"]

    def test_an_undated_filing_enters_no_as_of_prefix(self):
        """A filing that cannot be placed in time is no boundary (tested
        above) and must not leak into other boundaries' readings either —
        every prefix reading would silently reflect it."""
        undated = _quarter("X", None, "2025-06-30", 50.0)
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0), undated]
        h = confirmation_history(fs, None, ["SYN"], "current_ratio")
        assert len(h["readings"]) == 1
        assert h["readings"][0]["accession"] == "Q1"
        assert h["readings"][0]["value"] == 2.0

    def test_no_price_lookup_in_compute_bypasses_the_context(self):
        """Under a price_cutoff every close must come through Ctx, or an
        as-of reading silently prices at today (the multi-class market-cap
        path did exactly that). The two allowed calls live inside Ctx."""
        from pathlib import Path

        import engine.compute as compute_mod
        src = Path(compute_mod.__file__).read_text(encoding="utf-8")
        assert src.count("price_store.latest_close(") == 2

    def test_price_cutoff_reaches_per_class_prices(self):
        doc = price_store.load(3)
        price_store.merge_series(doc, "SYNB", "tiingo",
                                 [["2025-01-02", 10.0, 0],
                                  ["2025-06-30", 99.0, 0]], [])
        ctx = Ctx([], doc, ["SYN"], price_cutoff="2025-01-05")
        got = ctx.price_for("SYNB")
        assert got == ("2025-01-02", 10.0)
        assert "2025-01-02" in ctx.price_dates_served

    def test_an_unknown_entry_says_so(self):
        h = confirmation_history([], None, ["SYN"], "no_such_entry")
        assert h["readings"] == []
        assert "no computation" in h["note"]


class TestPricePinning:
    def _prices(self):
        doc = price_store.load(1)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2025-01-02", 10.0, 0],
                                  ["2025-06-30", 20.0, 0]], [])
        return doc

    def test_price_cutoff_serves_the_close_of_that_day_not_the_newest(self):
        ctx = Ctx([], self._prices(), ["SYN"], price_cutoff="2025-01-05")
        p = ctx.price_now()
        assert p["close"] == 10.0 and p["date"] == "2025-01-02"
        assert "2025-01-02" in ctx.price_dates_served

    def test_without_a_cutoff_the_newest_close_serves(self):
        assert Ctx([], self._prices(), ["SYN"]).price_now()["close"] == 20.0

    def test_no_close_near_the_cutoff_is_absent_not_borrowed(self):
        ctx = Ctx([], self._prices(), ["SYN"], price_cutoff="2025-03-01")
        assert is_absent(ctx.price_now())


# -- cadence ----------------------------------------------------------------

_QUARTERLY_HELPERS = {"ttm", "ttm_at", "instant_latest", "instant_pair_yoy",
                      "quarterly_observation_fis",
                      "newest_quarterly_after_annual", "latest_fi",
                      "latest_balance_fi"}
_ANNUAL_HELPERS = {"annual_window", "instant_series_annual", "annual_points",
                   "latest_annual_fi", "latest_fiscal_years"}


class _RecordingSB:
    def __init__(self, sb):
        object.__setattr__(self, "_sb", sb)
        object.__setattr__(self, "touched", set())

    def __getattr__(self, name):
        attr = getattr(self._sb, name)
        if callable(attr):
            def wrapped(*a, **k):
                self.touched.add(name)
                return attr(*a, **k)
            return wrapped
        return attr


def _rich_company():
    from conftest import dur
    fs = []
    for i, year in enumerate((2022, 2023, 2024)):
        end, start = f"{year}-12-31", f"{year}-01-01"
        facts = [
            dur("us-gaap:Revenues", start, end, 1000 + i),
            dur("us-gaap:NetIncomeLoss", start, end, 100 + i),
            dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                start, end, 200, stmt="CashFlowStatement"),
            dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                start, end, 50, stmt="CashFlowStatement"),
            dur("us-gaap:EarningsPerShareDiluted", start, end, 2.0,
                unit="usdPerShare", decimals=2),
            dur("us-gaap:PaymentsOfDividendsCommonStock", start, end, 20,
                stmt="CashFlowStatement"),
        ] + balance_face(end, extra=[
            inst("us-gaap:AssetsCurrent", end, 200),
            inst("us-gaap:LiabilitiesCurrent", end, 100),
            inst("us-gaap:StockholdersEquity", end, 400),
            inst("us-gaap:LongTermDebtNoncurrent", end, 100),
        ])
        fs.append(filing(f"K{year}", "10-K", f"{year + 1}-02-20", end, facts))
    q_end = "2025-03-31"
    fs.append(filing("Q1-2025", "10-Q", "2025-05-10", q_end,
                     [dur("us-gaap:Revenues", "2025-01-01", q_end, 260)]
                     + balance_face(q_end, extra=[
                         inst("us-gaap:AssetsCurrent", q_end, 210),
                         inst("us-gaap:LiabilitiesCurrent", q_end, 105),
                     ])))
    return fs


class TestCadence:
    def test_every_computed_entry_declares_a_cadence(self):
        assert set(CADENCE) == set(REGISTRY)
        assert set(CADENCE.values()) <= {"annual", "quarterly"}

    def test_declared_cadence_matches_the_helpers_the_formula_touches(self):
        """The table is a claim about each formula; this derives the fact
        from the formula itself. An entry that consults trailing-twelve-month
        or balance-sheet machinery gains new inputs from a quarterly report;
        one that consults only annual series does not."""
        doc = price_store.load(2)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2025-05-12", 100.0, 0]], [])
        fs = _rich_company()
        untested = []
        for eid, fn in sorted(REGISTRY.items()):
            ctx = Ctx(fs, doc, ["SYN"], params={"risk_free_rate": 4.0})
            rec = _RecordingSB(ctx.sb)
            ctx.sb = rec
            try:
                fn(ctx)
            except Exception:       # noqa: BLE001 — touches already recorded
                pass
            q = rec.touched & _QUARTERLY_HELPERS
            a = rec.touched & _ANNUAL_HELPERS
            if not q and not a:
                untested.append(eid)
                continue
            want = "quarterly" if q else "annual"
            assert CADENCE[eid] == want, \
                f"{eid}: declared {CADENCE[eid]}, touched {sorted(rec.touched)}"
        # Only entries that never consult period data (separate ingestion
        # paths) may go unclassified; anything else escaping the check would
        # gut the test silently.
        assert set(untested) <= {"insider_net_buying_6m",
                                 "institutional_ownership_pct"}, untested


# -- the frozen record ------------------------------------------------------

class TestCloseWithConfirmation:
    def _setup(self):
        p = {**prof([entry("a", sell=ABS2)], DEFAULT_CONF),
             "file": "t.yaml", "id": "t", "name": "Test"}
        sec = holding({"a": 2.5})
        h = {"a": hist("annual",
                       rd("2025-12-31", "2026-02-20", 2.4),
                       rd("2024-12-31", "2025-02-21", 2.2))}
        return sec, p, h

    def test_a_confirmed_breach_freezes_as_a_sell_signal(self):
        sec, p, h = self._setup()
        portfolio.close_position(sec, p, 3, True, "Thesis broken", 12.0,
                                 today=date(2026, 8, 7), histories=h)
        assert sec["exit"]["signal_at_exit"] == "Sell signal"
        assert sec["exit"]["rule_triggered"] is True

    def test_without_histories_the_close_records_the_unconfirmed_breach(self):
        sec, p, _ = self._setup()
        portfolio.close_position(sec, p, 3, True, "Thesis broken", 12.0,
                                 today=date(2026, 8, 7), histories=None)
        assert sec["exit"]["signal_at_exit"] == "Breach unconfirmed"
        assert sec["exit"]["rule_triggered"] is False


# -- the cached provider ----------------------------------------------------

class TestDataviewProvider:
    def test_histories_are_cached_and_keyed_by_params(self):
        from engine import dataview, facts_store
        cik = 777
        for f in [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
                  _quarter("Q2", "2025-08-09", "2025-06-30", 150.0)]:
            facts_store.save_filing(cik, f)
        dataview.invalidate(cik)
        h1 = dataview.confirmation_history(cik, ["SYN"], "current_ratio")
        assert [r["value"] for r in h1["readings"]] == [1.5, 2.0]
        assert dataview.confirmation_history(cik, ["SYN"],
                                             "current_ratio") is h1
        h2 = dataview.confirmation_history(cik, ["SYN"], "current_ratio",
                                           {"risk_free_rate": 4.0})
        assert h2 is not h1
