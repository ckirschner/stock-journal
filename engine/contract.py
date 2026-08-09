"""The host/strategy contract.

The host is the rendering engine; a strategy is the decision engine. This
module is the line between them: what a strategy must declare about itself,
what it receives, what it must return, and the six render types the host owns.

Everything that crosses the line is plain data. A strategy is handed one plain
dict (built in engine/context.py) and returns one plain dict — a state it
declared, a payload shaped by that state's render type, and a structured
reason. The host validates both directions and refuses, legibly, anything
that doesn't conform. A strategy never invents vocabulary: an undeclared
state, an unknown payload key, or a render type of its own devising is an
error in place, not a new feature.

Nothing in this module holds an opinion about investing. Whether 15 is a good
P/E is a strategy's business; that a decision must name its rule is the
host's.
"""

from __future__ import annotations

import traceback
from datetime import date
from types import MappingProxyType

# The version of this contract. A strategy declares the version it speaks;
# the host refuses any other. Bumped only when the shape of what a strategy
# receives or returns changes incompatibly — adding a key to the context is
# not a bump, because strategies must tolerate keys they don't read.
CONTRACT_VERSION = 1

# A strategy may declare at most this many states. The cap is deliberate:
# states are user-facing vocabulary, and complexity must not creep back in
# through the plugin door.
MAX_STATES = 12

_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-"


# ---------------------------------------------------------------------------
# The six render types — the one permanent host-owned list.
#
# Internal only; a user never sees these words. They exist so the host can
# render, sort, count and aggregate a state whose meaning it does not know.
# Four are about the security, two are about the evaluation, and the two
# tiers must never be averaged together — "4 of 12 are hold" is a portfolio
# fact, "4 of 12 cannot be evaluated" is a data problem.
#
# The mapping is a read-only proxy over dicts with tuple values: nothing
# outside this file can add a type or edit one, by construction rather than
# by convention. Adding a type is a host change and a deliberate one.
# ---------------------------------------------------------------------------

def _rt(tier, meaning, order, attention, payload_keys):
    return MappingProxyType({
        "tier": tier,                    # "position" | "evaluation"
        "meaning": meaning,              # for the contract docs, not the user
        "order": order,                  # sort rank across a list of results
        "attention": attention,          # surfaces in "needs attention"
        "payload_keys": payload_keys,    # exactly these keys, no others
    })


RENDER_TYPES = MappingProxyType({
    "commit":  _rt("position", "capital may go in", 0, True,
                   ("size", "condition")),
    "reduce":  _rt("position", "partial exit", 1, True, ("to",)),
    "close":   _rt("position", "full exit", 2, True, ("when",)),
    "hold":    _rt("position", "no action", 3, False, ()),
    "blocked": _rt("evaluation",
                   "a decision is owed from the user before any verdict",
                   4, True, ("needs",)),
    "unknown": _rt("evaluation", "not enough data to say", 5, True, ()),
})

# States the host itself may produce when no strategy verdict exists. They
# are machinery, not opinion — "we could not ask the strategy" is a fact
# about the evaluation, and the host is allowed to know it. The "host:"
# prefix is reserved; a strategy declaring a state with it is refused.
HOST_STATES = MappingProxyType({
    "host:inputs-missing": MappingProxyType({
        "render": "blocked", "name": "Waiting on setup",
        "description": "The strategy needs information from you before it "
                       "can produce a verdict."}),
    "host:strategy-missing": MappingProxyType({
        "render": "blocked", "name": "Strategy not installed",
        "description": "The strategy this journal is stamped with is not on "
                       "this machine. History remains readable; new verdicts "
                       "need the strategy present."}),
    "host:values-unresolved": MappingProxyType({
        "render": "blocked", "name": "Settings need fixing",
        "description": "The strategy's declared values could not be "
                       "resolved, so no verdict can honestly be produced."}),
    "host:strategy-error": MappingProxyType({
        "render": "unknown", "name": "Strategy failed",
        "description": "The strategy's own logic failed while deciding. "
                       "This is a problem with the strategy, not with your "
                       "data or your decision."}),
    "host:invalid-decision": MappingProxyType({
        "render": "unknown", "name": "Strategy failed",
        "description": "The strategy returned something outside the "
                       "contract, so its verdict cannot be trusted or "
                       "shown."}),
})

VALUE_TYPES = ("number", "integer", "boolean", "text")
SIZE_UNITS = ("weight", "usd", "shares")   # weight is a percent number


# ---------------------------------------------------------------------------
# small checks
# ---------------------------------------------------------------------------

def _is_id(s) -> bool:
    return (isinstance(s, str) and s != "" and s[0].isalpha()
            and all(c in _ID_CHARS for c in s))


def _is_text(s) -> bool:
    return isinstance(s, str) and s.strip() != ""


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_date(s) -> bool:
    if not isinstance(s, str):
        return False
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def check_typed_value(spec: dict, value) -> str | None:
    """Does `value` fit a declared input or value? None, or one legible
    sentence saying what was expected and what arrived."""
    label = f'"{spec["id"]}"'
    t = spec["type"]
    if t == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
        expected = "a whole number"
    elif t == "number":
        ok = _is_num(value)
        expected = "a number"
    elif t == "boolean":
        ok = isinstance(value, bool)
        expected = "yes or no (true/false)"
    else:  # text
        ok = isinstance(value, str)
        expected = "text"
    if not ok:
        got = "nothing" if value is None else f"{value!r}"
        return f"{label} expects {expected}, not {got}."
    if t in ("integer", "number"):
        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None and value < lo:
            return f"{label} must be at least {lo}; {value} is below that."
        if hi is not None and value > hi:
            return f"{label} must be at most {hi}; {value} is above that."
    return None


# ---------------------------------------------------------------------------
# the declaration
# ---------------------------------------------------------------------------

_DECL_KEYS = {"id", "name", "summary", "version", "contract", "changelog",
              "states", "inputs", "values"}
_STATE_KEYS = {"id", "name", "description", "render"}
_FIELD_KEYS = {"id", "label", "type", "unit", "required", "min", "max",
               "explain"}


def _check_fields(kind: str, fields, errors: list) -> None:
    """Shared validation for declared inputs and declared values. `kind` is
    "input" or "value" — values never carry `required`, because every value
    ships a default; a value the user must supply is an input."""
    if not isinstance(fields, list):
        errors.append(f"`{kind}s` must be a list.")
        return
    seen = set()
    for i, f in enumerate(fields):
        where = f'{kind} {i + 1}'
        if not isinstance(f, dict):
            errors.append(f"{where} must be a mapping, not {type(f).__name__}.")
            continue
        if _is_id(f.get("id")):
            where = f'{kind} "{f["id"]}"'
            if f["id"] in seen:
                errors.append(f"{where} is declared twice.")
            seen.add(f["id"])
        else:
            errors.append(f'{where} needs an `id` in lowercase letters, '
                          "digits and hyphens.")
        unknown = set(f) - _FIELD_KEYS
        if unknown:
            errors.append(f"{where} has keys this contract does not know: "
                          f"{', '.join(sorted(map(str, unknown)))}.")
        if kind == "value" and "required" in f:
            errors.append(f"{where} declares `required`, but every value "
                          "ships a default — something the user must supply "
                          "is an input, not a value.")
        if not _is_text(f.get("label")):
            errors.append(f"{where} needs a user-facing `label`.")
        if f.get("type") not in VALUE_TYPES:
            errors.append(f"{where} needs a `type` from: "
                          f"{', '.join(VALUE_TYPES)}.")
        if not _is_text(f.get("explain")):
            errors.append(f"{where} needs an `explain` — plain language for "
                          "someone who has never valued a company. A field "
                          "without an explanation is incomplete, not a "
                          "follow-up ticket.")
        for bound in ("min", "max"):
            if bound in f and not _is_num(f[bound]):
                errors.append(f"{where}: `{bound}` must be a number.")
        if ("min" in f or "max" in f) and f.get("type") in ("boolean", "text"):
            errors.append(f"{where}: min/max only mean something for "
                          "numbers.")


def validate_declaration(decl) -> list[str]:
    """Every problem with a STRATEGY declaration, as legible sentences.

    An empty list means the declaration is well-formed and speaks this
    contract. Everything is checked without touching the strategy's decide
    logic — this is exactly what lets the host build a setup screen and
    validate a journal before any decision is made.
    """
    if not isinstance(decl, dict):
        return ["STRATEGY must be a mapping (a plain dict)."]
    errors: list[str] = []

    unknown = set(decl) - _DECL_KEYS
    if unknown:
        errors.append("STRATEGY has keys this contract does not know: "
                      + ", ".join(sorted(map(str, unknown)))
                      + ". Unknown keys fail loudly rather than silently "
                        "doing nothing.")

    if not _is_id(decl.get("id")):
        errors.append("`id` must be lowercase letters, digits and hyphens, "
                      "starting with a letter.")
    if not _is_text(decl.get("name")):
        errors.append("`name` must be a user-facing name.")
    if not _is_text(decl.get("summary")):
        errors.append("`summary` must say, in plain language, what this "
                      "strategy is.")

    version = decl.get("version")
    if not (isinstance(version, int) and not isinstance(version, bool)
            and version >= 1):
        errors.append("`version` must be a whole number starting at 1.")
        version = None

    if decl.get("contract") != CONTRACT_VERSION:
        errors.append(f"`contract` must be {CONTRACT_VERSION} — the contract "
                      "version this host speaks. A strategy written for "
                      "another version is refused rather than run wrongly.")

    changelog = decl.get("changelog")
    if not isinstance(changelog, dict) or not changelog:
        errors.append("`changelog` must map each version number to a "
                      "sentence saying what changed in that version.")
    else:
        for k, v in changelog.items():
            if not (isinstance(k, int) and not isinstance(k, bool)) \
                    or not _is_text(v):
                errors.append("`changelog` entries must map a version number "
                              f"to non-empty text; {k!r} does not.")
        if version is not None and version not in changelog:
            errors.append(f"version {version} has no changelog entry. A "
                          "version that does not say what changed is "
                          "refused — the record of rule changes depends on "
                          "it.")

    states = decl.get("states")
    if not isinstance(states, list) or not states:
        errors.append("`states` must be a non-empty list.")
        states = []
    if len(states) > MAX_STATES:
        errors.append(f"{len(states)} states is more than the cap of "
                      f"{MAX_STATES}. Fewer, clearer states — the cap is "
                      "how complexity is kept out.")
    seen = set()
    for i, s in enumerate(states):
        where = f"state {i + 1}"
        if not isinstance(s, dict):
            errors.append(f"{where} must be a mapping.")
            continue
        sid = s.get("id")
        # The host's own states are "host:..." — a colon the id alphabet
        # excludes, so no declared state can ever collide with one. The
        # namespace is protected by construction, not by a check.
        if _is_id(sid):
            where = f'state "{sid}"'
            if sid in seen:
                errors.append(f"{where} is declared twice.")
            seen.add(sid)
        else:
            errors.append(f"{where} needs an `id` in lowercase letters, "
                          "digits and hyphens.")
        unknown = set(s) - _STATE_KEYS
        if unknown:
            errors.append(f"{where} has keys this contract does not know: "
                          f"{', '.join(sorted(map(str, unknown)))}.")
        if not _is_text(s.get("name")):
            errors.append(f"{where} needs a user-facing `name`.")
        if not _is_text(s.get("description")):
            errors.append(f"{where} needs a `description` in plain "
                          "language.")
        if s.get("render") not in RENDER_TYPES:
            errors.append(f"{where} must set `render` to one of the host's "
                          f"six types ({', '.join(RENDER_TYPES)}). A "
                          "strategy cannot add a render type.")

    _check_fields("input", decl.get("inputs", []), errors)
    _check_fields("value", decl.get("values", []), errors)

    input_ids = {f.get("id") for f in decl.get("inputs", [])
                 if isinstance(f, dict)}
    value_ids = {f.get("id") for f in decl.get("values", [])
                 if isinstance(f, dict)}
    for shared in sorted(x for x in input_ids & value_ids if x):
        errors.append(f'"{shared}" is declared as both an input and a '
                      "value. Give one of them a different id — sharing a "
                      "name invites the wrong one being read.")
    return errors


# ---------------------------------------------------------------------------
# what the user supplied
# ---------------------------------------------------------------------------

def validate_inputs(record: dict, supplied: dict) -> list[str]:
    """Problems with the user-supplied inputs, as sentences a novice can
    act on. Run at journal open ("validate at load, not at evaluation")
    and again defensively before every decision."""
    problems = []
    declared = {f["id"]: f for f in record.get("inputs", [])}
    for key in supplied:
        if key not in declared:
            problems.append(f'The journal supplies "{key}", which '
                            f'{record.get("name", "this strategy")} does '
                            "not ask for.")
    for fid, spec in declared.items():
        value = supplied.get(fid)
        if value is None:
            if spec.get("required"):
                problems.append(f'"{spec["label"]}" ({fid}) is needed and '
                                "the journal does not have it yet. "
                                + str(spec["explain"]).strip())
            continue
        issue = check_typed_value(spec, value)
        if issue:
            problems.append(f'"{spec["label"]}": {issue}')
    return problems


# ---------------------------------------------------------------------------
# the decision
# ---------------------------------------------------------------------------

_DECISION_KEYS = {"state", "payload", "reason"}
_REASON_KEYS = {"rule", "summary", "data"}


def _names(keys) -> str:
    """Key names for a message. Sorted by their text, because a plugin may
    hand back keys of mixed types and comparing those would raise inside
    the very code whose job is to refuse them."""
    return ", ".join(sorted((str(k) for k in keys)))


def _check_payload(render: str, payload, errors: list) -> None:
    keys = RENDER_TYPES[render]["payload_keys"]
    if not isinstance(payload, dict):
        errors.append("`payload` must be a mapping.")
        return
    missing = [k for k in keys if k not in payload]
    extra = set(payload) - set(keys)
    if missing:
        errors.append(f"a `{render}` state's payload must carry: "
                      f"{', '.join(missing)}. A bare word is not a "
                      "decision.")
    if extra:
        errors.append(f"a `{render}` state's payload does not know: "
                      f"{_names(extra)}. Extra facts belong in the reason's "
                      "`data`.")
    if missing or extra:
        return

    if render == "commit":
        size = payload["size"]
        if not (isinstance(size, dict) and set(size) == {"unit", "value"}
                and size.get("unit") in SIZE_UNITS
                and _is_num(size.get("value")) and size["value"] > 0):
            errors.append("`size` must be {unit, value} with unit one of "
                          f"{', '.join(SIZE_UNITS)} and value above zero — "
                          "how much, or a staged entry collapses into buying "
                          "everything on day one.")
        cond = payload["condition"]
        if cond is not None and not (
                isinstance(cond, dict) and set(cond) == {"summary"}
                and _is_text(cond.get("summary"))):
            errors.append("`condition` must be None (commit now, "
                          "unconditionally) or {summary: plain language} "
                          "saying what must be true first.")
    elif render == "reduce":
        to = payload["to"]
        if not (isinstance(to, dict) and set(to) == {"unit", "value"}
                and to.get("unit") in ("weight", "shares")
                and _is_num(to.get("value")) and to["value"] >= 0):
            errors.append("`to` must be {unit, value} naming the level to "
                          "reduce to — weight (a percent number) or "
                          "shares.")
    elif render == "close":
        if not _is_date(payload["when"]):
            errors.append("`when` must be a YYYY-MM-DD date — the day the "
                          "exit is due. A close without a date makes a "
                          "scheduled exit fire months early.")
    elif render == "blocked":
        needs = payload["needs"]
        if not (isinstance(needs, list) and needs
                and all(_is_text(n) for n in needs)):
            errors.append("`needs` must be a non-empty list of sentences "
                          "saying what decision is owed from the user.")


def validate_decision(record: dict, decision) -> list[str]:
    """Everything wrong with what a strategy returned. Empty means the
    decision conforms and can be rendered."""
    if not isinstance(decision, dict):
        return ["the strategy returned "
                f"{type(decision).__name__ if decision is not None else 'nothing'}"
                ", not a decision mapping."]
    errors = []
    unknown = set(decision) - _DECISION_KEYS
    missing = _DECISION_KEYS - set(decision)
    if unknown:
        errors.append("the decision has keys this contract does not know: "
                      + _names(unknown) + ".")
    if missing:
        errors.append("the decision is missing: " + _names(missing) + ".")
        return errors

    states = {s["id"]: s for s in record.get("states", [])}
    sid = decision["state"]
    # A state id arrives from plugin code, so it may be any object at all —
    # including an unhashable one. Comparing by text refuses it as invented
    # vocabulary instead of raising inside the check that exists to refuse it.
    state = states.get(sid) if isinstance(sid, str) else None
    if state is None:
        errors.append(f"{sid!r} is not a state this strategy declared. A "
                      "strategy speaks only its own declared vocabulary.")
    else:
        _check_payload(state["render"], decision["payload"], errors)

    reason = decision["reason"]
    if not isinstance(reason, dict):
        errors.append("`reason` must be a mapping — a structured reason is "
                      "displayed at equal weight to the state, never free "
                      "text, never absent.")
    else:
        unknown = set(reason) - _REASON_KEYS
        if unknown:
            errors.append("`reason` has keys this contract does not know: "
                          + _names(unknown) + ".")
        if not _is_text(reason.get("rule")):
            errors.append("`reason.rule` must name the rule inside the "
                          "strategy that produced this state — a verdict "
                          "without its rule teaches nothing.")
        if not _is_text(reason.get("summary")):
            errors.append("`reason.summary` must say, in one plain "
                          "sentence, why this state and not another.")
        if "data" in reason and not isinstance(reason["data"], dict):
            errors.append("`reason.data` must be a mapping of the specific "
                          "figures that fired the rule.")
    return errors


# ---------------------------------------------------------------------------
# evaluation — one call, one state, contained failures
# ---------------------------------------------------------------------------

def _strategy_ref(record: dict | None) -> dict | None:
    if record is None:
        return None
    return {"id": record["id"], "name": record["name"],
            "version": record["version"],
            "values_version": record.get("values_version"),
            "contract": record["contract"]}


def _result(state_id, state, payload, reason, produced_by, record):
    render = state["render"]
    return {
        "render": render,
        "tier": RENDER_TYPES[render]["tier"],
        "state": {"id": state_id, "name": state["name"],
                  "description": state["description"]},
        "payload": payload,
        "reason": reason,
        "produced_by": produced_by,
        "strategy": _strategy_ref(record),
    }


def host_result(state_id: str, summary: str, record: dict | None = None,
                needs: list[str] | None = None,
                data: dict | None = None) -> dict:
    """A result the host produces itself when no strategy verdict exists —
    missing inputs, a missing strategy, a failure. Same envelope as a
    strategy's decision, so one screen renders both, but produced_by says
    which side is speaking and the reason never pretends to be a verdict."""
    state = HOST_STATES[state_id]
    payload = ({"needs": list(needs) if needs else [summary]}
               if state["render"] == "blocked" else {})
    reason = {"rule": state_id, "summary": summary}
    if data:
        reason["data"] = data
    return _result(state_id, state, payload, reason, "host", record)


def _failure_location(exc: BaseException, bundle_dir: str) -> str | None:
    """Where inside the strategy's own bundle the failure happened —
    "strategy.py line 12" — never a full path, never a stack trace."""
    try:
        frames = traceback.extract_tb(exc.__traceback__)
        inside = [f for f in frames
                  if str(f.filename).startswith(str(bundle_dir))]
        if inside:
            f = inside[-1]
            name = f.filename.rsplit("/", 1)[-1]
            return f"{name} line {f.lineno}"
    except Exception:  # noqa: BLE001 — locating a crash must never crash
        pass
    return None


def evaluate(record: dict, ctx: dict) -> dict:
    """Ask a loaded strategy for its one decision about one security.

    Never raises. Every way this can fail — inputs not yet supplied, the
    strategy's logic throwing, a decision outside the contract — comes back
    as a host-produced result in the same envelope: an error in place, not
    a crashed application, and never a blocked recording.
    """
    problems = validate_inputs(record, ctx.get("inputs") or {})
    if problems:
        return host_result(
            "host:inputs-missing",
            f'{record["name"]} needs information before it can produce a '
            "verdict.", record, needs=problems)

    try:
        decision = record["decide"](ctx)
    # BaseException, not Exception: a strategy calling sys.exit() must be
    # contained exactly like one raising — the host does not let plugin code
    # decide the application ends.
    except BaseException as e:  # noqa: BLE001 — a plugin must not sink the host
        where = _failure_location(e, record.get("dir", ""))
        at = f" (at {where})" if where else ""
        return host_result(
            "host:strategy-error",
            f'{record["name"]} failed while deciding: '
            f"{type(e).__name__}: {e}{at}. Your data and journal are "
            "untouched.", record)

    try:
        issues = validate_decision(record, decision)
    except Exception as e:  # noqa: BLE001 — checking must not raise either
        issues = [f"the decision could not even be checked "
                  f"({type(e).__name__}: {e})."]
    if issues:
        return host_result(
            "host:invalid-decision",
            f'{record["name"]} returned a decision outside the contract: '
            + " ".join(issues), record)

    state = next(s for s in record["states"] if s["id"] == decision["state"])
    return _result(decision["state"], state, decision["payload"],
                   decision["reason"], "strategy", record)
