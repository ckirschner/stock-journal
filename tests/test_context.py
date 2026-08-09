"""What a strategy receives: a complete shape whether or not data exists,
absence with reasons and never an invented value, series that obey the
clock, and a boundary the strategy cannot mutate anything through."""

from conftest import (balance_face, dur, filing, inst,
                      multiclass_company)

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
    s = {"ticker": "SYN", "name": "Synthetic Co", "metrics": {}, "lots": []}
    if cik:
        s["cik"] = cik
    s.update(over)
    return s


def lot(lid, kind, date, shares, price=10.0, against=None):
    """One recorded lot, shaped exactly as portfolio.add_lot writes it. The
    context reads lots and never writes them, so these are built by hand."""
    l = {"id": lid, "seq": int(lid[1:]), "kind": kind, "date": date,
         "recorded": date + "T00:00:00+00:00", "shares": float(shares),
         "price": float(price), "snapshot": None}
    if kind == "buy":
        l["override"] = None
    else:
        l["against"] = against or []
    return l


def holding(cik=None, shares=10, price=15.0, opened="2025-02-25", **over):
    return security(cik, lots=[lot("l1", "buy", opened, shares, price)],
                    **over)


def build(sec, journal=None, values=None, inputs=None, as_of=None,
          record=None):
    return context.build_context(sec, journal if journal is not None
                                 else [sec], values or {}, inputs or {},
                                 as_of=as_of, record=record)


def cash_strategy(required=True, **over):
    """A record shaped like the loader's output, declaring one input that
    claims the cash role — the only way the host is ever told what the
    account is."""
    spec = {"id": "free-cash", "label": "Free cash", "type": "number",
            "unit": "usd", "role": "cash", "explain": "Money not in a "
            "position."}
    if required:
        spec["required"] = True
    r = {"id": "sizer", "name": "Sizer", "summary": "s", "version": 1,
         "contract": contract.CONTRACT_VERSION, "changelog": {1: "f"},
         "states": [], "inputs": [spec], "values": [], "defaults": {}}
    r.update(over)
    return r


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

    def test_a_strategy_that_never_asks_for_cash_is_told_so_by_name(self):
        """Absence has to say which question was never asked, not shrug. The
        host holds no view about whether a journal ought to record cash."""
        ctx = build(security(), record=cash_strategy(inputs=[]))
        assert "no strategy in this journal asks for your free cash" in \
            ctx["portfolio"]["cash"]["reason"]


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

    def test_a_series_point_carries_the_cautions_of_its_own_reading(self):
        """A point is a measure like any other. Citing one at a past period
        must not be the way to get a figure with its qualification filed
        off — a screen showing that evidence has no other source for it, and
        a snapshot keeps whatever it was handed forever."""
        cls = multiclass_company(911)
        points = build(security(911))["measures"]["market_cap"]["series"][
            "points"]
        assert points, "the fixture must produce at least one boundary"
        for p in points:
            assert p["value"] is not None
            note = " ".join(p["cautions"])
            assert "no stored close" in note, p
            assert cls in note
            assert p["provenance"], p

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

    def test_the_close_and_its_history_are_the_security_being_shown(self):
        """Two share classes are two instruments. The served close and the
        close history must describe the same one — and it must be the one the
        journal holds, not whichever class traded most recently.

        This test used to assert the opposite: that the newest close across
        every mapped class wins. It was right about the guarantee and backwards
        about the answer, which is how a Class B holding came to be priced at
        the Class A close.
        """
        store_two_years(909)
        map_tickers(909, "SYN", "SYN.B")
        doc = price_store.load(909)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2026-01-02", 10.0, 100]], [])
        price_store.merge_series(doc, "SYN.B", "test",
                                 [["2026-01-05", 55.0, 100]], [])
        price_store.save(909, doc)
        sec = security(909)                          # the journal holds SYN
        ctx = context.build_context(sec, [sec], {}, {})
        latest = ctx["price"]["latest"]
        assert latest["ticker"] == "SYN"
        assert latest["value"] == 10.0
        assert ctx["price"]["closes"] == [["2026-01-02", 10.0]]

        held = context.build_context(security(909, ticker="SYN.B"),
                                     [security(909, ticker="SYN.B")], {}, {})
        assert held["price"]["latest"]["ticker"] == "SYN.B"
        assert held["price"]["latest"]["value"] == 55.0
        assert held["price"]["closes"] == [["2026-01-05", 55.0]]

    def test_a_security_with_no_close_of_its_own_says_so_by_name(self):
        """Seeing the company's other classes priced on screen while this one
        reads absent looks like a bug, so the absence names the instrument it
        is about and what else is stored. It explains the gap; it never fills
        it with a sibling's close."""
        store_two_years(915)
        map_tickers(915, "SYN", "SYN.B")
        doc = price_store.load(915)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2026-01-02", 10.0, 100]], [])
        price_store.save(915, doc)
        latest = context.build_context(security(915, ticker="SYN.B"),
                                       [], {}, {})["price"]["latest"]
        assert latest["status"] == "absent"
        assert "SYN.B" in latest["reason"]
        assert "SYN" in latest["reason"] and "share class" in latest["reason"]
        assert "value" not in latest

    def test_one_instrument_is_found_under_either_spelling(self):
        """The SEC writes a share class with a hyphen and people type a dot,
        and a fetch stores whichever it asked for. Those are one instrument;
        a different class is not."""
        store_two_years(916)
        doc = price_store.load(916)
        price_store.merge_series(doc, "SYN-B", "test",
                                 [["2026-01-05", 55.0, 100]], [])
        price_store.save(916, doc)
        latest = context.build_context(security(916, ticker="SYN.B"),
                                       [], {}, {})["price"]["latest"]
        assert latest["value"] == 55.0
        assert latest["ticker"] == "SYN-B"

    def test_every_mapped_share_class_is_read_for_company_measures(self):
        """The journal names one symbol; the SEC maps several to the CIK. A
        whole-company measure needs all of them, because the company is the
        subject. Nothing about the position comes through here."""
        store_two_years(914)
        map_tickers(914, "SYN", "SYN.B")
        assert context._tickers_of({"ticker": "SYN", "cik": 914}) \
            == ["SYN", "SYN.B"]
        assert context._tickers_of({"ticker": "SYN"}) == ["SYN"]

    def test_the_price_readers_refuse_a_list_of_classes(self):
        """The guarantee is structural, not a convention anyone has to
        remember: handing every mapped class to a price reader is refused at
        the door rather than quietly resolved to the newest one."""
        import pytest

        from engine import dataview
        for call in (lambda: dataview.price_view({}, 909, ["SYN", "SYN.B"]),
                     lambda: dataview.price_view_asof(909, ["SYN"],
                                                      "2026-01-05")):
            with pytest.raises(TypeError) as raised:
                call()
            assert "one symbol" in str(raised.value)

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
    def _priced(self, cik, rows):
        doc = price_store.load(cik)
        price_store.merge_series(doc, "SYN", "test", rows, [])
        price_store.save(cik, doc)

    def test_a_holding_reports_lots_and_market_value(self):
        store_two_years(906)
        self._priced(906, [["2025-03-01", 20.0, 100]])
        ctx = build(holding(906))
        pos = ctx["position"]
        assert pos["held"] is True
        assert pos["shares"] == 10.0
        assert pos["opened"] == "2025-02-25"
        assert pos["lots"] == [{"date": "2025-02-25", "shares": 10.0,
                                "remaining": 10.0, "open": True}]
        assert pos["disposals"] == []
        assert pos["market_value"]["value"] == 200.0
        assert pos["weight"]["status"] == "absent"      # nobody asked for cash
        assert ctx["portfolio"]["slots"]["occupied"] == 1
        assert ctx["portfolio"]["holdings"][0]["ticker"] == "SYN"

    def test_nothing_about_what_a_position_cost_reaches_a_strategy(self):
        """Structurally incapable of reaching a verdict means the figure is
        not there, not that citing it is discouraged. A rule fired on the
        distance from your own purchase price is anchoring — it makes the
        same company a buy for one person and a sell for another."""
        store_two_years(916)
        self._priced(916, [["2025-03-01", 20.0, 100]])
        sec = holding(916)      # bought at 15.00
        sec["lots"].append(lot("l2", "sell", "2025-04-01", 4, 30.0,
                               against=[{"lot": "l1", "shares": 4}]))
        ctx = build(sec)
        blob = repr(ctx["position"]) + repr(ctx["portfolio"])
        for figure in ("15.0", "30.0", "cost", "'price'"):
            assert figure not in blob, figure
        # ...and no fact names one either, so it cannot even be cited
        assert not [f for f in contract.HOST_FACTS if "cost" in f]

    def test_several_lots_report_what_remains_of_each(self):
        sec = security(lots=[
            lot("l1", "buy", "2025-01-01", 10, 15.0),
            lot("l2", "buy", "2025-03-01", 10, 25.0),
            lot("l3", "sell", "2025-06-01", 14, 30.0,
                against=[{"lot": "l1", "shares": 10},
                         {"lot": "l2", "shares": 4}])])
        pos = build(sec)["position"]
        assert pos["shares"] == 6.0
        # The holding began in January and has never ended, so that is what a
        # strategy binding on "held since" is told — the January *lot* being
        # sold down to nothing is a fact about a lot, and each lot carries its
        # own date and `open` for a rule that wants one.
        assert pos["opened"] == "2025-01-01"
        assert [(l["date"], l["remaining"], l["open"]) for l in pos["lots"]] \
            == [("2025-01-01", 0.0, False), ("2025-03-01", 6.0, True)]
        assert pos["disposals"] == [{"date": "2025-06-01", "shares": 14.0}]

    def test_a_position_opened_after_the_pin_did_not_exist_yet(self):
        ctx = build(holding(), as_of="2024-06-30")
        assert ctx["position"]["held"] is False
        assert ctx["position"]["lots"] == []
        # ...and the same context must not count it as occupying a slot.
        # One context, one story: a slot-bound strategy reconstructing a
        # past decision would otherwise see today's portfolio.
        assert ctx["portfolio"]["slots"]["occupied"] == 0
        assert ctx["portfolio"]["holdings"] == []

    def test_a_sale_after_the_pin_had_not_reduced_anything_yet(self):
        sec = holding(opened="2024-01-10")
        sec["lots"].append(lot("l2", "sell", "2025-01-01", 10, 30.0,
                               against=[{"lot": "l1", "shares": 10}]))
        assert build(sec, as_of="2024-06-30")["position"]["shares"] == 10.0
        assert build(sec)["position"]["shares"] == 0.0

    def test_a_position_opened_before_the_pin_is_priced_at_the_pin(self):
        store_two_years(908)
        self._priced(908, [["2024-06-28", 10.0, 100],
                           ["2026-01-05", 99.0, 100]])
        sec = holding(908, price="500.00", opened="2024-01-10")
        ctx = build(sec, as_of="2024-06-30")
        assert ctx["position"]["market_value"]["value"] == 100.0
        assert ctx["portfolio"]["holdings"][0]["market_value"]["value"] \
            == 100.0
        assert ctx["portfolio"]["slots"]["occupied"] == 1

    def test_the_portfolio_counts_only_what_the_clock_had(self):
        old = holding(ticker="OLD", shares=5, opened="2023-01-01")
        new = holding(ticker="NEW", shares=5, opened="2025-06-01")
        ctx = build(old, [old, new], as_of="2024-06-30")
        assert [h["ticker"] for h in ctx["portfolio"]["holdings"]] == ["OLD"]
        assert ctx["portfolio"]["slots"]["occupied"] == 1


class TestTheAccountAndWeight:
    """Weight is market value over the account, and the account is free cash
    plus every holding at market. All of it is arithmetic the host owns;
    whether a weight is too high belongs to a strategy and appears nowhere
    here."""

    def _priced(self, cik, close):
        doc = price_store.load(cik)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2025-03-01", close, 100]], [])
        price_store.save(cik, doc)

    def _held(self, cik=920, shares=10, close=20.0):
        store_two_years(cik)
        self._priced(cik, close)
        return holding(cik, shares=shares)

    def test_an_answered_cash_input_makes_weight_a_reported_fact(self):
        sec = self._held()
        ctx = build(sec, record=cash_strategy(),
                    inputs={"free-cash": 800.0})
        assert ctx["portfolio"]["cash"]["value"] == 800.0
        # 800 cash plus 10 shares at 20
        assert ctx["portfolio"]["account_value"]["value"] == 1000.0
        assert ctx["position"]["weight"]["value"] == 20.0
        assert ctx["portfolio"]["holdings"][0]["weight"]["value"] == 20.0

    def test_the_account_is_derived_and_says_what_it_rests_on(self):
        ctx = build(self._held(921), record=cash_strategy(),
                    inputs={"free-cash": 800.0})
        prov = " ".join(ctx["portfolio"]["account_value"]["provenance"])
        assert "free cash" in prov and "1 holding" in prov
        assert "of an account of" in \
            " ".join(ctx["position"]["weight"]["provenance"])

    def test_an_unanswered_cash_input_names_the_field_it_wants(self):
        ctx = build(self._held(922), record=cash_strategy())
        assert ctx["portfolio"]["cash"]["status"] == "absent"
        assert "Free cash" in ctx["portfolio"]["cash"]["reason"]
        assert ctx["position"]["weight"]["status"] == "absent"

    def test_one_unpriced_holding_makes_the_whole_account_absent(self):
        """Treating a missing price as zero would understate the account and
        quietly inflate every weight measured against it — a confident wrong
        answer in the number a sizing rule binds on."""
        sec = self._held(923)
        dark = holding(ticker="DARK", shares=5)     # no cik, no price
        ctx = build(sec, [sec, dark], record=cash_strategy(),
                    inputs={"free-cash": 800.0})
        av = ctx["portfolio"]["account_value"]
        assert av["status"] == "absent"
        assert "DARK" in av["reason"]
        assert ctx["position"]["weight"]["status"] == "absent"

    def test_an_account_of_nothing_or_less_has_no_share_to_express(self):
        """A margin balance is real, and dividing by it produces a confident
        nonsense figure rather than an honest absence."""
        sec = self._held(924)
        ctx = build(sec, record=cash_strategy(), inputs={"free-cash": -500.0})
        assert ctx["portfolio"]["account_value"]["value"] == -300.0
        assert ctx["position"]["weight"]["status"] == "absent"
        assert "nothing or less" in ctx["position"]["weight"]["reason"]

    def test_the_subject_counts_even_when_the_caller_passes_no_list(self):
        """A portfolio that excluded the holding in front of you would
        measure its weight against an account it was not part of."""
        sec = self._held(925)
        ctx = build(sec, [], record=cash_strategy(),
                    inputs={"free-cash": 800.0})
        assert ctx["portfolio"]["account_value"]["value"] == 1000.0
        assert ctx["position"]["weight"]["value"] == 20.0

    def test_under_a_pin_cash_participates_but_says_it_is_undated(self):
        """The same rule a hand-entered measure obeys: an answer with no date
        is the value on record now, never one known to be true then."""
        sec = self._held(926)
        ctx = build(sec, record=cash_strategy(), inputs={"free-cash": 800.0},
                    as_of="2025-03-05")
        for node in (ctx["portfolio"]["cash"],
                     ctx["portfolio"]["account_value"],
                     ctx["position"]["weight"]):
            assert any("carries no date" in c for c in node["cautions"]), node
        assert not build(sec, record=cash_strategy(),
                         inputs={"free-cash": 800.0}
                         )["portfolio"]["cash"]["cautions"]

    def test_an_answer_to_a_question_that_does_not_apply_is_not_served(self):
        """A stale answer to a gated-off question is worse than no answer:
        the strategy has no way to tell the two apart."""
        rec = cash_strategy(required=False, inputs=[
            {"id": "sizes-by-cash", "label": "Size by cash?", "type":
             "boolean", "explain": "e"},
            {"id": "free-cash", "label": "Free cash", "type": "number",
             "unit": "usd", "role": "cash", "explain": "e",
             "when": {"input": "sizes-by-cash", "is": True}}])
        supplied = {"sizes-by-cash": False, "free-cash": 800.0}
        ctx = build(self._held(927), record=rec, inputs=supplied)
        assert "free-cash" not in ctx["inputs"]
        assert ctx["portfolio"]["cash"]["status"] == "absent"
        assert build(self._held(928), record=rec,
                     inputs={"sizes-by-cash": True, "free-cash": 800.0}
                     )["portfolio"]["cash"]["value"] == 800.0


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
        sec = holding(opened="2020-01-01")
        ctx = context.build_context(sec, [sec], {}, {})
        ctx["portfolio"]["holdings"][0]["shares"] = 10_000
        ctx["position"]["lots"][0]["remaining"] = 10_000
        ctx["security"]["ticker"] = "HACKED"
        assert sec["lots"][0]["shares"] == 10
        assert sec["ticker"] == "SYN"


class TestTheEnvelope:
    def test_the_context_declares_the_contract_version_it_speaks(self):
        assert context.build_context(security(), [], {}, {})["contract"] \
            == contract.CONTRACT_VERSION
