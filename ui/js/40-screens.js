/* The screens behind the list: the strategy (read-only by design), the
   measures reference scoped to what this journal actually reads, the data
   screen, the backwards-looking analytics behind the journal menu, and the
   quick start that stands in for all of it before a journal exists. */

/* ------------------------------------------------------------- strategy */
function strategyView() {
  const st = S.strategy;
  const stamp = (S.journal || {}).strategy || {};
  if (!st) {
    return banners() + `<div class="panel"><h3>${esc(stamp.name || "This journal’s strategy")} is not installed</h3>
      <p>The journal is stamped with it — created ${esc(String((S.journal || {}).created || "").slice(0, 10))}, ${esc(stamp.name || "")} v${esc(stamp.version)} — and no verdict can be produced until a strategy with that id is back in the strategies folder. Nothing recorded is affected.</p></div>`
      + changeHistories();
  }
  const declines = (st.declines || []).length ? `
    <div class="panel"><h3>What it will not evaluate</h3>
      ${st.declines.map((x) => `<p><b>${esc(x.label || x.class)}</b> — ${esc(x.because || "")}${x.means ? ` <span class="dim">${esc(x.means)}</span>` : ""}</p>`).join("")}
      <p class="panelnote">Settled from the SEC’s own industry code inside a company’s filings, on the first fetch. A declined company is not a failed one — nothing was tested.</p></div>` : "";
  const limits = (st.limits || []).length ? `
    <div class="panel"><h3>What this method does not promise</h3>
      ${st.limits.map((l) => `<p><b>${esc(l.title || "")}</b></p>${prose(l.body || "")}`).join("")}</div>` : "";
  const states = `
    <div class="panel"><h3>What it can say</h3>
      ${(st.states || []).map((x) => {
        const spec = (S.render_types || {})[x.render] || {};
        return `<div class="kv"><span class="k"><span class="state ${RENDER_CLASS[x.render] || "s-unknown"}">${esc(x.name)}</span></span>
          <span class="v">${esc(spec.meaning || x.render)}<small>${esc(x.description || "")}</small></span></div>`;
      }).join("")}
      ${neverSays(st)}</div>`;
  const inputs = `
    <div class="panel"><h3>What it asked you</h3>
      ${(st.inputs || []).map((f) => {
        const val = f.answered_by === "host"
          ? (f.value !== null && f.value !== undefined
            ? `<b class="num">${esc(String(f.value))}</b><small>${esc(f.answered_how || "worked out by the journal")}</small>`
            : `<span class="absent">not worked out</span><small>${esc(f.unavailable || "")}</small>`)
          : f.inactive
            ? `<span class="dim">not asked</span><small>${esc(f.inactive)}</small>`
            : (f.value !== null && f.value !== undefined && f.value !== ""
              ? `<b>${esc(String(f.value))}</b>`
              : '<span class="absent">not answered</span>');
        return `<div class="kv"><span class="k"><button data-m="declared" data-arg="${escAttr({ kind: "input", id: f.id })}">${esc(f.label)}</button></span>
          <span class="v">${val}</span></div>`;
      }).join("")}
      ${(st.input_problems || []).length ? `<p class="panelnote" style="color:var(--blocked)">${st.input_problems.map(esc).join(" · ")}</p>` : ""}
      <button class="m-act quiet" data-m="settings" data-arg="{}">Change these answers</button>
      <p class="panelnote">Answers are facts about your account and genuinely move. The strategy’s own thresholds below do not move here — that is the point of them.</p></div>`;
  const values = `
    <div class="panel"><h3>Its settings — read-only here, by design</h3>
      ${(st.values || []).map((v) => `<div class="kv">
        <span class="k"><button data-m="declared" data-arg="${escAttr({ kind: "value", id: v.id })}">${esc(v.label)}</button></span>
        <span class="v"><b class="num">${esc(declaredText(v, v.value))}</b>
          <small>${v.set_by === "shipped default" ? "shipped default" : `${esc(v.set_by || "yours")} — shipped: ${esc(declaredText(v, v.shipped))}`}</small></span></div>`).join("")}
      ${(st.value_errors || []).length ? `<p class="panelnote" style="color:var(--exit)">${st.value_errors.map(esc).join(" · ")}</p>` : ""}
      <p class="panelnote">Changing a rule while looking at a position you want to buy is the failure this design exists to prevent. A threshold changes in the strategy’s own files, deliberately — and any change is detected and recorded below, whoever made it.</p></div>`;
  const list = st.list ? `
    <div class="panel"><h3>${esc(st.list.label || "It works from a list")}</h3>
      <p>${esc(st.list.explain || "")}</p><p class="panelnote">${esc(sourceName(st.list.source))}</p>
      <button class="m-act quiet" data-act="filter" data-filter="yourlist">Open the list</button></div>` : "";
  const refused = (S.refused || []).length ? `
    <div class="panel"><h3>Strategies that would not load</h3>
      ${S.refused.map((r) => `<p><b>${esc(r.name || r.bundle)}</b><br>${(r.errors || []).map(esc).join("<br>")}</p>`).join("")}</div>` : "";
  return banners() + `
    <div class="panel"><h3>${esc(st.name)} <span class="dim">v${esc(st.version)} · settings v${esc(st.values_version)} · contract ${esc(st.contract)}</span></h3>
      <p>${esc(st.summary || "")}</p>
      <p class="panelnote">Stamped onto this journal at creation${(S.journal || {}).created ? ` on ${esc(String(S.journal.created).slice(0, 10))}` : ""} — a journal has one strategy and it does not change.</p></div>
    ${limits}${declines}${states}${list}${inputs}${values}
    ${changeHistories()}${refused}`;
}
function neverSays(st) {
  const declared = new Set((st.states || []).map((x) => x.render));
  const never = Object.entries(S.render_types || {})
    .filter(([k, v]) => !declared.has(k) && !v.host_only);
  if (!never.length) return "";
  return `<div class="m-h" style="margin-top:1rem">What it will never say</div>
    ${never.map(([k, v]) => `<p class="panelnote">${esc(v.meaning || k)} — no state of this strategy renders as “${esc(k)}”.</p>`).join("")}`;
}
function declaredText(spec, value) {
  if (value === null || value === undefined || value === "") return "—";
  if (spec.type === "boolean") return value === true || value === "true" ? "Yes" : "No";
  const opt = (spec.options || []).find((o) => o.value === value);
  if (opt) return opt.label;
  return String(value) + (spec.unit ? ` ${spec.unit}` : "");
}

function changeHistories() {
  const rules = (S.rule_changes || []).slice().reverse();
  const meas = (S.measure_changes || []).slice().reverse();
  const ins = (S.input_changes || []).slice().reverse();
  const words = S.change_records || {};
  const explainBtn = (record, c) => c.reason
    ? `<div class="bline"><b>Why:</b> ${esc(c.reason)}</div>`
    : c.reason_owed
      ? `<div class="bline"><button class="link" data-m="explain" data-arg="${escAttr({ record, seq: c.seq })}">Write the reason</button></div>`
      : "";
  const section = (title, record, list, lineFn, always) => !list.length && !always ? "" : `
    <div class="panel"><h3>${esc(title)}</h3>
      <p class="panelnote">Append-only: entries are never edited, and a change made in the files is caught here the next time the journal opens.</p>
      ${list.length ? list.map((c) => `<div class="kv"><span class="k num">${esc(String(c.seen || "").slice(0, 10))}</span>
        <span class="v" style="text-align:left">${lineFn(c)}${explainBtn(record, c)}</span></div>`).join("")
      : '<p class="panelnote">Nothing has moved yet. The moment something does — through this app or by an edit to the files — it lands here, with what it was before.</p>'}</div>`;
  return section(`How the rules have moved`, "rules", rules, (c) => [
    ...(c.moved || []).map((m) => `<div class="bline">${esc(m.label || m.id)}: ${esc(fmtDefined(m.from))} → ${esc(fmtDefined(m.to))}</div>`),
    ...(c.changelog || []).map((line) => `<div class="bline dim">${esc(line)}</div>`),
    ...(c.notes || []).map((n) => `<div class="bline dim">${esc(n)}</div>`),
  ].join("") || `<div class="bline dim">${esc(c.kind || "recorded")}</div>`, true)
  + section(`How the measure definitions have moved`, "measures", meas, (c) => [
    ...(c.added || []).map((m) => `<div class="bline">${esc(m.name || m.id)} — added</div>`),
    ...(c.removed || []).map((m) => `<div class="bline">${esc(m.name || m.id)} — removed</div>`),
    ...(c.moved || []).map((m) => `<div class="bline">${esc(m.name || m.id)} · ${esc(m.field)}: ${esc(fmtDefined(m.from))} → ${esc(fmtDefined(m.to))}</div>`),
    ...(c.restated || []).map((m) => `<div class="bline">${esc(m.name || m.id)} · ${esc(m.field)} changed — not something this program can read back</div>`),
    ...(c.changelog || []).map((line) => `<div class="bline dim">${esc(line)}</div>`),
  ].join("") || `<div class="bline dim">first seen</div>`, true)
  + section(`How your answers have moved`, "inputs", ins, (c) => (c.moved || []).map((m) =>
    `<div class="bline">${esc(m.label || m.id)}: ${esc(fmtDefined(m.from))} → ${esc(fmtDefined(m.to))}</div>`).join(""));
}

/* ------------------------------------------------------------- measures */
let measureSearch = "";
function measuresView() {
  loadBankThen(() => { if (tab === "measures" && !openTicker) render(); });
  const cited = citedInJournal();
  const scoped = !showWholeBank;
  const all = C.bank || [];
  let entries = scoped ? all.filter((e) => cited.has(e.id)) : all;
  const q = measureSearch.trim().toLowerCase();
  if (q) {
    entries = entries.filter((e) => [e.id, e.label, e.kind, e.unit,
      (e.explanation || {}).plain, (e.explanation || {}).attribution,
      (e.derivation || {}).formula, e.question]
      .some((x) => String(x || "").toLowerCase().includes(q)));
  }
  const cards = !C.bank
    ? `<p class="quiet">${C.bankErr ? esc(C.bankErr) : "Reading the bank…"}</p>`
    : entries.length
      ? entries.map(bankCard).join("")
      : `<p class="quiet">${scoped ? "Nothing your strategy has read matches that." : "Nothing in the bank matches that."}</p>`;
  return banners() + `
    <div class="filters" style="padding-bottom:.2rem">
      <button class="${scoped ? "on" : ""}" data-act="bankscope" data-scope="cited">What this journal reads<span class="n">${cited.size}</span></button>
      <button class="${scoped ? "" : "on"}" data-act="bankscope" data-scope="all">The whole bank<span class="n">${all.length || (Object.keys(S.bank_meta || {}).length)}</span></button>
    </div>
    <p class="quiet">Definitions only — no thresholds live here. A limit belongs to your strategy and is read on its page.</p>
    <input class="search" id="banksearch" placeholder="Search by name, idea, or formula" value="${esc(measureSearch)}">
    <div>${cards}</div>`;
}
function bankCard(e) {
  const pol = e.polarity === "higher_is_better" ? "higher is better"
    : e.polarity === "lower_is_better" ? "lower is better"
    : "no favourable direction";
  const est = (e.estimator || {}).label || "";
  const nmw = (e.not_meaningful_when || []).length
    ? `<details><summary>When it refuses to compute</summary>${e.not_meaningful_when.map((c2) =>
        `<p>${esc(c2.states || c2.because || "")}${c2.because && c2.states ? ` — ${esc(c2.because)}` : ""}</p>`).join("")}</details>` : "";
  return `<div class="mcard">
    <div class="mc-head"><b>${esc(e.label || e.id)}</b>
      <span class="mc-meta"><code>${esc(e.id)}</code> · ${esc(e.kind || "")} · ${esc(pol)}${est ? " · " + esc(est) : ""}</span></div>
    ${(e.explanation || {}).plain ? `<p>${esc(e.explanation.plain)}</p>` : ""}
    ${e.question ? `<p><b>The question you answer:</b> ${esc(e.question)}</p>` : ""}
    ${(e.derivation || {}).formula ? `<pre>${esc(e.derivation.formula)}</pre>` : ""}
    ${(e.derivation || {}).window ? `<p class="panelnote">${esc(e.derivation.window)}</p>` : ""}
    ${nmw}
    ${(e.explanation || {}).misfires || (e.explanation || {}).attribution
      ? `<details><summary>Where it misfires · whose idea</summary>
         ${(e.explanation || {}).misfires ? prose(e.explanation.misfires) : ""}
         ${(e.explanation || {}).attribution ? prose(e.explanation.attribution) : ""}</details>` : ""}
  </div>`;
}

/* ----------------------------------------------------------------- data */
function dataView() {
  const sec = S.data_security || {};
  return banners() + `
    <div class="panel"><h3>Data sources</h3>
      <p>Filings come straight from SEC EDGAR; prices from Tiingo. Both need one-time setup, and neither can move money — the tool holds no broker credentials, ever.</p>
      <div class="kv"><span class="k">SEC identity</span><span class="v">${sec.sec_identity ? esc(sec.sec_identity) : '<span class="absent">not set</span>'}<small>Name and email, sent as the User-Agent the SEC asks for. Machine-only; never exported.</small></span></div>
      <div class="kv"><span class="k">Tiingo key</span><span class="v">${sec.key_configured ? "configured" : '<span class="absent">not set</span>'}<small>${esc(storageWords(sec.storage))}${sec.problem ? " — " + esc(sec.problem) : ""}</small></span></div>
      <button class="m-act quiet" data-m="sources" data-arg="{}">Set up data access</button>
      <p class="panelnote">Without a Tiingo key the tool cannot fetch prices and provides nothing — the free account at tiingo.com is enough.</p></div>
    <div class="panel"><h3>Valuation defaults</h3>
      <p>Prefill every expected-value calculation in this journal. Each one can be changed at the moment of use, and the value solved for is never typed.</p>
      ${["discount_rate", "terminal_growth", "margin_of_safety"].map((k) => {
        const v = ((S.journal || {}).settings || {})[k];
        const label = { discount_rate: "Discount rate", terminal_growth: "Terminal growth", margin_of_safety: "Margin of safety" }[k];
        return `<div class="kv"><span class="k"><button data-m="valdefaults" data-arg="{}">${label}</button></span><span class="v num">${v !== undefined && v !== null ? esc(String(v)) + "%" : "—"}</span></div>`;
      }).join("")}
      <button class="m-act quiet" data-m="valdefaults" data-arg="{}">Change these</button></div>
    <div class="panel"><h3>Back up</h3>
      <p>Everything you have recorded, exported to a folder you choose — positions, notes, history, journal configuration. Secrets are structurally outside the exported set and cannot be in it.</p>
      <button class="m-act quiet" data-act="export">Export a backup</button>
      <button class="m-act quiet" data-m="importdata" data-arg="{}">Import a backup</button></div>
    <div class="panel"><h3>Where your data lives</h3>
      <p class="num" style="font-size:.78rem">${esc(S.data_dir || "")}</p>
      <p class="panelnote">Outside the program’s own folder, never committed anywhere, never uploaded. Set <code>LEDGER_DATA</code> to move it.</p>
      <button class="m-act quiet" data-m="emptyjournal" data-arg="{}">Empty this journal</button></div>`;
}

/* ------------------------------------------------------------ analytics */
/* A tab of its own: not about one security, and not chrome — a reading
   surface about the journal, reached where the other screens are. */
function analyticsView() {
  const card = S.override_scorecard || {};
  const exits = S.exit_scorecard || {};
  const passed = S.pass_over_scorecard || {};
  const anything = (card.live || {}).n_purchases || (card.reconstructed || {}).n_purchases
    || Object.keys(exits).length || (passed.rows || []).length;
  const head = `<h2 class="sect">Looking back<span class="aside">how your decisions and your rules have actually done</span></h2>`;
  if (!anything) {
    return banners() + head + `<p class="quiet">Not enough history to mean anything yet. Once positions close and overrides age, this page reports both directions — your error rate against the rules, and the rules’ error rate against you. If overriding a particular rule keeps working out, that rule is miscalibrated; this page is where you would find out.</p>`;
  }
  const signed = (v) => v === null || v === undefined ? "—"
    : `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)}%`;
  /* Cohort labels are the host's — "seen at the time" against
     "reconstructed" is the line the engine draws, in its words. */
  const cohort = (c, label) => !c || !c.n_purchases ? "" : `
    <div class="kv"><span class="k">${esc(cap(label || ""))}</span><span class="v">
      ${c.n_purchases} purchase${c.n_purchases === 1 ? "" : "s"} · scored ${c.n ?? "—"} of ${c.n_purchases}
      ${c.win_rate !== undefined && c.win_rate !== null ? ` · win rate ${esc(String(c.win_rate))}%` : ""}
      ${c.avg !== undefined && c.avg !== null ? ` · avg ${signed(c.avg)}` : ""}
      ${(c.unscored || []).length ? `<small>${c.unscored.map(esc).join(" · ")}</small>` : ""}</span></div>`;
  const sides = (side, label) => `
    <div class="panel"><h3>${esc(label)}</h3>
      ${cohort((card.live || {})[side], (card.live || {}).label)}
      ${cohort((card.reconstructed || {})[side], (card.reconstructed || {}).label)}
      ${!((card.live || {})[side] || {}).n_purchases && !((card.reconstructed || {})[side] || {}).n_purchases
        ? '<p class="panelnote">Nothing in this cohort yet.</p>' : ""}</div>`;
  const unrecon = (card.unreconstructed || {}).n_purchases ? `
    <div class="panel"><h3>Could not be reconstructed</h3>
      <p>${card.unreconstructed.n_purchases} purchase${card.unreconstructed.n_purchases === 1 ? "" : "s"} whose day no verdict could be rebuilt for. Counted in neither comparison — there was no signal to obey or defy.</p></div>` : "";
  const perRule = ["live", "reconstructed"].flatMap((k) =>
    Object.values(((card[k] || {}).per_rule) || {}).map((r2) =>
      `<div class="kv"><span class="k">${esc(r2.label || "")}</span><span class="v">
        ${esc(String(r2.wins ?? "—"))} of ${esc(String(r2.n_scored ?? "—"))} overrides worked out
        ${r2.n_scored !== r2.n ? ` · of ${esc(String(r2.n))} in all` : ""}
        · avg ${signed(r2.avg)}
        <small>${esc(cap((card[k] || {}).label || k))}</small></span></div>`)).join("");
  const exitRows = Object.entries(exits).map(([reason, x]) => `
    <div class="kv"><span class="k">${esc(reason)}</span><span class="v">
      ${x.n ?? "—"} exit${x.n === 1 ? "" : "s"}
      ${x.avg_held !== undefined && x.avg_held !== null ? ` · held avg ${signed(x.avg_held)}` : ""}
      ${x.avg_after !== undefined && x.avg_after !== null ? ` · after avg ${signed(x.avg_after)}` : ""}
      ${(x.against || {}).n ? `<small>${x.against.n} of these went against the signal${x.against.avg_after !== null && x.against.avg_after !== undefined ? ` — after avg ${signed(x.against.avg_after)}` : ""}</small>` : ""}
      ${x.bought_again ? `<small>${x.bought_again} bought again — the after-window stops at your re-purchase</small>` : ""}</span></div>`).join("");
  const passRows = (passed.rows || []).map((p) => `
    <div class="kv"><span class="k">${esc(p.ticker)}</span><span class="v">
      ${p.pct !== undefined && p.pct !== null ? `${p.pct >= 0 ? "+" : "−"}${Math.abs(p.pct).toFixed(1)}% since declining` : `<small>${esc(p.reason || "not scored")}</small>`}
      ${p.later_bought ? "<small>later bought</small>" : ""}</span></div>`).join("");
  return banners() + head
    + sides("override", "Purchases against the signal")
    + sides("compliant", "Purchases with it")
    + unrecon
    + (perRule ? `<div class="panel"><h3>Rules you overrode</h3><p class="panelnote">If overriding one keeps working out, the rule is miscalibrated — not you. That is what this table exists to catch.</p>${perRule}</div>` : "")
    + (exitRows ? `<div class="panel"><h3>By why you sold</h3><p class="panelnote">What the price did after each kind of exit is how sell rules are graded. It is never a “you could have made” figure.</p>${exitRows}</div>` : "")
    + (passRows ? `<div class="panel"><h3>Names you passed over</h3>${passRows}</div>` : "");
}

/* -------------------------------------------------------------- welcome */
let chosenStrategy = null;
function welcomeView() {
  const offers = S.strategies || [];
  const sec = S.data_security || {};
  const journals = (S.journals || []).length ? `
    <div class="panel"><h3>Your journals</h3>
      ${S.journals.map((j) => `<div class="kv"><span class="k">${esc(j.name)}</span>
        <span class="v"><button class="m-act quiet" data-act="openjournal" data-id="${esc(j.id)}">Open</button></span></div>`).join("")}</div>` : "";
  const cards = offers.map((o) => `
    <div class="stratcard ${chosenStrategy === o.id ? "on" : ""}" data-act="choosestrategy" data-id="${esc(o.id)}">
      <b>${esc(o.name)}</b> <span class="dim">v${esc(o.version)}</span>
      <p>${esc(o.summary || "")}</p>
      ${(o.limits || []).length ? `<p class="sc-meta">${o.limits.map((l) => esc(l.title)).join(" · ")}</p>` : ""}
      ${(o.declines || []).length ? `<p class="sc-meta">Will not evaluate: ${o.declines.map((d2) => esc(d2.label || d2.class)).join(", ")}</p>` : ""}
      ${o.list ? `<p class="sc-meta">Works from a list you import — ${esc(sourceName(o.list.source))}</p>` : ""}
    </div>`).join("");
  const chosen = offers.find((o) => o.id === chosenStrategy) || null;
  const inputFields = chosen ? (chosen.inputs || []).filter((f) => f.answered_by !== "host").map((f) =>
    declaredField(f, undefined, "in_")).join("") : "";
  return banners() + `<div class="steps">
    <h1>Ledger</h1>
    <p>An investment journal that holds you to a strategy you commit to while calm. It reads public filings and prices, tells you what your own rules say about a security today, and records every decision — including the ones made against them. It never trades and it never advises.</p>
    ${journals}
    <div class="step"><div class="sn">Step 1</div><h3>Pick a strategy</h3>
      <p>A journal has exactly one strategy, chosen now and never changed — that is the discipline, not a limitation. Trading two strategies means two journals, the way it would mean two accounts.</p>
      ${cards || '<p class="quiet">No strategy would load. The strategies folder is empty or every bundle was refused.</p>'}
      ${(S.refused || []).length ? `<p class="panelnote">Would not load: ${S.refused.map((r) => esc(r.name || r.bundle)).join(", ")}</p>` : ""}</div>
    <div class="step"><div class="sn">Step 2</div><h3>Name it, and say what is in the account</h3>
      <div class="field"><label>Journal name</label><input name="w_name" placeholder="e.g. Long-term account"></div>
      <div class="m-row"><div><label>Cash in the account now</label><input name="w_cash" type="number" placeholder="e.g. 25000"></div>
      <div><label>As of</label><input name="w_cash_on" type="date" value="${esc(localToday())}" max="${esc(localToday())}"></div></div>
      ${inputFields}
      <p class="panelnote" style="margin-top:.6rem">Anything you already own is entered after the journal opens — add each security and enter its history from your records. Those holdings are then evaluated for <b>exit</b>, not entry: the buy decision is behind them, and the verdicts you will see are about whether to stay.</p></div>
    <div class="step"><div class="sn">Step 3</div><h3>Data access</h3>
      <p>Both are required — without them the tool cannot fetch and provides nothing.</p>
      <div class="m-row"><div><label>Your name and email <small>(the User-Agent the SEC asks for)</small></label>
        <input name="w_sec" placeholder="Jane Doe jane@example.com" value="${esc(sec.sec_identity || "")}"></div></div>
      <div class="m-row"><div><label>Tiingo API key <small>(free at tiingo.com — the tool only ever reads prices with it)</small></label>
        <input name="w_key" type="password" placeholder="${sec.key_configured ? "already configured" : "paste the key"}"></div></div>
      <p class="panelnote">${sec.key_configured ? "A key is already stored" : "Stored in the OS credential store"} — never shown, never exported, never logged.</p></div>
    <button class="m-act" data-act="createjournal" style="margin-top:1.1rem">Start the journal</button>
    <div class="m-err" id="w_err" style="display:none"></div>
  </div>`;
}

/* A declared field, built from the strategy's own declaration. */
function declaredField(spec, value, prefix) {
  const name = prefix + spec.id;
  const gate = spec.when
    ? ` data-gate="${esc(prefix + spec.when.input)}" data-gate-is="${esc(JSON.stringify(spec.when.is))}"` : "";
  let control;
  if ((spec.options || []).length) {
    control = `<select name="${name}">${spec.required ? "" : '<option value="">Not answered</option>'}
      ${spec.options.map((o) => `<option value="${esc(o.value)}" ${o.value === value ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`;
  } else if (spec.type === "boolean") {
    control = `<select name="${name}">${spec.required ? "" : '<option value="">Not answered</option>'}
      <option value="false" ${value === false ? "selected" : ""}>No</option>
      <option value="true" ${value === true ? "selected" : ""}>Yes</option></select>`;
  } else if (spec.type === "number" || spec.type === "integer") {
    const bounds = (spec.min !== undefined ? ` min="${esc(spec.min)}"` : "")
      + (spec.max !== undefined ? ` max="${esc(spec.max)}"` : "");
    control = `<input name="${name}" type="number" step="${spec.type === "integer" ? "1" : "any"}"${bounds} value="${esc(value ?? "")}">`;
  } else {
    control = `<input name="${name}" type="text" value="${esc(value ?? "")}">`;
  }
  return `<div class="field"${gate}><label>${esc(spec.label)}${spec.required ? "" : " (optional)"}${spec.unit ? ` <small>(${esc(spec.unit)})</small>` : ""}</label>
    ${control}<div class="panelnote">${esc(spec.explain || "")}</div></div>`;
}
/* A question whose gate is unmet is hidden rather than asked. The answer is
   still sent — the backend is the authority on which answers apply. */
function applyGates(root) {
  root.querySelectorAll("[data-gate]").forEach((el) => {
    const on = root.querySelector(`[name="${el.dataset.gate}"]`);
    let want;
    try { want = JSON.parse(el.dataset.gateIs); } catch (e) { want = null; }
    const answer = on ? String(on.value) : "";
    const opens = Array.isArray(want) ? want.map(String).includes(answer)
      : want !== null && want !== undefined ? String(want) === answer : false;
    el.hidden = !opens;
  });
}
