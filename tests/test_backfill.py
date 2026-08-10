"""Entering a position out of your own history, honestly.

Three things had to be true before a journal could be told about a purchase
made in 2019, and each of them fails silently if it breaks.

**A reconstruction that reaches no verdict is not an override.** Nobody saw a
signal, because nobody was standing in front of one, and the grey box is a
fact about what this program can rebuild rather than about anyone's
discipline. Recorded as an override it puts decisions nobody made into the
one figure that measures the user's judgement — and the moment backfill
exists it puts a pile of them there at once, so the scorecard reports that
overriding works fine.

**A backdated exit is judged with the data of its own day.** It was judged
with today's, so `signal_at_exit` and `rule_triggered` — the two facts the
panic-sell loop teaches from — carried a verdict the strategy was never asked
for.

**A reconstruction never passes for a record made at the time.** Everywhere it
appears, in the record and on every screen.

Driven through the real Api throughout: every one of these spans the write,
the clock and the screen, and none of them is visible from one end alone.
"""

from datetime import date

import pytest
from conftest import balance_face, dur, filing, inst, open_since

from engine import facts_store, journals, portfolio, price_store

from app import Api

ANSWERS = {"free-cash": "40000", "stance": "building",
           "keeps-reserve": "false", "first-buy": "4"}


@pytest.fixture
def api(strategies):
    strategies("awkward")
    a = Api()
    assert a.create_journal("Backfilled", "awkward", dict(ANSWERS))["ok"]
    return a


def journal():
    return journals.load(journals.resolve_open())


def security(ticker="SYN"):
    return next(s for s in journal()["securities"] if s["ticker"] == ticker)


def company(cik=881, ticker="SYN", filed="2025-02-20", close=30.0):
    """A filer whose only filing lands in 2025, so a purchase dated before
    that reconstructs against nothing — which is the ordinary shape of a
    position bought before this program existed."""
    end = "2024-12-31"
    facts = balance_face(end, extra=[
        inst("us-gaap:AssetsCurrent", end, 200),
        inst("us-gaap:LiabilitiesCurrent", end, 100)])
    facts += [dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                  "2024-01-01", end, 5_000_000, stmt="CashFlow"),
              dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                  "2024-01-01", end, 1_000_000, stmt="CashFlow")]
    facts_store.save_filing(cik, filing("A-1", "10-K", filed, end, facts))
    doc = price_store.load(cik)
    price_store.merge_series(doc, ticker, "test",
                             [["2026-08-01", close, 100]], [])
    price_store.save(cik, doc)
    return cik


def tracked(api, ticker="SYN", cik=881):
    api.add_security(ticker, "Synthetic Co")
    doc = journal()
    next(s for s in doc["securities"] if s["ticker"] == ticker)["cik"] = \
        company(cik, ticker)
    journals.save(doc)


HISTORY = [
    {"kind": "buy", "date": "2019-03-12", "shares": 100, "price": 10.0},
    {"kind": "buy", "date": "2022-05-04", "shares": 50, "price": 16.0},
    {"kind": "sell", "date": "2024-09-10", "shares": 50, "price": 24.0,
     "reason": "Hit valuation"},
]


# -- the correction that had to land first -----------------------------------

class TestAnUnrebuiltEvaluationIsNotAnOverride:
    def test_a_purchase_nothing_could_be_rebuilt_for_records_the_gap(
            self, api):
        tracked(api)
        assert api.open_position("SYN", 100, 10.0, "2019-03-12")["ok"]
        lot = security()["lots"][0]
        assert lot["override"] is None, \
            "there was no signal on any screen to go against"
        gap = lot["unreconstructed"]
        assert gap["as_of"] == "2019-03-12"
        assert gap["why"].strip(), \
            "a gap the reader cannot act on is worse than none"
        assert gap["note"], "the record can never be asked again what it " \
                            "was working from"

    def test_the_scorecard_keeps_it_out_of_both_comparisons(self, api):
        tracked(api)
        assert api.open_position("SYN", 100, 10.0, "2019-03-12")["ok"]
        card = api.get_state()["override_scorecard"]
        for cohort in ("live", "reconstructed"):
            for group in ("override", "compliant"):
                assert card[cohort][group]["n_purchases"] == 0, \
                    f"{cohort}/{group} claimed a decision nobody made"
        assert card["unreconstructed"]["n_purchases"] == 1
        assert card["unreconstructed"]["reasons"]

    def test_a_reconstruction_that_did_reach_a_verdict_is_an_override(
            self, api):
        """The other side of the line. A day that DID rebuild, and the
        purchase was made past it — that is a decision, and it belongs in the
        comparison. In the reconstructed cohort, because it is still not a
        verdict anybody was looking at."""
        assert api.create_journal("Paused", "awkward",
                                  {**ANSWERS, "stance": "paused"})["ok"]
        open_since("2019-01-01")
        tracked(api, cik=882)
        # Paused is a state the STRATEGY declared — "decide something before
        # I answer" — so going ahead is going against it, rebuilt or not.
        assert api.open_position("SYN", 5, 10.0, "2026-06-01",
                                 "I wanted more of it.")["ok"]
        lot = security()["lots"][0]
        assert lot["unreconstructed"] is None
        assert lot["override"]["basis"] == "reconstructed"
        card = api.get_state()["override_scorecard"]
        assert card["reconstructed"]["override"]["n_purchases"] == 1
        assert card["live"]["override"]["n_purchases"] == 0

    def test_the_preview_says_which_of_the_four_it_would_be(self, api):
        """The dialog asks for a reason on an override and must not ask for
        one where there was no signal to override. A second copy of that
        judgement in the browser is how the two came to disagree about the
        same purchase, so the engine answers and the view reads it."""
        tracked(api, cik=883)
        old = api.preview_purchase("SYN", "2019-03-12")
        assert old["recorded_as"] == "unreconstructed"
        now = api.preview_purchase("SYN", date.today().isoformat())
        assert now["recorded_as"] in portfolio.RECORDED_AS
        assert now["recorded_as"] != "unreconstructed", \
            "nothing recorded today is a failed reconstruction"


# -- the other half of the as-of machinery -----------------------------------

class TestABackdatedExitReconstructs:
    def _held(self, api, cik=884, when="2024-01-05"):
        open_since("2019-01-01")
        tracked(api, cik=cik)
        assert api.open_position("SYN", 100, 10.0, when)["ok"]

    def test_the_sale_records_the_day_it_was_judged_on(self, api):
        self._held(api)
        r = api.sell_shares("SYN", "Panic", 24.0, "2026-03-02")
        assert r["ok"] and r["basis"] == "reconstructed"
        assert r["as_of"] == "2026-03-02"
        sale = portfolio.lots(security(), "sell")[0]
        assert sale["snapshot"]["evaluation"]["as_of"] == "2026-03-02"
        assert portfolio.basis_of(sale) == "reconstructed"

    def test_a_sale_recorded_today_still_says_it_was_seen(self, api):
        self._held(api, cik=885)
        r = api.sell_shares("SYN", "Panic", 24.0, date.today().isoformat())
        assert r["ok"] and r["basis"] == "live"
        assert portfolio.basis_of(portfolio.lots(security(), "sell")[0]) \
            == "live"

    def test_the_frozen_values_are_the_ones_of_that_day(self, api):
        """The point of reconstructing at all. A filing that landed after the
        sale must not appear among the figures the sale was recorded
        against."""
        self._held(api, cik=886)
        assert api.sell_shares("SYN", "Panic", 24.0, "2024-06-01")["ok"], \
            "the purchase this draws on is dated 2024-01-05"
        sale = portfolio.lots(security(), "sell")[0]
        note = sale["snapshot"]["evaluation"]["note"]
        assert "2024-06-01" in note
        assert "none of the 1 stored filings" in note, note

    def test_the_exit_scorecard_counts_the_rebuilt_ones_apart(self, api):
        self._held(api, cik=887)
        assert api.sell_shares("SYN", "Panic", 24.0, "2026-03-02", 40)["ok"]
        assert api.sell_shares("SYN", "Panic", 26.0,
                               date.today().isoformat(), 60)["ok"]
        group = api.get_state()["exit_scorecard"]["Panic"]
        assert group["n"] == 2
        assert group["n_reconstructed"] == 1

    def test_the_exit_reason_list_says_which_sales_were_rebuilt(self, api):
        """A holding closed in stages can be closed partly at the time and
        partly from memory. "Panic, 40% of the exit" means one thing when it
        was typed while the screen said hold and another when it came out of
        a statement years later."""
        self._held(api, cik=888)
        assert api.sell_shares("SYN", "Risk limit", 24.0, "2026-03-02",
                               40)["ok"]
        assert api.sell_shares("SYN", "Panic", 26.0,
                               date.today().isoformat(), 60)["ok"]
        [period] = api.get_state()["securities"][0]["_cycles"]
        exit_ = period["exit"]
        assert exit_["reconstructed"] == 1
        by_reason = {r["reason"]: r for r in exit_["reasons"]}
        assert by_reason["Risk limit"]["reconstructed"] == 1
        assert by_reason["Panic"]["reconstructed"] == 0
        # The weighted price names which slivers were rebuilt, because the
        # record is written once and cannot be asked afterwards.
        assert any("reconstructed" in line
                   for line in exit_["price"]["provenance"])


# -- the third thing that judged the past with the present -------------------

class TestWhatTheJournalKnewOnADay:
    def test_an_answer_is_read_back_to_the_day_it_was_true(self, api):
        """Free cash was served from today's answer under any pin, with a
        caution admitting it carried no date. It does carry one — every
        change to it is on the journal's own append-only record — and the
        caution was the wrong fix: the account is built from this and every
        weight is measured against the account."""
        open_since("2019-01-01")
        assert api.save_journal_settings({"free-cash": "9000"})["ok"]
        doc = journal()
        assert doc["input_changes"], "a change to an answer is recorded"
        doc["input_changes"][-1]["seen"] = "2026-05-01T12:00:00+00:00"
        journals.save(doc)

        assert journals.answers_on(doc, None)["free-cash"] == 9000.0
        assert journals.answers_on(doc, "2026-08-09")["free-cash"] == 9000.0
        # Before the change, the answer was the one the journal was created
        # with, and that is what a decision made then was measured against.
        assert journals.answers_on(doc, "2026-04-30")["free-cash"] == 40000.0
        # A change made ON the day counts as in force, the rule every dated
        # record in this program obeys.
        assert journals.answers_on(doc, "2026-05-01")["free-cash"] == 9000.0

    def test_a_day_before_the_journal_existed_has_no_answers_at_all(self,
                                                                    api):
        doc = journal()
        assert journals.answers_on(doc, "2011-01-04") is None
        assert journals.answers_on(doc, doc["created"][:10]) is not None

    def test_and_the_absence_reaches_the_weight_a_rule_binds_on(self, api):
        """Not a caution beside a present-day balance. A qualified wrong
        number still decides."""
        tracked(api, cik=889)
        assert api.open_position("SYN", 100, 10.0, "2011-01-04")["ok"]
        lot = security()["lots"][0]
        assert lot["unreconstructed"], \
            "with no answers there is nothing to size against, so nothing " \
            "to reconstruct"
        assert "created on" in lot["unreconstructed"]["note"]

    def test_the_note_admits_the_rules_are_the_present_ones(self, api):
        """The one part of a reconstruction that genuinely does judge the
        past with the present, and it cannot be fixed — the version in force
        in 2019 is not on this machine. So it is said, in as many words, in a
        record written once."""
        open_since("2019-01-01")
        tracked(api, cik=890)
        note = api.preview_purchase("SYN", "2026-06-01")["note"]
        assert "as it stands today" in note
        assert "only the data is of the day" in note


# -- entering a whole position ------------------------------------------------

class TestEnteringAPositionFromHistory:
    def test_a_preview_writes_nothing_and_a_record_writes_all_of_it(self,
                                                                    api):
        tracked(api, cik=891)
        checked = api.preview_backfill("SYN", HISTORY)
        assert checked["ok"] and checked["problem"] is None
        assert checked["recorded"] is False
        assert security()["lots"] == [], "a preview must not touch the record"
        assert len(checked["events"]) == 3
        assert checked["shares_after"] == 100.0

        done = api.record_backfill("SYN", HISTORY)
        assert done["ok"] and done["recorded"] is True
        lots = security()["lots"]
        assert [l["kind"] for l in lots] == ["buy", "buy", "sell"]
        assert portfolio.shares_held(security()) == 100.0

    def test_every_entry_is_judged_against_its_own_day(self, api):
        tracked(api, cik=892)
        got = api.preview_backfill("SYN", HISTORY)
        assert [e["as_of"] for e in got["events"]] == \
            ["2019-03-12", "2022-05-04", "2024-09-10"]
        assert all(e["basis"] == "reconstructed" for e in got["events"])

    def test_entries_are_applied_oldest_first_whatever_order_they_arrive(
            self, api):
        """Each is judged against the position the ones before it leave
        behind, so a sale typed above the purchase it draws on still has to
        be checked against it."""
        tracked(api, cik=893)
        assert api.record_backfill("SYN", list(reversed(HISTORY)))["ok"]
        assert [l["date"] for l in security()["lots"]] == \
            ["2019-03-12", "2022-05-04", "2024-09-10"]

    def test_a_run_that_cannot_be_recorded_records_none_of_it(self, api):
        """Not "three landed and the fourth was refused". An append-only
        record has no way to take an entry back, so a half-applied run is a
        state that has to be unreachable rather than one to recover from."""
        tracked(api, cik=894)
        too_much = HISTORY + [
            {"kind": "sell", "date": "2025-01-05", "shares": 500,
             "price": 20.0, "reason": "Panic"}]
        got = api.record_backfill("SYN", too_much)
        assert got["ok"] and got["recorded"] is False
        assert got["problem"], "a refusal that says nothing cannot be fixed"
        assert security()["lots"] == []

    def test_it_stops_at_the_first_problem_and_says_what_it_did_not_check(
            self, api):
        tracked(api, cik=895)
        broken = [
            {"kind": "buy", "date": "2019-03-12", "shares": 10,
             "price": 10.0},
            {"kind": "sell", "date": "2020-01-05", "shares": 90,
             "price": 20.0, "reason": "Panic"},
            {"kind": "buy", "date": "2021-01-05", "shares": 10,
             "price": 10.0},
        ]
        got = api.preview_backfill("SYN", broken)
        assert got["problem"]
        assert got["events"][-1]["problem"] == got["problem"]
        assert got["unchecked"] == [2], \
            "an entry judged against a position missing a purchase would be " \
            "wrong in a way that looks like an answer"

    def test_a_run_that_opens_with_a_sale_is_refused_by_name(self, api):
        tracked(api, cik=896)
        got = api.preview_backfill("SYN", [HISTORY[2]])
        assert got["ok"] is False
        assert "built from the purchase up" in got["error"]

    def test_a_row_missing_a_number_names_the_row(self, api):
        tracked(api, cik=897)
        got = api.preview_backfill(
            "SYN", [{"kind": "buy", "date": "2019-03-12", "shares": "",
                     "price": "10"}])
        assert got["ok"] is False and "Entry 1" in got["error"]

    def test_a_sale_may_honestly_have_no_reason(self, api):
        """Forcing a pick from the list would manufacture the one fact the
        exit analytics exist to read. "I do not remember why I sold in 2014"
        is the truth, and counting it is itself the finding."""
        tracked(api, cik=898)
        assert api.record_backfill("SYN", [
            HISTORY[0],
            {"kind": "sell", "date": "2020-01-05", "shares": 100,
             "price": 20.0, "reason": ""}])["ok"]
        assert portfolio.lots(security(), "sell")[0]["reason"] == \
            portfolio.UNSTATED_REASON
        assert portfolio.UNSTATED_REASON in api.get_state()["exit_scorecard"]

    def test_a_whole_journey_lands_including_a_re_entry(self, api):
        """Someone's real history is not one buy. Purchase, add, trim, exit
        and back in — and the re-entry has to read as a second holding
        period rather than as a resumption of the first."""
        tracked(api, cik=899)
        assert api.record_backfill("SYN", HISTORY + [
            {"kind": "sell", "date": "2025-02-03", "shares": 100,
             "price": 28.0, "reason": "Thesis broke"},
            {"kind": "buy", "date": "2025-11-20", "shares": 30,
             "price": 22.0}])["ok"]
        s = api.get_state()["securities"][0]
        assert s["bucket"] == "holdings"
        assert len(s["_cycles"]) == 2
        assert s["_cycles"][0]["closed"] == "2025-02-03"
        assert s["_cycles"][1]["opened"] == "2025-11-20"

    def test_the_whole_run_is_narrated_once_not_once_an_entry(self, api):
        """Five near-identical notes stamped today, above every note the user
        actually wrote, is how the Journal panel stops being read."""
        tracked(api, cik=900)
        assert api.record_backfill("SYN", HISTORY)["ok"]
        notes = security()["notes"]
        assert len(notes) == 1, [n["text"] for n in notes]
        assert "2019-03-12 to 2024-09-10" in notes[0]["text"]
        assert "2 purchases, 1 sale" in notes[0]["text"]


# -- the hindsight surface ----------------------------------------------------

class TestARecollectionIsNeverAThesis:
    def test_it_attaches_to_the_first_purchase_and_says_when_it_was_written(
            self, api):
        tracked(api, cik=901)
        assert api.record_backfill(
            "SYN", HISTORY, "I bought it for the buyback and forgot about "
                            "it for five years.")["ok"]
        buys = portfolio.lots(security(), "buy")
        first = buys[0]["snapshot"]["recollection"]
        assert first["text"].startswith("I bought it")
        assert first["written"][:10] == date.today().isoformat(), \
            "written now, about then — and the record says which is which"
        assert buys[1]["snapshot"]["recollection"] is None, \
            "remembering the reasoning for each of six adds is not a thing " \
            "anybody can honestly do"

    def test_it_never_occupies_the_slot_the_thesis_is_read_from(self, api):
        tracked(api, cik=902)
        assert api.record_backfill("SYN", HISTORY[:1], "I remember why.")["ok"]
        snap = portfolio.lots(security(), "buy")[0]["snapshot"]
        assert snap["thesis"] is None
        assert snap["recollection"]["text"] == "I remember why."

    def test_it_is_refused_outright_on_an_entry_recorded_today(self, api):
        """The one place hindsight is allowed in, and the boundary is a
        refusal rather than a convention: a prose field that could reach a
        live purchase would be a second, undated, unamendable thesis sitting
        where the first one belongs."""
        tracked(api, cik=903)
        got = api.record_backfill(
            "SYN", [{"kind": "buy", "date": date.today().isoformat(),
                     "shares": 10, "price": 10.0}],
            "I am thinking this right now.")
        assert got["recorded"] is False
        assert "write a thesis" in got["problem"], got["problem"]
        assert security()["lots"] == []


# -- and it is visible, everywhere -------------------------------------------

class TestAReconstructionNeverPassesForARecord:
    def test_the_security_says_so_without_anything_walking_its_lots(self,
                                                                    api):
        tracked(api, cik=904)
        assert api.record_backfill("SYN", HISTORY)["ok"]
        s = api.get_state()["securities"][0]
        assert s["_backfilled"] is True
        assert portfolio.backfilled(security()) is True

    def test_a_journal_with_nothing_typed_in_says_that_too(self, api):
        open_since("2019-01-01")
        tracked(api, cik=905)
        assert api.open_position("SYN", 10, 10.0,
                                 date.today().isoformat())["ok"]
        assert api.get_state()["securities"][0]["_backfilled"] is False

    def test_every_entry_carries_it_on_its_own_frozen_record(self, api):
        tracked(api, cik=906)
        assert api.record_backfill("SYN", HISTORY)["ok"]
        for lot in security()["lots"]:
            assert lot["snapshot"]["evaluation"]["basis"] == "reconstructed"
            assert portfolio.is_reconstructed(lot)
