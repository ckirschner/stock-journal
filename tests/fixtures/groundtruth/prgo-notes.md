# PRGO (Perrigo Company plc, CIK 1585364) — fiscal-year-end-change ground truth

Hand-read from primary EDGAR HTML documents only (no XBRL APIs, no R*.htm renderings).
User-Agent used: the user's declared SEC identity (name + email, redacted here).

## Transition filing identification

- EDGAR form type: **10-KT**, accession **0001585364-16-000245**, filed **2016-02-25**,
  report date 2015-12-31, primary doc `cy15stubperiod10k.htm` (found via
  `CIK0001585364-submissions-001.json` supplemental file — it is older than the
  `filings.recent` window). No 10-KT/A amendment exists.
- Cover page as printed: the filing uses the standard "FORM 10-K" template with the
  TRANSITION REPORT box checked: "[X] TRANSITION REPORT ... For the transition period
  from June 28, 2015 to December 31, 2015". So the exact transition period is
  **June 28, 2015 through December 31, 2015** (Perrigo previously used a 52/53-week
  year ending on the Saturday nearest June 30; prior FY ended June 27, 2015).
- The filing states the stub "is referred to in this report as the six months ended
  December 31, 2015".

## Transition-period income statement (10-KT)

Consolidated Statements of Operations, "(in millions, except per share amounts)".
Columns: **Six Months Ended December 31, 2015** | Fiscal Year Ended June 27, 2015 |
June 28, 2014 | June 29, 2013. Note: the audited statement has NO comparative
six-months-ended December 27, 2014 column (that comparative appears only in
Selected Financial Data / MD&A discussion, unaudited).

Transition column (six months ended Dec 31, 2015):
- Net sales: **$ 2,769.5** (millions) = $2,769,500,000
- Operating income: **94.5** (millions) = $94,500,000 — an explicit "Operating income"
  subtotal IS printed. (In the Selected Financial Data table it appears as "$ 94.5".)
- Also printed on that column for context: Gross profit 1,108.1; Total operating
  expenses 1,013.6; Net income $ 5.6.

## FY2023 10-K

10-K, accession 0001585364-24-000009, filed 2024-02-27, primary doc `prgo-20231231.htm`.
Consolidated Statements of Operations, "(in millions, except per share amounts)".
Columns: Year Ended December 31, 2023 | December 31, 2022 | December 31, 2021.

FY2023 column:
- Net sales: **$ 4,655.6** (millions) = $4,655,600,000
- Operating income: **151.9** (millions) = $151,900,000 — explicit subtotal printed.
  Statement presents discontinued operations separately below tax, so operating
  income is a continuing-operations figure.

## Oddities / trap notes for the eval

1. **Two different "2015 annual reports" exist**: a 10-K for fiscal year ended
   June 27, 2015 (filed 2015-08-13, accession 0001585364-15-000100, net sales
   $4,603.9M) and the 10-KT for the six-month stub ended Dec 31, 2015
   (net sales $2,769.5M). An extractor asking for "FY2015" is ambiguous; the
   transition period must not be conflated with either FY-June-2015 or a full
   calendar 2015.
2. The 10-KT's Selected Financial Data table has 7 columns including an unaudited
   six months ended December 27, 2014 ($2,023.1M net sales) — easy to mis-pick.
3. The first calendar-year 10-K (period 2016-12-31) was filed late, on 2017-05-22.
4. In the FY2023 statement, "Income (loss) from continuing operations" is (130.9)
   for BOTH FY2022 and FY2021 — a genuine coincidence, not a transcription error
   (FY2022: (139.1)+8.2 benefit; FY2021: 258.7−389.6).

## Verification

Re-grepped printed forms in the raw primary HTML:
- `2,769.5` — 7 occurrences in cy15stubperiod10k.htm; statement context
  "...Total operating expenses 1,013.6 Operating income 94.5 ..." confirmed.
- `4,655.6` — 6 occurrences in prgo-20231231.htm; ">151.9<" present; context
  "Total operating expenses 1,528.5 1,376.5 1,005.8 Operating income 151.9" confirmed.

---

## Net property

FY2023, Consolidated Balance Sheets, caption "Property, plant and equipment,
net": 916.4, in millions, December 31 2023 column (prior column 926.3).
Confirmed against the property note, which builds the same 916.4 from land,
buildings, machinery and construction in progress less accumulated
depreciation.

Scale is the thing to notice on this filer: Perrigo prints one decimal place in
millions where the other companies here print whole millions, so 916.4 is
916,400,000 and not 916,000,000.
