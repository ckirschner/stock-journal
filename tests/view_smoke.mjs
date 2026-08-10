/* Render every screen against a real get_state payload, under Node with a
   stub DOM. Driven by tests/test_view_smoke.py, which builds the payload
   through the same Api the window calls.

   This is one smoke path, not a testing framework. It exists because the
   view layer carries real logic and the standard for it has been "correct by
   inspection" — which is the standard that produced the defects the Python
   reviews caught. What it can catch: a key renamed on the Python side, an
   undefined dereference in a branch nobody clicked, a number rendering as
   NaN, a whole section silently disappearing. What it cannot: anything about
   how it looks.

   Usage: node view_smoke.mjs <state.json> <app.js> */

import fs from "node:fs";
import vm from "node:vm";

const [statePath, appPath, mode] = process.argv.slice(2);
/* Two jobs, one harness. "coverage" (the default) also insists the payload
   reaches every surface the view draws — that is what stops a screen being
   silently unexercised. "render-only" drops those complaints and keeps the
   real ones, for a payload that exists to draw the branches the coverage
   fixture cannot reach and is not expected to reach the ones it can. A gap
   is not a defect; an unrendered screen is. */
const DEMAND_COVERAGE = mode !== "render-only";
const state = JSON.parse(fs.readFileSync(statePath, "utf8"));

const els = {};
const mkEl = (id) => (els[id] ||= {
  id, innerHTML: "", textContent: "", className: "", dataset: {},
  querySelectorAll: () => [], querySelector: () => null,
  appendChild() {}, remove() {}, prepend() {}, close() {}, showModal() {},
  focus() {}, onclick: null, onchange: null, value: "", readOnly: false,
  style: {}, open: false,
});
const ctx = vm.createContext({
  document: {
    getElementById: mkEl, querySelectorAll: () => [],
    createElement: () => mkEl("scratch"), addEventListener: () => {},
    body: { appendChild() {} },
  },
  window: { addEventListener: () => {} },
  setTimeout: () => {}, console,
  Number, String, Object, Array, Math, Date, JSON, Set, Map, RegExp,
  Intl, isNaN, parseInt, parseFloat,
});
vm.runInContext(fs.readFileSync(appPath, "utf8"), ctx, { filename: "app.js" });
Object.assign(ctx, { __state: state });
const run = (code) => vm.runInContext(code, ctx);
run("S = __state;");
// A stub backend, serving replies the Python side captured from the real
// Api. Some of the view loads asynchronously — the coverage panel does —
// and without this those loads fail and the page renders "could not reach
// the app backend" as its content. That was invisible for as long as the
// harness never yielded to the microtask queue, which is a bad reason for a
// panel to look tested.
run(`window.pywebview = { api: {
  preview_purchase: async (t) => (__state.__previews || {})[t]
    || { ok: false, error: "no preview captured for " + t },
  get_coverage: async (t) => (__state.__coverage || {})[t]
    || { ok: false, error: "no coverage captured for " + t },
} };`);
["view", "maststats", "subtitle", "foot", "tabs"].forEach(mkEl);

const problems = [];
/* A surface the payload never reached. Only a defect when this run is the one that is supposed to reach everything. */
const gap = (...parts) => {
  if (DEMAND_COVERAGE) problems.push(parts.join(""));
};
const out = {};

function check(label, code) {
  try {
    const html = run(code);
    if (typeof html === "string") {
      // A number that reached the screen as NaN, an object stringified into
      // the markup, or an undefined interpolation are all the same defect:
      // the view read a key the backend does not send.
      //
      // `/*` is a fourth of the same kind. Every screen here is built from
      // template literals, and a comment written one line too far inside one
      // stops being a comment and becomes body text — silently, because it
      // is still valid JavaScript and still renders.
      const m = html.match(
        /.{0,80}(undefined|\[object Object\]|\bNaN\b|\/\*).{0,80}/);
      if (m) problems.push(`${label}: rendered "${m[0].replace(/\s+/g, " ")}"`);
    }
    out[label] = html;
    return html;
  } catch (e) {
    problems.push(`${label}: threw ${e.name}: ${e.message}`);
    return "";
  }
}

check("mast", "renderMast(); renderTabs(); 0");
for (const t of ["holdings", "previous", "ideas", "strategy", "data"]) {
  run(`tab = ${JSON.stringify(t)};`);
  check(t, t === "strategy" ? "strategyView()"
    : t === "data" ? "dataView()" : "listView()");
}
run('tab = "holdings";');
for (const s of state.securities) {
  check(`detail:${s.ticker}`, `detailView(find(${JSON.stringify(s.ticker)}))`);
}
// The dialogs render from a strategy's declaration and from the lot list,
// which is where a renamed key or an unhandled field type shows up first.
// They write into the stub's dialog body rather than returning markup.
const dlg = (label, code) => check(label,
  `${code}; document.getElementById("dlgbody").innerHTML`);
dlg("dlg:settings", "dlgSettings()");
dlg("dlg:newjournal", "dlgNewJournal()");
const holding = state.securities.find((s) => s.bucket === "holdings");
if (holding) dlg("dlg:sell", `dlgSell(find(${JSON.stringify(holding.ticker)}))`);

// The three dialogs that write to a dated record. Each renders one branch
// when the record is empty and a different one when it is not — the second
// shows the standing version above the fields, which is the branch that
// dereferences the payload and so the branch that breaks when a key moves.
const written = state.securities.find(
  (s) => ((s._thesis || {}).history || []).length);
const unwritten = state.securities.find(
  (s) => !((s._thesis || {}).history || []).length);
if (written) dlg("dlg:thesis-amend",
                 `dlgThesis(find(${JSON.stringify(written.ticker)}))`);
if (unwritten) dlg("dlg:thesis-first",
                   `dlgThesis(find(${JSON.stringify(unwritten.ticker)}))`);
const valued = state.securities.find(
  (s) => (s._valuation || {}).status === "known");
if (valued) {
  // `pf` passed explicitly: undefined would send it round the backend for
  // its prefills, and there is no backend here.
  dlg("dlg:ev", `dlgEV(find(${JSON.stringify(valued.ticker)}), null,`
    + ` {prefill: {}, references: {}})`);
}

// The purchase dialog, against a REAL preview payload captured from the same
// Api the window calls. It is the one dialog that renders from a backend
// reply rather than from get_state, so it is the one place the two sides can
// hold different shapes for the same document and nothing notices — which is
// exactly what happened: it read the standing view and was handed a raw
// record entry, so it told people who had written a thesis that they had not.
for (const ticker of Object.keys(state.__previews || {})) {
  // dlgBuy is async; the stub resolves immediately, so awaiting it is enough
  // before reading the body. What it must and must not say is asserted with
  // everything else, further down — `must` is not declared yet up here.
  await run(`dlgBuy(find(${JSON.stringify(ticker)}))`);
  check(`dlg:buy:${ticker}`, `document.getElementById("dlgbody").innerHTML`);
}
// the explain-this-figure branch, which only renders when a tip is open
if (state.securities.length) {
  run('tipOpen = "ev:0";');
  check("detail-with-tip",
        `detailView(find(${JSON.stringify(state.securities[0].ticker)}))`);
  run("tipOpen = null;");
}
// the two screens a running app reaches only in trouble
check("welcome", "(() => { const j = S.journal; S.journal = null;"
  + " const h = welcomeView(); S.journal = j; return h; })()");
check("missing-strategy",
  "(() => { const a = S.strategy, b = S.strategy_missing;"
  + " S.strategy = null; S.strategy_missing = S.journal.strategy;"
  + " const h = strategyView() + listView();"
  + " S.strategy = a; S.strategy_missing = b; return h; })()");

// The gate arithmetic, exercised directly. Everything else here goes through
// the stub DOM, whose querySelectorAll returns nothing — so applyGates is
// reached on every dialog and does nothing on any of them. It is the one
// piece of view logic that decides whether a question is ASKED, and a gate
// that never opens reads as a question the strategy does not have rather
// than as a bug. The host's own answer to the same gate is pinned in
// tests/test_contract.py; these two have to agree or the user is shown a
// form the save disagrees with.
run(`__gate = (gateIs, answer) => {
  const f = { dataset: { gate: "g", gateIs: JSON.stringify(gateIs) },
              hidden: null };
  applyGates({ querySelectorAll: () => [f],
               querySelector: () => ({ value: answer }) });
  return f.hidden;
};`);
for (const [gateIs, answer, hidden, why] of [
  [["growth", "blend"], "growth", false, "any of several answers opens it"],
  [["growth", "blend"], "blend", false, "the second answer opens it too"],
  [["growth", "blend"], "income", true, "an answer outside the list does not"],
  [[], "growth", true, "a gate listing nothing can never open"],
  [true, "true", false, "a single yes/no answer still works"],
  [true, "", true, "an unanswered gate stays shut"],
  [3, "3", false, "a number gate is not defeated by the form's string"],
  [3, "4", true, "a different number does not open it"],
]) {
  const got = run(`__gate(${JSON.stringify(gateIs)}, ${JSON.stringify(answer)})`);
  if (got !== hidden) {
    problems.push(`applyGates(${JSON.stringify(gateIs)}, `
                  + `${JSON.stringify(answer)}): hidden=${got}, expected `
                  + `${hidden} — ${why}`);
  }
}

// A qualified figure — one that borrowed a share class's close, say — has to
// render its qualification wherever the number renders. The payload is
// stamped here, last, rather than built upstream: this harness is about what
// the view does with what it is handed, and that the host hands the caution
// over at all is pinned against a real multi-class filer in
// tests/test_cautions_travel.py.
const QUAL = "Class B has no stored close and is valued at the Class A close";
run(`__q = ${JSON.stringify(QUAL)};`);
const stamped = run(`(() => {
  const s = S.securities.find((x) => Object.keys(x._computed || {}).length);
  if (!s) return null;
  Object.values(s._computed).forEach((c) => { c.cautions = [__q]; });
  let cited = 0;
  (((s._decision || {}).reason || {}).evidence || []).forEach((e) => {
    if (e.observed && e.observed.status === "known") {
      e.observed.cautions = [__q];
      cited += 1;
    }
  });
  __qs = s;
  return { ticker: s.ticker, cited };
})();`);
if (!stamped) {
  gap("no security in the payload has a computed value, so the "
      + "qualified-figure rendering is unexercised");
} else {
  check("qualified:detail", "detailView(__qs)");
  dlg("qualified:values", "dlgMetrics(__qs)");
}

// Substance: a screen that renders empty is not a screen that works. Each
// of these is load-bearing text the pivot is supposed to have put there.
// Text a screen must NOT carry. A button offered where the backend would
// refuse the action is a dead end the user finds by clicking it.
const mustNot = [];
const must = [
  ["holdings", state.journal.name, "the open journal is named"],
  ["holdings", "Journal", "the journal switcher is present"],
  // wording unique to the history list, not to the banner above it — the
  // banner also says "rule changes" and would mask the list disappearing
  ["strategy", "append-only: entries are never edited",
   "the rule-change history is reachable"],
  ["strategy", state.journal.strategy.name, "the stamped strategy is named"],
  ["strategy", 'data-act="settings"', "the settings screen is reachable"],
  ["missing-strategy", "not installed", "a missing strategy says so"],
  ["welcome", "one strategy", "the empty state explains the commitment"],
  ["data", "Back up", "export is reachable"],
];
if (stamped) {
  // The whole point of carrying a caution: it is on screen beside the number
  // it qualifies. The values dialog never rendered one at all.
  must.push(["qualified:values", `Qualified — ${QUAL}`,
             "the values dialog says what a computed figure rests on"]);
  // The verdict's own figures, where a verdict cited any. A host state —
  // "the strategy could not be asked" — cites nothing about the security by
  // design, so there is nothing to qualify and nothing to assert.
  if (stamped.cited) {
    must.push(["qualified:detail", `Qualified — ${QUAL}`,
               "a cited figure's qualification renders with the verdict"]);
    // never a bare glyph, and never colour doing the work on its own
    mustNot.push(["qualified:detail", "⚠",
                  "a caution is not rendered as a warning glyph"]);
  }
}
// Everything the declaration asked for has to reach the settings form, and
// everything the lots recorded has to reach the detail page. A field type
// or a lot kind the view quietly drops renders as a shorter screen, which
// is exactly the failure "correct by inspection" never catches.
for (const f of (state.strategy || {}).inputs || []) {
  must.push(["dlg:settings", `name="in_${f.id}"`,
             `the declared input "${f.id}" reaches the settings form`]);
}
for (const v of (state.strategy || {}).values || []) {
  must.push(["dlg:settings", `name="cfg_${v.id}"`,
             `the declared value "${v.id}" reaches the settings form`]);
}
// A state the host says has a screen behind it must render the way in. A
// blocked verdict with nothing to click is a trap, and it is the state a
// strategy that gained a required input puts every journal into.
for (const s of state.securities) {
  const fix = ((s._decision || {}).state || {}).fix;
  if (fix) {
    must.push([`detail:${s.ticker}`, `data-act="${fix}"`,
               `a blocked verdict offers the "${fix}" screen that resolves it`]);
  }
}
// Several of the emptiness guards below are only owed where a strategy
// actually spoke. A journal blocked on setup is the host saying it could not
// ask: it cites nothing about any security, so demanding cited content there
// would fail the very screen that state exists for.
const spoke = state.securities.some(
  (s) => (s._decision || {}).produced_by === "strategy");

// A limit the host read out of a named setting has to say WHOSE it is, on
// screen, beside the number. That attribution is the whole reason the
// strategy is not allowed to state the figure itself, and it is also what
// the override scorecard groups by — an attribution that never renders is
// one nobody can check against the setting it claims.
let attributed = 0;
for (const s of state.securities) {
  for (const e of ((s._decision || {}).reason || {}).evidence || []) {
    const src = (e.test || {}).threshold_from;
    if (!src) continue;
    attributed += 1;
    must.push([`detail:${s.ticker}`, `— your ${src.label}`,
               `${s.ticker}: the limit names the setting it was read from`]);
  }
}
if (spoke && !attributed) {
  gap("no verdict in the harness cites a limit by the setting it "
      + "came from — the attribution renders against nothing");
}

// The heading a group renders as, and the rollup the host counted under it.
// A group is not decoration: it is what tells a reader which rows were
// disqualifying, and it is what the host refuses a contradicted buy on. If
// it never draws, the reader is back to a flat list of fifteen.
let headed = 0;
for (const s of state.securities) {
  for (const g of ((s._decision || {}).reason || {}).groups || []) {
    headed += 1;
    must.push([`detail:${s.ticker}`, g.name,
               `${s.ticker}: the "${g.name}" heading reaches the screen`]);
    if (g.tested) {
      must.push([`detail:${s.ticker}`, `${g.passed} of ${g.tested} passed`,
                 `${s.ticker}: the rollup under "${g.name}" is on screen`]);
    }
  }
}
if (spoke && !headed) {
  gap("no verdict in the harness gathers its evidence under a heading — "
      + "the group rendering is unexercised");
}

// Where a threshold came from, on the screen where someone is about to
// change it. The claim used to live inside the explanation, which meant it
// could be made once for a file and quietly fail to cover a value added
// afterwards; rendered from the declaration, it cannot go missing.
let attributedValues = 0;
for (const v of (state.strategy || {}).values || []) {
  if (!v.source || !v.source.name) continue;
  attributedValues += 1;
  must.push(["dlg:settings", v.source.name,
             `the setting "${v.id}" says where its number came from`]);
  must.push(["strategy", v.source.name,
             `the strategy page says where "${v.id}" came from`]);
}
if ((state.strategy || {}).values && !attributedValues) {
  gap("no declared value in the harness says where its number came from — "
      + "the attribution renders against nothing");
}

// The questions no filing answers. Three renderings have to work: an
// answered one showing the mark and the reasoning behind it, an unanswered
// one showing the question and a way to answer it, and the earlier
// assessments an append-only record keeps — which are the whole reason for
// keeping them and are invisible if only the newest one draws.
const judged = state.securities.filter((s) => (s._judgements || []).length);
if (spoke && !judged.length) {
  gap("no security in the payload has a judgement to answer, so "
      + "the whole judgement surface renders against nothing");
}
let answered = 0, unanswered = 0, revised = 0;
for (const s of judged) {
  must.push([`detail:${s.ticker}`, "Your judgement",
             `${s.ticker} shows the questions it was asked`]);
  for (const j of s._judgements) {
    must.push([`detail:${s.ticker}`, j.label,
               `${s.ticker}: "${j.id}" is named on the page`]);
    if (j.mark) {
      answered += 1;
      must.push([`detail:${s.ticker}`, j.reasoning,
                 `${s.ticker}: the reasoning behind "${j.id}" is on screen`]);
    } else {
      unanswered += 1;
      // Unanswered is not a fail, and it must never be dressed as one.
      mustNot.push([`detail:${s.ticker}`, "Failed",
                    `${s.ticker}: an unassessed question reads as a failure`]);
    }
    if ((j.history || []).length > 1) {
      revised += 1;
      must.push([`detail:${s.ticker}`, j.history[1].reasoning,
                 `${s.ticker}: the earlier assessment of "${j.id}" survives`]);
    }
    // Answered or not, there is always a way to record one. A verdict that
    // waits on a judgement with nothing to click is the trap.
    must.push([`detail:${s.ticker}`, `data-jid="${j.id}"`,
               `${s.ticker}: "${j.id}" can be answered from the page`]);
  }
}
for (const [n, what] of [[answered, "answered"], [unanswered, "unanswered"],
                         [revised, "revised"]]) {
  if (spoke && !n) {
    gap(`no ${what} judgement in the payload — that rendering is `
        + "unexercised and would pass however broken it is");
  }
}
/* Every scalar a decision's payload carries has to reach the screen.

   `esc(undefined)` is the empty string, so a payload key the view reads by
   the wrong name does not throw and does not print the word "undefined" —
   it prints nothing at all, and "Exit due" with no date beside it is a
   scheduled exit whose day has silently gone missing. Checked generically,
   over whatever keys the payload happens to carry, so a render type added
   later is covered without this being edited. */
for (const s of state.securities) {
  const decision = s._decision || {};
  const wanted = [];
  const walk = (node) => {
    if (node === null || node === undefined) return;
    if (typeof node === "object") { Object.values(node).forEach(walk); return; }
    if (typeof node === "boolean") return;
    /* Figures, dates and prose — the parts that mean something on their own
       and vanish silently when read by the wrong key. A payload's unit
       discriminator ("weight", "shares") is not among them: the view turns
       it into a phrase rather than printing the word. */
    if (typeof node === "number" || /^\d{4}-\d{2}-\d{2}$/.test(node)
        || String(node).includes(" ")) wanted.push(String(node));
  };
  walk(decision.payload);
  if (!wanted.length) continue;
  const html = String(run(`(() => { const was = openTicker;`
    + ` openTicker = ${JSON.stringify(s.ticker)};`
    + ` const h = decisionSection((find(${JSON.stringify(s.ticker)}) || {})._decision);`
    + ` openTicker = was; return h; })()`));
  /* The view escapes what it prints, so an apostrophe in a sentence is
     `&#39;` on the page. Compared both ways rather than only raw. */
  const escaped = (v) => v.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
  for (const value of wanted) {
    if (!html.includes(value) && !html.includes(escaped(value))) {
      problems.push(`detail:${s.ticker}: the ${decision.render} payload `
                    + `carries ${JSON.stringify(value)} and the screen does `
                    + "not say it");
    }
  }
}

// Recorded history offers no actions. A lot's frozen decision renders
// through the same row as the live one, and a purchase recorded in 2024
// says what was unanswered THEN — a button inside it reads as though
// answering would change what an append-only record says.
const frozenJudged = state.securities.filter(
  (s) => (s._lots || []).concat(s._sales || []).some(
    (l) => ((((l.snapshot || {}).decision || {}).reason || {}).evidence || [])
      .some((e) => (e.subject || {}).kind === "judgement")));
if (spoke && !frozenJudged.length) {
  gap("no lot in the payload froze a judgement citation, so "
      + "nothing checks what a frozen judgement row offers");
}
for (const s of frozenJudged) {
  const html = run(`(() => { const was = openTicker;`
    + ` openTicker = ${JSON.stringify(s.ticker)};`
    + ` const h = lotHistory(find(${JSON.stringify(s.ticker)}));`
    + ` openTicker = was; return h; })()`);
  if (String(html).includes("data-act=")) {
    problems.push(`detail:${s.ticker}: the lot history offers an action, and `
                  + "recorded history is not something to act on from "
                  + "inside");
  }
}

// The dialog that records one, on a question that has an answer already:
// the prior assessment and the "this appends, it does not replace" wording
// only render on that path.
const withAnswer = judged.find((s) => (s._judgements || []).some((j) => j.mark));
if (withAnswer) {
  const jid = withAnswer._judgements.find((j) => j.mark).id;
  dlg("dlg:judgement",
      `openTicker = ${JSON.stringify(withAnswer.ticker)};`
      + ` dlgJudgement(find(${JSON.stringify(withAnswer.ticker)}),`
      + ` ${JSON.stringify(jid)}); openTicker = null`);
  must.push(["dlg:judgement", 'name="mark"',
             "the dialog offers a mark"]);
  must.push(["dlg:judgement", 'name="reasoning"',
             "the dialog asks for the reasoning"]);
  must.push(["dlg:judgement", "adds a new entry above this one",
             "the dialog says the record appends rather than replaces"]);
}

// The three records the user writes, on the screen and in their dialogs.
// Each of these is the append-only guarantee made visible: if the earlier
// version stops rendering, the record is still correct and the reader has
// no way to know it changed, which is the whole thing being worthless.
if (written) {
  const t = written._thesis, prev = t.history[t.history.length - 1];
  must.push([`detail:${written.ticker}`, t.version.falsifier || t.version.thesis,
             "the standing thesis renders"]);
  must.push(["dlg:thesis-amend", 'name="reason"',
             "amending an existing thesis asks why it changed"]);
  must.push(["dlg:thesis-amend", "it adds a new version above it",
             "the dialog says the record appends rather than replaces"]);
  // The fields carry the standing text, so amending one half cannot blank
  // the other. An entry holds the whole document; a blank box would save a
  // blank half, silently and permanently.
  if (t.version.falsifier) {
    must.push(["dlg:thesis-amend", t.version.falsifier,
               "the amendment form carries the standing falsifier forward"]);
  }
  if (t.version.thesis) {
    must.push(["dlg:thesis-amend", t.version.thesis,
               "the amendment form carries the standing thesis forward"]);
  }
  if (t.version.reason) {
    must.push([`detail:${written.ticker}`, t.version.reason,
               "the reason for the standing amendment renders on the page"]);
  }
  if (t.history.length > 1) {
    must.push([`detail:${written.ticker}`, prev.falsifier || prev.thesis,
               "a superseded thesis is still readable on the page"]);
    must.push([`detail:${written.ticker}`, "earlier version",
               "the page says how many versions came before"]);
  }
}
if (unwritten) {
  mustNot.push(["dlg:thesis-first", 'name="reason"',
                "a first thesis is asked why it changed, when nothing changed"]);
}
// The purchase dialog, which renders from a backend reply rather than from
// get_state — the one place the two sides can hold different shapes for the
// same document. They did: it read the standing view, was handed a raw
// record entry, and so rendered "No thesis on record" over a thesis it was
// holding, splicing the amendment's own reason in as the explanation for the
// absence. A screen asserting absence about something present is the one
// inversion this program must never make, and nothing was watching for it.
// What the dialog must say is read off `_thesis` — the detail page's own
// payload, which is the standing shape — never off the preview reply. Keying
// it off the reply is how the first version of this check passed against the
// defect: a preview in the wrong shape has no `status`, the check read that
// as "nothing written", and cheerfully asserted the very sentence that was
// wrong. An expectation derived from the thing under test tests nothing.
for (const ticker of Object.keys(state.__previews || {})) {
  const t = (state.securities.find((s) => s.ticker === ticker) || {})._thesis;
  if (!t) continue;
  if (t.status === "known") {
    must.push([`dlg:buy:${ticker}`, t.version.thesis || t.version.falsifier,
               "the purchase dialog shows the thesis it is about to freeze"]);
    mustNot.push([`dlg:buy:${ticker}`, "No thesis on record",
                  "the purchase dialog denies a thesis it was handed"]);
    if (t.version.reason) {
      mustNot.push([`dlg:buy:${ticker}`, t.version.reason,
                    "the amendment reason reads as the reason there is none"]);
    }
  } else {
    must.push([`dlg:buy:${ticker}`, "No thesis on record",
               "buying with nothing written says so"]);
  }
}
if (valued) {
  const v = valued._valuation;
  must.push([`detail:${valued.ticker}`, `Claimed ${v.made}`,
             "the standing valuation says the day it was claimed"]);
  if (v.history.length > 1) {
    must.push([`detail:${valued.ticker}`, "earlier claim",
               "a superseded valuation is still reachable"]);
  }
}
for (const s of state.securities) {
  for (const m of s._inputs || []) {
    if ((m.entered || {}).status === "known") {
      must.push([`dlg:values:${s.ticker}`, `Entered by you on ${m.entered.recorded}`,
                 "a hand-entered figure says the day it was entered"]);
    }
    if ((m.entries || []).length > 1) {
      must.push([`dlg:values:${s.ticker}`, "earlier entr",
                 "an earlier hand-entered figure is still readable"]);
    }
  }
  if ((s._inputs || []).length) {
    dlg(`dlg:values:${s.ticker}`, `dlgMetrics(find(${JSON.stringify(s.ticker)}))`);
  }
}

const held = state.securities.find((s) => s.bucket === "holdings");
if (held) {
  must.push([`detail:${held.ticker}`, "Lot history",
             "a holding shows the lots it was built from"]);
  for (const lot of (held._lots || []).concat(held._sales || [])) {
    must.push([`detail:${held.ticker}`, String(lot.date).slice(0, 10),
               `lot ${lot.id} appears in the history`]);
  }
}
// A closed position must offer the way back in. Refusing to record a
// re-purchase is the app declining to record something that happened, which
// is the one thing it must never do — and the refusal lived entirely here,
// in a gate on lot history rather than on shares held.
const closed = state.securities.filter((s) => s.bucket === "previous");
if (!closed.length) {
  gap("the harness built no closed position — the previous screen "
      + "renders against nothing and proves nothing");
} else {
  for (const s of closed) {
    must.push([`detail:${s.ticker}`, 'data-act="buy"',
               `a closed position (${s.ticker}) can be bought again`]);
    mustNot.push([`detail:${s.ticker}`, 'data-act="remove"',
                  `a closed position (${s.ticker}) is never deletable`]);
  }
  must.push(["previous", closed[0].ticker,
             "a closed holding reaches the previous table"]);
  must.push(["previous", "Overrides", "the scorecards render beside the list"]);
  // The host counts a group's purchases and, apart from that, how many of
  // them could be scored at all. Printing the average beside the group count
  // and dropping the scored count is how a partial population passes for the
  // whole — on the one panel meant to be able to indict a rule.
  must.push(["previous", "Scored",
             "an average says how many purchases it rests on"]);
  for (const bad of ["null%", "NaN%", "undefined%"]) {
    mustNot.push(["previous", bad,
                  `an absent average renders as "${bad}" instead of a dash`]);
  }
}
// A name held more than once: every period is its own row, the detail page
// groups the entries by holding, and no figure spanning them is unlabelled.
const twice = state.securities.filter((s) => (s._cycles || []).length > 1);
if (!twice.length) {
  gap("the harness built no security held more than once — the "
      + "grouping, the ordinals and the windowed since-exit are "
      + "unexercised");
}
for (const s of twice) {
  must.push([`detail:${s.ticker}`, "First holding",
             `${s.ticker}'s lot history is grouped by holding period`]);
  must.push([`detail:${s.ticker}`, "Second holding",
             `${s.ticker}'s second holding is named apart from the first`]);
  must.push([`detail:${s.ticker}`, "All holdings",
             `${s.ticker} names its lifetime figure as spanning both`]);
  for (const c of s._cycles.filter((x) => !x.open)) {
    must.push(["previous", `${c.opened}`,
               `${s.ticker}'s closed holding of ${c.opened} has its own row`]);
  }
  // The window that must not run to today once the name was bought back.
  const back = s._cycles.find((c) => c.since_exit
    && c.since_exit.until === "purchase");
  if (!back) {
    problems.push(`${s.ticker} was bought back but no period's since_exit `
                  + "closed at that purchase — the window still runs to today");
  }
  // Headings alone prove nothing: a group can carry the right title over an
  // empty list, which is exactly what happens if the payload's lot ids stop
  // matching the lots. Each period's own entries must be inside its own
  // group, so the page is checked section by section rather than as one
  // haystack that any entry anywhere satisfies.
  const page = String(out[`detail:${s.ticker}`] ?? "");
  // Everything above the lot history describes ONE holding, and Previous
  // holdings has a row per holding — so arriving from the older row must not
  // land on a page that silently describes a different one.
  const meta = (page.match(/<div class="meta">([^<]*)/) || [])[1] || "";
  if (!/holding/i.test(meta)) {
    problems.push(`detail:${s.ticker}: the header does not say which of `
                  + `${s._cycles.length} holdings the figures describe — "${meta.trim()}"`);
  }
  const groups = page.split('<div class="cyc">').slice(1);
  if (groups.length !== s._cycles.length) {
    problems.push(`detail:${s.ticker}: ${s._cycles.length} holdings but `
                  + `${groups.length} groups in the lot history`);
  }
  // rendered newest first, so the payload's periods reverse onto the groups
  s._cycles.slice().reverse().forEach((c, i) => {
    const g = groups[i] || "";
    for (const id of c.buys.concat(c.sells)) {
      const lot = (s._lots || []).concat(s._sales || []).find((l) => l.id === id);
      if (!lot) continue;
      if (!g.includes(`<time>${String(lot.date).slice(0, 10)}</time>`)) {
        problems.push(`detail:${s.ticker}: lot ${id} (${lot.date}) is missing `
                      + `from the "${c.open ? "open" : "closed " + c.closed}" `
                      + "holding it belongs to");
      }
    }
  });
}
/* Text that reaches the page through `esc` arrives HTML-escaped, so an
   apostrophe in a source's name is `&#39;` in the markup. Both readings
   count: the expectation is that the words are on screen, not which entity
   the escaper chose. */
const asMarkup = (v) => String(v).replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
for (const [screen, text, why] of must) {
  const html = String(out[screen] ?? "");
  if (!html.includes(text) && !html.includes(asMarkup(text))) {
    problems.push(`${screen}: ${why} — expected "${text}"`);
  }
}
for (const [screen, text, why] of mustNot) {
  if (String(out[screen] ?? "").includes(text)) {
    problems.push(`${screen}: ${why} — did not expect "${text}"`);
  }
}
// Nothing on any screen may name a strategy the view was not handed, or a
// setting one of them happens to declare. The view renders from
// declaration; a hardcoded id means a wrong turn.
const viewSource = fs.readFileSync(appPath, "utf8");
// A caution says what a number rests on; it is not a failure. Rendering it as
// a warning glyph puts a red flag on twelve of a company's twenty-nine
// measures, and a warning that fires that often is one nobody reads — which
// is the same outcome as dropping it. One vocabulary, in cautionLines(), and
// nothing else in the view gets to invent a louder one.
if (viewSource.includes("⚠")) {
  problems.push("app.js renders a warning glyph — a caution is a "
                + "qualification, not a failure, and every one of them goes "
                + "through cautionLines()");
}
for (const sid of ["graham", "buffett", "lynch", "discount-closure",
                   "contract-proof", "verdicts", "awkward",
                   "free-cash", "cash-floor", "patience"]) {
  if (viewSource.includes(`"${sid}"`) || viewSource.includes(`'${sid}'`)) {
    problems.push(`app.js names "${sid}" — the view layer must know nothing `
                  + "about which strategies or settings exist");
  }
}

if (problems.length) {
  console.log(problems.map((p) => "- " + p).join("\n"));
  process.exit(1);
}
console.log(Object.entries(out)
  .map(([k, v]) => `${k}: ${String(v ?? "").length}`).join("\n"));
