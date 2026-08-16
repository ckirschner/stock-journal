/* The margin: the second surface, where explanation and acting live.

   The plane never grows a paragraph. Every name, figure and heading on it is
   a handle that fills this margin with its gloss — what the thing means in
   plain words, how it is worked out, where the number came from, and what
   qualifies it. Acting happens here too: recording a purchase or a sale
   opens in the margin with today's verdict pinned on top, which is how
   "every door leads to one place" is kept.

   Nothing opens the margin unprompted. The resting state invites a click
   and otherwise stays out of the way — teaching is by pull, never push. */

/* The registry. A pane is a function (arg) -> html, or an async function
   that writes the margin itself when its data lands. Registered from
   several files; this object is the only shared surface. */
const PANES = {};

let M = { id: "rest", arg: null };

let _marginSeq = 0;
function margin(id, arg) {
  const pane = PANES[id] || PANES.rest;
  M = { id, arg };
  const seq = ++_marginSeq;
  const el = $("margin");
  const paint = (html) => {
    /* A pane that resolved after the reader moved on stays unpainted —
       without this, a slow preview could clobber whatever they opened
       next, or re-open a margin they had closed. */
    if (seq !== _marginSeq) return;
    el.innerHTML = '<button class="m-close" data-mclose aria-label="Close">✕</button>' + html;
    el.scrollTop = 0;
    el.classList.toggle("open", id !== "rest");
    applyGates(el);
  };
  const out = pane(arg);
  if (out && typeof out.then === "function") {
    paint('<p class="m-hint">Reading…</p>');
    out.then((html) => { if (html != null) paint(html); });
  } else {
    paint(out);
  }
  document.querySelectorAll("tr.sel").forEach((r) => r.classList.remove("sel"));
  if (arg && arg.rowKey) {
    const tr = document.querySelector(`tr[data-rowkey="${CSS.escape(arg.rowKey)}"]`);
    if (tr) tr.classList.add("sel");
  }
}
const marginRest = () => margin("rest");

/* Re-open the current pane against fresh state — used after refresh() where
   the pane shows live data. Forms are not re-rendered: a pane that holds
   typed input repaints only when its own action finishes. */
function marginStill() {
  if (M.id !== "rest") margin(M.id, M.arg);
}

/* Read every [name] field in the margin, as strings. */
function marginForm() {
  const data = {};
  $("margin").querySelectorAll("[name]").forEach((el) => { data[el.name] = el.value; });
  return data;
}
/* Show a problem inside the pane, where the person is standing. */
function marginErr(msg) {
  let box = $("margin").querySelector(".m-err[data-live]");
  if (!box) {
    box = document.createElement("div");
    box.className = "m-err";
    box.setAttribute("data-live", "1");
    const h = $("margin").querySelector("h3");
    (h ? h.nextSibling ? h.parentNode : $("margin") : $("margin"))
      .insertBefore(box, h ? h.nextSibling : null);
  }
  box.textContent = msg;
}
/* Run an action from a pane: `fn(form)` returns an error sentence, true for
   "handled", or nothing for success (refresh + a pane of the caller's
   choosing, default rest). */
async function marginGo(fn, after) {
  const err = await fn(marginForm());
  if (err === true) return;
  if (err) { marginErr(err); return; }
  await refresh();
  refreshTimeframe();
  if (after) after(); else marginRest();
}

/* ---------------------------------------------------------------- shared */
/* Cautions render whole, one line each — except where several are the SAME
   sentence about different holdings ("HARW: entered by hand…" seven times
   over). Those fold to one line naming every subject, because a wall of
   repeated text is exactly how the one that mattered gets scrolled past.
   The sentence itself is never altered; only identical tails group. */
const mCautions = (cs) => {
  const list = cs || [];
  if (list.length < 4) {
    return list.map((c) => `<p class="caution">Qualified — ${esc(c)}</p>`).join("");
  }
  const groups = [];
  const byTail = {};
  list.forEach((c) => {
    const m = /^([A-Z0-9.\-]+): (.+)$/s.exec(String(c));
    if (m && byTail[m[2]]) { byTail[m[2]].subjects.push(m[1]); return; }
    const g = m ? { subjects: [m[1]], tail: m[2] } : { subjects: null, tail: String(c) };
    groups.push(g);
    if (m) byTail[m[2]] = g;
  });
  return groups.map((g) => `<p class="caution">Qualified — ${g.subjects && g.subjects.length > 1
    ? `${esc(g.subjects.join(", "))}: ${esc(g.tail)}`
    : esc(g.subjects ? `${g.subjects[0]}: ${g.tail}` : g.tail)}</p>`).join("");
};
const mProv = (ps) => (ps || []).map((p) => `<p class="m-quiet">${esc(p)}</p>`).join("");
const mNode = (node, renderVal, label) => node && node.status === "known"
  ? `<b class="num">${renderVal ? renderVal(node.value) : esc(String(node.value))}</b>`
  : `<button class="absent" data-m="absent" data-arg="${escAttr({
      label: label || "This figure",
      reason: (node || {}).reason || "" })}">${node && node.status === "inapplicable" ? "not applicable" : "not known"}</button>`;

/* ----------------------------------------------------------------- panes */
PANES.rest = () => `<p class="m-kicker">The margin</p>
<h3>Nothing is open</h3>
<p class="m-hint">Click any figure, state name, or group heading and it is
explained here — what it means in plain words, how it is worked out, where
the number came from, and what qualifies it.</p>
<p class="m-hint">The page never moves while you read. Close this with ✕ or
open something else.</p>`;

/* A derived figure, glossed: what it is in plain words, the value with
   what qualifies it, and where it came from. */
PANES.figure = (a) => `<p class="m-kicker">A figure the journal derives</p>
<h3>${esc(a.label || "This figure")}</h3>
<p>${a.text ? `<b class="num">${esc(a.text)}</b>` : `<span class="absent">not known</span>`}${
  a.reason ? ` — ${esc(a.reason)}` : ""}</p>
${a.explain ? prose(a.explain) : ""}
${mCautions(a.cautions)}
${mProv(a.provenance)}
<p class="m-quiet">Derived from your own record and the stored data — never typed, so when it looks wrong the input it came from is the thing to check.</p>`;

/* A generic absence: the label and the host's own reason. */
PANES.absent = (a) => `<p class="m-kicker">Why there is no figure</p>
<h3>${esc(a.label || "This figure")}</h3>
<p>${esc(a.reason || "No reason was recorded.")}</p>`;

/* A verdict state, glossed: the strategy's own words, where it sits in the
   host's vocabulary, and the rule that produced it. */
PANES.state = (a) => {
  const s = find(a.t);
  const d = a.frozen || (s && s._decision);
  if (!d) return PANES.rest();
  const spec = (S.render_types || {})[d.render] || {};
  const st = d.state || {};
  const r = d.reason || {};
  const host = d.produced_by === "host";
  return `<p class="m-kicker">${host ? "A state the journal itself produced"
      : "A state this strategy declares"}</p>
<h3>${esc(st.name || "")}</h3>
${prose(st.description)}
<div class="m-h">Where it sits</div>
<p>It renders as <b>${esc(d.render)}${spec.meaning ? " — " + esc(spec.meaning) : ""}</b>.
${spec.attention ? "It is one of the states that asks something of you."
  : "It asks nothing of you."}</p>
<div class="m-h">What produced it</div>
<p class="num">${host ? esc(r.rule || st.id || "")
  : `rule ${esc(r.rule || "")} · ${esc((d.strategy || {}).name || "")} v${esc((d.strategy || {}).version)}`
    + ((d.strategy || {}).values_version != null
      ? ` · settings v${esc(d.strategy.values_version)}` : "")}</p>
${host ? "<p class=\"m-quiet\">Produced by the journal itself — no strategy verdict exists to show.</p>" : ""}`;
};

/* A group of tests: what it demanded and how the tally reads. */
PANES.group = (a) => {
  const s = find(a.t);
  const d = a.frozen || (s && s._decision);
  const g = (((d || {}).reason || {}).groups || []).find((x) => x.id === a.gid);
  if (!g) return PANES.rest();
  const need = g.requires === "all"
    ? "Every tested line in it must hold."
    : g.requires === "at_least"
      ? ((g.test && g.test.absent)
        ? `It needs a number of passes and none is set — ${esc(g.test.absent)}.`
        : `At least ${esc(String((g.test || {}).threshold))} of its lines must hold`
          + ((g.test || {}).threshold_from ? ` — your ${esc(g.test.threshold_from.label)}.` : "."))
      : "It is reported on every reading and never blocks anything.";
  return `<p class="m-kicker">A group of tests</p>
<h3>${esc(g.name)}</h3>
<p>${need}</p>
<div class="m-h">How the tally reads</div>
<p>${g.tested
    ? `${g.passed} of ${g.tested} tested lines hold${g.failed ? `, ${g.failed} ${g.failed === 1 ? "misses" : "miss"}` : ""}${g.unknown ? `, and ${g.unknown} could not be worked out` : ""}.`
    : "Nothing in it was tested on this reading."}
${g.unknown ? " A line that could not be worked out counts as neither a pass nor a failure — absence never reads as success here." : ""}</p>`;
};

/* The measure gloss — the teaching surface. Everything the bank knows about
   the entry, the figure this security carries for it, where that figure came
   from, and the reader's own typed history. */
PANES.measure = (a) => {
  const meta = bankMeta(a.sid) || {};
  const s = a.t ? find(a.t) : null;
  loadBankThen(() => { if (M.id === "measure" && (M.arg || {}).sid === a.sid) margin("measure", M.arg); });
  const full = (C.bank || []).find((e) => e.id === a.sid) || null;

  /* The figure in front of the reader: the evidence row's if one was
     clicked, else the security's current resolved value. */
  let headline = "";
  const ev = a.ev || null;
  if (ev) {
    const obs = ev.observed || {};
    const t = ev.test || null;
    const val = obs.status === "known"
      ? `<b class="num">${esc(fmtSubject(ev.subject || {}, obs.value))}</b>`
      : `<span class="absent">${obs.status === "inapplicable" ? "not applicable" : "not known"}</span>`;
    const against = t && !t.absent
      ? ` against ${esc(t.phrase || "")} <b class="num">${esc(t.threshold_from && t.threshold_from.unit
          ? fmtUnit(t.threshold, t.threshold_from.unit)
          : fmtSubject(ev.subject || {}, t.threshold))}</b>${t.threshold_from ? ` — your ${esc(t.threshold_from.label)}` : ""}`
      : t && t.absent ? ` — <span class="absent">no limit is set</span>` : "";
    const [word] = OUTCOME[ev.outcome] || [ev.outcome];
    headline = `<p>${val}${against}${t ? ` — ${esc(word)}.` : ""}</p>`
      + (obs.status !== "known" ? `<div class="m-h">Why there is no number</div><p>${esc(obs.reason || "")}</p>` : "")
      + (t && t.absent ? `<div class="m-h">Why the test never ran</div><p>${esc(t.absent)}</p>` : "")
      + mCautions(obs.cautions) + mProv(obs.provenance);
  } else if (s) {
    const c = (s._computed || {})[a.sid]
      || (C.coverageFor === s.ticker
          && ((C.coverage || {}).entries || []).find((e) => e.id === a.sid))
      || null;
    if (c) {
      headline = c.status === "computed" || c.status === "known"
        ? `<p><b class="num">${esc(fmtMetric(a.sid, c.value))}</b> on the current reading.</p>`
          + mCautions(c.cautions) + mProv(c.provenance)
        : c.status === "inapplicable"
          ? `<p><span class="absent">not applicable</span> — ${esc(c.reason || "")}</p>`
          : `<p><span class="absent">not known</span> — ${esc(c.reason || "")}</p>`;
    }
  }

  const entered = s ? (s._inputs || []).find((r) => r.id === a.sid) : null;
  const typedNow = entered && entered.entered && entered.entered.status === "known";
  const series = entered && (entered.entries || []).length
    ? `<div class="m-h">Your readings</div><table class="m-series">${entered.entries.map((e) =>
        `<tr><td>${esc(String(e.recorded || "").slice(0, 10))} · typed</td><td class="num">${
          e.value === null || e.value === undefined || e.value === ""
            ? '<span class="absent">cleared</span>' : esc(fmtMetric(a.sid, e.value))}</td></tr>`).join("")}</table>`
      + (typedNow ? '<p class="m-quiet">A typed value is kept, dated, and beats anything fetched until you clear it.</p>' : "")
    : "";

  const deriv = full && full.derivation
    ? `<div class="m-h">How it is worked out</div><pre>${esc(full.derivation.formula || "")}</pre>`
      + (full.derivation.window ? `<p class="m-quiet">${esc(full.derivation.window)}</p>` : "")
    : "";
  const misfires = full && (full.explanation || {}).misfires
    ? `<div class="m-h">Where it misfires</div>${prose(full.explanation.misfires)}` : "";
  const whose = full && (full.explanation || {}).attribution
    ? `<div class="m-h">Whose idea</div>${prose(full.explanation.attribution)}` : "";
  const asks = full && full.question
    ? `<div class="m-h">The question you answer</div>${prose(full.question)}` : "";
  const kicker = meta.kind === "qualitative" ? "A question only you can answer"
    : a.kicker || "Measure";
  /* A measure the bank has dropped keeps its row for as long as something
     was typed; its gloss keeps the words it was entered under. */
  const droppedWords = !meta.label && entered ? entered : null;
  return `<p class="m-kicker">${esc(kicker)}</p>
<h3>${esc(meta.label || (droppedWords || {}).label || a.sid)}</h3>
${droppedWords ? '<p class="m-quiet">The bank no longer defines this measure; the words here are the ones it was entered under.</p>' : ""}
${headline}
${meta.plain ? prose(meta.plain) : ""}
${asks}${deriv}${series}${misfires}${whose}
<p class="m-quiet">Bank entry <code>${esc(a.sid)}</code> — the full definition is on the Measures tab.</p>`;
};

function loadBankThen(done) {
  if (C.bank || C.loadingBank) return;
  C.loadingBank = true;
  api("get_bank").then((r) => {
    C.loadingBank = false;
    if (r) C.bank = (r.bank || {}).entries || [];
    else C.bankErr = "The bank could not be read.";
    done && done();
  });
}

/* A non-measure subject on an evidence row: a host fact, a setting, an
   answer, a stated figure, a change since a purchase, a robustness re-test. */
PANES.subject = (a) => {
  const subj = a.ev.subject || {};
  const obs = a.ev.observed || {};
  const kindWords = {
    fact: "A fact about your position or your journal, worked out by the host — never typed.",
    value: "A setting this strategy ships and you can change, on the Strategy page.",
    input: "Something you told this journal at setup.",
    stated: "A figure the strategy worked out itself and stated.",
    change: "How far this has moved since one of your own purchases. Both readings are the journal's — the one frozen at that purchase and the one on record now.",
    robustness: "The same figure worked out again with the single most flattering year taken out — asking whether the rest of the record says the same thing.",
    judgement: "Your own assessment, not a figure the journal worked out.",
  };
  const t = a.ev.test || null;
  return `<p class="m-kicker">${esc(subj.kind === "fact" ? "A fact the journal reports" : "Cited by this verdict")}</p>
<h3>${esc(subj.label || subj.id || "")}</h3>
<p>${obs.status === "known"
    ? `<b class="num">${esc(fmtSubject(subj, obs.value))}</b>`
    : `<span class="absent">${obs.status === "inapplicable" ? "not applicable" : "not known"}</span> — ${esc(obs.reason || "")}`}${
    t && !t.absent ? ` against ${esc(t.phrase || "")} <b class="num">${esc(t.threshold_from && t.threshold_from.unit
      ? fmtUnit(t.threshold, t.threshold_from.unit) : fmtSubject(subj, t.threshold))}</b>${
      t.threshold_from ? ` — your ${esc(t.threshold_from.label)}` : ""}` : ""}</p>
${t && t.absent ? `<div class="m-h">Why the test never ran</div><p>${esc(t.absent)}</p>` : ""}
${subj.explain ? prose(subj.explain) : ""}
${subj.asks ? `<div class="m-h">What you are asked</div>${prose(subj.asks)}` : ""}
${mCautions(obs.cautions)}
${kindWords[subj.kind] ? `<div class="m-h">Where this comes from</div>
<p>${esc(kindWords[subj.kind])}</p>` : ""}
${mProv(obs.provenance)}`;
};

/* The price of one security: what it is, where it came from, what qualifies
   it, and the way to change it. */
PANES.price = (a) => {
  const s = find(a.t);
  if (!s) return PANES.rest();
  const p = s._price || {};
  let body;
  if (p.value == null) {
    body = `<p><span class="absent">No price is on record.</span></p><p>${esc(p.reason || "")}</p>
<div class="m-h">The way back</div>
<p>Fetch data to pull this security's own closes, or type the price you see quoted — a typed value is kept and beats a fetch until you clear it.</p>`;
  } else if (p.source === "manual") {
    body = `<p><b class="num">${money(p.value)}</b> · typed</p>
<p class="caution">Qualified — ${esc(p.undated || "entered by hand, so it carries no date")}</p>
<p>Dated closes${s._data && s._data.price_through ? ` are stored through ${esc(s._data.price_through)}` : " from a fetch are dated"}, but a typed value beats a fetched one until you clear it. Clear it and the newest close takes over — dated, and refreshed on every fetch. Every figure leaning on this price inherits the same sentence until then.</p>`;
  } else {
    body = `<p><b class="num">${money(p.value)}</b> — the close of ${esc(p.date || "an unknown day")}, fetched.</p>
${p.terminal ? `<p class="caution">Qualified — this price series has ended (${esc(p.terminal.reason || "no reason recorded")}). This is the last close it ever had, not what it trades at.</p>` : ""}
<p>Refreshed on every fetch. If it reads stale, the day beside it is the honest part.</p>`;
  }
  return `<p class="m-kicker">Where this number came from</p>
<h3>Price · ${esc(s.ticker)}</h3>${body}
<button class="m-act" data-m="values" data-arg="${escAttr({ t: s.ticker })}">Edit values</button>`;
};

/* The data behind one security: what is held, when it was fetched, what the
   SEC says the filer is, what went wrong — and the cross-check, because
   whether the stored numbers agree with what the filings say about
   themselves is part of the same trust question. */
PANES.datastatus = async (a) => {
  const s = find(a.t);
  if (!s) return PANES.rest();
  const d = s._data;
  if (!d) {
    return `<p class="m-kicker">The data behind this security</p>
<h3>Nothing has been fetched</h3>
<p>No filings and no price history are stored for ${esc(s.ticker)}. Every figure on its page is typed or absent.</p>
<button class="m-act" data-act="fetch" data-t="${esc(s.ticker)}">Fetch data</button>`;
  }
  const ind = (d.industry || {}).industry || {};
  const indLine = ind.status === "known"
    ? `<p>The SEC classifies this filer as <b>${esc(ind.title || ind.value || "")}</b> (SIC ${esc(ind.sic || ind.value || "")}).</p>${mCautions(ind.cautions)}`
    : `<p><span class="absent">Industry not established</span> — ${esc(ind.reason || "nothing on record says what kind of filer this is")}.</p>`;
  const errs = (d.extraction_error_detail || []).map((e) =>
    `<p class="m-quiet">${esc(e.accession)}: ${esc(e.error)}</p>`).join("");
  /* The cross-check rides on the coverage reply, cached per security. */
  let cc = null;
  if (s.cik) {
    if (C.coverageFor !== s.ticker || !C.coverage) {
      const r = await apiRaw("get_coverage", s.ticker);
      C.coverageFor = s.ticker;
      C.coverage = r.ok ? (r.coverage || { entries: [] })
        : { entries: [], error: r.error };
    }
    cc = (C.coverage || {}).crosscheck || null;
  }
  return `<p class="m-kicker">The data behind this security</p>
<h3>${esc(String(d.filings_held))} filings on record</h3>
<p>Last fetched ${esc(d.last_fetch ? String(d.last_fetch.at).slice(0, 10) : "never")}.
${d.price_through ? ` Prices are stored through ${esc(d.price_through)}.` : " No prices are stored."}</p>
${indLine}
${d.pre_xbrl_filings ? `<p class="m-quiet">${d.pre_xbrl_filings} older filings carry no machine-readable data — a boundary of the source, not an error.</p>` : ""}
${d.extraction_errors ? `<div class="m-h">What could not be read</div>${errs}` : ""}
${(d.terminal_series || []).map((t) => `<p class="caution">The ${esc(t.ticker)} price series has ended${t.reason ? ` — ${esc(t.reason)}` : ""}.</p>`).join("")}
${(d.unquoted_symbols || []).map((u) => `<p class="m-quiet">${esc(u.ticker)}: not carried by the price source${u.reason ? ` — ${esc(u.reason)}` : ""}.</p>`).join("")}
${cc ? crosscheckMargin(cc) : ""}
<p class="m-quiet">The full per-measure inventory — every measure the bank defines and what each computes to here — is behind “Everything stored about this security” at the bottom of its page.</p>`;
};

/* The cross-check, told in the margin: price × shares against the public
   float each 10-K states about itself — an independent test the filings
   themselves supply, which someone wants once. The words carry the state;
   colour repeats it and never stands alone. */
function crosscheckMargin(cc) {
  const checks = cc.checks || [];
  const sum = cc.summary || {};
  if (!checks.length) return "";
  const word = { pass: ["consistent", "o-pass"], warn: ["look closer", "o-unknown"],
    fail: ["inconsistent", "o-fail"], skipped: ["could not run", "o-noted"] };
  const head = sum.fail
    ? `<b class="o-fail">Inconsistent:</b> the tool’s own price × shares disagrees with a public float a filing states about itself — the signature of a wrong price basis, a split, a currency or a share-class error. The rows below say which filings.`
    : sum.warn
      ? `<b class="o-unknown">Look closer:</b> the price × shares comparison is off by more than rounding on ${sum.warn} filing${sum.warn === 1 ? "" : "s"} below.`
      : `The tool’s own price × shares agrees with the public float each 10-K states about itself${sum.ran ? ` — ${sum.ran} filing${sum.ran === 1 ? "" : "s"} compared${sum.skipped ? `, ${sum.skipped} could not run` : ""}` : ""}.`;
  const rows = checks.map((k) => {
    const [w, cls] = word[k.status] || [k.status || "", "o-noted"];
    return `<tr><td>${esc(k.form || "10-K")} · ${esc(k.period || "")}${
      k.ratio !== null && k.ratio !== undefined ? ` <span class="num">${Number(k.ratio).toFixed(2)}×</span>` : ""}
      <br><span class="dim"><code>${esc(k.accession || "")}</code>${k.note ? ` — ${esc(oneline(k.note))}` : ""}</span></td>
      <td class="${cls}">${esc(w)}</td></tr>`;
  }).join("");
  return `<div class="m-h">The cross-check</div>
<p class="m-quiet">${head}</p>
<details><summary>${checks.length} filing${checks.length === 1 ? "" : "s"}, each by accession</summary>
<table class="m-series">${rows}</table></details>`;
}

/* One note, read whole. */
PANES.note = (a) => {
  const s = find(a.t);
  const n = ((s || {}).notes || [])[a.i];
  if (!n) return PANES.rest();
  return `<p class="m-kicker">Your note · ${esc(String(n.date || n.recorded || "").slice(0, 10))}</p>
<h3>${esc(s.ticker)}</h3>${prose(n.text)}
<p class="m-quiet">Notes are dated and appended, never edited.</p>`;
};

/* The thesis, read whole, with its history. */
PANES.thesis = (a) => {
  const s = find(a.t);
  if (!s) return PANES.rest();
  const t = s._thesis || {};
  if (t.status !== "known") {
    return `<p class="m-kicker">Your record · absent</p>
<h3>Why I own this</h3>
<p>${esc(t.reason || "Nothing is written yet.")}</p>
<p class="m-quiet">Both parts are optional and strongly recommended: why you own it, and what would make you wrong. Every purchase freezes the version standing that day.</p>
<button class="m-act" data-m="thesisedit" data-arg="${escAttr({ t: s.ticker })}">Write it</button>`;
  }
  const v = t.version || {};
  const earlier = (t.history || []).slice(1);
  return `<p class="m-kicker">Your record · written ${esc(t.amended || "")}</p>
<h3>Why I own this</h3>
${prose(v.thesis)}
${v.falsifier ? `<div class="m-h">What would make me wrong</div>${prose(v.falsifier)}` : ""}
${v.reason ? `<div class="m-h">Changed because</div>${prose(v.reason)}` : ""}
${mCautions(t.cautions)}
${earlier.length ? `<details><summary>${earlier.length} earlier version${earlier.length === 1 ? "" : "s"}</summary>${earlier.map((h) =>
    `<div class="m-note">${prose(h.thesis)}${h.falsifier ? `<div class="m-h">What would make me wrong</div>${prose(h.falsifier)}` : ""}${h.reason ? `<div class="m-h">Changed because</div>${prose(h.reason)}` : ""}</div>`).join("")}</details>` : ""}
<p class="m-quiet">Amending keeps every prior version and asks why it changed.</p>
<button class="m-act" data-m="thesisedit" data-arg="${escAttr({ t: s.ticker })}">Amend</button>`;
};

/* One recorded lot: the frozen record of that day, never recomputed. */
PANES.lot = (a) => {
  const s = find(a.t);
  const lot = s && lotById(s)[a.id];
  if (!lot) return PANES.rest();
  const snap = lot.snapshot || {};
  const d = snap.decision || null;
  const sale = lot.kind === "sell" || !!lot.reason;
  const recon = reconstructed(lot);
  const ov = lot.override || null;
  const what = `${sale ? "Sold" : "Bought"} ${esc(String(lot.shares))} at ${money(lot.price)}`;
  const heading = sale
    ? (lot.rule_triggered === false ? `${what} — against the signal`
      : lot.rule_triggered ? `${what} — the rule called for it` : what)
    : (lot.unreconstructed ? `${what} — no verdict could be rebuilt`
      : ov ? `${what} — against the signal` : `${what} — with the signal`);
  const frozenState = lot.unreconstructed
    ? `<p>No verdict could be rebuilt for its day, so nothing is recorded
       about what your rules would have said — and it is <b>not</b> counted as
       acting against a signal, because there was none to go against. That
       distinction is what makes the override record mean anything.</p>`
    : d
      ? `<p>The verdict that day read <b>${esc((d.state || {}).name || "")}</b>${
          (d.reason || {}).summary ? ` — ${esc(d.reason.summary)}` : ""}.
         Frozen with it: every figure, in the words and thresholds in force then.
         It is never recomputed — today's page and this record may disagree, and that difference is the story.</p>`
      : "<p>No verdict is on this entry: nothing was recorded about what your rules said.</p>";
  const strategyLine = snap.strategy
    ? `<p class="m-quiet">${esc(snap.strategy.name || "")} v${esc(snap.strategy.version)}${
        snap.strategy.values_version != null ? ` · settings v${esc(snap.strategy.values_version)}` : ""} on the day.</p>` : "";
  const reasonBox = ov && ov.reason
    ? `<div class="m-h">Why, in your words at the time</div>${prose(ov.reason)}` : "";
  const saleReason = sale && lot.reason
    ? `<div class="m-h">Why you sold</div><p>${esc(lot.reason)}</p>` : "";
  const recollection = (snap.recollection || {}).text
    ? `<div class="m-h">Written in hindsight</div>${prose(snap.recollection.text)}
       <p class="m-quiet">A recollection, written ${esc(String((snap.recollection || {}).recorded || "").slice(0, 10))} about ${esc(lot.date)} — never counted as the case made at the time.</p>` : "";
  const evRows = d && ((d.reason || {}).evidence || []).length
    ? `<details><summary>Every frozen figure</summary>${frozenEvidence(d)}</details>` : "";
  return `<p class="m-kicker">The record of ${esc(lot.date)} · frozen${recon ? " · from history" : ""}</p>
<h3>${heading}</h3>
${recon ? '<p class="m-quiet">Entered from history: the verdict beside it was rebuilt from the data available on that day, not seen at the time.</p>' : ""}
${frozenState}${strategyLine}${saleReason}${reasonBox}${recollection}${evRows}`;
};

/* A frozen decision's evidence, compact, for the margin. Same row logic as
   the plane's table, rendered narrow. */
function frozenEvidence(d) {
  const rows = ((d.reason || {}).evidence || []).map((ev) => {
    const subj = ev.subject || {};
    const obs = ev.observed || {};
    const [word] = OUTCOME[ev.outcome] || [ev.outcome];
    const val = obs.status === "known"
      ? `<span class="num">${esc(fmtSubject(subj, obs.value))}</span>${cmMark(obs.cautions)}`
      : `<span class="absent">${obs.status === "inapplicable" ? "not applicable" : "not known"}</span>`;
    return `<tr><td>${esc(subj.label || subj.id || "")}</td><td>${val} · ${esc(word)}</td></tr>`;
  }).join("");
  return `<table class="m-series">${rows}</table>`;
}
