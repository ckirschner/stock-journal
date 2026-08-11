"""A fixture that never names a measure plainly.

Invented content. Everything it reads about the security, it reads as a
*change* since a purchase or as a window with a year dropped — never as the
plain reading. That is the shape the host used to answer wrongly: the
surfaces that let a user supply a figure worked out which measures a decision
had touched by matching the subject KIND, and a drift citation resolves as
kind `change`, so the figure was cited on screen with no way to give it.

Nothing in either shipped strategy exercises this, because both of them
happen to name every drift measure plainly somewhere else as well. This one
does not, so the seam is pinned rather than covered by coincidence.
"""

STRATEGY = {
    "id": "drifter",
    "name": "Drift fixture",
    "summary": "A test fixture that only ever asks how far something has "
               "moved. It is not investment logic.",
    "version": 1,
    "contract": 5,
    "changelog": {
        1: "First version.",
    },
    "states": [
        {"id": "watch", "name": "Watch", "render": "hold",
         "description": "The fixture holds and reports the drift."},
    ],
    "inputs": [],
    "values": [
        {"id": "drift-floor", "label": "Worst drift tolerated",
         "type": "number", "unit": "percentage_points", "max": 0,
         "source": {"name": "a test fixture", "reasoning": True},
         "explain": "How far the margin may fall from where it was at the "
                    "first purchase before this fixture says so."},
        {"id": "cushion-floor", "label": "Worst current ratio tolerated",
         "type": "number", "unit": "ratio", "min": 0,
         "source": {"name": "a test fixture", "reasoning": True},
         "explain": "The lowest current ratio this fixture accepts once its "
                    "flattering year is taken out."},
    ],
}


def decide(ctx):
    return {
        "state": "watch",
        "payload": {},
        "reason": {
            "rule": "drift-only",
            "summary": "The fixture reports how far its two measures have "
                       "moved and does nothing about it.",
            "evidence": [
                {"measure": "gross_margin_ttm", "since": "first-purchase",
                 "change": "distance", "comparator": "at_least",
                 "threshold_from": "drift-floor"},
                {"measure": "current_ratio", "without": "one-year",
                 "comparator": "at_least",
                 "threshold_from": "cushion-floor"},
            ],
        },
    }
