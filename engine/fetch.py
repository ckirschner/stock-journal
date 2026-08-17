"""Fetch orchestration: one ticker, all its raw material, every failure
visible.

Runs on explicit user action only — never on a schedule. The stages, in
order, each isolated so one failing cannot poison the rest:

1. Refresh the SEC ticker map (snapshot + diff) and resolve the ticker to a
   CIK. A ticker the journal has already tied to a CIK is never silently
   re-tied: if the symbol now resolves to a DIFFERENT company, the fetch
   stops and reports it — that is the reused-symbol trap, and only the user
   can say which company they mean.
2. Company identity from EDGAR (name history is evidence for renames).
3. Filing index, then extraction of every not-yet-extracted 10-K/10-Q family
   filing. Per-filing failures are recorded per accession and skipped next
   time when permanent (pre-XBRL filings have nothing to extract).
4. Prices for every symbol the SEC currently maps to the CIK, from the price
   source, merged raw. A symbol that stopped resolving gets its series marked
   terminal, kept as retrieved.

Progress is observable (the UI polls) because a first fetch walks fifteen
years of filings at the SEC's polite request rate and takes a minute or two.
A stale reading is identifiable as stale: every stage records when it last
succeeded, per ticker, in the company record.
"""

from __future__ import annotations

import threading
import traceback
from datetime import datetime, timezone

from . import facts_store, gateway, price_store, secrets, store, tickermap, \
    tiingo

_lock = threading.Lock()
_status: dict[str, dict] = {}     # ticker -> live progress
_cik_locks: dict[int, threading.Lock] = {}   # one writer per company
# One fetch at a time, full stop. Two reasons, both learned the hard way:
# the SEC's request budget is per requester, so concurrent fetches multiply
# our rate; and the underlying library shares global HTTP state that is not
# safe under concurrent fetches (a second fetch's setup killed the first
# one's in-flight requests). Queued fetches show "waiting" in their status.
_fetch_gate = threading.Lock()
_PERMANENT_ERROR_MARKERS = ("no parseable XBRL",)


def _cik_lock(cik: int) -> threading.Lock:
    """Two tickers can resolve to one CIK (share classes); their fetches must
    not interleave writes to the same company and price files."""
    with _lock:
        return _cik_locks.setdefault(int(cik), threading.Lock())


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def status_of(ticker: str) -> dict | None:
    with _lock:
        s = _status.get(str(ticker).upper())
        return dict(s) if s else None


def _set_status(ticker: str, **kw):
    with _lock:
        s = _status.setdefault(ticker, {})
        s.update(kw)


def identity() -> str:
    """The SEC identity contact. Machine-local and nowhere else: it is an
    email address, so it must not ride along in an export bundle. There is
    no fallback to a settings document, because a document that could hold
    one is a document that could export one."""
    return str(secrets.local_get("sec_identity") or "").strip()


def start_fetch(ticker: str, known_cik=None,
                on_resolved=None, on_report=None) -> dict:
    """Kick off a background fetch. Returns immediately with either
    {"started": True} or {"error": ...} for preconditions that fail fast.

    on_resolved(ticker, cik) is called from the fetch thread the moment the
    company is safely resolved (after the reused-symbol check), so the
    CIK tie-in persists even if no UI poll ever observes completion — the
    protection against a reassigned symbol must not depend on a poll loop
    surviving."""
    t = str(ticker).upper().strip()
    who = identity()
    if not who or "@" not in who:
        return {"error": "Set your SEC identity first (Data tab): your name "
                         "and a real email address. The SEC requires it on "
                         "every request and blocks anonymous tools."}
    with _lock:
        if _status.get(t, {}).get("running"):
            return {"error": f"A fetch for {t} is already running."}
        _status[t] = {"running": True, "stage": "starting", "errors": [],
                      "started": _stamp(), "done": 0, "total": 0}
    thread = threading.Thread(
        target=_run_fetch, args=(t, known_cik, on_resolved, on_report),
        daemon=True)
    thread.start()
    return {"started": True}


def _run_fetch(ticker: str, known_cik, on_resolved=None, on_report=None):
    try:
        got_gate = _fetch_gate.acquire(blocking=False)
        if not got_gate:
            _set_status(ticker, stage="waiting for another fetch to finish")
            _fetch_gate.acquire()
        try:
            report = fetch_ticker(ticker, known_cik,
                                  progress=lambda **kw: _set_status(ticker, **kw),
                                  on_resolved=on_resolved)
        finally:
            _fetch_gate.release()
        if on_report:
            # From the fetch thread, like on_resolved, and for the same
            # reason: a structural refusal is a fact about the security and
            # must not depend on a UI poll surviving to completion to get
            # recorded.
            on_report(ticker, report)
        _set_status(ticker, running=False, finished=_stamp(), report=report,
                    stage="done")
    except Exception as e:                              # noqa: BLE001
        traceback.print_exc()
        _set_status(ticker, running=False, finished=_stamp(), stage="failed",
                    error=f"{type(e).__name__}: {e}")


def fetch_ticker(ticker: str, known_cik=None,
                 progress=lambda **kw: None, on_resolved=None) -> dict:
    """The synchronous fetch. Returns a report dict; raises only for
    preconditions (identity), never for per-item failures."""
    who = identity()
    errors: list[str] = []
    report = {"ticker": ticker, "at": _stamp(), "errors": errors}

    # -- stage 1: resolve the company ------------------------------------
    progress(stage="resolving ticker")
    tmap = None
    resolved_cik = None
    try:
        tmap = tickermap.refresh(who)
        hit = tickermap.resolve(tmap, ticker)
        resolved_cik = hit["cik"] if hit else None
        report["sec_title"] = hit["title"] if hit else None
    except tickermap.TickerMapError as e:
        errors.append(f"ticker map: {e}")

    if known_cik and resolved_cik and int(known_cik) != int(resolved_cik):
        report["conflict"] = (
            f"{ticker} is recorded in the journal as CIK {int(known_cik)}, "
            f"but the SEC now maps it to CIK {resolved_cik} "
            f"({report.get('sec_title')}). Exchanges reuse symbols; this one "
            "appears to have been reassigned to a different company. Nothing "
            "was fetched — the recorded history stays with the original "
            "company, and re-tying the symbol is a decision only you can "
            "make (remove and re-add the security to adopt the new company).")
        _mark_prices_terminal(int(known_cik), ticker, report["conflict"],
                              errors)
        return report
    cik = int(known_cik or resolved_cik or 0)
    if not cik:
        report["conflict"] = (
            f"{ticker} does not resolve to any company in the SEC's current "
            "ticker map, and the journal has no CIK on record for it. If it "
            "was renamed or delisted, look the company up on EDGAR and check "
            "the symbol; nothing was fetched.")
        return report
    report["cik"] = cik
    if on_resolved is not None:
        try:
            on_resolved(ticker, cik)
        except Exception as e:                          # noqa: BLE001
            errors.append(f"recording the resolved company failed: {e}")
    if resolved_cik is None and tmap is not None:
        report["ticker_unmapped"] = (
            f"{ticker} has dropped out of the SEC ticker map; fetching by "
            f"its recorded CIK {cik}. The company may be delisted, renamed, "
            "or acquired — its filings and prices are kept and marked.")
        _mark_prices_terminal(cik, ticker, report["ticker_unmapped"], errors)

    # -- stage 2: identity + filing index --------------------------------
    lock = _cik_lock(cik)
    if not lock.acquire(timeout=1):
        report["conflict"] = (
            f"another fetch is already writing this company's records "
            f"(CIK {cik} — share classes share one company); wait for it to "
            "finish and fetch again")
        return report
    try:
        return _fetch_company(ticker, who, cik, tmap,
                              resolved_cik, report, errors, progress)
    finally:
        lock.release()


def _fetch_company(ticker, identity, cik, tmap, resolved_cik,
                   report, errors, progress):
    data_dir = store.data_dir()
    gateway.configure(str(data_dir / "cache" / "edgar"), identity)
    doc = facts_store.load_company(cik)
    info, filings = None, []
    try:
        progress(stage="reading company identity")
        info = _retry_once(lambda: gateway.company_info(cik))
        facts_store.record_identity(doc, info)
        progress(stage="listing filings")
        filings = _retry_once(lambda: gateway.list_filings(cik))
        facts_store.record_filing_index(doc, filings)
    except gateway.GatewayError as e:
        errors.append(f"EDGAR: {e}")
    if info is not None and not doc.get("filing_index"):
        # An empty index after a successful listing is a fact worth
        # explaining, not a quiet success: foreign private issuers file
        # 20-F/6-K under IFRS, which this pipeline does not read (its concept
        # map is US GAAP), and "fetched, nothing there" must say so.
        recent = [f for f in info.get("recent_forms") or []
                  if not f.startswith(("3", "4", "5", "SC "))]
        if any(f.startswith(("20-F", "40-F", "6-K")) for f in recent):
            report["no_coverage"] = (
                f"{info.get('name') or ticker} files "
                f"{', '.join(recent[:4])} — a foreign private issuer "
                "reporting under IFRS. This pipeline reads the 10-K/10-Q "
                "families and maps US GAAP concepts only, so there is "
                "nothing it can extract; metrics stay absent rather than "
                "guessed from a different accounting language.")
        elif recent:
            report["no_coverage"] = (
                f"{info.get('name') or ticker} has no 10-K/10-Q family "
                f"filings on EDGAR (it files {', '.join(recent[:4])}), so "
                "there is nothing this pipeline can extract.")
        if report.get("no_coverage"):
            errors.append(report["no_coverage"])
    facts_store.save_company(cik, doc)

    # -- stage 3: extract new filings ------------------------------------
    index = doc.get("filing_index", [])
    todo = []
    for f in index:
        if facts_store.has_filing(cik, f["accession"]):
            continue
        prior = (doc.get("extraction_errors") or {}).get(f["accession"])
        if prior and any(m in prior.get("error", "")
                         for m in _PERMANENT_ERROR_MARKERS):
            continue
        todo.append(f)
    extracted = failed = pre_xbrl = 0
    progress(stage="extracting filings", total=len(todo), done=0)
    for i, f in enumerate(todo):
        try:
            extraction = gateway.extract_filing(cik, f["accession"])
            facts_store.save_filing(cik, extraction)
            facts_store.clear_extraction_error(doc, f["accession"])
            extracted += 1
        except Exception as e:                          # noqa: BLE001
            facts_store.record_extraction_error(doc, f["accession"], str(e))
            if any(m in str(e) for m in _PERMANENT_ERROR_MARKERS):
                # Pre-XBRL filings (before the 2009-2011 phase-in) carry no
                # structured facts at all. That is a boundary of the source,
                # not a failure of this fetch — counted separately so a wall
                # of 1990s filings doesn't read as seventy errors.
                pre_xbrl += 1
            else:
                failed += 1
                errors.append(f"{f['form']} {f['accession']}: {e}")
        progress(stage="extracting filings", total=len(todo), done=i + 1)
    report["filings_new"] = extracted
    report["filings_failed"] = failed
    report["filings_pre_xbrl"] = pre_xbrl
    report["filings_held"] = sum(
        1 for f in index if facts_store.has_filing(cik, f["accession"]))

    # -- stage 4: prices ---------------------------------------------------
    progress(stage="fetching prices")
    try:
        token = secrets.get_secret("tiingo_api_token") or ""
    except secrets.SecretsError as e:
        token = ""
        errors.append(f"price key: {e}")
    symbols = []
    if tmap is not None:
        symbols = tickermap.tickers_for(tmap, cik)
    if ticker not in symbols and resolved_cik:
        symbols.append(ticker)
    prices_ok, price_notes, unquoted = [], [], []
    if symbols:
        pdoc = price_store.load(cik)
        for sym in symbols:
            # A symbol this source has already said it does not carry is not
            # asked about again. The SEC maps every registered symbol to the
            # company — Synchrony's two preferred series, eleven of Bank of
            # America's — and a price source carries none of them, so every
            # fetch spent a request per symbol to be told the same thing and
            # filed it under "problems from fetching", where it sat forever
            # on a company where nothing was wrong. A permanent red panel
            # about a non-problem teaches the reader to ignore the panel.
            #
            # Except the journal's own symbol, which is always retried. That
            # is the instrument the user holds and prices it directly; a
            # source that has started carrying it must be able to say so, and
            # the tool never refuses to look for the thing in front of you.
            was = price_store.unquoted_of(pdoc, sym, "tiingo")
            if was and sym.upper() != str(ticker).upper():
                unquoted.append(f"{sym}: {was['reason']}")
                continue
            try:
                got = tiingo.fetch_daily(sym, token)
                price_store.merge_series(pdoc, sym, "tiingo",
                                         got["rows"], got["events"])
                prices_ok.append(sym)
            except (tiingo.PriceSourceError, ValueError) as e:
                # A symbol the source has never quoted and holds no rows for
                # is a boundary of the source, recorded once — the same shape
                # stage 3 uses for a pre-XBRL filing, and counted apart from
                # real failures for the same reason.
                if getattr(e, "kind", None) == "unknown-symbol" \
                        and not price_store.series_key(pdoc, sym):
                    reason = ("the price source does not carry this symbol. "
                              "The SEC maps every security a company "
                              "registers, and a price source quotes its "
                              "common stock — a preferred series, a warrant "
                              "or a listed note is mapped here and quoted "
                              "nowhere")
                    price_store.mark_unquoted(pdoc, sym, "tiingo", reason)
                    unquoted.append(f"{sym}: {reason}")
                    continue
                price_notes.append(f"{sym}: {e}")
                errors.append(f"prices {sym}: {e}")
                # The source having never heard of a symbol we already hold
                # rows for is evidence the series ended, and the error
                # already told the user it would be marked. It was not, so
                # the promise was the only thing keeping a delisted series
                # from rendering as a live quote.
                #
                # Only that one kind. A rate limit and a rejected key raise
                # the same class of error, and marking a live series dead on
                # a throttle is worse than never marking one: the mark is
                # written once and nothing takes it back.
                #
                # Marked on the document this loop is already holding. A
                # second copy loaded here would be saved without the rows
                # merged for the symbols before it, and every one of those
                # fetches would be silently thrown away — a company with two
                # listed classes losing the good class's prices because the
                # dead one 404'd.
                #
                # Reached only where rows ARE held — the branch above takes
                # the symbol that never had any, which is not a series that
                # ended but one that never began.
                if getattr(e, "kind", None) == "unknown-symbol":
                    _mark_prices_terminal(
                        cik, sym,
                        "the price source no longer lists this symbol, which "
                        "is what a delisting or a rename looks like from "
                        "here", errors, doc=pdoc)
        price_store.save(cik, pdoc)
    else:
        price_notes.append("no symbol currently maps to this CIK; the held "
                           "series stays as retrieved")
    report["prices_fetched"] = prices_ok
    report["price_notes"] = price_notes
    # Reported apart from `errors`, exactly as pre-XBRL filings are reported
    # apart from extraction failures: a boundary of the source is not a
    # problem to go and fix, and listing one among the problems is how the
    # list of problems stops being read.
    report["prices_unquoted"] = unquoted

    facts_store.record_fetch(doc, {
        "ticker": ticker,
        "ok": not errors,
        "filings_new": extracted, "filings_failed": failed,
        "prices": prices_ok, "errors": errors[:20],
    })
    facts_store.save_company(cik, doc)
    progress(stage="done")
    return report


def _retry_once(call, pause: float = 5.0):
    """One polite retry for the listing stage: a single transient timeout
    should not fail a whole fetch, and one retry after a pause is well within
    the SEC's fair-access expectations."""
    import time
    try:
        return call()
    except gateway.GatewayError as e:
        if "429" in str(e) or "TooManyRequests" in str(e):
            raise                       # throttled: back off, do not press
        time.sleep(pause)
        return call()


def _mark_prices_terminal(cik: int, ticker: str, reason: str,
                          errors: list, doc: dict | None = None) -> None:
    """The terminal mark IS the evidence a series ended; a failure to record
    it must be visible, not swallowed.

    `doc` is for the one caller that already holds the price document open:
    the mark goes onto that document and the caller's own save persists it.
    Loading a second copy there would write a version of the file that does
    not have the rows just merged into the first — and the caller would then
    either save over the mark or reload and lose the rows. One document, one
    save; the shape refuses the interleaving rather than the caller having to
    remember it.
    """
    try:
        pdoc = doc if doc is not None else price_store.load(cik)
        if (pdoc.get("series") or {}).get(str(ticker).upper()):
            price_store.mark_terminal(pdoc, ticker, reason)
            if doc is None:
                price_store.save(cik, pdoc)
    except Exception as e:                              # noqa: BLE001
        errors.append(f"marking the {ticker} price series terminal failed "
                      f"({type(e).__name__}: {e}); the series still reads as "
                      "live — retry the fetch")
