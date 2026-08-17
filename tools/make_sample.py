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

from datetime import date, timedelta

from sample_kit import (buy, expect, journal, securities,
                        security, sell, state_of, write)

from engine import portfolio

# The day the stories are written against is the day the sample is BUILT.
#
# Two kinds of date below, and the split is the fix for a suite that rots
# overnight. A story that stays true as the calendar moves keeps absolute
# dates — MERIDN's two-year clock has run out and stays run out, BRENT's
# safety break outranks its clock, LOWFD is closed. A story that a moving
# calendar would silently overturn — a holding whose two-year clock must NOT
# have run out yet — is dated relative to the build day, with enough slack
# that a rebuilt sample holds its stories for at least a year. The canary in
# tests/test_sample.py evaluates every story six months ahead, so the suite
# says "rebuild the samples" long before any story actually turns.
TODAY = date.today().isoformat()


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()

FREE_CASH = 62_000.0



# ===========================================================================
# The journal
# ===========================================================================

# Created before the earliest entry in it — see sample_kit.journal for why
# that matters and what breaks when a sample journal is stamped today.
journal("Sample — Graham", "graham", {}, cash=FREE_CASH)


# -- a holding with nothing happening ---------------------------------------
# The ordinary case, and the one a novice most needs to see: a business
# nobody would call exciting, bought cheap, sitting there.

security(
    "HARW", "Harwick Paper Mills", 34.10,
    dict(pe_3y_avg_eps=8.4, price_to_book=0.96,
         graham_combined_multiple=8.06, current_ratio=2.6,
         ltd_to_working_capital=0.35, profitable_years_10y=10,
         altman_z_double_prime=3.4, eps_growth_10y=41.0,
         consecutive_capital_return_years=22, debt_to_equity=0.48,
         price_to_net_tangible_assets=1.15, accruals_ratio=0.02,
         revenue_ttm=1_210_000_000, ncav_to_market_cap=0.71,
         consecutive_annual_loss_years=0),
    on=days_ago(120),
    thesis=("A regional paper mill trading below its own book value with "
            "twenty-two straight years of dividends behind it. I am not "
            "claiming this is a wonderful business. I am claiming the price "
            "is wrong for what the balance sheet holds.",
            "Two consecutive years of losses, or the current ratio falling "
            "under 1.2. Either one means the balance sheet has stopped "
            "carrying the risk the business cannot."),
    notes=[(days_ago(120),
            "Bought because it is dull and cheap, which is the whole idea. "
            "Nothing about the industry is getting better and nothing needs "
            "to.")])
buy("HARW", 180, 30.85, days_ago(117))


# -- a line crossed once, and the rule declining to panic --------------------

security(
    "CALDR", "Caldera Tube & Steel", 21.75,
    dict(pe_3y_avg_eps=19.2, price_to_book=3.28,
         graham_combined_multiple=62.98, current_ratio=2.1,
         ltd_to_working_capital=0.55, profitable_years_10y=10,
         altman_z_double_prime=3.8, eps_growth_10y=63.0,
         consecutive_capital_return_years=21, debt_to_equity=0.35,
         price_to_net_tangible_assets=2.9, accruals_ratio=0.05,
         revenue_ttm=940_000_000, ncav_to_market_cap=0.34,
         consecutive_annual_loss_years=0),
    on=days_ago(7),
    earlier=(days_ago(304),
             dict(pe_3y_avg_eps=8.8, price_to_book=1.02,
                  graham_combined_multiple=8.98, current_ratio=2.3,
                  ltd_to_working_capital=0.51, profitable_years_10y=10,
                  altman_z_double_prime=3.1, eps_growth_10y=58.0,
                  consecutive_capital_return_years=20, debt_to_equity=0.38,
                  price_to_net_tangible_assets=1.5, accruals_ratio=0.04,
                  revenue_ttm=880_000_000, ncav_to_market_cap=0.61,
                  consecutive_annual_loss_years=0), 12.40),
    thesis=("Bought at a third of what the tubes and the plant are worth on "
            "the books, after a customer cancelled a contract that was 8% of "
            "revenue. The cancellation is real and it is not the business.",
            "Book value falling for two straight years, which would mean the "
            "plant is worth less than I thought rather than the market being "
            "wrong about it."),
    notes=[(days_ago(300),
            "Bought this under the size floor. $278M against a floor of "
            "$300M is not far under it, and the strategy still said no — a "
            "floor that bends for a near miss is not a floor. What I am "
            "actually taking on is a company small enough that getting out "
            "of a position this size may not be quick, and that is a "
            "different risk from the one every other test here measures. "
            "Written down so that if it turns out to matter, it is on the "
            "record that I knew."),
           (days_ago(7),
            "The price has run and both valuation lines are crossed on this "
            "reading. The strategy will not act until a second filing says "
            "the same thing, which is the rule doing its job — and because "
            "every figure here is typed by hand there are no filings to "
            "confirm it with. That is the honest limit of running this "
            "without a data connection.")])
buy("CALDR", 260, 12.40, days_ago(300),
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
         altman_z_double_prime=0.95, consecutive_capital_return_years=0,
         debt_to_equity=1.7, price_to_net_tangible_assets=0.9,
         accruals_ratio=0.14, revenue_ttm=760_000_000,
         ncav_to_market_cap=0.44, consecutive_annual_loss_years=2),
    on="2026-07-28",
    earlier=("2025-02-05",
             dict(pe_3y_avg_eps=7.9, price_to_book=0.71,
                  graham_combined_multiple=5.61, current_ratio=2.4,
                  ltd_to_working_capital=0.7, profitable_years_10y=10,
                  altman_z_double_prime=2.9, eps_growth_10y=36.0,
                  consecutive_capital_return_years=23, debt_to_equity=0.8,
                  price_to_net_tangible_assets=1.1, accruals_ratio=0.06,
                  # Comfortably over the size floor when it was bought. This
                  # security is here to show a balance sheet coming apart,
                  # and a purchase that also had to override the size test
                  # would have two stories in it and teach neither.
                  revenue_ttm=1_060_000_000, ncav_to_market_cap=0.66,
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
    dict(pe_3y_avg_eps=9.1, price_to_book=1.28,
         graham_combined_multiple=11.65, current_ratio=2.35,
         ltd_to_working_capital=0.6, profitable_years_10y=10,
         altman_z_double_prime=2.9, eps_growth_10y=39.0,
         consecutive_capital_return_years=27, debt_to_equity=0.7,
         price_to_net_tangible_assets=1.6, accruals_ratio=0.03,
         revenue_ttm=1_072_000_000, ncav_to_market_cap=0.55,
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
         altman_z_double_prime=4.1, eps_growth_10y=71.0,
         consecutive_capital_return_years=22, debt_to_equity=0.4,
         price_to_net_tangible_assets=3.1, accruals_ratio=0.02,
         revenue_ttm=1_980_000_000, ncav_to_market_cap=0.21,
         consecutive_annual_loss_years=0),
    on=days_ago(7),
    earlier=(days_ago(304),
             dict(pe_3y_avg_eps=14.1, price_to_book=1.94,
                  graham_combined_multiple=27.35, current_ratio=2.1,
                  ltd_to_working_capital=0.34, profitable_years_10y=10,
                  altman_z_double_prime=3.6, eps_growth_10y=64.0,
                  consecutive_capital_return_years=20, debt_to_equity=0.45,
                  price_to_net_tangible_assets=2.4, accruals_ratio=0.03,
                  revenue_ttm=1_478_000_000, ncav_to_market_cap=0.4), 20.10),
    thesis=("Marine fittings, family controlled, no debt to speak of. Book "
            "value is understated because the yard was bought in 1974 and "
            "sits at cost.",
            "Debt to equity above 1.0, or the dividend run breaking."),
    notes=[(days_ago(300),
            "The strategy said no: 1.94 times book against a limit of 1.5, "
            "and the combined multiple over the line too. I bought it "
            "anyway because I think the land is carried at nothing. Writing "
            "that down is the point — if I keep being right about this the "
            "limit is wrong, and if I keep being wrong I am."),
           (days_ago(7),
            "Up 105% and now 12% of the account against a cap of 10%. "
            "Nothing about the company has changed; the position has just "
            "got out of proportion to everything else, which is the risk a "
            "basket of twenty is supposed to avoid.")])
buy("OKELL", 300, 20.10, days_ago(300),
    override_reason="The yard is carried at 1974 cost and the book value "
                    "the test is measuring against is therefore wrong. I "
                    "accept this is exactly what someone talking themselves "
                    "into a stock sounds like.")


# -- a holding the strategy cannot say anything about -----------------------

security(
    "THRAP", "Thrapston Rail Components", 16.30, {}, on=days_ago(202),
    thesis=("Bought on a conversation, not on numbers. I have not entered a "
            "single figure for it.",
            "There is nothing here to falsify yet, which is itself the "
            "problem."),
    notes=[(days_ago(200),
            "Recorded with no verdict at all — not a verdict I overrode, a "
            "verdict that did not exist. The journal keeps those two apart "
            "on purpose, because counting a gap in the data as defiance "
            "would put a decision I never made into the one figure that is "
            "supposed to measure my judgement.")])
buy("THRAP", 190, 15.10, days_ago(200),
    recollection="No figures on record for this company, so there was "
                 "nothing to check it against. Buying first and filling the "
                 "numbers in later is how I have always done it, which is "
                 "what I am trying to stop.")


# -- a candidate that qualifies ---------------------------------------------

security(
    "PELHAM", "Pelham Bindery", 18.45,
    dict(pe_3y_avg_eps=9.2, price_to_book=1.05,
         graham_combined_multiple=9.66, current_ratio=2.7,
         ltd_to_working_capital=0.3, profitable_years_10y=10,
         altman_z_double_prime=3.3, eps_growth_10y=52.0,
         consecutive_capital_return_years=28, debt_to_equity=0.44,
         price_to_net_tangible_assets=1.3, accruals_ratio=0.01,
         revenue_ttm=1_020_000_000, ncav_to_market_cap=0.58,
         consecutive_annual_loss_years=0),
    on="2026-08-05",
    notes=[("2026-08-05",
            "Clears every test that can stop it, and the one worth reading "
            "is the price. The ceiling here is not the flat fifteen times "
            "typical earnings I expected: it is the stricter of that and "
            "what the bond market is paying. High-grade corporate bonds are "
            "set at 5% in my settings and the strategy wants twice that as "
            "an earnings yield — 10%, which is ten times earnings or less. "
            "So the bar is 10 and this is at 9.2.\n\n"
            "Worth knowing what that means when rates move. If I set the "
            "bond yield to 6%, the ceiling drops to 8.3 and this same "
            "company is refused outright on a number that did not change. "
            "That is the point of the rule rather than a defect in it — a "
            "9.2 multiple is a different proposition when safe money pays "
            "6% than when it pays 3% — but it does mean the one figure I "
            "have to maintain by hand is the one that decides the most.")])


# -- a candidate the strategy is built to reject -----------------------------

security(
    "VANTR", "Vantris Analytics", 96.30,
    dict(pe_3y_avg_eps=41.5, price_to_book=8.1,
         graham_combined_multiple=336.15, current_ratio=3.4,
         ltd_to_working_capital=0.0, profitable_years_10y=7,
         altman_z_double_prime=4.9, eps_growth_10y=210.0,
         consecutive_capital_return_years=0, debt_to_equity=0.1,
         price_to_net_tangible_assets=9.4, accruals_ratio=0.08,
         revenue_ttm=2_400_000_000, ncav_to_market_cap=0.09,
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
         eps_growth_10y=38.0, consecutive_capital_return_years=24,
         debt_to_equity=1.9, price_to_net_tangible_assets=0.95,
         accruals_ratio=0.04, revenue_ttm=880_000_000,
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
         altman_z_double_prime=4.0, eps_growth_10y=44.0,
         consecutive_capital_return_years=14, debt_to_equity=0.5,
         price_to_net_tangible_assets=3.6, accruals_ratio=0.03,
         revenue_ttm=690_000_000, ncav_to_market_cap=0.18,
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

rows = securities()
by_ticker = {s["ticker"]: s for s in rows}

# A verdict gone against, and an evaluation that could not be rebuilt at all.
# They are different records, not two flavours of one, and the whole learning
# loop depends on their staying apart: an override is a decision somebody took
# in the face of a signal, and a purchase nothing could be reconstructed for is
# not a decision about anything — there was no signal to obey or defy.
okell = portfolio.lots(by_ticker["OKELL"], "buy")[0]
assert okell["override"]["kind"] == "against", okell["override"]
assert okell["unreconstructed"] is None, okell["unreconstructed"]
thrap = portfolio.lots(by_ticker["THRAP"], "buy")[0]
assert thrap["override"] is None, thrap["override"]
assert thrap["unreconstructed"], thrap

# The buy that was against a verdict was against a real one, frozen as it
# stood on the day — not the verdict today, and not nothing.
assert okell["snapshot"]["decision"]["state"]["id"] == "not-cheap-enough"

# A closed holding period, still being priced.
cycles = portfolio.cycles(by_ticker["LOWFD"])
assert len(cycles) == 1 and not cycles[0]["open"], cycles

# The exit is judged against the data of the day it is dated, not against
# today's. It was judged against today's, which froze a verdict the strategy
# was never asked for into `signal_at_exit` and `rule_triggered` — the two
# facts the panic-sell scorecard teaches from. A sample shipping that would be
# demonstrating the defect.
exit_lot = portfolio.lots(by_ticker["LOWFD"], "sell")[0]
assert portfolio.basis_of(exit_lot) == "reconstructed", exit_lot["snapshot"]
assert exit_lot["snapshot"]["evaluation"]["as_of"] == "2025-10-15"
assert exit_lot["snapshot"]["decision"]["state"]["id"] != \
    state_of("LOWFD")[0], \
    "the frozen exit verdict is today's, which means the sale was not " \
    "rebuilt for its own day"

# Every entry in this sample is dated before the day it was written, so every
# one of them is a reconstruction and every one of them says so. That is the
# honest reading of a demonstration journal built out of an invented history,
# and it is what the screens have to mark.
assert portfolio.backfilled(by_ticker["LOWFD"])

# The weight rule needs an account, and the account needs the free cash the
# strategy asked for. If this stops being true the sizing states go quiet.
held = [s for s in rows if portfolio.shares_held(s) > 0]
assert len(held) == 6, len(held)

# Every story asserted against the real evaluator, and only then the file.
write("sample-graham.json", "graham", FREE_CASH, TODAY, STORIES)
