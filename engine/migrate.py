"""One-time migration of securities from the retired metric set to the bank.

The old flat schema carried fifteen metric identifiers. Eleven of them name
the same measure as a bank entry and are renamed to the bank id — the value
is untouched, only the key changes, and each rename is recorded in the
migration report together with any definitional caveat. Four have no honest
bank equivalent; their values move under ``legacy_metrics`` where they are
preserved verbatim and surfaced in the UI, never scored and never dropped.
An identifier this module does not recognise is treated the same way, with
its raw id as the label — nothing is guessed at.

Entry snapshots, overrides and exit records are never touched. They are
recorded history: what was true at the time, under the rules in force at the
time. A legacy snapshot is identified by its ``ruleset_version`` field and
renders as the frozen record it is.

The migration is explicit and reversible: the original file is backed up
beside the data before anything is written, the old ``rules.json`` (the
retired ruleset history) is archived as ``rules.legacy.json`` rather than
deleted, and a report of exactly what moved is persisted and shown in the
app. Re-running is a no-op — a vocabulary marker on securities.json records
that the file already speaks bank ids.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import store
from .profiles import bank_index, load_bank

VOCABULARY = "metric-bank/1"
REPORT_FILE = "migration-report.json"

# Old ids whose bank entry names the same measure. The note records anything
# the old definition left unstated that the bank pins down; the value itself
# is carried unchanged.
RESOLVED = {
    "gross_margin": {
        "to": "gross_margin_ttm",
        "note": "The old set stated no window; the bank's current-reading "
                "form is trailing twelve months.",
    },
    "fcf_margin": {
        "to": "fcf_margin_ttm",
        "note": "The old set stated no window; the bank's current-reading "
                "form is trailing twelve months.",
    },
    "net_debt_ebitda": {"to": "net_debt_to_ebitda", "note": None},
    "interest_cover": {"to": "interest_coverage", "note": None},
    "current_ratio": {"to": "current_ratio", "note": None},
    "share_change_5y": {
        "to": "diluted_share_count_change_5y",
        "note": "The old set did not say which share count; the bank uses "
                "diluted weighted shares.",
    },
    "pe": {"to": "pe_ttm", "note": None},
    "peg": {
        "to": "peg_trailing",
        "note": "The old set paired its TTM P/E with its 5-year EPS CAGR, "
                "which is exactly the bank's trailing PEG formula.",
    },
    "ev_ebit": {"to": "ev_to_ebit", "note": None},
    "rev_cagr_5y": {"to": "revenue_cagr_5y", "note": None},
    "eps_cagr_5y": {"to": "eps_cagr_5y", "note": None},
}

# Old ids with no bank equivalent. Values are preserved, not scored.
UNRESOLVED = {
    "roic": {
        "label": "Return on invested capital",
        "fmt": "pct",
        "why": "The bank's only ROIC entry is a five-year median "
               "(roic_median_5y); a point-in-time reading is a different "
               "measure and renaming it would claim a window that was "
               "never recorded.",
    },
    "fcf_yield": {
        "label": "Free cash flow yield",
        "fmt": "pct",
        "why": "The old value was free cash flow over market value; the "
               "bank measures it on enterprise value (fcf_yield_on_ev). "
               "Different denominator, different number.",
    },
    "insider_own": {
        "label": "Insider ownership",
        "fmt": "pct",
        "why": "The bank has no insider-ownership-percentage entry. "
               "insider_net_buying_6m measures transactions, not the level "
               "of ownership.",
    },
    "op_margin_trend": {
        "label": "Operating margin trend, 3-year",
        "fmt": "ppt",
        "why": "The bank has no operating-margin entry; "
               "gross_margin_change_3y measures gross margin, which is a "
               "different line of the income statement.",
    },
}

# Labels for every retired id, for rendering legacy snapshots and overrides.
LEGACY_LABELS = {
    "roic": {"label": "Return on invested capital", "fmt": "pct"},
    "gross_margin": {"label": "Gross margin", "fmt": "pct"},
    "fcf_margin": {"label": "Free cash flow margin", "fmt": "pct"},
    "insider_own": {"label": "Insider ownership", "fmt": "pct"},
    "net_debt_ebitda": {"label": "Net debt / EBITDA", "fmt": "x"},
    "interest_cover": {"label": "Interest coverage", "fmt": "x"},
    "current_ratio": {"label": "Current ratio", "fmt": "x"},
    "share_change_5y": {"label": "Share count, 5-year change", "fmt": "pctd"},
    "fcf_yield": {"label": "Free cash flow yield", "fmt": "pct"},
    "pe": {"label": "Price / earnings (TTM)", "fmt": "x"},
    "peg": {"label": "PEG ratio", "fmt": "x"},
    "ev_ebit": {"label": "EV / EBIT", "fmt": "x"},
    "rev_cagr_5y": {"label": "Revenue CAGR, 5-year", "fmt": "pct"},
    "eps_cagr_5y": {"label": "EPS CAGR, 5-year", "fmt": "pct"},
    "op_margin_trend": {"label": "Operating margin trend, 3-year", "fmt": "ppt"},
}


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def migrate_document(doc: dict, bank_ids: set[str]) -> tuple[dict, dict]:
    """Pure transform. Returns (migrated document, report).

    Never mutates its input. Snapshots, overrides and exits pass through
    untouched.
    """
    doc = json.loads(json.dumps(doc))       # deep copy, JSON-shaped by contract
    renamed: dict[str, int] = {}
    preserved: dict[str, dict] = {}

    for s in doc.get("securities", []):
        metrics = s.get("metrics") or {}
        new_metrics, legacy = {}, dict(s.get("legacy_metrics") or {})
        for key, value in metrics.items():
            if key in RESOLVED:
                new_metrics[RESOLVED[key]["to"]] = value
                renamed[key] = renamed.get(key, 0) + 1
            elif key in UNRESOLVED:
                legacy[key] = value
                entry = preserved.setdefault(key, {
                    "label": UNRESOLVED[key]["label"],
                    "why": UNRESOLVED[key]["why"], "count": 0})
                entry["count"] += 1
            elif key in bank_ids:
                new_metrics[key] = value    # already speaks the bank
            else:
                legacy[key] = value
                entry = preserved.setdefault(key, {
                    "label": key,
                    "why": "This identifier is not in the retired set and "
                           "not in the bank. It is preserved as found.",
                    "count": 0})
                entry["count"] += 1
        s["metrics"] = new_metrics
        if legacy:
            s["legacy_metrics"] = legacy

        history = s.get("history") or {}
        if history:
            new_hist, legacy_hist = {}, dict(s.get("legacy_history") or {})
            for key, series in history.items():
                if key in RESOLVED:
                    new_hist[RESOLVED[key]["to"]] = series
                elif key in bank_ids:
                    new_hist[key] = series
                else:
                    legacy_hist[key] = series
            s["history"] = new_hist
            if legacy_hist:
                s["legacy_history"] = legacy_hist

    doc["metrics_vocabulary"] = VOCABULARY
    report = {
        "migrated": _stamp(),
        "securities": len(doc.get("securities", [])),
        "renamed": [{"from": old, "to": RESOLVED[old]["to"],
                     "values": n, "note": RESOLVED[old]["note"]}
                    for old, n in sorted(renamed.items())],
        "preserved": [{"id": old, **info}
                      for old, info in sorted(preserved.items())],
    }
    return doc, report


def _read_report():
    path = store.data_dir() / REPORT_FILE
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def ensure_migrated():
    """Migrate the on-disk journal once, loudly and reversibly.

    Returns the persisted migration report, or None when no migration was
    ever needed (a fresh install starts in the bank vocabulary).
    """
    doc = store.load("securities.json")
    if doc.get("metrics_vocabulary") == VOCABULARY:
        return _read_report()

    bank_ids = set(bank_index(load_bank("metric-bank")))
    has_values = any((s.get("metrics") or s.get("history"))
                     for s in doc.get("securities", []))
    d = store.data_dir()

    if not has_values:
        # Nothing recorded against the old set; just stamp the vocabulary.
        doc["metrics_vocabulary"] = VOCABULARY
        store.save("securities.json", doc)
        _archive_rules()
        return _read_report()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_name = f"securities.pre-migration-{stamp}.json"
    (d / backup_name).write_text(
        json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    migrated, report = migrate_document(doc, bank_ids)
    report["backup"] = backup_name
    report["rules_archived"] = _archive_rules()
    # Report before data: if the process dies between the two writes, the
    # vocabulary marker is not yet stamped, so the next launch simply migrates
    # again and overwrites this report. The other order could complete the
    # migration and lose its record.
    store.save(REPORT_FILE, report)
    store.save("securities.json", migrated)
    return report


def _archive_rules():
    """The retired ruleset history is recorded history: archive, never delete."""
    d = store.data_dir()
    src = d / "rules.json"
    if not src.exists():
        return None
    dest = d / "rules.legacy.json"
    if dest.exists():
        dest = d / f"rules.legacy.{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    src.rename(dest)
    return dest.name
