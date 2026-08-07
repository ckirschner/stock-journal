"""The metric bank and the strategy profiles.

The bank (config/metric-bank.yaml) defines what a value *is* and holds no
decision power. Profiles (user data dir, profiles/*.yaml) hold every threshold
and roll-up rule. This module loads both and joins a profile against its bank
into a render-ready plain structure.

Loading is ruamel round-trip so comments and key order survive: this pass only
reads, but editing lands next and the loader must not need replacing.

Failures resolve loudly. An unresolved bank reference, an unsupplied required
parameter, or a tier the rollup does not declare becomes an error string
attached to the entry or the profile — never a silently skipped row.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ruamel.yaml import YAML

from engine import store

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_DIR / "config"
TEMPLATE_PROFILES = APP_DIR / "data.template" / "profiles"

_yaml = YAML()  # round-trip is the default; keeps comments and key order
_yaml.preserve_quotes = True


# -- paths and seeding -----------------------------------------------------

def profiles_dir() -> Path:
    return store.data_dir() / "profiles"


def ensure_profiles() -> Path:
    """Seed the user's profiles from the template on first run.

    Only when the directory does not exist at all: a profile the user has
    deleted must not quietly reappear.
    """
    d = profiles_dir()
    if not d.exists():
        if TEMPLATE_PROFILES.exists():
            shutil.copytree(TEMPLATE_PROFILES, d)
        else:
            d.mkdir(parents=True, exist_ok=True)
    return d


def bank_path(name: str) -> Path:
    return CONFIG_DIR / (name + ".yaml")


def load_yaml(path):
    """Round-trip document, suitable for writing back unchanged."""
    with open(path, encoding="utf-8") as f:
        return _yaml.load(f)


# -- plain conversion --------------------------------------------------------

def to_plain(node):
    """Strip ruamel types so nothing framework-shaped crosses to the UI."""
    if isinstance(node, dict):
        return {str(k): to_plain(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [to_plain(v) for v in node]
    if node is None or isinstance(node, bool):
        return node
    if isinstance(node, int):
        return int(node)
    if isinstance(node, float):
        return float(node)
    return str(node)


# -- bank ---------------------------------------------------------------------

_bank_cache: dict = {}


def load_bank(name: str):
    path = bank_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f'The metric bank "{name}" was not found at {path}.')
    # Round-trip parsing a 2,000-line YAML costs real time and get_state asks
    # for the bank several times per render; cache by mtime so edits still
    # show up without a restart. The doc is treated as read-only everywhere.
    mtime = path.stat().st_mtime
    held = _bank_cache.get(name)
    if held and held[0] == mtime:
        return held[1]
    doc = load_yaml(path) or {}
    schema = str(doc.get("schema") or "")
    if not schema.startswith("ledger.metric-bank/"):
        raise ValueError(
            f'{path.name} does not declare a metric-bank schema '
            f'(found "{schema or "nothing"}").')
    _bank_cache[name] = (mtime, doc)
    return doc


def bank_index(doc) -> dict:
    return {str(e.get("id")): e for e in (doc.get("entries") or [])}


def bank_view(name: str = "metric-bank") -> dict:
    """The full bank for the Metrics page. No thresholds exist here."""
    doc = load_bank(name)
    return {
        "name": name,
        "schema": to_plain(doc.get("schema")),
        "entries": [to_plain(e) for e in (doc.get("entries") or [])],
    }


# -- profiles -------------------------------------------------------------

def list_profiles():
    """(profiles, errors) for the selector: file, id and name only."""
    out, errors = [], []
    for path in sorted(ensure_profiles().glob("*.yaml")):
        try:
            doc = load_yaml(path) or {}
            out.append({
                "file": path.name,
                "id": str(doc.get("id") or path.stem),
                "name": str(doc.get("name") or path.stem),
            })
        except Exception as e:  # noqa: BLE001 — a broken file is a page fact
            errors.append(f"{path.name} could not be read: {e}")
    return out, errors


def resolve_profile(file_name: str) -> dict:
    """One profile joined against its bank, render-ready.

    Reads exactly one profile file. Nothing from any sibling profile enters
    this structure.
    """
    name = Path(str(file_name)).name
    if name != file_name or not name.endswith(".yaml"):
        raise ValueError(f'"{file_name}" is not a profile file name.')
    path = ensure_profiles() / name
    if not path.exists():
        raise FileNotFoundError(f"{name} is not in {profiles_dir()}.")

    prof = load_yaml(path) or {}
    errors = []

    schema = str(prof.get("schema") or "")
    if not schema.startswith("ledger.profile/"):
        errors.append(f'{name} does not declare a profile schema '
                      f'(found "{schema or "nothing"}").')

    bank_name = str(prof.get("bank") or "")
    index = {}
    if not bank_name:
        errors.append("This profile does not name a metric bank, so none of "
                      "its entries can be resolved.")
    else:
        try:
            index = bank_index(load_bank(bank_name))
        except (FileNotFoundError, ValueError) as e:
            errors.append(str(e))

    settings = prof.get("settings") or {}
    rollup = settings.get("rollup") or {}
    tiers_decl = rollup.get("tiers") or {}

    views = [_entry_view(e, index, bank_name)
             for e in (prof.get("entries") or [])]
    by_tier = {}
    for v in views:
        by_tier.setdefault(v["tier"], []).append(v)

    groups = []
    for key in [str(k) for k in tiers_decl.keys()]:
        decl = to_plain(tiers_decl.get(key)) or {}
        ents = by_tier.pop(key, [])
        declared = decl.get("count")
        if isinstance(declared, int) and declared != len(ents):
            errors.append(f"The rollup declares {declared} {key.upper()} "
                          f"entries but the profile lists {len(ents)}.")
        groups.append({
            "key": key,
            "count": declared,
            "requires": decl.get("requires"),
            "min_green": decl.get("min_green"),
            "contributes": decl.get("contributes"),
            "meaning": decl.get("meaning"),
            "entries": ents,
        })
    for key, ents in by_tier.items():
        errors.append(f'{len(ents)} entries use the tier "{key}", which the '
                      "rollup does not declare.")
        groups.append({"key": key, "count": None, "requires": None,
                       "min_green": None, "contributes": None,
                       "meaning": None, "entries": ents})

    return {
        "file": name,
        "id": to_plain(prof.get("id")),
        "name": to_plain(prof.get("name")) or name,
        "bank": bank_name,
        "summary": to_plain(prof.get("summary")),
        "notice": to_plain(prof.get("notice")),
        "rollup": {
            "rule": to_plain(rollup.get("rule")),
            "grey": to_plain(rollup.get("grey")),
        },
        "holding_period_exit": to_plain(settings.get("holding_period_exit")),
        "sell_confirmation": to_plain(
            (settings.get("defaults") or {}).get("sell_confirmation")),
        "tiers": groups,
        "errors": errors,
    }


def _entry_view(raw, index: dict, bank_name: str) -> dict:
    """One profile entry joined with its bank definition.

    An unresolved reference or missing parameter lands in the entry's own
    errors list; the row itself always survives to be rendered.
    """
    metric_id = str(raw.get("metric") or "").strip()
    entry_errors = []
    view = {
        "metric": metric_id,
        "tier": str(raw.get("tier") or ""),
        "buy": to_plain(raw.get("buy")),
        "sell": to_plain(raw.get("sell")),
        "flag": to_plain(raw.get("flag")),
        "note": to_plain(raw.get("note")),
        "errors": entry_errors,
    }

    bank_entry = index.get(metric_id)
    if bank_entry is None:
        entry_errors.append(
            f'This entry references "{metric_id or "(no metric named)"}", '
            f'which is not in the bank "{bank_name}".')
        return view

    explanation = bank_entry.get("explanation") or {}
    view.update({
        "label": to_plain(bank_entry.get("label")),
        "kind": to_plain(bank_entry.get("kind")),
        "unit": to_plain(bank_entry.get("unit")),
        "description": to_plain(explanation.get("plain")),
        "not_meaningful_when":
            to_plain(bank_entry.get("not_meaningful_when") or []),
    })

    for block_name in ("sell", "flag"):
        block = view.get(block_name)
        if isinstance(block, dict) and block.get("measured_on"):
            target = index.get(str(block["measured_on"]))
            if target is None:
                entry_errors.append(
                    f'The {block_name} threshold is measured on '
                    f'"{block["measured_on"]}", which is not in the bank '
                    f'"{bank_name}".')
            else:
                block["measured_on_label"] = to_plain(target.get("label"))

    declared = bank_entry.get("parameters") or []
    supplied = raw.get("parameters") or {}
    supplied = {str(k): v for k, v in supplied.items()}
    params, seen = [], set()
    for p in declared:
        pid = str(p.get("id"))
        seen.add(pid)
        given = pid in supplied
        if not given:
            entry_errors.append(
                f'"{metric_id}" needs the parameter "{pid}" and this profile '
                "does not supply it.")
        params.append({
            "id": pid,
            "label": to_plain(p.get("label")) or pid,
            "unit": to_plain(p.get("unit")),
            "means": to_plain(p.get("means")),
            "supplied": given,
            "value": to_plain(supplied.get(pid)) if given else None,
        })
    for pid, value in supplied.items():
        if pid not in seen:
            entry_errors.append(
                f'This profile supplies the parameter "{pid}", which '
                f'"{metric_id}" does not declare.')
            params.append({"id": pid, "label": pid, "unit": None,
                           "means": None, "supplied": True,
                           "value": to_plain(value)})
    view["parameters"] = params
    return view
