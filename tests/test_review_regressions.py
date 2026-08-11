"""Regressions from the adversarial review — each of these shipped a
plausible wrong number before it was caught, and each stays pinned here."""

from conftest import annual_filing, dur, filing, inst, balance_face, no_filer

from engine import concept_map as cm
from engine.compute import Ctx, compute_all
from engine.periods import SeriesBuilder, is_absent


def _cf(concept, start, end, value):
    return dur(concept, start, end, value, stmt="CashFlowStatement")


class TestStubNeverServesAsTTM:
    def _stub_company(self):
        fy = annual_filing("2022-06-30", "2021-07-01", "R1-FY", "2022-08-15",
                           1000)
        stub = filing("R1-KT", "10-KT", "2023-03-01", "2022-12-31",
                      [dur("us-gaap:Revenues", "2022-07-01", "2022-12-31", 480)])
        return SeriesBuilder([fy, stub])

    def test_ttm_refuses_the_stub(self):
        t = self._stub_company().ttm("revenue")
        assert is_absent(t)
        assert "stub" in t["reason"]

    def test_ttm_at_refuses_the_stub_observation(self):
        sb = self._stub_company()
        stub_fi = [fi for fi in sb.indices if fi.form == "10-KT"][0]
        t = sb.ttm_at("revenue", stub_fi)
        assert is_absent(t)
        assert "stub" in t["reason"]


class TestTTMSeamDiscipline:
    def test_ttm_refuses_a_family_splice(self):
        """Modified-retrospective 606: FY under the old tag, current YTD
        under the new one — the annual-window family rule applies to the
        TTM's legs too."""
        old = "us-gaap:SalesRevenueNet"
        new = "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        fy = annual_filing("2017-12-31", "2017-01-01", "R2-FY", "2018-02-15",
                           1000, concept=old)
        q = filing("R2-Q2", "10-Q", "2018-07-25", "2018-06-30", [
            dur(new, "2018-01-01", "2018-06-30", 560),
            dur(old, "2017-01-01", "2017-06-30", 490),
        ])
        t = SeriesBuilder([fy, q]).ttm("revenue")
        assert is_absent(t)
        assert "606" in t["reason"] or "famil" in t["reason"]

    def test_ttm_refuses_fy_restated_after_the_quarterly(self):
        """A 10-K/A restates the FY after the newest 10-Q was prepared: the
        FY leg and the comparative YTD leg sit on different bases."""
        fy = annual_filing("2022-12-31", "2022-01-01", "R3-FY", "2023-02-15",
                           1000)
        q = filing("R3-Q2", "10-Q", "2023-07-25", "2023-06-30", [
            dur("us-gaap:Revenues", "2023-01-01", "2023-06-30", 560),
            dur("us-gaap:Revenues", "2022-01-01", "2022-06-30", 490),
        ])
        amendment = annual_filing("2022-12-31", "2022-01-01", "R3-FYA",
                                  "2023-09-10", 950)
        amendment["form"] = "10-K/A"
        t = SeriesBuilder([fy, q, amendment]).ttm("revenue")
        assert is_absent(t)
        assert "restated" in t["reason"]


class TestNewestByPeriodNotFiled:
    def test_late_amendment_of_an_old_quarter_does_not_roll_ttm_back(self):
        fy = annual_filing("2022-12-31", "2022-01-01", "R4-FY", "2023-02-15",
                           1000)
        q1 = filing("R4-Q1", "10-Q", "2023-04-25", "2023-03-31", [
            dur("us-gaap:Revenues", "2023-01-01", "2023-03-31", 240),
            dur("us-gaap:Revenues", "2022-01-01", "2022-03-31", 228),
        ])
        q2 = filing("R4-Q2", "10-Q", "2023-07-25", "2023-06-30", [
            dur("us-gaap:Revenues", "2023-01-01", "2023-06-30", 500),
            dur("us-gaap:Revenues", "2022-01-01", "2022-06-30", 465),
        ])
        q1a = filing("R4-Q1A", "10-Q/A", "2023-09-10", "2023-03-31", [
            dur("us-gaap:Revenues", "2023-01-01", "2023-03-31", 240),
            dur("us-gaap:Revenues", "2022-01-01", "2022-03-31", 228),
        ])
        t = SeriesBuilder([fy, q1, q2, q1a]).ttm("revenue")
        assert not is_absent(t)
        assert t["end"] == "2023-06-30"      # the newest PERIOD, not filing
        assert t["value"] == 1000 - 465 + 500


class TestDividendCessation:
    def test_streak_is_zero_after_a_suspension(self):
        """Paid FY2019–2021, stopped FY2022–2023 (cash-flow face present, no
        dividends line). The completeness zero must enter the series and the
        streak must be 0 — not a stale 3."""
        def year(n, y, div):
            start, end = f"{y}-01-01", f"{y}-12-31"
            facts = [_cf("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                         start, end, 50)]
            if div:
                facts.append(_cf("us-gaap:PaymentsOfDividends", start, end, div))
            return filing(f"R5-{n}", "10-K", f"{y + 1}-02-15", end, facts)
        filings = [year(i, y, d) for i, (y, d) in enumerate(
            [(2019, 10), (2020, 11), (2021, 12), (2022, 0), (2023, 0)])]
        ctx = Ctx(filings, None, ["SYN"], industry=no_filer())
        r = compute_all(filings, None, ["SYN"], industry=no_filer(),
                        entry_ids=["consecutive_dividend_years"])
        assert r["consecutive_dividend_years"]["status"] == "computed"
        assert r["consecutive_dividend_years"]["value"] == 0

    def test_dividend_yield_zero_for_a_never_payer_needs_no_dividend_fact(self):
        """The completeness zero must be reachable through TTM assembly."""
        start, end = "2023-01-01", "2023-12-31"
        f = filing("R6-FY", "10-K", "2024-02-15", end, [
            _cf("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                start, end, 50)])
        t = SeriesBuilder([f]).ttm("dividends_paid")
        assert not is_absent(t)
        assert t["value"] == 0.0


class TestDebtAggregateGuards:
    def test_qname_debt_securities_asset_never_enters_debt(self):
        """'Debt' inside a concept QName is the securities' kind, not a
        borrowing — matching must be against the printed label only, and
        debit-balance elements are rejected outright."""
        d = "2023-12-31"
        fi = cm.FilingIndex(filing("R7", "10-K", "2024-02-01", d, balance_face(d, extra=[
            inst("us-gaap:LongTermDebtNoncurrent", d, 3000),
            inst("us-gaap:AvailableForSaleSecuritiesDebtSecuritiesNoncurrent",
                 d, 210000, label="Long-term marketable securities",
                 balance="debit"),
        ])))
        r = cm.resolve_instant(fi, "total_debt", d)
        assert r["value"] == 3000

    def test_debit_balance_label_match_is_skipped_loudly(self):
        d = "2023-12-31"
        fi = cm.FilingIndex(filing("R8", "10-K", "2024-02-01", d, balance_face(d, extra=[
            inst("us-gaap:LongTermDebtNoncurrent", d, 3000),
            inst("x:MortgageLoansHeld", d, 90000,
                 label="Mortgage loans on real estate", balance="debit"),
        ])))
        r = cm.resolve_instant(fi, "total_debt", d)
        assert r["value"] == 3000
        assert any("debit-balance" in c for c in r["cautions"])

    def test_long_term_debt_fallback_serves_instead_of_zero(self):
        """A filer whose only noncurrent debt line is us-gaap:LongTermDebt
        must get that figure (cautioned), never a completeness zero."""
        d = "2023-12-31"
        fi = cm.FilingIndex(filing("R9", "10-K", "2024-02-01", d, balance_face(d, extra=[
            inst("us-gaap:LongTermDebt", d, 5000, label="Long-term debt"),
        ])))
        r = cm.resolve_instant(fi, "long_term_debt", d)
        assert r is not None
        assert r["value"] == 5000
        assert r["matched"] == "fallback_total"

    def test_split_aggregate_never_claims_zero_beside_unclassified_debt(self):
        """An extension debt line the split can't classify blocks the
        completeness zero: unknown beats a confident 0."""
        d = "2023-12-31"
        fi = cm.FilingIndex(filing("R10", "10-K", "2024-02-01", d, balance_face(d, extra=[
            inst("x:SeniorSecuredFacility", d, 4000,
                 label="Term loans, net"),
        ])))
        assert cm.resolve_instant(fi, "long_term_debt", d) is None
        total = cm.resolve_instant(fi, "total_debt", d)
        assert total["value"] == 4000        # the total still reaches it

    def test_label_matched_lease_combined_line_sets_the_flag(self):
        d = "2023-12-31"
        fi = cm.FilingIndex(filing("R11", "10-K", "2024-02-01", d, balance_face(d, extra=[
            inst("x:DebtAndFinanceLeases", d, 8000,
                 label="Long-term debt and finance lease obligations"),
        ])))
        r = cm.resolve_instant(fi, "total_debt", d)
        assert r["value"] == 8000
        assert r["includes_finance_leases"] is True


class TestInstantSeriesGap:
    def test_missing_year_end_refuses_the_equity_series(self):
        def bs(n, y, equity):
            end = f"{y}-12-31"
            return filing(f"R12-{n}", "10-K", f"{y + 1}-02-15", end,
                          balance_face(end, extra=[
                              inst("us-gaap:StockholdersEquity", end, equity)]))
        filings = [bs(0, 2017, 500)] + [bs(i, y, 900 + i * 100)
                                        for i, y in enumerate(range(2019, 2024), 1)]
        sb = SeriesBuilder(filings)
        r = sb.instant_series_annual("total_equity", 6)
        assert is_absent(r)
        assert "do not run annually" in r["reason"]


class TestNegativeEndpointCagr:
    def test_cagr_to_a_loss_year_is_cleanly_not_meaningful(self):
        """A positive base compounding to a negative endpoint went complex
        ((-x) ** (1/5)) and leaked a TypeError into six entries. It must be a
        readable not-meaningful absence instead.

        Eight fiscal years since growth rates average three at each end, and
        the losses are at the newest three so the LATER mean is what comes
        out negative — the endpoint version of this could reach the same
        place with one loss year, and that is exactly the sensitivity the
        averaging removed."""
        filings = []
        values = [(2019, 100), (2020, 110), (2021, 100), (2022, 120),
                  (2023, 90), (2024, -40), (2025, -10), (2026, -55)]
        for y, ni in values:
            start, end = f"{y}-01-01", f"{y}-12-31"
            filings.append(filing(f"C-{y}", "10-K", f"{y + 1}-02-15", end, [
                dur("us-gaap:NetIncomeLoss", start, end, ni),
                dur("us-gaap:Revenues", start, end, 500 + y - 2021),
            ]))
        res = compute_all(filings, None, ["SYN"], industry=no_filer(),
                          entry_ids=["net_income_cagr_5y",
                                     "ni_minus_revenue_cagr_spread_5y"])
        r = res["net_income_cagr_5y"]
        assert r["status"] == "absent"
        assert "negative" in r["reason"] and "TypeError" not in r["reason"]
        spread = res["ni_minus_revenue_cagr_spread_5y"]
        assert spread["status"] == "absent"
        assert "TypeError" not in spread["reason"]
