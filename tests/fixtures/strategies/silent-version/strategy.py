"""Moved its version without saying what changed. The host refuses a version
that doesn't say — that is what makes rule changes recordable at all."""

STRATEGY = {
    "id": "silent-version",
    "name": "Silent version fixture",
    "summary": "Version 2 with a changelog that stops at 1.",
    "version": 2,
    "contract": 5,
    "changelog": {1: "First version."},
    "states": [
        {"id": "nothing", "name": "Nothing", "render": "hold",
         "description": "Never reached."},
    ],
}


def decide(ctx):
    return {"state": "nothing", "payload": {},
            "reason": {"rule": "never", "summary": "Never reached.",
                       "evidence": []}}
