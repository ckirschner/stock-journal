"""What a strategy receives: a complete shape whether or not data exists,
absence with reasons and never an invented value, series that obey the
clock, and a boundary the strategy cannot mutate anything through."""

from datetime import date

import conftest
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


def security(cik=None, entered_on=None, entered=None, **over):
    """A bare security, optionally with hand-entered figures already on its
    dated record. `entered_on` is the day they were written — the record has
    no other way to be given one, which is the point of it."""
    s = {"ticker": "SYN", "name": "Synthetic Co", "lots": []}
    if cik:
        s["cik"] = cik
    s.update(over)
    if entered:
        conftest.entered(s, entered_on, **entered)
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
        ctx = build(security(902, entered={"fcf_ttm": 149.0},
                             entered_on="2026-03-04"))
        cur = ctx["measures"]["fcf_ttm"]["current"]
        assert cur["value"] == 149.0
        assert cur["source"] == "manual"
        # And says when. A figure someone typed is only checkable against
        # what happened if the record says which day they typed it.
        assert cur["provenance"] == ["entered by hand on 2026-03-04"]

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

    def test_a_manual_measure_reaches_a_pin_written_after_it(self):
        """A hand-entered value is on record from the day it was entered.
        A pin after that day sees it, exactly as it sees a filing."""
        ctx = build(security(entered={"fcf_ttm": 999.0},
                             entered_on="2019-05-02"), as_of="2020-01-01")
        cur = ctx["measures"]["fcf_ttm"]["current"]
        assert cur["value"] == 999.0 and cur["source"] == "manual"
        assert cur["provenance"] == ["entered by hand on 2019-05-02"]
        # Nothing to caution about. The old undated warning existed because
        # the figure could not say when it was written; it can now.
        assert cur["cautions"] == []

    def test_a_manual_measure_written_after_the_pin_is_absent_not_undated(self):
        """The contamination this record exists to stop.

        A figure typed today may have been typed *because* of what happened
        since. Serving it to a verdict rebuilt for 2020 would let hindsight
        into a reconstruction, so it is absent, and the reason says the day
        it was actually written.
        """
        ctx = build(security(entered={"fcf_ttm": 999.0},
                             entered_on="2026-08-09"), as_of="2020-01-01")
        cur = ctx["measures"]["fcf_ttm"]["current"]
        assert cur["status"] == "absent"
        assert "value" not in cur
        assert "2026-08-09" in cur["reason"] and "2020-01-01" in cur["reason"]

    def test_a_withdrawn_value_is_absent_and_never_a_none(self):
        """Clearing a field is an entry, not a deletion — and the entry
        holds nothing, so nothing can serve it as a figure. A `None` reaching
        a strategy as a known value is principle 4's exact failure."""
        s = security(entered={"fcf_ttm": 999.0}, entered_on="2026-01-05")
        conftest.entered(s, "2026-02-05", fcf_ttm=None)
        cur = build(s)["measures"]["fcf_ttm"]["current"]
        assert cur["status"] == "absent"
        assert "value" not in cur
        assert "2026-02-05" in cur["reason"]
        # And the withdrawal is still legible: nothing was removed.
        assert len(s["hand_entered"]) == 2

    def test_a_withdrawn_value_lets_the_computed_one_back_through(self):
        """Withdrawing your own figure does not make the filings
        unreadable. "You cleared this" is a worse answer than the number
        that was there all along."""
        store_two_years(917)
        s = security(917, entered={"fcf_ttm": 149.0}, entered_on="2026-01-05")
        conftest.entered(s, "2026-02-05", fcf_ttm=None)
        cur = build(s)["measures"]["fcf_ttm"]["current"]
        assert cur["status"] == "known"
        assert cur["value"] == 240.0 and cur["source"] == "computed"

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

    def test_under_a_pin_cash_is_the_answer_of_that_day_or_none_at_all(self):
        """Free cash used to be served from today's answer under any pin,
        with a caution saying it carried no date. It does carry a date — every
        change to it is on the journal's own append-only record — and the
        caution was the wrong fix anyway: a qualified wrong number still
        decides. The account total is built from this, every weight is
        measured against the account, and strategies bind on weight, so a
        purchase backdated two years was being sized against today's balance
        with a sentence beside it.

        The answers that reach the context are now already the ones that were
        on record on the day being evaluated — resolved in journals.answers_on
        before the context is built — so a pin serves a figure or nothing.
        Nothing is where every real backfill lands, because the journal held
        no answers before it existed.
        """
        sec = self._held(926)
        ctx = build(sec, record=cash_strategy(), inputs={"free-cash": 800.0},
                    as_of="2025-03-05")
        # Given an answer for that day, it is served as one — dated, not
        # apologised for.
        assert ctx["portfolio"]["cash"]["value"] == 800.0
        assert not ctx["portfolio"]["cash"]["cautions"]
        assert "2025-03-05" in \
            " ".join(ctx["portfolio"]["cash"]["provenance"])

        # Given none, the absence cascades all the way to weight rather than
        # a present-day balance standing in for a past one.
        dark = build(sec, record=cash_strategy(), inputs={},
                     as_of="2025-03-05")
        assert dark["portfolio"]["cash"]["status"] == "absent"
        assert "2025-03-05" in dark["portfolio"]["cash"]["reason"]
        assert dark["portfolio"]["account_value"]["status"] == "absent"
        assert dark["position"]["weight"]["status"] == "absent"

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
        # The journal dict is untouched: a read never writes to the record.
        assert sec.get("hand_entered") is None

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


class TestOneContextComesFromOneReadingOfTheStores:
    """A context that is internally inconsistent gets frozen that way.

    Building one used to read the company's stores three separate times: the
    current values through `dataview._bundle`, the per-filing series through
    its own `facts_store.load_all_filings`, and the industry node through its
    own `industry.report`. Each read checked the fingerprint again, so a fetch
    landing between any two of them produced a context whose series were one
    filing newer than its current values, or whose classification came from a
    different reading of the identity record than the one that decided whether
    a measure applies.

    On a screen that self-heals on the next render. On a purchase it does not:
    principle 3 says what was frozen at that moment is never recomputed, so a
    context assembled from two instants is a permanent record of a day that
    never existed.

    Counted rather than described, because the window is a race and a race is
    exactly what a "check it carefully" rule fails to hold.
    """

    def _counted(self, fn):
        from engine import dataview
        from engine import industry as industry_mod
        calls = {"fingerprint": 0, "filings": 0, "identity": 0}
        real = (dataview._fingerprint, facts_store.load_all_filings,
                industry_mod.history)

        def wrap(key, f):
            def inner(*a, **kw):
                calls[key] += 1
                return f(*a, **kw)
            return inner

        dataview._fingerprint = wrap("fingerprint", real[0])
        facts_store.load_all_filings = wrap("filings", real[1])
        industry_mod.history = wrap("identity", real[2])
        try:
            dataview.invalidate()
            fn()
        finally:
            (dataview._fingerprint, facts_store.load_all_filings,
             industry_mod.history) = real
        return calls

    def test_a_live_build_reads_each_store_once(self):
        store_two_years(940)
        calls = self._counted(lambda: build(security(940)))
        assert calls == {"fingerprint": 1, "filings": 1, "identity": 1}, calls

    def test_a_reconstruction_reads_each_store_once(self):
        """The pinned build matters more, not less: this is the one whose
        output is written onto a lot and never touched again."""
        store_two_years(941)
        calls = self._counted(
            lambda: build(security(941), as_of="2024-06-30"))
        assert calls == {"fingerprint": 1, "filings": 1, "identity": 1}, calls

    def test_a_caller_holding_one_snapshot_spends_no_reads_at_all(self):
        """What the handle is for. A request assembling several contexts —
        the values a screen shows and the decision frozen beside them — takes
        one snapshot and hands it to each, so every one of them describes the
        same instant rather than each being separately correct."""
        from engine import dataview
        store_two_years(942)
        sec = security(942)
        snap = dataview.snapshot(942, ["SYN"])
        calls = self._counted(lambda: [
            context.build_context(sec, [sec], {}, {}, snap=snap),
            context.build_context(sec, [sec], {}, {}, as_of="2024-06-30",
                                  snap=snap)])
        assert calls == {"fingerprint": 0, "filings": 0, "identity": 0}, calls

    def test_the_series_and_the_current_value_agree_about_the_filings(self):
        """The observable half. Both halves of `measures` come off one
        reading, so the newest series point is computed from the same filing
        set the current value was."""
        store_two_years(943)
        m = build(security(943))["measures"]["fcf_ttm"]
        assert m["current"]["status"] == "known"
        assert m["current"]["value"] == 240.0        # cfo 300 − capex 60
        assert [p["value"] for p in m["series"]["points"]] == [150.0, 240.0]

    def test_the_context_never_reaches_a_store_itself(self):
        """The structural half, and the reason the counts above stay true.
        Building a context goes through `dataview` for everything; a direct
        store import here is how a fourth independent read gets added by
        somebody who did not know there was a rule."""
        import ast
        import pathlib
        tree = ast.parse(pathlib.Path(context.__file__).read_text(
            encoding="utf-8"))
        # Every import anywhere in the file, not only the ones at the top: a
        # function-local `from . import facts_store` is the version of this
        # somebody reaches for precisely because it looks smaller.
        named = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                named.update(a.name for a in node.names)
            elif isinstance(node, ast.Import):
                named.update(a.name.split(".")[-1] for a in node.names)
        reaching = named & {"facts_store", "price_store", "instruments",
                            "store"}
        assert reaching == set(), (
            f"engine/context.py imports {', '.join(sorted(reaching))} — read "
            "the stores through dataview.snapshot, so one build is one "
            "instant rather than several that each happen to be correct")

    def test_the_values_and_the_verdict_frozen_together_see_one_instant(self):
        """The pair that matters, because this one is written once.

        `_evaluated_for` assembles what a purchase freezes: the figures behind
        the decision, and the decision. They are two passes over the same
        stores and each used to read for itself, so a fetch landing between
        them froze a record whose verdict saw one filing more than the numbers
        recorded beside it as the reason for it. A screen heals on the next
        render; an append-only entry does not, and nothing may recompute it.

        Driven with a real strategy, so `_decide` genuinely builds a context.
        Without one it returns host:strategy-missing before reading anything,
        and the second pass this is counting never happens.
        """
        import app as app_mod

        store_two_years(944)
        api = app_mod.Api()
        sec = security(944)
        record = {
            "id": "counter", "name": "Counter", "summary": "s", "version": 1,
            "contract": contract.CONTRACT_VERSION, "changelog": {1: "f"},
            "states": [{"id": "sit", "name": "Sit", "render": "hold",
                        "description": "Do nothing."}],
            "inputs": [], "values": [], "defaults": {}, "values_version": 1,
            "decide": lambda ctx: {
                "state": "sit", "payload": {},
                "reason": {"rule": "always", "summary": "By design.",
                           "evidence": [{"label": "A stated figure",
                                         "unit": "count", "actual": 1}]}},
        }
        journal = {"securities": [sec], "strategy": {
            "id": "counter", "name": "Counter", "version": 1,
            "values_version": 1, "contract": contract.CONTRACT_VERSION}}

        for label, when, is_past in (("live", date.today().isoformat(), False),
                                     ("pinned", "2024-06-30", True)):
            calls = self._counted(lambda: api._evaluated_for(
                journal, record, {"values": {}, "errors": []}, sec,
                when, is_past))
            assert calls == {"fingerprint": 1, "filings": 1,
                             "identity": 1}, (label, calls)

    def test_that_entry_really_did_reach_a_verdict(self):
        """The guard on the test above. Counting reads proves nothing if the
        second pass returned early — a record with no strategy never builds a
        context at all, and the count would be 1 for the wrong reason."""
        import app as app_mod

        store_two_years(945)
        api = app_mod.Api()
        sec = security(945)
        record = {
            "id": "counter", "name": "Counter", "summary": "s", "version": 1,
            "contract": contract.CONTRACT_VERSION, "changelog": {1: "f"},
            "states": [{"id": "sit", "name": "Sit", "render": "hold",
                        "description": "Do nothing."}],
            "inputs": [], "values": [], "defaults": {}, "values_version": 1,
            "decide": lambda ctx: {
                "state": "sit", "payload": {},
                "reason": {"rule": "always", "summary": "By design.",
                           "evidence": [{"label": "A stated figure",
                                         "unit": "count", "actual": 1}]}},
        }
        journal = {"securities": [sec], "strategy": {
            "id": "counter", "name": "Counter", "version": 1,
            "values_version": 1, "contract": contract.CONTRACT_VERSION}}
        at = api._evaluated_for(journal, record, {"values": {}, "errors": []},
                                sec, date.today().isoformat(), False)
        assert at["decision"]["state"]["id"] == "sit"
        assert at["decision"]["produced_by"] == "strategy"
        assert at["values"]["fcf_ttm"]["value"] == 240.0
