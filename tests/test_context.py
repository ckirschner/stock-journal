"""What a strategy receives: a complete shape whether or not data exists,
absence with reasons and never an invented value, series that obey the
clock, and a boundary the strategy cannot mutate anything through."""

from conftest import dur, filing, inst, balance_face

from engine import context, contract, facts_store, price_store, tickermap


def map_tickers(cik, *tickers):
    """Seed the cached SEC ticker→CIK snapshot, the way a fetch would."""
    doc = tickermap.load_cached()
    for t in tickers:
        doc.setdefault("map", {})[t] = {"cik": int(cik), "name": "Synthetic"}
    tickermap._save(doc)


def synthetic_filing(cik, accession, fy_end, fy_start, filed, cfo, capex,
                     shares=None):
    facts = [
        dur("us-gaap:Revenues", fy_start, fy_end, 1000),
        dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
            fy_start, fy_end, cfo, stmt="CashFlowStatement"),
        dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            fy_start, fy_end, capex, stmt="CashFlowStatement"),
        dur("us-gaap:NetIncomeLoss", fy_start, fy_end, 120),
    ] + balance_face(fy_end, assets=800)
    if shares is not None:
        facts.append({**inst("dei:EntityCommonStockSharesOutstanding",
                             filed, shares, stmt=None),
                      "unit": "shares", "currency": None})
    f = filing(accession, "10-K", filed, fy_end, facts)
    f["cik"] = cik
    facts_store.save_filing(cik, f)
    return f


def store_two_years(cik):
    synthetic_filing(cik, "S-1", "2023-12-31", "2023-01-01",
                     "2024-02-20", cfo=200, capex=50)     # fcf 150
    synthetic_filing(cik, "S-2", "2024-12-31", "2024-01-01",
                     "2025-02-20", cfo=300, capex=60)     # fcf 240


def security(cik=None, **over):
    s = {"ticker": "SYN", "name": "Synthetic Co", "bucket": "ideas",
         "metrics": {}, "position": None}
    if cik:
        s["cik"] = cik
    s.update(over)
    return s


def build(sec, journal=None, values=None, inputs=None, as_of=None):
    return context.build_context(sec, journal if journal is not None
                                 else [sec], values or {}, inputs or {},
                                 as_of=as_of)


class TestCompleteness:
    def test_every_bank_measure_is_present_even_with_no_data(self):
        ctx = build(security())
        assert "fcf_ttm" in ctx["measures"]
        assert "moat_durability" in ctx["measures"]
        for m in ctx["measures"].values():
            assert m["current"]["status"] in ("known", "absent")
            if m["current"]["status"] == "absent":
                assert m["current"]["reason"]  # never a bare unknown
            assert "points" in m["series"]

    def test_no_data_is_absent_with_a_reason_never_zero(self):
        ctx = build(security())
        cur = ctx["measures"]["fcf_ttm"]["current"]
        assert cur["status"] == "absent"
        assert "fetch" in cur["reason"]
        assert "value" not in cur

    def test_a_qualitative_measure_says_it_is_assessed_not_computed(self):
        ctx = build(security())
        m = ctx["measures"]["moat_durability"]
        assert m["current"]["status"] == "absent"
        assert "assessed by you" in m["current"]["reason"]
        assert m["series"]["points"] == []
        assert "assessed by you" in m["series"]["note"]

    def test_portfolio_absences_carry_reasons_never_zero(self):
        ctx = build(security())
        assert ctx["portfolio"]["cash"]["status"] == "absent"
        assert ctx["portfolio"]["account_value"]["status"] == "absent"
        assert "free cash" in ctx["portfolio"]["account_value"]["reason"]


class TestMeasuresAndSeries:
    def test_current_and_series_from_stored_filings(self):
        store_two_years(901)
        ctx = build(security(901))
        m = ctx["measures"]["fcf_ttm"]
        assert m["current"] == {"status": "known", "value": 240.0,
                                "source": "computed",
                                "cautions": m["current"]["cautions"],
                                "provenance": m["current"]["provenance"]}
        assert [(p["filed"], p["value"]) for p in m["series"]["points"]] \
            == [("2024-02-20", 150.0), ("2025-02-20", 240.0)]
        for p in m["series"]["points"]:
            assert p["reason"] is None

    def test_a_hand_entered_value_wins_and_says_so(self):
        store_two_years(902)
        ctx = build(security(902, metrics={"fcf_ttm": 149.0}))
        cur = ctx["measures"]["fcf_ttm"]["current"]
        assert cur["value"] == 149.0
        assert cur["source"] == "manual"

    def test_an_unreadable_series_point_carries_its_reason(self):
        """The first boundary has no prior year, so a measure needing two
        readings is honest about why that point is empty."""
        store_two_years(903)
        ctx = build(security(903))
        points = ctx["measures"]["revenue_change_yoy"]["series"]["points"]
        assert points[0]["value"] is None and points[0]["reason"]


class TestTheClock:
    def test_a_pin_hides_filings_from_the_future(self):
        store_two_years(904)
        ctx = build(security(904), as_of="2024-06-30")
        assert ctx["today"] == "2024-06-30"
        m = ctx["measures"]["fcf_ttm"]
        assert m["current"]["value"] == 150.0     # only S-1 was observable
        assert [p["filed"] for p in m["series"]["points"]] == ["2024-02-20"]

    def test_a_manual_price_never_reaches_into_the_past(self):
        ctx = build(security(price="123.45"), as_of="2024-06-30")
        latest = ctx["price"]["latest"]
        assert latest["status"] == "absent"
        assert "2024-06-30" in latest["reason"]

    def test_a_manual_measure_participates_but_is_labelled_undated(self):
        """A hand-entered value has no date. It is the only value the
        journal has, so it stands — but never as a number known then."""
        ctx = build(security(metrics={"fcf_ttm": 999.0}), as_of="2020-01-01")
        cur = ctx["measures"]["fcf_ttm"]["current"]
        assert cur["value"] == 999.0 and cur["source"] == "manual"
        assert any("no date" in c and "2020-01-01" in c
                   for c in cur["cautions"])

    def test_the_same_value_carries_no_undated_caution_live(self):
        ctx = build(security(metrics={"fcf_ttm": 999.0}))
        assert ctx["measures"]["fcf_ttm"]["current"]["cautions"] == []

    def test_series_points_are_priced_at_their_own_boundary(self):
        """A 2024 reading must use the 2024 close, not today's. Without the
        per-boundary price pin a 2024 P/E would compute with a 2026 price —
        a plausible wrong number, no crash, nothing to notice. Share count
        is held constant, so any change in market cap is the price."""
        synthetic_filing(910, "S-1", "2023-12-31", "2023-01-01",
                         "2024-02-20", cfo=200, capex=50, shares=100.0)
        synthetic_filing(910, "S-2", "2024-12-31", "2024-01-01",
                         "2025-02-20", cfo=300, capex=60, shares=100.0)
        doc = price_store.load(910)
        price_store.merge_series(doc, "SYN", "test", [
            ["2024-02-20", 10.0, 100],     # the first boundary's close
            ["2025-02-20", 90.0, 100]], [])  # the second's, nine times higher
        price_store.save(910, doc)
        points = build(security(910))["measures"]["market_cap"]["series"][
            "points"]
        assert [p["value"] for p in points] == [1000.0, 9000.0]

    def test_dividend_and_split_events_stop_at_the_clock(self):
        store_two_years(911)
        doc = price_store.load(911)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2024-06-28", 10.0, 100]],
                                 [["2024-01-15", "dividend", 0.5],
                                  ["2025-01-15", "dividend", 0.6]])
        price_store.save(911, doc)
        ctx = build(security(911), as_of="2024-06-30")
        assert ctx["price"]["events"] == [["2024-01-15", "dividend", 0.5]]

    def test_a_truncated_series_says_so(self):
        cik, extra = 912, 2
        for i in range(context.SERIES_BOUNDARY_CAP + extra):
            year = 2010 + i
            synthetic_filing(cik, f"S-{i}", f"{year}-12-31", f"{year}-01-01",
                             f"{year + 1}-02-20", cfo=200 + i, capex=50)
        series = build(security(cik))["measures"]["fcf_ttm"]["series"]
        assert len(series["points"]) == context.SERIES_BOUNDARY_CAP
        assert series["truncated"] is True
        # the cap keeps the NEWEST boundaries, never the oldest
        newest_year = 2010 + context.SERIES_BOUNDARY_CAP + extra
        assert series["points"][-1]["filed"] == f"{newest_year}-02-20"
        assert series["points"][0]["filed"] == f"{newest_year - 11}-02-20"

    def test_a_short_series_is_not_truncated(self):
        store_two_years(913)
        assert build(security(913))["measures"]["fcf_ttm"]["series"][
            "truncated"] is False

    def test_the_history_belongs_to_the_same_class_as_the_close(self):
        """Two share classes are two instruments. The served close and the
        close history must describe the same one, or a strategy measures a
        move that never happened."""
        store_two_years(909)
        map_tickers(909, "SYN", "SYN.B")
        doc = price_store.load(909)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2026-01-02", 10.0, 100]], [])
        price_store.merge_series(doc, "SYN.B", "test",
                                 [["2026-01-05", 55.0, 100]], [])
        price_store.save(909, doc)
        sec = security(909)
        ctx = context.build_context(sec, [sec], {}, {})
        latest = ctx["price"]["latest"]
        assert latest["ticker"] == "SYN.B"           # the newest close wins
        assert ctx["price"]["closes"] == [["2026-01-05", 55.0]]

    def test_every_mapped_share_class_is_read_not_just_the_journals(self):
        """The journal names one symbol; the SEC maps several to the CIK.
        Reading only the journal's would price the security off a class the
        journal is not showing."""
        store_two_years(914)
        map_tickers(914, "SYN", "SYN.B")
        assert context._tickers_of({"ticker": "SYN", "cik": 914}) \
            == ["SYN", "SYN.B"]
        assert context._tickers_of({"ticker": "SYN"}) == ["SYN"]

    def test_closes_stop_at_the_clock_and_skip_no_trade_artifacts(self):
        store_two_years(905)
        doc = price_store.load(905)
        price_store.merge_series(doc, "SYN", "test", [
            ["2024-06-27", 10.0, 100], ["2024-06-28", None, 0],
            ["2024-06-30", 11.0, 100], ["2024-07-01", 12.0, 100]], [])
        price_store.save(905, doc)
        ctx = build(security(905), as_of="2024-06-30")
        assert ctx["price"]["closes"] == [["2024-06-27", 10.0],
                                          ["2024-06-30", 11.0]]
        assert ctx["price"]["latest"]["value"] == 11.0


class TestPositionAndPortfolio:
    def test_a_holding_reports_lots_and_market_value(self):
        store_two_years(906)
        doc = price_store.load(906)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2025-03-01", 20.0, 100]], [])
        price_store.save(906, doc)
        sec = security(906, bucket="holdings",
                       position={"shares": 10, "cost_basis": 15.0,
                                 "opened": "2025-02-25"})
        ctx = build(sec)
        pos = ctx["position"]
        assert pos["held"] is True
        assert pos["lots"] == [{"date": "2025-02-25", "shares": 10.0,
                                "price": 15.0, "kind": "buy"}]
        assert pos["market_value"]["value"] == 200.0
        assert pos["weight"]["status"] == "absent"      # no account value yet
        assert ctx["portfolio"]["slots"]["occupied"] == 1
        assert ctx["portfolio"]["holdings"][0]["ticker"] == "SYN"

    def test_a_position_opened_after_the_pin_did_not_exist_yet(self):
        sec = security(bucket="holdings",
                       position={"shares": 10, "cost_basis": 15.0,
                                 "opened": "2025-02-25"})
        ctx = build(sec, as_of="2024-06-30")
        assert ctx["position"]["held"] is False
        assert ctx["position"]["lots"] == []
        # ...and the same context must not count it as occupying a slot.
        # One context, one story: a slot-bound strategy reconstructing a
        # past decision would otherwise see today's portfolio.
        assert ctx["portfolio"]["slots"]["occupied"] == 0
        assert ctx["portfolio"]["holdings"] == []

    def test_a_position_opened_before_the_pin_is_priced_at_the_pin(self):
        store_two_years(908)
        doc = price_store.load(908)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2024-06-28", 10.0, 100],
                                  ["2026-01-05", 99.0, 100]], [])
        price_store.save(908, doc)
        sec = security(908, bucket="holdings", price="500.00",
                       position={"shares": 10, "cost_basis": 8.0,
                                 "opened": "2024-01-10"})
        ctx = build(sec, as_of="2024-06-30")
        assert ctx["position"]["market_value"]["value"] == 100.0
        assert ctx["portfolio"]["holdings"][0]["market_value"]["value"] \
            == 100.0
        assert ctx["portfolio"]["slots"]["occupied"] == 1

    def test_the_portfolio_counts_only_what_the_clock_had(self):
        old = security(bucket="holdings", ticker="OLD",
                       position={"shares": 5, "cost_basis": 10.0,
                                 "opened": "2023-01-01"})
        new = security(bucket="holdings", ticker="NEW",
                       position={"shares": 5, "cost_basis": 10.0,
                                 "opened": "2025-06-01"})
        ctx = build(old, [old, new], as_of="2024-06-30")
        assert [h["ticker"] for h in ctx["portfolio"]["holdings"]] == ["OLD"]
        assert ctx["portfolio"]["slots"]["occupied"] == 1


class TestTheBoundary:
    def test_mutating_the_context_corrupts_nothing(self):
        store_two_years(907)
        sec = security(907)
        ctx = build(sec)
        ctx["measures"]["fcf_ttm"]["current"]["value"] = -1.0
        ctx["measures"]["fcf_ttm"]["series"]["points"].clear()
        ctx["portfolio"]["holdings"].clear()
        again = build(sec)
        assert again["measures"]["fcf_ttm"]["current"]["value"] == 240.0
        assert again["measures"]["fcf_ttm"]["series"]["points"]
        assert sec.get("metrics") == {}  # the journal dict is untouched

    def test_a_strategy_cannot_retune_its_own_values_through_the_context(self):
        """The values and inputs dicts are the host's, resolved through the
        chain. A strategy mutating them would be the quiet retuning the
        record exists to prevent — so it gets a copy, not the original."""
        values = {"patience": 4}
        inputs = {"note": "as supplied"}
        ctx = context.build_context(security(), [], values, inputs)
        ctx["values"]["patience"] = 999
        ctx["inputs"]["note"] = "rewritten"
        assert values == {"patience": 4}
        assert inputs == {"note": "as supplied"}

    def test_the_journal_securities_list_is_never_reachable(self):
        sec = security(bucket="holdings",
                       position={"shares": 10, "cost_basis": 15.0,
                                 "opened": "2020-01-01"})
        ctx = context.build_context(sec, [sec], {}, {})
        ctx["portfolio"]["holdings"][0]["shares"] = 10_000
        ctx["security"]["ticker"] = "HACKED"
        assert sec["position"]["shares"] == 10
        assert sec["ticker"] == "SYN"


class TestTheEnvelope:
    def test_the_context_declares_the_contract_version_it_speaks(self):
        assert context.build_context(security(), [], {}, {})["contract"] \
            == contract.CONTRACT_VERSION
