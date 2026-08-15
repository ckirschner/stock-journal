/* Ledger · Nightdesk — core state and the helpers everything reads.

   The view renders what the backend serves and computes nothing substantive:
   every figure arrives known-or-absent, and an absent figure renders its
   reason, never a zero, never a bare dash where the host gave a sentence.
   No measure id, strategy id or state id is named anywhere in ui/ — the view
   sorts and colours by the host's render-type table and prints the words the
   payload carries. */

/* eslint-disable no-unused-vars */

let S = null;                 // last get_state payload
let T = null;                 // chosen-timeframe reply: {since, label, account, rows}
let tab = "list";             // list · strategy · measures · data · analytics
let filter = "everything";    // list filter: everything · holdings · watchlist · track · yourlist
let sortBy = "asks";          // asks · amount
let openTicker = null;
let openPeriodBuy = null;     // id of the purchase that opened the holding shown
let tipOpen = null;           // open in-place explainer key, at most one
let problemsFirst = true;     // evidence ordering toggle
let showWholeBank = false;    // measures screen escape hatch

/* Timeframe choices are offsets from today; "since a day you pick" goes
   through the same backend call. The label is what the header cell says. */
const TIMEFRAMES = [
  { id: "week",    label: "Past week",     days: 7 },
  { id: "month",   label: "Past month",    days: 30 },
  { id: "quarter", label: "Past 3 months", days: 91 },
  { id: "year",    label: "Past year",     days: 365 },
];
let timeframe = "month";

let C = {                     // lazy per-session caches
  bank: null, bankErr: null, loadingBank: false,
  coverage: null, coverageFor: null, loadingCoverage: false,
  snapEntry: null, snapFor: null,     // one opened snapshot record
};
let FETCH_POLLS = {};         // ticker -> true while a poll loop runs

function openSecurity(ticker, periodBuy = null) {
  openTicker = ticker;
  openPeriodBuy = periodBuy || null;
  tipOpen = null;
}
function closeSecurity() {
  openTicker = null;
  openPeriodBuy = null;
  tipOpen = null;
}

/* Render type -> state colour class. Keyed on the host's render types and
   nothing else; a strategy's states arrive already mapped. commit has its own
   colour — the loudest on the page and never confusable with a passing test. */
const RENDER_CLASS = {
  commit: "s-commit", reduce: "s-exit", close: "s-exit", hold: "s-hold",
  blocked: "s-blocked", unknown: "s-unknown", inapplicable: "s-scope",
};
const OUTCOME = {
  pass: ["meets it", "o-pass"],
  fail: ["misses it", "o-fail"],
  unknown: ["can’t say", "o-unknown"],
  noted: ["read", "o-noted"],
};

/* ------------------------------------------------------------------ utils */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* The bank's format strings: "0.0%", "0.00x", "$0,0", "+0.0 pp", "0 of 10",
   "+0,0 sh", "0 yrs", "0.00", "0". Parsed generically — no measure named. */
function fmtBank(v, format) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return esc(String(v));
  const m = /^(\+)?(\$)?0(,0)?(?:\.(0+))?(%|x)?(?:\s(.+))?$/.exec(format || "");
  if (!m) return String(n);
  const [, signed, dollar, thousands, decimals, symbol, suffix] = m;
  const digits = decimals ? decimals.length : 0;
  let s = thousands
    ? Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : Math.abs(n).toFixed(digits);
  if (dollar) s = "$" + s;
  s = (n < 0 ? "−" : (signed && n >= 0 ? "+" : "")) + s;
  if (symbol === "%") s += "%";
  if (symbol === "x") s += "×";
  if (suffix) s += " " + suffix;
  return s;
}

/* The contract's own unit list, for figures that are not bank measures — a
   declared setting, a host fact, something a strategy worked out itself. */
const num = (n, d) => Number(n).toLocaleString(undefined,
  { minimumFractionDigits: d, maximumFractionDigits: d });
const EV_UNIT = {
  percent: (n) => num(n, 1) + "%",
  percentage_points: (n) => (n >= 0 ? "+" : "−") + num(Math.abs(n), 1) + " pp",
  times: (n) => num(n, 2) + "×",
  times_own_median: (n) => num(n, 2) + "× its own median",
  ratio: (n) => num(n, 2),
  score: (n) => num(n, 2),
  usd: (n) => (n < 0 ? "−$" : "$") + num(Math.abs(n), 0),
  shares: (n) => num(n, 0) + " shares",
  years: (n) => num(n, 1) + " yrs",
  months: (n) => num(n, 0) + (Number(n) === 1 ? " month" : " months"),
  days: (n) => num(n, 0) + " days",
  count: (n) => num(n, 0),
  yes_no: (v) => (v ? "Yes" : "No"),
  date: (v) => String(v),
  text: (v) => String(v),
  none: (v) => String(v),
};
function fmtUnit(v, unit) {
  if (v === null || v === undefined) return "—";
  const f = EV_UNIT[unit];
  if (!f) return String(v);
  if (["yes_no", "date", "text", "none"].includes(unit)) return f(v);
  return Number.isFinite(Number(v)) ? f(Number(v)) : String(v);
}
/* A cited figure renders through the format the citation itself carries, so
   a decision frozen two years ago still reads the way it did that day. The
   bank standing today is consulted only for a record that predates the
   citation carrying its own format at all. */
function fmtSubject(subj, v) {
  const known = ["measure", "robustness"].includes(subj.kind);
  const f = !known ? null
    : subj.format !== undefined ? subj.format
    : (bankMeta(subj.id) || {}).format;
  if (f) return fmtBank(v, f);
  const out = fmtUnit(v, subj.unit);
  /* A distance between two readings always shows its sign — the bank's own
     format would render a six-point fall in a margin as "6.0%", which reads
     as the margin rather than as the move. */
  return (subj.kind === "change" && Number.isFinite(Number(v)) && Number(v) >= 0
    && !String(out).startsWith("+")) ? "+" + out : out;
}

const bankMeta = (id) => (S.bank_meta || {})[id] || null;
const labelOf = (id) => {
  const b = bankMeta(id);
  return b && b.label ? b.label : id;
};
const fmtMetric = (id, v) => {
  const b = bankMeta(id);
  return b ? fmtBank(v, b.format) : String(v);
};

const money = (n) => (n === null || n === undefined) ? "—" : "$" + Number(n).toFixed(2);
const money0 = (n) => (n === null || n === undefined) ? "—"
  : (n < 0 ? "−$" : "$") + Math.abs(Number(n)).toLocaleString(undefined,
      { maximumFractionDigits: 0 });
/* The user's own calendar date. toISOString() is UTC, which on an American
   evening is already tomorrow — a date the backend rightly refuses. */
const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const daysAgo = (n) => {
  const d = new Date(Date.now() - n * 86400000);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
/* Whole days between two YYYY-MM-DD strings (a minus b). The two-day margin
   used with it covers records written when stamps were UTC. */
const dayGap = (a, b) => Math.round((Date.parse(a) - Date.parse(b)) / 86400000);
function fmtCloseDate(d) {
  if (!d) return "";
  const s = String(d).slice(0, 10);
  return s.startsWith(String(new Date().getFullYear()) + "-") ? s.slice(5) : s;
}

/* A known-or-absent node, rendered. Absence carries its reason into a
   margin-openable marker rather than a tooltip nobody finds. */
function nodeVal(node, render) {
  if (!node || node.status !== "known") return null;
  return render ? render(node.value) : node.value;
}
const nodeWhy = (node) => (node && node.status !== "known" && node.reason) || "";

/* The caution mark: always °, hover shows the sentences, the click that
   opened the figure pins them in the margin. Never a warning glyph, never a
   colour — a caution is a number saying what it rests on, not a failure. */
const cmMark = (cs) => (cs || []).length
  ? `<span class="cm" title="${esc((cs || []).map((c) => "Qualified — " + c).join("\n"))}">°</span>` : "";

/* A return figure: signed, coloured by its own sign — the one place colour
   carries the figure's own state rather than a verdict's. */
function pctCell(r, key) {
  if (r === null || r === undefined) return '<span class="dim">—</span>';
  const node = (typeof r === "object") ? r : { status: "known", value: r };
  if (node.status !== "known") {
    return `<button class="dim" data-m="absent" data-arg="${escAttr({
      label: "This figure", reason: node.reason || "" })}">—</button>`;
  }
  const v = Number(node.value);
  return `<span class="num ${v >= 0 ? "pos" : "neg"}">${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}%</span>${cmMark(node.cautions)}`;
}

/* Margin-call encoding: data-m names a pane, data-arg carries its argument
   as JSON in an attribute. Everything user-visible inside stays escaped by
   the pane itself. */
const escAttr = (obj) => esc(JSON.stringify(obj));

function toast(msg, bad) {
  document.querySelectorAll(".toast").forEach((t) => t.remove());
  const el = document.createElement("div");
  el.className = "toast" + (bad ? " bad" : "");
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

async function api(method, ...args) {
  try {
    const r = await window.pywebview.api[method](...args);
    if (r && r.ok === false) { toast(r.error, true); return null; }
    return r;
  } catch (e) {
    toast("Could not reach the app backend: " + e, true);
    return null;
  }
}
/* Like api(), but failures come back inline for the pane that asked. */
async function apiRaw(method, ...args) {
  try {
    const r = await window.pywebview.api[method](...args);
    return r || { ok: false, error: "The backend returned nothing." };
  } catch (e) {
    return { ok: false, error: "Could not reach the app backend: " + e };
  }
}
async function refresh() {
  const r = await api("get_state");
  if (r) { S = r; render(); }
}
/* The timeframe reply, fetched beside the state. Absences render per row —
   a failure here never blanks the list. */
async function refreshTimeframe() {
  const spec = TIMEFRAMES.find((t) => t.id === timeframe) || TIMEFRAMES[1];
  const r = await apiRaw("timeframe_view", daysAgo(spec.days));
  T = r.ok ? { ...r, label: spec.label }
    : { label: spec.label, account: null, rows: {}, error: r.error };
  render();
}

const find = (t) => (S.securities || []).find((s) => s.ticker === t);
const inBucket = (b) => (S.securities || []).filter((s) => s.bucket === b);
const decisionOf = (s) => s._decision || null;
const renderOf = (d) => (d && d.render) || "unknown";
const renderSpec = (d) => (S.render_types || {})[renderOf(d)] || {};
const needsAttention = (d) => !!renderSpec(d).attention;
const stateClass = (d) => RENDER_CLASS[renderOf(d)] || "s-unknown";

/* A position is its lots. Nothing recomputes a total the backend derived. */
const buyLots = (s) => s._lots || [];
const sales = (s) => s._sales || [];
const reconstructed = (lot) =>
  (((lot || {}).snapshot || {}).evaluation || {}).basis === "reconstructed";
const RECON_CHIP = '<span class="chip" title="Entered from history. '
  + 'The verdict was rebuilt from the data available on the day this entry is '
  + 'dated, not seen at the time.">from history</span>';

const periods = (s) => s._cycles || [];
const openPeriod = (s) => periods(s).find((c) => c.open) || null;
const closedPeriods = (s) => periods(s).filter((c) => !c.open);
const subjectPeriod = (s) => (openPeriodBuy
  ? periods(s).find((c) => (c.buys || []).includes(openPeriodBuy))
  : null) || openPeriod(s) || closedPeriods(s).slice(-1)[0] || null;
const lotById = (s) => {
  const all = {};
  buyLots(s).concat(sales(s)).forEach((l) => { all[l.id] = l; });
  return all;
};
const periodLots = (s, c) => {
  const all = lotById(s);
  return { buys: (c.buys || []).map((i) => all[i]).filter(Boolean),
           sells: (c.sells || []).map((i) => all[i]).filter(Boolean) };
};
const ORDINALS = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth"];
const ordinal = (n) => ORDINALS[n] || `${n}th`;

/* Paragraphs, with the one markdown habit the declared prose actually uses:
   **emphasis** becomes bold. Applied after escaping, so nothing else in the
   text can become markup. */
const prose = (t) => !t ? "" : String(t).trim().split(/\n{2,}/)
  .map((p) => `<p>${esc(p).replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\n/g, " ")}</p>`).join("");
const oneline = (t) => esc(String(t == null ? "" : t).trim().replace(/\s+/g, " "));
const cap = (s) => String(s).charAt(0).toUpperCase() + String(s).slice(1);

/* What the strategy read for the journal, for the scoped measures screen:
   the union of everything any current decision cited plus anything with a
   typed history. A strategy declares no static list of what it may read —
   so this is honest about being what it HAS read here, not what it might. */
function citedInJournal() {
  const ids = new Set();
  (S.securities || []).forEach((s) => {
    (s._cited || []).forEach((id) => ids.add(id));
    (s._judgements || []).forEach((j) => ids.add(j.id));
    (s._inputs || []).forEach((r) => { if (r.cited) ids.add(r.id); });
  });
  return ids;
}

const storageWords = (st) => !st ? ""
  : typeof st === "string" ? st
  : `${st.kind === "os_keyring" ? "in the OS credential store" : "in a file"} (${st.where || ""})${st.unencrypted ? " — unencrypted: no credential store was available on this machine" : ""}`;

/* A declared source is {name, reasoning} on newer declarations and a plain
   string on older ones; the screen wants the name either way. */
const sourceName = (src) => !src ? "" : typeof src === "string" ? src : (src.name || "");
