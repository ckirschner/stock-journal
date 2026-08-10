"""Graham, the first real strategy written against the contract.

What is pinned here is what would fail *silently*. A crash gets noticed; a
plausible wrong verdict does not, and this is the file that decides whether
a novice sells.

Four things in particular:

- **Absence is never success and never failure.** A missing measure must not
  pass an entry test, must not fire an exit, and must not be quietly counted
  either way in the rollup.
- **Nothing fires on one reading.** The two-filing confirmation is the one
  mechanism standing between one impairment and a panic sale, and a gap in
  the filing history must neither confirm a breach nobody saw nor grant an
  indefinite reprieve.
- **Every threshold is the report's.** The numbers are checked against the
  expert report as written, not against whatever the bundle happens to ship
  — a quiet retune is exactly what this project exists to catch.
- **The strategy cites and never quotes.** Every test names the setting that
  holds its limit, so the host reads the number. A strategy that stated its
  own limits could attribute any number at all to any setting.

The contexts below are built by hand rather than from filings, because
driving fifteen measures to chosen values through the compute layer would
test the compute layer. One test at the end goes the whole way through
`context.build_context` so the hand-built shape cannot drift from the real
one.
"""

from datetime import date

import pytest

from conftest import entered, filing, dur, balance_face

from engine import context, contract, facts_store, strategy_loader
from engine import strategy_values

MEASURES = ("pe_3y_avg_eps", "price_to_book", "graham_combined_multiple",
            "current_ratio", "ltd_to_working_capital", "profitable_years_10y",
            "altman_z_score", "eps_growth_10y", "consecutive_dividend_years",
            "debt_to_equity", "price_to_net_tangible_assets",
            "accruals_ratio", "market_cap", "ncav_to_market_cap",
            "earnings_yield_to_risk_free_multiple",
            "consecutive_annual_loss_years")

# A company that clears every entry test. Invented, like everything else
# presented as an example here.
CLEARS_ENTRY = {"pe_3y_avg_eps": 11.0, "price_to_book": 1.1,
                "graham_combined_multiple": 12.1, "current_ratio": 2.4,
                "ltd_to_working_capital": 0.4, "profitable_years_10y": 10,
                "altman_z_score": 3.6, "eps_growth_10y": 48.0,
                "consecutive_dividend_years": 14, "debt_to_equity": 0.6,
                "price_to_net_tangible_assets": 1.4, "accruals_ratio": 0.03,
                "market_cap": 1.4e9, "ncav_to_market_cap": 0.62}

# The same company once held: only the eight exit measures matter now.
CLEARS_EXITS = {"pe_3y_avg_eps": 11.0, "price_to_book": 1.1,
                "graham_combined_multiple": 12.1, "current_ratio": 2.4,
                "ltd_to_working_capital": 0.4, "altman_z_score": 3.6,
                "debt_to_equity": 0.6, "consecutive_annual_loss_years": 0}

QUARTERS = ("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
            "2026-03-31")


@pytest.fixture
def graham():
    strategies, reports = strategy_loader.discover()
    record = strategies.get("graham")
    assert record is not None, [r["errors"] for r in reports if not r["ok"]]
    return record


def values_for(record, **override):
    chain = strategy_values.resolve(
        record, [("journal override", override)] if override else [])
    assert chain["errors"] == [], chain["errors"]
    return chain["values"]


def build(record, known=None, series=None, held=False, opened=None,
          weight=None, occupied=0, today="2026-08-09", **override):
    """A context shaped exactly as engine/context builds one."""
    known, series = known or {}, series or {}
    measures = {}
    for mid in MEASURES:
        current = ({"status": "known", "value": known[mid],
                    "source": "manual", "cautions": [], "provenance": []}
                   if mid in known else
                   {"status": "absent", "reason": "nothing is on record"})
        points = [{"period_end": pe, "filed": pe, "form": "10-Q",
                   "accession": pe, "value": value,
                   "reason": None if value is not None else "unreadable",
                   "cautions": [], "provenance": []}
                  for pe, value in series.get(mid, ())]
        measures[mid] = {"current": current,
                         "series": {"cadence": "quarterly", "points": points,
                                    "note": None, "truncated": False}}
    absent = {"status": "absent", "reason": "no free cash is recorded"}
    return {
        "contract": contract.CONTRACT_VERSION, "today": today,
        "security": {"ticker": "ARBR", "name": "Arbor Mills", "cik": None},
        "measures": measures,
        "price": {"latest": {"status": "absent", "reason": "no price"},
                  "closes": [], "events": []},
        "position": {
            "held": held, "shares": 100.0 if held else 0.0, "opened": opened,
            "lots": [], "disposals": [],
            "market_value": ({"status": "known", "value": 10_000.0,
                              "source": "computed", "cautions": [],
                              "provenance": []} if held else absent),
            "weight": ({"status": "known", "value": weight,
                        "source": "computed", "cautions": [],
                        "provenance": []} if weight is not None else absent)},
        "portfolio": {"cash": absent, "account_value": absent,
                      "slots": {"occupied": occupied}, "holdings": []},
        "values": values_for(record, **override), "inputs": {},
    }


def verdict(record, **kw):
    result = contract.evaluate(record, build(record, **kw))
    assert result["produced_by"] == "strategy", result["reason"]["summary"]
    return result


def outcomes(result):
    """{what was cited: how the host said the comparison came out}."""
    out = {}
    for item in result["reason"]["evidence"]:
        key = item["subject"].get("id") or item["subject"]["label"]
        if item["subject"].get("at"):
            key = f'{key}@{item["subject"]["at"]}'
        out[key] = item["outcome"]
    return out


# ---------------------------------------------------------------------------
# the numbers themselves
# ---------------------------------------------------------------------------

class TestTheThresholdsAreTheReports:
    """Read off the expert report's Graham table and its per-metric notes,
    not off the bundle. Deriving the expectation from the thing under test
    would prove only that it agrees with itself, and the whole reason these
    numbers are in a file of their own is that they are easy to retune."""

    REPORT = {
        # buy column, in the report's order
        "max-pe-3y-avg": 15, "max-price-to-book": 1.5,
        "max-combined-multiple": 22.5, "min-current-ratio": 2.0,
        "max-ltd-to-working-capital": 1.0, "min-profitable-years": 10,
        "min-altman-z": 3.0, "min-eps-growth-10y": 33,
        "min-dividend-years": 10, "max-debt-to-equity": 1.0,
        "max-price-to-tangible": 2.0, "max-accruals-ratio": 0.10,
        "min-market-cap": 300_000_000, "min-ncav-to-market-cap": 0.50,
        "min-earnings-yield-multiple": 2,
        # sell column
        "exit-pe-3y-avg": 25, "exit-price-to-book": 3.0,
        "exit-combined-multiple": 50, "exit-current-ratio": 1.2,
        "exit-ltd-to-working-capital": 2.0, "exit-altman-z": 1.8,
        "exit-debt-to-equity": 2.0, "exit-loss-years": 2,
        # the rollup, the clock and the confirmation rule
        "core-tests-required": 6, "holding-period-months": 24,
        "sell-confirmation-filings": 2,
    }

    def test_every_shipped_default_is_the_reports_number(self, graham):
        shipped = values_for(graham)
        for key, want in self.REPORT.items():
            assert shipped[key] == want, key

    def test_the_two_sizing_values_say_they_are_not_the_reports(self, graham):
        """The report was scoped to selection and exits and says nothing
        about size. Someone reading these later has to be able to tell that
        they came from somewhere else."""
        declared = {v["id"]: v for v in graham["values"]}
        for key in ("portfolio-slots", "position-weight-cap"):
            assert "report" in declared[key]["explain"]
            assert "Graham" in declared[key]["explain"]
        assert values_for(graham)["portfolio-slots"] == 20
        assert values_for(graham)["position-weight-cap"] == 10

    def test_every_declared_value_explains_itself(self, graham):
        for spec in graham["values"]:
            assert len(spec["explain"]) > 120, spec["id"]

    def test_no_test_states_its_own_limit(self, graham):
        """Cite, never quote. A strategy that supplied the number could
        attribute any limit to any setting, and the scorecard that asks
        whether overriding a rule keeps working groups by exactly that."""
        seen = 0
        for kw in ({"known": CLEARS_ENTRY},
                   {"known": CLEARS_EXITS, "held": True,
                    "opened": "2025-09-01"}):
            for item in verdict(graham, **kw)["reason"]["evidence"]:
                test = item["test"]
                if test is None or item["subject"]["kind"] == "stated":
                    continue
                assert test["threshold_from"] is not None, item["subject"]
                seen += 1
        assert seen >= 20


# ---------------------------------------------------------------------------
# the entry screen
# ---------------------------------------------------------------------------

class TestScreening:
    def test_a_company_that_clears_everything_is_a_buy(self, graham):
        result = verdict(graham, known=CLEARS_ENTRY)
        assert result["state"]["id"] == "buy"
        assert result["render"] == "commit"
        # An equal share of twenty places, and the reason says which of the
        # two sizing rules bound.
        assert result["payload"]["size"] == {"unit": "weight", "value": 5.0}
        assert result["payload"]["condition"] is None
        assert "equal share" in result["reason"]["summary"]

    def test_one_knockout_failure_is_enough(self, graham):
        result = verdict(graham,
                         known={**CLEARS_ENTRY, "price_to_book": 2.9})
        assert result["state"]["id"] == "not-cheap-enough"
        assert result["reason"]["rule"] == "knockout-failed"
        assert outcomes(result)["price_to_book"] == "fail"

    def test_a_missing_knockout_is_not_a_pass(self, graham):
        """The failure this most needs to refuse. A company with no book
        value on record must not screen as though it had cleared the book
        test."""
        thin = {k: v for k, v in CLEARS_ENTRY.items() if k != "price_to_book"}
        result = verdict(graham, known=thin)
        assert result["state"]["id"] == "cannot-screen"
        assert result["render"] == "unknown"
        assert outcomes(result)["price_to_book"] == "unknown"

    def test_a_missing_core_test_is_not_a_failure_either(self, graham):
        """Six of eight is the bar. Six passing and two unreadable is six
        passing — the missing ones could not have changed it."""
        thin = {k: v for k, v in CLEARS_ENTRY.items()
                if k not in ("altman_z_score", "accruals_ratio")}
        assert verdict(graham, known=thin)["state"]["id"] == "buy"

    def test_missing_core_tests_that_could_still_decide_it_say_so(self,
                                                                 graham):
        """Five passing, one failed and two unreadable: the two that could
        not be read are the difference between six and not, so nothing is
        claimed in either direction."""
        known = dict(CLEARS_ENTRY)
        known["eps_growth_10y"] = 4.0                       # a real failure
        for missing in ("altman_z_score", "accruals_ratio"):
            known.pop(missing)
        result = verdict(graham, known=known)
        assert result["state"]["id"] == "cannot-screen"
        assert result["reason"]["rule"] == "screen-incomplete"

    def test_core_tests_out_of_reach_is_a_settled_no(self, graham):
        """Three failed with nothing unreadable: six is arithmetically
        impossible, so this is a no rather than a shrug."""
        known = {**CLEARS_ENTRY, "ltd_to_working_capital": 1.9,
                 "altman_z_score": 1.2, "eps_growth_10y": 4.0}
        result = verdict(graham, known=known)
        assert result["state"]["id"] == "not-cheap-enough"
        assert result["reason"]["rule"] == "core-tests-short"

    def test_a_failed_bonus_test_never_blocks(self, graham):
        known = {**CLEARS_ENTRY, "market_cap": 5e6, "ncav_to_market_cap": 0.01}
        result = verdict(graham, known=known)
        assert result["state"]["id"] == "buy"
        assert outcomes(result)["market_cap"] == "fail"

    def test_the_risk_free_test_is_absent_and_blocks_nothing(self, graham):
        """Nothing in this host can be told what the risk-free rate is, so
        the measure that needs it is permanently absent. It is a bonus test
        precisely so that costs nothing, and it must read as unknown rather
        than as a pass."""
        result = verdict(graham, known=CLEARS_ENTRY)
        assert result["state"]["id"] == "buy"
        assert outcomes(result)["earnings_yield_to_risk_free_multiple"] == \
            "unknown"

    def test_a_full_journal_says_so_rather_than_saying_no(self, graham):
        """'I would buy this if I had room' is not 'I would not buy this',
        and a reader with new cash to deploy needs those to look
        different."""
        result = verdict(graham, known=CLEARS_ENTRY, occupied=20)
        assert result["state"]["id"] == "no-room"
        assert result["render"] == "hold"
        assert outcomes(result)["portfolio.slots_occupied"] == "fail"
        # Still a fact about the list, not about the company: every entry
        # test is still shown, and still passing.
        assert outcomes(result)["price_to_book"] == "pass"

    def test_capacity_only_matters_once_it_qualifies(self, graham):
        result = verdict(graham, known={**CLEARS_ENTRY, "price_to_book": 2.9},
                         occupied=20)
        assert result["state"]["id"] == "not-cheap-enough"

    def test_the_weight_cap_binds_where_the_slots_are_few(self, graham):
        """Two independent constraints. Four places is 25% each, which is
        past the cap, so the cap decides and the reason says which."""
        result = verdict(graham, known=CLEARS_ENTRY, **{"portfolio-slots": 4})
        assert result["payload"]["size"] == {"unit": "weight", "value": 10.0}
        assert "cap on any one name" in result["reason"]["summary"]

    def test_a_journal_override_reaches_the_verdict(self, graham):
        """The value chain is not decoration: tightening the knockout in a
        journal's own settings has to change what the strategy says."""
        known = {**CLEARS_ENTRY, "pe_3y_avg_eps": 13.0}
        assert verdict(graham, known=known)["state"]["id"] == "buy"
        strict = verdict(graham, known=known, **{"max-pe-3y-avg": 12})
        assert strict["state"]["id"] == "not-cheap-enough"
        cited = next(e for e in strict["reason"]["evidence"]
                     if e["subject"]["id"] == "pe_3y_avg_eps")
        assert cited["test"]["threshold"] == 12
        assert cited["test"]["threshold_from"]["id"] == "max-pe-3y-avg"


# ---------------------------------------------------------------------------
# holding it
# ---------------------------------------------------------------------------

class TestWatchingAHolding:
    HELD = {"held": True, "opened": "2025-09-01"}

    def test_all_exits_clear_is_nothing_to_do(self, graham):
        result = verdict(graham, known=CLEARS_EXITS, **self.HELD)
        assert result["state"]["id"] == "hold"
        assert result["render"] == "hold"

    def test_a_healthy_holding_reads_as_passes_not_failures(self, graham):
        """Each exit is cited as what the holding must keep being true. Cited
        the other way round — as the level that ends it — a perfectly sound
        position comes back as eight red rows beside a verdict of hold, and
        the reader learns the opposite of what happened."""
        got = outcomes(verdict(graham, known=CLEARS_EXITS, **self.HELD))
        for measure in CLEARS_EXITS:
            assert got[measure] == "pass", measure

    def test_one_reading_past_the_line_does_not_sell(self, graham):
        """The single most important behaviour in the file. One impairment,
        one settlement, one bad quarter, and a measure crosses a line —
        selling on that would be the tool causing the panic it exists to
        prevent."""
        result = verdict(graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
                         series={"price_to_book": [(QUARTERS[3], 1.9),
                                                   (QUARTERS[4], 3.4)]},
                         **self.HELD)
        assert result["state"]["id"] == "one-reading-past"
        assert result["render"] == "hold"
        got = outcomes(result)
        assert got["price_to_book"] == "fail"
        # The one filing that carried it is named, so the count can be
        # checked rather than taken on trust.
        assert got[f"price_to_book@{QUARTERS[4]}"] == "fail"

    def test_two_filings_past_the_line_closes_the_position(self, graham):
        result = verdict(graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
                         series={"price_to_book": [(QUARTERS[2], 1.4),
                                                   (QUARTERS[3], 3.1),
                                                   (QUARTERS[4], 3.4)]},
                         **self.HELD)
        assert result["state"]["id"] == "discount-closed"
        assert result["render"] == "close"
        assert result["payload"]["when"] == "2026-08-09"
        got = outcomes(result)
        assert got[f"price_to_book@{QUARTERS[3]}"] == "fail"
        assert got[f"price_to_book@{QUARTERS[4]}"] == "fail"

    def test_a_gap_in_the_filings_pauses_the_count(self, graham):
        """A reading that could not be worked out must not confirm a breach
        nobody observed — and must not grant an indefinite reprieve either.
        It pauses: two breaching filings with an unreadable one between them
        still confirm, one does not."""
        one_breach = verdict(
            graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
            series={"price_to_book": [(QUARTERS[2], 1.4),
                                      (QUARTERS[3], None),
                                      (QUARTERS[4], 3.4)]}, **self.HELD)
        assert one_breach["state"]["id"] == "one-reading-past"

        through_gap = verdict(
            graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
            series={"price_to_book": [(QUARTERS[1], 3.2),
                                      (QUARTERS[2], None),
                                      (QUARTERS[3], None),
                                      (QUARTERS[4], 3.4)]}, **self.HELD)
        assert through_gap["state"]["id"] == "discount-closed"

    def test_a_clear_filing_resets_the_count(self, graham):
        result = verdict(graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
                         series={"price_to_book": [(QUARTERS[1], 3.6),
                                                   (QUARTERS[2], 3.5),
                                                   (QUARTERS[3], 1.2),
                                                   (QUARTERS[4], 3.4)]},
                         **self.HELD)
        assert result["state"]["id"] == "one-reading-past"

    def test_the_balance_sheet_and_the_price_are_different_news(self, graham):
        """Both end the position and they mean opposite things: one is the
        trade working, the other is it breaking."""
        broke = verdict(graham, known={**CLEARS_EXITS, "altman_z_score": 1.4},
                        series={"altman_z_score": [(QUARTERS[3], 1.6),
                                                   (QUARTERS[4], 1.4)]},
                        **self.HELD)
        assert broke["state"]["id"] == "safety-gone"
        assert broke["render"] == "close"

    def test_safety_outranks_the_discount_closing(self, graham):
        both = verdict(
            graham,
            known={**CLEARS_EXITS, "altman_z_score": 1.4,
                   "price_to_book": 3.4},
            series={"altman_z_score": [(QUARTERS[3], 1.6),
                                       (QUARTERS[4], 1.4)],
                    "price_to_book": [(QUARTERS[3], 3.1),
                                      (QUARTERS[4], 3.4)]},
            **self.HELD)
        assert both["state"]["id"] == "safety-gone"

    def test_two_losing_years_confirm_themselves(self, graham):
        """The one exit the two-filing rule is not applied to twice. Two
        consecutive annual losses are already two consecutive annual
        filings; demanding another two would mean waiting four years."""
        result = verdict(
            graham, known={**CLEARS_EXITS,
                           "consecutive_annual_loss_years": 2}, **self.HELD)
        assert result["state"]["id"] == "safety-gone"

    def test_one_losing_year_is_not_two(self, graham):
        result = verdict(
            graham, known={**CLEARS_EXITS,
                           "consecutive_annual_loss_years": 1}, **self.HELD)
        assert result["state"]["id"] == "hold"

    def test_a_missing_exit_measure_never_sells(self, graham):
        """This program does not sell on silence. An absent reading is not
        evidence a company is in trouble."""
        thin = {k: v for k, v in CLEARS_EXITS.items()
                if k != "altman_z_score"}
        result = verdict(graham, known=thin, **self.HELD)
        assert result["state"]["id"] == "hold"
        assert outcomes(result)["altman_z_score"] == "unknown"
        # And it is not reported as though it had been checked.
        assert "could not be worked out" in result["reason"]["summary"]

    def test_no_exit_readable_at_all_says_it_cannot_tell(self, graham):
        result = verdict(graham, held=True, opened="2026-01-05")
        assert result["state"]["id"] == "cannot-watch"
        assert result["render"] == "unknown"
        assert result["tier"] == "evaluation"

    def test_a_dividend_cut_is_flagged_and_changes_nothing(self, graham):
        result = verdict(
            graham, known=CLEARS_EXITS,
            series={"consecutive_dividend_years": [(QUARTERS[3], 12),
                                                   (QUARTERS[4], 0)]},
            **self.HELD)
        assert result["state"]["id"] == "hold"
        assert "dividend" in result["reason"]["note"]
        assert f"consecutive_dividend_years@{QUARTERS[4]}" in outcomes(result)

    def test_an_unbroken_dividend_run_is_not_flagged(self, graham):
        result = verdict(
            graham, known=CLEARS_EXITS,
            series={"consecutive_dividend_years": [(QUARTERS[3], 12),
                                                   (QUARTERS[4], 13)]},
            **self.HELD)
        assert result["reason"]["note"] is None


class TestTheClock:
    def test_it_fires_on_the_anniversary_and_not_before(self, graham):
        before = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2024-08-10", today="2026-08-09")
        assert before["state"]["id"] == "hold"
        on_the_day = verdict(graham, known=CLEARS_EXITS, held=True,
                             opened="2024-08-09", today="2026-08-09")
        assert on_the_day["state"]["id"] == "time-is-up"
        assert on_the_day["payload"]["when"] == "2026-08-09"

    def test_the_due_date_is_the_scheduled_day_not_today(self, graham):
        """A close carries the day the exit is due. Reporting today's date
        would lose how long it has been overdue, which is the only thing
        this state has to say."""
        late = verdict(graham, known=CLEARS_EXITS, held=True,
                       opened="2024-05-15", today="2026-08-09")
        assert late["payload"]["when"] == "2026-05-15"
        assert "26 months" in late["reason"]["summary"]

    def test_a_month_end_start_does_not_roll_forward(self, graham):
        """31 December plus 24 months is 31 December. 31 January plus one
        month is 28 February, not 3 March — a clock that rolled would move
        an exit date."""
        result = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2024-02-29", today="2026-03-01")
        assert result["payload"]["when"] == "2026-02-28"

    def test_a_confirmed_exit_outranks_the_clock(self, graham):
        """Both end the position; the one that names a cause teaches more."""
        result = verdict(graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
                         series={"price_to_book": [(QUARTERS[3], 3.1),
                                                   (QUARTERS[4], 3.4)]},
                         held=True, opened="2024-01-01")
        assert result["state"]["id"] == "discount-closed"

    def test_the_holding_period_is_a_setting(self, graham):
        result = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2025-09-01", today="2026-08-09",
                         **{"holding-period-months": 6})
        assert result["state"]["id"] == "time-is-up"
        assert result["payload"]["when"] == "2026-03-01"


class TestWhatTheAuditCaught:
    """Four defects an independent read of the source found after the first
    pass. Each of them produced a verdict that was right beside evidence
    that was wrong, which is the failure mode this file exists for — the
    state was correct every time, so nothing crashed and nothing looked
    broken."""

    HELD = {"held": True, "opened": "2025-09-01"}

    def test_the_figure_that_closes_a_position_never_reads_as_a_pass(
            self, graham):
        """The clock fires ON the anniversary. Cited as "at most 24 months"
        it resolved green on exactly that day, so a close verdict carried
        its own cause rendered as a satisfied test."""
        result = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2024-08-09", today="2026-08-09")
        assert result["state"]["id"] == "time-is-up"
        assert outcomes(result)["Months held"] == "fail"

    def test_the_clock_agrees_with_itself_on_a_clamped_date(self, graham):
        """29 February plus two years is 28 February. Counting elapsed
        months by day number made that day read as 23 months held, so the
        position closed while its evidence said the period had not run."""
        result = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2024-02-29", today="2026-02-28")
        assert result["state"]["id"] == "time-is-up"
        assert result["payload"]["when"] == "2026-02-28"
        assert "24 months" in result["reason"]["summary"]
        assert outcomes(result)["Months held"] == "fail"

    def test_an_unreadable_knockout_is_not_counted_as_a_failed_one(self,
                                                                  graham):
        """Grey propagates: an unreadable knockout makes the security grey,
        not red. The state obeyed that and the evidence did not — three
        passes with one unreadable and three passes with one failed both
        cited "3, at least 4" and both rendered as a failure."""
        grey = verdict(graham, known={k: v for k, v in CLEARS_ENTRY.items()
                                      if k != "price_to_book"})
        red = verdict(graham, known={**CLEARS_ENTRY, "price_to_book": 2.9})
        assert grey["state"]["id"] == "cannot-screen"
        assert red["state"]["id"] == "not-cheap-enough"
        # The failing one still states the test. The grey one states the
        # count and says how many could not be worked out.
        assert outcomes(red)["Knockout tests passed"] == "fail"
        assert outcomes(grey)["Knockout tests passed"] == "noted"
        assert "Tests that could not be worked out" in outcomes(grey)
        assert "Tests that could not be worked out" not in outcomes(red)

    def test_self_confirmation_is_derived_from_the_levels_not_declared(
            self, graham):
        """Two losing years span two annual filings, which is why that one
        exit does not pay the confirmation rule twice. Lower the exit to one
        losing year and the reasoning evaporates — so the carve-out has to
        be worked out from the two settings rather than hardcoded, or a
        single reading closes a position while the verdict claims a
        confirmation that never happened."""
        shipped = verdict(graham, known={**CLEARS_EXITS,
                                         "consecutive_annual_loss_years": 2},
                          **self.HELD)
        assert shipped["state"]["id"] == "safety-gone"

        # One losing year, exit lowered to one: no longer self-confirming,
        # so it needs the filings like everything else and has none.
        lowered = verdict(graham,
                          known={**CLEARS_EXITS,
                                 "consecutive_annual_loss_years": 1},
                          **self.HELD, **{"exit-loss-years": 1})
        assert lowered["state"]["id"] == "one-reading-past"

        # And with the filings behind it, it closes.
        confirmed = verdict(
            graham, known={**CLEARS_EXITS,
                           "consecutive_annual_loss_years": 1},
            series={"consecutive_annual_loss_years": [(QUARTERS[3], 1),
                                                      (QUARTERS[4], 1)]},
            **self.HELD, **{"exit-loss-years": 1})
        assert confirmed["state"]["id"] == "safety-gone"

    def test_a_dividend_cut_stays_flagged_after_the_next_filing(self,
                                                               graham):
        """The run resets to zero on one filing and climbs from one on the
        next, so a flag that compared only the newest pair appeared for a
        single reporting period and vanished. Fetching is something the user
        does when they think of it, so that period is the one most likely to
        be missed entirely."""
        later = verdict(
            graham, known=CLEARS_EXITS,
            series={"consecutive_dividend_years": [(QUARTERS[1], 12),
                                                   (QUARTERS[2], 0),
                                                   (QUARTERS[3], 1),
                                                   (QUARTERS[4], 2)]},
            **self.HELD)
        assert "dividend" in (later["reason"]["note"] or "")

    def test_a_cut_before_this_holding_began_is_not_this_holding_s_news(
            self, graham):
        result = verdict(
            graham, known=CLEARS_EXITS,
            series={"consecutive_dividend_years": [(QUARTERS[0], 12),
                                                   (QUARTERS[1], 0)]},
            held=True, opened="2025-08-01")
        assert result["reason"]["note"] is None


class TestTheWeightCap:
    def test_a_position_that_outgrew_the_cap_is_trimmed_back_to_it(self,
                                                                  graham):
        result = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2025-09-01", weight=18.2)
        assert result["state"]["id"] == "too-big"
        assert result["render"] == "reduce"
        assert result["payload"]["to"] == {"unit": "weight", "value": 10.0}

    def test_it_cannot_fire_without_an_account_to_measure_against(self,
                                                                 graham):
        """Free cash is optional, and where it is unanswered the weight is
        absent. An absent weight must not trim anything, and must say the
        test could not be run rather than that it passed."""
        result = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2025-09-01")
        assert result["state"]["id"] == "hold"
        assert outcomes(result)["position.weight"] == "unknown"

    def test_an_exit_outranks_a_trim(self, graham):
        result = verdict(graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
                         series={"price_to_book": [(QUARTERS[3], 3.1),
                                                   (QUARTERS[4], 3.4)]},
                         held=True, opened="2025-09-01", weight=18.2)
        assert result["state"]["id"] == "discount-closed"


# ---------------------------------------------------------------------------
# the whole way through
# ---------------------------------------------------------------------------

class TestEveryStateIsReachable:
    """A declared state nothing can produce is vocabulary a user will never
    see and a description nobody ever checks."""

    def test_all_eleven(self, graham):
        held = {"held": True, "opened": "2025-09-01"}
        breach = {"price_to_book": [(QUARTERS[3], 3.1), (QUARTERS[4], 3.4)]}
        reached = {
            verdict(graham, known=CLEARS_ENTRY)["state"]["id"],
            verdict(graham, known=CLEARS_ENTRY,
                    occupied=20)["state"]["id"],
            verdict(graham, known={**CLEARS_ENTRY, "price_to_book": 2.9}
                    )["state"]["id"],
            verdict(graham, known={k: v for k, v in CLEARS_ENTRY.items()
                                   if k != "price_to_book"})["state"]["id"],
            verdict(graham, known=CLEARS_EXITS, **held)["state"]["id"],
            verdict(graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
                    series={"price_to_book": [(QUARTERS[4], 3.4)]},
                    **held)["state"]["id"],
            verdict(graham, known=CLEARS_EXITS, weight=18.2,
                    **held)["state"]["id"],
            verdict(graham, known={**CLEARS_EXITS, "price_to_book": 3.4},
                    series=breach, **held)["state"]["id"],
            verdict(graham, known={**CLEARS_EXITS,
                                   "consecutive_annual_loss_years": 2},
                    **held)["state"]["id"],
            verdict(graham, known=CLEARS_EXITS, held=True,
                    opened="2024-01-01")["state"]["id"],
            verdict(graham, held=True, opened="2026-01-05")["state"]["id"],
        }
        assert reached == {s["id"] for s in graham["states"]}


class TestThroughTheRealContext:
    """One pass through the machinery the app actually uses, so the
    hand-built contexts above cannot drift from the shape the host serves."""

    def test_hand_entered_figures_screen_a_candidate(self, graham, tmp_path):
        security = {"ticker": "ARBR", "name": "Arbor Mills", "cik": 4242,
                    "lots": []}
        # A filing has to exist for the company to have a series at all;
        # the figures themselves are entered by hand, as a user without a
        # data connection would enter them.
        facts_store.save_filing(4242, filing(
            "ARBR-1", "10-K", "2026-02-11", "2025-12-31",
            [dur("us-gaap:Revenues", "2025-01-01", "2025-12-31", 900)]
            + balance_face("2025-12-31", assets=700)))
        entered(security, **CLEARS_ENTRY)

        result = contract.evaluate(
            graham, context.build_context(security, [security],
                                          values_for(graham), {},
                                          record=graham))
        assert result["produced_by"] == "strategy"
        assert result["state"]["id"] == "buy"
        cited = next(e for e in result["reason"]["evidence"]
                     if e["subject"]["id"] == "price_to_book")
        # The host answered with the bank's own label and unit, and with the
        # provenance of a figure the user typed.
        assert cited["subject"]["label"] == "Price to book"
        assert cited["observed"]["value"] == 1.1
        assert cited["outcome"] == "pass"
        # A resolved citation reports its subject kind, so where the figure
        # came from lives in the provenance rather than in `source`.
        assert any("by hand" in p for p in cited["observed"]["provenance"])

    def test_a_journal_with_no_data_at_all_says_so(self, graham):
        security = {"ticker": "NONE", "name": "Nothing Fetched", "lots": []}
        result = contract.evaluate(
            graham, context.build_context(security, [security],
                                          values_for(graham), {},
                                          record=graham))
        assert result["state"]["id"] == "cannot-screen"
        assert result["render"] == "unknown"

    def test_free_cash_unlocks_the_weight_the_cap_needs(self, graham):
        """The one input this strategy declares, and the only thing that
        turns position weight from absent into a figure."""
        security = {"ticker": "ARBR", "name": "Arbor Mills", "cik": 4343,
                    "lots": [{"id": "L1", "kind": "buy", "date": "2026-01-05",
                              "shares": 100.0, "price": 20.0,
                              "recorded": "2026-01-05T00:00:00+00:00"}],
                    "price": 30.0}
        entered(security, **CLEARS_EXITS)
        ctx = context.build_context(security, [security], values_for(graham),
                                    {"free-cash": 6_000.0}, record=graham)
        assert ctx["position"]["weight"]["status"] == "known"
        # 100 shares at 30 is 3,000 of a 9,000 account.
        assert round(ctx["position"]["weight"]["value"], 1) == 33.3
        result = contract.evaluate(graham, ctx)
        assert result["state"]["id"] == "too-big"
        assert result["payload"]["to"]["value"] == 10.0


def test_the_bundle_declares_fewer_states_than_the_cap(graham):
    """Not an assertion that eleven is right — a marker that the most
    mechanical of the four strategies needs eleven of the twelve a strategy
    is allowed, which is the only evidence anyone has about that cap."""
    assert len(graham["states"]) == 11
    assert len(graham["states"]) <= contract.MAX_STATES


def test_the_clock_arithmetic_matches_the_calendar():
    """Worked out on a calendar, not through the function under test."""
    from importlib import util
    spec = util.spec_from_file_location(
        "graham_clock", "strategies/graham/strategy.py")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._plus_months(date(2024, 5, 15), 24) == date(2026, 5, 15)
    assert module._plus_months(date(2024, 2, 29), 24) == date(2026, 2, 28)
    assert module._plus_months(date(2025, 1, 31), 1) == date(2025, 2, 28)
    assert module._plus_months(date(2025, 12, 31), 24) == date(2027, 12, 31)
    assert module._months_elapsed(date(2024, 5, 15), date(2026, 5, 14)) == 23
    assert module._months_elapsed(date(2024, 5, 15), date(2026, 5, 15)) == 24
    # The clamped case, where counting by day numbers disagrees with the due
    # date: opened 29 February, due 28 February two years later, and on that
    # day the position has been held 24 months and not 23.
    assert module._plus_months(date(2024, 2, 29), 24) == date(2026, 2, 28)
    assert module._months_elapsed(date(2024, 2, 29), date(2026, 2, 28)) == 24


def test_the_clock_and_the_evidence_can_never_disagree(graham):
    """The figure that closes a position must not render as a passing test.

    Two halves decide this — the due date and the months-held figure cited
    beside it — and they used to be computed different ways. Swept over
    every start date in four years against every holding period the setting
    allows, because the disagreement only appeared on month ends.
    """
    from importlib import util
    from datetime import timedelta
    spec = util.spec_from_file_location(
        "graham_clock2", "strategies/graham/strategy.py")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    start = date(2024, 1, 1)
    for days in range(0, 4 * 365, 1):
        opened = start + timedelta(days=days)
        for limit in (1, 6, 18, 24, 36):
            due = module._plus_months(opened, limit)
            for probe in (due - timedelta(days=1), due, due + timedelta(days=1)):
                elapsed = probe >= due
                counted = module._months_elapsed(opened, probe) >= limit
                assert elapsed == counted, (opened, limit, probe)
