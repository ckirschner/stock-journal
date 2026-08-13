"""Expected-value prefill: computed values are computed, never typed.

The dialog predated the data pipeline and asked the user to type price, free
cash flow and shares outstanding — all three derivable. These tests pin the
derivations (with provenance and as-of dates), the unit conversion into the
millions the dialog speaks, the manual-wins merge, and honest absence when
nothing has been fetched. A typo in a typed field becoming a stored
assumption is the failure this whole surface exists to remove.
"""

import pytest
from conftest import (balance_face, dur, entered, filing, inst, symbols,
                      journal_for, no_filer)

from engine import bank, facts_store, journals, price_store
from engine.compute import Ctx, shares_outstanding_result, ttm_flow_result

import app as app_mod

_CIK = iter(range(801, 899))

# The day a hand-entered figure went on record, well before the prices and
# filings below, so the prefill quoting it has to have read the entry's own
# date rather than any other date lying around.
_ENTERED_ON = "2026-03-04"


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
        r = shares_outstanding_result(
            Ctx([_one_filing()], None, symbols("SYN"), industry=no_filer()))
        assert r["status"] == "computed"
        assert r["value"] == 1.0e9
        # the date the cover fact itself states, not the later filing date
        assert r["asof"] == "2024-01-25"
        assert any("E-1" in p for p in r["provenance"])

    def test_no_cover_fact_is_absent_with_the_reason(self):
        f = filing("E-2", "10-K", "2024-02-20", "2023-12-31",
                   balance_face("2023-12-31", assets=800e6))
        r = shares_outstanding_result(
            Ctx([f], None, symbols("SYN"), industry=no_filer()))
        assert r["status"] == "absent"
        assert "cover" in r["reason"]

    def test_ttm_flow_carries_value_and_provenance(self):
        ctx = Ctx([_one_filing()], None, symbols("SYN"), industry=no_filer())
        r = ttm_flow_result(ctx, "net_income")
        assert r["status"] == "computed"
        assert r["value"] == 120e6
        assert any("E-1" in p for p in r["provenance"])
        assert r["asof"] == "2023-12-31"

    def test_ttm_flow_without_an_annual_report_is_absent(self):
        r = ttm_flow_result(Ctx([], None, symbols("SYN"), industry=no_filer()),
                            "net_income")
        assert r["status"] == "absent"


@pytest.fixture
def journal(strategies):
    strategies("verdicts")
    return journal_for("verdicts", "Valuations")[0]


def _open_journal():
    return journals.load(journals.resolve_open())


def _seed_security(cik=None, price=None):
    """A journal holding one security, through the same Api the UI calls."""
    api = app_mod.Api()
    assert api.add_security("SYN", "Synthetic Co")["ok"]
    doc = _open_journal()
    s = doc["securities"][0]
    if cik:
        s["cik"] = cik
    if price is not None:
        s["price"] = price
    journals.save(doc)
    return api


def _hand_enter(**values):
    """Put figures on the seeded security's dated record, through the same
    write the values dialog uses.

    Nothing may hand a date to that write — an entry that could name its own
    day could be written into the past — so a test that needs a figure to
    have been on record on a particular day moves the host's clock around
    this call rather than setting a field on the entry.
    """
    doc = _open_journal()
    entered(doc["securities"][0], **values)
    journals.save(doc)


class TestEvPrefillApi:
    @pytest.fixture(autouse=True)
    def _journal(self, journal):
        return journal

    def _seed(self, cik, price=None):
        return _seed_security(cik, price)

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

    def test_hand_entered_fcf_wins_dated_and_names_what_it_overrides(
            self, written_on):
        """A figure the user read off the page themselves beats the one this
        program computed, and the dialog says both which day it was entered
        and which computed figure it is standing in front of.

        The date is the half of that sentence which could not be said
        before. A hand-entered value was a slot with no date on it, so the
        most the dialog could do was admit it had no idea when the number
        was typed; now the record knows, and a prefill read back months
        later distinguishes a figure taken off the last annual report from
        one typed this morning to make a valuation come out.

        Naming the computed figure is the other half, and it is what keeps
        the override legible as an override. A prefill that quietly showed
        149 with no mention of the 150 underneath would read as the only
        answer anyone could have got, and the user would have no way to
        notice their own number had drifted from the filings.
        """
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        with written_on(_ENTERED_ON):
            _hand_enter(fcf_ttm=149e6)
        pf = api.ev_prefill("SYN")["prefill"]
        assert pf["fcf_ttm"]["value"] == 149.0
        assert pf["fcf_ttm"]["source"] == "manual"
        assert pf["fcf_ttm"]["asof"] == _ENTERED_ON
        assert pf["fcf_ttm"]["provenance"][0] == (
            f"entered by hand on {_ENTERED_ON}")
        assert any("overrides the computed $150.0M" in p
                   for p in pf["fcf_ttm"]["provenance"])
        # Nothing qualifies it any more. The old warning that a hand-entered
        # value carried no date was true of the storage, not of the number,
        # and it has been answered by dating the entry rather than by being
        # dropped — a caution left standing after its cause is fixed is how
        # a reader learns to skip the ones that matter.
        assert pf["fcf_ttm"]["cautions"] == []

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
        second = journals.create("Other", record, bank.definitions())
        journals.set_open(second["id"])
        app_mod.Api().save_valuation_defaults(14.0, 3.0, 40.0)
        assert journals.load(first)["settings"]["discount_rate"] == 10.0
        assert journals.load(second["id"])["settings"]["discount_rate"] == 14.0


class TestValuationClaims:
    @pytest.fixture(autouse=True)
    def _journal(self, journal):
        return journal

    _INPUTS = {"price": 100, "fcf_ttm": 150, "shares": 1000,
               "discount_rate": 9, "terminal_growth": 2.5}

    def _claims(self):
        return _open_journal()["securities"][0]["valuations"]

    def test_a_claim_stores_sources_for_the_inputs_the_method_declares(self):
        """Where each assumption came from is kept, for the assumptions this
        method actually has and for nothing else.

        A key the method never declared is a leftover from some other
        method's dialog, and a source that is not a dict describing a source
        is not one. Either stored beside the claim would put a provenance
        line next to an input that never carried it, which is worse than
        having no provenance at all: the reader would be told where a number
        came from and be told wrong.
        """
        api = _seed_security()
        sources = {"price": {"used": "fetched", "asof": "2026-08-01"},
                   "junk_key": {"used": "fetched"},
                   "fcf_ttm": "not-a-dict"}
        r = api.record_valuation("SYN", "reverse_dcf", dict(self._INPUTS),
                                 sources)
        assert r["ok"], r
        assert r["recorded"] is True
        claims = self._claims()
        assert len(claims) == 1
        assert claims[0]["sources"] == {"price": {"used": "fetched",
                                                  "asof": "2026-08-01"}}
        # recompute still works from the stored record
        assert api.recompute_ev("SYN")["ok"]

    def test_a_second_claim_appends_and_the_first_stays_readable(self):
        """Valuing the business again adds a claim; it never replaces the
        one before it.

        A valuation is the case for a specific purchase, argued against a
        price and a filing that both move. Overwriting the previous one
        would delete the case you actually bought on and leave a single
        number reading as though you had always thought this — and it would
        take the claims that talked you out of buying with it, which are the
        ones worth reading back. So both are on the record, oldest first,
        and each still carries the assumptions it was made from.
        """
        api = _seed_security()
        assert api.record_valuation("SYN", "reverse_dcf",
                                    dict(self._INPUTS))["recorded"] is True
        revised = {**self._INPUTS, "fcf_ttm": 120}
        assert api.record_valuation("SYN", "reverse_dcf",
                                    revised)["recorded"] is True
        claims = self._claims()
        assert [c["inputs"]["fcf_ttm"] for c in claims] == [150, 120]
        # the newest is the one standing, and it is the one recompute solves
        assert claims[-1]["inputs"] == revised
        assert api.recompute_ev("SYN")["ok"]

    def test_re_running_the_same_assumptions_records_nothing(self):
        """Identical assumptions are not a new claim about anything.

        The dialog posts everything it holds every time it is saved, so an
        unconditional append would turn opening the valuation screen and
        pressing save into a revision. A history padded with entries nobody
        made is a history nobody reads, and the whole value of keeping every
        claim is that the one where the argument changed can be found.
        """
        api = _seed_security()
        assert api.record_valuation("SYN", "reverse_dcf",
                                    dict(self._INPUTS))["recorded"] is True
        again = api.record_valuation("SYN", "reverse_dcf", dict(self._INPUTS))
        assert again["ok"], again
        assert again["recorded"] is False
        # the answer still comes back, because the dialog has to paint
        assert again["result"] is not None
        assert len(self._claims()) == 1
