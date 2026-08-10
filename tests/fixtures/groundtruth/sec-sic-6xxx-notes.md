# SEC SIC codes 6000–6999 — the published list

`sec-sic-6xxx.json` is every code the SEC publishes in the 6000–6999 band, with
the office it routes to and the industry title, exactly as published.

Method: fetched from
`https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list`
with a User-Agent carrying a name and a real email address (the SEC requires
it). The page's one table was parsed and the 6xxx rows kept verbatim — no
titles were reworded, no codes were inferred, and nothing was added from the
1987 SIC manual, which is a different and larger list. The SEC's list is the
right one here because the only SIC this program ever sees is the one EDGAR
assigns to a filer.

Forty-one codes. That is the whole band, and its being a **closed published
set** is what `engine/industry.py` relies on: it classifies code by code
rather than by numeric range, because a range is a statement about codes that
do not exist, and every one of the ranges an ordinary reading suggests is
wrong somewhere.

## What the ranges get wrong

Worth recording, because these were found by reading the list rather than by
reasoning about it, and each one is a company that would have been evaluated
badly or refused wrongly.

| range you would reach for | what it does |
|---|---|
| 6020–6199 "banks and lenders" | ends one code short of the broker-dealers at 6200/6211/6221, so Bear Stearns and Charles Schwab fall outside it |
| 6311–6411 "insurance" | sweeps in 6411, which is insurance **agents and brokers** — Marsh, Aon, Brown & Brown — fee businesses that ordinary measures describe perfectly well |
| 6500–6798 "real estate" | sweeps in 6770 Blank Checks (SPACs), 6792 Oil Royalty Traders and 6795 Mineral Royalty Traders, none of which is real estate; and 6531, which is agents acting **for others** rather than owners |
| anything ending at 6798 | leaves out 6799 Investors, NEC — closed-end funds, BDCs and investment holding companies |

## The codes that cannot be classified from the code

Three of the forty-one are catch-alls the SEC assigns to filers whose
economics are opposite. Sampled from EDGAR's own company search
(`browse-edgar?action=getcompany&SIC=nnnn&type=10-K`) on 2026-08-10:

- **6199 Finance Services** — American Express and Synchrony Financial (both
  bank holding companies) file here, alongside payment processors, mortgage
  pass-through trusts and crypto shells. The SEC's own list routes this code
  to "Office of Finance **or** Office of Crypto Assets", which is the source
  saying out loud that the code does not settle it.
- **6200 Security & Commodity Brokers, Dealers, Exchanges & Services** —
  BATS Global Markets, Archipelago Holdings and the Chicago Board of Trade
  (exchanges, asset-light) file here alongside BGC Partners (an inter-dealer
  broker) and several closed-end funds.
- **6211 Security Brokers, Dealers & Flotation Companies** — Bear Stearns and
  Ameritrade (balance sheets of trading inventory and customer cash) file here
  alongside BlackRock (an asset manager).

Synchrony sitting at 6199 is the one that matters most: it is the company this
whole piece of work was commissioned about, and it carries the code an
exception list would have exempted.
