# Ledger

An investment journal. You commit to a strategy in advance; the tool tells
you what that strategy says about a security today, and records what you
actually did.

It never places a trade and holds no broker credentials.

## Run it

```
pip install -r requirements.txt
python app.py
```

On first run there are no journals. Create one, choose the strategy it will
be judged by, and add a security.

```
python app.py --reset     delete every journal and start empty
python app.py --debug     open the web inspector
```

## One journal, one strategy

A journal is created against one strategy and stays there. Trading two
strategies means two journals, the way it would mean two accounts.

That is not a limitation to be worked around. Choosing a strategy per
security, or per trade, is picking the rule that endorses what you already
wanted, and it makes the arithmetic incoherent — a sell rule cannot mean
anything if the strategy that wrote it can be swapped out at the moment it
fires.

Each journal owns its own lots, notes, snapshots, valuation assumptions and
the answers its strategy asked for. Fetched filings and prices are shared by
every journal, because they are public facts about a company rather than part
of anyone's record. Your free cash and everything derived from it stay inside
the journal, which lives outside this repository and is only ever copied out
by an export you ask for.

## How a verdict works

The host fetches, computes and presents. A strategy consumes what the host
computed and returns **one state** — buying, holding, adding, trimming and
exiting are outcomes of a single decision, not separate systems that each
reach their own conclusion.

Every state a strategy declares maps onto one of six render types the host
owns, which is how the host can sort, count and present a verdict whose
meaning it does not know:

| render    | means                                              |
|-----------|----------------------------------------------------|
| `commit`  | capital may go in — carries how much               |
| `reduce`  | partial exit — carries the level to reduce to      |
| `close`   | full exit — carries the date it is due             |
| `hold`    | no action                                          |
| `blocked` | a decision is owed from you before any verdict     |
| `unknown` | not enough data to say                             |

The last two are about the evaluation, not the security, and are never
averaged in with the others: "4 of 12 are hold" is a portfolio fact, "4 of 12
cannot be evaluated" is a data problem.

A verdict arrives with the reasoning attached. The strategy says what it
looked at and what it required; the **host** answers with the figure, its
label and unit, whether it was absent and why, and how the comparison came
out. So a strategy can never misquote the host's own numbers — it never
quotes them at all — and can never claim a pass on a value that was absent.

That extends to the limits themselves. A rule's limit is either a number the
strategy states outright or the name of one of its own settings, never both:
where it names the setting, the host reads the number out of your journal.
"At most your position cap" beside a figure that is not your position cap is
not a sentence this program can produce, and it matters because the
scorecard that asks whether overriding a rule keeps working out groups by
exactly that attribution.

A limit can be missing too. An answer you have not given sets no limit, and a
test with no limit reads as *not run* — never as passed.

### The figures are gathered under headings, and a heading has a rule

Fifteen rows of evidence are fifteen rows. What a reader needs to know is
which of them were disqualifying, and a flat list cannot say that. So a
strategy gathers its citations under headings, and each heading says what it
demands of the rows beneath it: **all** of them, **at least** so many of
them, or nothing at all.

The count under a heading is the host's, taken from the same rows you are
looking at. A strategy cannot tally "six of eight core tests passed"
separately from the eight rows underneath and have the two disagree, because
it does not tally it at all. Where a heading demands a number, that number is
read out of one of the strategy's own settings the way every other limit is.

A row nobody could read counts as neither a pass nor a failure there, exactly
as it does on its own. Five passed, one failed and two unreadable against a
bar of six is not a failure — it could still get there — so the heading reads
as undecided and says how many are missing.

### A verdict cannot contradict its own evidence

A strategy has to choose a state before any of its evidence is resolved,
which used to mean every strategy compared the figures twice: once privately
to decide, and once through the host to display. Nothing checked that the two
agreed, and when they did not, a verdict to buy rendered beside a row saying
the test had failed, with nothing on screen saying which was wrong.

Both halves of that are closed. A strategy now asks the host how a comparison
came out and cites the same question it asked, so there is one answer rather
than two. And where a strategy puts capital in anyway — beside a row the host
resolved as failed, or against a heading whose requirement was not met — the
verdict is **refused**, and the reason says which heading and by how much.

Refused, not shown with a warning. A screen carrying a buy and a red row
leaves you to arbitrate, which is the judgement call this tool exists to have
already made.

The check is narrow on purpose. A hold may cite failures — that is often why
it is a hold — and an exit rests on them by definition. It is `commit` alone
that says capital may go in.

## What a journal tells its strategy

Two kinds of thing, and the difference is where the default comes from.

**Settings** are numbers the strategy has an opinion about and ships a default
for — a position cap, a required return. **Answers** are facts about your
account that no strategy could guess: how much free cash you have, how you
are trading right now. The test is whether the strategy can ship a sensible
default. It has a view about a 5% position cap; it can have none about your
balance.

A strategy declares the answers it needs, and the setup screen is generated
from that declaration. A journal only ever asks for the fields its own
strategy uses; there is no list of known settings anywhere in the interface.
A declared field can be a number, a fixed set of choices, or a question that
only appears once another one is answered a particular way, and it can be
bounded by another field — "the cash you keep back" can never exceed the cash
you have.

A question can apply under any of several answers — "the cash you keep back"
means something whether you are building or trimming and nothing at all while
you are paused.

**Both are editable after the journal is created**, on one screen, and both
are recorded. Changing a setting changes what the strategy demands, so it
goes on the rule-change record and asks you to write down why. Changing an
answer updates a fact, so it goes on its own dated record and asks for
nothing — your cash balance moving is not a rule being retuned.

### Your judgement, per security

Some of what decides an investment is not in the filings: whether a moat
holds for another decade, whether management told the truth when the news was
bad, where the spare cash went and whether it was worth it. Those are
questions the metric bank asks and **you** answer, on the security's own page,
in prose with a pass or a fail.

The question lives beside its definition, so everything you need in order to
answer one — what it means, what a good answer looks for, where it misfires,
whose idea it was — is on the page you answer it on. A strategy reads one
exactly as it reads any other measure. You are only asked the questions your
strategy actually reads for that security, and the journal records what you
say as **your assessment**, never as something it worked out.

The record is append-only and dated. Changing your mind adds an entry above
the old one and both stay readable — which also means a purchase backdated to
2024 sees the answer that was on record in 2024, and an assessment written
before the holding you have now says so rather than passing itself off as
current. Leaving a question unanswered is not a fail; the strategy is told it
has no answer, and absence never reads as a pass.

### The account, and why it is derived

An answer can carry a **role**: a name from the host's own short list saying
what the figure is. Free cash is the only one. Once a journal has it, the
host reports free cash, the account value and every position's weight; until
then those read absent, with the reason naming the question nobody asked.

The account value is *not* something you type. It is free cash plus the
market value of every holding, because that is a figure the tool can reach —
and a number you typed would let two answers disagree with nothing to say
which was wrong. One unpriced holding makes the whole total absent rather
than understating it, since a missing price treated as zero would quietly
inflate every weight measured against it.

The host reports the figure and stops there. Whether a weight is too high is
a strategy's opinion, and appears nowhere in the host.

### A share class is a security; the company is not

Two classes of one company are two instruments at two prices, and the tool
keeps the two scopes apart because collapsing them produces figures that are
plausible in shape and badly wrong in value.

**A holding is priced from its own symbol, and only that one.** Market value,
weight, the account total and every return read the close of the security you
actually hold. Where that security has no close stored, the value is absent
and says so — a sibling class's price is a real price for a different thing,
so it is never borrowed. Twenty shares of a Class B security priced at the
Class A close read $14,100,000 instead of $9,400, and nothing on the screen
would have said which one you were looking at.

**A whole-company measure reads every class**, because the company is the
subject: market capitalization is each class's share count at its own price.
Where a class has no price of its own — a founder class that never listed is
the ordinary case — it is valued at the largest class that does have one, and
the caution says so, names the symbol borrowed from, and states what share of
the company was valued that way. That is the only approximation in the
compute layer, and it is labelled an assumption rather than a measurement.

## Writing a strategy

A strategy is a directory under `strategies/`:

```
strategies/<name>/
  strategy.py     STRATEGY (what it declares) and decide(ctx) (what it does)
  values.yaml     shipped defaults for its declared values, with a version
  <reference>     any static data it ships — loaded by the host, never by it
```

Strategies are discovered, not registered: adding one means adding a
directory. One that fails to load is skipped with a legible reason and does
not prevent the others from loading.

A strategy declares its identity, the host contract version it speaks, the
version of its logic, the version of its values, the settings it ships and
the answers it needs from you. It receives one plain dict and returns one
plain dict. It never fetches, never reaches the stores, never opens a file,
and never invents vocabulary — an undeclared state, an unknown payload key,
a render type or an input role of its own devising is an error in place.
Anything it needs that the host does not offer is a request against the
host, not something to work around.

What it receives is **frozen**. Reads work exactly as they do on a plain
dict; writes cannot happen at all. That is what makes "the host owns the
answer" true rather than merely intended — a figure a strategy could edit is
a figure it could quote back differently from the one on the screen.

Every setting a strategy ships says **where its number came from** and
whether the explanation beside it is that source's reasoning or the author's
own. Nothing can verify that a level really is a particular book's; what this
refuses is the three ways the claim goes wrong on its own — being absent,
being made once for a whole file, and being silent about how far it reaches.
A level with borrowed authority and homemade reasoning is the case worth
being able to tell apart, and prose loses it first.

`engine/contract.py` is the full specification and is written to be read.

**`strategies/graham/` is the first real one.** It buys a statistical
discount on a business it forms no opinion about, and sells when the discount
closes, when the balance sheet stops being safe, or when two years are up. It
declares eleven states, twenty-eight settings and one answer it needs from
you, and every threshold in it carries what it means, why that number and
where it misfires.

**`strategies/proof/` is a scaffold, not a strategy.** It proves the boundary
carries data both ways against real stored filings: it reads one measure,
always holds, and holds no view about any security.

### Seeing it work without any of your own data

**Data → Load sample journal** creates a separate journal of ten invented
companies with history already on them — a holding with nothing to do, one
that crossed a sell line and is waiting for a second filing before anything
happens, one whose balance sheet came apart, one the two-year clock has run
out on, one that grew too large a share of the account, a purchase made
against the signal and one made without one. Its own journal, because a
journal has one strategy and the sample is written against Graham.

Every company and figure in it is invented. It is built by
`tools/make_sample.py`, which drives this same API and refuses to write the
file if any security stops telling the story its notes claim.

### Changing what a strategy demands

Any change to what a strategy demands is detected and recorded on every
journal it governs, whether it came through this app or from editing a file
directly — rules that can be quietly retuned are not rules, and the retuning
always happens at the moment it is most tempting.

What the record can *say* depends on what changed. A declared value is
recorded as a before and after, because the number means something on its
own, and you are asked to write down why. A change to logic cannot be, so the
record carries the author's own changelog line — which is why the host
refuses a version that does not say what changed.

A journal's stamp holds the resolved values themselves, not only their
version number, so a threshold edited in place with the version left alone is
caught anyway. That case is reported as the louder one it is.

## The parts worth knowing about

### A position is its lots, and nothing else

A position is not a running total that gets updated. It is a list of **lots**
— one entry per purchase and one per sale, appended in the order they were
recorded and never edited afterwards. How many shares you hold, what the
average cost was, what each lot returned, and whether a security is a
holding, a previous holding or a candidate are all derived from that list
every time they are read.

That is append-only applied one level down: a sale that reduced the purchase
it drew from would be rewriting what was bought. Instead a sale names how
many shares it took from each lot, oldest first by default, and the lot it
drew on stays exactly as recorded. So several buys, a partial sale that
leaves the rest untouched, and buying back in after a full exit are all the
same operation — one more entry.

A sale of shares the journal never saw is refused, with the message naming
the fix. That is arithmetic, not a gate: nothing here asks whether selling
was wise, but shares that were never recorded as bought cannot be recorded as
sold without every figure derived below becoming fiction. Both bounds are
checked — what is left of the lots, and what was held on the sale's own date
— because a name bought back last year would otherwise accept an exit
backfilled into a period when far less was held.

### A security is held more than once, and each time is its own trade

Buy, close, buy again: that is two **holding periods**, and the split matters
because most questions are about one of them rather than about the ticker.
What the position in front of you has returned, what a round trip made, how
long you have held it and what a holding cost are all per period. Periods are
derived by walking the lots — a period opens at the purchase that takes the
position up from nothing and closes at the sale that returns it to nothing —
so a purchase entered later but dated before the exit correctly means the
position never closed at all, which no marker written at exit time could have
known.

**When a holding began is the period's first purchase, and a trim does not
move it.** How long you have held something and how old the oldest share you
still hold is are two questions, and they part company the day the oldest lot
is sold down to nothing. They serve different rules — a multi-year holding
discipline is about the position, a tax boundary is about a lot — so they get
different answers rather than one name. Lot ages live on the lot list, each
entry carrying its own date.

Two figures deliberately are not per period. **Overrides are counted per
purchase**, because one buy in a name can be compliant and the next an
override. **Exits are grouped per sale**, because the reason is given at the
sale, and a position trimmed on a risk limit and closed on a broken thesis
gave two different answers.

**Return since exit stops when you buy again.** A closed position keeps being
priced, because watching what happens next is the only way to find out
whether a sell rule works — but once you own the name again, the move from
there is yours. Carrying the window on to today would credit the sell rule
with a stretch you spent holding, and a rule given credit for your own later
buy cannot be judged at all. Buying back after an exit and adding after a
trim end the window for the same reason, so nothing calls it "buying it
back" — the second one never closed the position. A window that ends at a
purchase ends at the price you actually paid, so it needs no fetch and is
exact; every figure says which window it rests on, and a sale or a purchase
recorded at nothing produces a stated absence rather than a confident −100%.

**Cost basis is reporting only, structurally.** It is on every screen and in
the scorecards, and it is not in what a strategy receives at all. A rule that
fires on the distance from your own purchase price is anchoring — it makes
the same company a buy for one person and a sell for another on the same day,
and averaging down is that bias in its purest form. Market value and weight
survive because they are price × shares, which is a fact about today.

### Entry snapshots are frozen

When you record a purchase, the whole decision is written once and never
recomputed: the state, the payload, the rule that produced it, and every
figure it cited with what was required and how the comparison came out. If it
were recomputed, restated filings and a retuned strategy would quietly
rewrite history, and the journal would lose the only thing that makes it a
journal. Each lot carries its own, so the detail page shows what was on
screen at every entry beside today's verdict — you read the thesis holding or
decaying rather than just a colour.

### Buying against the signal is recorded, not blocked

The tool can't stop you and shouldn't try. It captures the state, the rule
behind it, which cited figures came out against, and your written reason for
going ahead.

Two kinds of override are kept apart, because they are different decisions:
going ahead **against** a verdict, and going ahead **without** one where the
strategy could not reach a verdict at all. Averaging them would make a gap in
the data look like defiance.

The per-rule breakdown is the part that earns its keep. If overriding one
particular limit keeps working out, that limit is miscalibrated, not you.

### Exits are grouped by reason

Closed positions keep getting priced. If *Panic* keeps showing a strong
return *after* you sold, that is a finding you would never get from a tool
that drops the ticker the day you exit.

### Your thesis, and what would prove you wrong

Everything else in the journal is measured against it. An override is
overriding *the thesis*; an exit is the thesis breaking or paying off; the
falsifier is the one part written to be checked.

So it is not a field you edit. It is a living document with amendments,
appended and dated, and the version standing on a day is the newest written
by then. **Amending it asks why it changed** — a first statement does not,
because there is nothing to explain the first time you write down what you
believe, and everything to explain every time after. A falsifier quietly
rewritten the week before it was about to fire is the most diagnostic event
a journal can hold, and the only way to hold it is to make the rewrite an
entry rather than an overwrite.

The thesis belongs to the **position**: one document per security, carried
across purchases, and each purchase freezes the version that was standing
when it was made. A sale freezes it too, because that is where it gets
graded. Buying a name back after selling it does not renew a thesis written
about the last time you owned it — that version still shows, and it says so.

### Expected value is computed, never typed

There is no target price field anywhere. You enter assumptions and the number
is solved for, so when the estimate turns out wrong you can see *which
assumption* was wrong.

Reverse DCF is the default. It solves for the growth rate today's price
already requires, which is a far easier question to answer honestly than
"what is this worth?". Scenario weighting takes bear, base and bull with
probabilities that must total 100%, and makes you enter the bear case first.
Owner earnings capitalises normalised cash flow at your discount rate, then
takes a required discount off the result.

A valuation belongs to the **purchase**, not to the position. What you
thought it was worth at $40 is not amended by what you think at $61 — they
are two claims about two decisions, so both are kept, the purchase freezes
the one it was made on, and nothing anywhere averages them. Claims that
talked you *out* of buying stay on the record too; they are the most
instructive entries in it.

### Fetched data never outranks you

**Fetch data** on a security pulls the company's full filing history from SEC
EDGAR (raw reported figures, per filing, stored exactly as tagged) and its
daily price history from Tiingo (as-traded closes plus split/dividend events
— never a pre-adjusted series, because sources rewrite adjusted history
retroactively). Every measure the bank can compute from that is computed on
the fly; nothing derived is ever saved, and a hand-entered value always wins
over a computed one, visibly.

A measure that cannot be computed is absent with the reason, in place: source
doesn't carry it, the mapping is ambiguous, a restatement makes the window
mix accounting bases, or the data simply hasn't been fetched. Absence is
never zero. Multi-year windows refuse to mix accounting bases by construction
— a five-year CAGR spliced across a restatement is arithmetic on two
different definitions, so it reports why it can't compute instead.

Fetching happens only when you press the button. The SEC requires every
automated tool to identify itself (name + monitored email — set it on the
Data tab); prices need your own free Tiingo key. Each 10-K's price × shares
is cross-checked against the company's own reported public float, which
catches adjusted-price, split-basis, currency and share-class errors in one
comparison.

### A purchase is judged by the data of its date

Record a purchase with a past date and the verdict is rebuilt from what was
observable then — filings filed by that day, that day's close — and is
labelled a reconstruction everywhere it appears.

Hand-entered values obey the same clock. Each one is dated when you enter it,
so a purchase backdated to 2024 reads the figure that was on record in 2024,
or nothing — and the record says which values it withheld as well as which it
used. A figure typed today may have been typed *because* of what happened
since, and serving it to a verdict rebuilt for an earlier day would let
hindsight into a reconstruction. Changing a value adds an entry above the old
one; clearing one is an entry too, not a deletion, so the number you no
longer stand behind stays readable and the computed figure underneath becomes
visible again.

Every value you supply now travels this path — a judgement, a thesis, a
valuation, a typed figure. None of them can be edited, none can be deleted,
and none can be given a date by the thing writing it: there is no parameter
to backdate an entry with, which is what makes "what did I know then" a
question the journal can answer honestly.

## Where your data lives

Never in the project folder.

| OS      | Location                                  |
|---------|-------------------------------------------|
| Windows | `%APPDATA%\Ledger`                        |
| macOS   | `~/Library/Application Support/Ledger`    |
| Linux   | `~/.local/share/Ledger`                   |

Set `LEDGER_DATA` to move it, onto a synced drive for instance.

```
journals/<id>/journal.json   one journal, whole, written atomically
local/                       the API key and the SEC contact — never exported
facts/ prices/ cache/        fetched public data, shared by every journal
```

Cloning or pushing this repository can never carry your journals with it:
`.gitignore` excludes every data path and nothing personal is written under
the project root at runtime. Back up with **Data → Export**, which writes one
timestamped JSON file containing every journal. Your API key and SEC contact
are not in it and cannot be — the exportable set is the journals directory,
and neither of them lives there.

## Layout

```
app.py                    pywebview window + the JS-facing API
config/metric-bank.yaml   what every measure IS — no thresholds live here
config/concept-map.yaml   how bank inputs resolve onto XBRL concepts — the
                          tag-selection judgement, as reviewable data
strategies/               one directory per strategy; discovered, not listed
  graham/                 the first real one: strategy.py and values.yaml
  proof/                  the contract scaffold; holds no view about anything
data.template/sample.json the demonstration journal — invented companies
tools/make_sample.py      builds it by driving the real API, and refuses to
                          write it if a story stops being true
engine/                   no UI imports live here
  contract.py             the host/strategy boundary: what a strategy
                          declares, receives and must return
  context.py              what a strategy receives, built per security
  strategy_loader.py      discovery, loading, and refusing a bad bundle
  strategy_values.py      the declared-values resolution chain
  journals.py             the journal collection, the rule-change record and
                          the record of answers you changed
  bank.py                 the metric bank
  dated.py                append, date, never edit — the one mechanic under
                          every record below
  judgements.py           the per-security questions no filing answers
  thesis.py               why you own it and what would prove you wrong;
                          belongs to the position, amended with a reason
  valuation.py            what you thought it was worth; belongs to the
                          purchase, and never averages into anything
  hand_entered.py         numbers you read off a document this program
                          could not; clearing one is an entry, not a delete
  portfolio.py            lot history, snapshots, the override log,
                          scorecards
  store.py                data paths and the two atomic primitives
  backup.py               export / import
  expected_value.py       the three EV calculators
  gateway.py              the edgartools boundary — nothing else imports it
  facts_store.py          raw filing facts, append-only, keyed by CIK
  price_store.py          as-traded prices + adjustment events, never adjusted
  tiingo.py               the price source client
  tickermap.py            SEC ticker→CIK snapshots, diffed for renames/reuse
  concept_map.py          resolves bank inputs from one filing's facts
  periods.py              fiscal years, TTM, basis-consistent windows
  compute.py              every computed bank measure, from raw facts
  crosscheck.py           price × shares vs public float
  fetch.py                the explicit-action fetch orchestrator
  dataview.py             computed values joined under hand-entered ones,
                          on the same clock a strategy reads them by
  secrets.py              the credential store and machine-local settings
ui/                       index.html, app.css, app.js
tests/fixtures/           hand-read ground truth + recorded extractions
dev_reference_docs/legacy-profiles/
                          the retired rulesets, kept as source material for
                          authoring strategies. Nothing reads them.
```

The engine is plain Python over plain dicts and imports nothing from the UI,
so the screening funnel can consume the same contract rather than
reimplementing scoring.

## Adding a measure

Add an entry to `config/metric-bank.yaml` — id, label, unit, format,
derivation and the plain-language explanation are all required; a bare number
with no explanation is incomplete, not a follow-up ticket. The UI renders
whatever the bank and the strategy hand it; there is no view code to change.

A `qualitative` entry is one you answer rather than one the host computes: it
carries the question instead of a derivation, and adding one adds it to the
security pages of every journal whose strategy reads it — again with no view
code to change.

A bank entry does nothing until a strategy reads it. That is intended: a new
measure shouldn't silently start scoring positions you opened before it
existed, and the level it should sit at is a strategy's decision.

## Tests

```
python -m pytest
```

The suite pins the behaviours that would fail *silently* — history
immutability, evaluation correctness, absence handling, atomic persistence,
and the rule-change record. A guarantee asserted in prose decays; one with a
failing test does not.

One test renders every screen under Node with a stub DOM
(`tests/test_view_smoke.py`); it is skipped where Node is not installed.

**Two ground-truth sweeps hold the arithmetic to figures no code produced.**
`tests/fixtures/groundtruth/` holds statement lines read by hand off primary
filings on EDGAR, cited by URL and accession, and
`tests/fixtures/positions/histories.json` holds position histories stated in
plain terms with every expected figure worked out on paper and the arithmetic
written beside it. Both exist for the same reason: deriving an expectation
through the machinery under test proves only that it agrees with itself.

Several of the position histories also record the *wrong* answer — the figure
the code produced with the defect that history was built for present — so a
passing run is evidence the defect is gone rather than evidence of a rounding
preference.

## Packaging to an EXE

```
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Ledger ^
  --add-data "ui;ui" --add-data "config;config" --add-data "strategies;strategies" ^
  --add-data "data.template;data.template" app.py
```

Use `:` instead of `;` in `--add-data` on macOS and Linux.

Prefer one-folder over `--onefile`. One-file builds unpack to a temp directory
at every launch, which Defender and SmartScreen flag constantly on unsigned
binaries. One-folder trips it far less and starts faster.

On Windows, pywebview renders through the Edge WebView2 runtime that ships
with Windows 10 and 11, so the build stays around 20 MB rather than the
80–120 MB a bundled Qt would cost.

## What isn't built yet

- **Three of the four strategies.** Graham ships; Buffett, Lynch and Discount
  Closure do not. The rulesets in `dev_reference_docs/legacy-profiles/` are
  the input to writing them.
- **A risk-free rate.** One strategy test — the earnings yield against what a
  government bond pays — needs a number that is in no filing and is not price
  data, and nothing here can be told it. The measure reads absent, which is
  honest, and the test never passes.
- **Adding to a position, in the interface.** The lot record and the engine
  serve several buys and partial sales against named lots, but the screens
  offer no way to add to a position that is already open — that carries the
  whole sizing and pre-commitment design. Buying back into a name you closed
  is offered, and is a separate question.
- **Choosing which lots a sale draws on.** The record holds whichever
  allocation it is given; the screens always propose oldest-first.
- **An allocation view.** Weights are computed and cited, and nothing yet
  puts them side by side.
- **History charts.** Per-filing history exists, so there is something to
  chart.
- **The screening funnel.** Deliberately later. This is the journal first.

## License

MIT. See [LICENSE](LICENSE).

This is a tool for recording and reviewing your own reasoning. It is not
investment advice, and demonstration content uses invented companies.
