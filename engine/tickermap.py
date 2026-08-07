"""The SEC ticker-to-CIK map, snapshotted and diffed.

A ticker is a display label the exchange leases out and reassigns; the CIK is
the identity. The SEC publishes only the *current* association
(company_tickers.json, "we periodically update the file but do not guarantee
accuracy or scope") with no history and no archive — so this module builds the
history itself: every fetch snapshots the mapping, and consecutive snapshots
are diffed. A ticker that vanished, moved to a different CIK, or appeared are
the only signals anywhere that a rename, delisting or symbol reuse happened.

One request per refresh, cached for a day, gzip accepted, SEC-compliant
User-Agent. This is the single cheapest mitigation the references identify,
and it is what stops a reused symbol from ever attaching to the wrong company.
"""

from __future__ import annotations

import gzip
import io
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import store

URL = "https://www.sec.gov/files/company_tickers.json"
MAX_AGE_SECONDS = 24 * 3600


class TickerMapError(Exception):
    pass


def _path() -> Path:
    return store.data_dir() / "tickermap.json"


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty() -> dict:
    return {"schema": "ledger.tickermap/1", "fetched_at": None,
            "map": {}, "changes": []}


def _load() -> dict:
    p = _path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty()
    except (json.JSONDecodeError, OSError):
        # The changes list is the ONLY record anywhere of tickers that
        # vanished, moved CIK or appeared. A corrupt file is set aside like
        # every other store — silently starting fresh would erase the
        # rename/reuse evidence trail and suppress the next diff as a
        # "baseline".
        aside = p.with_name(p.name + ".broken-" +
                            datetime.now().strftime("%Y%m%d-%H%M%S"))
        try:
            p.rename(aside)
        except OSError:
            pass
        doc = _empty()
        doc["changes"].append({"seen": _stamp(), "kind": "history_lost",
                               "note": f"the previous snapshot could not be "
                                       f"read and was set aside as "
                                       f"{aside.name}; diffs restart from "
                                       "this point"})
        return doc


def _save(doc: dict) -> None:
    import os
    import tempfile
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp",
                               dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(doc, separators=(",", ":")))
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _fetch(identity: str) -> dict:
    req = urllib.request.Request(URL, headers={
        "User-Agent": identity,
        "Accept-Encoding": "gzip",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    except urllib.error.HTTPError as e:
        raise TickerMapError(
            f"The SEC ticker map returned HTTP {e.code}. A 403 usually means "
            "the identity (name + email) in Settings is missing or malformed.") from e
    except urllib.error.URLError as e:
        raise TickerMapError(f"Could not reach www.sec.gov: {e.reason}") from e
    data = json.loads(raw.decode("utf-8"))
    # Keyed by stringified sequence numbers, not CIKs. cik_str is an integer.
    out = {}
    for row in data.values():
        t = str(row.get("ticker") or "").upper()
        if t:
            out[t] = {"cik": int(row["cik_str"]), "title": str(row.get("title") or "")}
    if not out:
        raise TickerMapError("The SEC ticker map came back empty; not trusting it.")
    return out


def load_cached() -> dict:
    """The last snapshot, without touching the network. For reads that must
    stay offline (rendering state); fetching refreshes it."""
    return _load()


def refresh(identity: str, force: bool = False) -> dict:
    """Snapshot the current mapping and record what changed since last time.

    Returns the full stored document. Changes are append-only observations:
    {"seen": ..., "ticker": ..., "kind": "appeared|vanished|moved",
     "was_cik": ..., "now_cik": ...}
    """
    doc = _load()
    if not force and doc.get("fetched_at"):
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(doc["fetched_at"])).total_seconds()
        if age < MAX_AGE_SECONDS:
            return doc
    fresh = _fetch(identity)
    old = doc.get("map") or {}
    now = _stamp()
    for t, row in fresh.items():
        prev = old.get(t)
        if prev is None:
            if old:      # first-ever snapshot is a baseline, not a wave of appearances
                doc["changes"].append({"seen": now, "ticker": t, "kind": "appeared",
                                       "now_cik": row["cik"]})
        elif prev["cik"] != row["cik"]:
            doc["changes"].append({"seen": now, "ticker": t, "kind": "moved",
                                   "was_cik": prev["cik"], "now_cik": row["cik"]})
    for t, prev in old.items():
        if t not in fresh:
            doc["changes"].append({"seen": now, "ticker": t, "kind": "vanished",
                                   "was_cik": prev["cik"]})
    doc["map"] = fresh
    doc["fetched_at"] = now
    _save(doc)
    return doc


def resolve(doc: dict, ticker: str):
    """Current CIK for a ticker, or None. The SEC writes share classes with a
    hyphen (BRK-B); accept the dot form users type."""
    t = str(ticker).strip().upper()
    m = doc.get("map") or {}
    hit = m.get(t) or m.get(t.replace(".", "-"))
    return dict(hit) if hit else None


def tickers_for(doc: dict, cik: int) -> list[str]:
    """Every symbol currently mapping to a CIK — share classes appear as
    separate rows against the same CIK."""
    return sorted(t for t, row in (doc.get("map") or {}).items()
                  if row["cik"] == int(cik))
