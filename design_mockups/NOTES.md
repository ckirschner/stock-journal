# Three directions — what each argues, what each trades away

Open `index.html` for links and shortcuts. All three show the same invented Graham
journal — same figures, same states, same rules — so the comparison is about
structure, not content. Every direction covers the one-inventory list and the
CALDR detail page, because that page is where the two readers collide.

The shared problem, restated: one reader wants *what does my strategy say today*;
the other wants *why, and what does this number mean*. The current app interleaves
the second reader's material into the first reader's path. All three directions
keep every explanation — nothing was deleted — and differ only in **where the
second reader's material physically lives**. That is the honest space of answers:
below (A), beside (B), or beneath (C).

---

## A · The ruled page — teaching lives *below* the line it explains

A single column set like a book. The resting state is one line per fact. Clicking
a line unfolds a quiet indented gloss directly under it — what it is, the formula,
where the number came from, what qualifies it, where it misfires, whose idea —
and clicking again folds it away.

**Argues:** locality. The explanation belongs at the exact point of curiosity,
in reading order, the way a footnote belongs at the bottom of its own page. No
second surface to learn; the page is the whole interface. This is the most
book-like and the least inventive — which is a feature for a tool meant to be
boring for years.

**Trades away:** stability while studying. An open gloss pushes the rest of the
table down, so the second reader churns the first reader's layout; comparing two
glosses means scrolling between them (one open at a time keeps it calm). At 30–50
candidate rows the unfold-per-row pattern also does nothing to help you study
*across* securities.

## B · Instrument and margin — teaching lives *beside* the page

Two surfaces. The left plane is the instrument: verdict, facts, evidence table,
record — permanently terse, it never grows a paragraph. Every name, figure, and
heading is a handle that fills the right margin with its gloss. The margin is
also where acting happens: Buy more / Record a sale open there with today's
verdict pinned on top, which resolves the brief's open question about where the
buy/sell screen lives (§9.4) with "nowhere — it's the margin of the security".

**Argues:** the two readers deserve two surfaces. The answer plane never moves
while you study, so the anxious reading and the curious reading stop competing.
On the list, clicking a row previews its whole verdict in the margin — you can
walk 50 candidates with the arrow of your attention without ever leaving the
table, which is the 30–50-names-from-a-screener loop the brief centres.

**Trades away:** width and singleness. It needs a wide window to be itself (the
margin overlays or collapses below ~900px, undemonstrated here). The gloss is
physically distant from the line it explains — your eye travels. And a persistent
second column is a real piece of interface chrome for a product that wants to
feel like a page, not a workbench.

## C · The depth dial — teaching lives *beneath* the page, one level down

One global control (keys 1 · 2 · 3) moves the entire page between three
altitudes. **Reading:** verdict, what decided it with the two figures, the
position strip, actions — nothing else; the whole screen fits without scrolling.
**Evidence:** every figure, one line each, groups and tallies complete.
**Study:** every gloss unfolded inline, formulas visible — the "novel", chosen
deliberately. The dial applies to the list too: states only → states with
figures → states with reasoning sentences.

**Argues:** the two readers are the same person on different *days*, so the mode
belongs to the visit, not the element. On an anxious day you never see a
paragraph; on a study day you never click forty little toggles — you turn the
dial once. It is also the cleanest answer to the author's "expert version /
training-wheels version" request for the header: they are altitudes 2 and 1.

**Trades away:** mixed-mode reading. You cannot study one row while everything
else stays terse — depth is all-or-nothing per visit (a deliberate purity; a
hybrid C+A would allow row-unfolds at altitude 2, but then the dial stops being
the single mechanism and the design collapses back into A with a mode switch).
Study altitude is genuinely long — the novel returns, but only when summoned.

**They did not converge.** A/B/C put the gloss below, beside, and beneath; the
click cost, layout stability, and list behaviour differ materially in use.

---

## Deliberately identical in all three (so the comparison is fair)

- **State colour semantics.** Commit green · reduce/close one red family (the
  words "trim" vs "exit" carry the difference) · hold inked, uncoloured — no
  action asks no attention · blocked ochre (not exercised in this journal) ·
  **unknown indigo** — its own colour, never grey, never red, always paired with
  words ("not a pass", "not calm — blind"), per decision §6.12 · inapplicable
  grey with words. Colour never appears decoratively anywhere.
- **Cautions as footnote marks (°)**, ink-coloured, expanding to the full
  sentence — a qualification, never a warning triangle, never amber.
- **The four-question order** on the detail page: status → required metrics →
  everything else read → questions for you / your record.
- **Waiting states say what they wait for in the headline**; sizing headlines in
  dollars with shares beside and percent smallest; both returns on every row;
  the account header carries value, change-over-timeframe, cash, positions
  **of 20 places**, and "something to say about N".
- **Vocabulary:** where-this-number-came-from, Why I own this / What would make
  me wrong, Watchlist / Holdings / Track record. "Need a look" is gone.
- Absence renders in words with its reason ("not known — no filing data is
  stored… fetch data first"), never a bare dash; group tallies count it as
  neither pass nor fail.

## Where the mockups run ahead of the engine (as-if-built, all small)

Shown as if they exist, per the brief's instruction to note rather than build:

1. **Change over a chosen timeframe** in the header and the per-row "past month"
   return — brief §7.4 (portfolio value as of a past date). The per-security
   ingredients exist; the aggregate endpoint does not.
2. **"Since your saved reading of 02 Aug: nothing has moved"** — snapshot
   comparison, §7.3. Snapshots themselves exist (see errata). Note the honest
   case shown: a comparison that reports *no change* is still doing its job —
   here it is exactly what the waiting rule needs to know.
3. **"Your readings" series** in B's margin — the measure-series call, §7.6.
4. **OKELL "trim to 10% — selling ≈58 sh restores it"** — derived from the
   reduce payload's target; arithmetic the engine could own (principle 5), not a
   new capability.
5. **Candidate must-pass columns** on watchlist rows — §9.2's decided content.
   A carries them inline on the row; B carries them in the margin preview (its
   presentation of the same decided content); C surfaces them at the Evidence
   altitude. A declared measure list (§7.8) would let these render before any
   data exists.

## Skins of the chosen direction (added after B was picked)

The owner chose B and rejected the paper-and-serif look. Two reskins of the
identical B structure — same HTML, same margin behaviour, same red/green/grey
action semantics — exist so the look can be chosen separately from the
structure:

- **`b-daylight.html`** — bright white ground, cool hairlines, Schibsted
  Grotesk + Spline Sans Mono, rounded verdict card and floating margin panel,
  pill-shaped actions, 140ms hover transitions. Fresh by light and type, not by
  decorative colour: state hues are still the only hues.
- **`b-nightdesk.html`** — dark ground (#0f1114), Instrument Sans + Red Hat
  Mono, luminous state colours tuned for dark (green #3ecf8e, red #f07067,
  indigo #9a96f2). A focused evening instrument; nothing glows that doesn't
  mean something.

Both load their typefaces from Google Fonts when online and fall back to system
faces offline. Everything is a variable in `:root` — ground, hairlines, radii,
the two families. The original `b-instrument-margin.html` is kept for comparison.

**Decision (2026-08-14): Nightdesk is the chosen skin — one palette, dark,
committed.** A light theme and toggle were built and then removed the same day,
on the owner's call: two palettes that both have to keep colour purely semantic
doubles the surface on the one thing this product cannot afford to get wrong,
forever. The palette still lives entirely in `:root` variables (nothing
hardcoded outside it) — that property survives and the rebuild should keep it.
Daylight stays on disk as the rejected exploration.

## Six corrections from the owner's review of Nightdesk (2026-08-14)

All applied to `b-nightdesk.html`; each is a rule for the rebuild, not just a
mockup edit. Kept unchanged, per the same review: states as the leftmost row
content, the pane instead of a page, "6 of 20 places" in the header, and
CALDR's "waiting on the next filing · nothing owed" line.

1. **The header separates verdict-tier from evaluation-tier.** "Something to
   say · about 3 of your 6" now counts only position-tier states (reduce/close);
   a second cell — "Cannot be watched · 1 — exit checks cannot run" — carries
   the evaluation-tier blindness on its own, in the unknown colour, because a
   holding the tool cannot see must never hide inside a to-do count. The engine
   already draws this line (tier: position vs evaluation); the header now
   respects it.
2. **One green was doing two jobs; the jobs are now two colours.** (Corrected
   twice: the first fix dimmed buy-eligible to neutral ink, which got the
   hierarchy backwards — commit is the most action-carrying state on the screen
   and must be the brightest.) Final form: `commit` has its own colour, a
   luminous cyan (`--commit:#4dc9f2`), the loudest thing in the list and never
   confusable with a passing test; passing measures and positive returns keep
   their green, now named `--clean:#3ecf8e`; holds and waiting stay quiet;
   reds, amber, and the cannot-evaluate violet are untouched. This mirrors the
   engine: `commit` is its own render type, not a variant of `hold`, and the
   palette now carries that. The copy fix survives — with the ambiguity gone,
   the pane's "not advice to spend it" apology stays deleted. Test audience:
   the person who opens this anxious and looking for permission.
3. **A row cites the resolved decision; it never composes numbers beside it.**
   Sub-lines now carry only host-resolved fields — the payload rendering
   ("sell — trim · to 10.0% of the account"), the allocation amount, or the
   strategy's own summary clause. Pairings like "trim to 10% · 12.4% now" are
   the restatement shape this codebase spent branches removing, and nothing
   verifies them.
4. **Absence is shown, with its fix, per kind.** The mockup now demonstrates
   all four: not fetched (THRAP — fetch, or type the figures you have); not
   meaningful for this kind of company (STANM — declined, permanent); not
   computable from the filings held (CALDR's Altman Z″ — "fetching again will
   not add a line the company never filed", with the typed-value way back and
   the cleared-stale-value story); not yet answered by the user (Expected
   value — "not calculated · this security has not been valued in this
   journal"). CALDR's fiction gained one fetch (9 filings, 08-11) to make the
   third kind honest — and typed values still ruling afterwards is the real
   engine behaviour, which is what fix 5 needed shown.
5. **typed° is legible.** The marker got weight (larger, dotted underline,
   hover title) without becoming a nag — it is the state a real user lives in
   before their first fetch, and the price fact's gloss now teaches the actual
   rule: dated closes are stored, but a typed value wins until cleared.
6. **One palette.** See the decision above.

## What an adversarial review pass caught, and where the fixes belong

The mockups were reviewed against the brief's traps and decided list, and against
their own arithmetic, before delivery. Fixed in place: an internally
contradictory "what changed since your snapshot" line; a header timeframe return
irreconcilable with the rows; an NCAV/market-cap figure arithmetically impossible
beside the shown P/B; the bank rendered as `unknown` when §6.14 decides
declined-and-badged (STANM now demonstrates "Outside these rules" with the
badge); "Thesis broke" in the sell reasons; trim sizing without dollars; the
track-record row headlining a fresh verdict instead of the round trip.

Three of those point at the **engine or sample kit**, not the interface, and are
worth their own log entries:

- `exit_reasons` in the host is `["Thesis broke", …]` — the banned word (§8),
  and it gets frozen into every sale record it's chosen on. Needs the rename at
  the source, with the old string kept readable in existing records (principle 3).
- The shipped Graham sample carries two arithmetic impossibilities a careful
  user could catch: NCAV/MC 0.34 beside P/B 3.28× (NCAV can never exceed book,
  so the ratio caps at ~0.30), and a thesis of "a third of what the tubes and
  plant are worth on the books" recorded at P/B ≈ 1.0. The mockups correct the
  first and keep the thesis verbatim (it is the record's voice); the sample kit
  should fix both.
- Graham's own state copy says "Nothing is owed from you today" — the brief bans
  owed-framing in the interface (§8, §3-copy). The mockups render the strategy's
  sentence verbatim, as decision §6.11 requires; if the framing should go, that
  is an edit to the strategy's declared copy, not to the view.

One review finding is left as an open choice rather than fixed: **returns are
coloured by sign** (green up, red down) in all three directions, which reuses
the hues that also carry verdict tone — on OKELL a red state sits beside a green
+105%. Conventional and instantly readable, but it is colour carrying two
meanings. The alternative — returns in ink with explicit signs, colour reserved
for verdicts alone — is stricter under "colour carries state and nothing else"
and slightly harder to scan. Worth deciding once, for whichever direction wins.

## Where the brief is wrong — errata worth recording

§7 says "None of this exists today." Three of its Required items shipped after
the interview, before this session:

- **§7.1 Deposits and withdrawals** — built. `engine/cash.py` is the dated cash
  record (opening / deposit / withdrawal / dividend, derived balance, and the
  contributed-vs-earned split that makes "up 12%" honest). The current UI already
  renders the ledger on Where capital goes.
- **§7.2 Snapshots** — built. `engine/snapshots.py` ("a day you kept") freezes
  the same object a purchase freezes, deliberately undatable to today. What's
  still missing is only §7.3, the comparison between two of them.
- **§7.5 Written reason on a sale against the signal** — built. The sale path
  computes `reason_owed` and the dialog requires the sentence; the asymmetry the
  brief describes no longer exists.
- **§7.4** is half-built: cash balance as-of-a-date exists; the aggregated
  portfolio value as-of does not. Related, and worth folding into the same work:
  today's masthead market value is summed **client-side** in the view — the one
  place the current app computes a substantive figure outside the backend.

One smaller point: §5's render-type table says `blocked` is what "asks for a
decision before any verdict". True — but note the live sample journal never
produces it; the state most likely to greet a new user with typed-in data is
`unknown` ("Exit checks cannot run"), which is why these mockups spend decision
§6.12's special treatment on it.

---

*Mockups only: static HTML, invented companies, no engine changes, nothing wired
into the app. The small JS in each file is disclosure/altitude switching for
review, not proposed implementation.*
