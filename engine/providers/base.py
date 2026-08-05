"""Data provider interface.

Nothing here touches the network yet. Fundamentals should come from SEC EDGAR's
XBRL companyfacts API (free, no key, but only reaches back to roughly 2009-2011
when the mandate phased in). Prices can come from yfinance, which is an
unofficial scrape and will break periodically. Fine for quotes, a bad thing to
make fundamentals depend on.

Implement fetch() and the rest of the app works unchanged.
"""

from __future__ import annotations


class Provider:
    name = "base"

    def fetch(self, ticker: str) -> dict:
        """Return {"price": float|None, "metrics": {id: value}, "history": {...}}.

        Absent metrics must be omitted rather than set to zero. The UI hides a
        metric it has no value for; a zero would render as a confident failure.
        """
        raise NotImplementedError


class ManualProvider(Provider):
    """Values are whatever the user typed. Always available, never wrong."""
    name = "manual"

    def fetch(self, ticker: str) -> dict:
        return {"price": None, "metrics": {}, "history": {}}
