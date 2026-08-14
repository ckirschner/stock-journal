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


def lot_of(spec) -> dict:
    """One lot as add_lot and sell_lots write it.

    The snapshot is stripped to the one thing the figures below read off it:
    whether this entry's verdict was seen on the day it is dated or rebuilt
    for that day afterwards. That is not decoration on a lot — it decides
    which cohort a purchase is counted in, whether an exit's reason reads as
    one somebody gave at the time, and whether going ahead was an override at
    all. A fixture that could not state it could not cover any of that.

    `basis` defaults to live, exactly as the write does, so every history
    written before backfill existed keeps meaning what it meant.
    """
    lot = dict(spec, snapshot={"evaluation": {
        "basis": spec.get("basis", "live"),
        "as_of": spec.get("as_of", spec["date"])}})
    lot.pop("basis", None)
    lot.pop("as_of", None)
    if spec["kind"] == "buy":
        # An override is part of the lot as add_lot writes it: which kind it
        # was, and which cited figures came out against. Beside it, and never
        # merged with it, an entry whose verdict could not be rebuilt at all.
        # The scorecards read nothing else about either.
        lot["override"] = spec.get("override")
        lot["unreconstructed"] = spec.get("unreconstructed")
    return lot


def security_of(spec, cik=None) -> dict:
    """One security as the journal stores it. `manual_price` is the price a
    user typed — the only price for a security the SEC does not match, and the
    one nobody validated."""
    return {
        "ticker": spec["ticker"], "name": spec["name"],
        "cik": spec.get("cik", cik),
        "price": spec.get("manual_price"), "notes": [],
        "lot_seq": len(spec["lots"]),
        "lots": [lot_of(l) for l in spec["lots"]],
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
    scorecards use.

    The whole view, not the number out of it. Every return below is worked
    out from this, and a return that cannot be worked out has to say why —
    the host's own sentence about the price is the honest reason, and it can
    only be the reason if the number never travels without it.
    """
    return dataview.price_view(sec, sec.get("cik"), sec["ticker"])


def figure(node, where=""):
    """A host figure's value, or None where it is absent — and an absence
    that says nothing is a failure here rather than a None passed along.

    Five different facts used to come back as one bare None: nobody has
    fetched a price, the figure on record is not a price, this purchase was
    recorded at nothing, one purchase of several was, the security was never
    bought. They have different fixes, so they are different answers.
    """
    # The shape itself is the guarantee, so a bare number is a failure here
    # rather than something to pass along. A return that went back to being
    # `float | None` would slip through a helper that shrugged and returned
    # it, and every assertion below would still read as green — which is the
    # exact way a suite stops proving the thing it was written for.
    assert isinstance(node, dict) and node.get("status") in ("known",
                                                             "absent"), \
        f"{where}: a host figure is {{status, value}} or {{status, reason}}, " \
        f"not {node!r}"
    if node["status"] == "absent":
        assert str(node.get("reason") or "").strip(), \
            f"{where}: an absence with no reason is indistinguishable from " \
            "a failure"
        return None
    return node.get("value")


def expected(node):
    """The hand-derived value out of a {"value": ..., "how": ...} node."""
    return node["value"]


def built(history, secs, cash=None):
    """The context for the first security, with the journal behind it.

    Free cash is not an answer this can supply — it is worked out from the
    journal's cash record — so a fixture that states an account balance opens
    a record at it. Which is the honest shape anyway: a hand-read account
    total rests on the cash actually being there on the day.
    """
    import conftest
    doc = conftest.cash_record(cash)
    return context.build_context(secs[0], secs, {}, {},
                                 record=cash_record(), journal=doc)


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
            assert figure(portfolio.cycle_return(sec, cycle, price), at) == \
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
            at = f"{where} lot {lot_id}"
            assert figure(portfolio.lot_return(sec, by_id[lot_id], price),
                          at) == expect["value"], \
                f'{at} — {expect["how"]}'
        assert figure(portfolio.position_return(sec, price), where) == \
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
            assert figure(portfolio.sale_return(sec, sale), at) == \
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
        for name, bad in wrong.items():
            got, how = None, bad["how"]
            if name == "market_value":
                got = (held or {}).get("market_value", {}).get("value")
            elif name == "weight":
                got = (held or {}).get("weight", {}).get("value")
            elif name == "position_return":
                got = figure(portfolio.position_return(sec, price))
            elif name == "opened_on":
                got = portfolio.opened_on(sec)
            elif name == "cycle_count":
                got = len(portfolio.cycles(sec))
            elif name == "price_ticker":
                got = dataview.price_view(sec, sec["cik"],
                                          sec["ticker"]).get("ticker")
            elif name.startswith("lot_return_"):
                got = figure(portfolio.lot_return(sec, by_id[name[11:]],
                                                  price))
            elif name.startswith("sale_return_"):
                got = figure(portfolio.sale_return(sec, sales[name[12:]]))
            elif name.startswith("since_sale_"):
                got = portfolio.since_sale(sec, sales[name[11:]],
                                           price)["pct"]
            else:
                raise AssertionError(f"{where}: no reader for {name}")
            assert got != bad["value"], f"{where} {name} — {how}"


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
                       "bought_again", "n_reconstructed"):
            assert got[reason][figure] == expect[figure], \
                f'{at} {figure} — {expect.get("how", "")}'


@pytest.mark.parametrize("loaded", OVERRIDES, indirect=True)
def test_the_override_scorecard_counts_purchases(loaded):
    """Counted per lot, not per security: with several buys in one name, one
    can be a compliant entry and the next an override, and collapsing them
    loses exactly the comparison the scorecard exists to make.

    Counted per cohort as well. A decision seen on the screen and a decision
    rebuilt for a day in the past are not evidence about the same thing, and a
    journal with a decade of history typed into it would answer "did
    overriding help" almost entirely with the second while labelling it the
    first.
    """
    history, _, secs = loaded
    got = portfolio.override_scorecard(secs, price_of)
    for cohort, groups in history["override_scorecard"].items():
        for group, expect in groups.items():
            at = f'{history["id"]} {cohort}/{group}'
            for figure in ("n", "n_purchases", "n_unscored", "win_rate",
                           "avg"):
                assert got[cohort][group][figure] == expect[figure], \
                    f'{at} {figure} — {expect.get("how", "")}'
            # The two populations must never be reported as one: a win rate
            # over the purchases that could be priced, beside a count of every
            # purchase, is a data gap reading as a settled result — in the
            # panel whose whole job is to be able to indict a rule rather than
            # the person.
            assert got[cohort][group]["n"] + got[cohort][group]["n_unscored"] \
                == got[cohort][group]["n_purchases"], at

    # Purchases nobody could rebuild a verdict for are in neither comparison.
    # Stated as its own figure rather than inferred from the two above, because
    # "it is not in either" is exactly the claim that would break silently.
    dark = history.get("unreconstructed")
    if dark:
        for figure in ("n", "n_purchases", "n_unscored", "win_rate", "avg"):
            assert got["unreconstructed"][figure] == dark[figure], \
                f'{history["id"]} unreconstructed {figure} — {dark["how"]}'
    if "kinds" in history:
        for cohort, kinds in history["kinds"].items():
            for kind, n in kinds.items():
                if kind != "how":
                    assert got[cohort]["kinds"][kind] == n, \
                        f'{history["id"]} {cohort} {kind} — ' \
                        f'{kinds.get("how", "")}'

    for cohort, rules in (history.get("per_rule") or {}).items():
        for key, expect in rules.items():
            bucket = got[cohort]["per_rule"].get(key)
            assert bucket is not None, \
                f'{history["id"]} the rule {key} is missing from {cohort}'
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
    got = portfolio.lot_return(sec, lot, view)
    assert figure(got) is None, spec["lot_return"]["how"]
    assert figure(got) != spec["must_not_be"]["lot_return"]["value"]
    # And the absence carries the host's OWN sentence about the price rather
    # than a weaker one invented here. That is the whole reason the price
    # travels as a view: a return that cannot be worked out because of the
    # price should say exactly what the price screen says.
    assert view["reason"] in got["reason"], got["reason"]

    # And again with the zero handed straight to the arithmetic rather than
    # arriving as an absence. Both layers refuse it: a zero reaching the
    # second one from anywhere would mark every open share at nothing and
    # report a confident total loss on a position nobody has valued.
    direct = spec["lot_return_asked_at_zero"]
    for reaching in (0.0, -3.0):
        assert figure(portfolio.lot_return(sec, lot, reaching)) is None, \
            direct["how"]
        assert figure(portfolio.cycle_return(sec, portfolio.cycles(sec)[0],
                                             reaching)) is None, direct["how"]
        assert figure(portfolio.position_return(sec, reaching)) is None, \
            direct["how"]

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


def test_the_frozen_record_says_which_instrument_its_price_belonged_to():
    """A record that says only "$470" cannot afterwards be told from one that
    should have said $705,000. This record is append-only and never
    recomputed, so anything it cannot say now it can never be asked later."""
    history = HISTORIES["class-held-is-not-class-priced"]
    secs = install(history)
    sec = secs[0]
    want = spec_of(history, "NWND.B")["expect"]["price"]

    seen = dataview.price_view(sec, sec["cik"], sec["ticker"])
    lot = portfolio.add_lot(sec, None, 20, 400.0, "2026-08-08",
                            override_reason="testing the record",
                            price_seen=seen)
    snapshot = lot["snapshot"]
    assert snapshot["price"] == want["value"]
    assert snapshot["price_ticker"] == want["ticker"]
    assert snapshot["price_date"] == want["date"]
    wrong = spec_of(history, "NWND.B")["must_not_be"]["price_ticker"]
    assert snapshot["price_ticker"] != wrong["value"], wrong["how"]


@pytest.mark.parametrize("loaded", IDS, indirect=True)
def test_how_a_holding_period_ended_across_every_sale_that_closed_it(loaded):
    """A period closed in stages ended at more than one price, on more than
    one day, for more than one stated reason — and it was described by the
    last sale alone.

    Sell 40 of 100 at $30 on a valuation call and the remaining 60 at $15 on
    a broken thesis, and the record called $15 the exit price and "Thesis
    broke" the exit reason. $15 is what one sliver got; the holding got
    $21.00 a share. Worse, the same strip carried a return computed from
    both sales, so the card contradicted its own arithmetic and left the
    reader to work out which half to believe.

    Three separate answers, and they belong to different questions:
      - the PRICE is share-weighted across every closing sale;
      - the DATE is the last sale's, because that is when nothing was held;
      - the REASONS are all of them, each carrying the shares it covers.
    """
    history, by_ticker, _ = loaded
    for spec in history["securities"]:
        sec = by_ticker[spec["ticker"]]
        for cycle, expect in zip(portfolio.cycles(sec),
                                 spec["expect"]["cycles"]):
            got = portfolio.cycle_exit(sec, cycle)
            at = f'{history["id"]}/{spec["ticker"]} period {expect["seq"]}'
            if "exit" not in expect:
                assert got is None, f"{at}: an open period has no exit"
                continue
            want = expect["exit"]
            assert got["date"] == want["date"] == cycle["closed"], \
                f'{at} — {want["how"]}'
            assert got["sales"] == want["sales"], f"{at} sales"
            assert got["shares"] == want["shares"], f"{at} shares"
            assert figure(got["price"], at) == want["price"]["value"], \
                f'{at} exit price — {want["price"]["how"]}'
            assert got["reasons"] == want["reasons"], \
                f'{at} every reason given, not one of them'


def test_a_staged_exit_is_not_described_by_its_smallest_sale():
    """The motivating case, at its worst. Ninety shares leave at $150 and
    the last ten at $55: the holding realised $140.50 a share, and reporting
    $55 describes a tenth of it as though it were the whole.

    Worked out on paper: 90 x 150.00 = 13,500.00 plus 10 x 55.00 = 550.00 is
    14,050.00 over 100 shares, so $140.50.
    """
    sec = portfolio.new_security("STGD", "Staged Exit Co")
    decision = {"render": "commit", "tier": "position",
                "state": {"id": "buy", "name": "Buy"},
                "reason": {"rule": "r", "summary": "s", "evidence": []}}
    portfolio.add_lot(sec, decision, 100, 100.0, "2025-01-06")
    portfolio.sell_lots(sec, None, "Hit valuation", 90, 150.0, "2025-06-10")
    portfolio.sell_lots(sec, None, "Thesis broke", 10, 55.0, "2025-11-10")

    [period] = portfolio.cycles(sec)
    got = portfolio.cycle_exit(sec, period)
    assert got["price"]["value"] == 140.5
    assert got["price"]["value"] != 55.0, "the last sliver is not the exit"
    assert got["date"] == "2025-11-10", "when nothing was left"
    assert [r["reason"] for r in got["reasons"]] == ["Hit valuation",
                                                     "Thesis broke"]
    assert [r["share"] for r in got["reasons"]] == [90.0, 10.0]
    # The per-sale figures the exit scorecard groups by are untouched: it was
    # already right, and the two panels now agree about the same exit instead
    # of one of them quietly describing a tenth of it.
    a, b = portfolio.lots(sec, "sell")
    assert figure(portfolio.sale_return(sec, a)) == 50.0
    assert figure(portfolio.sale_return(sec, b)) == -45.0
