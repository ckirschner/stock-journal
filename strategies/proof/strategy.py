"""The contract proof. A scaffold, not a strategy.

This bundle exists to prove the host/strategy boundary end to end: it is
discovered, its declaration is read without its logic running, its shipped
default resolves through the chain, and its decision crosses back in the
contract's envelope. It holds whatever it is shown, commits nothing, and
carries no view about any security. Delete it the day a real strategy
lands.

What it deliberately touches, so the wiring is exercised and not just
asserted: one measure's current value and dated series, the clock, the one
declared value, the declared inputs, and the figures the host can only
report once a journal says what the account is.
"""

STRATEGY = {
    "id": "contract-proof",
    "name": "Contract proof",
    "summary": "A scaffold that proves the host/strategy boundary carries "
               "data both ways. It reads one measure and always holds; it "
               "is not investment logic and never will be.",
    "version": 2,
    "contract": 4,
    "changelog": {
        1: "First version: reads free cash flow and the clock, and holds.",
        2: "Asks for free cash so the account figures can be proved end to "
           "end, and cites the weight and the account the host works out "
           "from it. Still holds, always.",
    },
    "states": [
        {"id": "scaffold-hold", "name": "Nothing to do", "render": "hold",
         "description": "The scaffold read the data and, as always, does "
                        "nothing. Holding is its entire repertoire."},
        {"id": "scaffold-dark", "name": "Can't read the data",
         "render": "unknown",
         "description": "The measure the scaffold watches has no value "
                        "right now, so even doing nothing lacks a basis."},
    ],
    "inputs": [
        # An input rather than a value because no strategy could ship a
        # sensible default for a word only this user can choose.
        {"id": "journal-note", "label": "A word for the record",
         "type": "text", "required": False,
         "explain": "Any word. The scaffold echoes it back in its reason to "
                    "prove that what you type in setup reaches a "
                    "decision."},
        # The role is how the host learns what the account is. Optional on
        # purpose: a scaffold that blocked every verdict until it was
        # answered would be proving the trap rather than the boundary, and
        # leaving it blank proves the other half — free cash and every
        # weight report absent, with the reason naming this field.
        {"id": "free-cash", "label": "Free cash", "type": "number",
         "unit": "usd", "role": "cash", "required": False,
         "explain": "Money in the account that is not in any position. The "
                    "journal adds it to what your holdings are worth to get "
                    "the account total, and reports each position as a share "
                    "of that. Leave it blank and those figures say they "
                    "cannot be worked out, rather than guessing."},
    ],
    "values": [
        {"id": "patience", "label": "Readings considered", "type": "integer",
         "unit": "count", "min": 1, "max": 40,
         "explain": "How many of the newest dated readings the scaffold "
                    "counts before holding. It changes nothing but the "
                    "sentence in the reason — it exists to prove a shipped "
                    "default can be overridden and seen."},
    ],
}


def decide(ctx):
    measure = ctx["measures"]["fcf_ttm"]
    current = measure["current"]
    if current["status"] != "known":
        # The absent measure is cited, not described: the host answers with
        # its own reason, so the screen never reads a worse sentence than
        # the one the host already knows.
        return {
            "state": "scaffold-dark",
            "payload": {},
            "reason": {
                "rule": "needs-a-reading",
                "summary": "Free cash flow has no value to read, so even "
                           "doing nothing has no basis.",
                "evidence": [{"measure": "fcf_ttm"}],
            },
        }

    patience = int(ctx["values"]["patience"])
    considered = measure["series"]["points"][-patience:]
    evidence = [
        {"measure": "fcf_ttm", "comparator": "above", "threshold": 0},
        {"value": "patience"},
        {"label": "Dated readings considered", "unit": "count",
         "actual": len(considered)},
        # Cited, never restated. Where the journal cannot say what the
        # account is, the host's own reason is what the screen reads — the
        # scaffold has no sentence of its own to offer about it.
        {"fact": "portfolio.cash"},
        {"fact": "portfolio.account_value"},
    ]
    if ctx["position"]["held"]:
        evidence.append({"fact": "position.weight"})
        evidence.append({"fact": "position.opened"})
    if considered:
        evidence.append({"measure": "fcf_ttm",
                         "at": considered[0]["period_end"]})
    return {
        "state": "scaffold-hold",
        "payload": {},
        "reason": {
            "rule": "always-hold",
            "summary": "The scaffold read the data and holds, which is the "
                       "only thing it does.",
            "evidence": evidence,
            "note": ctx["inputs"].get("journal-note") or None,
        },
    }
