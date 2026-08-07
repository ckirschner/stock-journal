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


# -- reads -------------------------------------------------------------------

def close_on(doc: dict, ticker: str, date: str, max_lookback_days: int = 7):
    """As-traded close on `date`, or the nearest earlier trading day within
    the lookback. Returns (date_used, close) or None. Never interpolates,
    never reaches forward — a price from the future of the asked date would
    silently describe a different world."""
    s = (doc.get("series") or {}).get(str(ticker).upper())
    if not s or not s["rows"]:
        return None
    rows = s["rows"]
    lo, hi = 0, len(rows)
    while lo < hi:                       # rightmost row with row.date <= date
        mid = (lo + hi) // 2
        if rows[mid][0] <= date:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return None
    row = rows[lo - 1]
    from datetime import date as D
    gap = (D.fromisoformat(date) - D.fromisoformat(row[0])).days
    if gap > max_lookback_days:
        return None
    close = row[1]
    if close in (None, 0):               # zero closes are no-trade artifacts
        return None
    return (row[0], float(close))


def latest_close(doc: dict, ticker: str):
    """(date, close) of the newest held row, or None. Staleness is the
    caller's question to ask — the date is right there."""
    s = (doc.get("series") or {}).get(str(ticker).upper())
    if not s or not s["rows"]:
        return None
    for row in reversed(s["rows"]):
        if row[1] not in (None, 0):
            return (row[0], float(row[1]))
    return None
