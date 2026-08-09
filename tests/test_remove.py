"""Removing candidates: possible for ones that were never bought, refused
for anything carrying a lot — the journal never deletes decisions.

The guard is over the lot list, because that IS the position history: a
purchase or a sale is a recorded decision with a frozen verdict attached, and
there is no separate label that can disagree with it. A refused removal must
also be a complete refusal: a half-delete that reported failure would be the
worst of both.
"""

import pytest
from conftest import journal_for

from engine import journals

from app import Api


@pytest.fixture
def api(strategies):
    strategies("verdicts")
    journal_for("verdicts", "Ideas")
    return Api()


def _securities():
    return journals.load(journals.resolve_open())["securities"]


def _find(ticker):
    return next(s for s in _securities() if s["ticker"] == ticker)


def _mutate(ticker, **fields):
    journal = journals.load(journals.resolve_open())
    s = next(x for x in journal["securities"] if x["ticker"] == ticker)
    s.update(fields)
    journals.save(journal)


class TestRemoveSecurity:
    def test_an_idea_can_be_removed(self, api):
        api.add_security("TYPO", "Mistyped Industries")
        r = api.remove_security("TYPO")
        assert r["ok"] and r["removed"] == "TYPO"
        assert all(s["ticker"] != "TYPO" for s in _securities())

    def test_an_idea_with_values_and_notes_still_removes(self, api):
        """Values and notes carry no decision, so removing one loses nothing
        the learning loop needs. The confirmation names them; the guard does
        not stand on them."""
        api.add_security("SCRAP", "Scrapped Idea Corp")
        api.save_metrics("SCRAP", {"current_ratio": 1.5}, 12.0)
        api.add_note("SCRAP", "considered, passed")
        assert api.remove_security("SCRAP")["ok"]
        assert all(s["ticker"] != "SCRAP" for s in _securities())

    def test_a_holding_is_refused_and_nothing_is_half_deleted(self, api):
        api.add_security("HELD", "Held Holdings")
        assert api.open_position("HELD", 10, 5.0, "2024-01-02", "why")["ok"]
        r = api.remove_security("HELD")
        assert r["ok"] is False
        assert "history" in r["error"]
        assert len(_find("HELD")["lots"]) == 1

    def test_a_previous_holding_is_refused(self, api):
        """Selling everything closes the position; it does not erase the
        lots, and the record they carry is exactly what must survive."""
        api.add_security("SOLD", "Sold & Gone Inc")
        assert api.open_position("SOLD", 10, 5.0, "2024-01-02", "why")["ok"]
        assert api.sell_shares("SOLD", "Hit valuation", 20.0, "2024-06-01")["ok"]
        assert api.remove_security("SOLD")["ok"] is False
        assert len(_find("SOLD")["lots"]) == 2

    def test_a_lot_recorded_as_an_override_is_refused(self, api):
        """An override is the record principle 10 depends on most. Losing one
        would quietly delete the evidence that a rule is miscalibrated."""
        api.add_security("OVR", "Overridden Idea")
        assert api.open_position("OVR", 1, 5.0, "2024-01-02",
                                 "went ahead anyway")["ok"]
        assert api.remove_security("OVR")["ok"] is False
        assert _find("OVR")["lots"][0]["override"]["reason"] == \
            "went ahead anyway"

    def test_removing_from_one_journal_leaves_another_alone(self, api,
                                                            strategies):
        from engine import strategy_loader
        api.add_security("SHARED", "Shared Ticker Co")
        record = strategy_loader.discover()[0]["verdicts"]
        other = journals.create("Second", record)
        other["securities"].append({"ticker": "SHARED", "lots": [],
                                    "metrics": {}, "notes": []})
        journals.save(other)

        assert api.remove_security("SHARED")["ok"]
        assert [s["ticker"] for s in journals.load(other["id"])["securities"]] \
            == ["SHARED"]
