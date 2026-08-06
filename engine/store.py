"""Where the data lives.

Nothing personal is stored inside the project directory. On first run the
template is copied to a user data directory outside the repo, so cloning or
pushing the code can never carry positions, notes or ideas with it.

Override with the LEDGER_DATA environment variable if you'd rather keep it on
a synced drive.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = APP_DIR / "data.template"

FILES = ("settings.json", "securities.json", "profile_history.json")


def data_dir() -> Path:
    env = os.environ.get("LEDGER_DATA")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "Ledger"


def ensure_data() -> Path:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = d / name
        if not target.exists():
            src = TEMPLATE_DIR / name
            if src.exists():
                shutil.copy(src, target)
            else:
                target.write_text("{}", encoding="utf-8")
    return d


def load(name: str) -> dict:
    path = ensure_data() / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Never lose a corrupt file silently. Move it aside and start clean —
        # and never overwrite an earlier .broken file doing it.
        if path.exists():
            aside = path.with_suffix(".json.broken")
            if aside.exists():
                from datetime import datetime
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                aside = path.with_name(f"{path.name}.broken-{stamp}")
            path.rename(aside)
        src = TEMPLATE_DIR / name
        if src.exists():
            shutil.copy(src, path)
            return json.loads(path.read_text(encoding="utf-8"))
        return {}


def save(name: str, payload: dict) -> None:
    d = ensure_data()
    path = d / name
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)  # atomic rename, so a crash mid-write can't truncate the journal
