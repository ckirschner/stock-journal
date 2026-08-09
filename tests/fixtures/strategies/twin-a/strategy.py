"""One of two bundles claiming the same id. Both must be refused — a
journal stamped "twin" cannot know which rules it would get."""

STRATEGY = {
    "id": "twin",
    "name": "Twin A",
    "summary": "Claims the id twin, as twin-b does.",
    "version": 1,
    "contract": 2,
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
