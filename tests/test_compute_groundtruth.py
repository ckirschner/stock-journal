"""The pipeline against hand-read primary-document truth, offline.

Expected values are transcribed from tests/fixtures/groundtruth/*.json —
figures a person read off the printed statements. Inputs are the recorded
extractions in tests/fixtures/extracted/ (see its README: recorded pipeline
input, never truth). Each case here is one of the failure modes the sample
companies were chosen for; a regression in any of them is a wrong number that
would have shipped silently.
"""

import gzip
import json
from pathlib import Path

import pytest

from engine import concept_map as cm
from engine.periods import SeriesBuilder, is_absent

FIX = Path(__file__).parent / "fixtures" / "extracted"
M = 1e6
K = 1e3


def load_filing(cik, accession):
    p = FIX / f"CIK{cik:010d}" / f"{accession}.json.gz"
    if not p.exists():
        pytest.skip(f"recorded extraction missing: {p.name}")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def fi(cik, accession):
    return cm.FilingIndex(load_filing(cik, accession))


def dur(index, iid, s, e):
    r = cm.resolve_duration(index, iid, s, e)
    return None if r is None else r["value"]


def inst(index, iid, d):
    r = cm.resolve_instant(index, iid, d)
    return None if r is None else r["value"]


class TestMSFT:
    """Baseline, plus the ASC 606 full-retrospective restatement."""

    def test_fy2024_income_and_cash_flow(self):
        x = fi(789019, "0000950170-24-087843")
        assert dur(x, "revenue", "2023-07-01", "2024-06-30") == 245122 * M
        assert dur(x, "operating_income", "2023-07-01", "2024-06-30") == 109433 * M
        assert dur(x, "cfo", "2023-07-01", "2024-06-30") == 118548 * M
        assert dur(x, "capex", "2023-07-01", "2024-06-30") == 44477 * M

    def test_fy2024_debt_is_the_three_printed_lines(self):
        x = fi(789019, "0000950170-24-087843")
        assert inst(x, "total_debt", "2024-06-30") == (6693 + 2249 + 42688) * M

    def test_fy2024_cover_shares_exact(self):
        r = cm.resolve_cover_shares(fi(789019, "0000950170-24-087843"))
        assert r["total"] == 7433038381

    def test_fy2017_serves_the_as_printed_original(self):
        """89,950 exists only in the original filing under the pre-606 tag;
        the restated 96,571 lives in later filings. Filing-anchored
        resolution must return what THIS filing printed."""
        x = fi(789019, "0001564590-17-014900")
        assert dur(x, "revenue", "2016-07-01", "2017-06-30") == 89950 * M
        assert dur(x, "operating_income", "2016-07-01", "2017-06-30") == 22326 * M

    def test_fy2017_debt_excludes_securities_loaned_lines(self):
        """The regression that shipped the label-pattern fix: 'Short-term
        investments (including securities loaned…)' must never read as
        debt."""
        x = fi(789019, "0001564590-17-014900")
        assert inst(x, "total_debt", "2017-06-30") == (9072 + 1049 + 76073) * M


class TestTGT:
    """52/53-week retailer; fiscal 2023 was 53 weeks."""

    def test_53_week_year_resolves_on_exact_dates(self):
        x = fi(27419, "0000027419-24-000032")
        assert dur(x, "revenue", "2023-01-29", "2024-02-03") == 107412 * M
        assert dur(x, "operating_income", "2023-01-29", "2024-02-03") == 5707 * M

    def test_fy2016_operating_income_absent_in_its_own_filing(self):
        """The FY2016 statement prints no 'Operating income' caption. The
        bank entry as written (OperatingIncomeLoss) is honestly absent in
        that filing — not substituted with the printed EBIT subtotal 4,969."""
        x = fi(27419, "0000027419-17-000008")
        assert dur(x, "operating_income", "2016-01-31", "2017-01-28") is None

    def test_fy2016_operating_income_reachable_from_a_later_filing(self):
        x = fi(27419, "0000027419-19-000006")
        assert dur(x, "operating_income", "2016-01-31", "2017-01-28") == 4864 * M

    def test_fy2016_cfo_prefers_the_statement_total(self):
        """5,436 including discontinued operations, not the 5,329
        continuing-only line."""
        x = fi(27419, "0000027419-17-000008")
        assert dur(x, "cfo", "2016-01-31", "2017-01-28") == 5436 * M


class TestKHC:
    """The 2019 restatement: original and restated both reachable, each from
    the filing that reported it."""

    def test_original_fy2017(self):
        x = fi(1637459, "0001637459-18-000015")
        assert dur(x, "revenue", "2017-01-01", "2017-12-30") == 26232 * M
        assert dur(x, "operating_income", "2017-01-01", "2017-12-30") == 6773 * M

    def test_restated_fy2017_from_the_restating_filing(self):
        x = fi(1637459, "0001637459-19-000049")
        assert dur(x, "revenue", "2017-01-01", "2017-12-30") == 26076 * M
        assert dur(x, "operating_income", "2017-01-01", "2017-12-30") == 6057 * M

    def test_restatement_is_a_detected_event(self):
        filings = [load_filing(1637459, "0001637459-18-000015"),
                   load_filing(1637459, "0001637459-19-000049")]
        sb = SeriesBuilder(filings)
        events = sb._restatement_events(sb.annual_points("revenue"))
        assert any(e["year_end"] == "2017-12-30"
                   and e["older_value"] == 26232 * M
                   and e["newer_value"] == 26076 * M for e in events)


class TestPRGO:
    """Fiscal-year-end change; the 10-KT transition stub."""

    def test_stub_period_resolves_exactly(self):
        """The known edgartools statement-builder defect drops the stub; the
        raw-fact path this pipeline uses must recover it."""
        x = fi(1585364, "0001585364-16-000245")
        assert dur(x, "revenue", "2015-06-28", "2015-12-31") == 2769.5 * M
        assert dur(x, "operating_income", "2015-06-28", "2015-12-31") == 94.5 * M

    def test_calendar_year_after_the_change(self):
        x = fi(1585364, "0001585364-24-000009")
        assert dur(x, "revenue", "2023-01-01", "2023-12-31") == 4655.6 * M


class TestGOOGL:
    """Three share classes; cover counts tagged exact-in-millions."""

    def test_per_class_cover_shares_with_symbols(self):
        r = cm.resolve_cover_shares(fi(1652044, "0001652044-25-000014"))
        assert r["classes"] is not None
        by = {c["member"].split(":")[-1]: c for c in r["classes"]}
        assert by["CommonClassAMember"]["value"] == 5833 * M
        assert by["CommonClassAMember"]["symbol"] == "GOOGL"
        assert by["CommonClassBMember"]["value"] == 860 * M
        assert by["CommonClassBMember"]["symbol"] is None   # unlisted
        c_class = by.get("CommonClassCMember") or by.get("CapitalClassCMember")
        assert c_class["value"] == 5497 * M
        assert c_class["symbol"] == "GOOG"

    def test_fy2024_statements(self):
        x = fi(1652044, "0001652044-25-000014")
        assert dur(x, "revenue", "2024-01-01", "2024-12-31") == 350018 * M
        assert dur(x, "capex", "2024-01-01", "2024-12-31") == 52535 * M


class TestRealtyIncome:
    """REIT: thousands scale, extension debt line, honest absences."""

    def test_values_arrive_unscaled(self):
        x = fi(726728, "0000726728-25-000055")
        assert dur(x, "revenue", "2024-01-01", "2024-12-31") == 5271142 * K

    def test_operating_income_and_capex_are_honestly_absent(self):
        x = fi(726728, "0000726728-25-000055")
        assert dur(x, "operating_income", "2024-01-01", "2024-12-31") is None
        # PaymentsForCapitalImprovements exists in this filing and is real-
        # estate improvements, not PP&E capex; the map refuses it.
        assert dur(x, "capex", "2024-01-01", "2024-12-31") is None

    def test_total_debt_sums_all_four_printed_lines(self):
        """Including the extension-tagged revolver line companyfacts cannot
        see — the case the hybrid data path was chosen for."""
        x = fi(726728, "0000726728-25-000055")
        r = cm.resolve_instant(x, "total_debt", "2024-12-31")
        assert r["value"] == 26226994 * K
        assert any(p["matched_by"] == "label_pattern"
                   and p["concept"] == "o:LineOfCreditAndCommercialPaper"
                   for p in r["parts"])
        assert any("label match" in c for c in r["cautions"])

    def test_fy2016_debt_includes_the_extension_notes_line(self):
        x = fi(726728, "0001104659-17-011170")
        r = cm.resolve_instant(x, "total_debt", "2016-12-31")
        assert r["value"] == 5839605 * K
