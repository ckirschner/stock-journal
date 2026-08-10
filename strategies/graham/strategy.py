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

**Nothing fires on one reading.** Every exit has to appear on two
consecutive filings before it counts. One goodwill impairment, one legal
settlement, one inventory build, and a measure crosses a line on noise —
and a tool whose purpose is preventing panic decisions must not use its own
authority to cause one. A crossed line that is not yet confirmed is a state
of its own, so the user can see the rule declining to panic rather than
seeing nothing at all.

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
REQUIRED = (
    ("pe_3y_avg_eps", "at_most", "max-pe-3y-avg"),
    ("price_to_book", "at_most", "max-price-to-book"),
    ("graham_combined_multiple", "at_most", "max-combined-multiple"),
    ("current_ratio", "at_least", "min-current-ratio"),
    ("market_cap", "at_least", "min-market-cap"),
)

# Most of these must pass; how many is a declared value.
CORE = (
    ("ltd_to_working_capital", "at_most", "max-ltd-to-working-capital"),
    ("profitable_years_10y", "at_least", "min-profitable-years"),
    ("altman_z_score", "at_least", "min-altman-z"),
    ("eps_growth_10y", "at_least", "min-eps-growth-10y"),
    ("consecutive_dividend_years", "at_least", "min-dividend-years"),
    ("debt_to_equity", "at_most", "max-debt-to-equity"),
    ("price_to_net_tangible_assets", "at_most", "max-price-to-tangible"),
    ("accruals_ratio", "at_most", "max-accruals-ratio"),
)

# Never block. They are reported so the reader can see them and stop there.
BONUS = (
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
# The fourth element says the failure counts its own filings. It is true of
# exactly one measure here: a run of consecutive annual losses is itself a
# count of annual reports, so a level of two already means two filings and
# the confirmation rule must not be charged a second time on top of it.
#
# Whether that actually holds is DERIVED from the two settings rather than
# asserted here — see _self_confirms. A journal that lowers the exit to one
# losing year has a level that no longer embodies the confirmation, and the
# ordinary rule has to come back rather than a hardcoded True asserting a
# confirmation that never happened.
EXITS_SAFETY = (
    ("current_ratio", "at_least", "exit-current-ratio", False),
    ("ltd_to_working_capital", "at_most", "exit-ltd-to-working-capital",
     False),
    ("altman_z_score", "at_least", "exit-altman-z", False),
    ("debt_to_equity", "below", "exit-debt-to-equity", False),
    ("consecutive_annual_loss_years", "below", "exit-loss-years", True),
)

EXITS_DISCOUNT = (
    ("pe_3y_avg_eps", "below", "exit-pe-3y-avg", False),
    ("price_to_book", "below", "exit-price-to-book", False),
    ("graham_combined_multiple", "below", "exit-combined-multiple", False),
)

# The dividend run is watched but never acts. A cut is real information about
# distress, and by the time it lands the balance-sheet exits will already be
# talking; it should send the reader to the filings, not to the sell button.
DIVIDEND_RUN = "consecutive_dividend_years"

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
    ("altman_z_score", "at_least", "drift-altman-z"),
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
CORE_GROUP = {"id": "core", "name": "Core tests", "requires": "at_least",
              "threshold_from": "core-tests-required"}
BONUS_GROUP = {"id": "bonus", "name": "Reported, never blocking",
               "requires": "noted"}
SIZING_GROUP = {"id": "sizing", "name": "Room in the list, and how much",
                "requires": "all"}

# On a holding, the two exit families demand nothing of a single reading —
# that is the confirmation rule, and it counts filings, which is not
# something the host can express. So they are `noted`: the host reports how
# they came out and this strategy decides what a run of them means. What the
# group names is which kind of news they are.
SAFETY_GROUP = {"id": "safety",
                "name": "The balance sheet and the earnings record",
                "requires": "noted"}
DISCOUNT_GROUP = {"id": "discount", "name": "The discount you bought",
                  "requires": "noted"}
CLOCK_GROUP = {"id": "clock", "name": "The holding period", "requires": "all"}
SIZE_GROUP = {"id": "size", "name": "How big it has got", "requires": "all"}
DIVIDEND_GROUP = {"id": "dividend", "name": "The dividend run",
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


STRATEGY = {
    "id": "graham",
    "name": "Graham",
    "summary": "Buys an ordinary business only when its price is far below "
               "what its assets and its typical earnings justify, and sells "
               "when that gap closes, when the balance sheet stops being "
               "safe, or when two years are up — whichever comes first.",
    "version": 6,
    "contract": 5,
    "declines": DECLINES,
    "changelog": {
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
        {"id": "core-tests-required", "label": "Core tests that must pass",
         "type": "integer", "unit": "count", "min": 0, "max": 8,
         "source": REPORT_LEVEL_ONLY,
         "explain": "There are eight second-tier tests, and this is how "
                    "many of them have to come back clear before a buy is "
                    "possible. Six of eight is the report's figure. It is "
                    "not eight of eight because no real company passes "
                    "every test in a list this strict, and it is not four "
                    "because at that point the list has stopped being a "
                    "standard. A test that could not be worked out counts "
                    "as neither a pass nor a failure: if the ones that are "
                    "missing could still have got you to six, the verdict "
                    "says it cannot tell rather than saying no."},

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
         "explain": "How far the Altman Z-score — a combined read on how "
                    "close a company is to financial distress — may fall "
                    "from where it was at a purchase before this strategy "
                    "stops adding.\n\n"
                    "A negative number, because it is a fall. Minus 0.6 is "
                    "half the distance from the 3.0 required to buy to the "
                    "1.8 that sells, and the score is built to move slowly, "
                    "so a fall of this size is not noise."},

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
                    "Shorten it and you will be selling discounts that had "
                    "not finished closing. Lengthen it and you are "
                    "reintroducing exactly the open-ended patience it "
                    "exists to refuse."},

        {"id": "sell-confirmation-filings",
         "label": "Filings an exit must appear on",
         "type": "integer", "unit": "count", "min": 1, "max": 8,
         "source": REPORT,
         "explain": "How many consecutive filings an exit level has to be "
                    "breached on before this strategy will act. Two is the "
                    "report's figure, and it applies to every exit here.\n\n"
                    "One goodwill impairment, one legal settlement, one "
                    "inventory build, and a measure crosses a line because "
                    "of something that happened once. Acting on that would "
                    "be the tool using its own authority to cause the panic "
                    "decision it exists to prevent — which is the worst "
                    "thing it could possibly do. Set it to one and you get "
                    "that behaviour back.\n\n"
                    "A filing whose reading could not be worked out neither "
                    "advances the count nor resets it: a gap must not "
                    "confirm something nobody observed, and must not grant "
                    "an indefinite reprieve either. The one exit this does "
                    "not apply to is the run of annual losses, because two "
                    "consecutive losing years are already two consecutive "
                    "filings."},

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
         "source": REPORT,
         "explain": "A single score built from five things about the "
                    "balance sheet and the profits, weighted by how well "
                    "each one predicted companies going broke in the study "
                    "that produced it. Above 3.0 is the safe zone; below "
                    "1.8 is the distress zone; in between is a grey "
                    "area.\n\n"
                    "3.0 rather than the grey area, because this strategy "
                    "holds a business it has formed no opinion about and "
                    "therefore takes the full cushion rather than half of "
                    "it.\n\n"
                    "This is the one test here that Graham never used. It "
                    "was published in 1968 and it is not his, but it is "
                    "the formalisation of precisely what his balance-sheet "
                    "tests were reaching for, and it has fifty years of "
                    "out-of-sample validation behind it, which none of his "
                    "individual ratios do. He would recognise the intent "
                    "even though he never saw the formula.\n\n"
                    "Where it misfires: its author excluded financial "
                    "companies, because the ratios do not map onto them. "
                    "Companies that own very little score poorly for "
                    "reasons unrelated to distress, and young companies "
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

        {"id": "min-dividend-years",
         "label": "Lowest unbroken run of dividend years",
         "type": "integer", "unit": "years", "min": 0,
         "source": REPORT,
         "explain": "How many years in a row the company has paid its "
                    "owners cash. A long unbroken run means it has come "
                    "through a full economic cycle and hands money back "
                    "rather than only promising to.\n\n"
                    "Ten rather than Graham's own twenty, and this is a "
                    "deliberate departure worth being explicit about. He "
                    "wrote before a 1982 rule change made buying back "
                    "shares a safe, routine alternative to paying "
                    "dividends. A twenty-year requirement today screens out "
                    "a large set of companies that return capital "
                    "consistently by repurchasing shares instead, which he "
                    "had no reason to anticipate. Ten preserves the signal "
                    "without penalising the change of mechanism.\n\n"
                    "Where it misfires: precisely there. A company that has "
                    "returned every spare dollar to shareholders through "
                    "buybacks for fifteen years reads as zero here."},

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

        # -- the three bonus tests -----------------------------------------
        {"id": "min-market-cap", "label": "Smallest company worth buying",
         "type": "number", "unit": "usd", "min": 0,
         "source": REPORT_LEVEL_ONLY,
         "explain": "What the stock market says the whole company's shares "
                    "are worth: every share multiplied by the price of "
                    "one.\n\n"
                    "Graham used $100M in 1972 as a test of adequate size, "
                    "which adjusts for inflation to roughly $750M today. "
                    "$300M is deliberately lower, because the discounts "
                    "this strategy hunts are disproportionately in smaller "
                    "companies and a $750M floor removes most of the "
                    "opportunity. $300M keeps filing quality and the "
                    "ability to sell when you want to acceptable without "
                    "gutting the list.\n\n"
                    "It is a test this strategy will not bend: below it, no "
                    "amount of cheapness counts. That placement is this "
                    "strategy's and not the report's, which scores this "
                    "test rather than disqualifying on it. The reasoning "
                    "the report gives for the level is filing quality and "
                    "being able to sell when you want to, and neither of "
                    "those is something a good score somewhere else makes "
                    "up for. A forty-million-dollar company can be cheap on "
                    "every other line here and still be a position you "
                    "cannot get out of.\n\n"
                    "Where it misfires: it is a price times a share count, "
                    "so it moves with the price. A holding that has halved "
                    "may now fail a test it passed when you bought — which "
                    "is why it is an entry test and there is no exit on the "
                    "other side of it. And a company whose shares are "
                    "closely held trades far less than its size suggests, "
                    "which this cannot see."},

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
         "label": "Lowest earnings yield against the risk-free rate",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "How many times more the company's earnings pay you "
                    "than lending the same money to the government would. "
                    "At 2.0 the stock's earnings yield is twice the "
                    "risk-free rate; at 1.0 you are taking every risk of "
                    "owning a business for a government-bond return.\n\n"
                    "Graham's Enterprising Investor test, which compared "
                    "the earnings yield to the corporate bond yield of his "
                    "day. It is the one test here that makes every other "
                    "valuation level in the strategy aware of what interest "
                    "rates are doing — a 6.7% earnings yield means "
                    "something very different when cash pays 1% than when "
                    "it pays 5%.\n\n"
                    "This and the risk-free rate below are read together, "
                    "and what they come to is a ceiling on what you may pay "
                    "for a dollar of typical earnings: at 2.0 against a "
                    "rate of 4%, an earnings yield of 8% or better, which "
                    "is 12.5 times earnings or less. That is the figure the "
                    "test is shown against, because it is the one being "
                    "compared.\n\n"
                    "It is a bonus test: failing it never blocks a buy. "
                    "Expect it to fail often at a high risk-free rate — "
                    "that is the test working, and it is telling you the "
                    "same money is being offered a competitive return with "
                    "none of the risk."},

        {"id": "risk-free-rate", "label": "The risk-free rate",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": {"name": "this strategy's author. The expert report names "
                            "the comparison but not a rate, because a rate "
                            "is not the kind of thing a report can fix — it "
                            "is whatever the government is paying while you "
                            "are reading this",
                    "reasoning": True},
         "explain": "What lending money to the government pays right now: "
                    "the yield on the ten-year US Treasury note, as an "
                    "annual percentage. It is the return you can have "
                    "without taking any business risk at all, so it is what "
                    "owning a business has to beat before the risk is worth "
                    "taking.\n\n"
                    "**This is the one number here you have to maintain, "
                    "and it is the only one that goes wrong just by sitting "
                    "still.** Nothing in this program fetches it — it is in "
                    "no filing and it is not price data — so the figure "
                    "shipped with the strategy is a starting point and "
                    "nothing more. Look up the current ten-year Treasury "
                    "yield and set it here; when rates move, come back. A "
                    "rate left at 4% while the market pays 6% quietly makes "
                    "this test easier than you agreed it should be.\n\n"
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
                    "caught. The same combined number the entry test uses, "
                    "at the level where the discount has closed.\n\n"
                    "Roughly a doubling of the entry level, which is how "
                    "the report derives it."},

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
         "source": REPORT,
         "explain": "Below 1.8 is the distress zone of the score described "
                    "in the entry test above — the range in which companies "
                    "in the original study went broke.\n\n"
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
                    "This is the one exit the two-filing confirmation rule "
                    "is not applied to a second time. Two consecutive "
                    "annual losses are already two consecutive annual "
                    "filings; requiring another two would mean waiting four "
                    "years to act on a company that has been losing money "
                    "throughout."},
    ],
}


# ---------------------------------------------------------------------------
# reading what the host handed over
# ---------------------------------------------------------------------------

PASS, FAIL, UNKNOWN = contract.PASS, contract.FAIL, contract.UNKNOWN
FIRED, BREACHED, CLEAR, UNREADABLE = "fired", "breached", "clear", "unreadable"


def _points(ctx, measure_id):
    """One measure's per-filing readings, oldest first."""
    entry = (ctx.get("measures") or {}).get(measure_id) or {}
    return ((entry.get("series") or {}).get("points")) or []


def _cite(measure_id, comparator, value_id, group, at=None):
    """One citation: which measure, which direction, and the setting the
    host reads the limit out of. Nothing here is a number."""
    item = {"measure": measure_id, "comparator": comparator,
            "threshold_from": value_id, "group": group}
    if at is not None:
        item["at"] = at
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
# the earnings yield against the risk-free rate
#
# Graham's Enterprising Investor test, and the one test here this strategy
# works out for itself instead of naming a measure that already holds the
# answer.
#
# There used to be a bank measure for it and it never ran. It needed a
# risk-free rate; the rate is in no filing, it is not price data, and nothing
# in the host could hand one over — so a row that looked like a test was
# permanently absent, which is the worst state for a test to be in, because
# it reads as a gap in the data rather than as a question nobody was ever
# able to ask.
#
# It moves here for a better reason than convenience. An earnings yield is a
# fact. What you compare it against is an opinion, and this strategy is the
# thing entitled to hold one — so the rate is a declared value like every
# other limit in this file, retunable, with any change to it landing on the
# journal's rule-change record with a before and an after.
#
# The measure is still cited and never quoted. Working out `1/PE ÷ rate` here
# and stating the answer would be this strategy restating a figure the host
# owns, and a restatement can be wrong. So the test is expressed as what it
# actually constrains: an earnings yield of at least `multiple × rate` per
# cent is exactly a price of at most `100 ÷ (multiple × rate)` times typical
# earnings. The strategy owns the question and the limit; the host still owns
# the figure, its unit, and whether the comparison was met.
#
# This is the one limit in this file the strategy states rather than names,
# and it is the one case the evidence vocabulary cannot express: a row cites
# ONE setting or states ONE number, and this limit is worked out from two
# settings. So both are cited beside it as the observations they are. That is
# the difference between a number a reader can check and a number they have
# to accept — 12.5 with "twice" and "4%" underneath it is arithmetic anyone
# can redo, and 12.5 on its own is this file asking to be trusted.
# ---------------------------------------------------------------------------

_YIELD_SETTINGS = ("min-earnings-yield-multiple", "risk-free-rate")


def _earnings_yield_cite(values):
    """The earnings-yield test as the ceiling on the earnings multiple it
    amounts to, or None where the two settings do not describe a limit.

    Both are declared values with defaults, so the arithmetic normally cannot
    fail — but either can be overridden to nought in a journal, and dividing
    by that would take the whole verdict down over a bonus test that blocks
    nothing. None means the caller shows the settings and no comparison,
    which is what a limit nobody could work out honestly looks like.
    """
    multiple, rate = (values.get(v) for v in _YIELD_SETTINGS)
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
               and v > 0 for v in (multiple, rate)):
        return None
    return {"measure": "pe_3y_avg_eps", "comparator": "at_most",
            "threshold": round(100.0 / (multiple * rate), 2),
            "group": BONUS_GROUP["id"]}


def _bonus_cites(ctx, values):
    """The reported-never-blocking rows, and the two settings behind the one
    row whose limit this strategy works out for itself.

    The settings are cited whether or not the limit could be built. Where it
    could, they are how the reader checks it; where it could not, they are
    the only thing left saying a test exists at all.
    """
    cites, _outcomes = _screen(ctx, BONUS, BONUS_GROUP["id"])
    derived = _earnings_yield_cite(values)
    return (cites + ([derived] if derived is not None else [])
            + [{"value": v, "group": BONUS_GROUP["id"]}
               for v in _YIELD_SETTINGS])


# ---------------------------------------------------------------------------
# the exits, and the confirmation walk
# ---------------------------------------------------------------------------

def _confirmation_run(ctx, measure_id, comparator, value_id, group):
    """(consecutive filings on which the requirement failed, counting back
    from the newest, and the period ends of those filings).

    Every reading is put to the host, at its own period, through the same
    citation the reader will see beside it. A filing whose reading could not
    be worked out neither advances the run nor resets it: a gap must not
    confirm a breach nobody observed, and must not grant an indefinite
    reprieve either — it pauses, and the periods returned say which filings
    actually carried the breach.
    """
    run, periods = 0, []
    for point in reversed(_points(ctx, measure_id)):
        outcome = contract.test(
            ctx, _cite(measure_id, comparator, value_id, group,
                       at=point["period_end"]))
        if outcome == UNKNOWN:
            continue
        if outcome != FAIL:
            break
        run += 1
        periods.append(point["period_end"])
    return run, periods


def _exit_state(ctx, group, measure_id, comparator, value_id,
                self_confirming):
    """One exit as fired / breached / clear / unreadable, with the filing
    periods that confirm it. `comparator` is what the holding must keep
    being true; the exit is that failing.

    Absence never fires an exit. A missing reading is not evidence that a
    company is in trouble, and this program does not sell on silence — but
    it does not report it as clear either, so the caller can tell the
    difference between an exit that was checked and one that was not.
    """
    outcome = contract.test(ctx, _cite(measure_id, comparator, value_id,
                                       group))
    if outcome == UNKNOWN:
        return UNREADABLE, []
    if outcome != FAIL:
        return CLEAR, []
    values = ctx.get("values") or {}
    need = values.get("sell-confirmation-filings")
    if self_confirming and _counts_its_own_filings(values.get(value_id),
                                                   need):
        return FIRED, []
    run, periods = _confirmation_run(ctx, measure_id, comparator, value_id,
                                     group)
    if isinstance(need, int) and run >= need:
        return FIRED, periods[:need]
    return BREACHED, periods


def _counts_its_own_filings(limit, need):
    """Whether an exit whose measure counts annual reports already carries
    the confirmation in its own level.

    A run of two losing years spans two annual filings, so demanding two
    consecutive filings on top of it would demand a third losing year. That
    reasoning holds only while the level is at least the confirmation count
    — set the exit to one losing year and it stops holding, so it is worked
    out rather than declared.
    """
    return (isinstance(limit, (int, float)) and isinstance(need, int)
            and not isinstance(limit, bool) and limit >= need)


def _dividend_cut(ctx):
    """The two period ends across which an unbroken dividend run reset since
    this holding was opened, or None.

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
    readable = [p for p in _points(ctx, DIVIDEND_RUN)
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


def _on_a_candidate(ctx):
    values = ctx.get("values") or {}
    need = values.get("core-tests-required")

    req_cites, req_out = _screen(ctx, REQUIRED, KNOCKOUTS["id"])
    core_cites, core_out = _screen(ctx, CORE, CORE_GROUP["id"])
    bonus_cites = _bonus_cites(ctx, values)

    req_fail = req_out.count(FAIL)
    req_unknown = req_out.count(UNKNOWN)
    core_pass, core_unknown = core_out.count(PASS), core_out.count(UNKNOWN)

    could_still_reach = (core_pass + core_unknown >= need
                         if isinstance(need, int) else None)
    core_met = core_pass >= need if isinstance(need, int) else None

    # No tallies are cited. The counts used to be evidence items this
    # strategy worked out and stated — "Knockout tests passed, 3, at least
    # 4" — which meant the rollup on screen came from a different
    # computation than the rows under it, and had to carry its own careful
    # handling of the grey case so that three passes with one unreadable did
    # not render identically to three passes with one failed. Both of those
    # are the host's now: it counts the outcomes it resolved, against the
    # bar the group names, and an unreadable row is neither a pass nor a
    # failure there for exactly the reason it is neither here.
    groups = [KNOCKOUTS, CORE_GROUP, BONUS_GROUP]
    evidence = req_cites + core_cites + bonus_cites

    # A knockout that failed, or a core count that cannot be reached even if
    # every unreadable test came back clear. Either is a settled no.
    if req_fail or could_still_reach is False:
        return {
            "state": "not-cheap-enough", "payload": {},
            "reason": {
                "rule": "knockout-failed" if req_fail else "core-tests-short",
                "summary": (
                    f"{req_fail} of the {len(REQUIRED)} tests this strategy "
                    "will not bend came back against it, and one is enough."
                    if req_fail else
                    f"Only {core_pass} of the {len(CORE)} core tests passed "
                    f"and {core_unknown} could not be worked out, so "
                    f"{need} is out of reach."),
                "evidence": evidence, "groups": groups,
            },
        }

    # Nothing has failed, but something that has not been read could still
    # decide it. Absence is not a pass, so nothing is claimed.
    if req_unknown or core_met is not True:
        missing = req_unknown + core_unknown
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
                f"Every knockout test passed and {core_pass} of "
                f"{len(CORE)} core tests did, against a bar of {need}. "
                f"The size is {size:g}% of the account, set by {bound}."),
            "evidence": evidence, "groups": groups,
        },
    }


# -- a security you own ------------------------------------------------------

CAP_CITE = {"fact": "position.weight", "comparator": "at_most",
            "threshold_from": "position-weight-cap",
            "group": SIZE_GROUP["id"]}


def _exit_evidence(group, rows, states):
    """Every exit test, cited, with the confirming filings named where an
    exit actually fired. Citing the confirming readings is what lets the
    reader check the two-filing rule instead of taking it on trust."""
    out = []
    for (measure_id, comparator, value_id, _self), (state, periods) in zip(
            rows, states):
        out.append(_cite(measure_id, comparator, value_id, group))
        if state in (FIRED, BREACHED):
            for period in periods:
                out.append(_cite(measure_id, comparator, value_id, group,
                                 at=period))
    return out


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

    cut = _dividend_cut(ctx)
    note = None
    if cut is not None:
        before, after = cut
        evidence.append({"measure": DIVIDEND_RUN, "at": before,
                         "group": DIVIDEND_GROUP["id"]})
        evidence.append({"measure": DIVIDEND_RUN, "at": after,
                         "group": DIVIDEND_GROUP["id"]})
        groups.append(DIVIDEND_GROUP)
        note = ("The unbroken run of dividend years has reset since the "
                f"filing for {before}. That is real information about "
                "financial distress and it changes nothing here on its own "
                "— by the time a dividend is cut the balance-sheet exits "
                "are usually already talking. Go and read the filing.")

    def fired(states, rows):
        return [rows[i][0] for i, (state, _p) in enumerate(states)
                if state == FIRED]

    waiting = [state for state, _p in safety + discount if state == BREACHED]

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
                    + " failed on more than one reading, so this is a change "
                    "and not a wobble. The cushion that made an unremarkable "
                    "business acceptable is gone." + also_waiting()),
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
                    + " failed on the run of filings this strategy "
                    "demands before acting. The gap you bought has closed, "
                    "which is this strategy working rather than failing."
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

    checked = [state for state, _p in safety + discount
               if state != UNREADABLE]
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
            f"It is already at {float(weight['value']):g}% of the account "
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
    req_cites, req_out = _screen(ctx, REQUIRED, KNOCKOUTS["id"])
    core_cites, core_out = _screen(ctx, CORE, CORE_GROUP["id"])
    bonus_cites = _bonus_cites(ctx, values)
    need = values.get("core-tests-required")
    screen = (req_cites + core_cites + bonus_cites,
              [KNOCKOUTS, CORE_GROUP, BONUS_GROUP])
    req_fail, req_unknown = req_out.count(FAIL), req_out.count(UNKNOWN)
    core_pass, core_unknown = core_out.count(PASS), core_out.count(UNKNOWN)
    could_still_reach = (core_pass + core_unknown >= need
                         if isinstance(need, int) else None)
    core_met = core_pass >= need if isinstance(need, int) else None

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
    if req_fail or could_still_reach is False:
        return held(
            "hold", "would-not-buy-it-today",
            f"Your rules would not buy this today: {req_fail} of the "
            f"{len(REQUIRED)} tests this strategy will not bend came back "
            f"against it, and {core_pass} of {len(CORE)} core tests passed "
            f"against a bar of {need}. Holding what you have is a different "
            "question, and every exit test above came back clear.",
            *body)

    if not (core_met is True and not req_unknown and steady):
        missing = req_unknown + core_unknown + (0 if steady else 1)
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
                f"{clear} It still passes the tests that bought it — "
                f"{core_pass} of {len(CORE)} core against a bar of {need} — "
                f"nothing has moved against you since either purchase, and "
                f"it sits {room:g}% of the account below the {target:g}% "
                f"target set by {bound}. That room is the whole of what may "
                "go in; where it goes is a question about your other "
                "holdings, not about this one."),
            "evidence": evidence + both[0] + screen[0] + sizing,
            "groups": groups + both[1] + screen[1] + [SIZING_GROUP],
            "note": note},
    }
