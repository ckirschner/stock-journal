"""The two assertions a strategy's tests are worth writing whatever else
they do.

docs/WRITING-A-STRATEGY.md names them, and until now it asked every author to
write them again: assert that no case returns `host:invalid-decision`, and
assert that every declared state is reached by some case. Three suites in this
repository each wrote their own copy of the second one, and the bundle the
documentation tells a new author to copy carried the *weakest* version of the
first — which is what a rule reimplemented per author looks like after three
authors.

Both are generic over any bundle, because both read only plain declaration
data and plain decisions. Neither knows anything about which measures exist,
what a strategy is for, or how its cases were built.

**Why these two and not more.** They are the pair that catch a whole class
each rather than a case each.

`host:invalid-decision` is where every contract refusal lands — a commit
standing beside a group the host resolved as anything but pass, a blocked
verdict with no way out of it, a malformed payload, evidence scattered across
groups that do not exist. One check catches all of them, and Buffett's
authoring found it the hard way, one contradiction at a time.

An unreached state is the opposite kind of defect: nothing is wrong with any
answer the tool gives, and the Strategy tab is telling the reader the tool can
say something it never says. That is vocabulary promising a verdict nobody can
ever receive, and no single case can catch it — only the union of them can.

**What this is not.** It is a helper an author imports, not a guarantee the
host enforces: an author who never calls it is exactly where they were before.
The one structural property available here is that it cannot pass vacuously —
`unmet(record, [])` always fails, because a declaration with no states is
refused at load, so an empty run has every state unreached. A floor that a
suite running zero cases could clear would not be a floor.

Deliberately narrower than what the shipped suites already do beside it. They
assert `produced_by == "strategy"`, which also catches `host:strategy-error`
and `host:inputs-missing` and fails at the case rather than at the end; this
delivers the documented pair and nothing more, so it sits beside that check
rather than replacing it.
"""

from __future__ import annotations

HOST_INVALID = "host:invalid-decision"


def unmet(record: dict, results) -> list[str]:
    """The floor assertions that did not hold, as sentences. Empty means both
    did.

    `record` is a loaded bundle — what `strategy_loader.discover` returns, for
    a bundle installed under `strategies/` or loaded from anywhere with
    `discover([your_dir])`. `results` is every result the suite's cases
    produced, straight from `contract.evaluate`.

    Returns a list rather than raising, matching `contract.validate_declaration`
    and `contract.validate_decision`: the caller asserts on it, and gets every
    problem at once instead of the first.
    """
    results = list(results)
    problems = [
        f"a case came back {HOST_INVALID}: "
        + str((r.get("reason") or {}).get("summary") or "no summary")
        for r in results
        if (r.get("state") or {}).get("id") == HOST_INVALID]

    reached = {(r.get("state") or {}).get("id") for r in results}
    missing = [str(s["id"]) for s in (record.get("states") or [])
               if s.get("id") not in reached]
    if missing:
        problems.append(
            "no case reached " + ", ".join(missing) + ". A declared state "
            "nothing returns is vocabulary on the Strategy tab telling the "
            "reader the tool can say something it cannot — either write the "
            "case that reaches it, or stop declaring it.")
    return problems
