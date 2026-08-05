"""Expected value.

There is deliberately no field anywhere that accepts a target price. The user
supplies assumptions; the number is solved for. When the estimate turns out to
be wrong you can then see *which assumption* was wrong, which is the whole
point of writing it down.
"""

from __future__ import annotations


class EVError(ValueError):
    pass


def _f(inputs, key, label=None):
    v = inputs.get(key)
    if v is None or v == "":
        raise EVError(f"{label or key} is required.")
    try:
        return float(v)
    except (TypeError, ValueError):
        raise EVError(f"{label or key} must be a number.")


# ---------------------------------------------------------------- reverse DCF
def _dcf_per_share(fcf, shares, growth, discount, terminal, years=10):
    """Present value per share of a 10-year growth stage plus terminal value."""
    r, g, tg = discount / 100.0, growth / 100.0, terminal / 100.0
    if r <= tg:
        raise EVError("Discount rate must exceed terminal growth.")
    pv, cash = 0.0, fcf
    for year in range(1, years + 1):
        cash *= (1 + g)
        pv += cash / ((1 + r) ** year)
    terminal_value = (cash * (1 + tg)) / (r - tg)
    pv += terminal_value / ((1 + r) ** years)
    return pv / shares


def reverse_dcf(inputs: dict) -> dict:
    """Solve for the growth rate today's price already requires."""
    price = _f(inputs, "price", "Current price")
    fcf = _f(inputs, "fcf_ttm", "Free cash flow")
    shares = _f(inputs, "shares", "Shares outstanding")
    discount = _f(inputs, "discount_rate", "Discount rate")
    terminal = _f(inputs, "terminal_growth", "Terminal growth")

    if shares <= 0:
        raise EVError("Shares outstanding must be positive.")
    if fcf <= 0:
        raise EVError("Reverse DCF needs positive free cash flow. "
                      "For a cash-burning business use scenario weighting instead.")

    lo, hi = -50.0, 60.0
    if _dcf_per_share(fcf, shares, hi, discount, terminal) < price:
        return {
            "value": None,
            "display": ">60%",
            "label": "Implied growth",
            "note": "The price requires more than 60% annual growth for a decade. "
                    "That is not an estimate, it is a warning.",
        }
    if _dcf_per_share(fcf, shares, lo, discount, terminal) > price:
        return {
            "value": None, "display": "<−50%", "label": "Implied growth",
            "note": "The price implies severe permanent decline. Check the inputs.",
        }

    for _ in range(200):
        mid = (lo + hi) / 2
        if _dcf_per_share(fcf, shares, mid, discount, terminal) < price:
            lo = mid
        else:
            hi = mid
    growth = (lo + hi) / 2
    return {
        "value": round(growth, 2),
        "display": f"{growth:.1f}%",
        "label": "Implied growth",
        "note": "This is what the market is already asking the business to do. "
                "Compare it against what the business has actually delivered.",
    }


# ----------------------------------------------------------------- scenarios
def scenario(inputs: dict) -> dict:
    bear_v = _f(inputs, "bear_value", "Bear value")
    bear_p = _f(inputs, "bear_prob", "Bear probability")
    base_v = _f(inputs, "base_value", "Base value")
    base_p = _f(inputs, "base_prob", "Base probability")
    bull_v = _f(inputs, "bull_value", "Bull value")
    bull_p = _f(inputs, "bull_prob", "Bull probability")

    total = bear_p + base_p + bull_p
    if abs(total - 100.0) > 0.01:
        raise EVError(f"Probabilities total {total:.1f}%. They must total 100%.")

    value = (bear_v * bear_p + base_v * base_p + bull_v * bull_p) / 100.0
    downside = bear_v - base_v
    return {
        "value": round(value, 2),
        "display": f"${value:,.2f}",
        "label": "Weighted value",
        "note": f"Bear case is {abs(downside / base_v * 100):.0f}% below base. "
                "If the weighted value is not comfortably above the price, "
                "there is no margin of safety here.",
    }


# ------------------------------------------------------------ owner earnings
def owner_earnings(inputs: dict) -> dict:
    oe = _f(inputs, "owner_earnings", "Owner earnings")
    shares = _f(inputs, "shares", "Shares outstanding")
    growth = _f(inputs, "growth", "Sustainable growth")
    discount = _f(inputs, "discount_rate", "Discount rate")
    mos = _f(inputs, "margin_of_safety", "Margin of safety")

    if shares <= 0:
        raise EVError("Shares outstanding must be positive.")
    r, g = discount / 100.0, growth / 100.0
    if r <= g:
        raise EVError("Discount rate must exceed sustainable growth, "
                      "or the value is infinite.")

    intrinsic = (oe * (1 + g)) / (r - g) / shares
    buy_below = intrinsic * (1 - mos / 100.0)
    return {
        "value": round(buy_below, 2),
        "display": f"${buy_below:,.2f}",
        "label": "Buy below",
        "note": f"Intrinsic value ${intrinsic:,.2f}, less a {mos:.0f}% margin of safety. "
                "The margin is not a return target. It is room to be wrong.",
    }


CALCULATORS = {
    "reverse_dcf": reverse_dcf,
    "scenario": scenario,
    "owner_earnings": owner_earnings,
}


def compute(method: str, inputs: dict) -> dict:
    fn = CALCULATORS.get(method)
    if not fn:
        raise EVError(f"Unknown method: {method}")
    return fn(inputs)
