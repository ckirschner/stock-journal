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
import traceback
from datetime import date
from pathlib import Path

import webview

from engine import backup, migrate, portfolio, profile_history, profiles, store
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


class Api:
    def __init__(self):
        self.window = None

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

    # -- read ------------------------------------------------------------
    @guarded
    def get_state(self):
        migration = migrate.ensure_migrated()
        order, resolved, cfg_errors, hist = self._resolved_profiles()

        doc = self._securities_doc()
        securities = doc.get("securities", [])
        for s in securities:
            s["_eval"] = {}
            for file, prof in resolved.items():
                view = {"buy": evaluate_buy(s.get("metrics") or {}, prof)}
                if s.get("bucket") == "holdings":
                    view["position"] = evaluate_position(s, prof)
                s["_eval"][file] = view
            s["_own"] = self._own_view(s, resolved)
            s["_realised"] = portfolio._realised(s)
            s["_since_exit"] = portfolio._since_exit(s)

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
            override_scorecard=portfolio.override_scorecard(securities),
            exit_scorecard=portfolio.exit_scorecard(securities),
            data_dir=str(store.data_dir()),
        )

    def _own_view(self, s, resolved):
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
        # The sell rules that run are the profile's CURRENT content; the
        # snapshot records which version the purchase was made under. Both
        # versions travel so the UI can label them honestly.
        return {"legacy": False,
                "profile": {**ref, "version": prof["version"]},
                "bought_version": ref.get("version"),
                "state": evaluate_position(s, prof)}

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
    def save_falsifier(self, ticker, text):
        doc = self._securities_doc()
        self._find(doc.get("securities", []), ticker)["falsifier"] = (text or "").strip()
        self._write_securities_doc(doc)
        return ok()

    @guarded
    def add_note(self, ticker, text):
        doc = self._securities_doc()
        portfolio.add_note(self._find(doc.get("securities", []), ticker), text)
        self._write_securities_doc(doc)
        return ok()

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
        result = evaluate_buy(s.get("metrics") or {}, prof)
        return ok(verdict=result["verdict"], causes=result["causes"],
                  profile_name=prof["name"], profile_version=prof["version"])

    @guarded
    def open_position(self, ticker, shares, cost, opened,
                      override_reason="", profile_file=None):
        _, resolved, _, _ = self._resolved_profiles()
        prof = resolved.get(profile_file)
        if prof is None:
            return err("Choose a profile to buy under; it names the rules "
                       "this purchase is recorded against.")
        doc = self._securities_doc()
        s = self._find(doc.get("securities", []), ticker)
        portfolio.open_position(s, prof, prof["version"],
                                float(shares), float(cost), opened or None,
                                override_reason)
        self._write_securities_doc(doc)
        return ok(override=bool(s.get("override")))

    @guarded
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

        portfolio.close_position(s, prof, prof["version"] if prof else None,
                                 governing, reason, float(price), exited or None,
                                 missing_profile_ref=missing_ref)
        self._write_securities_doc(doc)
        ex = s["exit"]
        return ok(rule_triggered=ex["rule_triggered"],
                  signal=ex["signal_at_exit"],
                  profile_name=(ex["profile"] or {}).get("name"),
                  governing=ex["governing"])

    # -- expected value --------------------------------------------------
    @guarded
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
    def import_data(self):
        paths = self.window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Ledger backup (*.json)",)) if self.window else None
        if not paths:
            return ok(cancelled=True)
        summary = backup.import_bundle(paths[0])
        return ok(summary=summary)

    @guarded
    def load_sample(self):
        sample = json.loads((TEMPLATE_DIR / "sample.json").read_text(encoding="utf-8"))
        doc = self._securities_doc()
        doc["securities"] = sample["securities"]
        self._write_securities_doc(doc)
        return ok(n=len(sample["securities"]))

    @guarded
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
