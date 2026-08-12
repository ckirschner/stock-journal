"""Joining computed values to the journal, with the resolution rule.

The rule, from the task's decisions: **hand-entered values are never
overwritten by a fetch.** Nothing here writes into what the user entered —
computed values live beside it, and the merge happens at read time, visibly:

    merged = computed values, with hand-entered values on top

Both sides survive. The UI can always show "hand-entered 2.1 (computed 1.8)"
because the resolution is a view, not a mutation. Clearing the hand-entered
value is the explicit act that lets the computed one through — and it is an
entry on a dated record rather than a deletion, so the figure that was
withdrawn is still readable and the day it was withdrawn is on it.

Computation is cheap and never persisted, but it is not free — a company's
filings are a few dozen JSON files — so results are cached in memory against a
fingerprint of the stores (file count + newest mtime + concept-map mtime).
A fetch changes the fingerprint and the cache falls away by itself.

No bank entry needs a number from outside the filings and the price
history. There used to be one — an earnings yield divided by a risk-free rate
— and it was permanently absent, because the rate is not in any filing and
nothing here could supply it. A measure needing a figure nobody can hand over
is not a measure; comparing earnings yield against a risk-free rate is a
judgement, so it belongs to a strategy, which declares the rate as one of its
own values and does the division itself.
"""

from __future__ import annotations

from pathlib import Path

from . import compute, concept_map, crosscheck, facts_store
from . import hand_entered, industry, instruments, judgements, price_store

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
    # Read once and shared by every context built from this bundle. What the
    # SEC calls a filer decides whether several measures mean anything at all,
    # so a live reading and a reconstruction disagreeing about it would be two
    # screens disagreeing about whether a number exists.
    ind = industry.history({"cik": cik})
    # Which of the company's symbols is its common stock, read once off the
    # newest cover page on record and shared by every context built from this
    # bundle — the live one and every reconstruction. What a symbol denotes is
    # identity rather than measurement, so it does not move with the day being
    # evaluated; see engine/instruments.py.
    syms = instruments.company_symbols(filings, tickers)
    held = {"fp": fp, "tickers": tuple(tickers), "symbols": syms,
            "ctx": compute.Ctx(filings, prices, syms, industry=ind),
            "filings": filings, "prices": prices, "industry": ind,
            "results": {}}
    _cache[cik] = held
    return held


def invalidate(cik: int | None = None) -> None:
    if cik is None:
        _cache.clear()
        _prices_cache.clear()
    else:
        _cache.pop(cik, None)
        _prices_cache.pop(cik, None)


_prices_cache: dict = {}


def _prices(cik: int) -> dict:
    """The stored price document, cached on the price file's own mtime.

    Kept apart from `_bundle` deliberately. Pricing a security needs the price
    rows and nothing else — no filings, no computation context, and above all
    no list of the company's other symbols. A reader with no list cannot pick
    the wrong one out of it.
    """
    p = price_store.path_for(cik)
    stamp = p.stat().st_mtime if p.exists() else 0
    held = _prices_cache.get(cik)
    if held and held[0] == stamp:
        return held[1]
    doc = price_store.load(cik)
    _prices_cache[cik] = (stamp, doc)
    return doc


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
        ctx = compute.Ctx(dated, b["prices"], b["symbols"],
                          today=as_of, price_cutoff=as_of,
                          industry=b["industry"])
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


def asof_availability(cik: int, tickers: list[str], ticker: str,
                      as_of: str) -> dict:
    """What the stores can honestly say about `as_of`: how many stored
    filings had been filed by then (and the newest), and whether a close
    exists on or shortly before that day. The reconstruction's basis, for
    the record and the screen.

    Two symbol arguments, because two different questions are being asked.
    The filings and the measures built from them belong to the *company*, so
    they read every class. The close belongs to the *security* being bought,
    so it reads one — a purchase reconstructed at a sibling class's price
    would freeze that price into an append-only record.
    """
    b = _bundle(cik, tickers)
    slot = _asof_slot(b, as_of)
    newest = max((str(f.get("filed") or "")[:10] for f in slot["filings"]),
                 default=None)
    price = price_view_asof(cik, ticker, as_of)
    return {"as_of": as_of,
            "filings_by_then": len(slot["filings"]),
            "filings_held": len(b["filings"]),
            "newest_filed": newest,
            "price": price}


def _one_symbol(ticker, caller: str) -> str:
    """Refuse a list where an instrument is wanted.

    Iterating a list of every class mapped to the company and keeping the
    newest close is exactly how a Class B holding came to be priced at the
    Class A close, so the price readers take one symbol and say so loudly.
    A string would iterate into characters and fail quietly; this is the
    version that cannot.
    """
    if not isinstance(ticker, str):
        raise TypeError(
            f"{caller} prices one security and takes one symbol, not "
            f"{type(ticker).__name__}. A company's other share classes are "
            "different instruments at different prices — handing them over is "
            "what let a holding be priced from a class it is not.")
    return ticker


def _no_close(prices: dict, ticker: str, when: str | None = None) -> str:
    """Why there is no price, naming the other classes when there are any.

    Seeing prices on screen under the same company while this security reads
    absent is confusing enough to look like a bug, so the absence says which
    instrument it is about and what else is stored. It is a sentence about
    identity — it can explain the gap, and it cannot fill it.
    """
    where = f" on or before {when}" if when else ""
    ended = price_store.terminal_of(prices, ticker)
    if ended:
        return (f"the {ticker} price series has ended "
                f"({ended.get('reason') or 'no reason recorded'}) and holds "
                f"no close{where}")
    others = price_store.other_series(prices, ticker)
    if others:
        return (f"no close is stored for {ticker}{where}. Prices are held for "
                + ", ".join(others) + " — other share classes of the same "
                "company, and not this security's price at any date")
    return f"no close is stored for {ticker}{where}"


def price_view_asof(cik: int, ticker: str, as_of: str) -> dict:
    """The close that belongs to `as_of` for ONE security: that day or the
    nearest earlier trading day, labelled with the date actually used and how
    far back it had to reach.

    It reaches back as far as the series goes, and reports the distance rather
    than refusing past it. There was a seven-day cut-off here, and it was the
    host deciding: an eight-day gap was refused outright while the live market
    cap served a year-old close with a note. Two policies for one number,
    neither of them derivable from anything the host is entitled to know.
    `days_before` is the fact; whether it is too far is the reader's call and
    the strategy's, and on a backdated purchase it is frozen into the record
    beside the price so the answer stays checkable.

    A hand-entered price never appears here — it is a statement about now, and
    reaching it into the past would invent a value. Neither does a sibling
    class's close, for the same reason one day further out: it is a real price
    for a different instrument, which is not this security's price at any
    date.
    """
    _one_symbol(ticker, "price_view_asof")
    prices = _prices(cik)
    got = price_store.close_on(prices, ticker, as_of)
    if got:
        return {"value": got[1], "source": "fetched", "date": got[0],
                "days_before": got[2],
                "ticker": price_store.series_key(prices, ticker),
                "terminal": price_store.terminal_of(prices, ticker)}
    return {"value": None, "source": None, "date": None, "days_before": None,
            "ticker": None, "terminal": price_store.terminal_of(prices,
                                                                ticker),
            "reason": _no_close(prices, ticker, as_of)}


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


def confirmation_history(cik: int, tickers: list[str],
                         entry_id: str) -> dict:
    """Per-filing readings for one sell-watched entry, cached with the same
    per-CIK bundle as the computed values — the fingerprint invalidates on
    new filings or prices. The history itself is derived, never stored:
    engine/compute.confirmation_history recomputes it from the filing files
    every time the cache turns over, so it cannot drift from the data."""
    b = _bundle(cik, tickers)
    cache = b.setdefault("confirmations", {})
    if entry_id not in cache:
        try:
            cache[entry_id] = compute.confirmation_history(
                b["filings"], b["prices"], b["symbols"], entry_id,
                industry=b["industry"])
        except Exception as e:                          # noqa: BLE001
            cache[entry_id] = {"entry": entry_id, "cadence": None,
                               "readings": [], "boundaries_held": 0,
                               "truncated": False,
                               "note": f"the filing history could not be "
                                       f"read: {type(e).__name__}: {e}"}
    return cache[entry_id]


# -- the resolution rule, in one place ---------------------------------------
#
# Computed values, hand-entered on top, and a measure the bank says cannot
# describe this filer refused before either. It was written out twice — here
# and in engine/context.py — for two consumers that want different shapes: a
# screen wants the figures that resolved, a strategy wants every measure
# including the ones that did not and why. They agreed, and they had already
# drifted once (one supplied a provenance sentence the other did not, and read
# the holding history on a different clock), and the inapplicable bar had to be
# written into both files in one change to keep them agreeing.
#
# So the rule is stated once and the two shapes are projections of it. The
# difference between them stops being prose in two docstrings and becomes a
# filter you can read.

def known(value, source, cautions=None, provenance=None,
          leave_one_out=None) -> dict:
    """One measure as a strategy reads it.

    `leave_one_out` travels beside the value because it is part of the same
    answer: for a measure read over a window of fiscal years, "and what does
    it say without its most flattering year?" is not a second measure, it is
    the only robustness test available — waiting for another filing re-reads
    the same years. Present only where the estimator reads a window; absent,
    never a copy of the value, so a check that cannot be made comes back
    unmade rather than passing itself.
    """
    out = {"status": "known", "value": value, "source": source,
           "cautions": list(cautions or []),
           "provenance": list(provenance or [])}
    if leave_one_out:
        out["leave_one_out"] = [dict(o) for o in leave_one_out]
    return out


def absent(reason: str) -> dict:
    return {"status": "absent", "reason": reason}


def inapplicable(reason: str, cls: str | None = None) -> dict:
    """A measure that will never describe this filer.

    The third status a measure can reach, and the one that must not read as
    the second. `absent` is a gap: something is missing and a fetch, a filing
    or an answer may close it, so it belongs among the things to go and do.
    This is a boundary: it was knowable before anything was computed, and it
    holds for as long as the company is the kind of company it is.

    Nothing that consumes a measure has to learn the word. Every reader asks
    whether the status is "known", so this can never be mistaken for a value
    and can never come out of a test as a pass. What the word buys is that a
    reader is told which of the two they are looking at.
    """
    node = {"status": "inapplicable", "reason": reason}
    if cls:
        node["industry"] = cls
    return node


def resolve(security: dict, computed: dict,
            as_of: str | None = None) -> dict:
    """{entry id: node} — the one resolution rule, status and all.

    A hand-entered value is dated, so a pinned reading serves the figure that
    was on record on its day and nothing entered afterwards. Where none was —
    the figure was typed later, or withdrawn — the measure is absent with the
    reason, and nothing is ever told a present-day number was known on a past
    day.

    That absence only shows through where the computed layer has nothing
    known to offer. A user who typed a figure today and then withdrew it has
    not made the filings unreadable, and "you cleared this" is a worse answer
    than the number that was there all along.

    A measure the bank says cannot describe this filer is refused BEFORE the
    overlay. Whatever was typed is a different quantity wearing this
    measure's name, unit and explanation, and it would feed a verdict — the
    one place principle 4 says a qualification is read by a person and ignored
    by the arithmetic. The figure stays on the dated record and becomes
    readable again if the SEC ever reclassifies the filer; it is the serving
    that is refused, not the recording.

    Judgements are not here. Hand-entered values are numbers, and a number
    laid over a question about a moat would be an assessment presented as a
    measurement. They are served from their own dated record by whoever wants
    them — see `merged_values` and engine/context._measures — because the two
    consumers want them at different points and on different clocks.
    """
    out = {}
    for eid, r in (computed or {}).items():
        if r.get("status") == "computed":
            out[eid] = known(r["value"], "computed", r.get("cautions"),
                             r.get("provenance"), r.get("leave_one_out"))
        elif r.get("status") == "inapplicable":
            out[eid] = inapplicable(r["reason"], r.get("industry"))
        else:
            out[eid] = absent(r.get("reason")
                              or "the value could not be computed")
    for eid in hand_entered.ids(security):
        if (out.get(eid) or {}).get("status") == "inapplicable":
            continue
        r = hand_entered.reading(security, eid, as_of)
        if r["status"] == "known":
            out[eid] = known(r["value"], "manual", r["cautions"],
                             r["provenance"])
        elif (out.get(eid) or {}).get("status") != "known":
            out[eid] = absent(r["reason"])
    return out


def qualified(value, source, cautions=None, provenance=None) -> dict:
    """A value and everything that qualifies it, as one object.

    One object rather than a number beside some notes, because the number
    travels — onto a screen, into a frozen snapshot, through a strategy's
    evidence — and every hop is a chance to carry the figure and drop what
    was wrong with it. A record that loses its qualifier states the number
    as more certain than it was, which in an append-only journal can never
    be corrected afterwards. Nothing here hands out a bare float, so no
    caller can hold one without its cautions.
    """
    return {"value": value, "source": source,
            "cautions": list(cautions or []),
            "provenance": list(provenance or [])}


def merged_values(security: dict, computed: dict,
                  as_of: str | None = None, today: str | None = None) -> dict:
    """{entry id: qualified value} — computed values, hand-entered on top,
    and the judgements the user assessed.

    Each entry says which side it came from and never loses the other: the
    computed result is still in `computed` for a screen to show beside it.

    Everything the user supplied is dated. A pin serves the figure or the
    assessment that stood on that day and nothing at all where none did, so
    a record frozen for a past day never claims a present-day number was
    known then. Both are read through the same modules the strategy's own
    context reads — `hand_entered.values` and `judgements.observations` —
    rather than off the stored list here, so the two overlays cannot come to
    disagree about the same figure. They did, before that was true: this one
    supplied a provenance sentence the context did not, and read the holding
    history on a different clock.

    `today` is that clock — the day the *holding* history is read against,
    which is not the same as the day being reconstructed. A judgement is
    stale because a holding closed, and whether it had closed is a question
    about the calendar, not about the pin.

    Judgements are here rather than only inside the decision's evidence
    because this is what a purchase freezes as "every value behind the
    decision", and an assessment the strategy did not happen to cite is
    still one of them.

    A hand-entered number can never land on a qualitative id — the write
    refuses it and the read refuses it again — so a journal written before
    that refusal existed cannot still read as an assessment.

    This is `resolve` with the judgements laid over it and everything that
    did not resolve dropped — the projection a screen and a frozen snapshot
    want. It is deliberately narrower than what a strategy is handed: a
    snapshot holds only figures that were known, because an absence frozen
    into an append-only record is a permanent statement that something could
    not be read on a day when it may only have been unfetched.
    """
    nodes = resolve(security, computed, as_of)
    # Judgements last, and only here. A purchase freezes this as "every value
    # behind the decision", and an assessment the strategy did not happen to
    # cite is still one of them — but it is read on the HOLDING's clock
    # (`today`) rather than the pin's, because a judgement is stale when a
    # holding closed and whether it had closed is a question about the
    # calendar, not about the day being reconstructed.
    for eid, a in judgements.observations(security, as_of=as_of,
                                          today=today).items():
        if a["status"] == "known":
            nodes[eid] = a
    return {eid: qualified(n["value"], n["source"], n.get("cautions"),
                           n.get("provenance"))
            for eid, n in nodes.items() if n["status"] == "known"}


# Said in one place, because it is said in several: on the price itself, and
# on every figure built from it. A price is the one thing the user types that
# is not dated, and the reason it is not is worth stating rather than leaving
# the reader to spot a blank where every other record shows a day.
_MANUAL_IS_UNDATED = (
    "entered by hand, so it carries no date — this is what you saw the "
    "market quote, not something you worked out, and the dated version of it "
    "is the price history a fetch keeps. Nothing here can tell how long ago "
    "you typed it")


def price_view(security: dict, cik: int | None, ticker: str) -> dict:
    """The price the journal should show for ONE security: hand-entered wins,
    else that security's own newest stored close, labelled with its date so
    stale is visible.

    One symbol, never a list of the company's classes. Two share classes are
    two instruments at two prices — twenty shares of a Class B security priced
    at the Class A close read $14,100,000 instead of $9,400 — and the error is
    silent, because a dollar figure is plausible in shape whatever its value.
    It reaches market value, the account total and every weight, and strategies
    bind on weight, so it is wrong decisions rather than wrong displays.

    The signature is the guarantee. There is no list here to take the newest
    close from, so no future caller can reintroduce the substitution without
    first changing this line.
    """
    _one_symbol(ticker, "price_view")
    # Zero or less is refused rather than served. It is not a price the market
    # set, and everything downstream would treat it as one — a $0 market value,
    # a 0% weight, a -100% on every open share, all four confident. Refused
    # here as well as at the field, because a journal written before the field
    # refused it must not still read as a fact.
    manual = security.get("price")
    refused = None
    ended = price_store.terminal_of(_prices(cik), ticker) if cik else None
    if manual not in (None, ""):
        if float(manual) > 0:
            # `date` is None and stays None, and the screen says why rather
            # than leaving the reader to notice. A hand-entered price is not
            # a claim about the business that could be dated and revised —
            # it is what the market said, and the dated form of that is the
            # price history the fetcher keeps. What it is NOT is a figure
            # anyone can tell the age of, and it feeds market value, weight
            # and the account total, so the absence is stated where those
            # are shown instead of being inferred from a blank.
            return {"value": float(manual), "source": "manual", "date": None,
                    "undated": _MANUAL_IS_UNDATED, "ticker": ticker,
                    "terminal": ended}
        refused = (f"the price on record for {ticker} is {float(manual):g}, "
                   "which is not a price — clear it, or enter what the "
                   "security actually trades at")
    if cik:
        prices = _prices(cik)
        got = price_store.latest_close(prices, ticker)
        if got:
            return {"value": got[1], "source": "fetched", "date": got[0],
                    "ticker": price_store.series_key(prices, ticker),
                    "terminal": ended}
        return {"value": None, "source": None, "date": None, "ticker": None,
                "terminal": ended,
                "reason": refused or _no_close(prices, ticker)}
    return {"value": None, "source": None, "date": None, "ticker": None,
            "terminal": None,
            "reason": refused or
            (f"{ticker} is not matched to a company at the SEC, so no price "
             "history has been fetched for it — enter a price by hand, or "
             "match it in Data")}


def price_series(cik: int | None, ticker: str, until: str | None = None):
    """(closes, events) for ONE security's own instrument, ascending.

    The history has to belong to the same instrument as the price beside it,
    or a strategy measures a move that never happened. Returned together with
    nothing to choose between, for the same reason `price_view` takes one
    symbol.
    """
    _one_symbol(ticker, "price_series")
    if not cik:
        return [], []
    key = price_store.series_key(_prices(cik), ticker)
    if key is None:
        return [], []
    s = _prices(cik)["series"][key]
    closes = [[d, float(c)] for d, c, *_ in s["rows"]
              if c not in (None, 0) and (until is None or d <= until)]
    events = [list(e) for e in (s.get("events") or [])
              if e and (until is None or e[0] <= until)]
    return closes, events


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
    # Symbols the price source does not carry. A standing fact about the
    # symbol rather than an event in the last fetch, so it is read off the
    # price document and not off the fetch record — and reported apart from
    # the errors, because it is a boundary of the source and not a problem to
    # go and fix. It sat in the red panel forever on companies where nothing
    # was wrong, which is how a panel of problems stops being read.
    unquoted = sorted(
        ({"ticker": t, "reason": m.get("reason"), "source": m.get("source")}
         for t, m in (prices.get("unquoted") or {}).items()),
        key=lambda r: r["ticker"])
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
        "unquoted_symbols": unquoted,
        "identity": (doc.get("identity") or {}).get("name"),
        # What the SEC says this filer is, and what the host makes of it.
        # Reported here rather than only handed to a strategy: it decides
        # whether a whole rule set has anything to say about the company, and
        # a figure that can do that with nowhere on screen to read it is the
        # kind of invisible input this program exists to not have.
        "industry": industry.report({"cik": cik}),
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
            # Which kind of company put a measure out of scope, where one
            # did. The reason sentence says it in prose; this says it in a
            # form a screen can group and count on, which is what keeps a
            # permanent boundary out of the list of things to go and fetch.
            "industry": r.get("industry"),
            "cautions": r.get("cautions") or [],
            "provenance": r.get("provenance") or [],
        })
    check = crosscheck.run(b["filings"], b["prices"], b["symbols"])
    return {"entries": rows, "crosscheck": check,
            "status": data_status(cik)}
