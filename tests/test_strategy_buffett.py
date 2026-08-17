"""Buffett, the second real strategy written against the contract.

What is pinned here is what would fail *silently*, and three of those things
are new — Graham exercised none of them.

- **A question nobody answered is never a pass.** Most of what this strategy
  is comes from three assessments the reader writes themselves, and the whole
  arrangement is worthless if silence reads as agreement. An unanswered
  question has to block a purchase, and it must block it by returning a state
  that says so rather than by the host refusing a contradiction.
- **A blocked verdict is never a dead end.** A strategy's blocked state gets
  no button of its own from the host; the way in is the Judgements section on
  the same page, and that section is built from what the decision *cited*. So
  a block that fails to cite the questions it is waiting on is a trap, and
  the citation is the only thing standing between the two.
- **A fall of a third is not a fall of thirty-three points.** The exit on
  returns is proportional, and the same absolute decline has to end a
  position on a business that earned 15% and not on one that earned 45%.
- **Nothing about price can end a position, and neither can time.** Five
  exits and not one of them is a valuation measure; no holding period; and no
  state anywhere in the bundle that trims. Each of those is a promise made in
  prose everywhere else in the program, and prose decays.

The contexts below are built by hand rather than from filings, for the same
reason Graham's are: driving fifteen measures to chosen values through the
compute layer would test the compute layer. One class at the end goes the
whole way through `context.build_context` so the hand-built shape cannot
drift from the real one.
"""

import pytest

from conftest import entered, filer, filing, dur, balance_face, \
    redefined_since, \
    industry_node

from engine import context, contract, facts_store, judgements
from engine import strategy_floor, strategy_loader, strategy_values

QUALITATIVE = ("moat_durability", "management_integrity", "capital_allocation")

MEASURES = ("roic_median_5y", "total_debt_to_avg_fcf_5y",
            "owner_earnings_yield_on_ev",
            "incremental_roic_5y",
            "interest_coverage", "roe_minus_roic_gap_5y",
            "fcf_margin_median_5y", "cash_conversion_median_5y",
            "revenue_cagr_5y", "ni_minus_revenue_cagr_spread_5y",
            "gross_margin_range_relative_5y",
            "diluted_share_count_change_5y",
            "goodwill_impairment_to_equity_5y",
            "total_debt_to_ebitda", "effective_tax_rate_median_5y",
            "current_ratio", "payout_to_fcf_median_5y", "fcf_margin_ttm",
            "diluted_share_count_change_3y")

# Which group each entry measure is cited under, so a test can say "make this
# dimension fail" without restating the strategy's own arrangement. The point
# of the arrangement is that the dimensions are separable, and a test that
# hard-codes which measure sits where would not notice one moving.
DIMENSION_OF = {
    "incremental_roic_5y": "returns",
    "interest_coverage": "leverage", "roe_minus_roic_gap_5y": "leverage",
    "fcf_margin_median_5y": "cash", "cash_conversion_median_5y": "cash",
    "revenue_cagr_5y": "growth", "ni_minus_revenue_cagr_spread_5y": "growth",
    "gross_margin_range_relative_5y": "pricing",
    "diluted_share_count_change_5y": "allocation",
    "goodwill_impairment_to_equity_5y": "allocation",
}

# A business that clears every entry test. Invented, like everything else
# presented as an example here.
CLEARS_ENTRY = {
    "roic_median_5y": 18.9, "total_debt_to_avg_fcf_5y": 1.4,
    "owner_earnings_yield_on_ev": 6.2,
    "incremental_roic_5y": 24.0,
    "interest_coverage": 14.0, "roe_minus_roic_gap_5y": 3.1,
    "fcf_margin_median_5y": 17.0, "cash_conversion_median_5y": 1.05,
    "revenue_cagr_5y": 7.0, "ni_minus_revenue_cagr_spread_5y": 1.8,
    "gross_margin_range_relative_5y": 4.4,
    "diluted_share_count_change_5y": -6.0,
    "goodwill_impairment_to_equity_5y": 0.0,
    "total_debt_to_ebitda": 1.1,
    "effective_tax_rate_median_5y": 21.0, "current_ratio": 1.3,
    "payout_to_fcf_median_5y": 55.0,
}

# The same business once held: the five exit measures matter now, and two of
# them are measures the entry tests never looked at.
CLEARS_EXITS = {**CLEARS_ENTRY, "fcf_margin_ttm": 16.0,
                "diluted_share_count_change_3y": -4.0}

# All three questions answered yes.
SAID_YES = dict.fromkeys(QUALITATIVE, True)

QUARTERS = ("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
            "2026-03-31")


@pytest.fixture
def buffett():
    strategies, reports = strategy_loader.discover()
    record = strategies.get("buffett")
    assert record is not None, [r["errors"] for r in reports if not r["ok"]]
    return record


def values_for(record, **override):
    chain = strategy_values.resolve(
        record, [("journal override", override)] if override else [])
    assert chain["errors"] == [], chain["errors"]
    return chain["values"]


def _baseline(when, values):
    """One anchor purchase as engine/context serves it: the day, and the
    figures frozen onto that decision."""
    return {"status": "known", "date": when, "lot": "l1",
            "measures": {mid: {"status": "known", "value": v,
                               "source": "frozen", "cautions": [],
                               "provenance": []}
                         for mid, v in values.items()}}


def _one_out_for(mid, value, outs):
    """The dropped-year readings a measure's `current` carries.

    Supplied for every measure whose estimator asks for the check, because
    the computation supplies them for every such measure — a fixture that
    omitted them would test a hole in the fixture rather than the strategy,
    and it would do it by making every breach unconfirmable, which is the
    silent direction.

    The default is that the breach survives: dropping any single year leaves
    the reading where it was. That is what "nothing about one year in this
    fixture is special" means, and a test wanting the other case — one year
    carrying the whole breach — passes `outs` and says so.
    """
    if mid in (outs or {}):
        return [{"dropped": y, "value": v} for y, v in outs[mid]]
    est = contract.estimator_of(mid) or {}
    if est.get("robustness") != "always" or not isinstance(value,
                                                           (int, float)):
        return None
    return [{"dropped": f"20{19 + i}-12-31", "value": float(value)}
            for i in range(3)]


def build(record, known=None, series=None, judged=None, held=False,
          opened=None, weight=None, occupied=0, today="2026-08-09",
          bought=None, purchases=1, industry=None, outs=None, **override):
    """A context shaped exactly as engine/context builds one.

    `judged` is {bank id: True|False} for the three questions; anything left
    out is unanswered, which is the state a real journal starts in and the
    one most of this file is about.

    `bought` is what was on record at the anchor purchases. Left out on a
    holding, both anchors carry today's figures — nothing has moved since
    either purchase, so an unchanged business is the default and a fall in
    returns is something a test has to ask for.
    """
    known, series, judged = known or {}, series or {}, judged or {}
    measures = {}
    for mid in MEASURES:
        current = ({"status": "known", "value": known[mid],
                    "source": "manual", "cautions": [], "provenance": []}
                   if mid in known else
                   {"status": "absent", "reason": "nothing is on record"})
        if current["status"] == "known":
            one_out = _one_out_for(mid, known[mid], outs)
            if one_out:
                current["leave_one_out"] = one_out
        points = [{"period_end": pe, "filed": pe, "form": "10-Q",
                   "accession": pe, "value": value,
                   "reason": None if value is not None else "unreadable",
                   "cautions": [], "provenance": []}
                  for pe, value in series.get(mid, ())]
        measures[mid] = {"current": current,
                         "series": {"cadence": "quarterly", "points": points,
                                    "note": None, "truncated": False}}
    # A judgement carries no series at all, exactly as engine/context serves
    # one. Citing `at` on it is therefore always absent, which is why this
    # strategy never does.
    for mid in QUALITATIVE:
        current = ({"status": "known", "value": judged[mid],
                    "source": "judgement", "cautions": [],
                    "provenance": ["your assessment of 2026-01-01", "because"]}
                   if mid in judged else
                   {"status": "absent",
                    "reason": "assessed by you, not computed — nothing is "
                              "recorded in this journal yet"})
        measures[mid] = {"current": current,
                         "series": {"cadence": None, "points": [],
                                    "note": "assessed by you, not computed "
                                            "— no filing series exists",
                                    "truncated": False}}
    absent = {"status": "absent", "reason": "no free cash is recorded"}
    bought = bought or {}
    no_purchase = {"status": "absent",
                   "reason": "no position is held, so there is no purchase "
                             "to measure from"}
    baselines = {}
    for anchor, key in (("first-purchase", "first"),
                        ("last-purchase", "last")):
        baselines[anchor] = (_baseline(opened, bought.get(key, known))
                             if held else no_purchase)
    return {
        "contract": contract.CONTRACT_VERSION, "today": today,
        # An ordinary operating business unless a test asks otherwise.
        # This strategy declines three kinds, and the gate refuses them
        # before `decide` is called at all.
        "security": {"ticker": "WDGE", "name": "Wedgemoor Fasteners",
                     "cik": None,
                     "sic": {"status": "absent",
                             "reason": "a hand-built context"},
                     "industry": industry_node(industry)},
        "measures": measures,
        "price": {"latest": {"status": "absent", "reason": "no price"},
                  "closes": [], "events": []},
        "position": {
            "held": held, "shares": 100.0 if held else 0.0, "opened": opened,
            "months_held": (contract.months_between(opened, today)
                            if held and opened else None),
            "last_purchase": opened if held else None,
            "purchases": purchases if held else 0,
            "baselines": baselines,
            "lots": [], "disposals": [],
            "market_value": ({"status": "known", "value": 10_000.0,
                              "source": "computed", "cautions": [],
                              "provenance": []} if held else absent),
            "weight": ({"status": "known", "value": weight,
                        "source": "computed", "cautions": [],
                        "provenance": []} if weight is not None else absent)},
        "portfolio": {"cash": absent, "account_value": absent,
                      "slots": {"occupied": occupied}, "holdings": []},
        "values": values_for(record, **override), "inputs": {},
    }


def verdict(record, **kw):
    result = contract.evaluate(record, build(record, **kw))
    assert result["produced_by"] == "strategy", result["reason"]["summary"]
    return result


def key_of(item):
    """A citation's address, unambiguous across one decision.

    The group matters and so does the comparator: this strategy cites return
    on invested capital three times in one add — as a knockout, as an exit
    floor, and as a proportional fall — and two of those share a comparator.
    """
    s = item["subject"]
    key = f'{item.get("group") or "-"}/{s.get("id") or s["label"]}'
    if s.get("kind") == "change":
        key += "~since"
    if s.get("at"):
        key += f'@{s["at"]}'
    if (item.get("test") or {}).get("comparator"):
        key += f':{item["test"]["comparator"]}'
    return key


def outcomes(result):
    """{what was cited: how the host said the comparison came out}."""
    return {key_of(i): i["outcome"] for i in result["reason"]["evidence"]}


def rollup(result):
    """{group id: the rollup the HOST counted from the rows it resolved}."""
    return {g["id"]: g for g in result["reason"]["groups"]}


def cited_judgements(result):
    """The bank ids the host resolved as judgements — which is exactly the
    list app.py builds the answering surface from."""
    return [i["subject"]["id"] for i in result["reason"]["evidence"]
            if i["subject"].get("kind") == "judgement"]


# ---------------------------------------------------------------------------
# the numbers themselves
# ---------------------------------------------------------------------------

class TestTheThresholdsAreTheReports:
    """Every level, checked against the source as written rather than
    against whatever the bundle happens to ship. A quiet retune is what this
    project exists to catch, so the expected figures are typed out here."""

    REPORT = {
        "min-roic": 15, "min-owner-earnings-yield": 5,
        "min-interest-coverage": 8,
        "min-fcf-margin": 10, "min-cash-conversion": 0.90,
        "max-share-count-change": 0, "min-revenue-cagr": 4,
        "min-profit-growth-spread": -1,
        "max-debt-to-ebitda": 2.5,
        "min-current-ratio": 1.0, "max-payout-to-fcf": 80,
        "exit-roic-fall": -33, "exit-roic-level": 12,
        "exit-interest-coverage": 4,
        "exit-fcf-margin": 0, "exit-share-count-change": 10,
    }

    # The seven the second review overruled the report on. Typed out here for
    # the same reason the report's are: these are the levels somebody
    # deliberately moved, so a later quiet move back has to break something.
    REVIEW = {
        "max-debt-to-fcf": 3.0, "min-incremental-roic": 15,
        "max-roe-roic-gap": 10, "max-gross-margin-swing": 15,
        "max-goodwill-written-off": 5,
        "min-effective-tax-rate": 12, "max-effective-tax-rate": 28,
    }

    # Not either source's. Neither was asked how much to buy.
    PRACTICE = {"portfolio-slots": 10, "position-weight-cap": 40}

    # Nobody's but this file's, and the ones to argue with hardest.
    AUTHOR = {"cash-tests-required": 1, "growth-tests-required": 1,
              "exit-debt-to-fcf": 5.0, "minimum-add": 25}

    def test_every_level_is_what_the_source_says(self, buffett):
        shipped = values_for(buffett)
        assert {k: shipped[k] for k in self.REPORT} == self.REPORT

    def test_every_level_the_review_moved_is_where_it_put_it(self, buffett):
        shipped = values_for(buffett)
        assert {k: shipped[k] for k in self.REVIEW} == self.REVIEW

    def test_sizing_is_buffetts_practice_and_says_so(self, buffett):
        shipped = values_for(buffett)
        assert {k: shipped[k] for k in self.PRACTICE} == self.PRACTICE
        for v in buffett["values"]:
            if v["id"] in self.PRACTICE:
                assert "Buffett's own documented practice" in \
                    v["source"]["name"]
                assert "says nothing whatever about how much to buy" in \
                    v["source"]["name"]

    def test_what_has_no_source_says_it_has_no_source(self, buffett):
        """The three values with nothing behind them are the three most
        likely to be mistaken for someone's published figure, so each has to
        say plainly that it is not one."""
        shipped = values_for(buffett)
        assert {k: shipped[k] for k in self.AUTHOR} == self.AUTHOR
        for v in buffett["values"]:
            if v["id"] in self.AUTHOR:
                assert "this strategy's own author" in v["source"]["name"]
                assert "none is\nclaimed for it" in v["source"]["name"] \
                    or "none is claimed for it" in " ".join(
                        v["source"]["name"].split())

    def test_every_value_belongs_to_exactly_one_of_the_four_sources(
            self, buffett):
        """Four groups, and the four together are the whole list. A value
        added later without provenance cannot hide inside one of them, and a
        value that quietly changes source is a different claim about who
        stands behind the number."""
        buckets = {"report": self.REPORT, "review": self.REVIEW,
                   "practice": self.PRACTICE, "author": self.AUTHOR}

        def which(v):
            name = " ".join(v["source"]["name"].split())
            if name.startswith("Buffett's own"):
                return "practice"
            if name.startswith("this strategy's own author"):
                return "author"
            if name.startswith("the second expert review"):
                return "review"
            if name.startswith("the expert report"):
                return "report"
            raise AssertionError(f'{v["id"]} names an unknown source: {name}')

        found = {}
        for v in buffett["values"]:
            found.setdefault(which(v), []).append(v["id"])
        assert sorted(found) == sorted(buckets)
        for key, expected in buckets.items():
            assert sorted(found[key]) == sorted(expected), key

    def test_the_file_counts_its_own_thresholds_correctly(self, buffett):
        """The module docstring makes counting claims about provenance, and a
        claim made once at the top of a file is exactly the kind nobody
        rechecks when the twenty-ninth value is added.

        All four counts, not just the report's. The one that would have gone
        stale silently before is the review's — it is the newest, it is the
        one a later correction would grow, and it is the count a reader uses
        to judge how much of this file is still the document it names.
        """
        import re
        doc = open(buffett["dir"] + "/strategy.py",
                   encoding="utf-8").read().split('"""')[1]
        words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
                 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
                 11: "eleven", 12: "twelve", 13: "thirteen",
                 14: "fourteen", 15: "fifteen", 16: "sixteen",
                 17: "seventeen", 18: "eighteen", 19: "nineteen",
                 20: "twenty", 21: "twenty-one", 22: "twenty-two",
                 23: "twenty-three", 24: "twenty-four", 25: "twenty-five",
                 26: "twenty-six", 27: "twenty-seven", 28: "twenty-eight",
                 29: "twenty-nine", 30: "thirty", 31: "thirty-one",
                 32: "thirty-two", 33: "thirty-three"}

        claim = re.search(r"([\w-]+) of the ([\w-]+)\s+thresholds below", doc)
        assert claim, "the docstring no longer states a threshold count"
        total = len(buffett["values"])
        assert claim.group(2).lower() == words[total], \
            f"docstring says {claim.group(2)} values; there are {total}"
        assert claim.group(1).lower() == words[len(self.REPORT)], \
            (f"docstring credits {claim.group(1)} to the report; "
             f"{len(self.REPORT)} name it")

        for count, phrase in ((len(self.REVIEW), "are the second expert "
                                                 "review's"),
                              (len(self.PRACTICE), "come from Buffett's own"),
                              (len(self.AUTHOR), "are nobody's but this "
                                                 "file's author's")):
            wanted = f"{words[count].capitalize()} {phrase}"
            assert wanted in " ".join(doc.split()), \
                f"the docstring does not say: {wanted}"

    def test_every_declared_value_ships_a_default_and_is_explained(
            self, buffett):
        shipped = values_for(buffett)
        for v in buffett["values"]:
            assert v["id"] in shipped, v["id"]
            assert len(v["explain"]) > 120, v["id"]

    def test_the_fall_in_returns_keeps_the_reports_magnitude(self, buffett):
        """The one value written in a form the report does not use. Its size
        is the report's 33; the sign is what makes it a fall, and the value
        says so where a reader will look."""
        v = next(x for x in buffett["values"] if x["id"] == "exit-roic-fall")
        assert abs(values_for(buffett)["exit-roic-fall"]) == 33
        assert v["source"]["reasoning"] is False
        assert "states this level as 33" in v["explain"]


# ---------------------------------------------------------------------------
# what this strategy refuses to be able to do
# ---------------------------------------------------------------------------

class TestTheShapeOfTheBundleIsItselfAClaim:

    def test_nothing_here_can_trim_a_position(self, buffett):
        """Not "no trim fires in these fixtures" — no trim can be returned at
        all, because no state renders as one. It is the only way to say "this
        strategy will not sell a wonderful business for having got large"
        that a reader can check without running anything."""
        assert not [s for s in buffett["states"] if s["render"] == "reduce"]

    def test_there_is_no_holding_period(self, buffett):
        """Graham's clock is the thing that closes a position for having been
        owned too long. This has no such value, and a test is the only place
        that absence is checkable."""
        ids = {v["id"] for v in buffett["values"]}
        assert not [i for i in ids if "holding-period" in i]

    def test_it_declares_fewer_states_than_the_cap(self, buffett):
        assert len(buffett["states"]) == 12
        assert len(buffett["states"]) <= contract.MAX_STATES


def test_the_exits_are_all_about_the_business_never_the_price(buffett):
    """Read off the bundle itself rather than off a list retyped here: the
    five measures that can end a position, checked against the ones the metric
    bank calls valuation measures."""
    from engine import bank
    entries = {str(e.get("id")): e for e in bank.load_bank()["entries"]}
    exits = exit_measures(buffett)
    priced = {"pe_ttm", "pe_3y_avg_eps", "price_to_book",
              "price_to_net_tangible_assets", "graham_combined_multiple",
              "ev_to_ebit", "owner_earnings_yield", "fcf_yield_on_ev",
              "dividend_yield", "peg_trailing", "market_cap",
              "enterprise_value", "ncav_to_market_cap"}
    assert exits and not (exits & priced), exits & priced
    assert exits <= set(entries)


def exit_measures(record):
    """The measures this bundle's exits are built from, taken from the
    running strategy rather than from a list in this file."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "buffett_under_test", record["dir"] + "/strategy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {row[0] for row in mod.EXITS} | {mod.ROIC_DRIFT["measure"]}


# ---------------------------------------------------------------------------
# the three questions
# ---------------------------------------------------------------------------

class TestAQuestionNobodyAnsweredIsNeverAPass:

    def test_the_numbers_alone_do_not_buy_anything(self, buffett):
        """A business that clears all fifteen tests and has no assessment on
        record is blocked, not bought. This is the whole point of the
        strategy and the one thing that would be worth nothing if it broke
        quietly."""
        out = verdict(buffett, known=CLEARS_ENTRY)
        assert out["state"]["id"] == "judgement-owed"
        assert out["render"] == "blocked"
        assert rollup(out)["knockouts"]["outcome"] == "pass"
        assert all(rollup(out)[g]["outcome"] == "pass"
                   for g in set(DIMENSION_OF.values()))

    def test_the_unanswered_questions_resolve_as_unknown_never_pass(
            self, buffett):
        out = verdict(buffett, known=CLEARS_ENTRY)
        for mid in QUALITATIVE:
            assert outcomes(out)[f"quality/{mid}:equals"] == "unknown"
        assert rollup(out)["quality"]["outcome"] == "unknown"
        assert rollup(out)["quality"]["passed"] == 0

    def test_two_answered_and_one_missing_is_still_blocked(self, buffett):
        out = verdict(buffett, known=CLEARS_ENTRY,
                      judged={"moat_durability": True,
                              "management_integrity": True})
        assert out["state"]["id"] == "judgement-owed"
        assert rollup(out)["quality"]["passed"] == 2
        assert rollup(out)["quality"]["unknown"] == 1
        assert rollup(out)["quality"]["outcome"] == "unknown"

    def test_all_three_answered_yes_buys_it(self, buffett):
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES)
        assert out["state"]["id"] == "wonderful-and-priced"
        assert out["render"] == "commit"
        assert rollup(out)["quality"]["outcome"] == "pass"

    def test_one_answered_no_is_a_different_verdict_from_unanswered(
            self, buffett):
        """"You looked and said no" and "nobody has looked" are different
        facts about a company, and a tool that rendered them the same would
        be teaching that not deciding is a decision."""
        out = verdict(buffett, known=CLEARS_ENTRY,
                      judged={**SAID_YES, "moat_durability": False})
        assert out["state"]["id"] == "you-marked-it-down"
        assert out["render"] == "hold"
        assert outcomes(out)["quality/moat_durability:equals"] == "fail"

    def test_the_questions_are_not_asked_of_a_company_already_rejected(
            self, buffett):
        """Nobody should be assessing the durability of a business their own
        rules have already turned down. Because the answering surface is
        built from what the decision cited, not citing them is what keeps the
        question off the screen."""
        out = verdict(buffett, known={**CLEARS_ENTRY, "roic_median_5y": 6.0})
        assert out["state"]["id"] == "not-wonderful-enough"
        assert cited_judgements(out) == []

    def test_a_host_that_could_not_read_the_numbers_asks_nothing_either(
            self, buffett):
        out = verdict(buffett, known={k: v for k, v in CLEARS_ENTRY.items()
                                      if k != "roic_median_5y"})
        assert out["state"]["id"] == "cannot-screen"
        assert cited_judgements(out) == []


class TestABlockedVerdictIsNeverADeadEnd:
    """The host gives a strategy's blocked state no button of its own. The
    way in is the Judgements section on the same page, and app.py builds that
    from the ids the decision cited. So the citation is load-bearing: a block
    that named its questions only in prose would be a trap."""

    def test_the_block_cites_every_question_it_is_waiting_on(self, buffett):
        out = verdict(buffett, known=CLEARS_ENTRY)
        assert cited_judgements(out) == list(QUALITATIVE)

    def test_it_cites_the_ones_already_answered_too(self, buffett):
        """Not only the missing one. A reader looking at a block wants to see
        the two they have done as well as the one they have not, and the
        answering surface is where a change of mind starts."""
        out = verdict(buffett, known=CLEARS_ENTRY,
                      judged={"moat_durability": True})
        assert cited_judgements(out) == list(QUALITATIVE)

    def test_the_needs_carry_prose_and_never_the_question_names(self,
                                                                buffett):
        """The host used to prepend one "<label> — unanswered." line per
        outstanding question here so the verdict card could name them. The
        card points at the one surface that owns the questions now, so the
        payload carries the strategy's prose alone — and which questions
        are outstanding stays the host's fact, carried in the citations,
        which is where the answering surface reads it from."""
        from engine import bank
        out = verdict(buffett, known=CLEARS_ENTRY,
                      judged={"moat_durability": True,
                              "management_integrity": True})
        needs = out["payload"]["needs"]
        label = bank.meta()["capital_allocation"]["label"]
        assert not any(n.endswith("— unanswered.") for n in needs)
        assert not any(label in n for n in needs)
        assert not any("capital_allocation" in n for n in needs)
        assert any("not a fail" in n for n in needs)
        # the outstanding question is still discoverable, from the citation
        assert "capital_allocation" in cited_judgements(out)

    def test_the_names_are_not_written_in_this_strategy_at_all(self,
                                                               buffett):
        """The structural half. A paraphrase that merely happens to agree
        with the bank today is the arrangement this replaced."""
        import pathlib
        src = pathlib.Path(buffett["dir"], "strategy.py").read_text()
        assert "_ASKING" not in src

    def test_the_host_marks_them_as_judgements_and_not_measurements(
            self, buffett):
        """The kind comes from the bank and never from the strategy, so a
        strategy cannot present an assessment as something the tool worked
        out. Pinned here because this is the first bundle that depends on
        it."""
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES)
        rows = [i for i in out["reason"]["evidence"]
                if i["subject"].get("id") in QUALITATIVE]
        assert len(rows) == 3
        for row in rows:
            assert row["subject"]["kind"] == "judgement"
            assert row["subject"]["unit"] == "yes_no"
            # Both, and in this order. `explain` is the plain-language
            # definition on every kind of subject, and a judgement is not the
            # exception it was: it carried the question here, so the one row
            # where somebody is deciding whether a moat is durable answered
            # "what is this?" by asking them again, and the definition every
            # other row shows was a tab away. The question is what to answer;
            # the explanation is what the words mean.
            assert row["subject"]["explain"]
            assert "?" not in row["subject"]["explain"]
            assert row["subject"]["asks"]
            assert "?" in row["subject"]["asks"]

    def test_the_definition_a_judgement_row_shows_is_the_banks_own(
            self, buffett):
        """One copy. The row that has to teach a novice what a moat is must
        not be able to teach them something the Metrics tab contradicts."""
        from engine import bank
        idx = {e["id"]: e for e in bank.to_plain(bank.load_bank())["entries"]}
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES)
        rows = [i for i in out["reason"]["evidence"]
                if i["subject"].get("id") in QUALITATIVE]
        assert rows
        for row in rows:
            entry = idx[row["subject"]["id"]]
            assert row["subject"]["explain"] == \
                entry["explanation"]["plain"].strip()
            assert row["subject"]["asks"] == entry["question"].strip()


class TestABusinessThatStoppedBeingWonderful:
    """The case this strategy exists for, and the one no measure can see."""

    def test_marking_a_question_down_on_a_holding_closes_it(self, buffett):
        out = verdict(buffett, known=CLEARS_EXITS, judged={
            **SAID_YES, "capital_allocation": False},
            held=True, opened="2019-04-01", weight=14.0)
        assert out["state"]["id"] == "stopped-being-wonderful"
        assert out["render"] == "close"
        assert out["payload"]["when"] == "2026-08-09"

    def test_it_does_not_wait_for_a_second_filing(self, buffett):
        """Confirmation counts filings because a filing can be a one-off. An
        assessment is not a filing — it is a considered opinion with written
        reasoning behind it, and demanding it be made twice would be the tool
        arguing with its user."""
        out = verdict(buffett, known=CLEARS_EXITS,
                      judged={**SAID_YES, "moat_durability": False},
                      held=True, opened="2019-04-01", weight=14.0,
                      series={"roic_median_5y": [(q, 18.9) for q in QUARTERS]})
        assert out["state"]["id"] == "stopped-being-wonderful"

    def test_an_unanswered_question_never_closes_a_holding(self, buffett):
        """Silence closes nothing. It is the difference between the tool
        noticing something and the tool noticing nothing."""
        out = verdict(buffett, known=CLEARS_EXITS, held=True,
                      opened="2019-04-01", weight=14.0)
        assert out["state"]["id"] == "hold"

    def test_an_unanswered_question_does_stop_an_add(self, buffett):
        out = verdict(buffett, known=CLEARS_EXITS, held=True,
                      opened="2019-04-01", weight=14.0)
        assert out["reason"]["rule"] == "questions-unanswered"
        assert cited_judgements(out) == list(QUALITATIVE)

    def test_a_measured_exit_outranks_an_assessed_one(self, buffett):
        """Both close the position and the state says which. A confirmed
        breach across filings is evidence; a mark is an opinion, and the
        evidence is the one to lead with."""
        out = verdict(
            buffett,
            known={**CLEARS_EXITS, "total_debt_to_avg_fcf_5y": 6.4},
            judged={**SAID_YES, "moat_durability": False},
            held=True, opened="2019-04-01", weight=14.0,
            series={"total_debt_to_avg_fcf_5y": [(q, 6.4) for q in QUARTERS]})
        assert out["state"]["id"] == "business-broken"
        # And the mark is still on the screen, in a group demanding a pass.
        assert outcomes(out)["quality/moat_durability:equals"] == "fail"


# ---------------------------------------------------------------------------
# the exits
# ---------------------------------------------------------------------------

class TestNothingFiresOnOneReading:

    def test_one_bad_reading_is_a_breach_and_not_an_exit(self, buffett):
        out = verdict(buffett, known={**CLEARS_EXITS,
                                      "total_debt_to_avg_fcf_5y": 6.4},
                      judged=SAID_YES, held=True, opened="2019-04-01",
                      weight=14.0,
                      series={"total_debt_to_avg_fcf_5y":
                              [(q, 1.4) for q in QUARTERS[:-1]]
                              + [(QUARTERS[-1], 6.4)]})
        assert out["state"]["id"] == "one-reading-past"
        assert out["render"] == "hold"

    def test_two_bad_readings_end_it(self, buffett):
        out = verdict(buffett, known={**CLEARS_EXITS,
                                      "total_debt_to_avg_fcf_5y": 6.4},
                      judged=SAID_YES, held=True, opened="2019-04-01",
                      weight=14.0,
                      series={"total_debt_to_avg_fcf_5y":
                              [(q, 1.4) for q in QUARTERS[:-2]]
                              + [(q, 6.4) for q in QUARTERS[-2:]]})
        assert out["state"]["id"] == "business-broken"

    def test_free_cash_flow_takes_two_filings_and_not_four_quarters(
            self, buffett):
        """The report gives this exit a year and it now takes two filings.

        The departure is deliberate and it is in the changelog. The measure
        is already a trailing twelve months, so a single odd quarter is a
        quarter of it before anything waits; four consecutive readings of it
        span seven quarters of data to establish a claim about one year.
        What a trailing window can be asked to confirm is two filings."""
        def at(n):
            return verdict(
                buffett, known={**CLEARS_EXITS, "fcf_margin_ttm": -3.0},
                judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
                series={"fcf_margin_ttm":
                        [(q, 16.0) for q in QUARTERS[:len(QUARTERS) - n]]
                        + [(q, -3.0) for q in QUARTERS[len(QUARTERS) - n:]]})
        assert at(1)["state"]["id"] == "one-reading-past"
        assert at(2)["state"]["id"] == "business-broken"

    def test_a_five_year_median_does_not_wait_for_a_second_reading(
            self, buffett):
        """The exit this strategy is really about, and the one the change is
        for. Returns on capital are a five-year median: the next filing's
        reading shares four of the same five years, so waiting for it was
        waiting for the same data to be looked at again.

        Both halves of the compound have to fail, so the baseline is set
        high enough that the fall is past the tolerance as well."""
        out = verdict(
            buffett, known={**CLEARS_EXITS, "roic_median_5y": 8.0},
            judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
            bought={"first": {**CLEARS_EXITS, "roic_median_5y": 22.0},
                    "last": {**CLEARS_EXITS, "roic_median_5y": 22.0}},
            series={"roic_median_5y": [(q, 22.0) for q in QUARTERS[:-1]]
                    + [(QUARTERS[-1], 8.0)]})
        assert out["state"]["id"] == "business-broken"

    def test_the_share_count_takes_one_filing_and_not_two(self, buffett):
        """A change between two single years is not a long-window measure
        however many years it spans — it is two observations, and the newest
        of them is what the next filing replaces. One filing, never four."""
        def at(n):
            return verdict(
                buffett,
                known={**CLEARS_EXITS, "diluted_share_count_change_3y": 18.0},
                judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
                series={"diluted_share_count_change_3y":
                        [(q, 0.0) for q in QUARTERS[:len(QUARTERS) - n]]
                        + [(q, 18.0) for q in QUARTERS[len(QUARTERS) - n:]]})
        assert at(0)["state"]["id"] == "one-reading-past"
        assert at(1)["state"]["id"] == "business-broken"

    def test_the_verdict_names_what_actually_established_the_exit(
            self, buffett):
        """A verdict has to name the rule that produced it, and here that is
        different for different exits. The sentence used to say "more than
        one set of filings" whatever had happened — one rule speaking for
        five exits that are read three different ways.

        The debt exit names the dropped year rather than the filing count,
        and that is the correction: the measure is debt at one balance-sheet
        date over free cash flow averaged across five fiscal years, so the
        noisiest leg is the instant and the window underneath is still a
        window one year can carry. It was computing the one-out readings all
        along and nothing could ask for them.
        """
        debt = verdict(
            buffett, known={**CLEARS_EXITS, "total_debt_to_avg_fcf_5y": 6.4},
            judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
            series={"total_debt_to_avg_fcf_5y": [(q, 6.4) for q in QUARTERS]},
        )["reason"]["summary"]
        assert "survives dropping the year that most favours" in debt

    def test_a_debt_breach_one_year_is_carrying_is_not_established(
            self, buffett):
        """The other side of the same correction, and the reason it matters.
        Five years of free cash flow averaged: one very good year in the
        window can hold the ratio down, and one very bad one can push it up.
        A breach that clears when that year is dropped is one year, not a
        record, and this exit now waits instead of selling."""
        def at(one_out):
            return verdict(
                buffett,
                known={**CLEARS_EXITS, "total_debt_to_avg_fcf_5y": 6.4},
                judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
                series={"total_debt_to_avg_fcf_5y":
                        [(q, 6.4) for q in QUARTERS]},
                outs={"total_debt_to_avg_fcf_5y": one_out})["state"]["id"]

        # every year dropped leaves it breached — the record carries it
        assert at([("2021-12-31", 6.4), ("2022-12-31", 6.5)]) \
            == "business-broken"
        # drop 2021 and the requirement is met again — one year carried it
        assert at([("2021-12-31", 2.0), ("2022-12-31", 6.4)]) \
            == "one-reading-past"

        shares = verdict(
            buffett,
            known={**CLEARS_EXITS, "diluted_share_count_change_3y": 18.0},
            judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
            series={"diluted_share_count_change_3y":
                    [(QUARTERS[-1], 18.0)]})["reason"]["summary"]
        assert "on the newest filing" in shares
        assert "consecutive filings" not in shares

        median = verdict(
            buffett, known={**CLEARS_EXITS, "roic_median_5y": 8.0},
            judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
            bought={"first": {**CLEARS_EXITS, "roic_median_5y": 22.0},
                    "last": {**CLEARS_EXITS, "roic_median_5y": 22.0}},
        )["reason"]["summary"]
        assert "nothing to wait for" in median
        assert "consecutive filings" not in median

    def test_a_gap_neither_confirms_a_breach_nor_forgives_one(self, buffett):
        """A filing whose reading could not be worked out must not confirm
        something nobody observed, and must not grant an indefinite reprieve
        either."""
        out = verdict(buffett, known={**CLEARS_EXITS,
                                      "total_debt_to_avg_fcf_5y": 6.4},
                      judged=SAID_YES, held=True, opened="2019-04-01",
                      weight=14.0,
                      series={"total_debt_to_avg_fcf_5y":
                              [(QUARTERS[0], 1.4), (QUARTERS[1], 6.4),
                               (QUARTERS[2], None), (QUARTERS[3], 6.4),
                               (QUARTERS[4], 6.4)]})
        assert out["state"]["id"] == "business-broken"

    def test_absence_never_fires_an_exit(self, buffett):
        """A missing reading is not evidence a company is in trouble, and
        this program does not sell on silence."""
        out = verdict(buffett, known={k: v for k, v in CLEARS_EXITS.items()
                                      if k != "total_debt_to_avg_fcf_5y"},
                      judged=SAID_YES, held=True, opened="2019-04-01",
                      weight=14.0)
        assert out["state"]["id"] != "business-broken"
        assert outcomes(out)["decay/total_debt_to_avg_fcf_5y:at_most"] == "unknown"

    def test_no_exit_readable_at_all_says_so(self, buffett):
        out = verdict(buffett, known={}, judged=SAID_YES, held=True,
                      opened="2019-04-01", weight=14.0)
        assert out["state"]["id"] == "cannot-watch"
        assert out["render"] == "unknown"


class TestTheFallInReturnsIsProportional:
    """The one thing this strategy needed that contract v5 could not say.

    A fall of a third is not a fall of thirty-three points, and one tolerance
    in points cannot mean the same thing to a business earning 45% and one
    earning 15%. Both halves of the compound also have to fail before
    anything happens.
    """

    def held(self, buffett, then, now, **kw):
        return verdict(
            buffett, known={**CLEARS_EXITS, "roic_median_5y": now},
            judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
            bought={"first": {**CLEARS_EXITS, "roic_median_5y": then},
                    "last": {**CLEARS_EXITS, "roic_median_5y": then}},
            series={"roic_median_5y": [(q, now) for q in QUARTERS]}, **kw)

    def test_a_third_off_a_low_return_business_ends_it(self, buffett):
        """16% to 10% is six points, and it is 37.5% of what it was — past
        the tolerance, and under the floor."""
        out = self.held(buffett, 16.0, 10.0)
        assert out["state"]["id"] == "business-broken"
        row = next(i for i in out["reason"]["evidence"]
                   if i["subject"].get("kind") == "change")
        assert round(row["observed"]["value"], 1) == -37.5
        assert row["subject"]["unit"] == "percent"
        assert row["outcome"] == "fail"

    def test_the_same_six_points_off_a_high_return_business_does_not(
            self, buffett):
        """45% to 39% is the same six points and only 13% of what it was.
        The business still earns nearly three times its cost of capital, and
        a tolerance in points would have sold it."""
        out = self.held(buffett, 45.0, 39.0)
        assert out["state"]["id"] != "business-broken"
        row = next(i for i in out["reason"]["evidence"]
                   if i["subject"].get("kind") == "change")
        assert round(row["observed"]["value"], 1) == -13.3
        assert row["outcome"] == "pass"

    def test_a_big_fall_that_is_still_a_good_business_does_not_end_it(
            self, buffett):
        """40% to 25% has lost more than a third and is still well above the
        floor. Both halves have to fail, and this is why."""
        out = self.held(buffett, 40.0, 25.0)
        assert out["state"]["id"] != "business-broken"
        assert outcomes(out)["decay/roic_median_5y~since:above"] == "fail"
        assert outcomes(out)["decay/roic_median_5y:at_least"] == "pass"

    def test_a_business_that_was_always_mediocre_is_not_sold_for_it(
            self, buffett):
        """13% to 11.5% is under the floor and has no third to lose. Selling
        it for being what it always was is the failure the compound
        prevents."""
        out = self.held(buffett, 13.0, 11.5)
        assert out["state"]["id"] != "business-broken"
        assert outcomes(out)["decay/roic_median_5y:at_least"] == "fail"
        assert outcomes(out)["decay/roic_median_5y~since:above"] == "pass"

    def test_a_fall_of_exactly_a_third_fires_it(self, buffett):
        """The boundary, and the one place in this bundle where the source
        states a level as a magnitude with the direction in the prose around
        it. "Falls by at least 33%" fires AT a third, so what the holding
        must keep is a change strictly above -33 — `at_least` would let the
        exact case through, and a boundary that goes the wrong way goes wrong
        silently."""
        # 25.0 -> 16.75 is a fall of exactly a third, and lands on -33.0
        # rather than near it, so this pins the comparator and not the
        # floating-point weather around the boundary.
        exact = self.held(buffett, 25.0, 16.75)
        assert outcomes(exact)["decay/roic_median_5y~since:above"] == "fail"
        # A hair short of a third does not.
        assert outcomes(self.held(buffett, 25.0, 16.80))[
            "decay/roic_median_5y~since:above"] == "pass"
        # And where the floor has gone too, the exact case ends the position
        # rather than surviving it by one tick.
        assert self.held(buffett, 11.0, 7.37)["state"]["id"] == \
            "business-broken"

    def test_every_exit_lands_the_right_way_round_at_its_own_boundary(
            self, buffett):
        """Each exit's comparator against the level the source states, at the
        exact level. A comparator one tick out never shows up on ordinary
        data and decides the case the rule was written for."""
        def at(**over):
            return verdict(buffett, known={**CLEARS_EXITS, **over},
                           judged=SAID_YES, held=True, opened="2019-04-01",
                           weight=14.0,
                           series={k: [(q, v) for q in QUARTERS]
                                   for k, v in over.items()})
        # "less_than 12" — 12 exactly does not fire.
        assert outcomes(at(roic_median_5y=12.0))[
            "decay/roic_median_5y:at_least"] == "pass"
        assert outcomes(at(roic_median_5y=11.99))[
            "decay/roic_median_5y:at_least"] == "fail"
        # "greater_than 5.0" — 5.0 exactly does not fire.
        assert outcomes(at(total_debt_to_avg_fcf_5y=5.0))[
            "decay/total_debt_to_avg_fcf_5y:at_most"] == "pass"
        assert outcomes(at(total_debt_to_avg_fcf_5y=5.01))[
            "decay/total_debt_to_avg_fcf_5y:at_most"] == "fail"
        # "less_than 4" — 4 exactly does not fire.
        assert outcomes(at(interest_coverage=4.0))[
            "decay/interest_coverage:at_least"] == "pass"
        # "less_than 0" — nought exactly does not fire.
        assert outcomes(at(fcf_margin_ttm=0.0))[
            "decay/fcf_margin_ttm:at_least"] == "pass"
        # "greater_than 10" — 10 exactly does not fire.
        assert outcomes(at(diluted_share_count_change_3y=10.0))[
            "decay/diluted_share_count_change_3y:at_most"] == "pass"

    def test_a_baseline_nobody_could_read_leaves_it_unreadable(self, buffett):
        """Not clear. A comparison nobody could make has not shown that
        nothing happened, and an exit half that cannot be worked out must not
        let the other half through on its own."""
        out = verdict(
            buffett, known={**CLEARS_EXITS, "roic_median_5y": 9.0},
            judged=SAID_YES, held=True, opened="2019-04-01", weight=14.0,
            bought={"first": {k: v for k, v in CLEARS_EXITS.items()
                              if k != "roic_median_5y"},
                    "last": CLEARS_EXITS},
            series={"roic_median_5y": [(q, 9.0) for q in QUARTERS]})
        assert out["state"]["id"] != "business-broken"
        assert outcomes(out)["decay/roic_median_5y~since:above"] == "unknown"

    def test_the_fall_is_cited_even_when_nothing_is_wrong(self, buffett):
        """Half a rule shown is a rule nobody can check. The two halves are
        one test and both are on the screen whatever the answer."""
        out = self.held(buffett, 18.9, 18.9)
        assert out["state"]["id"] == "room-for-more"
        assert outcomes(out)["decay/roic_median_5y~since:above"] == "pass"

    def test_a_half_failed_compound_is_accounted_for_in_the_summary(
            self, buffett):
        """The only place in this bundle where a red row sits beside a
        sentence saying everything came back clear, and both are true: the
        exit needs both halves and only one failed. A reader cannot be
        expected to work that out from a red row and a summary that does not
        mention it — "clear" is the claim they will believe."""
        # Fallen more than a third, still well above the floor.
        drifted = self.held(buffett, 40.0, 25.0)
        assert drifted["state"]["id"] == "room-for-more"
        assert outcomes(drifted)["decay/roic_median_5y~since:above"] == "fail"
        assert "requires both" in drifted["reason"]["summary"]
        assert "One red row below, and no exit" in drifted["reason"]["summary"]

        # And the other way round: under the floor, with no third to lose.
        floored = self.held(buffett, 13.0, 11.5)
        assert outcomes(floored)["decay/roic_median_5y:at_least"] == "fail"
        assert "requires both" in floored["reason"]["summary"]

    def test_a_clean_holding_says_nothing_about_halves(self, buffett):
        """The sentence is owed only where a row would otherwise contradict
        the summary. A holding with nothing wrong must not carry it."""
        assert "requires both" not in \
            self.held(buffett, 18.9, 18.9)["reason"]["summary"]

    def test_the_row_says_it_is_a_share_and_not_a_number_of_points(
            self, buffett):
        out = self.held(buffett, 16.0, 10.0)
        row = next(i for i in out["reason"]["evidence"]
                   if i["subject"].get("kind") == "change")
        assert "as a share of what it was then" in row["subject"]["label"]
        assert "since you first bought" in row["subject"]["label"]
        # And it explains itself in place, for someone who has never done it:
        # which purchase it measures from, how the move is counted, and what
        # the thing moving actually is.
        explain = row["subject"]["explain"]
        assert "the day this holding began" in explain
        assert "as a percentage of what it was at that purchase" in explain
        assert "cents of profit" in explain


# ---------------------------------------------------------------------------
# sizing, and the thing this strategy will not do
# ---------------------------------------------------------------------------

class TestHowMuchAndHowMany:

    def test_a_first_purchase_takes_an_equal_share(self, buffett):
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES)
        assert out["payload"]["size"] == {"unit": "weight", "value": 10.0}

    def test_a_full_list_has_no_room_for_an_eleventh(self, buffett):
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES,
                      occupied=10)
        assert out["state"]["id"] == "no-room"
        assert out["render"] == "hold"

    def test_an_add_goes_toward_the_cap_and_not_the_equal_share(self, buffett):
        """The concentration rule, and the sharpest difference from Graham. A
        holding already at 14% — above the 10% a first purchase takes — still
        has room, because money goes to what keeps proving itself."""
        out = verdict(buffett, known=CLEARS_EXITS, judged=SAID_YES, held=True,
                      opened="2019-04-01", weight=14.0)
        assert out["state"]["id"] == "room-for-more"
        assert out["payload"]["size"] == {"unit": "weight", "value": 26.0}

    def test_a_position_past_the_cap_is_held_and_never_trimmed(self, buffett):
        """The promise the missing `reduce` state makes, kept. A holding at
        52% of the account is left entirely alone."""
        out = verdict(buffett, known=CLEARS_EXITS, judged=SAID_YES, held=True,
                      opened="2019-04-01", weight=52.0)
        assert out["state"]["id"] == "hold"
        assert out["render"] == "hold"
        assert out["reason"]["rule"] == "no-room-to-add"
        assert "no trim" in out["reason"]["summary"]

    def test_a_weight_nobody_could_work_out_stops_the_add(self, buffett):
        out = verdict(buffett, known=CLEARS_EXITS, judged=SAID_YES, held=True,
                      opened="2019-04-01")
        assert out["state"]["id"] == "hold"
        assert out["reason"]["rule"] == "size-unreadable"

    def test_an_add_is_the_entry_tests_again_at_the_same_bar(self, buffett):
        """Not a softer set because you already own it and not a harder one
        because you are averaging in."""
        out = verdict(buffett,
                      known={**CLEARS_EXITS, "owner_earnings_yield_on_ev": 3.1},
                      judged=SAID_YES, held=True, opened="2019-04-01",
                      weight=14.0)
        assert out["state"]["id"] == "hold"
        assert out["reason"]["rule"] == "would-not-buy-it-today"
        assert outcomes(out)[
            "knockouts/owner_earnings_yield_on_ev:at_least"] == "fail"

    def test_a_screen_that_did_not_finish_is_not_a_passing_one(self, buffett):
        """A knockout nobody could read. Note it has to be a knockout, or
        one of the rows a question depends on alone: an unreadable row beside
        a passing one in the same near-duplicate pair still answers that
        question, and a screen that answered all six has finished."""
        out = verdict(buffett,
                      known={k: v for k, v in CLEARS_EXITS.items()
                             if k != "owner_earnings_yield_on_ev"},
                      judged=SAID_YES, held=True, opened="2019-04-01",
                      weight=14.0)
        assert out["state"]["id"] == "hold"
        assert out["reason"]["rule"] == "screen-unreadable"

    def test_one_unreadable_core_test_does_not_stop_an_add(self, buffett):
        """The other side of the same rule, and the reason the one above
        names a knockout. One row of a near-duplicate pair is unreadable and
        the other passes, so its question is still answered."""
        out = verdict(buffett,
                      known={k: v for k, v in CLEARS_EXITS.items()
                             if k != "cash_conversion_median_5y"},
                      judged=SAID_YES, held=True, opened="2019-04-01",
                      weight=14.0)
        assert out["state"]["id"] == "room-for-more"

    def test_time_held_is_reported_so_a_permanent_hold_still_moves(
            self, buffett):
        """The commonest verdict here is the same word for years. The one
        figure that visibly changes underneath it is how long you have owned
        the thing, so it is always cited."""
        out = verdict(buffett, known=CLEARS_EXITS, judged=SAID_YES, held=True,
                      opened="2019-04-01", weight=52.0)
        row = next(i for i in out["reason"]["evidence"]
                   if i["subject"].get("id") == "position.months_held")
        assert row["observed"]["value"] == 88
        assert row["outcome"] == "noted"
        assert "88 months" in out["reason"]["summary"]


# ---------------------------------------------------------------------------
# absence, and the rollup
# ---------------------------------------------------------------------------

class TestAbsenceIsNeverSuccessAndNeverFailure:

    def test_a_missing_knockout_cannot_be_bought_through(self, buffett):
        out = verdict(buffett,
                      known={k: v for k, v in CLEARS_ENTRY.items()
                             if k != "total_debt_to_avg_fcf_5y"},
                      judged=SAID_YES)
        assert out["state"]["id"] == "cannot-screen"
        assert rollup(out)["knockouts"]["outcome"] == "unknown"

    def test_a_dimension_that_cannot_be_answered_is_settled(self, buffett):
        """A question about the business with no passing row under it is a
        no, whatever else passed. Both rows about what the company owes fail
        here, and nothing anywhere else can make up for it."""
        out = verdict(buffett, known={**CLEARS_ENTRY,
                                      "interest_coverage": 2.0,
                                      "roe_minus_roic_gap_5y": 31.0},
                      judged=SAID_YES)
        assert out["state"]["id"] == "not-wonderful-enough"
        assert out["reason"]["rule"] == "dimension-short"
        assert rollup(out)["leverage"]["outcome"] == "fail"

    def test_one_of_a_near_duplicate_pair_may_fail(self, buffett):
        """The two cash tests are two readings of the same cash, so one of
        them is the coverage statement. The verdict has to survive its own
        failed row without the host refusing it as a contradiction."""
        out = verdict(buffett,
                      known={**CLEARS_ENTRY, "cash_conversion_median_5y": 0.4},
                      judged=SAID_YES)
        assert out["state"]["id"] == "wonderful-and-priced"
        assert rollup(out)["cash"]["passed"] == 1
        assert rollup(out)["cash"]["outcome"] == "pass"


class TestCoverageIsNotACount:
    """The correction this version exists for, and the one thing here that
    would go wrong silently if it regressed: a company must be strong across
    dimensions, not strong in one dimension measured several ways.

    The old arrangement was seven of nine. Under it, a company weak on what
    it owes and on what it hands to employees could still buy, because four
    passes from cash and growth and returns paid for them. That is the case
    driven below, and it must now refuse.
    """

    def test_excellent_at_one_thing_no_longer_pays_for_the_rest(
            self, buffett):
        """Nine of the ten rows are exceptional and both rows under one
        question fail. Under a seven-of-nine quota this bought. It must not
        now, and the reason has to name the question rather than a count."""
        out = verdict(buffett, known={**CLEARS_ENTRY,
                                      "diluted_share_count_change_5y": 9.0,
                                      "goodwill_impairment_to_equity_5y": 24.0},
                      judged=SAID_YES)
        assert out["state"]["id"] == "not-wonderful-enough"
        assert "what management does with the money" in \
            out["reason"]["summary"]
        # And the count it would have cleared is stated, so nobody reads the
        # refusal as the tests having gone badly across the board.
        assert "8 of the 10 tests behind them passed" in \
            out["reason"]["summary"]

    def test_every_dimension_is_its_own_group_and_all_are_demanded(
            self, buffett):
        """Six questions, each declared to the host with its own requirement,
        and not one of them `noted`. A dimension that demanded nothing would
        be the quota back by another door — and the host would let a commit
        stand beside its failures."""
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES)
        groups = rollup(out)
        wanted = {"returns", "leverage", "cash", "growth", "pricing",
                  "allocation"}
        assert wanted <= set(groups)
        for gid in wanted:
            assert groups[gid]["requires"] in ("all", "at_least"), gid
            assert groups[gid]["outcome"] == "pass", gid

    def test_each_group_fails_on_its_own_and_takes_the_verdict_with_it(
            self, buffett):
        """Every dimension, driven short one at a time. Any of them alone has
        to stop the purchase — which is the whole claim, and the claim would
        be worth nothing if it held for five of the six."""
        breaks = {
            "returns": {"incremental_roic_5y": 2.0},
            "leverage": {"interest_coverage": 2.0,
                         "roe_minus_roic_gap_5y": 31.0},
            "cash": {"fcf_margin_median_5y": 1.0,
                     "cash_conversion_median_5y": 0.3},
            "growth": {"revenue_cagr_5y": 0.5,
                       "ni_minus_revenue_cagr_spread_5y": -9.0},
            "pricing": {"gross_margin_range_relative_5y": 61.0},
            "allocation": {"diluted_share_count_change_5y": 9.0},
        }
        assert set(breaks) == set(DIMENSION_OF.values())
        for gid, over in breaks.items():
            out = verdict(buffett, known={**CLEARS_ENTRY, **over},
                          judged=SAID_YES)
            assert out["state"]["id"] == "not-wonderful-enough", gid
            assert rollup(out)[gid]["outcome"] == "fail", gid

    def test_an_unreadable_dimension_is_undecided_and_not_refused(
            self, buffett):
        """Absence is neither. A question whose only row could not be worked
        out has not been answered no — it has not been answered, and the
        verdict says it cannot tell."""
        out = verdict(buffett,
                      known={k: v for k, v in CLEARS_ENTRY.items()
                             if k != "gross_margin_range_relative_5y"},
                      judged=SAID_YES)
        assert out["state"]["id"] == "cannot-screen"
        assert rollup(out)["pricing"]["outcome"] == "unknown"

    def test_the_count_a_group_demands_is_the_one_the_host_reads(
            self, buffett):
        """A group's bar is cited from the strategy's own setting rather than
        stated, so the number the strategy screened against and the number
        the reader is shown cannot be two numbers."""
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES)
        for gid, setting in (("cash", "cash-tests-required"),
                             ("growth", "growth-tests-required")):
            group = rollup(out)[gid]
            assert group["test"]["threshold_from"]["id"] == setting
            assert group["test"]["threshold"] == values_for(buffett)[setting]

    def test_raising_a_groups_bar_is_a_real_tightening(self, buffett):
        """The settings do something. Demanding both cash readings refuses a
        company that passes one — which is the user making the strategy
        stricter, on the record, rather than a number that does nothing."""
        weak = {**CLEARS_ENTRY, "cash_conversion_median_5y": 0.4}
        assert verdict(buffett, known=weak,
                       judged=SAID_YES)["state"]["id"] == \
            "wonderful-and-priced"
        assert verdict(buffett, known=weak, judged=SAID_YES,
                       **{"cash-tests-required": 2})["state"]["id"] == \
            "not-wonderful-enough"

    def test_a_failed_bonus_test_never_blocks(self, buffett):
        out = verdict(buffett, known={**CLEARS_ENTRY,
                                      "payout_to_fcf_median_5y": 130.0,
                                      "current_ratio": 0.6},
                      judged=SAID_YES)
        assert out["state"]["id"] == "wonderful-and-priced"
        assert rollup(out)["bonus"]["outcome"] == "noted"

    def test_the_tax_band_reads_as_two_tests_and_says_which_end(self, buffett):
        out = verdict(buffett, known={**CLEARS_ENTRY,
                                      "effective_tax_rate_median_5y": 4.0},
                      judged=SAID_YES)
        got = outcomes(out)
        assert got["bonus/effective_tax_rate_median_5y:at_least"] == "fail"
        assert got["bonus/effective_tax_rate_median_5y:at_most"] == "pass"

    def test_the_rollup_is_the_hosts_count_and_not_a_tally(self, buffett):
        out = verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES)
        groups, got = rollup(out), outcomes(out)
        assert sum(groups[g]["tested"]
                   for g in set(DIMENSION_OF.values())) == 10
        for gid in set(DIMENSION_OF.values()):
            assert groups[gid]["passed"] == sum(
                1 for k, v in got.items()
                if k.startswith(gid + "/") and v == "pass"), gid


class TestEveryDeclaredStateIsReachable:
    """A state nobody can reach is vocabulary the screen shows and the
    journal never uses. Twelve declared, twelve driven."""

    def test_all_twelve(self, buffett):
        results = [
            verdict(buffett, known=CLEARS_ENTRY,
                    judged=SAID_YES),
            verdict(buffett, known=CLEARS_ENTRY),
            verdict(buffett, known=CLEARS_ENTRY,
                    judged={**SAID_YES, "moat_durability": False}
                    ),
            verdict(buffett, known={**CLEARS_ENTRY, "roic_median_5y": 6.0}
                    ),
            verdict(buffett, known={}),
            verdict(buffett, known=CLEARS_ENTRY, judged=SAID_YES,
                    occupied=10),
            verdict(buffett, known=CLEARS_EXITS, judged=SAID_YES, held=True,
                    opened="2019-04-01", weight=52.0),
            verdict(buffett, known=CLEARS_EXITS, judged=SAID_YES, held=True,
                    opened="2019-04-01", weight=14.0),
            verdict(buffett, known={**CLEARS_EXITS,
                                    "total_debt_to_avg_fcf_5y": 6.4},
                    judged=SAID_YES, held=True, opened="2019-04-01",
                    weight=14.0,
                    series={"total_debt_to_avg_fcf_5y":
                            [(q, 1.4) for q in QUARTERS[:-1]]
                            + [(QUARTERS[-1], 6.4)]}),
            verdict(buffett, known={**CLEARS_EXITS,
                                    "total_debt_to_avg_fcf_5y": 6.4},
                    judged=SAID_YES, held=True, opened="2019-04-01",
                    weight=14.0,
                    series={"total_debt_to_avg_fcf_5y":
                            [(q, 6.4) for q in QUARTERS]}),
            verdict(buffett, known=CLEARS_EXITS,
                    judged={**SAID_YES, "capital_allocation": False},
                    held=True, opened="2019-04-01",
                    weight=14.0),
            verdict(buffett, known={}, judged=SAID_YES, held=True,
                    opened="2019-04-01", weight=14.0),
        ]
        # The documented floor, from the shared helper. Buffett's own
        # authoring is where host:invalid-decision was found the hard way,
        # one contradicted commit at a time.
        assert strategy_floor.unmet(buffett, results) == []


# ---------------------------------------------------------------------------
# through the real machinery
# ---------------------------------------------------------------------------

class TestThroughTheRealContext:
    """One pass through the machinery the app actually uses, so the
    hand-built contexts above cannot drift from the shape the host serves."""

    def test_hand_entered_figures_and_a_real_assessment(self, buffett):
        security = {"ticker": "WDGE", "name": "Wedgemoor Fasteners",
                    "cik": 5151, "lots": []}
        facts_store.save_filing(5151, filing(
            "WDGE-1", "10-K", "2026-02-11", "2025-12-31",
            [dur("us-gaap:Revenues", "2025-01-01", "2025-12-31", 900)]
            + balance_face("2025-12-31", assets=700)))
        entered(security, **CLEARS_ENTRY)

        def evaluate():
            return contract.evaluate(
                buffett, context.build_context(security, [security],
                                               values_for(buffett), {},
                                               record=buffett))

        blocked = evaluate()
        assert blocked["state"]["id"] == "judgement-owed"
        assert cited_judgements(blocked) == list(QUALITATIVE)

        for mid in QUALITATIVE:
            judgements.assess(security, mid, "pass",
                              "Invented company; invented reasoning.")
        bought = evaluate()
        assert bought["state"]["id"] == "wonderful-and-priced"
        row = next(i for i in bought["reason"]["evidence"]
                   if i["subject"]["id"] == "moat_durability")
        assert row["subject"]["kind"] == "judgement"
        assert row["observed"]["value"] is True
        assert row["outcome"] == "pass"
        # The reasoning the user wrote travels with the answer, so a screen
        # showing the verdict can show what they said.
        assert any("Invented company" in p
                   for p in row["observed"]["provenance"])

    def test_a_number_can_never_be_typed_over_a_question(self, buffett):
        """A judgement is not a measurement, and the refusal is structural on
        both sides of the store rather than a convention this file keeps."""
        security = {"ticker": "WDGE", "name": "Wedgemoor Fasteners",
                    "lots": []}
        from engine import hand_entered
        with pytest.raises(ValueError) as caught:
            hand_entered.record(security, "moat_durability", 1.0)
        assert "judgement" in str(caught.value)

    def test_a_journal_with_no_data_at_all_says_so(self, buffett):
        security = {"ticker": "NONE", "name": "Nothing Fetched", "lots": []}
        result = contract.evaluate(
            buffett, context.build_context(security, [security],
                                           values_for(buffett), {},
                                           record=buffett))
        assert result["state"]["id"] == "cannot-screen"
        assert result["render"] == "unknown"


class TestTheCompaniesItWillNotJudge:
    """Three kinds of company get a refusal rather than a verdict — and
    unlike Graham's, this refusal is meant to be temporary.

    All three tests this strategy will not bend are category errors on a
    lender, and the third one is worse than useless. Owner earnings starts
    from cash from operations, and for a bank that figure moves with the
    period's change in loans and deposits rather than with the business — so
    a bank that is SHRINKING produces the largest owner earnings of all. That
    is not a gap that renders as grey and gets ignored. It is a big confident
    number pointing the wrong way, on one of the three tests that decide
    whether money goes in.
    """

    def test_a_company_that_would_otherwise_buy_is_refused(self, buffett):
        result = contract.evaluate(
            buffett, build(buffett, known=CLEARS_ENTRY,
                           judged=dict.fromkeys(
                               ("moat_durability", "management_integrity",
                                "capital_allocation"), True),
                           industry="depository-lending"))
        assert result["render"] == "inapplicable"
        assert result["produced_by"] == "host"
        assert "Buffett does not evaluate banks and lenders" in \
            result["reason"]["summary"]

    def test_the_refusal_says_the_measures_are_missing_not_the_view(
            self, buffett):
        """The difference between this and Graham's, said out loud where a
        reader will meet it. Buffett has plenty to say about banks; what is
        missing is measures built for them."""
        because = contract.declined_classes(buffett)["depository-lending"]
        assert "not in this program" in because

    def test_it_is_refused_before_the_three_questions_are_asked(self, buffett):
        """Nobody should be assessing the durability of a business their own
        rules are not going to evaluate. The gate runs first, so the
        judgement questions are never cited and never appear."""
        result = contract.evaluate(
            buffett, build(buffett, known=CLEARS_ENTRY,
                           industry="depository-lending"))
        cited = {e["subject"]["id"] for e in result["reason"]["evidence"]}
        assert cited == {"security.industry", "security.sic"}

    @pytest.mark.parametrize(
        "cls", ["depository-lending", "insurance", "real-estate"])
    def test_every_declined_class_says_why_in_its_own_words(self, buffett,
                                                            cls):
        result = contract.evaluate(
            buffett, build(buffett, known=CLEARS_ENTRY, industry=cls))
        assert contract.declined_classes(buffett)[cls] in \
            result["reason"]["summary"]

    def test_an_ordinary_business_is_untouched(self, buffett):
        result = contract.evaluate(buffett, build(buffett, known=CLEARS_ENTRY))
        assert result["produced_by"] == "strategy"


class TestWhatARedefinedMeasureCostsThisStrategy:
    """One measure — return on invested capital — and the whole of what a
    moved definition costs Buffett rides on it.

    The return-on-capital exit is compound on purpose: returns must have
    fallen by a third of what they were AND be under an absolute floor.
    Only the first half measures back to a purchase, so only the first half
    can be withheld when the definition moves — and the exit requires both,
    so withholding one ends it. This strategy then has four exits instead of
    five, and the one it loses is the one it is named for: a wonderful
    business that stopped being wonderful.

    Nothing happens while returns are clear of the floor. The compound test
    answers "clear" on the absolute half alone, so a redefinition costs
    exactly nothing until the day the floor is broken — which is the day it
    would have mattered.
    """

    def holding(self, buffett, roic, was=None):
        return build(buffett, known={**CLEARS_EXITS, "roic_median_5y": roic},
                     series={"roic_median_5y": [(d, roic) for d in
                                                ("2025-06-30", "2025-09-30",
                                                 "2025-12-31", "2026-03-31")]},
                     held=True, opened="2026-01-05", weight=3.0,
                     judged=SAID_YES,
                     bought={"first": {"roic_median_5y": was or roic},
                             "last": {"roic_median_5y": was or roic}})

    def test_nothing_moves_while_returns_are_clear_of_the_floor(self,
                                                                buffett):
        held = self.holding(buffett, 18.0)
        before = contract.evaluate(buffett, held)
        after = contract.evaluate(buffett,
                                  redefined_since(held, "roic_median_5y"))
        assert before["state"]["id"] == after["state"]["id"] == \
            "room-for-more"
        assert before["reason"]["summary"] == after["reason"]["summary"]

    def test_the_exit_it_is_named_for_can_no_longer_fire(self, buffett):
        """Returns halved and under the floor: both halves failed, and the
        position closes. With the drift half withheld it does not — and the
        summary says one test could not be worked out rather than counting
        it as clear, which is the difference between a rule that has stopped
        firing and a rule that has quietly started passing."""
        held = self.holding(buffett, 6.0, was=12.0)
        before = contract.evaluate(buffett, held)
        assert (before["state"]["id"], before["render"]) == \
            ("business-broken", "close")

        after = contract.evaluate(buffett,
                                  redefined_since(held, "roic_median_5y"))
        assert after["render"] == "hold"
        assert "1 could not be worked out and is listed below as unknown " \
            "rather than as passing" in after["reason"]["summary"]

    def test_the_other_four_exits_still_run(self, buffett):
        held = self.holding(buffett, 6.0, was=12.0)
        after = contract.evaluate(buffett,
                                  redefined_since(held, "roic_median_5y"))
        assert "All 4 exit tests that could be run came back clear" in \
            after["reason"]["summary"]
