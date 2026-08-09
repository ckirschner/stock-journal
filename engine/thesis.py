"""The thesis — why you own this, and what would prove you wrong.

Everything else in this journal is measured against it. An override is
overriding *the thesis*; an exit is the thesis breaking or paying off; a
falsifier is the one part of it written to be checked. A thesis that can be
edited after the fact makes every one of those unfalsifiable — you cannot
grade a prediction against a version of it revised once the answer was
known.

So it is not a field. It is a living document with amendments, appended and
dated like everything else the user supplies, and the version in force on a
day is the newest one written by then. A falsifier quietly rewritten the
week before it was about to fire is the most diagnostic event a journal can
capture, and the only way to capture it is to make the rewrite an entry
rather than an overwrite.

**It belongs to the position, not to a purchase.** One document per
security, amended as the holding teaches you something, and every purchase
freezes the version that was standing when it was made. That is the
opposite of the valuation claim beside it, which belongs to a specific buy
and does not carry forward — because "why I own this" survives adding to a
holding, and "what I thought it was worth at $40" does not.

**An amendment says why; a first statement does not.** There is nothing to
explain the first time you write down what you believe. There is something
to explain every time after, and it is the same argument principle 3 makes
about a strategy's declared values: a rule you can quietly retune is not a
rule, and the retuning always happens at the moment it is most tempting. A
correction to a fact needs no defence — it has a right answer and moving
toward it is good. A commitment has no right answer, so changing one is a
decision, and a decision this journal records is a decision it records the
reason for.

Storage, on the security, oldest first::

    "thesis": [{"seq", "thesis", "falsifier", "reason", "recorded"}]

Each entry holds the *whole* document, never a diff. An amendment has to be
legible on its own — beside a purchase it qualified, in a list of every
thesis rewritten in the month before an exit — and a diff only means
anything sitting next to its neighbour.
"""

from __future__ import annotations

from . import dated
from . import portfolio

KEY = "thesis"

_BELONGS_TO_AN_EARLIER_HOLDING = (
    "this was last amended on {when}, while you still owned this from an "
    "earlier holding that closed on {closed} — it was written about that "
    "decision, not the one you hold now")

_NOTHING_TO_RECORD = (
    "Write down what you believe about this business, or what would prove "
    "you wrong, or both. An empty thesis is the same as no thesis, and "
    "recording one says you have written something when you have not.")

_AMENDMENT_NEEDS_A_REASON = (
    "Say why it changed. There is already a thesis on record and this "
    "replaces it as the standing one — both stay readable, and months from "
    "now the useful question is not what you now believe but what made you "
    "stop believing the other thing. A first thesis needs no reason; an "
    "amendment is a decision, and this journal records the reason for a "
    "decision.")


def _clean(value) -> str:
    return str(value or "").strip()


# -- reading the record -------------------------------------------------------

def history(security: dict) -> list:
    """Every version ever written, newest first."""
    return dated.history(security, KEY)


def in_force(security: dict, as_of: str | None = None) -> dict | None:
    """The version that stood on a given day, or None.

    A purchase backdated to before the thesis was written sees nothing,
    which is the honest answer: you had not written one. It never sees the
    version you wrote afterwards.
    """
    return dated.in_force(security, KEY, as_of=as_of)


def standing(security: dict, as_of: str | None = None,
             today: str | None = None) -> dict:
    """The version in force, with anything qualifying it — or absent with
    the reason there is none.

    `today` is the clock the holding history is read against, so a pinned
    reading asks whether the thesis belonged to a holding that had already
    closed *by that day* rather than by this one.
    """
    version = in_force(security, as_of)
    if version is None:
        earliest = dated.first(security, KEY)
        if earliest is not None:
            return {"status": "absent",
                    "reason": f"you first wrote a thesis on "
                              f"{dated.day_of(earliest)}, after {as_of} — "
                              "nothing was on record then"}
        return {"status": "absent",
                "reason": "no thesis is written for this security yet"}

    when = dated.day_of(version)
    cautions = []
    # A name bought back inherits the thesis written about the last time you
    # owned it, which is a different decision. It is not withheld — the
    # user's own words are the best the journal has — but it never passes
    # itself off as having been written about the holding in front of you.
    closed = portfolio.last_exit(security, today)
    if closed and when <= str(closed):
        cautions.append(_BELONGS_TO_AN_EARLIER_HOLDING.format(
            when=when, closed=closed))
    return {"status": "known", "version": version, "amended": when,
            "cautions": cautions,
            "amendments": max(len(security.get(KEY) or []) - 1, 0)}


# -- writing to it ------------------------------------------------------------

def amend(security: dict, thesis: str, falsifier: str,
          reason: str = "") -> dict | None:
    """Append one version of the document. Never edits, never replaces.

    Returns None where nothing changed, so opening the dialog and pressing
    save does not fill the record with identical versions — a history that
    has to be waded through is a history nobody reads, and the amendment
    that matters is the one you can find.
    """
    thesis, falsifier = _clean(thesis), _clean(falsifier)
    reason = _clean(reason)
    if not thesis and not falsifier:
        raise ValueError(_NOTHING_TO_RECORD)

    current = in_force(security)
    if current is not None:
        if (_clean(current.get("thesis")) == thesis
                and _clean(current.get("falsifier")) == falsifier):
            return None
        if not reason:
            raise ValueError(_AMENDMENT_NEEDS_A_REASON)

    return dated.append(security, KEY, {
        "thesis": thesis, "falsifier": falsifier,
        # Empty on a first statement, and empty for no other reason: the
        # amendment path refuses a blank one above, so a blank here always
        # means "there was nothing to amend" rather than "they did not say".
        "reason": reason if current is not None else "",
    })
