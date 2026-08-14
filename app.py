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
import copy
import json
import shutil
import sys
import threading
import traceback
from datetime import date
from pathlib import Path

import webview

from engine import (allocation, backup, bank, cash, contract, context,
                    dataview, fetch, hand_entered, journals, judgements, lists,
                    portfolio, secrets, store, strategy_loader,
                    strategy_values, thesis as thesis_mod, tickermap, tiingo,
                    valuation)
from engine.expected_value import EV_METHODS, EVError
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

        The measure definitions are compared first, and whether or not the
        strategy is installed. A strategy missing from this machine is a
        reason no verdict can be produced; it is not a reason for the file
        that says what every figure means to move unobserved.
        """
        strategies, reports = self._strategies()
        jid = jid or journals.resolve_open()
        if jid is None:
            return None, None, None, reports
        journal = journals.load(jid)
        if self._observe_measures(journal):
            journals.save(journal)
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

    def _observe_measures(self, journal):
        """Put any move in what the measures mean onto this journal's record.
        Returns the appended entry, or None where nothing moved.

        Contained, because a bank that will not load is already reported
        everywhere a figure would have been and must not additionally stop a
        journal opening. What it costs is that the move is recorded the next
        time the file parses — which is the same as any other unreadable
        file here, and better than a window in which nothing opens at all.
        """
        try:
            return journals.observe_measure_change(
                journal, bank.definitions(), bank.changelog())
        except Exception:                               # noqa: BLE001
            traceback.print_exc()
            return None

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

    def _snapshot_for(self, s):
        """One reading of one company's stores, to be shared by everything
        assembled from it — or None where there is nothing to read.

        Never raises. A snapshot is an optimisation for consistency, not a
        precondition for recording: every caller still works without one, and
        a data layer that cannot be read must not stop a decision being
        written down.
        """
        cik = s.get("cik")
        if not cik:
            return None
        try:
            return dataview.snapshot(cik, self._tickers_of(s))
        except Exception:                               # noqa: BLE001
            return None

    def _computed_layer(self, s, entry_ids, snap=None, with_status=True):
        """The security's computed values and status, or empty layers when
        nothing has been fetched. Never raises — a broken data layer must not
        take the journal down with it, and must never block recording."""
        cik = s.get("cik")
        if not cik:
            return {}, dataview.price_view(s, None, s["ticker"]), None, \
                [s["ticker"]]
        # Company scope for the measures, security scope for the price. A
        # measure is about the enterprise and reads every class; a holding is
        # one instrument and is priced from its own symbol alone.
        tickers = self._tickers_of(s)
        try:
            computed = dataview.computed_results(cik, tickers, entry_ids,
                                                 snap)
            price = dataview.price_view(s, cik, s["ticker"])
            # Only where a screen is going to show it. It is a second reading
            # of the same stores — the company record, the filings, the price
            # document and the identity history again — and the callers that
            # freeze an entry discard it, so computing it there both cost a
            # read and put the entry's two halves an instant apart.
            status = dataview.data_status(cik) if with_status else None
        except Exception as e:                          # noqa: BLE001
            traceback.print_exc()
            return {}, dataview.price_view(s, None, s["ticker"]), \
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
    @staticmethod
    def _declared_input(f):
        """One declared question, saying who answers it.

        A field the host works out for itself is not a question for the user,
        and a form has to be able to tell the two apart without knowing which
        role it is looking at — free cash is the opening balance of a record,
        not an answer, and a form that rendered it as a plain number field
        would collect a figure the save then refuses. One reading of that, so
        the setup screen and the settings screen cannot disagree about which
        of their fields are questions.
        """
        spec = contract.INPUT_ROLES.get(f.get("role")) or {}
        return {**f, "answered_by": contract.answered_by(f.get("role")),
                "answered_how": spec.get("answered_how")}

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
            "inputs": [self._declared_input(f)
                       for f in (record.get("inputs") or [])],
            "roles": {k: dict(v) for k, v in contract.INPUT_ROLES.items()},
            # What it will not evaluate, and why, resolved into the host's
            # own words for each kind. This is on the OFFER and not only on
            # the stamped strategy on purpose: what a rule set covers is
            # knowable without running it, so somebody choosing one can be
            # told before the journal exists rather than finding out at the
            # first verdict.
            "declines": [
                {"class": cid, "because": because,
                 **{k: contract.INDUSTRY_CLASSES[cid][k]
                    for k in ("label", "noun", "means", "explain")}}
                for cid, because in
                contract.declined_classes(record).items()],
            # On the offer as well as the stamped strategy, for the same
            # reason: what a method does not promise is knowable before a
            # journal exists, and finding out afterwards is finding out too
            # late to choose differently.
            "limits": [dict(l) for l in (record.get("limits") or [])],
            # Whether this strategy works from a list somebody else chose,
            # and what it calls it. On the offer because it is the largest
            # single thing about how a journal will be used — one strategy
            # asks you to assess a business, another asks you to paste in
            # thirty names every year — and choosing between them without
            # being told that is choosing blind.
            "list": dict(record["list"]) if contract.declares_list(record)
                    else None,
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
        # `set_by` is which layer of the chain the value in force came from.
        # It is deliberately not called `source`: a declared value already
        # carries one of those, saying where its NUMBER came from, and the
        # two answer different questions — "the expert report" and "this
        # journal's override" would otherwise be one field.
        values = []
        for v in (record.get("values") or []):
            values.append({
                **v,
                "value": chain["values"].get(v["id"]),
                "set_by": chain["sources"].get(v["id"]),
                "shipped": (record.get("defaults") or {}).get(v["id"]),
            })
        # Only what the strategy still declares, exactly as the decision
        # path reads it. A journal can outlive an input the strategy has
        # dropped, and reporting that leftover as something the user owes an
        # answer for would name a problem they cannot act on.
        declared = {f["id"] for f in (record.get("inputs") or [])}
        supplied = {k: v for k, v in
                    contract.user_answers(record,
                                          journal.get("inputs")).items()
                    if k in declared}
        activity = contract.input_activity(record, supplied)
        _, problems = contract.check_inputs(record, supplied, chain["values"])
        # What the host answers for itself, on today's clock. Read here rather
        # than left as the stored figure: a journal written before free cash
        # was derived still holds the number somebody typed, and showing it on
        # the screen that explains where figures come from is the one place it
        # would be believed.
        roles = context.host_role_answers(journal)
        by_host = contract.host_answered(record)
        offered = contract.input_roles(record, supplied, roles)
        inputs = []
        for f in (record.get("inputs") or []):
            role = by_host.get(f["id"])
            answer = offered.get(role) if role else None
            inputs.append({
                **self._declared_input(f),
                "value": (answer or {}).get("value") if role
                         else supplied.get(f["id"]),
                # Why the host could not work it out, where it could not. An
                # empty field with nothing beside it reads as a question
                # nobody has answered, which is exactly what this is not.
                "unavailable": (answer or {}).get("reason") if role else None,
                "provenance": list((answer or {}).get("provenance") or [])
                              if role else [],
                "inactive": activity.get(f["id"]),
            })
        return {
            **self._strategy_offer(record),
            "changelog": {str(k): v
                          for k, v in (record.get("changelog") or {}).items()},
            "values": values,
            "inputs": inputs,
            "input_problems": problems,
            "value_errors": list(chain["errors"]),
            "bundle": Path(record["dir"]).name,
            "reference": sorted(record.get("reference") or {}),
        }

    def _list_view(self, journal, record, securities):
        """The list this journal works from, as the screen needs it.

        None where the strategy screens for itself — which is what keeps the
        tab off a Graham journal without the view ever asking which strategy
        is running. It reads one thing: whether this journal's strategy said
        it works from a list.

        Every row carries what the journal already knows about that name and
        nothing it has had to go and find out: whether a security record
        exists, whether it is held, the verdict already computed for this
        render, and whether the user has recorded a decision not to buy it.
        A name on the list with no security record is the ordinary case —
        importing fifty names does not create fifty securities, because
        forty-three of them will never be bought and each would carry its own
        fetch.
        """
        if record is None or not contract.declares_list(record):
            return None
        known = {s["ticker"]: s for s in securities}
        entries = lists.changes(journal)
        now = entries[0] if entries else None
        rows = []
        for ticker in (now or {}).get("tickers") or []:
            s = known.get(ticker)
            skip = (lists.passed_over(s, now["pulled_on"])
                    if s is not None else None)
            rows.append({
                "ticker": ticker,
                "name": (s or {}).get("name"),
                "tracked": s is not None,
                "held": bool(s is not None and portfolio.shares_held(s) > 0),
                "new": ticker in ((now or {}).get("added") or []),
                "decision": (s or {}).get("_decision"),
                "passed_over": skip,
            })
        return {
            "declared": dict(record["list"]),
            "current": now,
            "rows": rows,
            "history": entries[1:],
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
                as_of=None, snap=None):
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
        # The answers that were on record on the day being evaluated, not the
        # ones on record now. They are dated — every change to one is on the
        # journal's own append-only record — and a reconstruction that served
        # today's would size a purchase made two years ago against today's
        # account. A day before this journal existed has no answers at all,
        # and that absence is served as itself: see journals.answers_on.
        answered = journals.answers_on(journal, as_of)
        supplied = {k: v for k, v in (answered or {}).items()
                    if k in declared}
        try:
            ctx = context.build_context(security, securities,
                                        chain["values"], supplied,
                                        as_of=as_of, record=record,
                                        snap=snap, journal=journal)
        except Exception as e:                          # noqa: BLE001
            traceback.print_exc()
            return contract.host_result(
                "host:data-unreadable",
                f"The stored data for {security.get('ticker')} could not be "
                f"read ({type(e).__name__}: {e}), so {record['name']} was "
                "not asked. Fetching again replaces anything transient.",
                record)
        return contract.evaluate(record, ctx)

    @staticmethod
    def _cited_ids(decision, kind="computed") -> list:
        """What this decision actually looked at, of one kind of bank entry.
        It is what the Edit-values dialog offers, and what the Judgements
        section asks: the figures this strategy reads for THIS security,
        never the whole bank.

        Citation is the whole discovery mechanism for anything per security,
        because a question about one cannot be asked before there is one to
        ask it about — which is exactly why judgement inputs are not declared
        on a setup screen the way journal-level answers are. It has a
        consequence worth stating: a strategy that reaches its moat rule only
        after the numbers pass will not ask about a moat until they do. That
        is the right way round. Nobody should be assessing the durability of
        a business their own rules have already rejected.

        The host answers which entries were read; this only says which kind
        it wants. It used to match the subject kind itself, which meant this
        screen held a copy of the host's list of them and silently dropped
        every kind added after it was written — a measure cited only as a
        change since a purchase never reached the dialog that supplies it.
        See contract._subject.
        """
        return contract.cited_bank_ids(
            ((decision or {}).get("reason") or {}).get("evidence") or [],
            kind)

    @staticmethod
    def _judgement_view(security, asked) -> list:
        """The questions this security owes an answer to, and the answers on
        record. Built from the bank's own qualitative entries, so a question
        added there arrives here with no code changed.

        Every prior assessment travels with it. The record is append-only and
        the point of that is to be read: an opinion that flipped a fortnight
        before a purchase is the thing worth seeing, and it is invisible if
        only the newest one renders.

        The cautions come from the same call that qualifies the figure a
        strategy is handed, rather than being worked out again for the
        screen. One sentence, one home — two copies of a caution drift until
        they disagree about what they are warning of.
        """
        answered = [a["id"] for a in (security.get("judgements") or [])
                    if isinstance(a, dict) and a.get("id")]
        live = judgements.questions()
        seen = judgements.observations(security)
        # Driven by the bank AND by the record, not by the bank alone. The
        # `answered` set used to sit inside this loop as a gate, where it could
        # only keep an id the bank still offered and never add one the bank had
        # dropped — so deleting an entry, or flipping its `kind` to `computed`,
        # took the mark, the reasoning and the whole history off the screen
        # with nothing said. The words for such a row come off the answer
        # itself; see judgements.as_asked.
        ids = list(live) + [e for e in answered if e not in live]
        out = []
        for eid in ids:
            q = live.get(eid)
            if eid not in asked and eid not in answered:
                continue
            standing = judgements.in_force(security, eid) or {}
            asked_as = judgements.as_asked(standing, q, eid)
            # Where the host cannot serve the question at all, it reports no
            # answer — even if one is on record. The strategy was told the
            # measure is absent, and a screen showing "Passed" beside a
            # verdict that says "can't say" is the two halves of the program
            # disagreeing about the same fact in front of the reader. The
            # record itself is untouched and still travels in `history`.
            #
            # A question the bank no longer asks is the same case: the answer
            # is shown as what it was and not as what is standing, because
            # nothing is standing.
            if (q or {}).get("unsupported") or asked_as["withdrawn"]:
                standing = {}
            out.append({
                **asked_as,
                "cited": eid in asked,
                "mark": standing.get("mark"),
                "reasoning": standing.get("reasoning"),
                "recorded": standing.get("recorded"),
                "cautions": list((seen.get(eid) or {}).get("cautions") or []),
                "history": judgements.history(security, eid),
            })
        return out

    # -- read ------------------------------------------------------------
    @staticmethod
    def _cycle_view(security, cycle, price) -> dict:
        """One holding period, as the screens read it.

        Lots go by id rather than by value: they are already on the payload
        once, carrying a frozen decision each, and a second copy is both
        large and a second version of a record that must have exactly one.
        """
        # How it ended, across every sale that closed it — not the last one
        # standing for all of them. A period closed in stages had several
        # sales at several prices for several stated reasons, and reporting
        # the final sliver as "the exit" describes the smallest part of it:
        # sell ninety at $150 and the last ten at $55 and the record called
        # $55 the exit price, beside a return computed from both.
        #
        # Only a period that ended has one. An open period may hold trims,
        # and a trim is not an ending.
        exit_ = portfolio.cycle_exit(security, cycle)
        # "Since exit" still runs from the LAST sale, because that is the day
        # nothing was held — the one thing the final sale does settle. It is
        # measured from that sale's own price, which is what the shares
        # actually left at; the weighted figure above is what the holding
        # got out at across all of them, and the two answer different
        # questions. Both are labelled so neither can be read as the other.
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
            "exit": exit_,
            # What happened after it ended — to the re-purchase where there
            # was one, and only otherwise to today.
            "since_exit": portfolio.since_sale(security, closing, price)
            if closing else None,
        }

    @staticmethod
    def _price_known(view) -> dict:
        """A price view as the rest of the host states a figure: known with a
        value, or absent with the host's own reason. Never a bare number and
        never a None that a caller has to invent a sentence for."""
        if (view or {}).get("value") is None:
            return {"status": "absent",
                    "reason": (view or {}).get("reason")
                    or "no price is on record for this security"}
        return {"status": "known", "value": float(view["value"])}

    def _allocation(self, securities, journal, record, chain, priced):
        """Where capital goes, across the whole journal.

        Built from the verdicts already computed above rather than from a
        second pass. Two evaluations of the same security on one payload can
        disagree — a fetch landing between them is enough — and this screen's
        only job is to summarise the ones the security pages show.

        Built even when the strategy cannot be asked at all — a missing
        bundle, settings that will not resolve. The decisions are then the
        host's own "we could not ask", nothing is eligible, and every
        security lands in the list with that said against it. That is not a
        nicety: this screen is the only place a purchase into a name you
        already hold can be started, so a version of it that renders nothing
        when the strategy is missing would make recording an add impossible
        for exactly as long as the bundle is off the machine. The tool
        records decisions and never blocks them, and a screen that vanishes
        is a block however it is described.

        Never raises. An allocation view is a convenience over facts that are
        all visible elsewhere, and taking the window down for it would be the
        tail wagging the dog.
        """
        try:
            roles = {}
            if record is not None and not chain["errors"]:
                declared = {f["id"] for f in (record.get("inputs") or [])}
                supplied = {k: v for k, v in
                            contract.user_answers(
                                record, journal.get("inputs")).items()
                            if k in declared}
                effective, _ = contract.check_inputs(record, supplied,
                                                     chain["values"])
                # The same record on the same clock the security pages read.
                # Two screens reaching their own cash figure is how an account
                # total here comes to differ from the one a weight there was
                # measured against, with neither visibly the wrong one.
                roles = contract.input_roles(
                    record, effective, context.host_role_answers(journal))
            folio = context.portfolio_view(securities, roles)
            return allocation.view(
                securities,
                {s["ticker"]: s.get("_decision") for s in securities},
                {t: self._price_known(v) for t, v in priced.items()},
                folio)
        except Exception:                               # noqa: BLE001
            traceback.print_exc()
            return None

    @guarded
    @locked
    def get_state(self):
        strategies, reports = self._strategies()
        offers = [self._strategy_offer(r) for r in strategies.values()]
        refused = [{"bundle": Path(r["dir"]).name, "name": r["name"],
                    "errors": r["errors"]} for r in reports if not r["ok"]]
        listed = journals.list_journals()

        # The bank is a file the user edits, so a bad edit is an ordinary
        # event and must not be a dead window. `bank.refusal` reports what is
        # wrong with the version on disk and whether an earlier one is still
        # being served; where one is, everything below runs on it exactly as
        # before and the screen carries the problem. Where there is none —
        # a broken file at a cold start — the state still renders, with no
        # measures and the reason in place of them, because the way out of
        # this is to go and fix a file and that needs a window that opens.
        bank_problem = bank.refusal()
        try:
            bank_meta = bank.meta()
        except Exception as e:                      # noqa: BLE001
            bank_meta = {}
            if bank_problem is None:                # not a refusal: say what
                bank_problem = {"problems": [f"{type(e).__name__}: {e}"],
                                "holding": False,
                                "path": str(bank.bank_path("metric-bank"))}

        # A journal that cannot be read must not take the whole window down
        # with it: the list still renders, with the problem named, so the
        # user can open a different one rather than face a blank screen.
        problem = None
        try:
            journal, record, chain, _ = self._open()
        except store.StoreError as e:
            journal, record, chain, problem = None, None, None, str(e)
        # Nothing about a security survives a bank that will not load at all —
        # every measure, every verdict and every question you answer is
        # defined there — so the securities are not walked rather than walked
        # with each of a dozen bank reads contained separately. The list of
        # journals and the reason render, which is what the way out needs.
        if not bank_meta:
            journal = None
        if journal is None:
            return ok(journal=None, journals=listed, strategies=offers,
                      refused=refused, securities=[], journal_problem=problem,
                      bank_problem=bank_problem,
                      bank_meta=bank_meta, ev_methods=EV_METHODS,
                      exit_reasons=EXIT_REASONS,
                      data_dir=str(store.data_dir()),
                      data_security=self._data_security())

        if journals.open_id() != journal["id"]:
            journals.set_open(journal["id"])
        securities = journal.get("securities", [])
        entry_ids = list(bank_meta)
        priced = []             # effective-price views, for the analytics
        today = date.today().isoformat()

        for s in securities:
            computed, price, dstatus, _ = self._computed_layer(s, entry_ids)
            values = dataview.merged_values(s, computed, today=today)
            s["_price"] = price
            s["_data"] = dstatus
            s["_fetch"] = fetch.status_of(s["ticker"])
            # Everything about the position is derived from its lots on
            # read, never stored: a stored bucket or running total is a
            # second opinion about a fact the lots already settle.
            s["bucket"] = portfolio.bucket_of(s)
            # Whether any entry in this name was reconstructed rather than
            # captured at the time. Derived from the lots, like the bucket,
            # and stated here so the list and the detail page read one
            # answer — a screen working it out for itself is a second copy
            # of the rule, and the two disagree the first time an entry is
            # added without one.
            s["_backfilled"] = portfolio.backfilled(s)
            s["_lots"] = portfolio.open_lots(s)
            s["_sales"] = portfolio.lots(s, "sell")
            s["_shares"] = portfolio.shares_held(s)
            s["_cost_basis"] = portfolio.cost_basis(s)
            # No separate "opened" here. The screens read it off the holding
            # period below, which is the same value `opened_on` gives a
            # strategy — one figure with one derivation, rather than two that
            # have to be kept agreeing. Two panels disagreeing about when a
            # holding began is what put this on the board.
            s["_decision"] = self._decide(s, securities, journal, record,
                                          chain)
            # What the strategy read for THIS security, plus anything already
            # recorded — so a value entered before the strategy stopped
            # reading it never becomes invisible.
            cited = self._cited_ids(s["_decision"])
            shown = cited + [m for m in hand_entered.ids(s)
                             if m not in cited]
            s["_cited"] = cited
            # What the strategy asked this security about that no filing can
            # answer, plus anything already assessed — so an answer stays
            # readable after the strategy stops reading the question.
            s["_judgements"] = self._judgement_view(
                s, self._cited_ids(s["_decision"], "qualitative"))
            # The other two dated records the user writes. Both are read
            # through the same modules a purchase freezes from, so a screen
            # can never show a version the record would not have handed to a
            # decision.
            s["_thesis"] = {**thesis_mod.standing(s, today=today),
                            "history": thesis_mod.history(s)}
            s["_valuation"] = {**valuation.standing(s, today=today),
                               "history": valuation.history(s)}
            # A row per measure this security has something to show for, in
            # the words that measure was ENTERED under rather than today's.
            #
            # The membership test used to be `mid in bank_meta`, which meant a
            # bank entry deleted, or flipped from computed to qualitative,
            # took the row away — and with it the figure, its history, and the
            # only control that can withdraw it. The figure kept being served
            # into every new frozen snapshot from a record the user could no
            # longer reach. So a measure the bank has dropped keeps its row as
            # long as something was typed for it, and says it was dropped.
            s["_inputs"] = [
                {**hand_entered.shown_as(hand_entered.in_force(s, mid),
                                         bank_meta.get(mid), mid),
                 "cited": mid in cited,
                 # What was entered by hand for this measure, and when — plus
                 # everything entered before it. A value that was retyped the
                 # week a rule was about to fire is only visible if the
                 # earlier one renders too.
                 "entered": hand_entered.reading(s, mid),
                 "entries": hand_entered.history(s, mid)}
                for mid in shown
                if (bank_meta.get(mid) or {}).get("kind") == "computed"
                or (mid not in bank_meta and hand_entered.history(s, mid))]
            s["_computed"] = {
                eid: {"status": r.get("status"), "value": r.get("value"),
                      "reason": r.get("reason"),
                      "cautions": r.get("cautions") or [],
                      "provenance": r.get("provenance") or []}
                for eid, r in computed.items() if eid in shown}
            s["_value_sources"] = {k: v["source"] for k, v in values.items()
                                   if k in shown}
            # Returns and the scorecards read the EFFECTIVE price —
            # hand-entered over the fetched close. On the raw record a
            # position priced only by a fetch would silently drop out of the
            # analytics that judge the rules, which is the one place a
            # missing number would look like a settled answer.
            # The whole price view, not the number out of it. Everything
            # downstream that cannot produce a figure has to say why, and the
            # host has already worded each of those precisely — naming the
            # sibling share classes that ARE priced, or saying the figure on
            # record is not a price and how to clear it. Handing over the
            # value alone threw those away and left the browser guessing the
            # reason, which it got wrong for every case but one.
            priced.append(price)
            # Holding periods, not one running story. A security bought,
            # closed and bought back is two round trips, and the figures
            # that judge a round trip belong to one of them: which shares,
            # what they returned, what happened between selling and buying
            # back. Only the lifetime figure spans them, and it is named as
            # such so it can never sit in a column asking about the position
            # in front of you.
            s["_cycles"] = [self._cycle_view(s, c, price)
                            for c in portfolio.cycles(s)]
            open_cycle = portfolio.open_cycle(s)
            # "Nothing is held" is a complete answer rather than a missing
            # one, and it said so by being the same None as five real
            # absences. Stated, so the payload's own version of the collapse
            # is not reintroduced at the boundary the view reads.
            s["_return"] = portfolio.cycle_return(s, open_cycle, price) \
                if open_cycle else {
                    "status": "absent",
                    "reason": "no holding of this security is in progress"}
            s["_lifetime_return"] = portfolio.position_return(s, price)
            s["_lot_returns"] = {
                lot["id"]: portfolio.lot_return(s, lot, price)
                for lot in portfolio.lots(s, "buy")}

        by_ticker = dict(zip((s["ticker"] for s in securities), priced))

        return ok(
            allocation=self._allocation(securities, journal, record, chain,
                                        by_ticker),
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
            measure_changes=list(journal.get("measure_changes") or []),
            input_changes=list(journal.get("input_changes") or []),
            pending_changes=journals.pending(journal),
            # What each record is, in the host's words. The banner asking for
            # a reason has to say which of them moved, and a view holding its
            # own table of the two is a view that has to be edited when there
            # is a third — the wrong turn principle 9 names.
            change_records=journals.record_words(),
            # Every moment the definitions actually moved, so a decision
            # frozen before one of them can say so where it is read rather
            # than leaving the reader to join two screens. Moments and not a
            # count, because the comparison is per frozen entry and each one
            # was frozen on a different day. Which entries count as a move is
            # the host's to decide and is decided in engine/journals.py — a
            # release that changed only wording moved nothing.
            measures_moved_at=journals.measures_moved_at(journal),
            measures_version=journals.measures_baseline(journal)["version"],
            securities=securities,
            bank_meta=bank_meta,
            bank_problem=bank_problem,
            # The render types, so the view sorts and counts a state
            # whose meaning it does not know. It never learns which states
            # exist; it is told, every render.
            render_types={k: dict(v) for k, v in
                          contract.RENDER_TYPES.items()},
            # And the ways out of a state that stopped, so the button on a
            # blocked verdict is drawn from the host's own table rather than
            # from a list of labels kept in the view. The view held one, and
            # it knew about exactly one fix — which meant a state naming any
            # other rendered no button at all, silently, which is the dead
            # end the fix exists to close.
            state_fixes={k: dict(v) for k, v in
                         contract.STATE_FIXES.items()},
            ev_methods=EV_METHODS,
            exit_reasons=EXIT_REASONS,
            # None for a journal whose strategy screens for itself, which is
            # what hides the screen. The view asks whether this journal works
            # from a list, never which strategy is running.
            list=self._list_view(journal, record, securities),
            # What has happened to the account's cash, and what follows from
            # it. The balance is here rather than only inside the allocation
            # view because it is the account's own figure and outlives any one
            # screen; `movement` is here because it carries the one
            # distinction a cash balance on its own cannot make — money that
            # arrived against money that was earned — and a figure nothing
            # renders is a figure nobody can check.
            cash={"kinds": cash.kinds_view(),
                  # Which of them may be recorded right now. From the engine,
                  # so the screen never compares a kind against a word it
                  # holds itself — a button the write would refuse is the
                  # same wrong turn as a hardcoded measure id.
                  "offers": cash.offers(journal),
                  "opened": cash.opening(journal),
                  "ledger": cash.ledger(journal),
                  "balance": cash.balance(journal),
                  "movement": cash.movement(journal)},
            override_scorecard=portfolio.override_scorecard(
                securities, lambda s: by_ticker.get(s["ticker"])),
            exit_scorecard=portfolio.exit_scorecard(
                securities, lambda s: by_ticker.get(s["ticker"])),
            # And the third of the three ways this method gets broken. The
            # then-price has to come from a FETCHED series and never from the
            # effective price the other two read: a hand-entered figure is a
            # statement about now, and reaching it into the past would invent
            # the very number this panel is judging a decision against. A name
            # nobody ever fetched has no CIK, so it scores as unscored with
            # that said rather than dropping out of the count.
            pass_over_scorecard=portfolio.pass_over_scorecard(
                securities, lambda s: by_ticker.get(s["ticker"]),
                lambda s, day: dataview.price_view_asof(
                    s.get("cik"), s["ticker"], day) if s.get("cik") else
                {"value": None, "reason": "this journal has never fetched "
                 f"prices for {s['ticker']}, so what it was worth on the day "
                 "you passed on it is not on record — fetch its data and "
                 "this fills in"}),
            data_dir=str(store.data_dir()),
            data_security=self._data_security(),
        )

    @guarded
    def get_bank(self):
        return ok(bank=bank.bank_view())

    # -- journals ---------------------------------------------------------
    @guarded
    @locked
    def create_journal(self, name, strategy_id, inputs=None,
                       opening_cash=None, opening_cash_on=None):
        """Create a journal against one strategy and stamp it.

        The strategy is chosen here and never again. Two strategies means two
        journals, the way it would mean two accounts.

        `opening_cash` opens the journal's cash record rather than answering a
        question: what the account holds in cash is worked out from that
        record from here on, and the figure typed at setup is the day one it
        counts from. Optional, like every other setup answer — a journal with
        no opening balance reports its cash absent with the way out, and
        nothing about recording a decision is blocked by it.
        """
        strategies, _ = self._strategies()
        record = strategies.get(strategy_id)
        if record is None:
            return err("Choose a strategy. A journal is created against one "
                       "and stays there — it is what every decision in it "
                       "will be judged by.")
        typed = {k: v for k, v in
                 contract.user_answers(
                     record, self._typed(record.get("inputs"),
                                         inputs)).items()
                 if v is not None}
        chain = strategy_values.resolve(record, layers=[])
        _, problems = contract.check_inputs(record, typed, chain["values"])
        if problems:
            return err(" ".join(problems))
        journal = journals.create(name, record, bank.definitions(),
                                  inputs=typed)
        if opening_cash not in (None, ""):
            # Written after the journal exists and through the same call the
            # cash screen uses, so setup cannot open a record by a route the
            # rest of the program does not check — a second opening balance, a
            # negative figure and a future date are all refused in one place.
            try:
                cash.record(journal, cash.OPENING, opening_cash,
                            opening_cash_on)
            except ValueError as e:
                # The journal exists and is usable; only the balance is not
                # set. Saying so beats deleting a journal somebody just named
                # over a number they can type again in one click.
                journals.save(journal)
                journals.set_open(journal["id"])
                return ok(id=journal["id"], name=journal["name"],
                          cash_problem=str(e))
            journals.save(journal)
        journals.set_open(journal["id"])
        return ok(id=journal["id"], name=journal["name"])

    # -- cash -------------------------------------------------------------
    # What the account holds is derived from what happened to it. See
    # engine/cash.py for why an editable figure could not answer "how am I
    # doing" and this can.

    @guarded
    @locked
    def record_cash(self, kind, amount, when=None, note=""):
        """Append one cash entry — an opening balance, a deposit, a
        withdrawal, or a dividend received.

        Every refusal comes from the engine and names its fix. Nothing here
        decides whether the entry was wise; there is no such judgement to make
        about money arriving.
        """
        journal, _record, _chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        entry = cash.record(journal, kind, amount, when, note)
        self._write(journal)
        return ok(entry=entry,
                  balance=cash.balance(journal),
                  opened=entry["kind"] == cash.OPENING)

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

        # The same rule `journals.set_inputs` enforces at the write: an answer
        # the host works out for itself is not the journal's to hold. Applied
        # here too, so the check below runs against exactly what will be
        # stored rather than refusing a whole form over a key the save was
        # about to drop anyway.
        typed_inputs = contract.user_answers(
            record, merged(journal.get("inputs"), record.get("inputs"),
                           inputs))
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
    def rename_journal(self, journal_id, name):
        """Rename a journal. Its folder, and everything pointing at it, stay
        where they are — see journals.rename."""
        listed = {j["id"]: j for j in journals.list_journals()}
        if journal_id not in listed:
            return err("That journal is not on disk any more.")
        renamed = journals.rename(journal_id, name)
        return ok(id=journal_id, name=renamed["name"])

    @guarded
    @locked
    def delete_journal(self, journal_id, confirm_name):
        """Delete a journal and everything it recorded.

        The typed name is checked here rather than trusted to the dialog. A
        confirmation that the browser could skip is a confirmation the record
        does not actually have, and this is the one call in the program that
        destroys something no other copy exists of. Compared against the
        journal's *name* and not its id, because the name is what the user
        can see on the screen they are being asked about — asking someone to
        retype a slug they have never been shown is a rubber stamp with extra
        steps.

        Deliberately not refused when it is the open journal, or the last
        one. Both are recoverable situations — the next read resolves to
        whatever is left, or to the welcome screen — and a rule that made the
        final journal undeletable would leave a wrong first attempt on disk
        for good.
        """
        listed = {j["id"]: j for j in journals.list_journals()}
        if journal_id not in listed:
            return err("That journal is not on disk any more.")
        name = listed[journal_id].get("name") or journal_id
        if str(confirm_name or "").strip() != str(name).strip():
            return err(
                f'Type the journal\'s name exactly — "{name}" — to delete it. '
                "This removes every position, note and recorded decision in "
                "it, and nothing else holds a copy.")
        removed = journals.delete(journal_id)
        return ok(**removed)

    @guarded
    @locked
    def explain_change(self, record, seq, reason):
        """Write the reason a recorded change was made.

        `record` names which of this journal's append-only records the change
        sits on — the view is handed those words with the change itself and
        hands them back, rather than holding a list of the records that
        exist.
        """
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        change = journals.explain(journal, str(record), int(seq), reason)
        journals.save(journal)
        return ok(seq=change["seq"])

    # -- the list this journal works from --------------------------------
    @guarded
    @locked
    def import_list(self, pulled_on, pasted, floor=None):
        """Record one pull of the list this journal works from.

        Refuses rather than guesses. A paste with a line this cannot resolve
        to exactly one ticker comes back naming those lines and writes
        nothing — a list of thirty that quietly became twenty-nine looks
        exactly like a screen that returned twenty-nine, and the missing name
        is one the user will never buy and never know they skipped.

        Nothing is created here but the record itself. The names become
        securities when the user does something about one.
        """
        journal, record, *_ = self._open()
        if journal is None:
            return err("Create a journal first.")
        if record is None or not contract.declares_list(record):
            return err("This journal's strategy screens for itself; it does "
                       "not work from a list.")
        read = lists.read(pasted)
        if read["unreadable"]:
            shown = "; ".join(read["unreadable"][:4])
            more = (f" and {len(read['unreadable']) - 4} more"
                    if len(read["unreadable"]) > 4 else "")
            return err(
                f"{len(read['unreadable'])} line(s) here do not hold a "
                f"ticker this program can read: {shown}{more}. Nothing has "
                "been imported. Paste the screen's own table, or one ticker "
                "per line, and take out anything else.")
        entry = lists.record(journal, pulled_on, read["tickers"], floor)
        self._write(journal)
        return ok(pulled_on=entry["pulled_on"], n=len(entry["tickers"]),
                  seq=entry["seq"])

    @guarded
    @locked
    def pass_over(self, ticker, reason, name=None):
        """Record that a name the list offered is not being bought.

        It creates the security if the journal has never seen it, because the
        decision belongs on the security the way every other decision does —
        and a name considered and declined, with the reason on it, is exactly
        what this journal is for. Nothing about the verdict changes: the
        strategy goes on saying what its rules say, and this record says what
        was done about it.
        """
        journal, record, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        if record is None or not contract.declares_list(record):
            return err("This journal's strategy does not work from a list.")
        now = lists.current(journal)
        if now is None:
            return err("There is no list to pass over a name from.")
        symbol = str(ticker or "").strip().upper()
        if symbol not in (now.get("tickers") or []):
            return err(f"{symbol} is not on the list this journal is working "
                       "from, so there is nothing here to decline.")
        securities = journal.setdefault("securities", [])
        s = next((x for x in securities if x["ticker"] == symbol), None)
        if s is None:
            s = portfolio.new_security(symbol, name or symbol)
            securities.append(s)
        entry = lists.pass_over(s, now["pulled_on"], reason)
        self._write(journal)
        return ok(ticker=symbol, seq=entry["seq"], list=entry["list"])

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
        """Record hand-entered values on the security's dated record.

        Blank fields withdraw the value rather than storing a zero — a zero
        would render as a confident failure and absent renders as grey — and
        a withdrawal is an entry saying so on the day it happened, not a
        deletion. Only fields the dialog offered are touched, so a value the
        strategy has stopped reading is not silently dropped.

        Every change is appended. A figure quietly retyped the week a rule
        was about to fire is worth exactly as much as a judgement quietly
        remarked, and until now this screen was the one place in the journal
        where that left no trace. Nothing is appended where nothing changed:
        the dialog posts every field it offered on every save, and five
        visits should not read as five revisions.

        The price is the one value here that is still a mutable, undated
        slot. It is not a claim about the business — it is what the market
        said, superseded every time the market says something else, and the
        dated version of it is the price history the fetcher already keeps.
        """
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        # -- everything is checked before anything is written ------------
        # An append-only record cannot take an entry back, so "three fields
        # landed and the fourth was refused" is not a state to recover from
        # — it is a state that must be unreachable. The price is in the same
        # pass for the same reason: it is not on a dated record, but it
        # arrives from the same form, and a save that appended three figures
        # and then refused over the price would leave a rejection on screen
        # beside changes that went through.
        #
        # A price of nothing, or less than nothing, is not a price. Stored as
        # one it becomes a confident $0 market value, a 0% weight, and a -100%
        # on every open share — four settled-looking answers built on a number
        # that says the market valued the security at nothing. Blank is the way
        # to say you have no price, and it is a different thing.
        if price in (None, ""):
            entered = None
        else:
            try:
                entered = float(price)
            except (TypeError, ValueError):
                return err("The price must be a number, or left blank.")
            if entered <= 0:
                return err("A price has to be more than zero. Leave it blank "
                           "if you do not have one — the journal will say the "
                           "price is unknown rather than treat it as nothing.")
        # Bank membership, numbers-only and the judgement refusal all live in
        # engine/hand_entered rather than here: the dialog is a view and a
        # view is not a guarantee, and a second caller arriving later must
        # meet the same refusals this one does.
        for k, v in (metrics or {}).items():
            hand_entered.checked(k, v)

        # -- and only then is anything written ---------------------------
        for k, v in (metrics or {}).items():
            hand_entered.record(s, k, v)
        s["price"] = entered
        self._write(journal)
        return ok()

    @guarded
    @locked
    def record_judgement(self, ticker, entry_id, mark, reasoning):
        """Answer one qualitative bank entry for one security.

        Appended, never edited. A judgement rewritten at the moment it is
        about to matter is the most diagnostic thing this journal could hold,
        and a slot that can be overwritten holds none of it — so a change of
        mind is a new dated entry sitting above the old one, both readable.
        """
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        answer = judgements.assess(s, entry_id, mark, reasoning)
        self._write(journal)
        return ok(seq=answer["seq"], mark=answer["mark"])

    @guarded
    @locked
    def amend_thesis(self, ticker, thesis, falsifier, reason=""):
        """Append one version of why you own this and what would prove you
        wrong. Never edits, never replaces.

        A falsifier rewritten the week before it was about to fire is the
        most diagnostic event this journal could hold, and a slot that can
        be overwritten holds none of it. Both versions stay readable, and
        the amendment carries the reason it was made — because the thesis is
        what every override and every exit is graded against, and one that
        can be revised once the answer is known cannot grade anything.
        """
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        version = thesis_mod.amend(s, thesis, falsifier, reason)
        if version is not None:
            self._write(journal)
        return ok(amended=version is not None,
                  seq=(version or {}).get("seq"))

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
    def _entry_date(self, when, what):
        """(iso date or None, is_past), on the one date rule every dated
        entry obeys — a real date, and one that has happened.

        The refusal itself lives in engine/portfolio, at the write, so an
        entry cannot be dated ahead by any route. Checked again here because
        the preview evaluates before anything is written, and reconstructing
        a day that has not happened is not a thing the data can honestly
        answer.

        One function for a purchase and a sale, taking the word for the
        message. There were two of these and only one of them knew about the
        past at all — see `_evaluated_for`.
        """
        if not when:
            return None, False
        iso = portfolio.recorded_date(when, what)
        return iso, iso < date.today().isoformat()

    def _values_live(self, s, snap=None):
        """(values, price) — merged qualified values, hand-entered on top."""
        entry_ids = list(bank.meta())
        computed, price, _, _ = self._computed_layer(s, entry_ids, snap,
                                                    with_status=False)
        return (dataview.merged_values(s, computed,
                                       today=date.today().isoformat()), price)

    def _values_asof(self, s, as_of, snap=None):
        """(values, price, evaluation record) rebuilt from what was
        observable on `as_of`: filings filed by then, the close on or shortly
        before it — the same as-of rule the strategy's own context obeys.

        Hand-entered values sit on top exactly as in the live merge, and
        obey the same clock as the filings: the figure that was on record by
        `as_of` participates and names the day it was entered, and one
        entered afterwards does not participate at all. Both halves are in
        the evaluation record — what was there, and what was withheld —
        because a reconstruction that quietly dropped a value would look
        identical to one that never had it, and the second is the honest
        story only sometimes.
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
                                                 as_of, snap)
                avail = dataview.asof_availability(cik, tickers,
                                                   s["ticker"], as_of, snap)
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
                    # How far back the close had to be reached for, said
                    # rather than implied. Nothing refuses a distant one any
                    # more — how old is too old is a judgement, and it was
                    # the host's opinion when an eight-day gap was refused
                    # outright — so the distance is the fact, and this
                    # sentence is frozen onto the purchase. A record written
                    # once cannot be asked later what it left out.
                    gap = price.get("days_before")
                    parts.append(
                        f'priced at the {price["date"]} close'
                        + ("" if not gap else
                           ", which is the last one on record and "
                           + ("a day" if gap == 1 else f"{gap} days")
                           + f" before {as_of}"))
                    if price.get("terminal"):
                        parts.append(
                            "that price series has ended ("
                            + str(price["terminal"].get("reason")
                                  or "no reason recorded")
                            + "), so this is the last price the security ever "
                              "had rather than its price on the day")
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

        # Hand-entered values are dated now, so the reconstruction serves the
        # figure that was on record on the purchase date and nothing typed
        # afterwards. Both halves are worth saying: what was there, and what
        # the journal holds a figure for today that was not on record then —
        # otherwise a reader comparing this against the values screen finds a
        # number missing with nothing saying why.
        #
        # Said without naming a cause. There are two ways to be absent here —
        # entered after this day, or withdrawn on or before it — and the
        # summary cannot tell them apart without listing them one by one.
        # Each value carries its own reason in the record, which says exactly
        # which it was and when; a summary that guessed would be wrong every
        # time someone cleared a field.
        #
        # `today` is `as_of` here, not the real calendar. It is the clock the
        # *holding* history is read against — whether a judgement belongs to
        # a holding that had already closed — and under a pin the strategy's
        # own context reads it as the pinned day (engine/context.py). Handing
        # this side the real date would let one lot freeze two clocks: a
        # caution the strategy never saw filed into an append-only record, or
        # one it did see filed off. Live, `as_of` is None and the caller
        # passes the real day.
        values = dataview.merged_values(s, computed, as_of=as_of, today=as_of)
        manual = sorted(mid for mid, v in values.items()
                        if v["source"] == "manual")
        if manual:
            parts.append(f"{len(manual)} hand-entered value"
                         f"{'s' if len(manual) != 1 else ''} on record by "
                         f"{as_of}")
        later = sorted(mid for mid in hand_entered.ids(s) if mid not in manual)
        if later:
            parts.append(f"{len(later)} hand-entered value"
                         f"{'s' if len(later) != 1 else ''} not on record by "
                         f"{as_of}, so {'they' if len(later) != 1 else 'it'} "
                         "took no part in this")
        evaluation = {
            "basis": "reconstructed",
            "as_of": as_of,
            "filings_by_then": (avail or {}).get("filings_by_then", 0),
            "newest_filed": (avail or {}).get("newest_filed"),
            "priced": price.get("date"),
            # Renamed from "manual_undated" the day hand-entered values
            # stopped being undated. A snapshot is written once and never
            # revisited, so a key whose name asserts the opposite of what
            # the record holds is a wrong word frozen into permanent
            # history — worth changing now, while almost nothing carries it.
            "manual_on_record": manual,
            "manual_withheld": later,
            "note": "; ".join(parts),
        }
        return values, price, evaluation

    @staticmethod
    def _note_what_cannot_be_rebuilt(journal, record, when_iso, evaluation):
        """Add to a reconstruction's own account of itself the two things it
        rebuilt nothing for.

        The filings and the close reach back; these two do not, and a record
        written once can never be asked afterwards what it was working from.

        **The rules are today's.** A verdict rebuilt for 2019 is that day's
        data run through the strategy as it stands now — its logic and its
        thresholds — because the version in force in 2019 is not on this
        machine and, for a purchase predating the journal, never was. That is
        not a fault to fix; it is the only reconstruction there is. It is
        also the one part of a reconstruction that genuinely judges the past
        with the present, so the record says it in as many words rather than
        leaving it to be inferred from a version number.

        **The journal may not have existed.** Everything the user told it
        begins on the day it was created. Before that the journal holds no
        answers, and the figures built on them are absent rather than borrowed
        from now.

        **The cash record has its own day, and it is not that one.** Free cash
        stopped being an answer: it is worked out from a record whose opening
        balance carries a date the user chose, which is routinely *earlier*
        than the journal — opening it on the day the account actually started
        is the ordinary thing to do before backfilling history into it. So
        what the account was worth on a past day is asked of that record and
        of nothing else. Written off the answer this build actually produced,
        rather than off a second rule about dates: two rules about one fact is
        how the sentence came to say free cash was absent beside a weight
        computed from it — permanently, in a record that is written once and
        can never be asked again.
        """
        parts = [evaluation.get("note")] if evaluation.get("note") else []
        if record is not None:
            parts.append(
                f'judged by {record["name"]} v{record["version"]} as it '
                f'stands today (values v{record.get("values_version")}) — '
                "the version in force then is not recoverable, so the rules "
                "are the present ones and only the data is of the day")
        born = str(journal.get("created") or "")[:10]
        # Only where there was something to tell it. A strategy whose every
        # declared input the host works out for itself was never told
        # anything, so the sentence would be about nothing — and all four
        # shipped strategies are exactly that.
        asked = [f for f in ((record or {}).get("inputs") or [])
                 if f.get("id") not in contract.host_answered(record or {})]
        if born and when_iso < born and asked:
            parts.append(
                f"this journal was created on {born}, so it held no answers "
                f"on {when_iso} — anything you had told it, and every figure "
                "measured against those answers, is absent rather than taken "
                "from what you have told it since")
        held = cash.balance(journal, when_iso)
        if held["status"] != "known":
            parts.append(f"what this account held in cash on {when_iso} is "
                         f'not on record — {held["reason"]} — so the account '
                         "total and every share of it are absent")
        evaluation["note"] = "; ".join(p for p in parts if p)
        return evaluation

    def _evaluated_for(self, journal, record, chain, s, when_iso, is_past,
                       *, ask=True):
        """Everything an entry dated `when_iso` freezes: the verdict, the
        values behind it, the price seen, the record of how it was reached,
        and the versions of what the user had written by then.

        Today evaluates live; a past date is reconstructed from the data
        available by then, and says so everywhere.

        **One function for a purchase and a sale, and that is the point.**
        There were two paths here. The purchase path reconstructed; the sale
        path did not, so an exit backdated to 2019 was judged with today's
        filings and today's close, and the journal recorded a verdict it
        never computed — into `rule_triggered` and `signal_at_exit`, which
        are exactly what the panic-sell learning loop reads. Two paths is how
        that happened and one path is the fix: there is now nowhere to record
        a dated entry from that does not know about the clock, so the next
        kind of entry cannot reintroduce it by omission.

        The thesis and the valuation obey the same clock as the filings. An
        entry backdated to before either was written freezes nothing for it,
        which is the honest record of a decision made without one — never the
        version written afterwards, which would let a case composed with
        hindsight be presented as the one that was made at the time.

        `ask` False is the one caller that has no strategy to ask — the sale
        path when the bundle is not installed. It still reconstructs the
        values, because what was observable on the day does not depend on
        whether the strategy is on this machine, and the record then says the
        strategy could not be asked rather than showing a verdict that read
        clear.
        """
        securities = journal.get("securities", [])
        pin = when_iso if is_past else None
        # One reading of this company's stores for the whole entry. The
        # values and the verdict below are two passes over the same data and
        # each used to read it for itself, so a fetch landing between them
        # froze a record whose decision saw one filing more than the figures
        # recorded beside it as the reason for it. On a screen that heals on
        # the next render; here it does not — principle 3 says what was
        # captured at this moment is written once and never recomputed, so
        # the two halves disagreeing is permanent and uncorrectable.
        snap = self._snapshot_for(s)
        if is_past:
            values, price, evaluation = self._values_asof(s, when_iso, snap)
            self._note_what_cannot_be_rebuilt(journal, record, when_iso,
                                              evaluation)
        else:
            values, price = self._values_live(s, snap)
            evaluation = {"basis": "live", "as_of": date.today().isoformat()}
        decision = self._decide(s, securities, journal, record, chain,
                                as_of=pin, snap=snap) if ask else None
        return {
            "decision": decision,
            "values": values,
            "price": price,
            "evaluation": evaluation,
            "pin": pin,
            "thesis": thesis_mod.in_force(s, pin),
            "valuation": valuation.frozen(valuation.in_force(s, pin)),
        }

    @guarded
    @locked
    def preview_purchase(self, ticker, opened=None):
        """What the journal's strategy says for the chosen date, before
        anything is committed.

        The thesis and the claim come back as the same known-or-absent view
        every other screen reads, pinned to the day being recorded — not as
        the raw entries `_at_purchase` freezes. Two shapes for one document
        is how a screen comes to assert "no thesis on record" about a thesis
        it is holding: the absent branch reads a `status` the raw entry does
        not carry, and a raw entry's `reason` — the reason it was *amended*
        — reads as the reason there is nothing.
        """
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        opened_iso, is_past = self._entry_date(opened, "purchase")
        at = self._evaluated_for(journal, record, chain, s, opened_iso,
                                 is_past)
        # What this purchase is about to freeze, in front of the person
        # about to make it. A buy recorded against no thesis at all is
        # allowed and always will be — but it should be a thing you notice
        # you are doing, not a thing you find out about months later.
        pin, evaluation = at["pin"], at["evaluation"]
        clock = str(pin or date.today().isoformat())[:10]
        return ok(decision=at["decision"], basis=evaluation["basis"],
                  as_of=evaluation["as_of"], note=evaluation.get("note"),
                  # Which of the four ways this entry would go on the record,
                  # from the engine rather than worked out again in the
                  # browser. The dialog asks for a reason on an override and
                  # must not ask for one where there was no signal to
                  # override — and a second copy of that judgement in the
                  # view is how the two came to disagree about the same
                  # purchase.
                  recorded_as=portfolio.recorded_as(at["decision"],
                                                    evaluation["basis"]),
                  thesis=thesis_mod.standing(s, as_of=pin, today=clock),
                  valuation=valuation.standing(s, as_of=pin, today=clock))

    @guarded
    @locked
    def open_position(self, ticker, shares, cost, opened,
                      override_reason="", previewed_state=None,
                      recollection=""):
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        opened_iso, is_past = self._entry_date(opened, "purchase")
        at = self._evaluated_for(journal, record, chain, s, opened_iso,
                                 is_past)
        decision = at["decision"]
        lot = portfolio.add_lot(s, decision, float(shares), float(cost),
                                opened_iso, override_reason,
                                values=at["values"], price_seen=at["price"],
                                evaluation=at["evaluation"],
                                thesis=at["thesis"],
                                valuation=at["valuation"],
                                recollection=recollection)
        portfolio.note_recording(s, [lot])
        self._write(journal)
        state = (decision.get("state") or {}).get("id")
        return ok(override=bool(lot.get("override")),
                  unreconstructed=bool(lot.get("unreconstructed")),
                  basis=at["evaluation"]["basis"],
                  state=(decision.get("state") or {}).get("name"),
                  commit=portfolio.is_commit(decision),
                  state_changed=bool(previewed_state and state
                                     and previewed_state != state))

    @guarded
    @locked
    def preview_sale(self, ticker, exited=None):
        """What the journal's strategy says for the day a sale is dated,
        before anything is committed.

        The same shape the purchase preview returns, from the same
        evaluation, because they are the same question asked about different
        days. It exists for the backdated case: a sale entered out of a
        brokerage statement freezes a verdict, and the person entering it
        should see which one — and see it named as a reconstruction — rather
        than find out from a toast afterwards.

        **Everything the sale dialog states about the position comes from
        here**, on the sale's own clock: how many shares were held that day,
        which purchases they were, and what the security closed at. The dialog
        used to read all three off the live payload — today's share count as
        the default for "sell everything", today's open lots as the note about
        which ones go first, today's close as the reference beside the price
        field — beside a date picker set to 2019. Every one of those is a
        sentence about the wrong day, and the last one is a number the reader
        was being invited to type into a record that can never be corrected.
        """
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        exited_iso, is_past = self._entry_date(exited, "sale")
        at = self._evaluated_for(journal, record, chain, s, exited_iso,
                                 is_past, ask=record is not None)
        pin, evaluation = at["pin"], at["evaluation"]
        clock = str(pin or date.today().isoformat())[:10]
        return ok(decision=at["decision"], basis=evaluation["basis"],
                  as_of=evaluation["as_of"], note=evaluation.get("note"),
                  # Whether the strategy answered at all. A sale recorded
                  # where nothing could be rebuilt says so and records no
                  # signal — never "no rule triggered this exit", which
                  # claims a signal was read and came back clear.
                  verdict=portfolio.is_verdict(at["decision"]),
                  # Which of the four ways this sale would go on the record,
                  # and whether it owes a written reason — both from the
                  # engine rather than worked out again in the browser. A
                  # second copy of that judgement in the view is how the
                  # purchase dialog and the purchase record came to disagree
                  # about the same entry, and the sentence collected here is
                  # worth having only if it is asked for on exactly the sales
                  # that go against a verdict.
                  recorded_as=portfolio.sale_recorded_as(
                      at["decision"], evaluation["basis"]),
                  reason_owed=portfolio.sale_reason_owed(
                      at["decision"], evaluation["basis"]),
                  # What "everything" means for a sale dated this day. The
                  # write resolves it again from the same reader, so the
                  # number on the screen and the number recorded are one
                  # answer rather than two that agree on a position nobody
                  # has added to.
                  held=portfolio.shares_held(s, exited_iso),
                  # The purchases a sale dated this day can draw on, oldest
                  # first — what the allocation will actually spend.
                  lots=[{"date": l["date"], "remaining": l["remaining"]}
                        for l in portfolio.open_lots(s, exited_iso)
                        if l["open"]],
                  # The close that belonged to that day, offered as a
                  # reference and never prefilled. Nothing here is what the
                  # user got; what it must not be is a price from a different
                  # year presented beside the field.
                  price=self._price_known(at["price"]) | {
                      "date": at["price"].get("date"),
                      "source": at["price"].get("source"),
                      "terminal": at["price"].get("terminal")},
                  thesis=thesis_mod.standing(s, as_of=pin, today=clock))

    @guarded
    @locked
    def sell_shares(self, ticker, reason, price, exited, shares=None,
                    override_reason="", previewed_state=None):
        """Record a sale, whole or partial.

        `shares` left out sells everything held **on the day the sale is
        dated**, which is what closing a position means. That resolution
        belongs to the write and is left to it: this method knows the count on
        the screen, and the screen is standing in today. A partial sale leaves
        the remaining lots exactly as they are — nothing is rewritten, a sale
        is one more appended entry naming what it drew on.

        A sale dated in the past is judged with the data of that day, exactly
        as a purchase is — see `_evaluated_for`. It used to be judged with
        today's, which put a verdict the strategy was never asked for into
        `signal_at_exit` and `rule_triggered`, and those are what the exit
        analytics teach from.

        `override_reason` is what the user wrote about selling against the
        strategy. It is never a condition of recording: the sale is written
        with or without it, and an empty one goes on the record as "No reason
        given." — see engine/portfolio.sell_lots. The dialog asks; nothing
        refuses.

        `previewed_state` is the state the dialog was showing. The verdict is
        worked out again here, and it can have moved while the dialog was open
        — a fetch landing is enough. Where it has, what goes on the record is
        not what the person was looking at, and the reply says so: the dialog
        may have asked for a sentence that turned out not to be owed, or —
        worse — not asked for one that now is. Same signal the purchase path
        carries, for the same reason.
        """
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        # None all the way to the write, where the sale's own date is known.
        # It used to be resolved here, against `shares_held(s)` — today's
        # count — so closing out an exit dated two years back recorded
        # whatever is held now: too many, and the write refused a sale that
        # genuinely happened; too few, and it wrote a smaller exit than the
        # one that happened, leaving the holding period it should have closed
        # open with a residue nobody ever owned. Neither is loud.
        try:
            n = None if shares in (None, "") else float(shares)
        except (TypeError, ValueError):
            return err("The number of shares sold must be a number.")
        # Before anything is evaluated, on the same rule the purchase screen
        # obeys. The write refuses it too, which is where the guarantee
        # actually lives — this is only so the message names the date rather
        # than arriving after a strategy has been asked about a day that has
        # not happened.
        exited_iso, is_past = self._entry_date(exited, "sale")
        # A strategy that is not installed is not a signal that read clear:
        # the sale records that it could not be asked at all. The values are
        # still reconstructed for the day, because what was observable then
        # does not depend on what is on this machine now.
        at = self._evaluated_for(journal, record, chain, s, exited_iso,
                                 is_past, ask=record is not None)
        # The thesis standing at the sale, frozen with it. This is where it
        # gets graded — "did the falsifier fire, or did I talk myself out of
        # it" is a question about the version that was on record on the day
        # of the sale, which under a reconstruction is not the version
        # standing now.
        lot = portfolio.sell_lots(s, at["decision"], reason, n, float(price),
                                  exited_iso, values=at["values"],
                                  price_seen=at["price"],
                                  evaluation=at["evaluation"],
                                  thesis=at["thesis"],
                                  override_reason=override_reason)
        portfolio.note_recording(s, [lot])
        self._write(journal)
        state = ((at["decision"] or {}).get("state") or {}).get("id")
        return ok(rule_triggered=lot["rule_triggered"],
                  signal=lot["signal_at_exit"],
                  basis=at["evaluation"]["basis"],
                  as_of=at["evaluation"]["as_of"],
                  remaining=portfolio.shares_held(s),
                  # How it went on the record, read back off the entry rather
                  # than from what the preview predicted: the state can move
                  # between the dialog opening and the write, and the screen
                  # has to describe what was written.
                  recorded_as=portfolio.sold_as(lot),
                  override=bool(lot.get("override")),
                  # And whether a sentence was actually captured. "No reason
                  # given." is the host's own words, and a screen that could
                  # not tell it from the user's would say their reason is on
                  # the record when nothing is.
                  reason_given=bool((lot.get("override") or {})
                                    .get("reason_given")),
                  state_changed=bool(previewed_state and state
                                     and previewed_state != state),
                  strategy_name=(lot["strategy"] or {}).get("name"))

    # -- backfill ----------------------------------------------------------
    # Entering a position you already own, out of your own history.
    #
    # The journal is only usable forward from the day it was started, and
    # every analytic in it — the override scorecard, the exit reasons, what
    # happened after you sold — has nothing to work against until enough
    # decisions accumulate. Backfill is what gives them something. It is also
    # the fastest way to poison them, which is why the two corrections above
    # had to land first: a batch of old purchases against a strategy nothing
    # could reconstruct used to manufacture a pile of "bought against signal"
    # records describing data coverage rather than discipline.
    #
    # Nothing here is a new evaluation path. Each entry goes through exactly
    # the write the single-entry dialogs use, evaluated by exactly the
    # function they evaluate through, against the data of its own day. What
    # this adds is a sequence: several dated entries applied in order, each
    # one seeing the journal as the ones before it left it, so a sale in 2016
    # is checked against the shares that were held in 2016.

    _BACKFILL_KINDS = ("buy", "sell")

    def _backfill_event(self, raw, index):
        """One requested entry, in the types the record needs, or a refusal
        naming the row.

        Checked here, before any of them are applied, only for the things
        that are about the *request* — a kind nobody can record, a date that
        is not a date, a count that is not a number. Everything about whether
        the entry is possible against the position — selling shares that were
        never bought, a sale dated before the purchase it draws on — is left
        to engine/portfolio, which is where those rules live and where they
        are enforced for every other caller.
        """
        where = f"Entry {index + 1}"
        kind = str((raw or {}).get("kind") or "").strip()
        if kind not in self._BACKFILL_KINDS:
            raise ValueError(
                f'{where} is a "{kind or "blank"}", and a position is built '
                "out of purchases and sales. Choose one.")
        what = "purchase" if kind == "buy" else "sale"
        when = str(raw.get("date") or "").strip()
        if not when:
            raise ValueError(
                f"{where} has no date. Every entry is judged against the "
                "data of its own day, so the day is the one thing it cannot "
                "be recorded without.")
        try:
            iso = portfolio.recorded_date(when, what)
        except ValueError as e:
            raise ValueError(f"{where}: {e}")
        try:
            shares = float(str(raw.get("shares") or "").strip())
            price = float(str(raw.get("price") or "").strip())
        except (TypeError, ValueError):
            raise ValueError(
                f"{where} needs a share count and a price per share, both as "
                "numbers. Nothing is filled in for you — a price this "
                "program guessed would go into an append-only record as "
                "though you had read it off a statement.")
        return {"index": index, "kind": kind, "what": what, "date": iso,
                "is_past": iso < date.today().isoformat(),
                "shares": shares, "price": price,
                # A sale entered from history may honestly have no reason on
                # it. Forcing a choice from the list would manufacture the
                # one fact the exit analytics exist to read, and "I do not
                # remember why I sold in 2014" is itself worth counting.
                "reason": (str(raw.get("reason") or "").strip()
                           or portfolio.UNSTATED_REASON) if kind == "sell"
                else None}

    def _run_backfill(self, ticker, events, recollection, commit):
        """Apply a run of dated entries to one security, oldest first.

        The preview and the recording are this one function, run against a
        copy of the journal or against the real one. That is deliberate and
        it is the only honest arrangement: a preview built from a second
        implementation can promise a verdict the write does not produce, and
        the thing being previewed here is what is about to enter a record
        that can never be corrected.

        Stops at the first entry that cannot be recorded, and writes nothing
        unless every one of them can. Continuing past a failure would
        evaluate the entries after it against a position missing a purchase,
        so every row below the broken one would be wrong in a way that looks
        like an answer. Nothing is written on the way to the failure either —
        a journal is loaded fresh on every call and only saved at the end, so
        a run that stops halfway leaves the file exactly as it was.
        """
        journal, record, chain, _ = self._open()
        if journal is None:
            return err("No journal is open.")
        if not commit:
            # The preview mutates a security as it goes — that is how entry
            # four is evaluated against the position entries one to three
            # left behind — so it works on a copy and the real journal is
            # never touched by a screen that has not been confirmed.
            journal = copy.deepcopy(journal)
        s = self._find(journal, ticker)

        ordered = sorted((self._backfill_event(e, i)
                          for i, e in enumerate(events or [])),
                         key=lambda e: (e["date"], e["index"]))
        if not ordered:
            return err("Add at least one purchase. A position starts with "
                       "one, and everything else is recorded against it.")
        if ordered[0]["kind"] != "buy" and not portfolio.is_held(
                s, ordered[0]["date"]):
            return err(
                f'The earliest entry is a sale dated {ordered[0]["date"]}, '
                f"and no {s['ticker']} was held then. A position is built "
                "from the purchase up — record what you bought first.")

        results, made, problem = [], [], None
        remembered = str(recollection or "").strip()
        for ev in ordered:
            at = self._evaluated_for(journal, record, chain, s, ev["date"],
                                     ev["is_past"], ask=record is not None)
            decision, evaluation = at["decision"], at["evaluation"]
            row = {
                "index": ev["index"], "kind": ev["kind"], "date": ev["date"],
                "shares": ev["shares"], "price": ev["price"],
                "reason": ev["reason"],
                "basis": evaluation["basis"], "as_of": evaluation["as_of"],
                "note": evaluation.get("note"),
                "state": ((decision or {}).get("state") or {}).get("name"),
                "summary": ((decision or {}).get("reason") or {}).get(
                    "summary"),
                "problem": None,
            }
            try:
                if ev["kind"] == "buy":
                    # The recollection goes on the purchase that opens the
                    # run and on no other. It is what somebody can honestly
                    # answer — "what was I thinking when I bought this" — and
                    # asking it again of every add five years later is asking
                    # for something invented.
                    lot = portfolio.add_lot(
                        s, decision, ev["shares"], ev["price"], ev["date"],
                        values=at["values"], price_seen=at["price"],
                        evaluation=evaluation, thesis=at["thesis"],
                        valuation=at["valuation"],
                        recollection=remembered if not made else "")
                    row["recorded_as"] = portfolio.recorded_as(
                        decision, evaluation["basis"])
                else:
                    lot = portfolio.sell_lots(
                        s, decision, ev["reason"], ev["shares"], ev["price"],
                        ev["date"], values=at["values"],
                        price_seen=at["price"], evaluation=evaluation,
                        thesis=at["thesis"])
                    row["rule_triggered"] = lot["rule_triggered"]
                    row["signal"] = lot["signal_at_exit"]
                    # No written reason is collected for a sale entered out of
                    # history, on the rule the purchase side already follows:
                    # the sentence this asks for is the one somebody wrote on
                    # the day, and one composed now about a sale in 2016 would
                    # be hindsight filed where a contemporaneous reason
                    # belongs. It still records as an override, so the exit
                    # analytics can see it.
                    row["recorded_as"] = portfolio.sold_as(lot)
                made.append(lot)
            except (ValueError, store.StoreError) as e:
                row["problem"] = str(e)
                problem = str(e)
                results.append(row)
                break
            results.append(row)

        pending = [e["index"] for e in ordered
                   if e["index"] not in {r["index"] for r in results}]
        if problem is None and commit:
            portfolio.note_recording(s, made)
            self._write(journal)
        return ok(events=results, problem=problem, unchecked=pending,
                  recorded=bool(problem is None and commit),
                  # What the run would leave behind, so the dialog can say
                  # "this ends with 40 shares held" rather than leaving the
                  # reader to add up their own rows.
                  shares_after=portfolio.shares_held(s),
                  held_after=portfolio.is_held(s))

    @guarded
    @locked
    def preview_backfill(self, ticker, events=None, recollection=""):
        """What a run of historical entries would record, before any of it
        is permanent. Nothing is written."""
        return self._run_backfill(ticker, events, recollection, commit=False)

    @guarded
    @locked
    def record_backfill(self, ticker, events=None, recollection=""):
        """Record a run of historical entries. All of them or none."""
        return self._run_backfill(ticker, events, recollection, commit=True)

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

        price = dataview.price_view(s, cik, s["ticker"])
        if price["value"] is None:
            price_item = {"status": "absent",
                          "reason": "no price is stored — fetch prices, or "
                                    "enter one in Edit values"}
        elif price["source"] == "manual":
            price_item = {"status": "computed", "source": "manual",
                          "value": float(price["value"]), "asof": None,
                          "provenance": ["hand-entered price from Edit "
                                         "values (undated)"],
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
        entered = hand_entered.reading(s, "fcf_ttm")
        if entered["status"] == "known":
            prov = list(entered["provenance"])
            if fcf["status"] == "computed":
                prov.append(f"overrides the computed ${fcf['value']:,.1f}M "
                            "from filings — clear the hand-entered value in "
                            "Edit values to use it")
            fcf = {"status": "computed", "source": "manual",
                   "value": round(float(entered["value"]) / 1e6, 3),
                   "asof": entered["recorded"], "provenance": prov,
                   "cautions": list(entered["cautions"])}
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
    def record_valuation(self, ticker, method, inputs, sources=None):
        """Append one valuation claim. Never edits, never replaces.

        A valuation is the case for a specific purchase, made against a
        price and a filing that both move. Overwriting the last one would
        lose the claim you actually bought on and leave a number that reads
        as though you had always thought this — including the claims that
        talked you out of buying, which are the ones worth reading back.

        Where the assumptions are identical to the standing claim nothing is
        appended: re-running the same numbers is not a new claim about
        anything, and a history nobody can wade through is a history nobody
        consults.
        """
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        s = self._find(journal, ticker)
        entry, result = valuation.claim(s, method, inputs or {}, sources)
        if entry is not None:
            self._write(journal)
        return ok(result=result, recorded=entry is not None)

    @guarded
    @locked
    def recompute_ev(self, ticker):
        """The number the standing claim's assumptions solve to today.

        Derived rather than stored, so there is no second opinion about a
        figure the assumptions already settle. The frozen copy on a purchase
        is the exception, and it is a different record.
        """
        journal, *_ = self._open()
        if journal is None:
            return err("No journal is open.")
        claim = valuation.in_force(self._find(journal, ticker))
        if not claim:
            return ok(result=None)
        return ok(result=valuation.result_of(claim))

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

    SAMPLES = Path(__file__).resolve().parent / "data.template"

    def _sample_files(self) -> list:
        """Every shipped sample, discovered rather than listed.

        There is one per strategy that has one, and adding another is adding
        a file — the same rule strategies themselves follow. A hardcoded list
        here would be a second place the set of samples is written down, and
        the day they disagreed the missing one would simply never appear.
        """
        return sorted(self.SAMPLES.glob("sample-*.json"))

    def _load_one_sample(self, path):
        """(journal, securities) for one sample file, or (None, message).

        Nothing already in the user's data is touched: a sample is always a
        new journal, never a fill of the open one. That is principle 6 doing
        the deciding rather than a preference — a journal has exactly one
        strategy, and pouring these securities into a journal stamped with
        another would judge them by rules their stories were never about.
        """
        try:
            sample = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            return None, f"{path.name} could not be read ({e})."
        strategies, _ = self._strategies()
        record = strategies.get(sample.get("strategy"))
        if record is None:
            return None, (f'{path.name} is written against the '
                          f'"{sample.get("strategy")}" strategy, which is '
                          "not installed here, so its verdicts could not be "
                          "produced.")
        journal = journals.create(f"Sample — {record['name']}", record,
                                  bank.definitions())
        journal["securities"] = sample["securities"]
        # The cash a sample starts with opens its record rather than answering
        # a question, exactly as it does in the setup flow. A sample carrying
        # deposits and dividends of its own would tell a story about cash that
        # nothing in these files was built to support; what it needs is the
        # balance its sizing rules are measured against.
        if sample.get("free_cash") not in (None, ""):
            cash.record(journal, cash.OPENING, sample["free_cash"],
                        str(journal["created"])[:10])
        # A sample for a strategy that works from a list carries the imports
        # that were made into it, whole. They are the buy side of its story:
        # without them every verdict in the journal comes back blocked on a
        # list nobody can import for the user, and the sample would show
        # nothing but its own empty state.
        journal[lists.KEY] = list(sample.get(lists.KEY) or [])
        journals.save(journal)
        return journal, None

    @guarded
    @locked
    def load_sample(self):
        """Create the demonstration journals from invented companies.

        One journal per shipped sample, which is one per strategy that has
        one. They arrive together on purpose: the most useful thing about
        having two is that the same kind of company gets opposite verdicts
        from them, and a reader who loaded only one would never see it. It is
        also the plainest statement of the rule the whole program is built
        on — trading two strategies means two journals, the way it would mean
        two accounts.

        Each file holds securities exactly as a journal stores them —
        appended lots, frozen entry snapshots, dated hand-entered figures,
        dated assessments and dated notes — because each was built by driving
        this API against a scratch directory (tools/make_sample.py and its
        siblings). Every company and every figure in them is invented.

        A sample whose strategy is not installed is skipped with its reason
        rather than taking the others down with it, for the same reason a
        strategy that fails to load does not prevent the rest from loading.
        """
        files = self._sample_files()
        if not files:
            return err("No sample files are in this build. They are written "
                       "by the scripts in tools/.")
        made, skipped = [], []
        for path in files:
            journal, problem = self._load_one_sample(path)
            if problem:
                skipped.append(problem)
            else:
                made.append(journal)
        if not made:
            return err(" ".join(skipped))
        journals.set_open(made[0]["id"])
        return ok(names=[j["name"] for j in made],
                  journals=len(made),
                  n=sum(len(j["securities"]) for j in made),
                  skipped=skipped)

    @guarded
    @locked
    def clear_all(self):
        """Empty the open journal of securities. Its strategy stamp, its
        measure stamp, its settings and both change records stay — they are
        what the journal *is*, and clearing positions is not a statement that
        the rules never moved."""
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
