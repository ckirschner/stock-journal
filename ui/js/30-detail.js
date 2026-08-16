/* One security's page, in the order the questions come:

   1. What is my status on this security?         — the verdict card
   2. How do the required metrics fare?           — what your rules check,
      with the questions only you can answer answered (or owed) in place
   3. Are there open questions for me?            — answers on record that
      nothing currently asks, then the record itself
   4. What else is stored?                        — the full measure
      inventory, folded: a reference opened on purpose, never an ambush

   Terse is the resting state: one line per fact, and every line is a handle
   into the margin. Nothing here recomputes a figure — every number is a
   served node, rendered with its absence or its qualification attached. */

function detailView(s) {
  const d = s._decision || {};
  const period = subjectPeriod(s);
  const isOpen = !!(period && period.open);
  const isClosed = !!(period && !period.open);
  const backfilled = s._backfilled;

  const meta = [];
  if (isOpen && period.opened) meta.push(`Held since ${esc(period.opened)}`);
  if (isClosed) meta.push(`Held ${esc(period.opened || "")} → ${esc(period.closed || "")}${periods(s).length > 1 ? ` · ${ordinal(period.seq).toLowerCase()} holding` : ""}`);
  if (!period) meta.push("Not held");
  const strat = (d.strategy || {}).name || ((S.journal || {}).strategy || {}).name;
  if (strat) meta.push(`judged by ${esc(strat)}`);

  return `
  <div class="crumb"><button data-act="back">← The list</button></div>
  <div class="dhead"><div>
    <h1>${esc(s.ticker)} <small>${esc(s.name || "")}</small>${backfilled ? ' <span class="chip" title="Part of this record was entered from history rather than captured at the time.">from history</span>' : ""}</h1>
    <div class="meta">${meta.join(" · ")}</div>
  </div></div>
  ${verdictCard(s, d)}
  ${factsStrip(s, period, isOpen, isClosed)}
  ${actsRow(s, isOpen)}
  ${evidenceSections(s, d)}
  ${judgementSection(s)}
  ${recordSection(s)}
  ${coverageSection(s)}`;
}

/* ---------------------------------------------------------- the verdict */
function verdictCard(s, d) {
  const st = d.state || {};
  const r = d.reason || {};
  /* A state that is waiting says what it waits for in the headline. */
  const p = d.payload || {};
  const wait = d.render === "commit" && p.condition ? `— once ${esc(p.condition.summary)}`
    : d.render === "close" && p.when ? `— exit due ${esc(p.when)}`
    : d.render === "reduce" && p.to ? `— trim to ${esc(sizeText(p.to))}`
    : "";
  const rests = (r.rests_on || []);
  const decided = rests.length
    ? `<span><b>What decided it:</b> ${rests.map((x, i) =>
        `<button data-m="${x.reads || (x.kind === "measure" || x.kind === "judgement") ? "measure" : "subject"}" data-arg="${
          x.reads || x.id
            ? escAttr({ sid: x.reads || x.id, t: s.ticker, ev: evFor(d, x) })
            : escAttr({ ev: evFor(d, x) || { subject: x, observed: {} } })}">${esc(x.label || x.id)}</button>`).join(" · ")}</span>`
    : "";
  const since = s._since_reading;
  const canAnchor = !((s._snapshots || {}).refusal) && s._decision;
  const sinceLine = since && since.status === "known"
    ? `<span>Since your reading of ${esc(since.since)}: <b>${since.changed
        ? `it moved — it read ${esc((since.from || {}).name || "")} then`
        : "the verdict stands where it stood"}</b> <button data-m="readings" data-arg="${escAttr({ t: s.ticker })}">compare</button></span>`
    : `<span class="dim">${esc((since || {}).reason || "no saved reading stands to measure against")}${
        canAnchor ? ` — <button data-m="snapshot" data-arg="${escAttr({ t: s.ticker })}">save today’s</button> and “what changed” gets an anchor` : ""}.</span>`;
  const needs = d.render === "blocked" && (p.needs || []).length
    ? `<ul>${p.needs.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>` : "";
  const plan = d.render === "commit" && (p.plan || []).length
    ? `<ul>${p.plan.map((t2) => `<li>${esc(sizeText(t2.size))} held back — once ${esc((t2.condition || {}).summary || "")}</li>`).join("")}</ul>` : "";
  return `<div class="vcard">
    <div class="vname"><button class="state ${stateClass(d)}" data-m="state" data-arg="${escAttr({ t: s.ticker })}">${esc(st.name || "")}</button>
      ${wait ? `<span class="vwait">${wait}</span>` : ""}</div>
    ${r.summary ? `<p class="vsum">${esc(r.summary)}</p>` : ""}
    ${d.render === "commit" && p.size ? `<p class="vsum"><b>${esc(commitLine(s, p))}</b></p>` : ""}
    ${needs}${plan}
    ${r.note ? `<p class="vsum">${esc(r.note)}</p>` : ""}
    <div class="vrow">${decided}${sinceLine}${fixLink(d)}</div>
  </div>`;
}
/* Sizing headlines in dollars with shares beside it and the percent smallest
   — but only figures the host resolved. The allocation entry carries the
   dollar amount; without one, the strategy's own size unit stands alone. */
function commitLine(s, p) {
  const alloc = ((S.allocation || {}).ready || []).concat((S.allocation || {}).waiting || [])
    .find((e) => e.ticker === s.ticker);
  const amt = alloc && alloc.amount;
  if (amt && amt.status === "known") {
    /* Served figures only: the dollar amount is the host's, and a share
       count appears only where the strategy itself sized in shares. A count
       derived here from amount ÷ price would be view arithmetic on the one
       number a sizing decision reads (principles 5 and 13). */
    const sh = (p.size || {}).unit === "shares"
      ? ` — ${Number(p.size.value).toLocaleString()} sh` : "";
    const pct = (p.size || {}).unit === "weight" ? ` (${p.size.value}% of the account)` : "";
    return `${money0(amt.value)} may go in${sh}${pct}`;
  }
  return `Sized by the strategy: ${sizeText(p.size)}${amt && amt.status === "absent" ? ` — in dollars, ${amt.reason}` : ""}`;
}
function fixLink(d) {
  const fix = ((d || {}).state || {}).fix;
  const spec = fix ? (S.state_fixes || {})[fix] : null;
  if (!spec) return "";
  return `<span><button data-act="${esc(fix)}" data-t="${esc(openTicker || "")}"><b>${esc(spec.label)}</b></button></span>`;
}
/* Find the evidence row a rests_on subject refers to, so the margin gloss
   opens on the same figures the verdict used. */
function evFor(d, subj) {
  return (((d || {}).reason || {}).evidence || []).find((e) =>
    (e.subject || {}).id === subj.id && (e.subject || {}).kind === subj.kind) || null;
}

/* ------------------------------------------------------------- the facts */
function factsStrip(s, period, isOpen, isClosed) {
  const cells = [];
  const priceBtn = `<button data-m="price" data-arg="${escAttr({ t: s.ticker })}">${priceFactVal(s)}</button>`;
  cells.push(cell("Price", priceBtn));
  if (isOpen) {
    const h = ((S.portfolio || {}).holdings || []).find((x) => x.ticker === s.ticker);
    cells.push(cell("Avg cost", factBtn(`<span class="num">${money(s._cost_basis)}</span>`,
      { label: "Average cost", text: money(s._cost_basis),
        explain: "What you paid per share, averaged across this holding's open lots. Read off your own purchase record." })));
    cells.push(cell("Shares", factBtn(`<span class="num">${esc(String(s._shares))}</span>`,
      { label: "Shares held", text: String(s._shares),
        explain: "What the open lots hold — everything bought less everything sold, oldest shares first. Derived from the lots on every read; a stored total would be a second opinion about a fact they already settle." })));
    cells.push(cell("Value", factBtn(nodeFactBtn(h && h.market_value, money0, "Market value"),
      { label: "Market value", text: h && h.market_value && h.market_value.status === "known" ? money0(h.market_value.value) : "",
        explain: "Shares times the price of this security's own instrument — never a sibling share class's.",
        cautions: (h && h.market_value && h.market_value.cautions) || [],
        provenance: (h && h.market_value && h.market_value.provenance) || [] })));
    cells.push(cell("Of account", factBtn(nodeFactBtn(h && h.weight, (v) => Number(v).toFixed(1) + "%", "Share of the account"),
      { label: "Share of the account", text: h && h.weight && h.weight.status === "known" ? Number(h.weight.value).toFixed(1) + "%" : "",
        explain: "This holding's market value over everything the account is worth — cash included. It is the figure a sizing rule binds on.",
        cautions: (h && h.weight && h.weight.cautions) || [],
        provenance: (h && h.weight && h.weight.provenance) || [] })));
    cells.push(cell("Since buy", factBtn(pctCell(s._return),
      { label: "Since buy", text: s._return && s._return.status === "known" ? `${s._return.value >= 0 ? "+" : "−"}${Math.abs(s._return.value).toFixed(1)}%` : "",
        explain: "This holding against what it cost — the open round trip, not the ticker's lifetime. A name closed and bought back starts a fresh figure.",
        provenance: (s._return && s._return.provenance) || [] })));
  }
  if (isClosed) {
    cells.push(cell("Exit price", nodeFactBtn((period.exit || {}).price,
      (v) => money(v), "The share-weighted price this holding got out at")));
    cells.push(cell("While held", pctCell(period.return)));
    cells.push(cell("Since exit", sinceExitCell(period.since_exit)));
    const reasons = exitWords(period);
    if (reasons.length) cells.push(cell("Sold because", esc(reasons.join(", "))));
    if (periods(s).length > 1 && s._lifetime_return) {
      cells.push(cell("All holdings", pctCell(s._lifetime_return)));
    }
  }
  if (!period) {
    cells.push(cell("Added", `<span class="num">${esc(String(s.added || s.created || "").slice(0, 10) || "—")}</span>`));
  }
  const tfNode = T && T.rows ? T.rows[s.ticker] : null;
  cells.push(cell((T && T.label) || "Timeframe", factBtn(pctCell(tfNode, tfWhy()),
    { label: (T && T.label) || "Timeframe",
      text: tfNode && tfNode.status === "known" ? `${tfNode.value >= 0 ? "+" : "−"}${Math.abs(tfNode.value).toFixed(1)}%` : "",
      explain: "This security's own price move over the window chosen in the header — nothing about your position is in it.",
      cautions: (tfNode && tfNode.cautions) || [],
      provenance: (tfNode && tfNode.provenance) || [] })));
  const dstat = s._fetch && s._fetch.running ? "fetching…"
    : s._data ? `<span class="num">${esc(String(s._data.filings_held))}</span> <small>fetched ${esc(s._data.last_fetch ? String(s._data.last_fetch.at).slice(0, 10) : "never")}</small>`
    : "never fetched";
  cells.push(cell("Filings", `<button data-m="datastatus" data-arg="${escAttr({ t: s.ticker })}">${dstat}</button>`));
  return `<div class="facts">${cells.join("")}</div>`;
}
const cell = (l, v) => `<div class="cell"><div class="l">${esc(l)}</div><div class="v">${v}</div></div>`;
/* A known figure wraps in a button into its gloss; a figure that already
   renders as a button (an absence with its reason) is left as it is. */
const factBtn = (html, gloss) => html.includes("<button")
  ? html : `<button data-m="figure" data-arg="${escAttr(gloss)}">${html}</button>`;
function priceFactVal(s) {
  const p = s._price || {};
  if (p.value == null) return '<span class="absent">not known</span>';
  const mark = p.terminal ? ' <small><em class="typed">ended°</em></small>'
    : p.source === "manual" ? ' <small><em class="typed">typed°</em></small>'
    : ` <small>close ${esc(fmtCloseDate(p.date))}</small>`;
  return `<span class="num">${money(p.value)}</span>${mark}`;
}
function nodeFactBtn(node, renderVal, label) {
  if (!node) return '<span class="dim">—</span>';
  if (node.status !== "known") {
    return `<button class="absent" data-m="absent" data-arg="${escAttr({ label, reason: node.reason || "" })}">not known</button>`;
  }
  return `<span class="num">${renderVal(node.value)}</span>${cmMark(node.cautions)}`;
}

function actsRow(s, isOpen) {
  const fetching = s._fetch && s._fetch.running;
  return `<div class="acts">
    <button class="pri" data-act="fetch" data-t="${esc(s.ticker)}" ${fetching ? "disabled" : ""}>${fetching ? "Fetching…" : "Fetch data"}</button>
    <button data-m="snapshot" data-arg="${escAttr({ t: s.ticker })}">Save today’s reading</button>
    <button data-m="noteadd" data-arg="${escAttr({ t: s.ticker })}">Add note</button>
    <button data-m="buy" data-arg="${escAttr({ t: s.ticker })}">${isOpen ? "Buy more" : s.bucket === "previous" ? "Buy it back" : "Record a purchase"}</button>
    ${isOpen ? `<button class="warn" data-m="sell" data-arg="${escAttr({ t: s.ticker })}">Record a sale</button>` : ""}
    <button style="color:var(--dim)" data-menu="more" data-arg="${escAttr({ t: s.ticker })}">More ▾</button>
  </div>`;
}

/* ----------------------------------------------- 2 · what the rules check */
function evidenceSections(s, d) {
  const r = (d || {}).reason || {};
  const ev = r.evidence || [];
  if (!ev.length) {
    return `<h2 class="sect">What your rules are checking</h2>
      <p class="quiet">No figures were cited — nothing about the security was read.</p>`;
  }
  const groups = r.groups || [];
  const byGroup = {};
  groups.forEach((g) => { byGroup[g.id] = { g, rows: [] }; });
  const loose = [], noted = [];
  ev.forEach((item, i) => {
    if (item.group && byGroup[item.group]) byGroup[item.group].rows.push([item, i]);
    else if (item.outcome === "noted") noted.push([item, i]);
    else loose.push([item, i]);
  });
  const order = (rows) => !problemsFirst ? rows
    : rows.slice().sort((a, b) => rank(a[0]) - rank(b[0]));
  const rank = (item) => item.outcome === "fail" ? 0 : item.outcome === "unknown" ? 1 : 2;

  const grpHtml = groups.map((g) => {
    const slot = byGroup[g.id];
    const rows = order(slot.rows).map(([item, i]) => evidenceRow(s, item, i)).join("");
    return `<div class="grp">
      <div class="gh"><span class="gn"><button data-m="group" data-arg="${escAttr({ t: s.ticker, gid: g.id })}">${esc(g.name)}</button></span>
        <span class="gtally">${tally(g)}</span></div>
      <table class="ev"><tbody>${rows}</tbody></table></div>`;
  }).join("");
  const looseHtml = loose.length
    ? `<div class="grp"><table class="ev"><tbody>${order(loose).map(([item, i]) => evidenceRow(s, item, i)).join("")}</tbody></table></div>` : "";
  const notedHtml = noted.length
    ? `<h2 class="sect">Everything else this strategy reads<span class="aside">reported, never blocking today’s verdict</span></h2>
       <table class="ev"><tbody>${noted.map(([item, i]) => evidenceRow(s, item, i)).join("")}</tbody></table>` : "";
  return `<h2 class="sect">What your rules are checking<span class="aside">
      <button data-act="problemsfirst">${problemsFirst ? "problems first ⇅" : "the strategy’s order ⇅"}</button>
      · click anything for the margin</span></h2>
    ${grpHtml}${looseHtml}${notedHtml}`;
}

function tally(g) {
  const need = g.requires === "all"
    ? (g.tested > 1 ? `all ${g.tested} must hold` : g.tested === 1 ? "it must hold" : "")
    : g.requires === "at_least"
      ? ((g.test && g.test.absent) ? "no bar is set"
        : `at least ${esc(String((g.test || {}).threshold))} must hold`)
      : "reported on every reading";
  const counted = g.tested
    ? `<b>${g.passed} of ${g.tested}</b> ${g.passed === 1 && g.tested === 1 ? "holds" : "hold"}`
      + (g.unknown ? ` · ${g.unknown} could not be worked out` : "")
    : "nothing tested";
  return `${need} · ${counted}`;
}

/* One evidence line: name · value° · test — whose limit · outcome. A line
   whose subject is a question only the reader can answer carries its answer
   verb in place — this table is the one surface that owns the questions the
   verdict asked, and sending the reader elsewhere to answer them is how one
   fact came to be printed three times. */
function evidenceRow(s, item, i) {
  const subj = item.subject || {};
  const obs = item.observed || {};
  const [word, cls] = OUTCOME[item.outcome] || [item.outcome, "o-unknown"];
  const isBank = !!subj.reads || ["measure", "judgement", "robustness", "change"].includes(subj.kind);
  const paneArg = isBank && (subj.reads || subj.id)
    ? { m: "measure", arg: { sid: subj.reads || subj.id, t: s.ticker, ev: item,
        kicker: item.outcome === "noted" ? "Measure · read, never blocking" : "Measure · read by this strategy" } }
    : { m: "subject", arg: { t: s.ticker, ev: item } };
  const val = obs.status === "known"
    ? `<span class="num">${esc(fmtSubject(subj, obs.value))}</span>${cmMark(obs.cautions)}`
    : `<span class="absent">${obs.status === "inapplicable" ? "not applicable" : "not known"}</span>`;
  let test = "";
  if (item.test) {
    const t = item.test;
    test = t.absent ? '<span class="absent">no limit set</span>'
      : `${esc(t.phrase || "")} ${esc(t.threshold_from && t.threshold_from.unit
          ? fmtUnit(t.threshold, t.threshold_from.unit)
          : fmtSubject(subj, t.threshold))}${t.threshold_from ? ` — your ${esc(t.threshold_from.label)}` : ""}`;
  }
  const at = subj.at ? ` <span class="dim">as at ${esc(subj.at)}</span>` : "";
  const decided = item.rests_on ? '<span class="req">decided this</span>' : "";
  const j = subj.kind === "judgement"
    ? (s._judgements || []).find((x) => x.id === (subj.reads || subj.id)) : null;
  const answer = j
    ? ` · <button data-m="judgement" data-arg="${escAttr({ t: s.ticker, id: j.id })}" data-jid="${esc(j.id)}">${j.mark ? "reassess" : "answer this"}</button>` : "";
  return `<tr class="hot"${j ? ' data-jrow="1"' : ""}><td class="en"><button data-m="${paneArg.m}" data-arg="${escAttr(paneArg.arg)}">${esc(subj.label || subj.id || "")}</button>${decided}${at}${answer}</td>
    <td class="ev-v">${val}</td>
    <td class="ev-t">${test}</td>
    <td class="ev-o ${cls}">${esc(word)}</td></tr>`;
}

/* -------------------------------------------- 4a · questions only you can */
/* The questions the verdict is asking live in the evidence table above,
   answered or answerable in place — one surface owns them. What remains
   here is the append-only leftover: answers on record that nothing
   currently asks, kept readable because the record never deletes. A
   security nothing was ever asked of gets no section, not an empty one. */
const MARK_WORD = { pass: "Passed", fail: "Failed" };
function judgementSection(s) {
  const js = (s._judgements || []).filter((j) => !j.cited);
  if (!js.length) return "";
  const rows = js.map((j) => {
    const mark = j.mark
      ? `<span class="${j.mark === "fail" ? "o-fail" : "o-pass"}">${esc(MARK_WORD[j.mark] || j.mark)}</span>`
      : '<span class="absent">not assessed</span>';
    const when = j.recorded ? ` <span class="dim">· ${esc(String(j.recorded).slice(0, 10))}</span>` : "";
    const stale = j.withdrawn ? ' <span class="chip">withdrawn</span>'
      : ' <span class="chip" title="This strategy is not currently asking this question; your answer stays readable.">not currently asked</span>';
    return `<div class="recline" id="j-${esc(j.id)}"><span class="rmain">
      <button data-m="measure" data-arg="${escAttr({ sid: j.id, t: s.ticker })}">${esc(j.label || j.id)}</button>
      — ${mark}${when}${stale}
      · <button data-m="judgement" data-arg="${escAttr({ t: s.ticker, id: j.id })}" data-jid="${esc(j.id)}">${j.mark ? "reassess" : "answer this"}</button></span>
      </div>`;
  }).join("");
  return `<h2 class="sect" id="judgements">Questions only you can answer<span class="aside">answers on record · nothing above asks them today</span></h2>${rows}`;
}

/* ------------------------------------------------- 4b · your record here */
function recordSection(s) {
  const lines = [];
  const t = s._thesis || {};
  lines.push(recLine(
    `<b>Why I own this</b> — ${t.status === "known"
      ? `<button data-m="thesis" data-arg="${escAttr({ t: s.ticker })}">read it</button> · and what would make you wrong`
      : `<span class="absent">nothing on record</span> · <button data-m="thesisedit" data-arg="${escAttr({ t: s.ticker })}">write it</button>`}`,
    t.status === "known" ? t.amended : null));
  const v = s._valuation || {};
  lines.push(recLine(
    `<b>Expected value</b> — ${v.status === "known"
      ? `<button data-m="ev" data-arg="${escAttr({ t: s.ticker })}">read the claim</button>`
      : `<span class="absent">not calculated</span> · this security has not been valued in this journal · <button data-m="ev" data-arg="${escAttr({ t: s.ticker })}">value it</button>`}`,
    v.status === "known" ? (v.claim || {}).made || v.amended : null));

  const snaps = (s._snapshots || {}).rows || [];
  const refusal = (s._snapshots || {}).refusal;
  if (refusal) {
    lines.push(recLine(`<b>Saved readings</b> — <span class="absent">cannot be shown</span> · ${esc(refusal)}`, null));
  } else {
    snaps.forEach((row) => {
      const gone = row.discarded
        ? ` · <span class="chip">discarded ${esc(row.discarded.day)}</span>${row.discarded.reason ? ` — ${esc(row.discarded.reason)}` : ""}`
        : ` · <button data-m="readings" data-arg="${escAttr({ t: s.ticker, seq: row.seq })}">compare</button>
            · <button data-m="discardsnap" data-arg="${escAttr({ t: s.ticker, seq: row.seq })}">discard</button>`;
      lines.push(recLine(
        `<b>Saved reading</b> — it read <i>${esc(row.state || "no verdict")}</i>${row.note ? ` · “${esc(row.note)}”` : ""}${gone}`,
        row.day));
    });
  }

  (s.notes || []).slice().reverse().forEach((n, ri) => {
    const i = (s.notes || []).length - 1 - ri;
    const short = String(n.text || "").slice(0, 60);
    lines.push(recLine(
      `<b>Note</b> — “${esc(short)}${(n.text || "").length > 60 ? "…" : ""}” · <button data-m="note" data-arg="${escAttr({ t: s.ticker, i })}">read</button>`,
      String(n.date || n.recorded || "").slice(0, 10)));
  });

  /* The lots, newest first, grouped by holding period when there are two.
     Each is one line citing what the record froze; the margin holds it all. */
  const ps = periods(s);
  const all = lotById(s);
  const lotLine = (l) => {
    const sale = l.kind === "sell" || !!l.reason;
    const chipBits = [];
    if (reconstructed(l)) chipBits.push(RECON_CHIP);
    if (l.unreconstructed) chipBits.push('<span class="chip" title="No verdict could be rebuilt for this day — not counted as acting against a signal, because there was none.">no verdict to rebuild</span>');
    else if (sale && l.rule_triggered === false) chipBits.push('<span class="chip" style="color:var(--exit)">against the signal</span>');
    else if (!sale && l.override) chipBits.push('<span class="chip" style="color:var(--exit)">against the signal</span>');
    const what = `${sale ? "Sold" : "Bought"} ${esc(String(l.shares))} at ${money(l.price)}`;
    return recLine(
      `<b>${what}</b>${sale && l.reason ? ` — ${esc(l.reason)}` : ""} ${chipBits.join(" ")}
       · <button data-m="lot" data-arg="${escAttr({ t: s.ticker, id: l.id })}">the record of that day</button>`,
      l.date);
  };
  if (ps.length > 1) {
    ps.slice().reverse().forEach((c) => {
      const { buys, sells } = periodLots(s, c);
      const span = c.open ? `${esc(c.opened || "")} → still held` : `${esc(c.opened || "")} → ${esc(c.closed || "")}`;
      lines.push(`<div class="recline"><span class="rmain dim">${esc(ordinal(c.seq))} holding · ${span}</span></div>`);
      buys.concat(sells).sort((a, b) => String(b.date).localeCompare(String(a.date)))
        .forEach((l) => lines.push(lotLine(l)));
    });
  } else {
    Object.values(all).sort((a, b) => String(b.date).localeCompare(String(a.date)))
      .forEach((l) => lines.push(lotLine(l)));
  }

  const falsifierNudge = s.bucket === "holdings"
    && !(t.status === "known" && (t.version || {}).falsifier)
    ? recLine(`<b>What would make me wrong</b> — <span class="absent">nothing on record</span> · <button data-m="thesisedit" data-arg="${escAttr({ t: s.ticker })}">write it</button>`, null) : "";

  return `<h2 class="sect">Your record on this security<span class="aside">append-only · nothing is ever edited</span></h2>
    ${falsifierNudge}${lines.join("")}`;
}
const recLine = (main, when) =>
  `<div class="recline"><span class="rmain">${main}</span><time>${esc(when || "—")}</time></div>`;

/* -------------------------------------- 4c · the rest of what is stored */
/* The full inventory — every measure the bank defines, whether or not this
   strategy reads it — is a different question from the rest of the page.
   "What does my strategy check" is the page; "what else does the bank know
   about this company" is a reference someone opens on purpose. So it folds:
   one line at rest, the inventory read from disk only when opened. The
   cross-check lives with the rest of the data-trust story, in the margin's
   "data behind this security" pane. */
function coverageSection(s) {
  if (!s.cik) {
    return `<h2 class="sect">Everything stored about this security</h2>
      <p class="quiet">Nothing has been fetched for ${esc(s.ticker)}, so only what you type exists here. <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-act="fetch" data-t="${esc(s.ticker)}">Fetch data</button> and every measure the bank defines is worked out from the filings.</p>`;
  }
  const fold = (body) => `<details class="covfold" data-covfold${coverageOpen ? " open" : ""}>
    <summary>Everything stored about this security<span class="aside">every measure the bank defines, whether or not this strategy reads it — a reference, opened on purpose</span></summary>
    ${body}</details>`;
  if (!coverageOpen) return fold("");
  if (C.coverageFor !== s.ticker || (!C.coverage && !C.loadingCoverage)) {
    loadCoverage(s.ticker);
  }
  if (!C.coverage || C.coverageFor !== s.ticker) {
    return fold(`<p class="quiet">Reading the stored filings…</p>`);
  }
  const cov = C.coverage;
  if (cov.error) {
    return fold(`<p class="quiet">The stored filings could not be read: ${esc(cov.error)}
      <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-act="coverage-retry" data-t="${esc(s.ticker)}">Try again</button></p>`);
  }
  const entries = (cov.entries || []).filter((e) => (bankMeta(e.id) || {}).kind !== "qualitative");
  const computed = entries.filter((e) => e.status === "computed");
  const absent = entries.filter((e) => e.status === "absent");
  const inapp = entries.filter((e) => e.status === "inapplicable");
  const row = (e) => {
    const val = e.status === "computed"
      ? `<span class="num">${esc(fmtBank(e.value, e.format))}</span>${cmMark(e.cautions)}`
      : `<span class="absent">${e.status === "inapplicable" ? "not applicable" : "not known"}</span>`;
    return `<tr class="hot"><td class="en"><button data-m="measure" data-arg="${escAttr({ sid: e.id, t: s.ticker, kicker: "Measure · in the bank" })}">${esc(e.label || e.id)}</button></td>
      <td class="ev-v">${val}</td>
      <td class="ev-t">${e.status !== "computed" ? oneline(e.reason || "") : ""}</td>
      <td class="ev-o o-noted"></td></tr>`;
  };
  return fold(`
    ${computed.length ? `<div class="grp"><div class="gh"><span class="gn">Worked out</span><span class="gtally"><b>${computed.length}</b> of ${entries.length}</span></div>
      <table class="ev"><tbody>${computed.map(row).join("")}</tbody></table></div>` : ""}
    ${absent.length ? `<div class="grp"><div class="gh"><span class="gn">Not known</span><span class="gtally">each says why — a fetch, a filing or a typed figure may close it</span></div>
      <table class="ev"><tbody>${absent.map(row).join("")}</tbody></table></div>` : ""}
    ${inapp.length ? `<div class="grp"><div class="gh"><span class="gn">Not built to describe this kind of company</span><span class="gtally">settled from the SEC’s own classification — no amount of fetching changes it</span></div>
      <table class="ev"><tbody>${inapp.map(row).join("")}</tbody></table></div>` : ""}`);
}
async function loadCoverage(ticker) {
  C.loadingCoverage = true;
  C.coverageFor = ticker;
  C.coverage = null;
  const r = await apiRaw("get_coverage", ticker);
  C.loadingCoverage = false;
  if (C.coverageFor !== ticker) return;   /* the page moved on */
  C.coverage = r.ok ? (r.coverage || { entries: [] }) : { entries: [], error: r.error };
  if (openTicker === ticker) render();
}
