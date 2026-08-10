"""Returns a state it never declared. The host must refuse the invented
vocabulary and answer with its own error in place."""

STRATEGY = {
    "id": "invents",
    "name": "Inventing fixture",
    "summary": "Declares one state and returns another.",
    "version": 1,
    "contract": 5,
    "changelog": {1: "First version."},
    "states": [
        {"id": "declared", "name": "Declared", "render": "hold",
         "description": "The only state this fixture is allowed."},
    ],
}


def decide(ctx):
    return {"state": "moon-shot", "payload": {},
            "reason": {"rule": "hubris",
                       "summary": "This state was never declared."}}
