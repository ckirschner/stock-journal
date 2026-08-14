"""Cash as a record of what happened to it, never a figure that gets typed.

There was one editable number for free cash and a dated list of its edits.
That is enough to say what the balance is and nothing at all about how it got
there — and the distance between those two is the distance between a return
figure that means something and one that does not. Ten thousand dollars
arriving into a fifty-thousand-dollar account moves the total by a fifth, and
an account total that cannot tell that from a good quarter answers "how am I
doing" with a number that is simply false.

So cash is events. Money arriving, money leaving, money the holdings paid out,
each on the day it moved, appended and never edited — on the same substrate
every other thing the user writes already sits on (engine/dated.py). The
balance is derived from them on read, which is principle 5: anything the tool
can work out it works out, so that when a figure looks wrong there is an entry
to point at rather than a typo nobody can find.

**Three kinds, one shape, and what separates them is declared rather than
remembered.** A deposit and a dividend both add to the balance and are not the
same event: one is money you put in, the other is money the account earned. A
figure that counts a dividend as a contribution understates what the account
made by exactly that dividend; one that counts a deposit as a gain overstates
it by exactly that deposit. Both are one mistake — reading a label and
assuming what it implies — so no arithmetic in here reads a label. Each kind
declares its `direction`, which is what it does to the balance, and its
`flow`, which is whether the money crossed the account's boundary or was
earned inside it. The two sums that matter each read one of those fields, and
a fourth kind is a row in that table rather than a branch in a function.

**An amount is never signed.** The direction belongs to the kind and is
applied in exactly one place. A signed amount would be a sign convention
stated at the write and applied at the read, which is the failure CLAUDE.md
names outright: a withdrawal entered as -500 under a kind that already means
"out" adds five hundred dollars to the account, quietly, forever.

**The record begins somewhere and says where.** A ledger of flows with no
starting point is a change and not a balance — summing three deposits into an
account nobody has said anything about would report the balance as those three
deposits, which is an invented figure wearing a derivation. So the first entry
is an opening balance: what was in the account on the day this journal started
counting. Until there is one the balance is absent with that reason rather
than zero, nothing else may be recorded, and nothing may be dated before it.
That last refusal is correctness rather than strictness — the opening balance
already states what was there on its day, so a dividend dated before it is
money the opening figure has already counted, and adding it would count it
twice.

**The day the money moved governs, not the day it was typed.** That is the
rule every lot obeys and it is right here for the same reason: a deposit made
in March and entered in August was in the account in April, and a purchase
being reconstructed for April should be sized against an account that had it.
It differs from how a typed answer was dated — an answer carries no event
date, so the only day it could ever be read against was the day it was given —
and that difference is the improvement rather than an inconsistency.

**There is no edit and no delete.** A deposit entered wrong is corrected by an
entry of the difference with a note saying so, exactly as a correction is a
new entry everywhere else in this program.
"""

from __future__ import annotations

from types import MappingProxyType

from . import dated, portfolio

# Where the record lives on the journal document. A `dated` key, so it is
# append-only and no caller can supply its own `recorded`.
KEY = "cash_record"

# ---------------------------------------------------------------------------
# What can happen to cash — the host's closed table.
#
# `direction` is what the entry does to the balance: +1 adds, -1 takes away.
# `flow` is what kind of money it is, and it is a different question with a
# different consumer:
#
#   opening   the balance this record starts from. Not a flow at all — it is a
#             statement of what was there, and treating it as a contribution
#             would make the money you started with look like money you added.
#   external  it crossed the boundary of the account. It changes what the
#             account is worth and it is not a gain or a loss, so a return
#             figure has to net it out.
#   earned    the holdings produced it. It changes what the account is worth
#             AND it is part of what the account made, so a return figure must
#             not net it out.
#   internal  it moved between the cash and the positions — you bought shares,
#             or sold some. Cash changes and the account total does not, and
#             neither does what the account earned. Nobody records these: the
#             lots already are the record of them, and asking somebody to type
#             the same ten thousand dollars twice teaches nothing. `recorded_by`
#             says which side writes a kind, and the host writes these.
#
# Nothing below branches on a kind's name. The balance reads `direction`, the
# return-facing split reads `flow`, the screens read `recorded_by`, and a kind
# added here arrives at all of them without any of them being edited. That is
# the whole reason this is a table.
#
# Deliberately absent: an attribution to a security on a dividend. It is the
# obvious next field and nothing would read it — the per-position returns are
# derived from lots and prices and never touch this record — and a declaration
# nothing reads is a comment (principle 14). When a figure needs it, it
# arrives with the figure that needs it.
# ---------------------------------------------------------------------------

KINDS = MappingProxyType({
    "opening": MappingProxyType({
        "label": "Opening balance",
        "one": "opening balance",
        "plural": "opening balances",
        "direction": 1,
        "flow": "opening",
        "recorded_by": "you",
        "means": "the cash this account held at the START of the day the "
                 "record begins. Everything below is counted from it, which "
                 "is why nothing may be dated before it — and why anything "
                 "you bought or sold on that day counts, rather than being "
                 "assumed to be in the figure already.",
    }),
    "deposit": MappingProxyType({
        "label": "Deposit",
        "one": "deposit",
        "plural": "deposits",
        "direction": 1,
        "flow": "external",
        "recorded_by": "you",
        "means": "money you moved into the account from somewhere else. It "
                 "makes the account bigger and it is not a gain — nothing you "
                 "did as an investor produced it.",
    }),
    "withdrawal": MappingProxyType({
        "label": "Withdrawal",
        "one": "withdrawal",
        "plural": "withdrawals",
        "direction": -1,
        "flow": "external",
        "recorded_by": "you",
        "means": "money you moved out of the account. It makes the account "
                 "smaller and it is not a loss.",
    }),
    "dividend": MappingProxyType({
        # Not "dividend receiveds". Both forms of the noun are declared
        # beside the label because neither follows from it — English does not,
        # and a column heading is not a noun a sentence can use: "1 bought
        # shares" is what reusing the label produces.
        "label": "Dividend received",
        "one": "dividend received",
        "plural": "dividends received",
        "direction": 1,
        "flow": "earned",
        "recorded_by": "you",
        "means": "cash a holding paid you. It makes the account bigger and it "
                 "IS part of what the account earned — counting it as money "
                 "you put in would hide a real return.",
    }),
    "bought": MappingProxyType({
        "label": "Bought shares",
        "one": "purchase",
        "plural": "purchases",
        "direction": -1,
        "flow": "internal",
        "recorded_by": "the journal",
        "means": "cash that went into a position. The purchase is already on "
                 "the record as a lot, so this is read off it rather than "
                 "asked for — the account is worth the same either side of "
                 "it, and what changes is which half of it is cash.",
    }),
    "sold": MappingProxyType({
        "label": "Sold shares",
        "one": "sale",
        "plural": "sales",
        "direction": 1,
        "flow": "internal",
        "recorded_by": "the journal",
        "means": "cash that came out of a position. Read off the sale, for "
                 "the same reason a purchase is.",
    }),
})

OPENING = "opening"

# Every field this module reads off a kind, checked at import against every
# kind declared. It is the one thing that makes the table a table: the balance
# reads `direction`, the return-facing split reads `flow`, the sentences read
# `label` and `plural`, and a kind added without one of them would produce a
# KeyError inside an arithmetic function — or, for `plural`, a sentence that
# reads wrong and nothing that notices. Named here, by the code that consumes
# them, so a new field arrives with its own line rather than being trusted to
# whoever adds the next kind.
_KIND_FIELDS = ("label", "one", "plural", "direction", "flow", "means",
                "recorded_by")


def check_kinds(kinds) -> None:
    """Refuse a kind that does not declare everything something reads.

    A function rather than a loop at the bottom of the table, so the guarantee
    can be exercised against a broken table — a check nobody has seen fail is
    decoration.
    """
    for kind, spec in kinds.items():
        short = [f for f in _KIND_FIELDS if spec.get(f) in (None, "")]
        if short:
            raise RuntimeError(
                f'KINDS["{kind}"] does not declare {", ".join(short)}. Every '
                "field here is read by something: the balance, the split "
                "between money that arrived and money that was earned, or a "
                "sentence somebody checks a figure against.")


check_kinds(KINDS)

# What the user writes, and what the journal writes for itself. Derived from
# the table rather than listed again, so a kind added above cannot be left out
# of the list the screens offer or quietly become something a user can type.
YOURS = tuple(k for k, v in KINDS.items() if v["recorded_by"] == "you")
EVENT_KINDS = tuple(k for k in YOURS if k != OPENING)
DERIVED_KINDS = tuple(k for k in KINDS if k not in YOURS)


def kinds_view() -> dict:
    """The table as a screen reads it. Handed over rather than known, so the
    view never learns which kinds exist — principle 9, one level down from
    render types."""
    return {k: dict(v) for k, v in KINDS.items()}


def offers(journal: dict) -> list:
    """Which kinds may be recorded right now, in order.

    Answered here rather than by a screen comparing against a word. The rule
    is the write's — before the record is opened the only thing that can be
    recorded is the opening balance, and after it there is never a second one
    — and a view that worked it out for itself would be a second copy of a
    rule the write enforces, offering a button whose entry is refused.
    """
    if opening(journal) is None:
        return [OPENING]
    return list(EVENT_KINDS)


# -- the shape of an answer ---------------------------------------------------
# The same two nodes every other host figure is reported through. Local rather
# than imported from dataview for the reason allocation.py keeps its own: this
# module reasons about one record and has no business reaching into the data
# layer to say "known".

def _known(value, provenance=None, cautions=None) -> dict:
    return {"status": "known", "value": value, "source": "computed",
            "cautions": list(cautions or []),
            "provenance": list(provenance or [])}


def _absent(reason: str) -> dict:
    return {"status": "absent", "reason": reason}


NO_RECORD = ("this journal has no cash record yet. Record what the account "
             "holds now as an opening balance, and every deposit, withdrawal "
             "and dividend after it — the balance is worked out from those "
             "rather than typed, so a figure that looks wrong has an entry "
             "behind it")


def _usd(n) -> str:
    return f"${n:,.2f}"


def _amount(value, zero_is_a_figure: bool = False) -> float:
    """An amount, or a refusal. Never signed: the direction is the kind's and
    is applied in one place, so a signed figure here would be a second sign
    convention nothing joins to the first.

    Zero is a real opening balance — "there is nothing in the account" is a
    statement somebody can make and the arithmetic needs it — and it is not a
    real movement. A deposit of nothing did not happen, and letting one be
    recorded would put entries on the ledger that a reader has to work out
    mean nothing.

    An account that starts overdrawn is reached the way it happens: open at
    what is there and record what went out. Allowing a negative opening would
    be the signed amount again, arriving through the one entry that has no
    direction of its own to disagree with.
    """
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError("An amount has to be a number, in dollars.")
    if amount != amount or amount in (float("inf"), float("-inf")):
        raise ValueError("An amount has to be a number, in dollars.")
    if amount < 0 or (amount == 0 and not zero_is_a_figure):
        raise ValueError(
            ("An opening balance cannot be negative. If the account starts "
             "overdrawn, open it at what is in it and record what went out — "
             "which way money moved is the kind of entry, never the sign on "
             "the amount." if zero_is_a_figure else
             "An amount has to be more than zero. Which way the money went is "
             "the kind of entry you are making — a withdrawal is a withdrawal "
             "of a positive amount, never a deposit of a negative one."))
    return amount


# -- writing ------------------------------------------------------------------

def opening(journal: dict) -> dict | None:
    """The entry this record starts from, or None where there is none."""
    for entry in journal.get(KEY) or []:
        if isinstance(entry, dict) and entry.get("kind") == OPENING:
            return dict(entry)
    return None


def _from_lots(journal: dict, opened: str) -> list:
    """Every trade that moved cash, read off the lots.

    Nobody records these. A purchase is already a lot carrying its shares, its
    price and its date, and asking somebody to type the same ten thousand
    dollars again as a withdrawal would be asking for work that teaches
    nothing and mislabels it — a withdrawal is money leaving the account, and
    this money did not leave, it changed which half of the account it was in.

    **Trades before the opening balance are not counted**, because the opening
    balance is what the cash was at the START of its day and everything before
    it is already in that figure. Everything on or after it counts, including
    a trade dated on the opening day itself, which is the ordinary first
    session and the case a rule reading "strictly after" would get wrong.

    Priced at what the lot says it cost or fetched. Commission is not on the
    record anywhere, so it is not here either — an approximation of it would
    be a figure this program invented.
    """
    out = []
    for sec in journal.get("securities") or []:
        ticker = str(sec.get("ticker") or "")
        for lot in (sec.get("lots") or []):
            if not isinstance(lot, dict):
                continue
            kind = {"buy": "bought", "sell": "sold"}.get(lot.get("kind"))
            day = str(lot.get("date") or "")[:10]
            if kind is None or not day or day < opened:
                continue
            shares, price = lot.get("shares"), lot.get("price")
            if not isinstance(shares, (int, float)) \
                    or not isinstance(price, (int, float)):
                continue
            out.append({
                "kind": kind,
                "amount": round(float(shares) * float(price), 2),
                "date": day,
                "note": f'{float(shares):g} {ticker} at {_usd(float(price))}',
                # No `seq` of the cash record's own: this is not on it. The
                # lot's own sequence orders these against each other, and the
                # sort below puts every derived row after the recorded ones
                # of the same day — one stated rule rather than two records
                # racing for the same slot.
                "lot": lot.get("id"),
                "lot_seq": lot.get("seq") or 0,
                "recorded": lot.get("recorded"),
                "derived": True,
            })
    return out


def entries(journal: dict) -> list:
    """Every entry that moved cash, oldest first by the day it moved.

    Two sources, one list: what the user recorded, and what the lots already
    say. They are merged here rather than added up separately so that
    everything downstream — the balance, the split, the statement a reader
    checks — reads one sequence and cannot disagree with another about it.

    Ordered by event day, then by which source it came from, then by write
    order. Nothing about the balance depends on the order — a sum has no
    order — but the statement a reader sees does, and two entries on one day
    have to come out the same way on every render.
    """
    start = opening(journal)
    opened = str((start or {}).get("date") or "")[:10]
    got = [dict(e) for e in (journal.get(KEY) or []) if isinstance(e, dict)]
    if start is not None:
        got += _from_lots(journal, opened)
    got.sort(key=lambda e: (str(e.get("date") or ""),
                            1 if e.get("derived") else 0,
                            e.get("lot_seq") if e.get("derived")
                            else e.get("seq") or 0))
    return got


def record(journal: dict, kind: str, amount, when=None, note: str = "") -> dict:
    """Append one cash entry and return it.

    Refuses four things, and each of them would otherwise put a confident
    wrong number into the account total rather than an error on a screen:
    a kind the host does not have, an amount that is not a positive figure,
    a second opening balance, and any entry that cannot be counted from the
    opening balance this record already has.

    The date is the day the money moved and is checked by the same rule every
    dated entry in this journal obeys — engine/portfolio.recorded_date — so a
    future date is refused here for the reason it is refused on a sale: it has
    not happened, and the account inflates by its whole value in the meantime.
    """
    spec = KINDS.get(str(kind))
    if spec is None:
        raise ValueError(
            f'"{kind}" is not something that happens to cash. This journal '
            "records " + ", ".join(YOURS) + ".")
    if spec["recorded_by"] != "you":
        raise ValueError(
            f'{spec["label"]} is not recorded here — the journal reads it off '
            "your lots, because the trade is already on the record and typing "
            "the same money twice is how the two come to disagree.")
    value = _amount(amount, zero_is_a_figure=kind == OPENING)
    day = portfolio.recorded_date(when, "cash entry")
    start = opening(journal)

    if kind == OPENING:
        if start is not None:
            raise ValueError(
                "This journal's cash record already opens on "
                f'{start["date"]} at {_usd(start["amount"])}. There is only '
                "ever one opening balance — the record is append-only, and a "
                "second one would silently restate every figure counted from "
                "the first. If that balance was wrong, record the difference "
                "as a deposit or a withdrawal and say so in the note.")
    elif start is None:
        raise ValueError(
            "This journal's cash record has not been opened yet, so there is "
            "nothing for this to be counted from. Record what the account "
            "held on the day you started keeping it, then everything that has "
            "moved since.")
    elif day < str(start["date"])[:10]:
        raise ValueError(
            f'This journal\'s cash record opens on {start["date"]}, and an '
            f"entry dated {day} comes before it. The opening balance already "
            "says what the account held that day, so this would be counted "
            "twice. Date it on or after the opening, or open the record "
            "earlier — nothing recorded is changed either way.")

    return dated.append(journal, KEY, {
        "kind": str(kind),
        "amount": value,
        # The day the money moved, which the user types. `recorded` is the day
        # they typed it and is stamped by the substrate; the two come apart
        # whenever somebody enters last week's dividend, and each answers a
        # different question — see the module docstring.
        "date": day,
        "note": str(note or "").strip() or None,
    })


# -- reading ------------------------------------------------------------------

def _to(journal: dict, as_of: str | None):
    """Every entry that had happened by a day, and the opening it counts from.

    Returns (entries, opening, refusal) — the refusal is a sentence where the
    record cannot answer for that day at all, and None where it can.

    **An entry this build has no kind for makes the whole balance absent.**
    It is the case a restored backup produces: a record written where a fourth
    kind existed, read back where it does not. Summing around it would report
    a total short by exactly the entries nobody could read, with nothing on the
    screen saying so — and this figure is what the account and every weight
    are built on. Principle 4 is explicit that a source which cannot be shown
    to account for the whole leaves the value absent.
    """
    start = opening(journal)
    if start is None:
        return [], None, NO_RECORD
    day = None if as_of is None else str(as_of)[:10]
    if day is not None and day < str(start["date"])[:10]:
        return [], start, (
            f'this journal\'s cash record opens on {start["date"]} and has no '
            f"answer for {day} — what the account held before it started "
            "being kept is not something the record can say, and carrying the "
            "opening balance backwards would state a figure for a day nothing "
            "was recorded about")
    got = [e for e in entries(journal)
           if day is None or str(e.get("date") or "")[:10] <= day]
    unknown = sorted({str(e.get("kind")) for e in got
                      if str(e.get("kind")) not in KINDS})
    if unknown:
        return [], start, (
            "this journal's cash record holds "
            + ("an entry" if len(unknown) == 1 else "entries")
            + " this version cannot read — "
            + ", ".join(f'"{k}"' for k in unknown)
            + " — so what the account holds cannot be worked out without "
              "leaving "
            + ("it" if len(unknown) == 1 else "them")
            + " out, which would report a balance short by exactly the "
              "entries nobody could read. The record itself is untouched")
    return got, start, None


def _sum(got, flow=None) -> float:
    """What a set of entries comes to, with each kind's own direction applied.

    `flow` narrows it to one kind of money. Both reads go through here so the
    direction is applied in exactly one place — the balance and the
    contributed/earned split cannot disagree about which way a withdrawal
    went, because neither of them decides it.
    """
    total = 0.0
    for e in got:
        spec = KINDS.get(str(e.get("kind")))
        if spec is None or (flow is not None and spec["flow"] != flow):
            continue
        total += spec["direction"] * float(e.get("amount") or 0.0)
    return round(total, 2)


def _counted(got) -> str:
    """What the balance is made of, in a sentence the reader can redo.

    "then" rather than "plus": a withdrawal is one of the things counted here
    and it does not add. The sentence says what went on the record, and the
    direction of each is the kind's own business — which is the same reason
    nothing else in this module adds a sign to an amount.
    """
    tally = {}
    for e in got:
        if e.get("kind") == OPENING:
            continue
        tally[e["kind"]] = tally.get(e["kind"], 0) + 1
    parts = [f"{n} " + KINDS[k]["one" if n == 1 else "plural"]
             for k, n in tally.items()]
    if not parts:
        return "and nothing recorded since"
    if len(parts) == 1:
        return "then " + parts[0]
    return "then " + ", ".join(parts[:-1]) + " and " + parts[-1]


def balance(journal: dict, as_of: str | None = None) -> dict:
    """What the account holds in cash, on a day, or an absence saying why not.

    Derived, never stored. `as_of` of None means now; a day before the record
    opens is absent rather than answered with the opening figure, for the
    reason journals.answers_on refuses a day before the journal existed —
    carrying a figure backwards to a day nothing was recorded about is the
    carrying-forward principle 4 refuses, and it would size a backdated
    purchase against an account that did not exist.

    The whole account total is built on this and every position weight is
    measured against that total, so an absence here travels: the account is
    absent, the weight is absent, and a rule binding on weight says it cannot
    be worked out and names why. That is the honest chain, and it is why this
    never falls back to zero.
    """
    got, start, refusal = _to(journal, as_of)
    if refusal:
        return _absent(refusal)
    when = f" as at {str(as_of)[:10]}" if as_of else ""
    return _known(_sum(got), [
        f'{_usd(start["amount"])} opening balance on {start["date"]}, '
        f"{_counted(got)}{when}"])


def movement(journal: dict, since: str | None = None,
             until: str | None = None) -> dict:
    """What moved through the account over a window, split the way a return
    figure has to split it::

        {"contributed", "withdrawn", "earned", "net_external",  # known-or-absent
         "from", "until"}

    `contributed` and `withdrawn` are money crossing the account's boundary
    and are not gains or losses; `earned` is cash the holdings paid out and is.
    A return over a window is the change in what the account is worth **less
    `net_external`** — and specifically not less `earned`, which is the whole
    reason the two are reported apart. Netting a dividend out alongside a
    deposit understates what the account made by exactly the dividend, and the
    two are indistinguishable once they are added together.

    A window that starts before the record opens is absent rather than
    truncated to what is known. A partial answer here reads as a complete one
    — it is a dollar figure with nothing on it saying which months it covers —
    and a return netted against a flow figure missing its first two years is
    wrong by those two years with nothing to show for it.

    Zero is a true answer once the record is open, and it is not an invention:
    this record is append-only and total by construction, so "no deposits in
    this window" is the record accounting for the whole of it. That is the
    reading principle 4 permits — a source that demonstrably accounts for the
    whole is evidence a missing line is nil.
    """
    # Through the same reader the balance uses, so a record this build cannot
    # fully account for refuses here too rather than raising out of the middle
    # of a sum. `until` is the ceiling; the window's start is checked below.
    _got, start_entry, refusal = _to(journal, until)
    if refusal:
        return {"contributed": _absent(refusal), "withdrawn": _absent(refusal),
                "earned": _absent(refusal), "net_external": _absent(refusal),
                "from": None if since is None else str(since)[:10],
                "until": None if until is None else str(until)[:10]}

    opened = str(start_entry["date"])[:10]
    lo = opened if since is None else str(since)[:10]
    hi = None if until is None else str(until)[:10]
    if lo < opened:
        why = (f"this journal's cash record opens on {opened}, so what moved "
               f"through the account from {lo} is not something it can say. A "
               "figure covering part of the window would read as one covering "
               "all of it")
        return {"contributed": _absent(why), "withdrawn": _absent(why),
                "earned": _absent(why), "net_external": _absent(why),
                "from": lo, "until": hi}

    window = [e for e in entries(journal)
              if e.get("kind") != OPENING
              and lo <= str(e.get("date") or "")[:10]
              and (hi is None or str(e.get("date") or "")[:10] <= hi)]
    span = f'{lo} to {hi or "today"}'
    external = _sum(window, "external")
    # Reported as positive amounts moving in each direction, because "you took
    # out $4,000" is what a reader is looking for, and a signed net is what
    # arithmetic downstream wants. Both, rather than one and a note telling
    # the reader to flip the sign themselves.
    paid_in = round(sum(float(e["amount"]) for e in window
                        if KINDS[e["kind"]]["flow"] == "external"
                        and KINDS[e["kind"]]["direction"] > 0), 2)
    taken_out = round(paid_in - external, 2)
    return {
        "contributed": _known(paid_in, [f"deposits made {span}"]),
        "withdrawn": _known(taken_out, [f"withdrawals made {span}"]),
        "earned": _known(_sum(window, "earned"),
                         [f"cash your holdings paid out {span}"]),
        "net_external": _known(
            external,
            [f"{_usd(paid_in)} paid in less {_usd(taken_out)} taken out, "
             f"{span} — money that crossed the account's boundary and is "
             "neither a gain nor a loss"]),
        "from": lo, "until": hi,
    }


def ledger(journal: dict, as_of: str | None = None) -> list:
    """Every entry with what the balance stood at after it, oldest first.

    The running figure is derived here rather than stored on the entry, for
    the reason a position's share count is derived from its lots: a stored
    running total is a second opinion about a fact the entries already settle,
    and the two come apart the first time one is written without it.
    """
    got, _start, refusal = _to(journal, as_of)
    if refusal:
        return []
    out = []
    for i, e in enumerate(got):
        spec = KINDS[e["kind"]]
        # The same summation `balance` uses, over the prefix, rather than a
        # running total accumulated here. Two derivations of one figure round
        # differently the moment an amount has more than two decimal places,
        # and the screen shows both — "Free cash now $100.00" over a statement
        # whose last line reads $99.99.
        out.append({**e, "label": spec["label"], "flow": spec["flow"],
                    "recorded_by": spec["recorded_by"],
                    "direction": spec["direction"],
                    "balance": _sum(got[:i + 1])})
    return out
