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


def _baseline(when, values):
    """One anchor purchase as engine/context serves it: the day, and the
    figures frozen onto that decision."""
    return {"status": "known", "date": when, "lot": "l1",
            "measures": {mid: {"status": "known", "value": v,
                               "source": "frozen", "cautions": [],
                               "provenance": []}
                         for mid, v in values.items()}}


def build(record, known=None, series=None, held=False, opened=None,
          weight=None, occupied=0, today="2026-08-09", bought=None,
          purchases=1, **override):
    """A context shaped exactly as engine/context builds one.

    `bought` is what was on record at the two anchor purchases:
    {"first": {measure: value}, "last": {...}}. Left out on a holding, both
    anchors carry today's figures — nothing has moved since either purchase,
    which is what makes an unchanged business the default and drift
    something a test has to ask for. Left out on a candidate, both are
    absent, because there is no purchase to measure from.
    """
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
    bought = bought or {}
    no_purchase = {"status": "absent",
                   "reason": "no position is held, so there is no purchase "
                             "to measure from"}
    baselines = {}
    for anchor, key in (("first-purchase", "first"), ("last-purchase", "last")):
        if not held:
            baselines[anchor] = no_purchase
        else:
            baselines[anchor] = _baseline(opened, bought.get(key, known))
    return {
        "contract": contract.CONTRACT_VERSION, "today": today,
        "security": {"ticker": "ARBR", "name": "Arbor Mills", "cik": None},
        "measures": measures,
        "price": {"latest": {"status": "absent", "reason": "no price"},
                  "closes": [], "events": []},
        "position": {
            "held": held, "shares": 100.0 if held else 0.0, "opened": opened,
            # Built the way engine/context builds it — through the host's
            # own month arithmetic, which is the only thing that knows about
            # 29 February. The arithmetic itself is checked against a
            # calendar in tests/test_contract.py, not here.
            "months_held": (contract.months_between(opened, today)
                            if held and opened else None),
            "last_purchase": opened if held else None,
            "purchases": purchases if held else 0,
            "baselines": baselines,
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


def rollup(result):
    """{group id: the rollup the HOST counted from the rows it resolved}."""
    return {g["id"]: g for g in result["reason"]["groups"]}


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

    def test_no_test_states_its_own_limit_without_showing_its_working(
            self, graham):
        """Cite, never quote. A strategy that supplied the number could
        attribute any limit to any setting, and the scorecard that asks
        whether overriding a rule keeps working groups by exactly that.

        One row states its own limit and is allowed to: the earnings-yield
        test's ceiling is worked out from two settings, and a row cites one
        setting or states one number — there is no way to name two. The
        condition on that exemption is that both settings are cited in the
        same group, so the arithmetic is on the screen and the reader can
        redo it. A stated limit with nothing behind it would be this
        strategy asking to be believed.
        """
        seen, stated = 0, 0
        for kw in ({"known": CLEARS_ENTRY},
                   {"known": CLEARS_EXITS, "held": True,
                    "opened": "2025-09-01"}):
            evidence = verdict(graham, **kw)["reason"]["evidence"]
            for item in evidence:
                test = item["test"]
                if test is None or item["subject"]["kind"] == "stated":
                    continue
                if test["threshold_from"] is None:
                    stated += 1
                    shown = {e["subject"]["id"] for e in evidence
                             if e["group"] == item["group"]
                             and e["subject"]["kind"] == "value"}
                    assert shown >= {"min-earnings-yield-multiple",
                                     "risk-free-rate"}, item["subject"]
                    continue
                seen += 1
        assert seen >= 20
        assert stated == 1, "only the derived limit may state itself"


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
        known = {**CLEARS_ENTRY, "ncav_to_market_cap": 0.01}
        result = verdict(graham, known=known)
        assert result["state"]["id"] == "buy"
        assert outcomes(result)["ncav_to_market_cap"] == "fail"

    def test_a_company_under_the_size_floor_is_refused_outright(self, graham):
        """The floor is a floor. Size was a scored test until v3, so a
        company below it could be bought on the strength of everything else
        — and the argument for the level is filing quality and being able to
        sell, neither of which a low price-to-book makes up for."""
        result = verdict(graham, known={**CLEARS_ENTRY, "market_cap": 40e6})
        assert result["state"]["id"] == "not-cheap-enough"
        assert result["reason"]["rule"] == "knockout-failed"
        assert outcomes(result)["market_cap"] == "fail"

    def test_a_size_nobody_could_work_out_is_not_a_pass(self, graham):
        """The other half of moving it. An absent knockout cannot be shrugged
        off the way an absent bonus test could — it has to stop the verdict
        rather than cost nothing, or absence reads as success at the one test
        that exists to keep an unsellable position out."""
        known = {k: v for k, v in CLEARS_ENTRY.items() if k != "market_cap"}
        result = verdict(graham, known=known)
        assert result["state"]["id"] == "cannot-screen"
        assert outcomes(result)["market_cap"] == "unknown"

    def test_the_risk_free_test_runs_and_still_blocks_nothing(self, graham):
        """It used to be permanently absent: the measure needed a risk-free
        rate and nothing could supply one, so a row that looked like a test
        never once ran. The rate is a declared value now and the strategy
        makes the comparison itself, so the test produces a real answer —
        and it is still a bonus test, so the answer decides nothing.

        CLEARS_ENTRY is at 11 times typical earnings, a 9.1% earnings yield.
        Against twice a 4% rate — 8% — that passes; at a 6% rate it would
        not, and the verdict would be the same buy either way.
        """
        result = verdict(graham, known=CLEARS_ENTRY)
        assert result["state"]["id"] == "buy"
        bonus = [e for e in result["reason"]["evidence"]
                 if e["group"] == "bonus" and e["test"]
                 and e["subject"]["id"] == "pe_3y_avg_eps"]
        assert len(bonus) == 1
        assert bonus[0]["outcome"] == "pass"
        assert bonus[0]["test"]["threshold"] == 12.5

        dear = verdict(graham, known=CLEARS_ENTRY, **{"risk-free-rate": 6.0})
        assert dear["state"]["id"] == "buy"
        assert [e for e in dear["reason"]["evidence"]
                if e["group"] == "bonus" and e["test"]
                and e["subject"]["id"] == "pe_3y_avg_eps"
                ][0]["outcome"] == "fail"

    def test_a_rate_of_nought_shows_the_settings_instead_of_a_comparison(
            self, graham):
        """The earnings-yield limit is worked out from two settings, and
        either can be overridden to nought in a journal. Dividing by that
        would take the whole verdict down over a bonus test that blocks
        nothing — so no limit is built, and the two settings are shown as the
        observations they are. A row that simply vanished would leave the
        reader with no way to see that a test exists at all."""
        result = verdict(graham, known=CLEARS_ENTRY,
                         **{"risk-free-rate": 0})
        assert result["state"]["id"] == "buy"
        bonus = [e for e in result["reason"]["evidence"]
                 if e["group"] == "bonus"]
        assert not [e for e in bonus if e["test"]
                    and e["subject"]["id"] == "pe_3y_avg_eps"]
        shown = {e["subject"]["id"] for e in bonus
                 if e["subject"]["kind"] == "value"}
        assert shown == {"min-earnings-yield-multiple", "risk-free-rate"}

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


class TestTheRollupIsTheHostsAndNotItsOwn:
    """The reasoning that used to live in the order of a list and a count
    this strategy tallied itself. Four knockouts where all must pass, six of
    eight core, three that never block — a reader with fifteen rows in front
    of them needs to know which four were disqualifying."""

    def test_the_screen_reads_as_headings_and_not_one_flat_list(self,
                                                                graham):
        result = verdict(graham, known=CLEARS_ENTRY)
        assert [g["name"] for g in result["reason"]["groups"]] == [
            "Tests this strategy will not bend", "Core tests",
            "Reported, never blocking", "Room in the list, and how much"]
        got = rollup(result)
        assert got["knockouts"]["requires"] == "all"
        assert got["knockouts"]["tested"] == 5
        assert got["core"]["requires"] == "at_least"
        assert got["bonus"]["requires"] == "noted"

    def test_six_of_eight_is_counted_by_the_host_from_its_own_rows(self,
                                                                   graham):
        result = verdict(graham, known=CLEARS_ENTRY)
        core = rollup(result)["core"]
        rows = [e for e in result["reason"]["evidence"]
                if e["group"] == "core"]
        assert core["tested"] == len(rows) == 8
        assert core["passed"] == sum(1 for r in rows
                                     if r["outcome"] == "pass")
        # The bar is cited, not stated: the host read it out of the setting.
        assert core["test"]["threshold"] == 6
        assert core["test"]["threshold_from"]["id"] == "core-tests-required"
        assert core["outcome"] == "pass"

    def test_a_journal_that_moves_the_bar_moves_the_rollup(self, graham):
        strict = verdict(graham, known=CLEARS_ENTRY,
                         **{"core-tests-required": 8})
        assert rollup(strict)["core"]["test"]["threshold"] == 8

    def test_the_bonus_heading_carries_its_failures_and_blocks_nothing(
            self, graham):
        result = verdict(graham,
                         known={**CLEARS_ENTRY, "ncav_to_market_cap": 0.01})
        assert result["state"]["id"] == "buy"
        assert rollup(result)["bonus"]["failed"] == 1
        assert rollup(result)["bonus"]["outcome"] == "noted"

    def test_every_row_sits_under_a_heading(self, graham):
        """A row with no heading is a row the reader cannot place, and on a
        buy it is also a row the host has to treat strictly because nothing
        said otherwise."""
        for kw in ({"known": CLEARS_ENTRY},
                   {"known": CLEARS_ENTRY, "occupied": 20},
                   {"known": {**CLEARS_ENTRY, "price_to_book": 2.9}},
                   {"known": CLEARS_EXITS, "held": True,
                    "opened": "2025-09-01"}):
            result = verdict(graham, **kw)
            declared = {g["id"] for g in result["reason"]["groups"]}
            for item in result["reason"]["evidence"]:
                assert item["group"] in declared, item["subject"]


class TestABuyCannotContradictItsOwnEvidence:
    def test_the_shipped_bundle_never_trips_the_host_check(self, graham):
        """Every route to a commit, checked against the host's own reading
        of the rows it cited. A `host:invalid-decision` here would mean the
        strategy and the host disagreed about what it had just looked at."""
        for kw in ({"known": CLEARS_ENTRY},
                   {"known": CLEARS_ENTRY, "portfolio-slots": 4},
                   {"known": {**CLEARS_ENTRY, "ncav_to_market_cap": 0.01}},
                   {"known": {k: v for k, v in CLEARS_ENTRY.items()
                              if k not in ("altman_z_score",
                                           "accruals_ratio")}}):
            result = verdict(graham, **kw)
            assert result["state"]["id"] == "buy", kw
            assert result["produced_by"] == "strategy"

    def test_a_knockout_the_host_reads_as_failed_cannot_produce_a_buy(
            self, graham, monkeypatch):
        """The defect, staged. A strategy that decided a knockout had passed
        while the host read it as failed used to return a buy beside a red
        row, and both rendered. Now the host refuses the verdict.

        Staged by making the strategy's own reading lie rather than by
        editing the bundle, because the point is what the HOST does when the
        two disagree — not that this bundle happens not to disagree.
        """
        from importlib import util
        spec = util.spec_from_file_location(
            "graham_liar", "strategies/graham/strategy.py")
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        monkeypatch.setattr(module.contract, "test",
                            lambda ctx, item: module.contract.PASS)
        rec = dict(graham, decide=module.decide)
        result = contract.evaluate(
            rec, build(rec, known={**CLEARS_ENTRY, "price_to_book": 2.9}))
        assert result["produced_by"] == "host"
        assert result["state"]["id"] == "host:invalid-decision"
        assert "Tests this strategy will not bend" in \
            result["reason"]["summary"]


class TestEveryValueSaysWhereItCameFrom:
    def test_all_thirty_four_carry_a_source(self, graham):
        assert len(graham["values"]) == 34
        for spec in graham["values"]:
            assert spec["source"]["name"], spec["id"]
            assert isinstance(spec["source"]["reasoning"], bool), spec["id"]

    def test_the_drift_tolerances_claim_no_source_but_the_author(self, graham):
        """Neither the expert report nor Graham addresses adding to a
        position already held. Attributing these to either would be borrowing
        authority for a number the source does not contain — and these are
        the five settings in the file most worth arguing with, which is
        exactly why the attribution has to say so."""
        declared = {v["id"]: v for v in graham["values"]}
        drift = [k for k in declared if k.startswith("drift-")]
        assert len(drift) == 5
        for key in drift:
            name = declared[key]["source"]["name"]
            assert "own author" in name
            assert "no source" in name

    def test_the_two_sizing_values_are_not_the_reports(self, graham):
        """The report was scoped to selection and exits and says nothing
        about size. Someone reading these later has to be able to tell that
        they came from somewhere else — and that claim now sits on the value
        rather than in a paragraph at the top of the file."""
        declared = {v["id"]: v for v in graham["values"]}
        for key in ("portfolio-slots", "position-weight-cap"):
            assert "Graham" in declared[key]["source"]["name"]
            assert "report" in declared[key]["source"]["name"]
        assert values_for(graham)["portfolio-slots"] == 20
        assert values_for(graham)["position-weight-cap"] == 10

    def test_those_with_borrowed_levels_say_whose_reasoning_it_is(self,
                                                                  graham):
        """The report states these levels and gives no reasoning for them.
        The account in `explain` is this strategy's, and that used to be a
        paragraph pasted into six explanations — a claim nothing checked, on
        a field where a seventh value could quietly be added without it."""
        declared = {v["id"]: v for v in graham["values"]}
        borrowed = {vid for vid, v in declared.items()
                    if not v["source"]["reasoning"]}
        assert borrowed == {"core-tests-required", "max-price-to-tangible",
                            "min-market-cap",
                            "exit-price-to-book", "exit-current-ratio",
                            "exit-ltd-to-working-capital",
                            "exit-debt-to-equity"}
        # And the sentence they used to carry by hand is gone from all of
        # them, so there is exactly one place the claim is made.
        for spec in graham["values"]:
            assert "states this level and not the reason" not in \
                spec["explain"], spec["id"]


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
        assert outcomes(result)["position.months_held"] == "fail"

    def test_the_clock_agrees_with_itself_on_a_clamped_date(self, graham):
        """29 February plus two years is 28 February. Counting elapsed
        months by day number made that day read as 23 months held, so the
        position closed while its evidence said the period had not run."""
        result = verdict(graham, known=CLEARS_EXITS, held=True,
                         opened="2024-02-29", today="2026-02-28")
        assert result["state"]["id"] == "time-is-up"
        assert result["payload"]["when"] == "2026-02-28"
        assert "24 months" in result["reason"]["summary"]
        assert outcomes(result)["position.months_held"] == "fail"

    def test_an_unreadable_knockout_is_not_counted_as_a_failed_one(self,
                                                                  graham):
        """Grey propagates: an unreadable knockout makes the security grey,
        not red. The state obeyed that and the evidence did not — three
        passes with one unreadable and three passes with one failed both
        cited "3, at least 4" and both rendered as a failure.

        The rollup is the host's now, counted from the rows it resolved, and
        the three-way answer falls out of that: three passes and one failure
        is a settled no, three passes and one unreadable is undecided, and
        the counts beside them say which is which.
        """
        grey = verdict(graham, known={k: v for k, v in CLEARS_ENTRY.items()
                                      if k != "price_to_book"})
        red = verdict(graham, known={**CLEARS_ENTRY, "price_to_book": 2.9})
        assert grey["state"]["id"] == "cannot-screen"
        assert red["state"]["id"] == "not-cheap-enough"

        assert rollup(red)["knockouts"]["outcome"] == "fail"
        assert rollup(red)["knockouts"]["failed"] == 1
        assert rollup(red)["knockouts"]["unknown"] == 0

        assert rollup(grey)["knockouts"]["outcome"] == "unknown"
        assert rollup(grey)["knockouts"]["failed"] == 0
        assert rollup(grey)["knockouts"]["unknown"] == 1
        # Both counted the same passes. The count on its own was the thing
        # that could not tell them apart.
        assert rollup(red)["knockouts"]["passed"] == 4
        assert rollup(grey)["knockouts"]["passed"] == 4

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

    def test_all_thirteen(self, graham):
        held = {"held": True, "opened": "2025-09-01"}
        breach = {"price_to_book": [(QUARTERS[3], 3.1), (QUARTERS[4], 3.4)]}
        # A holding that still screens, sits well under its target and has
        # not moved since either purchase. Nothing here is about what it
        # cost — the strategy has no access to that and could not use it.
        room = {"known": {**CLEARS_ENTRY, **CLEARS_EXITS}, "weight": 2.0,
                **held}
        reached = {
            verdict(graham, **room)["state"]["id"],
            # The same holding, where the current ratio stood at 3.6 when it
            # was first bought and is 2.4 now. Not one exit has been crossed
            # — 2.4 is comfortably above the 1.2 that sells — and the total
            # move is further than this strategy will add behind.
            verdict(graham, bought={"first": {**CLEARS_ENTRY, **CLEARS_EXITS,
                                              "current_ratio": 3.6}},
                    **room)["state"]["id"],
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
    """Not an assertion that thirteen is right — a marker that the most
    mechanical style of investing there is needs thirteen states, which is
    the only evidence anyone has about where that cap belongs. It sat at
    twelve and this bundle used eleven of them; the cap moved to sixteen on
    the strength of exactly that measurement, and adding to an open position
    then cost two more. Three left."""
    assert len(graham["states"]) == 13
    assert len(graham["states"]) <= contract.MAX_STATES


def test_the_clock_reads_the_hosts_figure_and_does_no_arithmetic(graham):
    """Both halves of the clock are the host's now.

    The months-held figure is a host fact and the due date is
    `contract.months_after`, so the two cannot be computed different ways —
    which is what they were, and what made a position close on the day its
    own evidence said the period had not run. The arithmetic itself is
    checked against a calendar in tests/test_contract.py; this checks that
    Graham no longer has any of its own.
    """
    from importlib import util
    spec = util.spec_from_file_location(
        "graham_clock", "strategies/graham/strategy.py")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert not [n for n in vars(module)
                if n in ("_plus_months", "_months_elapsed", "_iso")]

    result = verdict(graham, known=CLEARS_EXITS, held=True,
                     opened="2024-02-29", today="2026-02-28")
    assert result["payload"]["when"] == contract.months_after("2024-02-29",
                                                              24)
    cited = next(e for e in result["reason"]["evidence"]
                 if e["subject"]["id"] == "position.months_held")
    assert cited["observed"]["value"] == contract.months_between(
        "2024-02-29", "2026-02-28")
