"""The metric bank — what every value *is*.

The bank (config/metric-bank.yaml) defines each measure: its label, unit,
format, how it is derived, and the plain-language explanation that must
accompany it. It holds no thresholds and no decision power, because deciding
is a strategy's job and the same host has to serve strategies that contradict
each other.

This module is the only reader of that file. It ships with the program rather
than living in the user's data directory: the bank is part of what the
program *is*, and a measure's definition is not a user setting.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_DIR / "config"

_yaml = YAML()  # round-trip: keeps comments and key order for anyone reading
_yaml.preserve_quotes = True


def bank_path(name: str) -> Path:
    return CONFIG_DIR / (name + ".yaml")


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return _yaml.load(f)


def to_plain(node):
    """Strip ruamel types so nothing framework-shaped crosses a boundary."""
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


_bank_cache: dict = {}

# Kinds whose estimator reads a fixed-length window of annual observations, so
# `observations` says something and its absence is a hole. A streak has no
# fixed window and may leave it out; a reading at one date or over a trailing
# window has no annual observations to count, and stating one would be noise.
_WINDOWED = ("averaged", "median", "range")
_UNWINDOWED = ("instant", "trailing", "assessed")


def _check_estimator(entry) -> list:
    """Everything wrong with one entry's estimator declaration.

    Refused at load rather than tolerated, because what follows from it is
    how much evidence a breach of that measure needs. A missing estimator
    would have to fall back to something, and every fallback is either the
    strict one — which silently stops exits firing — or the loose one, which
    silently fires them on a single year. Both are quiet, and quiet is the
    failure this file exists to refuse.
    """
    from .contract import ESTIMATORS               # local: bank loads first
    eid = str(entry.get("id"))
    node = entry.get("estimator")
    if not isinstance(node, dict):
        return [f'{eid} declares no `estimator`. Every entry says how it is '
                f'read — one of {", ".join(ESTIMATORS)} — because how much '
                "evidence a breach of it needs is derived from that."]
    kind = str(node.get("kind") or "")
    if kind not in ESTIMATORS:
        return [f'{eid} declares estimator kind "{kind or "nothing"}", which '
                f'is not one of {", ".join(ESTIMATORS)}. Adding a kind is a '
                "host change in engine/contract.py, never a new word here."]
    unknown = set(node) - {"kind", "observations"}
    if unknown:
        return [f"{eid}: an estimator carries `kind` and `observations` and "
                "nothing else; found " + ", ".join(sorted(unknown)) + "."]
    obs = node.get("observations")
    if obs is not None and (not isinstance(obs, int) or isinstance(obs, bool)
                            or obs < 2):
        return [f"{eid}: `observations` counts the annual observations the "
                "estimator reads, so it is a whole number of at least two."]
    if kind in _WINDOWED and obs is None:
        return [f"{eid}: a {kind} estimator reads a window of fixed length, "
                "so it has to say how many annual observations are in it — "
                "a three-point median and a five-point one do not resist an "
                "outlier equally."]
    if kind in _UNWINDOWED and obs is not None:
        return [f"{eid}: a {kind} estimator reads no window of annual "
                "observations, so `observations` says nothing about it."]
    return []


def load_bank(name: str = "metric-bank"):
    path = bank_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f'The metric bank "{name}" was not found at {path}.')
    # Round-trip parsing a 2,000-line YAML costs real time and a render asks
    # for the bank several times; cache by mtime so edits still show up
    # without a restart. The doc is treated as read-only everywhere.
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
    problems = [p for e in (doc.get("entries") or [])
                for p in _check_estimator(e)]
    if problems:
        raise ValueError(f"{path.name} cannot be loaded:\n  "
                         + "\n  ".join(problems))
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


def meta(name: str = "metric-bank") -> dict:
    """Per measure, what a screen needs to render it: label, unit, format,
    kind, favourable direction, and the plain-language explanation. The
    explanation travels because a number without one is incomplete."""
    doc = load_bank(name)
    out = {}
    for e in (doc.get("entries") or []):
        expl = e.get("explanation") or {}
        out[str(e.get("id"))] = {
            "label": to_plain(e.get("label")),
            "unit": to_plain(e.get("unit")),
            "format": to_plain(e.get("format")),
            "kind": to_plain(e.get("kind")),
            "polarity": to_plain(e.get("polarity")),
            "plain": to_plain(expl.get("plain")),
        }
    return out
