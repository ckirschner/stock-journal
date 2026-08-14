"""Journals — the collection, and the strategy stamped on each one.

A journal has exactly one strategy and it does not change. Trading two
strategies means two journals, the way it would mean two accounts. So the
strategy is chosen when a journal is created and recorded on it — its
identity, the host contract version it spoke, the version of its logic, the
version of its declared values, and the declared values themselves as they
resolved that day.

**The same is true of what a measure IS.** A strategy says a holding fails
when return on invested capital falls below fifteen percent; the metric bank
says what return on invested capital computes, over how many years, which kinds
of company it refuses to describe. Editing the second changes what every exit
demands just as surely as editing the first, in every journal at once, and it
is a file on the user's machine that this program re-reads whenever its mtime
moves. So a journal stamps those definitions too, and compares them on every
read — see `observe_measure_change`.

Layout, one directory per journal, one file inside it::

    <data>/journals/<id>/journal.json

One file, written atomically, so a crash mid-write can never leave a journal
half-recorded. Journals are *discovered*, not indexed: the host lists what it
finds. There is no central registry to fall out of step with the directory,
and a journal whose file cannot be read is listed with its problem rather
than quietly vanishing.

The document::

    {"schema", "id", "name", "created",
     "strategy": {"id", "name", "contract", "version", "values_version",
                  "values": {id: value}, "stamped"},   # frozen at creation
     "measures": {"version", "entries": {id: definition}, "stamped"},
                                         # frozen at creation
     "config":   {value id: value},      # this journal's override, if any
     "inputs":   {input id: value},      # what the user supplied
     "rule_changes":    [...],           # append-only, see below
     "measure_changes": [...],           # append-only, see below
     "input_changes":   [...],           # append-only, see below
     "settings": {...},                  # valuation defaults
     "securities": [...]}

**The stamp is never rewritten.** It says what this journal was created
against. What it runs under *now* is the strategy on disk, and any distance
between the two is recorded rather than absorbed: `observe_rule_change`
compares the loaded strategy against the newest known state — the last
rule change if there is one, the stamp otherwise — and appends what moved.

Two kinds of move are recorded differently, because the host can honestly say
different things about them. A change to declared *values* is recorded as a
before and after, because the numbers mean something on their own. A change
to a strategy's *logic* cannot be, so the record carries the author's own
changelog line for each version crossed — which is why the loader refuses a
version that does not say what changed.

The case worth naming: values that move while `values_version` does not.
That is a threshold edited in place with nothing to mark it, and it is
exactly the quiet retuning the record exists to prevent. It is detected
anyway, because the stamp holds the resolved values themselves and not just
their version number, and it is reported as the louder case it is.

One thing deliberately *not* recorded: a strategy that is simply not
installed here. That is a fact about this machine, not a change to what the
rules demand — it renders in place on every screen that would otherwise
carry a verdict, and appending it would write one entry per launch into a
record that is supposed to be readable. The moment the strategy is back, any
distance it travelled while away is caught by the same comparison.

**The measure record is the same argument one level down**, and it is kept in
its own list for the reason the two halves of a rule change are recorded
differently: they are not the same shape and one list holding both is one list
that comes apart. A strategy's record moves in whole values; the bank's moves
per measure and per field, because a bank is seventy-four definitions and a
change touching one of them must not read as a change to the file. Both records
answer to one `pending` and one `explain`, because owing a sentence is the same
obligation whichever record it sits on.

**Answers are not rules, and are kept apart.** What the user told the journal
— anything a strategy asks for that the host cannot work out — moves for
ordinary reasons and moves often; putting each edit on the rule-change record
would bury the retunings that record exists to surface. But those answers feed
figures a strategy binds on, so an answer that can be quietly adjusted the
day before a purchase is worth being able to see. They get their own
append-only list: before and after, dated, and no reason ever demanded,
because updating a fact is not a change to what the rules demand.

**Free cash used to be one of those answers and is not any more.** It is
worked out from this journal's own cash record — an opening balance and every
deposit, withdrawal and dividend since, each on the day it moved (engine/
cash.py). What the change buys is the difference between money that arrived
and money that was made, which a single editable figure and a log of its edits
cannot express: the edit from 50,000 to 60,000 could be a deposit or a
correction, and no reading of the record can say which. That is why nothing
converts the old answers into events. The old figure stays on the input-change
record, where it is what it always was — a dated statement of what somebody
typed — and the cash record starts from an opening balance the user states.
"""

from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path

from . import cash, contract, dated, lists, portfolio, secrets, store
from . import strategy_values

# 2: a security's position became append-only lot history and every stored
#    bucket, running total and single entry snapshot went with it. There is
#    no conversion: a journal written against schema 1 says so and is left
#    alone rather than half-read.
SCHEMA = "ledger.journal/2"
DIRNAME = "journals"
FILENAME = "journal.json"
_OPEN_KEY = "open_journal"      # machine-local: which journal is open here


def _now() -> str:
    """When something was observed, on the calendar the user was standing on.

    The same stamp, and the same reasoning, as `dated.stamp` — this record is
    read against days a person typed, so it has to be on the same calendar as
    those days. `answers_on` compares a change's day against a purchase date,
    and a UTC stamp would put an evening's change on tomorrow west of
    Greenwich, so a purchase backdated to that evening would be reconstructed
    against an answer the user had already replaced.

    Entries written before this are UTC and stay UTC. Nothing already on
    record is restated.
    """
    return dated.stamp()


# -- paths and discovery -----------------------------------------------------

def journals_dir() -> Path:
    return store.data_dir() / DIRNAME


def path_for(journal_id: str) -> Path:
    """The file for one journal id.

    The id is a plain folder name and nothing else. It reaches here from a
    journal's own document and from an imported bundle, so anything that
    could climb out of the journals directory — a separator, a parent step,
    a leading dot — is refused rather than sanitised. Silently rewriting a
    hostile name into a harmless one hides that it was sent at all.
    """
    jid = str(journal_id or "")
    if not jid or Path(jid).name != jid or jid in (".", "..") \
            or jid.startswith("."):
        raise ValueError(
            f'"{journal_id}" is not a journal name. A journal lives in a '
            "plain folder inside the journals directory.")
    return journals_dir() / jid / FILENAME


def _slug(name: str, taken=()) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    base = base[:48] or "journal"
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def list_journals() -> list[dict]:
    """Every journal on disk, newest last, each with enough to name it in a
    switcher without loading its positions.

    A journal whose file cannot be read is listed with `problem` set and no
    counts. Hiding it would make a storage failure look like a journal the
    user never created.
    """
    out = []
    d = journals_dir()
    if not d.is_dir():
        return out
    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        path = sub / FILENAME
        if not path.exists():
            continue
        try:
            doc = store.read_json(path)
        except store.StoreError as e:
            out.append({"id": sub.name, "name": sub.name, "created": None,
                        "strategy": None, "securities": None,
                        "problem": str(e)})
            continue
        if not isinstance(doc, dict):
            out.append({"id": sub.name, "name": sub.name, "created": None,
                        "strategy": None, "securities": None,
                        "problem": f"{path.name} does not hold a journal."})
            continue
        secs = doc.get("securities") or []
        out.append({
            # The DIRECTORY is the address — it is what path_for, load and
            # save all resolve by. Listing the id inside the document
            # instead would produce a row that opens nothing the moment the
            # two disagree, which a hand-renamed folder is enough to cause.
            "id": sub.name,
            "name": doc.get("name") or sub.name,
            "created": doc.get("created"),
            "strategy": doc.get("strategy"),
            "securities": len(secs),
            "holdings": len([s for s in secs
                             if portfolio.bucket_of(s) == "holdings"]),
            "problem": None,
        })
    out.sort(key=lambda j: str(j.get("created") or ""))
    return out


def load(journal_id: str) -> dict:
    path = path_for(str(journal_id))
    doc = store.read_json(path)
    if doc is None:
        raise store.StoreError(
            f'There is no journal called "{journal_id}" in {journals_dir()}.')
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise store.StoreError(
            f'{path} holds schema {doc.get("schema")!r} if it holds a '
            f'journal at all; this version reads "{SCHEMA}". Positions are '
            "recorded differently now and there is no conversion, so the "
            "file is left exactly as it is — nothing will overwrite it. "
            "Create a new journal, or start clean with: python app.py "
            "--reset")
    # The directory this was read from is what it is called, so the next
    # save writes back where it came from rather than splitting the record
    # across two folders.
    doc["id"] = str(journal_id)
    doc.setdefault("securities", [])
    doc.setdefault("rule_changes", [])
    doc.setdefault("measure_changes", [])
    doc.setdefault("input_changes", [])
    doc.setdefault("config", {})
    doc.setdefault("inputs", {})
    doc.setdefault("settings", {})
    # Every import of a list this journal works from, oldest first. Empty for
    # a journal whose strategy screens for itself, and empty for one that
    # works from a list and has not been given one yet — which is a state the
    # host answers with a blocked verdict rather than a guess.
    doc.setdefault(lists.KEY, [])
    # What has happened to the account's cash, oldest first. Empty until the
    # record is opened, which is a state the host answers with an absent
    # balance naming the fix — never with a zero.
    doc.setdefault(cash.KEY, [])
    return doc


def save(journal: dict) -> None:
    store.write_json(path_for(journal["id"]), journal)


# -- renaming and deleting ---------------------------------------------------
# Two operations on the journal as an object, rather than on anything it
# records. They are here rather than in the app because the id/name split is a
# storage fact, and a caller that did not know it would get renaming wrong in
# the one way that matters.

def rename(journal_id: str, name: str) -> dict:
    """Give a journal a different name. Its id, and therefore its folder,
    never moves.

    The two are separate on purpose. The id is the address — `list_journals`
    reads it off the directory, `load` overwrites the document's own copy with
    the directory it came from, and every stamp, export bundle and
    machine-local "which one is open" points at it. Moving the folder to match
    a new name would break all of those to make a slug prettier, and the slug
    is not what anyone reads: the name is, and it is free text with nothing
    hanging off it.

    So a journal renamed six times keeps `sample-graham-3` as its address
    forever, and the switcher shows whatever it is now called. The only place
    the old name survives is the id, which nobody is asked to read.

    Nothing recorded is touched. A name is not a rule and not a decision, so
    this goes on no change record and owes no reason — retitling a notebook
    does not restate what is written in it.
    """
    clean = str(name or "").strip()
    if not clean:
        raise ValueError("A journal needs a name — it is how you tell two of "
                         "them apart.")
    journal = load(journal_id)
    journal["name"] = clean
    save(journal)
    return journal


def delete(journal_id: str) -> dict:
    """Remove a journal and everything it recorded.

    This is the one destructive operation in the program, and it is worth
    saying plainly what it destroys: every position, every dated note, every
    frozen snapshot of a decision, and the record of every rule change. None
    of that is recoverable and none of it is anywhere else — principle 11
    keeps a journal out of the repository, so there is no copy in version
    control to fall back on.

    Append-only is a rule about *editing* the record, and this does not edit
    it. Removing a notebook whole is a different act from rewriting a page in
    one, and refusing it would leave four journals called "SAMPLE — GRAHAM"
    on screen forever with no way to tell them apart — a tool that cannot be
    tidied stops being used, which loses the record anyway and more slowly.

    What this will not do is decide for the user. It takes a journal id and
    removes it; whether they were warned, and whether they were offered an
    export first, belongs to the screen that calls it. The engine refuses
    only what it can actually check: that the id names a journal directory
    inside the journals directory and nothing else.

    Returns what was removed, so a caller can say what happened rather than
    reporting a bare success about a thing that is now gone.
    """
    path = path_for(journal_id)
    folder = path.parent
    if not folder.is_dir():
        raise store.StoreError(
            f'There is no journal called "{journal_id}" in {journals_dir()}.')
    listed = next((j for j in list_journals() if j["id"] == journal_id), None)
    removed = {"id": journal_id,
               "name": (listed or {}).get("name") or journal_id,
               "securities": (listed or {}).get("securities"),
               "holdings": (listed or {}).get("holdings")}
    shutil.rmtree(folder)
    # The machine-local pointer would otherwise name a journal that is not
    # there. `resolve_open` copes with that already, but leaving a dangling id
    # behind means the next journal created with the same slug silently
    # inherits "you had this one open", which is a small lie about a fact the
    # user never stated.
    if open_id() == journal_id:
        set_open(None)
    return removed


# -- the open journal --------------------------------------------------------
# Which journal is open is a fact about this machine, not about any journal,
# so it lives with the other machine-local settings and never travels in an
# export. It is still on the backend: the view renders state, it does not
# hold it.

def open_id() -> str | None:
    return secrets.local_get(_OPEN_KEY) or None


def set_open(journal_id: str | None) -> None:
    secrets.local_set(_OPEN_KEY, journal_id or None)


def resolve_open() -> str | None:
    """The journal to show: the one last opened here if it still exists,
    otherwise the oldest one, otherwise none."""
    known = {j["id"] for j in list_journals()}
    current = open_id()
    if current in known:
        return current
    listed = list_journals()
    return listed[0]["id"] if listed else None


# -- creation ----------------------------------------------------------------

def stamp_for(record: dict, resolved: dict) -> dict:
    """What this journal is created against. The name travels with the id so
    a journal whose strategy is no longer installed can still say whose rules
    it was written under."""
    return {
        "id": record["id"],
        "name": record["name"],
        "contract": record["contract"],
        "version": record["version"],
        "values_version": record.get("values_version"),
        "values": dict(resolved),
        "stamped": _now(),
    }


def measures_stamp_for(definitions: dict) -> dict:
    """What every measure meant on the day this journal was created.

    The definitions themselves and not their version number, for the same
    reason the strategy stamp holds resolved values rather than a
    `values_version`: the case this record exists for is an edit made in place
    with nothing beside it moving, and a stamp that held only a number could
    not see one.
    """
    return {"version": definitions.get("version"),
            "entries": copy.deepcopy(definitions.get("entries") or {}),
            "stamped": _now()}


def create(name: str, record: dict, measures: dict, config: dict | None = None,
           inputs: dict | None = None, settings: dict | None = None) -> dict:
    """Create a journal against one strategy, and stamp it — with what its
    rules demand and with what the measures those rules cite currently mean.

    `measures` is `bank.definitions()`. It is a required argument rather than
    something read here, because a journal is the thing that has to be able to
    say what its measures meant and a caller that could omit it would create a
    journal with no before — which is the one state in which a definition can
    move invisibly.

    Refuses if the strategy's declared values cannot be resolved through this
    journal's override: a journal that cannot say what its rules are is worse
    than one that was never created.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("A journal needs a name — it is how you tell two "
                         "of them apart.")
    chain = strategy_values.resolve(
        record, layers=[("this journal's settings", config or {})])
    if chain["errors"]:
        raise ValueError("This journal's settings do not fit "
                         f'{record["name"]}: ' + " ".join(chain["errors"]))

    from .expected_value import DEFAULT_SETTINGS
    taken = {j["id"] for j in list_journals()}
    journal = {
        "schema": SCHEMA,
        "id": _slug(name, taken),
        "name": name,
        "created": _now(),
        "strategy": stamp_for(record, chain["values"]),
        "measures": measures_stamp_for(measures),
        "config": dict(config or {}),
        # Only what the user is the one to answer. A figure the host works out
        # for itself never enters the stored answers, here or at any later
        # save — see `set_inputs` and contract.user_answers.
        "inputs": contract.user_answers(record, inputs),
        "rule_changes": [],
        "measure_changes": [],
        "input_changes": [],
        "settings": dict(settings or DEFAULT_SETTINGS),
        "securities": [],
        lists.KEY: [],
        cash.KEY: [],
    }
    if path_for(journal["id"]).exists():
        raise ValueError(f'A journal already exists at {journal["id"]}.')
    save(journal)
    return journal


# -- the rule-change record --------------------------------------------------

def baseline(journal: dict) -> dict:
    """The newest state this journal knows it ran under: the last recorded
    change if there is one, the stamp otherwise. The stamp itself is never
    rewritten — it says what the journal was created against, forever."""
    changes = journal.get("rule_changes") or []
    if changes:
        return dict(changes[-1]["to"])
    stamp = journal.get("strategy") or {}
    return {"version": stamp.get("version"),
            "values_version": stamp.get("values_version"),
            "values": dict(stamp.get("values") or {})}


def _moved(before: dict, after: dict, record: dict) -> list[dict]:
    """Per declared value, what changed — including one that appeared or
    disappeared because the strategy gained or dropped a setting."""
    labels = {v["id"]: v.get("label") or v["id"]
              for v in (record.get("values") or [])}
    out = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old == new:
            continue
        out.append({"id": key, "label": labels.get(key, key),
                    "from": old, "to": new})
    return out


def _changelog_across(record: dict, was, now) -> list[str]:
    """The author's own account of every version crossed. The host cannot
    say what a change to logic meant, so it quotes the person who can."""
    log = record.get("changelog") or {}
    if not (isinstance(was, int) and isinstance(now, int)):
        return []
    lo, hi = (was, now) if now > was else (now, was)
    out = []
    for v in range(lo + 1, hi + 1):
        text = log.get(v)
        out.append(f"v{v}: {text}" if text
                   else f"v{v}: the strategy states no change for this "
                        "version.")
    return out if now > was else [
        "The strategy's version moved backwards, to an older release. "
        "What it demands now is what that older version demanded."] + out


def observe_rule_change(journal: dict, record: dict,
                        resolved: dict) -> dict | None:
    """Record any distance between what this journal last ran under and the
    strategy on disk. Returns the appended entry, or None when nothing moved.

    The caller persists the journal. Nothing here decides whether the change
    was good — the host has no view about that — and nothing here blocks
    anything: the change is on the books either way, which is the point.
    """
    was = baseline(journal)
    now = {"version": record["version"],
           "values_version": record.get("values_version"),
           "values": dict(resolved)}
    moved = _moved(was.get("values") or {}, now["values"], record)
    logic = was.get("version") != now["version"]
    values = bool(moved) or was.get("values_version") != now["values_version"]
    if not logic and not values:
        return None

    notes = []
    if moved and was.get("values_version") == now["values_version"]:
        notes.append(
            "The settings moved but the version beside them did not, so the "
            "strategy's own record does not mark this change. It is on this "
            "journal's record instead.")
    if values and not moved and was.get("values_version") != \
            now["values_version"]:
        notes.append(
            "The settings version moved but no value this journal uses "
            "changed.")

    entry = {
        "seq": len(journal.get("rule_changes") or []) + 1,
        "seen": _now(),
        "kind": "logic and settings" if (logic and values)
                else "logic" if logic else "settings",
        "from": was,
        "to": now,
        "moved": moved,
        "changelog": _changelog_across(record, was.get("version"),
                                       now["version"]) if logic else [],
        "notes": notes,
        # A reason is owed only where the user is the one who retuned, and
        # the version beside the numbers is what tells the two apart: an
        # author bumps it when shipping new values, a hand edit leaves it
        # alone. Asking the user to explain an author's release would be
        # asking for a sentence they have no way to write — into a record
        # that is write-once, so a guess at it would stand forever.
        "reason_owed": bool(moved)
                       and was.get("values_version") == now["values_version"],
        "reason": None,
    }
    journal.setdefault("rule_changes", []).append(entry)
    return entry


# -- the measure-definition record -------------------------------------------
# The same guarantee as above, for the other file that decides what an exit
# demands. Three things differ, and each one follows from the bank being
# seventy-four definitions in one file rather than a handful of numbers beside
# one strategy.
#
# **Granularity is per measure, per field.** Whole-file would say "something
# changed" about a file nobody can diff by eye, which is worth almost nothing;
# per-file-line would be a diff and not a record. What a reader needs is the
# name of the measure and the name of the thing about it that moved —
# "Return on invested capital, 5-year median · observations read: 5 → 3" — and
# that is what a change touching one formula produces, out of a file with
# seventy-three other entries in it.
#
# **The record is not narrowed to what this journal cites.** It would be
# cheaper and it would be wrong twice over. A strategy names a measure inside
# its own logic and nowhere a host can read without running it, so the only
# available answer to "does this journal use it" is what the last evaluation
# happened to cite — which changes with the state a holding is in, and would
# leave a measure moving silently right up until the quarter a rule reached
# for it. And working it out would mean the record firing off the back of an
# evaluation, when the whole posture here is that detection reads what is
# stored.
#
# **The baseline is folded, not stored.** The strategy record can afford to
# carry its whole before and after on every entry because that is a dozen
# numbers; the bank's state is fifty kilobytes, and ten changes would put half
# a megabyte of duplicated definitions inside a file that belongs to the user.
# So the stamp holds the definitions at creation and is never rewritten, each
# entry holds only what moved, and what the journal last ran under is the one
# folded from the other. Nothing here is mutable, which is the version of this
# worth having.

_MEASURES = "measure_changes"


def _folded(stamp: dict, changes) -> dict:
    """What this journal last ran under: the stamped definitions with every
    recorded change applied, in order.

    Total by construction. A change naming a measure the fold has not seen
    installs it rather than being dropped, because a record that quietly
    ignores a line it cannot place would report the next observation as a
    change that already happened.
    """
    entries = copy.deepcopy(stamp.get("entries") or {})
    version = stamp.get("version")
    for change in changes or []:
        for gone in change.get("removed") or []:
            entries.pop(gone["id"], None)
        for new in change.get("added") or []:
            entries[new["id"]] = copy.deepcopy(new["definition"])
        for m in change.get("moved") or []:
            entries.setdefault(m["id"], {}).setdefault(
                "states", {})[m["field"]] = m["to"]
        for r in change.get("restated") or []:
            entries.setdefault(r["id"], {}).setdefault(
                "restates", {})[r["field"]] = r["digest"]
        version = (change.get("to") or {}).get("version", version)
    return {"version": version, "entries": entries}


def measures_baseline(journal: dict) -> dict:
    """The definitions this journal knows it ran under, in the same shape
    `bank.definitions` produces."""
    return _folded(journal.get("measures") or {},
                   journal.get(_MEASURES) or [])


def measures_moved_at(journal: dict) -> list[str]:
    """When the definitions actually moved, oldest first.

    A release that changed only the wording moved nothing a verdict reads, and
    the day this journal first saw the definitions at all is not a move
    either. Both are on the record and neither belongs in this list, because
    what reads it is the line beside a frozen decision saying the measures
    behind it are not the measures in force now — and that line must not
    appear over a change to a paragraph.
    """
    return [str(c.get("seen")) for c in (journal.get(_MEASURES) or [])
            if c.get("added") or c.get("removed") or c.get("moved")
            or c.get("restated")]


def measures_incomparable(journal: dict, comparable) -> dict:
    """Per measure, every recorded move that makes a reading taken before it
    and a reading taken after it readings of different things::

        {entry id: [{"seen", "field", "from", "to"},   # a stated field
                    {"seen", "field"},                 # arithmetic, unsayable
                    ...]}

    `comparable` is the set of field names a move in which leaves two readings
    comparable — `bank.COMPARABLE_FIELDS`. It is handed in rather than read
    here for the reason `observe_measure_change` takes its definitions: this
    module owns the shape of the record and holds no opinion about what a
    measure is, and which fields survive a comparison is entirely the second
    thing.

    Anything not in that set counts, including a field this build has never
    heard of. That is the safe direction: what it costs is a drift figure that
    says why it cannot be worked out, and what the other default costs is a
    five-year median subtracted from a three-year one and called drift.

    A measure that was removed, or added, counts whole. A measure that went
    and came back is not the same measure, and no field ever "moved" across
    the gap for anything to notice.
    """
    out: dict[str, list] = {}
    for change in journal.get(_MEASURES) or []:
        seen = str(change.get("seen"))
        for gone in change.get("removed") or []:
            out.setdefault(gone["id"], []).append(
                {"seen": seen, "field": "the measure was removed"})
        for new in change.get("added") or []:
            out.setdefault(new["id"], []).append(
                {"seen": seen, "field": "the measure was added"})
        for m in change.get("moved") or []:
            if m["field"] in comparable:
                continue
            out.setdefault(m["id"], []).append(
                {"seen": seen, "field": m["field"],
                 "from": m.get("from"), "to": m.get("to")})
        for r in change.get("restated") or []:
            if r["field"] in comparable:
                continue
            out.setdefault(r["id"], []).append(
                {"seen": seen, "field": r["field"]})
    return out


def _named(definition: dict, fallback: str) -> str:
    """What a measure is called, for a record a person reads. The id is what
    the record is keyed on and is never what it is read by."""
    return str((definition.get("states") or {}).get("name") or fallback)


def _measures_moved(before: dict, after: dict) -> dict:
    """Per measure, what moved: entries added, entries removed, values that
    can be stated as a before and after, and arithmetic that cannot.

    The two halves of the last sentence are the whole of what this record can
    honestly claim, and they are not decided here — engine/bank.py hands each
    definition over already split into what it states and what it restates, so
    a field added there arrives on this record without a second table here
    saying which kind it is.
    """
    added, removed, moved, restated = [], [], [], []
    for eid in sorted(set(before) | set(after)):
        was, now = before.get(eid), after.get(eid)
        if was is None:
            added.append({"id": eid, "name": _named(now, eid),
                          "definition": copy.deepcopy(now)})
            continue
        if now is None:
            removed.append({"id": eid, "name": _named(was, eid)})
            continue
        name = _named(now, eid)
        old_states = was.get("states") or {}
        new_states = now.get("states") or {}
        for field in sorted(set(old_states) | set(new_states)):
            if old_states.get(field) == new_states.get(field):
                continue
            moved.append({"id": eid, "name": name, "field": field,
                          "from": old_states.get(field),
                          "to": new_states.get(field)})
        old_rest = was.get("restates") or {}
        new_rest = now.get("restates") or {}
        for field in sorted(set(old_rest) | set(new_rest)):
            if old_rest.get(field) == new_rest.get(field):
                continue
            restated.append({"id": eid, "name": name, "field": field,
                             "digest": new_rest.get(field)})
    return {"added": added, "removed": removed, "moved": moved,
            "restated": restated}


def _releases_across(log: dict, was, now) -> list[str]:
    """The bank's own account of every release crossed. The host can see a
    formula move and has no way to say what the move meant, so it quotes the
    person who can — the same reason a strategy's changelog is quoted here."""
    if not (isinstance(was, int) and isinstance(now, int)):
        return []
    lo, hi = (was, now) if now > was else (now, was)
    out = []
    for v in range(lo + 1, hi + 1):
        text = (log or {}).get(v)
        out.append(f"v{v}: {text}" if text
                   else f"v{v}: the metric bank states no change for this "
                        "version.")
    return out if now > was else [
        "The measure definitions moved backwards, to an older release. What "
        "they mean now is what that older release meant."] + out


def observe_measure_change(journal: dict, definitions: dict,
                           changelog: dict | None = None) -> dict | None:
    """Record any distance between the measure definitions this journal last
    ran under and the ones on disk. Returns the appended entry, or None when
    nothing moved.

    `definitions` is `bank.definitions()` and `changelog` is
    `bank.changelog()`. Handed in rather than read here, so this module holds
    no opinion about where a definition comes from and a test can move one
    without a file on disk.

    Nothing here blocks anything, and nothing here decides whether the change
    was good. The caller persists the journal.
    """
    now = {"version": definitions.get("version"),
           "entries": definitions.get("entries") or {}}
    if not (journal.get("measures") or {}).get("entries"):
        # A journal created before any of this was recorded has no earlier
        # state, and there is no honest way to invent one: carrying today's
        # definitions backwards would claim it always ran under them, and
        # reporting seventy-four measures as newly added would claim it never
        # had any. It has neither. So the stamp is written now — first sight
        # is a first statement and owes no reason, the same rule the strategy
        # record already follows — and the record opens with one line saying
        # so, because a reader has to be able to tell the day this journal
        # started being able to see a change from the day it was created.
        journal["measures"] = measures_stamp_for(definitions)
        entry = {
            "seq": len(journal.get(_MEASURES) or []) + 1,
            "seen": _now(),
            "kind": "first seen",
            "from": {"version": None}, "to": {"version": now["version"]},
            "added": [], "removed": [], "moved": [], "restated": [],
            "changelog": [],
            "notes": ["This journal is older than the record of what its "
                      "measures mean, so there is nothing to compare today's "
                      "definitions against. They are what it runs under from "
                      "here, and anything that moves them from now on is on "
                      "this record. Whether they moved before today is not "
                      "something this journal can say."],
            "reason_owed": False, "reason": None,
        }
        journal.setdefault(_MEASURES, []).append(entry)
        return entry

    was = measures_baseline(journal)
    parts = _measures_moved(was["entries"], now["entries"])
    definitions_moved = any(parts.values())
    released = was.get("version") != now["version"]
    if not definitions_moved and not released:
        return None

    notes = []
    if definitions_moved and not released:
        notes.append(
            "What these measures mean moved, and the version beside them did "
            "not — so the bank's own record does not mark this change. It is "
            "on this journal's record instead.")
    if released and not definitions_moved:
        notes.append(
            "The measure definitions were released again, and nothing this "
            "record covers moved. What a measure computes, refuses on and is "
            "read as are all where they were; the wording that explains them "
            "to a reader is not on this record, and may have changed.")

    entry = {
        "seq": len(journal.get(_MEASURES) or []) + 1,
        "seen": _now(),
        "kind": "definitions and release" if (definitions_moved and released)
                else "release" if released else "definitions",
        # The version alone, not the definitions. What moved is below, and the
        # state this journal now runs under is those two folded together —
        # see `_folded` for why a whole copy does not live here.
        "from": {"version": was.get("version")},
        "to": {"version": now["version"]},
        **parts,
        "changelog": _releases_across(changelog, was.get("version"),
                                      now["version"]) if released else [],
        "notes": notes,
        # The same rule as a retuned threshold, and for the same reason. A
        # release says what it changed, in the bank's own words, and asking
        # the user to explain one would be asking for a sentence they have no
        # way to write. An edit made in place says nothing at all, and the
        # person who made it is the only one who can.
        "reason_owed": definitions_moved and not released,
        "reason": None,
    }
    journal.setdefault(_MEASURES, []).append(entry)
    return entry


def set_config(journal: dict, record: dict, config: dict) -> dict | None:
    """Replace this journal's override of the strategy's declared values.

    Refuses anything that will not resolve, whole: a journal left holding an
    override it cannot read would refuse every verdict from then on, over a
    number the user was in the middle of fixing.

    The change goes onto the rule-change record here rather than being
    noticed at the next open. It is a change to what the strategy demands
    and belongs with the rest, and recording it at the moment it happens
    means there is never a window in which the new rules are in force with
    nothing saying they moved. Returns the appended entry, or None when the
    resolved values did not actually move.
    """
    chain = strategy_values.resolve(
        record, layers=[("this journal's settings", dict(config or {}))])
    if chain["errors"]:
        raise ValueError(" ".join(chain["errors"]))
    journal["config"] = dict(config or {})
    return observe_rule_change(journal, record, chain["values"])


def set_inputs(journal: dict, record: dict, inputs: dict) -> dict | None:
    """Replace what the user told this journal, and record what moved.

    Not on the rule-change record: an answer is a fact about the account,
    not a rule, and asking someone to justify their cash balance changing
    would train them to ignore the record that does matter. It is still on
    a record, because these answers now feed figures a strategy binds on.

    Returns the appended entry, or None when nothing moved.

    A figure the host works out for itself is not an answer and cannot be
    stored as one — free cash is now derived from this journal's cash record,
    and a typed copy of it sitting beside the derived figure is two numbers
    about one thing. Filtered here, at the write, rather than trusted to each
    caller: this is the only path a stored answer can arrive by, so what a
    journal holds cannot include one. A journal written before that was true
    still holds the old figure until its owner next saves anything, and the
    save clears it onto the record below, where it stays readable.
    """
    before = dict(journal.get("inputs") or {})
    after = {k: v for k, v in contract.user_answers(record, inputs).items()
             if v is not None}
    journal["inputs"] = after
    labels = {f["id"]: f.get("label") or f["id"]
              for f in (record.get("inputs") or []) if isinstance(f, dict)}
    moved = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) == after.get(key):
            continue
        moved.append({"id": key, "label": labels.get(key, key),
                      "from": before.get(key), "to": after.get(key)})
    if not moved:
        return None
    entry = {"seq": len(journal.get("input_changes") or []) + 1,
             "seen": _now(), "moved": moved}
    journal.setdefault("input_changes", []).append(entry)
    return entry


def answers_on(journal: dict, as_of: str | None = None) -> dict | None:
    """What this journal's answers were on a given day, or None where it has
    no answer for that day at all.

    `as_of` of None means now — what the journal holds, with no ceiling.

    The change record already carried everything needed for this and nothing
    read it. A reconstruction served the answer standing *now*, qualified
    with a caution saying it carried no date — which stopped being true the
    day these changes started being recorded, and was never the whole
    problem anyway. Free cash is what the account total is built from, the
    account is what every weight is measured against, and a strategy binds
    on weight: a purchase backdated two years was being sized against
    today's balance, with a sentence beside it rather than a different
    number.

    **None where the day predates the journal**, which is every backfill of
    a position bought before this program was opened. The journal has no
    answer for that day — not a stale one, none — and carrying the earliest
    one it ever held backwards is exactly the carrying-forward principle 4
    refuses. What follows from that is deliberate: free cash is absent, so
    the account total is absent, so a weight is absent, so a rule that binds
    on one says it cannot be worked out and names why. That is a
    reconstruction admitting what it does not know, and it is the whole
    reason the entry it produces is recorded as unreconstructed rather than
    as an override.

    Walked newest-first and undone rather than replayed forward, because the
    record stores where each answer came *from*: the first answer a journal
    was created with is not a change and is not in the list, so replaying
    from empty would lose it.
    """
    if as_of is None:
        return dict(journal.get("inputs") or {})
    day = str(as_of)[:10]
    born = str(journal.get("created") or "")[:10]
    if born and day < born:
        return None
    answers = dict(journal.get("inputs") or {})
    for change in reversed(journal.get("input_changes") or []):
        # A change made on the day being asked about counts as in force,
        # which is the rule every dated record in this program obeys — see
        # dated.in_force. Only what came strictly afterwards is undone.
        if str(change.get("seen") or "")[:10] <= day:
            break
        for moved in change.get("moved") or []:
            was = moved.get("from")
            if was is None:
                answers.pop(moved.get("id"), None)
            else:
                answers[moved["id"]] = was
    return answers


# The two append-only records a change to what this journal demands can land
# on, and the word each one is addressed by. One table, so a third record
# cannot be added without the screen that asks for reasons picking it up: the
# view is handed the word alongside the sequence number and hands both back,
# rather than knowing that "rules" and "measures" are what exist.
#
# `words` is separated from `key` because one of them is the host's and the
# other is nobody's business: the screen is handed the words and never the
# name of a list inside a file it does not own.
RECORDS = {
    "rules": {"key": "rule_changes",
              "words": {"noun": "rule change",
                        "means": "what your strategy demands"}},
    "measures": {"key": _MEASURES,
                 "words": {"noun": "measure change",
                           "means": "what the figures it demands them of "
                                    "mean"}},
}


def record_words() -> dict:
    """What each record is, in the host's own words, for the screen that asks
    for a reason. It says which record it is asking about, so a third one
    would arrive with its own sentence rather than needing a branch added
    wherever changes are drawn."""
    return {name: dict(spec["words"]) for name, spec in RECORDS.items()}


def pending(journal: dict) -> list[dict]:
    """Every recorded change still owed a written reason, oldest first, each
    saying which record it sits on.

    Both records, because owing a sentence is one obligation and a banner that
    knew about only one of them would leave the other quietly unexplained.
    Copies, so naming the record here can never write that word into the
    append-only entry it describes.
    """
    out = []
    for name, spec in RECORDS.items():
        out += [{**c, "record": name} for c in (journal.get(spec["key"]) or [])
                if c.get("reason_owed") and c.get("reason") is None]
    return sorted(out, key=lambda c: (str(c.get("seen") or ""), c["seq"]))


def explain(journal: dict, record: str, seq: int, reason: str) -> dict:
    """Attach the written reason to a recorded change. Write-once: the record
    is append-only and a reason cannot be revised into a better one later."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required.")
    spec = RECORDS.get(str(record))
    if spec is None:
        raise ValueError(
            f'"{record}" is not a record this journal keeps. Changes are '
            "recorded against " + " or ".join(RECORDS) + ".")
    for c in (journal.get(spec["key"]) or []):
        if c.get("seq") == int(seq):
            if c.get("reason") is not None:
                raise ValueError(
                    f'{spec["words"]["noun"].capitalize()} {seq} already '
                    f'has a reason. '
                    "The record is append-only; it cannot be rewritten.")
            c["reason"] = reason
            return c
    raise ValueError(
        f'This journal has no recorded {spec["words"]["noun"]} {seq}.')
