"""A well-formed fixture strategy. Invented content; proves the happy path
and the richest payload shape (commit). Its one required input exists so
tests can watch a missing input become a blocked result, never a crash."""

STRATEGY = {
    "id": "sound",
    "name": "Sound fixture",
    "summary": "A test fixture that always stages a tiny commit. It is not "
               "investment logic.",
    "version": 2,
    "contract": 5,
    "changelog": {
        1: "First version.",
        2: "Second version, to prove multi-entry changelogs load.",
    },
    "states": [
        {"id": "stage-in", "name": "Stage in", "render": "commit",
         "description": "The fixture always proposes a staged entry."},
    ],
    "inputs": [
        {"id": "target-weight", "label": "Target position size",
         "type": "number", "unit": "percent", "required": True,
         "min": 0, "max": 100,
         "explain": "How large a full position should be, as a percent of "
                    "the account."},
    ],
    "values": [
        {"id": "first-stage", "label": "First stage", "type": "number",
         "unit": "percent", "min": 0, "max": 100,
         "source": {"name": "a test fixture", "reasoning": True},
         "explain": "What fraction of the target the first commit "
                    "stages."},
    ],
}


def decide(ctx):
    stage = ctx["values"]["first-stage"] * ctx["inputs"]["target-weight"] / 100
    return {
        "state": "stage-in",
        "payload": {
            "size": {"unit": "weight", "value": stage},
            "condition": {"summary": "This is a fixture; the condition "
                                     "exists to prove the shape."},
        },
        "reason": {
            "rule": "always-stage",
            "summary": "The fixture stages its first tranche "
                       "unconditionally, by construction.",
            "evidence": [
                # A held position's weight against the user's own target —
                # the case that proves a limit is NAMED rather than restated,
                # so the screen can say whose limit it is and the number
                # cannot disagree with the setting it is attributed to.
                {"fact": "position.weight", "comparator": "at_most",
                 "threshold_from": "target-weight"},
                {"input": "target-weight"},
                {"label": "This tranche", "unit": "percent",
                 "actual": stage},
            ],
        },
    }
