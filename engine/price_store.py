"""Price history on disk: as-traded rows plus adjustment events, never a
pre-adjusted series.

The decision this file enforces: sources restate their own adjusted history
retroactively (every dividend rescales the entire past), so a stored adjusted
series would silently disagree with itself across fetches. Raw as-traded
prices do not move. We store those, store the split/dividend events alongside,
and derive any adjusted series on demand in memory.

Layout: prices/CIK##########.json — keyed by CIK for the same reason the facts
store is, with each ticker's series kept separately inside (share classes are
genuinely different instruments at different prices).

Merge rules on re-fetch: rows merge by date, events by (date, kind); nothing
is ever deleted. A ticker whose SEC mapping stops pointing at this CIK is
marked terminal with the evidence, and its rows stay exactly as retrieved —
a series is never silently lost, and a reused symbol can never append another
company's prices here because appends require the mapping to still hold.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import store

SCHEMA = "ledger.prices/1"


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path_for(cik: int) -> Path:
    return store.data_dir() / "prices" / f"CIK{int(cik):010d}.json"


def load(cik: int) -> dict:
    p = path_for(cik)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"schema": SCHEMA, "cik": int(cik), "series": {}}
    except (json.JSONDecodeError, OSError):
        aside = p.with_name(p.name + ".broken-" +
                            datetime.now().strftime("%Y%m%d-%H%M%S"))
        try:
            p.rename(aside)
        except OSError:
            pass
        return {"schema": SCHEMA, "cik": int(cik), "series": {}}


def save(cik: int, doc: dict) -> None:
    import os
    import tempfile
    p = path_for(cik)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp",
                               dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(doc, separators=(",", ":"), ensure_ascii=False))
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def merge_series(doc: dict, ticker: str, source: str,
                 rows: list[list], events: list[list]) -> dict:
    """Merge freshly fetched raw rows and events into a ticker's series.

    rows:   [date, close, volume]      — as traded, never adjusted
    events: [date, kind, amount]       — kind: "split" (factor) | "dividend"
                                         (cash per share, on that basis)

    Adds and updates by date; never removes a date already held. A close that
    *changed* for a date we already hold is recorded in ``revisions`` rather
    than silently overwritten — sources do occasionally correct closes, and a
    correction is a fact worth keeping.
    """
    t = str(ticker).upper()
    s = doc.setdefault("series", {}).setdefault(t, {
        "source": source, "rows": [], "events": [],
        "terminal": None, "fetched_at": None, "revisions": []})
    if s.get("terminal"):
        raise ValueError(
            f"The {t} series is marked terminal "
            f"({s['terminal'].get('reason', 'no reason recorded')}); it no "
            "longer accepts new rows. Fetch under the current mapping instead.")

    by_date = {r[0]: r for r in s["rows"]}
    for row in rows:
        d = row[0]
        held = by_date.get(d)
        if held is None:
            s["rows"].append(list(row))
            by_date[d] = row
        elif abs((held[1] or 0) - (row[1] or 0)) > 1e-9:
            s.setdefault("revisions", []).append(
                {"date": d, "was": held[1], "now": row[1], "seen": _stamp()})
            idx = next(i for i, r in enumerate(s["rows"]) if r[0] == d)
            s["rows"][idx] = list(row)
    s["rows"].sort(key=lambda r: r[0])

    have = {(e[0], e[1]) for e in s["events"]}
    for e in events:
        if (e[0], e[1]) not in have:
            s["events"].append(list(e))
            have.add((e[0], e[1]))
    s["events"].sort(key=lambda e: e[0])

    s["source"] = source
    s["fetched_at"] = _stamp()
    return doc


def mark_terminal(doc: dict, ticker: str, reason: str) -> dict:
    """The series ends here — delisting, rename, or the symbol now resolves to
    a different company. What was retrieved stays retrieved."""
    t = str(ticker).upper()
    s = (doc.get("series") or {}).get(t)
    if s is not None and not s.get("terminal"):
        s["terminal"] = {"reason": str(reason), "at": _stamp()}
    return doc


def mark_unquoted(doc: dict, ticker: str, source: str, reason: str) -> dict:
    """This source has never quoted this symbol, and no rows are held for it.

    A different fact from `terminal`, and kept apart from the series for that
    reason. Terminal says a series ENDED: there are closes, and the last of
    them has stopped being a price. This says there was never a series — the
    SEC maps the symbol to the company and the price source does not carry
    it, which is what a preferred series, a warrant or a listed note looks
    like from here.

    Recorded per (symbol, source), so changing price source does not inherit
    the last one's coverage gaps. Stored outside `series` on purpose: an empty
    entry there would appear in `other_series`, so the sentence explaining why
    a holding has no close would start listing symbols that have never had
    one.
    """
    doc.setdefault("unquoted", {})[str(ticker).upper()] = {
        "reason": str(reason), "source": str(source), "at": _stamp()}
    return doc


def unquoted_of(doc: dict, ticker: str, source: str):
    """The record that this source does not carry this symbol, or None.

    Resolves punctuation the way `series_key` and `terminal_of` do, and is
    scoped to the source that said so — a symbol one source has never heard
    of is not a fact about the next one.
    """
    for form in symbol_forms(ticker):
        m = (doc.get("unquoted") or {}).get(form)
        if m and m.get("source") == source:
            return dict(m)
    return None


# -- reads -------------------------------------------------------------------

def symbol_forms(ticker) -> list[str]:
    """The spellings one instrument's symbol can be stored under.

    The SEC writes a share class with a hyphen (BRK-B); people and price
    sources write a dot (BRK.B); a fetch can leave a series under either,
    because it asks for both the mapped symbols and the one the journal holds.
    Those are one instrument under two spellings — the same equivalence
    tickermap.resolve already applies to the SEC map — and nothing else is.

    A *different class* is a different instrument at a different price and is
    never a form of this one. That is the whole point of this function
    existing: everything above it asks for one security's series by name, and
    the only latitude it gets is punctuation.
    """
    t = str(ticker or "").strip().upper()
    if not t:
        return []
    forms = [t]
    for alt in (t.replace(".", "-"), t.replace("-", ".")):
        if alt not in forms:
            forms.append(alt)
    return forms


def series_key(doc: dict, ticker: str):
    """The stored key holding this instrument's rows, or None.

    Tries the symbol as written and its punctuation variants, in that order,
    and returns the first that actually holds rows — so a series stored under
    the SEC's hyphen form is found by a journal that spells it with a dot,
    and a series that exists but is empty does not shadow one that isn't.
    """
    series = doc.get("series") or {}
    for form in symbol_forms(ticker):
        s = series.get(form)
        if s and s.get("rows"):
            return form
    return None


def other_series(doc: dict, ticker: str) -> list[str]:
    """Every stored series that is NOT this instrument, with rows in it.

    For saying why a value is absent, never for supplying one. A company's
    other share classes are what make "no price for this security" confusing
    when the screen can see prices under the same company, so the absence gets
    to name them — as a sentence, which cannot become a number.
    """
    forms = set(symbol_forms(ticker))
    return sorted(k for k, s in (doc.get("series") or {}).items()
                  if k not in forms and s and s.get("rows"))


def terminal_of(doc: dict, ticker: str):
    """The mark saying this instrument's series has ended, or None.

    A fact, not a judgement about age. "Nothing has traded for a while" and
    "nothing will trade again" look identical in a row of closes, and only one
    of them means the last close has stopped being a price. The series still
    serves that close — data is never hidden — but the mark travels beside it
    so nothing downstream can render a dead series as a live quote.

    Resolves punctuation the way `series_key` does, so the mark is found under
    whichever spelling the series was stored as.
    """
    series = doc.get("series") or {}
    for form in symbol_forms(ticker):
        s = series.get(form)
        if s and s.get("terminal"):
            return dict(s["terminal"])
    return None


def close_on(doc: dict, ticker: str, date: str, reach_days: int | None = None):
    """As-traded close on `date`, or the nearest earlier trading day. Returns
    (date_used, close, days_before) or None.

    `days_before` is how far back it had to reach, and it is reported rather
    than judged. There used to be a seven-day bound here, applied by default
    to every caller that did not think about it, and it was the host holding
    an opinion: whether a close five days before the day you asked about is
    good enough to decide on is a question about a strategy, not about a
    price. Callers that genuinely need a bound pass `reach_days`; nobody in
    this program does.

    Never interpolates, never reaches forward — a price from the future of
    the asked date would silently describe a different world.

    A zero or null close is a no-trade artifact, not a price; it is stepped
    over, exactly as latest_close steps over it, so a halt on the asked day
    cannot mask a real close from the day before.

    The symbol resolves through `series_key`, so one instrument is found
    whichever punctuation it was stored under — and only that instrument."""
    key = series_key(doc, ticker)
    if key is None:
        return None
    s = doc["series"][key]
    rows = s["rows"]
    lo, hi = 0, len(rows)
    while lo < hi:                       # rightmost row with row.date <= date
        mid = (lo + hi) // 2
        if rows[mid][0] <= date:
            lo = mid + 1
        else:
            hi = mid
    from datetime import date as D
    target = D.fromisoformat(date)
    for i in range(lo - 1, -1, -1):
        row = rows[i]
        gap = (target - D.fromisoformat(row[0])).days
        if reach_days is not None and gap > reach_days:
            return None
        if row[1] not in (None, 0):
            return (row[0], float(row[1]), gap)
    return None


def splits_between(doc: dict, ticker: str, after: str, upto: str) -> list:
    """[[date, factor], ...] — the split events for ONE instrument that fall
    strictly after `after` and on or before `upto`, oldest first.

    This is what makes a share count and a close comparable. A cover count is
    shares outstanding on the day the cover states, and a close is a price on
    its own day; a split between the two restates one of them and not the
    other, and the product is wrong by the factor. It is stored — the whole
    reason this file keeps raw rows and events side by side rather than an
    adjusted series — and until now nothing read it.

    Strictly after, because a split effective ON the counting date is already
    in the count the cover states. On or before `upto`, because a split after
    the close has not touched that close.

    A factor that is not a positive number is returned anyway. Whether a
    malformed event should stop a reading is the caller's question, and the
    honest answer at this level is that an event we cannot read is still an
    event: pretending it is not there is the direction that produces a
    confident wrong number.
    """
    key = series_key(doc, ticker)
    if key is None:
        return []
    lo, hi = str(after or "")[:10], str(upto or "")[:10]
    return [[e[0], e[2] if len(e) > 2 else None]
            for e in doc["series"][key].get("events") or []
            if str(e[1]) == "split" and lo < str(e[0])[:10] <= hi]


def latest_close(doc: dict, ticker: str):
    """(date, close) of the newest held row for ONE instrument, or None.
    Staleness is the caller's question to ask — the date is right there."""
    key = series_key(doc, ticker)
    if key is None:
        return None
    for row in reversed(doc["series"][key]["rows"]):
        if row[1] not in (None, 0):
            return (row[0], float(row[1]))
    return None
