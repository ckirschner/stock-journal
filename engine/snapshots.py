"""A day you kept — what everything said about one security, saved on purpose.

Until now the only way to keep what the tool said was to spend money. A
purchase freezes the whole evaluation — every figure with what qualified it,
the verdict, the rules and the versions that produced it — and that record is
never recomputed. Somebody watching a company for six months before buying it
had none of that. Their notes anchored to nothing, and "this has changed"
had no *changed from what*.

So the same freeze, taken deliberately. It is not a new kind of record: it is
`portfolio.freeze`, the identical object, hung on the day instead of on a lot.
That matters more than it sounds. Two builders would be two sets of refusals
and the second set is always the one missing a check — and the comparison this
exists to make possible is only sound if a snapshot taken on Tuesday and a
purchase made on Friday are the same shape read the same way.

**It is always today, and there is no way to say otherwise.** No `as_of`, no
`when`, no date parameter of any kind. The day a snapshot belongs to is the
day it was written, which is `recorded`, which the substrate stamps and no
caller can supply (engine/dated.py). That is a decision and not an oversight:

- A purchase or a deposit is an event that really happened on a day, and the
  record has to be able to say which. A snapshot is not an event. It is a
  reading taken by looking. There is no day to date it to except the day
  somebody looked, so a date field here would not be recording anything — it
  would be inventing an occasion.
- "Changed since your last snapshot" is the whole point, and a baseline you
  can mint retrospectively is not a baseline. It is a way to choose, after
  seeing today's answer, what today gets compared against. That is the same
  failure as retuning a threshold at the moment it is about to fire, and it
  is answered the same way: the thing is unavailable rather than discouraged.
- Nothing is lost by refusing it. A backdated decision already freezes its own
  evaluation, on its own lot, through the same builder.

**Taking one is not deciding anything, which is what lets it be discarded.**
Every other record here is append-only because it is evidence about a choice
somebody made — a lot, an exit, a thesis, an answer. None of those may be
removed, because the mistakes in them are exactly what a person learns from.
A snapshot is a bookmark. Nobody acted, no money moved, no scorecard reads
it. One taken by mistake is not a lesson; it is a mis-click, and a record you
cannot tidy is a record that stops being kept.

**But a discard is an append, never a removal.** The entry stays, whole,
carrying what it froze and the day it was taken; a second entry says it was
discarded, when, and why if a reason was given. It stops standing — it drops
out of the list, and out of what "since last time" measures against — and it
never stops having existed. The reason is not tidiness. The one snapshot
somebody would most want gone without trace is the one that shows what they
saw before they did something they now regret, and a baseline that can be
quietly erased is worth nothing on the day it matters.

So: taking one is free, discarding one is free, and losing one silently is
impossible.
"""

from __future__ import annotations

from . import dated, journals, portfolio

# Where the record lives on a security. A `dated` key, so it is append-only
# and no caller can supply its own `recorded` — which is what makes "the day
# this was taken" a fact rather than a claim. See the module docstring.
KEY = "snapshots"

# The two things that can be written here. `kind` is read — it is what
# `history` dispatches on — rather than being a label beside a shape that
# already implies it, so a third kind arrives as a refusal from a build that
# does not know it rather than as a row quietly treated as one of these two.
TAKEN = "taken"
DISCARDED = "discarded"

_NOT_TODAY = (
    "A snapshot is what everything says now, so there is no day to record it "
    "against except today, and no way to ask for another. This one arrived "
    "carrying a rebuilt evaluation for {as_of}. A decision dated in the past "
    "freezes its own evaluation onto its own entry; nothing needs a second "
    "one saved against a day nobody looked.")

_NOTHING_TO_KEEP = (
    "There is no verdict to keep. A snapshot records what the strategy said, "
    "and nothing asked it — which is not the same as its having nothing to "
    "say. A strategy that is not installed, or data that cannot be read, "
    "each comes back as a verdict saying so, and either of those is worth "
    "keeping.")


# -- writing -----------------------------------------------------------------

def take(journal: dict, security: dict, decision: dict, *,
         values: dict, price_seen: dict, evaluation: dict,
         thesis: dict | None = None, valuation: dict | None = None,
         note: str = "") -> dict:
    """Freeze what everything says about this security now, and keep it.

    The arguments after `decision` are what `portfolio.add_lot` takes and
    mean exactly the same things, because they go to the same builder — the
    merged qualified values, the effective price with its instrument and its
    date, the record of how the evaluation was reached, and the versions of
    what the user had written by then. Assemble them once, for the whole
    entry, the way a purchase does: two passes over the stores can see two
    different sets of filings, and a record written once cannot be corrected
    afterwards.

    `journal` is here for one reason: it is what says where the change
    records stood. Handing over the counts instead would let a caller supply
    them and let a caller forget to, and a snapshot that cannot say which
    rules were behind it is a number without a question.

    `note` is why this day was worth keeping, if the user says. It sits on
    the entry rather than inside what was frozen — the frozen part is what
    the tool said, and this is what the person said about it.
    """
    basis = (evaluation or {}).get("basis")
    if basis != "live":
        raise ValueError(_NOT_TODAY.format(
            as_of=(evaluation or {}).get("as_of") or "an earlier day"))
    if decision is None:
        raise ValueError(_NOTHING_TO_KEEP)
    # A day saved into a record nothing can display has not been saved. This
    # is a raise where the reads return an absence, and the difference is
    # who is standing there: a read runs on every render and must never take
    # the screen down, a write is one deliberate act and its refusal is a
    # sentence the person who pressed the button reads in place.
    refusal = unreadable(security)
    if refusal:
        raise ValueError(refusal)
    return dated.append(security, KEY, {
        "kind": TAKEN,
        "note": str(note or "").strip(),
        "snapshot": portfolio.freeze(
            decision, values, price_seen, evaluation,
            thesis=thesis, valuation=valuation,
            changes_recorded=journals.changes_recorded(journal or {})),
    })


def discard(security: dict, seq, reason: str = "") -> dict:
    """Stop a saved snapshot standing, by appending the fact that it was
    discarded.

    Nothing is removed. The snapshot keeps its place in the record and keeps
    everything it froze; it simply stops being one of the days this security
    is measured against. What a reader sees afterwards is that it was taken
    on one day and discarded on another — which is the honest account of what
    happened, and the only version that is worth anything when the snapshot
    somebody wanted gone was inconvenient rather than accidental.

    A reason is invited and never required. The one piece of mandatory
    friction in this program is writing down why you went against your own
    signal, and putting a second one here — over a bookmark nobody acted on —
    would spend that friction where nothing is learned from it.
    """
    seq = _seq(seq)
    got = read(security)
    if got["refusal"]:
        raise ValueError(got["refusal"])
    for row in got["entries"]:
        if row["seq"] != seq:
            continue
        if row["discarded"]:
            raise ValueError(
                f"That snapshot was already discarded on "
                f'{dated.day_of(row["discarded"])}. Discarding is an entry '
                "on the record, not a deletion, so there is nothing left to "
                "discard a second time.")
        return dated.append(security, KEY, {
            "kind": DISCARDED,
            "discards": seq,
            "reason": str(reason or "").strip(),
        })
    raise ValueError(
        f"No snapshot numbered {seq} was ever saved for "
        f'{security.get("ticker") or "this security"}.')


def _seq(seq) -> int:
    try:
        return int(seq)
    except (TypeError, ValueError):
        raise ValueError("A snapshot is identified by the number it was "
                         f"written under, and {seq!r} is not one.") from None


# -- reading -----------------------------------------------------------------

def read(security: dict) -> dict:
    """The whole record, walked once::

        {"entries": [...newest first, each carrying `discarded`],
         "refusal": None | "why none of it can be shown"}

    The one place the raw list is touched, and so the one place that knows
    the two kinds of entry apart. Everything below reads this. A discard is
    not a row of its own — it is a fact about the snapshot it names, and
    folding it on where it belongs is what stops a reader having to pair them
    up and get it wrong.

    **An entry this build cannot place makes the whole record unreadable
    rather than being skipped, and unreadable is an answer rather than an
    exception.** Those are two separate decisions and both matter.

    Skipping is the dangerous direction in both directions at once: an
    unrecognised discard leaves a snapshot standing that its owner retired,
    and an unrecognised entry disappears from a list presenting itself as
    complete. So nothing partial is served — `entries` is empty and the
    refusal says why.

    But it is returned, not raised. This runs on every render, once per
    security, and a raise here reached `get_state` — which produces the whole
    application state in one call, so one unplaceable entry on one security
    in one journal returned an error instead of a payload and the window
    rendered nothing at all: no securities, no journal list, no way to open a
    different journal. That is the case this refusal was written for — a
    journal restored from a bundle a later version wrote — so the refusal was
    reaching for the screen exactly when the screen was gone. engine/cash.py
    answers the identical question the same way, and for the same reason:
    an entry with a kind it has no table row for makes the balance *absent
    with a reason*, never an exception.

    Writing is the other way round. See `take` and `discard`: appending into
    a record nothing can display is not saving anything, and there the
    refusal is a raise the user reads in place.
    """
    rows = dated.history(security, KEY)
    taken = {e["seq"]: e for e in rows if e.get("kind") == TAKEN}
    named = security.get("ticker") or "this security"
    discarded: dict = {}
    for entry in rows:
        kind = entry.get("kind")
        if kind == TAKEN:
            continue
        if kind != DISCARDED:
            return {"entries": [], "refusal": (
                f'A saved snapshot for {named} is recorded as "{kind}", '
                "which this version of the program does not know how to "
                "read — most likely it was written by a later one. Nothing "
                "has been changed and nothing has been lost; none of this "
                f"security's saved days can be shown until a version that "
                "understands that entry opens the journal.")}
        target = entry.get("discards")
        if target not in taken:
            return {"entries": [], "refusal": (
                f"A discard in {named}'s snapshot record names snapshot "
                f"{target}, which is not on the record. Nothing has been "
                "changed, and none of this security's saved days can be "
                "shown until that is resolved.")}
        # One per snapshot by construction — `discard` refuses a second — and
        # the oldest wins if a hand-edited file ever holds two, because the
        # first one is the one that happened.
        discarded[target] = entry

    return {"entries": [{**e, "discarded": discarded.get(e["seq"])}
                        for e in rows if e.get("kind") == TAKEN],
            "refusal": None}


def unreadable(security: dict) -> str | None:
    """Why this security's saved days cannot be shown, or None."""
    return read(security)["refusal"]


def history(security: dict) -> list:
    """Every snapshot ever saved for this security, newest first.

    Empty where the record cannot be read — which is why nothing may treat
    an empty list as "none were saved" without asking `unreadable` too. The
    two readers that must not get that wrong ask through `standing` and
    `summaries`, which carry the refusal with them.
    """
    return read(security)["entries"]


def standing(security: dict) -> list:
    """The snapshots that still count, newest first. Empty where the record
    cannot be read — see `history`."""
    return [e for e in history(security) if not e["discarded"]]


def latest(security: dict) -> dict | None:
    """The most recently saved snapshot that still stands, or None.

    What "changed since last time" is measured against, and the anchor a note
    written today belongs to. A discarded one is not it — that is the whole
    of what discarding does.

    Raises where the record cannot be read, rather than answering None. This
    is the one read whose answer is a baseline, and "there is no baseline"
    and "I cannot say what the baseline is" are different facts that would
    produce the same comparison. Principle 4: an absence must never be served
    as a settled answer.
    """
    got = read(security)
    if got["refusal"]:
        raise ValueError(got["refusal"])
    kept = [e for e in got["entries"] if not e["discarded"]]
    return kept[0] if kept else None


def entry(security: dict, seq) -> dict | None:
    """One saved snapshot by its number, whole — or None.

    Raises where the record cannot be read, for the reason `latest` does: a
    caller that asked for a specific saved day must not be told it does not
    exist when the truth is that nothing here can be shown.
    """
    seq = _seq(seq)
    got = read(security)
    if got["refusal"]:
        raise ValueError(got["refusal"])
    for row in got["entries"]:
        if row["seq"] == seq:
            return row
    return None


_NOT_ON_RECORD = (
    "not on this snapshot's record — the day was kept without a known "
    "figure for it. A frozen record holds only what was known when it was "
    "written, and it cannot say whether the figure was absent or simply "
    "never asked about")

_PREDATES = (
    "this snapshot predates the change record, so whether the measure's "
    "definition moved between these two days cannot be said — and a "
    "distance across a definition that may have moved would not be a "
    "distance in one measure")


def _quantity(v) -> bool:
    """A value a subtraction means something on. Booleans are ints in
    Python and a judgement's pass minus fail is not a move in anything."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare(security: dict, journal: dict, seqs, comparable) -> dict:
    """Two or more saved days of one security, side by side::

        {"columns":  [{"seq", "day", "note", "discarded"}],   # oldest first
         "verdict":  [{"seq", "state", "render", "rule", "summary",
                       "strategy"}],
         "price":    [{"seq", "value", "source", "date", "ticker"}],
         "measures": {entry id: {"readings": [...one per column],
                                 "moved": known-or-absent}},
         "refusal":  None}

    Everything is read off what each snapshot froze and nothing is worked
    out again — a comparison that recomputed a column would be a second
    opinion about a record whose whole purpose is that it has only one.

    A measure missing from one column is served absent with the reason a
    frozen record can honestly give: the record cannot distinguish "was
    absent that day" from "was never asked", so the comparison says neither.

    `moved` is the newest reading against the oldest, and it is only served
    where the subtraction means something: both endpoints known, both
    quantities, and the measure's definition not moved in between. The gate
    is placed on the change record's *positions* — each snapshot recorded
    how far the record had got when it was frozen — never on wall-clock
    stamps, which do not sort across timezones. `comparable` is
    bank.COMPARABLE_FIELDS, handed in for the reason
    journals.measures_incomparable takes it: this module owns the record's
    shape and holds no opinion about what a measure is.

    Raises where the record cannot be read or a named day was never saved —
    a comparison is a deliberate act, and the refusal is a sentence the
    person who asked reads in place. A discarded snapshot is comparable:
    a discard retires a baseline, not the evidence.
    """
    got = read(security)
    if got["refusal"]:
        raise ValueError(got["refusal"])
    want = sorted({_seq(s) for s in (seqs or [])})
    if len(want) < 2:
        raise ValueError("A comparison needs at least two saved days.")
    by = {r["seq"]: r for r in got["entries"]}
    gone = [str(s) for s in want if s not in by]
    if gone:
        named = security.get("ticker") or "this security"
        raise ValueError(
            f'No snapshot numbered {", ".join(gone)} was ever saved for '
            f"{named}.")
    rows = [by[s] for s in want]

    columns, verdict, price = [], [], []
    for row in rows:
        snap = row.get("snapshot") or {}
        decision = snap.get("decision") or {}
        state = decision.get("state") or {}
        left = row["discarded"]
        columns.append({
            "seq": row["seq"], "day": dated.day_of(row),
            "note": row.get("note") or "",
            "discarded": None if not left else {
                "day": dated.day_of(left), "reason": left.get("reason") or ""},
        })
        verdict.append({
            "seq": row["seq"],
            "state": {"id": state.get("id"), "name": state.get("name")},
            "render": decision.get("render"),
            "rule": (decision.get("reason") or {}).get("rule"),
            "summary": (decision.get("reason") or {}).get("summary"),
            "strategy": snap.get("strategy"),
        })
        price.append({
            "seq": row["seq"], "value": snap.get("price"),
            "source": snap.get("price_source"), "date": snap.get("price_date"),
            "ticker": snap.get("price_ticker"),
        })

    # The gate's window, in positions. None where either snapshot predates
    # the change record — no stamp, no claim, and the absence says so.
    def _position(row):
        marks = (row.get("snapshot") or {}).get("changes_recorded")
        return None if marks is None else marks.get("measures")

    lo, hi = _position(rows[0]), _position(rows[-1])
    redefined = journals.measures_incomparable(journal or {}, comparable)

    measures: dict = {}
    ids = sorted({eid for row in rows
                  for eid in ((row.get("snapshot") or {}).get("metrics")
                              or {})})
    for eid in ids:
        readings = []
        for row in rows:
            held = ((row.get("snapshot") or {}).get("metrics") or {}).get(eid)
            if held is None:
                readings.append({"status": "absent",
                                 "reason": _NOT_ON_RECORD})
            else:
                readings.append({"status": "known", **held})
        first, last = readings[0], readings[-1]
        if first["status"] != "known" or last["status"] != "known":
            moved = {"status": "absent",
                     "reason": "the figure is not on both records, so there "
                               "is no distance to measure"}
        elif not (_quantity(first.get("value"))
                  and _quantity(last.get("value"))):
            moved = {"status": "absent",
                     "reason": "not a quantity — the readings sit beside "
                               "each other to be read, not subtracted"}
        elif lo is None or hi is None:
            moved = {"status": "absent", "reason": _PREDATES}
        else:
            between = [m for m in redefined.get(eid) or []
                       if m.get("seq") is not None and lo < m["seq"] <= hi]
            if between:
                day = str(between[0].get("seen") or "")[:10]
                moved = {"status": "absent",
                         "reason": (
                             f"what this measure means moved on {day}, "
                             "between these two days, so the readings were "
                             "not worked out to the same definition and the "
                             "distance between them would not be a distance "
                             "in one measure")}
            else:
                moved = {"status": "known",
                         "value": round(float(last["value"])
                                        - float(first["value"]), 6),
                         "source": "computed", "cautions": [],
                         "provenance": [
                             f'{first["value"]} on {columns[0]["day"]}, '
                             f'against {last["value"]} on '
                             f'{columns[-1]["day"]}, both read off what was '
                             "frozen"]}
        measures[eid] = {"readings": readings, "moved": moved}

    return {"columns": columns, "verdict": verdict, "price": price,
            "measures": measures, "refusal": None}


def since_last(security: dict, decision: dict | None) -> dict:
    """Whether the verdict has changed since the last saved day, as a row
    reads it on every render::

        {"status": "known", "seq", "since", "changed",
         "from": {"id", "name", "render"}, "to": {...}}
      | {"status": "absent", "reason"}

    "New" means changed since the last snapshot that stands — a meaning tied
    to something the user deliberately did, needing no continuous history.
    Absent, with the difference stated, where there is nothing to measure
    against: no standing snapshot is not the same fact as unchanged, and an
    unreadable record is neither. Returned rather than raised, because this
    runs once per security on every render and the refusal must never take
    the screen down — the same decision `read` documents.
    """
    got = read(security)
    if got["refusal"]:
        return {"status": "absent", "reason": got["refusal"]}
    kept = [e for e in got["entries"] if not e["discarded"]]
    if not kept:
        return {"status": "absent",
                "reason": "no saved reading stands to measure against — "
                          "nothing has been kept, or every kept day was "
                          "discarded"}
    if not decision:
        return {"status": "absent",
                "reason": "there is no verdict today to measure against the "
                          "saved one"}
    last = kept[0]
    frozen = (last.get("snapshot") or {}).get("decision") or {}
    state = frozen.get("state") or {}
    now = decision.get("state") or {}
    return {"status": "known", "seq": last["seq"],
            "since": dated.day_of(last),
            "changed": (state.get("id") != now.get("id")
                        or frozen.get("render") != decision.get("render")),
            "from": {"id": state.get("id"), "name": state.get("name"),
                     "render": frozen.get("render")},
            "to": {"id": now.get("id"), "name": now.get("name"),
                   "render": decision.get("render")}}


def summaries(security: dict) -> dict:
    """The list a screen draws::

        {"rows": [...newest first], "refusal": None | why there are none}

    One small row per saved snapshot — enough to list them and choose one,
    and not the thing itself. A frozen evaluation is kilobytes of evidence,
    and a screen shipping every one of them on every render would carry
    megabytes to draw a list of dates. So the list is rows and the record is
    fetched when somebody opens one.

    The refusal travels with the rows rather than beside them, because an
    empty list and an unreadable record draw different screens and a caller
    holding only the list cannot tell them apart. Same object, one read, and
    the qualifying half cannot go missing on the way.

    Every field is read off what was frozen and nothing is worked out again.
    A row that recomputed the state, or looked its name up in the strategy
    standing today, would be a second opinion about a record whose whole
    purpose is that it has only one.
    """
    got = read(security)
    out = []
    for row in got["entries"]:
        snap = row.get("snapshot") or {}
        decision = snap.get("decision") or {}
        state = decision.get("state") or {}
        gone = row["discarded"]
        out.append({
            "seq": row["seq"],
            "day": dated.day_of(row),
            "note": row.get("note") or "",
            "state": state.get("name"),
            "render": decision.get("render"),
            "summary": (decision.get("reason") or {}).get("summary"),
            "strategy": snap.get("strategy"),
            "price": snap.get("price"),
            "price_date": snap.get("price_date"),
            "measures": len(snap.get("metrics") or {}),
            "discarded": None if not gone else {
                "day": dated.day_of(gone),
                "reason": gone.get("reason") or "",
            },
        })
    return {"rows": out, "refusal": got["refusal"]}
