"""Discovering and loading strategies. Discovery over registration: the host
loads what it finds, and adding a strategy means adding a bundle — there is
no central list to edit.

A bundle is a directory holding:

    strategy.py     the declaration (STRATEGY, a plain dict) and the logic
                    (decide, a function of one context dict)
    values.yaml     shipped defaults for the declared values, with their
                    version
    reference files static data the strategy ships and the host does not
                    have — a sector map, a lookup table. Declared by name in
                    STRATEGY["reference"], loaded here, and handed back
                    through the context frozen. The host parses these files
                    and holds no opinion about what is in them; loading them
                    is what keeps a strategy from opening files itself.

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
import json
from pathlib import Path
from types import MappingProxyType

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


def _freeze(node):
    """A read-only view of parsed reference data.

    Reference data is read once at load and handed to every evaluation, so
    it must not be copied per security (a sector map would be copied for
    every holding on every refresh) and must not be mutable (one strategy
    call could then change what the next one sees). Freezing answers both:
    reads work exactly as they do on a dict or list, and writes cannot
    happen at all.
    """
    if isinstance(node, dict):
        return MappingProxyType({k: _freeze(v) for k, v in node.items()})
    if isinstance(node, (list, tuple)):
        return tuple(_freeze(v) for v in node)
    return node


def _read_reference(bundle_dir: Path, names) -> tuple[dict, list]:
    """(data, errors) — every declared reference file, parsed and frozen.

    A declared file that is missing or unparseable refuses the bundle: a
    strategy that reads half its lookup table would produce plausible wrong
    answers, which is worse than not loading.
    """
    data, errors = {}, []
    for name in names:
        path = bundle_dir / name
        if not path.exists():
            errors.append(f"{bundle_dir.name}/{name} is declared in "
                          "`reference` but is not in the bundle.")
            continue
        try:
            text = path.read_text(encoding="utf-8")
            parsed = json.loads(text) if name.endswith(".json") \
                else _yaml.load(text)
        except Exception as e:  # noqa: BLE001 — a bad file is a report
            errors.append(f"{bundle_dir.name}/{name} could not be read: "
                          f"{type(e).__name__}: {e}")
            continue
        if parsed is None:
            errors.append(f"{bundle_dir.name}/{name} is empty.")
            continue
        data[name] = _freeze(_plain(parsed))
    return data, errors


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

    reference, ref_errors = _read_reference(bundle_dir,
                                            decl.get("reference", []))
    if ref_errors:
        report["errors"].extend(ref_errors)
        return report

    record = {k: decl[k] for k in ("id", "name", "summary", "version",
                                   "contract", "changelog", "states")}
    record["inputs"] = decl.get("inputs", [])
    record["values"] = decl.get("values", [])
    # What this strategy will not evaluate, carried on the record so the host
    # can answer for a declined company without importing the bundle again —
    # and so the screen that offers a strategy can say what it covers before
    # any journal is stamped with it.
    record["declines"] = decl.get("declines", [])
    # What the METHOD asks for or admits to that this program does not do —
    # prose the screen renders and nothing reads. Carried on the record for
    # the same reason `declines` is: a reader choosing a strategy should be
    # able to see what it does not promise before a journal is stamped with
    # it, not after the first verdict.
    record["limits"] = decl.get("limits", [])
    # Whether this strategy works from a list somebody else chose. Carried on
    # the record for the third time for the same reason: it decides whether a
    # journal shows an import screen and whether the host serves the `list.*`
    # facts, and both of those are settled before any verdict exists.
    record["list"] = decl.get("list")
    # The measures this strategy may cite, and who it is for. Both are what
    # the chooser and the reference screens speak from before any journal
    # exists — and `reads` is a promise: evaluation refuses a citation
    # outside it, so a record that dropped it here would silently drop the
    # enforcement with it.
    if "reads" in decl:
        record["reads"] = tuple(decl["reads"])
    record["audience"] = decl.get("audience")
    record["reference"] = MappingProxyType(reference)
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
