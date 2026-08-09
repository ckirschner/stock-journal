"""Lot history, frozen snapshots and the override log.

The failures pinned here are all silent ones. A snapshot that keeps a
reference instead of a copy quietly rewrites itself when the strategy is
retuned. A sale that edited the lot it drew from would rewrite what was
bought. An override recorded against the wrong kind — went ahead in the face
of a verdict, versus went ahead where there was no verdict — makes a data gap
read as defiance, and the analytics that are supposed to indict the rules
start indicting the user instead. A close whose strategy was not installed
recorded as "no rule fired" claims a signal was read when none could be.

Nothing in here evaluates. The decision arrives already taken, in the
contract's envelope, and this module records it — so these tests build
decisions by hand rather than through a strategy.
"""

import copy
from datetime import date, timedelta

import pytest

from engine import dataview, portfolio

STRATEGY = {"id": "fixture", "name": "Fixture", "version": 2,
            "values_version": 3, "contract": 2}


def qual(value, source="computed", cautions=None, provenance=None):
    """A value in the shape a snapshot may freeze — built through the one
    constructor, so these tests break the same way callers would."""
    return dataview.qualified(value, source, cautions, provenance)


def decision(render, state="a-state", evidence=(), payload=None,
             rule="a-rule", summary="because."):
    tier = "evaluation" if render in ("blocked", "unknown") else "position"
    default = {"commit": {"size": {"unit": "weight", "value": 5.0},
                          "condition": None},
               "reduce": {"to": {"unit": "weight", "value": 2.0}},
               "close": {"when": "2026-08-08"},
               "blocked": {"needs": ["Tell it something."]}}.get(render, {})
    return {"render": render, "tier": tier,
            "state": {"id": state, "name": state.replace("-", " ").title(),
                      "description": "d", "fix": None},
            "payload": payload if payload is not None else default,
            "reason": {"rule": rule, "summary": summary,
                       "evidence": list(evidence), "note": None},
            "produced_by": "host" if tier == "evaluation" else "strategy",
            "strategy": dict(STRATEGY)}


def cite(label, outcome, kind="measure", mid="pe_ttm", threshold_from=None):
    item = {"subject": {"kind": kind, "id": mid, "label": label,
                        "unit": "times", "explain": None},
            "observed": ({"status": "known", "value": 12.0,
                          "source": kind, "cautions": [], "provenance": []}
                         if outcome != "unknown"
                         else {"status": "absent", "reason": "not stored",
                               "source": kind}),
            "test": {"comparator": "at_most", "phrase": "at most",
                     "threshold": 15.0,
                     "threshold_from": threshold_from},
            "outcome": outcome}
    return item


def held(ticker="ACME"):
    return portfolio.new_security(ticker, "Acme Widgets")


def bought(ticker="ACME", shares=10, price=40.0, when="2026-01-01",
           render="commit"):
    s = held(ticker)
    portfolio.add_lot(s, decision(render), shares, price, when)
    return s


def closing_sale(s):
    """The sale that ended the most recent completed holding, read off the
    period it closed — the same reader the app uses.

    There used to be a `last_exit` that returned the most recent sale of any
    kind, and these tests reached for it because they wanted "the exit". A
    trim is a sale too, so the two part company exactly when it matters."""
    closed = [c for c in portfolio.cycles(s) if not c["open"]]
    return closed[-1]["sells"][-1]


class TestFrozenSnapshot:
    def test_the_whole_decision_is_frozen_with_its_stamp(self):
        s = held()
        d = decision("commit", evidence=[cite("Price / earnings", "pass")])
        lot = portfolio.add_lot(s, d, 10, 40.0, "2026-08-01",
                                values={"pe_ttm": qual(12.0)},
                                price_seen={"value": 41.0,
                                            "source": "fetched",
                                            "date": "2026-07-31"})
        snap = lot["snapshot"]
        assert snap["strategy"] == STRATEGY
        # every part of the record of what was seen, not a pointer to it
        assert snap["decision"]["state"]["id"] == "a-state"
        assert snap["decision"]["reason"]["rule"] == "a-rule"
        assert snap["decision"]["reason"]["evidence"][0]["outcome"] == "pass"
        assert snap["decision"]["payload"]["size"]["value"] == 5.0
        assert snap["price"] == 41.0
        assert snap["price_source"] == "fetched"
        assert snap["price_date"] == "2026-07-31"

    def test_the_record_is_isolated_from_the_caller_that_wrote_it(self):
        """A snapshot holding a live reference would rewrite itself the next
        time anything upstream is touched — the exact failure the freeze
        exists to prevent, and one with no visible symptom."""
        s = held()
        d = decision("commit", evidence=[cite("Price / earnings", "pass")])
        values = {"pe_ttm": qual(12.0, cautions=["a live caution"])}
        evaluation = {"basis": "live", "as_of": "2026-08-01",
                      "manual_on_record": ["pe_ttm"]}
        lot = portfolio.add_lot(s, d, 10, 40.0, "2026-08-01", values=values,
                                evaluation=evaluation)
        d["state"]["id"] = "tampered"
        d["reason"]["evidence"][0]["outcome"] = "fail"
        values["pe_ttm"]["value"] = 99.0
        values["pe_ttm"]["cautions"].append("added afterwards")
        evaluation["manual_on_record"].append("tampered")
        snap = lot["snapshot"]
        assert snap["decision"]["state"]["id"] == "a-state"
        assert snap["decision"]["reason"]["evidence"][0]["outcome"] == "pass"
        assert snap["metrics"]["pe_ttm"]["value"] == 12.0
        assert snap["metrics"]["pe_ttm"]["cautions"] == ["a live caution"]
        assert snap["evaluation"]["manual_on_record"] == ["pe_ttm"]

    def test_a_frozen_value_keeps_what_qualified_it(self):
        """The serious half of the caution work. A snapshot is written once
        and never recomputed, so a figure that arrives without its caution
        states itself as more certain than the evidence supported — forever,
        with nothing downstream able to tell."""
        s = held()
        lot = portfolio.add_lot(
            s, decision("commit"), 10, 40.0, "2026-08-01",
            values={"market_cap": qual(
                2.4e12, source="computed",
                cautions=["Class B (860,000,000 shares) — 7.1% of the share "
                          "count — has no stored close"],
                provenance=["shares outstanding from the FY2024 cover"])})
        frozen = lot["snapshot"]["metrics"]["market_cap"]
        assert frozen["value"] == 2.4e12
        assert "7.1% of the share count" in frozen["cautions"][0]
        assert frozen["provenance"] == ["shares outstanding from the FY2024 "
                                        "cover"]
        assert frozen["source"] == "computed"

    def test_a_bare_number_cannot_be_frozen_at_all(self):
        """Structural, not procedural. The way a caution went missing was a
        caller handing over a float, so a float is refused at the write —
        every writer, including one nobody has written yet."""
        s = held()
        with pytest.raises(ValueError) as e:
            portfolio.add_lot(s, decision("commit"), 10, 40.0, "2026-08-01",
                              values={"pe_ttm": 12.0})
        assert "bare float" in str(e.value)
        assert "qualified" in str(e.value)
        # and the refusal happens before anything is appended
        assert s["lots"] == []

    def test_without_an_evaluation_the_default_is_live_as_of_today(self):
        """The engine never asserts a past evaluation it was not told about:
        a caller that passes no basis gets the honest description of what
        actually happened — evaluated live, today."""
        s = held()
        lot = portfolio.add_lot(s, decision("hold"), 10, 40.0, "2025-01-05",
                                override_reason="x")
        assert lot["snapshot"]["evaluation"]["basis"] == "live"
        assert lot["snapshot"]["evaluation"]["as_of"] == \
            date.today().isoformat()

    def test_a_sale_never_touches_the_lot_it_drew_from(self):
        """The one thing that makes append-only more than a word: what
        remains is derived on read, so nothing can rewrite what was bought."""
        s = bought()
        before = copy.deepcopy(s["lots"][0])
        portfolio.sell_lots(s, decision("close"), "Panic", 4, 60.0,
                            "2026-08-08")
        assert s["lots"][0] == before
        assert portfolio.open_lots(s)[0]["remaining"] == 6.0


class TestLotsAreTheposition:
    def test_several_buys_accumulate_and_average_their_cost(self):
        s = bought(shares=10, price=40.0, when="2026-01-01")
        portfolio.add_lot(s, decision("commit"), 30, 20.0, "2026-03-01")
        assert portfolio.shares_held(s) == 40.0
        # 10 at 40 and 30 at 20 is 1000 over 40 shares
        assert portfolio.cost_basis(s) == 25.0
        assert portfolio.opened_on(s) == "2026-01-01"

    def test_a_partial_sale_leaves_the_rest_open_and_priced_as_bought(self):
        s = bought(shares=10, price=40.0, when="2026-01-01")
        portfolio.add_lot(s, decision("commit"), 10, 60.0, "2026-03-01")
        portfolio.sell_lots(s, decision("reduce"), "Risk limit", 10, 100.0,
                            "2026-06-01")
        assert portfolio.shares_held(s) == 10.0
        # oldest first: the 40.0 lot is gone, the 60.0 lot is what remains
        assert portfolio.cost_basis(s) == 60.0
        assert portfolio.bucket_of(s) == "holdings"

    def test_trimming_the_oldest_lot_does_not_restart_the_holding(self):
        """`opened_on` answers when this holding began, and a trim does not
        begin one. The position has been held continuously since January; the
        January *lot* being sold down to nothing is a fact about a lot, and
        the lot list is where that lives.

        The two used to be one name. They agree until the day they matter,
        which is what made this worth pinning."""
        s = bought(shares=10, price=40.0, when="2026-01-01")
        portfolio.add_lot(s, decision("commit"), 10, 60.0, "2026-03-01")
        portfolio.sell_lots(s, decision("reduce"), "Risk limit", 10, 100.0,
                            "2026-06-01")
        assert portfolio.opened_on(s) == "2026-01-01"
        # the oldest share still held is newer, and says so on its own entry
        assert [l["date"] for l in portfolio.open_lots(s) if l["open"]] == \
            ["2026-03-01"]
        # …and it is one value with the period, not a second agreeing one
        assert portfolio.opened_on(s) == portfolio.open_cycle(s)["opened"]

    def test_a_sale_can_name_the_lots_it_drew_on(self):
        """Only the user knows what they told their broker. Oldest-first is
        a stated default, not the only answer the record can hold."""
        s = bought(shares=10, price=40.0, when="2026-01-01")
        portfolio.add_lot(s, decision("commit"), 10, 60.0, "2026-03-01")
        portfolio.sell_lots(s, decision("reduce"), "Risk limit", 10, 100.0,
                            "2026-06-01",
                            against=[{"lot": "l2", "shares": 10}])
        assert portfolio.cost_basis(s) == 40.0
        assert [l["id"] for l in portfolio.open_lots(s) if l["open"]] == ["l1"]

    def test_a_full_exit_leaves_the_lots_and_the_bucket_moves(self):
        s = bought(shares=10, price=40.0)
        portfolio.sell_lots(s, decision("close"), "Hit valuation", 10, 60.0,
                            "2026-08-08")
        assert portfolio.shares_held(s) == 0.0
        assert portfolio.bucket_of(s) == "previous"
        assert portfolio.cost_basis(s) is None
        assert portfolio.opened_on(s) is None
        assert len(portfolio.lots(s, "buy")) == 1     # nothing was deleted

    def test_re_entry_after_a_full_exit_reads_against_the_first(self):
        s = bought(shares=10, price=40.0, when="2026-01-01")
        portfolio.sell_lots(s, decision("close"), "Hit valuation", 10, 60.0,
                            "2026-03-01")
        portfolio.add_lot(s, decision("commit"), 5, 30.0, "2026-06-01")
        assert portfolio.bucket_of(s) == "holdings"
        assert portfolio.shares_held(s) == 5.0
        # the clock starts at the re-entry, not at a lot that no longer exists
        assert portfolio.opened_on(s) == "2026-06-01"
        assert len(portfolio.lots(s, "buy")) == 2
        assert len(portfolio.lots(s, "sell")) == 1

    def test_a_lot_id_is_never_reused_after_everything_closes(self):
        """A reused id would silently make an old sale draw on a new
        purchase, and every remaining-shares figure below it would be
        wrong with nothing on screen saying so."""
        s = bought(shares=10, price=40.0)
        portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0)
        portfolio.add_lot(s, decision("commit"), 5, 30.0, "2026-06-01")
        ids = [l["id"] for l in s["lots"]]
        assert len(set(ids)) == len(ids)

    def test_the_bucket_is_derived_and_never_stored(self):
        s = held()
        assert portfolio.bucket_of(s) == "ideas"
        assert "bucket" not in s
        portfolio.add_lot(s, decision("commit"), 1, 10.0)
        assert portfolio.bucket_of(s) == "holdings"
        assert "bucket" not in s

    def test_the_clock_governs_what_the_lots_say(self):
        """A purchase made after a pinned day did not exist then, and a sale
        made after it had not reduced anything."""
        s = bought(shares=10, price=40.0, when="2026-03-01")
        portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0,
                            "2026-06-01")
        assert portfolio.shares_held(s, "2026-01-01") == 0.0
        assert portfolio.shares_held(s, "2026-04-01") == 10.0
        assert portfolio.shares_held(s, "2026-07-01") == 0.0

    def test_selling_shares_that_were_never_bought_is_refused(self):
        """Not a gate on a decision — arithmetic. Recording a sale of shares
        the journal never saw would make every derived figure below it
        fiction, and the message names the fix."""
        s = bought(shares=10, price=40.0)
        with pytest.raises(ValueError, match="Record the purchase"):
            portfolio.sell_lots(s, decision("close"), "Panic", 25, 60.0)
        assert len(portfolio.lots(s, "sell")) == 0
        assert portfolio.shares_held(s) == 10.0

    def test_an_allocation_that_does_not_add_up_is_refused(self):
        s = bought(shares=10, price=40.0)
        with pytest.raises(ValueError, match="give up 4"):
            portfolio.sell_lots(s, decision("close"), "Panic", 6, 60.0,
                                against=[{"lot": "l1", "shares": 4}])

    def test_selling_from_a_lot_that_does_not_exist_is_refused(self):
        s = bought(shares=10, price=40.0)
        with pytest.raises(ValueError, match="not a recorded purchase"):
            portfolio.sell_lots(s, decision("close"), "Panic", 5, 60.0,
                                against=[{"lot": "l9", "shares": 5}])

    def test_a_backdated_sale_cannot_draw_on_a_later_purchase(self):
        """Two clocks: what a lot has left counts every sale ever recorded,
        so nothing can go negative; what a lot is eligible for stops at the
        sale's own date, so March cannot spend June's shares."""
        s = bought(shares=10, price=40.0, when="2026-01-01")
        portfolio.add_lot(s, decision("commit"), 10, 60.0, "2026-06-01")
        lot = portfolio.sell_lots(s, decision("close"), "Panic", 10, 90.0,
                                  "2026-03-01")
        assert lot["against"] == [{"lot": "l1", "shares": 10.0}]
        with pytest.raises(ValueError, match="had not been bought yet"):
            portfolio.sell_lots(s, decision("close"), "Panic", 5, 90.0,
                                "2026-02-01",
                                against=[{"lot": "l2", "shares": 5}])

    def test_a_backfilled_exit_cannot_spend_a_later_holding(self):
        """The bound that re-entry breaks apart. A journal holding a hundred
        shares bought back last year will accept a hundred-share exit
        backfilled into a period when ten were held unless the sale is
        checked against its own date — and every figure derived from that
        period is then fiction, with nothing on screen saying so."""
        s = bought(shares=10, price=40.0, when="2025-01-01")
        portfolio.add_lot(s, decision("commit"), 100, 50.0, "2026-01-01")
        with pytest.raises(ValueError, match="held 10 shares .* on 2025-06-01"):
            portfolio.sell_lots(s, decision("close"), "Panic", 50, 90.0,
                                "2025-06-01")
        # and the honest ten still records
        lot = portfolio.sell_lots(s, decision("close"), "Panic", 10, 90.0,
                                  "2025-06-01")
        assert lot["shares"] == 10.0

    def test_an_exit_says_it_closed_even_when_the_name_is_held_again(self):
        """Trimmed or closed is a fact about the holding the sale ended, so
        it is read on the sale's own clock. Asking what is held *now* calls a
        backfilled exit a trim because the user has since bought back — a
        sentence in the append-only record saying the position stayed open
        when it did not."""
        s = bought(shares=10, price=40.0, when="2025-01-01")
        portfolio.add_lot(s, decision("commit"), 100, 50.0, "2026-01-01")
        portfolio.sell_lots(s, decision("hold"), "Panic", 10, 90.0,
                            "2025-06-01")
        assert "Closed with no rule" in s["notes"][-1]["text"]
        assert portfolio.shares_held(s) == 100.0      # still held, after it

    def test_a_sale_backdated_into_a_closed_holding_says_so_in_dates(self):
        """Both named bounds can pass and still leave nothing to draw on: the
        shares held that day were spent by an exit recorded later. Re-entry is
        what puts a user in front of this, and the message has to be about
        dates — the allocation check underneath talks about lot ids nobody
        has seen."""
        s = bought(shares=10, price=10.0, when="2024-01-02")
        portfolio.sell_lots(s, decision("close"), "Hit valuation", 10, 20.0,
                            "2024-03-01")
        portfolio.add_lot(s, decision("commit"), 10, 40.0, "2024-06-01")
        with pytest.raises(ValueError,
                           match="On 2024-02-01 .* already sold"):
            portfolio.sell_lots(s, decision("close"), "Panic", 10, 15.0,
                                "2024-02-01")

    def test_a_backdated_sale_still_cannot_oversell_across_time(self):
        """Shares already sold in June are gone whatever a March entry
        says, or a lot goes negative and every figure below it is wrong."""
        s = bought(shares=10, price=40.0, when="2026-01-01")
        portfolio.sell_lots(s, decision("reduce"), "Risk limit", 6, 90.0,
                            "2026-06-01")
        with pytest.raises(ValueError, match="Record the purchase"):
            portfolio.sell_lots(s, decision("close"), "Panic", 10, 90.0,
                                "2026-03-01")
        assert portfolio.shares_held(s) == 4.0

    def test_a_sale_says_the_verdict_was_seen_live(self):
        s = bought()
        lot = portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0)
        assert lot["snapshot"]["evaluation"]["basis"] == "live"


class TestOverrides:
    def test_a_commit_is_not_an_override(self):
        s = held()
        lot = portfolio.add_lot(s, decision("commit"), 10, 40.0, "2026-08-01")
        assert lot["override"] is None
        assert portfolio.override_kind(decision("commit")) is None

    def test_going_ahead_against_a_verdict_is_recorded_as_against(self):
        s = held()
        d = decision("hold", evidence=[
            cite("Price / earnings", "fail",
                 threshold_from={"kind": "value", "id": "max-pe",
                                 "label": "Maximum P/E"})])
        lot = portfolio.add_lot(s, d, 10, 40.0, "2026-08-01",
                                override_reason="I disagree.")
        ov = lot["override"]
        assert ov["kind"] == "against"
        assert ov["failed"] == [{"key": "value:max-pe",
                                 "label": "Maximum P/E"}]
        assert ov["missing"] == []
        assert ov["reason"] == "I disagree."
        assert "against the signal" in s["notes"][-1]["text"]
        # never blocked: the position is recorded regardless
        assert portfolio.bucket_of(s) == "holdings"
        assert portfolio.shares_held(s) == 10

    def test_going_ahead_where_there_was_no_verdict_is_recorded_as_without(
            self):
        """A gap in the data is not defiance. Counting the two together would
        make the scorecard report that overriding works fine, because most of
        those were never decisions."""
        s = held()
        d = decision("unknown", evidence=[cite("Price / earnings", "unknown")])
        lot = portfolio.add_lot(s, d, 10, 40.0, "2026-08-01",
                                override_reason="No data, buying anyway.")
        ov = lot["override"]
        assert ov["kind"] == "without"
        assert ov["failed"] == []
        assert ov["missing"] == [{"key": "measure:pe_ttm",
                                  "label": "Price / earnings"}]
        assert "without a signal" in s["notes"][-1]["text"]

    def test_a_reduce_or_close_at_purchase_is_still_against(self):
        for render in ("reduce", "close"):
            s = held()
            lot = portfolio.add_lot(s, decision(render), 10, 40.0,
                                    "2026-08-01", override_reason="r")
            assert lot["override"]["kind"] == "against", render

    def test_an_absent_reason_is_named_rather_than_left_blank(self):
        s = held()
        lot = portfolio.add_lot(s, decision("hold"), 10, 40.0, "2026-08-01")
        assert lot["override"]["reason"] == "No reason given."

    def test_each_lot_carries_its_own_override(self):
        """One name can hold a compliant entry and an override beside it.
        Collapsing them into one flag per security would lose exactly the
        comparison the scorecard exists to make."""
        s = held()
        portfolio.add_lot(s, decision("commit"), 10, 40.0, "2026-01-01")
        portfolio.add_lot(s, decision("hold"), 10, 60.0, "2026-03-01",
                          override_reason="adding anyway")
        assert [bool(l["override"]) for l in portfolio.lots(s, "buy")] == \
            [False, True]

    def test_the_grouping_key_prefers_the_setting_a_threshold_came_from(self):
        """"Overriding your maximum P/E kept working out" is the finding worth
        surfacing; "overriding price / earnings" is not the same claim, and
        the two must not merge into one bucket."""
        from_setting = cite("Price / earnings", "fail",
                            threshold_from={"kind": "value", "id": "max-pe",
                                            "label": "Maximum P/E"})
        bare = cite("Price / earnings", "fail")
        assert portfolio._cite(from_setting)["key"] == "value:max-pe"
        assert portfolio._cite(bare)["key"] == "measure:pe_ttm"


class TestExits:
    def test_an_exit_the_strategy_called_for_is_marked_as_triggered(self):
        for render in ("close", "reduce"):
            s = bought(price=40.0)
            lot = portfolio.sell_lots(s, decision(render), "Thesis broke", 10,
                                      60.0, "2026-08-08")
            assert lot["rule_triggered"] is True, render
            assert portfolio.sale_return(s, lot) == 50.0

    def test_an_exit_nobody_called_for_says_so_on_the_record(self):
        s = bought()
        lot = portfolio.sell_lots(s, decision("hold"), "Panic", 10, 30.0,
                                  "2026-08-08")
        assert lot["rule_triggered"] is False
        assert lot["signal_at_exit"] == "A State"
        assert "no rule triggering" in s["notes"][-1]["text"]

    def test_a_missing_strategy_is_recorded_as_absence_not_as_clear(self):
        """"Nothing fired" and "nobody could be asked" are different facts.
        Recording the second as the first claims a signal was read."""
        s = bought()
        lot = portfolio.sell_lots(s, None, "Risk limit", 10, 30.0,
                                  "2026-08-08")
        assert lot["rule_triggered"] is None
        assert lot["signal_at_exit"] == "Strategy not installed"
        assert lot["strategy"] is None
        assert "not installed" in s["notes"][-1]["text"]
        # and the close still records — it is never blocked
        assert portfolio.bucket_of(s) == "previous"
        assert lot["price"] == 30.0

    def test_a_lot_bought_at_nothing_gives_an_absent_return_never_a_zero(self):
        s = held()
        portfolio.add_lot(s, decision("commit"), 1, 0.0, "2026-01-01")
        lot = portfolio.sell_lots(s, decision("close"), "Panic", 1, 30.0)
        assert portfolio.sale_return(s, lot) is None
        assert portfolio.position_return(s, 30.0) is None

    def test_the_exit_decision_is_frozen_too(self):
        s = bought()
        d = decision("close", state="get-out")
        lot = portfolio.sell_lots(s, d, "Thesis broke", 10, 60.0, "2026-08-08")
        d["state"]["id"] = "tampered"
        assert lot["snapshot"]["decision"]["state"]["id"] == "get-out"

    def test_a_trim_says_it_trimmed_rather_than_closed(self):
        s = bought(shares=10)
        portfolio.sell_lots(s, decision("hold"), "Risk limit", 4, 60.0)
        assert "Trimmed" in s["notes"][-1]["text"]
        assert portfolio.bucket_of(s) == "holdings"


class TestADatedEntryCannotBeInTheFuture:
    """One rule, at the write, for every kind of lot.

    The buy path refused a future date and the sale path did not, which is
    what a rule applied per caller looks like. A sale dated years ahead
    reports the position closed to every screen that asks while the strategy
    is still holding it — two states at once, which principle 7 forbids —
    and takes the whole holding out of the account total.

    Not a gate on judgement. Principle 2 protects decisions the user made,
    and a sale dated 2062 has not been made.
    """

    def _ahead(self, days=1):
        return (date.today() + timedelta(days=days)).isoformat()

    def test_a_sale_dated_ahead_is_refused(self):
        s = bought(shares=10)
        with pytest.raises(ValueError) as e:
            portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0,
                                self._ahead(13_000))
        assert "future" in str(e.value)
        assert "has not happened yet" in str(e.value)
        # nothing was appended, so the position is untouched
        assert portfolio.shares_held(s) == 10
        assert portfolio.bucket_of(s) == "holdings"

    def test_tomorrow_is_refused_as_firmly_as_2062(self):
        """A one-day slip is the ordinary typo, and it is the one that would
        pass a rule written to catch only absurd dates."""
        s = bought(shares=10)
        with pytest.raises(ValueError):
            portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0,
                                self._ahead(1))

    def test_a_purchase_dated_ahead_is_refused_at_the_write(self):
        """The screen checked this; the engine did not. A rule that lives
        only in the caller is one new caller away from being gone."""
        s = held()
        with pytest.raises(ValueError) as e:
            portfolio.add_lot(s, decision("commit"), 10, 40.0, self._ahead())
        assert "purchase" in str(e.value) and "future" in str(e.value)
        assert s["lots"] == []

    def test_today_is_allowed_on_both_paths(self):
        """The boundary is "has not happened", not "is not in the past".
        Refusing today would refuse every trade recorded the day it was
        made, which is most of them."""
        s = held()
        today = date.today().isoformat()
        portfolio.add_lot(s, decision("commit"), 10, 40.0, today)
        lot = portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0,
                                  today)
        assert lot["date"] == today

    def test_a_date_that_is_not_a_date_is_refused_by_name(self):
        s = bought(shares=10)
        for bad in ("not-a-date", "2026-13-01", "08/09/2026"):
            with pytest.raises(ValueError) as e:
                portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0,
                                    bad)
            assert "real date" in str(e.value), bad

    def test_no_date_still_means_today(self):
        s = bought(shares=10)
        lot = portfolio.sell_lots(s, decision("close"), "Panic", 10, 60.0)
        assert lot["date"] == date.today().isoformat()


class TestReturns:
    def test_a_lot_sold_in_two_pieces_reports_the_weighted_return(self):
        s = bought(shares=10, price=100.0, when="2026-01-01")
        portfolio.sell_lots(s, decision("reduce"), "Risk limit", 5, 150.0,
                            "2026-03-01")
        portfolio.sell_lots(s, decision("close"), "Panic", 5, 50.0,
                            "2026-06-01")
        # +50 on five shares and −50 on five is nothing at all
        assert portfolio.lot_return(s, portfolio.lots(s, "buy")[0], None) == 0.0

    def test_an_open_lot_with_no_price_has_no_return_never_zero(self):
        s = bought(shares=10, price=100.0)
        assert portfolio.lot_return(s, s["lots"][0], None) is None
        assert portfolio.position_return(s, None) is None
        assert portfolio.position_return(s, 120.0) == 20.0

    def test_a_half_sold_lot_marks_the_rest_at_the_price_given(self):
        s = bought(shares=10, price=100.0)
        portfolio.sell_lots(s, decision("reduce"), "Risk limit", 5, 200.0)
        # +100 realised on half, +20 unrealised on the other half
        assert portfolio.lot_return(s, s["lots"][0], 120.0) == 60.0

    def test_the_position_return_weights_lots_by_what_they_cost(self):
        s = bought(shares=1, price=100.0, when="2026-01-01")
        portfolio.add_lot(s, decision("commit"), 9, 100.0, "2026-03-01")
        assert portfolio.position_return(s, 110.0) == 10.0


def rebought(ticker="ACME"):
    """Bought, closed at a profit, bought back higher, and still held.

    Read straight off the numbers, not through the code under test:
      period 1  10 shares at $10 = $100 in, sold at $20 = $200 out  -> +100%
      exit $20 -> re-entry $40                                      -> +100%
      period 2  10 shares at $40 = $400 in, marked at $44           ->  +10%
      lifetime  $100 returning $100 and $400 returning $40          ->  +28%
    """
    s = bought(ticker=ticker, shares=10, price=10.0, when="2024-01-02")
    portfolio.sell_lots(s, decision("close"), "Hit valuation", 10, 20.0,
                        "2024-06-03")
    portfolio.add_lot(s, decision("commit"), 10, 40.0, "2025-01-06")
    return s


class TestHoldingPeriods:
    """A security is not held once. Everything that judges a round trip has
    to belong to one of them, and everything that spans them has to say so —
    a lifetime figure standing in a column about the position in front of you
    is the kind of wrong number nobody notices."""

    def test_a_re_entry_is_a_second_period_the_first_one_closed(self):
        c = portfolio.cycles(rebought())
        assert len(c) == 2
        assert (c[0]["opened"], c[0]["closed"], c[0]["open"]) == \
            ("2024-01-02", "2024-06-03", False)
        assert (c[1]["opened"], c[1]["closed"], c[1]["open"]) == \
            ("2025-01-06", None, True)
        assert c[0]["shares"] == 0.0 and c[1]["shares"] == 10.0
        assert [l["id"] for l in c[0]["buys"]] == ["l1"]
        assert [l["id"] for l in c[0]["sells"]] == ["l2"]
        assert [l["id"] for l in c[1]["buys"]] == ["l3"]

    def test_one_purchase_and_one_sale_is_still_exactly_one_period(self):
        s = bought(shares=10, price=40.0, when="2026-01-01")
        assert len(portfolio.cycles(s)) == 1
        portfolio.sell_lots(s, decision("reduce"), "Risk limit", 4, 60.0,
                            "2026-03-01")
        assert len(portfolio.cycles(s)) == 1     # a trim does not end one
        portfolio.sell_lots(s, decision("close"), "Panic", 6, 60.0,
                            "2026-06-01")
        c = portfolio.cycles(s)
        assert len(c) == 1 and c[0]["closed"] == "2026-06-01"

    def test_a_purchase_backdated_before_the_exit_never_was_two_periods(self):
        """The boundary is derived by walking the running total, not stored
        when the exit is recorded. A purchase entered later but dated earlier
        means the position never reached nothing — so it was one continuous
        holding all along, and no marker written at exit time could have
        known that."""
        s = bought(shares=10, price=10.0, when="2024-01-02")
        portfolio.sell_lots(s, decision("close"), "Hit valuation", 10, 20.0,
                            "2024-06-03")
        assert len(portfolio.cycles(s)) == 1
        portfolio.add_lot(s, decision("commit"), 5, 15.0, "2024-03-01")
        c = portfolio.cycles(s)
        assert len(c) == 1
        assert c[0]["open"] is True and c[0]["closed"] is None
        assert c[0]["shares"] == 5.0
        assert portfolio.shares_held(s) == 5.0

    def test_the_open_period_is_scored_without_the_one_that_closed(self):
        s = rebought()
        assert portfolio.cycle_return(s, portfolio.open_cycle(s), 44.0) == 10.0
        assert portfolio.cycle_return(s, portfolio.cycles(s)[0], 44.0) == 100.0
        # …and the lifetime figure still spans both, for the one place that
        # asks a question about the whole ticker
        assert portfolio.position_return(s, 44.0) == 28.0

    def test_a_closed_period_needs_no_price_to_be_scored(self):
        s = rebought()
        assert portfolio.cycle_return(s, portfolio.cycles(s)[0], None) == 100.0
        assert portfolio.cycle_return(s, portfolio.open_cycle(s), None) is None

    def test_one_unscoreable_lot_makes_the_whole_period_absent(self):
        """A period averaged over the lots that happened to work is a subset
        presented as the whole — a number that looks like an answer about the
        holding and is an answer about part of it. The lot bought at nothing
        has no return to give, so the period has none either."""
        s = bought(shares=10, price=10.0, when="2024-01-02")
        portfolio.add_lot(s, decision("commit"), 5, 0.0, "2024-02-02")
        c = portfolio.open_cycle(s)
        assert portfolio.lot_return(s, c["buys"][0], 20.0) == 100.0
        assert portfolio.lot_return(s, c["buys"][1], 20.0) is None
        assert portfolio.cycle_return(s, c, 20.0) is None
        assert portfolio.position_return(s, 20.0) is None

    def test_a_purchase_recorded_at_nothing_never_scores_the_window(self):
        """Free shares say nothing about what the market was doing, so they
        cannot close a since-exit window. Reading the lot price as a market
        price would put a confident −100% into the evidence that judges the
        sell rules."""
        s = bought(shares=10, price=10.0, when="2024-01-02")
        portfolio.sell_lots(s, decision("close"), "Hit valuation", 10, 20.0,
                            "2024-06-03")
        portfolio.add_lot(s, decision("commit"), 5, 0.0, "2024-09-01")
        x = portfolio.since_sale(s, closing_sale(s), 25.0)
        assert x["pct"] is None and "recorded at nothing" in x["reason"]
        card = portfolio.exit_scorecard([s], lambda _: 25.0)
        assert card["Hit valuation"]["avg_after"] is None
        assert card["Hit valuation"]["n_after"] == 0

    def test_a_sale_recorded_at_nothing_is_not_a_missing_sale_price(self):
        """Selling a holding for nothing is a real entry and the record says
        so — `sale_return` reads it. What cannot be expressed is a change
        measured from nothing, and the reason has to say that rather than
        claim the price was never recorded."""
        s = bought(shares=10, price=10.0, when="2024-01-02")
        sale = portfolio.sell_lots(s, decision("close"), "Thesis broke", 10,
                                   0.0, "2024-06-03")
        assert portfolio.sale_return(s, sale) == -100.0
        x = portfolio.since_sale(s, sale, 44.0)
        assert x["pct"] is None
        assert x["reason"] == ("the sale is recorded at nothing, so what the "
                               "price did against it cannot be expressed")

    def test_adding_after_a_trim_ends_the_window_without_claiming_re_entry(
            self):
        """A trim followed by an add closes the window for the same reason a
        re-entry does — from that purchase the price is moving on shares you
        chose to own. What it is not is proof the position ever closed, and
        nothing may say it was bought back."""
        s = bought(shares=100, price=10.0, when="2024-01-02")
        trim = portfolio.sell_lots(s, decision("reduce"), "Risk limit", 50,
                                   20.0, "2024-06-03")
        portfolio.add_lot(s, decision("commit"), 50, 25.0, "2024-07-01")
        assert len(portfolio.cycles(s)) == 1      # it never closed
        x = portfolio.since_sale(s, trim, 44.0)
        assert x["until"] == "purchase" and x["pct"] == 25.0
        assert portfolio.exit_scorecard(
            [s], lambda _: 44.0)["Risk limit"]["bought_again"] == 1


class TestReturnSinceExit:
    """Watching what happened after a sale is the only way to find out
    whether a sell rule works — and the window has an end. Once the name was
    bought back the move belongs to the new position, and a rule credited
    with a stretch the user spent holding cannot be judged at all."""

    def test_the_window_closes_at_the_re_purchase(self):
        s = rebought()
        x = portfolio.since_sale(s, closing_sale(s), 44.0)
        assert x["until"] == "purchase"
        assert x["date"] == "2025-01-06" and x["price"] == 40.0
        # $20 out, $40 back in. Today's $44 is after they were holding again.
        assert x["pct"] == 100.0

    def test_without_a_re_purchase_it_runs_to_the_price_given(self):
        s = bought(shares=10, price=10.0, when="2024-01-02")
        portfolio.sell_lots(s, decision("close"), "Hit valuation", 10, 20.0,
                            "2024-06-03")
        x = portfolio.since_sale(s, closing_sale(s), 44.0)
        assert x["until"] == "today" and x["date"] is None
        assert x["pct"] == 120.0

    def test_an_open_window_with_no_price_is_absent_and_says_why(self):
        s = bought(shares=10, price=10.0, when="2024-01-02")
        portfolio.sell_lots(s, decision("close"), "Panic", 10, 20.0,
                            "2024-06-03")
        x = portfolio.since_sale(s, closing_sale(s), None)
        assert x["pct"] is None and x["reason"]
        assert x["until"] == "today"

    def test_a_closed_window_is_exact_even_with_no_price_at_all(self):
        """The re-entry price is a recorded fact, so a window that ended at
        one never depends on a fetch and never goes absent for want of it."""
        s = rebought()
        x = portfolio.since_sale(s, closing_sale(s), None)
        assert x["pct"] == 100.0 and x["until"] == "purchase"

    def test_a_purchase_before_the_sale_does_not_close_its_window(self):
        s = bought(shares=10, price=10.0, when="2024-01-02")
        portfolio.add_lot(s, decision("commit"), 10, 12.0, "2024-02-02")
        portfolio.sell_lots(s, decision("close"), "Panic", 20, 20.0,
                            "2024-06-03")
        x = portfolio.since_sale(s, closing_sale(s), 30.0)
        assert x["until"] == "today" and x["pct"] == 50.0

    def test_the_exit_scorecard_windows_each_sale_and_says_how_many(self):
        back = rebought("BACK")            # sold at 20, bought back at 40
        out = bought("OUT", shares=10, price=10.0, when="2024-01-02")
        portfolio.sell_lots(out, decision("close"), "Hit valuation", 10, 20.0,
                            "2024-06-03")
        card = portfolio.exit_scorecard([back, out], lambda s: 80.0)
        b = card["Hit valuation"]
        assert b["n"] == 2 and b["bought_again"] == 1
        # +100% to the re-buy, +300% to today's $80 — averaged, 200%.
        # Unwindowed both would read +300%, and the rule would look twice as
        # wrong as it was.
        assert b["avg_after"] == 200.0
        assert b["avg_held"] == 100.0


class TestScorecards:
    def _closed(self, ticker, override_reason, cost, exit_price,
                reason="Panic"):
        s = held(ticker)
        portfolio.add_lot(s, decision("hold" if override_reason else "commit"),
                          1, cost, "2026-01-01",
                          override_reason=override_reason or "")
        portfolio.sell_lots(s, decision("hold"), reason, 1, exit_price,
                            "2026-06-01")
        return s

    def test_the_two_kinds_of_override_are_counted_apart(self):
        a = held("A")
        portfolio.add_lot(a, decision("hold"), 1, 100.0, "2026-01-01",
                          override_reason="against")
        b = held("B")
        portfolio.add_lot(b, decision("unknown"), 1, 100.0, "2026-01-01",
                          override_reason="without")
        card = portfolio.override_scorecard([a, b], lambda s: 110.0)
        assert card["override"]["n"] == 2
        assert card["kinds"]["against"] == 1
        assert card["kinds"]["without"] == 1

    def test_a_rule_that_keeps_being_overridden_successfully_is_surfaced(self):
        """Principle 10: the analytics must be able to indict the rules, not
        only the user. A per-rule breakdown that only ever counted the user's
        error rate would be a guilt machine."""
        rule = cite("Price / earnings", "fail",
                    threshold_from={"kind": "value", "id": "max-pe",
                                    "label": "Maximum P/E"})
        wins = []
        for i in range(3):
            s = held(f"W{i}")
            portfolio.add_lot(s, decision("hold", evidence=[rule]), 1, 100.0,
                              "2026-01-01", override_reason="anyway")
            wins.append(s)
        card = portfolio.override_scorecard(wins, lambda s: 120.0)
        b = card["per_rule"]["value:max-pe"]
        assert b["label"] == "Maximum P/E"
        assert (b["n"], b["wins"], b["avg"]) == (3, 3, 20.0)

    def test_reconstructed_backfills_are_counted_but_named(self):
        live, rec = held("L"), held("R")
        portfolio.add_lot(live, decision("hold"), 1, 100.0, "2026-01-01",
                          override_reason="x")
        portfolio.add_lot(rec, decision("hold"), 1, 100.0, "2026-01-01",
                          override_reason="x",
                          evaluation={"basis": "reconstructed",
                                      "as_of": "2026-01-01"})
        card = portfolio.override_scorecard([live, rec], lambda s: 110.0)
        assert card["override"]["n"] == 2
        assert card["reconstructed_overrides"] == 1

    def test_overrides_are_counted_per_lot_not_per_security(self):
        s = held("MIXED")
        portfolio.add_lot(s, decision("commit"), 1, 100.0, "2026-01-01")
        portfolio.add_lot(s, decision("hold"), 1, 100.0, "2026-03-01",
                          override_reason="adding anyway")
        card = portfolio.override_scorecard([s], lambda x: 110.0)
        assert card["override"]["n"] == 1
        assert card["compliant"]["n"] == 1

    def test_exits_group_by_reason_and_keep_pricing_after_the_sale(self):
        """If one reason keeps showing a strong return after the sale, that is
        a finding no tool that drops the ticker at exit can produce."""
        a = self._closed("A", None, 100.0, 80.0, reason="Panic")
        b = self._closed("B", None, 100.0, 90.0, reason="Panic")
        c = self._closed("C", None, 100.0, 140.0, reason="Hit valuation")
        prices = {"A": 120.0, "B": 117.0, "C": 133.0}
        card = portfolio.exit_scorecard([a, b, c],
                                        lambda s: prices[s["ticker"]])
        assert card["Panic"]["n"] == 2
        assert card["Panic"]["avg_held"] == -15.0
        assert card["Panic"]["avg_after"] == 40.0
        assert card["Hit valuation"]["avg_after"] == -5.0

    def test_a_position_with_no_price_is_absent_from_the_average_not_zero(
            self):
        s = held("NOPRICE")
        portfolio.add_lot(s, decision("hold"), 1, 100.0, "2026-01-01",
                          override_reason="x")
        card = portfolio.override_scorecard([s], lambda x: None)
        assert card["override"]["n"] == 0
        assert card["override"]["avg"] is None
        # the override itself is still counted — only the return is absent
        assert card["kinds"]["against"] == 1


class TestNotes:
    def test_notes_are_appended_and_never_edited(self):
        s = held()
        portfolio.add_note(s, "first")
        first = copy.deepcopy(s["notes"][0])
        portfolio.add_note(s, "second")
        assert s["notes"][0] == first
        assert [n["text"] for n in s["notes"]] == ["first", "second"]

    def test_an_empty_note_is_not_recorded(self):
        s = held()
        portfolio.add_note(s, "   ")
        assert s["notes"] == []


class TestNoVerdictIsNotAClearSignal:
    """The exit record must distinguish "the strategy read this and nothing
    fired" from "no verdict could be produced at all". Collapsing the second
    into the first claims a signal was read, which is the difference between
    a fact and a fabrication — and it is the record the exit scorecard
    learns from."""

    @pytest.mark.parametrize("render", ["blocked", "unknown"])
    def test_an_evaluation_tier_state_records_an_absence(self, render):
        s = bought()
        lot = portfolio.sell_lots(s, decision(render, state="cant-say"),
                                  "Panic", 10, 30.0, "2026-08-08")
        assert lot["rule_triggered"] is None
        assert lot["signal_at_exit"] == "Cant Say"
        assert "no verdict to go on" in s["notes"][-1]["text"]

    def test_a_real_hold_still_records_that_no_rule_fired(self):
        s = bought()
        lot = portfolio.sell_lots(s, decision("hold"), "Panic", 10, 30.0,
                                  "2026-08-08")
        assert lot["rule_triggered"] is False
        assert "no rule triggering" in s["notes"][-1]["text"]


class TestTheReasonIsNeverDiscarded:
    def test_a_reason_written_before_the_state_moved_is_kept(self):
        """The dialog demands a reason while the verdict says otherwise; the
        state is re-evaluated at commit and can have moved to commit by then.
        Dropping the sentence loses the only record that the user was, at the
        moment they decided, going ahead against something."""
        s = held()
        lot = portfolio.add_lot(s, decision("commit"), 10, 40.0, "2026-08-01",
                                override_reason="It read hold when I typed "
                                                "this.")
        assert lot["override"] is None
        assert "It read hold when I typed this." in s["notes"][-1]["text"]

    def test_an_ordinary_compliant_purchase_gains_no_note(self):
        s = held()
        portfolio.add_lot(s, decision("commit"), 10, 40.0, "2026-08-01",
                          override_reason="")
        assert s["notes"] == []


class TestAveragesSayWhatTheyRestOn:
    def test_an_average_over_a_subset_reports_its_own_count(self):
        """`Panic (3) · held +20%` where only one of the three had a figure
        presents absence as a settled answer."""
        def closed(t, cost, exit_price):
            s = held(t)
            portfolio.add_lot(s, decision("commit"), 1, cost, "2026-01-01")
            portfolio.sell_lots(s, decision("hold"), "Panic", 1, exit_price,
                                "2026-06-01")
            return s

        rows = [closed("A", 100.0, 120.0), closed("B", 0.0, 100.0),
                closed("C", 0.0, 100.0)]
        prices = {"A": 132.0, "B": None, "C": None}
        card = portfolio.exit_scorecard(rows, lambda s: prices[s["ticker"]])
        b = card["Panic"]
        assert (b["n"], b["n_held"], b["n_after"]) == (3, 1, 1)
        assert b["avg_held"] == 20.0
