"""Buffett — a wonderful business at a sane price, held until it stops being
wonderful.

The opposite claim from Graham's, made about the opposite kind of company.
Graham buys an ordinary business so far below what its assets justify that
the quality stops mattering, and sells when the gap closes. This buys a
business good enough that the gap is never the reason to own it, and sells
only when the business itself breaks.

Four things follow, and they are the whole shape of this file.

**Nothing about price can end a position here.** Five of the fifteen entry
tests can force an exit and not one of them is a valuation measure — they are
returns, leverage, coverage, cash flow and share count. That is intended and
it is the sharpest disagreement in investing. A business compounding at 18% a
year will look expensive for most of the twenty years you should own it, and
a rule that sold on price would destroy the return while appearing to work.
Graham fills that field in; this leaves it empty on purpose. Neither is a
compromise, there is no number in between that either side would sign, and
that is why they are separate strategies and separate journals.

**There is no clock, and there is no trim.** No holding period, so nothing
closes a position for having been owned a long time. And no state anywhere in
this file reduces a position: a holding that has quadrupled and become half
the account is left alone, because selling a wonderful business for having
got large is the same mistake as selling it for having got expensive. The
size rules here bind on the way in and never on the way out, which is a
genuine limitation to state rather than a gap to fill — see
`position-weight-cap`.

**Most of what this strategy is cannot be measured.** Whether a moat holds
for another decade, whether management has told the truth when the news was
bad, whether spare cash has gone somewhere worth more than paying it out:
none of it is in a filing, all of it decides more than any ratio here, and
all three are questions the reader answers themselves. The numbers are asked
first and the questions only once the numbers pass — nobody should be
assessing the durability of a business their own rules have already rejected.
Unanswered is never a pass. It produces a verdict that says a decision is
owed, and every question it names is answerable on the same screen that
reports it.

**It does not evaluate lenders, insurers or property companies — for now.**
See DECLINES. Unlike Graham's refusal, this one is a gap in the host rather
than a boundary of the method: Buffett has plenty to say about banks, and
what is missing is measures built for them. All three tests here that cannot
be bent are category errors on a lender, and one of them — owner earnings —
does not come back grey but large, because a shrinking bank throws off the
most cash from operations there is.

**The dominant state is "nothing to do", for years at a time.** That is the
strategy working. A wonderful business bought once and held for a decade
without a single add — because the entry test stopped passing long ago while
nothing ever broke — is the ordinary case here, not a failure to have an
opinion. What changes underneath a hold that stays the same is the reason for
it, and the rule named beside the verdict says which of the several reasons
is today's.

Sources, and which is which, because a reader auditing a number later has to
be able to tell. Every value carries its own `source` saying so, which is
where to look rather than here.

There are now four of them, where there used to be two, and that is the
first thing to know before checking any number here.

Sixteen of the twenty-eight thresholds below are the expert report's, at the
level it states.

Seven are the second expert review's. That review read the report and
disputed it in every profile, and where it did, this strategy follows the
review and each of those values says so in its own words — what the level
was, what it is, and what the argument was. None of them moved quietly, and
the changelog for version 5 is the same account in one place. They are the
most interesting numbers in this file to argue with, because they are the
ones where two sources disagreed and this file picked.

Two come from Buffett's own documented practice — `portfolio-slots` and
`position-weight-cap` — because neither source was asked how much to buy. That
is the same gap Graham had, and the answer is a genuinely different one: this
strategy concentrates where Graham spreads, and the difference is the point
rather than an accident of tuning.

Three are nobody's but this file's author's, and they are the ones to look at
hardest. Two are how many of a pair of near-duplicate tests must pass, which
no source addresses because no source grouped the tests. The third is the
borrowing exit, which had to be given a level when the measure under it
changed and neither source states one for the replacement.

**One thing a reader should know about the provenance of every number here.**
The expert report itself is not in this repository. Its levels were taken
from `dev_reference_docs/legacy-profiles/buffett.yaml`, which states in its
own header that its values are written exactly as the report states them, and
whose README records that it exists to be checked against. So that chain is
one link longer than Graham's was, and it is a transcription rather than the
document. The review IS in this repository, at
`dev_reference_docs/ledger-default-profiles-addendum.md`, so the seven values
that follow it can be checked against the thing itself. Nothing here was
rounded, converted or adjusted at any step, and the one value written in a
different form from its source's says so in its own explanation.

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

# Knockout. One failure kills the buy regardless of everything else.
#
# Three, and the choice of which three is the whole thesis. Returns on
# capital say the business is good. Borrowing says it can survive being
# wrong. Owner earnings yield says you did not pay anything for it. Every
# other test here is evidence for one of those three.
REQUIRED = (
    ("roic_median_5y", "at_least", "min-roic"),
    ("total_debt_to_avg_fcf_5y", "at_most", "max-debt-to-fcf"),
    ("owner_earnings_yield_on_ev", "at_least", "min-owner-earnings-yield"),
)

# ---------------------------------------------------------------------------
# The rest of the entry tests, gathered by WHAT THEY MEASURE.
#
# This replaced a single list of nine where seven had to pass, and the
# replacement is the most consequential change in this file. A count assumes
# its members are independent evidence and these are nothing of the kind.
# Cash flow margin and cash conversion are two readings of the same cash.
# Revenue growth and the profit-growth spread share a numerator. Under one
# quota a company cleared seven of nine by being superb at one thing measured
# four ways while being weak on borrowing and on dilution — and the arithmetic
# was biased that way systematically, in the direction of buying.
#
# So the demand is coverage rather than a total. Each group below is one
# question about the business, every group has to be satisfied, and no
# group's passes can be spent on another's. Being excellent at cash
# generation no longer pays for a balance sheet nobody looked at.
#
# Within a group the rule follows from whether the members are substitutes:
#
#   all       the members measure genuinely different things, so passing one
#             says little about the other and both are owed.
#   at_least  the members are near-readings of one another. Requiring both
#             double-counts and requiring one is the coverage statement. How
#             many is a declared value, because loosening it is a real
#             loosening and belongs on the rule-change record.
#
# The bar in total is eight of these ten rather than the seven of nine it
# replaced — but the count is not the point and is very nearly a
# coincidence. What changed is that the eight cannot all come from one
# corner of the business.
# ---------------------------------------------------------------------------

RETURNS = (
    ("incremental_roic_5y", "at_least", "min-incremental-roic"),
)

LEVERAGE = (
    ("interest_coverage", "at_least", "min-interest-coverage"),
    ("roe_minus_roic_gap_5y", "at_most", "max-roe-roic-gap"),
)

CASH = (
    ("fcf_margin_median_5y", "at_least", "min-fcf-margin"),
    ("cash_conversion_median_5y", "at_least", "min-cash-conversion"),
)

GROWTH = (
    ("revenue_cagr_5y", "at_least", "min-revenue-cagr"),
    ("ni_minus_revenue_cagr_spread_5y", "at_least",
     "min-profit-growth-spread"),
)

PRICING = (
    ("gross_margin_range_relative_5y", "at_most", "max-gross-margin-swing"),
)

ALLOCATION = (
    ("diluted_share_count_change_5y", "at_most", "max-share-count-change"),
    ("goodwill_impairment_to_equity_5y", "at_most", "max-goodwill-written-off"),
)

# Never block. They are reported so the reader can see them and stop there.
#
# Four rows for three tests: the report states the tax check as a band, and
# a band is two comparisons. There is no `between` in the host's comparison
# vocabulary and this strategy does not want one — two rows say which end
# was missed, and one row could only say that something was.
#
# Debt against EBITDA is here and is the one row worth explaining. It used to
# be a knockout, and a knockout is the last place it belonged: Munger's
# position on EBITDA is that the phrase should be read as a synonym for
# fictitious earnings, and Buffett has written repeatedly that depreciation is
# a real expense. A measure this strategy's own sources have attacked in
# public cannot sit at the tier that overrules everything else in it. What it
# is still good for is comparison — it is the number credit ratings speak, so
# a reader who wants to know how a lender sees this balance sheet can look at
# it here, where it decides nothing.
BONUS = (
    ("total_debt_to_ebitda", "at_most", "max-debt-to-ebitda"),
    ("effective_tax_rate_median_5y", "at_least", "min-effective-tax-rate"),
    ("effective_tax_rate_median_5y", "at_most", "max-effective-tax-rate"),
    ("current_ratio", "at_least", "min-current-ratio"),
    ("payout_to_fcf_median_5y", "at_most", "max-payout-to-fcf"),
)

# The questions no filing answers, and the three that decide most of this.
#
# Cited as an ordinary measure, because that is what they are to the host: a
# yes/no the reader assessed, absent until they do. Nothing here can present
# one as something the tool worked out — the host decides that from the bank
# and never from this file.
#
# The limit is stated rather than named, and it is the only stated limit in
# this file. "It has to be a pass" is not a level anybody could retune to
# something else, so there is no setting for it to come out of.
QUALITATIVE = ("moat_durability", "management_integrity", "capital_allocation")

# The exits. Written as what the holding must KEEP being true, not as the
# condition that ends it, so a healthy holding reads as passes and a breach
# is the one row that is not.
#
# Nothing here says how much evidence a breach needs, and there used to be a
# fourth column naming a setting that did. It is a property of the measure —
# of how far one filing can move a five-year median against how far it can
# move a single balance-sheet date — and the host derives it from what the
# metric bank declares. See contract.ESTIMATORS.
#
# Two of these five changed when it moved. Returns on capital are a five-year
# median: one year cannot move a median past the observation next to it, the
# window already did the smoothing a second reading was being asked for, and
# a second reading re-reads four of the same five years. That exit now acts
# on the reading in front of you. And the share count is a change between two
# single years, which is not a long-window measure however many years it
# spans; it takes one filing rather than two.
#
# Free cash flow is the one worth arguing with, and it is set out in the
# changelog: the report gives it four quarters and it now takes two filings.
#
# The borrowing exit moved with the entry test it belongs to. A strategy that
# refuses to BUY on debt against EBITDA, on the grounds that the measure adds
# back a real expense, cannot coherently SELL on it — and selling is the more
# consequential of the two. See `exit-debt-to-fcf`, which is the one level in
# this file with no source behind it.
EXITS = (
    ("roic_median_5y", "at_least", "exit-roic-level"),
    ("total_debt_to_avg_fcf_5y", "at_most", "exit-debt-to-fcf"),
    ("interest_coverage", "at_least", "exit-interest-coverage"),
    ("fcf_margin_ttm", "at_least", "exit-fcf-margin"),
    ("diluted_share_count_change_3y", "at_most", "exit-share-count-change"),
)

# The index of the return-on-capital exit inside EXITS. It is the one that is
# half of a compound test rather than a test on its own — see _roic_exit.
ROIC = 0

# The other half of that compound: how far returns have fallen since the day
# this holding began, as a share of what they were then rather than as a
# number of points.
#
# The proportion is the whole reason this row exists in this form, and it is
# the one thing this strategy needed from the host that the host did not
# already do. A third off a business earning 45% is fifteen points and an
# ordinary couple of years; a third off one earning 15% is five points and
# most of the reason you owned it. One tolerance in points cannot say the
# same thing to both, and the report's rule is a claim about proportion. See
# contract.CHANGE_FORMS.
#
# Anchored to the FIRST purchase and not the last, against the host's own
# general advice, and the exception is deliberate. The host warns that a
# deterioration rule anchored to the first purchase can fire on a decline you
# consciously re-underwrote — true, and the cost is real. But this rule is
# specifically about the multi-year leak: a moat that gave way over a decade,
# never in any one year enough to notice. Anchored to the last purchase, a
# holder who added along the way would re-underwrite that decay away one
# purchase at a time and the rule could never fire at all, which is the exact
# failure it exists to catch.
#
# `above` and not `at_least`, and the difference is one tick at the boundary.
# The source states this exit as "falls by at least 33%", so a fall of exactly
# a third fires it. What the holding must keep being true is therefore that it
# has NOT fallen that far — a change strictly above -33 — and `at_least` would
# let the exact case through. Every other exit in this file lands the same way
# round against its own comparator; this is the only one where the source
# states the level as a magnitude and the direction in prose, which is exactly
# where a boundary goes quietly wrong.
ROIC_DRIFT = {"measure": "roic_median_5y", "since": "first-purchase",
              "change": "proportion", "comparator": "above",
              "threshold_from": "exit-roic-fall"}


# ---------------------------------------------------------------------------
# The headings the evidence is gathered under, and what each demands.
#
# The grouping IS the rollup, and it is also the correction. Three knockouts
# where every one has to pass, then six questions about the business where
# every question has to be answered — some by all of their rows and some by
# enough of them — then five reported and never blocking, then three the
# reader answers themselves. The host counts every one of those from the rows
# it resolved rather than from a tally this file kept.
#
# The reason a reader can trust that "each group must be satisfied" is a rule
# and not a habit: the host refuses a state whose render is `commit` when any
# group that stated a requirement did not come out passed. So there is no
# path through this file that buys something with a dimension unmet, whatever
# the ladder below does.
# ---------------------------------------------------------------------------

KNOCKOUTS = {"id": "knockouts", "name": "Tests this strategy will not bend",
             "requires": "all"}

RETURNS_GROUP = {"id": "returns", "name": "What the money it keeps earns",
                 "requires": "all"}
LEVERAGE_GROUP = {"id": "leverage",
                  "name": "What it owes, and what its returns rest on",
                  "requires": "all"}
CASH_GROUP = {"id": "cash", "name": "Whether the profits are cash",
              "requires": "at_least",
              "threshold_from": "cash-tests-required"}
GROWTH_GROUP = {"id": "growth", "name": "Whether it is still growing",
                "requires": "at_least",
                "threshold_from": "growth-tests-required"}
PRICING_GROUP = {"id": "pricing", "name": "Whether it sets its own prices",
                 "requires": "all"}
ALLOCATION_GROUP = {"id": "allocation",
                    "name": "What management does with the money",
                    "requires": "all"}

# In the order they are asked, which is the order they are cited and drawn.
# Returns first because it is what this strategy is for; borrowing second
# because it is what ends positions; allocation last because it is the
# closest of them to the three questions no filing answers.
DIMENSIONS = (
    (RETURNS_GROUP, RETURNS),
    (LEVERAGE_GROUP, LEVERAGE),
    (CASH_GROUP, CASH),
    (GROWTH_GROUP, GROWTH),
    (PRICING_GROUP, PRICING),
    (ALLOCATION_GROUP, ALLOCATION),
)

BONUS_GROUP = {"id": "bonus", "name": "Reported, never blocking",
               "requires": "noted"}

# `all`, and that is load-bearing rather than decorative. A state whose
# render is `commit` is refused by the host when a group it declared did not
# come out passed — and an unreadable row is not good enough there either. So
# "no money goes in without all three of these answered, and answered yes" is
# enforced by the contract rather than by this file remembering to check.
# The branches below reach a state that explains itself first; the group is
# what makes the wrong answer unrepresentable if they ever stop.
QUALITY_GROUP = {"id": "quality", "name": "What only you can answer",
                 "requires": "all"}

SIZING_GROUP = {"id": "sizing", "name": "Room in the list, and how much",
                "requires": "all"}

# The exits demand nothing of a single reading — that is the confirmation
# rule, and it counts filings, which the host cannot express. So the group is
# `noted`: the host reports how each came out and this strategy decides what
# a run of them means.
DECAY_GROUP = {"id": "decay", "name": "What would end this position",
               "requires": "noted"}

# Reported and never tested. A holding period that is not a rule still has a
# number, and on a strategy whose commonest verdict is the same word for
# years the one figure that visibly moves is how long you have held it.
TIME_GROUP = {"id": "time", "name": "How long you have owned it",
              "requires": "noted"}


# ---------------------------------------------------------------------------
# Where the numbers came from.
# ---------------------------------------------------------------------------

_REPORT = ("the expert report commissioned for this strategy, by way of the "
           "transcription of it kept at "
           "dev_reference_docs/legacy-profiles/buffett.yaml — the report "
           "itself is not in this repository, so that file is what a reader "
           "can check this against")

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
REVIEW_LEVEL_ONLY = {"name": REVIEW["name"], "reasoning": False}

# Nobody's but this file's. Neither source addresses how the tests should be
# gathered, and one exit level had to move when the measure under it did.
# These are the numbers here most worth arguing with, and the attribution is
# what makes that visible.
AUTHOR = {
    "name": "this strategy's own author. Neither the expert report nor the "
            "review that corrected it states this number, and none is "
            "claimed for it",
    "reasoning": True}

BUFFETT_PRACTICE = {
    "name": "Buffett's own documented practice — the 1993 Berkshire "
            "shareholder letter for the number of names, and the 1965 "
            "partnership letter for how large one may get. The expert report "
            "was scoped to selection and to exits and says nothing whatever "
            "about how much to buy, so its silence here is a gap in the "
            "source rather than a decision it made",
    "reasoning": True}


# ---------------------------------------------------------------------------
# The kinds of company this strategy does not evaluate yet, and why the "yet"
# is real here where it is not on Graham.
#
# Graham's refusal is permanent because his tests ARE the liquidation-oriented
# balance sheet. This one's is not. What this strategy believes — a business
# that earns high returns on the money put into it, protects them, and does
# not need much borrowing to do it — is a claim somebody can make about a bank
# and Buffett spent forty years making it. The obstruction is entirely in the
# measures: the ones here are built for a company that sells something, and
# every one of the three knockouts is a category error on a lender.
#
# Returns on invested capital divides by debt plus equity less cash, which for
# a bank is most of the funding it exists to deploy. Debt against EBITDA
# treats deposits as borrowing and strikes profit after the interest that IS
# the cost of the product. Owner earnings takes operating cash flow less
# maintenance capital spending — and a lender's operating cash flow moves with
# the period's change in loans and deposits, so a bank that is SHRINKING
# generates the most of it. That last one is the dangerous one, because it
# does not come back grey. It comes back large.
#
# The substitute is a real piece of work rather than a switch: returns on
# tangible common equity, the efficiency ratio, the net interest margin, the
# reserve against charge-offs, the funding mix. None of those exists in this
# host yet. Until they do, this refuses, because the alternative is not a
# rougher answer — it is a confident wrong one on the exact tests that decide
# whether money goes in.
#
# What is deliberately not refused: asset managers, exchanges and insurance
# brokers. Those are ordinary fee businesses, several of them are exactly what
# this strategy is looking for, and refusing everything financial-sounding
# would be refusing some of the best companies on the list.
DECLINES = [
    {"class": "depository-lending",
     "because": "Every one of the three tests this strategy will not bend is "
                "a category error on a lender. Returns on invested capital "
                "divides by borrowing plus equity, which for a bank is the "
                "funding it exists to lend out. Debt against operating "
                "profit counts deposits as borrowing and strikes the profit "
                "after the interest that is the cost of the product. And "
                "owner earnings starts from operating cash flow, which for a "
                "lender moves with the period's change in loans and deposits "
                "rather than with the business — a bank that is shrinking "
                "generates the most of it, which is a large confident number "
                "pointing the wrong way. This strategy has a real view about "
                "banks and no honest way to express it here yet; the "
                "measures it would need are not in this program."},
    {"class": "insurance",
     "because": "An insurer holds an investment portfolio against claims not "
                "yet made, so returns measured against its capital are "
                "measuring money that belongs to policyholders. Premiums "
                "arriving before claims are paid make cash from operations "
                "look like cash the business generated, when it is cash it "
                "is holding — which lands on the owner-earnings test, one of "
                "the three that decide a purchase here. Underwriting and "
                "investing are two businesses in one set of accounts and "
                "nothing in this program separates them."},
    {"class": "real-estate",
     "because": "Depreciation on buildings is an accounting convention "
                "rather than a cost being incurred, so reported profit "
                "understates by design and the return, margin and coverage "
                "tests all read a company that is doing better than they "
                "say. The industry's own figure adds it back; this program "
                "does not compute that figure. Borrowing is structural here "
                "too, so the leverage knockout refuses every property "
                "company for a reason that has nothing to do with the "
                "particular one in front of you."},
]


# What the METHOD asks for or admits to that this program does not do.
#
# Separate from DECLINES, which is about a kind of company these measures
# cannot read. This is about the method itself, and it is here because the
# alternative is silence — and silence on this particular point is not
# neutral, it is a promise nobody made.
LIMITS = [
    {"title": "It is a portfolio method, and this is one security",
     "body": "Everything in this strategy was worked out by somebody running "
             "a portfolio, and it carries an expected rate of losers that "
             "the good outcomes are meant to pay for. Buffett has been "
             "explicit about it: the record includes purchases that went "
             "nowhere and several he has named as mistakes, and the method "
             "is sound because the winners were held long enough to "
             "outweigh them — not because each judgement was right.\n\n"
             "**A verdict on this page is about one security, and no method "
             "here can tell you that one will work.** What a buy verdict "
             "says is that this security meets the standard you set while "
             "you were calm. It does not say the standard will be met by "
             "the outcome, and a strategy that passed every test can still "
             "be the one that costs you money.\n\n"
             "That is not an argument against the rules — it is what the "
             "rules are for. It is an argument against reading any one "
             "verdict as a forecast, and against judging the method by "
             "whichever position you happen to be looking at."},

    {"title": "Most of what decides this is not in any filing",
     "body": "Three of the tests here are questions you answer yourself, "
             "and by the reckoning of the person this strategy is named "
             "after they decide more than every ratio on the page put "
             "together. Whether a moat holds for another decade, whether "
             "management tells the truth when the news is bad, whether "
             "spare cash went somewhere worth more than paying it out: "
             "none of it is tagged in a filing and none of it is "
             "computable.\n\n"
             "So the numbers here are a filter and not a judgement. They "
             "are strong enough to rule things out — most companies fail "
             "them, and that is the intent — and they cannot rule anything "
             "in on their own. That is why an unanswered question blocks a "
             "purchase here rather than being read as agreement."},
]


STRATEGY = {
    "id": "buffett",
    "name": "Buffett",
    "summary": "Buys a business good enough to be worth owning for decades, "
               "and only at a price that leaves something on the table. "
               "Sells when the business breaks — never when the price gets "
               "high, and never because time has passed.",
    "version": 6,
    "contract": 8,
    "declines": DECLINES,
    "limits": LIMITS,
    "changelog": {
    6: "`exit-debt-to-fcf` NOW ASKS WHETHER ONE YEAR IS CARRYING THE BREACH. "
       "No level moved, and this exit is now HARDER to fire, not easier.\n\n"
       "The measure is debt at one balance-sheet date over five fiscal years "
       "of free cash flow averaged. The host classified it by its noisiest "
       "leg — the balance-sheet instant, which is right, and which is why it "
       "still takes two filings — and that also decided, silently, that no "
       "single year could be carrying it. It has a five-year window "
       "underneath, and one very bad year in it can push the ratio past this "
       "level on its own. The computation had been working out the "
       "year-dropped readings all along and nothing could ask for them.\n\n"
       "So a breach that clears when its worst year is dropped no longer "
       "ends the position; it waits, and says so. If you were relying on "
       "this exit acting on a single bad year, the honest place for that is "
       "the level: say what borrowing you will accept against normal cash "
       "generation. The other four exits are unchanged.",
        5: "A SECOND EXPERT REVIEW READ THE REPORT THIS STRATEGY WAS BUILT "
           "FROM AND DISPUTED IT. This version is that review's corrections, "
           "and it changes what this strategy will buy more than any version "
           "before it.\n\n"
           "THE NINE SECOND-TIER TESTS ARE NOW SIX QUESTIONS ABOUT THE "
           "BUSINESS, AND EVERY ONE HAS TO BE ANSWERED. Seven of nine had to "
           "pass before; the nine were treated as nine pieces of evidence and "
           "they were nothing of the kind. Cash flow margin and cash "
           "conversion are two readings of the same cash. Revenue growth and "
           "the profit-growth spread share a numerator. Returns on equity and "
           "returns on capital were both being tested as levels. So a company "
           "could clear seven of nine by being superb at one thing measured "
           "four ways while being weak on borrowing and on dilution — and the "
           "arithmetic was biased that way every time, in the direction of "
           "buying. Now each of returns, borrowing, cash, growth, pricing "
           "power and capital allocation must be satisfied on its own, and no "
           "group's passes can be spent on another's. Where two tests inside "
           "a group are near-duplicates, one of them is enough and how many "
           "is a setting. The bar in total is eight of ten rather than seven "
           "of nine, but the count was never the point.\n\n"
           "FIVE MEASURES CHANGED, EACH BECAUSE IT WAS MEASURING THE WRONG "
           "THING.\n\n"
           "Borrowing is held against five-year average free cash flow at "
           "3.0x rather than against EBITDA at 2.5x. EBITDA adds back "
           "depreciation, which is the cost of the equipment wearing out; "
           "Munger has said the term should be read as a synonym for "
           "fictitious earnings and Buffett has written repeatedly that "
           "depreciation is a real expense. A measure they attacked in public "
           "cannot sit at the tier that overrules everything else in their "
           "own strategy. The EBITDA version stays, reported and never "
           "blocking, at the level it always had, because it is what credit "
           "ratings speak. The EXIT moved with it, to 5.0x of free cash flow "
           "— and that level is this author's, with no source behind it, "
           "because neither source states one.\n\n"
           "Returns on equity is no longer tested as a level. What is tested "
           "is the GAP between it and returns on capital, at 10 points, "
           "because that gap is borrowing and the note beside the old test "
           "always said the divergence was the informative part.\n\n"
           "The gross margin swing is a share of the margin rather than a "
           "number of points — at most 15% of it, where it used to be at most "
           "six points. Six points on a 12% distributor is half its margin; "
           "six points on an 81% software company is nothing. The old limit "
           "called them identical.\n\n"
           "Goodwill on the balance sheet is no longer tested at all. What is "
           "tested is goodwill WRITTEN BACK OFF over five years, at 5% of the "
           "equity that existed before them. Buffett's own 1983 letter argues "
           "that the accounting entry measures economic goodwill badly, and "
           "the old test punished one good acquisition fifteen years ago; the "
           "new one asks whether the acquisitions worked.\n\n"
           "And the price test is held against what the whole business costs "
           "— shares and debts together — rather than against the shares "
           "alone, with the maintenance-spending estimate no longer counting "
           "the amortisation of acquired intangibles. Both make the figure "
           "smaller for the companies it was flattering. The 5% level did NOT "
           "move, so this test is now stricter for anything carrying net debt.\n\n"
           "ONE TEST IS NEW AND THE REVIEW CALLS IT THE MOST MATERIAL "
           "OMISSION: what the money the company KEEPS earns, at 15%. The "
           "five-year median says what the existing base earns and can sit at "
           "25% for years while every new dollar goes into something earning "
           "six. The increment is what sets the rate of compounding from "
           "here, and this strategy's whole thesis is that the compounding "
           "continues.\n\n"
           "The tax band moved from 10–35% to 12–28%. It was calibrated on a "
           "35% US statutory rate; after the 2017 act cut that to 21% the old "
           "ceiling sat a dozen points above anything it could ever have "
           "flagged, so it was not a lenient test but an absent one wearing a "
           "number.\n\n"
           "WHAT DID NOT CHANGE, and the reason is written down beside it: "
           "the 5% owner earnings yield does not move when interest rates do, "
           "while every absolute price level in the Graham strategy does. "
           "Coca-Cola was bought in 1988 at a 6.7% yield against a 9% "
           "Treasury — a negative spread — and any rule expressing this as "
           "\"beat the bond by so much\" would have refused it. See "
           "`min-owner-earnings-yield`.\n\n"
           "Expect more verdicts of \"not enough to go on\" than before. The "
           "new tests need eight fiscal years, and a question answered by one "
           "test is undecided the moment that test is unreadable, where a "
           "count of nine could absorb it. That is absence behaving "
           "correctly, and it is the price of asking each question "
           "separately.",
        4: "HOW MUCH EVIDENCE AN EXIT NEEDS IS NO LONGER A SETTING, AND TWO "
           "OF THE FIVE EXITS NOW ACT SOONER. No level moved.\n\n"
           "`sell-confirmation-filings` and `fcf-exit-quarters` are gone. "
           "They asked for a number of consecutive filings, and that number "
           "is now worked out from how each measure is read — because the "
           "five exits here are read three different ways and neither "
           "setting could tell them apart.\n\n"
           "RETURNS ON CAPITAL, the exit this strategy is really about, now "
           "acts on the reading in front of you. It is a five-year median: "
           "one year cannot move a median past the observation next to it, "
           "and the next filing's reading shares four of the same five "
           "years — so waiting for a second was waiting for the same data "
           "to be looked at again. Where the fall was real this now closes "
           "the position a quarter or two earlier; where it was not, the "
           "median never crossed the floor in the first place. THE SHARE "
           "COUNT takes one filing rather than two, for the opposite "
           "reason: a change between two single years is not a long-window "
           "measure however many years it spans, and the newest of those "
           "two is what the next filing replaces.\n\n"
           "AND FREE CASH FLOW TAKES TWO FILINGS RATHER THAN FOUR "
           "QUARTERS, which is a departure from the report and the one to "
           "argue with. The report's reasoning is that a single negative "
           "quarter is working-capital timing rather than news, and it is "
           "right — but the measure is already a trailing twelve months, so "
           "one quarter is a quarter of it before anything waits, and four "
           "consecutive readings of it span seven quarters of data to "
           "establish a condition about one year. Two filings is what a "
           "trailing window can be asked to confirm. If you were relying on "
           "the longer wait to sit through a deliberate investment cycle, "
           "the honest place for that is `exit-fcf-margin` — say what level "
           "of cash generation you will accept, rather than how long you "
           "will wait to believe the reading.\n\n"
           "Separately, growth rates are now measured between three-year "
           "averages at each end of the window rather than between single "
           "years. That changes `min-revenue-cagr` and the profit-growth "
           "spread from figures a one-off charge could swing by several "
           "points into figures it cannot, and it needs eight fiscal years "
           "of history where six did before — so both will be absent for "
           "some companies they used to answer for. Absent is not a fail, "
           "but it does mean two of the nine core tests cannot be counted "
           "towards the seven.",
        3: "THIS STRATEGY NO LONGER EVALUATES BANKS, LENDERS, INSURERS OR "
           "PROPERTY COMPANIES. No threshold moved and no test changed; "
           "three kinds of company now get a refusal instead of a "
           "verdict.\n\n"
           "All three tests this strategy will not bend are category errors "
           "on a lender, and the third one is worse than useless. Owner "
           "earnings starts from cash from operations — and for a bank that "
           "figure moves with the period's change in loans and deposits "
           "rather than with the business, so a bank that is shrinking "
           "produces the largest owner earnings of all. That is not a gap "
           "that renders as grey and gets ignored; it is a big confident "
           "number pointing the wrong way, on one of the three tests that "
           "decide whether money goes in. Returns on invested capital and "
           "debt against operating profit are wrong in quieter ways, both "
           "because a bank's borrowing is its raw material and its interest "
           "is its cost of goods.\n\n"
           "Unlike Graham's, this refusal is meant to be temporary. What "
           "this strategy believes is a claim somebody can make about a "
           "bank, and Buffett spent forty years making it. What is missing "
           "is the measures: returns on tangible common equity, the "
           "efficiency ratio, the net interest margin, the reserve against "
           "charge-offs. None of them exists in this program yet. When they "
           "do, this strategy gets a branch for lenders rather than a "
           "refusal — and that will be a version of its own, with its own "
           "thresholds and its own sources, not a quiet lifting of this "
           "one.\n\n"
           "Nothing recorded changes: past verdicts were written down when "
           "they were made and are never recomputed. Nothing is sold — a "
           "holding in one of these now reads 'outside these rules', which "
           "asks nothing of you. Asset managers, exchanges and insurance "
           "brokers are NOT refused: they are ordinary fee businesses and "
           "several are exactly what this strategy looks for.",
        2: "No threshold and no rule changed, and no verdict moves. The one "
           "state that stops and waits for you — the three questions — now "
           "says where it is answered, so the host puts a button on the "
           "verdict rather than the state's description having to tell you "
           "to scroll. It was the strategy's own prose holding that up "
           "before, which meant it held only as long as somebody remembered "
           "to write it.",
        1: "First version. The fifteen entry tests, the three-knockout / "
           "seven-of-nine rollup, and the five exits with two-filing "
           "confirmation — four quarters for free cash flow — all as stated "
           "in the expert report. The three questions the filings cannot "
           "answer are asked once the numbers pass, and an unanswered one "
           "blocks a purchase rather than being read as a pass. Sizing by "
           "name count and position cap, attributed to Buffett's own "
           "documented practice because the report does not cover it. No "
           "holding period and no trim: nothing here closes or reduces a "
           "position for the price having risen or for time having passed.",
    },

    # -----------------------------------------------------------------
    # Twelve states, and the shape of the list is itself a claim.
    #
    # There is no state here that reduces a position. That is not an
    # omission to be filled in a later version — it is what this strategy
    # believes, and leaving the state undeclared is the only way to say so
    # that a reader can check. A strategy that declared a trim and never
    # reached it would look identical on the screen that lists what a
    # journal can say.
    # -----------------------------------------------------------------
    "states": [
        {"id": "wonderful-and-priced", "render": "commit",
         "name": "Worth owning, at this price",
         "description": "Every test this strategy will not bend has passed, "
                        "enough of the rest have, and you have answered the "
                        "three questions no filing can answer with a yes.\n\n"
                        "That is a claim about the business first and the "
                        "price second: this strategy is not looking for a "
                        "bargain, it is looking for a company worth owning "
                        "for a decade that is not being sold at a silly "
                        "price. The size is an equal share of the names this "
                        "strategy runs at once."},

        {"id": "judgement-owed", "render": "blocked",
         # The one state here that stops rather than answers, so it is the
         # one that has to say where it is un-stopped. The host reads this
         # and puts the button on the verdict; the description below says the
         # same thing in words for a reader who is not clicking anything.
         "fix": "judgement",
         "name": "Three questions only you can answer",
         "description": "The numbers pass. What decides this now is not in "
                        "any filing — whether the moat holds, whether "
                        "management can be taken at their word, whether "
                        "spare cash has gone somewhere worth more than "
                        "paying it out.\n\n"
                        "Those are yours to answer, in your own words, and "
                        "they are listed under \"Your judgement\" further "
                        "down this page. Leaving one blank is not a fail and "
                        "is not held against the company — it is simply not "
                        "an answer, and this strategy will not put money "
                        "behind a question nobody asked."},

        {"id": "you-marked-it-down", "render": "hold",
         "name": "You said no to it",
         "description": "The numbers pass and your own assessment does not. "
                        "One of the three questions this strategy asks came "
                        "back a fail, with your reasoning beside it.\n\n"
                        "Nothing here overrides that, and nothing here "
                        "argues with it. If you have changed your mind, "
                        "reassess it — the old answer is kept and the new "
                        "one goes above it, so a change of mind is visible "
                        "rather than silent."},

        {"id": "not-wonderful-enough", "render": "hold",
         "name": "Not a business this buys",
         "description": "At least one test this strategy cannot bend has "
                        "failed, or too many of the rest have. Read which "
                        "below.\n\n"
                        "Most companies fail this list and that is the "
                        "intent: it is looking for a business that earns "
                        "high returns on the money put into it, year after "
                        "year, without much borrowing. A failure here is "
                        "usually not a bad company — it is an ordinary one."},

        {"id": "cannot-screen", "render": "unknown",
         "name": "Not enough to go on",
         "description": "Some of the figures this strategy needs are "
                        "missing, and the ones that are present do not "
                        "settle it either way. A missing number is not a "
                        "pass and it is not a failure, so nothing is "
                        "claimed. The reasons below say which figures are "
                        "absent and why."},

        {"id": "no-room", "render": "hold",
         "name": "No room for it",
         "description": "It passes, and you already hold as many names as "
                        "this strategy runs at once. This is not a verdict "
                        "against the company — it is a fact about your list, "
                        "and it changes the day one of your holdings "
                        "closes.\n\n"
                        "This strategy runs a short list on purpose. Holding "
                        "more names than you can follow properly is the "
                        "thing it is trying to avoid, so it will not talk "
                        "you into room that is not there."},

        {"id": "hold", "render": "hold",
         "name": "Nothing to do",
         "description": "You own it, every test that could be run came back "
                        "clear, and nothing about the business has broken. "
                        "Sitting still is the whole activity, and on this "
                        "strategy it is expected to be the answer for years "
                        "at a time.\n\n"
                        "It also covers every way more money does not go in "
                        "today — no room left under the most this strategy "
                        "will hold in one name, a business that would not "
                        "pass the entry tests at today's price, a question "
                        "you have not answered yet, or a figure that could "
                        "not be worked out. The rule named beside the "
                        "verdict says which, and an unreadable test is never "
                        "reported as a failed one."},

        {"id": "room-for-more", "render": "commit",
         "name": "Room for more of it",
         "description": "You own it, nothing has broken, it would still be "
                        "bought at today's price on the same tests that "
                        "bought it, and your three answers still stand. It "
                        "also sits below the most this strategy will hold in "
                        "any one name, and that gap is the whole of what may "
                        "go in.\n\n"
                        "This says the position may take capital. It does "
                        "not say to put any in, and it says nothing about "
                        "whether this is the best place for it. Nothing here "
                        "knows or can know what you paid — an add is never "
                        "triggered by the price having fallen below your own "
                        "cost."},

        {"id": "one-reading-past", "render": "hold",
         "name": "One reading past the line",
         "description": "An exit level has been crossed on the current "
                        "reading, and this strategy will not act on it until "
                        "the next filings say the same thing. One "
                        "impairment, one settlement, one heavy quarter of "
                        "investment can push a measure over a line without "
                        "anything having changed, and selling on that would "
                        "be the panic this exists to prevent. Nothing is "
                        "owed from you today."},

        {"id": "stopped-being-wonderful", "render": "close",
         "name": "It has stopped being wonderful",
         "description": "You marked one of the three questions a fail on a "
                        "business you own. That is the exit this strategy is "
                        "built around, and it is the only one that does not "
                        "come from a filing.\n\n"
                        "The reason for owning this was never the price — it "
                        "was that the business was worth owning. Your own "
                        "assessment now says it is not, and holding on from "
                        "here means owning it for a reason you have already "
                        "rejected. Your written reasoning is below, and it "
                        "is what you should read before acting."},

        {"id": "business-broken", "render": "close",
         "name": "The business has broken",
         "description": "Returns on capital, borrowing, interest cover, cash "
                        "generation or the share count has gone wrong, and "
                        "stayed wrong across more than one set of "
                        "filings.\n\n"
                        "Note what is not on that list: the price. Nothing "
                        "about what this company costs can produce this "
                        "verdict. Overpaying for a great business costs you "
                        "return; leverage and decay cost you the business, "
                        "and this is the strategy noticing the second."},

        {"id": "cannot-watch", "render": "unknown",
         "name": "Exit checks cannot run",
         "description": "You own it, and not one of the exit tests could be "
                        "worked out from the data on record — so this "
                        "strategy has nothing to say about whether to stay. "
                        "It is not telling you to hold; it is telling you it "
                        "cannot tell. Fetching data, or entering the figures "
                        "by hand, is what changes it."},
    ],

    "inputs": [
        # Deliberately optional, exactly as on Graham. Without it the size
        # rules cannot be worked out and say so, naming this field. Requiring
        # it would put a setup gate in front of every verdict in the journal
        # over a rule that binds on one holding in a handful.
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
    # where it does, and where it misfires. The reasoning is the report's
    # own except where a value says otherwise.
    # -----------------------------------------------------------------
    "values": [

        # -- how the tests roll up -----------------------------------------
        #
        # Two settings where there used to be one, and the one they replaced
        # was a single count over all nine second-tier tests. See the
        # DIMENSIONS comment for why a count was the wrong instrument.
        #
        # There is deliberately no setting for the four groups that demand
        # all of their rows. "Both of these must pass" is not a level anybody
        # can retune to something else without changing what the group means,
        # and a group that could be quietly set to nought is the quota
        # arriving again by another door.
        {"id": "cash-tests-required",
         "label": "Cash tests that must pass, of two",
         "type": "integer", "unit": "count", "min": 0, "max": 2,
         "source": AUTHOR,
         "explain": "This strategy asks two questions about whether the "
                    "profits turn into money: how much cash each dollar of "
                    "sales leaves behind, and how much of the reported "
                    "profit arrives as cash at all. This is how many of the "
                    "two have to come back clear.\n\n"
                    "One, because the two are largely the same reading. Both "
                    "are built on free cash flow, both move together, and a "
                    "company that fails one usually fails the other for the "
                    "same underlying reason. Demanding both would count one "
                    "piece of evidence twice — which is precisely the fault "
                    "the grouping here exists to correct. What is being "
                    "asked is that the question be answered, not that it be "
                    "answered twice.\n\n"
                    "Set it to 2 if you want both, and understand what you "
                    "have done: you have not added a second piece of "
                    "evidence, you have made one piece of evidence harder to "
                    "satisfy. Set it to 0 and this strategy stops asking "
                    "whether the profits are real, which is most of what it "
                    "means by a wonderful business."},

        {"id": "growth-tests-required",
         "label": "Growth tests that must pass, of two",
         "type": "integer", "unit": "count", "min": 0, "max": 2,
         "source": AUTHOR,
         "explain": "This strategy asks two questions about growth: whether "
                    "sales are growing at least as fast as the economy, and "
                    "whether profits are keeping up with sales. This is how "
                    "many of the two have to come back clear.\n\n"
                    "One, because they share a number. Both are computed "
                    "from the same revenue figure, so a company whose sales "
                    "history is distorted — by a large disposal, by a change "
                    "in how revenue is recognised — has both readings moved "
                    "by the same event, in the same direction, at the same "
                    "time. Two tests that fail together on one cause are one "
                    "test, and counting them as two is what let a company "
                    "look like it had cleared a broad standard when it had "
                    "cleared a narrow one several times.\n\n"
                    "Growth is also the dimension this strategy cares least "
                    "about. A slow grower earning very high returns on "
                    "capital is a fine thing to own, and requiring both "
                    "readings here would weigh growth more heavily than any "
                    "of the sources behind this file ever did."},

        # -- how much, and how many ----------------------------------------
        #
        # The two values here that are not the report's, and the place this
        # strategy differs most visibly from Graham's. Graham holds twenty
        # names at five percent each because he has formed no opinion about
        # any of them. This holds ten and will take one to forty percent,
        # because forming an opinion is the entire method.
        {"id": "portfolio-slots", "label": "Names held at once",
         "type": "integer", "unit": "count", "min": 1, "max": 100,
         "source": BUFFETT_PRACTICE,
         "explain": "How many separate companies this strategy holds at one "
                    "time. Each first purchase takes an equal share of the "
                    "account, so ten names means about ten percent each, and "
                    "once every place is taken a new candidate is told there "
                    "is no room rather than being talked down.\n\n"
                    "Ten is the top of Buffett's own stated range. His 1993 "
                    "letter to shareholders argues that an investor who can "
                    "identify five to ten sensibly-priced companies with "
                    "durable advantages has no use for conventional "
                    "diversification. The top of that range is used rather "
                    "than the bottom because five names is a concentration "
                    "somebody should arrive at deliberately, having done the "
                    "work, and not one a tool should hand them by "
                    "default.\n\n"
                    "Move toward five and every position doubles in "
                    "consequence — including the one where your assessment "
                    "of the moat turns out to be wrong, which is the risk "
                    "this style carries and Graham's does not. Move past "
                    "twenty and you are holding more businesses than anyone "
                    "can follow closely enough to answer this strategy's own "
                    "three questions honestly, which quietly turns the whole "
                    "method into guessing.\n\n"
                    "This figure and the position cap below are the only two "
                    "here that do not come from the expert report — it was "
                    "never asked about sizing."},

        {"id": "position-weight-cap",
         "label": "Most this will put into one name",
         "type": "number", "unit": "percent", "min": 1, "max": 100,
         "source": BUFFETT_PRACTICE,
         "explain": "The largest share of your account this strategy will "
                    "take a single holding up to by buying more of it.\n\n"
                    "**Read what that does and does not mean, because it is "
                    "the one setting here most likely to be "
                    "misunderstood.** It is a limit on your purchases, not "
                    "on the position. If a holding compounds until it is "
                    "sixty percent of the account, nothing here tells you to "
                    "trim it — this strategy has no trim, on purpose. What "
                    "this number does is stop you *adding* past forty "
                    "percent. The market may take a position wherever it "
                    "likes; you may not.\n\n"
                    "Forty percent is Buffett's own figure from his 1965 "
                    "partnership letter, where he set it as the most he "
                    "would commit to a single holding, and only in an "
                    "exceptional case. It is the most concentrated setting "
                    "in this program by a wide margin, and it is only "
                    "reachable through repeated purchases, each of which "
                    "has to pass every entry test and all three of your own "
                    "assessments on the day it is made.\n\n"
                    "It is deliberately far above the ten percent a first "
                    "purchase is sized at. The gap between the two is where "
                    "this strategy differs from a rebalancing one: money is "
                    "added to what keeps proving itself rather than moved "
                    "back toward an average.\n\n"
                    "It needs this journal's cash record to be open, "
                    "because a share of the account cannot be worked out "
                    "without knowing what the account is. Until it is, the "
                    "size rules report that they could not be run.\n\n"
                    "Attributed to Buffett's practice, not to the expert "
                    "report, which does not cover sizing."},

        # -- the three knockouts -------------------------------------------
        {"id": "min-roic", "label": "Lowest return on invested capital",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "How much profit the company earns each year for every "
                    "dollar of money tied up in it — the money its owners "
                    "put in and the money it borrowed, together. At 15 it "
                    "turns fifteen cents of profit a year out of every "
                    "dollar the business runs on. Taken as the middle "
                    "reading of the last five years, so one exceptional year "
                    "cannot carry it.\n\n"
                    "This is the single most important number in this "
                    "strategy. A business that earns high returns on the "
                    "money inside it can grow by keeping its own profits, "
                    "which is what compounding actually is; one that earns "
                    "low returns has to keep asking you for more.\n\n"
                    "Fifteen rather than twelve because the cost of the "
                    "money is somewhere near eight to ten percent for a "
                    "typical business. At twelve you are looking at a spread "
                    "of two or three points, which is inside the error bars "
                    "of the calculation itself. Fifteen is where the gap "
                    "becomes wide enough to survive being wrong about the "
                    "inputs — and it is roughly where the population thins "
                    "out, since plenty of companies clear twelve for a year "
                    "or two and far fewer hold fifteen across five.\n\n"
                    "Where it misfires: it does not mean anything for banks "
                    "or insurers, whose balance sheets do not work this way, "
                    "and the journal marks it unreadable for them rather "
                    "than scoring them badly."},

        {"id": "max-debt-to-fcf",
         "label": "Highest debt against the cash it generates",
         "type": "number", "unit": "times", "min": 0,
         "source": REVIEW,
         "explain": "How many years of the spare cash the business actually "
                    "produces it would take to pay off everything it has "
                    "borrowed. At 3.0 it would take three.\n\n"
                    "The preference is a business that could clear its debts "
                    "out of a few years of earnings. The point of intending "
                    "to hold something forever is that it never has to "
                    "renegotiate anything at a bad moment.\n\n"
                    "**This test used to be run against EBITDA and is the "
                    "one place in this file where a source was overruled "
                    "rather than followed.** EBITDA adds depreciation back "
                    "to profit — the cost of the machinery wearing out — on "
                    "the reasoning that it is not a cash payment this year. "
                    "Munger's stated position is that the word should be "
                    "read as a synonym for fictitious earnings, and Buffett "
                    "has written repeatedly that depreciation is a real "
                    "expense and that any measure ignoring it flatters "
                    "exactly the capital-hungry businesses least able to "
                    "carry debt. A measure they attacked in public cannot "
                    "sit at the tier that overrules everything else in a "
                    "strategy named after them. Free cash flow has already "
                    "paid for the equipment, so it needs no such argument, "
                    "and it is averaged over five years so that one heavy "
                    "year of investment does not read as a balance-sheet "
                    "problem.\n\n"
                    "3.0 rather than the 2.5 the EBITDA version used, "
                    "because the two are not the same scale: free cash flow "
                    "is the smaller number for almost every company, so the "
                    "same ratio against it is the stricter test. The level "
                    "moved so that the demand did not.\n\n"
                    "The EBITDA version is still reported below, among the "
                    "tests that never block. It is the number credit ratings "
                    "speak, so it is worth being able to see — and being "
                    "able to see it is all it is worth.\n\n"
                    "This is a knockout and the exit on the other side of it "
                    "is the exception to everything else this strategy "
                    "believes. Overpaying for a great business costs you "
                    "return. Borrowing costs you the business. Every "
                    "permanent-capital disaster in this tradition ran "
                    "through the balance sheet and not the income "
                    "statement.\n\n"
                    "Where it misfires: a company with a lending arm of its "
                    "own reports borrowings that are its stock in trade "
                    "rather than a risk, and the combined figure means very "
                    "little. The journal marks those unreadable rather than "
                    "failing them. A company part-way through a deliberate "
                    "building programme also reads as more indebted than it "
                    "is, and five years of averaging absorbs one such year "
                    "rather than a decade of them."},

        {"id": "min-owner-earnings-yield",
         "label": "Lowest owner earnings yield",
         "type": "number", "unit": "percent",
         # The level is the report's and the review agreed with it
         # explicitly. What the level is measured against is the review's,
         # and so is most of the account below, which is why this cites the
         # report for the number and claims the reasoning for itself.
         "source": REPORT_LEVEL_ONLY,
         "explain": "What the company's cash profits pay you each year, as a "
                    "percentage of what the whole business costs at today's "
                    "price — the shares AND the debts that come with them. "
                    "At 5 you are being paid five cents a year for every "
                    "dollar of price, which is another way of saying you are "
                    "paying twenty times earnings.\n\n"
                    "\"Owner earnings\" is the profit left after everything "
                    "the business must spend to stay as good as it is. It is "
                    "a stricter figure than reported profit and a more "
                    "honest one, because reported profit does not subtract "
                    "the machinery a company has to keep replacing.\n\n"
                    "**The price it is measured against is the whole "
                    "business and not just the shares, and that is a "
                    "change.** Owner earnings is a figure about the "
                    "business, so it belongs over what the business costs: "
                    "buying a company with borrowings attached means taking "
                    "the borrowings on. Measured against the shares alone, a "
                    "heavily indebted company reads as cheap precisely for "
                    "being indebted. The level stayed at 5 while the "
                    "denominator changed, so this test is now stricter for "
                    "companies carrying net debt and slightly looser for "
                    "companies carrying net cash — which is the correction, "
                    "not a side effect of it.\n\n"
                    "This is the only price test here and the only one that "
                    "will ever be. The reputation for ignoring price is "
                    "mostly myth — Coca-Cola was bought at roughly fifteen "
                    "times earnings, Apple at roughly thirteen, and dozens "
                    "of wonderful businesses were walked away from on price "
                    "alone. Twenty times owner earnings is about the outer "
                    "edge of what has historically been paid for quality. "
                    "Set it to 7% and you have imposed a deep-value "
                    "discipline that will never buy anything wonderful; set "
                    "it to 3% and you have removed price discipline "
                    "entirely.\n\n"
                    "**Why this level does not move when interest rates do, "
                    "when every other absolute price level in this program "
                    "does.** It is the obvious objection and it has a "
                    "specific answer. Coca-Cola was bought in 1988 at "
                    "roughly a 6.7% earnings yield when a ten-year Treasury "
                    "paid around 9% — a negative spread to the risk-free "
                    "rate. Any rule of the form \"yield must beat the bond "
                    "by so much\" would have refused one of the best "
                    "purchases on record, and refused it most firmly at the "
                    "moment it was most right. The discipline being expressed "
                    "here is a judgement about what a durable stream of owner "
                    "earnings is worth to keep, not a spread against an "
                    "alternative you would have to sell it to buy. A fixed "
                    "5% is a crude stand-in for that and it is an honest "
                    "one. This is a real disagreement with the Graham "
                    "strategy, whose valuation levels are rate-aware by "
                    "design and whose author would have argued the other "
                    "side; the two are separate strategies and separate "
                    "journals for exactly this class of reason.\n\n"
                    "**There is no exit on the other side of this, and that "
                    "is the most important empty field in the program.** A "
                    "business that compounds at 18% for twenty years will "
                    "spend most of those twenty years looking expensive. If "
                    "this could force a sale, this strategy would sell every "
                    "great business it ever bought, roughly three years in, "
                    "and would be destroying your returns while appearing to "
                    "work correctly."},

        # -- the ten tests behind the six questions -------------------------
        {"id": "min-incremental-roic",
         "label": "Lowest return on the money it keeps",
         "type": "number", "unit": "percent",
         "source": REVIEW,
         "explain": "How much the profits the company retained over the last "
                    "five years have earned. Not what the business as a "
                    "whole earns — what the newly retained money "
                    "earns.\n\n"
                    "**This is the difference between a wonderful business "
                    "and a wonderful business that has run out of things to "
                    "do.** Return on invested capital, the first knockout "
                    "above, describes everything built and bought over the "
                    "company's whole life, taken together. It can stay at "
                    "25% for years while every new dollar goes into "
                    "something earning 6, because the old business is "
                    "carrying the average. This measures only the new "
                    "dollars — and the new dollars are what set the rate the "
                    "company compounds at from here.\n\n"
                    "Fifteen, matching the floor under the existing base, "
                    "and deliberately so: a company reinvesting at less than "
                    "it already earns is a company whose returns are on "
                    "their way down, and this strategy's whole thesis is "
                    "that the compounding continues.\n\n"
                    "Where it misfires: it is a ratio of two differences, so "
                    "it moves more than any level does. A large acquisition "
                    "puts its whole price into the denominator at once and "
                    "delivers its profits over years, so an acquisitive "
                    "company reads low for a while and then recovers. And it "
                    "needs eight fiscal years, so it is absent for anything "
                    "listed recently — absent, not failed."},
        {"id": "min-interest-coverage", "label": "Lowest interest coverage",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "How many times over the company's operating profit "
                    "covers its interest bill. At 8 it earns eight dollars "
                    "for every dollar of interest it owes.\n\n"
                    "Graham used 5x as his bond-safety standard for an "
                    "average industrial company. This strategy's quality bar "
                    "sits above an average industrial, and 8x is where a "
                    "halving of earnings still leaves comfortable cover. "
                    "Below 5x you are one recession away from a conversation "
                    "with your lenders.\n\n"
                    "Where it misfires: a company with no debt has no "
                    "interest bill, and dividing by nothing has no answer. "
                    "The journal marks that unreadable — which is the "
                    "opposite of a problem and reads oddly, since a company "
                    "with no debt is the ideal this test is reaching for."},

        {"id": "max-gross-margin-swing",
         "label": "Widest the gross margin may swing, against its own size",
         "type": "number", "unit": "percent", "min": 0,
         "source": REVIEW,
         "explain": "Gross margin is what is left of each sales dollar after "
                    "the direct cost of the thing sold. This measures how "
                    "far it has moved between its best and worst year over "
                    "five — as a share of the margin itself. At 15 the whole "
                    "swing is a seventh of the typical margin.\n\n"
                    "The range rather than the level, on purpose, and this "
                    "is the most easily misread test here. Requiring a *high* "
                    "gross margin — say forty percent — would exclude "
                    "high-volume retail and most of retail generally, which "
                    "this style has owned very happily. Stability is the "
                    "actual signal. Pricing power shows up as a flat line, "
                    "not a high one: a company that can pass its costs on "
                    "keeps the same margin whatever its inputs do.\n\n"
                    "**A share of the margin and not a number of points, and "
                    "that is a change to what this test means.** It used to "
                    "allow a six-point swing, full stop. A distributor "
                    "earning 12% and moving between 9% and 15% swung six "
                    "points and half its margin came and went; a software "
                    "company earning 81% and moving between 78% and 84% swung "
                    "six points and barely noticed. One is a commodity "
                    "business and the other sets its own prices, and a limit "
                    "in points calls them identical. Fifteen percent of the "
                    "margin says the same thing to both.\n\n"
                    "Where it misfires: a company whose margin is genuinely "
                    "thin — a few points, as in wholesale distribution — has "
                    "little to divide by, so ordinary movement reads as "
                    "violent. That is arguably correct, since a point really "
                    "does take a large share of such a company's margin, but "
                    "it means this reads harshly at the bottom end. A "
                    "company that does not report its cost of sales "
                    "separately cannot be measured at all, and many service "
                    "businesses do not. And the 2018 revenue-recognition "
                    "change moved some shipping and fulfilment costs between "
                    "cost of sales and operating expense, which puts a step "
                    "in the margin of any window spanning it that is "
                    "presentation rather than pricing."},

        {"id": "min-fcf-margin", "label": "Lowest free cash flow margin",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "How many cents of genuinely spare cash the company "
                    "produces per dollar of sales, after paying for the "
                    "equipment and buildings it needs. At 10 it keeps ten "
                    "cents. Taken as the middle reading of five years.\n\n"
                    "Below ten cents, growth eats the cash and the owner "
                    "never sees any of it. This is the line between a "
                    "business that funds itself and one that periodically "
                    "needs your money back.\n\n"
                    "The exit on the other side of this watches a different "
                    "figure — the most recent twelve months rather than the "
                    "five-year middle — because a five-year median is "
                    "designed not to move and would take years to notice a "
                    "business that had stopped producing cash."},

        {"id": "min-cash-conversion", "label": "Lowest cash conversion",
         "type": "number", "unit": "ratio",
         "source": REPORT,
         "explain": "How much of the profit the company reports actually "
                    "turns up as cash. At 0.90 it collects ninety cents of "
                    "real money for every dollar of stated profit.\n\n"
                    "This is a check that the earnings are real rather than "
                    "a quality bar. Perfect conversion is rare, and slightly "
                    "above 1.0 is common for companies with a lot of "
                    "depreciation and little current spending. Persistently "
                    "below 0.80 means bookkeeping: profit booked on sales "
                    "not yet collected, or costs parked on the balance sheet "
                    "instead of being subtracted. 0.90 sits between the "
                    "two.\n\n"
                    "There is no exit on the other side of it. A bad reading "
                    "tells you to go and read the filings, not to sell on a "
                    "number.\n\n"
                    "Where it misfires: fast growth produces a low reading "
                    "legitimately, because the cash is going into stock and "
                    "unpaid invoices that will turn into money later."},

        {"id": "max-share-count-change",
         "label": "Most the share count may grow",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "How much the number of shares has changed over five "
                    "years. At 0 it must not have grown at all: flat is the "
                    "floor and shrinking is the point.\n\n"
                    "Everything else in this list is about the company. This "
                    "one is about your share of it. A business can improve "
                    "every year while your slice of it quietly shrinks, "
                    "because shares handed to employees are a real cost "
                    "that never appears as one on the profit line. Per share "
                    "is the only thing that matters to an owner.\n\n"
                    "Where it misfires: a company that issued shares to buy "
                    "something genuinely worth buying fails this, and "
                    "occasionally it should not have."},

        {"id": "max-roe-roic-gap",
         "label": "Most of the return that may be borrowed",
         "type": "number", "unit": "percentage_points", "min": 0,
         "source": REVIEW,
         "explain": "Return on equity counts only the owners' money. Return "
                    "on invested capital counts the borrowed money as well. "
                    "So the distance between them is borrowing, and nothing "
                    "else. At 10 the company may earn ten points more on its "
                    "owners' money than on all the money in the business, "
                    "and no more.\n\n"
                    "A company earning 30% on equity and 12% on capital is "
                    "producing most of that 30% with debt rather than with "
                    "the business. It is not a fraud and it is not always a "
                    "mistake — but the returns being admired belong partly "
                    "to the lenders, and they get thinner the moment "
                    "borrowing gets dearer or harder to get.\n\n"
                    "**This used to test the level of return on equity, at "
                    "the same 15 the return on capital is held to, and that "
                    "was two tests measuring one thing.** The reasoning "
                    "beside it always said the informative part was the "
                    "divergence — and then it tested the height. Testing the "
                    "distance directly is what that sentence was describing, "
                    "and it stops a leveraged company from banking two "
                    "passes for one good business.\n\n"
                    "There is no exit on the other side of it. Return on "
                    "equity is trivially inflated by borrowing, so a company "
                    "that levers up to defend a falling return keeps it "
                    "looking well right through the deterioration — which is "
                    "the reason this measures the gap, and also the reason "
                    "the gap is a poor thing to sell on. Return on invested "
                    "capital catches the decay, and that is where the exit "
                    "is.\n\n"
                    "Where it misfires: a company that has bought back so "
                    "much stock that its stated equity is near zero produces "
                    "a very wide gap for a reason that is arithmetic rather "
                    "than borrowing, and the journal marks the underlying "
                    "figure unreadable where equity goes negative. A "
                    "debt-free company shows a narrow gap, correctly, but "
                    "then the two measures differ only by its cash and its "
                    "tax, so the number stops carrying much."},

        {"id": "min-revenue-cagr", "label": "Lowest revenue growth",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "How fast sales have grown each year, averaged over five "
                    "years. At 4 the company is growing roughly as fast as "
                    "the economy in cash terms.\n\n"
                    "A business growing slower than the economy is losing "
                    "share of its market, and a wonderful business losing "
                    "share is on its way to being an ordinary one.\n\n"
                    "It sits among the core tests rather than the knockouts "
                    "because growth is not what this strategy is buying. A "
                    "slow grower is perfectly acceptable when the returns on "
                    "capital are high enough — that combination is a "
                    "business that hands its profits back to you instead of "
                    "needing them, which is a fine thing to own."},

        {"id": "min-profit-growth-spread",
         "label": "Lowest gap between profit growth and sales growth",
         "type": "number", "unit": "percentage_points",
         "source": REPORT,
         "explain": "Profit growth minus sales growth, over five years. At "
                    "-1 profits may grow one point a year slower than sales "
                    "and no worse.\n\n"
                    "Profits should grow at least as fast as sales. If sales "
                    "grow eight percent and profits grow three, the company "
                    "is buying its growth by giving away margin — which "
                    "works right up until it stops, and looks like success "
                    "the whole way.\n\n"
                    "Zero tolerance makes this fire on rounding and "
                    "single-year noise. Wider than a point and it stops "
                    "detecting anything."},

        {"id": "max-goodwill-written-off",
         "label": "Most of the owners' money that may have been written off",
         "type": "number", "unit": "percent", "min": 0,
         "source": REVIEW,
         "explain": "How much the company has written back off the "
                    "acquisitions it made, added up over five years, against "
                    "the owners' money that existed before those write-offs "
                    "began. At 5 a twentieth of the equity base has been "
                    "conceded.\n\n"
                    "Goodwill is the premium an acquirer pays over what the "
                    "acquired business's identifiable assets are worth. "
                    "Writing it off is management admitting, in public and "
                    "in the accounts, that the premium bought nothing. One "
                    "such admission is a deal that went wrong. A run of them "
                    "against a large share of the equity is a company whose "
                    "growth has been bought at prices it could not "
                    "justify.\n\n"
                    "**This used to test how much goodwill sat on the "
                    "balance sheet, and that test measured the wrong "
                    "thing.** Buffett's own 1983 letter appendix argues that "
                    "economic goodwill is the most valuable asset a business "
                    "owns and that the accounting entry measures it badly — "
                    "so a limit on the accounting entry is a limit his own "
                    "writing argues against. It also punished a company "
                    "permanently for one good acquisition fifteen years ago, "
                    "and the note beside it conceded that it wrongly "
                    "excluded some of the best acquisitive compounders "
                    "there are. What survives that objection is the "
                    "outcome: not that a company bought things, but that "
                    "what it bought turned out not to be there.\n\n"
                    "The denominator is the equity *before* the window and "
                    "not after it. Write-offs reduce equity, so measuring "
                    "against today's would divide a large charge by a base "
                    "the same charge had already shrunk, and flatter the "
                    "worst cases most.\n\n"
                    "There is still no exit on the other side of it. A "
                    "write-off is usually the market telling you something "
                    "you already knew, and by the time it is in the accounts "
                    "the returns test has had years to notice.\n\n"
                    "Where it misfires: the timing of an impairment says as "
                    "much about when management conceded as about when the "
                    "value went, and a charge in a year interest rates moved "
                    "sharply is weaker evidence than one in a quiet year, "
                    "because rates feed the impairment test directly. A "
                    "company that has never acquired anything reads zero, "
                    "and so does one whose acquisitions all worked; this "
                    "cannot tell those apart and is not trying to."},

        # -- the five bonus tests ------------------------------------------
        {"id": "max-debt-to-ebitda",
         "label": "Highest debt against earnings before depreciation",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "How many years of the company's operating earnings "
                    "*before* the cost of its equipment wearing out it would "
                    "take to repay everything it has borrowed. At 2.5 it "
                    "would take two and a half.\n\n"
                    "**This was a knockout and is now reported and never "
                    "blocking, which is the largest single change in what "
                    "this strategy demands.** The measure adds depreciation "
                    "back to profit on the reasoning that it is not a cash "
                    "payment this year. Munger's stated position is that the "
                    "term should be read as a synonym for fictitious "
                    "earnings; Buffett has written repeatedly that "
                    "depreciation is a real expense and that ignoring it "
                    "flatters exactly the capital-hungry businesses least "
                    "able to carry debt. Leaving a measure they attacked at "
                    "the tier that overrules everything else was attributing "
                    "to them a test they would disown.\n\n"
                    "It is kept because it is the number credit ratings "
                    "speak. Three times is roughly where agencies begin "
                    "marking down cyclical borrowers, so 2.5 shows whether "
                    "this balance sheet has a turn of cushion by the "
                    "convention the outside world uses. That is worth being "
                    "able to see. It is not worth deciding on, and the "
                    "knockout it used to be is now held against free cash "
                    "flow instead.\n\n"
                    "The level is the report's and is untouched. Only where "
                    "it sits has moved, and that placement is this "
                    "strategy's own."},

        {"id": "min-effective-tax-rate", "label": "Lowest effective tax rate",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": REVIEW,
         "explain": "The share of profit the company actually pays in tax, "
                    "averaged over five years — the lower end of a band this "
                    "test expects it to sit inside.\n\n"
                    "This is a sanity check on earnings quality and not a "
                    "quality bar, which is why it never blocks anything. A "
                    "company reporting a four percent tax rate is either "
                    "running an aggressive structure that will eventually be "
                    "challenged, or booking one-off benefits that flatter "
                    "its earnings and will not repeat. Either way the profit "
                    "figure everything else here is built on is not what it "
                    "looks like.\n\n"
                    "Twelve rather than the ten this used to be. The band "
                    "was set against a 35% US federal rate; the 2017 tax act "
                    "cut that to 21%, and every rate in the distribution "
                    "moved down with it. Holding the old floor while the "
                    "world moved would quietly widen the band from below.\n\n"
                    "The source states this as one band. It is two settings "
                    "here because a band is two comparisons, and two rows on "
                    "the screen can say which end was missed where one row "
                    "could only say that something was."},

        {"id": "max-effective-tax-rate", "label": "Highest effective tax rate",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": REVIEW,
         "explain": "The upper end of the tax band described above. Above "
                    "roughly twenty-eight percent, either the company is "
                    "paying an unusual amount for a reason worth "
                    "understanding, or a one-off charge has landed in the "
                    "tax line and the profit figure is understated rather "
                    "than overstated.\n\n"
                    "**Twenty-eight rather than the thirty-five this used to "
                    "be, and the old figure had stopped doing anything at "
                    "all.** It was set when the US federal statutory rate "
                    "was 35%, so a ceiling at 35 caught only companies "
                    "paying more than the full domestic rate. After the 2017 "
                    "act cut the statutory rate to 21%, a US-centric company "
                    "typically runs somewhere around 19 to 23 — so the old "
                    "ceiling sat a dozen points above anything it could ever "
                    "have flagged. A test that cannot fire is not a lenient "
                    "test, it is an absent one wearing a number.\n\n"
                    "The band catches both ends of the same worry: that the "
                    "reported profit is not a repeatable profit. Like its "
                    "twin it never blocks a buy."},
        {"id": "min-current-ratio", "label": "Lowest current ratio",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "How much the company holds in things it can turn into "
                    "cash within a year against the bills it has to pay in "
                    "that year. At 1.0 the two exactly balance.\n\n"
                    "**This is deliberately a bare solvency check and not a "
                    "quality signal, and it is set far below where a "
                    "different strategy would set it.** Graham requires 2.0 "
                    "and treats it as a knockout, because he is buying a "
                    "business he has formed no opinion about and the balance "
                    "sheet has to carry the risk the operations cannot. This "
                    "strategy has formed an opinion, so the same measure "
                    "means something else here.\n\n"
                    "More than that: negative working capital is a *feature* "
                    "in this style. A business that collects from its "
                    "customers before it pays its suppliers is being "
                    "financed for free by its own operations, and several of "
                    "the best businesses this strategy would want to own "
                    "fail any stricter version of this test. That counts "
                    "against the test rather than against them, which is "
                    "why it never blocks a buy.\n\n"
                    "Keep this among the bonus tests and never among the "
                    "knockouts."},

        {"id": "max-payout-to-fcf",
         "label": "Most of free cash flow that may be paid out",
         "type": "number", "unit": "percent", "min": 0,
         "source": REPORT,
         "explain": "How much of the spare cash the company produces is "
                    "handed back to shareholders as dividends and buybacks, "
                    "averaged over five years. At 80 it is returning four "
                    "fifths and keeping one.\n\n"
                    "Sustainably above one hundred percent means the returns "
                    "are being funded with borrowing rather than earnings, "
                    "which is a dividend that is quietly a loan. Eighty "
                    "leaves room for a bad year without the payout tipping "
                    "over that line.\n\n"
                    "There is no exit on the other side of it, because if "
                    "the payout is being debt-funded the borrowing test "
                    "catches it and that one does have an exit. Two tests "
                    "firing on one underlying event is how somebody gets "
                    "frightened out of a position twice."},

        # -- the five exits ------------------------------------------------
        #
        # Not one of them is a valuation measure. That is the character of
        # this strategy rather than an omission, and it is stated on every
        # entry test that has no exit beside it.
        {"id": "exit-roic-fall",
         "label": "Worst fall in returns before this sells",
         "type": "number", "unit": "percent", "max": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "How far the return on invested capital may fall from "
                    "where it stood when you first bought, measured as a "
                    "share of what it was then rather than as a number of "
                    "points. At -33 it may lose a third of itself.\n\n"
                    "**A share of itself, not a number of points, and that "
                    "distinction is the entire test.** A third off a "
                    "business earning 45% is fifteen points and probably an "
                    "ordinary couple of years. A third off one earning 15% "
                    "is five points and most of the reason you owned it. A "
                    "single limit expressed in points cannot say the same "
                    "thing to both companies; expressed this way, one number "
                    "does.\n\n"
                    "The exit is relative rather than absolute on purpose. "
                    "You do not sell because returns printed 14%. You sell "
                    "because a business that used to earn 22% now earns 12% "
                    "and the reason is that the moat leaked. An absolute "
                    "floor on its own would let you sit through the entire "
                    "decay and fire only at the bottom — which is why this "
                    "is only half the test, and the other half is the floor "
                    "below.\n\n"
                    "It is measured from your *first* purchase and not your "
                    "most recent one. That is the only way a slow leak is "
                    "visible: measured from the last time you bought, a "
                    "holder who added along the way would reset the "
                    "comparison every time and the rule could never fire. "
                    "The cost of that choice is real and worth knowing — if "
                    "you knowingly bought more of a business at lower "
                    "returns, this still measures you against the day you "
                    "started.\n\n"
                    "**The report states this level as 33 and puts the "
                    "direction in the sentence around it.** It is written "
                    "here as -33 because the journal reads a limit as a "
                    "signed number and compares it against a signed change, "
                    "so the minus sign is what makes it a fall rather than a "
                    "rise. The size of it is untouched."},

        {"id": "exit-roic-level",
         "label": "Return on capital that ends the position",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "The absolute floor under the return on invested "
                    "capital. Below 12% the business has stopped earning "
                    "meaningfully more than its money costs, whatever it "
                    "used to earn.\n\n"
                    "This and the fall above are one test and both halves "
                    "have to be true before anything happens. Requiring both "
                    "catches a deterioration while it is still a "
                    "deterioration, and stops a company that was always "
                    "around 13% from firing on ordinary movement — it never "
                    "had a third to lose.\n\n"
                    "Only this half is checked across consecutive filings. "
                    "The fall is measured against a figure frozen at your "
                    "purchase, and the journal keeps no history of that "
                    "comparison to walk back through, so the confirmation "
                    "rule is applied where there is a series to apply it to."},

        {"id": "exit-debt-to-fcf",
         "label": "Debt against cash generation that ends the position",
         "type": "number", "unit": "times", "min": 0,
         "source": AUTHOR,
         "explain": "At five years of spare cash owed, the balance sheet has "
                    "stopped being the thing that lets you hold this "
                    "calmly.\n\n"
                    "This is the exception to everything else here, and it "
                    "is deliberate. This strategy will not sell a wonderful "
                    "business for being expensive, for being slow, or for "
                    "having been owned a long time. It will sell one for "
                    "borrowing too much, because overpaying costs you return "
                    "and borrowing costs you the business.\n\n"
                    "Note the distance from the 3.0 required to buy. That "
                    "gap is deliberate: a company drifting from 3.0 to 3.3 "
                    "is not the same event as one arriving at 5.0, and an "
                    "exit set at the entry level would fire on ordinary "
                    "movement.\n\n"
                    "**This is the one level in this file with no source "
                    "behind it, and it is the one to argue with.** The exit "
                    "used to be held against debt over EBITDA at 4.0, and it "
                    "had to move when the test it belongs to did: a strategy "
                    "that refuses to *buy* on a measure — because it adds "
                    "back the cost of the equipment wearing out — cannot "
                    "coherently *sell* on the same measure, and selling is "
                    "the more consequential of the two. Neither source "
                    "states a level for the replacement. Five is chosen as "
                    "five years of every spare dollar, which is a business "
                    "whose future substantially belongs to its lenders; for "
                    "what it is worth, keeping the entry-to-exit distance "
                    "the report used on the pair it did state — 2.5 to 4.0, "
                    "or one and three fifths — would put it at 4.8, and the "
                    "difference between those two is not meaningful at this "
                    "precision."},

        {"id": "exit-interest-coverage",
         "label": "Interest coverage that ends the position",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "Below four times cover, the interest bill has stopped "
                    "being an incidental line and started being a constraint "
                    "on what the business is allowed to do — what it can "
                    "invest in, what it can pay out, what it can survive.\n\n"
                    "Set at half the 8x required to buy, for the same reason "
                    "every exit here sits well below its entry test: the "
                    "distance between them is the room a company is allowed "
                    "to move in without anybody acting."},

        {"id": "exit-fcf-margin",
         "label": "Free cash flow margin that ends the position",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "Zero. Not a low number — negative. The company is "
                    "spending more cash than it brings in.\n\n"
                    "Held against the most recent twelve months rather than "
                    "the five-year median the entry test uses, because a "
                    "five-year median is built not to move and would take "
                    "years to register a business that had stopped producing "
                    "cash at all.\n\n"
                    "How long it has to stay there before this acts is set "
                    "separately — see the free cash flow window, which is "
                    "four quarters rather than the two filings every other "
                    "exit takes."},

        {"id": "exit-share-count-change",
         "label": "Share count growth that ends the position",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "How much the share count may grow over three years "
                    "before this strategy treats it as a change in what kind "
                    "of company you own. At 10 it is a little over three "
                    "percent a year.\n\n"
                    "The entry test spans five years and requires no growth "
                    "at all; this watches a shorter window, because the "
                    "question is not what the company has historically done "
                    "but what it started doing recently. A company diluting "
                    "three percent a year forever is structurally not a "
                    "holding for this strategy, and if it began doing that "
                    "after you bought, something about how management thinks "
                    "has changed."},
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
    """One citation: which measure, which direction, and the setting the
    host reads the limit out of. Nothing here is a number.

    `at` cites the reading at one past filing; `without` cites the current
    window with the single year that most favours the requirement taken
    out. Both are the host's arithmetic on the host's figures — this file
    names the question and never the answer."""
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
# the three questions
#
# Cited exactly like a measure, because to the host that is what they are.
# The difference the reader sees — "your own assessment, not a figure the
# journal worked out" — is decided by the host from the bank, and this file
# could not present one as a measurement if it tried.
#
# The order they are cited in is the order they are asked in, and it is not
# arbitrary: the moat is the business, management is the people, capital
# allocation is what the people do with the business. Each one is harder to
# answer than the last and the first is the one worth most.
# ---------------------------------------------------------------------------

def _judgement_cites(group):
    return [{"measure": m, "comparator": "equals", "threshold": True,
             "group": group} for m in QUALITATIVE]


def _judgements(ctx, group):
    """(citations, outcomes) for the three questions.

    Unanswered comes back `unknown` and never `pass` — the host's own
    arithmetic does that, and it is why this strategy does not have to
    remember to treat silence as a refusal.
    """
    cites = _judgement_cites(group)
    return cites, [contract.test(ctx, item) for item in cites]


def _unanswered(outcomes):
    """The questions with no answer on record, by their bank id."""
    return [QUALITATIVE[i] for i, o in enumerate(outcomes) if o == UNKNOWN]


def _marked_down(outcomes):
    """The questions the reader answered with a no."""
    return [QUALITATIVE[i] for i, o in enumerate(outcomes) if o == FAIL]


# ---------------------------------------------------------------------------
# the exits, and the confirmation walk
# ---------------------------------------------------------------------------

def _exit_state(ctx, group, measure_id, comparator, value_id):
    """One exit as confirmed / breached / clear / unreadable, with whatever
    the host leant on to say so. `comparator` is what the holding must keep
    being true; the exit is that failing.

    This file used to walk the filing series itself and compare the run
    against a setting it declared. It no longer does, and the settings are
    gone with them: how much evidence a breach needs is a property of the
    measure, and this strategy had no way to know that its five exits are
    read three different ways. A five-year median cannot be confirmed by
    waiting — the next reading shares four of its five years — while a
    trailing twelve months genuinely rolls a quarter, and a change between
    two single years is not a long-window measure at all.

    Absence never fires an exit. A missing reading is not evidence that a
    company is in trouble, and this program does not sell on silence — but
    it is not reported as clear either, so the caller can tell an exit that
    was checked from one that was not.
    """
    return contract.confirm(ctx, _cite(measure_id, comparator, value_id,
                                       group))


def _roic_exit(ctx, group, absolute):
    """The one compound exit, as a single answer.

    The report asks for both halves at once: returns must have fallen by a
    third of what they were AND be under an absolute floor. Either on its own
    is a rule this strategy does not have. A company that has always earned
    13% has no third to lose and must not be sold for being what it always
    was; a company that fell from 40% to 25% has lost more than a third and
    is still a better business than most things anybody owns.

    So the requirement holds while EITHER half holds, and only the two
    failing together ends it. Absence on either side leaves it unreadable
    rather than clear, because a comparison nobody could make has not shown
    that nothing happened.
    """
    drift = contract.test(ctx, {**ROIC_DRIFT, "group": group})
    found = absolute
    if drift == PASS or found["confirmation"] == CLEAR:
        return {**found, "confirmation": CLEAR}
    if drift == UNKNOWN or found["confirmation"] == UNREADABLE:
        return {**found, "confirmation": UNREADABLE}
    return found


def _exit_states(ctx, group):
    """Every exit, in the order EXITS declares them."""
    states = [_exit_state(ctx, group, *row) for row in EXITS]
    states[ROIC] = _roic_exit(ctx, group, states[ROIC])
    return states


def _half_failed(ctx, group, states):
    """Whether one half of the compound return-on-capital exit came back
    failed while the exit itself did not fire.

    It has to be said out loud, because it is the one case where a row on
    the screen reads as a failure beside a summary saying everything is
    clear. That is not a contradiction — the exit genuinely requires both
    halves, and one of them failing is not the exit failing — but a reader
    cannot be expected to work that out from a red row and a sentence that
    does not mention it. The same reason `also_waiting` exists.
    """
    if states[ROIC]["confirmation"] != CLEAR:
        return None
    drift = contract.test(ctx, {**ROIC_DRIFT, "group": group})
    level = contract.test(ctx, _cite(*EXITS[ROIC], group))
    if drift == FAIL:
        return ("Returns on capital have fallen further from where they were "
                "when you first bought than this strategy will sit through — "
                "but they are still above the floor it needs them to break as "
                "well, and that exit requires both. One red row below, and no "
                "exit.")
    if level == FAIL:
        return ("Returns on capital are below the floor that can end this "
                "position — but they have not fallen far enough from where "
                "they were when you first bought, and that exit requires "
                "both. One red row below, and no exit.")
    return None


def _confirmed_on(broken):
    """What the exits that fired were established on, in a clause.

    Derived rather than asserted. The sentence used to read "on more than
    one set of filings" whatever had happened, which is one rule speaking
    for five exits that are read three different ways — and a verdict has to
    name the rule that produced it, or the reader is being asked to take the
    strongest available reading of a sentence on trust.

    Where the five disagree the clause does not state a number at all,
    rather than picking one of them and being wrong about the others.
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
    """Every exit test, cited, with the confirming filings named where an
    exit actually fired. Citing the confirming readings is what lets the
    reader check the confirmation rule instead of taking it on trust.

    The fall in returns is cited beside the floor it is compounded with,
    always, and not only when it fires — the two are one test and a reader
    shown one of them has been shown half a rule.

    Where the host established a breach by dropping a year rather than by
    counting filings, that reading is cited as well. A verdict reached on a
    recomputation the reader cannot see is a verdict they have to believe.
    """
    out = []
    for i, ((measure_id, comparator, value_id), f) in \
            enumerate(zip(EXITS, states)):
        out.append(_cite(measure_id, comparator, value_id, group))
        if i == ROIC:
            out.append({**ROIC_DRIFT, "group": group})
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
    considering it are different questions rather than two systems. Below
    that fork the order is a single ladder with one exit at each rung, so no
    two conclusions can ever both be true.
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
    against — the host resolves the same `threshold_from` when it works out
    the rollup the reader sees.
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
    answered — did a knockout fail, is any dimension short, was anything
    unreadable, and what should be cited — and a holding asks them in exactly
    the same way a candidate does. An add is the same claim about the same
    business made again, and the only honest way to make it is against the
    same bar.
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
        "unmet": [d for d in dims if not d["met"]],
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
    """How the dimensions came out, in a clause a verdict can carry.

    It states the count AND that the count is not what was demanded, because
    a reader who has been shown "eight of ten" will otherwise carry away the
    quota this arrangement exists to replace.
    """
    return (f'{screen["passed"]} of the {screen["tested"]} tests behind them '
            "passed")


def _on_a_candidate(ctx):
    values = ctx.get("values") or {}
    screen = _entry_screen(ctx)

    # A knockout that failed, or a question about the business that cannot be
    # answered even if every unreadable row under it came back clear. Either
    # is a settled no — and the three questions are deliberately NOT cited
    # here, so nobody is asked to assess the durability of a business their
    # own rules have already rejected.
    #
    # Which dimension fell short is named rather than counted. "Six of ten
    # passed" was true under the old quota and told a reader nothing about
    # what to go and look at; "nothing here answers what it owes" tells them
    # where the business failed, which is the whole point of grouping.
    if screen["settled_no"]:
        return {
            "state": "not-wonderful-enough", "payload": {},
            "reason": {
                "rule": ("knockout-failed" if screen["req_fail"]
                         else "dimension-short"),
                "summary": (
                    f'{screen["req_fail"]} of the {len(REQUIRED)} tests this '
                    "strategy will not bend came back against it, and one is "
                    "enough."
                    if screen["req_fail"] else
                    "This strategy asks six separate questions about a "
                    "business and needs every one of them answered. "
                    + ("One is" if len(screen["short"]) == 1
                       else f'{len(screen["short"])} are')
                    + " not: " + _names_of(screen["short"])
                    + f'. Across all six, {_covered(screen)}, and no amount '
                      "of passing elsewhere settles the "
                    + ("one that is short."
                       if len(screen["short"]) == 1 else "ones that are "
                       "short.")),
                "evidence": screen["evidence"], "groups": screen["groups"],
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
                "evidence": screen["evidence"], "groups": screen["groups"],
            },
        }

    # The numbers pass. Now the part no filing can answer — and citing the
    # three is what puts them on this page with a way to answer each.
    judged_cites, judged_out = _judgements(ctx, QUALITY_GROUP["id"])
    evidence = screen["evidence"] + judged_cites
    groups = screen["groups"] + [QUALITY_GROUP]

    said_no = _marked_down(judged_out)
    if said_no:
        return {
            "state": "you-marked-it-down", "payload": {},
            "reason": {
                "rule": "you-answered-no",
                "summary": (
                    "It answers every question this strategy asks about "
                    "the business and passes every test it will not bend — "
                    f"{_covered(screen)} — "
                    "and you have marked "
                    + ("one of the three questions" if len(said_no) == 1
                       else f"{len(said_no)} of the three questions")
                    + " a fail. Your assessment decides this, not the "
                      "numbers."),
                "evidence": evidence, "groups": groups,
            },
        }

    owed = _unanswered(judged_out)
    if owed:
        return {
            "state": "judgement-owed",
            # No list of what is owed here. The host builds those lines
            # from the questions this decision cited that came back
            # unanswered — see contract._owed_by — in the bank's own words,
            # which are the words the rows under this verdict and the
            # section it sends the reader to already carry. This file used to
            # keep a hand-written paraphrase of each of the three, with a
            # fallback that printed the raw bank id, because the context
            # handed over a value and not a label. It cites them instead now,
            # which is what it should have been doing.
            "payload": {"needs": [
                "Answer them under \"Your judgement\" on this page. Each one "
                "takes a pass or a fail and your reasoning in your own "
                "words, and the reasoning is what makes the record worth "
                "reading back in five years.",
                "Leaving one unanswered is not a fail and is not held "
                "against the company. It simply is not an answer, and this "
                "strategy will not put money behind a question nobody "
                "asked."]},
            "reason": {
                "rule": "questions-unanswered",
                "summary": (
                    "Every number this strategy checks is in order — all "
                    "six questions about the business answered, "
                    f"{_covered(screen)}, and all {len(REQUIRED)} tests it "
                    "will not bend. What decides it now is "
                    + ("a question" if len(owed) == 1 else f"{len(owed)} "
                       "questions")
                    + " no filing can answer, and only you can."),
                "evidence": evidence, "groups": groups,
            },
        }

    # It passes and you have said yes to all three. What remains is whether
    # there is room for it, and how much.
    slots = values.get("portfolio-slots")
    cap = values.get("position-weight-cap")
    evidence = evidence + [ROOM_CITE]
    groups = groups + [SIZING_GROUP]

    if contract.test(ctx, ROOM_CITE) == FAIL:
        return {
            "state": "no-room", "payload": {},
            "reason": {
                "rule": "at-capacity",
                "summary": (
                    f"It passes every test and you have answered all three "
                    f"questions yes, and all {slots} of the places this "
                    "strategy runs are taken. Nothing here swaps one holding "
                    "for another — a place opens when one of your positions "
                    "closes."),
                "evidence": evidence, "groups": groups,
            },
        }

    # Both settings ship a default, are typed, and are bounded away from
    # zero by the declaration; a journal override that broke either is
    # refused before decide() is ever called.
    size, bound = _first_purchase_size(values)
    evidence = evidence + _sizing_cites(SIZING_GROUP["id"]) + [
        {"label": "Size this buy", "unit": "percent", "actual": size,
         "group": SIZING_GROUP["id"]}]
    return {
        "state": "wonderful-and-priced",
        "payload": {"size": {"unit": "weight", "value": size},
                    "condition": None,
                    # This strategy stages nothing. Buying a wonderful
                    # business in thirds against a falling price is a rule it
                    # does not have, and inventing one here so a screen had
                    # something to render would be putting a recommendation
                    # into shipped content.
                    "plan": None},
        "reason": {
            "rule": "worth-owning",
            "summary": (
                "Every test this strategy will not bend passed, all six "
                "questions about the business are answered — "
                f"{_covered(screen)} — and you have answered all three "
                "questions only you can. The size is "
                f"{size:g}% of the account, set by {bound}."),
            "evidence": evidence, "groups": groups,
        },
    }



# -- sizing ------------------------------------------------------------------
#
# Two different questions with two different answers, and the gap between
# them is what makes this strategy concentrate.
#
# A FIRST purchase takes an equal share of the places this strategy runs —
# one tenth of the account across ten names. That is a starting size and
# nothing more: at the moment of a first purchase there is no evidence about
# this holding that a screen has not already reported.
#
# An ADD goes toward the cap instead, which is four times larger. That is the
# concentration rule and it is deliberate: money goes to what has kept
# proving itself, not back toward an average. Every add has to pass every
# entry test and all three of your own assessments again on the day it is
# made, so the route from ten percent to forty runs through the whole list
# several times.
#
# Nothing about what the position cost is available to either of them. The
# host does not offer it, so a rule that put more money in because the price
# had fallen below what you paid cannot be written here — and that rule is
# the failure mode this whole screen was built against.

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
              {"fact": "position.months_held", "group": TIME_GROUP["id"]})


def _on_a_holding(ctx):
    values = ctx.get("values") or {}
    states = _exit_states(ctx, DECAY_GROUP["id"])
    judged_cites, judged_out = _judgements(ctx, QUALITY_GROUP["id"])

    evidence = _exit_evidence(DECAY_GROUP["id"], states) + judged_cites \
        + list(TIME_CITES)
    groups = [DECAY_GROUP, QUALITY_GROUP, TIME_GROUP]

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

    # The ladder. The measured exits before the assessed one, because a
    # confirmed breach across filings is evidence and a mark is an opinion —
    # and because leverage is the thing that takes the business away from you
    # while a leaking moat only takes the returns. Both close the position;
    # the state says which happened, and either way all of it is cited.
    broken = [f for f in states if f["confirmation"] == CONFIRMED]
    if broken:
        return {
            "state": "business-broken",
            "payload": {"when": ctx["today"]},
            "reason": {
                "rule": "exit-confirmed",
                "summary": (
                    f"{len(broken)} of the {len(EXITS)} tests that can end "
                    "this position " + ("has" if len(broken) == 1 else "have")
                    + f" failed{_confirmed_on(broken)}. Nothing about the "
                    "price decided it — no price ever can here."
                    + also_waiting()),
                "evidence": evidence, "groups": groups,
            },
        }

    said_no = _marked_down(judged_out)
    if said_no:
        return {
            "state": "stopped-being-wonderful",
            "payload": {"when": ctx["today"]},
            "reason": {
                "rule": "you-answered-no",
                "summary": (
                    "You have marked "
                    + ("one of the three questions" if len(said_no) == 1
                       else f"{len(said_no)} of the three questions")
                    + " a fail on a business you own. The reason to hold "
                      "this was that it was worth owning, and your own "
                      "assessment now says it is not. Your reasoning is "
                      "below." + also_waiting()),
                "evidence": evidence, "groups": groups,
            },
        }

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
    # sentence saying everything came back clear, and both are true. Said
    # here rather than left to the reader, because "clear" is the claim they
    # will believe and the row is the thing they will see.
    half = _half_failed(ctx, DECAY_GROUP["id"], states)
    if half:
        clear = f"{clear} {half}"
    return _more_money(ctx, values, evidence, groups, clear, judged_out)


# -- may more money go into a name you already own ---------------------------

def _more_money(ctx, values, evidence, groups, clear, judged_out):
    """Reached only when nothing above it fired: every exit that could be
    read came back clear and nothing has been marked down.

    So this asks one question, and it is deliberately not "is this a good
    idea" — it is "would this strategy buy this today, is it still what you
    said it was, and is there room".
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
    # The weight itself, cited and not merely spoken about. It is the figure
    # every sentence below is measured against, and citing it is what lets a
    # reader ask what a position weight is and where this one came from
    # without leaving the screen.
    #
    # Cited as an observation and NOT as a test, deliberately. A row reading
    # "at most your 40%" beside a holding at 49% would render as a failure,
    # and a reader would reasonably take a failed row about position size to
    # mean something is owed. Nothing is: this strategy has no trim, the cap
    # binds on purchases only, and a group demanding a pass here would refuse
    # every add on a position that had done well.
    sizing = _sizing_cites(SIZING_GROUP["id"]) + [
        {"fact": "position.weight", "group": SIZING_GROUP["id"]},
        {"label": "Room left under your cap", "unit": "percent",
         "actual": room, "group": SIZING_GROUP["id"]}]

    if room <= 0:
        return held(
            "no-room-to-add",
            # One decimal, matching how the same figure renders in the row
            # below it. A weight printed at full precision reads as a
            # measured quantity rather than a share of an account that moves
            # every time the market opens.
            f"It is already {float(weight['value']):.1f}% of the account, "
            f"against the {cap:g}% most this strategy will take one name to "
            "by buying, so no more money goes into it here. Nothing is being "
            "trimmed — this strategy has no trim, and a position that has "
            "grown large by compounding is what it is trying to produce.",
            sizing, [SIZING_GROUP])

    # The three questions, before the numbers this time. On a candidate the
    # numbers are asked first so nobody assesses a business their rules have
    # rejected; on a holding the rules already accepted it, you already own
    # it, and an unanswered question is the more interesting fact.
    owed = _unanswered(judged_out)
    if owed:
        return held(
            "questions-unanswered",
            "There is room for more of it and "
            + ("one of the three questions" if len(owed) == 1
               else f"{len(owed)} of the three questions")
            + " this strategy asks has no answer on record, so nothing more "
              "goes in. They are listed under \"Your judgement\" below. "
              "Nothing is owed on the position you have — this is a bar on "
              "adding to it, not a verdict on holding it.",
            sizing, [SIZING_GROUP])

    screen = _entry_screen(ctx)
    body = (screen["evidence"] + sizing, screen["groups"] + [SIZING_GROUP])

    if screen["settled_no"]:
        return held(
            "would-not-buy-it-today",
            "Your rules would not buy this today: "
            + (f"{screen['req_fail']} of the {len(REQUIRED)} tests this "
               "strategy will not bend came back against it"
               if screen["req_fail"] else
               "nothing here answers " + _names_of(screen["short"]))
            + f", and {_covered(screen)}. Holding what you have is a "
            "different question, and every exit test above came back clear — "
            "a business that has stopped being cheap enough to buy again is "
            "not a business that has stopped being worth owning.",
            *body)

    if not screen["met"]:
        missing = screen["req_unknown"] + screen["unknown"]
        return held(
            "screen-unreadable",
            f"Whether your rules would buy this today could not be settled: "
            f"{missing} of the tests that decide it could not be worked out "
            "from the data on record. Nothing more goes in on a screen that "
            "did not finish — an unreadable test is not a passing one.",
            *body)

    return {
        "state": "room-for-more",
        "payload": {"size": {"unit": "weight", "value": room},
                    "condition": None, "plan": None},
        "reason": {
            "rule": "still-worth-owning-and-has-room",
            "summary": (
                f"{clear} It would still be bought at today's price — "
                "every question about the business answered, "
                f"{_covered(screen)} — your three answers still stand, "
                f"and it sits {room:.1f}% of the account below the {cap:g}% "
                "most this strategy will take one name to. That room is the "
                "whole of what may go in; where it goes is a question about "
                "your other holdings, not about this one."),
            "evidence": evidence + screen["evidence"] + sizing,
            "groups": groups + screen["groups"] + [SIZING_GROUP]},
    }
