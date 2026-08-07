"""Computation semantics: absence over guessing, manual over fetched, and the
public-float cross-check catching a wrong price basis."""

from conftest import dur, filing, inst, balance_face

from engine import crosscheck, dataview, price_store
from engine.compute import Ctx, compute_all


def _synthetic_company():
    """One clean fiscal year with a cash-flow face and a balance sheet."""
    end, start = "2023-12-31", "2023-01-01"
    facts = [
        dur("us-gaap:Revenues", start, end, 1000),
        dur("us-gaap:NetCashProvidedByUsedInOperatingActivities", start, end,
            200, stmt="CashFlowStatement"),
        dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", start, end,
            50, stmt="CashFlowStatement"),
        dur("us-gaap:NetIncomeLoss", start, end, 120),
    ] + balance_face(end, assets=800, extra=[
        inst("us-gaap:LongTermDebtNoncurrent", end, 100),
    ])
    return [filing("S-1", "10-K", "2024-02-20", end, facts)]


class TestAbsenceSemantics:
    def test_fcf_computes_and_carries_provenance(self):
        res = compute_all(_synthetic_company(), None, ["SYN"],
                          entry_ids=["fcf_ttm"])
        r = res["fcf_ttm"]
        assert r["status"] == "computed"
        assert r["value"] == 150
        assert any("S-1" in p for p in r["provenance"])

    def test_missing_capex_makes_fcf_absent_never_cfo_alone(self):
        """A REIT-shaped filer: CFO exists, no PP&E capex caption. FCF must
        be absent with the reason — CFO minus a guessed zero would be the
        plausible wrong number."""
        end, start = "2023-12-31", "2023-01-01"
        f = filing("S-2", "10-K", "2024-02-20", end, [
            dur("us-gaap:NetCashProvidedByUsedInOperatingActivities", start,
                end, 200, stmt="CashFlowStatement"),
            dur("us-gaap:Revenues", start, end, 1000),
        ])
        r = compute_all([f], None, ["SYN"], entry_ids=["fcf_ttm"])["fcf_ttm"]
        assert r["status"] == "absent"
        assert "capital expenditure" in r["reason"]

    def test_not_meaningful_negative_equity_is_absent_with_the_test_named(self):
        end, start = "2023-12-31", "2023-01-01"
        f = filing("S-3", "10-K", "2024-02-20", end,
                   balance_face(end, extra=[
                       inst("us-gaap:LongTermDebtNoncurrent", end, 100),
                       inst("us-gaap:StockholdersEquity", end, -40),
                   ]))
        r = compute_all([f], None, ["SYN"],
                        entry_ids=["debt_to_equity"])["debt_to_equity"]
        assert r["status"] == "absent"
        assert "Not meaningful" in r["reason"]

    def test_one_broken_entry_cannot_hide_the_others(self, monkeypatch):
        from engine import compute as compute_mod
        def boom(ctx):
            raise RuntimeError("kaput")
        monkeypatch.setitem(compute_mod.REGISTRY, "current_ratio", boom)
        res = compute_all(_synthetic_company(), None, ["SYN"],
                          entry_ids=["current_ratio", "fcf_ttm"])
        assert res["current_ratio"]["status"] == "absent"
        assert "kaput" in res["current_ratio"]["reason"]
        assert res["fcf_ttm"]["status"] == "computed"


class TestManualOverFetched:
    def test_hand_entered_wins_and_both_sides_survive(self):
        computed = {"fcf_ttm": {"status": "computed", "value": 150.0},
                    "current_ratio": {"status": "computed", "value": 1.4}}
        security = {"metrics": {"fcf_ttm": 149.0}}
        values, sources = dataview.merged_values(security, computed)
        assert values["fcf_ttm"] == 149.0
        assert sources["fcf_ttm"] == "manual"
        assert values["current_ratio"] == 1.4
        assert sources["current_ratio"] == "computed"
        # nothing was written into the security by the merge
        assert security["metrics"] == {"fcf_ttm": 149.0}

    def test_absent_computed_never_contributes_a_value(self):
        computed = {"pe_ttm": {"status": "absent", "reason": "no prices"}}
        values, sources = dataview.merged_values({"metrics": {}}, computed)
        assert "pe_ttm" not in values


class TestCrosscheck:
    def _filing_with_float(self, float_usd, shares):
        end = "2023-12-31"
        facts = balance_face(end) + [
            {**inst("dei:EntityPublicFloat", "2023-06-30", float_usd,
                    stmt=None), "currency": "USD"},
            {**inst("dei:EntityCommonStockSharesOutstanding", "2024-01-25",
                    shares, stmt=None), "unit": "shares", "currency": None},
        ]
        return [filing("S-4", "10-K", "2024-02-20", end, facts)]

    def _prices(self, close):
        doc = price_store.load(300)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2023-06-30", close, 1000]], [])
        return doc

    def test_consistent_market_cap_passes(self):
        filings = self._filing_with_float(9.0e9, 1.0e9)   # float 9B
        out = crosscheck.run(filings, self._prices(10.0), ["SYN"])  # mcap 10B
        assert out["checks"][0]["status"] == "pass"

    def test_adjusted_price_contamination_fails_loudly(self):
        """A dividend-adjusted historical close is far below the as-traded
        close; market cap lands under half of float — the exact signature the
        check exists for."""
        filings = self._filing_with_float(9.0e9, 1.0e9)
        out = crosscheck.run(filings, self._prices(4.0), ["SYN"])
        c = out["checks"][0]
        assert c["status"] == "fail"
        assert "adjusted" in c["note"]

    def test_no_price_reports_why_it_could_not_run(self):
        filings = self._filing_with_float(9.0e9, 1.0e9)
        out = crosscheck.run(filings, price_store.load(301), ["SYN"])
        c = out["checks"][0]
        assert c["status"] == "skipped"
        assert "price" in c["note"]
