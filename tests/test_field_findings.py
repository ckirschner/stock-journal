"""Pins for the two field-test findings that produced wrong numbers on
screen from real filings (2026-08-17).

1. Asserted-nil may only reason from a cash-flow statement that
   demonstrably accounts for the period — its own operating total must
   cover the duration. A 10-Q carrying one stray prior-FY comparative typed
   CashFlowStatement asserted nil annual dividends for Johnson & Johnson
   and zeroed a six-decade capital-return streak.

2. A stock split is a unit change, not a restatement. A per-share window
   spanning a split-explained restatement computes, split-adjusted; one the
   factor does not explain still refuses.

Both are pinned with hand-built filings, not store data — break the guard
and these go red.
"""

from engine import periods


def _fact(concept, value, start, end, stmt=None):
    return {"concept": concept, "value": value, "start": start, "end": end,
            "instant": None, "dimensions": None, "statement_type": stmt,
            "period_type": "duration", "unit": None, "currency": None,
            "decimals": None, "label": "", "balance": None, "weight": None,
            "preferred_sign": 1.0}


def _filing(accession, form, filed, period, facts):
    return {"accession": accession, "cik": 1, "form": form, "filed": filed,
            "period_of_report": period, "facts": facts}


ANCHOR = "us-gaap:NetCashProvidedByUsedInOperatingActivities"
DIVS = "us-gaap:PaymentsOfDividends"
EPS = "us-gaap:EarningsPerShareDiluted"


def _annual_10k(year, filed, dividends=None):
    start, end = f"{year}-01-01", f"{year}-12-31"
    facts = [_fact(ANCHOR, 100.0, start, end, "CashFlowStatement")]
    if dividends is not None:
        facts.append(_fact(DIVS, dividends, start, end, "CashFlowStatement"))
    return _filing(f"K{year}", "10-K", filed, end, facts)


class TestAssertedNilCompleteness:
    def test_anchored_cash_flow_face_still_asserts_nil(self):
        # A real annual CF face (anchor present) with no dividends line IS
        # the filer reporting none — the zero must survive the fix.
        sb = periods.SeriesBuilder([_annual_10k(2024, "2025-02-01")])
        pts = sb.annual_points("dividends_paid")
        assert pts["2024-12-31"][0]["value"] == 0.0

    def test_stray_comparative_cannot_assert_annual_nil(self):
        # The JNJ shape: a 10-Q whose only annual-duration cash-flow fact is
        # one stray comparative. No anchor covers the year, so no nil may be
        # asserted from it — and it must not displace the 10-K's real value.
        k = _annual_10k(2024, "2025-02-01", dividends=500.0)
        q = _filing("Q1", "10-Q", "2025-04-20", "2025-03-31", [
            _fact(ANCHOR, 25.0, "2025-01-01", "2025-03-31",
                  "CashFlowStatement"),
            _fact("us-gaap:PaymentsToAcquireBusinessesNetOfCashAcquired",
                  17.5, "2024-01-01", "2024-12-31", "CashFlowStatement"),
        ])
        sb = periods.SeriesBuilder([k, q])
        pts = sb.annual_points("dividends_paid")
        rows = pts["2024-12-31"]
        assert all(r["value"] == 500.0 for r in rows), (
            "a stray comparative asserted an annual nil")


def _eps_10k(year, filed, eps, prior_eps=None):
    start, end = f"{year}-01-01", f"{year}-12-31"
    facts = [_fact(EPS, eps, start, end, "IncomeStatement")]
    if prior_eps is not None:
        facts.append(_fact(EPS, prior_eps, f"{year - 1}-01-01",
                           f"{year - 1}-12-31", "IncomeStatement"))
    return _filing(f"K{year}", "10-K", filed, end, facts)


class TestSplitAdjustedWindow:
    def _filings(self):
        # The Alphabet shape. FY2019's newest copy is a pre-split vintage
        # (its own 10-K and the FY2020 comparative both pre-date the split;
        # comparatives only reach one year back, so it is never re-reported).
        # The FY2021 10-K, filed after the 20:1 split, restates FY2020
        # (44.0 -> 2.2) and states FY2021 in the new unit.
        return [
            _eps_10k(2019, "2020-02-01", 38.0),
            _eps_10k(2020, "2021-02-01", 44.0, prior_eps=38.0),
            _eps_10k(2021, "2022-08-20", 2.5, prior_eps=2.2),
        ]

    def test_split_explained_restatement_computes_adjusted(self):
        sb = periods.SeriesBuilder(self._filings(),
                                   splits=[["2022-07-18", 20.0]])
        w = sb.annual_window("diluted_eps", 3)
        assert "values" in w, w.get("reason")
        assert w["values"] == [38.0 / 20.0, 2.2, 2.5]
        assert any("Split-adjusted" in c for c in w["cautions"])

    def test_unexplained_restatement_still_refuses(self):
        # Same shape, no split on record: the restatement is real and the
        # window must refuse exactly as before.
        sb = periods.SeriesBuilder(self._filings(), splits=[])
        w = sb.annual_window("diluted_eps", 3)
        assert w.get("absent") is True
        assert "restated" in (w.get("reason") or "")
