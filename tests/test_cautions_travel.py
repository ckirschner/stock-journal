"""A qualified number is never handed over bare.

Some figures rest on something the reader has to be told about: a share class
valued at a sibling's close, a balance-sheet line matched by its label rather
than by a mapped concept, a price too old to be current. The host says so in
`cautions`, and this file holds the rule that the sentence goes wherever the
number goes — onto the screen, into an append-only snapshot, and through a
per-filing series point.

The snapshot is the serious one. A frozen record is written once and never
recomputed, so a caution dropped on the way in is dropped forever, and the
record then states a figure as more certain than the evidence supported. That
is not a display gap; it is the audit trail asserting something nothing ever
established.

Market capitalization drives most of these, on purpose. It is the one
admitted approximation in the compute layer, it was kept on the explicit
condition that its qualification reaches the reader, and it feeds P/E,
enterprise value, dividend yield and both cash-to-cap ratios — so a caution
lost here is lost from a third of the bank at once.
"""

import itertools

import pytest
from conftest import (MULTICLASS_PRICED, MULTICLASS_UNPRICED, journal_for,
                      multiclass_company)

from engine import dataview, journals

from app import Api

_CIK = itertools.count(7100)


class TestTheMarketCapChain:
    """The specific chain the blend was kept on: which classes were blended,
    what share of the company was assumed, and how stale the oldest close in
    it is — reaching the reader at every stop."""

    @pytest.fixture(autouse=True)
    def _journal(self, strategies):
        strategies("qualified")
        journal_for("qualified", "Chain")

    def _seed(self, closes=None):
        cik = next(_CIK)
        multiclass_company(cik, closes)
        api = Api()
        assert api.add_security("SYN", "Synthetic Co")["ok"]
        journal = journals.load(journals.resolve_open())
        journal["securities"][0]["cik"] = cik
        journals.save(journal)
        return api

    def _blend_note(self, cautions):
        return next((c for c in cautions if "no stored close" in c), None)

    def test_the_engine_states_all_three_things(self):
        """Read once at the source, so the tests below are about the trip and
        not about whether there was anything to carry."""
        api = self._seed(closes=[("2024-01-02", 20.0)])   # deliberately old
        s = api.get_state()["securities"][0]
        cautions = s["_computed"]["market_cap"]["cautions"]
        blend = self._blend_note(cautions)
        assert blend is not None
        assert "Class B" in blend                       # which class
        assert "10.0% of the share count" in blend      # how much of it
        assert "SYN close of 2024-01-02" in blend       # valued at whose
        assert "assumption" in blend and "not a measurement" in blend
        stale = next(c for c in cautions if "days old" in c)
        assert "2024-01-02" in stale and "fetch prices" in stale

    def test_it_reaches_the_screen_with_the_value(self):
        api = self._seed()
        s = api.get_state()["securities"][0]
        entry = s["_computed"]["market_cap"]
        assert entry["status"] == "computed"
        assert entry["value"] == (MULTICLASS_PRICED
                                  + MULTICLASS_UNPRICED) * 20.0
        assert self._blend_note(entry["cautions"])

    def test_it_reaches_the_data_page(self):
        api = self._seed()
        rows = api.get_coverage("SYN")["coverage"]["entries"]
        row = next(r for r in rows if r["id"] == "market_cap")
        assert self._blend_note(row["cautions"])

    def test_it_reaches_the_strategys_evidence(self):
        """The strategy cites; the host answers. The answer carries what
        qualified the figure, because a strategy may never restate it."""
        api = self._seed()
        d = api.get_state()["securities"][0]["_decision"]
        cited = [e for e in d["reason"]["evidence"]
                 if e["subject"]["id"] == "market_cap" and "at" not in
                 e["subject"]]
        assert cited, d
        assert self._blend_note(cited[0]["observed"]["cautions"])

    def test_it_reaches_a_reading_cited_at_a_past_period(self):
        """A per-filing series point is a reading of the same measure and is
        qualified the same way. This was the one route that returned the
        number alone."""
        api = self._seed()
        d = api.get_state()["securities"][0]["_decision"]
        at = [e for e in d["reason"]["evidence"]
              if e["subject"]["id"] == "market_cap" and "at" in e["subject"]]
        assert at, d
        assert self._blend_note(at[0]["observed"]["cautions"])

    def test_it_is_frozen_into_the_purchase_record(self):
        """The correctness half. This record can never be asked again."""
        api = self._seed()
        assert api.open_position("SYN", 5, 9.5, "2025-06-30", "in")["ok"]
        journal = journals.load(journals.resolve_open())
        snap = journal["securities"][0]["lots"][-1]["snapshot"]
        frozen = snap["metrics"]["market_cap"]
        assert frozen["value"] is not None
        assert self._blend_note(frozen["cautions"])
        assert frozen["provenance"]
        # and inside the frozen decision, where the verdict's own figures are
        cited = [e for e in snap["decision"]["reason"]["evidence"]
                 if e["subject"]["id"] == "market_cap"]
        assert cited and all(self._blend_note(e["observed"]["cautions"])
                             for e in cited)

    def test_it_is_frozen_into_the_sale_record_too(self):
        api = self._seed()
        assert api.open_position("SYN", 5, 9.5, "2025-06-30", "in")["ok"]
        assert api.sell_shares("SYN", "Panic", 12.0, "2025-07-30")["ok"]
        journal = journals.load(journals.resolve_open())
        snap = journal["securities"][0]["lots"][-1]["snapshot"]
        assert self._blend_note(snap["metrics"]["market_cap"]["cautions"])


class TestASnapshotRefusesABareNumber:
    """Structural rather than remembered. Three carriers dropped cautions by
    each holding a plain float; the shape that made that possible is gone,
    and the write refuses the old one."""

    def test_a_qualified_value_has_exactly_the_four_parts(self):
        v = dataview.qualified(1.0, "computed", ["a caution"], ["a source"])
        assert set(v) == {"value", "source", "cautions", "provenance"}

    def test_the_snapshot_refuses_a_number_on_its_own(self):
        from engine import portfolio
        s = portfolio.new_security("SYN", "Synthetic Co")
        with pytest.raises(ValueError) as e:
            portfolio.add_lot(s, None, 1, 10.0, "2025-01-02",
                              values={"market_cap": 1000.0})
        assert "bare float" in str(e.value)
