"""Judgements — the questions no filing answers, answered per security.

Everything here fails silently if it breaks. A judgement that renders as a
measurement is a number the reader trusts more than they should; an
unanswered one that reads as a pass is a rule that stopped applying with
nothing on screen saying so; an assessment that can be quietly rewritten
before it fires makes every override record measured against it worthless;
and an opinion formed today reaching backwards into a purchase made in 2024
is the journal claiming a verdict it never computed.

Driven through the real Api wherever the guarantee spans both sides, because
several of these were only ever visible from one end.
"""

import pytest
from conftest import balance_face, dur, filing, inst, open_since

from engine import contract, dataview, facts_store, journals, judgements
from engine import price_store

from app import Api

MOAT = "moat_durability"
ANSWERS = {"free-cash": "40000", "stance": "building",
           "keeps-reserve": "false", "first-buy": "4"}


@pytest.fixture
def api(strategies):
    strategies("awkward")
    a = Api()
    assert a.create_journal("Judged", "awkward", dict(ANSWERS))["ok"]
    return a


def journal():
    return journals.load(journals.resolve_open())


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


def hold(api, ticker="SYN", shares=10, cost=15.0, when=None):
    cik = company()
    api.add_security(ticker, "Synthetic Co")
    doc = journal()
    next(s for s in doc["securities"] if s["ticker"] == ticker)["cik"] = cik
    journals.save(doc)
    assert api.open_position(ticker, shares, cost, when, "recording")["ok"]


def held(state, ticker="SYN"):
    return next(s for s in state["securities"] if s["ticker"] == ticker)


def cited(state, ticker="SYN"):
    d = held(state, ticker)["_decision"]
    return {e["subject"]["id"]: e for e in d["reason"]["evidence"]}


def security():
    return journal()["securities"][0]


class TestTheQuestionLivesWithItsDefinition:
    def test_the_questions_are_the_banks_own_qualitative_entries(self):
        """No second place a question can be defined. A strategy asking about
        a moat asks the bank's question, so two strategies cannot ask the
        same thing differently and the explanation someone needs in order to
        answer is already written beside it."""
        from engine import bank
        expected = {str(e["id"]) for e in bank.load_bank()["entries"]
                    if str(e.get("kind") or "") == "qualitative"}
        assert set(judgements.questions()) == expected
        assert expected, "the bank ships no qualitative entries to answer"

    def test_every_question_carries_what_is_needed_to_answer_it(self):
        for eid, q in judgements.questions().items():
            assert q["question"], f"{eid} asks nothing"
            assert q["plain"], f"{eid} has no plain-language explanation"
            assert q["marks"] == list(judgements.MARKS)

    def test_a_question_the_host_cannot_serve_shows_no_answer_either(self,
                                                                     api,
                                                                     monkeypatch):
        """The screen and the strategy must not disagree about the same
        fact. Where the host cannot serve the question, the strategy is told
        the measure is absent — so the page reports no mark either, rather
        than a confident "Passed" beside a verdict that says it cannot say.
        The record itself is untouched and still readable."""
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")
        monkeypatch.setattr(judgements, "unanswerable",
                            lambda entry: "this journal cannot record that")

        row = next(j for j in held(api.get_state())["_judgements"]
                   if j["id"] == MOAT)
        assert row["unsupported"]
        assert (row["mark"], row["reasoning"], row["recorded"]) == \
            (None, None, None)
        assert cited(api.get_state())[MOAT]["observed"]["status"] == "absent"
        # …and nothing was destroyed: the assessment is still on the record.
        assert [a["mark"] for a in row["history"]] == ["pass"]
        assert security()["judgements"][0]["reasoning"] == "It holds."

    def test_a_mark_shape_this_host_cannot_store_is_refused_not_guessed(self):
        entry = {"id": "scored", "label": "Scored",
                 "response": {"marks": ["one", "two", "three"]}}
        why = judgements.unanswerable(entry)
        assert why and "change to the host" in why
        # …and it reports absent rather than being stored in a shape nothing
        # can read back.
        obs = judgements.observation({}, "scored", entry)
        assert obs["status"] == "absent"
        assert obs["reason"] == why


class TestAnsweringOne:
    def test_a_mark_and_its_reasoning_are_recorded_together(self, api):
        hold(api)
        r = api.record_judgement("SYN", MOAT, "pass", "Brand nobody switches.")
        assert r["ok"], r
        [entry] = security()["judgements"]
        assert entry["id"] == MOAT and entry["mark"] == "pass"
        assert entry["reasoning"] == "Brand nobody switches."
        assert entry["recorded"]

    def test_a_mark_with_nothing_behind_it_is_refused(self, api):
        hold(api)
        r = api.record_judgement("SYN", MOAT, "pass", "   ")
        assert r["ok"] is False
        assert "reasoning" in r["error"]
        assert security().get("judgements") in (None, [])

    def test_only_pass_or_fail_and_never_a_third_answer(self, api):
        hold(api)
        r = api.record_judgement("SYN", MOAT, "maybe", "Not sure.")
        assert r["ok"] is False
        assert "unmarked is not a third answer" in r["error"]

    def test_a_question_the_bank_does_not_ask_is_refused(self, api):
        hold(api)
        r = api.record_judgement("SYN", "roic_median_5y", "pass", "Because.")
        assert r["ok"] is False
        assert "not a question in the metric bank" in r["error"]


class TestItIsAJudgementAndNeverAMeasurement:
    def test_a_number_can_never_be_stored_where_a_judgement_belongs(self,
                                                                    api):
        """float(True) is 1.0, so the hand-entered values field would have
        taken a moat read and served it as a computed-looking number. Refused
        at the write, because the dialog that does not offer it is a view and
        a view is not a guarantee."""
        hold(api)
        r = api.save_metrics("SYN", {MOAT: 1}, None)
        assert r["ok"] is False
        assert "judgement you make" in r["error"]
        assert not [e for e in (security().get("hand_entered") or [])
                    if e["id"] == MOAT]

    def test_a_number_left_behind_by_an_older_journal_is_still_ignored(self,
                                                                       api):
        """A journal written before that refusal existed must not still read
        as an assessment. The read skips it too, so the guarantee does not
        rest on every past write having been checked."""
        hold(api)
        doc = journal()
        # Planted straight onto the dated record, going round the write that
        # would refuse it — which is exactly what an older journal on disk
        # amounts to.
        doc["securities"][0].setdefault("hand_entered", []).append(
            {"seq": 1, "id": MOAT, "value": 1.0,
             "recorded": "2020-01-01T00:00:00+00:00"})
        journals.save(doc)
        state = api.get_state()
        moat = cited(state)[MOAT]["observed"]
        assert moat["status"] == "absent"
        assert dataview.merged_values(security(), {}).get(MOAT) is None

    def test_the_host_decides_it_is_a_judgement_not_the_strategy(self, api):
        """A strategy cites a judgement exactly as it cites any measure. What
        it IS comes from the bank, so a strategy cannot present an assessment
        as something the tool worked out."""
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "Switching costs.")
        item = cited(api.get_state())[MOAT]
        assert item["subject"]["kind"] == "judgement"
        assert item["subject"]["unit"] == "yes_no"
        assert item["subject"]["explain"], "the question does not travel"

    def test_the_reasoning_travels_with_the_mark(self, api):
        """The mark on its own is a bare yes. What makes it worth reading
        back is why — so the reasoning travels with the figure rather than
        living on a screen the record cannot reach."""
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "Switching costs.")
        obs = cited(api.get_state())[MOAT]["observed"]
        assert obs["value"] is True
        assert any("Switching costs." in p for p in obs["provenance"])
        assert any("your assessment of" in p for p in obs["provenance"])


class TestAbsenceIsNeverAPass:
    def test_unanswered_is_absent_with_a_reason(self, api):
        hold(api)
        item = cited(api.get_state())[MOAT]
        assert item["observed"]["status"] == "absent"
        assert "nothing is recorded" in item["observed"]["reason"]

    def test_an_unanswered_judgement_can_never_come_out_as_a_pass(self, api):
        hold(api)
        item = cited(api.get_state())[MOAT]
        assert item["outcome"] == "unknown"

    def test_a_mark_decides_the_outcome_and_the_verdict(self, api):
        """End to end: the user's own assessment reaches a state. Nothing
        else about the position changes between these two."""
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")
        assert cited(api.get_state())[MOAT]["outcome"] == "pass"
        first = held(api.get_state())["_decision"]["state"]["id"]

        assert api.record_judgement("SYN", MOAT, "fail", "Two rivals now.")
        state = api.get_state()
        assert cited(state)[MOAT]["outcome"] == "fail"
        assert held(state)["_decision"]["state"]["id"] == "size-down"
        assert held(state)["_decision"]["reason"]["rule"] == \
            "moat-you-marked-broken"
        assert first != "size-down"


class TestTheRecordIsAppendOnly:
    def test_changing_your_mind_appends_and_never_edits(self, api):
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")
        assert api.record_judgement("SYN", MOAT, "fail", "It stopped.")
        log = security()["judgements"]
        assert [a["mark"] for a in log] == ["pass", "fail"]
        assert log[0]["reasoning"] == "It holds."
        assert [a["seq"] for a in log] == [1, 2]

    def test_the_newest_answer_is_the_one_in_force(self, api):
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")
        assert api.record_judgement("SYN", MOAT, "fail", "It stopped.")
        assert judgements.in_force(security(), MOAT)["mark"] == "fail"
        assert [a["mark"] for a in judgements.history(security(), MOAT)] == \
            ["fail", "pass"]

    def test_every_earlier_answer_reaches_the_screen(self, api):
        """The point of keeping them is reading them. An opinion that flipped
        a fortnight before a purchase is the most diagnostic thing here and
        is invisible if only the newest renders."""
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")
        assert api.record_judgement("SYN", MOAT, "fail", "It stopped.")
        view = next(j for j in held(api.get_state())["_judgements"]
                    if j["id"] == MOAT)
        assert view["mark"] == "fail"
        assert [a["mark"] for a in view["history"]] == ["fail", "pass"]

    def test_the_whole_record_survives_an_export_and_an_import(self, api,
                                                               tmp_path):
        """Your own reasoning, written down once and worth reading years
        later, has to be in a backup — including the assessments you
        changed your mind about, which is the half a summary would drop."""
        from engine import backup
        hold(api)
        assert api.record_judgement("SYN", MOAT, "fail", "It broke.")
        assert api.record_judgement("SYN", MOAT, "pass", "Rebuilt since.")
        before = security()["judgements"]

        path = backup.export_bundle(tmp_path)
        import json
        bundle = json.loads(path.read_text())
        [sec] = bundle["journals"][0]["securities"]
        assert sec["judgements"] == before

        backup.import_bundle(path)
        assert security()["judgements"] == before

    def test_a_frozen_purchase_keeps_the_assessment_it_was_made_on(self, api):
        """The snapshot is written once and never recomputed, so an
        assessment revised afterwards must not reach back into it."""
        hold(api)
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")
        assert api.open_position("SYN", 5, 21.0, None, "adding")["ok"]
        assert api.record_judgement("SYN", MOAT, "fail", "It stopped.")

        lot = security()["lots"][-1]
        frozen = lot["snapshot"]["metrics"][MOAT]
        assert frozen["value"] is True
        assert any("It holds." in p for p in frozen["provenance"])
        assert frozen["source"] == "judgement"


class TestTheClockGovernsIt:
    @staticmethod
    def _pinned(api, day):
        r = api.preview_purchase("SYN", day)
        assert r["ok"], r
        assert r["basis"] == "reconstructed"
        return {e["subject"]["id"]: e
                for e in r["decision"]["reason"]["evidence"]}[MOAT]

    def test_a_backdated_purchase_never_inherits_a_later_opinion(self, api):
        """The hole that hand-entered values still have and this does not: an
        assessment carries the day it was written, so a reconstruction can
        refuse it rather than quietly using today's answer for 2024."""
        open_since("2024-01-01")
        hold(api, when="2024-01-10")
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")

        item = self._pinned(api, "2024-03-02")
        assert item["observed"]["status"] == "absent"
        assert "after 2024-03-02" in item["observed"]["reason"]
        assert item["outcome"] == "unknown"
        # …and the same citation today reads the answer, so this is the clock
        # refusing it rather than the answer being unreadable.
        assert cited(api.get_state())[MOAT]["observed"]["value"] is True

    def test_the_assessment_that_stood_on_the_day_is_the_one_served(self,
                                                                    api):
        open_since("2024-01-01")
        hold(api, when="2024-01-10")
        assert api.record_judgement("SYN", MOAT, "fail", "It broke.")
        assert api.record_judgement("SYN", MOAT, "pass", "Rebuilt since.")
        doc = journal()
        log = doc["securities"][0]["judgements"]
        log[0]["recorded"] = "2024-01-05T00:00:00+00:00"
        log[1]["recorded"] = "2026-06-01T00:00:00+00:00"
        journals.save(doc)

        # On the day, the answer on record was the first one — not the one
        # written two years later, however much better it turned out to be.
        item = self._pinned(api, "2024-03-02")
        assert item["observed"]["value"] is False
        assert item["outcome"] == "fail"
        assert any("It broke." in p for p in item["observed"]["provenance"])
        assert cited(api.get_state())[MOAT]["observed"]["value"] is True

    @staticmethod
    def _assessed_on(day, mark="pass", reasoning="It held."):
        doc = journal()
        s = doc["securities"][0]
        log = s.setdefault("judgements", [])
        log.append({"seq": len(log) + 1, "id": MOAT, "mark": mark,
                    "reasoning": reasoning,
                    "recorded": f"{day}T00:00:00+00:00"})
        journals.save(doc)

    def test_an_assessment_from_a_previous_holding_says_so(self, api):
        """Buying a name back does not renew a judgement written about the
        last time you owned it. It is still served — the user's own opinion
        is the best the journal has — but never as though it were written
        about the holding in front of you."""
        hold(api, when="2025-01-05")
        self._assessed_on("2025-06-01")
        assert api.sell_shares("SYN", "Hit valuation", 22.0, "2025-09-01")["ok"]
        assert api.open_position("SYN", 8, 19.0, "2026-01-05", "back in")["ok"]

        obs = cited(api.get_state())[MOAT]["observed"]
        assert obs["value"] is True
        assert any("closed on 2025-09-01" in c for c in obs["cautions"])

    def test_assessing_before_you_buy_is_never_called_stale(self, api):
        """The whole discipline is committing to the criteria while calm,
        which means writing the assessment before the purchase. Keying
        staleness on "written before this holding opened" would put a
        warning on every correctly-formed assessment there is — and a
        caution that fires when nothing is wrong is one nobody reads."""
        api.add_security("SYN", "Synthetic Co")
        doc = journal()
        doc["securities"][0]["cik"] = company()
        journals.save(doc)
        self._assessed_on("2026-01-01")
        assert api.open_position("SYN", 10, 15.0, "2026-01-05", "in")["ok"]

        assert cited(api.get_state())[MOAT]["observed"]["cautions"] == []

    def test_an_assessment_made_while_flat_belongs_to_the_buy_after_it(self,
                                                                       api):
        """Written between two holdings — sold out, thinking about buying
        back. That is about the holding that followed it, not the one before.
        """
        hold(api, when="2025-01-05")
        assert api.sell_shares("SYN", "Hit valuation", 22.0, "2025-09-01")["ok"]
        self._assessed_on("2025-11-01")
        assert api.open_position("SYN", 8, 19.0, "2026-01-05", "back in")["ok"]

        assert cited(api.get_state())[MOAT]["observed"]["cautions"] == []

    def test_an_assessment_inside_this_holding_is_not_qualified(self, api):
        hold(api, when="2026-01-05")
        assert api.record_judgement("SYN", MOAT, "pass", "It holds.")
        assert cited(api.get_state())[MOAT]["observed"]["cautions"] == []


class TestTheReaderCanAlwaysAnswer:
    def test_the_page_offers_the_questions_the_strategy_asked(self, api):
        hold(api)
        view = held(api.get_state())["_judgements"]
        assert [j["id"] for j in view] == [MOAT]
        assert view[0]["cited"] is True
        assert view[0]["mark"] is None
        assert view[0]["question"] and view[0]["plain"]

    def test_an_answer_stays_visible_after_the_strategy_stops_asking(self,
                                                                     api):
        """A judgement recorded once is not made invisible by a strategy that
        no longer reads it — the same rule hand-entered values follow."""
        api.add_security("IDEA", "Ideaworks")
        assert api.record_judgement("IDEA", MOAT, "pass", "It holds.")
        view = held(api.get_state(), "IDEA")["_judgements"]
        assert [j["id"] for j in view] == [MOAT]
        assert view[0]["cited"] is False

    def test_nothing_is_offered_where_nothing_was_asked_or_answered(self,
                                                                    api):
        """Never the union of every question the bank could ask. Assessing
        the durability of a business your own rules already rejected is the
        overwhelm this program exists to avoid."""
        api.add_security("IDEA", "Ideaworks")
        assert held(api.get_state(), "IDEA")["_judgements"] == []


class TestTheHostHoldsNoViewAboutIt:
    def test_a_strategy_may_block_on_an_unanswered_judgement(self):
        """The other of the two things a strategy may do with an unanswered
        judgement. Nothing in the host decides which is right, and blocking a
        VERDICT is not blocking a decision: the purchase still records, with
        the blocked state captured as the signal it went against."""
        rec = {"id": "x", "name": "X", "summary": "s", "version": 1,
               "contract": contract.CONTRACT_VERSION, "changelog": {1: "f"},
               "inputs": [], "values": [], "defaults": {},
               "states": [{"id": "wait", "name": "Waiting on you",
                           "render": "blocked",
                           "description": "It needs your read."}],
               "dir": "/nowhere",
               "decide": lambda ctx: {
                   "state": "wait",
                   "payload": {"needs": ["Assess the moat."]},
                   "reason": {"rule": "needs-your-read",
                              "summary": "No moat read on record.",
                              "evidence": [{"measure": MOAT}]}}}
        ctx = {"contract": contract.CONTRACT_VERSION, "today": "2026-08-09",
               "inputs": {}, "values": {},
               "measures": {MOAT: {"current": {"status": "absent",
                                               "reason": "not assessed yet"},
                                   "series": {"cadence": None, "points": [],
                                              "note": None,
                                              "truncated": False}}}}
        out = contract.evaluate(rec, ctx)
        assert out["render"] == "blocked"
        assert out["produced_by"] == "strategy"
        # …and the reason names the judgement, which is what the screen turns
        # into a way out of the block.
        [item] = out["reason"]["evidence"]
        assert item["subject"]["kind"] == "judgement"
        assert item["observed"]["status"] == "absent"
