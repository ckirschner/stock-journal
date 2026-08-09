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
      "position": {"held", "shares", "opened",
                   "lots":      [{"date", "shares", "remaining", "open"}],
                   "disposals": [{"date", "shares"}],
                   "market_value": known-or-absent,
                   "weight": known-or-absent},       # percent of the account
      "portfolio": {"cash", "account_value",         # known-or-absent
                    "slots": {"occupied"},
                    "holdings": [{"ticker", "name", "shares", "opened",
                                  "market_value", "weight"}]},
      "values": {id: value},        # the resolved declaration chain
      "inputs": {id: value},        # the answers that apply, with answers
      "reference": {file name: parsed},   # what the bundle ships, frozen
    }

`reference` is attached by engine/contract.evaluate rather than built here:
it belongs to the strategy, not the security, and it is shared read-only
across every evaluation instead of being copied for each one.

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
- **`position` is the holding you have now, except where it says otherwise.**
  `held`, `shares`, `opened`, `market_value` and `weight` are all about the
  current holding period — the run from the purchase that took the position
  up from nothing to now. `opened` is that period's first purchase and does
  not move when a lot is trimmed away: it answers when this holding began,
  not how old the oldest surviving share is. A rule that wants lot ages reads
  `lots`, where every entry carries its own date, `remaining` and `open`.
  A re-entry after a full exit opens a new period, so `opened` counts from
  the re-entry.
- **`lots` and `disposals` are the security's whole record, not the current
  holding's.** Every purchase this journal ever made in the name is in
  `lots`, and every sale in `disposals`, including those belonging to a
  holding that closed before the current one opened. That is deliberate: a
  strategy asking "have I owned this before" has nowhere else to look. But it
  means these two are scoped differently from everything beside them, so a
  rule counting entries wants `[l for l in lots if l["open"]]` rather than
  the length.

  `disposals` cannot be narrowed that way, and that is a known gap rather
  than a design: each entry carries only `date` and `shares`, so nothing on
  it says which holding it ended. Two securities can arrive with identical
  `lots`, `disposals` and `shares` and different `opened` — one closed out
  and bought back the same day, one added and trimmed the same day — and no
  rule reading `disposals` can tell them apart. Until an entry can say which
  holding it belongs to, treat `disposals` as a fact about the security and
  not about the position, and do not derive "what this holding has sold" from
  it.
- **Nothing here says what a position cost.** Cost basis is reporting and is
  kept out of the context entirely, so a rule that fires on the distance
  from your own purchase price cannot be written. See contract.HOST_FACTS.
- **The account is derived, never declared.** `portfolio.account_value` is
  free cash plus the market value of every holding the journal knows about,
  which is why free cash is the one thing a strategy has to ask for. An
  account value the user typed would be a conclusion the tool could reach
  itself, and when a weight came out wrong there would be no way to see
  which input was wrong.
- **Free cash is only served where a strategy asked for it.** An input
  carrying the `cash` role is what unlocks cash, the account value and every
  weight; a strategy that declares no such input gets all of them absent
  with a reason saying the question was never asked. The host holds no view
  about whether a journal ought to record cash.
"""

from __future__ import annotations

import copy
from datetime import date

from . import bank as bank_mod
from . import compute, contract, dataview, facts_store, portfolio, price_store
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
    bank = bank_mod.load_bank()
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


_NO_CASH_ROLE = ("no strategy in this journal asks for your free cash, so "
                 "the journal does not record it and the account it would "
                 "be measured against cannot be reached")
_UNDATED_INPUT = ("what you told this journal carries no date, so this is "
                  "the answer on record now, not one known to be true on "
                  "{day}")


def _usd(n) -> str:
    return f"${n:,.0f}"


def _cash(roles, as_of) -> dict:
    """Free cash, from whichever declared input claims the `cash` role.

    Under a pin it is served with the same caution a hand-entered measure
    carries: an answer with no date participates, because the journal has no
    other to offer, but it is never presented as a figure known to have been
    true on a past day.
    """
    entry = (roles or {}).get("cash")
    if entry is None:
        return _absent(_NO_CASH_ROLE)
    if "value" not in entry:
        return _absent(entry.get("reason")
                       or "this journal has no answer for it yet")
    cautions = [_UNDATED_INPUT.format(day=as_of)] if as_of else None
    return _known(float(entry["value"]), "input", cautions,
                  [f'"{entry["label"]}", answered in this journal\'s '
                   "settings"])


def _account_value(cash, holdings) -> dict:
    """Free cash plus every holding at market. Derived rather than asked
    for: it is a figure the host can reach, and a typed one would let two
    numbers disagree with nothing to say which was wrong.

    One unpriced holding makes the whole total absent. Treating a missing
    price as zero would understate the account and quietly inflate every
    weight measured against it — a confident wrong answer in the number a
    sizing rule binds on.
    """
    if cash["status"] != "known":
        return _absent("the account is free cash plus the value of every "
                       "holding, and " + cash["reason"])
    dark = [h for h in holdings if h["market_value"]["status"] != "known"]
    if dark:
        names = ", ".join(str(h["ticker"]) for h in dark)
        return _absent(
            f"{len(dark)} of {len(holdings)} holdings have no price "
            f"({names}), so the account total cannot be reached without "
            "inventing one")
    total = cash["value"] + sum(h["market_value"]["value"] for h in holdings)
    return _known(total, "computed", cash.get("cautions"),
                  [f'{_usd(cash["value"])} free cash plus {len(holdings)} '
                   f'holding{"" if len(holdings) == 1 else "s"} at market'])


def _weight(market_value, account_value) -> dict:
    """A holding's share of the account, as a percent number. Arithmetic,
    not an opinion — whether a weight is too high belongs to a strategy."""
    if market_value["status"] != "known":
        return _absent(market_value["reason"])
    if account_value["status"] != "known":
        return _absent(account_value["reason"])
    if account_value["value"] <= 0:
        return _absent("the account works out to nothing or less once free "
                       "cash is included, so a share of it cannot be "
                       "expressed")
    return _known(market_value["value"] / account_value["value"] * 100,
                  "computed", account_value.get("cautions"),
                  [f'{_usd(market_value["value"])} of an account of '
                   f'{_usd(account_value["value"])}'])


def _position(security, today, as_of, account_value) -> dict:
    """The lot history as a strategy reads it: every acquisition with what
    remains of it, every disposal, and not one figure about cost.

    `opened` is the current holding period's first purchase — when this
    holding began — and is read off the period rather than recomputed here,
    so what a strategy is told and what the screens show for the same holding
    are one value rather than two that happen to agree.
    """
    held_lots = portfolio.open_lots(security, today)
    shares = round(sum(l["remaining"] for l in held_lots), 8)
    held = shares > 0
    out = {
        "held": held,
        "shares": shares,
        "opened": portfolio.opened_on(security, today),
        "lots": [{"date": l["date"], "shares": float(l["shares"]),
                  "remaining": l["remaining"], "open": l["open"]}
                 for l in held_lots],
        "disposals": [{"date": l["date"], "shares": float(l["shares"])}
                      for l in portfolio.lots(security, "sell", today)],
    }
    if held:
        out["market_value"] = _market_value(security, shares, as_of)
        out["weight"] = _weight(out["market_value"], account_value)
    else:
        out["market_value"] = _absent("no position is held")
        out["weight"] = _absent("no position is held")
    return out


def _portfolio(journal_securities, subject, today, as_of, roles) -> dict:
    holdings = []
    seen = set()
    # The security being evaluated counts even when the caller passed no
    # list: a portfolio that excluded the holding in front of you would
    # measure its weight against an account it was not part of.
    pool = list(journal_securities or [])
    if subject is not None:
        pool.append(subject)
    for sec in pool:
        ticker = str(sec.get("ticker") or "")
        if ticker in seen:
            continue
        seen.add(ticker)
        # The clock governs the portfolio exactly as it governs the position:
        # a holding bought after the pin did not occupy a slot then, and a
        # sale made after it had not reduced anything.
        shares = portfolio.shares_held(sec, today)
        if shares <= 0:
            continue
        holdings.append({
            "ticker": sec.get("ticker"), "name": sec.get("name"),
            "shares": shares,
            "opened": portfolio.opened_on(sec, today),
            "market_value": _market_value(sec, shares, as_of),
        })
    cash = _cash(roles, as_of)
    account_value = _account_value(cash, holdings)
    for h in holdings:
        h["weight"] = _weight(h["market_value"], account_value)
    return {
        "cash": cash,
        "account_value": account_value,
        "slots": {"occupied": len(holdings)},
        "holdings": holdings,
    }


# -- the public build --------------------------------------------------------

def build_context(security: dict, journal_securities: list | None,
                  values: dict, inputs: dict,
                  as_of: str | None = None, record: dict | None = None) -> dict:
    """The context for one security, live or pinned.

    With `as_of`, everything is reconstructed from what was observable on
    that day — filings filed by then, the close on or before it, no
    hand-entered price — exactly as the as-of purchase machinery reads the
    past. Without it, the clock is today and the newest stored data serves.

    `record` is the loaded strategy. It is what turns the journal's raw
    answers into the ones that currently apply, and what says which of them
    the host may report as a figure. Without it the answers are passed
    through as given and no role is served — which is the honest reading of
    "there is no strategy to ask", not a silent fallback.
    """
    today = str(as_of)[:10] if as_of else date.today().isoformat()
    cik = security.get("cik")
    tickers = _tickers_of(security)

    effective, roles = dict(inputs or {}), {}
    if record is not None:
        effective, _ = contract.check_inputs(record, inputs or {},
                                             values or {})
        roles = contract.input_roles(record, effective)

    # The portfolio comes first: a position's weight is measured against an
    # account that includes the position, so the total has to exist before
    # any share of it can.
    folio = _portfolio(journal_securities, security, today, as_of, roles)
    ctx = {
        "contract": contract.CONTRACT_VERSION,
        "today": today,
        "security": {"ticker": security.get("ticker"),
                     "name": security.get("name"),
                     "cik": cik},
        "measures": _measures(security, cik, tickers, as_of, today),
        "price": _price(security, cik, tickers, as_of, today),
        "position": _position(security, today, as_of,
                              folio["account_value"]),
        "portfolio": folio,
        "values": values or {},
        "inputs": effective,
    }
    # One deep copy at the boundary: the strategy's dict shares nothing with
    # the journal or the dataview caches, so mutating it can corrupt nothing.
    return copy.deepcopy(ctx)
