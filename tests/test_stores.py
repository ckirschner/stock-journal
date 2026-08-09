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


class TestStorePrimitives:
    """Every journal write goes through these two functions, so what they
    guarantee is what a journal guarantees."""

    def test_a_write_lands_whole_and_leaves_no_debris(self):
        path = store.data_dir() / "thing.json"
        store.write_json(path, {"x": 1})
        assert json.loads(path.read_text())["x"] == 1
        assert not list(store.data_dir().rglob("*.tmp"))

    def test_a_failed_write_leaves_the_previous_file_byte_identical(self):
        """Atomic persistence, tested by breaking it. A crash mid-write must
        never truncate what was already recorded — and the temp file must not
        survive to be mistaken for the real one."""
        path = store.data_dir() / "thing.json"
        store.write_json(path, {"x": 1})
        before = path.read_bytes()
        with pytest.raises(TypeError):
            store.write_json(path, {"x": {1, 2}})   # a set will not serialise
        assert path.read_bytes() == before
        assert not list(store.data_dir().rglob("*.tmp"))

    def test_two_writers_do_not_share_a_temp_file(self):
        """The journal is irreplaceable, so it gets at least the discipline
        the re-fetchable filing cache already has: a unique temp per writer,
        never a shared name two processes can finish for each other."""
        import os
        import tempfile
        seen = []
        real = tempfile.mkstemp

        def spy(*a, **kw):
            fd, name = real(*a, **kw)
            seen.append(os.path.basename(name))
            return fd, name

        tempfile.mkstemp = spy
        try:
            store.write_json(store.data_dir() / "a.json", {"x": 1})
            store.write_json(store.data_dir() / "a.json", {"x": 2})
        finally:
            tempfile.mkstemp = real
        assert len(seen) == 2 and seen[0] != seen[1]

    def test_a_missing_file_is_absence_not_an_error(self):
        assert store.read_json(store.data_dir() / "nothing.json") is None
        assert store.read_json(store.data_dir() / "nothing.json", {}) == {}

    def test_an_unreadable_file_refuses_rather_than_reading_as_empty(self):
        """A journal that reads as empty looks like a journal with nothing in
        it, which is a fabricated answer to "what did I record?". The file is
        left exactly where it is so nothing overwrites it."""
        path = store.ensure_data() / "broken.json"
        path.write_text("{ truncated", encoding="utf-8")
        with pytest.raises(store.StoreError):
            store.read_json(path)
        assert path.read_text(encoding="utf-8") == "{ truncated"
