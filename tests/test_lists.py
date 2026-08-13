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

from engine import backup, contract, context, dated, journals, lists
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


def journal_with(*imports):
    j = {"securities": []}
    for pulled, tickers in imports:
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

    def test_membership_and_age_are_served_off_the_current_list(self, magic):
        j = journal_with(("2026-06-01", ["ACME"]))
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        assert ctx["list"]["pulled"]["value"] == "2026-06-01"
        assert ctx["list"]["age_months"] == 2
        assert ctx["security"]["on_list"]["value"] is True
        assert ctx["security"]["listed_on"]["value"] == "2026-06-01"

    def test_every_list_fact_is_citable_and_resolves(self, magic):
        j = journal_with(("2026-06-01", ["ACME"]))
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        for fid in ("security.on_list", "security.listed_on", "list.pulled",
                    "list.age_months"):
            assert fid in contract.HOST_FACTS
            assert contract.test(ctx, {"fact": fid}) == contract.NOTED

    def test_the_age_a_rule_reads_is_measured_from_the_pull(self, magic,
                                                            monkeypatch):
        monkeypatch.setattr(dated, "stamp", lambda: "2026-08-01T12:00:00+00:00")
        j = journal_with(("2026-02-01", ["ACME"]))
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        # Six months since the screen was run, not twelve days since it was
        # typed in. A rule reading the wrong one is invisible and wrong.
        assert ctx["list"]["age_months"] == 6


class TestTheBlockedVerdictAndWhoGetsIt:

    def test_a_strategy_that_works_from_a_list_is_blocked_without_one(self,
                                                                      magic):
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, record=magic, journal={})
        result = contract.evaluate(magic, ctx)
        assert result["state"]["id"] == "host:list-missing"
        assert result["render"] == "blocked"
        assert result["state"]["fix"] == "list"
        assert result["payload"]["needs"]

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
        assert contract.evaluate(graham, ctx)["state"]["id"] != \
            "host:list-missing"

    def test_the_gate_and_the_row_read_the_same_node(self, magic):
        """A verdict blocked on a missing list beside evidence naming the
        list it is waiting for is the failure this pairing prevents."""
        j = journal_with(("2026-06-01", ["ACME"]))
        ctx = context.build_context({"ticker": "ACME", "lots": []}, [],
                                    strategy_values.resolve(magic)["values"],
                                    {}, as_of="2026-08-13", record=magic,
                                    journal=j)
        assert contract._has_list(ctx) is True
        assert contract.test(ctx, {"fact": "list.pulled"}) == contract.NOTED
        assert contract._has_list({"list": {"pulled": {"status": "absent",
                                                        "reason": "x"}}}) \
            is False


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
        j = journals.create("Listed", record, inputs={})
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
        j = journals.create("Plain", strategies["graham"], inputs={})
        assert journals.load(j["id"])[lists.KEY] == []
