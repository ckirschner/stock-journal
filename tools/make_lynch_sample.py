"""Builds data.template/sample-lynch.json — the third demonstration journal.

Every company and every figure below is invented. Nothing here is a
recommendation, a model portfolio, or a real security; the tickers are made
up and so are the numbers.

Run from the project root:

    python tools/make_lynch_sample.py

It is its own journal, beside the Graham and Buffett ones, because a journal
has exactly one strategy. That is the point rather than an inconvenience: the
three sit side by side in the app and the same kind of company gets different
verdicts from them, which is the clearest way to show what committing to one
strategy actually means.

What it covers, and what it deliberately cannot
-----------------------------------------------
Eight of Lynch's twelve states. The four missing ones, and why — the second
group is the interesting one and it is worth reading before the stories.

- **"No room for it"** needs the journal at capacity. This strategy runs
  eight places, so demonstrating it would mean shipping eight holdings and
  seven of the stories would be the same word. The state is covered by the
  test suite instead.

- **All three closing states are unreachable here, and that is a fact about
  hand-kept journals rather than about this sample.** Every exit in this
  strategy is a measurement, and confirming a measured breach counts
  *filings*. No company in a sample is linked to a real filer, so there is no
  filing history to walk, so a breach can be crossed and never confirmed —
  the run is always nought.

  Graham's sample can close a position because one of its exits is a clock,
  and Buffett's can because one of its exits is a question the reader
  answered. **Lynch has neither.** So a Lynch journal driven entirely by hand
  — a company the SEC does not cover, or one nobody has fetched — will report
  that a level has been crossed and will never act on it, however bad the
  number gets.

  HAVERTY below sits in exactly that position and its notes say so plainly.
  It is the most important thing in this file.

The uncomfortable ones this sample makes a point of showing
-----------------------------------------------------------
- **A position that stopped growing and cannot be sold.** HAVERTY. Earnings
  are barely moving, sales agree, and the verdict is that one reading is not
  enough — which is correct and is also, in a hand-kept journal, permanent.
- **A tenbagger left alone.** DUNSFOLD is two fifths of the account and
  nothing here asks for a trim, because there is no verdict in this strategy
  that could. That is the arithmetic of the method working, and it is the
  part a reader is most likely to mistake for a bug.
- **A company whose growth is not growth.** KETTLEBY earns forty times what
  it earned five years ago and the journal declines to call it a grower,
  because it was earning almost nothing then and almost nothing per pound of
  sales. It is a turnaround, and the verdict says so rather than saying it
  cannot tell.
- **A stalwart that only one price test can read.** ALDBURY grows at eleven
  percent and pays a dividend. It fails the test against its own history and
  passes on growth-plus-yield, which is the reading Lynch used for exactly
  this kind of company — and it is the whole reason the growth floor came
  down from fifteen.
- **A holding worth keeping that is not worth buying.** PELSALL. Its price
  has run up without running away, so nothing sells it and nothing adds to
  it, and the verdict says which of those it is.
"""

from sample_kit import (buy, expect, journal, securities, security,
                        state_of, write)

from engine import portfolio

# The day the stories were written against. Fixed rather than relative, so
# the sample reads the same on the day it is built and a year later.
TODAY = "2026-08-12"

FREE_CASH = 30_000.0

# A company this strategy would buy: growing profits at nineteen percent a
# year on sales growing at fourteen, priced below its own growth rate, barely
# borrowing, and with nothing piling up in the warehouse. Every figure
# invented; the shape of the set is what matters.
GROWING = {
    "earnings_base_share_5y": 46.0, "net_margin_base_share_5y": 79.0,
    "peg_trailing": 0.82, "eps_cagr_5y": 19.0, "debt_to_equity": 0.24,
    "eps_minus_revenue_cagr_spread_5y": 5.0,
    "dividend_adjusted_peg": 0.80, "pe_to_own_5y_median_pe": 0.93,
    "revenue_cagr_3y": 14.0,
    "inventory_minus_revenue_growth_yoy": 1.2,
    "receivables_minus_revenue_growth_yoy": 2.4,
    "gross_margin_change_3y": 0.6,
    "interest_coverage": 17.0, "fcf_ttm": 38_000_000.0,
    "net_cash_to_market_cap": 0.05,
    # The two the entry tests never look at, and the two the exits turn on.
    "eps_change_yoy": 17.0, "revenue_change_yoy": 13.0,
}


def like(**over):
    return {**GROWING, **over}


journal("Sample — Lynch", "lynch", {}, cash=FREE_CASH)


# -- the one that worked, and is left alone ----------------------------------
# The state a reader most needs to see from this strategy and the one most
# likely to be mistaken for a bug. It has multiplied several times over since
# it was bought and is now two fifths of the account, and nothing here asks
# for a trim — because the method's arithmetic is that one or two names carry
# the rest, and a rule that cut them back would be cutting back the only part
# that pays for the misses.

security(
    "DUNSFOLD", "Dunsfold Diagnostics", 74.00,
    like(eps_cagr_5y=23.0, revenue_cagr_3y=18.0, peg_trailing=0.94,
         dividend_adjusted_peg=0.94, pe_to_own_5y_median_pe=0.97,
         eps_change_yoy=21.0, revenue_change_yoy=17.0,
         eps_minus_revenue_cagr_spread_5y=4.0),
    on="2026-08-04",
    earlier=("2021-05-10",
             like(eps_cagr_5y=24.0, peg_trailing=0.61,
                  dividend_adjusted_peg=0.61, pe_to_own_5y_median_pe=0.78,
                  revenue_cagr_3y=19.0, eps_change_yoy=26.0,
                  revenue_change_yoy=20.0), 9.80),
    thesis=("A bench-top analyser sold once and then fed with consumables "
            "for a decade. The machine is the loss leader and nobody swaps "
            "one out mid-study.",
            "The consumable gets a generic, or a competitor's machine takes "
            "a study protocol."),
    notes=[("2024-02-11",
            "Up more than fourfold. The journal has stopped offering to add "
            "and has never once suggested trimming. Read the strategy page: "
            "that is the design, not an oversight."),
           ("2026-08-04",
            "Two fifths of the account. Every instinct says take some off "
            "and the whole reason I wrote the rules down first was that "
            "this instinct is usually wrong — four of the other seven names "
            "went nowhere, and this is the one that paid for them.")])

buy("DUNSFOLD", 700, 9.80, "2021-05-17")


# -- a holding this strategy would still buy ---------------------------------
# The add case. It sits well under the cap, nothing has ended, and it still
# clears every entry test at today's price.

security(
    "ORRELL", "Orrell Fastenings", 58.00,
    like(eps_cagr_5y=17.0, revenue_cagr_3y=12.5, peg_trailing=0.88,
         dividend_adjusted_peg=0.86, pe_to_own_5y_median_pe=0.95,
         eps_change_yoy=15.0, revenue_change_yoy=11.0),
    on="2026-08-06",
    earlier=("2024-04-02",
             like(eps_cagr_5y=18.0, peg_trailing=0.71,
                  dividend_adjusted_peg=0.70, pe_to_own_5y_median_pe=0.84,
                  revenue_cagr_3y=13.0, eps_change_yoy=19.0,
                  revenue_change_yoy=14.0), 41.30),
    thesis=("Fixings specified into an aerospace maintenance manual, "
            "reordered without a decision being made, growing with the "
            "installed fleet.",
            "An airframe programme requalifies its fasteners, or the "
            "aftermarket goes to a distributor's own brand."),
    notes=[("2026-08-06",
            "Still growing and still not expensive against the growth. The "
            "journal says there is room. Whether this is the best home for "
            "the next pound is a question about the whole list rather than "
            "about this company.")])

buy("ORRELL", 300, 41.30, "2024-04-09")


# -- the growth stopped, and a hand-kept journal cannot act on it ------------
# The most important story in this file and the least comfortable. Earnings
# over the last twelve months are barely above the twelve before, sales
# agree, and the exit that this whole strategy is built around has therefore
# been crossed — on one reading.
#
# It will never be crossed on a second, because confirming a measured breach
# counts filings and nothing here is linked to a filer. Graham's sample can
# close a position on its clock and Buffett's on a question the reader
# answered; every exit in this strategy is a measurement, so a Lynch journal
# driven by hand reports the breach and never acts on it.

security(
    "HAVERTY", "Haverty Tooling", 26.50,
    like(eps_cagr_5y=16.0, revenue_cagr_3y=10.0, peg_trailing=0.74,
         dividend_adjusted_peg=0.74, pe_to_own_5y_median_pe=0.66,
         eps_change_yoy=1.8, revenue_change_yoy=0.4,
         inventory_minus_revenue_growth_yoy=4.1,
         gross_margin_change_3y=-1.4),
    on="2026-08-07",
    earlier=("2023-06-12",
             like(eps_cagr_5y=21.0, peg_trailing=0.66,
                  dividend_adjusted_peg=0.66, pe_to_own_5y_median_pe=0.81,
                  revenue_cagr_3y=17.0, eps_change_yoy=22.0,
                  revenue_change_yoy=18.0), 21.40),
    thesis=("Cutting tools for a machining market growing with reshored "
            "manufacturing, sold through distributors who reorder monthly.",
            "Order growth flattening for two quarters while the tool "
            "inventory keeps building."),
    notes=[("2026-08-07",
            "The falsifier I wrote in 2023 is the thing that happened. "
            "Earnings up under two percent, sales up almost nothing, and "
            "the five-year rate still says sixteen — which is exactly the "
            "problem the trailing exit exists to solve."),
           ("2026-08-09",
            "The journal says one reading is not enough and it is right in "
            "general and stuck in particular: it confirms breaches by "
            "counting filings, and I type these numbers in by hand, so "
            "there are none to count. It will sit here saying the same "
            "thing forever. That is on me and my record-keeping, not on the "
            "rule — but it is worth knowing that this journal will never "
            "tell me to sell anything.")])

buy("HAVERTY", 400, 21.40, "2023-06-19")


# -- worth keeping, not worth buying -----------------------------------------
# The asymmetry stated out loud. The price has run up without running away,
# so nothing sells it and nothing adds to it, and the verdict names which of
# those it is.

security(
    "PELSALL", "Pelsall Ceramics", 45.00,
    like(eps_cagr_5y=15.0, revenue_cagr_3y=11.0, peg_trailing=1.45,
         dividend_adjusted_peg=1.42, pe_to_own_5y_median_pe=1.31,
         eps_change_yoy=14.0, revenue_change_yoy=10.0),
    on="2026-08-05",
    earlier=("2024-09-03",
             like(eps_cagr_5y=16.0, peg_trailing=0.79,
                  dividend_adjusted_peg=0.78, pe_to_own_5y_median_pe=0.88,
                  revenue_cagr_3y=12.0, eps_change_yoy=17.0,
                  revenue_change_yoy=12.0), 28.60),
    thesis=("Technical ceramics for semiconductor tooling, where the part "
            "is a rounding error in the machine and a catastrophe if it "
            "fails.",
            "A customer qualifies a second source, or the fab build cycle "
            "turns down."),
    notes=[("2026-08-05",
            "Re-rated hard. The journal will not buy more and will not sell "
            "it either — the exit sits at twice the level that would buy, "
            "and it is nowhere near that. Two different questions with two "
            "different answers, which is what I wanted written down in "
            "advance.")])

buy("PELSALL", 250, 28.60, "2024-09-10")


# -- a holding nothing can be said about -------------------------------------
# Bought out of the reader's own records years later, with no figures ever
# entered. Not one exit test can run, so the strategy says it cannot tell
# rather than saying hold — and the purchase carries a recollection, which is
# never a thesis and never counted as one.

security("CASTERTON", "Casterton Papers", 33.00, {}, on="2026-08-03",
         notes=[("2026-08-03",
                 "Entered from an old statement. No figures in for it, so "
                 "the journal is honest about having nothing to say. It is "
                 "not telling me to hold — it is telling me it cannot "
                 "tell.")])

buy("CASTERTON", 200, 27.10, "2023-11-08",
    recollection="No figures on record for this. What I remember is buying "
                 "it because the speciality paper line had two customers "
                 "who could not qualify anyone else inside a year.")


# -- a company this strategy would buy today ---------------------------------
# Also the one place the insider row is filled in. Nothing in this program
# computes it — it lives in a kind of SEC filing this journal does not read —
# so it is blank everywhere until somebody looks it up and types it in, and
# the row is what gives them somewhere to do that.

security(
    "BRINDLE", "Brindle Water Systems", 39.50,
    like(eps_cagr_5y=21.0, revenue_cagr_3y=16.0, peg_trailing=0.79,
         dividend_adjusted_peg=0.79, pe_to_own_5y_median_pe=0.88,
         eps_change_yoy=20.0, revenue_change_yoy=15.0,
         insider_net_buying_6m=42_000.0),
    on="2026-08-10",
    notes=[("2026-08-10",
            "Two directors bought in the open market in June. Nothing here "
            "computes that — I read it off the filings myself and typed it "
            "in, which is what the blank row was asking for. It decides "
            "nothing on its own and I would not have looked at the company "
            "without it.")])


# -- the stalwart, and the reason the growth floor came down -----------------
# Eleven percent growth and a dividend. Under the report's original fifteen
# percent floor this was not buyable at all, which is what the second review
# objected to: Lynch sorted companies into six kinds and held these
# deliberately.
#
# It also shows the price group doing its job. Against its own five-year
# history it looks dear and fails; against growth plus yield it is cheap and
# passes. One of the two is enough, and the one that passes is the reading
# Lynch used for exactly this kind of company.

security(
    "ALDBURY", "Aldbury Household", 61.20,
    like(eps_cagr_5y=11.0, revenue_cagr_3y=6.5,
         eps_minus_revenue_cagr_spread_5y=4.5,
         peg_trailing=0.95, dividend_adjusted_peg=0.72,
         pe_to_own_5y_median_pe=1.18,
         eps_change_yoy=10.0, revenue_change_yoy=6.0,
         net_cash_to_market_cap=-0.09,
         earnings_base_share_5y=61.0, net_margin_base_share_5y=88.0),
    on="2026-08-09",
    notes=[("2026-08-09",
            "Not a fast grower and not meant to be. Eleven percent and a "
            "three percent yield is fourteen a year against a multiple of "
            "ten, and the journal reads that on the dividend-adjusted test "
            "because the plain one cannot see the yield at all."),
           ("2026-08-09",
            "It also fails the test against its own history and still "
            "passes the group, and the row showing net debt fails and "
            "blocks nothing. Both of those are the rules I set, working — "
            "not the tool being lenient.")])


# -- the earnings did not grow, they appeared --------------------------------
# Forty times the profit it made five years ago, and the journal declines to
# call it a grower. It was earning almost nothing then and almost nothing per
# pound of sales, so a compound rate off that base measures a margin coming
# back rather than a business selling more — and margin recovery has a
# ceiling that selling more does not.
#
# The growth rate itself is deliberately not on record here, because the
# metric bank refuses to compute one on this shape of history. That is the
# case: the reader is given the reason rather than a blank.

security(
    "KETTLEBY", "Kettleby Foundries", 12.80,
    {"earnings_base_share_5y": 2.6, "net_margin_base_share_5y": 4.9,
     "debt_to_equity": 0.44, "revenue_cagr_3y": 5.5,
     "interest_coverage": 6.2, "fcf_ttm": 4_100_000.0,
     "inventory_minus_revenue_growth_yoy": 3.0,
     "receivables_minus_revenue_growth_yoy": 1.8,
     "gross_margin_change_3y": 7.4,
     "pe_to_own_5y_median_pe": 0.71, "net_cash_to_market_cap": -0.22,
     "eps_change_yoy": 96.0, "revenue_change_yoy": 6.0},
    on="2026-08-08",
    notes=[("2026-08-08",
            "Profits up forty-fold in five years and the journal will not "
            "call it growth. It is right: sales are up a quarter and the "
            "margin went from almost nothing to eight percent, so what has "
            "happened is a recovery finishing, not a company getting "
            "bigger."),
           ("2026-08-08",
            "This may well still be a good investment. What it is not is "
            "the kind of company any test in this journal was built to "
            "judge, and the verdict says which question I should be asking "
            "instead — whether the balance sheet survives long enough for "
            "the recovery to finish.")])


# -- growing well, and already paid for --------------------------------------

security(
    "MOSSGIEL", "Mossgiel Robotics", 88.40,
    like(eps_cagr_5y=27.0, revenue_cagr_3y=22.0, peg_trailing=1.55,
         dividend_adjusted_peg=1.55, pe_to_own_5y_median_pe=1.42,
         eps_change_yoy=26.0, revenue_change_yoy=21.0),
    on="2026-08-11",
    notes=[("2026-08-11",
            "The best company on this list and the journal will not buy it. "
            "Growing at twenty-seven percent on a multiple of forty-two, "
            "which means three years of the growth is already in the price. "
            "Not a criticism of the company — it is the reason to wait.")])


# -- not enough to go on -----------------------------------------------------

security(
    "TREWIN", "Trewin Robotics Components", 24.60,
    {k: v for k, v in like(revenue_cagr_3y=13.0).items()
     if k not in ("peg_trailing", "eps_cagr_5y", "dividend_adjusted_peg",
                  "eps_minus_revenue_cagr_spread_5y")},
    on="2026-08-02",
    notes=[("2026-08-02",
            "Listed four years ago, so there are not eight years of "
            "accounts to measure a five-year growth rate between. The "
            "journal says it cannot tell rather than guessing, which is the "
            "only honest answer — a missing number is not a pass and it is "
            "not a failure. It will be answerable in 2030 and not before.")])


# ===========================================================================
# What each of them exists to show. Asserted against the real evaluator, so
# the sample cannot ship claiming a story it no longer tells.
# ===========================================================================

STORIES = {
    "DUNSFOLD": "hold",
    "ORRELL": "room-for-more",
    "HAVERTY": "one-reading-past",
    "PELSALL": "hold",
    "CASTERTON": "cannot-watch",
    "BRINDLE": "worth-buying",
    "ALDBURY": "worth-buying",
    "KETTLEBY": "not-established-as-a-grower",
    "MOSSGIEL": "not-growth-at-this-price",
    "TREWIN": "cannot-screen",
}

for ticker, want in STORIES.items():
    expect(ticker, want)

rows = securities()
by_ticker = {s["ticker"]: s for s in rows}

# The tenbagger is left alone, and the reason is the rule rather than an
# accident of the figures. If a trim ever becomes reachable this fails.
dunsfold = expect("DUNSFOLD", "hold")
assert dunsfold["reason"]["rule"] == "no-room-to-add", dunsfold["reason"]
assert dunsfold["render"] == "hold", dunsfold["render"]

# It is genuinely past the cap. A sample where the cap happened not to bind
# would demonstrate nothing.
_, decision = state_of("DUNSFOLD")
held_weight = next(i["observed"]["value"]
                   for i in decision["reason"]["evidence"]
                   if i["subject"].get("id") == "position.weight")
assert held_weight > 25.0, held_weight

# The two holdings that are held for different reasons say which. One is past
# the cap; the other would not be bought at today's price.
pelsall = expect("PELSALL", "hold")
assert pelsall["reason"]["rule"] == "would-not-buy-it-today", \
    pelsall["reason"]

# The growth exit is genuinely crossed and genuinely cannot be confirmed.
# That is the fact this sample exists to make visible, so it is asserted
# rather than described: the current reading fails, and no filing carries it.
haverty = expect("HAVERTY", "one-reading-past")
growth = [i for i in haverty["reason"]["evidence"]
          if i["subject"].get("id") == "eps_change_yoy"]
assert growth and growth[0]["outcome"] == "fail", growth
assert not any(i["subject"].get("at") for i in haverty["reason"]["evidence"])

# The turnaround is named from two readings and never from the growth rate,
# which is absent on exactly this shape of history.
kettleby = expect("KETTLEBY", "not-established-as-a-grower")
assert kettleby["reason"]["rule"] == "earnings-appeared-rather-than-grew"
cited = {i["subject"]["id"] for i in kettleby["reason"]["evidence"]}
assert cited == {"earnings_base_share_5y", "net_margin_base_share_5y"}, cited

# The stalwart passes the price question on one of its two rows and fails the
# other, which is the correction the whole growth floor rests on.
aldbury = expect("ALDBURY", "worth-buying")
price_rows = {i["subject"]["id"]: i["outcome"]
              for i in aldbury["reason"]["evidence"]
              if i.get("group") == "price"}
assert price_rows == {"dividend_adjusted_peg": "pass",
                      "pe_to_own_5y_median_pe": "fail"}, price_rows
assert next(g for g in aldbury["reason"]["groups"]
            if g["id"] == "price")["outcome"] == "pass"

# And a reported row that fails blocks nothing.
assert next(i["outcome"] for i in aldbury["reason"]["evidence"]
            if i["subject"]["id"] == "net_cash_to_market_cap") == "fail"

# The insider row is answered on exactly one company, by hand, because
# nothing computes it.
brindle = expect("BRINDLE", "worth-buying")
insider = next(i for i in brindle["reason"]["evidence"]
               if i["subject"]["id"] == "insider_net_buying_6m")
assert insider["observed"]["status"] == "known", insider

# The purchase nothing could be rebuilt for is marked as that and not as an
# override. They are different records and the learning loop depends on it.
casterton = portfolio.lots(by_ticker["CASTERTON"], "buy")[0]
assert casterton["override"] is None, casterton["override"]
assert casterton["unreconstructed"], casterton
assert casterton["snapshot"]["recollection"]["text"].startswith("No figures")

# Every holding was bought against a verdict this strategy actually reached,
# except the one nothing could be rebuilt for.
for ticker in ("DUNSFOLD", "ORRELL", "HAVERTY", "PELSALL"):
    lot = portfolio.lots(by_ticker[ticker], "buy")[0]
    assert lot["override"] is None, (ticker, lot["override"])
    assert lot["snapshot"]["decision"]["state"]["id"] == "worth-buying", \
        (ticker, lot["snapshot"]["decision"]["state"])

# The account has to be reachable or every size rule goes quiet.
held = [s for s in rows if portfolio.shares_held(s) > 0]
assert len(held) == 5, len(held)

write("sample-lynch.json", "lynch", FREE_CASH, TODAY, STORIES)
