"""Ledger. A portfolio journal that checks holdings against rules you wrote.

    python app.py            run the app
    python app.py --reset    start again from the template

The app never places a trade and has no broker credentials. It reads what you
tell it, checks it against profiles you configured, and shows you the answer.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import threading
import traceback
from datetime import date
from pathlib import Path

import webview

from engine import (backup, dataview, fetch, migrate, portfolio,
                    profile_history, profiles, secrets, store, tickermap,
                    tiingo)
from engine.evaluate import evaluate_buy, evaluate_position
from engine.expected_value import EV_METHODS, EVError
from engine.expected_value import compute as compute_ev
from engine.portfolio import EXIT_REASONS

UI_DIR = Path(__file__).resolve().parent / "ui"
TEMPLATE_DIR = Path(__file__).resolve().parent / "data.template"


def ok(**kw):
    return {"ok": True, **kw}


def err(message):
    return {"ok": False, "error": str(message)}


def guarded(fn):
    """Any exception becomes a message in the UI rather than a dead window."""
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except (EVError, ValueError) as e:
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
        # cycle on securities.json goes through this lock, or two concurrent
        # writes silently drop each other's changes — including hand-entered
        # values, which nothing may ever overwrite.
        self._doc_lock = threading.RLock()

    # -- data ------------------------------------------------------------
    def _securities_doc(self) -> dict:
        return store.load("securities.json")

    def _write_securities_doc(self, doc):
        doc["metrics_vocabulary"] = migrate.VOCABULARY
        store.save("securities.json", doc)

    def _find(self, securities, ticker):
        for s in securities:
            if s["ticker"] == ticker:
                return s
        raise ValueError(f"{ticker} is not in the journal.")

    def _resolved_profiles(self):
        """(ordered files, {file: resolved profile}, page-level errors).

        Versions come from the history, which is synced first so an edit made
        outside the app is recorded before anything is scored under it.
        """
        hist = profile_history.sync()
        plist, errors = profiles.list_profiles()
        resolved, order = {}, []
        for p in plist:
            try:
                r = profiles.resolve_profile(p["file"])
            except Exception as e:                  # noqa: BLE001
                errors.append(f'{p["file"]} could not be resolved: {e}')
                continue
            r["version"] = profile_history.current_version(hist, p["file"])
            r["history"] = profile_history.summary(hist, p["file"])
            resolved[p["file"]] = r
            order.append(p["file"])
        return order, resolved, errors, hist

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

    def _used_metric_ids(self, order, resolved, securities):
        """Bank ids any profile references (incl. sell measured_on) plus any
        a security already carries — the set worth computing and entering."""
        used: dict[str, list] = {}
        for file in order:
            prof = resolved[file]
            for tier in prof.get("tiers", []):
                for e in tier.get("entries", []):
                    ids = [e.get("metric")]
                    for block in (e.get("sell"), e.get("flag")):
                        if isinstance(block, dict) and block.get("measured_on"):
                            ids.append(str(block["measured_on"]))
                    for mid in ids:
                        if mid:
                            users = used.setdefault(mid, [])
                            if prof["name"] not in users:
                                users.append(prof["name"])
        for s in securities:
            for mid in (s.get("metrics") or {}):
                used.setdefault(mid, [])
        return used

    def _computed_layer(self, s, used_ids):
        """The security's computed values and status, or empty layers when
        nothing has been fetched. Never raises — a broken data layer must not
        take the journal down with it."""
        cik = s.get("cik")
        if not cik:
            return {}, dataview.price_view(s, None, [s["ticker"]]), None, []
        tickers = self._tickers_of(s)
        try:
            computed = dataview.computed_results(cik, tickers, used_ids)
            price = dataview.price_view(s, cik, tickers)
            status = dataview.data_status(cik)
        except Exception as e:                          # noqa: BLE001
            traceback.print_exc()
            return {}, dataview.price_view(s, None, [s["ticker"]]), \
                {"error": f"the data layer failed: {e}"}, tickers
        return computed, price, status, tickers

    def _migrate_secrets(self):
        """Move any plaintext key or identity out of the exportable settings
        the moment it is seen — including one that just arrived inside an
        imported bundle."""
        with self._doc_lock:
            settings = store.load("settings.json")
            if secrets.migrate_from_settings(settings):
                store.save("settings.json", settings)

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
            "rotate_notice": bool(secrets.local_get(secrets.ROTATE_FLAG)),
            "sec_identity": str(secrets.local_get("sec_identity") or ""),
            "problem": problem,
        }

    # -- read ------------------------------------------------------------
    @guarded
    def get_state(self):
        migration = migrate.ensure_migrated()
        self._migrate_secrets()
        order, resolved, cfg_errors, hist = self._resolved_profiles()

        doc = self._securities_doc()
        securities = doc.get("securities", [])
        used_ids = self._used_metric_ids(order, resolved, securities)
        param_ids = dataview.parameterized_entry_ids()

        eval_secs = []      # merged-value views, for the scorecards
        for s in securities:
            computed, price, dstatus, tickers = self._computed_layer(s, used_ids)
            values, sources = dataview.merged_values(s, computed)
            s["_computed"] = {
                eid: {"status": r.get("status"), "value": r.get("value"),
                      "reason": r.get("reason"),
                      "cautions": r.get("cautions") or [],
                      "provenance": r.get("provenance") or []}
                for eid, r in computed.items()}
            s["_value_sources"] = sources
            s["_price"] = price
            s["_data"] = dstatus
            s["_fetch"] = fetch.status_of(s["ticker"])

            eval_sec = {**s, "metrics": values, "price": price["value"]}
            eval_secs.append(eval_sec)
            s["_eval"] = {}
            for file, prof in resolved.items():
                pv, _ = self._values_for_profile(s, values, sources, prof,
                                                 param_ids, tickers)
                view = {"buy": evaluate_buy(pv, prof)}
                if s.get("bucket") == "holdings":
                    view["position"] = evaluate_position(
                        {**eval_sec, "metrics": pv}, prof)
                s["_eval"][file] = view
            s["_own"] = self._own_view(s, resolved, eval_sec, values, sources,
                                       param_ids, tickers)
            s["_realised"] = portfolio._realised(eval_sec)
            s["_since_exit"] = portfolio._since_exit(eval_sec)

        return ok(
            settings=store.load("settings.json"),
            securities=securities,
            profile_order=order,
            profiles=resolved,
            profile_errors=cfg_errors,
            pending_changes=profile_history.pending(hist),
            bank_meta=self._bank_meta(),
            input_metrics=self._input_metrics(order, resolved, securities),
            legacy_labels=migrate.LEGACY_LABELS,
            migration=migration,
            ev_methods=EV_METHODS,
            exit_reasons=EXIT_REASONS,
            # Scorecards read the merged view (hand-entered price over
            # fetched close); on the raw records a fetched-price position
            # would silently drop out of the analytics that judge the rules.
            override_scorecard=portfolio.override_scorecard(eval_secs),
            exit_scorecard=portfolio.exit_scorecard(eval_secs),
            data_dir=str(store.data_dir()),
            data_security=self._data_security(),
        )

    def _values_for_profile(self, s, values, sources, prof, param_ids,
                            tickers):
        """Merged values with this profile's parameterized entries overlaid."""
        cik = s.get("cik")
        if not cik:
            return values, sources
        try:
            return dataview.overlay_for_profile(cik, tickers, values, sources,
                                                prof, param_ids)
        except Exception:                               # noqa: BLE001
            return values, sources

    def _own_view(self, s, resolved, eval_sec, values, sources, param_ids,
                  tickers):
        """The position judged under the profile it was bought under.

        A lens is for looking; the entry profile is the contract the position
        lives under, and it is what the header counts. Positions recorded
        before profiles have no governing profile — that absence is reported,
        not papered over.
        """
        if s.get("bucket") != "holdings":
            return None
        snap = s.get("entry_snapshot") or {}
        if "ruleset_version" in snap:
            return {"legacy": True, "profile": None, "state": None}
        ref = snap.get("profile") or {}
        prof = resolved.get(ref.get("file"))
        if prof is None:
            return {"legacy": False, "profile": ref, "state": None,
                    "problem": f'The profile this was bought under '
                               f'({ref.get("name") or ref.get("file")}) is no '
                               "longer on disk, so its sell rules cannot run."}
        pv, _ = self._values_for_profile(s, values, sources, prof, param_ids,
                                         tickers)
        # The sell rules that run are the profile's CURRENT content; the
        # snapshot records which version the purchase was made under. Both
        # versions travel so the UI can label them honestly.
        return {"legacy": False,
                "profile": {**ref, "version": prof["version"]},
                "bought_version": ref.get("version"),
                "state": evaluate_position({**eval_sec, "metrics": pv}, prof)}

    def _bank_meta(self):
        doc = profiles.load_bank("metric-bank")
        return {str(e.get("id")): {
                    "label": profiles.to_plain(e.get("label")),
                    "unit": profiles.to_plain(e.get("unit")),
                    "format": profiles.to_plain(e.get("format")),
                    "kind": profiles.to_plain(e.get("kind")),
                    "polarity": profiles.to_plain(e.get("polarity")),
                } for e in (doc.get("entries") or [])}

    def _input_metrics(self, order, resolved, securities=()):
        """The metrics worth entering: every bank entry any profile on disk
        references, including the second measures sells are taken on — plus
        any bank entry a security already carries a value for, so nothing
        recorded becomes invisible when the profiles stop using it. Never the
        whole bank."""
        used: dict[str, list] = {}
        for file in order:
            prof = resolved[file]
            for tier in prof.get("tiers", []):
                for e in tier.get("entries", []):
                    ids = [e.get("metric")]
                    for block in (e.get("sell"), e.get("flag")):
                        if isinstance(block, dict) and block.get("measured_on"):
                            ids.append(str(block["measured_on"]))
                    for mid in ids:
                        if mid:
                            users = used.setdefault(mid, [])
                            if prof["name"] not in users:
                                users.append(prof["name"])
        for s in securities:
            for mid in (s.get("metrics") or {}):
                used.setdefault(mid, [])        # recorded, no current user

        doc = profiles.load_bank("metric-bank")
        out = []
        for e in (doc.get("entries") or []):    # bank order, so themes group
            mid = str(e.get("id"))
            if mid not in used or profiles.to_plain(e.get("kind")) != "computed":
                continue
            expl = e.get("explanation") or {}
            out.append({
                "id": mid,
                "label": profiles.to_plain(e.get("label")),
                "unit": profiles.to_plain(e.get("unit")),
                "format": profiles.to_plain(e.get("format")),
                "plain": profiles.to_plain(expl.get("plain")),
                "used_by": used[mid],
            })
        return out

    @guarded
    def get_bank(self):
        return ok(bank=profiles.bank_view())

    # -- profiles ---------------------------------------------------------
    @guarded
    def set_active_profile(self, file_name):
        settings = store.load("settings.json")
        settings["active_profile"] = file_name
        store.save("settings.json", settings)
        return ok()

    @guarded
    def explain_profile_change(self, file_name, version, reason):
        v = profile_history.explain(file_name, version, reason)
        return ok(version=v["version"])

    # -- securities ------------------------------------------------------
    @guarded
    @locked
    def add_security(self, ticker, name):
        if not (ticker or "").strip():
            return err("A ticker is required.")
        doc = self._securities_doc()
        securities = doc.get("securities", [])
        if any(s["ticker"] == ticker.upper().strip() for s in securities):
            return err(f"{ticker.upper()} is already in the journal.")
        securities.append(portfolio.new_security(ticker, name or ticker))
        doc["securities"] = securities
        self._write_securities_doc(doc)
        return ok(ticker=ticker.upper().strip())

    @guarded
    @locked
    def remove_security(self, ticker):
        """Remove an idea that was never bought — a mistyped ticker, a
        candidate no longer worth tracking.

        Anything with position history is refused outright: a purchase, an
        exit, an entry snapshot or an override is recorded history, and this
        journal never deletes history — that is what makes it a journal.
        Ideas carry no decisions, so removing one loses nothing the learning
        loop needs; whatever notes or values it carried are named in the
        confirmation the UI shows first."""
        doc = self._securities_doc()
        securities = doc.get("securities", [])
        s = self._find(securities, ticker)
        if s.get("bucket") != "ideas" or s.get("position") or s.get("exit") \
                or s.get("entry_snapshot") or s.get("override"):
            return err(f"{s['ticker']} has recorded position history — a "
                       "purchase, exit or entry snapshot — and the journal "
                       "never deletes history. Only ideas that were never "
                       "bought can be removed.")
        securities.remove(s)
        doc["securities"] = securities
        self._write_securities_doc(doc)
        return ok(removed=s["ticker"])

    @guarded
    @locked
    def save_metrics(self, ticker, metrics, price):
        """Blank fields delete the metric rather than storing a zero.

        A zero would render as a confident failure; absent renders as grey.
        Only fields the dialog offered are touched, so a value entered under
        a profile that has since been removed is not silently dropped.
        """
        known = set(self._bank_meta())
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)
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
        self._write_securities_doc(doc)
        return ok()

    @guarded
    @locked
    def save_falsifier(self, ticker, text):
        doc = self._securities_doc()
        self._find(doc.get("securities", []), ticker)["falsifier"] = (text or "").strip()
        self._write_securities_doc(doc)
        return ok()

    @guarded
    @locked
    def add_note(self, ticker, text):
        doc = self._securities_doc()
        portfolio.add_note(self._find(doc.get("securities", []), ticker), text)
        self._write_securities_doc(doc)
        return ok()

    def _profile_values(self, s, prof):
        """Merged values (hand-entered over computed) for one security under
        one profile — the values the lens actually sees."""
        used = {}
        for tier in prof.get("tiers", []):
            for e in tier.get("entries", []):
                ids = [e.get("metric")]
                for block in (e.get("sell"), e.get("flag")):
                    if isinstance(block, dict) and block.get("measured_on"):
                        ids.append(str(block["measured_on"]))
                for mid in ids:
                    if mid:
                        used.setdefault(mid, [])
        for mid in (s.get("metrics") or {}):
            used.setdefault(mid, [])
        computed, price, _, tickers = self._computed_layer(s, used)
        values, sources = dataview.merged_values(s, computed)
        param_ids = dataview.parameterized_entry_ids()
        pv, psrc = self._values_for_profile(s, values, sources, prof,
                                            param_ids, tickers)
        return pv, psrc, price

    @guarded
    def preview_purchase(self, ticker, profile_file):
        """What the chosen lens would say right now, before anything is
        committed."""
        _, resolved, _, _ = self._resolved_profiles()
        prof = resolved.get(profile_file)
        if prof is None:
            return err(f"{profile_file} is not a profile on disk.")
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)
        values, _, _ = self._profile_values(s, prof)
        result = evaluate_buy(values, prof)
        return ok(verdict=result["verdict"], causes=result["causes"],
                  profile_name=prof["name"], profile_version=prof["version"])

    @guarded
    @locked
    def open_position(self, ticker, shares, cost, opened,
                      override_reason="", profile_file=None,
                      previewed_verdict=None):
        _, resolved, _, _ = self._resolved_profiles()
        prof = resolved.get(profile_file)
        if prof is None:
            return err("Choose a profile to buy under; it names the rules "
                       "this purchase is recorded against.")
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)
        values, sources, price = self._profile_values(s, prof)
        portfolio.open_position(s, prof, prof["version"],
                                float(shares), float(cost), opened or None,
                                override_reason, values=values,
                                value_sources=sources, price_seen=price)
        self._write_securities_doc(doc)
        verdict = ((s.get("entry_snapshot") or {}).get("result") or {}) \
            .get("verdict")
        return ok(override=bool(s.get("override")), verdict=verdict,
                  verdict_changed=bool(previewed_verdict
                                       and verdict
                                       and previewed_verdict != verdict))

    @guarded
    @locked
    def close_position(self, ticker, reason, price, exited, lens_file=None):
        _, resolved, _, _ = self._resolved_profiles()
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)

        snap = s.get("entry_snapshot") or {}
        own_ref = (snap.get("profile") or None) \
            if "ruleset_version" not in snap else None
        prof, governing, missing_ref = None, False, None
        if own_ref and own_ref.get("file") in resolved:
            prof, governing = resolved[own_ref["file"]], True
        elif own_ref:
            # The governing profile exists in the record but not on disk.
            # Record that, rather than judging under a lens that never
            # governed this position.
            missing_ref = own_ref
        elif lens_file and lens_file in resolved:
            prof = resolved[lens_file]

        values = self._profile_values(s, prof)[0] if prof else None
        portfolio.close_position(s, prof, prof["version"] if prof else None,
                                 governing, reason, float(price), exited or None,
                                 missing_profile_ref=missing_ref,
                                 values=values)
        self._write_securities_doc(doc)
        ex = s["exit"]
        return ok(rule_triggered=ex["rule_triggered"],
                  signal=ex["signal_at_exit"],
                  profile_name=(ex["profile"] or {}).get("name"),
                  governing=ex["governing"])

    # -- data acquisition ------------------------------------------------
    def _tie_cik(self, ticker, cik):
        """Record the resolved company on the security, from the fetch thread
        itself, under the journal lock. A recorded CIK is what makes the
        reused-symbol protection work on the NEXT fetch, so it must not
        depend on a UI poll surviving to completion."""
        with self._doc_lock:
            doc = self._securities_doc()
            try:
                s = self._find(doc.get("securities", []), ticker)
            except ValueError:
                return
            if s.get("cik") != int(cik):
                s["cik"] = int(cik)
                self._write_securities_doc(doc)
        dataview.invalidate(int(cik))

    @guarded
    def fetch_security(self, ticker):
        """Start a background fetch of filings and prices for one security.
        Explicit user action only — nothing here runs on a schedule."""
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)
        settings = store.load("settings.json")
        r = fetch.start_fetch(s["ticker"], settings, known_cik=s.get("cik"),
                              on_resolved=self._tie_cik)
        if r.get("error"):
            return err(r["error"])
        return ok(started=True)

    @guarded
    @locked
    def get_fetch_status(self, ticker):
        """Progress of a running fetch; on completion, tie the resolved CIK
        to the security (once — a recorded CIK is never silently re-tied)."""
        st = fetch.status_of(ticker)
        if st and not st.get("running") and st.get("report"):
            report = st["report"]
            cik = report.get("cik")
            if cik and not report.get("conflict"):
                doc = self._securities_doc()
                try:
                    s = self._find(doc.get("securities", []), ticker)
                except ValueError:
                    s = None
                if s is not None and s.get("cik") != cik:
                    s["cik"] = int(cik)
                    self._write_securities_doc(doc)
                dataview.invalidate(int(cik))
        return ok(status=st)

    @guarded
    def get_coverage(self, ticker):
        """Per bank entry: computed or absent-with-reason, plus the
        public-float cross-check — the data page for one security."""
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)
        cik = s.get("cik")
        if not cik:
            return ok(coverage=None,
                      note="Nothing fetched yet for this security. Fetch "
                           "filings & prices first.")
        order, resolved, _, _ = self._resolved_profiles()
        used = self._used_metric_ids(order, resolved, [s])
        cov = dataview.coverage(cik, self._tickers_of(s), list(used),
                                self._bank_meta())
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
        goes in and never comes back out to the UI; saving a fresh one also
        clears the rotate notice, because a rotated key answers it."""
        key = (key or "").strip()
        if not key:
            return err("Paste the key first. To remove the stored key, use "
                       "Remove key.")
        try:
            secrets.set_secret("tiingo_api_token", key)
        except secrets.SecretsError as e:
            return err(str(e))
        secrets.local_set(secrets.ROTATE_FLAG, None)
        return ok(storage=secrets.storage())

    @guarded
    def remove_api_key(self):
        try:
            had = secrets.delete_secret("tiingo_api_token")
        except secrets.SecretsError as e:
            return err(str(e))
        secrets.local_set(secrets.ROTATE_FLAG, None)
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
        return ok(valid=bool(v.get("ok")), message=str(v.get("message") or ""))

    # -- expected value --------------------------------------------------
    @guarded
    @locked
    def compute_ev(self, ticker, method, inputs):
        result = compute_ev(method, inputs or {})
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)
        s["ev"] = {"method": method, "inputs": inputs,
                   "computed": date.today().isoformat()}
        self._write_securities_doc(doc)
        return ok(result=result)

    @guarded
    def recompute_ev(self, ticker):
        s = self._find(self._securities_doc().get("securities", []), ticker)
        ev = s.get("ev")
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
            webview.OPEN_DIALOG, file_types=("Ledger backup (*.json)",)) if self.window else None
        if not paths:
            return ok(cancelled=True)
        summary = backup.import_bundle(paths[0])
        return ok(summary=summary)

    @guarded
    @locked
    def load_sample(self):
        sample = json.loads((TEMPLATE_DIR / "sample.json").read_text(encoding="utf-8"))
        doc = self._securities_doc()
        doc["securities"] = sample["securities"]
        self._write_securities_doc(doc)
        return ok(n=len(sample["securities"]))

    @guarded
    @locked
    def clear_all(self):
        doc = self._securities_doc()
        doc["securities"] = []
        self._write_securities_doc(doc)
        return ok()

    @guarded
    def open_data_dir(self):
        return ok(path=str(store.data_dir()))


def main():
    parser = argparse.ArgumentParser(description="Ledger, a portfolio journal")
    parser.add_argument("--reset", action="store_true",
                        help="delete local data and start from the template")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.reset:
        d = store.ensure_data()
        for name in store.FILES:
            (d / name).unlink(missing_ok=True)
        # The migration report describes data that no longer exists after a
        # reset; backups (pre-migration, pre-import, rules.legacy) stay.
        (d / migrate.REPORT_FILE).unlink(missing_ok=True)
        shutil.rmtree(d / "profiles", ignore_errors=True)
        print(f"Cleared {d}")

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
