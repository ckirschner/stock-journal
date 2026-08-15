/* Render every screen and every margin pane against a real get_state
   payload, under Node with a stub DOM. Driven by tests/test_view_smoke.py,
   which builds the payload through the same Api the window calls.

   One smoke path, not a testing framework. What it catches: a key renamed
   on the Python side, an undefined dereference in a branch nobody clicked,
   a number rendering as NaN, a section silently disappearing — and, through
   the must/mustNot lists, the semantic guarantees the interface carries:
   absence renders with its reason, a caution is a mark and never a warning,
   an override asks for its sentence, recorded history stays readable and
   offers no actions from inside itself.

   Usage: node view_smoke.mjs <state.json> <ui/js dir> [mode]
   "coverage" (default) also insists the payload reached every surface the
   view draws; "render-only" keeps the real complaints and drops the gaps. */

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const [statePath, uiDir, mode] = process.argv.slice(2);
const DEMAND_COVERAGE = mode !== "render-only";
const state = JSON.parse(fs.readFileSync(statePath, "utf8"));

const els = {};
const mkEl = (id) => (els[id] ||= {
  id, innerHTML: "", textContent: "", className: "", dataset: {},
  querySelectorAll: () => [], querySelector: () => null,
  appendChild() {}, remove() {}, prepend() {}, insertBefore() {},
  focus() {}, setSelectionRange() {}, scrollIntoView() {},
  classList: { toggle() {}, add() {}, remove() {} },
  style: {}, value: "", checked: false, hidden: false, scrollTop: 0,
});
const ctx = vm.createContext({
  document: {
    getElementById: mkEl, querySelectorAll: () => [],
    createElement: () => mkEl("scratch"), addEventListener: () => {},
    body: { appendChild() {} },
  },
  window: { addEventListener: () => {}, scrollTo: () => {} },
  CSS: { escape: (s) => String(s) },
  setTimeout: () => {}, console,
  Number, String, Object, Array, Math, Date, JSON, Set, Map, RegExp,
  Intl, isNaN, parseInt, parseFloat,
});
const uiFiles = fs.readdirSync(uiDir).filter((x) => x.endsWith(".js")).sort();
let viewSource = "";
for (const f of uiFiles) {
  const src = fs.readFileSync(path.join(uiDir, f), "utf8");
  viewSource += src;
  vm.runInContext(src, ctx, { filename: f });
}
Object.assign(ctx, { __state: state });
const run = (code) => vm.runInContext(code, ctx);
run("S = __state;");
if (state.__timeframe && state.__timeframe.ok) {
  run('T = { ...__state.__timeframe, label: "Past month" };');
}
// A stub backend, serving replies the Python side captured from the real
// Api — the async surfaces render against real shapes or not at all.
run(`window.pywebview = { api: {
  preview_purchase: async (t) => (__state.__previews || {})[t]
    || { ok: false, error: "no preview captured for " + t },
  preview_sale: async (t, when) => (__state.__sale_previews || {})[t + "@" + when]
    || { ok: false, error: "no sale preview captured for " + t + " on " + when },
  preview_backfill: async () => __state.__backfill
    || { ok: false, error: "no backfill preview captured" },
  get_coverage: async (t) => (__state.__coverage || {})[t]
    || { ok: false, error: "no coverage captured for " + t },
  get_snapshot: async (t, seq) => (__state.__snapshots || {})[t + "@" + seq]
    || { ok: false, error: "no snapshot captured for " + t + " " + seq },
  get_bank: async () => __state.__bank || { ok: false, error: "no bank captured" },
  ev_prefill: async (t) => (__state.__ev || {})[t]
    || { ok: true, prefill: {}, references: {} },
  compare_snapshots: async (t, seqs) => (__state.__compare || {})[t]
    || { ok: false, error: "no comparison captured for " + t },
  timeframe_view: async () => __state.__timeframe
    || { ok: false, error: "no timeframe captured" },
} };`);
["view", "maststats", "tabs", "foot", "margin", "journalchip"].forEach(mkEl);
if (state.__bank && state.__bank.ok) run("C.bank = (__state.__bank.bank || {}).entries || [];");

const problems = [];
const gap = (...parts) => { if (DEMAND_COVERAGE) problems.push(parts.join("")); };
const out = {};

async function check(label, code) {
  try {
    let html = run(code);
    if (html && typeof html.then === "function") html = await html;
    if (typeof html === "string") {
      /* undefined, [object Object], NaN and a comment leaked into a template
         literal are all the same defect: the view read a key the backend
         does not send, and it prints instead of throwing.

         The measures screens are exempt from the `undefined` token alone:
         they print the bank's own misfires prose, which is entitled to say
         "makes the ratio undefined" in English. NaN, stringified objects
         and leaked comments stay fatal there too. */
      const lax = label.startsWith("measures");
      const m = html.match(lax
        ? /.{0,80}(\[object Object\]|\bNaN\b|\/\*).{0,80}/
        : /.{0,80}(undefined|\[object Object\]|\bNaN\b|\/\*).{0,80}/);
      if (m) problems.push(`${label}: rendered "${m[0].replace(/\s+/g, " ")}"`);
    }
    out[label] = html;
    return html;
  } catch (e) {
    problems.push(`${label}: threw ${e.name}: ${e.message}`);
    return "";
  }
}
const pane = (label, id, arg) =>
  check(label, `PANES[${JSON.stringify(id)}](${JSON.stringify(arg)})`);

// ---------------------------------------------------------------- screens
await check("mast", "renderMast(); renderTabs(); "
  + '$("maststats").innerHTML + $("journalchip").innerHTML');
for (const f of ["everything", "holdings", "watchlist", "track"]) {
  run(`filter = ${JSON.stringify(f)};`);
  await check(`list:${f}`, "listView()");
}
if (state.list) {
  run('filter = "yourlist";');
  await check("list:yourlist", "listView()");
  await check("list:yourlist:empty", `(() => {
    const was = S.list;
    S.list = { ...was, current: null, rows: [], history: [] };
    const h = listView(); S.list = was; return h; })()`);
  await check("list:yourlist:untracked", `(() => {
    const was = S.list;
    S.list = { ...was, rows: [{ ticker: "ZZZZ", name: null, tracked: false,
      held: false, new: true, decision: null, passed_over: null }] };
    const h = listView(); S.list = was; return h; })()`);
}
run('filter = "everything";');
await check("strategy", "strategyView()");
await check("measures", "measuresView()");
await check("measures:whole-bank", `(() => {
  showWholeBank = true; const h = measuresView(); showWholeBank = false; return h; })()`);
await check("data", "dataView()");
await check("analytics", "analyticsView()");
await check("welcome", "(() => { const j = S.journal; S.journal = null;"
  + " const h = welcomeView(); S.journal = j; return h; })()");
await check("missing-strategy",
  "(() => { const a = S.strategy, b = S.strategy_missing;"
  + " S.strategy = null; S.strategy_missing = S.journal.strategy;"
  + " const h = strategyView(); S.strategy = a; S.strategy_missing = b;"
  + " return h; })()");

// Detail per security, the coverage panel primed with its captured reply so
// the whole page renders rather than the loading placeholder.
const prime = (ticker) => {
  const cov = (state.__coverage || {})[ticker];
  run(`C.coverage = ${JSON.stringify(cov && cov.ok
    ? cov.coverage || { entries: [] } : { entries: [] })};`
    + ` C.coverageFor = ${JSON.stringify(ticker)}; C.loadingCoverage = false;`);
};
for (const s of state.securities) {
  const t = JSON.stringify(s.ticker);
  prime(s.ticker);
  run(`openTicker = ${t};`);
  await check(`detail:${s.ticker}`, `detailView(find(${t}))`);
  run("openTicker = null;");
}
/* The page describes ONE holding period, carried by the click. A page that
   draws the same thing whichever row you came from is the defect. */
for (const s of state.securities) {
  const cycles = s._cycles || [];
  if (cycles.length < 2) continue;
  const drawn = new Map();
  prime(s.ticker);
  for (const c of cycles) {
    const html = String(await check(
      `detail:${s.ticker}:period:${c.seq}`,
      `(() => { const was = openPeriodBuy;`
      + ` openTicker = ${JSON.stringify(s.ticker)};`
      + ` openPeriodBuy = ${JSON.stringify(c.buys[0])};`
      + ` const h = detailView(find(${JSON.stringify(s.ticker)}));`
      + ` openPeriodBuy = was; openTicker = null; return h; })()`));
    drawn.set(c.seq, html);
    const wants = c.open ? "Since buy" : "While held";
    if (html && !html.includes(wants)) {
      problems.push(`detail:${s.ticker}:period:${c.seq}: `
        + `${c.open ? "an open" : "a closed"} holding rendered without "${wants}"`);
    }
    if (html && !html.includes(c.open ? c.opened : c.closed)) {
      problems.push(`detail:${s.ticker}:period:${c.seq}: the page does not `
        + "name the day this holding " + (c.open ? "opened" : "closed"));
    }
  }
  const seen = [...drawn.values()].filter(Boolean);
  if (seen.length > 1 && new Set(seen).size === 1) {
    problems.push(`detail:${s.ticker}: every holding period renders the same `
      + "page, so the period the reader clicked is not reaching it");
  }
}

// ---------------------------------------------------------- margin panes
await pane("m:rest", "rest", null);
await pane("m:journal", "journal", {});
await pane("m:newjournal", "newjournal", {});
await pane("m:renamejournal", "renamejournal", {});
await pane("m:deletejournal", "deletejournal", {});
await pane("m:add", "add", {});
await pane("m:cash", "cash", {});
await pane("m:settings", "settings", {});
await pane("m:sources", "sources", {});
await pane("m:valdefaults", "valdefaults", {});
await pane("m:importdata", "importdata", {});
await pane("m:emptyjournal", "emptyjournal", {});
await pane("m:timeframe", "timeframe", {});
for (const which of ["value", "cash", "saying", "blind", "positions"]) {
  await pane(`m:acct:${which}`, "acct", { which });
}
if (state.list) {
  await pane("m:importlist", "importlist", {});
  await pane("m:passover", "passover", { t: "ZZZZ", name: "Zed Corp" });
}
for (const c of state.pending_changes || []) {
  await pane(`m:explain:${c.record}`, "explain", { record: c.record, seq: c.seq });
}
for (const v of (state.strategy || {}).values || []) {
  await pane(`m:declared:${v.id}`, "declared", { kind: "value", id: v.id });
}
for (const s of state.securities) {
  const t = s.ticker;
  await pane(`m:row:${t}`, "row", { t });
  await pane(`m:state:${t}`, "state", { t });
  await pane(`m:price:${t}`, "price", { t });
  await pane(`m:datastatus:${t}`, "datastatus", { t });
  await pane(`m:thesis:${t}`, "thesis", { t });
  await pane(`m:thesisedit:${t}`, "thesisedit", { t });
  await pane(`m:values:${t}`, "values", { t });
  await pane(`m:more:${t}`, "more", { t });
  await pane(`m:snapshot:${t}`, "snapshot", { t });
  await pane(`m:readings:${t}`, "readings", { t });
  await pane(`m:buy:${t}`, "buy", { t });
  await pane(`m:backfill:${t}`, "backfill", { t });
  for (const c of s._cycles || []) {
    if (!c.open) await pane(`m:row:${t}:${c.seq}`, "row", { t, period: c.seq });
  }
  for (const lot of (s._lots || []).concat(s._sales || [])) {
    await pane(`m:lot:${t}:${lot.id}`, "lot", { t, id: lot.id });
  }
  for (const j of s._judgements || []) {
    await pane(`m:judgement:${t}:${j.id}`, "judgement", { t, id: j.id });
  }
  for (const id of s._cited || []) {
    await pane(`m:measure:${t}:${id}`, "measure", { sid: id, t });
  }
  (s.notes || []).forEach((n, i) => pane(`m:note:${t}:${i}`, "note", { t, i }));
  for (const row of ((s._snapshots || {}).rows || [])) {
    if (!row.discarded) {
      await pane(`m:readings:${t}:${row.seq}`, "readings", { t, seq: row.seq });
      await pane(`m:discardsnap:${t}:${row.seq}`, "discardsnap", { t, seq: row.seq });
      break;
    }
  }
}
const holding = state.securities.find((s) => s.bucket === "holdings");
if (holding && state.__sale_previews) {
  const t = holding.ticker;
  const days = Object.keys(state.__sale_previews)
    .filter((k) => k.startsWith(t + "@")).map((k) => k.split("@")[1]).sort();
  const past = days[0], today = days[days.length - 1];
  await check("m:sell", `paneSell(${JSON.stringify(t)}, ${JSON.stringify(today)})`);
  await check("m:sell-from-history",
    `paneSell(${JSON.stringify(t)}, ${JSON.stringify(past)})`);
  // The preview not answering must not stop today's sale being recorded.
  run("__saved = __state.__sale_previews; __state.__sale_previews = {};");
  await check("m:sell-no-preview",
    `paneSell(${JSON.stringify(t)}, ${JSON.stringify(today)})`);
  run("__state.__sale_previews = __saved;");
}
if (state.__backfill) {
  await check("m:backfill-checked",
    `paneBackfill(${JSON.stringify(state.securities[0].ticker)},`
    + ` { rows: __state.__backfill_rows, recollection: "",`
    + ` preview: __state.__backfill })`);
}
const valued = state.securities.find(
  (s) => (s._valuation || {}).status === "known");
if (valued) await pane("m:ev", "ev", { t: valued.ticker });
const compared = Object.keys(state.__compare || {})
  .find((t) => state.__compare[t].ok);
if (compared) {
  await check("m:comparison",
    `comparisonHtml(${JSON.stringify(compared)},`
    + ` __state.__compare[${JSON.stringify(compared)}].comparison)`);
} else {
  gap("no snapshot comparison was captured, so the side-by-side rendering "
    + "is unexercised");
}

// A change row — its own subject kind, its own unit and sign rule: a
// distance between two readings always shows its sign, in every unit.
await check("evidence:change", `(() => {
  const s = S.securities[0];
  const row = (id, unit, value) => evidenceRow(s, {
    group: null,
    subject: {kind: "change", id, since: "first-purchase", unit,
              label: "Gross margin, change since you first bought",
              explain: "How far this has moved since the day this holding began."},
    observed: {status: "known", value, cautions: [], provenance: [
      "40 on 2024-02-01, frozen at that purchase and not worked out again, against 34 now"]},
    test: {phrase: "at least", threshold: -5, threshold_from:
           {kind: "value", id: "drift", label: "Worst fall you will add behind",
            unit}, absent: null},
    outcome: "fail"}, 0);
  return [row("gross_margin_ttm", "percentage_points", -6),
          row("gross_margin_ttm", "percentage_points", 2),
          row("current_ratio", "ratio", 0.2),
          row("current_ratio", "ratio", -1.1)].join("");
})()`);

// The gate arithmetic, exercised directly — the stub DOM's querySelectorAll
// returns nothing, so applyGates does nothing on any rendered form above.
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
      + `${JSON.stringify(answer)}): hidden=${got}, expected ${hidden} — ${why}`);
  }
}

// A qualified figure carries its qualification wherever the number renders:
// the ° mark holds the sentences on hover, the margin says them whole, and
// a pane where the figure is acted on says them inline.
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
  prime(stamped.ticker);
  run(`openTicker = ${JSON.stringify(stamped.ticker)};`);
  await check("qualified:detail", "detailView(__qs)");
  run("openTicker = null;");
  await check("qualified:values", "PANES.values({ t: __qs.ticker })");
  await check("qualified:measure",
    "PANES.measure({ sid: Object.keys(__qs._computed)[0], t: __qs.ticker })");
}

// ------------------------------------------------------- must / must not
const mustNot = [];
const must = [
  ["mast", state.journal.name, "the open journal is named in the chip"],
  ["mast", 'data-m="journal"', "the journal menu is reachable"],
  ["mast", "Something to say", "the header reports; it never demands"],
  ["strategy", state.journal.strategy.name, "the stamped strategy is named"],
  ["strategy", "Append-only: entries are never edited",
   "the change histories say what they are"],
  ["strategy", 'data-m="settings"', "the answers screen is reachable"],
  ["strategy", "read-only", "the thresholds say they cannot be edited here"],
  ["missing-strategy", "not installed", "a missing strategy says so"],
  ["welcome", "one strategy", "the empty state explains the commitment"],
  ["welcome", "exit", "existing holdings are framed as evaluated for exit"],
  ["welcome", "tiingo.com", "the setup wall links the way in"],
  ["data", "Back up", "export is reachable"],
  ["m:deletejournal", "Export it first",
   "the destructive pane offers the backup before the deletion"],
  ["m:deletejournal", "none of it can be recovered",
   "the destructive pane names the cost"],
  ["m:deletejournal", 'name="confirm_name"',
   "deletion is confirmed by typing the name, not a bare yes"],
  ["m:renamejournal", 'name="name"', "the rename pane asks for a name"],
  ["m:add", "Fetch its data now", "one added name auto-fetches by default"],
  ["evidence:change", "−6.0 pp", "a percent measure moves in points"],
  ["evidence:change", "+2.0 pp", "a rise shows its sign"],
  ["evidence:change", "+0.20", "a unit that does not sign itself is signed"],
  ["evidence:change", "change since you first bought",
   "the row says which purchase it measures from"],
];
mustNot.push(
  ["data", "Load sample", "the sample-journals button left the interface (§6.30)"],
  [`m:snapshot:${state.securities[0].ticker}`, 'type="date"',
   "a saved reading offers no date picker — today only, by design"]);
must.push([`m:snapshot:${state.securities[0].ticker}`, "no date field",
  "and says why not"]);

const fromHistory = state.securities.find((s) => s._backfilled);
if (fromHistory) {
  must.push(
    ["list:everything", "from history",
     "the list marks a position entered afterwards"],
    [`detail:${fromHistory.ticker}`, "from history",
     "the page says so before a single figure is read"]);
}
const declines = (state.strategy || {}).declines || [];
if (declines.length) {
  must.push(
    ["strategy", "What it will not evaluate",
     "the boundary exists on the strategy page before a verdict shows it"],
    ["strategy", declines[0].label, "and names the kind of company"],
    ["strategy", declines[0].because, "in the strategy's own words"]);
}
Object.values(state.render_types || {}).filter((t) => t.host_only)
  .forEach((t) => mustNot.push(["strategy", t.meaning,
    "a verdict only the host produces is not something this strategy "
    + "declined to have"]));
const outOfScope = state.securities.find(
  (s) => (s._decision || {}).render === "inapplicable");
if (outOfScope) {
  must.push(
    [`detail:${outOfScope.ticker}`, "Outside these rules",
     "a company these rules do not cover says so as a verdict"],
    [`m:state:${outOfScope.ticker}`, "Produced by the journal itself",
     "and the state gloss says the strategy did not produce it"]);
}
const industryOf = (s) => ((((((state.__coverage || {})[s.ticker] || {})
  .coverage || {}).status) || {}).industry || {}).industry || {};
const classified = state.securities.find(
  (s) => industryOf(s).status === "known");
const unclassified = state.securities.find(
  (s) => s._data && industryOf(s).status === "absent");
if (classified) {
  must.push([`m:datastatus:${classified.ticker}`, "The SEC classifies",
    "the data gloss reports the filer's kind"]);
}
if (unclassified) {
  must.push([`m:datastatus:${unclassified.ticker}`, "not established",
    "an unclassified filer says so rather than reading as ordinary"]);
}
const card = state.override_scorecard || {};
if ((card.unreconstructed || {}).n_purchases) {
  must.push(["analytics", "Could not be reconstructed",
    "the third population is reported apart, never folded in"]);
}
const capWord = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
if (((card.live || {}).override || {}).n_purchases
  && ((card.reconstructed || {}).override || {}).n_purchases) {
  // The cohort labels are the host's own words, read off the payload.
  must.push(["analytics", capWord(card.live.label), "the cohorts are labelled"],
    ["analytics", capWord(card.reconstructed.label), "both of them"]);
}
const noVerdict = state.securities.find(
  (s) => (s._lots || []).concat(s._sales || []).some((l) => l.unreconstructed));
if (noVerdict) {
  const lot = (noVerdict._lots || []).concat(noVerdict._sales || [])
    .find((l) => l.unreconstructed);
  must.push(
    [`detail:${noVerdict.ticker}`, "no verdict to rebuild",
     "an entry nothing could be rebuilt for says what kind of gap it is"],
    [`m:lot:${noVerdict.ticker}:${lot.id}`,
     "not</b> counted as acting against a signal",
     "and the record pane says it is not an override"]);
  mustNot.push([`m:lot:${noVerdict.ticker}:${lot.id}`, "Bought without a signal",
    "a gap in what can be reconstructed is not a decision"]);
}
const remembered = state.securities.find(
  (s) => (s._lots || []).concat(s._sales || []).some(
    (l) => ((l.snapshot || {}).recollection || {}).text));
if (remembered) {
  const lot = (remembered._lots || []).concat(remembered._sales || [])
    .find((l) => ((l.snapshot || {}).recollection || {}).text);
  must.push([`m:lot:${remembered.ticker}:${lot.id}`, "Written in hindsight",
    "a recollection is never presented as the case made at the time"]);
}
for (const s of state.securities) {
  const said = (s._sales || []).find((l) => (l.override || {}).reason
    && l.rule_triggered === false);
  if (!said) continue;
  must.push([`detail:${s.ticker}`, "against the signal",
    "a sale nobody's rule called for is named as one"],
    [`m:lot:${s.ticker}:${said.id}`, said.override.reason,
     "and carries the reason written at the time"]);
  break;
}
if (holding && state.__sale_previews) {
  must.push(
    ["m:sell-from-history", "not seen at the time",
     "a backdated sale says what it freezes was rebuilt"],
    ["m:sell-from-history", "you held", "the count belongs to the chosen day"],
    ["m:sell", "you hold", "a sale today says what is held today"],
    ["m:sell", "never prefilled", "the price field says why it is empty"],
    ["m:sell-no-preview", "Shares sold",
     "a preview that did not answer does not stop a sale being recorded"]);
  mustNot.push(["m:sell-from-history", "you hold ",
    "the live share count has no business on a backdated sale"]);
  for (const [key, reply] of Object.entries(state.__sale_previews)) {
    if (!reply.reason_owed) continue;
    const label = key.split("@")[1] < new Date().toISOString().slice(0, 10)
      ? "m:sell-from-history" : "m:sell";
    must.push([label, 'name="override_reason"',
      "a sale against the signal asks for a written reason"],
      [label, "goes against your own rules", "and says so plainly"]);
  }
}
if (state.__backfill) {
  const label = `m:backfill:${state.securities[0].ticker}`;
  must.push(
    [label, "Add a purchase", "the history form grows a row at a time"],
    [label, "Check these entries", "nothing is recorded before it is checked"],
    [label, "exit", "entered holdings are framed as evaluated for exit"],
    ["m:backfill-checked", "nothing recorded yet",
     "the checked form still says the record is untouched"],
    ["m:backfill-checked", "no verdict to rebuild — not an override",
     "the check names the rows that would record a gap"]);
}
if (valued) {
  const v = valued._valuation;
  must.push(["m:ev", "target price", "the no-target-price rule is stated"],
    ["m:ev", 'name="ev_method"', "the method is chosen, not implied"],
    ["m:ev", (v.claim || {}).made || "", "the standing claim says its day"]);
}
if (stamped) {
  must.push(["qualified:measure", `Qualified — ${QUAL}`,
    "the measure gloss says what the figure rests on"]);
  must.push(["qualified:values", `Qualified — ${QUAL}`,
    "the values pane says it inline, where the figure is acted on"]);
  if (stamped.cited) {
    must.push(["qualified:detail", QUAL,
      "a cited figure's qualification travels to the page on the mark"]);
    mustNot.push(["qualified:detail", "⚠",
      "a caution is never a warning glyph"]);
  }
}
for (const f of (state.strategy || {}).inputs || []) {
  if (f.answered_by === "host") {
    mustNot.push(["m:settings", `name="in_${f.id}"`,
      `"${f.id}" is worked out by the journal and must not be a field`]);
    must.push(["m:settings", f.label,
      `the derived figure "${f.id}" still shows`]);
    continue;
  }
  must.push(["m:settings", `name="in_${f.id}"`,
    `the declared input "${f.id}" reaches the answers form`]);
}
for (const v of (state.strategy || {}).values || []) {
  mustNot.push(["m:settings", `name="cfg_${v.id}"`,
    `the threshold "${v.id}" must not be editable in the app (§6.20)`]);
  must.push(["strategy", v.label, `the threshold "${v.id}" is readable`]);
  if (v.source && v.source.name) {
    must.push([`m:declared:${v.id}`, v.source.name,
      `"${v.id}" says where its number came from`]);
  }
}
const FIX_ANCHOR = { judgement: 'id="judgements"' };
for (const s of state.securities) {
  const fix = ((s._decision || {}).state || {}).fix;
  if (fix) {
    must.push([`detail:${s.ticker}`, `data-act="${fix}"`,
      `a blocked verdict offers the "${fix}" way out`]);
    if (FIX_ANCHOR[fix]) {
      must.push([`detail:${s.ticker}`, FIX_ANCHOR[fix],
        `the "${fix}" button has somewhere on this page to land`]);
    }
  }
}
const spoke = state.securities.some(
  (s) => (s._decision || {}).produced_by === "strategy");
let attributed = 0;
for (const s of state.securities) {
  for (const e of ((s._decision || {}).reason || {}).evidence || []) {
    if (!(e.test || {}).threshold_from) continue;
    attributed += 1;
    must.push([`detail:${s.ticker}`, `— your ${e.test.threshold_from.label}`,
      `${s.ticker}: the limit names the setting it was read from`]);
  }
}
if (spoke && !attributed) {
  gap("no verdict cites a limit by the setting it came from — "
    + "the attribution renders against nothing");
}
let headed = 0;
for (const s of state.securities) {
  for (const g of ((s._decision || {}).reason || {}).groups || []) {
    headed += 1;
    must.push([`detail:${s.ticker}`, g.name,
      `${s.ticker}: the "${g.name}" heading reaches the screen`]);
    if (g.tested) {
      must.push([`detail:${s.ticker}`, `${g.passed} of ${g.tested}`,
        `${s.ticker}: the rollup under "${g.name}" is on screen`]);
    }
  }
}
if (spoke && !headed) {
  gap("no verdict gathers its evidence under a heading — "
    + "the group rendering is unexercised");
}
const judged = state.securities.filter((s) => (s._judgements || []).length);
if (spoke && !judged.length) {
  gap("no security has a judgement to answer — the surface is unexercised");
}
let answered = 0, unanswered = 0, revised = 0;
for (const s of judged) {
  must.push([`detail:${s.ticker}`, "Questions only you can answer",
    `${s.ticker} shows the questions it was asked`]);
  for (const j of s._judgements) {
    must.push([`detail:${s.ticker}`, j.label, `${s.ticker}: "${j.id}" is named`]);
    must.push([`detail:${s.ticker}`, `data-jid="${j.id}"`,
      `${s.ticker}: "${j.id}" can be answered from the page`]);
    if (j.mark) {
      answered += 1;
      must.push([`m:judgement:${s.ticker}:${j.id}`, j.reasoning,
        `${s.ticker}: the reasoning behind "${j.id}" is readable`]);
    } else {
      unanswered += 1;
      mustNot.push([`detail:${s.ticker}`, "Failed",
        `${s.ticker}: an unassessed question reads as a failure`]);
    }
    if ((j.history || []).length > 1) {
      revised += 1;
      must.push([`m:judgement:${s.ticker}:${j.id}`, j.history[1].reasoning,
        `${s.ticker}: the earlier assessment of "${j.id}" survives`]);
    }
  }
}
for (const [n, what] of [[answered, "answered"], [unanswered, "unanswered"],
                         [revised, "revised"]]) {
  if (spoke && !n) gap(`no ${what} judgement in the payload — that rendering `
    + "is unexercised");
}
// Every scalar a decision's payload carries reaches the verdict card:
// esc(undefined) is the empty string, so a key read by the wrong name prints
// nothing at all, and "exit due" with no day is a scheduled exit gone silent.
for (const s of state.securities) {
  const decision = s._decision || {};
  const wanted = [];
  const walk = (node) => {
    if (node === null || node === undefined) return;
    if (typeof node === "object") { Object.values(node).forEach(walk); return; }
    if (typeof node === "boolean") return;
    if (typeof node === "number" || /^\d{4}-\d{2}-\d{2}$/.test(node)
        || String(node).includes(" ")) wanted.push(String(node));
  };
  walk(decision.payload);
  if (!wanted.length) continue;
  const html = String(run(`(() => { const was = openTicker;`
    + ` openTicker = ${JSON.stringify(s.ticker)};`
    + ` const h = verdictCard(find(${JSON.stringify(s.ticker)}),`
    + ` find(${JSON.stringify(s.ticker)})._decision);`
    + ` openTicker = was; return h; })()`));
  const escd = (v) => v.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
  for (const value of wanted) {
    if (!html.includes(value) && !html.includes(escd(value))) {
      problems.push(`detail:${s.ticker}: the ${decision.render} payload `
        + `carries ${JSON.stringify(value)} and the verdict card does not `
        + "say it");
    }
  }
}
// Recorded history offers no actions from inside itself.
for (const s of state.securities) {
  for (const lot of (s._lots || []).concat(s._sales || [])) {
    if (String(out[`m:lot:${s.ticker}:${lot.id}`] || "").includes("data-do=")) {
      problems.push(`m:lot:${s.ticker}:${lot.id}: recorded history offers an `
        + "action, and it is not something to act on from inside");
    }
  }
}
// Saved readings: rows, discards, and the unreadable refusal — all on the
// page, read off what was frozen.
const snapRows = (s) => ((s._snapshots || {}).rows || []);
const kept = state.securities.filter((s) => snapRows(s).length);
const unreadable = state.securities.filter((s) => (s._snapshots || {}).refusal);
if (!unreadable.length) {
  gap("no security carries a snapshot record this build cannot read — the "
    + "refusal rendering is never drawn");
}
for (const s of unreadable) {
  must.push([`detail:${s.ticker}`, s._snapshots.refusal,
    "an unreadable saved-days record says why, on the page"]);
}
if (!kept.length) gap("no security has a saved reading — the rows never draw");
if (!kept.some((s) => snapRows(s).some((r) => r.discarded))) {
  gap("no saved reading was discarded — the discarded row is never drawn");
}
for (const s of kept) {
  for (const row of snapRows(s)) {
    if (row.state) {
      must.push([`detail:${s.ticker}`, row.state,
        "a saved reading says what the verdict was"]);
    }
    must.push([`detail:${s.ticker}`, row.day,
      "a saved reading says which day it kept"]);
    if (row.discarded) {
      must.push([`detail:${s.ticker}`, `discarded ${row.discarded.day}`,
        "a discarded reading says so"]);
      if (row.discarded.reason) {
        must.push([`detail:${s.ticker}`, row.discarded.reason,
          "with the reason it was let go"]);
      }
    }
  }
}
// The thesis: standing text renders whole, amendment asks why, a first
// write does not, superseded versions survive.
const written = state.securities.find(
  (s) => ((s._thesis || {}).history || []).length);
const unwritten = state.securities.find(
  (s) => !((s._thesis || {}).history || []).length);
if (written) {
  const t = written._thesis;
  must.push([`m:thesis:${written.ticker}`, t.version.thesis,
    "the standing thesis renders whole"]);
  must.push([`m:thesisedit:${written.ticker}`, 'name="reason"',
    "amending asks what changed"]);
  must.push([`m:thesisedit:${written.ticker}`, "adds a new version",
    "and says the record appends"]);
  if (t.version.falsifier) {
    must.push([`m:thesisedit:${written.ticker}`, t.version.falsifier,
      "the amendment form carries the standing falsifier forward"]);
  }
  if (t.history.length > 1) {
    const prev = t.history[t.history.length - 1];
    must.push([`m:thesis:${written.ticker}`, prev.falsifier || prev.thesis,
      "a superseded version is still readable"]);
  }
  if (t.version.reason) {
    must.push([`m:thesis:${written.ticker}`, t.version.reason,
      "the reason for the standing amendment renders"]);
  }
}
if (unwritten) {
  mustNot.push([`m:thesisedit:${unwritten.ticker}`, 'name="reason"',
    "a first thesis is not asked why it changed"]);
}
// Hand-entered figures: the day they were entered, and the earlier entries.
for (const s of state.securities) {
  for (const m of s._inputs || []) {
    if ((m.entered || {}).status === "known") {
      must.push([`m:measure:${s.ticker}:${m.id}`, "typed",
        `${s.ticker}: a typed figure says it was typed`]);
      // The gloss is only captured for cited ids; enter one if needed.
      if (!(s._cited || []).includes(m.id)) {
        await pane(`m:measure:${s.ticker}:${m.id}`, "measure",
          { sid: m.id, t: s.ticker });
      }
    }
  }
}
// The buy pane, against real previews: the verdict is pinned on top, an
// override asks its sentence, and the thesis shape matches the page's.
for (const [ticker, reply] of Object.entries(state.__previews || {})) {
  if (!reply.ok) continue;
  const label = `m:buy:${ticker}`;
  const d = reply.decision || {};
  must.push([label, (d.state || {}).name,
    `${ticker}: today's verdict is in front of you`]);
  const commit = d.render === "commit";
  const cannotRebuild = reply.recorded_as === "unreconstructed";
  if (!commit && !cannotRebuild) {
    must.push([label, 'name="override_reason"',
      `${ticker}: a buy against the verdict asks for its sentence`]);
  } else {
    mustNot.push([label, 'name="override_reason"',
      `${ticker}: no sentence is owed where nothing said no`]);
  }
  const page = state.securities.find((x) => x.ticker === ticker) || {};
  const th = page._thesis || {};
  if ((reply.thesis || {}).status !== th.status) {
    problems.push(`${ticker}: the purchase preview and the page hold `
      + "different shapes for the same thesis");
  }
  if (th.status === "known") {
    must.push([label, th.version.thesis || th.version.falsifier,
      `${ticker}: the pane shows the thesis it is about to freeze`]);
    mustNot.push([label, "Nothing under \u201cWhy I own this\u201d is on record",
      `${ticker}: the pane denies a written case it was handed`]);
  } else {
    must.push([label, "is on record",
      `${ticker}: buying with nothing written says so`]);
  }
}
// A closed position can always be bought back, and its round trip has its
// own row under the track record.
const closed = state.securities.filter((s) => s.bucket === "previous");
if (!closed.length) {
  gap("the harness built no closed position — the track record renders "
    + "against nothing");
} else {
  for (const s of closed) {
    must.push([`detail:${s.ticker}`, "Buy it back",
      `a closed position (${s.ticker}) can be bought again`]);
    must.push([`m:more:${s.ticker}`, "unavailable",
      `a closed position (${s.ticker}) says why it cannot be removed`]);
  }
  must.push(["list:track", closed[0].ticker,
    "a closed holding reaches the track record"]);
  // Every reason a staged exit gave is on its row and its facts.
  let staged = 0;
  for (const s of closed) {
    for (const c of (s._cycles || []).filter((x) => !x.open && x.exit)) {
      if ((c.exit.sales || 0) < 2) continue;
      staged += 1;
      for (const r of c.exit.reasons || []) {
        const word = typeof r === "string" ? r : r.reason;
        must.push(["list:track", word,
          `${s.ticker}'s staged exit gave "${word}" and the row says so`]);
        must.push([`detail:${s.ticker}`, word,
          `and so does the page`]);
      }
    }
  }
  if (!staged) {
    gap("no holding closed in stages — the multi-reason row is unexercised");
  }
}
// A name held more than once: every closed period its own track row, the
// record grouped by holding, the windowed since-exit closed at re-purchase.
const twice = state.securities.filter((s) => (s._cycles || []).length > 1);
if (!twice.length) {
  gap("no security held more than once — the grouping, the ordinals and the "
    + "windowed since-exit are unexercised");
}
for (const s of twice) {
  must.push([`detail:${s.ticker}`, "holding ·",
    `${s.ticker}'s record is grouped by holding period`]);
  for (const c of s._cycles.filter((x) => !x.open)) {
    must.push(["list:track", c.opened,
      `${s.ticker}'s closed holding of ${c.opened} has its own row`]);
  }
  const back = s._cycles.find((c) => c.since_exit
    && c.since_exit.until === "purchase");
  if (!back) {
    problems.push(`${s.ticker} was bought back but no period's since_exit `
      + "closed at that purchase — the window still runs to today");
  }
}

// ------------------------------------------------------------- verdicts
const asMarkup = (v) => String(v).replace(/[&<>"']/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const flat = (t) => String(t ?? "").replace(/\s+/g, " ");
for (const [screen, text, why] of must) {
  const html = flat(out[screen]);
  if (!html.includes(flat(text)) && !html.includes(flat(asMarkup(text)))) {
    problems.push(`${screen}: ${why} — expected "${String(text).slice(0, 70)}"`);
  }
}
for (const [screen, text, why] of mustNot) {
  if (flat(out[screen]).includes(flat(text))) {
    problems.push(`${screen}: ${why} — did not expect "${String(text).slice(0, 70)}"`);
  }
}
// The banned words never appear in the view's own copy (§8). Checked in
// the SOURCE, not the rendered output: everything else on a screen is
// payload — strategy prose, the user's own notes, recorded vocabulary —
// which renders verbatim and is not the view's to rewrite (the engine-side
// renames are reported findings). Comments are stripped; identifiers
// (doThesis, _thesis, name="thesis", PANES.thesis) are excluded by the
// boundary classes, so what remains is words a reader would see.
{
  const code = viewSource.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  for (const word of ["thesis", "falsifier", "provenance"]) {
    const re = new RegExp(String.raw`(?<![A-Za-z_$.\/"'\-])${word}(?![A-Za-z_$:"])`, "gi");
    let m;
    while ((m = re.exec(code)) !== null) {
      problems.push(`banned word "${word}" in view copy: "…${code.slice(Math.max(0, m.index - 60), m.index + 60).replace(/\s+/g, " ")}…"`);
    }
  }
  for (const phrase of ["Need a look", "Nothing needs you"]) {
    if (code.includes(phrase)) {
      problems.push(`banned phrase "${phrase}" in view copy`);
    }
  }
}
// The view never names a strategy, a strategy's setting, or a warning glyph.
if (viewSource.includes("⚠")) {
  problems.push("ui/js renders a warning glyph — a caution is a "
    + "qualification, not a failure");
}
for (const sid of ["graham", "buffett", "lynch", "magic-formula",
                   "discount-closure", "contract-proof", "verdicts",
                   "awkward", "free-cash", "cash-floor", "patience"]) {
  if (viewSource.includes(`"${sid}"`) || viewSource.includes(`'${sid}'`)) {
    problems.push(`ui/js names "${sid}" — the view layer must know nothing `
      + "about which strategies or settings exist");
  }
}

if (problems.length) {
  console.log(problems.map((p) => "- " + p).join("\n"));
  process.exit(1);
}
console.log(Object.entries(out)
  .map(([k, v]) => `${k}: ${String(v ?? "").length}`).join("\n"));
