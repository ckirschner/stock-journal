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
               "bucket": "ideas", "metrics": {}}
        ctx = context.build_context(sec, [sec], resolved["values"],
                                    {"journal-note": "present"})
        result = contract.evaluate(rec, ctx)
        assert result["render"] == "hold"
        assert result["produced_by"] == "strategy"
        assert result["state"]["id"] == "scaffold-hold"
        assert result["reason"]["data"]["journal_note"] == "present"
        assert result["reason"]["data"]["patience"] == 4  # shipped default

    def test_an_override_reaches_the_decision(self):
        store_company()
        rec = proof_record()
        resolved = strategy_values.resolve(
            rec, [("journal override", {"patience": 1})])
        sec = {"ticker": "SYN", "name": "Synthetic Co", "cik": 999,
               "bucket": "ideas", "metrics": {}}
        ctx = context.build_context(sec, [sec], resolved["values"], {})
        result = contract.evaluate(rec, ctx)
        assert result["reason"]["data"]["patience"] == 1

    def test_absence_flows_through_as_its_own_state(self):
        """No stored data: the scaffold must land on its unknown-typed
        state carrying the host's reason — never a zero, never a crash."""
        rec = proof_record()
        sec = {"ticker": "NOPE", "name": "Never Fetched Co",
               "bucket": "ideas", "metrics": {}}
        ctx = context.build_context(sec, [sec],
                                    strategy_values.resolve(rec)["values"],
                                    {})
        result = contract.evaluate(rec, ctx)
        assert result["render"] == "unknown"
        assert result["tier"] == "evaluation"
        assert result["state"]["id"] == "scaffold-dark"
        assert "fetch" in result["reason"]["summary"]
