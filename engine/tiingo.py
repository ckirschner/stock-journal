"""Tiingo price client. The chosen price source, and why:

The references were surveyed for a source with documented terms that returns
raw prices plus adjustment events. Tiingo is the one that fits: every daily row
carries the as-traded OHLC alongside ``divCash`` and ``splitFactor`` (the raw
series and the adjustment events in one response), 30+ years of history on the
free tier, documented individual-use terms, a status page, and a support
address. The rejected alternatives: yfinance/Yahoo is a reverse-engineered
endpoint with a history of breaking for everyone at once and terms that don't
contemplate the use; Stooq serves an adjusted-only series with no events, which
cannot support provenance; Alpha Vantage's free tier fell to 25 requests/day
with a report (unverified) that full history is now premium-gated.

Free-tier ceilings that matter here: 500 unique symbols/month, 50 requests/
hour. A watchlist-sized journal fetches one request per ticker per explicit
fetch, so neither binds. We are polite anyway: no retries on 429, ever.

The key is the user's own, held in the OS credential store (engine/secrets),
and it authenticates via the Authorization HEADER, never a query string — a
key in a URL lands in server logs, proxy logs and tracebacks outside our
control, and header auth makes that whole leak class impossible by
construction. Error messages from this module never contain the key either;
the failure paths are where secrets usually escape, so every dynamic message
is scrubbed. No key → prices are absent and say so. Fundamentals never depend
on this module.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.tiingo.com/tiingo/daily"
TEST_URL = "https://api.tiingo.com/api/test"
EARLIEST = "1980-01-01"


class PriceSourceError(Exception):
    """Loud, specific price-fetch failure. Never returns an empty series as
    if it were data — an empty result writes a permanent-looking gap.

    `kind` is the machine-readable half, and it exists for exactly one
    caller: only "the source has never heard of this symbol" is evidence a
    series has ended, and a rate limit or a rejected key must never be
    mistaken for it. Marking a live series terminal is worse than never
    marking one — the price keeps rendering, now labelled as dead, and the
    mark is written once and cannot be taken back. Branching on the sentence
    would put that decision one copy-edit away from breaking.
    """

    def __init__(self, message, kind: str | None = None):
        super().__init__(message)
        self.kind = kind


def _scrub(text: str, token: str) -> str:
    """No message path may carry the key, whatever upstream put in it."""
    if token and token in (text or ""):
        return text.replace(token, "•••")
    return text or ""


def _get(url: str, token: str, timeout: int = 60) -> object:
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Ledger personal journal (single user)",
        "Authorization": f"Token {token.strip()}",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # What the source said, and not what happens next. The sentence
            # used to promise the series would be kept and marked terminal,
            # which is true only where a series exists — and for a preferred
            # series or a warrant the source has never quoted, there is no
            # series and never was. Only the fetcher knows which case this is.
            raise PriceSourceError(
                "Tiingo does not know this symbol.",
                kind="unknown-symbol") from e
        if e.code in (401, 403):
            raise PriceSourceError(
                "Tiingo rejected the API key. Test or replace it on the "
                "Data tab.") from e
        if e.code == 429:
            raise PriceSourceError(
                "Tiingo's rate limit was hit (free tier: 50 requests/hour). "
                "Wait and fetch again; nothing was lost.") from e
        raise PriceSourceError(f"Tiingo returned HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise PriceSourceError(
            f"Could not reach Tiingo: {_scrub(str(e.reason), token)}") from e


def fetch_daily(ticker: str, token: str, start: str = EARLIEST) -> dict:
    """Full raw daily history for one ticker.

    Returns {"rows": [[date, close, volume]...],
             "events": [[date, "split", factor] | [date, "dividend", cash]...]}

    Rows are the as-traded close — the price actually printed that day, on
    that day's share basis. splitFactor/divCash are kept as events so any
    adjusted series can be derived later without ever storing one.
    """
    if not (token or "").strip():
        raise PriceSourceError(
            "No Tiingo API key is set. Prices stay absent until one is "
            "added on the Data tab (a free key from tiingo.com works).")
    sym = str(ticker).strip().upper().replace(".", "-")   # BRK.B -> BRK-B form
    q = urllib.parse.urlencode({
        "startDate": start,
        "format": "json",
        "resampleFreq": "daily",
    })
    data = _get(f"{BASE}/{urllib.parse.quote(sym)}/prices?{q}", token)
    if not isinstance(data, list):
        raise PriceSourceError(f"Unexpected response shape from Tiingo: "
                               f"{_scrub(str(data)[:200], token)}")
    if not data:
        raise PriceSourceError(
            "Tiingo returned an empty history for this symbol. That is a "
            "failure to fetch, not a statement that no prices exist.")
    rows, events = [], []
    for r in data:
        d = str(r.get("date") or "")[:10]
        if not d:
            continue
        close = r.get("close")
        rows.append([d, float(close) if close is not None else None,
                     r.get("volume")])
        split = r.get("splitFactor")
        if split not in (None, 0, 1, 1.0):
            events.append([d, "split", float(split)])
        div = r.get("divCash")
        if div not in (None, 0, 0.0):
            events.append([d, "dividend", float(div)])
    return {"rows": rows, "events": events}


def verify_key(token: str) -> dict:
    """One cheap request against Tiingo's test endpoint, so a bad key is
    obvious immediately instead of surfacing later as mysteriously absent
    price data. Returns {"ok": bool, "message": str}; the message never
    contains the key."""
    if not (token or "").strip():
        return {"ok": False, "message": "No key is stored to test."}
    try:
        data = _get(TEST_URL, token, timeout=30)
        msg = ""
        if isinstance(data, dict):
            msg = str(data.get("message") or "")
        return {"ok": True,
                "message": _scrub(msg, token)
                or "Tiingo accepted the key."}
    except PriceSourceError as e:
        return {"ok": False, "message": _scrub(str(e), token)}
