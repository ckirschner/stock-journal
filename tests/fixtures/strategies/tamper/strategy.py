"""A fixture that edits the context it was handed before citing it. Invented
content; it exists so the host's claim that a strategy cannot restate the
host's own figures can be tested rather than asserted.

It swallows the refusal, which is what a strategy trying to get away with
this would do. Failing loudly would be the easy case to test; the case worth
pinning is the one where the write is refused, the strategy carries on as
though it had worked, and the host still reports what the host computed."""

STRATEGY = {
    "id": "tamper",
    "name": "Tampering fixture",
    "summary": "A test fixture that rewrites what it was given and then "
               "cites it. It is not investment logic.",
    "version": 1,
    "contract": 7,
    "changelog": {1: "First version: rewrites the context, then cites it."},
    "states": [
        {"id": "said-so", "name": "Said so", "render": "hold",
         "description": "The fixture holds, having first tried to rewrite "
                        "the figures it is about to cite."},
    ],
}


def decide(ctx):
    # Everything a strategy could reach for to make the host report a number
    # that was never computed. Every one of them is refused by the frozen
    # view, and every one of them is swallowed here.
    for write in (
        lambda: ctx["measures"]["fcf_ttm"].__setitem__("current", {
            "status": "known", "value": 999999.0, "source": "measure",
            "cautions": [], "provenance": ["invented by the strategy"]}),
        lambda: ctx["measures"]["fcf_ttm"]["series"].__setitem__("points",
                                                                 []),
        lambda: ctx["position"].__setitem__("shares", 10_000),
        lambda: ctx["values"].__setitem__("cash-floor", -1),
        lambda: ctx.__setitem__("measures", {}),
    ):
        try:
            write()
        except (TypeError, AttributeError):
            pass
    return {
        "state": "said-so",
        "payload": {},
        "reason": {
            "rule": "rewrote-it",
            "summary": "The fixture rewrote the context and cited it.",
            "evidence": [{"measure": "fcf_ttm"}, {"fact": "position.shares"}],
        },
    }
