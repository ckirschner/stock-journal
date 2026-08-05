"""Metric definitions.

This module is the only place a metric is *described*. The UI renders whatever
this hands it, so adding a metric here is the whole job of adding a metric.

fmt      how the value is displayed: pct, pctd (signed), ppt, x, ratio
dir      "high" = bigger is better, "low" = smaller is better
mode     default weight: knockout | required | optional
"""

DEFAULT_SCHEMA = [
    {
        "id": "quality",
        "title": "Quality of the business",
        "metrics": [
            {
                "id": "roic", "label": "Return on invested capital",
                "fmt": "pct", "dir": "high", "threshold": 12.0, "mode": "required",
                "tip": "Profit generated per dollar of capital the business actually employs. "
                       "Sustained ROIC above the cost of capital is the clearest quantitative "
                       "fingerprint of a moat. A business earning 20% on capital for a decade "
                       "is fending something off.",
                "who": "Buffett · Greenblatt",
            },
            {
                "id": "gross_margin", "label": "Gross margin",
                "fmt": "pct", "dir": "high", "threshold": 35.0, "mode": "optional",
                "tip": "What's left of each sales dollar after the direct cost of the product. "
                       "High and stable margins suggest pricing power; margins that erode year "
                       "over year usually mean competition arrived.",
                "who": "Buffett",
            },
            {
                "id": "fcf_margin", "label": "Free cash flow margin",
                "fmt": "pct", "dir": "high", "threshold": 8.0, "mode": "required",
                "tip": "Free cash flow as a share of revenue. Earnings are an opinion, cash is a "
                       "fact. A company reporting profits it never converts to cash is the "
                       "single most common value trap.",
                "who": "Buffett · Klarman",
            },
            {
                "id": "insider_own", "label": "Insider ownership",
                "fmt": "pct", "dir": "high", "threshold": 3.0, "mode": "optional",
                "tip": "Share of the company held by executives and directors. Lynch's point was "
                       "blunt: insiders sell for a hundred reasons but buy for exactly one.",
                "who": "Lynch",
            },
        ],
    },
    {
        "id": "health",
        "title": "Financial health",
        "metrics": [
            {
                "id": "net_debt_ebitda", "label": "Net debt / EBITDA",
                "fmt": "x", "dir": "low", "threshold": 2.5, "mode": "knockout",
                "tip": "Years of current earnings it would take to clear the debt. Above roughly "
                       "3x, the lenders start making the decisions instead of management. This is "
                       "a knockout because leverage is what turns a bad year into a permanent loss.",
                "who": "Graham · Klarman",
            },
            {
                "id": "interest_cover", "label": "Interest coverage",
                "fmt": "x", "dir": "high", "threshold": 5.0, "mode": "knockout",
                "tip": "Operating profit divided by interest expense: how many times over the "
                       "company can pay its lenders. Graham wanted a wide margin here precisely "
                       "because it's the number that goes to zero fastest in a downturn.",
                "who": "Graham",
            },
            {
                "id": "current_ratio", "label": "Current ratio",
                "fmt": "x", "dir": "high", "threshold": 1.5, "mode": "optional",
                "tip": "Short-term assets over short-term obligations. Below 1.0 the company needs "
                       "to raise money or sell something to get through the year.",
                "who": "Graham",
            },
            {
                "id": "share_change_5y", "label": "Share count, 5-year change",
                "fmt": "pctd", "dir": "low", "threshold": 0.0, "mode": "optional",
                "tip": "Whether your slice of the business is growing or shrinking. Steady buybacks "
                       "quietly compound your ownership; steady issuance quietly dilutes it, and it "
                       "rarely shows up in the headline growth rate.",
                "who": "Buffett",
            },
        ],
    },
    {
        "id": "value",
        "title": "Valuation",
        "metrics": [
            {
                "id": "fcf_yield", "label": "Free cash flow yield",
                "fmt": "pct", "dir": "high", "threshold": 5.0, "mode": "required",
                "tip": "Free cash flow divided by market value. Roughly what it would pay you "
                       "if it handed over all its spare cash. Compare it to the 10-year Treasury: if "
                       "you're not being paid more than the risk-free rate, you're being paid to take "
                       "risk for free.",
                "who": "Buffett",
            },
            {
                "id": "pe", "label": "Price / earnings (TTM)",
                "fmt": "x", "dir": "low", "threshold": 22.0, "mode": "optional",
                "tip": "Price divided by the last twelve months of earnings. Useful mostly as a "
                       "comparison against the company's own history and its industry. An "
                       "absolute P/E number in isolation says very little.",
                "who": "Lynch · Graham",
            },
            {
                "id": "peg", "label": "PEG ratio",
                "fmt": "x", "dir": "low", "threshold": 1.2, "mode": "optional",
                "tip": "P/E divided by the earnings growth rate. Lynch's shorthand: a fairly priced "
                       "growth company trades at a P/E roughly equal to its growth rate, so anything "
                       "meaningfully under 1.0 is worth a hard look.",
                "who": "Lynch",
            },
            {
                "id": "ev_ebit", "label": "EV / EBIT",
                "fmt": "x", "dir": "low", "threshold": 15.0, "mode": "optional",
                "tip": "Total cost to buy the whole business, debt included, against its operating "
                       "profit. Harder to distort than P/E because it can't be flattered by a "
                       "leveraged balance sheet.",
                "who": "Greenblatt",
            },
        ],
    },
    {
        "id": "momentum",
        "title": "Fundamental momentum",
        "metrics": [
            {
                "id": "rev_cagr_5y", "label": "Revenue CAGR, 5-year",
                "fmt": "pct", "dir": "high", "threshold": 5.0, "mode": "optional",
                "tip": "Compound annual sales growth over five years. Smooths out the single blowout "
                       "quarter that makes a flat business look like a grower.",
                "who": "Lynch",
            },
            {
                "id": "eps_cagr_5y", "label": "EPS CAGR, 5-year",
                "fmt": "pct", "dir": "high", "threshold": 8.0, "mode": "optional",
                "tip": "Compound annual growth in per-share earnings. Read it against revenue growth: "
                       "if EPS is outrunning sales for years, check whether it's real margin expansion "
                       "or just buybacks.",
                "who": "Lynch · Buffett",
            },
            {
                "id": "op_margin_trend", "label": "Operating margin trend, 3-year",
                "fmt": "ppt", "dir": "high", "threshold": 0.0, "mode": "optional",
                "tip": "Change in operating margin over three years, in percentage points. Direction "
                       "matters more than level. A widening margin usually means the moat is "
                       "holding, a narrowing one means it isn't.",
                "who": "Buffett",
            },
        ],
    },
]

# Expected-value methods. Each assumption is an input the user supplies;
# the result is always computed, never typed.
EV_METHODS = {
    "reverse_dcf": {
        "label": "Reverse DCF",
        "blurb": "Don't forecast. Invert. Ask what growth rate today's price already "
                 "requires, then decide whether the market is asking too much or too little.",
        "who": "Mauboussin · Rappaport",
        "inputs": [
            ("price", "Current price", "The market's number. Everything else is solved against it."),
            ("fcf_ttm", "Free cash flow (TTM)", "Trailing twelve months of free cash flow, in millions."),
            ("shares", "Shares outstanding", "Diluted, in millions."),
            ("discount_rate", "Discount rate %", "Your required return. Set it once and leave it alone. "
                                                 "Moving it per stock is how a DCF becomes a rationalisation."),
            ("terminal_growth", "Terminal growth %", "Long-run growth after year 10. Above about 3% you're "
                                                     "claiming the company outgrows the economy forever."),
        ],
        "output": ("implied_growth", "Implied growth"),
    },
    "scenario": {
        "label": "Scenario weighted",
        "blurb": "Bear, base and bull with explicit probabilities. The bear case is entered "
                 "first, by rule, so downside gets estimated before upside.",
        "who": "Klarman · Greenblatt",
        "inputs": [
            ("bear_value", "Bear value per share", "What it's worth if the thing you're worried about happens."),
            ("bear_prob", "Bear probability %", "Entered first. Probabilities must total 100%."),
            ("base_value", "Base value per share", "No recovery, no further deterioration."),
            ("base_prob", "Base probability %", "The boring outcome, which is usually the likeliest."),
            ("bull_value", "Bull value per share", "The thesis works."),
            ("bull_prob", "Bull probability %", "Whatever is left after bear and base."),
        ],
        "output": ("weighted_value", "Weighted value"),
    },
    "owner_earnings": {
        "label": "Owner earnings + margin of safety",
        "blurb": "Normalised free cash flow capitalised at your discount rate, then discounted "
                 "again by a required margin of safety. The margin isn't a return target. "
                 "It's protection against your own estimation error.",
        "who": "Buffett · Graham",
        "inputs": [
            ("owner_earnings", "Owner earnings", "Net income + depreciation − maintenance capex, in millions."),
            ("shares", "Shares outstanding", "Diluted, in millions."),
            ("growth", "Sustainable growth %", "What the business can grow at without extra capital."),
            ("discount_rate", "Discount rate %", "Your required return."),
            ("margin_of_safety", "Margin of safety %", "Graham's traditional number is 30%. The wider your "
                                                       "uncertainty, the wider this should be."),
        ],
        "output": ("buy_below", "Buy below"),
    },
}

EXIT_REASONS = [
    "Thesis broke",
    "Hit valuation",
    "Better opportunity",
    "Risk limit",
    "Panic",
]


def flat_metrics(schema=None):
    """Every metric definition, ungrouped."""
    schema = schema or DEFAULT_SCHEMA
    return [m for g in schema for m in g["metrics"]]


def metric_by_id(metric_id, schema=None):
    for m in flat_metrics(schema):
        if m["id"] == metric_id:
            return m
    return None
