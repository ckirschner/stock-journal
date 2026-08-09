"""Expected-value prefill: computed values are computed, never typed.

The dialog predated the data pipeline and asked the user to type price, free
cash flow and shares outstanding — all three derivable. These tests pin the
derivations (with provenance and as-of dates), the unit conversion into the
millions the dialog speaks, the manual-wins merge, and honest absence when
nothing has been fetched. A typo in a typed field becoming a stored
assumption is the failure this whole surface exists to remove.
"""

import pytest
from conftest import balance_face, dur, filing, inst, journal_for

from engine import facts_store, journals, price_store
from engine.compute import Ctx, shares_outstanding_result, ttm_flow_result

import app as app_mod

_CIK = iter(range(801, 899))


def _company_facts(end="2023-12-31", start="2023-01-01"):
    return [
        dur("us-gaap:Revenues", start, end, 1000e6),
        dur("us-gaap:NetCashProvidedByUsedInOperatingActivities", start, end,
            200e6, stmt="CashFlowStatement"),
        dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", start, end,
            50e6, stmt="CashFlowStatement"),
        dur("us-gaap:NetIncomeLoss", start, end, 120e6),
        dur("us-gaap:DepreciationDepletionAndAmortization", start, end,
            30e6, stmt="CashFlowStatement"),
        {**inst("dei:EntityCommonStockSharesOutstanding", "2024-01-25",
                1.0e9, stmt=None), "unit": "shares", "currency": None},
    ] + balance_face(end, assets=800e6)


def _one_filing():
    return filing("E-1", "10-K", "2024-02-20", "2023-12-31", _company_facts())


class TestComputeHelpers:
    def test_shares_outstanding_from_the_cover_with_its_stated_date(self):
        r = shares_outstanding_result(Ctx([_one_filing()], None, ["SYN"]))
        assert r["status"] == "computed"
        assert r["value"] == 1.0e9
        # the date the cover fact itself states, not the later filing date
        assert r["asof"] == "2024-01-25"
        assert any("E-1" in p for p in r["provenance"])

    def test_no_cover_fact_is_absent_with_the_reason(self):
        f = filing("E-2", "10-K", "2024-02-20", "2023-12-31",
                   balance_face("2023-12-31", assets=800e6))
        r = shares_outstanding_result(Ctx([f], None, ["SYN"]))
        assert r["status"] == "absent"
        assert "cover" in r["reason"]

    def test_ttm_flow_carries_value_and_provenance(self):
        ctx = Ctx([_one_filing()], None, ["SYN"])
        r = ttm_flow_result(ctx, "net_income")
        assert r["status"] == "computed"
        assert r["value"] == 120e6
        assert any("E-1" in p for p in r["provenance"])
        assert r["asof"] == "2023-12-31"

    def test_ttm_flow_without_an_annual_report_is_absent(self):
        r = ttm_flow_result(Ctx([], None, ["SYN"]), "net_income")
        assert r["status"] == "absent"


@pytest.fixture
def journal(strategies):
    strategies("verdicts")
    return journal_for("verdicts", "Valuations")[0]


def _open_journal():
    return journals.load(journals.resolve_open())


def _seed_security(cik=None, metrics=None, price=None):
    """A journal holding one security, through the same Api the UI calls."""
    api = app_mod.Api()
    assert api.add_security("SYN", "Synthetic Co")["ok"]
    doc = _open_journal()
    s = doc["securities"][0]
    if cik:
        s["cik"] = cik
    if metrics:
        s["metrics"] = dict(metrics)
    if price is not None:
        s["price"] = price
    journals.save(doc)
    return api


class TestEvPrefillApi:
    @pytest.fixture(autouse=True)
    def _journal(self, journal):
        return journal

    def _seed(self, cik, metrics=None, price=None):
        return _seed_security(cik, metrics, price)

    def _company(self, cik):
        facts_store.save_filing(cik, _one_filing())
        doc = price_store.load(cik)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2026-08-01", 20.0, 1000]], [])
        price_store.save(cik, doc)

    def test_prefills_come_computed_in_millions_with_provenance(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        r = api.ev_prefill("SYN")
        assert r["ok"], r
        pf = r["prefill"]
        assert pf["price"]["value"] == 20.0
        assert pf["price"]["source"] == "fetched"
        assert pf["price"]["asof"] == "2026-08-01"
        assert "close on 2026-08-01" in pf["price"]["provenance"][0]
        assert pf["fcf_ttm"]["value"] == 150.0          # (200 − 50)M
        assert pf["fcf_ttm"]["source"] == "computed"
        assert any("E-1" in p for p in pf["fcf_ttm"]["provenance"])
        assert pf["shares"]["value"] == 1000.0          # 1.0e9 → millions
        refs = r["references"]
        assert refs["net_income_ttm"]["value"] == 120.0
        assert refs["dda_ttm"]["value"] == 30.0
        assert refs["capex_ttm"]["value"] == 50.0

    def test_hand_entered_fcf_wins_and_names_what_it_overrides(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik, metrics={"fcf_ttm": 149e6})
        pf = api.ev_prefill("SYN")["prefill"]
        assert pf["fcf_ttm"]["value"] == 149.0
        assert pf["fcf_ttm"]["source"] == "manual"
        assert any("overrides the computed" in p
                   for p in pf["fcf_ttm"]["provenance"])

    def test_hand_entered_price_wins_and_is_named_undated(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik, price=12.34)
        pf = api.ev_prefill("SYN")["prefill"]
        assert pf["price"]["value"] == 12.34
        assert pf["price"]["source"] == "manual"
        assert pf["price"]["asof"] is None

    def test_nothing_fetched_is_absent_with_an_actionable_reason(self):
        api = self._seed(None)
        r = api.ev_prefill("SYN")
        pf = r["prefill"]
        assert pf["price"]["status"] == "absent"
        assert pf["fcf_ttm"]["status"] == "absent"
        assert "fetch" in pf["fcf_ttm"]["reason"].lower()
        assert pf["shares"]["status"] == "absent"
        for item in r["references"].values():
            assert item["status"] == "absent"


class TestValuationDefaults:
    @pytest.fixture(autouse=True)
    def _journal(self, journal):
        return journal

    def test_saves_the_three_defaults(self):
        api = app_mod.Api()
        r = api.save_valuation_defaults(10.0, 2.0, 25.0)
        assert r["ok"], r
        settings = _open_journal()["settings"]
        assert settings["discount_rate"] == 10.0
        assert settings["terminal_growth"] == 2.0
        assert settings["margin_of_safety"] == 25.0

    def test_discount_must_exceed_terminal_growth(self):
        api = app_mod.Api()
        r = api.save_valuation_defaults(3.0, 3.0, 30.0)
        assert r["ok"] is False
        assert "exceed" in r["error"]

    def test_gibberish_is_refused(self):
        """Nothing half-written: the journal keeps the defaults it shipped
        with rather than a partly-applied set."""
        api = app_mod.Api()
        assert api.save_valuation_defaults(11.0, 2.0, 25.0)["ok"]
        assert api.save_valuation_defaults("nine", 2.5, 30.0)["ok"] is False
        settings = _open_journal()["settings"]
        assert settings["discount_rate"] == 11.0

    def test_two_journals_keep_their_own_assumptions(self, strategies):
        """A discount rate is a standing assumption of one journal, not of
        the machine."""
        from engine import strategy_loader
        first = journals.resolve_open()
        app_mod.Api().save_valuation_defaults(10.0, 2.0, 25.0)
        record = strategy_loader.discover()[0]["verdicts"]
        second = journals.create("Other", record)
        journals.set_open(second["id"])
        app_mod.Api().save_valuation_defaults(14.0, 3.0, 40.0)
        assert journals.load(first)["settings"]["discount_rate"] == 10.0
        assert journals.load(second["id"])["settings"]["discount_rate"] == 14.0


class TestEvSourcesRecord:
    @pytest.fixture(autouse=True)
    def _journal(self, journal):
        return journal

    def test_compute_ev_stores_sources_for_known_inputs_only(self):
        api = _seed_security()
        inputs = {"price": 100, "fcf_ttm": 150, "shares": 1000,
                  "discount_rate": 9, "terminal_growth": 2.5}
        sources = {"price": {"used": "fetched", "asof": "2026-08-01"},
                   "junk_key": {"used": "fetched"},
                   "fcf_ttm": "not-a-dict"}
        r = api.compute_ev("SYN", "reverse_dcf", inputs, sources)
        assert r["ok"], r
        stored = _open_journal()["securities"][0]["ev"]
        assert stored["sources"] == {"price": {"used": "fetched",
                                               "asof": "2026-08-01"}}
        # recompute still works from the stored record
        assert api.recompute_ev("SYN")["ok"]
