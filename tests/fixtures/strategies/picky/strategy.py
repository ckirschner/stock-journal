"""A fixture that declines two of the three kinds of company the host can
name, and evaluates everything else. Invented content; it is not investment
logic and it holds no view about any security.

It exists so the decline path can be exercised end to end — through discovery,
through the loaded record, through `evaluate`, and onto the screen — against a
bundle that also has a live branch, so a test can prove the gate refuses one
company and does not refuse the next one.

Two of three and not three of three on purpose: a fixture that declined
everything could not tell "the gate fired" from "the gate always fires".
"""

STRATEGY = {
    "id": "picky",
    "name": "Picky fixture",
    "summary": "A test fixture that holds whatever it is shown, except for "
               "kinds of company it says it does not evaluate. It is not "
               "investment logic.",
    "version": 1,
    "contract": 5,
    "changelog": {
        1: "First version. Declines lenders and property companies; "
           "evaluates insurers and everything else, and always holds.",
    },
    "declines": [
        {"class": "depository-lending",
         "because": "A fixture reason. Nothing here reads a balance sheet "
                    "that has no current section."},
        {"class": "real-estate",
         "because": "A fixture reason. Nothing here adds depreciation back."},
    ],
    "states": [
        {"id": "fixture-hold", "name": "Nothing to do", "render": "hold",
         "description": "The fixture looked at the company it was given and "
                        "did nothing, which is all it does."},
    ],
    # One declared value so the settings screen has something on it. A
    # strategy with no settings at all is a legal bundle and not the case
    # this fixture is here to draw.
    "values": [
        {"id": "patience", "label": "A number that decides nothing",
         "type": "integer", "unit": "count", "min": 0, "max": 10,
         "source": {"name": "a test fixture", "reasoning": True},
         "explain": "It exists so this fixture has a setting to render. "
                    "Changing it changes nothing at all."},
    ],
}


def decide(ctx):
    return {
        "state": "fixture-hold",
        "payload": {},
        "reason": {
            "rule": "always-hold",
            "summary": "The fixture holds, which is the only thing it does.",
            # Cited so a test can prove the fact reaches a strategy as an
            # ordinary citation, and reads as the host's own answer rather
            # than as anything this bundle worked out.
            "evidence": [{"fact": "security.industry"},
                         {"fact": "security.sic"}],
        },
    }
