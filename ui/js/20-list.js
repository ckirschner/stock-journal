/* The mast, the tabs, and the one inventory screen.

   Holdings, watchlist and track record are filters over one list, not three
   screens — at thirty candidates plus holdings you compare across the
   boundary anyway. The order is the host's: what asks most of you first,
   from the render-type table, never from state names. */

function journalName() {
  return S.journal ? S.journal.name : "";
}

function renderMast() {
  const chip = $("journalchip");
  if (!S.journal) {
    chip.innerHTML = "";
    $("maststats").innerHTML = "";
    return;
  }
  const stratName = ((S.journal || {}).strategy || {}).name || "";
  chip.innerHTML = `<button class="journal" data-menu="journal" data-arg="{}">
    <b>${esc(journalName())}</b>${stratName ? " · " + esc(stratName) : ""} ▾</button>`;

  const folio = S.portfolio || {};
  const av = folio.account_value || { status: "absent", reason: "the account has not been read" };
  const cash = folio.cash || { status: "absent", reason: "no cash record" };
  const holdings = inBucket("holdings");
  /* Verdict-tier and evaluation-tier are different facts and get different
     cells: "something to say" counts only position-tier attention among
     holdings; a holding the tool cannot see gets its own cell in the
     unknown colour, because blindness must never hide inside a to-do count. */
  const saying = holdings.filter((s) => needsAttention(s._decision)
    && (s._decision || {}).tier === "position").length;
  const blind = holdings.filter((s) => renderOf(s._decision) === "unknown").length;
  const owed = holdings.filter((s) => renderOf(s._decision) === "blocked").length;
  const tf = TIMEFRAMES.find((x) => x.id === timeframe) || TIMEFRAMES[1];
  const change = T && T.account ? T.account.percent : null;

  const cells = [];
  cells.push(`<div class="cell"><div class="l"><button data-m="acct" data-arg="${escAttr({ which: "value" })}">Account value</button></div>
    <div class="v num">${av.status === "known" ? money0(av.value)
      : `<button class="absent" data-m="acct" data-arg="${escAttr({ which: "value" })}">not known</button>`}${
      av.status === "known" ? cmMark(av.cautions) : ""}</div></div>`);
  cells.push(`<div class="cell"><div class="l"><button data-menu="timeframe" data-arg="{}">${esc(tf.label)} ▾</button></div>
    <div class="v">${change && change.status === "known"
      ? `<button data-m="timeframe" data-arg="{}"><span class="num ${change.value >= 0 ? "pos" : "neg"}">${change.value >= 0 ? "+" : "−"}${Math.abs(change.value).toFixed(1)}%</span>${cmMark(change.cautions)}${
          T && T.clamped ? ` <small>since ${esc(fmtCloseDate(T.since))}</small>` : ""}</button>`
      : `<button class="absent" data-m="timeframe" data-arg="{}">not known</button>`}</div></div>`);
  cells.push(`<div class="cell"><div class="l"><button data-m="acct" data-arg="${escAttr({ which: "cash" })}">Cash</button></div>
    <div class="v num">${cash.status === "known" ? money0(cash.value)
      : `<button class="absent" data-m="acct" data-arg="${escAttr({ which: "cash" })}">not known</button>`}</div></div>`);
  /* "6 of 20" where the strategy declared its slot count — the one place a
     portfolio-level limit reads in the header, and the count alone where it
     declares none. The total is the strategy's own value, host-resolved. */
  const slotTotal = ((folio.slots || {}).total) || {};
  cells.push(`<div class="cell"><div class="l"><button data-m="acct" data-arg="${escAttr({ which: "positions" })}">Positions</button></div>
    <div class="v num">${holdings.length}${slotTotal.status === "known"
      ? ` <small>of ${esc(String(slotTotal.value))}</small>` : ""}</div></div>`);
  cells.push(`<div class="cell"><div class="l"><button data-m="acct" data-arg="${escAttr({ which: "saying" })}">Something to say</button></div>
    <div class="v">${holdings.length ? `about <b class="num">${saying}</b> <small>of your ${holdings.length}</small>` : '<small>nothing is held</small>'}</div></div>`);
  if (blind) {
    cells.push(`<div class="cell"><div class="l"><button data-m="acct" data-arg="${escAttr({ which: "blind" })}">Cannot be watched</button></div>
      <div class="v"><b class="num" style="color:var(--unknown)">${blind}</b> <small>— exit checks cannot run</small></div></div>`);
  }
  if (owed) {
    cells.push(`<div class="cell"><div class="l">Waiting on you</div>
      <div class="v"><b class="num" style="color:var(--blocked)">${owed}</b> <small>— a decision is owed before any verdict</small></div></div>`);
  }
  $("maststats").innerHTML = cells.join("");
}

const TAB_DEFS = () => [
  ["list", "The list"],
  ["strategy", "Strategy"],
  ["measures", `Measures · ${journalReads().size}`],
  ["data", "Data"],
  ["analytics", "Looking back"],
];

function renderTabs() {
  if (!S.journal) { $("tabs").innerHTML = ""; return; }
  $("tabs").innerHTML = TAB_DEFS().map(([id, label]) =>
    `<button class="${tab === id && !openTicker ? "on" : ""}" data-act="tab" data-tab="${id}">${esc(label)}</button>`).join("");
}

/* Banners: problems that need to be visible from wherever you stand.
   Each says what happened and how to fix it. */
function banners() {
  const out = [];
  const bp = S.bank_problem;
  if (bp) {
    out.push(`<div class="banner err"><b>The measure definitions could not be ${bp.holding ? "reloaded" : "loaded"}.</b>
      ${bp.holding ? "An earlier version is still being served, so every figure below is computed under it." : "No figures can be computed until the file loads."}
      ${(bp.problems || []).map((p) => `<div class="bline">${esc(p)}</div>`).join("")}
      <div class="bline dim">${esc(bp.path || "")}</div></div>`);
  }
  if (S.strategy_missing) {
    out.push(`<div class="banner"><b>${esc(S.strategy_missing.name || "This journal's strategy")} is not installed on this machine.</b>
      Every verdict says so rather than guessing. Your record is untouched; installing the strategy brings the verdicts back.</div>`);
  }
  /* No banner for a recorded rule change: §6.19 dropped that friction to a
     quiet record. The change histories on the Strategy page list every entry
     with the way to attach the sentence. */
  if (S.journal_problem) {
    out.push(`<div class="banner err"><b>A journal could not be read.</b> ${esc(S.journal_problem)}</div>`);
  }
  return out.join("");
}
const fmtDefined = (v) => v === null || v === undefined ? "nothing"
  : Array.isArray(v) ? (v.length ? v.join(", ") : "nothing") : String(v);

/* ------------------------------------------------------------- the list */
const FILTERS = () => {
  const out = [
    ["everything", "Everything", (S.securities || []).length],
    ["holdings", "Holdings", inBucket("holdings").length],
    ["watchlist", "Watchlist", inBucket("ideas").length],
    ["track", "Track record", allClosedPeriods().length],
  ];
  if (S.list) out.push(["yourlist", "Your list",
    (S.list.rows || []).filter((r) => !r.held).length]);
  return out;
};

const allClosedPeriods = () => (S.securities || [])
  .flatMap((s) => closedPeriods(s).map((c) => ({ s, c })))
  .sort((a, b) => String(b.c.closed || "").localeCompare(String(a.c.closed || "")));

function orderRows(rows) {
  if (sortBy === "amount") {
    const rank = {};
    ((S.allocation || {}).ready || []).forEach((e, i) => { rank[e.ticker] = i; });
    return rows.slice().sort((a, b) =>
      (rank[a.ticker] ?? 999) - (rank[b.ticker] ?? 999)
      || orderKey(a) - orderKey(b) || a.ticker.localeCompare(b.ticker));
  }
  return rows.slice().sort((a, b) =>
    orderKey(a) - orderKey(b) || a.ticker.localeCompare(b.ticker));
}
const orderKey = (s) => {
  const spec = renderSpec(s._decision);
  return spec.order !== undefined ? spec.order : 99;
};

function listView() {
  const filters = FILTERS().map(([id, label, n]) =>
    `<button class="${filter === id ? "on" : ""}" data-act="filter" data-filter="${id}">${esc(label)}<span class="n">${n}</span></button>`).join("");
  const sortLabel = sortBy === "asks" ? "what asks most of you" : "what may take capital";
  const sortable = ((S.allocation || {}).ready || []).length > 0;
  const head = `<div class="filters">${filters}
    <span class="sort">ordered by ${sortable
      ? `<button data-act="sort">${esc(sortLabel)} ⇅</button>` : esc(sortLabel)}</span></div>`;
  const unfetched = (S.securities || []).filter((s) =>
    !s._data && !(s._fetch && s._fetch.running));
  const toolbar = `<div class="toolrow">
    <button data-m="add" data-arg="{}">Add securities</button>
    ${unfetched.length > 1 ? `<button data-act="fetchall">Fetch the ${unfetched.length} without data</button>` : ""}
    ${S.list ? `<button data-m="importlist" data-arg="{}">Import a fresh list</button>` : ""}
  </div>`;

  if (filter === "yourlist" && S.list) return head + toolbar + yourListSection();

  let rows;
  if (filter === "track") {
    rows = allClosedPeriods();
    if (!rows.length) {
      return head + toolbar + `<p class="quiet">Nothing has been closed yet. When a holding is sold out, its round trip lands here — a record of how it went, not a place to evaluate anything.</p>`;
    }
    return head + toolbar + trackTable(rows) + listNote();
  }
  const pool = filter === "holdings" ? inBucket("holdings")
    : filter === "watchlist" ? inBucket("ideas")
    : (S.securities || []);
  rows = orderRows(pool);
  if (!rows.length) {
    const invite = filter === "holdings"
      ? `Nothing is held. A purchase records itself here — and if you already own things, <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-m="add" data-arg="{}">add each security</button> and enter its history from your records. Those holdings are then judged for exit, not entry: the buy decision is behind them.`
      : `Nothing is being tracked. <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-m="add" data-arg="{}">Add a security</button> and this journal's strategy will say what it makes of it.`;
    return head + toolbar + `<p class="quiet">${invite}</p>`;
  }
  const tfLabel = (T && T.label) || "Timeframe";
  return head + toolbar + `<table class="list">
    <thead><tr><th>Security</th><th>What your strategy says</th><th>Price</th><th>Since buy</th><th>${esc(tfLabel)}</th><th>Of acct.</th></tr></thead>
    <tbody>${rows.map(securityRow).join("")}</tbody></table>` + listNote();
}

/* What the strategy said, resolved: the state name in its own colour, and a
   sub-line carrying one line of consequence — host-resolved payload facts
   where the payload holds figures, else the one-line consequence the state
   itself declares (the contract caps it at one line, so this can never grow
   a paragraph). The explaining prose renders once, in the margin the row
   opens, not beside thirty rows at a time. */
function sayCell(s) {
  const d = s._decision || {};
  const st = d.state || {};
  const sub = payloadLine(d, s.ticker) || oneline(st.consequence || "");
  const since = s._since_reading;
  const movedChip = since && since.status === "known" && since.changed
    ? ` <span class="moved" title="The verdict has moved since your saved reading of ${esc(since.since)}. It read ${esc((since.from || {}).name || "")} then.">moved since ${esc(since.since)}</span>` : "";
  return `<span class="state ${stateClass(d)}">${esc(st.name || "")}</span>${movedChip}${
    sub ? `<span class="sub">${sub}</span>` : ""}`;
}

/* One line of payload, host-resolved. The longer forms render on the page. */
function payloadLine(d, ticker) {
  const p = d.payload || {};
  if (d.render === "commit") {
    const alloc = ((S.allocation || {}).ready || []).concat((S.allocation || {}).waiting || [])
      .find((e) => e.ticker === ticker);
    const amt = alloc && alloc.amount && alloc.amount.status === "known"
      ? money100(alloc.amount.value) + " may go in — " : "";
    return esc(amt) + esc(sizeText(p.size)) + (p.condition ? " — once " + esc(p.condition.summary) : "");
  }
  if (d.render === "reduce") {
    const t = p.to || {};
    return "sell — trim · to " + esc(t.unit === "weight"
      ? `${t.value}% of the account` : `${Number(t.value).toLocaleString()} shares`);
  }
  if (d.render === "close") return "exit due " + esc(p.when || "");
  if (d.render === "blocked") {
    /* The consequence of a block is the way out of it, and the host's fix
       table owns those words. The strategy's `needs` prose is explanation
       and renders on the page and in the margin, never squeezed in here. */
    const spec = (S.state_fixes || {})[((d.state || {}).fix) || ""] || null;
    return spec ? esc(spec.label) : "";
  }
  return "";
}
function sizeText(size) {
  const z = size || {};
  return z.unit === "weight" ? `${Number(z.value).toFixed(1)}% of the account`
    : z.unit === "usd" ? "$" + Number(z.value).toLocaleString()
    : `${Number(z.value).toLocaleString()} shares`;
}

function priceCellHtml(s) {
  const p = s._price || {};
  if (p.value == null) {
    return `<button class="dim" data-m="price" data-arg="${escAttr({ t: s.ticker })}">—</button><span class="sub">no price — click for why</span>`;
  }
  const label = p.terminal
    ? `<button class="typed" data-m="price" data-arg="${escAttr({ t: s.ticker })}" title="This series has ended. This is the last close it ever had, not what it trades at.">ended°</button>`
    : p.source === "fetched"
      ? `close ${esc(fmtCloseDate(p.date))}`
      : `<button class="typed" data-m="price" data-arg="${escAttr({ t: s.ticker })}" title="Entered by hand — carries no date. Click for what that qualifies.">typed°</button>`;
  return `<span class="num">${money(p.value)}</span><span class="sub">${label}</span>`;
}

function weightCell(s) {
  const h = ((S.portfolio || {}).holdings || []).find((x) => x.ticker === s.ticker);
  if (!h) return '<span class="num dim">—</span>';
  const w = h.weight || {};
  const mv = h.market_value || {};
  if (w.status !== "known") {
    return `<button class="dim" data-m="absent" data-arg="${escAttr({ label: "Share of the account", reason: w.reason || "" })}">—</button>`;
  }
  return `<span class="num">${Number(w.value).toFixed(1)}%</span>${cmMark(w.cautions)}<span class="sub">${
    mv.status === "known" ? money0(mv.value) : ""}</span>`;
}

function securityRow(s) {
  const held = s.bucket === "holdings";
  const closed = s.bucket === "previous";
  const tfNode = T && T.rows ? T.rows[s.ticker] : null;
  const sinceBuy = held ? pctCell(s._return)
    : closed ? (() => {
        const last = closedPeriods(s).slice(-1)[0];
        return last ? pctCell(last.return) + '<span class="sub">while held</span>'
          : '<span class="num dim">—</span>';
      })()
    : '<span class="num dim">—</span><span class="sub">not held</span>';
  /* On the unfiltered list, money in a name is marked beside the name — the
     far-right column is the least-read place on the row. Filtered views ARE
     the mark, so they carry none. */
  const bucketMark = filter !== "everything" ? ""
    : held ? ' <span class="chip">held</span>'
    : closed ? ' <span class="chip">sold out</span>' : "";
  return `<tr class="sec" data-rowkey="r:${esc(s.ticker)}" data-m="row" data-arg="${escAttr({ t: s.ticker })}">
    <td class="tk"><button data-act="open" data-t="${esc(s.ticker)}">${esc(s.ticker)}</button>${bucketMark}<small>${esc(s.name || "")}${s._backfilled ? ' <span class="chip" title="Part of this record was entered from history rather than captured at the time.">from history</span>' : ""}</small></td>
    <td>${sayCell(s)}</td>
    <td>${priceCellHtml(s)}</td>
    <td>${sinceBuy}</td>
    <td>${pctCell(tfNode, tfWhy())}</td>
    <td>${held ? weightCell(s) : '<span class="num dim">—</span>'}</td>
  </tr>`;
}

function trackTable(rows) {
  const tfLabel = (T && T.label) || "Timeframe";
  return `<table class="list">
    <thead><tr><th>Security</th><th>The round trip</th><th>Price</th><th>While held</th><th>${esc(tfLabel)}</th><th>Since exit</th></tr></thead>
    <tbody>${rows.map(({ s, c }) => {
    const reasons = exitWords(c);
    const heldAgain = s.bucket === "holdings"
      ? ' <span class="chip">held again</span>' : "";
    const today = (s._decision || {}).state || {};
    const sinceExit = sinceExitCell(c.since_exit);
    return `<tr class="sec" data-rowkey="p:${esc(s.ticker)}:${esc(String(c.seq))}" data-m="row" data-arg="${escAttr({ t: s.ticker, period: c.seq })}">
      <td class="tk"><button data-act="open" data-t="${esc(s.ticker)}" data-p="${esc(String((c.buys || [])[0] || ""))}">${esc(s.ticker)}</button><small>${esc(s.name || "")}${heldAgain}</small></td>
      <td><span class="recstate">Closed${reasons.length ? " — sold: " + esc(reasons.join(", ")) : ""}</span>
        <span class="sub">${esc(c.opened || "")} → ${esc(c.closed || "")}${today.name ? ` · today it reads: ${esc(today.name)}` : ""}</span></td>
      <td>${priceCellHtml(s)}</td>
      <td>${pctCell(c.return)}</td>
      <td>${pctCell(T && T.rows ? T.rows[s.ticker] : null, tfWhy())}</td>
      <td>${sinceExit}</td>
    </tr>`;
  }).join("")}</tbody></table>`;
}

/* The allocation's own standing speaks for the list — four host-worded
   states with the arithmetic behind them, never a sentence composed here. */
function listNote() {
  const standing = ((S.allocation || {}).standing) || null;
  if (!standing) return "";
  return `<p class="listnote"><b>${esc(standing.headline || "")}</b> ${esc(standing.detail || "")}${
    standing.action ? ` <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-m="add" data-arg="{}">${esc(standing.action)}</button>` : ""}</p>`;
}

/* A since-exit figure, or its absence with the host's own reason. The node
   is {pct, reason, until, ...}, not known-or-absent, so it has its own
   renderer rather than passing through pctCell. */
function sinceExitCell(se) {
  if (!se) return '<span class="num dim">—</span>';
  if (se.pct === null || se.pct === undefined) {
    return `<button class="dim" data-m="absent" data-arg="${escAttr({
      label: "Since exit", reason: se.reason || "" })}">—</button>`;
  }
  return `<span class="num ${se.pct >= 0 ? "pos" : "neg"}">${se.pct >= 0 ? "+" : "−"}${Math.abs(se.pct).toFixed(1)}%</span>`
    + (se.until === "purchase" ? '<span class="sub">to your next buy</span>' : "");
}

/* The list a list-strategy journal works from. */
function yourListSection() {
  const L = S.list;
  if (!L.current) {
    return `<div class="panel"><h3>${esc((L.declared || {}).label || "The list you work from")}</h3>
      <p>${esc((L.declared || {}).explain || "")}</p>
      <p class="panelnote">${esc(sourceName((L.declared || {}).source))}</p>
      <p>No list has been imported yet.</p>
      <button class="m-act" data-m="importlist" data-arg="{}">Import a list</button></div>`;
  }
  const rows = (L.rows || []).map((r) => {
    const st = (r.decision || {}).state || {};
    const passed = r.passed_over
      ? `<span class="sub">passed over ${esc(String(r.passed_over.date || "").slice(0, 10))} — ${esc(r.passed_over.reason || "")}</span>` : "";
    return `<tr class="sec" data-rowkey="l:${esc(r.ticker)}">
      <td class="tk">${r.tracked
        ? `<button data-act="open" data-t="${esc(r.ticker)}">${esc(r.ticker)}</button>`
        : esc(r.ticker)}<small>${esc(r.name || "")}${r.new ? ' <span class="chip">new</span>' : ""}${r.held ? ' <span class="chip">held</span>' : ""}</small></td>
      <td>${r.decision
        ? `<span class="state ${RENDER_CLASS[r.decision.render] || "s-unknown"}">${esc(st.name || "")}</span>`
        : '<span class="dim">not looked at</span>'}${passed}</td>
      <td style="white-space:nowrap">${r.tracked
        ? `<button class="dim" data-act="open" data-t="${esc(r.ticker)}">open</button>`
        : `<button class="dim" data-act="track" data-t="${esc(r.ticker)}" data-name="${esc(r.name || "")}">track this</button>`}
        ${!r.held && !r.passed_over ? ` · <button class="dim" data-m="passover" data-arg="${escAttr({ t: r.ticker, name: r.name || "" })}">not buying this one</button>` : ""}</td>
    </tr>`;
  }).join("");
  const c = L.current;
  const history = (L.history || []).length > 1
    ? `<p class="listnote">${L.history.length - 1} earlier list${L.history.length === 2 ? "" : "s"} on record, kept whole and never rewritten.</p>` : "";
  /* The framing prose is a gloss, not a greeting — it reads once, behind
     the heading, like every other explanation in this program. */
  return `<div class="panel"><h3><button data-m="listabout" data-arg="{}">${esc((L.declared || {}).label || "Your list")}</button></h3>
    <div class="kv"><span class="k">Pulled</span><span class="v num">${esc(c.pulled_on || "")}</span></div>
    ${c.floor ? `<div class="kv"><span class="k">Smallest asked for</span><span class="v num">${money0(c.floor)}</span></div>` : ""}
    <p class="panelnote">The order below is yours to ignore — the list carries no ranking here.</p></div>
  <table class="list"><thead><tr><th>Name</th><th>Standing</th><th></th></tr></thead><tbody>${rows}</tbody></table>${history}`;
}

/* What the list is and where it comes from, read on request. */
PANES.listabout = () => {
  const declared = (S.list || {}).declared || {};
  return `<p class="m-kicker">The list this journal works from</p>
<h3>${esc(declared.label || "Your list")}</h3>
${prose(declared.explain || "")}
<p class="m-quiet">${esc(sourceName(declared.source))}</p>`;
};

/* ------------------------------------------------------- margin: previews */
/* Clicking a row previews its whole verdict in the margin — the walk-fifty-
   candidates loop. Opening the page is one more click, on the action. */
PANES.row = (a) => {
  const s = find(a.t);
  if (!s) return PANES.rest();
  const d = s._decision || {};
  const st = d.state || {};
  const kicker = s.bucket === "holdings" ? "Holding" : s.bucket === "ideas" ? "Watchlist" : "Track record";
  const summary = (d.reason || {}).summary || "";
  const period = a.period !== undefined
    ? periods(s).find((c) => c.seq === a.period) : null;

  if (period && !period.open) {
    const reasons = exitWords(period);
    return `<p class="m-kicker">Track record · ${esc(s.ticker)}</p>
<h3>Held ${esc(period.opened || "")} → ${esc(period.closed || "")}</h3>
<table class="m-series">
<tr><td>While held</td><td>${mNode(period.return, (v) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(1) + "%")}</td></tr>
${period.since_exit ? `<tr><td>Since exit</td><td>${sinceExitCell(period.since_exit)}</td></tr>` : ""}
${reasons.length ? `<tr><td>Sold because</td><td>${esc(reasons.join(", "))}</td></tr>` : ""}
${st.name ? `<tr><td>Today it reads</td><td>${esc(st.name)}</td></tr>` : ""}
</table>
<p class="m-quiet">Since-exit is how your sell rules are graded, not an invitation to regret. Considering it again? It re-enters through the watchlist and is judged from scratch.</p>
<button class="m-act" data-act="open" data-t="${esc(s.ticker)}" data-p="${esc(String((period.buys || [])[0] || ""))}">Open ${esc(s.ticker)}</button>`;
  }

  const alloc = ((S.allocation || {}).ready || []).concat((S.allocation || {}).waiting || [])
    .find((e) => e.ticker === s.ticker);
  const tooSmall = alloc && alloc.below_minimum
    && alloc.below_minimum.status === "known" && alloc.below_minimum.value;
  const allocRows = alloc && d.render === "commit" ? `<table class="m-series">
    ${alloc.amount ? `<tr><td>May go in now</td><td>${mNode(alloc.amount, money100)}${
      alloc.shares_approx && alloc.shares_approx.status === "known"
        ? ` <span class="dim">· about ${Number(alloc.shares_approx.value).toLocaleString()} sh</span>` : ""}</td></tr>` : ""}
    ${alloc.amount && alloc.amount.status !== "known" ? `<tr><td colspan="2" class="dim">${esc(alloc.amount.reason || "")}</td></tr>` : ""}
    ${(S.portfolio || {}).cash && S.portfolio.cash.status === "known" ? `<tr><td>Free cash</td><td class="num">${money0(S.portfolio.cash.value)}</td></tr>` : ""}
    ${alloc.condition ? `<tr><td>Waiting on</td><td>${esc(alloc.condition.summary || "")}</td></tr>` : ""}
  </table>${tooSmall
    ? `<p class="m-quiet">Below your strategy's smallest addition worth making — ${esc((alloc.below_minimum.provenance || [])[0] || "")}. Nothing stops a smaller purchase; this is the strategy's own view of what is worth the trade.</p>` : ""}` : "";

  const held = s.bucket === "holdings" ? (() => {
    const h = ((S.portfolio || {}).holdings || []).find((x) => x.ticker === s.ticker);
    const p = openPeriod(s);
    return `<table class="m-series">
      <tr><td>${esc(String(s._shares))} sh at ${money(s._cost_basis)} avg</td><td>${h ? mNode(h.market_value, money0, "Market value") + cmMark((h.market_value || {}).cautions) : ""}</td></tr>
      <tr><td>Since buy</td><td>${mNode(s._return, (v) => (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(1) + "%")}</td></tr>
      ${p && p.opened ? `<tr><td>Held since</td><td class="num">${esc(p.opened)}</td></tr>` : ""}
      ${h && h.weight && h.weight.status === "known" ? `<tr><td>Of the account</td><td class="num">${Number(h.weight.value).toFixed(1)}%${cmMark(h.weight.cautions)}</td></tr>` : ""}
    </table>`;
  })() : "";

  /* An unheld name has no position facts, so the margin's job is what the
     row cannot hold instead: the unanswered questions by name, the groups
     standing between it and a different verdict, and when the reading it
     rests on was taken. */
  const unheld = s.bucket !== "holdings" ? (() => {
    const ev = ((d.reason || {}).evidence || []);
    const owedQs = (s._judgements || []).filter((j) => j.cited && !j.mark);
    const owed = owedQs.length
      ? `<div class="m-h">Waiting on you</div>${owedQs.map((j) =>
          `<p class="m-line"><button data-m="judgement" data-arg="${escAttr({ t: s.ticker, id: j.id })}">${esc(j.label || j.id)}</button> — <span class="absent">not assessed</span></p>`).join("")}` : "";
    /* A group whose unreadable rows are all questions for the reader is
       already listed above by name; repeating its tally under a second
       heading would be the duplication this margin exists to end. */
    const humanOnly = (g) => ev.filter((e2) => e2.group === g.id && e2.outcome === "unknown")
      .every((e2) => ((e2.subject || {}).kind) === "judgement");
    const standing = ((d.reason || {}).groups || []).filter((g) =>
      g.outcome === "fail" || (g.outcome === "unknown" && !humanOnly(g)));
    const grpRows = standing.length
      ? `<div class="m-h">What stands in the way</div><table class="m-series">${standing.map((g) => {
          const [word, cls] = OUTCOME[g.outcome === "fail" ? "fail" : "unknown"];
          return `<tr><td><button data-m="group" data-arg="${escAttr({ t: s.ticker, gid: g.id })}">${esc(g.name)}</button></td>
            <td><span class="${cls}">${esc(word)}</span> · <span class="num">${g.passed} of ${g.tested}</span></td></tr>`;
        }).join("")}</table>` : "";
    const dd = s._data;
    const p = s._price || {};
    const lastRead = `<div class="m-h">The last reading</div><table class="m-series">
      <tr><td><button data-m="datastatus" data-arg="${escAttr({ t: s.ticker })}">Filings</button></td>
        <td>${s.fetch_refused && !(dd && dd.filings_held) ? '<span class="absent">fetch refused</span>' : dd ? `<span class="num">${esc(String(dd.filings_held))}</span> · fetched ${esc(dd.last_fetch ? String(dd.last_fetch.at).slice(0, 10) : "never")}` : "never fetched"}</td></tr>
      <tr><td><button data-m="price" data-arg="${escAttr({ t: s.ticker })}">Price</button></td>
        <td>${p.value == null ? '<span class="absent">not known</span>'
          : `<span class="num">${money(p.value)}</span> · ${p.source === "manual" ? "typed" : `close ${esc(fmtCloseDate(p.date))}`}`}</td></tr>
    </table>`;
    return owed + grpRows + lastRead;
  })() : "";

  const rests = ((d.reason || {}).rests_on || []);
  const decided = rests.length
    ? `<div class="m-h">What decided it</div><p>${rests.map((x) => esc(x.label || x.id)).join(" · ")}</p>` : "";
  return `<p class="m-kicker">${esc(kicker)} · ${esc(s.ticker)}</p>
<h3><span class="state ${stateClass(d)}">${esc(st.name || "")}</span></h3>
${summary ? `<p>${esc(summary)}</p>` : ""}
${decided}${allocRows}${held}${unheld}
<button class="m-act" data-act="open" data-t="${esc(s.ticker)}">Open ${esc(s.ticker)}</button>
${d.render === "commit" ? `<button class="m-act quiet" data-m="buy" data-arg="${escAttr({ t: s.ticker })}">Record a purchase</button>` : ""}`;
};

/* ------------------------------------------------- margin: account cells */
PANES.acct = (a) => {
  const folio = S.portfolio || {};
  if (a.which === "value") {
    const av = folio.account_value || {};
    return `<p class="m-kicker">The account</p>
<h3>Account value</h3>
${av.status === "known"
    ? `<p><b class="num">${money0(av.value)}</b></p>${mProv(av.provenance)}${mCautions(av.cautions)}`
    : `<p><span class="absent">not known</span></p><p>${esc(av.reason || "")}</p>`}
<p class="m-quiet">Free cash plus every holding at its own price — derived by the journal, never typed. One unpriced holding makes the whole figure absent rather than quietly smaller.</p>`;
  }
  if (a.which === "cash") {
    const cash = folio.cash || {};
    const opened = (S.cash || {}).opened;
    return `<p class="m-kicker">The account</p>
<h3>Cash</h3>
${cash.status === "known"
    ? `<p><b class="num">${money0(cash.value)}</b></p>${mProv(cash.provenance)}`
    : `<p><span class="absent">not known</span></p><p>${esc(cash.reason || "")}</p>`}
${opened ? `<p class="m-quiet">Derived from the dated cash record — the opening balance and every deposit, withdrawal and dividend since, plus what your own trades moved.</p>` : ""}
<button class="m-act" data-m="cash" data-arg="{}">${opened ? "Record money in or out" : "Open the cash record"}</button>
${cashMini()}`;
  }
  if (a.which === "saying") {
    return `<p class="m-kicker">The account</p>
<h3>Something to say</h3>
<p>How many of your holdings have a verdict that asks for an action — an add, a trim, or an exit. It counts only states about the <b>position</b>; a holding the tool cannot evaluate is a different fact and counted apart.</p>
<p class="m-quiet">The tool never owes you a task and never says "done" — this is it reporting, not demanding.</p>`;
  }
  if (a.which === "blind") {
    return `<p class="m-kicker">The account</p>
<h3>Cannot be watched</h3>
<p>Holdings whose exit checks cannot run — not calm, blindness. The strategy has nothing to say about whether to stay, which is not the same as "nothing to do".</p>
<p class="m-quiet">Fetching data, or typing the figures you have, is the way back for each.</p>`;
  }
  const limits = ((S.strategy || {}).limits || []);
  const slots = (S.portfolio || {}).slots || {};
  const total = slots.total || {};
  const slotLine = total.status === "known"
    ? `<p>${slots.occupied} of the <b class="num">${esc(String(total.value))}</b> places this strategy runs are taken. The limit is the strategy's own — reading it here every visit is how a portfolio-level risk rule stays visible without a screen of its own.</p>${mProv(total.provenance)}`
    : `<p>How many names the account holds now.</p><p class="m-quiet">${esc(total.reason || "This strategy declares no limit of its own here — that is a true fact about the method, not a gap in the screen.")}</p>`;
  return `<p class="m-kicker">The account</p>
<h3>Positions</h3>
${slotLine}
${limits.length ? `<div class="m-h">What this method does not promise</div>${limits.map((l) =>
    `<p><b>${esc(l.title || "")}</b></p>${prose(l.body || "")}`).join("")}` : ""}`;
};

function cashMini() {
  const led = ((S.cash || {}).ledger || []).slice(-6).reverse();
  if (!led.length) return "";
  return `<div class="m-h">The record, newest first</div><table class="m-series">${led.map((e) =>
    `<tr><td>${esc(String(e.date || "").slice(0, 10))} · ${esc(e.label || e.kind)}</td>
     <td class="num">${e.direction < 0 ? "−" : "+"}${money0(Math.abs(e.amount))}</td></tr>`).join("")}</table>`;
}

/* The timeframe gloss: what the header figure means. Choosing the window is
   chrome and happens in the dropdown on the header cell, not here. */
PANES.timeframe = () => {
  const acct = T && T.account;
  const ch = acct && acct.change;
  const pc = acct && acct.percent;
  const body = !T ? "<p class=\"m-hint\">Reading…</p>"
    : T.error ? `<p><span class="absent">not known</span> — ${esc(T.error)}</p>`
    : ch && ch.status === "known"
      ? `<p>The account moved <b class="num">${money0(ch.value)}</b>${pc && pc.status === "known"
          ? ` (<b class="num">${pc.value >= 0 ? "+" : "−"}${Math.abs(pc.value).toFixed(1)}%</b>)` : ""} since ${esc(T.since || "")}.</p>
        ${T.clamped ? `<p class="m-quiet">The window you chose starts before this journal's cash record opened, so the figure runs from ${esc(T.since || "")} — the day the record began. What the account held before it started being kept is not something the record can say.</p>` : ""}
        ${mProv(ch.provenance)}${mCautions(ch.cautions)}
        <p class="m-quiet">Money you paid in or took out is netted out, so adding cash never reads as a gain. Dividends are not netted — a holding paying cash out is the account earning.</p>`
      : `<p><span class="absent">not known</span> — ${esc((ch || {}).reason || "the window could not be read")}</p>`;
  return `<p class="m-kicker">The timeframe</p>
<h3>Change over a window you choose</h3>
${body}
<p class="m-quiet">The window is chosen on the header cell itself, and every row's "${esc((T && T.label) || "timeframe")}" column reads over the same one.</p>`;
};

/* Why a timeframe cell can be empty when the whole reply is missing. */
const tfWhy = () => !T ? "the timeframe has not been read yet"
  : T.error ? `the timeframe could not be read — ${T.error}`
  : "this security was not in the last timeframe reading — it may have just been added";

/* Every reason a holding period's exit gave, in words — with the share of
   the exit each accounts for when there was more than one. The host counted
   the shares; nothing here re-weights anything. */
function exitWords(c) {
  const rows = ((c || {}).exit || {}).reasons || [];
  return rows.map((r) => typeof r === "string" ? r
    : rows.length > 1 && r.share != null
      ? `${r.reason} (${r.share}% of the exit)` : r.reason);
}
