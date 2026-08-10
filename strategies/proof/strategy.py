"""The contract proof. A scaffold, not a strategy.

This bundle exists to prove the host/strategy boundary end to end: it is
discovered, its declaration is read without its logic running, its shipped
default resolves through the chain, and its decision crosses back in the
contract's envelope. It holds whatever it is shown, commits nothing, and
carries no view about any security. Delete it the day a real strategy
lands.

What it deliberately touches, so the wiring is exercised and not just
asserted: one measure's current value and dated series, the clock, the one
declared value, the declared inputs, the figures the host can only report
once a journal says what the account is, the host's answer to a comparison,
and one heading over the lot.
"""

from engine import contract

STRATEGY = {
    "id": "contract-proof",
    "name": "Contract proof",
    "summary": "A scaffold that proves the host/strategy boundary carries "
               "data both ways. It reads one measure and always holds; it "
               "is not investment logic and never will be.",
    "version": 4,
    "contract": 5,
    "changelog": {
        1: "First version: reads free cash flow and the clock, and holds.",
        2: "Asks for free cash so the account figures can be proved end to "
           "end, and cites the weight and the account the host works out "
           "from it. Still holds, always.",
        3: "Cites the latest price, so the boundary is proved to carry a "
           "figure's day and its symbol and not just its number. Still "
           "holds, always.",
        4: "Speaks contract 5: asks the host how its one comparison came "
           "out rather than working it out itself, gathers its citations "
           "under a heading, cites the months-held figure, and says where "
           "its one declared value came from. Still holds, always.",
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
         # There is no outside source for a number a scaffold made up, and
         # saying so is the honest answer rather than an omission. A value
         # with nothing behind it is exactly the case the field exists to
         # make visible.
         "source": {"name": "the scaffold itself — it is not investment "
                            "logic and this number decides nothing",
                    "reasoning": True},
         "explain": "How many of the newest dated readings the scaffold "
                    "counts before holding. It changes nothing but the "
                    "sentence in the reason — it exists to prove a shipped "
                    "default can be overridden and seen."},
    ],
}

# One heading, so the boundary is proved to carry a rollup as well as rows.
# `noted`, because the scaffold demands nothing of anything: it holds either
# way, and a group claiming a requirement it does not have would be the
# scaffold pretending to be a strategy.
READINGS = {"id": "readings", "name": "What the scaffold read",
            "requires": "noted"}

POSITIVE = {"measure": "fcf_ttm", "comparator": "above", "threshold": 0,
            "group": READINGS["id"]}


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
    # Asked of the host, not worked out here — the scaffold does nothing
    # with the answer except prove the boundary carries it, which is the
    # point of a scaffold.
    positive = contract.test(ctx, POSITIVE)
    evidence = [
        POSITIVE,
        {"value": "patience", "group": READINGS["id"]},
        {"label": "Dated readings considered", "unit": "count",
         "actual": len(considered), "group": READINGS["id"]},
        # Cited, never restated. Where the journal cannot say what the
        # account is, the host's own reason is what the screen reads — the
        # scaffold has no sentence of its own to offer about it.
        {"fact": "portfolio.cash", "group": READINGS["id"]},
        {"fact": "portfolio.account_value", "group": READINGS["id"]},
        # A price is a figure about one instrument on one day, and citing it
        # has to carry both — a company's share classes trade at different
        # prices, so a number with no symbol behind it cannot be checked.
        {"fact": "price.latest", "group": READINGS["id"]},
    ]
    if ctx["position"]["held"]:
        evidence.append({"fact": "position.weight",
                         "group": READINGS["id"]})
        evidence.append({"fact": "position.opened",
                         "group": READINGS["id"]})
        evidence.append({"fact": "position.months_held",
                         "group": READINGS["id"]})
    if considered:
        evidence.append({"measure": "fcf_ttm",
                         "at": considered[0]["period_end"],
                         "group": READINGS["id"]})
    return {
        "state": "scaffold-hold",
        "payload": {},
        "reason": {
            "rule": "always-hold",
            "summary": "The scaffold read the data and holds, which is the "
                       f"only thing it does. Free cash flow came out "
                       f"{positive} against zero, and nothing follows from "
                       "that here.",
            "evidence": evidence,
            "groups": [READINGS],
            "note": ctx["inputs"].get("journal-note") or None,
        },
    }
