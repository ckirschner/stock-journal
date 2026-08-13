"""Graham — buy a statistical discount, sell when it closes or the clock runs.

An ordinary or mediocre business bought so far below what its assets and
earnings justify that the business quality stops mattering. There is no
quality thesis here and there is not meant to be one: the reason to own the
security is that it is cheap against its own book and its own typical
earnings, and the reason to sell it is that it has stopped being cheap.

Three things follow from that, and they are the whole shape of this file.

**The valuation tests have exits.** This is where Graham and a
buy-and-hold-forever strategy genuinely part company. When the discount
closes, the reason to own the security is gone, and holding on means
switching to a thesis that was never tested.

**Nothing fires on noise, and what counts as noise is the measure's
business rather than this file's.** One goodwill impairment, one legal
settlement, one inventory build, and a measure crosses a line because of
something that happened once — and a tool whose purpose is preventing panic
decisions must not use its own authority to cause one. What it takes to
believe a crossed line is asked of the host, which knows how each of these
eight measures is read. Seven of them are readings at a moment — a balance
sheet is one morning's photograph, and a multiple against a price is a new
number every day — so a second filing genuinely says something the first
did not, and the report's two consecutive filings stand. The eighth counts
annual reports, and a level of two losing years already means two annual
filings; asking for two filings on top of it would be asking for a third
year. A crossed line that is not yet established is a state of its own, so
the user can see the rule declining to panic rather than seeing nothing at
all.

**There is a clock.** Sell after two years regardless of what happened. No
measure can hold "it has been two years", and without it there is no exit
for a security that simply stays cheap — which is the single most common way
this style of investing fails.

And one thing it will not do at all. **It does not evaluate banks, lenders,
insurers or property companies**, and the refusal is permanent — see
DECLINES. The tests below are not a philosophy implemented through metrics;
they *are* the metrics, and the spine of them is a balance sheet split into
what falls due within the year and what does not. Three kinds of filer do not
publish one. Substituting measures built for them would produce something
that is not this strategy, so it says so instead of producing a verdict that
looks like a judgement about the business and is not.

Sources, and which is which, because a reader auditing a number later has
to be able to tell. Every value carries its own `source` saying so, which
is where to look rather than here: this paragraph is the version that used
to have to be believed, and a claim made once at the top of a file is a
claim nobody can check against the twenty-ninth value somebody adds.

Twenty-six of the thirty-four thresholds below are the expert report's,
verbatim — nothing is rounded, converted or adjusted. Six of those carry
the report's level and this strategy's reasoning, and say so. Two more,
`portfolio-slots` and `position-weight-cap`, come from Graham's own
documented practice, because the report was scoped to selection and to exits
and says nothing whatever about how much to buy. The last six — the risk-free
rate and the five drift tolerances — are attributed to nobody but this
file's author, because no source here addresses adding to a position already
held, and they are the numbers most worth arguing with.

Nothing here computes a comparison. Every test is put to `contract.test` and
then cited as the same item, so what a rule acted on and what the reader
sees are one answer rather than two that agree until they do not.
"""

from engine import contract

# ---------------------------------------------------------------------------
# The tests, as data.
#
# Each row is (bank measure, comparator, the declared value holding the
# limit). The strategy names the measure and the direction; the host reads
# the number out of the setting and answers with the figure, its unit and
# whether the comparison was met. Nothing below restates a number, and
# nothing below decides one either — `contract.test` is asked how each
# comparison came out, and the same item is then cited, so the answer the
# rule acted on and the answer the screen shows are one answer.
# ---------------------------------------------------------------------------

# Knockout. One failure kills the buy regardless of everything else.
#
# Size is here rather than among the bonus tests, and it is the one place
# this strategy overrules the arrangement of its source. The report scores
# it; the argument the report gives for the level is filing quality and the
# ability to sell when you want to, and neither of those is something a good
# score elsewhere can compensate for. A scored floor is not a floor. At $40M
# the buy went through on a company whose shares cannot be sold in the size
# this strategy would take, with a note underneath saying so — and the whole
# reason for a discipline agreed while calm is that it is not a note.
# The price ceiling is not here, and it is the only test in this file the
# strategy works out for itself — see `_price_ceiling`. Everything else names
# a measure and a setting and lets the host do the comparing.
REQUIRED = (
    ("price_to_book", "at_most", "max-price-to-book"),
    ("current_ratio", "at_least", "min-current-ratio"),
    ("revenue_ttm", "at_least", "min-revenue"),
)

# ---------------------------------------------------------------------------
# The rest of the entry tests, gathered by WHAT THEY MEASURE.
#
# This replaced a single list of eight where six had to pass. A count assumes
# its members are independent evidence, and three of these eight are three
# readings of one balance sheet while two more read one decade of earnings.
# Under a quota a company banked passes for the same strength twice and spent
# them somewhere it was weak — and the arithmetic ran that way every time, in
# the direction of buying.
#
# So the demand is coverage rather than a total. Each group below is one
# question, every group has to be satisfied, and no group's passes can be
# spent on another's. Within a group the rule follows from whether the
# members are substitutes: `all` where they measure different things,
# `at_least` where they are near-readings of one another and requiring both
# would count one piece of evidence twice.
#
# The bar in total is six of these eight, exactly as before. That is a
# coincidence of arithmetic and not the point: what changed is that the six
# can no longer all be the balance sheet.
# ---------------------------------------------------------------------------

SAFETY = (
    ("ltd_to_working_capital", "at_most", "max-ltd-to-working-capital"),
    ("altman_z_double_prime", "at_least", "min-altman-z"),
    ("debt_to_equity", "at_most", "max-debt-to-equity"),
)

RECORD = (
    ("profitable_years_10y", "at_least", "min-profitable-years"),
    ("eps_growth_10y", "at_least", "min-eps-growth-10y"),
)

CAPITAL_RETURNED = (
    ("consecutive_capital_return_years", "at_least",
     "min-capital-return-years"),
)

ASSET_BACKING = (
    ("price_to_net_tangible_assets", "at_most", "max-price-to-tangible"),
)

EARNINGS_QUALITY = (
    ("accruals_ratio", "at_most", "max-accruals-ratio"),
)

# Never block. They are reported so the reader can see them and stop there.
#
# The combined multiple is here and used to be a knockout, and the move is
# arithmetic rather than judgement. It is price-to-earnings multiplied by
# price-to-book against a ceiling that is the product of their two ceilings —
# so while both of those are demanded, this one CANNOT fail. A row that can
# never be the reason for anything is not a knockout; it is a row nobody can
# learn from, taking up the tier where the reader looks for what decided the
# verdict.
#
# It keeps its exit, where it is a genuinely separate test: on the way out
# the three levels are alternatives rather than requirements, and a holding
# at 20 times earnings and 2.8 times book trips the product at 56 while
# tripping neither of the others.
#
# Graham's own intent for it was as a RELAXATION — a low multiple of earnings
# justifying a higher multiple of assets — and this strategy does not
# implement it that way. Doing so would let a company at thirty times
# earnings through on a low price to book, which is not a company this
# strategy is for. That is a departure and it is stated rather than hidden.
BONUS = (
    ("graham_combined_multiple", "at_most", "max-combined-multiple"),
    ("ncav_to_market_cap", "at_least", "min-ncav-to-market-cap"),
)

# The exits, in two families, because they are different news. A balance
# sheet coming apart sends you to the sell button; a multiple that finally
# got fair sends you there having made money. Both close the position and
# the state says which happened.
#
# Each is written as what the holding must KEEP being true, not as the
# condition that ends it, and the exit is that requirement failing. The two
# are the same rule and only one of them reads correctly on screen: a
# healthy holding cited against "sell at or above 3.0 times book" comes back
# as eight red failures beside a verdict of hold, and a reader learns
# exactly the wrong thing from it. Cited as "stay below 3.0", the same
# holding is eight passes and a breach is the one that is not.
#
# Nothing here says how much evidence a breach needs, and there used to be a
# fourth column that did. How many readings it takes to believe one is a
# property of the measure — of how a five-year median moves against how a
# balance-sheet date moves — and the host derives it from what the metric
# bank declares about each. See contract.ESTIMATORS.
#
# The column that went was the run of annual losses saying it counted its own
# filings, which was true and is now true for a better reason: the bank says
# that measure is a count of annual reports, so its level already carries the
# persistence and the host asks for no repetition on top. What was a special
# case worked out inside this file is a fact about the measure everywhere.
EXITS_SAFETY = (
    ("current_ratio", "at_least", "exit-current-ratio"),
    ("ltd_to_working_capital", "at_most", "exit-ltd-to-working-capital"),
    ("altman_z_double_prime", "at_least", "exit-altman-z"),
    ("debt_to_equity", "below", "exit-debt-to-equity"),
    ("consecutive_annual_loss_years", "below", "exit-loss-years"),
)

EXITS_DISCOUNT = (
    ("pe_3y_avg_eps", "below", "exit-pe-3y-avg"),
    ("price_to_book", "below", "exit-price-to-book"),
    ("graham_combined_multiple", "below", "exit-combined-multiple"),
)

# The run of years returning capital is watched but never acts. A break in it
# is real information about distress, and by the time it lands the
# balance-sheet exits will already be talking; it should send the reader to
# the filings, not to the sell button.
#
# It watches the same measure the entry test demands twenty years of, so a
# company that stops paying AND stops buying back is what breaks it. That is
# a later and stronger signal than a dividend cut alone — a company that
# suspends its dividend while continuing to repurchase has not stopped
# returning capital, and flagging it would send a reader to the filings over
# a change of route.
CAPITAL_RUN = "consecutive_capital_return_years"

# What must not have moved too far since a purchase, before more money goes
# into the same name.
#
# The exits above are absolute: a current ratio below 1.2 is a sell whatever
# it was when you bought. These are relative, and they exist because an
# absolute level cannot see the shape this style of investing actually fails
# in. A company bought at a current ratio of 3.1 that is now at 1.4 has not
# tripped a single exit and is a different company from the one that was
# bought. Nothing anywhere compared it against itself, because every quarter
# looked acceptable against the quarter before it.
#
# The limit is the CHANGE, signed, so nothing here has to be negated — the
# host reads the number out of the setting exactly as it reads every other
# limit, and a reader sees "change since you first bought: -0.55, at least
# your -0.4". A tolerance stated as a magnitude with the direction hidden in
# the comparator is a limit whose sign lives in this file instead of in the
# setting, which is the half nobody thinks to check when they retune it.
#
# The same five tolerances answer two different questions, from two different
# anchors, and that is the whole reason the host offers both:
#
#   since the FIRST purchase   how far it has drifted in total. Failing this
#                              does not sell anything; it demands a fresh
#                              read before any more money goes in.
#   since the LAST purchase    whether it has got worse since you last looked
#                              at this business and said yes. Failing this
#                              stops the add and nothing else — you already
#                              own it, and a decline you have not yet
#                              re-underwritten is not grounds for an exit the
#                              absolute levels have not called for.
#
# One set of numbers because the question each answers is the same question —
# how much movement in this measure means something has changed — asked from
# two places. On a position bought once they are the same test, and the day
# they part company is the day of the second purchase.
DRIFT = (
    ("current_ratio", "at_least", "drift-current-ratio"),
    ("ltd_to_working_capital", "at_most", "drift-ltd-to-working-capital"),
    ("altman_z_double_prime", "at_least", "drift-altman-z"),
    ("debt_to_equity", "at_most", "drift-debt-to-equity"),
    ("consecutive_annual_loss_years", "at_most", "drift-loss-years"),
)

# ---------------------------------------------------------------------------
# The headings the evidence is gathered under, and what each demands.
#
# The grouping IS the rollup. Four knockouts where every one has to pass, six
# of eight core tests, three that are reported and never block — that is the
# whole shape of the entry rule, and before a group could say it the shape
# lived in the order of the list plus a count the strategy tallied itself. A
# reader looking at fifteen rows could not tell which four were
# disqualifying, and nothing stopped the tally disagreeing with the rows.
#
# The host counts, so it cannot. `core-tests-required` is cited rather than
# stated, for the same reason every other limit here is.
# ---------------------------------------------------------------------------

KNOCKOUTS = {"id": "knockouts", "name": "Tests this strategy will not bend",
             "requires": "all"}

SAFETY_TESTS = {"id": "safety-tests",
                "name": "What the balance sheet can carry",
                "requires": "at_least",
                "threshold_from": "safety-tests-required"}
RECORD_GROUP = {"id": "record", "name": "The ten-year earnings record",
                "requires": "at_least",
                "threshold_from": "record-tests-required"}
RETURNED_GROUP = {"id": "returned",
                  "name": "Whether it has paid its owners, and for how long",
                  "requires": "all"}
BACKING_GROUP = {"id": "backing",
                 "name": "What you pay per dollar of real assets",
                 "requires": "all"}
QUALITY_TESTS = {"id": "quality-tests",
                 "name": "Whether the reported profit is cash",
                 "requires": "all"}

# In the order they are asked, cited and drawn: the balance sheet first,
# because it is the whole reason an unremarkable business is acceptable here.
DIMENSIONS = (
    (SAFETY_TESTS, SAFETY),
    (RECORD_GROUP, RECORD),
    (RETURNED_GROUP, CAPITAL_RETURNED),
    (BACKING_GROUP, ASSET_BACKING),
    (QUALITY_TESTS, EARNINGS_QUALITY),
)

BONUS_GROUP = {"id": "bonus", "name": "Reported, never blocking",
               "requires": "noted"}
SIZING_GROUP = {"id": "sizing", "name": "Room in the list, and how much",
                "requires": "all"}

# On a holding, the two exit families are `noted`: the host reports how each
# came out and this strategy decides what to do about the ones that are
# established. It is the ladder below that acts, not the rollup, because a
# single failed exit closes a position and no count of them says more than
# that. What the group names is which kind of news they are.
SAFETY_GROUP = {"id": "safety",
                "name": "The balance sheet and the earnings record",
                "requires": "noted"}
DISCOUNT_GROUP = {"id": "discount", "name": "The discount you bought",
                  "requires": "noted"}
CLOCK_GROUP = {"id": "clock", "name": "The holding period", "requires": "all"}
SIZE_GROUP = {"id": "size", "name": "How big it has got", "requires": "all"}
DIVIDEND_GROUP = {"id": "dividend", "name": "The run of capital returned",
                  "requires": "noted"}

# The two drift families, and both demand `all`. That is not decoration: a
# state whose render is `commit` is refused by the host when a group it
# declared did not come out passed, so "no more money goes in until this is
# still true" is enforced by the contract rather than by this file
# remembering to check. An unreadable row is not good enough either — a
# baseline nobody could recover has not shown that nothing has changed, and
# treating it as though it had is exactly the absence-reads-as-success this
# whole arrangement exists to refuse.
DRIFT_GROUP = {"id": "drift",
               "name": "How far it has drifted since you first bought",
               "requires": "all"}
WORSE_GROUP = {"id": "worse",
               "name": "What has changed since you last bought",
               "requires": "all"}


# ---------------------------------------------------------------------------
# Where the numbers came from.
#
# `name` is what to check a threshold against; `reasoning` says whether the
# account in that value's own `explain` is the source's or this strategy's.
#
# The distinction is the whole reason these are fields and not prose. Six of
# the thirty-four values here have the report's level and an explanation
# this strategy wrote, and that used to be a paragraph pasted into six
# `explain` strings — which is a claim nothing checks, on a value it is easy
# to add a seventh of and forget. Two more come from somewhere else
# altogether. Now every value says which it is, in the same place, in a shape
# a screen can render without reading English.
# ---------------------------------------------------------------------------

_REPORT = "the expert report commissioned for this strategy"

REPORT = {"name": _REPORT, "reasoning": True}
REPORT_LEVEL_ONLY = {"name": _REPORT, "reasoning": False}

# The second expert review of the profile document, which read that report
# and disputed it in every profile. Where a level cites this rather than the
# report, the report's own number was overruled and the value says why in its
# own `explain`.
REVIEW = {
    "name": "the second expert review of the profile document, held at "
            "dev_reference_docs/ledger-default-profiles-addendum.md, which "
            "disputes this level in the report it reviewed",
    "reasoning": True}
GRAHAM_PRACTICE = {
    "name": "Graham's own documented practice in The Intelligent Investor. "
            "The expert report was scoped to selection and to exits and says "
            "nothing whatever about how much to buy, so its silence here is "
            "a gap in the source rather than a decision it made",
    "reasoning": True}
# Nobody's but this file's. The drift tolerances have no source to cite:
# neither the report nor Graham addresses adding to an open position, and
# saying so plainly is better than attributing a number to a document that
# does not contain it. These are the settings here most worth arguing with,
# and the attribution is what makes that visible.
AUTHOR = {
    "name": "this strategy's own author. Neither the expert report nor "
            "Graham addresses adding to a position already held, so there is "
            "no source to attribute these to and none is claimed",
    "reasoning": True}


# ---------------------------------------------------------------------------
# The kinds of company this strategy does not evaluate, and why each refusal
# is permanent rather than a gap waiting on data.
#
# This is not a judgement that banks, insurers or property companies are poor
# investments. It is the narrower and more awkward statement that THIS RULE
# SET is not a philosophy implemented through metrics — it *is* the metrics,
# and specifically the liquidation-oriented balance sheet. Fifteen entry tests
# and eight exits, and the spine of them is what the company owns that could
# be turned into cash inside a year against what it owes inside that year.
# Take that away and substitute something else and the result is not a
# stricter Graham or a looser one; it is a different strategy wearing the
# name, and the whole value of committing to one set of rules is that they
# stay the ones you committed to.
#
# So these do not lift when better measures arrive. Bank measures would let
# something be evaluated here; they would not make it Graham. There is
# precedent rather than retreat in that: Greenblatt's published method
# excludes financials and utilities outright, for exactly this reason.
#
# What is deliberately not refused: asset managers, exchanges, insurance
# brokers and estate agents. Those are ordinary fee businesses with ordinary
# balance sheets, and several of them screen well here. A refusal aimed at
# everything financial-sounding would be this strategy declining companies it
# is perfectly capable of judging.
DECLINES = [
    {"class": "depository-lending",
     "because": "A bank does not divide its balance sheet into what falls due "
                "within the year and what does not, so the current ratio, "
                "long-term debt against working capital, the distress score "
                "and the net-current-asset test — four of the fifteen tests "
                "that buy, and three of the eight that sell — have nothing to "
                "read. That division is not incidental to this strategy. It "
                "is the strategy: the whole reason an unremarkable business "
                "is acceptable here is that its liquid position carries the "
                "risk its operations cannot, and there is no reading of a "
                "lender's accounts that answers that question. Substituting "
                "measures built for banks would produce something that is "
                "not this strategy."},
    {"class": "insurance",
     "because": "An insurer's balance sheet is an investment portfolio held "
                "against claims not yet made, and it is not split into "
                "current and non-current either — so the same four "
                "liquidity tests that make this strategy what it is have "
                "nothing to read. Book value, which two of the knockouts "
                "rest on, is whatever the reserve estimates say it is, and "
                "the estimate is the thing an outsider cannot check. This "
                "strategy buys on the published balance sheet being close to "
                "literally true; here it is an actuarial opinion."},
    {"class": "real-estate",
     "because": "The accounts charge depreciation against buildings as "
                "though they wear out, and well-kept property mostly does "
                "not — so reported earnings understate by design, and every "
                "test here that prices a company against its earnings reads "
                "as expensive when it is not. The industry's own answer is a "
                "different profit figure entirely, which this program does "
                "not compute. High borrowing is also the normal condition of "
                "a property company rather than a warning, so the leverage "
                "tests refuse every one of them for a reason that is not "
                "about the company."},
]


# What the METHOD asks for or admits to that this program does not do.
#
# Separate from DECLINES, which is about a kind of company these tests cannot
# read. This is about the method, and the first of the two is the one most
# likely to be experienced as the tool being broken.
LIMITS = [
    {"title": "Returning nothing for years is this strategy working",
     "body": "**Against a realistic set of US companies these tests will "
             "produce no candidates at all, for years at a time.** That is "
             "faithful rather than broken, and it is worth understanding "
             "before you are tempted to loosen anything.\n\n"
             "Graham's own programme was never a stock-selection rule set "
             "standing on its own. It sat inside an allocation between "
             "shares and bonds — never less than a quarter in either, "
             "rebalanced as prices moved — and he was explicit that in an "
             "expensive market the criteria would find nothing, and that "
             "this was the signal to hold more bonds rather than to relax "
             "the criteria. The empty screen was the output. It was telling "
             "you where the money should be.\n\n"
             "**This program does not implement that allocation and cannot "
             "tell you to hold bonds.** It has no view of your account "
             "beyond what you tell it and it does not know what else you "
             "own. So the half of the method that gave an empty screen its "
             "meaning is missing here, and what is left looks like a tool "
             "that has stopped working.\n\n"
             "If you take one thing from this page: when this strategy has "
             "nothing to buy for a long stretch, the answer the method "
             "gives is to hold more in something safe and wait. It is not "
             "to lower a threshold. A level moved during a drought is a "
             "level moved at the exact moment you had the least reason to "
             "trust yourself, which is the whole thing a written-down rule "
             "exists to prevent."},

    {"title": "It is a portfolio method, and this is one security",
     "body": "This method buys a statistical discount, and statistics is "
             "the operative word. Graham expected a meaningful share of "
             "these positions to disappoint and said so plainly; the "
             "arithmetic works because a diversified set of them works on "
             "average, not because any one of them was correctly "
             "picked.\n\n"
             "**A verdict on this page is about one security, and no method "
             "here can tell you that one will work.** A buy verdict says "
             "this security is cheap against its own assets and its own "
             "typical earnings by the standard you set while you were calm. "
             "Some of the companies that pass will be cheap because "
             "something is wrong that no filing shows.\n\n"
             "It is also why the number of names this strategy holds is a "
             "setting rather than a suggestion. Twenty positions at five "
             "percent each is not timidity — it is the mechanism by which "
             "a method with an expected loser rate is supposed to work."},
]


STRATEGY = {
    "id": "graham",
    "name": "Graham",
    "summary": "Buys an ordinary business only when its price is far below "
               "what its assets and its typical earnings justify, and sells "
               "when that gap closes, when the balance sheet stops being "
               "safe, or when two years are up — whichever comes first.",
    "version": 8,
    "contract": 6,
    "declines": DECLINES,
    "limits": LIMITS,
    "changelog": {
        8: "A SECOND EXPERT REVIEW READ THE REPORT THIS STRATEGY WAS BUILT "
           "FROM AND DISPUTED IT. This version is that review's "
           "corrections, and every one of them changes what this strategy "
           "will buy.\n\n"
           "THE TWO PRICE TESTS CONTRADICTED EACH OTHER AND THE STRICTER "
           "ONE NEVER DECIDED ANYTHING. A ceiling of fifteen times typical "
           "earnings sat among the knockouts while the rule that the "
           "earnings yield must beat the bond yield twice over sat among "
           "the rows that never block — and above a bond yield of about "
           "3.3% the second is the stricter. So in every environment since "
           "this shipped, the strategy was quietly running the looser rule "
           "because of where the two happened to sit. There is now one "
           "test, and its ceiling is the stricter of the two rules. At the "
           "shipped 5% bond yield that is a price of at most ten times "
           "typical earnings rather than fifteen, which is a materially "
           "harder test.\n\n"
           "AND THE RATE IT COMPARES AGAINST IS NOW A CORPORATE BOND YIELD "
           "RATHER THAN A TREASURY. Graham's test was written against "
           "high-grade corporate bonds; a Treasury typically pays around "
           "0.7 to 1.0 points less, so twice a Treasury yield was "
           "materially looser than what he wrote. The setting is renamed "
           "and its shipped figure changed with it. It remains the one "
           "number here that nothing fetches and that goes wrong by "
           "sitting still — and it now sets the price ceiling on every "
           "purchase, so leaving it stale is no longer a small quiet.\n\n"
           "THE SIZE FLOOR IS ON SALES RATHER THAN ON MARKET VALUE, at "
           "$750M rather than $300M. Graham's adequate-size test was $100M "
           "of annual sales, which inflation-adjusts to roughly that; the "
           "old level was a market value defended with an argument about "
           "sales. It was also the wrong variable for this strategy in "
           "particular — a rule set hunting companies the market has "
           "priced too cheaply, which then refuses anything the market "
           "prices too low, is partly rejecting companies for being cheap. "
           "This will refuse smaller companies it used to buy.\n\n"
           "THE EIGHT SECOND-TIER TESTS ARE NOW FIVE QUESTIONS, AND EVERY "
           "ONE MUST BE ANSWERED. Six of eight had to pass. That treated "
           "the eight as eight pieces of evidence when three of them are "
           "three readings of one balance sheet and two more read one "
           "decade of earnings — so a company banked passes for the same "
           "strength twice and spent them where it was weak. Now the "
           "balance sheet, the earnings record, capital returned, asset "
           "backing and earnings quality are each satisfied on their own. "
           "The total is still six of eight, which is a coincidence of "
           "arithmetic: what changed is that the six can no longer all be "
           "the balance sheet.\n\n"
           "TWENTY YEARS OF RETURNING CAPITAL, BY EITHER ROUTE, replaces "
           "ten years of dividends. Graham's twenty was doing two jobs — "
           "evidence of capital return, and evidence of survival across a "
           "full cycle including a bad one — and cutting it to ten kept "
           "the first and threw away the second, which was the half that "
           "cannot be replaced. Counting net buybacks alongside dividends "
           "handles the 1982 change in how companies return cash without "
           "shortening the window. Buybacks count NET of issuance.\n\n"
           "THE DISTRESS SCORE IS ALTMAN'S FOUR-VARIABLE VERSION, the one "
           "he published for companies that do not manufacture, which is "
           "most of what this strategy meets. The entry level moved from "
           "3.0 to 2.6 and the exit from 1.8 to 1.1 — those are his "
           "published bands for the variant, so the DEMAND is unchanged "
           "and only the scale moved. Carrying the old numbers across "
           "would have made the exit fire far too early on every company. "
           "It also stops the score moving with the share price, which is "
           "what a solvency test inside a valuation strategy needs: "
           "otherwise a share falling for being cheap reads as a share "
           "falling for being in trouble.\n\n"
           "THE COMBINED MULTIPLE IS NO LONGER A KNOCKOUT, and this is "
           "arithmetic rather than judgement. It is the earnings multiple "
           "times the book multiple against a ceiling that is the product "
           "of their two ceilings — so while both of those are demanded, "
           "it CANNOT fail. A row that can never be the reason for "
           "anything does not belong at the tier where a reader looks for "
           "what decided the verdict. It keeps its exit, where it is a "
           "genuinely separate test: on the way out the three levels are "
           "alternatives, and a holding at twenty times earnings and 2.8 "
           "times book trips this while tripping neither of the others.\n\n"
           "NOTHING ELSE MOVED, but two things are now written down that "
           "were not. The two-year clock is not from the defensive "
           "programme this strategy implements — it is from Graham's "
           "net-net work — and it is imported deliberately because "
           "otherwise nothing here answers a security that stays cheap "
           "forever. Its companion leg, sell at roughly +50%, cannot be "
           "built at all: it needs what you paid, and the host does not "
           "hand a strategy the cost of a position, deliberately, because "
           "that is the same rule that stops any strategy buying more "
           "because the price fell below your own cost. So the clock runs "
           "as the looser half of a pair. See `holding-period-months`.",
        1: "First version. The fifteen entry tests, the four-knockout / "
           "six-of-eight rollup, the eight exits with two-filing "
           "confirmation, the dividend-cut flag and the two-year clock, all "
           "as stated in the expert report. Sizing by slot count and "
           "position weight cap, attributed to Graham's own practice "
           "because the report does not cover it.",
        2: "No threshold and no rule changed. Every comparison is now put to "
           "the host rather than worked out here, so the answer a rule acts "
           "on and the answer shown beside it are one answer; the rollup is "
           "counted by the host from the rows it resolved instead of being "
           "tallied here; the holding period is counted from the host's own "
           "months-held figure; and each value now says where its number "
           "came from and whose reasoning stands behind it, which six of "
           "them were saying in prose and twenty-two were not saying at "
           "all.",
        3: "Two changes, and the first one changes what this strategy will "
           "buy. THE SIZE TEST IS NOW A KNOCKOUT. $300M was a scored test "
           "before, so a company below it could be bought as long as enough "
           "else passed — and the argument for the level was never a "
           "scoring argument. It is filing quality and being able to sell "
           "when you want to, and neither of those is made up for by a low "
           "price-to-book. A $40M company could clear every other test here "
           "and still be a position you cannot get out of. From this "
           "version a company under the floor is refused outright, and a "
           "company whose size cannot be worked out returns 'not enough to "
           "go on' rather than costing nothing. No level moved: $300M is "
           "the same $300M. The placement is this strategy's own, against "
           "the expert report, which scores this test — so the setting now "
           "says the level is the report's and the reasoning is not.\n\n"
           "SECOND, the earnings-yield test now runs. It compared the "
           "earnings yield to a risk-free rate through a measure that "
           "needed the rate handed to it, and nothing could hand one over, "
           "so from the day it shipped it was permanently unreadable — a "
           "test in name only. The rate is now a declared value on this "
           "strategy and the comparison is made here, so the test produces "
           "a real answer for the first time. It is still a bonus test and "
           "still blocks nothing, but it will now show passes and failures "
           "where it used to show nothing at all. The rate ships at a "
           "starting figure and is the one setting here that has to be "
           "maintained: nothing fetches it.",
        4: "This strategy can now add to a position you already hold, which "
           "it never could before — a holding was watched only for exits, so "
           "'buy' was unreachable the moment you owned any of it.\n\n"
           "An add is the entry tests, unchanged. The same five knockouts "
           "and the same eight core tests decide it, measured exactly as "
           "they would be on a security you had never owned, because an add "
           "is the same claim about the same business made again. What is "
           "new is room: a holding may only be taken up to the same target "
           "weight a first purchase is sized to, and the gap between where "
           "it is and where that target sits is the whole of what may go "
           "in. Nothing about what the position cost is available to any of "
           "it — the host does not offer it, so an add cannot be triggered "
           "by the price having fallen below what you paid.\n\n"
           "Two new checks come with it, and they are the only new "
           "thresholds. Five measures are compared against what they were "
           "when you last bought, and against what they were when you first "
           "bought; the first stops an add on a business that has got worse "
           "since you last said yes, the second demands a fresh read of a "
           "business that has drifted a long way in total without any single "
           "quarter looking wrong. Neither sells anything. Both refuse an "
           "add when they cannot be worked out, because a comparison nobody "
           "could make has not shown that nothing changed.\n\n"
           "No existing level moved and no exit changed. A holding that "
           "would have read 'nothing to do' still does, unless it now has "
           "room and still screens — in which case it says so, and the "
           "reason names which of the several ways an add was refused.",
        5: "No threshold and no rule changed, and no verdict moves. The one "
           "state that stops and waits for you — the bar on adding to a "
           "holding that has drifted — now says where what it asks for is "
           "written down, so the host puts a button on the verdict instead "
           "of the reader having to know which record a fresh read of a "
           "business belongs in. Writing one still does not lift the bar: "
           "nothing does but selling and buying again, which is what the "
           "bar is for.",
        6: "THIS STRATEGY NO LONGER EVALUATES BANKS, LENDERS, INSURERS OR "
           "PROPERTY COMPANIES. No threshold moved and no test changed; what "
           "changed is that three kinds of company now get a refusal instead "
           "of a verdict.\n\n"
           "It was producing verdicts on them, and the verdicts were "
           "arithmetic laid over accounts the tests were never written "
           "for. Four of the fifteen entry tests and three of the eight "
           "exits read a balance sheet split into what falls due within the "
           "year and what does not — and a bank does not split its balance "
           "sheet that way at all, so those tests came back unreadable while "
           "the remaining ones went on scoring the company. A verdict of "
           "'not cheap enough' or 'not enough to go on' reads as a judgement "
           "about the business. It was not one. It was this strategy running "
           "on a company it has no way to assess, and saying so was the only "
           "honest answer available.\n\n"
           "The refusal is permanent and does not lift when better data "
           "arrives, which is the part worth arguing with. This rule set is "
           "not a philosophy that happens to be implemented through metrics; "
           "it *is* the metrics, and specifically the liquidation-oriented "
           "balance sheet. Measures built for banks would let something be "
           "evaluated here — they would not make it Graham, and the value of "
           "committing to one set of rules is that they stay the ones you "
           "committed to. Greenblatt's published method excludes financials "
           "outright for the same reason.\n\n"
           "Nothing already recorded changes: every verdict in your history "
           "was written down when it was made and is not recomputed. Nothing "
           "is being sold — a holding in one of these companies now reads "
           "'outside these rules', which asks nothing of you and blocks "
           "nothing. And recording what you decide to do is never blocked by "
           "any of this.\n\n"
           "Asset managers, exchanges, insurance brokers and estate agents "
           "are NOT refused. They are ordinary fee businesses with ordinary "
           "balance sheets, several of them screen well here, and refusing "
           "everything that sounds financial would have been this strategy "
           "declining companies it can perfectly well judge.",
        7: "TWO CHANGES TO HOW EVIDENCE IS WEIGHED. No level moved, and one "
           "setting is gone.\n\n"
           "Growth is now measured between the averages of three fiscal "
           "years at each end of the window rather than between the two "
           "single years at its ends. That is Graham's own construction — "
           "it was already how the ten-year earnings growth test worked, "
           "and now every compound rate in the program works that way. It "
           "matters most where it is least visible: a company growing 7% a "
           "year whose base year carried a one-off charge used to measure "
           "around 20%, sit comfortably inside any band, and pass. The cost "
           "is history. Eight fiscal years on one accounting basis are "
           "needed where six were before, so growth will be absent for some "
           "companies it used to answer for — a recent listing, or a "
           "restatement that was never carried back through the older "
           "years. Absent is the honest answer there, and it is not a "
           "fail.\n\n"
           "AND `sell-confirmation-filings` NO LONGER EXISTS. It said two "
           "consecutive filings for all eight exits; how much evidence a "
           "breach needs is now worked out from how each measure is read. "
           "Seven of the eight behave exactly as before — a current ratio, "
           "the debt tests and the three valuation multiples are readings "
           "at a moment, and a second filing genuinely tells you something "
           "new about them. One changed: a run of annual losses now acts on "
           "its own level, which is what it always meant, so lowering that "
           "level to one losing year now acts on one losing year instead of "
           "quietly waiting for a second.",
    },

    # -----------------------------------------------------------------
    # Thirteen states. Every one of them is something a reader has to be
    # able to tell apart from the others at a glance: "I would buy this
    # if I had room" is not "I would not buy this", and "the discount
    # closed" is not "the balance sheet broke", even though both end the
    # position.
    # -----------------------------------------------------------------
    "states": [
        {"id": "buy", "render": "commit",
         "name": "Cheap enough to buy",
         "description": "Every test this strategy will not bend has "
                        "passed, and enough of the rest have. That is not "
                        "the same as everything passing — some may have "
                        "failed and are listed below — and it is not a "
                        "claim that the business is good. It is a claim "
                        "that the price is low against what the company "
                        "owns and what it typically earns. The size is "
                        "worked out from how many names you hold at once "
                        "and how large any one of them may get."},

        {"id": "no-room", "render": "hold",
         "name": "No room for it",
         "description": "It passes. You are already holding as many "
                        "positions as this strategy runs at once, so there "
                        "is nowhere to put it. This is not a verdict "
                        "against the security — it is a fact about your "
                        "list, and it changes the day one of your holdings "
                        "closes."},

        {"id": "not-cheap-enough", "render": "hold",
         "name": "Not cheap enough",
         "description": "At least one test this strategy cannot bend has "
                        "failed, or too many of the rest have. Read which "
                        "ones below: some of these tests are about the "
                        "price, and some are about whether the company is "
                        "solid enough that its price is worth arguing "
                        "about. The two mean quite different things and "
                        "this state does not distinguish them."},

        {"id": "cannot-screen", "render": "unknown",
         "name": "Not enough to go on",
         "description": "Some of the figures this strategy needs are "
                        "missing, and the ones that are present do not "
                        "settle it either way. A missing number is not a "
                        "pass and it is not a failure, so nothing is "
                        "claimed. The reasons below say which figures are "
                        "absent and why."},

        {"id": "add", "render": "commit",
         "name": "Room for more of it",
         "description": "You hold it, every exit test came back clear, and "
                        "it still passes the tests that bought it — measured "
                        "the same way a security you had never owned would "
                        "be. It also sits below the size this strategy runs "
                        "one name at, and that gap is the whole of what may "
                        "go in.\n\n"
                        "This says the position may take capital. It does "
                        "not say to put any in, and it says nothing about "
                        "whether this is the best place for it — that is a "
                        "question about your whole list, and it is answered "
                        "on the screen that can see all of it. Nothing here "
                        "knows or can know what you paid."},

        {"id": "re-underwrite-owed", "render": "blocked",
         # What this state asks for is a fresh view of the business, and the
         # place a fresh view is written down is the thesis. Writing one does
         # not clear the bar — nothing does except selling and buying again,
         # which is the point of the bar — but it is the thing being asked
         # for, and the button says so rather than the reader having to find
         # the record it belongs in.
         "fix": "thesis",
         "name": "Read it again before adding",
         "description": "The measures this strategy watches have moved "
                        "further since your first purchase than it will put "
                        "more money behind — not on any one filing, which is "
                        "the point, but in total.\n\n"
                        "Nothing is being sold and nothing is owed on the "
                        "position you have: every exit test came back clear "
                        "and this is a bar on adding, not a verdict on "
                        "holding. What it is asking is that a fresh decision "
                        "be made deliberately rather than arrived at one "
                        "small purchase at a time."},

        {"id": "hold", "render": "hold",
         "name": "Nothing to do",
         "description": "You hold it, every exit test that could be run "
                        "came back clear, and the holding period you "
                        "committed to has not run out. Sitting still is the "
                        "whole activity.\n\n"
                        "It also covers the several ways more money does not "
                        "go in — no room left under the size this strategy "
                        "runs one name at, a business that would not pass the "
                        "tests today, a screen that could not be finished, or "
                        "a comparison against your own purchases that could "
                        "not be worked out. The rule named beside the verdict "
                        "says which, and an unreadable test is never reported "
                        "as a failed one."},

        {"id": "one-reading-past", "render": "hold",
         "name": "One reading past the line",
         "description": "An exit level has been crossed on the current "
                        "reading, and this strategy will not act on it "
                        "until the next filings say the same thing. One "
                        "impairment or one settlement can push a measure "
                        "over a line without anything having changed, and "
                        "selling on that would be the panic this is here to "
                        "prevent. Nothing is owed from you today."},

        {"id": "too-big", "render": "reduce",
         "name": "Too big a share of the account",
         "description": "This holding has grown past the largest share of "
                        "the account any one name is allowed here. Nothing "
                        "about the company has changed; the position has "
                        "just got out of proportion to the rest of the "
                        "list, and trimming it back restores the spread "
                        "this strategy relies on."},

        {"id": "discount-closed", "render": "close",
         "name": "The discount has closed",
         "description": "The gap you bought is gone: the price is now high "
                        "against this company's assets or its typical "
                        "earnings, and it has stayed that way over the run "
                        "of filings this strategy demands before acting. "
                        "The reason to own it was that gap, and holding on "
                        "from here means owning it for a reason you never "
                        "tested."},

        {"id": "safety-gone", "render": "close",
         "name": "The safety has gone",
         "description": "The balance sheet or the earnings record has "
                        "broken down, and stayed broken over more than one "
                        "reading. This strategy accepts an unremarkable "
                        "business because "
                        "the balance sheet carries the risk the operations "
                        "cannot; when that stops being true there is "
                        "nothing left holding it up. A cheap company that "
                        "goes broke is how this style of investing fails."},

        {"id": "time-is-up", "render": "close",
         "name": "The holding period is up",
         "description": "The time you committed to giving this position has "
                        "elapsed, and the exit falls due on the date shown. "
                        "This is not a judgement about the company: it "
                        "exists because a security that simply stays cheap "
                        "has no other exit, and waiting indefinitely for a "
                        "discount to close is the most common way this "
                        "approach quietly fails."},

        {"id": "cannot-watch", "render": "unknown",
         "name": "Exit checks cannot run",
         "description": "You hold it, and not one of the exit tests could "
                        "be worked out from the data on record — so this "
                        "strategy has nothing to say about whether to "
                        "stay. It is not telling you to hold; it is telling "
                        "you it cannot tell. Fetching data, or entering the "
                        "figures by hand, is what changes it."},
    ],

    "inputs": [
        # Deliberately optional. Without it the position cap simply cannot
        # be checked and says so, naming this field. Requiring it would put
        # a setup gate in front of every verdict in the journal over a rule
        # that binds on perhaps one holding in twenty.
        {"id": "free-cash", "label": "Free cash", "type": "number",
         "unit": "usd", "role": "cash", "required": False,
         "explain": "Money in the account this journal covers that is not "
                    "in any position. The journal adds it to what your "
                    "holdings are worth to get the account total, and that "
                    "total is what a position's size is measured against. "
                    "Leave it blank and the size rules say they cannot be "
                    "worked out rather than guessing at them."},
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
        # was a single count over all eight second-tier tests. See the
        # comment above SAFETY for why a count was the wrong instrument.
        #
        # There is deliberately no setting for the three groups that demand
        # all of their rows. "This must pass" is not a level anybody can
        # retune without changing what the group means, and a group that
        # could be quietly set to nought is the quota arriving by another
        # door.
        {"id": "safety-tests-required",
         "label": "Balance-sheet tests that must pass, of three",
         "type": "integer", "unit": "count", "min": 0, "max": 3,
         "source": AUTHOR,
         "explain": "This strategy reads the balance sheet three ways: "
                    "whether long-term borrowings could be covered by the "
                    "liquid cushion, what the distress score says, and how "
                    "the borrowings compare to the owners' money. This is "
                    "how many of the three have to come back clear.\n\n"
                    "Two, because they are three readings of one thing. All "
                    "three are built from the same balance sheet on the same "
                    "date and they move together — a company that has "
                    "borrowed too much fails them together, and a company "
                    "that has not passes them together. Requiring all three "
                    "would count one piece of evidence three times, which is "
                    "the fault the grouping here exists to correct. "
                    "Requiring one would let a single favourable reading "
                    "speak for a balance sheet the other two disliked.\n\n"
                    "This is the dimension that matters most in this "
                    "strategy, because the whole reason an unremarkable "
                    "business is acceptable is that its liquid position "
                    "carries the risk its operations cannot. Set it to 3 if "
                    "you want the strictest reading; set it below 2 and the "
                    "balance sheet has stopped carrying anything."},

        {"id": "record-tests-required",
         "label": "Earnings-record tests that must pass, of two",
         "type": "integer", "unit": "count", "min": 0, "max": 2,
         "source": AUTHOR,
         "explain": "This strategy asks two questions about the last ten "
                    "years of earnings: whether the company lost money in "
                    "any of them, and whether it earns meaningfully more now "
                    "than it did then. This is how many of the two have to "
                    "come back clear.\n\n"
                    "One, because they read the same decade of the same "
                    "earnings line. One is stability and one is progress, "
                    "and a company whose earnings record is distorted — by a "
                    "single dreadful year, by a restatement — has both "
                    "readings moved by the same event at the same time. Two "
                    "tests that fail together on one cause are one test.\n\n"
                    "There is a particular reason to leave room here rather "
                    "than demand both. The no-loss test is the most "
                    "punishing in this strategy and will stay that way for "
                    "years: 2020 put a shutdown loss or a non-cash "
                    "impairment on the books of a great many companies "
                    "Graham would have bought without hesitating. Requiring "
                    "both readings would let one pandemic year decide this "
                    "dimension outright."},

        # -- how much, and how many ----------------------------------------
        #
        # These two are the one place this strategy departs from its
        # source. The expert report covers what to buy and when to sell
        # and says nothing whatever about size, so its silence is a gap in
        # the source rather than a decision it made. They are attributed
        # to Graham's own documented practice instead, and say so.
        {"id": "portfolio-slots", "label": "Names held at once",
         "type": "integer", "unit": "count", "min": 1, "max": 100,
         "source": GRAHAM_PRACTICE,
         "explain": "How many separate companies this strategy holds at "
                    "one time. Each buy takes an equal share of the "
                    "account, so twenty names means about five percent "
                    "each, and once every place is taken a new candidate "
                    "is told there is no room rather than being talked "
                    "down.\n\n"
                    "Graham's own guidance is a list of somewhere between "
                    "ten and thirty names, and the twenty here sits in the "
                    "middle of it. Move toward ten and each position gets "
                    "larger, which means one company being a fraud or a "
                    "fraud-shaped accident costs you more than the rest of "
                    "the list can absorb — and this strategy deliberately "
                    "does not form an opinion about whether a business is "
                    "good, so it has nothing to offer in defence of a "
                    "concentrated bet. Move toward thirty and each position "
                    "gets small enough that the work of following it stops "
                    "paying for itself. Past thirty you own the market with "
                    "extra steps.\n\n"
                    "This figure and the position cap below are the only "
                    "two here that do not come from the expert report — it "
                    "was never asked about sizing. They come from Graham's "
                    "documented practice instead."},

        {"id": "position-weight-cap", "label": "Largest one name may get",
         "type": "number", "unit": "percent", "min": 1, "max": 100,
         "source": GRAHAM_PRACTICE,
         "explain": "The most of your account any single holding is "
                    "allowed to be. It almost never binds when you buy — an "
                    "equal share of twenty names is five percent, well "
                    "under it — and it exists for what happens afterwards, "
                    "when one name doubles and doubles again while the rest "
                    "sit still. At that point the spread you thought you "
                    "had is gone, and this is what notices.\n\n"
                    "Ten percent is the weight of one name in a list of "
                    "ten, which is the concentrated end of Graham's own "
                    "range. A position larger than that is more "
                    "concentrated than his most concentrated list, on a "
                    "business he would be the first to say he had no "
                    "particular faith in.\n\n"
                    "It needs your free cash to be answered in settings, "
                    "because a share of the account cannot be worked out "
                    "without knowing what the account is. Unanswered, this "
                    "test reports that it could not be run.\n\n"
                    "Attributed to Graham's practice, not to the expert "
                    "report, which does not cover sizing."},

        # -- how far a business may move before more money goes in ---------
        #
        # Five tolerances, stated as the worst CHANGE that will still take
        # another purchase — signed, so the direction lives in the setting
        # rather than in the code reading it. A reader retuning "-0.4" can
        # see it is a fall; a reader retuning "0.4" beside a comparator in a
        # file they never open cannot.
        #
        # Each level is roughly half the distance between what this strategy
        # requires to buy and what it requires to sell, and that is where the
        # reasoning comes from rather than from any source. Halfway from
        # "would buy" to "would sell" is a business that has changed enough
        # to be worth reading about again, and not so far that a normal
        # quarter trips it. The expert report was scoped to selection and to
        # exits and says nothing about adding, so nothing here is attributed
        # to it — these are the author's, and they are the settings in this
        # file most worth arguing with.
        {"id": "drift-current-ratio",
         "label": "Worst change in the current ratio you will add behind",
         "type": "number", "unit": "ratio", "max": 0, "source": AUTHOR,
         "explain": "How far the current ratio — what a company owes within "
                    "the year against what it can readily turn into cash — "
                    "may fall from where it was at a purchase before this "
                    "strategy stops putting more money in.\n\n"
                    "A negative number, because it is a fall. Minus 0.4 is "
                    "about halfway from the 2.0 this strategy requires to "
                    "buy to the 1.2 at which it sells: a company that has "
                    "come that far has used up half the cushion that made it "
                    "worth owning, without having crossed any line that "
                    "would exit it.\n\n"
                    "Move it toward zero and almost any decline stops you "
                    "adding. Move it away and the position can double while "
                    "the balance sheet quietly halves."},

        {"id": "drift-ltd-to-working-capital",
         "label": "Worst change in long-term debt against working capital "
                  "you will add behind",
         "type": "number", "unit": "ratio", "min": 0, "source": AUTHOR,
         "explain": "How much further long-term debt may climb against "
                    "working capital, from where it was at a purchase, "
                    "before this strategy stops adding.\n\n"
                    "A positive number, because on this measure it is the "
                    "rise that is bad. Half a turn is about halfway from the "
                    "1.0 required to buy to the 2.0 that sells."},

        {"id": "drift-altman-z",
         "label": "Worst change in the distress score you will add behind",
         "type": "number", "unit": "score", "max": 0, "source": AUTHOR,
         "explain": "How far the Altman score — a combined read on how "
                    "close a company is to financial distress — may fall "
                    "from where it was at a purchase before this strategy "
                    "stops adding.\n\n"
                    "A negative number, because it is a fall. Minus 0.75 is "
                    "half the distance from the 2.6 required to buy to the "
                    "1.1 that sells, and the score is built to move slowly, "
                    "so a fall of this size is not noise. It moved with "
                    "those two levels when the score changed to the "
                    "four-variable version, so the tolerance still means "
                    "the same share of the distance it always did."},

        {"id": "drift-debt-to-equity",
         "label": "Worst change in debt against equity you will add behind",
         "type": "number", "unit": "ratio", "min": 0, "source": AUTHOR,
         "explain": "How much further total debt may climb against "
                    "shareholders' equity, from where it was at a purchase, "
                    "before this strategy stops adding. Positive, because "
                    "the rise is what matters; half a turn is about halfway "
                    "from the 1.0 required to buy to the 2.0 that sells."},

        {"id": "drift-loss-years",
         "label": "Extra losing years you will add behind",
         "type": "integer", "unit": "count", "min": 0, "max": 10,
         "source": AUTHOR,
         "explain": "How many more consecutive loss-making years the record "
                    "may show than it did at a purchase, before this "
                    "strategy stops adding.\n\n"
                    "Nought means any new losing year stops further "
                    "purchases. That is deliberately the strictest of these "
                    "five: this strategy already refuses to sell on a single "
                    "losing year, and the space between \"not yet a sell\" "
                    "and \"quietly buy more of it\" is exactly where a "
                    "position gets averaged into a business that has stopped "
                    "making money."},

        # -- the discipline that is not a measure --------------------------
        {"id": "holding-period-months", "label": "Months before time is up",
         "type": "integer", "unit": "count", "min": 1, "max": 600,
         "source": REPORT,
         "explain": "How long a position is given to work before it is "
                    "closed regardless of what any figure says. Twenty-four "
                    "months is the report's figure.\n\n"
                    "It is here because the characteristic failure of "
                    "buying statistical discounts is not the ones that go "
                    "wrong loudly — it is the ones that simply stay cheap, "
                    "year after year, while your money sits in them doing "
                    "nothing. No measure can hold \"it has been two "
                    "years\", so without this there is no exit for that "
                    "case at all.\n\n"
                    "**Two things about where this rule comes from, and "
                    "neither is comfortable.**\n\n"
                    "It is not from the programme this strategy otherwise "
                    "implements. Graham's sell-after-two-years discipline "
                    "belongs to his net-net and simplified-criteria work "
                    "rather than to the defensive programme of chapter 14, "
                    "which is where nearly every other test here comes "
                    "from. So this is a rule imported from a neighbouring "
                    "method, and it is imported deliberately: without it "
                    "this strategy has no answer at all for a security that "
                    "stays cheap forever, which is the way this style of "
                    "investing most commonly fails.\n\n"
                    "And as Graham stated it, the rule had two legs — sell "
                    "at roughly a fifty percent gain, or after two years, "
                    "whichever comes first. Only the clock is here, and the "
                    "gain leg cannot be built. It would need to know what "
                    "you paid, and nothing in this program hands a strategy "
                    "the cost of a position. That is deliberate on the "
                    "host's part rather than a gap: the same rule that "
                    "makes the gain leg unwritable is what stops any "
                    "strategy writing \"buy more when it falls below what "
                    "you paid\", which is the failure mode the whole "
                    "program is built against. The clock therefore runs "
                    "alone, which makes it the LOOSER half of the pair — a "
                    "position that doubles in eighteen months is held to "
                    "the full two years here where Graham would have taken "
                    "the gain. The valuation exits do some of that work and "
                    "not all of it.\n\n"
                    "Shorten it and you will be selling discounts that had "
                    "not finished closing. Lengthen it and you are "
                    "reintroducing exactly the open-ended patience it "
                    "exists to refuse."},

        # -- the four knockouts --------------------------------------------
        {"id": "max-pe-3y-avg",
         "label": "Highest price to three-year average earnings",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "What you are paying for a dollar of the company's "
                    "typical yearly profit. At 15 you are paying fifteen "
                    "dollars for each dollar it earns in an ordinary year. "
                    "The three-year average is the point of it: it stops "
                    "you paying a low-looking multiple on one fluke good "
                    "year.\n\n"
                    "Fifteen is Graham's published figure from The "
                    "Intelligent Investor, chapter 14. It corresponds to "
                    "the company's earnings paying you 6.7% a year. His "
                    "number is used rather than a modernised one, because "
                    "the whole value of this strategy is that it is his.\n\n"
                    "**This is a ceiling on the ceiling rather than the "
                    "test itself.** What this strategy actually demands is "
                    "the STRICTER of two rules Graham wrote: this fixed "
                    "fifteen, and the separate requirement that the "
                    "earnings yield beat the bond yield several times over. "
                    "The second is the binding one at any bond yield above "
                    "about 3.3%, so in most rate environments the price "
                    "test is well below fifteen and this number is doing "
                    "nothing. That is intended: raising this cannot loosen "
                    "the strategy while the bond rule binds, and lowering "
                    "it can always tighten it.\n\n"
                    "The two used to be separate tests at different tiers — "
                    "this one a knockout and the bond rule reported and "
                    "never blocking — which meant that whenever the bond "
                    "rule was the stricter, the strategy was quietly using "
                    "the looser one. Nobody decided that; it fell out of "
                    "where the two happened to sit.\n\n"
                    "Where it misfires: a company in a cyclical industry at "
                    "the bottom of its cycle has collapsed earnings, so "
                    "this number explodes and the company looks expensive "
                    "at the exact moment it is cheapest. Any large one-off "
                    "charge inside the three years drags the average down "
                    "and makes the stock look dearer than it is. And "
                    "where the three-year average earnings are negative "
                    "there is no meaningful multiple at all, so this reads "
                    "as unknown rather than as a failure."},

        {"id": "max-price-to-book", "label": "Highest price to book value",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "Book value is what the company's own accounts say it "
                    "is worth: everything it owns, less everything it owes. "
                    "This is what you pay for a dollar of that. At 1.5 you "
                    "are paying a dollar fifty for a dollar of accounting "
                    "net worth.\n\n"
                    "Graham's number, for the same reason his earnings "
                    "multiple is used unmodified.\n\n"
                    "Where it misfires, and it is severe: book value "
                    "stopped describing modern businesses sometime around "
                    "1990. Software, drug, brand and services companies "
                    "carry their real assets — code, patents, reputation, "
                    "people — nowhere on the balance sheet, so this test "
                    "rejects them systematically. Where it still works well "
                    "is banks, insurers and asset-heavy industrials, which "
                    "is the irony worth knowing about this strategy: the "
                    "companies it handles best are the ones you are least "
                    "likely to have heard of."},

        {"id": "max-combined-multiple",
         "label": "Highest combined earnings and book multiple",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "What you pay for a dollar of typical earnings, "
                    "multiplied by what you pay for a dollar of the "
                    "company's accounting net worth — the two price tests "
                    "combined into one number, so that either may be high "
                    "if the other is low. A company at 18 times earnings "
                    "and 1.2 times book scores 21.6 and passes; one at 18 "
                    "times earnings and 2.0 times book scores 36 and does "
                    "not.\n\n"
                    "22.5 is 15 × 1.5, which is exactly how Graham derived "
                    "it. It is often called the Graham Number in his "
                    "honour.\n\n"
                    "Where it misfires: it inherits every problem of both "
                    "components and compounds them. A cyclical company at "
                    "the bottom of its cycle with few tangible assets fails "
                    "twice, for two unrelated bad reasons."},

        {"id": "min-current-ratio", "label": "Lowest current ratio",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "How much the company holds in things it can turn into "
                    "cash within a year — money in the bank, bills owed to "
                    "it, stock on the shelves — against the bills it has to "
                    "pay in that year. At 2.0 it holds two dollars for "
                    "every dollar coming due.\n\n"
                    "It is a knockout here, and set twice as high as a "
                    "quality-first strategy would set it, for one reason: "
                    "this strategy is buying a business it does not trust, "
                    "so the balance sheet has to carry the risk the "
                    "operations cannot. The same measure means the opposite "
                    "thing to someone buying a business they do trust, "
                    "where being paid by customers before paying suppliers "
                    "is a sign of strength that shows up here as a bad "
                    "number.\n\n"
                    "Where it misfires: retailers, restaurants and "
                    "subscription businesses routinely run below 1.0 and "
                    "are perfectly sound. Graham's answer would be that "
                    "they are then not Graham stocks."},

        # -- the eight core tests ------------------------------------------
        {"id": "max-ltd-to-working-capital",
         "label": "Highest long-term debt against working capital",
         "type": "number", "unit": "ratio",
         "source": REPORT,
         "explain": "Working capital is what is left of the short-term "
                    "assets once the short-term bills are paid — the liquid "
                    "cushion. This asks whether the company's long-term "
                    "borrowings could be covered by that cushion alone. At "
                    "1.0 they exactly could.\n\n"
                    "Graham's own test, stated in exactly this form. It is "
                    "stricter and more literal than comparing debt to "
                    "equity because it ignores fixed assets entirely, which "
                    "is deliberate: if the company were wound up, the "
                    "factory sells for a fraction of what the books say.\n\n"
                    "Where it misfires: utilities, telecoms, railways and "
                    "anything else that has to own a great deal of "
                    "equipment fail this permanently. From this strategy's "
                    "point of view that is correct behaviour and not a "
                    "defect."},

        {"id": "min-profitable-years",
         "label": "Profitable years out of the last ten",
         "type": "integer", "unit": "count", "min": 0, "max": 10,
         "source": REPORT,
         "explain": "How many of the last ten financial years the company "
                    "made a profit. Ten out of ten means it has never lost "
                    "money in a decade — not usually profitable, never lost "
                    "money.\n\n"
                    "Ten of ten rather than eight of ten because stability "
                    "itself is the criterion, and a tool that tells a "
                    "beginner \"a couple of loss years is fine\" is "
                    "teaching the wrong lesson at exactly the point where "
                    "the lesson matters. Relaxing it is a decision to make "
                    "here, consciously, rather than one to have made for "
                    "you.\n\n"
                    "Where it misfires: this is the most punishing test in "
                    "the set right now, because 2020 put a shutdown loss or "
                    "a paper write-down on the books of a great many "
                    "otherwise stable companies. Through roughly 2030 it "
                    "will exclude businesses this strategy would otherwise "
                    "have accepted."},

        {"id": "min-altman-z", "label": "Lowest bankruptcy score",
         "type": "number", "unit": "score",
         "source": REVIEW,
         "explain": "A single score built from four things about the "
                    "balance sheet and the profits, weighted by how well "
                    "each one predicted companies going broke in the study "
                    "that produced it. Above 2.6 is the safe zone; below "
                    "1.1 is the distress zone; in between is a grey "
                    "area.\n\n"
                    "2.6 rather than the grey area, because this strategy "
                    "holds a business it has formed no opinion about and "
                    "therefore takes the full cushion rather than half of "
                    "it.\n\n"
                    "**This is the four-variable score and it used to be "
                    "the five-variable one, which is why the level moved "
                    "from 3.0 to 2.6 without the demand changing.** The "
                    "original was fitted on public manufacturers and "
                    "carries a sales-to-assets term: a factory turning its "
                    "assets over slowly is a warning, and a consultancy "
                    "turning over almost no assets at all is not thereby in "
                    "trouble. Its author published this variant for exactly "
                    "that reason, for service and non-manufacturing "
                    "companies, which is most of what any screen meets now. "
                    "2.6 and 1.1 are his published bands for the variant, "
                    "as 3.0 and 1.8 were for the original.\n\n"
                    "The second difference matters as much and is easy to "
                    "miss. The variant compares the owners\u2019 money to what "
                    "the company owes using what the BOOKS say the equity "
                    "is worth, where the original used what the market says. "
                    "So the score no longer moves when the share price "
                    "does — which is what a solvency test inside a "
                    "valuation strategy needs, because otherwise a share "
                    "falling for being cheap reads as a share falling for "
                    "being in trouble, and the one measure meant to tell "
                    "those apart moves with the wrong one.\n\n"
                    "This is the one test here that Graham never used. It "
                    "was published in 1968 and it is not his, but it is "
                    "the formalisation of precisely what his balance-sheet "
                    "tests were reaching for, and it has fifty years of "
                    "out-of-sample validation behind it, which none of his "
                    "individual ratios do. He would recognise the intent "
                    "even though he never saw the formula.\n\n"
                    "Where it misfires: its author excluded financial "
                    "companies, because the ratios do not map onto them, "
                    "and the variant does not change that. Young companies "
                    "score low simply for not having existed long enough to "
                    "accumulate past profits."},

        {"id": "min-eps-growth-10y",
         "label": "Lowest ten-year growth in earnings per share",
         "type": "number", "unit": "percent", "min": -100,
         "source": REPORT,
         "explain": "How much more the company earns per share than it did "
                    "a decade ago, as a total rather than a yearly rate. A "
                    "third more over ten years is under 3% a year: a very "
                    "low bar, deliberately.\n\n"
                    "33% is Graham's exact figure. The way it is measured "
                    "matters more than the level does — a three-year "
                    "average at each end rather than single years, which is "
                    "also his method, because single-year endpoints make "
                    "the number meaningless.\n\n"
                    "Growth was never the reason to buy here; the discount "
                    "was. A third more over a decade is a low bar and it "
                    "is not a zero bar — a company earning exactly what it "
                    "did ten years ago fails it, and so does one that grew "
                    "a fifth. There is no exit on the other side of this "
                    "one, because a company that stops growing was never "
                    "being owned for its growth.\n\n"
                    "Where it misfires: it needs ten years of filings, "
                    "which excludes anything that listed recently."},

        {"id": "min-capital-return-years",
         "label": "Lowest unbroken run of years returning capital",
         "type": "integer", "unit": "years", "min": 0,
         "source": REVIEW,
         "explain": "How many years in a row the company has handed cash "
                    "back to its owners — by dividend, by buying its own "
                    "shares back, or by both.\n\n"
                    "Twenty is Graham's own figure, and it was doing two "
                    "jobs rather than one. It evidences that the company "
                    "returns capital rather than only promising to. And it "
                    "evidences SURVIVAL: twenty years reaches back through "
                    "whatever the last two decades contained, including "
                    "something bad, which no shorter window can show at "
                    "all.\n\n"
                    "**This used to demand ten years of dividends, and that "
                    "solved the right problem the wrong way.** The problem "
                    "is real: Graham wrote before a 1982 rule change made "
                    "buying back shares a safe, routine alternative to "
                    "paying dividends, so a dividend-only test now excludes "
                    "companies that have returned capital every year by a "
                    "route he had no reason to anticipate. But cutting the "
                    "run from twenty to ten kept the capital-return "
                    "evidence and threw away the survival evidence, which "
                    "was the half that could not be replaced. Widening the "
                    "mechanism and keeping the twenty years keeps "
                    "both.\n\n"
                    "Buybacks count NET of shares issued. A company handing "
                    "out more stock than it repurchases is not returning "
                    "capital, it is mopping up after its own issuance, and "
                    "counting the repurchase line gross would let that read "
                    "as a capital return in the year it is least true.\n\n"
                    "Where it misfires: buybacks are discretionary in a way "
                    "dividends are not. A company can repurchase in good "
                    "years and quietly stop in bad ones without the signal "
                    "a dividend cut sends, so a run counted this way "
                    "evidences capacity more than it evidences commitment. "
                    "And a company that returns capital by special dividend "
                    "every other year breaks the run despite having handed "
                    "back a great deal."},

        {"id": "max-debt-to-equity", "label": "Highest debt to equity",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "How much of the company is financed by lenders against "
                    "how much by its owners. At 1.0 there is a dollar "
                    "borrowed for every dollar of shareholders' money.\n\n"
                    "A full turn of borrowing is tolerable here because "
                    "this strategy is buying a mature, boring business with "
                    "ten straight profitable years behind it. A strategy "
                    "buying a company growing twenty percent a year sets "
                    "this at half as much, because that company has never "
                    "been tested by a downturn and borrowing plus a stumble "
                    "is the standard way such positions go to zero. Same "
                    "measure, different number, and the difference is the "
                    "whole point of committing to one strategy.\n\n"
                    "Where it misfires: recently listed companies with "
                    "large cash piles and small equity bases read oddly, "
                    "and a company that has bought back so much stock that "
                    "equity is negative produces a number with no meaning "
                    "at all."},

        {"id": "max-price-to-tangible",
         "label": "Highest price to tangible assets",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "Price to book with the imaginary parts taken out — "
                    "goodwill and other intangibles removed, so what is "
                    "left is things that could actually be sold. At 2.0 you "
                    "are paying two dollars per dollar of them.\n\n"
                    "Two dollars is the outer edge of what a "
                    "liquidation-minded discount justifies. Beyond it you "
                    "are relying on the business rather than on what it "
                    "owns, and relying on the business is not what this "
                    "strategy does.\n\n"
                    "Where it misfires: businesses that own very little "
                    "fail it by construction, because there is nothing "
                    "tangible to price. Companies with negative tangible "
                    "book, which is common after a large acquisition, "
                    "produce a meaningless number."},

        {"id": "max-accruals-ratio", "label": "Highest accruals ratio",
         "type": "number", "unit": "ratio",
         "source": REPORT,
         "explain": "How much of the reported profit is bookkeeping rather "
                    "than money that actually arrived. A company can book a "
                    "sale it has not been paid for, or record a cost as "
                    "an asset to be written off slowly instead of "
                    "subtracting it from this year's profit. Both raise "
                    "reported profit without any money arriving. This "
                    "measures the gap between the two.\n\n"
                    "This is not Graham's — it comes from research "
                    "published in 1996 — but a portfolio bought this way is "
                    "bought on reported numbers, so a check that the "
                    "reported numbers are real is doing exactly his job "
                    "with better tools. A high reading predicts poor "
                    "subsequent returns with unusual reliability.\n\n"
                    "Where it misfires: fast growth generates this "
                    "legitimately, and seasonal businesses read oddly at "
                    "particular quarter-ends."},

        {"id": "min-revenue", "label": "Smallest company worth buying",
         "type": "number", "unit": "usd", "min": 0,
         "source": REVIEW,
         "explain": "What the company sold in the last year, in money.\n\n"
                    "Graham's own test of adequate size, which he set at "
                    "$100M of annual sales for an industrial company in the "
                    "1973 edition. Adjusted for inflation that is roughly "
                    "$750M today, and that is the figure used.\n\n"
                    "**This used to be a floor on market capitalisation, "
                    "and that was the wrong quantity.** Graham stated the "
                    "criterion in sales; the level here was a market value "
                    "defended with an argument about sales. Worse, it was "
                    "the wrong variable for this particular strategy: a "
                    "rule set that hunts for companies the market has "
                    "priced too cheaply, and then refuses anything the "
                    "market prices too low, is partly rejecting companies "
                    "for being cheap. Sales do not move when the share "
                    "price does.\n\n"
                    "It is a test this strategy will not bend: below it, no "
                    "amount of cheapness counts. That placement is this "
                    "strategy's, not the report's, which scores the size "
                    "test rather than disqualifying on it — and the "
                    "argument for the tier survives the change of variable. "
                    "Filing quality and being able to sell when you want to "
                    "are not things a good score somewhere else makes up "
                    "for.\n\n"
                    "The old level was deliberately below Graham's, on the "
                    "argument that the discounts this strategy hunts are "
                    "disproportionately in smaller companies. That argument "
                    "is still available and it now has to be made about "
                    "sales rather than about market value, which nobody has "
                    "made. So the level went to Graham's own.\n\n"
                    "Where it misfires: sales are a poor comparison of size "
                    "across industries. A grocery chain turning over ten "
                    "billion at two percent margins is a smaller business, "
                    "on any other reading, than a software company turning "
                    "over two billion at thirty. And what this is really "
                    "guarding — being able to sell your position when you "
                    "want to — is liquidity, which no figure in any filing "
                    "measures. Sales are a proxy for it and not the thing "
                    "itself."},

        # -- the two bonus tests -------------------------------------------
        {"id": "min-ncav-to-market-cap",
         "label": "Lowest liquid assets against the price",
         "type": "number", "unit": "ratio",
         "source": REPORT,
         "explain": "How much of what you are paying is already covered by "
                    "assets that could be turned into cash within a year, "
                    "after settling every debt the company has. At 1.5 you "
                    "would be buying the company for two-thirds of its net "
                    "liquid assets and getting the business itself free — "
                    "which is Graham's famous net-net, and which barely "
                    "exists in modern markets outside Japan and very small "
                    "companies.\n\n"
                    "Requiring a true net-net would leave you with an empty "
                    "screen for years at a time. At 0.50 and as a bonus it "
                    "rewards a real balance-sheet cushion without demanding "
                    "the impossible.\n\n"
                    "Where it misfires: assets are counted at what the "
                    "books say, and stock on the shelves in particular "
                    "rarely fetches book value in a wind-down. It assumes "
                    "an orderly liquidation that would not actually "
                    "happen."},

        {"id": "min-earnings-yield-multiple",
         "label": "Lowest earnings yield against the bond yield",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "How many times more the company's earnings pay you "
                    "than lending the same money to a first-class borrower "
                    "would. At 2.0 the stock's earnings yield is twice the "
                    "bond yield; at 1.0 you are taking every risk of owning "
                    "a business for a bond's return.\n\n"
                    "Graham's Enterprising Investor test. It is what makes "
                    "every absolute price level in this strategy aware of "
                    "what interest rates are doing — a 6.7% earnings yield "
                    "means something very different when a bond pays 1% "
                    "than when it pays 5%.\n\n"
                    "**This is no longer a test of its own. It is half of "
                    "the price ceiling**, read together with the bond yield "
                    "below: at 2.0 against a yield of 5%, the demand is an "
                    "earnings yield of 10% or better, which is a price of "
                    "at most ten times typical earnings. That is compared "
                    "against the fixed fifteen and the stricter of the two "
                    "is what this strategy will pay — so this rule now "
                    "decides purchases in every environment where it is the "
                    "binding one, which used to be exactly where it was "
                    "being ignored.\n\n"
                    "Expect it to bind at a high bond yield. That is the "
                    "test working, and what it is telling you is that the "
                    "same money is being offered a competitive return with "
                    "none of the risk."},

        {"id": "aaa-corporate-yield",
         "label": "What a first-class corporate bond pays",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": {"name": "Graham for which rate, this strategy's author "
                            "for the figure. Neither the expert report nor "
                            "the review states a number, because a rate is "
                            "not the kind of thing a document can fix — it "
                            "is whatever the market is paying while you are "
                            "reading this",
                    "reasoning": True},
         "explain": "What lending money to the safest corporate borrowers "
                    "pays right now: the yield on high-grade — Aaa-rated — "
                    "corporate bonds, as an annual percentage. It is close "
                    "to the return you can have without taking business "
                    "risk, so it is what owning a business has to beat "
                    "before the risk is worth taking.\n\n"
                    "**Corporate and not government, and the difference is "
                    "not cosmetic.** Graham's test was written against "
                    "high-grade corporate bonds. This strategy used to use "
                    "the ten-year Treasury instead, which typically pays "
                    "somewhere around 0.7 to 1.0 points less — so twice a "
                    "Treasury yield is materially looser than the twice a "
                    "corporate yield he actually wrote, and the strategy "
                    "was demanding less than it claimed. At a 5% corporate "
                    "yield against a 4.2% Treasury, the price ceiling is 10 "
                    "times earnings rather than 11.9, which is a real "
                    "difference in what gets bought.\n\n"
                    "Look up Moody's seasoned Aaa corporate bond yield — "
                    "the Federal Reserve publishes it and it is easy to "
                    "find — and put the figure here.\n\n"
                    "**This is the one number here you have to maintain, "
                    "and it is the only one that goes wrong just by sitting "
                    "still.** Nothing in this program fetches it: it is in "
                    "no filing and it is not price data, so the figure "
                    "shipped with the strategy is a starting point and "
                    "nothing more. When rates move, come back. A yield left "
                    "at 5% while the market pays 7% quietly makes this "
                    "strategy easier than you agreed it should be — and "
                    "since this one number sets the price ceiling on every "
                    "purchase, that is not a small quiet.\n\n"
                    "It is here as a setting rather than as a question at "
                    "setup so that changing it is recorded: the day you "
                    "moved it, what it was, and what it became go on this "
                    "journal's record of rule changes, next to the reason "
                    "you give. A number that sets a bar and can be adjusted "
                    "without trace is the thing this journal exists to "
                    "prevent."},

        # -- the eight exits -----------------------------------------------
        {"id": "exit-pe-3y-avg",
         "label": "Exit level for price to typical earnings",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "The point at which the discount you bought has "
                    "closed on the earnings side. You bought at fifteen "
                    "times typical earnings or less; at twenty-five the "
                    "statistical bargain is gone.\n\n"
                    "This field having a number in it at all is the "
                    "sharpest disagreement in investing, and it is worth "
                    "understanding before you change it. A strategy built "
                    "on owning wonderful businesses leaves it blank on "
                    "purpose, because a business compounding at 18% a year "
                    "will look expensive for most of the twenty years you "
                    "should own it, and a rule that sold on price would "
                    "destroy your returns while appearing to work. This "
                    "strategy fills it in because it never claimed the "
                    "business was worth anything in particular — only that "
                    "it was mispriced. When the mispricing is gone, so is "
                    "the reason to own it, and holding on means you have "
                    "quietly switched to a thesis you never tested.\n\n"
                    "Neither position is a compromise and there is no "
                    "number in between that either side would sign. That is "
                    "why they are separate strategies and separate "
                    "journals."},

        {"id": "exit-price-to-book",
         "label": "Exit level for price to book",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "Book value is what the company's own accounts say "
                    "it is worth: everything it owns, less everything it "
                    "owes. This is the level at which what you pay for a "
                    "dollar of that has stopped being a discount — you "
                    "bought below the company's stated net worth and are "
                    "now being asked three dollars for every dollar of "
                    "it.\n\n"
                    "Roughly a doubling of the entry level, which is the "
                    "discount closing by any reasonable reading."},

        {"id": "exit-combined-multiple",
         "label": "Exit level for the combined multiple",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT,
         "explain": "The earnings multiple and the book multiple "
                    "multiplied together, so a security that has run hard "
                    "on one of them and only a little on the other is still "
                    "caught. The same combined number the entry side "
                    "reports, at the level where the discount has "
                    "closed.\n\n"
                    "Roughly a doubling of the entry level, which is how "
                    "the report derives it.\n\n"
                    "**This is the one place the combined multiple decides "
                    "anything, and it is why it is still here.** On the "
                    "entry side the three price tests are all demanded at "
                    "once, so a company passing the earnings ceiling and "
                    "the book ceiling passes their product automatically — "
                    "the row cannot fail and cannot be the reason for "
                    "anything. On the way out they are alternatives, and a "
                    "holding at twenty times earnings and 2.8 times book "
                    "trips this at 56 while tripping neither of the "
                    "others."},

        {"id": "exit-current-ratio",
         "label": "Exit level for the current ratio",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "The cushion the whole thesis rests on has gone. You "
                    "required two dollars of short-term assets per dollar "
                    "of short-term bills when you bought; at 1.2 the liquid "
                    "position is no longer carrying risk the operations "
                    "cannot.\n\n"
                    "Note how far this sits below the 2.0 entry level. That "
                    "gap is deliberate: a company drifting from 2.0 to 1.8 "
                    "is not the same event as one arriving at 1.2, and an "
                    "exit set at the entry level would fire on ordinary "
                    "drift."},

        {"id": "exit-ltd-to-working-capital",
         "label": "Exit level for long-term debt against working capital",
         "type": "number", "unit": "ratio",
         "source": REPORT_LEVEL_ONLY,
         "explain": "Long-term borrowings at twice the liquid cushion means "
                    "the cushion has stopped covering them, which is the "
                    "specific thing this measure was in the entry tests to "
                    "establish."},

        {"id": "exit-altman-z", "label": "Exit level for the bankruptcy score",
         "type": "number", "unit": "score",
         "source": REVIEW,
         "explain": "Below 1.1 is the distress zone of the score described "
                    "in the entry test above — the range in which companies "
                    "in the study went broke.\n\n"
                    "1.1 rather than the 1.8 this used to be, and nothing "
                    "about the demand changed: 1.8 is the distress band of "
                    "the five-variable score and 1.1 is the distress band "
                    "of the four-variable one this strategy now uses. "
                    "Carrying the old number across would have been reading "
                    "a level off one scale and applying it to another, "
                    "which would have made this exit fire far earlier than "
                    "intended on every company it evaluates.\n\n"
                    "A cheap stock that goes bankrupt is the characteristic "
                    "failure of this entire approach, and this is the "
                    "single test most directly aimed at it."},

        {"id": "exit-debt-to-equity",
         "label": "Exit level for debt to equity",
         "type": "number", "unit": "ratio", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "At two turns of borrowing the lenders own more of the "
                    "outcome than the owners do, and the balance sheet has "
                    "stopped being the thing carrying the risk — which was "
                    "the entire reason an unremarkable business was "
                    "acceptable."},

        {"id": "exit-loss-years",
         "label": "Losing years in a row that end the position",
         "type": "integer", "unit": "count", "min": 1,
         "source": REPORT,
         "explain": "How many years in a row of losses end the position. "
                    "One loss year can be a write-down or a settlement. Two "
                    "in a row is the business, and the stability that was "
                    "the reason to accept an unremarkable company has "
                    "gone.\n\n"
                    "Nothing is asked on top of this level. The measure "
                    "counts annual reports, so two losing years already "
                    "means two annual filings — and the host knows that "
                    "from the metric bank rather than from a note here, "
                    "which is why lowering this to one now acts on one "
                    "losing year instead of quietly waiting for a second."},
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


def _points(ctx, measure_id):
    """One measure's per-filing readings, oldest first."""
    entry = (ctx.get("measures") or {}).get(measure_id) or {}
    return ((entry.get("series") or {}).get("points")) or []


def _cite(measure_id, comparator, value_id, group, at=None, without=None):
    """One citation: which measure, which direction, and the setting the
    host reads the limit out of. Nothing here is a number.

    `at` cites the reading at one past filing; `without` cites the current
    window with the single year that most favours the requirement taken out.
    Both are the host's arithmetic on the host's figures — this file names
    the question and never the answer."""
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
    once. There is no second comparison here to disagree with the first,
    which is the point: this strategy used to carry its own comparators, the
    host ran the comparison again when it resolved the citation, and nothing
    checked the two agreed. A verdict could be returned beside evidence
    saying the opposite of it.
    """
    cites = [_cite(m, c, v, group) for m, c, v in rows]
    return cites, [contract.test(ctx, item) for item in cites]


def _drift_cite(measure_id, comparator, value_id, anchor, group):
    """One drift citation: which measure, which purchase to measure from,
    which direction, and the setting holding the tolerance.

    Not one number. The reading at the purchase, the reading now and the
    distance between them are all the host's — this strategy could take one
    from the other itself, and then the figure on screen would be one it had
    stated rather than one anybody could check against the record.
    """
    return {"measure": measure_id, "since": anchor, "comparator": comparator,
            "threshold_from": value_id, "group": group}


def _drift(ctx, anchor, group):
    """(citations, outcomes) for every drift test against one anchor."""
    cites = [_drift_cite(m, c, v, anchor, group) for m, c, v in DRIFT]
    return cites, [contract.test(ctx, item) for item in cites]


# ---------------------------------------------------------------------------
# the price ceiling, which is the stricter of two rules and not either of them
#
# The only test here the strategy works out for itself rather than naming a
# measure that already holds the answer, and the only limit it states rather
# than cites. Both of those cost something, so both are argued for.
#
# THERE USED TO BE TWO PRICE TESTS AND THEY CONTRADICTED EACH OTHER. A fixed
# ceiling of fifteen times typical earnings sat among the knockouts; a rule
# that the earnings yield must beat the bond yield several times over sat
# among the rows that never block. Above a bond yield of about 3.3% the second
# is the stricter of the two — so in every environment since, the strategy was
# quietly running the looser rule, because of where the tiers happened to put
# them. That is not a judgement anybody made. It is an accident of layout
# deciding what a strategy demands.
#
# So there is one test, and its limit is the stricter of the two rules:
#
#     min( the fixed ceiling, 100 ÷ (multiple × the bond yield) )
#
# An earnings yield of at least `multiple × yield` per cent is exactly a price
# of at most `100 ÷ (multiple × yield)` times typical earnings, which is why
# the second rule can be expressed as a ceiling on the same measure at all.
# Graham stated one figure and one relationship; taking the stricter is what
# holds both of the things he wrote at once, in every rate environment rather
# than in the one his was written in.
#
# The measure is still cited and never quoted. Working out `1/PE ÷ rate` here
# and stating the answer would be this strategy restating a figure the host
# owns, and a restatement can be wrong. The strategy owns the question and the
# limit; the host owns the figure, its unit, and whether the comparison was
# met.
#
# What this costs is the one thing the evidence vocabulary cannot express: a
# row cites ONE setting or states ONE number, and this limit is worked out
# from three. So all three are cited beside it as the observations they are.
# That is the difference between a number a reader can check and a number they
# have to accept — 12.5 with "fifteen", "twice" and "4%" underneath it is
# arithmetic anyone can redo, and 12.5 on its own is this file asking to be
# trusted.
# ---------------------------------------------------------------------------

_PRICE_SETTINGS = ("max-pe-3y-avg", "min-earnings-yield-multiple",
                   "aaa-corporate-yield")


def _price_ceiling(values):
    """The highest multiple of typical earnings this strategy will pay, and
    which of the two rules set it — or (None, None) where the settings do not
    describe a limit.

    All three are declared values with defaults, so the arithmetic normally
    cannot fail; but any of them can be overridden in a journal, and dividing
    by a nought would take a whole verdict down over one row. None means the
    caller shows the settings and no comparison, which is what a limit nobody
    could work out honestly looks like.
    """
    fixed, multiple, yield_ = (values.get(v) for v in _PRICE_SETTINGS)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and v > 0 for v in (fixed, multiple, yield_)):
        return None, None
    against_bonds = round(100.0 / (multiple * yield_), 2)
    if against_bonds < fixed:
        return against_bonds, "bonds"
    return fixed, "fixed"


def _price_cite(values, group):
    """The price test, or None where its limit could not be built."""
    ceiling, _which = _price_ceiling(values)
    if ceiling is None:
        return None
    return {"measure": "pe_3y_avg_eps", "comparator": "at_most",
            "threshold": ceiling, "group": group}


def _price_cites(values, group):
    """The price test and the three settings behind it.

    The settings are cited whether or not the limit could be built. Where it
    could, they are how the reader checks it; where it could not, they are the
    only thing left saying a test exists at all.
    """
    cite = _price_cite(values, group)
    return ([cite] if cite is not None else []) + [
        {"value": v, "group": group} for v in _PRICE_SETTINGS]


def _bonus_cites(ctx, group):
    cites, _outcomes = _screen(ctx, BONUS, group)
    return cites


# ---------------------------------------------------------------------------
# the exits, and the confirmation walk
# ---------------------------------------------------------------------------

def _exit_state(ctx, group, measure_id, comparator, value_id):
    """One exit as confirmed / breached / clear / unreadable, with whatever
    the host leant on to say so. `comparator` is what the holding must keep
    being true; the exit is that failing.

    This file used to walk the filing series itself and compare the run
    against a setting. It no longer does, and the setting is gone with it:
    how much evidence a breach needs is a property of the measure, and this
    strategy had no way to know that the eight exits below are read four
    different ways. A balance-sheet ratio is a photograph of one morning and
    wants a second filing; a price against three-year average earnings is a
    new number every day and wants the same; a run of losing years counts
    annual reports and needs nothing on top; and the tests that read a
    window of years cannot be confirmed by waiting at all, because the year
    that produced the breach is still in the window next quarter.

    Absence never fires an exit. A missing reading is not evidence that a
    company is in trouble, and this program does not sell on silence — but
    it is not reported as clear either, so the caller can tell an exit that
    was checked from one that was not.
    """
    return contract.confirm(ctx, _cite(measure_id, comparator, value_id,
                                       group))


def _capital_return_break(ctx):
    """The two period ends across which an unbroken run of years returning
    capital reset since this holding was opened, or None.

    Every readable pair is walked, not only the newest two. A run that goes
    from twelve years to nothing shows a drop on one filing and then climbs
    again from one, so a flag that only looked at the last pair would appear
    for a single reporting period and vanish — and because fetching is
    something the user does when they think of it, the filing that carried
    it is the one most likely to be missed entirely. The point of the flag
    is to send someone to the filings; a flag with a one-filing shelf life
    does not.

    Bounded by the holding, because a cut the company made before this
    position existed is not news about this position.

    A cut never changes the verdict. By the time a dividend is cut the
    balance-sheet exits are usually already talking, and the report is
    explicit that this should send the reader to read rather than to sell.
    """
    opened = str((ctx.get("position") or {}).get("opened") or "")
    readable = [p for p in _points(ctx, CAPITAL_RUN)
                if p.get("value") is not None]
    for before, after in zip(readable, readable[1:]):
        # The period the drop was REPORTED in decides whether it belongs to
        # this holding, not the period it is measured against: a run that
        # ended is news when the filing says so, and the reading it fell
        # from is necessarily older than that.
        if opened and str(after.get("period_end") or "") < opened:
            continue
        if after["value"] < before["value"]:
            return before["period_end"], after["period_end"]
    return None


# ---------------------------------------------------------------------------
# the clock
#
# Both halves are the host's arithmetic. How long the position has been held
# is a fact the host reports, and the day the exit falls due is `months_after`
# — the function that months-held is counted by. That is what stops them
# disagreeing: a position opened on 29 February is due on 28 February two
# years later, and by any other count it reads as 23 months held on exactly
# that day, so the position closes while the evidence beside it says the
# period has not run.
#
# Only the *limit* is this strategy's, and it is cited rather than compared
# here: `below`, not `at_most`, because the clock fires ON the anniversary
# and at exactly the limit the requirement has failed.
# ---------------------------------------------------------------------------

CLOCK_CITE = {"fact": "position.months_held", "comparator": "below",
              "threshold_from": "holding-period-months",
              "group": CLOCK_GROUP["id"]}


def _clock(ctx):
    """(months held, the day the exit falls due, whether it has arrived).
    Nones where the journal does not say when the holding began."""
    months = (ctx.get("position") or {}).get("months_held")
    due = contract.months_after((ctx.get("position") or {}).get("opened"),
                                (ctx.get("values") or {}).get(
                                    "holding-period-months"))
    return months, due, contract.test(ctx, CLOCK_CITE) == FAIL


# ---------------------------------------------------------------------------
# the decision
# ---------------------------------------------------------------------------

def decide(ctx):
    """One evaluation, one state.

    The first fork is whether the security is held, because owning it and
    considering it are different questions rather than two systems: a
    candidate is screened on the fifteen entry tests, a holding is watched
    on the eight exits, the clock and its size. Below that fork the order is
    a single ladder with one exit at each rung, so no two conclusions can
    ever both be true.
    """
    if (ctx.get("position") or {}).get("held"):
        return _on_a_holding(ctx)
    return _on_a_candidate(ctx)


# -- a security you do not own ----------------------------------------------

ROOM_CITE = {"fact": "portfolio.slots_occupied", "comparator": "below",
             "threshold_from": "portfolio-slots", "group": SIZING_GROUP["id"]}


def _dimension(ctx, group, rows):
    """One question about the company: its citations, and whether the rows
    under it answer it.

    The three outcomes are the same three a single test has, reached the same
    way. `met` is the requirement satisfied; `settled_no` is it out of reach
    even if every unreadable row came back a pass; neither means undecided,
    and undecided is neither a purchase nor a refusal.

    How many rows a group needs is read from the group's own declaration, so
    this cannot demand a number different from the one the host counts
    against when it works out the rollup the reader sees.
    """
    cites, out = _screen(ctx, rows, group["id"])
    passed, unknown = out.count(PASS), out.count(UNKNOWN)
    if group["requires"] == "all":
        need = len(rows)
    else:
        need = (ctx.get("values") or {}).get(group["threshold_from"])
    ok = isinstance(need, int) and not isinstance(need, bool)
    return {"group": group, "cites": cites, "passed": passed,
            "unknown": unknown, "tested": len(rows),
            "settled_no": ok and passed + unknown < need,
            "met": ok and passed >= need}


def _names_of(dims) -> str:
    """The groups named in a sentence, lower-cased the way they read mid-line
    rather than as headings."""
    names = [d["group"]["name"][0].lower() + d["group"]["name"][1:]
             for d in dims]
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _entry_screen(ctx):
    """Every entry test, and what the host made of each."""
    values = ctx.get("values") or {}
    price_cites = _price_cites(values, KNOCKOUTS["id"])
    price_cite = _price_cite(values, KNOCKOUTS["id"])
    req_cites, req_out = _screen(ctx, REQUIRED, KNOCKOUTS["id"])
    if price_cite is not None:
        req_out = req_out + [contract.test(ctx, price_cite)]
    else:
        # A ceiling that could not be built is not a passing test. It is a
        # knockout nobody could run, which is exactly what unknown is for.
        req_out = req_out + [UNKNOWN]
    dims = [_dimension(ctx, g, rows) for g, rows in DIMENSIONS]
    short = [d for d in dims if d["settled_no"]]
    return {
        "req_fail": req_out.count(FAIL),
        "req_unknown": req_out.count(UNKNOWN),
        "req_tested": len(req_out),
        "dims": dims, "short": short,
        "passed": sum(d["passed"] for d in dims),
        "tested": sum(d["tested"] for d in dims),
        "unknown": sum(d["unknown"] for d in dims),
        "settled_no": req_out.count(FAIL) > 0 or bool(short),
        "met": req_out.count(UNKNOWN) == 0 and all(d["met"] for d in dims),
        "evidence": (price_cites + req_cites
                     + [c for d in dims for c in d["cites"]]
                     + _bonus_cites(ctx, BONUS_GROUP["id"])),
        "groups": [KNOCKOUTS] + [g for g, _ in DIMENSIONS] + [BONUS_GROUP],
    }


def _on_a_candidate(ctx):
    values = ctx.get("values") or {}
    screen = _entry_screen(ctx)

    req_fail = screen["req_fail"]
    req_unknown = screen["req_unknown"]

    # No tallies are cited. The counts used to be evidence items this
    # strategy worked out and stated — "Knockout tests passed, 3, at least
    # 4" — which meant the rollup on screen came from a different
    # computation than the rows under it, and had to carry its own careful
    # handling of the grey case so that three passes with one unreadable did
    # not render identically to three passes with one failed. Both of those
    # are the host's now: it counts the outcomes it resolved, against the
    # bar the group names, and an unreadable row is neither a pass nor a
    # failure there for exactly the reason it is neither here.
    groups = screen["groups"]
    evidence = screen["evidence"]

    # A knockout that failed, or a question about the company that cannot be
    # answered even if every unreadable row under it came back clear. Either
    # is a settled no — and which question fell short is named rather than
    # counted, because "four of eight passed" told a reader nothing about
    # where to look.
    if screen["settled_no"]:
        return {
            "state": "not-cheap-enough", "payload": {},
            "reason": {
                "rule": "knockout-failed" if req_fail else "dimension-short",
                "summary": (
                    f'{req_fail} of the {screen["req_tested"]} tests this '
                    "strategy will not bend came back against it, and one is "
                    "enough."
                    if req_fail else
                    "This strategy asks five separate questions about a "
                    "company and needs every one of them answered. "
                    + ("One is" if len(screen["short"]) == 1
                       else f'{len(screen["short"])} are')
                    + " not: " + _names_of(screen["short"])
                    + f'. Across all five, {screen["passed"]} of the '
                      f'{screen["tested"]} tests behind them passed, and no '
                      "amount of passing elsewhere settles what is short."),
                "evidence": evidence, "groups": groups,
            },
        }

    # Nothing has failed, but something that has not been read could still
    # decide it. Absence is not a pass, so nothing is claimed.
    if not screen["met"]:
        missing = req_unknown + screen["unknown"]
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

    # It passes. What remains is whether there is room for it, and how much.
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
                    f"It passes every test, and all {slots} of the places "
                    "this strategy runs are taken. Nothing here swaps one "
                    "holding for another — a place opens when one of your "
                    "positions closes."),
                "evidence": evidence, "groups": groups,
            },
        }

    # Both settings ship a default, are typed, and are bounded away from
    # zero by the declaration; a journal override that broke either is
    # refused before decide() is ever called. So the arithmetic below is
    # done without a guard: if that ever stops being true it should fail
    # loudly and say where, not quietly hand back a state whose description
    # is about missing measures.
    equal_share = round(100.0 / slots, 2)
    size = min(equal_share, float(cap))
    bound = ("an equal share of your places" if equal_share <= cap
             else "the cap on any one name")
    evidence = evidence + [
        {"value": "portfolio-slots", "group": SIZING_GROUP["id"]},
        {"value": "position-weight-cap", "group": SIZING_GROUP["id"]},
        {"label": "Size this buy", "unit": "percent", "actual": size,
         "group": SIZING_GROUP["id"]},
    ]
    return {
        "state": "buy",
        "payload": {"size": {"unit": "weight", "value": size},
                    "condition": None},
        "reason": {
            "rule": "qualifies",
            "summary": (
                "Every test this strategy will not bend passed, all five "
                "questions about the company are answered — "
                f'{screen["passed"]} of the {screen["tested"]} tests behind '
                f"them did — and the size is {size:g}% of the account, set "
                f"by {bound}."),
            "evidence": evidence, "groups": groups,
        },
    }


# -- a security you own ------------------------------------------------------

CAP_CITE = {"fact": "position.weight", "comparator": "at_most",
            "threshold_from": "position-weight-cap",
            "group": SIZE_GROUP["id"]}


def _exit_evidence(group, rows, found):
    """Every exit test, cited, with whatever established it named beside it.

    Citing what the host leant on is what lets a reader check the rule
    instead of taking it on trust, and there are two things to cite because
    the host does two different jobs. Where a breach was established by
    filings agreeing, the confirming readings are cited at their own
    periods. Where the measure reads a window of years — a median, a range,
    a growth rate — no number of filings can establish anything, and what
    the host asked instead was whether the failure survives dropping the
    year that most favours it. That reading is cited too, because a verdict
    reached on a recomputation the reader cannot see is a verdict they have
    to believe.
    """
    out = []
    for (measure_id, comparator, value_id), f in zip(rows, found):
        out.append(_cite(measure_id, comparator, value_id, group))
        if f["confirmation"] in (CONFIRMED, BREACHED):
            for period in f["periods"]:
                out.append(_cite(measure_id, comparator, value_id, group,
                                 at=period))
            if f["robust"] is not None:
                out.append(_cite(measure_id, comparator, value_id, group,
                                 without="one-year"))
    return out


def _established_on(found) -> str:
    """How the exits that fired were established, in a clause.

    Counted rather than asserted. The sentence used to read "on more than
    one set of filings" whatever had happened, which is one rule speaking
    for eight exits that are now read four different ways — and a verdict
    has to name the rule that produced it.
    """
    ways = set()
    for f in found:
        if f["robust"]:
            ways.add("surviving the loss of the year that most favours it")
        elif f["needs"] <= 0:
            ways.add("on the current reading, which is all a measure this "
                     "smooth can be asked for")
        elif f["needs"] == 1:
            ways.add("on the newest filing")
        else:
            ways.add(f"on {f['needs']} consecutive filings")
    if len(ways) != 1:
        return " each on the evidence its own measure can carry"
    return " " + ways.pop()


def _on_a_holding(ctx):
    values = ctx.get("values") or {}
    safety = [_exit_state(ctx, SAFETY_GROUP["id"], *row)
              for row in EXITS_SAFETY]
    discount = [_exit_state(ctx, DISCOUNT_GROUP["id"], *row)
                for row in EXITS_DISCOUNT]

    months, due, elapsed = _clock(ctx)
    cap = values.get("position-weight-cap")

    evidence = _exit_evidence(SAFETY_GROUP["id"], EXITS_SAFETY, safety)
    evidence += _exit_evidence(DISCOUNT_GROUP["id"], EXITS_DISCOUNT, discount)
    evidence.append({"fact": "position.opened", "group": CLOCK_GROUP["id"]})
    evidence.append(CLOCK_CITE)
    evidence.append(CAP_CITE)
    groups = [SAFETY_GROUP, DISCOUNT_GROUP, CLOCK_GROUP, SIZE_GROUP]

    cut = _capital_return_break(ctx)
    note = None
    if cut is not None:
        before, after = cut
        evidence.append({"measure": CAPITAL_RUN, "at": before,
                         "group": DIVIDEND_GROUP["id"]})
        evidence.append({"measure": CAPITAL_RUN, "at": after,
                         "group": DIVIDEND_GROUP["id"]})
        groups.append(DIVIDEND_GROUP)
        note = ("The unbroken run of years returning capital — by dividend "
                "or by buying back shares — has reset since the filing for "
                f"{before}. A company that has stopped doing both is real "
                "information about financial distress, and it changes "
                "nothing here on its own: by the time capital returns stop "
                "the balance-sheet exits are usually already talking. Go "
                "and read the filing.")

    def fired(states, rows):
        return [f for f in states if f["confirmation"] == CONFIRMED]

    waiting = [f for f in safety + discount
               if f["confirmation"] == BREACHED]

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

    # The ladder. Safety before price, because a company coming apart is
    # more urgent than a multiple that finally got fair; the clock after
    # both, because it is the fallback for a security that did neither.
    broken = fired(safety, EXITS_SAFETY)
    if broken:
        return {
            "state": "safety-gone",
            "payload": {"when": ctx["today"]},
            "reason": {
                "rule": "safety-exit-confirmed",
                "summary": (
                    f"{len(broken)} of the balance-sheet and earnings "
                    "tests " + ("has" if len(broken) == 1 else "have")
                    + " failed" + _established_on(broken)
                    + ", so this is a change and not a wobble. The cushion "
                    "that made an unremarkable business acceptable is gone."
                    + also_waiting()),
                "evidence": evidence, "groups": groups, "note": note,
            },
        }

    closed = fired(discount, EXITS_DISCOUNT)
    if closed:
        return {
            "state": "discount-closed",
            "payload": {"when": ctx["today"]},
            "reason": {
                "rule": "discount-exit-confirmed",
                "summary": (
                    f"{len(closed)} of the valuation tests "
                    + ("has" if len(closed) == 1 else "have")
                    + " failed" + _established_on(closed)
                    + ". The gap you bought has closed, which is this "
                    "strategy working rather than failing."
                    + also_waiting()),
                "evidence": evidence, "groups": groups, "note": note,
            },
        }

    if elapsed:
        return {
            "state": "time-is-up",
            "payload": {"when": due},
            "reason": {
                "rule": "holding-period-elapsed",
                "summary": (
                    f"You have held this {months} months and the exit fell "
                    f"due on {due}. Nothing about the company decided "
                    "that: a discount that has not closed in the time you "
                    "gave it is the case this clock exists for."
                    + also_waiting()),
                "evidence": evidence, "groups": groups, "note": note,
            },
        }

    if contract.test(ctx, CAP_CITE) == FAIL:
        return {
            "state": "too-big",
            "payload": {"to": {"unit": "weight", "value": float(cap)}},
            "reason": {
                "rule": "over-position-cap",
                "summary": (
                    "This holding has grown past the largest share of the "
                    "account any one name is allowed here — the figure and "
                    "the cap are below. Trimming it back to the cap restores "
                    "the spread this strategy relies on instead of the "
                    "business being good." + also_waiting()),
                "evidence": evidence, "groups": groups, "note": note,
            },
        }

    if waiting:
        return {
            "state": "one-reading-past", "payload": {},
            "reason": {
                "rule": "breach-awaiting-confirmation",
                "summary": (
                    f"{len(waiting)} exit level has been crossed on the "
                    "current reading and has not yet been crossed on "
                    "enough consecutive filings to act on. Nothing is owed "
                    "from you today."
                    if len(waiting) == 1 else
                    f"{len(waiting)} exit levels have been crossed on the "
                    "current reading and have not yet been crossed on "
                    "enough consecutive filings to act on. Nothing is owed "
                    "from you today."),
                "evidence": evidence, "groups": groups, "note": note,
            },
        }

    checked = [f for f in safety + discount
               if f["confirmation"] != UNREADABLE]
    if not checked:
        return {
            "state": "cannot-watch", "payload": {},
            "reason": {
                "rule": "no-exit-test-could-run",
                "summary": (
                    f"Not one of the {len(EXITS_SAFETY) + len(EXITS_DISCOUNT)}"
                    " exit tests could be worked out from the data on "
                    "record, so this strategy has nothing to say about "
                    "whether to stay."),
                "evidence": evidence, "groups": groups, "note": note,
            },
        }

    unread = len(safety) + len(discount) - len(checked)
    # What the clock actually said, not what it did not say. The ladder above
    # acts on the clock having FAILED, so a clock nobody could read falls
    # through it — and this sentence then asserted the holding period had not
    # elapsed off a test that never ran. Absence reading as a pass in prose
    # is still absence reading as a pass; the rows below would have shown
    # "can't say" beside a summary claiming otherwise.
    clear = ("All " + str(len(checked)) + " exit tests that could be run came "
             "back clear"
             + (" and the holding period has not elapsed."
                if contract.test(ctx, CLOCK_CITE) == PASS
                else ", and how long you have held this could not be worked "
                     "out.")
             + (f" {unread} could not be worked out and are listed below as "
                "unknown rather than as passing." if unread else ""))
    return _more_money(ctx, evidence, groups, note, clear)


# -- may more money go into a name you already own ---------------------------
#
# Reached only when nothing above it fired: every exit that could be read came
# back clear, the clock has not run, and the position is not over its cap. So
# this asks one question, and it is deliberately not "is this a good idea" —
# it is "would this strategy buy this today, and is there room".
#
# The tests are the entry tests, unchanged. Not a softer set because you
# already own it and not a harder one because you are averaging in: an add is
# the same claim about the same business, made again, and the only honest way
# to make it is against the same bar. What is genuinely new is room, which is
# invisible on a first purchase and binding most of the time afterwards.
#
# What is deliberately NOT re-tested is the slot count. A slot is a name, and
# an add does not take a new one — citing the slot test here would refuse
# every add in a full portfolio, which is the opposite of what running a
# fixed number of positions means.
#
# What is deliberately NOT available is anything about what the position
# cost. Not the average, not the last price paid, not the distance from
# either. The host does not offer it, so a rule that put more money in
# because the price had fallen below what you paid cannot be written here —
# and that rule is the entire failure mode this screen was built against.

def _size_row(room, group):
    return {"label": "Room left under your target", "unit": "percent",
            "actual": room, "group": group}


def _sizing_cites(group):
    return [{"value": "portfolio-slots", "group": group},
            {"value": "position-weight-cap", "group": group}]


def _target_weight(values):
    """The share of the account one name is meant to reach: an equal share of
    the places this strategy runs, capped. The same arithmetic a first
    purchase is sized by, because it is the same question — this is where
    this name is supposed to end up, and a purchase is how far it currently
    is from there."""
    equal_share = round(100.0 / values["portfolio-slots"], 2)
    cap = float(values["position-weight-cap"])
    return (min(equal_share, cap),
            "an equal share of your places" if equal_share <= cap
            else "the cap on any one name")


def _more_money(ctx, evidence, groups, note, clear):
    values = ctx.get("values") or {}
    weight = ((ctx.get("position") or {}).get("weight")) or {}

    def held(state, rule, summary, extra=(), more_groups=()):
        return {"state": state, "payload": {},
                "reason": {"rule": rule, "summary": f"{clear} {summary}",
                           "evidence": evidence + list(extra),
                           "groups": groups + list(more_groups),
                           "note": note}}

    # Every figure below is derived from the position's weight, so a weight
    # nobody could work out is not a small gap — it is the whole question
    # unanswerable. Said as its own outcome rather than folded into "hold",
    # because "your rules would take more of this and the size could not be
    # worked out" and "your rules want nothing more here" are different
    # facts, and only one of them is fixed by finding a price.
    if weight.get("status") != "known":
        return held(
            "hold", "size-unreadable",
            "Whether there is room for more of it could not be worked out: "
            + str(weight.get("reason") or "this holding has no weight on "
                                          "record") + ".")

    target, bound = _target_weight(values)
    room = round(target - float(weight["value"]), 2)
    sizing = _sizing_cites(SIZING_GROUP["id"]) + [
        _size_row(room, SIZING_GROUP["id"])]

    if room <= 0:
        return held(
            "hold", "no-room-to-add",
            # One decimal, matching how the same figure renders in the row
            # below it. A weight printed at full precision reads as a measured
            # quantity rather than a share of an account that moves every time
            # the market opens — "48.9887%" is a number nobody could act on a
            # change in. The target beside it is this strategy's own
            # arithmetic over its own declared values and keeps its own
            # rendering.
            f"It is already at {float(weight['value']):.1f}% of the account "
            f"against a target of {target:g}%, set by {bound}, so no more "
            "money goes into it here.", sizing, [SIZING_GROUP])

    # The two baselines, in the order their consequences differ. Cumulative
    # drift is the stronger statement — it says the business you own is no
    # longer the one you underwrote — so it is asked first, and its answer is
    # a demand rather than a shrug.
    drift_cites, drift_out = _drift(ctx, "first-purchase", DRIFT_GROUP["id"])
    worse_cites, worse_out = _drift(ctx, "last-purchase", WORSE_GROUP["id"])
    both = (list(drift_cites) + list(worse_cites), [DRIFT_GROUP, WORSE_GROUP])

    if FAIL in drift_out:
        n = drift_out.count(FAIL)
        return {
            "state": "re-underwrite-owed",
            "payload": {"needs": [
                f"Read the most recent filings for this company and record "
                f"what you now think of it. {n} of the "
                f"{len(DRIFT)} measures this strategy watches "
                + ("has" if n == 1 else "have")
                + " moved further since your first purchase than this "
                  "strategy will put more money behind.",
                "Nothing is being sold. Every exit test came back clear, and "
                "this is a bar on adding to it, not a verdict on holding it.",
                "If you still want the position, the honest way back is to "
                "sell it and buy it again as a fresh decision — that is what "
                "resets what you are measured against."]},
            "reason": {
                "rule": "drifted-since-first-purchase",
                "summary": (
                    f"{clear} But {n} of the measures this strategy watches "
                    + ("has" if n == 1 else "have")
                    + " drifted further since you first bought than it will "
                      "add behind. No single quarter looked like this — that "
                      "is what the comparison against your first purchase is "
                      "for."),
                "evidence": evidence + both[0], "groups": groups + both[1],
                "note": note},
        }

    if UNKNOWN in drift_out or UNKNOWN in worse_out:
        n = drift_out.count(UNKNOWN) + worse_out.count(UNKNOWN)
        return held(
            "hold", "drift-unreadable",
            f"Whether it has changed since you bought could not be settled: "
            f"{n} of the {len(DRIFT) * 2} comparisons against your purchases "
            "could not be worked out. Nothing more goes in on a comparison "
            "nobody could make.", both[0], both[1])

    if FAIL in worse_out:
        n = worse_out.count(FAIL)
        return held(
            "hold", "worse-since-you-last-bought",
            f"{n} of the measures this strategy watches "
            + ("is" if n == 1 else "are")
            + " worse than when you last bought this, by more than it will "
              "add behind. That is not an exit — the absolute levels have "
              "not been crossed — it is a reason not to put more in until "
              "they recover or you re-read the business.", both[0], both[1])

    # It has not deteriorated and it has not drifted. Whether this strategy
    # would buy it *today* is the same fifteen tests a candidate faces, run
    # again from scratch. A holding that no longer screens is a holding this
    # strategy will not add to, and saying so is most of what this branch is
    # worth: it is the sentence that tells you your own rules would not buy
    # what you own.
    entry = _entry_screen(ctx)
    screen = (entry["evidence"], entry["groups"])
    req_fail, req_unknown = entry["req_fail"], entry["req_unknown"]

    # The clock and the cap are already cited above, and both sit in groups
    # demanding a pass. A commit beside a group the host resolves as anything
    # else is refused by the host — correctly — so this asks the same
    # question first and returns a state that explains itself instead.
    #
    # PASS and not "did not fail": an unreadable clock or an unreadable cap
    # has not shown there is room, and the ladder above only asked whether
    # either had FAILED. Absence must not walk through a gate by not
    # tripping it.
    steady = (contract.test(ctx, CLOCK_CITE) == PASS
              and contract.test(ctx, CAP_CITE) == PASS)

    body = (both[0] + screen[0] + sizing,
            both[1] + screen[1] + [SIZING_GROUP])

    # A settled no and an unfinished screen are different answers, and this
    # branch used to give the first one's sentence to both. A holding with an
    # unreadable market cap came back "your rules would not buy this today: 8
    # of 8 core passed and 0 of 5 knockouts came back against it" — a verdict
    # stating figures that contradict it, over a measure the rows beside it
    # showed as unknown. That is the exact failure the whole evidence
    # arrangement exists to refuse, and the candidate path has always split
    # them (`not-cheap-enough` against `cannot-screen`); only this one did
    # not. Same split, same order, same reasoning.
    if entry["settled_no"]:
        return held(
            "hold", "would-not-buy-it-today",
            "Your rules would not buy this today: "
            + (f'{req_fail} of the {entry["req_tested"]} tests this strategy '
               "will not bend came back against it"
               if req_fail else
               "nothing here answers " + _names_of(entry["short"]))
            + f', and {entry["passed"]} of the {entry["tested"]} tests behind '
            "the five questions passed. Holding what you have is a different "
            "question, and every exit test above came back clear.",
            *body)

    if not (entry["met"] and steady):
        missing = req_unknown + entry["unknown"] + (0 if steady else 1)
        return held(
            "hold", "screen-unreadable",
            f"Whether your rules would buy this today could not be settled: "
            f"{missing} of the tests that decide it could not be worked out "
            "from the data on record, and the ones that could do not settle "
            "it either way. Nothing more goes in on a screen that did not "
            "finish — an unreadable test is not a passing one.",
            *body)

    return {
        "state": "add",
        "payload": {"size": {"unit": "weight", "value": room},
                    "condition": None,
                    # Graham stages nothing, and should not. Buying a
                    # statistical discount in thirds is a rule this strategy
                    # does not have, and inventing one here so a screen has
                    # something to render would be putting a recommendation
                    # into shipped content. A strategy that genuinely stages
                    # declares its tranches here.
                    "plan": None},
        "reason": {
            "rule": "qualifies-and-has-room",
            "summary": (
                f"{clear} It still passes the tests that bought it — all "
                f'five questions answered, {entry["passed"]} of the '
                f'{entry["tested"]} tests behind them — '
                f"nothing has moved against you since either purchase, and "
                f"it sits {room:.1f}% of the account below the {target:g}% "
                f"target set by {bound}. That room is the whole of what may "
                "go in; where it goes is a question about your other "
                "holdings, not about this one."),
            "evidence": evidence + both[0] + screen[0] + sizing,
            "groups": groups + both[1] + screen[1] + [SIZING_GROUP],
            "note": note},
    }
