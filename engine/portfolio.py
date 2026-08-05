"""Positions, snapshots and the override log.

The rule that matters here: an entry snapshot is written once, at purchase,
and never recomputed. If it were recomputed, restated filings and amended
rules would quietly rewrite history and the journal would lose the only thing
that makes it a journal.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone

from .evaluate import evaluate


def _today():
    return date.today().isoformat()


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_security(ticker: str, name: str, bucket: str = "ideas") -> dict:
    return {
        "ticker": ticker.upper().strip(),
        "name": name.strip(),
        "bucket": bucket,
        "added": _today(),
        "price": None,
        "metrics": {},
        "history": {},          # metric_id -> [[period, value], ...] for the 15y charts
        "entry_snapshot": None,
        "override": None,
        "ev": None,
        "falsifier": "",
        "notes": [],            # dated entries, appended, never edited in place
        "position": None,
        "exit": None,
    }


def add_note(security: dict, text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return security
    security.setdefault("notes", []).append({"date": _stamp(), "text": text})
    return security


def open_position(security: dict, ruleset: dict, shares: float, cost: float,
                  opened: str | None = None, override_reason: str = "") -> dict:
    """Record a purchase and freeze the signal that was showing at the time.

    A failing verdict does not block anything. It gets recorded alongside the
    purchase, with the user's stated reason for going ahead.
    """
    result = evaluate(security, ruleset, which="now")

    security["bucket"] = "holdings"
    security["position"] = {
        "shares": float(shares),
        "cost_basis": float(cost),
        "opened": opened or _today(),
    }
    security["entry_snapshot"] = {
        "frozen": _stamp(),
        "ruleset_version": ruleset["version"],
        "metrics": copy.deepcopy(security.get("metrics") or {}),
        "price": security.get("price"),
        "result": result,
    }

    if result["tone"] == "fail":
        security["override"] = {
            "date": security["position"]["opened"],
            "verdict": result["verdict"],
            "failed": result["knockouts"] + result["required_fails"],
            "reason": (override_reason or "").strip() or "No reason given.",
        }
        add_note(security, f"Bought against signal ({result['verdict']}). "
                           f"Stated reason: {security['override']['reason']}")
    else:
        security["override"] = None
    return security


def close_position(security: dict, ruleset: dict, reason: str,
                   exit_price: float, exited: str | None = None) -> dict:
    """Close a position, keeping the ticker in the journal for tracking."""
    result = evaluate(security, ruleset, which="now")
    pos = security.get("position") or {}
    cost = pos.get("cost_basis") or 0.0
    held_pct = ((exit_price / cost) - 1) * 100 if cost else None

    security["bucket"] = "previous"
    security["exit"] = {
        "date": exited or _today(),
        "reason": reason,
        "price": float(exit_price),
        "return_pct": round(held_pct, 2) if held_pct is not None else None,
        "ruleset_version": ruleset["version"],
        "signal_at_exit": result["verdict"],
        "rule_triggered": bool(result["knockouts"] or result["required_fails"]),
    }
    if not security["exit"]["rule_triggered"]:
        add_note(security, f"Closed with no rule triggering the exit. "
                           f"Signal at exit was {result['verdict']}.")
    return security


# ------------------------------------------------------------------ analytics
def override_scorecard(securities: list[dict]) -> dict:
    """Did overriding the tool help or hurt? And is any rule miscalibrated?"""
    overrides, compliant = [], []
    for s in securities:
        r = _realised(s)
        if r is None:
            continue
        (overrides if s.get("override") else compliant).append(r)

    per_rule: dict[str, dict] = {}
    for s in securities:
        ov = s.get("override")
        r = _realised(s)
        if not ov or r is None:
            continue
        for mid in ov.get("failed", []):
            bucket = per_rule.setdefault(mid, {"n": 0, "wins": 0, "avg": 0.0, "returns": []})
            bucket["n"] += 1
            bucket["returns"].append(r)
            if r > 0:
                bucket["wins"] += 1
    for mid, b in per_rule.items():
        b["avg"] = round(sum(b["returns"]) / len(b["returns"]), 1)
        b.pop("returns")

    return {
        "override": _summarise(overrides),
        "compliant": _summarise(compliant),
        # If overrides on a specific rule keep working out, the rule is wrong,
        # not the person. Surfacing this is the difference between a feedback
        # loop and a guilt machine.
        "per_rule": per_rule,
    }


def exit_scorecard(securities: list[dict]) -> dict:
    """Group closed positions by why they were closed, and what happened after."""
    out: dict[str, dict] = {}
    for s in securities:
        ex = s.get("exit")
        if not ex:
            continue
        b = out.setdefault(ex["reason"], {"n": 0, "avg_held": 0.0, "avg_after": 0.0,
                                          "_held": [], "_after": []})
        b["n"] += 1
        if ex.get("return_pct") is not None:
            b["_held"].append(ex["return_pct"])
        after = _since_exit(s)
        if after is not None:
            b["_after"].append(after)
    for b in out.values():
        b["avg_held"] = round(sum(b["_held"]) / len(b["_held"]), 1) if b["_held"] else None
        b["avg_after"] = round(sum(b["_after"]) / len(b["_after"]), 1) if b["_after"] else None
        b.pop("_held"); b.pop("_after")
    return out


def _realised(s: dict):
    ex = s.get("exit")
    if ex and ex.get("return_pct") is not None:
        return ex["return_pct"]
    pos, price = s.get("position"), s.get("price")
    if pos and price and pos.get("cost_basis"):
        return round(((price / pos["cost_basis"]) - 1) * 100, 2)
    return None


def _since_exit(s: dict):
    ex, price = s.get("exit"), s.get("price")
    if ex and price and ex.get("price"):
        return round(((price / ex["price"]) - 1) * 100, 2)
    return None


def _summarise(returns: list[float]) -> dict:
    if not returns:
        return {"n": 0, "win_rate": None, "avg": None}
    wins = len([r for r in returns if r > 0])
    return {
        "n": len(returns),
        "win_rate": round(wins / len(returns) * 100),
        "avg": round(sum(returns) / len(returns), 1),
    }
