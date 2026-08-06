# Metric bank and profiles — authoring notes

Input to the next task. Nothing here has been acted on.

Files written:

- `config/metric-bank.yaml` — 58 computed entries, 3 qualitative entries
- `data.template/profiles/buffett.yaml`
- `data.template/profiles/graham.yaml`
- `data.template/profiles/lynch.yaml`
- `data.template/profiles/discount-closure.yaml`

---

## Decisions taken

**YAML, not JSON.** Every entry carries multi-paragraph prose. YAML block
scalars keep that hand-editable; JSON would put the whole report into escaped
one-line strings. This conflicts with the existing `data.template/*.json`.

**One file per profile.** The rule that no profile may reference, be compared
with, or be merged with another is enforced structurally this way — there is no
sibling in scope to reference, and adding or removing a profile is adding or
removing a file. A single combined file would place all four in one namespace
and make cross-references a typo away.

**Bank in `config/`, profiles in `data.template/profiles/`.** The bank is
static, universal and shipped; the user never edits it. The profiles are
defaults the user is expected to edit, so they follow the existing
`data.template/` seeding path and land in the user data directory. The
filesystem split mirrors the authority split.

**Qualitative entries exist in the bank but no profile references them.** The
report names moat durability, management integrity and capital allocation under
"What the data constraint costs you", but puts none of them in a profile table.
They are defined in the bank; adding them to a profile would have been inventing
a metric.

**Profiles name the bank as `bank: metric-bank`, not a path.** Path resolution
between the repo and the user data directory is the next task's problem.

---

## Could not express in the report's two-threshold model

1. **Sell measured on a different measure than the buy.** Three entries buy on
   one window and exit on another: Buffett FCF margin (buy 5-yr median, exit on
   the current reading below 0), Buffett share count (buy 5-yr change, exit on
   3-yr change above +10%), Graham profitable years (buy 10-of-10 count, exit on
   2 consecutive annual losses). Written as `measured_on:` inside the sell block,
   naming a second bank entry. Needs an evaluator that resolves two bank entries
   for one profile row, and a snapshot that records both.

2. **Sell severity — flag versus exit.** The report's framework gap 4. One place
   needs it: Graham's dividend entry, "BLANK (flag on cut)". Written as a
   separate `flag:` block with `severity: flag` and `never_blocks: true`.

3. **"Flag on a cut" has no measurable definition.** `consecutive_dividend_years`
   only resets when the company stops paying entirely. A dividend that is reduced
   but still positive keeps the streak running and would not flag. Written as
   `delta_entry / falls_below_entry_value`, which catches a suspension and not a
   reduction. Catching a reduction needs a dividends-per-share bank entry.

4. **BONUS scoring is undefined.** Every profile states that BONUS "adds to the
   score, never blocks". The report never says how much a bonus entry adds, what
   range the score has, or what the score is used for once the REQ/CORE verdict
   is settled. Written as `contributes: score` with no weight.

5. **Graham's position clock is not in the Graham section.** The Graham profile
   body says only that it "needs the position clock". The 24-month figure comes
   from the Framework gaps section ("Graham's actual discipline was to sell after
   two years"). Carried into `graham.yaml` on that basis.

6. **Global confirmation versus per-entry persistence.** The report states both a
   global rule ("All sell triggers require the breach on two consecutive
   filings") and per-entry windows ("< 0% for 4 quarters"). Written as a
   profile-level `sell_confirmation` default plus a per-entry `sustained_for`.
   Whether they compose or the per-entry window replaces the default is not
   stated. Configured as: `sustained_for` replaces the default where present.

7. **Graham "2 consecutive annual losses" and the confirmation default.** Set to
   `sell_confirmation: {form: inherent}` on the grounds that the two-year streak
   *is* two consecutive filings. That is an interpretation; the report does not
   address it. Without it, the default would require two consecutive filings each
   showing a two-year loss streak.

8. **Cross-profile comparative reasoning could not be carried.** The report
   justifies several thresholds by comparison with a sibling profile: "Why 2.0
   here and 1.0 in the Buffett profile" (Graham 4, with "Call this one out in the
   UI"), "Compare with Lynch's 0.5" (Graham 10), "Why 0.5 when Graham accepts
   1.0" (Lynch 3), "Why 10% versus 4% in the Buffett profile" (Lynch 4), "Compare
   Buffett's 8x" (Lynch 10), "Why merely positive, when the Buffett profile wants
   a 10% margin" (Lynch 11), "Why the bar is so much lower than Graham's 2.0"
   (Buffett 14), "Looser than Buffett's 2.5" (DC 4), "Why lower than Graham's
   3.0" (DC 3), "The lowest bar of the four profiles" (DC 8), "much shorter than
   the four-quarter window in the Buffett and Lynch profiles" (DC 7), and the
   Buffett counter-argument in Graham 1's sell reasoning. Each was rewritten to
   justify its number on its own terms. The comparative content itself is in no
   file. The report's two instructions to "call this out in the UI" have no home
   in this config, because what they ask to be called out is the comparison.

   Two references to "Graham" survive, in `buffett.yaml` and `lynch.yaml`, both
   in the interest-coverage reasoning ("Graham used 5x as his bond-safety
   standard for average industrials"). These name the historical investor and
   his published standard, the same way the bank cites Altman and Sloan. They
   are not references to `graham.yaml`, which does not use interest coverage at
   all. A mechanical check for sibling profile names will flag them.

9. **Sector-based applicability is prose, not a test.** "Banks and insurers",
   "the company is a financial company", "any company with a captive finance
   arm" are written as prose `test:` strings under `not_meaningful_when`. They
   are not derivable from XBRL company facts.

10. **Conditional reconfiguration advice has no mechanism.** Buffett 6 ("drop
    this to BONUS or raise the sell window" if buying heavy-investment
    companies on purpose) and Lynch 12 ("promote this to CORE" if the growth
    band is widened downward) are carried as `note:` prose.

11. **Sixteen entries have a blank sell and no stated reason for it.** Buffett
    10, 11, 13, 14; Graham 11, 12, 13, 14, 15; Lynch 5, 9, 12, 13, 15; DC 12,
    13. Their `why` reads "The source report records this as blank and gives no
    exit reasoning for it" rather than inventing one.

---

## Entries needing data outside SEC XBRL filings and daily prices

1. **`earnings_yield_to_risk_free_multiple`** — declares the parameter
   `risk_free_rate`. Not in EDGAR, not price data. Left `null` in
   `graham.yaml`, so the entry resolves grey. Used by Graham BONUS 15. The
   report's proposed fix is a single hand-entered field updated quarterly.

2. **`insider_net_buying_6m`** — Form 4 ownership XML, a separate ingestion path
   from XBRL company facts. Used by Lynch BONUS 14 and Discount Closure BONUS
   13. The report names this as the one to defer if build cost matters.

3. **`institutional_ownership_pct`** — 13F filings aggregated across hundreds of
   filers per quarter, 45-day lag, approximate. Used by Lynch BONUS 15.

4. **`ev_ebit_to_own_5y_median` and `pe_to_own_5y_median_pe`** — need 20 quarters
   of *retained* historical prices, not only the current daily price. In scope if
   price history is stored, out of scope if only today's close is fetched. Both
   are load-bearing: the first is Discount Closure's entire thesis.

5. **Sector or industry classification** — required by the applicability tests on
   `roic_median_5y` (banks and insurers), `altman_z_score` (financial
   companies), `total_debt_to_ebitda` and `net_debt_to_ebitda` (captive finance
   arm). Not a tagged XBRL fact. Needs either a classification source or a
   per-security user flag.

6. **Inconsistently tagged XBRL figures** — in EDGAR, but not reliably present:
   `finance lease obligations` (total debt to EBITDA), `retained earnings` and
   `total liabilities` (Altman Z), `short-term investments` (net cash),
   `cost of revenue` (every gross margin entry), `inventory` and
   `accounts receivable` (Lynch 6 and 7).

7. **The three qualitative entries** have no data source by construction. No
   profile references them.

---

## Thresholds believed wrong or ambiguous

Nothing below was changed in the files.

1. **The Buffett blank count is stated three ways.** The Buffett preamble says
   "nine of fifteen sell thresholds are blank". The table has ten blanks
   (entries 3, 5, 7, 9, 10, 11, 12, 13, 14, 15) and five populated (1, 2, 4, 6,
   8). The Framework gaps section says "only four sell triggers total, all of
   them balance-sheet or cash-flow related" — there are five, and two of them
   (ROIC, interest coverage) are neither balance-sheet nor cash-flow. The table
   was taken as authoritative; `buffett.yaml`'s notice says ten and five.

2. **Lynch 5 names no windows.** "EPS CAGR ≤ Revenue CAGR + 10 pp". Lynch buys on
   5-year EPS CAGR (entry 2) and 3-year revenue CAGR (entry 4), so the pairing is
   ambiguous. Configured 5-year against 5-year, matching the EPS growth the
   profile buys on. Flagged in the entry's `note`.

3. **"For 4 quarters" is ambiguous for Buffett 6 and Lynch 11.** The tables read
   as four consecutive quarterly evaluations of the stated (median or TTM)
   measure. The prose reads as four individually negative quarters ("a full year
   of negative free cash flow", "four consecutive negative quarters"). Configured
   as the former, uniform with Discount Closure's two-quarter windows. The
   difference is material: a TTM figure staying negative across four consecutive
   readings fires roughly three quarters later than four negative quarters would.

4. **Buffett 1's `Δentry` unit is not defined.** "Falls ≥ 33% below entry value"
   is read as a relative fall — 0.67 × the value at purchase — not 33 percentage
   points. Written as `unit: percent_of_entry_value`. The report's `Δentry`
   legend says only "change versus the value recorded at purchase".

5. **`total_debt_to_ebitda` grey handling.** The misfire paragraph covers
   regulated utilities, pipelines and REITs (which run 4–6x legitimately) and
   captive finance arms (whose consolidated number is meaningless), then says
   "Mark those grey rather than red." Only the captive-finance case was written
   into the bank's `not_meaningful_when`, because the utility case is a threshold
   mismatch rather than a meaningless number. If "those" covers both, the bank
   entry needs a second applicability condition.

6. **Graham 5 states the same condition twice, in two registers.** "≤ 1.0, and
   working capital must be positive" in the buy test; "Negative working capital
   makes the ratio undefined; grey" three lines later. Treated as applicability
   and put in the bank, not as a second buy condition.

7. **`Δmedian` is redundant on three entries.** Lynch 8 and Discount Closure 1
   and 10 are tagged `Δmedian`, but their bank entries are already
   median-relative — the value *is* the ratio to, or difference from, its own
   median. Both buy and sell are absolute levels of that ratio. The
   `form: delta_median` tag was carried as stated, with `basis:` naming the
   median, but no further transformation is intended at evaluation.

8. **Graham 6 is effectively unreachable until roughly 2030.** "10 of 10"
   profitable years excludes any company with a 2020 impairment or shutdown loss,
   which the report itself acknowledges. Not wrong, but it is the tightest
   binding constraint anywhere in this config, and it sits in CORE where it can
   still be outvoted.

9. **Discount Closure 2 is disowned by its own attribution.** The report states
   that the author of the underlying method would not endorse a fixed level of
   EV/EBIT, and that freezing it at 8.0 makes the profile un-buyable in an
   expensive market and too loose in a cheap one. Carried unchanged, with the
   caveat as an entry note.

10. **Buffett 14 and Graham 4 set the same bank entry at 1.0 and 2.0.** Correct
    and intentional per the report, and noted here only because it is the single
    configuration most likely to be reported as a bug.

11. **Two "flag" cases, one expressible.** The report asks for a flag on a
    dividend cut (Graham 9) and on a goodwill impairment (Buffett 12, "an event,
    not a level"). Only the dividend one got a `flag:` block. The goodwill case
    has no level to express and would need an event detector.
