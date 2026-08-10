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

Sources, and which is which, because a reader auditing a number later has
to be able to tell. Every value carries its own `source` saying so, which
is where to look rather than here: this paragraph is the version that used
to have to be believed, and a claim made once at the top of a file is a
claim nobody can check against the twenty-ninth value somebody adds.

Twenty-six of the twenty-eight thresholds below are the expert report's,
verbatim — nothing is rounded, converted or adjusted. Six of those carry
the report's level and this strategy's reasoning, and say so. The last two,
`portfolio-slots` and `position-weight-cap`, come from Graham's own
documented practice, because the report was scoped to selection and to exits
and says nothing whatever about how much to buy.

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
REQUIRED = (
    ("pe_3y_avg_eps", "at_most", "max-pe-3y-avg"),
    ("price_to_book", "at_most", "max-price-to-book"),
    ("graham_combined_multiple", "at_most", "max-combined-multiple"),
    ("current_ratio", "at_least", "min-current-ratio"),
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
    ("market_cap", "at_least", "min-market-cap"),
    ("ncav_to_market_cap", "at_least", "min-ncav-to-market-cap"),
    ("earnings_yield_to_risk_free_multiple", "at_least",
     "min-earnings-yield-multiple"),
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


# ---------------------------------------------------------------------------
# Where the numbers came from.
#
# `name` is what to check a threshold against; `reasoning` says whether the
# account in that value's own `explain` is the source's or this strategy's.
#
# The distinction is the whole reason these are fields and not prose. Six of
# the twenty-eight values here have the report's level and an explanation
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


STRATEGY = {
    "id": "graham",
    "name": "Graham",
    "summary": "Buys an ordinary business only when its price is far below "
               "what its assets and its typical earnings justify, and sells "
               "when that gap closes, when the balance sheet stops being "
               "safe, or when two years are up — whichever comes first.",
    "version": 2,
    "contract": 5,
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
    },

    # -----------------------------------------------------------------
    # Eleven states. Every one of them is something a reader has to be
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

        {"id": "hold", "render": "hold",
         "name": "Nothing to do",
         "description": "You hold it, every exit test that could be run "
                        "came back clear, and the holding period you "
                        "committed to has not run out. Sitting still is the "
                        "whole activity."},

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
         "source": REPORT,
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
                    "It is a bonus test rather than a knockout: failing it "
                    "never blocks a buy on its own. It is reported so you "
                    "know what you are stepping into."},

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
                    "It will read as absent until this program can be told "
                    "what the risk-free rate is. That figure is not in any "
                    "filing and it is not price data, so nothing here is "
                    "entitled to invent one, and an absent reading is the "
                    "honest answer rather than a passing one. It is a bonus "
                    "test, so nothing is blocked by that."},

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
    bonus_cites, _bonus_out = _screen(ctx, BONUS, BONUS_GROUP["id"])

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
    return {
        "state": "hold", "payload": {},
        "reason": {
            "rule": "all-exit-tests-clear",
            "summary": (
                f"All {len(checked)} exit tests that could be run came back "
                "clear and the holding period has not elapsed."
                + (f" {unread} could not be worked out and are listed below "
                   "as unknown rather than as passing."
                   if unread else "")),
            "evidence": evidence, "groups": groups, "note": note,
        },
    }
