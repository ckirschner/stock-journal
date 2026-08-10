"""Builds data.template/sample.json — the demonstration journal.

Every company and every figure below is invented. Nothing here is a
recommendation, a model portfolio, or a real security; the tickers are made
up and so are the numbers.

The sample is built by driving the real API against a scratch data
directory, so every lot, every frozen entry snapshot, every dated
hand-entered figure and every verdict is produced by the same code the app
runs. Then each security is evaluated and the state it exists to demonstrate
is asserted. If a change to the strategy or the host moves any of those
states, this script refuses to write the file rather than shipping a sample
that no longer shows what its own notes claim.

Run from the project root:

    python tools/make_sample.py

What it covers, and what it deliberately cannot
-----------------------------------------------
Nine of Graham's eleven states. The two missing ones and why:

- **"No room for it"** needs the journal to be at capacity. Graham runs
  twenty places by default, so demonstrating it would mean shipping twenty
  holdings or configuring the sample journal below Graham's own ten-to-thirty
  range. Both cost more than the state is worth here; the state is covered by
  the test suite instead.

- **"The discount has closed"** needs an exit level breached on *two
  consecutive filings*, and the confirmation walk reads filing history. A
  journal whose figures are all entered by hand has no filing history at all,
  so a valuation exit can be crossed but never confirmed. That is not a
  limitation of the sample — it is true of any real journal driven by hand,
  and it is worth knowing. CALDR below sits in exactly that position and its
  note says so.

The one exit that *can* fire without filing history is the run of annual
losses, because two consecutive losing years are already two consecutive
annual filings. BRENT demonstrates it.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# A scratch data directory, so building the sample can never touch a real
# journal. Set before anything imports the store.
os.environ["LEDGER_DATA"] = tempfile.mkdtemp(prefix="ledger-sample-")

from app import Api                                            # noqa: E402
from engine import dated, portfolio                            # noqa: E402

TEMPLATE = ROOT / "data.template" / "sample.json"

# The day the stories were written against. Dates below are fixed rather
# than relative, so the sample reads the same on the day it is built and a
# year later: the two-year clock on MERIDN has run out and stays run out.
TODAY = "2026-08-09"

FREE_CASH = 62_000.0

api = Api()


class writing_on:
    """Write dated entries as though on a chosen day.

    Every record the user supplies is stamped by the host at the moment of
    writing and no caller can hand in its own date — that guarantee is what
    makes "what did I know then" answerable, and it is not weakened for a
    sample. So the generator does what a test does: it moves the clock the
    host reads, rather than asking politely for a date.
    """

    def __init__(self, day):
        # Local noon, because that is what the real stamp records: the day
        # the writer was standing on. A fixed UTC hour lands on the following
        # calendar day east of about UTC+10, which would build a sample whose
        # entries are dated a day after the story says they were.
        self.day = (datetime.fromisoformat(f"{day}T12:00:00")
                    .astimezone().isoformat(timespec="seconds"))

    def __enter__(self):
        self._dated, self._stamp = dated.stamp, portfolio._stamp
        dated.stamp = lambda: self.day
        portfolio._stamp = lambda: self.day

    def __exit__(self, *exc):
        dated.stamp, portfolio._stamp = self._dated, self._stamp


def call(fn, *a, **kw):
    r = fn(*a, **kw)
    assert r.get("ok"), f"{fn.__name__}: {r.get('error')}"
    return r


def security(ticker, name, price, values, on, thesis=None, notes=(),
             earlier=None):
    """One invented company: its figures on the record, dated, with the
    thesis and notes that go with them."""
    call(api.add_security, ticker, name)
    if earlier:
        day, figures, then_price = earlier
        with writing_on(day):
            call(api.save_metrics, ticker, figures, then_price)
    with writing_on(on):
        call(api.save_metrics, ticker, values, price)
        if thesis:
            call(api.amend_thesis, ticker, thesis[0], thesis[1])
    for day, text in notes:
        with writing_on(day):
            call(api.add_note, ticker, text)


def buy(ticker, shares, cost, opened, override_reason=""):
    with writing_on(opened):
        return call(api.open_position, ticker, shares, cost, opened,
                    override_reason)


def sell(ticker, reason, price, exited, shares=None):
    with writing_on(exited):
        return call(api.sell_shares, ticker, reason, price, exited, shares)


def state_of(ticker):
    journal, record, chain, _ = api._open()
    s = api._find(journal, ticker)
    decision = api._decide(s, journal["securities"], journal, record, chain)
    return decision["state"]["id"], decision


def expect(ticker, want):
    got, decision = state_of(ticker)
    assert got == want, (f"{ticker}: expected {want}, got {got} — "
                         f"{decision['reason']['summary']}")
    return decision


# ===========================================================================
# The journal
# ===========================================================================

call(api.create_journal, "Sample — Graham", "graham",
     {"free-cash": FREE_CASH})


# -- a holding with nothing happening ---------------------------------------
# The ordinary case, and the one a novice most needs to see: a business
# nobody would call exciting, bought cheap, sitting there.

security(
    "HARW", "Harwick Paper Mills", 34.10,
    dict(pe_3y_avg_eps=10.4, price_to_book=0.96,
         graham_combined_multiple=9.98, current_ratio=2.6,
         ltd_to_working_capital=0.35, profitable_years_10y=10,
         altman_z_score=3.9, eps_growth_10y=41.0,
         consecutive_dividend_years=22, debt_to_equity=0.48,
         price_to_net_tangible_assets=1.15, accruals_ratio=0.02,
         market_cap=610_000_000, ncav_to_market_cap=0.71,
         consecutive_annual_loss_years=0),
    on="2025-11-01",
    thesis=("A regional paper mill trading below its own book value with "
            "twenty-two straight years of dividends behind it. I am not "
            "claiming this is a wonderful business. I am claiming the price "
            "is wrong for what the balance sheet holds.",
            "Two consecutive years of losses, or the current ratio falling "
            "under 1.2. Either one means the balance sheet has stopped "
            "carrying the risk the business cannot."),
    notes=[("2025-11-01",
            "Bought because it is dull and cheap, which is the whole idea. "
            "Nothing about the industry is getting better and nothing needs "
            "to.")])
buy("HARW", 180, 30.85, "2025-11-04")


# -- a line crossed once, and the rule declining to panic --------------------

security(
    "CALDR", "Caldera Tube & Steel", 21.75,
    dict(pe_3y_avg_eps=19.2, price_to_book=3.28,
         graham_combined_multiple=62.98, current_ratio=2.1,
         ltd_to_working_capital=0.55, profitable_years_10y=10,
         altman_z_score=4.4, eps_growth_10y=63.0,
         consecutive_dividend_years=11, debt_to_equity=0.35,
         price_to_net_tangible_assets=2.9, accruals_ratio=0.05,
         market_cap=488_000_000, ncav_to_market_cap=0.34,
         consecutive_annual_loss_years=0),
    on="2026-08-02",
    earlier=("2025-06-08",
             dict(pe_3y_avg_eps=11.0, price_to_book=1.31,
                  graham_combined_multiple=14.41, current_ratio=2.3,
                  ltd_to_working_capital=0.51, profitable_years_10y=10,
                  altman_z_score=3.6, eps_growth_10y=58.0,
                  consecutive_dividend_years=10, debt_to_equity=0.38,
                  price_to_net_tangible_assets=1.5, accruals_ratio=0.04,
                  market_cap=278_000_000, ncav_to_market_cap=0.61,
                  consecutive_annual_loss_years=0), 12.40),
    thesis=("Bought at a third of what the tubes and the plant are worth on "
            "the books, after a customer cancelled a contract that was 8% of "
            "revenue. The cancellation is real and it is not the business.",
            "Book value falling for two straight years, which would mean the "
            "plant is worth less than I thought rather than the market being "
            "wrong about it."),
    notes=[("2025-06-12",
            "Bought this under the size floor. $278M against a floor of "
            "$300M is not far under it, and the strategy still said no — a "
            "floor that bends for a near miss is not a floor. What I am "
            "actually taking on is a company small enough that getting out "
            "of a position this size may not be quick, and that is a "
            "different risk from the one every other test here measures. "
            "Written down so that if it turns out to matter, it is on the "
            "record that I knew."),
           ("2026-08-02",
            "The price has run and both valuation lines are crossed on this "
            "reading. The strategy will not act until a second filing says "
            "the same thing, which is the rule doing its job — and because "
            "every figure here is typed by hand there are no filings to "
            "confirm it with. That is the honest limit of running this "
            "without a data connection.")])
buy("CALDR", 260, 12.40, "2025-06-12",
    override_reason="Under the $300M size floor, at $278M. I am taking that "
                    "on deliberately: the discount is on the plant and the "
                    "tubes, which do not care what the market capitalisation "
                    "is, and I am buying a size I could still get out of. If "
                    "I am wrong it will be because I could not sell it, not "
                    "because the plant was worth less than I thought.")


# -- the balance sheet coming apart -----------------------------------------
# Uncomfortable on purpose. Down 41%, two losing years, and the strategy is
# saying get out.

security(
    "BRENT", "Brentford Chemical Works", 9.40,
    # The three earnings-based figures are WITHDRAWN rather than restated:
    # there are no earnings left to divide by, and blanking a field is an
    # entry saying you withdrew it on the day you did, not a deletion. The
    # measures then read absent — which is what a strategy must never
    # mistake for a pass.
    dict(pe_3y_avg_eps=None, graham_combined_multiple=None,
         eps_growth_10y=None,
         price_to_book=0.62, current_ratio=1.6,
         ltd_to_working_capital=1.4, profitable_years_10y=8,
         altman_z_score=1.55, consecutive_dividend_years=0,
         debt_to_equity=1.7, price_to_net_tangible_assets=0.9,
         accruals_ratio=0.14, market_cap=141_000_000,
         ncav_to_market_cap=0.44, consecutive_annual_loss_years=2),
    on="2026-07-28",
    earlier=("2025-02-05",
             dict(pe_3y_avg_eps=8.9, price_to_book=0.71,
                  graham_combined_multiple=6.32, current_ratio=2.4,
                  ltd_to_working_capital=0.7, profitable_years_10y=10,
                  altman_z_score=3.1, eps_growth_10y=36.0,
                  consecutive_dividend_years=13, debt_to_equity=0.8,
                  price_to_net_tangible_assets=1.1, accruals_ratio=0.06,
                  # Comfortably over the size floor when it was bought. This
                  # security is here to show a balance sheet coming apart,
                  # and a purchase that also had to override the size test
                  # would have two stories in it and teach neither.
                  market_cap=460_000_000, ncav_to_market_cap=0.66,
                  consecutive_annual_loss_years=0), 15.85),
    thesis=("Speciality chemicals at 0.7 times book with thirteen years of "
            "dividends. The plant is worth more than the whole company.",
            "A second consecutive annual loss, or the bankruptcy score "
            "dropping into the distress zone. Either would mean the plant "
            "being worth something is no longer the question."),
    notes=[("2025-02-10", "Cheap on assets. Everything else is ordinary."),
           ("2026-07-28",
            "Both halves of my falsifier fired. There is no earnings "
            "multiple on the screen because there are no earnings to divide "
            "by — the strategy reports that as unknown rather than as a "
            "pass, which is the difference between not knowing and being "
            "reassured.")])
buy("BRENT", 520, 15.85, "2025-02-10")


# -- the clock -------------------------------------------------------------
# Nothing is wrong. Sell anyway. This is the state most likely to be argued
# with and the one with the best evidence behind it.

security(
    "MERIDN", "Meridian Casting", 27.55,
    dict(pe_3y_avg_eps=13.1, price_to_book=1.28,
         graham_combined_multiple=16.77, current_ratio=2.35,
         ltd_to_working_capital=0.6, profitable_years_10y=10,
         altman_z_score=3.2, eps_growth_10y=39.0,
         consecutive_dividend_years=17, debt_to_equity=0.7,
         price_to_net_tangible_assets=1.6, accruals_ratio=0.03,
         market_cap=372_000_000, ncav_to_market_cap=0.55,
         consecutive_annual_loss_years=0),
    on="2024-03-04",
    thesis=("Foundry work for rail and marine, priced at 1.3 times book "
            "with seventeen years of dividends. The discount is the reason "
            "and the only reason.",
            "The current ratio under 1.2, or two losing years. I have no "
            "view on whether this business is good."),
    notes=[("2024-03-08", "Bought on the numbers. Nothing else."),
           ("2026-08-09",
            "Twenty-nine months in and up 6%. Nothing has broken and nothing "
            "has closed. This is the case the two-year clock exists for: a "
            "discount that simply sits there is how this style of investing "
            "quietly fails, and no measure can hold 'it has been two "
            "years'.")])
buy("MERIDN", 200, 25.90, "2024-03-08")


# -- a name that ran, and an override that worked ---------------------------
# Bought against the strategy's own verdict, doubled, and is now the largest
# thing in the account. Both halves belong in a journal: the override log
# says the rule was overridden and it worked, and the size rule says it has
# become a different kind of risk.

security(
    "OKELL", "Okell Marine Supply", 41.20,
    dict(pe_3y_avg_eps=18.2, price_to_book=2.35,
         graham_combined_multiple=42.77, current_ratio=2.2,
         ltd_to_working_capital=0.3, profitable_years_10y=10,
         altman_z_score=4.8, eps_growth_10y=71.0,
         consecutive_dividend_years=12, debt_to_equity=0.4,
         price_to_net_tangible_assets=3.1, accruals_ratio=0.02,
         market_cap=980_000_000, ncav_to_market_cap=0.21,
         consecutive_annual_loss_years=0),
    on="2026-08-02",
    earlier=("2024-11-15",
             dict(pe_3y_avg_eps=14.1, price_to_book=1.94,
                  graham_combined_multiple=27.35, current_ratio=2.1,
                  ltd_to_working_capital=0.34, profitable_years_10y=10,
                  altman_z_score=4.1, eps_growth_10y=64.0,
                  consecutive_dividend_years=10, debt_to_equity=0.45,
                  price_to_net_tangible_assets=2.4, accruals_ratio=0.03,
                  market_cap=478_000_000, ncav_to_market_cap=0.4), 20.10),
    thesis=("Marine fittings, family controlled, no debt to speak of. Book "
            "value is understated because the yard was bought in 1974 and "
            "sits at cost.",
            "Debt to equity above 1.0, or the dividend run breaking."),
    notes=[("2024-11-19",
            "The strategy said no: 1.94 times book against a limit of 1.5, "
            "and the combined multiple over the line too. I bought it "
            "anyway because I think the land is carried at nothing. Writing "
            "that down is the point — if I keep being right about this the "
            "limit is wrong, and if I keep being wrong I am."),
           ("2026-08-02",
            "Up 105% and now 12% of the account against a cap of 10%. "
            "Nothing about the company has changed; the position has just "
            "got out of proportion to everything else, which is the risk a "
            "basket of twenty is supposed to avoid.")])
buy("OKELL", 300, 20.10, "2024-11-19",
    override_reason="The yard is carried at 1974 cost and the book value "
                    "the test is measuring against is therefore wrong. I "
                    "accept this is exactly what someone talking themselves "
                    "into a stock sounds like.")


# -- a holding the strategy cannot say anything about -----------------------

security(
    "THRAP", "Thrapston Rail Components", 16.30, {}, on="2025-08-18",
    thesis=("Bought on a conversation, not on numbers. I have not entered a "
            "single figure for it.",
            "There is nothing here to falsify yet, which is itself the "
            "problem."),
    notes=[("2025-08-20",
            "Recorded with no verdict at all — not a verdict I overrode, a "
            "verdict that did not exist. The journal keeps those two apart "
            "on purpose, because averaging them would make a gap in the "
            "data look like defiance.")])
buy("THRAP", 190, 15.10, "2025-08-20",
    override_reason="No figures on record for this company, so there was "
                    "nothing to check it against. Buying first and filling "
                    "the numbers in later is how I have always done it, "
                    "which is what I am trying to stop.")


# -- a candidate that qualifies ---------------------------------------------

security(
    "PELHAM", "Pelham Bindery", 18.45,
    dict(pe_3y_avg_eps=12.8, price_to_book=1.05,
         graham_combined_multiple=13.44, current_ratio=2.7,
         ltd_to_working_capital=0.3, profitable_years_10y=10,
         altman_z_score=3.8, eps_growth_10y=52.0,
         consecutive_dividend_years=18, debt_to_equity=0.44,
         price_to_net_tangible_assets=1.3, accruals_ratio=0.01,
         market_cap=420_000_000, ncav_to_market_cap=0.58,
         consecutive_annual_loss_years=0),
    on="2026-08-05",
    notes=[("2026-08-05",
            "Clears every test that can stop it. The one showing red is the "
            "earnings yield against the risk-free rate: at 12.8 times "
            "typical earnings this yields 7.8% a year, and against a "
            "risk-free rate of 4% the strategy wants twice that — 8%, which "
            "is 12.5 times earnings or less. It misses by two tenths of a "
            "percentage point of yield, which is three tenths of a turn on "
            "the multiple. That test never blocks a buy, and what it is "
            "telling me is worth reading anyway: the government is paying "
            "enough that "
            "this discount is thinner than it looks.")])


# -- a candidate the strategy is built to reject -----------------------------

security(
    "VANTR", "Vantris Analytics", 96.30,
    dict(pe_3y_avg_eps=41.5, price_to_book=8.1,
         graham_combined_multiple=336.15, current_ratio=3.4,
         ltd_to_working_capital=0.0, profitable_years_10y=7,
         altman_z_score=5.6, eps_growth_10y=210.0,
         consecutive_dividend_years=0, debt_to_equity=0.1,
         price_to_net_tangible_assets=9.4, accruals_ratio=0.08,
         market_cap=2_400_000_000, ncav_to_market_cap=0.09,
         consecutive_annual_loss_years=0),
    on="2026-08-05",
    notes=[("2026-08-05",
            "Growing fast, no debt, and rejected on three of the four "
            "knockouts. This is the strategy working as designed rather "
            "than failing: book value stopped describing companies like "
            "this around 1990, and their real assets — the code and the "
            "people — are on no balance sheet. A strategy that buys "
            "statistical discounts to book has nothing to say about it.")])


# -- a candidate that cannot be screened at all ------------------------------

security(
    "STANM", "Stanmore Regional Bank", 32.80,
    dict(pe_3y_avg_eps=9.2, price_to_book=0.88,
         graham_combined_multiple=8.10, profitable_years_10y=10,
         eps_growth_10y=38.0, consecutive_dividend_years=16,
         debt_to_equity=1.9, price_to_net_tangible_assets=0.95,
         accruals_ratio=0.04, market_cap=880_000_000,
         consecutive_annual_loss_years=0),
    on="2026-08-05",
    notes=[("2026-08-05",
            "Cheap on every measure that can be read, and it cannot be "
            "screened. Banks do not present a current ratio in the way this "
            "test means, and the bankruptcy score's author excluded "
            "financial companies outright because the ratios do not map. "
            "Both come back unknown, and unknown is not a pass. The irony "
            "is worth sitting with: price to book is the measure that still "
            "works best on banks, and this strategy cannot get far enough "
            "to use it.")])


# -- a previous holding, and what happened after the exit --------------------

security(
    "LOWFD", "Lowfield Ceramics", 24.60,
    dict(pe_3y_avg_eps=26.4, price_to_book=3.15,
         graham_combined_multiple=83.16, current_ratio=2.2,
         ltd_to_working_capital=0.4, profitable_years_10y=10,
         altman_z_score=4.0, eps_growth_10y=44.0,
         consecutive_dividend_years=14, debt_to_equity=0.5,
         price_to_net_tangible_assets=3.6, accruals_ratio=0.03,
         market_cap=690_000_000, ncav_to_market_cap=0.18,
         consecutive_annual_loss_years=0),
    on="2024-06-01",
    thesis=("Tableware and industrial ceramics at 0.8 times book. The "
            "market has priced the whole company at less than the kilns.",
            "Price to book above 3.0, at which point the discount I bought "
            "is gone and I am holding it for a reason I never tested."),
    notes=[("2024-06-04", "Bought at 0.8 times book."),
           ("2025-10-15",
            "Sold at 1.77 times what I paid. The discount closed, which is "
            "the entire exit condition of this strategy."),
           ("2026-08-05",
            "It has gone up another 24% since I sold. That is what the exit "
            "scorecard is for: if selling on a closed discount keeps "
            "leaving money on the table, the limit is the thing to look at "
            "and not my nerve.")])
buy("LOWFD", 400, 11.20, "2024-06-04")
sell("LOWFD", "Hit valuation", 19.80, "2025-10-15")


# ===========================================================================
# What each of them exists to show. Asserted against the real evaluator, so
# the sample cannot ship claiming a story it no longer tells.
# ===========================================================================

STORIES = {
    "HARW": "hold",
    "CALDR": "one-reading-past",
    "BRENT": "safety-gone",
    "MERIDN": "time-is-up",
    "OKELL": "too-big",
    "THRAP": "cannot-watch",
    "PELHAM": "buy",
    "VANTR": "not-cheap-enough",
    "STANM": "cannot-screen",
}

for ticker, want in STORIES.items():
    expect(ticker, want)

journal, *_ = api._open()
securities = journal["securities"]
by_ticker = {s["ticker"]: s for s in securities}

# The two overrides are different kinds and stay different kinds.
okell = portfolio.lots(by_ticker["OKELL"], "buy")[0]
assert okell["override"]["kind"] == "against", okell["override"]
thrap = portfolio.lots(by_ticker["THRAP"], "buy")[0]
assert thrap["override"]["kind"] == "without", thrap["override"]

# The buy that was against a verdict was against a real one, frozen as it
# stood on the day — not the verdict today, and not nothing.
assert okell["snapshot"]["decision"]["state"]["id"] == "not-cheap-enough"

# A closed holding period, still being priced.
cycles = portfolio.cycles(by_ticker["LOWFD"])
assert len(cycles) == 1 and not cycles[0]["open"], cycles

# The weight rule needs an account, and the account needs the free cash the
# strategy asked for. If this stops being true the sizing states go quiet.
held = [s for s in securities if portfolio.shares_held(s) > 0]
assert len(held) == 6, len(held)

TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
TEMPLATE.write_text(json.dumps(
    {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
     "as_of": TODAY,
     "free_cash": FREE_CASH,
     "strategy": "graham",
     "securities": securities}, indent=1, ensure_ascii=False) + "\n",
    encoding="utf-8")
print(f"wrote {TEMPLATE.relative_to(ROOT)}: {len(securities)} securities, "
      f"{len(set(STORIES.values()))} distinct states")
