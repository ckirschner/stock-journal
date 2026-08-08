# Ledger

A portfolio journal that checks your holdings against rules you wrote, so the
decision gets made once, calmly and in advance, instead of every time you look
at a price.

It never places a trade and holds no broker credentials.

## Run it

```
pip install -r requirements.txt
python app.py
```

On first run the app creates a data directory outside the project and copies an
empty template into it. Open the **Data** tab and choose *Load sample data* to
see the thing populated; *Clear everything* when you're done looking.

```
python app.py --reset     start over from the template
python app.py --debug     open the web inspector
```

## Where your data lives

Never in the project folder.

| OS      | Location                                  |
|---------|-------------------------------------------|
| Windows | `%APPDATA%\Ledger`                        |
| macOS   | `~/Library/Application Support/Ledger`    |
| Linux   | `~/.local/share/Ledger`                   |

Set `LEDGER_DATA` to move it, onto a synced drive for instance.

Cloning or pushing this repository can never carry your positions, notes or
ideas with it: `.gitignore` excludes every data path, and only the empty
template ships with the code. Back up with **Data → Export**, which writes one
timestamped JSON file you can put wherever you like.

## How the verdict works

Rules live in **profiles** — YAML files in your data directory, one lens per
strategy. A profile references entries in the **metric bank**
(`config/metric-bank.yaml`), which defines what each value *is* and holds no
thresholds; every level, tier and rollup rule belongs to the profile. Four
profiles ship as editable defaults. Switching the lens re-reads the same data
through a different profile, instantly.

The buy verdict is three-valued, per the profile's own rollup:

1. Any **required** entry red → No buy.
2. Not enough **core** entries green → No buy.
3. If grey entries — no value recorded, or a value that isn't meaningful for
   this company — could still change the outcome → Can't say. Grey propagates;
   it is never a pass and never a failure.
4. Otherwise → Buy. **Bonus** entries only ever add to a score.

Buy rules and sell rules are not the same thing. A holding is watched against
its profile's *sell* thresholds, and most sell breaches need the breach on
consecutive filings before they count — the tool reports a first-reading
breach as *unconfirmed* rather than firing, because panicking you out on one
quarter's noise is the exact failure the confirmation exists to prevent.
Confirmation is checked against the stored filings themselves: the breach must
appear on the required run of reports that actually brought new numbers for
that metric (only the report that first delivered each period counts — a
re-filing of a period already counted adds nothing — and a report that
can't be read pauses the count: it neither confirms nor resets). A breach in
progress says how many reports it has, how many it needs, and when it could
next be confirmed. For metrics built on annual figures that run counts annual
reports, so confirmation can genuinely take a year or more — the watch says
so rather than hiding it. The position clocks (Graham and Discount Closure
sell on a 24-month calendar) need no filing history and fire outright.

## The parts worth knowing about

### Entry snapshots are frozen

When you record a purchase, every metric value, the verdict, and the profile
(with its version) that produced it are written once and never recomputed. If
they were recomputed, restated filings and amended rules would quietly rewrite
history, and the journal would lose the only thing that makes it a journal.
The detail page shows entry → now for every metric, both sides labelled with
the profile that produced them, so you read the thesis holding or decaying
rather than just a colour.

### Buying against the signal is recorded, not blocked

The tool can't stop you and shouldn't try. It captures what the rules said,
which rules failed, and your written reason for going ahead. Previous holdings
then compares override trades against compliant ones.

The per-rule breakdown is the part that earns its keep. If overriding one
particular rule keeps working out, that rule is miscalibrated, not you. Widen
it, and write down why.

### Exits are grouped by reason

Closed positions keep getting priced. If *Panic* keeps showing a strong return
*after* you sold, that is a finding you would never get from a tool that drops
the ticker the day you exit.

### Expected value is computed, never typed

There is no target price field anywhere. You enter assumptions and the number
is solved for, so when the estimate turns out wrong you can see *which
assumption* was wrong.

Reverse DCF is the default. It solves for the growth rate today's price already
requires, which is a far easier question to answer honestly than "what is this
worth?". Scenario weighting takes bear, base and bull with probabilities that
must total 100%, and makes you enter the bear case first. Owner earnings
capitalises normalised cash flow at your discount rate, then takes a required
discount off the result.

### Fetched data never outranks you

**Fetch data** on a security pulls the company's full filing history from SEC
EDGAR (raw reported figures, per filing, stored exactly as tagged) and its
daily price history from Tiingo (as-traded closes plus split/dividend events —
never a pre-adjusted series, because sources rewrite adjusted history
retroactively). Every metric the bank can compute from that is computed on the
fly; nothing derived is ever saved, and a hand-entered value always wins over
a computed one, visibly — the computed value stays on screen beside it.

An entry that cannot be computed is absent with the reason, in place: source
doesn't carry it, the mapping is ambiguous, a restatement makes the window
mix accounting bases, or the data simply hasn't been fetched. Absence is never
zero. Multi-year windows refuse to mix accounting bases by construction — a
five-year CAGR spliced across a restatement is arithmetic on two different
definitions, so it reports why it can't compute instead.

Fetching happens only when you press the button. The SEC requires every
automated tool to identify itself (name + monitored email — set it on the
Data tab); prices need your own free Tiingo key. Each 10-K's price × shares is
cross-checked against the company's own reported public float, which catches
adjusted-price, split-basis, currency and share-class errors in one
comparison; the result is on each security's Data coverage section.

### Profile changes are versioned, even hand-edits

Profiles are edited by hand, so changes happen outside the app. On every load
the app compares each profile against the last version it recorded; any change
is appended to an append-only history immediately — timestamped, with a full
snapshot and the exact lines that moved — and the app asks for a written
reason, loudly, until one is given. Reasons are write-once. Open positions
record the profile and version they were opened under. Without this you can
rewrite the rules to justify holding a loser and never notice you did it.

## Layout

```
app.py                    pywebview window + the JS-facing API
config/metric-bank.yaml   what every value IS — no thresholds live here
config/concept-map.yaml   how bank inputs resolve onto XBRL concepts — the
                          tag-selection judgement, as reviewable data
engine/                   no UI imports live here
  profiles.py             loads the bank, resolves profiles against it
  evaluate.py             the verdict: buy tiers, sell watch, clock, flags
  profile_history.py      append-only version history for hand-edited profiles
  migrate.py              one-time move from the retired metric set to the bank
  expected_value.py       the three EV calculators
  portfolio.py            snapshots, override log, scorecards
  store.py                JSON persistence, atomic writes
  backup.py               export / import
  gateway.py              the edgartools boundary — nothing else imports it
  facts_store.py          raw filing facts, append-only, keyed by CIK
  price_store.py          as-traded prices + adjustment events, never adjusted
  tiingo.py               the price source client
  tickermap.py            SEC ticker→CIK snapshots, diffed for renames/reuse
  concept_map.py          resolves bank inputs from one filing's facts
  periods.py              fiscal years, TTM, basis-consistent windows
  compute.py              every computed bank entry, from raw facts on the fly
  crosscheck.py           price × shares vs public float
  fetch.py                the explicit-action fetch orchestrator
  dataview.py             computed values joined under hand-entered ones
ui/                       index.html, app.css, app.js
data.template/            what gets copied on first run, incl. profiles/
tests/fixtures/           hand-read ground truth + recorded extractions
tools/make_sample.py      regenerates the sample set
```

The engine is plain Python over plain dicts and imports nothing from the UI, so
the screening funnel can `from engine import evaluate` rather than
reimplementing the scoring.

## Adding a metric

Add an entry to `config/metric-bank.yaml` — id, label, unit, format,
derivation and the plain-language explanation are all required; a bare number
with no explanation is incomplete, not a follow-up ticket. The UI renders
whatever the bank and the profiles hand it; there is no view code to change.

A bank entry does nothing until a profile references it with a threshold.
That is the intended behaviour: a new metric shouldn't silently start scoring
positions you opened before it existed, and the level it should sit at is a
strategy decision that belongs in the profile, with a written reason.

## Data providers

Nothing touches the network yet. Metrics are entered by hand.

`engine/providers/base.py` defines the interface. For fundamentals, use SEC
EDGAR's XBRL `companyfacts` API: free, no key, and authoritative. It only
reaches back to roughly 2009–2011, when the mandate phased in, so a 15-year
history sits right at the edge of what's actually available. For prices,
yfinance is fine. It is an unofficial scrape and will break periodically, which
is why fundamentals should never depend on it.

A provider must **omit** metrics it has no value for rather than returning
zero. Absent renders grey; a zero renders as a confident failure.

## Packaging to an EXE

```
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Ledger ^
  --add-data "ui;ui" --add-data "data.template;data.template" app.py
```

Use `:` instead of `;` in `--add-data` on macOS and Linux.

Prefer one-folder over `--onefile`. One-file builds unpack to a temp directory
at every launch, which Defender and SmartScreen flag constantly on unsigned
binaries. One-folder trips it far less and starts faster.

On Windows, pywebview renders through the Edge WebView2 runtime that ships with
Windows 10 and 11, so the build stays around 20 MB rather than the 80–120 MB a
bundled Qt would cost.

## What isn't built yet

- **Risk and position sizing.** No concentration limits, no sizing rules, no
  sector exposure. For value investing the risk that matters is permanent
  capital impairment rather than volatility, so this should be balance-sheet
  and concentration shaped, not beta and Sharpe.
- **History charts.** `history` exists on every security and nothing fills it.
- **The screening funnel.** Deliberately later. This is the journal first.

## License

MIT. See [LICENSE](LICENSE).

This is a tool for recording and reviewing your own reasoning. It is not
investment advice, and the sample data uses invented companies.
