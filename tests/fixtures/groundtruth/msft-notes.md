# MSFT ground-truth notes (hand-read from primary 10-K HTML documents)

Method: downloaded each filing's primary document from EDGAR Archives (User-Agent
the user's declared SEC identity (name + email, redacted here)), stripped HTML to pipe-delimited text
preserving table cells, read the statements directly. No XBRL APIs, no R*.htm
renderings, no FilingSummary.xml. Every number was re-verified by grepping its
printed form in the raw HTML a second time (all hits confirmed).

## FY2024 10-K (accession 0000950170-24-087843, period 2024-06-30)

- Income statement header: "INCOME STATEMENTS (In millions, except per share amounts)".
  Balance sheet and cash flows headers: "(In millions)".
- Capex caption is exactly "Additions to property and equipment", printed "(44,477)"
  under Investing. It does NOT mention finance leases; Microsoft discloses finance-lease
  asset additions as a non-cash item elsewhere, so this line is cash capex only.
- Balance sheet debt lines at 2024-06-30, exactly three:
  - "Short-term debt" 6,693 (2023 column shows 0 — MSFT reintroduced commercial paper
    in FY2024; there is no separate "commercial paper" caption, it is inside Short-term debt)
  - "Current portion of long-term debt" 2,249
  - "Long-term debt" 42,688
  Not counted as debt (deliberately excluded): Short-term/Long-term income taxes,
  unearned revenue, operating lease liabilities, other liabilities.
- Cover page: "As of July 25, 2024, there were 7,433,038,381 shares of common stock
  outstanding." Note this as-of date (2024-07-25) is AFTER fiscal year end; the balance
  sheet caption separately says shares outstanding 7,434 (millions) at 6/30/2024 and
  Note 16 shows balance end of year 7,434 (millions). These are different measurement
  dates — the recorded cover figure is the 7,433,038,381 / July 25, 2024 one as asked.
- Other income (expense), net is negative in FY2024: "(1,646)" — not recorded as a
  target metric, noted only to flag that parenthesized negatives render as
  "(1,646 | )" in the extracted text (close-paren in its own cell).

## FY2017 10-K (accession 0001564590-17-014900, period 2017-06-30)

- Income statement header: "INCOME STATEMENTS (In millions, except per share amounts)".
- FY2017 income statement includes an extra operating-expense line vs FY2024:
  "Impairment, integration, and restructuring" 306. Operating income 22,326 is the
  printed subtotal after that line.
- Capex caption exactly "Additions to property and equipment", printed "(8,129)" under
  Investing. No lease qualifier.
- Balance sheet debt lines at 2017-06-30, exactly three:
  - "Short-term debt" 9,072 (again no separate commercial-paper caption on the face;
    the debt note describes its composition, face amounts differ from carrying)
  - "Current portion of long-term debt" 1,049 (2016 column 0)
  - "Long-term debt" 76,073
  Excluded: "Income taxes" 718 (taxes payable, not debt), "Securities lending
  payable" 97 (collateral obligation, not borrowings), unearned revenue, deferred
  income taxes, other long-term liabilities.
- FY2017 cash flow statement (pre-ASC 606 presentation) shows gross
  "Deferral of unearned revenue" / "Recognition of unearned revenue" lines; the printed
  "Net cash from operations" subtotal 39,507 is what was recorded.

## Ambiguities / judgment calls

1. "Every debt line": both balance sheets present exactly three debt captions
   (short-term debt, current portion of long-term debt, long-term debt). No
   commercial-paper caption appears on the face of either balance sheet.
2. Shares outstanding: three candidate figures exist in the FY2024 filing (cover
   7,433,038,381 at 7/25/2024; balance-sheet caption 7,434 million at 6/30/2024;
   Note 16 roll-forward 7,434 million). The cover figure was recorded per instructions.
3. Signs: capex recorded negative (parentheses as printed). Balance-sheet debt recorded
   positive (printed without parentheses).

---

## Net property

Both years, from the Balance Sheets, caption "Property and equipment, net of
accumulated depreciation of $X and $Y" — the accumulated-depreciation figures
are inside the caption itself, so the printed value is already net. FY2024:
135,591 (accumulated depreciation 76,421); FY2017: 23,734 (accumulated
depreciation 24,179). Both in millions, current-year column first on this
filer's sheet.

**This is the case that proves the plain element is not narrow, and it was
first written up here as though it were.** Microsoft tags one undimensioned
`us-gaap:PropertyPlantAndEquipmentNet` = 135,591 on the balance-sheet face,
and a second, dimensioned `LeaseContractualTermAxis = FinanceLeaseMember`
fact = 25,862 in the lease note. The second is inside the first, and the
filing says so in words rather than leaving it to be worked out:

> Finance leases are included in property and equipment, other current
> liabilities, and other long-term liabilities in our consolidated balance
> sheets.

So nineteen percent of the figure served here is a finance-lease right-of-use
asset. The operating-lease asset is genuinely separate — "Operating lease
right-of-use assets" 18,961 is its own line directly below, under its own
element — and nothing in the map reaches it.

That matters because the concept map briefly refused the longer ASC 842
element on the stated grounds that the plain one excluded leased assets. It
does not, this filing is the proof, and the refusal would have made Target
absent at four percent lease content while serving Microsoft at nineteen. See
the note in `config/concept-map.yaml`.
