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
