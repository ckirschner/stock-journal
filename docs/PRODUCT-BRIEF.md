# Ledger — what this application is for

**A brief for the session that will redesign and rebuild the interface.**

Written 2026-08-14 from a long interview with the program's author, who is also
its intended user. It describes who the tool is for, what they are trying to
do, in what order, and what they need to know at each point.

---

## 0. How to read this

**This document contains no design.** No layout, no mockups, no wireframes, no
component names, no colour. Those are yours. What is here is the intent behind
them, and a set of decisions that were made deliberately during the interview
so you would not have to guess at them.

Three kinds of statement appear, and they carry different weight:

- **Decided.** Settled in the interview and confirmed by the author. Follow it.
  If you find a decision that makes something impossible, say so and explain —
  do not quietly route around it.
- **Open.** Genuinely yours to choose. Marked as such, gathered in §9.
- **Missing.** Something the program cannot do today and must be built. Gathered
  in §7 with a size and a priority. **You are not authorised to redesign the
  engine.** Note what you need and build the interface as if it exists, or
  around its absence — but say which.

**The engine is correct and stays.** Months of careful work sit under this, most
of it enforcing guarantees that look like inconveniences until you know why they
exist. `CLAUDE.md` in the project root holds fourteen principles. Read it before
you touch anything. §10 of this document lists the specific places where a
reasonable-looking improvement would break one of them.

**The interface is not correct and none of it is sacred.** The author's words:
*"I'm pretty appalled at how it looks right now... I don't think there is
anything I'm married to in this version of the program."* And: *"Be free to make
the program desirable to use. Feel free to trim as much as possible without
losing the essence of what we are trying to do."*

---

## 1. What this is, in the user's own words

> You've been researching how to invest, you understand the gist of it, but all
> of the tools and data is overwhelming. You want to trade intelligently and you
> want to learn as you do it. But more importantly you want to be **disciplined**.
> You refuse to blindly trade and you want something that helps you not just buy,
> but more importantly **when to sell and how to manage risk**. Using this tool
> not only helps you make intelligent decisions but presents everything to you so
> you avoid making emotional decisions, and stay as objective as possible —
> emotions lead to losses.

Two phrases from the interview that settle more arguments than anything else in
this document:

**"Training wheels, not hands off."** The tool never does the part that teaches
you something, and never makes you do the part that teaches you nothing. When
you are unsure whether to automate something, ask which side of that line it
falls on. Confirming a scheduled deposit: keep it manual, it keeps you honest
about your own money. Typing a ticker fifty times to fetch fifty securities:
automate it, nobody learns anything from that.

**"It's a measuring tool."** Not an advisor. It reports a reading: *based on
this strategy's requirements, this security is a buy / sell / hold / trim / add*.
It states that plainly and attributes it to the strategy. It does not hedge into
mush, and it does not pretend to an authority it hasn't got.

---

## 2. The person

**A retail investor, novice to a few years in. Never a professional, and the
program will never be built for one.** That is not a limitation being worked
around — it is the entire reason the thing exists. Existing tools are
overwhelming, and anyone who wants an overwhelming tool has plenty of choices.

### What they know

They have **"kind of heard of"** all of these: free cash flow, book value,
current ratio, margin of safety, dilution, EBITDA, accruals, enterprise value,
moat, P/E.

> *"We don't need to treat them like first graders, but high school level
> explanations are good."*

So: never assume fluency, never condescend. Plain English throughout. Formulas
are welcome — they're concrete and they build the connection between a word and
a calculation — but a formula is never the explanation.

### How they learn

**Purely by pull. Never by push.** This is the single most emphatic thing the
author said, and it is stated three separate times in the interview:

> *"We shouldn't SHOVE explanations in their face. They should be able to scan
> all metrics available for a security and do something like click a tooltip on
> a metric to find out more about what that is."*

> *"They should be curious and click. No need to put something in their face.
> Present them the facts, if the facts are confusing they should be able to
> click on it and it will tell them what it's all about, then they click out.
> This way if they ever need a refresher they have the option, but they are
> never forced to learn or relearn something they don't want or need to."*

There is **no moment** where the tool is permitted to teach unprompted. Not the
first time a measure blocks a purchase, not on a first run, not ever. The
explanation is always available and never in the way.

### What makes them leave

Two things, tied for first:

1. **Numbers they don't trust.** *"If the numbers aren't working, then no one is
   going to use this, the numbers have to be trustworthy, that's table stakes."*
2. **Friction and reading.** *"When I open it now I see an absolute NOVEL, I'm
   not reading that, it's insane. Especially when I am being forced to read the
   novel every time I go in there and I don't get a choice otherwise."*

Note the second half of that sentence. The complaint is not that explanation
exists. It is that it is **compulsory and repeated**. The fix is that the choice
always exists and the default is always closed.

### One more thing about the person

> *"A lazy person shouldn't be doing this, but someone that has ADHD like me
> should be able to strap in and really make it happen."*

Design for someone who will engage hard for twenty minutes and will not tolerate
a wall of text before they get to the thing they came for.

---

## 3. What they are trying to do

### Buying is easy. Exiting is open-ended.

This is the centre of gravity and it is not where the current app puts it.

> *"Buying is almost easy, exiting is open ended."*

The whole reason the program exists is the second half of a trade and the risk
that sits under it. An entry decision is a moment; an exit decision is a
question that stays open every day you hold the thing, and it is the one people
get wrong under pressure. Design accordingly: the holding and its exit rules are
the main event, not the aftermath of a purchase.

### The three questions of an ordinary visit

Directly from the interview, in the author's order:

1. **"I have an idea — is it a good one?"** Does the company match the metrics
   this strategy needs? Is it worth investigating further?
2. **"How are my current investments doing?"** Are they up or down — and do
   their metrics still stand? Am I supposed to keep holding, add, trim, or sell?
3. **"Is my risk being managed properly?"** Am I making sound decisions but,
   more importantly, protecting myself from losses? *"Losses will happen, but am
   I preventing total meltdowns, and unrecoverable downturns?"*

Question 1 is where **most of the time is spent**. Question 2 is second. Both
resolve to the same underlying act: reading measures and understanding them.

### Risk is the strategy's business, never the tool's

Question 3 has no screen of its own and must not get one.

> *"Risk being managed should actually be outlined and part of the strategy
> itself... Risk management isn't a standard rule, so it must follow whatever the
> strategy dictates."*

The answer to "is my risk managed" is: *every holding's state is clean, and every
position sits inside the size limits your own strategy declared*. The host holds
no opinion about exposure and must not acquire one. This is principle 8 and it is
load-bearing — the same host serves four strategies that contradict each other.

### Risk has no screen. That is not the same as invisible.

Question 3 gets no dedicated screen, and the reason is architectural rather than
editorial: risk in this product *is* the strategy. Graham runs twenty positions with
a hard cap on each; Buffett runs ten and permits 40% in one. Those are opposite
answers to the same question and both are correct inside their own method. A risk
screen would have to say something true for both — which means saying nothing, or
the host inventing an opinion about exposure. That is principle 8.

**But learning to manage risk is a stated reason this tool exists.** From the
interview: the user is here to learn *"when to sell and how to manage risk"*, and
their own question is not about returns — *"losses will happen, but am I preventing
total meltdowns, and unrecoverable downturns?"*

So risk is not a feature to be hidden. It is a thread that runs through the
interface and must be legible at every point it appears:

- **A holding's state can be a risk verdict.** "Too big a share of the account" is
  the strategy speaking about exposure, and it sits in the same place as every
  other state. It must not read as a lesser kind of finding than a broken measure.
- **Position size against the strategy's limit belongs on the row**, not only on
  the buy screen. A person should be able to see where they are concentrated by
  reading the list they already open.
- **The amount a purchase may take is a risk statement**, and the brief already
  decided it headlines in dollars. Why that is the amount — the cap, the slot
  count, the room remaining — is the teaching.
- **Portfolio-level limits are facts about the whole journal** and need somewhere
  to live. Graham's twenty slots, six filled, is not a property of any holding.
  The account header is the likely home. This is the one place where "no risk
  screen" could be misread into "no portfolio-level anything", and it should not
  be.
- **Cash is a position.** A strategy that holds cash because nothing qualifies is
  managing risk, and the interface should not read that as an empty state or a
  failure to find something.

The rule is: **the host never forms a view about exposure; it renders the
strategy's view prominently.** Anything the strategy declares about size, slots,
concentration or cash is first-class content. Anything the host would have to
invent — a correlation warning, a sector limit, a volatility measure — is
forbidden, however helpful it looks.

Where a strategy is silent on risk, the interface says so plainly rather than
filling the gap. "This strategy sets no limit on position size" is a true and
teachable sentence.

### There is no "done"

> *"It's a browsing thing. There isn't a 'done'. The user comes in, checks their
> account status, they review some securities they find interesting, then they
> stop. It's all open ended. Again, the tool should never say 'nothing needed
> from you now' — it's not about the tool needing something from the user, the
> user is trying to get feedback from the tool."*

**Decided:** no completion states, no empty-queue congratulations, no inbox
metaphor. And a copy consequence that runs through everything: the tool never
phrases anything as owed to it. The current header says *"Need a look"* — the
tool demanding attention. It should read as the tool reporting: *these are the
ones your strategy has something to say about*.

### Scale

- **Holdings: modest.** Graham runs 20 slots; Magic Formula 20–30. The author
  does not expect to hold 80 things.
- **Under evaluation: 30–50 at once is normal for a mechanical strategy.** Joel
  Greenblatt's screen hands you 30–50 names in one go.
- **Ceiling:** *"I think having 50–100 may be possible. I don't think it would be
  thousands."*

Nothing may break at 100 rows. Everything should feel right at 10–30.

---

## 4. The shape of the work, over time

### Cold start

**Decided: a quick-start flow.** Ask enough, require little.

Order:

1. **Pick a strategy** — from readable summaries including *who this one is for*
   (§7, item 9). This choice is permanent for that journal.
2. **Name the journal.** One journal is the normal case; a second journal means
   a second real trading account, not a second opinion.
3. **Account size** — total (cash plus positions), then the breakdown: how much
   is cash, what the positions are.
4. **Anything you already own** — ticker, purchase date, quantity, price, with
   several purchases per name supported. This is the existing backfill
   machinery, promoted out of a buried button. It rebuilds each day's verdict
   from that day's data.
5. **SEC identity and Tiingo key.** Required, honest, with a direct link to the
   free signup.

On the setup wall, the author is unambiguous:

> *"Unfortunately this tool only works with Tiingo. If the user doesn't have
> Tiingo it cannot fetch data and provides nothing. It should require these
> things and offer a link to Tiingo to set up the free account."*

So say so plainly rather than letting someone wander into an app full of dashes.

**Critical framing.** Existing holdings are evaluated for **exit**, not entry.
The buy decision is behind them. Say this before the verdicts appear, or the
first thing a new user sees is eight red judgements on trades they cannot undo.

**Not now, but wanted:** a questionnaire that helps someone pick a strategy.
Explicitly out of scope for this rebuild.

### The watchlist loop — where most of the time goes

An idea arrives, usually from outside: a screener, a list, something they read.
For a mechanical strategy it arrives as 30–50 names at once.

1. **Add** — one name, or a bulk paste/import.
2. **Fetch** — one name auto-fetches; a bulk import does not, and lands as an
   explicit *no data yet* state.
3. **Read the verdict and the measures behind it.** This is the core act of the
   program and it must be the easiest thing in it.
4. **Investigate further.** The author's definition: *"Investigating more should
   really be telling the user to go take their notes."* It means answering the
   strategy's open-ended questions (moat, management, capital allocation) and
   writing down what you think. The work happens outside the tool; the tool is
   where the conclusion lands.
5. **Buy, or clear it out.** Cleared is cleared — *"If they want it back, they
   put it back manually."*

### The holding loop

Open it, and answer four questions in this order — this is the author's own
ordering of what is in their head, and the security page follows it:

1. **What is my status on this security?** Do I own it, and is there a
   recommendation?
2. **How do the required metrics fare?** (Charts here eventually.)
3. **What about the rest of the metrics?**
4. **Are there open-ended questions for me?** Moat, leadership, and so on.

Note that the judgement questions come **last**, not in the middle where the
current app puts them.

### The moment of acting

Buy and sell are available **wherever a security appears** and all of them land
in the same place: that security's buy/sell screen, with today's verdict in
front of you.

This reverses a deliberate decision in the current app, which refused to put a
"buy more" button on a holding's own page on the grounds that nobody opens a
losing position at random and a size-stamped button there is permission to
average down. The author overrode it. The protection survives anyway, because
the guardrail was never the button's absence — it is that pressing buy shows
today's verdict and demands a written reason when you are going against it. That
works from any door.

**After a purchase**, land on the security you just bought. (Open to revision;
the author had no strong view.)

### The track record

Closed positions, demoted. Not a place to evaluate anything.

> *"Previous holdings should be available but not necessarily promoted like the
> rest... it needs to read more as a track record. Not really a place to evaluate
> a stock. It should really be about how a previous holding did, transaction
> history kind of thing."*

And: *"they won't have a 'you could have made this much if you just hung onto
this' feature."* **No counterfactuals, ever.** The tool does keep pricing a
closed position — that is how it answers *did my sell rules work* — but it never
frames it as what you missed.

A name you used to own and are considering again **re-enters through the
Watchlist** and is judged from scratch. The old round trip stays in the track
record; the new decision is a new decision.

### Cadence, and looking backwards

The backwards-looking analytics — how your overrides actually performed, whether
a rule you keep ignoring is miscalibrated rather than you being undisciplined,
what happened after each kind of exit — are **behind a menu**, not on a main
screen, and are not worth showing until there is enough history to mean
something. *"Maybe monthly, I haven't thought about that yet... so maybe yearly.
It doesn't need to be front and centre."*

### Between sessions

**Nothing.** No notifications, no background work, no email. *"Out of scope at
the moment."* Everything that changed must be discoverable when you are standing
in front of it, and needs no persistence beyond the snapshots described below.

---

## 5. What the tool already knows — a capability inventory

You cannot design what you don't know exists. This is what the engine hands the
view on every read. Nearly all of it is currently rendered somewhere, most of it
badly.

### The verdict

Every security resolves to **exactly one state**, always, from one call. The
state is declared by the strategy and carries its own name and description in
the strategy's own words (*"Cheap enough to buy"*, *"The safety has gone"*,
*"One reading past the line"*). Graham declares 13 states; Buffett 11; Lynch 12;
Magic Formula 7.

Every state maps to one of **seven host-owned render types**, which is what the
view sorts and colours by — it never learns which states exist:

| render | means | asks for attention |
|---|---|---|
| `commit` | capital may go in | yes |
| `reduce` | partial exit | yes |
| `close` | full exit | yes |
| `hold` | no action | no |
| `blocked` | a decision is owed from the user before any verdict | yes |
| `unknown` | not enough data to say | yes |
| `inapplicable` | these rules do not evaluate this kind of company | no |

Each carries a sort order, so a list ranked by "what asks most of you" needs no
view-side knowledge.

A `blocked` state always names its **way out** from a host-owned list — fix the
journal's settings, answer these questions, write down what you think now,
import a list — and the host supplies the button label. There are no dead ends
by construction.

### The reason behind a verdict

Structured data, not prose:

- **`summary`** — one sentence from the strategy.
- **`rule`** — the identifier of the rule that fired, plus the strategy's version
  and its settings version.
- **`rests_on`** — *what decided it*. The host names the specific measures that
  were decisive, in the bank's own words. This is what you want on a table row.
- **`evidence[]`** — one row per thing looked at. Each row carries:
  - the **subject**: its label, its unit, its kind (a measure, a fact about your
    position, an answer you gave at setup, one of the strategy's own settings,
    your own judgement, how far something has moved since a purchase, or a
    leave-one-year-out re-test), and a plain-language explanation.
  - the **observation**: known with a value, or absent with a reason, or not
    applicable with a reason — plus any cautions and the source of the figure.
  - the **test**: the comparator phrase ("at least", "below"), the threshold, and
    *whose* threshold it is — "your Exit level for the current ratio".
  - the **outcome**: `pass`, `fail`, `unknown`, or `noted`.
- **`groups[]`** — evidence gathered under headings, and each heading says what
  it demanded. **This is the three-tier structure the author asked for and it
  already exists:**
  - `all` — every member must pass. These are the non-negotiables. Graham calls
    its group *"Tests this strategy will not bend"*.
  - `at_least N` — X of Y must pass.
  - `noted` — reported, never blocking. Graham calls this *"Reported, never
    blocking"*. These are the strengthening candidates.

  The host counts passes itself, so a heading's rollup ("6 of 8 passed · 1 could
  not be worked out") cannot disagree with the rows under it. A verdict that
  contradicts its own evidence is refused by the contract.
- **`note`** — one string, for prose that genuinely will not fit anywhere else.

### The payload of an actionable verdict

- `commit` carries a **size** in one of three units — percent of the account,
  dollars, or shares — and optionally a condition it is waiting on, and a staged
  plan of tranches with what releases each.
- `reduce` carries the target to shrink **to**.
- `close` carries the date the exit falls **due**.
- `blocked` carries a list of what it **needs**.

### Four different ways there is no number

This is the honesty machinery and it must survive the redesign. They are
genuinely different facts with different fixes:

1. **Absent** — nothing was fetched, or the filing does not support it. The host
   says which, in a sentence. *Go and look.*
2. **Not applicable** — this measure was never built to describe this kind of
   company. Settled from the SEC's own industry code before anything computes.
   *No amount of looking will change it.*
3. **Not set** — the strategy named a threshold nobody supplied. The test did not
   fail; it never ran.
4. **Series ended** — a price exists but the security stopped trading. It is the
   last close it ever had, not what it trades at.

A value is **never invented**. Not zero, not carried forward, not interpolated.

### Cautions

A caution is a sentence about what a number rests on — a share class valued at a
sibling's close, a balance-sheet line matched by its label rather than a mapped
concept, a price too old to be current. They **travel with the value everywhere
it goes**, and they propagate through derivation: one borrowed price becomes the
same sentence on eleven measures. A real company's data page produces around 38
caution lines saying about 9 distinct things.

A caution is not a failure and must never be drawn as one — a red mark on twelve
of a company's twenty-nine measures is how a reader learns to stop looking at
all twenty-nine.

**Important:** a caution qualifies what a *reader* sees. It never qualifies what
a *decision* consumes. Where a value feeds a verdict and cannot be right, it is
absent, not warned about.

### The measures

**74 entries in the bank: 71 computed, 3 you answer yourself.** Each computed
entry carries:

- a label, unit, display format, and polarity (higher/lower is better, or
  neither — several are deliberately neither)
- an **estimator** — how the value is read, which decides how many readings a
  breach of a level needs before a strategy may act
- a **derivation**: the formula, and the window it is read over
- its **inputs**: which filing lines, which prices, which other bank entries
- an **explanation** in three parts: *plain* (what it means, before how it's
  calculated), *misfires* (where this number lies to you), and *attribution*
  (whose idea it was)
- **`not_meaningful_when`** — machine-evaluable conditions under which it refuses
  to compute, each with why

The three judgement entries (moat durability, management integrity, capital
allocation) carry a **question**, a response shape (prose required, marked pass
or fail, unmarked means unassessed), and the same three-part explanation.

### The record the user writes

All of it append-only, dated, and never rewritten:

- **Purchases and sales**, as lots. Everything about a position is derived from
  its lots on read — never stored, because a stored total is a second opinion
  about a fact the lots already settle.
- **The decision frozen at each purchase and sale**, with all its evidence, in
  the words and thresholds in force that day.
- **Why I own this** and **what would make me wrong**, versioned, each amendment
  keeping the whole prior version and the reason it changed.
- **A valuation claim** — you enter assumptions, the value is solved for. There
  is no field anywhere that accepts a target price.
- **Judgement answers**, with reasoning, with full history.
- **Hand-entered values**, dated, which always beat fetched ones and are never
  overwritten by a fetch.
- **Notes.**
- **Change records** — what a strategy demanded and when it moved, what a measure
  definition meant and when *that* moved, what you answered at setup and when
  you changed it.

### What it can tell you about your own behaviour

- Purchases made **with** the signal versus **against** it, each with win rate
  and average return.
- **Which rules you override, and how those overrides did.** If overriding a
  particular rule keeps working out, that rule is miscalibrated — not you. This
  is principle 10 and it exists so the analytics cannot become a guilt machine.
- Outcomes grouped by **why you sold**, including what the price did afterwards.
- Names you **passed over** from a list, and what they did.

### Data and provenance

- Filings straight from SEC EDGAR, stored raw per accession, add-only.
- Prices from Tiingo, per symbol, with terminal-series detection.
- **Every computed value names the filing it came from** — e.g. *"Assets for
  2025-09-30 from 10-K 0000320193-25-000073"*. Today that is a sentence, not a
  field. See §7 item 7.
- A cross-check that compares the tool's own price × shares against the public
  float each 10-K states about itself — an independent test that catches
  adjusted-price, split-basis, currency and share-class errors in one shot.
- The company's SEC industry classification, and whether the strategy declines
  that kind of company.

---

## 6. Decisions

These were settled in the interview. Each has its reason. Follow them.

### Information architecture

1. **One inventory screen with filters, not three tabs.** Holdings, watchlist and
   track record become filters over one list. At 30–50 candidates plus holdings
   you compare across the boundary anyway, and three tabs is three places to
   learn. *(The author invited alternatives here — see §9.1.)*
2. **The buckets are renamed.** *Ideas* → **Watchlist**. *Current holdings* →
   **Holdings**. *Previous holdings* → **Track record**. The watchlist is where
   most time goes; the track record is a record, not a workspace.
3. **"Where capital goes" folds into the main list as a sort.** It existed as a
   separate screen mainly because it was the only door to adding, and that reason
   is gone. Its real value — comparing everything eligible at once, ranked by
   amount — is the main list sorted properly, with the dollar figures as columns.
4. **The measures reference is scoped to your strategy.** Not all 74. *"I don't
   know why that library is in there to be honest... this huge thing of 74
   metrics just because some strategy somewhere used that metric, not helpful. We
   want to know the metrics this strategy is using, that's it."* A "show
   everything" escape hatch may exist for the curious, well out of the way.
5. **The journal is a named context in the header with a menu behind it**, not a
   row of buttons. One journal is the normal case; the switcher must not occupy
   the same weight as navigation.
6. **The backwards-looking analytics live behind a menu** and appear only once
   there is enough history to mean anything.

### Density and teaching

7. **Prose is opt-in everywhere. Terse is the resting state.** Nothing renders a
   paragraph by default. The always-visible layer is: the value, what it is
   called, its unit, and — if absent — one line saying why. Every explanation,
   every caution, every derivation is behind a click. Hover to show temporarily,
   click to pin until dismissed.
8. **There is no unprompted teaching, ever.** Not on first run, not the first
   time a measure blocks a purchase. Explanation is always one click away and
   never in the way.
9. **Formulas may be more visible than prose** — possibly always-on, possibly a
   global toggle. They are concrete and short. Full explanations are not.
10. **Evidence is a table: everything visible, one line per row, with a
    problems-first toggle.** Name, value, your limit, met or missed. Both of the
    shapes offered in the interview, as one control — the toggle changes the
    order, not the contents. *"It's important to have everything visible so the
    end user trusts and believes in what they are seeing. But it doesn't need to
    be verbose by default."*

### The verdict

11. **The verdict is stated plainly and attributed, not hedged.** The state name
    as the strategy wrote it, with the strategy named beside it. It is a
    measuring instrument reporting a reading.
12. **`unknown` gets its own treatment and never reads as neutral.** Today the
    interface paints *"Not enough to go on"* the same grey as *"these rules don't
    cover this kind of company"* — but the first means **don't buy** and the
    second is genuinely neutral. Not the red of a failed test, not grey, and
    never nothing.
13. **A state that is waiting says what it is waiting for, in the headline.**
    "Breached — waiting on one more filing", not a sentence you must read to the
    end of.
14. **A declined company is allowed in and badged afterwards.** The industry comes
    from the SEC's code inside the filings, so nothing is knowable until a fetch
    happens. Add it freely, fetch, then a persistent badge — *"Graham doesn't
    evaluate banks"* — with one click to why.
15. **No cash never suppresses a verdict.** It still says buy; the shortfall is a
    fact reported beside the amount.
16. **Sizing headlines in dollars**, with the share count derived beside it and
    the percentage smallest. *"x% of the account is always a dollar amount."*

### The record

17. **A trim reads as "Sell — trim"** and goes down the same recording path as
    any sale. It is not a separate mechanism with its own vocabulary.
18. **Buying or selling against the signal always requires a written reason.**
    This is the one piece of mandatory friction in the program and it does not
    move. Note the nuance the author raised: if a judgement you previously
    marked *pass* flips to *fail* and that becomes the sell signal, you are
    selling **with** your policy, not against it.
19. **Rule-change friction drops to a quiet record.** Editing a threshold in a
    config file is already deliberate — you had to go into a file. It lands in
    the strategy's own change history, readable later, with an optional note. The
    banner that sits on every screen demanding a reason is removed. **The record
    itself is untouched** — principle 3 requires that the change is detected and
    written down, and it still is. Only the nagging goes.
20. **Declared thresholds are read-only in the app.** The Strategy screen shows
    what each is, where it came from, and what changed — but has no editor. Your
    *answers* (free cash, account size) stay editable, because those are facts
    about your account that genuinely move. Changing a rule while looking at a
    position you want to buy is the failure the whole design exists to prevent.
21. **Notes attach to a dated snapshot**, so a note is always anchored to what
    everything said the day it was written. Two kinds: free-form post-its the
    user drops anywhere (including a passive field in the purchase log), and the
    strategy's judgement questions, which are metrics like any other and live in
    the security's evaluation section.
22. **Snapshots are per security.** A separate, much smaller journal-level
    snapshot records account value and cash only.
23. **"New status" means changed since your last saved snapshot.** That gives the
    word an exact meaning, ties it to something you deliberately did, and needs
    no continuous history — which the engine does not have and should not grow.
24. **Cash becomes a dated record** with a kind: deposit, withdrawal, dividend.
    Scheduled deposits are offered as a one-press confirmation on the day, never
    automatic.
25. **A row shows both returns** — against what you paid, and over the timeframe
    you chose. They answer different questions. Either both at once or a toggle.

### Onboarding and vocabulary

26. **Quick-start flow**, ordered as §4. Nothing required unless the tool
    genuinely cannot run without it — and Tiingo genuinely is.
27. **The words "thesis" and "falsifier" are gone from the interface.** They
    become *Why I own this* and *What would make me wrong* — which is what the
    record already calls them internally. Both optional, both marked strongly
    recommended, each with a worked example behind a click showing what a good
    one looks like.
28. **Judgement tooltips carry two things**: what a good answer looks like, and
    *where to go find out* — the company's products, how they sell against
    competitors, what the company says about itself. The tool cannot answer these
    and shouldn't try; its job is to make the homework findable.
29. **"Provenance" is dead.** It becomes *Where this number came from*.
30. **Sample data leaves the interface.** The "load sample journals" button goes.
    If a demo ever ships it is an importable file, not a button that creates five
    journals.

### Behaviour

31. **Adding one security auto-fetches**, with a "fetch now" checkbox defaulted
    on. Bulk import does not — it lands as an explicit *no data yet* state.
32. **Bulk fetch shows per-name progress, never blocks other work, and is never
    silent.** You can act on the first name that lands without waiting for the
    fiftieth.
33. **Staleness is always apparent and never blocking.** None of these strategies
    are day-trading; a day-old figure is not a catastrophe. But if the number is
    not from today, that must be obvious without hunting.
34. **Nothing fails silently.** Every failure says what didn't work and roughly
    why, in place.
35. **Charts let you pick which measures to overlay**, with your threshold drawn
    on each, and permit enabling all of them even though it will be unreadable —
    *"it helps them learn how to use charts in the real world a bit better."*
36. **Bulk actions start with multi-fetch and remove/delete**, built on a
    framework that makes adding more of them cheap later.

---

## 7. What must be built

None of this exists today. Each item says what it is for and how big.

| # | What | Why | Size | Priority |
|---|---|---|---|---|
| 1 | **Deposits and withdrawals** — a dated cash record with a kind (deposit, withdrawal, dividend) | Without it, "up 12% this year" is a lie the first time someone adds money. Today there is only a single editable "free cash" figure and its edit history. | Medium — new record type, atomic writes, and it feeds the account header | **Required** |
| 2 | **Snapshots** — a user-saved record of what everything said about a security on a day, saved explicitly and automatically on a purchase | The author's answer to "how do I know what changed". Also what notes anchor to, and what "new status" is measured against. | Medium — the freezing machinery exists for purchases; this generalises it | **Required** |
| 3 | **Snapshot comparison** — select two or more snapshots of one security and see the trend between them | *"They could check off 2 or more snapshots from the same security and review the trend between them."* Also enables "what moved since last time" on a row. | Small once #2 exists | **Required** |
| 4 | **Portfolio value as of a past date** | The account header's "change over a timeframe you choose". The ingredients all exist — free-cash answers are already dated, lots give exactly what was held on any date, and the host can already price one security as of a past date. Only the aggregate is missing. Combine with #1 to net out deposits. | Small–medium | **Required** |
| 5 | **A written reason on a sale that goes against the signal** | Purchases against the signal require one; sales do not. The asymmetry is a gap, and panic-selling is the exact behaviour the tool exists to catch. | Small — a field on the sale record and a required prompt | **Required** |
| 6 | **A measure's series over time**, for charting | The host can already recompute any measure as of a past date and keeps a per-filing series for confirmation rules. What is missing is a call that returns the series in one go. | Small | High |
| 7 | **The filing accession as a field, not only inside a sentence** | Every value already names its filing in prose. To link straight to sec.gov you need it as data — building a URL by parsing prose is how you ship a broken link. The author's answer on trust: *"providing a link back to the source of that number, if at all possible."* | Small | High |
| 8 | **A strategy declares the measures it may read** | Makes the scoped reference (§6.4) knowable before any journal exists, so the chooser can say "this reads 22 measures, here they are". And it can be *enforced* — the contract could refuse a citation outside the declaration, which is exactly how the rest of this codebase guarantees things. | Small — one declared list plus a check | High |
| 9 | **A strategy declares who it is for** | Wanted at the chooser and nothing carries it today. Draft copy in §8; the author wants expert review of the wording after the rebuild. | Small — one declared field | High |
| 10 | **Bulk import of tickers**, and multi-select fetch across many securities | 30–50 names arrive at once from a screener. Adding them one at a time is the friction the author named unprompted. | Medium | High |
| 11 | **Scheduled deposits** — a recurring amount the user confirms with one press on the day | Training wheels: the tool remembers, the user confirms. | Small, depends on #1 | Medium |

---

## 8. Vocabulary

### Never say

| Don't say | Say |
|---|---|
| Provenance | Where this number came from |
| Thesis | Why I own this |
| Falsifier | What would make me wrong |
| Need a look / needs attention | Your strategy has something to say about these |
| Nothing needs you today | *(say nothing — there is no done state)* |

Watch **inapplicable**, **robustness** and **basis** — the author called each
"probably fine, depending on context". Judge each landing site; replace where it
reads as jargon rather than everywhere.

**Fine as they are:** override, knockout test, caution / qualified, backfill,
lot, position weight, verdict, signal, evidence.

### Who each strategy is for — draft copy

Written as our best assumption, to be put in front of experts after the rebuild.
The author asked for exactly this.

- **Graham** — *For someone who wants a rule that tells them when to get out.* It
  buys ordinary businesses at a statistical discount to what they own and
  typically earn, and sells when the discount closes, the balance sheet breaks,
  or two years pass — whichever comes first. It asks you to form no opinion about
  whether the business is any good. It will not evaluate banks, lenders, insurers
  or property companies. Suits someone who does not want to have views about
  companies and does want a hard exit.
- **Buffett** — *For someone willing to form an opinion about a business and hold
  it for years.* It buys a business good enough to own for decades, and only at a
  price that leaves something on the table. It never sells because the price got
  high and never because time has passed — only because the business broke. It
  will not conclude until you have answered questions about the moat and about
  management honestly. Suits patience and reading; punishes anyone who wants
  activity.
- **Lynch** — *For someone who follows companies and their growth.* It buys a
  company that is growing at a price that has not paid for the growth yet, and
  sells when the growth stops or the price runs past it. More turnover than
  Buffett, more judgement than Graham. Suits someone willing to check in each
  quarter and act on what the numbers say.
- **Magic Formula** — *For someone who wants to exercise as little judgement as
  possible.* You pull a ranked list from Greenblatt's screen yourself, buy a few
  names from it every couple of months until the portfolio is full, and sell each
  after about a year. It never judges a company — the list already did. Suits
  someone who does not want to evaluate businesses at all, and who can live with
  owning names they would never have picked.

Every one of these is a **portfolio method with an expected rate of losers built
in**. Each strategy already declares its own limits, and the chooser must show
them — a screen that stays silent about that is quietly promising something the
method never did.

---

## 9. Open — yours to decide

1. **Whether one filtered inventory screen is actually right.** The author liked
   it and explicitly left it open: *"Put that in as a possible option that should
   be weighed when determining the entire flow later on."* Weigh it against the
   alternative and commit.
2. **What a row looks like at rest, and what expanding one reveals.** The author
   handed you this: *"Use best judgement on this — think like you're an expert
   trader to decide what you would want there, then think like a novice to decide
   how you would need it displayed to make sense."* The content decided in the
   interview: a candidate row carries ticker and company, the verdict, *what
   decided it*, the must-pass measures as columns, and price with its freshness.
   A holding row adds shares, average cost, current value, return since purchase,
   return over the chosen timeframe, how long it has been held, and its share of
   the account. The **presentation** is yours.
3. **The account header's exact contents.** Decided: account value, change over
   the chosen timeframe, cash, positions held, and how many your strategy has
   something to say about. The author suggested some items might be
   user-toggleable, and asked for "the expert's version, then the training-wheels
   version by default". Yours to resolve.
4. **Where the buy/sell screen lives** — a step on the security page, a modal, a
   route of its own. Only the rule is fixed: every door leads to one place, and
   today's verdict is in front of you when you get there.
5. **Where you land after recording a purchase.** The author's guess was the
   security you just bought, with no strong view.
6. **How the three tiers of measure (must-pass / X-of-Y / strengthening) are
   distinguished visually** — the data is there; the treatment is yours.
7. **How charts are selected and stacked.**
8. **All colour, type, spacing, and motion**, subject to the constraints in §11.

---

## 10. Traps

Things that look like improvements and will break something load-bearing. Read
`CLAUDE.md` for the full set; these are the ones a redesign walks into.

1. **Do not let the view learn what a measure or a strategy is called.** Adding
   either means adding a definition, with no view code changed. If you find
   yourself writing `if (measure === 'current_ratio')` or naming a strategy in
   the interface, you have taken a wrong turn (principle 9). The current view is
   disciplined about this and it is worth preserving — it is why four strategies
   with wildly different vocabularies render through one screen.
2. **Do not collapse the four kinds of absence into one em-dash.** They have
   different fixes and a bare dash tells the reader nothing. This was fixed once
   already, deliberately, after five different facts came back as the same null.
3. **Do not make a caution look like a failure.** It is a number saying what it
   rests on. Colour it as a problem and readers learn to ignore all of them.
4. **Do not add a gate.** Anything can be recorded, always, including a purchase
   against a screaming red verdict. The tool records decisions and never blocks
   them (principle 2) — because months later, your own record of what the signal
   said and why you went ahead anyway is what teaches you. A screen that refuses
   to appear is a gate however it is described.
5. **Do not let a strategy's verdict be re-derived in the view.** One evaluation,
   one state. Two code paths reaching their own conclusions is how contradictory
   states become true at once (principle 7).
6. **Do not show a number without a way to find out what it is.** Every value
   must explain itself in place — what it means in plain language, how it is
   derived, what a good value looks like, and where the thinking comes from. The
   *default* is now closed (decision 7), but the path must exist for every single
   figure. A new measure without an explanation is incomplete, not a follow-up
   ticket.
7. **Do not recompute or rewrite anything already recorded.** A frozen decision
   renders in the words and thresholds that were in force the day it was frozen,
   not today's. Corrections are new entries.
8. **Do not put personal data in the repository** and do not write it under the
   project root at runtime (principle 11). Data lives in the OS application
   support directory. The Tiingo key lives in the OS credential store and is
   never shown, exported, or logged.
9. **Do not let colour carry meaning alone.** Every state also has words. And
   colour communicates state and nothing else — if it is doing decorative work,
   it cannot be trusted when it is doing semantic work.
10. **Do not add a "you could have made this much" figure.** Explicitly refused.

---

## 11. The constraints, restated

From the original brief, unchanged and non-negotiable:

- Colour carries state and nothing else. No decoration.
- Never colour alone — every state also has words.
- A verdict can always be traced to what produced it, without leaving the screen.
- Nothing reads as advice. The tool reports what the person's own rules say.
- Nothing about the engine, the data, or how decisions are computed changes. If
  something underneath makes good design impossible, note it — do not redesign
  it.

And two from `CLAUDE.md` worth surfacing here because they govern every layout
choice you will make:

- **Legibility over density.** Overwhelm is the failure mode, not ugliness. When
  a change adds capability and complexity together, the complexity is the thing
  to argue about, and the burden is on the capability to justify itself.
- **Simple over everything.** If a screen grows, something comes off it. Prefer a
  good default over a setting. Prefer one obvious path over two flexible ones.

---

## 12. The sentence to keep on the wall

> The point is a person who can say **why** they bought something — not that a
> program told them to.
