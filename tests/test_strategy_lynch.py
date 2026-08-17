"""Lynch, the third real strategy written against the contract.

What is pinned here is what would fail *silently*, and three of those things
are new — neither Graham nor Buffett exercises any of them.

- **Entry and exit are different measures, and the exit is the fast one.**
  Every strategy before this bought and sold on the same figure. The whole
  argument for splitting them is that a rate whose ends are three-year means
  cannot fall below an exit level until the bad years have worked their way
  into an average — so the pinned fact is that a company whose growth has
  just stopped exits on the trailing twelve months while its five-year rate
  is still comfortably above the level that bought it. If the exit ever
  drifts back onto the long measure, this file goes red.
- **A tiny base routes, and it takes both readings to route it.** Where the
  earnings at the base of the window were almost nothing *and* the margin was
  almost nothing, the verdict names a turnaround. Either reading alone must
  not — each of them on its own fires on companies that grew perfectly
  ordinarily, which is exactly the false positive the pair exists to avoid.
- **The growth exit needs sales to agree.** Earnings falling while sales keep
  rising is an expensive year, not a company that has stopped growing, and a
  strategy that sold on the first would sell every good business that ever
  invested in itself.

And three promises this strategy makes in prose, which decays:

- **Price can end a position here**, which is the sharpest disagreement with
  the Buffett bundle in the same program.
- **Time cannot.** No holding period, no clock, no state that closes for age.
- **Nothing trims.** No state in the bundle reduces a position, so a holding
  that has grown past the cap is left alone and told so.

The contexts below are built by hand rather than from filings, for the same
reason Graham's and Buffett's are: driving sixteen measures to chosen values
through the compute layer would test the compute layer. One class at the end
goes the whole way through `context.build_context` so the hand-built shape
cannot drift from the real one.
"""

import pytest

from conftest import industry_node, redefined_since

from engine import context, contract
from engine import strategy_floor, strategy_loader, strategy_values

# Every bank measure this strategy reads, entry and exit together.
MEASURES = ("earnings_base_share_5y", "net_margin_base_share_5y",
            "peg_trailing", "eps_cagr_5y", "debt_to_equity",
            "eps_minus_revenue_cagr_spread_5y",
            "dividend_adjusted_peg", "pe_to_own_5y_median_pe",
            "revenue_cagr_3y",
            "inventory_minus_revenue_growth_yoy",
            "receivables_minus_revenue_growth_yoy", "gross_margin_change_3y",
            "interest_coverage", "fcf_ttm",
            "net_cash_to_market_cap", "insider_net_buying_6m",
            "eps_change_yoy", "revenue_change_yoy")

# Which group each second-tier measure is cited under, so a test can say
# "make this question fail" without restating the strategy's own arrangement.
QUESTION_OF = {
    "dividend_adjusted_peg": "price", "pe_to_own_5y_median_pe": "price",
    "revenue_cagr_3y": "growing",
    "inventory_minus_revenue_growth_yoy": "real",
    "receivables_minus_revenue_growth_yoy": "real",
    "gross_margin_change_3y": "real",
    "interest_coverage": "survives", "fcf_ttm": "survives",
}

# A company that clears every entry test. Invented, like everything else
# presented as an example here. Growing profits at 18% a year on sales
# growing at 12, priced at 0.85 times its growth rate, barely borrowing.
CLEARS_ENTRY = {
    "earnings_base_share_5y": 48.0, "net_margin_base_share_5y": 82.0,
    "peg_trailing": 0.85, "eps_cagr_5y": 18.0, "debt_to_equity": 0.22,
    "eps_minus_revenue_cagr_spread_5y": 6.0,
    "dividend_adjusted_peg": 0.82, "pe_to_own_5y_median_pe": 0.91,
    "revenue_cagr_3y": 12.0,
    "inventory_minus_revenue_growth_yoy": 1.5,
    "receivables_minus_revenue_growth_yoy": 2.0,
    "gross_margin_change_3y": 0.8,
    "interest_coverage": 19.0, "fcf_ttm": 42_000_000.0,
    "net_cash_to_market_cap": 0.06, "insider_net_buying_6m": 24_000.0,
}

# The same company once held: the two measures no entry test looks at.
CLEARS_EXITS = {**CLEARS_ENTRY, "eps_change_yoy": 16.0,
                "revenue_change_yoy": 11.0}

QUARTERS = ("2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
            "2026-03-31")


@pytest.fixture
def lynch():
    strategies, reports = strategy_loader.discover()
    record = strategies.get("lynch")
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


def build(record, known=None, series=None, held=False, opened=None,
          weight=None, occupied=0, today="2026-08-09", bought=None,
          purchases=1, industry=None, **override):
    """A context shaped exactly as engine/context builds one.

    `bought` is what was on record at the anchor purchases. Left out on a
    holding, both anchors carry today's figures — nothing has moved since
    either purchase, so an unchanged company is the default and a fall in the
    growth rate is something a test has to ask for.
    """
    known, series = known or {}, series or {}
    measures = {}
    for mid in MEASURES:
        current = ({"status": "known", "value": known[mid],
                    "source": "manual", "cautions": [], "provenance": []}
                   if mid in known else
                   {"status": "absent", "reason": "nothing is on record"})
        points = [{"period_end": pe, "filed": pe, "form": "10-Q",
                   "accession": pe, "value": value,
                   "reason": None if value is not None else "unreadable",
                   "cautions": [], "provenance": []}
                  for pe, value in series.get(mid, ())]
        measures[mid] = {"current": current,
                         "series": {"cadence": "quarterly", "points": points,
                                    "note": None, "truncated": False}}
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
        # An ordinary operating business unless a test asks otherwise. This
        # strategy declines three kinds, and the gate refuses them before
        # `decide` is called at all.
        "security": {"ticker": "KELVIN", "name": "Kelvinside Instruments",
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


def held_verdict(record, known=None, **kw):
    return verdict(record, known=known or CLEARS_EXITS, held=True,
                   opened="2024-02-01", weight=8.0, **kw)


def key_of(item):
    """A citation's address, unambiguous across one decision."""
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


def failing_run(value):
    """A series carrying one failing reading at each of the last two
    quarters — enough to confirm anything that takes two filings."""
    return [(QUARTERS[-2], value), (QUARTERS[-1], value)]


# ---------------------------------------------------------------------------
# the numbers themselves
# ---------------------------------------------------------------------------

class TestTheThresholdsAreTheirSources:
    """Every level, typed out here from the sources rather than read out of
    the bundle. A quiet retune is what this project exists to catch, so a
    file that read the shipped numbers and compared them with themselves
    would be decoration."""

    # The expert report's, at the level it states, by way of
    # dev_reference_docs/legacy-profiles/lynch.yaml.
    REPORT = {
        "max-peg": 1.0, "max-eps-growth": 35, "max-debt-to-equity": 0.5,
        "max-dividend-adjusted-peg": 1.0, "max-pe-to-own-median": 1.0,
        "max-inventory-spread": 5, "max-receivables-spread": 5,
        "min-gross-margin-change": -2, "min-interest-coverage": 5,
        "min-free-cash-flow": 0, "min-net-cash": 0, "min-insider-buying": 0,
        "exit-peg": 2.0, "exit-debt-to-equity": 1.0,
        "exit-interest-coverage": 3, "exit-free-cash-flow": 0,
        "exit-inventory-spread": 20, "exit-receivables-spread": 20,
        "exit-eps-growth": 8, "exit-revenue-growth": 3,
    }

    # The second review's, where it overruled the report. The two base
    # readings are its construction; the growth floor is its correction to
    # the report's 15; the spread's LEVEL is the report's and its being a
    # knockout is the review's, so it appears in both dictionaries at the
    # same number and that is not a mistake.
    REVIEW = {
        "min-eps-growth": 10, "max-growth-spread": 10,
        "min-earnings-base-share": 10, "min-margin-base-share": 50,
    }

    # Nobody's but the bundle author's.
    AUTHOR = {"price-tests-required": 1, "quality-tests-required": 2,
              "min-revenue-growth": 5, "position-weight-cap": 25,
              "minimum-add": 10}

    # Lynch's own documented advice.
    LYNCH = {"portfolio-slots": 8}

    @pytest.mark.parametrize("source", ["REPORT", "REVIEW", "AUTHOR",
                                        "LYNCH"])
    def test_the_shipped_defaults_are_what_the_source_says(self, lynch,
                                                           source):
        values = values_for(lynch)
        for key, want in getattr(self, source).items():
            assert values[key] == want, key

    def test_every_declared_value_is_accounted_for_above(self, lynch):
        """So a value added later cannot slip in without somebody writing
        down where its number came from."""
        declared = {v["id"] for v in lynch["values"]}
        named = set(self.REPORT) | set(self.REVIEW) | set(self.AUTHOR) \
            | set(self.LYNCH)
        assert declared == named

    def test_the_growth_floor_admits_a_stalwart(self, lynch):
        """The single most consequential number here, pinned as behaviour
        rather than as a figure. The review's whole argument is that a 15%
        floor can only ever buy one of the six kinds of company Lynch sorted
        into, so a company growing at 11% has to be buyable."""
        assert verdict(lynch, known={**CLEARS_ENTRY, "eps_cagr_5y": 11.0,
                                     "revenue_cagr_3y": 6.0,
                                     "eps_minus_revenue_cagr_spread_5y": 5.0}
                       )["render"] == "commit"

    def test_the_sales_floor_does_not_shut_the_stalwart_out_again(self,
                                                                 lynch):
        """The report's 10% sales bar would have excluded exactly the
        companies the growth floor came down to admit, through a different
        door. Put it back to 10 and the same company is refused, which is
        what the value's own explanation says."""
        stalwart = {**CLEARS_ENTRY, "eps_cagr_5y": 11.0,
                    "revenue_cagr_3y": 6.0,
                    "eps_minus_revenue_cagr_spread_5y": 5.0}
        result = verdict(lynch, known=stalwart, **{"min-revenue-growth": 10})
        assert result["state"]["id"] == "not-growth-at-this-price"


# ---------------------------------------------------------------------------
# a base too small to compound from
# ---------------------------------------------------------------------------

class TestARecordThatDoesNotEstablishAGrower:
    """The addendum's correction: a tiny or negative base is not "cannot be
    assessed", it is a statement that the earnings appeared rather than grew.

    It takes both readings, and that is the part most likely to be broken by
    somebody simplifying it later. Each of them alone fires on companies that
    grew straightforwardly — the earnings multiple on a company whose sales
    multiplied as fast as its profits, the margin share on any ordinary
    scaling business expanding from eight percent to twelve.
    """

    APPEARED = {**CLEARS_ENTRY, "earnings_base_share_5y": 3.1,
                "net_margin_base_share_5y": 6.0}

    def test_both_readings_failing_names_a_turnaround(self, lynch):
        result = verdict(lynch, known=self.APPEARED)
        assert result["state"]["id"] == "not-established-as-a-grower"
        assert result["render"] == "hold"
        assert result["reason"]["rule"] == "earnings-appeared-rather-than-grew"

    def test_a_negative_base_routes_the_same_way(self, lynch):
        """Losses at the base of the window and profits at the end of it.
        Both readings come back negative, both fail, and the verdict is the
        same one — which is the point: "small or negative" is one case and
        not two, because a company that was losing money then has not shown
        a growth rate either.

        The growth rate is absent here for a different reason from the
        turnaround above — no compound rate exists from a negative base at
        all — and this strategy does not have to know that. It routes on two
        figures it can see rather than on why a third is missing.
        """
        result = verdict(lynch, known={**CLEARS_ENTRY,
                                       "earnings_base_share_5y": -30.0,
                                       "net_margin_base_share_5y": -40.2})
        assert result["state"]["id"] == "not-established-as-a-grower"

    def test_the_earnings_reading_alone_does_not(self, lynch):
        """A company whose sales multiplied about as fast as its profits
        reads low here and grew."""
        result = verdict(lynch, known={**CLEARS_ENTRY,
                                       "earnings_base_share_5y": 3.1})
        assert result["state"]["id"] != "not-established-as-a-grower"

    def test_the_margin_reading_alone_does_not(self, lynch):
        """On its own this is a margin-expansion test, and expanding margins
        while genuinely growing is what a good scaling business does."""
        result = verdict(lynch, known={**CLEARS_ENTRY,
                                       "net_margin_base_share_5y": 40.0})
        assert result["state"]["id"] != "not-established-as-a-grower"

    def test_an_unreadable_reading_is_never_one_of_the_two(self, lynch):
        """A company whose accounts do not reach back eight years has not
        been shown to be a turnaround. It has not been shown to be anything,
        and absence must not walk through this gate by failing to trip it."""
        thin = {k: v for k, v in CLEARS_ENTRY.items()
                if k not in ("earnings_base_share_5y",
                             "net_margin_base_share_5y", "eps_cagr_5y",
                             "peg_trailing")}
        result = verdict(lynch, known=thin)
        assert result["state"]["id"] == "cannot-screen"
        assert result["render"] == "unknown"

    def test_it_is_reached_before_the_growth_rate_is_missed(self, lynch):
        """The routing has to come first in the ladder. When it fires the
        growth rate is usually absent — which is what the metric bank does
        with the same two quantities — so a strategy that screened first
        would report "not enough to go on" and tell the reader nothing."""
        appeared_no_rate = {k: v for k, v in self.APPEARED.items()
                            if k not in ("eps_cagr_5y", "peg_trailing",
                                         "dividend_adjusted_peg",
                                         "eps_minus_revenue_cagr_spread_5y")}
        assert verdict(lynch, known=appeared_no_rate)["state"]["id"] == \
            "not-established-as-a-grower"

    def test_it_cites_the_two_readings_and_nothing_else(self, lynch):
        """Nobody is walked through fourteen rows about a rate that does not
        exist. Citing is what puts a question on the page."""
        result = verdict(lynch, known=self.APPEARED)
        assert set(outcomes(result)) == {
            "base/earnings_base_share_5y:at_least",
            "base/net_margin_base_share_5y:at_least"}

    def test_a_holding_stops_taking_money_but_is_not_sold(self, lynch):
        """The exits are about the business and the price, and neither of
        these is either. So this bars an add and says so, and closes
        nothing."""
        result = held_verdict(lynch, known={**CLEARS_EXITS,
                                            "earnings_base_share_5y": 3.1,
                                            "net_margin_base_share_5y": 6.0})
        assert result["state"]["id"] == "hold"
        assert result["reason"]["rule"] == "no-longer-establishes-a-grower"


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------

class TestWhatItWillBuy:
    def test_a_company_that_clears_everything_is_bought(self, lynch):
        result = verdict(lynch, known=CLEARS_ENTRY)
        assert result["state"]["id"] == "worth-buying"
        assert result["render"] == "commit"
        assert result["payload"]["size"] == {"unit": "weight", "value": 12.5}
        assert result["payload"]["plan"] is None

    @pytest.mark.parametrize("measure,bad", [
        ("peg_trailing", 1.4),
        ("eps_cagr_5y", 4.0),
        ("eps_cagr_5y", 61.0),
        ("debt_to_equity", 0.9),
        ("eps_minus_revenue_cagr_spread_5y", 24.0),
    ])
    def test_one_knockout_is_enough(self, lynch, measure, bad):
        result = verdict(lynch, known={**CLEARS_ENTRY, measure: bad})
        assert result["state"]["id"] == "not-growth-at-this-price"
        assert result["reason"]["rule"] == "knockout-failed"

    def test_the_growth_band_is_two_comparisons(self, lynch):
        """A band is two rows because the host has no `between`, and the
        point of two rows is that the reader is told which end was missed."""
        fast = outcomes(verdict(lynch,
                                known={**CLEARS_ENTRY, "eps_cagr_5y": 61.0}))
        assert fast["knockouts/eps_cagr_5y:at_least"] == "pass"
        assert fast["knockouts/eps_cagr_5y:at_most"] == "fail"

    def test_one_of_the_two_price_tests_is_enough(self, lynch):
        """The direct answer to the review's double-gate warning: in a period
        when a whole category re-rates, the test against a company's own
        history fails for everything in it."""
        result = verdict(lynch, known={**CLEARS_ENTRY,
                                       "pe_to_own_5y_median_pe": 1.6})
        assert result["render"] == "commit"
        assert rollup(result)["price"]["outcome"] == "pass"

    def test_both_price_tests_failing_is_not(self, lynch):
        result = verdict(lynch, known={**CLEARS_ENTRY,
                                       "pe_to_own_5y_median_pe": 1.6,
                                       "dividend_adjusted_peg": 1.3})
        assert result["state"]["id"] == "not-growth-at-this-price"
        assert result["reason"]["rule"] == "question-short"

    def test_a_company_with_no_warehouse_can_still_be_bought(self, lynch):
        """Software and services hold no inventory, so that row is absent for
        them permanently. Demanding all three would leave every such company
        undecided forever — an unreadable row is not a passing one — and
        Lynch owned plenty of businesses with nothing in a warehouse."""
        no_stock = {k: v for k, v in CLEARS_ENTRY.items()
                    if k != "inventory_minus_revenue_growth_yoy"}
        result = verdict(lynch, known=no_stock)
        assert result["render"] == "commit"
        assert rollup(result)["real"]["outcome"] == "pass"

    def test_two_of_the_three_quality_tests_failing_is_not_enough(self,
                                                                 lynch):
        result = verdict(lynch, known={**CLEARS_ENTRY,
                                       "gross_margin_change_3y": -7.0,
                                       "receivables_minus_revenue_growth_yoy":
                                           14.0})
        assert result["state"]["id"] == "not-growth-at-this-price"

    def test_an_unreadable_test_is_never_a_passing_one(self, lynch):
        """The quietest bug available: absence walking through a gate by
        failing to trip it. The knockouts are `all`, so one unreadable row
        makes the whole thing undecided rather than passed."""
        blind = {k: v for k, v in CLEARS_ENTRY.items() if k != "debt_to_equity"}
        result = verdict(lynch, known=blind)
        assert result["state"]["id"] == "cannot-screen"
        assert rollup(result)["knockouts"]["outcome"] == "unknown"

    def test_a_full_list_says_so_rather_than_talking_you_down(self, lynch):
        result = verdict(lynch, known=CLEARS_ENTRY, occupied=8)
        assert result["state"]["id"] == "no-room"
        assert result["render"] == "hold"

    def test_the_reported_rows_never_block(self, lynch):
        """Net cash and insider buying are shown and decide nothing — the
        second of them is absent for everybody until somebody types it in."""
        thin = {k: v for k, v in CLEARS_ENTRY.items()
                if k not in ("net_cash_to_market_cap",
                             "insider_net_buying_6m")}
        result = verdict(lynch, known={**thin,
                                       "net_cash_to_market_cap": -0.4})
        assert result["render"] == "commit"
        assert rollup(result)["bonus"]["outcome"] == "noted"


# ---------------------------------------------------------------------------
# the exits
# ---------------------------------------------------------------------------

class TestTheGrowthExitIsNotTheGrowthTest:
    """The structural change this strategy exists to make.

    The entry rate is measured between three-year averages five years apart.
    The exit is the trailing twelve months against the twelve before. A
    company whose growth stopped last year still shows a fine five-year rate
    — that is arithmetic, not an opinion — and the pinned fact is that the
    position closes anyway.
    """

    # Growth over five years still 18%, because it is mostly the years before
    # last. Growth over the last twelve months, 3%, on two filings. Sales
    # agree at 1%.
    STOPPED = {**CLEARS_EXITS, "eps_change_yoy": 3.0,
               "revenue_change_yoy": 1.0}
    RUN = {"eps_change_yoy": failing_run(3.0)}

    def test_the_position_closes_while_the_five_year_rate_is_untouched(
            self, lynch):
        result = held_verdict(lynch, known=self.STOPPED, series=self.RUN)
        assert result["state"]["id"] == "growth-stopped"
        assert result["render"] == "close"
        assert result["payload"]["when"] == "2026-08-09"
        # The rate that bought it is still comfortably above the floor.
        assert outcomes(result)["decay/eps_change_yoy:at_least"] == "fail"

    def test_the_long_rate_alone_could_never_have_fired_it(self, lynch):
        """Said as arithmetic rather than as prose: the five-year rate on
        this company is 18%, which is well above any level that would close a
        position, and the company has stopped growing."""
        assert self.STOPPED["eps_cagr_5y"] > 8
        assert self.STOPPED["eps_change_yoy"] < 8

    def test_sales_still_growing_hold_the_position(self, lynch):
        """Earnings falling while sales rise is an expensive year, not a
        company that has stopped growing — so nothing closes, and the
        position is judged on the entry tests like any other."""
        result = held_verdict(lynch,
                              known={**self.STOPPED,
                                     "revenue_change_yoy": 9.0},
                              series=self.RUN)
        assert result["render"] != "close"

    def test_and_the_red_row_that_leaves_is_explained(self, lynch):
        """One failed row beside a verdict saying everything is clear is a
        contradiction to a reader unless somebody says otherwise."""
        result = held_verdict(lynch,
                              known={**self.STOPPED,
                                     "revenue_change_yoy": 9.0},
                              series=self.RUN)
        assert "sales are still growing" in result["reason"]["summary"]

    def test_sales_unreadable_leaves_it_unreadable_rather_than_clear(self,
                                                                     lynch):
        """A comparison nobody could make has not shown that nothing
        happened. With the corroboration absent the exit cannot fire, and it
        must not be reported as having come back clear either."""
        blind = {k: v for k, v in self.STOPPED.items()
                 if k != "revenue_change_yoy"}
        result = held_verdict(lynch, known=blind, series=self.RUN)
        assert result["render"] != "close"
        assert "1 could not be worked out" in result["reason"]["summary"]
        assert outcomes(result)["decay/eps_change_yoy:at_least"] == "fail"

    def test_one_filing_is_not_enough(self, lynch):
        result = held_verdict(lynch, known=self.STOPPED)
        assert result["state"]["id"] == "one-reading-past"
        assert result["render"] == "hold"

    def test_sales_are_cited_beside_it_whether_or_not_it_fires(self, lynch):
        """The two are one test, and a reader shown one of them has been
        shown half a rule."""
        clear = held_verdict(lynch)
        assert "decay/revenue_change_yoy:at_least" in outcomes(clear)


class TestPriceCanEndAPosition:
    """The sharpest disagreement between this strategy and the Buffett bundle
    in the same program, which has no valuation exit at all. Pinned because
    it is a promise made in prose in three files."""

    RAN = {**CLEARS_EXITS, "peg_trailing": 2.4}

    def test_a_multiple_that_ran_past_the_growth_closes_it(self, lynch):
        result = held_verdict(lynch, known=self.RAN,
                              series={"peg_trailing": failing_run(2.4)})
        assert result["state"]["id"] == "price-ran-ahead"
        assert result["render"] == "close"

    def test_nothing_about_the_business_is_claimed(self, lynch):
        result = held_verdict(lynch, known=self.RAN,
                              series={"peg_trailing": failing_run(2.4)})
        assert "Nothing about the business has broken" in \
            result["reason"]["summary"]

    def test_merely_no_longer_cheap_is_not_an_exit(self, lynch):
        """The gap between the level that buys and the level that sells is
        what stops this selling the moment something stops being a bargain."""
        result = held_verdict(lynch, known={**CLEARS_EXITS,
                                            "peg_trailing": 1.5})
        assert result["state"]["id"] == "hold"
        assert result["reason"]["rule"] == "would-not-buy-it-today"


class TestTheStoryBreaking:
    def test_the_warehouse_filling_up_fires_on_one_filing(self, lynch):
        """The measure compares two balance-sheet dates a year apart, so the
        next filing replaces the end carrying the noise rather than adding to
        a run. Waiting for a second reading would be waiting a year, and the
        host derives that from the metric bank rather than taking it from
        here."""
        result = held_verdict(
            lynch, known={**CLEARS_EXITS,
                          "inventory_minus_revenue_growth_yoy": 26.0},
            series={"inventory_minus_revenue_growth_yoy":
                    [(QUARTERS[-1], 26.0)]})
        assert result["state"]["id"] == "story-broke"
        assert result["render"] == "close"

    def test_borrowing_takes_two(self, lynch):
        """A balance sheet is a photograph of one morning."""
        heavy = {**CLEARS_EXITS, "debt_to_equity": 1.3}
        assert held_verdict(lynch, known=heavy)["state"]["id"] == \
            "one-reading-past"
        assert held_verdict(
            lynch, known=heavy,
            series={"debt_to_equity": failing_run(1.3)}
        )["state"]["id"] == "story-broke"

    def test_the_verdict_names_what_broke_in_the_banks_own_words(self, lynch):
        """Cited, not written. This strategy used to keep a clause for each of
        the five things that can break the story, with a fallback that printed
        the raw bank id into the sentence telling somebody to sell. It names
        the id now and the host supplies the label — the same one every row
        under the verdict already carries."""
        from engine import bank
        result = held_verdict(lynch, known={**CLEARS_EXITS,
                                            "fcf_ttm": -8_000_000.0},
                              series={"fcf_ttm": failing_run(-8_000_000.0)})
        rests = result["reason"]["rests_on"]
        assert [r["id"] for r in rests] == ["fcf_ttm"]
        assert rests[0]["label"] == bank.meta()["fcf_ttm"]["label"]
        # and the summary carries no measure name of its own
        assert "fcf" not in result["reason"]["summary"].lower()

    def test_the_rows_it_rests_on_are_marked_apart_from_the_rest(self, lynch):
        """The gap this closed. Every closing verdict cites all seven exits,
        and a verdict still one reading short of confirmation cites the same
        seven — so the rows alone could not say which of them decided it, and
        that difference is the whole point of a confirmation rule."""
        result = held_verdict(lynch, known={**CLEARS_EXITS,
                                            "fcf_ttm": -8_000_000.0},
                              series={"fcf_ttm": failing_run(-8_000_000.0)})
        marked = [e["subject"]["id"] for e in result["reason"]["evidence"]
                  if e.get("rests_on")]
        assert marked == ["fcf_ttm"]
        assert len(result["reason"]["evidence"]) > 1

    def test_a_verdict_still_waiting_rests_on_nothing(self, lynch):
        """The other side of the same fact. One reading past a threshold is
        not a decision yet, so nothing is built on it."""
        result = held_verdict(lynch, known={**CLEARS_EXITS,
                                            "fcf_ttm": -8_000_000.0})
        assert result["state"]["id"] == "one-reading-past"
        assert result["reason"]["rests_on"] == []

    def test_the_names_are_not_written_in_this_strategy_at_all(self, lynch):
        import pathlib
        src = pathlib.Path(lynch["dir"], "strategy.py").read_text()
        assert "_BROKE" not in src

    def test_solvency_is_reported_ahead_of_the_price(self, lynch):
        """Both fired; the state says which decided it. Borrowing can take
        the company away, and a multiple that ran ahead only takes the
        return."""
        result = held_verdict(
            lynch, known={**CLEARS_EXITS, "debt_to_equity": 1.3,
                          "peg_trailing": 2.4},
            series={"debt_to_equity": failing_run(1.3),
                    "peg_trailing": failing_run(2.4)})
        assert result["state"]["id"] == "story-broke"


class TestWhatCannotEndAPosition:
    def test_time_cannot(self, lynch):
        """No holding period, no clock, and nothing that closes for age. Ten
        years in, a company still growing is still held."""
        result = verdict(lynch, known=CLEARS_EXITS, held=True,
                         opened="2015-01-05", weight=9.0)
        assert result["state"]["id"] in ("hold", "room-for-more")

    def test_nothing_in_the_bundle_trims(self, lynch):
        """A state that reduced a position would be a different strategy.
        Declared vocabulary is what a reader can check, so the absence is
        pinned on the declaration rather than on behaviour."""
        assert not [s for s in lynch["states"] if s["render"] == "reduce"]

    def test_a_position_past_the_cap_is_left_alone_and_told_so(self, lynch):
        result = verdict(lynch, known=CLEARS_EXITS, held=True,
                         opened="2021-01-05", weight=38.0)
        assert result["state"]["id"] == "hold"
        assert result["reason"]["rule"] == "no-room-to-add"
        assert "no trim" in result["reason"]["summary"]

    def test_the_size_cap_is_cited_as_an_observation_not_a_test(self, lynch):
        """A row reading "at most your 25%" beside a holding at 38% renders
        as a failure, and a reader would take a failed row about position
        size to mean something is owed. Nothing is."""
        result = verdict(lynch, known=CLEARS_EXITS, held=True,
                         opened="2021-01-05", weight=38.0)
        assert outcomes(result)["sizing/position.weight"] == "noted"


class TestHoldingAndAdding:
    def test_a_clear_holding_with_room_may_take_more(self, lynch):
        result = held_verdict(lynch)
        assert result["state"]["id"] == "room-for-more"
        assert result["render"] == "commit"
        assert result["payload"]["size"] == {"unit": "weight", "value": 17.0}

    def test_an_add_is_measured_against_the_same_bar_as_a_purchase(self,
                                                                   lynch):
        result = held_verdict(lynch, known={**CLEARS_EXITS,
                                            "debt_to_equity": 0.7})
        assert result["state"]["id"] == "hold"
        assert result["reason"]["rule"] == "would-not-buy-it-today"

    def test_no_exit_readable_says_it_cannot_tell(self, lynch):
        result = verdict(lynch, known={}, held=True, opened="2024-02-01",
                         weight=8.0)
        assert result["state"]["id"] == "cannot-watch"
        assert result["render"] == "unknown"

    def test_the_drift_in_the_growth_rate_is_reported(self, lynch):
        """The single most useful number a holder of a growth company can
        see, and the only `since` citation in this bundle. It decides
        nothing — the exit is a statement about the rate now — but a screen
        that reported the rate without reporting how far it had fallen would
        leave the reader to remember what they bought."""
        result = held_verdict(
            lynch, bought={"first": {**CLEARS_EXITS, "eps_cagr_5y": 26.0}})
        assert outcomes(result)["time/eps_cagr_5y~since"] == "noted"

    def test_a_weight_nobody_could_work_out_stops_the_add(self, lynch):
        result = verdict(lynch, known=CLEARS_EXITS, held=True,
                         opened="2024-02-01")
        assert result["state"]["id"] == "hold"
        assert result["reason"]["rule"] == "size-unreadable"


# ---------------------------------------------------------------------------
# the contract's own refusals
# ---------------------------------------------------------------------------

class TestTheContractIsNeverContradicted:
    """One check that catches contradicted commits, dead-end blocks,
    malformed payloads and scattered groups at once, run over every case this
    file drives."""

    CASES = [
        {"known": CLEARS_ENTRY},
        {"known": CLEARS_ENTRY, "occupied": 8},
        {"known": {**CLEARS_ENTRY, "peg_trailing": 1.4}},
        {"known": {**CLEARS_ENTRY, "earnings_base_share_5y": 3.1,
                   "net_margin_base_share_5y": 6.0}},
        {"known": {}},
        {"known": CLEARS_EXITS, "held": True, "opened": "2024-02-01",
         "weight": 8.0},
        {"known": CLEARS_EXITS, "held": True, "opened": "2021-01-05",
         "weight": 38.0},
        {"known": {**CLEARS_EXITS, "eps_change_yoy": 3.0,
                   "revenue_change_yoy": 1.0},
         "series": {"eps_change_yoy": failing_run(3.0)},
         "held": True, "opened": "2024-02-01", "weight": 8.0},
        {"known": {**CLEARS_EXITS, "peg_trailing": 2.4},
         "series": {"peg_trailing": failing_run(2.4)},
         "held": True, "opened": "2024-02-01", "weight": 8.0},
        {"known": {**CLEARS_EXITS,
                   "inventory_minus_revenue_growth_yoy": 26.0},
         "series": {"inventory_minus_revenue_growth_yoy":
                    [(QUARTERS[-1], 26.0)]},
         "held": True, "opened": "2024-02-01", "weight": 8.0},
        {"known": {**CLEARS_EXITS, "debt_to_equity": 1.3},
         "held": True, "opened": "2024-02-01", "weight": 8.0},
        {"known": {}, "held": True, "opened": "2024-02-01", "weight": 8.0},
    ]

    def results(self, lynch):
        return [contract.evaluate(lynch, build(lynch, **case))
                for case in self.CASES]

    def test_no_case_is_refused_by_the_host(self, lynch):
        for case, result in zip(self.CASES, self.results(lynch)):
            assert result["produced_by"] == "strategy", \
                f'{case}: {result["reason"]["summary"]}'

    def test_every_declared_state_is_reached(self, lynch):
        """A state nothing returns is vocabulary on the Strategy tab telling
        a reader the tool can say something it cannot."""
        assert strategy_floor.unmet(lynch, self.results(lynch)) == []

    def test_the_rollup_a_reader_sees_is_the_hosts_own(self, lynch):
        """Counted from the rows the host resolved, never from a tally this
        bundle kept — and a group short of its bar with unreadable rows is
        undecided rather than failed."""
        result = verdict(lynch, known={k: v for k, v in CLEARS_ENTRY.items()
                                       if k != "interest_coverage"})
        assert rollup(result)["survives"]["outcome"] == "unknown"


# ---------------------------------------------------------------------------
# the companies it will not judge
# ---------------------------------------------------------------------------

class TestTheCompaniesItWillNotJudge:
    """Three kinds get a refusal rather than a verdict, and — like Buffett's
    and unlike Graham's — this one is a gap in the host rather than a
    boundary of the method. Lynch owned a great many thrifts and wrote
    explicit criteria for them; those criteria are not these."""

    @pytest.mark.parametrize(
        "cls", ["depository-lending", "insurance", "real-estate"])
    def test_every_declined_class_says_why_in_its_own_words(self, lynch, cls):
        result = contract.evaluate(
            lynch, build(lynch, known=CLEARS_ENTRY, industry=cls))
        assert result["render"] == "inapplicable"
        assert result["produced_by"] == "host"
        assert contract.declined_classes(lynch)[cls] in \
            result["reason"]["summary"]

    def test_the_refusal_names_the_thrifts_it_is_not_judging(self, lynch):
        because = contract.declined_classes(lynch)["depository-lending"]
        assert "thrifts" in because
        assert "not in this program" in because

    def test_an_ordinary_business_is_untouched(self, lynch):
        assert contract.evaluate(
            lynch, build(lynch, known=CLEARS_ENTRY))["produced_by"] == \
            "strategy"


# ---------------------------------------------------------------------------
# one pass through the real context builder
# ---------------------------------------------------------------------------

class TestAgainstAContextTheHostActuallyBuilds:
    """Without this the whole file can pass against a context shape that no
    longer exists."""

    def test_a_journal_with_no_data_at_all_says_so(self, lynch):
        security = {"ticker": "NONE", "name": "Nothing Fetched", "lots": []}
        result = contract.evaluate(
            lynch, context.build_context(security, [security],
                                         values_for(lynch), {},
                                         record=lynch))
        assert result["state"]["id"] == "cannot-screen"
        assert result["render"] == "unknown"

    def test_every_measure_it_reads_is_served_by_the_host(self, lynch):
        """A misspelled bank id comes back as a strategy error naming the
        line, and it would look like a missing figure everywhere else."""
        security = {"ticker": "NONE", "name": "Nothing Fetched", "lots": []}
        ctx = context.build_context(security, [security], values_for(lynch),
                                    {}, record=lynch)
        for mid in MEASURES:
            assert mid in ctx["measures"], mid


class TestWhatARedefinedMeasureCostsThisStrategy:
    """Nothing, and that is worth pinning rather than assuming.

    Lynch cites how five-year EPS growth has moved since the first purchase,
    and cites it for the reader alone — no comparator, no threshold, nothing
    branching on the answer. So a redefinition takes the figure off that one
    row, with the reason in its place, and every verdict this strategy can
    reach is the verdict it reached before.

    The row still appears. A citation that vanished would take with it the
    only sign that the question was ever asked.
    """

    def holding(self, lynch):
        return build(lynch, known=dict(CLEARS_EXITS), held=True,
                     opened="2026-01-05", weight=3.0)

    def test_no_verdict_moves(self, lynch):
        held = self.holding(lynch)
        before = contract.evaluate(lynch, held)
        after = contract.evaluate(lynch,
                                  redefined_since(held, "eps_cagr_5y"))
        assert before["state"] == after["state"]
        assert before["render"] == after["render"]
        assert before["reason"]["rule"] == after["reason"]["rule"]
        assert before["reason"]["summary"] == after["reason"]["summary"]

    def test_the_row_stays_and_carries_the_reason(self, lynch):
        after = contract.evaluate(lynch,
                                  redefined_since(self.holding(lynch),
                                                  "eps_cagr_5y"))
        [row] = [r for r in after["reason"]["evidence"]
                 if r["subject"]["kind"] == "change"]
        assert row["observed"]["status"] == "absent"
        assert "value" not in row["observed"]
        assert "not worked out to the same definition" in \
            row["observed"]["reason"]
        # Noted, never failed: a figure nobody could work out has not shown
        # that growth held and has not shown that it broke.
        assert row["outcome"] == "noted"
