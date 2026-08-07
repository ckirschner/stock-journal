"""The edgartools boundary. Nothing else may import edgartools.

Why a wall: the decision memo measured edgartools' *parser* reproducing printed
statements 34/34 and its *standardization* layer mis-mapping debt lines. So we
take parsing only — every function here returns plain dicts and lists, no
library types, no standardized concepts, no statement-builder output. Tag
selection and period policy live in our own modules (concept_map, periods),
which consume only what this module emits. If edgartools dies or breaks, the
replacement (companyfacts direct, in degraded form) reimplements this module's
five functions and nothing else moves.

Version is pinned exactly in requirements.txt. The known defect coded around
here: the statement *builder* mis-assembles 10-KT transition reports, so we
never call it — extraction goes through the raw fact query, which the memo
verified recovers transition stubs correctly.

The library's HTTP cache is pointed inside the user data directory so nothing
is ever written under the project root at runtime.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

GATEWAY_VERSION = 1          # bump when extraction output changes shape/meaning

_configured = False
_configured_with = None      # (cache_dir, identity) currently in force
_configure_lock = None       # created lazily to avoid importing threading early

# Forms we extract facts from. Amendments are included because they can carry
# restated financials; transition reports because they carry the stub period.
FACT_FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A", "10-Q", "10-Q/A", "10-QT",
              "10-QT/A")


class GatewayError(Exception):
    """A failure inside the boundary, reported with plain text."""


def _boundary(fn):
    """No library exception type crosses the boundary — a caller handling
    this module's failures must never need to know what runs behind it."""
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except GatewayError:
            raise
        except Exception as e:                          # noqa: BLE001
            import traceback as tb
            frames = tb.extract_tb(e.__traceback__)
            where = ""
            if frames:
                last = frames[-1]
                where = (f" [raised at {os.path.basename(last.filename)}:"
                         f"{last.lineno} in {last.name}]")
            raise GatewayError(
                f"{fn.__name__} failed: {type(e).__name__}: {e}{where}. "
                "Network hiccups and SEC throttling both look like this; "
                "fetching again resumes where it left off.") from e
    wrapper.__name__ = fn.__name__
    return wrapper


def configure(cache_dir: str, identity: str) -> None:
    """Point the library's cache inside the user data dir and declare who we
    are to the SEC. Must be called before anything else here.

    identity is the SEC-required User-Agent: a name, a space, a real monitored
    email. Without it EDGAR returns 403.

    IDEMPOTENT ON PURPOSE, and this is load-bearing: edgar.set_identity()
    closes the library's shared HTTP clients "to reset the identity", so
    calling it while another thread's request is in flight kills that request
    mid-air (observed as `TypeError: cannot unpack non-iterable NoneType
    object` out of the cache transport — two of three concurrent first
    fetches died exactly this way). Configuration only touches the library
    when something actually changed.
    """
    global _configured, _configured_with, _configure_lock
    if not (identity or "").strip() or "@" not in identity:
        raise GatewayError(
            "SEC access needs an identity: your name and a real email address "
            "(the SEC requires this on every request). Set it in Settings.")
    import threading
    if _configure_lock is None:
        _configure_lock = threading.Lock()
    wanted = (str(cache_dir), identity.strip())
    with _configure_lock:
        if _configured and _configured_with == wanted:
            return
        # Must be set before the first edgar import; the library reads it
        # early.
        os.environ["EDGAR_LOCAL_DATA_DIR"] = str(cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        import edgar                                # deferred on purpose
        edgar.set_identity(identity.strip())
        _configured = True
        _configured_with = wanted


def _require_configured():
    if not _configured:
        raise GatewayError("gateway.configure() has not been called.")


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- company identity --------------------------------------------------------

@_boundary
def company_info(cik: int) -> dict:
    """Current identity for a CIK, from the SEC submissions data.

    Always called by CIK, never by ticker: CIKs are never recycled, tickers
    are. Ticker-to-CIK resolution is a separate concern (tickermap).
    """
    _require_configured()
    from edgar import Company
    c = Company(int(cik))
    if c is None:
        raise GatewayError(f"CIK {cik} was not found on EDGAR.")
    former = []
    try:
        for fn in (getattr(c.data, "former_names", None) or []):
            if isinstance(fn, dict):
                former.append({"name": str(fn.get("name") or ""),
                               "from": str(fn.get("from") or fn.get("from_", "") or ""),
                               "to": str(fn.get("to") or "")})
    except Exception:
        pass
    # What the company actually files, from the already-loaded recent
    # submissions — no extra requests. This is how a foreign private issuer
    # (20-F/6-K, IFRS) gets to say so instead of yielding a silent empty
    # fetch.
    recent_forms: list[str] = []
    try:
        col = c.data.filings.data.column("form")
        from collections import Counter
        counts = Counter(str(v) for v in col.to_pylist() if v)
        recent_forms = [f for f, _ in counts.most_common(8)]
    except Exception:
        pass
    return {
        "cik": int(c.cik),
        "name": str(c.name or ""),
        "tickers": [str(t) for t in (c.tickers or [])],
        "exchanges": [str(e) for e in (getattr(c, "exchanges", None) or [])],
        "sic": str(getattr(c, "sic", "") or ""),
        "sic_description": str(getattr(c, "sic_description", "") or getattr(c, "industry", "") or ""),
        "fiscal_year_end": str(getattr(c, "fiscal_year_end", "") or ""),
        "former_names": former,
        "recent_forms": recent_forms,
    }


@_boundary
def list_filings(cik: int, forms=FACT_FORMS) -> list[dict]:
    """Every filing of the given forms for a CIK, full history, plain dicts."""
    _require_configured()
    from edgar import Company
    filings = Company(int(cik)).get_filings(form=list(forms))
    out = []
    for f in filings or []:
        out.append({
            "accession": str(f.accession_no),
            "form": str(f.form),
            "filed": str(f.filing_date),
            "period_of_report": str(getattr(f, "period_of_report", "") or ""),
            "primary_document": str(getattr(f, "primary_document", "") or ""),
        })
    return out


# -- fact extraction ---------------------------------------------------------

def _parse_dimensions(raw: dict) -> dict | None:
    """dim_us-gaap_StatementClassOfStockAxis=us-gaap:CommonClassAMember
    becomes {"us-gaap:StatementClassOfStockAxis": "us-gaap:CommonClassAMember"}."""
    dims = {}
    for k, v in raw.items():
        if not k.startswith("dim_") or v in (None, ""):
            continue
        rest = k[4:]
        prefix, _, axis = rest.partition("_")
        dims[f"{prefix}:{axis}"] = str(v)
    return dims or None


def _clean_number(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


@_boundary
def extract_filing(cik: int, accession: str) -> dict:
    """All facts of one filing, as filed, via the raw fact query.

    Returns raw material only: concept, value, unit, period, dimensions,
    statement placement, and the taxonomy's sign metadata. No aggregation, no
    concept mapping, no period assembly — those are our judgement, made
    elsewhere where they can be tested against hand-read ground truth.

    Values are exactly as tagged, under each element's natural sign convention
    (a cash outflow like capex is typically a positive number here even though
    the statement prints it in parentheses). ``balance``/``weight``/
    ``preferred_sign`` travel along so the concept map can state sign policy
    explicitly instead of guessing.
    """
    _require_configured()
    from edgar import Company
    found = Company(int(cik)).get_filings(accession_number=accession)
    if not found:
        raise GatewayError(f"Accession {accession} was not found for CIK {cik}.")
    filing = found[0]
    xbrl = filing.xbrl()
    if xbrl is None:
        raise GatewayError(
            f"{accession} ({filing.form}) has no parseable XBRL. Filings "
            "before each filer's XBRL phase-in date (2009-2011) have none.")

    facts = []
    for raw in xbrl.facts.get_facts():
        concept = str(raw.get("concept") or "")
        if not concept:
            continue
        numeric = _clean_number(raw.get("numeric_value"))
        value = raw.get("value")
        is_dei = concept.startswith("dei:")
        # Numeric facts are the payload. dei facts are kept even when they are
        # strings (period end, fiscal focus, per-class trading symbols on the
        # cover); other non-numeric facts (text blocks) are noise here.
        if numeric is None and not is_dei:
            continue
        if is_dei and numeric is None and len(str(value)) > 200:
            continue                                # dei text blocks
        period_type = str(raw.get("period_type") or "")
        fact = {
            "concept": concept,
            "label": str(raw.get("label") or "") or None,
            "value": numeric if numeric is not None else str(value),
            "unit": str(raw.get("unit_ref") or "") or None,
            "currency": str(raw.get("currency") or "") or None,
            "decimals": raw.get("decimals"),
            "period_type": period_type or None,
            "start": str(raw.get("period_start") or "") or None,
            "end": str(raw.get("period_end") or "") or None,
            "instant": str(raw.get("period_instant") or "") or None,
            "dimensions": _parse_dimensions(raw),
            "statement_type": str(raw.get("statement_type") or "") or None,
            "balance": str(raw.get("balance") or "") or None,
            "weight": _clean_number(raw.get("weight")),
            "preferred_sign": _clean_number(raw.get("preferred_sign")),
        }
        facts.append(fact)

    return {
        "accession": str(accession),
        "cik": int(cik),
        "form": str(filing.form),
        "filed": str(filing.filing_date),
        "period_of_report": str(getattr(filing, "period_of_report", "") or ""),
        "extracted_at": _stamp(),
        "gateway_version": GATEWAY_VERSION,
        "facts": facts,
    }
