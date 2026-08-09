"""The valuation claim — what you thought it was worth, and on what.

A valuation is a claim about a specific moment. Its assumptions were formed
against a price, a filing and a mood that all move, so "the expected value
of this position" is not a thing that exists: there is the claim you made
when you bought at $40 and the claim you made when you added at $61, and
averaging them produces a number no decision was ever made on.

**So a claim belongs to the purchase it justified, not to the position.**
The log below is the working record — every claim ever made about the
security, including the ones that talked you out of buying, which are the
most instructive entries in it and would be lost entirely if a claim only
existed once a purchase attached to it. A purchase then freezes the claim
that was standing on its day, and that frozen copy is the one that is ever
read beside a lot. Nothing anywhere takes a *list* of claims and reduces
it, and nothing should.

**A claim needs no reason field, and that is not an inconsistency.** The
record next to this one — the thesis — requires a reason for every
amendment, because prose replacing prose says nothing about why. A claim
carries its entire reasoning already: the assumptions are the argument, and
principle 5 exists precisely so that when the estimate turns out wrong you
can see *which assumption* was wrong. Asking for a sentence on top would be
asking someone to restate in prose what the inputs already say exactly.

**A claim that does not solve never lands.** The result is computed before
the entry is appended, so the record cannot hold assumptions that produce
no number. What is stored is the assumptions, never the answer — except in
the frozen copy on a lot, where the answer *is* stored, because a purchase
records what was on screen that day and a later change to how a DCF is
computed must not restate a decision made in 2024.

Storage, on the security, oldest first::

    "valuations": [{"seq", "method", "inputs", "sources", "recorded"}]
"""

from __future__ import annotations

from . import dated
from . import expected_value
from . import portfolio

KEY = "valuations"

_BELONGS_TO_AN_EARLIER_HOLDING = (
    "this valuation was made on {when}, while you still owned this from an "
    "earlier holding that closed on {closed} — it was the case for that "
    "purchase, not for the one you hold now")


# -- reading the record -------------------------------------------------------

def history(security: dict) -> list:
    """Every claim ever made, newest first."""
    return dated.history(security, KEY)


def in_force(security: dict, as_of: str | None = None) -> dict | None:
    """The claim that stood on a given day, or None. A purchase backdated to
    before you valued the business sees nothing, never the claim you made
    afterwards."""
    return dated.in_force(security, KEY, as_of=as_of)


def result_of(entry: dict | None) -> dict | None:
    """The number the claim's assumptions solve to, or None where they no
    longer solve at all. Derived on read for a live claim — never stored,
    because a stored answer is a second opinion about something the
    assumptions already settle."""
    if not entry:
        return None
    try:
        return expected_value.compute(entry["method"], entry.get("inputs") or {})
    except (expected_value.EVError, KeyError):
        return None


def frozen(entry: dict | None) -> dict | None:
    """The claim as a purchase records it: the assumptions *and* the answer
    they gave that day.

    The one place a computed value is written down rather than derived. A
    lot is a record of what was on screen when a decision was made, and
    re-deriving it years later through whatever the code has become would
    let a refactor restate a purchase — which principle 3 forbids outright.
    """
    if not entry:
        return None
    return {**entry, "result": result_of(entry)}


def standing(security: dict, as_of: str | None = None,
             today: str | None = None) -> dict:
    """The claim in force with anything qualifying it, or absent with the
    reason there is none."""
    claim = in_force(security, as_of)
    if claim is None:
        earliest = dated.first(security, KEY)
        if earliest is not None:
            return {"status": "absent",
                    "reason": f"you first valued this on "
                              f"{dated.day_of(earliest)}, after {as_of} — "
                              "nothing was on record then"}
        return {"status": "absent",
                "reason": "this security has not been valued in this journal"}

    when = dated.day_of(claim)
    cautions = []
    closed = portfolio.last_exit(security, today)
    if closed and when <= str(closed):
        cautions.append(_BELONGS_TO_AN_EARLIER_HOLDING.format(
            when=when, closed=closed))
    return {"status": "known", "claim": claim, "made": when,
            "result": result_of(claim), "cautions": cautions,
            "earlier": max(len(security.get(KEY) or []) - 1, 0)}


# -- writing to it ------------------------------------------------------------

def claim(security: dict, method: str, inputs: dict,
          sources: dict | None = None) -> tuple[dict | None, dict]:
    """Append one valuation and return (entry, result).

    The entry is None where this claim is identical to the standing one —
    re-running the same assumptions is not a new claim about anything, and
    an unreadable history is a history nobody consults. The result comes
    back either way, because the dialog has to paint.
    """
    if method not in expected_value.EV_METHODS:
        raise expected_value.EVError(f"Unknown method: {method}")
    inputs = dict(inputs or {})
    # Solved before it is stored, so the record can never hold a claim that
    # produces nothing. The error the user sees is the calculator's own.
    result = expected_value.compute(method, inputs)

    payload = {"method": method, "inputs": inputs,
               "sources": _sources_for(method, sources)}
    current = in_force(security)
    # Compared whole, sources included. The assumptions are the claim, so
    # identical numbers are usually the same claim — but where the same
    # number now comes from a filing rather than from the user's typing, the
    # record of what the claim rested on has genuinely changed, and an
    # append-only record cannot go back and correct a stale provenance.
    # Appending is the only honest way to say it.
    if current is not None and all(current.get(k) == payload[k]
                                   for k in payload):
        return None, result
    return dated.append(security, KEY, payload), result


def _sources_for(method: str, sources) -> dict:
    """Where each assumption came from — fetched, computed, overridden or
    typed against absence — kept only for inputs the method actually
    declares, so a stale key from a previous method cannot ride along.

    A source carries its cautions as well as its provenance. A free cash
    flow prefilled from a debt line that folds in finance leases is that
    kind of number in the claim built on it, and a record that kept where a
    figure came from while dropping what was wrong with it would state the
    claim as more certain than it was.
    """
    if not isinstance(sources, dict):
        return {}
    declared = {k for k, _label, _help
                in expected_value.EV_METHODS.get(method, {}).get("inputs", [])}
    return {k: v for k, v in sources.items()
            if k in declared and isinstance(v, dict)}
