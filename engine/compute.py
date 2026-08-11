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
from .periods import ANNUAL_FORMS, SeriesBuilder, absent, is_absent, label

QUARTERS_FOR_OWN_MEDIAN = 20


# --------------------------------------------------------------------------
# context
# --------------------------------------------------------------------------

class Ctx:
    """One company's computation context: filings, prices, memoised entries.

    `price_cutoff` turns the context into an as-of observation: price_now()
    then serves the close on or shortly before that day instead of the newest
    close, and `today` should be pinned to the same day so nothing in the
    context runs on two clocks. Used for per-filing confirmation readings —
    "what was observable when this filing arrived" — never for the live view.
    """

    def __init__(self, filings: list[dict], prices_doc: dict | None,
                 tickers: list[str],
                 today: str | None = None, price_cutoff: str | None = None):
        self.sb = SeriesBuilder(filings)
        self.prices = prices_doc or {"series": {}}
        self.tickers = [str(t).upper() for t in tickers if t]
        self.today = today or date.today().isoformat()
        self.price_cutoff = str(price_cutoff)[:10] if price_cutoff else None
        self.price_dates_served: set = set()
        self._memo: dict = {}

    # -- prices -------------------------------------------------------------
    def price_now(self):
        """(date, close, ticker) of the newest as-traded close held for any of
        this company's tickers — or, under a price_cutoff, the close on or
        shortly before that day. Staleness is answered by the date itself."""
        best = None
        for t in self.tickers:
            if self.price_cutoff:
                got = price_store.close_on(self.prices, t, self.price_cutoff)
            else:
                got = price_store.latest_close(self.prices, t)
            if got and (best is None or got[0] > best[0]):
                best = (got[0], got[1], t)
        if best is None:
            if self.price_cutoff:
                return absent("no close is stored on or shortly before "
                              f"{self.price_cutoff} for "
                              + (", ".join(self.tickers) or "this security"))
            return absent("no price history is stored for "
                          + (", ".join(self.tickers) or "this security")
                          + " — fetch prices, or check the price source "
                            "settings")
        self.price_dates_served.add(best[0])
        return {"date": best[0], "close": best[1], "ticker": best[2]}

    def price_on(self, ticker, day):
        got = price_store.close_on(self.prices, ticker, day)
        if got:
            self.price_dates_served.add(got[0])
        return got

    def price_for(self, ticker):
        """The close a computation should use for one specific symbol: the
        newest held, or under a price_cutoff the close on or shortly before
        it. Every price consumer must come through the context — a direct
        latest_close call would quietly price an as-of reading at today.

        The symbol here comes off a filing cover, which writes it the way the
        company does; the series was stored under whatever the SEC map said.
        price_store resolves the punctuation between them, so a class that is
        listed and priced is not mistaken for one that has no price of its
        own — which is the difference between using this class's close and
        borrowing a sibling's.
        """
        if self.price_cutoff:
            got = price_store.close_on(self.prices, ticker, self.price_cutoff)
        else:
            got = price_store.latest_close(self.prices, ticker)
        if got:
            self.price_dates_served.add(got[0])
        return got

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


def computed(value, provenance=None, cautions=None, leave_one_out=None) -> dict:
    """One entry's answer.

    `leave_one_out` is the same figure worked out again with each single
    fiscal year of its window taken out — [{"dropped": year end, "value":
    v}, ...]. It is carried by every entry whose estimator reads a window,
    because a breach of a window measure cannot be confirmed by waiting: the
    offending year stays in the window, so two consecutive readings are
    mostly the same data. Dropping the flattering year and asking again is
    the test that means something, and the host does it rather than a
    strategy, for the reason it does every other comparison.

    Absent where the estimator reads no window. Never a copy of the
    full-window value — a robustness check that silently falls back to the
    number it was checking is not a check, so nothing at all is safer.
    """
    out = {"status": "computed", "value": float(value),
           "provenance": provenance or [], "cautions": cautions or []}
    if leave_one_out:
        out["leave_one_out"] = [{"dropped": str(o["dropped"]),
                                 "value": float(o["value"])}
                                for o in leave_one_out]
    return out


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


# --------------------------------------------------------------------------
# window statistics, and what they look like with one year taken out
#
# Every statistic read over a window of fiscal years is computed here rather
# than inline, so the one-year-dropped readings come out of the same
# arithmetic as the full-window one. Two implementations of a median — one
# for the answer and one for the robustness check — would be two things that
# agree until they don't, which is the failure the whole citation split
# exists to prevent one level up.
# --------------------------------------------------------------------------

def _with_one_out(values, years, stat, defined=None):
    """(the statistic, [{"dropped": year, "value": v}, ...]).

    One entry per fiscal year in the window. A window of two would leave one
    observation behind and there is no statistic of one worth reporting, so
    nothing is offered there.

    `defined` is for a statistic with a denominator. A ratio guarded against
    a non-positive denominator on the full window can still meet one when a
    year is dropped — five years averaging positive free cash flow with one
    very good year among them is the case — and what comes back is either a
    crash or a NEGATIVE ratio, which on a lower-is-better measure reads as
    the company being in wonderful shape. A wrong number arriving through the
    door marked robustness, in the flattering direction, is worse than no
    reading at all. So the year is skipped: dropping it leaves nothing to
    compare against rather than something excellent.
    """
    full = stat(values)
    if len(values) < 3:
        return full, []
    outs = []
    for i, y in enumerate(years):
        rest = values[:i] + values[i + 1:]
        if defined is not None and not defined(rest):
            continue
        outs.append({"dropped": y, "value": stat(rest)})
    return full, outs


def _median_of(values, years):
    return _with_one_out(values, years, median)


def _range_of(values, years):
    return _with_one_out(values, years, lambda vs: max(vs) - min(vs))


# How many fiscal years are averaged at each end of a growth window. Three,
# which is Graham's own construction and the only one already in this bank —
# see eps_growth_10y, where it was doing this job alone.
GROWTH_ENDS = 3


def _growth_window(span, ends=GROWTH_ENDS):
    """How many fiscal years a growth rate over `span` years needs.

    The two averages are centred `span` years apart, so the window runs from
    the oldest year of the earlier average to the newest of the later one:
    span + ends. Five years centre to centre with three-year averages is
    eight fiscal years of history.
    """
    return span + ends


def _averaged_ends(values, years, ends=GROWTH_ENDS):
    """(base mean, end mean, [(year, base mean, end mean) with that year
    dropped]).

    Only the years inside the two averages are offered as one-out readings.
    The years in the gap between them are in neither average, so dropping one
    changes nothing, and handing the same number back as a robustness check
    would be worse than handing back none.
    """
    def mean(xs):
        return sum(xs) / len(xs)

    base, late = mean(values[:ends]), mean(values[-ends:])
    outs = []
    for i in range(ends):
        outs.append((years[i],
                     mean(values[:ends][:i] + values[:ends][i + 1:]), late))
    for i in range(ends):
        j = len(values) - ends + i
        outs.append((years[j], base,
                     mean(values[-ends:][:i] + values[-ends:][i + 1:])))
    return base, late, outs


def _averaged_cagr_from(values, years, span, ends=GROWTH_ENDS):
    """(rate, one-out rates, base mean, end mean), or (None, ...) where no
    compound rate exists from this base."""
    base, late, outs = _averaged_ends(values, years, ends)
    if base <= 0 or late < 0:
        return None, [], base, late

    def rate_of(b, e):
        return ((e / b) ** (1.0 / span) - 1) * 100.0

    return (rate_of(base, late),
            [{"dropped": y, "value": rate_of(b, e)}
             for y, b, e in outs if b > 0 and e >= 0],
            base, late)


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


def _cover_shares(ctx):
    """The newest cover-fact shares resolution, falling back through earlier
    filings — some 10-Qs omit the cover fact. Absent with the reason when no
    stored filing answers."""
    fi = ctx.sb.latest_fi()
    if fi is None:
        return absent("no filings are stored, so shares outstanding is unknown")
    shares = cm.resolve_cover_shares(fi)
    if shares is None:
        for older in reversed(ctx.sb.indices[:-1]):
            shares = cm.resolve_cover_shares(older)
            if shares is not None:
                break
    if shares is None:
        return absent("no stored filing carries a shares-outstanding cover "
                      "fact")
    return shares


def shares_outstanding_result(ctx):
    """Total shares outstanding from the newest cover fact, as a plain
    count — the divisor a per-share valuation needs. Multi-class filers are
    summed here, which is right for dividing a whole-company value and wrong
    for market cap (each class has its own price; see _market_cap_result)."""
    shares = _cover_shares(ctx)
    if is_absent(shares):
        return _absent_result(shares)
    cautions = list(shares.get("cautions") or [])
    if shares.get("classes") and len(shares["classes"]) > 1:
        cautions.append(f"{len(shares['classes'])} share classes summed to "
                        "one count")
    r = computed(shares["total"],
                 [f"shares outstanding from {shares['source']}, filing "
                  f"{shares['accession']}"], cautions)
    # The date the cover fact itself states, when it states one; the filing
    # date is only the fallback, and is a few weeks later than the count.
    when = shares.get("stated") or shares.get("filed")
    if when:
        r["asof"] = str(when)[:10]
    return r


def ttm_flow_result(ctx, input_id):
    """One flow input over the trailing twelve months as a bank-style result
    — a reference figure with provenance, computed exactly as the entries
    above compute it, never typed."""
    r = _ttm(ctx, input_id)
    if is_absent(r):
        return _absent_result(r)
    out = computed(r["value"], [_prov_point(r)], _cautions_of(r))
    if r.get("end"):
        out["asof"] = str(r["end"])[:10]
    return out


def blend_classes(ctx, classes: list, on: str | None = None):
    """Every share class at its own close, with the classes that have none
    valued at the largest priced class — or absent when none of them can be
    priced at all.

    Returns {"total", "provenance", "cautions", "oldest"} or an absent dict.

    **This is an approximation, and it is the only one in the file.** A class
    with no stored close of its own is valued at a sibling's, which principle 4
    does not otherwise permit: the filing does not account for what that class
    was worth, so nothing is asserting the number. It is kept because the case
    it exists for is ordinary — a founder class that never lists, converting
    one-for-one into a class that does, a few percent of the count — and
    refusing would take market cap, and with it P/E, enterprise value,
    dividend yield and both cash-to-cap ratios, away from companies most people
    would think of as unremarkable.

    What it may not do is pretend to be a measurement. So:

    - The anchor is the **largest priced class**, not whichever series happens
      to be newest. The old rule flipped between fetches whenever one class's
      prices lagged the other's, silently moving a headline figure.
    - The caution states what is true — that the class has no stored price —
      never that it is unlisted, which the host has no evidence for and which
      is false whenever a listed class simply failed to fetch.
    - The caution says **how much of the company** was valued this way. Seven
      percent of the count is a footnote; ninety percent means the figure is
      mostly an assumption, and only the reader can judge which.
    - With no priced class at all there is nothing to anchor to, and the answer
      is absence rather than a number built on a symbol that is not a class.

    `on` pins every close to a past day, so the historical side of a
    self-comparison blends by exactly the same rule as the live side. Two
    different rules either side of "P/E against its own five-year median" made
    the comparison meaningless.
    """
    priced, unpriced = [], []
    for cl in classes:
        sym = cl.get("symbol")
        got = (ctx.price_on(sym, on) if on else ctx.price_for(sym)) \
            if sym else None
        (priced if got else unpriced).append((cl, got))

    count = sum(cl["value"] for cl in classes) or 0.0
    if not priced:
        named = ", ".join(str(cl.get("symbol") or cl["member"])
                          for cl in classes)
        return absent(
            f"none of the {len(classes)} share classes ({named}) has a stored "
            "close of its own"
            + (f" on or shortly before {on}" if on else "")
            + ", so market capitalization cannot be reached without inventing "
              "a price")

    anchor, anchor_close = max(priced, key=lambda pair: pair[0]["value"])
    total, prov, cautions, dates = 0.0, [], [], []
    borrowed = 0.0
    for cl, got in priced + unpriced:
        close = got or anchor_close
        if got is None:
            borrowed += cl["value"]
        total += cl["value"] * close[1]
        dates.append(close[0])
        prov.append(f"{cl.get('symbol') or cl['member']}: "
                    f"{cl['value']:,.0f} shares × {close[1]:,.2f} (close "
                    f"{close[0]}{'' if got else ', borrowed'})")
    if unpriced:
        share = f"{borrowed / count * 100:.1f}%" if count else "an unknown "\
            "share"
        cautions.append(
            ", ".join(f"{cl.get('label') or cl['member']} "
                      f"({cl['value']:,.0f} shares)" for cl, _ in unpriced)
            + f" — {share} of the share count — "
            + ("has" if len(unpriced) == 1 else "have")
            + " no stored close, and "
            + ("is" if len(unpriced) == 1 else "are")
            + f" valued here at the {anchor.get('symbol') or anchor['member']}"
              f" close of {anchor_close[0]}. That is an assumption about what "
              "those shares are worth, not a measurement of it.")
    return {"total": total, "provenance": prov, "cautions": cautions,
            "oldest": min(dates)}


def _market_cap_result(ctx):
    """Market cap = shares outstanding (cover) × as-traded price, summed per
    class for multi-class filers because each class has its own price."""
    shares = _cover_shares(ctx)
    if is_absent(shares):
        if "cover" in shares["reason"]:
            return absent(shares["reason"]
                          + ", so market capitalization cannot be computed")
        return shares

    cautions = list(shares.get("cautions") or [])
    prov = [f"shares outstanding from {shares['source']}, filing "
            f"{shares['accession']}"]

    if shares.get("classes"):
        blend = blend_classes(ctx, shares["classes"])
        if is_absent(blend):
            return _absent_result(blend)
        total = blend["total"]
        prov.extend(blend["provenance"])
        cautions.extend(blend["cautions"])
        # The OLDEST close in the blend, not the newest. Staleness measured
        # against the freshest class cannot see a second class whose prices
        # stopped updating months ago, which is precisely the one worth
        # knowing about.
        pdate = blend["oldest"]
    else:
        p = ctx.price_now()
        if is_absent(p):
            return p
        total = shares["total"] * p["close"]
        prov.append(f"{p['ticker']} close {p['close']:,.2f} on {p['date']}")
        # One count for the whole company and more than one symbol trading
        # against it: the count covers shares this price does not describe,
        # and the cover gave nothing to split them by.
        others = [t for t in ctx.tickers
                  if t != p["ticker"] and ctx.price_for(t)]
        if others:
            cautions.append(
                f"the cover states one share count for the whole company, but "
                f"{', '.join(others)} also trade against it; every share is "
                f"valued here at the {p['ticker']} close")
        pdate = p["date"]

    # The price's age, stated always and judged never. This used to be a
    # caution that appeared only past seven days, which made the fact
    # conditional on a host opinion: a six-day-old close said nothing about
    # its age and an eight-day-old one did, so a reader could not tell "this
    # is current" from "nobody asked". Seven days is a judgement, it differs
    # between strategies, and it belonged to nobody — the host carries the
    # date, and what is too old is the strategy's call.
    cautions.append(_price_age(ctx, pdate))
    cautions.extend(_ended_series(ctx))
    return computed(total, prov, cautions)


def _price_age(ctx, pdate) -> str:
    """How old the close behind a price-derived figure is, in words.

    Always the OLDEST close where several classes were blended, matching the
    rule the blend itself uses: staleness measured against the freshest class
    cannot see a second class whose prices stopped updating months ago, which
    is precisely the one worth knowing about.

    Counted against the context's own clock, so a reading rebuilt for a past
    filing reports its age as of THAT day. Against the wall clock it would
    report an age that is right for today and wrong for the day being
    reconstructed — a confident number, in a record that keeps it forever.
    """
    days = (date.fromisoformat(ctx.today) - date.fromisoformat(pdate)).days
    if days <= 0:
        return f"priced at the close of {pdate}, the latest held"
    return (f"priced at the close of {pdate}, "
            + ("a day" if days == 1 else f"{days} days")
            + " before "
            + ("the day this reading was rebuilt for" if ctx.price_cutoff
               else "today"))


def _ended_series(ctx) -> list[str]:
    """A word for every one of this company's symbols whose price series has
    ended. A fact about the instrument, not a judgement about age: a series
    that stopped last week and one that will never trade again look identical
    in a list of closes, and only one of them still has a price."""
    out = []
    for t in ctx.tickers:
        mark = price_store.terminal_of(ctx.prices, t)
        if mark:
            out.append(f"the {t} price series has ended ("
                       f"{mark.get('reason') or 'no reason recorded'}), so "
                       "its last close is the last price it ever had and not "
                       "what it trades at")
    return out


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
    value, outs = _median_of(roics, years)
    return computed(value, prov,
                    _cautions_of(ebit, tax, pretax, debt, eq, cash), outs)


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
    value, outs = _median_of(roes, years)
    return computed(value,
                    [f"net income FY {years[0]}..{years[-1]}",
                     "equity at the six bracketing year ends"],
                    _cautions_of(ni, eq), outs)


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
    value, outs = _range_of(gm["values"], gm["years"])
    return computed(value,
                    [f"annual gross margins for FY {gm['years'][0]}.."
                     f"{gm['years'][-1]}"], gm["cautions"], outs)


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
    value, outs = _median_of(vals, fcf["years"])
    return computed(value,
                    [f"CFO − capex over revenue, FY {fcf['years'][0]}.."
                     f"{fcf['years'][-1]}"],
                    sorted(set(fcf["cautions"] + _cautions_of(rev))), outs)


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
    value, outs = _median_of(vals, fcf["years"])
    return computed(value,
                    [f"(CFO − capex) ÷ net income, FY {fcf['years'][0]}.."
                     f"{fcf['years'][-1]}"],
                    sorted(set(fcf["cautions"] + _cautions_of(ni))), outs)


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
    value, outs = _median_of(rates, years)
    return computed(value,
                    [f"tax ÷ pre-tax income, FY {years[0]}..{years[-1]}"],
                    _cautions_of(tax, pretax), outs)


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
    value, outs = _median_of(vals, fcf["years"])
    return computed(value,
                    [f"(dividends + buybacks − issuance) ÷ FCF, FY "
                     f"{fcf['years'][0]}..{fcf['years'][-1]}"], cautions, outs)


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
                # The same blend as the live figure, by the same anchor rule.
                # This side used to borrow from the first class that happened
                # to have a price and the live side from whichever series was
                # newest — so "P/E against its own five-year median" compared
                # two numbers built on different share classes, which is the
                # one thing that comparison must not do.
                blend = blend_classes(ctx, shares["classes"], on=q)
                mcap = None if is_absent(blend) else blend["total"]
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


# How small a base may be against the end of the same window before the
# compound rate between them stops being a growth rate. A tenth: earnings that
# multiplied more than tenfold over five years did not compound at 58% a year,
# they arrived.
#
# It is here rather than in any strategy because it is an applicability test —
# the bank's own kind of level, a statement that the number does not mean
# anything for this company rather than a judgement about what to do. And it is
# a refusal rather than a caution, because this value feeds verdicts: a wrong
# number with a warning beside it is still a wrong verdict, since the caution
# is read by a person and ignored by the arithmetic. It used to be a caution.
APPEARED_MULTIPLE = 0.10

# And the second half of the same test, which is what stops the first from
# firing on a business that genuinely grew tenfold. Earnings can multiply by
# ten because the company sells ten times as much, or because a margin came
# back from nothing; only the second is an appearance. Measured as the base
# period's net margin against the end period's, both from the same three
# fiscal years the averages already use.
#
# Both halves are needed and neither is enough, and that was measured rather
# than assumed. Across 380 real filers sampled by size, the margin half alone
# fires on about one in seven — including several whose base-period earnings
# were plainly substantial, because it is algebraically a margin-expansion
# test, which this bank already publishes as ni_minus_revenue_cagr_spread_5y.
# The multiple half alone fires on a company whose revenue multiplied about as
# fast as its earnings, which is growth. Together they fired on one filer in
# 380: base-period net margin of 0.05%, revenue shrinking, and earnings that
# came from emerging from bankruptcy.
APPEARED_MARGIN = 0.50


def _appeared_rather_than_grew(ctx, years, base_ends=GROWTH_ENDS):
    """An absent reason where the earnings at the base of this window
    appeared rather than grew, or None.

    Routing rather than greying. A tiny base says something specific — that
    a margin came back or a turnaround landed — and a margin recovery has a
    ceiling that unit growth does not. So the reason says which question the
    reader is actually looking at, rather than reporting the record as
    unanswerable.

    `years` are the measure's own fiscal years, so net income and revenue are
    read over exactly the window whose rate is in question rather than over
    whatever eight years those two inputs happen to reach on their own.
    """
    n = len(years)
    ni = _window(ctx, "net_income", n)
    if is_absent(ni) or [p["end"] for p in ni["points"]] != years:
        return None
    base_ni = sum(ni["values"][:base_ends])
    end_ni = sum(ni["values"][-base_ends:])
    if end_ni <= 0 or base_ni <= 0 or base_ni >= APPEARED_MULTIPLE * end_ni:
        return None

    rev = _window(ctx, "revenue", n)
    aligned = (not is_absent(rev)
               and [p["end"] for p in rev["points"]] == years)
    base_rev = sum(rev["values"][:base_ends]) if aligned else 0.0
    end_rev = sum(rev["values"][-base_ends:]) if aligned else 0.0
    multiple = end_ni / base_ni
    grew = (f"net income over FY {years[0]}..{years[base_ends - 1]} was "
            f"{base_ni:,.0f} against {end_ni:,.0f} over FY "
            f"{years[-base_ends]}..{years[-1]} — {multiple:,.0f} times as "
            "much")
    if not aligned or base_rev <= 0 or end_rev <= 0:
        return absent(
            "The record does not establish a grower here: " + grew
            + ". Revenue could not be read over the same fiscal years, so "
            "whether the company grew that much or its margin came back "
            "from nothing cannot be told apart — and a compound rate off "
            "that base would answer as though it could")
    base_margin = base_ni / base_rev * 100.0
    end_margin = end_ni / end_rev * 100.0
    if base_margin >= APPEARED_MARGIN * end_margin:
        return None
    return absent(
        "The record does not establish a grower here: " + grew
        + f", while net margin went from {base_margin:,.2f}% to "
          f"{end_margin:,.2f}%. The earnings did not grow, they appeared — "
          "this is a margin recovery or a turnaround, and a compound rate "
          "measures the recovery, which has a ceiling that selling more "
          "does not. Read the base years before treating any of it as a "
          "growth rate")


def _cagr(ctx, input_id, span, gated=False):
    """A compound annual rate between the averages of the three fiscal years
    at each end of a `span`-year gap.

    Averaged rather than endpoint to endpoint, and that is the whole change:
    a single year at either end carries whatever one-off sat in it, and the
    rate then describes the one-off. The case that matters is not the company
    that fails high — a true 7.4% grower whose base year carried a charge
    reads as 20.1%, sits mid-band, and passes, and nothing anywhere catches
    it. Three years at each end is Graham's own construction; it was already
    in this bank at eps_growth_10y and used nowhere else.

    The cost is real and is paid in history: eight fiscal years on one
    accounting basis rather than six. Where they are not there the rate is
    absent, and the reason says so — there is no shorter-window fallback,
    because a measure that quietly becomes a weaker estimator when the data
    thins is the same failure in a different coat.
    """
    n = _growth_window(span)
    w = _window(ctx, input_id, n)
    if is_absent(w):
        return w
    years = [p["end"] for p in w["points"]]
    rate, outs, base, late = _averaged_cagr_from(w["values"], years, span)
    if base <= 0:
        return absent(
            f"Not meaningful here: mean {label(input_id)} over FY "
            f"{years[0]}..{years[GROWTH_ENDS - 1]} is zero or negative "
            f"({base:,.2f}) — no compound rate exists from that base")
    if rate is None:
        # A fractional power of a negative ratio is a complex number in
        # Python — and a nonsense answer in accounting. Positive-to-negative
        # has no compound annual rate; refusing beats a stack trace.
        return absent(
            f"Not meaningful here: mean {label(input_id)} over FY "
            f"{years[-GROWTH_ENDS]}..{years[-1]} is negative "
            f"({late:,.2f}) — no compound annual rate exists from a positive "
            "base to a negative end")
    if gated:
        appeared = _appeared_rather_than_grew(ctx, years)
        if appeared is not None:
            return appeared
    return {"value": rate, "leave_one_out": outs,
            "prov": [f"mean {label(input_id)} of FY {years[0]}.."
                     f"{years[GROWTH_ENDS - 1]} ({base:,.2f}) against FY "
                     f"{years[-GROWTH_ENDS]}..{years[-1]} ({late:,.2f}), "
                     f"{span} years centre to centre, from a basis-checked "
                     "window"],
            "cautions": list(w["cautions"])}


def _cagr_result(ctx, input_id, span, gated=False):
    r = _cagr(ctx, input_id, span, gated=gated)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], r["prov"], r["cautions"],
                    r["leave_one_out"])


def revenue_cagr_5y(ctx):
    # Ungated. Revenue has no margin under it, and revenue growing from a
    # small base is the thing itself rather than an artefact of one — a
    # company selling ten times what it sold is a company selling ten times
    # what it sold, whatever happened to its earnings.
    return _cagr_result(ctx, "revenue", 5)


def revenue_cagr_3y(ctx):
    return _cagr_result(ctx, "revenue", 3)


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
    return _cagr_result(ctx, "net_income", 5, gated=True)


def eps_cagr_5y(ctx):
    # Gated on net income and not on earnings per share, deliberately. What
    # the gate asks is whether the company had earnings at the base of the
    # window; a share count that halved in between moves per-share and says
    # nothing about that. The window is this measure's own fiscal years, so
    # the two are read over exactly the same period.
    return _cagr_result(ctx, "diluted_eps", 5, gated=True)


def eps_growth_10y(ctx):
    w = _window(ctx, "diluted_eps", 10)
    if is_absent(w):
        return _absent_result(w)
    ends = [p["end"] for p in w["points"]]
    early, late, outs = _averaged_ends(w["values"], ends)
    if early <= 0:
        return _absent_result(absent(
            "Not meaningful here: the earlier three-year mean EPS is zero "
            "or negative (the bank's own test)"))
    appeared = _appeared_rather_than_grew(ctx, ends)
    if appeared is not None:
        return _absent_result(appeared)
    return computed((late / early - 1) * 100.0,
                    [f"mean EPS of FY {ends[0]}..{ends[2]} against mean of "
                     f"FY {ends[-3]}..{ends[-1]}"], w["cautions"],
                    [{"dropped": y, "value": (e / b - 1) * 100.0}
                     for y, b, e in outs if b > 0])


def _spread_one_out(a, b):
    """One-out readings of a spread: the same fiscal year dropped from both
    sides.

    Only the years both components offer. Dropping FY2021 from one CAGR and
    FY2019 from the other would produce a difference between two rates
    measured over different histories — a number that answers nothing and
    reads like an answer.
    """
    left = {o["dropped"]: o["value"] for o in (a.get("leave_one_out") or [])}
    right = {o["dropped"]: o["value"] for o in (b.get("leave_one_out") or [])}
    return [{"dropped": y, "value": left[y] - right[y]}
            for y in sorted(set(left) & set(right))]


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
                     "above"], sorted(set(a["cautions"] + b["cautions"])),
                    _spread_one_out(a, b))


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
                     "above"], sorted(set(a["cautions"] + b["cautions"])),
                    _spread_one_out(a, b))


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
    most recent fiscal year, for a condition that reads one input."""
    return _streak_backward_by_year(ctx, input_id,
                                    lambda _year, value: holds(value))


def _streak_backward_by_year(ctx, input_id, holds):
    """The same walk, for a condition that needs to know WHICH year it is
    standing in — so it can go and look at another input for that year.

    `input_id` still sets the calendar: it is the series whose fiscal years
    are walked, whose tiling is checked, and whose restatements break the
    run. A condition reading a second input reads it for the year the walk
    reached, and a year that input does not answer for simply does not hold.
    That keeps one series responsible for the shape of the streak, which is
    what makes a gap in it detectable at all.

    The streak may only be reported if every year it covers — plus the year
    that breaks it — tiles, anchors on the company's actual latest fiscal
    year, and does not span a restatement; otherwise absent says why.
    """
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
        if holds(e, p["value"]):
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


# --------------------------------------------------------------------------
# measures added when quotas became coverage
#
# Six entries, and five of them replace something that was measuring the
# wrong thing rather than adding a sixth question. What they have in common
# is that each takes a LEVEL that was being tested and asks about the
# relationship it sits inside instead: what newly retained capital earns
# rather than what the existing base earns, how far a margin swings against
# how wide it is, what the acquisitions did rather than how many there were.
# --------------------------------------------------------------------------

def total_debt_to_avg_fcf_5y(ctx):
    """Years of typical free cash flow it would take to repay everything.

    The same question `total_debt_to_ebitda` asks, put to a number that is
    not EBITDA. Depreciation is a real expense and a measure that adds it
    back flatters exactly the capital-hungry business that can least afford
    the debt; free cash flow has already paid for the equipment.

    Five years averaged rather than the last twelve months, because one
    heavy investment year would otherwise read as a balance-sheet problem.
    """
    debt = _total_debt_with_leases(ctx)
    if is_absent(debt):
        return _absent_result(debt)
    fcf = _fcf_per_year(ctx, 5)
    if is_absent(fcf):
        return _absent_result(fcf)

    def ratio(values):
        return debt["value"] / (sum(values) / len(values))

    mean_fcf = sum(fcf["values"]) / len(fcf["values"])
    if mean_fcf <= 0:
        return _absent_result(absent(
            "Not meaningful here: average free cash flow over the five years "
            "is zero or negative, so there is no number of years of it that "
            "repays the debt (the bank's own test)"))
    value, outs = _with_one_out(fcf["values"], fcf["years"], ratio,
                                lambda rest: sum(rest) / len(rest) > 0)
    return computed(value,
                    debt["provenance"]
                    + [f"free cash flow for FY {fcf['years'][0]}.."
                       f"{fcf['years'][-1]}, averaged"],
                    sorted(set(debt["cautions"] + fcf["cautions"])), outs)


def incremental_roic_5y(ctx):
    """What the capital retained over the window earned, as opposed to what
    the capital already in the business earns.

    Change in after-tax operating profit divided by change in invested
    capital, both measured between three-year averages at each end of a
    five-year span — the same construction every growth rate in this bank
    uses, and needed here more than anywhere else, because this is a ratio of
    two differences and a one-off year moves both of them at once.

    Eight fiscal years of income statements and eight year-end balance
    sheets, so it is absent for exactly the companies the averaged CAGRs are
    absent for.
    """
    span = 5
    n = _growth_window(span)
    wins = _aligned_windows(ctx, n, "ebit", "income_tax_expense",
                            "pretax_income")
    if is_absent(wins):
        return _absent_result(wins)
    ebit, tax, pretax = wins
    years = [p["end"] for p in ebit["points"]]
    debt = ctx.sb.instant_series_annual("total_debt", n)
    eq = ctx.sb.instant_series_annual("total_equity", n)
    cash = ctx.sb.instant_series_annual("cash_and_equivalents", n)
    for w, what in ((debt, "total debt"), (eq, "total equity"),
                    (cash, "cash")):
        if is_absent(w):
            return _absent_result(absent(
                f"{what} for the {n} year-end balance sheets this needs: "
                + w["reason"]))
        if w["dates"] != years:
            return _absent_result(absent(
                f"{what} balance-sheet dates do not line up with the fiscal "
                "years of EBIT; the window cannot be aligned"))
    nopat, invested = [], []
    for i, y in enumerate(years):
        if pretax["values"][i] <= 0:
            return _absent_result(absent(
                f"pre-tax income for FY ending {y} is zero or negative, so "
                "the effective tax rate that year has no meaning and "
                "after-tax operating profit cannot be worked out for the "
                "window"))
        rate = tax["values"][i] / pretax["values"][i]
        nopat.append(ebit["values"][i] * (1 - rate))
        invested.append(debt["values"][i] + eq["values"][i]
                        - cash["values"][i])

    def rate_of(profit, capital):
        base_p, end_p, _ = _averaged_ends(profit, years)
        base_c, end_c, _ = _averaged_ends(capital, years)
        return (end_p - base_p) / (end_c - base_c) * 100.0

    base_c, end_c, _outs_c = _averaged_ends(invested, years)
    if end_c - base_c <= 0:
        return _absent_result(absent(
            "Not meaningful here: invested capital did not grow across the "
            "window, so no capital was retained for this to be the return "
            "on. A business that grew without keeping any of its profits is "
            "the case this ratio has no way to express, and reporting a "
            "figure divided by nothing or by a negative would read as an "
            "answer"))
    # One-out by hand rather than through `_with_one_out`: the statistic
    # needs both series, dropped at the same year on both sides, and a year
    # in the gap between the two averages is in neither of them.
    outs = []
    for i, y in enumerate(years):
        if not (i < GROWTH_ENDS or i >= len(years) - GROWTH_ENDS):
            continue
        p = nopat[:i] + nopat[i + 1:]
        c = invested[:i] + invested[i + 1:]
        ys = years[:i] + years[i + 1:]
        bc, ec, _ = _averaged_ends(c, ys)
        if ec - bc <= 0:
            continue
        bp, ep, _ = _averaged_ends(p, ys)
        outs.append({"dropped": y, "value": (ep - bp) / (ec - bc) * 100.0})
    return computed(rate_of(nopat, invested),
                    [f"after-tax operating profit and invested capital for "
                     f"FY {years[0]}..{years[-1]}, averaged three years at "
                     f"each end of a {span}-year span"],
                    _cautions_of(ebit, tax, pretax, debt, eq, cash), outs)


def roe_minus_roic_gap_5y(ctx):
    """How far return on equity sits above return on invested capital.

    The gap between them is borrowing. Testing either level on its own says
    how good the business is; testing the distance between them says how
    much of that goodness is the balance sheet — which is the thing the two
    measures were carried side by side to reveal, and which neither level
    states.
    """
    a = ctx.entry("roe_median_5y")
    b = ctx.entry("roic_median_5y")
    for c in (a, b):
        if c["status"] != "computed":
            return _absent_result(absent(
                "one side of the gap is not meaningful ("
                + c.get("reason", "") + "), and the distance between a "
                "number and a meaningless one is meaningless — the bank's "
                "own test"))
    return computed(a["value"] - b["value"],
                    ["return on equity minus return on invested capital, "
                     "both five-year medians computed above"],
                    sorted(set(a["cautions"] + b["cautions"])),
                    _spread_one_out(a, b))


def gross_margin_range_relative_5y(ctx):
    """How far the gross margin swings, as a share of how wide it is.

    A distributor at 12% moving between 9% and 15% and a software company at
    81% moving between 78% and 84% have the same six-point range and are not
    remotely comparably stable. Dividing by the middle reading is what makes
    one number say the same thing to both.
    """
    gm = _gross_margin_annual_pct(ctx, 5)
    if is_absent(gm):
        return _absent_result(gm)

    def relative(values):
        mid = median(values)
        return (max(values) - min(values)) / mid * 100.0

    if median(gm["values"]) <= 0:
        return _absent_result(absent(
            "Not meaningful here: the middle annual gross margin over the "
            "window is zero or negative, so a swing measured against it has "
            "no scale (the bank's own test)"))
    value, outs = _with_one_out(gm["values"], gm["years"], relative,
                                lambda rest: median(rest) > 0)
    return computed(value,
                    [f"annual gross margins for FY {gm['years'][0]}.."
                     f"{gm['years'][-1]}, spread over the middle reading"],
                    gm["cautions"], outs)


def goodwill_impairment_to_equity_5y(ctx):
    """What the acquisitions turned out to be worth, against the owners'
    money that was there before them.

    How much goodwill sits on a balance sheet is a level, and a level
    punishes one good acquisition fifteen years ago. Goodwill written back
    OFF is the acquirer conceding it paid for something that was not there,
    which is the outcome rather than the activity.

    Every year in the window must resolve. A missing impairment caption is
    not read as a nil: a filer reporting one combined goodwill-and-
    intangibles line and nothing else would have no figure here in a year it
    wrote off billions, and a zero would be a large confident number in the
    direction that flatters the company.
    """
    n = 5
    w = _window(ctx, "goodwill_impairment", n)
    if is_absent(w):
        return _absent_result(absent(
            "goodwill impairment for each of the five years: " + w["reason"]
            + ". A year with no impairment caption is left absent rather "
            "than counted as nil"))
    years = [p["end"] for p in w["points"]]
    eq = ctx.sb.instant_series_annual("total_equity", n + 1)
    if is_absent(eq):
        return _absent_result(absent(
            "equity at the balance sheet before the window opened (six "
            "year-end balance sheets in all): " + eq["reason"]))
    if eq["dates"][1:] != years:
        return _absent_result(absent(
            "equity balance-sheet dates do not line up with the fiscal years "
            "of the impairment window; it cannot be aligned"))
    opening = eq["values"][0]
    if opening <= 0:
        return _absent_result(absent(
            f"Not meaningful here: shareholders' equity at {eq['dates'][0]}, "
            "before the window opened, is zero or negative, so there is no "
            "base to measure the write-offs against (the bank's own test)"))

    def share(values):
        return sum(values) / opening * 100.0

    value, outs = _with_one_out(w["values"], years, share)
    return computed(value,
                    [f"goodwill impairment charged in FY {years[0]}.."
                     f"{years[-1]}, added up",
                     f"shareholders' equity at {eq['dates'][0]}, the year "
                     "end before the window"],
                    _cautions_of(w, eq), outs)


def owner_earnings_yield_on_ev(ctx):
    """Owner earnings against what the whole business costs, debts included.

    Two departures from the plainer version, and both push the figure DOWN
    for the companies it was flattering.

    The denominator is enterprise value rather than market capitalization.
    Owner earnings is a figure about the business, and a business bought with
    its debts attached costs what the shares cost plus what it owes — pricing
    a business-level number against the equity alone makes a leveraged
    company look cheap for being leveraged.

    And maintenance capital spending is proxied against depreciation with the
    amortization of intangibles taken out. The proxy works because a business
    replacing its assets spends roughly what it writes them down by; a
    customer list bought in an acquisition is written down over ten years and
    is never replaced by spending at all — it is replaced by another
    acquisition. Leaving it in raises the floor of the proxy, and so
    overstates owner earnings most for the serial acquirers where the
    overstatement matters most.
    """
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
    amort = _ttm(ctx, "intangible_amortisation")
    if is_absent(amort):
        return _absent_result(absent(
            "the amortization of intangible assets could not be resolved on "
            "its own (" + amort["reason"] + "), and it has to come out of "
            "depreciation before the maintenance-capex proxy means "
            "anything. Leaving it in would raise owner earnings rather than "
            "lower them, so it is not a gap this fills in with the whole "
            "figure"))
    ev = ctx.entry("enterprise_value")
    if ev["status"] != "computed":
        return ev
    if ev["value"] <= 0:
        return _absent_result(absent(
            "Not meaningful here: enterprise value is zero or negative — the "
            "company holds more cash than the shares and the debt together "
            "are worth (the bank's own test)"))
    depreciation = dda["value"] - amort["value"]
    if depreciation < 0:
        return _absent_result(absent(
            "the amortization of intangibles resolves larger than total "
            "depreciation and amortization, so the two figures are not on "
            "the same basis and subtracting one from the other would invent "
            "a negative depreciation charge"))
    maint = min(capex["value"], depreciation)
    return computed((cfo["value"] - maint) / ev["value"] * 100.0,
                    [_prov_point(cfo),
                     f"maintenance capex proxied as min(capex, D&A less "
                     f"intangible amortization) = {maint:,.0f}"]
                    + ev["provenance"],
                    sorted(set(_cautions_of(cfo, capex, dda, amort)
                               + ev["cautions"])))


def revenue_ttm(ctx):
    """Sales over the last twelve months.

    Here because a size test has to be on a size. Market capitalization
    measures what the market currently thinks a company is worth, which is
    the thing a value strategy is claiming to disagree with — so a floor
    under it rejects a company for being cheap, which is the opposite of the
    intent.
    """
    return ttm_flow_result(ctx, "revenue")


def consecutive_capital_return_years(ctx):
    """Consecutive fiscal years in which the company returned cash to its
    owners by either route, counting back from the most recent.

    Dividends alone stopped being the whole question in 1982, when SEC Rule
    10b-18 made repurchases a safe and routine alternative. A company that
    has bought back stock every year for fifteen years and never paid a
    dividend has returned capital every one of those years; a dividend
    count reads it as never having done so.

    Buybacks count NET of issuance. A company handing out more stock than it
    buys back is not returning capital, it is mopping up after itself, and
    counting the gross repurchase line would let that read as a capital
    return in the year it is least true.
    """
    buy = ctx.sb.annual_points("buybacks")
    iss = ctx.sb.annual_points("stock_issuance")
    # A year the walk reached where the dividend is nil and the repurchase
    # lines will not resolve. Nothing about that year is known either way, so
    # neither continuing the streak nor stopping it at that year is an
    # answer — both would be this measure asserting something it did not
    # read. Recorded as it happens and turned into an absence below.
    unreadable = []

    def returned(year_end, dividends):
        if dividends > 0:
            return True
        b = buy.get(year_end)
        if not b:
            unreadable.append(year_end)
            return False
        s = iss.get(year_end)
        return b[0]["value"] - (s[0]["value"] if s else 0.0) > 0

    r = _streak_backward_by_year(ctx, "dividends_paid", returned)
    if is_absent(r):
        return _absent_result(r)
    if unreadable:
        return _absent_result(absent(
            f"no dividend was paid in FY ending {unreadable[0]} and the "
            "share repurchase line for that year could not be resolved, so "
            "whether capital was returned that year is unknown. A streak "
            "either side of a year nobody can read is not a streak"))
    return computed(r["value"],
                    ["consecutive fiscal years with dividends paid or net "
                     "shares repurchased, newest backward"],
                    r["cautions"])


def altman_z_double_prime(ctx):
    """Altman's four-variable score, the one built for companies that do not
    manufacture anything.

    The original score was fitted on public manufacturers and carries a sales
    to assets term, which reads an asset-light company as distressed for
    reasons that have nothing to do with distress. Altman published this
    variant to drop that term and rescale the rest, and it is the one he
    intended for service and non-manufacturing businesses — which is most of
    what any screen meets now.

    The other difference matters as much: the fourth term takes the book
    value of equity against total liabilities rather than the market's. The
    score stops moving with the share price, which is what a solvency measure
    inside a valuation rule set should have been doing all along — otherwise
    a stock falling because it is cheap reads as a stock falling because it
    is failing.
    """
    ta = _instant(ctx, "total_assets")
    if is_absent(ta):
        return _absent_result(ta)
    if ta["value"] <= 0:
        return _absent_result(absent("total assets are zero or negative"))
    ca = _instant(ctx, "current_assets")
    cl = _instant(ctx, "current_liabilities")
    re = _instant(ctx, "retained_earnings")
    tl = _instant(ctx, "total_liabilities")
    eq = _instant(ctx, "total_equity")
    for w, what in ((ca, "current assets"), (cl, "current liabilities"),
                    (re, "retained earnings"), (tl, "total liabilities"),
                    (eq, "total equity")):
        if is_absent(w):
            return _absent_result(absent(f"{what}: " + w["reason"]))
    if tl["value"] <= 0:
        return _absent_result(absent(
            "total liabilities are zero or negative, so the equity-to-"
            "liabilities term has no denominator"))
    ebit = _ttm(ctx, "ebit")
    if is_absent(ebit):
        return _absent_result(ebit)
    x1 = (ca["value"] - cl["value"]) / ta["value"]
    x2 = re["value"] / ta["value"]
    x3 = ebit["value"] / ta["value"]
    x4 = eq["value"] / tl["value"]
    return computed(6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4,
                    ["working capital, retained earnings and EBIT against "
                     "total assets, and book equity against total "
                     "liabilities",
                     "Altman's four-variable weights: 6.56, 3.26, 6.72, 1.05"],
                    _cautions_of(ta, ca, cl, re, tl, eq, ebit))


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
    revenue_cagr_5y, revenue_cagr_3y,
    revenue_change_yoy, net_income_cagr_5y, eps_cagr_5y, eps_growth_10y,
    ni_minus_revenue_cagr_spread_5y, eps_minus_revenue_cagr_spread_5y,
    inventory_minus_revenue_growth_yoy, receivables_minus_revenue_growth_yoy,
    profitable_years_10y, consecutive_annual_loss_years,
    consecutive_dividend_years, diluted_share_count_change_5y,
    diluted_share_count_change_3y, diluted_share_count_change_ttm,
    goodwill_intangibles_to_assets, insider_net_buying_6m,
    institutional_ownership_pct,
    total_debt_to_avg_fcf_5y, incremental_roic_5y, roe_minus_roic_gap_5y,
    gross_margin_range_relative_5y, goodwill_impairment_to_equity_5y,
    owner_earnings_yield_on_ev, revenue_ttm,
    consecutive_capital_return_years, altman_z_double_prime,
)}


def compute_all(filings: list[dict], prices_doc: dict | None,
                tickers: list[str], entry_ids=None,
                today: str | None = None) -> dict:
    """Every requested bank entry for one company.

    Returns {entry_id: result}. A crash in one entry becomes that entry's
    absent reason rather than taking the others down — a wrong number is
    the enemy, but so is one bad entry hiding fifty good ones.
    """
    ctx = Ctx(filings, prices_doc, tickers, today=today)
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


# --------------------------------------------------------------------------
# per-filing confirmation readings
# --------------------------------------------------------------------------
# Sell-threshold confirmation counts distinct filing periods in which a
# metric's inputs actually changed. CADENCE states, per entry, which filings
# can change its inputs: "annual" for entries whose filing inputs are annual
# windows only (a 10-Q cannot move a five-year median), "quarterly" for
# entries consuming trailing-twelve-month figures, balance-sheet instants or
# cover data, all of which a quarterly report refreshes. Price is not a
# filing input — a price-bearing entry over annual windows is still "annual".
#
# This is a statement of fact about each formula above, not a judgement about
# any metric's importance; tests/test_confirmation.py verifies each claim
# against which period helpers the formula actually touches.

CADENCE = {
    # annual windows / annual streaks only
    "roic_median_5y": "annual", "roe_median_5y": "annual",
    "gross_margin_range_5y": "annual", "fcf_margin_median_5y": "annual",
    "cash_conversion_median_5y": "annual",
    "effective_tax_rate_median_5y": "annual",
    "payout_to_fcf_median_5y": "annual", "pe_3y_avg_eps": "annual",
    "revenue_cagr_5y": "annual", "revenue_cagr_3y": "annual",
    "net_income_cagr_5y": "annual", "eps_cagr_5y": "annual",
    "eps_growth_10y": "annual",
    "ni_minus_revenue_cagr_spread_5y": "annual",
    "eps_minus_revenue_cagr_spread_5y": "annual",
    "profitable_years_10y": "annual",
    "consecutive_annual_loss_years": "annual",
    "consecutive_dividend_years": "annual",
    "diluted_share_count_change_5y": "annual",
    "diluted_share_count_change_3y": "annual",
    "incremental_roic_5y": "annual",
    "roe_minus_roic_gap_5y": "annual",
    "gross_margin_range_relative_5y": "annual",
    "goodwill_impairment_to_equity_5y": "annual",
    "consecutive_capital_return_years": "annual",
    # anything touching TTM, instants, cover shares or the latest filing
    "total_debt_to_ebitda": "quarterly", "net_debt_to_ebitda": "quarterly",
    "debt_to_equity": "quarterly", "interest_coverage": "quarterly",
    "ltd_to_working_capital": "quarterly", "current_ratio": "quarterly",
    "altman_z_score": "quarterly", "gross_margin_ttm": "quarterly",
    "gross_margin_change_3y": "quarterly",
    "gross_margin_vs_3y_median": "quarterly", "fcf_ttm": "quarterly",
    "fcf_margin_ttm": "quarterly", "fcf_yield_on_ev": "quarterly",
    "accruals_ratio": "quarterly", "operating_income_ttm": "quarterly",
    "market_cap": "quarterly", "enterprise_value": "quarterly",
    "pe_ttm": "quarterly", "price_to_book": "quarterly",
    "price_to_net_tangible_assets": "quarterly",
    "graham_combined_multiple": "quarterly",
    "owner_earnings_yield": "quarterly", "ev_to_ebit": "quarterly",
    "ev_ebit_to_own_5y_median": "quarterly",
    "pe_to_own_5y_median_pe": "quarterly", "peg_trailing": "quarterly",
    "dividend_adjusted_peg": "quarterly", "dividend_yield": "quarterly",
    "ncav_to_market_cap": "quarterly", "net_cash_to_market_cap": "quarterly",
    "revenue_change_yoy": "quarterly",
    "inventory_minus_revenue_growth_yoy": "quarterly",
    "receivables_minus_revenue_growth_yoy": "quarterly",
    "diluted_share_count_change_ttm": "quarterly",
    "goodwill_intangibles_to_assets": "quarterly",
    # The debt is a balance-sheet instant and the enterprise value carries a
    # price, so both refresh on a 10-Q even though the window under each is
    # annual. The noisiest leg names the cadence, the same rule the bank's
    # estimator kinds follow.
    "total_debt_to_avg_fcf_5y": "quarterly",
    "owner_earnings_yield_on_ev": "quarterly",
    "revenue_ttm": "quarterly",
    "altman_z_double_prime": "quarterly",
    # never computed here (separate ingestion paths); cadence is nominal
    "insider_net_buying_6m": "quarterly",
    "institutional_ownership_pct": "quarterly",
}

CONFIRMATION_BOUNDARY_CAP = 12


def confirmation_boundaries(filings: list[dict], cadence: str) -> list[dict]:
    """The filings on which a metric of this cadence gained new inputs,
    oldest first: {"filed", "accession", "form", "period_end"}.

    A filing qualifies only if it advanced the newest-known reporting period
    when it arrived (the frontier rule): an amendment, a re-issue, or a
    delinquent filer's late catch-up of an old period brings no new inputs to
    a metric that reads the newest data, so it creates no boundary. Filings
    sharing a filed date collapse to one boundary — everything filed that day
    is one observation moment, and counting a same-day catch-up batch as
    several would confirm a breach nobody watched persist.
    """
    forms = ANNUAL_FORMS if cadence == "annual" else None
    docs = sorted(filings, key=lambda f: (str(f.get("filed") or ""),
                                          str(f.get("accession") or "")))
    frontier = ""
    picked: dict[str, dict] = {}
    for f in docs:
        form = str(f.get("form") or "")
        period = str(f.get("period_of_report") or "")[:10]
        filed = str(f.get("filed") or "")[:10]
        if not period or not filed:
            continue
        if forms is not None and form not in forms:
            continue
        if period <= frontier:
            continue
        frontier = period
        picked[filed] = {"filed": filed, "accession": f.get("accession"),
                         "form": form, "period_end": period}
    return [picked[d] for d in sorted(picked)]


def confirmation_history(filings: list[dict], prices_doc: dict | None,
                         tickers: list[str], entry_id: str,
                         max_boundaries: int = CONFIRMATION_BOUNDARY_CAP) -> dict:
    """Per-filing readings of one bank entry, newest first, for
    sell-confirmation.

    Each reading recomputes the entry from only the filings filed by that
    boundary's date, with the price pinned to the close on or before it —
    what was observable when that filing arrived. Later restatements and
    re-issues are invisible to earlier readings. Nothing here is persisted;
    the whole history is re-derived from the stores on every call, so it can
    never drift from the filings that justify it.
    """
    cadence = CADENCE.get(entry_id)
    if entry_id not in REGISTRY or cadence is None:
        return {"entry": entry_id, "cadence": cadence, "readings": [],
                "boundaries_held": 0, "truncated": False,
                "note": f"{entry_id} has no computation, so no per-filing "
                        "readings exist"}
    if not filings:
        return {"entry": entry_id, "cadence": cadence, "readings": [],
                "boundaries_held": 0, "truncated": False,
                "note": "no filings are stored for this security — fetch "
                        "data to begin building its filing history"}
    bounds = confirmation_boundaries(filings, cadence)
    if not bounds:
        kind = "annual" if cadence == "annual" else "quarterly or annual"
        return {"entry": entry_id, "cadence": cadence, "readings": [],
                "boundaries_held": 0, "truncated": False,
                "note": f"none of the stored filings delivers a new {kind} "
                        "reporting period, so there is nothing to read"}
    take = bounds[-max_boundaries:] if max_boundaries else bounds
    # A filing without a filed date cannot be placed in time, so it can never
    # be shown to precede a boundary — it belongs to no as-of prefix.
    dated = [f for f in filings if str(f.get("filed") or "")[:10]]
    readings = []
    for b in take:
        prefix = [f for f in dated
                  if str(f.get("filed") or "")[:10] <= b["filed"]]
        priced = None
        try:
            ctx = Ctx(prefix, prices_doc, tickers,
                      today=b["filed"], price_cutoff=b["filed"])
            r = ctx.entry(entry_id)
            priced = max(ctx.price_dates_served) if ctx.price_dates_served \
                else None
        except Exception as e:                          # noqa: BLE001
            r = {"status": "absent",
                 "reason": f"computation failed: {type(e).__name__}: {e}"}
        ok = isinstance(r, dict) and r.get("status") == "computed"
        readings.append({
            "period_end": b["period_end"], "filed": b["filed"],
            "accession": b["accession"], "form": b["form"],
            "value": r.get("value") if ok else None,
            "reason": None if ok else (r or {}).get("reason")
            or "the reading could not be computed",
            "priced": priced,
        })
    readings.reverse()
    return {"entry": entry_id, "cadence": cadence, "readings": readings,
            "boundaries_held": len(bounds),
            "truncated": len(bounds) > len(take), "note": None}
