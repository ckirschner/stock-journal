"""A fixture that cites a qualified measure, now and at a past period.

Market capitalization for a multi-class filer is the one figure in the host
that rests on an admitted approximation: a share class with no stored close
is valued at a sibling's. Keeping that approximation was made conditional on
the reader being told about it, so something has to cite the measure through
the real evaluation path — current and `at` a period end alike — for the
chain to be checkable end to end.

Invented content. It is not investment logic, and the threshold is a round
number chosen so the fixture reaches a state, not because it means anything.
"""

STRATEGY = {
    "id": "qualified",
    "name": "Qualified fixture",
    "summary": "A test fixture that reads market capitalization against a "
               "floor. It is not investment logic.",
    "version": 1,
    "contract": 4,
    "changelog": {1: "First version."},
    "states": [
        {"id": "big-enough", "name": "Big enough", "render": "commit",
         "description": "The fixture's floor was cleared."},
        {"id": "too-small", "name": "Too small", "render": "hold",
         "description": "The fixture's floor was not cleared."},
        {"id": "cannot-say", "name": "Cannot say", "render": "unknown",
         "description": "No market capitalization could be read."},
    ],
    "values": [
        {"id": "floor", "label": "Smallest company", "type": "number",
         "unit": "usd", "min": 0,
         "explain": "The smallest market capitalization the fixture will "
                    "stage an entry against."},
    ],
}


def decide(ctx):
    m = ctx["measures"]["market_cap"]
    current = m["current"]
    floor = ctx["values"]["floor"]
    # The newest reading on record, cited by its period end — the route that
    # used to hand back a number with its cautions removed.
    points = [p for p in m["series"]["points"] if p["value"] is not None]
    cite = [{"measure": "market_cap", "comparator": "at_least",
             "threshold": floor}]
    if points:
        cite.append({"measure": "market_cap", "at": points[-1]["period_end"]})

    if current["status"] != "known":
        return {"state": "cannot-say",
                "payload": {},
                "reason": {"rule": "needs-a-figure",
                           "summary": "The fixture has nothing to compare.",
                           "evidence": cite}}
    if current["value"] < floor:
        return {"state": "too-small",
                "payload": {},
                "reason": {"rule": "floor", "summary": "Under the floor.",
                           "evidence": cite}}
    return {
        "state": "big-enough",
        "payload": {"size": {"unit": "weight", "value": 5.0},
                    "condition": None},
        "reason": {"rule": "floor", "summary": "Over the floor.",
                   "evidence": cite},
    }
