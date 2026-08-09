"""Ships a values.yaml whose key is a typo of the declared one. The refusal
must name the file, the key, and the near miss."""

STRATEGY = {
    "id": "mistyped-values",
    "name": "Mistyped values fixture",
    "summary": "Declares `patience` but ships a default for `pateince`.",
    "version": 1,
    "contract": 1,
    "changelog": {1: "First version."},
    "states": [
        {"id": "nothing", "name": "Nothing", "render": "hold",
         "description": "Never reached."},
    ],
    "values": [
        {"id": "patience", "label": "Patience", "type": "integer",
         "min": 1, "max": 10,
         "explain": "A fixture value that never gets used."},
    ],
}


def decide(ctx):
    return {"state": "nothing", "payload": {},
            "reason": {"rule": "never", "summary": "Never reached.",
                       "evidence": []}}
