"""The list a journal works from: reading one in, keeping it, serving it.

What would fail silently here, and is therefore pinned:

- **A pasted line that quietly does not become a ticker.** A list of thirty
  that became twenty-nine looks exactly like a screen that returned
  twenty-nine, and the missing name is one nobody will ever buy or know they
  skipped. Every line either yields exactly one ticker or comes back named.
- **Which list is "current".** Two dates describe an import and they come
  apart the moment somebody enters on Friday a list they pulled on Monday.
  A reconstruction walks the day it was imported; a rule reads the day it was
  pulled. Swapping them is invisible and wrong.
- **A holding period counted from a date that moved backwards.** `listed_on`
  is the freshest pull date carrying a name, so importing an old list cannot
  shorten a position's year under it.
- **Absence reading as a settled answer.** "Not on your list" and "you have
  no list" are different things, and a False for the second would be the
  first said confidently.
- **A strategy that screens for itself noticing any of this.** The facts are
  served to every context; the blocked state and the screen are not.
"""

import pytest

from engine import backup, bank, contract, context, dated, journals, lists
from engine import strategy_loader, strategy_values


# -- reading a paste ---------------------------------------------------------

class TestReadingWhatSomebodyPasted:
    """The screen gives an HTML table; a browser copy of it arrives
    tab-separated with the ticker in the second column. One ticker per line is
    the other thing people do. Both work; nothing else is guessed at."""

    def test_a_pasted_table_takes_the_ticker_column(self):
        pasted = ("Company Name\tTicker\tMarket Cap (in millions)\n"
                  "Acme Diagnostics Inc\tACME\t1,204.1\n"
                  "Briar Foods Group\tBRIA\t880.0\n")
        assert lists.read(pasted) == {"tickers": ["ACME", "BRIA"],
                                      "unreadable": []}

    def test_one_symbol_per_line_works_too(self):
        assert lists.read("acme\nBRIA\n\nCWTH\n")["tickers"] == [
            "ACME", "BRIA", "CWTH"]

    def test_commas_and_semicolons_are_read_as_separators(self):
        assert lists.read("ACME, BRIA; CWTH")["tickers"] == [
            "ACME", "BRIA", "CWTH"]

    def test_the_order_pasted_is_the_order_kept(self):
        assert lists.read("CWTH\nACME\nBRIA")["tickers"] == [
            "CWTH", "ACME", "BRIA"]

    def test_a_repeat_is_kept_once(self):
        assert lists.read("ACME\nBRIA\nACME")["tickers"] == ["ACME", "BRIA"]

    def test_a_line_it_cannot_read_comes_back_named(self):
        """The whole point. It is never dropped and never guessed at."""
        got = lists.read("ACME\nsome prose that is not a row at all\nBRIA")
        assert got["tickers"] == ["ACME", "BRIA"]
        assert got["unreadable"] == ["some prose that is not a row at all"]

    def test_a_row_with_two_ticker_shaped_fields_and_no_column_is_refused(self):
        """Two candidates and no second column to break the tie is exactly
        the case where guessing produces a plausible wrong list."""
        got = lists.read("ACME\tBRIA")
        # Field 1 is ticker-shaped, so the column rule settles it rather than
        # the count — that is the documented layout and it wins.
        assert got["tickers"] == ["BRIA"]
        got = lists.read("Acme Diagnostics Incorporated\tACME BRIA CWTH")
        assert got["tickers"] == [] and got["unreadable"]

    def test_the_tables_own_heading_is_not_a_company(self):
        assert lists.read("Company Name\tTicker\tPrice From\nX\tACME\t1")[
            "tickers"] == ["ACME"]

    def test_nothing_at_all_reads_as_nothing(self):
        assert lists.read("") == {"tickers": [], "unreadable": []}
        assert lists.read(None) == {"tickers": [], "unreadable": []}

    def test_a_symbol_longer_than_any_real_one_is_refused(self):
        """Seven characters covers every US listing including a class
        suffix. Widening it would let a one-word company name on its own
        line read as a ticker, which is the silent failure this guards."""
        assert lists.read("MARLBROOK")["unreadable"] == ["MARLBROOK"]


# -- writing one -------------------------------------------------------------

class TestRecordingAnImport:

    def test_it_keeps_what_was_pulled_and_when(self):
        j = {}
        entry = lists.record(j, "2026-08-01", ["acme", "BRIA"], 1e9)
        assert entry["pulled_on"] == "2026-08-01"
        assert entry["tickers"] == ["ACME", "BRIA"]
        assert entry["floor"] == 1e9
        assert j[lists.KEY] == [entry]

    def test_the_day_it_was_written_is_the_hosts_and_not_the_callers(self):
        """`recorded` cannot be supplied, so an import cannot be backdated —
        which is what makes "what did this journal know then" answerable."""
        j = {}
        entry = lists.record(j, "2020-01-01", ["ACME"])
        assert entry["recorded"] == dated.stamp()
        assert dated.day_of(entry) != entry["pulled_on"]
        with pytest.raises(ValueError):
            dated.append(j, lists.KEY, {"pulled_on": "2020-01-01",
                                        "recorded": "2020-01-01"})

    def test_a_pull_date_is_required_and_must_be_a_date(self):
        for bad in (None, "", "last tuesday", "2026-8-1"):
            with pytest.raises(ValueError, match="YYYY-MM-DD"):
                lists.record({}, bad, ["ACME"])

    def test_a_pull_date_in_the_future_is_refused(self):
        with pytest.raises(ValueError, match="has not happened yet"):
            lists.record({}, "2099-01-01", ["ACME"])

    def test_an_empty_list_is_refused(self):
        with pytest.raises(ValueError, match="no names"):
            lists.record({}, "2026-08-01", [])

    def test_a_ticker_it_cannot_read_is_refused_outright(self):
        with pytest.raises(ValueError, match="not a ticker"):
            lists.record({}, "2026-08-01", ["ACME", "not a ticker"])

    def test_nothing_is_ever_edited(self):
        j = {}
        lists.record(j, "2026-01-05", ["ACME"])
        lists.record(j, "2026-08-01", ["BRIA"])
        assert [e["pulled_on"] for e in j[lists.KEY]] == ["2026-01-05",
                                                          "2026-08-01"]
        assert j[lists.KEY][0]["tickers"] == ["ACME"]


# -- reading them back -------------------------------------------------------

class TestWhichListIsCurrent:

    def test_the_one_imported_most_recently_wins(self):
        """Not the newest pull date. A user who imports an old list by
        mistake has most recently said that this is their list, and the fix
        is to import the right one — which is one action and leaves both on
        the record. The alternative makes the last thing you did not
        necessarily the thing that took effect."""
        j = {}
        lists.record(j, "2026-06-01", ["ACME"])
        lists.record(j, "2025-01-05", ["BRIA"])          # an older pull
        assert lists.current(j)["pulled_on"] == "2025-01-05"

    def test_no_list_is_none_rather_than_empty(self):
        assert lists.current({}) is None
        assert lists.on_current({}, "ACME") is None
        assert lists.listed_on({}, "ACME") is None

    def test_membership_is_a_yes_or_no_only_where_there_is_a_list(self):
        j = {}
        lists.record(j, "2026-08-01", ["ACME"])
        assert lists.on_current(j, "acme") is True
        assert lists.on_current(j, "BRIA") is False


class TestWhenANameentWasLastChosen:

    def test_it_is_the_freshest_pull_date_carrying_the_name(self):
        j = {}
        lists.record(j, "2025-08-04", ["ACME", "BRIA"])
        lists.record(j, "2026-08-03", ["ACME"])
        assert lists.listed_on(j, "ACME") == "2026-08-03"
        assert lists.listed_on(j, "BRIA") == "2025-08-04"
        assert lists.listed_on(j, "CWTH") is None

    def test_importing_an_older_list_cannot_move_it_backwards(self):
        """A holding period counts from this. If it could go backwards, a
        position's year could lengthen or shorten under it because of
        something the user did to a different list."""
        j = {}
        lists.record(j, "2026-08-03", ["ACME"])
        assert lists.listed_on(j, "ACME") == "2026-08-03"
        lists.record(j, "2024-01-01", ["ACME"])
        assert lists.listed_on(j, "ACME") == "2026-08-03"


class TestReconstruction:
    """A backdated purchase is judged against the list this journal held
    then, and a list imported since cannot present itself as though it had
    been there."""

    def test_as_of_walks_the_day_it_was_imported(self, monkeypatch):
        j = {}
        monkeypatch.setattr(dated, "stamp", lambda: "2026-01-10T12:00:00+00:00")
        lists.record(j, "2026-01-05", ["ACME"])
        monkeypatch.setattr(dated, "stamp", lambda: "2026-08-06T12:00:00+00:00")
        lists.record(j, "2026-08-03", ["BRIA"])

        assert lists.current(j, as_of="2026-03-01")["pulled_on"] == "2026-01-05"
        assert lists.on_current(j, "BRIA", as_of="2026-03-01") is False
        assert lists.listed_on(j, "BRIA", as_of="2026-03-01") is None
        assert lists.current(j, as_of="2026-01-01") is None

    def test_a_day_between_the_pull_and_the_import_sees_the_older_list(
            self, monkeypatch):
        """The day the two dates part company, and the only day on which
        swapping them is visible.

        A list pulled on the 3rd and imported on the 6th was not on this
        journal's record on the 4th. A reconstruction cutting on `pulled_on`
        would hand it to a purchase dated then — a decision judged against a
        ranking nobody had yet seen — and every other as_of in this file gives
        the same answer either way, so nothing else here would notice.
        """
        j = {}
        monkeypatch.setattr(dated, "stamp", lambda: "2026-01-10T12:00:00+00:00")
        lists.record(j, "2026-01-05", ["ACME"])
        monkeypatch.setattr(dated, "stamp", lambda: "2026-08-06T12:00:00+00:00")
        lists.record(j, "2026-08-03", ["BRIA"])

        for day in ("2026-08-03", "2026-08-04", "2026-08-05"):
            assert lists.current(j, as_of=day)["pulled_on"] == "2026-01-05", day
            assert lists.on_current(j, "BRIA", as_of=day) is False, day
            assert lists.listed_on(j, "BRIA", as_of=day) is None, day
        # And on the day it was actually imported, it is in force.
        assert lists.current(j, as_of="2026-08-06")["pulled_on"] == "2026-08-03"

    def test_the_first_import_is_invisible_before_the_day_it_was_made(
            self, monkeypatch):
        j = {}
        monkeypatch.setattr(dated, "stamp", lambda: "2026-01-10T12:00:00+00:00")
        lists.record(j, "2025-11-01", ["ACME"])
        assert lists.current(j, as_of="2025-12-31") is None
        assert lists.on_current(j, "ACME", as_of="2025-12-31") is None
        assert lists.current(j, as_of="2026-01-10")["pulled_on"] == "2025-11-01"

    def test_a_list_pulled_before_it_was_imported_still_dates_from_the_pull(
            self, monkeypatch):
        """The two dates are kept apart on purpose: `recorded` answers what
        the journal knew, `pulled_on` answers how old the ranking is."""
        j = {}
        monkeypatch.setattr(dated, "stamp", lambda: "2026-08-20T12:00:00+00:00")
        lists.record(j, "2026-08-01", ["ACME"])
        assert lists.current(j)["pulled_on"] == "2026-08-01"
        assert dated.day_of(lists.current(j)) == "2026-08-20"


class TestWhatChangedBetweenLists:

    def test_the_first_list_brings_everything_and_nothing_falls_off(self):
        j = {}
        lists.record(j, "2025-08-04", ["ACME", "BRIA"])
        first = lists.changes(j)[-1]
        assert first["added"] == ["ACME", "BRIA"] and first["dropped"] == []

    def test_a_later_list_names_what_came_on_and_what_came_off(self):
        j = {}
        lists.record(j, "2025-08-04", ["ACME", "BRIA"])
        lists.record(j, "2026-08-03", ["ACME", "CWTH"])
        newest = lists.changes(j)[0]
        assert newest["added"] == ["CWTH"] and newest["dropped"] == ["BRIA"]


# -- a name you were told to buy and did not ---------------------------------

class TestPassingOverAName:

    def test_a_reason_is_required(self):
        for bad in (None, "", "   "):
            with pytest.raises(ValueError, match="Say why"):
                lists.pass_over({}, "2026-08-01", bad)

    def test_it_is_tied_to_the_list_that_offered_the_name(self):
        """A name that comes back on the next list is a fresh question, and
        an answer about last quarter's ranking is not an answer to it."""
        s = {}
        lists.pass_over(s, "2026-08-01", "Second glass company in two years.")
        assert lists.passed_over(s, "2026-08-01")["reason"].startswith("Second")
        assert lists.passed_over(s, "2027-02-01") is None

    def test_a_second_thought_is_a_second_entry_and_the_newer_one_stands(self):
        """Append-only, like every other decision the user writes down. The
        one in force is the newest, and the one it replaced is still there —
        which is what makes "when did I decide that" answerable."""
        s = {}
        lists.pass_over(s, "2026-08-01", "first thought")
        lists.pass_over(s, "2026-08-01", "still true a week later")
        assert len(s[lists.SKIP_KEY]) == 2
        assert lists.passed_over(s, "2026-08-01")["reason"] == \
            "still true a week later"
        assert s[lists.SKIP_KEY][0]["reason"] == "first thought"


# -- what the host serves out of it ------------------------------------------

@pytest.fixture
def magic():
    strategies, reports = strategy_loader.discover()
    record = strategies.get("magic-formula")
    assert record is not None, [r["errors"] for r in reports if not r["ok"]]
    return record


def journal_with(written_on, *imports, written=None):
    """A journal holding these imports, each written down on a stated day.

    The writing day has to be stated, and it is the whole reason this takes a
    fixture. Two dates describe an import and only one of them is a date a
    caller can supply: `pulled_on` is what the list says about itself, and
    `recorded` is when this journal learned of it, stamped by the host at the
    moment of writing because a record that could be backdated is not a
    record. `history` walks the second one — a reconstruction must not see a
    list imported after the day being rebuilt — so an import recorded at the
    moment a test runs is invisible to every `as_of` before today.

    That is not a subtlety these tests can leave implicit, because it does not
    fail when it is wrong. It waits. Every test below reads a fixed past day,
    so they all passed for as long as the fixed day was today and went red
    overnight — two of them loudly, and two of them by quietly asserting
    against a list nothing could see.

    So the default is the pull day, which is the ordinary case: you import a
    screen's output on the day you ran it. `written` states otherwise, for the
    one test whose entire point is that the two dates are different.
    """
    j = {"securities": []}
    for pulled, tickers in imports:
        with written_on(written or pulled):
            lists.record(j, pulled, tickers)
    return j


class TestTheFactsTheHostServes:

    def test_a_journal_with_no_list_says_so_rather_than_saying_no(self, magic):
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, record=magic, journal={})
        assert ctx["list"]["pulled"]["status"] == "absent"
        assert ctx["list"]["age_months"] is None
        assert ctx["security"]["on_list"]["status"] == "absent"
        assert ctx["security"]["listed_on"]["status"] == "absent"

    def test_membership_and_age_are_served_off_the_current_list(
            self, magic, written_on):
        j = journal_with(written_on, ("2026-06-01", ["ACME"]))
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        assert ctx["list"]["pulled"]["value"] == "2026-06-01"
        assert ctx["list"]["age_months"] == 2
        assert ctx["security"]["on_list"]["value"] is True
        assert ctx["security"]["listed_on"]["value"] == "2026-06-01"

    def test_every_list_fact_is_citable_and_resolves(self, magic,
                                                     written_on):
        j = journal_with(written_on, ("2026-06-01", ["ACME"]))
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        for fid in ("security.on_list", "security.listed_on", "list.pulled",
                    "list.age_months"):
            assert fid in contract.HOST_FACTS
            assert contract.test(ctx, {"fact": fid}) == contract.NOTED

    def test_the_age_a_rule_reads_is_measured_from_the_pull(self, magic,
                                                            written_on):
        # Pulled in February, typed in in August. The two readings are six
        # months apart on purpose — a helper that wrote every import on its
        # own pull day would collapse them and this would prove nothing.
        j = journal_with(written_on, ("2026-02-01", ["ACME"]),
                         written="2026-08-01")
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        # Six months since the screen was run, not twelve days since it was
        # typed in. A rule reading the wrong one is invisible and wrong.
        assert ctx["list"]["age_months"] == 6


class TestTheBlockedVerdictAndWhoGetsIt:

    def test_a_strategy_that_works_from_a_list_blocks_without_one(self, magic):
        """The strategy's own state, not a host gate. The host used to refuse
        to run at all, which also silenced the clock on positions already
        held — see the magic-formula suite."""
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, record=magic, journal={})
        result = contract.evaluate(magic, ctx)
        assert result["produced_by"] == "strategy"
        assert result["state"]["id"] == "waiting-on-a-list"
        assert result["render"] == "blocked"
        assert result["state"]["fix"] == "list"
        assert result["payload"]["needs"]

    def test_the_host_has_no_opinion_about_a_missing_list(self):
        """Deliberately not a host state. Whether a strategy can say anything
        without a list is the strategy's question — a lender-declining rule
        set can answer it before running, and this cannot."""
        assert not [s for s in contract.HOST_STATES if "list" in s]

    def test_the_way_out_is_a_destination_the_host_holds(self):
        assert "list" in contract.STATE_FIXES
        assert contract.STATE_FIXES["list"]["cites"] is None

    def test_a_strategy_that_screens_for_itself_is_never_blocked_on_one(self):
        """The facts are served to every context; the gate is not. A Graham
        journal has no list, is not asked for one, and never sees the tab."""
        strategies, _ = strategy_loader.discover()
        graham = strategies["graham"]
        assert not contract.declares_list(graham)
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(graham)["values"],
                                    {}, record=graham, journal={})
        assert "list" in ctx
        assert ctx["list"]["pulled"]["status"] == "absent"
        assert contract.evaluate(graham, ctx)["produced_by"] == "strategy"

    def test_the_gate_and_the_row_read_the_same_node(self, magic,
                                                     written_on):
        """A verdict blocked on a missing list beside evidence naming the
        list it is waiting for is the failure this pairing prevents."""
        j = journal_with(written_on, ("2026-06-01", ["ACME"]))
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        assert contract.test(ctx, {"fact": "list.pulled"}) == contract.NOTED
        assert contract.test(ctx, {"fact": "list.age_months"}) == contract.NOTED


class TestTheDeclaration:

    def test_a_list_block_must_be_complete(self):
        from test_contract import decl
        base = decl()
        for bad in ({"label": "x"},
                    {"label": "x", "explain": "y"},
                    {"label": "", "explain": "y",
                     "source": {"name": "n", "reasoning": False}},
                    "a list"):
            errors = contract.validate_declaration({**base, "list": bad})
            assert errors, bad

    def test_a_good_one_is_accepted_and_carried_onto_the_record(self, magic):
        from test_contract import decl
        good = {"label": "The list", "explain": "What it is and where from.",
                "source": {"name": "somewhere published", "reasoning": False}}
        assert contract.validate_declaration({**decl(), "list": good}) == []
        assert contract.declares_list(magic)
        assert magic["list"]["label"]

    def test_leaving_it_out_is_how_a_strategy_says_it_screens_itself(self):
        from test_contract import decl
        assert contract.validate_declaration(decl()) == []
        assert contract.declares_list({}) is False


# -- it travels ---------------------------------------------------------------

class TestItSurvivesAnExport:

    def test_a_bundle_carries_the_imports_whole(self, tmp_path):
        strategies, _ = strategy_loader.discover()
        record = strategies["magic-formula"]
        j = journals.create("Listed", record, bank.definitions(), inputs={})
        lists.record(j, "2026-08-01", ["ACME", "BRIA"], 1e9)
        journals.save(j)

        dest = tmp_path / "bundle.json"
        backup.export_bundle(dest)
        assert backup.inspect_bundle(dest)["lists"] == 1

        journals.delete(j["id"])
        backup.import_bundle(dest, keep_backup=False)
        back = journals.load(j["id"])
        assert lists.current(back)["tickers"] == ["ACME", "BRIA"]
        assert lists.current(back)["floor"] == 1e9

    def test_a_journal_that_never_had_one_loads_with_an_empty_record(self,
                                                                     tmp_path):
        strategies, _ = strategy_loader.discover()
        j = journals.create("Plain", strategies["graham"],
                            bank.definitions(), inputs={})
        assert journals.load(j["id"])[lists.KEY] == []


# -- the wiring that turns a paste into a record -----------------------------

class TestTheImportItself:
    """`Api.import_list` and `Api.pass_over`, driven the way the browser
    drives them. `lists.read` is well covered on its own; what is pinned here
    is the refusal — the commit's own claim that an unreadable line writes
    nothing — and the security a pass-over creates on its way past."""

    def open_journal(self):
        from app import Api
        api = Api()
        strategies, _ = strategy_loader.discover()
        journals.create("Listed", strategies["magic-formula"],
                        bank.definitions(), inputs={})
        return api

    def test_an_unreadable_line_refuses_and_writes_nothing(self):
        api = self.open_journal()
        r = api.import_list("2026-08-01", "ACME\nnot a row at all\nBRIA")
        assert r["ok"] is False
        assert "not a row at all" in r["error"]
        journal, *_ = api._open()
        assert journal[lists.KEY] == []

    def test_a_good_paste_is_recorded_whole(self):
        api = self.open_journal()
        r = api.import_list("2026-08-01",
                            "Acme Diagnostics\tACME\t1,204\n"
                            "Briar Foods\tBRIA\t880", 1e9)
        assert r["ok"] and r["n"] == 2 and r["pulled_on"] == "2026-08-01"
        journal, *_ = api._open()
        assert lists.current(journal)["tickers"] == ["ACME", "BRIA"]
        assert lists.current(journal)["floor"] == 1e9

    def test_a_bad_pull_date_refuses_and_writes_nothing(self):
        api = self.open_journal()
        for bad in ("2026-02-31", "2099-01-01", "not a day"):
            assert api.import_list(bad, "ACME")["ok"] is False, bad
        journal, *_ = api._open()
        assert journal[lists.KEY] == []

    def test_importing_creates_no_securities(self):
        """Fifty names is not fifty things to track, and each one created
        would carry its own fetch, queued behind the last."""
        api = self.open_journal()
        api.import_list("2026-08-01", "ACME\nBRIA\nCWTH")
        journal, *_ = api._open()
        assert journal["securities"] == []

    def test_passing_over_creates_the_security_and_records_the_reason(self):
        api = self.open_journal()
        api.import_list("2026-08-01", "ACME\nBRIA")
        r = api.pass_over("acme", "Second glass company in two years.")
        assert r["ok"] and r["ticker"] == "ACME" and r["list"] == "2026-08-01"
        journal, *_ = api._open()
        s = next(x for x in journal["securities"] if x["ticker"] == "ACME")
        assert lists.passed_over(s, "2026-08-01")["reason"].startswith("Second")
        assert s["lots"] == []

    def test_passing_over_needs_a_reason_and_a_name_on_the_list(self):
        api = self.open_journal()
        api.import_list("2026-08-01", "ACME")
        assert api.pass_over("ACME", "   ")["ok"] is False
        assert api.pass_over("ZZZZ", "not on it")["ok"] is False
        journal, *_ = api._open()
        assert journal["securities"] == []

    def test_it_does_not_change_the_verdict(self):
        """Principle 2. The strategy goes on saying what its rules say; the
        record says what was done about it."""
        api = self.open_journal()
        api.import_list("2026-08-01", "ACME")
        api.pass_over("ACME", "Do not like the look of it.")
        state = api.get_state()
        row = next(r for r in state["list"]["rows"] if r["ticker"] == "ACME")
        assert row["passed_over"]["reason"].startswith("Do not like")
        assert row["decision"]["state"]["id"] == "buy-it"

    def test_a_journal_that_screens_for_itself_refuses_both(self):
        from app import Api
        api = Api()
        strategies, _ = strategy_loader.discover()
        journals.create("Plain", strategies["graham"],
                        bank.definitions(), inputs={})
        assert api.import_list("2026-08-01", "ACME")["ok"] is False
        assert api.pass_over("ACME", "why not")["ok"] is False
        assert api.get_state()["list"] is None


class TestPassingOverIsScored:
    """The record was written, shown as prose, and never measured.

    Under a mechanical method the list IS the decision, so every pass-over is
    the user overriding the method — and it is the only one of the three
    documented ways to break the method that leaves no lot behind. Without
    scoring, the analytics can report the user's error rate and never the
    list's, which is precisely the guilt machine principle 10 forbids.
    """

    def _security(self, ticker="ACME", passes=(), lots_=()):
        from engine import portfolio
        s = portfolio.new_security(ticker, "Acme")
        for day, reason, stamp in passes:
            lists.pass_over(s, day, reason)
            s[lists.SKIP_KEY][-1]["recorded"] = stamp
        for day, price in lots_:
            s.setdefault("lots", []).append(
                {"id": f"l{day}", "seq": len(s.get("lots") or []) + 1,
                 "kind": "buy", "date": day, "recorded": day + "T12:00:00",
                 "shares": 1, "price": price})
        return s

    def _score(self, securities, now, then):
        from engine import portfolio
        return portfolio.pass_over_scorecard(
            securities, lambda s: now, lambda s, day: then)

    def test_a_name_that_fell_counts_as_avoided(self):
        """The inversion, and it is the whole point. A purchase works out when
        the price rises; a pass-over works out when it falls. Counting these
        as wins on the same footing would tell the reader they were right
        whenever a name they refused went up."""
        s = self._security(passes=[("2026-01-05", "Too much debt.",
                                    "2026-01-06T12:00:00-05:00")])
        out = self._score([s], {"value": 60.0}, {"value": 100.0})
        b = out["Too much debt."]
        assert (b["n"], b["n_scored"], b["avoided"]) == (1, 1, 1)
        assert b["avg"] == -40.0

    def test_a_name_that_rose_is_scored_and_not_avoided(self):
        s = self._security(passes=[("2026-01-05", "Too much debt.",
                                    "2026-01-06T12:00:00-05:00")])
        b = self._score([s], {"value": 150.0}, {"value": 100.0})["Too much debt."]
        assert (b["n_scored"], b["avoided"], b["avg"]) == (1, 0, 50.0)

    def test_grouped_by_the_reason_the_user_wrote(self):
        a = self._security("AAA", [("2026-01-05", "Too much debt.",
                                    "2026-01-06T12:00:00-05:00")])
        b = self._security("BBB", [("2026-01-05", "Too much debt.",
                                    "2026-01-06T12:00:00-05:00")])
        c = self._security("CCC", [("2026-01-05", "Do not understand it.",
                                    "2026-01-06T12:00:00-05:00")])
        out = self._score([a, b, c], {"value": 50.0}, {"value": 100.0})
        assert sorted(out) == ["Do not understand it.", "Too much debt."]
        assert out["Too much debt."]["n"] == 2

    def test_a_name_with_no_price_is_counted_and_says_why(self):
        """The common case, not the odd one: a passed-over name is usually one
        this journal has never fetched. An average over the priced few beside
        a count of all of them would let a data gap read as a settled result
        about somebody's judgement."""
        s = self._security(passes=[("2026-01-05", "Too much debt.",
                                    "2026-01-06T12:00:00-05:00")])
        b = self._score([s], {"value": 60.0},
                        {"value": None, "reason": "never fetched"})["Too much debt."]
        assert (b["n"], b["n_scored"], b["avg"]) == (1, 0, None)
        assert b["unscored"] == [{"reason": "never fetched", "n": 1}]

    def test_buying_it_after_all_ends_the_window_there(self):
        """The same rule a sale's aftermath follows. Once the shares are
        yours the price stops saying anything about having declined them."""
        s = self._security(
            passes=[("2026-01-05", "Too much debt.",
                     "2026-01-06T12:00:00-05:00")],
            lots_=[("2026-03-01", 120.0)])
        b = self._score([s], {"value": 500.0}, {"value": 100.0})["Too much debt."]
        assert b["bought_later"] == 1
        # 120 against 100, not 500 against 100
        assert b["avg"] == 20.0

    def test_every_pass_over_is_reachable_and_not_only_one_list(self):
        """`passed_over` answers about ONE list because that is what a screen
        asks. Scoring asks the opposite question and had no way to ask it."""
        s = self._security(passes=[
            ("2026-01-05", "Too much debt.", "2026-01-06T12:00:00-05:00"),
            ("2026-04-05", "Still too much.", "2026-04-06T12:00:00-05:00")])
        assert len(lists.pass_overs(s)) == 2
        out = self._score([s], {"value": 60.0}, {"value": 100.0})
        assert sorted(out) == ["Still too much.", "Too much debt."]

    def test_it_is_measured_from_the_day_the_user_declined(self):
        """Two dates are stored and they answer different questions. The pull
        date asks how the RANKING has done; the day they said no asks how the
        DECISION has done, and this record exists because a decision was
        made. Both travel on the answer so a reader can see the gap."""
        from engine import portfolio
        s = self._security(passes=[("2026-01-05", "Too much debt.",
                                    "2026-01-20T12:00:00-05:00")])
        got = portfolio.since_pass_over(s, lists.pass_overs(s)[0],
                                        {"value": 60.0}, {"value": 100.0})
        assert got["from"] == "2026-01-20"
        assert got["list"] == "2026-01-05"

    def test_nothing_is_invented_where_a_figure_is_missing(self):
        """Never a zero. This is the panel that judges the method, and a
        fabricated number is the last thing that may pass for a finding."""
        from engine import portfolio
        s = self._security(passes=[("2026-01-05", "Too much debt.",
                                    "2026-01-06T12:00:00-05:00")])
        for now, then in (({"value": None, "reason": "no close today"},
                           {"value": 100.0}),
                          ({"value": 60.0},
                           {"value": None, "reason": "never fetched"}),
                          ({"value": 0.0}, {"value": 100.0})):
            got = portfolio.since_pass_over(s, lists.pass_overs(s)[0], now,
                                            then)
            assert got["pct"] is None
            assert got["why_not"], got
