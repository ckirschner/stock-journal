"""Cash as a record of what happened to it.

There was one editable figure for free cash and a dated log of its edits, and
the log could not answer the question the figure existed for. An edit from
50,000 to 60,000 is a deposit or a correction and no reading of that record
can say which — so "how am I doing" was answered by a number that treats
money arriving as money earned.

Four things have to hold, and every one of them fails quietly:

**The balance is derived and never typed.** A stored copy beside the derived
figure is two numbers about one thing, and which gets read is whichever the
next caller reaches for first.

**A dividend is not a deposit.** They both add to the balance and only one of
them is a return. Nothing in the arithmetic reads a kind's name to tell them
apart — each kind declares what it does to the balance and which side of the
account's boundary it came from, and the two sums read one field each.

**An empty record is absent, never zero.** A zero balance understates the
account and inflates every weight measured against it, in the figure sizing
rules bind on.

**The day the money moved governs.** A deposit made in March and typed in
August was in the account in April, and a purchase reconstructed for April is
sized against an account that had it.
"""

import pytest

import conftest
from conftest import journal_for

from engine import cash, contract, context, journals

from app import Api


def doc(opening=50_000.0, opened="2026-01-02", *events):
    return conftest.cash_record(opening, opened, *events)


class TestTheBalanceIsDerived:
    def test_an_opening_balance_is_the_balance(self):
        assert cash.balance(doc())["value"] == 50_000.0

    def test_every_kind_moves_it_the_way_its_own_table_says(self):
        j = doc(50_000.0, "2026-01-02",
                ("deposit", 10_000.0, "2026-02-01"),
                ("withdrawal", 4_000.0, "2026-03-01"),
                ("dividend", 250.0, "2026-04-01"))
        assert cash.balance(j)["value"] == 56_250.0

    def test_the_derivation_is_stated_so_a_reader_can_redo_it(self):
        j = doc(50_000.0, "2026-01-02", ("deposit", 10_000.0, "2026-02-01"))
        said = " ".join(cash.balance(j)["provenance"])
        assert "$50,000.00 opening balance on 2026-01-02" in said
        assert "1 deposit" in said

    def test_the_derivation_pluralises_from_the_table_not_by_adding_an_s(self):
        """"2 dividend receiveds" is what a sentence built by adding a letter
        produces, and this one is read by somebody checking a balance."""
        j = doc(50_000.0, "2026-01-02",
                ("dividend", 10.0, "2026-02-01"),
                ("dividend", 20.0, "2026-03-01"))
        assert "2 dividends received" in \
            " ".join(cash.balance(j)["provenance"])

    def test_a_running_balance_is_derived_per_entry_and_never_stored(self):
        j = doc(50_000.0, "2026-01-02",
                ("deposit", 10_000.0, "2026-02-01"),
                ("withdrawal", 4_000.0, "2026-03-01"))
        rows = cash.ledger(j)
        assert [r["balance"] for r in rows] == [50_000.0, 60_000.0, 56_000.0]
        # Nothing on the stored entry says what the balance was: a stored
        # running total is a second opinion about a fact the entries settle.
        assert all("balance" not in e for e in j[cash.KEY])

    def test_an_entry_is_never_edited_or_removed(self):
        """The substrate refuses a caller its own date, so a correction can
        only ever be a new entry."""
        j = doc()
        with pytest.raises(ValueError, match="set by the journal"):
            from engine import dated
            dated.append(j, cash.KEY, {"kind": "deposit", "amount": 1.0,
                                       "recorded": "2020-01-01T00:00:00"})
        assert not hasattr(cash, "edit") and not hasattr(cash, "delete")


class TestTheTableIsTheEnforcement:
    def test_a_kind_missing_a_field_something_reads_is_refused(self):
        """Not a KeyError inside an arithmetic function months later, on the
        machine of whoever adds the next kind. The shipped table passes it —
        which is the import doing the checking, not this test."""
        cash.check_kinds(cash.KINDS)
        for field in ("label", "plural", "direction", "flow", "means"):
            broken = {"deposit": {k: v for k, v in cash.KINDS["deposit"].items()
                                  if k != field}}
            with pytest.raises(RuntimeError, match="does not declare"):
                cash.check_kinds(broken)

    def test_a_host_answered_role_that_cannot_say_how_is_refused(self):
        contract.check_roles(contract.INPUT_ROLES)
        broken = {"cash": {k: v for k, v in contract.INPUT_ROLES["cash"].items()
                           if k != "answered_how"}}
        with pytest.raises(RuntimeError, match="does not say how"):
            contract.check_roles(broken)


class TestADividendIsNotADeposit:
    def test_the_split_is_reported_and_the_two_are_never_added_up(self):
        j = doc(50_000.0, "2026-01-02",
                ("deposit", 10_000.0, "2026-02-01"),
                ("withdrawal", 4_000.0, "2026-03-01"),
                ("dividend", 250.0, "2026-04-01"))
        moved = cash.movement(j)
        assert moved["contributed"]["value"] == 10_000.0
        assert moved["withdrawn"]["value"] == 4_000.0
        assert moved["earned"]["value"] == 250.0
        # What a return figure nets out: the money that crossed the boundary,
        # and NOT the dividend. Netting the dividend out too would understate
        # what the account made by exactly the dividend.
        assert moved["net_external"]["value"] == 6_000.0

    def test_no_arithmetic_reads_a_kinds_name(self):
        """The declaration and the enforcement are the same thing. A kind
        added to the table arrives at the balance and at the split without
        either being edited — which is the guarantee, so it is exercised
        rather than asserted in prose."""
        extra = dict(cash.KINDS)
        extra["interest"] = {"label": "Interest", "plural": "interest",
                             "direction": 1, "flow": "earned",
                             "means": "invented for this test"}
        original = cash.KINDS
        cash.KINDS = extra
        try:
            j = doc(100.0, "2026-01-02", ("interest", 5.0, "2026-02-01"))
            assert cash.balance(j)["value"] == 105.0
            assert cash.movement(j)["earned"]["value"] == 5.0
            assert cash.movement(j)["net_external"]["value"] == 0.0
        finally:
            cash.KINDS = original

    def test_a_window_that_starts_before_the_record_is_absent_not_partial(
            self):
        """A dollar figure carries nothing saying which months it covers, so
        a partial answer reads as a complete one — and a return netted
        against a flow figure missing its first two years is wrong by those
        two years with nothing to show for it."""
        j = doc(50_000.0, "2026-01-02", ("deposit", 10_000.0, "2026-02-01"))
        early = cash.movement(j, since="2025-01-01")
        for key in ("contributed", "withdrawn", "earned", "net_external"):
            assert early[key]["status"] == "absent"
            assert "2026-01-02" in early[key]["reason"]

    def test_nothing_having_moved_is_a_true_zero_once_the_record_is_open(
            self):
        """The record is append-only and total by construction, so "no
        deposits in this window" is it accounting for the whole of it."""
        moved = cash.movement(doc())
        assert moved["contributed"]["value"] == 0.0
        assert moved["earned"]["value"] == 0.0

    def test_with_no_record_at_all_every_part_is_absent(self):
        moved = cash.movement({})
        assert all(moved[k]["status"] == "absent" for k in
                   ("contributed", "withdrawn", "earned", "net_external"))


class TestAnAmountIsNeverSigned:
    def test_a_negative_amount_is_refused_rather_than_flipped(self):
        """A withdrawal entered as -500 under a kind that already means "out"
        would add five hundred dollars to the account, silently, forever."""
        j = doc()
        with pytest.raises(ValueError, match="more than zero"):
            cash.record(j, "withdrawal", -500.0, "2026-02-01")
        with pytest.raises(ValueError, match="more than zero"):
            cash.record(j, "deposit", 0, "2026-02-01")
        assert cash.balance(j)["value"] == 50_000.0

    def test_an_opening_of_nothing_is_a_statement_and_a_negative_one_is_not(
            self):
        assert cash.balance(conftest.cash_record(0))["value"] == 0.0
        with pytest.raises(ValueError, match="cannot be negative"):
            cash.record({}, cash.OPENING, -1.0)

    def test_an_account_that_starts_overdrawn_is_reached_by_recording_it(self):
        j = doc(0.0, "2026-01-02", ("withdrawal", 500.0, "2026-01-02"))
        assert cash.balance(j)["value"] == -500.0


class TestTheRecordHasToBeginSomewhere:
    def test_an_unopened_record_is_absent_and_names_the_way_out(self):
        answer = cash.balance({})
        assert answer["status"] == "absent"
        assert "value" not in answer
        assert "opening balance" in answer["reason"]

    def test_nothing_may_be_recorded_before_the_opening_balance(self):
        """A ledger of flows with no starting point is a change, not a
        balance."""
        with pytest.raises(ValueError, match="has not been opened"):
            cash.record({}, "deposit", 100.0)

    def test_a_second_opening_balance_is_refused(self):
        j = doc()
        with pytest.raises(ValueError, match="already opens on"):
            cash.record(j, cash.OPENING, 60_000.0)

    def test_an_entry_dated_before_the_opening_is_refused(self):
        """The opening already says what the account held that day, so an
        earlier dividend is money it has already counted."""
        j = doc(50_000.0, "2026-01-02")
        with pytest.raises(ValueError, match="comes before it"):
            cash.record(j, "dividend", 100.0, "2026-01-01")

    def test_an_entry_dated_in_the_future_is_refused(self):
        j = doc()
        with pytest.raises(ValueError, match="has not happened yet"):
            cash.record(j, "deposit", 100.0, "2099-01-01")


class TestTheDayTheMoneyMovedGoverns:
    def test_the_balance_on_a_day_counts_what_had_happened_by_then(self):
        j = doc(50_000.0, "2026-01-02", ("deposit", 10_000.0, "2026-05-01"))
        assert cash.balance(j, "2026-04-30")["value"] == 50_000.0
        assert cash.balance(j, "2026-05-01")["value"] == 60_000.0

    def test_a_day_before_the_record_opens_has_no_answer_at_all(self):
        answer = cash.balance(doc(), "2025-12-31")
        assert answer["status"] == "absent"
        assert "2026-01-02" in answer["reason"]
        assert "carrying the opening balance backwards" in answer["reason"]


class TestWhatTheStrategyIsHanded:
    """Through the real context, because the guarantee spans the record, the
    role machinery and the account arithmetic, and none of it is visible from
    one end alone."""

    @staticmethod
    def _record():
        return {"id": "sizer", "name": "Sizer", "summary": "s", "version": 1,
                "contract": contract.CONTRACT_VERSION, "changelog": {1: "f"},
                "states": [], "values": [], "defaults": {},
                "inputs": [{"id": "free-cash", "label": "Free cash",
                            "type": "number", "unit": "usd", "role": "cash",
                            "explain": "Money not in a position."}]}

    def _ctx(self, journal=None):
        sec = {"ticker": "SYN", "name": "Synthetic", "lots": []}
        return context.build_context(sec, [sec], {}, {},
                                     record=self._record(), journal=journal)

    def test_the_figure_reaches_both_names_as_one_number(self):
        ctx = self._ctx(doc(1_500.0))
        assert ctx["portfolio"]["cash"]["value"] == 1_500.0
        assert ctx["inputs"]["free-cash"] == 1_500.0

    def test_an_absence_reaches_both_and_is_never_a_zero(self):
        ctx = self._ctx({})
        assert ctx["portfolio"]["cash"]["status"] == "absent"
        assert ctx["portfolio"]["account_value"]["status"] == "absent"
        assert "free-cash" not in ctx["inputs"]

    def test_the_derivation_travels_to_the_reader(self):
        said = " ".join(self._ctx(doc(1_500.0))["portfolio"]["cash"]
                        ["provenance"])
        assert "Free cash" in said and "opening balance" in said


class TestTheOldAnswerIsNotMigrated:
    """No migrations is the standing rule, and it is also the honest answer
    here: the edit log cannot say whether a rise was a deposit or a
    correction, so manufacturing deposits out of it would poison the one
    figure this change exists to fix. The old answer stays where it was, on
    the input-change record, and is never read."""

    def test_a_stored_answer_is_inert_rather_than_a_second_source(self,
                                                                  strategies):
        strategies("awkward")
        journal, record = journal_for("awkward",
                                      inputs={"stance": "building"},
                                      cash_opening=1_000.0)
        journal["inputs"]["free-cash"] = 999_999.0     # as an older journal
        assert contract.user_answers(record, journal["inputs"]) == \
            {"stance": "building"}
        ctx = context.build_context(
            {"ticker": "SYN", "lots": []}, [], {},
            journal["inputs"], record=record, journal=journal)
        assert ctx["portfolio"]["cash"]["value"] == 1_000.0

    def test_with_no_record_it_is_absent_rather_than_the_stored_figure(
            self, strategies):
        """The case the fallback would take. A journal that has not opened
        its cash record and still holds the old typed answer must report the
        absence, not the answer — otherwise the change is cosmetic and the
        figure it was supposed to replace goes on deciding."""
        strategies("awkward")
        journal, record = journal_for("awkward",
                                      inputs={"stance": "building"})
        journal["inputs"]["free-cash"] = 999_999.0
        ctx = context.build_context(
            {"ticker": "SYN", "lots": []}, [], {},
            journal["inputs"], record=record, journal=journal)
        assert ctx["portfolio"]["cash"]["status"] == "absent"
        assert "opening balance" in ctx["portfolio"]["cash"]["reason"]
        assert "free-cash" not in ctx["inputs"]

    def test_typing_it_into_settings_is_refused_out_loud(self, strategies):
        """Not silently dropped. A form that accepted it and did nothing
        would leave somebody certain they had changed their balance."""
        strategies("awkward")
        api = Api()
        assert api.create_journal("S", "awkward", {"stance": "building"},
                                  opening_cash=1_000.0)["ok"]
        record = api._open()[1]
        _, problems = contract.check_inputs(record, {"free-cash": 5.0})
        assert any("does not answer it" in p for p in problems), problems

    def test_the_next_save_clears_it_onto_the_record(self, strategies):
        strategies("awkward")
        api = Api()
        assert api.create_journal("S", "awkward", {"stance": "building"},
                                  opening_cash=1_000.0)["ok"]
        stale = journals.load(journals.resolve_open())
        stale["inputs"]["free-cash"] = 999_999.0
        journals.save(stale)

        assert api.save_journal_settings({"stance": "trimming"}, None)["ok"]
        after = journals.load(journals.resolve_open())
        assert "free-cash" not in after["inputs"]
        moved = {m["id"]: m for c in after["input_changes"]
                 for m in c["moved"]}
        assert moved["free-cash"]["from"] == 999_999.0
        assert moved["free-cash"]["to"] is None


class TestThroughTheApi:
    @pytest.fixture
    def api(self, strategies):
        strategies("awkward")
        a = Api()
        assert a.create_journal("Cash", "awkward",
                                {"stance": "building"},
                                opening_cash=20_000.0,
                                opening_cash_on="2026-01-02")["ok"]
        return a

    def test_recording_an_event_moves_the_balance_and_nothing_else(self,
                                                                   api):
        r = api.record_cash("deposit", 5_000, "2026-02-01", "pay day")
        assert r["ok"] and r["balance"]["value"] == 25_000.0
        doc = journals.load(journals.resolve_open())
        assert doc["rule_changes"] == [] and doc["input_changes"] == []
        assert doc[cash.KEY][-1]["note"] == "pay day"

    def test_the_record_travels_in_an_export(self, api, tmp_path):
        from engine import backup
        api.record_cash("dividend", 120, "2026-03-01")
        path = backup.export_bundle(tmp_path)
        import json
        [carried] = json.loads(path.read_text())["journals"]
        assert [e["kind"] for e in carried[cash.KEY]] == ["opening",
                                                          "dividend"]

    def test_a_refusal_reaches_the_screen_rather_than_the_window(self, api):
        r = api.record_cash("deposit", -5)
        assert r["ok"] is False
        assert "more than zero" in r["error"]

    def test_the_state_carries_the_record_the_kinds_and_the_split(self, api):
        api.record_cash("deposit", 5_000, "2026-02-01")
        api.record_cash("dividend", 120, "2026-03-01")
        got = api.get_state()["cash"]
        assert got["balance"]["value"] == 25_120.0
        assert got["movement"]["contributed"]["value"] == 5_000.0
        assert got["movement"]["earned"]["value"] == 120.0
        assert [r["kind"] for r in got["ledger"]] == ["opening", "deposit",
                                                      "dividend"]
        # The kinds are handed over, never known by the view — the same rule
        # the render types follow one level up. So is which of them may be
        # recorded now, because a screen working that out would be a second
        # copy of a rule the write enforces, offering a button whose entry is
        # refused.
        assert set(got["kinds"]) == set(cash.KINDS)
        assert got["offers"] == list(cash.EVENT_KINDS)
        assert cash.OPENING not in got["offers"]

    def test_before_the_record_is_opened_only_opening_it_is_offered(
            self, strategies):
        strategies("awkward")
        api = Api()
        assert api.create_journal("Bare", "awkward",
                                  {"stance": "building"})["ok"]
        assert api.get_state()["cash"]["offers"] == [cash.OPENING]

    def test_a_bad_setup_figure_keeps_the_journal_and_says_what_went_wrong(
            self, strategies):
        """Deleting a journal somebody just named over a number they can
        retype in one click would be the worse failure of the two."""
        strategies("awkward")
        api = Api()
        r = api.create_journal("Odd", "awkward", {"stance": "building"},
                               opening_cash=-5)
        assert r["ok"] and "cannot be negative" in r["cash_problem"]
        listed = {j["name"] for j in journals.list_journals()}
        assert "Odd" in listed
