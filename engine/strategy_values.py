"""The declared-values resolution chain.

A strategy ships defaults in its bundle's values.yaml; a journal's override
is stamped on the journal; a machine-level layer between them is parked but
not rejected. So resolution is a chain, not a pair: defaults first, then
every override layer in the order given, later layers winning — and the
journal is always handed last.

Merging is per value. A strategy that gains a new setting picks up its
shipped default even in a journal that already overrides something else.

Failure is loud and complete. An unrecognised key, a mistyped value, or a
default missing for a declared value produces a sentence naming the file and
the key — every problem at once, not the first one found — because a setting
that silently does nothing is worse than one that refuses to load. When any
layer has errors the caller must refuse to evaluate: proceeding on defaults
the user believes they overrode would be the quiet retuning this program
exists to prevent.
"""

from __future__ import annotations

import difflib

from .contract import check_typed_value

_DEFAULTS_KEYS = {"version", "values"}


def _suggest(key: str, known) -> str:
    close = difflib.get_close_matches(str(key), list(known), n=1)
    return f' Did you mean "{close[0]}"?' if close else ""


def check_defaults(decl: dict, doc, source: str) -> list[str]:
    """Every problem with a bundle's shipped values.yaml, as sentences.

    `doc` is the parsed file; `source` names it for the messages. The file
    must carry a version and one default per declared value — a declared
    value without a default is an input wearing the wrong hat, and a default
    for an undeclared value is a setting that would silently do nothing.
    """
    declared = {v["id"]: v for v in decl.get("values", [])}
    if doc is None:
        if not declared:
            return []
        return [f"{source} is missing, but the strategy declares "
                f"{len(declared)} tuning value(s). Every declared value "
                "ships a default."]
    errors = []
    if not isinstance(doc, dict):
        return [f"{source} must be a mapping with `version` and `values`."]
    unknown = sorted(set(doc) - _DEFAULTS_KEYS)
    if unknown:
        errors.append(f"{source} has keys this contract does not know: "
                      + ", ".join(map(str, unknown)) + ".")
    version = doc.get("version")
    if not (isinstance(version, int) and not isinstance(version, bool)
            and version >= 1):
        errors.append(f"{source} needs `version`, a whole number starting "
                      "at 1 — it is what makes a change to these values "
                      "recordable.")
    values = doc.get("values")
    if values is None:
        values = {}
    if not isinstance(values, dict):
        errors.append(f"{source}: `values` must be a mapping of value id "
                      "to default.")
        values = {}
    for key, value in values.items():
        spec = declared.get(key)
        if spec is None:
            errors.append(f'{source} sets "{key}", which this strategy does '
                          f"not declare.{_suggest(key, declared)}")
            continue
        issue = check_typed_value(spec, value)
        if issue:
            errors.append(f"{source}: {issue}")
    for key in declared:
        if key not in values:
            errors.append(f'{source} ships no default for "{key}". Every '
                          "declared value ships a default; something the "
                          "user must supply is an input, not a value.")
    return errors


def resolve(record: dict, layers=()) -> dict:
    """Resolve a strategy's values through the chain.

    `layers` is an ordered sequence of (source, mapping) pairs, lowest
    precedence first, the journal's override last. Returns::

        {"values": {id: value},        # the resolved chain
         "sources": {id: source},      # where each value came from
         "errors": [sentence, ...]}    # every problem, naming file and key

    `sources` uses "shipped default" for untouched values, so a screen can
    always say "yours: 12 (shipped default: 15)" — the resolution is a view
    and never loses a side.
    """
    declared = {v["id"]: v for v in record.get("values", [])}
    values = dict(record.get("defaults") or {})
    sources = {k: "shipped default" for k in values}
    errors: list[str] = []

    for source, mapping in layers:
        if mapping is None:
            continue
        if not isinstance(mapping, dict):
            errors.append(f"{source} must be a mapping of value id to "
                          "value.")
            continue
        for key, value in mapping.items():
            spec = declared.get(key)
            if spec is None:
                errors.append(f'{source} sets "{key}", which '
                              f'{record.get("name", "this strategy")} does '
                              f"not declare.{_suggest(key, declared)}")
                continue
            issue = check_typed_value(spec, value)
            if issue:
                errors.append(f"{source}: {issue}")
                continue
            values[key] = value
            sources[key] = source

    return {"values": values, "sources": sources, "errors": errors}
