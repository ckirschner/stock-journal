"""Magic Formula — the half of Greenblatt's method that is a journal.

The fourth of four, and the first that does not screen. That is not a
simplification of the other three; it is the shape of the method.

**The method splits in two and only half of it belongs here.** Stage one ranks
a universe on two figures — what the business earns against what the whole
thing costs, and what it earns against the capital it needs to earn it — and
returns the best thirty or fifty names. That is a screener. It needs a
universe of three thousand companies this program does not have and will not
get, and Greenblatt gives it away free at magicformulainvesting.com. Stage two
is what you do with the list, and stage two is exactly a journal: buy a few
names at a time so the whole portfolio does not rest on one entry point, hold
each about a year, sell, refresh the list, replace.

**So there is almost no buy logic here, and that is the point.** Every other
strategy in this program answers *should I buy this*. This one answers *is it
time*. The list is the decision — the ranking already happened at Greenblatt's
end, against companies this journal has never heard of — and the journal never
says don't buy this one, because second-guessing the list is the deviation the
method exists to prevent. What it says instead is: not yet, or not any more.

Six things follow, and they are the shape of this file.

**The only exit is a clock.** Graham has one as the looser half of a pair;
Buffett and Lynch have none, and both say in as many words that nothing closes
a position for having been owned a long time. Here it is the whole exit rule.
Nothing about the business can end a position, because nothing about the
business began it: the two figures below are computed and shown and gate
nothing, and a rule that sold on one of them would be a rule this method does
not have.

**A name that comes back on a later list is held, and its year starts again.**
Greenblatt does not address this directly, so it is a design call, and the
alternative is worse in three ways at once. Without a reset the only other
answer is to sell — hold-with-an-expired-clock is not a state this method has
— and selling to buy the same name back is the same economic position, a new
lot with a new year on it anyway, having paid a spread to get there. In a
taxable account it is also a wash sale, so the loss it realises is disallowed.
The clock therefore runs from the later of the day you bought and the day the
freshest list carrying the name was pulled. See `back-on-the-list`.

**Buying is staged and the staging is a rule.** Five to seven names every
couple of months until the target is reached, which lands the whole portfolio
across four or five entry points rather than one. Buying the list in one go is
the most common way people break this, so it is expressed as a limit on how
many names may be *started* inside a window rather than as a date — a limit on
dates would also block the replacement you buy the day after a position is
sold, which is the same rule doing the opposite of what it is for.

**It sells on a date and it will not tell you which date is best for you.**
Greenblatt's own refinement is to sell a loser a few days before the one-year
mark and a winner a few days after. Knowing which you are requires knowing
what you paid, and nothing in this program hands a rule the cost of a
position — the same refusal that makes it impossible for any strategy here to
tell you to average down. So the date shown is the anniversary itself, the few
days either side are yours, and `time-is-up` says which way to lean. This is
the second timing rule from a mechanical school to hit that wall; Graham's
sell-at-fifty-percent leg was the first.

**Earnings yield and return on capital are shown and gate nothing.** They are
here so the page can say why a name was on a list — which is a fact about
Greenblatt's arithmetic, not about a test this journal ran. What cannot be
shown is where the name ranked, because a rank is a statement about the two
thousand nine hundred and seventy companies that did not make the list and
none of those are in this journal. Saying so is the honest version; implying
the tool selected anything is not.

**It does not evaluate lenders, insurers or property companies.** His own
database excludes financials, and this journal declines the three kinds of
filer the host can name. It cannot decline utilities, which he also excludes,
and that is a limit rather than a gap — see LIMITS.

Sources, and which is which, because a reader auditing a number later has to
be able to tell. Every value carries its own `source` saying so, which is
where to look rather than here. All five levels are Greenblatt's own, from
The Little Book That Still Beats the Market and the FAQ on his site; two of
them are a point inside a band he gives rather than a number he states, and
each of those says so in its own words.

Nothing here computes a comparison. Every test is put to `contract.test` and
then cited as the same item, so what a rule acted on and what the reader sees
are one answer rather than two that agree until they do not.
"""

from engine import contract

PASS, FAIL, UNKNOWN = contract.PASS, contract.FAIL, contract.UNKNOWN


# ---------------------------------------------------------------------------
# The groups.
#
# Three, and only two of them demand anything. That ratio is the strategy: a
# buy here rests on two facts about your own journal — this name is on the
# list you are working from, and there is room to start another one — and on
# nothing at all about the company.
# ---------------------------------------------------------------------------

LIST_GROUP = {"id": "list", "name": "The list you are working from",
              "requires": "all"}
ROOM_GROUP = {"id": "room", "name": "Whether there is room to start another",
              "requires": "all"}
# Reported so a reader can see why a name reached a list, and demanded of
# nothing. A `noted` group is exempt from the host's commit check, which is
# what lets these two sit beside a purchase without either of them being able
# to refuse one — the structural version of "these gate nothing".
WHY_GROUP = {"id": "why", "name": "Why it was on the list", "requires": "noted"}
CLOCK_GROUP = {"id": "clock", "name": "The year it is given", "requires": "all"}


# ---------------------------------------------------------------------------
# The citations.
#
# Every one of these is passed to `contract.test` to choose a state and then
# cited unchanged, so the rule that acted and the row that renders are one
# answer. None of them names a measure: this strategy tests nothing about any
# company, and the two rows that do name measures carry no comparator.
# ---------------------------------------------------------------------------

# Is this name on the list in force? `equals` rather than a number because the
# host serves the answer as a yes or no — the strategy owns the question and
# never works out membership for itself.
ON_LIST = {"fact": "security.on_list", "comparator": "equals",
           "threshold": True, "group": LIST_GROUP["id"]}

# Is that list current enough to still be buying from? A screen is a
# photograph of prices and accounts on one day; a year later it is a list of
# the companies that were cheapest then.
LIST_FRESH = {"fact": "list.age_months", "comparator": "below",
              "threshold_from": "list-refresh-months",
              "group": LIST_GROUP["id"]}

# Room in the portfolio at all.
SLOTS = {"fact": "portfolio.slots_occupied", "comparator": "below",
         "threshold_from": "portfolio-slots", "group": ROOM_GROUP["id"]}

# The clock, cited in the direction the holding must keep: below the year it
# was given. `below` and not `at_most` for the reason Graham's clock uses it —
# the exit falls due ON the anniversary, so at exactly the limit the
# requirement has failed.
CLOCK = {"fact": "position.months_held", "comparator": "below",
         "threshold_from": "holding-period-months", "group": CLOCK_GROUP["id"]}

# What the two ranked figures were. No comparator on either: they are read,
# never tested. Adding one would make this a screen, which is the one thing
# this method says not to do.
WHY_ROWS = ({"measure": "earnings_yield", "group": WHY_GROUP["id"]},
            {"measure": "return_on_capital", "group": WHY_GROUP["id"]})

# Two observations with no group of their own, because they are cited under
# different headings on the two paths: when you last saw this name on a list
# reads as part of the list on the way in and as part of the clock once it is
# held. A group is a property of the citation rather than of the subject, so
# it is supplied where the row is used.
WHEN_LISTED = {"fact": "security.listed_on"}
WHEN_OPENED = {"fact": "position.opened"}


def _under(row, group):
    """One citation, gathered under a heading. The rows of a group must be
    contiguous in the evidence list and a group with no rows is refused, so
    every list below is built in group order and a heading is only declared
    where its rows were appended."""
    return {**row, "group": group["id"]}


DECLINES = [
    {"class": "depository-lending",
     "because": "Greenblatt's own database leaves financial companies out, "
                "and says why in one line: their accounting statements are "
                "not the same kind of document. Both figures the ranking "
                "rests on assume the difference between what a business owns "
                "and what it owes is capital tied up in operations. For a "
                "lender that difference is the product — the deposits are "
                "what it lends out, and no filing tags them as borrowing — "
                "so a name here could never have reached a list in the first "
                "place, and evaluating one would be answering a question the "
                "method never asks."},
    {"class": "insurance",
     "because": "Excluded from Greenblatt's database for the same reason "
                "lenders are. An insurer's investment portfolio is held "
                "against claims not yet made and belongs to policyholders, "
                "so measuring a return against it measures somebody else's "
                "money — and its cash flow carries the growth of float, "
                "which is money owed out later arriving now. A name here "
                "could not have reached a list, so there is nothing for this "
                "journal to be timing."},
    {"class": "real-estate",
     "because": "A property company charges depreciation against buildings "
                "every year as though they were wearing out, and well-kept "
                "property mostly does not — so the operating profit both "
                "ranked figures divide understates by design, and the "
                "capital underneath is those same buildings at what they "
                "cost decades ago. The industry replaces the profit figure "
                "entirely, with funds from operations, which this program "
                "does not compute. Most of these filers also present no "
                "current-and-non-current balance sheet at all, so there is "
                "no working capital here to read."},
]


LIMITS = [
    {"title": "It is a portfolio method, and this is one security",
     "body": "Everything here was worked out by somebody running twenty to "
             "thirty positions at once, and the arithmetic works across the "
             "set rather than inside any one of them. Greenblatt is "
             "explicit that a meaningful number of these will lose money and "
             "that the method can trail the market for years at a stretch — "
             "he asks for three years before judging it at all. A screen "
             "that renders a verdict on one name at a time is quietly "
             "offering something he never offered, which is that this "
             "particular one will work.\n\n"
             "The staging rule is the part of that this journal does "
             "enforce. Everything else about running a set of positions — "
             "not abandoning it in the second bad year above all — is yours."},

    {"title": "Where a name ranked is not here, and cannot be",
     "body": "The list you imported is the top of a ranking run against "
             "roughly three thousand companies. This journal has the thirty "
             "or fifty names and none of the rest, so it can tell you what a "
             "company's earnings yield and return on capital are and it "
             "cannot tell you whether that put it third or twenty-ninth.\n\n"
             "That is worth saying plainly rather than leaving to be "
             "noticed, because the two figures on the page look exactly like "
             "the figures a screen would have tested. They were not tested "
             "here. Nothing in this journal ranked, chose or approved any of "
             "these names — it recorded which list you took them from, and "
             "when."},

    {"title": "It sells on a date, and which side of the date is yours",
     "body": "Greenblatt's refinement is to sell a position you are down on "
             "a few days BEFORE its one-year mark, and one you are up on a "
             "few days AFTER. The reason is tax: a loss realised inside a "
             "year is worth more against ordinary income, and a gain held "
             "past a year is taxed at the long-term rate. A mechanical date "
             "is not free when a few days either way is.\n\n"
             "This journal will not pick the side for you, and that is a "
             "refusal rather than a shortfall. Knowing whether you are up "
             "means knowing what you paid, and no rule in this program is "
             "ever handed the cost of a position — the same refusal is why "
             "nothing here will ever tell you to buy more of something "
             "because it has fallen since you bought it. A tool that knew "
             "your purchase price could tell you both, and the second one is "
             "the expensive habit of the two.\n\n"
             "So: the date shown is the anniversary. If you are down on the "
             "position, sell a few days early. If you are up, sell a few "
             "days late. You know which you are."},

    {"title": "His database also leaves out utilities, and this cannot",
     "body": "The screen excludes utilities alongside financial companies. "
             "This journal declines lenders, insurers and property "
             "companies, because those are kinds of filer the industry code "
             "the SEC publishes lets the program name — and there is no "
             "utilities class here to decline.\n\n"
             "In practice the exclusion has already been applied before you "
             "get here: it happens at the screen, so a utility cannot be on "
             "a list you imported. One can only reach this journal if "
             "somebody typed it in, and a name that is not on your list is "
             "not a buy here either way. That makes this a boundary of the "
             "method rather than a hole in the tool."},
]


STRATEGY = {
    "id": "magic-formula",
    "name": "Magic Formula",
    "summary": "Works from a ranked list you pull yourself, buys a few names "
               "from it every couple of months until the portfolio is full, "
               "and sells each after about a year. It never judges a company "
               "— the list already did that.",
    "version": 1,
    "contract": 6,
    "declines": DECLINES,
    "limits": LIMITS,

    # What this strategy works from. Declaring it is what turns on the import
    # screen, the four list facts the host serves, and the blocked verdict a
    # journal gets before it has been given one — none of which a strategy
    # that screens for itself ever sees.
    "list": {
        "label": "Your Magic Formula list",
        "explain": "The thirty or fifty names the Magic Formula screen "
                   "returned, and the day you pulled them. The screen is "
                   "free and it is Greenblatt's own: you give it a smallest "
                   "company size and ask for thirty names or fifty, and it "
                   "ranks the whole US market on two figures and hands you "
                   "the top of the list.\n\n"
                   "That ranking is the entire buy decision here. This "
                   "journal does not repeat it, improve on it or check it — "
                   "it records which list you used, so that a year later you "
                   "can see what you were working from rather than what you "
                   "remember working from.",
        "source": {"name": "magicformulainvesting.com — Greenblatt's own "
                           "free screener, described in The Little Book "
                           "That Still Beats the Market",
                   "reasoning": False},
    },

    "changelog": {
        1: "First version, and the first strategy in this program with no "
           "buy criteria at all.\n\n"
           "WHAT IT BUYS ON is a list you pulled yourself and imported, and "
           "two facts about your own journal: the list is still current, and "
           "you have not already started more names than the staging rule "
           "allows inside the last couple of months. No measure is tested "
           "anywhere on the buy path. Earnings yield and return on capital "
           "are shown beside every verdict and gate nothing — they say why a "
           "name reached a list, which happened somewhere else.\n\n"
           "WHAT IT SELLS ON is a clock and nothing else. Twelve months from "
           "the later of the day you bought and the day the freshest list "
           "carrying the name was pulled — so a name that comes back on a "
           "new list is held rather than sold and bought again. Nothing "
           "about the business can end a position here, because nothing "
           "about the business started one.\n\n"
           "WHAT IT WILL NOT DO is pick which side of the anniversary to "
           "sell on. That needs what you paid, and no rule in this program "
           "is given it. See the method's stated limits.",
    },

    "states": [
        {"id": "buy-it", "render": "commit",
         "name": "Buy it",
         "description": "It is on the list you are working from, that list "
                        "is still current, and there is room to start "
                        "another name without breaking the staging rule.\n\n"
                        "Nothing was tested about the company, and that is "
                        "not an oversight. The ranking that put this name in "
                        "front of you was run against three thousand others "
                        "and is the whole of the judgement in this method. "
                        "The size is an equal share of the number of "
                        "positions this journal is meant to run — equal "
                        "dollar amounts, which is Greenblatt's own answer "
                        "and differs from every other strategy here."},

        {"id": "not-time-yet", "render": "hold",
         "name": "On the list, but not yet",
         "description": "It is on your current list and this is not the "
                        "moment. Either the portfolio already holds as many "
                        "names as it is meant to, or you have started enough "
                        "new positions in the last couple of months and the "
                        "next few belong to the next couple.\n\n"
                        "The staging is deliberate and it is the rule most "
                        "worth keeping. Buying the whole list at once puts "
                        "every position you own on one day's prices, and "
                        "spreading the entry across four or five moments "
                        "over the first year is what stops a single bad "
                        "starting point deciding the whole result. Nothing "
                        "stops you buying anyway; it is recorded as going "
                        "against your own rule, with the reason you give."},

        {"id": "not-on-your-list", "render": "hold",
         "name": "Not on your list",
         "description": "The screen did not return this name, so this method "
                        "has nothing to say about buying it.\n\n"
                        "Read that as a statement about your list rather "
                        "than about the company. It has not been judged and "
                        "found wanting: it was ranked against three thousand "
                        "others somewhere else and did not reach the top "
                        "thirty or fifty, and the ranking itself is not in "
                        "this journal. If you want this name in a Magic "
                        "Formula portfolio, the honest route is a list it "
                        "appears on."},

        {"id": "waiting-on-a-list", "render": "blocked", "fix": "list",
         "name": "Your list is out of date",
         "description": "The list this journal is working from is older than "
                        "the strategy will buy off, so there is no honest "
                        "verdict to give about starting a new position.\n\n"
                        "A screen is a photograph of prices and published "
                        "accounts on one day. Prices have moved since and "
                        "accounts have been restated, so an old list is no "
                        "longer a list of the cheapest good companies — it "
                        "is a list of the ones that were cheapest then, "
                        "which is a different thing and looks identical. "
                        "Pull a fresh one and import it.\n\n"
                        "Positions you already hold are unaffected: their "
                        "year runs on its own clock and nothing here needs a "
                        "current list to say when it is up."},

        {"id": "still-running", "render": "hold",
         "name": "Held, and the year is not up",
         "description": "You own it and the clock has not run out. There is "
                        "nothing to check and nothing to do.\n\n"
                        "That is the whole of holding under this method. No "
                        "figure about the business will end this position "
                        "early, because no figure about the business started "
                        "it — the two shown below say why it reached a list "
                        "and are not tests. A price that has run up is not a "
                        "reason to sell here and a price that has fallen is "
                        "not a reason to buy more."},

        {"id": "back-on-the-list", "render": "hold",
         "name": "Back on the list, so the year starts again",
         "description": "A list pulled after you bought this still carries "
                        "the name, so it has been chosen again on fresh "
                        "prices and fresh accounts. Its year runs from that "
                        "list's day rather than from your purchase, and the "
                        "date it now falls due is below.\n\n"
                        "The alternative would be to sell it and buy it "
                        "straight back, which is the same economic position "
                        "with a new year on it, reached by paying a spread — "
                        "and in a taxable account it is a wash sale, so a "
                        "loss realised on the way through would be "
                        "disallowed. Greenblatt does not address this case "
                        "directly; holding is this strategy's answer to it."},

        {"id": "time-is-up", "render": "close",
         "name": "The year is up",
         "description": "This has been held for about the year the method "
                        "gives it, and no later list has carried the name "
                        "since. Nothing about the company decided that — "
                        "this is the only exit this strategy has.\n\n"
                        "The date shown is the anniversary itself, and a few "
                        "days either side of it is free. Greenblatt's own "
                        "refinement is to sell a position you are down on "
                        "shortly before that date and one you are up on "
                        "shortly after, which is worth a week of anybody's "
                        "patience in a taxable account. This journal will "
                        "not choose for you: it never holds what you paid, "
                        "which is the same reason it will never tell you to "
                        "buy more of something because it has fallen.\n\n"
                        "Selling here is half a decision. The other half is "
                        "a fresh list and a replacement bought from it."},
    ],

    "inputs": [
        # Optional, exactly as on the other three. Without it the size cannot
        # be turned into money and says so, naming this field. Requiring it
        # would put a setup gate in front of every verdict in the journal.
        {"id": "free-cash", "label": "Free cash", "type": "number",
         "unit": "usd", "role": "cash", "required": False,
         "explain": "Money in the account this journal covers that is not "
                    "in any position. The journal adds it to what your "
                    "holdings are worth to get the account total, and that "
                    "total is what an equal share of the portfolio is "
                    "measured against. Leave it blank and the size says it "
                    "cannot be worked out rather than guessing at it.\n\n"
                    "It matters more here than in a strategy that buys one "
                    "name at a time: equal dollar amounts across twenty-five "
                    "positions is arithmetic over the whole account, and in "
                    "the first year most of that account is still cash."},
    ],

    "values": [
        {"id": "portfolio-slots",
         "label": "How many names to hold at once",
         "type": "integer", "unit": "count", "min": 5, "max": 100,
         "source": {"name": "Greenblatt, The Little Book That Still Beats "
                            "the Market, and the FAQ at "
                            "magicformulainvesting.com — twenty to thirty "
                            "names, at least twenty. Twenty-five is the "
                            "middle of his band and is this file's pick "
                            "inside it",
                    "reasoning": False},
         "explain": "How many separate companies this journal is meant to "
                    "hold at once, and therefore how big each one is: an "
                    "equal share of the account, so twenty-five names is "
                    "four percent each.\n\n"
                    "The number is doing real work rather than expressing a "
                    "preference. This method expects a meaningful share of "
                    "its picks to lose money and pays for them out of the "
                    "ones that work, which only holds if no single name can "
                    "decide the result. Fewer names makes each outcome "
                    "matter more, which is the opposite of what the "
                    "arithmetic needs; many more makes the portfolio "
                    "expensive to keep up and eventually just buys the "
                    "market.\n\n"
                    "Greenblatt gives twenty to thirty and says at least "
                    "twenty. Twenty-five is the middle of that."},

        {"id": "names-per-tranche",
         "label": "Most new names to start in one go",
         "type": "integer", "unit": "count", "min": 1, "max": 50,
         "source": {"name": "Greenblatt, The Little Book That Still Beats "
                            "the Market — five to seven names every two to "
                            "three months",
                    "reasoning": False},
         "explain": "The most new positions this journal will start inside "
                    "one staging window. Reaching it is not a refusal to buy "
                    "the rest of the list, it is a refusal to buy them "
                    "today.\n\n"
                    "Buying a whole list at once means every position you "
                    "own was bought on one day's prices, and one badly "
                    "chosen day then decides an entire year's result. "
                    "Spreading the entry across four or five moments does "
                    "not improve any single purchase — it removes the "
                    "chance that all of them were made at the worst "
                    "possible time. It is the most common way people stop "
                    "getting this method's results."},

        {"id": "tranche-months",
         "label": "How long a staging window lasts",
         "type": "integer", "unit": "months", "min": 1, "max": 12,
         "source": {"name": "Greenblatt, The Little Book That Still Beats "
                            "the Market — every two to three months; the "
                            "shorter end of his range",
                    "reasoning": False},
         "explain": "How far back the journal looks when it counts how many "
                    "names you have started recently. A name bought inside "
                    "this window counts against the staging limit; one "
                    "bought before it does not.\n\n"
                    "Two months at five to seven names fills a "
                    "twenty-five-name portfolio in about eight months, which "
                    "is the pace the method describes. Making it longer "
                    "spreads the first year further and takes longer to be "
                    "fully invested; making it shorter concentrates the "
                    "entry back towards a single moment, which is the thing "
                    "the staging exists to prevent.\n\n"
                    "It does not stop you replacing a position you have just "
                    "sold. The limit counts names started recently, not days "
                    "since the last purchase, so a sale at its anniversary "
                    "and the replacement bought the same week are one name "
                    "against the window rather than a blocked purchase."},

        {"id": "holding-period-months",
         "label": "How long a position is held",
         "type": "integer", "unit": "months", "min": 1, "max": 120,
         "source": {"name": "Greenblatt, The Little Book That Still Beats "
                            "the Market, and the FAQ at "
                            "magicformulainvesting.com — hold approximately "
                            "one year",
                    "reasoning": False},
         "explain": "How long a position is given before it is sold, counted "
                    "from the later of the day you bought it and the day the "
                    "freshest list carrying it was pulled.\n\n"
                    "It is the only exit this strategy has. Nothing about "
                    "the company can end a position here, so this number is "
                    "the entire sell discipline, and moving it is the "
                    "largest change anyone can make to what this journal "
                    "does.\n\n"
                    "A year is not arbitrary. It is long enough for the "
                    "cheapness the ranking found to have a chance to correct "
                    "and short enough that the portfolio is rebuilt from "
                    "current accounts each year, and it is the point at "
                    "which a gain becomes long-term for tax. A few days "
                    "either side of the anniversary costs nothing — see what "
                    "this method does not promise."},

        {"id": "list-refresh-months",
         "label": "How old a list may be and still be bought from",
         "type": "integer", "unit": "months", "min": 1, "max": 60,
         "source": {"name": "Greenblatt, the FAQ at "
                            "magicformulainvesting.com — after a year, "
                            "screen for new stocks and build a new portfolio "
                            "on the most current financial statements and "
                            "stock prices",
                    "reasoning": False},
         "explain": "How stale the list may get before this journal stops "
                    "buying from it and asks for a fresh one.\n\n"
                    "A screen is a photograph. The prices it ranked on have "
                    "moved and the accounts have been restated, so an old "
                    "list is not a list of the cheapest good companies any "
                    "more — it is a list of the ones that were cheapest "
                    "then, which looks exactly the same on the page. Buying "
                    "from it is buying last year's answer at this year's "
                    "prices.\n\n"
                    "A year here lines up with the year a position is given, "
                    "which is what makes the loop close: the first positions "
                    "come due at about the moment the list they came from "
                    "expires, and one fresh pull answers both."},
    ],
}


# ---------------------------------------------------------------------------
# Reading the journal.
#
# Two helpers and both of them are arithmetic over what the host already
# reported. Neither restates a figure: the counts below choose a state, and
# the rows that render cite the host's own facts wherever the host has one.
# ---------------------------------------------------------------------------

def _months(start, end):
    """Whole months between two days, or None where either is missing.

    The host's arithmetic and never a second copy of it. Month counting looks
    trivial and is not — the 29th of February plus twelve months is the 28th —
    and a private version that disagreed by a day would close a position on a
    day its own evidence called early.
    """
    if not start or not end:
        return None
    return contract.months_between(start, end)


def _started_recently(ctx):
    """How many names this journal has started inside the staging window.

    Counted off the holdings the host reports, each of which carries the day
    its own holding began. It is stated as a figure of its own rather than
    cited, because the host has no fact for "positions opened lately" and
    could not have one: how lately is a level this strategy declares, and a
    fact cannot take a parameter.

    A trim does not restart a holding and a sale that closes one removes it,
    so this counts names currently held that were started recently — which is
    the quantity the staging rule is about.
    """
    window = (ctx.get("values") or {}).get("tranche-months")
    if not isinstance(window, int) or isinstance(window, bool):
        return None
    today = ctx.get("today")
    started = 0
    for holding in (ctx.get("portfolio") or {}).get("holdings") or []:
        elapsed = _months(holding.get("opened"), today)
        if elapsed is not None and elapsed < window:
            started += 1
    return started


def _clock_start(ctx):
    """(the day this position's year runs from, whether a list restarted it).

    The later of the day the holding began and the day the freshest list
    carrying the name was pulled. Both are host facts and neither is restated
    — what is worked out here is which of the two is later, which is a
    question rather than a figure.
    """
    opened = (ctx.get("position") or {}).get("opened")
    listed = (ctx.get("security") or {}).get("listed_on") or {}
    when = listed.get("value") if listed.get("status") == "known" else None
    if opened and when and when > opened:
        return when, True
    return opened, False


# ---------------------------------------------------------------------------
# The ladder.
#
# One fork on whether the security is held, and a single ladder under each
# with one exit per rung, so no two conclusions can both be true. The buy is
# the last rung of its ladder, which is not a stylistic choice: the host
# refuses a commit standing beside a group it resolved as anything but
# passed, so every way the answer can be no has to be reached and explained
# before the way it can be yes.
# ---------------------------------------------------------------------------

def decide(ctx):
    """One evaluation, one state."""
    if (ctx.get("position") or {}).get("held"):
        return _on_a_holding(ctx)
    return _on_a_candidate(ctx)


def _on_a_candidate(ctx):
    """A security this journal does not hold."""
    fresh = contract.test(ctx, LIST_FRESH)
    listed = contract.test(ctx, ON_LIST)
    age = (ctx.get("list") or {}).get("age_months")

    # The list first, because a stale list makes every other answer on this
    # path unsafe rather than merely unknown: a name is on it or off it
    # according to a ranking that no longer describes anything.
    if fresh != PASS:
        return {
            "state": "waiting-on-a-list",
            "payload": {"needs": [
                "Pull a fresh Magic Formula list and import it. Everything "
                "you already hold keeps its own clock and is unaffected."]},
            "reason": {
                "rule": "list-too-old-to-buy-from",
                "summary": (
                    f"The list this journal is working from is {age} months "
                    "old, and this strategy will not start a position off a "
                    "ranking that stale."
                    if isinstance(age, int) else
                    "How old the list this journal is working from is could "
                    "not be worked out, so nothing can be bought off it."),
                "evidence": [{"fact": "list.pulled"}, LIST_FRESH],
                "groups": [LIST_GROUP],
                "note": None},
        }

    if listed != PASS:
        return {
            "state": "not-on-your-list",
            "payload": {},
            "reason": {
                "rule": "not-among-the-names-the-screen-returned",
                "summary": (
                    "The screen did not return this name, so there is "
                    "nothing here to buy. It was not judged and turned down "
                    "— it was ranked somewhere else, against companies this "
                    "journal has never seen."),
                "evidence": [ON_LIST, _under(WHEN_LISTED, LIST_GROUP),
                             LIST_FRESH] + list(WHY_ROWS),
                "groups": [LIST_GROUP, WHY_GROUP],
                "note": None},
        }

    room = contract.test(ctx, SLOTS)
    started = _started_recently(ctx)
    staging = _staging_row(started)
    paced = contract.test(ctx, staging)
    slots = (ctx.get("values") or {}).get("portfolio-slots")
    occupied = ((ctx.get("portfolio") or {}).get("slots") or {}).get("occupied")

    if room != PASS or paced != PASS:
        return {
            "state": "not-time-yet",
            "payload": {},
            "reason": {
                "rule": ("portfolio-already-full" if room != PASS
                         else "enough-started-this-window"),
                "summary": (
                    f"You hold {occupied} names and this journal runs "
                    f"{slots}, so there is no room to start another."
                    if room != PASS else
                    f"{started} of these were started inside the staging "
                    "window. The rest of the list belongs to the next one — "
                    "buying it all today would put every position you own on "
                    "one day's prices."),
                "evidence": [ON_LIST, LIST_FRESH, SLOTS, staging,
                             {"value": "tranche-months",
                              "group": ROOM_GROUP["id"]}]
                            + list(WHY_ROWS),
                "groups": [LIST_GROUP, ROOM_GROUP, WHY_GROUP],
                "note": None},
        }

    return {
        "state": "buy-it",
        "payload": {"size": _size(slots), "condition": None},
        "reason": {
            "rule": "on-the-current-list-and-room-to-start-it",
            "summary": (
                "It is on the list you are working from and there is room to "
                "start it. Nothing about the company was tested here — the "
                "ranking that put it in front of you is the decision, and it "
                "was made against three thousand companies this journal does "
                "not have."),
            "evidence": [ON_LIST, LIST_FRESH, SLOTS, staging,
                         {"value": "tranche-months", "group": ROOM_GROUP["id"]}]
                        + list(WHY_ROWS),
            "groups": [LIST_GROUP, ROOM_GROUP, WHY_GROUP],
            "note": None},
    }


def _on_a_holding(ctx):
    """A security this journal holds. One clock, and nothing else."""
    period = (ctx.get("values") or {}).get("holding-period-months")
    start, restarted = _clock_start(ctx)
    due = contract.months_after(start, period) if start else None
    elapsed = _months(start, ctx.get("today"))

    # Cited in the direction the holding must keep — under the year it was
    # given — so a position sitting happily inside its year renders as a pass
    # and the exit is that same test failing. Written the other way round, a
    # perfectly ordinary holding renders a red row beside a verdict of hold.
    #
    # Two shapes of the same test, and the branch is the point. Where no list
    # has restarted the clock the host's own months-held fact answers it and
    # nothing is restated. Where one has, months held is the wrong quantity —
    # it counts from the purchase — so the strategy states the figure it does
    # own, and the two rows above it show the reader where it came from.
    clock = CLOCK if not restarted else _restarted_row(elapsed)
    rows = [_under(WHEN_OPENED, CLOCK_GROUP),
            _under(WHEN_LISTED, CLOCK_GROUP), clock]
    ran_out = contract.test(ctx, clock) == FAIL

    if ran_out:
        return {
            "state": "time-is-up",
            "payload": {"when": due},
            "reason": {
                "rule": ("year-since-it-was-last-listed-is-up" if restarted
                         else "year-since-you-bought-it-is-up"),
                "summary": (
                    f"The year this position was given ran out on {due}"
                    + (f", counted from {start} when the last list carrying "
                       "it was pulled" if restarted else "")
                    + ". Nothing about the company decided that; the clock "
                    "is the only exit this method has."),
                "evidence": rows + list(WHY_ROWS),
                "groups": [CLOCK_GROUP, WHY_GROUP],
                "note": None},
        }

    if restarted:
        return {
            "state": "back-on-the-list",
            "payload": {},
            "reason": {
                "rule": "relisted-so-the-year-restarts",
                "summary": (
                    f"A list pulled on {start} still carries this name, so "
                    "it has been chosen again on fresh prices and fresh "
                    f"accounts. Its year now runs to {due} rather than from "
                    "the day you bought."),
                "evidence": rows + list(WHY_ROWS),
                "groups": [CLOCK_GROUP, WHY_GROUP],
                "note": None},
        }

    return {
        "state": "still-running",
        "payload": {},
        "reason": {
            "rule": "inside-the-year-it-was-given",
            "summary": (
                f"Held since {start}, and due on {due}. Nothing to do — no "
                "figure about this business can end the position early, "
                "because none of them started it."
                if due else
                "This is held and when its year falls due could not be "
                "worked out, so nothing here says to sell it."),
            "evidence": rows + list(WHY_ROWS),
            "groups": [CLOCK_GROUP, WHY_GROUP],
            "note": None},
    }


# ---------------------------------------------------------------------------
# The two rows this strategy states itself.
#
# Both are counts the host has no fact for and could not have one for: each
# is measured against a window this strategy declares, and a host fact takes
# no parameters. They are the only figures in this bundle the host did not
# supply, which is the smallest number it could be rather than a convenience.
# ---------------------------------------------------------------------------

def _staging_row(started):
    """How many names were started inside the staging window."""
    row = {"label": "Names started inside the staging window",
           "unit": "count", "comparator": "below",
           "threshold_from": "names-per-tranche", "group": ROOM_GROUP["id"]}
    if started is None:
        return {**row, "absent": "how long the staging window runs could not "
                                 "be read from this journal's settings"}
    return {**row, "actual": started}


def _restarted_row(elapsed):
    """Months since a later list restarted this position's year."""
    row = {"label": "Months since the last list carrying it",
           "unit": "months", "comparator": "below",
           "threshold_from": "holding-period-months",
           "group": CLOCK_GROUP["id"]}
    if elapsed is None:
        return {**row, "absent": "the day the last list carrying this name "
                                 "was pulled could not be read"}
    return {**row, "actual": elapsed}


def _size(slots):
    """An equal share of the account, across the names this journal runs.

    Equal dollar amounts is Greenblatt's own answer and differs from all
    three of the other strategies here, each of which sizes on conviction or
    on a cap. It follows from the method rather than sitting beside it: a
    ranking that expects a meaningful share of its picks to lose money can
    only work if no single one of them is bigger than the rest.
    """
    if not isinstance(slots, int) or isinstance(slots, bool) or slots < 1:
        raise ValueError(
            "portfolio-slots must be a whole number of positions; this "
            "strategy sizes every purchase as an equal share of it.")
    return {"unit": "weight", "value": round(100.0 / slots, 4)}
