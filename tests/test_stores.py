"""The stores: append-only, atomic, and never silently merging two companies."""

import json

import pytest

from engine import facts_store, price_store, store


class TestFactsStore:
    def test_filings_append_and_never_disappear(self):
        cik = 111
        facts_store.save_filing(cik, {"accession": "A-1", "form": "10-K",
                                      "filed": "2020-01-01",
                                      "period_of_report": "2019-12-31",
                                      "facts": []})
        facts_store.save_filing(cik, {"accession": "A-2", "form": "10-Q",
                                      "filed": "2020-05-01",
                                      "period_of_report": "2020-03-31",
                                      "facts": []})
        held = facts_store.load_all_filings(cik)
        assert [f["accession"] for f in held] == ["A-1", "A-2"]
        # re-saving the same accession updates that file only
        facts_store.save_filing(cik, {"accession": "A-1", "form": "10-K",
                                      "filed": "2020-01-01",
                                      "period_of_report": "2019-12-31",
                                      "facts": [{"concept": "x"}]})
        held = facts_store.load_all_filings(cik)
        assert len(held) == 2

    def test_no_tmp_debris_after_write(self):
        cik = 112
        facts_store.save_filing(cik, {"accession": "A-1", "form": "10-K",
                                      "filed": "2020-01-01",
                                      "period_of_report": "2019-12-31",
                                      "facts": []})
        leftovers = list(facts_store.cik_dir(cik).glob("*.tmp"))
        assert leftovers == []

    def test_corrupt_company_file_is_set_aside_not_reused(self):
        cik = 113
        d = facts_store.cik_dir(cik)
        d.mkdir(parents=True)
        (d / "company.json").write_text("{ truncated", encoding="utf-8")
        doc = facts_store.load_company(cik)
        assert doc["identity"] is None
        assert any("broken" in p.name for p in d.iterdir())

    def test_identity_changes_are_history_not_overwrite(self):
        doc = facts_store.load_company(114)
        facts_store.record_identity(doc, {"cik": 114, "name": "Old Name Corp"})
        facts_store.record_identity(doc, {"cik": 114, "name": "Old Name Corp"})
        facts_store.record_identity(doc, {"cik": 114, "name": "New Name Inc"})
        assert doc["identity"]["name"] == "New Name Inc"
        assert [h["identity"]["name"] for h in doc["identity_history"]] == \
            ["Old Name Corp", "New Name Inc"]


class TestPriceStore:
    def test_merge_adds_and_never_deletes(self):
        doc = price_store.load(200)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2024-01-02", 10.0, 100]], [])
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2024-01-03", 11.0, 100]], [])
        rows = doc["series"]["SYN"]["rows"]
        assert [r[0] for r in rows] == ["2024-01-02", "2024-01-03"]

    def test_changed_close_is_a_recorded_revision(self):
        doc = price_store.load(201)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2024-01-02", 10.0, 100]], [])
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2024-01-02", 10.05, 100]], [])
        s = doc["series"]["SYN"]
        assert s["rows"][0][1] == 10.05
        assert s["revisions"][0]["was"] == 10.0

    def test_terminal_series_refuses_new_rows(self):
        doc = price_store.load(202)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2024-01-02", 10.0, 100]], [])
        price_store.mark_terminal(doc, "SYN", "symbol reassigned")
        with pytest.raises(ValueError):
            price_store.merge_series(doc, "SYN", "tiingo",
                                     [["2024-06-01", 55.0, 9]], [])
        assert doc["series"]["SYN"]["rows"][-1][0] == "2024-01-02"

    def test_close_on_never_reaches_forward(self):
        doc = price_store.load(203)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2024-01-05", 10.0, 100],
                                  ["2024-01-12", 12.0, 100]], [])
        assert price_store.close_on(doc, "SYN", "2024-01-10") == \
            ("2024-01-05", 10.0)
        assert price_store.close_on(doc, "SYN", "2024-01-04") is None
        # beyond the lookback: absent, not the stale value
        assert price_store.close_on(doc, "SYN", "2024-02-01") is None

    def test_zero_closes_are_no_trade_not_a_price(self):
        doc = price_store.load(204)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2024-01-05", 0.0, 0],
                                  ["2024-01-04", 9.0, 10]], [])
        assert price_store.latest_close(doc, "SYN") == ("2024-01-04", 9.0)


class TestAtomicJournal:
    def test_store_save_leaves_no_partial_file(self, tmp_path):
        store.save("securities.json", {"securities": [], "x": 1})
        path = store.data_dir() / "securities.json"
        assert json.loads(path.read_text())["x"] == 1
        assert not list(store.data_dir().glob("*.tmp"))
