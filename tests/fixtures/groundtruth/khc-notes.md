# KHC (The Kraft Heinz Company, CIK 1637459) — restatement case, hand-read notes

Method: primary HTML documents only, downloaded from SEC Archives with UA
the user's declared SEC identity (name + email, redacted here), converted to text on disk with
python3, read by hand. No XBRL data APIs, no R*.htm, no FilingSummary.xml,
no third-party sites. Every figure re-grepped in the raw HTML in its printed
form to verify.

## Filings read

1. **Original FY2017 10-K** — accession 0001637459-18-000015, filed 2018-02-16,
   period 2017-12-30, primary doc `form10-k2017.htm`.
   **No 10-K/A exists for this period** (checked every form starting with
   "10-K" in the submissions JSON; `filings.files` is empty, and `recent`
   reaches back to 2015-03-25, covering the company's whole EDGAR history).
2. **FY2018 10-K** — accession 0001637459-19-000049, filed 2019-06-07 (late,
   because of the restatement), period 2018-12-29, primary doc
   `form10-k2018.htm`. Contains restated FY2017/FY2016 comparatives.

## Column markings in the FY2018 10-K

- Income statement: a spanning header **"As Restated & Recast"** sits over the
  December 30, 2017 and December 31, 2016 columns only (verified in raw HTML:
  colspan-7 cell covering the two comparative 3-column groups; the 2018 column
  is outside it).
- Cash flow statement: same structure but the spanning header reads
  **"As Restated"** (no "& Recast") over the 2017/2016 columns.
- "Recast" ≠ restatement: the filing states the restated FY2017/FY2016 income
  statements also retrospectively apply **ASU 2017-07** (pension/postretirement
  net periodic benefit cost presentation), adopted Q1 2018, and labels that
  effect "As Recast".

## Did the restatement change FY2017 net sales / operating income?

Yes to both. From the restatement note's reconciliation table
("Consolidated Statement of Income ... For the Year Ended December 30, 2017",
columns: As Previously Reported / Restatement Impacts / As Restated /
ASU Adoption Impacts / As Restated & Recast), in $ millions:

| Line | As previously reported | Restatement impact | As restated | ASU recast | As restated & recast |
|---|---|---|---|---|---|
| Net sales | 26,232 | (156) | 26,076 | — | 26,076 |
| Operating income/(loss) | 6,773 | (80) | 6,693 | (636) | 6,057 |

- **Net sales**: restatement lowered FY2017 net sales by **$156M**
  (26,232 → 26,076). The recast had no effect on net sales.
- **Operating income**: the restatement itself lowered it by **$80M**
  (6,773 → 6,693). The additional **$(636)M** to reach the printed comparative
  6,057 is the ASU 2017-07 recast (moves non-service pension credits out of
  operating lines into "Other expense/(income), net" — that line goes
  9 → (627) in the same table). So the face-of-statement comparative change
  of 716 (6,773 → 6,057) is restatement + recast combined; restatement alone
  is 80.

## Operating income subtotal — printed?

- Original FY2017 10-K: **yes** — caption "Operating income", FY2017 value
  6,773 ($ millions). (So gross profit fallback not needed; for reference,
  gross profit as originally printed was 9,703.)
- FY2018 10-K: **yes** — caption "Operating income/(loss)"; FY2018 value
  (10,220), printed in parentheses (operating loss, driven by 7,008 goodwill
  and 8,928 intangible impairment losses).

## Other line-item observations

- Caption drift: original FY2017 statement prints a single
  "Selling, general and administrative expenses" line (2,930); the FY2018 10-K
  splits it into "...excluding impairment losses" (2,881 as previously
  reported), goodwill impairment, and intangible asset impairment (49), then a
  combined SG&A total.
- FY2018 net cash provided by operating activities: **2,574** ($ millions),
  caption "Net cash provided by/(used for) operating activities". MD&A rounds
  this to "$2.6 billion".
- Stated scale everywhere: "(in millions, except per share data)" on income
  statements; "(in millions)" on cash flows. All values USD.

## Ambiguities / cautions for scoring

1. An answer of **6,693** for restated FY2017 operating income is defensible
   ("As Restated" before recast, from the reconciliation note) but the figure
   printed in the FY2018 10-K's face income statement comparative column is
   **6,057** ("As Restated & Recast"). Both recorded in khc.json.
2. Restated FY2017 net sales is unambiguous: 26,076 in both the face statement
   and the reconciliation's "As Restated" column (recast impact nil).
3. The FY2018 auditor's report is adverse on ICFR (material weaknesses) —
   context only, no figures taken from it.
