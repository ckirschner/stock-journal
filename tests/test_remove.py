"""Removing ideas: possible for candidates that were never bought, refused
for anything carrying position history — the journal never deletes decisions."""

from app import Api
from engine import store


def _doc():
    return store.load("securities.json")


class TestRemoveSecurity:
    def test_an_idea_can_be_removed(self):
        api = Api()
        api.add_security("TYPO", "Mistyped Industries")
        r = api.remove_security("TYPO")
        assert r["ok"] and r["removed"] == "TYPO"
        assert all(s["ticker"] != "TYPO"
                   for s in _doc().get("securities", []))

    def test_an_idea_with_values_and_notes_still_removes(self):
        api = Api()
        api.add_security("SCRAP", "Scrapped Idea Corp")
        api.save_metrics("SCRAP", {"current_ratio": 1.5}, 12.0)
        api.add_note("SCRAP", "considered, passed")
        assert api.remove_security("SCRAP")["ok"]

    def test_a_holding_is_refused(self):
        api = Api()
        api.add_security("HELD", "Held Holdings")
        doc = _doc()
        s = next(x for x in doc["securities"] if x["ticker"] == "HELD")
        s["bucket"] = "holdings"
        s["position"] = {"shares": 10, "cost_basis": 5.0,
                        "opened": "2024-01-02"}
        store.save("securities.json", doc)
        r = api.remove_security("HELD")
        assert r["ok"] is False
        assert "history" in r["error"]
        assert any(x["ticker"] == "HELD" for x in _doc()["securities"])

    def test_a_previous_holding_is_refused(self):
        api = Api()
        api.add_security("SOLD", "Sold & Gone Inc")
        doc = _doc()
        s = next(x for x in doc["securities"] if x["ticker"] == "SOLD")
        s["bucket"] = "previous"
        s["exit"] = {"date": "2024-06-01", "reason": "Hit valuation",
                     "price": 20.0}
        store.save("securities.json", doc)
        r = api.remove_security("SOLD")
        assert r["ok"] is False
        assert any(x["ticker"] == "SOLD" for x in _doc()["securities"])

    def test_an_idea_with_a_frozen_snapshot_is_refused(self):
        """Whatever the bucket says, a frozen entry snapshot is recorded
        history and blocks removal."""
        api = Api()
        api.add_security("SNAP", "Snapshotted Idea")
        doc = _doc()
        s = next(x for x in doc["securities"] if x["ticker"] == "SNAP")
        s["entry_snapshot"] = {"frozen": "2024-01-02T00:00:00+00:00",
                               "metrics": {}}
        store.save("securities.json", doc)
        assert api.remove_security("SNAP")["ok"] is False
