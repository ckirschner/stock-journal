"""Journals, and the record of what their rules demanded.

Two guarantees live here, and both fail silently rather than loudly.

The first is that a journal is stamped with one strategy and keeps its own
records — a switcher that read the wrong journal, or a save that wrote into
another one, would look exactly like working software until someone noticed
their positions in the wrong place.

The second is principle 3's second half: a change to what a strategy demands
is detected and recorded, when it changed and what it was before. The
dangerous case is not a change nobody made — it is a threshold edited in
place with the version beside it left alone, because that is what the record
exists to make impossible, and because nothing about it looks wrong
afterwards.
"""

import copy

import pytest
from conftest import entered, journal_for

from engine import bank, journals, store, strategy_loader, strategy_values


def _record(strategy_id="verdicts"):
    strategies, reports = strategy_loader.discover()
    assert strategy_id in strategies, [r["errors"] for r in reports]
    return strategies[strategy_id]


def _resolve(record, journal):
    return strategy_values.resolve(
        record, layers=[("this journal", journal.get("config") or {})]
    )["values"]


class TestCreation:
    def test_a_journal_is_stamped_with_the_strategy_it_was_created_against(
            self, strategies):
        strategies("verdicts")
        journal, record = journal_for("verdicts", "Retirement")
        stamp = journal["strategy"]
        assert stamp["id"] == "verdicts"
        assert stamp["name"] == record["name"]
        assert stamp["contract"] == record["contract"]
        assert stamp["version"] == record["version"]
        assert stamp["values_version"] == record["values_version"]
        # the values themselves, not only their version number — this is what
        # catches a threshold edited without a version bump
        assert stamp["values"] == {"cash-floor": 1000000}

    def test_a_fresh_journal_owes_no_reason(self, strategies):
        """Being created is not a rule change. A journal that opened with a
        pending explanation would train the user to dismiss the banner."""
        strategies("verdicts")
        journal, _ = journal_for("verdicts")
        assert journal["rule_changes"] == []
        assert journals.pending(journal) == []

    def test_two_journals_keep_separate_records(self, strategies):
        strategies("verdicts")
        a, record = journal_for("verdicts", "First")
        b = journals.create("Second", record, bank.definitions())
        a["securities"].append(
            entered({"ticker": "ACME", "lots": []}, fcf_ttm=5.0))
        journals.save(a)
        assert journals.load(b["id"])["securities"] == []
        assert len(journals.load(a["id"])["securities"]) == 1

    def test_a_name_that_collides_gets_its_own_folder(self, strategies):
        strategies("verdicts")
        a, record = journal_for("verdicts", "Ideas")
        b = journals.create("Ideas", record, bank.definitions())
        assert a["id"] != b["id"]
        assert journals.path_for(a["id"]) != journals.path_for(b["id"])

    def test_an_unnamed_journal_is_refused(self, strategies):
        strategies("verdicts")
        record = _record()
        with pytest.raises(ValueError):
            journals.create("   ", record, bank.definitions())


class TestStorageBoundary:
    @pytest.mark.parametrize("bad", ["../escape", "a/b", "..", ".",
                                     ".hidden", ""])
    def test_a_journal_id_can_never_climb_out_of_the_journals_directory(
            self, bad):
        """The id reaches here from a journal's own document and from an
        imported bundle. Sanitising a hostile name into a harmless one would
        hide that it was sent at all."""
        with pytest.raises(ValueError):
            journals.path_for(bad)

    def test_an_unreadable_journal_is_listed_with_its_problem(self,
                                                              strategies):
        """Dropping it from the list would make a storage failure look like
        a journal the user never created."""
        strategies("verdicts")
        journal, _ = journal_for("verdicts")
        journals.path_for(journal["id"]).write_text("{ truncated",
                                                    encoding="utf-8")
        listed = journals.list_journals()
        assert len(listed) == 1
        assert listed[0]["id"] == journal["id"]
        assert listed[0]["problem"]
        assert listed[0]["securities"] is None

    def test_a_journal_from_a_schema_this_app_cannot_read_is_refused(
            self, strategies):
        strategies("verdicts")
        journal, _ = journal_for("verdicts")
        doc = store.read_json(journals.path_for(journal["id"]))
        doc["schema"] = "ledger.journal/99"
        store.write_json(journals.path_for(journal["id"]), doc)
        with pytest.raises(store.StoreError):
            journals.load(journal["id"])

    def test_a_journal_that_cannot_be_read_is_not_a_dead_end(self,
                                                             strategies):
        """The window must not go blank. The list still renders with the
        problem named, so the way out is to open a different journal — an
        error that leaves nowhere to click is not an error message."""
        from app import Api
        strategies("verdicts")
        broken, record = journal_for("verdicts", "Broken")
        other = journals.create("Other", record, bank.definitions())
        journals.set_open(broken["id"])
        journals.path_for(broken["id"]).write_text("{ truncated",
                                                   encoding="utf-8")

        api = Api()
        state = api.get_state()
        assert state["ok"]
        assert state["journal"] is None
        assert state["journal_problem"]
        assert {j["id"]: bool(j["problem"]) for j in state["journals"]} == \
            {broken["id"]: True, other["id"]: False}
        assert api.open_journal(other["id"])["ok"]
        assert api.get_state()["journal"]["id"] == other["id"]
        # and nothing was written over the file that could not be read
        assert journals.path_for(broken["id"]).read_text(
            encoding="utf-8") == "{ truncated"

    def test_a_deleted_journal_is_not_recreated(self, strategies):
        strategies("verdicts")
        a, record = journal_for("verdicts", "Keep")
        b = journals.create("Discard", record, bank.definitions())
        journals.set_open(b["id"])
        journals.path_for(b["id"]).unlink()
        assert journals.resolve_open() == a["id"]
        assert [j["id"] for j in journals.list_journals()] == [a["id"]]

    def test_a_fetch_result_lands_in_the_journal_that_asked_for_it(
            self, strategies):
        """A fetch runs on a background thread and can land minutes later. If
        it wrote into whichever journal happened to be open by then, switching
        journals mid-fetch would leave the one that asked without the company
        it just resolved — and silently give it to another."""
        from app import Api
        strategies("verdicts")
        asked, record = journal_for("verdicts", "Asked")
        api = Api()
        api.add_security("ACME", "Acme Widgets")

        other = journals.create("Other", record, bank.definitions())
        other["securities"].append({"ticker": "ACME", "lots": [],
                                    "notes": []})
        journals.save(other)
        journals.set_open(other["id"])

        api._tie_cik(asked["id"], "ACME", 424242)

        assert journals.load(asked["id"])["securities"][0]["cik"] == 424242
        assert "cik" not in journals.load(other["id"])["securities"][0]

    def test_a_write_that_fails_leaves_the_previous_journal_intact(
            self, strategies):
        """Atomic persistence, tested by breaking it: a payload that cannot
        be serialised must not truncate what was already recorded."""
        strategies("verdicts")
        journal, _ = journal_for("verdicts")
        journal["securities"].append({"ticker": "ACME", "lots": []})
        journals.save(journal)
        before = journals.path_for(journal["id"]).read_bytes()

        journal["securities"].append({"ticker": "BAD", "oops": {1, 2}})
        with pytest.raises(TypeError):
            journals.save(journal)
        assert journals.path_for(journal["id"]).read_bytes() == before
        assert not list(journals.journals_dir().rglob("*.tmp"))


class TestRuleChanges:
    def _journal(self, strategies):
        strategies("verdicts")
        journal, record = journal_for("verdicts")
        return journal, record

    def test_nothing_moved_records_nothing(self, strategies):
        journal, record = self._journal(strategies)
        assert journals.observe_rule_change(
            journal, record, _resolve(record, journal)) is None
        # and again, because this runs on every launch
        assert journals.observe_rule_change(
            journal, record, _resolve(record, journal)) is None
        assert journal["rule_changes"] == []

    def test_a_threshold_edited_without_a_version_bump_is_still_caught(
            self, strategies):
        """The case the record exists for. The version beside the number is
        the strategy's own marker of a change; a hand edit leaves it alone,
        and nothing about the result looks wrong afterwards."""
        journal, record = self._journal(strategies)
        entry = journals.observe_rule_change(journal, record,
                                             {"cash-floor": 250000})
        assert entry["kind"] == "settings"
        assert entry["moved"] == [{"id": "cash-floor",
                                   "label": "Cash flow floor",
                                   "from": 1000000, "to": 250000}]
        assert entry["reason_owed"] is True
        assert any("version beside them did not" in n for n in entry["notes"])
        assert [c["seq"] for c in journals.pending(journal)] == [1]

    def test_a_logic_change_quotes_the_author_and_owes_nothing(
            self, strategies):
        """The host cannot say what a change to logic meant, so it quotes the
        person who can. And the user did not make this change, so asking them
        to explain it would be asking for a sentence they cannot write."""
        journal, record = self._journal(strategies)
        moved = {**record, "version": 3,
                 "changelog": {**record["changelog"],
                               2: "loosened the floor test",
                               3: "added an exit rule"}}
        entry = journals.observe_rule_change(journal, moved,
                                             _resolve(record, journal))
        assert entry["kind"] == "logic"
        assert entry["changelog"] == ["v2: loosened the floor test",
                                      "v3: added an exit rule"]
        assert entry["moved"] == []
        assert entry["reason_owed"] is False
        assert journals.pending(journal) == []

    def test_the_stamp_is_never_rewritten_and_the_baseline_moves(
            self, strategies):
        journal, record = self._journal(strategies)
        journals.observe_rule_change(journal, record, {"cash-floor": 250000})
        assert journal["strategy"]["values"] == {"cash-floor": 1000000}
        assert journals.baseline(journal)["values"] == {"cash-floor": 250000}
        # a second launch at the new value is not a second change
        assert journals.observe_rule_change(
            journal, record, {"cash-floor": 250000}) is None

    def test_an_earlier_change_is_never_touched_by_a_later_one(
            self, strategies):
        journal, record = self._journal(strategies)
        journals.observe_rule_change(journal, record, {"cash-floor": 250000})
        first = copy.deepcopy(journal["rule_changes"][0])
        journals.observe_rule_change(journal, record, {"cash-floor": 90000})
        assert journal["rule_changes"][0] == first
        assert [c["seq"] for c in journal["rule_changes"]] == [1, 2]

    def test_a_reason_is_written_once(self, strategies):
        journal, record = self._journal(strategies)
        journals.observe_rule_change(journal, record, {"cash-floor": 250000})
        journals.explain(journal, "rules", 1,
                         "Overrides on this kept working out.")
        assert journal["rule_changes"][0]["reason"] == \
            "Overrides on this kept working out."
        with pytest.raises(ValueError):
            journals.explain(journal, "rules", 1, "a better sentence")
        assert journal["rule_changes"][0]["reason"] == \
            "Overrides on this kept working out."
        assert journals.pending(journal) == []

    def test_a_blank_reason_is_refused_and_the_change_still_stands(
            self, strategies):
        """Validating the explanation is never a gate on the change itself.
        The change is on the books either way — that is the whole point."""
        journal, record = self._journal(strategies)
        journals.observe_rule_change(journal, record, {"cash-floor": 250000})
        with pytest.raises(ValueError):
            journals.explain(journal, "rules", 1, "   ")
        assert journal["rule_changes"][0]["reason"] is None
        assert len(journal["rule_changes"]) == 1

    def test_a_settings_version_moving_alone_is_recorded_and_owes_nothing(
            self, strategies):
        journal, record = self._journal(strategies)
        bumped = {**record, "values_version": 2}
        entry = journals.observe_rule_change(journal, bumped,
                                             _resolve(record, journal))
        assert entry["kind"] == "settings"
        assert entry["moved"] == []
        assert entry["reason_owed"] is False
        assert any("no value this journal uses changed" in n
                   for n in entry["notes"])

    def test_a_value_this_journal_gained_is_recorded_as_appearing(
            self, strategies):
        """A strategy that grows a setting picks up its shipped default even
        in a journal that already overrides something else, and that arrival
        is a change to what the rules demand."""
        journal, record = self._journal(strategies)
        entry = journals.observe_rule_change(
            journal, record, {"cash-floor": 1000000, "new-limit": 3})
        assert {"id": "new-limit", "label": "new-limit",
                "from": None, "to": 3} in entry["moved"]

    def test_the_record_survives_being_written_and_read_back(self,
                                                             strategies):
        journal, record = self._journal(strategies)
        journals.observe_rule_change(journal, record, {"cash-floor": 250000})
        journals.explain(journal, "rules", 1, "Widened deliberately.")
        journals.save(journal)
        back = journals.load(journal["id"])
        assert back["rule_changes"][0]["reason"] == "Widened deliberately."
        assert back["strategy"]["values"] == {"cash-floor": 1000000}


class TestWhoIsAskedToExplain:
    """A reason is owed only where the user is the one who retuned.

    Getting this backwards is worse than it looks: the banner has no dismiss
    and `explain` is write-once, so a user asked to justify an author's
    release has to invent a sentence, and the invented sentence stands
    forever in an append-only record.
    """

    def _journal(self, strategies):
        strategies("verdicts")
        return journal_for("verdicts")

    def test_an_authors_release_is_recorded_but_never_owed(self, strategies):
        journal, record = self._journal(strategies)
        shipped = {**record, "values_version": 2,
                   "changelog": {**record["changelog"],
                                 2: "loosened the floor"}}
        entry = journals.observe_rule_change(journal, shipped,
                                             {"cash-floor": 250000})
        assert entry["moved"]                       # it is on the record
        assert entry["reason_owed"] is False        # but nothing is asked
        assert journals.pending(journal) == []

    def test_a_hand_edit_that_left_the_version_alone_is_owed(self,
                                                             strategies):
        journal, record = self._journal(strategies)
        entry = journals.observe_rule_change(journal, record,
                                             {"cash-floor": 250000})
        assert entry["reason_owed"] is True
        assert [c["seq"] for c in journals.pending(journal)] == [1]


class TestTheDirectoryIsTheAddress:
    def test_a_journal_is_listed_under_the_folder_that_opens_it(
            self, strategies):
        """A row that resolves to a path that does not exist is a switcher
        entry that silently does nothing."""
        strategies("verdicts")
        journal, _ = journal_for("verdicts", "Growth")
        doc = store.read_json(journals.path_for(journal["id"]))
        doc["id"] = "something-else"
        store.write_json(journals.path_for(journal["id"]), doc)

        listed = journals.list_journals()
        assert [j["id"] for j in listed] == [journal["id"]]
        assert journals.load(listed[0]["id"])["id"] == journal["id"]

    def test_saving_writes_back_where_it_was_read_from(self, strategies):
        """Otherwise the record splits across two folders — reads keep coming
        from one and writes start landing in the other."""
        strategies("verdicts")
        journal, _ = journal_for("verdicts", "Growth")
        doc = store.read_json(journals.path_for(journal["id"]))
        doc["id"] = "elsewhere"
        store.write_json(journals.path_for(journal["id"]), doc)

        back = journals.load(journal["id"])
        back["securities"].append({"ticker": "ACME", "lots": []})
        journals.save(back)
        assert [p.name for p in journals.journals_dir().iterdir()] == \
            [journal["id"]]
        assert journals.load(journal["id"])["securities"][0]["ticker"] == \
            "ACME"


class TestEditingWhatTheJournalTellsItsStrategy:
    """The two write paths, at the engine level. What they record differs
    because the host can honestly say different things about them, and the
    difference has to hold even when both move in the same save."""

    def _journal(self, strategies):
        strategies("verdicts")
        return journal_for("verdicts")

    def test_setting_the_override_records_it_as_a_rule_change(self,
                                                              strategies):
        journal, record = self._journal(strategies)
        entry = journals.set_config(journal, record, {"cash-floor": 5})
        assert journal["config"] == {"cash-floor": 5}
        assert entry["kind"] == "settings"
        assert entry["reason_owed"] is True
        # Named by the record it sits on, because a second record now keeps
        # changes too and the screen that asks for a reason has to hand back
        # which one it is asking about. A copy, so saying so here can never
        # write that word into the append-only entry itself.
        assert journals.pending(journal) == [{**entry, "record": "rules"}]
        assert "record" not in entry

    def test_an_override_that_will_not_resolve_is_refused_whole(self,
                                                                strategies):
        """A journal left holding an override it cannot read refuses every
        verdict from then on, over a number the user was in the middle of
        fixing."""
        journal, record = self._journal(strategies)
        with pytest.raises(ValueError, match="does not declare"):
            journals.set_config(journal, record, {"nonsense": 1})
        assert journal["config"] == {}
        assert journal["rule_changes"] == []

    def _answered(self, strategies):
        strategies("awkward")
        return journal_for("awkward", inputs={"stance": "building",
                                              "keeps-reserve": True,
                                              "reserve": 1000.0})

    def test_answers_go_on_their_own_record_and_owe_nothing(self,
                                                            strategies):
        journal, record = self._answered(strategies)
        entry = journals.set_inputs(journal, record,
                                    {"stance": "building",
                                     "keeps-reserve": True,
                                     "reserve": 2000.0})
        assert entry["moved"] == [{"id": "reserve",
                                   "label": "Cash you keep back",
                                   "from": 1000.0, "to": 2000.0}]
        assert journal["rule_changes"] == []
        assert journals.pending(journal) == []

    def test_a_figure_the_host_works_out_is_never_stored_as_an_answer(
            self, strategies):
        """Free cash comes from this journal's cash record. A typed copy
        beside it would be two numbers about one thing, and which one gets
        read is whichever the next caller reaches for first — so the write
        refuses to hold one at all, and a journal that already does has it
        cleared onto the record the next time anything is saved."""
        journal, record = self._answered(strategies)
        journal["inputs"]["free-cash"] = 1000.0        # as an older journal
        entry = journals.set_inputs(journal, record,
                                    {"stance": "building",
                                     "keeps-reserve": True,
                                     "reserve": 1000.0,
                                     "free-cash": 9999.0})
        assert "free-cash" not in journal["inputs"]
        assert entry["moved"] == [{"id": "free-cash", "label": "Free cash",
                                   "from": 1000.0, "to": None}]

    def test_an_answer_that_did_not_move_records_nothing(self, strategies):
        journal, record = self._answered(strategies)
        assert journals.set_inputs(journal, record,
                                   dict(journal["inputs"])) is None
        assert journal["input_changes"] == []

    def test_a_cleared_answer_is_recorded_as_going_away(self, strategies):
        journal, record = self._answered(strategies)
        entry = journals.set_inputs(journal, record,
                                    {"stance": "building",
                                     "keeps-reserve": True})
        assert entry["moved"] == [{"id": "reserve",
                                   "label": "Cash you keep back",
                                   "from": 1000.0, "to": None}]
        assert journal["inputs"] == {"stance": "building",
                                     "keeps-reserve": True}


class TestAStrategyThatMovedOn:
    def test_an_input_the_strategy_dropped_does_not_block_every_verdict(
            self, strategies):
        """A journal outlives the strategy version it was created against.
        An answer to a question the strategy no longer asks is not the
        strategy's business — refusing every verdict over a key the user has
        no way to delete is a dead end with no way out of it."""
        from app import Api
        strategies("verdicts")
        journal, record = journal_for("verdicts", "Older")
        journal["inputs"] = {"a-question-since-dropped": "yes"}
        journal["securities"].append(
            entered({"ticker": "ACME", "lots": [], "notes": []},
                    fcf_ttm=5_000_000.0))
        journals.save(journal)

        state = Api().get_state()
        assert state["ok"], state
        d = state["securities"][0]["_decision"]
        assert d["produced_by"] == "strategy"
        assert d["state"]["id"] == "say-yes"


# What release the shipped bank is on, and the one after it. Read rather than
# written down: these tests are about a version MOVING, and they used to say
# `version=2` because the file happened to be on 1. The first real bump made
# "the next version" and "version 2" different numbers, and three tests that
# were checking a release is recorded quietly started checking that an
# unchanged version is not — which is a different assertion that also passes.
SHIPPED_VERSION = bank.definitions()["version"]
NEXT = object()          # `_defs(x__version=NEXT)` — whatever comes next


def _log(*sentences) -> dict:
    """A changelog covering the shipped release and the next one, so a test
    naming a release never has to know which number it landed on."""
    first, *rest = sentences
    log = {v: first for v in range(1, SHIPPED_VERSION + 1)}
    log[SHIPPED_VERSION + 1] = rest[0] if rest else "reworded"
    return log


def _defs(**moves):
    """The shipped definitions with named fields moved, as `bank.definitions`
    hands them over. Built from the real bank rather than a fixture, because
    what this record has to survive is a real edit to the real file, and a
    hand-made pair of dicts would agree with itself about the shape.
    """
    d = copy.deepcopy(bank.definitions())
    for path, value in moves.items():
        if value is NEXT:
            value = SHIPPED_VERSION + 1
        eid, _, field = path.partition("__")
        if field == "gone":
            d["entries"].pop(eid)
        elif field == "version":
            d["version"] = value
        else:
            half = "restates" if field.startswith("formula") else "states"
            key = {"formula": "how it is worked out",
                   "obs": "observations read",
                   "unit": "unit",
                   "name": "name",
                   "declines": "does not describe"}[field]
            d["entries"][eid][half][key] = value
    return d


class TestTheMeasureRecord:
    """Principle 3, applied to the other file that decides what an exit
    demands.

    A strategy says a holding fails below fifteen per cent; the metric bank
    says what the fifteen per cent is measured over, which kinds of company
    the measure cannot describe, and how many readings a breach of it needs.
    Editing the second moves every exit in every journal, and it is a file on
    the user's machine that this program re-reads whenever its mtime moves.
    The dangerous case is the same one as above and for the same reason:
    nothing about a five-year window quietly becoming a three-year one looks
    wrong afterwards.
    """

    def _journal(self, strategies):
        strategies("verdicts")
        journal, _ = journal_for("verdicts")
        return journal

    def test_a_new_journal_stamps_what_its_measures_mean_and_owes_nothing(
            self, strategies):
        journal = self._journal(strategies)
        stamp = journal["measures"]
        assert stamp["version"] == bank.definitions()["version"]
        assert stamp["entries"] == bank.definitions()["entries"]
        assert journal["measure_changes"] == []
        assert journals.observe_measure_change(
            journal, bank.definitions()) is None
        # and again, because this runs on every read of every screen
        assert journals.observe_measure_change(
            journal, bank.definitions()) is None
        assert journal["measure_changes"] == []

    def test_a_window_narrowed_in_place_is_caught_and_owed_a_reason(
            self, strategies):
        """The case this record exists for. Five annual observations becoming
        three is a different measure wearing the same name, it changes how
        much evidence every exit built on it needs, and the version beside it
        does not move when somebody edits the file."""
        journal = self._journal(strategies)
        entry = journals.observe_measure_change(
            journal, _defs(roic_median_5y__obs=3))
        assert entry["kind"] == "definitions"
        assert entry["moved"] == [{
            "id": "roic_median_5y",
            "name": "Return on invested capital, 5-year median",
            "field": "observations read", "from": 5, "to": 3}]
        assert entry["restated"] == []
        assert entry["reason_owed"] is True
        assert any("version beside them did not" in n for n in entry["notes"])
        assert [(c["record"], c["seq"]) for c in journals.pending(journal)] \
            == [("measures", 1)]

    def test_a_changed_formula_is_recorded_without_being_quoted(
            self, strategies):
        """The host can see the arithmetic move and has no way to know what
        the move meant. Saying it changed is the whole of what is honest, and
        a summary invented here would be the program claiming to have read
        something it cannot."""
        journal = self._journal(strategies)
        entry = journals.observe_measure_change(
            journal, _defs(roic_median_5y__formula="0d0d0d0d0d0d"))
        assert entry["moved"] == []
        assert entry["restated"] == [{
            "id": "roic_median_5y",
            "name": "Return on invested capital, 5-year median",
            "field": "how it is worked out", "digest": "0d0d0d0d0d0d"}]
        assert "from" not in entry["restated"][0]
        assert entry["reason_owed"] is True

    def test_a_release_says_what_changed_and_asks_nothing_of_the_user(
            self, strategies):
        """The other half of the reason rule. An author who bumps the version
        has already written the sentence; asking the user to explain somebody
        else's release would be asking for a line they have no way to write,
        into a record that is written once."""
        journal = self._journal(strategies)
        entry = journals.observe_measure_change(
            journal,
            _defs(roic_median_5y__obs=3, roic_median_5y__version=NEXT),
            _log("as shipped", "cut the window to three years"))
        assert entry["kind"] == "definitions and release"
        assert entry["changelog"] == [
            f"v{SHIPPED_VERSION + 1}: cut the window to three years"]
        assert entry["reason_owed"] is False
        assert journals.pending(journal) == []

    def test_a_release_that_moved_nothing_says_so_rather_than_nothing(
            self, strategies):
        """Wording is not on this record, so a release that only reworded is
        a release with no rows. It is still recorded — a reader has to be
        able to tell a version they are running from one they are not — and
        it says in as many words that what a verdict reads is where it was."""
        journal = self._journal(strategies)
        entry = journals.observe_measure_change(
            journal, _defs(x__version=NEXT), _log("as shipped", "reworded"))
        assert entry["kind"] == "release"
        assert (entry["moved"], entry["restated"]) == ([], [])
        assert entry["reason_owed"] is False
        assert any("nothing this record covers moved" in n
                   for n in entry["notes"])
        # and it is not a moment a frozen decision was decided before
        assert journals.measures_moved_at(journal) == []

    def test_a_measure_that_is_gone_is_recorded_as_gone(self, strategies):
        journal = self._journal(strategies)
        entry = journals.observe_measure_change(
            journal, _defs(roic_median_5y__gone=True))
        assert entry["removed"] == [{
            "id": "roic_median_5y",
            "name": "Return on invested capital, 5-year median"}]
        assert entry["reason_owed"] is True
        assert journals.measures_baseline(journal)["entries"].get(
            "roic_median_5y") is None

    def test_a_measure_that_is_new_is_recorded_as_new(self, strategies):
        """A measure arriving is not neutral: it is a figure that can be
        cited from the next verdict onward and was citable by none of the
        ones already frozen. It carries its whole definition, because that is
        what the fold has to install — there is no earlier state to move it
        from."""
        journal = self._journal(strategies)
        arrived = copy.deepcopy(bank.definitions())
        arrived["entries"]["cash_burn_years"] = {
            "states": {"name": "Years of cash left", "unit": "years"},
            "restates": {"how it is worked out": "abcabcabcabc"}}
        entry = journals.observe_measure_change(journal, arrived)
        assert [(a["id"], a["name"]) for a in entry["added"]] == [
            ("cash_burn_years", "Years of cash left")]
        assert entry["added"][0]["definition"] == \
            arrived["entries"]["cash_burn_years"]
        assert (entry["moved"], entry["restated"]) == ([], [])
        assert journals.measures_baseline(journal)["entries"] == \
            arrived["entries"]

    def test_what_the_journal_last_ran_under_is_folded_not_stored(
            self, strategies):
        """The stamp is fifty kilobytes. Carrying a whole before and after on
        every entry would put half a megabyte of duplicated definitions in a
        file that belongs to the user, so each entry holds only what moved and
        the state is folded from the stamp. The proof is that the fold agrees
        with what was last observed — twice, over two changes, in both halves.
        """
        journal = self._journal(strategies)
        journals.observe_measure_change(journal, _defs(roic_median_5y__obs=3))
        # Both halves in the second change, because they fold differently and
        # the one that only ever moves a digest is the one a fold can drop
        # while every stated field still lands. What that costs is not a lost
        # entry — it is the same change re-recorded on every read of every
        # screen, which is the record filling up with one edit.
        second = _defs(roic_median_5y__obs=3, pe_ttm__unit="percent",
                       roic_median_5y__formula="0d0d0d0d0d0d")
        entry = journals.observe_measure_change(journal, second)
        assert entry["moved"] and entry["restated"]
        assert journals.measures_baseline(journal)["entries"] == \
            second["entries"]
        # and having caught up, it stays caught up
        assert journals.observe_measure_change(journal, second) is None
        assert journals.observe_measure_change(journal, second) is None
        assert len(journal["measure_changes"]) == 2
        assert sum(len(str(c)) for c in journal["measure_changes"]) < 2000

    def test_an_earlier_change_is_never_touched_by_a_later_one(self,
                                                               strategies):
        journal = self._journal(strategies)
        journals.observe_measure_change(journal, _defs(roic_median_5y__obs=3))
        first = copy.deepcopy(journal["measure_changes"][0])
        journals.observe_measure_change(journal, _defs(roic_median_5y__obs=2))
        assert journal["measure_changes"][0] == first
        assert [c["seq"] for c in journal["measure_changes"]] == [1, 2]

    def test_prose_a_reader_reads_is_not_a_change_to_what_is_demanded(
            self, strategies):
        """Stated rather than left to be inferred from a silence. Putting a
        wording pass over seventy-four entries onto every journal's record
        would bury the one retuning the record exists to surface."""
        journal = self._journal(strategies)
        edited = copy.deepcopy(bank.load_bank())
        for e in edited["entries"]:
            e["explanation"]["plain"] = "Rewritten."
            e["explanation"]["misfires"] = "Rewritten."
        moved = {"version": edited.get("version"),
                 "entries": {str(e.get("id")): bank._definition(e)
                             for e in edited["entries"]}}
        assert journals.observe_measure_change(journal, moved) is None

    def test_the_record_survives_being_written_and_read_back(self,
                                                             strategies):
        journal = self._journal(strategies)
        journals.observe_measure_change(journal, _defs(roic_median_5y__obs=3))
        journals.explain(journal, "measures", 1, "One year was carrying it.")
        journals.save(journal)
        back = journals.load(journal["id"])
        assert back["measure_changes"] == journal["measure_changes"]
        assert back["measures"] == journal["measures"]
        assert journals.pending(back) == []

    def test_a_reason_is_written_once_on_this_record_too(self, strategies):
        journal = self._journal(strategies)
        journals.observe_measure_change(journal, _defs(roic_median_5y__obs=3))
        journals.explain(journal, "measures", 1, "One year was carrying it.")
        with pytest.raises(ValueError, match="append-only"):
            journals.explain(journal, "measures", 1, "a better sentence")
        assert journal["measure_changes"][0]["reason"] == \
            "One year was carrying it."

    def test_a_reason_lands_on_the_record_it_was_asked_about(self,
                                                             strategies):
        """Two records, two sequences, and a `1` in each. A reason written
        against the wrong one would attach a sentence about a threshold to a
        changed formula, in a record that cannot be corrected afterwards."""
        journal = self._journal(strategies)
        journals.observe_measure_change(journal, _defs(roic_median_5y__obs=3))
        with pytest.raises(ValueError, match="no recorded rule change 1"):
            journals.explain(journal, "rules", 1, "wrong record")
        with pytest.raises(ValueError, match="not a record this journal"):
            journals.explain(journal, "measurements", 1, "no such record")
        assert journal["measure_changes"][0]["reason"] is None

    def test_both_records_are_asked_for_their_reasons_together(
            self, strategies):
        """Owing a sentence is one obligation. A banner that knew about only
        one record would leave the other quietly unexplained, which is the
        state this whole thing exists to make impossible."""
        strategies("verdicts")
        journal, record = journal_for("verdicts")
        journals.observe_rule_change(journal, record, {"cash-floor": 250000})
        journals.observe_measure_change(journal, _defs(roic_median_5y__obs=3))
        assert [(c["record"], c["seq"]) for c in journals.pending(journal)] \
            == [("rules", 1), ("measures", 1)]

    def test_a_journal_older_than_this_record_says_so_and_claims_nothing(
            self, strategies):
        """The one case with no honest answer available. Carrying today's
        definitions backwards would claim the journal always ran under them;
        reporting seventy-four measures as newly added would claim it never
        had any. It has neither, so it says so once and starts from here."""
        journal = self._journal(strategies)
        journal.pop("measures")
        journal["measure_changes"] = []

        entry = journals.observe_measure_change(journal, bank.definitions())
        assert entry["kind"] == "first seen"
        assert (entry["added"], entry["moved"], entry["restated"]) \
            == ([], [], [])
        assert entry["reason_owed"] is False
        assert journals.measures_moved_at(journal) == []
        assert any("older than the record" in n for n in entry["notes"])
        assert journal["measures"]["entries"] == bank.definitions()["entries"]

        # and from here it is an ordinary journal
        assert journals.observe_measure_change(
            journal, bank.definitions()) is None
        after = journals.observe_measure_change(
            journal, _defs(roic_median_5y__obs=3))
        assert after["seq"] == 2 and after["reason_owed"] is True

    def test_a_move_is_a_moment_a_frozen_decision_can_be_read_against(
            self, strategies):
        """What a journal tells the user, and where. Not a banner on launch —
        a line beside the decision whose figures are the ones that moved, which
        needs the days the definitions actually moved and nothing else."""
        journal = self._journal(strategies)
        journals.observe_measure_change(journal, _defs(x__version=NEXT),
                                        _log("a", "reworded"))
        journals.observe_measure_change(
            journal, _defs(roic_median_5y__obs=3, x__version=NEXT))
        assert journals.measures_moved_at(journal) == \
            [journal["measure_changes"][1]["seen"]]
