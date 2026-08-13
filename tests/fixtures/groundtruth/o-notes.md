# Realty Income Corporation (O), CIK 0000726728 — hand-read ground truth notes

Sources: primary HTML documents only, fetched with User-Agent
the user's declared SEC identity (name + email, redacted here). No XBRL data APIs, no R*.htm,
no FilingSummary.xml, no third-party sites.

- FY2024 10-K: accession 0000726728-25-000055, filed 2025-02-25, primary doc
  https://www.sec.gov/Archives/edgar/data/726728/000072672825000055/o-20241231.htm
- FY2016 10-K: accession 0001104659-17-011170, filed 2017-02-23, primary doc
  https://www.sec.gov/Archives/edgar/data/726728/000110465917011170/a17-1163_110k.htm

## Scale

Confirmed by reading each statement header:

- FY2024 balance sheet and income statement: "(in thousands, except per share
  amounts)"; cash flow statement: "(in thousands)".
- FY2016 balance sheet and income statement: "(dollars in thousands, except per
  share data)".

Both filings report in THOUSANDS. Any extractor treating these as whole dollars
or millions is off by 10^3.

## Key finding: no operating income subtotal (FY2024)

The FY2024 Consolidated Statements of Income and Comprehensive Income prints NO
"Operating income" subtotal. The structure is:

Total revenue (5,271,142) -> EXPENSES (incl. Depreciation and amortization AND
Interest, both inside total expenses) -> Total expenses (4,489,294) -> Gain on
sales of real estate 117,275 -> Foreign currency and derivative gain (loss),
net 3,420 -> Gain on extinguishment of debt "—" -> Equity in earnings of
unconsolidated entities 7,793 -> Other income, net 23,606 -> Income before
income taxes 933,942 -> Income taxes (66,601) -> Net income 867,341.

Because interest expense sits inside operating-style expenses, any attempt to
derive an "operating income" (Total revenue − Total expenses = 781,848) is NOT a
GAAP operating-income equivalent and is not printed. Ground truth records net
income (867,341 thousand) instead. Net income attributable to the Company:
860,772; net income available to common stockholders: $847,893.

FY2016 similarly has no operating income; it prints "Income from continuing
operations" 316,477 (which equals net income for 2016; discontinued operations
"-"). Income taxes in FY2016 are a line WITHIN total expenses (3,262), unusual
placement — there is no pre-tax income subtotal in FY2016.

## Revenue captions

- FY2024 (2 lines): "Rental (including reimbursable)" $5,043,748; "Other"
  227,394; Total revenue 5,271,142.
- FY2016 (3 lines): "Rental" $1,057,413; "Tenant reimbursements" 43,104;
  "Other" 2,655; Total revenue 1,103,172. Note the pre-2018 presentation splits
  tenant reimbursements out as its own line; post-ASC-842 filings fold it into
  "Rental (including reimbursable)".

## Cash flow / capex (FY2024)

- Net cash provided by operating activities: 3,573,276.
- There is NO "payments to acquire property, plant and equipment" or "capital
  expenditures" caption. Real-estate acquisition/improvement investing captions
  are:
  - "Investment in real estate" (3,262,437)
  - "Improvements to real estate, including leasing costs" (121,411)
  Other investing captions: Investment in unconsolidated entities (70,381);
  Investment in loans (631,650); Proceeds from sales of real estate 589,450;
  Return of investment from unconsolidated entities —; Net proceeds from sale of
  unconsolidated entities —; Proceeds from note receivable 57,300; Insurance
  proceeds received 2,788; Non-refundable escrow deposits (225); Net cash
  acquired in merger 93,683; Net cash used in investing activities (3,342,883).
  An extractor mapping the standard us-gaap PP&E capex tag will find nothing —
  this REIT uses custom/real-estate-specific captions.

## Balance-sheet borrowing lines (total-debt aggregation test)

FY2024 (Dec 31, 2024), four separate lines, all in thousands:

| Caption | As printed |
|---|---|
| Line of credit payable and commercial paper | 1,130,201 |
| Term loans, net | 2,358,417 |
| Mortgages payable, net | 80,784 |
| Notes payable, net | 22,657,592 |

Sum of the four net lines = 26,226,994. The MD&A separately states "Total debt
per the consolidated balance sheets, excluding deferred financing costs and net
premiums and discounts" = $26,510,798 — this is a company aggregate on a
different basis (gross of deferred financing costs and premiums/discounts), so
it intentionally does NOT tie to the sum of the net balance-sheet lines. A
total-debt aggregation over the printed balance sheet should yield 26,226,994
thousand.

Note the combined caption "Line of credit payable and commercial paper" — one
line covers both revolver and commercial paper; they are not separable on the
face of the balance sheet.

FY2016 (Dec 31, 2016), four separate lines, in thousands:

| Caption | As printed |
|---|---|
| Line of credit payable | 1,120,000 |
| Term loans, net | 319,127 |
| Mortgages payable, net | 466,045 |
| Notes payable, net | 3,934,433 |

Sum = 5,839,605 thousand. No commercial paper line in FY2016 (program did not
exist then); the revolver line is "Line of credit payable" (not "net" — carried
at drawn amount).

## Verification

Every recorded printed figure was re-grepped in the raw downloaded HTML and
found (counts >= 1). Figures with count > 1 (e.g. 316,477, 1,103,172, 1,120,000)
recur legitimately in MD&A/selected-financial-data sections of the same filing.

## Ambiguities / cautions

- FY2024 "Other" revenue includes interest income on financing receivables per
  the notes; caption on the face is just "Other".
- FY2016 prints "Income from continuing operations" and a discontinued-
  operations line ("-" for 2016) — an extractor looking for "net income" should
  still find "Net income" 316,477 printed below.
- All FY2024 borrowing lines are "net" (of deferred financing costs and
  premiums/discounts) except the line of credit/commercial paper line.

---

## Net property: a REIT has none of the lines this needs

FY2024, accession `0000726728-25-000055`. Realty Income tags neither
`us-gaap:PropertyPlantAndEquipmentNet` nor a classified balance sheet, so
`net_ppe`, `current_assets`, `current_liabilities` and `short_term_debt` all
resolve absent. Its property is `us-gaap:RealEstateInvestmentPropertyNet` — the
same assets under a different element, because for this filer they are the
business rather than the equipment the business runs on.

Nothing needs fixing here. Return on capital declares itself not meaningful for
`real-estate` before any of that is reached, so the absences are never the
reason a reader is told anything: the industry gate answers first, and it
answers with a sentence about what kind of company this is rather than with a
list of lines that did not resolve.
