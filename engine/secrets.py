"""Secrets and machine-local personal settings. Neither can be exported.

Two kinds of thing live here, both excluded from backups BY CONSTRUCTION —
the export bundle copies the allowlist in store.FILES, and nothing in this
module ever writes inside that list:

- **Secrets** (the Tiingo API key). Stored in the operating system's own
  credential facility via the `keyring` library — macOS Keychain, Windows
  Credential Locker, Secret Service on Linux. That is the right tool: it is
  per-user, survives no file copy, and never lands in a bundle, a synced
  folder, or a screenshot of a config file. Where no OS facility exists, the
  fallback is a file under <data>/local/ with owner-only permissions — and
  `storage()` tells the UI so it can say, plainly, that the key is stored
  unencrypted there. An honest fallback beats a fake one: on a machine the
  attacker already controls, any encryption key this app could reach, they
  can reach too.

- **Machine-local settings** (the SEC identity contact — a name and email).
  Not a secret, but personal information, and a backup bundle dropped on a
  synced drive shouldn't carry an email address any more than a key. It
  lives in <data>/local/machine.json, outside the export set.

The threat model is accidental exfiltration and casual disclosure, not a
determined attacker on this machine. Secrets never appear in URLs (header
auth only — see tiingo.py), never in error messages, and never come back out
to the UI once stored — the UI is told THAT a key exists and where, never
what it is.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import store

SERVICE = "Ledger"                 # the keyring service name
_DISABLE_KEYRING = False           # tests force the file fallback with this


class SecretsError(Exception):
    pass


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# -- backend selection -------------------------------------------------------

def _keyring():
    """The keyring module with a usable OS backend, or None.

    None means the file fallback is in use — and the UI says so.
    """
    if _DISABLE_KEYRING:
        return None
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring
        if isinstance(keyring.get_keyring(), FailKeyring):
            return None
        return keyring
    except Exception:                                   # noqa: BLE001
        return None


def storage() -> dict:
    """Where secrets live on this machine, for the UI to state honestly.

    {"kind": "os_keyring", "where": "macOS Keychain"} or
    {"kind": "file", "where": "<path>", "unencrypted": True}
    """
    kr = _keyring()
    if kr is not None:
        backend = kr.get_keyring()
        name = getattr(backend, "name", None) or type(backend).__name__
        return {"kind": "os_keyring", "where": str(name)}
    return {"kind": "file", "where": str(_secrets_path()), "unencrypted": True}


# -- the file fallback -------------------------------------------------------

def _local_dir() -> Path:
    d = store.data_dir() / "local"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _secrets_path() -> Path:
    return store.data_dir() / "local" / "secrets.json"


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write_json_private(path: Path, doc: dict) -> None:
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                               dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(doc, indent=2))
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# -- secrets ----------------------------------------------------------------

def get_secret(name: str) -> str | None:
    kr = _keyring()
    if kr is not None:
        try:
            v = kr.get_password(SERVICE, name)
            return v or None
        except Exception as e:                          # noqa: BLE001
            raise SecretsError(
                f"the OS credential store could not be read "
                f"({type(e).__name__})") from e
    v = _read_json(_secrets_path()).get(name)
    return v or None


def set_secret(name: str, value: str) -> None:
    value = (value or "").strip()
    if not value:
        raise SecretsError("an empty value is not a key; use remove instead")
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(SERVICE, name, value)
            return
        except Exception as e:                          # noqa: BLE001
            raise SecretsError(
                f"the OS credential store refused the write "
                f"({type(e).__name__})") from e
    _local_dir()
    doc = _read_json(_secrets_path())
    doc[name] = value
    _write_json_private(_secrets_path(), doc)


def delete_secret(name: str) -> bool:
    """Remove a secret. True if one was there."""
    kr = _keyring()
    if kr is not None:
        try:
            had = bool(kr.get_password(SERVICE, name))
            if had:
                kr.delete_password(SERVICE, name)
            return had
        except Exception as e:                          # noqa: BLE001
            raise SecretsError(
                f"the OS credential store refused the delete "
                f"({type(e).__name__})") from e
    doc = _read_json(_secrets_path())
    had = name in doc
    if had:
        doc.pop(name)
        _write_json_private(_secrets_path(), doc)
    return had


# -- machine-local settings --------------------------------------------------

def _machine_path() -> Path:
    return store.data_dir() / "local" / "machine.json"


def local_get(key: str):
    return _read_json(_machine_path()).get(key)


def local_set(key: str, value) -> None:
    _local_dir()
    doc = _read_json(_machine_path())
    if value is None:
        doc.pop(key, None)
    else:
        doc[key] = value
    _write_json_private(_machine_path(), doc)


# -- migration off plaintext settings ---------------------------------------

LEGACY_KEY_FIELD = "tiingo_api_token"
LEGACY_IDENTITY_FIELD = "sec_identity"
ROTATE_FLAG = "plaintext_key_migrated"


def migrate_from_settings(settings: dict) -> bool:
    """Move any secret or personal field out of the exportable settings doc.

    Returns True if the doc changed (caller persists it). The old copies are
    REMOVED, not duplicated — and a key that ever sat in plaintext gets a
    standing rotate notice (ROTATE_FLAG in machine.json) until the user
    replaces it, because files it may already have leaked into (old exports,
    synced copies) are beyond recall.

    This also runs after every bundle import: an old bundle that still
    carries a plaintext key gets cleaned on arrival instead of resurrecting
    the problem.
    """
    changed = False
    key = (settings.pop(LEGACY_KEY_FIELD, "") or "").strip()
    if key:
        set_secret("tiingo_api_token", key)
        local_set(ROTATE_FLAG, _stamp())
        changed = True
    elif LEGACY_KEY_FIELD in settings:
        settings.pop(LEGACY_KEY_FIELD, None)
        changed = True
    ident = (settings.pop(LEGACY_IDENTITY_FIELD, "") or "").strip()
    if ident:
        if not local_get("sec_identity"):
            local_set("sec_identity", ident)
        changed = True
    elif LEGACY_IDENTITY_FIELD in settings:
        settings.pop(LEGACY_IDENTITY_FIELD, None)
        changed = True
    return changed
