"""Where the data lives, and the two primitives everything writes through.

Nothing personal is stored inside the project directory. On first run a data
directory is created outside the repo, so cloning or pushing the code can
never carry positions, notes or ideas with it.

Override with the LEDGER_DATA environment variable if you'd rather keep it on
a synced drive.

Three kinds of thing live under the data directory, and the split is what
makes the export set safe by construction:

    journals/<id>/journal.json   the user's journals — the exportable set
    local/                       secrets and machine-local personal settings,
                                 outside the export set entirely
    facts/ prices/ cache/        fetched public data about companies, shared
    tickermap.json               by every journal; a cache, never a record

Writes go through write_json, which renames a temp file into place, so a
crash mid-write can never truncate a journal. Reads go through read_json,
which refuses a file it cannot parse rather than returning an empty document
— an unreadable journal must read as a problem, never as an empty one.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent


class StoreError(Exception):
    """A file that exists but cannot be read. Never raised for a file that is
    simply absent — that is a fact the caller judges."""


def data_dir() -> Path:
    env = os.environ.get("LEDGER_DATA")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME",
                                   Path.home() / ".local/share"))
    return base / "Ledger"


def ensure_data() -> Path:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_json(path: Path, default=None):
    """The parsed document, or `default` when the file does not exist.

    A file that exists but does not parse raises rather than resolving to an
    empty document. The old behaviour — quarantine it and start clean — is
    wrong for a journal: a journal that reads as empty looks like a journal
    with nothing in it, which is a fabricated answer to "what did I record?".
    The file is left exactly where it is, so nothing overwrites it while the
    problem is being fixed.
    """
    path = Path(path)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise StoreError(
            f"{path.name} is not readable as JSON (line {e.lineno}: "
            f"{e.msg}). It has been left exactly as it is at {path} — "
            "nothing will overwrite it.") from e
    except OSError as e:
        raise StoreError(f"{path.name} could not be read: {e}") from e


def write_json(path: Path, payload) -> None:
    """Write atomically: a crash mid-write leaves the previous file intact.

    The temp file gets a unique name rather than a fixed one, so two writers
    can never share it and finish each other's write — the same discipline
    the filing cache uses, and a journal deserves at least as much as a cache
    that can be re-fetched. Serialising the JSON before opening anything also
    means a payload that cannot be serialised raises with the old file
    untouched, instead of leaving a truncated temp behind. And the bytes are
    synced before the rename, so "the previous file survives" holds against a
    power loss and not only against a process crash.
    """
    path = Path(path)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            # The bytes reach the disk before the rename can publish the new
            # name. Without this the rename is atomic against a process
            # crash but not against a power loss: the metadata can land
            # while the data has not, and the journal comes back present and
            # empty — which reads as a journal with nothing in it.
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
