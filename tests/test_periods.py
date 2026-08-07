"""Period assembly: the behaviours that would serve a plausible wrong number.

Mixed-basis windows must be impossible by construction — including the
cross-tag restatement (the value moved to a different element, so within-tag
tracking never sees it), the modified-retrospective family switch (no number
ever disagrees because no year was reported on both bases), and the
transition-stub gap that breaks year tiling.
"""

from conftest import annual_filing, dur, filing, inst, balance_face

from engine.periods import SeriesBuilder, is_absent


def _rev(sb, n):
    return sb.annual_window("revenue", n)


class TestBasisWindows:
    def _restated_company(self):
        """FY2016..FY2019; FY2018's 10-K restated FY2016-17 under a new tag —
        the MSFT-shaped case. Values as first reported: 100, 110; restated:
        108, 118."""
        old, new = "us-gaap:SalesRevenueNet", \
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        f2016 = annual_filing("2016-12-31", "2016-01-01", "A-2016",
                              "2017-02-01", 100, concept=old,
                              comparatives=[("2015-01-01", "2015-12-31", 90)])
        f2017 = annual_filing("2017-12-31", "2017-01-01", "A-2017",
                              "2018-02-01", 110, concept=old,
                              comparatives=[("2016-01-01", "2016-12-31", 100)])
        f2018 = annual_filing("2018-12-31", "2018-01-01", "A-2018",
                              "2019-02-01", 125, concept=new,
                              comparatives=[("2017-01-01", "2017-12-31", 118),
                                            ("2016-01-01", "2016-12-31", 108)])
        f2019 = annual_filing("2019-12-31", "2019-01-01", "A-2019",
                              "2020-02-01", 130, concept=new,
                              comparatives=[("2018-01-01", "2018-12-31", 125),
                                            ("2017-01-01", "2017-12-31", 118)])
        return SeriesBuilder([f2016, f2017, f2018, f2019])

    def test_latest_basis_window_is_served(self):
        # FY2017..FY2019 all exist on the restated basis: served, restated
        # values, even though FY2017 was once reported differently.
        w = self._restated_company().annual_window("revenue", 3)
        assert not is_absent(w)
        assert w["values"] == [118, 125, 130]

    def test_window_spanning_the_restatement_is_refused(self):
        # FY2015 was never re-reported after the restatement; any window
        # reaching it mixes bases and must refuse, naming the filings.
        w = self._restated_company().annual_window("revenue", 5)
        assert is_absent(w)
        assert "restated" in w["reason"]
        assert "A-2018" in w["reason"]

    def test_restated_year_itself_uses_newest_value(self):
        sb = self._restated_company()
        pts = sb.annual_points("revenue")
        assert pts["2017-12-31"][0]["value"] == 118       # not 110

    def test_family_switch_without_disagreement_is_refused(self):
        """Modified retrospective: prior years keep their old values under the
        old tag; nothing ever numerically disagrees, only the tag family
        flips. The window must still refuse."""
        old, new = "us-gaap:SalesRevenueNet", \
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
        f1 = annual_filing("2017-12-31", "2017-01-01", "B-2017", "2018-02-01",
                           200, concept=old,
                           comparatives=[("2016-01-01", "2016-12-31", 190)])
        f2 = annual_filing("2018-12-31", "2018-01-01", "B-2018", "2019-02-01",
                           210, concept=new)
        f3 = annual_filing("2019-12-31", "2019-01-01", "B-2019", "2020-02-01",
                           220, concept=new,
                           comparatives=[("2018-01-01", "2018-12-31", 210)])
        w = SeriesBuilder([f1, f2, f3]).annual_window("revenue", 3)
        assert is_absent(w)
        assert "606" in w["reason"] or "family" in w["reason"]

    def test_transition_stub_breaks_tiling(self):
        """A fiscal-year change leaves a gap between annual periods; windows
        spanning it are refused rather than comparing different-length years."""
        f_old = annual_filing("2015-06-27", "2014-06-29", "C-FY15",
                              "2015-08-01", 300)
        # the stub period lives in a 10-KT and is not an annual duration
        f_stub = filing("C-KT", "10-KT", "2016-02-01", "2015-12-31",
                        [dur("us-gaap:Revenues", "2015-06-28", "2015-12-31", 150)])
        f_new = annual_filing("2016-12-31", "2016-01-01", "C-2016",
                              "2017-02-01", 320)
        f_new2 = annual_filing("2017-12-31", "2017-01-01", "C-2017",
                               "2018-02-01", 340,
                               comparatives=[("2016-01-01", "2016-12-31", 320)])
        sb = SeriesBuilder([f_old, f_stub, f_new, f_new2])
        w = sb.annual_window("revenue", 3)      # FY2015-06, CY2016, CY2017
        assert is_absent(w)
        assert "tile" in w["reason"]
        ok = sb.annual_window("revenue", 2)     # CY2016..CY2017 only: fine
        assert not is_absent(ok)
        assert ok["values"] == [320, 340]


class TestTTM:
    def _company(self):
        fy = annual_filing("2023-12-31", "2023-01-01", "D-2023", "2024-02-15",
                           400)
        q2 = filing("D-Q2", "10-Q", "2024-07-25", "2024-06-30", [
            dur("us-gaap:Revenues", "2024-01-01", "2024-06-30", 220),
            dur("us-gaap:Revenues", "2024-04-01", "2024-06-30", 115),
            dur("us-gaap:Revenues", "2023-01-01", "2023-06-30", 200),
            dur("us-gaap:Revenues", "2023-04-01", "2023-06-30", 105),
        ])
        return SeriesBuilder([fy, q2])

    def test_ttm_is_fy_minus_prior_ytd_plus_current_ytd(self):
        t = self._company().ttm("revenue")
        assert not is_absent(t)
        assert t["value"] == 400 - 200 + 220
        # the YTD (not the discrete quarter) columns were used
        assert "YTD" in t["ttm_basis"]

    def test_ttm_without_newer_quarter_is_the_fiscal_year(self):
        fy = annual_filing("2023-12-31", "2023-01-01", "E-2023", "2024-02-15",
                           400)
        t = SeriesBuilder([fy]).ttm("revenue")
        assert t["value"] == 400
        assert "no newer quarterly" in t["ttm_basis"]

    def test_ttm_refuses_a_start_mismatch(self):
        """If the comparative YTD doesn't start where the fiscal year starts,
        a fiscal-calendar shift sits inside the window: refuse."""
        fy = annual_filing("2023-12-31", "2023-01-01", "F-2023", "2024-02-15",
                           400)
        q = filing("F-Q", "10-Q", "2024-07-25", "2024-06-30", [
            dur("us-gaap:Revenues", "2024-01-01", "2024-06-30", 220),
            dur("us-gaap:Revenues", "2023-04-02", "2023-06-30", 200),
        ])
        t = SeriesBuilder([fy, q]).ttm("revenue")
        assert is_absent(t)


class TestStreaks:
    def test_zero_by_completeness_ends_a_dividend_streak(self):
        """A cash-flow face with no dividends line is the filer reporting
        none — the streak must stop there, not read it as unknown."""
        from engine.compute import consecutive_dividend_years, Ctx
        def year(n, end, start, div):
            facts = [dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                         start, end, 50, stmt="CashFlowStatement")]
            if div:
                facts.append(dur("us-gaap:PaymentsOfDividends", start, end,
                                 div, stmt="CashFlowStatement"))
            return filing(f"G-{n}", "10-K", end[:4] + "-12-30", end, facts)
        filings = [year(1, "2021-12-31", "2021-01-01", 0),
                   year(2, "2022-12-31", "2022-01-01", 10),
                   year(3, "2023-12-31", "2023-01-01", 12)]
        ctx = Ctx(filings, None, ["SYN"])
        r = consecutive_dividend_years(ctx)
        assert r["status"] == "computed"
        assert r["value"] == 2
