"""Judgements — the questions no filing can answer, answered per security.

Most of what a value investor actually decides on is not in the numbers.
Whether a moat holds for another decade, whether management has told the
truth when the news was bad, whether spare cash has gone somewhere worth
more than paying it out: none of it is recoverable from XBRL, all of it is
per security, and until now there was nowhere in the program to put it.

**The question lives with the definition that explains it.** A qualitative
bank entry already states the question, what a good answer looks for, where
it misfires and whose idea it was — everything someone who has never
assessed a moat needs in order to answer one. So the bank entry carries the
answering surface too, and a strategy reaches it the way it reaches every
other measure: it cites `{"measure": "moat_durability"}` and the host
answers. No new citation vocabulary, no second place a question can be
defined, and no way for two strategies to ask the same question differently.

**An answer is a judgement, never a measurement, and it is made to look
like one structurally rather than by convention.** The host decides an
evidence item's kind from the bank, not from the strategy, so a strategy
cannot present an assessment as something the tool computed. The value it
carries is the user's mark; the reasoning they wrote travels with it.

**The record is append-only and dated.** An assessment quietly rewritten at
the moment it is about to matter is the most diagnostic thing a journal
could capture, and a mutable slot captures none of it. A revision is a new
entry; nothing is ever edited. Because every entry carries the day it was
written:

  - a reconstructed evaluation sees the assessment that was on record then,
    or nothing at all where none was — a backdated purchase never inherits
    an opinion formed afterwards;
  - an assessment written before the holding you have now carries a caution
    saying so, because buying a name back does not renew a judgement made
    about a different decision.

**Absence is never a pass.** An unanswered question is absent with its
reason, and the contract's own arithmetic turns absence into `unknown`. What
a strategy does about that is the strategy's business — the host holds no
view on whether a missing moat read should stop a verdict.

Storage, on the security, oldest first::

    "judgements": [{"seq", "id", "mark": "pass"|"fail",
                    "reasoning", "recorded"}]
"""

from __future__ import annotations

from . import bank as bank_mod
from . import dated
from . import portfolio

KEY = "judgements"

# The marks this host can record. A bank entry asking for anything else is
# not served — the shape of an answer is something the host has to
# understand to store it, and a scored assessment is a host change, not
# something to guess at. Stated once here, checked against the bank.
MARKS = ("pass", "fail")

# What the mark means as a figure a strategy can test. Pass/fail is yes/no,
# so a rule reads `{"measure": "moat_durability", "comparator": "equals",
# "threshold": True}` and gets the same arithmetic every other comparison
# gets — including the part where an unanswered one can never come out
# as success.
_AS_VALUE = {"pass": True, "fail": False}

_BELONGS_TO_AN_EARLIER_HOLDING = (
    "this assessment was written on {when}, while you still owned this from "
    "an earlier holding that closed on {closed} — it was written about that "
    "decision, not the one you hold now")


# -- what the bank asks -------------------------------------------------------

_cache: dict = {}
_cached_doc = None


def _entries() -> dict:
    """{entry id: plain entry} for every qualitative bank entry.

    Held against the bank document itself rather than rebuilt per call:
    `is_judgement` is asked once per stored value per security on every
    render, and `load_bank` caches on the file's mtime and hands back the
    same document until it moves — so an edit to the bank still takes
    effect, and a render does not rescan sixty entries a hundred times.
    """
    global _cached_doc
    doc = bank_mod.load_bank()
    if doc is not _cached_doc:
        _cached_doc = doc
        _cache.clear()
        _cache.update({str(e.get("id")): bank_mod.to_plain(e)
                       for e in (doc.get("entries") or [])
                       if str(e.get("kind") or "") == "qualitative"})
    return _cache


def unanswerable(entry: dict) -> str | None:
    """None where this host can serve the entry, else one sentence saying
    why it cannot.

    A bank entry says what shape an answer takes. Where that shape is not
    one this host understands, the measure reports absent with this reason
    rather than being stored in a shape nothing can read back — a silently
    unstorable question is worse than one that says it is not supported.
    """
    marks = [str(m) for m in ((entry.get("response") or {}).get("marks") or [])]
    if marks != list(MARKS):
        asked = ", ".join(marks) or "in a way the bank does not state"
        return (f"this journal records a pass or a fail, and this question "
                f"asks to be marked {asked} — supporting that is a change to "
                "the host, not something to approximate")
    return None


def questions() -> dict:
    """{entry id: {label, question, plain, marks, unsupported}} for every
    qualitative bank entry, in bank order. What a screen needs to ask one."""
    out = {}
    for eid, e in _entries().items():
        out[eid] = {
            "id": eid,
            "label": str(e.get("label") or eid),
            "question": str(e.get("question") or "").strip(),
            "plain": ((e.get("explanation") or {}).get("plain") or "").strip(),
            "marks": list(MARKS),
            "unsupported": unanswerable(e),
        }
    return out


def is_judgement(entry_id: str) -> bool:
    return entry_id in _entries()


# -- reading the record -------------------------------------------------------

def history(security: dict, entry_id: str | None = None) -> list:
    """Every assessment on record, newest first. Nothing is ever removed
    from it, so a revision reads as what it is: an earlier answer, and the
    day the user changed their mind."""
    return dated.history(security, KEY, entry_id)


def in_force(security: dict, entry_id: str, as_of: str | None = None):
    """The assessment that stood on a given day, or None.

    The clock governs this exactly as it governs filings and prices: an
    evaluation reconstructed for a past date sees what was written by then
    and nothing later. An opinion formed after a purchase is not evidence
    about that purchase, however true it turned out to be.
    """
    return dated.in_force(security, KEY, entry_id, as_of)


def observation(security: dict, entry_id: str, entry: dict,
                as_of: str | None = None,
                last_exit: str | None = None) -> dict:
    """One judgement as the context serves it: known with its mark, its
    reasoning and anything qualifying it, or absent with the reason."""
    unsupported = unanswerable(entry)
    if unsupported:
        return {"status": "absent", "reason": unsupported}

    answer = in_force(security, entry_id, as_of)
    if answer is None:
        later = history(security, entry_id)
        if later:
            first = dated.day_of(later[-1])
            return {"status": "absent",
                    "reason": f"you first assessed this on {first}, after "
                              f"{as_of} — nothing was on record then"}
        return {"status": "absent",
                "reason": "assessed by you, not computed — nothing is "
                          "recorded in this journal yet"}

    when = dated.day_of(answer)
    cautions = []
    # A name bought back inherits the assessment written about the last time
    # you owned it, which is a different decision. It is not withheld — the
    # user's own opinion is the best the journal has — but it never passes
    # itself off as having been written about the holding in front of you.
    if last_exit and when <= str(last_exit):
        cautions.append(_BELONGS_TO_AN_EARLIER_HOLDING.format(
            when=when, closed=last_exit))
    return {
        "status": "known",
        "value": _AS_VALUE[answer["mark"]],
        "source": "judgement",
        "cautions": cautions,
        "provenance": [f"your assessment of {when}",
                       str(answer.get("reasoning") or "").strip()],
    }


def observations(security: dict, as_of: str | None = None,
                 today: str | None = None) -> dict:
    """{entry id: known-or-absent} for every qualitative bank entry.

    `today` is the clock the holding history is read against, so a pinned
    evaluation asks whether the assessment belonged to a holding that had
    already closed *by that day* rather than by this one.
    """
    last_exit = portfolio.last_exit(security, today)
    return {eid: observation(security, eid, entry, as_of, last_exit)
            for eid, entry in _entries().items()}


# -- writing to it ------------------------------------------------------------

def assess(security: dict, entry_id: str, mark: str, reasoning: str) -> dict:
    """Append one assessment. Never edits, never replaces.

    Reasoning is required, because the mark on its own teaches nothing and
    this record exists to be read back years later against what happened.
    That is the same reason nothing here is editable: an answer improved
    after the fact cannot be measured against anything.
    """
    entry = _entries().get(entry_id)
    if entry is None:
        raise ValueError(
            f'"{entry_id}" is not a question in the metric bank. The '
            "questions you answer are the bank's qualitative entries; a new "
            "one is a change to the bank.")
    unsupported = unanswerable(entry)
    if unsupported:
        raise ValueError(f'"{entry.get("label") or entry_id}": {unsupported}.')
    if mark not in MARKS:
        raise ValueError(
            f'An assessment is marked {" or ".join(MARKS)}. "{mark}" is '
            "neither — and leaving it unmarked is not a third answer to "
            "record, it is simply not answering yet.")
    reasoning = (reasoning or "").strip()
    if not reasoning:
        raise ValueError(
            "Write down your reasoning. A pass with nothing behind it cannot "
            "be checked against what happened, which is the only thing this "
            "record is for.")

    return dated.append(security, KEY, {"id": entry_id, "mark": mark,
                                        "reasoning": reasoning})
