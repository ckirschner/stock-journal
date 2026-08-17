/* Acting happens in the margin, with today's verdict pinned on top. Every
   door — a row, the detail page, the allocation note — leads to the same
   pane, which is how "every door leads to one place" is kept.

   Nothing here blocks a recording, ever. Where an action goes against the
   signal, the one piece of mandatory friction in the program is a written
   sentence — and it does not move. */

/* ------------------------------------------------------------------ buy */
PANES.buy = (a) => paneBuy(a.t, a.when, a.keep, a.fallback);
async function paneBuy(ticker, dateChosen, keep, fallbackDate) {
  const s = find(ticker);
  if (!s) return PANES.rest();
  const today = localToday();
  const when = dateChosen || today;
  const p = await apiRaw("preview_purchase", ticker, when);
  if (!p.ok) {
    if (fallbackDate) return paneBuy(ticker, fallbackDate, keep);
    return `<p class="m-kicker">Record a purchase · ${esc(ticker)}</p>
      <h3>The preview could not be built</h3><p>${esc(p.error)}</p>`;
  }
  const d = p.decision;
  /* Which of the four ways this would go on the record, from the engine
     alone. The dialog never works it out again from the render — a second
     copy of that judgement is how a dialog and the entry it wrote once came
     to disagree about the same purchase. */
  const asRecorded = p.recorded_as;
  const noVerdict = asRecorded === "without";
  const cannotRebuild = asRecorded === "unreconstructed";
  const bad = asRecorded === "against" || asRecorded === "without";
  const who = (d.strategy || {}).name || "Your strategy";
  const recon = p.basis === "reconstructed";
  const back = s.bucket === "previous";

  const verdictBox = `<p><span class="state ${stateClass(d)}">${esc((d.state || {}).name || "")}</span>
    ${recon ? ` <span class="dim">— rebuilt for ${esc(p.as_of || when)}</span>` : ""}</p>
  <p>${esc((d.reason || {}).summary || "")}</p>`;
  const reconBox = recon ? `<div class="m-note"><b>From history — not seen at the time.</b>
    ${esc(when)} is in the past, so the state above is rebuilt from what was observable then${p.note ? `: ${esc(p.note)}` : ""}. It is recorded as a reconstruction, distinct everywhere from a state you saw at the time.</div>` : "";
  const darkBox = cannotRebuild ? `<div class="m-note"><b>No verdict could be rebuilt for ${esc(when)}.</b>
    Nothing is recorded about what your rules would have said, and this purchase is <b>not</b> counted as buying against a signal — there was none to go against. That distinction is what makes the override record mean anything.</div>` : "";
  const warnBox = bad ? `<div class="m-err"><strong>${esc(who)}</strong> has not said to ${back || s.bucket === "holdings" ? "add" : "buy"}.
    ${noVerdict ? "There is no verdict here to go against — which is its own kind of override, and is recorded as one." : "Buying now goes against your own rules."}
    Nothing here stops you; it asks one sentence.</div>` : "";

  const th = p.thesis || {};
  const pv = p.valuation || {};
  const thesisBox = th.status === "known"
    ? `<details><summary>Buying on your written case of ${esc(th.amended || "")}${(th.cautions || []).length ? " — qualified" : ""}</summary>
       ${prose((th.version || {}).thesis)}
       ${(th.version || {}).falsifier ? `<div class="m-h">What would make me wrong</div>${prose(th.version.falsifier)}` : ""}
       ${mCautions(th.cautions)}
       ${pv.status === "known" ? `<p class="m-quiet">A valuation claim of ${esc((pv.claim || {}).made || "")} is frozen with it.</p>`
         : '<p class="m-quiet">No valuation is on record for this day, so this purchase records none.</p>'}
       <p class="m-quiet">This version is frozen onto the purchase. To change it, amend “Why I own this” first — nothing here edits it.</p></details>`
    : `<p class="m-quiet">Nothing under “Why I own this” is on record${recon ? ` for ${esc(when)}` : ""} — ${esc(th.reason || "nothing is written yet")}. The purchase records that. Nothing here stops you.</p>`;

  return `<p class="m-kicker">Record a purchase · ${esc(ticker)}</p>
<h3>Today’s verdict is in front of you</h3>
${verdictBox}${reconBox}${darkBox}${warnBox}${thesisBox}
${back ? `<p class="m-quiet">You held ${esc(ticker)} before and closed it. This starts a new holding, judged from scratch.</p>` : ""}
<div class="m-row"><div><label>Shares</label><input name="shares" type="number" value="${esc((keep || {}).shares || "")}"></div>
<div><label>Cost per share</label><input name="cost" type="number" placeholder="what you actually paid" value="${esc((keep || {}).cost || "")}"></div></div>
<label>Date</label><input name="opened" id="buy_date" type="date" value="${esc(when)}" max="${esc(today)}">
${bad ? `<label>${noVerdict ? "Why are you buying without a signal?" : "Why are you buying anyway?"} <small>Required. One sentence. You will read this again later.</small></label>
<textarea name="override_reason" rows="3">${esc((keep || {}).override_reason || "")}</textarea>` : ""}
${recon && th.status !== "known" ? `<label>What do you remember thinking? <small>Optional — written now, about then, and recorded as exactly that.</small></label>
<textarea name="recollection" rows="2">${esc((keep || {}).recollection || "")}</textarea>` : ""}
<button class="m-act ${bad ? "warn" : ""}" data-do="buy" data-t="${esc(ticker)}" data-state="${esc((d.state || {}).id || "")}" data-bad="${bad ? "1" : ""}">${bad ? "Record anyway" : "Record the purchase"}</button>
<p class="m-quiet">This records what you already did; the tool cannot place trades.</p>`;
}
async function doBuy(btn) {
  const f = marginForm();
  const bad = btn.dataset.bad === "1";
  if (!f.shares || !f.cost) return marginErr("Shares and cost per share are required.");
  if (bad && !(f.override_reason || "").trim())
    return marginErr("A reason is required when the strategy doesn’t say to commit.");
  const r = await api("open_position", btn.dataset.t, f.shares, f.cost, f.opened,
    f.override_reason || "", btn.dataset.state || null, f.recollection || "");
  if (!r) return;
  if (r.state_changed) {
    toast(`The state changed to ${r.state} between preview and record (data or the strategy moved). It is recorded under the new state${r.override ? " as an override — add a note with your reasoning" : ""}.`, !r.commit);
  } else if (r.unreconstructed) {
    toast(`Recorded from history, dated ${f.opened}. No verdict could be rebuilt for that day, so none is recorded — and this is not counted as buying against a signal.`);
  } else if (r.basis === "reconstructed") {
    toast(`Recorded from history, dated ${f.opened}. The verdict beside it was rebuilt from that day’s data, and says so wherever it appears.`);
  }
  openSecurity(btn.dataset.t);
  await refresh(); refreshTimeframe();
  marginRest();
}

/* ----------------------------------------------------------------- sell */
PANES.sell = (a) => paneSell(a.t, a.when, a.keep, a.fallback);
async function paneSell(ticker, dateChosen, keep, fallbackDate) {
  const s = find(ticker);
  if (!s) return PANES.rest();
  const today = localToday();
  const when = dateChosen || today;
  const past = when < today;
  const reply = await apiRaw("preview_sale", ticker, when);
  if (!reply.ok && past) {
    if (fallbackDate) return paneSell(ticker, fallbackDate, keep);
    return `<p class="m-kicker">Record a sale · ${esc(ticker)}</p>
      <h3>That day could not be read</h3><p>${esc(reply.error)}</p>`;
  }
  /* Today's preview failing must not stop a sale being recorded — the live
     payload IS today, so the figures are the same figures. */
  const p = reply.ok ? reply : {
    recorded_as: null, reason_owed: false, held: s._shares,
    lots: buyLots(s).filter((l) => l.open).map((l) => ({ date: l.date, remaining: l.remaining })),
    price: (s._price || {}).value != null
      ? { status: "known", value: s._price.value, date: s._price.date, source: s._price.source, terminal: s._price.terminal }
      : { status: "absent", reason: (s._price || {}).reason || "no price is on record" },
  };
  const owed = !!p.reason_owed;
  const verdict = p.decision || {};
  const who = ((verdict || {}).strategy || {}).name || "Your strategy";
  const verdictBox = verdict.state
    ? `<p><span class="state ${stateClass(verdict)}">${esc((verdict.state || {}).name || "")}</span>${past ? ` <span class="dim">— rebuilt for ${esc(when)}</span>` : ""}</p>
       <p>${esc(((verdict || {}).reason || {}).summary || "")}</p>` : "";
  const againstBox = owed ? `<div class="m-err"><strong>${esc(who)}</strong> has no rule calling for this exit.
    Selling now goes against your own rules; the record will say so, with your reason.</div>` : "";
  const reconBox = past ? `<div class="m-note"><b>From history — not seen at the time.</b>
    What gets frozen beside this sale is rebuilt from what was observable on ${esc(when)}${p.note ? `: ${esc(p.note)}` : ""}.
    ${p.verdict ? "" : "No verdict could be rebuilt for that day, so none is recorded against this sale — it will not read as an exit your rules called for, nor as one they stayed silent on."}</div>` : "";
  const quote = p.price || {};
  const closeNote = quote.status === "known" && quote.source === "fetched" && quote.date
    ? `For reference, the close on record for ${esc(quote.date)} was ${money(quote.value)}${quote.terminal ? " — the last this security ever traded at" : ""}.`
    : past ? `No close is on record for ${esc(when)}: ${esc(quote.reason || "none was stored for that day")}.` : "";
  const lots = p.lots || [];
  const lotHelp = lots.length > 1
    ? ` Oldest shares go first, across ${lots.length} open lots (${lots.map((l) => `${l.remaining} from ${l.date}`).join(", ")}).` : "";
  const opts = [...(S.exit_reasons || []).map((r) => `<option value="${esc(r)}" ${(keep || {}).reason === r ? "selected" : ""}>${esc(r)}</option>`),
    past ? '<option value="">I do not remember</option>' : ""].join("");
  return `<p class="m-kicker">Record a sale · ${esc(ticker)}</p>
<h3>Today’s verdict is in front of you</h3>
${verdictBox}${reconBox}${againstBox}
<label>Why are you selling?</label>
<select name="reason">${opts}</select>
<p class="m-quiet">Answer honestly — outcomes are grouped by this, and it is the only way to find out whether your sell rules work.</p>
<label>Shares sold <small>— ${past ? `you held ${esc(String(p.held))} on ${esc(when)}` : `you hold ${esc(String(p.held))}`}. Sell fewer to trim; a trim reads as “Sell — trim” and goes down the same path.${esc(lotHelp)}</small></label>
<input name="shares" type="number" value="${esc((keep || {}).shares || String(p.held ?? ""))}">
<label>Sale price per share <small>— never prefilled; a number off the tape is not the number you got. ${closeNote}</small></label>
<input name="price" type="number" value="${esc((keep || {}).price || "")}">
<label>Date</label><input name="exited" id="sell_date" type="date" value="${esc(when)}" max="${esc(today)}">
${owed ? `<label>Why, in your own words? <small>Required when no rule called for it — the record you will most want to read back.</small></label>
<textarea name="override_reason" rows="3">${esc((keep || {}).override_reason || "")}</textarea>` : ""}
<button class="m-act warn" data-do="sell" data-t="${esc(ticker)}" data-owed="${owed ? "1" : ""}" data-state="${esc(((verdict || {}).state || {}).id || "")}">${owed ? "Record it anyway" : "Record the sale"}</button>`;
}
async function doSell(btn) {
  const f = marginForm();
  if (!f.price) return marginErr("A sale price is required.");
  if (!f.shares) return marginErr("How many shares were sold?");
  if (btn.dataset.owed === "1" && !(f.override_reason || "").trim())
    return marginErr("A reason is required when you are selling against your strategy.");
  const r = await api("sell_shares", btn.dataset.t, f.reason, f.price, f.exited,
    f.shares, f.override_reason || "", btn.dataset.state || null);
  if (!r) return;
  if (r.state_changed) {
    toast(`The verdict changed between the preview and the record. The sale is recorded ${r.recorded_as === "against" ? "as going against the signal" : "under the new verdict"}${r.override && !r.reason_given ? " — with no reason on it, because you were not asked for one. Add a note if you want one there." : ""}.`, r.override && !r.reason_given);
  } else if (r.remaining > 0) {
    toast(`Recorded. ${r.remaining} shares still held; the lots they came from are unchanged.`);
  }
  await refresh(); refreshTimeframe();
  marginRest();
}

/* ------------------------------------------------------------- backfill */
PANES.backfill = (a) => paneBackfill(a.t, a.state);
function bfRowHtml(r, i) {
  const sellReason = r.kind === "sell"
    ? `<select name="bf_reason_${i}">${(S.exit_reasons || []).map((x) =>
        `<option value="${esc(x)}" ${r.reason === x ? "selected" : ""}>${esc(x)}</option>`).join("")}
        <option value="" ${!r.reason ? "selected" : ""}>I do not remember</option></select>` : "";
  return `<div class="m-note" data-bfrow="${i}">
    <b>${r.kind === "buy" ? "Purchase" : "Sale"}</b>
    <button class="m-close" style="position:static;float:right" data-bfdel="${i}">✕</button>
    <input type="hidden" name="bf_kind_${i}" value="${esc(r.kind)}">
    <div class="m-row"><div><label>Date</label><input name="bf_date_${i}" type="date" value="${esc(r.date || "")}" max="${esc(localToday())}"></div>
    <div><label>Shares</label><input name="bf_shares_${i}" type="number" value="${esc(r.shares || "")}"></div></div>
    <label>Price per share</label><input name="bf_price_${i}" type="number" value="${esc(r.price || "")}">
    ${r.kind === "sell" ? `<label>Why you sold</label>${sellReason}` : ""}
    ${r.outcome ? `<p class="m-quiet">${esc(r.outcome)}</p>` : ""}
  </div>`;
}
function paneBackfill(ticker, st) {
  const s = find(ticker);
  if (!s) return PANES.rest();
  const state = st || { rows: [{ kind: "buy", date: "", shares: "", price: "" }], preview: null, recollection: "" };
  const checked = state.preview;
  const outcomes = checked ? (checked.events || []) : [];
  const rows = state.rows.map((r, i) => {
    const o = outcomes.find((x) => x.index === i);
    return bfRowHtml({ ...r, outcome: o ? bfOutcomeText(o) : null }, i);
  }).join("");
  const problem = checked && checked.problem
    ? `<div class="m-err">${esc(checked.problem)}${(checked.unchecked || []).length ? ` — ${checked.unchecked.length} later entr${checked.unchecked.length === 1 ? "y was" : "ies were"} not checked.` : ""}</div>` : "";
  const firstIsPastBuy = state.rows[0] && state.rows[0].kind === "buy" && state.rows[0].date && state.rows[0].date < localToday();
  return `<p class="m-kicker">Enter history · ${esc(ticker)}</p>
<h3>From your own records</h3>
<p>Positions you already own enter here — each day’s verdict is rebuilt from that day’s data and frozen beside the entry, marked as a reconstruction everywhere it appears. These holdings are then evaluated for <b>exit</b>, not entry: the buy decision is behind them.</p>
${problem}${rows}
<p><button class="m-act quiet" data-bfadd="buy">Add a purchase</button>
<button class="m-act quiet" data-bfadd="sell">Add a sale</button></p>
${firstIsPastBuy && !((s._thesis || {}).status === "known") ? `<label>What do you remember thinking? <small>Optional — attached to the first purchase, dated today, never counted as the case made at the time.</small></label>
<textarea name="bf_recollection" rows="2">${esc(state.recollection || "")}</textarea>` : ""}
${checked && !checked.problem
    ? `<p class="m-quiet">Checked — nothing recorded yet. Recording writes all ${state.rows.length} entr${state.rows.length === 1 ? "y" : "ies"} at once, or none.</p>
       <button class="m-act" data-do="bfrecord" data-t="${esc(ticker)}">Record ${state.rows.length} entr${state.rows.length === 1 ? "y" : "ies"}</button>`
    : `<button class="m-act" data-do="bfcheck" data-t="${esc(ticker)}">Check these entries</button>
       <p class="m-quiet">Nothing is recorded before it has been checked.</p>`}`;
}
function bfOutcomeText(o) {
  if (o.problem) return o.problem;
  const basis = o.recorded_as === "unreconstructed"
    ? "no verdict to rebuild — not an override"
    : o.basis === "reconstructed" ? "rebuilt for its day" : "seen live";
  return `${o.state || "no state"} · ${basis}${o.summary ? ` — ${o.summary}` : ""}`;
}
function bfRead() {
  const rows = [];
  document.querySelectorAll("[data-bfrow]").forEach((el) => {
    const i = el.dataset.bfrow;
    const get = (n) => { const f = el.querySelector(`[name="bf_${n}_${i}"]`); return f ? f.value : ""; };
    rows.push({ kind: get("kind"), date: get("date"), shares: get("shares"),
      price: get("price"), reason: get("reason") });
  });
  const rec = document.querySelector('[name="bf_recollection"]');
  return { rows, recollection: rec ? rec.value : "" };
}
async function doBackfill(btn, commit) {
  const { rows, recollection } = bfRead();
  if (!rows.length) return marginErr("Nothing to check yet.");
  const method = commit ? "record_backfill" : "preview_backfill";
  const r = await apiRaw(method, btn.dataset.t, rows, recollection);
  if (!r.ok) return marginErr(r.error);
  if (commit) {
    toast(`Recorded ${rows.length} entr${rows.length === 1 ? "y" : "ies"} from history.`);
    await refresh(); refreshTimeframe();
    marginRest();
    return;
  }
  margin("backfill", { t: btn.dataset.t, state: { rows, recollection, preview: r } });
}

/* ------------------------------------------------------- expected value */
PANES.ev = (a) => paneEV(a.t, a.method, a.keep);
async function paneEV(ticker, methodOverride, keep) {
  const s = find(ticker);
  if (!s) return PANES.rest();
  const pf = await apiRaw("ev_prefill", ticker);
  const prefill = pf.ok ? (pf.prefill || {}) : {};
  const refs = pf.ok ? (pf.references || {}) : {};
  const v = s._valuation || {};
  const standing = v.status === "known" ? v.claim : null;
  const methods = S.ev_methods || {};
  const method = methodOverride || (standing || {}).method
    || ((S.journal || {}).settings || {}).default_ev_method
    || Object.keys(methods)[0];
  const spec = methods[method] || {};
  const seed = keep || (standing && standing.method === method ? standing.inputs : {}) || {};
  const defaults = (S.journal || {}).settings || {};
  /* Each declared input is [id, label, help] — from the method's own
     declaration, never a list kept here. Prefills come from the backend
     with their provenance; the journal's valuation defaults seed the three
     assumptions they exist for; a typed override replaces either, visibly. */
  const inputs = (spec.inputs || []).map((f) => {
    const [id, label, help] = f;
    const got = prefill[id];
    const known = got && (got.status === "computed" || got.status === "known");
    const dflt = { discount_rate: defaults.discount_rate,
      terminal_growth: defaults.terminal_growth,
      margin_of_safety: defaults.margin_of_safety }[id];
    const val = seed[id] !== undefined ? seed[id]
      : known ? got.value
      : dflt !== undefined && dflt !== null ? dflt : "";
    const src = known
      ? `<small>${esc((got.provenance || [])[0] || `prefilled${got.asof ? ` as of ${got.asof}` : ""}`)}</small>`
      : got && got.status === "absent" && got.reason
        ? `<small>not prefilled — ${esc(oneline(got.reason))}</small>`
        : dflt !== undefined && dflt !== null && val === dflt
          ? "<small>your journal default</small>" : "";
    /* The method's own declared references render under the input they
       belong to, with the declared labels — never a label invented from an
       id, and never a reference the method did not ask to show. */
    const refRows = ((spec.references || {})[id] || []).map(([rid, rlabel]) => {
      const rgot = refs[rid];
      const ok2 = rgot && (rgot.status === "computed" || rgot.status === "known");
      return `<tr><td>${esc(rlabel)}</td><td class="num">${ok2
        ? esc(String(rgot.value)) + "M"
        : `<span class="absent" title="${esc((rgot || {}).reason || "")}">not known</span>`}</td></tr>`;
    }).join("");
    return `<label>${esc(label || id)} ${src}</label>
      <input name="ev_${id}" type="number" step="any" value="${esc(val)}">
      ${known ? mCautions(got.cautions) : ""}
      ${help ? `<p class="m-quiet">${esc(help)}</p>` : ""}
      ${refRows ? `<table class="m-series">${refRows}</table>` : ""}`;
  }).join("");
  const standingBox = standing
    ? `<p class="m-quiet">A ${esc((methods[standing.method] || {}).label || standing.method)} claim of ${esc((v.claim || {}).made || "")} is standing${v.result ? ` — ${esc(v.result.label || "")} ${esc(v.result.display || "")}` : ""}. Recording with different assumptions appends a new claim above it.</p>` : "";

  return `<p class="m-kicker">Expected value · ${esc(ticker)}</p>
<h3>${esc(spec.label || "Value it")}</h3>
${spec.blurb || spec.explain ? `<p>${esc(spec.blurb || spec.explain)}</p>` : ""}
<p class="m-quiet">You enter assumptions; the value is solved for. There is no field anywhere that accepts a target price — when an estimate turns out wrong, you can see which assumption was.</p>
${!pf.ok ? `<div class="m-err">Prefills could not be read: ${esc(pf.error)}. Typed values are recorded without a note of where they came from.</div>` : ""}
${standingBox}
<label>Method</label>
<select name="ev_method" id="ev_method">${Object.entries(methods).map(([id, m]) =>
    `<option value="${esc(id)}" ${id === method ? "selected" : ""}>${esc(m.label || id)}</option>`).join("")}</select>
${inputs}
<button class="m-act" data-do="ev" data-t="${esc(ticker)}">Record the claim</button>
<p class="m-quiet">Assumptions identical to the standing claim record nothing — a claim is a change of mind, not a bookmark.</p>`;
}
async function doEV(btn) {
  const f = marginForm();
  const method = f.ev_method;
  const inputs = {};
  Object.entries(f).forEach(([k, v2]) => {
    if (k.startsWith("ev_") && k !== "ev_method" && v2 !== "") inputs[k.slice(3)] = v2;
  });
  const r = await apiRaw("record_valuation", btn.dataset.t, method, inputs);
  if (!r.ok) return marginErr(r.error);
  toast(r.recorded ? "Claim recorded." : "Nothing recorded — the assumptions match the standing claim.");
  await refresh();
  margin("ev", { t: btn.dataset.t });
}

/* ------------------------------------------------------- edit values */
PANES.values = (a) => {
  const s = find(a.t);
  if (!s) return PANES.rest();
  const rows = (s._inputs || []).map((r) => {
    const c = (s._computed || {})[r.id] || {};
    const computedLine = c.status === "computed" || c.status === "known"
      ? `<small>computed: ${boundWord(c)}${esc(fmtMetric(r.id, c.value))}</small>`
      : c.status === "inapplicable" ? `<small>not applicable — ${esc(oneline(c.reason || ""))}</small>`
      : c.reason ? `<small>not computed — ${esc(oneline(c.reason))}</small>` : "";
    const entered = r.entered || {};
    const enteredLine = entered.status === "known"
      ? `<small>${esc((entered.provenance || [])[0] || "entered by hand")}</small>` : "";
    const val = entered.status === "known" ? entered.value : "";
    /* A figure about to be overridden is being acted on, so what qualifies
       it sits inline here rather than behind the mark. */
    return `<label>${esc(r.label || labelOf(r.id))}${r.cited ? "" : " <small>(not currently read by the strategy)</small>"} ${computedLine}${enteredLine}</label>
      ${mCautions(c.cautions)}
      <input name="mx_${r.id}" type="number" step="any" value="${esc(val)}" ${c.status === "inapplicable" ? "disabled" : ""}>`;
  }).join("");
  const p = s._price || {};
  return `<p class="m-kicker">Edit values · ${esc(a.t)}</p>
<h3>Typed figures</h3>
<p>A typed value is dated, kept, and beats a fetched one until you clear it. Blank withdraws — never zero, which would be a confident answer.</p>
<label>Price <small>${p.source === "fetched" && p.value != null ? `— the fetched close is ${money(p.value)} (${esc(p.date || "")}); typing here overrides it` : "— what you see quoted, undated by nature"}</small></label>
<input name="mx__price" type="number" step="any" value="${esc(p.source === "manual" ? p.value : "")}">
${rows || '<p class="m-quiet">The strategy has cited no measure for this security yet; measures appear here once one is cited or entered.</p>'}
<button class="m-act" data-do="values" data-t="${esc(a.t)}">Save</button>`;
};
async function doValues(btn) {
  const f = marginForm();
  const metrics = {};
  let price = null;
  Object.entries(f).forEach(([k, v]) => {
    if (k === "mx__price") price = v === "" ? "" : v;
    else if (k.startsWith("mx_")) metrics[k.slice(3)] = v;
  });
  const r = await apiRaw("save_metrics", btn.dataset.t, metrics, price);
  if (!r.ok) return marginErr(r.error);
  await refresh(); refreshTimeframe();
  margin("price", { t: btn.dataset.t });
}

/* ------------------------------------------------------------ judgement */
PANES.judgement = (a) => {
  const s = find(a.t);
  const j = s && (s._judgements || []).find((x) => x.id === a.id);
  if (!j) return PANES.rest();
  const meta = bankMeta(a.id) || {};
  const prior = j.mark
    ? `<div class="m-note"><b>${esc(MARK_WORD[j.mark] || j.mark)}</b> · ${esc(String(j.recorded || "").slice(0, 10))}${j.reasoning ? `<br>${esc(j.reasoning)}` : ""}</div>` : "";
  /* The earlier assessments an append-only record keeps — the whole reason
     for keeping them, and invisible if only the newest renders. Each shows
     the question as it was asked THEN, where the wording has moved. */
  const earlier = (j.history || []).slice(j.mark ? 1 : 0);
  const history = earlier.length
    ? `<details><summary>${earlier.length} earlier assessment${earlier.length === 1 ? "" : "s"}</summary>${earlier.map((h) =>
        `<div class="m-note"><b>${esc(MARK_WORD[h.mark] || h.mark || "unmarked")}</b> · ${esc(String(h.recorded || "").slice(0, 10))}${
          h.reasoning ? `<br>${esc(h.reasoning)}` : ""}${
          h.asked && h.asked !== j.asks ? `<br><span class="dim">Asked then: ${esc(h.asked)}</span>` : ""}</div>`).join("")}</details>` : "";
  return `<p class="m-kicker">Your judgement · ${esc(a.t)}</p>
<h3>${esc(j.label || meta.label || a.id)}</h3>
${j.asks ? prose(j.asks) : meta.plain ? prose(meta.plain) : ""}
${prior}${history}
<label>Your mark</label>
<select name="mark">
  <option value="">Not answering yet</option>
  <option value="pass">Pass — the question is settled in its favour</option>
  <option value="fail">Fail — it does not hold up</option>
</select>
<p class="m-quiet">Unanswered is never a fail. A strategy that waits on this question keeps waiting until you mark it.</p>
<label>Your reasoning <small>Required — the mark teaches nothing without it.</small></label>
<textarea name="reasoning" rows="4"></textarea>
<button class="m-act" data-do="judgement" data-t="${esc(a.t)}" data-id="${esc(a.id)}">Record the assessment</button>
<p class="m-quiet">This adds a new entry above the earlier ones; nothing is replaced.</p>`;
};
async function doJudgement(btn) {
  const f = marginForm();
  if (!(f.reasoning || "").trim()) return marginErr("The reasoning is required — the mark teaches nothing without it.");
  const r = await apiRaw("record_judgement", btn.dataset.t, btn.dataset.id, f.mark || null, f.reasoning);
  if (!r.ok) return marginErr(r.error);
  await refresh();
  margin("measure", { sid: btn.dataset.id, t: btn.dataset.t });
}

/* ----------------------------------------------------------- thesis edit */
PANES.thesisedit = (a) => {
  const s = find(a.t);
  if (!s) return PANES.rest();
  const t = s._thesis || {};
  const v = t.status === "known" ? (t.version || {}) : {};
  const amending = t.status === "known";
  return `<p class="m-kicker">${amending ? "Amend" : "Write"} · ${esc(a.t)}</p>
<h3>Why I own this</h3>
<p>Plain words, yours. The strategy tests numbers; this is the part only you can write — and the version standing on the day of a purchase is frozen onto it.</p>
<label>Why I own this</label>
<textarea name="thesis" rows="4">${esc(v.thesis || "")}</textarea>
<details><summary>What a good one looks like</summary>
<div class="m-note">“Fenwick Springs sells replacement parts for machines it stopped making —
customers are locked in for the machine’s life, which is why margins have held
above 30% for a decade. I am paying 9× typical earnings for that.”
<p class="m-quiet">Invented company. Notice it names the mechanism, not a feeling — and a price.</p></div></details>
<label>What would make me wrong</label>
<textarea name="falsifier" rows="3">${esc(v.falsifier || "")}</textarea>
<details><summary>What a good one looks like</summary>
<div class="m-note">“Parts revenue falling two years running, or a competitor cross-licensed to
make the parts — either means the lock-in I am paying for is gone.”
<p class="m-quiet">Invented company. A good “wrong” names something observable — a number
falling, a customer leaving — not a feeling.</p></div></details>
<p class="m-quiet">Both parts are optional; both are strongly recommended.</p>
${amending ? `<label>What changed? <small>Required — an amendment keeps the old version and this sentence beside it.</small></label>
<textarea name="reason" rows="2"></textarea>` : ""}
<button class="m-act" data-do="thesis" data-t="${esc(a.t)}" data-amend="${amending ? "1" : ""}">${amending ? "Amend — it adds a new version above it" : "Write it down"}</button>`;
};
async function doThesis(btn) {
  const f = marginForm();
  if (!(f.thesis || "").trim() && !(f.falsifier || "").trim())
    return marginErr("At least one of the two parts is needed.");
  if (btn.dataset.amend === "1" && !(f.reason || "").trim())
    return marginErr("Say what changed — the record keeps the old version and this sentence beside it.");
  const r = await apiRaw("amend_thesis", btn.dataset.t, f.thesis, f.falsifier, f.reason || "");
  if (!r.ok) return marginErr(r.error);
  if (!r.amended) toast("Nothing changed, so nothing was recorded.");
  await refresh();
  margin("thesis", { t: btn.dataset.t });
}

/* ------------------------------------------------------------ small acts */
PANES.noteadd = (a) => `<p class="m-kicker">Add a note · ${esc(a.t)}</p>
<h3>Dated, appended, never edited</h3>
<label>The note</label><textarea name="text" rows="4"></textarea>
<button class="m-act" data-do="note" data-t="${esc(a.t)}">Add it</button>
<p class="m-quiet">A note is anchored by its date. To anchor it to everything the page says today, <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-m="snapshot" data-arg="${escAttr({ t: a.t })}">save today’s reading</button> as well — the two share the day.</p>`;
async function doNote(btn) {
  const f = marginForm();
  if (!(f.text || "").trim()) return marginErr("Write the note first.");
  const r = await apiRaw("add_note", btn.dataset.t, f.text);
  if (!r.ok) return marginErr(r.error);
  await refresh();
  marginRest();
}

PANES.snapshot = (a) => `<p class="m-kicker">Save today’s reading · ${esc(a.t)}</p>
<h3>A day you keep on purpose</h3>
<p>Freezes what everything says now — the verdict, every figure with what qualifies it, the rules in force — exactly the way a purchase freezes its day. “What changed” is measured against your last kept reading.</p>
<p class="m-quiet">There is no date field, by design: a reading is of the day somebody looked, and a baseline you could mint retrospectively would not be a baseline.</p>
<label>Why this day is worth keeping <small>(optional)</small></label>
<textarea name="note" rows="2"></textarea>
<button class="m-act" data-do="snapshot" data-t="${esc(a.t)}">Save it</button>`;
async function doSnapshot(btn) {
  const f = marginForm();
  const r = await apiRaw("save_snapshot", btn.dataset.t, f.note || "");
  if (!r.ok) return marginErr(r.error);
  toast(`Saved — it read “${r.state || "no verdict"}” on ${r.day}.`);
  await refresh();
  marginRest();
}

PANES.discardsnap = (a) => `<p class="m-kicker">Discard a saved reading · ${esc(a.t)}</p>
<h3>It stops counting; it never disappears</h3>
<p>The reading stays on the record, whole, marked discarded — it drops out of the list and out of what “since last time” measures against. Losing one silently is impossible by construction.</p>
<label>Why let it go <small>(optional)</small></label>
<input name="reason">
<button class="m-act warn" data-do="discardsnap" data-t="${esc(a.t)}" data-seq="${esc(String(a.seq))}">Discard it</button>`;
async function doDiscardSnap(btn) {
  const f = marginForm();
  const r = await apiRaw("discard_snapshot", btn.dataset.t, Number(btn.dataset.seq), f.reason || "");
  if (!r.ok) return marginErr(r.error);
  await refresh();
  marginRest();
}

/* --------------------------------------------------- readings comparison */
PANES.readings = (a) => paneReadings(a);
async function paneReadings(a) {
  const s = find(a.t);
  if (!s) return PANES.rest();
  const rows = ((s._snapshots || {}).rows || []);
  if ((s._snapshots || {}).refusal) {
    return `<p class="m-kicker">Saved readings · ${esc(a.t)}</p>
<h3>The record cannot be shown</h3><p>${esc(s._snapshots.refusal)}</p>`;
  }
  if (!rows.length) {
    return `<p class="m-kicker">Saved readings · ${esc(a.t)}</p>
<h3>Nothing is kept yet</h3>
<p>Save today’s reading and “what changed since” gets an anchor.</p>
<button class="m-act" data-m="snapshot" data-arg="${escAttr({ t: a.t })}">Save today’s reading</button>`;
  }
  if (a.seqs && a.seqs.length >= 2) {
    const r = await apiRaw("compare_snapshots", a.t, a.seqs);
    if (!r.ok) return `<p class="m-kicker">Saved readings · ${esc(a.t)}</p><h3>Could not compare</h3><p>${esc(r.error)}</p>`;
    return comparisonHtml(a.t, r.comparison);
  }
  /* One kept day against today: the frozen record beside the live one. */
  if (a.seq !== undefined || rows.filter((x) => !x.discarded).length === 1) {
    const seq = a.seq !== undefined ? a.seq : rows.find((x) => !x.discarded).seq;
    const got = await apiRaw("get_snapshot", a.t, seq);
    if (!got.ok) return `<p class="m-kicker">Saved readings · ${esc(a.t)}</p><h3>Could not open it</h3><p>${esc(got.error)}</p>`;
    return snapshotVsToday(s, got.entry) + pickList(a.t, rows, a);
  }
  return `<p class="m-kicker">Saved readings · ${esc(a.t)}</p>
<h3>${rows.length} kept day${rows.length === 1 ? "" : "s"}</h3>
<p>Open one against today, or tick two or more and compare the trend between them.</p>
${pickList(a.t, rows, a)}`;
}
function pickList(t, rows, a) {
  return `<div class="m-h">The kept days</div>
  ${rows.map((row) => `<div class="m-note" style="display:flex;gap:.6rem;align-items:baseline">
    <input type="checkbox" name="cmp_${row.seq}" style="width:auto" ${a && (a.seqs || []).includes(row.seq) ? "checked" : ""}>
    <span style="flex:1">${esc(row.day)} — <i>${esc(row.state || "no verdict")}</i>${row.note ? ` · “${esc(row.note)}”` : ""}${row.discarded ? ` <span class="chip">discarded</span>` : ""}
    <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-m="readings" data-arg="${escAttr({ t, seq: row.seq })}">against today</button></span>
  </div>`).join("")}
  <button class="m-act quiet" data-do="compare" data-t="${esc(t)}">Compare the ticked days</button>`;
}
async function doCompare(btn) {
  const seqs = [];
  $("margin").querySelectorAll('[name^="cmp_"]').forEach((el) => {
    if (el.checked) seqs.push(Number(el.name.slice(4)));
  });
  if (seqs.length < 2) return marginErr("Tick at least two kept days to compare.");
  margin("readings", { t: btn.dataset.t, seqs });
}
/* A frozen figure renders in the words and format IN FORCE when it was
   frozen — a measure renamed after a snapshot must not rename the snapshot.
   The bank standing today is consulted only for a record predating the
   frozen fields, the same rule a frozen citation follows. */
const frozenLabel = (id, held) =>
  held && held.label != null ? held.label : labelOf(id);
const fmtFrozen = (id, held, v) =>
  held && held.format !== undefined && held.format !== null
    ? fmtBank(v, held.format) : fmtMetric(id, v);

function snapshotVsToday(s, entry) {
  const snap = entry.snapshot || {};
  const frozen = snap.decision || {};
  const today = s._decision || {};
  const day = String(entry.recorded || "").slice(0, 10);
  const metrics = snap.metrics || {};
  const name = (id) => frozenLabel(id, metrics[id]);
  const rows = Object.keys(metrics).sort((a, b) => name(a).localeCompare(name(b))).map((id) => {
    const then = metrics[id];
    const now = (s._computed || {})[id];
    const nowTxt = now && (now.status === "computed" || now.status === "known")
      ? boundWord(now) + fmtMetric(id, now.value)
      : now && now.status === "inapplicable" ? "not applicable" : "not known now";
    const renamed = then && then.label != null && then.label !== labelOf(id)
      ? ` <span class="dim">(now called ${esc(labelOf(id))})</span>` : "";
    return `<tr><td>${esc(name(id))}${renamed}</td><td class="num">${boundWord(then)}${esc(fmtFrozen(id, then, then.value))}${cmMark(then.cautions)}</td><td class="num">${esc(nowTxt)}${now && (now.status === "computed" || now.status === "known") ? cmMark(now.cautions) : ""}</td></tr>`;
  }).join("");
  return `<p class="m-kicker">Saved reading · ${esc(day)}</p>
<h3>Compared with today</h3>
<p>It read <b>${esc((frozen.state || {}).name || "no verdict")}</b> that day; today reads <b>${esc((today.state || {}).name || "no verdict")}</b>${
    (frozen.state || {}).id === (today.state || {}).id ? " — the same state" : ""}.</p>
${entry.note ? `<div class="m-h">Your note that day</div><p>“${esc(entry.note)}”</p>` : ""}
${rows ? `<div class="m-h">Then · now</div><table class="m-series"><tr><td class="dim">figure</td><td class="dim">${esc(day)}</td><td class="dim">now</td></tr>${rows}</table>` : ""}
<p class="m-quiet">A reading is frozen when you save it and never updated. The difference between then and now is the thing worth reading — and a figure missing from the frozen side was simply not known that day.</p>`;
}
function comparisonHtml(t, cmp) {
  const cols = cmp.columns || [];
  const heads = cols.map((c) => `<td class="dim">${esc(c.day)}${c.discarded ? " ✕" : ""}</td>`).join("");
  const verdictRow = `<tr><td>Verdict</td>${(cmp.verdict || []).map((v) =>
    `<td>${esc((v.state || {}).name || "")}</td>`).join("")}<td></td></tr>`;
  const priceRow = `<tr><td>Price</td>${(cmp.price || []).map((p) =>
    `<td class="num">${p.status === "known"
      ? money(p.value) + (p.source === "manual"
        ? ' <span class="typed" title="Entered by hand — it carried no date when it was frozen.">typed°</span>'
        : p.date ? ` <span class="dim">${esc(fmtCloseDate(p.date))}</span>` : "")
      : `<span class="absent" title="${esc(p.reason || "")}">—</span>`}</td>`).join("")}<td></td></tr>`;
  /* Each column's figure renders in its own frozen words; the row is headed
     by the newest frozen label, with today's bank only covering records
     that predate the field. Two days frozen under different labels head the
     row with the newer and say so — relabelling either would rewrite it. */
  const rowLabel = (m, id) => {
    const withWords = (m.readings || []).filter((r) => r.status === "known"
      && r.label != null);
    return withWords.length ? withWords[withWords.length - 1].label
      : labelOf(id);
  };
  const ids = Object.keys(cmp.measures || {}).sort((a, b) =>
    rowLabel(cmp.measures[a], a).localeCompare(rowLabel(cmp.measures[b], b)));
  const rows = ids.map((id) => {
    const m = cmp.measures[id];
    const cells = (m.readings || []).map((r) =>
      `<td class="num">${r.status === "known"
        ? boundWord(r) + esc(fmtFrozen(id, r, r.value)) + cmMark(r.cautions)
        : '<span class="absent" title="' + esc(r.reason || "") + '">—</span>'}</td>`).join("");
    const moved = m.moved && m.moved.status === "known"
      ? `<td class="num">${esc(fmtMetric(id, m.moved.value))}</td>`
      : `<td><button class="absent" data-m="absent" data-arg="${escAttr({ label: rowLabel(m, id) + " — the move between these days", reason: (m.moved || {}).reason || "" })}">—</button></td>`;
    return `<tr><td>${esc(rowLabel(m, id))}</td>${cells}${moved}</tr>`;
  }).join("");
  return `<p class="m-kicker">Saved readings · ${esc(t)}</p>
<h3>${cols.length} days, side by side</h3>
<table class="m-series"><tr><td class="dim">figure</td>${heads}<td class="dim">moved</td></tr>
${verdictRow}${priceRow}${rows}</table>
<p class="m-quiet">Everything is read off what each day froze — nothing is worked out again. A dash carries its own reason; a move is refused where the measure’s definition changed in between, because that distance would not be a distance in one measure.</p>
<button class="m-act quiet" data-m="readings" data-arg="${escAttr({ t })}">Back to the kept days</button>`;
}

/* ------------------------------------------------------------------ cash */
PANES.cash = () => {
  const c = S.cash || {};
  const kinds = c.kinds || {};
  const offers = c.offers || [];
  const opened = c.opened;
  return `<p class="m-kicker">The cash record</p>
<h3>${opened ? "Record money in or out" : "Open the cash record"}</h3>
<p>${opened ? "Dated and appended — the balance is derived from the record, never typed."
    : "It starts with the cash the account held at the start of a day; everything after is counted from it. Without it, no account total and no position weight can be honest."}</p>
<label>What happened</label>
<select name="kind" id="cash_kind">${offers.map((k) =>
    `<option value="${esc(k)}">${esc((kinds[k] || {}).label || k)}</option>`).join("")}</select>
<div class="m-row"><div><label>Amount</label><input name="amount" type="number" step="any" placeholder="always positive — the kind carries the direction"></div>
<div><label>Date</label><input name="when" type="date" value="${esc(localToday())}" max="${esc(localToday())}"></div></div>
<label>Note <small>(optional)</small></label><input name="note">
<button class="m-act" data-do="cash">Record it</button>
${cashMini()}`;
};
async function doCash() {
  const f = marginForm();
  if (!f.amount) return marginErr("An amount is needed.");
  const r = await apiRaw("record_cash", f.kind, f.amount, f.when, f.note || "");
  if (!r.ok) return marginErr(r.error);
  await refresh(); refreshTimeframe();
  margin("acct", { which: "cash" });
}

/* -------------------------------------------------------------- settings */
PANES.settings = () => {
  const st = S.strategy;
  if (!st) return PANES.rest();
  const fields = (st.inputs || []).map((f) => {
    if (f.answered_by === "host") {
      return `<label>${esc(f.label)}</label>
        <input value="${f.value !== null && f.value !== undefined ? esc(String(f.value)) : "not worked out"}" readonly>
        <p class="m-quiet">${esc(f.answered_how || "Worked out by the journal from its own record.")}
        <button class="dim" style="border-bottom:1px dotted var(--hair-dark)" data-m="cash" data-arg="{}">Record money in or out</button></p>`;
    }
    return declaredField(f, f.value, "in_");
  }).join("");
  return `<p class="m-kicker">This journal’s answers</p>
<h3>What the strategy asked you</h3>
<p>Facts about your account — they genuinely move, and changing one lands on the answers record. The strategy’s own thresholds are not here: those are read-only in the app, by design.</p>
${fields}
<button class="m-act" data-do="settings">Save the answers</button>`;
};
async function doSettings() {
  const f = marginForm();
  const inputs = {};
  Object.entries(f).forEach(([k, v]) => { if (k.startsWith("in_")) inputs[k.slice(3)] = v; });
  const r = await apiRaw("save_journal_settings", inputs, null);
  if (!r.ok) return marginErr(r.error);
  await refresh(); refreshTimeframe();
  marginRest();
}

/* A declared value or input, glossed read-only from the Strategy page. */
PANES.declared = (a) => {
  const st = S.strategy || {};
  const spec = (a.kind === "value" ? st.values : st.inputs || []).find((x) => x.id === a.id);
  if (!spec) return PANES.rest();
  const src = spec.source
    ? `<div class="m-h">Where the number came from</div><p>${esc(spec.source.name || "")}${spec.source.reasoning ? " — the reasoning above is that source’s." : ""}</p>` : "";
  return `<p class="m-kicker">${a.kind === "value" ? "A setting this strategy ships" : "Something this journal asked you"}</p>
<h3>${esc(spec.label)}</h3>
<p>${a.kind === "value"
    ? `<b class="num">${esc(declaredText(spec, spec.value))}</b>${spec.set_by && spec.set_by !== "shipped default" ? ` <span class="dim">(${esc(spec.set_by)}; shipped: ${esc(declaredText(spec, spec.shipped))})</span>` : ' <span class="dim">(shipped default)</span>'}`
    : spec.value !== null && spec.value !== undefined && spec.value !== ""
      ? `<b>${esc(String(spec.value))}</b>` : '<span class="absent">not answered</span>'}</p>
${spec.explain ? prose(spec.explain) : ""}
${src}
${a.kind === "value" ? '<p class="m-quiet">Read-only here by design: a threshold changes in the strategy’s own files, deliberately, and every change is detected and recorded on the Strategy page.</p>'
    : `<button class="m-act quiet" data-m="settings" data-arg="{}">Change your answers</button>`}`;
};

/* ------------------------------------------------- journal housekeeping */
/* Rename and delete live in the dropdown the journal pill opens — chrome
   opens where it was clicked, and never evicts whatever the margin holds.
   Starting another journal is a screen (newJournalView): a permanent
   decision plus a form needs room a dropdown does not have. */
async function doRenameJournal() {
  const f = menuForm();
  const r = await apiRaw("rename_journal", (S.journal || {}).id, f.name);
  if (!r.ok) return menuErr(r.error);
  menuClose();
  await refresh();
}

async function doDeleteJournal() {
  const f = menuForm();
  const r = await apiRaw("delete_journal", (S.journal || {}).id, f.confirm_name || "");
  if (!r.ok) return menuErr(r.error);
  menuClose();
  closeSecurity(); tab = "list";
  await refresh();
  marginRest();
}

/* ------------------------------------------------------ add securities */
PANES.add = (a) => `<p class="m-kicker">Add securities</p>
<h3>One name, or a pasted list</h3>
<p>One name fetches its data straight away. A pasted list does not — each lands as an explicit “no data yet”, and a fetch is a click on its page.</p>
<label>Ticker</label><input name="ticker" placeholder="e.g. ACME" style="text-transform:uppercase">
<label>Company name</label><input name="name" placeholder="as you know it">
<label><input type="checkbox" name="fetchnow" checked style="width:auto"> Fetch its data now</label>
<button class="m-act" data-do="add">Add it</button>
<div class="m-h">Or paste several</div>
<label>One per line — ticker, then the name <small>e.g. “ACME Acme Widgets”</small></label>
<textarea name="bulk" rows="5"></textarea>
<button class="m-act quiet" data-do="addbulk">Add them all</button>
<p class="m-quiet">They land on the watchlist, judged as soon as data exists for them.</p>`;
async function doAdd() {
  const f = marginForm();
  const ticker = (f.ticker || "").trim().toUpperCase();
  if (!ticker) return marginErr("A ticker is needed.");
  const r = await apiRaw("add_security", ticker, (f.name || "").trim());
  if (!r.ok) return marginErr(r.error);
  const wantFetch = !!$("margin").querySelector('[name="fetchnow"]:checked');
  if (wantFetch) {
    const fr = await apiRaw("fetch_security", ticker);
    if (fr.ok) startFetchPoll(ticker);
    else toast(fr.error, true);
  }
  await refresh();
  refreshTimeframe();
  openSecurity(ticker); render();
  marginRest();
}
async function doAddBulk() {
  const f = marginForm();
  const lines = String(f.bulk || "").split("\n").map((l) => l.trim()).filter(Boolean);
  if (!lines.length) return marginErr("Paste at least one line.");
  const failed = [];
  for (const line of lines) {
    const m = /^(\S+)\s*(.*)$/.exec(line);
    const r = await apiRaw("add_security", m[1].toUpperCase(), m[2] || "");
    if (!r.ok) failed.push(`${m[1].toUpperCase()}: ${r.error}`);
  }
  await refresh();
  refreshTimeframe();
  if (failed.length) return marginErr(`${lines.length - failed.length} added. Not added — ${failed.join(" · ")}`);
  toast(`${lines.length} added to the watchlist — no data yet, by design. Fetch each from its page, or as you get to it.`);
  marginRest();
}

/* ------------------------------------------------------- list & passover */
PANES.importlist = () => {
  const declared = ((S.list || {}).declared || {});
  return `<p class="m-kicker">${esc(declared.label || "Import a list")}</p>
<h3>The list you work from</h3>
<p>${esc(declared.explain || "")}</p>
<p class="m-quiet">${esc(sourceName(declared.source))}</p>
<div class="m-row"><div><label>The day you pulled it</label><input name="pulled_on" type="date" value="${esc(localToday())}" max="${esc(localToday())}"></div>
<div><label>Smallest company asked for <small>(optional $)</small></label><input name="floor" type="number"></div></div>
<label>The names, pasted <small>— all or nothing; unreadable lines are named</small></label>
<textarea name="pasted" rows="6"></textarea>
<button class="m-act" data-do="importlist">Import it</button>`;
};
async function doImportList() {
  const f = marginForm();
  if (!(f.pasted || "").trim()) return marginErr("Paste the names first.");
  const r = await apiRaw("import_list", f.pulled_on, f.pasted, f.floor || null);
  if (!r.ok) return marginErr(r.error);
  toast(`Imported ${r.n} names, pulled ${r.pulled_on}.`);
  filter = "yourlist";
  await refresh();
  marginRest();
}
PANES.passover = (a) => `<p class="m-kicker">Not buying this one · ${esc(a.t)}</p>
<h3>Passing is a decision too</h3>
<p>The method hands you the list so you do not pick — passing over a name is a deviation from it, and the record keeps what happened to the names you declined.</p>
<label>Why are you passing? <small>Required.</small></label>
<textarea name="reason" rows="3"></textarea>
<button class="m-act warn" data-do="passover" data-t="${esc(a.t)}" data-name="${esc(a.name || "")}">Record the pass</button>`;
async function doPassOver(btn) {
  const f = marginForm();
  if (!(f.reason || "").trim()) return marginErr("A reason is required.");
  const r = await apiRaw("pass_over", btn.dataset.t, f.reason, btn.dataset.name || null);
  if (!r.ok) return marginErr(r.error);
  await refresh();
  marginRest();
}

/* ------------------------------------------------------- explain change */
PANES.explain = (a) => {
  const words = (S.change_records || {})[a.record] || {};
  const list = a.record === "rules" ? S.rule_changes : a.record === "measures" ? S.measure_changes : S.input_changes;
  const c = (list || []).find((x) => x.seq === a.seq) || {};
  const lines = [
    ...(c.moved || []).map((m) => `${m.label || m.id}: ${fmtDefined(m.from)} → ${fmtDefined(m.to)}`),
    ...(c.added || []).map((m) => `${m.name || m.id} — added`),
    ...(c.removed || []).map((m) => `${m.name || m.id} — removed`),
    ...(c.restated || []).map((m) => `${m.name || m.id} · ${m.field} changed`),
  ];
  return `<p class="m-kicker">${esc(cap(words.noun || "change"))} ${esc(String(a.seq))}</p>
<h3>What moved</h3>
${lines.map((l) => `<p class="m-quiet">${esc(l)}</p>`).join("") || "<p class='m-quiet'>Recorded.</p>"}
<label>Why <small>Written once — the record is append-only.</small></label>
<textarea name="reason" rows="3"></textarea>
<button class="m-act" data-do="explain" data-record="${esc(a.record)}" data-seq="${esc(String(a.seq))}">Attach the reason</button>`;
};
async function doExplain(btn) {
  const f = marginForm();
  if (!(f.reason || "").trim()) return marginErr("A reason is required.");
  const r = await apiRaw("explain_change", btn.dataset.record, Number(btn.dataset.seq), f.reason);
  if (!r.ok) return marginErr(r.error);
  await refresh();
  marginRest();
}

/* -------------------------------------------------------- data actions */
PANES.sources = () => {
  const sec = S.data_security || {};
  return `<p class="m-kicker">Data access</p>
<h3>The two things fetching needs</h3>
<label>Your name and email <small>— sent as the User-Agent the SEC asks for; machine-only, never exported</small></label>
<input name="sec_identity" placeholder="Jane Doe jane@example.com" value="${esc(sec.sec_identity || "")}">
<button class="m-act quiet" data-do="secidentity">Save identity</button>
<label>Tiingo API key <small>— free at tiingo.com; the tool only ever reads prices with it</small></label>
<input name="api_key" type="password" placeholder="${sec.key_configured ? "already configured — paste to replace" : "paste the key"}">
<p class="m-quiet">Stored ${esc(storageWords(sec.storage) || "in the OS credential store")} — never shown, never exported, never logged.${sec.problem ? " " + esc(sec.problem) : ""}</p>
<button class="m-act quiet" data-do="savekey">Save key</button>
<button class="m-act quiet" data-do="testkey">Test the stored key</button>
${sec.key_configured ? '<button class="m-act quiet" data-do="removekey">Remove it</button>' : ""}`;
};
async function doSecIdentity() {
  const f = marginForm();
  const r = await apiRaw("save_sec_identity", f.sec_identity || "");
  if (!r.ok) return marginErr(r.error);
  toast("Identity saved.");
  await refresh(); marginStill();
}
async function doSaveKey() {
  const f = marginForm();
  if (!(f.api_key || "").trim()) return marginErr("Paste the key first.");
  const r = await apiRaw("save_api_key", f.api_key);
  if (!r.ok) return marginErr(r.error);
  toast("Key saved. It is never shown again — test it below.");
  await refresh(); marginStill();
}
async function doTestKey() {
  const r = await apiRaw("test_api_key");
  if (!r.ok) return marginErr(r.error);
  toast(r.message || (r.valid ? "The key works." : "The key was refused."), !r.valid);
}
async function doRemoveKey() {
  const r = await apiRaw("remove_api_key");
  if (!r.ok) return marginErr(r.error);
  toast(r.removed ? "Key removed. Fetching stops until a new one is saved." : "No key was stored.");
  await refresh(); marginStill();
}

PANES.valdefaults = () => {
  const d = (S.journal || {}).settings || {};
  return `<p class="m-kicker">Valuation defaults</p>
<h3>Prefills, not conclusions</h3>
<p>These seed every expected-value calculation in this journal. Each can be changed at the moment of use, and the value solved for is never typed anywhere.</p>
<label>Discount rate <small>%</small></label><input name="discount_rate" type="number" step="any" value="${esc(d.discount_rate ?? "")}">
<p class="m-quiet">The yearly return you demand for tying money up in something this uncertain. Higher makes every valuation stingier. Something near what a whole-market fund has returned — 8 to 10 — is a common anchor.</p>
<label>Terminal growth <small>%</small></label><input name="terminal_growth" type="number" step="any" value="${esc(d.terminal_growth ?? "")}">
<p class="m-quiet">How fast the business grows forever, after the years you can see. Inflation plus a little — 2 to 3 — is the defensible range; above that you are claiming it outgrows the economy for eternity.</p>
<label>Margin of safety <small>%</small></label><input name="margin_of_safety" type="number" step="any" value="${esc(d.margin_of_safety ?? "")}">
<p class="m-quiet">The discount you demand below your own estimate — room to be wrong, not a return target. Graham's traditional number is 30.</p>
<button class="m-act" data-do="valdefaults">Save</button>`;
};
async function doValDefaults() {
  const f = marginForm();
  const r = await apiRaw("save_valuation_defaults", f.discount_rate, f.terminal_growth, f.margin_of_safety);
  if (!r.ok) return marginErr(r.error);
  await refresh();
  marginRest();
}

PANES.importdata = () => `<p class="m-kicker">Import a backup</p>
<h3>It replaces what is here</h3>
<p>Your current journals are exported automatically first, then replaced by the bundle you choose. Fetched filings, prices and your key are untouched.</p>
<button class="m-act warn" data-do="importdata">Choose a bundle</button>`;
async function doImportData() {
  const r = await apiRaw("import_data");
  if (!r.ok) return marginErr(r.error);
  if (r.cancelled) { marginRest(); return; }
  toast("Imported.");
  closeSecurity();
  await refresh(); refreshTimeframe();
  marginRest();
}

PANES.emptyjournal = () => `<p class="m-kicker">Empty this journal</p>
<h3>Every security goes; the journal stays</h3>
<p>The strategy stamp, your answers, and the change records are kept — they are the journal. The securities and everything recorded on them are removed and cannot be recovered. Export first if there is any doubt.</p>
<button class="m-act quiet" data-act="export">Export it first</button>
<button class="m-act warn" data-do="emptyjournal">Empty it</button>`;
async function doEmptyJournal() {
  const r = await apiRaw("clear_all");
  if (!r.ok) return marginErr(r.error);
  closeSecurity();
  await refresh(); refreshTimeframe();
  marginRest();
}

/* The "More ▾" toolbox is a dropdown now (see 15-menu.js) — a menu is
   chrome and opens where it was clicked; each door it holds still opens
   its pane here in the margin, where acting lives. */
PANES.remove = (a) => `<p class="m-kicker">Remove · ${esc(a.t)}</p>
<h3>Only what was never acted on can go</h3>
<p>Anything typed for it goes with it; fetched public data stays cached. A security with recorded decisions cannot be removed at all — the engine refuses, not this screen.</p>
<button class="m-act warn" data-do="remove" data-t="${esc(a.t)}">Remove it</button>`;
async function doRemove(btn) {
  const r = await apiRaw("remove_security", btn.dataset.t);
  if (!r.ok) return marginErr(r.error);
  closeSecurity();
  await refresh();
  marginRest();
}

/* ------------------------------------------------------------- fetching */
function startFetchPoll(ticker) {
  if (FETCH_POLLS[ticker]) return;
  FETCH_POLLS[ticker] = true;
  const tick = async () => {
    const r = await apiRaw("get_fetch_status", ticker);
    const st = r.ok ? r.status : null;
    if (st && st.running) { setTimeout(tick, 1500); return; }
    FETCH_POLLS[ticker] = false;
    if (st && st.error) {
      /* The crash path: the fetch died and said why. Never a plain
         "finished" — nothing fails silently. */
      toast(`${ticker}: the fetch failed — ${st.error}`, true);
    } else if (st && st.report) {
      const rep = st.report;
      const bits = [];
      if (rep.filings_new !== undefined) {
        bits.push(`${rep.filings_new} new filing${rep.filings_new === 1 ? "" : "s"}`);
      }
      const said = rep.conflict || rep.ticker_unmapped || rep.no_coverage;
      if (said) bits.push(said);
      const errs = rep.errors || [];
      if (errs.length) {
        bits.push(`${errs.length} problem${errs.length === 1 ? "" : "s"} — the first: ${errs[0]}`);
      }
      toast(`${ticker}: fetch finished${bits.length ? " — " + bits.join(" · ") : ""}.`
        .replace(/\.\.$/, "."), !!(said || errs.length));
    } else {
      toast(`${ticker}: fetch finished.`);
    }
    C.coverageFor = null;
    await refresh(); refreshTimeframe();
  };
  setTimeout(tick, 1500);
}
