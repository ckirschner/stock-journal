"""Discovering and loading strategies. Discovery over registration: the host
loads what it finds, and adding a strategy means adding a bundle — there is
no central list to edit.

A bundle is a directory holding:

    strategy.py     the declaration (STRATEGY, a plain dict) and the logic
                    (decide, a function of one context dict)
    values.yaml     shipped defaults for the declared values, with their
                    version
    anything else   reference data the strategy ships; the host never
                    touches it

Loading is defensive at every step. A bundle that fails to import, declares
itself badly, speaks the wrong contract version, moves its version without
saying what changed, or ships defaults that don't match its declaration is
*refused*: reported with a legible message naming the file, and skipped
without preventing any other bundle from loading. Nothing here raises for a
bad bundle — a broken plugin is a page fact, never a crashed application.

Importing a bundle runs its module top level, which is how the declaration
is read; the strategy's decide logic is never called here. That distinction
is what lets the host build a setup screen and validate a journal before any
decision is made.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

from ruamel.yaml import YAML

from . import contract, strategy_values

APP_DIR = Path(__file__).resolve().parent.parent
SHIPPED_DIR = APP_DIR / "strategies"

_yaml = YAML(typ="safe")


def _plain(node):
    """Strip YAML library types so nothing framework-shaped enters a record."""
    if isinstance(node, dict):
        return {_plain(k): _plain(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [_plain(v) for v in node]
    if node is None or isinstance(node, (bool, int, float)):
        return node
    return str(node)


def _read_values_yaml(path: Path):
    """(doc, error). doc is None when the file does not exist — a fact the
    caller judges against the declaration, not an error by itself. A file
    that exists but holds nothing is its own error, because telling an
    author a file is missing when they are looking at it names the wrong
    fix."""
    if not path.exists():
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            doc = _plain(_yaml.load(f))
    except Exception as e:  # noqa: BLE001 — a bad file is a report, not a crash
        return None, (f"{path.name} could not be read as YAML: "
                      f"{type(e).__name__}: {e}")
    if doc is None:
        return None, (f"{path.name} is empty. It must carry a `version` and "
                      "a `values` mapping holding one default per declared "
                      "value.")
    return doc, None


def _import_bundle(py: Path):
    """(module, error) — the only place strategy code is executed at load."""
    stamp = hashlib.sha256(str(py).encode()).hexdigest()[:8]
    name = f"ledger_strategy_{py.parent.name}_{stamp}"
    try:
        spec = importlib.util.spec_from_file_location(name, py)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, None
    except (Exception, SystemExit) as e:  # noqa: BLE001 — contain everything
        return None, (f"{py.parent.name}/{py.name} failed to load: "
                      f"{type(e).__name__}: {e}")


def _load_bundle(bundle_dir: Path) -> dict:
    """One bundle to one report: {"dir", "ok", "id", "name", "errors",
    "record"} where record is present only when ok."""
    label = bundle_dir.name
    report = {"dir": str(bundle_dir), "ok": False, "id": None,
              "name": label, "errors": []}

    module, err = _import_bundle(bundle_dir / "strategy.py")
    if err:
        report["errors"].append(err)
        return report

    decl = getattr(module, "STRATEGY", None)
    if decl is None:
        report["errors"].append(
            f"{label}/strategy.py does not define STRATEGY — the "
            "declaration the host reads without running any logic.")
        return report
    decide = getattr(module, "decide", None)
    if not callable(decide):
        report["errors"].append(
            f"{label}/strategy.py does not define decide(ctx) — the one "
            "function that turns a context into a decision.")

    decl_errors = contract.validate_declaration(decl)
    if decl_errors:
        report["errors"].extend(
            f"{label}/strategy.py: {e}" for e in decl_errors)
    if report["errors"]:
        if isinstance(decl, dict):
            report["id"] = decl.get("id") or None
            if decl.get("name"):
                report["name"] = str(decl["name"])
        return report

    report["id"], report["name"] = decl["id"], decl["name"]

    values_doc, err = _read_values_yaml(bundle_dir / "values.yaml")
    if err:
        report["errors"].append(f"{label}: {err}")
        return report
    default_errors = strategy_values.check_defaults(
        decl, values_doc, f"{label}/values.yaml")
    if default_errors:
        report["errors"].extend(default_errors)
        return report

    record = {k: decl[k] for k in ("id", "name", "summary", "version",
                                   "contract", "changelog", "states")}
    record["inputs"] = decl.get("inputs", [])
    record["values"] = decl.get("values", [])
    record["defaults"] = dict((values_doc or {}).get("values") or {})
    record["values_version"] = (values_doc or {}).get("version")
    record["dir"] = str(bundle_dir)
    record["decide"] = decide
    report["ok"], report["record"] = True, record
    return report


def discover(roots=None) -> tuple[dict, list]:
    """(strategies, reports): every loadable strategy keyed by its declared
    id, and one report per bundle found — including the refused ones, so
    the screen can say exactly why something is not offered.

    `roots` is an ordered list of directories to scan; by default the
    shipped strategies directory. A root that does not exist is simply
    empty. Two bundles claiming the same id are both refused: a journal is
    stamped with an id, and guessing which claimant it meant would evaluate
    it under rules its author never chose.
    """
    roots = [Path(r) for r in (roots if roots is not None else [SHIPPED_DIR])]
    reports = []
    for root in roots:
        if not root.is_dir():
            continue
        for py in sorted(root.glob("*/strategy.py")):
            reports.append(_load_bundle(py.parent))

    by_id: dict[str, list] = {}
    for r in reports:
        if r["ok"]:
            by_id.setdefault(r["id"], []).append(r)
    strategies = {}
    for sid, claimants in by_id.items():
        if len(claimants) > 1:
            dirs = ", ".join(Path(c["dir"]).name for c in claimants)
            for c in claimants:
                c["ok"] = False
                c.pop("record", None)
                c["errors"].append(
                    f'Two bundles declare the id "{sid}" ({dirs}). Both are '
                    "refused — a journal stamped with this id cannot know "
                    "which rules it would get.")
        else:
            strategies[sid] = claimants[0]["record"]
    return strategies, reports
