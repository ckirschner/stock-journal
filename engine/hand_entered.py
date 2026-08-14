"""Numbers the user read off a document this program could not.

Not every figure a strategy asks for can be computed. A filing this host
does not parse, a company whose XBRL is a mess, a measure with no data
source ingested at all — in each case the user can read the number off the
page themselves, and typing it in is the difference between a journal that
works and one that reports absence for everything.

They participate in a reconstruction, and they have to. Excluding them
would rebuild every manually-sourced security as "bought with no signal at
all" and manufacture an override on a purchase that had one. But until now
they carried no date, which meant a figure typed today was served to a
verdict rebuilt for 2024 — labelled undated, which is honest about what it
is and silent about the thing that matters: the number may have been typed
*because of* what happened afterwards.

So they are dated, on the same record as everything else the user supplies.
A purchase backdated to 2024 sees the value that was on record in 2024, or
nothing. Dating them is what makes including them honest.

**Clearing a value is an entry, not a deletion.** Blanking a field records
that you withdrew the figure on the day you withdrew it; the computed value
underneath becomes visible again, exactly as it did before, and the number
you no longer stand behind stays legible in the history. A record that can
be emptied is a record that can be emptied at the convenient moment.

**A withdrawn value can never be served as a value.** The entry holds None,
and nothing that builds a known value can see it — `values` returns only
entries that hold a figure. That is structural rather than careful: a zero
or a `None` presented as a known measure is principle 4's exact failure
mode, and the way to prevent it is for the absent case to be unreachable
from the reading path, not for every reader to remember to check.

**A judgement can never land here.** This field takes numbers, and
`float(True)` is 1.0 — a moat read typed into it would become a
measurement, which is the one thing principle 5 says a captured assessment
must never look like. Refused at the write, and unreadable even if a
journal written before that refusal holds one.

Storage, on the security, oldest first::

    "hand_entered": [{"seq", "id", "value", "recorded"}]   # value None: withdrawn
"""

from __future__ import annotations

from . import bank as bank_mod
from . import dated
from . import judgements

KEY = "hand_entered"

ENTERED = "entered by hand on {day}"
WITHDREW = ("you cleared the hand-entered value on {day}, and nothing is "
            "computed for it")
NOT_YET = ("you first entered this by hand on {first}, after {day} — "
           "nothing was on record then")


# -- reading the record -------------------------------------------------------

def history(security: dict, entry_id: str | None = None) -> list:
    """Every value ever entered for one measure, or for all of them, newest
    first — withdrawals included, since withdrawing a figure is part of what
    the user did about it."""
    return dated.history(security, KEY, entry_id)


def ids(security: dict) -> list:
    """Every measure ever entered by hand, in the order first entered,
    including ones since withdrawn.

    Withdrawn ids belong here. This is what keeps a measure on screen after
    the strategy stops reading it, and dropping the withdrawn ones would
    make a value's own history unreachable the moment you cleared it.
    """
    out = []
    for entry in reversed(history(security)):
        eid = entry.get("id")
        if eid and eid not in out:
            out.append(eid)
    return out


def in_force(security: dict, entry_id: str, as_of: str | None = None):
    """The entry that stood for this measure on a given day, or None. May be
    a withdrawal — callers wanting a figure want `values`."""
    return dated.in_force(security, KEY, entry_id, as_of)


def reading(security: dict, entry_id: str, as_of: str | None = None) -> dict:
    """One hand-entered figure as every reader serves it: known with its
    provenance, or absent with the reason.

    Source-neutral on purpose. The strategy's context and the snapshot merge
    both build their own shape from this, so the sentence explaining a value
    is written once and the two of them cannot drift into disagreeing about
    the same figure.
    """
    if judgements.is_judgement(entry_id):
        return {"status": "absent",
                "reason": "this is a judgement you make, not a number — it "
                          "is answered on its own record"}
    entry = in_force(security, entry_id, as_of)
    if entry is None:
        earliest = dated.first(security, KEY, entry_id)
        if earliest is not None:
            return {"status": "absent",
                    "reason": NOT_YET.format(first=dated.day_of(earliest),
                                             day=as_of)}
        return {"status": "absent",
                "reason": "no value has been entered by hand for this"}
    if entry.get("value") is None:
        return {"status": "absent",
                "reason": WITHDREW.format(day=dated.day_of(entry))}
    return {"status": "known", "value": entry["value"],
            "recorded": dated.day_of(entry), "cautions": [],
            "provenance": [ENTERED.format(day=dated.day_of(entry))]}


def values(security: dict, as_of: str | None = None) -> dict:
    """{measure id: reading} for every measure holding a figure on that day.

    Only figures. A withdrawal and a value not yet entered are both absent,
    and neither reaches this dict — so no caller can overlay one onto a
    computed value and turn "you took this back" into a confident answer.
    """
    out = {}
    for eid in ids(security):
        r = reading(security, eid, as_of)
        if r["status"] == "known":
            out[eid] = r
    return out


# -- writing to it ------------------------------------------------------------

def checked(entry_id: str, value):
    """The figure this value would be recorded as, or a refusal.

    Separate from the append so a caller writing several at once can refuse
    the whole set before any of it lands. An append-only record has no way
    to take an entry back, so "half the fields were written and then it
    failed" is not a state it can be got out of — it has to be a state that
    cannot be reached.
    """
    if entry_id not in bank_mod.meta():
        # A measure the bank no longer defines may be CLEARED and never set.
        # Refusing both left the one case that matters unreachable: a figure
        # typed under an entry somebody later deleted goes on being served
        # into every new frozen snapshot, and the only control that could take
        # it back was refused on the grounds that the measure does not exist.
        # Withdrawing it is precisely the thing that is still meaningful about
        # a measure that does not exist.
        if value in (None, "", "—"):
            return None
        raise ValueError(
            f'"{entry_id}" is not in the metric bank. A value already '
            "recorded for it can be cleared, but a new one cannot be entered "
            "against a measure nothing defines.")
    if judgements.is_judgement(entry_id):
        raise ValueError(
            f'"{entry_id}" is a judgement you make about this security, not '
            "a number to type. Answer it in Judgements, in prose with a pass "
            "or a fail, and it goes on a dated record that is never "
            "overwritten.")
    if value in (None, "", "—"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{entry_id} must be a number or left blank.")


def record(security: dict, entry_id: str, value) -> dict | None:
    """Append one hand-entered value, or a withdrawal where value is blank.

    Returns None where nothing changed. The values dialog posts every field
    it offered on every save, so an unconditional append would turn five
    visits to that screen into five identical entries and bury the one
    revision worth finding.
    """
    figure = checked(entry_id, value)

    current = in_force(security, entry_id)
    if current is not None and current.get("value") == figure:
        return None
    # Nothing to withdraw is not a withdrawal. Without this, a blank field
    # that was always blank appends an entry saying the user cleared
    # something they never entered.
    if figure is None and (current is None or current.get("value") is None):
        return None

    return dated.append(security, KEY, {"id": entry_id, "value": figure,
                                        **entered_as(entry_id, current)})


# What the bank said this measure WAS, on the day the figure was typed. The
# same freeze the citation subject already makes, on the other record the user
# writes — and the same defect it was made against, reproduced here exactly: a
# 10.4 entered as a multiple prints as "10.4%" after somebody corrects the
# unit, because the row is rendered from `bank.meta()` taken this render.
#
# Whose figure it is decides which words are right. A number the user typed
# was typed under a label, a unit and a format, and the entry is dated and
# never edited — so re-rendering it under today's is the record answering a
# question it was not asked.
#
# It matters more than the judgement case because the row is also the only
# way to WITHDRAW the figure. Deleting the bank entry used to drop the row
# from the values dialog entirely, and the figure went on being served into
# every new frozen snapshot from a record the user could no longer see or
# reach — which is the one shape of this that is not merely a display
# problem.
def entered_as(entry_id: str, previous: dict | None = None) -> dict:
    """The bank's rendering words for one measure, as they stand now.

    `previous` is the entry standing before this one, and it is used only
    where the bank no longer defines the measure at all — a withdrawal, since
    nothing else can be written then. Carrying its words forward keeps the
    clearing row readable beside the figure it clears; taking today's blank
    would make the last entry on the record the one that says least.
    """
    m = bank_mod.meta().get(entry_id)
    if m is None:
        return {k: (previous or {}).get(k)
                for k in ("label", "unit", "format", "plain")} \
            if isinstance(previous, dict) else {}
    return {"label": m.get("label") or entry_id, "unit": m.get("unit"),
            "format": m.get("format"), "plain": m.get("plain")}


def shown_as(entry: dict | None, live: dict | None, entry_id: str) -> dict:
    """How to print a hand-entered figure: the words frozen onto it where it
    carries them, the live bank only where it does not.

    Presence of the KEY decides, never truthiness. `format: None` is the bank
    declaring none — a yes/no carries no format and running one through a
    format prints a 1 — and it must not fall through to whatever the file
    says today. A record with no `label` key at all predates this.
    """
    out = {"label": entry_id, "unit": None, "format": None, "plain": None}
    out.update({k: v for k, v in (live or {}).items() if k in out})
    for field in ("label", "unit", "format", "plain"):
        if isinstance(entry, dict) and field in entry:
            out[field] = entry[field]
    out["id"] = entry_id
    out["withdrawn"] = live is None
    return out
