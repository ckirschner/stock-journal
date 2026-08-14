"""The shipped sample journals.

Each file is built by a script in tools/, which drives the real API and
asserts each story before it writes. This pins the other end: that the files
in the repository still tell those stories when loaded by the app, against
whatever the strategies and the host do today. A sample whose notes describe
verdicts it no longer produces teaches the wrong thing to the one person who
has no way to notice.

There is one sample per strategy, and the pairing is itself part of what they
demonstrate. A journal has exactly one strategy and it does not change, so
two strategies means two journals — and the quickest way to understand what
committing to one costs is to see the same kind of company judged by both.
"""

import json

import pytest

from app import Api
from engine import journals

# What each invented company exists to demonstrate. Written here rather than
# read out of the files, so a sample rebuilt around different stories has to
# be a deliberate change in two places.
GRAHAM = {
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

BUFFETT = {
    "NORBRY": ("hold", "hold"),
    "CRESSET": ("room-for-more", "commit"),
    "HALLAM": ("stopped-being-wonderful", "close"),
    "TILNEY": ("one-reading-past", "hold"),
    "WEXTON": ("cannot-watch", "unknown"),
    "LARKFD": ("wonderful-and-priced", "commit"),
    "MARLOW": ("judgement-owed", "blocked"),
    "ASHDWN": ("you-marked-it-down", "hold"),
    "PENRYN": ("not-wonderful-enough", "hold"),
    "BRAMBR": ("cannot-screen", "unknown"),
}

LYNCH = {
    "DUNSFOLD": ("hold", "hold"),
    "ORRELL": ("room-for-more", "commit"),
    "HAVERTY": ("one-reading-past", "hold"),
    "PELSALL": ("hold", "hold"),
    "CASTERTON": ("cannot-watch", "unknown"),
    "BRINDLE": ("worth-buying", "commit"),
    "ALDBURY": ("worth-buying", "commit"),
    "KETTLEBY": ("not-established-as-a-grower", "hold"),
    "MOSSGIEL": ("not-growth-at-this-price", "hold"),
    "TREWIN": ("cannot-screen", "unknown"),
}

MAGIC = {
    "MARLBK": ("not-on-your-list", "hold"),
    "BRAMLY": ("time-is-up", "close"),
    "FENWCK": ("back-on-the-list", "hold"),
    "TARRNT": ("still-running", "hold"),
    "WOOLSN": ("still-running", "hold"),
    "KINVER": ("still-running", "hold"),
    "HALSTD": ("still-running", "hold"),
    "ODDGLY": ("buy-it", "commit"),
    "SUTTBY": ("buy-it", "commit"),
    "CRANWL": ("not-on-your-list", "hold"),
}

EXTRA = {"graham": {"LOWFD"}, "buffett": set(), "lynch": set(),
         "magic-formula": set()}
STORIES = {"graham": GRAHAM, "buffett": BUFFETT, "lynch": LYNCH,
           "magic-formula": MAGIC}


@pytest.fixture
def loaded():
    api = Api()
    result = api.load_sample()
    assert result["ok"], result.get("error")
    assert not result["skipped"], result["skipped"]
    return api, result


def open_by_strategy(api, strategy_id):
    """Open the sample journal running one strategy, and return it.

    By strategy rather than by name, because the name is built from the
    strategy's own display name and a strategy that renamed itself would
    silently take the whole file with it.
    """
    row = next(j for j in journals.list_journals()
               if (j["strategy"] or {}).get("id") == strategy_id)
    journals.set_open(row["id"])
    return api._open()


def decisions(api, strategy_id):
    journal, record, chain, _ = open_by_strategy(api, strategy_id)
    return {s["ticker"]: api._decide(s, journal["securities"], journal,
                                     record, chain)
            for s in journal["securities"]}


def securities_of(api, strategy_id):
    journal, *_ = open_by_strategy(api, strategy_id)
    return {s["ticker"]: s for s in journal["securities"]}


class TestBothLand:
    def test_one_journal_per_strategy(self, loaded):
        _api, result = loaded
        assert result["journals"] == 4
        assert result["n"] == 40
        assert set(result["names"]) == {"Sample — Graham", "Sample — Buffett",
                                        "Sample — Lynch",
                                        "Sample — Magic Formula"}
        assert len(journals.list_journals()) == 4

    def test_each_is_stamped_with_its_own_strategy(self, loaded):
        api, _ = loaded
        for strategy_id in STORIES:
            journal, record, *_ = open_by_strategy(api, strategy_id)
            assert record["id"] == strategy_id
            assert journal["name"] == f"Sample — {record['name']}"
            # The cash record each opens with, so the size rules can run at
            # all. It is a record and not an answer: what a sample starts
            # with is day one of its ledger, exactly as it is in a real
            # journal.
            from engine import cash
            assert cash.opening(journal)["amount"] > 0
            assert cash.balance(journal)["value"] > 0

    def test_none_pours_into_another(self, loaded):
        """A journal has one strategy, so the securities of one sample must
        never appear in another's journal. Sharing them would judge each
        company by rules its story was never about."""
        api, _ = loaded
        seen = set()
        for strategy_id in STORIES:
            tickers = set(securities_of(api, strategy_id))
            assert tickers & seen == set(), strategy_id
            seen |= tickers

    def test_it_never_touches_a_journal_that_is_already_here(self, loaded):
        api, _ = loaded
        again = api.load_sample()
        assert again["ok"]
        assert len(journals.list_journals()) == 2 * len(STORIES)


@pytest.mark.parametrize("strategy_id", sorted(STORIES))
class TestEachStillTellsItsStories:
    def test_every_security_still_tells_its_story(self, loaded, strategy_id):
        api, _ = loaded
        got = decisions(api, strategy_id)
        for ticker, (state, render) in STORIES[strategy_id].items():
            assert got[ticker]["state"]["id"] == state, \
                f'{ticker}: {got[ticker]["reason"]["summary"]}'
            assert got[ticker]["render"] == render, ticker
            assert got[ticker]["produced_by"] == "strategy", ticker

    def test_the_verdicts_carry_their_figures(self, loaded, strategy_id):
        api, _ = loaded
        for ticker, decision in decisions(api, strategy_id).items():
            if ticker in EXTRA[strategy_id]:
                continue
            assert decision["reason"]["evidence"], ticker
            assert decision["reason"]["rule"], ticker

    def test_nothing_in_it_is_presented_as_a_real_company(self, loaded,
                                                          strategy_id):
        """Demonstration content uses invented companies. A sample that
        named a real one would read as a recommendation however it was
        labelled."""
        path = next(p for p in Api()._sample_files()
                    if strategy_id in p.name)
        raw = json.loads(path.read_text(encoding="utf-8"))
        tickers = {s["ticker"] for s in raw["securities"]}
        assert tickers == set(STORIES[strategy_id]) | EXTRA[strategy_id]
        for s in raw["securities"]:
            assert s.get("cik") is None, s["ticker"]


class TestTheGrahamSample:
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
        by_ticker = securities_of(api, "graham")
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
        thrap = securities_of(api, "graham")["THRAP"]
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
        okell = securities_of(api, "graham")["OKELL"]
        [lot] = [l for l in okell["lots"] if l["kind"] == "buy"]
        assert lot["snapshot"]["decision"]["state"]["id"] == \
            "not-cheap-enough"
        assert lot["date"] == "2024-11-19"
        # And today's verdict about the same security is a different one.
        assert decisions(api, "graham")["OKELL"]["state"]["id"] == "too-big"

    def test_a_closed_holding_is_still_being_watched(self, loaded):
        """Exits keep getting priced. If a rule keeps leaving money on the
        table that is the finding, and it is only available because the
        ticker stays in the journal after the sale."""
        from engine import portfolio
        api, _ = loaded
        lowfd = securities_of(api, "graham")["LOWFD"]
        [cycle] = portfolio.cycles(lowfd)
        assert not cycle["open"]
        assert portfolio.cycle_return(lowfd, cycle,
                                      lowfd["price"])["value"] \
            == pytest.approx(76.8, abs=0.1)     # 11.20 -> 19.80
        [sale] = portfolio.lots(lowfd, "sell")
        since = portfolio.since_sale(lowfd, sale, lowfd["price"])
        assert since["until"] == "today"          # never bought back
        assert since["pct"] == pytest.approx(24.24, abs=0.01)


class TestTheBuffettSample:
    """What the second sample exists to show that the first cannot."""

    def test_a_verdict_that_refuses_to_decide_can_be_acted_on(self, loaded):
        """MARLOW passes every number and produces no verdict, because the
        three questions are unanswered. The way to answer one is built from
        what the decision cited, so a block that named them only in prose
        would be a dead end for the reader."""
        api, _ = loaded
        marlow = decisions(api, "buffett")["MARLOW"]
        assert marlow["render"] == "blocked"
        assert marlow["payload"]["needs"]
        cited = [i["subject"]["id"] for i in marlow["reason"]["evidence"]
                 if i["subject"].get("kind") == "judgement"]
        assert cited == ["moat_durability", "management_integrity",
                         "capital_allocation"]

    def test_the_answering_surface_is_offered_for_exactly_those(self, loaded):
        """The screen builds its question list from the decision's own
        citations. This is the join that makes the block escapable, and it
        runs through the real view payload rather than through the strategy."""
        api, _ = loaded
        open_by_strategy(api, "buffett")
        state = api.get_state()
        assert state["ok"], state
        marlow = next(s for s in state["securities"]
                      if s["ticker"] == "MARLOW")
        asked = {q["id"] for q in marlow["_judgements"] if q["cited"]}
        assert asked == {"moat_durability", "management_integrity",
                         "capital_allocation"}
        assert all(q["mark"] is None for q in marlow["_judgements"])
        assert all(q["question"] for q in marlow["_judgements"])

    def test_a_rejected_company_is_never_asked_to_be_assessed(self, loaded):
        """Nobody should be assessing the durability of a business their own
        rules have already turned down."""
        api, _ = loaded
        open_by_strategy(api, "buffett")
        state = api.get_state()
        penryn = next(s for s in state["securities"]
                      if s["ticker"] == "PENRYN")
        assert penryn["_judgements"] == []

    def test_a_business_that_stopped_being_wonderful_closes(self, loaded):
        """The exit that comes from no filing at all — the reader's own
        answer, changed. Both answers are on the record and neither was
        edited."""
        api, _ = loaded
        hallam = securities_of(api, "buffett")["HALLAM"]
        capital = [j for j in hallam["judgements"]
                   if j["id"] == "capital_allocation"]
        assert [j["mark"] for j in capital] == ["pass", "fail"]
        assert capital[0]["reasoning"] != capital[1]["reasoning"]
        assert decisions(api, "buffett")["HALLAM"]["render"] == "close"

    def test_a_position_at_half_the_account_is_left_alone(self, loaded):
        """There is no trim in this strategy and no verdict that could ask
        for one. A reader watching a holding climb needs that to be a stated
        position rather than something inferred from silence."""
        api, _ = loaded
        norbry = decisions(api, "buffett")["NORBRY"]
        assert norbry["render"] == "hold"
        assert norbry["reason"]["rule"] == "no-room-to-add"
        weight = next(i["observed"]["value"]
                      for i in norbry["reason"]["evidence"]
                      if i["subject"].get("id") == "position.weight")
        assert weight > 40.0

    def test_no_verdict_in_it_asks_for_a_trim(self, loaded):
        api, _ = loaded
        renders = {d["render"] for d in decisions(api, "buffett").values()}
        assert "reduce" not in renders

    def test_the_two_journals_disagree_about_the_same_kind_of_company(
            self, loaded):
        """The reason both are shipped. PENRYN is cheap and ordinary, and
        Buffett refuses it on the business; VANTR is a good business at a
        high price, and Graham refuses it on the price. Neither is wrong, and
        seeing both is the point of committing to one."""
        api, _ = loaded
        assert decisions(api, "buffett")["PENRYN"]["state"]["id"] == \
            "not-wonderful-enough"
        assert decisions(api, "graham")["VANTR"]["state"]["id"] == \
            "not-cheap-enough"
