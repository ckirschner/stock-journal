"""A fixture that edits the context it was handed before citing it. Invented
content; it exists so the host's claim that a strategy cannot restate the
host's own figures can be tested rather than asserted."""

STRATEGY = {
    "id": "tamper",
    "name": "Tampering fixture",
    "summary": "A test fixture that rewrites what it was given and then "
               "cites it. It is not investment logic.",
    "version": 1,
    "contract": 3,
    "changelog": {1: "First version: rewrites the context, then cites it."},
    "states": [
        {"id": "said-so", "name": "Said so", "render": "hold",
         "description": "The fixture holds, having first tried to rewrite "
                        "the figures it is about to cite."},
    ],
}


def decide(ctx):
    # Everything a strategy could reach for to make the host report a number
    # that was never computed.
    ctx["measures"]["fcf_ttm"]["current"] = {
        "status": "known", "value": 999999.0, "source": "measure",
        "cautions": [], "provenance": ["invented by the strategy"]}
    ctx["measures"]["fcf_ttm"]["series"]["points"] = []
    ctx["position"]["shares"] = 10_000
    ctx["values"]["cash-floor"] = -1
    return {
        "state": "said-so",
        "payload": {},
        "reason": {
            "rule": "rewrote-it",
            "summary": "The fixture rewrote the context and cited it.",
            "evidence": [{"measure": "fcf_ttm"}, {"fact": "position.shares"}],
        },
    }
