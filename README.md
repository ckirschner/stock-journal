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

In strict order, and nothing overrides it:

1. Any **knockout** failure → red. Full stop.
2. Any **required** failure → red.
3. Six or more metrics missing → grey. Absent data is never a pass.
4. Otherwise the **optional score** decides: green at or above your threshold,
   amber below it.

A metric within 10% of its threshold reads *watch*: still passing, but close
enough that you want to know before it breaks.

Buy rules and sell rules are not the same thing. A holding that stops passing
the entry screen gets *Trim* or *Review*, not an automatic exit; only a
knockout produces *Exit*. Selling every time a ratio ticks is how you churn out
of good businesses on a bad quarter.

## The parts worth knowing about

### Entry snapshots are frozen

When you record a purchase, every metric value, its state and the ruleset
version are written once and never recomputed. If they were recomputed,
restated filings and amended rules would quietly rewrite history, and the
journal would lose the only thing that makes it a journal. The detail page
shows entry → now for every metric, so you read the thesis holding or decaying
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

### Rulesets are versioned in the app

Changing a threshold or a weight creates a new version with a timestamp and a
written reason. Open positions stay bound to the version they were opened
under. Without this you can rewrite the rules to justify holding a loser and
never notice you did it.

## Layout

```
app.py                    pywebview window + the JS-facing API
engine/                   no UI imports live here
  schema.py               metric definitions, the only place to add one
  rules.py                rulesets and version history
  evaluate.py             the verdict
  expected_value.py       the three EV calculators
  portfolio.py            snapshots, override log, scorecards
  store.py                JSON persistence, atomic writes
  backup.py               export / import
  providers/base.py       data provider interface (not yet implemented)
ui/                       index.html, app.css, app.js
data.template/            what gets copied on first run
tools/make_sample.py      regenerates the sample set
```

The engine is plain Python over plain dicts and imports nothing from the UI, so
the screening funnel can `from engine import evaluate` rather than
reimplementing the scoring.

## Adding a metric

Add an entry to `DEFAULT_SCHEMA` in `engine/schema.py`. The UI renders whatever
the schema hands it: inputs, thresholds, tooltip, rules row, detail row. There
is no view code to change.

Existing rulesets won't have a rule for the new metric until you amend them on
the Rules tab, which is the intended behaviour: a new metric shouldn't silently
start scoring positions you opened before it existed.

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
