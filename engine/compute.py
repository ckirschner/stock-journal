"""Computing the metric bank from stored raw facts and prices.

Every computed bank entry that can be computed is, on the fly, from the raw
facts and price rows on disk. Nothing computed is ever persisted — a change of
judgement in this file or the concept map takes effect everywhere on the next
read, with no stale derived numbers to chase.

The contract, entry by entry:

    {"status": "computed", "value": float, "cautions": [...],
     "provenance": [human-readable strings, each naming its source]}
or
    {"status": "absent", "reason": one sentence saying exactly why}

Absent is a real state, never zero, never an estimate, never a value carried
over from a neighbouring period. Where a bank entry's own not-meaningful test
is computable from the data (a negative denominator, a too-short history),
computing it and serving nonsense would hand the profiles a number that lies;
those come back absent with the not-meaningful reason instead.

Formulas follow config/metric-bank.yaml as written. Where the bank names a
concept (EBIT) that has no XBRL element, the approximation lives in the
concept map with its caution — never silently here. Where a definition cannot
be computed as written, the entry reports that; this file does not rewrite
definitions.

Percent-unit entries are served as percent numbers (18.9 means 18.9%), the
convention the journal's hand-entered values already use.
"""

from __future__ import annotations

from datetime import date
from statistics import median

from . import concept_map as cm
from . import price_store
from .periods import SeriesBuilder, absent, is_absent, label

STALE_PRICE_DAYS = 7
QUARTERS_FOR_OWN_MEDIAN = 20


# --------------------------------------------------------------------------
# context
# --------------------------------------------------------------------------

class Ctx:
    """One company's computation context: filings, prices, memoised entries."""

    def __init__(self, filings: list[dict], prices_doc: dict | None,
                 tickers: list[str], params: dict | None = None,
                 today: str | None = None):
        self.sb = SeriesBuilder(filings)
        self.prices = prices_doc or {"series": {}}
        self.tickers = [str(t).upper() for t in tickers if t]
        self.params = params or {}
        self.today = today or date.today().isoformat()
        self._memo: dict = {}

    # -- prices -------------------------------------------------------------
    def price_now(self):
        """(date, close, ticker) of the newest as-traded close held for any of
        this company's tickers, with staleness answered by the date itself."""
        best = None
        for t in self.tickers:
            got = price_store.latest_close(self.prices, t)
            if got and (best is None or got[0] > best[0]):
                best = (got[0], got[1], t)
        if best is None:
            return absent("no price history is stored for "
                          + (", ".join(self.tickers) or "this security")
                          + " — fetch prices, or check the price source "
                            "settings")
        return {"date": best[0], "close": best[1], "ticker": best[2]}

    def price_on(self, ticker, day):
        return price_store.close_on(self.prices, ticker, day,
                                    max_lookback_days=STALE_PRICE_DAYS)

    # -- memoised entry access ----------------------------------------------
    def entry(self, entry_id):
        if entry_id not in self._memo:
            fn = REGISTRY.get(entry_id)
            self._memo[entry_id] = fn(self) if fn else absent(
                f"{entry_id} has no computation")
        return self._memo[entry_id]


def _prov_point(p: dict) -> str:
    what = p.get("concept") or p.get("matched") or "?"
    when = p.get("end") or p.get("instant") or "?"
    return f"{what} for {when} from {p.get('form') or 'filing'} {p.get('accession')}"


def computed(value, provenance=None, cautions=None) -> dict:
    return {"status": "computed", "value": float(value),
            "provenance": provenance or [], "cautions": cautions or []}


def _absent_result(a) -> dict:
    return {"status": "absent", "reason": a["reason"] if isinstance(a, dict)
            else str(a)}


def _cautions_of(*things) -> list:
    out = []
    for t in things:
        if isinstance(t, dict):
            out.extend(t.get("cautions") or [])
    return sorted(set(out))


# --------------------------------------------------------------------------
# shared sub-results
# --------------------------------------------------------------------------

def _ttm(ctx, input_id):
    key = ("ttm", input_id)
    if key not in ctx._memo:
        ctx._memo[key] = ctx.sb.ttm(input_id)
    return ctx._memo[key]


def _instant(ctx, input_id):
    key = ("instant", input_id)
    if key not in ctx._memo:
        ctx._memo[key] = ctx.sb.instant_latest(input_id)
    return ctx._memo[key]


def _window(ctx, input_id, n):
    key = ("window", input_id, n)
    if key not in ctx._memo:
        ctx._memo[key] = ctx.sb.annual_window(input_id, n)
    return ctx._memo[key]


def _total_debt_with_leases(ctx):
    """total debt + finance lease obligations, without double counting when a
    combined debt-and-lease line already contributed."""
    debt = _instant(ctx, "total_debt")
    if is_absent(debt):
        return debt
    leases = None
    if not debt.get("includes_finance_leases"):
        leases = _instant(ctx, "finance_lease_obligations")
        if is_absent(leases):
            return absent("finance lease obligations could not be resolved: "
                          + leases["reason"])
    value = debt["value"] + (leases["value"] if leases else 0.0)
    prov = [_prov_point(debt)] + ([_prov_point(leases)] if leases else [])
    return {"value": value, "provenance": prov,
            "cautions": _cautions_of(debt, leases)}


def _gross_margin_ttm_pct(ctx):
    """Gross margin TTM as a percent number, or absent."""
    rev = _ttm(ctx, "revenue")
    if is_absent(rev):
        return rev
    gp = _ttm(ctx, "gross_profit")
    if not is_absent(gp):
        num, how = gp, "GrossProfit"
    else:
        cor = _ttm(ctx, "cost_of_revenue")
        if is_absent(cor):
            return absent("the company does not report cost of revenue "
                          "separately (no cost-of-revenue element and no "
                          "gross profit subtotal), so gross margin cannot "
                          "be computed")
        num = {"value": rev["value"] - cor["value"],
               "cautions": _cautions_of(rev, cor)}
        how = "revenue − cost of revenue"
    if rev["value"] == 0:
        return absent("revenue for the trailing window is zero")
    return {"value": num["value"] / rev["value"] * 100.0,
            "how": how, "cautions": _cautions_of(num, rev)}


def _gross_margin_annual_pct(ctx, n):
    """Per-year gross margin percents for the last n fiscal years."""
    rev = _window(ctx, "revenue", n)
    if is_absent(rev):
        return rev
    gp = _window(ctx, "gross_profit", n)
    if not is_absent(gp):
        gp_vals = gp["values"]
        if [p["end"] for p in gp["points"]] != [p["end"] for p in rev["points"]]:
            return absent("gross profit and revenue resolve over different "
                          "fiscal years; the margin series cannot be aligned")
        cautions = _cautions_of(gp, rev)
    else:
        cor = _window(ctx, "cost_of_revenue", n)
        if is_absent(cor):
            return absent("the company does not report cost of revenue "
                          "separately, so gross margin cannot be computed")
        if [p["end"] for p in cor["points"]] != [p["end"] for p in rev["points"]]:
            return absent("cost of revenue and revenue resolve over different "
                          "fiscal years; the margin series cannot be aligned")
        gp_vals = [r - c for r, c in zip(rev["values"], cor["values"])]
        cautions = _cautions_of(cor, rev)
    if any(r == 0 for r in rev["values"]):
        return absent("a fiscal year in the window has zero revenue")
    return {"values": [g / r * 100.0 for g, r in zip(gp_vals, rev["values"])],
            "years": [p["end"] for p in rev["points"]], "cautions": cautions}


def _aligned_windows(ctx, n, *input_ids):
    """Several inputs over the same n fiscal years, or absent. Alignment is
    checked on the period end dates, not assumed."""
    wins = []
    for iid in input_ids:
        w = _window(ctx, iid, n)
        if is_absent(w):
            return w
        wins.append(w)
    ends0 = [p["end"] for p in wins[0]["points"]]
    for w in wins[1:]:
        if [p["end"] for p in w["points"]] != ends0:
            return absent(f"{label(w['points'][0]['input'])} and "
                          f"{label(input_ids[0])} resolve over different "
                          "fiscal years; the window cannot be aligned")
    return wins


def _fcf_per_year(ctx, n):
    wins = _aligned_windows(ctx, n, "cfo", "capex")
    if is_absent(wins):
        if "capex" in str(wins.get("reason", "")) or "property" in str(wins.get("reason", "")):
            return wins
        return wins
    cfo, capex = wins
    return {"values": [c - x for c, x in zip(cfo["values"], capex["values"])],
            "years": [p["end"] for p in cfo["points"]],
            "cautions": _cautions_of(cfo, capex),
            "points": cfo["points"] + capex["points"]}


def _market_cap_result(ctx):
    """Market cap = shares outstanding (cover) × as-traded price, summed per
    class for multi-class filers because each class has its own price."""
    fi = ctx.sb.latest_fi()
    if fi is None:
        return absent("no filings are stored, so shares outstanding is unknown")
    shares = cm.resolve_cover_shares(fi)
    if shares is None:
        # fall back through earlier filings — some 10-Qs omit the cover fact
        for older in reversed(ctx.sb.indices[:-1]):
            shares = cm.resolve_cover_shares(older)
            if shares is not None:
                break
    if shares is None:
        return absent("no stored filing carries a shares-outstanding cover "
                      "fact, so market capitalization cannot be computed")

    cautions = list(shares.get("cautions") or [])
    prov = [f"shares outstanding from {shares['source']}, filing "
            f"{shares['accession']}"]

    if shares.get("classes"):
        total, prices_used = 0.0, []
        primary = ctx.price_now()
        if is_absent(primary):
            return primary
        for cl in shares["classes"]:
            sym = cl.get("symbol")
            close = None
            if sym:
                got = price_store.latest_close(ctx.prices, sym)
                if got:
                    close = got
            if close is None:
                close = (primary["date"], primary["close"])
                cautions.append(
                    f"{cl.get('label') or cl['member']} "
                    f"({cl['value']:,.0f} shares) has no market price"
                    + (f" for symbol {sym}" if sym else "")
                    + f"; valued at the {primary['ticker']} close — an "
                      "unlisted class carries no price of its own")
            total += cl["value"] * close[1]
            prices_used.append(
                f"{sym or cl['member']}: {cl['value']:,.0f} shares × "
                f"{close[1]:,.2f} (close {close[0]})")
        prov.extend(prices_used)
        pdate = primary["date"]
    else:
        p = ctx.price_now()
        if is_absent(p):
            return p
        total = shares["total"] * p["close"]
        prov.append(f"{p['ticker']} close {p['close']:,.2f} on {p['date']}")
        pdate = p["date"]

    gap = (date.fromisoformat(ctx.today) - date.fromisoformat(pdate)).days
    if gap > STALE_PRICE_DAYS:
        cautions.append(f"the newest stored price is {gap} days old "
                        f"({pdate}); fetch prices to bring it current")
    return computed(total, prov, cautions)


# --------------------------------------------------------------------------
# entry computations
# --------------------------------------------------------------------------

def roic_median_5y(ctx):
    wins = _aligned_windows(ctx, 5, "ebit", "income_tax_expense",
                            "pretax_income")
    if is_absent(wins):
        return _absent_result(wins)
    ebit, tax, pretax = wins
    years = [p["end"] for p in ebit["points"]]
    debt = ctx.sb.instant_series_annual("total_debt", 5)
    eq = ctx.sb.instant_series_annual("total_equity", 5)
    cash = ctx.sb.instant_series_annual("cash_and_equivalents", 5)
    for w, what in ((debt, "total debt"), (eq, "total equity"),
                    (cash, "cash")):
        if is_absent(w):
            return _absent_result(absent(f"{what} for the five year-end "
                                         f"balance sheets: {w['reason']}"))
        if w["dates"] != years:
            return _absent_result(absent(
                f"{what} balance-sheet dates do not line up with the fiscal "
                "years of EBIT; the window cannot be aligned"))
    rev = _window(ctx, "revenue", 5)
    roics = []
    for i, y in enumerate(years):
        if pretax["values"][i] <= 0:
            return _absent_result(absent(
                f"pre-tax income for FY ending {y} is zero or negative, so "
                "the effective tax rate that year has no meaning and ROIC "
                "cannot be computed for the window"))
        rate = tax["values"][i] / pretax["values"][i]
        invested = debt["values"][i] + eq["values"][i] - cash["values"][i]
        if not is_absent(rev) and invested < 0.10 * rev["values"][i]:
            return _absent_result(absent(
                f"Not meaningful here: invested capital at FY ending {y} is "
                "under 10% of revenue (the bank's own test) — asset-light "
                "denominators make this ratio explode"))
        if invested == 0:
            return _absent_result(absent(
                f"invested capital at FY ending {y} is zero"))
        roics.append(ebit["values"][i] * (1 - rate) / invested * 100.0)
    prov = [f"EBIT, tax and pre-tax income for FY {years[0]}..{years[-1]}",
            "debt, equity and cash at each fiscal year end"]
    return computed(median(roics), prov,
                    _cautions_of(ebit, tax, pretax, debt, eq, cash))


def roe_median_5y(ctx):
    ni = _window(ctx, "net_income", 5)
    if is_absent(ni):
        return _absent_result(ni)
    years = [p["end"] for p in ni["points"]]
    eq = ctx.sb.instant_series_annual("total_equity", 6)
    if is_absent(eq):
        return _absent_result(absent(
            "average equity needs six year-end balance sheets (each year's "
            "opening and closing equity): " + eq["reason"]))
    if eq["dates"][1:] != years:
        return _absent_result(absent(
            "equity balance-sheet dates do not line up with the fiscal years "
            "of net income; the window cannot be aligned"))
    roes = []
    for i, y in enumerate(years):
        avg_eq = (eq["values"][i] + eq["values"][i + 1]) / 2.0
        if avg_eq <= 0:
            return _absent_result(absent(
                f"Not meaningful here: average shareholders' equity for FY "
                f"ending {y} is zero or negative (the bank's own test)"))
        roes.append(ni["values"][i] / avg_eq * 100.0)
    return computed(median(roes),
                    [f"net income FY {years[0]}..{years[-1]}",
                     "equity at the six bracketing year ends"],
                    _cautions_of(ni, eq))


def total_debt_to_ebitda(ctx):
    debt = _total_debt_with_leases(ctx)
    if is_absent(debt):
        return _absent_result(debt)
    ebitda = _ttm(ctx, "ebitda")
    if is_absent(ebitda):
        return _absent_result(ebitda)
    if ebitda["value"] <= 0:
        return _absent_result(absent(
            "EBITDA for the trailing twelve months is zero or negative; "
            "years-to-repay has no meaning against negative earnings"))
    return computed(debt["value"] / ebitda["value"],
                    debt["provenance"] + [_prov_point(ebitda)],
                    _cautions_of(debt, ebitda))


def net_debt_to_ebitda(ctx):
    debt = _instant(ctx, "total_debt")
    if is_absent(debt):
        return _absent_result(debt)
    cash = _instant(ctx, "cash_and_equivalents")
    if is_absent(cash):
        return _absent_result(cash)
    ebitda = _ttm(ctx, "ebitda")
    if is_absent(ebitda):
        return _absent_result(ebitda)
    if ebitda["value"] <= 0:
        return _absent_result(absent(
            "EBITDA for the trailing twelve months is zero or negative"))
    return computed((debt["value"] - cash["value"]) / ebitda["value"],
                    [_prov_point(debt), _prov_point(cash),
                     _prov_point(ebitda)],
                    _cautions_of(debt, cash, ebitda))


def debt_to_equity(ctx):
    debt = _instant(ctx, "total_debt")
    if is_absent(debt):
        return _absent_result(debt)
    eq = _instant(ctx, "total_equity")
    if is_absent(eq):
        return _absent_result(eq)
    if eq["value"] <= 0:
        return _absent_result(absent(
            "Not meaningful here: total shareholders' equity is zero or "
            "negative (the bank's own test)"))
    return computed(debt["value"] / eq["value"],
                    [_prov_point(debt), _prov_point(eq)],
                    _cautions_of(debt, eq))


def interest_coverage(ctx):
    ebit = _ttm(ctx, "ebit")
    if is_absent(ebit):
        return _absent_result(ebit)
    interest = _ttm(ctx, "interest_expense")
    if is_absent(interest):
        return _absent_result(absent(
            "interest expense could not be resolved — debt-free companies "
            "often tag none, and the bank marks this ratio not meaningful "
            "when interest is near zero: " + interest["reason"]))
    if interest["value"] <= 0:
        return _absent_result(absent(
            "Not meaningful here: interest expense is zero or negative "
            "(the bank's own test — the ratio would be infinite)"))
    return computed(ebit["value"] / interest["value"],
                    [_prov_point(ebit), _prov_point(interest)],
                    _cautions_of(ebit, interest))


def ltd_to_working_capital(ctx):
    ltd = _instant(ctx, "long_term_debt")
    if is_absent(ltd):
        return _absent_result(ltd)
    ca = _instant(ctx, "current_assets")
    if is_absent(ca):
        return _absent_result(ca)
    cl = _instant(ctx, "current_liabilities")
    if is_absent(cl):
        return _absent_result(cl)
    wc = ca["value"] - cl["value"]
    if wc <= 0:
        return _absent_result(absent(
            "Not meaningful here: working capital is zero or negative "
            "(the bank's own test)"))
    return computed(ltd["value"] / wc,
                    [_prov_point(ltd), _prov_point(ca), _prov_point(cl)],
                    _cautions_of(ltd, ca, cl))


def current_ratio(ctx):
    ca = _instant(ctx, "current_assets")
    if is_absent(ca):
        return _absent_result(ca)
    cl = _instant(ctx, "current_liabilities")
    if is_absent(cl):
        return _absent_result(cl)
    if cl["value"] == 0:
        return _absent_result(absent("total current liabilities is zero"))
    return computed(ca["value"] / cl["value"],
                    [_prov_point(ca), _prov_point(cl)],
                    _cautions_of(ca, cl))


def altman_z_score(ctx):
    parts = {}
    for iid in ("current_assets", "current_liabilities", "retained_earnings",
                "total_assets", "total_liabilities"):
        r = _instant(ctx, iid)
        if is_absent(r):
            return _absent_result(r)
        parts[iid] = r
    ebit = _ttm(ctx, "ebit")
    if is_absent(ebit):
        return _absent_result(ebit)
    rev = _ttm(ctx, "revenue")
    if is_absent(rev):
        return _absent_result(rev)
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return _absent_result(absent("market capitalization is needed: "
                                     + mc.get("reason", "")))
    ta = parts["total_assets"]["value"]
    tl = parts["total_liabilities"]["value"]
    if ta == 0 or tl == 0:
        return _absent_result(absent("total assets or total liabilities is zero"))
    wc = parts["current_assets"]["value"] - parts["current_liabilities"]["value"]
    z = (1.2 * wc / ta
         + 1.4 * parts["retained_earnings"]["value"] / ta
         + 3.3 * ebit["value"] / ta
         + 0.6 * mc["value"] / tl
         + 1.0 * rev["value"] / ta)
    prov = ([_prov_point(parts[i]) for i in parts]
            + [_prov_point(ebit), _prov_point(rev),
               "market cap from the market_cap entry"])
    cautions = _cautions_of(ebit, rev, *parts.values()) + mc.get("cautions", [])
    cautions.append("The bank marks this not meaningful for financial "
                    "companies; whether this company is one is a judgement "
                    "the data cannot make — check before relying on it.")
    return computed(z, prov, cautions)


def gross_margin_ttm(ctx):
    gm = _gross_margin_ttm_pct(ctx)
    if is_absent(gm):
        return _absent_result(gm)
    return computed(gm["value"], [f"gross margin via {gm['how']}, trailing "
                                  "twelve months"], gm["cautions"])


def gross_margin_range_5y(ctx):
    gm = _gross_margin_annual_pct(ctx, 5)
    if is_absent(gm):
        return _absent_result(gm)
    return computed(max(gm["values"]) - min(gm["values"]),
                    [f"annual gross margins for FY {gm['years'][0]}.."
                     f"{gm['years'][-1]}"], gm["cautions"])


def gross_margin_change_3y(ctx):
    now = _gross_margin_ttm_pct(ctx)
    if is_absent(now):
        return _absent_result(now)
    ann = _gross_margin_annual_pct(ctx, 4)
    if is_absent(ann):
        return _absent_result(ann)
    return computed(now["value"] - ann["values"][0],
                    [f"gross margin TTM against FY ending {ann['years'][0]}"],
                    sorted(set(now["cautions"] + ann["cautions"])))


def gross_margin_vs_3y_median(ctx):
    now = _gross_margin_ttm_pct(ctx)
    if is_absent(now):
        return _absent_result(now)
    ann = _gross_margin_annual_pct(ctx, 3)
    if is_absent(ann):
        return _absent_result(ann)
    return computed(now["value"] - median(ann["values"]),
                    [f"gross margin TTM against the FY "
                     f"{ann['years'][0]}..{ann['years'][-1]} median"],
                    sorted(set(now["cautions"] + ann["cautions"])))


def fcf_ttm(ctx):
    cfo = _ttm(ctx, "cfo")
    if is_absent(cfo):
        return _absent_result(cfo)
    capex = _ttm(ctx, "capex")
    if is_absent(capex):
        return _absent_result(absent(
            "capital expenditure could not be resolved (" + capex["reason"]
            + ") — free cash flow is not computed with a guessed capex"))
    cautions = _cautions_of(cfo, capex)
    if capex["value"] < 0:
        cautions.append("capex resolved negative, which is unusual for a "
                        "payments element; check the filing")
    return computed(cfo["value"] - capex["value"],
                    [_prov_point(cfo), _prov_point(capex)], cautions)


def fcf_margin_ttm(ctx):
    f = ctx.entry("fcf_ttm")
    if f["status"] != "computed":
        return f
    rev = _ttm(ctx, "revenue")
    if is_absent(rev):
        return _absent_result(rev)
    if rev["value"] == 0:
        return _absent_result(absent("revenue for the trailing window is zero"))
    return computed(f["value"] / rev["value"] * 100.0,
                    f["provenance"] + [_prov_point(rev)],
                    sorted(set(f["cautions"] + _cautions_of(rev))))


def fcf_margin_median_5y(ctx):
    fcf = _fcf_per_year(ctx, 5)
    if is_absent(fcf):
        return _absent_result(fcf)
    rev = _window(ctx, "revenue", 5)
    if is_absent(rev):
        return _absent_result(rev)
    if fcf["years"] != [p["end"] for p in rev["points"]]:
        return _absent_result(absent("free cash flow and revenue resolve over "
                                     "different fiscal years"))
    if any(r == 0 for r in rev["values"]):
        return _absent_result(absent("a fiscal year in the window has zero revenue"))
    vals = [f / r * 100.0 for f, r in zip(fcf["values"], rev["values"])]
    return computed(median(vals),
                    [f"CFO − capex over revenue, FY {fcf['years'][0]}.."
                     f"{fcf['years'][-1]}"],
                    sorted(set(fcf["cautions"] + _cautions_of(rev))))


def fcf_yield_on_ev(ctx):
    f = ctx.entry("fcf_ttm")
    if f["status"] != "computed":
        return f
    ev = ctx.entry("enterprise_value")
    if ev["status"] != "computed":
        return ev
    if ev["value"] <= 0:
        return _absent_result(absent(
            "Not meaningful here: enterprise value is zero or negative "
            "(the bank's own test)"))
    return computed(f["value"] / ev["value"] * 100.0,
                    f["provenance"] + ["enterprise value from the "
                                       "enterprise_value entry"],
                    sorted(set(f["cautions"] + ev["cautions"])))


def cash_conversion_median_5y(ctx):
    fcf = _fcf_per_year(ctx, 5)
    if is_absent(fcf):
        return _absent_result(fcf)
    ni = _window(ctx, "net_income", 5)
    if is_absent(ni):
        return _absent_result(ni)
    if fcf["years"] != [p["end"] for p in ni["points"]]:
        return _absent_result(absent("free cash flow and net income resolve "
                                     "over different fiscal years"))
    vals = []
    for f, n, y in zip(fcf["values"], ni["values"], fcf["years"]):
        if n == 0:
            return _absent_result(absent(
                f"net income for FY ending {y} is zero; conversion against "
                "it has no meaning"))
        vals.append(f / n)
    return computed(median(vals),
                    [f"(CFO − capex) ÷ net income, FY {fcf['years'][0]}.."
                     f"{fcf['years'][-1]}"],
                    sorted(set(fcf["cautions"] + _cautions_of(ni))))


def accruals_ratio(ctx):
    ni = _ttm(ctx, "net_income")
    if is_absent(ni):
        return _absent_result(ni)
    cfo = _ttm(ctx, "cfo")
    if is_absent(cfo):
        return _absent_result(cfo)
    ta = _instant(ctx, "total_assets")
    if is_absent(ta):
        return _absent_result(ta)
    if ta["value"] == 0:
        return _absent_result(absent("total assets is zero"))
    return computed((ni["value"] - cfo["value"]) / ta["value"],
                    [_prov_point(ni), _prov_point(cfo), _prov_point(ta)],
                    _cautions_of(ni, cfo, ta))


def effective_tax_rate_median_5y(ctx):
    wins = _aligned_windows(ctx, 5, "income_tax_expense", "pretax_income")
    if is_absent(wins):
        return _absent_result(wins)
    tax, pretax = wins
    years = [p["end"] for p in tax["points"]]
    rates = []
    for t, p, y in zip(tax["values"], pretax["values"], years):
        if p <= 0:
            return _absent_result(absent(
                f"pre-tax income for FY ending {y} is zero or negative; an "
                "effective rate against it has no meaning"))
        rates.append(t / p * 100.0)
    return computed(median(rates),
                    [f"tax ÷ pre-tax income, FY {years[0]}..{years[-1]}"],
                    _cautions_of(tax, pretax))


def payout_to_fcf_median_5y(ctx):
    fcf = _fcf_per_year(ctx, 5)
    if is_absent(fcf):
        return _absent_result(fcf)
    wins = _aligned_windows(ctx, 5, "dividends_paid", "buybacks",
                            "stock_issuance")
    if is_absent(wins):
        return _absent_result(wins)
    div, buy, iss = wins
    if fcf["years"] != [p["end"] for p in div["points"]]:
        return _absent_result(absent("payout components and free cash flow "
                                     "resolve over different fiscal years"))
    vals = []
    for i, y in enumerate(fcf["years"]):
        if fcf["values"][i] == 0:
            return _absent_result(absent(
                f"free cash flow for FY ending {y} is zero; payout against "
                "it has no meaning"))
        vals.append((div["values"][i] + buy["values"][i] - iss["values"][i])
                    / fcf["values"][i] * 100.0)
    cautions = sorted(set(fcf["cautions"] + _cautions_of(div, buy, iss)))
    if any(f < 0 for f in fcf["values"]):
        cautions.append("free cash flow is negative in at least one window "
                        "year; the bank notes those years' ratios are "
                        "uninterpretable before the median is taken")
    return computed(median(vals),
                    [f"(dividends + buybacks − issuance) ÷ FCF, FY "
                     f"{fcf['years'][0]}..{fcf['years'][-1]}"], cautions)


def operating_income_ttm(ctx):
    oi = _ttm(ctx, "operating_income")
    if is_absent(oi):
        return _absent_result(oi)
    return computed(oi["value"], [_prov_point(oi),
                                  oi.get("ttm_basis") or ""],
                    _cautions_of(oi))


def market_cap(ctx):
    r = _market_cap_result(ctx)
    if is_absent(r):
        return _absent_result(r)
    return r


def enterprise_value(ctx):
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    debt = _instant(ctx, "total_debt")
    if is_absent(debt):
        return _absent_result(debt)
    cash = _instant(ctx, "cash_and_equivalents")
    if is_absent(cash):
        return _absent_result(cash)
    cautions = sorted(set(mc["cautions"] + _cautions_of(debt, cash)))
    cautions.append("mixes a live price against a balance sheet up to a "
                    "quarter old — the bank's own caveat")
    return computed(mc["value"] + debt["value"] - cash["value"],
                    mc["provenance"] + [_prov_point(debt), _prov_point(cash)],
                    cautions)


def _eps_ttm(ctx):
    eps = _ttm(ctx, "diluted_eps")
    if is_absent(eps):
        return eps
    out = dict(eps)
    if eps.get("legs"):
        out["cautions"] = eps["cautions"] + [
            "TTM EPS combines the fiscal-year figure with two year-to-date "
            "figures arithmetically; exact only while the share count is "
            "steady"]
    return out


def pe_ttm(ctx):
    p = ctx.price_now()
    if is_absent(p):
        return _absent_result(p)
    eps = _eps_ttm(ctx)
    if is_absent(eps):
        return _absent_result(eps)
    if eps["value"] <= 0:
        return _absent_result(absent(
            "Not meaningful here: diluted EPS (TTM) is zero or negative "
            "(the bank's own test)"))
    return computed(p["close"] / eps["value"],
                    [f"{p['ticker']} close {p['close']:,.2f} on {p['date']}",
                     _prov_point(eps)], _cautions_of(eps))


def pe_3y_avg_eps(ctx):
    p = ctx.price_now()
    if is_absent(p):
        return _absent_result(p)
    eps = _window(ctx, "diluted_eps", 3)
    if is_absent(eps):
        return _absent_result(eps)
    avg = sum(eps["values"]) / 3.0
    if avg <= 0:
        return _absent_result(absent(
            "Not meaningful here: the three-year average diluted EPS is zero "
            "or negative (the bank's own test)"))
    years = [pt["end"] for pt in eps["points"]]
    return computed(p["close"] / avg,
                    [f"{p['ticker']} close {p['close']:,.2f} on {p['date']}",
                     f"diluted EPS FY {years[0]}..{years[-1]}"],
                    _cautions_of(eps))


def price_to_book(ctx):
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    eq = _instant(ctx, "total_equity")
    if is_absent(eq):
        return _absent_result(eq)
    if eq["value"] <= 0:
        return _absent_result(absent(
            "Not meaningful here: total shareholders' equity is zero or "
            "negative (the bank's own test)"))
    return computed(mc["value"] / eq["value"],
                    mc["provenance"] + [_prov_point(eq)],
                    sorted(set(mc["cautions"] + _cautions_of(eq))))


def price_to_net_tangible_assets(ctx):
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    eq = _instant(ctx, "total_equity")
    if is_absent(eq):
        return _absent_result(eq)
    gw = _instant(ctx, "goodwill")
    if is_absent(gw):
        return _absent_result(gw)
    intang = _instant(ctx, "intangibles_ex_goodwill")
    if is_absent(intang):
        return _absent_result(intang)
    nta = eq["value"] - gw["value"] - intang["value"]
    if nta <= 0:
        return _absent_result(absent(
            "Not meaningful here: net tangible assets are zero or negative "
            "(the bank's own test)"))
    return computed(mc["value"] / nta,
                    mc["provenance"] + [_prov_point(eq), _prov_point(gw),
                                        _prov_point(intang)],
                    sorted(set(mc["cautions"] + _cautions_of(eq, gw, intang))))


def graham_combined_multiple(ctx):
    pe = ctx.entry("pe_3y_avg_eps")
    if pe["status"] != "computed":
        return _absent_result(absent(
            "P/E on three-year average EPS is not available ("
            + pe.get("reason", "") + "), and the product of a meaningless "
            "factor is meaningless — the bank's own test"))
    pb = ctx.entry("price_to_book")
    if pb["status"] != "computed":
        return _absent_result(absent(
            "price to book is not available (" + pb.get("reason", "")
            + "), and the product of a meaningless factor is meaningless"))
    return computed(pe["value"] * pb["value"],
                    ["P/E (3-yr average EPS) × price to book, both computed "
                     "above"],
                    sorted(set(pe["cautions"] + pb["cautions"])))


def owner_earnings_yield(ctx):
    cfo = _ttm(ctx, "cfo")
    if is_absent(cfo):
        return _absent_result(cfo)
    capex = _ttm(ctx, "capex")
    if is_absent(capex):
        return _absent_result(absent(
            "capital expenditure could not be resolved: " + capex["reason"]))
    dda = _ttm(ctx, "dda")
    if is_absent(dda):
        return _absent_result(absent(
            "depreciation & amortization could not be resolved (needed for "
            "the maintenance-capex proxy): " + dda["reason"]))
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    if mc["value"] == 0:
        return _absent_result(absent("market capitalization is zero"))
    maint = min(capex["value"], dda["value"])
    return computed((cfo["value"] - maint) / mc["value"] * 100.0,
                    [_prov_point(cfo),
                     f"maintenance capex proxied as min(capex, D&A) = "
                     f"{maint:,.0f}"],
                    sorted(set(_cautions_of(cfo, capex, dda) + mc["cautions"])))


def ev_to_ebit(ctx):
    ev = ctx.entry("enterprise_value")
    if ev["status"] != "computed":
        return ev
    ebit = _ttm(ctx, "ebit")
    if is_absent(ebit):
        return _absent_result(ebit)
    if ebit["value"] <= 0:
        return _absent_result(absent(
            "Not meaningful here: EBIT (TTM) is zero or negative (the "
            "bank's own test)"))
    return computed(ev["value"] / ebit["value"],
                    ev["provenance"] + [_prov_point(ebit)],
                    sorted(set(ev["cautions"] + _cautions_of(ebit))))


def _quarterly_ratio_series(ctx, kind):
    """20 quarterly observations of EV/EBIT or P/E, each self-consistent on
    its own quarter's original filing, price and cover shares."""
    fis = ctx.sb.quarterly_observation_fis(QUARTERS_FOR_OWN_MEDIAN)
    if len(fis) < QUARTERS_FOR_OWN_MEDIAN:
        return absent(f"only {len(fis)} reporting periods are on record; "
                      f"{QUARTERS_FOR_OWN_MEDIAN} quarters are needed — the "
                      "bank's own minimum")
    values, misses = [], []
    for fi in fis:
        q = fi.period_of_report
        shares = cm.resolve_cover_shares(fi)
        price = None
        if shares is not None:
            if shares.get("classes"):
                total = 0.0
                ok = True
                fallback = None
                for cl in shares["classes"]:
                    sym = cl.get("symbol")
                    got = ctx.price_on(sym, q) if sym else None
                    if got is None:
                        if fallback is None:
                            for c2 in shares["classes"]:
                                if c2.get("symbol"):
                                    fallback = ctx.price_on(c2["symbol"], q)
                                    if fallback:
                                        break
                        if fallback is None:
                            ok = False
                            break
                        got = fallback
                    total += cl["value"] * got[1]
                mcap = total if ok else None
            else:
                for t in ctx.tickers:
                    price = ctx.price_on(t, q)
                    if price:
                        break
                mcap = shares["total"] * price[1] if price else None
        else:
            mcap = None
        if mcap is None:
            misses.append(f"{q}: no shares-outstanding cover fact or no "
                          "price near that date")
            continue

        if kind == "ev_ebit":
            ebit = ctx.sb.ttm_at("ebit", fi)
            debt = cm.resolve_instant(fi, "total_debt", q)
            cash = cm.resolve_instant(fi, "cash_and_equivalents", q)
            if is_absent(ebit) or debt is None or cash is None:
                misses.append(f"{q}: EBIT TTM, debt or cash did not resolve")
                continue
            if ebit["value"] <= 0:
                misses.append(f"{q}: EBIT TTM not positive")
                continue
            values.append((mcap + debt["value"] - cash["value"]) / ebit["value"])
        else:
            eps = ctx.sb.ttm_at("diluted_eps", fi)
            if is_absent(eps) or eps["value"] <= 0:
                misses.append(f"{q}: diluted EPS TTM absent or not positive")
                continue
            values.append(mcap / (shares["total"] if not shares.get("classes")
                                  else sum(c["value"] for c in shares["classes"]))
                          / eps["value"])
    if len(values) < QUARTERS_FOR_OWN_MEDIAN:
        sample = "; ".join(misses[:4])
        return absent(f"only {len(values)} of the last "
                      f"{QUARTERS_FOR_OWN_MEDIAN} quarters could be "
                      f"assembled ({sample}{'; …' if len(misses) > 4 else ''})")
    return {"median": median(values), "n": len(values)}


def ev_ebit_to_own_5y_median(ctx):
    cur = ctx.entry("ev_to_ebit")
    if cur["status"] != "computed":
        return _absent_result(absent(
            "EV/EBIT is not meaningful in the current period ("
            + cur.get("reason", "") + "), and a ratio against a median needs "
            "a current value — the bank's own test"))
    hist = _quarterly_ratio_series(ctx, "ev_ebit")
    if is_absent(hist):
        return _absent_result(hist)
    if hist["median"] == 0:
        return _absent_result(absent("the five-year median EV/EBIT is zero"))
    return computed(cur["value"] / hist["median"],
                    [f"current EV/EBIT over the median of {hist['n']} "
                     "trailing quarterly observations, each priced and "
                     "measured as of its own quarter"],
                    cur["cautions"])


def pe_to_own_5y_median_pe(ctx):
    cur = ctx.entry("pe_ttm")
    if cur["status"] != "computed":
        return _absent_result(absent(
            "P/E (TTM) is not meaningful in the current period ("
            + cur.get("reason", "") + "), and a ratio against a median needs "
            "a current value — the bank's own test"))
    cur_value, cur_note = cur["value"], "current P/E"
    fi = ctx.sb.latest_fi()
    shares = cm.resolve_cover_shares(fi) if fi else None
    if shares and shares.get("classes"):
        # The historical observations are market-cap-per-share (a blend
        # across classes); the current side must be built the same way or a
        # persistent class premium reads as a standing dis/count vs history.
        mc = ctx.entry("market_cap")
        eps = _eps_ttm(ctx)
        if mc["status"] == "computed" and not is_absent(eps) \
                and eps["value"] > 0:
            total = sum(c["value"] for c in shares["classes"])
            if total > 0:
                cur_value = mc["value"] / total / eps["value"]
                cur_note = ("current P/E on the class-blended price (market "
                            "cap ÷ total shares), matching how the history "
                            "is built")
    hist = _quarterly_ratio_series(ctx, "pe")
    if is_absent(hist):
        return _absent_result(hist)
    if hist["median"] == 0:
        return _absent_result(absent("the five-year median P/E is zero"))
    return computed(cur_value / hist["median"],
                    [f"{cur_note} over the median of {hist['n']} trailing "
                     "quarterly observations"],
                    cur["cautions"])


def peg_trailing(ctx):
    pe = ctx.entry("pe_ttm")
    if pe["status"] != "computed":
        return _absent_result(absent("P/E (TTM) is not meaningful ("
                                     + pe.get("reason", "") + ")"))
    growth = ctx.entry("eps_cagr_5y")
    if growth["status"] != "computed":
        return _absent_result(absent(
            "the five-year EPS CAGR is not meaningful ("
            + growth.get("reason", "") + "), and the ratio built on it goes "
            "with it — the bank's own test"))
    if growth["value"] <= 0:
        return _absent_result(absent(
            "the five-year EPS CAGR is zero or negative; a PEG against "
            "non-growth has no meaning"))
    return computed(pe["value"] / growth["value"],
                    ["P/E (TTM) ÷ 5-yr diluted EPS CAGR as a whole number"],
                    sorted(set(pe["cautions"] + growth["cautions"])))


def dividend_adjusted_peg(ctx):
    pe = ctx.entry("pe_ttm")
    if pe["status"] != "computed":
        return _absent_result(absent("P/E (TTM) is not meaningful ("
                                     + pe.get("reason", "") + ")"))
    growth = ctx.entry("eps_cagr_5y")
    if growth["status"] != "computed":
        return _absent_result(absent(
            "the five-year EPS CAGR is not meaningful ("
            + growth.get("reason", "") + ")"))
    yld = ctx.entry("dividend_yield")
    if yld["status"] != "computed":
        return _absent_result(absent("dividend yield is not available ("
                                     + yld.get("reason", "") + ")"))
    denom = growth["value"] + yld["value"]
    if denom <= 0:
        return _absent_result(absent(
            "EPS growth plus dividend yield is zero or negative"))
    return computed(pe["value"] / denom,
                    ["P/E ÷ (5-yr EPS CAGR + dividend yield)"],
                    sorted(set(pe["cautions"] + growth["cautions"]
                               + yld["cautions"])))


def dividend_yield(ctx):
    div = _ttm(ctx, "dividends_paid")
    if is_absent(div):
        return _absent_result(div)
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    if mc["value"] == 0:
        return _absent_result(absent("market capitalization is zero"))
    return computed(div["value"] / mc["value"] * 100.0,
                    [_prov_point(div), "market cap from the market_cap entry"],
                    sorted(set(_cautions_of(div) + mc["cautions"])))


def ncav_to_market_cap(ctx):
    ca = _instant(ctx, "current_assets")
    if is_absent(ca):
        return _absent_result(ca)
    tl = _instant(ctx, "total_liabilities")
    if is_absent(tl):
        return _absent_result(tl)
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    if mc["value"] == 0:
        return _absent_result(absent("market capitalization is zero"))
    return computed((ca["value"] - tl["value"]) / mc["value"],
                    [_prov_point(ca), _prov_point(tl)],
                    sorted(set(_cautions_of(ca, tl) + mc["cautions"])))


def net_cash_to_market_cap(ctx):
    cash = _instant(ctx, "cash_and_equivalents")
    if is_absent(cash):
        return _absent_result(cash)
    sti = _instant(ctx, "short_term_investments")
    if is_absent(sti):
        return _absent_result(sti)
    debt = _instant(ctx, "total_debt")
    if is_absent(debt):
        return _absent_result(debt)
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    if mc["value"] == 0:
        return _absent_result(absent("market capitalization is zero"))
    return computed((cash["value"] + sti["value"] - debt["value"]) / mc["value"],
                    [_prov_point(cash), _prov_point(sti), _prov_point(debt)],
                    sorted(set(_cautions_of(cash, sti, debt) + mc["cautions"])))


def earnings_yield_to_risk_free_multiple(ctx):
    rate = ctx.params.get("risk_free_rate")
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        rate = None
    if rate is None or rate <= 0:
        return _absent_result(absent(
            "no risk-free rate has been supplied — it is a parameter the "
            "profile provides, not a figure in any filing"))
    pe = ctx.entry("pe_3y_avg_eps")
    if pe["status"] != "computed":
        return _absent_result(absent(
            "P/E on three-year average EPS is not meaningful ("
            + pe.get("reason", "") + "), and the earnings yield inherits it"))
    ey = 1.0 / pe["value"] * 100.0
    return computed(ey / rate,
                    [f"earnings yield {ey:.2f}% ÷ risk-free rate "
                     f"{rate:.2f}% (supplied by the profile)"],
                    pe["cautions"])


def _cagr(ctx, input_id, years_span):
    w = _window(ctx, input_id, years_span + 1)
    if is_absent(w):
        return w
    base, last = w["values"][0], w["values"][-1]
    if base <= 0:
        return absent(f"Not meaningful here: {label(input_id)} "
                      f"{years_span} fiscal years ago is zero or negative "
                      "(the bank's own test — no compound rate exists from "
                      "that base)")
    if last < 0:
        # A fractional power of a negative ratio is a complex number in
        # Python — and a nonsense answer in accounting. Positive-to-negative
        # has no compound annual rate; refusing beats a stack trace.
        ends0 = [p["end"] for p in w["points"]]
        return absent(f"Not meaningful here: {label(input_id)} for the "
                      f"latest fiscal year ({ends0[-1]}) is negative — no "
                      "compound annual rate exists from a positive base to "
                      "a negative endpoint")
    ends = [p["end"] for p in w["points"]]
    cautions = list(w["cautions"])
    if last > 0 and base < 0.10 * last:
        # The bank marks a "very small" base not meaningful for EPS and warns
        # about trough-base compounding generally. What counts as very small
        # is a judgement this engine may not make, so the tiny base is named
        # loudly instead of gated silently.
        cautions.append(
            f"the base year ({ends[0]}) is under a tenth of the latest year "
            f"({base:,.2f} against {last:,.2f}); a compound rate from a tiny "
            "base overstates growth, which the bank flags as the moment this "
            "measure misleads")
    return {"value": ((last / base) ** (1.0 / years_span) - 1) * 100.0,
            "prov": [f"{label(input_id)} FY {ends[0]} → FY {ends[-1]}, "
                     "endpoints of a basis-checked window"],
            "cautions": cautions}


def revenue_cagr_5y(ctx):
    r = _cagr(ctx, "revenue", 5)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], r["prov"], r["cautions"])


def revenue_cagr_3y(ctx):
    r = _cagr(ctx, "revenue", 3)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], r["prov"], r["cautions"])


def _families_of(res) -> set:
    """Every tag family contributing to a TTM result (its legs, or itself)."""
    legs = res.get("legs") or [res]
    return {r.get("family") for r in legs} - {None, "either"}


def revenue_change_yoy(ctx):
    latest = ctx.sb.latest_fi()
    if latest is not None and latest.form in (
            "10-K", "10-K/A", "10-KT", "10-KT/A"):
        # Latest report is annual: both trailing windows are fiscal years, so
        # the basis-checked annual window supplies them with every guard
        # (restatement vintages, families, tiling) already applied.
        w = _window(ctx, "revenue", 2)
        if is_absent(w):
            return _absent_result(w)
        if w["values"][0] == 0:
            return _absent_result(absent("revenue for the prior fiscal year "
                                         "is zero"))
        ends = [p["end"] for p in w["points"]]
        return computed((w["values"][1] / w["values"][0] - 1) * 100.0,
                        [f"FY {ends[1]} against FY {ends[0]}, both from a "
                         "basis-checked window"], w["cautions"])
    now = _ttm(ctx, "revenue")
    if is_absent(now):
        return _absent_result(now)
    prior = _prior_year_ttm(ctx, "revenue")
    if is_absent(prior):
        return _absent_result(prior)
    if prior["value"] == 0:
        return _absent_result(absent("revenue for the prior trailing window "
                                     "is zero"))
    # The two trailing windows come from different filing vintages; apply the
    # same basis discipline annual windows get.
    fams = _families_of(now) | _families_of(prior)
    if len(fams) > 1:
        return _absent_result(absent(
            "the two trailing windows resolve revenue under different tag "
            f"families ({' and '.join(sorted(fams))}) — the ASC 606 "
            "transition changed what the number measures, and a growth rate "
            "across it is a definition change dressed as growth"))
    prior_filed = min((r.get("filed") or "")
                      for r in (prior.get("legs") or [prior]))
    for ev in ctx.sb._restatement_events(ctx.sb.annual_points("revenue")):
        if ev["restating_filed"] > prior_filed:
            return _absent_result(absent(
                f"revenue for FY ending {ev['year_end']} was restated by "
                f"filing {ev['restating_accession']} after the prior "
                "trailing window's source filings were prepared — the "
                "comparison would mix bases"))
    return computed((now["value"] / prior["value"] - 1) * 100.0,
                    [f"TTM to {now.get('end')} against TTM to "
                     f"{prior.get('end')}"],
                    _cautions_of(now, prior))


def _prior_year_ttm(ctx, input_id):
    fis = ctx.sb.quarterly_observation_fis(12)
    if not fis:
        return absent("no reporting periods on record")
    latest = fis[-1]
    target = None
    for fi in fis[:-1]:
        span = (date.fromisoformat(latest.period_of_report)
                - date.fromisoformat(fi.period_of_report)).days
        if 340 <= span <= 385:
            target = fi
    if target is None:
        return absent(f"no reporting period ends about a year before "
                      f"{latest.period_of_report}, so a prior trailing "
                      "window cannot be assembled")
    return ctx.sb.ttm_at(input_id, target)


def net_income_cagr_5y(ctx):
    r = _cagr(ctx, "net_income", 5)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], r["prov"], r["cautions"])


def eps_cagr_5y(ctx):
    r = _cagr(ctx, "diluted_eps", 5)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], r["prov"], r["cautions"])


def eps_growth_10y(ctx):
    w = _window(ctx, "diluted_eps", 10)
    if is_absent(w):
        return _absent_result(w)
    early = sum(w["values"][:3]) / 3.0
    late = sum(w["values"][-3:]) / 3.0
    if early <= 0:
        return _absent_result(absent(
            "Not meaningful here: the earlier three-year mean EPS is zero "
            "or negative (the bank's own test)"))
    ends = [p["end"] for p in w["points"]]
    return computed((late / early - 1) * 100.0,
                    [f"mean EPS of FY {ends[0]}..{ends[2]} against mean of "
                     f"FY {ends[-3]}..{ends[-1]}"], w["cautions"])


def ni_minus_revenue_cagr_spread_5y(ctx):
    a = ctx.entry("net_income_cagr_5y")
    b = ctx.entry("revenue_cagr_5y")
    for c in (a, b):
        if c["status"] != "computed":
            return _absent_result(absent(
                "a component CAGR is not meaningful ("
                + c.get("reason", "") + "), and the difference of a "
                "meaningless number is meaningless — the bank's own test"))
    return computed(a["value"] - b["value"],
                    ["net income CAGR minus revenue CAGR, both computed "
                     "above"], sorted(set(a["cautions"] + b["cautions"])))


def eps_minus_revenue_cagr_spread_5y(ctx):
    a = ctx.entry("eps_cagr_5y")
    b = ctx.entry("revenue_cagr_5y")
    for c in (a, b):
        if c["status"] != "computed":
            return _absent_result(absent(
                "a component CAGR is not meaningful ("
                + c.get("reason", "") + ")"))
    return computed(a["value"] - b["value"],
                    ["diluted EPS CAGR minus revenue CAGR, both computed "
                     "above"], sorted(set(a["cautions"] + b["cautions"])))


def _same_filing_revenue_yoy(ctx, fi):
    """Revenue growth, current period against the same period a year earlier,
    both columns from one filing so both sit on one basis."""
    end = fi.period_of_report
    cur = ctx.sb._ytd_resolution(fi, "revenue", end)
    if cur is None:
        return absent("revenue did not resolve in the filing")
    prior = ctx.sb._matching_prior_ytd(fi, "revenue", cur)
    if prior is None:
        return absent("the filing carries no prior-year revenue comparative")
    if prior["value"] == 0:
        return absent("prior-period revenue is zero")
    return {"value": (cur["value"] / prior["value"] - 1) * 100.0,
            "cur": cur, "prior": prior,
            "cautions": _cautions_of(cur, prior)}


def _balance_growth_spread(ctx, input_id, nmw_text):
    fi = ctx.sb.latest_balance_fi()
    if fi is None:
        return _absent_result(absent("no stored filing carries a balance sheet"))
    pair = ctx.sb.instant_pair_yoy(input_id)
    if is_absent(pair):
        if "did not resolve" in pair["reason"]:
            return _absent_result(absent(nmw_text + " (" + pair["reason"] + ")"))
        return _absent_result(pair)
    if pair["ago"]["value"] == 0:
        return _absent_result(absent(
            f"{label(input_id)} a year earlier is zero; a growth rate from "
            "zero has no meaning"))
    rev = _same_filing_revenue_yoy(ctx, fi)
    if is_absent(rev):
        return _absent_result(rev)
    growth = (pair["now"]["value"] / pair["ago"]["value"] - 1) * 100.0
    return computed(growth - rev["value"],
                    [f"{label(input_id)} {pair['ago']['instant']} → "
                     f"{pair['now']['instant']} against revenue over the "
                     f"same span, all from filing {fi.accession}"],
                    sorted(set(_cautions_of(pair["now"], pair["ago"])
                               + rev["cautions"])))


def inventory_minus_revenue_growth_yoy(ctx):
    return _balance_growth_spread(
        ctx, "inventory_net",
        "Not meaningful here: the company reports no inventory — the bank's "
        "own test")


def receivables_minus_revenue_growth_yoy(ctx):
    return _balance_growth_spread(
        ctx, "accounts_receivable_net",
        "Not meaningful here: the company reports no accounts receivable — "
        "the bank's own test")


def profitable_years_10y(ctx):
    w = _window(ctx, "net_income", 10)
    if is_absent(w):
        return _absent_result(w)
    count = sum(1 for v in w["values"] if v > 0)
    ends = [p["end"] for p in w["points"]]
    return computed(count, [f"net income sign for FY {ends[0]}..{ends[-1]}"],
                    w["cautions"])


def _streak_backward(ctx, input_id, holds):
    """Length of the consecutive run of `holds(value)` counting back from the
    most recent fiscal year. The streak may only be reported if every year it
    covers — plus the year that breaks it — tiles, anchors on the company's
    actual latest fiscal year, and does not span a restatement; otherwise
    absent says why."""
    by_end = ctx.sb.annual_points(input_id)
    if not by_end:
        return absent(f"no annual figure for {label(input_id)} could be "
                      "resolved from any stored filing")
    ends = sorted(by_end.keys(), reverse=True)
    latest_annual = ctx.sb.latest_annual_fi()
    if latest_annual is not None and latest_annual.period_of_report \
            and ends[0] < latest_annual.period_of_report:
        # A streak counted from an older year than the company's latest
        # fiscal year is stale — the exact shape of a dividend suspension
        # being read as an unbroken run.
        return absent(
            f"the most recent fiscal year on record "
            f"({latest_annual.period_of_report}) has no resolvable "
            f"{label(input_id)}; a streak counted back from "
            f"{ends[0]} would be stale")
    streak = 0
    traversed = []
    ran_out = True
    for i, e in enumerate(ends):
        p = by_end[e][0]
        if i > 0:
            newer = by_end[ends[i - 1]][0]
            gap = (date.fromisoformat(newer["start"])
                   - date.fromisoformat(p["end"])).days
            if not (0 <= gap <= 7):
                return absent(
                    f"the run of fiscal years breaks between {p['end']} and "
                    f"{newer['start']} (a fiscal-year change or missing "
                    f"year); a streak for {label(input_id)} cannot be "
                    "counted across it")
        traversed.append(p)
        if holds(p["value"]):
            streak += 1
        else:
            ran_out = False
            break
    # basis: the traversed years (including the breaking one) must not span a
    # restatement — the same vintage rule annual windows enforce
    vintages = [p["filed"] for p in traversed]
    lo, hi = min(vintages), max(vintages)
    for ev in ctx.sb._restatement_events(by_end):
        if lo < ev["restating_filed"] <= hi:
            return absent(
                f"{label(input_id)} for FY ending {ev['year_end']} was "
                f"restated by filing {ev['restating_accession']} and the "
                "streak would span years never re-reported on that basis")
    if ran_out and streak > 0:
        return {"value": streak,
                "cautions": [f"the streak reaches the edge of recorded "
                             f"filings ({ends[-1]} is the oldest year "
                             "held); the true streak may be longer"]}
    return {"value": streak, "cautions": []}


def consecutive_annual_loss_years(ctx):
    r = _streak_backward(ctx, "net_income", lambda v: v < 0)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], ["consecutive fiscal years of negative net "
                                 "income, newest backward"], r["cautions"])


def consecutive_dividend_years(ctx):
    r = _streak_backward(ctx, "dividends_paid", lambda v: v > 0)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], ["consecutive fiscal years with dividends "
                                 "paid, newest backward"], r["cautions"])


def _share_change(ctx, span):
    w = _window(ctx, "diluted_wavg_shares", span + 1)
    if is_absent(w):
        return _absent_result(w)
    base, last = w["values"][0], w["values"][-1]
    if base == 0:
        return _absent_result(absent("the base-year share count is zero"))
    ends = [p["end"] for p in w["points"]]
    return computed((last / base - 1) * 100.0,
                    [f"diluted weighted shares FY {ends[0]} → FY {ends[-1]}"],
                    w["cautions"])


def diluted_share_count_change_5y(ctx):
    return _share_change(ctx, 5)


def diluted_share_count_change_3y(ctx):
    return _share_change(ctx, 3)


def _ttm_weighted_shares(ctx, annual_fi, quarter_fi):
    """Time-weighted trailing-twelve-month average diluted shares: the FY
    average with the prior stub swapped for the current one, weighted by
    days. An average cannot be stitched by plain subtraction the way flows
    can — this is the additive-flow machinery adapted for averages."""
    from datetime import date as D
    t = ctx.sb.ttm("diluted_wavg_shares", annual_fi=annual_fi,
                   quarter_fi=quarter_fi)
    if is_absent(t):
        return t
    legs = t.get("legs")
    if not legs:
        return t                     # a plain fiscal year IS a TTM average
    fy, prior, cur = legs
    days = lambda r: (D.fromisoformat(r["end"])
                      - D.fromisoformat(r["start"])).days
    d_fy, d_p, d_c = days(fy), days(prior), days(cur)
    denom = d_fy - d_p + d_c
    if denom <= 0:
        return absent("the trailing share window has no length")
    value = (fy["value"] * d_fy - prior["value"] * d_p
             + cur["value"] * d_c) / denom
    return {**t, "value": value,
            "cautions": sorted(set(t["cautions"] + [
                "trailing average share count is day-weighted from the "
                "fiscal-year and year-to-date averages"]))}


def diluted_share_count_change_ttm(ctx):
    latest = ctx.sb.latest_fi()
    if latest is None:
        return _absent_result(absent("no filings are stored"))
    if latest.form in ("10-K", "10-K/A", "10-KT", "10-KT/A"):
        # Latest report is annual: TTM and prior TTM are the two most recent
        # fiscal-year averages, basis-checked.
        w = _window(ctx, "diluted_wavg_shares", 2)
        if is_absent(w):
            return _absent_result(w)
        if w["values"][0] == 0:
            return _absent_result(absent("the prior-year share count is zero"))
        ends = [p["end"] for p in w["points"]]
        return computed((w["values"][1] / w["values"][0] - 1) * 100.0,
                        [f"average diluted shares FY {ends[1]} against "
                         f"FY {ends[0]}"], w["cautions"])
    cur = _ttm_weighted_shares(ctx, None, None)
    if is_absent(cur):
        return _absent_result(cur)
    # the prior trailing window ends at the observation about a year earlier
    fis = ctx.sb.quarterly_observation_fis(12)
    target = None
    from datetime import date as D
    for f in fis[:-1]:
        span = (D.fromisoformat(latest.period_of_report)
                - D.fromisoformat(f.period_of_report)).days
        if 340 <= span <= 385:
            target = f
    if target is None:
        return _absent_result(absent(
            "no reporting period ends about a year earlier, so a prior "
            "trailing share average cannot be assembled"))
    if target.form in ("10-K", "10-K/A", "10-KT", "10-KT/A"):
        prior = ctx.sb.ttm_at("diluted_wavg_shares", target)
    else:
        annuals = [a for a in ctx.sb.annual_fis if a.filed <= target.filed]
        prior = _ttm_weighted_shares(ctx, annuals[-1] if annuals else None,
                                     target) if annuals else absent(
            "no annual report precedes the prior-year observation")
    if is_absent(prior):
        return _absent_result(absent(
            "the prior trailing share average could not be assembled: "
            + prior["reason"]))
    if prior["value"] == 0:
        return _absent_result(absent("the prior-period share count is zero"))
    return computed((cur["value"] / prior["value"] - 1) * 100.0,
                    [f"day-weighted trailing average diluted shares to "
                     f"{cur.get('end')} against the trailing average to "
                     f"{prior.get('end')}"],
                    _cautions_of(cur, prior))


def goodwill_intangibles_to_assets(ctx):
    gw = _instant(ctx, "goodwill")
    if is_absent(gw):
        return _absent_result(gw)
    intang = _instant(ctx, "intangibles_ex_goodwill")
    if is_absent(intang):
        return _absent_result(intang)
    ta = _instant(ctx, "total_assets")
    if is_absent(ta):
        return _absent_result(ta)
    if ta["value"] == 0:
        return _absent_result(absent("total assets is zero"))
    return computed((gw["value"] + intang["value"]) / ta["value"] * 100.0,
                    [_prov_point(gw), _prov_point(intang), _prov_point(ta)],
                    _cautions_of(gw, intang, ta))


def insider_net_buying_6m(ctx):
    return _absent_result(absent(
        "insider transactions live in Form 4 XML, a separate ingestion "
        "source this pipeline does not read yet — the bank flags this entry "
        "as its own ingestion path"))


def institutional_ownership_pct(ctx):
    return _absent_result(absent(
        "institutional holdings live in 13F filings aggregated across "
        "hundreds of filers, a source this pipeline does not read"))


REGISTRY = {fn.__name__: fn for fn in (
    roic_median_5y, roe_median_5y, total_debt_to_ebitda, net_debt_to_ebitda,
    debt_to_equity, interest_coverage, ltd_to_working_capital, current_ratio,
    altman_z_score, gross_margin_ttm, gross_margin_range_5y,
    gross_margin_change_3y, gross_margin_vs_3y_median, fcf_ttm, fcf_margin_ttm,
    fcf_margin_median_5y, fcf_yield_on_ev, cash_conversion_median_5y,
    accruals_ratio, effective_tax_rate_median_5y, payout_to_fcf_median_5y,
    operating_income_ttm, market_cap, enterprise_value, pe_ttm, pe_3y_avg_eps,
    price_to_book, price_to_net_tangible_assets, graham_combined_multiple,
    owner_earnings_yield, ev_to_ebit, ev_ebit_to_own_5y_median,
    pe_to_own_5y_median_pe, peg_trailing, dividend_adjusted_peg,
    dividend_yield, ncav_to_market_cap, net_cash_to_market_cap,
    earnings_yield_to_risk_free_multiple, revenue_cagr_5y, revenue_cagr_3y,
    revenue_change_yoy, net_income_cagr_5y, eps_cagr_5y, eps_growth_10y,
    ni_minus_revenue_cagr_spread_5y, eps_minus_revenue_cagr_spread_5y,
    inventory_minus_revenue_growth_yoy, receivables_minus_revenue_growth_yoy,
    profitable_years_10y, consecutive_annual_loss_years,
    consecutive_dividend_years, diluted_share_count_change_5y,
    diluted_share_count_change_3y, diluted_share_count_change_ttm,
    goodwill_intangibles_to_assets, insider_net_buying_6m,
    institutional_ownership_pct,
)}


def compute_entry_with_params(ctx: Ctx, entry_id: str, params: dict) -> dict:
    """One parameterized entry under a specific profile's supplied
    parameters. Not memoised on the context: the same entry computes to
    different values under different profiles, by design."""
    fn = REGISTRY.get(entry_id)
    if fn is None:
        return {"status": "absent", "reason": f"{entry_id} has no computation"}
    old = ctx.params
    ctx.params = params or {}
    try:
        return fn(ctx)
    finally:
        ctx.params = old


def compute_all(filings: list[dict], prices_doc: dict | None,
                tickers: list[str], entry_ids=None, params: dict | None = None,
                today: str | None = None) -> dict:
    """Every requested bank entry for one company.

    Returns {entry_id: result}. A crash in one entry becomes that entry's
    absent reason rather than taking the others down — a wrong number is
    the enemy, but so is one bad entry hiding fifty good ones.
    """
    ctx = Ctx(filings, prices_doc, tickers, params=params, today=today)
    out = {}
    for entry_id in (entry_ids or REGISTRY.keys()):
        fn = REGISTRY.get(entry_id)
        if fn is None:
            continue
        try:
            out[entry_id] = ctx.entry(entry_id)
        except Exception as e:                          # noqa: BLE001
            out[entry_id] = {"status": "absent",
                             "reason": f"computation failed: "
                                       f"{type(e).__name__}: {e}"}
    return out
