"""Ledger. A portfolio journal that checks holdings against a strategy you
committed to in advance.

    python app.py            run the app
    python app.py --reset    delete local data and start empty

The app never places a trade and has no broker credentials. It reads what you
tell it, asks the strategy your journal is stamped with what that means, and
shows you the answer with the figures behind it.

A journal has exactly one strategy and it does not change. This file is the
JS-facing API; it holds no view about any security, and every verdict on
every screen comes from one call to engine.contract.evaluate.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import threading
import traceback
from datetime import date
from pathlib import Path

import webview

from engine import (backup, bank, contract, context, dataview, fetch,
                    journals, portfolio, secrets, store, strategy_loader,
                    strategy_values, tickermap, tiingo)
from engine.expected_value import EV_METHODS, EVError
from engine.expected_value import compute as compute_ev
from engine.portfolio import EXIT_REASONS

UI_DIR = Path(__file__).resolve().parent / "ui"


def ok(**kw):
    return {"ok": True, **kw}


def err(message):
    return {"ok": False, "error": str(message)}


def guarded(fn):
    """Any exception becomes a message in the UI rather than a dead window."""
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except (EVError, ValueError, store.StoreError) as e:
            return err(e)
        except Exception as e:                      # noqa: BLE001
            traceback.print_exc()
            return err(f"{type(e).__name__}: {e}")
    wrapper.__name__ = fn.__name__
    return wrapper


def locked(fn):
    """Serialize a journal read-modify-write cycle. Stacks under @guarded."""
    def wrapper(self, *a, **kw):
        with self._doc_lock:
            return fn(self, *a, **kw)
    wrapper.__name__ = fn.__name__
    return wrapper


class Api:
    def __init__(self):
        self.window = None
        # pywebview runs every JS call on its own thread, and the fetch
        # completion writes from a background thread. Every load-mutate-save
        # cycle on a journal goes through this lock, or two concurrent writes
        # silently drop each other's changes — including hand-entered values,
        # which nothing may ever overwrite.
        self._doc_lock = threading.RLock()

    # -- the open journal and its strategy --------------------------------
    def _strategies(self):
        """(loadable strategies by id, one report per bundle found).

        Rediscovered on every read rather than cached, which is what lets a
        strategy edited on disk be *seen* — and a threshold edited in place
        without a version bump is exactly the change the rule-change record
        exists to catch.
        """
        return strategy_loader.discover()

    def _open(self, jid=None):
        """(journal, record, chain, reports) for the journal in view.

        Records any distance between what this journal last ran under and the
        strategy on disk before anything is scored under it, so a rule change
        is on the books before the first verdict that uses it. journal is
        None when none exists yet; record is None when the stamped strategy
        is not installed here.
        """
        strategies, reports = self._strategies()
        jid = jid or journals.resolve_open()
        if jid is None:
            return None, None, None, reports
        journal = journals.load(jid)
        stamp = journal.get("strategy") or {}
        record = strategies.get(stamp.get("id"))
        if record is None:
            return journal, None, None, reports
        chain = strategy_values.resolve(
            record, layers=[("this journal's settings",
                             journal.get("config") or {})])
        if not chain["errors"]:
            if journals.observe_rule_change(journal, record, chain["values"]):
                journals.save(journal)
        return journal, record, chain, reports

    def _find(self, journal, ticker):
        for s in journal.get("securities", []):
            if s["ticker"] == ticker:
                return s
        raise ValueError(f"{ticker} is not in this journal.")

    # -- computed values --------------------------------------------------
    def _tickers_of(self, s):
        """Every symbol the SEC maps to this security's company (share
        classes are separate symbols), from the cached snapshot only —
        rendering never touches the network."""
        cik = s.get("cik")
        if cik:
            mapped = tickermap.tickers_for(tickermap.load_cached(), cik)
            if mapped:
                if s["ticker"] not in mapped:
                    mapped.append(s["ticker"])
                return mapped
        return [s["ticker"]]

    def _computed_layer(self, s, entry_ids):
        """The security's computed values and status, or empty layers when
        nothing has been fetched. Never raises — a broken data layer must not
        take the journal down with it, and must never block recording."""
        cik = s.get("cik")
        if not cik:
            return {}, dataview.price_view(s, None, [s["ticker"]]), None, \
                [s["ticker"]]
        tickers = self._tickers_of(s)
        try:
            computed = dataview.computed_results(cik, tickers, entry_ids)
            price = dataview.price_view(s, cik, tickers)
            status = dataview.data_status(cik)
        except Exception as e:                          # noqa: BLE001
            traceback.print_exc()
            return {}, dataview.price_view(s, None, [s["ticker"]]), \
                {"error": f"the data layer failed: {e}"}, tickers
        return computed, price, status, tickers

    def _data_security(self):
        """What the UI may know about the key: that one exists and where it
        lives — never the key itself."""
        try:
            configured = bool(secrets.get_secret("tiingo_api_token"))
            problem = None
        except secrets.SecretsError as e:
            configured, problem = False, str(e)
        return {
            "key_configured": configured,
            "storage": secrets.storage(),
            "sec_identity": str(secrets.local_get("sec_identity") or ""),
            "problem": problem,
        }

    # -- strategies -------------------------------------------------------
    def _strategy_offer(self, record):
        """One strategy as the creation screen needs it: what it is, and the
        questions it will ask. The setup screen is generated from this, so a
        journal only ever asks for the fields its own strategy uses."""
        return {
            "id": record["id"], "name": record["name"],
            "summary": record["summary"], "version": record["version"],
            "values_version": record.get("values_version"),
            "contract": record["contract"],
            "states": list(record["states"]),
            "inputs": list(record.get("inputs") or []),
        }

    def _strategy_view(self, record, chain, journal):
        """The stamped strategy, for the Strategy tab. Its declared values
        carry the resolved value *and* where it came from, so the screen can
        always say "yours: 12 (shipped default: 15)" — the resolution is a
        view and never loses a side.

        The declared inputs carry the same treatment: the answer on record,
        whether the question currently applies, and why not when it doesn't.
        One screen edits both, because a value and an input differ in where
        the default comes from rather than in how they are set.
        """
        values = []
        for v in (record.get("values") or []):
            values.append({
                **v,
                "value": chain["values"].get(v["id"]),
                "source": chain["sources"].get(v["id"]),
                "shipped": (record.get("defaults") or {}).get(v["id"]),
            })
        # Only what the strategy still declares, exactly as the decision
        # path reads it. A journal can outlive an input the strategy has
        # dropped, and reporting that leftover as something the user owes an
        # answer for would name a problem they cannot act on.
        declared = {f["id"] for f in (record.get("inputs") or [])}
        supplied = {k: v for k, v in (journal.get("inputs") or {}).items()
                    if k in declared}
        activity = contract.input_activity(record, supplied)
        _, problems = contract.check_inputs(record, supplied, chain["values"])
        inputs = [{**f, "value": supplied.get(f["id"]),
                   "inactive": activity.get(f["id"])}
                  for f in (record.get("inputs") or [])]
        return {
            **self._strategy_offer(record),
            "changelog": {str(k): v
                          for k, v in (record.get("changelog") or {}).items()},
            "values": values,
            "inputs": inputs,
            "input_problems": problems,
            "value_errors": list(chain["errors"]),
            "roles": {k: dict(v) for k, v in contract.INPUT_ROLES.items()},
            "bundle": Path(record["dir"]).name,
            "reference": sorted(record.get("reference") or {}),
        }

    def _typed(self, specs, raw):
        """What a form sent, in the types the declaration asked for.

        Every field arrives from a browser as text. Coercing here rather
        than in the view keeps the one place that knows what a field IS —
        the declaration — as the only place that decides how it is read.

        A field left blank is never zero: it comes back as None, meaning
        clear the answer or drop the override so the chain falls back to
        what the strategy ships. A field the payload does not mention at
        all is absent from the result and left exactly as it was — the two
        must not collapse, or a caller that names one field would silently
        delete every other answer in the journal.

        Raises with the field's own label on anything that will not
        convert, because "must be a number" is only useful beside the
        question it belongs to.
        """
        typed = {}
        for spec in (specs or []):
            if spec["id"] not in (raw or {}):
                continue
            value = raw[spec["id"]]
            if value is None or (isinstance(value, str) and not value.strip()):
                typed[spec["id"]] = None
                continue
            try:
                if spec["type"] == "integer":
                    typed[spec["id"]] = int(str(value).strip())
                elif spec["type"] == "number":
                    typed[spec["id"]] = float(str(value).strip())
                elif spec["type"] == "boolean":
                    typed[spec["id"]] = (value if isinstance(value, bool) else
                                         str(value).strip().lower()
                                         in ("true", "yes", "on", "1"))
                else:
                    typed[spec["id"]] = str(value)
            except (TypeError, ValueError):
                raise ValueError(
                    f'"{spec["label"]}" must be '
                    + ("a whole number." if spec["type"] == "integer"
                       else "a number."))
        return typed

    # -- deciding ---------------------------------------------------------
    def _decide(self, security, securities, journal, record, chain,
                as_of=None):
        """One state for one security, always. Every way this can fail comes
        back in the same envelope, produced by the host and saying so."""
        stamp = journal.get("strategy") or {}
        if record is None:
            return contract.host_result(
                "host:strategy-missing",
                f'{stamp.get("name") or stamp.get("id")} is not installed on '
                "this machine, so no new verdict can be produced. Everything "
                "already recorded stays readable.", stamp)
        if chain["errors"]:
            return contract.host_result(
                "host:values-unresolved",
                f'{record["name"]}’s settings could not be resolved: '
                + " ".join(chain["errors"]), record)
        # contract.evaluate never raises, but building what it is given can:
        # a corrupt filing file or an unreadable price document throws before
        # the strategy is ever reached. That must not become a purchase the
        # user cannot record — a tool that refuses to write down a decision
        # because it cannot score it is a gate, and there are none here.
        # Only what the strategy declares reaches it. A journal can outlive
        # an input the strategy has since dropped, and a leftover answer is
        # not the strategy's business — leaving it in would refuse every
        # verdict from then on, over a key the user has no way to delete.
        # Which of the surviving answers currently *apply*, and which of
        # them the host may report as a figure, is the declaration's
        # business and is settled inside build_context.
        declared = {f["id"] for f in (record.get("inputs") or [])}
        supplied = {k: v for k, v in (journal.get("inputs") or {}).items()
                    if k in declared}
        try:
            ctx = context.build_context(security, securities,
                                        chain["values"], supplied,
                                        as_of=as_of, record=record)
        except Exception as e:                          # noqa: BLE001
            traceback.print_exc()
            return contract.host_result(
                "host:data-unreadable",
                f"The stored data for {security.get('ticker')} could not be "
                f"read ({type(e).__name__}: {e}), so {record['name']} was "
                "not asked. Fetching again replaces anything transient.",
                record)
        return contract.evaluate(record, ctx)

    def _cited_ids(self, decision) -> list:
        """The bank measures this decision actually looked at. It is what the
        Edit-metrics dialog offers: the numbers this strategy reads for this
        security, never the whole bank."""
        out = []
        for item in ((decision or {}).get("reason") or {}).get("evidence", []):
            subj = item.get("subject") or {}
            if subj.get("kind") == "measure" and subj.get("id") not in out:
                out.append(subj["id"])
        return out

    # -- read ------------------------------------------------------------
    @staticmethod
    def _cycle_view(security, cycle, price) -> dict:
        """One holding period, as the screens read it.

        Lots go by id rather than by value: they are already on the payload
        once, carrying a frozen decision each, and a second copy is both
        large and a second version of a record that must have exactly one.
        """
        # The sale that ended it — and only a period that ended has one. An
        # open period may hold trims, and reporting the last trim's price and
        # reason as this holding's exit would put an ending on a position
        # still being held.
        closing = cycle["sells"][-1] if cycle["sells"] and not cycle["open"] \
            else None
        return {
            "seq": cycle["seq"],
            "opened": cycle["opened"],
            "closed": cycle["closed"],
            "open": cycle["open"],
            "shares": cycle["shares"],
            "buys": [l["id"] for l in cycle["buys"]],
            "sells": [l["id"] for l in cycle["sells"]],
            # What the round trip returned: realised once it is closed,
            # marked at the effective price while it is open.
            "return": portfolio.cycle_return(security, cycle, price),
            "reason": (closing or {}).get("reason"),
            "exit_price": (closing or {}).get("price"),
            # What happened after it ended — to the re-purchase where there
            # was one, and only otherwise to today.
            "since_exit": portfolio.since_sale(security, closing, price)
            if closing else None,
        }

    @guarded
    @locked
    def get_state(self):
        strategies, reports = self._strategies()
        offers = [self._strategy_offer(r) for r in strategies.values()]
        refused = [{"bundle": Path(r["dir"]).name, "name": r["name"],
                    "errors": r["errors"]} for r in reports if not r["ok"]]
        listed = journals.list_journals()

        # A journal that cannot be read must not take the whole window down
        # with it: the list still renders, with the problem named, so the
        # user can open a different one rather than face a blank screen.
        problem = None
        try:
            journal, record, chain, _ = self._open()
        except store.StoreError as e:
            journal, record, chain, problem = None, None, None, str(e)
        if journal is None:
            return ok(journal=None, journals=listed, strategies=offers,
                      refused=refused, securities=[], journal_problem=problem,
                      bank_meta=bank.meta(), ev_methods=EV_METHODS,
                      exit_reasons=EXIT_REASONS,
                      data_dir=str(store.data_dir()),
                      data_security=self._data_security())

        if journals.open_id() != journal["id"]:
            journals.set_open(journal["id"])
        bank_meta = bank.meta()
        securities = journal.get("securities", [])
        entry_ids = list(bank_meta)
        priced = []             # effective-price views, for the analytics

        for s in securities:
            computed, price, dstatus, _ = self._computed_layer(s, entry_ids)
            values, sources = dataview.merged_values(s, computed)
            s["_price"] = price
            s["_data"] = dstatus
            s["_fetch"] = fetch.status_of(s["ticker"])
            # Everything about the position is derived from its lots on
            # read, never stored: a stored bucket or running total is a
            # second opinion about a fact the lots already settle.
            s["bucket"] = portfolio.bucket_of(s)
            s["_lots"] = portfolio.open_lots(s)
            s["_sales"] = portfolio.lots(s, "sell")
            s["_shares"] = portfolio.shares_held(s)
            s["_cost_basis"] = portfolio.cost_basis(s)
            s["_opened"] = portfolio.opened_on(s)
            s["_decision"] = self._decide(s, securities, journal, record,
                                          chain)
            # What the strategy read for THIS security, plus anything already
            # recorded — so a value entered before the strategy stopped
            # reading it never becomes invisible.
            cited = self._cited_ids(s["_decision"])
            shown = cited + [m for m in (s.get("metrics") or {})
                             if m not in cited]
            s["_cited"] = cited
            s["_inputs"] = [
                {"id": mid, **{k: bank_meta[mid][k]
                               for k in ("label", "unit", "format", "plain")},
                 "cited": mid in cited}
                for mid in shown if mid in bank_meta
                and bank_meta[mid].get("kind") == "computed"]
            s["_computed"] = {
                eid: {"status": r.get("status"), "value": r.get("value"),
                      "reason": r.get("reason"),
                      "cautions": r.get("cautions") or [],
                      "provenance": r.get("provenance") or []}
                for eid, r in computed.items() if eid in shown}
            s["_value_sources"] = {k: v for k, v in sources.items()
                                   if k in shown}
            # Returns and the scorecards read the EFFECTIVE price —
            # hand-entered over the fetched close. On the raw record a
            # position priced only by a fetch would silently drop out of the
            # analytics that judge the rules, which is the one place a
            # missing number would look like a settled answer.
            priced.append(price["value"])
            # Holding periods, not one running story. A security bought,
            # closed and bought back is two round trips, and the figures
            # that judge a round trip belong to one of them: which shares,
            # what they returned, what happened between selling and buying
            # back. Only the lifetime figure spans them, and it is named as
            # such so it can never sit in a column asking about the position
            # in front of you.
            s["_cycles"] = [self._cycle_view(s, c, price["value"])
                            for c in portfolio.cycles(s)]
            open_cycle = portfolio.open_cycle(s)
            s["_return"] = portfolio.cycle_return(s, open_cycle,
                                                  price["value"]) \
                if open_cycle else None
            s["_lifetime_return"] = portfolio.position_return(
                s, price["value"])
            s["_lot_returns"] = {
                lot["id"]: portfolio.lot_return(s, lot, price["value"])
                for lot in portfolio.lots(s, "buy")}

        by_ticker = dict(zip((s["ticker"] for s in securities), priced))

        return ok(
            journal={k: journal[k] for k in
                     ("id", "name", "created", "strategy", "config",
                      "inputs", "settings")},
            journals=listed,
            strategies=offers,
            refused=refused,
            strategy=self._strategy_view(record, chain, journal)
            if record else None,
            strategy_missing=(journal.get("strategy") or {})
            if record is None else None,
            rule_changes=list(journal.get("rule_changes") or []),
            input_changes=list(journal.get("input_changes") or []),
            pending_changes=journals.pending(journal),
            securities=securities,
            bank_meta=bank_meta,
            # The six render types, so the view sorts and counts a state
            # whose meaning it does not know. It never learns which states
            # exist; it is told, every render.
            render_types={k: dict(v) for k, v in
                          contract.RENDER_TYPES.items()},
            ev_methods=EV_METHODS,
            exit_reasons=EXIT_REASONS,
            override_scorecard=portfolio.override_scorecard(
                securities, lambda s: by_ticker.get(s["ticker"])),
            exit_scorecard=portfolio.exit_scorecard(
                securities, lambda s: by_ticker.get(s["ticker"])),
            data_dir=str(store.data_dir()),
            data_security=self._data_security(),
        )

    @guarded
    def get_bank(self):
        return ok(bank=bank.bank_view())

    # -- journals ---------------------------------------------------------
    @guarded
    @locked
    def create_journal(self, name, strategy_id, inputs=None):
        """Create a journal against one strategy and stamp it.

        The strategy is chosen here and never again. Two strategies means two
        journals, the way it would mean two accounts.
        """
        strategies, _ = self._strategies()
        record = strategies.get(strategy_id)
        if record is None:
            return err("Choose a strategy. A journal is created against one "
                       "and stays there — it is what every decision in it "
                       "will be judged by.")
        typed = {k: v for k, v in
                 self._typed(record.get("inputs"), inputs).items()
                 if v is not None}
        chain = strategy_values.resolve(record, layers=[])
        _, problems = contract.check_inputs(record, typed, chain["values"])
        if problems:
            return err(" ".join(problems))
        journal = journals.create(name, record, inputs=typed)
        journals.set_open(journal["id"])
        return ok(id=journal["id"], name=journal["name"])

    @guarded
    @locked
    def save_journal_settings(self, inputs=None, config=None):
        """The one surface for everything this journal tells its strategy.

        Both halves are set here because they differ only in where the
        default comes from: a value ships one and an input cannot have one.
        Both are editable after creation and not only at it — a strategy
        version that adds a required input would otherwise put every journal
        stamped with it into a blocked state with nothing to click, which is
        a trap with no way out.

        The two are recorded differently, because the host can honestly say
        different things about them. Changing the override changes what the
        strategy demands and goes on the rule-change record, where it is
        owed a written reason. Changing an answer updates a fact about the
        account and goes on its own record, where nothing is owed.
        """
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        if record is None:
            return err("This journal's strategy is not installed on this "
                       "machine, so there is nothing to configure against. "
                       "Put the bundle back and reopen the journal.")

        # Everything is checked against what the journal is *about* to hold
        # before anything is written, so a form that fails halfway leaves
        # the journal exactly as it was rather than half-applied. The
        # override is resolved first because a declared value can be the
        # bound an answer is measured against, and checking an answer
        # against the number it is replacing would refuse one about to be
        # fine.
        def merged(stored, specs, sent):
            """What the journal will hold: what it already had, with what
            this form sent laid over it, and nothing the strategy no longer
            declares.

            The last part is what stops a journal becoming unfixable. A key
            left behind by a strategy that dropped a field refuses to
            resolve, which blocks every verdict — and if saving could not
            clear it, the screen the block sends you to would fail with the
            same message. Saving cleans it up, and the record says it went.
            """
            known = {f["id"] for f in (specs or [])}
            out = dict(stored or {})
            if sent is not None:
                out.update(self._typed(specs, sent))
            return {k: v for k, v in out.items()
                    if v is not None and k in known}

        typed_config = merged(journal.get("config"), record.get("values"),
                              config)
        chain = strategy_values.resolve(
            record, layers=[("this journal's settings", typed_config)])
        if chain["errors"]:
            return err(" ".join(chain["errors"]))

        typed_inputs = merged(journal.get("inputs"), record.get("inputs"),
                              inputs)
        _, problems = contract.check_inputs(record, typed_inputs,
                                            chain["values"])
        if problems:
            return err(" ".join(problems))

        if config is not None:
            journals.set_config(journal, record, typed_config)
        if inputs is not None:
            journals.set_inputs(journal, record, typed_inputs)
        self._write(journal)
        return ok(pending=len(journals.pending(journal)))

    @guarded
    @locked
    def open_journal(self, journal_id):
        listed = {j["id"]: j for j in journals.list_journals()}
        if journal_id not in listed:
            return err("That journal is not on disk any more.")
        if listed[journal_id].get("problem"):
            return err(listed[journal_id]["problem"])
        journals.set_open(journal_id)
        return ok(id=journal_id)

    @guarded
    @locked
    def explain_rule_change(self, seq, reason):
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        change = journals.explain(journal, int(seq), reason)
        journals.save(journal)
        return ok(seq=change["seq"])

    # -- securities ------------------------------------------------------
    def _write(self, journal):
        journals.save(journal)

    @guarded
    @locked
    def add_security(self, ticker, name):
        if not (ticker or "").strip():
            return err("A ticker is required.")
        journal, *_ = self._open()
        if journal is None:
            return err("Create a journal first.")
        securities = journal.setdefault("securities", [])
        if any(s["ticker"] == ticker.upper().strip() for s in securities):
            return err(f"{ticker.upper()} is already in this journal.")
        securities.append(portfolio.new_security(ticker, name or ticker))
        self._write(journal)
        return ok(ticker=ticker.upper().strip())

    @guarded
    @locked
    def remove_security(self, ticker):
        """Remove an idea that was never bought — a mistyped ticker, a
        candidate no longer worth tracking.

        Anything with a lot on it is refused outright: a purchase or a sale
        is recorded history, and this journal never deletes history — that
        is what makes it a journal."""
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        if portfolio.has_history(s):
            return err(f"{s['ticker']} has recorded position history — a "
                       "purchase or a sale — and the journal never deletes "
                       "history. Only candidates that were never bought can "
                       "be removed.")
        journal["securities"].remove(s)
        self._write(journal)
        return ok(removed=s["ticker"])

    @guarded
    @locked
    def save_metrics(self, ticker, metrics, price):
        """Blank fields delete the metric rather than storing a zero.

        A zero would render as a confident failure; absent renders as grey.
        Only fields the dialog offered are touched, so a value the strategy
        has stopped reading is not silently dropped.
        """
        known = set(bank.meta())
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        stored = s.get("metrics") or {}
        for k, v in (metrics or {}).items():
            if k not in known:
                return err(f'"{k}" is not in the metric bank.')
            if v in (None, "", "—"):
                stored.pop(k, None)
                continue
            try:
                stored[k] = float(v)
            except (TypeError, ValueError):
                return err(f"{k} must be a number or left blank.")
        s["metrics"] = stored
        s["price"] = float(price) if price not in (None, "") else None
        self._write(journal)
        return ok()

    @guarded
    @locked
    def save_falsifier(self, ticker, text):
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        self._find(journal, ticker)["falsifier"] = (text or "").strip()
        self._write(journal)
        return ok()

    @guarded
    @locked
    def add_note(self, ticker, text):
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        portfolio.add_note(self._find(journal, ticker), text)
        self._write(journal)
        return ok()

    # -- purchases and exits ----------------------------------------------
    def _purchase_date(self, opened):
        """(iso date or None, is_past). The future is refused outright: the
        data that belongs to a day that hasn't happened does not exist, so
        no honest evaluation of it can be recorded."""
        if not opened:
            return None, False
        try:
            d = date.fromisoformat(str(opened)[:10])
        except ValueError:
            raise ValueError("The purchase date must be a real date "
                             "(YYYY-MM-DD).")
        if d > date.today():
            raise ValueError("A purchase cannot be dated in the future — "
                             "the data belonging to that day does not "
                             "exist yet.")
        return d.isoformat(), d < date.today()

    def _values_live(self, s):
        """(values, sources, price) — merged values, hand-entered on top."""
        entry_ids = list(bank.meta())
        computed, price, _, _ = self._computed_layer(s, entry_ids)
        values, sources = dataview.merged_values(s, computed)
        return values, sources, price

    def _values_asof(self, s, as_of):
        """(values, sources, price, evaluation record) rebuilt from what was
        observable on `as_of`: filings filed by then, the close on or shortly
        before it — the same as-of rule the strategy's own context obeys.

        Hand-entered values still sit on top, exactly as in the live merge:
        they are the user's standing assertions and carry no date, so the
        record names them as undated rather than either trusting them into
        the past silently or fabricating a verdict on securities the user
        maintains by hand. The evaluation record says all of this in plain
        language, and it is frozen with the snapshot.
        """
        entry_ids = list(bank.meta())
        cik = s.get("cik")
        parts = []
        if cik:
            tickers = self._tickers_of(s)
            # Same contract as the live path: a broken data layer must not
            # block recording the decision. The purchase still records; the
            # reconstruction honestly reports that nothing computed could
            # enter it.
            try:
                computed = dataview.asof_results(cik, tickers, entry_ids,
                                                 as_of)
                avail = dataview.asof_availability(cik, tickers, as_of)
                price = avail["price"]
                if avail["filings_by_then"]:
                    parts.append(f'{avail["filings_by_then"]} of the '
                                 f'{avail["filings_held"]} stored filings had '
                                 f'been filed by {as_of} (newest '
                                 f'{avail["newest_filed"]})')
                else:
                    parts.append(f"none of the {avail['filings_held']} stored "
                                 f"filings had been filed by {as_of}")
                if price.get("value") is not None:
                    parts.append(f'priced at the {price["date"]} close')
                else:
                    parts.append(price.get("reason")
                                 or f"no close is stored for {as_of}")
            except Exception as e:                      # noqa: BLE001
                traceback.print_exc()
                computed, avail = {}, None
                price = {"value": None, "source": None, "date": None,
                         "reason": f"the data layer failed: "
                                   f"{type(e).__name__}: {e}"}
                parts.append("the stored filing and price data could not be "
                             f"read ({type(e).__name__}: {e}) — nothing "
                             "computed enters this reconstruction")
        else:
            computed, avail = {}, None
            price = {"value": None, "source": None, "date": None,
                     "reason": "no company is linked to this ticker, so no "
                               "filings or prices are stored for it"}
            parts.append("no company is linked to this ticker, so no stored "
                         f"filing or price from {as_of} could be consulted")

        values, sources = dataview.merged_values(s, computed)
        manual = sorted(mid for mid, side in sources.items()
                        if side == "manual")
        if manual:
            parts.append(f"{len(manual)} hand-entered value"
                         f"{'s' if len(manual) != 1 else ''} entered as "
                         "recorded — hand-entered values carry no date")
        evaluation = {
            "basis": "reconstructed",
            "as_of": as_of,
            "filings_by_then": (avail or {}).get("filings_by_then", 0),
            "newest_filed": (avail or {}).get("newest_filed"),
            "priced": price.get("date"),
            "manual_undated": manual,
            "note": "; ".join(parts),
        }
        return values, sources, price, evaluation

    def _at_purchase(self, journal, record, chain, s, opened_iso, is_past):
        """(decision, values, sources, price, evaluation) for the day being
        recorded. Today evaluates live; a past date is reconstructed from the
        data available by then, and says so everywhere."""
        securities = journal.get("securities", [])
        if is_past:
            values, sources, price, evaluation = self._values_asof(
                s, opened_iso)
            decision = self._decide(s, securities, journal, record, chain,
                                    as_of=opened_iso)
        else:
            values, sources, price = self._values_live(s)
            evaluation = {"basis": "live", "as_of": date.today().isoformat()}
            decision = self._decide(s, securities, journal, record, chain)
        return decision, values, sources, price, evaluation

    @guarded
    @locked
    def preview_purchase(self, ticker, opened=None):
        """What the journal's strategy says for the chosen date, before
        anything is committed."""
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        opened_iso, is_past = self._purchase_date(opened)
        decision, *_, evaluation = self._at_purchase(
            journal, record, chain, s, opened_iso, is_past)
        return ok(decision=decision, basis=evaluation["basis"],
                  as_of=evaluation["as_of"], note=evaluation.get("note"))

    @guarded
    @locked
    def open_position(self, ticker, shares, cost, opened,
                      override_reason="", previewed_state=None):
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        opened_iso, is_past = self._purchase_date(opened)
        decision, values, sources, price, evaluation = self._at_purchase(
            journal, record, chain, s, opened_iso, is_past)
        lot = portfolio.add_lot(s, decision, float(shares), float(cost),
                                opened_iso, override_reason, values=values,
                                value_sources=sources, price_seen=price,
                                evaluation=evaluation)
        self._write(journal)
        state = (decision.get("state") or {}).get("id")
        return ok(override=bool(lot.get("override")),
                  state=(decision.get("state") or {}).get("name"),
                  commit=portfolio.is_commit(decision),
                  state_changed=bool(previewed_state and state
                                     and previewed_state != state))

    @guarded
    @locked
    def sell_shares(self, ticker, reason, price, exited, shares=None):
        """Record a sale, whole or partial.

        `shares` left out sells everything still open, which is what closing
        a position means. A partial sale leaves the remaining lots exactly
        as they are — nothing is rewritten, a sale is one more appended
        entry naming what it drew on.
        """
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        held = portfolio.shares_held(s)
        try:
            n = float(shares) if shares not in (None, "") else held
        except (TypeError, ValueError):
            return err("The number of shares sold must be a number.")
        # A strategy that is not installed is not a signal that read clear:
        # the sale records that it could not be asked at all.
        decision, values, seen = None, None, None
        if record is not None:
            decision = self._decide(s, journal.get("securities", []), journal,
                                    record, chain)
            values, _, seen = self._values_live(s)
        lot = portfolio.sell_lots(s, decision, reason, n, float(price),
                                  exited or None, values=values,
                                  price_seen=seen)
        self._write(journal)
        return ok(rule_triggered=lot["rule_triggered"],
                  signal=lot["signal_at_exit"],
                  remaining=portfolio.shares_held(s),
                  strategy_name=(lot["strategy"] or {}).get("name"))

    # -- data acquisition ------------------------------------------------
    def _tie_cik(self, journal_id, ticker, cik):
        """Record the resolved company on the security, from the fetch thread
        itself, under the journal lock. A recorded CIK is what makes the
        reused-symbol protection work on the NEXT fetch, so it must not
        depend on a UI poll surviving to completion.

        Bound to the journal the fetch was started from, not to whichever is
        open when it lands: switching journals mid-fetch would otherwise
        write the result into the wrong one and leave the journal that asked
        for it without the company it just resolved.
        """
        with self._doc_lock:
            try:
                journal, *_ = self._open(journal_id)
                if journal is None:
                    return
                s = self._find(journal, ticker)
            except (ValueError, store.StoreError):
                return
            if s.get("cik") != int(cik):
                s["cik"] = int(cik)
                self._write(journal)
        dataview.invalidate(int(cik))

    @guarded
    @locked
    def fetch_security(self, ticker):
        """Start a background fetch of filings and prices for one security.
        Explicit user action only — nothing here runs on a schedule."""
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        jid = journal["id"]
        r = fetch.start_fetch(
            s["ticker"], known_cik=s.get("cik"),
            on_resolved=lambda t, c: self._tie_cik(jid, t, c))
        if r.get("error"):
            return err(r["error"])
        return ok(started=True)

    @guarded
    def get_fetch_status(self, ticker):
        """Progress of a running fetch.

        Nothing is recorded here. The resolved company was already tied to
        the security that asked for it, from the fetch thread itself and
        bound to the journal that started it — a poll has no way to know
        which journal that was, and fetch status is keyed by ticker alone.
        Only the derived-value cache is dropped, which is per company and
        belongs to no journal.
        """
        st = fetch.status_of(ticker)
        if st and not st.get("running") and st.get("report"):
            report = st["report"]
            cik = report.get("cik")
            if cik and not report.get("conflict"):
                dataview.invalidate(int(cik))
        return ok(status=st)

    @guarded
    @locked
    def get_coverage(self, ticker):
        """Per bank entry: computed or absent-with-reason, plus the
        public-float cross-check — the data page for one security.

        This page's subject is the data, not the strategy, so it lists
        everything the host can compute rather than only what was read."""
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        cik = s.get("cik")
        if not cik:
            return ok(coverage=None,
                      note="Nothing fetched yet for this security. Fetch "
                           "filings & prices first.")
        meta = bank.meta()
        cov = dataview.coverage(cik, self._tickers_of(s), list(meta), meta)
        return ok(coverage=cov)

    @guarded
    def save_sec_identity(self, sec_identity):
        """The SEC contact — personal information, kept machine-local so no
        export bundle ever carries an email address."""
        ident = (sec_identity or "").strip()
        if ident and "@" not in ident:
            return err("The SEC identity must include a real email address "
                       "— it is how the SEC reaches you before blocking a "
                       "misbehaving tool.")
        secrets.local_set("sec_identity", ident or None)
        return ok()

    @guarded
    def save_api_key(self, key):
        """Store a new price-source key in the OS credential store. The key
        goes in and never comes back out to the UI."""
        key = (key or "").strip()
        if not key:
            return err("Paste the key first. To remove the stored key, use "
                       "Remove key.")
        try:
            secrets.set_secret("tiingo_api_token", key)
        except secrets.SecretsError as e:
            return err(str(e))
        return ok(storage=secrets.storage())

    @guarded
    def remove_api_key(self):
        try:
            had = secrets.delete_secret("tiingo_api_token")
        except secrets.SecretsError as e:
            return err(str(e))
        return ok(removed=had)

    @guarded
    def test_api_key(self):
        """One cheap request against the price source's test endpoint — a
        bad key should be obvious now, not as mysteriously absent prices
        after a full fetch."""
        try:
            token = secrets.get_secret("tiingo_api_token")
        except secrets.SecretsError as e:
            return err(str(e))
        if not token:
            return err("No key is stored. Paste one and save it first.")
        v = tiingo.verify_key(token)
        return ok(valid=bool(v.get("ok")),
                  message=str(v.get("message") or ""))

    # -- expected value --------------------------------------------------
    def _ev_item(self, r, scale=1.0, digits=3):
        """One computed reference for the EV dialog: scaled to the unit the
        dialog speaks (millions), with provenance and as-of carried, or
        absent with its reason. Three decimals of a million keep a small
        filer's real figure from rounding to a confident zero."""
        if not isinstance(r, dict) or r.get("status") != "computed":
            return {"status": "absent",
                    "reason": (r or {}).get("reason")
                    or "this could not be computed from the stored filings"}
        return {"status": "computed", "source": "computed",
                "value": round(float(r["value"]) / scale, digits),
                "provenance": list(r.get("provenance") or []),
                "cautions": list(r.get("cautions") or []),
                "asof": r.get("asof")}

    @guarded
    @locked
    def ev_prefill(self, ticker):
        """What the expected-value dialog may prefill or cite, per input key:
        computed figures with provenance and as-of dates, or absence with the
        reason. Hand-entered values win where both exist, as everywhere."""
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        cik = s.get("cik")
        tickers = self._tickers_of(s)

        price = dataview.price_view(s, cik, tickers)
        if price["value"] is None:
            price_item = {"status": "absent",
                          "reason": "no price is stored — fetch prices, or "
                                    "enter one in Edit metrics"}
        elif price["source"] == "manual":
            price_item = {"status": "computed", "source": "manual",
                          "value": float(price["value"]), "asof": None,
                          "provenance": ["hand-entered price from Edit "
                                         "metrics (undated)"],
                          "cautions": []}
        else:
            price_item = {"status": "computed", "source": "fetched",
                          "value": float(price["value"]),
                          "asof": price["date"],
                          "provenance": [f'{price.get("ticker") or s["ticker"]}'
                                         f' close on {price["date"]}'],
                          "cautions": []}

        never = ("nothing has been fetched for this security yet — Fetch "
                 "data stores its filings and prices")
        ref = {}
        if cik:
            ref = dataview.ev_reference(cik, tickers)
        fcf = self._ev_item(ref.get("fcf_ttm")
                            or {"status": "absent", "reason": never}, 1e6)
        manual_fcf = (s.get("metrics") or {}).get("fcf_ttm")
        if manual_fcf is not None:
            prov = ["hand-entered in Edit metrics (undated)"]
            if fcf["status"] == "computed":
                prov.append(f"overrides the computed ${fcf['value']:,.1f}M "
                            "from filings — clear the hand-entered value in "
                            "Edit metrics to use it")
            fcf = {"status": "computed", "source": "manual",
                   "value": round(float(manual_fcf) / 1e6, 3),
                   "asof": None, "provenance": prov, "cautions": []}
        shares = self._ev_item(ref.get("shares")
                               or {"status": "absent", "reason": never}, 1e6)
        references = {}
        for rid in ("net_income_ttm", "dda_ttm", "capex_ttm"):
            references[rid] = self._ev_item(
                ref.get(rid) or {"status": "absent", "reason": never}, 1e6)
        return ok(prefill={"price": price_item, "fcf_ttm": fcf,
                           "shares": shares},
                  references=references)

    @guarded
    @locked
    def save_valuation_defaults(self, discount_rate, terminal_growth,
                                margin_of_safety):
        """The journal's set-once valuation assumptions. One place, on
        purpose: moving a discount rate per stock is how a DCF becomes a
        rationalisation, so the default moves every valuation at once."""
        try:
            dr = float(discount_rate)
            tg = float(terminal_growth)
            mos = float(margin_of_safety)
        except (TypeError, ValueError):
            return err("Each default must be a number, as a percentage.")
        if dr <= tg:
            return err("The discount rate must exceed terminal growth, or "
                       "every DCF value becomes infinite.")
        if not (0 <= mos < 100):
            return err("The margin of safety must be between 0 and 100 "
                       "percent.")
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        journal["settings"].update({"discount_rate": dr,
                                    "terminal_growth": tg,
                                    "margin_of_safety": mos})
        self._write(journal)
        return ok()

    @guarded
    @locked
    def compute_ev(self, ticker, method, inputs, sources=None):
        result = compute_ev(method, inputs or {})
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        record = {"method": method, "inputs": inputs,
                  "computed": date.today().isoformat()}
        # Where each prefillable input came from — fetched, overridden, or
        # typed against absence — so the stored assumptions stay traceable.
        if isinstance(sources, dict):
            keys = {k for k, _l, _h in EV_METHODS.get(method, {})
                    .get("inputs", [])}
            record["sources"] = {k: v for k, v in sources.items()
                                 if k in keys and isinstance(v, dict)}
        s["ev"] = record
        self._write(journal)
        return ok(result=result)

    @guarded
    @locked
    def recompute_ev(self, ticker):
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        ev = self._find(journal, ticker).get("ev")
        if not ev:
            return ok(result=None)
        return ok(result=compute_ev(ev["method"], ev["inputs"]))

    # -- backup ----------------------------------------------------------
    @guarded
    def export_data(self):
        paths = self.window.create_file_dialog(
            webview.FOLDER_DIALOG) if self.window else None
        if not paths:
            return ok(cancelled=True)
        written = backup.export_bundle(paths[0])
        return ok(path=str(written))

    @guarded
    @locked
    def import_data(self):
        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Ledger backup (*.json)",)) if self.window else None
        if not paths:
            return ok(cancelled=True)
        summary = backup.import_bundle(paths[0])
        journals.set_open(journals.resolve_open())
        return ok(summary=summary)

    @guarded
    @locked
    def clear_all(self):
        """Empty the open journal of securities. Its strategy stamp, settings
        and rule-change record stay — they are what the journal *is*."""
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        journal["securities"] = []
        self._write(journal)
        return ok()

    @guarded
    def open_data_dir(self):
        return ok(path=str(store.data_dir()))


def main():
    parser = argparse.ArgumentParser(description="Ledger, a portfolio journal")
    parser.add_argument("--reset", action="store_true",
                        help="delete every journal and start empty")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.reset:
        d = store.ensure_data()
        shutil.rmtree(journals.journals_dir(), ignore_errors=True)
        journals.set_open(None)
        print(f"Cleared every journal in {d}. Fetched filings and prices "
              "were kept — they are a cache of public data, not a record.")

    store.ensure_data()
    api = Api()
    window = webview.create_window(
        "Ledger", str(UI_DIR / "index.html"),
        js_api=api, width=1320, height=900, min_size=(900, 620),
    )
    api.window = window
    webview.start(debug=args.debug)


if __name__ == "__main__":
    sys.exit(main())
