"""Builds data.template/sample-buffett.json — the second demonstration journal.

Every company and every figure below is invented. Nothing here is a
recommendation, a model portfolio, or a real security; the tickers are made
up and so are the numbers.

Run from the project root:

    python tools/make_buffett_sample.py

It is its own journal, beside the Graham one, because a journal has exactly
one strategy. That is the point rather than an inconvenience: the two sit
side by side in the app and the same kind of company gets opposite verdicts
from them, which is the clearest way to show what committing to one strategy
actually means.

What it covers, and what it deliberately cannot
-----------------------------------------------
Ten of Buffett's twelve states. The two missing ones and why:

- **"No room for it"** needs the journal at capacity. This strategy runs ten
  places, so demonstrating it would mean shipping ten holdings. The state is
  covered by the test suite instead.

- **"The business has broken"** needs an exit level breached on *two
  consecutive filings* — four, for free cash flow — and the confirmation walk
  reads filing history. A journal whose figures are all entered by hand has no
  filing history at all, so an exit can be crossed and never confirmed. That
  is not a limitation of the sample: it is true of any real journal driven by
  hand, and it is worth knowing. TILNEY below sits in exactly that position
  and its note says so.

The exit that *can* fire here without any filing history is the one that is
not measured at all — a question the reader answered themselves. HALLAM
demonstrates it, and it is the case this whole strategy exists for: a
business that quietly stopped being wonderful while every number still looked
respectable.

The uncomfortable ones this sample makes a point of showing
-----------------------------------------------------------
- **A verdict that refuses to decide.** MARLOW passes all fifteen numeric
  tests and produces no verdict at all, because nobody has answered the three
  questions. That is meant to be slightly annoying. It is the strategy
  declining to launder an unexamined opinion into a buy signal.
- **A position that has grown to half the account and is left alone.**
  NORBRY. There is no trim in this strategy and no verdict that could ask for
  one, and a reader watching it climb needs to see that stated rather than
  inferred from silence.
- **A mind changed, on the record.** HALLAM's capital-allocation answer was a
  pass in 2021 and is a fail now. Both are kept; neither was edited.
"""

from sample_kit import (buy, expect, journal, securities, security,
                        state_of, write)

from engine import portfolio

# The day the stories were written against. Fixed rather than relative, so
# the sample reads the same on the day it is built and a year later.
TODAY = "2026-08-09"

FREE_CASH = 40_000.0

# A business this strategy would own. Every figure invented; the shape of the
# set is what matters — high returns on capital, little debt, steady margins,
# a share count going down rather than up.
WONDERFUL = {
    "roic_median_5y": 19.4, "total_debt_to_ebitda": 1.2,
    "owner_earnings_yield": 6.1, "interest_coverage": 15.0,
    "gross_margin_range_5y": 2.8, "fcf_margin_median_5y": 18.0,
    "cash_conversion_median_5y": 1.02, "diluted_share_count_change_5y": -5.0,
    "roe_median_5y": 24.0, "revenue_cagr_5y": 6.5,
    "ni_minus_revenue_cagr_spread_5y": 1.5,
    "goodwill_intangibles_to_assets": 9.0,
    "effective_tax_rate_median_5y": 22.0, "current_ratio": 1.1,
    "payout_to_fcf_median_5y": 58.0, "fcf_margin_ttm": 17.0,
    "diluted_share_count_change_3y": -3.0,
}


def like(**over):
    return {**WONDERFUL, **over}


journal("Sample — Buffett", "buffett", {"free-cash": FREE_CASH})


# -- the position that got large, and is left alone --------------------------
# The state a reader most needs to see from this strategy, and the one most
# likely to be mistaken for a bug. It has compounded to roughly half the
# account and nothing here asks for a trim, because there is no verdict in
# this strategy that could.

security(
    "NORBRY", "Norbury Ceramics", 88.00,
    like(roic_median_5y=23.8, roe_median_5y=29.0, owner_earnings_yield=4.2,
         revenue_cagr_5y=8.1, fcf_margin_median_5y=21.0, fcf_margin_ttm=20.4,
         diluted_share_count_change_5y=-8.0,
         diluted_share_count_change_3y=-4.5),
    on="2026-07-30",
    earlier=("2021-03-08",
             like(roic_median_5y=21.0, owner_earnings_yield=6.8,
                  roe_median_5y=25.0), 31.50),
    judged=[("2021-03-10", "moat_durability", "pass",
             "Kiln capacity in this grade of technical ceramic takes four "
             "years and a licence to build. The two firms that could have "
             "added it chose not to, twice."),
            ("2021-03-10", "management_integrity", "pass",
             "The 2019 letter opened with the recall and what it cost. "
             "Nobody buries a number they lead with."),
            ("2021-03-11", "capital_allocation", "pass",
             "Sixteen years of buying back stock below what the business is "
             "plainly worth, and no acquisition larger than a bolt-on.")],
    thesis=("A dull product with no substitute, made by two firms, one of "
            "which is this one. The price of admission is a kiln nobody "
            "wants to build.",
            "A third kiln gets built, or the licence regime changes."),
    notes=[("2024-06-02",
            "Up nearly threefold since I bought. The journal has stopped "
            "offering to add and has never once suggested trimming. Read "
            "the strategy page: that is the whole design, not an oversight."),
           ("2026-07-30",
            "Half the account now. This is the part I find hardest and the "
            "reason I wrote the rules down in advance.")])

buy("NORBRY", 900, 31.50, "2021-03-15")


# -- a holding this strategy would still buy ---------------------------------
# The add case. It sits well under the cap, still passes every entry test,
# and the three answers still stand.

security(
    "CRESSET", "Cresset Abrasives", 62.40,
    like(roic_median_5y=17.6, roe_median_5y=21.0, owner_earnings_yield=5.4,
         revenue_cagr_5y=5.2, gross_margin_range_5y=3.9),
    on="2026-07-28",
    earlier=("2023-09-05",
             like(roic_median_5y=17.9, owner_earnings_yield=7.2), 44.10),
    judged=[("2023-09-06", "moat_durability", "pass",
             "Bonded abrasives are specified into customers' own process "
             "documents. Changing supplier means requalifying the process, "
             "which nobody does to save four percent."),
            ("2023-09-06", "management_integrity", "pass",
             "Guidance missed twice in eleven years and both times the "
             "shortfall was explained before anyone asked."),
            ("2023-09-07", "capital_allocation", "pass",
             "Spare cash has gone into capacity at the plants earning the "
             "most, and into the dividend. No empire building.")],
    thesis=("Boring consumable, specified into the customer's process, "
            "reordered without a decision being made.",
            "Customers start dual-sourcing, or a synthetic substitute is "
            "qualified."),
    notes=[("2026-07-28",
            "Still cheap enough and still what I thought it was. The journal "
            "says there is room; whether this is the best home for the next "
            "pound is a question about the whole list, not about this.")])

buy("CRESSET", 300, 44.10, "2023-09-12")


# -- the business that quietly stopped being wonderful -----------------------
# The case this strategy exists for. Every number is still respectable — no
# exit level is crossed, nothing is breached, the balance sheet is fine — and
# the position is over, because the reader answered one of the three
# questions with a no and wrote down why.
#
# The earlier answer is kept. That is the whole value of the record: a pass
# in 2021 and a fail in 2026 with both reasons readable is the thing somebody
# learns from five years later.

security(
    "HALLAM", "Hallam Instruments", 41.00,
    like(roic_median_5y=16.2, roe_median_5y=19.5, owner_earnings_yield=5.9,
         goodwill_intangibles_to_assets=34.0, revenue_cagr_5y=4.4,
         diluted_share_count_change_5y=-1.0,
         diluted_share_count_change_3y=2.0),
    on="2026-07-26",
    earlier=("2021-06-14",
             like(roic_median_5y=18.4, owner_earnings_yield=6.6,
                  goodwill_intangibles_to_assets=11.0), 28.80),
    judged=[("2021-06-15", "moat_durability", "pass",
             "Calibration records live in their software. Ripping it out "
             "means revalidating a decade of instrument history."),
            ("2021-06-15", "management_integrity", "pass",
             "Straight about the 2020 shutdown and what it did to the "
             "order book."),
            ("2021-06-16", "capital_allocation", "pass",
             "Cash has gone back to owners or into the calibration software, "
             "which is the moat."),
            ("2026-07-26", "capital_allocation", "fail",
             "Four acquisitions in three years, each one further from the "
             "instruments, each one paid for partly in stock. Goodwill has "
             "gone from a ninth of the balance sheet to a third and the "
             "share count is rising for the first time. The returns still "
             "look fine because the acquired revenue is still new. I no "
             "longer think the chief executive is allocating capital; I "
             "think he is building something to run.")],
    thesis=("Instruments whose real product is the calibration record, which "
            "the customer cannot take with them.",
            "Acquisitions outside the instrument line, or a share count "
            "that starts rising."),
    notes=[("2026-07-26",
            "The falsifier I wrote in 2021 is the thing that happened. I am "
            "recording the answer rather than arguing with it.")])

buy("HALLAM", 250, 28.80, "2021-06-21")


# -- an exit level crossed on one reading, and no filings to confirm it ------
# The state that shows what a hand-kept journal cannot do. Borrowings are
# past the level that would end this position, and the confirmation rule
# counts filings — of which this journal has none, because no company here is
# linked to a real filer. The breach can be crossed and never confirmed.

security(
    "TILNEY", "Tilney Foods", 22.50,
    like(roic_median_5y=15.8, roe_median_5y=18.0, owner_earnings_yield=7.4,
         total_debt_to_ebitda=4.6, interest_coverage=5.1,
         fcf_margin_median_5y=11.0, fcf_margin_ttm=4.0,
         revenue_cagr_5y=4.2),
    on="2026-07-24",
    earlier=("2022-10-03",
             like(roic_median_5y=16.9, total_debt_to_ebitda=1.9,
                  owner_earnings_yield=6.9), 19.20),
    judged=[("2022-10-04", "moat_durability", "pass",
             "Two brands people ask for by name in a category nobody enters "
             "for the margins."),
            ("2022-10-04", "management_integrity", "pass",
             "Long record of saying what the input costs were doing before "
             "it showed up in the numbers."),
            ("2022-10-05", "capital_allocation", "pass",
             "Paid down the 2016 borrowings early rather than buying "
             "something.")],
    thesis=("Two brands with pricing power in a category with no glamour and "
            "therefore no new entrants.",
            "Borrowings taken on to buy growth rather than to bridge a "
            "cycle."),
    notes=[("2026-07-24",
            "Borrowings are past my exit level on this reading. The journal "
            "will not act on one reading and it cannot confirm this one at "
            "all, because I enter these figures by hand and there is no "
            "filing history for it to walk. That is on me, not on the tool."),
           ("2026-08-01",
            "Went and read the last two annual reports myself. The debt is "
            "the distribution acquisition. Watching.")])

buy("TILNEY", 400, 19.20, "2022-10-11")


# -- a holding nothing can be said about -------------------------------------
# Bought out of the reader's own records years later, with no figures ever
# entered. Not one exit test can run, so the strategy says it cannot tell
# rather than saying hold — and the purchase carries a recollection, which is
# never a thesis and never counted as one.

security("WEXTON", "Wexton Optical", 30.00, {}, on="2026-07-20",
         notes=[("2026-07-20",
                 "Entered from an old statement. I have put no figures in "
                 "for it, so the journal is honest about having nothing to "
                 "say. It is not telling me to hold — it is telling me it "
                 "cannot tell.")])

buy("WEXTON", 150, 26.40, "2023-02-14",
    recollection="No figures on record for this. What I remember is buying "
                 "it because the coatings patent had another eleven years "
                 "to run and nobody else could hit the tolerance.")


# -- a business this strategy would buy today --------------------------------

security(
    "LARKFD", "Larkfield Brewing", 54.20,
    like(roic_median_5y=20.6, roe_median_5y=26.0, owner_earnings_yield=5.6,
         revenue_cagr_5y=5.8, gross_margin_range_5y=2.2),
    on="2026-08-04",
    judged=[("2026-08-05", "moat_durability", "pass",
             "A regional beer nobody outside the region has heard of, with "
             "eighty years of shelf space that a new entrant would have to "
             "buy rather than earn."),
            ("2026-08-05", "management_integrity", "pass",
             "Family-run, and the one bad year in the last decade was "
             "explained in more detail than the good ones."),
            ("2026-08-06", "capital_allocation", "pass",
             "No acquisitions at all. Spare cash buys back stock or sits "
             "there, which is the right answer more often than people "
             "think.")],
    notes=[("2026-08-06",
            "Answered all three before looking at what the journal would "
            "say. That order matters — it is much harder to write an honest "
            "moat assessment once you know it is the last thing standing "
            "between you and a buy signal.")])


# -- every number passes and there is still no verdict -----------------------
# The headline case. Fifteen tests in order and nothing to show for it,
# because the three things that decide this are questions nobody has
# answered. Unanswered is not a fail and is not held against the company; it
# simply is not an answer.

security(
    "MARLOW", "Marlowe Precision", 71.80,
    like(roic_median_5y=18.1, roe_median_5y=22.5, owner_earnings_yield=5.2,
         revenue_cagr_5y=7.4),
    on="2026-08-05",
    notes=[("2026-08-05",
            "Numbers all clear and the journal will not give me a verdict. "
            "It wants me to say what stops a competitor, whether I trust "
            "the people, and what they have done with spare cash — in "
            "writing. I have not done the reading yet, so it is right.")])


# -- the reader looked, and said no ------------------------------------------

security(
    "ASHDWN", "Ashdown Group", 33.60,
    like(roic_median_5y=17.2, roe_median_5y=20.1, owner_earnings_yield=6.4,
         revenue_cagr_5y=9.2, gross_margin_range_5y=4.4),
    on="2026-08-03",
    judged=[("2026-08-04", "moat_durability", "fail",
             "The returns are real and I cannot find the reason for them. "
             "Two competitors have the same equipment, the same customers "
             "and no switching cost between them. I think this is three "
             "good years rather than a moat, and I would rather be wrong "
             "and out than right and lucky."),
            ("2026-08-04", "management_integrity", "pass",
             "No complaint. They have been straight."),
            ("2026-08-04", "capital_allocation", "pass",
             "Reinvested at high rates, no acquisitions.")],
    notes=[("2026-08-04",
            "Everything the tool can measure says yes and the one thing "
            "only I can judge says no. This is the whole reason the "
            "question exists.")])


# -- an ordinary business, which is not the same as a bad one ----------------

security(
    "PENRYN", "Penryn Logistics", 18.90,
    like(roic_median_5y=7.1, roe_median_5y=9.4, total_debt_to_ebitda=2.9,
         interest_coverage=5.2, fcf_margin_median_5y=4.0,
         fcf_margin_ttm=3.6, gross_margin_range_5y=7.8,
         owner_earnings_yield=8.8, revenue_cagr_5y=3.1),
    on="2026-08-02",
    notes=[("2026-08-02",
            "Cheaper than anything else on this list and this strategy does "
            "not care. It is looking for a business that earns a lot on the "
            "money inside it, and this one earns seven percent on capital "
            "that costs about nine. The other sample journal in this app "
            "would look at the same company quite differently, which is why "
            "they are two journals.")])


# -- not enough to go on -----------------------------------------------------

security(
    "BRAMBR", "Bramber Analytics", 46.70,
    {k: v for k, v in like(roe_median_5y=21.0, revenue_cagr_5y=11.0).items()
     if k not in ("roic_median_5y", "owner_earnings_yield",
                  "gross_margin_range_5y")},
    on="2026-08-01",
    notes=[("2026-08-01",
            "Three figures missing, and two of them are tests this strategy "
            "will not bend. It says it cannot tell rather than guessing, "
            "which is the only honest answer — a missing number is not a "
            "pass and it is not a failure.")])


# ===========================================================================
# What each of them exists to show. Asserted against the real evaluator, so
# the sample cannot ship claiming a story it no longer tells.
# ===========================================================================

STORIES = {
    "NORBRY": "hold",
    "CRESSET": "room-for-more",
    "HALLAM": "stopped-being-wonderful",
    "TILNEY": "one-reading-past",
    "WEXTON": "cannot-watch",
    "LARKFD": "wonderful-and-priced",
    "MARLOW": "judgement-owed",
    "ASHDWN": "you-marked-it-down",
    "PENRYN": "not-wonderful-enough",
    "BRAMBR": "cannot-screen",
}

for ticker, want in STORIES.items():
    expect(ticker, want)

rows = securities()
by_ticker = {s["ticker"]: s for s in rows}

# The large holding is left alone, and the reason is the rule rather than an
# accident of the figures. If a trim ever becomes reachable this fails.
norbry = expect("NORBRY", "hold")
assert norbry["reason"]["rule"] == "no-room-to-add", norbry["reason"]
assert norbry["render"] == "hold", norbry["render"]

# It is genuinely large. A sample where the cap happened not to bind would
# demonstrate nothing.
weight = next(h for h in by_ticker["NORBRY"].get("lots", []) if h)
del weight
_, decision = state_of("NORBRY")
held_weight = next(i["observed"]["value"] for i in decision["reason"]["evidence"]
                   if i["subject"].get("id") == "position.weight")
assert held_weight > 40.0, held_weight

# The blocked verdict names its questions AND cites them, because the way to
# answer one is built from what the decision cited. A block that named them
# only in prose would be a dead end.
marlow = expect("MARLOW", "judgement-owed")
assert marlow["render"] == "blocked"
cited = [i["subject"]["id"] for i in marlow["reason"]["evidence"]
         if i["subject"].get("kind") == "judgement"]
assert cited == ["moat_durability", "management_integrity",
                 "capital_allocation"], cited
assert marlow["payload"]["needs"], marlow["payload"]

# A company the rules already rejected is never asked to be assessed.
penryn = expect("PENRYN", "not-wonderful-enough")
assert not [i for i in penryn["reason"]["evidence"]
            if i["subject"].get("kind") == "judgement"]

# The mind that changed is on the record twice, and neither entry was edited.
hallam = by_ticker["HALLAM"]
capital = [j for j in hallam["judgements"]
           if j["id"] == "capital_allocation"]
assert len(capital) == 2, capital
assert [j["mark"] for j in capital] == ["pass", "fail"], capital

# The purchase nothing could be rebuilt for is marked as that and not as an
# override. They are different records and the learning loop depends on it.
wexton = portfolio.lots(by_ticker["WEXTON"], "buy")[0]
assert wexton["override"] is None, wexton["override"]
assert wexton["unreconstructed"], wexton
assert wexton["snapshot"]["recollection"]["text"].startswith("No figures")

# Every holding was bought against a verdict this strategy actually reached,
# except the one nothing could be rebuilt for. Assessing before buying is
# what makes that possible, and it is the order this sample is built in.
for ticker in ("NORBRY", "CRESSET", "HALLAM", "TILNEY"):
    lot = portfolio.lots(by_ticker[ticker], "buy")[0]
    assert lot["override"] is None, (ticker, lot["override"])
    assert lot["snapshot"]["decision"]["state"]["id"] == \
        "wonderful-and-priced", (ticker, lot["snapshot"]["decision"]["state"])

# The account has to be reachable or every size rule goes quiet.
held = [s for s in rows if portfolio.shares_held(s) > 0]
assert len(held) == 5, len(held)

write("sample-buffett.json", "buffett", FREE_CASH, TODAY, STORIES)
