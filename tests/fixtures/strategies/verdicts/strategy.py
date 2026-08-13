"""A fixture that can reach four different states, driven by one measure and
one declared value. Invented content; it exists so tests can watch a commit,
a hold, an exit and an unreadable evaluation come out of the same strategy
without needing four bundles.

Nothing here is investment logic. A cash-flow floor is not a reason to buy
anything.
"""

STRATEGY = {
    "id": "verdicts",
    "name": "Verdict fixture",
    "summary": "A test fixture that reads one measure against one floor and "
               "reaches a different state either side of it. It is not "
               "investment logic.",
    "version": 1,
    "contract": 7,
    "changelog": {1: "First version: reads free cash flow against a floor."},
    "states": [
        {"id": "say-yes", "name": "Commit", "render": "commit",
         "description": "Cash flow cleared the floor, so the fixture "
                        "proposes a position."},
        {"id": "say-no", "name": "Sit tight", "render": "hold",
         "description": "Cash flow is positive but under the floor, so the "
                        "fixture does nothing."},
        {"id": "say-out", "name": "Get out", "render": "close",
         "description": "Cash flow went negative, so the fixture proposes "
                        "an exit."},
        {"id": "say-dark", "name": "Nothing to read", "render": "unknown",
         "description": "Free cash flow has no value, so the fixture has no "
                        "basis for anything."},
    ],
    "values": [
        {"id": "cash-floor", "label": "Cash flow floor", "type": "number",
         "unit": "usd",
         "source": {"name": "a test fixture", "reasoning": True},
         "explain": "The trailing free cash flow a company must clear "
                    "before this fixture will propose anything."},
    ],
}


def decide(ctx):
    current = ctx["measures"]["fcf_ttm"]["current"]
    floor = ctx["values"]["cash-floor"]
    if current["status"] != "known":
        return {
            "state": "say-dark", "payload": {},
            "reason": {"rule": "needs-a-reading",
                       "summary": "Free cash flow has no value to read.",
                       "evidence": [{"measure": "fcf_ttm"}]},
        }
    value = current["value"]
    cite = {"measure": "fcf_ttm", "comparator": "at_least",
            "threshold_from": "cash-floor"}
    if value >= floor:
        return {
            "state": "say-yes",
            "payload": {"size": {"unit": "weight", "value": 5.0},
                        "condition": None},
            "reason": {"rule": "clears-the-floor",
                       "summary": "Free cash flow clears the floor.",
                       "evidence": [cite, {"value": "cash-floor"}]},
        }
    if value < 0:
        return {
            "state": "say-out",
            "payload": {"when": ctx["today"]},
            "reason": {"rule": "cash-went-negative",
                       "summary": "Free cash flow turned negative.",
                       "evidence": [cite]},
        }
    return {
        "state": "say-no", "payload": {},
        "reason": {"rule": "under-the-floor",
                   "summary": "Free cash flow is positive but under the "
                              "floor.",
                   "evidence": [cite]},
    }
