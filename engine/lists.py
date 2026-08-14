"""The list a journal works from — a dated set of securities somebody handed you.

Every strategy before this one answered *should I buy this*. One answers *is
it time*, because the choosing already happened somewhere else: a ranked
screen was run against a universe this program does not have, and what came
back is thirty or fifty names. The journal's job is to record which list, and
when, and then to hold the user to it.

So a list is a **snapshot**, not a collection that gets edited. It arrives
whole, on a day, and it is superseded by the next one rather than amended.
That is why it sits on the dated record (`engine/dated.py`) rather than in a
slot: a rule here reads how old the current list is and when a name was last
on one, and both of those answers would be worthless if the list could be
quietly retuned. Corrections are a fresh import, the way a correction is a
fresh entry everywhere else in this program.

**Two dates describe one import and they are not the same date.** `pulled_on`
is the day the screen was run — the user types it, it is the list's identity,
and it is the only date any rule reads. `recorded` is the day it was typed in;
the substrate stamps it and nothing can supply it. They come apart whenever
somebody imports on Friday a list they pulled on Monday, and each answers a
different question: `recorded` answers *what did this journal know then*,
which is what a reconstruction walks; `pulled_on` answers *how old is this
ranking*, which is what a strategy asks. Keeping both is what stops either
question being answered with the other one's date.

**The current list is the one most recently imported, not the one with the
newest pull date.** A user who imports an old list by mistake has said, most
recently, that this is their list — and the fix is to import the right one,
which is one action and leaves both on the record. Choosing the newest
`pulled_on` instead would mean the last thing you did was not necessarily
what took effect, which is harder to predict and no more correct.

**Nothing here adds a security to the journal.** A list of fifty names is not
fifty things to track — the user buys five to seven of them, and creating
fifty security records (each with its own fetch, each queued behind the last)
would spend an hour of somebody's evening to produce forty-three rows nobody
asked for. The list is a set of ticker strings; a security record appears when
the user does something about one. That separation is the whole reason this is
its own object rather than a flag on `journal["securities"]`.
"""

from __future__ import annotations

import re
from datetime import date

from engine import dated

# Where the imports live on the journal document, and where a decision not to
# buy one lives on a security. Both are `dated` keys, so both are append-only
# and neither can be backdated.
KEY = "lists"
SKIP_KEY = "passed_over"

# What a ticker may look like. Deliberately narrow: one to seven characters,
# a letter first, then letters, dots and hyphens. Everything the SEC maps is
# inside it, and a company name long enough to be prose falls outside it,
# which is what lets a pasted table be read without the user marking up which
# column is which.
_TICKER = re.compile(r"^[A-Za-z][A-Za-z.\-]{0,6}$")

# The screener's own table has the ticker in the second column. A pasted row
# arrives tab-separated, so that position is worth trying first — but only
# trying: a user who pasted one symbol per line is the other common case, and
# a rule that insisted on the column would refuse them.
_TICKER_COLUMN = 1

def _is_day(text) -> bool:
    """A real calendar day, not merely something shaped like one.

    The shape rule alone accepted 2026-02-31, which then travelled the whole
    way through: the import was written, `security.listed_on` served it as a
    known date, and the month arithmetic that counts a position's year came
    back None against it — so the clock the strategy depends on resolved
    unreadable forever, on a journal that looked completely ordinary.
    """
    try:
        date.fromisoformat(str(text or "")[:10])
    except (TypeError, ValueError):
        return False
    return True


# -- reading what somebody pasted ---------------------------------------------

def read(text: str) -> dict:
    """{"tickers": [...], "unreadable": [line, ...]} from a pasted screen.

    Never guesses and never drops something silently. A line this cannot
    resolve to exactly one ticker comes back in `unreadable` with its own
    text, so the import can refuse and say which lines it could not read —
    thirty names of which one was quietly skipped is the worst outcome
    available here, because the missing one looks exactly like a name the
    screen did not return.

    Order is the order it was pasted, which is the order the screen ranked
    them in. Nothing here reads that order as a ranking: the rank is only
    meaningful against the other two thousand nine hundred and seventy
    companies that did not make the list, and none of those are here.
    """
    tickers, unreadable, seen = [], [], set()
    for line in str(text or "").splitlines():
        if not line.strip():
            continue
        found = _tickers_on(line)
        if found is None:
            unreadable.append(line.strip())
            continue
        for hit in found:
            if hit not in seen:
                seen.add(hit)
                tickers.append(hit)
    return {"tickers": tickers, "unreadable": unreadable}


def _is_header(fields) -> bool:
    """Whether this row is the table's own heading rather than a company."""
    return any(f.strip().lower() in ("ticker", "symbol") for f in fields)


def _tickers_on(line):
    """Every ticker on one pasted line, or None where it cannot be settled.

    Three shapes, and which one this is, is decided by what separates the
    fields rather than by trying each rule until one answers. That matters:
    a row of a copied table and a comma-separated line of symbols mean
    different things by a comma, and a rule that tried the table layout on
    both quietly returned one name from a line holding three.

    A TAB means a copied table row — one company per line, and its ticker is
    one field of several. A comma or semicolon means a written-out line of
    symbols, so every field on it is a ticker and one that is not makes the
    whole line unreadable rather than being skipped. Neither means one symbol
    on its own.
    """
    if "\t" in line:
        fields = [f.strip() for f in line.split("\t")]
        if _is_header(fields):
            return []
        if len(fields) > _TICKER_COLUMN and _TICKER.match(
                fields[_TICKER_COLUMN]):
            return [fields[_TICKER_COLUMN].upper()]
        hits = [f.upper() for f in fields if _TICKER.match(f)]
        return hits if len(hits) == 1 else None
    fields = [f.strip() for f in re.split(r"[,;]", line) if f.strip()]
    if _is_header(fields):
        return []
    if not all(_TICKER.match(f) for f in fields):
        return None
    return [f.upper() for f in fields]


# -- writing one ---------------------------------------------------------------

def record(journal: dict, pulled_on: str, tickers, floor=None) -> dict:
    """Append one import. Never edits, never replaces.

    `floor` is the smallest company the user asked the screen for, in dollars,
    and it is provenance rather than a rule — nothing reads it. It is kept
    because "thirty names" means something different at a fifty million floor
    than at a billion, and a reader looking at this list in three years has no
    other way to find that out.
    """
    day = str(pulled_on or "").strip()[:10]
    if not _is_day(day):
        raise ValueError(
            "Say what day you pulled this list, as YYYY-MM-DD. It is the "
            "list's identity — how old the ranking is, and what a position's "
            "year is counted from, are both measured off it.")
    if day > dated.stamp()[:10]:
        raise ValueError(
            f"You cannot have pulled a list on {day}; that day has not "
            "happened yet.")

    clean, seen = [], set()
    for raw in tickers or []:
        symbol = str(raw or "").strip().upper()
        if not symbol:
            continue
        if not _TICKER.match(symbol):
            raise ValueError(
                f'"{symbol}" is not a ticker this program can read. Tickers '
                "are one to seven characters, starting with a letter.")
        if symbol not in seen:
            seen.add(symbol)
            clean.append(symbol)
    if not clean:
        raise ValueError(
            "There are no names in this list. Paste the screen's results, or "
            "one ticker per line.")

    amount = None if floor in (None, "") else float(floor)
    if amount is not None and amount < 0:
        raise ValueError("A market cap floor cannot be negative.")

    return dated.append(journal, KEY,
                        {"pulled_on": day, "floor": amount,
                         "tickers": clean})


# -- reading them back ---------------------------------------------------------

def history(journal: dict, as_of: str | None = None) -> list:
    """Every import this journal has made, newest first.

    `as_of` cuts it to what was on record by that day, so a reconstruction of
    a backdated purchase sees the lists that existed then and not the one
    imported last week.
    """
    entries = dated.history(journal, KEY)
    if as_of is None:
        return entries
    day = str(as_of)[:10]
    return [e for e in entries if dated.day_of(e) <= day]


def current(journal: dict, as_of: str | None = None):
    """The list in force, or None where this journal has never imported one."""
    entries = history(journal, as_of)
    return entries[0] if entries else None


def listed_on(journal: dict, ticker: str, as_of: str | None = None):
    """The pull date of the most recent list this ticker appeared on, or None.

    The *latest pull date*, not the latest import. A name is affirmed by the
    freshest ranking that carried it, and importing an old list afterwards
    cannot un-affirm it — so this only ever moves forward, which is what a
    holding period counted from it needs in order to be predictable.
    """
    symbol = str(ticker or "").strip().upper()
    days = [e["pulled_on"] for e in history(journal, as_of)
            if symbol in (e.get("tickers") or [])]
    return max(days) if days else None


def on_current(journal: dict, ticker: str, as_of: str | None = None):
    """Whether this ticker is on the list in force. None where there is none.

    None rather than False, and the difference matters: "your list does not
    have this name on it" and "you have no list" call for different things
    from the reader, and a False here would say the first when it meant the
    second.
    """
    now = current(journal, as_of)
    if now is None:
        return None
    return str(ticker or "").strip().upper() in (now.get("tickers") or [])


def changes(journal: dict) -> list:
    """Each import with what it added and dropped against the one before it.

    Newest first, oldest carrying everything as added. This is derived on read
    rather than stored, for the reason every other derived thing here is: a
    stored diff is a second opinion about a fact the two lists already settle.
    """
    entries = list(reversed(history(journal)))
    out, previous = [], set()
    for entry in entries:
        names = set(entry.get("tickers") or [])
        out.append({**entry,
                    "added": sorted(names - previous),
                    "dropped": sorted(previous - names)})
        previous = names
    return list(reversed(out))


# -- a name you were told to buy and did not ----------------------------------

def pass_over(security: dict, pulled_on: str, reason: str) -> dict:
    """Record that the user is not buying a name their own list gave them.

    This is the third documented way people break this method, and it is the
    only one of the three that leaves no other trace: buying the whole list at
    once and selling a winner early both produce a lot, and a lot carries its
    own override. Declining a name produces nothing at all — the verdict goes
    on saying buy, the user goes on not buying, and a year later there is no
    record that a decision was ever made.

    A reason is required for the same reason it is required on a judgement:
    the act on its own teaches nothing, and this record exists to be read back
    against what the name went on to do. Whether skipping keeps working out is
    a question about the list, not about the user — which is the direction
    this program is obliged to be able to report in.

    It is tied to one pull date. A name that comes back on the next list is a
    fresh question, and an answer given about last quarter's ranking is not an
    answer to this one.
    """
    day = str(pulled_on or "").strip()[:10]
    if not _is_day(day):
        raise ValueError("A decision not to buy is recorded against the list "
                         "that offered the name, so it needs that list's "
                         "pull date.")
    written = (reason or "").strip()
    if not written:
        raise ValueError(
            "Say why you are not buying this one. Your rules said to; the "
            "whole value of writing it down is being able to read it back "
            "when you find out whether you were right.")
    return dated.append(security, SKIP_KEY,
                        {"list": day, "reason": written})


def pass_overs(security: dict) -> list:
    """Every decision not to buy this name, newest first.

    `passed_over` below answers about ONE list, because that is what a screen
    asks: the name is in front of the user under today's ranking and the
    question is whether they already declined it under this one. Scoring asks
    the opposite question — every time this name was declined, whatever list
    offered it — and there was no way to ask it. A record written, displayed
    as prose, and never measured is the shape principle 10 exists against.
    """
    return dated.history(security, SKIP_KEY)


def passed_over(security: dict, pulled_on: str, as_of: str | None = None):
    """The standing decision not to buy this name off that list, or None."""
    day = str(pulled_on or "").strip()[:10]
    for entry in dated.history(security, SKIP_KEY):
        if entry.get("list") != day:
            continue
        if as_of is not None and dated.day_of(entry) > str(as_of)[:10]:
            continue
        return entry
    return None
