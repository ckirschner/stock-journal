"""A citation the user cannot answer is a dead end, and the host says which.

Citing is the whole discovery mechanism for anything asked per security: the
Edit-values dialog offers exactly the figures a decision read, the Judgements
section asks exactly the questions it asked, and a blocked verdict is refused
when it sends a reader somewhere its own citations do not fill. All three
have to agree about one thing — which metric-bank entry a citation touched —
and all three used to work it out separately, by matching the SHAPE the
subject renders in.

That was already wrong. A measure cited only as how far it has moved since a
purchase resolves as kind `change`, matched none of them, and reached none of
those screens: the verdict named a figure and offered no way to supply it.
Both shipped strategies escaped by coincidence, every drift measure of theirs
also appearing plainly in an exit — so nothing anywhere would have caught it,
and the first strategy whose rule is drift alone would have shipped broken.

So the answer travels with the subject: every citation says what it reads,
and the surfaces ask that rather than re-deriving it. What is pinned here is
the general shape and not the one case, because the case was never the point
— the next kind added is.
"""

import pytest
from conftest import filing, inst, balance_face, dur

from engine import contract, facts_store, journals, price_store

from app import Api

DRIFT = "gross_margin_ttm"          # cited only as a change since a purchase
ROBUST = "current_ratio"            # cited only with a year dropped


# ---------------------------------------------------------------------------
# the host's own answer
# ---------------------------------------------------------------------------

def evidence(record, ctx, items):
    rows, errors = contract.resolve_evidence(record, ctx, items)
    assert errors == [], errors
    return rows


def measure(value=None, reason="nothing has been computed for it"):
    """One measure as a context carries it. Absent is fine and deliberate:
    what is under test is which entry a citation NAMES, and a citation names
    the same entry whether or not anybody could work the figure out."""
    current = ({"status": "known", "value": value, "source": "computed",
                "cautions": [], "provenance": []} if value is not None
               else {"status": "absent", "reason": reason})
    return {"current": current,
            "series": {"cadence": None, "points": [], "note": None,
                       "truncated": False}}


def bare_ctx(**over):
    c = {"contract": contract.CONTRACT_VERSION, "today": "2026-08-11",
         "inputs": {}, "values": {"cap": 1},
         "measures": {"fcf_ttm": measure(150.0),
                      "roic_median_5y": measure(18.9),
                      "moat_durability": measure()},
         "position": {"weight": {"status": "absent",
                                 "reason": "the journal records no account "
                                           "value"},
                      "shares": 10.0,
                      "baselines": {
                          "first-purchase": {
                              "status": "absent",
                              "reason": "nothing is held"},
                          "last-purchase": {
                              "status": "absent",
                              "reason": "nothing is held"}}},
         "portfolio": {}}
    c.update(over)
    return c


def bare_record():
    from test_contract import record
    return record(values=[{"id": "cap", "label": "A cap",
                           "type": "number", "min": 0,
                           "source": {"name": "a fixture", "reasoning": True},
                           "explain": "e"}])


class TestEveryCitationSaysWhatItReads:
    """`reads` is a required argument of the subject constructor, so a kind
    added later cannot be built without answering. That is the part meant to
    survive; the kinds below are only today's list."""

    def rec(self):
        return bare_record()

    def ctx(self):
        return bare_ctx()

    def test_a_plain_measure_reads_its_own_bank_entry(self):
        [row] = evidence(self.rec(), self.ctx(), [{"measure": "fcf_ttm"}])
        assert row["subject"]["kind"] == "measure"
        assert row["subject"]["reads"] == "fcf_ttm"

    def test_a_change_reads_the_measure_it_is_a_change_in(self):
        """The case that was broken. The subject is its own thing — its own
        label, its own unit — and the figure underneath it is still one the
        user may have to supply."""
        [row] = evidence(self.rec(), self.ctx(),
                         [{"measure": "fcf_ttm", "since": "first-purchase"}])
        assert row["subject"]["kind"] == "change"
        assert row["subject"]["reads"] == "fcf_ttm"

    def test_a_dropped_year_reads_the_measure_it_dropped_it_from(self):
        [row] = evidence(self.rec(), self.ctx(),
                         [{"measure": "roic_median_5y", "without":
                           "one-year"}])
        assert row["subject"]["kind"] == "robustness"
        assert row["subject"]["reads"] == "roic_median_5y"

    def test_a_host_fact_reads_no_bank_entry(self):
        """None is a real answer and not an omission: a fact about the
        position is answerable nowhere the user types figures."""
        [row] = evidence(self.rec(), self.ctx(),
                         [{"fact": "position.weight"}])
        assert row["subject"]["reads"] is None

    def test_a_stated_figure_and_a_setting_read_no_bank_entry(self):
        rows = evidence(self.rec(), self.ctx(),
                        [{"label": "A number", "unit": "count", "actual": 3},
                         {"value": "cap"}])
        assert [r["subject"]["reads"] for r in rows] == [None, None]

    def test_every_kind_the_host_builds_answers_the_question(self):
        """The point of the constructor, asserted as coverage rather than as
        a list: whatever a citation resolves to, `reads` is answered."""
        rows = evidence(self.rec(), self.ctx(), [
            {"measure": "fcf_ttm"},
            {"measure": "fcf_ttm", "since": "last-purchase"},
            {"measure": "roic_median_5y", "without": "one-year"},
            {"fact": "position.weight"},
            {"measure": "moat_durability"},
            {"label": "A number", "unit": "count", "actual": 3},
            {"value": "cap"}])
        assert all("reads" in r["subject"] for r in rows)
        assert {r["subject"]["kind"] for r in rows} == {
            "measure", "change", "robustness", "judgement", "fact", "stated",
            "value"}

    def test_the_constructor_will_not_build_a_subject_that_stays_silent(self):
        """Principle 14. The next kind is not asked to remember; it cannot be
        written without saying what it draws on."""
        with pytest.raises(TypeError):
            contract._subject("invented", "x", label="L", unit="none")


class TestTheHostAnswersWhichEntriesWereRead:
    def rows(self, *items):
        return evidence(bare_record(), bare_ctx(), list(items))

    def test_a_drift_only_citation_is_found(self):
        got = contract.cited_bank_ids(
            self.rows({"measure": "fcf_ttm", "since": "first-purchase"}))
        assert got == ["fcf_ttm"]

    def test_the_same_measure_cited_three_ways_is_named_once(self):
        got = contract.cited_bank_ids(self.rows(
            {"measure": "roic_median_5y"},
            {"measure": "roic_median_5y", "since": "first-purchase"},
            {"measure": "roic_median_5y", "without": "one-year"}))
        assert got == ["roic_median_5y"]

    def test_what_reads_no_bank_entry_is_never_offered(self):
        assert contract.cited_bank_ids(
            self.rows({"fact": "position.weight"},
                      {"label": "A number", "unit": "count",
                       "actual": 3})) == []

    def test_the_bank_says_which_kind_an_entry_is_and_not_the_citation(self):
        """A strategy cites a judgement exactly as it cites a measure. Which
        surface answers it is the bank's call — principle 5, so a strategy
        cannot disguise an assessment as a measurement by choosing how to
        cite it."""
        rows = self.rows({"measure": "fcf_ttm"},
                         {"measure": "moat_durability"})
        assert contract.cited_bank_ids(rows, "computed") == ["fcf_ttm"]
        assert contract.cited_bank_ids(rows, "qualitative") == \
            ["moat_durability"]


# ---------------------------------------------------------------------------
# the surfaces that answer it
# ---------------------------------------------------------------------------

def company(cik=881, ticker="DRF", close=20.0):
    end = "2024-12-31"
    facts = balance_face(end, extra=[
        inst("us-gaap:AssetsCurrent", end, 200),
        inst("us-gaap:LiabilitiesCurrent", end, 100)])
    facts += [dur("us-gaap:Revenues", "2024-01-01", end, 1_000.0),
              dur("us-gaap:CostOfRevenue", "2024-01-01", end, 600.0)]
    facts_store.save_filing(cik, filing("A-1", "10-K", "2025-02-20", end,
                                        facts))
    doc = price_store.load(cik)
    price_store.merge_series(doc, ticker, "test", [["2026-08-01", close, 100]],
                             [])
    price_store.save(cik, doc)
    return cik


@pytest.fixture
def api(strategies):
    strategies("drifter")
    a = Api()
    assert a.create_journal("Drift", "drifter", {})["ok"]
    cik = company()
    assert a.add_security("DRF", "Drift Co")["ok"]
    doc = journals.load(journals.resolve_open())
    next(s for s in doc["securities"] if s["ticker"] == "DRF")["cik"] = cik
    journals.save(doc)
    return a


class TestAFigureCitedOnlyAsDriftCanStillBeSupplied:
    """The consequence, end to end. A strategy whose only rule is about how
    far something has moved names two measures and neither of them plainly.
    Both have to reach the dialog that lets the user type one in — otherwise
    the verdict cites a figure and the program offers nowhere to give it."""

    def security(self, api):
        return api.get_state()["securities"][0]

    def test_the_drift_measure_is_offered_for_hand_entry(self, api):
        s = self.security(api)
        assert DRIFT in s["_cited"]
        assert DRIFT in [row["id"] for row in s["_inputs"]]

    def test_the_dropped_year_measure_is_offered_too(self, api):
        s = self.security(api)
        assert ROBUST in s["_cited"]
        assert ROBUST in [row["id"] for row in s["_inputs"]]

    def test_the_row_says_the_strategy_is_reading_it(self, api):
        """`cited` is what the dialog uses to separate "your strategy reads
        this" from "you typed this once". A drift measure that arrived
        without it would render as a leftover."""
        rows = {r["id"]: r for r in self.security(api)["_inputs"]}
        assert rows[DRIFT]["cited"] is True
        assert rows[ROBUST]["cited"] is True

    def test_what_was_computed_for_it_travels_with_it(self, api):
        """The same set drives `_computed`, so a figure the tool did work out
        renders beside the box for typing one in."""
        assert DRIFT in self.security(api)["_computed"]

    def test_a_hand_entered_figure_reaches_the_drift_rule(self, api):
        """The whole point of offering it. What the user types is what the
        strategy reads on the next evaluation."""
        assert api.save_metrics("DRF", {ROBUST: 1.9}, None)["ok"]
        row = next(r for r in self.security(api)["_inputs"]
                   if r["id"] == ROBUST)
        assert row["entered"]["value"] == 1.9
        assert self.security(api)["_value_sources"][ROBUST] == "manual"
