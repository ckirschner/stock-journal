"""The dated record — one mechanic, every value the user supplies.

Four things in a journal come from the user rather than from a filing: what
they judge about a business, what they believe about it and what would prove
them wrong, what they think it is worth, and the numbers they read off a
document this program cannot parse. Every one of them was once a slot that
could be overwritten, and every one of them is worth most at exactly the
moment someone would want to overwrite it.

So none of them is a slot. Each is a list that is only ever appended to,
where every entry carries the day it was written, and the entry *in force*
on a given day is the newest one written by then. That is what makes a
reconstruction honest: an evaluation rebuilt for a past date sees what was
on record then, and nothing formed afterwards can present itself as though
it had been.

The mechanic lives here once rather than four times because four copies of
"append with a timestamp, walk back for the one in force" is four chances
for one copy to grow an edit path. There is no edit function here, no
delete, and no parameter that would let a caller supply its own `recorded`
— an entry cannot be backdated because there is nothing to backdate it
with. That is principle 14 rather than a convention: the wrong thing is
unrepresentable, not discouraged.

What each kind *means* is not here. Whether a reason is required, what
qualifies an entry, when an old one stops applying — those differ per kind
and belong with the kind. This module knows only that entries are dated,
ordered, and never rewritten.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Written by the host, never by a caller. Appearing in a payload means the
# caller is trying to say when something was recorded, which is the one
# thing an append-only record cannot let it say.
RESERVED = ("seq", "recorded")


def stamp() -> str:
    """When an entry was written, on the calendar the writer was standing on.

    Local and offset-aware — "2026-08-09T19:16:27-07:00" — which carries both
    facts in one field: the instant, and the day the user would say it was.

    It has to be the user's day, because every other date in this program
    already is. A purchase date, a sale date, a pin, `today` — all of them are
    calendar dates a person typed or read off their own clock. `recorded` was
    the only date derived from somewhere else, and `in_force` compared the two
    directly, so for part of every day the record answered "what did I know
    then" against the wrong calendar: an evening's work west of Greenwich was
    invisible to a purchase dated that same evening, and a morning's work east
    of it was served to a reconstruction of the day before. Both silently, and
    the first of them freezes "bought with no thesis" onto a lot that cannot
    be corrected.

    One field rather than a UTC stamp plus a local day beside it: two
    structures describing one moment are two structures that can come apart,
    and the half that goes missing is always the qualifying half.

    Entries written before this are UTC and stay UTC. Nothing already on
    record is restated — which is the whole point of an append-only record,
    and is why this is fixed at the write rather than by converting on read.
    """
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append(security: dict, key: str, payload: dict) -> dict:
    """Append one entry to a security's dated record and return it.

    `seq` counts every entry ever written under this key, including ones
    about other subjects, so it orders the record as a whole — two entries
    written the same second still read in the order they were made.
    """
    if not isinstance(payload, dict):
        raise TypeError("A dated entry is a dict of what was recorded.")
    for name in RESERVED:
        if name in payload:
            raise ValueError(
                f'"{name}" is set by the journal, not by the caller. An '
                "entry that could name its own date could be written into "
                "the past, and a record that can be written into the past "
                "is not a record.")
    log = security.setdefault(key, [])
    entry = {"seq": len(log) + 1, **payload, "recorded": stamp()}
    log.append(entry)
    return entry


def _instant(entry: dict) -> tuple:
    """One entry's `recorded` as an absolute moment, for ordering.

    The instant, never the day. Stamps carry an offset, so the text no longer
    sorts chronologically on its own — "2026-08-09T19:30:00-07:00" is *after*
    "2026-08-10T02:00:00+00:00" and sorts before it. Comparing the parsed
    moments in UTC is the same order on every machine, so moving one cannot
    reorder a record that is supposed to be append-only.

    An unreadable stamp sorts last rather than raising: `history` runs on
    every render, and one malformed entry must not blank a security's whole
    record.
    """
    text = str(entry.get("recorded") or "")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return (1, datetime.max.replace(tzinfo=timezone.utc))
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return (0, moment.astimezone(timezone.utc))


def history(security: dict, key: str, entry_id: str | None = None) -> list:
    """Every entry on record, newest first.

    Nothing is ever removed from it, so a revision reads as what it is: an
    earlier answer, and the day the user changed their mind.
    """
    kept = [dict(e) for e in (security.get(key) or [])
            if isinstance(e, dict)
            and (entry_id is None or e.get("id") == entry_id)]
    kept.sort(key=lambda e: (_instant(e), e.get("seq") or 0))
    return list(reversed(kept))


def in_force(security: dict, key: str, entry_id: str | None = None,
             as_of: str | None = None) -> dict | None:
    """The entry that stood on a given day, or None.

    The clock governs this exactly as it governs filings and prices. `as_of`
    of None means now — the newest entry, with no ceiling.

    Both sides are the writer's own calendar day: `as_of` is a date a person
    typed, and `day_of` is now the day they were standing on when they wrote
    (see `stamp`). Sliced on both sides rather than one, because comparing a
    day against a full timestamp reads "2026-08-06" <= "2026-08-06T02:30" as
    true, and the next caller to pass a stamp here would get an entry from
    the wrong side of midnight with nothing saying so.
    """
    for entry in history(security, key, entry_id):
        if as_of is None or day_of(entry) <= str(as_of)[:10]:
            return entry
    return None


def first(security: dict, key: str, entry_id: str | None = None) -> dict | None:
    """The oldest entry on record, or None. What "you first wrote this on
    ..." is read from when a reconstruction predates the whole record."""
    kept = history(security, key, entry_id)
    return kept[-1] if kept else None


def day_of(entry: dict | None) -> str:
    """The calendar day an entry was written on, as its writer would say it.

    A plain slice, and exact rather than approximate: `stamp` records the
    local day, so the first ten characters *are* that day. Entries written
    before stamps carried an offset report their UTC day, which is the day
    they have always reported — nothing already written is restated here.
    """
    return str((entry or {}).get("recorded") or "")[:10]
