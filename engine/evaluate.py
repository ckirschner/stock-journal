"""Verdict logic.

Precedence, in order, and nothing overrides it:
  1. Any knockout failure  -> red, regardless of everything else
  2. Any required failure  -> red
  3. Too much missing data -> grey (never a pass by default)
  4. Optional score        -> green above the threshold, amber below

A metric within 10% of its threshold is "watch": still passing, but close
enough that you want to know before it breaks.
"""

from __future__ import annotations

from .schema import DEFAULT_SCHEMA, metric_by_id

PASS, WATCH, FAIL, NONE = "pass", "watch", "fail", "none"
WATCH_BAND = 0.10
MISSING_LIMIT = 6  # >= this many absent metrics and we refuse to call it


def state_of(metric: dict, value, rule: dict) -> str:
    if value is None or rule is None or not rule.get("enabled", True):
        return NONE
    t = float(rule["threshold"])
    band = abs(t) * WATCH_BAND or 0.5
    v = float(value)
    if metric["dir"] == "high":
        if v >= t:
            return WATCH if (v - t) <= band else PASS
        return FAIL
    if v <= t:
        return WATCH if (t - v) <= band else PASS
    return FAIL


def _verdict_word(bucket: str, held: str, gone: str, idea: str) -> str:
    return {"holdings": held, "previous": gone}.get(bucket, idea)


def evaluate(security: dict, ruleset: dict, which: str = "now",
             schema=None) -> dict:
    """Score one security against one ruleset version.

    which: "now" uses live metrics, "entry" uses the frozen entry snapshot.
    """
    schema = schema or DEFAULT_SCHEMA
    if which == "entry":
        values = (security.get("entry_snapshot") or {}).get("metrics") or {}
    else:
        values = security.get("metrics") or {}

    knockouts, required_fails = [], []
    opt_pass = opt_total = missing = 0
    states = {}

    for group in schema:
        for m in group["metrics"]:
            rule = ruleset["metrics"].get(m["id"])
            if not rule or not rule.get("enabled", True):
                continue
            s = state_of(m, values.get(m["id"]), rule)
            states[m["id"]] = s
            if s == NONE:
                missing += 1
                continue
            if rule["mode"] == "knockout":
                if s == FAIL:
                    knockouts.append(m["id"])
            elif rule["mode"] == "required":
                if s == FAIL:
                    required_fails.append(m["id"])
            else:
                opt_total += 1
                if s in (PASS, WATCH):
                    opt_pass += 1

    bucket = security.get("bucket", "ideas")
    min_opt = ruleset.get("min_optional", 6)

    if knockouts:
        verdict = _verdict_word(bucket, "Exit", "Would avoid", "Avoid")
        tone = FAIL
    elif required_fails:
        verdict = _verdict_word(bucket, "Trim", "Would avoid", "Avoid")
        tone = FAIL
    elif missing >= MISSING_LIMIT:
        verdict, tone = "Insufficient data", NONE
    elif opt_pass >= min_opt:
        verdict = _verdict_word(bucket, "Hold", "Still qualifies", "Buy")
        tone = PASS
    else:
        verdict = _verdict_word(bucket, "Review", "Marginal", "Wait")
        tone = WATCH

    return {
        "verdict": verdict,
        "tone": tone,
        "knockouts": knockouts,
        "required_fails": required_fails,
        "optional_pass": opt_pass,
        "optional_total": opt_total,
        "missing": missing,
        "states": states,
        "ruleset_version": ruleset["version"],
    }


def failure_labels(result: dict) -> list[str]:
    ids = result["knockouts"] + result["required_fails"]
    out = []
    for i in ids:
        m = metric_by_id(i)
        out.append(m["label"] if m else i)
    return out


def format_value(value, fmt: str) -> str:
    if value is None:
        return "—"
    v = float(value)
    if fmt == "pct":
        return f"{v:.1f}%"
    if fmt == "pctd":
        return f"{v:+.1f}%"
    if fmt == "ppt":
        return f"{v:+.1f}pp"
    if fmt == "x":
        return f"{v:.2f}×"
    return f"{v:g}"
