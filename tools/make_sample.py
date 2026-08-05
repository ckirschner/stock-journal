"""Builds data.template/sample.json.

All companies and figures are invented. Run from the project root:
    python tools/make_sample.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.rules import default_ruleset          # noqa: E402
from engine.evaluate import evaluate              # noqa: E402

RS = default_ruleset()

M = lambda **kw: kw  # noqa: E731


def sec(ticker, name, bucket, price, metrics, **extra):
    s = {
        "ticker": ticker, "name": name, "bucket": bucket,
        "added": extra.pop("added", "2026-01-01"),
        "price": price, "metrics": metrics, "history": {},
        "entry_snapshot": None, "override": None, "ev": None,
        "falsifier": extra.pop("falsifier", ""),
        "notes": [{"date": d, "text": t} for d, t in extra.pop("notes", [])],
        "position": None, "exit": None,
    }
    s.update(extra)
    return s


def snap(s, entry_metrics, opened, version=3, price=None):
    stub = dict(s)
    stub["metrics"] = entry_metrics
    stub["bucket"] = "ideas"
    s["entry_snapshot"] = {
        "frozen": opened + "T00:00:00+00:00",
        "ruleset_version": version,
        "metrics": entry_metrics,
        "price": price,
        "result": evaluate(stub, RS, which="now"),
    }
    return s


SECS = []

# ---------------------------------------------------------------- holdings
s = sec("HLDN", "Halden Industrial Group", "holdings", 84.20,
        M(roic=17.4, gross_margin=41.2, fcf_margin=12.8, insider_own=6.1,
          net_debt_ebitda=1.4, interest_cover=11.2, current_ratio=2.1,
          share_change_5y=-4.2, fcf_yield=5.6, pe=18.4, peg=1.05, ev_ebit=13.1,
          rev_cagr_5y=8.4, eps_cagr_5y=12.1, op_margin_trend=1.8),
        added="2023-04-11",
        falsifier="Two consecutive quarters of gross margin below 38%, or net debt/EBITDA "
                  "back above 2.5x. Either one means the pricing power argument I bought "
                  "this on was wrong.",
        notes=[("2023-04-11", "Bought after the distribution contract loss knocked 30% off. "
                              "Thesis was that the loss was one customer, not the business. "
                              "Margins held through it, which is the tell.")])
s["position"] = {"shares": 180, "cost_basis": 61.05, "opened": "2023-04-11"}
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 84.20, "fcf_ttm": 412, "shares": 78,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-07-02"}
SECS.append(snap(s, M(roic=15.1, gross_margin=39.8, fcf_margin=11.2, insider_own=6.4,
                      net_debt_ebitda=1.9, interest_cover=8.7, current_ratio=1.9,
                      share_change_5y=-2.8, fcf_yield=7.9, pe=13.2, peg=0.71,
                      ev_ebit=9.8, rev_cagr_5y=7.1, eps_cagr_5y=10.4,
                      op_margin_trend=1.1), "2023-04-11", price=61.05))

s = sec("CVSW", "Corvus Software", "holdings", 214.60,
        M(roic=24.1, gross_margin=78.4, fcf_margin=22.6, insider_own=2.1,
          net_debt_ebitda=0.2, interest_cover=31.0, current_ratio=2.8,
          share_change_5y=3.1, fcf_yield=2.4, pe=44.8, peg=2.31, ev_ebit=36.2,
          rev_cagr_5y=16.8, eps_cagr_5y=19.4, op_margin_trend=3.2),
        added="2022-09-02",
        falsifier="Net revenue retention below 105%, or a full year of revenue growth "
                  "under 12%. Either would mean I'm paying a growth multiple for a "
                  "mature business.",
        notes=[("2022-09-02", "Bought on the post-guidance selloff."),
               ("2026-06-14", "The business hasn't deteriorated at all. Every quality "
                              "metric improved. What broke is the valuation, and only "
                              "because the price ran. Hardest kind of hold to think "
                              "about clearly.")])
s["position"] = {"shares": 64, "cost_basis": 118.40, "opened": "2022-09-02"}
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 214.60, "fcf_ttm": 690, "shares": 141,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-07-02"}
SECS.append(snap(s, M(roic=21.8, gross_margin=77.1, fcf_margin=19.8, insider_own=3.4,
                      net_debt_ebitda=0.4, interest_cover=24.5, current_ratio=2.4,
                      share_change_5y=1.9, fcf_yield=5.1, pe=21.6, peg=0.96,
                      ev_ebit=17.4, rev_cagr_5y=15.2, eps_cagr_5y=17.1,
                      op_margin_trend=2.4), "2022-09-02", price=118.40))

s = sec("PMBF", "Pemberton Foods", "holdings", 29.14,
        M(roic=6.2, gross_margin=24.1, fcf_margin=2.1, insider_own=1.4,
          net_debt_ebitda=4.1, interest_cover=2.4, current_ratio=0.9,
          share_change_5y=6.8, fcf_yield=3.1, pe=26.4, peg=4.10, ev_ebit=19.8,
          rev_cagr_5y=1.8, eps_cagr_5y=-3.4, op_margin_trend=-2.9),
        added="2024-01-22",
        falsifier="I said I'd be wrong if operating margin fell three years running. "
                  "It has. This is the falsifier firing, not a new opinion formed "
                  "after the drawdown.",
        notes=[("2024-01-22", "Cheap on normalised earnings, family-controlled, boring."),
               ("2026-05-08", "Interest coverage broke the knockout in Q2. I have been "
                              "telling myself the input costs are cyclical for three "
                              "quarters. The entry snapshot says every single reason I "
                              "bought this is now false.")])
s["position"] = {"shares": 240, "cost_basis": 38.90, "opened": "2024-01-22"}
s["ev"] = {"method": "scenario",
           "inputs": {"bear_value": 21, "bear_prob": 45, "base_value": 31,
                      "base_prob": 40, "bull_value": 44, "bull_prob": 15},
           "computed": "2026-05-08"}
SECS.append(snap(s, M(roic=13.4, gross_margin=31.8, fcf_margin=9.4, insider_own=2.2,
                      net_debt_ebitda=2.1, interest_cover=6.8, current_ratio=1.6,
                      share_change_5y=0.4, fcf_yield=6.8, pe=14.1, peg=0.98,
                      ev_ebit=11.2, rev_cagr_5y=5.4, eps_cagr_5y=9.1,
                      op_margin_trend=0.6), "2024-01-22", price=38.90))

s = sec("KTRA", "Kestrel Aerospace", "holdings", 47.80,
        M(roic=8.1, gross_margin=22.4, fcf_margin=1.2, insider_own=4.2,
          net_debt_ebitda=5.2, interest_cover=2.1, current_ratio=1.1,
          share_change_5y=11.4, fcf_yield=1.4, pe=38.2, peg=3.20, ev_ebit=28.4,
          rev_cagr_5y=9.8, eps_cagr_5y=2.1, op_margin_trend=-1.4),
        added="2025-11-14",
        falsifier="Left blank at purchase. That absence is itself part of the record.",
        notes=[("2025-11-14", "Bought this the same afternoon I read the backlog release. "
                              "Did not run the numbers first.")])
s["position"] = {"shares": 95, "cost_basis": 69.20, "opened": "2025-11-14"}
s["override"] = {"date": "2025-11-14", "verdict": "Avoid",
                 "failed": ["net_debt_ebitda", "interest_cover"],
                 "reason": "Backlog is at a record and the debt is from the acquisition, "
                           "which closes next year. I think the leverage number is temporary."}
SECS.append(snap(s, M(roic=9.4, gross_margin=23.8, fcf_margin=2.8, insider_own=4.4,
                      net_debt_ebitda=4.4, interest_cover=2.8, current_ratio=1.2,
                      share_change_5y=9.1, fcf_yield=2.2, pe=31.4, peg=2.84,
                      ev_ebit=24.1, rev_cagr_5y=10.2, eps_cagr_5y=4.8,
                      op_margin_trend=-0.8), "2025-11-14", price=69.20))

s = sec("LNWD", "Lindenwood Materials", "holdings", 52.35,
        M(roic=14.8, gross_margin=29.4, net_debt_ebitda=1.8, interest_cover=7.4,
          current_ratio=1.8, fcf_yield=5.9, pe=16.2, rev_cagr_5y=6.1),
        added="2026-05-30",
        falsifier="Not yet written. The position is open without one, and the tool should "
                  "keep saying so until it's filled in.",
        notes=[("2026-05-30", "Spun off in March, so there are only five quarters of "
                              "filings. Seven of the fifteen metrics have no data yet and "
                              "are hidden rather than guessed at.")])
s["position"] = {"shares": 120, "cost_basis": 49.10, "opened": "2026-05-30"}
SECS.append(snap(s, M(roic=14.2, gross_margin=29.1, net_debt_ebitda=1.9, interest_cover=7.1,
                      current_ratio=1.7, fcf_yield=6.4, pe=15.1, rev_cagr_5y=6.0),
                 "2026-05-30", price=49.10))

# ---------------------------------------------------------------- previous
s = sec("ORVL", "Orvalt Chemical", "previous", 34.10,
        M(roic=5.1, gross_margin=19.8, fcf_margin=1.4, insider_own=0.9,
          net_debt_ebitda=4.8, interest_cover=1.9, current_ratio=0.8,
          share_change_5y=14.2, fcf_yield=2.1, pe=41.0, peg=6.2, ev_ebit=31.4,
          rev_cagr_5y=-1.2, eps_cagr_5y=-8.4, op_margin_trend=-4.1),
        added="2024-04-02",
        falsifier="Margin compression for two straight years. It fired and I acted on it.",
        notes=[("2025-06-18", "Sold on the falsifier, not on the price.")])
s["position"] = {"shares": 210, "cost_basis": 40.10, "opened": "2024-04-02"}
s["exit"] = {"date": "2025-06-18", "reason": "Thesis broke", "price": 41.78,
             "return_pct": 4.2, "ruleset_version": 3,
             "signal_at_exit": "Exit", "rule_triggered": True}
SECS.append(snap(s, M(roic=14.8, gross_margin=28.4, fcf_margin=8.9, insider_own=2.8,
                      net_debt_ebitda=2.2, interest_cover=6.1, current_ratio=1.7,
                      share_change_5y=1.1, fcf_yield=6.9, pe=12.8, peg=0.88,
                      ev_ebit=10.4, rev_cagr_5y=6.8, eps_cagr_5y=11.2,
                      op_margin_trend=1.4), "2024-04-02", price=40.10))

s = sec("SBRK", "Seabright Retail", "previous", 88.40,
        M(roic=16.2, gross_margin=38.1, fcf_margin=10.4, insider_own=8.2,
          net_debt_ebitda=1.6, interest_cover=9.8, current_ratio=2.0,
          share_change_5y=-3.4, fcf_yield=5.2, pe=19.4, peg=1.08, ev_ebit=14.2,
          rev_cagr_5y=7.4, eps_cagr_5y=11.8, op_margin_trend=1.6),
        added="2024-09-05",
        falsifier="Same-store sales negative for three quarters. It never fired.",
        notes=[("2025-02-04", "Nothing in the rules said sell. The stock dropped 22% in "
                              "three weeks on a sector story and I sold anyway."),
               ("2026-07-30", "Up 46% since. This is the most expensive entry in the "
                              "journal and the only one where every metric was green the "
                              "day I exited.")])
s["position"] = {"shares": 140, "cost_basis": 68.50, "opened": "2024-09-05"}
s["exit"] = {"date": "2025-02-04", "reason": "Panic", "price": 60.42,
             "return_pct": -11.8, "ruleset_version": 3,
             "signal_at_exit": "Hold", "rule_triggered": False}
SECS.append(snap(s, M(roic=15.4, gross_margin=37.2, fcf_margin=9.8, insider_own=8.4,
                      net_debt_ebitda=1.8, interest_cover=8.9, current_ratio=1.9,
                      share_change_5y=-2.1, fcf_yield=7.4, pe=13.8, peg=0.79,
                      ev_ebit=10.8, rev_cagr_5y=7.1, eps_cagr_5y=10.9,
                      op_margin_trend=1.2), "2024-09-05", price=68.50))

s = sec("TRNT", "Trinnet Logistics", "previous", 131.20,
        M(roic=18.4, gross_margin=32.1, fcf_margin=11.2, insider_own=5.1,
          net_debt_ebitda=1.1, interest_cover=14.2, current_ratio=2.2,
          share_change_5y=-6.1, fcf_yield=3.1, pe=31.2, peg=2.84, ev_ebit=24.8,
          rev_cagr_5y=11.4, eps_cagr_5y=16.2, op_margin_trend=2.1),
        added="2023-03-01",
        falsifier="FCF yield below 3.5% with no growth acceleration. Fired at 3.1%.",
        notes=[("2025-09-30", "Sold into strength on the valuation rule. The rule neither "
                              "made nor cost me anything, which is the boring outcome you "
                              "want most of the time.")])
s["position"] = {"shares": 88, "cost_basis": 60.00, "opened": "2023-03-01"}
s["exit"] = {"date": "2025-09-30", "reason": "Hit valuation", "price": 127.24,
             "return_pct": 112.4, "ruleset_version": 3,
             "signal_at_exit": "Trim", "rule_triggered": True}
SECS.append(snap(s, M(roic=16.8, gross_margin=30.4, fcf_margin=9.4, insider_own=5.8,
                      net_debt_ebitda=1.9, interest_cover=9.1, current_ratio=1.8,
                      share_change_5y=-4.2, fcf_yield=8.1, pe=11.4, peg=0.62,
                      ev_ebit=8.9, rev_cagr_5y=10.8, eps_cagr_5y=14.8,
                      op_margin_trend=1.8), "2023-03-01", price=60.00))

# ------------------------------------------------------------------- ideas
s = sec("ASHW", "Ashworth Precision", "ideas", 71.40,
        M(roic=19.8, gross_margin=44.2, fcf_margin=14.1, insider_own=11.2,
          net_debt_ebitda=0.9, interest_cover=18.4, current_ratio=2.6,
          share_change_5y=-5.8, fcf_yield=6.4, pe=15.8, peg=0.94, ev_ebit=11.2,
          rev_cagr_5y=9.2, eps_cagr_5y=14.1, op_margin_trend=2.4),
        added="2026-07-12",
        falsifier="Insider ownership falling below 6%, or aerospace contract "
                  "concentration rising above 40% of revenue.",
        notes=[("2026-07-12", "Down 8% on the year with no change in the fundamentals I "
                              "can find. Family still holds 11%. This is the shape Lynch "
                              "described. Boring name, industry nobody covers.")])
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 71.40, "fcf_ttm": 188, "shares": 41,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-07-12"}
SECS.append(s)

s = sec("GRNL", "Grenelle Beverage", "ideas", 96.10,
        M(roic=13.1, gross_margin=47.8, fcf_margin=9.2, insider_own=1.8,
          net_debt_ebitda=2.2, interest_cover=6.4, current_ratio=1.4,
          share_change_5y=0.8, fcf_yield=4.1, pe=24.8, peg=1.84, ev_ebit=18.2,
          rev_cagr_5y=6.4, eps_cagr_5y=8.8, op_margin_trend=0.4),
        added="2026-06-28",
        falsifier="Not yet written.",
        notes=[("2026-06-28", "Quality is genuinely there. Everything failing is on the "
                              "valuation side, which means this is a watchlist item and a "
                              "price alert, not a decision.")])
s["ev"] = {"method": "reverse_dcf",
           "inputs": {"price": 96.10, "fcf_ttm": 240, "shares": 61,
                      "discount_rate": 9.0, "terminal_growth": 2.5},
           "computed": "2026-06-28"}
SECS.append(s)

s = sec("VTHM", "Vantham Semiconductor", "ideas", 188.90,
        M(roic=11.2, gross_margin=52.1, fcf_margin=4.1, insider_own=0.9,
          net_debt_ebitda=3.8, interest_cover=3.1, current_ratio=1.3,
          share_change_5y=18.4, fcf_yield=0.9, pe=68.4, peg=2.94, ev_ebit=52.1,
          rev_cagr_5y=22.4, eps_cagr_5y=24.1, op_margin_trend=4.2),
        added="2026-07-30",
        falsifier="Not applicable. Knocked out on leverage before valuation matters.",
        notes=[("2026-07-30", "Up 84% this year and it is genuinely hard to look at this "
                              "and not want in. That reaction is exactly why the knockout "
                              "is set where it is.")])
SECS.append(s)

s = sec("BRDG", "Bridgeport Marine", "ideas", 33.75,
        M(roic=15.1, net_debt_ebitda=1.2, interest_cover=12.1, current_ratio=2.4,
          fcf_yield=7.2, pe=11.8),
        added="2026-08-01",
        falsifier="Not yet written.",
        notes=[("2026-08-01", "Six metrics available. Not enough to form a view, so the tool "
                              "shows grey rather than pretending the missing data is a pass.")])
SECS.append(s)

out = Path(__file__).resolve().parent.parent / "data.template" / "sample.json"
out.write_text(json.dumps({"securities": SECS}, indent=2, ensure_ascii=False),
               encoding="utf-8")
print(f"wrote {out} ({len(SECS)} securities)")
