"""Its declaration is sound but its values.yaml will not parse. The refusal
must say the file could not be read — never that it is missing, which would
name a fix the author cannot act on."""

STRATEGY = {
    "id": "corrupt-values",
    "name": "Corrupt values fixture",
    "summary": "Ships a values.yaml that is not YAML.",
    "version": 1,
    "contract": 8,
    "changelog": {1: "First version."},
    "states": [
        {"id": "nothing", "name": "Nothing", "render": "hold",
         "description": "Never reached."},
    ],
    "values": [
        {"id": "patience", "label": "Patience", "type": "integer",
         "min": 1, "max": 10,
         "source": {"name": "a test fixture", "reasoning": True},
         "explain": "Never resolved."},
    ],
}


def decide(ctx):
    return {"state": "nothing", "payload": {},
            "reason": {"rule": "never", "summary": "Never reached.",
                       "evidence": []}}
