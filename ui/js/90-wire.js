/* Wiring: one render loop, one click handler, one change handler.

   Everything actionable is declared in the markup — data-m opens a margin
   pane, data-do runs an action, data-act is navigation and the handful of
   direct verbs. No element holds its own listener, so a re-render never
   orphans one. */

function render() {
  if (!S) return;
  renderMast();
  renderTabs();
  /* The margin's resting state paints once at startup; render never touches
     an open pane, so typing in one survives a background refresh. */
  if (!$("margin").innerHTML) marginRest();
  const v = $("view");
  if (!S.journal) {
    v.innerHTML = welcomeView();
    applyGates(v);
    $("foot").innerHTML = footText();
    return;
  }
  if (openTicker) {
    const s = find(openTicker);
    if (!s) { closeSecurity(); return render(); }
    v.innerHTML = banners() + detailView(s);
  } else if (tab === "strategy") v.innerHTML = strategyView();
  else if (tab === "measures") v.innerHTML = measuresView();
  else if (tab === "data") v.innerHTML = dataView();
  else if (tab === "analytics") v.innerHTML = analyticsView();
  else v.innerHTML = banners() + listView();
  applyGates(v);
  $("foot").innerHTML = footText();
}
function footText() {
  return `<p>This tool never places a trade and holds no broker credentials. A journal has one strategy, chosen when it is created.</p>
  <p>Your data lives at ${esc(S.data_dir || "")} — outside this program’s folder, never uploaded.</p>`;
}

/* Restore typed welcome fields across a re-render (choosing a strategy
   re-draws the declared inputs). */
function keepWelcomeFields(fn) {
  const kept = {};
  document.querySelectorAll('#view [name]').forEach((el) => { kept[el.name] = el.value; });
  fn();
  document.querySelectorAll('#view [name]').forEach((el) => {
    if (kept[el.name] !== undefined && el.type !== "checkbox") el.value = kept[el.name];
  });
  applyGates($("view"));
}

async function createJournalFromWelcome() {
  const get = (n) => { const el = document.querySelector(`#view [name="${n}"]`); return el ? el.value : ""; };
  const err = (msg) => { const box = $("w_err"); if (box) { box.style.display = "block"; box.textContent = msg; } };
  if (!chosenStrategy) return err("Pick a strategy first — it is the one permanent choice.");
  if (!get("w_name").trim()) return err("Name the journal.");
  const sec = get("w_sec").trim();
  if (sec && sec !== ((S.data_security || {}).sec_identity || "")) {
    const r = await apiRaw("save_sec_identity", sec);
    if (!r.ok) return err(r.error);
  }
  const key = get("w_key").trim();
  if (key) {
    const r = await apiRaw("save_api_key", key);
    if (!r.ok) return err(r.error);
  }
  const inputs = {};
  document.querySelectorAll('#view [name^="in_"]').forEach((el) => { inputs[el.name.slice(3)] = el.value; });
  const r = await apiRaw("create_journal", get("w_name"), chosenStrategy, inputs,
    get("w_cash") || null, get("w_cash_on") || null);
  if (!r.ok) return err(r.error);
  if (r.cash_problem) toast("The journal is created, but the opening cash was refused: " + r.cash_problem, true);
  tab = "list";
  await refresh();
  refreshTimeframe();
}

/* The state-fix verbs, from the host's own table: each key names the screen
   that resolves a stopped state. A key the view does not know falls through
   to nothing rather than to a wrong screen. */
const FIX_ACTIONS = {
  settings: () => margin("settings", {}),
  thesis: (t) => margin("thesisedit", { t }),
  judgement: () => {
    const el = document.getElementById("judgements");
    if (el && el.scrollIntoView) el.scrollIntoView({ behavior: "smooth" });
  },
  list: () => margin("importlist", {}),
};

document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-m],[data-do],[data-act],[data-mclose],[data-bfadd],[data-bfdel]");
  if (!btn) return;

  if (btn.hasAttribute("data-mclose")) { marginRest(); return; }

  if (btn.dataset.bfadd) {
    const st = bfRead();
    st.rows.push({ kind: btn.dataset.bfadd, date: "", shares: "", price: "" });
    margin("backfill", { t: (M.arg || {}).t, state: { ...st, preview: null } });
    return;
  }
  if (btn.dataset.bfdel !== undefined && btn.dataset.bfdel !== "") {
    const st = bfRead();
    st.rows.splice(Number(btn.dataset.bfdel), 1);
    margin("backfill", { t: (M.arg || {}).t, state: { ...st, preview: null } });
    return;
  }

  if (btn.dataset.m) {
    ev.stopPropagation();
    let arg = {};
    try { arg = JSON.parse(btn.dataset.arg || "{}"); } catch (e) { arg = {}; }
    if (btn.dataset.m === "row") arg.rowKey = (btn.closest("tr") || {}).dataset ? btn.closest("tr").dataset.rowkey : null;
    if (btn.dataset.m === "newjournal" && M.id === "newjournal") {
      /* Re-picking the strategy repaints the pane; the typed name and
         answers survive it. */
      const kept = marginForm();
      margin("newjournal", arg);
      $("margin").querySelectorAll("[name]").forEach((el) => {
        if (kept[el.name] !== undefined && el.type !== "checkbox") el.value = kept[el.name];
      });
      applyGates($("margin"));
      return;
    }
    margin(btn.dataset.m, arg);
    return;
  }

  if (btn.dataset.do) {
    ev.stopPropagation();
    const verb = btn.dataset.do;
    const table = {
      buy: () => doBuy(btn), sell: () => doSell(btn),
      bfcheck: () => doBackfill(btn, false), bfrecord: () => doBackfill(btn, true),
      ev: () => doEV(btn), values: () => doValues(btn),
      judgement: () => doJudgement(btn), thesis: () => doThesis(btn),
      note: () => doNote(btn), snapshot: () => doSnapshot(btn),
      discardsnap: () => doDiscardSnap(btn), compare: () => doCompare(btn),
      cash: () => doCash(), settings: () => doSettings(),
      newjournal: () => doNewJournal(btn), renamejournal: () => doRenameJournal(),
      deletejournal: () => doDeleteJournal(),
      add: () => doAdd(), addbulk: () => doAddBulk(),
      importlist: () => doImportList(), passover: () => doPassOver(btn),
      explain: () => doExplain(btn),
      secidentity: () => doSecIdentity(), savekey: () => doSaveKey(),
      testkey: () => doTestKey(), removekey: () => doRemoveKey(),
      valdefaults: () => doValDefaults(), importdata: () => doImportData(),
      emptyjournal: () => doEmptyJournal(), remove: () => doRemove(btn),
    };
    if (table[verb]) await table[verb]();
    return;
  }

  const act = btn.dataset.act;
  if (!act) return;
  ev.stopPropagation();
  if (act === "tab") { closeSecurity(); tab = btn.dataset.tab; render(); }
  else if (act === "filter") { closeSecurity(); tab = "list"; filter = btn.dataset.filter; render(); }
  else if (act === "sort") { sortBy = sortBy === "asks" ? "amount" : "asks"; render(); }
  else if (act === "open") { openSecurity(btn.dataset.t, btn.dataset.p || null); C.coverageFor = null; render(); window.scrollTo(0, 0); }
  else if (act === "back") { closeSecurity(); if (tab === "analytics") tab = "list"; render(); }
  else if (act === "analytics") { closeSecurity(); tab = "analytics"; render(); marginRest(); }
  else if (act === "problemsfirst") { problemsFirst = !problemsFirst; render(); }
  else if (act === "coverage-retry") { C.coverage = null; C.coverageFor = null; render(); }
  else if (act === "fetchall") {
    /* Per-name, never blocking: each fetch runs in the backend's own
       thread and lands its own toast; the first name that finishes can be
       acted on without waiting for the last. */
    const targets = (S.securities || []).filter((s) =>
      !s._data && !(s._fetch && s._fetch.running));
    for (const s of targets) {
      const r = await apiRaw("fetch_security", s.ticker);
      if (r.ok) startFetchPoll(s.ticker);
      else toast(`${s.ticker}: ${r.error}`, true);
    }
    await refresh();
  }
  else if (act === "bankscope") { showWholeBank = btn.dataset.scope === "all"; render(); }
  else if (act === "timeframe") { timeframe = btn.dataset.tf; refreshTimeframe().then(() => margin("timeframe", {})); }
  else if (act === "fetch") {
    const t = btn.dataset.t;
    const r = await apiRaw("fetch_security", t);
    if (!r.ok) { toast(r.error, true); return; }
    startFetchPoll(t);
    await refresh();
  }
  else if (act === "export") {
    const r = await apiRaw("export_data");
    if (!r.ok) toast(r.error, true);
    else if (!r.cancelled) toast(`Exported to ${r.path}.`);
  }
  else if (act === "openjournal") {
    const r = await apiRaw("open_journal", btn.dataset.id);
    if (!r.ok) { toast(r.error, true); return; }
    closeSecurity(); tab = "list"; filter = "everything";
    marginRest();
    await refresh(); refreshTimeframe();
  }
  else if (act === "choosestrategy") {
    keepWelcomeFields(() => { chosenStrategy = btn.dataset.id; render(); });
  }
  else if (act === "createjournal") await createJournalFromWelcome();
  else if (act === "track") {
    const r = await apiRaw("add_security", btn.dataset.t, btn.dataset.name || "");
    if (!r.ok && !/already/.test(r.error || "")) { toast(r.error, true); return; }
    await refresh();
    refreshTimeframe();
    openSecurity(btn.dataset.t); render();
  }
  else if (FIX_ACTIONS[act]) FIX_ACTIONS[act](btn.dataset.t || openTicker);
});

/* Date pickers inside act panes re-preview on change, keeping typed values.
   The measure search filters as you type without stealing focus. */
document.addEventListener("change", (ev) => {
  const el = ev.target;
  if (el.id === "buy_date") {
    const f = marginForm();
    /* The fallback is the date the pane was last built for — by the time
       this fires, the field already holds the new one. */
    margin("buy", { t: (M.arg || {}).t, when: el.value, keep: f,
      fallback: (M.arg || {}).when || localToday() });
  } else if (el.id === "sell_date") {
    const f = marginForm();
    margin("sell", { t: (M.arg || {}).t, when: el.value, keep: f,
      fallback: (M.arg || {}).when || localToday() });
  } else if (el.id === "ev_method") {
    const f = marginForm();
    const keep = {};
    Object.entries(f).forEach(([k, v]) => { if (k.startsWith("ev_") && k !== "ev_method") keep[k.slice(3)] = v; });
    margin("ev", { t: (M.arg || {}).t, method: el.value, keep });
  } else if (el.closest && el.closest("[data-bfrow]") && M.id === "backfill") {
    /* An edit after a check makes the shown per-row verdicts stale; the
       form re-renders unchecked, keeping what was typed. */
    const st = bfRead();
    margin("backfill", { t: (M.arg || {}).t, state: { ...st, preview: null } });
  } else if (el.closest && el.closest("#margin")) {
    applyGates($("margin"));
  } else if (el.closest && el.closest("#view")) {
    applyGates($("view"));
  }
});
document.addEventListener("input", (ev) => {
  if (ev.target.id === "banksearch") {
    measureSearch = ev.target.value;
    const el = ev.target;
    const pos = el.selectionStart;
    render();
    const again = $("banksearch");
    if (again) { again.focus(); again.setSelectionRange(pos, pos); }
  }
});
document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape") return;
  if (M.id !== "rest") {
    /* A pane holding typed work is closed with ✕, never wiped by a stray
       Escape — a written override reason is the one thing this program
       asks for and must not destroy. */
    const typed = Array.from($("margin").querySelectorAll("textarea[name], input[name]:not([type=date])"))
      .some((el) => (el.value || "").trim() !== "" && !el.readOnly);
    if (!typed) marginRest();
    return;
  }
  if (openTicker) { closeSecurity(); render(); }
});

window.addEventListener("pywebviewready", () => { refresh().then(refreshTimeframe); });
if (window.pywebview && window.pywebview.api) refresh().then(refreshTimeframe);
