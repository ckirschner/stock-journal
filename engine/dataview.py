"""Joining computed values to the journal, with the resolution rule.

The rule, from the task's decisions: **hand-entered values are never
overwritten by a fetch.** Nothing here writes into a security's `metrics` —
computed values live beside them, and the merge happens at read time, visibly:

    merged = computed values, with hand-entered values on top

Both sides survive. The UI can always show "hand-entered 2.1 (computed 1.8)"
because the resolution is a view, not a mutation. Clearing the hand-entered
value is the explicit act that lets the computed one through.

Computation is cheap and never persisted, but it is not free — a company's
filings are a few dozen JSON files — so results are cached in memory against a
fingerprint of the stores (file count + newest mtime + concept-map mtime).
A fetch changes the fingerprint and the cache falls away by itself.

Entries whose bank definition declares parameters (the risk-free rate) cannot
have a single computed value — the parameter is supplied per profile. Those
are computed per profile at evaluation time and overlaid, unless a
hand-entered value already answers them.
"""

from __future__ import annotations

from pathlib import Path

from . import compute, concept_map, crosscheck, facts_store, price_store
from . import profiles as profiles_mod

_cache: dict = {}


# -- cache fingerprint -------------------------------------------------------

def _fingerprint(cik: int) -> tuple:
    parts = []
    d = facts_store.cik_dir(cik)
    if d.exists():
        files = sorted(d.glob("*.json"))
        parts.append(len(files))
        parts.append(max((f.stat().st_mtime for f in files), default=0))
    else:
        parts.append(0)
        parts.append(0)
    p = price_store.path_for(cik)
    parts.append(p.stat().st_mtime if p.exists() else 0)
    try:
        parts.append(Path(concept_map.MAP_PATH).stat().st_mtime)
    except OSError:
        parts.append(0)
    return tuple(parts)


def _bundle(cik: int, tickers: list[str]):
    fp = _fingerprint(cik)
    held = _cache.get(cik)
    if held and held["fp"] == fp and held["tickers"] == tuple(tickers):
        return held
    filings = facts_store.load_all_filings(cik)
    prices = price_store.load(cik)
    ctx = compute.Ctx(filings, prices, tickers)
    held = {"fp": fp, "tickers": tuple(tickers), "ctx": ctx,
            "filings": filings, "prices": prices, "results": {}}
    _cache[cik] = held
    return held


def invalidate(cik: int | None = None) -> None:
    if cik is None:
        _cache.clear()
    else:
        _cache.pop(cik, None)


# -- parameterized entries ---------------------------------------------------

def parameterized_entry_ids() -> set:
    """Bank entries that declare parameters — their value depends on what a
    profile supplies, so they have no single computed value."""
    doc = profiles_mod.load_bank("metric-bank")
    return {str(e.get("id")) for e in (doc.get("entries") or [])
            if e.get("parameters")}


# -- the public joins --------------------------------------------------------

def computed_results(cik: int, tickers: list[str], entry_ids) -> dict:
    """{entry_id: result} for the requested entries, cached."""
    b = _bundle(cik, tickers)
    out = {}
    for eid in entry_ids:
        if eid not in compute.REGISTRY:
            continue
        if eid not in b["results"]:
            try:
                b["results"][eid] = b["ctx"].entry(eid)
            except Exception as e:                      # noqa: BLE001
                b["results"][eid] = {"status": "absent",
                                     "reason": f"computation failed: "
                                               f"{type(e).__name__}: {e}"}
        out[eid] = b["results"][eid]
    return out


def merged_values(security: dict, computed: dict) -> tuple[dict, dict]:
    """(values, sources): computed values with hand-entered on top.

    sources says, per entry id, which side the merged value came from —
    "manual" or "computed" — and never loses the other side: the computed
    result is still in `computed` for the UI to show beside it.
    """
    values, sources = {}, {}
    for eid, r in computed.items():
        if r.get("status") == "computed":
            values[eid] = r["value"]
            sources[eid] = "computed"
    for eid, v in (security.get("metrics") or {}).items():
        values[eid] = v
        sources[eid] = "manual"
    return values, sources


def profile_params_for(profile: dict) -> dict:
    """{entry_id: {param_id: value}} for every parameterized entry this
    resolved profile supplies values for."""
    out = {}
    for tier in profile.get("tiers", []):
        for e in tier.get("entries", []):
            supplied = {p["id"]: p.get("value")
                        for p in (e.get("parameters") or [])
                        if p.get("supplied") and p.get("value") not in (None, "")}
            if supplied:
                out[str(e.get("metric"))] = supplied
    return out


def overlay_for_profile(cik: int, tickers: list[str], base_values: dict,
                        sources: dict, profile: dict,
                        param_ids: set) -> tuple[dict, dict]:
    """Per-profile values: parameterized entries computed with the profile's
    own supplied parameters, unless a hand-entered value already answers."""
    params = profile_params_for(profile)
    if not params:
        return base_values, sources
    values, srcs = dict(base_values), dict(sources)
    b = _bundle(cik, tickers)
    for eid, supplied in params.items():
        if eid not in param_ids or srcs.get(eid) == "manual":
            continue
        if eid not in compute.REGISTRY:
            continue
        try:
            r = compute.compute_entry_with_params(b["ctx"], eid, supplied)
        except Exception:                               # noqa: BLE001
            continue
        if r.get("status") == "computed":
            values[eid] = r["value"]
            srcs[eid] = "computed"
    return values, srcs


def price_view(security: dict, cik: int | None, tickers: list[str]) -> dict:
    """The price the journal should show: hand-entered wins, else the newest
    stored as-traded close, labelled with its date so stale is visible."""
    manual = security.get("price")
    if manual not in (None, ""):
        return {"value": float(manual), "source": "manual", "date": None}
    if cik:
        b = _bundle(cik, tickers)
        best = None
        for t in tickers:
            got = price_store.latest_close(b["prices"], t)
            if got and (best is None or got[0] > best[0]):
                best = (got[0], got[1], t)
        if best:
            return {"value": best[1], "source": "fetched", "date": best[0],
                    "ticker": best[2]}
    return {"value": None, "source": None, "date": None}


def data_status(cik: int | None) -> dict | None:
    """When data was last fetched and what is held — the staleness answer."""
    if not cik:
        return None
    doc = facts_store.load_company(cik)
    last = facts_store.last_fetch(doc)
    held = len(facts_store.load_all_filings(cik))
    prices = price_store.load(cik)
    price_through = None
    terminal = []
    for t, s in (prices.get("series") or {}).items():
        if s.get("rows"):
            d = s["rows"][-1][0]
            price_through = max(price_through or d, d)
        if s.get("terminal"):
            terminal.append({"ticker": t,
                             "reason": s["terminal"].get("reason")})
    # Extraction failures must be readable, not just countable: an entry
    # absent because three 10-Ks failed to extract is a data problem, and
    # rendering it like a fact about the company would mislead. Pre-XBRL
    # filings are a boundary of the source, listed apart from real failures.
    err_detail, pre_xbrl = [], 0
    for accn, e in sorted((doc.get("extraction_errors") or {}).items()):
        msg = str(e.get("error") or "")
        if "no parseable XBRL" in msg:
            pre_xbrl += 1
        else:
            err_detail.append({"accession": accn, "error": msg[:300]})
    return {
        "cik": cik,
        "last_fetch": last,
        "filings_held": held,
        "extraction_errors": len(err_detail),
        "extraction_error_detail": err_detail[:10],
        "pre_xbrl_filings": pre_xbrl,
        "price_through": price_through,
        "terminal_series": terminal,
        "identity": (doc.get("identity") or {}).get("name"),
    }


def coverage(cik: int, tickers: list[str], entry_ids, bank_meta: dict) -> dict:
    """Per bank entry: does it compute, and where it doesn't, why. Plus the
    public-float cross-check, freshly run from the raw stores."""
    b = _bundle(cik, tickers)
    results = computed_results(cik, tickers, entry_ids)
    rows = []
    for eid in entry_ids:
        r = results.get(eid)
        if r is None:
            continue
        meta = bank_meta.get(eid) or {}
        rows.append({
            "id": eid,
            "label": meta.get("label") or eid,
            "status": r.get("status"),
            "value": r.get("value"),
            "format": meta.get("format"),
            "reason": r.get("reason"),
            "cautions": r.get("cautions") or [],
            "provenance": r.get("provenance") or [],
        })
    check = crosscheck.run(b["filings"], b["prices"], tickers)
    return {"entries": rows, "crosscheck": check,
            "status": data_status(cik)}
