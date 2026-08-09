"""Reads a lookup table it ships beside its own code — the third channel.
Invented content; it proves the host loads declared reference data, hands it
back frozen, and that a strategy never opens a file itself."""

STRATEGY = {
    "id": "shipped-data",
    "name": "Shipped data fixture",
    "summary": "Looks a ticker up in a table it ships. Not investment "
               "logic.",
    "version": 1,
    "contract": 4,
    "changelog": {1: "First version."},
    "reference": ["sectors.yaml"],
    "states": [
        {"id": "known-sector", "name": "Sector known", "render": "hold",
         "description": "The ticker was in the shipped table."},
        {"id": "unknown-sector", "name": "Sector unknown",
         "render": "unknown",
         "description": "The ticker was not in the shipped table, so the "
                        "fixture has nothing to say."},
    ],
}


def decide(ctx):
    sectors = ctx["reference"]["sectors.yaml"]["sectors"]
    ticker = ctx["security"]["ticker"]
    sector = sectors.get(ticker)
    if sector is None:
        return {
            "state": "unknown-sector",
            "payload": {},
            "reason": {
                "rule": "not-in-table",
                "summary": f"{ticker} is not in the shipped sector table.",
                "evidence": [],
            },
        }
    return {
        "state": "known-sector",
        "payload": {},
        "reason": {
            "rule": "table-lookup",
            "summary": f"{ticker} is listed as {sector}.",
            "evidence": [
                {"label": "Sector", "unit": "text", "actual": sector},
                {"label": "Tickers in the shipped table", "unit": "count",
                 "actual": len(sectors)},
            ],
        },
    }
