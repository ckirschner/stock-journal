"""The host/strategy contract.

The host is the rendering engine; a strategy is the decision engine. This
module is the line between them: what a strategy must declare about itself,
what it receives, what it must return, and the six render types the host owns.

Everything that crosses the line is plain data. A strategy is handed one plain
dict (built in engine/context.py) and returns one plain dict — a state it
declared, a payload shaped by that state's render type, and a structured
reason. The host validates both directions and refuses, legibly, anything
that doesn't conform. A strategy never invents vocabulary: an undeclared
state, an unknown payload key, or a render type of its own devising is an
error in place, not a new feature.

A reason carries typed evidence, not prose. The strategy cites what it looked
at and what it required; the host answers with the figure, its label and unit,
whether it was absent and why, and how the comparison came out. That is what
lets a screen write "Return on invested capital, 5-year median — 18.9%, at
least your minimum of 15%" without the strategy pre-rendering a sentence, and
it is what lets the same evidence be compared across securities and counted
over time. Prose that genuinely will not fit goes in `reason.note`, which is
one string and deliberately harder to reach for.

Evidence is gathered into *groups*, and a group says what it demands of its
own members — all of them, at least so many of them, or nothing. Two things
follow, and the second is why a group is more than a subheading. A reader
looking at fifteen rows learns which four were disqualifying without being
told in prose. And the host can count the passes itself, which means the
rollup — "six of eight" — is derived from the same outcomes the rows render,
and a state that puts capital in can be *refused* when the requirements it
cites are not met. A verdict that contradicts its own evidence is the exact
failure this contract exists to prevent, and until v5 nothing checked it.

The same idea one level down is `test`: a strategy asks the host how one
comparison came out rather than working it out itself. There is then one
computation, not two that can disagree, and the comparators stay where the
answers do.

The same idea again, one level further out: a strategy may cite how far a
measure has moved *since a purchase* (`since`), and the host does the
subtraction. It could have taken one reading from the other itself — what it
could not do is cite the answer, because a limit is a number stated outright
or the id of a setting, and "five points below what it was when you bought"
is neither. The baseline comes off what the purchase froze rather than a
recomputation of that day: a restatement must not be able to move the level
a re-underwrite is measured against. See BASELINE_ANCHORS for why there are
two of them and why averaging them is wrong, and CHANGE_FORMS for why "how
far" has two honest answers and why a strategy has to say which it means.

A strategy also declares what it needs *from the user*. Declared values are
numbers it has an opinion about and ships a default for; declared inputs are
facts about the account that no strategy could guess. Inputs build the setup
screen without any logic running, which is what lets a journal be validated
before a decision is ever made, and an input may carry a `role` — a name from
the host's own short list — saying what the figure is, so the host can report
position weight and free cash without ever having decided that a journal
must collect them.

Nothing in this module holds an opinion about investing. Whether 15 is a good
P/E is a strategy's business; that a decision must name its rule is the
host's. Deciding that 18.9 is at least 15 is arithmetic, not an opinion, which
is why the host does it.
"""

from __future__ import annotations

import traceback
from datetime import date
from types import MappingProxyType

# The version of this contract. A strategy declares the version it speaks;
# the host refuses any other.
#
# Bumped whenever a strategy written against the previous version would read
# what it receives *wrongly and silently*. That is the test, not whether the
# shape changed: a key that disappears raises, and a raise gets noticed, but a
# key that keeps its name and its type while answering a different question
# produces a plausible wrong verdict with nothing on screen saying so. A
# meaning change is the quietest break there is, so it is the one this
# mechanism most exists to refuse. Adding a key is still not a bump, because
# strategies must tolerate keys they don't read.
#
# 2: `position` gained real lot history and lost every cost figure. A v1
#    strategy was written when `lots` held exactly one synthesised buy and
#    could reasonably read `lots[0]` as the whole position; under real lots
#    that reading is wrong and wrong *quietly*, which is the case the
#    version exists to refuse. Cost basis left the context entirely — see
#    HOST_FACTS.
# 3: `position.opened` means the holding period's first purchase and no
#    longer moves when a lot is trimmed away. It used to be the date of the
#    oldest lot still open, so a v2 strategy holding a position since January
#    whose January lot was trimmed in June was told the position began in
#    March. Same key, same type, same label — a rule counting years held
#    would simply have been wrong, and would have looked right. Two questions
#    were sharing one name; lot ages remain on `position.lots`, each entry
#    carrying its own date.
# 4: a qualitative measure can now answer. It used to be permanently absent
#    — nothing in the program could record one — so a v3 strategy reading
#    `measures["moat_durability"]["current"]["status"]` got "absent" forever
#    and could reasonably branch on that to mean "nothing here to read".
#    Under v4 the same key returns a yes/no the user assessed, so that branch
#    silently takes the other road: same key, same shape, a different
#    question answered. That is the quietest break there is and the one this
#    number exists to refuse.
#
#    Bundled with it, because bumping once beats bumping twice: an evidence
#    item now carries `threshold` OR `threshold_from`, never both. Naming a
#    setting means the host reads the number out of it; stating a number
#    means the strategy may not attribute it. A v3 item supplying both is
#    refused, which is loud — but refusing it at *load*, by version, beats
#    refusing every verdict it produces at evaluation.
# 5: a decision that puts capital in may no longer be contradicted by its own
#    evidence. A v4 strategy could return a commit state beside a citation
#    the host resolved as failed, and both rendered — the strategy having
#    computed the comparison a second time, privately, and got a different
#    answer. Under v5 the host derives every comparison once (see `test`),
#    evidence is gathered into groups that say which rows are requirements,
#    and a commit whose requirements are unmet is refused. A v4 bundle would
#    keep working right up to the verdict it got wrong, so it is refused at
#    load instead.
#
#    Bundled with it, because bumping once beats bumping twice: a declared
#    value must now say where its number came from, the context is handed
#    over frozen rather than copied, `position.months_held` joins HOST_FACTS,
#    and the state cap moves to 16.
#
# Deliberately NOT bumped for what a position's baselines and a staged commit
# added. A strategy may now cite how a measure has moved since a purchase
# (`since`), and a commit may carry the tranches it is holding back (`plan`);
# `position` gained `baselines`, `last_purchase` and `purchases` to serve the
# first. Every one of those is additive and opt-in — a v5 bundle that reads
# none of them is handed exactly what it was handed before and reaches exactly
# the verdict it reached before. The test above is a *silent* misreading, and
# there is none here: nothing changed meaning, nothing changed shape, and a
# key nobody reads decides nothing. Bumping anyway would refuse fifteen
# correct bundles to no end, and a version number that moves for additions
# stops being evidence that a meaning moved.
#
# Deliberately NOT bumped, again, for `change` — the second strategy's one
# demand on the contract. A `since` citation may now say whether the move is
# counted in the measure's own units or as a share of what the reading was at
# that purchase (see CHANGE_FORMS), because a rule reading "the returns have
# fallen by a third" is a claim about proportion, and no tolerance in points
# says the same thing to a business earning 45% and one earning 15%.
#
# It passes the same test the additions above pass, and it is worth saying
# exactly how, because this one changes arithmetic rather than adding a key
# nobody reads. Left out, `change` is `distance` — bit for bit the subtraction
# every existing citation already got. A bundle written before this key
# existed cannot ask for the other form and cannot be handed it by accident,
# so the meaning that moved is reachable only from a citation that names it,
# and a strategy that names nothing is owed no version.
CONTRACT_VERSION = 5

# A strategy may declare at most this many states. The cap is deliberate:
# states are user-facing vocabulary, and complexity must not creep back in
# through the plugin door.
#
# Sixteen rather than twelve. The first real strategy needed eleven of the
# twelve on the most mechanical style there is — a purely quantitative screen
# with no view about any business — which is evidence rather than a guess:
# whatever the right cap is, it is not one state above what the simplest case
# already wanted.
MAX_STATES = 16

_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-"

_NO_REFERENCE = MappingProxyType({})


# ---------------------------------------------------------------------------
# The six render types — the one permanent host-owned list.
#
# Internal only; a user never sees these words. They exist so the host can
# render, sort, count and aggregate a state whose meaning it does not know.
# Four are about the security, two are about the evaluation, and the two
# tiers must never be averaged together — "4 of 12 are hold" is a portfolio
# fact, "4 of 12 cannot be evaluated" is a data problem.
#
# The mapping is a read-only proxy over dicts with tuple values: nothing
# outside this file can add a type or edit one, by construction rather than
# by convention. Adding a type is a host change and a deliberate one.
# ---------------------------------------------------------------------------

def _rt(tier, meaning, order, attention, payload_keys, optional_keys=()):
    return MappingProxyType({
        "tier": tier,                    # "position" | "evaluation"
        "meaning": meaning,              # for the contract docs, not the user
        "order": order,                  # sort rank across a list of results
        "attention": attention,          # surfaces in "needs attention"
        "payload_keys": payload_keys,    # every one of these, always
        # May also appear, and mean "no answer" by being left out. Reserved
        # for a fact that genuinely does not apply to most decisions of this
        # kind — a staged entry is the only one so far. A required key with a
        # nullable value is the better shape wherever the question is always
        # worth answering, because it makes the author answer it; an optional
        # key is right only where the absence is the ordinary case and
        # writing `None` fifty times teaches nobody anything.
        "optional_keys": optional_keys,
    })


RENDER_TYPES = MappingProxyType({
    "commit":  _rt("position", "capital may go in", 0, True,
                   ("size", "condition"), ("plan",)),
    "reduce":  _rt("position", "partial exit", 1, True, ("to",)),
    "close":   _rt("position", "full exit", 2, True, ("when",)),
    "hold":    _rt("position", "no action", 3, False, ()),
    "blocked": _rt("evaluation",
                   "a decision is owed from the user before any verdict",
                   4, True, ("needs",)),
    "unknown": _rt("evaluation", "not enough data to say", 5, True, ()),
})

# ---------------------------------------------------------------------------
# Where a blocked verdict sends someone — the host's list of ways out.
#
# `blocked` is the one render type that says the tool will not answer until
# the user does something. A blocked verdict that does not say *where* that
# something is done is a dead end: the user reads a sentence naming what is
# owed and has nothing to click, anywhere, and no way to find out what the
# author meant. It is the worst failure on this list, because it is the only
# one where the program has stopped and is not saying how to start it again.
#
# So a blocked state names its way out, from this closed host-owned list, and
# the host renders the button. That is the same arrangement as `render`: the
# strategy picks a word the host owns and the host owns everything behind it.
# A strategy cannot invent a destination, because a destination is a screen
# and screens are the host's — anything missing from this list is a request
# against the host, not something to work around.
#
# `cites` is the part that keeps a fix honest. Most destinations are fixed
# screens and are reachable whatever the decision said. One is not: the
# questions under "Your judgement" are built from the decision's own
# citations, so a verdict that says "answer these" and cites none of them
# sends the reader to an empty section — a dead end one screen further along,
# which is worse than the first one because it looks like it worked. Where
# `cites` names a subject kind, `evaluate` refuses a blocked verdict that
# does not cite one. The author finds out the first time they run it; the
# user never finds out at all.
#
# Adding a fix is a host change in this one table, and it means adding the
# screen behind it.
# ---------------------------------------------------------------------------

STATE_FIXES = MappingProxyType({
    "settings": MappingProxyType({
        "label": "Fix this journal's settings",
        "where": "this journal's setup screen",
        "cites": None,
        "explain": "The answers and settings this journal holds for its "
                   "strategy. Where a strategy asks for something the "
                   "journal has never been given, this is the one screen "
                   "that supplies it."}),
    "judgement": MappingProxyType({
        "label": "Answer these questions",
        "where": '"Your judgement" on this security\'s page',
        "cites": "judgement",
        "explain": "The questions no filing can answer, asked per security. "
                   "They are built from what the decision cited, which is "
                   "why a verdict that blocks on one has to cite it: the "
                   "citation is what puts the question on the page with a "
                   "way to answer it."}),
    "thesis": MappingProxyType({
        "label": "Write down what you think now",
        "where": "this security's thesis record",
        "cites": None,
        "explain": "What you believe about this business and what would "
                   "prove you wrong, in your own words. Where a strategy "
                   "will not act again until a fresh view has been taken, "
                   "this is where taking it is recorded."}),
})

# States the host itself may produce when no strategy verdict exists. They
# are machinery, not opinion — "we could not ask the strategy" is a fact
# about the evaluation, and the host is allowed to know it. The "host:"
# prefix is reserved; a strategy declaring a state with it is refused.
#
# `fix` names one of STATE_FIXES, or None where nothing in the app resolves
# the state. The view reads this rather than recognising state ids, so a new
# host state arrives with its own way out.
#
# One of these is blocked with no fix, and it is not the dead end a
# strategy's would be. "The strategy is not installed" is resolved by putting
# a directory back on disk, which is not a screen and never will be — naming
# one would be the host offering a button that cannot exist. The rule that
# every blocked state names a fix is therefore asked of what a *strategy*
# declares, where the alternative is an author's oversight rather than an
# honest absence, and the screen says the whole sentence instead.
HOST_STATES = MappingProxyType({
    "host:inputs-missing": MappingProxyType({
        "render": "blocked", "name": "Waiting on setup", "fix": "settings",
        "description": "The strategy needs information from you before it "
                       "can produce a verdict."}),
    "host:strategy-missing": MappingProxyType({
        "render": "blocked", "name": "Strategy not installed", "fix": None,
        "description": "The strategy this journal is stamped with is not on "
                       "this machine. History remains readable; new verdicts "
                       "need the strategy present."}),
    "host:values-unresolved": MappingProxyType({
        "render": "blocked", "name": "Settings need fixing", "fix": "settings",
        "description": "The strategy's declared values could not be "
                       "resolved, so no verdict can honestly be produced."}),
    "host:strategy-error": MappingProxyType({
        "render": "unknown", "name": "Strategy failed", "fix": None,
        "description": "The strategy's own logic failed while deciding. "
                       "This is a problem with the strategy, not with your "
                       "data or your decision."}),
    "host:data-unreadable": MappingProxyType({
        "render": "unknown", "name": "Data could not be read", "fix": None,
        "description": "The stored filings or prices could not be read, so "
                       "the strategy could not be given anything to decide "
                       "on. Nothing you recorded is affected, and recording "
                       "a decision is never blocked by this."}),
    "host:invalid-decision": MappingProxyType({
        "render": "unknown", "name": "Strategy failed", "fix": None,
        "description": "The strategy returned something outside the "
                       "contract, so its verdict cannot be trusted or "
                       "shown."}),
})

VALUE_TYPES = ("number", "integer", "boolean", "text")
SIZE_UNITS = ("weight", "usd", "shares")   # weight is a percent number

# The one test that decides whether something is a value or an input. It is
# quoted verbatim wherever the question can come up, because an author who
# gets this wrong writes a strategy that either cannot ship or asks the user
# for something it should have an opinion about.
SPLIT_TEST = (
    "The test is whether the strategy can ship a sensible default. A "
    "strategy has an opinion about a 5% position cap, so that is a value. No "
    "strategy can have an opinion about someone's account balance, so that "
    "is an input.")


# ---------------------------------------------------------------------------
# Evidence — how a decision says what it looked at.
#
# A verdict without the figures that produced it teaches nothing, and a
# free-text reason teaches only the security in front of you: it cannot be
# compared across holdings or counted across time. So a strategy cites what
# it examined and what it required, and the *host* resolves the citation into
# the rendered fact. That division is deliberate:
#
#   - the strategy owns the question — which measure, which direction, and
#     either a limit it states outright or the name of one of its own
#     settings. Those are opinions and belong to it.
#   - the host owns the answer — the value, its label, its unit, whether it
#     was absent and why, the limit read out of any setting that was named,
#     and whether the comparison passed. Those are facts, and a strategy
#     restating them could restate them wrongly.
#
# The consequence worth naming: a strategy cannot misquote the host's own
# numbers, because it never quotes them at all. It cannot claim a pass on an
# absent value either — absence resolves to `unknown`, never to success. And
# it cannot attribute a limit to a setting that does not hold it, because
# naming the setting and supplying the number is refused: one or the other.
# ---------------------------------------------------------------------------

# How a value is rendered. Must remain a superset of the metric bank's own
# units (tests/test_contract.py pins that), plus the renderings the bank has
# no need for. A strategy picks from this list; it never invents one.
EVIDENCE_UNITS = (
    "percent", "percentage_points", "times", "ratio", "score", "usd",
    "shares", "years", "months", "days", "count", "times_own_median",
    "date", "text", "yes_no", "none",
)

# How a comparison came out. The host derives one of these and a strategy
# never asserts one — but it does branch on them, so the words are here to
# be imported rather than spelled out again inside a bundle.
PASS, FAIL, UNKNOWN, NOTED = "pass", "fail", "unknown", "noted"
OUTCOMES = (PASS, FAIL, UNKNOWN, NOTED)


# ---------------------------------------------------------------------------
# Baselines — the two moments a measure can be compared against.
#
# A rule about a company you already own asks a question a rule about a
# candidate cannot: has this changed since I last looked at it? There are two
# honest answers to "since when", they are different questions, and picking
# one and eating the other's cost is what this list refuses.
#
#   last-purchase   the last time you looked at this business and said yes.
#                   A rule about the business deteriorating belongs here: a
#                   position you consciously re-underwrote last quarter must
#                   not fire an exit on a decline you already looked at and
#                   accepted.
#   first-purchase  the day the holding began. A rule about cumulative drift
#                   belongs here, and it is the only place the boiling frog
#                   is visible — six quarters of small declines, each one
#                   fine against the quarter before it, and nothing anywhere
#                   comparing the sixth against the first.
#
# A weighted average of the two, or of every purchase in between, is wrong
# for both. There is no coherent dollar-weighted average of a gross margin:
# averaging the readings at three purchases produces a number that was true
# on no day, answers neither question, and cannot be checked against any
# filing.
#
# Both are scoped to the holding you have now. Selling out entirely and
# buying back later starts both again, for the same reason `position.opened`
# does — that is a new decision about a name you happen to have owned before,
# and inheriting a baseline from the last time would measure this holding
# against a business case nobody re-made.
#
# What a baseline holds is what the record froze at that purchase, never a
# recomputation of it. That is principle 3 doing load-bearing work rather
# than decoration: a company that restates two years of accounts would
# otherwise silently move the level you are being measured against, and the
# question is what you were told when you said yes, not what the filings say
# today about the day you said it.
#
# Adding an anchor is a host change in this one table.
# ---------------------------------------------------------------------------

BASELINE_ANCHORS = MappingProxyType({
    "last-purchase": MappingProxyType({
        "label": "since you last bought",
        "means": "the last purchase into the holding you have now",
        "explain":
            "How far this has moved since the day you last put money into "
            "this holding — the last time you looked at the business and "
            "said yes. The figure is the one that was on record then, frozen "
            "at that purchase and never worked out again, so a company "
            "restating its accounts cannot quietly move what you are being "
            "measured against.",
    }),
    "first-purchase": MappingProxyType({
        "label": "since you first bought",
        "means": "the purchase that took this holding up from nothing",
        "explain":
            "How far this has moved since the day this holding began. It is "
            "the question the quarter-by-quarter view cannot answer: six "
            "small declines can each look acceptable against the one before "
            "it while the total is nothing you would have bought. The figure "
            "is the one that was on record at that first purchase, frozen "
            "then and never worked out again.",
    }),
})


# ---------------------------------------------------------------------------
# How far is "how far" — the two ways a move from a baseline is measured.
#
# `since` used to answer one question: subtract the reading then from the
# reading now. That is the right answer for a measure whose levels mean
# something on their own — a current ratio going from 2.6 to 2.1 has lost half
# a turn, and half a turn is half a turn wherever it started.
#
# It is the wrong answer for a measure whose levels do not. A rule saying "the
# returns this business earns have fallen by a third" is a claim about
# proportion, and a third of 22% is seven and a half points while a third of
# 45% is fifteen. One tolerance in points either fires on a decline the
# high-return business shrugs off, or never fires on the low-return one. The
# same rule stated as a share of what it was is one number that means the same
# thing to both.
#
# A strategy could not express that at all before this table existed, and the
# hole was exactly where it is least visible. It cannot cite the proportion,
# because a limit is a number stated outright or the id of a setting, and "a
# third below what it was when you bought" is neither. It could work the
# number out privately and state the answer — but the answer is built from a
# figure the host owns, so a strategy stating it is a strategy quoting the
# host, which is the one thing the evidence split exists to prevent. So the
# strategy owns the question, the form of the comparison included, and the
# host owns every number in the row.
#
# Adding a form is a host change in this one table.
# ---------------------------------------------------------------------------

CHANGE_FORMS = MappingProxyType({
    "distance": MappingProxyType({
        "suffix": "",
        "explain":
            "How far this has moved, counted in the units the figure itself "
            "is in. A ratio that went from 2.6 to 2.1 has moved by 0.5.",
    }),
    "proportion": MappingProxyType({
        "suffix": ", as a share of what it was then",
        "explain":
            "How far this has moved, as a percentage of what it was at that "
            "purchase rather than as a number of units. A return on capital "
            "that went from 21% to 14% has fallen by a third — and reads as "
            "-33%, not as -7.\n\n"
            "It is the honest way to compare a move on a measure whose level "
            "means nothing on its own. Seven points off a business earning "
            "45% is an ordinary year; seven points off one earning 15% is "
            "most of the reason you owned it. A limit in points cannot say "
            "both, and a limit stated this way says the same thing to "
            "either.\n\n"
            "Measured against the size of the reading at that purchase and "
            "not its sign, so a figure that was negative and got more "
            "negative reads as a fall rather than as a rise. Where the "
            "reading at that purchase was nought there is no share of it to "
            "take, and this is absent rather than being reported as an "
            "infinite move.",
    }),
})


def _cmp(phrase, fn, numeric_only):
    return MappingProxyType({"phrase": phrase, "fn": fn,
                             "numeric_only": numeric_only})


# The comparison vocabulary. `phrase` is how the host says it in a sentence;
# a strategy supplies only the name.
COMPARATORS = MappingProxyType({
    "at_least":   _cmp("at least", lambda a, b: a >= b, True),
    "at_most":    _cmp("at most", lambda a, b: a <= b, True),
    "above":      _cmp("above", lambda a, b: a > b, True),
    "below":      _cmp("below", lambda a, b: a < b, True),
    "equals":     _cmp("equal to", lambda a, b: a == b, False),
    "not_equals": _cmp("not equal to", lambda a, b: a != b, False),
})


def _fact(label, unit, path, explain, bare=False, when_missing=None):
    return MappingProxyType({"label": label, "unit": unit, "path": path,
                             "explain": explain, "bare": bare,
                             "when_missing": when_missing})


# Host-provided facts a strategy may cite by name. These are the figures the
# host reports and does not interpret — shares, price, market value, market
# value as a fraction of the account. Citing one is always more honest than
# restating it: where the host cannot answer, the host's own reason is what
# the user reads.
#
# What is deliberately NOT here: anything about what a position cost. Cost
# basis is reporting — it belongs on screen, in the record and in the
# scorecards — and it is kept out of the context entirely rather than merely
# discouraged, because "structurally incapable of reaching a verdict" is the
# only version of that promise worth making. A rule that fires on the
# distance from your own purchase price is anchoring: it makes the same
# company a buy for one person and a sell for another on the same day, and
# averaging down is that bias in its purest form. Market value and weight
# survive because they are price × shares, which is a fact about today.
#
# `position.months_held` is here for a duller reason: it is arithmetic over
# two dates the host already owns, and every strategy with a clock in it
# would otherwise write that arithmetic again. Month arithmetic looks trivial
# and is not — 29 February plus twenty-four months is 28 February, and a
# count that disagrees with that clamp reports a position as 23 months held
# on the day it falls due. See `months_after`, which both directions derive
# from so they cannot drift.
#
# Every one of them carries its own plain-language explanation, because a
# figure on a screen that the reader cannot find out the meaning of is an
# incomplete figure. These sit beside the bank's explanations for measures
# and the author's for a declared setting, so a row of evidence can always
# be asked what it is regardless of which kind of thing it cites.
HOST_FACTS = MappingProxyType({
    "position.weight": _fact(
        "Position weight", "percent", ("position", "weight"),
        "How much of your whole account this one holding is, as a "
        "percentage. It is what the shares are worth today divided by what "
        "the account is worth today — free cash plus every holding at "
        "market. It moves when the price moves, without you doing anything, "
        "which is the reason a rule about it exists at all."),
    "position.months_held": _fact(
        "Months held", "months", ("position", "months_held"),
        "How many whole months you have held this position, counted from "
        "the purchase that took it up from nothing. Selling part of it does "
        "not restart the clock; selling all of it and buying back later "
        "does, because that is a new decision. Counted the same way a date "
        "some number of months out is worked out, so \"twenty-four months "
        "held\" and \"the day two years after you bought\" always land "
        "together.", bare=True,
        when_missing="no position is held, so there is nothing to count"),
    "position.market_value": _fact(
        "Position market value", "usd", ("position", "market_value"),
        "What this holding is worth today: the shares you hold multiplied "
        "by the latest price of the security you hold. Not what you paid — "
        "nothing about what a position cost is available to a rule."),
    "position.shares": _fact(
        "Shares held", "shares", ("position", "shares"),
        "How many shares of this security you hold now — every purchase the "
        "journal has recorded, less everything you have sold. It is derived "
        "from that list each time it is read rather than kept as a running "
        "total, so it cannot drift away from the record it comes from.",
        bare=True),
    "position.opened": _fact(
        "Held since", "date", ("position", "opened"),
        "The day this holding began — the purchase that took the position "
        "up from nothing. It does not move when you trim part of the "
        "holding away, so it answers when you started owning this, not how "
        "old your oldest remaining share is.", bare=True,
        when_missing="no position is held"),
    "position.last_purchase": _fact(
        "Last bought", "date", ("position", "last_purchase"),
        "The day you last put money into this holding. On a position you "
        "have bought once it is the same day you started; after that the "
        "two part company, and which of them a rule should measure from "
        "depends entirely on what the rule is asking.\n\n"
        "The day you last bought is the day you last looked at this "
        "business and said yes. A question about whether something has gone "
        "wrong since then measures from here. A question about how far it "
        "has drifted in total measures from the day you started — see "
        "\"Held since\".", bare=True,
        when_missing="no position is held, so nothing has been bought"),
    "position.purchases": _fact(
        "Purchases in this holding", "count", ("position", "purchases"),
        "How many separate times you have bought this security during the "
        "holding you have now. It counts from the purchase that took the "
        "position up from nothing, so selling out and buying back starts it "
        "again — that is a new holding and a new decision.", bare=True,
        when_missing="no position is held"),
    "portfolio.cash": _fact(
        "Free cash", "usd", ("portfolio", "cash"),
        "Money in the account this journal covers that is not in any "
        "position. The journal cannot observe it, so it is only known where "
        "the strategy asked you for it in settings."),
    "portfolio.account_value": _fact(
        "Account value", "usd", ("portfolio", "account_value"),
        "What the whole account is worth: your free cash plus every holding "
        "at today's price. Worked out rather than typed in, so when a "
        "position's share of the account looks wrong you can see which "
        "input was wrong. One holding with no price makes the whole total "
        "unknown rather than quietly smaller."),
    "portfolio.slots_occupied": _fact(
        "Positions held", "count", ("portfolio", "slots", "occupied"),
        "How many separate securities this journal currently holds. A "
        "strategy that runs a fixed number of positions at once measures "
        "against this to know whether there is room for another.",
        bare=True),
    "price.latest": _fact(
        "Latest price", "usd", ("price", "latest"),
        "The most recent closing price on record for the security this "
        "journal holds — that share class and no other, because two classes "
        "of one company trade at different prices. The day it closed and "
        "the symbol it belongs to travel with it."),
    "price.days_since_close": _fact(
        "Days since the price's close", "days",
        ("price", "age"),
        "How many days ago the market last set a price for this security. "
        "Zero means today's close; a large number means the last trade on "
        "record is old, and every figure built on the price — what the "
        "holding is worth, what share of the account it is — describes that "
        "day rather than this one.\n\n"
        "The host reports the number and holds no view about it. Whether "
        "four days is fine and forty is not depends entirely on what the "
        "rule is for: a screen built on three-year average earnings barely "
        "notices a week-old close, and a rule about position size notices a "
        "month. A strategy that cares declares its own limit and compares "
        "against this.\n\n"
        "Absent for a price you entered by hand, because nothing here knows "
        "when you typed it. That is not nought days — nought would claim it "
        "was today's. Absent for a different reason where there is no price "
        "at all, and the two say which they are."),
})


# ---------------------------------------------------------------------------
# Input roles — how a declared input becomes a fact the host can report.
#
# The host has no journal-level fields of its own. It does not ask anyone for
# an account value, a cash balance, a slot count or a position cap, because
# deciding which of those a journal collects would be the host deciding how
# strategies work: a rank-based strategy wants slots, a scale-down strategy
# wants a cash reserve, and a strategy that sizes nothing wants neither.
#
# But some figures the host reports cannot be computed without one of those
# answers. Position weight is market value over the account, and the account
# is not something the host can observe. So an input may carry a `role`: a
# name from this closed, host-owned list saying what the number *is*. The
# host then reports the facts that role unlocks, and nothing else changes —
# a strategy that declares no role simply gets those facts absent, with the
# reason saying which question was never asked.
#
# Free cash is the only role, and deliberately so. Account value is NOT a
# role: it is free cash plus the market value of every holding, which the
# host can derive, and a field that accepts a figure the tool could reach
# itself teaches nothing when it turns out wrong. Position cap, slot count
# and target weight are not roles either — a strategy can ship a default for
# each, which makes them declared values, not questions for the user.
#
# Adding a role is a host change in this one table. `type` and `unit` are
# enforced against the declaration, because a role that arrived as a percent
# would be reported as dollars.
# ---------------------------------------------------------------------------

INPUT_ROLES = MappingProxyType({
    "cash": MappingProxyType({
        "means": "free cash in the account this journal covers — money that "
                 "is not in any position",
        "type": "number",
        "unit": "usd",
        "reports": ("portfolio.cash", "portfolio.account_value",
                    "position.weight"),
    }),
})

# Exactly one of these names the subject of an evidence item.
_SUBJECT_KEYS = ("measure", "fact", "input", "value", "label")
_ITEM_KEYS = {"measure", "fact", "input", "value", "label", "unit", "actual",
              "absent", "at", "since", "change", "comparator", "threshold",
              "threshold_from", "group"}

# What a group may demand of its members. Three words, host-owned, and a
# strategy picks one — it never writes a rule of its own here, because the
# host has to be able to count the answer for itself.
#
#   all       every member carrying a test has to pass. The default, and the
#             strict direction: an author who says nothing gets the rule
#             that refuses a contradiction rather than the one that allows
#             it.
#   at_least  that many of them, named the way any other limit is — a figure
#             stated outright or the id of one of the strategy's own
#             settings, never both.
#   noted     nothing is demanded. Reported so the reader can see them, or
#             acted on by a rule the host cannot express — a run of
#             consecutive filings, say. The host counts and does not judge.
#
# There is deliberately no fourth word separating "these never matter" from
# "these matter by a rule of my own". The host would have to render a
# sentence it cannot justify either way, and the group's own name and the
# state's description say which is meant.
GROUP_REQUIREMENTS = ("all", "at_least", "noted")
_GROUP_KEYS = {"id", "name", "requires", "threshold", "threshold_from"}


# ---------------------------------------------------------------------------
# small checks
# ---------------------------------------------------------------------------

def _is_id(s) -> bool:
    return (isinstance(s, str) and s != "" and s[0].isalpha()
            and all(c in _ID_CHARS for c in s))


def _is_text(s) -> bool:
    return isinstance(s, str) and s.strip() != ""


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_date(s) -> bool:
    if not isinstance(s, str):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def _kind_of(v) -> str:
    """What kind of thing a figure is, for comparison. Dates are text that
    sorts chronologically in ISO form, so they compare as dates, not text."""
    if isinstance(v, bool):
        return "yes/no"
    if _is_num(v):
        return "number"
    if _is_date(v):
        return "date"
    return "text"


def _is_scalar(v) -> bool:
    return isinstance(v, (bool, int, float, str))


def _as_date(value):
    """A YYYY-MM-DD string or a date, as a date. None where it is neither."""
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Month arithmetic — host-owned, and offered to strategies.
#
# A strategy with a clock in it needs two things: how long a position has
# been held, and the day some number of months from when it opened. Both are
# arithmetic over dates the host already has, and both have the same trap in
# them. Adding months has to clamp — 31 January plus one month is 28
# February, not 3 March — and counting months has to clamp the same way, or
# a position opened on 29 February reads as 23 months held on the day its
# 24-month clock falls due, and closes while its own evidence says the period
# has not run.
#
# So they are one function and its inverse rather than two implementations
# that happen to agree today. Strings in, strings out: nothing framework-
# shaped crosses to a strategy, and the contract's own dates are ISO text.
# ---------------------------------------------------------------------------

def months_after(day, months) -> str | None:
    """The same day of the month, that many months later, as YYYY-MM-DD.

    Clamped where the later month is shorter. None where `day` is not a date
    or `months` is not a whole number — an unanswerable question has no
    answer, and inventing one is what principle 4 refuses.
    """
    start = _as_date(day)
    if start is None or not isinstance(months, int) or isinstance(months,
                                                                 bool):
        return None
    total = start.month - 1 + months
    year, month = start.year + total // 12, total % 12 + 1
    following = (date(year + 1, 1, 1) if month == 12
                 else date(year, month + 1, 1))
    last_day = date.fromordinal(following.toordinal() - 1).day
    return date(year, month, min(start.day, last_day)).isoformat()


def months_between(start, end) -> int | None:
    """Whole months from `start` to `end`, counted by the rule `months_after`
    adds by. None where either is not a date.

    Derived from `months_after` rather than written beside it: `months >= n`
    is then exactly `end >= months_after(start, n)`, for every start date and
    every n, including the clamped ones.
    """
    a, b = _as_date(start), _as_date(end)
    if a is None or b is None:
        return None
    months = (b.year - a.year) * 12 + (b.month - a.month)
    if _as_date(months_after(a, months)) > b:
        months -= 1
    return months


def _same(a, b) -> bool:
    """Equality that does not let true equal 1. Python's does, and a `when`
    gate comparing a yes/no answer against a number would then fire on the
    wrong thing."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _options_of(spec: dict) -> list:
    opts = spec.get("options")
    return opts if isinstance(opts, list) else []


def option_label(spec: dict, value) -> str:
    """How one choice reads in a sentence. Falls back to the value itself,
    so a message is never worse than the raw answer."""
    for o in _options_of(spec):
        if isinstance(o, dict) and _same(o.get("value"), value):
            return str(o.get("label") or o.get("value"))
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def gate_answers(is_) -> list | None:
    """The answers a `when` gate accepts, always as a list — a single answer
    is a list of one.

    One shape downstream is the point: a membership test written once cannot
    drift from a membership test written again somewhere else, and the gate
    is evaluated in three places. None means the gate is malformed; an empty
    list is a gate nothing could ever satisfy, which would leave a required
    field permanently un-owed with nothing on screen saying why.
    """
    if isinstance(is_, list):
        return is_ or None
    return [is_]


def answer_phrase(spec: dict, wants) -> str:
    """How a gate's accepted answers read in a sentence — "growth",
    "growth or blend", "growth, blend or value"."""
    labels = [option_label(spec, w) for w in wants]
    if len(labels) <= 1:
        return labels[0] if labels else "nothing"
    return ", ".join(labels[:-1]) + " or " + labels[-1]


def check_typed_value(spec: dict, value) -> str | None:
    """Does `value` fit a declared input or value? None, or one legible
    sentence saying what was expected and what arrived."""
    label = f'"{spec["id"]}"'
    t = spec["type"]
    if t == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
        expected = "a whole number"
    elif t == "number":
        ok = _is_num(value)
        expected = "a number"
    elif t == "boolean":
        ok = isinstance(value, bool)
        expected = "yes or no (true/false)"
    else:  # text
        ok = isinstance(value, str)
        expected = "text"
    if not ok:
        got = "nothing" if value is None else f"{value!r}"
        return f"{label} expects {expected}, not {got}."
    options = _options_of(spec)
    if options:
        if not any(isinstance(o, dict) and _same(o.get("value"), value)
                   for o in options):
            offered = ", ".join(str(o.get("label") or o.get("value"))
                                for o in options if isinstance(o, dict))
            return (f"{label} must be one of: {offered}. {value!r} is not "
                    "one of them.")
        return None
    if t in ("integer", "number"):
        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None and value < lo:
            return f"{label} must be at least {lo}; {value} is below that."
        if hi is not None and value > hi:
            return f"{label} must be at most {hi}; {value} is above that."
    return None


# ---------------------------------------------------------------------------
# the declaration
# ---------------------------------------------------------------------------

_DECL_KEYS = {"id", "name", "summary", "version", "contract", "changelog",
              "states", "inputs", "values", "reference"}
_STATE_KEYS = {"id", "name", "description", "render", "fix"}
_FIELD_KEYS = {"id", "label", "type", "unit", "required", "min", "max",
               "explain", "options", "role", "when", "min_from", "max_from",
               "source"}
# Keys only an input may carry. A value ships a default and is always in
# force, so none of them can mean anything on one: a role is a fact about
# the user, and a value that only sometimes applies is a value the strategy
# can simply ignore.
_INPUT_ONLY_KEYS = ("required", "role", "when", "min_from", "max_from")
# And the reverse. An input has no number of its own — the user supplies it
# — so there is nothing about it to attribute.
_VALUE_ONLY_KEYS = ("source",)
_WHEN_KEYS = {"input", "is"}
_SOURCE_KEYS = {"name", "reasoning"}
_NUMERIC_TYPES = ("integer", "number")


def _check_options(where: str, f: dict, errors: list) -> None:
    """A fixed set of answers. It earns its place because the alternative is
    free text validated inside decide(), which fails at evaluation instead
    of at setup — and the whole point of validating a declaration without
    running its logic is that a setup screen can refuse a bad answer while
    the user is looking at the field."""
    options = f["options"]
    if not isinstance(options, list) or not options:
        errors.append(f"{where}: `options` must be a non-empty list of "
                      "{value, label} choices.")
        return
    if f.get("type") not in ("text", "integer", "number"):
        errors.append(f"{where}: `options` only mean something for text and "
                      "numbers — a yes/no answer is already a boolean.")
        return
    if "min" in f or "max" in f:
        errors.append(f"{where}: `options` already say exactly what is "
                      "allowed, so min/max cannot also apply.")
    if "role" in f:
        errors.append(f"{where}: a role names a figure the host reports, "
                      "which cannot come from a fixed list of choices.")
    seen = []
    for o in options:
        if not isinstance(o, dict) or set(o) != {"value", "label"}:
            errors.append(f"{where}: each option must be exactly "
                          "{value, label}.")
            continue
        if not _is_text(o.get("label")):
            errors.append(f"{where}: each option needs a user-facing "
                          "`label`.")
        issue = check_typed_value({"id": f.get("id"), "type": f["type"]},
                                  o.get("value"))
        if issue:
            errors.append(f"{where}: an option's value {issue.split(' ', 1)[1]}")
        elif any(_same(v, o["value"]) for v in seen):
            errors.append(f"{where}: two options offer {o['value']!r}.")
        else:
            seen.append(o["value"])


def _check_source(where: str, f: dict, errors: list) -> None:
    """Where a declared value's number came from.

    Every threshold in a strategy came from somewhere — a book, a report, a
    piece of research, or the author. Before this was a field the only place
    to say so was `explain`, which meant the claim was prose: it could be
    made once at the top of a file and quietly cover six values it did not
    fit, and nothing said which. That is the same integrity gap
    `threshold_from` closed one level down — an attribution nothing checks.

    Nothing here can verify that a number really is the report's; no host
    could read the report. What it can do is refuse the three ways the claim
    goes wrong on its own: being absent, being blanket, and being silent
    about how far it reaches. So the field is required, it sits on the value
    it describes, and `reasoning` says whether the account in `explain` is
    also that source's or the author's own — which is the distinction an
    auditor is actually trying to make, and the one prose blurs first.

    `name` is free text and has to be: the second strategy's source is a
    different document. A closed list would be wrong by the second bundle.
    """
    source = f["source"]
    if not isinstance(source, dict) or set(source) != _SOURCE_KEYS:
        errors.append(
            f"{where}: `source` must be exactly "
            "{name: where this number came from, reasoning: true if the "
            "explanation is that source's too, false if the source states "
            "the level and the reasoning below is this strategy's own}.")
        return
    if not _is_text(source.get("name")):
        errors.append(f"{where}: `source.name` must name where this number "
                      "came from, in words a reader could go and check — a "
                      "book and a chapter, a report, a piece of research, or "
                      "the strategy's own author.")
    if not isinstance(source.get("reasoning"), bool):
        errors.append(
            f"{where}: `source.reasoning` must be true or false. True says "
            f'the explanation above is {source.get("name") or "the source"}'
            "'s own reasoning; false says the source gives the level and "
            "nothing else, and the account in `explain` is this strategy's. "
            "A level with borrowed authority and homemade reasoning is the "
            "case worth being able to tell apart.")


def _check_fields(kind: str, fields, errors: list) -> None:
    """Shared validation for declared inputs and declared values. `kind` is
    "input" or "value" — values never carry `required`, because every value
    ships a default; a value the user must supply is an input.

    Everything here is checked field by field. Anything naming another field
    — `when`, `min_from`, `max_from`, and one role per strategy — is settled
    in _check_field_graph once every id is known.
    """
    if not isinstance(fields, list):
        errors.append(f"`{kind}s` must be a list.")
        return
    seen = set()
    for i, f in enumerate(fields):
        where = f'{kind} {i + 1}'
        if not isinstance(f, dict):
            errors.append(f"{where} must be a mapping, not {type(f).__name__}.")
            continue
        if _is_id(f.get("id")):
            where = f'{kind} "{f["id"]}"'
            if f["id"] in seen:
                errors.append(f"{where} is declared twice.")
            seen.add(f["id"])
        else:
            errors.append(f'{where} needs an `id` in lowercase letters, '
                          "digits and hyphens.")
        unknown = set(f) - _FIELD_KEYS
        if unknown:
            errors.append(f"{where} has keys this contract does not know: "
                          f"{', '.join(sorted(map(str, unknown)))}.")
        if kind == "value":
            if "required" in f:
                errors.append(f"{where} declares `required`, which no value "
                              "can be: every value ships a default. "
                              + SPLIT_TEST)
            for key in _INPUT_ONLY_KEYS[1:]:
                if key in f:
                    errors.append(
                        f"{where} declares `{key}`, which only an input can. "
                        "A value ships a default and is always in force. "
                        + SPLIT_TEST)
            if "source" not in f:
                errors.append(
                    f"{where} needs a `source` saying where its number came "
                    "from and whether the reasoning in `explain` is that "
                    "source's or this strategy's own. A threshold with no "
                    "stated provenance is an attribution nobody can check, "
                    "and the file-level version of the claim always ends up "
                    "covering values it does not fit.")
            else:
                _check_source(where, f, errors)
        else:
            for key in _VALUE_ONLY_KEYS:
                if key in f:
                    errors.append(
                        f"{where} declares `{key}`, which only a value can. "
                        "The user supplies an input, so there is no number "
                        "of the strategy's to attribute. " + SPLIT_TEST)
        if not _is_text(f.get("label")):
            errors.append(f"{where} needs a user-facing `label`.")
        if f.get("type") not in VALUE_TYPES:
            errors.append(f"{where} needs a `type` from: "
                          f"{', '.join(VALUE_TYPES)}.")
        if not _is_text(f.get("explain")):
            errors.append(f"{where} needs an `explain` — plain language for "
                          "someone who has never valued a company. A field "
                          "without an explanation is incomplete, not a "
                          "follow-up ticket.")
        for bound in ("min", "max"):
            if bound in f and not _is_num(f[bound]):
                errors.append(f"{where}: `{bound}` must be a number.")
        if ("min" in f or "max" in f) and f.get("type") in ("boolean", "text"):
            errors.append(f"{where}: min/max only mean something for "
                          "numbers.")
        if "options" in f:
            _check_options(where, f, errors)
        if "role" in f and kind == "input":
            _check_role(where, f, errors)
        if "when" in f and kind == "input" and \
                not (isinstance(f["when"], dict)
                     and set(f["when"]) == _WHEN_KEYS):
            errors.append(f"{where}: `when` must be exactly "
                          "{input: another input's id, is: the answer that "
                          "makes this one apply — or a list of answers, any "
                          "one of which does}.")
        for bound in ("min_from", "max_from"):
            if bound in f and kind == "input":
                if not isinstance(f[bound], str):
                    errors.append(f"{where}: `{bound}` must name another "
                                  "declared input or value by id.")
                elif f.get("type") not in _NUMERIC_TYPES:
                    errors.append(f"{where}: `{bound}` compares numbers, so "
                                  "it only means something for a number "
                                  "field.")


def _check_role(where: str, f: dict, errors: list) -> None:
    role = f["role"]
    spec = INPUT_ROLES.get(role) if isinstance(role, str) else None
    if spec is None:
        errors.append(
            f"{where}: `role` must be one of {', '.join(INPUT_ROLES)} — the "
            "figures the host reports and cannot observe for itself. A "
            "strategy never invents one; anything missing is a request "
            "against the host.")
        return
    if f.get("type") != spec["type"]:
        errors.append(f'{where}: the "{role}" role is {spec["means"]}, so it '
                      f'must be declared as `type: {spec["type"]}`.')
    if f.get("unit") != spec["unit"]:
        errors.append(f'{where}: the "{role}" role must be declared as '
                      f'`unit: {spec["unit"]}` — the host reports it in that '
                      "unit and would otherwise report one number as "
                      "another.")


def _check_field_graph(decl: dict, errors: list) -> None:
    """Everything that needs the whole declaration at once: fields naming
    other fields, and roles that may only be claimed once."""
    inputs = [f for f in decl.get("inputs", []) if isinstance(f, dict)
              and _is_id(f.get("id"))]
    values = [f for f in decl.get("values", []) if isinstance(f, dict)
              and _is_id(f.get("id"))]
    by_input = {f["id"]: f for f in inputs}
    numeric = {f["id"]: f for f in inputs + values
               if f.get("type") in _NUMERIC_TYPES}

    claimed: dict[str, str] = {}
    for f in inputs:
        role = f.get("role")
        if not isinstance(role, str) or role not in INPUT_ROLES:
            continue
        if role in claimed:
            errors.append(
                f'inputs "{claimed[role]}" and "{f["id"]}" both claim the '
                f'"{role}" role. The host would have no way to know which '
                "figure to report, so both are refused.")
        claimed[role] = f["id"]

    for f in inputs:
        where = f'input "{f["id"]}"'
        for bound, word in (("min_from", "at least"), ("max_from", "at most")):
            other = f.get(bound)
            if not isinstance(other, str):
                continue
            if other == f["id"]:
                errors.append(f"{where}: `{bound}` names itself.")
            elif other not in numeric:
                errors.append(
                    f'{where}: `{bound}` names "{other}", which this '
                    "strategy does not declare as a number — a bound has to "
                    f"be {word} something countable.")

        when = f.get("when")
        if not (isinstance(when, dict) and set(when) == _WHEN_KEYS):
            continue
        other = when.get("input")
        if other == f["id"]:
            errors.append(f"{where}: `when` names itself.")
            continue
        gate = by_input.get(other) if isinstance(other, str) else None
        if gate is None:
            errors.append(
                f'{where}: `when` names "{other}", which this strategy does '
                "not declare as an input. A field can only depend on another "
                "answer from the same setup screen.")
            continue
        # One answer, or several any one of which applies. Every one of them
        # is checked against the gate's own declaration, so a list cannot
        # smuggle in an answer the gate could never give — a gate that can
        # never be met hides its field forever, with nothing on screen to
        # say a question exists at all.
        wants = gate_answers(when["is"])
        if wants is None:
            errors.append(f"{where}: `when.is` is an empty list, which is a "
                          "gate no answer could ever meet. Name the answers "
                          "that make this field apply.")
            continue
        seen_answers = []
        for w in wants:
            issue = check_typed_value(gate, w)
            if issue:
                errors.append(f'{where}: `when.is` must name answers '
                              f'"{gate["label"]}" could give — {issue}')
            elif any(_same(w, prior) for prior in seen_answers):
                errors.append(f'{where}: `when.is` names '
                              f'{option_label(gate, w)} twice.')
            else:
                seen_answers.append(w)

    # A cycle would make the setup screen unresolvable: each field waits on
    # the other and neither is ever asked. Refused at load, so it can never
    # be reached at evaluation. Reported once per circle, not once per
    # member — the same fault stated four times reads as four faults.
    reported = set()
    for f in inputs:
        seen, node = [], f["id"]
        while node is not None:
            if node in seen:
                ring = seen[seen.index(node):]
                if frozenset(ring) not in reported:
                    reported.add(frozenset(ring))
                    errors.append(
                        "these inputs depend on each other in a circle, so "
                        "none of them could ever be asked: "
                        + " → ".join(ring + [node]) + ".")
                break
            seen.append(node)
            when = by_input.get(node, {}).get("when")
            node = when.get("input") if isinstance(when, dict) else None


def _check_state_fix(where: str, s: dict, errors: list) -> None:
    """A blocked state names where its answer is given; nothing else may.

    This is the load-time half of "a blocked verdict cannot become a dead
    end", and it is deliberately the half that fires first. An author writing
    a state that stops the program without saying how to start it again finds
    out the moment the bundle is loaded, before any journal is stamped with
    it and long before a user is standing in front of the verdict.

    The reverse — a `fix` on anything else — is refused rather than ignored.
    A hold does not stop, so there is nothing for a button to resolve, and a
    key that silently does nothing is exactly what this contract refuses
    everywhere else.
    """
    if s.get("render") != "blocked":
        if "fix" in s:
            errors.append(
                f"{where}: `fix` names where a blocked verdict is answered, "
                f'so only a `blocked` state carries one. This one is '
                f'`{s.get("render")}`, which does not stop and has nothing '
                "to resolve.")
        return
    if s.get("fix") not in STATE_FIXES:
        errors.append(
            f"{where} is `blocked`, so it must set `fix` to one of "
            f"{', '.join(STATE_FIXES)} — the screens this host can send "
            "someone to. A blocked verdict says the tool will not answer "
            "until you do something; one that does not say where that is "
            "done leaves the reader a sentence and nothing to click. Naming "
            "what is needed in `payload.needs` is not the same thing: prose "
            "cannot be clicked, and a screen cannot be guessed. Anything "
            "missing from that list is a request against the host.")


def validate_declaration(decl) -> list[str]:
    """Every problem with a STRATEGY declaration, as legible sentences.

    An empty list means the declaration is well-formed and speaks this
    contract. Everything is checked without touching the strategy's decide
    logic — this is exactly what lets the host build a setup screen and
    validate a journal before any decision is made.
    """
    if not isinstance(decl, dict):
        return ["STRATEGY must be a mapping (a plain dict)."]
    errors: list[str] = []

    unknown = set(decl) - _DECL_KEYS
    if unknown:
        errors.append("STRATEGY has keys this contract does not know: "
                      + ", ".join(sorted(map(str, unknown)))
                      + ". Unknown keys fail loudly rather than silently "
                        "doing nothing.")

    if not _is_id(decl.get("id")):
        errors.append("`id` must be lowercase letters, digits and hyphens, "
                      "starting with a letter.")
    if not _is_text(decl.get("name")):
        errors.append("`name` must be a user-facing name.")
    if not _is_text(decl.get("summary")):
        errors.append("`summary` must say, in plain language, what this "
                      "strategy is.")

    version = decl.get("version")
    if not (isinstance(version, int) and not isinstance(version, bool)
            and version >= 1):
        errors.append("`version` must be a whole number starting at 1.")
        version = None

    if decl.get("contract") != CONTRACT_VERSION:
        errors.append(f"`contract` must be {CONTRACT_VERSION} — the contract "
                      "version this host speaks. A strategy written for "
                      "another version is refused rather than run wrongly.")

    changelog = decl.get("changelog")
    if not isinstance(changelog, dict) or not changelog:
        errors.append("`changelog` must map each version number to a "
                      "sentence saying what changed in that version.")
    else:
        for k, v in changelog.items():
            if not (isinstance(k, int) and not isinstance(k, bool)) \
                    or not _is_text(v):
                errors.append("`changelog` entries must map a version number "
                              f"to non-empty text; {k!r} does not.")
        if version is not None and version not in changelog:
            errors.append(f"version {version} has no changelog entry. A "
                          "version that does not say what changed is "
                          "refused — the record of rule changes depends on "
                          "it.")

    states = decl.get("states")
    if not isinstance(states, list) or not states:
        errors.append("`states` must be a non-empty list.")
        states = []
    if len(states) > MAX_STATES:
        errors.append(f"{len(states)} states is more than the cap of "
                      f"{MAX_STATES}. Fewer, clearer states — the cap is "
                      "how complexity is kept out.")
    seen = set()
    for i, s in enumerate(states):
        where = f"state {i + 1}"
        if not isinstance(s, dict):
            errors.append(f"{where} must be a mapping.")
            continue
        sid = s.get("id")
        # The host's own states are "host:..." — a colon the id alphabet
        # excludes, so no declared state can ever collide with one. The
        # namespace is protected by construction, not by a check.
        if _is_id(sid):
            where = f'state "{sid}"'
            if sid in seen:
                errors.append(f"{where} is declared twice.")
            seen.add(sid)
        else:
            errors.append(f"{where} needs an `id` in lowercase letters, "
                          "digits and hyphens.")
        unknown = set(s) - _STATE_KEYS
        if unknown:
            errors.append(f"{where} has keys this contract does not know: "
                          f"{', '.join(sorted(map(str, unknown)))}.")
        if not _is_text(s.get("name")):
            errors.append(f"{where} needs a user-facing `name`.")
        if not _is_text(s.get("description")):
            errors.append(f"{where} needs a `description` in plain "
                          "language.")
        if s.get("render") not in RENDER_TYPES:
            errors.append(f"{where} must set `render` to one of the host's "
                          f"six types ({', '.join(RENDER_TYPES)}). A "
                          "strategy cannot add a render type.")
        _check_state_fix(where, s, errors)

    _check_fields("input", decl.get("inputs", []), errors)
    _check_fields("value", decl.get("values", []), errors)
    if isinstance(decl.get("inputs", []), list) \
            and isinstance(decl.get("values", []), list):
        _check_field_graph(decl, errors)

    reference = decl.get("reference", [])
    if not isinstance(reference, list):
        errors.append("`reference` must be a list of file names this bundle "
                      "ships beside its code.")
    else:
        for name in reference:
            if not isinstance(name, str) or not name:
                errors.append("`reference` entries must be file names.")
            elif "/" in name or "\\" in name or name.startswith("."):
                errors.append(f'`reference` entry "{name}" must be a plain '
                              "file name inside the bundle — a strategy "
                              "reads its own shipped data and nothing else.")
            elif not name.endswith((".yaml", ".yml", ".json")):
                errors.append(f'`reference` entry "{name}" must be .yaml, '
                              ".yml or .json — the host parses it so the "
                              "strategy never opens a file itself.")

    input_ids = {f.get("id") for f in decl.get("inputs", [])
                 if isinstance(f, dict)}
    value_ids = {f.get("id") for f in decl.get("values", [])
                 if isinstance(f, dict)}
    for shared in sorted(x for x in input_ids & value_ids if x):
        errors.append(f'"{shared}" is declared as both an input and a '
                      "value. Give one of them a different id — sharing a "
                      "name invites the wrong one being read.")
    return errors


# ---------------------------------------------------------------------------
# what the user supplied
# ---------------------------------------------------------------------------

def input_activity(record: dict, supplied: dict) -> dict:
    """{input id: None if it applies, else one sentence saying why it does
    not}.

    A `when` gate is a pure function of the other answers, which is what
    lets this run identically on a full setup form and on the reduced set a
    strategy was actually handed. A gate whose own answer is missing leaves
    everything below it inactive: a question nobody has reached yet cannot
    make a second question owed.
    """
    specs = {f["id"]: f for f in record.get("inputs", [])
             if isinstance(f, dict) and isinstance(f.get("id"), str)}
    state: dict = {}

    def resolve(fid, chain):
        if fid in state:
            return state[fid]
        if fid in chain:                    # refused at load; contained here
            state[fid] = "this setting depends on itself"
            return state[fid]
        when = specs[fid].get("when")
        if not (isinstance(when, dict) and set(when) == _WHEN_KEYS
                and when.get("input") in specs):
            state[fid] = None
            return None
        other = when["input"]
        gate = specs[other]
        why = resolve(other, chain | {fid})
        wants = gate_answers(when["is"]) or []
        if why is not None:
            state[fid] = (f'it only applies when "{gate["label"]}" does, '
                          "and that does not")
        elif supplied.get(other) is None:
            state[fid] = f'it only applies once "{gate["label"]}" is answered'
        # Per answer through `_same`, never Python's `in`: `in` compares with
        # `==`, under which 1 satisfies a gate listing True and 0 satisfies
        # one listing False. A gate opening on the wrong answer asks a
        # question that does not apply and hides one that does.
        elif not any(_same(supplied.get(other), w) for w in wants):
            state[fid] = (f'it only applies when "{gate["label"]}" is '
                          f'{answer_phrase(gate, wants)}')
        else:
            state[fid] = None
        return state[fid]

    for fid in specs:
        resolve(fid, frozenset())
    return state


def _cross_bound(spec: dict, value, pool: dict) -> str | None:
    """A bound that names another field. Where the other field has no answer
    the bound simply does not apply — an absent figure is not a failed test,
    and refusing an answer because a different question is unanswered would
    be inventing a comparison."""
    for key, word, fails in (("min_from", "at least",
                              lambda a, b: a < b),
                             ("max_from", "at most",
                              lambda a, b: a > b)):
        other = spec.get(key)
        if not isinstance(other, str) or other not in pool:
            continue
        limit, label = pool[other]
        if limit is None or not _is_num(limit) or not fails(value, limit):
            continue
        return (f'must be {word} your {label} ({limit:g}); {value:g} is not.')
    return None


def check_inputs(record: dict, supplied: dict,
                 values: dict | None = None) -> tuple[dict, list[str]]:
    """(what the strategy is handed, every problem as a sentence).

    Run when a journal's answers are saved — "validate at load, not at
    evaluation" — and again defensively before every decision, which is safe
    because the result of the first run is a valid input to the second.

    What comes back is only the inputs that *apply* and have an answer. An
    input whose `when` gate is unmet is never handed over: a stale answer to
    a question that no longer applies is worse than no answer, because the
    strategy has no way to tell the two apart.
    """
    declared = {f["id"]: f for f in record.get("inputs", [])
                if isinstance(f, dict) and isinstance(f.get("id"), str)}
    problems: list[str] = []
    for key in supplied:
        if key not in declared:
            problems.append(f'The journal supplies "{key}", which '
                            f'{record.get("name", "this strategy")} does '
                            "not ask for.")

    activity = input_activity(record, supplied)
    candidates: dict = {}
    for fid, spec in declared.items():
        value = supplied.get(fid)
        inactive = activity.get(fid) is not None
        if value is None:
            if spec.get("required") and not inactive:
                problems.append(f'"{spec["label"]}" ({fid}) is needed and '
                                "the journal does not have it yet. "
                                + str(spec["explain"]).strip())
            continue
        issue = check_typed_value(spec, value)
        if issue:
            problems.append(f'"{spec["label"]}": {issue}')
            continue
        # A stored answer to a question that does not currently apply is
        # still checked, so it cannot lie in wait and block everything the
        # day its gate flips.
        if not inactive:
            candidates[fid] = value

    # Bounds that name another field come last, once every plain answer is
    # known good — otherwise a mistyped figure would be compared against.
    # Ids are unique across inputs and values, so one pool cannot be
    # ambiguous.
    labels = {v["id"]: v.get("label") or v["id"]
              for v in record.get("values", []) if isinstance(v, dict)
              and isinstance(v.get("id"), str)}
    pool = {vid: (value, labels.get(vid, vid))
            for vid, value in (values or {}).items()}
    pool.update({fid: (v, declared[fid]["label"])
                 for fid, v in candidates.items()})
    for fid in list(candidates):
        issue = _cross_bound(declared[fid], candidates[fid], pool)
        if issue:
            problems.append(f'"{declared[fid]["label"]}" {issue}')
            candidates.pop(fid)
    return candidates, problems


def input_roles(record: dict, effective: dict) -> dict:
    """{role: {"id", "label", "value"} | {"id", "label", "reason"}} for every
    role this strategy claims. The host reports the facts a role unlocks and
    holds no view about the figure itself; where the question exists but is
    unanswered, the reason says so by name, so the screen can point at the
    field rather than at a shrug."""
    out = {}
    for f in record.get("inputs", []):
        role = f.get("role") if isinstance(f, dict) else None
        if not isinstance(role, str) or role not in INPUT_ROLES or role in out:
            continue
        entry = {"id": f["id"], "label": f["label"]}
        if f["id"] in effective:
            entry["value"] = effective[f["id"]]
        else:
            entry["reason"] = (f'{record.get("name", "this strategy")} asks '
                               f'for "{f["label"]}" and this journal has no '
                               "answer yet")
        out[role] = entry
    return out


# ---------------------------------------------------------------------------
# the decision
# ---------------------------------------------------------------------------

_DECISION_KEYS = {"state", "payload", "reason"}
_REASON_KEYS = {"rule", "summary", "evidence", "groups", "note"}


def _names(keys) -> str:
    """Key names for a message. Sorted by their text, because a plugin may
    hand back keys of mixed types and comparing those would raise inside
    the very code whose job is to refuse them."""
    return ", ".join(sorted((str(k) for k in keys)))


def _bad_size(size, *, above_zero=True) -> bool:
    return not (isinstance(size, dict) and set(size) == {"unit", "value"}
                and size.get("unit") in SIZE_UNITS
                and _is_num(size.get("value"))
                and (size["value"] > 0 if above_zero else size["value"] >= 0))


def _bad_condition(cond) -> bool:
    return not (isinstance(cond, dict) and set(cond) == {"summary"}
                and _is_text(cond.get("summary")))


def _check_plan(plan, unit, errors: list) -> None:
    """The tranches a staged entry is holding back, and every way the list
    goes wrong.

    A staged entry is one decision, not several: the state is still `commit`
    and the size in front of you is still the size in front of you. What the
    plan adds is the part a single tranche cannot say — that this 2% is the
    first third of an intended 6%, and what has to be true before the rest
    goes in. Without it the screen cannot tell a whole position from the
    opening slice of one, and the user cannot see at the moment of the first
    purchase that they are committing to a shape at all, which is the entire
    value of sizing something while calm.

    Three refusals, each closing a way the list would say less than it looks
    like it says:

    - a tranche with no condition is not held back, it is just more of the
      size in front of you. Left permissible, "3% now and 3% more, sometime"
      would render as a plan while committing to nothing.
    - the units have to match the size's. A first tranche in percent and a
      second in dollars cannot be added up, so nothing could say what the
      whole position is meant to be — and a screen would have to either
      guess or quietly show one of the two.
    - the host never checks whether a condition has been met, and must not
      look as though it might. It is prose the strategy re-reads on its own
      next evaluation: the day the condition holds, the strategy returns that
      tranche as the size in front of you, with no condition on it. Nothing
      is stored, nothing is scheduled, and the business is re-tested every
      time — which is strictly better than a plan executing itself six months
      after the last time anyone looked at the company.

    Worth naming because it is the shape people reach for first and it is
    absent by construction: a plan anchored to your own purchase price — a
    third now, a third 25% below what you paid — cannot be written here at
    all. Not because the payload lacks a field, but because nothing about
    what a position cost is in the context (see HOST_FACTS), so no strategy
    can know what "25% below what you paid" means. That is averaging down
    with a schedule attached, and it is refused one level deeper than this
    check. A plan anchored to what the business is worth — a third at a
    third off intrinsic value, a third at half off — asks the same shape of
    question about a number that is not about you, and writes fine.
    """
    if not isinstance(plan, list) or not plan:
        errors.append(
            "`plan` must be a non-empty list of the further tranches this "
            "entry is holding back, or be left out entirely. An empty list "
            "is a staged plan that stages nothing.")
        return
    for i, tranche in enumerate(plan):
        where = f"`plan` tranche {i + 1}"
        if not isinstance(tranche, dict) or set(tranche) != {"size",
                                                             "condition"}:
            errors.append(f"{where} must be exactly {{size, condition}}.")
            continue
        if _bad_size(tranche["size"]):
            errors.append(f"{where}: `size` must be {{unit, value}} with unit "
                          f"one of {', '.join(SIZE_UNITS)} and value above "
                          "zero.")
        elif tranche["size"]["unit"] != unit:
            errors.append(
                f'{where} is measured in {tranche["size"]["unit"]} and the '
                f"size in front of you is in {unit}. Every tranche of one "
                "plan has to be in the same unit, or nothing can say what "
                "the whole position is meant to come to.")
        if tranche["condition"] is None or _bad_condition(tranche["condition"]):
            errors.append(
                f"{where}: `condition` must be {{summary: plain language}} "
                "saying what has to be true before this tranche goes in. A "
                "tranche with no condition is not held back — it is more of "
                "the size in front of you, and belongs in that number.")


def _check_payload(render: str, payload, errors: list) -> None:
    keys = RENDER_TYPES[render]["payload_keys"]
    optional = RENDER_TYPES[render]["optional_keys"]
    if not isinstance(payload, dict):
        errors.append("`payload` must be a mapping.")
        return
    missing = [k for k in keys if k not in payload]
    extra = set(payload) - set(keys) - set(optional)
    if missing:
        errors.append(f"a `{render}` state's payload must carry: "
                      f"{', '.join(missing)}. A bare word is not a "
                      "decision.")
    if extra:
        errors.append(f"a `{render}` state's payload does not know: "
                      f"{_names(extra)}. Extra facts belong in the reason's "
                      "`evidence`.")
    if missing or extra:
        return

    if render == "commit":
        size = payload["size"]
        if _bad_size(size):
            errors.append("`size` must be {unit, value} with unit one of "
                          f"{', '.join(SIZE_UNITS)} and value above zero — "
                          "how much, or a staged entry collapses into buying "
                          "everything on day one.")
        cond = payload["condition"]
        if cond is not None and _bad_condition(cond):
            errors.append("`condition` must be None (commit now, "
                          "unconditionally) or {summary: plain language} "
                          "saying what must be true first.")
        if payload.get("plan") is not None:
            # Checked against the size's own unit, so a malformed size does
            # not also produce a wrong-unit complaint about every tranche.
            _check_plan(payload["plan"], (size or {}).get("unit")
                        if isinstance(size, dict) else None, errors)
    elif render == "reduce":
        to = payload["to"]
        if not (isinstance(to, dict) and set(to) == {"unit", "value"}
                and to.get("unit") in ("weight", "shares")
                and _is_num(to.get("value")) and to["value"] >= 0):
            errors.append("`to` must be {unit, value} naming the level to "
                          "reduce to — weight (a percent number) or "
                          "shares.")
    elif render == "close":
        if not _is_date(payload["when"]):
            errors.append("`when` must be a YYYY-MM-DD date — the day the "
                          "exit is due. A close without a date makes a "
                          "scheduled exit fire months early.")
    elif render == "blocked":
        needs = payload["needs"]
        if not (isinstance(needs, list) and needs
                and all(_is_text(n) for n in needs)):
            errors.append("`needs` must be a non-empty list of sentences "
                          "saying what decision is owed from the user.")


def _check_limit(record, spec, where, errors, *, what="`comparator`") -> None:
    """A limit is either stated or cited, and the two are mutually exclusive.

    Supplying both is what let a strategy attribute any number at all to a
    setting: "at most your position cap of 5" while the cap held 20, with
    nothing checking. That is the misquote the evidence split exists to
    prevent, at the one place the split had a hole — so it is closed the way
    principle 14 asks, by making the pair unrepresentable rather than by
    comparing the two and complaining.

    Shared by an evidence item and by a group's `at_least`, because a group
    counting passes against a limit can misattribute one in exactly the same
    way a row can.
    """
    limits = [k for k in ("threshold", "threshold_from") if k in spec]
    if len(limits) != 1:
        errors.append(
            f"{where}: {what} needs exactly one of `threshold` (a figure the "
            "strategy states outright) or `threshold_from` (the id of one of "
            "its own settings, which the host reads for itself). It carries "
            f"{_names(limits) or 'neither'}."
            + (" Naming the setting AND supplying the number is how a limit "
               "gets attributed to a setting that does not hold it — drop "
               "the `threshold` and the host will read the setting."
               if len(limits) == 2 else ""))
    if "threshold" in spec and not _is_scalar(spec["threshold"]):
        errors.append(f"{where}: `threshold` must be a number, a "
                      "YYYY-MM-DD date, true/false, or text.")
    if "threshold_from" in spec:
        known = {f["id"] for f in record.get("values", [])} \
            | {f["id"] for f in record.get("inputs", [])}
        if spec["threshold_from"] not in known:
            errors.append(
                f'{where}: `threshold_from` names "'
                f'{spec["threshold_from"]}", which this strategy declares as '
                "neither a value nor an input. The host reads the limit out "
                "of the setting you name, so it has to be one this strategy "
                "owns.")


def _check_groups(record, reason, errors) -> set:
    """Every group a decision declares, and every way the set can be wrong.
    Returns the ids that are usable, so an item naming one can be checked.

    A group is where a strategy says which of its citations were
    requirements. That is the only thing standing between "this row failed
    and the verdict was buy" being a contradiction and being a bonus test
    doing exactly what it is for, so the declaration is checked as hard as
    anything else here.
    """
    groups = reason.get("groups")
    if groups is None:
        return set()
    if not isinstance(groups, list) or not groups:
        errors.append("`reason.groups` must be a non-empty list of the "
                      "headings this decision's evidence is gathered under, "
                      "or be left out entirely.")
        return set()
    ok, seen = set(), set()
    for i, g in enumerate(groups):
        where = f"group {i + 1}"
        if not isinstance(g, dict):
            errors.append(f"{where} must be a mapping.")
            continue
        gid = g.get("id")
        if _is_id(gid):
            where = f'group "{gid}"'
            if gid in seen:
                errors.append(f"{where} is declared twice.")
                continue
            seen.add(gid)
        else:
            errors.append(f"{where} needs an `id` in lowercase letters, "
                          "digits and hyphens.")
        unknown = set(g) - _GROUP_KEYS
        if unknown:
            errors.append(f"{where} has keys this contract does not know: "
                          + _names(unknown) + ".")
        if not _is_text(g.get("name")):
            errors.append(f"{where} needs a `name` — the subheading a reader "
                          "sees above these rows.")
        requires = g.get("requires", "all")
        if requires not in GROUP_REQUIREMENTS:
            errors.append(
                f"{where}: `requires` must be one of "
                f"{', '.join(GROUP_REQUIREMENTS)}. Left out, it is `all` — "
                "the strict reading, because a group that quietly demanded "
                "nothing is how a contradiction gets through.")
        elif requires == "at_least":
            _check_limit(record, g, where, errors,
                         what="`requires: at_least`")
            limit = g.get("threshold")
            if "threshold" in g and not (isinstance(limit, int)
                                         and not isinstance(limit, bool)
                                         and limit >= 0):
                errors.append(f"{where}: `requires: at_least` counts rows, "
                              "so its `threshold` must be a whole number of "
                              "them, nought or more.")
        elif any(k in g for k in ("threshold", "threshold_from")):
            errors.append(
                f'{where}: `requires: {requires}` sets no limit, so it '
                "cannot carry one. Only `at_least` counts against a number.")
        if _is_id(gid):
            ok.add(gid)
    return ok


def _check_group_membership(evidence, declared, errors) -> None:
    """Which rows sit under which heading, and the two ways that goes wrong.

    An empty group is a subheading over nothing. A group whose rows are
    scattered would have to reopen its heading further down the list, which
    is not a thing a reader can follow or a screen can draw — so the rows of
    one group are contiguous, and that is refused here rather than papered
    over at render time.
    """
    order, runs = [], {}
    for item in evidence:
        gid = item.get("group") if isinstance(item, dict) else None
        if not isinstance(gid, str):
            gid = None
        if not order or order[-1] != gid:
            order.append(gid)
        if gid is not None:
            runs[gid] = runs.get(gid, 0) + 1
    for gid in declared:
        if gid not in runs:
            errors.append(f'group "{gid}" is declared and nothing is cited '
                          "under it. A heading over no rows is a heading the "
                          "reader has to work out the meaning of.")
    for gid in sorted(set(order) - {None} - set(declared)):
        errors.append(f'evidence names the group "{gid}", which '
                      "`reason.groups` does not declare. A heading has to say "
                      "what it demands of the rows under it.")
    scattered = sorted({gid for gid in set(order) - {None}
                        if order.count(gid) > 1})
    for gid in scattered:
        errors.append(f'the rows in group "{gid}" are not together. A group '
                      "renders as one heading over one run of rows, so its "
                      "citations have to be consecutive.")


def _check_evidence_item(record, item, where, errors) -> None:
    """One citation's own shape, without resolving it. Whether the thing
    cited exists is a separate question, answered in resolve_evidence."""
    if not isinstance(item, dict):
        errors.append(f"{where} must be a mapping.")
        return
    unknown = set(item) - _ITEM_KEYS
    if unknown:
        errors.append(f"{where} has keys this contract does not know: "
                      + _names(unknown) + ".")
    if "group" in item and not isinstance(item["group"], str):
        errors.append(f"{where}: `group` must name one of `reason.groups` by "
                      "id.")

    named = [k for k in _SUBJECT_KEYS if k in item]
    if len(named) != 1:
        errors.append(
            f"{where} must name exactly one subject — `measure` (a bank "
            "measure), `fact` (a figure the host reports), `input`, `value`, "
            "or `label` with `unit` for something the strategy works out "
            f"itself. It names {_names(named) or 'none'}.")
        return
    subject = named[0]

    if subject == "label":
        if not _is_text(item.get("label")):
            errors.append(f"{where}: `label` must say what this figure is.")
        if item.get("unit") not in EVIDENCE_UNITS:
            errors.append(f"{where}: `unit` must be one of "
                          f"{', '.join(EVIDENCE_UNITS)}. A strategy chooses "
                          "how a number reads from the host's list; it never "
                          "invents a rendering.")
        has = [k for k in ("actual", "absent") if k in item]
        if len(has) != 1:
            errors.append(f"{where} must carry exactly one of `actual` (the "
                          "figure) or `absent` (one sentence saying why it "
                          "is unknown). The host cannot supply a figure it "
                          "did not compute.")
        elif "absent" in item and not _is_text(item["absent"]):
            errors.append(f"{where}: `absent` must be a sentence saying why "
                          "the figure is unknown.")
        elif "actual" in item and not _is_scalar(item["actual"]):
            errors.append(f"{where}: `actual` must be a number, a "
                          "YYYY-MM-DD date, true/false, or text.")
    else:
        for banned in ("actual", "absent", "unit"):
            if banned in item:
                errors.append(
                    f"{where} cites `{subject}`, so the host supplies its "
                    f"value, unit and absence — remove `{banned}`. A figure "
                    "the host already knows is never restated by a strategy, "
                    "because a restatement can be wrong.")
        if not isinstance(item[subject], str):
            errors.append(f"{where}: `{subject}` must name one by id.")

    if "at" in item:
        if subject != "measure":
            errors.append(f"{where}: `at` names a reading in a measure's "
                          "filing history, so it only means something "
                          "alongside `measure`.")
        elif not _is_date(item["at"]):
            errors.append(f"{where}: `at` must be the YYYY-MM-DD period end "
                          "of the reading being cited.")

    if "since" in item:
        if subject != "measure":
            errors.append(f"{where}: `since` measures how far a bank measure "
                          "has moved, so it only means something alongside "
                          "`measure`.")
        elif "at" in item:
            errors.append(
                f"{where} carries both `at` and `since`. `at` cites the "
                "reading at one moment; `since` cites the distance between "
                "two. One citation answers one question — cite the reading "
                "and the change as two rows if you want both.")
        elif item["since"] not in BASELINE_ANCHORS:
            errors.append(
                f'{where}: `since` must be one of '
                f"{', '.join(BASELINE_ANCHORS)} — the moments the host can "
                "anchor to. A strategy never invents one; anything missing "
                "is a request against the host.")

    if "change" in item:
        if "since" not in item:
            errors.append(
                f"{where}: `change` says how a move from a baseline is "
                "counted, so it only means something alongside `since`. On "
                "its own there are not two readings to have moved between.")
        elif item["change"] not in CHANGE_FORMS:
            errors.append(
                f'{where}: `change` must be one of '
                f"{', '.join(CHANGE_FORMS)} — the ways the host counts a "
                "move. A strategy never invents one; anything missing is a "
                "request against the host.")

    has_cmp = "comparator" in item
    limits = [k for k in ("threshold", "threshold_from") if k in item]
    if has_cmp:
        _check_limit(record, item, where, errors)
        if item["comparator"] not in COMPARATORS:
            errors.append(f"{where}: `comparator` must be one of "
                          f"{', '.join(COMPARATORS)}.")
    elif limits:
        errors.append(
            f"{where} carries {_names(limits)} with no `comparator` saying "
            "what the limit is. An item with neither is an observation, "
            "which is a fine thing to cite.")


def validate_decision(record: dict, decision) -> list[str]:
    """Everything wrong with what a strategy returned. Empty means the
    decision conforms and can be rendered."""
    if not isinstance(decision, dict):
        return ["the strategy returned "
                f"{type(decision).__name__ if decision is not None else 'nothing'}"
                ", not a decision mapping."]
    errors = []
    unknown = set(decision) - _DECISION_KEYS
    missing = _DECISION_KEYS - set(decision)
    if unknown:
        errors.append("the decision has keys this contract does not know: "
                      + _names(unknown) + ".")
    if missing:
        errors.append("the decision is missing: " + _names(missing) + ".")
        return errors

    states = {s["id"]: s for s in record.get("states", [])}
    sid = decision["state"]
    # A state id arrives from plugin code, so it may be any object at all —
    # including an unhashable one. Comparing by text refuses it as invented
    # vocabulary instead of raising inside the check that exists to refuse it.
    state = states.get(sid) if isinstance(sid, str) else None
    if state is None:
        errors.append(f"{sid!r} is not a state this strategy declared. A "
                      "strategy speaks only its own declared vocabulary.")
    else:
        _check_payload(state["render"], decision["payload"], errors)

    reason = decision["reason"]
    if not isinstance(reason, dict):
        errors.append("`reason` must be a mapping — a structured reason is "
                      "displayed at equal weight to the state, never free "
                      "text, never absent.")
    else:
        unknown = set(reason) - _REASON_KEYS
        if unknown:
            errors.append("`reason` has keys this contract does not know: "
                          + _names(unknown) + ".")
        if not _is_text(reason.get("rule")):
            errors.append("`reason.rule` must name the rule inside the "
                          "strategy that produced this state — a verdict "
                          "without its rule teaches nothing.")
        if not _is_text(reason.get("summary")):
            errors.append("`reason.summary` must say, in one plain "
                          "sentence, why this state and not another.")
        # None is how a strategy says "nothing to add" when the note is
        # computed rather than literal; only a non-sentence is a mistake.
        if reason.get("note") is not None and not _is_text(reason["note"]):
            errors.append("`reason.note` is the escape hatch for what "
                          "genuinely will not fit an evidence item. It must "
                          "be a sentence, None, or be left out.")

        declared_groups = _check_groups(record, reason, errors)

        evidence = reason.get("evidence")
        if not isinstance(evidence, list):
            errors.append("`reason.evidence` must be a list of the figures "
                          "this decision rests on. Each one cites what was "
                          "looked at and what was required; the host fills "
                          "in what it was.")
        else:
            for i, item in enumerate(evidence):
                _check_evidence_item(record, item, f"evidence {i + 1}",
                                     errors)
            _check_group_membership(evidence, declared_groups, errors)
            # A verdict about the security must say what it looked at. An
            # evaluation-tier state is allowed to cite nothing, because
            # "the strategy could not run" is not a claim about the company.
            if not evidence and state is not None \
                    and RENDER_TYPES[state["render"]]["tier"] == "position":
                errors.append(
                    "`reason.evidence` is empty. A verdict about the "
                    "security has to say what it rested on — cite the "
                    "measures, facts or settings you read, even when the "
                    "answer was that they were absent.")
    return errors


# ---------------------------------------------------------------------------
# resolving evidence — the host answers what the strategy asked
# ---------------------------------------------------------------------------

def _observed(value, source, cautions=None, provenance=None) -> dict:
    return {"status": "known", "value": value, "source": source,
            "cautions": list(cautions or []),
            "provenance": list(provenance or [])}


def _unobserved(reason, source) -> dict:
    return {"status": "absent", "reason": reason, "source": source}


def _measure_observation(ctx, item):
    mid = item["measure"]
    entry = (ctx.get("measures") or {}).get(mid)
    if entry is None:
        return None, (f'the measure "{mid}", which is not in the metric '
                      "bank. A strategy asks only for measures the host "
                      "offers; anything missing is a request against the "
                      "host, not something to work around.")
    if "at" not in item:
        cur = entry["current"]
        if cur["status"] == "known":
            return _observed(cur["value"], "measure", cur.get("cautions"),
                             cur.get("provenance")), None
        return _unobserved(cur["reason"], "measure"), None

    points = entry["series"]["points"]
    hit = next((p for p in points if p["period_end"] == item["at"]), None)
    if hit is None:
        held = ", ".join(p["period_end"] for p in points) or "none"
        return _unobserved(
            f'no reading of this measure is on record for the period '
            f'ending {item["at"]} (the periods held are: {held})',
            "measure"), None
    if hit["value"] is None:
        return _unobserved(hit["reason"], "measure"), None
    # The filing this reading came from, then how the reading was built and
    # what qualifies it. A point is a measure like any other: citing one at
    # a past period must not be the way to get a figure with its cautions
    # filed off, because a screen showing evidence has no other source for
    # them and a frozen snapshot keeps whatever it was handed forever.
    return _observed(hit["value"], "measure", hit.get("cautions"),
                     [f'{hit["form"]} for the period ending '
                      f'{hit["period_end"]}, filed {hit["filed"]}']
                     + list(hit.get("provenance") or [])), None


def _change_form(item) -> str:
    """Which of the two ways a move from a baseline is measured.

    Left out, it is `distance` — what every citation written before this key
    existed meant, and what it goes on meaning. A default that changed the
    arithmetic would be the silent misreading the contract version exists to
    refuse, so the default is the old behaviour and the new one is asked for
    by name.
    """
    form = item.get("change") if _is_mapping(item) else None
    return form if form in CHANGE_FORMS else "distance"


def _baseline_observation(ctx, item):
    """How far a measure has moved since a purchase.

    The subtraction is the host's, and that is the whole point of the
    citation existing. A strategy can already reach both readings and take
    one from the other — what it cannot do is *cite* the answer, because an
    evidence item compares an observation against a limit, and a limit is
    either a number the strategy states outright or the id of one of its own
    settings. "At least five points below what it was when you bought" is
    neither: the number is baseline minus five, which the strategy would have
    to work out and state, and the host would have no way to check. That is
    the one hole left in cite-don't-quote, at the exact place a wrong number
    is least visible — a drift test states a threshold that looks arbitrary
    to a reader and cannot be traced to anything.

    So the strategy owns the question — which measure, which anchor, which
    direction, what tolerance — and the host owns every number in the row:
    the reading then, the reading now, the distance between them, its unit,
    and whether the tolerance was met.

    The reading *then* comes off the snapshot the purchase froze, never a
    recomputation of that day. Both are worth having and only one of them is
    the baseline: a recomputation answers "what do today's filings say about
    that day", and a restatement moves it. What a re-underwrite is measured
    against is what you were shown when you said yes.

    Absence on either side is absence, never a pass and never a zero. Two
    sides means two reasons and they read differently — no purchase to
    measure from, no reading on record at the purchase, no reading now — so
    each says which it is rather than collapsing into one shrug.
    """
    mid, anchor_id = item["measure"], item["since"]
    spec = BASELINE_ANCHORS.get(anchor_id)
    if spec is None:
        return None, (f'the baseline "{anchor_id}", which the host does not '
                      "anchor to. It anchors to: "
                      f"{', '.join(BASELINE_ANCHORS)}.")
    # Refused here and not left to `_change_form`, which has to keep handing
    # back a usable key because the rendering path indexes CHANGE_FORMS with
    # it. A form the host does not have is a fault in the strategy, exactly
    # like an anchor it does not have, and it has to be loud in the same
    # place: `test` is asked how a comparison came out *while the strategy is
    # deciding*, before any validation runs, so a misspelling that quietly
    # fell back to `distance` would change the arithmetic a verdict was
    # chosen by and leave nothing on screen saying so.
    if "change" in item and item["change"] not in CHANGE_FORMS:
        return None, (f'how "{mid}" has moved counted as '
                      f'"{item["change"]}", which is not one of the ways the '
                      f"host counts a move. It counts: "
                      f"{', '.join(CHANGE_FORMS)}.")
    entry = (ctx.get("measures") or {}).get(mid)
    if entry is None:
        return None, (f'the measure "{mid}", which is not in the metric '
                      "bank. A strategy asks only for measures the host "
                      "offers; anything missing is a request against the "
                      "host, not something to work around.")

    anchor = ((ctx.get("position") or {}).get("baselines") or {}).get(anchor_id)
    if not _is_mapping(anchor) or anchor.get("status") != "known":
        return _unobserved(
            _read(anchor, "reason")
            or f'there is no {spec["means"]} to measure from', "baseline"), None

    when = anchor.get("date")
    then = (anchor.get("measures") or {}).get(mid)
    if not _is_mapping(then) or then.get("status") != "known":
        return _unobserved(
            _read(then, "reason")
            or ("no reading of this was on record when you bought on "
                f"{when}, so there is nothing to measure from"),
            "baseline"), None

    now = entry["current"]
    if now["status"] != "known":
        return _unobserved(
            f'{now.get("reason") or "there is no reading now"}, so how far '
            "it has moved cannot be worked out", "baseline"), None

    before, after = then["value"], now["value"]
    if not _is_num(before) or not _is_num(after):
        return None, (f'how "{mid}" has moved since {spec["label"]}. It is '
                      f"{_kind_of(after)} now and {_kind_of(before)} then, "
                      "and a distance only means something between numbers.")

    # Both sides' qualifications, each saying which reading it belongs to. A
    # change is exactly as trustworthy as the less trustworthy of the two
    # readings behind it, and dropping either half is how a figure built on
    # an approximated market cap arrives on screen looking exact.
    cautions = [f"the reading now — {c}" for c in (now.get("cautions") or [])]
    cautions += [f"the reading you bought at — {c}"
                 for c in (then.get("cautions") or [])]
    frozen = (f"{before:g} on {when}, frozen at that purchase and not worked "
              f"out again, against {after:g} now")

    if _change_form(item) == "proportion":
        # Against the SIZE of the reading then, never its sign. A margin that
        # was -4% and is now -8% has got twice as bad, and dividing by a
        # negative would report that as +100% — a worsening rendered as an
        # improvement, in a figure an exit rule fires on.
        #
        # Nought has no share of it to take. Not a very large number, not a
        # zero, not carried over from the distance: absent, with the reason,
        # exactly as principle 4 asks of every value the host cannot honestly
        # reach.
        if before == 0:
            return _unobserved(
                f"this was nought on {when}, and a share of nought is not a "
                "quantity — how far it has moved in proportion cannot be "
                "worked out from it", "baseline"), None
        return _observed(
            (after - before) / abs(before) * 100, "baseline", cautions,
            [frozen + f", which is a move of {(after - before) / abs(before) * 100:+.1f}% "
                      "against what it was then"]), None

    return _observed(after - before, "baseline", cautions, [frozen]), None


def _fact_observation(ctx, item):
    fid = item["fact"]
    spec = HOST_FACTS.get(fid)
    if spec is None:
        return None, (f'the host fact "{fid}", which the host does not '
                      f"report. It reports: {', '.join(HOST_FACTS)}.")
    node = ctx
    for step in spec["path"]:
        node = _read(node, step)
    if spec["bare"]:
        if node is None:
            return _unobserved(spec["when_missing"]
                               or "the journal does not record this",
                               "fact"), None
        return _observed(node, "fact"), None
    if not _is_mapping(node):
        return _unobserved("the host did not report this figure",
                           "fact"), None
    if node.get("status") == "known":
        seen = _observed(node["value"], "fact", node.get("cautions"),
                         node.get("provenance"))
        # Anything else the host hung on the node comes across too — the
        # close's own date and symbol, whether its series has ended. Only
        # `value`, `cautions` and `provenance` used to survive, so the one
        # node that carried a structured date lost it here, and both the
        # evidence row and the snapshot frozen from it were left with a
        # number and no way to say which day it belonged to. A frozen record
        # is written once; a fact dropped here can never be recovered.
        for key, extra in node.items():
            if key not in seen and key != "status":
                seen[key] = extra
        return seen, None
    return _unobserved(node.get("reason")
                       or "the host cannot report this figure", "fact"), None


def _is_mapping(node) -> bool:
    """A dict, or the read-only view of one a strategy is handed. Both are
    mappings; only one is a `dict`, and the difference must not decide
    whether a figure can be read."""
    return isinstance(node, (dict, MappingProxyType))


def _read(node, step):
    return node.get(step) if _is_mapping(node) else None


def _pool(ctx, kind) -> dict:
    return (ctx.get("values") if kind == "value" else ctx.get("inputs")) or {}


def _setting_observation(ctx, kind, fid):
    """A declared value or an answered input, read out of the context."""
    pool = _pool(ctx, kind)
    if fid not in pool or pool[fid] is None:
        return _unobserved("this setting has no value yet", kind), None
    return _observed(pool[fid], kind), None


def _subject_of(item) -> str | None:
    named = [k for k in _SUBJECT_KEYS if k in item]
    return named[0] if len(named) == 1 else None


def _observation(ctx, item, subject):
    """(observation, problem) — the figure a citation names, from the context
    alone.

    Context alone is the point: this is the one resolution, shared by the
    host answering a citation on screen and by a strategy asking `test` how
    a comparison came out while it decides. Two implementations of it could
    disagree, and the whole reason v5 exists is that two of them did.
    """
    if subject == "measure":
        if "since" in item:
            return _baseline_observation(ctx, item)
        return _measure_observation(ctx, item)
    if subject == "fact":
        return _fact_observation(ctx, item)
    if subject == "label":
        if "actual" in item:
            return _observed(item["actual"], "stated"), None
        return _unobserved(item.get("absent"), "stated"), None
    return _setting_observation(ctx, subject, item[subject])


def _declared_unit(spec) -> str:
    """How a declared setting renders. Its own `unit` where it named one from
    the host's list, and otherwise whatever its type can honestly claim."""
    if spec.get("unit") in EVIDENCE_UNITS:
        return spec["unit"]
    return ("yes_no" if spec["type"] == "boolean"
            else "text" if spec["type"] == "text" else "none")


def _declared_spec(record, fid):
    """(kind, spec) for a declared setting named by id, or (None, None). Ids
    are unique across inputs and values, so one lookup cannot be ambiguous."""
    for kind in ("value", "input"):
        spec = next((f for f in record.get(kind + "s", [])
                     if f["id"] == fid), None)
        if spec is not None:
            return kind, spec
    return None, None


def _declared_observation(record, ctx, item, subject):
    """An input or a declared value, cited by id. Its label and unit come
    from the declaration, so a setting always reads on screen the way its
    author named it."""
    fid = item[subject]
    spec = next((f for f in record.get(subject + "s", [])
                 if f["id"] == fid), None)
    if spec is None:
        return None, (f'the {subject} "{fid}", which this strategy does not '
                      "declare.")
    return {"kind": subject, "id": fid, "label": spec["label"],
            "unit": _declared_unit(spec), "explain": spec["explain"]}, None


def _limit(ctx, item):
    """(threshold, absent-reason) — the limit a comparison is measured
    against, read out of the context.

    A limit is either stated by the strategy or read out of one of its own
    settings, never both — the declaration refuses the pair. Where it is
    cited, the number comes from this journal's resolved settings and not
    from the strategy, for the same reason nothing else in an evidence item
    does: a figure the strategy restates is a figure it can restate wrongly,
    and "at most your position cap of 5" over a cap holding 20 is a sentence
    the screen has no way to catch. The strategy owns the question — which
    setting, which direction. The host owns the number.

    An absent reason is not a failure: an optional input nobody answered
    sets no limit, and a test with no limit is unknown rather than passed.
    """
    if "threshold_from" not in item:
        return item.get("threshold"), None
    fid = item["threshold_from"]
    for kind in ("value", "input"):
        pool = _pool(ctx, kind)
        if fid in pool and pool[fid] is not None:
            return pool[fid], None
    return None, (f'"{fid}" has no answer in this journal, so the limit it '
                  "sets cannot be read")


def _test_view(record, ctx, item):
    """What the strategy required, rendered — the same limit `_limit` reads,
    with the setting's own label and unit beside it so the screen can say
    whose limit it is and render it the way its author named it, rather than
    in whatever unit the thing being measured happens to use."""
    if "comparator" not in item:
        return None
    phrase = (COMPARATORS[item["comparator"]]["phrase"]
              if item["comparator"] in COMPARATORS else None)
    threshold, absent = _limit(ctx, item)
    source = None
    if "threshold_from" in item:
        fid = item["threshold_from"]
        kind, spec = _declared_spec(record, fid)
        if spec is None:                   # refused by validate_decision
            absent = (f'"{fid}" is not a setting this strategy declares, so '
                      "there is no limit to read")
        else:
            source = {"kind": kind, "id": fid, "label": spec["label"],
                      "unit": _declared_unit(spec)}
            if absent is not None:
                absent = (f'"{spec["label"]}" has no answer in this journal, '
                          "so the limit it sets cannot be read")
    return {"comparator": item["comparator"], "phrase": phrase,
            "threshold": None if absent else threshold,
            "threshold_from": source, "absent": absent}


def _outcome(observation, comparator, threshold, absent):
    """(outcome, problem) — pass, fail, unknown or noted. Derived, never
    claimed: the strategy chose the question, and arithmetic is not an
    opinion.

    Either side of the comparison can be missing and neither missing side is
    ever success. An absent figure is `unknown`, and so is a limit the host
    could not read out of the setting it was told to read — a test whose
    limit nobody has supplied has not been passed, it has not been run.
    """
    if comparator is None:
        return NOTED, None
    cmp_ = COMPARATORS.get(comparator)
    if cmp_ is None:
        return None, (f'"{comparator}" is not one of the comparisons this '
                      f"host makes ({', '.join(COMPARATORS)}).")
    if absent is not None or observation["status"] != "known":
        return UNKNOWN, None
    actual = observation["value"]
    if _kind_of(actual) != _kind_of(threshold):
        return None, (f"it compares {_kind_of(actual)} against "
                      f"{_kind_of(threshold)}, and the two have to be the "
                      "same kind of thing.")
    if cmp_["numeric_only"] and _kind_of(actual) not in ("number", "date"):
        return None, (f'"{comparator}" only means something for numbers and '
                      "dates.")
    return (PASS if cmp_["fn"](actual, threshold) else FAIL), None


def _cited_as(item) -> str:
    subject = _subject_of(item)
    if subject is None:
        return "this citation"
    named = item[subject] if subject != "label" else item.get("label")
    at = f' at {item["at"]}' if "at" in item else ""
    if "since" in item:
        anchor = BASELINE_ANCHORS.get(item["since"]) or {}
        form = _change_form(item)
        at = (f' {anchor.get("label", item["since"])}'
              + (" as a share of what it was"
                 if form == "proportion" else ""))
    return f'the test of "{named}"{at}'


def test(ctx: dict, item: dict) -> str:
    """How one comparison came out: "pass", "fail", "unknown" or "noted".

    This is the host answering the same question it will answer again when
    the citation reaches the screen, out of the same context, through the
    same code. That is the entire point of it existing. Before it did, a
    strategy had to compare the figure itself in order to choose a state —
    the state is chosen before any evidence is resolved — so every strategy
    carried a private copy of the comparators, nothing checked the two
    agreed, and a verdict could be returned beside evidence saying the
    opposite. Both halves rendered, and neither said which was wrong.

    `item` is an evidence item, exactly as it will be cited: same subject,
    same comparator, same limit. Pass the item you are going to cite and the
    two cannot come apart.

    Absence never comes out as success. A figure the host could not observe,
    or a limit nobody has answered, is "unknown" — never "pass" and never
    "fail". An item with no comparator is "noted": an observation, which is
    a fine thing to cite.

    Raises ValueError where the citation is not answerable at all — a
    measure the bank does not hold, a fact the host does not report, a
    comparison between a number and a date. That is a fault in the strategy
    rather than a fact about the security, and `evaluate` contains it as an
    error in place. It is deliberately not "unknown", which would let a
    misspelled measure id read as a missing figure.

    One case it cannot raise on: a `value` or `input` named by an id the
    strategy does not declare. The context carries answers, not the
    declaration, so an id that is missing from it is indistinguishable here
    from an optional input nobody has answered — and that one is legitimate.
    It comes back "unknown", which is the safe direction, and the same item
    cited in the reason is refused loudly by `resolve_evidence`, which does
    have the declaration to check against.
    """
    if not _is_mapping(item):
        raise ValueError("a test needs an evidence item, which is a mapping.")
    subject = _subject_of(item)
    if subject is None:
        raise ValueError(
            "a test names exactly one subject — `measure`, `fact`, `input`, "
            "`value`, or `label` with `unit` for something the strategy works "
            "out itself.")
    observation, problem = _observation(ctx, item, subject)
    if problem is not None:
        raise ValueError(f"this strategy tested {problem}")
    threshold, absent = _limit(ctx, item)
    outcome, problem = _outcome(observation, item.get("comparator"),
                                threshold, absent)
    if problem is not None:
        raise ValueError(f"{_cited_as(item)}: {problem}")
    return outcome


def resolve_evidence(record: dict, ctx: dict, items: list):
    """(rendered, errors) — every citation answered by the host.

    The strategy said what it looked at and what it wanted; this says what
    was there, whether it was absent and why, and how the comparison came
    out. The result is renderable with no further joins: a screen can write
    "Return on invested capital, 5-year median — 18.9%, at least your
    minimum of 15%" from one item.
    """
    rendered, errors = [], []
    for i, item in enumerate(items):
        where = f"evidence {i + 1}"
        subject = _subject_of(item) if _is_mapping(item) else None
        # Refused by validate_decision before this runs, and handled anyway:
        # this is also called straight from a screen, and a citation with no
        # subject must come back as a legible problem rather than as a raise
        # inside the code whose job is answering it.
        if subject is None:
            errors.append(f"{where} names no subject the host can answer.")
            continue

        if subject == "measure":
            entry = (ctx.get("measures") or {}).get(item["measure"]) or {}
            # Whether a figure is something the tool worked out or something
            # the user assessed is decided HERE, from the bank, and never by
            # the strategy citing it. Principle 5 says a captured judgement
            # is recorded as judgement and never disguised as a measurement;
            # a strategy that could choose the label could disguise it.
            meta = _bank_entry(item["measure"]) or {}
            judged = meta.get("kind") == "qualitative"
            if "since" in item:
                # A change is its own subject, not the measure with a note
                # attached. It has a different label, a different unit and a
                # different explanation, and the reader must never be able to
                # mistake "gross margin, 34%" for "gross margin, down 6
                # points" — the two render side by side on a re-underwrite
                # screen and the second is the one deciding something.
                anchor = BASELINE_ANCHORS.get(item["since"]) or {}
                form = _change_form(item)
                view = {"kind": "change", "id": item["measure"],
                        "label": f'{_bank_label(item["measure"])}, change '
                                 f'{anchor.get("label", "")}'.strip()
                                 + CHANGE_FORMS[form]["suffix"],
                        "unit": _change_unit(item["measure"], form),
                        "since": item["since"], "change": form,
                        "explain": _change_explain(item["measure"], anchor,
                                                   form)}
            else:
                view = {"kind": "judgement" if judged else "measure",
                        "id": item["measure"],
                        "label": _bank_label(item["measure"]),
                        "unit": _bank_unit(item["measure"]),
                        "explain": meta.get("question") if judged else None}
                if "at" in item:
                    view["at"] = item["at"]
                    view["cadence"] = _read(entry.get("series"), "cadence")
        elif subject == "fact":
            spec = HOST_FACTS.get(item["fact"])
            view = ({"kind": "fact", "id": item["fact"],
                     "label": spec["label"], "unit": spec["unit"],
                     "explain": spec["explain"]} if spec else None)
        elif subject == "label":
            view = {"kind": "stated", "id": None, "label": item["label"],
                    "unit": item["unit"], "explain": None}
        else:
            view, problem = _declared_observation(record, ctx, item, subject)
            if problem is not None:
                errors.append(f"{where} cites {problem}")

        observation, problem = _observation(ctx, item, subject)
        if problem is not None:
            errors.append(f"{where} cites {problem}")
        if view is None or observation is None:
            continue

        test_view = _test_view(record, ctx, item)
        outcome, problem = _outcome(
            observation, item.get("comparator"),
            test_view["threshold"] if test_view else None,
            test_view["absent"] if test_view else None)
        if problem is not None:
            errors.append(f"{where}: {problem}")
            continue
        rendered.append({"subject": view, "observed": observation,
                         "test": test_view, "outcome": outcome,
                         "group": item.get("group")})
    return rendered, errors


def resolve_groups(record: dict, ctx: dict, groups, rendered: list) -> list:
    """Every group with its rollup worked out from the rows under it.

    The count is the host's, not the strategy's. That is what lets "six of
    eight core tests passed" render from the same outcomes the eight rows
    render, instead of from a figure the strategy tallied separately and
    could tally wrongly — and it is what lets `evaluate` refuse a commit
    whose requirements are not met, because the host has an answer of its
    own to compare the state against.

    A group's own outcome uses the same four words a row does, and reaches
    them the same way. Unreadable rows are neither passes nor failures: a
    requirement six rows short of its bar with three rows unreadable has not
    failed, it is undecided, and saying otherwise would let absence read as
    a verdict in the one place a reader looks for the rollup.
    """
    by_group: dict = {}
    for row in rendered:
        if row.get("group"):
            by_group.setdefault(row["group"], []).append(row)

    out = []
    for g in groups or []:
        members = by_group.get(g.get("id"), [])
        tested = [r for r in members if r["test"] is not None]
        passed = sum(1 for r in tested if r["outcome"] == PASS)
        failed = sum(1 for r in tested if r["outcome"] == FAIL)
        unknown = sum(1 for r in tested if r["outcome"] == UNKNOWN)
        requires = g.get("requires", "all")

        view = {"id": g.get("id"), "name": g.get("name"),
                "requires": requires, "test": None,
                "members": len(members), "tested": len(tested),
                "passed": passed, "failed": failed, "unknown": unknown}

        if requires == "noted":
            view["outcome"] = NOTED
            out.append(view)
            continue
        if requires == "all":
            need, view["test"] = len(tested), None
        else:
            view["test"] = _test_view(record, ctx,
                                      {**g, "comparator": "at_least"})
            need = view["test"]["threshold"]
        if not isinstance(need, int) or isinstance(need, bool):
            view["outcome"] = UNKNOWN
        elif passed >= need:
            view["outcome"] = PASS
        elif passed + unknown < need:
            view["outcome"] = FAIL
        else:
            view["outcome"] = UNKNOWN
        out.append(view)
    return out


def _contradicted_commit(record, evidence, groups) -> list[str]:
    """Why a state that puts capital in cannot stand beside this evidence.

    The narrow half of the guarantee, and narrow by necessity. A hold may
    legitimately cite failures — that is often why it is a hold — and an
    exit rests on them by definition. It is `commit` alone that says capital
    may go in, and a commit sitting beside a requirement the host resolved
    as failed is the two halves of one decision disagreeing in public, with
    nothing on screen saying which to believe.

    How hard the check bites is exactly how much the strategy declared, and
    that asymmetry is deliberate.

    A group that states a requirement has to come out `pass`. Unreadable is
    not good enough there: the strategy said all four of these must pass, or
    six of these eight, and a figure nobody could compute has not met that
    demand — treating it as though it had is absence reading as success in
    the one place the reader looks for the rollup.

    A citation with a comparator and no group only has to not have *failed*.
    Nothing declared it a requirement, so the host refuses the outright
    contradiction and nothing more. A rule that reads "respect the reserve,
    if you keep one" honestly cites the reserve test on a buy and honestly
    reports the limit as unset, and refusing that would forbid a true thing
    in order to look strict.
    """
    problems = []
    for g in groups:
        if g["requires"] == "noted" or g["outcome"] == PASS:
            continue
        need = (f'all {g["tested"]}' if g["requires"] == "all"
                else (g["test"] or {}).get("threshold"))
        problems.append(
            f'"{g["name"]}" needed {need} of its {g["tested"]} tests to '
            f'pass and {g["passed"]} did'
            + (f' ({g["unknown"]} could not be worked out)'
               if g["unknown"] else "") + ".")
    for r in evidence:
        if not r.get("group") and r["outcome"] == FAIL:
            problems.append(
                f'"{r["subject"]["label"]}" came out failed and is not in a '
                "group saying it need not pass.")
    if not problems:
        return []
    return problems + [
        f'{record["name"]} put capital in against its own evidence. A '
        "citation the host resolved as failed or unreadable cannot sit "
        "beside a decision to buy — one of the two is wrong, and showing "
        "both would leave you to work out which."]


def _unanswerable_block(record, state, evidence) -> str | None:
    """Why a blocked verdict has nothing behind the way out it names.

    The evaluate-time half of "a blocked verdict cannot become a dead end".
    The declaration check already refused a blocked state that names no
    destination; this refuses one whose destination is built out of the
    decision's own citations and was handed none.

    Only one destination works that way, and it is the one an author reaches
    for first. The questions under "Your judgement" are exactly the ones the
    decision cited — that is the whole discovery mechanism for anything asked
    per security, because a question about one security cannot be declared on
    a setup screen before there is a security to ask it about. So a verdict
    that says "answer these three questions" and cites none of them renders a
    button leading to a section with nothing in it. That is a worse dead end
    than the first, because it looks like it worked.

    Naming the questions in `payload.needs` is not citing them. Prose is not
    a citation, the host cannot read it, and a convention that lives in one
    strategy's prose is not a guarantee — which is the whole reason this is
    a refusal and not a paragraph of documentation.
    """
    spec = STATE_FIXES.get(state.get("fix")) or {}
    kind = spec.get("cites")
    if kind is None:
        return None
    if any((r.get("subject") or {}).get("kind") == kind for r in evidence):
        return None
    return (f'{record["name"]} blocked on "{state["name"]}" and sent the '
            f'reader to {spec["where"]} without citing anything that is '
            f"asked there. That section is built from what this decision "
            f"cited, so it would be empty — the verdict would say something "
            f"is owed and the page would offer no way to give it. Cite what "
            f"is being waited on; naming it in `needs` puts it in a sentence "
            f"and nowhere else.")


_bank_cache: dict = {}
_bank_doc = None


def _bank_entry(measure_id):
    """Label, unit and kind for a bank measure. Read from the bank so a
    measure reads the same in a strategy's reason as it does anywhere else.

    Rebuilt when the bank itself changes — `bank.load_bank` caches on the
    file's mtime and hands back the same document until it moves, so an edit
    takes effect here too. A cache that outlived its source would report a
    measure's old label and, worse, its old kind: a judgement rendering as a
    measurement is the one thing this index must not get wrong.
    """
    global _bank_doc
    try:
        from . import bank
        doc = bank.load_bank()
    except Exception:  # noqa: BLE001 — rendering must not depend on it
        return _bank_cache.get(measure_id)
    if doc is not _bank_doc:
        _bank_doc = doc
        _bank_cache.clear()
        for e in (doc.get("entries") or []):
            _bank_cache[str(e.get("id"))] = {
                "label": str(e.get("label") or e.get("id")),
                "unit": str(e.get("unit") or "none"),
                "kind": str(e.get("kind") or ""),
                "question": str(e.get("question") or "").strip() or None,
                # Under `explanation`, where the bank keeps it — the same
                # sentence `bank.meta` hands the view as `plain`. Read from
                # the entry's own shape rather than from a flattened copy, so
                # there is one place the bank's layout is known.
                "plain": str((e.get("explanation") or {}).get("plain")
                             or "").strip() or None}
    return _bank_cache.get(measure_id)


def _bank_label(measure_id):
    entry = _bank_entry(measure_id)
    return entry["label"] if entry else measure_id


def _bank_unit(measure_id):
    entry = _bank_entry(measure_id)
    unit = entry["unit"] if entry else "none"
    return unit if unit in EVIDENCE_UNITS else "none"


def _change_unit(measure_id, form="distance"):
    """How a move between two readings renders.

    A distance in a percentage is not a percentage. Gross margin going from
    40% to 34% is six percentage points, and rendering that as "6%" invites
    the reader to take it for a relative move — which is a different number
    (fifteen percent of the original) pointing the same way, so the mistake
    survives a sanity check. Everything else keeps its own unit, because the
    distance between two ratios is a ratio and the distance between two
    dollar figures is dollars.

    A proportion is a percent whatever it was taken of, because it is no
    longer in the measure's units at all — it is the share of the old reading
    the move came to. That is the same distinction the paragraph above turns
    on, which is why the two forms must never share a unit: "-6" and "-15%"
    describing one decline is the whole point, and a screen that rendered
    both as "6" would make the two forms indistinguishable in the one place
    the difference decides something.
    """
    if form == "proportion":
        return "percent"
    unit = _bank_unit(measure_id)
    return "percentage_points" if unit == "percent" else unit


def _change_explain(measure_id, anchor, form="distance"):
    """What a change row means, how it is counted, and what the thing
    changing is. All three, because a reader who has never valued a company
    needs the last before the first two are worth anything — and the bank's
    account of the measure is the only place any of them is written down
    once."""
    entry = _bank_entry(measure_id) or {}
    parts = [anchor.get("explain"), (CHANGE_FORMS.get(form) or {}).get(
        "explain") if form != "distance" else None, entry.get("plain")]
    return "\n\n".join(p for p in parts if p) or None


# ---------------------------------------------------------------------------
# evaluation — one call, one state, contained failures
# ---------------------------------------------------------------------------

def _strategy_ref(record: dict | None) -> dict | None:
    if record is None:
        return None
    return {"id": record["id"], "name": record["name"],
            "version": record["version"],
            "values_version": record.get("values_version"),
            "contract": record["contract"]}


def _result(state_id, state, payload, reason, produced_by, record):
    render = state["render"]
    return {
        "render": render,
        "tier": RENDER_TYPES[render]["tier"],
        # `fix` names one of STATE_FIXES, or is None where nothing in the app
        # resolves the state. Both sides fill it the same way — a strategy
        # declares one on every blocked state it has, the host carries one on
        # its own — so the view renders a way out without ever knowing whose
        # state it is looking at.
        "state": {"id": state_id, "name": state["name"],
                  "description": state["description"],
                  "fix": state.get("fix")},
        "payload": payload,
        "reason": reason,
        "produced_by": produced_by,
        "strategy": _strategy_ref(record),
    }


def host_result(state_id: str, summary: str, record: dict | None = None,
                needs: list[str] | None = None,
                evidence: list | None = None) -> dict:
    """A result the host produces itself when no strategy verdict exists —
    missing inputs, a missing strategy, a failure. Same envelope as a
    strategy's decision, so one screen renders both, but produced_by says
    which side is speaking and the reason never pretends to be a verdict."""
    state = HOST_STATES[state_id]
    payload = ({"needs": list(needs) if needs else [summary]}
               if state["render"] == "blocked" else {})
    reason = {"rule": state_id, "summary": summary,
              "evidence": list(evidence or []), "groups": [], "note": None}
    return _result(state_id, state, payload, reason, "host", record)


def _frozen(node):
    """A read-only view of plain data, all the way down.

    Mappings become read-only proxies and lists become tuples, both of which
    read exactly as the originals do — `.get`, `in`, indexing, slicing,
    iteration, `len` — and neither of which can be written to. Anything else
    is a scalar and already immutable.

    This is what a strategy is handed. It is not defence against a hostile
    plugin, which shares this process and could do as it liked; it is what
    makes "the host owns the answer" true rather than merely intended. A
    figure a strategy could edit is a figure it could quote back differently
    from the one the screen renders.
    """
    if _is_mapping(node):
        return MappingProxyType({k: _frozen(v) for k, v in node.items()})
    if isinstance(node, list):
        return tuple(_frozen(v) for v in node)
    return node


def _failure_location(exc: BaseException, bundle_dir: str) -> str | None:
    """Where inside the strategy's own bundle the failure happened —
    "strategy.py line 12" — never a full path, never a stack trace."""
    try:
        frames = traceback.extract_tb(exc.__traceback__)
        inside = [f for f in frames
                  if str(f.filename).startswith(str(bundle_dir))]
        if inside:
            f = inside[-1]
            name = f.filename.rsplit("/", 1)[-1]
            return f"{name} line {f.lineno}"
    except Exception:  # noqa: BLE001 — locating a crash must never crash
        pass
    return None


def evaluate(record: dict, ctx: dict) -> dict:
    """Ask a loaded strategy for its one decision about one security.

    Never raises. Every way this can fail — inputs not yet supplied, the
    strategy's logic throwing, a decision outside the contract — comes back
    as a host-produced result in the same envelope: an error in place, not
    a crashed application, and never a blocked recording.
    """
    _, problems = check_inputs(record, ctx.get("inputs") or {},
                               ctx.get("values") or {})
    if problems:
        return host_result(
            "host:inputs-missing",
            f'{record["name"]} needs information before it can produce a '
            "verdict.", record, needs=problems)

    # Reference data the bundle ships travels with the context rather than
    # being read off disk inside decide(): a strategy reaches nothing, not
    # even its own files, once it is running. Always present, so reading it
    # is never a surprise; frozen, so one evaluation cannot change what the
    # next one sees.
    reference = record.get("reference") or _NO_REFERENCE
    ctx = {**ctx, "reference": reference}

    # The strategy decides against a frozen view, and the host resolves the
    # citations below against the original. It used to be a deep copy, which
    # stopped a strategy corrupting the host's caches but not much else. A
    # frozen view is the stronger version of the same promise and the cheaper
    # one: nothing to copy, and the wrong thing is refused rather than
    # allowed and then ignored.
    #
    # What that buys, now that a strategy can ask the host how a comparison
    # came out: `test` and the resolution below read the same figures, so
    # they cannot disagree. Against a mutable copy they could — a strategy
    # that edited its own context would be told one thing while the screen
    # was told another, which is the exact divergence v5 exists to close, one
    # level further down than the private comparators that made it visible.
    mine = MappingProxyType(
        {**{k: _frozen(v) for k, v in ctx.items() if k != "reference"},
         "reference": reference})

    try:
        decision = record["decide"](mine)
    # BaseException, not Exception: a strategy calling sys.exit() must be
    # contained exactly like one raising — the host does not let plugin code
    # decide the application ends.
    except BaseException as e:  # noqa: BLE001 — a plugin must not sink the host
        where = _failure_location(e, record.get("dir", ""))
        at = f" (at {where})" if where else ""
        return host_result(
            "host:strategy-error",
            f'{record["name"]} failed while deciding: '
            f"{type(e).__name__}: {e}{at}. Your data and journal are "
            "untouched.", record)

    try:
        issues = validate_decision(record, decision)
    except Exception as e:  # noqa: BLE001 — checking must not raise either
        issues = [f"the decision could not even be checked "
                  f"({type(e).__name__}: {e})."]
    if issues:
        return host_result(
            "host:invalid-decision",
            f'{record["name"]} returned a decision outside the contract: '
            + " ".join(issues), record)

    try:
        evidence, issues = resolve_evidence(
            record, ctx, decision["reason"]["evidence"])
    except Exception as e:  # noqa: BLE001 — answering must not raise either
        evidence, issues = [], [f"the evidence could not be resolved "
                                f"({type(e).__name__}: {e})."]
    if issues:
        return host_result(
            "host:invalid-decision",
            f'{record["name"]} cited evidence the host cannot answer: '
            + " ".join(issues), record)

    state = next(s for s in record["states"] if s["id"] == decision["state"])
    try:
        groups = resolve_groups(record, ctx,
                                decision["reason"].get("groups") or [],
                                evidence)
    except Exception as e:  # noqa: BLE001 — rolling up must not raise either
        return host_result(
            "host:invalid-decision",
            f'{record["name"]} declared evidence groups the host could not '
            f"roll up ({type(e).__name__}: {e}).", record)

    # The two places the host compares a strategy's conclusion against its
    # own arithmetic. Everything else here checks shape; these check that the
    # decision and the evidence say the same thing — a commit that its own
    # citations contradict, and a block whose way out its own citations do
    # not open.
    if state["render"] == "commit":
        contradictions = _contradicted_commit(record, evidence, groups)
        if contradictions:
            return host_result("host:invalid-decision",
                               " ".join(contradictions), record)
    elif state["render"] == "blocked":
        dead_end = _unanswerable_block(record, state, evidence)
        if dead_end:
            return host_result("host:invalid-decision", dead_end, record)

    reason = {"rule": decision["reason"]["rule"],
              "summary": decision["reason"]["summary"],
              "evidence": evidence,
              "groups": groups,
              "note": decision["reason"].get("note")}
    return _result(decision["state"], state, decision["payload"],
                   reason, "strategy", record)
