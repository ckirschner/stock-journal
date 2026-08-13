/* The view layer knows nothing about which measures or strategies exist.
   Every verdict on every screen is one decision, produced by the strategy the
   open journal is stamped with and handed over as plain data: a state the
   strategy declared, a payload shaped by that state's render type, and a
   reason carrying the figures behind it. Adding a measure to the bank, or
   writing a whole new strategy, changes no code here. */

let S = null;                 // last state from Python
let tab = "holdings";
let openTicker = null;
let openPeriodBuy = null;     // id of the purchase that opened the holding shown
let tipOpen = null;

/* Which security page is open, and which of its holding periods the figures
   above the lot history describe. Written together because they are one fact:
   Previous holdings has a row per closed period, and clicking an older one
   used to land on a page whose facts strip described the most recent holding
   instead — the header named which, so nothing was ambiguous, but the click
   did not go where it looked like it should.

   Named by the id of the purchase that opened the period, which is the one
   thing about a period that is recorded rather than derived. `seq` renumbers
   when a backdated purchase merges two periods, and `opened` is not unique
   when a name is bought, closed and bought again on one day.

   The setter is what makes this hold. A second free-floating variable would
   be the procedural version — a stale period surviving a ticker change, and
   the first person to reach the same name through `opensec` from the
   allocation screen would see the wrong holding. One function writes both, so
   the period cannot outlive the ticker it was clicked with, and any caller
   that does not name one gets the ordinary default. */
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

const TABS = [
  ["holdings", "Current holdings"],
  ["previous", "Previous holdings"],
  ["ideas", "Ideas"],
  /* Where capital goes is its own screen, and it is the ONLY place a
     purchase into a name you already hold can be started. That is not a
     layout preference. Asked on a holding's own page, "should I buy more of
     this" is an averaging-down machine with an authority stamp on it —
     nobody opens a holding's page at random, they open it because it is
     down. Here the list is ordered by how far each position is from where
     its own strategy wants it, so the thing you already hold too much of is
     never what the screen suggests. */
  ["allocate", "Where capital goes"],
  /* Only for a journal whose strategy said it works from a list somebody
     else chose — see `shownTabs`. It is not a screen every journal gets a
     dimmed version of: a tab about a list, on a journal that screens for
     itself, is a permanent piece of furniture with nothing behind it. */
  ["list", "The list"],
  ["strategy", "Strategy"],
  ["metrics", "Metrics"],
  ["data", "Data"],
];
const BUCKETS = ["holdings", "previous", "ideas"];

/* Config pages keep their own lazy state. Selection lives in memory only,
   like the open tab — nothing is persisted browser-side. */
let C = {
  bank: null, bankErr: null, loadingBank: false,
  search: "",
  coverage: null, coverageFor: null, loadingCoverage: false,
};
let FETCH_POLLS = {};         // ticker -> true while a poll loop runs

/* ------------------------------------------------------------------ words */
/* Colour is semantic and never decorative, and every state carries its own
   text label besides — the label is the strategy's declared name for it, so
   colour is only ever the second signal. Keyed on the host's render types,
   which is the one permanent list; a strategy cannot add one.

   `inapplicable` is toneless on purpose, the same as `unknown`. It says these
   rules do not cover this kind of company, which is neither good news nor bad
   news about the company — colouring it either way would be this screen
   holding an opinion the host does not have. It is told apart from `unknown`
   by its words and by not asking for attention, never by a colour. */
const RENDER_TONE = {
  commit: "pass", hold: "pass", reduce: "watch",
  close: "fail", blocked: "watch", unknown: "none", inapplicable: "none",
};
const OUTCOME = {
  pass: ["meets it", "s-pass"],
  fail: ["misses it", "s-fail"],
  unknown: ["can't say", "s-none"],
  noted: ["read", "blank"],
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
   declared setting, a host fact, something a strategy worked out itself. A
   strategy picks the rendering from this list; it never invents one. */
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
/* A cited figure renders through its bank format where the bank has one, so
   a measure reads the same in a strategy's reason as it does anywhere else,
   and through the contract's unit list otherwise. */
function fmtSubject(subj, v) {
  const b = ["measure", "robustness"].includes(subj.kind)
    ? bankMeta(subj.id) : null;
  if (b && b.format) return fmtBank(v, b.format);
  const out = fmtUnit(v, subj.unit);
  /* A distance between two readings always shows its sign. The bank's format
     is deliberately not used for one — "0.0%" over a six-point fall in a
     margin renders "6.0%", which reads as the margin rather than as the move
     — and a rise of 0.2 in a ratio renders "0.20", which reads the same way.
     Some units sign themselves; the rest are signed here so no change row can
     be mistaken for the level it moved from. */
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
/* The user's own calendar date. toISOString() is UTC, which on an American
   evening is already tomorrow — a date the backend rightly refuses as the
   future. Dates the user acts on must be local. */
const localToday = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
/* Whole days between two YYYY-MM-DD strings (a minus b). Snapshot "frozen"
   stamps now carry the writer's own day, the same calendar a purchase date is
   on, so a gap here is a real gap. The two-day margin below stays because
   records written before that was true carry UTC stamps and can still read a
   day out — a claim about backdating has to hold for those too. */
const dayGap = (a, b) => Math.round((Date.parse(a) - Date.parse(b)) / 86400000);
/* Effective price: hand-entered wins; otherwise the newest fetched close.
   The source and date travel with it so a stale quote is visibly stale. */
const px = (s) => (s._price && s._price.value != null) ? s._price.value : s.price;
function fmtCloseDate(d) {
  if (!d) return "";
  const s = String(d).slice(0, 10);
  return s.startsWith(String(new Date().getFullYear()) + "-") ? s.slice(5) : s;
}
function priceCell(s) {
  const p = s._price;
  /* A dash with the host's reason behind it. "No close is stored for BRK.B —
     prices are held for BRK.A, another share class of the same company" is a
     different fact from "nothing has been fetched", and a bare dash makes
     them look identical in the one column where it matters. */
  if (!p || p.value == null) {
    return (p && p.reason)
      ? `<span class="dim" title="${esc(p.reason)}">—</span>` : money(null);
  }
  /* A series that has ENDED is not a stale price, it is not a price. The
     word says so — never colour alone, and never a bare number that a
     novice reads as what the security trades at today. */
  if (p.terminal)
    return `${money(p.value)} <span class="ended" title="${esc(
      "This price series has ended (" + (p.terminal.reason || "no reason recorded")
      + "). This is the last close it ever had, not what it trades at.")}">· ended</span>`;
  if (p.source === "fetched")
    return `${money(p.value)} <span class="dim" title="Fetched close, as of ${esc(p.date)}">·${esc(fmtCloseDate(p.date))}</span>`;
  /* Hand-entered, and the one value in the journal with no date on it. The
     host says why; the column says that it is undated at all, because a bare
     number beside dated ones reads as the freshest of them. */
  return `${money(p.value)} <span class="dim" title="${esc(
    p.undated || "Entered by hand; it carries no date.")}">·typed</span>`;
}
function dataFact(s) {
  if (s._fetch && s._fetch.running) return "fetching…";
  const d = s._data;
  if (!d) return "never fetched";
  /* The host contains a broken data layer rather than crashing, and hands
     the sentence over. Reading counts off that object would print
     "undefined filings · fetched never" — a confident, wrong answer where
     the honest one was already available. */
  if (d.error) return d.error;
  const when = d.last_fetch ? String(d.last_fetch.at).slice(0, 10) : "never";
  return `${d.filings_held} filings · fetched ${when}`;
}
/* A return, or a dash carrying the host's own reason for there not being one.
   Returns arrive as {status, value} or {status, reason} like every other host
   figure — they used to be a bare number-or-null, and five different facts
   came back as the same null: nobody has fetched a price, the figure on
   record is not a price, this purchase was recorded at $0.00, one purchase of
   several was, the security was never bought. Those have different fixes, so
   a single silent em-dash was the wrong answer to all of them. */
function pctVal(r) {
  if (r === null || r === undefined) return null;
  if (typeof r === "object") return r.status === "known" ? r.value : null;
  return r;
}
function pctWhy(r) {
  return (r && typeof r === "object" && r.status === "absent") ? r.reason : "";
}
function pctCell(r) {
  const v = pctVal(r);
  if (v === null || v === undefined) {
    const why = pctWhy(r);
    return why ? `<span class="dim" title="${esc("Not known: " + why)}">—</span>`
      : '<span class="dim">—</span>';
  }
  return `<span class="${v >= 0 ? "pos" : "neg"}">${v >= 0 ? "+" : ""}${Number(v).toFixed(1)}%</span>`;
}

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
/* Like api(), but failures come back as text for the page instead of a
   toast: a configuration problem must be readable where it happened. */
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

const inBucket = (b) => (S.securities || []).filter((s) => s.bucket === b);
const find = (t) => (S.securities || []).find((s) => s.ticker === t);
const decisionOf = (s) => s._decision || null;
const renderOf = (d) => (d && d.render) || "unknown";
const needsAttention = (d) =>
  !!(d && (S.render_types || {})[d.render] || {}).attention;

/* A position is its lots. Everything below reads them; nothing recomputes a
   total the backend already derived, because two answers to "how many
   shares" is one answer too many. */
const buyLots = (s) => s._lots || [];
const sales = (s) => s._sales || [];
const overrideLots = (s) => buyLots(s).filter((l) => l.override);

/* Whether an entry's verdict was seen on the day it is dated or rebuilt for
   that day afterwards. One reader, here, because the answer is written in one
   place on the record and a screen working it out for itself is a second copy
   of the rule — and this is the rule that decides whether a reconstruction
   can be shown as a contemporaneous record. Whether the SECURITY has any such
   entry is the engine's answer, on `_backfilled`; this is the per-entry one. */
const reconstructed = (lot) =>
  (((lot || {}).snapshot || {}).evaluation || {}).basis === "reconstructed";
/* The label, once. Every place a backfilled entry appears says the same word
   in the same shape, so a reader learns it once. Never colour alone. */
const RECON_CHIP = '<span class="chip s-recon" title="Entered from history. '
  + 'The verdict was rebuilt from the data available on the day this entry is '
  + 'dated, not seen at the time.">from history</span>';

/* A security is not held once. It is bought, closed, and — when the strategy
   says so again — bought back, and each of those is its own round trip with
   its own answer to "how did that go". The backend derives the periods from
   the lots; nothing here recomputes a boundary, and nothing here asks a
   per-period question of the security as a whole. */
const periods = (s) => s._cycles || [];
const openPeriod = (s) => periods(s).find((c) => c.open) || null;
const closedPeriods = (s) => periods(s).filter((c) => !c.open);
/* Which holding period this page's figures are about: the one clicked in from,
   else the one still open, else the one that ended most recently.

   Resolved against THIS security's own periods, so an id belonging to another
   name selects nothing and falls through to the default rather than describing
   somebody else's holding. That is the half of the guarantee the setter cannot
   give: `openSecurity` stops a period outliving its ticker, and this stops one
   that does not belong from being believed. */
const subjectPeriod = (s) => (openPeriodBuy
  && periods(s).find((c) => c.buys[0] === openPeriodBuy))
  || openPeriod(s) || closedPeriods(s).slice(-1)[0] || null;
const lotById = (s) => {
  const m = {};
  buyLots(s).concat(sales(s)).forEach((l) => { m[l.id] = l; });
  return m;
};
const periodLots = (s, c) => {
  const by = lotById(s);
  return c.buys.concat(c.sells).map((id) => by[id]).filter(Boolean)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)) || (a.seq - b.seq));
};
/* Every closed period in the journal, newest first — the unit the Previous
   holdings tab is about. A name held twice closed twice, and one row
   covering both would describe neither. */
const allClosedPeriods = () => (S.securities || [])
  .flatMap((s) => closedPeriods(s).map((c) => ({ s, c })))
  .sort((a, b) => String(b.c.closed).localeCompare(String(a.c.closed)));

const ORDINALS = ["", "First", "Second", "Third", "Fourth", "Fifth", "Sixth"];
/* Words while there are words, then digits with the right suffix. "21th" is
   the kind of small wrongness that makes a reader trust the numbers less. */
const ordinal = (n) => ORDINALS[n]
  || `${n}${["th", "st", "nd", "rd"][(n % 100 - n % 10 !== 10) && n % 10 < 4 ? n % 10 : 0]}`;
/* Named only where it disambiguates. One holding needs no ordinal, and
   adding one everywhere would spend legibility to say nothing. */
const periodName = (s, c) =>
  periods(s).length > 1 ? `${ordinal(c.seq)} holding` : "Holding";

const lotCount = (s) => {
  /* Lots you still hold shares from — not lots this ticker ever had, and not
     ones a trim has already emptied. Either of those reads on a holdings row
     as shares you own. */
  const n = buyLots(s).filter((l) => l.open).length;
  return n > 1 ? ` <span class="dim">· ${n} lots</span>` : "";
};

/* ---------------------------------------------------------------- chrome */
function renderMast() {
  const j = S.journal;
  const h = inBucket("holdings");
  /* A holding without a price must never enter these sums as zero — that
     would render a confident, wrong loss in the most prominent numbers in
     the app. Absence propagates: any unpriced holding makes the totals
     honestly unknown. */
  const unpriced = h.filter((s) => px(s) == null).length;
  const mv = h.reduce((a, s) => a + (px(s) || 0) * (s._shares || 0), 0);
  const cb = h.reduce((a, s) => a + (s._cost_basis || 0) * (s._shares || 0), 0);
  const mvTxt = unpriced ? "—" : "$" + mv.toLocaleString(undefined, { maximumFractionDigits: 0 });
  const unrealTxt = (unpriced || !cb) ? "—" : (mv >= cb ? "+" : "") + ((mv / cb - 1) * 100).toFixed(1) + "%";
  const unpricedNote = unpriced ? ` title="${unpriced} of ${h.length} position${h.length === 1 ? "" : "s"} ha${unpriced === 1 ? "s" : "ve"} no price — fetch data or enter one"` : "";
  const attention = h.filter((s) => needsAttention(decisionOf(s))).length;
  $("maststats").innerHTML = (!j || !h.length) ? "" :
    `<div><i>Market value${unpriced ? ` · ${unpriced} unpriced` : ""}</i><b${unpricedNote}>${mvTxt}</b></div>
     <div><i>Unrealised</i><b class="${unpriced || !cb ? "" : mv >= cb ? "pos" : "neg"}"${unpricedNote}>${unrealTxt}</b></div>
     <div><i>Positions</i><b>${h.length}</b></div>
     <div><i>Need a look</i><b class="${attention ? "neg" : ""}" title="Positions whose state asks something of you">${attention}</b></div>`;
  $("subtitle").textContent = j
    ? `${j.name} · ${(j.strategy || {}).name || "no strategy"}`
    : "Portfolio journal";
  $("foot").innerHTML = `This tool never places a trade and holds no broker credentials. `
    + `A journal has one strategy, chosen when it is created.<br>Data stored at ${esc(S.data_dir)}, never inside the project folder.`;
}
/* Which tabs this journal has. The only conditional one is the list, and the
   condition is read off the journal's own payload rather than off which
   strategy is running — the view never learns that a strategy called
   "magic-formula" exists, exactly as it never learns which measures do. */
const shownTabs = () => TABS.filter(([id]) => id !== "list" || !!S.list);

function renderTabs() {
  if (!S.journal) { $("tabs").innerHTML = ""; return; }
  /* Switching to a journal whose strategy screens for itself takes the list
     tab away underneath whoever was standing on it. Without this they are
     left on a tab with no button, and render() falls through to the holdings
     table with a heading for a bucket that does not exist. */
  if (!shownTabs().some(([id]) => id === tab)) tab = "holdings";
  $("tabs").innerHTML = shownTabs().map(([id, label]) => {
    /* Previous holdings counts closed periods, not securities: a name held
       and closed twice is two things that happened, and counting it once
       hides the second. The other two count securities, because a security
       is either held now or it is not. */
    /* The allocation count is what may take capital NOW — not what is
       waiting on a condition and not what was turned down. A tab badge is
       read at a glance and has one number's worth of room, so it has to be
       the number somebody would act on. */
    const n = id === "previous" ? `<em>${allClosedPeriods().length}</em>`
      : id === "allocate" ? (S.allocation
        ? `<em>${(S.allocation.ready || []).length}</em>`
        /* Not a zero. "Nothing may take capital" and "the strategy could
           not be asked" are different facts, and a badge reading 0 for the
           second says the discipline is working when nothing ran. */
        : '<em title="This journal\'s strategy could not be asked">—</em>')
      /* Names on the current list this journal is not holding. Not the
         list's length, which stays the same all year and tells nobody
         anything, and an em-dash rather than a nought where no list has been
         imported, because "nothing left to buy" and "no list yet" are
         opposite situations.
         A name passed over is still counted, deliberately: the verdict on it
         has not changed and the strategy still says to buy it. Deducting it
         here would make a badge that quietly agreed with the user against
         their own rules, which is the one thing this program will not do. */
      : id === "list" ? (S.list && S.list.current
        ? `<em>${(S.list.rows || []).filter((r) => !r.held).length}</em>`
        : '<em title="No list has been imported yet">—</em>')
      : BUCKETS.includes(id) ? `<em>${inBucket(id).length}</em>` : "";
    return `<button class="tab" role="tab" aria-selected="${tab === id}" data-tab="${id}">${label}${n}</button>`;
  }).join("");
}

function journalBar() {
  const j = S.journal;
  const others = (S.journals || []).filter((x) => x.id !== (j && j.id));
  return `<div class="jbar">
    <span class="lenslabel">Journal</span>
    <span class="seg">${(S.journals || []).map((x) => `<button type="button"
      data-journal="${esc(x.id)}" aria-pressed="${j && x.id === j.id}"
      ${x.problem ? `disabled title="${esc(x.problem)}"` : ""}>${esc(x.name)}</button>`).join("")}</span>
    <button class="btn" data-act="newjournal">New journal</button>
    ${j ? `<button class="btn" data-act="renamejournal">Rename</button>
    <button class="btn danger" data-act="deletejournal">Delete</button>` : ""}
    ${others.length ? "" : '<span class="dim">One strategy per journal. A second strategy means a second journal.</span>'}
  </div>`;
}

/* Renaming touches the name and nothing else. The journal's id is its
   address on disk and never moves — which is why a journal renamed six times
   still opens, still exports and still stamps the same way. Nothing recorded
   is affected, so this owes no reason and goes on no change record: a name
   is not a rule. */
function dlgRenameJournal() {
  const j = S.journal;
  if (!j) return;
  dialog({
    title: "Rename this journal",
    blurb: "Only the name changes. Everything recorded in it, and the folder "
      + "it lives in, stay exactly where they are.",
    body: field("name", "Name", j.name, "What you want to see in the journal "
      + "switcher. Four journals with the same name is the problem this "
      + "solves — give them names you can tell apart."),
    confirm: "Rename",
    onConfirm: async (d) => {
      if (!String(d.name || "").trim()) return "A journal needs a name.";
      /* apiRaw, not api: a refusal has to land in the dialog the user is
         looking at. Through api() it becomes a toast that fades in four
         seconds while the dialog closes as though the rename had worked,
         and the switcher still showing the old name is the only clue. */
      const r = await apiRaw("rename_journal", j.id, d.name);
      if (!r.ok) return r.error;
    },
  });
}

/* The one destructive action in the program, and the dialog says exactly
   what goes with it rather than asking "are you sure".

   Two things stand in front of it: an export offered first, because the
   record is nowhere else — principle 11 keeps a journal out of the
   repository, so there is no copy in version control to fall back on — and
   the journal's name typed out, checked on the backend rather than here. A
   confirmation the browser could skip is not a confirmation the record
   has. */
function dlgDeleteJournal() {
  const j = S.journal;
  if (!j) return;
  const listed = (S.journals || []).find((x) => x.id === j.id) || {};
  const counts = listed.securities
    ? `${listed.securities} securit${listed.securities === 1 ? "y" : "ies"}`
      + (listed.holdings ? `, ${listed.holdings} of them held` : "")
      + ", along with everything each of them has on record"
    : "Nothing has been recorded in it yet";
  dialog({
    title: `Delete "${j.name}"`,
    blurb: "This removes every position, every note, every recorded decision "
      + "and the whole rule-change history in this journal. Nothing else "
      + "holds a copy and none of it can be recovered.",
    body: `<div class="notice"><h4>What goes</h4>
      <p>${esc(counts)}. Other journals are untouched.</p></div>
      <div class="notice quiet"><h4>Export it first</h4>
      <p>Backing up on the Data tab writes the whole journal to a file you
      choose. It takes a moment and it is the only thing that makes this
      reversible.</p></div>
      ${field("confirm_name", "Type the journal's name to confirm", "",
        `Exactly as it reads: ${j.name}`)}`,
    confirm: "Delete this journal",
    danger: true,
    onConfirm: async (d) => {
      const r = await apiRaw("delete_journal", j.id, d.confirm_name || "");
      if (!r.ok) return r.error;
      closeSecurity(); tab = "holdings";
    },
  });
}

const cfgErrorBox = (errs) => !errs.length ? "" :
  `<div class="notice"><h4>Configuration problem</h4>
   ${errs.map((e) => `<p>${esc(e)}</p>`).join("")}</div>`;

/* One side of a change is empty when the strategy gained or dropped the
   setting entirely. That is not a value, and it never renders as one — a
   literal "null" on screen reads as a number somebody chose. */
const movedLine = (m) =>
  m.from === null || m.from === undefined
    ? `${m.label}: now ${m.to} — the strategy did not have this setting before`
    : m.to === null || m.to === undefined
    ? `${m.label}: was ${m.from} — the strategy no longer has this setting`
    : `${m.label}: ${m.from} → ${m.to}`;

/* A change to what the strategy demands is already on the record. What is
   still owed is the reason — and only where the user is the one who moved a
   number. An author's new version already says what changed. */
function pendingBanner() {
  const pend = S.pending_changes || [];
  if (!pend.length) return "";
  return `<div class="pending"><h4>Rule changes without a written reason</h4>
    ${pend.map((c) => `<div class="pendrow">
      <b>Change ${c.seq} · ${esc(String(c.seen).slice(0, 10))}</b>
      <ul>${(c.moved || []).map((m) => `<li>${esc(movedLine(m))}</li>`).join("")}</ul>
      ${(c.notes || []).map((n) => `<p class="hint">${esc(n)}</p>`).join("")}
      <button class="btn" data-act="explain" data-seq="${c.seq}">Write the reason</button>
    </div>`).join("")}
    <p class="hint" style="margin-top:10px">The change itself is recorded either way — timestamped, with the
    numbers that moved. The reason is the part only you can supply, and it is written once.</p></div>`;
}

function missingStrategyBanner() {
  if (!S.strategy_missing) return "";
  const m = S.strategy_missing;
  return `<div class="notice"><h4>${esc(m.name || m.id)} is not installed here</h4>
    <p>This journal is stamped with it, so everything already recorded stays readable exactly as written —
    but no new verdict can be produced until the strategy is back on this machine. Install it and the
    journal picks up where it left off, including anything its rules changed while it was away.</p></div>`;
}

/* ----------------------------------------------------------------- lists */
function stateStamp(d, big) {
  if (!d) return `<span class="stamp${big ? " big" : ""} v-none">—</span>`;
  const tone = RENDER_TONE[renderOf(d)] || "none";
  return `<span class="stamp${big ? " big" : ""} v-${tone}"
    title="${esc((d.state || {}).description || "")}">${esc((d.state || {}).name || "—")}</span>`;
}

/* What happened after a sale, with the window it rests on named. "Up 40%
   since you sold" and "up 40% between selling and buying again" are different
   claims, and only one of them is true once the user went back in. */
/* Every reason given across the sales that closed a period, each carrying
   the share of the exit it accounts for. A position trimmed on a risk limit
   and closed on a broken thesis gave two answers and both are true; the card
   used to print the last one and drop the rest. */
function exitReasonChips(x) {
  const rs = (x && x.reasons) || [];
  if (!rs.length) return '<span class="dim">—</span>';
  return rs.map((r) => `<span class="chip s-none"${rs.length > 1
    ? ` title="${esc(`${r.reason} — ${r.shares} of ${x.shares} shares, ${r.share}% of the exit`)}"` : ""
    }>${esc(r.reason)}${rs.length > 1 ? ` <span class="dim">${r.share}%</span>` : ""}</span>`).join(" ");
}

function sinceExitCell(x) {
  if (!x) return '<span class="dim">—</span>';
  if (x.pct === null || x.pct === undefined)
    return `<span class="dim" title="${esc(x.reason || "")}">—</span>`;
  return x.until === "purchase"
    ? `${pctCell(x.pct)} <span class="dim" title="Measured to the ${esc(x.date)} purchase, not to today — once you owned it again, the move was yours rather than evidence about the sale.">·&nbsp;to&nbsp;next&nbsp;buy</span>`
    : pctCell(x.pct);
}

function listView() {
  const rows = tab === "previous" ? allClosedPeriods() : inBucket(tab);
  const addBtn = tab === "previous" ? ""
    : `<button class="btn primary" data-act="add">${tab === "ideas" ? "Add a candidate" : "Add a security"}</button>`;
  let html = missingStrategyBanner() + pendingBanner();
  html += `<div class="toolbar" style="justify-content:space-between;align-items:center">
    ${journalBar()}<div>${addBtn}</div></div>`;

  if (!rows.length) {
    const msg = {
      holdings: "No open positions. Add a security, then record a purchase — the strategy tells you what it makes of it first.",
      previous: "Nothing closed yet. When you exit a position it stays here so you can see what happened next — and it stays buyable, so coming back to a name is one more entry.",
      ideas: "No candidates yet. Add one and the strategy will tell you where it stands.",
    }[tab];
    html += `<div class="sheet"><div class="empty"><p>${msg}</p>
      ${tab !== "previous" ? '<button class="btn primary" data-act="add">Add a security</button>' : ""}</div></div>`;
    /* An empty list is not a reason to withhold the analytics. They summarise
       every purchase and sale in the journal, and hiding them because this
       one list has no rows is how a re-purchase used to make a whole
       journal's evidence disappear. */
    return html + (tab === "previous" ? scorecards() : "");
  }

  /* Sorted by the host's own render order, so whatever asks most of you sits
     at the top. The view never learns which states exist. */
  const order = (s) => ((S.render_types || {})[renderOf(decisionOf(s))] || {}).order ?? 9;

  let head, body;
  if (tab === "holdings") {
    const sorted = rows.slice().sort((a, b) => order(a) - order(b));
    head = '<th class="l">Position</th><th>Price</th><th>Avg cost</th><th>Since buy</th><th>State</th>';
    body = sorted.map((s) => `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
      ${(openPeriod(s) ? periodLots(s, openPeriod(s)) : []).some((l) => l.override) ? '<span class="flagdot" title="This position holds shares bought against or without the signal"></span>' : ""}
      ${s._backfilled ? RECON_CHIP : ""}
      <div class="coname">${esc(s.name)}${lotCount(s)}</div></td>
      <td>${priceCell(s)}</td><td class="dim">${money(s._cost_basis)}</td>
      <td title="What the position you hold now has returned. An earlier holding of the same name is its own row under Previous holdings.">${pctCell(s._return)}</td>
      <td>${stateStamp(decisionOf(s))}</td></tr>`).join("");
  } else if (tab === "previous") {
    /* One row per closed holding period, newest first. A name held twice is
       two round trips, and one row averaging them would describe neither. */
    head = '<th class="l">Holding</th><th>Return held</th><th>Since exit</th><th class="hide-sm">Exit reason</th><th>Today</th>';
    body = rows.map(({ s, c }) => `<tr data-t="${s.ticker}" data-p="${esc(c.buys[0])}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
        ${openPeriod(s) ? '<span class="chip s-none" title="This name is held again — the open position is under Current holdings.">held again</span>' : ""}
        ${periodLots(s, c).some(reconstructed) ? RECON_CHIP : ""}
        <div class="coname">${esc(s.name)}</div>
        <div class="dim">${periods(s).length > 1 ? esc(periodName(s, c)) + " · " : ""}${esc(c.opened)} → ${esc(c.closed)}</div></td>
        <td>${pctCell(c.return)}</td><td>${sinceExitCell(c.since_exit)}</td>
        <td class="hide-sm">${exitReasonChips(c.exit)}</td>
        <td>${stateStamp(decisionOf(s))}</td></tr>`).join("");
  } else {
    const sorted = rows.slice().sort((a, b) => order(a) - order(b));
    head = '<th class="l">Candidate</th><th>Price</th><th class="hide-sm">Added</th><th>State</th>';
    /* No history mark here: a candidate is a security with no lots at all,
       so there is nothing on it that could have been entered afterwards. */
    body = sorted.map((s) => `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
      <div class="coname">${esc(s.name)}</div></td>
      <td>${priceCell(s)}</td><td class="dim hide-sm">${esc(s.added)}</td>
      <td>${stateStamp(decisionOf(s))}</td></tr>`).join("");
  }
  html += `<div class="sheet"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  if (tab === "previous") html += scorecards();
  return html;
}

function scorecards() {
  const o = S.override_scorecard, x = S.exit_scorecard;
  const line = (k, v) => `<div class="kv"><span>${esc(k)}</span><b>${v}</b></div>`;
  /* Counted per purchase, not per name and not per round trip: one buy can
     be a compliant entry and the next in the same name an override, and
     collapsing them loses exactly the comparison this exists to make.

     Every average says what it rests on. The host counts the purchases in a
     group and, separately, how many of them could be scored at all — a
     purchase with no price is a decision that happened and a return that is
     not knowable. Printing the average beside the group count and dropping
     the scored count is how a partial population passes for the whole, on
     the one panel that is supposed to be able to indict a rule. */
  const pct = (v) => v === null || v === undefined
    ? "—" : (v >= 0 ? "+" : "") + v + "%";
  /* Why they could not be scored, from the engine, rather than a reason
     asserted here. The panel used to say flatly that they "have no price" —
     for every unscoreable purchase, including one recorded at $0.00, which
     sent the reader off to fetch data that would never fix it. In the one
     panel principle 10 says must be able to indict a rule, an invented
     reason is the last thing that may pass for a finding. */
  /* Each panel's own reasons, never the journal's. A shared list would let
     the Overrides panel itemise a compliant purchase — the panel attributing
     a decision to the wrong side of the line it exists to measure. */
  const unscored = (n, why) => n
    ? `<div class="hint" style="margin:4px 0 0">${n} more ${n === 1 ? "was" : "were"} counted but not averaged.${
        (why || []).map((u) => ` ${u.n}: ${esc(u.reason)}.`).join("")}</div>`
    : "";
  const summ = (d) => d.n_purchases
    ? line("Purchases", d.n_purchases)
      + line("Scored", d.n + " of " + d.n_purchases)
      + line("Win rate", d.win_rate === null ? "—" : d.win_rate + "%")
      + line("Average return", pct(d.avg))
      + unscored(d.n_unscored, d.unscored)
    : "";

  /* Two cohorts, never added up. A decision seen on the screen and a decision
     rebuilt for a day in the past are not the same evidence about the same
     question: the first is somebody's judgement under a verdict they were
     looking at, the second is this program's best attempt at a day nobody was
     standing in. A journal backfilled with ten years of history would answer
     "did overriding help" almost entirely with the second and report it as
     the first.

     Each cohort renders only if it has purchases in it, so a journal with no
     history entered looks exactly as it did, and a wholly backfilled one is
     not two empty panels above a footnote. */
  const COHORTS = ["live", "reconstructed"];
  /* Per side, not per journal. A journal can have overrides in one cohort
     only and compliant purchases in both, and a heading printed over a
     single row is a distinction charged for nothing — while the same
     heading missing from two stacked rows is two win rates reading as one. */
  const shown = (which) => COHORTS.filter((c) => (o[c] || {})[which]
    && o[c][which].n_purchases);
  const side = (which) => {
    const cohorts = shown(which);
    return cohorts.map((c) => (cohorts.length > 1
      ? `<div class="cohort" title="${esc(o[c].means)}">${esc(o[c].label)}</div>`
      : "") + summ(o[c][which])).join("")
      || '<p class="hint">Nothing to compare yet.</p>';
  };

  /* The purchases nobody could rebuild a verdict for. In neither comparison,
     because there was no verdict to obey or defy — putting them in either
     would invent a decision that was never made. Reported anyway: they
     happened, what they returned is knowable, and how many of them there are
     is the honest measure of how far back this journal can see. */
  const u = o.unreconstructed || {};
  const dark = u.n_purchases
    ? `<div class="panel"><h3>Could not be reconstructed</h3>
       <div class="sub">Entered from history, with no verdict to rebuild</div>
       ${summ(u)}
       <p class="hint">These are in neither comparison. There was no signal to
       go against, so calling them overrides would put decisions nobody made
       into the one figure that is supposed to measure your judgement.
       ${(u.reasons || []).map((r) => `${r.n}: ${esc(r.reason)}`).join(" ")}</p></div>`
    : "";

  /* Per rule, per cohort, and labelled — the panel that is supposed to be able
     to indict a rule is the last place two populations may pass for one. */
  const perRule = COHORTS.map((c) => {
    const rules = (o[c] || {}).per_rule || {};
    const rows = Object.keys(rules).map((id) => {
      const b = rules[id];
      /* wins are counted over what could be scored, so the denominator has to
         be that same population — "1/3" over three purchases of which two had
         no price says a rule lost twice when nothing is known about them. */
      return line(b.label, `${b.wins}/${b.n_scored} · ${pct(b.avg)}`
        + (b.n_scored < b.n
          ? ` <span class="dim">of ${b.n} overrides</span>` : ""));
    }).join("");
    if (!rows) return "";
    return (COHORTS.filter((x) => Object.keys((o[x] || {}).per_rule || {}).length)
      .length > 1
      ? `<div class="cohort" title="${esc(o[c].means)}">${esc(o[c].label)}</div>`
      : "") + rows;
  }).join("");

  const exRows = Object.keys(x).map((reason) => {
    const b = x[reason];
    const over = (n) => n < b.n ? ` <span class="dim">(${n} of ${b.n})</span>` : "";
    /* How many of this group's sales were entered from history. The returns
       either side of a sale are recorded prices and do not change according to
       when the row was typed — but the signal the sale was recorded against
       was rebuilt, and "Panic, three times, and it rose after each" reads
       differently when none of the three was a moment anybody lived through. */
    return line(reason + ` (${b.n})`,
      `held ${pct(b.avg_held)}${over(b.n_held)}`
      + ` · after ${pct(b.avg_after)}${over(b.n_after)}`
      + (b.n_reconstructed
        ? ` <span class="dim" title="Entered from history: the verdict beside these sales was rebuilt, not seen at the time.">· ${b.n_reconstructed} from history</span>`
        : ""));
  }).join("") || '<p class="hint">No sales recorded yet.</p>';
  /* "After" measures to today, except where the name was bought again — there
     it stops at that purchase. Saying so matters: an average that silently
     mixes two window lengths is a different number from the one it claims to
     be, and this one is the sell-rule evidence. Bought *again*, not bought
     *back*: adding after a trim ends the window for the same reason, and the
     position was never closed. */
  const again = Object.keys(x).reduce((a, r) => a + (x[r].bought_again || 0), 0);
  const backNote = again
    ? `<p class="hint">${again} of these sales ${again === 1 ? "was" : "were"} followed by buying the name again.
       Those measure to that purchase rather than to today — once you owned it again, the move was yours rather than
       evidence about the sale.</p>` : "";

  /* Two kinds of override, counted apart on purpose. Going ahead in the face
     of a verdict and going ahead where there was no verdict to face are not
     the same decision, and averaging them makes a data gap look like
     defiance. Counted within the live cohort only, because that is the only
     one that can hold the second kind: a reconstruction that reached no
     verdict is not a decision taken without one — see recorded_as. */
  const k = (o.live || {}).kinds || {};
  const kindNote = (k.against || k.without)
    ? `<p class="hint">Seen at the time: ${k.against || 0} against a verdict · ${k.without || 0} where there was no verdict to go against.</p>` : "";
  /* Said once, under whichever panel is actually showing two rows. A panel
     with one row has nothing to explain, and the sentence printed under
     "nothing to compare yet" is noise where a reader is looking for a
     figure. */
  const reconNote = (which) => shown(which).length > 1
    ? `<p class="hint">The two rows are not added up. ${esc(o.reconstructed.label)} means
       ${esc(o.reconstructed.means)} — the same question asked of a moment nobody was standing in.</p>` : "";
  return `<div class="cards">
    <div class="panel"><h3>Overrides</h3><div class="sub">Bought against or without the signal</div>${side("override")}${kindNote}${reconNote("override")}</div>
    <div class="panel"><h3>Compliant</h3><div class="sub">Bought when the strategy said so</div>${side("compliant")}${reconNote("compliant")}</div>
    ${dark}
    <div class="panel"><h3>By exit reason</h3><div class="sub">Return while held · return since</div>${exRows}
      <p class="hint">If one reason keeps showing a strong return <em>after</em> you sold, that is the rule to look at.</p>${backNote}</div>
    ${perRule ? `<div class="panel"><h3>Rules you overrode</h3><div class="sub">Wins / times · average</div>${perRule}
      <p class="hint">If overriding a rule keeps working, the rule is miscalibrated, not you. That is a reason to change the
      strategy's settings, written down.</p></div>` : ""}
  </div>`;
}

/* ------------------------------------------------------- the decision ---- */
/* A verdict without the figures that produced it teaches nothing. Every
   conclusion is traceable to its cause, in place: the rule inside the
   strategy that produced it, the sentence saying why, and each figure it
   cited with what was required and how the comparison came out. */

/* How much, in whatever unit the strategy sized it in. The host's three, and
   a strategy cannot add a fourth. */
function sizeText(size) {
  const s = size || {};
  return s.unit === "weight" ? `${s.value}% of the account`
    : s.unit === "usd" ? "$" + Number(s.value).toLocaleString()
    : `${Number(s.value).toLocaleString()} shares`;
}

/* The tranches a staged entry is holding back, each with what releases it.
   Rendered as intention and never as entitlement: the strategy re-runs every
   time, so a tranche is only ever bought when that day's evaluation offers
   it as the size in front of you. Saying "then 3% at a 40% discount" as a
   promise would be this screen scheduling a purchase, which is the one thing
   a pre-commitment must not become — the business is re-tested each time,
   and it may fail. */
function planText(plan) {
  if (!plan || !plan.length) return "";
  return `<div class="pe-block"><b>Held back, and what releases it</b>
    <ul class="pe-nmw">${plan.map((t) =>
      `<li>${esc(sizeText(t.size))} — once ${esc((t.condition || {}).summary)}</li>`).join("")}</ul>
    <span class="dim">Written in advance, and re-tested every time. A tranche
    goes in only when this strategy offers it on the day, which it will not do
    if the business has stopped qualifying.</span></div>`;
}

function payloadText(d) {
  const p = d.payload || {};
  if (d.render === "commit") {
    const how = sizeText(p.size);
    const head = p.condition
      ? `Commit ${how} — once ${esc(p.condition.summary)}`
      : `Commit ${how}, now`;
    return head + planText(p.plan);
  }
  if (d.render === "reduce") {
    const t = p.to || {};
    return `Reduce to ${t.unit === "weight" ? t.value + "% of the account"
      : Number(t.value).toLocaleString() + " shares"}`;
  }
  if (d.render === "close") return `Exit due ${esc(p.when)}`;
  if (d.render === "blocked") {
    return `<ul class="pe-nmw">${(p.needs || []).map((n) => `<li>${esc(n)}</li>`).join("")}</ul>`;
  }
  return "";
}

/* ------------------------------------------------------------- cautions */
/* A caution is a sentence about what a number rests on: a share class valued
   at a sibling's close, a balance-sheet line matched by its label rather than
   by a mapped concept, a price too old to be current. It travels with the
   value everywhere the value goes, and this is the only place that decides
   how it reads.

   Not a warning glyph and not a colour. A caution is not a failure — it is a
   number saying what it rests on — and a red mark on twelve of a company's
   twenty-nine measures is how a reader learns to stop looking at all
   twenty-nine. The word carries it instead, which also means it survives
   being read aloud and never depends on colour alone.

   Two treatments, because two kinds of screen ask different things:

   - Where a figure is being acted on or audited — the evidence behind a
     verdict, a frozen purchase, the values you are about to override — the
     sentences are inline and always visible. It is a handful of rows and the
     reader is deciding something on exactly these numbers.
   - Where a screen is an inventory — the data page's thirty-odd measures —
     the value carries a mark and its sentences open in place underneath.
     Cautions propagate through derivation, so one borrowed price becomes the
     same sentence on eleven measures: a real company's data page renders
     thirty-eight caution lines saying nine things, and a wall of repeated
     text is exactly how the one that mattered gets scrolled past. */
const cautionLines = (cs) => (cs || []).map((c) =>
  `<div class="greynote qual">Qualified — ${esc(c)}</div>`).join("");

/* The mark. Always the same mark, always carrying the count, so "this number
   has something attached to it" is one glance and never a judgement call. */
function cautionMark(cs, key) {
  if (!(cs || []).length) return "";
  const id = "q:" + key;
  return `<button class="chip qualmark" data-tip="${esc(id)}"
    aria-expanded="${tipOpen === id}"
    aria-label="What qualifies this figure">qualified${cs.length > 1 ? " ×" + cs.length : ""}</button>`;
}
const cautionBox = (cs, key) =>
  tipOpen === "q:" + key ? cautionLines(cs) : "";

function evidenceRow(item, i) {
  const subj = item.subject || {};
  const obs = item.observed || {};
  const [word, cls] = OUTCOME[item.outcome] || [item.outcome, "s-none"];
  const known = obs.status === "known";
  /* Two ways to have no figure, and the row must not draw them alike. "Not
     known" says go and look — fetch, wait a quarter, answer the question.
     "Not applicable" says this measure was never built to describe this kind
     of company, and no amount of looking will change it. The outcome beside
     them is the same word on purpose: neither was tested, and a fifth
     outcome would be a word every strategy written before today would fall
     straight through. */
  const val = known
    ? `<b>${esc(fmtSubject(subj, obs.value))}</b>`
    : `<span class="chip blank">${obs.status === "inapplicable"
        ? "not applicable" : "not known"}</span>`;

  /* The limit, and whose it is. Where the strategy named one of its own
     settings the host read the number out of that setting — so it renders in
     the SETTING's unit, not in the unit of the thing being measured: a
     dollar reserve under a percent measure would otherwise read as a
     percentage. Older records carry no unit on the source and fall back to
     the subject's, which is what they were rendered with when frozen. */
  let test = "";
  if (item.test) {
    const t = item.test;
    const src = t.threshold_from;
    const thr = t.absent
      ? '<span class="chip blank">not set</span>'
      : esc(src && src.unit ? fmtUnit(t.threshold, src.unit)
                            : fmtSubject(subj, t.threshold));
    const from = src
      ? ` <span class="dim">— your ${esc(src.label)}</span>` : "";
    test = ` <span class="dim">${esc(t.phrase)}</span> ${thr}${from}`;
  }
  const at = subj.at ? ` <span class="dim">as at ${esc(subj.at)}</span>` : "";
  const why = !known ? `<div class="greynote">${esc(obs.reason)}</div>` : "";
  /* A limit nobody supplied is its own kind of absence, and a different one
     from a figure nobody could compute. Both can be true at once, and both
     say so — the test did not fail, it never ran. */
  const noLimit = (item.test && item.test.absent)
    ? `<div class="greynote">${esc(item.test.absent)}</div>` : "";
  const prov = (obs.provenance || []).map((p) => `<div class="greynote">${esc(p)}</div>`).join("");
  const warn = cautionLines(obs.cautions);

  const explain = subj.explain
    || (["measure", "robustness"].includes(subj.kind) && bankMeta(subj.id)
      ? bankMeta(subj.id).plain : null);
  const tipId = "ev:" + i;
  const tip = explain
    ? `<button class="tip" data-tip="${esc(tipId)}" aria-expanded="${tipOpen === tipId}"
        aria-label="What is ${esc(subj.label)}?">?</button>` : "";
  /* The definition first, then the question it is asked through. A judgement
     row used to open with the question alone, which answers "what is this?"
     by asking it again — at the exact moment somebody is deciding whether a
     moat is durable. The whole argument that a novice can answer these rests
     on the explanation being right here. */
  const asks = subj.asks
    ? `<div class="pe-sub" style="margin-top:6px"><b>What you are asked:</b> ${prose(subj.asks)}</div>` : "";
  const tipBox = (explain && tipOpen === tipId)
    ? `<div class="tipbox">${prose(explain)}${asks}
       <span class="who">${subj.kind === "measure" ? `Bank entry <code>${esc(subj.id)}</code> — full definition on the Metrics tab`
         : subj.kind === "judgement" ? `Your own assessment, not a figure the journal worked out — bank entry <code>${esc(subj.id)}</code>`
         : subj.kind === "value" ? "A setting this strategy ships and you can change"
         : subj.kind === "input" ? "Something you told this journal at setup"
         : subj.kind === "fact" ? "A figure the journal reports about your position"
         : subj.kind === "change" ? `How far this has moved since one of your own purchases. Both readings are the journal's — the one frozen at that purchase and the one on record now — and the distance between them is worked out here, not stated by the strategy. Bank entry <code>${esc(subj.id)}</code>`
         : subj.kind === "robustness" ? `The same figure worked out again with one fiscal year taken out — the single year whose removal most helps the test be met. It is here because this measure is read over a window of years, so waiting for another filing would mostly re-read the same years; taking the flattering year out asks whether the rest of the record says the same thing. Bank entry <code>${esc(subj.id)}</code>`
         : "A figure the strategy worked out itself"}</span></div>` : "";

  /* No action here, deliberately. A verdict waiting on a question nobody
     answered must not be a dead end — but the way in belongs to the
     Judgements section on the same page, which renders a button for every
     question the strategy cites, answered or not. A second button beside
     the evidence would be the same action twice on one screen, and this row
     is also what renders a decision frozen onto a lot years ago: offering
     to answer that reads as though answering would change what an
     append-only record says. */
  return `<div class="srow"><div class="sname">${esc(subj.label)}${at}${tip}</div>
    <div class="scond">${val}${test}${why}${noLimit}${prov}${warn}${tipBox}</div>
    <div class="sstate"><span class="chip ${cls}">${esc(word)}</span></div></div>`;
}

/* The headings the rows are gathered under, and what each one demanded.
   Rendered from the reason, never from a list in this file: a strategy that
   groups its evidence differently arrives here with no view code changed.

   The counts are the host's own, taken from the rows below the heading, so
   a rollup and its rows cannot say different things. Where a group demanded
   nothing, only the count shows — inventing "never blocks" for it would be
   this file claiming to know why the strategy is not testing them, and an
   exit awaiting a second filing is not the same as a bonus test. */
function groupHead(g) {
  const [word, cls] = OUTCOME[g.outcome] || [g.outcome, "s-none"];
  const need = g.requires === "all"
    ? (g.tested > 1 ? `all ${g.tested} must pass`
      : g.tested === 1 ? "it must pass" : "")
    : g.requires === "at_least"
      ? ((g.test && g.test.absent)
        ? "no bar is set — " + esc(g.test.absent)
        : `at least ${esc(String((g.test || {}).threshold))} must pass`
          + ((g.test || {}).threshold_from
            ? ` — your ${esc(g.test.threshold_from.label)}` : ""))
      : "";
  const counted = g.tested
    ? `${g.passed} of ${g.tested} passed`
      + (g.unknown ? ` · ${g.unknown} could not be worked out` : "")
    : "";
  return `<div class="srow ghrow"><div class="sname"><b>${esc(g.name)}</b></div>
    <div class="scond"><span class="dim">${counted}${counted && need ? " · " : ""}${need}</span></div>
    <div class="sstate">${g.requires === "noted" ? ""
      : `<span class="chip ${cls}">${esc(word)}</span>`}</div></div>`;
}

/* One list of rows, with a heading wherever a group starts. The order is the
   strategy's — the contract refuses a group whose rows are not together, so
   a heading is opened once and never reopened. */
function evidenceList(decision, key) {
  const reason = decision.reason || {};
  const ev = reason.evidence || [];
  const by = {};
  (reason.groups || []).forEach((g) => { by[g.id] = g; });
  let open = null;
  return ev.map((item, i) => {
    let head = "";
    if (item.group !== open) {
      open = item.group;
      if (open && by[open]) head = groupHead(by[open]);
    }
    return head + evidenceRow(item, key + ":" + i);
  }).join("");
}

/* A blocked verdict with nothing to click is a dead end, and a state that
   says "the strategy will not answer until you do something" is exactly the
   one a user must be able to escape. Every state that stops names the screen
   that resolves it — a strategy's as much as the host's — and the label comes
   with it. There is no list of fixes in this file: one lived here, it knew
   about a single id, and a state naming any other drew no button at all. */
function fixButton(d) {
  const fix = ((d || {}).state || {}).fix;
  const spec = fix ? (S.state_fixes || {})[fix] : null;
  if (!spec) return "";
  return `<div class="toolbar" style="justify-content:flex-start;margin:12px 0 0">
    <button class="btn primary" data-act="${esc(fix)}">${esc(spec.label)}</button></div>`;
}

function decisionSection(d, title) {
  if (!d) return "";
  const r = d.reason || {};
  const ev = r.evidence || [];
  const payload = payloadText(d);
  const host = d.produced_by === "host";
  return `<section class="group"><div class="ghead"><h3>${esc(title || "The verdict")}</h3>
      <span>${esc((d.state || {}).name || "")}</span></div>
    <div class="hint" style="margin:8px 0 0">${prose((d.state || {}).description)}</div>
    <div class="rollup" style="margin-top:12px">
      <div class="pe-head"><b>${esc(r.summary || "")}</b></div>
      <div class="pe-sub" style="margin-top:6px">${host
        ? "Produced by the journal itself, not by the strategy — no verdict exists to show."
        : `Rule <code>${esc(r.rule)}</code> inside ${esc((d.strategy || {}).name || "the strategy")}
           v${esc((d.strategy || {}).version)}${(d.strategy || {}).values_version != null
             ? ` · settings v${esc((d.strategy || {}).values_version)}` : ""}`}</div>
      ${payload ? `<div class="pe-th" style="margin-top:10px">${payload}</div>` : ""}
      ${r.note ? `<div class="pe-why">${prose(r.note)}</div>` : ""}
      ${fixButton(d)}
    </div>
    ${ev.length ? `<div class="slist" style="margin-top:14px">${evidenceList(d, "ev")}</div>`
      : '<p class="hint" style="margin-top:12px">No figures were cited — nothing about the security was read.</p>'}
  </section>`;
}

/* ------------------------------------------------------------ judgements */
/* The questions no filing answers, asked per security. Rendered from the
   bank's own qualitative entries by way of the backend — there is no list of
   them in this file, and a question added to the bank arrives here with no
   view code changed.

   Shown only where the strategy asked for one or an answer already exists.
   The union of every question the bank could ask is not this page's
   business, and asking someone to assess the durability of a business their
   own rules already rejected is the overwhelm this program exists to avoid. */
const MARK_CHIP = {
  pass: ["Passed", "s-pass"],
  fail: ["Failed", "s-fail"],
};

function judgementSection(s) {
  const list = s._judgements || [];
  if (!list.length) return "";
  const owed = list.filter((j) => !j.mark && !j.unsupported).length;
  const rows = list.map((j) => {
    const [word, cls] = MARK_CHIP[j.mark] || ["Not assessed", "blank"];
    const when = j.recorded ? String(j.recorded).slice(0, 10) : null;
    /* Whatever qualifies the answer — an assessment written before the
       holding you have now, say. The host's own sentences, the same ones the
       strategy is handed, rendered by the same helper as every other
       caution. Nothing is worked out again here. */
    const stale = cautionLines(j.cautions);
    const older = (j.history || []).slice(1);
    return `<div class="pentry">
      <div class="pe-head"><b>${esc(j.label)}</b><code>${esc(j.id)}</code>
        <span class="chip ${cls}">${esc(word)}</span>
        ${j.cited ? "" : '<span class="req">not currently asked</span>'}</div>
      ${j.unsupported
        ? `<div class="greynote">${esc(j.unsupported)}</div>`
        : j.mark
        ? `<div class="pe-why">${prose(j.reasoning)}</div>
           <div class="pe-sub">Your assessment of ${esc(when)}</div>${stale}`
        : `<div class="pe-desc">${prose(j.question)}</div>`}
      <details class="whybox"><summary>What this asks${
        older.length ? ` · ${older.length} earlier assessment${older.length === 1 ? "" : "s"}` : ""}</summary>
        ${prose(j.question)}${prose(j.plain)}
        ${older.map((a) => `<div class="pe-sub" style="margin-top:8px">
          <b>${esc((MARK_CHIP[a.mark] || ["Marked"])[0])}</b> on
          ${esc(String(a.recorded).slice(0, 10))}</div>
          <div class="pe-why" style="margin-top:0">${prose(a.reasoning)}</div>`).join("")}
      </details>
      ${j.unsupported ? "" : `<div class="toolbar" style="justify-content:flex-start;margin-top:8px">
        <button class="btn${j.mark ? "" : " primary"}" data-act="judge" data-jid="${esc(j.id)}">${
          j.mark ? "Reassess" : "Answer this"}</button></div>`}
    </div>`;
  }).join("");
  /* Named, because a blocked verdict whose way out is "answer these" sends
     the reader here from further up the page. The host refuses that verdict
     unless it cited a question, so by the time the button exists this
     section does too. */
  return `<section class="group" id="judgements" style="margin-top:26px">
    <div class="ghead"><h3>Your judgement</h3>
      <span>${owed ? `${owed} unanswered` : "answered"}</span></div>
    <p class="hint" style="margin:8px 0 0">Questions the filings cannot answer, which
    ${esc(((S.strategy || {}).name) || "this journal's strategy")} reads for this security.
    Each is your assessment with your reasoning, never a figure the journal worked out — and
    unanswered is not a fail. The record is append-only and dated: changing your mind adds an
    entry above the old one, and neither is ever edited.</p>
    <div class="plist" style="margin-top:12px">${rows}</div></section>`;
}

/* -------------------------------------------------------------- thesis */
/* The standing version, and every version before it.

   Amendments render collapsed rather than hidden. A falsifier rewritten the
   week before an exit is the most instructive thing this journal holds, and
   it is instructive precisely because you can see what it said before — but
   the screen at rest is the thesis you hold today, not a changelog. */
function thesisBlock(s) {
  const t = s._thesis || {};
  const v = t.status === "known" ? t.version : null;
  const past = (t.history || []).slice(1);
  if (!v) {
    return `<div class="fals"><em>Why I own this</em>
      <span class="dim">Not yet written.</span></div>`;
  }
  return `<div class="fals">
    ${v.thesis ? `<em>Why I own this</em>${esc(v.thesis)}` : ""}
    ${v.falsifier ? `<em>What would make me wrong</em>${esc(v.falsifier)}` : ""}
    </div>
    <div class="pe-sub">${past.length ? "Amended" : "Written"} ${esc(t.amended)}</div>
    ${/* The reason for the amendment standing now — the most recent time
          someone changed their mind, which is the one worth reading before
          the earlier ones are opened at all. It renders here rather than
          only inside the history, because a version list you have to expand
          is a version list nobody expands. */
      v.reason ? `<div class="pe-why"><b>Changed because</b> ${esc(v.reason)}</div>` : ""}
    ${cautionLines(t.cautions)}
    ${past.length ? `<details class="whybox"><summary>${past.length} earlier version${past.length === 1 ? "" : "s"}</summary>
      ${past.map((p) => `<div class="pe-sub" style="margin-top:8px">
        <b>${esc(String(p.recorded).slice(0, 10))}</b></div>
        ${p.reason ? `<div class="pe-why" style="margin-top:0"><b>Changed because</b> ${esc(p.reason)}</div>` : ""}
        ${p.thesis ? `<div class="pe-why" style="margin-top:0">${prose(p.thesis)}</div>` : ""}
        ${p.falsifier ? `<div class="pe-why" style="margin-top:0"><b>Would make me wrong</b> ${esc(p.falsifier)}</div>` : ""}`).join("")}
      <p class="hint">Nothing here was edited. Each amendment is the whole thesis as it stood that day,
      with the reason it changed — because a thesis that can be revised once the answer is known cannot
      grade the decisions made under it.</p></details>` : ""}`;
}

/* ---------------------------------------------------------------- detail */
function detailView(s) {
  const isHold = s.bucket === "holdings", isPrev = s.bucket === "previous";
  const d = decisionOf(s);
  const open = openPeriod(s), closed = closedPeriods(s);
  /* The closed holding this page is about — the one clicked in from, and only
     otherwise the one that ended most recently. It was always the most recent:
     clicking the second of three rows under Previous holdings opened a page
     whose exit price, return and since-exit all described the third. The
     header named which holding it was showing, so nothing was ambiguous — but
     the click did not go where it looked like it should, and every figure on
     the strip was about a round trip the reader had not asked for. */
  const subject = subjectPeriod(s);
  const last = (subject && !subject.open ? subject : null)
    || closed[closed.length - 1] || null;
  const many = periods(s).length > 1;
  /* What the strip and the header describe is the PERIOD in front of you;
     what the toolbar offers is about the security as it stands now. Those are
     two different questions and they were one, read off the bucket — so a name
     you closed and bought back showed its open position however you arrived,
     including from the closed round trip you clicked. Buying and selling stay
     on the bucket, because you cannot sell a holding that ended. */
  const showsOpen = subject ? subject.open : isHold;
  const showsClosed = subject ? !subject.open : isPrev;
  let h = missingStrategyBanner() + pendingBanner();
  h += `<button class="backlink" data-act="back">← ${TABS.find((t) => t[0] === tab)[1]}</button>`;

  /* The header says which holding you are looking at, by name, whenever
     there is more than one. Everything above the lot history describes a
     single period — the open one, or the one that ended most recently — and
     the Previous holdings tab has a row per period, so a reader arriving
     from the older row must be told at once which one they are reading.
     "Held since" or "Closed" alone reads as the whole story of the ticker. */
  const meta = showsOpen
    ? (many ? `${esc(periodName(s, subject || open))} · held since ` : "Held since ")
      + esc((subject || open).opened)
    : showsClosed
    ? (many ? `${esc(periodName(s, last))} of ${closed.length} · closed `
        : "Closed ") + esc(last.closed)
      + " · " + esc(((last.exit || {}).reasons || [])
          .map((r) => r.reason).join(", ") || "no reason recorded")
    : "Added " + esc(s.added);
  h += `<div class="dhead"><div class="dtitle"><h1>${esc(s.ticker)}</h1><p>${esc(s.name)}</p>
    <div class="meta">${meta} · judged by ${esc((S.journal.strategy || {}).name || "no strategy")}${
      s._backfilled ? " · " + RECON_CHIP : ""}</div></div>
    <div style="text-align:right">${stateStamp(d, true)}
    <div class="stamp-note">${esc((d && (d.reason || {}).summary) || "")}</div></div></div>`;
  /* Said once, at the top, on any position holding an entry that was typed in
     rather than captured. Everything below repeats it per entry — the point
     of this line is that somebody arriving at the page knows before they read
     a single figure that part of this record is a reconstruction. */
  if (s._backfilled) {
    const n = buyLots(s).concat(sales(s)).filter(reconstructed).length;
    h += `<div class="notice quiet"><h4>Part of this record was entered from history</h4>
      <p>${n} ${n === 1 ? "entry is" : "entries are"} dated earlier than the day
      ${n === 1 ? "it was" : "they were"} entered, so what is frozen beside
      ${n === 1 ? "it" : "them"} was rebuilt rather than seen. Each was judged
      against the filings and the close available on its own day — never against
      today's — and each says so where it appears. What could not be rebuilt
      says that instead of guessing.</p></div>`;
  }

  const fetching = s._fetch && s._fetch.running;
  h += `<div class="toolbar" style="margin-top:16px;justify-content:flex-end;align-items:center"><div>
    <button class="btn" data-act="fetchdata" ${fetching ? "disabled" : ""}>${fetching ? "Fetching…" : "Fetch data"}</button>
    <button class="btn" data-act="metrics">Edit values</button>
    <button class="btn" data-act="ev">Expected value</button>
    <button class="btn" data-act="thesis">Thesis</button>
    <button class="btn" data-act="note">Add note</button>
    <button class="btn" data-act="backfill">Enter history</button>
    ${!isHold ? `<button class="btn primary" data-act="buy">${isPrev ? "Record a purchase — buying it back" : "Record a purchase"}</button>` : ""}
    ${!isHold && !isPrev ? '<button class="btn danger" data-act="remove">Remove</button>' : ""}
    ${isHold ? '<button class="btn danger" data-act="sell">Record a sale</button>' : ""}
    </div></div>`;
  /* No way to buy more of it from here, and that costs a click on purpose.
     This page is where you end up when a holding is down, and a button
     offering more of it — with a size on it — is the tool lending its
     authority to averaging down at the moment somebody is looking for
     permission. Where the money goes is a question about the whole list and
     is answered on the screen that can see all of it. The verdict above
     still says whether this one is eligible; it just does not say how much. */
  if (isHold) {
    h += `<p class="hint">Putting more money into this is decided on
      <button class="linkish" data-tab="allocate">Where capital goes</button>,
      beside everything else your rules would take today. Your average cost
      is on this page because it is worth knowing; what it is not is
      available to any rule, on either screen.</p>`;
  }
  if (fetching) {
    h += `<p class="hint" id="fetchstate" style="margin:8px 0 0">${esc(fetchStateText(s._fetch))}</p>`;
    startFetchPoll(s.ticker);
  }

  /* facts */
  const priceLabel = (s._price && s._price.terminal)
    ? "Price · series ended"
    : (s._price && s._price.source === "fetched")
    ? `Price · close ${String(s._price.date).slice(0, 10)}` : "Price";
  /* Why there is no price, not just a dash. The host's reason names the
     instrument and lists the sibling share classes that DO have stored
     closes, which is the whole difference between "nothing was fetched" and
     "prices exist for this company but not for the security you hold". A
     bare dash makes the second look like the first. */
  const priceWhy = (s._price && s._price.value == null && s._price.reason)
    ? "Not known: " + s._price.reason + "."
    : (s._price && s._price.terminal)
    ? "This price series has ended (" + s._price.terminal.reason
      + "). What you see is the last close this security ever had, not what "
      + "it trades at — and what it is worth, and its share of the account, "
      + "are worked out from that."
    : (s._price && s._price.source === "manual")
    ? (s._price.undated
       ? "The price you entered by hand. It wins over any fetched close. It "
         + "is the one thing you record here that carries no date: it is what "
         + "you saw the market quote rather than something you worked out, "
         + "and the dated version of it is the price history a fetch keeps. "
         + "What it is worth and its share of the account come from it, so if "
         + "it is old, so are they."
       : "The price you entered by hand. It wins over any fetched close.")
    : "";
  const pctText = (r) => {
    const v = pctVal(r);
    return v === null || v === undefined ? "—" : (v >= 0 ? "+" : "") + v + "%";
  };
  /* The reason travels with the figure now, so the strip stops guessing at
     it. It used to test a separate field and splice in the price's reason,
     which was right for an unpriced security and wrong for every other way a
     return can be absent — including the one that reads identically. */
  const pctWhyOr = (r, fallback) => {
    const why = pctWhy(r);
    return why ? `Not known: ${why}` : fallback;
  };
  /* Every fact on this strip describes one holding — the one open, or the one
     that ended. The lifetime figure is the single exception and appears only
     when there is more than one holding to span, named so it can never be
     read as the position in front of you. */
  const sinceExitText = (x) => !x || x.pct === null || x.pct === undefined
    ? "—"
    : pctText(x.pct) + (x.until === "purchase" ? ` to the ${x.date} buy` : "");
  /* An absent figure carries the host's reason for being absent, here as
     well as in the list. A bare dash that drops the reason is a value failing
     to explain itself at exactly the moment there is something to explain. */
  const sinceExitWhy = (x) =>
    !x ? "What the price has done since you sold."
    : x.reason ? `Not known: ${x.reason}.`
    : x.until === "purchase"
    ? `Measured from the sale to the ${x.date} purchase. Once you owned it again the move was yours, and carrying the window on to today would credit the sell rule with a stretch you spent holding.`
    : "What the price has done since you sold. A closed position keeps being priced, which is the only way to find out whether a sell rule works.";
  /* An open holding is marked at the price it is worth now, so where there
     is no price there is no return — and the reason is the price's reason.
     Without it the two ways a return can be absent, unpriced and uncostable,
     read as the same shrug. */
  const sinceBuyWhy = "What this holding has returned so far, against what its"
    + " purchases cost — counting shares you have already sold out of it at"
    + " the price they got."
    + (many ? " This holding only; the earlier one is its own row under Previous holdings." : "");
  const unpriced = s._price && s._price.value == null && px(s) == null;
  let facts = [];
  if (showsOpen) {
    facts = [[priceLabel, money(px(s)), priceWhy], ["Average cost", money(s._cost_basis)],
      ["Shares", s._shares],
      ["Since buy", pctText(s._return), pctWhyOr(s._return, sinceBuyWhy)],
      ["Value", px(s) ? "$" + (px(s) * s._shares).toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—",
        unpriced && s._price.reason ? `Not known: ${s._price.reason}.` : ""]];
  } else if (showsClosed) {
    const ex = last.exit || {};
    const exPrice = ex.price || {};
    facts = [["Exit price",
      exPrice.status === "known" ? money(exPrice.value) : "—",
      exPrice.status === "absent" ? `Not known: ${exPrice.reason}`
        : ex.sales > 1
        ? `Share-weighted across the ${ex.sales} sales that closed this holding — ${
            (exPrice.provenance || []).join("; ")}. Not the last sale's price, which is one sliver of it.`
        : "What you sold at."],
      ["Return held", pctText(last.return),
        pctWhyOr(last.return,
          `What this holding returned over its life: bought ${last.opened}, closed ${last.closed}.`)],
      ["Since exit", sinceExitText(last.since_exit), sinceExitWhy(last.since_exit)],
      ["Reason", (ex.reasons || []).map((r) => r.reason).join(", ") || "not stated",
        (ex.reasons || []).length > 1
          ? "Every reason given, in the order the sales happened: "
            + ex.reasons.map((r) => `${r.reason} for ${r.shares} shares (${r.share}%)`).join("; ")
            + ". A holding closed in stages gave more than one answer and all of them are true."
          : ""]];
  } else {
    facts = [[priceLabel, money(px(s)), priceWhy], ["Added", s.added],
      ["Values read", (s._cited || []).length + " cited by the strategy"]];
  }
  if (many) {
    facts.push(["All holdings", pctText(s._lifetime_return),
      `Every share of ${s.ticker} this journal ever bought, across all `
      + `${periods(s).length} holdings, weighted by what each cost. A lifetime `
      + "figure — it is not what any one of them returned."]);
  }
  facts.push(["Filing data", dataFact(s)]);
  h += '<div class="facts">' + facts.map((f) =>
    `<div class="fact"${f[2] ? ` title="${esc(f[2])}"` : ""}><i>${esc(f[0])}</i><b>${esc(f[1])}</b></div>`).join("") + "</div>";

  /* notices */
  /* Overrides on shares you still hold come first and in full — they are
     about the position in front of you. An override inside a holding that is
     over is history, and it is told inside that holding's own section below
     rather than shouted at the top of a page about a different one. */
  (open ? periodLots(s, open) : []).filter((l) => l.kind === "buy" && l.override)
    .forEach((l) => { h += overrideNotice(s, l); });
  /* An entry whose verdict could not be rebuilt is not an override and is
     never told as one — there was no signal on any screen to go against. It
     still belongs at the top of a position that is holding shares bought this
     way, because "I do not know what my rules would have said about this"
     is the single most important thing to know about a holding. */
  (open ? periodLots(s, open) : [])
    .filter((l) => l.kind === "buy" && l.unreconstructed)
    .forEach((l) => { h += unreconstructedNotice(s, l); });

  /* An exit nobody's rule called for is the panic-sell learning loop, and it
     belongs to the holding it ended — every closed one, not just the last,
     because a name bought back would otherwise bury the exit that taught the
     most. */
  const by = lotById(s);
  closed.forEach((c) => {
    const ex = by[c.sells[c.sells.length - 1]];
    if (!ex) return;
    const which = many ? ` (${periodName(s, c).toLowerCase()})` : "";
    const x = c.since_exit || {};
    const after = x.pct === null || x.pct === undefined ? ""
      : `It went ${x.pct >= 0 ? "up" : "down"} ${Math.abs(x.pct).toFixed(1)}% `
        + (x.until === "purchase"
          ? `between that sale and buying it again on ${esc(x.date)}.`
          : "since it was closed.");
    if (ex.rule_triggered === false) {
      h += `<div class="notice"><h4>No rule triggered this exit${which}</h4>
        <p>The signal read <strong>${esc(ex.signal_at_exit)}</strong> under
        ${esc((ex.strategy || {}).name || "the strategy")} on ${esc(ex.date)}. ${after}</p></div>`;
    } else if (ex.rule_triggered === null) {
      h += `<div class="notice quiet"><h4>Closed without its rules${which}</h4>
        <p>The strategy this journal is stamped with was not installed when this position was closed on
        ${esc(ex.date)}, so no signal could be evaluated. That absence is on the record, not papered over.</p></div>`;
    }
  });
  if (isHold && !((s._thesis || {}).version || {}).falsifier) {
    h += `<div class="notice quiet"><h4>No falsifier on record</h4>
      <p>This position is open without a written answer to "what would make me wrong?".
      That is the field you will want when it drops 25% and you are deciding whether to add or exit.</p></div>`;
  }

  /* the decision, what you had to judge for yourself, then the lots */
  h += decisionSection(d, isPrev ? "Where it stands now" : "The verdict");
  h += judgementSection(s);
  h += lotHistory(s);

  /* where the numbers come from */
  h += coverageSection(s);

  /* panels */
  h += '<div class="panels">';
  const val = s._valuation || {};
  const claim = val.status === "known" ? val.claim : null;
  h += `<div class="panel" id="evpanel"><h3>Expected value</h3><div class="sub">${
    claim ? esc(S.ev_methods[claim.method].label) : "Not calculated"}</div>`;
  if (claim) {
    const meth = S.ev_methods[claim.method];
    /* Each stored assumption says where it came from, in place: fetched
       with its as-of date, computed from filings, or typed — and an
       override names what it replaced. No bare numbers in the record. */
    const SRC_MARK = (src) => {
      if (!src) return "";
      if (src.used === "fetched") return ` <span class="dim">· fetched${src.asof ? ", as of " + esc(src.asof) : ""}</span>`;
      if (src.used === "computed") return ' <span class="dim">· computed from filings</span>';
      if (src.used === "manual") return ' <span class="dim">· hand-entered value</span>';
      if (src.used === "overridden") {
        const was = { fetched: "fetched", manual: "hand-entered", computed: "computed" }[src.instead_of] || "offered";
        return ` <span class="dim">· overridden by hand — replaced the ${esc(was)} ${esc(src.offered ?? "value")}</span>`;
      }
      if (src.used === "typed") return ' <span class="dim">· entered by hand; nothing computed</span>';
      return "";
    };
    h += '<div class="assump">';
    meth.inputs.forEach(([key, label]) => {
      const src = (claim.sources || {})[key];
      h += `<div class="k">${esc(label)}</div><div class="v">${esc(claim.inputs[key] ?? "—")}${SRC_MARK(src)}</div>`
        + (src ? cautionLines(src.cautions) : "");
    });
    h += `</div><div class="evout" id="evout"><div><div class="lbl">Computing…</div><div class="big">—</div></div></div>`;
    h += cautionLines(val.cautions);
    h += `<p class="locked">Claimed ${esc(val.made)} from the assumptions above. There is no field anywhere that accepts a target price.</p>`;
    /* Earlier claims, collapsed. A valuation belongs to the purchase it
       justified — what you thought it was worth at $40 is not amended by
       what you think at $61, it is a different claim about a different
       decision. Both stay, neither averages into anything, and the one a
       purchase was made on is frozen onto that purchase. */
    const past = (val.history || []).slice(1);
    if (past.length) {
      h += `<details class="whybox"><summary>${past.length} earlier claim${past.length === 1 ? "" : "s"}</summary>
        ${past.map((c) => {
          const m = S.ev_methods[c.method] || { label: c.method, inputs: [] };
          return `<div class="pe-sub" style="margin-top:8px"><b>${esc(m.label)}</b> on
            ${esc(String(c.recorded).slice(0, 10))}</div>
            <div class="assump">${m.inputs.map(([k, l]) =>
              `<div class="k">${esc(l)}</div><div class="v">${esc(c.inputs[k] ?? "—")}</div>`).join("")}</div>`;
        }).join("")}
        <p class="hint">Nothing here was replaced. A claim is the case for one purchase, so it is kept
        as the case for that purchase and never blended into a figure about the position.</p></details>`;
    }
  } else if (val.reason) {
    h += `<p class="fals">${esc(S.ev_methods[S.journal.settings.default_ev_method].blurb)}</p>
      <div class="greynote">${esc(val.reason)}</div>
      <p class="locked">You enter assumptions; the value is solved for. That way, when the estimate is wrong, you can see which assumption was wrong.</p>`;
  } else {
    h += `<p class="fals">${esc(S.ev_methods[S.journal.settings.default_ev_method].blurb)}</p>
      <p class="locked">You enter assumptions; the value is solved for. That way, when the estimate is wrong, you can see which assumption was wrong.</p>`;
  }
  h += "</div>";

  h += `<div class="panel"><h3>Journal</h3><div class="sub">Thesis and notes</div>
    ${thesisBlock(s)}
    <div class="fals"><em>Notes</em></div>
    <ul class="notelist">${(s.notes || []).slice().reverse().map((n) =>
      `<li><time>${esc(String(n.date).slice(0, 10))}</time><p>${esc(n.text)}</p></li>`).join("")
      || '<li><p class="dim">No entries yet.</p></li>'}</ul></div>`;
  h += "</div>";
  return h;
}

/* What the user remembers thinking, on an entry they typed in out of their
   own history. Rendered wherever the thesis would be, and never as one: it
   carries the day it was actually written, and the sentence beside it says
   the outcome was already known when it was written. That is the whole
   difference between a record and a story, and the reader has to be able to
   see which they are holding. */
function recollectionBox(lot, where) {
  const r = ((lot || {}).snapshot || {}).recollection;
  if (!r) return "";
  return `<details class="whybox"${where === "open" ? " open" : ""}>
    <summary>Written in hindsight, on ${esc(String(r.written).slice(0, 10))}</summary>
    ${prose(r.text)}
    <p class="hint">Not a thesis. This was written after the outcome was known,
    about a purchase dated ${esc(String(lot.date).slice(0, 10))} — nothing here
    can be graded against what happened, because whoever wrote it already knew.
    A thesis is what you commit to before, and it lives on its own record.</p></details>`;
}

/* An entry this program could not rebuild a verdict for. Deliberately not the
   override notice with different words: an override is a decision somebody
   took in the face of a signal, and there was no signal here — the purchase
   predates what can be reconstructed, and saying otherwise would put a
   decision nobody made on the record. */
function unreconstructedNotice(s, lot) {
  const u = lot.unreconstructed;
  const own = periods(s).find((c) => c.buys.includes(lot.id));
  const many = (own && own.buys.length > 1) ? ` of ${lot.shares} shares` : "";
  const who = (u.strategy || {}).name || "the strategy";
  const r = pctVal((s._lot_returns || {})[lot.id]);
  const rWhy = pctWhy((s._lot_returns || {})[lot.id]);
  return `<div class="notice quiet"><h4>No verdict could be reconstructed · from history</h4>
    <p>This purchase${many} is dated ${esc(u.date)} and was entered from your own
    records. ${esc(who)} could not be rebuilt for that day — ${esc(u.why)}
    So nothing is recorded about what your rules would have said, and this is
    <strong>not</strong> counted as buying against a signal: there was none.${
      r === null || r === undefined
        ? (rWhy ? ` What these shares have done since is not known: ${esc(rWhy)}.` : "")
        : lot.open ? ` These shares are ${r >= 0 ? "up" : "down"} ${Math.abs(r).toFixed(1)}% since.`
        : ` These shares ${r >= 0 ? "returned" : "lost"} ${Math.abs(r).toFixed(1)}% before they were sold.`}</p>
    ${u.note ? `<p class="hint">What the reconstruction could consult: ${esc(u.note)}.</p>` : ""}
    ${recollectionBox(lot, "open")}</div>`;
}

function overrideNotice(s, lot) {
  const ov = lot.override;
  const failed = (ov.failed || []).map((c) => c.label).join(", ");
  const missing = (ov.missing || []).map((c) => c.label).join(", ");
  const under = ov.strategy ? ` under ${esc(ov.strategy.name)} v${esc(ov.strategy.version)}` : "";
  /* The lead sentence must say when the verdict was actually computed.
     basis "live": seen on screen when recorded. basis "reconstructed":
     rebuilt later from the data of the purchase date. */
  const snapEval = (lot.snapshot && lot.snapshot.evaluation) || null;
  const frozen = String((lot.snapshot || {}).frozen || "").slice(0, 10);
  /* Named by size only where the holding it belongs to has more than one
     purchase in it. Counting every lot the ticker ever had would qualify a
     single-lot position because of a holding that ended years ago. */
  const own = periods(s).find((c) => c.buys.includes(lot.id));
  const many = (own && own.buys.length > 1) ? ` of ${lot.shares} shares` : "";
  let lead, basisNote = "";
  if (ov.basis === "reconstructed") {
    lead = `This purchase${many} is dated ${esc(ov.date)}; the state — <strong>${esc(ov.state)}</strong>${under} —
      was <strong>reconstructed</strong> from the data available by that day, not seen live at the time.`;
    if (snapEval && snapEval.note) basisNote = `<p class="hint" style="margin:6px 0 0">Reconstructed from: ${esc(snapEval.note)}.</p>`;
  } else if (!ov.basis && frozen && dayGap(frozen, ov.date) >= 2) {
    lead = `This purchase${many} is dated ${esc(ov.date)}, but its state — <strong>${esc(ov.state)}</strong>${under} —
      was evaluated when it was recorded, around ${esc(frozen)}, with the data current then.`;
  } else {
    lead = `On ${esc(ov.date)} this${many ? " purchase" + many : ""} read <strong>${esc(ov.state)}</strong>${under}.`;
  }
  const head = ov.kind === "without"
    ? "Bought without a signal" : "Bought against the signal";
  const why = ov.kind === "without"
    ? "There was no verdict to go against — the strategy could not reach one."
    : "The strategy did not say to commit capital.";
  const r = pctVal((s._lot_returns || {})[lot.id]);
  const rWhy = pctWhy((s._lot_returns || {})[lot.id]);
  return `<div class="notice"><h4>${head}${ov.basis === "reconstructed" ? " · reconstructed" : ""}</h4>
    <p>${lead} ${esc(why)}
    ${failed ? " " + esc(failed) + " missed its threshold." : ""}${missing ? " " + esc(missing) + " could not be read." : ""}
    The purchase was recorded anyway.${r === null || r === undefined
      ? (rWhy ? ` What these shares have done since is not known: ${esc(rWhy)}.` : "")
      : lot.open ? ` These shares are ${r >= 0 ? "up" : "down"} ${Math.abs(r).toFixed(1)}% since.`
      : ` These shares ${r >= 0 ? "returned" : "lost"} ${Math.abs(r).toFixed(1)}% before they were sold.`}</p>
    ${ov.rule ? `<p class="hint">Rule at the time: <code>${esc(ov.rule)}</code> — ${esc(ov.summary || "")}</p>` : ""}
    ${basisNote}
    <q>${esc(ov.reason)}</q>${recollectionBox(lot)}</div>`;
}

/* Lot history. Every purchase and every sale, in order, each with the
   decision that was frozen for it — written once and never recomputed, so a
   restatement or a retuned strategy cannot rewrite what was seen. A position
   is not a running total that gets updated; it is these entries, and the
   totals above are derived from them on every read. */
function lotHistory(s) {
  const all = periods(s);
  const events = buyLots(s).concat(sales(s))
    .sort((a, b) => String(a.date).localeCompare(String(b.date)) || (a.seq - b.seq));
  if (!events.length) return "";
  const nowState = ((decisionOf(s) || {}).state || {}).id;
  const row = (lot) => {
    const buy = lot.kind === "buy";
    const snap = lot.snapshot || {};
    const d = snap.decision;
    const st = snap.strategy || {};
    const ev = snap.evaluation || {};
    const frozenD = String(snap.frozen || "").slice(0, 10);
    const lotReturn = buy ? (s._lot_returns || {})[lot.id] : null;
    const r = pctVal(lotReturn);

    let how = "";
    if (reconstructed(lot)) {
      how = ` · <b>from history</b> — rebuilt for ${esc(ev.as_of)} from the data available by that day, not seen at the time`;
    } else if (!ev.basis && frozenD && dayGap(frozenD, String(lot.date).slice(0, 10)) >= 2) {
      how = ` · evaluated when it was recorded, around ${esc(frozenD)}, not on the day itself`;
    } else if (frozenD) {
      how = ` · frozen ${esc(frozenD)}`;
    }
    const left = buy
      ? (lot.open ? `${lot.remaining} of ${lot.shares} shares still held`
        : `all ${lot.shares} shares sold`)
      : `${lot.shares} shares, drawn from ${(lot.against || []).length} lot${(lot.against || []).length === 1 ? "" : "s"}`;
    const moved = buy && d && nowState && (d.state || {}).id !== nowState
      ? `<p class="hint">It reads <b>${esc(((decisionOf(s) || {}).state || {}).name)}</b> today. The snapshot is not
         updated to match — that difference is the thesis holding or decaying, and erasing it would erase the only
         thing worth reading.</p>` : "";
    const diff = (st.version != null && (S.journal.strategy || {}).version != null
      && st.version !== (S.journal.strategy || {}).version)
      ? `<p class="hint">Recorded under v${esc(st.version)}; the strategy is at v${esc((S.journal.strategy || {}).version)} now.
         Every change between them is on the Strategy tab.</p>` : "";

    /* Keyed on the lot's own id, not its position in the list: grouped by
       holding, two entries would otherwise share an index and one "what is
       this?" would open two boxes on different periods.

       A decision frozen before groups existed simply has none, and its rows
       render in a flat list exactly as they were written. Nothing about an
       old record is recomputed to acquire headings it never had. */
    const frozenEvidence = evidenceList(d || {}, "lot" + lot.id);

    return `<div class="lot">
      <div class="lothead">
        <b>${buy ? "Bought" : "Sold"} ${esc(lot.shares)} at ${money(lot.price)}</b>
        <time>${esc(String(lot.date).slice(0, 10))}</time>
        ${reconstructed(lot) ? RECON_CHIP : ""}
        ${buy ? "" : `<span class="chip s-none">${esc(lot.reason || "no reason recorded")}</span>`}
        ${r !== null && r !== undefined ? `<span class="chip ${r >= 0 ? "s-pass" : "s-fail"}"
          title="What these shares have returned: the price each sale got on the ones that are gone, today's price on the ones still held, against what this lot cost.">${r >= 0 ? "+" : ""}${r}%</span>`
          : pctWhy(lotReturn) ? `<span class="chip blank" title="${esc("Not known: " + pctWhy(lotReturn))}">not known</span>` : ""}
      </div>
      <div class="pe-sub">${left}${how}${st.name ? ` · under ${esc(st.name)} v${esc(st.version)}` : ""}</div>
      ${moved}${diff}
      ${recollectionBox(lot)}
      ${lot.unreconstructed ? `<p class="hint">No verdict could be rebuilt for
        ${esc(lot.unreconstructed.as_of)}: ${esc(lot.unreconstructed.why)}
        This is not recorded as buying against a signal, because there was none.</p>` : ""}
      ${d ? `<div class="rollup" style="margin-top:10px">
          <div class="pe-head"><b>${esc((d.reason || {}).summary || "")}</b>
            <span class="chip s-none">${esc((d.state || {}).name || "")}</span></div>
          <div class="pe-sub" style="margin-top:6px">Rule <code>${esc((d.reason || {}).rule || "")}</code></div></div>
        <div class="slist" style="margin-top:12px">${frozenEvidence}</div>`
        : `<p class="hint">No verdict was recorded with this entry.</p>`}
    </div>`;
  };

  /* One holding: the plain chronological list, exactly as it always was. The
     grouping below appears only when there is a second holding to tell apart
     — a heading over a single group is complexity charged for nothing. */
  let body;
  if (all.length < 2) {
    body = `<div class="lots">${events.map(row).join("")}</div>`;
  } else {
    /* Several holdings: newest first, so the position in front of you is at
       the top, and each group headed by what that round trip was and how it
       came out. Inside a group the entries stay chronological, because a
       holding reads as a story — bought, trimmed, closed. Someone looking at
       a name held twice must never have to work out which entry belongs to
       which period, and this is the whole of that answer. */
    body = all.slice().reverse().map((c) => {
      const rows = periodLots(s, c).map(row).join("");
      const cv = pctVal(c.return);
      const ret = cv === null || cv === undefined
        ? (pctWhy(c.return)
           ? `<span class="chip blank" title="${esc("Not known: " + pctWhy(c.return))}">not known</span>`
           : "")
        : `<span class="chip ${cv >= 0 ? "s-pass" : "s-fail"}">${cv >= 0 ? "+" : ""}${cv}%</span>`;
      const span = c.open
        ? `bought ${esc(c.opened)} · ${c.shares} shares still held`
        : `${esc(c.opened)} → ${esc(c.closed)} · closed: ${esc(
            ((c.exit || {}).reasons || []).map((r) => r.reason).join(", ")
            || "no reason recorded")}`;
      return `<div class="cyc"><div class="cychead">
          <b>${esc(periodName(s, c))}</b><span class="dim">${span}</span>${ret}</div>
        <div class="lots">${rows}</div></div>`;
    }).join("");
  }

  return `<section class="group"><div class="ghead"><h3>Lot history</h3>
      <span>${events.length} entr${events.length === 1 ? "y" : "ies"}${all.length > 1 ? ` · ${all.length} holdings` : ""}</span></div>
    <p class="hint" style="margin:8px 0 0">Every purchase and sale, in the order they happened, with the verdict
    that was on screen for each. Nothing here is ever edited or recomputed: a sale is a new entry naming the lots
    it drew on, never a change to what was bought.${all.length > 1
      ? " This name has been held more than once, so the entries are grouped by holding — each one its own round trip,"
        + " newest first." : ""}</p>
    ${body}</section>`;
}

/* ------------------------------------------------------------ data layer */
function fetchStateText(st) {
  if (!st) return "";
  const stage = st.stage || "working";
  const n = st.total ? ` — ${st.done || 0} of ${st.total} filings` : "";
  return `Fetching: ${stage}${n}. A first fetch walks the whole filing history at the SEC's polite request rate; expect a minute or two.`;
}
function fetchDoneText(report) {
  if (!report) return "Fetch finished.";
  if (report.no_coverage) return report.no_coverage;
  const bits = [];
  if (report.filings_new) bits.push(`${report.filings_new} new filings`);
  if (report.filings_held != null) bits.push(`${report.filings_held} held`);
  if ((report.prices_fetched || []).length) bits.push(`prices for ${report.prices_fetched.join(", ")}`);
  const errs = (report.errors || []).length;
  return `Fetch finished: ${bits.join(" · ") || "nothing new"}.` + (errs ? ` ${errs} problem${errs === 1 ? "" : "s"} — details in the data coverage section.` : "");
}
function startFetchPoll(ticker) {
  if (FETCH_POLLS[ticker]) return;
  FETCH_POLLS[ticker] = true;
  const poll = async () => {
    const r = await api("get_fetch_status", ticker);
    const st = r && r.status;
    if (st && st.running) {
      const el = $("fetchstate");
      if (el) el.textContent = fetchStateText(st);
      setTimeout(poll, 1500);
      return;
    }
    delete FETCH_POLLS[ticker];
    if (st && st.report && st.report.conflict) toast(st.report.conflict, true);
    else if (st && st.error) toast("Fetch failed: " + st.error, true);
    else if (st) {
      toast(fetchDoneText(st.report));
      const notes = (st.report && st.report.price_notes) || [];
      if (notes.length) setTimeout(() => toast(notes[0], true), 4400);
    }
    C.coverage = null; C.coverageFor = null;
    await refresh();
  };
  setTimeout(poll, 1200);
}

async function loadCoverage(ticker) {
  if (C.loadingCoverage) return;
  C.loadingCoverage = true;
  const r = await apiRaw("get_coverage", ticker);
  C.loadingCoverage = false;
  C.coverageFor = ticker;
  C.coverage = r.ok === false ? { error: r.error } : r;
  /* Re-render whichever security is open, not only the one this load was
     for. Opening another mid-flight would otherwise leave that page with no
     pending load and nothing to trigger one, stuck on "Reading…" forever. */
  if (openTicker) render();
}

/* What kind of company the SEC says this filer is, and the code it says it
   with. On the data page rather than beside the verdict, because it is a
   fact about the company like the filing count and the price series — and
   because the verdict already says its own piece when a strategy declines.

   Absence is drawn as absence and never as "ordinary": a code that covers
   businesses with nothing in common has told us nothing, and rendering that
   as a confident classification is the exact substitution the whole
   arrangement refuses. */
function industryLine(node) {
  if (!node || !node.industry) return "";
  const cls = node.industry, sic = node.sic || {};
  const code = sic.status === "known" ? sic.value : null;
  if (cls.status !== "known") {
    return `<div class="notice quiet"><h4>What kind of company this is — not established</h4>
      <p>${esc(cls.reason || "")}</p>
      <p class="hint">A strategy that does not evaluate every kind of company will say so rather than
      produce a verdict here. One that evaluates everything is unaffected.</p></div>`;
  }
  return `<p class="hint" style="margin:0 0 10px"><b>${esc(cls.value)}</b>${
    code ? ` · SIC ${esc(code)}` : ""}. What the SEC classifies this filer as. It matters because a
    strategy may say it does not evaluate a kind of company — its measures were built for one that sells
    something, and a lender, an insurer and a property company each break them differently.
    ${cautionMark(cls.cautions, "ind")}</p>${cautionBox(cls.cautions, "ind")}`;
}

function coverageSection(s) {
  let inner;
  if (!s.cik) {
    inner = `<p class="hint">Nothing fetched yet. “Fetch data” pulls this company's full filing
      history from SEC EDGAR and its price history from Tiingo, stores the raw reported figures,
      and computes every measure it can. Hand-entered values always win where both exist.</p>`;
  } else if (C.coverageFor !== s.ticker || !C.coverage) {
    loadCoverage(s.ticker);
    inner = '<p class="hint">Reading the stored filings…</p>';
  } else if (C.coverage.error) {
    inner = cfgErrorBox([C.coverage.error]);
  } else if (C.coverage.note) {
    inner = `<p class="hint">${esc(C.coverage.note)}</p>`;
  } else {
    const cov = C.coverage.coverage;
    const st = cov.status || {};
    inner = `<p class="hint" style="margin:8px 0 12px">${st.filings_held || 0} filings held
      (${esc(st.identity || "")}, CIK ${st.cik})${st.pre_xbrl_filings ? ` · ${st.pre_xbrl_filings} older filings predate XBRL (2009–2011 phase-in) and carry no structured data` : ""}
      · prices through ${esc(st.price_through || "none stored")}
      · last fetch ${st.last_fetch ? esc(String(st.last_fetch.at).slice(0, 10)) : "never"}.
      Every value below is recomputed from raw stored figures on each read; nothing derived is saved.</p>`;
    const fetchErrs = (st.last_fetch && st.last_fetch.errors) || [];
    const extractErrs = st.extraction_error_detail || [];
    if (fetchErrs.length || extractErrs.length) {
      inner += `<div class="notice"><h4>Problems from fetching</h4>
        <ul class="pe-nmw">${fetchErrs.map((e) => `<li>${esc(e)}</li>`).join("")}
        ${extractErrs.map((e) => `<li>${esc(e.accession)}: ${esc(e.error)}</li>`).join("")}</ul>
        <p class="hint">Entries that can't compute because of these will say so below.
        Fetching again retries anything transient.</p></div>`;
    }
    (st.terminal_series || []).forEach((t) => {
      inner += `<div class="notice quiet"><h4>${esc(t.ticker)} price series is terminal</h4><p>${esc(t.reason)}</p></div>`;
    });
    /* Quiet, and one box for all of them. These are the symbols the SEC maps
       to the company that the price source does not quote — preferred series,
       warrants, listed notes. They used to arrive one per fetch in "Problems
       from fetching" and stay there permanently, on companies where nothing
       was wrong: Synchrony showed two, Bank of America would show sixteen. A
       red panel that is always right and never actionable teaches the reader
       to skip the panel, which is the one place real problems appear. */
    const unquoted = st.unquoted_symbols || [];
    if (unquoted.length) {
      inner += `<div class="notice quiet"><h4>${unquoted.length}
        ${unquoted.length === 1 ? "symbol has" : "symbols have"} no price history</h4>
        <p>${unquoted.map((u) => `<b>${esc(u.ticker)}</b>`).join(", ")} —
        ${esc(unquoted[0].reason)}. Nothing on this page needs
        ${unquoted.length === 1 ? "it" : "them"}: a company's worth is priced
        in its common stock. ${unquoted.length === 1 ? "It is" : "They are"} no
        longer asked for on each fetch.</p></div>`;
    }
    inner += industryLine(st.industry);
    /* The one inventory screen. Thirty-odd rows, and cautions propagate
       through derivation — one borrowed price lands on every measure built
       from market cap — so the sentences are marked here and opened in
       place rather than repeated down the page. Provenance stays inline:
       it is specific to its own row and does not multiply. */
    const scoped = cov.entries.filter((e) => e.status === "inapplicable");
    if (scoped.length) {
      inner += `<p class="hint" style="margin:0 0 10px">${scoped.length} of
        ${cov.entries.length} measures were never built to describe this kind of company, and say so
        rather than computing. Nothing is missing and there is nothing to fetch — open one to read
        which kind of company the SEC says this is, and why the measure cannot describe it.</p>`;
    }
    const marked = cov.entries.filter((e) => (e.cautions || []).length);
    if (marked.length) {
      inner += `<p class="hint" style="margin:0 0 10px">${marked.length} of
        ${cov.entries.length} figures rest on something worth knowing — a share class
        valued at another's close, a line matched by its label, a price no longer current.
        Each is marked <b>qualified</b>; open one to read what it rests on.</p>`;
    }
    /* Three states and not two, and the third is counted apart above. A
       measure that cannot describe this kind of company will never compute,
       so listing it beside the gaps would leave a permanent item among the
       things to go and do — which is how that list stops being read. The
       word carries it; the dashed edge is the same one `absent` wears. */
    inner += cov.entries.map((e) => {
      const val = e.status === "computed" ? fmtBank(e.value, e.format) : "—";
      const chip = e.status === "computed"
        ? '<span class="chip s-none">computed</span>'
        : e.status === "inapplicable"
          ? '<span class="chip blank">not applicable</span>'
          : '<span class="chip blank">absent</span>';
      const why = e.status === "computed"
        ? (e.provenance || []).map((p) => `<div class="greynote">${esc(p)}</div>`).join("")
        : `<div class="greynote">${esc(e.reason || "")}</div>`;
      return `<div class="srow"><div class="sname">${esc(e.label)}</div>
        <div class="scond">${val === "—" ? "" : `<b>${val}</b>`}
          ${cautionMark(e.cautions, "cov:" + e.id)}${why}${cautionBox(e.cautions, "cov:" + e.id)}</div>
        <div class="sstate">${chip}</div></div>`;
    }).join("");
    inner = `<div class="slist">${inner}</div>` + crosscheckHTML(cov.crosscheck);
  }
  return `<section class="group"><div class="ghead"><h3>Data coverage</h3>
    <span>what computes from filings, and why the rest doesn't</span></div>${inner}</section>`;
}

function crosscheckHTML(cc) {
  if (!cc || !cc.checks || !cc.checks.length) return "";
  const words = { pass: ["Consistent", "s-pass"], warn: ["Look closer", "s-watch"],
    fail: ["Inconsistent", "s-fail"], skipped: ["Could not run", "s-none"] };
  const rows = cc.checks.slice().reverse().map((c) => {
    const [txt, cls] = words[c.status] || [c.status, "s-none"];
    const detail = c.ratio != null
      ? `market cap ÷ public float = ${c.ratio}× (float $${Number(c.float_usd).toLocaleString()} measured ${esc(c.float_measured)})`
      : "";
    return `<div class="srow"><div class="sname">${esc(c.form)} ${esc(c.period)}</div>
      <div class="scond">${detail}${c.note ? `<div class="greynote">${esc(c.note)}</div>` : ""}</div>
      <div class="sstate"><span class="chip ${cls}">${txt}</span></div></div>`;
  }).join("");
  return `<div class="ghead" style="margin-top:18px"><h3 style="font-size:13px">Price × shares vs public float</h3>
    <span>${cc.summary.ran} ran · ${cc.summary.skipped} could not run</span></div>
    <p class="hint" style="margin:6px 0 0">Each 10-K states its own public float — the company's price × shares for
    non-affiliate holders. Comparing it against this tool's price × shares catches adjusted-price, split-basis,
    currency and share-class errors in one shot. Market cap should sit at or above float.</p>
    <div class="slist">${rows}</div>`;
}

/* --------------------------------------------------- config: shared bits */
/* Block scalars arrive with hard wraps: collapse single newlines, keep
   paragraph breaks. */
const prose = (t) => !t ? "" : String(t).trim().split(/\n{2,}/)
  .map((p) => `<p>${esc(p).replace(/\n/g, " ")}</p>`).join("");
const oneline = (t) => esc(String(t == null ? "" : t).trim().replace(/\s+/g, " "));

/* ------------------------------------------------- config: strategy page */
/* What a strategy has no state for at all.

   The states list reads as a menu of things that might happen, and for a
   strategy that has deliberately given one of them up that is the wrong
   impression in the direction that matters: somebody watching a holding
   double and waiting to be told to trim it would wait forever, and nothing
   on the page would say so.

   Derived from the host's own render types against what the bundle declares,
   so no strategy is named here and none could be. A strategy that adds a
   state later loses the line about it without a word of this changing.

   Host-only types are left out. Nothing a strategy declares could ever reach
   one, so listing it would report the contract's own shape as a position this
   strategy has taken — under a heading that is true of everything beside it,
   which is exactly where a reader would believe it. The flag comes off the
   host's table rather than from a list of ids here; a view that recognised a
   render type by name is the hardcoding principle 9 refuses. */
function neverSays(st) {
  const has = new Set((st.states || []).map((s) => s.render));
  const missing = Object.entries(S.render_types || {})
    .filter(([id, t]) => !has.has(id) && !t.host_only)
    .map(([, t]) => t.meaning).filter(Boolean);
  if (!missing.length) return "";
  return `<div class="notice quiet" style="margin-top:14px">
    <h4>What it will never say</h4>
    <p>This strategy has no verdict at all that means:
    <b>${missing.map(esc).join("</b>, <b>")}</b>. Not "it has not come up
    yet" — there is nothing here that could reach it. Where another strategy
    would have that verdict, this one has taken a settled position instead,
    and its summary above says what that position is.</p></div>`;
}

/* The kinds of company this strategy says it does not evaluate.

   It earns a section rather than a footnote because it is the one thing on
   this screen that changes what a whole category of security does, and
   because a reader who meets it for the first time as a verdict has no way to
   tell a considered boundary from a gap nobody got to. Two sentences per
   kind: what the host means by it, which is the same for every strategy, and
   why THIS one has nothing to say, which is not.

   Nothing here is hardcoded — a strategy that declines nothing renders no
   section, and a kind the host learns to name arrives with its own words. */
function wontEvaluate(st) {
  const list = st.declines || [];
  if (!list.length) return "";
  return `<section class="group" style="margin-top:26px">
    <div class="ghead"><h3>What it will not evaluate</h3>
      <span>${list.length} kind${list.length === 1 ? "" : "s"} of company</span></div>
    <p class="hint" style="margin:8px 0 0">These are not verdicts and they are not opinions about whether such
    companies are worth owning. They are this strategy saying its own measures do not describe them, and choosing
    to say so rather than produce a number it cannot stand behind. A security of one of these kinds reads
    <b>outside these rules</b>, asks nothing of you, and never blocks you recording whatever you decide to do.</p>
    <div class="plist" style="margin-top:12px">${list.map((d) => `<div class="pentry">
      <div class="pe-head"><b>${esc(d.label)}</b><code>${esc(d.class)}</code></div>
      <div class="pe-sub">${esc(d.means)}</div>
      <div class="pe-why">${prose(d.because)}</div>
      <details class="whybox"><summary>Why this kind is different</summary>${prose(d.explain)}</details>
    </div>`).join("")}</div></section>`;
}

/* What the METHOD asks for or admits to that this program does not do.

   Different from the section above it, and the distinction is the point.
   That one is about a kind of COMPANY these rules cannot read. This is about
   the method itself: something its own author said was part of it which a
   journal evaluating one security at a time does not do.

   It sits high on the page, above the states, because it changes how
   everything under it should be read — a verdict is worth less than it
   looks if the method it came from was never a promise about one security.
   Every one of these methods is a portfolio method with an expected rate of
   losers built in, and saying nothing about that is not neutral: it is the
   screen quietly implying the opposite.

   Nothing here is hardcoded and nothing here does anything. A strategy that
   declares no limits renders no section, and the host neither reads these
   nor acts on them. */
function worksFromAList(st) {
  const d = st.list;
  if (!d) return "";
  return `<section class="group" style="margin-top:26px">
    <div class="ghead"><h3>${esc(d.label)}</h3><span>where the buying comes from</span></div>
    <p class="hint" style="margin:8px 0 0">${prose(d.explain)}</p>
    <div class="pe-sub" style="margin-top:10px">Pulled from ${esc(d.source.name)}. ${
      d.source.reasoning ? "That description is theirs."
                         : "The description above is this strategy's own."}</div>
    <div class="toolbar" style="margin-top:12px">
      <button class="btn" data-act="list">Open the list</button></div>
  </section>`;
}

function methodLimits(st) {
  const list = st.limits || [];
  if (!list.length) return "";
  return `<section class="group" style="margin-top:26px">
    <div class="ghead"><h3>What this method does not promise</h3>
      <span>${list.length} thing${list.length === 1 ? "" : "s"} to know</span></div>
    <p class="hint" style="margin:8px 0 0">These are not faults in the rules and they are not reasons to distrust
    a verdict. They are the parts of the method that a journal looking at one security at a time cannot carry —
    said here rather than left for you to discover, because a screen that stays silent about them is quietly
    promising something the method never did.</p>
    <div class="plist" style="margin-top:12px">${list.map((l) => `<div class="pentry">
      <div class="pe-head"><b>${esc(l.title)}</b></div>
      <div class="pe-why">${prose(l.body)}</div>
    </div>`).join("")}</div></section>`;
}

/* Read-only, on purpose. A strategy is edited where it lives — as code and a
   values file beside it — and every change is caught and recorded here
   whether or not it came through this app. */
function strategyView() {
  const st = S.strategy;
  let h = pendingBanner();
  if (!st) {
    const m = S.strategy_missing || {};
    return h + missingStrategyBanner() + `<div class="sheet"><div class="empty">
      <p>This journal is stamped with <b>${esc(m.name || m.id)}</b> v${esc(m.version)}, which is not installed
      on this machine. Put the bundle back in the strategies folder and it will be picked up.</p></div></div>`
      + ruleChangeHistory();
  }
  h += cfgErrorBox(st.value_errors || []);
  const stamp = S.journal.strategy || {};
  h += `<div class="rollup"><h3>${esc(st.name)}
      <span class="dim" style="font-family:var(--mono);font-size:11px">v${esc(st.version)}${
        st.values_version != null ? ` · settings v${esc(st.values_version)}` : ""} · contract ${esc(st.contract)}</span></h3>
    <div class="pe-desc">${prose(st.summary)}</div>
    <div class="pe-sub-block"><i>This journal</i><p>Created ${esc(String(S.journal.created).slice(0, 10))} against
      ${esc(stamp.name)} v${esc(stamp.version)} · settings v${esc(stamp.values_version)}. It cannot be changed —
      a second strategy means a second journal, the way it would mean a second account.</p></div>
    <div class="pe-sub-block"><i>Bundle</i><p><code>${esc(st.bundle)}</code>${
      (st.reference || []).length ? ` · ships ${st.reference.map((r) => `<code>${esc(r)}</code>`).join(", ")}` : ""}</p></div>
  </div>`;

  h += worksFromAList(st);
  h += methodLimits(st);

  h += `<section class="group" style="margin-top:26px"><div class="ghead"><h3>What it can say</h3>
    <span>${st.states.length} state${st.states.length === 1 ? "" : "s"}</span></div>
    <p class="hint" style="margin:8px 0 0">Every verdict this journal produces is one of these, and only one —
    a decision resolves to a single state rather than several systems each reaching their own conclusion.
    <b>This is the list of what it <i>can</i> say, not a list of what it will.</b> A strategy may go years
    without reaching some of these, and one or two may never come up in your journal at all. That is the
    strategy having a settled view, not the tool failing to notice something.</p>
    <div class="slist" style="margin-top:12px">${st.states.map((s) => `<div class="srow">
      <div class="sname">${esc(s.name)}</div>
      <div class="scond">${prose(s.description)}</div>
      <div class="sstate"><span class="chip s-${RENDER_TONE[s.render] || "none"}">${
        esc(((S.render_types || {})[s.render] || {}).meaning || "")}</span></div>
    </div>`).join("")}</div>${neverSays(st)}</section>${wontEvaluate(st)}`;

  if ((st.inputs || []).length) {
    const problems = st.input_problems || [];
    h += `<section class="group" style="margin-top:26px"><div class="ghead"><h3>What it asked you</h3>
      <span>${problems.length ? "something is still owed" : "answered in this journal"}</span></div>
      <p class="hint" style="margin:8px 0 0">Things no strategy could ship a sensible default for, because they
      are facts about your account rather than opinions about investing. They can be changed whenever they change
      — a figure like your free cash is expected to move — and every edit is dated on the record below.</p>
      ${problems.length ? `<div class="notice"><h4>Answers still needed</h4>
        ${problems.map((p) => `<p>${esc(p)}</p>`).join("")}
        <p class="hint">Until these are answered this journal produces no verdicts, only a note saying what is
        missing. Nothing already recorded is affected, and recording a decision is never blocked by it.</p></div>` : ""}
      <div class="plist" style="margin-top:12px">${st.inputs.map((f) => `<div class="pentry">
        <div class="pe-head"><b>${esc(f.label)}</b><code>${esc(f.id)}</code>
          ${f.required ? '<span class="req">required</span>' : ""}
          ${f.role ? `<span class="req" title="${esc(((st.roles || {})[f.role] || {}).means || "")}">the journal reports this</span>` : ""}</div>
        <div class="pe-desc">${prose(f.explain)}</div>
        ${f.inactive
          ? `<div class="pe-param"><span class="chip blank">not asked</span>
             <span class="dim">${esc(f.inactive)}</span></div>`
          : `<div class="pe-param">${f.value === null || f.value === undefined
              ? '<span class="chip blank">not answered</span>'
              : `<b>${esc(declaredText(f, f.value))}</b>`}</div>`}
      </div>`).join("")}</div>
      <div class="toolbar" style="justify-content:flex-start;margin-top:12px">
        <button class="btn primary" data-act="settings">Change these answers</button></div></section>`;
  }

  if ((st.values || []).length) {
    h += `<section class="group" style="margin-top:26px"><div class="ghead"><h3>Its settings</h3>
      <span>shipped defaults, and what this journal uses</span></div>
      <p class="hint" style="margin:8px 0 0">Numbers the strategy has an opinion about and ships a default for.
      Changing one changes what every future verdict in this journal means, so a change is recorded with the
      before and after and asks you to say why.</p>
      <div class="plist" style="margin-top:12px">${st.values.map((v) => `<div class="pentry">
        <div class="pe-head"><b>${esc(v.label)}</b><code>${esc(v.id)}</code>
          <span class="req">${esc(v.unit || v.type)}</span></div>
        <div class="pe-desc">${prose(v.explain)}</div>
        ${valueSource(v)}
        <div class="pe-param"><b>${esc(fmtUnit(v.value, v.unit || (v.type === "boolean" ? "yes_no" : "none")))}</b>
          <span class="dim">${v.set_by === "shipped default" ? "shipped default"
            : `set by ${esc(v.set_by)} — shipped default ${esc(String(v.shipped))}`}</span></div>
      </div>`).join("")}</div>
      <div class="toolbar" style="justify-content:flex-start;margin-top:12px">
        <button class="btn" data-act="settings">Change these settings</button></div></section>`;
  }

  h += ruleChangeHistory() + inputChangeHistory();
  if ((S.refused || []).length) {
    h += `<div class="rollup" style="margin-top:26px"><h3>Strategies that would not load</h3>
      <p>These bundles are on this machine and were refused. A refused strategy is skipped with its reason and
      never prevents another from loading.</p>
      <ul class="pe-nmw">${S.refused.map((r) => `<li><code>${esc(r.bundle)}</code>
        ${(r.errors || []).map((e) => `<div class="greynote">${esc(e)}</div>`).join("")}</li>`).join("")}</ul></div>`;
  }
  /* A pointer, not the documentation. A strategy is written in an editor and
     the reference is for someone with the engine open beside it — putting a
     tab of it in here would charge the complexity to a reader who will never
     write one, which is the whole audience this program is for. What this
     screen owes is that somebody who wants to know where to look is not left
     guessing. */
  h += `<div class="rollup" style="margin-top:26px"><h3>Writing your own</h3>
    <p>A strategy is a folder of code and a file of numbers, written in an editor rather than in here.
    Nothing on this page needs it: the strategies that come with this program are meant to be enough,
    and one of them governs this journal already.</p>
    <p>If you do want to write one, the reference is <code>docs/WRITING-A-STRATEGY.md</code> in this
    program's source — what a strategy declares, what it is handed, what it must return and what it
    may never do — with a complete worked example beside it in <code>docs/example-strategy/</code>.
    A new strategy is picked up by being put in the <code>strategies</code> folder; there is no list
    in here to add it to.</p></div>`;
  return h;
}

/* Where a threshold came from, and whose reasoning the explanation above is.
   Rendered from the declaration, never written by hand into the explanation:
   the version that lived in prose could be stated once for a whole file and
   silently fail to cover the value added afterwards, and a reader auditing a
   number had no way to tell which kind of claim they were reading. */
function valueSource(v) {
  const s = v.source;
  if (!s || !s.name) return "";
  return `<div class="greynote">Level from ${esc(s.name)}. ${s.reasoning
    ? "The explanation above is theirs too."
    : "The explanation above is this strategy's own account of it, not theirs."}</div>`;
}

/* One declared field's answer, as words. A choice reads as its label, never
   as the value the strategy stores — "Building positions" beats "building". */
function declaredText(spec, value) {
  const opt = (spec.options || []).find((o) => o.value === value);
  if (opt) return opt.label;
  if (spec.type === "boolean") return value ? "Yes" : "No";
  return fmtUnit(value, spec.unit || (spec.type === "text" ? "text" : "none"));
}

/* Answers are not rules, so they get their own record: dated, before and
   after, and nothing owed. They are here because they feed figures a
   strategy binds on, and an answer that could be quietly adjusted the day
   before a purchase is worth being able to see afterwards. */
function inputChangeHistory() {
  const hist = (S.input_changes || []).slice().reverse();
  if (!hist.length) return "";
  return `<div class="rollup" style="margin-top:26px"><h3>Answers you changed</h3>
    <p>What you told this journal, and when it moved. These are facts about your account rather than rules, so no
    reason is asked for — but the verdicts that used the old answer are frozen in the record beside the purchases
    they belong to, and are never rewritten to match.</p>
    <ul class="histlist">${hist.map((c) => `<li><b>#${c.seq}</b>
      <span><div class="histchanges">${(c.moved || []).map((m) => esc(movedLine(m))).join("<br>")}</div></span>
      <time>${esc(String(c.seen).slice(0, 10))}</time></li>`).join("")}</ul></div>`;
}

function ruleChangeHistory() {
  const hist = (S.rule_changes || []).slice().reverse();
  return `<div class="rollup" style="margin-top:26px"><h3>Rule changes</h3>
    <p>A strategy is edited where it lives, so changes happen outside this app. Every one is recorded the moment
    it is seen — what moved, and when. A change to a setting is recorded as a before and after, because the
    number means something on its own; a change to the logic cannot be, so what is recorded is the author's own
    account of it. The record is append-only: entries are never edited or removed.</p>
    <ul class="histlist">${hist.map((c) => `<li><b>#${c.seq}</b>
      <span>${(c.moved || []).length
        ? `<div class="histchanges">${c.moved.map((m) => esc(movedLine(m))).join("<br>")}</div>` : ""}
        ${(c.changelog || []).length ? `<div class="histchanges">${c.changelog.map(esc).join("<br>")}</div>` : ""}
        ${(c.notes || []).map((n) => `<div class="greynote">${esc(n)}</div>`).join("")}
        ${c.reason ? esc(c.reason) : c.reason_owed
          ? `<span class="neg">No reason recorded yet.</span>
             <button class="btn" data-act="explain" data-seq="${c.seq}">Write the reason</button>`
          : '<span class="dim">Recorded from the strategy\'s own changelog — nothing is owed from you.</span>'}</span>
      <time>${esc(String(c.seen).slice(0, 10))}</time></li>`).join("")
      || "<li><span>Nothing has changed since this journal was created.</span></li>"}</ul></div>`;
}

/* -------------------------------------------------- config: metrics page */
async function loadBank() {
  if (C.loadingBank) return;
  C.loadingBank = true;
  const r = await apiRaw("get_bank");
  if (r.ok === false) C.bankErr = r.error;
  else C.bank = r.bank;
  C.loadingBank = false;
  if (tab === "metrics") render();
}

function metricsView() {
  if (C.bankErr) return cfgErrorBox([C.bankErr]);
  if (C.bank === null) {
    loadBank();
    return '<div class="sheet"><p class="empty">Reading the metric bank…</p></div>';
  }
  return `<div class="toolbar" style="justify-content:space-between;align-items:center">
      <input id="banksearch" class="search" type="search" value="${esc(C.search)}"
        placeholder="Search ${C.bank.entries.length} measures…" aria-label="Search measures">
      <span class="dim" id="bankcount" style="font-family:var(--mono);font-size:11px">${bankCountText()}</span>
    </div>
    <p class="hint" style="margin:0 0 14px">The bank defines what each value <em>is</em>.
    No thresholds appear here because none exist here — every level belongs to a strategy.</p>
    <div id="banklist">${bankListHTML()}</div>`;
}

function bankCountText() {
  const total = C.bank.entries.length, shown = bankFiltered().length;
  return shown === total ? `${total} entries` : `${shown} of ${total} entries`;
}
function bankFiltered() {
  const q = C.search.trim().toLowerCase();
  if (!q) return C.bank.entries;
  return C.bank.entries.filter((e) => {
    const hay = [e.id, e.label, e.kind, e.unit,
      e.explanation && e.explanation.plain,
      e.explanation && e.explanation.attribution,
      e.derivation && e.derivation.formula, e.question,
    ].filter(Boolean).join(" ").toLowerCase();
    return hay.includes(q);
  });
}
function bankListHTML() {
  const list = bankFiltered();
  if (!list.length) return `<div class="sheet"><div class="empty">
    <p>No measure matches “${esc(C.search)}”. Try part of a name or an id.</p></div></div>`;
  return `<div class="plist">${list.map(bankCard).join("")}</div>`;
}

/* The units whose id does not read as words. An unglossed token on a page
   whose whole job is explaining what a value is teaches the wrong thing. */
const UNIT_WORD = {
  yes_no: "pass or fail",
  percentage_points: "percentage points",
  times_own_median: "times its own median",
};

/* How a measure is READ, which is not what it measures. It decides how much
   evidence a breach of somebody's level needs, so a reader who sees an exit
   fire on one reading has to be able to find out why here. The words are the
   host's own (engine/contract.py, ESTIMATORS) said in plain language. */
const ESTIMATOR_WORD = {
  instant: "read at one date",
  trailing: "a trailing window",
  endpoint: "two readings, one at each end",
  averaged: "means at both ends",
  median: "the middle of a window",
  range: "the spread across a window",
  count: "a count of annual reports",
  assessed: "assessed, not measured",
};

function bankCard(e) {
  const pol = e.polarity === "higher_is_better" ? "higher is better"
    : e.polarity === "lower_is_better" ? "lower is better"
    : e.polarity === "none" ? "no favourable direction" : null;
  const x = e.explanation || {};
  let h = `<div class="pentry">
    <div class="pe-head"><b>${esc(e.label || e.id)}</b><code>${esc(e.id)}</code>
      <span class="req">${esc(e.kind || "")}</span>
      ${pol ? `<span class="req">${esc(pol)}</span>` : ""}
      ${e.unit ? `<span class="req">${esc(UNIT_WORD[e.unit] || e.unit)}</span>` : ""}
      ${e.estimator ? `<span class="req">${esc(ESTIMATOR_WORD[e.estimator.kind] || e.estimator.kind)}</span>` : ""}</div>`;
  if (x.plain) h += `<div class="pe-desc">${prose(x.plain)}</div>`;
  if (e.polarity_note) h += `<div class="pe-block"><i>Why no direction</i>
    <div class="pe-why" style="margin-top:0">${prose(e.polarity_note)}</div></div>`;

  if (e.derivation) {
    h += `<div class="pe-block"><i>How it is derived</i>
      <pre class="pe-formula">${esc(String(e.derivation.formula || "").trim())}</pre>
      ${e.derivation.window ? `<div class="pe-sub">window: ${oneline(e.derivation.window)}</div>` : ""}</div>`;
  }
  if (e.question) {
    h += `<div class="pe-block"><i>The question you answer</i>
      <div class="pe-why" style="margin-top:0">${prose(e.question)}</div>
      ${e.response ? `<div class="pe-sub">prose ${esc(e.response.prose)} ·
        marked ${esc((e.response.marks || []).join(" or "))} ·
        unmarked = ${esc(e.response.unmarked)}</div>` : ""}
      <div class="pe-sub">Answered per security, under <i>Your judgement</i> on
      that security's page, whenever your strategy reads it. The record is
      append-only and dated: changing your mind adds an entry, and nothing is
      ever edited.</div></div>`;
  }
  if (e.parameters && e.parameters.length) {
    h += `<div class="pe-block"><i>Declared parameters — no strategy can supply one yet</i>${
      e.parameters.map((p) => `<div class="pe-param"><code>${esc(p.id)}</code>
        ${p.unit ? `<span class="dim">${esc(p.unit)}</span>` : ""}
        ${p.means ? `<div class="pe-why" style="flex-basis:100%">${prose(p.means)}</div>` : ""}</div>`).join("")}
      <p class="hint">This measure reports absent everywhere until the contract gains a way to hand one in.</p></div>`;
  }
  if (e.not_meaningful_when && e.not_meaningful_when.length) {
    /* Three kinds of condition, refused by three different things — and one
       of them refused by nothing at all, which is the whole reason the host
       hands the sentence over rather than letting this decide. There was a
       two-way ternary here: an industry condition got its own paragraph and
       everything else got "refused by the calculation itself, from the
       figures". That is true of a `data` condition and the exact inverse of
       an `undetected` one, where neither this program nor the figures can
       tell — so the reader was told the program had checked something it
       cannot check, with the condition's own text rendering blank beside it.

       `t.form.means` is the host's sentence for whichever form this is, and
       `t.needs` is what it would take to settle one nobody can. The view
       knows the shape and never the vocabulary. */
    h += `<div class="pe-block"><i>Not meaningful when</i><ul class="pe-nmw">${
      e.not_meaningful_when.map((t) => {
        const form = t.form || {};
        const what = form.id === "industry"
          ? `the company is ${(t.industry || []).map((c) => `<b>${esc(c.label)}</b> <span class="dim">(${esc(c.means)})</span>`).join(", or ")}`
          : oneline(t.states);
        return `<li>${what}
          <div class="pe-sub">${esc(form.means || "")}</div>${
          t.because ? `<div class="pe-why" style="margin-top:4px">${prose(t.because)}</div>` : ""}${
          t.needs ? `<div class="pe-sub" style="margin-top:4px"><b>What would settle it:</b> ${prose(t.needs)}</div>` : ""}</li>`;
      }).join("")}</ul></div>`;
  }
  if (x.misfires || x.attribution) {
    h += `<details class="whybox"><summary>Where it misfires · where it comes from</summary>
      ${x.misfires ? `<div class="pe-why">${prose(x.misfires)}</div>` : ""}
      ${x.attribution ? `<div class="pe-sub" style="margin-top:8px">${oneline(x.attribution)}</div>` : ""}</details>`;
  }
  return h + "</div>";
}

/* ------------------------------------------------------------------ data */
function dataView() {
  const sec = S.data_security || {};
  const storage = sec.storage || {};
  const keyStatus = sec.key_configured
    ? `A key is configured — stored in ${esc(storage.where || "the OS credential store")}. It is never shown again, never exported, and never written to a journal.`
    : "No key is stored. Filing measures still compute; price-dependent ones say why they can't.";
  const unencryptedNote = storage.unencrypted
    ? `<p class="hint"><b>This platform offers no credential vault</b>, so the key is stored <b>unencrypted</b> at
       <code>${esc(storage.where)}</code> with owner-only file permissions. That is an honest fallback, not protection
       against someone using this account.</p>` : "";
  const secProblem = sec.problem
    ? `<div class="notice"><h4>Credential store problem</h4><p>${esc(sec.problem)}</p></div>` : "";
  const set = S.journal.settings || {};
  return `<div class="cards">
    <div class="panel"><h3>Data sources</h3><div class="sub">SEC EDGAR filings · Tiingo prices</div>
      <p class="hint" style="margin-top:0">Filings come straight from SEC EDGAR — free, no key, but the SEC
      requires every automated tool to identify itself with a name and a monitored email, and blocks the
      anonymous ones. Prices come from Tiingo under your own free API key (tiingo.com). Fetching happens only
      when you press Fetch data, and hand-entered values are never overwritten by anything fetched. Filings and
      prices are shared by every journal — they are public facts about a company, not part of any record.</p>
      ${secProblem}
      <div class="field"><label for="ds_ident">SEC identity — name and email</label>
        <input id="ds_ident" type="text" value="${esc(sec.sec_identity || "")}" placeholder="Jane Doe jane@example.com">
        <div class="help">Sent as the User-Agent on every EDGAR request. Kept on this machine only — it is personal
        information, so it never rides along in an export bundle.</div></div>
      <div class="toolbar" style="justify-content:flex-start;margin:0 0 14px">
        <button class="btn" data-act="save-identity">Save identity</button></div>
      <div class="field"><label for="ds_token">Tiingo API key</label>
        <div class="help" style="margin:0 0 6px">${keyStatus}</div>
        <input id="ds_token" type="password" autocomplete="off" value="" placeholder="${sec.key_configured ? "paste a replacement key" : "paste your key"}">
        <div class="help">To rotate: generate a new key at tiingo.com/account/api/token, paste it here, save. The old
        key stops working the moment Tiingo regenerates it.</div></div>
      ${unencryptedNote}
      <div class="toolbar" style="justify-content:flex-start;margin-top:8px">
        <button class="btn primary" data-act="save-key">Save key</button>
        <button class="btn" data-act="test-key" ${sec.key_configured ? "" : "disabled"}>Test key</button>
        <button class="btn danger" data-act="remove-key" ${sec.key_configured ? "" : "disabled"}>Remove key</button></div></div>

    <div class="panel"><h3>Valuation defaults</h3><div class="sub">Set once · prefills every expected-value calculation in this journal</div>
      <p class="hint" style="margin-top:0">These are standing assumptions, not per-stock levers. Changing one moves
      every valuation at once — which is the point: a rate tuned for a single stock is a rationalisation, not a
      requirement. Each calculation can still override, and the record says so when it does.</p>
      <div class="field"><label for="vd_dr">Discount rate %</label>
        <input id="vd_dr" type="number" step="any" value="${esc(set.discount_rate ?? "")}">
        <div class="help">Your required annual return. Derive it once: start from the 10-year Treasury yield — the
        return for taking no risk — and add 4 to 6 points for owning a business instead. Most long-term investors
        land between 8 and 12.</div></div>
      <div class="field"><label for="vd_tg">Terminal growth %</label>
        <input id="vd_tg" type="number" step="any" value="${esc(set.terminal_growth ?? "")}">
        <div class="help">Long-run growth after the forecast years. Inflation plus a little — 2 to 3 — is the
        defensible range. Above about 3 you are claiming the company outgrows the economy forever.</div></div>
      <div class="field"><label for="vd_mos">Margin of safety %</label>
        <input id="vd_mos" type="number" step="any" value="${esc(set.margin_of_safety ?? "")}">
        <div class="help">Graham's traditional number is 30. It is room to be wrong, not a return target — the wider
        your uncertainty, the wider it should be.</div></div>
      <div class="toolbar" style="justify-content:flex-start;margin-top:8px">
        <button class="btn primary" data-act="save-valuation">Save defaults</button></div></div>

    <div class="panel"><h3>Sample journals</h3><div class="sub">Invented companies and invented figures</div>
      <p class="hint" style="margin-top:0">Creates separate journals of made-up companies so you can see what a
      journal looks like once it has been used — a holding with nothing to do, one that crossed a sell line and is
      waiting for a second filing before anything happens, one whose balance sheet came apart, one that grew to
      half the account, a business that quietly stopped being worth owning, a verdict that refuses to decide until
      you have answered something, a purchase made against the signal and one made without one.
      Nothing in any of them is a real company or a recommendation.</p>
      <p class="hint">There is one per strategy, because a journal has exactly one strategy and it does not
      change. Loading them together is the quickest way to see what that costs and what it buys: the same kind of
      company gets opposite verdicts from them, and neither is wrong. Nothing already here is touched.</p>
      <div class="toolbar" style="justify-content:flex-start;margin-top:16px">
        <button class="btn" data-act="sample">Load sample journals</button></div></div>

    <div class="panel"><h3>Back up</h3><div class="sub">Export to a folder you control</div>
      <p class="hint" style="margin-top:0">Writes one timestamped file containing every journal — positions, notes,
      snapshots, the strategy each is stamped with and its rule-change record. Put it wherever you keep backups.
      Nothing is uploaded anywhere. Your API key and SEC contact are not in it, and cannot be.</p>
      <div class="toolbar" style="justify-content:flex-start;margin-top:16px">
        <button class="btn primary" data-act="export">Export</button>
        <button class="btn" data-act="import">Import</button></div></div>

    <div class="panel"><h3>Where your data lives</h3><div class="sub">Outside the project folder</div>
      <p class="hint" style="margin-top:0"><code>${esc(S.data_dir)}</code></p>
      <p class="hint">Deliberately not inside the repository. Cloning or pushing the code can never carry your
      positions, notes or ideas with it.</p>
      <p class="hint">Set the <code>LEDGER_DATA</code> environment variable to move it, for instance onto a synced drive.</p>
      <div class="toolbar" style="justify-content:flex-start;margin-top:16px">
        <button class="btn danger" data-act="clear">Empty this journal</button></div></div>
  </div>`;
}

/* ------------------------------------------------------------ no journal */
function welcomeView() {
  const n = (S.strategies || []).length;
  /* A journal that could not be read never leaves the window blank: the list
     is still here, so the way out is to open a different one. */
  let h = S.journal_problem
    ? `<div class="notice"><h4>That journal could not be read</h4>
       <p>${esc(S.journal_problem)}</p>
       <p>Nothing has been written to it. Open another journal below, or fix
       the file and reopen this one.</p></div>` : "";
  h += `<div class="sheet"><div class="empty">
    <h2 style="margin:0 0 8px">${S.journal_problem ? "Or start a new one" : "Start a journal"}</h2>
    <p>A journal is created against one strategy and stays there. It is what every decision in it will be
    judged by, chosen now while you are calm rather than in the moment you want to act.</p>
    ${n ? `<button class="btn primary" data-act="newjournal">Create a journal</button>`
      : `<p class="neg">No strategy would load, so there is nothing to create a journal against.</p>`}
  </div></div>`;
  if ((S.refused || []).length) {
    h += `<div class="rollup" style="margin-top:26px"><h3>Strategies that would not load</h3>
      <ul class="pe-nmw">${S.refused.map((r) => `<li><code>${esc(r.bundle)}</code>
        ${(r.errors || []).map((e) => `<div class="greynote">${esc(e)}</div>`).join("")}</li>`).join("")}</ul></div>`;
  }
  if ((S.journals || []).length) {
    h += `<div class="toolbar" style="margin-top:20px">${journalBar()}</div>`;
  }
  return h;
}

/* ------------------------------------------------- where capital goes ---- */
/* One question — "I have money, where does it go" — asked across the whole
   journal instead of one security at a time.

   Every figure here comes off the backend's own allocation view. Nothing is
   ranked, scored or converted in this file: the ordering is the amount each
   position may take, descending, worked out against the same account value
   every verdict on every other screen was measured against. Where a figure
   could not be reached it arrives absent with the host's reason, and the
   entry is shown unordered rather than given a made-up place in the list. */

const allocAmount = (a) => (a && a.status === "known")
  ? `<b>${esc(fmtUnit(a.value, "usd"))}</b>`
  : `<span class="chip blank">not known</span>`;

const allocWhy = (a) => (a && a.status !== "known")
  ? `<div class="greynote">${esc(a.reason)}</div>` : "";

const allocProv = (a) => (a && a.status === "known")
  ? (a.provenance || []).map((p) => `<div class="greynote">${esc(p)}</div>`).join("")
  : "";

/* One line for a position that may take capital. The action is the same
   recording dialog the security page uses, so a purchase started here is
   captured exactly as any other is — the same frozen decision, the same
   override capture where it is one. */
function allocEntry(e) {
  const cond = e.condition
    ? `<div class="greynote">Held back until ${esc(e.condition.summary)}. Your
       strategy will offer it as the size in front of you on the day it
       decides that has happened.</div>` : "";
  /* "May go in now" is only true where nothing is holding it back. A
     conditioned commit is sized and waiting, and labelling its figure as
     going in now would contradict the heading it renders under. */
  const shape = [
    ["Already in", e.committed],
    [e.condition ? "Would go in" : "May go in now", e.amount],
    ["Held back", e.plan ? e.plan.held_back : null],
    ["Whole position", e.target],
  ].filter(([, v]) => v).map(([label, v]) =>
    /* An em-dash with the reason thrown away is the absence rule failing at
       the last inch: the host worked out precisely why each of these could
       not be reached, and a dash tells the reader only that something is
       missing. The reason rides in the title, the way every other bare
       figure on these screens carries its own. */
    `<div class="fact" ${v.status === "known" ? "" :
      `title="Not known: ${esc(v.reason)}"`}><i>${esc(label)}</i><b>${
      v.status === "known" ? esc(fmtUnit(v.value, "usd")) : "—"}</b></div>`)
    .join("");

  return `<div class="pentry">
    <div class="alloc-head">
      <div><b><button class="linkish" data-act="opensec" data-t="${esc(e.ticker)}">${esc(e.ticker)}</button></b>
        <span class="dim">${esc(e.name || "")}</span>
        <div class="dim">${esc(e.state.name)} · ${esc(e.summary)}</div></div>
      <div class="alloc-amt">${allocAmount(e.amount)}
        <div class="dim">${esc(sizeText(e.size))}</div></div>
    </div>
    ${allocWhy(e.amount)}${allocProv(e.amount)}${cond}
    <div class="facts">${shape}</div>
    ${e.plan ? planText(e.plan.tranches) : ""}
    <div class="toolbar"><button class="btn primary" data-act="buy"
      data-t="${esc(e.ticker)}">${e.held ? "Record a purchase — adding to it"
        : "Record a purchase"}</button></div>
  </div>`;
}

/* The securities the strategy will not put capital into, each with the rule
   that turned it down.

   Listed rather than hidden, for two reasons. "Your strategy said no to
   eleven names today" is the useful half of an empty screen — it is the
   evidence that the rules are working rather than that something failed to
   load. And a purchase made against the signal has to be recordable from
   somewhere: the tool records decisions and never blocks them, and this is
   the only screen a purchase into a name you already hold can start from. */
function allocExcluded(e) {
  return `<div class="pentry">
    <div class="alloc-head">
      <div><b><button class="linkish" data-act="opensec" data-t="${esc(e.ticker)}">${esc(e.ticker)}</button></b>
        <span class="dim">${esc(e.name || "")}</span>
        <div class="dim">${esc(e.summary)}</div></div>
      <div><span class="chip ${"s-" + (RENDER_TONE[e.render] || "none")}">${esc(e.state.name)}</span></div>
    </div>
    <div class="toolbar"><button class="btn danger" data-act="buy"
      data-t="${esc(e.ticker)}">Record a purchase against this</button></div>
  </div>`;
}

/* ------------------------------------------------------------- the list */
/* Everything here comes off `S.list`, which the host builds only for a
   journal whose strategy declared that it works from one. Nothing in this
   file knows what a Magic Formula is, what a ranking is, or how old is too
   old — the strategy's own label and explanation head the screen, and every
   verdict beside a name is the one the strategy already produced. */

function importedListRow(r) {
  const skip = r.passed_over;
  const state = r.decision
    ? stateStamp(r.decision)
    : '<span class="chip blank" title="This name is not in the journal yet, so nothing has been evaluated about it">not looked at</span>';
  /* Held names get no buttons. The list's job is done for them — what
     happens next is the clock, and that lives on the security's own page. */
  const acts = r.held ? ""
    : `<button class="btn" data-act="listadd" data-t="${esc(r.ticker)}">${
        r.tracked ? "Open" : "Track this"}</button>`
      + (skip ? "" : `<button class="btn" data-act="passover" data-t="${esc(r.ticker)}">Not buying this one</button>`);
  return `<div class="pentry">
    <div class="pe-head"><b>${esc(r.ticker)}</b>${
      r.name && r.name !== r.ticker ? `<span class="dim">${esc(r.name)}</span>` : ""}
      ${r.new ? '<span class="chip blank" title="This name was not on the list before this one">new</span>' : ""}
      ${r.held ? '<span class="chip s-pass">held</span>' : ""}
      <span class="req">${state}</span></div>
    ${skip ? `<div class="pe-why"><b>You passed on this one</b> on ${
      esc(String(skip.recorded).slice(0, 10))}: ${esc(skip.reason)}</div>` : ""}
    ${acts ? `<div class="toolbar">${acts}</div>` : ""}
  </div>`;
}

function importedListView() {
  const L = S.list;
  const d = L.declared;
  let h = `<section class="group">
    <div class="ghead"><h3>${esc(d.label)}</h3>${
      L.current ? `<span>${(L.current.tickers || []).length} names</span>` : ""}</div>
    <p class="hint">${prose(d.explain)}</p>
    <div class="pe-sub">Pulled from ${esc(d.source.name)}. ${
      d.source.reasoning
        ? "That description is theirs."
        : "The description above is this strategy's own."}</div>`;

  if (!L.current) {
    /* An empty state that invites the action, and says the one thing a
       reader needs to know before taking it: nothing here chose these. */
    h += `<div class="rollup"><div class="pe-head"><b>No list has been imported yet.</b></div>
      <div class="pe-why">Run the screen, then paste what it gives you. This
      journal records which list and what day it was pulled, and every list
      you have ever imported stays on the record — so a name's year can be
      counted from the day it was last chosen, and so a ranking you are still
      buying from a year later says how old it is.</div>
      <div class="toolbar"><button class="btn primary" data-act="importlist">Import a list</button></div>
    </div></section>`;
    return h;
  }

  const held = L.rows.filter((r) => r.held).length;
  const passed = L.rows.filter((r) => r.passed_over).length;
  h += `<div class="facts">
    <div class="fact"><i>Pulled</i><b>${esc(L.current.pulled_on)}</b></div>
    <div class="fact"><i>Imported</i><b>${esc(String(L.current.recorded).slice(0, 10))}</b></div>
    <div class="fact"><i>Held</i><b>${held} of ${L.rows.length}</b></div>
    ${L.current.floor !== null && L.current.floor !== undefined
      ? `<div class="fact"><i>Smallest asked for</i><b>${esc(fmtUnit(L.current.floor, "usd"))}</b></div>` : ""}
    ${passed ? `<div class="fact"><i>Passed over</i><b>${passed}</b></div>` : ""}
  </div>
  <p class="hint">These are the names the screen returned, in the order it
  returned them. Where each sits in its own ranking is not here and cannot
  be: a rank means nothing without the thousands of companies it was ranked
  against, and none of those are in this journal. Nothing on this screen
  ranked anything.</p>
  <div class="toolbar"><button class="btn primary" data-act="importlist">Import a fresh list</button></div>
  <div class="plist">${L.rows.map(importedListRow).join("")}</div>
  </section>`;

  if (L.history.length) {
    h += `<section class="group"><div class="ghead"><h3>Lists before this one</h3>
      <span>${L.history.length}</span></div>
      <p class="hint">Kept whole and never rewritten. What a list said on the
      day you acted on it is what your own record has to be able to show.</p>
      <div class="plist">${L.history.map((e) => `<div class="pentry">
        <div class="pe-head"><b>Pulled ${esc(e.pulled_on)}</b>
          <span class="dim">imported ${esc(String(e.recorded).slice(0, 10))} · ${
            (e.tickers || []).length} names</span></div>
        ${e.added.length ? `<div class="pe-why"><b>Came on:</b> ${esc(e.added.join(", "))}</div>` : ""}
        ${e.dropped.length ? `<div class="pe-why"><b>Came off:</b> ${esc(e.dropped.join(", "))}</div>` : ""}
      </div>`).join("")}</div></section>`;
  }
  return h;
}

function dlgImportList() {
  const d = S.list.declared;
  dialog({
    title: "Import a list",
    blurb: `Paste what ${d.source.name} gave you. Nothing is created until you confirm, and nothing already recorded changes.`,
    body: field("pulled_on", "The day you pulled it", localToday(), "Not today unless you ran the screen today. Everything about how current this ranking is measures from this day, and so does the year each position you buy from it is given.", "date", `max="${localToday()}"`)
      + field("floor", "Smallest company you asked for", "", "Optional, in dollars. Nothing reads it — it is here because \"thirty names\" means something different at a fifty-million floor than at a billion, and a reader in three years has no other way to find that out.", "number")
      + area("pasted", "The names", "", "Paste the screen's own table, or one ticker per line. Any line this cannot read comes back named, and nothing is imported until every line is readable — a list of thirty that quietly became twenty-nine looks exactly like a screen that returned twenty-nine."),
    confirm: "Import",
    onConfirm: async (v) => {
      if (!(v.pasted || "").trim()) return "Paste the names first.";
      const r = await apiRaw("import_list", v.pulled_on, v.pasted, v.floor || null);
      if (!r.ok) return r.error;
      toast(`Imported ${r.n} names, pulled ${r.pulled_on}.`);
    },
  });
}

function dlgPassOver(ticker) {
  dialog({
    title: `Not buying ${ticker}`,
    blurb: "Your own list gave you this name and your rules say to buy it. Nothing here stops you passing — this writes down that you did, and why.",
    /* `.dlg-warn`, not `.dlg-err`: dialog() reuses the first `.dlg-err` it
       finds for validation messages, so a caution written into that slot is
       replaced by "A reason is required" the first time somebody confirms an
       empty form — and never comes back. */
    body: `<div class="dlg-warn">Skipping names you do not like the look of is
      one of the three documented ways people stop getting this method's
      results. The list is the decision; second-guessing it is the deviation
      the method exists to prevent. That is not an argument against passing —
      it is the reason the reason is worth having in a year.</div>`
      + area("reason", "Why are you passing on this one?", "", "Required. One sentence. You will read this again when you find out what it did."),
    confirm: "Record it",
    danger: true,
    onConfirm: async (v) => {
      if (!(v.reason || "").trim()) return "A reason is required.";
      const r = await apiRaw("pass_over", ticker, v.reason);
      if (!r.ok) return r.error;
    },
  });
}

function allocationView() {
  const a = S.allocation;
  /* Only when the screen itself could not be built — a data layer that threw
     on the way here. A journal whose STRATEGY cannot be asked still gets a
     full allocation view, with every security listed and the host's own
     reason against each: this is the only screen a purchase into a name you
     already hold starts from, so it must not be the screen that disappears
     when something upstream breaks. */
  if (!a) {
    return `<section class="group"><div class="ghead"><h3>Where capital goes</h3></div>
      <p class="hint">This screen could not be built, so there is nothing to
      allocate against. Every security is still on the holdings and ideas
      tabs, and nothing you have recorded is affected.</p></section>`;
  }
  const st = a.standing;
  const figure = (label, v) => `<div class="fact"><i>${esc(label)}</i><b>${
    v && v.status === "known" ? esc(fmtUnit(v.value, "usd")) : "—"}</b>${
    v && v.status !== "known" ? `<div class="greynote">${esc(v.reason)}</div>` : ""}</div>`;

  let h = `<section class="group">
    <div class="ghead"><h3>Where capital goes</h3></div>
    <div class="rollup"><div class="pe-head"><b>${esc(st.headline)}</b></div>
      <div class="pe-why">${prose(st.detail)}</div>
      ${st.action ? `<div class="toolbar"><button class="btn primary" data-act="add">${esc(st.action)}</button></div>` : ""}
    </div>
    <div class="facts">${figure("Free cash", a.cash)}${figure("Account value", a.account_value)}</div>
  </section>`;

  if (a.ready.length) {
    h += `<section class="group"><div class="ghead"><h3>May take capital now</h3>
      <span>${a.ready.length}</span></div>
      <p class="hint">Furthest from where its own strategy wants it, first.
      Every amount is what that strategy said, converted against your account
      — nothing here ranks one business above another.</p>
      <div class="plist">${a.ready.map(allocEntry).join("")}</div></section>`;
  }
  if (a.waiting.length) {
    h += `<section class="group"><div class="ghead"><h3>Waiting on a condition</h3>
      <span>${a.waiting.length}</span></div>
      <p class="hint">Your strategy has sized these and is holding them back
      until something it stated is true. It decides when that has happened —
      nothing here checks the condition, and nothing here stops you.</p>
      <div class="plist">${a.waiting.map(allocEntry).join("")}</div></section>`;
  }
  if (a.excluded.length) {
    h += `<section class="group"><div class="ghead"><h3>Your strategy says no to these</h3>
      <span>${a.excluded.length}</span></div>
      <p class="hint">Listed with the rule that turned each one down. Buying
      one anyway is allowed and always will be — it is recorded as going
      against your own signal, with the reason you give, which is the part
      worth reading in a year.</p>
      <div class="plist">${a.excluded.map(allocExcluded).join("")}</div></section>`;
  }
  return h;
}

/* ---------------------------------------------------------------- render */
function render() {
  if (!S) return;
  renderMast(); renderTabs();
  const v = $("view");
  if (!S.journal) { v.innerHTML = welcomeView(); return; }
  if (openTicker) {
    const s = find(openTicker);
    if (!s) { closeSecurity(); return render(); }
    v.innerHTML = detailView(s);
    if ((s._valuation || {}).status === "known") paintEV(s.ticker);
  } else if (tab === "strategy") v.innerHTML = strategyView();
  else if (tab === "metrics") v.innerHTML = metricsView();
  else if (tab === "data") v.innerHTML = dataView();
  else if (tab === "allocate") v.innerHTML = allocationView();
  else if (tab === "list") v.innerHTML = importedListView();
  else v.innerHTML = listView();
}

async function paintEV(ticker) {
  const r = await api("recompute_ev", ticker);
  const el = $("evout");
  if (!el) return;
  if (!r || !r.result) { el.innerHTML = '<div><div class="lbl">Unavailable</div><div class="big">—</div></div>'; return; }
  el.innerHTML = `<div><div class="lbl">${esc(r.result.label)}</div><div class="big">${esc(r.result.display)}</div></div>`;
  const panel = $("evpanel");
  if (panel && r.result.note) {
    const p = document.createElement("p");
    p.className = "locked"; p.textContent = r.result.note;
    panel.appendChild(p);
  }
}

/* --------------------------------------------------------------- dialogs */
function dialog({ title, blurb, body, confirm, onConfirm, danger }) {
  $("dlgtitle").textContent = title;
  $("dlgblurb").textContent = blurb || "";
  $("dlgbody").innerHTML = body;
  $("dlgfoot").innerHTML =
    `<button class="btn" value="cancel" data-close>Cancel</button>
     <button class="btn ${danger ? "danger" : "primary"}" type="button" id="dlgok">${esc(confirm)}</button>`;
  const dlg = $("dlg");
  $("dlgok").onclick = async () => {
    const data = {};
    dlg.querySelectorAll("[name]").forEach((el) => { data[el.name] = el.value; });
    const err = await onConfirm(data);
    if (err === true) return;      /* handled: the dialog was replaced */
    if (err) {
      let box = dlg.querySelector(".dlg-err");
      if (!box) { box = document.createElement("div"); box.className = "dlg-err"; $("dlgbody").prepend(box); }
      box.textContent = err;
    } else { dlg.close(); await refresh(); }
  };
  dlg.showModal();
}
/* `attrs` is inserted as markup, for the handful of native constraints an
   input can carry — a date's `max`, say. Callers pass literals they wrote
   themselves; nothing user-supplied goes through it. */
const field = (name, label, value, help, type = "text", attrs = "") =>
  `<div class="field"><label for="f_${name}">${esc(label)}</label>
   <input id="f_${name}" name="${name}" type="${type}" value="${esc(value ?? "")}" ${attrs}>
   ${help ? `<div class="help">${esc(help)}</div>` : ""}</div>`;
const area = (name, label, value, help) =>
  `<div class="field"><label for="f_${name}">${esc(label)}</label>
   <textarea id="f_${name}" name="${name}">${esc(value ?? "")}</textarea>
   ${help ? `<div class="help">${esc(help)}</div>` : ""}</div>`;

/* ------------------------------------------------- declaration-built forms */
/* Every field below comes from a strategy's own declaration and nothing
   else. There is no list of known settings anywhere in this file: a journal
   shows the fields its own strategy uses, and a strategy that gains one
   gains a form field with no view code changed. */

/* `help` is inserted as markup so a caller can bold a shipped default;
   every caller escapes what it interpolates. Everything else here is
   escaped in place. */
function declaredField(spec, value, prefix, help) {
  const name = prefix + spec.id;
  const id = "f_" + name;
  const gate = spec.when
    ? ` data-gate="${esc(prefix + spec.when.input)}" data-gate-is="${esc(JSON.stringify(spec.when.is))}"` : "";
  const label = `<label for="${id}">${esc(spec.label)}${spec.required ? "" : " (optional)"}</label>`;
  const notes = `${help ? `<div class="help">${help}</div>` : ""}
    <div class="help">${esc(spec.explain)}</div>`;
  let control;
  if ((spec.options || []).length) {
    control = `<select id="${id}" name="${name}">
      ${spec.required ? "" : '<option value="">Not answered</option>'}
      ${spec.options.map((o) => `<option value="${esc(o.value)}" ${o.value === value ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`;
  } else if (spec.type === "boolean") {
    control = `<select id="${id}" name="${name}">
      ${spec.required ? "" : '<option value="">Not answered</option>'}
      <option value="false" ${value === false ? "selected" : ""}>No</option>
      <option value="true" ${value === true ? "selected" : ""}>Yes</option></select>`;
  } else if (spec.type === "number" || spec.type === "integer") {
    const bounds = (spec.min !== undefined ? ` min="${esc(spec.min)}"` : "")
      + (spec.max !== undefined ? ` max="${esc(spec.max)}"` : "");
    control = `<input id="${id}" name="${name}" type="number"
      step="${spec.type === "integer" ? "1" : "any"}"${bounds} value="${esc(value ?? "")}">`;
  } else {
    control = `<input id="${id}" name="${name}" type="text" value="${esc(value ?? "")}">`;
  }
  return `<div class="field"${gate}>${label}${control}${notes}</div>`;
}

/* A question whose gate is unmet is hidden rather than asked: a field that
   cannot mean anything teaches the wrong thing. Its answer is still sent —
   the backend is the authority on which answers apply, and it keeps a stale
   one rather than destroying it in case the gate swings back. */
function applyGates(root) {
  root.querySelectorAll("[data-gate]").forEach((el) => {
    const on = root.querySelector(`[name="${el.dataset.gate}"]`);
    let want;
    try { want = JSON.parse(el.dataset.gateIs); } catch (e) { want = null; }
    /* One answer or several, any of which opens the gate. The backend is
       the authority on which answers apply; this only decides what to draw,
       and it has to agree with it or the user is asked a question the save
       will discard — or worse, never shown one the save demands. */
    const wants = Array.isArray(want) ? want : [want];
    const raw = on ? on.value : "";
    const got = raw === "" ? null : (raw === "true" ? true : raw === "false" ? false : raw);
    /* Every value off a form is a string. A gate on a number would compare
       "3" against 3 and hide its field forever, which reads as a question
       that does not exist rather than as a bug. */
    const hit = (w) => (typeof w === "number" && raw !== ""
      ? Number(raw) === w : got === w);
    el.hidden = !(on && wants.some(hit));
  });
}

/* Everything this journal tells its strategy, on one screen: the answers it
   asked for and the override of the numbers it ships. They differ in where
   the default comes from, not in how they are set. */
function dlgSettings() {
  const st = S.strategy;
  if (!st) { toast("This journal's strategy is not installed here.", true); return; }
  const cfg = S.journal.config || {};
  const inputs = (st.inputs || []).map((f) =>
    declaredField(f, f.value, "in_",
      f.role ? `This journal reports it back to you as a figure: ${esc(((st.roles || {})[f.role] || {}).means || "")}.` : "")).join("");
  /* The attribution belongs here above all: this is the screen where someone
     is about to overwrite a number, and whose number it is — and whether the
     reasoning they just read is that source's or the strategy author's — is
     the thing that should give them pause. */
  const values = (st.values || []).map((v) =>
    declaredField({ ...v, required: false }, cfg[v.id], "cfg_",
      `${esc(st.name)} ships <b>${esc(declaredText(v, v.shipped))}</b>. Leave blank to use it.`
      + (v.source && v.source.name
        ? ` The level is ${esc(v.source.name)}'s${v.source.reasoning ? ""
          : ", and the reasoning above is this strategy's own"}.` : ""))).join("");
  dialog({
    title: "Journal settings",
    blurb: `${st.name} · everything ${S.journal.name} tells it.`,
    body: (inputs ? `<p class="hint" style="margin:0 0 10px">What it asked you. Facts about your account, which
        change for ordinary reasons — each edit is dated on the record, and nothing is owed for it.</p>${inputs}` : "")
      + (values ? `<p class="hint" style="margin:18px 0 10px">Its settings. Changing one changes what every future
        verdict in this journal means, so it goes on the rule-change record and asks you to write down why.</p>${values}` : ""),
    confirm: "Save",
    onConfirm: async (d) => {
      const ins = {}, conf = {};
      Object.keys(d).forEach((k) => {
        if (k.startsWith("in_")) ins[k.slice(3)] = d[k];
        else if (k.startsWith("cfg_")) conf[k.slice(4)] = d[k];
      });
      const r = await api("save_journal_settings", ins, conf);
      if (!r) return " ";
      if (r.pending) toast("Saved. A setting moved, so the rule-change record is waiting for you to write down why.");
      else toast("Saved.");
    },
  });
  const body = $("dlgbody");
  applyGates(body);
  body.querySelectorAll("select").forEach((el) => {
    el.addEventListener("change", () => applyGates(body));
  });
}

/* Creating a journal is where the strategy is chosen, and the only time. The
   setup fields below are generated from the chosen strategy's declaration,
   so a journal only ever asks for what its own strategy uses. */
function dlgNewJournal(chosenId) {
  const list = S.strategies || [];
  if (!list.length) { toast("No strategy would load, so there is nothing to create a journal against.", true); return; }
  const cur = list.find((x) => x.id === chosenId) || list[0];
  const opts = list.map((x) => `<option value="${esc(x.id)}" ${x.id === cur.id ? "selected" : ""}>${esc(x.name)}</option>`).join("");
  const setup = (cur.inputs || []).map(
    (f) => declaredField(f, undefined, "in_")).join("");
  dialog({
    title: "New journal",
    blurb: "One journal, one strategy, chosen now and not changed later. Trading two strategies means two journals, the way it would mean two accounts.",
    body: field("name", "Name this journal", "", "How you will tell it apart from another. “Retirement”, “Small caps”.")
      + `<div class="field"><label for="f_strategy">Strategy</label>
         <select id="f_strategy" name="strategy">${opts}</select>
         <div class="help">${esc(cur.summary)}</div>
         <div class="help">v${esc(cur.version)} · settings v${esc(cur.values_version)} · speaks contract ${esc(cur.contract)} ·
         can return: ${cur.states.map((s) => esc(s.name)).join(", ")}</div>
         ${(cur.declines || []).length ? `<div class="help"><b>Does not evaluate ${
           cur.declines.map((d) => esc(d.noun)).join(", ")}.</b> Its measures were not built for them, so a
           security of one of those kinds reads “outside these rules” rather than getting a verdict. Said here
           because it is knowable before the journal exists, and a journal cannot change strategy afterwards.</div>` : ""}
         ${cur.list ? `<div class="help"><b>Works from a list you import.</b> It does not screen for itself —
           you run ${esc(cur.list.source.name)} yourself, paste what it gives you, and this journal records
           which list and when. Nothing is bought here that is not on it. Said now because it is the largest
           single difference in how a journal is used, and the strategy cannot be changed afterwards.</div>` : ""}
         </div>`
      + (setup ? `<p class="hint" style="margin:4px 0 10px">${esc(cur.name)} asks for the following. These are things no
          strategy could ship a default for, because they are facts about you rather than opinions about investing.</p>${setup}` : ""),
    confirm: "Create journal",
    onConfirm: async (d) => {
      if (!(d.name || "").trim()) return "Give the journal a name.";
      const inputs = {};
      Object.keys(d).forEach((k) => { if (k.startsWith("in_")) inputs[k.slice(3)] = d[k]; });
      const r = await api("create_journal", d.name, d.strategy, inputs);
      if (!r) return " ";
      tab = "holdings"; closeSecurity();
      toast(`${r.name} created. Every decision in it will be judged by ${cur.name}.`);
    },
  });
  const body = $("dlgbody");
  applyGates(body);
  const sel = $("f_strategy");
  body.querySelectorAll("select").forEach((el) => {
    if (el === sel) return;
    el.addEventListener("change", () => applyGates(body));
  });
  if (sel) sel.onchange = () => {
    const name = $("f_name").value;
    $("dlg").close();
    dlgNewJournal(sel.value);
    if (name) $("f_name").value = name;
  };
}

function dlgAdd() {
  dialog({
    title: "Add a security", blurb: "It starts in Ideas. The strategy scores it from whatever data is available, and says what is missing.",
    body: field("ticker", "Ticker", "") + field("name", "Company name", ""),
    confirm: "Add",
    onConfirm: async (d) => {
      const r = await api("add_security", d.ticker, d.name);
      if (!r) return " ";
      tab = "ideas"; openSecurity(r.ticker);
    },
  });
}

/* The values offered are the ones the strategy actually read for this
   security, plus anything already recorded — never the whole bank. */
function dlgMetrics(s) {
  const priceHelp = (s._price && s._price.source === "fetched")
    ? `Blank uses the fetched close (${money(s._price.value)}, ${s._price.date}). A value typed here overrides it.`
    : "Leave blank if you don't have it.";
  let body = field("price", "Price", s.price ?? "", priceHelp, "number");
  const list = s._inputs || [];
  if (!list.length) {
    body += `<p class="hint">The strategy read no measure for this security, and none is recorded by hand.
      Fetch data, and whatever it reads will appear here.</p>`;
  }
  list.forEach((m) => {
    const comp = (s._computed || {})[m.id];
    let compNote = "";
    if (comp && comp.status === "computed") {
      /* Inline and always visible, not behind a mark. This is the screen
         where someone decides whether to type over a computed figure, and
         "it borrowed another share class's price" is the single most likely
         reason to. A qualification hidden here is a qualification withheld
         at the only moment it changes what the reader does. */
      compNote = `<div class="u">Computed from filings: <b>${fmtBank(comp.value, m.format)}</b> — a value typed here overrides it; blank uses it.</div>`
        + cautionLines(comp.cautions);
    } else if (comp && comp.status === "inapplicable") {
      /* The one place a typed figure is refused rather than preferred. This
         screen exists to let someone type over a computed number; here there
         is no number to type over, because the measure does not describe this
         company at all. Said before they type, not after. */
      compNote = `<div class="u">Not applicable to this company — ${esc(comp.reason)}
        A figure typed here is kept and dated, and is not used while this holds.</div>`;
    } else if (comp && comp.status === "absent" && comp.reason) {
      compNote = `<div class="u">Not computed — ${esc(comp.reason)}</div>`;
    }
    /* When you entered it, and everything entered before. A figure quietly
       retyped the week a rule was about to fire is worth what a judgement
       quietly remarked is worth, and it is only visible if the earlier one
       renders too. Collapsed, because the screen at rest is the value you
       hold now. */
    const ent = m.entered || {};
    const all = m.entries || [];
    const past = all.slice(1);
    let mine = "";
    if (ent.status === "known") {
      mine = `<div class="u">Entered by you on ${esc(ent.recorded)}.</div>`;
    } else if (all.length && all[0].value === null) {
      /* Clearing a field is an entry too, and it is the entry someone is
         most likely to want back. Said in place — the standing row is the
         withdrawal, so it never appears in the earlier-entries list below. */
      mine = `<div class="u">You cleared your value on
        ${esc(String(all[0].recorded).slice(0, 10))}.</div>`;
    }
    if (past.length) {
      mine += `<details class="whybox"><summary>${past.length} earlier entr${past.length === 1 ? "y" : "ies"}</summary>
        ${past.map((e) => `<div class="pe-sub">${esc(String(e.recorded).slice(0, 10))} —
          ${e.value === null ? "cleared" : `<b>${esc(fmtBank(e.value, m.format))}</b>`}</div>`).join("")}
        <p class="hint">Nothing was overwritten. Each save that changed something added an entry, and a
        reconstruction for a past day reads the one that was standing then.</p></details>`;
    }
    body += `<div class="metric-input"><div>${esc(m.label)}
      <div class="u">${esc(m.unit || "")} · ${m.cited ? "read by the strategy for this security"
        : "not currently read — kept because a value was recorded"}</div>${compNote}${mine}</div>
      <input name="m_${m.id}" type="number" step="any" value="${(m.entered || {}).value ?? ""}"></div>`;
  });
  dialog({
    title: `Values · ${s.ticker}`,
    blurb: "Hand-entered values always beat fetched ones, visibly, and each one is dated — a purchase "
      + "recorded for a past day reads the value that was on record then. Changing one adds an entry "
      + "rather than replacing it. Leave a field blank to withdraw yours and use the computed value, or "
      + "to show absent where none computes — a zero would read as a confident failure.",
    body, confirm: "Save",
    onConfirm: async (d) => {
      const metrics = {};
      Object.keys(d).forEach((k) => { if (k.startsWith("m_")) metrics[k.slice(2)] = d[k]; });
      const r = await api("save_metrics", s.ticker, metrics, d.price);
      if (!r) return " ";
    },
  });
}

/* One question at a time, with what it means in front of you. Not folded
   into the values dialog: that one is a column of numbers, and a question
   about whether a moat holds for another decade is not answered well in a
   row between two of them. It is also the only dialog whose answer is
   append-only, and putting it beside fields that overwrite would say the
   wrong thing about what happens when you press save. */
function dlgJudgement(s, entryId) {
  const j = (s._judgements || []).find((x) => x.id === entryId);
  if (!j) { toast("That question is not on this security.", true); return; }
  const prior = j.mark
    ? `<div class="notice quiet"><h4>Your assessment of ${esc(String(j.recorded).slice(0, 10))}</h4>
       <p><b>${esc((MARK_CHIP[j.mark] || ["Marked"])[0])}</b></p>${prose(j.reasoning)}
       <p class="hint">Saving adds a new entry above this one. Nothing here is
       edited or replaced — an answer improved after the fact cannot be measured
       against what happened, which is the only thing this record is for.</p></div>`
    : "";
  dialog({
    title: `${j.label} · ${s.ticker}`,
    blurb: "Your judgement, with your reasoning. The journal records it as yours and never as something it worked out.",
    body: prior
      + `<div class="pe-desc">${prose(j.question)}</div>`
      + `<details class="whybox"><summary>What this is asking</summary>${prose(j.plain)}
         <span class="who">Bank entry <code>${esc(j.id)}</code> — full definition, where it
         misfires and where it comes from, on the Metrics tab</span></details>`
      + `<div class="field"><label for="f_mark">Your mark</label>
         <select id="f_mark" name="mark">
           <option value="">Not answering yet</option>
           <option value="pass">Pass</option>
           <option value="fail">Fail</option></select>
         <div class="help">Unanswered is not a fail. Leaving it is a fine thing to
         do — the strategy is told the question has no answer, and absence never
         reads as a pass.</div></div>`
      + area("reasoning", "Why", "",
             "What you looked at and what convinced you. Required: a mark with "
             + "nothing behind it teaches nothing when you read it back.")
      /* Both fields are checked here as well as at the write, so the message
         lands beside the field rather than as a banner over a closed dialog. */,
    confirm: "Record it",
    onConfirm: async (d) => {
      if (!d.mark) return "Choose pass or fail, or cancel — leaving it unanswered is done by not recording anything.";
      if (!(d.reasoning || "").trim()) return "Write down your reasoning.";
      const r = await api("record_judgement", s.ticker, j.id, d.mark, d.reasoning);
      if (!r) return " ";
      toast(`Recorded. ${j.label} for ${s.ticker} is on the journal's dated record.`);
    },
  });
}

/* The thesis, amended. Never edited.

   The fields carry the standing text forward, because an entry holds the
   WHOLE document: someone changing only the falsifier would otherwise save
   a version whose thesis prose is blank, and the blanking would be silent
   and permanent. Starting empty was the wrong way to say "this is not an
   edit" — the notice above the fields says it in words instead, and the
   words can say the part the empty box could not.

   The reason is required on an amendment and absent on a first statement.
   There is nothing to explain the first time you write down what you
   believe; there is something to explain every time after. That is the same
   argument the journal makes about a strategy's declared values — a rule you
   can quietly retune is not a rule — and the falsifier is the rule you wrote
   for yourself. */
function dlgThesis(s) {
  const t = s._thesis || {};
  const v = t.status === "known" ? t.version : null;
  const prior = v
    ? `<div class="notice quiet"><h4>Standing since ${esc(t.amended)}</h4>
       <p class="hint">Below is your thesis as it stands, ready to change. Saving does not edit it —
       it adds a new version above it, and the one standing now stays readable exactly as written.
       A thesis revised after the answer is known cannot be measured against what happened, and
       measuring it is what every override and every exit in this journal is for.</p></div>`
    : "";
  dialog({
    title: `Thesis · ${s.ticker}`,
    blurb: v
      ? "Amending what you believe. Both versions stay on the record, with the reason it changed."
      : "Why is this worth owning, and what would have to happen for you to be wrong? Write it now, while you are calm.",
    body: prior
      + area("thesis", "Why I own this", v ? v.thesis : "",
             "What the business is, and why the market is wrong about it. This is what "
             + "every later decision gets graded against.")
      + area("falsifier", "What would make me wrong", v ? v.falsifier : "",
             "Make it testable. “Margins fall below 30% for two quarters” beats “the story changes”.")
      + (v ? area("reason", "Why it changed", "",
                  "Required on an amendment. Months from now the useful question is not what "
                  + "you believe — it is what made you stop believing the other thing.") : ""),
    confirm: v ? "Amend" : "Save",
    onConfirm: async (d) => {
      if (!(d.thesis || "").trim() && !(d.falsifier || "").trim())
        return "Write down what you believe, or what would prove you wrong, or both.";
      if (v && !(d.reason || "").trim()) return "Say why it changed.";
      const r = await api("amend_thesis", s.ticker, d.thesis, d.falsifier, d.reason || "");
      if (!r) return " ";
      if (r.amended === false) toast("Nothing changed, so nothing was recorded.");
    },
  });
}

function dlgNote(s) {
  dialog({
    title: `Add note · ${s.ticker}`,
    blurb: "Notes are dated and appended. Nothing is ever edited in place.",
    body: area("text", "Note", "", ""),
    confirm: "Add",
    onConfirm: async (d) => {
      if (!(d.text || "").trim()) return "Write something first.";
      if (!(await api("add_note", s.ticker, d.text))) return " ";
    },
  });
}

/* The purchase dialog evaluates for the DATE being recorded, not for today.
   A past date reconstructs the state from the data available by then —
   filings filed by that day, that day's close — and says so, visibly:
   asserting "on <date> this read X" about an evaluation that ran today would
   be claiming a fact never computed. Changing the date re-runs the preview
   for the new date, keeping whatever was already typed. */
async function dlgBuy(s, dateChosen, keep, fallbackDate) {
  const today = localToday();
  const when = dateChosen || today;
  const p = await api("preview_purchase", s.ticker, when);
  if (!p) {
    /* The chosen date was refused (future, unparseable). Reopen on the last
       date that worked rather than eating everything already typed. */
    if (fallbackDate) dlgBuy(s, fallbackDate, keep);
    return;
  }
  const d = p.decision;
  const commit = d.render === "commit";
  /* Which of the four ways this would go on the record, from the engine.
     "Bought without a signal" is a real decision — you read the grey box and
     went ahead — and a reconstruction that reaches no verdict is not that
     decision at all: nobody was standing in front of anything. The engine
     draws that line, and the dialog reads its answer rather than working it
     out again from the render tier, which is how the two came to disagree. */
  const asRecorded = p.recorded_as;
  const noVerdict = asRecorded === "without";
  const cannotRebuild = asRecorded === "unreconstructed";
  /* A reason is owed where there was something to go against. Asking for one
     where nothing could be rebuilt would be asking somebody to justify a
     purchase against a signal that never existed. */
  const bad = !commit && !cannotRebuild;
  const cited = ((d.reason || {}).evidence || []);
  const failed = cited.filter((e) => e.outcome === "fail").map((e) => e.subject.label);
  const unknown = cited.filter((e) => e.outcome === "unknown").map((e) => e.subject.label);
  const who = (d.strategy || {}).name || "The strategy";
  const recon = p.basis === "reconstructed";
  const reconBox = recon
    ? `<div class="notice quiet" style="margin:0 0 12px"><h4>From history — not seen at the time</h4>
       <p>${esc(when)} is in the past, so the state below is rebuilt from what was observable then:
       ${esc(p.note || "")}. It is recorded as a reconstruction, distinct everywhere from a state
       you saw at the time.</p></div>` : "";
  const darkBox = cannotRebuild
    ? `<div class="notice quiet" style="margin:0 0 12px"><h4>No verdict could be rebuilt for ${esc(when)}</h4>
       <p>${esc(who)} reads <strong>${esc(d.state.name)}</strong> — ${esc((d.reason || {}).summary || "")}
       Nothing is recorded about what your rules would have said, and this purchase is
       <strong>not</strong> counted as buying against a signal, because there was none to go against.
       That distinction is the whole reason the override scorecard means anything.</p></div>` : "";
  const warn = bad
    ? `<div class="dlg-err"><strong>${esc(who)}</strong> ${recon ? `reads <strong>${esc(d.state.name)}</strong> for ${esc(p.as_of)}, reconstructed from the data available by then`
        : `says <strong>${esc(d.state.name)}</strong>`}. ${esc((d.reason || {}).summary || "")}
       ${failed.length ? esc(failed.join(", ")) + " missed its threshold." : ""}
       ${unknown.length ? esc(unknown.join(", ")) + " could not be read." : ""}
       ${noVerdict ? "There is no verdict here to go against — which is its own kind of override, and is recorded as one." : ""}
       Nothing here stops you. The purchase and this reason both go into the journal, so that in a year you can
       see what you ignored and what it cost or earned you.</div>` : "";
  /* Buying a name back is one more purchase, judged the same way — not a
     resumption of the holding that ended. Saying so is the whole difference
     between a fresh decision and averaging into an old one. */
  const back = s.bucket === "previous";
  /* What this purchase is about to freeze onto itself: the thesis standing
     on the day being recorded, and the valuation claim standing with it.
     Shown, not editable. Amending is done in one place — the Thesis dialog —
     because two ways to write the same document is how you end up with a
     version written to fit the purchase you had already decided on. A buy
     against no thesis is allowed and always will be; it should be a thing
     you notice you are doing.

     Under a reconstruction this reads the past too, so a backdated purchase
     never shows a thesis written afterwards as the case that was made. */
  const th = p.thesis || {};
  const pv = p.valuation || {};
  const claimLine = pv.status === "known"
    ? `<p class="hint"><b>${esc((S.ev_methods[pv.claim.method] || {}).label || pv.claim.method)}</b>,
       claimed ${esc(pv.made)}${pv.result ? ` — ${esc(pv.result.label)} ${esc(pv.result.display)}` : ""}.
       That claim belongs to this purchase and to no other.</p>${cautionLines(pv.cautions)}`
    : `<p class="hint">No valuation is on record for this day, so this purchase records none.</p>`;
  const thesisBox = th.status === "known"
    ? `<details class="whybox" style="margin:0 0 12px"><summary>Buying on your thesis
       of ${esc(th.amended)}${(th.cautions || []).length ? " — qualified" : ""}</summary>
       ${th.version.thesis ? prose(th.version.thesis) : ""}
       ${th.version.falsifier ? `<p><b>What would make me wrong</b></p>${prose(th.version.falsifier)}` : ""}
       ${cautionLines(th.cautions)}${claimLine}
       <p class="hint">This version is frozen onto the purchase. To change it, close this and amend the
       thesis first — nothing here edits it.</p></details>`
    : `<div class="notice quiet" style="margin:0 0 12px"><h4>No thesis on record${recon ? ` for ${esc(when)}` : ""}</h4>
       <p>${esc(th.reason || "Nothing is written yet.")} The purchase records that, and so does every
       later question about why you own this. Nothing here stops you.</p></div>`;
  dialog({
    title: `Record a purchase · ${s.ticker}`,
    blurb: (back
      ? `You held ${s.ticker} before and closed it. This starts a new holding, judged from scratch by ${who}`
      : `Judged by ${who}`)
      + ", the strategy this journal is stamped with. This records what you already did; the tool cannot place trades.",
    body: reconBox + darkBox + warn + thesisBox + `<div class="grid2">${field("shares", "Shares", (keep && keep.shares) || "", "", "number")}${field("cost", "Cost per share", (keep && keep.cost) || "", "", "number")}</div>`
      + `<div class="field"><label for="f_opened">Date</label>
         <input id="f_opened" name="opened" type="date" value="${esc(when)}" max="${esc(today)}">
         ${recon ? "" : '<div class="help">A past date is evaluated with the data of that day, and the preview updates when you change this. The future is not offered — its data does not exist yet.</div>'}</div>`
      + (bad ? area("override_reason", noVerdict ? "Why are you buying without a signal?" : "Why are you buying anyway?", (keep && keep.override_reason) || "",
        "Required. One sentence. You will read this again later.") : "")
      /* Offered where there is something to remember and nothing on record:
         a purchase in the past that froze no thesis. Never on a purchase made
         today, where the honest answer is to write a thesis — the engine
         refuses it there outright, so this is the form agreeing with a rule
         rather than enforcing one. */
      + (recon && th.status !== "known"
        ? area("recollection", "What do you remember thinking? (optional)", (keep && keep.recollection) || "",
          "Written now, about then — and recorded as exactly that, with today's date on it. It is not a "
          + "thesis and is never counted as one: you already know how this turned out, so nothing here can "
          + "be graded against what happened.")
        : ""),
    confirm: bad ? "Record anyway" : "Record purchase", danger: bad,
    onConfirm: async (dd) => {
      if (!dd.shares || !dd.cost) return "Shares and cost per share are required.";
      if (bad && !(dd.override_reason || "").trim()) return "A reason is required when the strategy doesn't say to commit.";
      const r = await api("open_position", s.ticker, dd.shares, dd.cost, dd.opened,
        dd.override_reason || "", d.state.id, dd.recollection || "");
      if (!r) return " ";
      /* The state is re-evaluated at commit; if it moved while the dialog
         was open (a fetch completed, the strategy changed), the record
         differs from what the user was shown — say so, loudly. */
      if (r.state_changed) {
        toast(`The state changed to ${r.state} between preview and commit (data or the strategy moved). The purchase is recorded under the new state${r.override ? " as an override — add a note with your reasoning" : ""}.`, !r.commit);
      }
      if (r.unreconstructed) {
        toast(`Recorded from history, dated ${dd.opened}. No verdict could be rebuilt for that day, so none is recorded — and this is not counted as buying against a signal.`);
      } else if (r.basis === "reconstructed") {
        toast(`Recorded from history, dated ${dd.opened}. The verdict beside it was rebuilt from that day's data, and says so wherever it appears.`);
      }
      /* Stay where the purchase was started from. Someone allocating a sum
         across a list has more of the list to get through, and throwing them
         onto the holdings tab after each one turns a session into a series
         of round trips. From anywhere else, the holding is what they just
         acted on and is where they expect to land. */
      if (tab !== "allocate") tab = "holdings";
    },
  });
  const dateEl = $("f_opened");
  if (dateEl) dateEl.onchange = () => {
    if ((dateEl.value || today) === when) return;
    const keepNow = { shares: $("f_shares").value, cost: $("f_cost").value,
      override_reason: ($("f_override_reason") || {}).value || "",
      recollection: ($("f_recollection") || {}).value || "" };
    $("dlg").close();
    dlgBuy(s, dateEl.value, keepNow, when);
  };
}

/* A sale is one more appended entry, not an edit. Selling part of a position
   leaves the remaining lots exactly as they were bought — which is what makes
   a trim recordable at all, and what a `reduce` verdict has been asking for
   with nowhere to go. Shares default to everything held on the day the sale is
   dated, so closing out is still one field away.

   Every figure here about the position is read off the chosen date and none of
   it off the live payload. This dialog has a date picker in it, so "what you
   hold" is a question with two answers the moment somebody changes the date —
   and the live one was being shown against a day years in the past, all the
   way down to the reference close beside the price field. */
async function dlgSell(s, dateChosen, keep, fallbackDate) {
  const today = localToday();
  const when = dateChosen || today;
  /* A sale dated in the past is judged with the data of that day, exactly as
     a purchase is. It used to be judged with today's, which froze a verdict
     the strategy was never asked for into `signal_at_exit` and
     `rule_triggered` — the two facts the panic-sell learning loop reads. The
     preview exists so the person entering it sees which verdict is about to
     go on the record, and sees it named as a reconstruction.

     Asked for on every date, not only a past one. The verdict box is still
     shown only on a backdated sale — a verdict box on a trade already made
     would be the tool asking you to reconsider it, which is a gate wearing a
     preview's clothes — but the share count, the lots and the close have to
     come from the same clock whichever day is chosen, or the dialog holds one
     figure from the picker and three from today. */
  const past = when < today;
  const reply = await api("preview_sale", s.ticker, when);
  if (!reply && past) {
    /* A past date has nowhere honest to fall back to: showing today's figures
       against it is the exact reading this dialog exists to stop. So it
       reopens on the date that last worked. */
    if (fallbackDate) dlgSell(s, fallbackDate, keep);
    return;
  }
  /* Today's can fall back, and must. The live payload *is* today, so the
     figures are the same figures — and a dialog that refuses to open because
     a preview did not answer is a gate on recording a sale that has already
     happened. The tool records decisions and never blocks them, and a screen
     that will not appear is a block however it is described. */
  const p = reply || {
    held: s._shares,
    lots: buyLots(s).filter((l) => l.open)
      .map((l) => ({ date: l.date, remaining: l.remaining })),
    price: (s._price || {}).value != null
      ? { status: "known", value: s._price.value, date: s._price.date,
          source: s._price.source, terminal: s._price.terminal }
      : { status: "absent",
          reason: (s._price || {}).reason || "no price is on record" },
  };
  const reconBox = past
    ? `<div class="notice quiet" style="margin:0 0 12px"><h4>From history — not seen at the time</h4>
       <p>${esc(when)} is in the past, so what gets frozen beside this sale is rebuilt from what was
       observable then: ${esc(p.note || "")}.
       ${p.verdict
         ? `${esc(((p.decision || {}).state || {}).name || "")} — ${esc(((p.decision || {}).reason || {}).summary || "")}`
         : "No verdict could be rebuilt for that day, so none is recorded against this sale. It will not read as "
           + "an exit your rules called for, and it will not read as one they stayed silent on either."}</p>
       ${(p.thesis || {}).status === "known"
         ? `<p class="hint">Graded against the thesis standing on ${esc(p.thesis.amended)} — the version on record then,
            not the one on record now.</p>`
         : `<p class="hint">No thesis is frozen with this sale: ${esc((p.thesis || {}).reason || "none was on record then")}.</p>`}</div>`
    : "";
  const opts = [...S.exit_reasons.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`),
    /* Offered only on a sale entered out of history, and never on one being
       recorded as it happens: you were there, and the reason is the one fact
       the exit analytics cannot work without. Years later it may honestly be
       gone, and forcing a pick from the list would manufacture exactly the
       figure this record exists to measure. */
    past ? '<option value="">I do not remember</option>' : ""].join("");
  /* The exit price enters an append-only record, so nothing is prefilled
     here at all. What the tape says is not what you got: you sold at a time
     of day, possibly across a spread, and the close is a different number
     that happens to be nearby. It also used to be prefilled only when the
     close was under seven days old — a rule the browser applied itself, in a
     second copy of a judgement the engine was making too, and neither of
     them was the host's to make. The honest field is an empty one with the
     close shown beside it as a reference.

     The close that belonged to the chosen day, from the preview, not the one
     on the live payload. A sale dated 2019 was shown last week's close as its
     reference, beside an empty field it was inviting a number into — the
     nearest thing this dialog can do to prefilling the wrong price. */
  const quote = p.price || {};
  const closeNote = quote.status === "known" && quote.source === "fetched" && quote.date
    ? ` For reference, the close on record for ${quote.date} was ${money(quote.value)}${
        quote.terminal ? " — the last this security ever traded at" : ""}.`
    : past ? ` No close is on record for ${when}: ${quote.reason || "none was stored for that day"}.` : "";
  const priceHelp = "The price you actually sold at, per share. Nothing is "
    + "filled in for you: this goes on the record permanently, and a number "
    + "off the tape is not the number you got." + closeNote;
  /* The purchases a sale dated this day can draw on, and what each had left
     then. Read off the preview for the same reason the share count is: the
     allocation stops at the sale's own date, so a lot bought after it cannot
     supply anything — and listing it here promised shares the write would
     refuse. */
  const lots = p.lots || [];
  const asOfThen = past ? ` as they stood on ${esc(when)}` : "";
  const lotHelp = lots.length > 1
    ? `Oldest shares go first, across ${lots.length} open lots${asOfThen} (${lots.map((l) => `${l.remaining} from ${l.date}`).join(", ")}).`
    : "";
  dialog({
    title: `Record a sale · ${s.ticker}`,
    blurb: "It stays in the journal and keeps being priced, so you can see what happened after you sold.",
    body: reconBox + `<div class="field"><label for="f_reason">Why are you selling?</label>
        <select id="f_reason" name="reason">${opts}</select>
        <div class="help">Answer honestly. The Previous holdings tab groups outcomes by this, and it is the only way to find out whether your sell rules work.</div></div>`
      + field("shares", "Shares sold", (keep && keep.shares) || p.held,
        `${past ? `You held ${p.held} on ${esc(when)}` : `You hold ${p.held}`}. Sell fewer to trim; the rest stays open, priced from what it actually cost. ${lotHelp}`, "number")
      + field("price", "Sale price per share", (keep && keep.price) || "", priceHelp, "number")
      /* Same bound as the purchase date, and for the same reason. A sale
         dated ahead has not happened: it reports the position closed to
         every screen that asks while the strategy is still holding it, and
         takes the whole holding out of the account. The backend refuses it
         regardless; this is so the picker never offers it. */
      + `<div class="field"><label for="f_exited">Date</label>
         <input id="f_exited" name="exited" type="date" value="${esc(when)}" max="${esc(today)}">
         <div class="help">The day you actually sold. A past date is judged with the data of that day,
         and this dialog updates when you change it. A date that has not happened yet is refused.</div></div>`,
    confirm: "Record the sale", danger: true,
    onConfirm: async (d) => {
      if (!d.price) return "A sale price is required.";
      if (!d.shares) return "How many shares were sold?";
      const r = await api("sell_shares", s.ticker, d.reason, d.price, d.exited, d.shares);
      if (!r) return " ";
      tab = r.remaining > 0 ? "holdings" : "previous";
      if (r.remaining > 0)
        toast(`Recorded. ${r.remaining} shares still held; the lots they came from are unchanged.`);
      if (r.basis === "reconstructed")
        toast(`Recorded from history, dated ${r.as_of}. What is frozen beside it was rebuilt from that day's data, and says so wherever it appears.`);
      else if (r.rule_triggered === false)
        toast(`Recorded. ${r.signal} under ${r.strategy_name} — no rule triggered this sale. That is now on the record.`);
      else if (r.rule_triggered === null)
        toast("Recorded. No verdict could be evaluated, and that absence is on the record rather than papered over.");
    },
  });
  const dateEl = $("f_exited");
  if (dateEl) dateEl.onchange = () => {
    if ((dateEl.value || today) === when) return;
    const typed = $("f_shares").value;
    /* What the user typed is theirs and survives the date change. The default
       does not: it is the answer to "how many were held" for the day that was
       chosen before, and carrying it across would put the old day's count in
       front of the new day's label — the same wrong-clock reading this dialog
       just stopped making, reintroduced at the one seam where the clock
       moves. */
    const keepNow = { price: $("f_price").value,
      shares: String(typed) === String(p.held) ? "" : typed };
    $("dlg").close();
    dlgSell(s, dateEl.value, keepNow, when);
  };
}

/* ------------------------------------------------------------- backfill --- */
/* Entering a position you already own, out of your own records.

   A journal is otherwise only usable forward from the day it was started, and
   every analytic in it has nothing to work against until enough decisions
   accumulate. This is what gives them something — and the thing it must never
   do is let a reconstruction pass for a record made at the time, which is why
   every entry it writes is marked, everywhere, for as long as it exists.

   Nothing is guessed. Each row asks for the three facts only the person who
   made the trade has — the day, the shares, the price — and for a sale, why.
   A form that filled any of those in from the tape would put a number nobody
   read off a statement into a record that can never be corrected. What the
   form does instead is show, before anything is permanent, exactly what each
   row would record: the verdict rebuilt for its own day, or the fact that
   none could be. */
const BF_BLANK = { kind: "buy", date: "", shares: "", price: "", reason: "" };

function bfRow(r, i, previewed) {
  const p = previewed || null;
  const sell = r.kind === "sell";
  const outcome = !p ? "" : p.problem
    ? `<div class="bf-out bad">${esc(p.problem)}</div>`
    : `<div class="bf-out"><b>${esc(p.state || "No verdict")}</b>
       ${p.basis === "reconstructed" ? RECON_CHIP : '<span class="chip s-none">seen live</span>'}
       ${p.recorded_as === "unreconstructed"
         ? '<span class="chip s-none">no verdict to rebuild — not an override</span>'
         : p.recorded_as === "against" ? '<span class="chip s-fail">against the signal</span>'
         : p.recorded_as === "commit" ? '<span class="chip s-pass">with the signal</span>' : ""}
       <div class="dim">${esc(p.summary || p.note || "")}</div></div>`;
  return `<div class="bfrow" data-i="${i}">
    <select data-k="kind">
      <option value="buy" ${sell ? "" : "selected"}>Bought</option>
      <option value="sell" ${sell ? "selected" : ""}>Sold</option></select>
    <input data-k="date" type="date" value="${esc(r.date)}" max="${esc(localToday())}">
    <input data-k="shares" type="number" step="any" placeholder="Shares" value="${esc(r.shares)}">
    <input data-k="price" type="number" step="any" placeholder="Price each" value="${esc(r.price)}">
    ${sell ? `<select data-k="reason">
        ${S.exit_reasons.map((x) => `<option value="${esc(x)}" ${x === r.reason ? "selected" : ""}>${esc(x)}</option>`).join("")}
        <option value="" ${r.reason ? "" : "selected"}>I do not remember</option></select>`
      : '<span class="dim">—</span>'}
    <button class="btn" type="button" data-drop="${i}">Remove</button>
    ${outcome}</div>`;
}

async function dlgBackfill(s, state) {
  const st = state || { rows: [{ ...BF_BLANK }], recollection: "", preview: null };
  const pv = st.preview;
  const byIndex = {};
  ((pv || {}).events || []).forEach((e) => { byIndex[e.index] = e; });

  /* Offered only where it can be answered honestly: on a run that opens with
     a purchase in the past. It is not a thesis and can never become one — the
     record keeps it under its own name with the day it was actually written,
     and the engine refuses it outright on an entry dated today, where the
     answer is to write a thesis instead. */
  const first = st.rows[0] || BF_BLANK;
  const canRemember = first.kind === "buy" && first.date
    && first.date < localToday();

  const summary = !pv ? "" : pv.problem
    ? `<div class="dlg-err">Nothing has been recorded. ${esc(pv.problem)}
       ${(pv.unchecked || []).length ? ` The ${pv.unchecked.length} entries after it were not checked — each one is judged against the position the ones before it leave behind, so there is nothing honest to say about them until this is fixed.` : ""}</div>`
    : `<div class="notice quiet"><h4>Checked — nothing recorded yet</h4>
       <p>${pv.events.length} ${pv.events.length === 1 ? "entry" : "entries"}, each judged against the
       data of its own day. This run ends with ${pv.shares_after} ${s.ticker} held.
       ${pv.events.filter((e) => e.recorded_as === "unreconstructed").length
         ? `${pv.events.filter((e) => e.recorded_as === "unreconstructed").length} could not have a verdict rebuilt — those record the gap and produce no override.`
         : ""}</p></div>`;

  dialog({
    title: `Enter history · ${s.ticker}`,
    blurb: "Purchases, adds, trims, exits and re-entries you made before you started recording them here. "
      + "Each is judged against the filings and the close of its own day, and is marked as a reconstruction for good.",
    body: summary
      + `<div class="bfhead"><span>What</span><span>Date</span><span>Shares</span><span>Price each</span><span>Why sold</span><span></span></div>
         <div id="bf_rows">${st.rows.map((r, i) => bfRow(r, i, byIndex[i])).join("")}</div>
         <div class="toolbar" style="margin:8px 0">
           <button class="btn" type="button" id="bf_add_buy">Add a purchase</button>
           <button class="btn" type="button" id="bf_add_sell">Add a sale</button></div>`
      + (canRemember
        ? area("recollection", "What do you remember thinking? (optional)", st.recollection,
          "Written now, about then — and recorded as exactly that, with today's date on it. "
          + "It is not a thesis and is never counted as one: you already know how this turned out, "
          + "so nothing here can be graded against what happened. It attaches to the first purchase above.")
        : ""),
    confirm: pv && !pv.problem ? `Record ${pv.events.length} ${pv.events.length === 1 ? "entry" : "entries"}` : "Check these entries",
    danger: !!(pv && !pv.problem),
    onConfirm: async () => {
      const rows = bfRead();
      const remembered = ($("f_recollection") || {}).value || "";
      if (!rows.length) return "Add at least one entry.";
      /* Check first, record second, and never both on one press. What is
         about to be written cannot be corrected afterwards, so the person
         writing it sees the verdict each row produces — including the rows
         that produce none — before any of it is permanent. */
      const fresh = await api(pv && !pv.problem ? "record_backfill" : "preview_backfill",
        s.ticker, rows, remembered);
      if (!fresh) return " ";
      if (fresh.recorded) {
        tab = fresh.held_after ? "holdings" : "previous";
        toast(`Recorded ${fresh.events.length} ${fresh.events.length === 1 ? "entry" : "entries"} from history. Every one of them is marked as a reconstruction wherever it appears.`);
        return;
      }
      $("dlg").close();
      dlgBackfill(s, { rows, recollection: remembered, preview: fresh });
      return true;
    },
  });

  const add = (kind) => {
    const rows = bfRead();
    rows.push({ ...BF_BLANK, kind });
    const remembered = ($("f_recollection") || {}).value || "";
    $("dlg").close();
    dlgBackfill(s, { rows, recollection: remembered, preview: null });
  };
  if ($("bf_add_buy")) $("bf_add_buy").onclick = () => add("buy");
  if ($("bf_add_sell")) $("bf_add_sell").onclick = () => add("sell");
  const holder = $("bf_rows");
  if (holder && holder.querySelectorAll) {
    holder.querySelectorAll("[data-drop]").forEach((b) => {
      b.onclick = () => {
        const rows = bfRead();
        rows.splice(Number(b.dataset.drop), 1);
        const remembered = ($("f_recollection") || {}).value || "";
        $("dlg").close();
        dlgBackfill(s, { rows: rows.length ? rows : [{ ...BF_BLANK }],
          recollection: remembered, preview: null });
      };
    });
    /* Changing what an entry IS changes which questions it owes — a sale owes
       a reason and a purchase does not — so the form is redrawn rather than
       leaving a column that means nothing. */
    holder.querySelectorAll('[data-k="kind"]').forEach((el) => {
      el.onchange = () => {
        const remembered = ($("f_recollection") || {}).value || "";
        $("dlg").close();
        dlgBackfill(s, { rows: bfRead(), recollection: remembered, preview: null });
      };
    });
  }
}

/* What the rows currently say, read off the form rather than tracked in a
   second copy beside it. One source for what is about to be recorded. */
function bfRead() {
  const holder = $("bf_rows");
  if (!holder || !holder.querySelectorAll) return [];
  return Array.from(holder.querySelectorAll(".bfrow")).map((el) => {
    const get = (k) => {
      const f = el.querySelector(`[data-k="${k}"]`);
      return f ? f.value : "";
    };
    return { kind: get("kind") || "buy", date: get("date"),
      shares: get("shares"), price: get("price"), reason: get("reason") };
  });
}

/* The expected-value dialog computes what it can and asks only for
   judgement. Price, FCF and shares arrive prefilled from fetched data with
   their provenance and as-of date, locked until deliberately overridden —
   a typo must not become a stored assumption. */
function dlgEV(s, methodOverride, pf) {
  if (pf === undefined) {   /* fetch the prefills once, then reopen */
    api("ev_prefill", s.ticker).then((r) => dlgEV(s, methodOverride, r || null));
    return;
  }
  /* The standing claim seeds the form, and saving makes a new one — a
     valuation is a claim about a moment, not a document you revise. */
  const standing = (s._valuation || {}).status === "known" ? s._valuation.claim : null;
  const cur = methodOverride || (standing ? standing.method : S.journal.settings.default_ev_method);
  const meth = S.ev_methods[cur];
  const prefill = (pf && pf.prefill) || {};
  const refs = (pf && pf.references) || {};
  /* pf === null means the prefill call itself failed — a different fact
     from "nothing is fetched", and it must not render as silently blank. */
  const pfFailed = pf === null
    ? `<div class="dlg-err">The computed prefills (price, cash flow, shares) could not be read just now.
       Anything typed below is recorded as entered by hand, without provenance.</div>` : "";
  const opts = Object.keys(S.ev_methods).map((k) =>
    `<option value="${k}" ${k === cur ? "selected" : ""}>${esc(S.ev_methods[k].label)}</option>`).join("");
  const DEFAULT_KEYS = ["discount_rate", "terminal_growth", "margin_of_safety"];
  const SOURCE_WORDS = { fetched: "Fetched", computed: "Computed from filings", manual: "Hand-entered value" };
  const sourcesInit = {};      /* key -> provenance of what was offered */
  const inputs = meth.inputs.map(([key, label, help]) => {
    const pre = prefill[key];
    const refLines = (((meth.references || {})[key]) || []).map(([rid, rlabel]) => {
      const r = refs[rid];
      if (!r) return "";
      return r.status === "computed"
        ? `<div class="help refline">${esc(rlabel)}: <b>$${Number(r.value).toLocaleString()}M</b>${r.asof ? ` · through ${esc(r.asof)}` : ""}${(r.provenance || []).length ? ` <span class="dim">— ${(r.provenance || []).map(esc).join("; ")}</span>` : ""}</div>`
        : `<div class="help refline">${esc(rlabel)}: not computed — ${esc(r.reason)}</div>`;
    }).join("");
    if (pre && pre.status === "computed") {
      /* Cautions travel with the figure into the stored claim. A cash flow
         prefilled from a line that folds in finance leases is that kind of
         number in the claim built on it, and a record keeping where a figure
         came from while dropping what was wrong with it states the claim as
         more certain than it was. */
      sourcesInit[key] = { used: pre.source, provenance: (pre.provenance || []).join("; "),
        cautions: pre.cautions || [], asof: pre.asof || null, offered: String(pre.value) };
      const prov = (pre.provenance || []).map(esc).join(" · ");
      const priorSrc = (standing && standing.method === cur && standing.sources) ? standing.sources[key] : null;
      const prior = (priorSrc && priorSrc.used === "overridden"
        && String(standing.inputs[key]) !== String(pre.value))
        ? `<div class="help">Your last claim overrode this with ${esc(standing.inputs[key])}; the fresh ${esc(SOURCE_WORDS[pre.source] || pre.source).toLowerCase()} value is shown. Override again if you still disagree.</div>` : "";
      return `<div class="field"><label for="f_${key}">${esc(label)}</label>
        <div class="prefill-row">
          <input id="f_${key}" name="${key}" type="number" step="any" value="${esc(pre.value)}" readonly>
          <button type="button" class="btn" data-unlock="${key}">Override</button>
        </div>
        <div class="help" id="prov_${key}"><b>${esc(SOURCE_WORDS[pre.source] || pre.source)}</b> — ${prov}.${pre.source === "manual" ? "" : " Computed, never typed; override only when you have reason to disagree."}</div>
        ${cautionLines(pre.cautions)}
        ${prior}<div class="help">${esc(help)}</div>${refLines}</div>`;
    }
    let v = standing && standing.method === cur ? standing.inputs[key] : "";
    let extra = "";
    if (pre && pre.status === "absent") {
      sourcesInit[key] = { used: "typed", provenance: "entered by hand — " + pre.reason, asof: null };
      extra = `<div class="help">Not computed — ${esc(pre.reason)}. A number typed here is your own; the record will say so.</div>`;
    }
    if (v === "" || v === undefined) {
      if (DEFAULT_KEYS.includes(key) && S.journal.settings[key] !== undefined && S.journal.settings[key] !== null) {
        v = S.journal.settings[key];
        extra = `<div class="help">From this journal's valuation defaults (Data tab) — set once, used everywhere.</div>`;
      }
    }
    return `<div class="field"><label for="f_${key}">${esc(label)}</label>
      <input id="f_${key}" name="${key}" type="number" step="any" value="${esc(v ?? "")}">
      ${extra}<div class="help">${esc(help)}</div>${refLines}</div>`;
  }).join("");
  const unlocked = new Set();
  dialog({
    title: `Expected value · ${s.ticker}`,
    blurb: meth.blurb + "  ·  " + meth.who,
    body: pfFailed + `<div class="field"><label for="f_method">Method</label>
        <select id="f_method" name="method">${opts}</select>
        <div class="help">Changing the method reopens this with its own assumptions.</div></div>${inputs}`,
    confirm: "Compute",
    onConfirm: async (d) => {
      if (d.method !== cur) { $("dlg").close(); dlgEV(find(s.ticker), d.method); return true; }
      const inputsObj = {}, sources = {};
      meth.inputs.forEach(([k]) => {
        inputsObj[k] = d[k];
        const si = sourcesInit[k];
        if (!si) return;
        if (unlocked.has(k) && String(d[k]) !== si.offered) {
          sources[k] = { used: "overridden", instead_of: si.used,
            provenance: si.provenance, cautions: si.cautions || [],
            asof: si.asof, offered: si.offered };
        } else {
          sources[k] = { used: si.used, provenance: si.provenance,
            cautions: si.cautions || [], asof: si.asof };
        }
      });
      const r = await api("record_valuation", s.ticker, d.method, inputsObj, sources);
      if (!r) return " ";
      toast(r.recorded === false
        ? `${r.result.label}: ${r.result.display} — unchanged, so nothing was added to the record.`
        : `${r.result.label}: ${r.result.display}`);
    },
  });
  $("dlgbody").querySelectorAll("[data-unlock]").forEach((b) => {
    b.onclick = () => {
      const k = b.dataset.unlock;
      const el = $("f_" + k);
      el.readOnly = false;
      el.focus();
      unlocked.add(k);
      b.remove();
      const pl = $("prov_" + k);
      if (pl) pl.innerHTML = `<b>Overriding by hand.</b> The record will keep what this replaced: ` + pl.innerHTML;
    };
  });
}

function dlgExplain(seq) {
  const c = (S.rule_changes || []).find((x) => x.seq === Number(seq));
  const moved = c ? (c.moved || []) : [];
  dialog({
    title: `Rule change ${seq}`,
    blurb: "This change is already on the record. Write down why it was made — in two years this line will be the most useful thing here.",
    body: (moved.length ? `<div class="dlg-err" style="background:var(--card-2);border-left-color:var(--ink);color:var(--ink-2)">
        ${moved.map((m) => esc(movedLine(m))).join("<br>")}</div>` : "")
      + area("reason", "Why was this changed?", "",
        "For example: “Overrides on the leverage limit kept working out, so widening it from 2.5× to 3.0×.” Written once; it cannot be edited later."),
    confirm: "Record the reason",
    onConfirm: async (d) => {
      if (!(d.reason || "").trim()) return "A reason is required.";
      const r = await api("explain_rule_change", Number(seq), d.reason);
      if (!r) return " ";
      toast(`Recorded the reason for change ${seq}.`);
    },
  });
}

/* ----------------------------------------------------------------- events */
document.addEventListener("click", async (ev) => {
  const t = ev.target;
  if (t.closest("[data-close]")) return;

  const tip = t.closest("[data-tip]");
  if (tip) { const id = tip.dataset.tip; tipOpen = tipOpen === id ? null : id; return render(); }

  const tb = t.closest("[data-tab]");
  if (tb) { tab = tb.dataset.tab; closeSecurity(); return render(); }

  const jb = t.closest("[data-journal]");
  if (jb) {
    if (!S.journal || jb.dataset.journal !== S.journal.id) {
      const r = await api("open_journal", jb.dataset.journal);
      if (r) { closeSecurity(); tab = "holdings"; await refresh(); }
    }
    return;
  }

  const act = t.closest("[data-act]");
  if (!act) {
    const row = t.closest("tbody tr");
    if (row) { openSecurity(row.dataset.t, row.dataset.p); render(); window.scrollTo({ top: 0 }); }
    return;
  }

  /* A button may name the security it is about. The detail page's buttons do
     not need to — there is only one security on it — but the allocation view
     has a row per name, and resolving from `openTicker` there would silently
     act on nothing. Named wins; the open ticker is the fallback. */
  const s = act.dataset.t ? find(act.dataset.t)
    : openTicker ? find(openTicker) : null;
  switch (act.dataset.act) {
    case "back": closeSecurity(); return render();
    case "opensec":
      if (!s) return;
      openSecurity(s.ticker); render();
      return window.scrollTo({ top: 0 });
    case "newjournal": return dlgNewJournal();
    case "renamejournal": return dlgRenameJournal();
    case "deletejournal": return dlgDeleteJournal();
    case "add": return dlgAdd();
    case "remove": {
      if (!s) return;
      /* Only ideas reach this button; the backend re-checks regardless.
         Say exactly what goes with it — an informed removal, not a shrug. */
      const lost = [];
      /* Counted off the dated records, so what goes is what was written —
         including versions since amended and figures since withdrawn. Those
         are the record, not clutter on top of it. */
      const vals = (s._inputs || []).reduce((n, m) => n + (m.entries || []).length, 0);
      const notes = (s.notes || []).length;
      const amend = ((s._thesis || {}).history || []).length;
      const claims = ((s._valuation || {}).history || []).length;
      const judged = (s._judgements || []).reduce((n, j) => n + (j.history || []).length, 0);
      if (vals) lost.push(`${vals} hand-entered value${vals === 1 ? "" : "s"}`);
      if (notes) lost.push(`${notes} note${notes === 1 ? "" : "s"}`);
      if (amend) lost.push(`its thesis${amend > 1 ? ` and ${amend - 1} amendment${amend === 2 ? "" : "s"}` : ""}`);
      if (claims) lost.push(`${claims} valuation${claims === 1 ? "" : "s"}`);
      if (judged) lost.push(`${judged} assessment${judged === 1 ? "" : "s"}`);
      dialog({
        title: `Remove ${s.ticker}`,
        blurb: "It was never a position, so no decision history is lost. Positions and previous holdings can never be removed.",
        body: `<p class="hint">${lost.length
          ? `Going with it: ${lost.join(", ")}.`
          : "Nothing else was recorded on it."}
          Fetched filings and prices stay cached on disk, so adding the ticker again starts warm.</p>`,
        confirm: "Remove", danger: true,
        onConfirm: async () => {
          const r = await api("remove_security", s.ticker);
          if (!r) return " ";
          closeSecurity();
          tab = "ideas";
          toast(`${r.removed} removed from this journal.`);
        },
      });
      return;
    }
    case "fetchdata": {
      if (!s) return;
      const r = await api("fetch_security", s.ticker);
      if (r) {
        s._fetch = { running: true, stage: "starting" };
        render();
        startFetchPoll(s.ticker);
      }
      return;
    }
    case "save-valuation": {
      const r = await api("save_valuation_defaults",
        $("vd_dr").value, $("vd_tg").value, $("vd_mos").value);
      if (r) { toast("Valuation defaults saved — they prefill every new calculation in this journal."); await refresh(); }
      return;
    }
    case "save-identity": {
      const r = await api("save_sec_identity", $("ds_ident").value);
      if (r) { toast("SEC identity saved — on this machine only."); await refresh(); }
      return;
    }
    case "save-key": {
      const el = $("ds_token");
      const r = await api("save_api_key", el.value);
      if (r) {
        el.value = "";        /* the key went in; it never comes back out */
        toast(`Key saved to ${r.storage && r.storage.where ? r.storage.where : "the credential store"}.`);
        await refresh();
      }
      return;
    }
    case "test-key": {
      const r = await api("test_api_key");
      if (r) toast(r.valid ? `Key works: ${r.message}` : `Key failed: ${r.message}`, !r.valid);
      return;
    }
    case "remove-key": {
      dialog({
        title: "Remove the API key",
        blurb: "Prices stop fetching until a new key is saved; everything already stored stays.",
        body: '<p class="hint">Filing data is unaffected. Price-dependent measures will show why they can\'t compute.</p>',
        confirm: "Remove key", danger: true,
        onConfirm: async () => {
          if (!(await api("remove_api_key"))) return " ";
          toast("Key removed.");
        },
      });
      return;
    }
    case "metrics": return dlgMetrics(s);
    case "judge": return dlgJudgement(s, act.dataset.jid);
    /* The way out of a verdict blocked on something only you can answer.
       It goes to the questions rather than opening one of them: which of
       them is owed is the section's business, and a verdict that blocks on
       three would otherwise have to pick one to be the button. */
    case "judgement": {
      const sec = $("judgements");
      if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    case "thesis": return dlgThesis(s);
    /* The way out of a verdict blocked because this journal has no list, and
       the button on the list screen itself. Both land on the same dialog. */
    case "list":
      closeSecurity(); tab = "list"; render();
      return S.list && !S.list.current ? dlgImportList() : undefined;
    case "importlist": return dlgImportList();
    case "passover": return dlgPassOver(act.dataset.t);
    /* Track a name off the list. If the journal already has it, this is just
       a way to reach its page; if not, it is created first — the list is a
       set of ticker strings, and a security record appears when somebody
       does something about one rather than fifty at a time on import. */
    case "listadd": {
      const t = act.dataset.t;
      if (!find(t)) {
        const r = await api("add_security", t, t);
        if (!r) return;
        await refresh();
      }
      openSecurity(t); render();
      return window.scrollTo({ top: 0 });
    }
    case "note": return dlgNote(s);
    case "buy": return dlgBuy(s);
    case "sell": return dlgSell(s);
    case "backfill": return dlgBackfill(s);
    case "ev": return dlgEV(s);
    case "settings": return dlgSettings();
    case "explain": return dlgExplain(act.dataset.seq);
    case "export": {
      const r = await api("export_data");
      if (r && !r.cancelled) toast("Exported to " + r.path);
      return;
    }
    case "import": {
      const have = (S.journals || []).length;
      dialog({
        title: "Import a backup",
        blurb: "This replaces the journals on this machine with the ones in the backup file.",
        body: `<p class="hint">${have
          ? `Any of your ${have} journal${have === 1 ? "" : "s"} the backup does not contain is removed.
             Everything here is exported beside your data first, so an import can be undone.`
          : "There is nothing here to replace."}
          Filings, prices and your API key are untouched.</p>`,
        confirm: "Choose a file…", danger: have > 0,
        onConfirm: async () => {
          const r = await api("import_data");
          if (!r) return " ";
          if (r.cancelled) return;
          const s = r.summary;
          const gone = (s.removed || []).length
            ? ` ${s.removed.length} journal${s.removed.length === 1 ? " was" : "s were"} removed.` : "";
          const kept = (s.kept_unreadable || []).length
            ? ` ${s.kept_unreadable.length} unreadable journal${s.kept_unreadable.length === 1 ? " was" : "s were"} left untouched.` : "";
          toast(`Imported ${s.journals} journal${s.journals === 1 ? "" : "s"}, `
            + `${s.securities} securities.${gone}${kept}`);
          closeSecurity();
        },
      });
      return;
    }
    case "sample": {
      dialog({
        title: "Load the sample journals",
        blurb: "Invented companies in journals of their own, so nothing you have recorded is touched.",
        body: `<p class="hint">Every company, price and figure in them is made up. They exist to show what the
          verdicts look like once a journal has some history — including the uncomfortable ones.</p>
          <p class="hint">One journal per strategy, because a journal has exactly one. Open the same kind of
          company in each and you will see them disagree, which is the thing worth understanding before you
          pick one.</p>
          <p class="hint">You can empty or ignore them afterwards; they are ordinary journals.</p>`,
        confirm: "Load them",
        onConfirm: async () => {
          const r = await api("load_sample");
          if (!r) return " ";
          closeSecurity();
          const missed = (r.skipped || []).length
            ? ` ${r.skipped.length} could not be loaded.` : "";
          toast(`Created ${r.journals} journal${r.journals === 1 ? "" : "s"} `
            + `with ${r.n} securities.${missed}`);
        },
      });
      return;
    }
    case "clear": {
      dialog({
        title: "Empty this journal",
        blurb: `This removes every security from ${S.journal.name}. Its strategy, its settings and its rule-change record stay.`,
        body: '<p class="hint">Export first if you might want any of it back. Other journals are untouched.</p>',
        confirm: "Empty it", danger: true,
        onConfirm: async () => { if (!(await api("clear_all"))) return " "; closeSecurity(); },
      });
      return;
    }
  }
});

/* The bank search re-renders only the list, so the input keeps focus. */
document.addEventListener("input", (ev) => {
  if (ev.target.id !== "banksearch") return;
  C.search = ev.target.value;
  const list = $("banklist"), count = $("bankcount");
  if (list) list.innerHTML = bankListHTML();
  if (count) count.textContent = bankCountText();
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && openTicker && !$("dlg").open) { closeSecurity(); render(); }
});

window.addEventListener("pywebviewready", refresh);
if (window.pywebview && window.pywebview.api) refresh();
