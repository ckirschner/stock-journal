"""Lynch — a company growing faster than its price says it is, sold when the
growth stops or the price catches up.

The third of three, and the first that is neither of the other two. Graham
buys an ordinary business cheap against its assets and sells when the gap
closes. Buffett buys an extraordinary business at a sane price and sells only
when the business breaks. This buys an ordinary-to-good business that is
*growing*, at a price that has not yet paid for the growth, and it sells for
either of two reasons — the growth stopped, or the price ran past it.

Six things follow, and they are the shape of this file.

**Entry and exit do not share a measure, and that is the most consequential
thing here.** Every strategy in this program before this one bought and sold
on the same figure. Entry wants durability, which argues for a long window;
exit wants timeliness, which argues for a short one. One measure cannot serve
both, and using one guarantees you either buy on noise or sell late — this
profile's source chose late. So the entry test is a five-year rate measured
between three-year averages at each end, and the exit is the trailing twelve
months against the twelve before it. A company that stops growing says so
here about two quarters afterwards rather than several years afterwards,
which is what Lynch actually acted on.

**A base too small to compound from is routed, not greyed.** Where the
earnings at the start of the window were almost nothing and the margin was
almost nothing, the earnings did not grow — they appeared. That is a margin
recovery or a turnaround, which Lynch treated as a different category with
different rules, and this strategy says so in as many words rather than
reporting that it cannot decide. See `not-established-as-a-grower`, and the
two measures under `WAS_THERE_A_BUSINESS` that reach it.

**It buys stalwarts as well as fast growers, and that is a change from the
source.** The report set the earnings growth floor at 15%. Lynch sorted every
company into one of six categories and held stalwarts at 10–12% deliberately,
as ballast rather than as rejects, so a 15% floor can only ever buy one of the
six. The floor is 10% here, the price test that does the work is the PEG, and
the dividend-adjusted PEG a stalwart is actually judged on has come up out of
the reported rows into the tests that decide. `min-revenue-growth` moved with
it and says why.

**It sells on price, and Buffett does not.** A company whose multiple has run
to twice its growth rate has borrowed its future return, and this closes the
position. That is a real disagreement rather than a difference of tuning:
Buffett's strategy leaves every valuation exit blank on purpose, this one
fills two in, and no number in between is one either side would sign.

**There is no clock and no trim.** Nothing here closes a position for having
been owned a long time — the exits are things the business or the price does,
not things the calendar does — and no state in this file reduces a holding.
A position that has grown large by rising is what the method is trying to
produce. The size rules bind on the way in and never on the way out.

**It does not evaluate lenders, insurers or property companies.** See
DECLINES. Lynch owned a great many thrifts and wrote explicit criteria for
them, so this refusal is a gap in the host rather than a boundary of the
method — and the criteria he used for them are not the ones in this file.

Sources, and which is which, because a reader auditing a number later has to
be able to tell. Every value carries its own `source` saying so, which is
where to look rather than here.

Fourteen of the thresholds below are the expert report's, at the level it
states.

Five are the second expert review's, and each of those says in its own words
what the level was, what it is, and what the argument was. They are the most
interesting numbers here to argue with, because they are the ones where two
sources disagreed and this file picked.

Two come from Lynch's own documented practice, because neither source was
asked how much to buy — the same gap Graham and Buffett had, and a third
different answer to it.

The rest are nobody's but this file's author's, and they are the ones to look
at hardest: how many of a group of near-duplicate tests must pass, the
revenue growth floor that had to move when the earnings floor did, and the
two levels that say what a turnaround looks like.

**One thing a reader should know about the provenance of every report number
here.** The expert report itself is not in this repository. Its levels were
taken from `dev_reference_docs/legacy-profiles/lynch.yaml`, which states in
its own header that its values are written exactly as the report states them.
So that chain is one link longer than a direct reading, and it is a
transcription rather than the document. The review IS in this repository, at
`dev_reference_docs/ledger-default-profiles-addendum.md`, so the five values
that follow it can be checked against the thing itself.

Nothing here computes a comparison. Every test is put to `contract.test` and
then cited as the same item, so what a rule acted on and what the reader sees
are one answer rather than two that agree until they do not.
"""

from engine import contract

# ---------------------------------------------------------------------------
# The tests, as data.
#
# Each row is (bank measure, comparator, the declared value holding the
# limit). The strategy names the measure and the direction; the host reads
# the number out of the setting and answers with the figure, its unit and
# whether the comparison was met. Nothing below restates a number.
# ---------------------------------------------------------------------------

# Was there a business at the base of the growth window?
#
# Reported, never blocking, and acted on by a rule the host cannot express:
# this strategy calls a company a turnaround when BOTH of these fail, and a
# group can demand that all of its rows pass or that some do — never that all
# of them fail.
#
# Both, and never one, and that is measured rather than assumed. The earnings
# multiple on its own fires on a company whose sales multiplied about as fast
# as its profits, which is growth of the most straightforward kind. The margin
# share on its own is a margin-expansion test, and an ordinary scaling
# business expanding from eight percent to twelve would trip it. Together they
# say something neither says alone: there was almost no profit then, and there
# was almost no profit *per dollar of sales* then, so what has happened since
# is a recovery rather than a company selling more.
#
# The metric bank refuses a five-year growth rate on the same two quantities
# at the same two levels, which is why these usually come with the growth rate
# absent beside them. The two decisions are not one decision said twice: the
# host is declining to serve a number it cannot stand behind, and this is a
# strategy saying what kind of company it thinks it is looking at. Move either
# level here and they part company deliberately, on the rule-change record.
WAS_THERE_A_BUSINESS = (
    ("earnings_base_share_5y", "at_least", "min-earnings-base-share"),
    ("net_margin_base_share_5y", "at_least", "min-margin-base-share"),
)

# Knockout. One failure kills the buy regardless of everything else.
#
# Four tests in five rows, and the choice of which four is the whole thesis.
# The PEG says the price has not yet paid for the growth. The band says the
# growth is fast enough to be worth buying and not so fast that it cannot
# last. Borrowing says a growth stumble will not take the company with it.
# And the spread between earnings growth and sales growth says the growth is
# the business rather than the buyback.
#
# The spread is the row that moved, and it moved up here from the tier below
# for a reason worth reading. The PEG and the growth band are both knockouts
# and both take the same growth number as an input, so a distorted base breaks
# two of the four required tests in the same direction at the same moment.
# The spread is the only thing in this file that catches that, and a tier
# where six of eight is enough cannot be relied on to enforce it.
#
# The band is two rows because a band is two comparisons. There is no
# `between` in the host's comparison vocabulary and this strategy does not
# want one: two rows say which end was missed, and one row could only say that
# something was.
REQUIRED = (
    ("peg_trailing", "at_most", "max-peg"),
    ("eps_cagr_5y", "at_least", "min-eps-growth"),
    ("eps_cagr_5y", "at_most", "max-eps-growth"),
    ("debt_to_equity", "at_most", "max-debt-to-equity"),
    ("eps_minus_revenue_cagr_spread_5y", "at_most", "max-growth-spread"),
)

# ---------------------------------------------------------------------------
# The rest of the entry tests, gathered by WHAT THEY MEASURE.
#
# The report states these as eight tests of which six must pass. A count
# assumes its members are independent evidence, and these are nothing of the
# kind: three of them divide the same current P/E by three different things,
# and two of them ask whether working capital is running ahead of sales. Under
# a quota a company clears six of eight by being cheap measured three ways
# while nobody looks at whether the growth is real.
#
# So the demand is coverage rather than a total. Each group is one question,
# every group has to be satisfied, and no group's passes can be spent on
# another's.
#
# Within a group the rule follows from whether the members are substitutes:
#
#   all       the members measure genuinely different things, so passing one
#             says little about the other and both are owed.
#   at_least  the members are near-readings of one another, or one of them is
#             absent for whole industries. Requiring every one double-counts
#             or excludes; how many is a declared value, because loosening it
#             is a real loosening and belongs on the rule-change record.
# ---------------------------------------------------------------------------

# What you are paying for the growth.
#
# The PEG is already a knockout, so this is the corroboration rather than the
# question. Both rows here divide the same trailing P/E — one by the growth
# rate plus the yield, one by what the market has usually paid for this
# company — so a single distorted P/E moves both readings the same way at the
# same moment, which is what makes one of them the coverage statement.
#
# It is also the direct answer to the review's warning that a PEG under 1.0
# alongside a P/E under its own five-year median is a heavy double gate for a
# growth profile, which will reject good companies in any period when the
# whole category re-rates. In such a period the median test fails for
# everybody and the dividend-adjusted PEG can still pass, which is the reading
# a stalwart should have been judged on in the first place.
#
# One instruction carried into this profile from the source document has no
# target here, and it is worth saying so rather than leaving somebody to look
# for the missing setting. Every absolute price level in this program is
# supposed to read from one declared rate rather than sitting frozen — which
# is why the Graham bundle declares a bond yield and works its price ceiling
# out from it. **This strategy has no absolute price level.** All three of
# its price tests are ratios against something the company itself supplies:
# its growth rate, its growth rate plus its yield, and what the market has
# usually paid for it. A multiple of forty is cheap against forty percent
# growth and dear against ten, and that is true in any rate environment. So
# there is no number here for a rate to move, and adding one would be adding
# a setting that changed nothing.
PRICE = (
    ("dividend_adjusted_peg", "at_most", "max-dividend-adjusted-peg"),
    ("pe_to_own_5y_median_pe", "at_most", "max-pe-to-own-median"),
)

# Whether the top line is still growing. One row, over three years rather than
# five, because it is the faster-moving signal and the question is whether
# sales have decelerated recently — which a five-year window would smooth away.
GROWING = (
    ("revenue_cagr_3y", "at_least", "min-revenue-growth"),
)

# Whether the growth is real or manufactured.
#
# Three readings of one question: is the reported growth being pushed into the
# warehouse, booked and not collected, or bought with discounts. They are
# correlated by construction — a company discounting to move product shows it
# in the margin and in the inventory at once — and two of the three is the
# coverage statement rather than a relaxation.
#
# Two rather than three for a second reason that matters more in practice.
# Software, services and most asset-light businesses hold no inventory, so
# that row is absent for them permanently and by nature. Demanding all three
# would leave every such company undecided forever — an unreadable row is not
# a passing one, so the group would never resolve and no purchase could stand
# beside it. Lynch owned plenty of businesses with nothing in a warehouse.
REAL = (
    ("inventory_minus_revenue_growth_yoy", "at_most", "max-inventory-spread"),
    ("receivables_minus_revenue_growth_yoy", "at_most",
     "max-receivables-spread"),
    ("gross_margin_change_3y", "at_least", "min-gross-margin-change"),
)

# Whether it can survive a stumble. Two genuinely different questions — can it
# pay the interest, and does it fund itself — so both are owed.
SURVIVES = (
    ("interest_coverage", "at_least", "min-interest-coverage"),
    ("fcf_ttm", "above", "min-free-cash-flow"),
)

# Never block. Reported so the reader can see them and stop there.
#
# Insider buying is the row worth explaining. Nothing in this program computes
# it — it lives in Form 4 ownership XML, which is a separate ingestion path
# this host does not read — so it is absent until somebody types it in, and
# the citation is what puts a place to type it on the page. It is here rather
# than dropped because it is the one signal in this whole file that moves in
# days rather than quarters, it is cheap for a person to look up, and Lynch's
# reasoning about it is worth a reader meeting: insiders sell for dozens of
# reasons and buy for one.
#
# Institutional ownership used to sit here and does not any more. See the
# changelog; the short version is that index funds now hold a fifth to a
# quarter of the US market, so the number no longer measures what its own
# rationale claims it measures.
BONUS = (
    ("net_cash_to_market_cap", "at_least", "min-net-cash"),
    ("insider_net_buying_6m", "above", "min-insider-buying"),
)

# The exits. Written as what the holding must KEEP being true, not as the
# condition that ends it, so a healthy holding reads as passes and a breach is
# the one row that is not.
#
# Nothing here says how much evidence a breach needs. That is a property of
# the measure — of how far one filing can move a trailing twelve months
# against how far it can move a balance-sheet date — and the host derives it
# from what the metric bank declares. See contract.ESTIMATORS.
#
# Three departures from the report, and all three are set out in the changelog.
# The growth exit is on the trailing twelve months rather than on the
# five-year rate. The cash exit takes two filings rather than four quarters.
# And the report's second valuation exit — the P/E against its own five-year
# median at 1.75 — is not here at all: it stays an entry test, because a
# strategy with one valuation exit that is Lynch's own does not need a second
# that is not, and doubling the ways a re-rating can force a sale costs more
# on the exit side than on the entry side.
EXITS = (
    ("eps_change_yoy", "at_least", "exit-eps-growth"),
    ("peg_trailing", "at_most", "exit-peg"),
    ("debt_to_equity", "at_most", "exit-debt-to-equity"),
    ("interest_coverage", "at_least", "exit-interest-coverage"),
    ("fcf_ttm", "at_least", "exit-free-cash-flow"),
    ("inventory_minus_revenue_growth_yoy", "at_most",
     "exit-inventory-spread"),
    ("receivables_minus_revenue_growth_yoy", "at_most",
     "exit-receivables-spread"),
)

# Which exit is which, by position in EXITS. The three closing states this
# strategy can reach are these three slices, and the split is the reason a
# reader is told *why* they are out rather than only that they are.
GROWTH_EXIT = 0            # the growth stopped — the exit this is built on
PRICE_EXIT = 1             # the multiple ran past the growth
STORY_EXITS = (2, 3, 4, 5, 6)   # borrowing, cover, cash, and the two warnings

# The other half of the growth exit: sales over the same two windows.
#
# Earnings falling while sales keep growing is a margin event, not a growth
# event, and this strategy does not sell a company for having a bad year on
# costs. So the requirement holds while EITHER earnings or sales are still
# growing, and only both failing ends it. Absence on either side leaves it
# unreadable rather than clear, because a comparison nobody could make has not
# shown that nothing happened.
#
# Tested rather than confirmed, deliberately. It is a corroborating read of
# the current quarter and not a second exit: the persistence this exit asks
# for is asked of the earnings, which is the measure the rule is about.
REVENUE_CORROBORATION = ("revenue_change_yoy", "at_least",
                         "exit-revenue-growth")

# How far the growth rate has moved since the day this holding began.
#
# Cited as an observation and never as a test. It decides nothing — the exit
# above is a statement about the rate now, which is the whole point of it not
# being a statement about the distance from where it was — but it is the
# single most useful number a holder of a growth company can see, and a screen
# that reported the rate without reporting how far it had fallen would be
# leaving the reader to remember what they bought.
#
# As a distance and not a proportion: a rate that went from 24% to 14% has
# fallen ten points, and ten points is what the sentence "it is not the
# company you bought" means for a growth rate. The proportional form is the
# right one for a return on capital, where a third off 45% and a third off 15%
# are different events; two growth rates ten points apart are the same event
# wherever they started.
GROWTH_DRIFT = {"measure": "eps_cagr_5y", "since": "first-purchase",
                "change": "distance"}


# ---------------------------------------------------------------------------
# The headings the evidence is gathered under, and what each demands.
#
# The grouping IS the rollup. The host counts every group from the rows it
# resolved rather than from a tally this file kept, and it refuses a state
# whose render is `commit` when any group that stated a requirement did not
# come out passed. So there is no path through this file that buys something
# with a question unanswered, whatever the ladder below does.
# ---------------------------------------------------------------------------

BASE_GROUP = {"id": "base",
              "name": "What it looked like when the growth started",
              "requires": "noted"}

KNOCKOUTS = {"id": "knockouts", "name": "Tests this strategy will not bend",
             "requires": "all"}

PRICE_GROUP = {"id": "price", "name": "What you are paying for the growth",
               "requires": "at_least",
               "threshold_from": "price-tests-required"}
GROWING_GROUP = {"id": "growing", "name": "Whether the top line is growing",
                 "requires": "all"}
REAL_GROUP = {"id": "real",
              "name": "Whether the growth is real or manufactured",
              "requires": "at_least",
              "threshold_from": "quality-tests-required"}
SURVIVES_GROUP = {"id": "survives",
                  "name": "Whether it survives a stumble",
                  "requires": "all"}

# In the order they are asked, cited and drawn. Price first because this
# strategy is about paying the right price for growth and the PEG is the
# knockout it turns on; whether the growth is real next, because it is the
# question the numbers most often get wrong; solvency last because it is what
# ends positions rather than what starts them.
DIMENSIONS = (
    (PRICE_GROUP, PRICE),
    (GROWING_GROUP, GROWING),
    (REAL_GROUP, REAL),
    (SURVIVES_GROUP, SURVIVES),
)

BONUS_GROUP = {"id": "bonus", "name": "Reported, never blocking",
               "requires": "noted"}

SIZING_GROUP = {"id": "sizing", "name": "Room in the list, and how much",
                "requires": "all"}

# The exits demand nothing of a single reading — that is the confirmation
# rule, and it counts filings, which the host cannot express as a group
# requirement. So the group is `noted`: the host reports how each came out and
# this strategy decides what a run of them means.
DECAY_GROUP = {"id": "decay", "name": "What would end this position",
               "requires": "noted"}

TIME_GROUP = {"id": "time", "name": "How long you have held it, and how far "
                                    "it has moved",
              "requires": "noted"}


# ---------------------------------------------------------------------------
# Where the numbers came from.
# ---------------------------------------------------------------------------

_REPORT = ("the expert report commissioned for this strategy, by way of the "
           "transcription of it kept at "
           "dev_reference_docs/legacy-profiles/lynch.yaml — the report itself "
           "is not in this repository, so that file is what a reader can "
           "check this against")

REPORT = {"name": _REPORT, "reasoning": True}
REPORT_LEVEL_ONLY = {"name": _REPORT, "reasoning": False}

# The second expert review of the profile document, which disputes the first
# report in every profile. Where a level below cites this rather than the
# report, the report's own number was overruled and the value says why in its
# own `explain`.
REVIEW = {
    "name": "the second expert review of the profile document, held at "
            "dev_reference_docs/ledger-default-profiles-addendum.md, which "
            "disputes this level in the report it reviewed",
    "reasoning": True}

# Nobody's but this file's. These are the numbers here most worth arguing
# with, and the attribution is what makes that visible.
AUTHOR = {
    "name": "this strategy's own author. Neither the expert report nor the "
            "review that corrected it states this number, and none is "
            "claimed for it",
    "reasoning": True}

LYNCH_PRACTICE = {
    "name": "Lynch's own documented advice to individual investors in *One Up "
            "on Wall Street*, where he sets out how many names a small "
            "portfolio should hold. The expert report was scoped to selection "
            "and to exits and says nothing whatever about how much to buy, so "
            "its silence here is a gap in the source rather than a decision "
            "it made",
    "reasoning": True}


# ---------------------------------------------------------------------------
# The kinds of company this strategy does not evaluate, and why the refusal is
# temporary here in a way Graham's is not.
#
# Lynch owned a great many savings institutions and wrote explicit criteria
# for them: equity against assets as the safety test, non-performing assets as
# the quality test, and price against book as the price test. So there is a
# Lynch branch for lenders and it is well founded — what is missing is every
# measure it would need, none of which exists in this host. Until they do this
# refuses, because the alternative on the tests that decide a purchase here is
# not a rougher answer but a confident wrong one.
#
# What is deliberately not refused: asset managers, exchanges, brokers and
# estate agents. Those are ordinary fee businesses, several of them grow
# exactly the way this strategy is looking for, and refusing everything
# financial-sounding would refuse some of the best candidates on the list.
DECLINES = [
    {"class": "depository-lending",
     "because": "Almost every test here is a category error on a lender. "
                "Borrowing against equity counts deposits as debt, when "
                "deposits are the raw material the business exists to take "
                "in — a healthy bank reads as ruinously leveraged. Interest "
                "cover divides operating profit by interest expense, and for "
                "a lender interest is the cost of the product rather than "
                "the cost of the balance sheet, so the ratio compares a "
                "number with part of itself. Free cash flow is the dangerous "
                "one: a lender's cash from operations moves with the "
                "period's change in loans and deposits, so a bank that is "
                "shrinking generates the most of it — a large confident "
                "number pointing the wrong way. And inventory and "
                "receivables mean something else entirely here, where the "
                "receivables line is the loan book and loans outrunning "
                "deposits is loosening underwriting rather than channel "
                "stuffing. Lynch himself owned many thrifts and wrote "
                "criteria for them; those criteria are not these, and the "
                "measures they need are not in this program yet."},
    {"class": "insurance",
     "because": "Premiums arrive before claims are paid, so cash from "
                "operations rises with the growth of money the insurer is "
                "holding rather than money it has earned — which lands "
                "directly on the free cash flow test here. Underwriting and "
                "investing are two businesses in one set of accounts and "
                "nothing in this program separates them, so an earnings "
                "growth rate reads the investment portfolio and the reserve "
                "releases as much as the business. There is no inventory and "
                "no gross margin to read at all."},
    {"class": "real-estate",
     "because": "Depreciation on buildings is an accounting convention "
                "rather than a cost being incurred, so reported profit "
                "understates by design — and every test here that decides a "
                "purchase is built on earnings or on their growth. The "
                "industry's own figure adds the charge back; this program "
                "does not compute it. Borrowing is structural here too, so "
                "the debt knockout would refuse every property company for a "
                "reason that has nothing to do with the particular one in "
                "front of you."},
]


# What the METHOD asks for or admits to that this program does not do.
#
# Separate from DECLINES, which is about a kind of company these measures
# cannot read. This is about the method itself, and it is here because the
# alternative is silence — and silence on these particular points is not
# neutral, it is a set of promises nobody made.
LIMITS = [
    {"title": "It is a portfolio method, and this is one security",
     "body": "Everything in this strategy was worked out by somebody running "
             "a portfolio, and it carries an expected rate of losers that "
             "the good outcomes are meant to pay for. Lynch was unusually "
             "explicit about it: his own account of the arithmetic is that "
             "if you hold five companies and one of them multiplies ten "
             "times while four go nowhere, you have still tripled your "
             "money. That is a statement about a set of positions, and it "
             "says in passing that four fifths of them disappointed.\n\n"
             "**A verdict on this page is about one security, and no method "
             "here can tell you that one will work.** What a buy verdict "
             "says is that this security meets the standard you set while "
             "you were calm. It does not say the standard will be met by "
             "the outcome.\n\n"
             "It matters more here than on a strategy that holds for "
             "decades, because the whole shape of this method is a few very "
             "large winners paying for a majority that did not work. Judging "
             "it by whichever position you happen to be looking at will "
             "almost always be judging it by one that did not."},

    {"title": "The growth rate it buys on is backward-looking, and his was "
              "not",
     "body": "Lynch's price test compares what a company costs against how "
             "fast it is *expected* to grow. Expectations come from analyst "
             "estimates, and this program has none — it reads filings and "
             "prices and nothing else. So every growth rate here is the "
             "record rather than the forecast.\n\n"
             "That changes what the test catches. A company whose growth has "
             "just peaked and is about to roll over looks its best on a "
             "trailing rate at exactly the moment it is worst, and that is "
             "the situation forward estimates existed to avoid. It is the "
             "largest single compromise in this strategy.\n\n"
             "Two things partly cover it, and it is worth knowing which. "
             "The inventory and receivables tests are early warnings of that "
             "same failure showing up in the balance sheet a quarter or two "
             "before the income statement, which is why they decide "
             "purchases here rather than being reported beside them. And the "
             "exit is on the current rate rather than the five-year one, so "
             "the position closes about two quarters after the growth stops "
             "rather than several years after.\n\n"
             "The case neither covers is the cyclical at the top of its "
             "cycle. Its trailing growth is enormous, its multiple looks "
             "modest against it, and both are about to reverse. Nothing in a "
             "filing distinguishes that from a company that is simply "
             "growing, and this strategy does not pretend otherwise."},

    {"title": "He sorted companies into six kinds; this is one rule set",
     "body": "Lynch's method starts by deciding what kind of company he was "
             "looking at — a slow grower, a stalwart, a fast grower, a "
             "cyclical, a turnaround, or an asset play — because almost "
             "every rule after that is conditional on the answer. What you "
             "want from a cyclical is not what you want from a stalwart, and "
             "the same number means opposite things to the two.\n\n"
             "This is one rule set applied to whatever it is shown, with one "
             "exception. Where the record says the earnings appeared rather "
             "than grew, it says so and stops, because that is a turnaround "
             "and none of these tests describe one. Everything else — "
             "stalwart, fast grower, cyclical — is judged on the same list.\n\n"
             "Two of the three are handled honestly by that list. The "
             "earnings growth floor is low enough to admit a stalwart, and "
             "the dividend-adjusted price test is the one a stalwart should "
             "be judged on, so a company growing at eleven percent and "
             "paying a yield is neither excluded nor measured with the wrong "
             "instrument.\n\n"
             "The cyclical is the one that is not handled, and it is stated "
             "here rather than guessed at. Telling a cyclical from a growth "
             "company needs its sensitivity to a cycle, which needs a cycle "
             "to measure it against — and this program has company filings "
             "and share prices, not an economy. Margin volatility on its own "
             "does not separate a cyclical from a company that had a bad "
             "year. A route built on that would put a confident label on the "
             "one category where being wrong costs the most."},

    {"title": "Every exit here is a measurement, so a hand-kept journal "
              "never sells",
     "body": "The other two strategies in this program can each close a "
             "position without a filing. Graham's has a clock, which runs "
             "on the calendar. Buffett's turns on three questions the "
             "reader answers themselves, and an answer is an answer the day "
             "it is written.\n\n"
             "**Every exit here is a number read out of an accounting "
             "record**, and this program will not act on one reading of a "
             "number. It waits for the next filing to say the same thing — "
             "which is right, because one heavy quarter can push a measure "
             "over a line without anything having changed.\n\n"
             "The consequence is easy to miss and worth stating plainly. "
             "Confirming a breach counts *filings*. A company this journal "
             "has never fetched — one the SEC does not cover, one you track "
             "by typing the figures in yourself — has no filings on record, "
             "so the count is always nought and **an exit can be crossed "
             "and never confirmed, however bad the number gets.** The "
             "verdict will say a level has been crossed and that one "
             "reading is not enough, and it will go on saying it.\n\n"
             "Nothing about that is broken and nothing is being hidden: "
             "nobody observed a second reading, so nothing is confirmed. "
             "But a reader who assumed the sell discipline was watching on "
             "their behalf would be wrong, and the sell discipline is most "
             "of what this method is. Fetching filings for a company is "
             "what turns it on."},

    {"title": "The research this rests on does not happen at a screen",
     "body": "Lynch's stated edge was noticing things before the market "
             "did — a product his family kept buying, a shop that was always "
             "full, a business he understood well enough to explain in two "
             "minutes. The numbers came afterwards, to check the idea and to "
             "price it.\n\n"
             "This strategy is the second half of that and none of the "
             "first. It can tell you whether a company you have thought of "
             "is growing, whether the growth looks real, and whether the "
             "price has got ahead of it. It cannot tell you why the company "
             "is worth thinking about, and a list of companies that pass it "
             "is not a list of companies to buy.\n\n"
             "That is worth being blunt about because the tests here are "
             "less demanding than the other strategies in this program, by "
             "design — most companies fail Graham's list and Buffett's, and "
             "rather more will pass this one. The filter being lighter does "
             "not mean the bar is lower. It means the rest of the bar is "
             "yours."},
]


STRATEGY = {
    "id": "lynch",
    "name": "Lynch",
    "summary": "Buys a company that is growing, at a price that has not paid "
               "for the growth yet. Sells when the growth stops or when the "
               "price runs past it — and never because time has passed.",
    "version": 3,
    "contract": 8,
    "declines": DECLINES,
    "limits": LIMITS,
    "changelog": {
    3: "NO LEVEL MOVED AND NO LOGIC CHANGED — TWO SENTENCES MISSTATED THE "
       "ARITHMETIC. A question about the company that cannot reach its bar "
       "even if every unreadable row under it passed was described as \"not "
       "answered\", on the candidate verdict and on the would-not-buy-it-"
       "today holding verdict. Unanswered is a different verdict in this "
       "strategy — it is what cannot-screen and screen-unreadable mean. "
       "Both sentences now say what the rollup under them already said: "
       "the question was answered, and the answer is no.\n\n"
       "Four states also declare the contract's new one-line `consequence` "
       "for the list row. One reading past the line: waiting on the next "
       "readings, nothing owed — and its description now says readings "
       "rather than filings, which version 2 made true when the price exit "
       "moved to trading days. Not enough to go on: undecided, not "
       "rejected. Exit checks cannot run: not being watched. The record "
       "does not establish a grower: a turnaround these rules will not "
       "judge. The rest carry their consequence in their names and declare "
       "none.",
    2: "THE PRICE EXIT NOW ACTS IN DAYS RATHER THAN IN QUARTERS. No level "
       "moved.\n\n"
       "`exit-peg` reads a multiple against a share price, and that is a new "
       "number every session. The host used to wait for a second FILING to "
       "carry the breach before closing the position — up to a quarter, "
       "while the multiple this exit exists to catch moved every day and the "
       "series doing the waiting could not see any of it. A company bought "
       "for its growth whose price ran away in a fortnight could not be sold "
       "on that until its next report agreed. It now takes two trading "
       "days.\n\n"
       "Two, and not more, because what a second close rules out is the odd "
       "print — a thin session, a bad tick, a halt. How long you are willing "
       "to hold something expensive is `exit-peg` itself, and saying it "
       "twice would be saying half of it somewhere you cannot see. The six "
       "other exits are unchanged: they read the accounts, and the accounts "
       "change when a report is filed.",
        1: "First version, and the first strategy in this program whose "
           "entry tests and exit tests are different measures.\n\n"
           "WHAT IT BUYS ON is a five-year earnings growth rate measured "
           "between three-year averages at each end, a price against that "
           "growth, a limit on borrowing, and the gap between earnings "
           "growth and sales growth — four tests it will not bend — and then "
           "four questions about the business, every one of which has to be "
           "answered: what you are paying, whether sales are growing, "
           "whether the growth is real, and whether a stumble would be "
           "survivable.\n\n"
           "WHAT IT SELLS ON is the trailing twelve months, not the "
           "five-year rate. This is the departure from the expert report "
           "that matters most and the second review argued for it "
           "directly. The report sells when the five-year rate falls below "
           "8%; a rate whose ends are three-year means cannot fall that far "
           "until the bad years have worked their way into a mean, which is "
           "years after the business changed — and the report then asked "
           "for four consecutive readings of it on top, which is nine years "
           "of data to establish one fact. The exit here is earnings over "
           "the last twelve months against the twelve before, below 8% on "
           "two consecutive filings, with sales over the same two windows "
           "having to agree before it fires. The delay drops from years to "
           "about six months, and it measures the thing Lynch acted on: "
           "that the company stopped growing.\n\n"
           "THE GROWTH FLOOR IS 10% AND NOT 15%, which is the review's "
           "correction and it changes what this strategy will buy more than "
           "any other number here. Lynch sorted companies into six kinds and "
           "held stalwarts at 10–12% deliberately, as ballast rather than as "
           "rejects; a 15% floor can only ever buy one of the six. The price "
           "test does the work instead — his own rule that a fairly priced "
           "company's multiple equals its growth rate is not a statement "
           "about any one category — and the dividend-adjusted version of "
           "it, which is what a stalwart should be judged on, has come up "
           "from the reported rows into the tests that decide. The revenue "
           "growth floor came down with it, to 5%, because a 10% sales bar "
           "would have kept stalwarts out through a different door; that "
           "number is this author's and says so.\n\n"
           "THE EARNINGS-VERSUS-SALES SPREAD IS A KNOCKOUT rather than one "
           "of eight tests where six must pass. The price test and the "
           "growth band both take the same growth number, so a distorted "
           "base breaks two of the four required tests at once, and the "
           "spread is the only thing that catches it.\n\n"
           "A COMPANY WHOSE EARNINGS APPEARED RATHER THAN GREW IS NAMED AS "
           "ONE. Where profits at the base of the window were almost nothing "
           "and the margin was almost nothing, a compound rate measures a "
           "recovery, which has a ceiling that selling more does not. This "
           "reports that the record does not establish a grower and points "
           "at the turnaround rules Lynch used for such companies, rather "
           "than reporting that it cannot decide.\n\n"
           "INSTITUTIONAL OWNERSHIP IS NOT HERE. The report asks for it "
           "below 60% on the reasoning that a stock every large fund already "
           "owns has no marginal buyer left. Index funds now hold something "
           "like a fifth to a quarter of the US market, so typical large-cap "
           "ownership sits well above 60% for reasons that say nothing about "
           "whether anyone has noticed the company, and the holdings data "
           "cannot separate index money from active. The signal the rule "
           "wanted is not recoverable, so the rule is gone rather than "
           "kept while meaning something else.\n\n"
           "THE SECOND VALUATION EXIT IS ALSO NOT HERE. The report sells "
           "when the multiple reaches 1.75 times the company's own five-year "
           "median. That measure stays as an entry test and is not an exit: "
           "this strategy already has a valuation exit that is Lynch's own, "
           "and a second one that is not his doubles the ways a whole "
           "category re-rating can force a sale.\n\n"
           "TWO ATTRIBUTIONS ARE SOFTER THAN THE REPORT'S. Borrowing at "
           "half of equity is sensible and is not a figure Lynch published; "
           "the price against a company's own five-year median is good "
           "practice and is not his. Both keep their levels and both say so "
           "where they are declared.\n\n"
           "SIZING IS LYNCH'S OWN DOCUMENTED ADVICE, because the report was "
           "never asked. Eight names rather than Graham's twenty or "
           "Buffett's ten, and a cap on adding well short of Buffett's — "
           "this method expects a position to become large by rising, not by "
           "being bought large. No holding period and no trim.",
    },

    # -----------------------------------------------------------------
    # Twelve states.
    #
    # Three of them close a position, where Buffett has two and Graham
    # three, and the split is deliberate: this strategy exits for reasons
    # that are genuinely different from one another, and a reader told
    # only that they are out has been told the least useful half of it.
    #
    # There is no state here that reduces a position and none that blocks
    # waiting on the user. Neither is an omission to be filled later. The
    # first is what this strategy believes about a winner that has grown
    # large; the second is a consequence of every test here being a
    # measurement — nothing in this file asks the reader a question, which
    # is worth noticing beside a strategy that asks three.
    # -----------------------------------------------------------------
    "states": [
        {"id": "worth-buying", "render": "commit",
         "name": "Worth buying, at this price",
         "description": "Every test this strategy will not bend has passed, "
                        "and all four questions it asks about the business "
                        "are answered.\n\n"
                        "That is a claim about the price and the growth "
                        "together, and neither on its own. A company growing "
                        "quickly at a price that has already paid for the "
                        "growth is not a buy here, and neither is a cheap "
                        "company that has stopped growing. The size is an "
                        "equal share of the names this strategy runs at "
                        "once."},

        {"id": "room-for-more", "render": "commit",
         "name": "Room for more of it",
         "description": "You own it, nothing that would end the position has "
                        "happened, and it would still be bought at today's "
                        "price on the same tests that bought it. It also "
                        "sits below the most this strategy will take one "
                        "name to by buying, and that gap is the whole of "
                        "what may go in.\n\n"
                        "This says the position may take capital. It does "
                        "not say to put any in. Nothing here knows or can "
                        "know what you paid — an add is never triggered by "
                        "the price having fallen below your own cost."},

        {"id": "no-room", "render": "hold",
         "name": "No room for it",
         "description": "It passes, and you already hold as many names as "
                        "this strategy runs at once. This is not a verdict "
                        "against the company — it is a fact about your list, "
                        "and it changes the day one of your holdings "
                        "closes.\n\n"
                        "This strategy holds a short list on purpose. Its "
                        "arithmetic depends on knowing each company well "
                        "enough to notice when its story changes, and that "
                        "is what stops working first when the list grows."},

        {"id": "not-growth-at-this-price", "render": "hold",
         "name": "Not a buy at this price",
         "description": "At least one test this strategy cannot bend has "
                        "failed, or one of the four questions it asks about "
                        "the business has been settled against it. Read "
                        "which below.\n\n"
                        "Two thirds of what fails here fails on price rather "
                        "than on the company. A good business growing well "
                        "whose multiple has already paid for the growth is "
                        "the ordinary case, and it is not a criticism of the "
                        "business — it is the reason to wait."},

        {"id": "not-established-as-a-grower", "render": "hold",
         "name": "The record does not establish a grower",
         "consequence": "a turnaround, not a grower — these rules will not judge it",
         "description": "The profits at the start of this company's record "
                        "were almost nothing, and so was the margin on them. "
                        "What looks like growth is mostly the distance from "
                        "almost nothing: the earnings did not grow, they "
                        "appeared.\n\n"
                        "That is a real and often interesting thing for a "
                        "company to be doing — it is a turnaround, or a "
                        "margin recovering from a bad patch — and it is not "
                        "what any test in this strategy was built to "
                        "measure. A recovering margin has a ceiling that "
                        "selling more does not, so a compound growth rate "
                        "taken off that base describes the recovery and then "
                        "keeps describing it after it has finished.\n\n"
                        "Lynch treated these as a separate kind of company "
                        "with rules of their own, chiefly about whether the "
                        "balance sheet survives long enough for the recovery "
                        "to finish. This strategy does not implement those "
                        "rules, and it will not judge a turnaround by the "
                        "ones it has."},

        {"id": "cannot-screen", "render": "unknown",
         "name": "Not enough to go on",
         "consequence": "undecided, not rejected — more data may settle it",
         "description": "Some of the figures this strategy needs are "
                        "missing, and the ones that are present do not "
                        "settle it either way. A missing number is not a "
                        "pass and it is not a failure, so nothing is "
                        "claimed. The reasons below say which figures are "
                        "absent and why.\n\n"
                        "This is commoner here than you might expect and it "
                        "is not a fault. The growth rates need eight fiscal "
                        "years of accounts on one basis, and a company that "
                        "listed five years ago simply does not have them "
                        "yet — which is a fact about the record rather than "
                        "about the company."},

        {"id": "hold", "render": "hold",
         "name": "Nothing to do",
         "description": "You own it, every test that could be run came back "
                        "clear, and nothing that would end this position has "
                        "happened.\n\n"
                        "It also covers every way more money does not go in "
                        "today — no room left under the most this strategy "
                        "will hold in one name, a company that would not "
                        "pass the entry tests at today's price, or a figure "
                        "that could not be worked out. The rule named beside "
                        "the verdict says which, and an unreadable test is "
                        "never reported as a failed one."},

        {"id": "one-reading-past", "render": "hold",
         "name": "One reading past the line",
         "consequence": "waiting on the next readings to confirm · nothing owed",
         "description": "An exit level has been crossed on the current "
                        "reading, and this strategy will not act on it until "
                        "the next readings say the same thing — trading days "
                        "for the price exit, filings for the growth ones. "
                        "One heavy quarter, one settlement, one inventory "
                        "build ahead of a launch can push a measure over a "
                        "line without anything having changed, and selling "
                        "on that would be the panic this exists to prevent. "
                        "Nothing is owed from you today.\n\n"
                        "Worth knowing: the wait counts *readings on "
                        "record*. On a company with nothing fetched — every "
                        "figure typed in by hand — nothing ever confirms, "
                        "and an exit can sit here indefinitely however bad "
                        "the number gets."},

        {"id": "growth-stopped", "render": "close",
         "name": "It has stopped growing",
         "description": "Earnings over the last twelve months are barely "
                        "above where they were a year ago, they were on the "
                        "filing before this one as well, and sales agree.\n\n"
                        "This is the exit this strategy is built around. The "
                        "reason to own this was that it was growing; that is "
                        "no longer what it is doing, and a company bought "
                        "for its growth and held after the growth stops is a "
                        "company being held for a reason nobody chose.\n\n"
                        "Sales have to agree before this fires. Earnings "
                        "falling while sales keep rising is a bad year on "
                        "costs, and nothing here sells a growing company for "
                        "one of those."},

        {"id": "price-ran-ahead", "render": "close",
         "name": "The price has run ahead of the growth",
         "description": "What this company costs, measured against how fast "
                        "it is growing, has reached twice the level that "
                        "would have bought it.\n\n"
                        "Nothing about the business has broken. This is the "
                        "position having worked: the market now pays for "
                        "growth that has not happened yet, and the return "
                        "that was ahead of you has been paid in advance. "
                        "That is the point at which this strategy takes the "
                        "money and looks for the next one.\n\n"
                        "It is also the sharpest disagreement between this "
                        "strategy and the Buffett one, which has no "
                        "valuation exit at all and would call this the worst "
                        "mistake available. Both positions are held "
                        "seriously by serious people; they are separate "
                        "strategies and separate journals for exactly that "
                        "reason."},

        {"id": "story-broke", "render": "close",
         "name": "The story has broken",
         "description": "Borrowing, interest cover, cash generation, or "
                        "product piling up in the warehouse or in unpaid "
                        "invoices — one of these has gone wrong and stayed "
                        "wrong across more than one set of filings.\n\n"
                        "A growing company is spending ahead of its sales "
                        "and has usually never been tested by a downturn, "
                        "which is why these end the position here rather "
                        "than being noted beside it. Leverage plus a growth "
                        "stumble is the standard way a position like this "
                        "goes to nothing."},

        {"id": "cannot-watch", "render": "unknown",
         "name": "Exit checks cannot run",
         "consequence": "not being watched — a fetch or typed figures restore it",
         "description": "You own it, and not one of the exit tests could be "
                        "worked out from the data on record — so this "
                        "strategy has nothing to say about whether to stay. "
                        "It is not telling you to hold; it is telling you it "
                        "cannot tell. Fetching data, or entering the figures "
                        "by hand, is what changes it."},
    ],

    "inputs": [
        # Deliberately optional, exactly as on Graham and Buffett. Without it
        # the size rules cannot be worked out and say so, naming this field.
        # Requiring it would put a setup gate in front of every verdict in the
        # journal over a rule that binds on one holding in a handful.
        {"id": "free-cash", "label": "Free cash", "type": "number",
         "unit": "usd", "role": "cash", "required": False,
         "explain": "Money in the account this journal covers that is not "
                    "in any position. You do not type it: the journal "
                    "works it out from what you record moving — an "
                    "opening balance, then deposits, withdrawals and "
                    "dividends received, with what every purchase cost "
                    "and every sale fetched read off your own lots. It "
                    "adds that to what your holdings are worth to get "
                    "the account total, and that total is what a "
                    "position's size is measured against. Until the "
                    "record is opened the size rules say they cannot "
                    "be worked out rather than guessing at them."},
    ],

    # -----------------------------------------------------------------
    # Every number this strategy demands, with what it means, why it sits
    # where it does, and where it misfires.
    # -----------------------------------------------------------------
    "values": [

        # -- how the tests roll up -----------------------------------------
        #
        # Two settings, and only the two groups whose members are
        # near-readings of one another carry a count. There is deliberately
        # no setting for the groups that demand all of their rows: "both of
        # these must pass" is not a level anybody can retune without changing
        # what the group means, and a group that could be quietly set to
        # nought is the eight-test quota arriving again by another door.
        {"id": "price-tests-required",
         "label": "Price tests that must pass, of two",
         "type": "integer", "unit": "count", "min": 0, "max": 2,
         "source": AUTHOR,
         "explain": "This strategy asks two supporting questions about what "
                    "you are paying: whether the price is low against the "
                    "growth plus the dividend, and whether it is low against "
                    "what the market has usually paid for this particular "
                    "company. This is how many of the two have to come back "
                    "clear.\n\n"
                    "One, for two reasons. Both divide the same current "
                    "price-to-earnings figure, so a company whose latest "
                    "earnings carry a one-off charge has both readings moved "
                    "the same way by the same event — two tests that fail "
                    "together on one cause are one test.\n\n"
                    "And the main price test is already a knockout. "
                    "Requiring cheapness against growth, against growth plus "
                    "yield, and against the company's own history all at "
                    "once is a very heavy gate for a growth strategy: in any "
                    "period where a whole category re-rates upward, every "
                    "company in it fails the test against its own history "
                    "regardless of how good it is. The knockout is the "
                    "question; these two are how it is corroborated.\n\n"
                    "Set it to 2 and you have made this strategy noticeably "
                    "stricter and given it a strong tendency to buy nothing "
                    "for years at a time in an expensive market. Set it to 0 "
                    "and the only price test left is the knockout."},

        {"id": "quality-tests-required",
         "label": "Tests of whether the growth is real that must pass, of "
                  "three",
         "type": "integer", "unit": "count", "min": 0, "max": 3,
         "source": AUTHOR,
         "explain": "This strategy asks three questions about whether the "
                    "reported growth is genuine: is product piling up in the "
                    "warehouse faster than it sells, are sales being booked "
                    "and not collected, and is the growth being bought with "
                    "discounts. This is how many of the three have to come "
                    "back clear.\n\n"
                    "Two, and the reason is mostly about which companies "
                    "have an answer at all. Software, services and most "
                    "asset-light businesses hold no inventory, so that test "
                    "is permanently unreadable for them — and an unreadable "
                    "test is not a passing one, so demanding all three would "
                    "leave every such company undecided forever and unable "
                    "to be bought. Two means the question gets answered by "
                    "whichever readings exist.\n\n"
                    "It is also the case that these move together. A company "
                    "discounting hard to shift product shows it in the "
                    "margin and in the inventory at the same time, so three "
                    "passes is often one fact counted three times.\n\n"
                    "Set it to 3 and you have excluded most businesses "
                    "without a warehouse. Set it to 1 and you have kept the "
                    "heading and dropped the standard: this is the group "
                    "that guards against the single failure a backward-"
                    "looking growth rate is worst at seeing coming."},

        # -- how much, and how many ----------------------------------------
        #
        # The two values here that are not the report's, and a third
        # different answer to a question the other two strategies also
        # answered. Graham holds twenty names at five percent because he has
        # formed no opinion about any of them. Buffett holds ten and will
        # take one to forty because forming an opinion is the whole method.
        # This holds eight and will take one to twenty-five, because the
        # method expects one or two of the eight to become very large by
        # rising rather than by being bought.
        {"id": "portfolio-slots", "label": "Names held at once",
         "type": "integer", "unit": "count", "min": 1, "max": 100,
         "source": LYNCH_PRACTICE,
         "explain": "How many separate companies this strategy holds at one "
                    "time. Each first purchase takes an equal share of the "
                    "account, so eight names means about twelve and a half "
                    "percent each, and once every place is taken a new "
                    "candidate is told there is no room rather than being "
                    "talked down.\n\n"
                    "Eight sits toward the top of the three-to-ten range "
                    "Lynch gave individual investors for a small portfolio. "
                    "His argument against going wider is that diversifying "
                    "into companies you know nothing about buys you nothing, "
                    "and his argument against going narrower is that however "
                    "carefully you choose, one of them will be hit by "
                    "something nobody could have seen. The top of the range "
                    "rather than the bottom because five names is a "
                    "concentration somebody should arrive at deliberately "
                    "and not one a tool should hand them by default.\n\n"
                    "The number matters more here than on a strategy that "
                    "holds for decades. This method's arithmetic is that one "
                    "or two large winners pay for a majority that did not "
                    "work — so cutting the list makes it likelier that no "
                    "position in it is a large winner, which is the way this "
                    "style fails rather than a risk it takes.\n\n"
                    "Past about fifteen you are holding more companies than "
                    "you can follow closely enough to notice when one of "
                    "their stories changes, and noticing that is the entire "
                    "exit discipline here.\n\n"
                    "This figure and the cap below are the only two here "
                    "that do not come from the expert report — it was never "
                    "asked about sizing."},

        {"id": "position-weight-cap",
         "label": "Most this will put into one name",
         "type": "number", "unit": "percent", "min": 1, "max": 100,
         "source": AUTHOR,
         "explain": "The largest share of your account this strategy will "
                    "take a single holding up to **by buying more of it**.\n\n"
                    "It is a limit on your purchases, not on the position. "
                    "If a holding multiplies until it is half the account, "
                    "nothing here tells you to trim it — this strategy has "
                    "no trim, on purpose, because a position that got large "
                    "by rising is precisely what the method is trying to "
                    "produce. What this number does is stop you *adding* "
                    "past it.\n\n"
                    "Twenty-five percent is twice the share a first purchase "
                    "takes, so a company can be added to twice as its story "
                    "keeps proving out, and it is far short of the forty "
                    "percent the Buffett strategy in this program will "
                    "commit to one name. That difference is the point rather "
                    "than a matter of taste. Buffett's concentration rests "
                    "on a judgement about a business that is meant to hold "
                    "for decades; this strategy's holding periods are "
                    "measured in quarters to a few years and its exits fire "
                    "on things that can change in one filing, so a position "
                    "sized for a decade of conviction is sized wrong here.\n\n"
                    "**Lynch published no such figure and none is claimed "
                    "for him.** He advised individuals on how many companies "
                    "to hold and not on how much to put in one. This number "
                    "is this file's, derived from the slot count above, and "
                    "it is the one in this strategy with the least behind "
                    "it.\n\n"
                    "It needs this journal's cash record to be open, "
                    "because a share of the account cannot be worked out "
                    "without knowing what the account is. Until it is, the "
                    "size rules report that they could not be run."},

        # -- was there a business at the base of the window ----------------
        {"id": "min-earnings-base-share",
         "label": "Least the company may have earned at the start of its "
                  "growth window, as a share of what it earns now",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": REVIEW,
         "explain": "A growth rate is a comparison between what a company "
                    "earned then and what it earns now, and it stops meaning "
                    "anything when the *then* is almost nothing. A company "
                    "going from a cent a share to two dollars produces an "
                    "enormous compound rate that describes arithmetic rather "
                    "than a business.\n\n"
                    "This is the floor on the *then*, written as a share of "
                    "the *now* rather than in money. At 10 the company has "
                    "to have been earning at least a tenth of what it earns "
                    "today. Both ends are three-year averages, so one bad "
                    "year at either end cannot swing it.\n\n"
                    "It is a share and not an amount of money for a reason "
                    "worth knowing: any floor written in cents of earnings "
                    "per share is measuring the share count. A three-for-one "
                    "split turns a thirty-cent base into ten and changes "
                    "nothing whatever about the company.\n\n"
                    "**Failing this on its own is not a fault and does not "
                    "reject anything.** A company whose sales multiplied as "
                    "fast as its earnings reads low here and grew, "
                    "straightforwardly. Only failing this *and* the margin "
                    "test below together says the earnings appeared rather "
                    "than grew, and only that combination reaches a verdict."},

        {"id": "min-margin-base-share",
         "label": "Least the margin may have been at the start of the growth "
                  "window, as a share of the margin now",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": REVIEW,
         "explain": "The other half, and the half that separates a company "
                    "that grew from one that recovered.\n\n"
                    "A business that scaled up keeps roughly the profit it "
                    "made on each dollar of sales, or improves it a little: "
                    "going from eight cents in the dollar to twelve over "
                    "five years is ordinary operating leverage and reads as "
                    "67 here. A business whose margin came back from nothing "
                    "— half a cent in the dollar to eight cents — reads as "
                    "6, and its earnings multiplied because the margin "
                    "returned rather than because it sold more.\n\n"
                    "50 is the level the second review proposes, and its "
                    "argument for a margin test rather than an earnings one "
                    "is that this is free of scale, of currency and of "
                    "industry: it is a ratio of two ratios, so it says the "
                    "same thing to a company selling ten dollars and one "
                    "selling ten billion.\n\n"
                    "**Failing this alone is not a fault either.** On its "
                    "own it is a margin-expansion test, and plenty of good "
                    "companies expand margins a great deal while genuinely "
                    "growing. It is the pair that means something.\n\n"
                    "The metric bank refuses to compute a five-year growth "
                    "rate on the same pair at the same two levels, which is "
                    "why the growth rate is usually absent when these both "
                    "fail. That is not one rule written twice: the bank is "
                    "declining to serve a number it cannot stand behind, and "
                    "this is a strategy deciding what kind of company it is "
                    "looking at. Move these and the two part company, which "
                    "is allowed and lands on the rule-change record."},

        # -- the knockouts -------------------------------------------------
        {"id": "max-peg",
         "label": "Highest price against growth it will pay",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "What the company costs per dollar of profit, divided by "
                    "how fast that profit is growing. A company priced at 24 "
                    "times its earnings and growing 20% a year reads 1.2 "
                    "here.\n\n"
                    "This is the most important number in this strategy and "
                    "the one it is really about. Lynch's formulation is that "
                    "the price-to-earnings of any fairly priced company will "
                    "equal its growth rate — so a reading of 1.0 is fair, "
                    "below 1.0 is the growth not yet paid for, and above is "
                    "paying today for growth that has not happened.\n\n"
                    "1.0 rather than 1.2 or 1.5 because it is his number and "
                    "it is the definition of the strategy. Loosening it "
                    "turns growth at a reasonable price into growth, which "
                    "is a different and much worse thing to be doing.\n\n"
                    "Where it misfires: a company growing at 2% produces "
                    "absurd readings here — the dividend-adjusted version "
                    "among the supporting tests is the one to look at for "
                    "those. A cyclical coming off the bottom shows enormous "
                    "trailing growth and a flattering reading at exactly the "
                    "wrong moment, and nothing in this program can tell that "
                    "apart from a company that is simply growing."},

        {"id": "min-eps-growth",
         "label": "Slowest growth it will buy",
         "type": "number", "unit": "percent",
         "source": REVIEW,
         "explain": "How fast profit per share has grown per year over five "
                    "years, measured between three-year averages at each "
                    "end so that a single unusual year at either end cannot "
                    "set the answer.\n\n"
                    "**This level was 15 in the expert report and the second "
                    "review overruled it, and the change matters more than "
                    "any other number here.** Lynch's method starts by "
                    "sorting a company into one of six kinds, and companies "
                    "growing at 10 to 12 percent — he called them stalwarts "
                    "— were deliberate ballast in his portfolio rather than "
                    "rejects. A floor at 15 can only ever buy one of the "
                    "six, which makes a rule set named after him into a "
                    "fast-grower screen wearing his name.\n\n"
                    "At 10 the price test does the work instead, which is "
                    "the right division of labour: his rule that a fairly "
                    "priced company's multiple equals its growth rate is not "
                    "a statement about any one category, and it prices a "
                    "stalwart perfectly well.\n\n"
                    "Raise it back to 15 and you have a fast-grower "
                    "strategy, which is a legitimate thing to run — but "
                    "raise the supporting price test with it, because the "
                    "dividend-adjusted reading is in the tests that decide "
                    "specifically to serve the slower companies this floor "
                    "now admits.\n\n"
                    "Where it misfires: a company that has been buying back "
                    "a lot of its own shares grows profit per share faster "
                    "than it grows profit, and the earnings-against-sales "
                    "test among the knockouts is what catches that."},

        {"id": "max-eps-growth",
         "label": "Fastest growth it will buy",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "The upper end of the band, and the distinctive part of "
                    "it — no other strategy in this program refuses a "
                    "company for growing too fast.\n\n"
                    "Lynch was direct about avoiding companies growing 50 "
                    "to 100 percent a year. The reasoning is that growth "
                    "like that attracts competition, cannot persist for "
                    "long, and is priced as though it can — so a company "
                    "growing 20 to 25 percent is a better proposition than "
                    "one growing 60 at the same price against growth, "
                    "because the second one's price contains an assumption "
                    "that will not survive.\n\n"
                    "35 catches the genuine hypergrowth cases without "
                    "excluding good fast growers. Note what it does to the "
                    "price test: a company growing at 60 percent would need "
                    "a multiple of 60 to read 1.0, and this refuses it "
                    "before that arithmetic gets a chance to look "
                    "reasonable.\n\n"
                    "Where it misfires: a company recovering from a bad year "
                    "posts a huge rate for one window and is refused for it. "
                    "The two tests of what the company looked like at the "
                    "start of the window are what catch the extreme version "
                    "of that, and they name it rather than rejecting it."},

        {"id": "max-debt-to-equity",
         "label": "Highest debt against equity",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "Everything the company has borrowed, divided by what "
                    "its owners have in it. At 0.5 it has borrowed fifty "
                    "cents for every dollar of equity.\n\n"
                    "**Half of what the Graham strategy in this program "
                    "accepts, and the difference is deliberate.** A Graham "
                    "company has ten straight profitable years behind it and "
                    "can survive a full turn of debt. A company growing 20 "
                    "percent a year is spending ahead of its sales and has "
                    "usually never been tested by a downturn. Leverage plus "
                    "a growth stumble is the standard way a position like "
                    "this goes to nothing, and it is why this is a knockout "
                    "rather than a test that can be outvoted.\n\n"
                    "**The level is the report's and the attribution is "
                    "softer than the report's.** The second review checked "
                    "it and found no published Lynch figure: he wrote about "
                    "the debt factor at length and preferred companies with "
                    "more cash than debt, but 0.5 is consistent with his "
                    "stated preference rather than a number he gave. Read it "
                    "as sensible rather than as canonical.\n\n"
                    "Where it misfires: a company that listed recently with "
                    "a large cash balance and a small equity base reads "
                    "oddly. Negative equity makes the ratio meaningless and "
                    "the journal marks it unreadable rather than scoring it "
                    "badly."},

        {"id": "max-growth-spread",
         "label": "Most that profit growth may outrun sales growth",
         "type": "number", "unit": "percentage_points",
         "source": REVIEW,
         "explain": "How many points faster profit per share has grown than "
                    "sales, over the same five years. A company growing "
                    "profit at 30 percent on sales growing at 4 has a spread "
                    "of 26 and fails this at 10.\n\n"
                    "**What it means.** Whether the growth is coming from "
                    "the business or from arithmetic. Widening margins and "
                    "buying back shares are real and legitimate, and both "
                    "grow profit per share without the company selling any "
                    "more than it did. The difference is that a business "
                    "selling more can keep doing it, and a margin that has "
                    "gone from 8 percent to 22 cannot go to 36. Beyond about "
                    "ten points there is no third act.\n\n"
                    "Ten points of headroom because genuine operating "
                    "leverage in a scaling business easily produces that gap "
                    "and should not be punished for it.\n\n"
                    "**This test was one of eight where six had to pass, and "
                    "the second review moved it up here. That is the most "
                    "structural of its corrections to this profile.** The "
                    "price test and the growth band are both knockouts and "
                    "both take the same growth number as an input, so a "
                    "company whose growth rate is distorted fails to be "
                    "caught by either — both are broken in the same "
                    "direction at the same moment. This is the only test in "
                    "the file that catches that, and a tier where two "
                    "failures are affordable cannot be relied on to enforce "
                    "it."},

        # -- what you are paying for the growth ----------------------------
        {"id": "max-dividend-adjusted-peg",
         "label": "Highest price against growth plus yield",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "The same price-against-growth reading with the dividend "
                    "yield added to the growth rate. A company priced at 13 "
                    "times earnings, growing 10 percent and paying 3 percent "
                    "reads 1.0 here and 1.3 on the plain version.\n\n"
                    "**What it means.** What you get back per year, counting "
                    "both the ways you get it. Lynch used this explicitly "
                    "for the slower, dividend-paying companies where the "
                    "plain reading is useless: a company growing at 4 "
                    "percent and yielding 4 is returning 8 percent a year to "
                    "its owner, and a test that only counted the growth "
                    "would call it twice as expensive as it is.\n\n"
                    "**This was a reported-only row in the report and it "
                    "decides purchases here.** That follows directly from "
                    "the growth floor coming down to 10: the report's own "
                    "note says to promote this if the growth band is widened "
                    "downward, because the companies the wider band lets in "
                    "are exactly the ones this measure exists for. The "
                    "reasoning here is this file's rather than the report's; "
                    "only the level of 1.0 is the report's.\n\n"
                    "One of this and the test below has to pass, not both. "
                    "In a period when a whole category re-rates upward, the "
                    "test below fails for every company in it."},

        {"id": "max-pe-to-own-median",
         "label": "Highest price against what this company usually costs",
         "type": "number", "unit": "times_own_median", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "What the company costs per dollar of profit today, "
                    "against the middle of what it has cost over the last "
                    "five years. At 1.0 it costs what it usually costs; at "
                    "1.4 it is forty percent dearer than its own normal.\n\n"
                    "**What it means.** Whether the price is high or low for "
                    "*this* company rather than for companies in general. A "
                    "multiple of 30 is expensive for a supermarket and "
                    "ordinary for a software business, and comparing a "
                    "company against its own history sidesteps the question "
                    "of which it is.\n\n"
                    "**The level is the report's and the idea is not "
                    "Lynch's.** The second review is explicit that this is "
                    "good practice rather than anything he published, and it "
                    "is attributed to practice here. The reasoning above is "
                    "this file's.\n\n"
                    "Where it misfires: a company whose business has "
                    "genuinely changed — a hardware maker that became a "
                    "software company — has a five-year median describing a "
                    "company that no longer exists. And five years of "
                    "steadily falling multiples make a company that is "
                    "quietly dying look cheap against itself the whole way "
                    "down. It needs twenty quarters of stored prices, so it "
                    "is unreadable for a company this journal has followed "
                    "for less than that."},

        # -- whether the top line is growing -------------------------------
        {"id": "min-revenue-growth",
         "label": "Slowest sales growth it will buy",
         "type": "number", "unit": "percent",
         "source": AUTHOR,
         "explain": "How fast sales have grown per year over three years, "
                    "measured between three-year averages at each end.\n\n"
                    "**Three years here where the profit test uses five, and "
                    "that is deliberate.** Sales are the faster-moving "
                    "signal, and what this asks is whether the top line has "
                    "slowed down *recently* — which a five-year window would "
                    "smooth away. The two three-year averages it compares do "
                    "not overlap, so it is still a statement about recent "
                    "years rather than a shorter version of the same "
                    "question.\n\n"
                    "**The report sets this at 10 and this is 5, and the "
                    "change is this file's rather than either source's.** It "
                    "follows from the profit growth floor coming down to 10 "
                    "on the review's argument. A company growing profits at "
                    "11 percent a year — the stalwart that change exists to "
                    "let in — typically grows sales in the mid single "
                    "digits, so a 10 percent sales bar would have kept "
                    "exactly those companies out through a door nobody "
                    "looked at. Leaving it at 10 would have made the "
                    "review's correction cosmetic.\n\n"
                    "It is worth saying plainly that this now sits close to "
                    "the 4 percent the Buffett strategy in this program uses "
                    "for the same measure, where the report drew a sharp "
                    "distinction between the two — his bar being 'keeping up "
                    "with the economy' and this one being 'actually "
                    "growing'. That distinction was drawn against a 15 "
                    "percent profit floor which no longer exists. If you put "
                    "the profit floor back to 15, put this back to 10."},

        # -- whether the growth is real ------------------------------------
        {"id": "max-inventory-spread",
         "label": "Most that stock may pile up faster than sales grow",
         "type": "number", "unit": "percentage_points",
         "source": REPORT,
         "explain": "How many points faster the value of unsold goods has "
                    "grown over the last year than sales have. At 5 the "
                    "warehouse may grow five points faster than the business "
                    "before this counts against it.\n\n"
                    "**What it means.** Whether product is piling up faster "
                    "than it is selling. This is one of the oldest and most "
                    "reliable early warnings that demand is softening, and "
                    "it appears in the balance sheet a quarter or two before "
                    "it appears in the profits.\n\n"
                    "It is Lynch's, and he would recognise it instantly — he "
                    "wrote about walking through shops and noticing whether "
                    "the stock was moving. This is the version of that "
                    "instinct you can read in a filing.\n\n"
                    "Where it misfires: companies with no inventory — "
                    "software, services, most fee businesses — have no "
                    "answer here at all, which is why two of the three tests "
                    "in this group are enough. A deliberate build ahead of a "
                    "product launch, or through a supply chain everyone "
                    "expects to seize up, looks identical to weakening "
                    "demand in the numbers."},

        {"id": "max-receivables-spread",
         "label": "Most that unpaid invoices may grow faster than sales",
         "type": "number", "unit": "percentage_points",
         "source": REPORT,
         "explain": "How many points faster money owed by customers has "
                    "grown over the last year than sales have.\n\n"
                    "**What it means.** Whether sales are being booked but "
                    "not collected. Money owed growing faster than sales "
                    "means either that customers are struggling to pay or "
                    "that the company is pushing product at its distributors "
                    "to make a quarter look better than it was. Both are "
                    "worth knowing before the quarter after.\n\n"
                    "Where it misfires: a genuine shift toward larger "
                    "customers who pay on longer terms triggers this "
                    "legitimately, and so does an acquisition, which brings "
                    "somebody else's unpaid invoices with it."},

        {"id": "min-gross-margin-change",
         "label": "Most the margin may have fallen in three years",
         "type": "number", "unit": "percentage_points",
         "source": REPORT,
         "explain": "How many points the profit on each dollar of sales, "
                    "before overheads, has moved over three years. At −2 the "
                    "margin may give up two points before this counts "
                    "against the company.\n\n"
                    "**What it means.** Whether the growth is being bought "
                    "with discounts. Fast-growing sales with a falling "
                    "margin usually means the company is purchasing market "
                    "share, and that stops working when the money runs "
                    "out — usually at the moment it is most needed.\n\n"
                    "Two points of tolerance because input costs, product "
                    "mix and currency all move a margin by a point or so "
                    "without anything being decided by anyone.\n\n"
                    "Where it misfires: a company that does not report the "
                    "cost of what it sells separately has no margin to read "
                    "here. The 2018 change to revenue accounting moved "
                    "shipping and fulfilment costs between two lines for "
                    "many companies, which puts an artificial step in the "
                    "record across that boundary."},

        # -- whether it survives a stumble ---------------------------------
        {"id": "min-interest-coverage",
         "label": "Lowest interest cover",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "How many times over the company's operating profit "
                    "covers the interest it owes. At 5 it earns five dollars "
                    "for every dollar of interest.\n\n"
                    "**What it means.** Whether a bad year is a bad year or "
                    "a crisis. Interest is owed whether or not the business "
                    "is going well, and a company covering it five times can "
                    "lose most of its profit and still pay.\n\n"
                    "Five rather than the eight the Buffett strategy in this "
                    "program asks for. A growing company reinvests everything "
                    "it earns and legitimately carries thinner cover than a "
                    "mature business throwing off cash; five is Graham's old "
                    "bond-safety line and is the right floor for a business "
                    "that is expected to be bigger next year.\n\n"
                    "Where it misfires: a company with no debt has no "
                    "interest to cover, and the ratio is unreadable rather "
                    "than excellent."},

        {"id": "min-free-cash-flow",
         "label": "Least spare cash it will accept",
         "type": "number", "unit": "usd",
         "source": REPORT,
         "explain": "What the business generated in the last twelve months "
                    "after paying for everything it bought to keep running "
                    "and to grow.\n\n"
                    "**What it means, and why the bar is merely above "
                    "nothing.** This strategy tolerates cash-hungry growth "
                    "that the Buffett strategy in this program would not "
                    "touch — that one wants ten cents of spare cash per "
                    "dollar of sales. All this asks is that the company is "
                    "not structurally dependent on somebody else's money to "
                    "survive. A business that has to raise capital to keep "
                    "going has handed the timing of its own future to "
                    "whoever is lending, and growth companies discover that "
                    "in exactly the quarter it is most expensive.\n\n"
                    "Above nothing rather than at least nothing, and the "
                    "difference is one tick: a company generating exactly "
                    "nothing is not a company generating cash. The exit on "
                    "the other side is set at *at least* nothing, so "
                    "breaking even does not force a sale of something you "
                    "already own. Buying and holding are different "
                    "questions and this is the one place the two levels "
                    "differ by a hair.\n\n"
                    "Where it misfires: a year with an unusually large "
                    "investment programme reads as a cash problem. It is a "
                    "trailing twelve months, so a single heavy quarter is a "
                    "quarter of it rather than the whole."},

        # -- reported, never blocking --------------------------------------
        {"id": "min-net-cash",
         "label": "Least net cash it likes to see",
         "type": "number", "unit": "ratio",
         "source": REPORT,
         "explain": "Cash and short-term investments less everything "
                    "borrowed, as a share of what the company's shares are "
                    "worth. At 0 the company has as much cash as debt; at "
                    "0.2 a fifth of what you are paying is money already "
                    "sitting in the bank.\n\n"
                    "**What it means.** How much of the price you are paying "
                    "is not for the business at all. Net cash lowers the "
                    "effective multiple on the operating company and it is a "
                    "cushion during a stumble — Lynch liked knowing both.\n\n"
                    "It is reported and never blocks. A good company with "
                    "modest net debt is a perfectly ordinary thing to own, "
                    "and the borrowing knockout is where debt actually gets "
                    "judged.\n\n"
                    "Where it misfires: short-term investments are "
                    "inconsistently tagged, so this reads low for some "
                    "companies that hold plenty."},

        {"id": "min-insider-buying",
         "label": "Least insider buying it likes to see",
         "type": "number", "unit": "shares",
         "source": REPORT,
         "explain": "Shares bought by the company's own officers and "
                    "directors over the last six months, less what they "
                    "sold, excluding option exercises and pre-scheduled "
                    "sales.\n\n"
                    "**What it means.** Whether the people who know the most "
                    "about the company are putting their own money into it. "
                    "Lynch's reasoning about it is worth reading once: "
                    "insiders sell for dozens of reasons that have nothing "
                    "to do with the business — tax bills, houses, divorces, "
                    "not wanting everything they own in one place — but they "
                    "buy for one. So selling tells you nothing and buying "
                    "tells you something, which is why this has a floor and "
                    "no exit on the other side of it.\n\n"
                    "**Nothing in this program computes it.** It lives in a "
                    "different kind of SEC filing from everything else here "
                    "and this journal does not read that one yet, so this "
                    "row is blank unless you look it up and type it in — "
                    "which the row itself gives you a place to do. It is "
                    "kept, rather than dropped, because it is the only "
                    "signal in this strategy that moves in days rather than "
                    "quarters, and because a few minutes on the SEC's own "
                    "site answers it.\n\n"
                    "Where it misfires: small purchases timed to look good. "
                    "One director buying a token amount the week before "
                    "results is not the same as three of them buying "
                    "meaningfully in a quiet month."},

        # -- the exits -----------------------------------------------------
        #
        # None of them is a holding period, because this strategy has none.
        # Two of them are about the price and the growth, which is what makes
        # it a different animal from the Buffett strategy in this program;
        # the rest are about the company surviving.
        {"id": "exit-eps-growth",
         "label": "Growth below which a holding is sold",
         "type": "number", "unit": "percent",
         "source": REPORT_LEVEL_ONLY,
         "explain": "How much more the company earned per share over the "
                    "last twelve months than over the twelve before. Below "
                    "8 percent on two consecutive filings, with sales "
                    "agreeing, closes the position.\n\n"
                    "**This is the exit this strategy is built around.** "
                    "Lynch's sell discipline for a company bought for its "
                    "growth was that it stopped being one — and 8 percent is "
                    "well clear of ordinary quarterly noise while sitting "
                    "comfortably below the growth this strategy buys, so it "
                    "fires on a change of regime rather than on a wobble.\n\n"
                    "**The level is the report's and the measure under it is "
                    "not.** The report sells on the same five-year rate it "
                    "buys on, and the second review's argument against that "
                    "is the reason this strategy exists in the shape it "
                    "does: a rate whose ends are three-year averages cannot "
                    "fall below a level until the bad years have worked "
                    "their way into an average, which is years after the "
                    "business changed. This is the rate as it stands now, "
                    "and the position closes about six months after the "
                    "growth stops rather than several years after.\n\n"
                    "Lower it and you will sit through a real slowdown. "
                    "Raise it much and you will sell companies for having a "
                    "soft year, which on a business still growing sales is "
                    "what the corroboration below is there to prevent."},

        {"id": "exit-revenue-growth",
         "label": "Sales growth that keeps a holding despite weak earnings",
         "type": "number", "unit": "percent",
         "source": REPORT_LEVEL_ONLY,
         "explain": "How much more the company sold over the last twelve "
                    "months than over the twelve before. Sales still growing "
                    "faster than this keeps the position open even when "
                    "earnings have stalled.\n\n"
                    "**What it is for.** Earnings falling while sales keep "
                    "rising is a margin event — a year of higher costs, an "
                    "investment programme, a price war — and it is not the "
                    "same thing as a company that has stopped growing. This "
                    "strategy does not sell a growing business for having an "
                    "expensive year, so both readings have to fail before "
                    "the growth exit fires.\n\n"
                    "3 percent is the level the report attaches to its own "
                    "sales exit. It is deliberately low: this is not a test "
                    "of whether sales are growing well, it is a test of "
                    "whether they are growing at all, and anything above it "
                    "means the earnings weakness has some other explanation "
                    "worth finding before selling.\n\n"
                    "Note what it does at the boundary. Set it to 0 and only "
                    "outright shrinking sales will let the growth exit fire, "
                    "which is patient to the point of never selling "
                    "anything. Set it near the buy floor and the "
                    "corroboration stops doing its job."},

        {"id": "exit-peg",
         "label": "Price against growth at which a holding is sold",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "The same price-against-growth reading the buy test "
                    "uses, at the level where the position closes.\n\n"
                    "**Why there is an exit here at all, when the Buffett "
                    "strategy in this program leaves every valuation exit "
                    "blank.** Lynch sold, constantly, and was explicit about "
                    "why: a company whose multiple has run far past its "
                    "growth rate has borrowed its future return, and the "
                    "years of gain still ahead of you have been paid into "
                    "the price already. His holding periods were measured in "
                    "quarters to a few years rather than in decades, and "
                    "rotating out of something fully priced into something "
                    "that is not is most of where the return came from.\n\n"
                    "2.0 is twice the level that would buy it, so the "
                    "position has to become twice as expensive against its "
                    "own growth as it was worth paying. That gap is what "
                    "stops the strategy selling something the moment it "
                    "stops being a bargain.\n\n"
                    "**One thing to know about how quickly this can fire.** "
                    "The wait for a second reading counts trading days, "
                    "because that is how often this reading changes — a "
                    "multiple against a share price is a new number every "
                    "session. So a price that runs away in a fortnight "
                    "closes the position two sessions after it crosses, "
                    "rather than waiting for a filing that has nothing to "
                    "say about it.\n\n"
                    "What the two days buy is the odd close: a thin print, "
                    "a bad tick, a halt. They are not a bet that a high "
                    "price comes back down — how long you are willing to sit "
                    "with an expensive holding is what the level above says, "
                    "and saying it twice would be saying it in a place you "
                    "cannot see."},

        {"id": "exit-debt-to-equity",
         "label": "Debt against equity that ends a holding",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "Twice the level that would buy it. A growing company "
                    "that has taken its borrowing to a full turn of equity "
                    "has changed what it is: the equity has stopped being "
                    "the buffer and started being the thin end.\n\n"
                    "The gap between 0.5 and 1.0 is deliberate room. "
                    "Companies fund a good acquisition or a plant with debt "
                    "and pay it down, and a strategy that sold the moment "
                    "borrowing rose above what it would buy at would be "
                    "selling on ordinary corporate finance.\n\n"
                    "It takes two consecutive filings, because a balance "
                    "sheet is a photograph of one morning and a bond issued "
                    "the week before a quarter end is in it."},

        {"id": "exit-interest-coverage",
         "label": "Interest cover that ends a holding",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "Where the interest bill stops being comfortably "
                    "covered. At 3 the company earns three dollars of "
                    "operating profit for every dollar of interest — which "
                    "sounds like room and is not, for a business whose "
                    "profits are supposed to be growing and have instead "
                    "fallen far enough to get here.\n\n"
                    "Five is the bar to buy and three is the bar to stay, "
                    "and the gap is the same deliberate room the borrowing "
                    "exit has. Below three, one bad year takes the cover to "
                    "nothing."},

        {"id": "exit-free-cash-flow",
         "label": "Spare cash below which a holding is sold",
         "type": "number", "unit": "usd",
         "source": REPORT_LEVEL_ONLY,
         "explain": "The cash the business generated in the last twelve "
                    "months after everything it spent. Below nothing, on two "
                    "consecutive filings, closes the position.\n\n"
                    "**What it means.** A growing company that is burning "
                    "cash is being funded by somebody, and whoever that is "
                    "sets the terms of its future. One negative reading is "
                    "an investment programme or the timing of a payment; two "
                    "in a row on a trailing twelve months is a company that "
                    "needs money it does not make.\n\n"
                    "**The report asks for four consecutive quarters and "
                    "this takes two filings, which is a departure and the "
                    "one to argue with.** The report's reasoning is that a "
                    "single negative quarter is working-capital timing "
                    "rather than news, and it is right — but the measure is "
                    "already a trailing twelve months, so one quarter is a "
                    "quarter of it before anything waits, and four "
                    "consecutive readings of it span seven quarters of data "
                    "to establish a fact about one year. If you were relying "
                    "on the longer wait to sit through a deliberate "
                    "investment cycle, the honest place for that is this "
                    "level: say what burn you will accept rather than how "
                    "long you will wait to believe the reading."},

        {"id": "exit-inventory-spread",
         "label": "Stock piling up that ends a holding",
         "type": "number", "unit": "percentage_points",
         "source": REPORT,
         "explain": "Where a warehouse filling up stops being a wobble. At "
                    "20 the value of unsold goods has grown twenty points "
                    "faster than sales over a year, which is not a build "
                    "ahead of a launch — it is product that did not sell.\n\n"
                    "Four times the level that would refuse a purchase, "
                    "because a company you already own has earned the "
                    "benefit of the doubt on one year's build and a company "
                    "you are considering has not.\n\n"
                    "It fires on the newest filing alone. The measure "
                    "compares two single balance-sheet dates a year apart, "
                    "so the next filing replaces the end carrying the noise "
                    "rather than adding to a run — waiting for a second "
                    "reading would be waiting a year."},

        {"id": "exit-receivables-spread",
         "label": "Unpaid invoices that end a holding",
         "type": "number", "unit": "percentage_points",
         "source": REPORT,
         "explain": "Where money owed by customers outrunning sales stops "
                    "being a change in the customer mix. At 20 points over a "
                    "year, either the customers cannot pay or the sales were "
                    "pushed into the channel to make a quarter — and a "
                    "company that has done the second will have to do it "
                    "again, larger, next quarter.\n\n"
                    "Same four-fold gap from the buy level, and for the same "
                    "reason. This and the inventory exit are the two that "
                    "fire earliest in practice, which is exactly what they "
                    "are for: they show up in the balance sheet before the "
                    "profits, and this strategy buys on a growth rate that "
                    "by construction cannot see anything coming."},
    ],
}


# ---------------------------------------------------------------------------
# reading what the host handed over
# ---------------------------------------------------------------------------

PASS, FAIL, UNKNOWN = contract.PASS, contract.FAIL, contract.UNKNOWN
# How an exit came out. Imported rather than spelled out here: they are the
# host's words now, because the host is what decides which of them applies.
CLEAR, BREACHED = contract.CLEAR, contract.BREACHED
CONFIRMED, UNREADABLE = contract.CONFIRMED, contract.UNREADABLE


def _cite(measure_id, comparator, value_id, group, at=None, without=None):
    """One citation: which measure, which direction, and the setting the host
    reads the limit out of. Nothing here is a number.

    `at` cites the reading at one past filing; `without` cites the current
    window with the single year that most favours the requirement taken out.
    Both are the host's arithmetic on the host's figures — this file names the
    question and never the answer.
    """
    item = {"measure": measure_id, "comparator": comparator,
            "threshold_from": value_id, "group": group}
    if at is not None:
        item["at"] = at
    if without is not None:
        item["without"] = without
    return item


def _screen(ctx, rows, group):
    """(citations, outcomes) for one family of tests.

    The item that is tested is the item that is cited — the same dict, asked
    once. There is no second comparison here to disagree with the first.
    """
    cites = [_cite(m, c, v, group) for m, c, v in rows]
    return cites, [contract.test(ctx, item) for item in cites]


# ---------------------------------------------------------------------------
# was there a business at the base of the growth window
# ---------------------------------------------------------------------------

def _base(ctx):
    """Whether the record establishes a company that grew, as (citations,
    settled-against).

    Settled against only where BOTH readings came back failed. One failure is
    not evidence of anything — each of these on its own fires on companies
    that grew perfectly ordinarily, which is measured rather than assumed and
    is why neither is a test that can refuse anything by itself.

    An unreadable reading is never one of the two. A company whose accounts do
    not reach back eight years has not been shown to be a turnaround; it has
    not been shown to be anything, and that is a different verdict reached
    further down the ladder.
    """
    cites, out = _screen(ctx, WAS_THERE_A_BUSINESS, BASE_GROUP["id"])
    return cites, all(o == FAIL for o in out)


# ---------------------------------------------------------------------------
# the exits, and the confirmation walk
# ---------------------------------------------------------------------------

def _exit_state(ctx, group, measure_id, comparator, value_id):
    """One exit as confirmed / breached / clear / unreadable.

    `comparator` is what the holding must keep being true; the exit is that
    failing. How much evidence a breach needs is a property of the measure and
    the host derives it — this file neither states it nor could, because the
    seven exits here are read three different ways.

    Absence never fires an exit. A missing reading is not evidence that a
    company is in trouble, and this program does not sell on silence — but it
    is not reported as clear either, so the caller can tell an exit that was
    checked from one that was not.
    """
    return contract.confirm(ctx, _cite(measure_id, comparator, value_id,
                                       group))


def _growth_exit(ctx, group, earnings):
    """The growth exit as a single answer, out of its two halves.

    The requirement is that the company is still growing, and it holds while
    EITHER earnings or sales are. Only both failing ends the position, because
    earnings falling while sales keep rising is a year of higher costs and not
    a company that has stopped growing.

    Absence on either side leaves it unreadable rather than clear: a
    comparison nobody could make has not shown that nothing happened.
    """
    sales = contract.test(ctx, _cite(*REVENUE_CORROBORATION, group))
    if sales == PASS or earnings["confirmation"] == CLEAR:
        return {**earnings, "confirmation": CLEAR}
    if sales == UNKNOWN or earnings["confirmation"] == UNREADABLE:
        return {**earnings, "confirmation": UNREADABLE}
    return earnings


def _exit_states(ctx, group):
    """Every exit, in the order EXITS declares them."""
    states = [_exit_state(ctx, group, *row) for row in EXITS]
    states[GROWTH_EXIT] = _growth_exit(ctx, group, states[GROWTH_EXIT])
    return states


def _sales_held_it(ctx, group, states):
    """Whether sales alone are keeping the growth exit from firing.

    It has to be said out loud, because it is the one place where a red row
    sits on the screen beside a verdict saying nothing has ended. That is not
    a contradiction — the exit genuinely requires both halves — but a reader
    cannot be expected to work it out from one red row and a sentence that
    does not mention it.
    """
    if states[GROWTH_EXIT]["confirmation"] != CLEAR:
        return None
    earnings = contract.test(ctx, _cite(*EXITS[GROWTH_EXIT], group))
    if earnings != FAIL:
        return None
    return ("Earnings per share have stopped growing fast enough to hold this "
            "position on their own — but sales are still growing, and this "
            "strategy does not sell a company that is selling more for having "
            "an expensive year. One red row below, and no exit.")


def _confirmed_on(broken):
    """What the exits that fired were established on, in a clause.

    Derived rather than asserted, because the seven exits here are read three
    different ways and one sentence speaking for all of them would be asking
    the reader to take the strongest available reading on trust. Where they
    disagree the clause does not state a number at all.
    """
    ways = set()
    for f in broken:
        if f["robust"]:
            ways.add(" and the failure survives dropping the year that most "
                     "favours the company, which one bad year would not")
        elif f["needs"] <= 0:
            ways.add(" on a reading a single year cannot have moved, so "
                     "there is nothing to wait for")
        elif f["needs"] == 1:
            ways.add(f" on the newest {f['estimator']['counts_one']}")
        else:
            ways.add(f" on {f['needs']} consecutive "
                     f"{f['estimator']['counts']}, so this is a change "
                     "and not a wobble")
    if len(ways) != 1:
        return " each on the evidence its own measure can carry"
    return ways.pop()


def _waiting_unit(waiting) -> str:
    """The host's word for what these breaches are waiting on.

    Never "filings". Which series a breach is counted in is a property of the
    measure and the host derives it, so this asks rather than assumes — a
    valuation multiple is confirmed over trading days and a balance-sheet
    ratio over filings, and a single sentence covering both has to say
    "readings" rather than pick one and be wrong about the other.
    """
    nouns = {f["estimator"]["counts"] for f in waiting}
    return nouns.pop() if len(nouns) == 1 else "readings"


def _exit_evidence(group, states):
    """Every exit test, cited, with the confirming filings named where one
    actually fired. Citing the confirming readings is what lets a reader check
    the confirmation rule rather than take it on trust.

    Sales are cited beside the growth exit always, and not only when it fires:
    the two are one test, and a reader shown one of them has been shown half a
    rule.
    """
    out = []
    for i, ((measure_id, comparator, value_id), f) in \
            enumerate(zip(EXITS, states)):
        out.append(_cite(measure_id, comparator, value_id, group))
        if i == GROWTH_EXIT:
            out.append(_cite(*REVENUE_CORROBORATION, group))
        if f["confirmation"] in (CONFIRMED, BREACHED):
            for period in f["periods"]:
                out.append(_cite(measure_id, comparator, value_id, group,
                                 at=period))
            if f["robust"] is not None:
                out.append(_cite(measure_id, comparator, value_id, group,
                                 without="one-year"))
    return out



# ---------------------------------------------------------------------------
# the decision
# ---------------------------------------------------------------------------

def decide(ctx):
    """One evaluation, one state.

    The first fork is whether the security is held, because owning it and
    considering it are different questions rather than two systems. Below that
    fork the order is a single ladder with one exit at each rung, so no two
    conclusions can ever both be true.
    """
    if (ctx.get("position") or {}).get("held"):
        return _on_a_holding(ctx)
    return _on_a_candidate(ctx)


# -- a security you do not own ----------------------------------------------

ROOM_CITE = {"fact": "portfolio.slots_occupied", "comparator": "below",
             "threshold_from": "portfolio-slots", "group": SIZING_GROUP["id"]}


def _dimension(ctx, group, rows):
    """One question about the business: its citations, and whether the rows
    under it answer it.

    The three outcomes are the same three a single test has, reached the same
    way. `met` is the requirement satisfied. `settled_no` is the requirement
    out of reach even if every unreadable row came back a pass. Neither means
    undecided, and undecided is neither a purchase nor a refusal.

    How many rows a group needs is read from the group's own declaration, so
    this cannot demand a number different from the one the host will count
    against when it works out the rollup the reader sees.
    """
    cites, out = _screen(ctx, rows, group["id"])
    passed, unknown = out.count(PASS), out.count(UNKNOWN)
    if group["requires"] == "all":
        need = len(rows)
    else:
        need = (ctx.get("values") or {}).get(group["threshold_from"])
    ok = isinstance(need, int) and not isinstance(need, bool)
    return {
        "group": group, "cites": cites, "need": need,
        "passed": passed, "unknown": unknown, "tested": len(rows),
        "settled_no": ok and passed + unknown < need,
        "met": ok and passed >= need,
    }


def _entry_screen(ctx):
    """Every entry test, and what the host made of each.

    Returned as one object because every caller wants the same questions
    answered — did a knockout fail, is any question short, was anything
    unreadable, and what should be cited — and a holding asks them in exactly
    the same way a candidate does. An add is the same claim about the same
    company made again, and the only honest way to make it is against the same
    bar.
    """
    req_cites, req_out = _screen(ctx, REQUIRED, KNOCKOUTS["id"])
    dims = [_dimension(ctx, g, rows) for g, rows in DIMENSIONS]
    bonus_cites, _bonus_out = _screen(ctx, BONUS, BONUS_GROUP["id"])
    short = [d for d in dims if d["settled_no"]]
    return {
        "req_fail": req_out.count(FAIL),
        "req_unknown": req_out.count(UNKNOWN),
        "dims": dims,
        "short": short,
        "passed": sum(d["passed"] for d in dims),
        "tested": sum(d["tested"] for d in dims),
        "unknown": sum(d["unknown"] for d in dims),
        "settled_no": req_out.count(FAIL) > 0 or bool(short),
        "met": (req_out.count(UNKNOWN) == 0 and all(d["met"] for d in dims)),
        "evidence": (req_cites
                     + [c for d in dims for c in d["cites"]] + bonus_cites),
        "groups": ([KNOCKOUTS] + [g for g, _ in DIMENSIONS] + [BONUS_GROUP]),
    }


def _names_of(dims) -> str:
    """The groups named in a sentence, lower-cased the way they read mid-line
    rather than as headings."""
    names = [d["group"]["name"][0].lower() + d["group"]["name"][1:]
             for d in dims]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _covered(screen) -> str:
    return (f'{screen["passed"]} of the {screen["tested"]} tests behind them '
            "passed")


def _on_a_candidate(ctx):
    values = ctx.get("values") or {}

    # First rung, before anything about price or growth, and it has to be
    # first: when this fires the growth rate is usually absent, which would
    # otherwise walk the ladder down to "not enough to go on" and tell the
    # reader nothing. Nothing else is cited here — a reader whose company has
    # been named a turnaround does not need fourteen rows about a rate that
    # does not exist.
    base_cites, appeared = _base(ctx)
    if appeared:
        return {
            "state": "not-established-as-a-grower", "payload": {},
            "reason": {
                "rule": "earnings-appeared-rather-than-grew",
                "summary": (
                    "At the start of the window this strategy measures growth "
                    "over, this company was earning almost nothing, and "
                    "almost nothing per dollar of sales. Both together mean "
                    "the earnings did not grow so much as appear — a "
                    "turnaround or a margin recovering — and none of the "
                    "tests here were built to judge one."),
                "evidence": base_cites, "groups": [BASE_GROUP],
            },
        }

    screen = _entry_screen(ctx)
    evidence = base_cites + screen["evidence"]
    groups = [BASE_GROUP] + screen["groups"]

    # A knockout that failed, or a question about the business that cannot be
    # answered even if every unreadable row under it came back clear. Either
    # is a settled no.
    if screen["settled_no"]:
        return {
            "state": "not-growth-at-this-price", "payload": {},
            "reason": {
                "rule": ("knockout-failed" if screen["req_fail"]
                         else "question-short"),
                "summary": (
                    f'{screen["req_fail"]} of the {len(REQUIRED)} tests this '
                    "strategy will not bend came back against it, and one is "
                    "enough."
                    if screen["req_fail"] else
                    "This strategy asks four separate questions about a "
                    "company and needs a yes to every one. "
                    + ("One has come back no"
                       if len(screen["short"]) == 1
                       else f'{len(screen["short"])} have come back no')
                    + ": " + _names_of(screen["short"])
                    + f'. Across all four, {_covered(screen)}, and no amount '
                      "of passing elsewhere turns a no into a yes."),
                "evidence": evidence, "groups": groups,
            },
        }

    if not screen["met"]:
        missing = screen["req_unknown"] + screen["unknown"]
        return {
            "state": "cannot-screen", "payload": {},
            "reason": {
                "rule": "screen-incomplete",
                "summary": (
                    f"{missing} of the tests that decide this could not be "
                    "worked out from the data on record, and the ones that "
                    "could do not settle it either way."),
                "evidence": evidence, "groups": groups,
            },
        }

    slots = values.get("portfolio-slots")
    evidence = evidence + [ROOM_CITE]
    groups = groups + [SIZING_GROUP]

    if contract.test(ctx, ROOM_CITE) == FAIL:
        return {
            "state": "no-room", "payload": {},
            "reason": {
                "rule": "at-capacity",
                "summary": (
                    f"It passes every test, and all {slots} of the places "
                    "this strategy runs are taken. Nothing here swaps one "
                    "holding for another — a place opens when one of your "
                    "positions closes."),
                "evidence": evidence, "groups": groups,
            },
        }

    # Both settings ship a default, are typed, and are bounded away from zero
    # by the declaration; a journal override that broke either is refused
    # before decide() is ever called.
    size, bound = _first_purchase_size(values)
    evidence = evidence + _sizing_cites(SIZING_GROUP["id"]) + [
        {"label": "Size this buy", "unit": "percent", "actual": size,
         "group": SIZING_GROUP["id"]}]
    return {
        "state": "worth-buying",
        "payload": {"size": {"unit": "weight", "value": size},
                    "condition": None,
                    # Nothing is staged. Buying a growing company in thirds
                    # against a falling price is a rule this strategy does not
                    # have, and inventing one here so a screen had something
                    # to render would be putting a recommendation into shipped
                    # content.
                    "plan": None},
        "reason": {
            "rule": "growth-not-yet-paid-for",
            "summary": (
                f"All {len(REQUIRED)} tests this strategy will not bend "
                "passed, and all four questions about the company are "
                f"answered — {_covered(screen)}. The size is {size:g}% of the "
                f"account, set by {bound}."),
            "evidence": evidence, "groups": groups,
        },
    }


# -- sizing ------------------------------------------------------------------
#
# A FIRST purchase takes an equal share of the places this strategy runs — one
# eighth of the account across eight names. An ADD goes toward the cap, which
# is twice that.
#
# The gap between the two is smaller than the Buffett strategy's by a long way
# and larger than Graham's, which is the whole of what "sizing differs between
# these three" means in practice. This method expects one or two of its names
# to become very large by rising; it does not expect any of them to be bought
# large.
#
# Nothing about what the position cost is available to either. The host does
# not offer it, so a rule that put more money in because the price had fallen
# below what you paid cannot be written here — and that rule is the failure
# mode this whole screen was built against.

def _sizing_cites(group):
    return [{"value": "portfolio-slots", "group": group},
            {"value": "position-weight-cap", "group": group}]


def _first_purchase_size(values):
    """(the share of the account a first purchase takes, what set it)."""
    equal_share = round(100.0 / values["portfolio-slots"], 2)
    cap = float(values["position-weight-cap"])
    return (min(equal_share, cap),
            "an equal share of your places" if equal_share <= cap
            else "the cap on any one name")


# -- a security you own ------------------------------------------------------

TIME_CITES = ({"fact": "position.opened", "group": TIME_GROUP["id"]},
              {"fact": "position.months_held", "group": TIME_GROUP["id"]},
              {**GROWTH_DRIFT, "group": TIME_GROUP["id"]})


def _on_a_holding(ctx):
    values = ctx.get("values") or {}
    states = _exit_states(ctx, DECAY_GROUP["id"])

    evidence = _exit_evidence(DECAY_GROUP["id"], states) + list(TIME_CITES)
    groups = [DECAY_GROUP, TIME_GROUP]

    fired = [i for i, f in enumerate(states)
             if f["confirmation"] == CONFIRMED]
    waiting = [f for f in states if f["confirmation"] == BREACHED]

    def also_waiting():
        """A closing verdict still has to account for every red row on the
        screen. An exit that fired and an exit still one reading short both
        render as a failed test, and a summary that counted only the first
        leaves the reader to work out why the numbers disagree."""
        if not waiting:
            return ""
        return (f" {len(waiting)} more "
                + ("has" if len(waiting) == 1 else "have")
                + " been crossed on this reading without being confirmed "
                "yet, and did not decide this.")

    def closing(state, rule, summary, rests_on=()):
        """`rests_on` names the exits this state is actually built on.

        Every closing verdict cites all seven, because a reader looking at
        one wants the whole picture — which means the rows alone cannot say
        which of them decided it, and a verdict still one reading short of
        confirmation renders exactly the same rows. That difference is the
        entire point of a confirmation rule, so it is stated rather than left
        to be inferred.

        Named by id, never in words. This file used to carry a clause per
        measure it might mention, with a fallback that printed the raw bank id
        into the sentence telling somebody to sell; the host resolves each
        label now, in the words every row under this verdict already uses.
        """
        reason = {"rule": rule, "summary": summary + also_waiting(),
                  "evidence": evidence, "groups": groups}
        if rests_on:
            reason["rests_on"] = [EXITS[i][0] for i in rests_on]
        return {"state": state, "payload": {"when": ctx["today"]},
                "reason": reason}

    # The ladder, and the order is an argument. Solvency first, because it is
    # the only one of the three that can take the company away rather than the
    # return; then the growth, which is the reason the position existed; then
    # the price, which is the position having worked. All three are cited
    # whichever fires, so a reader sees the whole picture and the state says
    # which part of it decided.
    broke = [i for i in fired if i in STORY_EXITS]
    if broke:
        return closing(
            "story-broke", "exit-confirmed",
            ("A company bought for its growth has to survive long enough to "
             "do the growing, and one of the things that would stop it has "
             "gone wrong and stayed wrong across more than one set of "
             "filings."
             if len(broke) == 1 else
             "A company bought for its growth has to survive long enough to "
             "do the growing, and " + str(len(broke)) + " of the things that "
             "would stop it have gone wrong and stayed wrong.")
            + _confirmed_on([states[i] for i in broke]) + ".",
            rests_on=broke)

    if GROWTH_EXIT in fired:
        return closing(
            "growth-stopped", "growth-exit-confirmed",
            "Earnings per share over the last twelve months have stopped "
            "growing fast enough to hold this position, on more than one set "
            "of filings, and sales over the same two windows agree. The "
            "reason to own this was that it was growing. It is not.",
            rests_on=[GROWTH_EXIT])

    if PRICE_EXIT in fired:
        return closing(
            "price-ran-ahead", "price-exit-confirmed",
            "What this company costs against how fast it is growing has "
            "reached the level that closes the position, on more than one set "
            "of filings. Nothing about the business has broken — the price "
            "has simply been paid in advance, and the years of return still "
            "ahead of you are in it already.",
            rests_on=[PRICE_EXIT])

    if waiting:
        return {
            "state": "one-reading-past", "payload": {},
            "reason": {
                "rule": "breach-awaiting-confirmation",
                "summary": (
                    f"{len(waiting)} exit level "
                    + ("has" if len(waiting) == 1 else "have")
                    + " been crossed on the current reading and "
                    + ("has" if len(waiting) == 1 else "have")
                    + " not yet been crossed on enough consecutive "
                    + _waiting_unit(waiting)
                    + " to act on. Nothing is owed from you today."),
                "evidence": evidence, "groups": groups,
            },
        }

    checked = [f for f in states if f["confirmation"] != UNREADABLE]
    if not checked:
        return {
            "state": "cannot-watch", "payload": {},
            "reason": {
                "rule": "no-exit-test-could-run",
                "summary": (
                    f"Not one of the {len(EXITS)} exit tests could be worked "
                    "out from the data on record, so this strategy has "
                    "nothing to say about whether to stay."),
                "evidence": evidence, "groups": groups,
            },
        }

    unread = len(states) - len(checked)
    held = (ctx.get("position") or {}).get("months_held")
    clear = ("All " + str(len(checked)) + " exit tests that could be run came "
             "back clear"
             + (f", {unread} could not be worked out and "
                + ("is" if unread == 1 else "are")
                + " listed below as unknown rather than as passing,"
                if unread else "")
             + (f" and you have held this {held} months."
                if isinstance(held, int) else
                " and how long you have held this could not be worked out."))
    # A compound exit with one half failed reads as a red row beside a
    # sentence saying everything came back clear, and both are true.
    held_by_sales = _sales_held_it(ctx, DECAY_GROUP["id"], states)
    if held_by_sales:
        clear = f"{clear} {held_by_sales}"
    return _more_money(ctx, values, evidence, groups, clear)


# -- may more money go into a name you already own ---------------------------

def _more_money(ctx, values, evidence, groups, clear):
    """Reached only when nothing above it fired: every exit that could be read
    came back clear.

    So this asks one question, and it is deliberately not "is this a good
    idea" — it is "would this strategy buy this today, and is there room".
    """
    weight = ((ctx.get("position") or {}).get("weight")) or {}

    def held(rule, summary, extra=(), more_groups=()):
        return {"state": "hold", "payload": {},
                "reason": {"rule": rule, "summary": f"{clear} {summary}",
                           "evidence": evidence + list(extra),
                           "groups": groups + list(more_groups)}}

    # Every figure below is derived from the position's weight, so a weight
    # nobody could work out is not a small gap — it is the whole question
    # unanswerable.
    if weight.get("status") != "known":
        return held(
            "size-unreadable",
            "Whether there is room for more of it could not be worked out: "
            + str(weight.get("reason") or "this holding has no weight on "
                                          "record") + ".")

    cap = float(values["position-weight-cap"])
    room = round(cap - float(weight["value"]), 2)
    # The weight itself, cited and not merely spoken about — and cited as an
    # observation rather than as a test. A row reading "at most your 25%"
    # beside a holding at 31% would render as a failure, and a reader would
    # reasonably take a failed row about position size to mean something is
    # owed. Nothing is: this strategy has no trim, the cap binds on purchases
    # only, and a group demanding a pass here would refuse every add on a
    # position that had done well.
    sizing = _sizing_cites(SIZING_GROUP["id"]) + [
        {"fact": "position.weight", "group": SIZING_GROUP["id"]},
        {"label": "Room left under your cap", "unit": "percent",
         "actual": room, "group": SIZING_GROUP["id"]}]

    if room <= 0:
        return held(
            "no-room-to-add",
            f"It is already {float(weight['value']):.1f}% of the account, "
            f"against the {cap:g}% most this strategy will take one name to "
            "by buying, so no more money goes into it here. Nothing is being "
            "trimmed — this strategy has no trim, and a position that has "
            "grown large by rising is what it is trying to produce.",
            sizing, [SIZING_GROUP])

    base_cites, appeared = _base(ctx)
    if appeared:
        return held(
            "no-longer-establishes-a-grower",
            "Its record no longer establishes a company that grew: the "
            "earnings at the base of the window this strategy measures over "
            "have become almost nothing beside what it earns now, and so has "
            "the margin on them. Nothing more goes in on a growth rate that "
            "is measuring a recovery. Holding what you have is a different "
            "question, and every exit test above came back clear.",
            base_cites + sizing, [BASE_GROUP, SIZING_GROUP])

    screen = _entry_screen(ctx)
    body = (base_cites + screen["evidence"] + sizing,
            [BASE_GROUP] + screen["groups"] + [SIZING_GROUP])

    if screen["settled_no"]:
        return held(
            "would-not-buy-it-today",
            "Your rules would not buy this today: "
            + (f"{screen['req_fail']} of the {len(REQUIRED)} tests this "
               "strategy will not bend came back against it"
               if screen["req_fail"] else
               _names_of(screen["short"])
               + (" has come back no" if len(screen["short"]) == 1
                  else " have come back no"))
            + f", and {_covered(screen)}. Holding what you have is a "
            "different question, and every exit test above came back clear — "
            "a company that has stopped being cheap enough to buy again has "
            "not yet run far enough ahead of its growth to be sold.",
            *body)

    if not screen["met"]:
        missing = screen["req_unknown"] + screen["unknown"]
        return held(
            "screen-unreadable",
            "Whether your rules would buy this today could not be settled: "
            f"{missing} of the tests that decide it could not be worked out "
            "from the data on record. Nothing more goes in on a screen that "
            "did not finish — an unreadable test is not a passing one.",
            *body)

    return {
        "state": "room-for-more",
        "payload": {"size": {"unit": "weight", "value": room},
                    "condition": None, "plan": None},
        "reason": {
            "rule": "still-a-buy-and-has-room",
            "summary": (
                f"{clear} It would still be bought at today's price — every "
                f"question about the company answered, {_covered(screen)} — "
                f"and it sits {room:.1f}% of the account below the {cap:g}% "
                "most this strategy will take one name to. That room is the "
                "whole of what may go in; where it goes is a question about "
                "your other holdings, not about this one."),
            "evidence": base_cites + evidence + screen["evidence"] + sizing,
            "groups": [BASE_GROUP] + groups + screen["groups"]
                      + [SIZING_GROUP]},
    }
