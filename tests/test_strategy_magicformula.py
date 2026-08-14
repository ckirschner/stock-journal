"""The Magic Formula bundle: the strategy that screens nothing.

Three of these pin things no other suite in this program has had to, because
this is the first strategy whose buy path tests no measure and whose only
exit is a clock:

- **That it really does gate on nothing.** "The two figures are shown and
  decide nothing" is a promise made in prose in four places. Here it is
  checked: no citation this bundle produces, on any path, names a measure and
  carries a comparator. A future author adding a threshold to one of them
  turns this red rather than quietly turning the method into a screen.
- **That the clock is the host's arithmetic and not a second copy.** Graham's
  suite pins the same thing for the same reason — a private date helper that
  disagreed by a day closed a position on a day its own evidence called
  early — and here the clock is the ENTIRE exit, so a drift of one day is the
  whole strategy being wrong once a year per position.
- **That a list restarting a year cannot make the year longer than it is.**
  The reset is the one design call in the bundle that Greenblatt does not
  make himself, and the failure it can have is silent: a name relisted
  eighteen months ago must be sold, not held, and both are a `hold` away from
  each other in the ladder.

Thresholds below are typed from their source rather than read out of the
bundle. A test that read the shipped value could not tell a deliberate retune
from an accident, which is the only thing it would be there to do.
"""

import importlib.util

import pytest
from conftest import industry_node

from engine import (bank, contract, context, journals, lists, portfolio,
                    strategy_floor, strategy_loader, strategy_values)

PASS, FAIL, UNKNOWN, NOTED = (contract.PASS, contract.FAIL, contract.UNKNOWN,
                              contract.NOTED)

# Every bank id this strategy reads. Both are shown and neither is tested;
# the pairing is asserted below rather than trusted.
MEASURES = ("earnings_yield", "return_on_capital")

TODAY = "2026-08-13"


@pytest.fixture
def magic():
    strategies, reports = strategy_loader.discover()
    record = strategies.get("magic-formula")
    assert record is not None, [r["errors"] for r in reports if not r["ok"]]
    return record


def values_for(record, **override):
    chain = strategy_values.resolve(
        record, [("journal override", override)] if override else [])
    assert chain["errors"] == [], chain["errors"]
    return chain["values"]


def known(value):
    return {"status": "known", "value": value, "source": "test",
            "cautions": [], "provenance": []}


def absent(reason="nothing is on record"):
    return {"status": "absent", "reason": reason}


def build(record, today=TODAY, on_list=True, listed_on="2026-08-01",
          pulled="2026-08-01", age=0, held=False, opened=None, occupied=0,
          holdings=(), have_list=True, figures=(11.5, 34.0), **override):
    """One context by hand, so a journal can be driven to a chosen shape.

    Driving the list, the portfolio and the clock through the real stores for
    every case would be a test of those stores. One case does go through the
    real builder — see the last class — so this shape cannot drift from the
    one a journal actually serves.
    """
    return {
        "contract": contract.CONTRACT_VERSION,
        "today": today,
        "security": {
            "ticker": "ACME", "name": "Acme Works", "cik": None,
            "sic": absent(), "industry": industry_node(None),
            "on_list": known(on_list) if have_list
                       else absent("this journal has no list on record"),
            "listed_on": known(listed_on) if listed_on
                         else absent("no list has carried ACME")},
        "measures": {mid: {"current": known(v),
                           "series": {"cadence": "quarterly", "points": [],
                                      "note": None, "truncated": False}}
                     for mid, v in zip(MEASURES, figures)},
        "price": {"latest": absent(), "closes": [], "events": [],
                  "age": absent()},
        "position": {
            "held": held, "shares": 100.0 if held else 0.0,
            "opened": opened, "last_purchase": opened,
            "months_held": (contract.months_between(opened, today)
                            if held and opened else None),
            "purchases": 1 if held else 0, "baselines": {}, "lots": [],
            "disposals": [], "market_value": absent(), "weight": absent()},
        "portfolio": {"cash": absent(), "account_value": absent(),
                      "slots": {"occupied": occupied},
                      "holdings": list(holdings)},
        "list": ({"pulled": known(pulled), "age_months": age} if have_list
                 else {"pulled": absent("this journal has no list on record"),
                       "age_months": None}),
        "values": values_for(record, **override),
        "inputs": {},
    }


def verdict(record, **kw):
    result = contract.evaluate(record, build(record, **kw))
    assert result["produced_by"] == "strategy", result["reason"]["summary"]
    return result


def opened_recently(n, day="2026-07-20"):
    return [{"ticker": f"T{i}", "name": f"T{i}", "shares": 1.0,
             "opened": day, "market_value": absent(), "weight": absent()}
            for i in range(n)]


def rows_of(result):
    return result["reason"]["evidence"]


def outcome_for(result, kind, ident):
    for row in rows_of(result):
        subject = row["subject"]
        if subject["kind"] == kind and subject.get("id") == ident:
            return row["outcome"]
    return None


# ---------------------------------------------------------------------------

class TestTheThresholdsAreTheirSources:
    """Every number here is Greenblatt's, and two of them are a point inside
    a band he gives rather than a figure he states. Typed out, so a retune is
    a failing test rather than a diff nobody reads."""

    GREENBLATT = {"holding-period-months": 12, "list-refresh-months": 12,
                  "names-per-tranche": 7}
    INSIDE_HIS_BAND = {"portfolio-slots": 25, "tranche-months": 2}

    @pytest.mark.parametrize("name", ["GREENBLATT", "INSIDE_HIS_BAND"])
    def test_the_shipped_defaults_are_what_the_source_says(self, magic, name):
        shipped = values_for(magic)
        for key, want in getattr(self, name).items():
            assert shipped[key] == want, key

    def test_every_declared_value_is_accounted_for_above(self, magic):
        assert {v["id"] for v in magic["values"]} == \
            set(self.GREENBLATT) | set(self.INSIDE_HIS_BAND)

    def test_there_are_no_thresholds_about_any_company(self, magic):
        """Five settings and not one of them is a level a business has to
        clear. That is the method rather than an omission, and a sixth that
        was would be a screen."""
        assert len(magic["values"]) == 5


class TestItScreensNothing:
    """The promise that the two ranked figures gate nothing, checked rather
    than asserted in prose."""

    CASES = [
        {}, {"on_list": False, "listed_on": None}, {"age": 14},
        {"occupied": 25}, {"occupied": 7, "holdings": opened_recently(7)},
        {"held": True, "opened": "2026-06-01", "listed_on": "2026-01-05",
         "on_list": False},
        {"held": True, "opened": "2025-02-01"},
        {"held": True, "opened": "2025-02-01", "listed_on": "2025-01-05",
         "on_list": False},
    ]

    def test_no_measure_is_ever_tested_on_any_path(self, magic):
        seen = 0
        for case in self.CASES:
            for row in rows_of(verdict(magic, **case)):
                if row["subject"]["kind"] != "measure":
                    continue
                seen += 1
                assert row["test"] is None, (case, row["subject"]["id"])
                assert row["outcome"] == NOTED
        assert seen, "no measure was cited anywhere, so nothing was checked"

    def test_both_ranked_figures_are_shown_on_every_verdict_about_a_name(
            self, magic):
        """Every verdict ABOUT THE SECURITY carries them. A blocked one does
        not, and should not: "your list is out of date" is a fact about the
        journal, and answering it with two figures about a company would be
        the screen this method does not run, offered at the one moment the
        reader has been told to go and do something else."""
        for case in self.CASES:
            result = verdict(magic, **case)
            if result["tier"] != "position":
                assert not [r for r in rows_of(result)
                            if r["subject"]["kind"] == "measure"], case
                continue
            cited = {r["subject"].get("id") for r in rows_of(result)}
            assert set(MEASURES) <= cited, case

    def test_they_are_gathered_under_a_heading_that_demands_nothing(self,
                                                                     magic):
        groups = {g["id"]: g for g in verdict(magic)["reason"]["groups"]}
        assert groups["why"]["requires"] == "noted"
        assert groups["why"]["outcome"] == NOTED

    def test_the_measures_it_names_are_in_the_bank(self, magic):
        """`contract.test` raises on a measure the bank does not hold, so a
        misspelling here would surface as a strategy error rather than as a
        missing figure. Checked directly so the message says which."""
        from engine import bank
        held = bank.meta()
        for mid in MEASURES:
            assert mid in held, mid
            assert held[mid]["unit"] == "percent"


class TestTheBuyPath:

    def test_on_the_list_with_room_is_a_buy(self, magic):
        result = verdict(magic)
        assert result["state"]["id"] == "buy-it"
        assert result["render"] == "commit"
        assert result["payload"]["condition"] is None

    def test_the_size_is_an_equal_share_of_the_names_it_runs(self, magic):
        assert verdict(magic)["payload"]["size"] == {"unit": "weight",
                                                     "value": 4.0}
        assert verdict(magic, **{"portfolio-slots": 20})["payload"]["size"] \
            == {"unit": "weight", "value": 5.0}

    def test_a_name_the_screen_did_not_return_is_not_a_buy(self, magic):
        result = verdict(magic, on_list=False, listed_on=None)
        assert result["state"]["id"] == "not-on-your-list"
        assert outcome_for(result, "fact", "security.on_list") == FAIL

    def test_a_full_portfolio_stops_it(self, magic):
        result = verdict(magic, occupied=25)
        assert result["state"]["id"] == "not-time-yet"
        assert result["reason"]["rule"] == "portfolio-already-full"

    def test_the_staging_rule_stops_it_and_says_which_rule(self, magic):
        result = verdict(magic, occupied=7, holdings=opened_recently(7))
        assert result["state"]["id"] == "not-time-yet"
        assert result["reason"]["rule"] == "enough-started-this-window"

    def test_one_short_of_the_tranche_still_buys(self, magic):
        assert verdict(magic, occupied=6, holdings=opened_recently(6)
                       )["state"]["id"] == "buy-it"

    def test_a_name_started_before_the_window_does_not_count_against_it(
            self, magic):
        """The limit counts names started recently, not days since the last
        purchase — which is what lets a position sold at its anniversary be
        replaced the same week instead of blocking the replacement."""
        old = opened_recently(7, day="2026-01-05")
        assert verdict(magic, occupied=7, holdings=old)["state"]["id"] \
            == "buy-it"

    def test_a_stale_list_blocks_the_whole_path(self, magic):
        result = verdict(magic, age=14)
        assert result["state"]["id"] == "waiting-on-a-list"
        assert result["render"] == "blocked"
        assert result["state"]["fix"] == "list"
        assert result["payload"]["needs"]

    def test_the_freshness_limit_is_a_setting(self, magic):
        assert verdict(magic, age=14, **{"list-refresh-months": 24}
                       )["state"]["id"] == "buy-it"

    def test_a_list_exactly_at_the_limit_has_expired(self, magic):
        """`below`, not `at_most` — the same convention the clock uses, so a
        list pulled a year ago today is out of date today."""
        assert verdict(magic, age=11)["state"]["id"] == "buy-it"
        assert verdict(magic, age=12)["state"]["id"] == "waiting-on-a-list"


class TestTheClock:
    """The only exit this strategy has."""

    def test_it_fires_on_the_anniversary_and_not_before(self, magic):
        assert verdict(magic, held=True, opened="2025-08-14",
                       listed_on=None, on_list=False)["state"]["id"] \
            == "still-running"
        result = verdict(magic, held=True, opened="2025-08-13",
                         listed_on=None, on_list=False)
        assert result["state"]["id"] == "time-is-up"
        assert result["payload"]["when"] == "2026-08-13"

    def test_the_due_date_is_the_scheduled_day_and_not_today(self, magic):
        result = verdict(magic, held=True, opened="2025-02-01",
                         listed_on="2025-01-05", on_list=False)
        assert result["payload"]["when"] == "2026-02-01"
        assert result["payload"]["when"] != TODAY

    def test_a_month_end_start_does_not_roll_forward(self, magic):
        result = verdict(magic, today="2025-03-01", held=True,
                         opened="2024-02-29", listed_on=None, on_list=False,
                         **{"holding-period-months": 12})
        assert result["payload"]["when"] == "2025-02-28"

    def test_the_figure_that_closes_a_position_never_reads_as_a_pass(self,
                                                                     magic):
        result = verdict(magic, held=True, opened="2025-02-01",
                         listed_on=None, on_list=False)
        assert outcome_for(result, "fact", "position.months_held") == FAIL

    def test_a_holding_inside_its_year_renders_as_a_pass(self, magic):
        """Cited in the direction the holding must keep. Written the other
        way round, an ordinary holding is a page of red beside a hold."""
        result = verdict(magic, held=True, opened="2026-06-01",
                         listed_on=None, on_list=False)
        assert outcome_for(result, "fact", "position.months_held") == PASS

    def test_the_holding_period_is_a_setting(self, magic):
        assert verdict(magic, held=True, opened="2025-11-01", listed_on=None,
                       on_list=False, **{"holding-period-months": 6}
                       )["state"]["id"] == "time-is-up"

    def test_no_figure_about_the_business_can_close_a_position(self, magic):
        """A dreadful company inside its year is held, and an excellent one
        past its year is sold. Nothing about the two figures moves either."""
        assert verdict(magic, held=True, opened="2026-06-01", listed_on=None,
                       on_list=False, figures=(0.1, 0.4))["state"]["id"] \
            == "still-running"
        assert verdict(magic, held=True, opened="2025-01-01", listed_on=None,
                       on_list=False, figures=(40.0, 90.0))["state"]["id"] \
            == "time-is-up"

    def test_it_uses_the_hosts_month_arithmetic_and_not_its_own(self):
        """Graham's suite pins the same thing, for the same reason: a second
        implementation of date arithmetic drifted from the host's and closed
        a position on a day its own evidence called early. Here the clock is
        the whole exit."""
        spec = importlib.util.spec_from_file_location(
            "_mf_probe", "strategies/magic-formula/strategy.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for private in ("_plus_months", "_months_elapsed", "_iso", "_today"):
            assert not hasattr(module, private), private
        assert "datetime" not in module.__dict__


class TestARelistedNameStartsItsYearAgain:

    def test_a_later_list_restarts_the_year_and_says_so(self, magic):
        result = verdict(magic, held=True, opened="2025-02-01",
                         listed_on="2026-08-01")
        assert result["state"]["id"] == "back-on-the-list"
        assert result["render"] == "hold"

    def test_the_restarted_year_runs_from_the_list_and_not_the_purchase(
            self, magic):
        result = verdict(magic, held=True, opened="2024-01-01",
                         listed_on="2026-08-01")
        assert result["state"]["id"] == "back-on-the-list"
        assert "2027-08-01" in result["reason"]["summary"]

    def test_a_restarted_year_can_itself_run_out(self, magic):
        """The silent failure this pins: a name relisted eighteen months ago
        must be sold, and holding it is one rung away in the ladder."""
        result = verdict(magic, held=True, opened="2024-01-01",
                         listed_on="2025-01-05", on_list=False)
        assert result["state"]["id"] == "time-is-up"
        assert result["payload"]["when"] == "2026-01-05"

    def test_a_list_older_than_the_purchase_does_not_restart_anything(self,
                                                                      magic):
        result = verdict(magic, held=True, opened="2026-06-01",
                         listed_on="2025-08-04", on_list=False)
        assert result["state"]["id"] == "still-running"
        assert outcome_for(result, "fact", "position.months_held") == PASS

    def test_a_holding_no_list_ever_carried_is_still_clocked(self, magic):
        """Bought against the signal, or added by hand. It is held, so it has
        a year, counted from the only date there is."""
        result = verdict(magic, held=True, opened="2026-06-01",
                         listed_on=None, on_list=False)
        assert result["state"]["id"] == "still-running"
        assert outcome_for(result, "fact", "security.listed_on") == NOTED

    def test_the_restarted_clock_is_stated_only_where_it_differs(self, magic):
        """Where nothing restarted it, the host's own months-held answers and
        nothing is restated. Where one did, months held is the wrong quantity
        and the strategy states the one it owns."""
        plain = verdict(magic, held=True, opened="2026-06-01", listed_on=None,
                        on_list=False)
        assert outcome_for(plain, "fact", "position.months_held") is not None
        reset = verdict(magic, held=True, opened="2025-02-01",
                        listed_on="2026-08-01")
        assert outcome_for(reset, "fact", "position.months_held") is None
        stated = [r for r in rows_of(reset) if r["subject"]["kind"] == "value"
                  or r["subject"].get("id") is None]
        assert any("Months since" in (r["subject"].get("label") or "")
                   for r in rows_of(reset)), stated


class TestTheContractIsNeverContradicted:

    CASES = [
        {},
        {"on_list": False, "listed_on": None},
        {"age": 14},
        {"occupied": 25},
        {"occupied": 7, "holdings": opened_recently(7)},
        {"held": True, "opened": "2026-06-01", "listed_on": None,
         "on_list": False},
        {"held": True, "opened": "2025-02-01", "listed_on": "2026-08-01"},
        {"held": True, "opened": "2025-02-01", "listed_on": None,
         "on_list": False},
        {"have_list": False, "on_list": False, "listed_on": None},
    ]

    def results(self, magic):
        return [contract.evaluate(magic, build(magic, **c))
                for c in self.CASES]

    def test_no_case_is_refused_by_the_host(self, magic):
        for case, result in zip(self.CASES, self.results(magic)):
            assert result["produced_by"] == "strategy", \
                f'{case}: {result["reason"]["summary"]}'

    def test_every_declared_state_is_reached(self, magic):
        assert strategy_floor.unmet(magic, self.results(magic)) == []

    def test_it_declares_no_verdict_it_cannot_reach_and_none_it_will_not_use(
            self, magic):
        """No `reduce`: this method never trims. No `unknown`: every input it
        reads is either a fact about the journal or a date, so there is no
        state of the data in which it cannot answer."""
        renders = {s["render"] for s in magic["states"]}
        assert "reduce" not in renders
        assert "unknown" not in renders
        assert renders == {"commit", "hold", "close", "blocked"}


class TestAJournalWithNoListStillClocksWhatItHolds:
    """The bug the host gate had. A journal that has never imported a list
    still holds positions — bought against the signal, or added by hand — and
    each of those has a year running that the clock needs no list to measure.
    The host used to refuse to run at all in that journal, so the one verdict
    that matters went quiet, while this strategy's own `waiting-on-a-list`
    description promised the opposite in as many words."""

    def test_an_overdue_holding_is_sold_and_not_blocked(self, magic):
        result = verdict(magic, have_list=False, on_list=False,
                         listed_on=None, held=True, opened="2025-02-01")
        assert result["state"]["id"] == "time-is-up"
        assert result["payload"]["when"] == "2026-02-01"

    def test_a_holding_inside_its_year_is_held_and_not_blocked(self, magic):
        result = verdict(magic, have_list=False, on_list=False,
                         listed_on=None, held=True, opened="2026-06-01")
        assert result["state"]["id"] == "still-running"

    def test_only_a_name_you_do_not_hold_waits_on_the_list(self, magic):
        result = verdict(magic, have_list=False, on_list=False,
                         listed_on=None)
        assert result["state"]["id"] == "waiting-on-a-list"
        assert result["reason"]["rule"] == "no-list-to-buy-from"
        assert "no list yet" in result["reason"]["summary"]

    def test_the_promise_in_the_state_description_is_the_behaviour(self,
                                                                    magic):
        """The description says positions you already hold are unaffected.
        Pinned against the words, so the two cannot part company again."""
        state = next(s for s in magic["states"]
                     if s["id"] == "waiting-on-a-list")
        assert "already hold are unaffected" in state["description"]


class TestAgainstAContextTheHostActuallyBuilds:
    """Without this the whole file can pass against a context shape that no
    longer exists. One journal, driven through the real stores."""

    def test_a_real_journal_with_a_real_list_reaches_a_real_verdict(
            self, magic, written_on):
        # Built on a stated day rather than on whatever day the suite runs.
        # A list is served to a reconstruction by the day it was WRITTEN, not
        # the day it was pulled, so a journal assembled at test time holds a
        # list that is invisible to every `as_of` before today — and TODAY
        # here is a fixed past date. That does not fail when it is wrong; it
        # waits until midnight and then fails for a reason that looks like a
        # defect in the strategy.
        with written_on("2026-08-01"):
            journal = journals.create("Live", magic, bank.definitions(),
                                      inputs={})
            lists.record(journal, "2026-08-01", ["ACME", "BRIA"])
        security = portfolio.new_security("ACME", "Acme Works")
        journal["securities"] = [security]
        journals.save(journal)

        ctx = context.build_context(security, journal["securities"],
                                    values_for(magic), {}, as_of=TODAY,
                                    record=magic, journal=journal)
        assert ctx["security"]["on_list"]["value"] is True
        assert ctx["list"]["pulled"]["value"] == "2026-08-01"
        for mid in MEASURES:
            assert mid in ctx["measures"]

        result = contract.evaluate(magic, ctx)
        assert result["produced_by"] == "strategy", \
            result["reason"]["summary"]
        assert result["state"]["id"] == "buy-it"

    def test_a_real_journal_with_no_list_blocks_with_a_way_out(self, magic):
        journal = journals.create("Empty", magic, bank.definitions(),
                                  inputs={})
        security = portfolio.new_security("ACME", "Acme Works")
        journal["securities"] = [security]
        journals.save(journal)
        ctx = context.build_context(security, journal["securities"],
                                    values_for(magic), {}, record=magic,
                                    journal=journal)
        result = contract.evaluate(magic, ctx)
        assert result["produced_by"] == "strategy"
        assert result["state"]["id"] == "waiting-on-a-list"
        assert result["state"]["fix"] == "list"
        assert result["reason"]["rule"] == "no-list-to-buy-from"


def test_no_rule_here_measures_back_to_a_purchase(magic):
    """So a redefined measure costs this strategy nothing, and the reason is
    structural rather than lucky: its only exit is a clock. It never asks how
    far anything has moved since you bought, so there is no frozen figure for
    a moved definition to make incomparable.

    Read off the running bundle rather than asserted as prose, because the
    day somebody adds a drift rule here is the day this stops being true and
    the cost has to be worked out again.
    """
    import ast
    import pathlib
    tree = ast.parse((pathlib.Path(magic["dir"]) / "strategy.py").read_text())
    cites_a_baseline = [
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.Dict)
        and "since" in [k.value for k in node.keys
                        if isinstance(k, ast.Constant)]]
    assert cites_a_baseline == [], cites_a_baseline
