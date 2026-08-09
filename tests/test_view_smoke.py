"""One executing path through the view layer.

The view carries real logic — which screen renders, what a state's payload
says, whether a figure that could not be read renders as absence or as a
confident zero — and until now the standard for it was "correct by
inspection", which is the standard that produced the defects the Python-side
reviews caught.

This is deliberately one smoke path rather than a testing framework. It
builds a real journal through the same Api the window calls, hands the
resulting state to ui/app.js under a stub DOM, and renders every screen. It
catches a key renamed on the Python side, an undefined dereference in a
branch nobody clicked, a number that reaches the screen as NaN, and a
section that silently disappears. It says nothing about how any of it looks.

The journal it builds runs on the awkward fixture on purpose: a strategy
declaring a role, a fixed set of answers and two levels of gating is what
puts real content on the settings screen, and a strategy that binds on
position weight is what makes the account arithmetic reach the page at all.

Skipped where Node is not installed: a machine without it can still run
everything else, and a test that cannot run must say so rather than pass.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import balance_face, dur, filing, inst

from engine import facts_store, journals, price_store, strategy_loader

import app as app_mod

UI = Path(__file__).resolve().parent.parent / "ui" / "app.js"
HARNESS = Path(__file__).resolve().parent / "view_smoke.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="Node is not installed on this machine")

ANSWERS = {"free-cash": "40000", "stance": "building",
           "keeps-reserve": "true", "reserve": "5000", "first-buy": "4"}


def _company(cik, ticker="ACME"):
    """Two years of filings, so a measure has a current value and a dated
    series, and the price panel has a close to show."""
    for yr, cfo in ((2024, 5_000_000), (2025, 1_200_000)):
        end = f"{yr}-12-31"
        facts = balance_face(end, extra=[
            inst("us-gaap:AssetsCurrent", end, 200),
            inst("us-gaap:LiabilitiesCurrent", end, 100)])
        facts += [
            dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                f"{yr}-01-01", end, cfo, stmt="CashFlow"),
            dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                f"{yr}-01-01", end, 1_000_000, stmt="CashFlow")]
        facts_store.save_filing(cik, filing(f"A-{yr}", "10-K",
                                            f"{yr + 1}-02-20", end, facts))
    doc = price_store.load(cik)
    price_store.merge_series(doc, ticker, "tiingo",
                             [["2026-08-01", 20.0, 1000]], [])
    price_store.save(cik, doc)


def _state(strategies, answers=ANSWERS) -> dict:
    """A journal exercising every branch the screens have: a holding built
    from two lots and trimmed by a partial sale, one lot bought against the
    signal, a name held twice — closed and bought back — a name closed and
    left closed, an idea, an expected-value record, a note, a second journal
    to switch to, and a rule change owed a reason.

    The two-holdings case earns its place here rather than in a fixture of
    its own: the previous-holdings table, the period grouping in the lot
    history and every "which holding is this" line only render when a
    security has more than one, and until they did the harness rendered the
    closed-position screen against nothing at all.
    """
    strategies("awkward")
    api = app_mod.Api()
    created = api.create_journal("Long-term ideas", "awkward", dict(answers))
    assert created["ok"], created

    cik = 611
    _company(cik)
    api.add_security("ACME", "Acme Widgets")
    api.add_security("BRDG", "Bridgeworks")
    api.add_security("RVER", "Riverbend Tools")
    api.add_security("CLSD", "Clearsted Mills")
    doc = journals.load(journals.resolve_open())
    doc["securities"][0]["cik"] = cik
    journals.save(doc)

    # Two lots and a trim: the lot history, the per-lot return and the
    # partial-sale path all have something to render.
    preview = api.preview_purchase("ACME")
    assert api.open_position("ACME", 10, 18.0, "2026-07-01", "",
                             preview["decision"]["state"]["id"])["ok"]
    assert api.open_position("ACME", 10, 22.0, None,
                             "adding against the signal")["ok"]
    assert api.sell_shares("ACME", "Risk limit", 25.0, None, 4)["ok"]

    # Priced by hand: neither has filings, and an unpriced holding rightly
    # makes the account total absent, which would take the weight arithmetic
    # below down with it.
    assert api.save_metrics("RVER", {}, 15.0)["ok"]
    assert api.save_metrics("CLSD", {}, 27.0)["ok"]

    # Held, closed, bought back: two holding periods on one security, so the
    # previous table has a row whose name also sits under current holdings.
    assert api.open_position("RVER", 20, 10.0, "2026-01-05", "why not")["ok"]
    assert api.sell_shares("RVER", "Hit valuation", 16.0, "2026-04-05")["ok"]
    assert api.open_position("RVER", 12, 21.0, "2026-06-01", "back in")["ok"]

    # Closed and left closed, so the one-period previous screen renders too.
    assert api.open_position("CLSD", 5, 30.0, "2026-02-02", "a reason")["ok"]
    assert api.sell_shares("CLSD", "Panic", 24.0, "2026-05-02")["ok"]

    api.compute_ev("ACME", "reverse_dcf",
                   {"price": 20, "fcf_ttm": 4, "shares": 10,
                    "discount_rate": 9, "terminal_growth": 2.5},
                   {"price": {"used": "fetched", "asof": "2026-08-01"}})
    api.add_note("BRDG", "watching this one")

    record = strategy_loader.discover()[0]["awkward"]
    journals.create("Small caps", record)

    # A retuned setting, through the same surface the user would use, so the
    # rule-change record and the answers record both have an entry.
    assert api.save_journal_settings(None, {"cap": "12"})["ok"]

    state = api.get_state()
    assert state["ok"], state
    return state


def _render(state, tmp_path):
    payload = tmp_path / "state.json"
    payload.write_text(json.dumps(state), encoding="utf-8")
    return subprocess.run(["node", str(HARNESS), str(payload), str(UI)],
                          capture_output=True, text=True, timeout=120)


def test_every_screen_renders(strategies, tmp_path):
    state = _state(strategies)
    assert state["journal"], "the harness built no journal to render"
    assert state["securities"], "the harness built no securities to render"
    assert state["pending_changes"], "the rule-change banner has nothing to say"
    assert state["input_changes"] == [], "no answer was edited by this path"

    r = _render(state, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_blocked_journal_offers_the_way_out(strategies, tmp_path):
    """A strategy version that adds a required input puts every journal
    stamped with it into "Waiting on setup". With nothing to click that is a
    trap: the host names the screen that resolves its own state, and the
    view has to render a way in.

    The journal is created answered and then has the answer taken away,
    because that is what the gap looks like from the journal's side — a
    field the record never had, demanded by a strategy that has moved on.
    """
    _state(strategies)
    doc = journals.load(journals.resolve_open())
    doc["inputs"].pop("free-cash")
    journals.save(doc)

    state = app_mod.Api().get_state()
    assert state["ok"], state
    held = [s for s in state["securities"] if s["bucket"] == "holdings"][0]
    d = held["_decision"]
    assert d["state"]["id"] == "host:inputs-missing", d["state"]
    assert d["state"]["fix"] == "settings"
    assert any("Free cash" in n for n in d["payload"]["needs"])
    assert any("Free cash" in p for p in state["strategy"]["input_problems"])

    # The harness asserts the way out is on the page: every state the host
    # says has a screen behind it must render the button that opens it.
    r = _render(state, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr

    # ...and supplying it in the app resolves the block, which is the half
    # that makes the button worth rendering.
    api = app_mod.Api()
    assert api.save_journal_settings({"free-cash": "40000"}, None)["ok"]
    again = api.get_state()
    held = [s for s in again["securities"] if s["bucket"] == "holdings"][0]
    assert held["_decision"]["produced_by"] == "strategy"
    assert again["input_changes"][-1]["moved"][0]["id"] == "free-cash"


def test_weight_reaches_the_screen_once_the_account_is_known(strategies):
    """The whole point of the journal-level inputs: a strategy that binds on
    position size can be written, and the figure it binds on is a fact the
    host reports with its own reason when it cannot."""
    state = _state(strategies)
    held = [s for s in state["securities"] if s["bucket"] == "holdings"][0]
    cited = {e["subject"]["id"]: e
             for e in held["_decision"]["reason"]["evidence"]}
    weight = cited["position.weight"]["observed"]
    assert weight["status"] == "known", weight
    # ACME: 16 shares at the 20.00 close is 320. RVER: 12 shares at the 15.00
    # hand-entered price is 180. CLSD is closed and holds nothing. Against
    # 40,000 of free cash that is an account of 40,500.
    assert cited["portfolio.account_value"]["observed"]["value"] == 40500.0
    assert round(weight["value"], 4) == round(320 / 40500 * 100, 4)


def test_returns_and_scorecards_use_the_fetched_price(strategies):
    """The effective price is hand-entered over the fetched close. Reading
    only the hand-entered field would make every position priced by a fetch
    show "—" for its return and drop silently out of the analytics that judge
    the rules — a whole portfolio's worth of evidence missing, with nothing
    on screen saying so."""
    state = _state(strategies)
    held = [s for s in state["securities"] if s["bucket"] == "holdings"]
    assert held, "the harness built no holding"
    s = held[0]
    assert s["price"] is None, "this test needs a fetch-priced position"
    assert s["_price"]["source"] == "fetched"
    assert s["_return"] is not None, \
        "a fetch-priced position reported no return"
    # …and it reaches the analytics, not just the row. Five purchases were
    # recorded here — two of ACME, two of RVER either side of its exit, one
    # of CLSD — and every one of them has to be in the count, whichever side
    # of the override line it fell on. A purchase that drops out because the
    # price behind its return came from a fetch is evidence lost silently.
    card = state["override_scorecard"]
    assert card["override"]["n"] + card["compliant"]["n"] == 5


def test_the_payload_scores_the_holding_you_have_not_the_ticker(strategies):
    """The regression this whole change exists to stop, pinned on the value
    rather than on its presence.

    RVER was bought at 10, closed at 16, and bought back at 21. It is now 12
    shares that cost 252 and are worth 12 x 15 = 180, which is −28.57%. That
    is what the holdings row says "Since buy" about. The ticker's lifetime
    figure is a different number — 200 of cost returning +60% and 252 of cost
    returning −28.57%, so (120 − 72) / 452 = +10.62% — and it is a different
    field, because the day those two share a column is the day a position
    down nearly thirty per cent reads as up ten.
    """
    state = _state(strategies)
    s = [x for x in state["securities"] if x["ticker"] == "RVER"][0]
    assert s["bucket"] == "holdings"
    assert s["_return"] == -28.57
    assert s["_lifetime_return"] == 10.62

    first, second = s["_cycles"]
    assert (first["opened"], first["closed"], first["open"]) == \
        ("2026-01-05", "2026-04-05", False)
    assert first["return"] == 60.0
    assert (second["opened"], second["closed"], second["open"]) == \
        ("2026-06-01", None, True)
    assert second["return"] == -28.57

    # …and the window on the closed one stops where the user bought again,
    # at the price they paid, rather than running on to today's 15.00.
    assert first["since_exit"] == {
        "until": "purchase", "date": "2026-06-01", "price": 21.0,
        "reason": None, "pct": 31.25}
    # sold at 16 having bought at 10; today's price is nowhere in it
    assert state["exit_scorecard"]["Hit valuation"]["avg_after"] == 31.2
    assert state["exit_scorecard"]["Hit valuation"]["bought_again"] == 1
