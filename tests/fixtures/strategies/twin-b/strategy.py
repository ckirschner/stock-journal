"""The other claimant of the id "twin". See twin-a."""

STRATEGY = {
    "id": "twin",
    "name": "Twin B",
    "summary": "Claims the id twin, as twin-a does.",
    "version": 1,
    "contract": 4,
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
