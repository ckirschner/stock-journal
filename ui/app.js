/* The view layer knows nothing about which metrics exist. Everything it draws
   comes from the resolved profiles, the bank metadata and the evaluations
   Python sends over. Adding a metric to the bank, or an entry to a profile,
   changes no code here. */

let S = null;                 // last state from Python
let tab = "holdings";
let openTicker = null;
let tipOpen = null;
let lens = null;              // profile file currently viewed through

const TABS = [
  ["holdings", "Current holdings"],
  ["previous", "Previous holdings"],
  ["ideas", "Ideas"],
  ["profiles", "Profiles"],
  ["metrics", "Metrics"],
  ["data", "Data"],
];
const BUCKETS = ["holdings", "previous", "ideas"];

/* Config pages keep their own lazy state. Selection lives in memory only,
   like the open tab — nothing is persisted browser-side. */
let C = {
  selected: null,             // profiles page selection
  bank: null, bankErr: null, loadingBank: false,
  search: "",
  coverage: null, coverageFor: null, loadingCoverage: false,
};
let FETCH_POLLS = {};         // ticker -> true while a poll loop runs

/* ------------------------------------------------------------------ words */
/* Semantic verdicts arrive from Python; the words are a view concern. */
const BUY_WORDS = {
  ideas: { buy: "Buy", no_buy: "No buy", cant_say: "Can't say" },
  holdings: { buy: "Qualifies", no_buy: "Not now", cant_say: "Can't say" },
  previous: { buy: "Would buy", no_buy: "Would not buy", cant_say: "Can't say" },
};
const BUY_TONES = { buy: "pass", no_buy: "fail", cant_say: "none" };
const POS_WORDS = { fired: "Sell signal", breached: "Unconfirmed breach",
  clear: "Hold", unwatched: "Unwatched" };
const POS_TONES = { fired: "fail", breached: "watch", clear: "pass", unwatched: "none" };
const SELL_STATUS = {
  fired: ["Fired", "s-fail"], breached: ["Breached — unconfirmed", "s-watch"],
  clear: ["Clear", "s-pass"], unevaluable: ["Can't check", "s-none"],
  no_threshold: ["No threshold, by choice", "blank"],
};
const FLAG_STATUS = {
  flagged: ["Flagged", "s-watch"], clear: ["Clear", "s-pass"],
  unevaluable: ["Can't check", "s-none"],
};

/* ------------------------------------------------------------------ utils */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* Formatter for the retired metric set, used only on frozen legacy records. */
function fmtLegacy(v, f) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (f === "pct") return n.toFixed(1) + "%";
  if (f === "pctd") return (n >= 0 ? "+" : "") + n.toFixed(1) + "%";
  if (f === "ppt") return (n >= 0 ? "+" : "") + n.toFixed(1) + "pp";
  if (f === "x") return n.toFixed(2) + "×";
  return String(n);
}

/* The bank's format strings: "0.0%", "0.00x", "$0,0", "+0.0 pp", "0 of 10",
   "+0,0 sh", "0 yrs", "0.00", "0". Parsed generically — no metric named. */
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
const bankMeta = (id) => (S.bank_meta || {})[id] || null;
const labelOf = (id) => {
  const b = bankMeta(id);
  if (b && b.label) return b.label;
  const l = (S.legacy_labels || {})[id];
  return l ? l.label + " (retired)" : id;
};
const fmtMetric = (id, v) => {
  const b = bankMeta(id);
  if (b) return fmtBank(v, b.format);
  const l = (S.legacy_labels || {})[id];
  return l ? fmtLegacy(v, l.fmt) : String(v);
};

const money = (n) => (n === null || n === undefined) ? "—" : "$" + Number(n).toFixed(2);
/* Effective price: hand-entered wins; otherwise the newest fetched close.
   The source and date travel with it so a stale quote is visibly stale. */
const px = (s) => (s._price && s._price.value != null) ? s._price.value : s.price;
/* A close's age must be readable at a glance: a year-old close shown as
   MM-DD reads as days old, which is the display lying about staleness. */
function fmtCloseDate(d) {
  if (!d) return "";
  const s = String(d).slice(0, 10);
  return s.startsWith(String(new Date().getFullYear()) + "-") ? s.slice(5) : s;
}
function priceCell(s) {
  const p = s._price;
  if (!p || p.value == null) return money(null);
  if (p.source === "fetched")
    return `${money(p.value)} <span class="dim" title="Fetched close, as of ${esc(p.date)}">·${esc(fmtCloseDate(p.date))}</span>`;
  return money(p.value);
}
function dataFact(s) {
  if (s._fetch && s._fetch.running) return "fetching…";
  const d = s._data;
  if (!d) return "never fetched";
  const when = d.last_fetch ? String(d.last_fetch.at).slice(0, 10) : "never";
  return `${d.filings_held} filings · fetched ${when}`;
}
function pctCell(v) {
  if (v === null || v === undefined) return '<span class="dim">—</span>';
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
  if (r) {
    S = r;
    if (!lens || !S.profiles[lens]) {
      lens = (S.settings.active_profile && S.profiles[S.settings.active_profile])
        ? S.settings.active_profile : (S.profile_order[0] || null);
    }
    if (!C.selected || !S.profiles[C.selected]) C.selected = lens;
    render();
  }
}

const inBucket = (b) => S.securities.filter((s) => s.bucket === b);
const find = (t) => S.securities.find((s) => s.ticker === t);
const lensProfile = () => (lens && S.profiles[lens]) || null;
const evalFor = (s) => (lens && s._eval && s._eval[lens]) || null;
const profLabel = (p) => p ? `${p.name} v${p.version ?? "?"}` : "—";

/* ---------------------------------------------------------------- chrome */
function renderMast() {
  const h = inBucket("holdings");
  /* A holding without a price must never enter these sums as zero — that
     would render a confident, wrong loss in the most prominent numbers in
     the app. Absence propagates: any unpriced holding makes the totals
     honestly unknown. */
  const unpriced = h.filter((s) => px(s) == null).length;
  const mv = h.reduce((a, s) => a + (px(s) || 0) * (s.position ? s.position.shares : 0), 0);
  const cb = h.reduce((a, s) => a + (s.position ? s.position.cost_basis * s.position.shares : 0), 0);
  const mvTxt = unpriced ? "—" : "$" + mv.toLocaleString(undefined, { maximumFractionDigits: 0 });
  const unrealTxt = (unpriced || !cb) ? "—" : (mv >= cb ? "+" : "") + ((mv / cb - 1) * 100).toFixed(1) + "%";
  const unpricedNote = unpriced ? ` title="${unpriced} of ${h.length} position${h.length === 1 ? "" : "s"} ha${unpriced === 1 ? "s" : "ve"} no price — fetch data or enter one"` : "";
  /* The header counts signals under each position's own profile — the rules
     it was bought under — so the count doesn't change when the lens does. */
  const fired = h.filter((s) => s._own && s._own.state && s._own.state.overall === "fired").length;
  $("maststats").innerHTML = !h.length ? "" :
    `<div><i>Market value${unpriced ? ` · ${unpriced} unpriced` : ""}</i><b${unpricedNote}>${mvTxt}</b></div>
     <div><i>Unrealised</i><b class="${unpriced || !cb ? "" : mv >= cb ? "pos" : "neg"}"${unpricedNote}>${unrealTxt}</b></div>
     <div><i>Positions</i><b>${h.length}</b></div>
     <div><i>Sell signals</i><b class="${fired ? "neg" : ""}" title="Counted under each position's own profile">${fired}</b></div>`;
  const p = lensProfile();
  $("subtitle").textContent = "Portfolio journal" + (p ? ` · viewing through ${profLabel(p)}` : "");
  $("foot").innerHTML = `This tool never places a trade and holds no broker credentials. `
    + `It checks what you tell it against profiles you configured.<br>Data stored at ${esc(S.data_dir)}, never inside the project folder.`;
}
function renderTabs() {
  $("tabs").innerHTML = TABS.map(([id, label]) => {
    const n = BUCKETS.includes(id) ? `<em>${inBucket(id).length}</em>` : "";
    return `<button class="tab" role="tab" aria-selected="${tab === id}" data-tab="${id}">${label}${n}</button>`;
  }).join("");
}

function lensBar() {
  if (!S.profile_order.length) return "";
  return `<span class="lenslabel">Lens</span><span class="seg">${
    S.profile_order.map((f) => `<button type="button" data-lens="${esc(f)}"
      aria-pressed="${f === lens}">${esc(S.profiles[f].name)}</button>`).join("")}</span>`;
}

/* Profile edits made outside the app are already on the record; what is
   still owed is the reason. Loud until written. */
function pendingBanner() {
  const pend = S.pending_changes || [];
  if (!pend.length) return "";
  return `<div class="pending"><h4>Profile changes without a written reason</h4>
    ${pend.map((c) => `<div class="pendrow">
      <b>${esc(c.file)} v${c.version}</b>
      <ul>${(c.changes || []).map((l) => `<li>${esc(l)}</li>`).join("")}</ul>
      <button class="btn" data-act="explain" data-file="${esc(c.file)}" data-version="${c.version}">Write the reason</button>
    </div>`).join("")}
    <p class="hint" style="margin-top:10px">The change itself is recorded either way — with a timestamp and the
    exact lines that moved. The reason is the part only you can supply, and it is written once.</p></div>`;
}

const cfgErrorBox = (errs) => !errs.length ? "" :
  `<div class="notice"><h4>Configuration problem</h4>
   ${errs.map((e) => `<p>${esc(e)}</p>`).join("")}</div>`;

/* ----------------------------------------------------------------- lists */
function buyPill(b) {
  if (!b) return '<span class="score s-none">—</span>';
  const ko = b.tiers.find((t) => t.requires === "all_green" && t.outcome === "fail");
  if (ko) return `<span class="score s-fail">${esc((ko.key || "").toUpperCase())} ✗</span>`;
  const core = b.tiers.filter((t) => t.requires === "at_least");
  if (!core.length) return "";
  const g = core.reduce((a, t) => a + t.greens, 0);
  const n = core.reduce((a, t) => a + t.count, 0);
  const keys = core.map((t) => t.key).join(" + ");
  return `<span class="score s-${BUY_TONES[b.verdict]}" title="${esc(keys)} entries green">${g}/${n}</span>`;
}
function verdictCell(s) {
  const ev = evalFor(s);
  if (!ev) return '<span class="stamp v-none">—</span>';
  if (s.bucket === "holdings" && ev.position) {
    const o = ev.position.overall;
    return `<span class="stamp v-${POS_TONES[o]}">${POS_WORDS[o]}</span>`;
  }
  const v = ev.buy.verdict;
  return `<span class="stamp v-${BUY_TONES[v]}">${BUY_WORDS[s.bucket][v]}</span>`;
}

function listView() {
  const rows = inBucket(tab);
  const addBtn = tab === "previous" ? ""
    : `<button class="btn primary" data-act="add">${tab === "ideas" ? "Add a candidate" : "Add a security"}</button>`;
  let html = pendingBanner();
  html += `<div class="toolbar" style="justify-content:space-between;align-items:center">
    <div class="lensbar">${lensBar()}</div><div>${addBtn}</div></div>`;
  if (!lens) return html + cfgErrorBox(S.profile_errors.length ? S.profile_errors
    : ["No profiles found on disk. Profiles live as .yaml files in the profiles folder inside your data directory."]);

  if (!rows.length) {
    const msg = {
      holdings: "No open positions. Add a security, enter its metrics, then record a purchase.",
      previous: "Nothing closed yet. When you exit a position it stays here so you can see what happened next.",
      ideas: "No candidates yet. Add one and the profile will tell you where it stands.",
    }[tab];
    return html + `<div class="sheet"><div class="empty"><p>${msg}</p>
      ${tab !== "previous" ? '<button class="btn primary" data-act="add">Add a security</button>' : ""}</div></div>`;
  }

  let head, body;
  if (tab === "holdings") {
    head = '<th class="l">Position</th><th>Price</th><th>Cost</th><th>Since buy</th><th class="hide-sm">Score</th><th>Verdict</th>';
    body = rows.map((s) => {
      const ownFired = s._own && s._own.state && s._own.state.overall === "fired";
      const ownName = s._own && s._own.profile ? s._own.profile.name : "";
      return `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
      ${s.override ? '<span class="flagdot" title="Bought against or without the signal"></span>' : ""}
      ${ownFired ? `<span class="flagdot" title="Sell signal under ${esc(ownName)}, the profile it was bought under"></span>` : ""}
      <div class="coname">${esc(s.name)}</div></td>
      <td>${priceCell(s)}</td><td class="dim">${money(s.position && s.position.cost_basis)}</td>
      <td>${pctCell(s._realised)}</td>
      <td class="hide-sm">${buyPill(evalFor(s) && evalFor(s).buy)}</td>
      <td>${verdictCell(s)}</td></tr>`;
    }).join("");
  } else if (tab === "previous") {
    head = '<th class="l">Position</th><th>Return held</th><th>Since exit</th><th class="hide-sm">Exit reason</th><th class="hide-sm">Score</th><th>Today</th>';
    body = rows.map((s) => {
      const ex = s.exit || {};
      return `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
        <div class="coname">${esc(s.name)}</div></td>
        <td>${pctCell(ex.return_pct)}</td><td>${pctCell(s._since_exit)}</td>
        <td class="hide-sm"><span class="chip s-none">${esc(ex.reason || "")}</span></td>
        <td class="hide-sm">${buyPill(evalFor(s) && evalFor(s).buy)}</td>
        <td>${verdictCell(s)}</td></tr>`;
    }).join("");
  } else {
    head = '<th class="l">Candidate</th><th>Price</th><th class="hide-sm">Added</th><th class="hide-sm">Score</th><th>Verdict</th>';
    body = rows.map((s) => `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
      <div class="coname">${esc(s.name)}</div></td>
      <td>${priceCell(s)}</td><td class="dim hide-sm">${esc(s.added)}</td>
      <td class="hide-sm">${buyPill(evalFor(s) && evalFor(s).buy)}</td>
      <td>${verdictCell(s)}</td></tr>`).join("");
  }
  html += `<div class="sheet"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  if (tab === "previous") html += scorecards();
  return html;
}

function scorecards() {
  const o = S.override_scorecard, x = S.exit_scorecard;
  const line = (k, v) => `<div class="kv"><span>${esc(k)}</span><b>${v}</b></div>`;
  const summ = (d) => d.n
    ? line("Trades", d.n) + line("Win rate", d.win_rate + "%") + line("Average return", (d.avg >= 0 ? "+" : "") + d.avg + "%")
    : '<p class="hint">Nothing to compare yet.</p>';

  let perRule = "";
  const keys = Object.keys(o.per_rule || {});
  if (keys.length) {
    perRule = keys.map((id) => {
      const b = o.per_rule[id];
      return line(labelOf(id), `${b.wins}/${b.n} · ${b.avg >= 0 ? "+" : ""}${b.avg}%`);
    }).join("");
  }

  const exRows = Object.keys(x).map((reason) => {
    const b = x[reason];
    return line(reason + ` (${b.n})`,
      `held ${b.avg_held === null ? "—" : (b.avg_held >= 0 ? "+" : "") + b.avg_held + "%"}`
      + ` · after ${b.avg_after === null ? "—" : (b.avg_after >= 0 ? "+" : "") + b.avg_after + "%"}`);
  }).join("") || '<p class="hint">No closed positions yet.</p>';

  return `<div class="cards">
    <div class="panel"><h3>Overrides</h3><div class="sub">Bought against or without the signal</div>${summ(o.override)}</div>
    <div class="panel"><h3>Compliant</h3><div class="sub">Bought with the signal</div>${summ(o.compliant)}</div>
    <div class="panel"><h3>By exit reason</h3><div class="sub">Return while held · return since</div>${exRows}
      <p class="hint">If one reason keeps showing a strong return <em>after</em> you sold, that is the sell rule to look at.</p></div>
    ${perRule ? `<div class="panel"><h3>Rules you overrode</h3><div class="sub">Wins / times · average</div>${perRule}
      <p class="hint">If overriding a rule keeps working, the rule is miscalibrated, not you. That is a reason to change the profile, written down.</p></div>` : ""}
  </div>`;
}

/* ---------------------------------------------------------------- detail */
function causeText(buy) {
  if (!buy || !buy.causes.length) {
    if (!buy) return "";
    const core = buy.tiers.filter((t) => t.requires === "at_least");
    const g = core.reduce((a, t) => a + t.greens, 0), n = core.reduce((a, t) => a + t.count, 0);
    const keys = core.map((t) => t.key).join(" + ");
    return core.length ? `${g} of ${n} ${keys} entries green` : "all tiers clear";
  }
  return buy.causes.map((c) => c.text).join(" · ");
}
function positionNote(pos) {
  if (!pos) return "";
  if (pos.overall === "fired") {
    const which = pos.signals.filter((x) => x.status === "fired").map((x) => labelOf(x.metric));
    if (pos.clock && pos.clock.expired) which.push(`position clock expired ${pos.clock.due}`);
    return which.join(" · ");
  }
  if (pos.overall === "breached")
    return pos.signals.filter((x) => x.status === "breached").map((x) => labelOf(x.metric)).join(" · ") + " — awaiting confirmation";
  if (pos.overall === "unwatched") return "sell thresholds exist but none can currently be checked";
  return pos.watchable ? `${pos.watchable - pos.unevaluable} of ${pos.watchable} sell checks running` : "no sell thresholds";
}

function detailView(s) {
  const isHold = s.bucket === "holdings", isPrev = s.bucket === "previous";
  const prof = lensProfile();
  const ev = evalFor(s);
  let h = pendingBanner();
  h += `<button class="backlink" data-act="back">← ${TABS.find((t) => t[0] === tab)[1]}</button>`;
  if (!prof || !ev) {
    return h + `<div class="dhead"><div class="dtitle"><h1>${esc(s.ticker)}</h1><p>${esc(s.name)}</p></div></div>`
      + cfgErrorBox(["No profile is available to score this security. Check the Profiles tab."]);
  }

  const snap = s.entry_snapshot;
  const snapLegacy = snap && "ruleset_version" in snap;
  const cmp = !!snap && !snapLegacy;
  const stamp = isHold && ev.position
    ? { word: POS_WORDS[ev.position.overall], tone: POS_TONES[ev.position.overall], note: positionNote(ev.position) }
    : { word: BUY_WORDS[s.bucket][ev.buy.verdict], tone: BUY_TONES[ev.buy.verdict], note: causeText(ev.buy) };

  h += `<div class="dhead"><div class="dtitle"><h1>${esc(s.ticker)}</h1><p>${esc(s.name)}</p>
    <div class="meta">${isHold ? "Opened " + esc(s.position.opened)
      : isPrev ? "Closed " + esc(s.exit.date) + " · " + esc(s.exit.reason)
      : "Added " + esc(s.added)} · viewed through ${esc(profLabel(prof))}</div></div>
    <div style="text-align:right"><span class="stamp big v-${stamp.tone}">${esc(stamp.word)}</span>
    <div class="stamp-note">${esc(stamp.note)}</div></div></div>`;

  const fetching = s._fetch && s._fetch.running;
  h += `<div class="toolbar" style="margin-top:16px;justify-content:space-between;align-items:center">
    <div class="lensbar">${lensBar()}</div><div>
    <button class="btn" data-act="fetchdata" ${fetching ? "disabled" : ""}>${fetching ? "Fetching…" : "Fetch data"}</button>
    <button class="btn" data-act="metrics">Edit metrics</button>
    <button class="btn" data-act="ev">Expected value</button>
    <button class="btn" data-act="falsifier">Falsifier</button>
    <button class="btn" data-act="note">Add note</button>
    ${!isHold && !isPrev ? '<button class="btn primary" data-act="buy">Record a purchase</button>' : ""}
    ${!isHold && !isPrev ? '<button class="btn danger" data-act="remove">Remove</button>' : ""}
    ${isHold ? '<button class="btn danger" data-act="sell">Close position</button>' : ""}
    </div></div>`;
  if (fetching) {
    h += `<p class="hint" id="fetchstate" style="margin:8px 0 0">${esc(fetchStateText(s._fetch))}</p>`;
    startFetchPoll(s.ticker);
  }

  /* facts */
  const priceLabel = (s._price && s._price.source === "fetched")
    ? `Price · close ${String(s._price.date).slice(0, 10)}` : "Price";
  let facts = [];
  if (isHold) {
    facts = [[priceLabel, money(px(s))], ["Cost basis", money(s.position.cost_basis)],
      ["Shares", s.position.shares], ["Since buy", s._realised === null ? "—" : (s._realised >= 0 ? "+" : "") + s._realised + "%"],
      ["Value", px(s) ? "$" + (px(s) * s.position.shares).toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"]];
  } else if (isPrev) {
    facts = [["Exit price", money(s.exit.price)],
      ["Return held", s.exit.return_pct === null || s.exit.return_pct === undefined
        ? "—" : (s.exit.return_pct >= 0 ? "+" : "") + s.exit.return_pct + "%"],
      ["Since exit", s._since_exit === null ? "—" : (s._since_exit >= 0 ? "+" : "") + s._since_exit + "%"],
      ["Reason", s.exit.reason]];
  } else {
    facts = [[priceLabel, money(px(s))], ["Added", s.added],
      ["Values entered", Object.keys(s.metrics || {}).length + " of " + S.input_metrics.length]];
  }
  facts.push(["Filing data", dataFact(s)]);
  h += '<div class="facts">' + facts.map((f) =>
    `<div class="fact"><i>${esc(f[0])}</i><b>${esc(f[1])}</b></div>`).join("") + "</div>";

  /* notices */
  if (s.override) {
    const failed = (s.override.failed || []).map(labelOf).join(", ");
    const missing = (s.override.missing || []).map(labelOf).join(", ");
    const under = s.override.profile ? ` under ${esc(s.override.profile.name)} v${s.override.profile.version}` : "";
    h += `<div class="notice"><h4>${failed ? "Bought against signal" : "Bought without a signal"}</h4>
      <p>On ${esc(s.override.date)} this evaluated to <strong>${esc(s.override.verdict)}</strong>${under}.
      ${failed ? esc(failed) + " failed." : ""}${missing ? " " + esc(missing) + " could not be evaluated." : ""}
      The purchase was recorded anyway.${s._realised !== null ? ` Position is ${s._realised >= 0 ? "up" : "down"} ${Math.abs(s._realised).toFixed(1)}% since.` : ""}</p>
      <q>${esc(s.override.reason)}</q></div>`;
  }
  if (isPrev && s.exit && s.exit.rule_triggered === false) {
    const exProf = s.exit.profile ? ` under ${esc(s.exit.profile.name)} v${s.exit.profile.version}`
      + (s.exit.governing ? " (the profile it was bought under)" : " (the lens in use at close — the position had no governing profile)")
      : ` under ruleset v${esc(s.exit.ruleset_version ?? "?")}, before profiles`;
    h += `<div class="notice"><h4>No rule triggered this exit</h4>
      <p>The signal read <strong>${esc(s.exit.signal_at_exit)}</strong>${exProf} on ${esc(s.exit.date)}.
      ${s._since_exit !== null ? `The position is ${s._since_exit >= 0 ? "up" : "down"} ${Math.abs(s._since_exit).toFixed(1)}% since it was closed.` : ""}</p></div>`;
  }
  if (isPrev && s.exit && s.exit.rule_triggered === null && s.exit.profile) {
    h += `<div class="notice quiet"><h4>Closed without its rules</h4>
      <p>This position was governed by ${esc(s.exit.profile.name)} v${esc(s.exit.profile.version)}, but that
      profile was not on disk when the position was closed on ${esc(s.exit.date)}, so no signal could be
      evaluated. That absence is on the record, not papered over.</p></div>`;
  }
  if (isHold && !(s.falsifier || "").trim()) {
    h += `<div class="notice quiet"><h4>No falsifier on record</h4>
      <p>This position is open without a written answer to "what would make me wrong?".
      That is the field you will want when it drops 25% and you are deciding whether to add or exit.</p></div>`;
  }
  if (s.legacy_metrics && Object.keys(s.legacy_metrics).length) {
    const whys = {};
    ((S.migration || {}).preserved || []).forEach((p) => { whys[p.id] = p.why; });
    h += `<div class="notice quiet"><h4>Values from the retired metric set</h4>
      <p>These were recorded before the metric bank and have no bank equivalent. They are preserved
      exactly as entered and are not scored — rescoring them against a different definition would be
      pretending they measure something they don't.</p>
      <ul class="pe-nmw" style="margin-top:8px">${Object.entries(s.legacy_metrics).map(([id, v]) => {
        const l = (S.legacy_labels || {})[id] || { label: id, fmt: null };
        return `<li><b>${esc(l.label)}</b>: ${esc(fmtLegacy(v, l.fmt))}${whys[id] ? ` <span class="dim">— ${esc(whys[id])}</span>` : ""}</li>`;
      }).join("")}</ul></div>`;
  }

  /* sell watch — under the profile the position was bought under */
  if (isHold) h += sellWatch(s, ev);

  /* buy tiers under the lens */
  h += tierSections(s, prof, ev.buy, cmp ? snap : null);

  /* where the numbers come from */
  h += coverageSection(s);

  /* panels */
  h += '<div class="panels">';
  h += `<div class="panel" id="evpanel"><h3>Expected value</h3><div class="sub">${s.ev ? esc(S.ev_methods[s.ev.method].label) : "Not calculated"}</div>`;
  if (s.ev) {
    const meth = S.ev_methods[s.ev.method];
    h += '<div class="assump">';
    meth.inputs.forEach(([key, label]) => {
      h += `<div class="k">${esc(label)}</div><div class="v">${esc(s.ev.inputs[key] ?? "—")}</div>`;
    });
    h += `</div><div class="evout" id="evout"><div><div class="lbl">Computing…</div><div class="big">—</div></div></div>`;
    h += `<p class="locked">Computed ${esc(s.ev.computed)} from the assumptions above. There is no field anywhere that accepts a target price.</p>`;
  } else {
    h += `<p class="fals">${esc(S.ev_methods[S.settings.default_ev_method].blurb)}</p>
      <p class="locked">You enter assumptions; the value is solved for. That way, when the estimate is wrong, you can see which assumption was wrong.</p>`;
  }
  h += "</div>";

  h += `<div class="panel"><h3>Journal</h3><div class="sub">Falsifier and notes</div>
    <div class="fals"><em>What would make me wrong</em>${esc(s.falsifier) || '<span class="dim">Not yet written.</span>'}
    <em>Notes</em></div>
    <ul class="notelist">${(s.notes || []).slice().reverse().map((n) =>
      `<li><time>${esc(String(n.date).slice(0, 10))}</time><p>${esc(n.text)}</p></li>`).join("")
      || '<li><p class="dim">No entries yet.</p></li>'}</ul>`;
  if (snap && !snapLegacy) {
    const sp = snap.profile || {};
    const word = BUY_WORDS.ideas[(snap.result || {}).verdict] || "—";
    h += `<p class="locked">Entry snapshot frozen ${esc(String(snap.frozen).slice(0, 10))} under
      ${esc(sp.name)} v${esc(sp.version)} — it read <b>${esc(word)}</b> then. The snapshot is never
      recomputed, so restatements and profile changes cannot rewrite it.</p>`;
  }
  if (snap && snapLegacy) {
    h += `<p class="locked">Entry snapshot frozen ${esc(String(snap.frozen).slice(0, 10))} under the
      retired ruleset system (v${esc(snap.ruleset_version)}) — it read <b>${esc((snap.result || {}).verdict || "—")}</b> then.
      It is preserved as recorded and never re-scored.</p>
      <details class="whybox"><summary>Values at entry, retired metric set</summary>
      <ul class="pe-nmw" style="margin-top:8px">${Object.entries(snap.metrics || {}).map(([id, v]) => {
        const l = (S.legacy_labels || {})[id] || { label: id, fmt: null };
        return `<li>${esc(l.label)}: ${esc(fmtLegacy(v, l.fmt))}</li>`;
      }).join("") || "<li>No values were recorded.</li>"}</ul></details>`;
  }
  h += "</div></div>";
  return h;
}

function sellWatch(s, lensEv) {
  const own = s._own || {};
  let intro, state;
  if (own.legacy) {
    intro = `This position was recorded before profiles, so no profile governs it.
      The signals below are read through the current lens, ${esc(profLabel(lensProfile()))} — a view, not a contract.`;
    state = lensEv.position;
  } else if (own.problem) {
    return `<section class="group"><div class="ghead"><h3>Sell watch</h3></div>
      ${cfgErrorBox([own.problem])}</section>`;
  } else {
    intro = `Governed by ${esc(profLabel(own.profile))}, the profile it was bought under`
      + (own.bought_version != null && own.profile && own.bought_version !== own.profile.version
        ? ` (bought at v${esc(own.bought_version)} — the profile has changed since, and its current rules are what runs)` : "")
      + "."
      + (own.profile && own.profile.file !== lens
        ? ` The lens above changes how the tiers below are read; it does not change these sell rules.` : "");
    state = own.state;
  }
  if (!state) return "";

  let rows = "";
  if (state.clock) {
    const c = state.clock;
    const [txt, cls] = c.expired ? ["Expired", "s-fail"] : ["Running", "s-pass"];
    rows += `<div class="srow"><div class="sname">Position clock</div>
      <div class="scond">${c.due ? `sell after ${c.months} months — due ${esc(c.due)}` : esc(c.problem || "")}</div>
      <div class="sstate"><span class="chip ${c.due ? cls : "s-none"}">${c.due ? txt : "Can't run"}</span></div></div>`;
  }
  state.signals.forEach((sig) => {
    const [txt, cls] = SELL_STATUS[sig.status] || [sig.status, "s-none"];
    const cond = sig.status === "no_threshold" ? "" : condText(sig.condition) || "";
    const measured = sig.measured_on && sig.measured_on !== sig.metric
      ? `<span class="dim"> — measured on ${esc(labelOf(sig.measured_on))}</span>` : "";
    const val = sig.status === "no_threshold" ? ""
      : ` <span class="dim">now ${esc(fmtMetric(sig.measured_on || sig.metric, sig.value))}${
        sig.entry_value !== null && sig.entry_value !== undefined
          ? ", at entry " + esc(fmtMetric(sig.measured_on || sig.metric, sig.entry_value)) : ""}</span>`;
    rows += `<div class="srow"><div class="sname">${esc(labelOf(sig.metric))}${measured}</div>
      <div class="scond">${cond ? esc0(cond) : '<span class="dim">no sell threshold, by choice</span>'}${val}
      ${sig.needs ? `<div class="greynote">${esc(sig.needs)}</div>` : ""}</div>
      <div class="sstate"><span class="chip ${cls}">${esc(txt)}</span></div></div>`;
  });
  state.flags.forEach((f) => {
    const [txt, cls] = FLAG_STATUS[f.status] || [f.status, "s-none"];
    const measured = f.measured_on && f.measured_on !== f.metric
      ? `<span class="dim"> — measured on ${esc(labelOf(f.measured_on))}</span>` : "";
    rows += `<div class="srow"><div class="sname">${esc(labelOf(f.metric))}${measured} <span class="req">Flag</span></div>
      <div class="scond">${esc0(condText(f.condition) || "")} <span class="dim">— surfaces only, never blocks</span>
      ${f.needs ? `<div class="greynote">${esc(f.needs)}</div>` : ""}</div>
      <div class="sstate"><span class="chip ${cls}">${esc(txt)}</span></div></div>`;
  });

  const unmon = state.unevaluable
    ? `<p class="hint">${state.unevaluable} of ${state.watchable} sell checks cannot currently run —
       each says why on its row. A check that cannot run is reported, never assumed clear.</p>` : "";
  return `<section class="group"><div class="ghead"><h3>Sell watch</h3>
    <span>${POS_WORDS[state.overall]}</span></div>
    <p class="hint" style="margin:8px 0 0">${intro}</p>
    <div class="slist">${rows || '<p class="hint">This profile defines no sell conditions.</p>'}</div>${unmon}</section>`;
}
/* condText output contains entities (≤, ≥) built from trusted profile config
   already escaped piecewise; pass through. */
const esc0 = (s) => s;

function tierSections(s, prof, buy, snap) {
  const snapProf = snap && snap.profile ? snap.profile : null;
  let h = "";
  prof.tiers.forEach((tier, i) => {
    const evTier = buy.tiers[i] || { entries: [] };
    const outcome = { pass: ["met", "s-pass"], fail: ["not met", "s-fail"],
      indeterminate: ["can't say", "s-none"], score: [`score ${evTier.greens}/${evTier.count}`, "s-none"] }[evTier.outcome] || ["", "s-none"];
    h += `<section class="group"><div class="ghead"><h3>${esc((tier.key || "").toUpperCase())}</h3>
      <span>${esc(tierRuleText(tier))} · <span class="chip ${outcome[1]}">${esc(outcome[0])}</span></span></div>`;
    if (snap) h += `<div class="cmphead">At entry (under ${esc(profLabel(snapProf))}) → now (through ${esc(profLabel(prof))})</div>`;
    tier.entries.forEach((e, j) => {
      const st = (evTier.entries[j] || {});
      const meta = bankMeta(e.metric) || {};
      const vNow = st.value;
      const vEntry = snap ? (snap.metrics || {})[e.metric] : undefined;
      const d = (snap && vEntry !== undefined && vEntry !== null && vNow !== null && vNow !== undefined)
        ? Number(vNow) - Number(vEntry) : null;
      const dGood = d === null ? null
        : meta.polarity === "higher_is_better" ? d >= 0
        : meta.polarity === "lower_is_better" ? d <= 0 : null;
      /* Where the merged value came from, and why a grey one is grey. The
         reason a value is absent lives with the computed layer; it beats the
         generic "no value recorded". */
      const src = (s._value_sources || {})[e.metric];
      const comp = (s._computed || {})[e.metric];
      let reason = st.reason;
      if (reason === "no value recorded" && comp && comp.status === "absent" && comp.reason)
        reason = comp.reason;
      let srcMark = "";
      if (vNow !== null && vNow !== undefined) {
        if (src === "computed") srcMark = '<span class="delta dim" title="Computed from stored filings and prices">filings</span>';
        else if (src === "manual" && comp && comp.status === "computed")
          srcMark = `<span class="delta dim" title="Hand-entered; overrides the computed ${fmtBank(comp.value, meta.format)}">by hand*</span>`;
        else if (src === "manual") srcMark = '<span class="delta dim" title="Hand-entered">by hand</span>';
      }
      h += `<div class="mrow"><div class="mname">${esc(e.label || e.metric)}
        <button class="tip" data-tip="${esc(e.metric)}:${i}" aria-expanded="${tipOpen === e.metric + ":" + i}" aria-label="What is ${esc(e.label || e.metric)}?">?</button>
        ${reason ? `<div class="greynote">${esc(reason)}</div>` : ""}</div>
        ${snap ? `<div class="mval entry">${fmtBank(vEntry, meta.format)}<span class="delta dim">at entry</span></div>` : '<div class="mval entry"></div>'}
        <div class="mval">${fmtBank(vNow, meta.format)}${d !== null
          ? `<span class="delta ${dGood === null ? "dim" : dGood ? "pos" : "neg"}">${d >= 0 ? "+" : "−"}${Math.abs(d) < 0.05 && d !== 0 ? Math.abs(d).toFixed(2) : Math.abs(d).toFixed(1)}</span>` : ""}${srcMark}</div>
        <div class="mthresh">${esc0(condText(e.buy) || "—")}</div>
        <div class="mstate"><span class="chip s-${st.state === "green" ? "pass" : st.state === "red" ? "fail" : "none"}">${esc(st.state || "—")}</span></div>`;
      if (tipOpen === e.metric + ":" + i) {
        const provenance = (src === "computed" && comp && comp.provenance && comp.provenance.length)
          ? `<div class="pe-why"><b>Computed from:</b> ${comp.provenance.map(oneline).join("; ")}</div>` : "";
        const cautions = (src === "computed" && comp && comp.cautions && comp.cautions.length)
          ? `<div class="pe-why"><b>Cautions:</b> ${comp.cautions.map(oneline).join("; ")}</div>` : "";
        const overridden = (src === "manual" && comp && comp.status === "computed")
          ? `<div class="pe-why"><b>Hand-entered value in force.</b> The computed value from filings reads ${fmtBank(comp.value, meta.format)}; clear the hand-entered value in Edit metrics to use it.</div>` : "";
        h += `<div class="tipbox">${prose(e.description)}
          ${e.buy && e.buy.why ? `<div class="pe-why"><b>Why this level:</b> ${prose(e.buy.why)}</div>` : ""}
          ${provenance}${cautions}${overridden}
          ${e.not_meaningful_when && e.not_meaningful_when.length
            ? `<div class="pe-why"><b>Not meaningful when:</b> ${e.not_meaningful_when.map((t) => oneline(t.test)).join("; ")}</div>` : ""}
          <span class="who">Bank entry <code>${esc(e.metric)}</code> — full definition on the Metrics tab</span></div>`;
      }
      h += "</div>";
    });
    h += "</section>";
  });
  return h;
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
  if (openTicker === ticker) render();
}

function coverageSection(s) {
  let inner;
  if (!s.cik) {
    inner = `<p class="hint">Nothing fetched yet. “Fetch data” pulls this company's full filing
      history from SEC EDGAR and its price history from Tiingo, stores the raw reported figures,
      and computes every metric it can. Hand-entered values always win where both exist.</p>`;
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
    /* Problems from the last fetch stay readable here — a toast is not a
       record, and an entry absent because filings failed to extract must
       not read like a fact about the company. */
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
    inner += cov.entries.map((e) => {
      const val = e.status === "computed" ? fmtBank(e.value, e.format) : "—";
      const chip = e.status === "computed"
        ? '<span class="chip s-none">computed</span>'
        : '<span class="chip blank">absent</span>';
      const why = e.status === "computed"
        ? (e.provenance || []).map((p) => `<div class="greynote">${esc(p)}</div>`).join("")
        : `<div class="greynote">${esc(e.reason || "")}</div>`;
      const warn = (e.cautions || []).map((c) => `<div class="greynote">⚠ ${esc(c)}</div>`).join("");
      return `<div class="srow"><div class="sname">${esc(e.label)}</div>
        <div class="scond">${val === "—" ? "" : `<b>${val}</b>`}${why}${warn}</div>
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

const CMP = { at_most: "≤", at_least: "≥", less_than: "<", greater_than: ">" };
const UNIT_SUFFIX = {
  percent: "%", percentage_points: " pp", times: "×",
  times_own_median: "× own median", percent_of_entry_value: "% of entry value",
  years: " yrs", shares: " sh", ratio: "", score: "", count: "",
};

function unitVal(v, unit, of) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  const num = Number.isFinite(n)
    ? n.toLocaleString(undefined, { maximumFractionDigits: 4 }) : esc(String(v));
  let s;
  if (unit === "usd") s = "$" + num;
  else {
    const suf = UNIT_SUFFIX[unit];
    s = num + (suf !== undefined ? suf : (unit ? " " + esc(unit) : ""));
  }
  if (of !== undefined && of !== null) s += " of " + esc(of);
  return s;
}

/* One threshold block to text. Generic over the forms the profile schema
   defines — nothing here knows any particular metric. */
function condText(b) {
  if (!b || b.form === "none") return null;
  if (b.form === "abs") {
    if (b.comparator === "between")
      return `between ${unitVal(b.min, b.unit)} and ${unitVal(b.max, b.unit)}`;
    return `${CMP[b.comparator] || esc(b.comparator)} ${unitVal(b.value, b.unit, b.of)}`;
  }
  if (b.form === "delta_entry") {
    if (b.comparator === "falls_by_at_least")
      return `falls ≥ ${unitVal(b.value, "percent")} below its value at entry`;
    if (b.comparator === "falls_below_entry_value")
      return "falls below its value at entry";
    return `${esc(b.comparator)} ${unitVal(b.value, b.unit)} versus entry`;
  }
  if (b.form === "delta_median") {
    let s = `${CMP[b.comparator] || esc(b.comparator)} ${unitVal(b.value, b.unit)}`;
    if (b.basis && b.unit !== "times_own_median")
      s += ` (versus ${esc(String(b.basis).replace(/_/g, " "))})`;
    return s;
  }
  if (b.form === "compound") {
    const parts = (b.conditions || []).map(condText).filter(Boolean);
    return parts.join(b.require === "any" ? " — or — " : " — and — ");
  }
  return esc(b.form);
}

/* ------------------------------------------------- config: profiles page */
function profilesView() {
  let h = pendingBanner() + cfgErrorBox(S.profile_errors || []);
  if (!S.profile_order.length) {
    return h + `<div class="sheet"><div class="empty">
      <p>No profiles found on disk. Profiles live as .yaml files in the
      profiles folder inside your data directory.</p></div></div>`;
  }
  if (!C.selected || !S.profiles[C.selected]) C.selected = S.profile_order[0];
  h += `<div class="toolbar" style="justify-content:flex-start"><span class="seg">${
    S.profile_order.map((f) => `<button type="button" data-profile="${esc(f)}"
      aria-pressed="${f === C.selected}">${esc(S.profiles[f].name)}</button>`).join("")}</span></div>`;
  return h + profileDetail(S.profiles[C.selected]);
}

function tierRuleText(g) {
  const n = g.entries.length;
  if (g.requires === "all_green") return `all ${n} must be green`;
  if (g.requires === "at_least") {
    if (g.min_green === null || g.min_green === undefined)
      return `at least ? of ${n} — no min_green declared, cannot be evaluated`;
    return `at least ${g.min_green} of ${n} must be green`;
  }
  if (g.requires === "none") return `${n} ${n === 1 ? "entry" : "entries"} · score only, never blocks`;
  return `rollup "${g.requires ?? "not declared"}" — cannot be evaluated`;
}

function profileDetail(p) {
  let h = cfgErrorBox(p.errors || []);

  const hpe = p.holding_period_exit;
  const conf = p.sell_confirmation;
  h += `<div class="rollup">
    <h3>${esc(p.name)} <span class="dim" style="font-family:var(--mono);font-size:11px">v${esc(p.version ?? "?")}</span></h3>
    <div class="pe-desc">${prose(p.summary)}</div>
    <div class="tierline">${p.tiers.map((g) =>
      `<span class="chip s-none">${esc(g.key.toUpperCase())} · ${esc(tierRuleText(g))}</span>`).join(" ")}</div>
    <div class="pe-desc">${prose(p.rollup.rule)}</div>
    ${p.rollup.grey ? `<div class="pe-sub-block"><i>When a value is grey</i>${prose(p.rollup.grey)}</div>` : ""}
    ${hpe && hpe.form === "fixed_period" ? `<div class="pe-sub-block"><i>Position clock</i>
      <p>Sell after ${esc(hpe.value)} ${esc(hpe.unit)}, regardless of the metrics.</p>
      ${hpe.why ? `<details class="whybox"><summary>Why</summary>${prose(hpe.why)}</details>` : ""}</div>` : ""}
    ${hpe && hpe.form === "none" ? `<div class="pe-sub-block"><i>Position clock</i>
      <p>None — exits here are event-driven, not calendar-driven.</p>
      ${hpe.why ? `<details class="whybox"><summary>Why</summary>${prose(hpe.why)}</details>` : ""}</div>` : ""}
    ${conf ? `<div class="pe-sub-block"><i>Sell confirmation</i>
      <p>${esc(conf.applies_to || "Every sell threshold")} needs the breach on
      ${esc(conf.count)} ${esc(String(conf.unit || "").replace(/_/g, " "))} before it counts.</p>
      ${conf.why ? `<details class="whybox"><summary>Why</summary>${prose(conf.why)}</details>` : ""}</div>` : ""}
  </div>`;

  if (p.notice) h += `<div class="notice quiet" style="margin-top:20px">
    <h4>Before you use this profile</h4>${prose(p.notice)}</div>`;

  p.tiers.forEach((g) => {
    h += `<section class="group" style="margin-top:26px"><div class="ghead">
      <h3>${esc(g.key.toUpperCase())}</h3><span>${esc(tierRuleText(g))}</span></div>`;
    if (g.meaning) h += `<p class="hint" style="margin:8px 0 0">${oneline(g.meaning)}</p>`;
    h += `<div class="plist" style="margin-top:12px">${
      g.entries.map(profileEntry).join("") ||
      '<div class="pentry"><p class="pe-desc" style="margin:0">No entries in this tier.</p></div>'
    }</div></section>`;
  });

  /* version history — the append-only record of every change to this file */
  const hist = (p.history || []).slice().reverse();
  h += `<div class="rollup" style="margin-top:26px"><h3>Version history</h3>
    <p>Profiles are edited by hand, so changes happen outside the app. Every change is recorded
    here the moment it is seen — timestamped, with the exact lines that moved — and asks for a
    written reason. The record is append-only: versions are never edited or removed.</p>
    <ul class="histlist">${hist.map((v) => `<li><b>v${v.version}</b>
      <span>${v.reason ? esc(v.reason)
        : `<span class="neg">No reason recorded yet.</span>
           <button class="btn" data-act="explain" data-file="${esc(p.file)}" data-version="${v.version}">Write the reason</button>`}
        ${(v.changes || []).length ? `<div class="histchanges">${v.changes.map((c) => esc(c)).join("<br>")}</div>` : ""}</span>
      <time>${esc(String(v.recorded).slice(0, 10))}</time></li>`).join("")
      || "<li><span>No history recorded yet.</span></li>"}</ul></div>`;
  return h;
}

function profileEntry(e) {
  let h = `<div class="pentry">
    <div class="pe-head"><b>${esc(e.label || e.metric || "(unnamed)")}</b>
      <code>${esc(e.metric)}</code></div>`;
  if (e.errors && e.errors.length)
    h += `<div class="dlg-err" style="margin-top:10px">${e.errors.map(esc).join("<br>")}</div>`;
  if (e.description) h += `<div class="pe-desc">${prose(e.description)}</div>`;

  if (e.buy || e.sell) {
    h += '<div class="pe-cols">';
    if (e.buy) {
      h += `<div class="pe-col"><i>Buy when</i>
        <div class="pe-th">${condText(e.buy) || "—"}</div>
        ${e.buy.sustained_for ? `<div class="pe-sub">sustained for ${esc(e.buy.sustained_for.count)}
          ${esc(String(e.buy.sustained_for.unit).replace(/_/g, " "))}</div>` : ""}
        ${e.buy.why ? `<div class="pe-why">${prose(e.buy.why)}</div>` : ""}</div>`;
    }
    const s = e.sell;
    if (!s || s.form === "none") {
      /* A blank sell is a decision, not missing data. It renders as one. */
      h += `<div class="pe-col"><i>Sell when</i>
        <div class="pe-th"><span class="chip blank">Blank — no sell threshold, by choice</span></div>
        ${s && s.why ? `<div class="pe-why">${prose(s.why)}</div>` : ""}</div>`;
    } else {
      h += `<div class="pe-col"><i>Sell when</i>
        ${s.measured_on ? `<div class="pe-sub" style="margin:0 0 6px">measured on
          ${esc(s.measured_on_label || s.measured_on)} <code>${esc(s.measured_on)}</code></div>` : ""}
        <div class="pe-th">${condText(s) || "—"}</div>
        ${s.sustained_for ? `<div class="pe-sub">sustained for ${esc(s.sustained_for.count)}
          ${esc(String(s.sustained_for.unit).replace(/_/g, " "))}</div>` : ""}
        ${s.sell_confirmation ? `<div class="pe-sub">confirmation: ${esc(s.sell_confirmation.form)}${
          s.sell_confirmation.why ? " — " + oneline(s.sell_confirmation.why) : ""}</div>` : ""}
        ${s.why ? `<div class="pe-why">${prose(s.why)}</div>` : ""}</div>`;
    }
    h += "</div>";
  }

  if (e.flag) {
    h += `<div class="pe-flag"><span class="chip s-watch">Flag</span>
      <div><b class="pe-flag-b">${condText(e.flag) || esc(e.flag.comparator || "")}</b>
      — surfaces a flag only; it never blocks anything.
      ${e.flag.why ? `<div class="pe-why">${prose(e.flag.why)}</div>` : ""}</div></div>`;
  }

  if (e.parameters && e.parameters.length) {
    h += `<div class="pe-block"><i>Parameters this profile supplies</i>${
      e.parameters.map((pm) => `<div class="pe-param">
        <code>${esc(pm.id)}</code>
        ${!pm.supplied ? '<span class="chip s-fail">Not supplied — required</span>'
          : (pm.value === null || pm.value === undefined || pm.value === ""
            ? '<span class="chip blank">Not set</span>'
            : `<b>${unitVal(pm.value, pm.unit)}</b>`)}
        ${pm.means ? `<div class="pe-why" style="flex-basis:100%">${prose(pm.means)}</div>` : ""}
      </div>`).join("")}</div>`;
  }

  if (e.not_meaningful_when && e.not_meaningful_when.length) {
    h += `<div class="pe-block"><i>Not meaningful when</i><ul class="pe-nmw">${
      e.not_meaningful_when.map((t) => `<li>${oneline(t.test)}${
        t.because ? ` <span class="dim">— ${oneline(t.because)}</span>` : ""}</li>`).join("")}</ul></div>`;
  }

  if (e.note) h += `<div class="pe-block"><i>Note</i><div class="pe-why" style="margin-top:0">${prose(e.note)}</div></div>`;
  return h + "</div>";
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
        placeholder="Search ${C.bank.entries.length} metrics…" aria-label="Search metrics">
      <span class="dim" id="bankcount" style="font-family:var(--mono);font-size:11px">${bankCountText()}</span>
    </div>
    <p class="hint" style="margin:0 0 14px">The bank defines what each value <em>is</em>.
    No thresholds appear here because none exist here — every level lives in a profile.</p>
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
    <p>No metric matches “${esc(C.search)}”. Try part of a name or an id.</p></div></div>`;
  return `<div class="plist">${list.map(bankCard).join("")}</div>`;
}

function bankCard(e) {
  const pol = e.polarity === "higher_is_better" ? "higher is better"
    : e.polarity === "lower_is_better" ? "lower is better"
    : e.polarity === "none" ? "no favourable direction" : null;
  const x = e.explanation || {};
  let h = `<div class="pentry">
    <div class="pe-head"><b>${esc(e.label || e.id)}</b><code>${esc(e.id)}</code>
      <span class="req">${esc(e.kind || "")}</span>
      ${pol ? `<span class="req">${esc(pol)}</span>` : ""}
      ${e.unit ? `<span class="req">${esc(e.unit)}</span>` : ""}</div>`;
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
        unmarked = ${esc(e.response.unmarked)}</div>` : ""}</div>`;
  }
  if (e.parameters && e.parameters.length) {
    h += `<div class="pe-block"><i>Declared parameters — supplied by a profile, never set here</i>${
      e.parameters.map((p) => `<div class="pe-param"><code>${esc(p.id)}</code>
        ${p.unit ? `<span class="dim">${esc(p.unit)}</span>` : ""}
        ${p.means ? `<div class="pe-why" style="flex-basis:100%">${prose(p.means)}</div>` : ""}</div>`).join("")}</div>`;
  }
  if (e.not_meaningful_when && e.not_meaningful_when.length) {
    h += `<div class="pe-block"><i>Not meaningful when</i><ul class="pe-nmw">${
      e.not_meaningful_when.map((t) => `<li>${oneline(t.test)}${
        t.because ? ` <span class="dim">— ${oneline(t.because)}</span>` : ""}</li>`).join("")}</ul></div>`;
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
  let mig = "";
  const m = S.migration;
  if (m) {
    mig = `<div class="panel"><h3>Migration record</h3><div class="sub">Old metric set → the bank</div>
      <p class="hint" style="margin-top:0">On ${esc(String(m.migrated).slice(0, 10))} the journal's values were
      migrated to the metric bank. The original file was backed up first
      (<code>${esc(m.backup || "—")}</code>)${m.rules_archived ? `, and the retired ruleset history was archived as
      <code>${esc(m.rules_archived)}</code>` : ""}. Entry snapshots were not touched — they are recorded history.</p>
      ${(m.renamed || []).length ? `<div class="fals"><em>Renamed — same measure, bank id</em></div>
        <ul class="pe-nmw">${m.renamed.map((r) => `<li><code>${esc(r.from)}</code> → <code>${esc(r.to)}</code>
          (${r.values} values)${r.note ? ` <span class="dim">— ${esc(r.note)}</span>` : ""}</li>`).join("")}</ul>` : ""}
      ${(m.preserved || []).length ? `<div class="fals"><em>No bank equivalent — preserved, not scored</em></div>
        <ul class="pe-nmw">${m.preserved.map((p) => `<li><b>${esc(p.label)}</b> (${p.count} values)
          <span class="dim">— ${esc(p.why)}</span></li>`).join("")}</ul>` : ""}
    </div>`;
  }
  const sec = S.data_security || {};
  const storage = sec.storage || {};
  const keyStatus = sec.key_configured
    ? `A key is configured — stored in ${esc(storage.where || "the OS credential store")}. It is never shown again, never exported, and never written to settings.`
    : "No key is stored. Filing metrics still compute; price-dependent entries say why they can't.";
  const unencryptedNote = storage.unencrypted
    ? `<p class="hint"><b>This platform offers no credential vault</b>, so the key is stored <b>unencrypted</b> at
       <code>${esc(storage.where)}</code> with owner-only file permissions. That is an honest fallback, not protection
       against someone using this account.</p>` : "";
  const rotateNotice = sec.rotate_notice
    ? `<div class="notice"><h4>Rotate this key</h4><p>It previously sat in plain text inside settings — and inside any
       export made while it did. It has been moved to ${esc(storage.where || "the credential store")}, but copies that
       already left this machine can't be recalled. Generate a new key at tiingo.com/account/api/token and save it
       here; saving a new key clears this notice.</p></div>` : "";
  const secProblem = sec.problem
    ? `<div class="notice"><h4>Credential store problem</h4><p>${esc(sec.problem)}</p></div>` : "";
  return `<div class="cards">
    <div class="panel"><h3>Data sources</h3><div class="sub">SEC EDGAR filings · Tiingo prices</div>
      <p class="hint" style="margin-top:0">Filings come straight from SEC EDGAR — free, no key, but the SEC
      requires every automated tool to identify itself with a name and a monitored email, and blocks the
      anonymous ones. Prices come from Tiingo under your own free API key (tiingo.com). Fetching happens only
      when you press Fetch data, and hand-entered values are never overwritten by anything fetched.</p>
      ${secProblem}${rotateNotice}
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

    <div class="panel"><h3>Back up</h3><div class="sub">Export to a folder you control</div>
      <p class="hint" style="margin-top:0">Writes one timestamped file containing your positions, notes,
      profiles and their version history. Put it wherever you keep backups. Nothing is uploaded anywhere.</p>
      <div class="toolbar" style="justify-content:flex-start;margin-top:16px">
        <button class="btn primary" data-act="export">Export</button>
        <button class="btn" data-act="import">Import</button></div></div>

    <div class="panel"><h3>Where your data lives</h3><div class="sub">Outside the project folder</div>
      <p class="hint" style="margin-top:0"><code>${esc(S.data_dir)}</code></p>
      <p class="hint">Deliberately not inside the repository. Cloning or pushing the code can never carry your
      positions, notes or ideas with it. Only an empty template ships with the app.</p>
      <p class="hint">Set the <code>LEDGER_DATA</code> environment variable to move it, for instance onto a synced drive.</p></div>

    <div class="panel"><h3>Sample data</h3><div class="sub">Invented companies and figures</div>
      <p class="hint" style="margin-top:0">Twelve fictional securities covering the cases worth seeing: an
      expired position clock, a breach awaiting confirmation, purchases recorded against and without the
      signal, a panic sell that kept rising, and candidates the four profiles disagree about.</p>
      <div class="toolbar" style="justify-content:flex-start;margin-top:16px">
        <button class="btn" data-act="sample">Load sample data</button>
        <button class="btn danger" data-act="clear">Clear everything</button></div></div>
    ${mig}
  </div>`;
}

/* ---------------------------------------------------------------- render */
function render() {
  if (!S) return;
  renderMast(); renderTabs();
  const v = $("view");
  if (openTicker) {
    const s = find(openTicker);
    if (!s) { openTicker = null; return render(); }
    v.innerHTML = detailView(s);
    if (s.ev) paintEV(s.ticker);
  } else if (tab === "profiles") v.innerHTML = profilesView();
  else if (tab === "metrics") v.innerHTML = metricsView();
  else if (tab === "data") v.innerHTML = dataView();
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
const field = (name, label, value, help, type = "text") =>
  `<div class="field"><label for="f_${name}">${esc(label)}</label>
   <input id="f_${name}" name="${name}" type="${type}" value="${esc(value ?? "")}">
   ${help ? `<div class="help">${esc(help)}</div>` : ""}</div>`;
const area = (name, label, value, help) =>
  `<div class="field"><label for="f_${name}">${esc(label)}</label>
   <textarea id="f_${name}" name="${name}">${esc(value ?? "")}</textarea>
   ${help ? `<div class="help">${esc(help)}</div>` : ""}</div>`;

function dlgAdd() {
  dialog({
    title: "Add a security", blurb: "It starts in Ideas. Enter metrics next, then the profile will score it.",
    body: field("ticker", "Ticker", "") + field("name", "Company name", ""),
    confirm: "Add",
    onConfirm: async (d) => {
      const r = await api("add_security", d.ticker, d.name);
      if (!r) return " ";
      tab = "ideas"; openTicker = r.ticker;
    },
  });
}

function dlgMetrics(s) {
  const priceHelp = (s._price && s._price.source === "fetched")
    ? `Blank uses the fetched close (${money(s._price.value)}, ${s._price.date}). A value typed here overrides it.`
    : "Leave blank if you don't have it.";
  let body = field("price", "Price", s.price ?? "", priceHelp, "number");
  S.input_metrics.forEach((m) => {
    const users = m.used_by.length ? "Used by " + m.used_by.join(" · ")
      : "No profile currently uses this — kept because a value was recorded";
    const comp = (s._computed || {})[m.id];
    let compNote = "";
    if (comp && comp.status === "computed") {
      compNote = `<div class="u">Computed from filings: <b>${fmtBank(comp.value, m.format)}</b> — a value typed here overrides it; blank uses it.</div>`;
    } else if (comp && comp.status === "absent" && comp.reason) {
      compNote = `<div class="u">Not computed — ${esc(comp.reason)}</div>`;
    }
    body += `<div class="metric-input"><div>${esc(m.label)}
      <div class="u">${esc(m.unit || "")} · ${esc(users)}</div>${compNote}</div>
      <input name="m_${m.id}" type="number" step="any" value="${s.metrics[m.id] ?? ""}"></div>`;
  });
  dialog({
    title: `Metrics · ${s.ticker}`,
    blurb: "Only what your profiles use is listed. Hand-entered values always beat fetched ones, visibly. Leave a field blank to use the computed value, or to show grey where none computes — a zero would read as a confident failure.",
    body, confirm: "Save",
    onConfirm: async (d) => {
      const metrics = {};
      Object.keys(d).forEach((k) => { if (k.startsWith("m_")) metrics[k.slice(2)] = d[k]; });
      const r = await api("save_metrics", s.ticker, metrics, d.price);
      if (!r) return " ";
    },
  });
}

function dlgFalsifier(s) {
  dialog({
    title: `Falsifier · ${s.ticker}`,
    blurb: "What would have to happen for you to be wrong? Write it now, while you are calm.",
    body: area("text", "What would make me wrong", s.falsifier,
      "Make it testable. “Margins fall below 30% for two quarters” beats “the story changes”."),
    confirm: "Save",
    onConfirm: async (d) => { if (!(await api("save_falsifier", s.ticker, d.text))) return " "; },
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

async function dlgBuy(s) {
  const p = await api("preview_purchase", s.ticker, lens);
  if (!p) return;
  const grey = p.verdict === "cant_say", red = p.verdict === "no_buy";
  const bad = red || grey;
  const causeLabels = (p.causes || [])
    .flatMap((c) => c.metrics.map(labelOf)).join(", ");
  const warn = red
    ? `<div class="dlg-err">${esc(p.profile_name)} says <strong>No buy</strong>. ${esc(causeLabels)} failed.
       Nothing here stops you. The purchase and this reason both go into the journal, so that in a year you can
       see what you ignored and what it cost or earned you.</div>`
    : grey
    ? `<div class="dlg-err">${esc(p.profile_name)} can't call this — ${esc(causeLabels)} could not be evaluated.
       Grey is not a pass. Buying without a signal is allowed and gets logged with your reason, exactly like
       buying against one.</div>` : "";
  dialog({
    title: `Record a purchase · ${s.ticker}`,
    blurb: `Recorded under ${p.profile_name} v${p.profile_version} — the lens you are looking through. This records what you already did; the tool cannot place trades.`,
    body: warn + `<div class="grid2">${field("shares", "Shares", "", "", "number")}${field("cost", "Cost per share", "", "", "number")}</div>`
      + field("opened", "Date", new Date().toISOString().slice(0, 10), "", "date")
      + (bad ? area("override_reason", red ? "Why are you buying anyway?" : "Why are you buying without a signal?", "",
        "Required. One sentence. You will read this again later.") : ""),
    confirm: bad ? "Record anyway" : "Record purchase", danger: bad,
    onConfirm: async (d) => {
      if (!d.shares || !d.cost) return "Shares and cost per share are required.";
      if (bad && !(d.override_reason || "").trim()) return "A reason is required when the signal doesn't say buy.";
      const r = await api("open_position", s.ticker, d.shares, d.cost, d.opened, d.override_reason || "", lens, p.verdict);
      if (!r) return " ";
      /* The verdict is re-evaluated at commit; if it moved while the dialog
         was open (a fetch completed, a profile changed), the record differs
         from what the user was shown — say so, loudly. */
      if (r.verdict_changed) {
        toast(`The verdict changed to ${r.verdict === "no_buy" ? "No buy" : r.verdict === "cant_say" ? "Can't say" : "Buy"} between preview and commit (data or profiles moved). The purchase is recorded under the new verdict${r.override ? " as an override — add a note with your reasoning" : ""}.`, r.verdict !== "buy");
      }
      tab = "holdings";
    },
  });
}

function dlgSell(s) {
  const opts = S.exit_reasons.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join("");
  /* The exit price enters an append-only record. A stale fetched close must
     never slide in as a silent default. */
  const p = s._price || {};
  const fetchedAge = p.source === "fetched" && p.date
    ? Math.round((Date.now() - new Date(p.date).getTime()) / 86400000) : null;
  const stale = fetchedAge !== null && fetchedAge > 7;
  const prefill = p.source === "fetched" ? (stale ? "" : p.value) : (px(s) ?? "");
  const priceHelp = p.source === "fetched"
    ? (stale
      ? `Left blank on purpose: the newest fetched close is ${fetchedAge} days old (${p.date}). Enter the price you actually sold at.`
      : `Prefilled from the fetched close of ${p.date} — replace it with the price you actually sold at.`)
    : "The price you actually sold at.";
  dialog({
    title: `Close position · ${s.ticker}`,
    blurb: "It stays in the journal and keeps being priced, so you can see what happened after you sold.",
    body: `<div class="field"><label for="f_reason">Why are you selling?</label>
        <select id="f_reason" name="reason">${opts}</select>
        <div class="help">Answer honestly. The Previous holdings tab groups outcomes by this, and it is the only way to find out whether your sell rules work.</div></div>`
      + field("price", "Exit price per share", prefill, priceHelp, "number")
      + field("exited", "Date", new Date().toISOString().slice(0, 10), "", "date"),
    confirm: "Close position", danger: true,
    onConfirm: async (d) => {
      if (!d.price) return "An exit price is required.";
      const r = await api("close_position", s.ticker, d.reason, d.price, d.exited, lens);
      if (!r) return " ";
      tab = "previous";
      if (r.rule_triggered === false)
        toast(`Recorded. ${r.signal} under ${r.profile_name} — no rule triggered this exit. That is now on the record.`);
      if (r.rule_triggered === null)
        toast("Recorded. This position had no governing profile, which is itself on the record.");
    },
  });
}

function dlgEV(s, methodOverride) {
  const cur = methodOverride || (s.ev ? s.ev.method : S.settings.default_ev_method);
  const meth = S.ev_methods[cur];
  const opts = Object.keys(S.ev_methods).map((k) =>
    `<option value="${k}" ${k === cur ? "selected" : ""}>${esc(S.ev_methods[k].label)}</option>`).join("");
  const inputs = meth.inputs.map(([key, label, help]) => {
    let v = s.ev && s.ev.method === cur ? s.ev.inputs[key] : "";
    if (v === "" || v === undefined) {
      if (key === "price") v = s.price ?? "";
      if (key === "discount_rate") v = S.settings.discount_rate;
      if (key === "terminal_growth") v = S.settings.terminal_growth;
      if (key === "margin_of_safety") v = S.settings.margin_of_safety;
    }
    return field(key, label, v, help, "number");
  }).join("");
  dialog({
    title: `Expected value · ${s.ticker}`,
    blurb: meth.blurb + "  ·  " + meth.who,
    body: `<div class="field"><label for="f_method">Method</label>
        <select id="f_method" name="method">${opts}</select>
        <div class="help">Changing the method reopens this with its own assumptions.</div></div>${inputs}`,
    confirm: "Compute",
    onConfirm: async (d) => {
      if (d.method !== cur) { $("dlg").close(); dlgEV(find(s.ticker), d.method); return true; }
      const inputsObj = {};
      meth.inputs.forEach(([k]) => { inputsObj[k] = d[k]; });
      const r = await api("compute_ev", s.ticker, d.method, inputsObj);
      if (!r) return " ";
      toast(`${r.result.label}: ${r.result.display}`);
    },
  });
}

function dlgExplain(file, version) {
  const pend = (S.pending_changes || []).find((c) => c.file === file && c.version === Number(version));
  const changes = pend ? pend.changes : [];
  dialog({
    title: `${file} — v${version}`,
    blurb: "This change is already on the record. Write down why it was made — in two years this line will be the most useful thing in the file.",
    body: (changes.length ? `<div class="dlg-err" style="background:var(--card-2);border-left-color:var(--ink);color:var(--ink-2)">
        ${changes.map(esc).join("<br>")}</div>` : "")
      + area("reason", "Why was this changed?", "",
        "For example: “Overrides on the leverage entry kept working, so widening from 2.5× to 3.0×.” Written once; it cannot be edited later."),
    confirm: "Record the reason",
    onConfirm: async (d) => {
      if (!(d.reason || "").trim()) return "A reason is required.";
      const r = await api("explain_profile_change", file, Number(version), d.reason);
      if (!r) return " ";
      toast(`Recorded the reason for ${file} v${version}.`);
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
  if (tb) { tab = tb.dataset.tab; openTicker = null; tipOpen = null; return render(); }

  const ln = t.closest("[data-lens]");
  if (ln) {
    if (ln.dataset.lens !== lens) {
      lens = ln.dataset.lens;
      S.settings.active_profile = lens;
      api("set_active_profile", lens);   /* persisted in Python; the switch itself is local */
      render();
    }
    return;
  }

  const psel = t.closest("[data-profile]");
  if (psel) { C.selected = psel.dataset.profile; return render(); }

  const act = t.closest("[data-act]");
  if (!act) {
    const row = t.closest("tbody tr");
    if (row) { openTicker = row.dataset.t; tipOpen = null; render(); window.scrollTo({ top: 0 }); }
    return;
  }

  const s = openTicker ? find(openTicker) : null;
  switch (act.dataset.act) {
    case "back": openTicker = null; tipOpen = null; return render();
    case "add": return dlgAdd();
    case "remove": {
      if (!s) return;
      /* Only ideas reach this button; the backend re-checks regardless.
         Say exactly what goes with it — an informed removal, not a shrug. */
      const lost = [];
      const vals = Object.keys(s.metrics || {}).length;
      const notes = (s.notes || []).length;
      if (vals) lost.push(`${vals} hand-entered value${vals === 1 ? "" : "s"}`);
      if (notes) lost.push(`${notes} note${notes === 1 ? "" : "s"}`);
      if ((s.falsifier || "").trim()) lost.push("its falsifier");
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
          openTicker = null;
          tab = "ideas";
          toast(`${r.removed} removed from the journal.`);
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
        body: '<p class="hint">Filing data is unaffected. Price-dependent metrics will show why they can\'t compute.</p>',
        confirm: "Remove key", danger: true,
        onConfirm: async () => {
          if (!(await api("remove_api_key"))) return " ";
          toast("Key removed.");
        },
      });
      return;
    }
    case "metrics": return dlgMetrics(s);
    case "falsifier": return dlgFalsifier(s);
    case "note": return dlgNote(s);
    case "buy": return dlgBuy(s);
    case "sell": return dlgSell(s);
    case "ev": return dlgEV(s);
    case "explain": return dlgExplain(act.dataset.file, act.dataset.version);
    case "export": {
      const r = await api("export_data");
      if (r && !r.cancelled) toast("Exported to " + r.path);
      return;
    }
    case "import": {
      const r = await api("import_data");
      if (r && !r.cancelled) {
        toast(`Imported ${r.summary.securities} securities.` + (r.summary.note ? " " + r.summary.note : ""));
        await refresh();
      }
      return;
    }
    case "sample": {
      const held = S.securities.length;
      dialog({
        title: "Load sample data",
        blurb: held
          ? `This replaces the ${held} securit${held === 1 ? "y" : "ies"} currently in the journal — snapshots, notes and exit records included.`
          : "Twelve invented companies, covering the cases worth seeing.",
        body: held ? '<p class="hint">Export first if you might want any of it back. Your profiles and their history stay.</p>'
                   : '<p class="hint">Nothing currently in the journal will be affected, because there is nothing in it.</p>',
        confirm: "Load sample", danger: held > 0,
        onConfirm: async () => {
          const r = await api("load_sample");
          if (!r) return " ";
          toast(`Loaded ${r.n} sample securities.`);
          tab = "holdings"; openTicker = null;
        },
      });
      return;
    }
    case "clear": {
      dialog({
        title: "Clear everything", blurb: "This removes every security from the journal. Your profiles and their history stay.",
        body: '<p class="hint">Export first if you might want any of it back.</p>',
        confirm: "Clear", danger: true,
        onConfirm: async () => { if (!(await api("clear_all"))) return " "; openTicker = null; },
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
  if (ev.key === "Escape" && openTicker && !$("dlg").open) { openTicker = null; render(); }
});

window.addEventListener("pywebviewready", refresh);
if (window.pywebview && window.pywebview.api) refresh();
