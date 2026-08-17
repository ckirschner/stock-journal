/* The menu: chrome opens where it was clicked.

   The rule that owns this file: if it is about a security, it goes in the
   margin; if it is chrome — switching journals, picking a window, a toolbox
   of doors — it opens right under the thing that was clicked and closes the
   moment the choice is made. A menu never evicts the margin, so someone
   reading why a measure failed can switch journals without losing their
   place.

   A menu entry is a function (arg) -> html, registered here and in 50-act.
   One menu is open at a time, anchored to the element that opened it. */

/* eslint-disable no-unused-vars */

const MENUS = {};
let MENU = { id: null, arg: null };

function menuEl() {
  let el = $("menu");
  if (!el) {
    el = document.createElement("div");
    el.id = "menu";
    el.className = "menu";
    document.body.appendChild(el);
  }
  return el;
}

function menuOpen(id, arg, anchor) {
  const entry = MENUS[id];
  if (!entry) return;
  MENU = { id, arg };
  const el = menuEl();
  el.innerHTML = entry(arg);
  el.hidden = false;
  applyGates(el);
  /* Under the anchor, pulled left if it would leave the window. */
  const r = anchor.getBoundingClientRect();
  el.style.top = `${Math.round(r.bottom + 6)}px`;
  let left = Math.round(r.left);
  const w = el.offsetWidth;
  if (left + w > window.innerWidth - 8) left = Math.max(8, Math.round(r.right - w));
  el.style.left = `${left}px`;
  const over = r.bottom + 6 + el.offsetHeight - window.innerHeight;
  if (over > 0) el.style.maxHeight = `${Math.max(160, el.offsetHeight - over - 12)}px`;
  else el.style.maxHeight = "";
}

function menuClose() {
  MENU = { id: null, arg: null };
  const el = $("menu");
  if (el) { el.hidden = true; el.innerHTML = ""; }
}

/* Swap what the open menu shows without moving it — a form inside the menu
   (rename, delete) replaces the list that offered it. The height bound is
   recomputed, because the replacement can be taller than what it replaced
   and a fixed panel that outgrows the window with no bound cannot scroll —
   whatever fell below the fold would be unreachable. */
function menuSwap(id, arg, keepTyped) {
  const el = $("menu");
  if (!el || el.hidden) return;
  const kept = keepTyped ? menuForm() : {};
  MENU = { id, arg };
  el.innerHTML = (MENUS[id] || (() => ""))(arg);
  el.querySelectorAll("[name]").forEach((f) => {
    if (kept[f.name] !== undefined && f.type !== "checkbox") f.value = kept[f.name];
  });
  applyGates(el);
  const top = parseFloat(el.style.top) || 0;
  const over = top + el.offsetHeight - window.innerHeight;
  el.style.maxHeight = over > 0
    ? `${Math.max(160, el.offsetHeight - over - 12)}px` : "";
}

/* Read every [name] field in the menu, as strings. */
function menuForm() {
  const data = {};
  const el = $("menu");
  if (el) el.querySelectorAll("[name]").forEach((f) => { data[f.name] = f.value; });
  return data;
}
/* Show a problem inside the menu, where the person is standing. */
function menuErr(msg) {
  const el = $("menu");
  if (!el) return;
  let box = el.querySelector(".m-err[data-live]");
  if (!box) {
    box = document.createElement("div");
    box.className = "m-err";
    box.setAttribute("data-live", "1");
    el.appendChild(box);
  }
  box.textContent = msg;
}

/* ------------------------------------------------------------ the menus */
/* The journal pill: the journal's own facts, the other journals, and the
   housekeeping that is about the journal as a container — never about a
   security. Looking back is a tab now, not a burrow. */
MENUS.journal = () => {
  const others = (S.journals || []).filter((j) => j.id !== (S.journal || {}).id);
  return `<p class="mn-kicker">This journal</p>
<p class="mn-line"><b>${esc(journalName())}</b></p>
<p class="mn-quiet">Created ${esc(String((S.journal || {}).created || "").slice(0, 10))} · stamped with ${esc(((S.journal || {}).strategy || {}).name || "")} — one strategy per journal, chosen once.</p>
${others.length ? `<div class="mn-h">Switch to</div>${others.map((j) =>
    `<button class="mn-item" data-act="openjournal" data-id="${esc(j.id)}">${esc(j.name)}</button>`).join("")}` : ""}
<div class="mn-h">Housekeeping</div>
<button class="mn-item" data-act="newjournal">Start another journal <span class="dim">— a second journal means a second real account</span></button>
<button class="mn-item" data-menu="renamejournal" data-arg="{}">Rename this journal</button>
<button class="mn-item" data-menu="deletejournal" data-arg="{}">Delete this journal</button>`;
};

MENUS.renamejournal = () => `<p class="mn-kicker">Rename</p>
<p class="mn-quiet">The name is a label; the record underneath does not move and no reason is owed.</p>
<label>New name</label><input name="name" value="${esc(journalName())}">
<button class="m-act" data-do="renamejournal">Rename</button>`;

MENUS.deletejournal = () => {
  const n = (S.securities || []).length;
  return `<p class="mn-kicker">Delete this journal</p>
<p class="mn-line"><b>Everything it holds goes with it</b></p>
<p class="mn-quiet">${n} securit${n === 1 ? "y" : "ies"}, every lot, every note, every frozen decision — none of it can be recovered. <b>Export it first</b> if there is any doubt.</p>
<button class="m-act quiet" data-act="export">Export it first</button>
<label>Type the journal’s name to confirm</label>
<input name="confirm_name" placeholder="${esc(journalName())}">
<button class="m-act warn" data-do="deletejournal">Delete it</button>`;
};

/* Starting another journal is a screen, not a menu — a permanent decision
   plus a form needs room to breathe and to scroll, and a dropdown offers
   neither. The menu item above opens it (see newJournalView). */

/* The header's window picker. Picking is chrome and happens here; what the
   figure means stays a margin gloss on the figure itself. */
MENUS.timeframe = () => {
  const acct = T && T.account;
  const ch = acct && acct.change;
  const pc = acct && acct.percent;
  const line = !T ? ""
    : T.error ? `<p class="mn-quiet"><span class="absent">not known</span> — ${esc(T.error)}</p>`
    : ch && ch.status === "known"
      ? `<p class="mn-quiet">The account moved <b class="num">${money0(ch.value)}</b>${pc && pc.status === "known"
          ? ` (<b class="num">${pc.value >= 0 ? "+" : "−"}${Math.abs(pc.value).toFixed(1)}%</b>)` : ""} since ${esc(T.since || "")}.</p>`
      : "";
  return `<p class="mn-kicker">The timeframe</p>
${TIMEFRAMES.map((t) =>
    `<button class="mn-item ${t.id === timeframe ? "on" : ""}" data-act="timeframe" data-tf="${t.id}">${esc(t.label)}${t.id === timeframe ? " ✓" : ""}</button>`).join("")}
${line}
<p class="mn-quiet">Every row’s “${esc((T && T.label) || "timeframe")}” column reads over the same window.</p>`;
};

/* The rest of one security's toolbox. The doors are chrome; each one opens
   its pane in the margin, where acting lives. */
MENUS.more = (a) => {
  const s = find(a.t);
  if (!s) return "";
  const onList = S.list && (S.list.rows || []).some((r) => r.ticker === s.ticker && !r.held && !r.passed_over);
  return `<p class="mn-kicker">More · ${esc(s.ticker)}</p>
<button class="mn-item" data-m="values" data-arg="${escAttr({ t: s.ticker })}">Edit values <span class="dim">— typed figures, dated, beating fetched ones</span></button>
<button class="mn-item" data-m="ev" data-arg="${escAttr({ t: s.ticker })}">Expected value <span class="dim">— assumptions in, value solved for</span></button>
<button class="mn-item" data-m="thesisedit" data-arg="${escAttr({ t: s.ticker })}">Why I own this</button>
<button class="mn-item" data-m="backfill" data-arg="${escAttr({ t: s.ticker })}">Enter history <span class="dim">— purchases and sales from your records</span></button>
${onList ? `<button class="mn-item" data-m="passover" data-arg="${escAttr({ t: s.ticker, name: s.name || "" })}">Not buying this one</button>` : ""}
${s._removable ? `<button class="mn-item" data-m="remove" data-arg="${escAttr({ t: s.ticker })}">Remove from the journal</button>`
    : `<p class="mn-quiet">Remove — unavailable: this security carries recorded history, and the record does not delete.</p>`}`;
};
