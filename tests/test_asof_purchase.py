"""Purchase-time evaluation belongs to the purchase date.

What would fail silently here, and did before this existed: a purchase
recorded against a past date quietly judged with today's data, then written
into the journal as if that state had been seen on the purchase date. The
tests pin the as-of cutoffs (filings by filed date, price by that day's
close), the honest absence when the data of that day is not there, and the
record's basis field — a reconstruction must never be able to masquerade as
something seen live.

The decisive fixture is the one where the two answers differ: a company whose
cash flow cleared the strategy's floor in 2025 and does not today. If the
as-of path ever silently used current data, the reconstruction would agree
with the live reading and every test here would still pass on a fixture where
they happen to match.
"""

from datetime import date, timedelta

import pytest
from conftest import balance_face, dur, filing, inst, journal_for

from engine import dataview, facts_store, journals, price_store

from app import Api


def _fy_filing(accession, filed, end, ca, cl, cfo=None, capex=None):
    """A 10-K whose balance sheet gives current_ratio = ca / cl, and whose
    cash-flow statement gives free cash flow = cfo − capex."""
    start = f"{int(end[:4])}-01-01"
    facts = balance_face(end, extra=[
        inst("us-gaap:AssetsCurrent", end, ca),
        inst("us-gaap:LiabilitiesCurrent", end, cl),
    ])
    if cfo is not None:
        facts.append(dur(
            "us-gaap:NetCashProvidedByUsedInOperatingActivities",
            start, end, cfo, stmt="CashFlow"))
        facts.append(dur(
            "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            start, end, capex, stmt="CashFlow"))
    return filing(accession, "10-K", filed, end, facts)


def _store_company(cik, filings, price_rows=(), ticker="SYN"):
    for f in filings:
        facts_store.save_filing(cik, f)
    doc = price_store.load(cik)
    if price_rows:
        price_store.merge_series(doc, ticker, "tiingo", list(price_rows), [])
    price_store.save(cik, doc)


# Distinct CIK per test: the dataview bundle cache is keyed by CIK and
# fingerprinted by file mtimes, which can collide across same-second tests.
_CIK = iter(range(701, 799))


class TestAsofResults:
    def test_past_date_sees_only_filings_filed_by_then(self):
        cik = next(_CIK)
        _store_company(cik, [
            _fy_filing("A-1", "2025-02-20", "2024-12-31", 200, 100),
            _fy_filing("A-2", "2026-02-20", "2025-12-31", 300, 300),
        ])
        live = dataview.computed_results(cik, ["SYN"], ["current_ratio"])
        asof = dataview.asof_results(cik, ["SYN"], ["current_ratio"],
                                     "2025-06-30")
        assert live["current_ratio"]["value"] == 1.0
        assert asof["current_ratio"]["value"] == 2.0

    def test_date_before_any_filing_is_absent_not_approximated(self):
        cik = next(_CIK)
        _store_company(cik, [
            _fy_filing("A-1", "2025-02-20", "2024-12-31", 200, 100),
        ])
        r = dataview.asof_results(cik, ["SYN"], ["current_ratio"],
                                  "2024-06-30")["current_ratio"]
        assert r["status"] == "absent"

    def test_reconstruction_never_mutates_the_stores(self):
        cik = next(_CIK)
        _store_company(cik, [
            _fy_filing("A-1", "2025-02-20", "2024-12-31", 200, 100),
        ], [["2025-06-27", 10.0, 1000]])
        before = {p.name: p.read_bytes()
                  for p in facts_store.cik_dir(cik).glob("*.json")}
        before[price_store.path_for(cik).name] = \
            price_store.path_for(cik).read_bytes()
        dataview.asof_results(cik, ["SYN"], ["current_ratio"], "2025-06-30")
        dataview.price_view_asof(cik, "SYN", "2025-06-30")
        after = {p.name: p.read_bytes()
                 for p in facts_store.cik_dir(cik).glob("*.json")}
        after[price_store.path_for(cik).name] = \
            price_store.path_for(cik).read_bytes()
        assert before == after


class TestAsofPrice:
    def test_close_on_the_day_or_nearest_earlier_within_the_window(self):
        cik = next(_CIK)
        _store_company(cik, [], [["2025-06-27", 10.0, 1000],
                                 ["2026-08-01", 20.0, 1000]])
        p = dataview.price_view_asof(cik, "SYN", "2025-06-30")
        assert p["value"] == 10.0
        assert p["date"] == "2025-06-27"
        assert p["source"] == "fetched"

    def test_gap_beyond_the_stale_window_is_absent_with_reason(self):
        cik = next(_CIK)
        _store_company(cik, [], [["2025-06-27", 10.0, 1000]])
        p = dataview.price_view_asof(cik, "SYN", "2025-07-20")
        assert p["value"] is None
        assert "2025-07-20" in p["reason"]

    def test_never_reaches_forward_to_a_later_close(self):
        cik = next(_CIK)
        _store_company(cik, [], [["2025-06-27", 10.0, 1000]])
        p = dataview.price_view_asof(cik, "SYN", "2025-06-26")
        assert p["value"] is None

    def test_a_no_trade_zero_row_cannot_mask_the_prior_real_close(self):
        """A halt or bad row stored as close 0 is an artifact, not a price;
        the as-of read steps over it to the real close the day before — a
        false 'no close is stored' here would freeze a false absence into
        the entry snapshot."""
        cik = next(_CIK)
        _store_company(cik, [], [["2025-06-27", 10.0, 1000],
                                 ["2025-06-30", 0, 0]])
        p = dataview.price_view_asof(cik, "SYN", "2025-06-30")
        assert p["value"] == 10.0
        assert p["date"] == "2025-06-27"


class TestAvailability:
    def test_counts_what_the_day_could_see(self):
        cik = next(_CIK)
        _store_company(cik, [
            _fy_filing("A-1", "2025-02-20", "2024-12-31", 200, 100),
            _fy_filing("A-2", "2026-02-20", "2025-12-31", 300, 300),
        ], [["2025-06-27", 10.0, 1000]])
        a = dataview.asof_availability(cik, ["SYN"], "SYN", "2025-06-30")
        assert a["filings_by_then"] == 1
        assert a["filings_held"] == 2
        assert a["newest_filed"] == "2025-02-20"
        assert a["price"]["value"] == 10.0


class TestApiPurchasePath:
    """The whole seam, through the same Api the UI calls."""

    @pytest.fixture(autouse=True)
    def _journal(self, strategies):
        strategies("verdicts")
        journal_for("verdicts", "Backfill")

    def _seed(self, cik, metrics=None):
        api = Api()
        assert api.add_security("SYN", "Synthetic Co")["ok"]
        journal = journals.load(journals.resolve_open())
        s = journal["securities"][0]
        if cik is not None:
            s["cik"] = cik
        if metrics:
            s["metrics"] = dict(metrics)
        journals.save(journal)
        return api

    def _company(self, cik):
        """Cash flow clears the strategy's floor in 2024 and does not in
        2025, so the reconstruction and the live reading genuinely differ."""
        _store_company(cik, [
            _fy_filing("A-1", "2025-02-20", "2024-12-31", 200, 100,
                       cfo=5_000_000, capex=1_000_000),
            _fy_filing("A-2", "2026-02-20", "2025-12-31", 300, 300,
                       cfo=1_200_000, capex=1_000_000),
        ], [["2025-06-27", 10.0, 1000], ["2026-08-01", 20.0, 1000]])

    def _snapshot(self):
        """The snapshot frozen with the newest recorded lot. A purchase is a
        lot now, and each one freezes the decision that was on screen for
        it — so "the entry snapshot" is the one belonging to that entry."""
        journal = journals.load(journals.resolve_open())
        return journal["securities"][0]["lots"][-1]["snapshot"]

    def test_backdated_purchase_is_judged_by_the_data_of_its_date(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        r = api.open_position("SYN", 5, 9.5, "2025-06-30",
                              override_reason="backfilled")
        assert r["ok"], r
        snap = self._snapshot()
        assert snap["evaluation"]["basis"] == "reconstructed"
        assert snap["evaluation"]["as_of"] == "2025-06-30"
        # the frozen value is the one observable then, not today's
        assert snap["metrics"]["current_ratio"]["value"] == 2.0
        # priced at that day's close, not today's
        assert snap["price"] == 10.0
        assert snap["price_date"] == "2025-06-27"
        assert snap["price_source"] == "fetched"
        assert "filed by 2025-06-30" in snap["evaluation"]["note"]

    def test_the_state_itself_is_the_one_that_day_would_have_produced(self):
        """The decisive case: if the as-of path silently used current data,
        every other test here would still pass on a fixture where the two
        happen to agree."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        past = api.preview_purchase("SYN", "2025-06-30")
        now = api.preview_purchase("SYN", date.today().isoformat())
        assert past["decision"]["state"]["id"] == "say-yes"
        assert past["decision"]["render"] == "commit"
        assert now["decision"]["state"]["id"] == "say-no"
        assert now["decision"]["render"] == "hold"

    def test_todays_purchase_is_live_and_uses_current_data(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        r = api.open_position("SYN", 5, 9.5, date.today().isoformat(),
                              override_reason="now")
        assert r["ok"], r
        snap = self._snapshot()
        assert snap["evaluation"]["basis"] == "live"
        assert snap["metrics"]["current_ratio"]["value"] == 1.0
        assert snap["decision"]["state"]["id"] == "say-no"

    def test_a_reconstruction_can_never_be_labelled_live(self):
        """The basis is derived from whether a pin was used, not asserted by
        the caller, so it cannot drift from what actually happened."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        past = api.preview_purchase("SYN", "2025-06-30")
        now = api.preview_purchase("SYN", date.today().isoformat())
        assert (past["basis"], past["as_of"]) == ("reconstructed",
                                                  "2025-06-30")
        assert now["basis"] == "live"
        assert now["as_of"] == date.today().isoformat()

    def test_preview_and_the_committed_record_agree(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        p = api.preview_purchase("SYN", "2025-06-30")
        api.open_position("SYN", 5, 9.5, "2025-06-30",
                          override_reason="backfilled",
                          previewed_state=p["decision"]["state"]["id"])
        snap = self._snapshot()
        assert snap["decision"]["state"]["id"] == \
            p["decision"]["state"]["id"]
        assert snap["evaluation"]["basis"] == p["basis"]
        assert snap["evaluation"]["as_of"] == p["as_of"]

    def test_future_dated_purchase_is_refused(self):
        cik = next(_CIK)
        api = self._seed(cik)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = api.open_position("SYN", 5, 9.5, tomorrow)
        assert r["ok"] is False
        assert "future" in r["error"]
        assert api.preview_purchase("SYN", tomorrow)["ok"] is False

    def test_future_dated_sale_is_refused_the_same_way(self):
        """The asymmetry that put this on the board: the purchase screen
        refused tomorrow and the sale screen took 2062, which closed the
        position for every reader and removed its whole value from the
        account while the strategy was still holding it."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        assert api.open_position("SYN", 5, 9.5, "2025-06-30", "in")["ok"]
        ahead = (date.today() + timedelta(days=13_000)).isoformat()
        r = api.sell_shares("SYN", "Panic", 12.0, ahead)
        assert r["ok"] is False
        assert "future" in r["error"] and "sale" in r["error"]
        # and the holding is exactly as it was
        state = api.get_state()
        held = state["securities"][0]
        assert held["_shares"] == 5
        assert held["bucket"] == "holdings"

    def test_a_sale_dated_today_still_records(self):
        """The refusal is of days that have not happened, not of same-day
        entry — which is how most sales are recorded."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        assert api.open_position("SYN", 5, 9.5, "2025-06-30", "in")["ok"]
        r = api.sell_shares("SYN", "Hit valuation", 12.0,
                            date.today().isoformat())
        assert r["ok"], r
        assert r["remaining"] == 0

    def test_manual_values_participate_and_are_named_undated(self):
        """A hand-entered value is the user's standing assertion; excluding
        it would fabricate an unevaluable state — and with it a 'bought
        without a signal' override — on securities the user maintains by
        hand. It enters, and the record says it is undated.

        Said on the value itself, not only in the evaluation's prose note.
        The note is a summary of the reconstruction; a reader two years from
        now looking at one figure needs the qualification beside that figure,
        because the number is what they are reading.
        """
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik, metrics={"pe_3y_avg_eps": 12.0})
        r = api.open_position("SYN", 5, 9.5, "2025-06-30",
                              override_reason="backfilled")
        assert r["ok"], r
        snap = self._snapshot()
        frozen = snap["metrics"]["pe_3y_avg_eps"]
        assert frozen["value"] == 12.0
        assert frozen["source"] == "manual"
        assert any("carry no date" in c and "2025-06-30" in c
                   for c in frozen["cautions"])
        assert "pe_3y_avg_eps" in snap["evaluation"]["manual_undated"]
        assert "hand-entered" in snap["evaluation"]["note"]

    def test_a_live_purchase_leaves_a_hand_entered_value_unqualified(self):
        """The undated caution is about a pin, not about hand entry. A live
        record that carried it would be warning of a mismatch that does not
        exist, and a caution that fires when nothing is wrong is how the
        rest stop being read."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik, metrics={"pe_3y_avg_eps": 12.0})
        assert api.open_position("SYN", 5, 9.5, date.today().isoformat(),
                                 override_reason="now")["ok"]
        assert self._snapshot()["metrics"]["pe_3y_avg_eps"]["cautions"] == []

    def test_a_broken_data_layer_never_blocks_recording_the_decision(self):
        """Principle 2: the tool records decisions, it never blocks them. A
        backdated purchase that errors out while a today-dated one records
        would pressure the user to falsify the date."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)

        def boom(*a, **kw):
            raise RuntimeError("kaput store")

        real = dataview.asof_results
        dataview.asof_results = boom
        try:
            r = api.open_position("SYN", 5, 9.5, "2025-06-30",
                                  override_reason="backfilled")
        finally:
            dataview.asof_results = real
        assert r["ok"], r
        snap = self._snapshot()
        assert snap["evaluation"]["basis"] == "reconstructed"
        assert "could not be read" in snap["evaluation"]["note"]
        assert "kaput store" in snap["evaluation"]["note"]

    def test_a_broken_context_never_blocks_recording_either(self):
        """The same principle one layer further in. contract.evaluate never
        raises, but building what it is handed can — and that runs first."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)

        from engine import context

        def boom(*a, **kw):
            raise RuntimeError("kaput context")

        real = context.build_context
        context.build_context = boom
        try:
            r = api.open_position("SYN", 5, 9.5, date.today().isoformat(),
                                  override_reason="recording anyway")
        finally:
            context.build_context = real
        assert r["ok"], r
        snap = self._snapshot()
        d = snap["decision"]
        assert d["state"]["id"] == "host:data-unreadable"
        assert d["produced_by"] == "host"
        assert "kaput context" in d["reason"]["summary"]
        # and it is an override, because there was no verdict to go against
        journal = journals.load(journals.resolve_open())
        assert journal["securities"][0]["lots"][-1]["override"]["kind"] \
            == "without"

    def test_no_company_linked_reconstruction_says_so(self):
        api = self._seed(None)
        r = api.preview_purchase("SYN", "2025-06-30")
        assert r["ok"], r
        assert r["basis"] == "reconstructed"
        assert "no company is linked" in r["note"]
