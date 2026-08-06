"""Builds data.template/sample.json.

All companies and figures are invented. Values are keyed by metric-bank ids
and every entry snapshot is produced by the real evaluator against the real
template profiles, so the sample can never drift out of step with the code.
The script asserts the story each security exists to tell — an expired
position clock, a breach awaiting confirmation, a purchase recorded against
the signal and one recorded without a signal, profiles disagreeing about the
same candidate — and refuses to write the file if any of it stops being true.

Run from the project root:
    python tools/make_sample.py
"""
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Point the data dir at a scratch location so the template profiles seed there
# and no real user data is touched.
os.environ["LEDGER_DATA"] = tempfile.mkdtemp(prefix="ledger-sample-")

from engine import profiles                                    # noqa: E402
from engine.evaluate import evaluate_buy, evaluate_position    # noqa: E402

TODAY = date(2026, 8, 6)      # the date the stories were written against

PROFILES = {p["id"]: profiles.resolve_profile(p["file"])
            for p in profiles.list_profiles()[0]}
for _p in PROFILES.values():
    assert not _p["errors"], f'{_p["file"]}: {_p["errors"]}'

BANK_IDS = set(profiles.bank_index(profiles.load_bank("metric-bank")))
REFERENCED = set()
for _p in PROFILES.values():
    for _t in _p["tiers"]:
        for _e in _t["entries"]:
            REFERENCED.add(_e["metric"])
            for _b in (_e.get("sell"), _e.get("flag")):
                if isinstance(_b, dict) and _b.get("measured_on"):
                    REFERENCED.add(str(_b["measured_on"]))


def M(**kw):
    bad = set(kw) - BANK_IDS
    assert not bad, f"not bank ids: {bad}"
    loose = set(kw) - REFERENCED
    assert not loose, f"no profile references: {loose}"
    return kw


def sec(ticker, name, bucket, price, metrics, added, falsifier="", notes=()):
    return {
        "ticker": ticker, "name": name, "bucket": bucket, "added": added,
        "price": price, "metrics": metrics, "history": {},
        "entry_snapshot": None, "override": None, "ev": None,
        "falsifier": falsifier,
        "notes": [{"date": d, "text": t} for d, t in notes],
        "position": None, "exit": None,
    }


def snap(s, profile_id, entry_metrics, opened, price):
    """Freeze an entry snapshot the way open_position does, at a fixed date."""
    prof = PROFILES[profile_id]
    result = evaluate_buy(entry_metrics, prof)
    s["entry_snapshot"] = {
        "frozen": opened + "T00:00:00+00:00",
        "profile": {"file": prof["file"], "id": prof["id"],
                    "name": prof["name"], "version": 1},
        "metrics": entry_metrics,
        "price": price,
        "result": result,
    }
    return result


def expect(label, got, want):
    assert got == want, f"{label}: expected {want}, got {got}"


SECS = []

# ---------------------------------------------------------------- holdings

# 1. A healthy Buffett hold: green at entry, still green, nothing to do.
s = sec("HLDN", "Halden Industrial Group", "holdings", 84.20,
        M(roic_median_5y=18.9, total_debt_to_ebitda=1.4, owner_earnings_yield=5.6,
          interest_coverage=11.2, gross_margin_range_5y=3.1,
          fcf_margin_median_5y=12.4, fcf_margin_ttm=12.8,
          cash_conversion_median_5y=0.97, diluted_share_count_change_5y=-4.2,
          diluted_share_count_change_3y=-2.6, roe_median_5y=17.8,
          revenue_cagr_5y=8.4, ni_minus_revenue_cagr_spread_5y=1.2,
          goodwill_intangibles_to_assets=21.5, effective_tax_rate_median_5y=21.4,
          current_ratio=2.1, payout_to_fcf_median_5y=44,
          pe_3y_avg_eps=19.6, price_to_book=3.1, graham_combined_multiple=60.8,
          eps_cagr_5y=12.1, peg_trailing=1.52,
          revenue_cagr_3y=7.9, debt_to_equity=0.34, altman_z_score=4.1,
          ev_to_ebit=13.1, fcf_ttm=412_000_000),
        added="2023-04-11",
        falsifier="Two consecutive quarters of gross margin below 38%, or total "
                  "debt/EBITDA back above 2.5x. Either one means the pricing power "
                  "argument I bought this on was wrong.",
        notes=[("2023-04-11", "Bought after the distribution contract loss knocked 30% off. "
                              "Thesis was that the loss was one customer, not the business. "
                              "Margins held through it, which is the tell.")])
s["position"] = {"shares": 180, "cost_basis": 61.05, "opened": "2023-04-11"}
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 84.20, "fcf_ttm": 412, "shares": 78,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-07-02"}
r = snap(s, "buffett",
         M(roic_median_5y=17.2, total_debt_to_ebitda=1.9, owner_earnings_yield=7.9,
           interest_coverage=8.7, gross_margin_range_5y=3.8,
           fcf_margin_median_5y=11.2, fcf_margin_ttm=11.0,
           cash_conversion_median_5y=0.94, diluted_share_count_change_5y=-2.8,
           diluted_share_count_change_3y=-1.7, roe_median_5y=16.4,
           revenue_cagr_5y=7.1, ni_minus_revenue_cagr_spread_5y=0.8,
           goodwill_intangibles_to_assets=22.4, effective_tax_rate_median_5y=21.8,
           current_ratio=1.9, payout_to_fcf_median_5y=41),
         "2023-04-11", 61.05)
expect("HLDN entry verdict", r["verdict"], "buy")
expect("HLDN now (buffett)",
       evaluate_buy(s["metrics"], PROFILES["buffett"])["verdict"], "buy")
expect("HLDN sell watch",
       evaluate_position(s, PROFILES["buffett"], TODAY)["overall"], "clear")
SECS.append(s)

# 2. A Lynch position whose PEG has run past the sell line: breached, but the
#    profile demands two consecutive filings and the journal has one reading.
s = sec("CVSW", "Corvus Software", "holdings", 214.60,
        M(peg_trailing=2.31, eps_cagr_5y=19.4, debt_to_equity=0.12,
          revenue_cagr_3y=14.8, eps_minus_revenue_cagr_spread_5y=2.6,
          receivables_minus_revenue_growth_yoy=3.8, pe_to_own_5y_median_pe=1.38,
          gross_margin_change_3y=1.3, interest_coverage=31.0,
          fcf_ttm=690_000_000, net_cash_to_market_cap=0.04,
          institutional_ownership_pct=72),
        added="2022-09-02",
        falsifier="Net revenue retention below 105%, or a full year of revenue "
                  "growth under 12%. Either would mean I'm paying a growth "
                  "multiple for a mature business.",
        notes=[("2022-09-02", "Bought on the post-guidance selloff."),
               ("2026-06-14", "The business hasn't deteriorated at all. What broke is "
                              "the valuation, and only because the price ran. The PEG "
                              "sell line is breached on this quarter's reading; the "
                              "profile wants it on two filings before it counts.")])
s["position"] = {"shares": 64, "cost_basis": 118.40, "opened": "2022-09-02"}
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 214.60, "fcf_ttm": 690, "shares": 141,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-07-02"}
r = snap(s, "lynch",
         M(peg_trailing=0.96, eps_cagr_5y=17.1, debt_to_equity=0.14,
           revenue_cagr_3y=15.2, eps_minus_revenue_cagr_spread_5y=1.9,
           receivables_minus_revenue_growth_yoy=2.1, pe_to_own_5y_median_pe=0.82,
           gross_margin_change_3y=0.9, interest_coverage=24.5,
           fcf_ttm=420_000_000, net_cash_to_market_cap=0.06,
           institutional_ownership_pct=64),
         "2022-09-02", 118.40)
expect("CVSW entry verdict", r["verdict"], "buy")
_pos = evaluate_position(s, PROFILES["lynch"], TODAY)
expect("CVSW sell watch", _pos["overall"], "breached")
assert any(x["metric"] == "peg_trailing" and x["status"] == "breached"
           for x in _pos["signals"])
SECS.append(s)

# 3. A Buffett thesis decaying: the compound ROIC exit has one leg true and one
#    false (so it does not fire), while leverage and current free cash flow sit
#    past their lines awaiting confirmation.
s = sec("PMBF", "Pemberton Foods", "holdings", 29.14,
        M(roic_median_5y=12.8, total_debt_to_ebitda=4.3, owner_earnings_yield=6.9,
          interest_coverage=4.6, gross_margin_range_5y=7.2,
          fcf_margin_median_5y=6.1, fcf_margin_ttm=-1.2,
          cash_conversion_median_5y=0.78, diluted_share_count_change_5y=4.1,
          diluted_share_count_change_3y=2.4, roe_median_5y=11.9,
          revenue_cagr_5y=1.8, ni_minus_revenue_cagr_spread_5y=-4.2,
          goodwill_intangibles_to_assets=27.0, effective_tax_rate_median_5y=22.1,
          current_ratio=0.9, payout_to_fcf_median_5y=96),
        added="2024-01-22",
        falsifier="I said I'd be wrong if free cash flow went negative while the "
                  "debt built. Both are on the current reading. The confirmation "
                  "window is the only thing between me and the sell button, which "
                  "is exactly what it's for.",
        notes=[("2024-01-22", "Cheap on normalised earnings, family-controlled, boring."),
               ("2026-05-08", "Debt through 4x on this quarter's reading and FCF "
                              "negative. One more filing like this and the rules "
                              "say what I already suspect.")])
s["position"] = {"shares": 240, "cost_basis": 38.90, "opened": "2024-01-22"}
s["ev"] = {"method": "scenario",
           "inputs": {"bear_value": 21, "bear_prob": 45, "base_value": 31,
                      "base_prob": 40, "bull_value": 44, "bull_prob": 15},
           "computed": "2026-05-08"}
r = snap(s, "buffett",
         M(roic_median_5y=19.5, total_debt_to_ebitda=2.1, owner_earnings_yield=7.2,
           interest_coverage=8.4, gross_margin_range_5y=4.8,
           fcf_margin_median_5y=10.8, fcf_margin_ttm=9.4,
           cash_conversion_median_5y=0.91, diluted_share_count_change_5y=-1.5,
           diluted_share_count_change_3y=-0.9, roe_median_5y=16.2,
           revenue_cagr_5y=5.4, ni_minus_revenue_cagr_spread_5y=-0.6,
           goodwill_intangibles_to_assets=18.0, effective_tax_rate_median_5y=21.2,
           current_ratio=1.6, payout_to_fcf_median_5y=58),
         "2024-01-22", 38.90)
expect("PMBF entry verdict", r["verdict"], "buy")
_pos = evaluate_position(s, PROFILES["buffett"], TODAY)
expect("PMBF sell watch", _pos["overall"], "breached")
_roic = next(x for x in _pos["signals"] if x["metric"] == "roic_median_5y")
expect("PMBF compound sell holds fire on one leg", _roic["status"], "clear")
assert any(x["metric"] == "total_debt_to_ebitda" and x["status"] == "breached"
           for x in _pos["signals"])
SECS.append(s)

# 4. Bought against the signal: Lynch said No buy on all three required
#    entries and the purchase was recorded anyway, with the stated reason.
s = sec("KTRA", "Kestrel Aerospace", "holdings", 47.80,
        M(peg_trailing=3.20, eps_cagr_5y=2.1, debt_to_equity=1.48,
          revenue_cagr_3y=9.8, eps_minus_revenue_cagr_spread_5y=-7.7,
          inventory_minus_revenue_growth_yoy=9.4,
          receivables_minus_revenue_growth_yoy=6.1, pe_to_own_5y_median_pe=1.21,
          gross_margin_change_3y=-1.9, interest_coverage=2.1,
          fcf_ttm=-40_000_000, net_cash_to_market_cap=-0.22,
          institutional_ownership_pct=48),
        added="2025-11-14",
        falsifier="Left blank at purchase. That absence is itself part of the record.",
        notes=[("2025-11-14", "Bought this the same afternoon I read the backlog release. "
                              "Did not run the numbers first.")])
s["position"] = {"shares": 95, "cost_basis": 69.20, "opened": "2025-11-14"}
r = snap(s, "lynch",
         M(peg_trailing=2.84, eps_cagr_5y=4.8, debt_to_equity=1.31,
           revenue_cagr_3y=10.2, eps_minus_revenue_cagr_spread_5y=-5.4,
           inventory_minus_revenue_growth_yoy=6.2,
           receivables_minus_revenue_growth_yoy=4.8, pe_to_own_5y_median_pe=1.34,
           gross_margin_change_3y=-0.8, interest_coverage=2.8,
           fcf_ttm=-25_000_000, net_cash_to_market_cap=-0.18,
           institutional_ownership_pct=46),
         "2025-11-14", 69.20)
expect("KTRA entry verdict", r["verdict"], "no_buy")
_failed = [m for c in r["causes"] if c["kind"] == "fail" for m in c["metrics"]]
s["override"] = {
    "date": "2025-11-14", "verdict": "No buy",
    "profile": s["entry_snapshot"]["profile"],
    "failed": _failed, "missing": [],
    "reason": "Backlog is at a record and the debt is from the acquisition, "
              "which closes next year. I think the leverage number is temporary.",
}
s["notes"].append({"date": "2025-11-14",
                   "text": "Bought against signal (No buy under Lynch). Stated reason: "
                           + s["override"]["reason"]})
assert "debt_to_equity" in _failed and "peg_trailing" in _failed
SECS.append(s)

# 5. Bought without a signal: a recent spin-off with too little history for
#    Graham's ten-year tests, so the verdict was grey — and grey is not a pass.
s = sec("LNWD", "Lindenwood Materials", "holdings", 52.35,
        M(pe_3y_avg_eps=16.2, price_to_book=1.3, graham_combined_multiple=21.1,
          current_ratio=2.2, ltd_to_working_capital=0.7, debt_to_equity=0.5,
          altman_z_score=3.4, accruals_ratio=0.06,
          price_to_net_tangible_assets=1.9, market_cap=1_400_000_000,
          ncav_to_market_cap=0.22),
        added="2026-05-30",
        falsifier="Not yet written. The position is open without one, and the tool "
                  "should keep saying so until it's filled in.",
        notes=[("2026-05-30", "Spun off in March, so the ten-year stability tests "
                              "can't run. The verdict was Can't say, not Buy — "
                              "I bought on a judgement the data couldn't check.")])
s["position"] = {"shares": 120, "cost_basis": 49.10, "opened": "2026-05-30"}
r = snap(s, "graham",
         M(pe_3y_avg_eps=14.8, price_to_book=1.3, graham_combined_multiple=19.2,
           current_ratio=2.2, ltd_to_working_capital=0.7, debt_to_equity=0.5,
           altman_z_score=3.4, accruals_ratio=0.06,
           price_to_net_tangible_assets=1.9, market_cap=1_300_000_000,
           ncav_to_market_cap=0.24),
         "2026-05-30", 49.10)
expect("LNWD entry verdict", r["verdict"], "cant_say")
_missing = [m for c in r["causes"] if c["kind"] == "indeterminate"
            for m in c["metrics"]]
s["override"] = {
    "date": "2026-05-30", "verdict": "Can't say",
    "profile": s["entry_snapshot"]["profile"],
    "failed": [], "missing": _missing,
    "reason": "The business is ninety years old even if the filings are five "
              "quarters old. I am treating the parent's history as the record "
              "the spin-off doesn't have yet.",
}
s["notes"].append({"date": "2026-05-30",
                   "text": "Bought without a signal (Can't say under Graham). Stated reason: "
                           + s["override"]["reason"]})
assert "profitable_years_10y" in _missing
_pos = evaluate_position(s, PROFILES["graham"], TODAY)
expect("LNWD clock running", _pos["clock"]["expired"], False)
assert any(x["status"] == "unevaluable" for x in _pos["signals"])
SECS.append(s)

# 6. Discount Closure with the 24-month clock expired: the discount mostly
#    closed, no metric fired, and the calendar — which needs no filing
#    history — is the thing saying sell.
s = sec("MERI", "Meridian Fastener Co.", "holdings", 24.60,
        M(ev_ebit_to_own_5y_median=0.94, ev_to_ebit=10.4, altman_z_score=3.0,
          net_debt_to_ebitda=2.2, operating_income_ttm=150_000_000,
          fcf_yield_on_ev=7.6, fcf_ttm=95_000_000, interest_coverage=5.8,
          revenue_change_yoy=2.1, gross_margin_vs_3y_median=0.4,
          diluted_share_count_change_ttm=1.1, accruals_ratio=0.04),
        added="2024-04-10",
        falsifier="A structural reason for the discount that I failed to find "
                  "before buying. None surfaced; the discount just closed slowly.",
        notes=[("2024-04-15", "30% under its own five-year multiple with nothing in "
                              "the filings to explain it. Solvency floors all clear."),
               ("2026-07-15", "Up 35% and the clock runs out this spring. The exit "
                              "is the calendar, by design — a stock that stays "
                              "cheap forever is how this style fails.")])
s["position"] = {"shares": 400, "cost_basis": 18.20, "opened": "2024-04-15"}
r = snap(s, "discount_closure",
         M(ev_ebit_to_own_5y_median=0.64, ev_to_ebit=6.8, altman_z_score=3.1,
           net_debt_to_ebitda=1.9, operating_income_ttm=140_000_000,
           fcf_yield_on_ev=11.2, fcf_ttm=90_000_000, interest_coverage=6.2,
           revenue_change_yoy=-4.1, gross_margin_vs_3y_median=-0.8,
           diluted_share_count_change_ttm=0.9, accruals_ratio=0.05),
         "2024-04-15", 18.20)
expect("MERI entry verdict", r["verdict"], "buy")
_pos = evaluate_position(s, PROFILES["discount_closure"], TODAY)
expect("MERI clock expired", _pos["clock"]["expired"], True)
expect("MERI sell watch", _pos["overall"], "fired")
SECS.append(s)

# ---------------------------------------------------------------- previous

# 7. An exit a rule genuinely fired: two consecutive annual losses is Graham's
#    loss-streak exit, and the streak is its own confirmation.
s = sec("ORVL", "Orvalt Chemical", "previous", 34.10,
        M(price_to_book=0.8, current_ratio=1.1, ltd_to_working_capital=1.9,
          profitable_years_10y=7, consecutive_annual_loss_years=3,
          altman_z_score=1.9, consecutive_dividend_years=0, debt_to_equity=1.6,
          price_to_net_tangible_assets=1.1, accruals_ratio=0.14,
          market_cap=420_000_000, ncav_to_market_cap=0.18),
        added="2024-04-02",
        falsifier="Two annual losses in a row. It fired and I acted on it.",
        notes=[("2025-06-18", "Sold on the loss-streak rule, not on the price. The "
                              "streak is its own two-filing confirmation.")])
s["position"] = {"shares": 210, "cost_basis": 40.10, "opened": "2024-04-02"}
s["exit"] = {"date": "2025-06-18", "reason": "Thesis broke", "price": 41.78,
             "return_pct": 4.2,
             "profile": {"file": "graham.yaml", "id": "graham",
                         "name": "Graham", "version": 1},
             "governing": True,
             "signal_at_exit": "Sell signal", "rule_triggered": True}
r = snap(s, "graham",
         M(pe_3y_avg_eps=12.8, price_to_book=1.1, graham_combined_multiple=14.1,
           current_ratio=2.3, ltd_to_working_capital=0.5, profitable_years_10y=10,
           consecutive_annual_loss_years=0, altman_z_score=3.3, eps_growth_10y=41,
           consecutive_dividend_years=11, debt_to_equity=0.6,
           price_to_net_tangible_assets=1.4, accruals_ratio=0.05,
           market_cap=890_000_000, ncav_to_market_cap=0.31),
         "2024-04-02", 40.10)
expect("ORVL entry verdict", r["verdict"], "buy")
SECS.append(s)

# 8. The panic sell that kept rising. No rule said sell; the record says so.
s = sec("SBRK", "Seabright Retail", "previous", 88.40,
        M(peg_trailing=1.08, eps_cagr_5y=16.2, debt_to_equity=0.31,
          revenue_cagr_3y=10.8, eps_minus_revenue_cagr_spread_5y=4.4,
          inventory_minus_revenue_growth_yoy=1.4,
          receivables_minus_revenue_growth_yoy=1.9, pe_to_own_5y_median_pe=1.02,
          gross_margin_change_3y=1.1, interest_coverage=9.8,
          fcf_ttm=230_000_000, net_cash_to_market_cap=0.02,
          institutional_ownership_pct=51),
        added="2024-09-05",
        falsifier="Same-store sales negative for three quarters. It never fired.",
        notes=[("2025-02-04", "Nothing in the rules said sell. The stock dropped 22% in "
                              "three weeks on a sector story and I sold anyway."),
               ("2026-07-30", "Up 46% since. This is the most expensive entry in the "
                              "journal and the only one where every check was clear the "
                              "day I exited.")])
s["position"] = {"shares": 140, "cost_basis": 68.50, "opened": "2024-09-05"}
s["exit"] = {"date": "2025-02-04", "reason": "Panic", "price": 60.42,
             "return_pct": -11.8,
             "profile": {"file": "lynch.yaml", "id": "lynch",
                         "name": "Lynch", "version": 1},
             "governing": True,
             "signal_at_exit": "No signal", "rule_triggered": False}
r = snap(s, "lynch",
         M(peg_trailing=0.79, eps_cagr_5y=16.4, debt_to_equity=0.28,
           revenue_cagr_3y=11.2, eps_minus_revenue_cagr_spread_5y=4.2,
           inventory_minus_revenue_growth_yoy=1.8,
           receivables_minus_revenue_growth_yoy=2.2, pe_to_own_5y_median_pe=0.85,
           gross_margin_change_3y=0.9, interest_coverage=9.1,
           fcf_ttm=210_000_000, net_cash_to_market_cap=0.03,
           institutional_ownership_pct=44),
         "2024-09-05", 68.50)
expect("SBRK entry verdict", r["verdict"], "buy")
SECS.append(s)

# ------------------------------------------------------------------- ideas

# 9. The candidate the profiles disagree about: a fairly priced grower that
#    Lynch and Buffett would buy and Graham and Discount Closure would not.
s = sec("ASHW", "Ashworth Precision", "ideas", 71.40,
        M(peg_trailing=0.94, eps_cagr_5y=15.8, debt_to_equity=0.21,
          revenue_cagr_3y=10.6, eps_minus_revenue_cagr_spread_5y=6.6,
          inventory_minus_revenue_growth_yoy=2.3,
          receivables_minus_revenue_growth_yoy=1.1, pe_to_own_5y_median_pe=0.88,
          gross_margin_change_3y=0.6, interest_coverage=18.4,
          fcf_ttm=188_000_000, net_cash_to_market_cap=0.09,
          insider_net_buying_6m=42_000, institutional_ownership_pct=38,
          roic_median_5y=19.8, total_debt_to_ebitda=0.9, owner_earnings_yield=6.4,
          gross_margin_range_5y=2.9, fcf_margin_median_5y=14.1, fcf_margin_ttm=14.6,
          cash_conversion_median_5y=0.94, diluted_share_count_change_5y=-5.8,
          diluted_share_count_change_3y=-3.4, roe_median_5y=18.9,
          revenue_cagr_5y=9.2, ni_minus_revenue_cagr_spread_5y=0.8,
          goodwill_intangibles_to_assets=12.0, effective_tax_rate_median_5y=20.6,
          current_ratio=2.6, payout_to_fcf_median_5y=31,
          pe_3y_avg_eps=16.8, price_to_book=2.9, graham_combined_multiple=48.7,
          ev_ebit_to_own_5y_median=0.91, ev_to_ebit=11.2, altman_z_score=5.2,
          net_debt_to_ebitda=0.4, operating_income_ttm=240_000_000,
          fcf_yield_on_ev=6.1, revenue_change_yoy=9.4,
          gross_margin_vs_3y_median=0.5, diluted_share_count_change_ttm=-1.2,
          accruals_ratio=0.02, market_cap=2_900_000_000, ncav_to_market_cap=0.05,
          ltd_to_working_capital=0.3, price_to_net_tangible_assets=4.8,
          profitable_years_10y=10, consecutive_annual_loss_years=0,
          consecutive_dividend_years=6, eps_growth_10y=210),
        added="2026-07-12",
        falsifier="Insider ownership falling below 6%, or aerospace contract "
                  "concentration rising above 40% of revenue.",
        notes=[("2026-07-12", "Down 8% on the year with no change in the fundamentals I "
                              "can find. Lynch and Buffett both say buy; Graham won't "
                              "touch the book multiple and Discount Closure sees no "
                              "discount. Same company, four honest answers.")])
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 71.40, "fcf_ttm": 188, "shares": 41,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-07-12"}
expect("ASHW lynch", evaluate_buy(s["metrics"], PROFILES["lynch"])["verdict"], "buy")
expect("ASHW buffett", evaluate_buy(s["metrics"], PROFILES["buffett"])["verdict"], "buy")
expect("ASHW graham", evaluate_buy(s["metrics"], PROFILES["graham"])["verdict"], "no_buy")
expect("ASHW dc", evaluate_buy(s["metrics"], PROFILES["discount_closure"])["verdict"], "no_buy")
SECS.append(s)

# 10. Quality is there, price is not: every profile says no for a price reason.
s = sec("GRNL", "Grenelle Beverage", "ideas", 96.10,
        M(roic_median_5y=16.2, total_debt_to_ebitda=2.2, owner_earnings_yield=3.9,
          interest_coverage=6.4, gross_margin_range_5y=2.2,
          fcf_margin_median_5y=9.2, fcf_margin_ttm=9.6,
          cash_conversion_median_5y=0.92, diluted_share_count_change_5y=0.8,
          diluted_share_count_change_3y=0.5, roe_median_5y=17.1,
          revenue_cagr_5y=6.4, ni_minus_revenue_cagr_spread_5y=0.4,
          goodwill_intangibles_to_assets=31.0, effective_tax_rate_median_5y=23.4,
          current_ratio=1.4, payout_to_fcf_median_5y=68,
          peg_trailing=2.82, eps_cagr_5y=8.8, debt_to_equity=0.62,
          pe_3y_avg_eps=26.1, price_to_book=5.8, graham_combined_multiple=151.4,
          ev_ebit_to_own_5y_median=1.02, ev_to_ebit=18.2, altman_z_score=4.4,
          net_debt_to_ebitda=2.2, operating_income_ttm=310_000_000,
          fcf_yield_on_ev=4.1, fcf_ttm=240_000_000),
        added="2026-06-28",
        falsifier="Not yet written.",
        notes=[("2026-06-28", "Quality is genuinely there. Everything failing is on the "
                              "valuation side, which means this is a watchlist item and a "
                              "price alert, not a decision.")])
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 96.10, "fcf_ttm": 240, "shares": 61,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-06-28"}
expect("GRNL buffett", evaluate_buy(s["metrics"], PROFILES["buffett"])["verdict"], "no_buy")
expect("GRNL lynch", evaluate_buy(s["metrics"], PROFILES["lynch"])["verdict"], "no_buy")
SECS.append(s)

# 11. Hypergrowth: fails Lynch's band at the top — growth too fast to trust,
#    which is the distinctive part of the rule.
s = sec("VTHM", "Vantham Semiconductor", "ideas", 188.90,
        M(peg_trailing=1.67, eps_cagr_5y=41.0, debt_to_equity=0.92,
          revenue_cagr_3y=28.4, eps_minus_revenue_cagr_spread_5y=18.6,
          inventory_minus_revenue_growth_yoy=11.2,
          receivables_minus_revenue_growth_yoy=8.4, pe_to_own_5y_median_pe=1.61,
          gross_margin_change_3y=4.2, interest_coverage=3.1,
          fcf_ttm=120_000_000, net_cash_to_market_cap=-0.08,
          institutional_ownership_pct=84),
        added="2026-07-30",
        falsifier="Not applicable. The growth band excludes it before valuation matters.",
        notes=[("2026-07-30", "Up 84% this year and it is genuinely hard to look at this "
                              "and not want in. That reaction is exactly why the growth "
                              "ceiling is set where it is.")])
_r = evaluate_buy(s["metrics"], PROFILES["lynch"])
expect("VTHM lynch", _r["verdict"], "no_buy")
assert "eps_cagr_5y" in [m for c in _r["causes"] for m in c["metrics"]]
SECS.append(s)

# 12. Too little data to call, under every lens. Grey is its own state.
s = sec("BRDG", "Bridgeport Marine", "ideas", 33.75,
        M(interest_coverage=12.1, current_ratio=2.4, pe_3y_avg_eps=11.8,
          net_debt_to_ebitda=1.2, debt_to_equity=0.4, fcf_ttm=56_000_000),
        added="2026-08-01",
        falsifier="Not yet written.",
        notes=[("2026-08-01", "Six values available. Not enough for any profile to form "
                              "a view, so every lens shows Can't say rather than "
                              "pretending the missing data is a pass.")])
for pid in PROFILES:
    expect(f"BRDG {pid}", evaluate_buy(s["metrics"], PROFILES[pid])["verdict"],
           "cant_say")
SECS.append(s)


out = ROOT / "data.template" / "sample.json"
out.write_text(json.dumps({"securities": SECS,
                           "metrics_vocabulary": "metric-bank/1"},
                          indent=2, ensure_ascii=False) + "\n",
               encoding="utf-8")
print(f"wrote {out} ({len(SECS)} securities)")
