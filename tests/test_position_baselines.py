"""The two purchases a rule about a holding can measure back to.

`position.baselines` is what makes "has this got worse since you said yes"
answerable at all, and every way it can go wrong is quiet. A baseline read
off today's filings instead of off the frozen snapshot answers a different
question — what the accounts say *now* about that day — and a restatement
then moves the thing the user is being measured against, with the same
plausible-looking number on screen either way. An anchor that reached back
past a full exit would measure a holding opened last month against a
business the user underwrote in 2024 and sold. An anchor that skipped a lot
sold down to nothing would forget a day somebody looked at this business and
said yes. None of those crash; all of them produce a confident wrong verdict.

`purchases_in_holding` is the one reader underneath all of it, so it is
pinned here too rather than only through what the context makes of it — and
`disposals_in_holding` beside it, because the two are one period read twice
and a boundary that held for the buys and not for the sells would be the
quietest version of this failure there is.
"""

import pytest
from conftest import balance_face, dur, filing

from engine import context, dataview, facts_store, portfolio

STRATEGY = {"id": "fixture", "name": "Fixture", "version": 2,
            "values_version": 3, "contract": 2}

FIRST = "first-purchase"
LAST = "last-purchase"


def qual(value, source="computed", cautions=None, provenance=None):
    """A value in the shape a snapshot may freeze. Built through the one
    constructor, because a bare float is refused at the write and these
    tests should break the way a real caller would."""
    return dataview.qualified(value, source, cautions, provenance)


def decision(render="commit", state="a-state"):
    """A decision already taken, in the contract's envelope. Nothing here
    evaluates — the baselines are a fact about the lot list."""
    tier = "evaluation" if render in ("blocked", "unknown") else "position"
    default = {"commit": {"size": {"unit": "weight", "value": 5.0},
                          "condition": None},
               "reduce": {"to": {"unit": "weight", "value": 2.0}},
               "close": {"when": "2026-08-08"}}.get(render, {})
    return {"render": render, "tier": tier,
            "state": {"id": state, "name": state.replace("-", " ").title(),
                      "description": "d", "fix": None},
            "payload": default,
            "reason": {"rule": "a-rule", "summary": "because.",
                       "evidence": [], "note": None},
            "produced_by": "strategy", "strategy": dict(STRATEGY)}


def security(ticker="ARBR", name="Arbor Mills", cik=None):
    s = portfolio.new_security(ticker, name)
    if cik:
        s["cik"] = cik
    return s


def buy(s, when, shares=10, price=40.0, values=None):
    return portfolio.add_lot(s, decision("commit"), shares, price, when,
                             values=values)


def sell(s, when, shares, price=90.0, render="close", against=None):
    return portfolio.sell_lots(s, decision(render), "A stated reason",
                               shares, price, when, against=against)


def build(s, as_of=None):
    return context.build_context(s, [s], {}, {}, as_of=as_of)


def anchors(s, as_of=None):
    return build(s, as_of)["position"]["baselines"]


def reading(anchor, entry_id):
    """One measure off one anchor, insisting the anchor was readable at all.
    An absent anchor and an anchor missing that one measure are different
    facts and must not be confused by a `.get` chain here."""
    assert anchor["status"] == "known", anchor.get("reason")
    return anchor["measures"][entry_id]


# -- the restatement fixture -------------------------------------------------
# One invented filer with a cash-flow face, so the frozen figure comes off
# stored filings through the same compute the app uses rather than off a
# number typed into the test.

CIK = 1234567


def file_capex(capex):
    """Store this filer's only 10-K with the stated capital expenditure.
    Writing it again under the same accession is a restatement: the source
    filing is immutable, what the journal holds about it is not."""
    end, start, filed = "2024-12-31", "2024-01-01", "2025-02-20"
    f = filing("S-1", "10-K", filed, end, [
        dur("us-gaap:Revenues", start, end, 1000),
        dur("us-gaap:NetCashProvidedByUsedInOperatingActivities", start, end,
            200, stmt="CashFlowStatement"),
        dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", start, end,
            capex, stmt="CashFlowStatement"),
        dur("us-gaap:NetIncomeLoss", start, end, 120),
    ] + balance_face(end, assets=800))
    f["cik"] = CIK
    facts_store.save_filing(CIK, f)
    dataview.invalidate()


def computed_now(s):
    """What the journal would freeze onto a purchase made today — the merged
    qualified values, off the same reader `open_position` uses."""
    computed = dataview.computed_results(CIK, [s["ticker"]], ["fcf_ttm"])
    return dataview.merged_values(s, computed)


class TestABaselineIsWhatWasFrozenAndIsNeverRecomputed:
    """Principle 3, at the one place it is most tempting to break. The
    baseline is the whole reason a snapshot is written, and reading it off
    live data instead would look right in every test that never restates."""

    def test_a_restatement_after_the_purchase_cannot_move_the_baseline(self):
        """The important one. A company reissues its accounts; the live
        measure moves, as it should. If the baseline moved with it, a rule
        asking "is this worse than when you bought" would be silently
        answering "is this worse than the accounts now say it was when you
        bought" — and a bad enough restatement would fire an exit on a
        business that had not changed at all since the user said yes.

        Nothing about this fails loudly. Both numbers are real, both are
        plausible, and the wrong one is only wrong because of when it was
        worked out.
        """
        file_capex(50)                       # cash flow 200 - capex 50
        s = security(cik=CIK)
        buy(s, "2025-03-01", values=computed_now(s))
        assert build(s)["measures"]["fcf_ttm"]["current"]["value"] == 150.0
        assert reading(anchors(s)[FIRST], "fcf_ttm")["value"] == 150.0

        file_capex(120)                      # the accounts are reissued

        after = build(s)
        # the live figure moves — without this the test proves nothing, since
        # a baseline that never moves and a number that never moves look the
        # same from here
        assert after["measures"]["fcf_ttm"]["current"]["value"] == 80.0
        for anchor in (FIRST, LAST):
            assert reading(after["position"]["baselines"][anchor],
                           "fcf_ttm")["value"] == 150.0

    def test_the_frozen_figure_keeps_what_qualified_it(self):
        """A caution is the half that goes missing at every hop, and this is
        a hop. A baseline arriving without the caution that was on the figure
        states it as more certain than the evidence supported — and it is the
        number a re-underwrite is measured against, which nothing downstream
        can afterwards correct."""
        s = security()
        buy(s, "2025-03-01", values={"market_cap": qual(
            2.4e12, cautions=["Class B — 7.1% of the share count — has no "
                              "stored close"],
            provenance=["shares outstanding from the FY2024 cover"])})
        frozen = reading(anchors(s)[FIRST], "market_cap")
        assert frozen["value"] == 2.4e12
        assert "7.1% of the share count" in frozen["cautions"][0]
        assert frozen["provenance"] == ["shares outstanding from the FY2024 "
                                        "cover"]

    def test_a_purchase_that_froze_nothing_is_known_with_no_measures(self):
        """A gap in the data. The purchase is on record and its day is
        readable; the journal simply held no figure for anything that day.
        The anchor has to say that — a measure nobody can read must come out
        of a rule as unknown, and an anchor reported as absent would send the
        reader looking for a missing purchase instead."""
        s = security()
        buy(s, "2025-03-01")                  # no values behind it
        anchor = anchors(s)[FIRST]
        assert anchor["status"] == "known"
        assert anchor["date"] == "2025-03-01"
        assert anchor["measures"] == {}

    def test_a_purchase_with_no_frozen_record_is_absent_and_says_which(self):
        """A gap in the journal, and a different fix from the one above. A
        lot written before this journal froze anything has nothing to measure
        against at all, and the reason names the day and what that purchase
        is — otherwise "no reading of this" arrives thirty times over with
        nothing saying the record itself is missing."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        s["lots"][0]["snapshot"] = None       # as an older journal holds it
        anchor = anchors(s)[FIRST]
        assert anchor["status"] == "absent"
        assert "2025-03-01" in anchor["reason"]
        assert "took this holding up from nothing" in anchor["reason"]
        assert "value" not in anchor

    def test_a_measure_the_record_never_held_is_simply_not_there(self):
        """Never a nought. A figure that was not on record at the purchase is
        absent from the anchor, so a rule citing it resolves to unknown; a
        zero would read as the most catastrophic possible reading of that
        measure and fire whatever guards against it."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        measures = reading(anchors(s)[FIRST], "fcf_ttm"), \
            anchors(s)[FIRST]["measures"]
        assert measures[0]["value"] == 150.0
        assert "current_ratio" not in measures[1]


class TestTheTwoAnchorsAreOnePurchaseUntilYouBuyAgain:
    def test_one_purchase_puts_both_anchors_on_the_same_lot(self):
        """Not a special case to collapse. Both questions have an answer and
        it is the same answer, and a host that served only one of them would
        make a strategy citing the other absent for no reason the user could
        act on."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        first, last = anchors(s)[FIRST], anchors(s)[LAST]
        assert first["lot"] == last["lot"] == "l1"
        assert first["date"] == last["date"] == "2025-03-01"
        assert reading(first, "fcf_ttm")["value"] == 150.0
        assert reading(last, "fcf_ttm")["value"] == 150.0

    def test_a_second_purchase_parts_them(self):
        """The day they part company is the day the second purchase is
        recorded, and it is the whole reason both exist: a drift rule reading
        the last purchase can never see six quarters of small declines, and a
        deterioration rule reading the first fires on a position the user
        consciously re-underwrote last quarter. Serving one where the other
        was asked for is silent — both are real figures off real purchases.
        """
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        buy(s, "2026-01-15", values={"fcf_ttm": qual(90.0)})
        first, last = anchors(s)[FIRST], anchors(s)[LAST]
        assert (first["lot"], first["date"]) == ("l1", "2025-03-01")
        assert (last["lot"], last["date"]) == ("l2", "2026-01-15")
        assert reading(first, "fcf_ttm")["value"] == 150.0
        assert reading(last, "fcf_ttm")["value"] == 90.0

    def test_the_middle_purchase_is_neither_anchor(self):
        """Oldest and newest, never an average and never whichever happened
        to be walked to last. A middle purchase answering "when you last
        bought" would be wrong by however long ago it was."""
        s = security()
        for when, v in (("2025-03-01", 150.0), ("2025-09-01", 120.0),
                        ("2026-01-15", 90.0)):
            buy(s, when, values={"fcf_ttm": qual(v)})
        assert reading(anchors(s)[FIRST], "fcf_ttm")["value"] == 150.0
        assert reading(anchors(s)[LAST], "fcf_ttm")["value"] == 90.0


class TestAnAnchorBelongsToTheHoldingYouHaveNow:
    def test_buying_back_after_a_full_exit_moves_both_anchors(self):
        """The holding you have now began at the re-entry. An anchor that
        reached past the exit would measure a position opened in June against
        a business underwritten in March and sold in April — and a
        deterioration rule reading it would exit a holding the user had just
        re-underwritten, citing evidence about a position nobody owns."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        sell(s, "2025-04-01", 10)
        buy(s, "2025-06-01", values={"fcf_ttm": qual(60.0)})
        first, last = anchors(s)[FIRST], anchors(s)[LAST]
        assert first["lot"] == last["lot"] == "l3"
        assert first["date"] == last["date"] == "2025-06-01"
        assert reading(first, "fcf_ttm")["value"] == 60.0
        # and the purchase before the exit is gone from the count entirely
        assert build(s)["position"]["purchases"] == 1

    def test_a_trim_does_not_start_a_new_holding_or_move_an_anchor(self):
        """A trim is not an exit. The position has been held continuously,
        so the first anchor is still the day it opened — the two only agree
        until somebody sells part of a position, which is the case worth
        pinning."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        buy(s, "2025-09-01", values={"fcf_ttm": qual(120.0)})
        sell(s, "2026-01-05", 5, render="reduce")
        assert anchors(s)[FIRST]["date"] == "2025-03-01"
        assert anchors(s)[LAST]["date"] == "2025-09-01"
        assert build(s)["position"]["purchases"] == 2

    def test_a_lot_sold_down_to_nothing_is_still_a_purchase(self):
        """It was still a day somebody looked at this business and said yes,
        and the holding it built is still the one being held. Anchoring on
        surviving shares instead would make the first anchor jump forward the
        moment an old lot was trimmed away — a rule measuring "since you
        first bought" would quietly start measuring from later, and get
        easier to pass every time the user sold."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        buy(s, "2025-09-01", values={"fcf_ttm": qual(120.0)})
        sell(s, "2026-01-05", 10, render="reduce",
             against=[{"lot": "l1", "shares": 10}])
        assert portfolio.shares_held(s) == 10.0
        assert [l["id"] for l in portfolio.open_lots(s) if l["open"]] == ["l2"]

        first = anchors(s)[FIRST]
        assert first["lot"] == "l1"                       # nothing left of it
        assert reading(first, "fcf_ttm")["value"] == 150.0
        assert build(s)["position"]["purchases"] == 2


class TestTheClockGovernsWhichPurchasesExist:
    def test_a_purchase_made_after_the_pin_has_not_happened_yet(self):
        """A reconstruction sees the world of its day. A later purchase
        leaking into a pinned evaluation would make a decision explain itself
        with evidence measured from a day the user had not yet reached — and
        the reconstruction is exactly what an as-of purchase freezes, so the
        wrong reading would be written into the record permanently."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        buy(s, "2026-01-15", values={"fcf_ttm": qual(90.0)})

        pinned = build(s, as_of="2025-06-01")["position"]
        assert pinned["purchases"] == 1
        assert pinned["last_purchase"] == "2025-03-01"
        assert pinned["baselines"][LAST]["lot"] == "l1"
        assert reading(pinned["baselines"][LAST], "fcf_ttm")["value"] == 150.0

        live = build(s)["position"]
        assert live["purchases"] == 2
        assert live["last_purchase"] == "2026-01-15"

    def test_a_pin_before_the_first_purchase_holds_nothing(self):
        """Not "no purchases" — nothing was held that day, so there is no
        holding for an anchor to belong to, and the reason has to say that
        rather than leave a rule to read an empty answer as a clean one."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        pinned = build(s, as_of="2025-01-01")["position"]
        assert pinned["purchases"] == 0
        assert pinned["last_purchase"] is None
        for anchor in (FIRST, LAST):
            node = pinned["baselines"][anchor]
            assert node["status"] == "absent"
            assert "no position is held" in node["reason"]


class TestHoldingNothingIsAbsenceAndNeverAZero:
    def test_a_security_with_no_lots_has_both_anchors_absent(self):
        """An idea nobody owns. Both anchors absent with the reason, so a
        rule citing a change since a purchase resolves to unknown — an empty
        set of measures would come out of a comparison as a pass, and absence
        is never a pass."""
        s = security()
        node = build(s)["position"]
        assert node["held"] is False
        for anchor in (FIRST, LAST):
            assert node["baselines"][anchor] == {
                "status": "absent",
                "reason": "no position is held, so there is no purchase to "
                          "measure from"}

    def test_a_closed_out_holding_has_no_last_purchase_and_no_count(self):
        """Never today's date and never a nought that looks like an answer.
        A previous holding has purchases on record and none of them built
        anything the user owns, so "when did you last buy" has no answer at
        all — a rule reading a stale date would happily measure drift since a
        purchase that was sold out of last year."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        sell(s, "2025-04-01", 10)
        node = build(s)["position"]
        assert node["last_purchase"] is None
        assert node["purchases"] == 0
        assert node["baselines"][FIRST]["status"] == "absent"
        assert len(portfolio.lots(s, "buy")) == 1     # the purchase is still
        assert portfolio.bucket_of(s) == "previous"   # on record

    def test_the_count_and_the_date_agree_with_the_anchors(self):
        """Three readings of one lot list. They are separate keys because a
        rule must not silently read one where it asked for another, and
        separate keys are exactly what can drift apart."""
        s = security()
        for when in ("2025-03-01", "2025-09-01", "2026-01-15"):
            buy(s, when, values={"fcf_ttm": qual(1.0)})
        node = build(s)["position"]
        assert node["purchases"] == 3
        assert node["last_purchase"] == node["baselines"][LAST]["date"]
        assert node["opened"] == node["baselines"][FIRST]["date"]


class TestPurchasesInHolding:
    """The reader underneath all of the above. Pinned directly, because the
    boundary it draws — this holding's buys, not this security's — is the
    one thing every anchor and every count inherits."""

    def test_it_returns_the_open_periods_buys_oldest_first(self):
        s = security()
        buy(s, "2025-09-01")
        buy(s, "2025-03-01")            # recorded later, dated earlier
        assert [l["date"] for l in portfolio.purchases_in_holding(s)] == \
            ["2025-03-01", "2025-09-01"]

    def test_nothing_held_is_empty_and_not_the_securitys_history(self):
        """Empty because there is no period, which is a different sentence
        from "this name was never bought" — and the caller that turns this
        into an anchor has to be able to tell them apart. It cannot if a
        closed-out holding's purchases keep coming back."""
        s = security()
        assert portfolio.purchases_in_holding(s) == []
        buy(s, "2025-03-01")
        sell(s, "2025-04-01", 10)
        assert portfolio.purchases_in_holding(s) == []
        assert len(portfolio.lots(s, "buy")) == 1

    def test_it_stops_at_the_clock(self):
        s = security()
        buy(s, "2025-03-01")
        buy(s, "2026-01-15")
        assert [l["date"] for l in
                portfolio.purchases_in_holding(s, "2025-06-01")] == \
            ["2025-03-01"]
        assert portfolio.purchases_in_holding(s, "2025-01-01") == []

    def test_it_keeps_a_lot_that_was_trimmed_to_nothing(self):
        s = security()
        buy(s, "2025-03-01")
        buy(s, "2025-09-01")
        sell(s, "2026-01-05", 10, render="reduce",
             against=[{"lot": "l1", "shares": 10}])
        assert [l["id"] for l in portfolio.purchases_in_holding(s)] == \
            ["l1", "l2"]

    def test_its_first_entry_and_opened_on_are_one_value(self):
        """Two answers to "when did this holding begin" is one answer too
        many, and they would agree in every ordinary case — which is what
        makes a disagreement on the re-entry case so quiet."""
        s = security()
        buy(s, "2025-03-01")
        sell(s, "2025-04-01", 10)
        buy(s, "2025-06-01")
        assert portfolio.purchases_in_holding(s)[0]["date"] == \
            portfolio.opened_on(s)
        assert portfolio.opened_on(s) == "2025-06-01"

    def test_a_sale_is_never_one_of_them(self):
        s = security()
        buy(s, "2025-03-01")
        sell(s, "2025-04-01", 4, render="reduce")
        assert {l["kind"] for l in portfolio.purchases_in_holding(s)} == \
            {"buy"}


class TestDisposalsInHolding:
    """The other half of the same reader, and the pairing is the point: what
    this holding has bought and what it has sold come off one period, so the
    two cannot answer at different scopes."""

    def test_it_returns_the_open_periods_sells_oldest_first(self):
        s = security()
        buy(s, "2025-03-01", shares=30)
        sell(s, "2025-09-01", 5, render="reduce")
        sell(s, "2025-06-01", 4, render="reduce")   # recorded later, earlier
        assert [(l["date"], l["shares"]) for l in
                portfolio.disposals_in_holding(s)] == \
            [("2025-06-01", 4.0), ("2025-09-01", 5.0)]

    def test_a_sale_from_a_holding_that_ended_is_not_one_of_them(self):
        """The scope this exists to draw. The 2025 exit ended a holding; the
        one in progress now was opened by a later purchase and has sold
        nothing. Both sales are still on the security's record."""
        s = security()
        buy(s, "2025-03-01")
        sell(s, "2025-04-01", 10)
        buy(s, "2025-06-01")
        assert portfolio.disposals_in_holding(s) == []
        assert len(portfolio.lots(s, "sell")) == 1

    def test_nothing_held_is_empty_because_there_is_no_holding(self):
        s = security()
        assert portfolio.disposals_in_holding(s) == []
        buy(s, "2025-03-01")
        sell(s, "2025-04-01", 10)
        assert portfolio.disposals_in_holding(s) == []

    def test_it_stops_at_the_clock(self):
        s = security()
        buy(s, "2025-03-01", shares=30)
        sell(s, "2025-06-01", 4, render="reduce")
        sell(s, "2026-01-15", 5, render="reduce")
        assert [l["date"] for l in
                portfolio.disposals_in_holding(s, "2025-09-01")] == \
            ["2025-06-01"]
        assert portfolio.disposals_in_holding(s, "2025-05-01") == []

    def test_it_reads_the_same_period_the_purchases_do(self):
        """One period, two projections of it. Two readers walking the lot list
        for themselves would agree until a same-day exit-and-re-entry, which
        is exactly the case the boundary exists for."""
        s = security()
        buy(s, "2025-03-01")
        sell(s, "2025-06-01", 10)
        buy(s, "2025-06-01")
        period = portfolio.open_cycle(s)
        assert portfolio.purchases_in_holding(s) == list(period["buys"])
        assert portfolio.disposals_in_holding(s) == list(period["sells"])

    def test_a_purchase_is_never_one_of_them(self):
        s = security()
        buy(s, "2025-03-01", shares=30)
        sell(s, "2025-04-01", 4, render="reduce")
        assert {l["kind"] for l in portfolio.disposals_in_holding(s)} == \
            {"sell"}


class TestTheContextCannotBeMutatedThroughABaseline:
    def test_a_strategy_editing_a_baseline_cannot_reach_the_journal(self):
        """The context is deep-copied at the boundary, and a baseline is the
        one node built out of an append-only snapshot. A live reference here
        would let a strategy rewrite what was frozen at a purchase — the
        record that exists precisely because nothing may rewrite it."""
        s = security()
        buy(s, "2025-03-01", values={"fcf_ttm": qual(150.0)})
        ctx = build(s)
        ctx["position"]["baselines"][FIRST]["measures"]["fcf_ttm"]["value"] \
            = 9.0
        ctx["position"]["baselines"][FIRST]["measures"].pop("fcf_ttm")
        assert s["lots"][0]["snapshot"]["metrics"]["fcf_ttm"]["value"] == 150.0
        assert reading(anchors(s)[FIRST], "fcf_ttm")["value"] == 150.0


def test_a_bare_number_still_cannot_reach_a_baseline():
    """Structural, not procedural. The way a qualifier goes missing is a
    caller handing over a float, and a baseline is downstream of every such
    caller — so the refusal has to be at the write, where no future writer
    can get round it."""
    s = security()
    with pytest.raises(ValueError, match="bare float"):
        portfolio.add_lot(s, decision("commit"), 10, 40.0, "2025-03-01",
                          values={"fcf_ttm": 150.0})
    assert s["lots"] == []


# -- a definition that moved after the purchase ------------------------------
# The other way a baseline goes quietly wrong, and the one a restatement guard
# cannot catch. The frozen figure is exactly what was seen; today's figure is
# exactly what is seen now; and if the measure was redefined in between they
# are readings of two different things, so the distance between them is a
# distance in nothing. It reaches a rule as drift.

def journal_with(*changes):
    """A journal whose measure-change record holds these entries. Built as the
    record's own shape rather than by driving the bank, because what is under
    test is the join between a recorded change and a frozen reading, and a
    real bank edit would have to move a real formula to exercise one row."""
    return {"measure_changes": [
        {"seq": i + 1, "seen": seen, "kind": "definitions",
         "added": [], "removed": [], "moved": list(moved),
         "restated": list(restated), "changelog": [], "notes": [],
         "reason_owed": True, "reason": None}
        for i, (seen, moved, restated) in enumerate(changes)]}


def moved(field, was, now, eid="fcf_ttm"):
    return {"id": eid, "name": "Free cash flow", "field": field,
            "from": was, "to": now}


def restated(field, eid="fcf_ttm"):
    return {"id": eid, "name": "Free cash flow", "field": field,
            "digest": "0d0d0d0d0d0d"}


def anchored(s, journal, as_of=None):
    ctx = context.build_context(s, [s], {}, {}, as_of=as_of, journal=journal)
    return ctx["position"]["baselines"]


def frozen_at(s, day):
    """Stamp the purchase's snapshot, since what a definition change is placed
    against is when the figures were worked out and not the day traded — a
    backfilled purchase is dated years ago and was computed this morning."""
    s["lots"][0]["snapshot"]["frozen"] = day
    return s


class TestAFigureIsNotSubtractedFromADifferentMeasure:
    """The gate, and the reason it is a gate rather than a caution.

    What a baseline feeds is one subtraction — today's reading minus the
    frozen one — reported as how far the business has moved since you bought,
    with a rule firing on the answer. Where the measure was redefined in
    between, the answer is a five-year median taken from a three-year one.
    Principle 4 is explicit that a caution is read by a person and ignored by
    the arithmetic, so the number is withheld rather than qualified: the
    strategy is never handed the figure it would have subtracted.
    """

    def held(self, values=None):
        s = security()
        buy(s, "2024-03-01", values=values or {"fcf_ttm": qual(4.0)})
        return frozen_at(s, "2024-03-01T12:00:00-05:00")

    def test_a_window_that_narrowed_after_the_purchase_withholds_the_figure(
            self):
        """The case this exists for. Five annual observations becoming three
        is a different measure under the same name, and nothing about the
        subtraction looks wrong afterwards.

        Both anchors, because they are two purchases and not two views of
        one: a strategy asking how far a business has drifted since it was
        first bought and one asking whether it got worse since the last
        addition read different lots, and gating one of them would leave the
        other subtracting across the same redefinition.
        """
        s = security()
        buy(s, "2024-03-01", values={"fcf_ttm": qual(4.0)})
        buy(s, "2024-09-01", values={"fcf_ttm": qual(5.0)})
        for lot in s["lots"]:
            lot["snapshot"]["frozen"] = f'{lot["date"]}T12:00:00-05:00'
        j = journal_with(("2026-08-13T09:00:00-04:00",
                          [moved("observations read", 5, 3)], []))
        anchors_now = anchored(s, j)
        assert anchors_now[FIRST]["lot"] != anchors_now[LAST]["lot"]
        for anchor in (FIRST, LAST):
            got = reading(anchors_now[anchor], "fcf_ttm")
            assert got["status"] == "absent", anchor
            assert "value" not in got, anchor

    def test_the_absence_says_which_day_and_what_moved(self):
        """A drift figure that silently disappears teaches nothing. Somebody
        watching an exit stop firing has to be able to find out that the exit
        did not stop firing — the comparison did."""
        s = self.held()
        j = journal_with(("2026-08-13T09:00:00-04:00",
                          [moved("observations read", 5, 3)], []))
        why = reading(anchored(s, j)[FIRST], "fcf_ttm")["reason"]
        assert "2024-03-01" in why           # when it was worked out
        assert "2026-08-13" in why           # when the definition moved
        assert "observations read moved from 5 to 3" in why
        assert "would not be a distance in one measure" in why

    def test_a_changed_formula_withholds_it_too_without_quoting_itself(self):
        s = self.held()
        j = journal_with(("2026-08-13T09:00:00-04:00", [],
                          [restated("how it is worked out")]))
        why = reading(anchored(s, j)[FIRST], "fcf_ttm")["reason"]
        assert "how it is worked out changed" in why
        assert "0d0d0d" not in why           # a digest is not a sentence

    def test_a_move_that_leaves_the_readings_comparable_changes_nothing(self):
        """The narrowness is the point. A renamed measure, a corrected
        format, a reworded condition the formula refuses on — none of them
        makes two readings readings of different things, and gating on any
        bank change at all would take a working drift rule off a journal
        because somebody fixed a typo."""
        s = self.held()
        for field in ("name", "format", "favourable direction",
                      "does not describe", "judged against"):
            j = journal_with(("2026-08-13T09:00:00-04:00",
                              [moved(field, "a", "b")], []))
            got = reading(anchored(s, j)[FIRST], "fcf_ttm")
            assert got["status"] == "known", (field, got)
            assert got["value"] == 4.0
        for field in ("what the formula refuses on",
                      "what nothing here can settle"):
            j = journal_with(("2026-08-13T09:00:00-04:00", [],
                              [restated(field)]))
            assert reading(anchored(s, j)[FIRST],
                           "fcf_ttm")["status"] == "known", field

    def test_a_definition_that_moved_before_the_purchase_changes_nothing(self):
        """Both readings were taken under the definition standing then. The
        comparison is between them and not against history."""
        s = self.held()
        j = journal_with(("2023-01-04T09:00:00-05:00",
                          [moved("observations read", 5, 3)], []))
        assert reading(anchored(s, j)[FIRST], "fcf_ttm")["status"] == "known"

    def test_only_the_measure_that_moved_goes_quiet(self):
        s = security()
        buy(s, "2024-03-01", values={"fcf_ttm": qual(4.0),
                                     "pe_ttm": qual(11.0)})
        frozen_at(s, "2024-03-01T12:00:00-05:00")
        j = journal_with(("2026-08-13T09:00:00-04:00",
                          [moved("observations read", 5, 3)], []))
        anchor = anchored(s, j)[FIRST]
        assert reading(anchor, "fcf_ttm")["status"] == "absent"
        assert reading(anchor, "pe_ttm")["status"] == "known"

    def test_a_measure_that_went_and_came_back_is_not_the_same_measure(self):
        """No field ever moved across the gap, so nothing else would notice.
        A definition can be replaced whole between a removal and an addition,
        and the id is the only thing that survived."""
        s = self.held()
        j = {"measure_changes": [
            {"seq": 1, "seen": "2026-08-13T09:00:00-04:00",
             "removed": [{"id": "fcf_ttm", "name": "Free cash flow"}],
             "added": [], "moved": [], "restated": []},
            {"seq": 2, "seen": "2026-09-01T09:00:00-04:00",
             "removed": [], "moved": [], "restated": [],
             "added": [{"id": "fcf_ttm", "name": "Free cash flow",
                        "definition": {"states": {}, "restates": {}}}]}]}
        got = reading(anchored(s, j)[FIRST], "fcf_ttm")
        assert got["status"] == "absent"
        assert "the measure was removed" in got["reason"]
        assert "once more since" in got["reason"]

    def test_a_field_this_build_has_never_heard_of_counts(self):
        """Fails closed. A field added to a definition later, and not thought
        about here, takes a drift figure off the screen with a reason — which
        is noticed. The other default subtracts two different measures and is
        not."""
        s = self.held()
        j = journal_with(("2026-08-13T09:00:00-04:00",
                          [moved("some later idea", 1, 2)], []))
        assert reading(anchored(s, j)[FIRST], "fcf_ttm")["status"] == "absent"

    def test_a_purchase_with_no_stamp_is_never_placed_against_the_record(
            self):
        """A snapshot that cannot say when it was worked out cannot be told
        from one frozen this morning, and guessing is the failure being
        guarded against. It stays comparable rather than being gated on a
        guess — the record says what it says, and it does not say this."""
        s = self.held()
        s["lots"][0]["snapshot"].pop("frozen")
        j = journal_with(("2026-08-13T09:00:00-04:00",
                          [moved("observations read", 5, 3)], []))
        assert reading(anchored(s, j)[FIRST], "fcf_ttm")["status"] == "known"

    def test_no_journal_gates_nothing(self):
        """Every context built without one — the engine tests above, and any
        caller with no record to consult. There is no record saying a measure
        moved, so nothing here may claim one did."""
        s = self.held()
        assert reading(anchors(s)[FIRST], "fcf_ttm")["status"] == "known"


class TestTheGateReachesTheRuleAndNotJustTheContext:
    """The seam that matters: a strategy asks the host how far a measure has
    moved, and the host answers. Pinned end to end rather than on the context
    node alone, because what the context withholds only counts if the
    citation that reads it comes back unanswered rather than falling through
    to something."""

    def cited(self, journal):
        from engine import contract
        s = security()
        buy(s, "2024-03-01", values={"fcf_ttm": qual(4.0)})
        frozen_at(s, "2024-03-01T12:00:00-05:00")
        ctx = context.build_context(s, [s], {}, {}, journal=journal)
        # A reading now, so the only thing missing is the baseline.
        ctx["measures"]["fcf_ttm"]["current"] = {
            "status": "known", "value": 9.0, "source": "computed",
            "cautions": [], "provenance": []}
        item = {"measure": "fcf_ttm", "since": FIRST,
                "comparator": "at_least", "threshold": -1.0}
        rows, errors = contract.resolve_evidence(
            {"name": "Fixture", "values": []}, ctx, [item])
        assert errors == [], errors
        return contract.test(ctx, item), rows[0]

    def test_the_distance_is_answered_where_the_measure_did_not_move(self):
        from engine import contract
        outcome, row = self.cited(journal_with())
        assert row["observed"]["value"] == 5.0
        assert outcome == contract.PASS

    def test_the_distance_is_unknown_where_it_did(self):
        """Never a pass, never a zero, and never a number with a warning
        beside it. The rule cannot fire on a comparison that was not made."""
        from engine import contract
        outcome, row = self.cited(journal_with(
            ("2026-08-13T09:00:00-04:00",
             [moved("observations read", 5, 3)], [])))
        assert outcome == contract.UNKNOWN
        assert row["observed"]["status"] == "absent"
        assert "value" not in row["observed"]
        assert "what the measure means moved" in row["observed"]["reason"]
