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

from collections.abc import Mapping
from datetime import date
from statistics import median

from . import bank as bank_mod
from . import concept_map as cm
from . import industry as industry_mod
from . import instruments, price_store
from .periods import ANNUAL_FORMS, SeriesBuilder, absent, is_absent, label

QUARTERS_FOR_OWN_MEDIAN = 20


def _one_symbol(ticker, caller: str) -> str:
    """Refuse a list where an instrument is wanted.

    The same guard dataview puts on the price a *holding* is valued at, on the
    price a *company* measure is valued at, and for the same reason: iterating
    a company's symbols and keeping one close is how a share count came to be
    multiplied by a warrant's price. A string would iterate into characters
    and fail quietly; this is the version that cannot.
    """
    if not isinstance(ticker, str):
        raise TypeError(
            f"{caller} prices one instrument and takes one symbol, not "
            f"{type(ticker).__name__}. A company's warrants, units, listed "
            "notes and preferred series are different instruments at "
            "different prices — handing them over is what let a share count "
            "be valued at one of them.")
    return ticker


# --------------------------------------------------------------------------
# context
# --------------------------------------------------------------------------

class Ctx:
    """One company's computation context: filings, prices, memoised entries.

    `symbols` is an instruments.CompanySymbols — every symbol the SEC maps to
    this filer, with the one that is its *common stock* already picked out by
    the filer's own cover page. It is that type and not a list, because a list
    is what let a whole-company share count be priced at whichever symbol had
    the newest close: a warrant, a listed note, a preferred series. There is
    nothing here to iterate and take a newest from, so the substitution cannot
    come back without first changing this line. See engine/instruments.py.

    `price_cutoff` turns the context into an as-of observation: prices then
    serve the close on or shortly before that day instead of the newest close,
    and `today` should be pinned to the same day so nothing in the context
    runs on two clocks. Used for per-filing confirmation readings — "what was
    observable when this filing arrived" — never for the live view.

    `industry` is what the SEC says this filer is, as engine/industry.history
    reads it off the identity record — the whole append-only history rather
    than one reading of it, so a context pinned to a past day resolves the
    class that was in force then. Nothing here fetches it: a computation is
    told what kind of company this is and reaches for nothing, which is the
    same arrangement every other input arrives under.

    It is required and has no default, which costs every call site a word and
    is the point. A default would mean a context built two years from now by
    somebody who has not read this computes every measure ungated and looks
    exactly like one that was told — the quiet failure this whole arrangement
    exists to end. Where there genuinely is no filer on record, say so with
    `industry.NOT_ESTABLISHED()`.

    A filer nobody has established computes exactly as it did before, and that
    matches how the host already treats a strategy's scope: a published code
    the host cannot act on is evidence, and no code at all is not. A journal
    driven entirely by hand has no code, and refusing its measures on the
    chance that an unnamed company might be a bank would be treating silence
    as an accusation.
    """

    def __init__(self, filings: list[dict], prices_doc: dict | None,
                 symbols, *, industry: dict,
                 today: str | None = None, price_cutoff: str | None = None):
        if not isinstance(symbols, instruments.CompanySymbols):
            raise TypeError(
                "Ctx takes an instruments.CompanySymbols, not "
                f"{type(symbols).__name__}. A bare list of a company's "
                "symbols is what priced a whole-company share count at "
                "whichever one closed most recently — build it with "
                "instruments.company_symbols(filings, tickers) so the common "
                "stock is identified before anything is multiplied by a "
                "price.")
        self.sb = SeriesBuilder(filings)
        self.prices = prices_doc or {"series": {}}
        self.symbols = symbols
        self.tickers = list(symbols.all)
        self.today = today or date.today().isoformat()
        self.price_cutoff = str(price_cutoff)[:10] if price_cutoff else None
        self.industry = industry
        self.price_dates_served: set = set()
        self._industry_node = None
        self._memo: dict = {}

    # -- what kind of company this is ---------------------------------------
    def industry_now(self) -> dict:
        """The filer's class as it stood on this context's own day.

        Read against `price_cutoff` rather than `today`, because those are two
        different questions. Every context carries a `today`; only a *pinned*
        one is a reconstruction, and asking the identity record "what was in
        force on this day" when the day is simply now would answer a filer
        whose observations carry no stamp with "nothing on record says what it
        was then" — a sentence about a reconstruction, printed on the live
        view.
        """
        if self._industry_node is None:
            self._industry_node = industry_mod.at(
                self.industry, self.price_cutoff)["industry"]
        return self._industry_node

    # -- prices -------------------------------------------------------------
    # There is deliberately no "newest close across this company's symbols"
    # here. That function existed, three computations called it, and what it
    # returned was whichever instrument the price source had updated most
    # recently — the common stock on most days and a warrant, a listed note or
    # a preferred series on the days one of those traded later. Every caller
    # now names one symbol, and the only way to get the one that means
    # "this company's shares" is `common_class`, which refuses rather than
    # choosing.

    def common_class(self, shares_total: float):
        """The whole share count as one priced class, or an absence saying why
        this company's shares cannot be located under a single symbol.

        Shaped as a one-entry class list so that a filer stating one total and
        a filer stating a count per class go through exactly the same pricing
        code. What differs between them is where the counts come from, which
        is a fact about the filing; how they are priced is not, and it used to
        be — the per-class path blended on the largest priced class and this
        one took the newest close of anything.
        """
        got = self.symbols.common_or_absent()
        if got.get("absent"):
            return absent(got["reason"]
                          + ", so market capitalization cannot be computed")
        return [{"member": "common stock", "label": "common stock",
                 "value": shares_total, "symbol": got["symbol"]}]

    def price_on(self, ticker, day):
        _one_symbol(ticker, "price_on")
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
        _one_symbol(ticker, "price_for")
        if self.price_cutoff:
            got = price_store.close_on(self.prices, ticker, self.price_cutoff)
        else:
            got = price_store.latest_close(self.prices, ticker)
        if got:
            self.price_dates_served.add(got[0])
        return got

    # -- memoised entry access ----------------------------------------------
    def entry(self, entry_id):
        """One bank entry's answer, applicability settled before arithmetic.

        The order is the whole guarantee. A measure the bank says cannot
        describe this filer never reaches its formula, so there is no branch
        an author has to remember at the top of fifty-nine functions and no
        way to add a sixtieth that quietly skips it. What runs is what the
        declaration allows to run.
        """
        if entry_id not in self._memo:
            stop = self._not_meaningful(entry_id)
            if stop is not None:
                self._memo[entry_id] = stop
            else:
                fn = REGISTRY.get(entry_id)
                self._memo[entry_id] = fn(self) if fn else absent(
                    f"{entry_id} has no computation")
        return self._memo[entry_id]

    def _not_meaningful(self, entry_id):
        """The refusal owed to one entry for this filer, or None.

        Two refusals, and they are not the same fact. A class the measure
        cannot describe is `inapplicable`: knowable in advance, true for as
        long as the company is what it is, and nothing anybody can go and fix.
        A code that was published and cannot be classified is `absent`: the
        SEC has said something that points where this measure does not go, but
        the code may be reassigned and this host may learn to read it, so
        calling it permanent would tell a reader a fixable gap was not.
        """
        rules = _applicability().get(entry_id)
        if not rules:
            return None
        node = self.industry_now()
        if node.get("status") == "known":
            cls = node.get("class")
            for classes, because in rules:
                if cls in classes:
                    return inapplicable(
                        f'{because} The SEC classifies this filer as '
                        f'{node.get("value")}'
                        + (f' — {node["provenance"][0]}.'
                           if node.get("provenance") else "."),
                        industry=cls)
            return None
        if node.get("unclassifiable"):
            nouns = sorted({industry_mod.noun_of(c)
                            for classes, _ in rules for c in classes})
            return _absent_result(absent(
                "this measure does not describe " + _or_list(nouns)
                + ", and what kind of company this filer is cannot be "
                  "settled: " + str(node.get("reason") or "")))
        # No code at all. Silence is not an accusation — see the class
        # docstring.
        return None


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


def inapplicable(reason: str, **extra) -> dict:
    """A measure that cannot describe this filer, whatever its figures say.

    A third status and not a flag on `absent`, for the reason the host already
    keeps `inapplicable` apart from `unknown` one level up: the two look alike
    and behave oppositely. Absent asks for attention — a figure is missing and
    may not be next quarter, and the coverage screen lists it as something to
    go and do. This will never resolve and there is nothing to do, so a screen
    counting it among the gaps would put a permanent item on a to-do list,
    which is how that list stops being read.

    Every reader of a result already asks whether the status is "computed", so
    this can never be mistaken for a value. What it changes is only what a
    reader is told, which is the part a flag could not carry.
    """
    node = {"status": "inapplicable", "reason": reason}
    node.update(extra)
    return node


def _or_list(words: list) -> str:
    """Alternatives in a sentence, separated by commas even at two.

    Commas rather than a bare "and", because the things being listed are
    themselves phrases containing one: "banks and lenders and insurers" reads
    as three things or as one, and the reader has to go back.
    """
    return words[0] if len(words) < 2 else ", ".join(words[:-1]) \
        + ", or " + words[-1]


_APPLICABILITY: dict = {}


def _applicability() -> dict:
    """{entry id: [(classes, because)]} — the bank's declaration, cached.

    Read through `bank`, which is the only reader of that file, and re-read
    whenever it changes: the bank caches on the file's own mtime, so an edit
    to a condition takes effect on the next read exactly as an edit to a
    formula does.
    """
    doc_mtime = bank_mod.bank_path("metric-bank").stat().st_mtime
    if _APPLICABILITY.get("mtime") != doc_mtime:
        _APPLICABILITY.clear()
        _APPLICABILITY["mtime"] = doc_mtime
        _APPLICABILITY["rules"] = bank_mod.applicability()
    return _APPLICABILITY["rules"]


# The one sentence anything in this file may speak in the bank's name, held
# as constants because the check that guards it derives from them rather than
# from a list of the phrasings somebody thought of.
#
# tests/test_applicability.py imports these. That is the point: a refusal
# wearing this sentence without going through the function below is exactly
# what the check looks for, and it can only look for it reliably if the words
# it searches for and the words that get printed are one object. They were
# not, and three refusals wore the sentence — two in `_cagr`, one in
# `incremental_roic_5y` — for a condition no bank entry declared.
NOT_MEANINGFUL = "Not meaningful here: "
CITES_THE_BANK = " (the bank's own test)"

# What the check refuses OUTSIDE that sentence: any attribution to the bank at
# all. The list it replaces held eight particular phrasings and four claims
# walked past it — "the bank's own minimum", "the bank's own caveat", "the
# bank's test" (the list had "the bank's OWN test"), and one flagging an entry
# as its own ingestion path. Each was true and each was a second copy of words
# the bank owns, in a file where the bank cannot correct them. Naming the
# thing rather than its phrasings is the only version of this that holds.
ATTRIBUTES_TO_THE_BANK = "the bank"


def _not_meaningful_absence(entry_id: str, condition: str,
                            detail: str = "") -> dict:
    """The refusal sentence as a raw absence, for the callers that carry one.

    Split from `not_meaningful` below so a helper assembling a series can
    refuse in the bank's words and still hand its caller the absence shape
    that caller already reads — `_quarterly_ratio_series` was writing the
    sentence itself for exactly this reason. One check, one sentence, two
    shapes; the alternative was the second copy that has already happened
    three times in this file.
    """
    declared = _data_conditions().get(entry_id) or []
    if condition not in declared:
        raise ValueError(
            f'{entry_id} refuses on "{condition}", which is not one of the '
            "`data` conditions its metric-bank entry declares "
            + (f"({_or_list(list(declared))})." if declared
               else "— it declares none.")
            + " A refusal a reader cannot look up teaches them the tool is "
              "broken. Declare the condition under `not_meaningful_when`.")
    return absent(NOT_MEANINGFUL + condition + CITES_THE_BANK
                  + (f" — {detail}" if detail else ""))


def not_meaningful(entry_id: str, condition: str, detail: str = "") -> dict:
    """This entry's own declared refusal, in the bank's words.

    The `data` form of an applicability condition is the one the HOST cannot
    evaluate: it is a reading of the figures, so the formula is the only
    thing that can refuse on it. That left the declaration and the
    enforcement in two files with nothing joining them, and the join failed
    in both directions. A condition was declared and the arithmetic never
    performed it — that is what let a payout ratio the bank calls
    uninterpretable be served with a warning beside it, and a cash
    conversion divide through a loss. And a refusal was performed citing
    "the bank's own test" for a test the entry does not declare, so a reader
    following the sentence to the Metrics page found nothing there.

    So a refusal names the condition it is performing, and the sentence a
    reader gets is the bank's own — one copy, in the file where every other
    word about a measure lives. Naming one the entry does not declare raises,
    which is the second direction; tests/test_applicability.py walks this
    file for these calls and checks the first, so a condition nobody
    performs cannot sit in the bank looking enforced.

    `detail` is what this reading was, which the bank cannot know — which
    year, which figures. It never restates the condition.
    """
    return _absent_result(_not_meaningful_absence(entry_id, condition, detail))


_DATA_CONDITIONS: dict = {}


def _data_conditions() -> dict:
    """{entry id: [condition, ...]} — every `data` condition the bank states,
    cached on the file's own mtime exactly as the industry rules are."""
    doc_mtime = bank_mod.bank_path("metric-bank").stat().st_mtime
    if _DATA_CONDITIONS.get("mtime") != doc_mtime:
        _DATA_CONDITIONS.clear()
        _DATA_CONDITIONS["mtime"] = doc_mtime
        _DATA_CONDITIONS["rules"] = bank_mod.data_conditions()
    return _DATA_CONDITIONS["rules"]


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
    if not (rev["value"] > 0):
        return absent(f"revenue for the trailing window is "
                      f"{rev['value']:,.0f}; a gross margin over a revenue "
                      "that is not positive inverts its sign")
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
    if any(not (r > 0) for r in rev["values"]):
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
    stored filing answers.

    The fallback walks every stored filing newest-first, by the same ordering
    `latest_fi` uses. It used to walk `indices[:-1]` reversed, which is a
    different ordering entirely: `indices` is sorted by *filed date* and
    "newest" here means newest *reporting period*, so on any company where
    those disagree — a late-filed amendment of an old quarter, two filings
    posted the same day — the walk dropped a filing that was never tried and
    retried one that had already refused. What it produced was an absent
    market capitalization, and with it an absent enterprise value, P/E and
    every yield, for a company whose share count was sitting in the store.
    """
    fi = ctx.sb.latest_fi()
    if fi is None:
        return absent("no filings are stored, so shares outstanding is unknown")
    shares = cm.resolve_cover_shares(fi)
    if shares is None:
        newest_first = sorted(
            ctx.sb.indices,
            key=lambda i: (i.period_of_report or "", i.filed or "",
                           i.accession or ""), reverse=True)
        for older in newest_first:
            if older is fi:
                continue
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


def blend_classes(ctx, classes: list, counted_on, on: str | None = None):
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

    `counted_on` is the day the share count states, and it is required rather
    than optional because the check below cannot be left to a caller to
    remember. A count and a close are only multipliable while no split sits
    between them: a two-for-one on Tuesday doubles the count and halves the
    close, and a Monday count against a Wednesday close is out by four in the
    direction that makes the company look cheap. The events are stored — that
    is what price_store keeps alongside the raw rows — and nothing here read
    them until now.

    Absent, not cautioned. This figure reaches P/E, price-to-book, the Graham
    multiple and every yield, and three of those close a position: a caution
    is read by a person and ignored by the arithmetic.
    """
    priced, unpriced = [], []
    straddled = []
    for cl in classes:
        sym = cl.get("symbol")
        got = (ctx.price_on(sym, on) if on else ctx.price_for(sym)) \
            if sym else None
        if got and counted_on:
            splits = price_store.splits_between(ctx.prices, sym, counted_on,
                                                got[0])
            if splits:
                straddled.append((sym, splits, got[0]))
        (priced if got else unpriced).append((cl, got))

    if straddled:
        sym, splits, closed = straddled[0]
        when = ", ".join(str(s[0]) for s in splits)
        return absent(
            f"{sym} split on {when}, between the day the share count states "
            f"({counted_on}) and the close being used ({closed}). The count "
            "is on one side of that and the price on the other, so their "
            "product is out by the split factor — market capitalization is "
            "not reported until a filing restates the count")

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


def _counted_on(shares) -> str | None:
    """The day a cover share count speaks for.

    `stated` is the date the cover fact itself claims and is the honest
    answer; `filed` is when the document was published, which is later and is
    the fallback. Where the cover states one date per class and they disagree,
    `resolve_cover_shares` carries no `stated` at all rather than averaging
    them, and the filing date stands in.

    None where neither is on record — and a caller handed None asks for no
    split check, because a check against an unknown date would either refuse
    everything or nothing, and both are worse than saying the date is not
    known. That case is already visible: a count with no date behind it is
    the one thing this function cannot make comparable.
    """
    if not isinstance(shares, dict):
        return None
    return (str(shares.get("stated") or "")[:10]
            or str(shares.get("filed") or "")[:10] or None)


def _classes_to_price(ctx, shares):
    """The share classes a market capitalization has to price, or an absence.

    One function and one answer, where there were two branches. A filer that
    tags its cover count per class hands over the classes with their own
    symbols, each dimension-matched to the count beside it. A filer that tags
    one total hands over one class, and *which symbol denominates it* is the
    question engine/instruments.py answers off the filer's own cover page.

    Both then go through `blend_classes`, which is the point of doing it this
    way: there is one rule for pricing a class list, one rule for what to do
    with a class that has no close of its own, and one place where either can
    be argued with. The second branch never had a rule — it took whichever of
    the company's symbols had closed most recently, which on a company with a
    listed warrant is the warrant on any day the warrant traded later.
    """
    if shares.get("classes"):
        return shares["classes"]
    return ctx.common_class(shares["total"])


def _unidentified_traded(ctx, classes) -> list[str]:
    """Symbols that trade against this filer, are not what we priced, and that
    nothing has identified — as a caution, one sentence.

    Narrowed from "every other symbol with a price", which named a company's
    preferred series back at the reader as though they were a doubt. A
    preferred series the filer registers and the host has read is a fact. What
    is worth saying is the opposite case: something is trading against this
    company, the cover page does not account for it, and if it is another
    class of common then the one count being priced here covers shares this
    price does not describe.
    """
    priced = {str(c.get("symbol") or "").upper() for c in classes}
    live = [t for t in ctx.symbols.unclassified
            if t.upper() not in priced and ctx.price_for(t)]
    if not live:
        return []
    return [f"{', '.join(live)} also trade against this filer and no cover "
            "page says what they are. If any of them is another class of "
            "common stock, the share count priced here covers shares this "
            "price does not describe"]


def _market_cap_result(ctx):
    """Market cap = shares outstanding (cover) × the as-traded price of the
    common stock, per class where the cover states a count per class."""
    shares = _cover_shares(ctx)
    if is_absent(shares):
        if "cover" in shares["reason"]:
            return absent(shares["reason"]
                          + ", so market capitalization cannot be computed")
        return shares

    classes = _classes_to_price(ctx, shares)
    if is_absent(classes):
        return _absent_result(classes)
    blend = blend_classes(ctx, classes, _counted_on(shares))
    if is_absent(blend):
        return _absent_result(blend)

    cautions = list(shares.get("cautions") or [])
    prov = [f"shares outstanding from {shares['source']}, filing "
            f"{shares['accession']}"]
    prov.extend(blend["provenance"])
    cautions.extend(blend["cautions"])
    cautions.extend(_unidentified_traded(ctx, classes))
    # The price's age, stated always and judged never. This used to be a
    # caution that appeared only past seven days, which made the fact
    # conditional on a host opinion: a six-day-old close said nothing about
    # its age and an eight-day-old one did, so a reader could not tell "this
    # is current" from "nobody asked". Seven days is a judgement, it differs
    # between strategies, and it belonged to nobody — the host carries the
    # date, and what is too old is the strategy's call.
    #
    # The OLDEST close in the blend, not the newest. Staleness measured
    # against the freshest class cannot see a second class whose prices
    # stopped updating months ago, which is precisely the one worth knowing
    # about.
    cautions.append(_price_age(ctx, blend["oldest"]))
    cautions.extend(_ended_series(ctx, classes))
    return computed(blend["total"], prov, cautions)


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


def _ended_series(ctx, classes) -> list[str]:
    """A word for every symbol *this figure was priced from* whose series has
    ended. A fact about the instrument, not a judgement about age: a series
    that stopped last week and one that will never trade again look identical
    in a list of closes, and only one of them still has a price.

    Scoped to what was priced rather than to every symbol mapped to the filer.
    A dead warrant series has nothing to do with a market capitalization
    denominated in the common stock, and a caution that fires about instruments
    the figure never touched is one a reader learns to skip past — including on
    the day it is about the instrument that matters.
    """
    out = []
    for t in [c.get("symbol") for c in classes if c.get("symbol")]:
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
    # Revenue is not in the formula; it is what the bank's own test judges
    # the denominator small AGAINST, so it is required for the same reason
    # every other input is. It used to be read and then used only `if not
    # is_absent(rev)`, which turned the declared refusal off for exactly the
    # filers most likely to be missing a revenue total — the concept map says
    # in as many words that some of them tag none. A gate that cannot be
    # evaluated has not been passed.
    rev = _window(ctx, "revenue", 5)
    if is_absent(rev):
        return _absent_result(absent(
            "revenue over the same five fiscal years: " + rev["reason"]
            + " — and whether invested capital is too small to divide by is "
              "measured against revenue, so that test cannot be settled "
              "either way"))
    # Aligned on the period ends like every other window here, and for the
    # same reason: each input resolves its own newest five fiscal years, so
    # two that answer for different years line up by position while
    # describing different periods. Unaligned, the year's invested capital
    # was tested against another year's revenue.
    if [p["end"] for p in rev["points"]] != years:
        return _absent_result(absent(
            "revenue resolves over different fiscal years from EBIT, so the "
            "test of whether invested capital is too small to divide by "
            "would compare one year against another"))
    roics = []
    for i, y in enumerate(years):
        if pretax["values"][i] <= 0:
            return _absent_result(absent(
                f"pre-tax income for FY ending {y} is zero or negative, so "
                "the effective tax rate that year has no meaning and ROIC "
                "cannot be computed for the window"))
        rate = tax["values"][i] / pretax["values"][i]
        invested = debt["values"][i] + eq["values"][i] - cash["values"][i]
        if invested < 0.10 * rev["values"][i]:
            return not_meaningful(
                "roic_median_5y",
                "invested capital (the denominator) is under 10% of revenue",
                f"invested capital at FY ending {y} is {invested:,.0f} "
                f"against revenue of {rev['values'][i]:,.0f}")
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
        # Each END, not their average, and that is what the bank's condition
        # says: "total shareholders' equity is zero or negative". Refusing on
        # the average alone let a year-end that dips negative between two
        # positive ones through — 300, 200, 100, −20, 60, 150 averages
        # positive at every step, so the year bracketed by 100 and −20
        # divides net income by 40 and reports a return four times the truth,
        # on a `higher_is_better` measure, for the company whose equity had
        # just gone negative. That is precisely the case the `because` prose
        # says the refusal exists to stop, and the same sentence in
        # debt_to_equity and price_to_book is enforced as written.
        opening, closing = eq["values"][i], eq["values"][i + 1]
        if opening <= 0 or closing <= 0:
            return not_meaningful(
                "roe_median_5y",
                "total shareholders' equity is zero or negative",
                f"FY ending {y} opens at {opening:,.0f} and closes at "
                f"{closing:,.0f}")
        roes.append(ni["values"][i] / ((opening + closing) / 2.0) * 100.0)
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
        return not_meaningful(
            "debt_to_equity",
            "total shareholders' equity is zero or negative",
            f"equity is {eq['value']:,.0f}")
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
            "often tag none, and this ratio has nothing to divide by without "
            "it: " + interest["reason"]))
    if interest["value"] <= 0:
        return not_meaningful(
            "interest_coverage", "interest expense is zero or negative",
            f"interest expense is {interest['value']:,.0f}")
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
        return not_meaningful(
            "ltd_to_working_capital",
            "working capital (current assets − current liabilities) is zero "
            "or negative",
            f"working capital is {wc:,.0f}")
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
    # No caution about financial companies. There was one, asking the reader
    # to decide whether this filer was a bank — and the host now decides it,
    # from the code the SEC publishes, before this function is entered at all
    # (Ctx.entry, and the industry conditions the bank declares for this
    # entry). A caution that asks for a judgement already made is worse than
    # none: it tells a reader the program could not settle something it did,
    # and it invites them to discount a number that is fine.
    cautions = _cautions_of(ebit, rev, *parts.values()) + mc.get("cautions", [])
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
    """Today's gross margin against the middle of its last three fiscal years.

    The one-out readings are formed even though this measure's estimator does
    not demand them, and that is not the same thing as forming a check nobody
    asked for. A strategy may cite `without: one-year` on any measure, and on
    a measure that IS read over a window of fiscal years the honest answer is
    the reading, not the sentence `_leave_one_out` gives when none was formed
    — "this measure is not read over a window of fiscal years, so there is no
    year to drop out of it", which is false here: it is read over three.

    Which year the drop takes is decided by the comparator, in the host. Only
    the median leg moves; the trailing leg is one reading and no dropped
    fiscal year can perturb it. That is the right target — the near leg is
    the one a dropped year cannot distort.
    """
    now = _gross_margin_ttm_pct(ctx)
    if is_absent(now):
        return _absent_result(now)
    ann = _gross_margin_annual_pct(ctx, 3)
    if is_absent(ann):
        return _absent_result(ann)
    value, outs = _with_one_out(ann["values"], ann["years"],
                                lambda vs: now["value"] - median(vs))
    return computed(value,
                    [f"gross margin TTM against the FY "
                     f"{ann['years'][0]}..{ann['years'][-1]} median"],
                    sorted(set(now["cautions"] + ann["cautions"])), outs)


def fcf_ttm(ctx):
    cfo = _ttm(ctx, "cfo")
    if is_absent(cfo):
        return _absent_result(cfo)
    capex = _ttm(ctx, "capex")
    if is_absent(capex):
        return _absent_result(absent(
            "capital expenditure could not be resolved (" + capex["reason"]
            + ") — free cash flow is not computed with a guessed capex"))
    # There was a branch here cautioning that capex had resolved negative and
    # computing anyway. `cfo - capex` then ADDED the capital spending, so free
    # cash flow came back overstated by twice it — a wrong number with a
    # warning beside it, which is still a wrong verdict once fcf_margin_ttm
    # carries it onto an exit. The concept map declares that line's sign and
    # now enforces it, so a wrong-signed capex never arrives here at all.
    return computed(cfo["value"] - capex["value"],
                    [_prov_point(cfo), _prov_point(capex)],
                    _cautions_of(cfo, capex))


def fcf_margin_ttm(ctx):
    f = ctx.entry("fcf_ttm")
    if f["status"] != "computed":
        return f
    rev = _ttm(ctx, "revenue")
    if is_absent(rev):
        return _absent_result(rev)
    # Positive, not merely non-zero. A contra-revenue restatement year tags
    # `us-gaap:Revenues` negative, and a negative free cash flow over it is a
    # large POSITIVE margin — the maximum-favourable answer to the worst
    # facts, with `higher_is_better` beside it and no caution. Buffett cites
    # this on an exit, so it is a false clear on the rule that sells.
    if not (rev["value"] > 0):
        return _absent_result(absent(
            f"revenue for the trailing window is {rev['value']:,.0f}, which "
            "is not a quantity a share of can be expressed as — a margin "
            "over it inverts, so a loss reads as a high margin"))
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
    bad = [(y, r) for y, r in zip(fcf["years"], rev["values"])
           if not (r > 0)]
    if bad:
        return _absent_result(absent(
            f"revenue for FY ending {bad[0][0]} is {bad[0][1]:,.0f}; a margin "
            "over a revenue that is not positive inverts, so a loss year "
            "would enter the median as a high margin"))
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
        return not_meaningful(
            "fcf_yield_on_ev", "enterprise value is zero or negative",
            f"enterprise value is {ev['value']:,.0f}")
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
        # Negative and not merely zero. A loss inverts the ratio rather than
        # undefining it: a company that lost money and burned cash divides
        # one negative by another and reads as a perfect converter, which is
        # the flattering answer to the facts this measure exists to catch.
        # It used to guard `n == 0` alone.
        if n <= 0:
            return not_meaningful(
                "cash_conversion_median_5y",
                "net income in any year of the window is zero or negative",
                f"net income for FY ending {y} is {n:,.0f}")
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
        # Negative as well as zero, and a refusal rather than the caution
        # that stood here. A payout over negative free cash flow comes back
        # NEGATIVE, so a company borrowing to fund its dividend reads as
        # paying out less than it earns — the flattering answer to the one
        # set of facts this measure exists to catch. The caution said as much
        # and the median was taken regardless, which is the arithmetic
        # ignoring a sentence written for a person.
        if fcf["values"][i] <= 0:
            return not_meaningful(
                "payout_to_fcf_median_5y",
                "free cash flow in any year of the window is zero or "
                "negative",
                f"free cash flow for FY ending {y} is "
                f"{fcf['values'][i]:,.0f}")
        vals.append((div["values"][i] + buy["values"][i] - iss["values"][i])
                    / fcf["values"][i] * 100.0)
    cautions = sorted(set(fcf["cautions"] + _cautions_of(div, buy, iss)))
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
    # No attribution on the end of this. The sentence is true and the bank
    # says it too, under this entry's `misfires`; claiming the bank as its
    # author from here is a second copy of words the bank owns, sitting where
    # the bank cannot correct it. The caution itself stays, because it travels
    # with the value and the misfires prose does not.
    cautions.append("mixes a live price against a balance sheet up to a "
                    "quarter old")
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


def _price_per_common_share(ctx):
    """What one common share costs: market capitalization ÷ the cover share
    count. Absent, with market cap's own reason, where that cannot be reached.

    Derived rather than read off a symbol, and that is not a detour. Earnings
    per share is a whole-company figure divided by every common share there
    is, so the price it is compared against has to be denominated the same
    way; on a company with two classes at two prices, the honest per-share
    price is the average the market actually pays, which is exactly market cap
    over the count. On a single-class company it is that class's close to the
    cent, so nothing changes for almost every filer.

    What it ends is a P/E built on a different instrument from the market cap
    beside it. The two used to be able to disagree — market cap blended across
    classes, P/E took whichever symbol had closed most recently — and "P/E
    against its own five-year median" then compared a figure built one way
    against a history built the other, which is the one comparison that must
    not do that. The history has always been market cap over the count; now
    the current reading is too, and the special case that used to paper over
    the difference for multi-class filers is gone.
    """
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    shares = _cover_shares(ctx)
    if is_absent(shares):
        return _absent_result(shares)
    if not shares["total"]:
        return _absent_result(absent("the cover states no shares outstanding, "
                                     "so there is no per-share price"))
    return computed(mc["value"] / shares["total"],
                    ["market capitalization ÷ shares outstanding"]
                    + mc["provenance"], mc["cautions"])


def pe_ttm(ctx):
    p = _price_per_common_share(ctx)
    if p["status"] != "computed":
        return p
    eps = _eps_ttm(ctx)
    if is_absent(eps):
        return _absent_result(eps)
    if eps["value"] <= 0:
        return not_meaningful(
            "pe_ttm", "diluted earnings per share (TTM) is zero or negative",
            f"diluted EPS is {eps['value']:,.2f}")
    return computed(p["value"] / eps["value"],
                    p["provenance"] + [_prov_point(eps)],
                    sorted(set(p["cautions"] + _cautions_of(eps))))


def pe_3y_avg_eps(ctx):
    p = _price_per_common_share(ctx)
    if p["status"] != "computed":
        return p
    eps = _window(ctx, "diluted_eps", 3)
    if is_absent(eps):
        return _absent_result(eps)
    avg = sum(eps["values"]) / 3.0
    if avg <= 0:
        return not_meaningful(
            "pe_3y_avg_eps",
            "the three-year average diluted EPS is zero or negative",
            f"the average is {avg:,.2f}")
    years = [pt["end"] for pt in eps["points"]]
    return computed(p["value"] / avg,
                    p["provenance"]
                    + [f"diluted EPS FY {years[0]}..{years[-1]}"],
                    sorted(set(p["cautions"] + _cautions_of(eps))))


def price_to_book(ctx):
    mc = ctx.entry("market_cap")
    if mc["status"] != "computed":
        return mc
    eq = _instant(ctx, "total_equity")
    if is_absent(eq):
        return _absent_result(eq)
    if eq["value"] <= 0:
        return not_meaningful(
            "price_to_book",
            "total shareholders' equity is zero or negative",
            f"equity is {eq['value']:,.0f}")
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
        return not_meaningful(
            "price_to_net_tangible_assets",
            "net tangible assets (equity − goodwill − intangibles) is zero "
            "or negative",
            f"net tangible assets are {nta:,.0f}")
    return computed(mc["value"] / nta,
                    mc["provenance"] + [_prov_point(eq), _prov_point(gw),
                                        _prov_point(intang)],
                    sorted(set(mc["cautions"] + _cautions_of(eq, gw, intang))))


def graham_combined_multiple(ctx):
    pe = ctx.entry("pe_3y_avg_eps")
    if pe["status"] != "computed":
        return not_meaningful(
            "graham_combined_multiple", "either component is not meaningful",
            "P/E on three-year average EPS is not available ("
            + pe.get("reason", "") + "), and the product of a meaningless "
            "factor is meaningless")
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
    # The numerator, in the order the formula reads: EV ÷ EBIT. Only the
    # denominator was guarded, so a company holding more cash than its shares
    # and debt are worth together produced a negative multiple that sorted
    # below every real reading on a measure where lower is better — and then
    # ev_ebit_to_own_5y_median divided one negative by another and reported
    # the price going UP as 30% below its own normal.
    if ev["value"] <= 0:
        return not_meaningful(
            "ev_to_ebit", "enterprise value is zero or negative",
            f"enterprise value is {ev['value']:,.0f}")
    ebit = _ttm(ctx, "ebit")
    if is_absent(ebit):
        return _absent_result(ebit)
    if ebit["value"] <= 0:
        return not_meaningful(
            "ev_to_ebit", "EBIT (TTM) is zero or negative",
            f"EBIT is {ebit['value']:,.0f}")
    return computed(ev["value"] / ebit["value"],
                    ev["provenance"] + [_prov_point(ebit)],
                    sorted(set(ev["cautions"] + _cautions_of(ebit))))


def earnings_yield(ctx):
    """Greenblatt's first half: operating profit against what the whole
    business costs, price included and debts included.

    Not `1 / ev_to_ebit`. Same arithmetic, and it is written out rather than
    inverted because the two guards do not invert with it: `ev_to_ebit`
    refuses a non-positive EBIT because a negative multiple sorts below every
    real reading on a measure where lower is better, and that reasoning is
    about the multiple rather than about the yield. Here a negative EBIT
    gives a negative yield, which is the ordinary reading of a company
    losing money at the operating line and sorts exactly where it belongs.
    Only the denominator is refused.
    """
    ev = ctx.entry("enterprise_value")
    if ev["status"] != "computed":
        return ev
    if ev["value"] <= 0:
        return not_meaningful(
            "earnings_yield", "enterprise value is zero or negative",
            f"enterprise value is {ev['value']:,.0f}")
    ebit = _ttm(ctx, "ebit")
    if is_absent(ebit):
        return _absent_result(ebit)
    return computed(100.0 * ebit["value"] / ev["value"],
                    ev["provenance"] + [_prov_point(ebit)],
                    sorted(set(ev["cautions"] + _cautions_of(ebit))))


def return_on_capital(ctx):
    """Greenblatt's second half: operating profit against the capital the
    business actually needs to earn it — working capital plus fixed assets,
    and nothing else.

    The denominator is his and not the ordinary invested-capital one. Debt
    and equity are deliberately not in it: how a business is financed is a
    question about its balance sheet, and this is a question about how good
    the business is. Goodwill is not in it either, for the same reason — what
    a previous owner overpaid tells you nothing about the return the assets
    throw off.

    Non-interest-bearing current liabilities come out because supplier credit
    funds part of the working capital at no cost, and capital somebody else
    is providing for free is not capital tied up. They are reached by
    subtraction — current liabilities less the short-term borrowings inside
    them — because no filer tags the residual directly. Where the borrowings
    inside current liabilities cannot be separated, `short_term_debt` comes
    back absent by its own zero_guard and so does this: a denominator that
    silently kept the borrowings in would overstate capital and understate
    the return by an unknown amount.
    """
    ebit = _ttm(ctx, "ebit")
    if is_absent(ebit):
        return _absent_result(ebit)
    parts = {}
    for iid in ("current_assets", "current_liabilities",
                "cash_and_equivalents", "short_term_debt", "net_ppe"):
        got = _instant(ctx, iid)
        if is_absent(got):
            return _absent_result(got)
        parts[iid] = got
    # Working capital as he defines it, then the fixed assets it works with.
    working = ((parts["current_assets"]["value"]
                - parts["cash_and_equivalents"]["value"])
               - (parts["current_liabilities"]["value"]
                  - parts["short_term_debt"]["value"]))
    capital = working + parts["net_ppe"]["value"]
    if capital <= 0:
        return not_meaningful(
            "return_on_capital", "tangible capital is zero or negative",
            f"working capital and net fixed assets come to {capital:,.0f}")
    return computed(
        100.0 * ebit["value"] / capital,
        [_prov_point(ebit)] + [_prov_point(p) for p in parts.values()],
        _cautions_of(ebit, *parts.values()))


def _quarterly_ratio_series(ctx, kind, entry):
    """20 quarterly observations of EV/EBIT or P/E, each self-consistent on
    its own quarter's original filing, price and cover shares.

    `entry` is `(entry_id, shortfall_condition)` — the bank entry this series
    answers for and the condition it refuses on when the quarters are not
    there. It used to say "the bank's own minimum" in a sentence of its own,
    which was true and was still the defect: the number 20 is a constant in
    this file and the sentence naming the bank as its author was checked by
    nothing. Both entries declare the condition; now both cite it.
    """
    entry_id, shortfall = entry
    fis = ctx.sb.quarterly_observation_fis(QUARTERS_FOR_OWN_MEDIAN)
    if len(fis) < QUARTERS_FOR_OWN_MEDIAN:
        return _not_meaningful_absence(
            entry_id, shortfall,
            f"only {len(fis)} reporting periods are on record")
    values, misses = [], []
    for fi in fis:
        q = fi.period_of_report
        shares = cm.resolve_cover_shares(fi)
        mcap, why = None, "no shares-outstanding cover fact in that filing"
        if shares is not None:
            # The same class list and the same blend as the live figure, by
            # the same anchor rule. Every part of that had to be made true
            # separately: this side used to borrow from the first class that
            # happened to have a price, and — where the cover stated one total
            # — to price it at the first of the company's symbols that had a
            # close near the quarter, which is alphabetical order deciding
            # whether a share count is multiplied by a share or by a warrant.
            # "P/E against its own five-year median" compared numbers built
            # two different ways, which is the one thing that comparison must
            # not do.
            classes = _classes_to_price(ctx, shares)
            if is_absent(classes):
                why = classes["reason"]
            else:
                blend = blend_classes(ctx, classes, _counted_on(shares), on=q)
                if is_absent(blend):
                    why = blend["reason"]
                else:
                    mcap = blend["total"]
        if mcap is None:
            # The quarter's own reason, not one sentence covering three
            # different ones. "No cover fact" is a gap in the filings, "no
            # close near that date" is a gap in the price history, and "which
            # symbol is the common stock is not established" is neither — they
            # point at different things to go and do, and a reader looking at
            # twenty of these needs to see which.
            misses.append(f"{q}: {why}")
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
            # Both ends of the ratio, on the same terms the current period is
            # refused on. A quarter priced at a negative enterprise value is
            # not a cheap quarter, and letting one into the median moves the
            # thing every later reading is measured against.
            ev = mcap + debt["value"] - cash["value"]
            if ev <= 0:
                misses.append(f"{q}: enterprise value not positive")
                continue
            values.append(ev / ebit["value"])
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
        return _not_meaningful_absence(
            entry_id, shortfall,
            f"only {len(values)} of the last {QUARTERS_FOR_OWN_MEDIAN} "
            f"quarters could be assembled "
            f"({sample}{'; …' if len(misses) > 4 else ''})")
    return {"median": median(values), "n": len(values)}


def ev_ebit_to_own_5y_median(ctx):
    cur = ctx.entry("ev_to_ebit")
    if cur["status"] != "computed":
        return not_meaningful(
            "ev_ebit_to_own_5y_median",
            "EV/EBIT is not meaningful in the current period",
            cur.get("reason", "") + ", and a ratio against a median needs a "
            "current value")
    hist = _quarterly_ratio_series(
        ctx, "ev_ebit",
        ("ev_ebit_to_own_5y_median",
         "fewer than 20 trailing quarters of EV/EBIT are available"))
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
        return not_meaningful(
            "pe_to_own_5y_median_pe",
            "P/E (TTM) is not meaningful in the current period",
            cur.get("reason", "") + ", and a ratio against a median needs a "
            "current value")
    # No re-derivation here any more. The current P/E and every historical
    # observation are both market capitalization ÷ shares ÷ EPS, from the same
    # class list priced by the same blend, so the two sides of this comparison
    # are built the same way by construction rather than by a correction
    # applied at the last moment for multi-class filers and forgotten for the
    # single-class filer whose common stock shares a CIK with a warrant.
    hist = _quarterly_ratio_series(
        ctx, "pe",
        ("pe_to_own_5y_median_pe",
         "fewer than 20 trailing quarters of P/E are available"))
    if is_absent(hist):
        return _absent_result(hist)
    if hist["median"] == 0:
        return _absent_result(absent("the five-year median P/E is zero"))
    return computed(cur["value"] / hist["median"],
                    [f"current P/E over the median of {hist['n']} trailing "
                     "quarterly observations, each priced and measured as of "
                     "its own quarter"],
                    cur["cautions"])


def peg_trailing(ctx):
    pe = ctx.entry("pe_ttm")
    if pe["status"] != "computed":
        return _absent_result(absent("P/E (TTM) is not meaningful ("
                                     + pe.get("reason", "") + ")"))
    growth = ctx.entry("eps_cagr_5y")
    if growth["status"] != "computed":
        return not_meaningful(
            "peg_trailing", "the five-year EPS CAGR is not meaningful",
            growth.get("reason", "") + ", and the ratio built on it goes "
            "with it")
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

    Where the earnings behind the window cannot be read over those years, the
    rate is refused rather than served ungated. This is a gate, and a gate
    that cannot be evaluated has not been passed — the same reading the
    revenue half below has always taken. It mattered because the two measures
    that most need it do not read net income themselves: eps_cagr_5y and
    eps_growth_10y run on diluted EPS, so the earnings window is a separate
    input that can thin out or land on different years on its own, and the
    turnaround this exists to catch would then have come back as a compound
    growth rate.
    """
    n = len(years)
    ni = _window(ctx, "net_income", n)
    if is_absent(ni):
        return absent(
            "The record does not establish a grower here: net income over FY "
            f"{years[0]}..{years[-1]} could not be read ({ni['reason']}), so "
            "whether the earnings at the base of this window grew or "
            "appeared cannot be told apart — and a compound rate off that "
            "base would answer as though it could")
    if [p["end"] for p in ni["points"]] != years:
        return absent(
            "The record does not establish a grower here: net income "
            "resolves over different fiscal years from the window whose rate "
            "is in question, so the base years cannot be read — and a "
            "compound rate off a base nobody could check would answer as "
            "though they had been")
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


def _cagr(ctx, entry_id, base_condition, end_condition, input_id, span,
          gated=False):
    """A compound annual rate between the averages of the three fiscal years
    at each end of a `span`-year gap.

    `entry_id` is the bank entry this rate answers for, and the two
    conditions beside it are the ones it refuses on, in the bank's own words.
    They are here because a refusal has to name the entry it is refusing for.
    This helper used to write both of its refusals by hand, in the shape of a
    bank citation, and nothing joined either sentence to a declaration. One of
    them was a condition all four entries did declare; the other was one none
    of them did — a positive base falling to a negative end, which is a profit
    turning into a loss and is not rare. A reader following that sentence to
    the Metrics page found nothing there, which is the exact failure
    `not_meaningful` was written to end.

    The conditions travel as text rather than being derived from the input's
    label because the bank's noun and the concept map's label are not the same
    word — "Net income (loss)" and "Diluted earnings per share" against "net
    income" and "diluted EPS" — and a sentence assembled out of the wrong one
    would be a citation of something the bank does not say. Passing them is
    safe in the way deriving them is not: `not_meaningful` refuses any string
    the entry does not declare, so a typo raises rather than printing — and
    they are passed one per argument rather than bundled, so each stays a
    literal at the entry's own function where tests/test_applicability.py can
    read the pair it is enforcing.

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
        return _not_meaningful_absence(
            entry_id, base_condition,
            f"mean {label(input_id)} over FY {years[0]}.."
            f"{years[GROWTH_ENDS - 1]} is {base:,.2f}, and no compound rate "
            "exists from that base")
    if rate is None:
        # A fractional power of a negative ratio is a complex number in
        # Python — and a nonsense answer in accounting. Positive-to-negative
        # has no compound annual rate; refusing beats a stack trace.
        return _not_meaningful_absence(
            entry_id, end_condition,
            f"mean {label(input_id)} over FY {years[-GROWTH_ENDS]}.."
            f"{years[-1]} is {late:,.2f}, against {base:,.2f} over FY "
            f"{years[0]}..{years[GROWTH_ENDS - 1]}")
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


def _cagr_result(ctx, entry_id, base_condition, end_condition, input_id,
                 span, gated=False):
    r = _cagr(ctx, entry_id, base_condition, end_condition, input_id, span,
              gated=gated)
    if is_absent(r):
        return _absent_result(r)
    return computed(r["value"], r["prov"], r["cautions"],
                    r["leave_one_out"])


def revenue_cagr_5y(ctx):
    # Ungated. Revenue has no margin under it, and revenue growing from a
    # small base is the thing itself rather than an artefact of one — a
    # company selling ten times what it sold is a company selling ten times
    # what it sold, whatever happened to its earnings.
    return _cagr_result(
        ctx, "revenue_cagr_5y",
        "mean revenue over the three base years is zero or negative",
        "mean revenue over the three end years is negative", "revenue", 5)


def revenue_cagr_3y(ctx):
    return _cagr_result(
        ctx, "revenue_cagr_3y",
        "mean revenue over the three base years is zero or negative",
        "mean revenue over the three end years is negative", "revenue", 3)


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
        ends = [p["end"] for p in w["points"]]
        # Positive, not merely non-zero, and the same guard `fcf_margin_ttm`
        # already makes for the same reason: a contra-revenue restatement
        # tags `us-gaap:Revenues` negative, and dividing one negative total
        # by another turns a further collapse into a large POSITIVE rate.
        # This entry is `higher_is_better` and Lynch reads it as the half of
        # its growth exit that can hold the exit OFF, so the flattering
        # direction of that flip suppresses a sale the record justifies.
        if w["values"][0] <= 0:
            return not_meaningful(
                "revenue_change_yoy",
                "revenue over the earlier of the two windows is zero or "
                "negative",
                f"FY {ends[0]} is {w['values'][0]:,.0f}")
        return computed((w["values"][1] / w["values"][0] - 1) * 100.0,
                        [f"FY {ends[1]} against FY {ends[0]}, both from a "
                         "basis-checked window"], w["cautions"])
    now = _ttm(ctx, "revenue")
    if is_absent(now):
        return _absent_result(now)
    prior = _prior_year_ttm(ctx, "revenue")
    if is_absent(prior):
        return _absent_result(prior)
    if prior["value"] <= 0:
        return not_meaningful(
            "revenue_change_yoy",
            "revenue over the earlier of the two windows is zero or negative",
            f"the trailing window to {prior.get('end')} is "
            f"{prior['value']:,.0f}")
    # The two trailing windows come from different filing vintages; apply the
    # same basis discipline annual windows get.
    fams = _families_of(now) | _families_of(prior)
    if len(fams) > 1:
        return not_meaningful(
            "revenue_change_yoy",
            "the two windows resolve revenue under different tag families, or "
            "a fiscal year inside them was restated after the earlier "
            "window's filings were prepared",
            f"they resolve under {' and '.join(sorted(fams))} — the ASC 606 "
            "transition changed what the number measures")
    prior_filed = min((r.get("filed") or "")
                      for r in (prior.get("legs") or [prior]))
    for ev in ctx.sb._restatement_events(ctx.sb.annual_points("revenue")):
        if ev["restating_filed"] > prior_filed:
            return not_meaningful(
                "revenue_change_yoy",
                "the two windows resolve revenue under different tag "
                "families, or a fiscal year inside them was restated after "
                "the earlier window's filings were prepared",
                f"FY ending {ev['year_end']} was restated by filing "
                f"{ev['restating_accession']}")
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


def eps_change_yoy(ctx):
    """Diluted EPS over the last twelve months against the twelve before it.

    The same construction as `revenue_change_yoy`, on the same two branches
    and for the same reasons, applied to the per-share figure.

    It exists because entry and exit want opposite things from a growth
    number. An entry test wants durability, which argues for a long window;
    an exit wants timeliness, which argues for a short one. Every growth
    exit in this bank before this one was a level on the same multi-year
    rate the entry bought on — and a rate whose ends are three-year means
    cannot fall below an exit level until the bad years have worked their
    way into a mean, which is years after the business changed. This is the
    current rate, and a company that has stopped growing says so here two
    quarters after it stops.

    Per share rather than in total, and that is a real limitation to know:
    a company retiring stock fast enough shows growth here that the business
    did not produce. The guard is that nothing exits on this figure alone —
    see the growth exit in strategies/lynch, where revenue over the same two
    windows has to agree before the exit fires.
    """
    latest = ctx.sb.latest_fi()
    if latest is not None and latest.form in (
            "10-K", "10-K/A", "10-KT", "10-KT/A"):
        # Latest report is annual: both trailing windows are fiscal years, so
        # the basis-checked annual window supplies them with every guard
        # (restatement vintages, families, tiling) already applied.
        w = _window(ctx, "diluted_eps", 2)
        if is_absent(w):
            return _absent_result(w)
        ends = [p["end"] for p in w["points"]]
        if w["values"][0] <= 0:
            return not_meaningful(
                "eps_change_yoy",
                "diluted EPS over the earlier of the two windows is zero or "
                "negative",
                f"FY {ends[0]} is {w['values'][0]:,.2f}")
        return computed((w["values"][1] / w["values"][0] - 1) * 100.0,
                        [f"FY {ends[1]} against FY {ends[0]}, both from a "
                         "basis-checked window"], w["cautions"])
    now = _ttm(ctx, "diluted_eps")
    if is_absent(now):
        return _absent_result(now)
    prior = _prior_year_ttm(ctx, "diluted_eps")
    if is_absent(prior):
        return _absent_result(prior)
    if prior["value"] <= 0:
        return not_meaningful(
            "eps_change_yoy",
            "diluted EPS over the earlier of the two windows is zero or "
            "negative",
            f"the trailing window to {prior.get('end')} is "
            f"{prior['value']:,.2f}")
    # The two trailing windows come from different filing vintages; apply the
    # same basis discipline annual windows get.
    fams = _families_of(now) | _families_of(prior)
    if len(fams) > 1:
        return not_meaningful(
            "eps_change_yoy",
            "the two windows resolve diluted EPS under different tag "
            "families, or a fiscal year inside them was restated after the "
            "earlier window's filings were prepared",
            f"they resolve under {' and '.join(sorted(fams))}")
    prior_filed = min((r.get("filed") or "")
                      for r in (prior.get("legs") or [prior]))
    for ev in ctx.sb._restatement_events(ctx.sb.annual_points("diluted_eps")):
        if ev["restating_filed"] > prior_filed:
            return not_meaningful(
                "eps_change_yoy",
                "the two windows resolve diluted EPS under different tag "
                "families, or a fiscal year inside them was restated after "
                "the earlier window's filings were prepared",
                f"FY ending {ev['year_end']} was restated by filing "
                f"{ev['restating_accession']}")
    return computed((now["value"] / prior["value"] - 1) * 100.0,
                    [f"TTM to {now.get('end')} against TTM to "
                     f"{prior.get('end')}"],
                    _cautions_of(now, prior))


# --------------------------------------------------------------------------
# what the earnings at the base of a growth window looked like
#
# Two published readings of the same two quantities `_appeared_rather_than_
# grew` refuses a compound rate on. The gate above and the pair below are not
# two statements of one rule and must not be read as one: the gate is the
# host declining to serve a number it cannot stand behind, and these are the
# figures themselves, served so that a strategy can hold its own opinion
# about what they mean and a reader can see the arithmetic that produced it.
#
# The distinction matters because the answer is a category rather than a
# fault. A company whose earnings multiplied off almost nothing while its
# margin came back from almost nothing did not grow at a rate — it recovered,
# and recovery has a ceiling that selling more does not. Naming that is more
# useful to a reader than an absent growth rate, and it points at the right
# question. What it is not is a fact about whether the company is good.
#
# Both are read over the eight fiscal years of net income the five-year
# growth rates use, with means at each end, so a single distorted year at
# either end moves them by a third of its distortion rather than by all of
# it.
# --------------------------------------------------------------------------

def _base_and_end(ctx, input_id, ends=GROWTH_ENDS):
    """The two three-year means at the ends of the five-year growth window,
    with the same pair recomputed for each single year dropped out of them,
    or an absence.

    `outs` is {fiscal year: (base mean, end mean)} — the same one-out
    arithmetic every averaged rate in this file uses, so a robustness reading
    of these cannot disagree with one of a growth rate over the same window.
    """
    n = _growth_window(5, ends)
    w = _window(ctx, input_id, n)
    if is_absent(w):
        return w
    years = [p["end"] for p in w["points"]]
    base, end, outs = _averaged_ends(w["values"], years, ends)
    return {"base": base, "end": end, "years": years,
            "outs": {y: (b, e) for y, b, e in outs},
            "cautions": list(w["cautions"])}


def earnings_base_share_5y(ctx):
    """What the company earned at the base of the growth window, as a share
    of what it earns at the end of it.

    Under a tenth is the multiple half of what the growth gate refuses a
    compound rate on, and on its own it is not a fault: a company whose
    revenue multiplied about as fast as its earnings grew, and this reads
    low for it. What it is on its own is a fact a strategy can hold an
    opinion about, published so that one can.
    """
    ni = _base_and_end(ctx, "net_income")
    if is_absent(ni):
        return _absent_result(ni)
    years = ni["years"]
    if ni["end"] <= 0:
        return not_meaningful(
            "earnings_base_share_5y",
            "mean net income over the three most recent fiscal years is zero "
            "or negative",
            f"FY {years[-GROWTH_ENDS]}..{years[-1]} means {ni['end']:,.0f}")
    # A dropped year that empties the denominator is not offered. A negative
    # end mean turns a share into a negative number, which on a
    # higher-is-better measure reads as the base being tiny — the flattering
    # answer arriving through the door marked robustness.
    outs = [{"dropped": y, "value": b / e * 100.0}
            for y, (b, e) in ni["outs"].items() if e > 0]
    return computed(ni["base"] / ni["end"] * 100.0,
                    [f"mean net income of FY {years[0]}.."
                     f"{years[GROWTH_ENDS - 1]} ({ni['base']:,.0f}) against "
                     f"FY {years[-GROWTH_ENDS]}..{years[-1]} "
                     f"({ni['end']:,.0f})"],
                    ni["cautions"], outs)


def net_margin_base_share_5y(ctx):
    """The margin the company earned at the base of the growth window, as a
    share of the margin it earns at the end of it.

    The other half of the same gate, and the scale-free one: it is a ratio of
    two ratios, so it says the same thing to a company selling ten dollars
    and one selling ten billion, and a split changes nothing about it.
    """
    ni = _base_and_end(ctx, "net_income")
    if is_absent(ni):
        return _absent_result(ni)
    rev = _base_and_end(ctx, "revenue")
    if is_absent(rev):
        return _absent_result(rev)
    if rev["years"] != ni["years"]:
        return not_meaningful(
            "net_margin_base_share_5y",
            "revenue and net income resolve over different fiscal years",
            f"net income over {ni['years'][0]}..{ni['years'][-1]} against "
            f"revenue over {rev['years'][0]}..{rev['years'][-1]}")

    def share(base_ni, end_ni, base_rev, end_rev):
        if base_rev <= 0 or end_rev <= 0:
            return None
        end_margin = end_ni / end_rev
        if end_margin <= 0:
            return None
        return (base_ni / base_rev) / end_margin * 100.0

    value = share(ni["base"], ni["end"], rev["base"], rev["end"])
    if value is None:
        return not_meaningful(
            "net_margin_base_share_5y",
            "mean revenue at either end of the window is zero or negative, "
            "or the margin over the three most recent fiscal years is zero "
            "or negative",
            f"mean revenue {rev['base']:,.0f} then and {rev['end']:,.0f} "
            f"now, mean net income {ni['end']:,.0f} now")
    outs = []
    for y, (base_ni, end_ni) in ni["outs"].items():
        if y not in rev["outs"]:
            continue
        base_rev, end_rev = rev["outs"][y]
        one = share(base_ni, end_ni, base_rev, end_rev)
        if one is not None:
            outs.append({"dropped": y, "value": one})
    years = ni["years"]
    return computed(value,
                    [f"net margin of FY {years[0]}..{years[GROWTH_ENDS - 1]} "
                     f"({ni['base'] / rev['base'] * 100:,.2f}%) against FY "
                     f"{years[-GROWTH_ENDS]}..{years[-1]} "
                     f"({ni['end'] / rev['end'] * 100:,.2f}%)"],
                    sorted(set(ni["cautions"] + rev["cautions"])), outs)


def net_income_cagr_5y(ctx):
    return _cagr_result(
        ctx, "net_income_cagr_5y",
        "mean net income over the three base years is zero or negative",
        "mean net income over the three end years is negative",
        "net_income", 5, gated=True)


def eps_cagr_5y(ctx):
    # Gated on net income and not on earnings per share, deliberately. What
    # the gate asks is whether the company had earnings at the base of the
    # window; a share count that halved in between moves per-share and says
    # nothing about that. The window is this measure's own fiscal years, so
    # the two are read over exactly the same period.
    return _cagr_result(
        ctx, "eps_cagr_5y",
        "mean diluted EPS over the three base years is zero or negative",
        "mean diluted EPS over the three end years is negative",
        "diluted_eps", 5, gated=True)


def eps_growth_10y(ctx):
    w = _window(ctx, "diluted_eps", 10)
    if is_absent(w):
        return _absent_result(w)
    ends = [p["end"] for p in w["points"]]
    early, late, outs = _averaged_ends(w["values"], ends)
    if early <= 0:
        return not_meaningful(
            "eps_growth_10y",
            "the earlier three-year mean EPS is zero or negative",
            f"the earlier mean is {early:,.2f}")
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
            return not_meaningful(
                "ni_minus_revenue_cagr_spread_5y",
                "either component CAGR is not meaningful",
                c.get("reason", "") + ", and the difference of a meaningless "
                "number is meaningless")
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
    # `is_absent`, not `is None`. Neither helper has ever returned None — both
    # come back with a resolved reading or with `absent(reason)` (see
    # periods.SeriesBuilder._ytd_resolution and _matching_prior_ytd, and the
    # is_absent guards every other caller of them already makes). So the two
    # checks below never fired, and a filing carrying no prior-year revenue
    # comparative reached the arithmetic as a dict with no `value` key: both
    # balance-growth spreads came back "computation failed: KeyError: 'value'"
    # where the honest answer was the reason the helper had already written.
    cur = ctx.sb._ytd_resolution(fi, "revenue", end)
    if is_absent(cur):
        return absent("revenue did not resolve in the filing: "
                      + cur["reason"])
    prior = ctx.sb._matching_prior_ytd(fi, "revenue", cur)
    if is_absent(prior):
        return absent("the filing carries no prior-year revenue comparative: "
                      + prior["reason"])
    if prior["value"] == 0:
        return absent("prior-period revenue is zero")
    return {"value": (cur["value"] / prior["value"] - 1) * 100.0,
            "cur": cur, "prior": prior,
            "cautions": _cautions_of(cur, prior)}


def _balance_growth_spread(ctx, entry_id, input_id, condition):
    fi = ctx.sb.latest_balance_fi()
    if fi is None:
        return _absent_result(absent("no stored filing carries a balance sheet"))
    pair = ctx.sb.instant_pair_yoy(input_id)
    if is_absent(pair):
        if "did not resolve" in pair["reason"]:
            return not_meaningful(entry_id, condition, pair["reason"])
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
        ctx, "inventory_minus_revenue_growth_yoy", "inventory_net",
        "the company reports no inventory")


def receivables_minus_revenue_growth_yoy(ctx):
    return _balance_growth_spread(
        ctx, "receivables_minus_revenue_growth_yoy",
        "accounts_receivable_net",
        "the company reports no accounts receivable")


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
        "source this pipeline does not read yet"))


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
        return not_meaningful(
            "total_debt_to_avg_fcf_5y",
            "average free cash flow over the five years is zero or negative",
            f"the average is {mean_fcf:,.0f}, so there is no number of "
            "years of it that repays the debt")
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
        return not_meaningful(
            "incremental_roic_5y",
            "invested capital did not grow across the window",
            f"mean invested capital over FY {years[-GROWTH_ENDS]}.."
            f"{years[-1]} is {end_c:,.0f} against {base_c:,.0f} over FY "
            f"{years[0]}..{years[GROWTH_ENDS - 1]}, so no capital was "
            "retained for this to be the return on")
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
            return not_meaningful(
                "roe_minus_roic_gap_5y",
                "either side is not meaningful for this company",
                c.get("reason", "") + ", and the distance between a number "
                "and a meaningless one is meaningless")
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
        return not_meaningful(
            "gross_margin_range_relative_5y",
            "the middle annual gross margin is zero or negative",
            f"the middle margin is {median(gm['values']):,.1f}%, so a "
            "swing measured against it has no scale")
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
        return not_meaningful(
            "goodwill_impairment_to_equity_5y",
            "shareholders' equity before the window is zero or negative",
            f"equity at {eq['dates'][0]} is {eq['values'][0]:,.0f}, so there "
            "is no base to measure the write-offs against")

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
        return not_meaningful(
            "owner_earnings_yield_on_ev",
            "enterprise value is zero or negative",
            "the company holds more cash than the shares and the debt "
            "together are worth")
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
        return not_meaningful(
            "altman_z_double_prime",
            "total liabilities are zero or negative",
            f"total liabilities are {tl['value']:,.0f}, so the "
            "equity-to-liabilities term has no denominator")
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
    earnings_yield, return_on_capital,
    pe_to_own_5y_median_pe, peg_trailing, dividend_adjusted_peg,
    dividend_yield, ncav_to_market_cap, net_cash_to_market_cap,
    revenue_cagr_5y, revenue_cagr_3y,
    revenue_change_yoy, eps_change_yoy,
    earnings_base_share_5y, net_margin_base_share_5y,
    net_income_cagr_5y, eps_cagr_5y, eps_growth_10y,
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
                symbols, *, industry: dict, entry_ids=None,
                today: str | None = None) -> dict:
    """Every requested bank entry for one company.

    Returns {entry_id: result}. A crash in one entry becomes that entry's
    absent reason rather than taking the others down — a wrong number is
    the enemy, but so is one bad entry hiding fifty good ones.
    """
    ctx = Ctx(filings, prices_doc, symbols, today=today, industry=industry)
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
# A third value, "daily", is not written below and cannot be: it is DERIVED,
# from the estimator kind the bank declares, by `cadence_of`. An entry read
# by a quoted price gains a new reading every session rather than every
# filing, and the clock follows from that fact rather than restating it. See
# contract.CLOCKS.
#
# This is a statement of fact about each formula above, not a judgement about
# any metric's importance; tests/test_filing_series.py TestCadence verifies
# each claim against which period helpers the formula actually touches, and
# tests/test_estimators.py verifies the derived arm against which formulas
# actually reach a price.

_FILING_CADENCE = {
    # annual windows / annual streaks only
    "roic_median_5y": "annual", "roe_median_5y": "annual",
    "gross_margin_range_5y": "annual", "fcf_margin_median_5y": "annual",
    "cash_conversion_median_5y": "annual",
    "effective_tax_rate_median_5y": "annual",
    "payout_to_fcf_median_5y": "annual",
    "revenue_cagr_5y": "annual", "revenue_cagr_3y": "annual",
    "net_income_cagr_5y": "annual", "eps_cagr_5y": "annual",
    "eps_growth_10y": "annual",
    "ni_minus_revenue_cagr_spread_5y": "annual",
    "eps_minus_revenue_cagr_spread_5y": "annual",
    "earnings_base_share_5y": "annual",
    "net_margin_base_share_5y": "annual",
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
    "pe_ttm": "quarterly",
    # Annual EPS on top, and a cover share count underneath: the per-share
    # price both P/E entries divide by is market capitalization over the
    # count, and a 10-Q restates that count. Declared annual while the price
    # came straight off a symbol, which stopped being true when the symbol
    # stopped being chosen from a list.
    "pe_3y_avg_eps": "quarterly",
    "price_to_book": "quarterly",
    "price_to_net_tangible_assets": "quarterly",
    "graham_combined_multiple": "quarterly",
    "owner_earnings_yield": "quarterly", "ev_to_ebit": "quarterly",
    "earnings_yield": "quarterly", "return_on_capital": "quarterly",
    "ev_ebit_to_own_5y_median": "quarterly",
    "pe_to_own_5y_median_pe": "quarterly", "peg_trailing": "quarterly",
    "dividend_adjusted_peg": "quarterly", "dividend_yield": "quarterly",
    "ncav_to_market_cap": "quarterly", "net_cash_to_market_cap": "quarterly",
    "revenue_change_yoy": "quarterly", "eps_change_yoy": "quarterly",
    "inventory_minus_revenue_growth_yoy": "quarterly",
    "receivables_minus_revenue_growth_yoy": "quarterly",
    "diluted_share_count_change_ttm": "quarterly",
    "goodwill_intangibles_to_assets": "quarterly",
    # A balance-sheet instant over a five-year window: the debt refreshes on
    # a 10-Q even though the window under it is annual. The noisiest leg
    # names the cadence, the same rule the bank's estimator kinds follow.
    # (This entry reads no price — the comment here used to say it carried an
    # enterprise value, which is true of its neighbour below and not of it.)
    "total_debt_to_avg_fcf_5y": "quarterly",
    "owner_earnings_yield_on_ev": "quarterly",
    "revenue_ttm": "quarterly",
    "altman_z_double_prime": "quarterly",
    # never computed here (separate ingestion paths); cadence is nominal
    "insider_net_buying_6m": "quarterly",
    "institutional_ownership_pct": "quarterly",
}

DAILY = "daily"

# --------------------------------------------------------------------------
# which formulas read a price — derived from this file, not declared about it
# --------------------------------------------------------------------------
# The bank says how each measure is read, and for twenty entries the answer
# turns on one fact: does the arithmetic consult a quoted price? That decides
# the clock a breach of them is confirmed on, and it is not a thing an author
# should be trusted to remember about the fifty-ninth measure.
#
# So it is read off the formulas. Every price in this file arrives through
# `Ctx.price_for` or `Ctx.price_on` — both say so, and `_one_symbol` refuses
# anything reaching around them — so a static walk of the call graph from an
# entry's own function, following local calls and `ctx.entry("...")` into
# other entries, settles it exactly. There is no fixture to be too thin and
# no guard to refuse before the price is reached, which is what rules out
# doing this by running the formulas: a price-bearing entry that goes absent
# on a missing input looks price-free, and the derivation would then agree
# with a wrong declaration.
#
# What it cannot see is a price reached by a name this file does not contain.
# That is what `_PRICE_DOORS` is: the doors are named here, and
# tests/test_estimators.py checks the list against the methods Ctx actually
# offers, so a third door cannot be added without this being told.

_PRICE_DOORS = ("price_for", "price_on")

_price_driven: dict = {}


def _entry_calls(node):
    """Every name one function calls, plus `ctx.entry("x")` as "@x"."""
    import ast
    out = set()
    for c in ast.walk(node):
        if not isinstance(c, ast.Call):
            continue
        name = getattr(c.func, "id", None) or getattr(c.func, "attr", None)
        if not name:
            continue
        out.add(name)
        if name == "entry" and c.args:
            try:
                lit = ast.literal_eval(c.args[0])
            except Exception:                             # noqa: BLE001
                lit = None
            if isinstance(lit, str):
                out.add("@" + lit)
    return out


def price_driven_entries() -> frozenset:
    """Every REGISTRY entry whose arithmetic reaches a quoted price."""
    import ast
    import pathlib
    if _price_driven:
        return _price_driven["ids"]
    tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
    funcs = {n.name: n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef)}
    edges = {n: _entry_calls(f) for n, f in funcs.items()}

    def reaches(name, seen):
        if name in seen:
            return False
        seen.add(name)
        for callee in edges.get(name, ()):
            tgt = callee[1:] if callee.startswith("@") else callee
            if tgt in _PRICE_DOORS:
                return True
            if tgt in funcs and reaches(tgt, seen):
                return True
        return False

    _price_driven["ids"] = frozenset(
        eid for eid in REGISTRY if eid in funcs and reaches(eid, set()))
    return _price_driven["ids"]


def cadence_of(entry_id: str):
    """Which clock one entry's confirmation series runs on, or None.

    Derived where it can be. An entry the bank declares `quoted` is read from
    a price, so its readings are sessions and not filings — and that is the
    bank's declaration, not a second table here that would have to be kept in
    step with it. Everything else falls through to the filing cadence stated
    above, which is a claim about which FILINGS refresh a formula's inputs
    and remains exactly that.

    Falls back to the stated filing cadence where the bank cannot be read at
    all, because a render must not depend on the bank being well formed —
    same rule as contract._plain_estimator.
    """
    try:
        from .contract import ESTIMATORS, estimator_of
        est = estimator_of(entry_id)
        if est and ESTIMATORS[est["kind"]]["clock"] == "sessions":
            return DAILY
    except Exception:                                     # noqa: BLE001
        pass
    return _FILING_CADENCE.get(entry_id)


class _Cadence(Mapping):
    """`CADENCE` as it always read — {entry id: clock word} — with the
    derived arm folded in.

    Resolved on access rather than built once at import. The bank is cached
    on its file's mtime precisely so an edit takes effect without a restart,
    and a dict built at import would answer from whatever the bank said the
    first time anything imported this module. It would also have to import
    contract at module scope, which imports bank, which reads this one.
    """

    def __getitem__(self, key):
        if key not in _FILING_CADENCE:
            raise KeyError(key)
        return cadence_of(key)

    def __iter__(self):
        return iter(_FILING_CADENCE)

    def __len__(self):
        return len(_FILING_CADENCE)


CADENCE = _Cadence()

# Every clock an entry can be on. engine/context._series_for walks these and
# builds one pinned context per boundary within each.
CADENCES = ("annual", "quarterly", DAILY)

CONFIRMATION_BOUNDARY_CAP = 12


def trading_boundaries(prices_doc, symbols, today: str,
                       limit: int = CONFIRMATION_BOUNDARY_CAP) -> list[dict]:
    """The sessions on which a price-bearing metric gained a new reading,
    oldest first: {"filed", "accession", "form", "period_end"}.

    The sibling of `confirmation_boundaries`, in the same shape and for the
    same reason: everything downstream counts readings and must not care
    which series produced them.

    A boundary is a day the series actually holds a close for — never a
    calendar day. `price_store.close_on` reaches backward to the nearest
    earlier trading day, so a boundary on a day with no row would serve the
    close from the day before and the run would count one observation twice.
    That is the same failure the filing frontier rule exists to prevent, and
    it arrives here by a different route.

    Across every symbol the company has, unioned: a day on which any listed
    class traded is a day the blended reading could have moved. `period_end`
    and `filed` are the session itself — a reading taken that day, from the
    filings on record that day. There is no accession or form, and inventing
    one would put a fiscal document behind a figure that came from a price.
    """
    days: set = set()
    for sym in sorted(getattr(symbols, "all", symbols) or []):
        key = price_store.series_key(prices_doc or {}, sym)
        if key is None:
            continue
        days.update(str(r[0])[:10]
                    for r in (prices_doc["series"][key].get("rows") or [])
                    if r[1] not in (None, 0) and str(r[0])[:10] <= today)
    return [{"filed": d, "accession": None, "form": None, "period_end": d}
            for d in sorted(days)[-limit:]] if days else []


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
                         symbols, entry_id: str, *, industry: dict,
                         max_boundaries: int = CONFIRMATION_BOUNDARY_CAP
                         ) -> dict:
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
            ctx = Ctx(prefix, prices_doc, symbols,
                      today=b["filed"], price_cutoff=b["filed"],
                      industry=industry)
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
