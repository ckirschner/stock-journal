## 1. When an earnings base is too small for a growth rate to mean anything

**The floor cannot be denominated in per-share currency, and that's the whole answer to the "$200 stock vs $3 stock" part of your question.** A three-for-one split turns a $0.30 base into $0.10 and changes nothing about the business. Any threshold expressed in cents of EPS is measuring share count. The floor has to be a ratio of two accounting quantities from the same period.

Before setting one, though, the bigger fix is to the estimator. Graham's method, already sitting in your own document at Graham metric 8, is three-year averages at both endpoints. Lynch metric 2 uses single-year endpoints. Import Graham's construction: compare mean(EPS, FY0..FY-2) against mean(EPS, FY-5..FY-7), which preserves a five-year centre-to-centre gap and needs eight years of history. That single change eliminates most of what you're asking about, including negative base years, which almost never survive a three-year average.

The reason this matters more than the threshold: the dangerous case is not the one that fails high. Take a company whose true trend EPS went 0.70 to 1.00 over five years, a 7.4% rate that correctly fails the 15% floor. Now suppose the base year carried a one-off charge and printed 0.40. Measured CAGR is 20.1%, sits mid-band, and passes. A reject silently became a buy. The $0.05-to-$2.00 case fails high and gets caught for the wrong reason; the moderate distortion passes and never gets caught at all. Your band's upper bound only protects against the extreme version.

For genuine smallness (not depression), the scale-free test is margin-based:

> Base-period net margin ≥ 50% of end-period net margin.

For a real operating grower, net margin is stable or modestly expanding as it scales; going from 8% to 12% over five years is ordinary operating leverage and passes easily. The 0.05-to-2.00 company went from roughly 0.5% to 8%, so its base is 6% of its end margin and it fails. This is price-free, unit-free, industry-free, and it doesn't fight the growth band the way a test against the window's own median would (a legitimate 35% grower's base year is only 41% of its window median, so that construction would reject the top of your allowed range).

**What to do when a company is on the wrong side of the line: don't grey it, route it.** A tiny or negative base tells you something specific and it isn't "unanswerable." It tells you the earnings did not grow, they appeared. That is a margin recovery or a turnaround, and margin recovery has a hard ceiling that unit growth does not. Lynch had a name for this and treated it as a separate category with different rules: turnarounds are not fast growers, and none of the fast-grower criteria apply to them. So the correct output is "this company's record does not establish it as a fast grower; it looks like a turnaround or a cyclical off a trough," which is more useful than grey and directs the reader to the right question.

One related change: Lynch metric 5 (EPS CAGR ≤ revenue CAGR + 10pp) is already a partial guard against exactly this and it's sitting in CORE. It should be REQ. PEG and EPS CAGR are both REQ and both take the same growth number as an input, so a distorted base breaks both required tests in the same direction simultaneously. Metric 5 is the only thing in the profile that catches that, and a quota-based tier can't be relied on to enforce it.

---

## 2. How much persistence a sell rule needs

Confirmation exists to filter measurement noise, not reality. So the question is not how long the window is, it's how much a single observation can move the estimator. Window length is a poor proxy for that.

Two consecutive readings of a rolling five-year window share four of five years. They are 80% the same data. Requiring four such readings is not accumulating four pieces of evidence, it is accumulating one piece of evidence and nine years. That is the answer to your central question: **persistence confirmation on a rolling multi-year window is close to a null operation on the evidence and a large operation on the delay.**

But the answer splits by estimator type, not by window:

A five-year *median* (Buffett ROIC, ROE, FCF margin, cash conversion) is maximally robust by construction. One outlier year cannot move it further than the adjacent order statistic. The window has already done the smoothing that confirmation is supposed to do. These should fire on first breach, no confirmation.

A five-year *CAGR on single-year endpoints* (Lynch metrics 2 and 4, Buffett 10 and 11) is not a long-window measure at all. It is a two-observation measure with a five-year gap between the observations. Take a 20% grower at 1.00 to 2.49: a one-off charge dropping the terminal year to 1.80 takes the measured CAGR to 12.5%. One year moved it 7.5 points. It looks robust and behaves as fragilely as a TTM number. Either average the endpoints (preferred, and it's the same fix as question 1) or require one confirmation, never four.

TTM and quarterly measures keep two consecutive filings as written. Point-in-time balance sheet measures (debt/EBITDA, current ratio, interest coverage) also keep two, because a single-date snapshot genuinely is noisy: a bond issued a week before quarter end distorts it.

There is a legitimate residual worry that the persistence rule was reaching for, and it isn't noise across time, it's that the most recent fiscal year is the one most likely to contain a one-off. That can be tested within a single observation rather than across four:

> Recompute the measure with the single worst year excluded. If it still breaches, the deterioration is structural and the trigger fires now. If excluding one year clears it, it was one year and you wait.

This gets you one-observation robustness at one filing instead of nine years, and it is a property of the measure's definition rather than a scheduling rule.

**Three-year versus five-year:** the difference is real but it runs through the estimator again. A three-point median has less breakdown resistance than a five-point one (one bad year shifts it to what was the second-best value), so a three-year median tolerates first-breach firing but benefits more from the leave-one-out check. A three-year mean or CAGR is fragile enough to need it outright. Overlap also matters: consecutive three-year windows share two of three years, so the independence problem is only slightly better.

**The structural error underneath all of this.** The document uses the same measure for entry and exit throughout. Entry wants durability, which argues for a long window. Exit wants timeliness, which argues for a short one. Using one measure for both guarantees you either buy on noise or exit late, and this profile set chose late. Lynch's actual sell discipline for a fast grower was that it stopped being a fast grower, which is a statement about the current rate, not the five-year average. So Lynch metric 2's sell should not be a threshold on the five-year CAGR at all. Buy on the five-year averaged-endpoint CAGR ≥ 15%; sell on TTM EPS versus prior-year TTM below 8% for two consecutive quarters, with TTM revenue growth as a corroborating read. Delay drops from nine years to about six months, and it is measuring the thing Lynch actually acted on.

Apply the same split wherever a long-window buy currently has a long-window sell.

---

## 3. Financial companies

First, a routing problem: SIC 6xxx over-captures badly. Asset managers, exchanges, and rating agencies (6199, 6200, 6282) are asset-light operating businesses that read fine under the standard rules apart from the near-zero invested capital issue your ROIC note already handles. REITs (6798) break in a completely different way from banks (depreciation is meaningless, FFO replaces net income, high leverage is structural). You need at minimum three routes plus a no-route exception list: depository and lending (6020-6199 excluding the exceptions), insurance (6311-6411), real estate and REITs (6500-6798). Routing all of 6xxx down one path will misclassify BlackRock and Moody's as banks.

### What genuinely breaks (no reading fixes it)

Anything built on invested capital, enterprise value, or operating cash flow. For a bank, debt is raw material rather than a claim on the business, so ROIC, EV/EBIT, debt/EBITDA, net debt/EBITDA, and interest coverage are not merely distorted, they are category errors. EBIT is computed after interest expense for a bank, where interest is cost of goods sold.

The one to name loudest is the cash flow family: owner earnings, FCF margin, cash conversion, FCF yield on EV. A bank's operating cash flow is dominated by period changes in loans, deposits, and trading assets. These do not return grey, they return large confident numbers that look excellent. A shrinking bank generates enormous "free cash flow." This is the only place in the document where a financial company produces a wrong green instead of a grey, and it is the most damaging failure mode in the whole set.

Graham's balance sheet apparatus is not just distorted but literally uncomputable: banks do not classify a balance sheet into current and non-current, so current ratio, long-term debt over working capital, and NCAV have no inputs. Altman excluded financials himself, as your document notes. Inventory checks have no denominator.

### What reads differently but survives

ROE works and is the primary measure, but it needs a different guard. For a non-financial, ROIC is the guard that catches ROE manufactured by leverage. For a bank, leverage *is* the product, so the guard has to be a capital ratio. Price to book works better here than anywhere else in the document, which is the irony your Graham section already flagged. P/E on three-year averages works, with the caveat that bank earnings are provision-driven and provisions are the most discretionary line in the filing; three-year averaging is doing real work. Dividend record, share count, effective tax rate, and insider buying all work unchanged. Revenue needs redefining as net interest income plus non-interest income, since banks tag `Revenues` inconsistently.

Receivables growth is the interesting transplant. For a bank the receivables line is the loan book, and loan growth outpacing deposit or asset growth is meaningful, but it means the opposite of what the Lynch metric intends: it isn't channel stuffing, it's underwriting loosening. Same arithmetic, different diagnosis, and it's one of the better predictors of a bank's next credit cycle.

### Substitutes, per school

**Buffett branch (banks).** Replace ROIC with return on average assets, and replace debt/EBITDA with tangible common equity over tangible assets. This is Buffett's own framing rather than a synthesis: his 1990 Wells Fargo discussion works from assets-to-equity ratio and return on assets, and his stated point is that at twenty-to-one leverage, management error is magnified twentyfold. Suggested levels: ROA ≥ 1.1% five-year median, TCE/TA ≥ 8%, both REQ. TCE/TA is computable from the balance sheet directly, which matters because CET1 appears in Basel III tables and is unreliably tagged.

Replace gross margin range with net interest margin stability (net interest income over average earning assets, five-year range relative to median), which does exactly the job the margin range does for an industrial: it distinguishes a franchise that prices its own deposits from one that takes market pricing.

Add a credit quality measure, because it is the single thing separating a good bank from a bad one across a cycle: net charge-offs over average loans, five-year median, plus the range. Flag: CECL adoption in 2020 changed provisioning to lifetime expected loss and broke comparability across that boundary, and post-CECL allowance tags are inconsistent between filers.

Replace owner earnings yield with five-year average net income over market cap, since a bank has no maintenance capex wedge. The level should be *higher* than the 5% used for non-financials, around 7%. Buffett has consistently paid less for banks than for consumer franchises, and the reason is that a bank's earnings stream is not durable in the way a brand's is.

**Buffett branch (insurers)** diverges from banks and should be its own path. Interest coverage survives at the holding company, since insurer debt is real corporate debt. Combined ratio below 100 across a five-year median is the measure; it is rarely tagged as one fact but the components (premiums earned, losses and LAE incurred, underwriting expense) are, so it is reconstructable. Most usefully, replace EPS growth with book value per share growth plus dividends, which is Buffett's own explicit yardstick for insurance operations and handles the earnings volatility from realized gains and reserve development. Prior-year reserve development is where insurer earnings quality actually lives; it appears in the ASC 944 rollforward and is tagged inconsistently, so flag it as wanted-but-unreliable rather than substituting something worse.

**Lynch branch.** He owned a great many thrifts and wrote explicit criteria for them, so this branch is well founded: equity-to-assets ratio as the primary safety test, non-performing assets as a percentage of total assets as the quality test, and price to book near or below 1 as the price test, with the usual growth arithmetic on EPS. My recollection of his stated levels is roughly 5.5% equity-to-assets as adequate with a preference for 7.5%+, and non-performing assets under about 2%. Treat those two numbers as moderate confidence and worth checking against *Beating the Street* directly; the structure of the test I'm confident about.

**Discount Closure branch.** This one transplants cleanly, because the profile is purely a discount measurement with solvency floors and no quality thesis. Replace EV/EBIT versus own median with price to tangible book versus own five-year median at the same 0.70x / 1.00x symmetry. Replace Altman with TCE/TA ≥ 7% and NPAs/loans ≤ 3%. Everything else stands.

**Graham branch: I'd tell you plainly that this one is incoherent.** For the other three schools, the thesis survives translation because the thesis is a proposition about business economics that the measures approximate. Graham's rule set is not a philosophy implemented through metrics; it *is* the metrics, and specifically the liquidation-oriented balance sheet apparatus. Substituting bank measures into the Graham profile produces something that is not Graham. The historical evidence supports this rather than contradicting it: Graham's one great financial position, GEICO, was bought as a concentrated stake in a growing insurer on grounds that violated his own published criteria, and he said afterward that it made more money than everything else in the partnership combined. That is not a rule set being applied to a financial. It is the rule set being set aside.

So the honest per-school answer is: branch three, exclude one, and say why on the config page. Buffett's largest positions being financials costs nothing under this answer, because the Buffett branch exists.

### On your grey semantics

Your three-way resolution is right and I wouldn't change it, but it is conflating two states that behave differently. A grey from a missing tag might resolve next quarter. A grey from a measure that has no meaning for this filer will never resolve, and it is knowable in advance from SIC rather than discovered at computation time. Split them: unavailable versus inapplicable. Unavailable leaves the group undecided, as now. Inapplicable should trigger the branch, and if no branch exists for that school, it should return "this rule set does not evaluate this kind of company," which is a different and more honest sentence than "cannot be assessed."

---

## 4. The broader review

### Buffett profile

**Debt to EBITDA at REQ is the clearest thing in the document he would disown.** Munger's position on EBITDA is that the word should be read as a synonym for fictitious earnings, and Buffett has written repeatedly that depreciation is a real expense and that any metric ignoring it flatters capital-intensive businesses. Putting it at the knockout tier in his own profile is attributing to him a measure he has publicly attacked. Replace it with total debt over five-year average free cash flow ≤ 3.0x at REQ, which measures the same thing (years of earnings to repay) using a number he endorses. Keep the EBITDA version at BONUS if you want the comparability with credit ratings.

**Goodwill plus intangibles over total assets should come out.** Buffett's 1983 letter appendix on goodwill argues that economic goodwill is the most valuable asset a business owns and that accounting goodwill measures it poorly. A level test penalizes a company for one good acquisition fifteen years ago, and your own note concedes it wrongly excludes Constellation, Danaher, and Roper. If you want the signal, measure the outcome rather than the activity: cumulative goodwill impairment over five years exceeding 5% of prior-year equity is evidence the acquisitions destroyed value. Better, use the freed CORE slot for the measure I think is the profile's most material omission.

**Missing: incremental return on capital.** Change in NOPAT over five years divided by change in invested capital over the same period. The five-year median ROIC tells you what the existing capital base earns. Incremental ROIC tells you what newly retained capital earns, and that, not the base, is what determines the compounding rate. It is the single most Buffett-relevant measure absent from the document, and it is the one that separates a wonderful business from a wonderful business that has run out of places to put money. Suggested level ≥ 15%, CORE. It displaces the goodwill test.

**ROE at CORE should become the ROE minus ROIC gap.** Your own note says the informative thing is the divergence, because the gap is leverage, and then the profile tests the level instead. Test the gap directly (≤ 10pp). As currently built, ROE and ROIC are two CORE slots measuring one thing, which inflates the count for leveraged companies.

**Gross margin range should be relative, not in percentage points.** A distributor at 12% gross margin swinging between 9% and 15% has a 6pp range and is wildly unstable. A software company at 78-84% has the same 6pp range and is rock solid. Use (max − min) / median ≤ 15%. Same principle as question 1: absolute units don't travel across scale.

**Owner earnings yield: the level is defensible, and the rate-adjustment argument you correctly make for Graham does not transfer here.** Buffett bought Coca-Cola in 1988 at roughly 15x, a 6.7% earnings yield, when the ten-year Treasury was around 9%. That is a negative spread to the risk-free rate. Any rule expressing his price discipline as "yield ≥ Treasury + N" would have blocked one of the best purchases in the record. His discipline is a judgment about capitalized future owner earnings, not a spread, and a fixed 5% is a crude but acceptable stand-in for it. Say this explicitly on the config page, because it is a real disagreement with the Graham profile and the temptation to harmonize them will be strong.

Two mechanical notes on the same metric. The denominator should arguably be enterprise value rather than market cap, since owner earnings is a business-level number and market cap makes a leveraged company look cheap. And `min(capex, D&A)` includes amortization of acquired intangibles in D&A, which systematically inflates owner earnings for serial acquirers whose intangibles have to be replaced through further M&A. Use D&A excluding acquired intangible amortization; it is separately tagged by most filers.

**Aged: the effective tax rate band.** 10-35% was calibrated on a 35% federal statutory rate. Post-TCJA a US-centric company runs 19-23%, so the upper bound now catches essentially nobody and the band is doing no work. Roughly 12-28% restores the original intent.

**Also aged:** ASC 606 (2018) reclassified certain shipping and fulfillment costs between cost of revenue and operating expense, which creates artificial steps in gross margin across the boundary. Your note flags 606 for revenue recognition but not for margin, and the margin range metric is more sensitive to it.

### Graham profile

**The market cap floor is on the wrong quantity.** Graham's adequate size criterion in the fourth edition is $100 million of annual *sales* for an industrial company (and $50 million of total assets for a utility), not market capitalization. Inflation-adjusted, that is roughly $750-800 million of sales today. Your $300M is a market cap number defended against a sales number. Move it to revenue and set it consciously; the argument for going below Graham's inflation-adjusted level is still available, it just needs to be made about the right variable.

**The dividend relaxation is solving the right problem the wrong way.** Graham's 20 years was doing two jobs: evidence of capital return, and evidence of survival across a full cycle including a severe one. Cutting to 10 preserves the first and discards the second. Better fix: keep 20 years, but count either dividends or positive net buybacks in each year. That accommodates the post-1982 mechanism change without shortening the survival window.

**The two valuation tests contradict each other and the stricter one is in BONUS.** P/E ≤ 15 at REQ and earnings yield ≥ 2× the bond yield at BONUS give different answers at any bond yield above about 3.3%, and above that level the bond test is the binding one. So in the current environment the profile is silently using the looser test because of where it sits in the tier structure. Make the P/E ceiling min(15, 1/(2 × AAA yield)). Also note the substitution you made: Graham's test was against AAA corporates, not Treasuries, and AAA typically runs 70-100bp wide of the ten-year, so 2× Treasury is materially looser than what he wrote.

**Misattributed: the 24-month clock is not a Defensive Investor rule.** Graham's sell-at-a-gain-or-after-two-years discipline comes from his net-net and simplified-criteria work, not from the chapter 14 defensive program that this profile mostly implements. The profile is defensive-flavoured, so attaching the clock to it is importing a rule from a different program. Your Framework Gaps section is right to put the clock on Discount Closure. Separately, the rule as Graham stated it has two legs, sell at roughly +50% or after two years, whichever comes first, and only the clock leg is in the document. Add the gain leg (moderate-to-high confidence on the specific 50% figure; the two-part structure I'm confident about).

**Altman: use Z'' for non-manufacturers.** The original Z was calibrated on public manufacturers. The four-variable Z'' variant drops the asset turnover term and is the one Altman intended for service and non-manufacturing companies, which is most of what this profile will encounter. Scoring a services company on the original formula mis-reads it for reasons unrelated to distress, which your note half-identifies.

**The largest omission is not a metric.** Graham's defensive program was never a stock selection rule set standing alone; it was a stock selection rule set inside a 25-to-75-percent bond allocation, rebalanced against valuation. He was explicit that in expensive markets the criteria would produce no candidates, and that this was the signal to hold more bonds rather than to relax the criteria. Your profile as built has four REQ knockouts plus a 6-of-8 CORE quota, and against a realistic US universe it will return nothing for years at a time. That is faithful behaviour, and without the allocation rule the reader will experience it as the tool being broken and will loosen the thresholds. The escape valve is part of the method.

### Lynch profile

**Metric 2's lower bound at REQ makes this a fast-grower profile, not a Lynch profile.** Lynch's method begins by sorting the company into one of six categories, and stalwarts at 10-12% growth were deliberate portfolio ballast, not rejects. A 15% REQ floor can only ever buy one of the six. Either relabel the profile "Lynch, fast growers" and say so, or drop the floor to 10%, let PEG do the work (his own rule that a fairly priced company's P/E equals its growth rate is category-agnostic), and promote dividend-adjusted PEG from BONUS to CORE, which your own note says to do in exactly this case. I'd do the second.

The deeper version of this is that the category assignment is itself the missing measure. Since you can route on SIC, you can route on category: revenue CAGR, margin volatility, and revenue sensitivity to the cycle separate fast grower from stalwart from cyclical reasonably well, and a negative or trivial base year identifies a turnaround, which is where question 1 lands. Every other Lynch rule is conditional on the category, so applying one rule set to all comers is not doing what he did.

**Institutional ownership ≤ 60% has aged out of usefulness.** When Lynch wrote, high institutional ownership meant Wall Street had found the story. Today index funds alone hold roughly a fifth to a quarter of the US market, and typical large-cap institutional ownership sits well above 60% for reasons that carry no information about discovery. The signal he wanted (analyst coverage, marginal-buyer scarcity) is not recoverable from 13F data, since you cannot reliably separate index from active holdings. I'd cut it rather than keep a metric that now means something different from what its rationale claims. That also removes what your own note calls the heaviest data job in the document, so the trade is favourable. My figures on current ownership levels are approximate; the direction is not in doubt.

**Debt to equity ≤ 0.5**: the reasoning is sound and the level is sensible, but I'm not aware of Lynch publishing 0.5 specifically. He wrote about the debt factor and preferred net cash. Keep the number, soften the attribution to "consistent with Lynch's stated preference" rather than "his figure."

**P/E versus own five-year median** is a good measure and it isn't his. Attribute it to practice. Note also that with PEG ≤ 1.0 also at REQ, the profile requires cheapness both absolutely and relative to the company's own history, which is a heavy double gate for a growth profile and will reject good fast growers in any period where the whole category re-rates.

### Discount Closure profile

The framing is right and the honesty about the swing-trading mismatch is the best writing in the document. Three things.

**The median is contaminated by the discount.** EV/EBIT versus its own five-year median includes the current depressed period in the median, which drags the reference point toward the current reading and understates the discount. Compute the median excluding the trailing four quarters.

**Missing, and material: the maturity wall.** The profile's characteristic failure is the value trap, and every guard it has is a solvency level or a trend. The specific mechanism by which cheap companies become zeroes on a 24-month horizon is a refinancing that has to happen inside the holding period. Debt maturities are tagged (the next-twelve-months and by-year repayment elements). Add: debt due within 24 months divided by (cash plus two times TTM free cash flow) ≤ 1.0, at REQ. This displaces the accruals BONUS, or the absolute EV/EBIT test if you accept the Greenblatt objection below.

**Your Greenblatt caveat is correct and generalizes further than you took it.** You wrote that freezing his earnings yield at an absolute threshold misrepresents a cross-sectional ranking method, and that this is why there's no Greenblatt profile. The same objection applies to Graham and Lynch: both are portfolio methods with expected loser rates built in, and both stated as much. A tool that renders a verdict on one security at a time is silently promising something none of these methods deliver, which is that this particular stock will work. That belongs on the config page for all four profiles, not just as the reason one profile is absent.

---

## 5. Two things about how the measures are combined

**The X-of-Y quota assumes the Y are independent evidence, and they are heavily correlated.** In the Buffett profile, ROE and ROIC measure returns, FCF margin and cash conversion measure the same cash generation, and revenue CAGR and NI-vs-revenue CAGR share an input. A company can clear 7 of 9 by being excellent at one thing measured four ways while being weak on leverage and dilution. In Graham, P/E, P/B, and the combined multiple are three slots holding two independent numbers, so a stock cheap on both automatically banks three REQ passes. Group the criteria by what they measure (returns, leverage, growth, earnings quality, valuation, capital allocation) and require coverage across groups rather than a raw count. This is a bigger correctness issue than any individual threshold in the document, because it is systematically biased in the direction of passing.

**Every absolute valuation threshold is frozen to a rate environment, and the document identifies this once then commits it five more times.** You correctly flag it at Graham metric 15 and propose a single manual field. But Graham's P/E of 15, Discount Closure's EV/EBIT of 8 and 8% FCF yield, and arguably its 0.70x median discount are all absolute price levels calibrated against an implicit cost of capital. The manual Treasury field should feed all of them, not one. The exception, as above, is Buffett's owner earnings yield, and the reason it's an exception is worth writing down rather than treated as an oversight.

---

Two structural changes carry most of the value here and they're cheap: three-year averaged endpoints on every CAGR in the document (Graham's construction, already present in one place), and confirmation requirements keyed to how much one observation can move the estimator rather than to window length. Between them they resolve most of questions 1 and 2 and remove a set of false reds you haven't hit yet.