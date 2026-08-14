"""A day kept on purpose — and every way keeping one could quietly go wrong.

Nothing in here crashes when it breaks. A snapshot that re-rendered through
today's bank would read as though it had always said this. One that could be
dated by its caller would let a baseline be chosen after the answer was known.
One that vanished on a discard would let the inconvenient day be the one that
disappears. One that went with a removed candidate would take six months of
watching with it and report "removed". And a snapshot that could not say
which rules produced it is a verdict with no question attached — readable,
plausible, and worth nothing the first time a threshold moves.

The other half of what is pinned here is that a saved snapshot and a purchase
snapshot are ONE object. Two builders would be two sets of refusals, and the
comparison this record exists to make possible is only sound if a Tuesday
saved and a Friday bought are the same shape read the same way.
"""

import copy

import pytest
from conftest import balance_face, dur, filing, inst

from engine import (backup, dated, facts_store, journals, portfolio,
                    price_store, snapshots)

from app import Api

ANSWERS = {"free-cash": "40000", "stance": "building",
           "keeps-reserve": "false", "first-buy": "4"}


@pytest.fixture
def api(strategies):
    strategies("awkward")
    a = Api()
    assert a.create_journal("Kept", "awkward", dict(ANSWERS))["ok"]
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


def save(api, ticker="SYN", note=""):
    r = api.save_snapshot(ticker, note)
    assert r["ok"], r
    return r


# -- one object, not two ------------------------------------------------------

class TestASavedSnapshotIsAPurchaseSnapshotWithoutThePurchase:
    """The generalisation, asserted rather than assumed.

    If these two ever come apart, everything downstream that reads "a frozen
    evaluation" has to learn which kind it is holding — and the first reader
    to forget is the one that silently reports the wrong half.
    """

    def test_both_are_built_by_one_function(self):
        """Asserted as an absence: there is no second builder to drift.

        `portfolio.freeze` is called by the purchase path, the sale path and
        the snapshot record. A private copy anywhere would be a second set of
        refusals, and the second set is always the one missing a check.
        """
        import inspect
        src = inspect.getsource(portfolio)
        assert src.count("def freeze(") == 1
        assert "def _snapshot(" not in src, \
            "the freeze was copied rather than shared"
        assert "portfolio.freeze(" in inspect.getsource(snapshots)

    def test_a_saved_snapshot_carries_the_same_keys_as_a_purchases(self, api):
        idea(api)
        save(api)
        kept = snapshots.standing(security())[0]["snapshot"]
        assert api.open_position("SYN", 10, 15.0, None, "recording")["ok"]
        bought = portfolio.lots(security(), "buy")[0]["snapshot"]
        assert set(kept) == set(bought), \
            "a saved snapshot and a purchase snapshot are different shapes"

    def test_a_bare_number_cannot_be_frozen_into_one_either(self):
        """The refusal is on the builder, so it covers every caller — the
        one that exists now and the one written next year."""
        with pytest.raises(ValueError) as e:
            portfolio.freeze({}, {"current_ratio": 1.4}, None,
                             {"basis": "live", "as_of": "2026-08-01"})
        assert "dataview.qualified" in str(e.value)

    def test_prose_cannot_be_frozen_where_a_thesis_belongs(self):
        with pytest.raises(ValueError) as e:
            portfolio.freeze({}, {}, None,
                             {"basis": "live", "as_of": "2026-08-01"},
                             thesis="I like the toll road.")
        assert "off the thesis record" in str(e.value)


# -- it is always today -------------------------------------------------------

class TestASnapshotCannotBeDated:
    """The baseline problem. "Changed since your last snapshot" is only worth
    anything if the snapshot could not be chosen after today's answer was
    known — which is the same failure as retuning a threshold at the moment
    it is about to fire, and gets the same answer: unavailable, not
    discouraged.
    """

    def test_there_is_no_parameter_that_would_date_one(self):
        import ast
        import inspect
        import pathlib
        taking = inspect.signature(snapshots.take).parameters
        for name in ("as_of", "when", "date", "opened", "day", "on"):
            assert name not in taking, \
                f"snapshots.take accepts {name} — a snapshot can be backdated"
        # Read off the source, because @guarded replaces the signature with
        # (*a, **kw) and a test asking the wrapper would pass whatever the
        # method took.
        tree = ast.parse(pathlib.Path(
            inspect.getsourcefile(Api)).read_text(encoding="utf-8"))
        saving = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef)
                      and n.name == "save_snapshot")
        named = [a.arg for a in saving.args.args + saving.args.kwonlyargs]
        assert named == ["self", "ticker", "note"], named

    def test_a_rebuilt_evaluation_is_refused_outright(self, api):
        """Not ignored, and not quietly recorded as live. A reconstruction
        saved as a snapshot would be a day nobody looked at, presented as one
        somebody did."""
        idea(api)
        s = security()
        with pytest.raises(ValueError) as e:
            snapshots.take(journal(), s, {"state": {"id": "x"}},
                           values={}, price_seen=None,
                           evaluation={"basis": "reconstructed",
                                       "as_of": "2019-04-04"})
        assert "2019-04-04" in str(e.value)
        assert not s.get(snapshots.KEY), \
            "the refusal happened after something was appended"

    def test_the_day_it_belongs_to_is_the_day_it_was_written(self, api,
                                                             written_on):
        """One field, not two. A `taken` date beside `recorded` would be two
        structures describing one moment, and the half that goes missing is
        always the qualifying half."""
        idea(api)
        with written_on("2026-03-04"):
            save(api)
        row = snapshots.summaries(security())[0]
        assert row["day"] == "2026-03-04"
        entry = snapshots.standing(security())[0]
        assert dated.day_of(entry) == "2026-03-04"
        assert not any(k in entry for k in ("date", "taken", "as_of"))

    def test_a_caller_cannot_say_when_one_was_written(self):
        s = {}
        for field in ("recorded", "seq"):
            with pytest.raises(ValueError):
                dated.append(s, snapshots.KEY, {"kind": "taken",
                                                field: "2020-01-01"})
        assert s == {}


# -- it is never recomputed ---------------------------------------------------

class TestItIsFrozen:
    def test_it_does_not_move_when_the_measures_are_redefined(self, api,
                                                              strategies):
        """The failure this record exists against: a saved day that renders
        through today's bank reads as though it had always said this, and the
        one thing a person wanted from it — what did it look like THEN — is
        the one thing it can no longer answer."""
        idea(api)
        save(api)
        before = copy.deepcopy(snapshots.standing(security())[0]["snapshot"])

        doc = journal()
        stamped = doc["measures"]["entries"]
        moved = next(iter(stamped))
        stamped[moved]["states"]["name"] = "Something else entirely"
        journals.save(doc)

        after = snapshots.standing(security())[0]["snapshot"]
        assert after == before

    def test_the_whole_decision_is_kept_and_not_a_summary_of_it(self, api):
        """A row saying "Cheap enough" teaches nothing six months later. The
        evidence is the record; the state is the headline on it."""
        idea(api)
        save(api)
        snap = snapshots.standing(security())[0]["snapshot"]
        reason = (snap["decision"] or {}).get("reason") or {}
        assert reason.get("evidence"), "no evidence was frozen"
        assert snap["strategy"]["id"] == "awkward"
        assert snap["evaluation"]["basis"] == "live"

    def test_the_record_is_isolated_from_the_caller_that_wrote_it(self, api):
        """A live dict handed in and kept by reference is a frozen record
        that keeps changing after it was written, invisibly."""
        idea(api)
        s = security()
        decision = {"state": {"id": "x", "name": "Fine"}, "reason": {},
                    "strategy": {"id": "awkward"}}
        snapshots.take(journal(), s, decision, values={}, price_seen=None,
                       evaluation={"basis": "live", "as_of": "2026-08-14"})
        decision["state"]["name"] = "Rewritten afterwards"
        kept = snapshots.standing(s)[0]["snapshot"]
        assert kept["decision"]["state"]["name"] == "Fine"


# -- which rules produced it --------------------------------------------------

class TestItSaysWhichRulesWereInForce:
    """A snapshot that cannot say what was behind it is a number without a
    question. The old answer was a wall-clock string compared against the
    change record's stamps — which is a text sort over two calendars now that
    both carry an offset, and it fails towards saying nothing has moved.
    """

    def test_it_records_where_both_change_records_stood(self, api):
        idea(api)
        save(api)
        where = snapshots.standing(security())[0]["snapshot"]["changes_recorded"]
        assert set(where) == set(journals.record_words()), \
            "a change record exists that a snapshot does not position itself in"
        assert where == journals.changes_recorded(journal())

    def test_a_third_change_record_is_carried_with_nothing_here_to_edit(self):
        """The declaration and its enforcement are one path: RECORDS is the
        table, and this is read straight off it. A record added there and
        forgotten here is the failure being ruled out."""
        j = {"rule_changes": [1, 2, 3], "measure_changes": [1]}
        assert journals.changes_recorded(j) == {"rules": 3, "measures": 1}
        table = dict(journals.RECORDS)
        try:
            journals.RECORDS["invented"] = {
                "key": "invented_changes",
                "words": {"noun": "invented change", "means": "nothing"}}
            assert journals.changes_recorded(
                {"invented_changes": [1, 1]})["invented"] == 2
        finally:
            journals.RECORDS.clear()
            journals.RECORDS.update(table)

    @pytest.mark.parametrize("write", ("purchase", "sale", "snapshot",
                                       "backfill"))
    def test_every_path_that_freezes_one_records_it(self, api, write):
        """The pairing CLAUDE.md asks for where a declaration cannot enforce
        itself. `freeze` accepts None so entries written before this existed
        stay honest about not knowing — which means nothing stops a NEW
        writer omitting it except this test, and it fails the moment one is
        added without a case here.
        """
        idea(api)
        if write == "snapshot":
            save(api)
            frozen = [snapshots.standing(security())[0]["snapshot"]]
        elif write == "backfill":
            assert api.record_backfill("SYN", [
                {"kind": "buy", "date": "2025-02-03", "shares": 5,
                 "price": 11.0}])["ok"]
            frozen = [lot["snapshot"] for lot in security()["lots"]]
        else:
            assert api.open_position("SYN", 10, 15.0, None, "recording")["ok"]
            if write == "sale":
                assert api.sell_shares("SYN", "Hit valuation", 30.0,
                                       None)["ok"]
            frozen = [lot["snapshot"] for lot in security()["lots"]]
        assert frozen
        for snap in frozen:
            assert snap["changes_recorded"] == {"rules": 0, "measures": 0}, \
                f"the {write} path froze a record that cannot say what " \
                "produced it"

    def test_a_made_up_position_is_refused_and_absence_is_not(self):
        """None is a real answer — every entry frozen before this existed
        says exactly that, and nothing invents one for them. A dict that
        looks like an answer and is not is the thing worth refusing."""
        live = {"basis": "live", "as_of": "2026-08-14"}
        assert portfolio.freeze({}, {}, None, live)["changes_recorded"] is None
        for bad in ({"rules": "3"}, {"rules": -1}, {"rules": True}, "3"):
            with pytest.raises(ValueError) as e:
                portfolio.freeze({}, {}, None, live, changes_recorded=bad)
            assert "changes_recorded" in str(e.value)


# -- discarding ---------------------------------------------------------------

class TestDiscardingIsAnEntryAndNotADeletion:
    def test_a_discarded_snapshot_stops_standing_and_stays_on_the_record(
            self, api):
        """The one somebody would most want gone without trace is the one
        showing what they saw before doing something they now regret. So it
        stops counting and it never stops having existed."""
        idea(api)
        first = save(api, note="watching")["seq"]
        save(api, note="still watching")
        assert len(snapshots.standing(security())) == 2

        assert api.discard_snapshot("SYN", first, "took it twice")["ok"]
        kept = snapshots.standing(security())
        assert len(kept) == 1 and kept[0]["seq"] != first

        gone = next(e for e in snapshots.history(security())
                    if e["seq"] == first)
        assert gone["discarded"], "the discard left no mark"
        assert gone["discarded"]["reason"] == "took it twice"
        assert gone["snapshot"]["decision"], \
            "discarding threw the record away rather than retiring it"

    def test_the_number_it_was_written_under_is_never_reused(self, api):
        """A seq that came round again would let a later discard land on an
        earlier snapshot."""
        idea(api)
        first = save(api)["seq"]
        api.discard_snapshot("SYN", first)
        assert save(api)["seq"] != first

    def test_a_discarded_snapshot_cannot_be_discarded_again(self, api):
        idea(api)
        seq = save(api)["seq"]
        assert api.discard_snapshot("SYN", seq)["ok"]
        again = api.discard_snapshot("SYN", seq)
        assert again["ok"] is False and "already discarded" in again["error"]
        assert len(security()[snapshots.KEY]) == 2, \
            "a refused discard still appended"

    def test_discarding_something_that_was_never_saved_is_refused(self, api):
        idea(api)
        r = api.discard_snapshot("SYN", 99)
        assert r["ok"] is False and "99" in r["error"]

    def test_what_changed_since_is_measured_against_a_standing_one(self, api):
        idea(api)
        older = save(api)["seq"]
        newer = save(api)["seq"]
        assert snapshots.latest(security())["seq"] == newer
        api.discard_snapshot("SYN", newer)
        assert snapshots.latest(security())["seq"] == older
        api.discard_snapshot("SYN", older)
        assert snapshots.latest(security()) is None

    def test_there_is_no_verb_that_removes_one(self):
        for verb in ("edit", "delete", "remove", "replace", "update"):
            assert not hasattr(snapshots, verb), \
                f"snapshots.{verb} exists"


# -- what a saved day costs the candidate it belongs to -----------------------

class TestASavedDayCannotBeLostByAccident:
    def test_a_candidate_carrying_one_is_not_removed(self, api):
        """`has_history` guarded lots and nothing else, and a saved snapshot
        is the identical frozen verdict with no lot under it. Six months of
        watching would have gone on a click that reports "removed"."""
        idea(api)
        save(api)
        r = api.remove_security("SYN")
        assert r["ok"] is False and "snapshot" in r["error"]
        assert security(), "the security went anyway"

    def test_discarding_them_all_makes_it_removable_again(self, api):
        """Refusing is only the right answer because it is not a dead end."""
        idea(api)
        seq = save(api)["seq"]
        assert api.discard_snapshot("SYN", seq)["ok"]
        assert api.remove_security("SYN")["ok"]
        assert all(s["ticker"] != "SYN" for s in journal()["securities"])

    def test_a_candidate_with_nothing_kept_still_removes(self, api):
        idea(api)
        assert api.remove_security("SYN")["ok"]


# -- travelling ---------------------------------------------------------------

class TestItIsTheJournalsSoItTravels:
    def test_an_export_carries_it_whole(self, api, tmp_path):
        """Anything not inside the journal is lost on export. Asserted off
        the file rather than through a reader, because a reader that dropped
        it would agree with a writer that dropped it."""
        idea(api)
        save(api, note="the day I started watching")
        dest = backup.export_bundle(tmp_path)
        import json
        carried = json.loads(dest.read_text())["journals"][0]
        s = next(x for x in carried["securities"] if x["ticker"] == "SYN")
        kept = s[snapshots.KEY]
        assert len(kept) == 1
        assert kept[0]["note"] == "the day I started watching"
        assert kept[0]["snapshot"]["decision"]["reason"]["evidence"]

    def test_the_confirmation_screen_counts_them(self, api, tmp_path):
        """A record missing from the screen somebody confirms an import
        against reads as one the bundle does not carry."""
        idea(api)
        seq = save(api)["seq"]
        dest = backup.export_bundle(tmp_path / "one.json")
        assert backup.inspect_bundle(dest)["snapshots"] == 1
        api.discard_snapshot("SYN", seq)
        dest = backup.export_bundle(tmp_path / "two.json")
        assert backup.inspect_bundle(dest)["snapshots"] == 0


# -- reading it back ----------------------------------------------------------

class TestReadingTheRecord:
    def test_an_entry_this_build_cannot_place_makes_the_whole_read_refuse(
            self, api):
        """The case is a journal restored from a bundle a later version
        wrote. Skipping is dangerous in both directions at once: an
        unrecognised discard leaves a snapshot standing that its owner
        retired, and an unrecognised entry disappears from a list presenting
        itself as complete."""
        idea(api)
        save(api)
        doc = journal()
        s = next(x for x in doc["securities"] if x["ticker"] == "SYN")
        dated.append(s, snapshots.KEY, {"kind": "pinned"})
        with pytest.raises(ValueError) as e:
            snapshots.history(s)
        assert "later one" in str(e.value)

    def test_a_discard_naming_nothing_makes_the_read_refuse(self, api):
        idea(api)
        save(api)
        s = security()
        dated.append(s, snapshots.KEY, {"kind": "discarded", "discards": 404})
        with pytest.raises(ValueError) as e:
            snapshots.history(s)
        assert "404" in str(e.value)

    def test_the_list_ships_rows_and_never_the_records(self, api):
        """One frozen evaluation is kilobytes of evidence and `get_state`
        runs on every render. A year of watching thirty names would put tens
        of megabytes through it."""
        idea(api)
        save(api, note="worth a look")
        state = api.get_state()
        s = next(x for x in state["securities"] if x["ticker"] == "SYN")
        row = s["_snapshots"][0]
        assert row["note"] == "worth a look" and row["day"]
        assert "snapshot" not in row and "decision" not in row
        import json
        assert len(json.dumps(row)) < 1000, json.dumps(row)

    def test_the_record_itself_comes_back_on_request(self, api):
        idea(api)
        seq = save(api)["seq"]
        r = api.get_snapshot("SYN", seq)
        assert r["ok"]
        assert r["entry"]["snapshot"]["decision"]["reason"]["evidence"]
        assert api.get_snapshot("SYN", 99)["ok"] is False

    def test_a_row_is_read_off_what_was_frozen_and_never_worked_out_again(
            self, api):
        """A list that looked a state's name up in the strategy standing
        today would be a second opinion about a record whose whole purpose is
        that it has only one."""
        idea(api)
        save(api)
        s = security()
        s[snapshots.KEY][0]["snapshot"]["decision"]["state"]["name"] = "Kept"
        assert snapshots.summaries(s)[0]["state"] == "Kept"


# -- it is not a gate ---------------------------------------------------------

class TestNothingIsBlocked:
    def test_a_name_with_nothing_fetched_is_still_kept(self, api):
        """Nothing was fetched, so most of the evidence is absent — and the
        day somebody first looked at a name is exactly the day worth keeping.
        The tool records; it never refuses to."""
        api.add_security("DARK", "Never Fetched Ltd")
        assert api.save_snapshot("DARK")["ok"]
        snap = snapshots.standing(security("DARK"))[0]["snapshot"]
        assert snap["decision"]["state"]["name"]

    def test_a_day_the_strategy_could_not_be_asked_is_still_kept(
            self, api, strategies):
        """The hardest case for a record to be honest about, and the one an
        implementation is most likely to refuse: the strategy this journal is
        stamped with is not on this machine, so the verdict is the host's own
        saying exactly that. Refusing here would mean the only days you could
        keep are the ones nothing went wrong on."""
        import shutil as sh
        idea(api)
        sh.rmtree(strategies.root / "awkward")
        r = api.save_snapshot("SYN")
        assert r["ok"], r
        snap = snapshots.standing(security("SYN"))[0]["snapshot"]
        assert snap["decision"]["produced_by"] == "host"
        assert "not installed" in snap["decision"]["reason"]["summary"]

    def test_two_snapshots_of_an_unchanged_day_are_both_kept(self, api):
        """Not deduplicated. Two identical readings on two days are two
        facts, and "nothing has moved in three months" is only readable if
        the unchanged ones are there."""
        idea(api)
        save(api)
        save(api)
        assert len(snapshots.standing(security())) == 2
