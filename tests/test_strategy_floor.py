"""The floor an author imports instead of reimplementing.

docs/WRITING-A-STRATEGY.md names two assertions worth writing whatever else
you do, and until now every author wrote them again. Three suites here each
carried their own copy of the reachability one, and the bundle the document
tells a new author to copy carried the weakest version of the other.

Built on a synthetic two-state bundle rather than on Graham or Buffett: the
helper is generic over any bundle, and a test of it that needed a shipped
strategy would be evidence of the opposite.
"""

import pytest
from test_contract import decl, record

from engine import contract, strategy_floor


def two_states(**over):
    """A declaration with two states, so "reached" and "not reached" are both
    expressible. One state cannot distinguish them."""
    d = decl(states=[
        {"id": "sit", "name": "Sit", "render": "hold",
         "description": "Do nothing."},
        {"id": "go", "name": "Go", "render": "commit",
         "description": "Put money in."},
    ])
    d.update(over)
    return d


def bundle(decide):
    r = record(**two_states())
    r["decide"] = decide
    return r


def sit(ctx):
    return {"state": "sit", "payload": {},
            "reason": {"rule": "always", "summary": "By design.",
                       "evidence": [{"label": "A stated figure",
                                     "unit": "count", "actual": 1}]}}


def go(ctx):
    return {"state": "go",
            "payload": {"size": {"unit": "weight", "value": 5.0},
                        "condition": None},
            "reason": {"rule": "qualifies", "summary": "Everything passed.",
                       "evidence": [{"label": "A stated figure",
                                     "unit": "count", "actual": 1}]}}


def ctx_for(rec):
    from engine import context
    return context.build_context(
        {"ticker": "SYN", "name": "Synthetic Co", "lots": []}, [],
        values={}, inputs={}, record=rec)


def evaluate(rec):
    return contract.evaluate(rec, ctx_for(rec))


class TestTheTwoAssertions:

    def test_a_clean_run_is_empty(self):
        """The control. A floor that flagged a correct suite would be worse
        than none — it teaches the author to ignore it."""
        results = [evaluate(bundle(sit)), evaluate(bundle(go))]
        assert strategy_floor.unmet(two_states(), results) == []

    def test_a_refused_decision_is_reported_with_the_hosts_own_summary(self):
        """Every contract refusal lands on one state, which is why one check
        catches contradicted commits, dead-end blocks, malformed payloads and
        scattered groups at once. The sentence is the host's, so an author
        reading the failure is told what was wrong rather than that something
        was."""
        def invents(ctx):
            return {"state": "not-declared", "payload": {},
                    "reason": {"rule": "r", "summary": "s", "evidence": []}}

        got = evaluate(bundle(invents))
        assert got["state"]["id"] == "host:invalid-decision"
        problems = strategy_floor.unmet(two_states(), [got])
        assert len(problems) >= 1
        assert problems[0].startswith("a case came back host:invalid-decision")
        assert got["reason"]["summary"] in problems[0]

    def test_a_state_no_case_reached_is_reported_by_name(self):
        """The half no single case can catch. Nothing is wrong with any
        answer given; the Strategy tab is promising a verdict nobody can ever
        receive."""
        problems = strategy_floor.unmet(two_states(), [evaluate(bundle(sit))])
        assert len(problems) == 1
        assert "no case reached go" in problems[0]
        assert "vocabulary on the Strategy tab" in problems[0]

    def test_both_are_reported_at_once_and_not_the_first(self):
        """A list, matching validate_declaration and validate_decision. An
        author fixing one problem per run fixes them one per run."""
        def invents(ctx):
            return {"state": "not-declared", "payload": {},
                    "reason": {"rule": "r", "summary": "s", "evidence": []}}

        problems = strategy_floor.unmet(two_states(),
                                        [evaluate(bundle(invents))])
        assert len(problems) == 2
        assert any("invalid-decision" in p for p in problems)
        assert any("no case reached" in p for p in problems)

    def test_it_cannot_pass_on_no_cases(self):
        """The one structural property available here, and the reason this is
        a floor rather than a convenience.

        A suite that drove nothing at all — a fixture that stopped building
        contexts, a loop over an empty list — must not clear it. It cannot,
        because a declaration with no states is refused at load
        (engine/contract.validate_declaration), so there is always at least
        one state for an empty run to have failed to reach."""
        assert strategy_floor.unmet(two_states(), []) != []
        assert contract.validate_declaration(decl(states=[])) != []

    def test_it_reads_only_plain_data_so_any_bundle_can_use_it(self):
        """No fixture, no context, no knowledge of what a strategy is for. It
        takes a declaration and a list of decisions, both of which are plain
        dicts the host already produces."""
        assert strategy_floor.unmet(
            {"states": [{"id": "sit"}, {"id": "go"}]},
            [{"state": {"id": "sit"}}, {"state": {"id": "go"}}]) == []
        assert strategy_floor.unmet(
            {"states": [{"id": "sit"}, {"id": "go"}]},
            [{"state": {"id": "sit"}}]) != []

    def test_it_accepts_any_iterable_of_results(self):
        """An author who hands it a generator gets an answer rather than an
        empty one — a floor that silently passes on a consumed iterator is
        the vacuity the test above exists to refuse, arriving by another
        route."""
        rec = two_states()
        results = (r for r in [evaluate(bundle(sit)), evaluate(bundle(go))])
        assert strategy_floor.unmet(rec, results) == []


class TestTheShippedBundlesClearIt:
    """The three bundles in the repository, through the helper rather than
    through three hand-written copies of it."""

    @pytest.mark.parametrize("name", ["graham", "buffett"])
    def test_a_shipped_strategy_declares_no_state_it_cannot_reach(self, name):
        """Not a re-run of the suites' own coverage — those drive the cases.
        This asserts the helper agrees with them about what was declared, so
        a state added to a bundle without a case is caught by the same
        sentence wherever it is checked."""
        from engine import strategy_loader
        strategies, _reports = strategy_loader.discover()
        rec = strategies.get(name)
        assert rec is not None, f"{name} did not load"
        assert rec["states"], "a bundle with no states cannot be checked"
        problems = strategy_floor.unmet(rec, [])
        assert len(problems) == 1
        for s in rec["states"]:
            assert s["id"] in problems[0]
