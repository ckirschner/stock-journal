"""Positions as lot history, snapshots, and the override log.

A security's position is not a figure that gets updated. It is a list of
**lots** — one entry per acquisition and one per disposal, appended in the
order they were recorded and never edited afterwards. Everything anyone wants
to know about the position is derived from that list on read: how many shares
are held, which lots are still open, what the average cost was, what a lot
returned.

The rule that matters here: a snapshot is written once, at the moment a
decision is acted on, and never recomputed. If it were recomputed, restated
filings and an amended strategy would quietly rewrite history and the journal
would lose the only thing that makes it a journal. Deriving the position from
appended events rather than storing a running total is the same rule applied
one level down — a sale that edited the buy lot it drew from would be
rewriting what was bought.

The shape is designed against the three things that have to work, not against
what happens to be stored today:

- **several buys.** Each is its own lot with its own date, price, decision
  and snapshot. Adding to a position is one more append.
- **partial sells against specific lots.** A sale names how many shares it
  took from each lot (`against`), because only the user knows what they told
  their broker. The host defaults that allocation to oldest-first and says
  so; it never silently decides.
- **re-entry after a full exit.** A security whose lots are all closed keeps
  them and can take a new lot dated later. Nothing is deleted, so the second
  entry reads against the first.

Which bucket a security is in — an idea, a holding, a previous holding — is
*derived* from its lots and never stored. A stored bucket is a second
opinion about a fact the lots already settle, and the two fall out of step.

Nothing here evaluates. The caller hands in the decision it just took under
the journal's stamped strategy, and this module records it. Reading a state's
*render* to tell a purchase-with-the-signal from a purchase-against-it is not
an opinion about investing — the render types are the host's own vocabulary
and `commit` means "capital may go in" by definition. Which securities
deserve capital is the strategy's business, and this module never asks.

An entry also records **when its verdict was worked out**, and the two
answers are not interchangeable. A decision seen on the day it is dated was
seen; a decision rebuilt afterwards for a day in the past was not, however
faithfully it was rebuilt. Every figure derived from the record splits on
that line — see `recorded_as` for the case that made it load-bearing, and
`override_scorecard` for what happens to a comparison that ignores it.
"""

from __future__ import annotations

import copy
from datetime import date, datetime
from types import MappingProxyType

EXIT_REASONS = [
    "Thesis broke",
    "Hit valuation",
    "Better opportunity",
    "Risk limit",
    "Panic",
]

# What a sale with no reason on it is called, everywhere it is counted.
#
# Not one of the reasons above, and deliberately not offered when a sale is
# recorded as it happens: you were there, and the answer is the one thing the
# exit analytics cannot work without. It exists for a sale entered out of
# history, where "I do not remember why I sold in 2014" is the truth and any
# of the five above would be a guess dressed as a fact — in the record that
# exists to tell you whether your sell rules work.
#
# Named here rather than written out at each of its three call sites, because
# a reason that is spelled differently in two places is two groups in the
# scorecard for one thing that happened.
UNSTATED_REASON = "Not stated"

BUCKETS = ("holdings", "previous", "ideas")


def _today():
    return date.today().isoformat()


def _stamp():
    """When something was recorded, on the calendar the user was standing on.

    The same decision `dated.stamp` makes, for the same reason and at the same
    time: a lot's `recorded`, a snapshot's `frozen` and a note's date all sit
    beside dates the user typed — `lot["date"]`, a pin, `today` — and a stamp
    on a different calendar is a stamp that reads a day out at the boundary.
    A note written at seven in the evening west of Greenwich rendered as
    tomorrow, which is a date that has not happened yet.

    Left as UTC this would also keep the view guessing: ui/app.js compares a
    snapshot's `frozen` against a purchase date to spot a backdated entry, and
    had to allow a whole day of slack for the skew.
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def recorded_date(value, what: str) -> str:
    """The day a lot is dated, or a refusal. One rule, every writer.

    The future is refused. This is not principle 2 being weakened: that
    principle protects decisions the user actually made, and a sale dated
    2062 has not been made — it is a typo or a bad import. It is also two
    contradictory states at once, which principle 7 forbids outright: the
    position reads closed to every screen that asks, while the strategy is
    still holding it, and the account inflates by its whole value.

    Here rather than in each caller, because that is how the two paths came
    apart in the first place — the purchase screen checked and the sale
    screen did not. Every dated lot is written through this module, so a
    rule enforced at the write cannot be got round by a new caller that
    does not know it exists.
    """
    if not value:
        return _today()
    try:
        d = date.fromisoformat(str(value)[:10])
    except ValueError:
        raise ValueError(f"The {what} date must be a real date "
                         "(YYYY-MM-DD).")
    if d > date.today():
        raise ValueError(f"A {what} cannot be dated in the future — "
                         f"{d.isoformat()} has not happened yet. Check the "
                         "date.")
    return d.isoformat()


def new_security(ticker: str, name: str) -> dict:
    return {
        "ticker": ticker.upper().strip(),
        "name": name.strip(),
        "added": _today(),
        "price": None,
        "lots": [],             # append-only; the position is derived from it
        # Everything the user supplies about this security is a dated,
        # append-only record — never a slot. Each is read through its own
        # module, and the entry in force on a day is the newest one written
        # by then, so a purchase rebuilt for a past date sees what was on
        # record then and never what was written afterwards.
        "judgements": [],       # engine/judgements.py — the questions asked
        "hand_entered": [],     # engine/hand_entered.py — numbers you read
        "thesis": [],           # engine/thesis.py — why you own it
        "valuations": [],       # engine/valuation.py — what it is worth
        "notes": [],            # dated entries, appended, never edited
    }


def add_note(security: dict, text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return security
    security.setdefault("notes", []).append({"date": _stamp(), "text": text})
    return security


# -- reading the lot list ----------------------------------------------------
# Every one of these is a pure read. They are the only way anything else is
# allowed to ask what a position is, so there is one answer rather than one
# per caller.

def lots(security: dict, kind: str | None = None, on_or_before=None) -> list:
    """The recorded lots, oldest first, optionally of one kind and only
    those that had happened by a given day.

    The date filter is the clock: under a pinned evaluation a purchase made
    after the pin did not exist yet, and a sale made after it had not
    reduced anything. Sorting by date and then by the order they were
    recorded keeps two lots on the same day in the order they were entered.
    """
    out = [l for l in (security.get("lots") or [])
           if (kind is None or l.get("kind") == kind)
           and (on_or_before is None
                or str(l.get("date") or "")[:10] <= str(on_or_before)[:10])]
    return sorted(out, key=lambda l: (str(l.get("date") or ""),
                                      int(l.get("seq") or 0)))


def open_lots(security: dict, on_or_before=None) -> list:
    """Every acquisition with what remains of it, oldest first.

    A lot that has been sold down to nothing stays in the list with
    `remaining` zero, because "this was bought and then exited" is part of
    the record and a re-entry only reads against it if the earlier lot is
    still visible.

    Per lot, and only per lot: this is the reader for "what is left of each
    purchase", and every entry carries its own date, `remaining` and `open`.
    Anything asking a question about a *holding* — when it began, what it
    returned, whether it has ended — wants `cycles`, because the answer
    depends on where the position touched nothing and that boundary is not
    in this list.
    """
    remaining = {}
    buys = lots(security, "buy", on_or_before)
    for lot in buys:
        remaining[lot["id"]] = float(lot["shares"])
    for sale in lots(security, "sell", on_or_before):
        for alloc in sale.get("against") or []:
            if alloc.get("lot") in remaining:
                remaining[alloc["lot"]] -= float(alloc.get("shares") or 0)
    out = []
    for lot in buys:
        left = round(remaining[lot["id"]], 8)
        out.append({**lot, "remaining": max(left, 0.0), "open": left > 0})
    return out


def cycles(security: dict, on_or_before=None) -> list[dict]:
    """Every holding period, oldest first.

    A security is not held once. It is bought, closed, and — when the
    strategy says so again — bought back, and each of those round trips has
    its own answer to "how did that go". A period opens at the purchase that
    takes the position up from nothing and closes at the sale that returns it
    to nothing; a period with shares still in it is open and has no closing
    date.

    Derived on read, exactly like the bucket, and for the same reason: a
    stored boundary is a second opinion about a fact the lots already settle.
    Walking the running total is also what makes a backdated re-entry behave
    — a purchase dated *before* the exit means the position never reached
    nothing, so it never was two periods, and no stored marker could have
    known that in advance.
    """
    out: list[dict] = []
    cur, held = None, 0.0
    for lot in lots(security, None, on_or_before):
        if lot.get("kind") == "buy":
            if cur is None:
                cur = {"seq": len(out) + 1, "opened": lot["date"],
                       "closed": None, "open": True, "shares": 0.0,
                       "buys": [], "sells": []}
                out.append(cur)
            cur["buys"].append(lot)
            held = round(held + float(lot.get("shares") or 0), 8)
        else:
            # A sale with nothing open is refused at the door. It is skipped
            # rather than trusted here, because inventing a period around it
            # would put a holding on the record that never happened.
            if cur is None:
                continue
            cur["sells"].append(lot)
            held = round(held - float(lot.get("shares") or 0), 8)
        cur["shares"] = max(held, 0.0)
        if held <= 1e-9:
            cur.update(closed=lot["date"], open=False, shares=0.0)
            cur, held = None, 0.0
    return out


def open_cycle(security: dict, on_or_before=None) -> dict | None:
    """The holding period currently in progress, or None when nothing is
    held. There is at most one: shares are held or they are not."""
    found = [c for c in cycles(security, on_or_before) if c["open"]]
    return found[-1] if found else None


def last_exit(security: dict, on_or_before=None) -> str | None:
    """When the holding *before* the current one ended, or None.

    This is what makes something the user wrote about this security stale,
    and the current holding's own start date is not. Writing your thesis the
    week before you buy is the whole discipline — commit to the criteria
    while calm — so keying staleness on "written before this holding opened"
    would put a warning on every correctly-formed record there is. What is
    genuinely stale is something written while you owned the name a previous
    time: you sold it, the reasons you sold it are not in what you wrote,
    and buying it back is a different decision.

    Anything written in the gap — flat, between two holdings, deciding
    whether to buy back — is about the holding that followed it, so it is
    not stale either.

    Here rather than beside any one of its readers: the judgement record,
    the thesis and the valuation claim all ask the same question of the same
    lot list, and three answers to "when did the last holding end" is two
    answers too many.
    """
    periods = cycles(security, on_or_before)
    if not periods or periods[-1].get("open") is not True:
        return None
    closed = [p["closed"] for p in periods[:-1] if p.get("closed")]
    return max(closed) if closed else None


def shares_held(security: dict, on_or_before=None) -> float:
    return round(sum(l["remaining"] for l in open_lots(security, on_or_before)),
                 8)


def is_held(security: dict, on_or_before=None) -> bool:
    return shares_held(security, on_or_before) > 0


def cost_basis(security: dict, on_or_before=None):
    """The average cost per share of what is still held, or None when
    nothing is. Reporting only — it never reaches a strategy, because a rule
    that fires on the distance from your own purchase price is anchoring.
    """
    left = [l for l in open_lots(security, on_or_before) if l["open"]]
    total = sum(l["remaining"] for l in left)
    if not total:
        return None
    return sum(l["remaining"] * float(l["price"]) for l in left) / total


def opened_on(security: dict, on_or_before=None):
    """When the holding you have now began: the first purchase of the open
    period, or None when nothing is held.

    It does not move when a lot is trimmed away. Two legitimate questions were
    sharing this name — when this holding began, and how old the oldest share
    still held is — and they part company the moment the oldest lot is sold
    down to nothing. They answer different rules: a multi-year holding
    discipline is about the position, a tax boundary is about a lot. The lot
    ages are still there for anyone who wants them, on the lot list, each with
    its own date.

    A re-entry after a full exit counts from the re-entry, because that is
    where the period it belongs to opened.

    Read off the period rather than recomputed, so this and the date the
    screens show for the same holding cannot drift apart — they are one value,
    not two agreeing ones.
    """
    period = open_cycle(security, on_or_before)
    return period["opened"] if period else None


def purchases_in_holding(security: dict, on_or_before=None) -> list[dict]:
    """Every purchase that built the holding you have now, oldest first.

    The period's buys, not the security's. A name bought, exited and bought
    back has purchases belonging to a holding nobody currently owns, and a
    question about *this* holding — when it began, when you last added to it,
    what you were shown each time — must not reach them. That is the same
    boundary `opened_on` reads, off the same period, so the first entry here
    and the day the holding began are one value rather than two.

    Trimming is deliberately ignored. A lot sold down to nothing is still a
    day you looked at this business and said yes, and it is still one of the
    moments a later decision might be measured against; whether any of those
    particular shares survive is a different question, answered by
    `open_lots`.

    Empty where nothing is held. There is no period, so there is no purchase
    that built it — not "no purchases", which a security you exited last year
    would also be.
    """
    period = open_cycle(security, on_or_before)
    return list(period["buys"]) if period else []


def disposals_in_holding(security: dict, on_or_before=None) -> list[dict]:
    """Every sale that reduced the holding you have now, oldest first.

    The period's sells, not the security's, and off the same period
    `purchases_in_holding` reads — so what this holding has bought and what it
    has sold are two answers about one thing rather than two scopes that
    happen to sit beside each other.

    The pairing is the whole reason this exists rather than a filter applied
    by whoever asks. A sale carries a date and a share count and neither of
    them says which holding it ended, so a list spanning every period cannot
    be narrowed afterwards by anyone. Two securities can arrive with identical
    purchases, identical sales and identical share counts and differ only in
    where the position touched nothing — one closed out and bought back the
    same day, one added to and trimmed the same day — and the boundary that
    tells them apart is in the period walk, never on the entries. Scoping it
    here is what makes "what has this holding sold" answerable at all.

    Empty where nothing is held: there is no period, so there is no sale that
    reduced one. What the *security* has ever sold is a different question at
    a different scope, and `lots(security, "sell")` is where it is asked by
    name.
    """
    period = open_cycle(security, on_or_before)
    return list(period["sells"]) if period else []


def bucket_of(security: dict) -> str:
    """Derived, never stored. No lots is an idea; open lots is a holding;
    lots that are all closed is a previous holding."""
    if not (security.get("lots") or []):
        return "ideas"
    return "holdings" if is_held(security) else "previous"


def has_history(security: dict) -> bool:
    return bool(security.get("lots"))


# -- reading a decision ------------------------------------------------------
# Four host-owned facts, and nothing more: whether the strategy said capital
# may go in, whether it answered at all, which of the figures it cited came
# out against, and which it could not settle. All four are read off the
# contract's own vocabulary, so this module needs no view about any measure
# or level.

def _cite(item: dict) -> dict:
    """How one cited figure is named in the record. A threshold that came
    from a declared setting is named by that setting, because "your maximum
    P/E kept being overridden and it kept working out" is the finding worth
    surfacing; otherwise the subject itself is the name."""
    test = item.get("test") or {}
    src = test.get("threshold_from")
    if src:
        return {"key": f'{src["kind"]}:{src["id"]}', "label": src["label"]}
    subj = item.get("subject") or {}
    kind, sid = subj.get("kind"), subj.get("id")
    return {"key": f"{kind}:{sid}" if sid else f'stated:{subj.get("label")}',
            "label": subj.get("label") or sid or "an unnamed figure"}


def _by_outcome(decision: dict, outcome: str) -> list[dict]:
    evidence = ((decision or {}).get("reason") or {}).get("evidence") or []
    out, seen = [], set()
    for item in evidence:
        if item.get("outcome") != outcome:
            continue
        c = _cite(item)
        if c["key"] in seen:
            continue
        seen.add(c["key"])
        out.append(c)
    return out


def is_commit(decision: dict | None) -> bool:
    return bool(decision) and decision.get("render") == "commit"


def is_verdict(decision: dict | None) -> bool:
    """Whether the strategy actually answered, as opposed to the evaluation
    failing to produce an answer.

    The render tier settles most of it — a `hold`, a `reduce`, a `close` and
    a `commit` are all about the security, and `unknown` is about the
    evaluation.

    `blocked` is the one that needs asking who produced it, and getting that
    wrong matters because it feeds the scorecard that is supposed to be able
    to indict the rules. The host's own blocked states mean "we could not
    ask" — setup missing, values unresolved, the strategy not on this
    machine — and there is no verdict behind any of them. A blocked state a
    *strategy* declared is the opposite: it is a verdict, and a pointed one.
    "Read this again before adding" is an answer, and going ahead anyway is
    going against it. Counted as an absence it would sit beside purchases
    nobody could evaluate, and the one rule most worth measuring — a bar on
    adding — would be invisible in the count of times the user was right to
    overrule it.
    """
    if decision is None:
        return False
    if decision.get("tier") == "position":
        return True
    return (decision.get("render") == "blocked"
            and decision.get("produced_by") == "strategy")


# How a purchase goes on the record. Exactly one of these, always — the same
# rule principle 7 makes about a position's state, one level down: parallel
# answers to "was this an override" are how a purchase came to be counted in
# two populations at once.
#
#   commit           the strategy said capital may go in, and it went in.
#   against          a verdict was reached and the user went the other way.
#   without          no verdict could be reached, and the user — looking at
#                    that on the screen — went ahead anyway.
#   unreconstructed  no verdict could be REBUILT for a day in the past. There
#                    was nothing on any screen, because nobody was standing
#                    in front of one.
RECORDED_AS = ("commit", "against", "without", "unreconstructed")


def recorded_as(decision: dict | None, basis: str) -> str:
    """Which of the four this purchase is, given what the strategy said and
    whether that answer was seen or rebuilt.

    The basis is the whole reason this takes two arguments. "Without a
    signal" is a real decision: the screen said it could not say, the user
    read that and bought anyway, and counting it apart from a defied verdict
    is what stops a data gap reading as defiance. A *reconstruction* that
    reaches no verdict is not that decision and never was. Nobody saw
    anything — the purchase predates the journal, and the grey box is a fact
    about what this program can rebuild in 2011, not about what its owner
    ignored. Filed as an override it would put fictional entries into the
    one metric the learning loop depends on, and the moment backfill exists
    it would put a pile of them there at once: the scorecard would report
    that overriding works fine, because most of those were never decisions.

    Two arguments rather than one, and `basis` required rather than
    defaulted, because that is principle 14 here. A caller that does not say
    which moment it is recording cannot get an answer at all, so the
    "without" branch is unreachable from a reconstruction by construction
    and not by anyone remembering.
    """
    if basis not in ("live", "reconstructed"):
        raise ValueError(
            f'"{basis}" is not a basis. A decision was either seen live or '
            "reconstructed for a past day, and which one it was decides "
            "whether going ahead was an override or simply a gap in what "
            "could be rebuilt.")
    if is_commit(decision):
        return "commit"
    if is_verdict(decision):
        return "against"
    return "without" if basis == "live" else "unreconstructed"


def basis_of(lot: dict | None) -> str:
    """Whether this entry's verdict was seen on the day it is dated, or
    rebuilt for that day afterwards.

    Read off the entry's own frozen evaluation, which is the only place it
    is written. Anything that is not the word "reconstructed" is live: a
    reconstruction is stamped as one at the write and always has been, so
    the absence of a stamp can only mean an entry recorded against the data
    in front of the user. That direction is the safe one — the failure this
    guards is a reconstruction passing for a contemporaneous record, and it
    cannot happen by omission.
    """
    evaluation = ((lot or {}).get("snapshot") or {}).get("evaluation") or {}
    return "reconstructed" if evaluation.get("basis") == "reconstructed" \
        else "live"


def is_reconstructed(lot: dict | None) -> bool:
    return basis_of(lot) == "reconstructed"


def backfilled(security: dict) -> bool:
    """Whether any entry in this security's record was reconstructed rather
    than captured at the time.

    Derived from the lots on read, exactly like the bucket and the holding
    periods, and for the same reason: a stored flag is a second opinion
    about a fact the entries already settle, and the two fall out of step
    the first time one entry is added without it.
    """
    return any(is_reconstructed(l) for l in (security.get("lots") or []))


# -- writing a lot -----------------------------------------------------------

def _next_id(security: dict) -> tuple[str, int]:
    """A lot id that is never reused, even after everything is closed. Sales
    point at lots by id, so an id that came round again would silently make
    an old sale draw on a new purchase."""
    seq = int(security.get("lot_seq") or 0) + 1
    security["lot_seq"] = seq
    return f"l{seq}", seq


# What a value must carry to be frozen. Named here, by the consumer, so a
# producer that renames one of them fails at the write with this message
# rather than quietly freezing a shape nothing can read back.
# dataview.qualified() builds them.
_VALUE_KEYS = ("value", "source", "cautions", "provenance")


def _qualified_values(values) -> dict:
    """Refuse a bare number where a qualified value belongs.

    A snapshot is written once and never recomputed, so a caution filed off
    on the way in is filed off forever — the record then states a figure as
    more certain than the evidence supported, and nothing downstream can
    tell. The check is here, at the write, rather than trusted to every
    caller: a number arriving on its own is the failure this is guarding,
    and it is exactly what a new caller would hand over.
    """
    out = {}
    for eid, v in (values or {}).items():
        if not isinstance(v, dict) or not all(k in v for k in _VALUE_KEYS):
            raise ValueError(
                f'The value frozen for "{eid}" is a bare '
                f"{type(v).__name__}. A snapshot records what a figure was "
                "and what qualified it — its source, its provenance and any "
                "caution on it — because the record can never be asked "
                "again. Build it with dataview.qualified().")
        out[eid] = copy.deepcopy(v)
    return out


def _dated_entry(entry, what: str):
    """Refuse naked prose where a dated entry belongs.

    Same guarantee as `_qualified_values` above, for the other half of what
    a lot freezes. A thesis or a valuation arriving as a bare string or as a
    dict with no `recorded` on it is one that was read from somewhere other
    than its own append-only record — and a frozen copy that cannot say
    which version it was, or when that version was written, is a copy the
    record can never be reconciled against.
    """
    if entry is None:
        return None
    if not isinstance(entry, dict) or "recorded" not in entry \
            or "seq" not in entry:
        raise ValueError(
            f"The {what} frozen onto this lot is a bare "
            f"{type(entry).__name__}. A purchase records which version was "
            "standing and when it was written, so it must be an entry off "
            f"the {what} record — not the text of one.")
    return copy.deepcopy(entry)


_RECOLLECTION_IS_NOT_A_THESIS = (
    "A recollection is what you remember thinking, written now about a day "
    "that has passed. There is nothing to remember about a decision being "
    "made today — write a thesis, on the record that keeps every version of "
    "it and demands a reason for every change. Offering this here would be "
    "a way round that record, and a thesis you can write after the fact is "
    "a thesis nothing can be graded against.")


def _recollection(text, basis: str) -> dict | None:
    """What the user remembers thinking, or a refusal.

    Only on a reconstruction, and refused outright anywhere else. This is
    the one place hindsight is allowed into the record, so the boundary is
    a raise rather than a convention: the thesis record is what an override,
    an exit and a falsifier are all graded against, and a prose field that
    could reach a live purchase would be a second, undated, unamendable
    version of it sitting where the first one belongs.

    It is never the thesis and is never stored as one. The lot keeps it
    under its own name, carrying the day it was actually written, so no
    reader looking for the case that was made at the time can find this
    instead. Backdating the writing is not possible anywhere in this
    program, and nothing here is an exception to that — only the subject is
    in the past.
    """
    text = str(text or "").strip()
    if not text:
        return None
    if basis != "reconstructed":
        raise ValueError(_RECOLLECTION_IS_NOT_A_THESIS)
    return {"text": text, "written": _stamp()}


def _snapshot(decision, values, price_seen, evaluation,
              thesis=None, valuation=None, recollection=None) -> dict:
    return {
        "frozen": _stamp(),
        # The decision, entire. Everything the screen showed — state, payload
        # and the resolved reason with every figure it cited — is here, so
        # the record explains itself with no strategy on disk to ask.
        "decision": copy.deepcopy(decision),
        "strategy": copy.deepcopy((decision or {}).get("strategy")),
        # Every value behind the decision, each with its source, its
        # provenance and any caution on it. One object per figure rather
        # than a number here and a source label in a table beside it: two
        # structures describing one value are two structures that can come
        # apart, and the half that goes missing is always the qualifying
        # half.
        "metrics": _qualified_values(values),
        # What was SEEN: the effective price (hand-entered over fetched),
        # with its source, its date and the instrument it belongs to — not
        # just the hand-entered field.
        #
        # The symbol is here because a company can have several share classes
        # at several prices, and a frozen record that says only "$470" cannot
        # afterwards be told from one that should have said $705,000. This
        # record is append-only and never recomputed, so anything it cannot
        # say now it can never be asked later.
        "price": (price_seen or {}).get("value"),
        "price_source": (price_seen or {}).get("source"),
        "price_date": (price_seen or {}).get("date"),
        "price_ticker": (price_seen or {}).get("ticker"),
        "evaluation": copy.deepcopy(evaluation),
        # What the user believed, and what they thought it was worth, on the
        # day this was recorded — the version standing then, not the version
        # standing now. Both are whole entries off their own append-only
        # records, carrying their own `seq` and `recorded`, so this copy can
        # always be pointed back at the amendment it came from.
        #
        # A copy rather than a reference by seq, for the same reason the
        # values above are copied: the record has to explain itself with
        # nothing else on hand. The valuation's copy is the one place the
        # solved number is written down instead of derived, because a later
        # change to how a DCF is computed must not restate a decision made
        # two years ago.
        "thesis": _dated_entry(thesis, "thesis"),
        "valuation": _dated_entry(valuation, "valuation"),
        # What the user remembers thinking, on a purchase they are entering
        # from their own history. Deliberately not merged into `thesis`
        # above, and deliberately carrying its own writing date: the two
        # answer the same question from opposite sides of the outcome, and
        # a record that could not tell them apart would let a case composed
        # with hindsight be read as the case that was made at the time.
        "recollection": copy.deepcopy(recollection),
    }


def add_lot(security: dict, decision: dict, shares: float, price: float,
            opened: str | None = None, override_reason: str = "",
            values: dict | None = None,
            price_seen: dict | None = None,
            evaluation: dict | None = None,
            thesis: dict | None = None,
            valuation: dict | None = None,
            recollection: str = "") -> dict:
    """Record a purchase as its own lot, and freeze the decision that was on
    screen for it — or the one that could not be rebuilt for it.

    A decision that does not say commit does not block anything. Where the
    user saw it and went ahead, it is recorded as an override with their
    stated reason — including going ahead on a state nobody could evaluate,
    which is its own kind of override and is kept apart from the other.

    Where the decision was *reconstructed* and produced no verdict, there was
    no override, because there was nothing on any screen to override. The lot
    records that the evaluation could not be rebuilt, and says why. See
    `recorded_as`: this is the distinction the whole learning loop rests on,
    and backfill is what would otherwise flood it.

    `values` are the merged values behind the decision — hand-entered over
    computed — each one qualified: what it was, which side it came from, how
    it was derived and anything that was wrong with it. Built by
    dataview.merged_values; a bare number is refused.

    `evaluation` says which moment those belong to: basis "live" (the data on
    screen right now) or "reconstructed" (rebuilt from what was observable on
    a past purchase date), with `as_of` naming the day. The record must never
    claim a verdict was seen live when it was rebuilt later.

    `thesis` and `valuation` are the versions that were standing on the day
    being recorded, off their own append-only records. The thesis belongs to
    the position and carries on to the next purchase; the valuation belongs
    to *this* purchase and to no other, which is why it is frozen here and
    never averaged into a figure about the holding.

    `recollection` is what the user remembers thinking, on a purchase they
    are entering out of their own history. It is refused on a live purchase
    outright — see `_recollection` — and it is never the thesis.
    """
    shares, price = float(shares), float(price)
    if shares <= 0:
        raise ValueError("A purchase has to be more than zero shares.")
    when = recorded_date(opened, "purchase")
    evaluation = copy.deepcopy(evaluation) if evaluation \
        else {"basis": "live", "as_of": _today()}
    remembered = _recollection(recollection, evaluation["basis"])

    lot_id, seq = _next_id(security)
    lot = {
        "id": lot_id,
        "seq": seq,
        "kind": "buy",
        "date": when,
        "recorded": _stamp(),
        "shares": shares,
        "price": price,
        # Two fields rather than one with a kind on it, because they are two
        # populations rather than two flavours of one. An override belongs
        # in the comparison that asks whether going against the tool paid;
        # an entry whose evaluation could not be rebuilt has no counterpart
        # to compare against and belongs nowhere near it. A single field
        # would put them in the same list and leave every reader to
        # remember to split it.
        "override": None,
        "unreconstructed": None,
        "snapshot": _snapshot(decision, values, price_seen, evaluation,
                              thesis, valuation, remembered),
    }

    how = recorded_as(decision, evaluation["basis"])
    state = (decision or {}).get("state") or {}
    named = state.get("name") or state.get("id") or "no verdict"
    who = (((decision or {}).get("strategy") or {}).get("name")
           or "the strategy")
    reason = (decision or {}).get("reason") or {}

    if how in ("against", "without"):
        lot["override"] = {
            "date": lot["date"],
            "kind": how,
            "state": named,
            "rule": reason.get("rule"),
            "summary": reason.get("summary"),
            "basis": evaluation["basis"],
            "as_of": evaluation["as_of"],
            "strategy": copy.deepcopy((decision or {}).get("strategy")),
            "failed": _by_outcome(decision, "fail"),
            "missing": _by_outcome(decision, "unknown"),
            "reason": (override_reason or "").strip() or "No reason given.",
        }
    elif how == "unreconstructed":
        lot["unreconstructed"] = {
            "date": lot["date"],
            "as_of": evaluation["as_of"],
            "state": named,
            # The strategy's own sentence about why it could not answer, or
            # the host's. Kept verbatim: "no filings had been filed by then"
            # and "the strategy is not installed on this machine" send the
            # reader to different places, and a summary written here would
            # have to guess which.
            "why": reason.get("summary") or "No reason was given.",
            "strategy": copy.deepcopy((decision or {}).get("strategy")),
            "missing": _by_outcome(decision, "unknown"),
            # What the reconstruction could and could not consult, frozen
            # beside the failure it explains. The record is written once and
            # can never be asked again what it was working from.
            "note": evaluation.get("note"),
        }

    security.setdefault("lots", []).append(lot)

    if how == "commit":
        # The state can move between the preview and the commit — a fetch
        # lands, the strategy is upgraded — and the user may already have
        # written why they were going ahead against the old one. That
        # sentence is theirs and is kept, rather than dropped because the
        # answer improved while they were typing. Kept on a reconstruction
        # too, and checked before the early return below: the sentence
        # belongs to the person who wrote it whichever clock the verdict was
        # worked out on.
        if (override_reason or "").strip():
            add_note(security,
                     "Recorded with the signal. The reason written while the "
                     "verdict still read otherwise: "
                     + override_reason.strip())
        return lot

    if evaluation["basis"] == "reconstructed":
        # No note. See `note_recording`: an entry made out of history is
        # narrated once for the whole act of recording, not once per entry.
        # A ten-event backfill writing ten near-identical notes stamped
        # today would bury every note the user actually wrote under a wall
        # of machinery, and each of those sentences already sits on its own
        # entry, beside the purchase it is about — including the stated
        # reason for an override, which the notice renders in place.
        return lot

    what = "against the signal" if how == "against" else "without a signal"
    add_note(security,
             f"Bought {what} ({named} under {who}). Stated reason: "
             f"{lot['override']['reason']}")
    return lot


def note_recording(security: dict, entries: list[dict]) -> dict | None:
    """One note for one act of recording, however many entries it wrote.

    Only for entries made out of history. An entry captured as it happens
    narrates itself where it is written, because it is one line about one
    thing that just happened. A backfill is one thing that just happened too
    — somebody sat down and typed in six years of a position — and writing a
    line per entry would put six near-identical sentences, all stamped
    today, above every note the user has ever actually written. The Journal
    panel is the human narrative, and burying it under machinery is how it
    stops being read.

    Everything specific to an entry stays on the entry, where a reader
    looking at a 2014 purchase will be standing. This is only the sentence
    that says the typing happened, and when.

    Returns None where there was nothing to narrate, so a live recording can
    call it without a condition.
    """
    made = [l for l in (entries or []) if is_reconstructed(l)]
    if not made:
        return None
    days = sorted(str(l.get("date") or "")[:10] for l in made)
    span = days[0] if days[0] == days[-1] else f"{days[0]} to {days[-1]}"
    buys = sum(1 for l in made if l.get("kind") == "buy")
    sells = len(made) - buys
    what = ", ".join(
        f"{n} {word if n == 1 else word + 's'}"
        for n, word in ((buys, "purchase"), (sells, "sale")) if n)
    dark = sum(1 for l in made if l.get("unreconstructed"))
    could_not = (
        f" {dark} of {'them' if len(made) > 1 else 'these'} could not have a "
        "verdict reconstructed, so none is recorded against "
        f"{'them' if dark > 1 else 'it'}." if dark else "")
    add_note(security,
             f"Recorded from history: {what}, dated {span}. Each was judged "
             "against the data available on its own day, not against "
             "today's." + could_not)
    return security["notes"][-1]


# -- exits -------------------------------------------------------------------

def allocate(security: dict, shares: float, on_or_before=None) -> list[dict]:
    """Which lots a sale of `shares` draws on, oldest first.

    Oldest-first is the host's stated default, not a tax opinion: something
    has to be proposed, and the alternative is asking a question most people
    cannot answer about a single-lot position. A caller that knows what was
    actually sold passes its own allocation instead, and the record keeps
    whichever arrived.

    Two clocks, deliberately. What a lot has *left* counts every sale ever
    recorded, so no lot can go negative whichever order things were entered
    in. What a lot is *eligible* for stops at the sale's own date, so a sale
    dated in March cannot draw on shares bought in June.
    """
    remaining = {l["id"]: l["remaining"] for l in open_lots(security)}
    left, out = float(shares), []
    for lot in lots(security, "buy", on_or_before):
        if left <= 0:
            break
        take = min(remaining.get(lot["id"], 0.0), left)
        if take <= 0:
            continue
        out.append({"lot": lot["id"], "shares": round(take, 8)})
        left = round(left - take, 8)
    return out


def _check_allocation(security: dict, shares: float, against: list) -> None:
    """Refuse an allocation that does not add up.

    This is not a gate on a decision — nothing here asks whether selling was
    wise. It is arithmetic: shares that were never recorded as bought cannot
    be recorded as sold without every derived figure below becoming
    fiction. The message says which purchase is missing, because that is the
    fix.
    """
    available = {l["id"]: l["remaining"] for l in open_lots(security)}
    total = 0.0
    for alloc in against:
        lot_id, n = alloc.get("lot"), float(alloc.get("shares") or 0)
        if lot_id not in available:
            raise ValueError(
                f'This sale names lot "{lot_id}", which is not a recorded '
                f"purchase of {security['ticker']}.")
        if n <= 0:
            raise ValueError("Each lot in a sale has to give up more than "
                             "zero shares.")
        if n > available[lot_id] + 1e-9:
            raise ValueError(
                f"That sale takes {n:g} shares from a lot holding "
                f"{available[lot_id]:g}. Record the purchase those shares "
                "came from first — the journal cannot sell shares it was "
                "never told about.")
        available[lot_id] -= n
        total += n
    if abs(total - float(shares)) > 1e-9:
        raise ValueError(
            f"The lots named give up {total:g} shares, but the sale is for "
            f"{float(shares):g}.")


def sell_lots(security: dict, decision: dict | None, reason: str,
              shares: float | None, exit_price: float,
              exited: str | None = None,
              against: list | None = None,
              values: dict | None = None,
              price_seen: dict | None = None,
              evaluation: dict | None = None,
              thesis: dict | None = None) -> dict:
    """Record a sale against specific lots, keeping the ticker in the journal.

    A partial sale leaves the position open and the remaining lots intact; a
    sale of everything leaves a security with closed lots, which is what
    makes it a previous holding and what a re-entry later reads against.

    **`shares` None means everything held on the sale's own date**, and the
    resolution is here rather than at the caller for the reason every other
    rule about a dated entry is here. "Sell everything" is a question about a
    day, and the only clock a caller reaching for it has to hand is today's:
    the screen said sixty shares, so sixty is what went into an exit dated
    two years back that ended a hundred. Nothing about that write is loud —
    the sale is smaller than the bound, so it records, and the holding period
    it was supposed to close stays open with a forty-share residue nobody
    ever owned. The date is worked out in this function; so, now, is the
    count, and a caller cannot hand over the wrong clock because it no longer
    hands over one at all.

    The decision frozen here is the one the journal's own strategy produced
    for the day the sale is dated — there is only ever one, because a journal
    has one strategy and it does not change. Where the strategy could not be
    asked at all (it is not installed on this machine), that absence is
    recorded as itself rather than as a signal that read clear.

    **A backdated sale is judged with the data of its own day**, exactly as a
    backdated purchase is. `evaluation` says which: basis "live" for a sale
    recorded as it happens, "reconstructed" for one entered afterwards, with
    `as_of` naming the day. That is not a nicety — `rule_triggered` and
    `signal_at_exit` are what the panic-sell loop reads, and an exit dated
    2019 carrying today's verdict states that the strategy said something on
    a day it was never asked about.

    Where the reconstruction reaches no verdict, `rule_triggered` is None and
    stays None. "No rule triggered this exit" would claim a signal was read
    and came back clear; the honest record is that nothing could be rebuilt,
    and the note says which of the two it was.

    The thesis standing at the sale is frozen with it, because this is where
    it gets graded: "did the falsifier fire, or did I talk myself out of it"
    is a question about the version that was on record when the sell button
    was pressed. Under a reconstruction that is the version on record on the
    sale's own date — never one amended since, which would grade a prediction
    against a revision made after the answer was known. No valuation is
    frozen here — a claim is the case for a purchase, and attaching one to an
    exit would invent a number the sale was never justified by.
    """
    exit_price = float(exit_price)
    when = recorded_date(exited, "sale")
    held = shares_held(security)
    if held <= 0:
        raise ValueError(f"No shares of {security['ticker']} are recorded as "
                         "held, so none can be sold.")
    then = shares_held(security, when)
    if shares is None:
        if then <= 0:
            raise ValueError(
                f"No shares of {security['ticker']} were held on {when}, so "
                "a sale dated then cannot be for everything held — there was "
                "nothing to sell. Check the date, or say how many shares "
                "went.")
        if then > held + 1e-9:
            # The day's own count, against shares a later entry has already
            # sold. Refused with its own sentence rather than falling through
            # to the bound below, whose message tells the user to record the
            # purchase the extra shares came from — advice that is right when
            # somebody typed a number too large and nonsense here, where the
            # purchase is on the record and a later sale is what spent it.
            # The two entries cannot both be true, and which of them is wrong
            # is not the host's to guess.
            raise ValueError(
                f"On {when} this journal held {then:g} shares of "
                f"{security['ticker']} and {held:g} are left now, because "
                "entries dated later have already sold some of them. Selling "
                "everything held that day would sell the same shares twice — "
                "say how many shares this sale was for, or check the date.")
        shares = then
    shares = float(shares)
    if shares <= 0:
        raise ValueError("A sale has to be more than zero shares.")
    # Both bounds, in this order, because they answer different questions and
    # the first one is the fix more often. What is *left* counts every sale
    # ever recorded, so nothing can be sold twice. What was *held on the day*
    # stops at the sale's own date, which is what a re-entry breaks apart: a
    # journal holding a hundred shares bought back last year will happily
    # accept a hundred-share exit backfilled into a period when ten were
    # held, and every figure derived from that period is then fiction.
    #
    # Caught here rather than falling through to the allocation, so the most
    # common ways to get this wrong get a message that names the fix instead
    # of one about lots the user never saw.
    if shares > held + 1e-9:
        raise ValueError(
            f"This journal holds {held:g} shares of {security['ticker']} and "
            f"the sale is for {shares:g}. Record the purchase the extra "
            "shares came from first — the journal cannot sell shares it was "
            "never told about.")
    if shares > then + 1e-9:
        raise ValueError(
            f"This journal held {then:g} shares of {security['ticker']} on "
            f"{when} and the sale is for {shares:g}. A sale cannot take more "
            "than was held on its own date — record the purchase those "
            "shares came from first, or check the date.")
    if against:
        against = list(against)
    else:
        against = allocate(security, shares, when)
        # The two bounds above can both pass and still leave nothing to draw
        # on: shares held on the sale's date, already spent by a sale recorded
        # later. Re-entry is what puts a user in front of this — backfilling
        # an exit into a period that is already accounted for. Said here, in
        # terms of dates, rather than left to the allocation check, whose
        # message is about lot ids nobody has seen.
        taken = round(sum(a["shares"] for a in against), 8)
        if taken < shares - 1e-9:
            raise ValueError(
                f"On {when} this journal held shares of "
                f"{security['ticker']} that a later entry has already sold, "
                f"so only {taken:g} of the {shares:g} can be drawn on. Check "
                "the date, or record the purchase the rest came from.")
    _check_allocation(security, shares, against)
    for alloc in against:
        bought = next((l for l in lots(security, "buy")
                       if l["id"] == alloc["lot"]), None)
        if bought and str(bought["date"])[:10] > str(when)[:10]:
            raise ValueError(
                f"This sale is dated {when} and draws on shares bought on "
                f'{bought["date"]}. A sale cannot take shares that had not '
                "been bought yet.")

    evaluation = copy.deepcopy(evaluation) if evaluation \
        else {"basis": "live", "as_of": _today()}
    rebuilt = evaluation.get("basis") == "reconstructed"

    if decision is None:
        signal, rule_triggered, strategy = "Strategy not installed", None, None
    else:
        state = decision.get("state") or {}
        signal = state.get("name") or state.get("id") or "no verdict"
        strategy = copy.deepcopy(decision.get("strategy"))
        if not is_verdict(decision):
            # No verdict was reached at all — the strategy could not be
            # asked, could not answer, or could not be rebuilt for the day
            # this sale is dated. That is an absence, and it is recorded as
            # one. Calling it "no rule triggered this exit" would claim a
            # signal was read and came back clear, which is the difference
            # between a fact and a fabrication.
            #
            # Read through `is_verdict` rather than off the tier, so a
            # strategy's own blocked state — "read this again before you
            # act" — counts as the answer it is, on the sale exactly as on
            # the purchase.
            rule_triggered = None
        else:
            # An exit the strategy called for: it said to leave, in whole or
            # in part. Everything else is an exit the user reached on their
            # own, which is what the exit scorecard exists to measure.
            rule_triggered = decision.get("render") in ("close", "reduce")

    lot_id, seq = _next_id(security)
    lot = {
        "id": lot_id,
        "seq": seq,
        "kind": "sell",
        "date": when,
        "recorded": _stamp(),
        "shares": shares,
        "price": exit_price,
        "against": against,
        "reason": reason,
        "signal_at_exit": signal,
        "rule_triggered": rule_triggered,
        "strategy": strategy,
        "snapshot": _snapshot(decision, values, price_seen, evaluation,
                              thesis=thesis),
    }
    security.setdefault("lots", []).append(lot)

    # Whether this sale trimmed or closed is a fact about the holding it
    # ended, so it is read on the sale's own clock. Asking what is held
    # *now* would call a backfilled exit a trim because the user has since
    # bought back — putting a sentence in the append-only record that says
    # the position stayed open when it did not.
    partial = shares_held(security, when) > 0
    did = "Trimmed" if partial else "Closed"
    if rebuilt:
        # No note. See `note_recording`: an entry made out of history is
        # narrated once for the whole act of recording, not once per entry,
        # and everything specific to this sale is on the sale.
        return lot
    if rule_triggered is False:
        who = (strategy or {}).get("name") or "the strategy"
        add_note(security, f"{did} with no rule triggering it. {who} read "
                           f"{signal} at the time.")
    elif rule_triggered is None:
        add_note(security, f"{did} with no verdict to go on — {signal}. No "
                           "signal could be evaluated at the time, and that "
                           "absence is on the record rather than papered "
                           "over.")
    return lot


# -- returns -----------------------------------------------------------------
# Every return says what it rests on, and absence never becomes zero. A lot
# with shares still open cannot be scored without a current price, and a
# position that silently returned 0% would be the most confidently wrong
# number on the screen.
#
# A return that cannot be worked out says WHY, in the shape every other figure
# the host reports uses: {status: "known", value} or {status: "absent",
# reason}. It used to be a bare `float | None`, and five different facts came
# back as the same None — nobody has fetched a price, the price on record is
# not a price, this purchase was recorded at nothing, one purchase of five
# was, the security was never bought at all. Those have different fixes and
# different blame, and a reader given one em-dash for all of them cannot act
# on any of them.
#
# The price arrives as the host's own price view rather than as a bare float,
# and that is the structural half. `price_view` already words each absence
# precisely — naming the sibling share classes that ARE priced, or saying
# that the figure on record is not a price and how to clear it — and those
# sentences were dropped at the call site and re-guessed in the browser,
# where the guess was wrong for every absence except one. The number cannot
# travel without its reason if there is no way to hand over the number alone.

def _known(value, provenance=None) -> dict:
    return {"status": "known", "value": value,
            "provenance": list(provenance or [])}


def _absent(reason: str) -> dict:
    return {"status": "absent", "reason": reason}


def _price_of(price) -> tuple:
    """(figure, why there isn't one) from the host's price view.

    A bare number is still accepted, because a caller with a price and no
    view of it is not lying about anything — it just has a duller sentence to
    offer when there is nothing there.
    """
    if isinstance(price, dict):
        value = price.get("value")
        if value is None or float(value) <= 0:
            return None, (price.get("reason")
                          or "no price is on record for this security")
        return float(value), None
    if price is None:
        return None, "no price is on record for this security"
    if float(price) <= 0:
        return None, (f"the price on record is {float(price):g}, which is "
                      "not a price")
    return float(price), None


def _gain_and_cost(security: dict, lot: dict, price):
    """One acquisition as (gain, cost) in currency, or an absence with the
    reason it could not be worked out honestly.

    The realised part comes from the sales that drew on this lot, at the price
    each of them got. The open part is marked at the price passed in. A lot
    with shares still open and no price has no answer, and neither has a lot
    that cost nothing — a change measured from nothing has no value.

    Currency rather than a percentage, because this is what an aggregate has
    to be built from. Adding up percentages that have each been rounded, and
    re-expanding them against their costs, is not the same arithmetic as
    adding up the money.
    """
    cost = float(lot["shares"]) * float(lot["price"])
    if cost <= 0:
        return _absent(
            f'the purchase on {lot["date"]} is recorded at '
            f'{float(lot["price"]):g} a share, so there is nothing to measure '
            "a change against — check what it actually cost")
    gain, sold = 0.0, 0.0
    for sale in lots(security, "sell"):
        for alloc in sale.get("against") or []:
            if alloc.get("lot") != lot["id"]:
                continue
            n = float(alloc.get("shares") or 0)
            gain += n * (float(sale["price"]) - float(lot["price"]))
            sold += n
    left = round(float(lot["shares"]) - sold, 8)
    if left > 0:
        # Open shares need a price to be marked at, and nothing-or-less is not
        # one. Marking them at zero would report a confident -100% on a
        # position nobody has valued, which is the most believable wrong number
        # this module can produce.
        mark, why = _price_of(price)
        if mark is None:
            return _absent(f"{left:g} of these shares are still held and "
                           f"{why}")
        gain += left * (mark - float(lot["price"]))
    return gain, cost


def _is_absent(x) -> bool:
    return isinstance(x, dict) and x.get("status") == "absent"


def lot_return(security: dict, lot: dict, price) -> dict:
    """One acquisition's return, in percent, or absent with the reason."""
    got = _gain_and_cost(security, lot, price)
    if _is_absent(got):
        return got
    return _known(round(got[0] / got[1] * 100, 2))


def _weighted(security: dict, buys: list[dict], price, whole: str) -> dict:
    """Several acquisitions as one figure, weighted by what each cost.

    Absent if any of them is, because a subset average presented as the whole
    is a fabrication — and the absence names the purchase that could not be
    scored, because with five buys in a period "this cannot be worked out" on
    its own leaves nobody knowing which one to look at.

    Summed as money and divided once, rather than as each lot's already-rounded
    percentage re-expanded against its cost. The old arrangement made the
    aggregate a figure derived from displayed figures rather than from the
    underlying ones, so a period could report a return that its own lots did
    not add up to — off only in the last place, which is exactly the kind of
    wrong number nobody notices.
    """
    total_cost, total_gain = 0.0, 0.0
    for lot in buys:
        got = _gain_and_cost(security, lot, price)
        if _is_absent(got):
            return _absent(
                f'{whole} cannot be worked out: {got["reason"]}. Averaging '
                "the purchases that could be scored would present part of it "
                "as the whole.")
        total_gain += got[0]
        total_cost += got[1]
    if total_cost <= 0:
        return _absent(f"no purchase of this security is on record, so "
                       f"{whole} is not a question with an answer yet")
    return _known(round(total_gain / total_cost * 100, 2))


def cycle_return(security: dict, cycle: dict, price) -> dict:
    """What one holding period returned, weighted by what each purchase in it
    cost — or absent, saying which purchase stopped it and why.

    This is the figure a round trip is judged by, and it is per period rather
    than per security on purpose: a name bought, closed at a loss and bought
    back is two trades, and one percentage covering both describes neither. A
    closed period is entirely realised and needs no price; an open one is
    marked at the price passed in, and is absent without one.
    """
    return _weighted(security, cycle.get("buys") or [], price,
                     "what this holding period returned")


def position_return(security: dict, price) -> dict:
    """The security's return over its whole life — every lot it ever had,
    across every holding period, weighted by what each one cost.

    A lifetime figure, and only ever presented as one. Where the question is
    about the position in front of you, `cycle_return` on the open period is
    the honest answer; this one blends a finished trade into a live one and
    would read as the current position's return if it were put in that
    column.
    """
    return _weighted(security, lots(security, "buy"), price,
                     "what this security has returned over its whole life")


def sale_return(security: dict, sale: dict) -> dict:
    """What the shares in one sale returned while they were held, weighted
    across the lots it drew on."""
    cost, proceeds = 0.0, 0.0
    by_id = {l["id"]: l for l in lots(security, "buy")}
    for alloc in sale.get("against") or []:
        lot = by_id.get(alloc.get("lot"))
        if lot is None:
            # Not a data gap. The sale points at a purchase that is not in
            # the record, which is the record contradicting itself, and it
            # reads differently from a price nobody has fetched.
            return _absent(f'this sale draws on lot "{alloc.get("lot")}", '
                           "which is not a purchase this journal holds")
        n = float(alloc.get("shares") or 0)
        cost += n * float(lot["price"])
        proceeds += n * float(sale["price"])
    if cost <= 0:
        return _absent("the purchases this sale drew on are recorded at "
                       "nothing, so there is no base to express a return "
                       "against")
    return _known(round((proceeds / cost - 1) * 100, 2))


def cycle_exit(security: dict, cycle: dict) -> dict | None:
    """How a holding period ended: what it got out at on average, when
    nothing was left, and every reason given along the way.

    None for a period still open. An open period may hold trims, and a trim
    is not an ending — reporting the last trim's price as this holding's exit
    would put a conclusion on a position still being held.

    **The price is share-weighted across every sale that closed the period.**
    The last sale's price is one sliver's price: sell ninety at $150 and the
    final ten at $55 and it reports $55 for a holding that realised $140.50.
    Worse, it sat on the same strip as a return computed from all the sales,
    so the card contradicted its own arithmetic and left the reader to work
    out which half to believe.

    **The date is the last sale's**, because that is the day nothing was
    held — the one thing the final sliver genuinely does settle.

    **Every reason is kept.** A position trimmed on a risk limit and closed
    on a broken thesis gave two answers and both are true; picking one loses
    which shares each was about, and joining them into a sentence loses the
    weights. Each carries the shares it accounts for, so a reason behind 5%
    of an exit cannot read like the reason behind all of it.

    **Every reason says which of its sales were reconstructed.** A holding
    closed in stages can have been closed partly at the time and partly from
    memory afterwards, and the two are different evidence about the same
    exit. Carried per reason rather than once for the whole exit, because the
    reason is what the panic-sell loop groups on: "Panic, 40% of the exit"
    means one thing when it was typed while the screen said hold and another
    when it was entered years later out of a brokerage statement.

    Absent, with its reason, wherever the mean cannot be built honestly — a
    sale recorded at nothing makes the whole mean absent rather than dragging
    it toward zero. That is the rule `_weighted` obeys one level up, and for
    the same reason: an average over the sales that happened to have a price
    is a subset presented as the whole.
    """
    if cycle.get("open") or not cycle.get("sells"):
        return None
    sells = list(cycle["sells"])
    shares = round(sum(float(s.get("shares") or 0) for s in sells), 8)

    reasons: list[dict] = []
    for sale in sells:
        text = sale.get("reason") or UNSTATED_REASON
        n = float(sale.get("shares") or 0)
        rebuilt = 1 if is_reconstructed(sale) else 0
        hit = next((r for r in reasons if r["reason"] == text), None)
        if hit is None:
            reasons.append({"reason": text, "shares": n, "sales": 1,
                            "reconstructed": rebuilt})
        else:
            hit["shares"] = round(hit["shares"] + n, 8)
            hit["sales"] += 1
            hit["reconstructed"] += rebuilt
    for r in reasons:
        r["share"] = round(r["shares"] / shares * 100, 1) if shares else None

    # A sale recorded at nothing is a real entry and goes into the mean at
    # nothing, which is what the position actually got for those shares. It
    # is the same distinction the rest of this module already draws: a sale
    # at nought is a fact `sale_return` reads as −100%, while a sale with no
    # price at all is a figure nobody recorded. Only the second is an
    # absence, and only the second could make the mean a fabrication.
    missing = [s for s in sells if s.get("price") is None]
    if not shares:
        exit_price = _absent("the sales that closed this holding are recorded "
                             "for no shares, so there is nothing to weight a "
                             "price across")
    elif missing:
        exit_price = _absent(
            f'the sale on {missing[0]["date"]} has no price on the record, '
            "so what this holding got out at cannot be worked out. Averaging "
            "the sales that do have one would be part of the exit presented "
            "as all of it.")
    else:
        exit_price = _known(
            round(sum(float(s["price"]) * float(s.get("shares") or 0)
                      for s in sells) / shares, 4),
            # Each sliver names its day, its price and — where it applies —
            # that its verdict was rebuilt rather than seen. The price itself
            # is a recorded fact either way: what the user got is what the
            # user got, and nothing here reconstructs it. What was rebuilt is
            # the signal the sale was recorded against, and the provenance
            # line is the one place a reader can see which sales carried one.
            [f'{float(s.get("shares") or 0):g} at '
             f'{float(s["price"]):,.2f} on {s["date"]}'
             + (" (reconstructed)" if is_reconstructed(s) else "")
             for s in sells])

    return {"date": cycle["closed"], "sales": len(sells), "shares": shares,
            "price": exit_price, "reasons": reasons,
            # How much of this exit was entered from history rather than
            # captured as it happened. Counted in sales rather than shares
            # because that is the unit a reason is given in.
            "reconstructed": sum(1 for s in sells if is_reconstructed(s))}


def bought_again_after(security: dict, sale: dict) -> dict | None:
    """The first purchase recorded after a sale, or None if the user never
    bought the name again. Ordered by date and then by the order things were
    entered, so a sale and a purchase on the same day read in the order they
    happened.

    Any purchase, not only one that reopened a closed position. Buying back
    into a name you exited and adding after a trim are the same fact for this
    question: from that point the price is moving on shares you chose to own,
    so it is no longer telling you anything about the sale. What it is *not*
    is proof that the position had closed — which is why nothing here or
    downstream may call it "buying it back".
    """
    after = (str(sale.get("date") or "")[:10], int(sale.get("seq") or 0))
    for lot in lots(security, "buy"):
        if (str(lot.get("date") or "")[:10], int(lot.get("seq") or 0)) > after:
            return lot
    return None


def since_sale(security: dict, sale: dict, price) -> dict:
    """What the shares did after they were sold, over the window that is
    honestly about the sale.

    A closed position keeps being priced, because watching what happened next
    is the only way to find out whether a sell rule works. But the window has
    an end. Once the user bought the name again, the move from there belongs
    to the shares they chose to own — running the window on to today would
    credit the sell rule with a stretch spent holding, and a rule given the
    credit for your own later purchase cannot be judged at all.

    A window that ends at a purchase needs no price and no fetch: it ends at
    what the user actually paid, which is a recorded fact rather than a
    reconstruction. An open one is marked at the price passed in.

    Every way this can fail to produce a figure produces an absence with its
    own reason instead — including the two that look like numbers. A sale or a
    purchase recorded at nothing is a real entry, not a missing one, but it
    cannot stand for what the price was: a change measured from nothing has no
    value, and free shares say nothing about the market. Reporting either as
    -100% would put a fabricated figure into the evidence that judges the sell
    rules, which is the one place it would be believed.

    Returns the figure with the window it rests on, because "up 40% since you
    sold" and "up 40% between selling and buying again" are different claims
    and only one of them is true.
    """
    back = bought_again_after(security, sale)
    mark, why = _price_of(price)
    end = {"until": "purchase", "date": back["date"],
           "price": float(back["price"])} if back else \
        {"until": "today", "date": None, "price": mark}
    sold_at = sale.get("price")
    if sold_at is None:
        return {**end, "pct": None,
                "reason": "no sale price is on the record"}
    if float(sold_at) <= 0:
        return {**end, "pct": None,
                "reason": "the sale is recorded at nothing, so what the price "
                          "did against it cannot be expressed"}
    if end["price"] is None:
        # The host's own sentence, which names the sibling share classes that
        # ARE priced or says the figure on record is not a price. "No current
        # price is known" was true and useless — it could not tell a security
        # nobody has fetched from one whose price was typed as nought.
        return {**end, "pct": None,
                "reason": why or "no current price is known for this "
                                 "security"}
    if end["price"] <= 0:
        # Two different things end a window, and the reason has to say which.
        # Blaming "the purchase on None" when the window runs to today names an
        # entry the user never made, and sends them looking for it.
        return {**end, "pct": None,
                "reason": (f'the purchase on {end["date"]} that ends this '
                           "window is recorded at nothing, so it cannot stand "
                           "for what the price was that day")
                if end["until"] == "purchase" else
                ("the price on record for this security is nothing or less, "
                 "so what it did against the sale cannot be expressed")}
    return {**end, "reason": None,
            "pct": round((end["price"] / float(sold_at) - 1) * 100, 2)}


# ------------------------------------------------------------------ analytics

# The two cohorts every purchase figure is reported in, never blended.
#
# A decision seen on screen and a decision rebuilt for a day in the past are
# not the same evidence about the same question. "Did overriding the tool
# help" is a question about a person's judgement under a verdict they were
# looking at; a reconstruction had no such moment, and the rebuild is
# imperfect in ways nobody can quantify — filings get restated, coverage
# thins the further back you go. Averaged together, a journal backfilled with
# ten years of history would answer the question almost entirely with entries
# where nobody was standing in front of a screen, and the panel would report
# a finding about the user that is really a finding about EDGAR.
#
# Both are reported, at equal weight, side by side. Excluding the
# reconstructed cohort would be the other failure: it is real evidence about
# the rules, and principle 10 says the panel has to be able to indict them.
COHORTS = MappingProxyType({
    "live": MappingProxyType({
        "label": "seen at the time",
        "means": "the verdict was on the screen when the entry was recorded",
    }),
    "reconstructed": MappingProxyType({
        "label": "reconstructed",
        "means": "the entry is dated in the past and its verdict was rebuilt "
                 "from the data available by that day, not seen at the time",
    }),
})


def _empty_cohort() -> dict:
    return {"override": [], "compliant": [],
            "unscored": {"override": {}, "compliant": {}},
            "counted": {"override": 0, "compliant": 0},
            "kinds": {"against": 0, "without": 0},
            "per_rule": {}}


def _rule_bucket(per_rule: dict, cite: dict) -> dict:
    return per_rule.setdefault(
        cite["key"], {"label": cite.get("label") or cite["key"],
                      "n": 0, "n_scored": 0, "wins": 0, "avg": None,
                      "returns": []})


def override_scorecard(securities: list[dict], price_of) -> dict:
    """Did overriding the tool help or hurt? And is any rule miscalibrated?

    Counted per lot, not per security: with several buys in one name, one
    can be a compliant entry and the next an override, and collapsing them
    would lose exactly the comparison the scorecard exists to make.

    Both directions, always. Reporting only the user's error rate builds a
    guilt machine that punishes being right, so the per-rule breakdown is
    here at equal weight: if overriding one particular limit keeps working
    out, that limit is wrong, not the person.

    Three splits, and none of them may be collapsed.

    **By cohort.** Every figure is reported once for decisions seen at the
    time and once for decisions reconstructed afterwards, and the two are
    never added up — see COHORTS.

    **By kind, within the live cohort.** "Bought against the signal" is a
    decision taken in the face of a verdict; "bought without a signal" is a
    decision taken where there was no verdict to face. Averaging them would
    make a data gap look like defiance. The reconstructed cohort has only the
    first kind, by construction: see `recorded_as`.

    **Purchases whose evaluation could not be rebuilt at all** are their own
    population, in neither the override count nor the compliant one. They are
    not a decision that went either way — there was no verdict to obey or
    defy — so putting them in either group would be inventing a decision
    nobody made. They are still counted and their returns still reported,
    because the purchases happened and what they did is worth knowing.
    """
    cohorts = {name: _empty_cohort() for name in COHORTS}
    # In neither cohort's comparison, and reported on its own. A returns
    # figure is still built for it: "the twelve entries this program could
    # not rebuild a verdict for returned 8% on average" is a fact, and a fact
    # that says nothing about anyone's discipline, which is the point.
    unrebuilt = {"returns": [], "counted": 0, "unscored": {}, "reasons": {}}
    for s in securities:
        price = price_of(s)
        for lot in lots(s, "buy"):
            r = lot_return(s, lot, price)
            scored = None if _is_absent(r) else r["value"]
            ov = lot.get("override")
            gap = lot.get("unreconstructed")
            if gap:
                unrebuilt["counted"] += 1
                why = gap.get("why") or "No reason was given."
                unrebuilt["reasons"][why] = \
                    unrebuilt["reasons"].get(why, 0) + 1
                if _is_absent(r):
                    unrebuilt["unscored"][r["reason"]] = \
                        unrebuilt["unscored"].get(r["reason"], 0) + 1
                else:
                    unrebuilt["returns"].append(scored)
                continue
            c = cohorts[basis_of(lot)]
            side = "override" if ov else "compliant"
            c["counted"][side] += 1
            if _is_absent(r):
                tally = c["unscored"][side]
                tally[r["reason"]] = tally.get(r["reason"], 0) + 1
            if ov:
                kind = ov.get("kind", "against")
                c["kinds"][kind] = c["kinds"].get(kind, 0) + 1
            # Every purchase is counted; only the ones that can be scored are
            # averaged. A purchase that cannot be scored is a real decision
            # that happened and a return that is not knowable, and the two
            # have to be reported apart — see the population figures below,
            # and `unscored`, which says why rather than guessing.
            for cite in (ov or {}).get("failed", []):
                b = _rule_bucket(c["per_rule"], cite)
                b["n"] += 1
                if scored is not None:
                    b["n_scored"] += 1
                    b["returns"].append(scored)
                    if scored > 0:
                        b["wins"] += 1
            if scored is not None:
                c[side].append(scored)

    out = {}
    for name, c in cohorts.items():
        for b in c["per_rule"].values():
            b["avg"] = round(sum(b["returns"]) / len(b["returns"]), 1) \
                if b["returns"] else None
            b.pop("returns")
        # Each group says how many purchases it covers AND how many of them
        # could be scored. Reporting a win rate over the priced subset beside
        # a count of every override would let a data gap read as a settled
        # result — and this is the panel that is supposed to be able to
        # indict a rule, so it is the last place a partial population may
        # pass for the whole.
        out[name] = {
            **COHORTS[name],
            "override": {**_summarise(c["override"]),
                         "n_purchases": c["counted"]["override"],
                         "n_unscored": (c["counted"]["override"]
                                        - len(c["override"])),
                         "unscored": _why_unscored(c["unscored"]["override"])},
            "compliant": {**_summarise(c["compliant"]),
                          "n_purchases": c["counted"]["compliant"],
                          "n_unscored": (c["counted"]["compliant"]
                                         - len(c["compliant"])),
                          "unscored": _why_unscored(
                              c["unscored"]["compliant"])},
            "kinds": c["kinds"],
            "per_rule": c["per_rule"],
            "n_purchases": (c["counted"]["override"]
                            + c["counted"]["compliant"]),
        }
    out["unreconstructed"] = {
        **_summarise(unrebuilt["returns"]),
        "n_purchases": unrebuilt["counted"],
        "n_unscored": unrebuilt["counted"] - len(unrebuilt["returns"]),
        "unscored": _why_unscored(unrebuilt["unscored"]),
        "reasons": _why_unscored(unrebuilt["reasons"]),
    }
    return out


def _why_unscored(tally: dict) -> list[dict]:
    """A tally of reasons as the panel reads it: each sentence with how many
    entries gave it, commonest first.

    Why, and not just how many. The panel used to say flatly that unscored
    purchases "have no price", which the engine agreed with in its own
    docstring, so neither of them could catch it: a purchase recorded at
    $0.00 was reported as one with no price, sending the reader to fetch data
    that would never fix it. In the one panel that is supposed to be able to
    indict a rule, an invented reason is the last thing that may pass for a
    finding. The same shape now carries why a reconstruction could not be
    made, for the same reason — "no filings had been filed by then" and "the
    strategy is not installed" send the reader to different places.
    """
    return [{"reason": why, "n": n}
            for why, n in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))]


def exit_scorecard(securities: list[dict], price_of) -> dict:
    """Group sales by why they were made, and what happened after. If one
    reason keeps showing a strong return *after* the sale, that is a finding
    no tool that drops the ticker at exit can ever produce.

    Counted per sale, not per holding period: the reason is given at the
    sale, and a position trimmed on a risk limit and then closed on a broken
    thesis gave two different answers that a per-period figure would have to
    pick between. What happened after is windowed per sale for the same
    reason — each one is asked about its own aftermath, and a sale the user
    later bought against is asked only about the stretch before that.

    The returns here are not split by cohort, and that is deliberate rather
    than an oversight. What a sale got and what the price did afterwards are
    recorded prices and market history — facts that do not change according
    to when the entry was typed. What *was* reconstructed is the signal the
    sale was recorded against, so `n_reconstructed` says how many sales in
    each group carried a rebuilt verdict rather than one seen at the time.
    That is the figure a reader needs before treating "Panic, three times,
    and the price rose 20% after each" as evidence about their own nerve.
    """
    out: dict[str, dict] = {}
    for s in securities:
        price = price_of(s)
        for sale in lots(s, "sell"):
            b = out.setdefault(sale.get("reason") or UNSTATED_REASON,
                               {"n": 0, "n_reconstructed": 0,
                                "avg_held": 0.0, "avg_after": 0.0,
                                "bought_again": 0, "_held": [], "_after": []})
            b["n"] += 1
            if is_reconstructed(sale):
                b["n_reconstructed"] += 1
            held = sale_return(s, sale)
            if not _is_absent(held):
                b["_held"].append(held["value"])
            after = since_sale(s, sale, price)
            if after["until"] == "purchase":
                b["bought_again"] += 1
            if after["pct"] is not None:
                b["_after"].append(after["pct"])
    for b in out.values():
        # Each average says what it rests on. The group count is a true
        # figure on its own ("you panicked three times"), but presenting an
        # average of one beside a count of three would let absence pass for
        # a settled answer. `bought_again` is on the same footing: it says
        # how many of these windows ended at a later purchase rather than at
        # today, because otherwise the average silently changes meaning.
        b["n_held"], b["n_after"] = len(b["_held"]), len(b["_after"])
        b["avg_held"] = round(sum(b["_held"]) / len(b["_held"]), 1) \
            if b["_held"] else None
        b["avg_after"] = round(sum(b["_after"]) / len(b["_after"]), 1) \
            if b["_after"] else None
        b.pop("_held")
        b.pop("_after")
    return out


def _summarise(returns: list[float]) -> dict:
    if not returns:
        return {"n": 0, "win_rate": None, "avg": None}
    wins = len([r for r in returns if r > 0])
    return {
        "n": len(returns),
        "win_rate": round(wins / len(returns) * 100),
        "avg": round(sum(returns) / len(returns), 1),
    }
