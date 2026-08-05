"""Rulesets and their version history.

The app owns this history, not git. Every change to a threshold or a weight
creates a new version with a timestamp and a written reason. Open positions
stay bound to the version they were opened under, so an entry snapshot can
never be quietly re-scored under rules you invented afterwards.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

from .schema import DEFAULT_SCHEMA

MODES = ("knockout", "required", "optional")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_ruleset() -> dict:
    metrics = {}
    for group in DEFAULT_SCHEMA:
        for m in group["metrics"]:
            metrics[m["id"]] = {
                "mode": m["mode"],
                "threshold": m["threshold"],
                "enabled": True,
            }
    return {
        "version": 1,
        "created": _now(),
        "reason": "Initial ruleset from defaults.",
        "min_optional": 6,
        "metrics": metrics,
    }


class RuleBook:
    """All ruleset versions, newest last. Never mutates an old version."""

    def __init__(self, data: dict | None = None):
        if data and data.get("versions"):
            self.versions = data["versions"]
        else:
            self.versions = [default_ruleset()]

    # -- access ---------------------------------------------------------
    @property
    def current(self) -> dict:
        return self.versions[-1]

    def get(self, version: int) -> dict:
        for v in self.versions:
            if v["version"] == version:
                return v
        # A snapshot referencing a version we no longer have still has to
        # render something. Fall back to current rather than crashing.
        return self.current

    def to_dict(self) -> dict:
        return {"versions": self.versions}

    # -- mutation -------------------------------------------------------
    def amend(self, changes: dict, reason: str) -> dict:
        """Create the next version.

        changes: {"min_optional": int, "metrics": {id: {mode/threshold/enabled}}}
        Returns the new version dict.
        """
        nxt = copy.deepcopy(self.current)
        nxt["version"] = self.current["version"] + 1
        nxt["created"] = _now()
        nxt["reason"] = (reason or "").strip() or "No reason given."

        if "min_optional" in changes:
            nxt["min_optional"] = int(changes["min_optional"])

        for mid, patch in (changes.get("metrics") or {}).items():
            if mid not in nxt["metrics"]:
                continue
            rule = nxt["metrics"][mid]
            if "mode" in patch and patch["mode"] in MODES:
                rule["mode"] = patch["mode"]
            if "threshold" in patch and patch["threshold"] is not None:
                rule["threshold"] = float(patch["threshold"])
            if "enabled" in patch:
                rule["enabled"] = bool(patch["enabled"])

        self.versions.append(nxt)
        return nxt

    def diff(self, older: int, newer: int) -> list[str]:
        """Human-readable changes between two versions."""
        a, b = self.get(older), self.get(newer)
        out = []
        if a["min_optional"] != b["min_optional"]:
            out.append(
                f"Optional metrics required: {a['min_optional']} → {b['min_optional']}"
            )
        for mid, rb in b["metrics"].items():
            ra = a["metrics"].get(mid)
            if not ra:
                out.append(f"{mid}: added")
                continue
            if ra["mode"] != rb["mode"]:
                out.append(f"{mid}: {ra['mode']} → {rb['mode']}")
            if ra["threshold"] != rb["threshold"]:
                out.append(f"{mid}: threshold {ra['threshold']} → {rb['threshold']}")
            if ra["enabled"] != rb["enabled"]:
                out.append(f"{mid}: {'enabled' if rb['enabled'] else 'disabled'}")
        return out
