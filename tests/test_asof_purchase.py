"""Purchase-time evaluation belongs to the purchase date.

What would fail silently here, and did before this existed: a purchase
recorded against a past date quietly judged with today's data, then written
into the journal as if that verdict had been seen on the purchase date. The
tests pin the as-of cutoffs (filings by filed date, price by that day's
close), the honest absence when the data of that day is not there, and the
record's basis field — a reconstruction must never be able to masquerade as
a live evaluation.
"""

from datetime import date, timedelta

from conftest import filing, inst, balance_face

from engine import dataview, facts_store, portfolio, price_store, profiles

import app as app_mod


def _fy_filing(cik_unused, accession, filed, end, ca, cl):
    """A 10-K whose balance sheet gives current_ratio = ca / cl."""
    facts = balance_face(end, extra=[
        inst("us-gaap:AssetsCurrent", end, ca),
        inst("us-gaap:LiabilitiesCurrent", end, cl),
    ])
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
            _fy_filing(cik, "A-1", "2025-02-20", "2024-12-31", 200, 100),
            _fy_filing(cik, "A-2", "2026-02-20", "2025-12-31", 300, 300),
        ])
        live = dataview.computed_results(cik, ["SYN"], ["current_ratio"])
        asof = dataview.asof_results(cik, ["SYN"], ["current_ratio"],
                                     "2025-06-30")
        assert live["current_ratio"]["value"] == 1.0
        assert asof["current_ratio"]["value"] == 2.0

    def test_date_before_any_filing_is_absent_not_approximated(self):
        cik = next(_CIK)
        _store_company(cik, [
            _fy_filing(cik, "A-1", "2025-02-20", "2024-12-31", 200, 100),
        ])
        r = dataview.asof_results(cik, ["SYN"], ["current_ratio"],
                                  "2024-06-30")["current_ratio"]
        assert r["status"] == "absent"

    def test_reconstruction_never_mutates_the_stores(self):
        cik = next(_CIK)
        _store_company(cik, [
            _fy_filing(cik, "A-1", "2025-02-20", "2024-12-31", 200, 100),
        ], [["2025-06-27", 10.0, 1000]])
        before = {p.name: p.read_bytes()
                  for p in facts_store.cik_dir(cik).glob("*.json")}
        before[price_store.path_for(cik).name] = \
            price_store.path_for(cik).read_bytes()
        dataview.asof_results(cik, ["SYN"], ["current_ratio"], "2025-06-30")
        dataview.price_view_asof(cik, ["SYN"], "2025-06-30")
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
        p = dataview.price_view_asof(cik, ["SYN"], "2025-06-30")
        assert p["value"] == 10.0
        assert p["date"] == "2025-06-27"
        assert p["source"] == "fetched"

    def test_gap_beyond_the_stale_window_is_absent_with_reason(self):
        cik = next(_CIK)
        _store_company(cik, [], [["2025-06-27", 10.0, 1000]])
        p = dataview.price_view_asof(cik, ["SYN"], "2025-07-20")
        assert p["value"] is None
        assert "2025-07-20" in p["reason"]

    def test_never_reaches_forward_to_a_later_close(self):
        cik = next(_CIK)
        _store_company(cik, [], [["2025-06-27", 10.0, 1000]])
        p = dataview.price_view_asof(cik, ["SYN"], "2025-06-26")
        assert p["value"] is None

    def test_a_no_trade_zero_row_cannot_mask_the_prior_real_close(self):
        """A halt or bad row stored as close 0 is an artifact, not a price;
        the as-of read steps over it to the real close the day before — a
        false 'no close is stored' here would freeze a false absence into
        the entry snapshot."""
        cik = next(_CIK)
        _store_company(cik, [], [["2025-06-27", 10.0, 1000],
                                 ["2025-06-30", 0, 0]])
        p = dataview.price_view_asof(cik, ["SYN"], "2025-06-30")
        assert p["value"] == 10.0
        assert p["date"] == "2025-06-27"


class TestAvailability:
    def test_counts_what_the_day_could_see(self):
        cik = next(_CIK)
        _store_company(cik, [
            _fy_filing(cik, "A-1", "2025-02-20", "2024-12-31", 200, 100),
            _fy_filing(cik, "A-2", "2026-02-20", "2025-12-31", 300, 300),
        ], [["2025-06-27", 10.0, 1000]])
        a = dataview.asof_availability(cik, ["SYN"], "2025-06-30")
        assert a["filings_by_then"] == 1
        assert a["filings_held"] == 2
        assert a["newest_filed"] == "2025-02-20"
        assert a["price"]["value"] == 10.0


class TestPortfolioEvaluationBasis:
    def _graham(self):
        return profiles.resolve_profile("graham.yaml")

    def test_snapshot_records_the_reconstruction_basis(self):
        s = portfolio.new_security("rec", "Recon Co")
        evaluation = {"basis": "reconstructed", "as_of": "2025-06-30",
                      "manual_undated": ["pe_3y_avg_eps"],
                      "note": "1 of 2 stored filings had been filed by "
                              "2025-06-30"}
        portfolio.open_position(s, self._graham(), 3, 10, 20.0, "2025-06-30",
                                override_reason="Backfilled.",
                                values={"current_ratio": 2.0},
                                evaluation=evaluation)
        snap = s["entry_snapshot"]
        assert snap["evaluation"]["basis"] == "reconstructed"
        assert snap["evaluation"]["as_of"] == "2025-06-30"
        # the frozen record is isolated from later caller mutation
        evaluation["manual_undated"].append("tampered")
        assert snap["evaluation"]["manual_undated"] == ["pe_3y_avg_eps"]
        # the verdict here is not "buy", so the override carries the basis
        ov = s["override"]
        assert ov["basis"] == "reconstructed"
        assert ov["as_of"] == "2025-06-30"
        assert "reconstructed for 2025-06-30" in s["notes"][-1]["text"]

    def test_without_an_evaluation_the_default_is_live_as_of_today(self):
        """The engine never asserts a past evaluation it was not told about:
        a caller that passes no basis gets the honest description of what
        actually happened — evaluated live, today."""
        s = portfolio.new_security("liv", "Live Co")
        portfolio.open_position(s, self._graham(), 3, 10, 20.0, "2025-01-05",
                                override_reason="x",
                                values={"current_ratio": 2.0})
        snap = s["entry_snapshot"]
        assert snap["evaluation"]["basis"] == "live"
        assert snap["evaluation"]["as_of"] == date.today().isoformat()


class TestApiPurchasePath:
    """The whole seam, through the same Api the UI calls."""

    def _seed(self, cik, metrics=None):
        api = app_mod.Api()
        s = portfolio.new_security("SYN", "Synthetic Co")
        s["cik"] = cik
        if metrics:
            s["metrics"] = dict(metrics)
        from engine import store
        doc = store.load("securities.json")
        doc["securities"] = [s]
        store.save("securities.json", doc)
        return api

    def _company(self, cik):
        _store_company(cik, [
            _fy_filing(cik, "A-1", "2025-02-20", "2024-12-31", 200, 100),
            _fy_filing(cik, "A-2", "2026-02-20", "2025-12-31", 300, 300),
        ], [["2025-06-27", 10.0, 1000], ["2026-08-01", 20.0, 1000]])

    def test_backdated_purchase_is_judged_by_the_data_of_its_date(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        r = api.open_position("SYN", 5, 9.5, "2025-06-30",
                              override_reason="backfilled",
                              profile_file="graham.yaml")
        assert r["ok"], r
        from engine import store
        s = store.load("securities.json")["securities"][0]
        snap = s["entry_snapshot"]
        assert snap["evaluation"]["basis"] == "reconstructed"
        assert snap["evaluation"]["as_of"] == "2025-06-30"
        # the frozen value is the one observable then, not today's
        assert snap["metrics"]["current_ratio"] == 2.0
        # priced at that day's close, not today's
        assert snap["price"] == 10.0
        assert snap["price_date"] == "2025-06-27"
        assert snap["price_source"] == "fetched"
        assert "filed by 2025-06-30" in snap["evaluation"]["note"]

    def test_todays_purchase_is_live_and_uses_current_data(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        r = api.open_position("SYN", 5, 9.5, date.today().isoformat(),
                              override_reason="now",
                              profile_file="graham.yaml")
        assert r["ok"], r
        from engine import store
        s = store.load("securities.json")["securities"][0]
        snap = s["entry_snapshot"]
        assert snap["evaluation"]["basis"] == "live"
        assert snap["metrics"]["current_ratio"] == 1.0

    def test_future_dated_purchase_is_refused(self):
        cik = next(_CIK)
        api = self._seed(cik)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = api.open_position("SYN", 5, 9.5, tomorrow,
                              profile_file="graham.yaml")
        assert r["ok"] is False
        assert "future" in r["error"]
        r = api.preview_purchase("SYN", "graham.yaml", tomorrow)
        assert r["ok"] is False

    def test_manual_values_participate_and_are_named_undated(self):
        """A hand-entered value is the user's standing assertion; excluding
        it would fabricate a grey verdict — and with it a 'bought without a
        signal' override — on securities the user maintains by hand. It
        enters, and the record says it is undated."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik, metrics={"pe_3y_avg_eps": 12.0})
        r = api.open_position("SYN", 5, 9.5, "2025-06-30",
                              override_reason="backfilled",
                              profile_file="graham.yaml")
        assert r["ok"], r
        from engine import store
        s = store.load("securities.json")["securities"][0]
        snap = s["entry_snapshot"]
        assert snap["metrics"]["pe_3y_avg_eps"] == 12.0
        assert snap["value_sources"]["pe_3y_avg_eps"] == "manual"
        assert "pe_3y_avg_eps" in snap["evaluation"]["manual_undated"]
        assert "hand-entered" in snap["evaluation"]["note"]

    def test_preview_reports_the_basis_it_evaluated_on(self):
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)
        past = api.preview_purchase("SYN", "graham.yaml", "2025-06-30")
        assert past["basis"] == "reconstructed"
        assert past["as_of"] == "2025-06-30"
        assert "filed by 2025-06-30" in past["note"]
        now = api.preview_purchase("SYN", "graham.yaml",
                                   date.today().isoformat())
        assert now["basis"] == "live"

    def test_a_broken_data_layer_never_blocks_recording_the_decision(self):
        """Principle 2: the tool records decisions, it never blocks them.
        The live path survives a broken data layer by degrading to absent
        values; the as-of path must do the same — a backdated purchase that
        errors out while a today-dated one records would pressure the user
        to falsify the date."""
        cik = next(_CIK)
        self._company(cik)
        api = self._seed(cik)

        import engine.dataview as dv
        real = dv.asof_results
        def boom(*a, **kw):
            raise RuntimeError("kaput store")
        dv.asof_results = boom
        try:
            r = api.open_position("SYN", 5, 9.5, "2025-06-30",
                                  override_reason="backfilled",
                                  profile_file="graham.yaml")
        finally:
            dv.asof_results = real
        assert r["ok"], r
        from engine import store
        s = store.load("securities.json")["securities"][0]
        snap = s["entry_snapshot"]
        assert snap["evaluation"]["basis"] == "reconstructed"
        assert "could not be read" in snap["evaluation"]["note"]
        assert "kaput store" in snap["evaluation"]["note"]
        # nothing computed entered: the verdict went grey, honestly
        assert snap["result"]["verdict"] == "cant_say"

    def test_scorecard_names_its_reconstructed_backfills(self):
        live = portfolio.new_security("liv", "Live Co")
        live["override"] = {"date": "2026-01-05", "basis": "live",
                            "failed": [], "missing": ["x"], "reason": "r"}
        live["position"] = {"shares": 1, "cost_basis": 10.0,
                            "opened": "2026-01-05"}
        live["price"] = 12.0
        rec = portfolio.new_security("rec", "Recon Co")
        rec["override"] = {"date": "2025-06-30", "basis": "reconstructed",
                           "failed": [], "missing": ["x"], "reason": "r"}
        rec["position"] = {"shares": 1, "cost_basis": 10.0,
                           "opened": "2025-06-30"}
        rec["price"] = 8.0
        card = portfolio.override_scorecard([live, rec])
        assert card["override"]["n"] == 2
        assert card["reconstructed_overrides"] == 1

    def test_no_company_linked_reconstruction_says_so(self):
        api = self._seed(None)
        from engine import store
        doc = store.load("securities.json")
        doc["securities"][0].pop("cik")
        store.save("securities.json", doc)
        r = api.preview_purchase("SYN", "graham.yaml", "2025-06-30")
        assert r["ok"], r
        assert r["basis"] == "reconstructed"
        assert "no company is linked" in r["note"]
