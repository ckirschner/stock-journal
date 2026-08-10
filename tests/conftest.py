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


@pytest.fixture
def written_on(monkeypatch):
    """Write dated entries as though on a chosen day.

    Everything the user supplies — a judgement, a thesis, a valuation, a
    hand-entered figure — is stamped by the host at the moment of writing,
    and no caller can hand in its own date. That is the guarantee, so a test
    exercising "what was on record in 2024" cannot ask for it politely: it
    has to move the clock the host reads.

        def test_x(written_on):
            with written_on("2024-03-01"):
                hand_entered.record(s, "fcf_ttm", 149.0)

    Leaving the block restores the real clock, so a test can lay down a
    history and then write today's entry the way the app does.

    `at(day)` writes at noon on the machine's own calendar, which is what the
    real stamp records. It used to be noon UTC, and that is why no test in
    this suite could see the day-boundary bug: noon UTC lands on the same
    calendar day from UTC-11 to UTC+11, so the whole suite passed identically
    at every offset. A fixture that cannot express the failure cannot test
    for it. `at_local(day, hour)` is for the tests that need the edges.
    """
    import contextlib
    from datetime import datetime

    from engine import dated
    real = dated.stamp

    def local(day, hour=12, minute=0):
        return (datetime.fromisoformat(f"{day}T00:00:00")
                .replace(hour=hour, minute=minute)
                .astimezone().isoformat(timespec="seconds"))

    @contextlib.contextmanager
    def at(day, hour=12, minute=0):
        monkeypatch.setattr(dated, "stamp", lambda: local(day, hour, minute))
        try:
            yield
        finally:
            monkeypatch.setattr(dated, "stamp", real)
    return at


def entered(security, day=None, **values):
    """Hand-entered figures on a security's dated record, through the same
    write the dialog uses — bank membership, judgement refusal and all.

    For the many tests that only need a value to exist. Anything asserting
    *when* it was on record should take the `written_on` fixture instead,
    which is scoped by pytest rather than by a try/finally here.
    """
    from datetime import datetime

    from engine import dated, hand_entered
    real = dated.stamp
    try:
        if day:
            dated.stamp = lambda: (
                datetime.fromisoformat(f"{day}T12:00:00")
                .astimezone().isoformat(timespec="seconds"))
        for eid, v in values.items():
            hand_entered.record(security, eid, v)
    finally:
        dated.stamp = real
    return security


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


CLASS_AXIS = "us-gaap:StatementClassOfStockAxis"
MULTICLASS_PRICED, MULTICLASS_UNPRICED = 900.0, 100.0   # 10% has no close
MULTICLASS_CLOSES = (("2025-02-20", 20.0), ("2025-06-27", 20.0))


def multiclass_company(cik, closes=None):
    """A two-class filer where only one class has a stored close of its own.

    Invented company. It exists because this is the case the market-cap blend
    was kept for — the unpriced class is valued at the priced one's close,
    the one approximation in the compute layer — and the condition of keeping
    it was that the reader is told which class, what share of the count, and
    at whose close. Anything checking that a caution survives a trip needs a
    caution to carry.

    `closes` are rows for the listed class alone. The second default row is
    there so a purchase backdated into mid-2025 reconstructs to a real close
    rather than to absence: a figure that cannot be computed carries no
    caution to lose.

    Returns the unpriced class's label, so a test can assert the caution
    names it rather than matching a substring that could come from anywhere.
    """
    from engine import facts_store, price_store
    end, filed = "2024-12-31", "2025-02-20"
    facts = [
        dur("us-gaap:Revenues", "2024-01-01", end, 1000),
        dur("us-gaap:NetIncomeLoss", "2024-01-01", end, 120),
    ] + balance_face(end, assets=800)
    for member, label, count, symbol in (
            ("us-gaap:CommonClassAMember", "Class A", MULTICLASS_PRICED,
             "SYN"),
            ("us-gaap:CommonClassBMember", "Class B", MULTICLASS_UNPRICED,
             None)):
        facts.append({**inst("dei:EntityCommonStockSharesOutstanding", filed,
                             count, stmt=None),
                      "unit": "shares", "currency": None, "label": label,
                      "dimensions": {CLASS_AXIS: member}})
        if symbol:
            facts.append({**inst("dei:TradingSymbol", filed, 0, stmt=None),
                          "value": symbol, "unit": None, "currency": None,
                          "dimensions": {CLASS_AXIS: member}})
    f = filing("M-1", "10-K", filed, end, facts)
    f["cik"] = cik
    facts_store.save_filing(cik, f)
    doc = price_store.load(cik)
    price_store.merge_series(doc, "SYN", "test",
                             [[d, c, 100] for d, c in
                              (closes or MULTICLASS_CLOSES)], [])
    price_store.save(cik, doc)
    return "Class B"


def annual_filing(fy_end, fy_start, accession, filed, revenue,
                  concept="us-gaap:Revenues", comparatives=(), extra=()):
    """A 10-K with its own-year revenue and optional comparative years.
    comparatives: iterable of (start, end, value) under the same concept."""
    facts = [dur(concept, fy_start, fy_end, revenue)]
    for (s, e, v) in comparatives:
        facts.append(dur(concept, s, e, v))
    facts.extend(extra)
    return filing(accession, "10-K", filed, fy_end, facts)
