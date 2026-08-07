"""Raw filing facts on disk. Append-only, keyed by CIK, nothing derived.

Layout, inside the user data directory (never the project root):

    facts/CIK##########/company.json          identity, filing index, fetch log
    facts/CIK##########/<accession>.json      one filing's extracted facts

Why this shape:

- **CIK is the key, never ticker.** Tickers change and get reused; CIKs are
  never recycled. A reused symbol can therefore never attach another company's
  filings to this one.
- **One file per filing.** A filing is immutable once made, so its file is
  written once and never edited. Re-fetching discovers *new* accessions and
  writes *new* files; a period already held can never be discarded, because
  nothing ever deletes a filing file. (Re-extracting the same accession — a
  parser upgrade — may rewrite that one file with fresher raw facts of the
  same immutable source; that is an update, not a restatement of history.)
- **Only raw facts.** Values exactly as tagged, with period, unit, dimensions
  and sign metadata. No mapped concepts, no assembled periods, no computed
  entries — computation is cheap and lives in compute.py, so a change of
  judgement there never has stale derived data to fight.

All writes go through the same atomic tmp-then-rename pattern as the journal:
a crash mid-write must never truncate anything.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import store

SCHEMA = "ledger.facts/1"


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cik_dir(cik: int) -> Path:
    return store.data_dir() / "facts" / f"CIK{int(cik):010d}"


def _atomic_write(path: Path, payload: dict) -> None:
    """Write-then-rename with a per-writer temp name: two threads writing the
    same target must never share a temp inode, or one promotes the other's
    half-written bytes."""
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, separators=(",", ":"),
                               ensure_ascii=False))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError):
        # A corrupt file is set aside loudly, never silently reused.
        aside = path.with_name(path.name + ".broken-" +
                               datetime.now().strftime("%Y%m%d-%H%M%S"))
        try:
            path.rename(aside)
        except OSError:
            pass
        return None


# -- company record ----------------------------------------------------------

def load_company(cik: int) -> dict:
    doc = _read(cik_dir(cik) / "company.json")
    if doc is None:
        doc = {"schema": SCHEMA, "cik": int(cik), "identity": None,
               "identity_history": [], "filing_index": [],
               "extraction_errors": {}, "fetches": []}
    return doc


def save_company(cik: int, doc: dict) -> None:
    _atomic_write(cik_dir(cik) / "company.json", doc)


def record_identity(doc: dict, identity: dict) -> dict:
    """Keep the current identity and an append-only history of changes.

    Name changes and ticker changes are how reused symbols and reverse mergers
    announce themselves; the history is the evidence trail.
    """
    current = doc.get("identity")
    if current != identity:
        doc.setdefault("identity_history", []).append(
            {"observed": _stamp(), "identity": identity})
        doc["identity"] = identity
    return doc


def record_filing_index(doc: dict, filings: list[dict]) -> dict:
    """Merge the submissions filing list. Add-only: an accession once listed
    is never removed, even if EDGAR stops listing it."""
    known = {f["accession"] for f in doc.get("filing_index", [])}
    for f in filings:
        if f["accession"] not in known:
            doc.setdefault("filing_index", []).append(dict(f))
            known.add(f["accession"])
    doc["filing_index"].sort(key=lambda f: (f.get("filed") or "", f["accession"]))
    return doc


def record_fetch(doc: dict, entry: dict) -> dict:
    doc.setdefault("fetches", []).append({"at": _stamp(), **entry})
    return doc


def last_fetch(doc: dict) -> dict | None:
    fetches = doc.get("fetches") or []
    return fetches[-1] if fetches else None


# -- filing facts ------------------------------------------------------------

def filing_path(cik: int, accession: str) -> Path:
    safe = str(accession).replace("/", "_")
    return cik_dir(cik) / f"{safe}.json"


def has_filing(cik: int, accession: str) -> bool:
    return filing_path(cik, accession).exists()


def save_filing(cik: int, extraction: dict) -> None:
    """Write one filing's extracted facts. New accessions append; the same
    accession may be rewritten (same immutable source, fresher extraction);
    no code path deletes a filing file."""
    _atomic_write(filing_path(cik, extraction["accession"]), extraction)


def load_filing(cik: int, accession: str) -> dict | None:
    return _read(filing_path(cik, accession))


def load_all_filings(cik: int) -> list[dict]:
    """Every extracted filing for a CIK, oldest filed first."""
    d = cik_dir(cik)
    if not d.exists():
        return []
    out = []
    for p in d.glob("*.json"):
        if p.name == "company.json":
            continue
        doc = _read(p)
        if doc and doc.get("facts") is not None:
            out.append(doc)
    out.sort(key=lambda f: (f.get("filed") or "", f.get("accession") or ""))
    return out


def record_extraction_error(doc: dict, accession: str, error: str) -> dict:
    """A filing that would not extract is a visible fact, not a silent hole."""
    doc.setdefault("extraction_errors", {})[accession] = {
        "error": str(error), "at": _stamp()}
    return doc


def clear_extraction_error(doc: dict, accession: str) -> dict:
    doc.setdefault("extraction_errors", {}).pop(accession, None)
    return doc
