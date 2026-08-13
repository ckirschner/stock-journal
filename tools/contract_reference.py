"""The reference tables in docs/WRITING-A-STRATEGY.md, generated from the
host's own tables.

A strategy cites the host rather than quoting it, for the reason principle 8
gives: a restatement can be wrong, and nothing checks it. Documentation is a
restatement. Every table in the reference is a host-owned mapping in
engine/contract.py, and a hand-typed copy of one goes stale the first time
somebody adds a comparator — silently, in the one place an author trusts to
be right.

So the tables are not written. They are generated from the mappings
themselves, into marked regions of the document, and tests/test_contract_docs
regenerates and compares. A table that has moved and a document that has not
is a failing test rather than a paragraph nobody re-reads.

    python -m tools.contract_reference            rewrite the document
    python -m tools.contract_reference --check    say whether it is stale

The prose around the regions is written by a person and is never touched:
what a thing is *for* cannot be generated, and generating half a document is
the only honest split.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import contract  # noqa: E402

DOC = Path(__file__).resolve().parent.parent / "docs" / "WRITING-A-STRATEGY.md"

_REGION = re.compile(
    r"(<!-- generated: (?P<name>[a-z-]+) -->\n).*?(<!-- end: (?P=name) -->)",
    re.DOTALL)


def _cell(text) -> str:
    """One table cell. Pipes would end the column and newlines the row, so
    both are flattened rather than escaped — a reference table is a summary
    and the long form lives in the code it came from."""
    return str(text).replace("|", "/").replace("\n", " ").strip()


def _table(headings, rows) -> str:
    out = ["| " + " | ".join(headings) + " |",
           "|" + "|".join("---" for _ in headings) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return "\n".join(out)


def _code(values) -> str:
    return ", ".join(f"`{v}`" for v in values)


def _yes(flag) -> str:
    return "yes" if flag else "—"


# ---------------------------------------------------------------------------
# one function per marked region
# ---------------------------------------------------------------------------

def _render_types() -> str:
    return _table(
        ["`render`", "tier", "means", "payload keys", "may also carry",
         "needs attention", "a strategy may declare it"],
        [(f"`{k}`", v["tier"], v["meaning"],
          _code(v["payload_keys"]) or "— (none)",
          _code(v["optional_keys"]) or "—", _yes(v["attention"]),
          _yes(not v["host_only"]))
         for k, v in sorted(contract.RENDER_TYPES.items(),
                            key=lambda kv: kv[1]["order"])])


def _state_fixes() -> str:
    return _table(
        ["`fix`", "button", "where it goes", "must cite"],
        [(f"`{k}`", v["label"], v["where"],
          f'a bank entry of kind `{v["cites"]}`, however it is cited'
          if v["cites"] else "—")
         for k, v in contract.STATE_FIXES.items()])


def _host_states() -> str:
    return _table(
        ["state", "`render`", "shown as", "way out"],
        [(f"`{k}`", f'`{v["render"]}`', v["name"],
          f'`{v["fix"]}`' if v["fix"] else "nothing in the app resolves it")
         for k, v in contract.HOST_STATES.items()])


def _comparators() -> str:
    return _table(
        ["`comparator`", "reads as", "numbers and dates only"],
        [(f"`{k}`", v["phrase"], _yes(v["numeric_only"]))
         for k, v in contract.COMPARATORS.items()])


def _host_facts() -> str:
    return _table(
        ["`fact`", "label", "unit"],
        [(f"`{k}`", v["label"], f'`{v["unit"]}`')
         for k, v in contract.HOST_FACTS.items()])


def _baseline_anchors() -> str:
    return _table(
        ["`since`", "reads as", "the moment it anchors to"],
        [(f"`{k}`", v["label"], v["means"])
         for k, v in contract.BASELINE_ANCHORS.items()])


def _change_forms() -> str:
    return _table(
        ["`change`", "the row's unit", "reads as"],
        [(f"`{k}`",
          "`percent`" if k == "proportion" else "the measure's own",
          f'"…, change since you bought{v["suffix"]}"')
         for k, v in contract.CHANGE_FORMS.items()])


def _industry_classes() -> str:
    return _table(
        ["`class`", "reads as", "the refusal reads \"does not evaluate …\"",
         "the filers it covers"],
        [(f"`{k}`", v["label"], v["noun"], v["means"])
         for k, v in contract.INDUSTRY_CLASSES.items()])


def _estimators() -> str:
    return _table(
        ["`kind`", "reads as", "a breach needs", "counted in",
         "must survive dropping a year"],
        [(f"`{k}`", v["label"], v["confirmations"],
          contract.CLOCKS[v["clock"]]["noun"],
          {"no": "—", "always": "yes",
           "short-window":
               f'under {contract.BREAKDOWN_OBSERVATIONS} observations'}
          [v["robustness"]])
         for k, v in contract.ESTIMATORS.items()])


def _clocks() -> str:
    return _table(
        ["`clock`", "counts", "which are"],
        [(f"`{k}`", v["noun"], v["means"])
         for k, v in contract.CLOCKS.items()])


def _robustness() -> str:
    return _table(
        ["`without`", "reads as"],
        [(f"`{k}`", v["label"]) for k, v in contract.ROBUSTNESS.items()])


def _input_roles() -> str:
    return _table(
        ["`role`", "declared as", "means", "unlocks"],
        [(f"`{k}`", f'`{v["type"]}` in `{v["unit"]}`', v["means"],
          _code(v["reports"]))
         for k, v in contract.INPUT_ROLES.items()])


def _vocabulary() -> str:
    return "\n".join([
        f"- **Contract version** — `{contract.CONTRACT_VERSION}`. A "
        "declaration naming any other is refused at load.",
        f"- **Most states one strategy may declare** — "
        f"`{contract.MAX_STATES}`.",
        f"- **Declared field types** — {_code(contract.VALUE_TYPES)}.",
        f"- **Units a `size` may be in** — {_code(contract.SIZE_UNITS)} "
        "(`weight` is a percent number).",
        f"- **Units a cited figure may render in** — "
        f"{_code(contract.EVIDENCE_UNITS)}. A strategy picks one; it never "
        "invents a rendering.",
        f"- **How a comparison can come out** — {_code(contract.OUTCOMES)}. "
        "The host derives one; a strategy branches on it and never asserts "
        "one.",
        f"- **How an established breach can come out** — "
        f"{_code(contract.CONFIRMATIONS)}. `contract.confirm` derives one; a "
        "strategy branches on it and never asserts one.",
        f"- **Observations at which a median stops needing help** — "
        f"`{contract.BREAKDOWN_OBSERVATIONS}`. Below it, a breach of a "
        "median must also survive dropping a year.",
        f"- **What a group may demand** — "
        f"{_code(contract.GROUP_REQUIREMENTS)}.",
    ])


BLOCKS = {
    "render-types": _render_types,
    "state-fixes": _state_fixes,
    "host-states": _host_states,
    "comparators": _comparators,
    "host-facts": _host_facts,
    "baseline-anchors": _baseline_anchors,
    "change-forms": _change_forms,
    "estimators": _estimators,
    "clocks": _clocks,
    "robustness": _robustness,
    "industry-classes": _industry_classes,
    "input-roles": _input_roles,
    "vocabulary": _vocabulary,
}


def render(text: str) -> str:
    """The document with every marked region refilled from the host.

    Raises where a region names something this tool does not generate: a
    marker nobody fills would leave a stale table behind the very check that
    exists to catch stale tables.
    """
    named = {m.group("name") for m in _REGION.finditer(text)}
    unknown = sorted(named - set(BLOCKS))
    if unknown:
        raise ValueError(
            f'{DOC.name} marks region(s) this tool does not generate: '
            + ", ".join(unknown) + ". Add a block or drop the marker.")
    missing = sorted(set(BLOCKS) - named)
    if missing:
        raise ValueError(
            f"{DOC.name} has no region for: " + ", ".join(missing)
            + ". Every generated table has to be somewhere in the document, "
              "or it is generated into nothing.")
    return _REGION.sub(
        lambda m: m.group(1) + BLOCKS[m.group("name")]() + "\n" + m.group(3),
        text)


def main(argv) -> int:
    text = DOC.read_text(encoding="utf-8")
    fresh = render(text)
    if "--check" in argv:
        if fresh == text:
            return 0
        print(f"{DOC} is out of date with engine/contract.py. Run "
              "`python -m tools.contract_reference`.")
        return 1
    if fresh != text:
        DOC.write_text(fresh, encoding="utf-8")
        print(f"Rewrote {DOC}.")
    else:
        print(f"{DOC} is already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
