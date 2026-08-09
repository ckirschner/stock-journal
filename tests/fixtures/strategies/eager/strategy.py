"""Two proofs in one bundle. Its declaration must be fully readable at load
— if the host ever calls decide while loading, this file screams — and when
decide genuinely runs, its crash must come back as an error in place, never
a crashed application."""

STRATEGY = {
    "id": "eager",
    "name": "Eager fixture",
    "summary": "Raises the moment its logic is asked anything.",
    "version": 1,
    "contract": 4,
    "changelog": {1: "First version."},
    "states": [
        {"id": "unreachable", "name": "Unreachable", "render": "hold",
         "description": "This state can never be produced."},
    ],
    "inputs": [
        {"id": "a-number", "label": "A number", "type": "number",
         "required": False,
         "explain": "Declared so tests can read inputs without running "
                    "logic."},
    ],
}


def decide(ctx):
    raise RuntimeError("decide must never run at load time")
