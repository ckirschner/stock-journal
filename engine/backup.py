"""Export and import.

Your positions, notes and ideas are yours. They never enter the repository.
Export writes one timestamped file you can drop wherever you keep backups.
Import reads it back.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import store

BUNDLE_VERSION = 1


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
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    return dest


def inspect_bundle(src: str | Path) -> dict:
    """Read a bundle without applying it, so the user can confirm first."""
    data = json.loads(Path(src).expanduser().read_text(encoding="utf-8"))
    if data.get("bundle_version") != BUNDLE_VERSION:
        raise ValueError(
            f"Bundle version {data.get('bundle_version')} is not supported "
            f"(expected {BUNDLE_VERSION})."
        )
    secs = (data["files"].get("securities.json") or {}).get("securities", [])
    rules = (data["files"].get("rules.json") or {}).get("versions", [])
    return {
        "exported": data.get("exported"),
        "securities": len(secs),
        "holdings": len([s for s in secs if s.get("bucket") == "holdings"]),
        "ruleset_versions": len(rules),
    }


def import_bundle(src: str | Path, keep_backup: bool = True) -> dict:
    """Replace local data with a bundle. The current data is backed up first."""
    src = Path(src).expanduser()
    summary = inspect_bundle(src)

    if keep_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        export_bundle(store.data_dir() / f"pre-import-{stamp}.json")

    data = json.loads(src.read_text(encoding="utf-8"))
    for name, payload in data["files"].items():
        if name in store.FILES:
            store.save(name, payload)
    return summary
