"""The shipped sample journal.

The file is built by tools/make_sample.py, which drives the real API and
asserts each story before it writes. This pins the other end: that the file
in the repository still tells those stories when loaded by the app, against
whatever the strategy and the host do today. A sample whose notes describe
verdicts it no longer produces teaches the wrong thing to the one person
who has no way to notice.
"""

import json

import pytest

from app import Api

# What each invented company exists to demonstrate. Written here rather than
# read out of the file, so a sample rebuilt around different stories has to
# be a deliberate change in two places.
STORIES = {
    "HARW": ("hold", "hold"),
    "CALDR": ("one-reading-past", "hold"),
    "BRENT": ("safety-gone", "close"),
    "MERIDN": ("time-is-up", "close"),
    "OKELL": ("too-big", "reduce"),
    "THRAP": ("cannot-watch", "unknown"),
    "PELHAM": ("buy", "commit"),
    "VANTR": ("not-cheap-enough", "hold"),
    "STANM": ("cannot-screen", "unknown"),
}


@pytest.fixture
def loaded():
    api = Api()
    result = api.load_sample()
    assert result["ok"], result.get("error")
    return api, result


def decisions(api):
    journal, record, chain, _ = api._open()
    return {s["ticker"]: api._decide(s, journal["securities"], journal,
                                     record, chain)
            for s in journal["securities"]}


class TestTheSample:
    def test_it_lands_in_its_own_graham_journal(self, loaded):
        api, result = loaded
        assert result["n"] == 10
        journal, record, *_ = api._open()
        assert record["id"] == "graham"
        assert journal["name"] == "Sample — Graham"
        # The one answer Graham asks for, so the size rules can run at all.
        assert journal["inputs"]["free-cash"] == 62_000.0

    def test_every_security_still_tells_its_story(self, loaded):
        api, _ = loaded
        got = decisions(api)
        for ticker, (state, render) in STORIES.items():
            assert got[ticker]["state"]["id"] == state, \
                f'{ticker}: {got[ticker]["reason"]["summary"]}'
            assert got[ticker]["render"] == render, ticker
            assert got[ticker]["produced_by"] == "strategy", ticker

    def test_the_verdicts_carry_their_figures(self, loaded):
        api, _ = loaded
        for ticker, decision in decisions(api).items():
            if ticker == "LOWFD":
                continue
            evidence = decision["reason"]["evidence"]
            assert evidence, ticker
            assert decision["reason"]["rule"], ticker

    def test_a_verdict_gone_against_and_a_verdict_that_never_existed(
            self, loaded):
        """Two different records, not two flavours of one. OKELL was bought
        in the face of a real verdict — a decision, and one the override
        scorecard is entitled to judge. THRAP had no figures on record at
        all, so nothing could be reconstructed for the day it is dated, and
        there was no signal to obey or defy. Counted as an override it would
        put a decision nobody made into the one figure that measures the
        user's judgement.
        """
        api, _ = loaded
        journal, *_ = api._open()
        by_ticker = {s["ticker"]: s for s in journal["securities"]}
        buys = {t: [l for l in by_ticker[t]["lots"] if l["kind"] == "buy"]
                for t in ("OKELL", "THRAP", "HARW")}
        assert [l["override"]["kind"] for l in buys["OKELL"]] == ["against"]
        assert [l["unreconstructed"] for l in buys["OKELL"]] == [None]
        assert [l["override"] for l in buys["THRAP"]] == [None]
        assert all(l["unreconstructed"]["why"] for l in buys["THRAP"])
        assert [l["override"] for l in buys["HARW"]] == [None]
        assert [l["unreconstructed"] for l in buys["HARW"]] == [None]

    def test_a_memory_is_marked_as_one_and_is_never_the_thesis(self, loaded):
        """THRAP carries what its buyer remembers thinking. It is written
        after the outcome is known, so it can be graded against nothing, and
        the record keeps it under its own name with the day it was actually
        written on it."""
        api, _ = loaded
        journal, *_ = api._open()
        thrap = next(s for s in journal["securities"]
                     if s["ticker"] == "THRAP")
        [lot] = [l for l in thrap["lots"] if l["kind"] == "buy"]
        snap = lot["snapshot"]
        assert snap["recollection"]["text"].startswith("No figures on record")
        assert snap["recollection"]["written"]
        assert snap["thesis"] is None or \
            snap["thesis"]["thesis"] != snap["recollection"]["text"]

    def test_the_frozen_snapshot_is_the_verdict_of_its_own_day(self, loaded):
        """OKELL was bought against a real verdict and has since more than
        doubled. What is frozen on that lot has to be what was on screen in
        November 2024, not what the strategy says about it now."""
        api, _ = loaded
        journal, *_ = api._open()
        okell = next(s for s in journal["securities"]
                     if s["ticker"] == "OKELL")
        [lot] = [l for l in okell["lots"] if l["kind"] == "buy"]
        frozen = lot["snapshot"]["decision"]
        assert frozen["state"]["id"] == "not-cheap-enough"
        assert lot["date"] == "2024-11-19"
        # And today's verdict about the same security is a different one.
        assert decisions(api)["OKELL"]["state"]["id"] == "too-big"

    def test_a_closed_holding_is_still_being_watched(self, loaded):
        """Exits keep getting priced. If a rule keeps leaving money on the
        table that is the finding, and it is only available because the
        ticker stays in the journal after the sale."""
        from engine import portfolio
        api, _ = loaded
        journal, *_ = api._open()
        lowfd = next(s for s in journal["securities"]
                     if s["ticker"] == "LOWFD")
        [cycle] = portfolio.cycles(lowfd)
        assert not cycle["open"]
        assert portfolio.cycle_return(lowfd, cycle,
                                      lowfd["price"])["value"] \
            == pytest.approx(76.8, abs=0.1)     # 11.20 -> 19.80
        [sale] = portfolio.lots(lowfd, "sell")
        since = portfolio.since_sale(lowfd, sale, lowfd["price"])
        assert since["until"] == "today"          # never bought back
        assert since["pct"] == pytest.approx(24.24, abs=0.01)

    def test_it_never_touches_a_journal_that_is_already_here(self, loaded):
        api, _ = loaded
        before = len(api.load_sample.__self__._strategies()[0])
        assert before                                  # strategies loaded
        again = api.load_sample()
        assert again["ok"]
        from engine import journals
        assert len(journals.list_journals()) == 2

    def test_nothing_in_it_is_presented_as_a_real_company(self):
        """Demonstration content uses invented companies. A sample that
        named a real one would read as a recommendation however it was
        labelled."""
        raw = json.loads(Api.SAMPLE.read_text(encoding="utf-8"))
        tickers = {s["ticker"] for s in raw["securities"]}
        assert tickers == set(STORIES) | {"LOWFD"}
        for s in raw["securities"]:
            assert s.get("cik") is None, s["ticker"]
