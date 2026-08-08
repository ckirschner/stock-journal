"""Positions, snapshots and the override log.

The rule that matters here: an entry snapshot is written once, at purchase,
and never recomputed. If it were recomputed, restated filings and amended
rules would quietly rewrite history and the journal would lose the only thing
that makes it a journal.

A purchase is recorded under a profile — the lens the user was buying
through. The snapshot freezes that profile's identity and version, every
metric value on the security, and the verdict the profile produced. Snapshots
recorded before the profile system carry a ``ruleset_version`` instead; they
are recognised by that field and rendered as the frozen records they are,
never re-scored.
"""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone

from .evaluate import evaluate_buy, evaluate_position

EXIT_REASONS = [
    "Thesis broke",
    "Hit valuation",
    "Better opportunity",
    "Risk limit",
    "Panic",
]

VERDICT_WORDS = {"buy": "Buy", "no_buy": "No buy", "cant_say": "Can't say"}
SIGNAL_WORDS = {
    "fired": "Sell signal",
    "breached": "Breach unconfirmed",
    "clear": "No signal",
    "unwatched": "Unwatched",
}


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
        "metrics": {},          # bank id -> value
        "history": {},          # bank id -> [[period, value], ...], unfilled
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


def open_position(security: dict, profile: dict, profile_version,
                  shares: float, cost: float, opened: str | None = None,
                  override_reason: str = "", values: dict | None = None,
                  value_sources: dict | None = None,
                  price_seen: dict | None = None) -> dict:
    """Record a purchase under a profile and freeze what the lens showed.

    A failing or indeterminate verdict does not block anything. It gets
    recorded alongside the purchase, with the user's stated reason for going
    ahead — that includes buying on grey, where the profile's own rule is
    that the user decides and logs an override.

    `values` are the values the lens actually evaluated — hand-entered merged
    over computed. They are what the snapshot freezes, because the snapshot's
    job is to record what was seen, and `value_sources` records where each
    one came from so the frozen record can say so forever.
    """
    values = values if values is not None else (security.get("metrics") or {})
    result = evaluate_buy(values, profile)

    security["bucket"] = "holdings"
    security["position"] = {
        "shares": float(shares),
        "cost_basis": float(cost),
        "opened": opened or _today(),
    }
    security["entry_snapshot"] = {
        "frozen": _stamp(),
        "profile": {"file": profile.get("file"), "id": profile.get("id"),
                    "name": profile.get("name"), "version": profile_version},
        "metrics": copy.deepcopy(values),
        "value_sources": copy.deepcopy(value_sources or {}),
        # The snapshot records what was SEEN — the effective price (manual
        # over fetched), with its source and date, not just the manual field.
        "price": (price_seen or {}).get("value", security.get("price")),
        "price_source": (price_seen or {}).get("source"),
        "price_date": (price_seen or {}).get("date"),
        "result": result,
    }

    if result["verdict"] != "buy":
        failed = [m for c in result["causes"]
                  if c["kind"] == "fail" for m in c["metrics"]]
        missing = [m for c in result["causes"]
                   if c["kind"] == "indeterminate" for m in c["metrics"]]
        word = VERDICT_WORDS[result["verdict"]]
        security["override"] = {
            "date": security["position"]["opened"],
            "verdict": word,
            "profile": security["entry_snapshot"]["profile"],
            "failed": failed,
            "missing": missing,
            "reason": (override_reason or "").strip() or "No reason given.",
        }
        what = ("against signal" if result["verdict"] == "no_buy"
                else "without a signal")
        add_note(security, f"Bought {what} ({word} under "
                           f"{profile.get('name')}). Stated reason: "
                           f"{security['override']['reason']}")
    else:
        security["override"] = None
    return security


def close_position(security: dict, profile: dict | None, profile_version,
                   governing: bool, reason: str, exit_price: float,
                   exited: str | None = None, today: date | None = None,
                   missing_profile_ref: dict | None = None,
                   values: dict | None = None,
                   histories: dict | None = None) -> dict:
    """Close a position, keeping the ticker in the journal for tracking.

    profile is the lens the exit is judged under — the position's own entry
    profile when it has one (governing=True), otherwise whatever lens the
    user was looking through, labelled as such. Two absences are recorded
    distinctly, never conflated: a position from before the profile system
    has no governing profile at all, while a position whose governing profile
    file is off disk at close time still names it (missing_profile_ref) and
    records that no signal could be evaluated.
    """
    pos = security.get("position") or {}
    cost = pos.get("cost_basis") or 0.0
    held_pct = ((exit_price / cost) - 1) * 100 if cost else None

    if profile is not None:
        eval_sec = security if values is None else {**security, "metrics": values}
        # histories carries the per-filing readings for breached thresholds so
        # the signal frozen here agrees with what the sell watch showed — a
        # confirmed breach must not read "unconfirmed" in the record merely
        # because the close path forgot the filings.
        state = evaluate_position(eval_sec, profile, today, histories=histories)
        signal = SIGNAL_WORDS[state["overall"]]
        rule_triggered = state["overall"] == "fired"
        profile_ref = {"file": profile.get("file"), "id": profile.get("id"),
                       "name": profile.get("name"), "version": profile_version}
        is_governing = governing
    elif missing_profile_ref is not None:
        signal = "Profile not on disk"
        rule_triggered = None
        profile_ref = dict(missing_profile_ref)
        is_governing = True
    else:
        signal, rule_triggered, profile_ref = "No governing profile", None, None
        is_governing = False

    security["bucket"] = "previous"
    security["exit"] = {
        "date": exited or _today(),
        "reason": reason,
        "price": float(exit_price),
        "return_pct": round(held_pct, 2) if held_pct is not None else None,
        "profile": profile_ref,
        "governing": is_governing,
        "signal_at_exit": signal,
        "rule_triggered": rule_triggered,
    }
    if rule_triggered is False:
        add_note(security, f"Closed with no rule triggering the exit. "
                           f"Signal at exit was {signal} under "
                           f"{profile.get('name')}.")
    elif rule_triggered is None and missing_profile_ref is not None:
        add_note(security, f"Closed while its governing profile "
                           f"({missing_profile_ref.get('name')}) was not on "
                           "disk, so no signal could be evaluated.")
    elif rule_triggered is None:
        add_note(security, "Closed with no governing profile on record — "
                           "the position predates the profile system.")
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
