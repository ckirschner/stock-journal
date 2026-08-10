"""Graham putting more money into a name it already holds.

Until v4 this could not happen: `_on_a_holding` returned only exits, a trim
and a hold, so `buy` was unreachable the moment you owned any of it. The tool
could record a first purchase and a re-purchase after an exit, and refused to
record the one thing in between.

What is pinned here is what would be wrong *plausibly*, because an add is the
decision this program is most likely to get wrong in a way nobody notices:

- **the entry tests are re-run, unchanged.** An add is the same claim about
  the same business made again. A softer bar for a name you already own is
  how a position gets averaged into something you would not buy today, and
  the screen would look identical either way.
- **the slot count does not block it.** A slot is a name and an add does not
  take a new one. Citing the slot test here would refuse every add in a full
  portfolio — a wrong answer that reads entirely sensibly.
- **the two baselines are separately load-bearing.** Deterioration measures
  from the last purchase, cumulative drift from the first, and the case that
  distinguishes them is three small declines that each pass against the
  purchase before them and fail in total. That is the boiling frog, it is the
  reason both anchors exist, and a position bought once cannot see it.
- **absence never buys.** A baseline nobody could recover has not shown that
  nothing changed.
- **an exit always outranks an add.** The ladder is the one thing standing
  between "the balance sheet is coming apart" and "there is room, buy more".

Nothing here can reach cost basis, and no test below needs to: the host does
not offer it, so a rule that added because the price had fallen below what
you paid cannot be written at all.
"""

import pytest

from test_strategy_graham import (CLEARS_ENTRY, CLEARS_EXITS, QUARTERS,
                                  build, graham, outcomes, verdict)  # noqa: F401

# A holding that clears everything: it would still be bought today, it has
# not moved since either purchase, and it sits well under its target.
SCREENS = {**CLEARS_ENTRY, **CLEARS_EXITS}
HELD = {"held": True, "opened": "2025-09-01"}
ROOMY = {"known": SCREENS, "weight": 2.0, **HELD}

# Graham ships twenty slots and a ten per cent cap, so the target weight of
# any one name is an equal share of the places: 100 / 20 = 5%.
TARGET = 5.0


def rule(result):
    return result["reason"]["rule"]


class TestAHoldingWithRoomMayTakeMore:
    def test_it_says_add_and_the_state_commits(self, graham):
        result = verdict(graham, **ROOMY)
        assert result["state"]["id"] == "add"
        assert result["render"] == "commit"

    def test_the_size_is_the_room_left_and_not_the_whole_target(self, graham):
        """The single most consequential number here. `size` means how much
        goes in, so on a position already at 2% of a 5% target the answer is
        3% — not 5%, which would take it to 7% and past its own cap on the
        second purchase, with the screen reading exactly the same."""
        result = verdict(graham, **ROOMY)
        assert result["payload"]["size"] == {"unit": "weight",
                                             "value": TARGET - 2.0}

    def test_it_goes_in_now_and_stages_nothing(self, graham):
        """Graham has no staged entry and should not: buying a statistical
        discount in thirds is a rule it does not have, and inventing one so a
        screen has something to render would put a recommendation into
        shipped content."""
        result = verdict(graham, **ROOMY)
        assert result["payload"]["condition"] is None
        assert result["payload"]["plan"] is None

    def test_the_host_never_refuses_a_shipped_add(self, graham):
        """A commit standing beside a group the host resolved as anything but
        passed is refused as `host:invalid-decision` — which renders as
        "Strategy failed" and is the right answer to a strategy contradicting
        itself. It must never be the answer to a legitimate add."""
        result = verdict(graham, **ROOMY)
        assert result["produced_by"] == "strategy"
        for group in result["reason"]["groups"]:
            if group["requires"] != "noted":
                assert group["outcome"] == "pass", group

    def test_the_reason_names_the_rule_that_produced_it(self, graham):
        assert rule(verdict(graham, **ROOMY)) == "qualifies-and-has-room"


class TestAnAddIsTheEntryTestsUnchanged:
    """"Valuation and conviction are evaluated identically to a first
    purchase." A holding screened against a softer bar is the averaging-down
    machine wearing the tool's authority, and every screen looks the same."""

    def test_a_failed_knockout_stops_the_add(self, graham):
        result = verdict(graham, **{**ROOMY,
                                    "known": {**SCREENS, "price_to_book": 2.9}})
        assert result["state"]["id"] == "hold"
        assert rule(result) == "would-not-buy-it-today"
        assert result["render"] != "commit"

    def test_too_few_core_tests_stops_the_add(self, graham):
        """Three core tests failing outright, on measures that are not also
        exits — so this is a screen that came back against it rather than an
        exit firing."""
        result = verdict(graham, **{**ROOMY, "known": {
            **SCREENS, "profitable_years_10y": 2, "eps_growth_10y": 5.0,
            "consecutive_dividend_years": 0}})
        assert result["state"]["id"] == "hold"
        assert rule(result) == "would-not-buy-it-today"

    def test_an_unreadable_test_is_not_reported_as_a_failed_one(self, graham):
        """The bug this test exists for, and it is the exact class the whole
        evidence arrangement is built to refuse.

        A holding whose market cap cannot be worked out is not a holding that
        failed the screen — it is one whose screen did not finish. Collapsed
        into the failure branch it came back "your rules would not buy this
        today: 0 of the 5 tests this strategy will not bend came back against
        it, and 8 of 8 core tests passed against a bar of 6" — a verdict
        stating the figures that contradict it, beside rows showing the
        measure as unknown. The candidate path has always split these two;
        this one did not.
        """
        result = verdict(graham, **{**ROOMY, "known": {
            k: v for k, v in SCREENS.items() if k != "market_cap"}})
        assert result["state"]["id"] == "hold"
        assert rule(result) == "screen-unreadable"
        assert outcomes(result)["market_cap"] == "unknown"

    def test_no_refusal_ever_states_figures_that_contradict_it(self, graham):
        """The general form. Whatever the rule, a summary claiming a count of
        failures must not appear over a screen where nothing failed — and a
        reader must never have to reconcile the sentence with the rows."""
        for dropped in ("market_cap", "price_to_book", "pe_3y_avg_eps",
                        "current_ratio"):
            result = verdict(graham, **{**ROOMY, "known": {
                k: v for k, v in SCREENS.items() if k != dropped}})
            summary = result["reason"]["summary"]
            failures = sum(1 for e in result["reason"]["evidence"]
                           if e["outcome"] == "fail")
            if failures == 0:
                assert "came back against it" not in summary, dropped

    def test_the_entry_evidence_is_actually_on_the_screen(self, graham):
        """A verdict has to say what it rested on. An add that cited only the
        exits would be claiming the entry tests were re-run while showing
        none of them."""
        seen = outcomes(verdict(graham, **ROOMY))
        for measure in ("price_to_book", "market_cap", "altman_z_score"):
            assert measure in seen

    def test_a_holding_that_only_clears_the_exits_does_not_add(self, graham):
        """The exits are a much lower bar than the entry tests — that is the
        whole design, a discount you own is not sold the moment it stops
        being a bargain. A holding sitting between the two must hold, not
        add."""
        result = verdict(graham, known=CLEARS_EXITS, weight=2.0, **HELD)
        assert result["state"]["id"] == "hold"
        # Unreadable rather than failed: the entry measures the exits do not
        # cover are simply not on record here, and an absent test is neither.
        assert rule(result) == "screen-unreadable"


class TestTheSlotCountIsAboutNamesNotMoney:
    """A slot is a name. An add does not take a new one, and citing the slot
    test on an add would refuse every add in a full portfolio — which is a
    wrong answer that reads perfectly sensibly, and would look to the user
    like the discipline working."""

    def test_a_full_portfolio_still_adds_to_what_it_holds(self, graham):
        result = verdict(graham, occupied=20, **ROOMY)
        assert result["state"]["id"] == "add"

    def test_the_slot_test_is_not_cited_on_an_add(self, graham):
        """Not merely passed — absent. Cited, it would fail on a full
        portfolio and the host would refuse the commit."""
        assert "portfolio.slots_occupied" not in outcomes(verdict(graham,
                                                                  **ROOMY))

    def test_a_candidate_is_still_refused_when_the_places_are_taken(self,
                                                                   graham):
        """The other half of the same rule. Room for a NEW name is exactly
        what the slot count is for, and loosening the add must not have
        loosened that."""
        result = verdict(graham, known=CLEARS_ENTRY, occupied=20)
        assert result["state"]["id"] == "no-room"


class TestRoomIsTheNewGate:
    """Invisible on a first purchase and binding most of the time
    afterwards."""

    def test_a_position_at_its_target_holds(self, graham):
        result = verdict(graham, **{**ROOMY, "weight": TARGET})
        assert result["state"]["id"] == "hold"
        assert rule(result) == "no-room-to-add"

    def test_a_position_past_its_target_but_under_the_cap_holds(self, graham):
        """Between the 5% target and the 10% cap nothing is wrong — the
        position is not too big, there is simply nowhere for more to go."""
        result = verdict(graham, **{**ROOMY, "weight": 7.0})
        assert result["state"]["id"] == "hold"
        assert rule(result) == "no-room-to-add"

    def test_a_position_over_the_cap_is_trimmed_and_not_merely_held(self,
                                                                   graham):
        result = verdict(graham, **{**ROOMY, "weight": 18.2})
        assert result["state"]["id"] == "too-big"
        assert result["render"] == "reduce"

    def test_a_weight_nobody_could_work_out_never_adds(self, graham):
        """Free cash is optional, and without it there is no account to
        measure a share of. Every figure the add depends on comes off that
        weight, so an absent one is the whole question unanswerable — and it
        must say so rather than reading as "your rules want nothing more"."""
        result = verdict(graham, known=SCREENS, **HELD)
        assert result["state"]["id"] == "hold"
        assert rule(result) == "size-unreadable"


class TestTheTwoBaselinesDoDifferentWork:
    """The part the brief said was most likely to be got wrong, and it is:
    both anchors use the same five tolerances, and only the anchor differs.
    A position bought once cannot tell them apart."""

    def test_drift_since_the_first_purchase_demands_a_re_underwrite(self,
                                                                   graham):
        result = verdict(graham, bought={"first": {**SCREENS,
                                                   "current_ratio": 3.6}},
                         **ROOMY)
        assert result["state"]["id"] == "re-underwrite-owed"
        assert result["render"] == "blocked"
        assert rule(result) == "drifted-since-first-purchase"

    def test_a_re_underwrite_demand_sells_nothing(self, graham):
        """It is a bar on adding, not a verdict on holding. Every exit test
        came back clear, and a state that closed the position here would be
        the tool inventing an exit its own rules do not have."""
        result = verdict(graham, bought={"first": {**SCREENS,
                                                   "current_ratio": 3.6}},
                         **ROOMY)
        assert result["render"] not in ("close", "reduce")
        assert result["payload"]["needs"]
        assert any("Nothing is being sold" in n
                   for n in result["payload"]["needs"])

    def test_deterioration_since_the_last_purchase_stops_the_add(self, graham):
        result = verdict(graham, bought={"last": {**SCREENS,
                                                  "current_ratio": 3.6}},
                         **ROOMY)
        assert result["state"]["id"] == "hold"
        assert rule(result) == "worse-since-you-last-bought"

    def test_the_boiling_frog(self, graham):
        """Three small declines. Each is inside the tolerance against the
        purchase before it; the total is not. Anchored only to the last
        purchase this position adds happily forever, and every individual
        quarter looks fine — which is exactly how the failure works.

        Current ratio 3.5 at the first purchase, 2.7 at the last, 2.4 now.
        Against the last purchase that is a fall of 0.3, inside the 0.4
        tolerance. Against the first it is 1.1, well outside it.
        """
        result = verdict(
            graham,
            bought={"first": {**SCREENS, "current_ratio": 3.5},
                    "last": {**SCREENS, "current_ratio": 2.7}},
            purchases=3, **{**ROOMY, "known": {**SCREENS,
                                               "current_ratio": 2.4}})
        assert result["state"]["id"] == "re-underwrite-owed"

    def test_the_anchor_that_fired_is_the_one_cited_as_failed(self, graham):
        """The rows have to agree with the verdict. A re-underwrite whose
        drift row read as passing would be the two halves of one decision
        disagreeing in public."""
        result = verdict(
            graham,
            bought={"first": {**SCREENS, "current_ratio": 3.5},
                    "last": {**SCREENS, "current_ratio": 2.7}},
            **{**ROOMY, "known": {**SCREENS, "current_ratio": 2.4}})
        rows = {(e["subject"].get("since"), e["subject"]["id"]): e["outcome"]
                for e in result["reason"]["evidence"]
                if e["subject"]["kind"] == "change"}
        assert rows[("first-purchase", "current_ratio")] == "fail"
        assert rows[("last-purchase", "current_ratio")] == "pass"

    def test_a_single_purchase_makes_the_two_anchors_agree(self, graham):
        """Not a special case to collapse — the honest answer. On a position
        bought once they are the same purchase, and the day they part company
        is the day of the second."""
        result = verdict(graham, bought={"first": {**SCREENS,
                                                   "current_ratio": 3.6},
                                         "last": {**SCREENS,
                                                  "current_ratio": 3.6}},
                         **ROOMY)
        rows = {e["subject"].get("since"): e["outcome"]
                for e in result["reason"]["evidence"]
                if e["subject"]["kind"] == "change"
                and e["subject"]["id"] == "current_ratio"}
        assert rows["first-purchase"] == rows["last-purchase"] == "fail"

    def test_a_rise_is_watched_as_well_as_a_fall(self, graham):
        """Two of the five tolerances are signed the other way — debt
        climbing is the bad direction. A drift table that only ever caught
        falls would miss half of what it is for."""
        result = verdict(graham, bought={"first": {**SCREENS,
                                                   "debt_to_equity": 0.05}},
                         **ROOMY)
        assert result["state"]["id"] == "re-underwrite-owed"


class TestAbsenceNeverBuys:
    def test_an_unrecoverable_baseline_stops_the_add(self, graham):
        """A comparison nobody could make has not shown that nothing
        changed. This is the absence-is-not-a-pass rule at the one place it
        decides whether more money goes in."""
        result = verdict(graham,
                         bought={"first": {k: v for k, v in SCREENS.items()
                                           if k != "current_ratio"}},
                         **ROOMY)
        assert result["state"]["id"] == "hold"
        assert rule(result) == "drift-unreadable"

    def test_it_is_not_a_re_underwrite_demand_either(self, graham):
        """Two different things. "It has drifted too far" is a finding about
        the business; "we could not tell" is a gap in the data, and sending
        someone to re-read filings over a missing number teaches them the
        wrong lesson about their own rules."""
        result = verdict(graham,
                         bought={"first": {k: v for k, v in SCREENS.items()
                                           if k != "current_ratio"}},
                         **ROOMY)
        assert result["state"]["id"] != "re-underwrite-owed"

    def test_a_holding_with_no_frozen_record_at_all_never_adds(self, graham):
        result = verdict(graham, bought={"first": {}, "last": {}}, **ROOMY)
        assert result["state"]["id"] == "hold"
        assert rule(result) == "drift-unreadable"


class TestTheLadderStillHolds:
    """An add sits at the bottom of it. Everything that would take money out
    is asked first, and the one thing that must never happen is a position
    coming apart while the screen offers more of it."""

    def test_a_confirmed_safety_breach_closes_rather_than_adds(self, graham):
        result = verdict(
            graham,
            known={**SCREENS, "current_ratio": 1.1},
            series={"current_ratio": [(QUARTERS[3], 1.15),
                                      (QUARTERS[4], 1.1)]},
            weight=2.0, **HELD)
        assert result["state"]["id"] == "safety-gone"
        assert result["render"] == "close"

    def test_a_closed_discount_closes_rather_than_adds(self, graham):
        result = verdict(
            graham,
            known={**SCREENS, "price_to_book": 3.4},
            series={"price_to_book": [(QUARTERS[3], 3.1),
                                      (QUARTERS[4], 3.4)]},
            weight=2.0, **HELD)
        assert result["state"]["id"] == "discount-closed"

    def test_an_elapsed_clock_outranks_an_add(self, graham):
        """A holding whose two years are up is due to be sold. Adding to it
        because it still screens would be the strategy arguing with its own
        exit on the day it fires."""
        result = verdict(graham, known=SCREENS, weight=2.0,
                         held=True, opened="2024-01-01")
        assert result["state"]["id"] == "time-is-up"

    def test_an_unconfirmed_breach_waits_rather_than_adding(self, graham):
        """One reading past a line is not an exit and it is not an
        invitation. Nothing is owed from the user — and nothing more goes in
        while a line is crossed and unresolved."""
        result = verdict(graham, known={**SCREENS, "price_to_book": 3.4},
                         series={"price_to_book": [(QUARTERS[4], 3.4)]},
                         weight=2.0, **HELD)
        assert result["state"]["id"] == "one-reading-past"


class TestNothingHereKnowsWhatYouPaid:
    """The guarantee the whole feature was built against. It is structural —
    cost basis is not in the context — so this checks the structure rather
    than the behaviour, which is the only version worth having."""

    def test_no_evidence_row_cites_anything_about_cost(self, graham):
        result = verdict(graham, **ROOMY)
        cited = {e["subject"].get("id") for e in result["reason"]["evidence"]}
        assert not any("cost" in str(c) or "basis" in str(c) for c in cited)

    @pytest.mark.parametrize("banned", ["cost", "basis", "paid", "price"])
    def test_the_position_an_add_is_decided_from_offers_no_cost_key(
            self, graham, banned):
        """Read off the context rather than off a verdict. A rule that
        cannot be written today stays unwritable only because the figure is
        never handed over — checking that no verdict happened to use it would
        pin the behaviour and leave the door open."""
        position = build(graham, **ROOMY)["position"]
        assert not any(banned in key for key in position)

    def test_the_frozen_baselines_carry_no_cost_either(self, graham):
        """The new surface, and the one worth re-checking. A baseline hands
        over what a purchase froze, and a purchase's own record DOES know
        what it cost — so the conversion has to drop it, and dropping it is
        what keeps averaging down unwritable."""
        for anchor in build(graham, **ROOMY)["position"]["baselines"].values():
            for key in anchor:
                assert "price" not in key and "cost" not in key


class TestThroughTheRealMachinery:
    """One pass with nothing hand-built between the strategy and the stores.

    Everything above drives graham against a context this test file writes,
    which is the right way to put fifteen measures at chosen values without
    testing the compute layer. What it cannot check is that the context the
    *host* builds has the same shape — and this feature added three keys to
    it, so producer and consumer would otherwise be tested in separate
    worlds that agree only because one person wrote both.

    The cost-basis guard in particular is worth nothing hand-built: the
    purchase record genuinely knows what it cost, so the guarantee is that
    the conversion into a context drops it. Asserting that against a
    dictionary this file wrote would prove only that this file did not add
    a cost key.
    """

    @staticmethod
    def _held(tmp_path):
        from conftest import entered, journal_for
        from engine import context, portfolio, dataview, price_store
        _journal, record = journal_for("graham", inputs={"free-cash": 50_000.0})
        security = portfolio.new_security("ARBR", "Arbor Mills")
        security["price"] = 20.0
        entered(security, **SCREENS)
        values = dataview.merged_values(security, {})
        portfolio.add_lot(
            security, None, shares=100.0, price=17.0, opened="2026-01-05",
            values=values,
            price_seen={"value": 17.0, "source": "manual", "date": None,
                        "ticker": "ARBR"})
        return security, record, context

    def test_the_context_the_host_builds_carries_the_baselines(self, tmp_path):
        security, record, context = self._held(tmp_path)
        ctx = context.build_context(security, [security],
                                    _values(record), {"free-cash": 50_000.0},
                                    record=record)
        pos = ctx["position"]
        assert pos["purchases"] == 1
        assert pos["last_purchase"] == "2026-01-05"
        assert pos["opened"] == "2026-01-05"
        for anchor in ("first-purchase", "last-purchase"):
            base = pos["baselines"][anchor]
            assert base["status"] == "known", base
            assert base["date"] == "2026-01-05"
            # Every figure the purchase froze, from the record — not a
            # recomputation, and not the empty dict a shape mismatch would
            # quietly produce.
            assert base["measures"]["current_ratio"]["value"] == \
                SCREENS["current_ratio"]

    def test_nothing_about_cost_survives_into_that_context(self, tmp_path):
        """The lot knows it was bought at $17. The context must not, anywhere
        — including inside the baselines, which are built from the very
        record that holds the price."""
        security, record, context = self._held(tmp_path)
        ctx = context.build_context(security, [security],
                                    _values(record), {"free-cash": 50_000.0},
                                    record=record)
        assert any(l["price"] == 17.0 for l in security["lots"])
        blob = repr(ctx)
        assert "17.0" not in blob.replace("117.0", "")
        for node in (ctx["position"], *ctx["position"]["baselines"].values()):
            for key in node:
                assert "price" not in key and "cost" not in key

    def test_the_real_context_produces_the_same_verdict_shape(self, tmp_path):
        """The add path, end to end, against a context nothing in this file
        wrote. A key renamed on the host side would leave every test above
        green and this one red, which is the whole reason it exists."""
        from engine import contract
        security, record, context = self._held(tmp_path)
        ctx = context.build_context(security, [security],
                                    _values(record), {"free-cash": 50_000.0},
                                    record=record)
        result = contract.evaluate(record, ctx)
        assert result["produced_by"] == "strategy", result["reason"]["summary"]
        # 100 shares at $20 in a $52,000 account is 3.85%, under the 5%
        # target, so there is room and every drift comparison reads zero.
        assert result["state"]["id"] == "add"
        assert result["payload"]["size"]["unit"] == "weight"
        changes = [e for e in result["reason"]["evidence"]
                   if e["subject"]["kind"] == "change"]
        assert len(changes) == 10
        assert {e["outcome"] for e in changes} == {"pass"}


def _values(record):
    from engine import strategy_values
    chain = strategy_values.resolve(record, [])
    assert chain["errors"] == [], chain["errors"]
    return chain["values"]
