"""Profile evaluation.

A resolved profile (engine/profiles.py) supplies every threshold, tier rule
and rollup setting; the security supplies values keyed by bank id. This module
joins the two and holds no opinion of its own: no threshold, no metric name,
no strategy assumption appears below. Anything that looks like a rule here is
structure — how three-valued logic composes — never a level.

Buy side, per entry, three states:
  green   the buy condition holds
  red     it doesn't
  grey    it can't be evaluated: no value recorded, a declared parameter the
          profile leaves unset, or a configuration error on the entry.
          Grey is its own state. It is never a pass and never a failure.

Tier rollup, three-valued:
  all_green    any red -> fail; else any grey -> indeterminate; else pass
  at_least     greens >= min        -> pass  (greys can't change the outcome)
               greens + greys < min -> fail  (greys couldn't save it)
               otherwise            -> indeterminate (the greys decide, and
                                       they are unknown)
  none         score only; never blocks

Verdict: any non-bonus tier failing -> no_buy. Else any non-bonus tier
indeterminate -> cant_say. Else buy. This is the report's rule that grey
propagates rather than counting for or against.

Sell side, per entry with a threshold, four states:
  fired        the condition holds and its confirmation requirement is met:
               inherent confirmation, the calendar clock (which needs no
               filing history), or the breach observed on the required run of
               per-filing readings recomputed from the stored filings
  breached     the condition holds on the current reading but has not yet
               appeared on enough consecutive filing periods — the signal
               reports how many it has, how many it needs, and when it could
               next be confirmed
  clear        the condition does not hold
  unevaluable  a value it needs is missing — the current reading, the entry
               snapshot for a delta-versus-entry test, or the snapshot predates
               the profile system

Confirmation is recomputed, never accumulated: the caller passes per-filing
reading histories (plain data, newest first, one reading per filing that
actually changed the metric's inputs) and the walk here counts the consecutive
readings on which the breach appears. A reading that could not be computed
neither advances nor resets the count — a gap must not confirm what nobody
observed, and must not grant an indefinite reprieve either. It pauses, and the
signal says so. Absence on the sell side always means "do not sell": no
reading, no fire.

A breached-but-unconfirmed sell never claims to have fired. The profiles
demand the confirmation precisely so one quarter's noise cannot use the tool's
authority to cause a panic; firing early would be the tool doing the thing it
exists to prevent.
"""

from __future__ import annotations

from datetime import date, timedelta

GREEN, RED, GREY = "green", "red", "grey"


# -- plumbing ----------------------------------------------------------------

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    try:
        return d.replace(year=d.year + y, month=m + 1)
    except ValueError:                      # e.g. Jan 31 + 1 month
        nxt = date(d.year + y + (1 if m == 11 else 0), 1 if m == 11 else m + 2, 1)
        return nxt - timedelta(days=1)


def _parse_date(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


# -- conditions --------------------------------------------------------------

def condition_holds(cond: dict, value, entry_value=None):
    """True/False, or None when the condition cannot be evaluated.

    delta_median conditions compare the stored value directly: the bank
    entries they appear on are already median-relative, so the value *is* the
    ratio or difference the threshold speaks about.
    """
    if not isinstance(cond, dict):
        return None
    form = cond.get("form")
    if form == "none":
        return None
    if form == "compound":
        results = [condition_holds(c, value, entry_value)
                   for c in (cond.get("conditions") or [])]
        if not results:
            return None
        if cond.get("require") == "any":
            if any(r is True for r in results):
                return True
            return False if all(r is False for r in results) else None
        # require: all (the default)
        if any(r is False for r in results):
            return False
        return True if all(r is True for r in results) else None

    v = _num(value)
    if form in ("abs", "delta_median"):
        if v is None:
            return None
        cmpr = cond.get("comparator")
        if cmpr == "between":
            lo, hi = _num(cond.get("min")), _num(cond.get("max"))
            if lo is None or hi is None:
                return None
            return lo <= v <= hi
        t = _num(cond.get("value"))
        if t is None:
            return None
        return {
            "at_most": v <= t,
            "at_least": v >= t,
            "less_than": v < t,
            "greater_than": v > t,
        }.get(cmpr)

    if form == "delta_entry":
        e = _num(entry_value)
        if v is None or e is None:
            return None
        cmpr = cond.get("comparator")
        if cmpr == "falls_below_entry_value":
            return v < e
        if cmpr == "falls_by_at_least":
            t = _num(cond.get("value"))
            # A percentage fall from a zero or negative base has no meaning —
            # with e <= 0 the raw formula marks improvements as falls.
            if t is None or e <= 0:
                return None
            # unit is percent_of_entry_value: a relative fall from entry
            return v <= e * (1 - t / 100.0)
        return None

    return None


def _needs_entry_value(cond: dict) -> bool:
    if not isinstance(cond, dict):
        return False
    if cond.get("form") == "delta_entry":
        return True
    if cond.get("form") == "compound":
        return any(_needs_entry_value(c) for c in (cond.get("conditions") or []))
    return False


# -- buy side ----------------------------------------------------------------

def _entry_grey_reason(entry: dict, values: dict):
    """Why this entry cannot be evaluated, or None if it can."""
    if entry.get("errors"):
        return "configuration problem: " + " ".join(entry["errors"])
    for p in entry.get("parameters") or []:
        if not p.get("supplied") or p.get("value") in (None, ""):
            label = p.get("label") or p.get("id")
            return (f'the parameter "{label}" is not set, so this value '
                    "cannot be computed")
    if values.get(entry["metric"]) is None:
        return "no value recorded"
    return None


def evaluate_buy(values: dict, profile: dict) -> dict:
    """Score one security's values against one resolved profile, buy side."""
    tiers_out, causes = [], []
    for tier in profile.get("tiers", []):
        entries_out = []
        greens = reds = greys = 0
        for e in tier.get("entries", []):
            grey_reason = _entry_grey_reason(e, values)
            value = values.get(e["metric"])
            if grey_reason is not None:
                state, reason = GREY, grey_reason
                greys += 1
            else:
                holds = condition_holds(e.get("buy"), value)
                if holds is None:
                    state, reason = GREY, "the buy condition could not be evaluated"
                    greys += 1
                elif holds:
                    state, reason = GREEN, None
                    greens += 1
                else:
                    state, reason = RED, None
                    reds += 1
            entries_out.append({"metric": e["metric"], "state": state,
                                "value": value, "reason": reason})

        requires = tier.get("requires")
        n = len(entries_out)
        problem = None
        if requires == "all_green":
            outcome = ("fail" if reds else "indeterminate" if greys else "pass")
        elif requires == "at_least":
            need = _num(tier.get("min_green"))
            if need is None:
                # Absence is never silently imputed: a tier that names no bar
                # cannot pass by default.
                outcome = "indeterminate"
                problem = ("declares at_least but no min_green, so the "
                           "rollup cannot be evaluated")
            elif greens >= need:
                outcome = "pass"
            elif greens + greys < need:
                outcome = "fail"
            else:
                outcome = "indeterminate"
        elif requires == "none":
            outcome = "score"
        else:
            outcome = "indeterminate"
            problem = (f'uses the rollup form "{requires}", which the '
                       "evaluator does not recognise")

        tiers_out.append({
            "key": tier.get("key"), "requires": requires,
            "min_green": tier.get("min_green"), "count": n,
            "greens": greens, "reds": reds, "greys": greys,
            "outcome": outcome, "problem": problem, "entries": entries_out,
        })

    verdict = "buy"
    for t in tiers_out:
        if t["outcome"] == "fail":
            verdict = "no_buy"
            causes.append(_tier_cause(t, failed=True))
    if verdict == "buy":
        for t in tiers_out:
            if t["outcome"] == "indeterminate":
                verdict = "cant_say"
                causes.append(_tier_cause(t, failed=False))

    return {"verdict": verdict, "causes": causes, "tiers": tiers_out}


def _tier_cause(t: dict, failed: bool) -> dict:
    key = (t["key"] or "").upper()
    reds = [e["metric"] for e in t["entries"] if e["state"] == RED]
    greys = [e["metric"] for e in t["entries"] if e["state"] == GREY]
    if failed:
        if t["requires"] == "all_green":
            text = f"{key} entries red"
        else:
            text = (f"only {t['greens']} of {t['count']} {key} entries green — "
                    f"{t['min_green']} needed")
        return {"kind": "fail", "tier": t["key"], "metrics": reds, "text": text}
    if t.get("problem"):
        text = f"the {key} tier {t['problem']}"
        return {"kind": "indeterminate", "tier": t["key"], "metrics": [],
                "text": text}
    if t["requires"] == "all_green":
        text = f"{key} entries grey — a grey {key} entry makes the verdict grey, not red"
    else:
        text = (f"{t['greens']} of {t['count']} {key} entries green with "
                f"{t['greys']} grey — the grey entries decide, and they are unknown")
    return {"kind": "indeterminate", "tier": t["key"], "metrics": greys, "text": text}


# -- sell side ---------------------------------------------------------------

def _confirmation(entry_sell: dict, profile: dict):
    """(kind, spec). kind: 'inherent' | 'sustained' | 'default' | 'none'."""
    conf = entry_sell.get("sell_confirmation")
    if isinstance(conf, dict) and conf.get("form") == "inherent":
        return "inherent", None
    sust = entry_sell.get("sustained_for")
    if isinstance(sust, dict):
        return "sustained", sust
    default = profile.get("sell_confirmation")
    if isinstance(default, dict):
        return "default", default
    return "none", None


# Mirrors periods.ANNUAL_FORMS. Restated here rather than imported so this
# module keeps needing nothing but the standard library; a drift test in
# tests/test_confirmation.py holds the two equal.
_ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A")


def _cadence_words(cadence, n: int) -> str:
    one = {"annual": "annual report",
           "quarterly": "quarterly report"}.get(cadence, "filing")
    return one if n == 1 else one + "s"


def _run_words(spec: dict) -> str:
    unit = str((spec or {}).get("unit") or "").replace("_", " ")
    if not unit:
        return "consecutive filings"
    return unit if unit.startswith("consecutive") else f"consecutive {unit}"


def _next_estimate(readings: list, remaining: int) -> dict:
    """When the breach could next be confirmed — an estimate from the spacing
    of past qualifying reports, always labelled as one, or an honest unknown.
    Nothing here is a measurement; it is a projection and says so."""
    ends = sorted((d for d in (_parse_date(r.get("period_end"))
                               for r in readings) if d), reverse=True)[:5]
    if len(ends) < 2:
        return {"unknown": "only one qualifying report is on record, so the "
                           "spacing of future reports cannot be estimated"}
    gaps = [(ends[i] - ends[i + 1]).days for i in range(len(ends) - 1)]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return {"unknown": "the qualifying reports on record share a period "
                           "end, so future spacing cannot be estimated"}
    med = sorted(gaps)[len(gaps) // 2]
    last_filed = _parse_date(readings[0].get("filed"))
    if last_filed is None:
        return {"unknown": "the newest qualifying report carries no filed "
                           "date, so nothing can be projected from it"}
    days = med * max(remaining, 1)
    if days > (date.max - last_filed).days:
        return {"unknown": f"confirmation would need {remaining} more "
                           "qualifying reports, which at the observed "
                           "spacing lies beyond any projectable date — "
                           "check the profile's confirmation count"}
    due = last_filed + timedelta(days=days)
    return {"date": due.isoformat(),
            "basis": f"estimated from the roughly {med}-day spacing of past "
                     "reports"}


def _confirm_from_history(cond: dict, spec: dict, history, entry_value,
                          opened: str | None) -> dict:
    """Walk per-filing readings, newest first, and count the consecutive ones
    on which the condition holds.

    True advances the count; False stops it (that period was observed clear);
    an uncomputable reading is a pause — it neither advances nor resets, and
    is reported. For a condition that compares against the entry snapshot,
    readings filed before the position opened are out of scope: a change
    versus the entry value is not a proposition that had a truth value before
    the entry existed. An absolute threshold, by contrast, counts standing
    breaches from before the purchase — a condition that has persisted across
    filings is a fact about the security, not noise, whenever one lived
    through it.
    """
    required = int(_num((spec or {}).get("count")) or 0)
    unit = str((spec or {}).get("unit") or "")
    lead = f"needs the breach on {required} {_run_words(spec)}"
    detail = {"required": required, "unit": unit, "confirmed": False,
              "observed": 0, "cadence": None, "readings": [], "gaps": 0,
              "undecided": 0, "unit_mismatch": False, "next": None,
              "note": None}
    if required <= 0:
        detail["note"] = (f"the confirmation is declared as "
                          f"{(spec or {}).get('count')!r} {unit or '?'}, "
                          "which cannot be counted — the breach stays "
                          "unconfirmed until the profile is corrected")
        return detail
    if not isinstance(history, dict):
        detail["note"] = (lead + "; stored filings were not consulted in "
                                 "this evaluation")
        return detail
    cadence = history.get("cadence")
    detail["cadence"] = cadence
    readings = history.get("readings") or []
    if not readings:
        why = history.get("note") or "no per-filing readings are available"
        detail["note"] = f"{lead}; {why}"
        return detail
    # Unit versus cadence, both directions. A quarterly unit on an annual
    # metric can only be counted in annual reports (slower than written —
    # conservative, reported). An annual unit on a quarterly metric is
    # honoured as written: only readings on annual reports advance the count,
    # because counting quarterly readings would fire years earlier than the
    # profile demanded. In both directions a clear reading on ANY report ends
    # the run — a mismatch may make confirming slower, never easier.
    strict_annual = cadence == "quarterly" and "annual" in unit
    if strict_annual or (cadence == "annual" and "quarter" in unit):
        detail["unit_mismatch"] = True
    unit_cadence = "annual" if strict_annual else cadence
    needs_entry = _needs_entry_value(cond)
    if needs_entry and not opened:
        detail["note"] = (lead + "; the position's opened date could not be "
                                 "read, so it cannot be said which reports "
                                 "arrived during this holding")
        return detail
    observed, gaps, undecided, rows, stopped = 0, 0, 0, [], None
    for r in readings:
        pre_entry = needs_entry and str(r.get("filed") or "") < opened
        countable = (not strict_annual
                     or str(r.get("form") or "") in _ANNUAL_FORMS)
        # A pre-entry reading is probed with the entry value withheld: a leg
        # that compares against it had no truth value then, but an absolute
        # leg can still settle the reading either way.
        holds = condition_holds(cond, r.get("value"),
                                None if pre_entry else entry_value)
        if holds is False:
            rows.append({**r, "state": "clear"})
            stopped = "clear"
            break
        if pre_entry and holds is None:
            rows.append({**r, "state": "out_of_scope"})
            stopped = "pre_entry"
            break
        if holds is True and countable:
            observed += 1
            rows.append({**r, "state": "breached"})
            if observed >= required:
                break
        elif holds is True:
            rows.append({**r, "state": "not_counted"})
        elif r.get("value") is not None:
            undecided += 1
            rows.append({**r, "state": "undecided"})
        else:
            gaps += 1
            rows.append({**r, "state": "unobserved"})
    detail.update(observed=observed, gaps=gaps, undecided=undecided,
                  readings=rows, confirmed=observed >= required)
    if detail["confirmed"]:
        which = ", ".join(f"{r['form']} for {r['period_end']}"
                          for r in rows if r["state"] == "breached")
        w = _cadence_words(unit_cadence, observed)
        if gaps:
            detail["note"] = (
                f"the breach appears on {observed} {w} with no clear "
                f"reading between them ({which}); "
                f"{gaps} report{'s' if gaps != 1 else ''} in between could "
                "not be read — a gap neither advances nor resets the count")
        else:
            run = " in a row" if observed > 1 else ""
            detail["note"] = (f"the breach appears on {observed} {w}{run} "
                              f"({which})")
        return detail
    parts = [f"{lead}; so far it appears on {observed} of {required} "
             f"{_cadence_words(unit_cadence, required)}"]
    if stopped == "clear":
        r = rows[-1]
        if observed == 0:
            where = ("the newest reading" if len(rows) == 1
                     else "the newest reading that could settle the run")
            parts.append(f"{where} ({r['form']} for {r['period_end']}) is "
                         "clear of the exit threshold, so no run has started")
        else:
            parts.append(f"the run is bounded by a clear reading on "
                         f"{r['form']} for {r['period_end']}")
    elif stopped == "pre_entry":
        parts.append("reports filed before this position was opened are not "
                     "counted for a change-versus-entry test")
    if gaps:
        parts.append(f"{gaps} report{'s' if gaps != 1 else ''} could not be "
                     "read — a gap neither advances nor resets the count")
    if undecided:
        parts.append(f"{undecided} reading{'s' if undecided != 1 else ''} "
                     "computed but could not be judged against this "
                     "threshold, which neither advances nor resets the count")
    if history.get("truncated") and stopped is None:
        parts.append(f"only the newest {len(readings)} qualifying reports "
                     "were examined")
    if detail["unit_mismatch"]:
        if strict_annual:
            parts.append("the profile counts annual reports and this metric "
                         "refreshes with every quarterly report, so only "
                         "readings on annual reports advance the count")
        else:
            parts.append("the profile counts quarterly filings, but this "
                         "metric's inputs change only with annual reports, "
                         "so annual reports are what is counted")
    detail["next"] = _next_estimate(readings, required - observed)
    nxt = detail["next"]
    if nxt.get("date"):
        parts.append(f"next possible confirmation around {nxt['date']} "
                     f"({nxt['basis']})")
    else:
        parts.append(nxt.get("unknown") or "")
    detail["note"] = "; ".join(p for p in parts if p)
    return detail


def evaluate_position(security: dict, profile: dict, today: date | None = None,
                      histories: dict | None = None) -> dict:
    """Sell conditions, flags and the position clock for one security.

    Uses the security's current values and, for delta-versus-entry tests, the
    values frozen in the entry snapshot. A snapshot recorded before the
    profile system (it carries a ruleset_version) has no bank-id values, so
    those tests report unevaluable rather than guessing.

    `histories`, when supplied, maps a bank id (the metric a sell condition is
    measured on) to its per-filing reading history — plain data as produced by
    compute.confirmation_history — and lets a breached threshold confirm.
    Without it a breach stays unconfirmed and says that stored filings were
    not consulted; it never claims anything about what is on disk.
    """
    today = today or date.today()
    values = security.get("metrics") or {}
    snap = security.get("entry_snapshot") or {}
    snap_is_legacy = "ruleset_version" in snap
    snap_values = {} if snap_is_legacy else (snap.get("metrics") or {})
    opened = str((security.get("position") or {}).get("opened") or "")[:10] \
        or None

    signals, flags = [], []
    for tier in profile.get("tiers", []):
        for e in tier.get("entries", []):
            sig = _sell_signal(e, values, snap_values, snap_is_legacy,
                               profile, histories, opened)
            if sig is not None:
                signals.append(sig)
            flg = _flag_signal(e, values, snap_values, snap_is_legacy)
            if flg is not None:
                flags.append(flg)

    clock = None
    hpe = profile.get("holding_period_exit")
    if isinstance(hpe, dict) and hpe.get("form") == "fixed_period":
        opened = _parse_date((security.get("position") or {}).get("opened"))
        months = int(_num(hpe.get("value")) or 0)
        if str(hpe.get("unit")) != "months" or months <= 0:
            clock = {"months": months, "opened": None, "due": None,
                     "expired": False,
                     "problem": f'the clock is declared as {hpe.get("value")!r} '
                                f'{hpe.get("unit")!r}, which the evaluator does '
                                "not support — it runs on a positive number of "
                                "months"}
        elif opened is None:
            clock = {"months": months, "opened": None, "due": None,
                     "expired": False,
                     "problem": "the position's opened date could not be read, "
                                "so the clock cannot run"}
        else:
            due = _add_months(opened, months)
            clock = {"months": months, "opened": opened.isoformat(),
                     "due": due.isoformat(), "expired": today >= due}

    fired = any(s["status"] == "fired" for s in signals) or bool(
        clock and clock.get("expired"))
    breached = any(s["status"] == "breached" for s in signals)
    watchable = [s for s in signals if s["status"] != "no_threshold"]
    unevaluable = [s for s in watchable if s["status"] == "unevaluable"]

    if fired:
        overall = "fired"
    elif breached:
        overall = "breached"
    elif watchable and len(unevaluable) == len(watchable) and not clock:
        overall = "unwatched"      # sell thresholds exist and none can run
    else:
        overall = "clear"

    return {"signals": signals, "flags": flags, "clock": clock,
            "overall": overall,
            "watchable": len(watchable), "unevaluable": len(unevaluable)}


def _unevaluable_reason(cond, measured_on, value, entry_value, snap_is_legacy):
    """Why a condition returned None, in plain language, best effort first."""
    if value is None:
        return f'no current value recorded for "{measured_on}"'
    if _needs_entry_value(cond):
        if entry_value is None:
            return ("compares against the value at purchase, and the entry "
                    "snapshot predates the profile system" if snap_is_legacy
                    else "compares against the value at purchase, which the "
                         "entry snapshot does not hold")
        e = _num(entry_value)
        if e is not None and e <= 0:
            return ("the value at entry is zero or negative, so a "
                    "percentage fall from it has no meaning")
    return "the condition could not be evaluated"


def _sell_signal(entry, values, snap_values, snap_is_legacy, profile,
                 histories=None, opened=None):
    sell = entry.get("sell")
    if not isinstance(sell, dict):
        return None
    metric = entry["metric"]
    if sell.get("form") == "none":
        return {"metric": metric, "measured_on": None, "condition": sell,
                "status": "no_threshold", "value": None, "entry_value": None,
                "needs": None}

    measured_on = str(sell.get("measured_on") or "") or metric
    value = values.get(measured_on)
    entry_value = snap_values.get(measured_on)

    out = {"metric": metric, "measured_on": measured_on, "condition": sell,
           "status": "clear", "value": value, "entry_value": entry_value,
           "needs": None}

    # Three-valued resolution first: a compound with require:any can settle
    # even when one leg cannot be evaluated.
    holds = condition_holds(sell, value, entry_value)
    if holds is None:
        out["status"] = "unevaluable"
        out["needs"] = _unevaluable_reason(sell, measured_on, value,
                                           entry_value, snap_is_legacy)
        return out
    if not holds:
        return out

    kind, spec = _confirmation(sell, profile)
    if kind in ("inherent", "none"):
        out["status"] = "fired"
        return out

    conf = _confirm_from_history(sell, spec,
                                 (histories or {}).get(measured_on),
                                 entry_value, opened)
    conf["kind"] = kind
    out["confirmation"] = conf
    if conf["confirmed"]:
        out["status"] = "fired"
    else:
        out["status"] = "breached"
        out["needs"] = conf["note"]
    return out


def _flag_signal(entry, values, snap_values, snap_is_legacy):
    flag = entry.get("flag")
    if not isinstance(flag, dict) or flag.get("form") in (None, "none"):
        return None
    metric = entry["metric"]
    measured_on = str(flag.get("measured_on") or "") or metric
    value = values.get(measured_on)
    entry_value = snap_values.get(measured_on)

    out = {"metric": metric, "measured_on": measured_on, "condition": flag,
           "status": "clear", "value": value, "entry_value": entry_value,
           "needs": None}
    holds = condition_holds(flag, value, entry_value)
    if holds is None:
        out["status"] = "unevaluable"
        out["needs"] = _unevaluable_reason(flag, measured_on, value,
                                           entry_value, snap_is_legacy)
    elif holds:
        out["status"] = "flagged"
    return out
