"""The shipped proof bundle, end to end: discovered from the real strategies
directory, values resolved through the chain, a context built from stored
filings, and one decision back across the boundary in the contract's
envelope. This is the whole point of the branch in one test file."""

from conftest import dur, filing, balance_face

from engine import context, contract, facts_store, strategy_loader
from engine import strategy_values


def store_company(cik=999):
    end, start = "2023-12-31", "2023-01-01"
    facts = [
        dur("us-gaap:Revenues", start, end, 1000),
        dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
            start, end, 200, stmt="CashFlowStatement"),
        dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            start, end, 50, stmt="CashFlowStatement"),
    ] + balance_face(end, assets=800)
    facts_store.save_filing(cik, filing("S-1", "10-K", "2024-02-20", end,
                                        facts))


def proof_record():
    strategies, reports = strategy_loader.discover()
    assert "contract-proof" in strategies, \
        [r["errors"] for r in reports if not r["ok"]]
    return strategies["contract-proof"]


class TestTheProof:
    def test_it_holds_when_the_measure_reads(self):
        store_company()
        rec = proof_record()
        resolved = strategy_values.resolve(rec, [])
        assert resolved["errors"] == []
        sec = {"ticker": "SYN", "name": "Synthetic Co", "cik": 999,
               "metrics": {}, "lots": []}
        ctx = context.build_context(sec, [sec], resolved["values"],
                                    {"journal-note": "present"}, record=rec)
        result = contract.evaluate(rec, ctx)
        assert result["render"] == "hold"
        assert result["produced_by"] == "strategy"
        assert result["state"]["id"] == "scaffold-hold"
        # The escape hatch carried the one thing that is genuinely prose.
        assert result["reason"]["note"] == "present"

        cited = result["reason"]["evidence"]
        by_id = {e["subject"]["id"]: e for e in cited}
        # The same measure is cited twice — once as a test against a level,
        # once pinned to a past period end — so these are picked by what
        # they are rather than by where they happen to sit in the list.
        tested = next(e for e in cited if e["subject"]["id"] == "fcf_ttm"
                      and e["test"])
        dated = next(e for e in cited if e["subject"].get("at"))
        value_cited = by_id["patience"]
        stated = next(e for e in cited if e["subject"]["kind"] == "stated")
        # The host answered the citation: label and unit from the bank, the
        # value from the context, the outcome from the arithmetic.
        assert tested["subject"]["label"] == \
            "Free cash flow, trailing twelve months"
        assert tested["subject"]["unit"] == "usd"
        assert tested["observed"]["value"] == 150.0
        assert tested["observed"]["provenance"]      # the bank's, not made up
        assert tested["test"]["phrase"] == "above"
        assert tested["outcome"] == "pass"
        # A declared value cited by id renders with its own declared label
        # and its explanation, so the number can be understood in place.
        assert value_cited["subject"]["label"] == "Readings considered"
        assert value_cited["observed"]["value"] == 4     # shipped default
        assert value_cited["subject"]["explain"]
        assert value_cited["outcome"] == "noted"
        # A figure the strategy worked out itself is stated, and says so.
        assert stated["subject"]["kind"] == "stated"
        assert stated["observed"]["source"] == "stated"
        # A past reading of the same measure, cited by its period end.
        assert dated["subject"]["at"] == "2023-12-31"
        assert dated["observed"]["value"] == 150.0
        # The account figures the host can only reach once a journal answers
        # for them. Unanswered here, so they are absent — and the absence
        # names the field, rather than the scaffold inventing a sentence.
        assert by_id["portfolio.cash"]["observed"]["status"] == "absent"
        assert "Free cash" in by_id["portfolio.cash"]["observed"]["reason"]

    def test_the_account_figures_resolve_once_the_journal_answers(self):
        """The other half: a declared role turns an answer into a figure the
        host reports, with no strategy restating it."""
        store_company()
        rec = proof_record()
        sec = {"ticker": "SYN", "name": "Synthetic Co", "cik": 999,
               "metrics": {}, "lots": []}
        ctx = context.build_context(sec, [sec],
                                    strategy_values.resolve(rec)["values"],
                                    {"free-cash": 25_000.0}, record=rec)
        result = contract.evaluate(rec, ctx)
        by_id = {e["subject"]["id"]: e for e in result["reason"]["evidence"]}
        assert by_id["portfolio.cash"]["observed"]["value"] == 25_000.0
        assert by_id["portfolio.account_value"]["observed"]["value"] == \
            25_000.0      # nothing held, so the account is the cash

    def test_an_override_reaches_the_decision(self):
        store_company()
        rec = proof_record()
        resolved = strategy_values.resolve(
            rec, [("journal override", {"patience": 1})])
        sec = {"ticker": "SYN", "name": "Synthetic Co", "cik": 999,
               "metrics": {}, "lots": []}
        ctx = context.build_context(sec, [sec], resolved["values"], {},
                                    record=rec)
        result = contract.evaluate(rec, ctx)
        cited = next(e for e in result["reason"]["evidence"]
                     if e["subject"]["id"] == "patience")
        assert cited["observed"]["value"] == 1
        assert result["reason"]["note"] is None

    def test_absence_flows_through_as_its_own_state(self):
        """No stored data: the scaffold must land on its unknown-typed
        state carrying the host's reason — never a zero, never a crash."""
        rec = proof_record()
        sec = {"ticker": "NOPE", "name": "Never Fetched Co",
               "metrics": {}, "lots": []}
        ctx = context.build_context(sec, [sec],
                                    strategy_values.resolve(rec)["values"],
                                    {}, record=rec)
        result = contract.evaluate(rec, ctx)
        assert result["render"] == "unknown"
        assert result["tier"] == "evaluation"
        assert result["state"]["id"] == "scaffold-dark"
        # The strategy cited the measure and said nothing about why it was
        # absent; the host's own reason is what reaches the screen.
        [item] = result["reason"]["evidence"]
        assert item["observed"]["status"] == "absent"
        assert "fetch" in item["observed"]["reason"]
        assert item["outcome"] == "noted"
