"""Building what a strategy receives: one plain dict per security.

The context is the host's entire offer. A strategy consumes it and produces
a decision; it never fetches, never reaches the stores, never sees a
framework type. Everything in here is plain data, deep-copied on the way
out, so a strategy can neither corrupt the host's caches nor reach a live
reference into the journal.

The shape, in full::

    {
      "contract": <contract.CONTRACT_VERSION>,
      "today": "YYYY-MM-DD",        # the clock; everything below obeys it
      "security": {"ticker", "name", "cik"},
      "measures": {bank id: {
          "current": {"status": "known", "value", "source", "cautions",
                      "provenance"}
                   | {"status": "absent", "reason"},
          "series": {"cadence", "points": [{"period_end", "filed", "form",
                                            "accession", "value", "reason"}],
                     "note", "truncated"}}},
      "price":    {"latest": {"status": "known", "value", "date", "ticker",
                              "source"}
                            | {"status": "absent", "reason"},
                   "closes": [[date, close], ...],   # as traded, ascending
                   "events": [[date, "split"|"dividend", amount], ...]},
      "position": {"held", "lots": [{"date", "shares", "price", "kind"}],
                   "shares", "cost_basis",
                   "market_value": known-or-absent,
                   "weight": known-or-absent},       # percent of the account
      "portfolio": {"cash", "account_value",         # known-or-absent
                    "slots": {"occupied"},
                    "holdings": [{"ticker", "name", "shares", "cost_basis",
                                  "opened", "market_value", "weight"}]},
      "values": {id: value},        # the resolved declaration chain
      "inputs": {id: value},        # what the user supplied
    }

Reading rules a strategy can rely on:

- **The clock governs everything.** Series points come only from filings
  filed by `today`; each point is computed from the filings on record at its
  own boundary, priced at the close on or before that boundary's filed date.
  Prices stop at `today`. A reconstructed evaluation therefore sees the
  world of its day, never this one.
- **Absence is a value.** Every bank measure is present in `measures`; where
  the host cannot honestly serve a number, status is "absent" with a reason,
  and a series point that could not be read carries value None with its
  reason. Nothing is zero-filled, carried forward, or interpolated.
- **Percent units are percent numbers** (18.9 means 18.9%), including
  position weight, matching the metric bank's convention.
- **A hand-entered value has no date.** It wins over a computed one, says so
  in `source`, and under a pin carries a caution saying it is the value on
  record now rather than one known to be true then. A hand-entered *price*
  never reaches into the past at all.
- **Unknown keys may appear** in future contract versions; a strategy reads
  what it declares an interest in and ignores the rest.

Two things the host cannot yet answer honestly, so it says so rather than
guessing: free cash and account value are not recorded anywhere in the
journal, which makes every `weight` absent with that reason. A strategy that
binds on weight will be blocked until the journal carries them — the right
failure, and the request that fixes it is against the host.
"""

from __future__ import annotations

import copy
from datetime import date

from . import compute, contract, dataview, facts_store, price_store
from . import profiles as profiles_mod
from . import tickermap

# Series stop at the same number of filing boundaries the sell-confirmation
# view uses; the truncated flag says when older boundaries exist.
SERIES_BOUNDARY_CAP = compute.CONFIRMATION_BOUNDARY_CAP


def _tickers_of(security: dict) -> list:
    """Every symbol the SEC maps to this security's company — share classes
    are genuinely different instruments at different prices, and reading one
    class's series while the journal shows another's would compute a
    different number for the same security. Cached snapshot only; building a
    context never touches the network."""
    ticker = str(security.get("ticker") or "").upper()
    cik = security.get("cik")
    if cik:
        try:
            mapped = tickermap.tickers_for(tickermap.load_cached(), cik)
        except Exception:  # noqa: BLE001 — a missing snapshot is not fatal
            mapped = []
        if mapped:
            if ticker and ticker not in mapped:
                mapped.append(ticker)
            return mapped
    return [ticker] if ticker else []


def _known(value, source, cautions=None, provenance=None) -> dict:
    return {"status": "known", "value": value, "source": source,
            "cautions": list(cautions or []),
            "provenance": list(provenance or [])}


def _absent(reason: str) -> dict:
    return {"status": "absent", "reason": reason}


# -- measures ----------------------------------------------------------------

_UNDATED = ("hand-entered values carry no date, so this one is the value on "
            "record now, not a value known to be true on {day}")


def _current_values(security, cik, tickers, registry_ids, as_of):
    """{entry id: current dict} for every computable entry, hand-entered
    values winning over computed ones exactly as the journal shows them.

    A hand-entered value has no date. It still participates in a pinned
    reading — the journal has no other value to offer — but it is labelled
    undated there, so a strategy is never told a present-day number was
    known on a past day."""
    out = {}
    if cik:
        if as_of:
            results = dataview.asof_results(cik, tickers, registry_ids, as_of)
        else:
            results = dataview.computed_results(cik, tickers, registry_ids)
        for eid, r in results.items():
            if r.get("status") == "computed":
                out[eid] = _known(r["value"], "computed",
                                  r.get("cautions"), r.get("provenance"))
            else:
                out[eid] = _absent(r.get("reason")
                                   or "the value could not be computed")
    cautions = [_UNDATED.format(day=as_of)] if as_of else None
    for eid, value in (security.get("metrics") or {}).items():
        out[eid] = _known(value, "manual", cautions)
    return out


def _series_for(filings, prices, tickers, today):
    """{entry id: series dict} for every entry with a filing cadence, all
    entries of a cadence sharing one pinned context per boundary so the
    series is cheap to assemble and every reading obeys the same clock."""
    dated = [f for f in filings
             if str(f.get("filed") or "")[:10]
             and str(f.get("filed") or "")[:10] <= today]
    out = {}
    for cadence in ("annual", "quarterly"):
        eids = [e for e, c in compute.CADENCE.items()
                if c == cadence and e in compute.REGISTRY]
        bounds = compute.confirmation_boundaries(dated, cadence)
        take = bounds[-SERIES_BOUNDARY_CAP:]
        contexts = []
        for b in take:
            prefix = [f for f in dated
                      if str(f.get("filed") or "")[:10] <= b["filed"]]
            contexts.append((b, compute.Ctx(prefix, prices, tickers,
                                            today=b["filed"],
                                            price_cutoff=b["filed"])))
        for eid in eids:
            points = []
            for b, bctx in contexts:
                try:
                    r = bctx.entry(eid)
                except Exception as e:  # noqa: BLE001 — a point, not a crash
                    r = {"status": "absent",
                         "reason": f"computation failed: "
                                   f"{type(e).__name__}: {e}"}
                ok = r.get("status") == "computed"
                points.append({
                    "period_end": b["period_end"], "filed": b["filed"],
                    "form": b["form"], "accession": b["accession"],
                    "value": r.get("value") if ok else None,
                    "reason": None if ok else (r.get("reason")
                                               or "the reading could not "
                                                  "be computed"),
                })
            if points:
                note = None
            elif not dated:
                note = ("no filing data is stored for this security on or "
                        f"before {today} — fetch data to build its history")
            else:
                note = ("none of the stored filings delivers a new "
                        + ("annual" if cadence == "annual"
                           else "quarterly or annual")
                        + " reporting period, so there is nothing to read")
            out[eid] = {"cadence": cadence, "points": points, "note": note,
                        "truncated": len(bounds) > len(take)}
    return out


def _no_series(note: str) -> dict:
    return {"cadence": None, "points": [], "note": note, "truncated": False}


def _measures(security, cik, tickers, as_of, today) -> dict:
    bank = profiles_mod.load_bank("metric-bank")
    entries = [(str(e.get("id")), e) for e in (bank.get("entries") or [])]
    registry_ids = [eid for eid, _ in entries if eid in compute.REGISTRY]

    current = _current_values(security, cik, tickers, registry_ids, as_of)
    if cik:
        filings = facts_store.load_all_filings(cik)
        prices = price_store.load(cik)
        series = _series_for(filings, prices, tickers, today)
    else:
        series = {}

    out = {}
    for eid, entry in entries:
        kind = str(entry.get("kind") or "")
        if kind == "qualitative":
            cur = current.get(eid) or _absent(
                "assessed by you, not computed — nothing is recorded in the "
                "journal yet")
            ser = _no_series("assessed by you, not computed — no filing "
                            "series exists")
        elif eid not in compute.REGISTRY:
            cur = current.get(eid) or _absent(
                f"this host has no computation for {eid} — its data source "
                "is not ingested")
            ser = _no_series(f"this host has no computation for {eid}")
        else:
            cur = current.get(eid) or _absent(
                "no filing data is stored for this security — fetch data "
                "first")
            ser = series.get(eid) or _no_series(
                "no filing data is stored for this security — fetch data "
                "first" if not cik else
                f"{eid} has no filing cadence, so no per-filing series "
                "exists")
        out[eid] = {"current": cur, "series": ser}
    return out


# -- price -------------------------------------------------------------------

def _price(security, cik, tickers, as_of, today) -> dict:
    if as_of:
        # A hand-entered price is a statement about now; it never reaches
        # into the past, even when no fetched history exists to answer.
        view = dataview.price_view_asof(cik, tickers, as_of) if cik else \
            {"value": None,
             "reason": "no fetched price history is stored for this "
                       f"security, so no close exists to reconstruct "
                       f"for {as_of}"}
    else:
        view = dataview.price_view(security, cik, tickers)
    if view.get("value") is None:
        latest = _absent(view.get("reason")
                         or "no price is stored for this security — fetch "
                            "prices, or enter one by hand")
    else:
        latest = {"status": "known", "value": float(view["value"]),
                  "date": view.get("date"), "ticker": view.get("ticker"),
                  "source": view.get("source")}
    # The history must belong to the same instrument as `latest`: share
    # classes are genuinely different instruments at different prices, and a
    # history from one class under a close from another would let a strategy
    # measure a move that never happened. When no close was served, fall
    # back to the first class holding rows so the history is not silently
    # empty.
    closes, events = [], []
    if cik:
        doc = price_store.load(cik)
        served = latest.get("ticker")
        order = [served] + [t for t in tickers if t != served] if served \
            else list(tickers)
        for t in order:
            s = (doc.get("series") or {}).get(str(t or "").upper())
            if not s or not s.get("rows"):
                continue
            closes = [[d, float(c)] for d, c, *_ in s["rows"]
                      if c not in (None, 0) and d <= today]
            events = [list(e) for e in (s.get("events") or [])
                      if e and e[0] <= today]
            break
    return {"latest": latest, "closes": closes, "events": events}


# -- position and portfolio --------------------------------------------------

def _market_value(sec, shares, as_of=None):
    """Shares times the price that belongs to the clock — the journal's
    effective price live, the reconstructed close under a pin."""
    cik = sec.get("cik")
    tickers = _tickers_of(sec)
    if as_of:
        view = dataview.price_view_asof(cik, tickers, as_of) if cik else \
            {"value": None,
             "reason": "no fetched price history is stored for this "
                       f"security, so no close exists to reconstruct "
                       f"for {as_of}"}
    else:
        view = dataview.price_view(sec, cik, tickers)
    if view.get("value") is None:
        return _absent(view.get("reason")
                       or "no price is stored for this security, so its "
                          "market value cannot be computed")
    if view.get("source") == "manual":
        basis = "the price entered by hand"
    else:
        basis = ("the close of " + view["date"] if view.get("date")
                 else "the recorded close")
    return _known(float(view["value"]) * shares, "computed",
                  provenance=[f"{shares:g} shares at {basis}"])


_NO_ACCOUNT = ("the journal does not yet record free cash, so the account "
               "value — and any weight against it — cannot be computed")


def _lots_of(sec, today) -> list:
    pos = sec.get("position")
    if not pos:
        return []
    opened = str(pos.get("opened") or "")[:10]
    if opened and opened > today:
        return []   # a position opened after the clock did not exist yet
    return [{"date": opened or None, "shares": float(pos.get("shares") or 0),
             "price": pos.get("cost_basis"), "kind": "buy"}]


def _position(security, today, as_of) -> dict:
    lots = _lots_of(security, today)
    shares = sum(l["shares"] for l in lots if l["kind"] == "buy") \
        - sum(l["shares"] for l in lots if l["kind"] == "sell")
    held = security.get("bucket") == "holdings" and bool(lots) and shares > 0
    out = {"held": held, "lots": lots,
           "shares": shares if held else 0.0,
           "cost_basis": (security.get("position") or {}).get("cost_basis")
           if held else None}
    if held:
        out["market_value"] = _market_value(security, shares, as_of)
        out["weight"] = _absent(_NO_ACCOUNT)
    else:
        out["market_value"] = _absent("no position is held")
        out["weight"] = _absent("no position is held")
    return out


def _portfolio(journal_securities, today, as_of) -> dict:
    holdings = []
    for sec in journal_securities or []:
        if sec.get("bucket") != "holdings" or not sec.get("position"):
            continue
        pos = sec["position"]
        # The clock governs the portfolio exactly as it governs the position:
        # a holding opened after the pin did not occupy a slot then, and
        # counting it would hand a slot-bound strategy today's portfolio
        # under yesterday's clock.
        if not _lots_of(sec, today):
            continue
        shares = float(pos.get("shares") or 0)
        holdings.append({
            "ticker": sec.get("ticker"), "name": sec.get("name"),
            "shares": shares, "cost_basis": pos.get("cost_basis"),
            "opened": pos.get("opened"),
            "market_value": _market_value(sec, shares, as_of),
            "weight": _absent(_NO_ACCOUNT),
        })
    return {
        "cash": _absent("the journal does not yet record free cash"),
        "account_value": _absent(_NO_ACCOUNT),
        "slots": {"occupied": len(holdings)},
        "holdings": holdings,
    }


# -- the public build --------------------------------------------------------

def build_context(security: dict, journal_securities: list | None,
                  values: dict, inputs: dict,
                  as_of: str | None = None) -> dict:
    """The context for one security, live or pinned.

    With `as_of`, everything is reconstructed from what was observable on
    that day — filings filed by then, the close on or before it, no
    hand-entered price — exactly as the as-of purchase machinery reads the
    past. Without it, the clock is today and the newest stored data serves.
    """
    today = str(as_of)[:10] if as_of else date.today().isoformat()
    cik = security.get("cik")
    tickers = _tickers_of(security)

    ctx = {
        "contract": contract.CONTRACT_VERSION,
        "today": today,
        "security": {"ticker": security.get("ticker"),
                     "name": security.get("name"),
                     "cik": cik},
        "measures": _measures(security, cik, tickers, as_of, today),
        "price": _price(security, cik, tickers, as_of, today),
        "position": _position(security, today, as_of),
        "portfolio": _portfolio(journal_securities, today, as_of),
        "values": values or {},
        "inputs": inputs or {},
    }
    # One deep copy at the boundary: the strategy's dict shares nothing with
    # the journal or the dataview caches, so mutating it can corrupt nothing.
    return copy.deepcopy(ctx)
