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

---

## Added for the goodwill-outcome and maintenance-capex measures

Same method and the same two filings. Everything below is from the FY2018 10-K
(`form10-k2018.htm`, accession 0001637459-19-000049).

**Goodwill impairment.** The Consolidated Statements of Income carry it as its
own caption on the face of the statement, which is what makes this company the
counterpart to Target's combined caption:

| Caption | Dec 29 2018 | Dec 30 2017 | Dec 31 2016 |
|---|---|---|---|
| Selling, general and administrative expenses, excluding impairment losses | 3,205 | 2,927 | 3,527 |
| **Goodwill impairment losses** | **7,008** | **—** | **—** |
| Intangible asset impairment losses | 8,928 | 49 | 18 |
| Selling, general and administrative expenses | 19,141 | 2,976 | 3,545 |

(The 2017 and 2016 columns sit under the "As Restated & Recast" spanning
header, as everywhere else in this filing.)

Three things this case pins:

1. **The write-off itself**, 7,008 in $ millions, the largest figure in this
   fixture set and the shape the measure exists to catch.
2. **That goodwill is separable here.** 8,928 of other intangibles was written
   off in the same year, on the adjacent line. A mapping that reached for the
   larger figure, or for a combined one, would produce a perfectly plausible
   number — so the intangible charge is recorded in `khc.json` as well,
   precisely so that a wrong answer is recognisable rather than reasonable.
3. **The em-dash is a nil.** FY2017 and FY2016 print "—" and tag zero. A
   five-year window over this company therefore spans a stated nil and the
   largest charge in the set, and has to read them as 0 and 7,008 rather than
   as absent and 7,008.

**Amortization of intangibles.** From the Goodwill and Intangible Assets note:
"Amortization expense for definite-lived intangible assets was $290 million in
2018, $278 million in 2017, and $267 million in 2016."

Against the 983 of "Depreciation and amortization" on the Consolidated
Statements of Cash Flows, that leaves 693 of depreciation — which is the figure
the maintenance-capex proxy should be comparing capital spending against, and
not the 983. The segment note prints the same 983 as "Total depreciation and
amortization expense", built up from 626 + 39 + 102 + 119 + 97, so the two
presentations agree.

Note where the amortization figure is tagged rather than merely printed: in
this filer it is in the intangibles note, not on the cash flow face. Which
statement a fact was presented on plays no part in resolution, so it costs
nothing — but it is the first thing anyone auditing the mapping will wonder
about, and Target tags it the same way.
