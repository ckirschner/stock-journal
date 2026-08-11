"""Computation semantics: absence over guessing, manual over fetched, and the
public-float cross-check catching a wrong price basis."""

from conftest import dur, entered, filing, inst, balance_face, no_filer

from engine import context, crosscheck, dataview, price_store
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
                          industry=no_filer(),
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
        r = compute_all([f], None, ["SYN"], industry=no_filer(),
                        entry_ids=["fcf_ttm"])["fcf_ttm"]
        assert r["status"] == "absent"
        assert "capital expenditure" in r["reason"]

    def test_not_meaningful_negative_equity_is_absent_with_the_test_named(self):
        end, start = "2023-12-31", "2023-01-01"
        f = filing("S-3", "10-K", "2024-02-20", end,
                   balance_face(end, extra=[
                       inst("us-gaap:LongTermDebtNoncurrent", end, 100),
                       inst("us-gaap:StockholdersEquity", end, -40),
                   ]))
        r = compute_all([f], None, ["SYN"], industry=no_filer(),
                        entry_ids=["debt_to_equity"])["debt_to_equity"]
        assert r["status"] == "absent"
        assert "Not meaningful" in r["reason"]

    def test_one_broken_entry_cannot_hide_the_others(self, monkeypatch):
        from engine import compute as compute_mod
        def boom(ctx):
            raise RuntimeError("kaput")
        monkeypatch.setitem(compute_mod.REGISTRY, "current_ratio", boom)
        res = compute_all(_synthetic_company(), None, ["SYN"],
                          industry=no_filer(),
                          entry_ids=["current_ratio", "fcf_ttm"])
        assert res["current_ratio"]["status"] == "absent"
        assert "kaput" in res["current_ratio"]["reason"]
        assert res["fcf_ttm"]["status"] == "computed"


class TestManualOverFetched:
    def test_hand_entered_wins_and_both_sides_survive(self):
        computed = {"fcf_ttm": {"status": "computed", "value": 150.0},
                    "current_ratio": {"status": "computed", "value": 1.4}}
        security = entered({}, "2026-03-04", fcf_ttm=149.0)
        before = len(security["hand_entered"])
        values = dataview.merged_values(security, computed)
        assert values["fcf_ttm"]["value"] == 149.0
        assert values["fcf_ttm"]["source"] == "manual"
        assert values["current_ratio"]["value"] == 1.4
        assert values["current_ratio"]["source"] == "computed"
        # nothing was written into the security by the merge
        assert len(security["hand_entered"]) == before

    def test_absent_computed_never_contributes_a_value(self):
        computed = {"pe_ttm": {"status": "absent", "reason": "no prices"}}
        values = dataview.merged_values({}, computed)
        assert "pe_ttm" not in values

    def test_the_merge_carries_the_caution_with_the_value(self):
        """The merge is the last place a computed figure is a rich object
        before it is frozen into a snapshot for good. A merge that kept the
        number and dropped what qualified it would put a figure into an
        append-only record stating it as more certain than it was."""
        computed = {"market_cap": {"status": "computed", "value": 2.4e12,
                                   "cautions": ["Class B has no stored close"],
                                   "provenance": ["shares from the cover"]}}
        v = dataview.merged_values({}, computed)["market_cap"]
        assert v["cautions"] == ["Class B has no stored close"]
        assert v["provenance"] == ["shares from the cover"]

    def test_a_hand_entered_value_names_the_day_it_was_entered(self):
        """A record rebuilt for a past day must never claim a number typed
        today was known then. It says which day instead, and a pin before
        that day does not see it at all."""
        s = entered({}, "2024-03-01", fcf_ttm=149.0)
        after = dataview.merged_values(s, {}, as_of="2024-06-30")["fcf_ttm"]
        assert after["value"] == 149.0
        assert after["provenance"] == ["entered by hand on 2024-03-01"]
        assert after["cautions"] == []
        assert "fcf_ttm" not in dataview.merged_values(s, {},
                                                       as_of="2024-01-01")

    def test_the_two_overlays_cannot_disagree_about_the_same_figure(self):
        """The strategy's context and the snapshot merge read the same
        record through the same module.

        They were separate implementations and had already come apart: this
        one supplied a provenance sentence the context did not. A figure that
        reads one way to a strategy and another way in the record frozen
        beside it is two halves of the program disagreeing about a number
        nobody can go back and check.
        """
        s = {"ticker": "SYN", "name": "Synthetic Co", "lots": []}
        entered(s, "2026-03-04", fcf_ttm=149.0)
        merged = dataview.merged_values(s, {})["fcf_ttm"]
        served = context.build_context(
            s, [], values={}, inputs={},
        )["measures"]["fcf_ttm"]["current"]
        for key in ("value", "source", "cautions", "provenance"):
            assert merged[key] == served[key], key


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
