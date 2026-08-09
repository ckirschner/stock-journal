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

Entries whose bank definition declares parameters (the risk-free rate) have
no computed value at all here, and no caller supplies one. Those entries
resolve to absent with their own reason, which is honest: nothing in this
host is entitled to invent a rate. Giving a strategy a way to supply one is a
change to the contract and a request against the host, not something to route
around here.
"""

from __future__ import annotations

from pathlib import Path

from . import compute, concept_map, crosscheck, facts_store, price_store

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


# -- as-of observation -------------------------------------------------------
# One reconstruction rule, shared with sell confirmation: an as-of reading
# sees only filings filed by that day and prices at or before that day's
# close. compute.Ctx enforces it; everything here just builds the pinned
# context and caches it inside the same per-CIK bundle, so a fetch
# invalidates reconstructions and live values together.

def _asof_slot(b: dict, as_of: str) -> dict:
    slots = b.setdefault("asof", {})
    if as_of not in slots:
        dated = [f for f in b["filings"]
                 if str(f.get("filed") or "")[:10]
                 and str(f.get("filed") or "")[:10] <= as_of]
        ctx = compute.Ctx(dated, b["prices"], list(b["tickers"]),
                          today=as_of, price_cutoff=as_of)
        slots[as_of] = {"ctx": ctx, "filings": dated, "results": {}}
    return slots[as_of]


def asof_results(cik: int, tickers: list[str], entry_ids,
                 as_of: str) -> dict:
    """{entry_id: result} recomputed from only what was observable on
    `as_of`: filings filed by then, the close on or shortly before it.
    Later restatements are invisible, exactly as in confirmation readings."""
    b = _bundle(cik, tickers)
    slot = _asof_slot(b, as_of)
    out = {}
    for eid in entry_ids:
        if eid not in compute.REGISTRY:
            continue
        if eid not in slot["results"]:
            try:
                slot["results"][eid] = slot["ctx"].entry(eid)
            except Exception as e:                      # noqa: BLE001
                slot["results"][eid] = {"status": "absent",
                                        "reason": f"computation failed: "
                                                  f"{type(e).__name__}: {e}"}
        out[eid] = slot["results"][eid]
    return out


def asof_availability(cik: int, tickers: list[str], as_of: str) -> dict:
    """What the stores can honestly say about `as_of`: how many stored
    filings had been filed by then (and the newest), and whether a close
    exists on or shortly before that day. The reconstruction's basis, for
    the record and the screen."""
    b = _bundle(cik, tickers)
    slot = _asof_slot(b, as_of)
    newest = max((str(f.get("filed") or "")[:10] for f in slot["filings"]),
                 default=None)
    price = price_view_asof(cik, tickers, as_of)
    return {"as_of": as_of,
            "filings_by_then": len(slot["filings"]),
            "filings_held": len(b["filings"]),
            "newest_filed": newest,
            "price": price}


def price_view_asof(cik: int, tickers: list[str], as_of: str) -> dict:
    """The close that belongs to `as_of`: that day or the nearest earlier
    trading day within the stale window, labelled with the date actually
    used. A hand-entered price never appears here — it is a statement about
    now, and reaching it into the past would invent a value."""
    b = _bundle(cik, tickers)
    best = None
    for t in b["tickers"]:
        got = price_store.close_on(b["prices"], t, as_of,
                                   max_lookback_days=compute.STALE_PRICE_DAYS)
        if got and (best is None or got[0] > best[0]):
            best = (got[0], got[1], t)
    if best:
        return {"value": best[1], "source": "fetched", "date": best[0],
                "ticker": best[2]}
    return {"value": None, "source": None, "date": None,
            "reason": f"no close is stored on or shortly before {as_of} for "
                      + (", ".join(b["tickers"]) or "this security")}


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


def confirmation_history(cik: int, tickers: list[str], entry_id: str,
                         params: dict | None = None) -> dict:
    """Per-filing readings for one sell-watched entry, cached with the same
    per-CIK bundle as the computed values — the fingerprint invalidates on
    new filings or prices. The history itself is derived, never stored:
    engine/compute.confirmation_history recomputes it from the filing files
    every time the cache turns over, so it cannot drift from the data."""
    b = _bundle(cik, tickers)
    key = (entry_id, tuple(sorted((params or {}).items())))
    cache = b.setdefault("confirmations", {})
    if key not in cache:
        try:
            cache[key] = compute.confirmation_history(
                b["filings"], b["prices"], list(b["tickers"]), entry_id,
                params or None)
        except Exception as e:                          # noqa: BLE001
            cache[key] = {"entry": entry_id, "cadence": None, "readings": [],
                          "boundaries_held": 0, "truncated": False,
                          "note": f"the filing history could not be read: "
                                  f"{type(e).__name__}: {e}"}
    return cache[key]


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


def ev_reference(cik: int, tickers: list[str]) -> dict:
    """The computed figures an expected-value dialog may prefill or cite:
    free cash flow TTM, shares outstanding, and the owner-earnings
    ingredients (net income, depreciation & amortisation, capex — all TTM).
    Every result carries provenance and, where the source states one, the
    date it is as of. Raw dollars and raw counts; presentation converts."""
    b = _bundle(cik, tickers)
    out = {"fcf_ttm": computed_results(cik, tickers,
                                       ["fcf_ttm"]).get("fcf_ttm")}
    for key, fn in (("shares", compute.shares_outstanding_result),):
        try:
            out[key] = fn(b["ctx"])
        except Exception as e:                          # noqa: BLE001
            out[key] = {"status": "absent",
                        "reason": f"computation failed: "
                                  f"{type(e).__name__}: {e}"}
    for key, input_id in (("net_income_ttm", "net_income"),
                          ("dda_ttm", "dda"),
                          ("capex_ttm", "capex")):
        try:
            out[key] = compute.ttm_flow_result(b["ctx"], input_id)
        except Exception as e:                          # noqa: BLE001
            out[key] = {"status": "absent",
                        "reason": f"computation failed: "
                                  f"{type(e).__name__}: {e}"}
    return out


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
