"""Resolving bank inputs against one filing's stored facts.

This module executes config/concept-map.yaml — the tag-selection judgement —
against the raw facts the gateway extracted. It works on one filing at a time,
deliberately: a filing is a self-consistent statement of the world on one
accounting basis, and every resolved value carries the accession it came from
so period assembly (periods.py) can refuse to mix bases.

Everything returned is a plain dict called a resolution:

    {"value": float, "input": input_id, "matched": how,
     "parts": [{concept, label, value, matched_by}...],   # aggregates
     "concept": "us-gaap:...",                            # single concepts
     "family": "asc606" | "pre606" | "either" | None,
     "cautions": [...], "accession": ..., "filed": ...,
     "start": ..., "end": ..., "instant": ...}

or None when the input genuinely does not resolve in this filing for that
period. The caller decides what absence means; nothing here invents a value.
The single narrow exception is `absent_means_zero` on balance-sheet inputs,
which applies only when the statement's face was located and carries no such
line — the face sums to its total, so the statement itself is asserting nil.
Those resolutions say so in `matched` and carry a caution.
"""

from __future__ import annotations

import re
from pathlib import Path

from ruamel.yaml import YAML

APP_DIR = Path(__file__).resolve().parent.parent
MAP_PATH = APP_DIR / "config" / "concept-map.yaml"

_cache: dict = {}

CLASS_AXES = ("us-gaap:StatementClassOfStockAxis", "us-gaap:ClassOfStockAxis")


def load_map() -> dict:
    """The concept map, cached by file mtime so edits show up without a restart."""
    try:
        mtime = MAP_PATH.stat().st_mtime
    except OSError as e:
        raise FileNotFoundError(f"The concept map was not found at {MAP_PATH}.") from e
    if _cache.get("mtime") != mtime:
        yaml = YAML(typ="safe")
        with open(MAP_PATH, encoding="utf-8") as f:
            doc = yaml.load(f) or {}
        if not str(doc.get("schema", "")).startswith("ledger.concept-map/"):
            raise ValueError(f"{MAP_PATH.name} does not declare a concept-map schema.")
        _cache["mtime"] = mtime
        _cache["doc"] = doc
    return _cache["doc"]


def input_ids() -> list[str]:
    return list((load_map().get("inputs") or {}).keys())


def input_spec(input_id: str) -> dict:
    spec = (load_map().get("inputs") or {}).get(input_id)
    if spec is None:
        raise KeyError(f'"{input_id}" is not in the concept map.')
    return spec


# -- filing index ------------------------------------------------------------

class FilingIndex:
    """Fast lookups over one stored filing's facts. Read-only."""

    def __init__(self, filing: dict):
        self.accession = filing.get("accession")
        self.form = filing.get("form")
        self.filed = filing.get("filed")
        self.period_of_report = filing.get("period_of_report")
        self._dur = {}          # (concept, start, end) -> fact
        self._inst = {}         # (concept, date) -> fact
        self._dur_periods = {}  # concept -> set[(start, end)]
        self._face_inst = {}    # date -> [facts on the BalanceSheet face]
        self._dei = {}          # concept -> [facts]
        self._class_shares = []   # dimensioned share-class cover counts
        self._class_symbols = []  # dimensioned per-class trading symbols
        self._cf_periods = set()  # durations with a cash-flow-statement face
        self._bs_dates = set()    # dates with a genuine balance-sheet face
        for f in filing.get("facts") or []:
            c = f.get("concept") or ""
            dims = f.get("dimensions")
            if c.startswith("dei:"):
                if dims and any(a in dims for a in CLASS_AXES):
                    if c == "dei:EntityCommonStockSharesOutstanding":
                        self._class_shares.append(f)
                    elif c == "dei:TradingSymbol":
                        self._class_symbols.append(f)
                if not dims:
                    self._dei.setdefault(c, []).append(f)
                continue
            if dims:
                continue                      # segment/member facts: not ours
            if not isinstance(f.get("value"), (int, float)):
                continue
            if f.get("start") and f.get("end"):
                key = (c, f["start"], f["end"])
                held = self._dur.get(key)
                if held is None or _better(f, held):
                    self._dur[key] = f
                self._dur_periods.setdefault(c, set()).add((f["start"], f["end"]))
                if "CashFlow" in (f.get("statement_type") or ""):
                    self._cf_periods.add((f["start"], f["end"]))
            elif f.get("instant"):
                key = (c, f["instant"])
                held = self._inst.get(key)
                if held is None or _better(f, held):
                    self._inst[key] = f
                if f.get("statement_type") == "BalanceSheet":
                    self._face_inst.setdefault(f["instant"], []).append(f)
                    # A date only counts as a genuine balance-sheet
                    # presentation if the statement's own total is there.
                    # Equity-rollforward and note facts also arrive tagged
                    # BalanceSheet at extra dates, and treating those as a
                    # complete face once produced a confident zero total
                    # debt — the exact plausible-wrong-number this store
                    # exists to prevent.
                    if c in ("us-gaap:Assets",
                             "us-gaap:LiabilitiesAndStockholdersEquity"):
                        self._bs_dates.add(f["instant"])

    # lookups ---------------------------------------------------------------
    def duration_fact(self, concept, start, end):
        return self._dur.get((concept, start, end))

    def durations_of(self, concept):
        return sorted(self._dur_periods.get(concept, ()))

    def instant_fact(self, concept, date):
        return self._inst.get((concept, date))

    def face_instants(self, date):
        """Balance-sheet face lines at a date — only for dates where the face
        genuinely exists (its own total is present). Anything else returns
        empty, so completeness arguments cannot run against a partial face."""
        if date not in self._bs_dates:
            return []
        return list(self._face_inst.get(date, ()))

    def balance_dates(self):
        return sorted(self._bs_dates)

    def dei_value(self, concept):
        rows = self._dei.get(concept) or []
        return rows[0] if rows else None

    def class_share_facts(self):
        return list(self._class_shares)

    def class_symbol(self, member: str):
        """The trading symbol the cover page tags for a share class, if any."""
        for f in self._class_symbols:
            dims = f.get("dimensions") or {}
            if any(dims.get(a) == member for a in CLASS_AXES):
                v = f.get("value")
                return str(v).strip().upper() if v not in (None, "") else None
        return None


def _better(a: dict, b: dict) -> bool:
    """Between two undimensioned facts for the same key, prefer the one with
    finer decimals (a re-tag at coarser rounding never wins)."""
    da, db = a.get("decimals"), b.get("decimals")
    try:
        return int(da) > int(db)
    except (TypeError, ValueError):
        return False


# -- resolution --------------------------------------------------------------

def _res(input_id, fi, value, *, matched, concept=None, parts=None,
         cautions=None, family=None, start=None, end=None, instant=None):
    return {"input": input_id, "value": float(value), "matched": matched,
            "concept": concept, "parts": parts,
            "cautions": [c for c in (cautions or []) if c],
            "family": family, "accession": fi.accession, "form": fi.form,
            "filed": fi.filed, "start": start, "end": end, "instant": instant}


def _cand_list(spec) -> list:
    return spec.get("candidates") or []


def resolve_duration(fi: FilingIndex, input_id: str, start: str, end: str):
    """One input over one duration in one filing, or None."""
    spec = input_spec(input_id)
    if spec.get("derive"):
        base = resolve_duration(fi, spec["derive"], start, end)
        if base is None:
            return None
        return {**base, "input": input_id,
                "cautions": base["cautions"] + [spec.get("caution")] if spec.get("caution")
                else base["cautions"]}
    if spec.get("derive_sum"):
        parts, cautions = [], [spec.get("caution")]
        total = 0.0
        for sub in spec["derive_sum"]:
            r = resolve_duration(fi, sub, start, end)
            if r is None:
                return None
            total += r["value"]
            parts.append({"concept": r.get("concept"), "input": sub,
                          "value": r["value"], "matched_by": r["matched"]})
            cautions.extend(r["cautions"])
        return _res(input_id, fi, total, matched="derived_sum", parts=parts,
                    cautions=cautions, start=start, end=end)

    for cand in _cand_list(spec):
        r = _try_candidate_duration(fi, input_id, cand, start, end)
        if r is not None:
            return r
    if spec.get("absent_means_zero") and (start, end) in fi._cf_periods:
        # Cash-flow-face completeness: the statement's sections sum to their
        # totals, so a located cash flow statement with no such line is the
        # filer reporting none (no dividends paid, nothing repurchased).
        return _res(input_id, fi, 0.0, matched="zero_by_completeness",
                    cautions=[f"No {input_id.replace('_', ' ')} line on the "
                              "cash flow statement for this period; the "
                              "statement reports none."],
                    start=start, end=end)
    return None


def _try_candidate_duration(fi, input_id, cand, start, end):
    if "concept" in cand:
        f = fi.duration_fact(cand["concept"], start, end)
        if f is None:
            return None
        return _res(input_id, fi, f["value"], matched="concept",
                    concept=cand["concept"], cautions=[cand.get("caution")],
                    family=cand.get("family"), start=start, end=end)
    if "sum" in cand:
        parts, total, found = [], 0.0, 0
        for concept in cand["sum"]:
            f = fi.duration_fact(concept, start, end)
            if f is not None:
                found += 1
                total += f["value"]
                parts.append({"concept": concept, "value": f["value"],
                              "label": f.get("label"), "matched_by": "concept"})
        need = cand.get("min_present", len(cand["sum"]))
        if found < max(1, need):
            return None
        return _res(input_id, fi, total, matched="sum", parts=parts,
                    cautions=[cand.get("caution")],
                    family=cand.get("family"), start=start, end=end)
    return None


def resolve_instant(fi: FilingIndex, input_id: str, date: str):
    """One input at one balance-sheet date in one filing, or None."""
    spec = input_spec(input_id)
    if spec.get("resolve") == "aggregate":
        return _resolve_aggregate(fi, input_id, spec, date)

    for cand in _cand_list(spec):
        if "concept" in cand:
            f = fi.instant_fact(cand["concept"], date)
            if f is not None:
                return _res(input_id, fi, f["value"], matched="concept",
                            concept=cand["concept"],
                            cautions=[cand.get("caution")], instant=date)
        elif "sum" in cand:
            parts, total, found = [], 0.0, 0
            for concept in cand["sum"]:
                f = fi.instant_fact(concept, date)
                if f is not None:
                    found += 1
                    total += f["value"]
                    parts.append({"concept": concept, "value": f["value"],
                                  "label": f.get("label"), "matched_by": "concept"})
            if found >= max(1, cand.get("min_present", len(cand["sum"]))):
                return _res(input_id, fi, total, matched="sum", parts=parts,
                            cautions=[cand.get("caution")], instant=date)
        elif "subtract" in cand:
            top = fi.instant_fact(cand["subtract"]["from"], date)
            take = fi.instant_fact(cand["subtract"]["take"], date)
            if top is not None and take is not None:
                parts = [{"concept": cand["subtract"]["from"], "value": top["value"],
                          "matched_by": "concept"},
                         {"concept": cand["subtract"]["take"], "value": -take["value"],
                          "matched_by": "concept"}]
                return _res(input_id, fi, top["value"] - take["value"],
                            matched="subtract", parts=parts,
                            cautions=[cand.get("caution")], instant=date)

    if spec.get("absent_means_zero") and fi.face_instants(date):
        return _res(input_id, fi, 0.0, matched="zero_by_completeness",
                    cautions=[f"No {input_id.replace('_', ' ')} line on the "
                              "balance-sheet face at this date; the face sums "
                              "to its total, so the statement reports none."],
                    instant=date)
    return None


# -- debt aggregates ---------------------------------------------------------

def _patterns(spec):
    lp = spec.get("label_patterns") or {}
    inc = lp.get("include")
    exc = lp.get("exclude")
    return (re.compile(inc, re.I) if inc else None,
            re.compile(exc, re.I) if exc else None)


_LEASE_RE = re.compile(r"leas", re.I)


def _resolve_aggregate(fi, input_id, spec, date):
    face = fi.face_instants(date)
    if not face:
        return None      # can't assert disjointness without the face

    cautions, parts = [], []
    counted = set()
    lease_combined = set(spec.get("lease_combined") or [])
    includes_leases = False

    for concept in spec.get("total_candidates") or []:
        f = fi.instant_fact(concept, date)
        if f is not None and any(x.get("concept") == concept for x in face):
            r = _res(input_id, fi, f["value"], matched="total",
                     concept=concept, instant=date)
            r["includes_finance_leases"] = False
            return r

    total, found = 0.0, False
    for concept in spec.get("components") or []:
        f = next((x for x in face if x.get("concept") == concept), None)
        if f is None:
            continue
        if f.get("balance") == "debit":
            # A debit-balance element on the liability list is an asset in
            # disguise (an investment book, a receivable). Summing it would
            # inflate debt by the whole portfolio; skipping it loudly is the
            # only safe move.
            cautions.append(
                f'Skipped "{f.get("label") or concept}" ({concept}): it is a '
                "debit-balance (asset-side) element and cannot be a "
                "borrowing.")
            counted.add(concept)
            continue
        total += f["value"]
        found = True
        counted.add(concept)
        parts.append({"concept": concept, "label": f.get("label"),
                      "value": f["value"], "matched_by": "concept"})
        if concept in lease_combined:
            includes_leases = True
            cautions.append(f"{concept} combines debt with finance leases; "
                            "finance leases are not added again on top.")

    inc, exc = _patterns(spec)
    if inc is not None:
        for f in face:
            c = f.get("concept") or ""
            if c in counted or c.startswith("dei:"):
                continue
            # Match the PRINTED LABEL only. Matching concept QNames pulled
            # us-gaap:...DebtSecurities... asset lines into total debt (the
            # 'Debt' in the name is the securities' kind, not a borrowing).
            label = f.get("label") or ""
            if not label:
                continue
            if inc.search(label) and not (exc and exc.search(label)):
                if f.get("balance") == "debit":
                    cautions.append(
                        f'Skipped "{label}" ({c}): debt-like caption but a '
                        "debit-balance (asset-side) element.")
                    counted.add(c)
                    continue
                total += f["value"]
                found = True
                counted.add(c)
                parts.append({"concept": c, "label": label, "value": f["value"],
                              "matched_by": "label_pattern"})
                cautions.append(
                    f'Included by label match, not by a mapped concept: '
                    f'"{label}" ({c}) = {f["value"]:,.0f}. Verify against '
                    "the filing; add the concept to the map to make this "
                    "certain.")
                if _LEASE_RE.search(label) or _LEASE_RE.search(c):
                    includes_leases = True
                    cautions.append(
                        f'"{label}" appears to combine debt with lease '
                        "obligations; finance leases are not added again on "
                        "top.")

    if not found:
        # A recognised-total fallback must be tried BEFORE any completeness
        # zero: a filer whose only debt line is us-gaap:LongTermDebt would
        # otherwise get a confident zero with the real figure sitting in the
        # same filing.
        for cand in spec.get("fallback_total") or []:
            f = fi.instant_fact(cand["concept"], date)
            if f is not None:
                r = _res(input_id, fi, f["value"], matched="fallback_total",
                         concept=cand["concept"],
                         cautions=[cand.get("caution")], instant=date)
                r["includes_finance_leases"] = False
                return r
        # Split aggregates (short/long classification) may not claim zero
        # while unclassifiable debt-like lines sit on the same face — the
        # guard spec (total_debt) knows how to spot them.
        guard = spec.get("zero_guard")
        if guard:
            gspec = input_spec(guard)
            ginc, gexc = _patterns(gspec)
            gconcepts = set(gspec.get("components") or []) \
                | set(gspec.get("total_candidates") or [])
            for f in face:
                c = f.get("concept") or ""
                label = f.get("label") or ""
                if c in counted or f.get("balance") == "debit":
                    continue
                concept_hit = c in gconcepts
                label_hit = bool(ginc and label and ginc.search(label)
                                 and not (gexc and gexc.search(label)))
                if concept_hit or label_hit:
                    return None     # debt exists here; the split is unknowable
        if spec.get("absent_means_zero"):
            r = _res(input_id, fi, 0.0, matched="zero_by_completeness",
                     cautions=["No recognised debt line on the balance-sheet "
                               "face at this date; the face sums to its "
                               "total, so the statement reports none."],
                     instant=date)
            r["includes_finance_leases"] = False
            return r
        return None

    r = _res(input_id, fi, total, matched="aggregate", parts=parts,
             cautions=cautions, instant=date)
    r["includes_finance_leases"] = includes_leases
    return r


# -- cover-page shares -------------------------------------------------------

def resolve_cover_shares(fi: FilingIndex):
    """Shares outstanding from the filing cover.

    Returns {"classes": [{"member", "label", "value"}...], "total": float,
             "source": ..., "accession": ..., "cautions": [...]} or None.
    Multi-class filers are kept per class — each class has its own price, so a
    single total would be the wrong shape for market cap.
    """
    per_class = fi.class_share_facts()
    if per_class:
        classes, seen, instants = [], set(), set()
        for f in per_class:
            dims = f.get("dimensions") or {}
            member = next((dims[a] for a in CLASS_AXES if a in dims), None)
            if member in seen or not isinstance(f.get("value"), (int, float)):
                continue
            seen.add(member)
            instants.add(str(f.get("instant") or "")[:10] or None)
            classes.append({"member": member, "label": f.get("label"),
                            "value": float(f["value"]),
                            "symbol": fi.class_symbol(member)})
        if classes:
            # `stated` is the date the cover fact itself claims — carried
            # only when every class states the same one, never averaged.
            only = instants.pop() if len(instants) == 1 else None
            return {"classes": classes,
                    "total": sum(c["value"] for c in classes),
                    "source": "dei:EntityCommonStockSharesOutstanding (per class)",
                    "accession": fi.accession, "filed": fi.filed,
                    "stated": only, "cautions": []}
    f = fi.dei_value("dei:EntityCommonStockSharesOutstanding")
    if f is not None and isinstance(f.get("value"), (int, float)):
        return {"classes": None, "total": float(f["value"]),
                "source": "dei:EntityCommonStockSharesOutstanding",
                "accession": fi.accession, "filed": fi.filed,
                "stated": str(f.get("instant") or "")[:10] or None,
                "cautions": []}
    dates = fi.balance_dates()
    if dates:
        f = fi.instant_fact("us-gaap:CommonStockSharesOutstanding", dates[-1])
        if f is not None:
            return {"classes": None, "total": float(f["value"]),
                    "source": "us-gaap:CommonStockSharesOutstanding "
                              "(balance sheet; cover fact missing)",
                    "accession": fi.accession, "filed": fi.filed,
                    "stated": str(dates[-1])[:10],
                    "cautions": ["Share count is at the balance-sheet date, "
                                 "not the cover date."]}
    return None


def public_float(fi: FilingIndex):
    """dei:EntityPublicFloat with its measurement date, or None."""
    f = fi.dei_value("dei:EntityPublicFloat")
    if f is None or not isinstance(f.get("value"), (int, float)):
        return None
    return {"value": float(f["value"]),
            "measured": f.get("instant") or f.get("end"),
            "accession": fi.accession, "filed": fi.filed}
