# Ground truth — hand-read from primary documents

These figures were read by a person from the primary 10-K / 10-KT HTML documents
on SEC EDGAR and recorded with their printed captions, scales and signs. They
were **never** taken from any XBRL API, R*.htm rendering, FilingSummary.xml, or
third-party site. That is the entire point of them: they are the independent
evidence the extraction pipeline is judged against, so regenerating them from
XBRL by any route would make the test circular. Do not "refresh" these files
from the pipeline. If one is wrong, re-read the filing.

The companies are real — MSFT, TGT, KHC, PRGO, GOOGL, O — with real accession
numbers, because a citation of a published filing is only evidence if it can be
checked. This is a deliberate, approved exception to the invented-companies
rule for sample data (see CLAUDE.md): these are factual citations of public
records, not model portfolios, and nothing here reads as a view on any security.

Each company was chosen for a specific failure mode:

| File | Case |
|---|---|
| msft.json | Baseline; ASC 606 full-retrospective restatement (FY2017 revenue as printed 89,950M exists only in the original filing) |
| tgt.json | 52/53-week retailer (fiscal 2023 = 53 weeks); FY2016 prints no "Operating income" caption |
| khc.json | 2019 restatement of FY2016–17, plus an ASU 2017-07 recast — original, restated and restated&recast values all recorded |
| prgo.json | Fiscal-year-end change; 10-KT transition stub Jun 28 – Dec 31 2015 |
| googl.json | Three share classes; cover-page counts printed in millions |
| o.json | REIT: extension-tagged debt line, no operating-income subtotal, no PP&E capex caption, statements in thousands |

The `-notes.md` files record how each figure was located and verified, and the
judgement calls made. Read them before touching the tests that consume these.
