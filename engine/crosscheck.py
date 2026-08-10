"""The public-float cross-check: the one comparison that catches a wrong
price basis with data we already hold.

Price × shares outstanding around a 10-K's cover date, compared against
dei:EntityPublicFloat from that same filing. Public float is the market value
of common equity held by non-affiliates, measured by the filer itself at the
last business day of its most recent second fiscal quarter — an independent,
company-computed price × shares data point. One comparison catches
adjusted-price contamination (historical P/E systematically too low),
split-basis errors (off by the split factor), currency errors (off by ~100
for GBX-style quotes) and wrong-share-class errors, none of which error out
anywhere else.

Reading the ratio (market cap ÷ float):

- Float excludes affiliate holdings, so computed market cap should be AT OR
  ABOVE float. Market cap materially BELOW float is close to impossible with
  correct inputs — that is the signature of an adjusted price or a basis
  error, and it fails loudly.
- The two measurements are up to ~7 months apart (float at mid-year, cover
  date near filing), so price drift adds noise; the thresholds are loose on
  purpose and a warn is a prompt to look, not a verdict.
- A huge ratio usually means a closely-held company (founders hold most of
  it) but can also be a share-count scale error; it warns.

Where it can't run, it says exactly why: no float tagged (smaller filers and
some years), no price history reaching the date, or no cover share count.
Nothing here is persisted — it recomputes from raw stores on demand.
"""

from __future__ import annotations

from . import concept_map as cm
from . import price_store

FAIL_LOW = 0.5      # mcap below half of float: inputs are wrong somewhere
WARN_LOW = 0.9      # below float at all is already suspicious; small band
WARN_HIGH = 25.0    # float under 4% of mcap: closely held, or a scale error


def run(filings: list[dict], prices_doc: dict, tickers: list[str]) -> dict:
    """Cross-check every stored annual filing that carries a public float.

    Returns {"checks": [...], "summary": {...}} with one row per 10-K,
    including the rows that could not run and why.
    """
    checks = []
    for f in filings:
        if not str(f.get("form", "")).startswith(("10-K",)):
            continue
        fi = cm.FilingIndex(f)
        row = {"accession": f.get("accession"), "form": f.get("form"),
               "period": f.get("period_of_report"), "status": None,
               "note": None, "ratio": None}
        pf = cm.public_float(fi)
        if pf is None:
            row.update(status="skipped",
                       note="this filing tags no dei:EntityPublicFloat "
                            "(smaller filers and some years omit it)")
            checks.append(row)
            continue
        if pf["value"] == 0:
            row.update(status="skipped",
                       note="public float is tagged as zero (shell or "
                            "wholly-affiliate-held registrant); nothing to "
                            "compare against")
            checks.append(row)
            continue
        shares = cm.resolve_cover_shares(fi)
        if shares is None:
            row.update(status="skipped",
                       note="no shares-outstanding cover fact in this filing")
            checks.append(row)
            continue
        when = pf.get("measured") or f.get("period_of_report")
        mcap, prices_used, missing = _market_cap_at(
            prices_doc, tickers, shares, when)
        if mcap is None:
            row.update(status="skipped",
                       note=f"no stored price near {when} for "
                            f"{', '.join(missing) or 'any ticker'} — fetch "
                            "deeper price history to run this check")
            checks.append(row)
            continue
        ratio = mcap / pf["value"]
        if ratio < FAIL_LOW:
            status = "fail"
            note = ("computed market cap is under half the company's own "
                    "public float — impossible with correct inputs. Suspect "
                    "an adjusted price series, a split-basis mismatch, a "
                    "currency mix-up, or the wrong share class.")
        elif ratio < WARN_LOW:
            status = "warn"
            note = ("computed market cap sits below public float; the "
                    "measurement dates differ by months, so drift can "
                    "explain a little of this, but float should not exceed "
                    "market cap — worth checking the price basis.")
        elif ratio > WARN_HIGH:
            status = "warn"
            note = ("public float is a very small fraction of computed "
                    "market cap — plausible for a closely-held company, but "
                    "also the signature of a share-count scale error.")
        else:
            status = "pass"
            note = None
        row.update(status=status, ratio=round(ratio, 3), note=note,
                   float_usd=pf["value"], float_measured=when,
                   market_cap=round(mcap), prices=prices_used,
                   shares_source=shares["source"])
        checks.append(row)

    ran = [c for c in checks if c["status"] in ("pass", "warn", "fail")]
    summary = {
        "ran": len(ran),
        "skipped": len(checks) - len(ran),
        "pass": sum(1 for c in ran if c["status"] == "pass"),
        "warn": sum(1 for c in ran if c["status"] == "warn"),
        "fail": sum(1 for c in ran if c["status"] == "fail"),
    }
    return {"checks": checks, "summary": summary}


# The one place a reach bound survives, and it is not a staleness rule. This
# check reconciles a figure the filing states on its cover AGAINST the price
# on that cover date, so a close from a month either side is not a stale
# answer to the question — it is an answer to a different one, and the check
# would report a mismatch that is really a calendar gap. Ten days covers a
# holiday week plus a weekend, which is the longest a cover date can be from
# the nearest trading day. Nothing decided by a strategy comes through here.
_REACH = 10


def _market_cap_at(prices_doc, tickers, shares, when):
    """Market cap near a date from as-traded closes; per class where classes
    exist. Returns (mcap|None, [price descriptions], [tickers missing])."""
    used, missing = [], []
    if shares.get("classes"):
        total = 0.0
        fallback = None
        for cl in shares["classes"]:
            sym = cl.get("symbol")
            got = price_store.close_on(prices_doc, sym, when,
                                       reach_days=_REACH) if sym else None
            if got is None:
                if fallback is None:
                    for c2 in shares["classes"]:
                        if c2.get("symbol"):
                            fallback = price_store.close_on(
                                prices_doc, c2["symbol"], when,
                                reach_days=_REACH)
                            if fallback:
                                break
                if fallback is None:
                    missing.append(sym or cl["member"])
                    return None, used, missing
                got = fallback
                used.append(f"{cl['member']}: valued at a listed sibling "
                            f"class's close {got[1]:,.2f} ({got[0]})")
            else:
                used.append(f"{sym}: close {got[1]:,.2f} on {got[0]}")
            total += cl["value"] * got[1]
        return total, used, missing
    for t in tickers:
        got = price_store.close_on(prices_doc, t, when, reach_days=_REACH)
        if got is not None:
            used.append(f"{t}: close {got[1]:,.2f} on {got[0]}")
            return shares["total"] * got[1], used, missing
        missing.append(t)
    return None, used, missing
