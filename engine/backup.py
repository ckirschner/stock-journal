"""Export and import.

Your positions, notes and ideas are yours. They never enter the repository.
Export writes one timestamped file you can drop wherever you keep backups —
the journal, the settings, the profiles and their version history. Import
reads it back.

Version-1 bundles predate the profile system. Importing one restores the
journal and settings; the retired ruleset history it carries is archived
beside the data rather than discarded, because it is recorded history, and
the securities are migrated to the bank vocabulary on the next load.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import store
from .profiles import ensure_profiles

BUNDLE_VERSION = 2


def export_bundle(dest: str | Path) -> Path:
    """Write every data file into one portable JSON bundle."""
    dest = Path(dest).expanduser()
    if dest.is_dir():
        stamp = datetime.now().strftime("%Y-%m-%d")
        dest = dest / f"ledger-backup-{stamp}.json"

    bundle = {
        "bundle_version": BUNDLE_VERSION,
        "exported": datetime.now().isoformat(timespec="seconds"),
        "files": {name: store.load(name) for name in store.FILES},
        "profiles": {p.name: p.read_text(encoding="utf-8")
                     for p in sorted(ensure_profiles().glob("*.yaml"))},
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def inspect_bundle(src: str | Path) -> dict:
    """Read a bundle without applying it, so the user can confirm first."""
    data = json.loads(Path(src).expanduser().read_text(encoding="utf-8"))
    version = data.get("bundle_version")
    if version not in (1, BUNDLE_VERSION):
        raise ValueError(
            f"Bundle version {version} is not supported "
            f"(expected 1 or {BUNDLE_VERSION})."
        )
    secs = (data["files"].get("securities.json") or {}).get("securities", [])
    out = {
        "bundle_version": version,
        "exported": data.get("exported"),
        "securities": len(secs),
        "holdings": len([s for s in secs if s.get("bucket") == "holdings"]),
        "profiles": len(data.get("profiles") or {}),
    }
    if version == 1:
        out["note"] = ("This backup predates profiles. Its securities will "
                       "be migrated on the next load, and the retired "
                       "ruleset history it carries is archived, not lost.")
    return out


def import_bundle(src: str | Path, keep_backup: bool = True) -> dict:
    """Replace local data with a bundle. The current data is backed up first."""
    src = Path(src).expanduser()
    summary = inspect_bundle(src)

    # Validate everything before touching anything: a bundle that would fail
    # halfway must fail before the first write instead.
    data = json.loads(src.read_text(encoding="utf-8"))
    for name in (data.get("profiles") or {}):
        if (not name or Path(name).name != name
                or not name.endswith(".yaml")):
            raise ValueError(
                f'The bundle names a profile "{name}", which is not a plain '
                ".yaml file name. Nothing was imported.")

    if keep_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        export_bundle(store.data_dir() / f"pre-import-{stamp}.json")

    for name, payload in data["files"].items():
        if name in store.FILES:
            store.save(name, payload)

    if data.get("bundle_version") == 1:
        rules = data["files"].get("rules.json")
        if rules:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            store.save(f"rules.legacy.import-{stamp}.json", rules)
    else:
        profiles_dir = ensure_profiles()
        bundled = data.get("profiles") or {}
        for existing in profiles_dir.glob("*.yaml"):
            if existing.name not in bundled:
                existing.unlink()
        for name, text in bundled.items():  # names validated above
            (profiles_dir / name).write_text(text, encoding="utf-8")
    return summary
