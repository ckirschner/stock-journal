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

Twenty-five of the twenty-seven thresholds below are the expert report's, at
the level it states. Two — `portfolio-slots` and `position-weight-cap` — come
from Buffett's own documented practice, because the report was scoped to
selection and to exits and says nothing whatever about how much to buy. That
is the same gap Graham had, and the answer is a genuinely different one: this
strategy concentrates where Graham spreads, and the difference is the point
rather than an accident of tuning.

**One thing a reader should know about the provenance of every number here.**
The expert report itself is not in this repository. The levels below were
taken from `dev_reference_docs/legacy-profiles/buffett.yaml`, which states in
its own header that its values are written exactly as the report states them,
and whose README records that it exists to be checked against. So the chain
is one link longer than Graham's was, and it is a transcription rather than
the document. Nothing here was rounded, converted or adjusted at either step,
and the one value written in a different form from the report's says so in
its own explanation.

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
# capital say the business is good. Leverage says it can survive being wrong.
# Owner earnings yield says you did not pay anything for it. Every other test
# here is evidence for one of those three.
REQUIRED = (
    ("roic_median_5y", "at_least", "min-roic"),
    ("total_debt_to_ebitda", "at_most", "max-debt-to-ebitda"),
    ("owner_earnings_yield", "at_least", "min-owner-earnings-yield"),
)

# Most of these must pass; how many is a declared value.
CORE = (
    ("interest_coverage", "at_least", "min-interest-coverage"),
    ("gross_margin_range_5y", "at_most", "max-gross-margin-range"),
    ("fcf_margin_median_5y", "at_least", "min-fcf-margin"),
    ("cash_conversion_median_5y", "at_least", "min-cash-conversion"),
    ("diluted_share_count_change_5y", "at_most", "max-share-count-change"),
    ("roe_median_5y", "at_least", "min-roe"),
    ("revenue_cagr_5y", "at_least", "min-revenue-cagr"),
    ("ni_minus_revenue_cagr_spread_5y", "at_least",
     "min-profit-growth-spread"),
    ("goodwill_intangibles_to_assets", "at_most", "max-goodwill-to-assets"),
)

# Never block. They are reported so the reader can see them and stop there.
#
# Four rows for three tests: the report states the tax check as a band, and
# a band is two comparisons. There is no `between` in the host's comparison
# vocabulary and this strategy does not want one — two rows say which end
# was missed, and one row could only say that something was.
BONUS = (
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
# The fourth element names the declared value holding how many consecutive
# filings the breach must appear on. Four of the five take the report's
# default of two; free cash flow takes its own window, because the report
# states one for it and a single negative quarter is working capital timing
# rather than news.
EXITS = (
    ("roic_median_5y", "at_least", "exit-roic-level",
     "sell-confirmation-filings"),
    ("total_debt_to_ebitda", "at_most", "exit-debt-to-ebitda",
     "sell-confirmation-filings"),
    ("interest_coverage", "at_least", "exit-interest-coverage",
     "sell-confirmation-filings"),
    ("fcf_margin_ttm", "at_least", "exit-fcf-margin", "fcf-exit-quarters"),
    ("diluted_share_count_change_3y", "at_most", "exit-share-count-change",
     "sell-confirmation-filings"),
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
# The grouping IS the rollup. Three knockouts where every one has to pass,
# seven of nine core tests, four reported and never blocking, three questions
# where every one has to come back a pass — that is the whole shape of the
# entry rule, and the host counts it from the rows it resolved rather than
# from a tally this file kept.
# ---------------------------------------------------------------------------

KNOCKOUTS = {"id": "knockouts", "name": "Tests this strategy will not bend",
             "requires": "all"}
CORE_GROUP = {"id": "core", "name": "Core tests", "requires": "at_least",
              "threshold_from": "core-tests-required"}
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

BUFFETT_PRACTICE = {
    "name": "Buffett's own documented practice — the 1993 Berkshire "
            "shareholder letter for the number of names, and the 1965 "
            "partnership letter for how large one may get. The expert report "
            "was scoped to selection and to exits and says nothing whatever "
            "about how much to buy, so its silence here is a gap in the "
            "source rather than a decision it made",
    "reasoning": True}


STRATEGY = {
    "id": "buffett",
    "name": "Buffett",
    "summary": "Buys a business good enough to be worth owning for decades, "
               "and only at a price that leaves something on the table. "
               "Sells when the business breaks — never when the price gets "
               "high, and never because time has passed.",
    "version": 2,
    "contract": 5,
    "changelog": {
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
         "type": "integer", "unit": "count", "min": 0, "max": 9,
         "source": REPORT_LEVEL_ONLY,
         "explain": "There are nine second-tier tests, and this is how many "
                    "of them have to come back clear before a buy is "
                    "possible. Seven of nine is the report's figure.\n\n"
                    "It is not nine of nine because no real company passes "
                    "every test in a list this strict — the gross margin "
                    "range alone rules out anything that buys a commodity, "
                    "and plenty of businesses worth owning do. It is not "
                    "five because at that point half the list can be wrong "
                    "and the list has stopped being a standard.\n\n"
                    "A test that could not be worked out counts as neither a "
                    "pass nor a failure: if the ones that are missing could "
                    "still have got you to seven, the verdict says it cannot "
                    "tell rather than saying no."},

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
                    "It needs your free cash to be answered in settings, "
                    "because a share of the account cannot be worked out "
                    "without knowing what the account is. Unanswered, the "
                    "size rules report that they could not be run.\n\n"
                    "Attributed to Buffett's practice, not to the expert "
                    "report, which does not cover sizing."},

        # -- the discipline that is not a measure --------------------------
        {"id": "sell-confirmation-filings",
         "label": "Filings an exit must appear on",
         "type": "integer", "unit": "count", "min": 1, "max": 8,
         "source": REPORT,
         "explain": "How many consecutive filings an exit level has to be "
                    "breached on before this strategy will act. Two is the "
                    "report's figure, and it applies to every exit here "
                    "except free cash flow, which has a window of its "
                    "own.\n\n"
                    "One goodwill impairment, one legal settlement, one "
                    "inventory build, and a measure crosses a line because "
                    "of something that happened once. For a tool whose "
                    "purpose is preventing panic decisions, firing on one "
                    "quarter's one-off charge is the worst possible failure: "
                    "it would use the authority of the system to cause "
                    "exactly the behaviour it exists to prevent. Set it to "
                    "one and you get that behaviour back.\n\n"
                    "A filing whose reading could not be worked out neither "
                    "advances the count nor resets it: a gap must not "
                    "confirm something nobody observed, and must not grant "
                    "an indefinite reprieve either."},

        {"id": "fcf-exit-quarters",
         "label": "Quarters of negative free cash flow that end it",
         "type": "integer", "unit": "count", "min": 1, "max": 12,
         "source": REPORT,
         "explain": "How many consecutive quarterly readings of free cash "
                    "flow have to come back negative before this strategy "
                    "acts on it. Four is the report's figure — a full "
                    "year.\n\n"
                    "It is longer than the two filings every other exit here "
                    "takes, and deliberately so. A single negative quarter "
                    "is working capital timing and nothing else. A full year "
                    "of it in a mature business means the thing you bought "
                    "no longer produces cash for its owners, which is the "
                    "whole thesis gone.\n\n"
                    "Where it misfires, and it is worth knowing before you "
                    "buy: a company deliberately in a heavy investment cycle "
                    "shows negative free cash flow as a choice rather than a "
                    "failure, and this will call it broken. If you are "
                    "buying that pattern on purpose, this is the number to "
                    "widen."},

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

        {"id": "max-debt-to-ebitda", "label": "Highest debt against earnings",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "How many years of the company's rough operating "
                    "earnings it would take to pay off everything it has "
                    "borrowed. At 2.5 it would take two and a half.\n\n"
                    "The preference is a business that could clear its debts "
                    "out of a couple of years of earnings. Three times is "
                    "where credit rating agencies start marking down "
                    "cyclical borrowers, so 2.5 leaves a full turn of "
                    "cushion before anyone outside the company gets nervous. "
                    "The point of intending to hold something forever is "
                    "that it never has to renegotiate anything at a bad "
                    "moment.\n\n"
                    "This is a knockout and the exit on the other side of it "
                    "is the exception to everything else this strategy "
                    "believes. Overpaying for a great business costs you "
                    "return. Leverage costs you the business. Every "
                    "permanent-capital disaster in this tradition ran "
                    "through the balance sheet and not the income "
                    "statement.\n\n"
                    "Where it misfires: a company with a lending arm of its "
                    "own reports borrowings that are its stock in trade "
                    "rather than a risk, and the combined figure means very "
                    "little. The journal marks those unreadable rather than "
                    "failing them."},

        {"id": "min-owner-earnings-yield",
         "label": "Lowest owner earnings yield",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "What the company's cash profits pay you each year, as a "
                    "percentage of what the whole company costs at today's "
                    "price. At 5 you are being paid five cents a year for "
                    "every dollar of price — which is another way of saying "
                    "you are paying twenty times earnings.\n\n"
                    "\"Owner earnings\" is the profit left after everything "
                    "the business must spend to stay as good as it is. It is "
                    "a stricter figure than reported profit and a more "
                    "honest one, because reported profit does not subtract "
                    "the machinery a company has to keep replacing.\n\n"
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
                    "**There is no exit on the other side of this, and that "
                    "is the most important empty field in the program.** A "
                    "business that compounds at 18% for twenty years will "
                    "spend most of those twenty years looking expensive. If "
                    "this could force a sale, this strategy would sell every "
                    "great business it ever bought, roughly three years in, "
                    "and would be destroying your returns while appearing to "
                    "work correctly."},

        # -- the nine core tests -------------------------------------------
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

        {"id": "max-gross-margin-range",
         "label": "Widest the gross margin may swing",
         "type": "number", "unit": "percentage_points", "min": 0,
         "source": REPORT,
         "explain": "Gross margin is what is left of each sales dollar after "
                    "the direct cost of the thing sold. This measures how "
                    "far it has moved between its best and worst year over "
                    "five — at 6 it has stayed inside a six-point band.\n\n"
                    "The range rather than the level, on purpose, and this "
                    "is the most easily misread test here. Requiring a *high* "
                    "gross margin — say forty percent — would exclude "
                    "high-volume retail and most of retail generally, which "
                    "this style has owned very happily. Stability is the "
                    "actual signal. Pricing power shows up as a flat line, "
                    "not a high one: a company that can pass its costs on "
                    "keeps the same margin whatever its inputs do.\n\n"
                    "Six points is wide enough to absorb one bad "
                    "input-cost year and narrow enough that commodity "
                    "producers fail every time, which is the "
                    "intent.\n\nWhere it misfires: a company that does not "
                    "report its cost of sales separately cannot be measured "
                    "at all, and many service businesses do not."},

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

        {"id": "min-roe", "label": "Lowest return on equity",
         "type": "number", "unit": "percent",
         "source": REPORT,
         "explain": "How much profit the company earns each year for every "
                    "dollar its owners have in it — the same idea as return "
                    "on invested capital, counting only the owners' money "
                    "and not the borrowed part. Taken as the middle reading "
                    "of five years.\n\n"
                    "Set at the same 15 and for the same reason: below that, "
                    "the spread over what the money costs is inside the "
                    "error bars of the calculation.\n\n"
                    "It is carried alongside return on invested capital "
                    "deliberately, and the redundancy is only apparent. The "
                    "two diverging is itself the information, because the "
                    "gap between them is borrowing: a company whose return "
                    "on equity is far above its return on capital is "
                    "producing that difference with debt rather than with "
                    "the business.\n\n"
                    "There is no exit on the other side of it, and that is "
                    "why. Return on equity is trivially inflated by "
                    "borrowing money, so a company that levers up to defend "
                    "a falling return will keep this test green right "
                    "through the deterioration. Return on invested capital "
                    "catches that; this does not.\n\n"
                    "Where it misfires: a company that has bought back so "
                    "much stock that its stated equity is near zero or "
                    "negative produces a number with no meaning, and the "
                    "journal marks it unreadable."},

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

        {"id": "max-goodwill-to-assets",
         "label": "Most of the company that may be goodwill",
         "type": "number", "unit": "percent", "min": 0,
         "source": REPORT,
         "explain": "How much of everything the company owns is goodwill and "
                    "other intangibles — the accounting entry created when a "
                    "company pays more for a business than that business's "
                    "identifiable assets are worth. At 40 it is two fifths "
                    "of the balance sheet.\n\n"
                    "Above roughly forty percent you are looking at a serial "
                    "acquirer, and the historical return figures above "
                    "reflect acquisition accounting more than they reflect "
                    "operating skill. The returns you are being shown were "
                    "partly bought.\n\n"
                    "There is no exit on the other side of it. A goodwill "
                    "write-off is an event rather than a level, and it is "
                    "usually the market telling you something you already "
                    "knew.\n\n"
                    "Where it misfires: genuinely good acquisitive "
                    "compounders fail this and should not. This strategy is "
                    "not built for them, which is a limitation to state "
                    "rather than to fix."},

        # -- the three bonus tests -----------------------------------------
        {"id": "min-effective-tax-rate", "label": "Lowest effective tax rate",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": REPORT,
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
                    "The report states this as one band. It is two settings "
                    "here because a band is two comparisons, and two rows on "
                    "the screen can say which end was missed where one row "
                    "could only say that something was."},

        {"id": "max-effective-tax-rate", "label": "Highest effective tax rate",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": REPORT,
         "explain": "The upper end of the tax band described above. Above "
                    "roughly thirty-five percent, either the company is "
                    "paying an unusual amount for a reason worth "
                    "understanding, or a one-off charge has landed in the "
                    "tax line and the profit figure is understated rather "
                    "than overstated.\n\n"
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

        {"id": "exit-debt-to-ebitda",
         "label": "Debt against earnings that ends the position",
         "type": "number", "unit": "times", "min": 0,
         "source": REPORT,
         "explain": "At four years of earnings' worth of borrowings the "
                    "balance sheet has stopped being the thing that lets you "
                    "hold this calmly.\n\n"
                    "This is the exception to everything else here, and it "
                    "is deliberate. This strategy will not sell a wonderful "
                    "business for being expensive, for being slow, or for "
                    "having been owned a long time. It will sell one for "
                    "borrowing too much, because overpaying costs you return "
                    "and leverage costs you the business.\n\n"
                    "Note the distance from the 2.5 required to buy. That "
                    "gap is deliberate: a company drifting from 2.5 to 2.8 "
                    "is not the same event as one arriving at 4.0, and an "
                    "exit set at the entry level would fire on ordinary "
                    "movement."},

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

def _confirmation_run(ctx, measure_id, comparator, value_id, group):
    """(consecutive filings on which the requirement failed, counting back
    from the newest, and the period ends of those filings).

    Every reading is put to the host, at its own period, through the same
    citation the reader will see beside it. A filing whose reading could not
    be worked out neither advances the run nor resets it: a gap must not
    confirm a breach nobody observed, and must not grant an indefinite
    reprieve either.
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


def _exit_state(ctx, group, measure_id, comparator, value_id, window_id):
    """One exit as fired / breached / clear / unreadable, with the filing
    periods that confirm it. `comparator` is what the holding must keep
    being true; the exit is that failing.

    `window_id` names the declared value holding how many consecutive
    filings this particular exit needs. Four of the five name the shared
    default and free cash flow names its own — read out of the settings
    rather than written here, so a journal that retunes either gets the
    behaviour it asked for.

    Absence never fires an exit. A missing reading is not evidence that a
    company is in trouble, and this program does not sell on silence — but
    it is not reported as clear either, so the caller can tell an exit that
    was checked from one that was not.
    """
    outcome = contract.test(ctx, _cite(measure_id, comparator, value_id,
                                       group))
    if outcome == UNKNOWN:
        return UNREADABLE, []
    if outcome != FAIL:
        return CLEAR, []
    need = (ctx.get("values") or {}).get(window_id)
    run, periods = _confirmation_run(ctx, measure_id, comparator, value_id,
                                     group)
    if isinstance(need, int) and run >= need:
        return FIRED, periods[:need]
    return BREACHED, periods


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
    state, periods = absolute
    if drift == PASS or state == CLEAR:
        return CLEAR, []
    if drift == UNKNOWN or state == UNREADABLE:
        return UNREADABLE, []
    return state, periods


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
    if states[ROIC][0] != CLEAR:
        return None
    drift = contract.test(ctx, {**ROIC_DRIFT, "group": group})
    level = contract.test(ctx, _cite(*EXITS[ROIC][:3], group))
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
    """How many consecutive filings the exits that fired actually carried.

    Counted rather than asserted. The sentence used to read "on more than
    one set of filings" whatever the settings said, which is the shipped
    default speaking rather than the rule that ran: a journal that lowers
    the confirmation to a single filing gets an exit that fires on one
    reading and a summary telling it the opposite, and a journal reading the
    free-cash-flow window gets four described as "more than one". A verdict
    has to name the rule that produced it, and this is the number in it.

    The two exits here can demand different windows, so where they disagree
    the count is not stated at all rather than a wrong one being picked.
    """
    counts = {n for _m, n in broken}
    if len(counts) != 1:
        return (" on the run of consecutive filings this strategy demands "
                "for each of them")
    n = counts.pop()
    if n <= 1:
        return (" on the most recent filing — this journal's settings ask "
                "for no more than that before acting")
    return (f" on {n} consecutive filings, so this is a change and not a "
            "wobble")


def _exit_evidence(group, states):
    """Every exit test, cited, with the confirming filings named where an
    exit actually fired. Citing the confirming readings is what lets the
    reader check the confirmation rule instead of taking it on trust.

    The fall in returns is cited beside the floor it is compounded with,
    always, and not only when it fires — the two are one test and a reader
    shown one of them has been shown half a rule.
    """
    out = []
    for i, ((measure_id, comparator, value_id, _w), (state, periods)) in \
            enumerate(zip(EXITS, states)):
        out.append(_cite(measure_id, comparator, value_id, group))
        if i == ROIC:
            out.append({**ROIC_DRIFT, "group": group})
        if state in (FIRED, BREACHED):
            for period in periods:
                out.append(_cite(measure_id, comparator, value_id, group,
                                 at=period))
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


def _entry_screen(ctx):
    """The fifteen entry tests, and what the host made of each.

    Returned as one object because every caller wants the same four
    questions answered — did a knockout fail, can the core count still be
    reached, was anything unreadable, and what should be cited — and a
    holding asks them in exactly the same way a candidate does. An add is
    the same claim about the same business made again, and the only honest
    way to make it is against the same bar.
    """
    values = ctx.get("values") or {}
    need = values.get("core-tests-required")
    req_cites, req_out = _screen(ctx, REQUIRED, KNOCKOUTS["id"])
    core_cites, core_out = _screen(ctx, CORE, CORE_GROUP["id"])
    bonus_cites, _bonus_out = _screen(ctx, BONUS, BONUS_GROUP["id"])
    core_pass, core_unknown = core_out.count(PASS), core_out.count(UNKNOWN)
    return {
        "need": need,
        "req_fail": req_out.count(FAIL),
        "req_unknown": req_out.count(UNKNOWN),
        "core_pass": core_pass,
        "core_unknown": core_unknown,
        "settled_no": (req_out.count(FAIL) > 0
                       or (isinstance(need, int)
                           and core_pass + core_unknown < need)),
        "met": (req_out.count(UNKNOWN) == 0 and isinstance(need, int)
                and core_pass >= need),
        "evidence": req_cites + core_cites + bonus_cites,
        "groups": [KNOCKOUTS, CORE_GROUP, BONUS_GROUP],
    }


def _on_a_candidate(ctx):
    values = ctx.get("values") or {}
    screen = _entry_screen(ctx)

    # A knockout that failed, or a core count that cannot be reached even if
    # every unreadable test came back clear. Either is a settled no — and
    # the three questions are deliberately NOT cited here, so nobody is
    # asked to assess the durability of a business their own rules have
    # already rejected.
    if screen["settled_no"]:
        return {
            "state": "not-wonderful-enough", "payload": {},
            "reason": {
                "rule": ("knockout-failed" if screen["req_fail"]
                         else "core-tests-short"),
                "summary": (
                    f'{screen["req_fail"]} of the {len(REQUIRED)} tests this '
                    "strategy will not bend came back against it, and one is "
                    "enough."
                    if screen["req_fail"] else
                    f'Only {screen["core_pass"]} of the {len(CORE)} core '
                    f'tests passed and {screen["core_unknown"]} could not be '
                    f'worked out, so {screen["need"]} is out of reach.'),
                "evidence": screen["evidence"], "groups": screen["groups"],
            },
        }

    if not screen["met"]:
        missing = screen["req_unknown"] + screen["core_unknown"]
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
                    f"It passes {screen['core_pass']} of the {len(CORE)} "
                    f"core tests and every test this strategy will not bend, "
                    f"and you have marked "
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
            "payload": {"needs": _needs(owed) + [
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
                    f"Every number this strategy checks is in order — "
                    f"{screen['core_pass']} of {len(CORE)} core tests and "
                    f"all {len(REQUIRED)} it will not bend. What decides it "
                    "now is "
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
                f"Every test this strategy will not bend passed, "
                f"{screen['core_pass']} of {len(CORE)} core tests did "
                f"against a bar of {screen['need']}, and you have answered "
                f"all three questions yes. The size is {size:g}% of the "
                f"account, set by {bound}."),
            "evidence": evidence, "groups": groups,
        },
    }


# What each of the three is asking, in one clause, for the one place a
# sentence has to be built here rather than cited.
#
# These are this strategy's own paraphrases and not the bank's text, which is
# a compromise worth naming rather than hiding. A blocked verdict has to say
# what is owed specifically enough to act on, and "answer the qualitative
# measures" is not that — but the context hands a strategy a measure's value
# and not its label, so there is no way to reach the host's own words from
# inside `decide`. Everywhere a label matters the host supplies it: the rows
# under this verdict, and the questions in full under "Your judgement" on the
# same page, are the bank's own text. Only these five-word summaries are this
# file's, and a reader who follows them lands on the real question.
#
# The gap is a request against the host rather than something to solve here,
# and the failure mode if these drift is mild: a paraphrase that reads a
# little differently from the question it points at.
_ASKING = {
    "moat_durability": "Whether the moat holds for another decade",
    "management_integrity": "Whether management can be taken at their word",
    "capital_allocation": "Whether spare cash has gone somewhere worth more "
                          "than paying it out",
}


def _needs(owed):
    """One sentence per unanswered question, named specifically enough to
    act on. Falls back to the bank id, which is what the screen shows beside
    it anyway, so a question added to the bank is never a blank line."""
    return [f"{_ASKING.get(m, m)} — unanswered." for m in owed]


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

    waiting = [s for s, _p in states if s == BREACHED]

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
    broken = [(EXITS[i][0], len(p)) for i, (s, p) in enumerate(states)
              if s == FIRED]
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
                    + " not yet been crossed on enough consecutive filings "
                      "to act on. Nothing is owed from you today."),
                "evidence": evidence, "groups": groups,
            },
        }

    checked = [s for s, _p in states if s != UNREADABLE]
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
            f"Your rules would not buy this today: {screen['req_fail']} of "
            f"the {len(REQUIRED)} tests this strategy will not bend came back "
            f"against it, and {screen['core_pass']} of {len(CORE)} core tests "
            f"passed against a bar of {screen['need']}. Holding what you have "
            "is a different question, and every exit test above came back "
            "clear — a business that has stopped being cheap enough to buy "
            "again is not a business that has stopped being worth owning.",
            *body)

    if not screen["met"]:
        missing = screen["req_unknown"] + screen["core_unknown"]
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
                f"{screen['core_pass']} of {len(CORE)} core tests against a "
                f"bar of {screen['need']} — your three answers still stand, "
                f"and it sits {room:.1f}% of the account below the {cap:g}% "
                "most this strategy will take one name to. That room is the "
                "whole of what may go in; where it goes is a question about "
                "your other holdings, not about this one."),
            "evidence": evidence + screen["evidence"] + sizing,
            "groups": groups + screen["groups"] + [SIZING_GROUP]},
    }
