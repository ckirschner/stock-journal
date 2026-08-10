"""Everything the user supplies is dated, appended, and never rewritten.

Four records travel this path — a judgement, a thesis, a valuation claim, a
hand-entered figure — and every one of them fails silently if it breaks. A
thesis quietly rewritten before it fires makes every override and exit
measured against it worthless. A valuation overwritten at the next purchase
loses the claim the last one was actually made on. A figure typed today and
served to a verdict rebuilt for 2024 is the journal presenting hindsight as
something it computed at the time. None of those produces a crash, an error
or a visibly wrong number — they produce a record that reads as though it
had always said this.

The judgement record has its own file. This one covers the substrate all
four share and the three that were slots until now.
"""

import contextlib
import time
from datetime import date, datetime

import pytest
from conftest import balance_face, dur, entered, filing, inst

from engine import (dated, expected_value, facts_store, hand_entered,
                    journals, judgements, portfolio, price_store, thesis,
                    valuation)

from app import Api

ANSWERS = {"free-cash": "40000", "stance": "building",
           "keeps-reserve": "false", "first-buy": "4"}

DCF = {"price": 20, "fcf_ttm": 4, "shares": 10,
       "discount_rate": 9, "terminal_growth": 2.5}


@pytest.fixture
def api(strategies):
    strategies("awkward")
    a = Api()
    assert a.create_journal("Dated", "awkward", dict(ANSWERS))["ok"]
    return a


def journal():
    return journals.load(journals.resolve_open())


def security(ticker="SYN"):
    return next(s for s in journal()["securities"] if s["ticker"] == ticker)


def company(cik=771, ticker="SYN", close=20.0):
    end = "2024-12-31"
    facts = balance_face(end, extra=[
        inst("us-gaap:AssetsCurrent", end, 200),
        inst("us-gaap:LiabilitiesCurrent", end, 100)])
    facts += [dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                  "2024-01-01", end, 5_000_000, stmt="CashFlow"),
              dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                  "2024-01-01", end, 1_000_000, stmt="CashFlow")]
    facts_store.save_filing(cik, filing("A-1", "10-K", "2025-02-20", end,
                                        facts))
    doc = price_store.load(cik)
    price_store.merge_series(doc, ticker, "test", [["2026-08-01", close, 100]],
                             [])
    price_store.save(cik, doc)
    return cik


def idea(api, ticker="SYN"):
    """A security in the journal, linked to a company, never bought."""
    cik = company(ticker=ticker)
    api.add_security(ticker, "Synthetic Co")
    doc = journal()
    next(s for s in doc["securities"] if s["ticker"] == ticker)["cik"] = cik
    journals.save(doc)


def buy(api, ticker="SYN", shares=10, cost=15.0, when=None):
    assert api.open_position(ticker, shares, cost, when, "recording")["ok"]


def lots_of(ticker="SYN"):
    return portfolio.lots(security(ticker), "buy")


# -- the substrate ------------------------------------------------------------

class TestNothingCanBeBackdatedOrEdited:
    """The guarantee under all four records, and the reason it is one
    module rather than four copies of the same walk."""

    KEYS = ("judgements", "thesis", "valuations", "hand_entered")

    @pytest.mark.parametrize("key", KEYS)
    def test_a_caller_cannot_say_when_an_entry_was_written(self, key):
        """There is no parameter to backdate an entry with, and handing one
        over anyway is refused rather than ignored.

        This is the whole thing. Every other guarantee here — a purchase
        seeing the version in force on its day, an amendment being findable
        against the exit that followed it — rests on `recorded` meaning "when
        the journal wrote this down". A caller that could set it could write
        a thesis into the week before an exit it was actually composed after.
        """
        s = {}
        for field in ("recorded", "seq"):
            with pytest.raises(ValueError) as e:
                dated.append(s, key, {"id": "x", field: "2020-01-01"})
            assert "set by the journal" in str(e.value)
        assert s == {}, "a refused append still touched the record"

    @pytest.mark.parametrize("key", KEYS)
    def test_there_is_no_way_to_edit_or_remove_an_entry(self, key):
        """Principle 14: the wrong thing is unavailable, not discouraged.

        A module offering `edit` "for corrections" is a module where the
        correction happens at the moment it is most tempting. Corrections are
        new entries. Asserted as an absence because that is what it is.
        """
        for module in (thesis, valuation, hand_entered, dated):
            for verb in ("edit", "delete", "remove", "replace", "update"):
                assert not hasattr(module, verb), \
                    f"{module.__name__}.{verb} exists"

    def test_the_entry_in_force_is_the_newest_written_by_that_day(self):
        s = {}
        for day, value in (("2024-01-01", 1), ("2025-06-30", 2),
                           ("2026-02-02", 3)):
            entered(s, day, fcf_ttm=value)
        walk = [hand_entered.in_force(s, "fcf_ttm", d)
                for d in (None, "2026-08-09", "2025-12-31", "2024-06-01",
                          "2023-01-01")]
        assert [(e or {}).get("value") for e in walk] == [3, 3, 2, 1, None]


# -- the thesis ---------------------------------------------------------------

class TestTheThesisIsAmendedNeverRewritten:
    def test_a_first_statement_needs_no_reason(self, api):
        """There is nothing to explain the first time you write down what
        you believe. Requiring one here would be friction with no record
        behind it, and would train people to type a full stop."""
        idea(api)
        r = api.amend_thesis("SYN", "Toll road on payments.",
                             "Take rate below 2% for two quarters.")
        assert r["ok"] and r["amended"] is True
        assert len(security()["thesis"]) == 1
        assert security()["thesis"][0]["reason"] == ""

    def test_an_amendment_without_a_reason_is_refused(self, api):
        """The field most likely to be rewritten under pressure is the
        falsifier, and the pressure arrives exactly when it is about to
        fire. A reason does not stop anyone — nothing here stops anyone —
        but a rewrite that had to be explained is a rewrite the person
        making it had to look at.

        Required on the whole document rather than on the falsifier alone,
        because a requirement you can route around by editing the other half
        of the same form is not a requirement.
        """
        idea(api)
        assert api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.")
        r = api.amend_thesis("SYN", "Toll road.", "Take rate below 4%.")
        assert r["ok"] is False
        assert "Say why it changed" in r["error"]
        assert len(security()["thesis"]) == 1

    def test_an_amendment_appends_and_the_earlier_version_survives_whole(
            self, api):
        """Whole versions, never diffs. An amendment has to be legible on
        its own — beside the purchase it qualified, or in a list of every
        thesis rewritten in the month before an exit — and a diff only means
        anything sitting next to its neighbour."""
        idea(api)
        assert api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.")
        assert api.amend_thesis("SYN", "Toll road, plus float.",
                                "Take rate below 4%.",
                                "Rivals cut price; 2% was never realistic.")
        log = security()["thesis"]
        assert len(log) == 2
        assert log[0]["falsifier"] == "Take rate below 2%."
        assert log[0]["thesis"] == "Toll road."
        assert log[1]["reason"].startswith("Rivals cut price")
        # And the standing one is the newer.
        assert thesis.in_force(security())["falsifier"] == "Take rate below 4%."

    def test_saving_an_unchanged_thesis_records_nothing(self, api):
        """A history that has to be waded through is a history nobody
        reads, and the amendment that matters is the one you can find."""
        idea(api)
        assert api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.")
        r = api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.", "x")
        assert r["ok"] and r["amended"] is False
        assert len(security()["thesis"]) == 1

    def test_an_empty_thesis_is_not_a_thesis(self, api):
        idea(api)
        r = api.amend_thesis("SYN", "   ", "")
        assert r["ok"] is False and "empty thesis" in r["error"]
        assert security().get("thesis") == []

    def test_a_purchase_freezes_the_version_standing_on_its_own_day(
            self, api, written_on):
        """The point of dating it. A thesis composed after a purchase is not
        the case that was made for that purchase, however true it turned out
        to be — so a backdated buy freezes what was on record then, which is
        sometimes nothing, and never what came later."""
        idea(api)
        with written_on("2026-01-10"):
            api.amend_thesis("SYN", "First take.", "Margin below 30%.")
        buy(api, when="2025-06-01")            # before the thesis existed
        buy(api, when="2026-03-01")            # after it
        with written_on("2026-06-01"):
            api.amend_thesis("SYN", "Second take.", "Margin below 20%.",
                             "Learned the mix was different.")
        buy(api, when="2026-07-01")

        frozen = [(l["date"], (l["snapshot"]["thesis"] or {}).get("thesis"))
                  for l in lots_of()]
        assert frozen == [("2025-06-01", None),
                          ("2026-03-01", "First take."),
                          ("2026-07-01", "Second take.")]
        # The middle purchase is still reading the first version — a later
        # amendment did not reach backwards into it.
        assert lots_of()[1]["snapshot"]["thesis"]["seq"] == 1

    def test_a_frozen_thesis_carries_its_own_date_and_version(self, api):
        """A copy that cannot say which version it was, or when that version
        was written, is a copy the record can never be reconciled against."""
        idea(api)
        assert api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.")
        buy(api)
        frozen = lots_of()[0]["snapshot"]["thesis"]
        assert frozen["seq"] == 1 and frozen["recorded"]
        assert frozen["recorded"] == security()["thesis"][0]["recorded"]

    def test_naked_prose_cannot_be_frozen_onto_a_lot(self):
        """The structural half of the guarantee above. A caller reading the
        thesis from anywhere other than its own record — the text off a
        form, say — is refused at the write rather than trusted."""
        s = portfolio.new_security("SYN", "Synthetic Co")
        with pytest.raises(ValueError) as e:
            portfolio.add_lot(s, None, 1, 10.0, thesis="Toll road.")
        assert "bare str" in str(e.value)

    def test_a_thesis_from_a_previous_holding_says_so(self, api, written_on):
        """Buying a name back does not renew what you wrote about owning it
        last time. You sold it, the reasons you sold it are not in that
        thesis, and the tool has nothing better to offer — so it offers it,
        and never lets it pass as having been written about the holding in
        front of you."""
        idea(api)
        with written_on("2026-01-04"):          # while the first holding ran
            api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.")
        buy(api, when="2026-01-05")
        assert api.sell_shares("SYN", "Hit valuation", 30.0, "2026-04-05")["ok"]
        buy(api, when="2026-06-01")

        standing = thesis.standing(security(), today="2026-08-09")
        assert standing["status"] == "known"
        assert any("earlier holding that closed on 2026-04-05" in c
                   for c in standing["cautions"])

    def test_a_thesis_written_between_two_holdings_is_not_stale(self, api):
        """Deciding whether to buy back is exactly when you should be
        writing one. A caution on every correctly-formed thesis is a caution
        nobody reads."""
        idea(api)
        buy(api, when="2026-01-05")
        assert api.sell_shares("SYN", "Hit valuation", 30.0, "2026-04-05")["ok"]
        assert api.amend_thesis("SYN", "Cheaper now.", "Take rate below 2%.")
        buy(api, when="2026-06-01")
        assert thesis.standing(security(), today="2026-08-09")["cautions"] == []

    def test_a_sale_freezes_the_thesis_it_was_judged_against(self, api):
        """Where the thesis gets graded. "Did the falsifier fire, or did I
        talk myself out of it" is a question about the version standing when
        the sell button was pressed, and that version is amendable right up
        until it."""
        idea(api)
        assert api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.")
        buy(api, when="2026-01-05")
        assert api.sell_shares("SYN", "Thesis broke", 9.0, "2026-04-05")["ok"]
        sale = portfolio.lots(security(), "sell")[0]
        assert sale["snapshot"]["thesis"]["falsifier"] == "Take rate below 2%."
        # And no valuation: a claim is the case for a purchase, and
        # attaching one to an exit would invent a number the sale was never
        # justified by.
        assert sale["snapshot"]["valuation"] is None


# -- the valuation claim ------------------------------------------------------

class TestAValuationBelongsToItsPurchase:
    def test_a_second_claim_appends_and_neither_is_averaged(self, api):
        """What you thought it was worth at $40 is not amended by what you
        think at $61. They are two claims about two decisions, and a blend
        of them is a number no decision was ever made on — so both are kept
        and nothing anywhere reduces the list."""
        idea(api)
        assert api.record_valuation("SYN", "reverse_dcf", DCF)["ok"]
        assert api.record_valuation("SYN", "reverse_dcf",
                                    {**DCF, "price": 31})["ok"]
        claims = security()["valuations"]
        assert [c["inputs"]["price"] for c in claims] == [20, 31]
        assert valuation.in_force(security())["inputs"]["price"] == 31

    def test_a_claim_that_does_not_solve_never_lands(self, api):
        """Solved before it is stored, so the record cannot hold assumptions
        that produce nothing. An unsolvable claim on the record would render
        as a valuation with a blank answer, which reads as a tool failure
        rather than as arithmetic that cannot be done."""
        idea(api)
        r = api.record_valuation("SYN", "reverse_dcf",
                                 {**DCF, "discount_rate": 1,
                                  "terminal_growth": 5})
        assert r["ok"] is False
        assert "must exceed terminal growth" in r["error"]
        assert security().get("valuations") == []

    def test_the_frozen_claim_keeps_the_answer_it_gave_that_day(self, api,
                                                                monkeypatch):
        """The one place a computed number is written down instead of
        derived. A lot records what was on screen when a decision was made,
        and re-deriving it years later through whatever the code has become
        would let a refactor restate a purchase — which principle 3 forbids
        outright."""
        idea(api)
        assert api.record_valuation("SYN", "reverse_dcf", DCF)["ok"]
        buy(api)
        was = lots_of()[0]["snapshot"]["valuation"]["result"]
        assert was["value"] is not None

        monkeypatch.setattr(expected_value, "compute",
                            lambda *a, **k: {"value": -999.0,
                                             "display": "-999",
                                             "label": "Implied growth",
                                             "note": ""})
        assert lots_of()[0]["snapshot"]["valuation"]["result"] == was

    def test_a_prefilled_figures_cautions_reach_the_stored_claim(self, api):
        """A cash flow prefilled from a line that folds in finance leases is
        that kind of number in the claim built on it. A record that kept
        where a figure came from while dropping what was wrong with it
        states the claim as more certain than it was — and an append-only
        record can never be told afterwards."""
        idea(api)
        sources = {"fcf_ttm": {"used": "computed",
                               "provenance": "cash flow face",
                               "cautions": ["the debt line folds in "
                                            "finance leases"]}}
        assert api.record_valuation("SYN", "reverse_dcf", DCF, sources)["ok"]
        stored = security()["valuations"][0]["sources"]["fcf_ttm"]
        assert stored["cautions"] == ["the debt line folds in finance leases"]

    def test_a_source_for_an_input_the_method_does_not_declare_is_dropped(
            self, api):
        idea(api)
        sources = {"fcf_ttm": {"used": "computed", "provenance": "p"},
                   "owner_earnings": {"used": "typed", "provenance": "q"}}
        assert api.record_valuation("SYN", "reverse_dcf", DCF, sources)["ok"]
        assert set(security()["valuations"][0]["sources"]) == {"fcf_ttm"}

    def test_a_purchase_freezes_the_claim_standing_on_its_own_day(
            self, api, written_on):
        idea(api)
        with written_on("2026-01-10"):
            api.record_valuation("SYN", "reverse_dcf", DCF)
        buy(api, when="2025-06-01")            # before it was valued
        buy(api, when="2026-03-01")
        frozen = [(l["date"], l["snapshot"]["valuation"]) for l in lots_of()]
        assert frozen[0][1] is None
        assert frozen[1][1]["inputs"]["price"] == 20

    def test_a_claim_that_talked_you_out_of_buying_is_still_on_the_record(
            self, api):
        """The most instructive entries in the log are the ones with no
        purchase attached. A claim stored only on a lot would lose every
        valuation that stopped a purchase happening."""
        idea(api)
        assert api.record_valuation("SYN", "reverse_dcf", DCF)["ok"]
        assert not portfolio.has_history(security())
        assert len(security()["valuations"]) == 1

    def test_re_running_identical_assumptions_records_nothing(self, api):
        idea(api)
        assert api.record_valuation("SYN", "reverse_dcf", DCF)["recorded"]
        r = api.record_valuation("SYN", "reverse_dcf", DCF)
        assert r["ok"] and r["recorded"] is False
        assert r["result"]["value"] is not None      # the dialog still paints
        assert len(security()["valuations"]) == 1


# -- hand-entered figures -----------------------------------------------------

class TestAHandEnteredFigureIsDated:
    def test_it_is_served_to_a_pin_after_it_and_withheld_from_one_before(self):
        """The contamination this record exists to stop. A figure typed
        today may have been typed *because* of what happened since, so
        serving it to a verdict rebuilt for an earlier day would let
        hindsight into a reconstruction."""
        s = entered({}, "2025-06-30", fcf_ttm=149.0)
        assert hand_entered.reading(s, "fcf_ttm", "2025-12-31")["value"] == 149.0
        early = hand_entered.reading(s, "fcf_ttm", "2025-01-01")
        assert early["status"] == "absent"
        assert "2025-06-30" in early["reason"] and "2025-01-01" in early["reason"]

    def test_a_withdrawal_is_an_entry_and_can_never_be_read_as_a_value(self):
        """A record that can be emptied is a record that can be emptied at
        the convenient moment. Blanking a field says you withdrew the figure
        on the day you withdrew it — and the entry holds nothing, so nothing
        that builds a known value can reach it. A `None` served as a measure
        is principle 4's exact failure."""
        s = entered({}, "2026-01-05", fcf_ttm=149.0)
        entered(s, "2026-02-05", fcf_ttm=None)
        assert len(s["hand_entered"]) == 2
        assert s["hand_entered"][1]["value"] is None
        r = hand_entered.reading(s, "fcf_ttm")
        assert r["status"] == "absent" and "value" not in r
        assert "fcf_ttm" not in hand_entered.values(s)
        # And the figure withdrawn is still on record for the day it stood.
        assert hand_entered.reading(s, "fcf_ttm", "2026-01-20")["value"] == 149.0

    def test_a_withdrawn_measure_stays_visible_on_the_screen(self, api):
        """`ids` is what keeps a measure on screen after the strategy stops
        reading it. Dropping the withdrawn ones would make a value's own
        history unreachable the moment you cleared it — which is the moment
        it becomes worth reading."""
        idea(api)
        assert api.save_metrics("SYN", {"fcf_ttm": 149.0}, None)["ok"]
        assert api.save_metrics("SYN", {"fcf_ttm": ""}, None)["ok"]
        assert hand_entered.ids(security()) == ["fcf_ttm"]
        row = next(i for i in api.get_state()["securities"][0]["_inputs"]
                   if i["id"] == "fcf_ttm")
        assert len(row["entries"]) == 2
        assert row["entered"]["status"] == "absent"

    def test_saving_unchanged_fields_records_nothing(self, api):
        """The values dialog posts every field it offered on every save, so
        an unconditional append would turn five visits to that screen into
        five identical entries and bury the one revision worth finding."""
        idea(api)
        assert api.save_metrics("SYN", {"fcf_ttm": 149.0}, None)["ok"]
        assert api.save_metrics("SYN", {"fcf_ttm": 149.0}, None)["ok"]
        assert len(security()["hand_entered"]) == 1
        # A field that was always blank is not a withdrawal either.
        assert api.save_metrics("SYN", {"current_ratio": ""}, None)["ok"]
        assert len(security()["hand_entered"]) == 1

    def test_a_revision_appends_above_the_figure_it_replaced(self, api):
        idea(api)
        assert api.save_metrics("SYN", {"fcf_ttm": 149.0}, None)["ok"]
        assert api.save_metrics("SYN", {"fcf_ttm": 151.0}, None)["ok"]
        assert [e["value"] for e in security()["hand_entered"]] == [149.0, 151.0]

    def test_a_whole_set_can_be_checked_before_any_of_it_is_written(self):
        """An append-only record cannot take an entry back, so "three fields
        landed and the fourth was refused" is not a state to recover from —
        it has to be a state that cannot be reached.

        Pinned on the engine, because that is where the guarantee is. The
        API path is also protected by re-reading the journal on every call,
        which means the test below would pass even with the refusal removed
        — two mechanisms, one of them incidental, and a test that cannot
        tell them apart is not testing either.
        """
        s = portfolio.new_security("SYN", "Synthetic Co")
        fields = {"fcf_ttm": 149.0, "current_ratio": "not a number"}
        with pytest.raises(ValueError):
            for eid, v in fields.items():
                hand_entered.checked(eid, v)
        assert s["hand_entered"] == [], "checking a field wrote one"

    def test_a_refused_field_leaves_nothing_on_the_record(self, api):
        """The same thing from the outside: the user sees a message, and
        the journal on disk is exactly as it was."""
        idea(api)
        r = api.save_metrics("SYN", {"fcf_ttm": 149.0,
                                     "current_ratio": "not a number"}, None)
        assert r["ok"] is False
        assert "must be a number" in r["error"]
        assert security().get("hand_entered") == []


class TestOneLotCarriesOneClock:
    def test_the_frozen_values_and_the_decision_agree_about_a_judgement(
            self, api, written_on):
        """A lot freezes two things about the same assessment: the values
        behind the decision, and the decision itself. They are built by
        different code and must read the holding history on the same day.

        The day that matters is the *purchase* date, not the real calendar.
        A buy backdated into a holding that had not ended yet must not freeze
        "this belongs to an earlier holding that closed on ..." — that
        holding had not closed when the purchase was made, and the sentence
        is about a fact that had not happened. A caution invented into an
        append-only record can never be taken back out, and a caution filed
        off it can never be put back.
        """
        idea(api)
        with written_on("2026-01-04"):
            api.record_judgement("SYN", "moat_durability", "pass",
                                 "Switching costs are contractual.")
        buy(api, when="2026-01-05")
        assert api.sell_shares("SYN", "Hit valuation", 30.0, "2026-04-05")["ok"]
        buy(api, when="2026-06-01")
        # Backdated into the FIRST holding, which had not closed then.
        buy(api, when="2026-02-01")

        lot = next(l for l in lots_of() if l["date"] == "2026-02-01")
        frozen = lot["snapshot"]["metrics"].get("moat_durability")
        assert frozen is not None, "the assessment did not reach the snapshot"
        assert frozen["cautions"] == [], frozen["cautions"]

        cited = {e["subject"]["id"]: e
                 for e in lot["snapshot"]["decision"]["reason"]["evidence"]}
        seen = cited.get("moat_durability")
        if seen is not None:
            assert (seen["observed"].get("cautions") or []) \
                == frozen["cautions"], "one lot, two answers"


# -- what the three do not share ----------------------------------------------

class TestSharedWhereItIsTheSameQuestion:
    def test_only_the_records_about_a_holding_go_stale_on_re_entry(
            self, api, written_on):
        """A thesis and a valuation are about a decision you made, so buying
        the name back leaves them describing a different one. A number read
        off a balance sheet is about the *company*, and a holding closing
        says nothing about whether the figure is still right.

        The mechanism is shared; the predicate is not, and forcing one
        would put a warning on a figure with nothing wrong with it.
        """
        idea(api)
        with written_on("2026-01-04"):
            api.amend_thesis("SYN", "Toll road.", "Take rate below 2%.")
            api.record_valuation("SYN", "reverse_dcf", DCF)
            api.save_metrics("SYN", {"fcf_ttm": 149.0}, None)
        buy(api, when="2026-01-05")
        assert api.sell_shares("SYN", "Hit valuation", 30.0, "2026-04-05")["ok"]
        buy(api, when="2026-06-01")

        s, today = security(), "2026-08-09"
        assert thesis.standing(s, today=today)["cautions"]
        assert valuation.standing(s, today=today)["cautions"]
        assert hand_entered.reading(s, "fcf_ttm")["cautions"] == []


# -- the day the writer was standing on ---------------------------------------

class TestOneCalendarNotTwo:
    """`recorded` and `as_of` are compared against each other, so they have to
    be the same calendar.

    Every other date in this program is local: a purchase date, a sale date, a
    pin, `today`. `recorded` was the only one derived from somewhere else, and
    for part of every day the two calendars disagree — so an evening's work
    west of Greenwich was invisible to a purchase dated that same evening, and
    a morning's work east of it was served to a reconstruction of the day
    before. Both silently, which is the failure the whole record exists to
    refuse: hindsight entering a reconstruction in one direction, and a
    permanent "bought with no thesis" frozen onto a lot in the other.

    These tests force a timezone and a wall-clock instant, because the bug is
    invisible at noon UTC — which is exactly where every other fixture in this
    suite writes, and why 808 tests passed against the broken version at every
    offset from UTC-11 to UTC+14.
    """

    WEST, EAST = "America/Los_Angeles", "Asia/Tokyo"

    @staticmethod
    @contextlib.contextmanager
    def clock(monkeypatch, zone, local_iso):
        """The machine in `zone`, with the wall clock at `local_iso` local.

        The real `stamp` runs — only the instant and the offset are pinned —
        so this exercises the production clock rather than a fixture standing
        in for it. `now(tz)` answers the same instant either way, so the same
        test drives a UTC stamp and a local one and can tell them apart.
        """
        monkeypatch.setenv("TZ", zone)
        time.tzset()
        wall = datetime.fromisoformat(local_iso)

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                here = wall.astimezone()
                return here if tz is None else here.astimezone(tz)

        monkeypatch.setattr(dated, "datetime", Clock)
        monkeypatch.setattr(portfolio, "datetime", Clock)
        try:
            yield
        finally:
            time.tzset()

    # Written through each record's own public write, because the guarantee
    # is about the substrate and all four sit on it.
    WRITES = {
        "thesis": lambda s: thesis.amend(s, "A toll road.", "Take rate <2%."),
        "valuations": lambda s: valuation.claim(s, "reverse_dcf", dict(DCF)),
        "hand_entered": lambda s: hand_entered.record(s, "fcf_ttm", 149.0),
        "judgements": lambda s: judgements.assess(
            s, "moat_durability", "pass", "Regulated crossing."),
    }

    @pytest.mark.parametrize("key", sorted(WRITES))
    def test_an_evening_entry_is_in_force_for_that_same_evening(
            self, monkeypatch, key):
        """West of Greenwich, 19:30 is already tomorrow in UTC.

        A thesis written on the evening of the fifth, and a purchase dated the
        fifth, are the same day to the person who did both. Stamped in UTC the
        entry lands on the sixth and the purchase cannot see it — and what the
        purchase freezes is append-only, so "bought with no thesis" would be
        permanent and there is no entry that corrects it.
        """
        s = {}
        with self.clock(monkeypatch, self.WEST, "2026-08-05T19:30:00"):
            self.WRITES[key](s)
        entry = s[key][0]
        assert dated.day_of(entry) == "2026-08-05", entry["recorded"]
        assert dated.in_force(s, key, as_of="2026-08-05") is not None

    @pytest.mark.parametrize("key", sorted(WRITES))
    def test_a_morning_entry_is_withheld_from_the_day_before(
            self, monkeypatch, key):
        """East of Greenwich, 07:00 is still yesterday in UTC — the worse
        direction, because it is hindsight presenting itself as something that
        was on record at the time. The module's own docstring promises exactly
        this cannot happen."""
        s = {}
        with self.clock(monkeypatch, self.EAST, "2026-08-10T07:00:00"):
            self.WRITES[key](s)
        entry = s[key][0]
        assert dated.day_of(entry) == "2026-08-10", entry["recorded"]
        assert dated.in_force(s, key, as_of="2026-08-09") is None

    def test_a_purchase_that_evening_freezes_that_evening_s_thesis(
            self, api, monkeypatch):
        """The consequence that cannot be undone, end to end through the Api.

        A lot's frozen thesis is written once and there is no path that
        corrects it — `_dated_entry` is deliberately the only way in. A one-day
        skew therefore writes a permanent falsehood into the record the whole
        product exists to keep honest, and it also breaks the override
        arithmetic: a purchase frozen against no thesis cannot be graded
        against a falsifier that was in fact standing.
        """
        idea(api)
        with self.clock(monkeypatch, self.WEST, "2026-08-05T19:30:00"):
            assert api.amend_thesis("SYN", "A toll road.", "Take rate <2%.")["ok"]
            buy(api, when="2026-08-05")
        frozen = lots_of()[0]["snapshot"]["thesis"]
        assert frozen is not None, "the evening's thesis was not on record"
        assert frozen["seq"] == 1

    def test_nothing_is_ever_dated_after_today(self, monkeypatch):
        """A record that says you wrote something tomorrow is a record the
        reader stops trusting, and it is what a UTC stamp renders west of
        Greenwich for the last hours of every day."""
        s = {}
        with self.clock(monkeypatch, self.WEST, "2026-08-05T23:59:00"):
            thesis.amend(s, "A toll road.", "Take rate <2%.")
            today = date.today().isoformat()
        assert dated.day_of(s["thesis"][0]) == "2026-08-05"
        assert dated.day_of(s["thesis"][0]) <= today

    def test_a_thesis_written_the_morning_after_an_exit_is_not_called_stale(
            self, api, monkeypatch):
        """The caution that fires when nothing is wrong.

        `last_exit` is a local lot date and the thesis's day was a UTC one, so
        east of Greenwich a thesis written the morning after an exit was told
        it "belongs to an earlier holding" — about words the user had written
        minutes earlier. This one fires on the live path, where `as_of` being
        None is no protection at all.
        """
        idea(api)
        with self.clock(monkeypatch, self.EAST, "2026-08-04T12:00:00"):
            assert api.amend_thesis("SYN", "First read.", "Take rate <2%.")["ok"]
            buy(api, when="2026-08-04")
        # Sold, then bought back the same day. The re-entry is what makes the
        # caution reachable at all: `last_exit` answers "when did the holding
        # BEFORE this one end", so it is None while nothing is held and the
        # test would pass against any implementation without it.
        assert api.sell_shares("SYN", "Hit valuation", 30.0, "2026-08-09")["ok"]
        buy(api, when="2026-08-09")
        with self.clock(monkeypatch, self.EAST, "2026-08-10T07:00:00"):
            assert api.amend_thesis("SYN", "Second read.", "Take rate <1%.",
                                    "Bought it back cheaper.")["ok"]
        standing = thesis.standing(security(), today="2026-08-10")
        assert standing["amended"] == "2026-08-10"
        assert standing["cautions"] == [], standing["cautions"]

    def test_the_order_of_the_record_does_not_depend_on_where_you_read_it(
            self, monkeypatch):
        """Principle 3: history is append-only, so its order is a fact about
        the record and not about the machine reading it.

        Stamps carry an offset now, so the raw text no longer sorts
        chronologically — "2026-08-09T19:30:00-07:00" is *after*
        "2026-08-10T02:00:00+00:00" and sorts before it. `history` orders by
        the parsed instant for that reason, and this goes red against the
        lexicographic key it replaced.

        What it does NOT catch, said plainly: ordering by the stored day
        passes this, because a slice of a stamp is as machine-independent as
        the instant is. The two only disagree where a later entry carries an
        earlier local day, which cannot happen inside one record — appends
        happen in real time and `seq` settles them. The instant is still the
        right key; this test guards the property that matters, not that one.
        """
        s = {}
        for zone, when in ((self.WEST, "2026-08-09T19:30:00"),
                           (self.EAST, "2026-08-10T12:00:00"),
                           (self.WEST, "2026-08-10T09:00:00")):
            with self.clock(monkeypatch, zone, when):
                hand_entered.record(s, "fcf_ttm", len(s.get("hand_entered", [])))

        def order_under(zone):
            monkeypatch.setenv("TZ", zone)
            time.tzset()
            return [e["seq"] for e in dated.history(s, "hand_entered")]

        try:
            assert order_under(self.WEST) == [3, 2, 1]
            assert order_under(self.EAST) == [3, 2, 1]
        finally:
            time.tzset()
