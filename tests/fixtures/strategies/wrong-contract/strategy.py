"""Speaks a contract version this host does not. Must be refused, not run."""

STRATEGY = {
    "id": "wrong-contract",
    "name": "Wrong contract fixture",
    "summary": "Declares contract 99 to prove version refusal.",
    "version": 1,
    "contract": 99,
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
