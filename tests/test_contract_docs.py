"""The reference document, against the tables it documents.

Documentation is a restatement, and the whole contract is built on the idea
that a restatement can be wrong and nothing checks it. A hand-typed copy of
`COMPARATORS` goes stale the first time somebody adds a comparator —
silently, in the one place an author trusts to be right, and the author has
no way to find out except by writing a bundle the host refuses.

So the tables are generated from the mappings themselves, and this is what
makes that guarantee hold rather than merely exist: a host table that has
moved and a document that has not is a failing test.

What it deliberately does NOT check is the prose. What a thing is *for*
cannot be generated, and a test that demanded it would be pinning sentences
rather than facts.
"""

import re

import pytest

from engine import contract
from tools import contract_reference as ref


@pytest.fixture
def doc():
    return ref.DOC.read_text(encoding="utf-8")


class TestTheGeneratedTablesAreCurrent:
    def test_the_document_matches_the_host_tables(self, doc):
        assert ref.render(doc) == doc, (
            "docs/WRITING-A-STRATEGY.md is out of date with "
            "engine/contract.py. Run `python -m tools.contract_reference`.")

    def test_regenerating_twice_changes_nothing(self, doc):
        """A generator that is not idempotent turns every edit to the
        document into a diff nobody can review."""
        once = ref.render(doc)
        assert ref.render(once) == once

    def test_a_table_that_moved_is_caught(self, doc):
        """The check proved against a change rather than asserted. A new
        comparator with the document untouched has to come back stale."""
        extra = dict(contract.COMPARATORS)
        extra["roughly"] = contract.COMPARATORS["equals"]
        original = contract.COMPARATORS
        contract.COMPARATORS = extra
        try:
            assert ref.render(doc) != doc
        finally:
            contract.COMPARATORS = original
        assert ref.render(doc) == doc


class TestEveryHostTableIsDocumented:
    """A table nobody generated is a table the reference silently omits, and
    an author's first sign of it is a bundle the host refuses over vocabulary
    they were never shown."""

    DOCUMENTED = {
        "RENDER_TYPES", "STATE_FIXES", "HOST_STATES", "COMPARATORS",
        "VALUE_ROLES",
        "HOST_FACTS", "BASELINE_ANCHORS", "CHANGE_FORMS", "INPUT_ROLES",
        "INDUSTRY_CLASSES", "ESTIMATORS", "ROBUSTNESS", "CLOCKS",
        # Bank vocabulary rather than strategy vocabulary: a strategy never
        # declares a window, it reads the robustness that follows from one.
        # The estimators table above already renders that column, and the
        # declaration itself is documented in config/metric-bank.yaml where
        # the person writing one is looking.
        "WINDOW_STATISTICS",
        # Flattened into the vocabulary list rather than a table of their own.
        "VALUE_TYPES", "SIZE_UNITS", "EVIDENCE_UNITS", "OUTCOMES",
        "GROUP_REQUIREMENTS", "CONFIRMATIONS",
        # Prose, not a table: the sentence is quoted where the split is
        # explained, and pinning it here would pin a paragraph.
        "SPLIT_TEST",
        # Not vocabulary an author declares — it is read off RENDER_TYPES,
        # whose generated table already carries the `exits` column that
        # produces it. A block of its own would restate that column, which
        # is the failure this whole file exists against.
        "EXIT_RENDERS",
    }

    def test_no_host_owned_vocabulary_is_undocumented(self):
        exported = {name for name in dir(contract)
                    if name.isupper() and not name.startswith("_")
                    and name not in ("CONTRACT_VERSION", "MAX_STATES",
                                     "MAX_CONSEQUENCE",
                                     "BREAKDOWN_OBSERVATIONS",
                                     "PASS", "FAIL", "UNKNOWN", "NOTED",
                                     "CLEAR", "BREACHED", "CONFIRMED",
                                     "UNREADABLE")}
        assert exported == self.DOCUMENTED, (
            "engine/contract.py exports vocabulary this document does not "
            "cover. Add a generated block for it, or add it to DOCUMENTED "
            "with a comment saying where it is covered instead.")

    def test_the_bare_numbers_are_in_the_document(self, doc):
        assert f"`{contract.CONTRACT_VERSION}`" in doc
        assert f"`{contract.MAX_STATES}`" in doc
        assert f"`{contract.MAX_CONSEQUENCE}`" in doc


class TestTheDocumentPointsAtThingsThatExist:
    def test_every_repository_path_it_names_is_there(self, doc):
        root = ref.DOC.resolve().parent.parent
        named = set(re.findall(
            r"`((?:engine|tools|strategies|docs|tests)/[A-Za-z0-9_./-]+)`",
            doc))
        assert named, "the reference names no files, which cannot be right"
        missing = sorted(p for p in named if not (root / p).exists())
        assert missing == [], missing

    def test_the_worked_example_it_sends_people_to_is_the_bundle_that_loads(
            self, doc):
        """The reference tells an author to start with the example. If the
        two ever part company the first thing anybody writes is a copy of
        something that no longer works."""
        from engine import strategy_loader
        assert "docs/example-strategy/" in doc
        loaded, reports = strategy_loader.discover([ref.DOC.parent])
        assert "worked-example" in loaded, \
            [r["errors"] for r in reports if not r["ok"]]

    def test_the_command_it_tells_you_to_run_is_the_one_that_works(self, doc):
        assert "python -m tools.contract_reference" in doc
        assert ref.main(["--check"]) == 0
