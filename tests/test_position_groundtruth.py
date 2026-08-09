"""The position arithmetic against hand-derived truth.

Expected values are transcribed from tests/fixtures/positions/histories.json —
figures worked out on paper from a history stated in plain terms, never read
back out of this program. Deriving an expectation through the code proves only
that the code agrees with itself, which is what let three branches' worth of
arithmetic bugs survive in this layer.

Each history is one of the shapes that has produced a bug or sits next to one:
a class held that is not the class priced, a trim followed by a close, re-entry
including a purchase backdated before an earlier exit, specific-lot and
lot-spanning sales, an unpriced holding, four round trips in one name, the
boundary where an account reaches nothing, a same-day exit and re-entry, and
entries recorded at nothing.

Every figure here would fail silently if it were wrong. A wrong market value is
a plausible dollar amount; a wrong weight is a plausible percentage; and weight
feeds sizing and strategies bind to sizing, so these are wrong decisions rather
than wrong displays.
"""

import json
from pathlib import Path

import pytest

from engine import context, contract, dataview, portfolio, price_store, tickermap

FIXTURE = Path(__file__).parent / "fixtures" / "positions" / "histories.json"
GROUND = json.loads(FIXTURE.read_text(encoding="utf-8"))
HISTORIES = {h["id"]: h for h in GROUND["histories"]}
IDS = list(HISTORIES)


def stating(*keys) -> list[str]:
    """The histories that state one of these figures.

    Each test runs over exactly the histories that have an answer for it, so
    the test ids say which shapes cover what and a history that quietly stops
    stating a figure disappears from the run rather than passing empty.
    """
    out = [hid for hid, h in HISTORIES.items()
           if any(k in h for k in keys)
           or any(k in s for s in h["securities"] for k in keys)
           or any(k in s["expect"] for s in h["securities"] for k in keys)]
    assert out, f"no history states {keys}"
    return out


LOTS_REMAINING = stating("open_lots_remaining")
WRONG_ANSWERS = stating("must_not_be")
EXITS = stating("exit_scorecard")
OVERRIDES = stating("override_scorecard")
ACCOUNTS = [hid for hid, h in HISTORIES.items() if "account" in h]


# -- installing a history ----------------------------------------------------

def cash_record(name="Sizer"):
    """A strategy record shaped like the loader's output, declaring the one
    input that claims the cash role. Free cash is the only thing a strategy
    has to ask for, and it is what unlocks the account and every weight."""
    return {"id": "sizer", "name": name, "summary": "s", "version": 1,
            "contract": contract.CONTRACT_VERSION, "changelog": {1: "f"},
            "states": [], "values": [], "defaults": {},
            "inputs": [{"id": "free-cash", "label": "Free cash",
                        "type": "number", "unit": "usd", "role": "cash",
                        "explain": "Money not in a position."}]}


def install(history) -> list[dict]:
    """Write the history's securities into the stores exactly as a fetch
    would leave them, and return the journal's securities in order."""
    dataview.invalidate()
    tmap = tickermap.load_cached()
    out = []
    for spec in history["securities"]:
        cik = spec["cik"]
        for symbol in spec.get("maps_to_cik") or []:
            tmap.setdefault("map", {})[symbol] = {"cik": int(cik),
                                                  "title": spec["name"]}
        if spec.get("prices"):
            doc = price_store.load(cik)
            for symbol, rows in spec["prices"].items():
                price_store.merge_series(
                    doc, symbol, "test",
                    [[d, c, 100] for d, c in rows], [])
            price_store.save(cik, doc)
        out.append(security_of(spec, cik))
    tickermap._save(tmap)
    return out


def security_of(spec, cik=None) -> dict:
    """One security as the journal stores it. `manual_price` is the price a
    user typed — the only price for a security the SEC does not match, and the
    one nobody validated."""
    return {
        "ticker": spec["ticker"], "name": spec["name"],
        "cik": spec.get("cik", cik),
        "price": spec.get("manual_price"), "metrics": {}, "notes": [],
        "lot_seq": len(spec["lots"]),
        # An override is part of the lot as add_lot writes it: which kind it
        # was, and which cited figures came out against. The scorecards read
        # nothing else about it.
        "lots": [dict(l, snapshot=None,
                      **({"override": l.get("override")}
                         if l["kind"] == "buy" else {}))
                 for l in spec["lots"]],
    }



@pytest.fixture
def loaded(request):
    """(history, securities by ticker, securities in order)."""
    history = HISTORIES[request.param]
    secs = install(history)
    return history, {s["ticker"]: s for s in secs}, secs


def spec_of(history, ticker):
    return next(s for s in history["securities"] if s["ticker"] == ticker)


def price_of(sec):
    """The effective price of one security — the same read the screens and the
    scorecards use."""
    return dataview.price_view(sec, sec.get("cik"), sec["ticker"])["value"]


def expected(node):
    """The hand-derived value out of a {"value": ..., "how": ...} node."""
    return node["value"]


def built(history, secs, cash=None):
    """The context for the first security, with the journal behind it."""
    inputs = {} if cash is None else {"free-cash": cash}
    return context.build_context(secs[0], secs, {}, inputs,
                                 record=cash_record())


def cash_of(history):
    return history.get("cash")


# -- the lot arithmetic ------------------------------------------------------
# Pure reads over the lot list: no price store, no journal, no strategy. If a
# fixture belongs anywhere durable it belongs here — these answers are true
# whatever the layers above do with them.

@pytest.mark.parametrize("loaded", IDS, indirect=True)
def test_the_shape_of_the_position(loaded):
    """Shares held, what they cost, when the holding began, and which bucket
    the security is in — all derived from the lots on read."""
    history, by_ticker, _ = loaded
    for spec in history["securities"]:
        sec, want = by_ticker[spec["ticker"]], spec["expect"]
        where = f'{history["id"]}/{spec["ticker"]}'
        assert portfolio.shares_held(sec) == expected(want["shares_held"]), \
            f'{where} shares held — {want["shares_held"]["how"]}'
        assert portfolio.cost_basis(sec) == expected(want["cost_basis"]), \
            f'{where} cost basis — {want["cost_basis"]["how"]}'
        assert portfolio.opened_on(sec) == expected(want["opened_on"]), \
            f'{where} opened — {want["opened_on"]["how"]}'
        assert portfolio.bucket_of(sec) == expected(want["bucket"]), \
            f'{where} bucket — {want["bucket"]["how"]}'


@pytest.mark.parametrize("loaded", IDS, indirect=True)
def test_the_holding_periods_and_what_each_returned(loaded):
    """A name bought, closed and bought back is two trades, and each round
    trip has its own answer. A period opens where the position came up from
    nothing and closes where it went back to it — walked from the running
    total, so a backdated purchase that means the position never reached
    nothing is not two periods however it was entered."""
    history, by_ticker, _ = loaded
    for spec in history["securities"]:
        sec, want = by_ticker[spec["ticker"]], spec["expect"]
        where = f'{history["id"]}/{spec["ticker"]}'
        price = price_of(sec)
        got = portfolio.cycles(sec)
        assert len(got) == len(want["cycles"]), \
            f'{where} expected {len(want["cycles"])} holding periods, got ' \
            f'{[(c["opened"], c["closed"]) for c in got]}'
        for cycle, expect in zip(got, want["cycles"]):
            at = f'{where} period {expect["seq"]}'
            assert cycle["seq"] == expect["seq"], at
            assert cycle["opened"] == expect["opened"], f"{at} opened"
            assert cycle["closed"] == expect["closed"], f"{at} closed"
            assert cycle["open"] is expect["open"], f"{at} open"
            assert cycle["shares"] == expect["shares"], f"{at} shares"
            assert portfolio.cycle_return(sec, cycle, price) == \
                expect["return"]["value"], \
                f'{at} return — {expect["return"]["how"]}'


@pytest.mark.parametrize("loaded", IDS, indirect=True)
def test_what_each_purchase_returned_and_what_the_name_returned(loaded):
    """Per lot and over the security's whole life. The lifetime figure blends
    finished trades into a live one and is never the current position's
    return, which is why it is asserted apart from the period figures."""
    history, by_ticker, _ = loaded
    for spec in history["securities"]:
        sec, want = by_ticker[spec["ticker"]], spec["expect"]
        where = f'{history["id"]}/{spec["ticker"]}'
        price = price_of(sec)
        by_id = {l["id"]: l for l in portfolio.lots(sec, "buy")}
        for lot_id, expect in want["lot_returns"].items():
            assert portfolio.lot_return(sec, by_id[lot_id], price) == \
                expect["value"], \
                f'{where} lot {lot_id} — {expect["how"]}'
        assert portfolio.position_return(sec, price) == \
            expected(want["position_return"]), \
            f'{where} lifetime — {want["position_return"]["how"]}'


@pytest.mark.parametrize("loaded", IDS, indirect=True)
def test_what_each_sale_returned_and_what_happened_after_it(loaded):
    """Per sale, because the reason is given at the sale and a position
    trimmed on one reason then closed on another gave two answers. The window
    after a sale ends at the purchase that followed it — running it on to
    today would credit the sell rule with a stretch spent holding."""
    history, by_ticker, _ = loaded
    for spec in history["securities"]:
        sec, want = by_ticker[spec["ticker"]], spec["expect"]
        where = f'{history["id"]}/{spec["ticker"]}'
        price = price_of(sec)
        sales = {l["id"]: l for l in portfolio.lots(sec, "sell")}
        assert set(sales) == set(want["sales"]), f"{where} sales recorded"
        for sale_id, expect in want["sales"].items():
            at = f"{where} sale {sale_id}"
            sale = sales[sale_id]
            assert portfolio.sale_return(sec, sale) == \
                expect["sale_return"]["value"], \
                f'{at} return — {expect["sale_return"]["how"]}'
            after, wanted = portfolio.since_sale(sec, sale, price), \
                expect["since_sale"]
            assert after["pct"] == wanted["value"], \
                f'{at} since — {wanted["how"]}'
            assert after["until"] == wanted["until"], f"{at} window"
            assert after["date"] == wanted["date"], f"{at} window ends"
            if wanted.get("reason_mentions"):
                assert wanted["reason_mentions"] in (after["reason"] or ""), \
                    f'{at} absence must say why: {after["reason"]!r}'
            if wanted["value"] is not None:
                assert after["reason"] is None, at


@pytest.mark.parametrize("loaded", LOTS_REMAINING, indirect=True)
def test_what_is_left_of_each_purchase_and_where_a_sale_would_draw(loaded):
    """Only the histories that say. `remaining` is per lot and is the only
    thing a specific-lot sale can be checked against."""
    history, by_ticker, _ = loaded
    for spec in history["securities"]:
        want = spec["expect"]
        sec = by_ticker[spec["ticker"]]
        where = f'{history["id"]}/{spec["ticker"]}'
        left = {l["id"]: l["remaining"] for l in portfolio.open_lots(sec)}
        assert left == expected(want["open_lots_remaining"]), \
            f'{where} — {want["open_lots_remaining"]["how"]}'
        if "allocate_60_default" in want:
            assert portfolio.allocate(sec, 60) == \
                expected(want["allocate_60_default"]), \
                f'{where} — {want["allocate_60_default"]["how"]}'


# -- the money -------------------------------------------------------------
# Market value, the account total and every weight. These need the price store
# and the journal's answer about free cash, so they are read through the
# context — the same shape a strategy binds on.

@pytest.mark.parametrize("loaded", IDS, indirect=True)
def test_a_position_is_priced_from_the_security_actually_held(loaded):
    """The close that belongs to this instrument, named by the symbol it came
    from. Two share classes are two instruments at two prices; a sibling's
    close is not this security's price at any date, and where this one has no
    close the value is absent rather than borrowed."""
    history, by_ticker, _ = loaded
    for spec in history["securities"]:
        sec, want = by_ticker[spec["ticker"]], spec["expect"]["price"]
        where = f'{history["id"]}/{spec["ticker"]}'
        view = dataview.price_view(sec, sec["cik"], sec["ticker"])
        assert view["value"] == want["value"], f'{where} — {want["how"]}'
        assert view["date"] == want["date"], f"{where} price date"
        if want["value"] is not None:
            assert view["ticker"] == want["ticker"], \
                f'{where} the close must come from {want["ticker"]}'
        else:
            assert view.get("reason"), f"{where} absence must say why"


@pytest.mark.parametrize("loaded", ACCOUNTS, indirect=True)
def test_market_value_weight_and_the_account_total(loaded):
    """One unpriced holding makes the account absent rather than understating
    it: treating a missing price as zero would inflate every weight measured
    against it, in the number a sizing rule binds on."""
    history, _, secs = loaded
    cash = cash_of(history)
    want_account = history["account"]["value"]
    ctx = built(history, secs, cash)
    folio = ctx["portfolio"]

    if want_account["value"] is None:
        assert folio["account_value"]["status"] == "absent", \
            f'{history["id"]} account — {want_account["how"]}'
        for named in history["account"].get("reason_names") or []:
            assert named in folio["account_value"]["reason"], \
                f'{history["id"]} the absence must name {named}'
    else:
        assert folio["account_value"]["value"] == want_account["value"], \
            f'{history["id"]} account — {want_account["how"]}'

    holdings = {h["ticker"]: h for h in folio["holdings"]}
    for spec in history["securities"]:
        want, where = spec["expect"], f'{history["id"]}/{spec["ticker"]}'
        held = holdings.get(spec["ticker"])
        if expected(want["market_value"]) is None and \
                expected(want["shares_held"]) == 0:
            assert held is None, f"{where} holds nothing and is not a holding"
            continue
        assert held is not None, f"{where} should be a holding"
        for figure in ("market_value", "weight"):
            node, wanted = held.get(figure) if figure in held else None, \
                want[figure]
            if figure == "weight" and node is None:
                node = held["weight"]
            if wanted["value"] is None:
                assert node["status"] == "absent", \
                    f'{where} {figure} — {wanted["how"]}'
                assert node["reason"], f"{where} {figure} absence says why"
            else:
                assert node["status"] == "known", \
                    f'{where} {figure} — {wanted["how"]}: ' \
                    f'{node.get("reason")}'
                assert round(node["value"], 6) == round(wanted["value"], 6), \
                    f'{where} {figure} — {wanted["how"]}'


@pytest.mark.parametrize("loaded", WRONG_ANSWERS, indirect=True)
def test_the_answer_the_defect_gives_is_not_the_answer(loaded):
    """Every figure a history states a wrong answer for. These are the numbers
    the code gave, or would give, with the defect the history was built for
    present — a passing assertion here is the proof the defect is gone, not a
    rounding preference."""
    history, by_ticker, secs = loaded
    reject = {}
    for spec in history["securities"]:
        if spec.get("must_not_be"):
            reject[spec["ticker"]] = spec["must_not_be"]

    ctx = built(history, secs, cash_of(history))
    holdings = {h["ticker"]: h for h in ctx["portfolio"]["holdings"]}

    account_wrong = (history.get("account") or {}).get("must_not_be")
    if account_wrong:
        node = ctx["portfolio"]["account_value"]
        assert node.get("value") != account_wrong["value"], \
            f'{history["id"]} account is the wrong answer — ' \
            f'{account_wrong["how"]}'

    for ticker, wrong in reject.items():
        sec = by_ticker[ticker]
        where = f'{history["id"]}/{ticker}'
        price = price_of(sec)
        held = holdings.get(ticker)
        by_id = {l["id"]: l for l in portfolio.lots(sec, "buy")}
        sales = {l["id"]: l for l in portfolio.lots(sec, "sell")}
        for figure, bad in wrong.items():
            got, how = None, bad["how"]
            if figure == "market_value":
                got = (held or {}).get("market_value", {}).get("value")
            elif figure == "weight":
                got = (held or {}).get("weight", {}).get("value")
            elif figure == "position_return":
                got = portfolio.position_return(sec, price)
            elif figure == "opened_on":
                got = portfolio.opened_on(sec)
            elif figure == "cycle_count":
                got = len(portfolio.cycles(sec))
            elif figure == "price_ticker":
                got = dataview.price_view(sec, sec["cik"],
                                          sec["ticker"]).get("ticker")
            elif figure.startswith("lot_return_"):
                got = portfolio.lot_return(sec, by_id[figure[11:]], price)
            elif figure.startswith("sale_return_"):
                got = portfolio.sale_return(sec, sales[figure[12:]])
            elif figure.startswith("since_sale_"):
                got = portfolio.since_sale(sec, sales[figure[11:]],
                                           price)["pct"]
            else:
                raise AssertionError(f"{where}: no reader for {figure}")
            assert got != bad["value"], f"{where} {figure} — {how}"


# -- the scorecards ----------------------------------------------------------

@pytest.mark.parametrize("loaded", EXITS, indirect=True)
def test_the_exit_scorecard_groups_sales_by_reason(loaded):
    """Grouped per sale, not per holding period: a position trimmed on a risk
    limit and closed on a broken thesis gave two answers a per-period figure
    would have to pick between. Each average says what it rests on, because
    an average of one beside a count of three would let absence pass for a
    settled answer."""
    history, _, secs = loaded
    got = portfolio.exit_scorecard(secs, price_of)
    want = history["exit_scorecard"]
    assert set(got) == set(want), f'{history["id"]} exit reasons grouped'
    for reason, expect in want.items():
        at = f'{history["id"]} exit "{reason}"'
        for figure in ("n", "n_held", "n_after", "avg_held", "avg_after",
                       "bought_again"):
            assert got[reason][figure] == expect[figure], \
                f'{at} {figure} — {expect.get("how", "")}'


@pytest.mark.parametrize("loaded", OVERRIDES, indirect=True)
def test_the_override_scorecard_counts_purchases(loaded):
    """Counted per lot, not per security: with several buys in one name, one
    can be a compliant entry and the next an override, and collapsing them
    loses exactly the comparison the scorecard exists to make."""
    history, _, secs = loaded
    got = portfolio.override_scorecard(secs, price_of)
    for group, expect in history["override_scorecard"].items():
        at = f'{history["id"]} {group}'
        for figure in ("n", "n_purchases", "n_unscored", "win_rate", "avg"):
            assert got[group][figure] == expect[figure], \
                f'{at} {figure} — {expect.get("how", "")}'
        # The two populations must never be reported as one: a win rate over
        # the purchases that could be priced, beside a count of every purchase,
        # is a data gap reading as a settled result — in the panel whose whole
        # job is to be able to indict a rule rather than the person.
        assert got[group]["n"] + got[group]["n_unscored"] == \
            got[group]["n_purchases"], at

    if "kinds" in history:
        for kind, n in history["kinds"].items():
            if kind != "how":
                assert got["kinds"][kind] == n, \
                    f'{history["id"]} {kind} — {history["kinds"]["how"]}'

    for key, expect in (history.get("per_rule") or {}).items():
        bucket = got["per_rule"].get(key)
        assert bucket is not None, \
            f'{history["id"]} the rule {key} is missing from the panel'
        for figure in ("label", "n", "n_scored", "wins", "avg"):
            assert bucket[figure] == expect[figure], \
                f'{history["id"]} {key} {figure} — {expect["how"]}'
        wrong = (history.get("must_not_be") or {}).get("per_rule_n")
        if wrong:
            assert bucket["n"] != wrong["value"], \
                f'{history["id"]} {key} — {wrong["how"]}'


# -- the account boundary ----------------------------------------------------

def test_cash_of_nothing_is_an_answer_and_an_account_of_nothing_is_not():
    """The three cases that collapse into each other if anything treats
    absence as zero. Nothing in cash is a stated answer and the account is
    then the holdings alone. An account that works out to nothing has no
    share of it to express — not a division by zero, not 0%, and not a
    clamped 100%. An unanswered question is absent for its own reason."""
    history = HISTORIES["zero-and-negative-cash"]
    secs = install(history)
    spec = history["securities"][0]
    market_value = expected(spec["expect"]["market_value"])

    for case in history["cash_cases"]:
        ctx = built(history, secs, case["cash"])
        account = ctx["portfolio"]["account_value"]
        weight = ctx["position"]["weight"]
        at = f'free cash {case["cash"]!r} — {case["how"]}'

        if case["cash"] is None:
            assert ctx["portfolio"]["cash"]["status"] == "absent", at
        else:
            assert ctx["portfolio"]["cash"]["status"] == "known", at
            assert ctx["portfolio"]["cash"]["value"] == case["cash"], at

        if case["account"] is None:
            assert account["status"] == "absent", at
            assert case["account_reason_mentions"] in account["reason"], at
        else:
            assert account["status"] == "known", at
            assert account["value"] == case["account"], at

        if case["weight"] is None:
            assert weight["status"] == "absent", at
            assert weight["reason"], f"{at}: the absence must say why"
        else:
            assert weight["status"] == "known", f'{at}: {weight.get("reason")}'
            assert weight["value"] == case["weight"], at

        assert ctx["position"]["market_value"]["value"] == market_value, \
            f"{at}: what the holding is worth does not depend on the cash"


def test_the_account_absence_says_which_question_it_is_about():
    """An account absent because a price is missing and one absent because
    the cash question was never answered are different problems with
    different fixes, and the reason has to say which."""
    unpriced = HISTORIES["an-unpriced-holding-darkens-the-account"]
    secs = install(unpriced)
    reason = built(unpriced, secs, 800.0)["portfolio"]["account_value"]["reason"]
    assert "DRAY" in reason and "no price" in reason
    assert "free cash" not in reason

    secs = install(HISTORIES["zero-and-negative-cash"])
    reason = built(HISTORIES["zero-and-negative-cash"], secs,
                   None)["portfolio"]["account_value"]["reason"]
    assert "free cash" in reason


# -- the prices that are not prices ------------------------------------------

def test_a_price_of_nothing_on_record_is_refused_rather_than_served():
    """Zero is not a price the market set. Served as one it produces a $0
    market value, a 0% weight and a -100% on every open share — four settled
    answers built on a claim nobody made. Refused on read as well as at the
    field, because a journal written before the field refused it must not
    still read as a fact."""
    history = HISTORIES["a-price-entered-by-hand"]
    install(history)
    spec = history["refused_price"]
    sec = security_of(spec, cik=None)

    view = dataview.price_view(sec, None, sec["ticker"])
    assert view["value"] is None, spec["how"]
    assert spec["price"]["reason_mentions"] in view["reason"], view["reason"]

    lot = portfolio.lots(sec, "buy")[0]
    got = portfolio.lot_return(sec, lot, view["value"])
    assert got is None, spec["lot_return"]["how"]
    assert got != spec["must_not_be"]["lot_return"]["value"]

    # And again with the zero handed straight to the arithmetic rather than
    # arriving as an absence. Both layers refuse it: a zero reaching the
    # second one from anywhere would mark every open share at nothing and
    # report a confident total loss on a position nobody has valued.
    direct = spec["lot_return_asked_at_zero"]
    for reaching in (0.0, -3.0):
        assert portfolio.lot_return(sec, lot, reaching) is None, direct["how"]
        assert portfolio.cycle_return(sec, portfolio.cycles(sec)[0],
                                      reaching) is None, direct["how"]
        assert portfolio.position_return(sec, reaching) is None, direct["how"]

    ctx = context.build_context(sec, [sec], {}, {"free-cash": 500.0},
                                record=cash_record())
    value = ctx["position"]["market_value"]
    assert value["status"] == "absent", spec["market_value"]["how"]
    assert value.get("value") != spec["must_not_be"]["market_value"]["value"]
    assert ctx["portfolio"]["account_value"]["status"] == "absent", \
        "an unpriceable holding darkens the account, however it lost its price"


def test_the_field_refuses_a_price_of_nothing_at_the_door(strategies):
    """The structural half. Refusing on read keeps an old journal honest;
    refusing at the field is what stops one being written. Blank stays the way
    to say you have no price, because that is a different statement."""
    from conftest import journal_for

    from app import Api
    strategies("sound")
    journal_for("sound")
    api = Api()
    api.add_security("VSKR", "Vasker Minerals")

    for refused in (0, "0", -4.5, "-4.5"):
        result = api.save_metrics("VSKR", {}, refused)
        assert result["ok"] is False, f"a price of {refused!r} was accepted"
        assert "more than zero" in result["error"]
        assert "blank" in result["error"], "the message has to say the way out"

    assert api.save_metrics("VSKR", {}, "")["ok"] is True
    assert api.save_metrics("VSKR", {}, 18.0)["ok"] is True


def test_since_sale_says_which_thing_ended_the_window():
    """Two different things end a window and the reason has to say which.
    Naming a purchase when the window runs to today points at an entry the
    user never made, and sends them looking for it."""
    history = HISTORIES["recorded-at-nothing"]
    secs = install(history)
    case = history["since_sale_at_no_price"]
    sec = next(s for s in secs if s["ticker"] == case["security"])
    sale = next(l for l in portfolio.lots(sec, "sell")
                if l["id"] == case["sale"])

    after = portfolio.since_sale(sec, sale, case["price"])
    assert after["pct"] is None, case["how"]
    assert after["until"] == "today"
    assert case["reason_mentions"] in after["reason"], after["reason"]
    assert case["must_not_mention"] not in after["reason"], after["reason"]
