"""Export and import.

Your journals are yours. They never enter the repository. Export writes one
timestamped file you can drop wherever you keep backups; import reads it
back.

What travels is exactly the journals directory: each journal entire, with its
positions, notes, the snapshots frozen onto purchases and the ones saved on
purpose, declared inputs, its cash record, valuation
settings, its rule change record and the strategy it is stamped with. That last part is what
makes a restored journal still mean something — it names the rules every
decision in it was taken under, and the versions they were at.

What does not travel, by construction rather than by care: the API key and
the SEC contact. They live under <data>/local/, and the exportable set is the
journals directory, so no future field added to a journal can carry one out.
Fetched filings and prices do not travel either — they are a cache of public
data, re-fetchable, and shipping a few hundred megabytes of them inside a
backup would make the backup something people stop taking.

Bundles from before journals existed are refused, not converted. They
describe a program that evaluated securities under several profiles at once,
and there is no honest way to say which of those verdicts a restored journal
would be stamped with.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import cash, journals, lists, portfolio, snapshots, store

# 4: journals hold lot history rather than one position per security, and
#    carry the answers a strategy asked for. Nothing converts an older
#    bundle — the positions in one describe a shape this app no longer has.
BUNDLE_VERSION = 4


def export_bundle(dest: str | Path) -> Path:
    """Write every journal into one portable JSON bundle."""
    dest = Path(dest).expanduser()
    if dest.is_dir():
        stamp = datetime.now().strftime("%Y-%m-%d")
        dest = dest / f"ledger-backup-{stamp}.json"

    docs = []
    for listed in journals.list_journals():
        if listed.get("problem"):
            continue        # an unreadable journal is reported, never guessed
        docs.append(journals.load(listed["id"]))

    bundle = {
        "bundle_version": BUNDLE_VERSION,
        "exported": datetime.now().isoformat(timespec="seconds"),
        "journals": docs,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bundle, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return dest


def _read(src: Path) -> dict:
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{src.name} is not readable as JSON "
                         f"(line {e.lineno}: {e.msg}).") from e
    version = data.get("bundle_version")
    if version != BUNDLE_VERSION:
        raise ValueError(
            f"This backup is version {version}; this app writes and reads "
            f"version {BUNDLE_VERSION}. Older bundles record a position as "
            "one running total per security rather than the lots it was "
            "built from, and there is no honest way to invent the lots that "
            "were never written down. Nothing was imported, and the file is "
            "untouched.")
    if not isinstance(data.get("journals"), list):
        raise ValueError("This backup carries no journals. Nothing was "
                         "imported.")
    return data


def inspect_bundle(src: str | Path) -> dict:
    """Read a bundle without applying it, so the user can confirm first."""
    data = _read(Path(src).expanduser())
    docs = data["journals"]
    return {
        "bundle_version": data.get("bundle_version"),
        "exported": data.get("exported"),
        "journals": len(docs),
        "securities": sum(len(d.get("securities") or []) for d in docs),
        "holdings": sum(len([s for s in (d.get("securities") or [])
                             if portfolio.bucket_of(s) == "holdings"])
                        for d in docs),
        # Every import of a list a journal works from. Counted here because
        # this screen is what somebody confirms an import against, and a
        # figure missing from it reads as a collection the bundle does not
        # carry — which, for a strategy whose entire buy decision is the
        # list, is the one thing they would want to check.
        "lists": sum(len(d.get(lists.KEY) or []) for d in docs),
        # And every cash entry. Counted for the reason the lists are: this
        # screen is what somebody confirms an import against, and a record
        # missing from it reads as one the bundle does not carry — for cash,
        # that is what every account total and every position weight in the
        # restored journal is built on.
        "cash_entries": sum(len(d.get(cash.KEY) or []) for d in docs),
        # And every day somebody deliberately kept. Counted for the same
        # reason again, and with one of its own: a saved snapshot is the only
        # frozen verdict in the file that is not attached to a purchase, so
        # it is the one a reader scanning for positions would not think to
        # check for. Standing ones, not every entry — a discarded snapshot
        # travels and is meant to, but a count that included it would say
        # this bundle carries more than the restored journal will show.
        "snapshots": sum(len(snapshots.standing(s))
                         for d in docs for s in (d.get("securities") or [])),
        "names": [str(d.get("name") or d.get("id")) for d in docs],
    }


def import_bundle(src: str | Path, keep_backup: bool = True) -> dict:
    """Replace the journals on this machine with a bundle's.

    Everything is validated before anything is written: a bundle that would
    fail halfway fails before the first write instead. The current journals
    are exported beside the data first, so an import can always be undone.
    """
    src = Path(src).expanduser()
    data = _read(src)
    summary = inspect_bundle(src)

    seen = set()
    for doc in data["journals"]:
        if not isinstance(doc, dict):
            raise ValueError("A journal in this backup is not a journal. "
                             "Nothing was imported.")
        jid = str(doc.get("id") or "")
        if not jid or Path(jid).name != jid or jid.startswith("."):
            raise ValueError(
                f'This backup names a journal "{jid}", which is not a plain '
                "folder name. Nothing was imported.")
        if doc.get("schema") != journals.SCHEMA:
            raise ValueError(
                f'The journal "{jid}" declares schema '
                f'{doc.get("schema")!r}, which this app cannot read. '
                "Nothing was imported.")
        if jid in seen:
            raise ValueError(f'This backup carries two journals called '
                             f'"{jid}". Nothing was imported.')
        seen.add(jid)

    here = journals.list_journals()
    rescue = None
    if keep_backup and here:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rescue = export_bundle(store.data_dir() / f"pre-import-{stamp}.json")

    # A journal whose file will not parse was skipped by the rescue copy
    # above, so removing it here would destroy the only copy there is — and
    # read_json has already promised its owner that an unreadable file is
    # left exactly where it is. It keeps listing with its problem until they
    # repair it.
    unreadable = {j["id"] for j in here if j.get("problem")}
    removed = []
    d = journals.journals_dir()
    if d.is_dir():
        for sub in sorted(d.iterdir()):
            if not sub.is_dir() or sub.name in seen \
                    or sub.name in unreadable:
                continue
            path = sub / journals.FILENAME
            if path.exists():
                path.unlink()
                removed.append(sub.name)
            try:
                sub.rmdir()
            except OSError:
                pass            # something else is in there; leave it alone
    for doc in data["journals"]:
        journals.save(doc)
    # What the import cost, so the screen can say it rather than leave the
    # user to notice a journal is gone.
    summary["removed"] = removed
    summary["kept_unreadable"] = sorted(unreadable)
    summary["rescue"] = str(rescue) if rescue else None
    return summary
