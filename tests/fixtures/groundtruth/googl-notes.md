# GOOGL (Alphabet Inc., CIK 1652044) — hand-read ground truth notes

Method: primary HTML documents only, fetched from
`https://www.sec.gov/Archives/edgar/data/1652044/{accn}/{primaryDocument}` with
User-Agent the user's declared SEC identity (name + email, redacted here). No XBRL data APIs, no
R*.htm renderings, no FilingSummary.xml. Every figure re-grepped in the raw HTML
in its printed form.

## Filings

| FY | Accession | Primary doc | Filed |
|----|-----------|-------------|-------|
| FY2024 10-K | 0001652044-25-000014 | goog-20241231.htm | 2025-02-05 |
| FY2017 10-K | 0001652044-18-000007 | goog10-kq42017.htm | 2018-02-06 |

## Cover page (FY2024 10-K) — share counts are stated in MILLIONS

Unusual and eval-relevant: Alphabet's cover page does NOT print whole-share
counts. Verbatim:

> "As of January 28, 2025, there were 5,833 million shares of Alphabet's
> Class A stock outstanding, 860 million shares of Alphabet's Class B stock
> outstanding, and 5,497 million shares of the Alphabet's Class C stock
> outstanding."

("of the Alphabet's" is a typo as printed in the filing.) The inline XBRL tags
carry `scale="6"` and `decimals="INF"`, i.e. the printed numbers are exact in
millions — the whole-unit values 5,833,000,000 / 860,000,000 / 5,497,000,000 are
the tagged values, but as PRINTED the precision is whole millions. An extractor
that expects whole shares on the cover will be off by a factor of 1e6 unless it
reads the word "million".

## Balance sheet aggregation of the classes (FY2024 10-K)

The Dec 31, 2024 balance sheet has ONE equity caption combining all three
share classes AND additional paid-in capital:

> "Class A, Class B, and Class C stock and additional paid-in capital, $0.001
> par value per share: 300,000 shares authorized (Class A 180,000, Class B
> 60,000, Class C 60,000); 12,460 (Class A 5,899, Class B 870, Class C 5,691)
> and 12,211 (Class A 5,835, Class B 861, Class C 5,515) shares issued and
> outstanding"

- Column order is 2023 | 2024, so the FIRST count group (12,460 total) is
  Dec 31, 2023 and the SECOND (12,211 total) is Dec 31, 2024.
- Share counts in the caption are in millions (header: "in millions, except
  par value per share amounts").
- Issued = outstanding (single "issued and outstanding" phrase; no treasury).
- Dollar amounts on that line: 76,534 (2023) and 84,800 (2024), $ millions.
  There is no separate common-stock line — par + APIC are one number. NCI and
  redeemable NCI are also stated (Note) to be included within additional
  paid-in capital.
- Cover counts (Jan 28, 2025: A 5,833 / B 860 / C 5,497) differ slightly from
  balance-sheet counts (Dec 31, 2024: A 5,835 / B 861 / C 5,515) because of
  the later as-of date and continuing buybacks — both are correct; they are
  different dates.

## Income statement / cash flow (FY2024 10-K, FY2024 column)

- Revenues: $350,018 (millions) — three-year columns 2022 | 2023 | 2024.
- Income from operations: 112,390 (millions).
- Net cash provided by operating activities: 125,299 (millions).
- Purchases of property and equipment: (52,535) — parentheses as printed,
  investing section. Only occurrence of 52,535 in the document.

## FY2017 10-K (FY2017 column; columns 2015 | 2016 | 2017)

- Revenues: $110,855 (millions; header "In millions, except per share amounts").
- Income from operations: 26,146 (millions).
  Row as printed: 19,360 | 23,716 | 26,146.

## Verification greps (raw HTML occurrence counts)

fy2024: "350,018" x8, "112,390" x4, "125,299" x2, "52,535" x1 (wrapped in
parentheses in the source), "5,833" x1, "5,497" x1, "12,211" x2, "12,460" x4,
"5,835" x1, "5,899" x1. fy2017: "110,855" x7, "26,146" x3.

## Ambiguities

- Cover-page scale: printed in millions, not whole shares (see above). This is
  the main trap for this multi-class case.
- The balance sheet gives no per-class dollar split; par is immaterial and
  merged with APIC.
- "As of January 28, 2025" in the source HTML uses a non-breaking space
  (January&#160;28) and is split across spans — plain-text grep for the date
  fails on the raw HTML but the date is as recorded.
