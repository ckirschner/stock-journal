"""The concurrent-fetch failure class: the library's shared HTTP state dies
when reconfigured under in-flight requests, so configuration is idempotent
and fetches are serialized. Both properties are pinned here — this shipped as
three of four first fetches failing with a NoneType unpack out of the
library's transport."""

import threading
import time

from engine import fetch, gateway


class TestConfigureIdempotence:
    def test_unchanged_configure_never_touches_the_library(self, tmp_path,
                                                           monkeypatch):
        calls = []

        class FakeEdgar:
            @staticmethod
            def set_identity(identity):
                calls.append(identity)

        import sys
        monkeypatch.setitem(sys.modules, "edgar", FakeEdgar())
        monkeypatch.setattr(gateway, "_configured", False)
        monkeypatch.setattr(gateway, "_configured_with", None)
        monkeypatch.setattr(gateway, "_configure_lock", None)

        ident = "Jane Doe jane@example.com"
        gateway.configure(str(tmp_path / "cache"), ident)
        gateway.configure(str(tmp_path / "cache"), ident)
        gateway.configure(str(tmp_path / "cache"), ident)
        # set_identity closes the library's shared HTTP clients; repeating it
        # under a running fetch kills that fetch's requests mid-air.
        assert calls == [ident]

        gateway.configure(str(tmp_path / "cache"), "New Name new@example.com")
        assert len(calls) == 2


class TestFetchGate:
    def test_fetches_run_one_at_a_time(self, monkeypatch):
        running = []
        overlap = []

        def fake_fetch_ticker(ticker, known_cik=None,
                              progress=None, on_resolved=None):
            running.append(ticker)
            if len(running) > 1:
                overlap.append(tuple(running))
            time.sleep(0.05)
            running.remove(ticker)
            return {"ticker": ticker, "errors": []}

        from engine import secrets
        secrets.local_set("sec_identity", "Jane Doe jane@example.com")
        monkeypatch.setattr(fetch, "fetch_ticker", fake_fetch_ticker)
        for t in ("AAA", "BBB", "CCC"):
            r = fetch.start_fetch(t)
            assert r.get("started")
        deadline = time.time() + 5
        while time.time() < deadline:
            done = [fetch.status_of(t) for t in ("AAA", "BBB", "CCC")]
            if all(s and not s.get("running") for s in done):
                break
            time.sleep(0.02)
        assert overlap == []          # never two fetches inside at once
        for t in ("AAA", "BBB", "CCC"):
            assert fetch.status_of(t).get("stage") == "done"


class TestADeadSymbolDoesNotTakeItsSiblingsPricesWithIt:
    """A company with two listed classes, one of which has been delisted.

    Marking the dead series terminal is right — a novice must never see a
    dead series rendered as a current price, and the fetch error already
    promised the mark would be written. What must not happen is the mark
    costing the fetch: the price document is open across the whole symbol
    loop, and loading a second copy to mark one symbol writes a file without
    the rows just merged for the others. The good class's prices would be
    thrown away, silently, on every fetch, for as long as the dead symbol
    stayed in the map.

    Driven through `fetch._fetch_company` — the function that actually holds
    the document open — rather than through a copy of its loop written here.
    A test that re-implements the code path it is guarding passes whatever
    the real one does, which is the failure mode this whole exercise is
    about.
    """

    def _run(self, monkeypatch, tmp_path, cik=900123, fetcher=None):
        from engine import (fetch, gateway, price_store, secrets, store,
                            tickermap, tiingo)

        monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
        monkeypatch.setattr(gateway, "configure", lambda *a, **kw: None)
        monkeypatch.setattr(gateway, "company_info",
                            lambda c: {"name": "Alive & Dead Co",
                                       "recent_forms": ["10-K"]})
        monkeypatch.setattr(gateway, "list_filings", lambda c: [])
        monkeypatch.setattr(secrets, "get_secret", lambda k: "token")
        monkeypatch.setattr(tickermap, "tickers_for",
                            lambda tmap, c: ["ALIV", "ADED"])

        def fake_fetch(sym, token):
            if sym == "ADED":
                raise tiingo.PriceSourceError(
                    "Tiingo does not know this symbol.",
                    kind="unknown-symbol")
            return {"rows": [["2026-08-07", 12.0, 100]], "events": []}

        monkeypatch.setattr(tiingo, "fetch_daily", fetcher or fake_fetch)

        # Both classes already have history. ADED last traded in 2024.
        doc = price_store.load(cik)
        price_store.merge_series(doc, "ALIV", "tiingo",
                                 [["2026-01-02", 10.0, 100]], [])
        price_store.merge_series(doc, "ADED", "tiingo",
                                 [["2024-03-11", 4.0, 100]], [])
        price_store.save(cik, doc)

        errors, report = [], {}
        fetch._fetch_company("ALIV", "Tester test@example.com", cik,
                             object(), cik, report, errors,
                             lambda **kw: None)
        return price_store.load(cik), errors, report

    def test_the_terminal_mark_keeps_the_rows_fetched_before_it(
            self, monkeypatch, tmp_path):
        from engine import price_store
        saved, errors, report = self._run(monkeypatch, tmp_path)

        # the live class kept the close fetched before the dead one failed…
        assert price_store.latest_close(saved, "ALIV") == ("2026-08-07", 12.0)
        # …the dead one is marked, which is the point of the branch…
        assert price_store.terminal_of(saved, "ADED")["reason"], errors
        # …and its own history is untouched, never deleted.
        assert price_store.latest_close(saved, "ADED") == ("2024-03-11", 4.0)
        assert report["prices_fetched"] == ["ALIV"]

    def test_only_an_unknown_symbol_marks_a_series_dead(self, monkeypatch,
                                                        tmp_path):
        """A rate limit and a rejected key raise the same class of error. The
        mark is written once and nothing takes it back, so marking a live
        series dead on a throttle is worse than never marking one: the price
        keeps rendering, now labelled as ended, for good."""
        from engine import price_store, tiingo

        def throttled(sym, token):
            raise tiingo.PriceSourceError("Tiingo's rate limit was hit.")

        saved, errors, _report = self._run(monkeypatch, tmp_path, cik=900124,
                                           fetcher=throttled)
        assert errors, "a throttled fetch is still reported"
        for sym in ("ALIV", "ADED"):
            assert price_store.terminal_of(saved, sym) is None, \
                f"{sym} was marked dead by a rate limit"


class TestASymbolThePriceSourceHasNeverQuoted:
    """The SEC maps every security a company registers to its CIK. A price
    source quotes its common stock.

    So a fetch of Synchrony asked for SYF, SYF-PA and SYF-PB; the two
    preferred series came back unknown, went into "problems from fetching",
    and stayed there — permanently, on a company where nothing was wrong,
    re-requested on every fetch for as long as the symbols stayed in the map.
    Bank of America maps seventeen symbols and would show sixteen. A red panel
    that is always right and never actionable teaches the reader to skip the
    one place real problems appear.

    It is not a terminal series. Terminal says a series ENDED and the last
    close has stopped being a price; there were never any closes here, and
    marking one would put a dead-series label on a symbol that has no rows to
    label. It is a boundary of the source, recorded once — the shape stage 3
    already uses for a pre-XBRL filing, which is counted apart from real
    extraction failures for exactly this reason.

    The instrument-classification work cannot answer this one, which is why
    the fix is here. Synchrony's cover spells its preferreds SYFPrA and
    SYFPrB and the SEC map spells them SYF-PA and SYF-PB; the two do not
    resolve to each other, and making them resolve would mean reasoning from
    a symbol-suffix convention — refused at engine/instruments.py, because a
    convention is a convention and CLSKW is a warrant while BRK-B is not. The
    price source's own 404 is the evidence, and it is already machine-readable.
    """

    def _run(self, monkeypatch, tmp_path, cik, mapped, asked, ticker="SYF",
             prepare=None):
        from engine import (fetch, gateway, price_store, secrets, store,
                            tickermap, tiingo)

        monkeypatch.setattr(store, "data_dir", lambda: tmp_path)
        monkeypatch.setattr(gateway, "configure", lambda *a, **kw: None)
        # No `recent_forms`: an empty filing index with forms on record is the
        # foreign-private-issuer case and reports its own error, which has
        # nothing to do with prices.
        monkeypatch.setattr(gateway, "company_info",
                            lambda c: {"name": "Synthetic Financial",
                                       "recent_forms": []})
        monkeypatch.setattr(gateway, "list_filings", lambda c: [])
        monkeypatch.setattr(secrets, "get_secret", lambda k: "token")
        monkeypatch.setattr(tickermap, "tickers_for", lambda tmap, c: mapped)

        def fake_fetch(sym, token):
            asked.append(sym)
            if sym != ticker:
                raise tiingo.PriceSourceError(
                    "Tiingo does not know this symbol.",
                    kind="unknown-symbol")
            return {"rows": [["2026-08-07", 61.0, 100]], "events": []}

        monkeypatch.setattr(tiingo, "fetch_daily", fake_fetch)
        # After the data directory is redirected, never before: a document
        # written first lands in the real one and the fetch reads an empty
        # store, which is a test that passes for no reason.
        if prepare is not None:
            prepare(price_store, cik)
        errors, report = [], {}
        fetch._fetch_company(ticker, "Tester test@example.com", cik,
                             object(), cik, report, errors,
                             lambda **kw: None)
        return price_store.load(cik), errors, report

    def test_it_is_not_reported_as_a_problem(self, monkeypatch, tmp_path):
        asked = []
        saved, errors, report = self._run(
            monkeypatch, tmp_path, 900200, ["SYF", "SYF-PA", "SYF-PB"], asked)
        assert asked == ["SYF", "SYF-PA", "SYF-PB"]
        assert report["prices_fetched"] == ["SYF"]
        assert errors == [], errors
        assert len(report["prices_unquoted"]) == 2

    def test_it_is_recorded_so_it_is_never_asked_again(self, monkeypatch,
                                                       tmp_path):
        from engine import price_store
        asked = []
        self._run(monkeypatch, tmp_path, 900201,
                  ["SYF", "SYF-PA", "SYF-PB"], asked)
        assert asked == ["SYF", "SYF-PA", "SYF-PB"]

        asked.clear()
        saved, errors, report = self._run(
            monkeypatch, tmp_path, 900201, ["SYF", "SYF-PA", "SYF-PB"], asked)
        assert asked == ["SYF"], "a symbol already known unquoted was re-asked"
        assert errors == []
        assert report["prices_fetched"] == ["SYF"]
        assert len(report["prices_unquoted"]) == 2
        assert price_store.unquoted_of(saved, "SYF-PA", "tiingo")["source"] \
            == "tiingo"

    def test_it_is_not_a_terminal_series_and_makes_no_empty_one(
            self, monkeypatch, tmp_path):
        """Two things it must not become. A terminal mark says a series
        ended, and there was never a series to end. And an empty entry under
        `series` would surface in `other_series`, so the sentence explaining
        why a holding has no close would start listing symbols that have
        never had one."""
        from engine import price_store
        saved, _e, _r = self._run(monkeypatch, tmp_path, 900202,
                                  ["SYF", "SYF-PA"], [])
        assert price_store.terminal_of(saved, "SYF-PA") is None
        assert "SYF-PA" not in (saved.get("series") or {})
        assert price_store.other_series(saved, "SYF") == []

    def test_the_journals_own_symbol_is_always_retried(self, monkeypatch,
                                                       tmp_path):
        """The instrument the user holds is priced from this symbol directly.
        A source that has started carrying it must be able to say so, and the
        tool never refuses to go and look for the thing in front of you."""
        from engine import price_store

        def prepare(ps, cik):
            doc = ps.load(cik)
            ps.mark_unquoted(doc, "SYF", "tiingo", "not carried")
            ps.save(cik, doc)

        asked = []
        saved, errors, report = self._run(monkeypatch, tmp_path, 900203,
                                          ["SYF", "SYF-PA"], asked,
                                          prepare=prepare)
        assert "SYF" in asked
        assert report["prices_fetched"] == ["SYF"]
        assert price_store.latest_close(saved, "SYF") == ("2026-08-07", 61.0)

    def test_a_symbol_that_once_had_rows_is_still_marked_terminal(
            self, monkeypatch, tmp_path):
        """The two facts stay apart. A series with closes that the source
        stops listing HAS ended, and the mark is what keeps its last close
        from rendering as a live quote — that branch must not be swallowed by
        the new one."""
        from engine import price_store

        def prepare(ps, cik):
            doc = ps.load(cik)
            ps.merge_series(doc, "SYF-PA", "tiingo",
                            [["2024-03-11", 22.0, 100]], [])
            ps.save(cik, doc)

        saved, errors, report = self._run(monkeypatch, tmp_path, 900204,
                                          ["SYF", "SYF-PA"], [],
                                          prepare=prepare)
        assert price_store.terminal_of(saved, "SYF-PA")["reason"]
        assert price_store.unquoted_of(saved, "SYF-PA", "tiingo") is None
        assert errors, "a series that ended is still worth reporting"
