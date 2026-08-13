# TGT ground-truth notes (hand-read from primary 10-K HTML documents)

Source documents (only sources used — no XBRL APIs, no R*.htm, no FilingSummary.xml):

- FY2023 10-K: accession 0000027419-24-000032, primary doc `tgt-20240203.htm`
  https://www.sec.gov/Archives/edgar/data/27419/000002741924000032/tgt-20240203.htm
- FY2016 10-K: accession 0000027419-17-000008, primary doc `tgt-20170128x10k.htm`
  https://www.sec.gov/Archives/edgar/data/27419/000002741917000008/tgt-20170128x10k.htm

Every figure below was verified by re-grepping its printed form in the plain-text
conversion of the raw HTML (local copies: `../tgt_fy2023.txt`, `../tgt_fy2016.txt`).

## 52/53-week facts (the reason TGT is in the sample)

- Target's fiscal year "ends on the Saturday nearest January 31" (stated in
  Note 1 / Summary of Accounting Policies of both filings).
- **Fiscal 2023 was a 53-week year, ended February 3, 2024.** FY2023 10-K, Note 1:
  "Fiscal 2023 ended February 3, 2024, and consisted of 53 weeks. Fiscal 2022 and
  2021 ended January 28, 2023, and January 29, 2022, respectively, and consisted
  of 52 weeks. Fiscal 2024 will end February 1, 2025, and will consist of 52 weeks."
- Each financial statement in the FY2023 10-K carries the footnote:
  "Note: 2023 consisted of 53 weeks compared with 52 weeks in 2022 and 2021."
- MD&A of the FY2023 10-K: "(a) 2023 consisted of 53 weeks. The extra week in 2023
  contributed $1.7 billion of sales."
- **Fiscal 2016 was a 52-week year, ended January 28, 2017.** FY2016 10-K, Note 1
  (Summary of Accounting Policies): "Fiscal 2016 ended January 28, 2017, and
  consisted of 52 weeks. Fiscal 2015 ended January 30, 2016, and consisted of 52
  weeks. Fiscal 2014 ended January 31, 2015, and consisted of 52 weeks. Fiscal 2017
  will end February 3, 2018, and will consist of 53 weeks."
- In the FY2016 10-K's Selected Financial Data (Item 6), footnote (a) "Consisted of
  53 weeks." refers to fiscal 2012, not fiscal 2016.
- The statements themselves do not print "53 weeks ended February 3, 2024" as a
  column heading; columns are simply headed "2023 2022 2021" (FY2023) and
  "2016 2015 2014" (FY2016), with the week counts stated in footnotes/Note 1 as
  quoted above.

## FY2023 (53 weeks ended February 3, 2024) — all "(millions, except per share data)" / "(millions)"

Consolidated Statements of Operations, 2023 column:
- Sales: $ 105,803
- Other revenue: 1,609
- Total revenue: 107,412
- Operating income: 5,707

Consolidated Statements of Cash Flows, 2023 column:
- Cash provided by operating activities: 8,621
- Expenditures for property and equipment: (4,806) — printed in parentheses under
  "Investing activities"

## FY2016 (52 weeks ended January 28, 2017) — "(millions, except per share data)" / "(millions)"

Consolidated Statements of Operations, 2016 column (pre-ASC 606 presentation):
- Sales: $ 69,495 — **the only revenue line printed.** There is no "Other revenue"
  and no "Total revenue" line. (Credit card revenues were only ever combined into
  a revenue line in fiscal 2012 per Selected Financial Data footnote (b).)
- There is **no line captioned "Operating income."** The printed subtotal is
  "Earnings from continuing operations before interest expense and income taxes: 4,969".
  Statement order: Sales, Cost of sales, Gross margin (20,623), SG&A (13,356),
  Depreciation and amortization (2,298), Gain on sale (—), then the EBIT line.

Consolidated Statements of Cash Flows, 2016 column:
- Cash provided by operating activities—continuing operations: 5,329
- Cash provided by / (required for) operating activities—discontinued operations: 107
- **Cash provided by operations: 5,436** (the total line; caption is "operations",
  not "operating activities")
- Expenditures for property and equipment: (1,547) — printed in parentheses under
  "Investing activities"

## Ambiguities / judgement calls

1. **FY2016 "operating income"**: no such caption exists. Recorded the printed EBIT
   subtotal ("Earnings from continuing operations before interest expense and
   income taxes", 4,969) as the operating-income-equivalent, flagged in the JSON.
   An extractor answering "operating income" for TGT FY2016 has no exact-caption match.
2. **FY2016 operating cash flow**: two candidate totals — continuing-only (5,329)
   vs including discontinued (5,436, the statement's bottom-line "Cash provided by
   operations"). Both recorded; 5,436 is tagged as the primary `cash_from_operations`.
3. Capex sign: both filings print capex in parentheses (cash outflow);
   `value_usd` recorded as negative per instructions.
4. FY2016 net earnings context (not requested, for reference): Net earnings 2,737 =
   continuing 2,669 + discontinued 68.

---

## Added for the maintenance-capex and goodwill-outcome measures

Same method: the FY2016 10-K primary document (`tgt-20170128x10k.htm`,
accession 0000027419-17-000008) read by hand. Both figures live in the notes as
prose rather than as statement lines, which is worth knowing before looking for
them: neither has a caption to grep for.

**Amortization of intangibles.** From the Goodwill and Intangible Assets note:
"Amortization expense was $18 million, $23 million, and $22 million in 2016,
2015, and 2014, respectively." So fiscal 2016 (ended January 28, 2017) is 18,
fiscal 2015 is 23, fiscal 2014 is 22.

**And the arithmetic that makes it useful,** which is the reason this filing was
chosen for the figure rather than any other. The property note states
"Depreciation and capital lease amortization expense for 2016, 2015, and 2014
was $2,280 million, $2,191 million, and $2,108 million". The Consolidated
Statements of Cash Flows prints "Depreciation and amortization" of 2,298, 2,213
and 2,129 for the same three years.

| Year | Depreciation, per the property note | Intangible amortization | Sum | D&A on the cash flow statement |
|---|---|---|---|---|
| 2016 | 2,280 | 18 | 2,298 | 2,298 |
| 2015 | 2,191 | 23 | 2,214 | 2,213 |
| 2014 | 2,108 | 22 | 2,130 | 2,129 |

2016 reconciles exactly; 2015 and 2014 are one million out, which is rounding
in figures printed to the million. That is the evidence — read off the printed
document rather than assumed — that the cash-flow D&A line **includes**
intangible amortization, and therefore that subtracting one from the other
leaves depreciation. A measure that subtracts the two when they do not overlap
would understate depreciation and so overstate owner earnings, silently.

**Goodwill impairment, and the combined-caption problem.** From the same note:
"Goodwill totaled $133 million at January 28, 2017 and January 30, 2016. During
2015, we announced our decision to wind down certain noncore operations. As a
result, we recorded a $35 million pretax impairment loss, which included
approximately $23 million of intangible assets and $12 million of goodwill.
These costs were included in SG&A on our Consolidated Statements of Operations,
but were not included in our segment results. No impairments were recorded in
2016 or 2014 as a result of the annual goodwill impairment tests performed."

Two separate things follow.

Fiscal 2015 is the **combined-caption case**. The goodwill charge alone is 12;
the only figure this filer tags is the combined 35. The concept map resolves
the 35 and attaches a caution saying the figure is at or above the goodwill
charge alone — this filing is the evidence for that claim rather than a guess
at it, and a threshold tested against 35 therefore reads more harshly than
intended and never more leniently. The 12 is recoverable by a person reading
the sentence and is not recoverable from any tagged fact.

Fiscal 2016 is the **stated-nil case**: the company says in words that nothing
was written off, and tags the zero. A measure summing five years of write-offs
needs that to be a zero rather than an absence, and needs a year with no figure
at all to stay absent. Both behaviours are pinned in
`test_compute_groundtruth.py`.

---

## Net property, and why it is absent rather than 33,096

FY2023, accession `0000027419-24-000032`, primary document `tgt-20240203.htm`.
The Consolidated Statements of Financial Position print:

> Property and equipment, net … 33,096 … 31,512

read as the FY2023 and FY2022 columns, in millions. The figure is real and it
is on the page. The pipeline reports **absent** for it, on purpose.

The reason is the tag rather than the number. This filer carries no
`us-gaap:PropertyPlantAndEquipmentNet` fact at all; the caption above is tagged
`us-gaap:PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulated
DepreciationAndAmortization`, which since ASC 842 folds the right-of-use asset
from finance leases into the same line. That is a wider quantity than the one
`net_ppe` is declared to serve, and the width is not small for a retailer:
Target's own leased-asset breakdown in the same filing puts it in the billions.

Serving it with a caution was the alternative and is refused for the reason the
`us-gaap:LongTermDebt` fallback was removed from `long_term_debt` — the caution
is read by a person and ignored by the arithmetic. Return on capital divides by
this, so a leased asset in the denominator understates the return, silently,
for every post-2019 retailer and restaurant against every filer still tagging
the narrow element. Comparing those two would be comparing an accounting
convention.

Recorded in `tgt.json` with a `note` rather than left out, so the figure a
reader sees on the page sits beside the reason the pipeline will not serve it.
This is the case that pins the refusal.
