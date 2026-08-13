# Writing a strategy

This is the reference for the host/strategy contract. It is for someone with
`engine/contract.py` open in an editor, and it does not appear in the app —
the program is built for people who will never write one of these, and a tab
of developer documentation in it would be complexity charged to the wrong
reader. What the app shows is the strategy a journal is actually stamped with:
what it can say, what it asked you, what its settings are and every time they
moved. That is a different document with a different audience.

**Start with `docs/example-strategy/`.** It is a complete bundle demonstrating
the three things that cost the most time here, and it is short enough to read
in a sitting — about two hundred lines of declaration, two hundred of logic,
and the rest comments explaining why each piece is shaped the way it is. That
ratio is itself worth noticing: most of a strategy is saying what it means,
not working anything out. Read §12 of this file before you write anything.

Contents:

1. [The shape of it](#1-the-shape-of-it)
2. [The bundle](#2-the-bundle)
3. [The declaration](#3-the-declaration)
4. [Settings and answers](#4-settings-and-answers)
5. [What `decide` receives](#5-what-decide-receives)
6. [What `decide` must return](#6-what-decide-must-return)
7. [Evidence](#7-evidence)
8. [Groups, rollups, and the two checks](#8-groups-rollups-and-the-two-checks)
9. [Versions, and when each one moves](#9-versions-and-when-each-one-moves)
10. [When it goes wrong](#10-when-it-goes-wrong)
11. [What a strategy may never do](#11-what-a-strategy-may-never-do)
12. [The things that cost the most time](#12-the-things-that-cost-the-most-time)
13. [Reference tables](#13-reference-tables)

---

## 1. The shape of it

The host is an engine. Strategies are content.

The host fetches filings and prices, computes measures, assembles periods,
reconstructs any of it as of a past date, renders, records and reports. It
holds no opinion about which strategy is correct, because the same host has to
serve strategies that contradict each other.

A strategy consumes what the host computed and produces one decision about one
security. It holds all the opinions: which measures matter, in which direction,
against what level, and what the answer means.

**The boundary runs one way.** A strategy is strictly a consumer of what the
host provides and a producer of decisions in the format the host defines. It
never fetches, never reaches the network, never touches source data, never
opens a file — not even its own — and never invents vocabulary. Not a state, not
a render type, not a unit, not a comparator, not a destination for a blocked
verdict. A strategy that needs something the host does not offer fails loudly
and becomes a request against the host. It does not work around the gap.

**A strategy cites, it never quotes.** Where a decision refers to a figure the
host owns, it names the subject and lets the host resolve it. The strategy owns
the question — which measure, which direction, which threshold. The host owns
the answer — the value, its unit, whether it was absent and why, and whether
the test was met. That split is the reason a strategy cannot misquote a number
(it never states one), cannot claim a pass on a figure nobody could compute
(absence resolves to `unknown`, never to success), and cannot attribute a level
to a setting that does not hold it (naming the setting and supplying the number
is refused — one or the other).

Everything crossing the line is plain data: one dict in, one dict out. Nothing
framework-shaped, no host objects, no live references into the journal.

---

## 2. The bundle

A strategy is a directory:

```
strategies/<name>/
  strategy.py     STRATEGY (the declaration) and decide(ctx) (the logic)
  values.yaml     shipped defaults for the declared values, with a version
  <reference>     any static data it ships — parsed by the host, never by it
```

**Discovered, not registered.** The host loads what it finds under
`strategies/`. There is no central list to edit; adding a strategy means adding
a directory.

**Logic and declared values live apart, on purpose.** Logic is written in a
real language because behaviour — conditionals, sequencing, anything depending
on what else is true — cannot be expressed in a configuration format without
inventing a language inside one. Declared values live in a YAML file beside it
because a threshold means something on its own and belongs where it can be
read, compared and changed without touching logic. That split follows the
record: values are easy to retune, so they need a legible before-and-after;
logic is not, and cannot have one.

**Loading is defensive at every step.** A bundle that fails to import, declares
itself badly, speaks the wrong contract version, moves its version without
saying what changed, or ships defaults that do not match its declaration is
*refused*: reported with a message naming the file, skipped, and never allowed
to prevent another bundle from loading. Refused bundles are listed on the
Strategy tab with their reasons. Nothing about a broken plugin raises — a
broken plugin is a page fact, never a crashed application.

**Importing runs the module's top level, and only that.** That is how the
declaration is read. `decide` is never called at load, which is what lets the
host build a setup screen and validate a journal before any decision is made.
Do not do work at import time that a missing file or a network could break.

**Two bundles claiming one id are both refused.** A journal is stamped with an
id; guessing which claimant it meant would evaluate it under rules its author
never chose.

**Reference data.** A bundle may ship static data the host does not have — a
sector map, a lookup table — as `.yaml`, `.yml` or `.json` files named in
`STRATEGY["reference"]`. The host parses them at load and hands them back
through `ctx["reference"]`, frozen and shared across every evaluation. That is
what keeps a strategy from opening files itself. A declared reference file that
is missing or unparseable refuses the whole bundle: a strategy reading half its
lookup table produces plausible wrong answers, which is worse than not loading.

---

## 3. The declaration

`STRATEGY` is a plain dict. Every key below is required except `inputs`,
`values` and `reference`.

| key | what it is |
|---|---|
| `id` | lowercase letters, digits and hyphens, starting with a letter. What a journal is stamped with, permanently. |
| `name` | the user-facing name. |
| `summary` | plain language: what this strategy *is*. Shown on the create-journal screen and on the Strategy tab. |
| `version` | whole number ≥ 1. The version of the *logic*. See §9. |
| `contract` | the contract version this bundle speaks. Anything but the current one is refused. |
| `changelog` | `{version number: sentence}`. The declared `version` must have an entry, or the bundle is refused. |
| `states` | every verdict this strategy can reach. |
| `inputs` | what it needs from the user. Optional. |
| `values` | numbers it has an opinion about. Optional. |
| `reference` | file names it ships beside its code. Optional. |
| `declines` | kinds of company this strategy will not evaluate. Optional. |
| `limits` | what the method demands or delivers that this program does not. Optional. |
| `list` | that this strategy works from a set of securities chosen elsewhere. Optional. |

### What you will not evaluate

Most measures the host serves were written for a company that sells something.
A handful of kinds of filer do not merely read oddly on them — they *break*
them, and they break them into confident numbers rather than into gaps. A
lender's operating cash flow moves with the period's change in loans and
deposits, so a shrinking bank generates enormous free cash flow. An insurer's
cash flow carries the growth of float. A property company's depreciation is a
convention rather than a cost, so every measure built on profit understates by
design.

Which kind of company a filer is, is a **fact**: the SEC assigns it an
industry code, EDGAR publishes it, and the host resolves it into one of the
classes in §13. What a strategy does about that is the strategy's business,
and there are exactly two things it can do.

**Route.** Read `ctx["security"]["industry"]["class"]` and branch. Nothing
special about it — it is a host fact like any other and you may cite it as
`{"fact": "security.industry"}`. Route on `["class"]`, never on the `value`
beside it: the value is the sentence a reader sees, and comparing against a
sentence is quoting the host.

**Decline.** Say so in the declaration and the host answers for you:

```python
"declines": [
    {"class": "depository-lending",
     "because": "These tests are the liquidation-oriented balance sheet, and "
                "a bank does not classify its assets as current or "
                "non-current at all. Substituting bank measures would produce "
                "something that is not this strategy any more."},
],
```

A declined company never reaches `decide` at all. The host resolves the
filer's class first — before it even checks that the journal's setup is
complete — and returns a verdict of its own whose render type is
`inapplicable`, carrying your `because` as the reason. Three consequences,
and they are the reason this is a declaration and not a branch:

- The screen that offers a strategy can say what it covers **before any
  journal is stamped with it.** A branch inside `decide` is invisible until it
  fires.
- You cannot evaluate a declined company by forgetting to check, and neither
  can whoever edits this file next.
- `because` is yours because the reason genuinely differs. One rule set
  declines a bank permanently, because its tests *are* the balance sheet it
  cannot read. Another declines one until measures it does not yet have
  arrive. A reader deserves the right sentence, and a host-written "not
  supported" is neither.

**Where the class cannot be established, a strategy that declines anything is
not run**, and the verdict is `unknown` rather than `inapplicable`. That split
is the whole point of the second render type. A missing industry code may
resolve on the next fetch; a bank will not stop being a bank. Several codes
the SEC publishes genuinely do not settle it — American Express and a payment
processor file under the same one — and there the honest answer is that the
code does not say, not a guess in either direction.

You cannot declare a state whose render is `inapplicable`. It says a thing
will never change, so it has to be traceable to something checkable from
outside the bundle, and `declines` is that. Where your rules *do* cover the
company and simply reach no action, that is a `hold`.

### What the method does not promise

`declines` is about a kind of **company** your measures cannot read. `limits`
is about the **method**: something its own author said was part of it that a
journal evaluating one security at a time does not do.

```python
"limits": [
    {"title": "It is a portfolio method, and this is one security",
     "body": "Everything here was worked out by somebody running a "
             "portfolio, and it carries an expected rate of losers the "
             "good outcomes are meant to pay for…"},
],
```

- `title` — the heading, short enough to scan a list of them.
- `body` — plain language. Markdown-ish, rendered as prose.

**Nothing here does anything.** The host renders it and never reads it: no
limit gates a verdict, changes a state, or reaches `decide`. A limit that
altered behaviour would be a rule, and rules belong in your tests and your
levels where they can be checked. This is for the part of a method that
cannot be expressed as a rule at all.

Which is exactly the part that otherwise goes unsaid, and why the field
exists. Every published method these strategies draw on is a portfolio method
with an expected rate of losers built in, and every one of their authors said
so. A screen rendering a verdict on one security is quietly offering
something none of them offered — that this particular one will work — and
nothing contradicts it unless you say so here. Silence is not neutral.

Two shapes worth writing, and both are in the shipped strategies:

- **What the method never claimed.** The expected loser rate; the fact that
  the arithmetic works across a set of positions rather than within any one.
- **The half of the method this program does not implement.** Graham's rules
  sat inside a bond allocation he was explicit about, and an empty screen
  meant hold more bonds rather than lower a threshold. Without that said, a
  strategy that correctly returns nothing for a year reads as broken — and a
  reader who concludes the tool is broken loosens the tool.

### Working from a list somebody else chose

Some methods do not screen. The choosing happens elsewhere — a ranked screen
run against a universe this program does not have — and what the journal is
for is what you do with the names that come back. Say so and the host does
the rest:

```python
"list": {
    "label": "Your Magic Formula list",
    "explain": "The thirty or fifty names the screen returned, and the day "
               "you pulled them…",
    "source": {"name": "the screener's own site — the screener itself",
               "reasoning": False},
},
```

Declared rather than inferred, because everything it turns on has to be
settled before any decision exists. A journal whose strategy declares one
gets the import screen, a tab, and a **blocked verdict with a button** —
`host:list-missing` — until a list has been given to it. A journal whose
strategy does not declare one gets none of that, sees no tab, and is never
asked. The view reads whether *this journal* works from a list and never
which strategy is running, which is what keeps §9 true.

Four facts follow (§13): whether a security is on the list in force, the day
the freshest list carrying it was pulled, the day the current list was
pulled, and how many months old that is. They are ordinary host facts and are
cited like any other. `security.on_list` is **absent, not false**, where the
journal has no list — "not on your list" and "you have no list" are different
answers.

Two things it deliberately does not carry. **No thresholds** — how many names,
how often, how stale is too stale are levels, they belong in `values` where a
change to one lands on the rule-change record, and a list declaration holding
them would be a set of numbers nothing could retune. And **no ranking** — the
host keeps a set of securities with a date, and where a name sat inside the
ranking that produced it is not recoverable from the list, because a rank is a
statement about the thousands of companies that did not make it. A strategy
that implies otherwise is claiming the tool selected something.

`source` is required and is the same field a declared value carries, for the
same reason: where a list came from is the most load-bearing fact on the page
in a strategy shaped like this one.

### States

A state is the whole verdict as far as the user is concerned: a name, a
description, and the render type that tells the host how to draw, sort, count
and aggregate something whose meaning it does not know.

```python
{"id": "worth-buying", "render": "commit",
 "name": "Worth buying",
 "description": "Both tests this strategy will not bend have passed…"}
```

- `id` — lowercase letters, digits and hyphens. `host:` can never collide,
  because the id alphabet has no colon in it.
- `name` — what the user reads as the verdict.
- `description` — plain language, and it is not optional. This is the text a
  reader gets when they want to know what the verdict *means*.
- `render` — one of the six host types. See the table in §13.
- `fix` — **required on a `blocked` state, refused on any other.** Where the
  answer is given. See below.

There is a cap on how many states one strategy may declare (§13). It is
deliberate: states are user-facing vocabulary, and complexity must not creep
back in through the plugin door.

**Declare only what you can reach.** A state nothing ever returns is vocabulary
on the Strategy tab claiming the tool can say something it cannot. It is worth a
test that walks every state. Conversely, *not* declaring a state is how a
strategy says it does not believe in one: a strategy with no `reduce` state is
saying it never trims, and that is legible on the screen in a way a declared
state nothing reaches is not.

### A blocked state must say where it is answered

`blocked` means the tool will not produce a verdict until the user does
something. A blocked verdict that does not say *where* that something is done
is a dead end: the reader gets a sentence naming what is owed and has nothing
to click, anywhere, with no way to find out what the author meant.

So a blocked state names its way out from the host's own closed list, and the
host renders the button. Two refusals enforce it, and they fire in different
places on purpose:

- **At load.** A `blocked` state with no `fix`, or a `fix` the host does not
  have, refuses the bundle. That happens the first time the directory is
  scanned — before a journal is ever stamped with it.
- **At evaluation.** One destination is built out of the decision's own
  citations: the questions under *Your judgement* are exactly the ones the
  decision cited, because a question about one security cannot be declared on a
  setup screen before there is a security to ask it about. So a verdict whose
  `fix` is `judgement` and which cites no judgement is refused — otherwise the
  button leads to an empty section, which is the same dead end one screen
  further along and looks like it worked.

Putting what is needed in `payload.needs` is **not** the same thing. Prose
cannot be clicked and the host cannot read it. `needs` is the sentence; `fix`
plus the citation is the way out.

The list of destinations is in §13. Anything missing from it is a request
against the host.

---

## 4. Settings and answers

A strategy declares two kinds of thing the journal supplies. Getting the split
wrong produces either a strategy that cannot ship or one that asks the user for
something it should have an opinion about.

### The test, and it has two axes

**Can the strategy ship a sensible default? Does changing it move where a bar
sits?** Either one makes it a value.

| | ships a default? | moves a bar? | so it is |
|---|---|---|---|
| a position cap | yes | yes | a **value** |
| a risk-free rate | no | yes | a **value** |
| an account balance | no | no | an **input** |

The risk-free rate is the case worth understanding, because the first axis on
its own gets it wrong. Nobody has an opinion about what the Treasury pays, so
in the ordinary sense no strategy can "have a view" on it. But retuning it moves
every valuation bar in the strategy — so a change to it has to land on the
rule-change record with a before and an after, and that is what being a value
buys. An account balance moves no bar: it is a fact about the user, it changes
because their circumstances changed, and asking them to write a *reason* for it
would be the program treating their life as a rule change.

### Declared values

Numbers the strategy has an opinion about. Every one ships a default in
`values.yaml`; a declared value with no default is refused, and a default for
an undeclared value is refused too — a setting that silently does nothing is
worse than one that will not load.

```python
{"id": "min-roic", "label": "Lowest return on capital it will take",
 "type": "number", "unit": "percent", "min": 0, "max": 100,
 "source": {"name": "…", "reasoning": True},
 "explain": "How much profit the business makes on the money tied up in it…"}
```

- `type` — see §13.
- `unit` — how the number renders.
- `min` / `max` — bounds, for numbers only.
- `options` — a fixed set of `{value, label}` choices, instead of bounds. Text
  and numbers only; a yes/no answer is already a boolean. It earns its place
  because the alternative is free text checked inside `decide`, which fails at
  evaluation instead of while the user is looking at the field.
- `explain` — **required.** Plain language, written for someone who has never
  valued a company. Say what it means before how it is calculated. A field
  without an explanation is incomplete, not a follow-up ticket.
- `source` — **required.** `{"name": where the number came from,
  "reasoning": whether the explanation above is that source's or your own}`.
  Nothing can verify that a level really is a particular book's. What this
  refuses is the three ways the claim goes wrong on its own: being absent,
  being made once for a whole file and silently failing to cover the value
  added afterwards, and being silent about how far it reaches. A level with
  borrowed authority and homemade reasoning is exactly the case a reader needs
  to be able to tell apart. If you made the number up, say so — a value with
  nothing behind it is the case this field exists to make visible.

### Declared inputs

Facts about the account no strategy could guess. They build the setup screen
with no logic running, which is what lets a journal be validated before a
decision is ever made.

```python
{"id": "free-cash", "label": "Free cash", "type": "number", "unit": "usd",
 "role": "cash", "required": False,
 "explain": "Money in the account this journal covers that is not in any…"}
```

Everything a value carries except `source`, plus:

- `required` — whether a verdict is possible without it. A required input with
  no answer produces `host:inputs-missing`, which is blocked with a button to
  the settings screen.
- `role` — what the figure *is*, from the host's closed list (§13). The host has
  no journal-level fields of its own: deciding which of them a journal collects
  would be the host deciding how strategies work. But some figures the host
  reports cannot be computed without one — position weight is market value over
  the account, and the account is not something the host can observe. A role is
  how those meet. A strategy that declares no role simply gets those facts
  absent, with the reason naming the question that was never asked. Two inputs
  claiming one role are both refused — the host would have no way to know which
  figure to report — and the declared `type` and `unit` are checked against
  what the role says the figure is.
- `when` — `{"input": another input's id, "is": the answer that makes this one
  apply}`, or a list of answers any one of which does. An input whose gate is
  unmet is never handed to `decide` at all: a stale answer to a question that no
  longer applies is worse than no answer, because the strategy cannot tell the
  two apart.
- `min_from` / `max_from` — a bound naming another declared field rather than a
  literal. Where the other field has no answer the bound simply does not apply.

### How they resolve

Defaults first, then each override layer in order, the journal's own settings
last, **merged per value**. A strategy that gains a new setting picks up its
shipped default even in a journal that already overrides something else.

Failure is loud and complete: an unrecognised key, a mistyped value or a
missing default produces a sentence naming the file and the key — every problem
at once, not the first one found. Where any layer has errors the host refuses
to evaluate at all and returns `host:values-unresolved`. Proceeding on defaults
the user believes they overrode is the quiet retuning this program exists to
prevent.

---

## 5. What `decide` receives

One plain dict per security, built in `engine/context.py` — whose module
docstring is the authority on the exact shape and is worth reading in full. The
top-level keys:

```python
{
  "contract": 6,
  "today": "YYYY-MM-DD",        # the clock; everything below obeys it
  "security":  {"ticker", "name", "cik"},
  "measures":  {bank id: {"current": known-or-absent,
                          "series": {"cadence", "points", "note",
                                     "truncated"}}},
  "price":     {"latest": known-or-absent, "closes", "events"},
  "position":  {"held", "shares", "opened", "months_held", "last_purchase",
                "purchases", "baselines", "lots", "disposals",
                "market_value", "weight"},
  "portfolio": {"cash", "account_value", "slots", "holdings"},
  "values":    {id: value},     # the resolved chain
  "inputs":    {id: value},     # the answers that apply, and have answers
  "reference": {file name: parsed},   # what the bundle ships, frozen
}
```

A **known-or-absent** node is either
`{"status": "known", "value", "source", "cautions", "provenance"}` or
`{"status": "absent", "reason"}`. There is no null value standing in for one.

A **measure** has one more: `{"status": "inapplicable", "reason", "industry"}`,
where the metric bank says the measure was never built to describe this kind of
company — a lender has no invested capital in the sense return on it means, and
no filing will ever supply one. It is settled from the industry code the SEC
publishes before any arithmetic runs. You do not have to know the word: every
rule here asks whether a status is `"known"`, so an inapplicable measure can no
more come out of a test as a pass than an absent one can. What it is *not* is
`absent` — that is a gap a fetch may close, and this is a boundary that holds
for as long as the company is the kind of company it is.

### Reading rules you can rely on

- **The clock governs everything.** Series points come only from filings filed
  by `today`; prices stop at `today`. A reconstructed evaluation sees the world
  of its day, never this one. Never read the system clock inside a strategy —
  `ctx["today"]` is the only clock there is, and a strategy that reaches past it
  produces a verdict that cannot be rebuilt.
- **Absence is a value.** Every bank measure is present in `measures`. Where the
  host cannot honestly serve a number, `status` is `"absent"` with a reason.
  Nothing is zero-filled, carried forward, interpolated, or inferred from a
  neighbour. Do not write `or 0`.
- **Absence is never success.** The host's own arithmetic turns an absent figure
  into `unknown`, never `pass` and never `fail`. What you *do* about that is
  yours — but if you branch on it yourself, branch on `unknown`, never on
  "did not fail". The same holds for an inapplicable one.
- **A measure can refuse a company outright.** Where the bank says a measure
  cannot describe this kind of filer, its status is `"inapplicable"` and it
  never computes. If your rules rest on such a measure for a kind of company
  you evaluate, you will get `unknown` on that test rather than a number — which
  is a signal that the honest declaration is `declines`, so the reader is told
  the rules do not cover it instead of watching a verdict fail to assemble.
- **A qualified number says so.** Where a figure rests on an approximation or a
  loosely matched line, its `cautions` say so, on `current` and on every series
  point alike. You never restate a caution; the host carries it to the screen.
- **Percent units are percent numbers.** 18.9 means 18.9%, including position
  weight.
- **A share class is a security; the company is not.** `price`,
  `position.market_value`, `position.weight` and every holding in `portfolio`
  are about the *instrument this journal holds*, priced from its own symbol
  alone. `measures` are about the *company* and read every class.
- **`position` is the holding you have now** — including `disposals`, which is
  what *this* holding has sold and never a sale belonging to a holding that
  closed before it opened. `lots` is the one exception: it is the security's
  whole record, including purchases from holdings that closed, which is where
  "have I owned this before" is answered. A rule counting what is held now
  wants `[l for l in lots if l["open"]]`.
- **`baselines` are what you were shown**, frozen onto each purchase and never
  recomputed. A company restating two years of accounts cannot move them.
- **Nothing here says what a position cost.** Cost basis is kept out of the
  context entirely, not merely discouraged. A rule that fires on the distance
  from your own purchase price is anchoring — it makes the same company a buy
  for one person and a sell for another on the same day — so it is not merely
  unsupported, it is unwritable.
- **Unknown keys may appear** in later contract versions. Read what you declared
  an interest in and ignore the rest.

### What the context is, physically

**Frozen, all the way down.** Mappings are read-only proxies and lists are
tuples. Reads work exactly as they do on plain data — `.get`, `in`, indexing,
slicing, iteration, `len` — and writes cannot happen at all. That is what makes
"the host owns the answer" true rather than merely intended: a figure a strategy
could edit is a figure it could quote back differently from the one on screen.
If you need a mutable copy, build your own.

### What the host offers a strategy to call

- `contract.test(ctx, item)` — how one comparison came out. See §7.
- `contract.months_after(day, months)` and `contract.months_between(start, end)`
  — month arithmetic, clamped, each derived from the other so they cannot
  disagree. 29 February plus twenty-four months is 28 February, and a count that
  disagrees with that clamp reports a position as 23 months held on the day its
  two-year clock falls due. Use these rather than writing date arithmetic.
- `contract.PASS`, `FAIL`, `UNKNOWN`, `NOTED` — the outcome words, so a bundle
  branches on the host's own vocabulary instead of on string literals.

---

## 6. What `decide` must return

One dict, exactly three keys.

```python
{"state":   "worth-buying",       # an id this strategy declared
 "payload": {...},                # shaped by that state's render type
 "reason":  {...}}                # why, structured
```

### `payload`

Exactly the keys that state's render type requires, and nothing else. Extra
facts belong in the reason's evidence. The keys per type are in §13.

- **`commit`** — `size` is `{"unit", "value"}` with a unit from the size list
  and a value above zero. `condition` is `None` (buy now, unconditionally) or
  `{"summary": plain language}` saying what must be true first. `plan` is
  optional: the tranches being held back, each `{"size", "condition"}`, in the
  same unit as the size, each with a real condition. The host never evaluates a
  condition — a plan is prose the strategy re-reads on its own next evaluation,
  and the day a condition holds it returns that tranche as the size in front of
  you. Nothing is stored and nothing is scheduled, which is strictly better than
  a plan executing itself six months after anyone last looked at the company.
- **`reduce`** — `to` is `{"unit", "value"}` naming the level to reduce *to*,
  in `weight` or `shares`. Not the amount to sell.
- **`close`** — `when` is a `YYYY-MM-DD` date: the day the exit is due. A close
  with no date makes a scheduled exit fire months early, so it is refused.
- **`blocked`** — `needs` is a non-empty list of sentences saying what decision
  is owed. Remember that this is the sentence, not the way out (§3).
- **`hold`, `unknown`** — `{}`.

### `reason`

```python
{"rule":     "screened-and-assessed",   # required
 "summary":  "Both tests it will not bend passed…",  # required
 "evidence": [...],                      # required, a list
 "groups":   [...],                      # optional
 "note":     None}                       # optional
```

- `rule` — the name of the rule *inside your strategy* that produced this state.
  It renders beside the verdict. A verdict without its rule teaches nothing, and
  teaching people their own rules is the point of the tool.
- `summary` — one plain sentence saying why this state and not another.
- `evidence` — the figures the decision rests on. A verdict about the security
  (`commit`, `reduce`, `close`, `hold`) must cite something; an evaluation-tier
  state (`blocked`, `unknown`) may cite nothing, because "the strategy could not
  run" is not a claim about the company. The exception is a `blocked` state
  whose `fix` is one the host builds out of citations — that one has to cite
  what it is waiting on, because the citation *is* the way out (§3).
- `groups` — the headings the evidence is gathered under. See §8.
- `note` — the escape hatch for prose that genuinely will not fit an evidence
  item. One string, deliberately harder to reach for than it looks. `None` is
  fine.

---

## 7. Evidence

A verdict without the figures that produced it teaches nothing, and a free-text
reason teaches only the security in front of you — it cannot be compared across
holdings or counted over time. So a strategy cites what it examined, and the
host resolves each citation into the rendered fact: the value, its label, its
unit, whether it was absent and why, the limit read out of any setting that was
named, and how the comparison came out.

An evidence item names **exactly one subject**:

| key | cites |
|---|---|
| `measure` | a metric-bank measure, by id. Includes the qualitative ones. |
| `fact` | a figure the host reports (§13), by name. |
| `value` | one of this strategy's declared values, by id. |
| `input` | one of this strategy's declared inputs, by id. |
| `label` | something the strategy worked out itself. |

Where the subject is `measure`, `fact`, `value` or `input`, the host supplies
the value, the unit and the absence — so `actual`, `absent` and `unit` on the
item are **refused**. A figure the host already knows is never restated by a
strategy, because a restatement can be wrong.

Where the subject is `label`, the strategy is stating a figure of its own, and
must supply `unit` (from the host's list) and exactly one of `actual` (the
figure) or `absent` (one sentence saying why it is unknown). Reach for this
last: a stated figure is the one kind of row nobody can check.

Optional on any item:

- `comparator` — one of the host's comparisons (§13). With it, **exactly one**
  of `threshold` (a figure stated outright) or `threshold_from` (the id of one
  of this strategy's own settings, which the host reads for itself). Supplying
  both is refused: that is how a limit gets attributed to a setting that does
  not hold it — "at most your position cap of 5" while the cap held 20. An item
  with neither is an observation, which is a fine thing to cite.
- `group` — the id of one of `reason.groups`.
- `at` — a `YYYY-MM-DD` period end, cites that reading in the measure's filing
  history. `measure` only.
- `since` — one of the baseline anchors (§13): cites how far the measure has
  *moved* since a purchase. `measure` only, and never alongside `at` — one
  citation answers one question. The host finds both readings and does the
  subtraction. You could do that arithmetic yourself; what you could not do is
  *cite* the answer, because a limit is a number or the id of a setting, and
  "five points below what it was when you bought" is neither.
- `change` — `distance` (the default) or `proportion`. Only alongside `since`.
  A ratio that went from 2.6 to 2.1 has moved 0.5 as a distance. A return on
  capital that went from 21% to 14% has fallen by a third — which reads as -33%
  as a proportion and -7 as a distance, and only one of those says the same
  thing to a business earning 45% and one earning 15%.

### Asking the host how it came out

```python
CITE = {"measure": "interest_coverage", "comparator": "at_least",
        "threshold_from": "min-interest-coverage", "group": "core"}

if contract.test(ctx, CITE) == contract.FAIL:
    ...
```

`contract.test` is the host answering the same question it will answer again
when the citation reaches the screen, out of the same context, through the same
code. **Pass the item you are going to cite** and the two cannot come apart.

Before this existed, a strategy had to compare the figure itself in order to
choose a state — the state is chosen before any evidence is resolved — so every
bundle carried a private copy of the comparators, nothing checked the two
agreed, and a verdict could render beside evidence saying the opposite with
nothing on screen saying which to believe.

`test` returns `pass`, `fail`, `unknown` or `noted`. It **raises** where the
citation is not answerable at all — a measure the bank does not hold, a fact the
host does not report, a comparison between a number and a date. That is a fault
in the strategy rather than a fact about the security, and it is deliberately
not `unknown`, which would let a misspelled measure id read as a missing figure.

---

## 8. Groups, rollups, and the two checks

Evidence is gathered into groups, and a group says what it demands of its own
members.

```python
KNOCKOUTS = {"id": "knockouts", "name": "Tests this strategy will not bend",
             "requires": "all"}
CORE = {"id": "core", "name": "Core tests", "requires": "at_least",
        "threshold_from": "core-tests-required"}
NOTED = {"id": "size", "name": "Where it sits in your account",
         "requires": "noted"}
```

- `requires: "all"` — every member carrying a test has to pass. **The default**,
  and the strict direction: an author who says nothing gets the rule that
  refuses a contradiction rather than the one that allows it.
- `requires: "at_least"` — that many of them, named the way any other limit is:
  `threshold` or `threshold_from`, never both.
- `requires: "noted"` — nothing is demanded. Reported so the reader can see
  them, or acted on by a rule the host cannot express.

The rows of one group must be **contiguous** in the evidence list — a group
renders as one heading over one run of rows — and a declared group with no rows
is refused, as is a row naming a group that was not declared.

**The rollup is the host's.** "Six of eight core tests passed" is counted from
the same outcomes the eight rows render, not from a tally the strategy kept. A
group's own outcome uses the same four words a row does and reaches them the
same way: unreadable rows are neither passes nor failures, so a requirement six
rows short of its bar with three rows unreadable is `unknown`, not `fail`.

Two things then follow, and they are the only places the host compares a
strategy's conclusion against its own arithmetic.

### A commit cannot contradict its own evidence

A state whose render is `commit` is **refused** when:

- a group it declared came out anything other than `pass` — including
  `unknown`. The strategy said all four of these must pass, or six of these
  eight; a figure nobody could compute has not met that demand, and treating it
  as though it had is absence reading as success in the one place a reader looks
  for the rollup; or
- a citation carrying a comparator and *no* group came out `fail`. Nothing
  declared it a requirement, so the host refuses the outright contradiction and
  nothing more.

The asymmetry is deliberate. A hold may legitimately cite failures — that is
often why it is a hold — and an exit rests on them by definition. It is `commit`
alone that says capital may go in.

**This is the rule that decides the shape of your `decide`.** See §12.

### A blocked verdict cannot be a dead end

Covered in §3: a `blocked` state declares its `fix` at load, and where that fix
is one the host builds out of citations, the decision has to cite one.

---

## 9. Versions, and when each one moves

Three version numbers, three different questions.

### `STRATEGY["contract"]` — which host contract this bundle speaks

The host refuses any value but its own. That is what lets the contract be
extended later without silently breaking what already exists.

**When the host bumps it is not "when the shape changed incompatibly."** The
test is: *would a strategy written against the previous version read what it
receives wrongly and silently?*

A key that disappears raises, and a raise gets noticed. A key that keeps its
name, its type and its label while answering a *different question* produces a
plausible wrong verdict with nothing on screen saying so. A meaning change is
the quietest break there is, so it is the one this mechanism most exists to
refuse. Adding a key is not a bump, because strategies must tolerate keys they
do not read. The comments above `CONTRACT_VERSION` record every past bump and,
just as usefully, several changes that deliberately did *not* bump and exactly
why.

### `STRATEGY["version"]` — the version of your logic

Move it whenever the bundle's behaviour or declaration changes, and add a
`changelog` entry saying what changed — the host refuses a version with no
entry. That entry is not paperwork: a change to logic cannot be recorded as a
before and after the way a number can, so the author's own account of it is the
only thing the rule-change record can carry. Write it for someone reading their
own journal in five years, and say plainly when a change moves what the strategy
will buy.

### `values.yaml: version` — the version of the declared numbers

Move it whenever any number in the file moves. That is what puts the change on
the rule-change record of every journal running the strategy, with a before and
an after.

Move a number and leave the version alone and the host **still** catches it — a
journal's stamp holds the resolved values themselves, not only their version
number — and reports it as the louder thing it is: settings that moved with
nothing marking the change, on the journal's record rather than the author's,
with a written reason owed from whoever did it.

---

## 10. When it goes wrong

Every failure comes back in the same envelope, produced by the host and saying
so. `evaluate` never raises. A strategy can never crash the application, can
never block a recording, and can never take another bundle down with it.

| what happened | when | comes back as |
|---|---|---|
| the module will not import, or declares itself badly | load | the bundle is refused and listed with its reason |
| a required input has no answer | evaluation | `host:inputs-missing` |
| the declared values will not resolve | evaluation | `host:values-unresolved` |
| the journal's strategy is not installed here | evaluation | `host:strategy-missing` |
| `decide` raised, or called `sys.exit` | evaluation | `host:strategy-error`, naming the file and line **inside the bundle** — never a full path, never a stack trace |
| the decision is outside the contract | evaluation | `host:invalid-decision`, with every problem in the message |
| the stored filings or prices could not be read | before evaluation | `host:data-unreadable` |

The full list, with what each renders as and how each is escaped, is in §13.

**Fail loudly inside your own logic.** A strategy that needs something the host
does not offer should raise rather than approximate. `host:strategy-error` names
the line; a plausible wrong verdict names nothing.

---

## 11. What a strategy may never do

- **Fetch anything.** No network, at load or at evaluation.
- **Read source data.** No filings store, no price store, no journal file.
- **Open a file** — including its own. Reference data is declared and the host
  parses it.
- **Read the system clock.** `ctx["today"]` is the clock.
- **Invent vocabulary.** Not a state id it did not declare, not a render type,
  not a unit, not a comparator, not a baseline anchor, not a change form, not an
  input role, not a blocked-state destination, not a payload key.
- **Restate a figure the host owns.** Cite it.
- **Mutate the context.** It is frozen; the attempt raises.
- **Reach for what a position cost.** It is not there.
- **Treat absence as success.**
- **Block a recording.** The tool records decisions and never gates them. Acting
  against the signal is allowed by design — a strategy's job is to say what its
  rules say, not to stop anyone.

Anything missing that you need is a request against the host, not something to
work around. The host's tables are small, closed and deliberate; each of them
says in a comment why it is closed and what adding to it costs.

---

## 12. The things that cost the most time

Two strategies and one worked example are the whole of the experience behind
this list. It is in order of what each one actually cost.

### Confirmation counts filings, so a hand-driven journal may never confirm

`contract.confirm` counts consecutive readings out of
`measures[id]["series"]["points"]`. Those points are built from **filings**, and
from nothing else.

A figure the user typed in by hand answers `current` and adds no point. So on a
security with no stored filings — no CIK, nothing fetched, every number entered
by hand — the run is always nought, and an exit on a measure whose estimator
asks for two of them **can never fire**, however bad the number gets. The
strategy is not broken and the host is not lying: nobody observed a second
reading, so nothing is confirmed.

`engine/context.py` states the fact. Nobody states the consequence, and it is
invisible until an exit quietly never fires — there is no error, no absence, no
caution. It is true of real journals and not only of demonstration data: a user
who tracks a company the SEC does not cover, or who has not fetched, is in
exactly this position.

Which measures this bites is now visible rather than a matter of what you wrote:
it is the ones whose estimator asks for filings at all. An exit on a five-year
median, a growth rate or a run of annual losses fires on the current reading and
works perfectly well in a hand-driven journal; an exit on a balance-sheet ratio
or a trailing twelve months does not. If your strategy is meant for hand-entered
data, choose what it exits on with that in mind, and say so in the state's
description — that is the only place a user finds out.

### A commit is refused beside a group that did not pass, so every other branch comes first

The host refuses a `commit` standing beside a group it resolved as anything but
`pass`. That is the guarantee working. What it means for your code is that the
buy branch must be the **last** rung of the ladder, and every way the answer can
be no has to be reached and explained before it.

Write it the other way round — reach for the buy and let the host catch the
contradiction — and the user gets `host:invalid-decision`: "the strategy
returned something outside the contract". That tells them nothing about the
company, and it is how you find this rule, by hitting it.

The same applies one level in. `met` must mean *no knockout is unreadable and
enough core tests passed*, not *no knockout failed*. Absence walking through a
gate by failing to trip it is the quietest bug on this list, and the host's
refusal will catch it — as an unreadable error rather than as a sentence.

### Cite an exit in the direction the holding must keep, not the direction it fires

Write the exit as `interest_coverage below exit-level` and a perfectly healthy
holding renders as a page of red rows beside a verdict of *hold*, because the
host correctly resolved "is it below 4" as false, and false renders as *misses
it*.

Write the same rule as `interest_coverage at_least exit-level` — what the
holding must keep being true — and the same holding renders as passes, the exit
is that test *failing*, and the screen says what you meant. The logic is
identical; only the reader's experience changes, and only in the direction of
being wrong.

You find this by looking at the output, not by reading anything.

### Smaller ones, in no order

- **`decide` runs before evidence is resolved.** You cannot look at the rendered
  rows to choose a state. That is what `contract.test` is for, and passing it
  the same dict you are about to cite is the only thing that keeps the two
  agreeing.
- **A group with no rows is refused, and so are scattered rows.** Build the
  evidence list in group order and only append a group when you appended its
  rows.
- **The `at_least` threshold on a group is a count of rows**, so it has to be a
  whole number. Stated outright, it must be one. Read out of a setting with
  `threshold_from`, the setting itself must be a declared **value** of `type:
  integer` with `min: 0` or higher, and the decision is refused if it is not.
  The check is on the declaration and not on the number, because the number is
  resolved out of a chain the user edits afterwards — a value's type holds for
  the shipped default, for a journal's override, and for anything added to the
  chain later. It must be a value rather than an input for the same reason: a
  value always resolves, and an unanswered input would leave the group with no
  count, which reads as `unknown` and quietly refuses every commit beside it.
- **A citation is answerable however you cite it.** The screens that let a user
  supply a figure, ask a judgement, or clear a blocked verdict are built from
  which *bank entry* each citation reads — never from the shape it renders in.
  So a measure you only ever cite as a change since a purchase still reaches
  the dialog that lets someone type it in. What you cannot do is `confirm` a
  drift: a confirmation counts filings that each carry the failure on their own
  reading, and a baseline is frozen at the purchase rather than re-read.
- **A judgement is a judgement because the bank says so.** You cite it exactly
  as you cite a computed measure; the host decides from the bank that it renders
  as an assessment. You could not disguise one as a measurement if you tried.
- **Do not cite a question your own rules have already made moot.** Citing is
  what puts a question on the page. A screen asking someone to assess the
  durability of a business their own rules have already rejected is the
  overwhelm this program exists to avoid — so reach the refusing state *without*
  the citation, and only cite the question on the branch where the answer would
  actually decide something.
- **`contract.test` raises where a citation is unanswerable** — a misspelled
  measure id, a fact that does not exist, a number compared against a date. It
  comes back as `host:strategy-error` naming the line inside your bundle, which
  is the fastest debugging loop the contract has. It is deliberately not
  `unknown`: a typo must not read as a missing figure.
- **A `close` needs a date and there is no obvious one.** For an exit that has
  already fired, `ctx["today"]` is the honest answer. For a scheduled one — a
  holding period running out — it is the scheduled day, worked out with
  `contract.months_after`, and not today.
- **`weight` is a percent number.** A `size` of `{"unit": "weight", "value": 10}`
  is ten percent of the account, not ten percent of one percent and not 0.1.
- **The changelog entry is checked against the version you declared.** Bumping
  `version` and forgetting the entry refuses the bundle at load, which is easy
  to hit while iterating and reads at first like the bump itself was rejected.
- **`position.opened` is the holding period's first purchase** and does not move
  when a lot is trimmed away. Lot ages are on `position.lots`.
- **A staged `plan` cannot be anchored to what you paid.** Not because the
  payload lacks a field — because nothing about cost is in the context. Anchor
  it to what the business is worth.
- **A verdict that is really about the journal is still one verdict per
  security.** A strategy that works from a list has states meaning "your list
  is out of date" and "you have started enough names this month", and those are
  facts about the journal rather than about the name in front of you — so
  whichever is true is true of *every* unheld security at once, and no two of
  them can be reached on the same day. That is not a fault to design around;
  it is what a method with no screen looks like. What it costs is that a
  sample journal can demonstrate exactly one of them, so the rest belong in
  your tests, and it is worth saying so where a reader will find it.

### Testing one

`strategy_loader.discover(roots)` takes the directories to scan, so a bundle
can be loaded and exercised from anywhere — it does not have to be installed
under `strategies/` to be tested. That is how `docs/example-strategy/` is kept
honest without ever being offered to a user, and it is worth copying: a bundle
under test is a bundle nobody can accidentally create a journal against.

`tests/test_example_strategy.py` is the pattern. Two layers, and both earn
their place:

- **Contexts built by hand**, one dict per case, so a measure can be driven to
  a chosen value directly. Driving fifteen measures to chosen values through the
  compute layer would be a test of the compute layer, and it would be nearly
  impossible to write.
- **One pass through `context.build_context`** against stored filings, so the
  hand-built shape cannot drift from the one a real journal serves. Without it
  the whole suite can pass against a context shape that no longer exists.

Two assertions are worth writing whatever else you do. That no case returns
`host:invalid-decision` — every contract refusal lands there, so one check
catches contradicted commits, dead-end blocks, malformed payloads and scattered
groups at once. And that **every declared state is reached** by some case: a
state nothing returns is vocabulary on the Strategy tab telling the reader the
tool can say something it cannot.

`engine/strategy_floor.py` writes both. Keep every result your cases produced
and end with one line:

```python
from engine import strategy_floor

assert strategy_floor.unmet(record, results) == []
```

It reads nothing but your declaration and those decisions, so it is the same
floor for every bundle rather than one each author reimplements — and it cannot
pass on a suite that drove no cases at all, because a declaration with no states
is refused at load, so every state is unreached.

It is deliberately the documented pair and nothing more. The shipped suites also
assert `result["produced_by"] == "strategy"` on each case as it is produced,
which is stronger — it catches `host:strategy-error` and `host:inputs-missing`
too, and it fails at the case rather than at the end. Write both; the helper
does not replace that one.

---

## 13. Reference tables

Generated from `engine/contract.py`. Do not edit by hand; run
`python -m tools.contract_reference`, and `tests/test_contract_docs.py` will
tell you if you forgot.

### The render types

Four are about the security, two are about the evaluation, and one is about
the scope of the rules. The three tiers are never averaged together: "4 of 12
are hold" is a fact about the portfolio, "4 of 12 cannot be evaluated" is a
data problem, and "4 of 12 are outside these rules" is a fact about the
journal you chose. `inapplicable` is the only one a strategy cannot declare —
the host produces it, from `declines`.

<!-- generated: render-types -->
| `render` | tier | means | payload keys | may also carry | needs attention | a strategy may declare it |
|---|---|---|---|---|---|---|
| `commit` | position | capital may go in | `size`, `condition` | `plan` | yes | yes |
| `reduce` | position | partial exit | `to` | — | yes | yes |
| `close` | position | full exit | `when` | — | yes | yes |
| `hold` | position | no action | — (none) | — | — | yes |
| `blocked` | evaluation | a decision is owed from the user before any verdict | `needs` | — | yes | yes |
| `unknown` | evaluation | not enough data to say | — (none) | — | yes | yes |
| `inapplicable` | scope | these rules do not evaluate this kind of company | — (none) | — | — | — |
<!-- end: render-types -->

### Where a blocked verdict sends someone

<!-- generated: state-fixes -->
| `fix` | button | where it goes | must cite |
|---|---|---|---|
| `settings` | Fix this journal's settings | this journal's setup screen | — |
| `judgement` | Answer these questions | "Your judgement" on this security's page | a bank entry of kind `qualitative`, however it is cited |
| `thesis` | Write down what you think now | this security's thesis record | — |
| `list` | Import a list | the list this journal works from | — |
<!-- end: state-fixes -->

### States the host produces itself

A strategy never declares one of these; they are what the host says when no
strategy verdict exists.

<!-- generated: host-states -->
| state | `render` | shown as | way out |
|---|---|---|---|
| `host:inputs-missing` | `blocked` | Waiting on setup | `settings` |
| `host:strategy-missing` | `blocked` | Strategy not installed | nothing in the app resolves it |
| `host:values-unresolved` | `blocked` | Settings need fixing | `settings` |
| `host:list-missing` | `blocked` | Waiting on a list | `list` |
| `host:strategy-error` | `unknown` | Strategy failed | nothing in the app resolves it |
| `host:data-unreadable` | `unknown` | Data could not be read | nothing in the app resolves it |
| `host:invalid-decision` | `unknown` | Strategy failed | nothing in the app resolves it |
| `host:not-evaluated` | `inapplicable` | Outside these rules | nothing in the app resolves it |
| `host:industry-unknown` | `unknown` | Industry not established | nothing in the app resolves it |
<!-- end: host-states -->

### Comparisons

<!-- generated: comparators -->
| `comparator` | reads as | numbers and dates only |
|---|---|---|
| `at_least` | at least | yes |
| `at_most` | at most | yes |
| `above` | above | yes |
| `below` | below | yes |
| `equals` | equal to | — |
| `not_equals` | not equal to | — |
<!-- end: comparators -->

### Facts the host reports

Cited as `{"fact": "<name>"}`. Each carries its own plain-language explanation
in `contract.HOST_FACTS`, which is what the reader sees.

<!-- generated: host-facts -->
| `fact` | label | unit |
|---|---|---|
| `security.industry` | Industry | `text` |
| `security.sic` | SEC industry code | `text` |
| `security.on_list` | On your current list | `yes_no` |
| `security.listed_on` | Last on a list | `date` |
| `list.pulled` | List pulled | `date` |
| `list.age_months` | Months since the list was pulled | `months` |
| `position.weight` | Position weight | `percent` |
| `position.months_held` | Months held | `months` |
| `position.market_value` | Position market value | `usd` |
| `position.shares` | Shares held | `shares` |
| `position.opened` | Held since | `date` |
| `position.last_purchase` | Last bought | `date` |
| `position.purchases` | Purchases in this holding | `count` |
| `portfolio.cash` | Free cash | `usd` |
| `portfolio.account_value` | Account value | `usd` |
| `portfolio.slots_occupied` | Positions held | `count` |
| `price.latest` | Latest price | `usd` |
| `price.days_since_close` | Days since the price's close | `days` |
<!-- end: host-facts -->

### Baseline anchors

Cited as `{"measure": "<id>", "since": "<anchor>"}`.

<!-- generated: baseline-anchors -->
| `since` | reads as | the moment it anchors to |
|---|---|---|
| `last-purchase` | since you last bought | the last purchase into the holding you have now |
| `first-purchase` | since you first bought | the purchase that took this holding up from nothing |
<!-- end: baseline-anchors -->

### How a move from a baseline is counted

<!-- generated: change-forms -->
| `change` | the row's unit | reads as |
|---|---|---|
| `distance` | the measure's own | "…, change since you bought" |
| `proportion` | `percent` | "…, change since you bought, as a share of what it was then" |
<!-- end: change-forms -->

### How a measure is read, and what a breach of it therefore needs

You do not declare this and you cannot override it. The metric bank states how
every measure is read, and the host derives from that how much evidence a
breach of one of your levels needs — because that is a fact about the
estimator, not an opinion about investing.

The reason it is not yours is worth reading once. Two consecutive readings of a
rolling five-year median share four of five years: they are the same data
looked at twice, and the year that produced the breach does not leave the
window by being looked at again. A rule saying "not on one reading" is a bet
that the next reading carries new information, and on a long window that bet
loses. Where it loses, the host asks the question that does work instead —
drop the year that most favours you and see whether the answer holds.

Patience is still yours. It lives in the level: a strategy that wants to be
slower to sell asks for a worse number, which is a claim about the business, not
for more repetitions, which is a claim about the data that is not true.

<!-- generated: estimators -->
| `kind` | reads as | filings a breach needs | must survive dropping a year |
|---|---|---|---|
| `instant` | read at one date | 2 | — |
| `trailing` | a trailing window | 2 | — |
| `endpoint` | two readings, one at each end | 1 | — |
| `averaged` | means at both ends | 0 | yes |
| `median` | the middle of a window | 0 | under 5 observations |
| `range` | the spread across a window | 0 | yes |
| `cumulative` | added up across a window | 0 | yes |
| `count` | a count of annual reports | 0 | — |
| `assessed` | assessed, not measured | 0 | — |
<!-- end: estimators -->

Ask for the answer with `contract.confirm(ctx, item)`, passing the citation
that says what the holding must keep being true. Where an estimator asks for
the one-year-dropped reading you may cite it too, so the reader can check the
rule rather than take it on trust:

<!-- generated: robustness -->
| `without` | reads as |
|---|---|
| `one-year` | with its most favourable year dropped |
<!-- end: robustness -->

### Kinds of company a strategy can decline

Named in `declines`. Each is a *different* way the host's measures break, not
a label for "financial" — asset managers, exchanges, insurance brokers and
estate agents are ordinary businesses here and are deliberately not on this
list. `engine/industry.py` holds the code-by-code mapping and the reasoning,
against the SEC's published list in
`tests/fixtures/groundtruth/sec-sic-6xxx.json`.

<!-- generated: industry-classes -->
| `class` | reads as | the refusal reads "does not evaluate …" | the filers it covers |
|---|---|---|---|
| `depository-lending` | Depository and lending | banks and lenders | banks, savings institutions, consumer and business lenders, finance lessors and securitisation vehicles |
| `insurance` | Insurance | insurers | life, health, property, casualty, surety and title insurance carriers |
| `real-estate` | Real estate and REITs | property companies and REITs | property owners, operators, developers and real estate investment trusts |
<!-- end: industry-classes -->

### Input roles

<!-- generated: input-roles -->
| `role` | declared as | means | unlocks |
|---|---|---|---|
| `cash` | `number` in `usd` | free cash in the account this journal covers — money that is not in any position | `portfolio.cash`, `portfolio.account_value`, `position.weight` |
<!-- end: input-roles -->

### The rest of the vocabulary

<!-- generated: vocabulary -->
- **Contract version** — `6`. A declaration naming any other is refused at load.
- **Most states one strategy may declare** — `16`.
- **Declared field types** — `number`, `integer`, `boolean`, `text`.
- **Units a `size` may be in** — `weight`, `usd`, `shares` (`weight` is a percent number).
- **Units a cited figure may render in** — `percent`, `percentage_points`, `times`, `ratio`, `score`, `usd`, `shares`, `years`, `months`, `days`, `count`, `times_own_median`, `date`, `text`, `yes_no`, `none`. A strategy picks one; it never invents a rendering.
- **How a comparison can come out** — `pass`, `fail`, `unknown`, `noted`. The host derives one; a strategy branches on it and never asserts one.
- **How an established breach can come out** — `clear`, `breached`, `confirmed`, `unreadable`. `contract.confirm` derives one; a strategy branches on it and never asserts one.
- **Observations at which a median stops needing help** — `5`. Below it, a breach of a median must also survive dropping a year.
- **What a group may demand** — `all`, `at_least`, `noted`.
<!-- end: vocabulary -->

---

## Where to look next

- `engine/contract.py` — the specification itself, written to be read. Every
  closed table carries a comment saying why it is closed.
- `engine/context.py` — the module docstring is the authority on what a
  strategy receives.
- `docs/example-strategy/` — a complete bundle demonstrating the three
  expensive things above. Copy it into `strategies/` to watch it run, and take
  it out again — every number in it is invented, and it is not a strategy.
- `strategies/graham/` and `strategies/buffett/` — two real ones that
  contradict each other, which is the point.
