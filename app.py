"""Ledger. A portfolio journal that checks holdings against rules you wrote.

    python app.py            run the app
    python app.py --reset    start again from the template

The app never places a trade and has no broker credentials. It reads what you
tell it, checks it against rules you wrote, and shows you the answer.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date
from pathlib import Path

import webview

from engine import backup, portfolio, store
from engine.evaluate import evaluate, failure_labels
from engine.expected_value import EVError
from engine.expected_value import compute as compute_ev
from engine.rules import RuleBook
from engine.schema import DEFAULT_SCHEMA, EV_METHODS, EXIT_REASONS

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
        except EVError as e:
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
    def _rulebook(self) -> RuleBook:
        return RuleBook(store.load("rules.json"))

    def _securities(self) -> list[dict]:
        return store.load("securities.json").get("securities", [])

    def _write_securities(self, securities):
        store.save("securities.json", {"securities": securities})

    def _find(self, securities, ticker):
        for s in securities:
            if s["ticker"] == ticker:
                return s
        raise ValueError(f"{ticker} is not in the journal.")

    # -- read ------------------------------------------------------------
    @guarded
    def get_state(self):
        rb = self._rulebook()
        rules = rb.current
        securities = self._securities()

        for s in securities:
            s["_now"] = evaluate(s, rules, "now")
            s["_now"]["failure_labels"] = failure_labels(s["_now"])
            snap = s.get("entry_snapshot")
            s["_entry"] = snap.get("result") if snap else None
            s["_realised"] = portfolio._realised(s)
            s["_since_exit"] = portfolio._since_exit(s)

        return ok(
            schema=DEFAULT_SCHEMA,
            rules=rules,
            rule_history=[{"version": v["version"], "created": v["created"],
                           "reason": v["reason"]} for v in reversed(rb.versions)],
            settings=store.load("settings.json"),
            securities=securities,
            ev_methods=EV_METHODS,
            exit_reasons=EXIT_REASONS,
            override_scorecard=portfolio.override_scorecard(securities),
            exit_scorecard=portfolio.exit_scorecard(securities),
            data_dir=str(store.data_dir()),
        )

    # -- rules -----------------------------------------------------------
    @guarded
    def amend_rules(self, changes, reason):
        rb = self._rulebook()
        version = rb.amend(changes or {}, reason)
        store.save("rules.json", rb.to_dict())
        return ok(version=version["version"],
                  changes=rb.diff(version["version"] - 1, version["version"]))

    # -- securities ------------------------------------------------------
    @guarded
    def add_security(self, ticker, name):
        if not (ticker or "").strip():
            return err("A ticker is required.")
        securities = self._securities()
        if any(s["ticker"] == ticker.upper().strip() for s in securities):
            return err(f"{ticker.upper()} is already in the journal.")
        securities.append(portfolio.new_security(ticker, name or ticker))
        self._write_securities(securities)
        return ok(ticker=ticker.upper().strip())

    @guarded
    def save_metrics(self, ticker, metrics, price):
        """Blank fields delete the metric rather than storing a zero.

        A zero would render as a confident failure; absent renders as grey.
        """
        securities = self._securities()
        s = self._find(securities, ticker)
        cleaned = {}
        for k, v in (metrics or {}).items():
            if v in (None, "", "—"):
                continue
            try:
                cleaned[k] = float(v)
            except (TypeError, ValueError):
                return err(f"{k} must be a number or left blank.")
        s["metrics"] = cleaned
        s["price"] = float(price) if price not in (None, "") else None
        self._write_securities(securities)
        return ok()

    @guarded
    def save_falsifier(self, ticker, text):
        securities = self._securities()
        self._find(securities, ticker)["falsifier"] = (text or "").strip()
        self._write_securities(securities)
        return ok()

    @guarded
    def add_note(self, ticker, text):
        securities = self._securities()
        portfolio.add_note(self._find(securities, ticker), text)
        self._write_securities(securities)
        return ok()

    @guarded
    def preview_purchase(self, ticker):
        """What the tool would say right now, before anything is committed."""
        securities = self._securities()
        s = self._find(securities, ticker)
        result = evaluate(s, self._rulebook().current, "now")
        return ok(verdict=result["verdict"], tone=result["tone"],
                  failures=failure_labels(result))

    @guarded
    def open_position(self, ticker, shares, cost, opened, override_reason=""):
        securities = self._securities()
        s = self._find(securities, ticker)
        portfolio.open_position(s, self._rulebook().current,
                                float(shares), float(cost), opened or None,
                                override_reason)
        self._write_securities(securities)
        return ok(override=bool(s.get("override")))

    @guarded
    def close_position(self, ticker, reason, price, exited):
        securities = self._securities()
        s = self._find(securities, ticker)
        portfolio.close_position(s, self._rulebook().current, reason,
                                 float(price), exited or None)
        self._write_securities(securities)
        return ok(rule_triggered=s["exit"]["rule_triggered"])

    # -- expected value --------------------------------------------------
    @guarded
    def compute_ev(self, ticker, method, inputs):
        result = compute_ev(method, inputs or {})
        securities = self._securities()
        s = self._find(securities, ticker)
        s["ev"] = {"method": method, "inputs": inputs,
                   "computed": date.today().isoformat()}
        self._write_securities(securities)
        return ok(result=result)

    @guarded
    def recompute_ev(self, ticker):
        s = self._find(self._securities(), ticker)
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
        self._write_securities(sample["securities"])
        return ok(n=len(sample["securities"]))

    @guarded
    def clear_all(self):
        self._write_securities([])
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
