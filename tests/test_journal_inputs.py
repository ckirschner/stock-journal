"""What a journal tells its strategy, and how it changes.

Two guarantees here, and both fail silently if they break.

The first is that a journal cannot become a trap. A strategy version that
adds a required input blocks every journal stamped with it; if the answer can
only be given at creation, the user's journal is dead and the app says
nothing except "Waiting on setup". So answers are editable afterwards, and
the blocked state resolves by supplying what is owed.

The second is that the two kinds of edit are recorded differently, because
the host can honestly say different things about them. Changing what the
strategy demands is a rule change and is owed a written reason. Changing what
you told it about your account is a fact update and is owed nothing — but it
is still on a record, because those answers now feed figures a strategy binds
on, and an answer that could be quietly adjusted the day before a purchase is
worth being able to see afterwards.
"""

import pytest
from conftest import balance_face, dur, filing, inst

from engine import facts_store, journals, price_store

from app import Api

ANSWERS = {"stance": "building", "keeps-reserve": "false", "first-buy": "4"}
OPENING_CASH = 40000.0


@pytest.fixture
def api(strategies):
    strategies("awkward")
    return Api()


def journal():
    return journals.load(journals.resolve_open())


def make(api, name="Sized", answers=None, cash=OPENING_CASH):
    """Create the journal, and open its cash record at the setup figure.

    Free cash is not an answer any more — it is worked out from the record —
    so the setup figure opens that record rather than being stored. Passed on
    the same call, because that is what the quick-start flow does.
    """
    r = api.create_journal(name, "awkward",
                           dict(ANSWERS if answers is None else answers),
                           opening_cash=cash)
    assert r["ok"], r
    assert not r.get("cash_problem"), r.get("cash_problem")
    return r


def spend(api, amount, when=None):
    """Take money out of the account. What free cash is now follows from it,
    which is the only way the figure moves."""
    r = api.record_cash("withdrawal", amount, when)
    assert r["ok"], r.get("error")
    return r


def company(cik=771, ticker="SYN", close=20.0):
    """One filed year and one close, so a holding has a market value and the
    account arithmetic has something to add up."""
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


def hold(api, ticker="SYN", shares=10, cost=15.0, cik=None):
    api.add_security(ticker, "Synthetic Co")
    if cik:
        doc = journal()
        next(s for s in doc["securities"] if s["ticker"] == ticker)["cik"] = cik
        journals.save(doc)
    assert api.open_position(ticker, shares, cost, None, "recording")["ok"]


def decision_for(state, ticker="SYN"):
    return next(s for s in state["securities"]
                if s["ticker"] == ticker)["_decision"]


def decision_for_any(state):
    """The verdict on whatever the journal holds. Some of what is checked
    here blocks every security identically, so the first one will do."""
    return state["securities"][0]["_decision"]


class TestSetupCollectsWhatIsDeclared:
    def test_a_journal_holds_the_answers_it_was_created_with(self, api):
        make(api)
        assert journal()["inputs"] == {
            "stance": "building", "keeps-reserve": False, "first-buy": 4.0}

    def test_the_cash_at_setup_opens_a_record_rather_than_being_stored(self,
                                                                       api):
        """The figure somebody types at setup is day one of a ledger, not an
        answer sitting in a slot. A stored copy beside the derived balance
        would be two numbers about one thing."""
        from engine import cash
        make(api)
        doc = journal()
        assert "free-cash" not in doc["inputs"]
        assert cash.opening(doc)["amount"] == 40000.0
        assert cash.balance(doc)["value"] == 40000.0

    def test_the_answers_travel_in_an_export(self, api, tmp_path):
        """They live inside the journal, so the exportable set carries them
        without any field having to remember to."""
        from engine import backup
        make(api)
        path = backup.export_bundle(tmp_path)
        import json
        bundle = json.loads(path.read_text())
        assert bundle["journals"][0]["inputs"]["stance"] == "building"
        # And the cash record with them: it lives inside the journal, so the
        # exportable set carries it without any field having to remember to.
        [opened] = bundle["journals"][0]["cash_record"]
        assert opened["kind"] == "opening" and opened["amount"] == 40000.0

    def test_a_missing_required_answer_refuses_creation_by_name(self, api):
        answers = dict(ANSWERS)
        answers.pop("stance")
        r = api.create_journal("No stance", "awkward", answers)
        assert r["ok"] is False
        assert "How you are trading right now" in r["error"]

    def test_a_gated_off_answer_is_never_demanded_at_creation(self, api):
        """"Cash you keep back" is required, and irrelevant until you say
        you keep cash back. A form that demanded it anyway would be asking
        for a number that cannot mean anything."""
        assert api.create_journal("No reserve", "awkward", ANSWERS)["ok"]

    def test_a_gate_turned_on_makes_its_field_owed(self, api):
        answers = dict(ANSWERS, **{"keeps-reserve": "true"})
        r = api.create_journal("Reserved", "awkward", answers)
        assert r["ok"] is False
        assert "Cash you keep back" in r["error"]

    def test_a_bound_that_names_a_declared_value_is_enforced(self, api):
        """The cap is a setting the strategy ships; the first-buy size is an
        answer measured against it."""
        r = api.create_journal("Too big", "awkward",
                               dict(ANSWERS, **{"first-buy": "50"}))
        assert r["ok"] is False
        assert "at most your Largest a position may get (8)" in r["error"]

    def test_an_answer_outside_the_offered_choices_is_refused(self, api):
        r = api.create_journal("Odd", "awkward",
                               dict(ANSWERS, **{"stance": "sideways"}))
        assert r["ok"] is False
        assert "must be one of" in r["error"]


class TestTheJournalStopsBeingATrap:
    def test_a_strategy_that_gains_a_required_input_can_be_answered(self, api):
        """The dead end this exists to remove: a journal blocked on a field
        the setup screen has already been past."""
        make(api)
        hold(api, cik=company())
        doc = journal()
        doc["inputs"].pop("stance")
        journals.save(doc)

        blocked = decision_for(api.get_state())
        assert blocked["state"]["id"] == "host:inputs-missing"
        assert blocked["state"]["fix"] == "settings"

        assert api.save_journal_settings({"stance": "building"}, None)["ok"]
        assert decision_for(api.get_state())["produced_by"] == "strategy"

    def test_naming_one_answer_never_deletes_the_others(self, api):
        """A partial payload that replaced the whole set would silently
        empty a journal, and the next screen would say the strategy needs
        setting up again."""
        make(api)
        assert api.save_journal_settings({"first-buy": "6"}, None)["ok"]
        assert journal()["inputs"]["stance"] == "building"
        assert journal()["inputs"]["first-buy"] == 6.0

    def test_a_blank_answer_clears_it_rather_than_storing_a_zero(self, api):
        make(api)
        assert api.save_journal_settings({"first-buy": ""}, None)["ok"]
        assert "first-buy" not in journal()["inputs"]

    def test_a_rejected_edit_leaves_the_journal_exactly_as_it_was(self, api):
        make(api)
        before = dict(journal()["inputs"])
        r = api.save_journal_settings({"first-buy": "not a number"}, None)
        assert r["ok"] is False
        assert journal()["inputs"] == before

    def test_a_figure_the_host_derives_cannot_be_typed_into_settings(self):
        """Not silently dropped — the screen says where the number comes
        from. A form that accepted it and did nothing would leave somebody
        certain they had changed their balance."""
        from engine import contract
        strategies, _ = None, None
        rec = {"name": "F", "inputs": [
            {"id": "free-cash", "label": "Free cash", "type": "number",
             "unit": "usd", "role": "cash", "explain": "e"}]}
        _, problems = contract.check_inputs(rec, {"free-cash": 5.0})
        assert any("does not answer it" in p for p in problems), problems

    def test_saving_clears_a_setting_the_strategy_no_longer_declares(self,
                                                                     api):
        """A leftover override refuses to resolve, which blocks every
        verdict — and the screen the block sends you to has to be able to
        fix it, or the way out is a dead end too."""
        make(api)
        hold(api, cik=company())
        doc = journal()
        doc["config"]["gone"] = 3
        doc["inputs"]["also-gone"] = "x"
        journals.save(doc)
        assert decision_for_any(api.get_state())["state"]["id"] == \
            "host:values-unresolved"

        assert api.save_journal_settings({}, {})["ok"]
        after = journal()
        assert after["config"] == {} and "also-gone" not in after["inputs"]
        assert after["inputs"]["stance"] == "building"     # nothing else went
        assert decision_for_any(api.get_state())["produced_by"] == "strategy"

    def test_a_config_edit_that_would_break_an_answer_is_refused_whole(self,
                                                                      api):
        """Lowering the cap under an answer that is bounded by it must fail
        before either is written — half-applied settings would leave the
        journal refusing every verdict over a number the user was fixing."""
        make(api)
        r = api.save_journal_settings(None, {"cap": "2"})
        assert r["ok"] is False
        assert "at most your Largest a position may get (2)" in r["error"]
        assert journal()["config"] == {}
        assert journal()["rule_changes"] == []


class TestTheTwoRecords:
    def test_a_config_edit_lands_on_the_rule_change_record_and_owes_why(
            self, api):
        make(api)
        r = api.save_journal_settings(None, {"cap": "12"})
        assert r["ok"] and r["pending"] == 1
        [change] = journal()["rule_changes"]
        assert change["kind"] == "settings"
        assert change["moved"] == [{"id": "cap",
                                    "label": "Largest a position may get",
                                    "from": 8, "to": 12.0}]
        assert change["reason_owed"] is True
        assert journal()["input_changes"] == []

    def test_an_answer_edit_lands_on_its_own_record_and_owes_nothing(self,
                                                                     api):
        """An answer is a fact about the account, not a rule. Asking someone
        to justify their cash balance changing would train them to ignore
        the record that does matter."""
        make(api)
        assert api.save_journal_settings({"first-buy": "6"}, None)["ok"]
        assert journal()["rule_changes"] == []
        [change] = journal()["input_changes"]
        assert change["moved"] == [{"id": "first-buy",
                                    "label": "Size of a first position",
                                    "from": 4.0, "to": 6.0}]
        assert "reason_owed" not in change
        assert journals.pending(journal()) == []

    def test_cash_moving_owes_nothing_and_is_its_own_record(self, api):
        """Money arriving is not a change to what the rules demand and not an
        edit to an answer either. It is an event, and it goes where events
        go."""
        make(api)
        assert api.record_cash("deposit", 5_000, None, "pay day")["ok"]
        doc = journal()
        assert doc["rule_changes"] == [] and doc["input_changes"] == []
        assert [e["kind"] for e in doc["cash_record"]] == ["opening",
                                                           "deposit"]
        assert journals.pending(doc) == []

    def test_an_edit_that_moves_nothing_records_nothing(self, api):
        make(api)
        assert api.save_journal_settings(dict(ANSWERS), {"cap": "8"})["ok"]
        assert journal()["input_changes"] == []
        assert journal()["rule_changes"] == []

    def test_both_records_are_append_only(self, api):
        make(api)
        api.save_journal_settings({"first-buy": "6"}, {"cap": "12"})
        first = [dict(c) for c in journal()["input_changes"]]
        api.save_journal_settings({"first-buy": "7"}, {"cap": "14"})
        after = journal()
        assert [dict(c) for c in after["input_changes"][:1]] == first
        assert [c["seq"] for c in after["input_changes"]] == [1, 2]
        assert [c["seq"] for c in after["rule_changes"]] == [1, 2]

    def test_a_frozen_verdict_is_not_rewritten_when_the_answer_moves(self,
                                                                     api):
        """The purchase keeps the figures it was actually judged on. If the
        snapshot followed the current answer, editing cash would rewrite
        history — which is the whole reason the answer record exists."""
        def figure(decision, fact):
            return next(e["observed"]["value"]
                        for e in decision["reason"]["evidence"]
                        if e["subject"]["id"] == fact)

        make(api)
        hold(api, cik=company())      # 10 shares at 15, priced at 20
        frozen = journal()["securities"][0]["lots"][0]["snapshot"]["decision"]
        # The purchase itself is netted off the cash the moment it is
        # recorded, so what was frozen is the balance BEFORE it: 40,000. The
        # figure the verdict was computed against is what the record says, not
        # a number that stopped moving.
        assert figure(frozen, "portfolio.cash") == 40000.0

        spend(api, 39_000)
        again = journal()["securities"][0]["lots"][0]["snapshot"]["decision"]
        assert figure(again, "portfolio.cash") == 40000.0
        # ...while today's verdict does move, which is the point. 40,000 less
        # the 150 the shares cost less the 39,000 withdrawn is 850, plus 200
        # of stock.
        assert figure(decision_for(api.get_state()),
                      "portfolio.account_value") == 1050.0


class TestSizeBindingWorksEndToEnd:
    def test_a_strategy_that_binds_on_weight_reaches_a_verdict(self, api):
        make(api)
        hold(api, shares=10, cost=15.0, cik=company(close=20.0))
        d = decision_for(api.get_state())
        assert d["produced_by"] == "strategy"
        cited = {e["subject"]["id"]: e for e in d["reason"]["evidence"]}
        # 200 of stock, and cash of 40,000 less the 150 the shares cost — the
        # money that went into the position is not still sitting in cash.
        assert cited["portfolio.account_value"]["observed"]["value"] == 40050.0
        assert round(cited["position.weight"]["observed"]["value"], 6) == \
            round(200 / 40050 * 100, 6)
        assert cited["position.weight"]["outcome"] == "pass"

    def test_crossing_the_cap_moves_the_state_not_just_the_number(self, api):
        """The verdict has to actually turn on the figure, or none of this
        was worth building."""
        make(api, cash=100.0)
        hold(api, shares=100, cost=15.0, cik=company(close=20.0))
        d = decision_for(api.get_state())
        assert d["render"] == "reduce"
        assert d["payload"]["to"] == {"unit": "weight", "value": 8.0}

    def test_without_a_cash_record_the_same_strategy_cannot_say(self, api):
        """No opening balance means no account total, so a rule about a share
        of the account has nothing to read — and says so, rather than sizing
        against a zero nobody stated."""
        make(api, cash=None)
        hold(api, shares=10, cost=15.0, cik=company(close=20.0))
        d = decision_for(api.get_state())
        assert d["render"] == "unknown"
        cited = {e["subject"]["id"]: e for e in d["reason"]["evidence"]}
        assert cited["portfolio.cash"]["observed"]["status"] == "absent"
        assert "opening balance" in \
            cited["portfolio.cash"]["observed"]["reason"]

    def test_the_host_never_says_whether_a_weight_is_too_high(self, api):
        """The host reports the figure. Which side of a line it should sit
        on is the strategy's opinion, and the limit on the record names the
        setting it came from — and is read out of it, not supplied."""
        make(api)
        hold(api, cik=company())
        cited = {e["subject"]["id"]: e for e in
                 decision_for(api.get_state())["reason"]["evidence"]}
        test = cited["position.weight"]["test"]
        assert test["threshold_from"] == {"kind": "value", "id": "cap",
                                          "label": "Largest a position may "
                                                   "get", "unit": "percent"}
        assert test["threshold"] == journal()["strategy"]["values"]["cap"]

    def test_retuning_the_setting_moves_the_limit_on_the_record(self, api):
        """The attribution is only worth anything if it is true. Change the
        cap and the limit the reason states changes with it, because the
        strategy never held a copy of the number to go stale."""
        make(api)
        hold(api, cik=company())

        def limit():
            cited = {e["subject"]["id"]: e for e in
                     decision_for(api.get_state())["reason"]["evidence"]}
            return cited["position.weight"]["test"]["threshold"]

        before = limit()
        assert api.save_journal_settings(None, {"cap": str(before + 7)})["ok"]
        assert limit() == before + 7
