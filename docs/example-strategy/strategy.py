"""A worked example. Not a strategy, and never load it as one.

`strategies/proof/` proves the boundary carries data. This proves the three
things that actually cost time when writing a real one, and it exists to be
copied and cut down rather than read straight through:

  1. **A two-tier rollup.** Some tests every one of which must pass, and some
     where a count is enough — with the count read out of a declared setting
     rather than written into the logic.
  2. **A confirmed exit.** A rule that does not fire on one bad reading —
     asked of the host, which knows how the measure is read and therefore
     how much evidence a breach of it needs. This file states no number of
     filings and declares no setting for one, because it has no way to know
     whether the measure it exits on is a balance-sheet date, a trailing
     twelve months or a five-year median, and those need different things.
  3. **A judgement with a blocked branch.** A question no filing answers,
     cited like any other measure, with a state that stops and says where
     the answer is given.
  4. **A declared refusal.** The kinds of company these rules will not
     evaluate, said in the declaration rather than branched on inside
     `decide`, so the host can answer for them before any logic runs.

Everything in it is invented, including every company it would ever look at
and every number in values.yaml. It is not a claim about investing and no
journal should be created against it — which is why the bundle does not live
in `strategies/` and is not discovered. Copy the directory in there to watch
it run, and take it out again afterwards.

Read `docs/WRITING-A-STRATEGY.md` beside it. The reference explains what each
piece is; this shows the pieces fitted together.
"""

from engine import contract

# The words the host uses for how a comparison came out. Imported rather than
# spelled out, so a bundle cannot drift from the host's own vocabulary.
PASS, FAIL, UNKNOWN = contract.PASS, contract.FAIL, contract.UNKNOWN

# Where every number in this bundle came from. There is no outside source for
# figures somebody made up to demonstrate a mechanism, and saying so is the
# honest answer rather than an omission — the field exists to make exactly
# this case visible.
INVENTED = {"name": "invented for this worked example. It is a demonstration "
                    "of how a rule is written, not a view about what any "
                    "company is worth, and nothing here is a recommendation",
            "reasoning": True}


STRATEGY = {
    "id": "worked-example",
    "name": "Worked example",
    "summary": "A demonstration bundle: two tiers of entry test, one exit "
               "that has to hold across consecutive filings, and one "
               "question only you can answer. Every number in it is "
               "invented and it is not investment logic.",
    "version": 2,
    "contract": 6,
    "changelog": {
        1: "First version. Two knockouts and three core tests of which some "
           "number must pass, one exit on interest coverage confirmed across "
           "consecutive filings, and the moat question blocking a purchase "
           "until it is answered.",
        2: "Declines the three kinds of company whose accounts the measures "
           "it reads were not built for, so the fourth mechanism worth "
           "demonstrating is demonstrated. No threshold moved.",
    },

    # -----------------------------------------------------------------
    # The kinds of company these rules will not evaluate.
    #
    # Demonstrated here because it is the one part of a declaration whose
    # absence is invisible: a bundle with no `declines` looks exactly like a
    # bundle whose author never considered the question, and the second is
    # much commoner than the first.
    #
    # The reason it is declared rather than checked at the top of `decide`
    # is worth sitting with. A branch is invisible from outside the bundle,
    # so the screen offering this strategy could not say what it covers, and
    # a journal could not be warned before it was stamped. A declaration is
    # readable without running anything — the same reason inputs and values
    # are declared — and the host refuses a declined company before `decide`
    # is called at all, so the boundary cannot be lost to a later edit that
    # adds a branch above the check.
    #
    # `because` is the strategy's own sentence and is required. What a reader
    # needs is the reason THIS rule set has nothing to say, and only the
    # author has that; "not supported" would be the host guessing.
    # -----------------------------------------------------------------
    "declines": [
        {"class": "depository-lending",
         "because": "Every test here reads a company that sells something. A "
                    "lender's cash from operations moves with the period's "
                    "change in loans and deposits rather than with the "
                    "business, and it does not divide its balance sheet into "
                    "what falls due within the year and what does not — so "
                    "these tests do not read a lender roughly, they read "
                    "something else entirely."},
        {"class": "insurance",
         "because": "Premiums arrive before claims are paid, so cash from "
                    "operations carries money the company is holding rather "
                    "than money it earned, and the investment portfolio "
                    "behind it belongs to policyholders. The returns and "
                    "coverage tests here would be measuring the wrong "
                    "capital."},
        {"class": "real-estate",
         "because": "Depreciation on buildings is an accounting convention "
                    "rather than a cost, so reported profit understates by "
                    "design and every test here built on it reads a company "
                    "as worse than it is."},
    ],

    # -----------------------------------------------------------------
    # Eight states. Every branch below reaches exactly one of them, and
    # every one of them is something a reader has to be able to tell apart
    # from the others: "your own rules said no" is not "your rules could
    # not be run", and "it crossed the line once" is not "it has stayed
    # across it".
    # -----------------------------------------------------------------
    "states": [
        {"id": "worth-buying", "render": "commit",
         "name": "Worth buying",
         "description": "Both tests this example will not bend have passed, "
                        "enough of the rest have, and you have assessed the "
                        "moat as intact. The size is the largest share of "
                        "the account it allows one position."},

        {"id": "not-good-enough", "render": "hold",
         "name": "Not good enough",
         "description": "Either a test this example will not bend came back "
                        "against the company, or too few of the rest passed "
                        "for the count it needs to be reachable. Nothing is "
                        "bought and nothing is held against you for it — "
                        "most companies fail most screens."},

        {"id": "assessment-owed", "render": "blocked",
         # The one state here that stops rather than answers, so it is the
         # one obliged to say where it is un-stopped. Both halves of that
         # obligation are enforced: the host refuses this declaration if
         # `fix` is missing, and refuses a decision reaching this state
         # without citing a question the "Your judgement" section will ask.
         # Prose telling the reader to scroll is not a way out.
         "fix": "judgement",
         "name": "A question only you can answer",
         "description": "The numbers pass. What decides it now is whether "
                        "the business can keep competitors out for years, "
                        "and no filing says. That is yours to answer, in "
                        "your own words, under \"Your judgement\" on this "
                        "page.\n\n"
                        "Leaving it blank is not a fail and is not held "
                        "against the company. It is simply not an answer, "
                        "and this example will not put money behind a "
                        "question nobody asked."},

        {"id": "you-marked-it-down", "render": "hold",
         "name": "You said no to it",
         "description": "The numbers pass and your own assessment does not. "
                        "Nothing here argues with that. If you have changed "
                        "your mind, reassess it — the record keeps both "
                        "answers and the day each was written."},

        {"id": "exit-confirmed", "render": "close",
         "name": "Sell it",
         "description": "Interest coverage has been under the level this "
                        "example exits on for as many consecutive filings as "
                        "it asks for. One bad quarter would not have done "
                        "this, which is the whole point of counting them."},

        {"id": "breach-unconfirmed", "render": "hold",
         "name": "Crossed, not confirmed",
         "description": "Interest coverage is under the level this example "
                        "exits on, but not yet on enough filings in a row "
                        "for it to act. Nothing is sold on one reading.\n\n"
                        "This is the state that costs the most to sit in, "
                        "and it is deliberate: a rule that fires on a single "
                        "quarter fires on noise, and a rule that never fires "
                        "is not a rule."},

        {"id": "nothing-to-do", "render": "hold",
         "name": "Nothing to do",
         "description": "You hold it and the exit test came back clear. "
                        "Sitting still is the whole activity."},

        {"id": "cannot-say", "render": "unknown",
         "name": "Not enough to go on",
         "description": "Too much of what decides this could not be worked "
                        "out from the data on record, so there is no honest "
                        "answer either way. Fetching data usually fixes it; "
                        "a figure that stays absent is one this journal "
                        "genuinely cannot compute for this company."},
    ],

    # One input, and it is here to show the line rather than because this
    # example needs much from it. The test is two-sided and either side makes
    # something a value: can the strategy ship a sensible default, and does
    # changing it move where a bar sits? Nobody can ship a default for
    # somebody's cash balance and moving it moves no bar, so it is an input.
    # Every number below it fails the first half and passes the second.
    "inputs": [
        {"id": "free-cash", "label": "Free cash", "type": "number",
         "unit": "usd", "role": "cash", "required": False,
         # The role is the whole reason this is worth declaring. The host has
         # no cash field of its own and never will — deciding that a journal
         # must record cash would be the host deciding how strategies work —
         # so an input says what the number IS, and the host then reports the
         # account value and every position weight built on it.
         "explain": "Money in the account this journal covers that is not in "
                    "any position. The journal adds it to what your holdings "
                    "are worth to get the account total, and reports each "
                    "position as a share of that. Leave it blank and those "
                    "figures say they cannot be worked out rather than "
                    "guessing at them."},
    ],

    "values": [
        # -- the two knockouts ----------------------------------------
        {"id": "min-roic", "label": "Lowest return on capital it will take",
         "type": "number", "unit": "percent", "min": 0, "max": 100,
         "source": INVENTED,
         "explain": "How much profit the business makes on the money tied up "
                    "in it, as a percentage, taken as the middle of the last "
                    "five years so one good year cannot carry it. A business "
                    "below this line is one this example refuses outright "
                    "rather than scoring against the rest."},
        {"id": "max-debt-to-ebitda", "label": "Most debt it will take",
         "type": "number", "unit": "times", "min": 0, "max": 20,
         "source": INVENTED,
         "explain": "Total borrowings measured in years of the company's own "
                    "rough operating cash flow. Two means it could repay "
                    "everything it owes in about two such years. Above this "
                    "line the company is refused outright: a good business "
                    "with too much borrowed against it is a different risk "
                    "from a mediocre one, and no other test here notices it."},

        # -- the count the second tier rolls up to ---------------------
        {"id": "core-tests-required",
         "label": "How many core tests must pass",
         "type": "integer", "unit": "count", "min": 0, "max": 3,
         "source": INVENTED,
         "explain": "How many of the three core tests below have to come "
                    "back a pass before this example will buy. It is a count "
                    "rather than a demand that all of them pass, because a "
                    "company clearing every single test is rare enough that "
                    "insisting on it means never buying anything.\n\n"
                    "The host counts the passes itself from the rows it "
                    "resolved, so the heading's \"2 of 3\" and the rows under "
                    "it can never disagree."},

        # -- the three core tests --------------------------------------
        {"id": "min-current-ratio", "label": "Lowest current ratio",
         "type": "number", "unit": "ratio", "min": 0, "max": 10,
         "source": INVENTED,
         "explain": "What the company can turn into cash within a year, "
                    "divided by what it owes within a year. Below 1 it "
                    "cannot cover the next twelve months out of what it "
                    "already has, and has to borrow or sell something."},
        {"id": "min-fcf-margin",
         "label": "Lowest free cash flow margin", "type": "number",
         "unit": "percent", "min": -100, "max": 100, "source": INVENTED,
         "explain": "Of every hundred pounds of sales, how many are left as "
                    "cash after paying for everything including the "
                    "equipment the business had to buy. Profit is an "
                    "opinion in a way cash is not, which is why this is "
                    "here and an earnings margin is not."},
        {"id": "min-interest-coverage", "label": "Lowest interest coverage",
         "type": "number", "unit": "times", "min": 0, "max": 100,
         "source": INVENTED,
         "explain": "How many times over the company's operating profit "
                    "covers its interest bill. At 8 it could lose seven "
                    "eighths of its profit and still pay the bank. It is "
                    "the same measure the exit below watches, at a stricter "
                    "level — what it takes to be bought is not what it takes "
                    "to be kept, and one number cannot say both."},

        # -- the exit, and what confirms it ----------------------------
        {"id": "exit-interest-coverage",
         "label": "Interest coverage that ends the position",
         "type": "number", "unit": "times", "min": 0, "max": 100,
         "source": INVENTED,
         "explain": "The level of interest cover this example will not hold "
                    "a company below. It sits well under what it takes to "
                    "buy one, deliberately: a business that has slipped from "
                    "comfortable to merely adequate is not a business in "
                    "trouble, and selling on that is selling on noise."},
        # -- how much goes in ------------------------------------------
        {"id": "position-weight-cap",
         "label": "Largest a position may get", "type": "number",
         "unit": "percent", "min": 0.1, "max": 100, "source": INVENTED,
         "explain": "The most of the account this example will put into any "
                    "one name, as a percentage. It is an opinion about "
                    "concentration — which is exactly why it ships a default "
                    "instead of being asked for."},
    ],
}


# ---------------------------------------------------------------------------
# The headings, and what each demands of the rows under it.
#
# The grouping IS the rollup. Two tests where every one has to pass and three
# where a count is enough is the whole shape of the entry rule, and the host
# counts it from the rows it resolved rather than from a tally kept here.
#
# `all` and `at_least` are load-bearing rather than decorative: a state whose
# render is `commit` is refused by the host when a group it declared did not
# come out passed, and an unreadable row is not good enough there either. The
# branches below reach a state that explains itself first — but if one of them
# ever stops, the wrong verdict is unrepresentable rather than merely unlikely.
# ---------------------------------------------------------------------------

KNOCKOUTS = {"id": "knockouts", "name": "Tests this example will not bend",
             "requires": "all"}
CORE = {"id": "core", "name": "Core tests", "requires": "at_least",
        # Named, never restated. The host reads the number out of the setting,
        # so the heading cannot claim a bar the settings do not hold.
        "threshold_from": "core-tests-required"}
ASSESSED = {"id": "assessed", "name": "What only you can answer",
            "requires": "all"}

# `noted`, because what ends a position here is a run of filings and the host
# cannot express a run. It reports how each reading came out and this file
# decides what a sequence of them means. A group claiming `all` would refuse
# every hold on a position that had crossed the line once, which is the state
# this strategy most needs to be able to sit in.
EXITS = {"id": "exits", "name": "What would end this position",
         "requires": "noted"}

# Reported and never tested. Neither figure under it decides anything here;
# they are on the screen because a reader looking at a verdict of "nothing to
# do" wants to know how much of their money is in it and how long it has been
# there. A `noted` heading is how a strategy shows a figure without pretending
# it is a requirement.
HOLDING = {"id": "holding", "name": "The holding itself", "requires": "noted"}


# ---------------------------------------------------------------------------
# The tests, as data. Which measure, which direction, and the id of the
# setting the host reads the limit out of — never a number.
#
# Every one is written as what the company must KEEP BEING, not as what would
# disqualify it. That is not a style preference and it is the mistake that
# costs an afternoon: cite an exit in the direction it fires — "coverage below
# 4" — and a perfectly healthy holding renders as a page of failed rows beside
# a verdict of hold, because the host resolved "is it below 4" as false. Write
# the same rule as "coverage at least 4" and the same holding renders as
# passes, the exit is that test failing, and the screen says what you meant.
# ---------------------------------------------------------------------------

KNOCKOUT_TESTS = (
    ("roic_median_5y", "at_least", "min-roic"),
    ("total_debt_to_ebitda", "at_most", "max-debt-to-ebitda"),
)

CORE_TESTS = (
    ("current_ratio", "at_least", "min-current-ratio"),
    ("fcf_margin_ttm", "at_least", "min-fcf-margin"),
    ("interest_coverage", "at_least", "min-interest-coverage"),
)

# One exit, one measure. What the holding must keep being true.
EXIT = ("interest_coverage", "at_least", "exit-interest-coverage")

# The question no filing answers. Cited exactly as a measure is, because to
# the host that is what it is — and the host decides from the bank that it is
# a judgement rather than a measurement, so this file could not present an
# opinion as something the tool computed even if it wanted to.
MOAT = "moat_durability"


def _cite(measure_id, comparator, value_id, group, at=None):
    """One citation. Nothing in it is a figure."""
    item = {"measure": measure_id, "comparator": comparator,
            "threshold_from": value_id, "group": group}
    if at is not None:
        item["at"] = at
    return item


def _screen(ctx, rows, group):
    """(citations, outcomes) for one family of tests.

    The item that is tested is the item that is cited — the same dict, asked
    once. There is no second comparison here to disagree with the first, and
    that is the arrangement worth copying: `contract.test` is the host
    answering the question it will answer again when the row reaches the
    screen, out of the same context, through the same code.
    """
    cites = [_cite(m, c, v, group) for m, c, v in rows]
    return cites, [contract.test(ctx, item) for item in cites]


def _moat_cite(group):
    return {"measure": MOAT, "comparator": "equals", "threshold": True,
            "group": group}


# ---------------------------------------------------------------------------
# a security you do not own
# ---------------------------------------------------------------------------

def _entry(ctx):
    """The five entry tests and what the host made of each, as one object.

    Returned together because every caller wants the same three questions
    answered — did a knockout fail, can the count still be reached, and what
    should be cited — and answering them in one place is what keeps the
    ladder below readable.
    """
    need = (ctx.get("values") or {}).get("core-tests-required")
    knock_cites, knock_out = _screen(ctx, KNOCKOUT_TESTS, KNOCKOUTS["id"])
    core_cites, core_out = _screen(ctx, CORE_TESTS, CORE["id"])
    passed, unreadable = core_out.count(PASS), core_out.count(UNKNOWN)
    return {
        "need": need,
        "knocked_out": knock_out.count(FAIL),
        "knock_unreadable": knock_out.count(UNKNOWN),
        "passed": passed,
        "unreadable": unreadable,
        # A settled no: something it will not bend on failed, or the count
        # cannot be reached even if every unreadable test came back a pass.
        "settled_no": (knock_out.count(FAIL) > 0
                       or (isinstance(need, int)
                           and passed + unreadable < need)),
        # Met, and note what it is NOT: "no knockout failed". An unreadable
        # knockout has not shown the company is sound, and absence walking
        # through a gate by failing to trip it is the quietest bug on this
        # list. The host would refuse the commit anyway — that is what the
        # `all` on the group is for — but a refusal the reader sees as
        # "the strategy returned something outside the contract" teaches
        # nobody anything, so the ladder asks first and explains itself.
        "met": (knock_out.count(UNKNOWN) == 0 and isinstance(need, int)
                and passed >= need),
        "evidence": knock_cites + core_cites,
        "groups": [KNOCKOUTS, CORE],
    }


def _on_a_candidate(ctx):
    """The ladder. One rung, one state, and the order is the whole design.

    Every branch that is NOT a commit is reached first, and that is not
    tidiness. A commit standing beside a group the host resolved as anything
    other than passed is refused outright — so a strategy that reaches for
    the buy first and hopes the tests were fine produces `host:invalid-
    decision`, which tells the reader nothing about the company. Reaching the
    explaining state first is how the same fact arrives as a sentence.
    """
    screen = _entry(ctx)

    if screen["settled_no"]:
        return {
            "state": "not-good-enough", "payload": {},
            "reason": {
                "rule": ("knockout-failed" if screen["knocked_out"]
                         else "core-tests-short"),
                "summary": (
                    f'{screen["knocked_out"]} of the '
                    f"{len(KNOCKOUT_TESTS)} tests this example will not bend "
                    "came back against it, and one is enough."
                    if screen["knocked_out"] else
                    f'Only {screen["passed"]} of the {len(CORE_TESTS)} core '
                    f'tests passed and {screen["unreadable"]} could not be '
                    f'worked out, so {screen["need"]} is out of reach.'),
                "evidence": screen["evidence"], "groups": screen["groups"]},
        }

    if not screen["met"]:
        missing = screen["knock_unreadable"] + screen["unreadable"]
        return {
            "state": "cannot-say", "payload": {},
            "reason": {
                "rule": "screen-incomplete",
                "summary": (
                    f"{missing} of the tests that decide this could not be "
                    "worked out from the data on record, and the ones that "
                    "could do not settle it either way."),
                "evidence": screen["evidence"], "groups": screen["groups"]},
        }

    # The numbers pass. What is left is the part no filing answers — and
    # citing it is what puts the question on this page with a way to answer
    # it. Deliberately not cited above: nobody should be asked to assess the
    # durability of a business their own rules have already rejected.
    moat = _moat_cite(ASSESSED["id"])
    evidence = screen["evidence"] + [moat]
    groups = screen["groups"] + [ASSESSED]
    outcome = contract.test(ctx, moat)

    if outcome == UNKNOWN:
        return {
            "state": "assessment-owed",
            # `needs` is the sentence a reader gets. It is not the way out —
            # the way out is `fix` on the state above, plus the citation just
            # added, and the host refuses this verdict without both.
            "payload": {"needs": [
                "Assess whether this business can keep competitors out for "
                "years, and write down why you think so.",
                "Leaving it unanswered is not a fail and is not held against "
                "the company. It simply is not an answer, and this example "
                "will not put money behind a question nobody asked."]},
            "reason": {
                "rule": "moat-unanswered",
                "summary": (
                    f'Every number this example checks is in order — '
                    f'{screen["passed"]} of {len(CORE_TESTS)} core tests and '
                    f"both it will not bend. What decides it now is a "
                    "question no filing can answer, and only you can."),
                "evidence": evidence, "groups": groups},
        }

    if outcome == FAIL:
        return {
            "state": "you-marked-it-down", "payload": {},
            "reason": {
                "rule": "you-said-the-moat-is-gone",
                "summary": "The numbers pass and your own assessment does "
                           "not. Your reasoning is on the record beside it.",
                "evidence": evidence, "groups": groups},
        }

    cap = float((ctx.get("values") or {})["position-weight-cap"])
    return {
        "state": "worth-buying",
        "payload": {"size": {"unit": "weight", "value": cap},
                    # None is "buy it now, unconditionally". A condition is a
                    # sentence the host renders and never evaluates — this
                    # example re-runs every day, so anything it would wait for
                    # is better expressed as a rule that has not passed yet.
                    "condition": None},
        "reason": {
            "rule": "screened-and-assessed",
            "summary": (
                f'Both tests this example will not bend passed, '
                f'{screen["passed"]} of the {len(CORE_TESTS)} core tests '
                f'passed against the {screen["need"]} it asks for, and you '
                f"have assessed the moat as intact."),
            "evidence": evidence, "groups": groups},
    }


# ---------------------------------------------------------------------------
# a security you hold
# ---------------------------------------------------------------------------

def _on_a_holding(ctx):
    """One exit, asked once, and the three ways it can answer."""
    measure_id, comparator, value_id = EXIT
    live = _cite(measure_id, comparator, value_id, EXITS["id"])
    # Reported, never tested. The weight comes from the `cash` role on the
    # declared input and says so itself where the question was never
    # answered; the months come from two dates the host already owns, so a
    # strategy with a clock in it never writes month arithmetic of its own.
    holding = [{"fact": "position.weight", "group": HOLDING["id"]},
               {"fact": "position.months_held", "group": HOLDING["id"]}]
    groups = [EXITS, HOLDING]
    outcome = contract.test(ctx, live)

    if outcome == UNKNOWN:
        return {
            "state": "cannot-say", "payload": {},
            "reason": {
                "rule": "exit-unreadable",
                "summary": "Whether this company still covers its interest "
                           "could not be worked out from the data on record, "
                           "so nothing here can say the position is sound or "
                           "that it is not.",
                "evidence": [live] + holding, "groups": groups},
        }

    if outcome == PASS:
        return {
            "state": "nothing-to-do", "payload": {},
            "reason": {
                "rule": "exit-clear",
                "summary": "The one thing this example sells on has not "
                           "happened. Sitting still is the whole activity.",
                "evidence": [live] + holding, "groups": groups},
        }

    # The host answers this, not the walk this file used to carry. It knows
    # from the metric bank that interest coverage is a trailing twelve
    # months, so a second filing genuinely rolls a quarter and tells you
    # something; had this exit been written on a five-year median it would
    # act on the first reading instead, because a second one would share
    # four of the same five years.
    #
    # Worth knowing before you rely on it: the run is counted over FILINGS.
    # A figure typed in by hand answers `current` and adds no filing, so on
    # a security with nothing fetched an exit needing two of them can never
    # fire. That is honest — nobody observed a second reading — and it is
    # invisible until an exit quietly never fires. Where a measure needs no
    # confirmation at all this does not arise, which is one more reason not
    # to state a number of filings by hand.
    found = contract.confirm(ctx, live)
    # The confirming readings are cited, not summarised. Citing them is what
    # lets a reader check the rule against the filings instead of taking
    # this file's word for it.
    confirming = [_cite(measure_id, comparator, value_id, EXITS["id"],
                        at=period) for period in found["periods"]]
    evidence = [live] + confirming + holding

    if found["confirmation"] == contract.CONFIRMED:
        return {
            "state": "exit-confirmed",
            # The day the exit is due. A close with no date makes a scheduled
            # exit fire months early, so the host insists on one — and the
            # honest answer for an exit that has already confirmed is today.
            "payload": {"when": ctx["today"]},
            "reason": {
                "rule": "coverage-exit-confirmed",
                "summary": (
                    "Interest coverage is under the level this example exits "
                    "on, and that is established rather than glimpsed: "
                    + found["why"] + "."),
                "evidence": evidence, "groups": groups},
        }

    return {
        "state": "breach-unconfirmed", "payload": {},
        "reason": {
            "rule": "breach-awaiting-confirmation",
            "summary": (
                "Interest coverage is under the level this example exits on, "
                "and that is not enough on its own: " + found["why"]
                + ". Nothing is sold on a reading that has not been "
                  "confirmed."),
            "evidence": evidence, "groups": groups},
    }


def decide(ctx):
    """One evaluation, one state.

    The first fork is whether the security is held, because owning it and
    considering it are different questions rather than two systems that each
    reach a conclusion. Below the fork each side is a single ladder, so no
    two states can ever both be true.
    """
    if (ctx.get("position") or {}).get("held"):
        return _on_a_holding(ctx)
    return _on_a_candidate(ctx)
