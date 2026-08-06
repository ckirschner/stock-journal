"""Append-only version history for the profiles.

Profiles are hand-edited YAML, so changes happen outside the app. This module
makes sure they cannot happen quietly: on every load the current content of
each profile is compared against the last recorded version, and any change is
appended to the history immediately — timestamped, with a full content
snapshot and a line-by-line account of what moved. The reason arrives later,
written by the user through the app, and is write-once: a version can be
explained exactly once and never re-explained.

The record is the point. Whether or not a reason is ever written, the change
itself is on the books with its diff, so the rules cannot be rewritten to
justify holding a loser without the rewrite being visible. Versions are only
ever appended; nothing here mutates or removes one.

The history lives in profile_history.json in the user data directory, beside
the profiles it describes, and travels with backups.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import profiles, store

FILE = "profile_history.json"

_TEXT_LIMIT = 60      # longer strings diff as "text changed", not quoted


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> dict:
    doc = store.load(FILE)
    if not isinstance(doc.get("profiles"), dict):
        doc = {"profiles": {}}
    return doc


def _version(number: int, content, changes: list[str], reason) -> dict:
    return {"version": number, "recorded": _now(), "reason": reason,
            "changes": changes, "content": content}


def sync() -> dict:
    """Record any profile that changed on disk since last seen.

    Returns the full history document. New versions created here carry
    reason None until the user explains them; the first sighting of a
    profile is recorded without a pending reason, because seeding from the
    template is not an edit.
    """
    doc = _load()
    changed = False

    on_disk, present = {}, set()
    for path in sorted(profiles.ensure_profiles().glob("*.yaml")):
        present.add(path.name)
        try:
            content = profiles.to_plain(profiles.load_yaml(path) or {})
        except Exception:  # noqa: BLE001 — unreadable files surface elsewhere
            continue       # never snapshot something we couldn't parse
        if not isinstance(content, dict):
            continue       # a YAML scalar or list is not a profile
        on_disk[path.name] = content

    for name, content in on_disk.items():
        hist = doc["profiles"].setdefault(name, {"versions": []})
        versions = hist["versions"]
        last = versions[-1] if versions else None
        if last is None:
            versions.append(_version(1, content, ["First recorded."],
                                     reason="First recorded from disk."))
            changed = True
        elif last["content"] != content:
            diffs = diff_profiles(last["content"], content) or ["Content changed."]
            versions.append(_version(last["version"] + 1, content, diffs,
                                     reason=None))
            changed = True

    # A removal is recorded only when the file is genuinely gone. A file that
    # is present but unreadable is not a deletion, and recording one would put
    # an event that never happened into the permanent record.
    for name, hist in doc["profiles"].items():
        versions = hist["versions"]
        if name not in present and versions and versions[-1]["content"] is not None:
            versions.append(_version(versions[-1]["version"] + 1, None,
                                     ["Profile removed from disk."],
                                     reason=None))
            changed = True

    if changed:
        store.save(FILE, doc)
    return doc


def pending(doc: dict | None = None) -> list[dict]:
    """Versions recorded without a reason yet, oldest first."""
    doc = doc or _load()
    out = []
    for name, hist in sorted(doc["profiles"].items()):
        for v in hist["versions"]:
            if v["reason"] is None:
                out.append({"file": name, "version": v["version"],
                            "recorded": v["recorded"], "changes": v["changes"]})
    return out


def explain(file_name: str, version: int, reason: str) -> dict:
    """Attach the written reason to a recorded change. Write-once."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("A reason is required.")
    doc = _load()
    hist = doc["profiles"].get(file_name)
    if not hist:
        raise ValueError(f"{file_name} has no recorded history.")
    for v in hist["versions"]:
        if v["version"] == int(version):
            if v["reason"] is not None:
                raise ValueError(
                    f"{file_name} v{version} already has a reason. "
                    "The record is append-only; it cannot be rewritten.")
            v["reason"] = reason
            store.save(FILE, doc)
            return v
    raise ValueError(f"{file_name} has no version {version}.")


def current_version(doc: dict, file_name: str) -> int | None:
    hist = doc["profiles"].get(file_name)
    if not hist or not hist["versions"]:
        return None
    return hist["versions"][-1]["version"]


def summary(doc: dict, file_name: str) -> list[dict]:
    """Version list for display: everything except the content snapshots."""
    hist = doc["profiles"].get(file_name)
    if not hist:
        return []
    return [{"version": v["version"], "recorded": v["recorded"],
             "reason": v["reason"], "changes": v["changes"]}
            for v in hist["versions"]]


# -- diffing -----------------------------------------------------------------

def diff_profiles(old, new) -> list[str]:
    """Human-readable account of what moved between two profile snapshots.

    Entries are matched by the metric they reference, so a reorder is not a
    change; everything else is a generic structural walk.
    """
    if old is None:
        return ["Profile restored to disk."]
    out = []
    old = dict(old) if isinstance(old, dict) else {}
    new = dict(new) if isinstance(new, dict) else {}
    old_entries = old.pop("entries", []) or []
    new_entries = new.pop("entries", []) or []
    _diff_value("", old, new, out)

    def keyed(entries):
        d = {}
        for e in entries:
            mid = str((e or {}).get("metric"))
            d.setdefault(mid, []).append(e)
        return d

    a, b = keyed(old_entries), keyed(new_entries)
    for mid in sorted(set(a) | set(b)):
        olds, news = a.get(mid, []), b.get(mid, [])
        for i in range(max(len(olds), len(news))):
            label = mid if len(olds) <= 1 and len(news) <= 1 else f"{mid}[{i}]"
            if i >= len(olds):
                tier = str((news[i] or {}).get("tier", ""))
                out.append(f"{label}: added"
                           + (f" to {tier.upper()}" if tier else ""))
            elif i >= len(news):
                out.append(f"{label}: removed")
            else:
                _diff_value(label, olds[i], news[i], out)
    return out


def _render(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, str):
        s = " ".join(v.split())
        return f'"{s}"' if len(s) <= _TEXT_LIMIT else "text"
    if isinstance(v, (dict, list)):
        return "…"
    return str(v)


def _diff_value(path, a, b, out):
    if a == b:
        return
    dot = f"{path}." if path else ""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            _diff_value(f"{dot}{k}", a.get(k), b.get(k), out)
        return
    if isinstance(a, list) and isinstance(b, list):
        for i in range(max(len(a), len(b))):
            ai = a[i] if i < len(a) else None
            bi = b[i] if i < len(b) else None
            _diff_value(f"{dot}{i}" if not path else f"{path}[{i}]", ai, bi, out)
        return
    if isinstance(a, str) and isinstance(b, str) and (
            len(a) > _TEXT_LIMIT or len(b) > _TEXT_LIMIT):
        out.append(f"{path}: text changed")
        return
    out.append(f"{path}: {_render(a)} → {_render(b)}")
