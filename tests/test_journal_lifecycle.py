"""A journal as an object — renamed, removed — and a commit that stages.

Three silent failures live here.

The first is a rename that moves more than the name. The id is the address:
`list_journals` reads it off the directory, `load` overwrites the document's
own copy with the folder it came from, and the machine-local "which one is
open" points at it. A rename that renamed the folder to match would leave
every one of those pointing at nothing, and the symptom — a switcher row that
opens an empty screen — arrives long after the rename that caused it.

The second is a delete that reaches further than the journal named. There is
no undo and no copy: principle 11 keeps a journal out of the repository, so a
delete that took a neighbour with it, or that left the open pointer naming a
folder that is gone, destroys the only record there was.

The third is a staged plan that stages nothing. A plan is prose the strategy
re-reads next time — the host never checks a condition and must never look as
though it might — so every way the list can say less than it appears to say
has to be refused at the boundary. A tranche with no condition, or in a unit
nothing can add up, renders as a commitment to a shape while committing to
nothing, and it renders that way at the one moment the shape is supposed to
be settled: while the user is calm.
"""

import json

import pytest
from conftest import entered, journal_for

from engine import bank, contract, journals, store

# -- journals ---------------------------------------------------------------


def _decision():
    """A commit envelope in the shape portfolio freezes, built by hand: this
    file records decisions, it never evaluates one."""
    return {"render": "commit", "tier": "position",
            "state": {"id": "say-yes", "name": "Commit", "description": "d",
                      "fix": None},
            "payload": {"size": {"unit": "weight", "value": 5.0},
                        "condition": None},
            "reason": {"rule": "cleared-the-floor", "summary": "It cleared.",
                       "evidence": [], "note": None},
            "produced_by": "strategy",
            "strategy": {"id": "verdicts", "name": "Verdict fixture",
                         "version": 1, "values_version": 1, "contract": 5}}


def _furnished(journal, record, ticker="ARBR"):
    """A journal with something to lose: a holding with a frozen snapshot, a
    dated hand-entered figure, and a recorded rule change with its reason.

    A rename or a delete tested against an empty journal proves nothing —
    what has to survive one and go with the other is the record itself.
    """
    from engine import portfolio
    security = entered(portfolio.new_security(ticker, "Arbor Mills"),
                       day="2026-03-01", fcf_ttm=2_500_000.0)
    portfolio.add_lot(security, _decision(), 10, 40.0, "2026-03-02")
    journal["securities"].append(security)
    journals.observe_rule_change(journal, record, {"cash-floor": 250000})
    journals.explain(journal, "rules", 1,
                     "Overrides on this kept working out.")
    journals.save(journal)
    return journal


def _doc(journal_id):
    return store.read_json(journals.path_for(journal_id))


class TestARenameIsNotAMove:
    """The name is free text nobody hangs anything off. The id is the
    address, and it stays put — a journal renamed six times keeps the slug it
    was born with, and nothing that points at it has to be told."""

    def _journal(self, strategies, name="Before the rename"):
        strategies("verdicts")
        journal, record = journal_for("verdicts", name)
        return _furnished(journal, record), record

    def test_the_id_and_the_folder_never_move(self, strategies):
        journal, _ = self._journal(strategies)
        before = journals.path_for(journal["id"])
        renamed = journals.rename(journal["id"], "After the rename")

        assert renamed["name"] == "After the rename"
        assert renamed["id"] == journal["id"]
        assert journals.path_for(journal["id"]) == before
        assert [p.name for p in journals.journals_dir().iterdir()] == \
            [journal["id"]]
        # and it still opens at the address everything else is holding
        assert journals.load(journal["id"])["name"] == "After the rename"
        assert [(j["id"], j["name"]) for j in journals.list_journals()] == \
            [(journal["id"], "After the rename")]

    def test_everything_recorded_comes_back_byte_for_byte(self, strategies):
        """Read off the file rather than out of the returned document, and
        compared as bytes: a rename that re-serialised the record through
        anything with an opinion — a default filled in, a snapshot rebuilt
        from a strategy that has since moved — would pass an equality check
        on the parts a test thought to name, and quietly restate the rest."""
        journal, _ = self._journal(strategies)
        path = journals.path_for(journal["id"])
        before = path.read_bytes()
        assert before.count(b"Before the rename") == 1

        journals.rename(journal["id"], "After the rename")
        after = path.read_bytes()
        assert after == before.replace(b"Before the rename",
                                       b"After the rename")

    def test_a_name_that_is_only_whitespace_is_refused(self, strategies):
        """Every journal is told apart by its name on one screen. A blank one
        is a row the user cannot identify, and the delete dialog asks them to
        retype it — a journal called "   " could not be deleted either."""
        journal, _ = self._journal(strategies)
        for blank in ("", "   ", "\t\n", None):
            with pytest.raises(ValueError):
                journals.rename(journal["id"], blank)
        assert _doc(journal["id"])["name"] == "Before the rename"

    def test_the_name_is_taken_without_its_surrounding_space(self,
                                                             strategies):
        journal, _ = self._journal(strategies)
        assert journals.rename(journal["id"], "  Growth  ")["name"] == "Growth"

    def test_a_rename_goes_on_no_record_and_owes_no_reason(self, strategies):
        """A name is not a rule and not a decision. Recorded as a rule change
        it would raise a banner with no dismiss, demanding a written
        justification for retitling a notebook — and the reason is
        write-once, so the sentence invented to clear it stands forever."""
        journal, record = self._journal(strategies)
        before = list(_doc(journal["id"])["rule_changes"])
        renamed = journals.rename(journal["id"], "After the rename")

        assert renamed["rule_changes"] == before
        assert renamed["input_changes"] == []
        assert journals.pending(renamed) == []
        assert journals.baseline(renamed)["values"] == {"cash-floor": 250000}
        assert renamed["strategy"]["values"] == {"cash-floor": 1000000}

    def test_two_journals_may_answer_to_the_same_name(self, strategies):
        """Nothing resolves by name, so nothing breaks when two agree. If a
        collision were refused, the way out would be renaming the folder —
        which is the move this whole split exists to avoid."""
        strategies("verdicts")
        a, record = journal_for("verdicts", "Ideas")
        b = journals.create("Second", record, bank.definitions())
        journals.rename(b["id"], "Ideas")
        assert a["id"] != b["id"]
        assert [j["name"] for j in journals.list_journals()] == \
            ["Ideas", "Ideas"]
        assert journals.load(a["id"])["id"] == a["id"]
        assert journals.load(b["id"])["id"] == b["id"]

    def test_renaming_one_that_is_not_there_says_so(self, strategies):
        strategies("verdicts")
        journal_for("verdicts")
        with pytest.raises(store.StoreError):
            journals.rename("never-existed", "Something")


class TestDeleteTakesOneJournalAndNothingElse:
    """The one destructive operation in the program. What it removes is not
    recoverable and is nowhere else."""

    def _two(self, strategies):
        strategies("verdicts")
        keep, record = journal_for("verdicts", "Keep")
        _furnished(keep, record, ticker="ARBR")
        discard = journals.create("Discard", record, bank.definitions())
        _furnished(discard, record, ticker="BRKW")
        return keep, discard

    def test_the_folder_and_everything_in_it_goes(self, strategies):
        keep, discard = self._two(strategies)
        folder = journals.path_for(discard["id"]).parent
        (folder / "stray.json").write_text("{}", encoding="utf-8")

        removed = journals.delete(discard["id"])

        assert not folder.exists()
        assert [j["id"] for j in journals.list_journals()] == [keep["id"]]
        with pytest.raises(store.StoreError):
            journals.load(discard["id"])
        assert removed == {"id": discard["id"], "name": "Discard",
                           "securities": 1, "holdings": 1}

    def test_what_was_removed_is_reported_by_the_name_on_screen(self,
                                                                strategies):
        """The caller has to be able to say what happened, and the thing it
        is describing is gone by then — so the answer travels back out. It
        names the journal the way the user saw it, which after a rename is
        the new name and never the slug underneath."""
        strategies("verdicts")
        journal, record = journal_for("verdicts", "Before the rename")
        _furnished(journal, record)
        journals.rename(journal["id"], "After the rename")
        assert journals.delete(journal["id"])["name"] == "After the rename"

    def test_no_other_journal_is_touched(self, strategies):
        """Byte-for-byte, because the failure this guards is a delete that
        reached one folder too far — and the neighbour it emptied has no
        second copy anywhere to compare against afterwards."""
        keep, discard = self._two(strategies)
        before = journals.path_for(keep["id"]).read_bytes()
        journals.delete(discard["id"])
        assert journals.path_for(keep["id"]).read_bytes() == before
        assert journals.load(keep["id"])["securities"][0]["ticker"] == "ARBR"

    def test_the_open_pointer_is_cleared_when_it_named_the_one_deleted(
            self, strategies):
        """Left dangling, the next journal created with the same slug
        silently inherits "you had this one open" — a small lie about a fact
        the user never stated, told by a folder name they never chose."""
        keep, discard = self._two(strategies)
        journals.set_open(discard["id"])
        journals.delete(discard["id"])
        assert journals.open_id() is None
        assert journals.resolve_open() == keep["id"]

    def test_the_open_pointer_is_left_alone_when_it_named_another(
            self, strategies):
        """The other half, and the one a test is likelier to skip: clearing
        it unconditionally would silently move the user out of the journal
        they were working in, every time they tidied up a different one."""
        keep, discard = self._two(strategies)
        journals.set_open(keep["id"])
        journals.delete(discard["id"])
        assert journals.open_id() == keep["id"]
        assert journals.resolve_open() == keep["id"]

    def test_deleting_one_that_is_not_there_is_refused(self, strategies):
        """And takes nothing with it. The assertion that matters is not that
        it raised — it is that the journals on disk before and after are the
        same ones, byte for byte. A refusal that had already removed
        something would raise identically."""
        keep, other = self._two(strategies)
        before = {j["id"]: json.dumps(journals.load(j["id"]), sort_keys=True)
                  for j in journals.list_journals()}
        assert set(before) == {keep["id"], other["id"]}
        with pytest.raises(store.StoreError):
            journals.delete("never-existed")
        after = {j["id"]: json.dumps(journals.load(j["id"]), sort_keys=True)
                 for j in journals.list_journals()}
        assert after == before

    def test_deleting_the_last_journal_is_allowed(self, strategies):
        """Deliberately not refused. A rule making the final journal
        undeletable would leave a wrong first attempt on disk for good, and
        the welcome screen is what a user with no journals is meant to see.
        """
        strategies("verdicts")
        journal, record = journal_for("verdicts", "Only")
        _furnished(journal, record)
        journals.set_open(journal["id"])
        journals.delete(journal["id"])
        assert journals.list_journals() == []
        assert journals.resolve_open() is None


class TestNeitherCanClimbOutOfTheJournalsDirectory:
    """A journal id is a plain folder name and nothing else. It reaches these
    two functions from a document, an imported bundle and the view, and one
    of them removes a directory tree — so the id is refused rather than
    sanitised, before anything is opened or unlinked."""

    HOSTILE = ["../escape", "a/b", "..", ".", ".hidden", ""]

    def _outside(self):
        """Something worth protecting one step above the journals directory,
        exactly where "../escape" points."""
        outside = journals.journals_dir().parent / "escape"
        outside.mkdir(parents=True, exist_ok=True)
        (outside / "keys.json").write_text('{"secret": 1}', encoding="utf-8")
        return outside

    @pytest.mark.parametrize("bad", HOSTILE)
    def test_a_hostile_id_is_never_renamed(self, bad, strategies):
        strategies("verdicts")
        journal_for("verdicts")
        outside = self._outside()
        with pytest.raises(ValueError):
            journals.rename(bad, "Mine now")
        assert (outside / "keys.json").exists()

    @pytest.mark.parametrize("bad", HOSTILE)
    def test_a_hostile_id_is_never_deleted(self, bad, strategies):
        strategies("verdicts")
        journal, _ = journal_for("verdicts")
        outside = self._outside()
        with pytest.raises(ValueError):
            journals.delete(bad)
        assert (outside / "keys.json").read_text(encoding="utf-8") == \
            '{"secret": 1}'
        assert [j["id"] for j in journals.list_journals()] == [journal["id"]]


# -- the staged plan ---------------------------------------------------------


def decl(**over):
    """A declaration whose one state puts capital in, so a payload can be
    tested. Invented content; it is not investment logic."""
    d = {
        "id": "staged",
        "name": "Staged fixture",
        "summary": "A test declaration with one state that commits.",
        "version": 1,
        "contract": contract.CONTRACT_VERSION,
        "changelog": {1: "First version."},
        "states": [
            {"id": "start", "name": "Start a position", "render": "commit",
             "description": "Open the first tranche of an intended size."},
            {"id": "sit", "name": "Sit", "render": "hold",
             "description": "Do nothing."},
        ],
    }
    d.update(over)
    return d


def record(**over):
    r = decl()
    r.update({"inputs": [], "values": [], "defaults": {}, "values_version": 1,
              "dir": "/nowhere", "decide": lambda ctx: None})
    r.update(over)
    return r


def tranche(value=2.0, unit="weight", summary="the price falls a third "
                                              "below what the business "
                                              "is worth."):
    return {"size": {"unit": unit, "value": value},
            "condition": {"summary": summary}}


def payload(plan=None, **over):
    p = {"size": {"unit": "weight", "value": 2.0}, "condition": None}
    if plan is not None:
        p["plan"] = plan
    p.update(over)
    return p


def errors_for(pl, state="start"):
    return contract.validate_decision(record(), {
        "state": state, "payload": pl,
        "reason": {"rule": "opens-in-thirds", "summary": "A third now.",
                   "evidence": [{"measure": "fcf_ttm"}]}})


class TestAStagedEntryCommitsToAShape:
    """One decision, not several: the state is `commit` and the size in front
    of you is the size in front of you. The plan is what a single tranche
    cannot say — that this 2% is the first third of an intended 6%, and what
    has to be true before the rest goes in."""

    def test_a_plan_of_further_tranches_is_accepted(self):
        assert errors_for(payload([tranche(), tranche(
            summary="the price falls by half.")])) == []

    def test_a_commit_that_stages_nothing_is_still_a_decision(self):
        """The key is optional, and the ordinary case is the whole position
        at once. A strategy that never stages must not have to say so."""
        assert errors_for(payload()) == []
        assert "plan" not in payload()
        assert errors_for(payload(plan=None)) == []

    def test_the_plan_reaches_the_reader_intact(self):
        """Validation passing is not the guarantee — the plan surviving into
        the envelope the screen and the frozen snapshot read is. A payload
        checked and then dropped would leave the user committing to a shape
        that nothing afterwards can show them."""
        plan = [tranche(), tranche(3.0, summary="the price falls by half.")]
        rec = record(decide=lambda ctx: {
            "state": "start", "payload": payload(plan),
            "reason": {"rule": "opens-in-thirds", "summary": "A third now.",
                       "evidence": [{"measure": "fcf_ttm"}]}})
        result = contract.evaluate(rec, ctx())

        assert result["state"]["id"] == "start"
        assert result["render"] == "commit"
        assert result["payload"]["plan"] == plan
        assert result["payload"]["size"] == {"unit": "weight", "value": 2.0}

    def test_an_empty_list_stages_nothing(self):
        errs = errors_for(payload([]))
        assert any("stages nothing" in e for e in errs)

    def test_a_plan_that_is_not_a_list_of_tranches_is_refused(self):
        for bad in ({"size": {"unit": "weight", "value": 2.0}}, "later", 3):
            assert errors_for(payload(bad)), bad
        assert any("must be exactly {size, condition}" in e
                   for e in errors_for(payload(["later"])))

    def test_a_tranche_missing_its_size_is_refused(self):
        errs = errors_for(payload([{"condition": {"summary": "it falls."}}]))
        assert any("tranche 1 must be exactly {size, condition}" in e
                   for e in errs)

    def test_a_tranche_missing_its_condition_is_refused(self):
        errs = errors_for(payload([{"size": {"unit": "weight",
                                             "value": 2.0}}]))
        assert any("tranche 1 must be exactly {size, condition}" in e
                   for e in errs)

    def test_a_tranche_with_no_condition_is_not_held_back(self):
        """The refusal that carries the weight. "3% now and 3% more,
        sometime" would render as a plan while committing to nothing — and
        the number it commits to nothing about is already in front of the
        user, in the size."""
        errs = errors_for(payload([{**tranche(), "condition": None}]))
        assert any("is not held back" in e for e in errs)
        assert any("belongs in that number" in e for e in errs)

    def test_a_condition_the_reader_cannot_read_is_refused(self):
        for bad in ("it falls", {"summary": "  "}, {"summary": 3},
                    {"when": "it falls"}, {}):
            errs = errors_for(payload([{**tranche(), "condition": bad}]))
            assert any("plain language" in e for e in errs), bad

    def test_a_tranche_in_another_unit_cannot_be_added_up(self):
        """A first tranche in percent and a second in dollars: nothing can
        say what the whole position is meant to come to, so a screen would
        have to guess or quietly show one of the two."""
        errs = errors_for(payload([tranche(unit="usd", value=500.0)]))
        assert any("measured in usd" in e and "in weight" in e for e in errs)
        assert any("the same unit" in e for e in errs)
        # …and the same plan under a size in that unit is fine
        assert errors_for(payload([tranche(unit="usd", value=500.0)],
                                  size={"unit": "usd",
                                        "value": 500.0})) == []

    def test_a_tranche_of_nothing_is_refused(self):
        for value in (0, -3.0):
            errs = errors_for(payload([tranche(value=value)]))
            assert any("above zero" in e for e in errs), value

    def test_a_broken_size_is_named_however_good_the_plan_looks(self):
        """The plan is the shape; the size is the money going in today. A
        well-formed list of tranches must never carry a payload whose own
        size is unreadable — the staged part would render while the part
        that actually commits capital had no number anyone could act on."""
        for size in ({"unit": "vibes", "value": 2.0},
                     {"unit": "weight", "value": 0}, "lots", None):
            errs = errors_for(payload([tranche(), tranche()], size=size))
            assert any(e.startswith("`size` must be") for e in errs), size

    def test_the_optional_key_opens_the_door_to_nothing_else(self):
        """`plan` is permitted by name, not by loosening the payload. An
        extra key the host does not know is a fact nobody will render, and
        the strategy that wrote it has no way to find out it went nowhere."""
        assert any("vibe" in e for e in errors_for(payload(vibe="calm")))
        errs = errors_for(payload([tranche()], vibe="calm"))
        assert any("vibe" in e for e in errs)
        assert any("Extra facts belong in the reason" in e for e in errs)

    def test_only_a_commit_can_carry_one(self):
        """A hold that stages tranches is a proposal to buy wearing the
        clothes of doing nothing."""
        errs = errors_for({"plan": [tranche()]}, state="sit")
        assert any("plan" in e for e in errs)
        assert contract.RENDER_TYPES["commit"]["optional_keys"] == ("plan",)
        assert {r: contract.RENDER_TYPES[r]["optional_keys"]
                for r in contract.RENDER_TYPES if r != "commit"} == \
            {"hold": (), "reduce": (), "close": (), "blocked": (),
             "unknown": (), "inapplicable": ()}

    def test_a_malformed_plan_is_refused_and_never_rendered(self):
        """Validation says no; this is what the user sees when it does. A
        plan that failed its checks must not reach the screen as a commit
        with the bad tranche quietly dropped."""
        rec = record(decide=lambda ctx: {
            "state": "start", "payload": payload([{**tranche(),
                                                   "condition": None}]),
            "reason": {"rule": "opens-in-thirds", "summary": "A third now.",
                       "evidence": [{"measure": "fcf_ttm"}]}})
        result = contract.evaluate(rec, ctx())

        assert result["state"]["id"] == "host:invalid-decision"
        assert result["produced_by"] == "host"
        assert result["render"] in ("unknown", "blocked")
        assert "is not held back" in result["reason"]["summary"]

    def test_the_message_says_which_tranche(self):
        """Three tranches deep, "a tranche is wrong" is not a fix."""
        errs = errors_for(payload([tranche(), tranche(value=0),
                                   {**tranche(), "condition": None}]))
        assert any("tranche 2" in e for e in errs)
        assert any("tranche 3" in e for e in errs)
        assert not any("tranche 1" in e for e in errs)


def ctx(**over):
    c = {"contract": contract.CONTRACT_VERSION, "today": "2026-08-10",
         "inputs": {}, "values": {},
         "measures": {"fcf_ttm": {
             "current": {"status": "known", "value": 150.0,
                         "source": "computed", "cautions": [],
                         "provenance": ["10-K S-1"]},
             "series": {"cadence": "annual", "truncated": False,
                        "note": None, "points": []}}},
         "position": {"held": False, "shares": 0.0},
         "portfolio": {"slots": {"occupied": 1}}}
    c.update(over)
    return c


class TestAStagedPlanIsProseAndNotASchedule:
    """The host never checks whether a condition has been met, and must not
    look as though it might. What is written here is re-read by the strategy
    on its own next evaluation — nothing is stored against the plan, nothing
    fires on its own, and the business is re-tested every time."""

    def test_a_plan_is_not_a_thing_the_host_stores_or_acts_on(self):
        """Pinned by what the payload cannot carry: no date, no trigger
        price, no reference to the plan on a later evaluation. A condition
        with a day attached would be a standing order, and the tool never
        trades."""
        for schedule in ({**tranche(), "when": "2026-12-01"},
                         {**tranche(), "trigger": 40.0}):
            errs = errors_for(payload([schedule]))
            assert any("must be exactly {size, condition}" in e
                       for e in errs), schedule

    def test_the_same_tranche_arrives_later_as_a_size_with_no_condition(self):
        """The whole mechanism, stated as the two decisions it actually is:
        the day the condition holds, the strategy returns that tranche as the
        size in front of you, unconditionally. Both are ordinary commits and
        neither remembers the other."""
        first = payload([tranche(2.0)])
        second = payload(size={"unit": "weight", "value": 2.0})
        assert errors_for(first) == []
        assert errors_for(second) == []
        assert second["condition"] is None
        assert "plan" not in second


class TestTheContractVersionMovesOnlyForAMeaning:
    def test_a_staged_plan_is_additive_to_the_version_already_spoken(self):
        """An optional key is the one kind of change that does not need a new
        contract: every strategy written before it stays valid, and the host
        would refuse them all if the number moved.

        The bare number is here on purpose, and it is the reason this cannot
        grow quietly: a contract bump has to come past this test, and whoever
        updates it has to be able to say the move was for a meaning that
        changed rather than for a key that was added. It has moved twice
        since — to 6, when `position.disposals` narrowed from the security's
        whole record to the current holding's sales; to 7, when `confirm()`
        stopped counting filings for the twenty measures carrying a quoted
        price and started counting the sessions they actually change on; and
        to 8, when the evidence began saying which citations a verdict rests
        on, because a closing verdict and one still waiting on confirmation
        cite exactly the same exits and a bundle reading the rows to tell
        them apart was reading an answer that was not there. All three are
        the same test: the same key, the same shape, a different question
        answered. The staged plan is still not why.
        """
        assert contract.CONTRACT_VERSION == 8
        assert contract.validate_declaration(decl()) == []
        assert json.loads(json.dumps(payload([tranche()]))) == \
            payload([tranche()])


class TestABrokenMetricBankStillOpensTheWindow:
    """The whole of item 1, end to end and through the real Api.

    The unit tests above the engine prove the bank refuses well. This proves
    the thing that actually went wrong: `get_state` called `bank.meta()` with
    nothing around it, `@guarded` turned the ValueError into `ok: false`, the
    browser toasted it for four seconds with the line breaks collapsed and
    never called `render()`. On a cold start that left the boot placeholder
    on screen forever; on a warm one it left the last good screen up with no
    sign anything was wrong.
    """

    def _break_the_bank(self, tmp_path, monkeypatch, *, parseable=True,
                        cold=False):
        """Edit the shipped bank the way a user would — in a file.

        `cold` is the difference between the two cases and it is only about
        what this program has already read. A mid-session edit leaves whatever
        loaded at launch in memory, which is the version that goes on
        answering; a cold start has nothing, so the caches are emptied to
        stand for a process that has just begun.
        """
        import os
        from engine import bank
        src = (bank.APP_DIR / "config" / "metric-bank.yaml").read_text(
            encoding="utf-8")
        broken = (src.replace("      kind: median\n      observations: 5\n",
                              "      kind: median\n      observations: 1\n", 1)
                  if parseable else src.replace("entries:\n", "entries: [{\n",
                                                1))
        assert broken != src
        d = tmp_path / "bank"
        d.mkdir(exist_ok=True)
        (d / "metric-bank.yaml").write_text(broken, encoding="utf-8")
        monkeypatch.setattr(bank, "CONFIG_DIR", d)
        bank._bank_refused.pop("metric-bank", None)
        if cold:
            bank._bank_cache.pop("metric-bank", None)
            bank._definitions_cache.pop("metric-bank", None)
        os.utime(d / "metric-bank.yaml", None)

    def test_a_cold_start_on_a_broken_bank_still_renders(
            self, strategies, tmp_path, monkeypatch):
        """Nothing good was ever loaded, so there are no measures — and the
        state still comes back `ok` with the journal list and the reason,
        because the way out of this is to go and fix a file and that needs a
        window that opens."""
        from app import Api
        strategies("verdicts")
        journal_for("verdicts", "Mine")
        self._break_the_bank(tmp_path, monkeypatch, parseable=False,
                             cold=True)

        state = Api().get_state()
        assert state["ok"] is True
        assert state["bank_problem"]["holding"] is False
        assert state["bank_problem"]["problems"]
        assert [j["name"] for j in state["journals"]] == ["Mine"]

    def test_a_bad_edit_mid_session_keeps_the_figures_and_says_so(
            self, strategies, tmp_path, monkeypatch):
        """The warm case, which is the common one: the user is editing the
        file while the program is running. The last good version goes on
        answering, the securities still render, and the screen says the edit
        did not take — the difference between "your figures are stale" and
        "your figures are gone" being the whole point of reporting it."""
        from app import Api
        strategies("verdicts")
        journal, _ = journal_for("verdicts", "Mine")
        api = Api()
        api.add_security("ACME", "Acme Widgets")
        assert api.get_state()["bank_problem"] is None

        self._break_the_bank(tmp_path, monkeypatch)
        state = api.get_state()
        assert state["ok"] is True
        assert state["bank_problem"]["holding"] is True
        assert any("line" in p for p in state["bank_problem"]["problems"])
        # still a working journal, read from the version that loaded
        assert state["journal"]["name"] == "Mine"
        assert [s["ticker"] for s in state["securities"]] == ["ACME"]
        assert state["bank_meta"], "the measures went with the bad edit"


class TestTheTypedDeleteConfirmationCanActuallyBeTyped:
    """The confirmation asks the user to retype the name they can see — and
    a name holding an em-dash ("Sample — Graham") has no key that types it,
    which made every journal named that way undeletable from the screen that
    showed it. A plain hyphen stands in for any dash; everything else still
    has to match, so the confirmation stays a confirmation."""

    def test_a_hyphen_stands_in_for_the_em_dash(self, strategies):
        strategies("verdicts")
        from app import Api
        from conftest import journal_for
        journal, record = journal_for("verdicts", "Sample — Graham")
        r = Api().delete_journal(journal["id"], "Sample - Graham")
        assert r["ok"], r
        assert journals.list_journals() == []

    def test_a_wrong_name_is_still_refused(self, strategies):
        strategies("verdicts")
        from app import Api
        from conftest import journal_for
        journal, record = journal_for("verdicts", "Sample — Graham")
        r = Api().delete_journal(journal["id"], "Sample Graham")
        assert not r["ok"]
        assert "hyphen" in r["error"]
        assert len(journals.list_journals()) == 1
