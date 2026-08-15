"""The account on a day, the change across a window, and two kept days side
by side — the interface additions the brief authorised, pinned where they
would fail silently.

Every failure mode here is a confident wrong number, not a crash: a missing
price becoming zero inside the account total, a deposit reading as a gain,
a return anchored to a figure nobody typed on that day, a delta subtracted
across a redefinition, and "nothing kept" reading as "unchanged". Each is
asserted as an absence with its reason, because that is the shape the whole
program serves them in.
"""

import pytest
from conftest import balance_face, filing, inst, open_since

from engine import bank, context, dataview, dated, journals, snapshots

from app import Api

ANSWERS = {"stance": "building", "keeps-reserve": "false", "first-buy": "4"}

OPENED_ON = "2026-01-01"
OPENING = 50_000.0


@pytest.fixture
def api(strategies):
    strategies("awkward")
    a = Api()
    made = a.create_journal("Whole account", "awkward", dict(ANSWERS),
                            opening_cash=OPENING, opening_cash_on=OPENED_ON)
    assert made["ok"], made
    open_since(OPENED_ON)
    return a


def journal():
    return journals.load(journals.resolve_open())


def security(ticker):
    return next(s for s in journal()["securities"] if s["ticker"] == ticker)


def company(cik=881, ticker="TUBE", rows=None):
    """One filing so measures have something to read, and a price series
    with closes either side of the window the tests measure across."""
    from engine import facts_store, price_store
    end = "2024-12-31"
    facts = balance_face(end, extra=[
        inst("us-gaap:AssetsCurrent", end, 200),
        inst("us-gaap:LiabilitiesCurrent", end, 100)])
    facts_store.save_filing(cik, filing("A-1", "10-K", "2025-02-20", end,
                                        facts))
    doc = price_store.load(cik)
    price_store.merge_series(doc, ticker, "test", rows or [
        ["2026-06-30", 10.0, 100],
        ["2026-07-31", 12.0, 100],
        ["2026-08-12", 14.0, 100]], [])
    price_store.save(cik, doc)
    return cik


def add(api, ticker, cik=None, name=None):
    assert api.add_security(ticker, name or f"{ticker.title()} Co")["ok"]
    if cik is not None:
        doc = journal()
        next(s for s in doc["securities"]
             if s["ticker"] == ticker)["cik"] = cik
        journals.save(doc)


# -- the account on a day ----------------------------------------------------

class TestTheAccountOnADay:

    def test_a_past_day_prices_that_days_holdings_at_that_days_closes(
            self, api):
        add(api, "TUBE", company())
        assert api.open_position("TUBE", 100, 9.0, "2026-06-30",
                                 "a reason")["ok"]
        # Bought more later; the earlier day must not see it.
        assert api.open_position("TUBE", 50, 12.0, "2026-08-01",
                                 "a reason")["ok"]
        doc = journal()
        got = context.account_value_on(doc, doc["securities"], "2026-07-15")
        [h] = got["holdings"]
        assert h["shares"] == 100
        assert h["market_value"]["value"] == 100 * 10.0  # the 06-30 close
        assert got["cash"]["value"] == OPENING - 900
        assert got["account_value"]["value"] == OPENING - 900 + 1_000
        assert h["weight"]["status"] == "known"

    def test_a_missing_close_makes_the_total_absent_naming_it_never_zero(
            self, api):
        add(api, "TUBE", company())
        add(api, "DARK")
        assert api.save_metrics("DARK", {}, 5.0)["ok"]  # typed, undated
        assert api.open_position("TUBE", 10, 9.0, "2026-06-30", "r")["ok"]
        assert api.open_position("DARK", 10, 4.0, "2026-06-30", "r")["ok"]
        doc = journal()
        got = context.account_value_on(doc, doc["securities"], "2026-07-15")
        total = got["account_value"]
        assert total["status"] == "absent"
        assert "DARK" in total["reason"]
        dark = next(h for h in got["holdings"] if h["ticker"] == "DARK")
        # A typed price is a statement about now; the past never serves it.
        assert dark["market_value"]["status"] == "absent"
        tube = next(h for h in got["holdings"] if h["ticker"] == "TUBE")
        assert tube["market_value"]["status"] == "known", \
            "one dark holding must not take the priced one's own node down"

    def test_the_live_total_reads_the_effective_price(self, api):
        add(api, "DARK")
        assert api.save_metrics("DARK", {}, 5.0)["ok"]
        assert api.open_position("DARK", 10, 4.0, "2026-06-30", "r")["ok"]
        doc = journal()
        got = context.account_value_on(doc, doc["securities"])
        [h] = got["holdings"]
        assert h["market_value"]["value"] == 50.0
        assert got["account_value"]["value"] == OPENING - 40 + 50

    def test_a_day_before_the_cash_record_is_absent_not_the_opening_figure(
            self, api):
        doc = journal()
        got = context.account_value_on(doc, doc["securities"], "2025-06-01")
        assert got["cash"]["status"] == "absent"
        assert got["account_value"]["status"] == "absent"


# -- the change across a window ----------------------------------------------

class TestTheChangeAcrossAWindow:

    def test_a_deposit_inside_the_window_is_not_a_gain(self, api):
        add(api, "TUBE", company())
        assert api.open_position("TUBE", 100, 9.0, "2026-06-30", "r")["ok"]
        assert api.record_cash("deposit", 10_000, "2026-07-20")["ok"]
        doc = journal()
        got = context.account_change(doc, doc["securities"], "2026-07-15")
        # then: 49,100 cash + 100 sh at the 10.0 close = 50,100
        # now:  59,100 cash + 100 sh at the 14.0 close = 60,500
        # the only real move is the price: 100 x (14 - 10) = 400
        assert got["net_external"]["value"] == 10_000
        assert got["change"]["value"] == 400.0
        assert got["percent"]["value"] == round(400 / 50_100 * 100, 2)

    def test_a_deposit_on_the_window_start_day_is_not_double_counted(
            self, api):
        add(api, "TUBE", company())
        assert api.open_position("TUBE", 100, 9.0, "2026-06-30", "r")["ok"]
        assert api.record_cash("deposit", 5_000, "2026-07-15")["ok"]
        doc = journal()
        got = context.account_change(doc, doc["securities"], "2026-07-15")
        # The 07-15 valuation is end-of-day, so the deposit is inside `then`
        # and outside the flows — counted once, not twice.
        assert got["net_external"]["value"] == 0
        assert got["change"]["value"] == 400.0

    def test_an_unpriceable_endpoint_makes_the_change_absent(self, api):
        add(api, "DARK")
        assert api.save_metrics("DARK", {}, 5.0)["ok"]
        assert api.open_position("DARK", 10, 4.0, "2026-06-30", "r")["ok"]
        doc = journal()
        got = context.account_change(doc, doc["securities"], "2026-07-15")
        assert got["change"]["status"] == "absent"
        assert "2026-07-15" in got["change"]["reason"]
        assert got["percent"]["status"] == "absent"

    def test_a_dividend_is_earned_and_never_netted_out(self, api):
        add(api, "TUBE", company())
        assert api.open_position("TUBE", 100, 9.0, "2026-06-30", "r")["ok"]
        assert api.record_cash("dividend", 1_000, "2026-07-20")["ok"]
        doc = journal()
        got = context.account_change(doc, doc["securities"], "2026-07-15")
        assert got["net_external"]["value"] == 0
        # 400 of price move plus 1,000 the holdings paid out.
        assert got["change"]["value"] == 1_400.0


# -- a row's move over the window --------------------------------------------

class TestARowsMoveOverTheWindow:

    def test_a_fetched_to_fetched_move(self, api):
        cik = company()
        add(api, "TUBE", cik)
        got = dataview.price_return(security("TUBE"), cik, "TUBE",
                                    "2026-07-15")
        assert got["status"] == "known"
        assert got["value"] == 40.0  # 10.0 to 14.0

    def test_a_typed_now_end_is_qualified_not_refused(self, api):
        cik = company()
        add(api, "TUBE", cik)
        assert api.save_metrics("TUBE", {}, 21.0)["ok"]
        got = dataview.price_return(security("TUBE"), cik, "TUBE",
                                    "2026-07-15")
        assert got["status"] == "known"
        assert got["value"] == 110.0  # 10.0 to the typed 21.0
        assert any("carries no date" in c for c in got["cautions"])

    def test_a_name_with_no_dated_history_says_so(self, api):
        add(api, "DARK")
        assert api.save_metrics("DARK", {}, 5.0)["ok"]
        got = dataview.price_return(security("DARK"), None, "DARK",
                                    "2026-07-15")
        assert got["status"] == "absent"
        assert "dated price history" in got["reason"]

    def test_a_window_starting_before_the_series_says_which_close_is_missing(
            self, api):
        cik = company()
        add(api, "TUBE", cik)
        got = dataview.price_return(security("TUBE"), cik, "TUBE",
                                    "2026-01-15")
        assert got["status"] == "absent"
        assert "2026-01-15" in got["reason"]


# -- two kept days side by side ----------------------------------------------

def kept_seq(api, ticker, note=""):
    r = api.save_snapshot(ticker, note)
    assert r["ok"], r
    return r["seq"]


class TestTwoKeptDaysSideBySide:

    def test_the_delta_reads_off_what_was_frozen(self, api):
        add(api, "TUBE", company())
        assert api.save_metrics("TUBE", {"fcf_ttm": 1_000_000}, None)["ok"]
        one = kept_seq(api, "TUBE", "first")
        assert api.save_metrics("TUBE", {"fcf_ttm": 2_500_000}, None)["ok"]
        two = kept_seq(api, "TUBE", "second")
        got = snapshots.compare(security("TUBE"), journal(), [two, one],
                                bank.COMPARABLE_FIELDS)
        assert [c["seq"] for c in got["columns"]] == [one, two], \
            "columns are oldest first whatever order was asked in"
        m = got["measures"]["fcf_ttm"]
        assert [r["status"] for r in m["readings"]] == ["known", "known"]
        assert m["readings"][0]["value"] == 1_000_000
        assert m["moved"]["value"] == 1_500_000
        assert len(got["verdict"]) == len(got["price"]) == 2

    def test_a_figure_on_one_record_only_is_absent_never_invented(self, api):
        add(api, "TUBE", company())
        one = kept_seq(api, "TUBE")
        assert api.save_metrics("TUBE", {"fcf_ttm": 2_500_000}, None)["ok"]
        two = kept_seq(api, "TUBE")
        got = snapshots.compare(security("TUBE"), journal(), [one, two],
                                bank.COMPARABLE_FIELDS)
        m = got["measures"]["fcf_ttm"]
        assert m["readings"][0]["status"] == "absent"
        assert "cannot say whether" in m["readings"][0]["reason"]
        assert m["moved"]["status"] == "absent"
        assert "not on both records" in m["moved"]["reason"]

    def test_a_judgement_is_read_beside_itself_never_subtracted(self, api):
        add(api, "TUBE", company())
        assert api.record_judgement("TUBE", "moat_durability", "pass",
                                    "Contracts lock the customers in.")["ok"]
        one = kept_seq(api, "TUBE")
        assert api.record_judgement("TUBE", "moat_durability", "fail",
                                    "The contracts lapsed.")["ok"]
        two = kept_seq(api, "TUBE")
        got = snapshots.compare(security("TUBE"), journal(), [one, two],
                                bank.COMPARABLE_FIELDS)
        m = got["measures"]["moat_durability"]
        assert [r["status"] for r in m["readings"]] == ["known", "known"]
        assert m["moved"]["status"] == "absent"
        assert "not a quantity" in m["moved"]["reason"]

    def test_a_redefined_measure_refuses_the_delta(self, api):
        assert "unit" not in bank.COMPARABLE_FIELDS, \
            "this test needs a field whose move breaks comparability"
        add(api, "TUBE", company())
        assert api.save_metrics("TUBE", {"fcf_ttm": 1_000_000}, None)["ok"]
        one = kept_seq(api, "TUBE")
        # The definition moves between the two kept days. Forged onto the
        # record in the shape observe_measure_change writes, with the next
        # position in the append-only list.
        doc = journal()
        record = doc.setdefault("measure_changes", [])
        record.append({"seq": len(record) + 1, "seen": "2026-08-14T09:00:00",
                       "moved": [{"id": "fcf_ttm", "name": "Free cash flow",
                                  "field": "unit", "from": "usd",
                                  "to": "score"}]})
        journals.save(doc)
        assert api.save_metrics("TUBE", {"fcf_ttm": 2_500_000}, None)["ok"]
        two = kept_seq(api, "TUBE")
        got = snapshots.compare(security("TUBE"), journal(), [one, two],
                                bank.COMPARABLE_FIELDS)
        m = got["measures"]["fcf_ttm"]
        assert [r["status"] for r in m["readings"]] == ["known", "known"], \
            "the readings themselves stay readable"
        assert m["moved"]["status"] == "absent"
        assert "not be a distance in one measure" in m["moved"]["reason"]

    def test_a_record_without_positions_cannot_place_the_gate(self, api):
        add(api, "TUBE", company())
        assert api.save_metrics("TUBE", {"fcf_ttm": 1_000_000}, None)["ok"]
        one = kept_seq(api, "TUBE")
        two = kept_seq(api, "TUBE")
        # An entry frozen before the change record existed carries no
        # positions. Simulated on the stored entry, the way an old journal
        # genuinely holds it.
        doc = journal()
        sec = next(s for s in doc["securities"] if s["ticker"] == "TUBE")
        for row in sec["snapshots"]:
            if row["seq"] == one:
                row["snapshot"]["changes_recorded"] = None
        journals.save(doc)
        got = snapshots.compare(security("TUBE"), journal(), [one, two],
                                bank.COMPARABLE_FIELDS)
        m = got["measures"]["fcf_ttm"]
        assert m["moved"]["status"] == "absent"
        assert "predates the change record" in m["moved"]["reason"]

    def test_a_discarded_day_is_still_comparable(self, api):
        add(api, "TUBE", company())
        assert api.save_metrics("TUBE", {"fcf_ttm": 1_000_000}, None)["ok"]
        one = kept_seq(api, "TUBE")
        assert api.save_metrics("TUBE", {"fcf_ttm": 2_500_000}, None)["ok"]
        two = kept_seq(api, "TUBE")
        assert api.discard_snapshot("TUBE", one, "kept twice")["ok"]
        got = snapshots.compare(security("TUBE"), journal(), [one, two],
                                bank.COMPARABLE_FIELDS)
        assert got["columns"][0]["discarded"], \
            "the comparison says the day was discarded"
        assert got["measures"]["fcf_ttm"]["moved"]["value"] == 1_500_000

    def test_fewer_than_two_days_is_refused(self, api):
        add(api, "TUBE", company())
        one = kept_seq(api, "TUBE")
        with pytest.raises(ValueError):
            snapshots.compare(security("TUBE"), journal(), [one],
                              bank.COMPARABLE_FIELDS)

    def test_a_day_never_saved_is_refused_by_name(self, api):
        add(api, "TUBE", company())
        one = kept_seq(api, "TUBE")
        with pytest.raises(ValueError) as e:
            snapshots.compare(security("TUBE"), journal(), [one, 99],
                              bank.COMPARABLE_FIELDS)
        assert "99" in str(e.value)


# -- "new" means changed since the last kept day ------------------------------

class TestNewMeansChangedSinceTheLastKeptDay:

    def test_nothing_kept_is_absent_not_unchanged(self, api):
        add(api, "TUBE", company())
        got = snapshots.since_last(security("TUBE"), {"state": {"id": "x"}})
        assert got["status"] == "absent"
        assert "no saved reading" in got["reason"]

    def test_the_same_verdict_reads_unchanged(self, api):
        add(api, "TUBE", company())
        kept_seq(api, "TUBE")
        state = api.get_state()
        s = next(x for x in state["securities"] if x["ticker"] == "TUBE")
        assert s["_since_reading"]["status"] == "known"
        assert s["_since_reading"]["changed"] is False

    def test_a_moved_verdict_reads_changed(self, api):
        add(api, "TUBE", company())
        kept_seq(api, "TUBE")
        doc = journal()
        sec = next(s for s in doc["securities"] if s["ticker"] == "TUBE")
        frozen = sec["snapshots"][-1]["snapshot"]["decision"]
        frozen["state"] = {**frozen["state"], "id": "some-earlier-state",
                          "name": "What it said then"}
        journals.save(doc)
        state = api.get_state()
        s = next(x for x in state["securities"] if x["ticker"] == "TUBE")
        assert s["_since_reading"]["changed"] is True
        assert s["_since_reading"]["from"]["name"] == "What it said then"

    def test_every_kept_day_discarded_is_absent_again(self, api):
        add(api, "TUBE", company())
        one = kept_seq(api, "TUBE")
        assert api.discard_snapshot("TUBE", one)["ok"]
        got = snapshots.since_last(security("TUBE"), {"state": {"id": "x"}})
        assert got["status"] == "absent"

    def test_an_unreadable_record_is_absent_with_the_refusal_never_a_raise(
            self, api):
        add(api, "TUBE", company())
        kept_seq(api, "TUBE")
        doc = journal()
        sec = next(s for s in doc["securities"] if s["ticker"] == "TUBE")
        dated.append(sec, snapshots.KEY, {"kind": "pinned"})
        journals.save(doc)
        got = snapshots.since_last(security("TUBE"), {"state": {"id": "x"}})
        assert got["status"] == "absent"
        assert "does not know how to read" in got["reason"]


# -- the served payload -------------------------------------------------------

class TestTheServedPayload:

    def test_get_state_serves_the_account_node_whole(self, api):
        add(api, "TUBE", company())
        assert api.open_position("TUBE", 100, 9.0, "2026-06-30", "r")["ok"]
        state = api.get_state()
        node = state["portfolio"]
        assert node["account_value"]["status"] == "known"
        assert node["cash"]["value"] == state["cash"]["balance"]["value"], \
            "two servings of the cash balance disagree"
        [h] = node["holdings"]
        assert h["ticker"] == "TUBE" and h["weight"]["status"] == "known"

    def test_timeframe_view_serves_the_window_whole(self, api):
        add(api, "TUBE", company())
        assert api.open_position("TUBE", 100, 9.0, "2026-06-30", "r")["ok"]
        assert api.record_cash("deposit", 10_000, "2026-07-20")["ok"]
        r = api.timeframe_view("2026-07-15")
        assert r["ok"], r
        assert r["account"]["change"]["value"] == 400.0
        assert r["rows"]["TUBE"]["value"] == 40.0

    def test_timeframe_view_refuses_a_day_that_is_not_one(self, api):
        assert not api.timeframe_view("not-a-day")["ok"]
        assert not api.timeframe_view("2030-01-01")["ok"]

    def test_compare_snapshots_round_trips(self, api):
        add(api, "TUBE", company())
        assert api.save_metrics("TUBE", {"fcf_ttm": 1_000_000}, None)["ok"]
        one = kept_seq(api, "TUBE")
        assert api.save_metrics("TUBE", {"fcf_ttm": 2_500_000}, None)["ok"]
        two = kept_seq(api, "TUBE")
        r = api.compare_snapshots("TUBE", [one, two])
        assert r["ok"], r
        assert r["comparison"]["measures"]["fcf_ttm"]["moved"]["value"] \
            == 1_500_000

    def test_compare_snapshots_refusal_is_a_sentence_not_a_crash(self, api):
        add(api, "TUBE", company())
        one = kept_seq(api, "TUBE")
        r = api.compare_snapshots("TUBE", [one])
        assert not r["ok"]
        assert "two" in r["error"]


class TestTheReviewsFindings:
    """Two honest-absence gaps an adversarial review caught in the code this
    branch added, pinned so they stay closed."""

    def test_a_window_with_no_close_in_it_is_absent_not_a_confident_zero(
            self, api):
        # The newest close on record predates the window's start: the same
        # close would stand at both ends, and 0.0% would be an answer about
        # a window nothing was observed in.
        cik = company(rows=[["2026-05-30", 10.0, 100]])
        add(api, "TUBE", cik)
        got = dataview.price_return(security("TUBE"), cik, "TUBE",
                                    "2026-07-15")
        assert got["status"] == "absent"
        assert "no close is stored after 2026-07-15" in got["reason"]

    def test_a_typed_now_end_still_measures_across_the_window(self, api):
        cik = company(rows=[["2026-05-30", 10.0, 100]])
        add(api, "TUBE", cik)
        assert api.save_metrics("TUBE", {}, 12.0)["ok"]
        got = dataview.price_return(security("TUBE"), cik, "TUBE",
                                    "2026-07-15")
        assert got["status"] == "known"
        assert any("carries no date" in c for c in got["cautions"])

    def test_a_day_kept_without_a_price_compares_as_absent_with_its_reason(
            self, api):
        add(api, "DARK")
        assert api.save_metrics("DARK", {"fcf_ttm": 1_000_000}, None)["ok"]
        one = kept_seq(api, "DARK")
        two = kept_seq(api, "DARK")
        got = snapshots.compare(security("DARK"), journal(), [one, two],
                                bank.COMPARABLE_FIELDS)
        for p in got["price"]:
            assert p["status"] == "absent"
            assert "not on this snapshot's record" in p["reason"]
