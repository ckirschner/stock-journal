"""Journals — the collection, and the strategy stamped on each one.

A journal has exactly one strategy and it does not change. Trading two
strategies means two journals, the way it would mean two accounts. So the
strategy is chosen when a journal is created and recorded on it — its
identity, the host contract version it spoke, the version of its logic, the
version of its declared values, and the declared values themselves as they
resolved that day.

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
     "config":   {value id: value},      # this journal's override, if any
     "inputs":   {input id: value},      # what the user supplied
     "rule_changes":  [...],             # append-only, see below
     "input_changes": [...],             # append-only, see below
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

**Answers are not rules, and are kept apart.** What the user told the journal
— free cash, and anything else a strategy asks for — moves for ordinary
reasons and moves often; putting each edit on the rule-change record would
bury the retunings that record exists to surface. But those answers now feed
figures a strategy binds on, so an answer that can be quietly adjusted the
day before a purchase is worth being able to see. They get their own
append-only list: before and after, dated, and no reason ever demanded,
because updating a fact is not a change to what the rules demand.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import dated, lists, portfolio, secrets, store, strategy_values

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
    doc.setdefault("input_changes", [])
    doc.setdefault("config", {})
    doc.setdefault("inputs", {})
    doc.setdefault("settings", {})
    # Every import of a list this journal works from, oldest first. Empty for
    # a journal whose strategy screens for itself, and empty for one that
    # works from a list and has not been given one yet — which is a state the
    # host answers with a blocked verdict rather than a guess.
    doc.setdefault(lists.KEY, [])
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


def create(name: str, record: dict, config: dict | None = None,
           inputs: dict | None = None, settings: dict | None = None) -> dict:
    """Create a journal against one strategy, and stamp it.

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
        "config": dict(config or {}),
        "inputs": dict(inputs or {}),
        "rule_changes": [],
        "input_changes": [],
        "settings": dict(settings or DEFAULT_SETTINGS),
        "securities": [],
        lists.KEY: [],
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
    """
    before = dict(journal.get("inputs") or {})
    after = {k: v for k, v in (inputs or {}).items() if v is not None}
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


def pending(journal: dict) -> list[dict]:
    """Recorded changes still owed a written reason, oldest first."""
    return [c for c in (journal.get("rule_changes") or [])
            if c.get("reason_owed") and c.get("reason") is None]


def explain(journal: dict, seq: int, reason: str) -> dict:
    """Attach the written reason to a recorded change. Write-once: the record
    is append-only and a reason cannot be revised into a better one later."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required.")
    for c in (journal.get("rule_changes") or []):
        if c.get("seq") == int(seq):
            if c.get("reason") is not None:
                raise ValueError(
                    f"Change {seq} already has a reason. The record is "
                    "append-only; it cannot be rewritten.")
            c["reason"] = reason
            return c
    raise ValueError(f"This journal has no recorded change {seq}.")
