"""The worked example in docs/, which ships with the repository and is
deliberately not installed.

An example nobody runs is an example that rots, and a wrong one costs more
than none at all — the first strategy anybody writes will be a copy of this.
So it is loaded here through the same loader the app uses, pointed at the
directory it actually lives in, and every state it declares is reached.

It is NOT under `strategies/`, so the app never discovers it and no journal
can be created against it. That is the whole reason this file exists: the
loader is the only thing that would otherwise have checked it.
"""

from pathlib import Path

import pytest

from conftest import balance_face, dur, filing, industry_node

from engine import context, contract, facts_store, judgements
from engine import strategy_loader, strategy_values

DOCS = Path(__file__).resolve().parent.parent / "docs"

MEASURES = ("roic_median_5y", "total_debt_to_ebitda", "current_ratio",
            "fcf_margin_ttm", "interest_coverage")

# A business that clears everything. Invented, like every figure in the
# bundle it is being fed to.
CLEARS = {"roic_median_5y": 18.0, "total_debt_to_ebitda": 1.2,
          "current_ratio": 1.8, "fcf_margin_ttm": 12.0,
          "interest_coverage": 15.0}

QUARTERS = ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31")


@pytest.fixture
def example():
    strategies, reports = strategy_loader.discover([DOCS])
    record = strategies.get("worked-example")
    assert record is not None, [r["errors"] for r in reports if not r["ok"]]
    return record


def values_for(record, **override):
    chain = strategy_values.resolve(
        record, [("journal override", override)] if override else [])
    assert chain["errors"] == [], chain["errors"]
    return chain["values"]


def build(record, known=None, series=None, moat=None, held=False,
          weight=None, today="2026-08-09", industry=None, **override):
    """A context shaped exactly as engine/context builds one.

    Built by hand rather than from filings because driving five measures to
    chosen values through the compute layer would be a test of the compute
    layer. The last class in this file goes the whole way through
    `context.build_context` so this shape cannot drift from the real one.
    """
    known, series = known or {}, series or {}
    measures = {}
    for mid in MEASURES:
        points = [{"period_end": pe, "filed": pe, "form": "10-Q",
                   "accession": pe, "value": value,
                   "reason": None if value is not None else "unreadable",
                   "cautions": [], "provenance": []}
                  for pe, value in series.get(mid, ())]
        measures[mid] = {
            "current": ({"status": "known", "value": known[mid],
                         "source": "manual", "cautions": [], "provenance": []}
                        if mid in known
                        else {"status": "absent",
                              "reason": "nothing is on record"}),
            "series": {"cadence": "quarterly", "points": points,
                       "note": None, "truncated": False}}
    measures["moat_durability"] = {
        "current": ({"status": "known", "value": moat, "source": "judgement",
                     "cautions": [],
                     "provenance": ["your assessment of 2026-01-01",
                                    "because"]}
                    if moat is not None
                    else {"status": "absent",
                          "reason": "assessed by you, not computed — nothing "
                                    "is recorded in this journal yet"}),
        "series": {"cadence": None, "points": [], "note": None,
                   "truncated": False}}
    absent = {"status": "absent", "reason": "no free cash is recorded"}

    def figure(value):
        return ({"status": "known", "value": value, "source": "computed",
                 "cautions": [], "provenance": []} if value is not None
                else absent)

    return {
        "contract": contract.CONTRACT_VERSION, "today": today,
        "security": {"ticker": "WDGE", "name": "Wedgemoor Fasteners",
                     "cik": None,
                     "sic": {"status": "absent",
                             "reason": "a hand-built context"},
                     "industry": industry_node(industry)},
        "measures": measures,
        "price": {"latest": {"status": "absent", "reason": "no price"},
                  "closes": [], "events": []},
        "position": {
            "held": held, "shares": 100.0 if held else 0.0,
            "opened": "2025-01-15" if held else None,
            "months_held": (contract.months_between("2025-01-15", today)
                            if held else None),
            "last_purchase": "2025-01-15" if held else None,
            "purchases": 1 if held else 0,
            "baselines": {a: {"status": "absent", "reason": "not used here"}
                          for a in contract.BASELINE_ANCHORS},
            "lots": [], "disposals": [],
            "market_value": figure(10_000.0 if held else None),
            "weight": figure(weight)},
        "portfolio": {"cash": absent, "account_value": absent,
                      "slots": {"occupied": 1 if held else 0},
                      "holdings": []},
        "values": values_for(record, **override),
        "inputs": {},
    }


def verdict(record, **kw):
    result = contract.evaluate(record, build(record, **kw))
    assert result["state"]["id"] != "host:invalid-decision", \
        result["reason"]["summary"]
    return result


def falling(*values):
    """A per-filing series, oldest first, one reading per quarter."""
    return list(zip(QUARTERS, values))


class TestItLoads:
    def test_the_bundle_the_documentation_points_at_is_the_one_that_loads(
            self, example):
        assert example["name"] == "Worked example"
        assert example["contract"] == contract.CONTRACT_VERSION
        assert (DOCS / "example-strategy" / "values.yaml").exists()

    def test_it_is_not_installed_and_cannot_be_journalled_against(self):
        """The app discovers `strategies/` and nothing else. An example that
        loaded there would be a set of invented thresholds someone could
        record real purchases against."""
        shipped, _ = strategy_loader.discover()
        assert "worked-example" not in shipped

    def test_every_shipped_default_matches_its_declaration(self, example):
        """The loader refuses a bundle whose defaults do not fit what it
        declares, so this passing at all is the check — asserted here so the
        example cannot be edited into a state where it silently stops being
        loadable and no test says which half moved."""
        assert strategy_values.check_defaults(
            example, {"version": example["values_version"],
                      "values": example["defaults"]}, "values.yaml") == []

    def test_nothing_in_it_reads_as_a_recommendation(self, example):
        """Every declared value says where its number came from, and every
        one of them says the same thing: nowhere. A demonstration threshold
        that claimed a source would be the one sentence in this repository
        that turned an example into advice."""
        for v in example["values"]:
            assert "invented" in v["source"]["name"], v["id"]
            assert "recommendation" in v["source"]["name"], v["id"]


class TestTheTwoTierRollup:
    def test_a_knockout_ends_it_whatever_else_passed(self, example):
        r = verdict(example, known={**CLEARS, "total_debt_to_ebitda": 6.0})
        assert r["state"]["id"] == "not-good-enough"
        assert r["reason"]["rule"] == "knockout-failed"
        knockouts = next(g for g in r["reason"]["groups"]
                         if g["id"] == "knockouts")
        assert (knockouts["outcome"], knockouts["failed"]) == ("fail", 1)

    def test_the_count_is_the_hosts_and_the_bar_comes_from_the_setting(
            self, example):
        """Two of three, with one core test failing. The heading's rollup is
        counted by the host from the rows it resolved — nothing in the bundle
        tallies it — and the bar is read out of the declared setting."""
        r = verdict(example, known={**CLEARS, "current_ratio": 0.4},
                    moat=True)
        assert r["state"]["id"] == "worth-buying"
        core = next(g for g in r["reason"]["groups"] if g["id"] == "core")
        assert (core["passed"], core["failed"], core["tested"]) == (2, 1, 3)
        assert core["test"]["threshold"] == 2
        assert core["outcome"] == "pass"

    def test_a_journal_that_moves_the_bar_moves_the_verdict(self, example):
        r = verdict(example, known={**CLEARS, "current_ratio": 0.4},
                    moat=True, **{"core-tests-required": 3})
        assert r["state"]["id"] == "not-good-enough"
        assert r["reason"]["rule"] == "core-tests-short"

    def test_an_unreadable_knockout_is_not_a_failed_one_and_not_a_pass(
            self, example):
        """The quietest bug on the list: absence walking through a gate by
        failing to trip it. Nothing is bought and nothing is refused."""
        known = {k: v for k, v in CLEARS.items() if k != "roic_median_5y"}
        r = verdict(example, known=known, moat=True)
        assert r["state"]["id"] == "cannot-say"
        assert r["render"] == "unknown"

    def test_a_buy_cites_every_row_the_reader_needs_to_check_it(
            self, example):
        r = verdict(example, known=CLEARS, moat=True)
        assert r["state"]["id"] == "worth-buying"
        assert r["payload"]["size"] == {"unit": "weight", "value": 10.0}
        cited = {e["subject"]["id"] for e in r["reason"]["evidence"]}
        assert cited == set(MEASURES) | {"moat_durability"}
        # Every group it declared came out passed, which is the only reason
        # the host let a commit through at all.
        assert {g["outcome"] for g in r["reason"]["groups"]} == {"pass"}


class TestTheQuestionOnlyYouCanAnswer:
    def test_unanswered_blocks_and_says_where_the_answer_is_given(
            self, example):
        r = verdict(example, known=CLEARS)
        assert r["state"]["id"] == "assessment-owed"
        assert r["render"] == "blocked"
        assert r["state"]["fix"] == "judgement"
        # The way out is the citation, not the prose. Both are here, and it
        # is the citation the host refuses the verdict without.
        cited = [e for e in r["reason"]["evidence"]
                 if e["subject"]["kind"] == "judgement"]
        assert [e["subject"]["id"] for e in cited] == ["moat_durability"]
        assert cited[0]["outcome"] == "unknown"
        assert r["payload"]["needs"]

    def test_it_is_a_judgement_because_the_bank_says_so(self, example):
        """The bundle cites the moat exactly as it cites a computed measure.
        That it renders as an assessment rather than as something the tool
        worked out is the host's decision, from the bank — a strategy that
        could choose would be a strategy that could disguise one."""
        r = verdict(example, known=CLEARS)
        moat = next(e for e in r["reason"]["evidence"]
                    if e["subject"]["id"] == "moat_durability")
        assert moat["subject"]["kind"] == "judgement"

    def test_a_no_is_a_hold_and_not_a_failure_of_the_numbers(self, example):
        r = verdict(example, known=CLEARS, moat=False)
        assert r["state"]["id"] == "you-marked-it-down"
        assert r["render"] == "hold"

    def test_the_question_is_not_asked_of_a_company_already_refused(
            self, example):
        """Nobody should be assessing the durability of a business their own
        rules have already rejected, and not citing it is what keeps the
        question off the page."""
        r = verdict(example, known={**CLEARS, "roic_median_5y": 1.0})
        assert r["state"]["id"] == "not-good-enough"
        assert not [e for e in r["reason"]["evidence"]
                    if e["subject"]["id"] == "moat_durability"]


class TestTheConfirmedExit:
    def test_one_bad_filing_does_not_sell_anything(self, example):
        r = verdict(example, held=True, weight=8.0,
                    known={**CLEARS, "interest_coverage": 2.0},
                    series={"interest_coverage": falling(9.0, 9.0, 8.0, 2.0)})
        assert r["state"]["id"] == "breach-unconfirmed"
        assert r["render"] == "hold"

    def test_two_in_a_row_do(self, example):
        r = verdict(example, held=True, weight=8.0,
                    known={**CLEARS, "interest_coverage": 2.0},
                    series={"interest_coverage": falling(9.0, 9.0, 3.0, 2.0)})
        assert r["state"]["id"] == "exit-confirmed"
        assert r["render"] == "close"
        assert r["payload"]["when"] == "2026-08-09"
        # The confirming readings are cited by their period end, so a reader
        # can check the run against the filings instead of taking it on trust.
        confirming = sorted(e["subject"]["at"] for e in r["reason"]["evidence"]
                            if e["subject"].get("at"))
        assert confirming == ["2025-12-31", "2026-03-31"]

    def test_a_gap_neither_confirms_nor_forgives(self, example):
        """A filing whose reading could not be worked out must not confirm a
        breach nobody observed, and must not grant a reprieve either."""
        r = verdict(example, held=True, weight=8.0,
                    known={**CLEARS, "interest_coverage": 2.0},
                    series={"interest_coverage": falling(9.0, 3.0, None, 2.0)})
        assert r["state"]["id"] == "exit-confirmed"

    def test_the_journal_decides_how_many_filings_confirm(self, example):
        r = verdict(example, held=True, weight=8.0,
                    known={**CLEARS, "interest_coverage": 2.0},
                    series={"interest_coverage": falling(9.0, 9.0, 8.0, 2.0)},
                    **{"exit-confirmation-filings": 1})
        assert r["state"]["id"] == "exit-confirmed"

    def test_a_healthy_holding_renders_as_passes_and_not_as_failures(
            self, example):
        """The exit is cited as what the holding must KEEP BEING TRUE. Cite
        it in the direction it fires and this same holding renders a page of
        red rows beside a verdict of hold."""
        r = verdict(example, held=True, weight=8.0, known=CLEARS)
        assert r["state"]["id"] == "nothing-to-do"
        exit_row = next(e for e in r["reason"]["evidence"]
                        if e["subject"]["id"] == "interest_coverage")
        assert exit_row["outcome"] == "pass"

    def test_an_unreadable_exit_never_sells_and_never_says_it_is_clear(
            self, example):
        held = {k: v for k, v in CLEARS.items() if k != "interest_coverage"}
        r = verdict(example, held=True, weight=8.0, known=held)
        assert r["state"]["id"] == "cannot-say"

    def test_a_hand_entered_journal_can_never_confirm_this_exit(
            self, example):
        """The consequence the bundle warns about, pinned. A typed figure
        answers `current` and adds no filing point, so the run is always
        nought and this exit cannot fire however bad the number is."""
        r = verdict(example, held=True, weight=8.0,
                    known={**CLEARS, "interest_coverage": 0.1}, series={})
        assert r["state"]["id"] == "breach-unconfirmed"


class TestEveryStateIsReachable:
    def test_all_eight(self, example):
        """A declared state nothing reaches is vocabulary on the Strategy tab
        that never appears in a verdict, which is worse than not declaring
        it — the reader is told the tool can say something it cannot."""
        breached = {"interest_coverage": 2.0}
        cases = [
            {"known": CLEARS, "moat": True},
            {"known": {**CLEARS, "total_debt_to_ebitda": 6.0}},
            {"known": CLEARS},
            {"known": CLEARS, "moat": False},
            {"known": {k: v for k, v in CLEARS.items()
                       if k != "roic_median_5y"}},
            {"held": True, "weight": 8.0, "known": CLEARS},
            {"held": True, "weight": 8.0, "known": {**CLEARS, **breached},
             "series": {"interest_coverage": falling(9.0, 9.0, 8.0, 2.0)}},
            {"held": True, "weight": 8.0, "known": {**CLEARS, **breached},
             "series": {"interest_coverage": falling(9.0, 9.0, 3.0, 2.0)}},
        ]
        reached = {verdict(example, **c)["state"]["id"] for c in cases}
        assert reached == {s["id"] for s in example["states"]}


class TestThroughTheRealContext:
    """One pass through the machinery the app actually uses, so the
    hand-built contexts above cannot drift from the shape a journal serves."""

    def test_it_decides_against_a_context_built_from_stored_filings(
            self, example):
        end, start = "2023-12-31", "2023-01-01"
        facts_store.save_filing(1234, filing(
            "E-1", "10-K", "2024-02-20", end,
            [dur("us-gaap:Revenues", start, end, 1000),
             dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                 start, end, 200, stmt="CashFlowStatement"),
             dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                 start, end, 50, stmt="CashFlowStatement")]
            + balance_face(end, assets=800)))
        sec = {"ticker": "WDGE", "name": "Wedgemoor Fasteners", "cik": 1234,
               "lots": []}
        ctx = context.build_context(sec, [sec], values_for(example), {},
                                    record=example)
        result = contract.evaluate(example, ctx)
        assert result["produced_by"] == "strategy"
        # Most of the screen is uncomputable from three facts, so the honest
        # answer is that it cannot be settled — never a zero and never a buy.
        assert result["state"]["id"] in ("cannot-say", "not-good-enough")

    def test_an_answered_question_reaches_it_as_the_users_own(self, example):
        sec = {"ticker": "WDGE", "name": "Wedgemoor Fasteners", "cik": None,
               "lots": []}
        judgements.assess(sec, "moat_durability", "pass",
                          "Two decades of price rises nobody left over.")
        ctx = context.build_context(sec, [sec], values_for(example), {},
                                    record=example)
        moat = ctx["measures"]["moat_durability"]["current"]
        assert (moat["status"], moat["value"]) == ("known", True)
        assert moat["source"] == "judgement"
