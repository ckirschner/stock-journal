/* The view layer knows nothing about which metrics exist. Everything it draws
   comes from the schema and the securities Python sends over. Adding a metric
   in engine/schema.py is the whole job of adding a metric. */

let S = null;                 // last state from Python
let tab = "holdings";
let openTicker = null;
let tipOpen = null;
let pending = { metrics: {}, min_optional: null };   // unsaved rule edits

const TABS = [
  ["holdings", "Current holdings"],
  ["previous", "Previous holdings"],
  ["ideas", "Ideas"],
  ["rules", "Rules"],
  ["data", "Data"],
];

/* ------------------------------------------------------------------ utils */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fmt(v, f) {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (f === "pct") return n.toFixed(1) + "%";
  if (f === "pctd") return (n >= 0 ? "+" : "") + n.toFixed(1) + "%";
  if (f === "ppt") return (n >= 0 ? "+" : "") + n.toFixed(1) + "pp";
  if (f === "x") return n.toFixed(2) + "×";
  return String(n);
}
const money = (n) => (n === null || n === undefined) ? "—" : "$" + Number(n).toFixed(2);
function pctCell(v) {
  if (v === null || v === undefined) return '<span class="dim">—</span>';
  return `<span class="${v >= 0 ? "pos" : "neg"}">${v >= 0 ? "+" : ""}${Number(v).toFixed(1)}%</span>`;
}
const allMetrics = () => S.schema.flatMap((g) => g.metrics);
const metricById = (id) => allMetrics().find((m) => m.id === id);

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
async function refresh() {
  const r = await api("get_state");
  if (r) { S = r; render(); }
}

/* --------------------------------------------------------------- evaluate */
function stateOf(metric, value, rule) {
  if (value === null || value === undefined || !rule || !rule.enabled) return "none";
  const t = Number(rule.threshold), v = Number(value);
  const band = Math.abs(t) * 0.10 || 0.5;
  if (metric.dir === "high") {
    if (v >= t) return (v - t) <= band ? "watch" : "pass";
    return "fail";
  }
  if (v <= t) return (t - v) <= band ? "watch" : "pass";
  return "fail";
}
const inBucket = (b) => S.securities.filter((s) => s.bucket === b);
const find = (t) => S.securities.find((s) => s.ticker === t);

/* ---------------------------------------------------------------- chrome */
function renderMast() {
  const h = inBucket("holdings");
  const mv = h.reduce((a, s) => a + (s.price || 0) * (s.position ? s.position.shares : 0), 0);
  const cb = h.reduce((a, s) => a + (s.position ? s.position.cost_basis * s.position.shares : 0), 0);
  const flagged = h.filter((s) => s._now.tone === "fail").length;
  $("maststats").innerHTML = !h.length ? "" :
    `<div><i>Market value</i><b>$${mv.toLocaleString(undefined, { maximumFractionDigits: 0 })}</b></div>
     <div><i>Unrealised</i><b class="${mv >= cb ? "pos" : "neg"}">${cb ? (mv >= cb ? "+" : "") + ((mv / cb - 1) * 100).toFixed(1) + "%" : "—"}</b></div>
     <div><i>Positions</i><b>${h.length}</b></div>
     <div><i>Flagged</i><b class="${flagged ? "neg" : ""}">${flagged}</b></div>`;
  $("subtitle").textContent = `Portfolio journal · ruleset v${S.rules.version}`;
  $("foot").innerHTML = `This tool never places a trade and holds no broker credentials. `
    + `It checks what you tell it against rules you wrote.<br>Data stored at ${esc(S.data_dir)}, never inside the project folder.`;
}
function renderTabs() {
  $("tabs").innerHTML = TABS.map(([id, label]) => {
    const n = (id === "rules" || id === "data") ? "" : `<em>${inBucket(id).length}</em>`;
    return `<button class="tab" role="tab" aria-selected="${tab === id}" data-tab="${id}">${label}${n}</button>`;
  }).join("");
}

/* ----------------------------------------------------------------- lists */
function scorePill(e) {
  if (e.knockouts.length) return '<span class="score s-fail">KO</span>';
  const cls = e.required_fails.length ? "s-fail"
    : (e.tone === "pass" ? "s-pass" : (e.tone === "none" ? "s-none" : "s-watch"));
  return `<span class="score ${cls}">${e.optional_pass}/${e.optional_total}</span>`;
}

function listView() {
  const rows = inBucket(tab);
  const addBtn = tab === "ideas"
    ? '<button class="btn primary" data-act="add">Add a candidate</button>'
    : (tab === "holdings" ? '<button class="btn primary" data-act="add">Add a security</button>' : "");
  let html = `<div class="toolbar">${addBtn}</div>`;

  if (!rows.length) {
    const msg = {
      holdings: "No open positions. Add a security, enter its metrics, then record a purchase.",
      previous: "Nothing closed yet. When you exit a position it stays here so you can see what happened next.",
      ideas: "No candidates yet. Add one and the rules will tell you where it stands.",
    }[tab];
    return html + `<div class="sheet"><div class="empty"><p>${msg}</p>
      ${tab !== "previous" ? '<button class="btn primary" data-act="add">Add a security</button>' : ""}</div></div>`;
  }

  let head, body;
  if (tab === "holdings") {
    head = '<th class="l">Position</th><th>Price</th><th>Cost</th><th>Since buy</th><th class="hide-sm">Score</th><th>Verdict</th>';
    body = rows.map((s) => `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
      ${s.override ? '<span class="flagdot" title="Bought against signal"></span>' : ""}
      <div class="coname">${esc(s.name)}</div></td>
      <td>${money(s.price)}</td><td class="dim">${money(s.position && s.position.cost_basis)}</td>
      <td>${pctCell(s._realised)}</td>
      <td class="hide-sm">${scorePill(s._now)}</td>
      <td><span class="stamp v-${s._now.tone}">${esc(s._now.verdict)}</span></td></tr>`).join("");
  } else if (tab === "previous") {
    head = '<th class="l">Position</th><th>Return held</th><th>Since exit</th><th class="hide-sm">Exit reason</th><th class="hide-sm">Score</th><th>Today</th>';
    body = rows.map((s) => {
      const ex = s.exit || {};
      const regret = !ex.rule_triggered && s._since_exit > 15;
      return `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
        <div class="coname">${esc(s.name)}</div></td>
        <td>${pctCell(ex.return_pct)}</td><td>${pctCell(s._since_exit)}</td>
        <td class="hide-sm"><span class="chip ${regret ? "s-fail" : "s-none"}">${esc(ex.reason || "")}</span></td>
        <td class="hide-sm">${scorePill(s._now)}</td>
        <td><span class="stamp v-${s._now.tone}">${esc(s._now.verdict)}</span></td></tr>`;
    }).join("");
  } else {
    head = '<th class="l">Candidate</th><th>Price</th><th class="hide-sm">Added</th><th class="hide-sm">Score</th><th>Verdict</th>';
    body = rows.map((s) => `<tr data-t="${s.ticker}"><td class="l"><span class="tick">${esc(s.ticker)}</span>
      <div class="coname">${esc(s.name)}</div></td>
      <td>${money(s.price)}</td><td class="dim hide-sm">${esc(s.added)}</td>
      <td class="hide-sm">${scorePill(s._now)}</td>
      <td><span class="stamp v-${s._now.tone}">${esc(s._now.verdict)}</span></td></tr>`).join("");
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
      const b = o.per_rule[id], m = metricById(id);
      return line((m ? m.label : id), `${b.wins}/${b.n} · ${b.avg >= 0 ? "+" : ""}${b.avg}%`);
    }).join("");
  }

  const exRows = Object.keys(x).map((reason) => {
    const b = x[reason];
    return line(reason + ` (${b.n})`,
      `held ${b.avg_held === null ? "—" : (b.avg_held >= 0 ? "+" : "") + b.avg_held + "%"}`
      + ` · after ${b.avg_after === null ? "—" : (b.avg_after >= 0 ? "+" : "") + b.avg_after + "%"}`);
  }).join("") || '<p class="hint">No closed positions yet.</p>';

  return `<div class="cards">
    <div class="panel"><h3>Overrides</h3><div class="sub">Bought against the signal</div>${summ(o.override)}</div>
    <div class="panel"><h3>Compliant</h3><div class="sub">Bought with the signal</div>${summ(o.compliant)}</div>
    <div class="panel"><h3>By exit reason</h3><div class="sub">Return while held · return since</div>${exRows}
      <p class="hint">If one reason keeps showing a strong return <em>after</em> you sold, that is the sell rule to look at.</p></div>
    ${perRule ? `<div class="panel"><h3>Rules you overrode</h3><div class="sub">Wins / times · average</div>${perRule}
      <p class="hint">If overriding a rule keeps working, the rule is miscalibrated, not you. Widen it on the Rules tab.</p></div>` : ""}
  </div>`;
}

/* ---------------------------------------------------------------- detail */
function detailView(s) {
  const e = s._now, isHold = s.bucket === "holdings", isPrev = s.bucket === "previous";
  const snap = s.entry_snapshot;
  const cmp = !!snap;

  let h = `<button class="backlink" data-act="back">← ${TABS.find((t) => t[0] === tab)[1]}</button>`;

  h += `<div class="dhead"><div class="dtitle"><h1>${esc(s.ticker)}</h1><p>${esc(s.name)}</p>
    <div class="meta">${isHold ? "Opened " + esc(s.position.opened)
      : isPrev ? "Closed " + esc(s.exit.date) + " · " + esc(s.exit.reason)
      : "Added " + esc(s.added)} · scored against ruleset v${e.ruleset_version}</div></div>
    <div style="text-align:right"><span class="stamp big v-${e.tone}">${esc(e.verdict)}</span>
    <div class="stamp-note">${e.knockouts.length ? "Knockout failed"
      : e.required_fails.length ? "Required rule failed"
      : e.tone === "none" ? e.missing + " metrics missing"
      : e.optional_pass + " of " + e.optional_total + " optional passed"}</div></div></div>`;

  /* actions */
  h += '<div class="toolbar" style="margin-top:16px">';
  h += '<button class="btn" data-act="metrics">Edit metrics</button>';
  h += '<button class="btn" data-act="ev">Expected value</button>';
  h += '<button class="btn" data-act="falsifier">Falsifier</button>';
  h += '<button class="btn" data-act="note">Add note</button>';
  if (!isHold && !isPrev) h += '<button class="btn primary" data-act="buy">Record a purchase</button>';
  if (isHold) h += '<button class="btn danger" data-act="sell">Close position</button>';
  h += "</div>";

  /* facts */
  let facts = [];
  if (isHold) {
    facts = [["Price", money(s.price)], ["Cost basis", money(s.position.cost_basis)],
      ["Shares", s.position.shares], ["Since buy", s._realised === null ? "—" : (s._realised >= 0 ? "+" : "") + s._realised + "%"],
      ["Value", s.price ? "$" + (s.price * s.position.shares).toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"]];
  } else if (isPrev) {
    facts = [["Exit price", money(s.exit.price)], ["Return held", (s.exit.return_pct >= 0 ? "+" : "") + s.exit.return_pct + "%"],
      ["Since exit", s._since_exit === null ? "—" : (s._since_exit >= 0 ? "+" : "") + s._since_exit + "%"],
      ["Reason", s.exit.reason]];
  } else {
    facts = [["Price", money(s.price)], ["Added", s.added],
      ["Metrics", Object.keys(s.metrics || {}).length + " of " + allMetrics().length]];
  }
  h += '<div class="facts">' + facts.map((f) =>
    `<div class="fact"><i>${esc(f[0])}</i><b>${esc(f[1])}</b></div>`).join("") + "</div>";

  /* notices */
  if (s.override) {
    const labels = s.override.failed.map((id) => (metricById(id) || {}).label || id).join(" and ");
    h += `<div class="notice"><h4>Bought against signal</h4>
      <p>On ${esc(s.override.date)} this evaluated to <strong>${esc(s.override.verdict)}</strong>. ${esc(labels)}
      failed. The purchase was recorded anyway.${s._realised !== null ? ` Position is ${s._realised >= 0 ? "up" : "down"} ${Math.abs(s._realised).toFixed(1)}% since.` : ""}</p>
      <q>${esc(s.override.reason)}</q></div>`;
  }
  if (isPrev && s.exit && !s.exit.rule_triggered) {
    h += `<div class="notice"><h4>No rule triggered this exit</h4>
      <p>The signal read <strong>${esc(s.exit.signal_at_exit)}</strong> on ${esc(s.exit.date)}.
      ${s._since_exit !== null ? `The position is ${s._since_exit >= 0 ? "up" : "down"} ${Math.abs(s._since_exit).toFixed(1)}% since it was closed.` : ""}</p></div>`;
  }
  if (isHold && !(s.falsifier || "").trim()) {
    h += `<div class="notice quiet"><h4>No falsifier on record</h4>
      <p>This position is open without a written answer to "what would make me wrong?".
      That is the field you will want when it drops 25% and you are deciding whether to add or exit.</p></div>`;
  }

  /* metric groups */
  S.schema.forEach((g) => {
    const present = g.metrics.filter((m) => s.metrics[m.id] !== undefined && S.rules.metrics[m.id].enabled);
    if (!present.length) return;
    h += `<section class="group"><div class="ghead"><h3>${esc(g.title)}</h3>
      <span>${cmp ? "At entry → now" : "Current"}</span></div>`;
    present.forEach((m) => {
      const rule = S.rules.metrics[m.id];
      const vN = s.metrics[m.id];
      const vE = cmp ? snap.metrics[m.id] : undefined;
      const sN = stateOf(m, vN, rule);
      const badge = rule.mode === "knockout" ? '<span class="req hard">Knockout</span>'
        : rule.mode === "required" ? '<span class="req">Required</span>' : "";
      const d = (vE !== undefined && vE !== null) ? (vN - vE) : null;
      h += `<div class="mrow"><div class="mname">${esc(m.label)}${badge}
        <button class="tip" data-tip="${m.id}" aria-expanded="${tipOpen === m.id}" aria-label="What is ${esc(m.label)}?">?</button></div>
        ${cmp ? `<div class="mval entry">${fmt(vE, m.fmt)}<span class="delta dim">at entry</span></div>` : '<div class="mval entry"></div>'}
        <div class="mval">${fmt(vN, m.fmt)}${d !== null
          ? `<span class="delta ${(m.dir === "high" ? d >= 0 : d <= 0) ? "pos" : "neg"}">${d >= 0 ? "+" : ""}${d.toFixed(1)}</span>` : ""}</div>
        <div class="mthresh">${m.dir === "high" ? "≥ " : "≤ "}${fmt(rule.threshold, m.fmt)}</div>
        <div class="mstate"><span class="chip s-${sN}">${sN}</span></div>`;
      if (tipOpen === m.id) h += `<div class="tipbox">${esc(m.tip)}<span class="who">Used by ${esc(m.who)}</span></div>`;
      h += "</div>";
    });
    h += "</section>";
  });

  const hidden = allMetrics().filter((m) => s.metrics[m.id] === undefined).length;
  if (hidden) h += `<p class="foot" style="margin:-12px 0 24px;border:0;padding:0">${hidden} metrics have no data for ${esc(s.ticker)} and are not shown.</p>`;

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
  if (snap) h += `<p class="locked">Entry snapshot frozen ${esc(String(snap.frozen).slice(0, 10))} against ruleset v${snap.ruleset_version}. It is never recomputed, so restatements and rule changes cannot rewrite it.</p>`;
  h += "</div></div>";
  return h;
}

/* ----------------------------------------------------------------- rules */
function rulesView() {
  const merged = (id) => Object.assign({}, S.rules.metrics[id], pending.metrics[id] || {});
  const minOpt = pending.min_optional === null ? S.rules.min_optional : pending.min_optional;

  let h = `<div class="rulegrid"><div class="rr h"><div>Metric</div><div>Threshold</div>
    <div class="hide-sm2">Weight</div><div class="hide-sm2">Group</div></div>`;
  S.schema.forEach((g) => g.metrics.forEach((m) => {
    const r = merged(m.id);
    h += `<div class="rr"><div>${esc(m.label)}
      <button class="tip" data-tip="${m.id}" aria-expanded="${tipOpen === m.id}" aria-label="What is ${esc(m.label)}?">?</button>
      ${tipOpen === m.id ? `<div class="tipbox" style="margin-top:9px">${esc(m.tip)}<span class="who">Used by ${esc(m.who)}</span></div>` : ""}</div>
      <div class="mono">${m.dir === "high" ? "≥" : "≤"}
        <input class="thin" type="number" step="0.1" value="${r.threshold}" data-thresh="${m.id}"></div>
      <div class="hide-sm2"><span class="seg">${["knockout", "required", "optional"].map((md) =>
        `<button type="button" class="${md === "knockout" ? "k" : ""}" data-mode="${md}" data-metric="${m.id}"
          aria-pressed="${r.mode === md}">${md.slice(0, 3)}</button>`).join("")}</span></div>
      <div class="mono hide-sm2" style="color:var(--ink-3)">${esc(g.title)}</div></div>`;
  }));
  h += "</div>";

  const optCount = allMetrics().filter((m) => merged(m.id).mode === "optional" && merged(m.id).enabled).length;
  h += `<div class="rollup"><h3>How a security rolls up</h3>
    <p>Any knockout failure marks the security red regardless of everything else. Any required failure does the same.
    Only once both are clear does the optional score decide between green and amber.</p>
    <p>Optional metrics that must pass: <span class="stepper">
      <button type="button" data-act="dec">−</button><span>${minOpt}</span><button type="button" data-act="inc">+</button>
    </span> of ${optCount} enabled.</p>`;

  const changed = Object.keys(pending.metrics).length || pending.min_optional !== null;
  if (changed) {
    h += `<div class="pending"><h4>Unsaved changes</h4>
      <ul>${describePending().map((l) => `<li>${esc(l)}</li>`).join("")}</ul>
      <button class="btn primary" data-act="amend">Save as ruleset v${S.rules.version + 1}</button>
      <button class="btn" data-act="discard">Discard</button></div>`;
  } else {
    h += `<p class="hint">Changing anything here creates a new ruleset version with a written reason.
      Open positions stay bound to the version they were opened under, so your entry snapshots never move.</p>`;
  }
  h += "</div>";

  h += `<div class="rollup"><h3>Version history</h3><ul class="histlist">${S.rule_history.map((v) =>
    `<li><b>v${v.version}</b><span>${esc(v.reason)}</span><time>${esc(String(v.created).slice(0, 10))}</time></li>`).join("")}</ul></div>`;
  return h;
}

function describePending() {
  const out = [];
  if (pending.min_optional !== null && pending.min_optional !== S.rules.min_optional)
    out.push(`Optional metrics required: ${S.rules.min_optional} → ${pending.min_optional}`);
  Object.keys(pending.metrics).forEach((id) => {
    const m = metricById(id), cur = S.rules.metrics[id], p = pending.metrics[id];
    if (p.mode && p.mode !== cur.mode) out.push(`${m.label}: ${cur.mode} → ${p.mode}`);
    if (p.threshold !== undefined && Number(p.threshold) !== Number(cur.threshold))
      out.push(`${m.label}: threshold ${cur.threshold} → ${p.threshold}`);
  });
  return out;
}

/* ------------------------------------------------------------------ data */
function dataView() {
  return `<div class="cards">
    <div class="panel"><h3>Back up</h3><div class="sub">Export to a folder you control</div>
      <p class="hint" style="margin-top:0">Writes one timestamped file containing your positions, rules and notes.
      Put it wherever you keep backups. Nothing is uploaded anywhere.</p>
      <div class="toolbar" style="justify-content:flex-start;margin-top:16px">
        <button class="btn primary" data-act="export">Export</button>
        <button class="btn" data-act="import">Import</button></div></div>

    <div class="panel"><h3>Where your data lives</h3><div class="sub">Outside the project folder</div>
      <p class="hint" style="margin-top:0"><code>${esc(S.data_dir)}</code></p>
      <p class="hint">Deliberately not inside the repository. Cloning or pushing the code can never carry your
      positions, notes or ideas with it. Only an empty template ships with the app.</p>
      <p class="hint">Set the <code>LEDGER_DATA</code> environment variable to move it, for instance onto a synced drive.</p></div>

    <div class="panel"><h3>Sample data</h3><div class="sub">Invented companies and figures</div>
      <p class="hint" style="margin-top:0">Twelve fictional securities covering the cases worth seeing: an override,
      a panic sell that kept rising, a thesis decaying across the entry snapshot, and two with missing data.</p>
      <div class="toolbar" style="justify-content:flex-start;margin-top:16px">
        <button class="btn" data-act="sample">Load sample data</button>
        <button class="btn danger" data-act="clear">Clear everything</button></div></div>
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
  } else if (tab === "rules") v.innerHTML = rulesView();
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
    title: "Add a security", blurb: "It starts in Ideas. Enter metrics next, then the rules will score it.",
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
  let body = field("price", "Price", s.price ?? "", "Leave blank if you don't have it.", "number");
  S.schema.forEach((g) => {
    body += `<div class="dlg-group">${esc(g.title)}</div>`;
    g.metrics.forEach((m) => {
      body += `<div class="metric-input"><div>${esc(m.label)}<div class="u">${m.dir === "high" ? "≥" : "≤"} ${fmt(S.rules.metrics[m.id].threshold, m.fmt)}</div></div>
        <input name="m_${m.id}" type="number" step="any" value="${s.metrics[m.id] ?? ""}"></div>`;
    });
  });
  dialog({
    title: `Metrics · ${s.ticker}`,
    blurb: "Leave a field blank if you don't have the number. Blank hides the metric and shows grey. A zero would read as a confident failure.",
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
  const p = await api("preview_purchase", s.ticker);
  if (!p) return;
  const bad = p.tone === "fail";
  const warn = bad
    ? `<div class="dlg-err">The rules say <strong>${esc(p.verdict)}</strong>. ${esc(p.failures.join(", "))} failed.
       Nothing here stops you. The purchase and this reason both go into the journal, so that in a year you can
       see what you ignored and what it cost or earned you.</div>` : "";
  dialog({
    title: `Record a purchase · ${s.ticker}`,
    blurb: "This records what you already did. The tool cannot place trades.",
    body: warn + `<div class="grid2">${field("shares", "Shares", "", "", "number")}${field("cost", "Cost per share", "", "", "number")}</div>`
      + field("opened", "Date", new Date().toISOString().slice(0, 10), "", "date")
      + (bad ? area("override_reason", "Why are you buying anyway?", "",
        "Required. One sentence. You will read this again later.") : ""),
    confirm: bad ? "Record anyway" : "Record purchase", danger: bad,
    onConfirm: async (d) => {
      if (!d.shares || !d.cost) return "Shares and cost per share are required.";
      if (bad && !(d.override_reason || "").trim()) return "A reason is required when buying against the signal.";
      const r = await api("open_position", s.ticker, d.shares, d.cost, d.opened, d.override_reason || "");
      if (!r) return " ";
      tab = "holdings";
    },
  });
}

function dlgSell(s) {
  const opts = S.exit_reasons.map((r) => `<option value="${esc(r)}">${esc(r)}</option>`).join("");
  dialog({
    title: `Close position · ${s.ticker}`,
    blurb: "It stays in the journal and keeps being priced, so you can see what happened after you sold.",
    body: `<div class="field"><label for="f_reason">Why are you selling?</label>
        <select id="f_reason" name="reason">${opts}</select>
        <div class="help">Answer honestly. The Previous holdings tab groups outcomes by this, and it is the only way to find out whether your sell rules work.</div></div>`
      + field("price", "Exit price per share", s.price ?? "", "", "number")
      + field("exited", "Date", new Date().toISOString().slice(0, 10), "", "date"),
    confirm: "Close position", danger: true,
    onConfirm: async (d) => {
      if (!d.price) return "An exit price is required.";
      const r = await api("close_position", s.ticker, d.reason, d.price, d.exited);
      if (!r) return " ";
      tab = "previous";
      if (!r.rule_triggered) toast("Recorded. No rule triggered this exit. That is now on the record.");
    },
  });
}

function dlgEV(s) {
  const cur = s.ev ? s.ev.method : S.settings.default_ev_method;
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
      if (d.method !== cur) { $("dlg").close(); const s2 = find(s.ticker); s2.ev = { method: d.method, inputs: {} }; dlgEV(s2); return " "; }
      const inputsObj = {};
      meth.inputs.forEach(([k]) => { inputsObj[k] = d[k]; });
      const r = await api("compute_ev", s.ticker, d.method, inputsObj);
      if (!r) return " ";
      toast(`${r.result.label}: ${r.result.display}`);
    },
  });
}

function dlgAmend() {
  dialog({
    title: `Save as ruleset v${S.rules.version + 1}`,
    blurb: "Write down why. In two years this line will be the most useful thing in the file.",
    body: `<div class="dlg-err" style="background:var(--card-2);border-left-color:var(--ink);color:var(--ink-2)">
        ${describePending().map(esc).join("<br>")}</div>`
      + area("reason", "Why are you changing this?", "",
        "For example: “Overrides on the leverage knockout kept working, so widening from 2.5x to 3.0x.”"),
    confirm: "Save version",
    onConfirm: async (d) => {
      if (!(d.reason || "").trim()) return "A reason is required.";
      const changes = { metrics: pending.metrics };
      if (pending.min_optional !== null) changes.min_optional = pending.min_optional;
      const r = await api("amend_rules", changes, d.reason);
      if (!r) return " ";
      pending = { metrics: {}, min_optional: null };
      toast(`Saved ruleset v${r.version}.`);
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

  const mode = t.closest("[data-mode]");
  if (mode) {
    const id = mode.dataset.metric;
    pending.metrics[id] = Object.assign({}, pending.metrics[id], { mode: mode.dataset.mode });
    if (pending.metrics[id].mode === S.rules.metrics[id].mode && pending.metrics[id].threshold === undefined)
      delete pending.metrics[id];
    return render();
  }

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
    case "metrics": return dlgMetrics(s);
    case "falsifier": return dlgFalsifier(s);
    case "note": return dlgNote(s);
    case "buy": return dlgBuy(s);
    case "sell": return dlgSell(s);
    case "ev": return dlgEV(s);
    case "inc": pending.min_optional = (pending.min_optional === null ? S.rules.min_optional : pending.min_optional) + 1; return render();
    case "dec": pending.min_optional = Math.max(0, (pending.min_optional === null ? S.rules.min_optional : pending.min_optional) - 1); return render();
    case "amend": return dlgAmend();
    case "discard": pending = { metrics: {}, min_optional: null }; return render();
    case "export": {
      const r = await api("export_data");
      if (r && !r.cancelled) toast("Exported to " + r.path);
      return;
    }
    case "import": {
      const r = await api("import_data");
      if (r && !r.cancelled) { toast(`Imported ${r.summary.securities} securities.`); await refresh(); }
      return;
    }
    case "sample": {
      const r = await api("load_sample");
      if (r) { toast(`Loaded ${r.n} sample securities.`); tab = "holdings"; await refresh(); }
      return;
    }
    case "clear": {
      dialog({
        title: "Clear everything", blurb: "This removes every security from the journal. Your rules stay.",
        body: '<p class="hint">Export first if you might want any of it back.</p>',
        confirm: "Clear", danger: true,
        onConfirm: async () => { if (!(await api("clear_all"))) return " "; openTicker = null; },
      });
      return;
    }
  }
});

document.addEventListener("change", (ev) => {
  const th = ev.target.closest("[data-thresh]");
  if (!th) return;
  const id = th.dataset.thresh;
  pending.metrics[id] = Object.assign({}, pending.metrics[id], { threshold: Number(th.value) });
  if (Number(th.value) === Number(S.rules.metrics[id].threshold) && pending.metrics[id].mode === undefined)
    delete pending.metrics[id];
  render();
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && openTicker && !$("dlg").open) { openTicker = null; render(); }
});

window.addEventListener("pywebviewready", refresh);
if (window.pywebview && window.pywebview.api) refresh();
