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
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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


def history(security: dict, key: str, entry_id: str | None = None) -> list:
    """Every entry on record, newest first.

    Nothing is ever removed from it, so a revision reads as what it is: an
    earlier answer, and the day the user changed their mind.
    """
    kept = [dict(e) for e in (security.get(key) or [])
            if isinstance(e, dict)
            and (entry_id is None or e.get("id") == entry_id)]
    kept.sort(key=lambda e: (str(e.get("recorded") or ""), e.get("seq") or 0))
    return list(reversed(kept))


def in_force(security: dict, key: str, entry_id: str | None = None,
             as_of: str | None = None) -> dict | None:
    """The entry that stood on a given day, or None.

    The clock governs this exactly as it governs filings and prices. `as_of`
    of None means now — the newest entry, with no ceiling — which is not the
    same as passing today's date: a stamp is UTC and a calendar day is
    local, and an evening's work west of Greenwich would disappear off the
    user's own screen if the live path imposed a date at all.
    """
    for entry in history(security, key, entry_id):
        if as_of is None or str(entry.get("recorded") or "")[:10] <= str(as_of):
            return entry
    return None


def first(security: dict, key: str, entry_id: str | None = None) -> dict | None:
    """The oldest entry on record, or None. What "you first wrote this on
    ..." is read from when a reconstruction predates the whole record."""
    kept = history(security, key, entry_id)
    return kept[-1] if kept else None


def day_of(entry: dict | None) -> str:
    return str((entry or {}).get("recorded") or "")[:10]
