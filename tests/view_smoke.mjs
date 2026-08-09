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

const [statePath, appPath] = process.argv.slice(2);
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
["view", "maststats", "subtitle", "foot", "tabs"].forEach(mkEl);

const problems = [];
const out = {};

function check(label, code) {
  try {
    const html = run(code);
    if (typeof html === "string") {
      // A number that reached the screen as NaN, an object stringified into
      // the markup, or an undefined interpolation are all the same defect:
      // the view read a key the backend does not send.
      const m = html.match(/.{0,80}(undefined|\[object Object\]|\bNaN\b).{0,80}/);
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
  problems.push("no security in the payload has a computed value, so the "
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
// Only owed where a strategy actually spoke. A journal blocked on setup is
// the host saying it could not ask, and the host cites no limits at all —
// demanding one there would fail the very screen that state exists for.
const spoke = state.securities.some(
  (s) => (s._decision || {}).produced_by === "strategy");
if (spoke && !attributed) {
  problems.push("no verdict in the harness cites a limit by the setting it "
                + "came from — the attribution renders against nothing");
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
  problems.push("the harness built no closed position — the previous screen "
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
  problems.push("the harness built no security held more than once — the "
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
for (const [screen, text, why] of must) {
  if (!String(out[screen] ?? "").includes(text)) {
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
