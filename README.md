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

Every state a strategy declares maps onto one of the render types the host
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
| `inapplicable` | these rules do not evaluate this kind of company |

The last three are not about the security, and are never averaged in with the
others — or with each other. "4 of 12 are hold" is a portfolio fact, "4 of 12
cannot be evaluated" is a data problem, and "4 of 12 are outside these rules"
is a fact about the journal you chose.

A strategy also declares the **kinds of company it will not evaluate**, and
the host answers for those before any of its logic runs. That is not a view
about whether banks are worth owning; it is the narrower statement that the
measures here were built for a company that sells something, and that a
lender, an insurer and a property company each break them in a different way.
A bank's cash from operations moves with the period's change in loans and
deposits, so a *shrinking* bank generates enormous free cash flow — the one
place a financial company produced a confident wrong answer rather than an
honest absence. Which kind of company a filer is comes from the industry code
the SEC publishes for it, code by code against the published list, and where
that code covers businesses that are nothing alike the classification is
absent rather than guessed.

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

**Your answers are dated too.** Every change to one is on the journal's own
append-only record, so an entry judged for a past day reads the answer that
was standing then. Before the journal existed there is no answer, and the
absence is served as itself: free cash absent, so the account absent, so
every weight absent, so a rule that binds on one says it cannot be worked
out and names why. This used to serve today's balance with a caution beside
it, which is the same failure one step removed — a qualified wrong number
still decides, and a purchase made two years ago was being sized against
today's account.

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

**`docs/WRITING-A-STRATEGY.md` is the reference**: what a bundle declares,
what `decide` receives, what it must return, how evidence and groups work,
which of the three version numbers moves when, what happens when a bundle
fails to load or throws, and the things that cost the most time to get right.
Its tables are generated from the host's own — a documented list that has
gone stale is a failing test rather than a paragraph nobody re-reads.
`engine/contract.py` is the specification itself and is written to be read.

**`docs/example-strategy/` is a complete worked bundle** and the fastest way
in: a two-tier rollup, one exit that does not act on a single bad reading, and
one question no filing answers with a state that blocks until it is answered.
It is deliberately not under `strategies/`, so the app never offers it and no
journal can be created against its invented thresholds — copy the directory
in to watch it run, and take it out again. It is loaded and exercised by the
test suite from where it sits, so it cannot rot.

A citation can also ask **how far a measure has moved since one of your own
purchases**, rather than what it is now. The strategy names the measure, the
anchor — the first purchase into this holding, or the last — the direction
and its own tolerance; the host finds both readings, takes one from the
other, and answers with the change, its unit and whether the tolerance was
met. The strategy could have done that subtraction itself. What it could not
do is *cite* the answer, because a limit is a number stated outright or the
id of a setting, and "five points below what it was when you bought" is
neither — so the drift figure would have been one the strategy asserted and
nobody could check.

A commit can carry a **staged plan**: the tranches it is holding back and, in
plain language, what releases each. The host never evaluates a condition. The
strategy re-runs every time, so a held-back tranche is bought only when that
day's evaluation offers it as the size in front of you — which is strictly
better than a schedule executing itself six months after the last time
anybody looked at the company. A plan anchored to your own purchase price is
not merely unsupported but unwritable: nothing about what a position cost is
in what a strategy receives.

**`strategies/graham/` is the first real one.** It buys a statistical
discount on a business it forms no opinion about, adds to what it holds while
that stays true and there is room, and sells when the discount closes, when
the balance sheet stops being safe, or when two years are up. It declares
thirteen states, thirty-four settings and one answer it needs from you, and
every threshold in it carries what it means, why that number and where it
misfires.

**`strategies/buffett/` is the second.** It buys a business good enough to
be worth owning for decades, at a price that leaves something on the table,
and sells only when the business breaks — never when the price gets high and
never because time has passed. It declares twelve states and twenty-seven
settings, and two things about the shape of it are the point rather than
gaps. There is no state that trims, so a holding that compounds to half the
account is left alone. And three of the things it reads are not measurements
at all: whether the moat holds, whether management can be taken at their
word, and what has been done with spare cash are questions you answer
yourself, in writing, and an unanswered one blocks a purchase rather than
being read as agreement.

### Seeing it work without any of your own data

**Data → Load sample journals** creates one journal of invented companies
per strategy, with history already on them — a holding with nothing to do,
one that crossed a sell line and is waiting for a second filing before
anything happens, one whose balance sheet came apart, one the two-year clock
has run out on, one that grew to half the account and is deliberately left
alone, a business that quietly stopped being worth owning, a verdict that
refuses to decide until you have answered something, a purchase made against
the signal and one made without one.

They are separate journals because a journal has exactly one strategy and it
does not change. Loading them together is the fastest way to see what that
costs and what it buys: a cheap, ordinary company is a candidate in one and a
refusal in the other, a good business at a full price is the reverse, and
neither journal is wrong.

Every company and figure in them is invented. They are built by the scripts
in `tools/`, which drive this same API and refuse to write a file if any
security stops telling the story its notes claim.

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

### Adding to a position, and where that decision is made

A position is revisited as often as it needs to be, and adding to one is a
decision like any other: its own lot, its own frozen snapshot, its own record
of whether it went with the signal or against it.

What is deliberate is **where** it happens. The security's own page says
whether a holding is eligible to receive capital. It does not say how much,
and it has no button to add. That costs a click, and the click is the point:
nobody opens a holding's page at random, they open it because it is down, and
a verdict sitting there saying "yes, more, this much" is the tool lending its
authority to averaging down at the moment somebody is looking for permission.

How much, and which one, is a portfolio question, and it is answered on
**Where capital goes** — a screen you have to visit on purpose. It lists
every position your strategy will put money into, ordered by how far each is
from where that strategy wants it, so the thing you already hold too much of
is never what the screen suggests. The ordering is arithmetic over what the
strategies said, converted against the same account value every other screen
is measured against; nothing there ranks one business above another.

Nothing on either screen can see what you paid. That is not a rule anybody
has to remember — cost basis is not in what a strategy is handed, so a rule
that added because the price had fallen below your purchase price cannot be
written at all.

Buying something your strategy said no to is still allowed, still recorded as
an override with the reason you give, and reachable from the same screen. In
a year that log is the most useful thing in the journal.

### Two baselines, and why one of them is not enough

A rule about a company you already own can ask something a rule about a
candidate cannot: has this changed since I last looked at it? There are two
honest answers to "since when", and a strategy can cite either.

**Since you last bought** is the last time you looked at this business and
said yes. A deterioration rule belongs here — anchored to the first purchase
instead, it fires an exit on a position you consciously re-underwrote last
quarter.

**Since you first bought** is the day the holding began, and it is the only
place the slow version is visible: six quarters of small declines, each one
acceptable against the quarter before it, adding up to something you would
never have bought. Graham uses it to demand a fresh read of the business
before any more money goes in. It sells nothing.

A weighted average of the two is wrong for both. There is no coherent
dollar-weighted average of a gross margin — averaging the readings at three
purchases produces a number that was true on no day and can be checked
against no filing.

Both figures come off **what the purchase froze**, never a recomputation of
that day. A company restating two years of accounts cannot move the level a
re-underwrite is measured against, because the question is what you were
shown when you said yes, not what today's filings say about the day you said
it. Where a purchase froze nothing, or froze nothing about that measure, the
comparison is absent with its reason — and absent never buys.

The subtraction is the host's. A strategy names the measure, the anchor, the
direction and its own tolerance; every number in the row is the journal's, so
a drift figure is one anybody can check rather than one the strategy asserted.

### Renaming and deleting a journal

A journal can be renamed. Only the name changes — the folder it lives in
never moves, which is why a journal renamed six times still opens, still
exports and still carries the same stamp. Nothing recorded is touched, so it
goes on no change record and owes no reason: a name is not a rule.

A journal can also be deleted, and it is the one destructive action in the
program. It takes every position, note, frozen decision and rule change with
it, nothing else holds a copy, and none of it comes back. So the dialog says
what goes, offers the export first, and asks you to type the journal's name —
checked on the backend, because a confirmation the browser could skip is not
a confirmation the record has.

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

**A holding closed in stages is described by all of it, not by its last
sale.** Sell 90 shares at $150 and the final 10 at $55 and the exit price is
$140.50 — share-weighted across every sale that closed the period — not $55,
which is what one sliver got. The date is still the last sale's, because that
is the day nothing was held. Every reason given is shown, each carrying the
share of the exit it accounts for: two answers were given and both are true,
and picking one loses which shares each was about.

**A return that cannot be worked out says why.** Every return is a figure or
an absence with a reason, never a bare dash. "Nobody has fetched a price for
this" and "the 2 February purchase is recorded at $0.00" are different facts
with different fixes — one is solved by fetching and the other never will be
— and the panel that judges your rules used to tell you to fetch for both.

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

**A third thing is not an override at all.** Enter a purchase you made in
2019 and the verdict is rebuilt for that day — but sometimes there is nothing
to rebuild it from: no filings had been filed, or the journal did not exist
yet and holds no answer for what your account was worth. That is not a signal
you went past. Nobody was standing in front of a screen, and the grey box is
a fact about how far back this program can see rather than about your
discipline. It is recorded as exactly that, counted in its own population,
and kept out of both comparisons — because the moment history can be entered,
counting those as overrides would fill the one figure that measures your
judgement with decisions nobody made, and the scorecard would report that
overriding works fine.

**And the comparison is reported twice.** Once for decisions you saw at the
time, once for decisions rebuilt afterwards, never added together. They are
not evidence about the same thing: the first is your judgement under a
verdict you were looking at, the second is this program's best attempt at a
day nobody lived through. Both are shown, at equal weight — dropping the
second would hide real evidence about the rules.

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
— a five-year growth rate spliced across a restatement is arithmetic on two
different definitions, so it reports why it can't compute instead.

**Growth rates average three fiscal years at each end**, five years centre to
centre, which is Graham's own construction. Between two single years, a rate
describes whatever one-off sat in either of them — and the damaging case is
not the company that fails high and is rejected but the one that lands
mid-band: a business compounding at 7% whose base year carried a charge reads
around 20%, passes every test, and nothing anywhere says so. The cost is eight
fiscal years of history on one basis rather than six, so some companies that
had a growth rate now have an absence instead. That is the right trade and it
is not a hidden one: the absence names what is missing.

**How much evidence it takes to act on a breach follows from how the measure
is read**, not from a setting. Two consecutive readings of a rolling five-year
median share four of five years — they are the same data looked at twice, and
the year that produced the breach does not leave the window by being looked at
again. So a median acts on the reading in front of you; a balance-sheet ratio,
which is one morning's photograph, still wants a second filing; and a measure
read across a window is asked instead whether its failure survives dropping
the single year that most favours the company. The metric bank states how each
measure is read, so an author of a new one cannot get it wrong.

Fetching happens only when you press the button. The SEC requires every
automated tool to identify itself (name + monitored email — set it on the
Data tab); prices need your own free Tiingo key. Each 10-K's price × shares
is cross-checked against the company's own reported public float, which
catches adjusted-price, split-basis, currency and share-class errors in one
comparison.

### An entry is judged by the data of its date

Record a purchase **or a sale** with a past date and the verdict is rebuilt
from what was observable then — filings filed by that day, that day's close —
and is labelled a reconstruction everywhere it appears.

The sale used to be judged with today's data, which put a verdict the
strategy was never asked for into the two facts the exit analytics teach
from: what the signal read at the exit, and whether a rule called for it. An
exit dated 2019 now reads the world of 2019 or says it could not, and the
thesis frozen beside it is the version that was standing that day rather than
one amended since.

### Entering a position you already own

**Enter history** on a security's page takes a run of dated entries —
purchases, adds, trims, an exit, a re-entry — and applies them oldest first,
each judged against the data of its own day and each checked against the
position the ones before it leave behind. Nothing is filled in for you: the
day, the shares and the price are the three facts only you have, and a number
this program guessed would enter a record that can never be corrected.

It checks before it records, and shows you what every row would produce —
including the rows nothing can be rebuilt for. If any row cannot be recorded,
none of them is: an append-only record has no way to take an entry back, so
"three landed and the fourth was refused" has to be a state that cannot be
reached rather than one to recover from.

A backfilled entry is marked wherever it appears — the list, the detail page,
the lot history, both scorecards — for as long as it exists. Reconstruction
is imperfect and that is acceptable; presenting one as a record made at the
time is not.

**A sale entered from history may honestly have no reason on it.** You were
not there, and forcing a pick from the list would manufacture the one fact
the exit analytics exist to read. "I do not remember" is an answer, and
counting how many of your old exits are unexplained is itself the finding.

### What you remember, marked as a memory

A purchase backdated to 2019 freezes no thesis, because you had not written
one — and it never gets the one you write today, which would be a case
composed with hindsight presented as the case that was made at the time.

So there is one hindsight surface and it is not the thesis. On a purchase
entered from history you can write down **what you remember thinking**. It is
kept under its own name, carrying the day it was actually written, and it is
rendered as what it is: written after the outcome was known, and gradeable
against nothing. It is refused outright on a purchase made today, where the
honest answer is to write a thesis on the record that keeps every version and
asks why each one changed. Nothing about it reaches a strategy, and no
judgement or valuation has an equivalent — a remembered assessment would be a
measurement invented backwards, and a strategy binds on those.

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

**The day an entry was written is your day, not the clock in Greenwich.**
Every date in the journal is one you typed or read — a purchase date, a sale
date, the day being reconstructed — so the day an entry was recorded on has
to be on the same calendar, or the two disagree for part of every day. They
did: a thesis written at seven in the evening in California was invisible to
a purchase dated that same evening, and a note written on a Tokyo morning
rendered as the day before. Records written before this carry the old stamp
and keep reporting exactly the day they always reported; nothing already
written is restated.

**A price says which day the market set it.** There is no rule here about
how old is too old, because that is a strategy's judgement and not the
program's — a screen built on three-year average earnings barely notices a
week-old close and a rule about position size notices a month. So the age is
always stated, on the price and on everything built from it: what the holding
is worth, its share of the account, the account total. A strategy that cares
declares its own limit and compares against the count the host reports. And
where a price series has *ended* — delisted, or the symbol reassigned — that
is a fact rather than a judgement about age, and it is said wherever the
price appears. The last close of a dead series is the last price it ever had,
not what it trades at.

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
  graham/                 buys a statistical discount: strategy.py, values.yaml
  buffett/                buys a wonderful business, and asks you three
                          questions no filing can answer
data.template/            one demonstration journal per strategy — invented
                          companies, invented figures
tools/sample_kit.py       the shared machinery every sample is built with
tools/make_sample.py      builds them by driving the real API, and refuses to
                          write one if a story stops being true
tools/contract_reference.py
                          regenerates the reference tables in the strategy
                          documentation from the host's own tables
docs/WRITING-A-STRATEGY.md
                          the host/strategy contract, for someone writing one
docs/example-strategy/    a complete worked bundle. Deliberately NOT under
                          strategies/, so it never loads and no journal can
                          be created against its invented numbers
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
  allocation.py           where capital goes across the journal: what may
                          take it, ordered by how far each is from its own
                          strategy's target
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

- **Two of the four strategies.** Graham and Buffett ship; Lynch and Discount
  Closure do not. `dev_reference_docs/ledger-default-profiles.md` carries a
  section for each, and each of those sections now opens with a header saying
  which state it is in and what the review corrected — read it and the
  addendum beside it before authoring either.
- **Debt falling due within 24 months, and so the maturity wall built on it.**
  The characteristic failure of a discount strategy is the value trap, and the
  mechanism by which a cheap company becomes a zero inside a two-year holding
  period is a refinancing that has to happen while you own it. The measure
  would be debt due within 24 months over cash plus twice trailing free cash
  flow. It is not built, and the reason is coverage rather than effort: the
  by-year repayment elements are footnote-level and thinly tagged, so the
  figure would be absent for a large share of filers and quietly wrong for
  some — and an absent knockout makes a security grey rather than red, which
  is a lot of greyness bought for a measure that is not reliable. A
  **12-month** version is computable from what the concept map already
  resolves; it answers a different question, because the 24 months was chosen
  to match the period a trap has to survive. Anyone building it on 12 months
  should say so where the value is declared rather than let it arrive as a
  substitution.
- **A fetched bond yield.** Graham's price ceiling is the stricter of a fixed
  multiple and what high-grade corporate bonds pay, and nothing here fetches
  that number — it is in no filing and it is not price data. The yield is a
  setting on the strategy, shipped at a starting figure, and it is the one
  value in the program that goes wrong by sitting still. Changing it is recorded on the
  journal's rule-change record like any other rule change.
- **A strategy that stages an entry.** The contract carries staged plans and
  the allocation view renders them; no shipped strategy declares one, because
  Graham does not buy a statistical discount in thirds and inventing that
  rule so a screen had something to show would put a recommendation into
  shipped content.
- **Choosing which lots a sale draws on.** The record holds whichever
  allocation it is given; the screens always propose oldest-first.
- **Telling a journal what your account looked like in the past.** Answers —
  free cash above all — begin the day the journal is created, so an entry
  dated before that has no account to be sized against and any rule about
  position size reports that it cannot be worked out. That is the honest
  answer and it is why most backfilled purchases record no verdict. Fixing it
  means a dated answer record you can enter history into as well, which is
  its own piece of work rather than a corner of this one.
- **The strategy of the day.** A reconstruction runs *that day's data*
  through *today's* strategy, because the version in force in 2019 is not on
  the machine and, for a purchase predating the journal, never was. The
  record says so in as many words; nothing can make it otherwise.
- **History charts.** Per-filing history exists, so there is something to
  chart.
- **The screening funnel.** Deliberately later. This is the journal first.

## License

MIT. See [LICENSE](LICENSE).

This is a tool for recording and reviewing your own reasoning. It is not
investment advice, and demonstration content uses invented companies.
