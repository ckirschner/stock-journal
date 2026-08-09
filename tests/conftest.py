"""Shared builders for synthetic filings, shaped exactly like the gateway's
extraction output. Synthetic companies are invented; real-company evidence
lives only in tests/fixtures/groundtruth (hand-read) and fixtures/extracted
(recorded pipeline input for the same filings)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

STRATEGY_FIXTURES = Path(__file__).parent / "fixtures" / "strategies"


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own data dir; nothing touches the real one — and
    the real OS keychain is never touched either: secrets fall back to the
    per-test file store."""
    monkeypatch.setenv("LEDGER_DATA", str(tmp_path / "data"))
    from engine import secrets
    monkeypatch.setattr(secrets, "_DISABLE_KEYRING", True)
    yield


@pytest.fixture
def strategies(tmp_path, monkeypatch):
    """Install fixture strategy bundles and point discovery at them.

    Copied rather than referenced, so a test can edit a bundle's values.yaml
    in place — which is exactly the hand-retuning the rule-change record
    exists to catch, and it cannot be exercised against a read-only fixture.
    """
    root = tmp_path / "strategies"
    root.mkdir(exist_ok=True)

    def install(*names):
        from engine import strategy_loader
        for n in names:
            shutil.copytree(STRATEGY_FIXTURES / n, root / n,
                            dirs_exist_ok=True)
        monkeypatch.setattr(strategy_loader, "SHIPPED_DIR", root)
        return root
    install.root = root
    return install


def journal_for(strategy_id, name="Test journal", inputs=None, config=None):
    """A journal stamped with a discovered strategy, saved and opened.

    Returns (journal, record). Tests that only need the engine use this;
    tests that drive the UI seam go through Api.create_journal, which is the
    same path with the typing and validation the dialog does.
    """
    from engine import journals, strategy_loader
    strategies, reports = strategy_loader.discover()
    record = strategies.get(strategy_id)
    assert record is not None, [r["errors"] for r in reports]
    journal = journals.create(name, record, config=config, inputs=inputs)
    journals.set_open(journal["id"])
    return journal, record


def dur(concept, start, end, value, stmt="IncomeStatement", **kw):
    f = {"concept": concept, "label": kw.pop("label", concept.split(":")[-1]),
         "value": float(value), "unit": "usd", "currency": "USD",
         "decimals": kw.pop("decimals", -6), "period_type": "duration",
         "start": start, "end": end, "instant": None, "dimensions": None,
         "statement_type": stmt, "balance": None, "weight": None,
         "preferred_sign": None}
    f.update(kw)
    return f


def inst(concept, date, value, stmt="BalanceSheet", **kw):
    f = {"concept": concept, "label": kw.pop("label", concept.split(":")[-1]),
         "value": float(value), "unit": "usd", "currency": "USD",
         "decimals": kw.pop("decimals", -6), "period_type": "instant",
         "start": None, "end": None, "instant": date, "dimensions": None,
         "statement_type": stmt, "balance": None, "weight": None,
         "preferred_sign": None}
    f.update(kw)
    return f


def filing(accession, form, filed, period, facts):
    return {"accession": accession, "cik": 999, "form": form, "filed": filed,
            "period_of_report": period, "extracted_at": "2026-01-01T00:00:00",
            "gateway_version": 1, "facts": list(facts)}


def balance_face(date, assets=1000.0, extra=()):
    """A minimal genuine balance-sheet face: the totals plus whatever lines
    the test needs. Totals are what make the face count as located."""
    rows = [inst("us-gaap:Assets", date, assets),
            inst("us-gaap:LiabilitiesAndStockholdersEquity", date, assets)]
    rows.extend(extra)
    return rows


def annual_filing(fy_end, fy_start, accession, filed, revenue,
                  concept="us-gaap:Revenues", comparatives=(), extra=()):
    """A 10-K with its own-year revenue and optional comparative years.
    comparatives: iterable of (start, end, value) under the same concept."""
    facts = [dur(concept, fy_start, fy_end, revenue)]
    for (s, e, v) in comparatives:
        facts.append(dur(concept, s, e, v))
    facts.extend(extra)
    return filing(accession, "10-K", filed, fy_end, facts)
