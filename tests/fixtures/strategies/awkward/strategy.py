"""A fixture that asks for everything difficult a declaration can express.

Invented content, and deliberately not a sensible strategy: a sensible one
declares two tidy fields and proves nothing about the parts of the contract
that only bend under load. This one exists so the input declaration is
exercised where it is awkward — a role the host reports as a figure, a
question gated on another question gated on a third, a bound that names a
different field, a fixed set of answers, and an optional field measured
against a declared value rather than a literal.

It is also the first fixture that *binds on size*: it reads position weight
against its own cap and returns a state either side of it. That could not be
written at all until a journal could say what the account is, which is the
whole point of exercising it here rather than asserting it in prose.

Nothing here is investment logic. A percentage cap picked out of the air is
not a reason to buy or sell anything.
"""

STRATEGY = {
    "id": "awkward",
    "name": "Awkward fixture",
    "summary": "A test fixture that sizes positions against the account and "
               "asks every awkward question a declaration can ask. It is "
               "not investment logic.",
    "version": 1,
    "contract": 4,
    "changelog": {
        1: "First version: sizes against account weight and a cap.",
    },
    "states": [
        {"id": "size-up", "name": "Room to add", "render": "commit",
         "description": "The position sits under the cap, so there is room "
                        "in the account for more of it."},
        {"id": "size-down", "name": "Over the cap", "render": "reduce",
         "description": "The position has grown past the share of the "
                        "account this fixture allows it."},
        {"id": "sit", "name": "Sized right", "render": "hold",
         "description": "The position is where the cap wants it, so there "
                        "is nothing to do."},
        {"id": "paused", "name": "You paused this journal", "render": "blocked",
         "description": "You said you are not opening positions right now, "
                        "so the fixture will not propose one."},
        {"id": "no-account", "name": "Nothing to measure against",
         "render": "unknown",
         "description": "The share of the account this position takes up "
                        "cannot be worked out, so a rule about size has "
                        "nothing to read."},
    ],
    "inputs": [
        # The one input the host reports back as a figure. No strategy could
        # ship a default for someone's cash, and the host has no field of
        # its own to put it in — the role is how the two meet.
        {"id": "free-cash", "label": "Free cash", "type": "number",
         "unit": "usd", "role": "cash", "required": True,
         "explain": "Money sitting in the account that is not in any "
                    "position. It is what the account is worth on top of "
                    "the holdings, and every share-of-the-account figure "
                    "here is measured against that total."},
        # A fixed set of answers: free text would push the checking into
        # decide(), which fails at evaluation instead of while the user is
        # looking at the field.
        {"id": "stance", "label": "How you are trading right now",
         "type": "text", "required": True,
         "options": [{"value": "building", "label": "Building positions"},
                     {"value": "trimming", "label": "Trimming — selling down"},
                     {"value": "paused", "label": "Paused — not adding"}],
         "explain": "Whether you are putting money to work at the moment. "
                    "Choosing paused stops this fixture proposing anything "
                    "new; it says nothing about what you already hold."},
        # Gated on ANY of several answers above, and itself the gate for the
        # next one. A reserve means something whether you are buying or
        # selling down and nothing at all while paused — which a single
        # equality test could not say.
        {"id": "keeps-reserve", "label": "Do you keep cash back?",
         "type": "boolean",
         "when": {"input": "stance", "is": ["building", "trimming"]},
         "explain": "Whether you deliberately hold some cash rather than "
                    "putting all of it into positions. Answer no and "
                    "nothing below is asked."},
        {"id": "reserve", "label": "Cash you keep back", "type": "number",
         "unit": "usd", "min": 0, "max_from": "free-cash", "required": True,
         "when": {"input": "keeps-reserve", "is": True},
         "explain": "The amount you will not spend. It cannot be more than "
                    "the cash you have, because a floor above the balance "
                    "would stop every purchase forever."},
        # Optional, and bounded by a declared value rather than a literal.
        {"id": "first-buy", "label": "Size of a first position",
         "type": "number", "unit": "percent", "min": 0.1,
         "max_from": "cap",
         "explain": "How much of the account a brand-new position starts "
                    "at, as a percentage. Left blank it starts at the cap. "
                    "It can never be more than the cap, because that would "
                    "be over the limit on day one."},
    ],
    "values": [
        {"id": "cap", "label": "Largest a position may get", "type": "number",
         "unit": "percent", "min": 0.1, "max": 100,
         "explain": "The most of the account this fixture will let one "
                    "position take up, as a percentage. It is an opinion "
                    "about concentration, which is why it ships a default "
                    "rather than being asked for."},
    ],
}


def _reason(rule, summary, evidence, note=None):
    return {"rule": rule, "summary": summary, "evidence": evidence,
            "note": note}


def decide(ctx):
    cap = float(ctx["values"]["cap"])
    position, folio = ctx["position"], ctx["portfolio"]
    cash_cite = {"fact": "portfolio.cash"}
    cap_cite = {"value": "cap"}

    if not position["held"]:
        if ctx["inputs"].get("stance") == "paused":
            return {
                "state": "paused",
                "payload": {"needs": ["You said you are paused. Change that "
                                      "in this journal's settings and the "
                                      "fixture will size a first position."]},
                "reason": _reason(
                    "paused-by-you",
                    "Nothing is proposed while this journal is paused.",
                    [{"input": "stance"}]),
            }
        reserve = ctx["inputs"].get("reserve")
        # The limit is named, never restated: the host reads "reserve" out of
        # this journal's own answers. Cited unconditionally, because a
        # reserve nobody answered is a limit the host reports as unset rather
        # than a test that quietly disappears from the reason.
        evidence = [{"fact": "portfolio.cash", "comparator": "at_least",
                     "threshold_from": "reserve"},
                    cap_cite]
        first = ctx["inputs"].get("first-buy")
        if first is not None:
            evidence.append({"input": "first-buy"})
        cash = folio["cash"]
        if reserve is not None and (cash["status"] != "known"
                                    or cash["value"] < float(reserve)):
            return {
                "state": "sit", "payload": {},
                "reason": _reason(
                    "reserve-comes-first",
                    "Free cash is at or below the reserve you keep back, so "
                    "there is nothing to put to work.", evidence),
            }
        return {
            "state": "size-up",
            "payload": {"size": {"unit": "weight",
                                 "value": float(first) if first is not None
                                 else cap},
                        "condition": None},
            "reason": _reason(
                "open-at-the-starting-size",
                "Nothing is held yet, so the fixture opens at its starting "
                "size.", evidence),
        }

    weight = position["weight"]
    evidence = [{"fact": "position.weight", "comparator": "at_most",
                 "threshold_from": "cap"},
                {"fact": "portfolio.account_value"},
                {"fact": "position.opened"}]
    if weight["status"] != "known":
        return {
            "state": "no-account", "payload": {},
            "reason": _reason(
                "needs-an-account",
                "The share of the account this position takes up cannot be "
                "worked out, so a cap on it has nothing to read.",
                evidence + [cash_cite]),
        }
    if weight["value"] > cap:
        return {
            "state": "size-down",
            "payload": {"to": {"unit": "weight", "value": cap}},
            "reason": _reason(
                "over-the-cap",
                "The position takes up more of the account than the cap "
                "allows.", evidence),
        }
    if weight["value"] == cap:
        return {
            "state": "sit", "payload": {},
            "reason": _reason("at-the-cap",
                              "The position is exactly at its cap.",
                              evidence),
        }
    return {
        "state": "size-up",
        "payload": {"size": {"unit": "weight",
                             "value": round(cap - weight["value"], 6)},
                    "condition": None},
        "reason": _reason(
            "room-under-the-cap",
            "The position is under its cap, so the difference is room to "
            "add.", evidence),
    }
