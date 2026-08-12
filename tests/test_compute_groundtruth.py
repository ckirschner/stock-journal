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
from conftest import no_filer, symbols

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


# These helpers exist to compare a resolved figure against one read by hand
# from the filing, so absence is None here whatever shape the resolver uses to
# express it. The reason a resolution was refused is a different question and
# has its own tests; every one of these cases is a real filing whose numbers
# were read off the document.

def dur(index, iid, s, e):
    r = cm.resolve_duration(index, iid, s, e)
    return None if cm.is_absent(r) else r["value"]


def inst(index, iid, d):
    r = cm.resolve_instant(index, iid, d)
    return None if cm.is_absent(r) else r["value"]


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


class TestGoodwillWrittenOff:
    """What an acquirer later admitted it had not bought.

    Two filings, because the concept resolves two different ways and the
    difference decides what a threshold means. Kraft Heinz carries goodwill as
    its own caption on the face of the income statement, beside a separate and
    larger charge against other intangibles. Target reports one combined
    figure and states the goodwill component only in prose.

    Expected values are hand-read from the primary documents; see
    fixtures/groundtruth/khc-notes.md and tgt-notes.md.
    """

    def test_khc_fy2018_is_the_goodwill_line_and_not_its_neighbour(self):
        """7,008 of goodwill and 8,928 of other intangibles were written off
        in the same year on adjacent lines. Either figure reads as plausible;
        only one is this concept."""
        x = fi(1637459, "0001637459-19-000049")
        assert dur(x, "goodwill_impairment",
                   "2017-12-31", "2018-12-29") == 7008 * M

    def test_khc_prints_an_em_dash_and_it_means_nought(self):
        """A five-year window over this company spans a stated nil and the
        largest charge in the fixture set. Reading the nil as absent would
        drop the year out of a window that has to cover it."""
        x = fi(1637459, "0001637459-19-000049")
        assert dur(x, "goodwill_impairment",
                   "2017-01-01", "2017-12-30") == 0.0

    def test_tgt_combined_caption_resolves_with_its_caution(self):
        """Target's fiscal 2015 charge is 35 combined, of which 12 is
        goodwill. The 35 is what any tagged fact offers, so the 35 is served —
        with the caution saying so, because a reader has to know the figure is
        above the goodwill charge rather than equal to it."""
        x = fi(27419, "0000027419-17-000008")
        r = cm.resolve_duration(x, "goodwill_impairment",
                                "2015-02-01", "2016-01-30")
        assert r["value"] == 35 * M
        assert r["concept"] == "us-gaap:GoodwillAndIntangibleAssetImpairment"
        assert any("at or above the goodwill charge alone" in c
                   for c in r["cautions"])

    def test_tgt_a_year_it_says_had_none(self):
        """"No impairments were recorded in 2016" — stated in the note and
        tagged as a zero, so it is a zero and not a gap."""
        x = fi(27419, "0000027419-17-000008")
        assert dur(x, "goodwill_impairment",
                   "2016-01-31", "2017-01-28") == 0.0


class TestIntangibleAmortisationComesOutOfDandA:
    """The maintenance-capex proxy compares capital spending against what the
    company wrote its assets down by — and acquired intangibles are written
    down without ever being replaced by spending.

    The figures below are hand-read. What makes them worth having is the
    reconciliation in the third test: it is evidence from the printed document
    that the two lines overlap, and subtracting one from the other would be
    wrong if they did not.
    """

    def test_khc_fy2018_amortisation_alone(self):
        x = fi(1637459, "0001637459-19-000049")
        assert dur(x, "intangible_amortisation",
                   "2017-12-31", "2018-12-29") == 290 * M
        assert dur(x, "dda", "2017-12-31", "2018-12-29") == 983 * M

    def test_tgt_three_years_of_it(self):
        x = fi(27419, "0000027419-17-000008")
        assert dur(x, "intangible_amortisation",
                   "2016-01-31", "2017-01-28") == 18 * M
        assert dur(x, "intangible_amortisation",
                   "2015-02-01", "2016-01-30") == 23 * M
        assert dur(x, "intangible_amortisation",
                   "2014-02-02", "2015-01-31") == 22 * M

    def test_tgt_depreciation_plus_amortisation_is_the_dda_line(self):
        """The property note prints depreciation and capital lease
        amortization of 2,280 for fiscal 2016; the intangibles note prints 18;
        the cash flow statement prints 2,298. Read off three separate parts of
        one filing, they reconcile exactly — which is what establishes that
        D&A includes the amortization, and so that D&A less amortization is
        depreciation.

        If they did not overlap, subtracting would understate depreciation,
        which lowers the maintenance-capex floor and RAISES owner earnings.
        The error would flatter, and nothing on screen would say so.
        """
        x = fi(27419, "0000027419-17-000008")
        dda_line = dur(x, "dda", "2016-01-31", "2017-01-28")
        amort = dur(x, "intangible_amortisation", "2016-01-31", "2017-01-28")
        assert dda_line == 2298 * M
        assert dda_line - amort == 2280 * M


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


class TestMulticlassMarketCap:
    """The one approximation in the compute layer, pinned against a real
    three-class filer.

    Alphabet's FY2024 cover states Class A 5,833 million (GOOGL), Class B 860
    million (no trading symbol tagged — the founder class, which does not
    list), Class C 5,497 million (GOOG). Those counts are hand-read from the
    primary document and pinned above; the closes below are chosen for the
    trace and stated as such.

    Class B has no close of its own, so it is valued at a sibling's. That is
    an approximation principle 4 does not otherwise allow, and it earns its
    place only by being deterministic, bounded, and honest about both — which
    is what these tests hold it to.
    """

    A, B, C = 5833 * M, 860 * M, 5497 * M

    def _ctx(self, rows):
        from engine import compute, price_store
        doc = {"schema": price_store.SCHEMA, "cik": 1652044, "series": {}}
        for sym, date, close in rows:
            price_store.merge_series(doc, sym, "test", [[date, close, 100]], [])
        return compute.Ctx([], doc, symbols("GOOG", "GOOGL"),
                           today="2026-08-10", industry=no_filer())

    def _classes(self):
        r = cm.resolve_cover_shares(fi(1652044, "0001652044-25-000014"))
        return r["classes"]

    def test_the_unpriced_class_is_valued_at_the_largest_priced_one(self):
        """Not at whichever series is newest. GOOG closes a day after GOOGL
        here, which is exactly the arrangement that used to decide it — and it
        moved a headline figure every time one class's fetch lagged."""
        from engine import compute
        ctx = self._ctx([("GOOGL", "2026-08-06", 200.0),
                         ("GOOG", "2026-08-07", 198.0)])
        blend = compute.blend_classes(ctx, self._classes())
        # 5,833M x 200.00  +  860M x 200.00 (borrowed)  +  5,497M x 198.00
        assert blend["total"] == (5833 * 200 + 860 * 200 + 5497 * 198) * M
        assert blend["total"] == 2427006 * M
        # and NOT the old rule, which anchored Class B on the newer GOOG close
        assert blend["total"] != (5833 * 200 + 860 * 198 + 5497 * 198) * M

    def test_the_caution_says_how_much_of_the_company_was_assumed(self):
        """Seven percent is a footnote and ninety percent means the figure is
        mostly an assumption. Only the reader can judge which, and only if the
        share is stated."""
        from engine import compute
        ctx = self._ctx([("GOOGL", "2026-08-06", 200.0),
                         ("GOOG", "2026-08-06", 198.0)])
        note = " ".join(compute.blend_classes(ctx, self._classes())["cautions"])
        assert "7.1%" in note                       # 860 / 12,190 of the count
        assert "860,000,000 shares" in note
        assert "GOOGL close of 2026-08-06" in note
        assert "assumption" in note and "not a measurement" in note

    def test_the_caution_never_claims_the_class_is_unlisted(self):
        """A class lands here for three different reasons — genuinely unlisted,
        listed but untagged on the cover, listed and tagged but never fetched.
        The host cannot tell them apart, so it states what it knows (no stored
        close) and not what it would like to conclude."""
        from engine import compute
        ctx = self._ctx([("GOOGL", "2026-08-06", 200.0),
                         ("GOOG", "2026-08-06", 198.0)])
        note = " ".join(compute.blend_classes(ctx, self._classes())["cautions"])
        assert "unlisted" not in note
        assert "no stored close" in note

    def test_staleness_is_measured_against_the_oldest_close_in_the_blend(self):
        """A second class whose prices stopped updating months ago is the one
        worth knowing about, and measuring against the freshest cannot see
        it."""
        from engine import compute
        ctx = self._ctx([("GOOGL", "2026-08-06", 200.0),
                         ("GOOG", "2025-01-02", 198.0)])
        assert compute.blend_classes(ctx, self._classes())["oldest"] \
            == "2025-01-02"

    def test_with_no_priced_class_there_is_nothing_to_anchor_to(self):
        """Absence, not a number built on a symbol that is not a share
        class."""
        from engine import compute
        blend = compute.blend_classes(self._ctx([]), self._classes())
        assert is_absent(blend)
        assert "none of the 3 share classes" in blend["reason"]
        assert "without inventing a price" in blend["reason"]

    def test_a_class_with_its_own_close_never_borrows(self):
        """The approximation applies only where there is nothing else. Both
        listed classes are priced at their own closes, so only Class B is
        assumed."""
        from engine import compute
        ctx = self._ctx([("GOOGL", "2026-08-06", 200.0),
                         ("GOOG", "2026-08-06", 150.0)])
        blend = compute.blend_classes(ctx, self._classes())
        assert blend["total"] == (5833 * 200 + 860 * 200 + 5497 * 150) * M
        borrowed = [p for p in blend["provenance"] if "borrowed" in p]
        assert len(borrowed) == 1 and "860,000,000" in borrowed[0]

    def test_the_live_and_historical_blends_use_one_anchor_rule(self):
        """P/E against its own five-year median compares a current figure with
        a historical one. Two anchor rules made those two numbers rest on
        different share classes, which is the one thing that comparison must
        not do."""
        from engine import compute
        ctx = self._ctx([("GOOGL", "2026-08-06", 200.0),
                         ("GOOG", "2026-08-07", 198.0)])
        classes = self._classes()
        live = compute.blend_classes(ctx, classes)
        then = compute.blend_classes(ctx, classes, on="2026-08-07")
        assert live["total"] == then["total"] == 2427006 * M
