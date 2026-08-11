> ## Superseded in part — read the addendum alongside this
>
> This document was produced by one consultation and reviewed by a second. The
> review is in `ledger-default-profiles-addendum.md` and it disputes material in
> every profile here.
>
> **Do not take a threshold, tier, or attribution from this file without checking
> the addendum first.**
>
> Three of its findings affect nearly every metric in this document, so section-level
> agreement is not evidence that a given metric survived:
>
> - Every CAGR should use three-year averaged endpoints at both ends, not single-year
>   endpoints. Single-year endpoints let a one-off charge in the base year turn a
>   7% grower into a 20% grower that passes mid-band.
> - Sell confirmation should be keyed to how much one observation can move the
>   estimator, not to window length. Several sell cadences here are unreachable as
>   written — some require nine years of evidence before an exit can fire.
> - The X-of-Y tier quotas assume the criteria are independent evidence. They are
>   heavily correlated, which biases every profile toward passing.
>
> It also finds that entry and exit should not share a measure, that financial
> companies produce confident wrong passes rather than blanks, and that individual
> metrics in all four profiles are misattributed, mis-tiered, or calibrated to a
> world that has changed.
>
> Where the two documents disagree, the addendum is later and better evidenced. It
> marks its own uncertainty in three places; those want checking against primary
> sources before becoming thresholds.
>
> **The two profiles that have since been authored are corrected in code, not
> here.** Neither document has been rewritten and neither will be: this one is
> what the first consultation said, the addendum is what the review challenged
> and when, and merging them would lose the dating that makes either worth
> auditing against. Each profile below carries a header saying which state it
> is in.

# Ledger — Default Rule Profiles

Four profiles. Each metric is computable from SEC EDGAR XBRL plus daily price data.
No target prices, no analyst estimates, no subjective scoring.

Tiers per profile:
- **REQ** — knockout. One red kills the buy verdict regardless of score.
- **CORE** — X of Y must be green.
- **BONUS** — adds to the score, never blocks.

Grey (uncomputable) propagates: a grey REQ metric makes the security grey, not red.
The user decides and logs an override.

Sell column: a number means that metric can force an exit. **BLANK** means it never can.
Sell forms used below:
- `abs` — an absolute level
- `Δentry` — change versus the value recorded at purchase
- `Δmedian` — change versus the trailing 5-year median

All sell triggers require the breach on two consecutive filings before turning red.

---

# Profile 1 — Buffett

> **Authored, and this section is history.** `strategies/buffett/` is
> authoritative; where it and this section differ, it is right and this is the
> record of what it was corrected from. The review's corrections landed in its
> code and `values.yaml` — seven levels moved, five measures were replaced, one
> was added, and the nine-test quota became six questions about the business
> that each have to be answered. Each changed value says in its own `explain`
> what it was, what it is, and which document it came from. Do not take a
> number from below without checking the strategy.

Wonderful business, bought at a sane price, held until the business stops being wonderful.
The defining feature of this profile is that **nine of fifteen sell thresholds are blank.**
Nothing about price can make Ledger tell you to sell one of these. That is the intended
behaviour and the config page should say so out loud when you save it.

| # | Metric | Buy | Sell | Tier |
|---|--------|-----|------|------|
| 1 | ROIC, 5-yr median | ≥ 15% | falls ≥ 33% below entry value AND < 12% abs (`Δentry`) | REQ |
| 2 | Total debt / EBITDA | ≤ 2.5x | > 4.0x (`abs`) | REQ |
| 3 | Owner earnings yield | ≥ 5% | **BLANK** | REQ |
| 4 | Interest coverage | ≥ 8x | < 4x (`abs`) | CORE |
| 5 | Gross margin range, 5-yr | ≤ 6 pp | **BLANK** | CORE |
| 6 | FCF margin, 5-yr median | ≥ 10% | < 0% for 4 quarters (`abs`) | CORE |
| 7 | Cash conversion, 5-yr median | ≥ 0.90 | **BLANK** | CORE |
| 8 | Diluted share count, 5-yr change | ≤ 0% | > +10% over 3 yrs (`abs`) | CORE |
| 9 | ROE, 5-yr median | ≥ 15% | **BLANK** | CORE |
| 10 | Revenue CAGR, 5-yr | ≥ 4% | **BLANK** | CORE |
| 11 | Net income CAGR vs revenue CAGR, 5-yr | NI ≥ Rev − 1 pp | **BLANK** | CORE |
| 12 | Goodwill + intangibles / total assets | ≤ 40% | **BLANK** | CORE |
| 13 | Effective tax rate, 5-yr median | 10%–35% | **BLANK** | BONUS |
| 14 | Current ratio | ≥ 1.0 | **BLANK** | BONUS |
| 15 | Total payout / FCF, 5-yr median | ≤ 80% | **BLANK** | BONUS |

Suggested rollup: 3 REQ, 7 of 9 CORE, 3 BONUS.

### 1. Return on invested capital, 5-year median — REQ

`ROIC = EBIT × (1 − effective tax rate) ÷ (total debt + total equity − cash & equivalents)`,
taken for each of the last five fiscal years, then the median.

**What it means.** How many cents of profit the business earns per dollar that's tied up in
it. A company earning 20 cents on every dollar of capital is a machine; one earning 7 cents
is a job. This is the single number Buffett cares about most.

**Why 15% and not 12%.** Cost of capital for a typical business is somewhere near 8–10%.
At 12% you're looking at a spread of two or three points, which is inside the error bars of
your own calculation. 15% is where the gap becomes wide enough to survive being wrong about
the inputs. It's also roughly where the population thins out: plenty of companies clear 12%
for a year or two, far fewer hold 15% as a five-year median.

**Why the sell threshold is relative, not absolute.** Buffett does not sell because ROIC
printed 14%. He sells because a business that used to earn 22% now earns 12% and the reason
is that the moat leaked. An absolute floor of, say, 10% would let you sit through the entire
decay and only fire at the bottom. The `Δentry` form catches the deterioration while it's
still a deterioration.

**Where it misfires.** Banks and insurers have no meaningful invested capital in this sense;
mark grey. Asset-light companies can have near-zero or negative invested capital, which makes
the ratio explode or invert into nonsense (Moody's, Yum Brands); mark grey if the denominator
is under 10% of revenue. A company that just closed a large acquisition carries fresh goodwill
in the denominator and will understate ROIC for a year or two. Post-ASC 842, operating lease
assets sit on the balance sheet and depress ROIC for retailers and restaurants relative to
their pre-2019 history.

**Attribution.** Buffett, unambiguously. He'd phrase it as return on unleveraged net tangible
assets, which is stricter than this (it strips goodwill). This version is the common
approximation.

### 2. Total debt to EBITDA — REQ

`(short-term debt + long-term debt + finance lease obligations) ÷ EBITDA (TTM)`

**What it means.** How many years of earnings it would take to repay everything the company
owes. Two years is comfortable. Five is a company whose future belongs partly to its lenders.

**Why 2.5x.** Buffett's stated preference is a business that could pay off its debt out of a
couple of years of earnings. Three times is where credit rating agencies start marking down
cyclical investment-grade issuers, so 2.5 gives a full turn of cushion before anyone external
gets nervous. The point of a permanent holding is that it never has to renegotiate anything
at a bad moment.

**Why the sell threshold is not blank.** This is the exception to the buy-and-never-sell
logic. Overpaying for a great business costs you return. Leverage costs you the business.
Every permanent-capital disaster in this tradition ran through the balance sheet, not the
income statement.

**Where it misfires.** Regulated utilities and pipelines run at 4–6x as a matter of course and
that's fine because the revenue is legislated. REITs, same. Any company with a captive finance
arm (Deere, Ford, Caterpillar) carries debt that funds a loan book, not operations; the
consolidated number is meaningless without splitting industrial from financial, which XBRL
tagging won't reliably let you do. Mark those grey rather than red.

### 3. Owner earnings yield — REQ

`(cash flow from operations − maintenance capex) ÷ market capitalization`, where maintenance
capex is proxied as `min(capex, depreciation & amortization)`.

**What it means.** The cash the business throws off for its owners each year, divided by what
you'd pay for the whole thing. At 5% you're buying a dollar of annual owner cash for twenty
dollars. It's the closest thing here to "what am I actually getting for my money."

**Why 5% and not 4% or 7%.** Buffett's reputation for ignoring price is mostly myth. He bought
Coca-Cola at roughly 15x earnings, Apple at roughly 13x, and walked away from dozens of great
businesses on price alone. Twenty times owner earnings is about the outer edge of what he's
historically paid for quality. Setting it at 7% would make the profile Graham-flavoured and
you'd never buy anything wonderful. Setting it at 3% removes price discipline entirely and the
profile stops protecting you from paying anything.

**Why the sell threshold is blank, and this one matters most.** This is the flagship empty
field. A business that compounds at 18% for twenty years will spend most of those twenty years
looking expensive. If this metric could force an exit, the profile would sell every great
business it ever bought, roughly three years in, and the tool would be actively destroying
your returns while appearing to work correctly.

**Where it misfires.** Cyclicals at the top of the cycle look cheapest exactly when they're
most dangerous, because E is at peak. Any company with genuinely lumpy capex will have years
where `min(capex, D&A)` badly misstates maintenance. Companies whose capex is really disguised
M&A (or the reverse) break the proxy entirely.

**Attribution.** The concept is Buffett's, from the 1986 shareholder letter appendix. He would
recognise owner earnings; he'd quibble that the maintenance capex proxy is crude, and he'd be
right.

### 4. Interest coverage — CORE

`EBIT ÷ interest expense (TTM)`

**What it means.** How many times over the company's operating profit covers its interest
bill. At 8x, earnings could fall by half and the lenders still get paid without anyone
noticing.

**Why 8x.** Graham used 5x as his bond-safety standard for average industrials. Buffett's
quality bar sits above Graham's average industrial, and 8x is where a 50% earnings collapse
still leaves comfortable coverage. Below 5x you're one recession from a covenant conversation.

**Where it misfires.** Debt-free companies have interest expense near zero, which makes the
ratio infinite or undefined; mark grey rather than green so it doesn't silently inflate the
score. Companies capitalising interest into construction projects understate the expense.

### 5. Gross margin range, 5-year — CORE

`max(annual gross margin, 5 yrs) − min(annual gross margin, 5 yrs)`, in percentage points.

**What it means.** Whether the company sets its own prices or the market sets them. A business
whose gross margin sits between 61% and 63% for five years is telling you customers don't
shop it on price. One that swings from 22% to 38% is telling you it sells a commodity.

**Why range and not level.** Setting a minimum gross margin (say 40%) would exclude Costco,
See's-style volume businesses, and most of retail, which Buffett has owned happily. Stability
is the actual signal. Pricing power shows up as a flat line, not a high one.

**Why 6 percentage points.** Wide enough to absorb one bad input-cost year, narrow enough that
commodity producers fail every time, which is the intent.

**Why blank on the sell side.** Sustained margin compression will show up in ROIC within a
year or two, and ROIC already has a sell trigger. Two metrics firing on the same underlying
event is how a novice gets scared out of a position twice.

**Where it misfires.** Any company that changed segment reporting, made a transformative
acquisition, or restated within the window will show artificial range. Companies that don't
report cost of revenue separately (some financials, some conglomerates) go grey.

### 6. Free cash flow margin, 5-year median — CORE

`(cash from operations − capital expenditures) ÷ revenue`, per year, then median.

**What it means.** Out of every hundred dollars of sales, how many end up as spendable cash
after keeping the lights on and the equipment current. Ten dollars is healthy. Zero means the
business grows by consuming everything it earns.

**Why 10%.** Below that, growth eats the cash and the owner never sees any of it. This is the
line between a business that funds itself and one that periodically needs your money back.

**Why the sell threshold is negative FCF for four straight quarters.** A single negative
quarter is working capital timing. A full year of negative free cash flow in a mature business
means the thing you bought no longer generates owner earnings, which is the whole thesis gone.

**Where it misfires.** Companies deliberately in a heavy investment cycle (TSMC building fabs,
Amazon for most of the 2010s) show negative FCF as a choice, not a failure, and this metric
will call them red for years. If you're buying that pattern on purpose, drop this to BONUS or
raise the sell window. Also breaks where capex is really acquisitions in disguise.

### 7. Cash conversion, 5-year median — CORE

`free cash flow ÷ net income`, per year, then median.

**What it means.** Whether the reported profits turn into actual money. If a company reports a
billion in earnings and collects nine hundred million in cash, fine. If it reports a billion
and collects three hundred million, the earnings are an accounting opinion.

**Why 0.90.** Perfect conversion is rare and slightly above 1.0 is common for
depreciation-heavy companies with low current capex. Persistently below 0.80 means accruals,
aggressive capitalisation, or receivables that aren't being collected.

**Why blank.** It's a quality-of-earnings check, and a bad reading tells you to go read the
filings, not to sell on a number.

**Where it misfires.** Fast growers show poor conversion because working capital absorbs cash;
that's normal and not a defect. Software companies with large deferred revenue balances show
conversion well above 1.0 and look better than they are. Companies with high D&A and low
current capex flatter this badly.

**Attribution.** Buffett's owner-earnings thinking, formalised. Also standard in forensic
accounting (Schilit).

### 8. Diluted share count change, 5-year — CORE

`(diluted weighted shares, latest FY ÷ diluted weighted shares, 5 FYs ago) − 1`

**What it means.** Whether your slice of the company is getting bigger or smaller. A company
can grow earnings 8% a year and still deliver you nothing if it issues 8% more shares a year.

**Why 0%.** Buffett is explicit and repetitive on this: per-share is the only thing that
matters, and stock compensation is a real expense that transfers ownership from you to
employees quietly. Flat is the floor. Shrinking is the point.

**Why the sell threshold is +10% over three years.** A company diluting 3%+ per year forever is
structurally not a Buffett holding, and if it started doing that after you bought it, something
about how management thinks changed.

**Where it misfires.** A single large stock-funded acquisition will blow the window and it may
have been a fine deal. Post-IPO companies work through lockups and grant overhangs for years.
Banks that raised equity in a crisis get punished by this for half a decade afterward.

### 9. Return on equity, 5-year median — CORE

`net income ÷ average shareholders' equity`, per year, then median.

**What it means.** Profit earned per dollar of shareholder money left in the business.

**Why 15%.** This was Buffett's most-cited single figure through the 1970s and 1980s letters.
Same reasoning as ROIC.

**Why it's here at all when ROIC exists.** Redundancy is deliberate for the buy side: ROE and
ROIC diverging is itself informative, because the gap is leverage.

**Why blank on the sell side.** ROE is trivially inflated by borrowing money, which makes it a
bad exit trigger. A company that levers up to defend a falling ROE will keep this metric green
right through the deterioration. ROIC catches that; ROE doesn't.

**Where it misfires.** Companies that have bought back so much stock that equity is negative
(Home Depot, McDonald's, Starbucks at various points) produce a negative or absurd denominator;
those must go grey, not red. Heavy goodwill inflates equity and depresses ROE for acquirers.
Any leveraged business will look better on this than it deserves.

### 10. Revenue CAGR, 5-year — CORE

`(revenue_t ÷ revenue_{t−5})^(1/5) − 1`

**What it means.** Whether the business is growing at least as fast as the economy around it.

**Why 4%.** Roughly nominal GDP. A business growing slower than the economy is losing share,
and a wonderful business that's losing share is on its way to being an ordinary one.

**Attribution.** This is more Lynch than Buffett. Buffett would accept it as sensible but
wouldn't lead with it; he's held slow growers happily when the returns on capital were high
enough. It sits in CORE rather than REQ for that reason.

**Where it misfires.** A large divestiture drops revenue permanently without anything being
wrong. Companies that shifted from gross to net revenue recognition under ASC 606 show
artificial declines across the 2018 boundary.

### 11. Net income CAGR versus revenue CAGR, 5-year — CORE

Both computed as above; test is `NI CAGR ≥ Rev CAGR − 1 pp`.

**What it means.** Whether profits are growing at least as fast as sales. If sales grow 8% and
profits grow 3%, the company is buying its growth by giving away margin.

**Why a 1 point tolerance.** Zero tolerance makes this fire on rounding and single-year noise.
Wider than a point and it stops detecting anything.

**Where it misfires.** The 2017 tax act permanently changed effective rates and distorts any
five-year window spanning it. One-time charges at either endpoint of the window swing this
wildly; consider using three-year averages at each end if you see too many false reds.

### 12. Goodwill plus intangibles over total assets — CORE

`(goodwill + intangible assets) ÷ total assets`

**What it means.** How much of the company was bought rather than built. Goodwill is the
premium paid over the fair value of things acquired; it represents returns purchased with
shareholder money.

**Why 40%.** Above roughly 40% you are looking at a serial acquirer, and the historical return
figures reflect acquisition accounting more than operating skill.

**Why blank.** A goodwill impairment is an event, not a level, and it's usually the market
telling you something you already knew. Better handled as a flag than an exit.

**Where it misfires.** Genuinely good acquisitive compounders (Constellation Software, Danaher,
Roper) fail this and shouldn't. This profile isn't built for them, which is a legitimate
limitation to state rather than fix.

### 13. Effective tax rate, 5-year median — BONUS

`income tax expense ÷ pre-tax income`, per year, then median. Band: 10% to 35%.

**What it means.** A sanity check on earnings quality. A company reporting a 4% tax rate is
either running an aggressive structure that will eventually be challenged, or booking one-time
benefits that inflate EPS and won't repeat.

**Where it misfires.** Companies with large foreign-derived intangible income legitimately run
low. Loss carryforwards suppress the rate for years after a bad patch. REITs pay essentially
no corporate tax by design.

**Attribution.** Not Buffett. Forensic accounting practice. He'd recognise the concern.

### 14. Current ratio — BONUS

`current assets ÷ current liabilities`. Buy at ≥ 1.0.

**Why the bar is so much lower than Graham's 2.0.** Buffett has repeatedly praised negative
working capital as a feature. A business that collects from customers before paying suppliers
is being financed for free by its own operations. Costco and McDonald's would fail Graham's
test and Buffett would call that a point against the test. The 1.0 floor here is a bare
solvency check, not a quality signal.

**Where it misfires.** Exactly as described: the best businesses sometimes fail it. Keep it in
BONUS and never in REQ for this profile.

### 15. Total payout over free cash flow, 5-year median — BONUS

`(dividends paid + share repurchases − share issuance) ÷ free cash flow`, per year, median.

**What it means.** Whether the company is returning more cash than it produces. Sustainably
above 100% means the returns are being funded with debt.

**Why blank.** If the payout is being debt-funded, debt-to-EBITDA catches it and that metric
already has a sell trigger. Don't fire twice on one problem.

---

# Profile 2 — Graham

> **Authored, and this section is history.** `strategies/graham/` is
> authoritative; where it and this section differ, it is right and this is the
> record of what it was corrected from. The review's corrections landed in its
> code and `values.yaml` — the two contradicting price tests became one, the
> size floor moved onto sales, the dividend run became a capital-return run at
> Graham's own twenty years, the distress score became Altman's four-variable
> variant, and the eight-test quota became five questions that each have to be
> answered. Do not take a number from below without checking the strategy.

An ordinary or mediocre business bought so far below what its assets and earnings justify that
the business quality stops mattering. **The defining difference from Buffett: valuation
metrics here have sell thresholds.** The discount closing is the entire reason to exit.

This profile also needs the position clock (see Framework Gaps below). Without it, it has no
coherent exit for a stock that stays cheap forever, which is the characteristic Graham failure
mode.

| # | Metric | Buy | Sell | Tier |
|---|--------|-----|------|------|
| 1 | P/E on 3-yr average EPS | ≤ 15 | ≥ 25 (`abs`) | REQ |
| 2 | Price to book | ≤ 1.5 | ≥ 3.0 (`abs`) | REQ |
| 3 | Graham combined multiple | ≤ 22.5 | ≥ 50 (`abs`) | REQ |
| 4 | Current ratio | ≥ 2.0 | < 1.2 (`abs`) | REQ |
| 5 | Long-term debt / working capital | ≤ 1.0 | > 2.0 (`abs`) | CORE |
| 6 | Positive net income, each of 10 yrs | 10 of 10 | 2 consecutive annual losses | CORE |
| 7 | Altman Z-score | ≥ 3.0 | < 1.8 (`abs`) | CORE |
| 8 | 10-yr EPS growth (3-yr avgs) | ≥ 33% | **BLANK** | CORE |
| 9 | Consecutive years paying dividends | ≥ 10 | **BLANK** (flag on cut) | CORE |
| 10 | Debt to equity | ≤ 1.0 | ≥ 2.0 (`abs`) | CORE |
| 11 | Price to net tangible assets | ≤ 2.0 | **BLANK** | CORE |
| 12 | Accruals ratio | ≤ 0.10 | **BLANK** | CORE |
| 13 | Market capitalization | ≥ $300M | **BLANK** | BONUS |
| 14 | NCAV / market cap | ≥ 0.50 | **BLANK** | BONUS |
| 15 | Earnings yield vs 10-yr Treasury | ≥ 2× | **BLANK** | BONUS |

Suggested rollup: 4 REQ, 6 of 8 CORE, 3 BONUS.

### 1. P/E on three-year average EPS — REQ

`current price ÷ mean(diluted EPS, last 3 fiscal years)`

**What it means.** What you're paying for a dollar of typical earnings. Averaging three years
is the point: it stops you paying a low multiple on a fluke good year.

**Why 15.** It's Graham's published figure from *The Intelligent Investor*, chapter 14. It
corresponds to a 6.7% earnings yield. I'd rather give you his number than a modernised one,
because the whole value of a Graham profile is that it's his.

**Why the sell is 25 and not blank.** This is where Graham and Buffett genuinely part company,
and it's the most important disagreement in this document. Graham bought a statistical
discount on a business he had no particular faith in. When the discount closes, the reason to
own it is gone, and holding on means you've quietly switched to a different thesis you never
tested. Buffett's counter, which he made explicitly when he stopped running the partnership
this way, is that selling a compounding business at a fair price is a tax-inefficient way to
turn a great outcome into a mediocre one. Both are right about different kinds of company.
That's why they're separate profiles and not one blended set of numbers.

**Where it misfires.** Cyclicals at the trough have collapsed earnings, so P/E explodes and
they look expensive at the exact moment they're cheapest. Any large one-off charge inside the
three-year window drags the average down and makes the stock look dearer than it is. Negative
average EPS makes the ratio meaningless; go grey.

### 2. Price to book — REQ

`market capitalization ÷ total shareholders' equity`

**What it means.** What you pay for a dollar of the company's accounting net worth.

**Why 1.5.** Graham's number. Same reasoning.

**Where it misfires, and this is severe.** Book value stopped describing modern businesses
sometime around 1990. Software, pharma, brands, and services companies carry their real assets
off the balance sheet entirely, so this metric systematically rejects them. Companies with
buyback-driven negative equity produce a meaningless ratio and must go grey. Where it still
works well is banks, insurers, and asset-heavy industrials. That's a real irony worth putting
in the tooltip: the sectors this profile handles best are the ones you said you don't want to
own.

### 3. Graham combined multiple — REQ

`P/E (3-yr average) × P/B ≤ 22.5`

**What it means.** A single test that lets one number be high if the other is low. A stock at
18x earnings and 1.2x book passes; one at 18x and 2.0x doesn't.

**Why 22.5.** It's 15 × 1.5, which is exactly how Graham derived it. He'd recognise this
immediately; it's often called the Graham Number in his honour.

**Why sell at 50.** Roughly a doubling of the combined multiple, which is the discount closing
by any reasonable reading.

**Where it misfires.** Inherits every problem of both components, and compounds them: a
cyclical at trough earnings with an asset-light model fails twice for two unrelated bad
reasons.

### 4. Current ratio — REQ

`current assets ÷ current liabilities`. Buy at ≥ 2.0.

**Why 2.0 here and 1.0 in the Buffett profile.** Call this one out in the UI. Graham is buying
a business he doesn't trust, so the balance sheet has to carry the risk that the operations
can't. Buffett is buying a business he does trust and treats negative working capital as
evidence of strength. The same metric means opposite things depending on why you bought.

**Where it misfires.** Retailers, restaurants, and subscription businesses with large deferred
revenue routinely run below 1.0 and are fine. Graham would say: then this isn't a Graham stock.

### 5. Long-term debt versus working capital — CORE

`long-term debt ÷ (current assets − current liabilities) ≤ 1.0`, and working capital must be
positive.

**What it means.** Whether the company's long-term borrowings could be covered by the liquid
cushion it already has.

**Why this rather than a leverage ratio.** It's Graham's own test, stated in exactly this form.
It's stricter and more literal than debt-to-equity because it ignores fixed assets entirely,
which is deliberate: in liquidation, the factory sells for a fraction of book.

**Where it misfires.** Utilities, telecom, railroads, and anything capital-intensive fails
permanently. From Graham's perspective that's correct behaviour, not a bug. Negative working
capital makes the ratio undefined; grey.

### 6. Positive net income in each of the last ten years — CORE

Count of fiscal years since the earliest available with `NetIncomeLoss > 0`. Requires 10 of 10.

**What it means.** The company has never lost money in a decade. Not "usually profitable."
Never lost money.

**Why 10 of 10 and not 8 of 10.** Graham's criterion is stability itself, and a tool for a
novice that says "a couple of loss years is fine" is teaching the wrong lesson at the exact
point where the lesson matters. If you want to relax it, relax it consciously in the config,
not in the default.

**Where it misfires.** This is currently the most punishing metric in the profile, because 2020
put a non-cash impairment or a shutdown loss on the books of a great many otherwise stable
companies. Through roughly 2030 this test will exclude businesses Graham would have accepted.
Worth a specific tooltip. Consider allowing one excluded year with a logged reason.

### 7. Altman Z-score — CORE

`1.2×(working capital/total assets) + 1.4×(retained earnings/total assets) +
3.3×(EBIT/total assets) + 0.6×(market cap/total liabilities) + 1.0×(revenue/total assets)`

**What it means.** A bankruptcy probability score. Above 3.0 is the safe zone; below 1.8 is
the distress zone; between is grey area.

**Why it's in a Graham profile at all.** Altman published it in 1968 and it isn't Graham's.
But it is the formalisation of precisely what Graham's balance sheet tests were reaching for,
and it has fifty years of out-of-sample validation behind it, which none of Graham's individual
ratios do. He'd recognise the intent even if he'd never seen the formula. This is the one place
I'm adding something the named investor didn't use.

**Where it misfires.** Altman himself excluded financial companies; the ratios don't map. Very
asset-light companies score poorly on the working capital and asset turnover terms for reasons
unrelated to distress. Young companies have low retained earnings by construction.

### 8. Ten-year EPS growth — CORE

`mean(EPS, most recent 3 yrs) ÷ mean(EPS, 3 yrs ending 10 yrs ago) − 1 ≥ 33%`

**What it means.** The company earns at least a third more than it did a decade ago. That's
under 3% a year: a very low bar, deliberately.

**Why 33%.** Graham's exact figure. The three-year averaging at both ends is also his method,
and it matters more than the threshold does, because single-year endpoints make this number
meaningless.

**Why blank.** Growth was never the reason you bought. Discount was.

### 9. Consecutive years paying a dividend — CORE

Count of consecutive fiscal years with `PaymentsOfDividends > 0`, most recent backward.

**Why 10 and not Graham's 20.** I'm relaxing his number and I want to be explicit about it.
Graham wrote before SEC Rule 10b-18 (1982) made buybacks a safe, routine alternative to
dividends. A 20-year dividend requirement today screens out a large set of companies that
return capital consistently through repurchases instead, which Graham had no reason to
anticipate. Ten years preserves the signal (this company has survived a full cycle and returns
cash) without penalising the mechanism change.

**Why blank, with a flag on a cut.** A dividend cut is real information about financial
distress, but by the time it happens the balance sheet metrics will already be red. Flag it so
you go and read; don't make it an automatic exit.

### 10. Debt to equity — CORE

`total debt ÷ total shareholders' equity ≤ 1.0`

**Compare with Lynch's 0.5 in the next profile.** Graham is buying a mature, boring, stable
business; a full turn of leverage on a company that has never lost money in ten years is
tolerable. Lynch is buying a company growing 20% a year, where the same leverage is fatal at
the first stumble. Same metric, different number, and the difference is the whole point.

### 11. Price to net tangible assets — CORE

`market capitalization ÷ (total equity − goodwill − intangible assets) ≤ 2.0`

**What it means.** P/B with the imaginary parts removed. What you're paying per dollar of
things that could actually be sold.

**Where it misfires.** Companies with negative tangible book (common after large acquisitions)
go grey. Asset-light businesses fail by construction.

### 12. Accruals ratio — CORE

`(net income − cash from operations) ÷ total assets ≤ 0.10`

**What it means.** How much of the reported profit is bookkeeping rather than cash. High
accruals predict poor subsequent returns with unusual reliability.

**Attribution.** Sloan (1996), not Graham. It's included because a Graham portfolio is bought
on reported numbers, so a check that the reported numbers are real is doing exactly Graham's
job with better tools.

**Where it misfires.** Rapid growth generates accruals legitimately. Seasonal businesses show
distorted readings at particular quarter-ends.

### 13. Market capitalization — BONUS

`shares outstanding × price ≥ $300M`

**Why $300M.** Graham used $100M in 1972 as an "adequate size" test, which inflation-adjusts to
roughly $750M. I've set it lower deliberately, because the discounts this profile hunts are
disproportionately in smaller companies and a $750M floor removes most of the opportunity set.
$300M keeps filing quality and liquidity acceptable without gutting the universe.

### 14. NCAV over market capitalization — BONUS

`(current assets − total liabilities) ÷ market capitalization ≥ 0.50`

**What it means.** How much of the purchase price is covered by liquid assets net of all debts.
At 1.5 you'd be buying the company for two-thirds of its net current assets and getting the
business itself free. That's Graham's net-net, and it barely exists in modern markets outside
of Japan and micro-caps.

**Why 0.50 as a bonus rather than 1.5 as a requirement.** Requiring a true net-net would leave
you with an empty screen for years at a time. As a bonus it rewards the balance sheet cushion
without demanding the impossible.

### 15. Earnings yield versus the 10-year Treasury — BONUS

`(1 ÷ P/E on 3-yr avg) ≥ 2 × 10-year Treasury yield`

**This is the one important metric your data constraint excludes.** Graham's Enterprising
Investor test compared earnings yield to the AAA corporate bond yield, and Buffett has said for
decades that the long bond is the hurdle rate against which everything is measured. Neither
number is in EDGAR. It's not price data either.

**The cheap fix.** Put a single manually-entered field on the config page for the current
10-year Treasury yield, with a note to update it quarterly. One number, four times a year,
and it makes every valuation threshold in the tool cycle-aware instead of frozen at whatever
rate environment I happened to calibrate against. Without it, a 5% owner earnings yield means
something very different in a 1% world than a 5% world, and the tool can't tell the difference.

---

# Profile 3 — Lynch

> **Not yet authored. Read the addendum before authoring it.** The addendum
> corrects material in this section and the corrections have landed nowhere
> else — there is no code to check them against, so they are still only in
> that document. In summary, and not as a substitute for reading it: the
> EPS-versus-revenue spread belongs at REQ rather than CORE; the 15% growth
> floor makes this a fast-grower profile rather than a Lynch profile and should
> come down to 10% with dividend-adjusted PEG promoted to CORE; institutional
> ownership should be cut outright; and two attributions here are not his.
>
> Two things to carry over from the two profiles already authored. The X-of-Y
> quota below is the same fault corrected in both of them — group by what is
> measured and require every group to be answered, which needs nothing from the
> contract. And absolute valuation levels should read from one declared rate
> rather than sitting frozen, as Graham's price ceiling now does.

Growth at a reasonable price. A good business growing fast, bought before the market fully
prices the growth, sold when the growth stops or the price gets ahead of it.

**One substitution to flag up front.** Lynch's PEG uses *projected* earnings growth. Projections
require analyst estimates, which you've excluded. Everything below uses trailing five-year
growth instead. This changes the metric's character: it will look good on companies whose
growth has just peaked and is about to roll over, which is exactly the situation Lynch used
forward estimates to avoid. It's the largest compromise in this document. The partial defence
is that the inventory and receivables checks below are early-warning signals for that same
failure, which is why they're in CORE rather than BONUS.

| # | Metric | Buy | Sell | Tier |
|---|--------|-----|------|------|
| 1 | PEG (trailing) | ≤ 1.0 | ≥ 2.0 (`abs`) | REQ |
| 2 | Diluted EPS CAGR, 5-yr | 15% to 35% | < 8% for 4 quarters (`abs`) | REQ |
| 3 | Debt to equity | ≤ 0.5 | ≥ 1.0 (`abs`) | REQ |
| 4 | Revenue CAGR, 3-yr | ≥ 10% | < 3% for 4 quarters (`abs`) | CORE |
| 5 | EPS CAGR vs revenue CAGR | EPS ≤ Rev + 10 pp | **BLANK** | CORE |
| 6 | Inventory growth − revenue growth, YoY | ≤ +5 pp | ≥ +20 pp (`abs`) | CORE |
| 7 | Receivables growth − revenue growth, YoY | ≤ +5 pp | ≥ +20 pp (`abs`) | CORE |
| 8 | P/E vs own 5-yr median P/E | ≤ 1.0× | ≥ 1.75× (`Δmedian`) | CORE |
| 9 | Gross margin change, 3-yr | ≥ −2 pp | **BLANK** | CORE |
| 10 | Interest coverage | ≥ 5x | < 3x (`abs`) | CORE |
| 11 | Free cash flow, TTM | > 0 | < 0 for 4 quarters (`abs`) | CORE |
| 12 | Dividend-adjusted PEG | ≤ 1.0 | **BLANK** | BONUS |
| 13 | Net cash / market cap | ≥ 0 | **BLANK** | BONUS |
| 14 | Insider net buying, 6 months | > 0 shares | **BLANK** | BONUS |
| 15 | Institutional ownership | ≤ 60% | **BLANK** | BONUS |

Suggested rollup: 3 REQ, 6 of 8 CORE, 4 BONUS.

### 1. PEG ratio — REQ

`P/E (TTM) ÷ (5-yr diluted EPS CAGR expressed as a whole number)`. A company at 24x earnings
growing 20% a year has a PEG of 1.2.

**What it means.** Whether the price you're paying is justified by the speed the company is
growing. Lynch's formulation: the P/E of any fairly priced company will equal its growth rate.

**Why 1.0.** It's his number and it's the definition of the profile. Loosening to 1.2 or 1.5
turns "growth at a reasonable price" into "growth," which is a different and much worse
strategy.

**Why sell at 2.0 rather than blank.** Lynch sold. Constantly. He was explicit that a stock
whose P/E has run far ahead of its growth rate has borrowed its future returns, and this is a
second clear divergence from Buffett's blank valuation exits. Lynch's holding periods were
measured in quarters to a few years, not decades.

**Where it misfires.** Slow growers with 2% growth produce absurd PEGs; use metric 12 for those
instead. Cyclicals coming off a trough show enormous trailing growth and a flattering PEG at
exactly the wrong moment. A near-zero or negative base year makes the CAGR meaningless; go
grey.

### 2. Diluted EPS CAGR, 5-year — REQ

`(diluted EPS_t ÷ diluted EPS_{t−5})^(1/5) − 1`. Buy band: 15% to 35%.

**The upper bound is the distinctive part.** No other profile here has one. Lynch was direct
about avoiding companies growing 50–100% a year, on the grounds that such growth attracts
competition, cannot persist, and is priced as if it can. A 20–25% grower is a better
proposition than a 60% grower at the same PEG. Setting the ceiling at 35% catches the genuine
hypergrowth cases without excluding good fast growers.

**Why the sell is 8%.** Lynch's actual sell discipline for a fast grower was that it stopped
being a fast grower. Eight percent is well clear of ordinary quarterly noise and well below the
15% entry bar, so it fires on a real change of regime rather than a wobble.

**Where it misfires.** Negative or tiny base-year EPS breaks the CAGR entirely. Buyback-heavy
companies show EPS growth that isn't operating growth, which metric 5 is there to catch.

### 3. Debt to equity — REQ

`total debt ÷ total equity ≤ 0.5`

**Why 0.5 when Graham accepts 1.0.** Explicitly flag the difference. The Graham company has ten
straight profitable years behind it; a full turn of debt is survivable. The Lynch company is
growing 20% a year, which means it is spending ahead of its revenue and has never been tested
by a downturn. Leverage plus a growth stumble is the standard way these positions go to zero,
and Lynch wrote about it repeatedly.

**Where it misfires.** Recently-IPO'd companies with large cash balances and small equity bases
can read oddly. Negative equity goes grey.

### 4. Revenue CAGR, 3-year — CORE

`(revenue_t ÷ revenue_{t−3})^(1/3) − 1 ≥ 10%`

**Why 3-year here and 5-year for EPS.** The shorter window on revenue is deliberate: it's the
faster-moving signal and you want to know if the top line has decelerated recently, which a
five-year window would smooth away.

**Why 10% versus 4% in the Buffett profile.** Buffett's bar is "keeping up with the economy."
Lynch's is "actually growing." Different question entirely.

### 5. EPS CAGR versus revenue CAGR — CORE

Test: `EPS CAGR ≤ Revenue CAGR + 10 pp`.

**What it means.** Whether the earnings growth is coming from the business or from financial
engineering. Margin expansion and buybacks are real and legitimate, but a company growing EPS
at 30% on 4% revenue growth has nearly exhausted both, and there is no third act.

**Why 10 points of headroom.** Genuine operating leverage in a scaling business easily produces
that gap and shouldn't be punished. Beyond it, the arithmetic runs out.

### 6. Inventory growth minus revenue growth — CORE

`(inventory YoY % change) − (revenue YoY % change) ≤ +5 pp`

**What it means.** Whether product is piling up in the warehouse faster than it's selling. This
is one of the oldest and most reliable early warnings that demand is softening, and it shows up
in the balance sheet a quarter or two before it shows up in the income statement.

**Attribution.** Lynch, and he'd recognise it instantly. He wrote about walking through stores
and checking whether inventory was moving; this is the filing-level version of the same
instinct.

**Where it misfires.** Companies without inventory (software, services, most financials) go
grey. Deliberate builds ahead of a product launch or through a supply chain disruption look
identical to demand weakness in the numbers. Seasonal businesses need year-over-year comparison
specifically, never sequential.

### 7. Receivables growth minus revenue growth — CORE

Same construction with accounts receivable.

**What it means.** Whether sales are being booked but not collected. Rising receivables
outpacing sales means either customers are struggling or the company is pushing product into
the channel to make a quarter.

**Where it misfires.** A genuine shift toward larger enterprise customers with longer payment
terms will trigger this legitimately. Acquisitions bring receivables with them.

### 8. P/E versus its own five-year median P/E — CORE

`current P/E (TTM) ÷ median(quarterly P/E over 5 yrs) ≤ 1.0`

**What it means.** Whether the stock is cheap compared to how the market has usually priced
this particular company. Absolute multiples mean different things for different businesses;
this asks a company-specific question instead.

**Why it's the one `Δmedian` metric in the buy column.** It's the only place where the
comparison that matters is against the company's own history rather than a universal standard.

**Where it misfires.** A company whose business has genuinely changed (a hardware company that
became a software company) has a stale median that describes a company that no longer exists.
Five years of persistent multiple compression makes a falling knife look cheap.

### 9. Gross margin change over three years — CORE

`gross margin (TTM) − gross margin (3 FYs ago) ≥ −2 pp`

**What it means.** Whether the growth is being bought with discounts. Rapid revenue growth with
falling gross margin usually means the company is purchasing market share, and that stops
working when the money runs out.

### 10. Interest coverage — CORE

`EBIT ÷ interest expense ≥ 5x`. Compare Buffett's 8x. A growing company reinvests everything it
earns and legitimately carries thinner coverage than a mature cash cow. Five times is Graham's
old bond-safety line and is the right floor for a business that is expected to be bigger next
year.

### 11. Free cash flow, TTM — CORE

`cash from operations − capex > 0`

**Why merely positive, when the Buffett profile wants a 10% margin.** Lynch tolerated
cash-hungry growth that Buffett wouldn't touch. The requirement here is only that the company
isn't structurally dependent on external funding to survive. Four consecutive negative quarters
means it is.

### 12. Dividend-adjusted PEG — BONUS

`P/E ÷ (5-yr EPS CAGR + dividend yield) ≤ 1.0`

Lynch used this explicitly for stalwarts and slow growers, where the plain PEG is useless. It's
in BONUS because in a profile whose entry bar is 15% growth, few holdings will be paying a
meaningful yield. If you widen the growth band downward, promote this to CORE.

### 13. Net cash over market capitalization — BONUS

`(cash + short-term investments − total debt) ÷ market capitalization ≥ 0`

Lynch liked knowing how much of the price he was paying was already sitting in the bank. It
lowers the effective multiple on the operating business and it's a cushion during a stumble.

### 14. Insider net buying, trailing six months — BONUS

Net shares purchased across all Form 4 filings for the issuer, excluding option exercises and
transactions coded as 10b5-1 plan sales, over the last 180 days. Buy: net positive.

**What it means.** Whether the people who know the most about the company are putting their own
money in.

**Why the sell threshold is blank.** Lynch's own reasoning, and it's correct: insiders sell for
dozens of reasons that have nothing to do with the business (taxes, houses, divorce,
diversification), but they buy for one. Selling is uninformative. Buying is a signal.

**Where it misfires.** Small purchases timed for optics. Option exercises misparsed as
purchases. This requires parsing Form 4 XML rather than XBRL company facts, so it's a separate
ingestion path and genuinely more work than the rest of the metric set. If build cost matters,
this is the one to defer.

### 15. Institutional ownership — BONUS

Sum of shares reported across 13F filings for the ticker, divided by shares outstanding.
Buy: ≤ 60%.

**What it means, and it's counterintuitive.** Lynch wanted institutional ownership to be *low*.
His argument was that a stock already owned by every large fund has no marginal buyer left, and
that the best opportunities are in companies Wall Street hasn't covered yet.

**Why BONUS.** 13F data lags 45 days, aggregating it across hundreds of filers per quarter is
by far the heaviest data job in this document, and the number is approximate at best. High
value, high cost. Fair to defer indefinitely.

---

# Profile 4 — Discount Closure (the honest version of the swing profile)

> **Not yet authored. Read the addendum before authoring it.** The addendum
> corrects material in this section and the corrections have landed nowhere
> else. In summary, and not as a substitute for reading it: the EV/EBIT median
> is contaminated by the discount being measured and should exclude the
> trailing four quarters; and the maturity wall is missing and material — debt
> due within 24 months over cash plus twice TTM free cash flow, at REQ.
>
> **The maturity wall is not buildable today and that is recorded rather than
> assumed.** The by-year debt repayment elements are footnote-level and thinly
> tagged, so a measure built on them would be absent for a large share of
> filers and quietly wrong for some — which is worse than not having it. A
> 12-month version IS computable from what the concept map already resolves.
> It answers a different question: 24 months was chosen because it matches the
> holding period a value trap has to survive. If you want to build the wall on
> 12 months, make that argument openly and say so where the value is declared;
> do not let it arrive as a substitution nobody noticed.
>
> Two things to carry over from the two profiles already authored, as with
> Lynch: the X-of-Y quota is the same fault corrected in both, and this
> profile's absolute price levels — EV/EBIT of 8, the 8% FCF yield — should
> read from one declared rate.

**You asked me to say plainly whether a fundamental swing profile is defensible. It is not, as
described.** The reason is a timing mismatch, not a philosophical objection: if the holding
period is weeks and the underlying data refreshes quarterly, then for most of the trade the
only input that changes is price. Rules driven only by price movement are technical rules,
which you've ruled out. A tool that appeared to be running fundamental swing logic on a
six-week horizon would in fact be running a stale quarterly snapshot and a price chart, and
would be lying to a novice about what it was doing.

What *is* defensible on the same fundamental logic at a compressed horizon is the pattern
Graham ran in his own workout book: buy a measurable statistical discount in a business that is
demonstrably not dying, exit when the discount closes or when a clock expires, and deliberately
do not form an opinion about whether the business is wonderful. Expected holding period is six
to twenty-four months, not weeks. Everything in this profile is either a solvency floor or a
discount measurement. There is no quality thesis, because there isn't time for one to play out.

Call it what it is in the UI. If you label this "swing trading," a beginner will expect it to
tell him something in week three, and it won't.

Fewer metrics here, deliberately, because on a short horizon fewer things can meaningfully
change.

| # | Metric | Buy | Sell | Tier |
|---|--------|-----|------|------|
| 1 | EV/EBIT vs own 5-yr median | ≤ 0.70× | ≥ 1.00× (`Δmedian`) | REQ |
| 2 | EV/EBIT, absolute | ≤ 8.0 | ≥ 13.0 (`abs`) | REQ |
| 3 | Altman Z-score | ≥ 2.5 | < 1.8 (`abs`) | REQ |
| 4 | Net debt / EBITDA | ≤ 3.0 | ≥ 4.5 (`abs`) | REQ |
| 5 | Operating income, TTM | > 0 | < 0 for 2 quarters (`abs`) | REQ |
| 6 | Free cash flow yield on EV | ≥ 8% | ≤ 4% (`abs`) | CORE |
| 7 | Free cash flow, TTM | > 0 | < 0 for 2 quarters (`abs`) | CORE |
| 8 | Interest coverage | ≥ 4x | < 2.5x (`abs`) | CORE |
| 9 | Revenue change, YoY | ≥ −10% | ≤ −15% for 2 quarters (`abs`) | CORE |
| 10 | Gross margin vs 3-yr median | ≥ −3 pp | ≤ −5 pp (`Δmedian`) | CORE |
| 11 | Diluted share count, TTM change | ≤ +3% | ≥ +8% (`abs`) | CORE |
| 12 | Accruals ratio | ≤ 0.10 | **BLANK** | BONUS |
| 13 | Insider net buying, 6 months | > 0 shares | **BLANK** | BONUS |

Plus a position clock: **exit at 24 months regardless of any metric.**

Suggested rollup: 5 REQ, 5 of 6 CORE, 2 BONUS.

### 1. EV/EBIT versus its own five-year median — REQ

`EV/EBIT (current) ÷ median(EV/EBIT over 20 trailing quarters) ≤ 0.70`

**This metric is the profile.** Everything else is a filter that stops you buying a discount
that exists because the company is dying. This one is the actual thesis: the market has priced
this business at 30% below its own normal, and nothing in the filings explains why.

**Why 0.70 and why the sell is exactly 1.00.** The entry is a 30% discount to normal. The exit
is normal. That symmetry is the whole design: the trade is complete when the thing that made it
a trade is gone, and there is no second thesis waiting to justify holding on. This is the
cleanest possible statement of Graham's discount-closure logic and it's why this profile exists
at all.

**Where it misfires.** A company whose business has permanently deteriorated has a median that
describes a company that no longer exists, and it will read as a 30% discount all the way down.
Metrics 9 and 10 exist specifically to catch that case. Five years of data is also the minimum;
anything shorter and the median is noise.

### 2. EV/EBIT, absolute — REQ

`(market cap + total debt − cash & equivalents) ÷ EBIT (TTM)`

**What it means.** What the entire business costs, including its debts, per dollar of operating
profit. Enterprise value rather than market cap because when you buy a leveraged company you
assume its debts, and the price tag should say so.

**Why 8.** It's a 12.5% pre-tax operating earnings yield, which is roughly where Greenblatt's
Magic Formula work found the cheap decile historically.

**Attribution, with a caveat.** This is Greenblatt's earnings yield inverted. He would *not*
endorse it as a threshold, because his method is a cross-sectional ranking: buy the cheapest
30 out of 3,500, whatever the absolute number happens to be that year. Freezing it at 8 makes
the profile un-buyable in an expensive market and too loose in a cheap one. That's a real
limitation of a tool that evaluates one security at a time, and it's why I'm not giving you a
Greenblatt profile.

### 3. Altman Z-score — REQ

Formula as in the Graham profile. Buy at ≥ 2.5, sell below 1.8.

**Why lower than Graham's 3.0.** The 24-month clock does some of the work here; Graham's
permanent-capital version needs more cushion because it might hold through a full cycle. But
this stays a knockout, because on a compressed horizon there is no time to recover from a
solvency event. Cheap stocks that go bankrupt are the characteristic failure of this entire
approach.

### 4. Net debt to EBITDA — REQ

`(total debt − cash & equivalents) ÷ EBITDA (TTM) ≤ 3.0`

Looser than Buffett's 2.5 gross measure because netting cash is more appropriate for a
time-limited position, and because a modestly leveraged cheap company is exactly what this
profile is hunting. The 4.5 sell is a hard stop: a leveraged company whose leverage is rising
while you hold it is the one situation where waiting for the clock is the wrong answer.

### 5. Operating income positive, TTM — REQ

`OperatingIncomeLoss (TTM) > 0`

**What it means.** The company makes money from what it does. No turnarounds, no story stocks,
no "it'll be profitable in 2028."

**Why it's a knockout.** Every metric in this profile that measures a discount uses earnings in
the denominator. If earnings are negative, the discount isn't measurable and the profile has
nothing to say. This isn't a quality judgement; it's a precondition for the arithmetic.

### 6. Free cash flow yield on enterprise value — CORE

`(cash from operations − capex) ÷ enterprise value ≥ 8%`

The cash cross-check on metric 2. EBIT can be flattered by accounting choices; free cash flow
is harder to fake. Requiring both to show a discount is what keeps this profile from buying
accounting artifacts.

### 7. Free cash flow positive, TTM — CORE

The two-quarter sell window here is much shorter than the four-quarter window in the Buffett
and Lynch profiles. Deliberate: on a 24-month horizon, two bad quarters is 8% of your holding
period and you don't have time to be patient about it.

### 8. Interest coverage — CORE

`EBIT ÷ interest expense ≥ 4x`. The lowest bar of the four profiles, for the same reason as
metric 4: modest leverage in a cheap company is part of the setup, not a defect. Below 2.5x
you're in the zone where a bad quarter becomes a covenant problem.

### 9. Revenue change year over year — CORE

`revenue (TTM) ÷ revenue (prior year TTM) − 1 ≥ −10%`

**What it means.** The difference between a business having a bad year and a business
disappearing. A 5% revenue decline in a cyclical downturn is the setup. A 20% decline in a
structurally challenged industry is the trap.

**Where it misfires.** Deep cyclicals at a genuine trough will fail this and they are, in
principle, exactly what the profile wants. That's an accepted cost: distinguishing a cyclical
trough from a structural collapse in the numbers alone isn't reliably possible, and for a
novice-facing tool the false negative is much cheaper than the false positive.

### 10. Gross margin versus three-year median — CORE

`gross margin (TTM) − median(annual gross margin, 3 yrs) ≥ −3 pp`

This is the metric that distinguishes cyclical weakness from structural decline. Revenue falls
in both cases. Gross margin holding up through a revenue decline means the company still has
pricing power and is just selling less; gross margin collapsing alongside revenue means it's
discounting to hold volume, which is the pattern that precedes permanent impairment.

### 11. Diluted share count, TTM change — CORE

`≤ +3%`. A cheap company that funds itself by issuing stock into a depressed price is
transferring your discount to new shareholders. The 8% sell trigger is a hard one: it means
management has decided the way out of the problem is your ownership stake.

### 12. Accruals ratio — BONUS

As in the Graham profile. A check that the cheapness is real and not the reversal of aggressive
prior-period accounting.

### 13. Insider net buying, six months — BONUS

The single most timely fundamental signal available on this horizon, and the only one in the
entire document that updates in days rather than quarters. For a profile whose problem is that
nothing changes fast enough, this is disproportionately valuable. Same Form 4 parsing cost as
in the Lynch profile.

---

# Where the profiles disagree

These are the places to put a tooltip, because the difference between the numbers is the
actual content.

| Metric | Buffett | Graham | Lynch | Discount Closure |
|--------|---------|--------|-------|------------------|
| Valuation sell threshold | **BLANK everywhere** | Yes, on P/E, P/B, combined | Yes, on PEG and relative P/E | Yes, it's the exit |
| Current ratio | ≥ 1.0, bonus | ≥ 2.0, knockout | not used | not used |
| Debt to equity | not used (uses debt/EBITDA ≤ 2.5) | ≤ 1.0 | ≤ 0.5 | not used (uses net debt/EBITDA ≤ 3.0) |
| Interest coverage | ≥ 8x | not used (uses LTD ≤ WC) | ≥ 5x | ≥ 4x |
| Revenue growth | ≥ 4% (5-yr) | ≥ 33% over 10 yrs | ≥ 10% (3-yr) | ≥ −10% YoY |
| Growth upper bound | none | none | **≤ 35%** | none |
| Book value | never used | knockout at 1.5x | never used | never used |
| FCF requirement | ≥ 10% margin | not used | merely positive | ≥ 8% yield on EV |
| Share count | ≤ 0% over 5 yrs | not used | not used | ≤ +3% TTM |
| Altman Z | not used | ≥ 3.0 | not used | ≥ 2.5 |
| Position clock | none | **24 months** | none | **24 months** |

The single most important row is the first one. Buffett's valuation sell fields are blank
because he's decided in advance that the business compounding is worth more than the price
being right. Graham's are populated because he never believed the business was worth anything
in particular, only that it was mispriced. Neither is a compromise position and there is no
number in between that either would sign.

The second most important is the current ratio row, because it's the clearest case of one
metric meaning opposite things. Graham needs the balance sheet to carry risk the operations
can't. Buffett treats negative working capital as evidence that customers pay before suppliers
do, which is a competitive advantage showing up as a bad-looking ratio.

---

# Framework gaps

Four things the two-threshold model can't express, in order of how much damage they do.

**1. Relative sell thresholds.** Covered above and used throughout. Without `Δentry` and
`Δmedian` forms, the Buffett ROIC exit has to be an absolute floor, which fires years late; the
Lynch relative-P/E metric can't exist at all; and the entire Discount Closure profile
collapses, because its exit is definitionally relative. A dropdown next to the sell field with
three options, and a stored snapshot of each metric's value at purchase.

**2. The position clock.** Graham's actual discipline was to sell after two years regardless of
what happened, and Discount Closure needs the same. No metric can hold "it's been two years."
This is a per-profile setting on the position, not on any metric, and without it both of those
profiles have no exit for the case where the stock simply stays cheap. That case is the single
most common way this style of investing fails.

**3. Two-filing persistence.** Already assumed in every sell threshold above. One goodwill
impairment, one legal settlement, one inventory build, and a metric crosses the line on noise.
For a tool whose entire purpose is preventing panic decisions, firing a red on one quarter's
one-off charge is the worst possible failure mode: it would use the authority of the system to
cause exactly the behaviour it exists to prevent.

**4. Sell severity.** Right now a red is a red. But "debt to EBITDA hit 4.5x" and "the P/E
finally exceeded 25" are different kinds of news, and the second one should send you to your
notes while the first sends you to the sell button. Two levels (flag and exit) per sell
threshold would carry that. This is the one I'd call optional; you could live without it if the
build cost is real.

One more thing that isn't a gap but should be surfaced in the UI: the Buffett profile as
configured has no valuation exit and only four sell triggers total, all of them balance-sheet
or cash-flow related. It is therefore possible to hold a position in that profile for twenty
years and never see a sell signal. That's correct and intended. It should still say so on the
config page when you save it, because otherwise it looks like the tool is broken.

# What the data constraint costs you

Worth being explicit about, since you asked.

**The risk-free rate.** Discussed under Graham metric 15. This is the significant one and it
has a cheap fix: one manually-updated field.

**Forward growth estimates.** Lynch's PEG is forward-looking by design. Using trailing growth
inverts the metric's behaviour at exactly the moment it matters most, when growth is peaking.
No workaround exists within your constraints.

**Maintenance versus growth capex.** `min(capex, D&A)` is a crude proxy and every owner-earnings
figure in the Buffett profile inherits its error. Companies disclose this qualitatively in the
MD&A sometimes, never in a tagged field.

**Segment and same-store data.** Sometimes tagged in XBRL, inconsistently, with no reliable
schema across filers. Lynch's actual research method depended heavily on unit-level economics
that aren't recoverable this way.

**Everything qualitative.** Moat durability, management integrity, whether the CEO is a
capital allocator or an empire builder. Buffett would say this is most of the job. Partial
recovery is possible from DEF 14A compensation structures and Form 4 insider behaviour, which
is one more argument for building the Form 4 ingestion.

---

*Threshold conventions drawn from published methods of the investors named. Not investment
advice, and I'm not a licensed advisor. These are defaults for a configuration file, meant to
be argued with and changed.*
