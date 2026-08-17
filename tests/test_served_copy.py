"""The copy a reader gets, scanned where it is declared and served.

Three findings in two branches were the same shape: a sentence declared in
one place describing a mechanism that lived in another, with nothing joining
them — wrong copy reaching the reader verbatim because the view rightly
refuses to rewrite recorded words. The view harness scans the view's own
copy; this is the same move over the strategies' declared prose and the
engine sentences a reader is served.

Two kinds of check. The banned-word scan catches vocabulary the brief
retired ("thesis" is "Why I own this" to a reader) and framing it bans (the
tool never phrases anything as owed to it). The pairing pin is the harder
one: copy that names a counting mechanism — "waiting on the next filings" —
is held against the bank's own clock for the measures it describes, so a
strategy that moves an exit to trading days goes red here instead of
shipping a sentence that stopped being true.
"""

import importlib.util
from pathlib import Path

import pytest

from engine import bank, contract, portfolio, strategy_loader
from engine import thesis as thesis_mod

# Words and framings a reader must never be served. Identifiers, ids and
# file paths are not scanned — only declared prose.
BANNED = ("thesis", "falsifier", "provenance", "nothing is owed",
          "owed from you", "need a look", "nothing needs you")


@pytest.fixture(scope="module")
def shipped():
    strategies, reports = strategy_loader.discover()
    assert strategies, [r["errors"] for r in reports]
    return strategies


def _prose_of(record):
    """Every declared sentence a reader can be served, labelled."""
    out = []
    for s in record.get("states", []):
        for key in ("name", "description", "consequence"):
            if s.get(key):
                out.append((f'{record["id"]} state {s["id"]}.{key}', s[key]))
    for kind in ("values", "inputs"):
        for f in record.get(kind, []) or []:
            for key in ("label", "explain"):
                if f.get(key):
                    out.append((f'{record["id"]} {kind[:-1]} '
                                f'{f["id"]}.{key}', f[key]))
    for l in record.get("limits", []) or []:
        out.append((f'{record["id"]} limit', f'{l.get("title", "")} '
                    f'{l.get("body", "")}'))
    if record.get("audience"):
        out.append((f'{record["id"]} audience', record["audience"]))
    if record.get("summary"):
        out.append((f'{record["id"]} summary', record["summary"]))
    return out


class TestDeclaredStrategyProse:
    def test_no_banned_word_reaches_a_reader(self, shipped):
        for record in shipped.values():
            for where, text in _prose_of(record):
                low = " ".join(str(text).lower().split())
                for word in BANNED:
                    assert word not in low, (where, word)


class TestEngineSentences:
    def test_the_offered_exit_reasons_speak_the_interface_words(self):
        for reason in portfolio.EXIT_REASONS + [portfolio.UNSTATED_REASON]:
            low = reason.lower()
            for word in BANNED:
                assert word not in low, reason

    def test_the_record_absence_sentences_do_too(self):
        """The module's field names say "thesis"; its sentences must not.
        A reason the engine serves is a sentence the reader gets verbatim."""
        served = [
            thesis_mod._NOTHING_TO_RECORD,
            thesis_mod._AMENDMENT_NEEDS_A_REASON,
            thesis_mod._BELONGS_TO_AN_EARLIER_HOLDING,
            thesis_mod.standing({}, today="2026-01-01")["reason"],
        ]
        for text in served:
            low = " ".join(str(text).lower().split())
            for word in BANNED:
                assert word not in low, text


def _module_of(record):
    spec = importlib.util.spec_from_file_location(
        f'copy_scan_{record["id"]}', Path(record["dir"]) / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _counting_nouns(measure_ids):
    """What the bank says each measure's confirmation counts — the same
    resolution the host's own waiting sentences read."""
    return {contract.estimator_of(m)["counts"] for m in measure_ids
            if contract.estimator_of(m)}


class TestTheWaitCopyMatchesTheClock:
    """One reading past the line says what the wait counts. Graham and
    Lynch moved exits to trading days and their descriptions kept saying
    "filings" — found by reading, unfindable from code. This joins the
    sentence to the bank's own clock for the strategy's exit measures, so
    the next such move goes red here instead of shipping."""

    def _wait_copy(self, record):
        state = next(s for s in record["states"]
                     if s["id"] == "one-reading-past")
        return (" ".join(str(state.get("description", "")).split())
                + " " + str(state.get("consequence", ""))).lower()

    def test_buffett_may_say_filings_because_every_exit_counts_them(
            self, shipped):
        mod = _module_of(shipped["buffett"])
        exits = {row[0] for row in mod.EXITS}
        assert _counting_nouns(exits) == {"filings"}, \
            "an exit stopped counting filings — the wait copy must move too"
        assert "filings" in self._wait_copy(shipped["buffett"])

    def test_graham_says_readings_because_its_exits_count_two_things(
            self, shipped):
        mod = _module_of(shipped["graham"])
        exits = {row[0] for row in mod.EXITS_SAFETY} \
            | {row[0] for row in mod.EXITS_DISCOUNT}
        nouns = _counting_nouns(exits)
        assert len(nouns) > 1, \
            "the exits now count one thing — the wait copy may name it"
        copy = self._wait_copy(shipped["graham"])
        assert "readings" in copy
        assert "next filings" not in copy

    def test_lynch_says_readings_for_the_same_reason(self, shipped):
        mod = _module_of(shipped["lynch"])
        exits = {row[0] for row in mod.EXITS}
        nouns = _counting_nouns(exits)
        assert len(nouns) > 1, \
            "the exits now count one thing — the wait copy may name it"
        copy = self._wait_copy(shipped["lynch"])
        assert "readings" in copy
        assert "next filings say" not in copy


class TestReadsDeclarationsMatchTheTables:
    """Each strategy derives `reads` from its own tables, and the host
    refuses a citation outside it — so the declaration cannot drift ahead.
    What nothing above guarantees is the reverse: an entry in `reads` that
    nothing cites is a declaration nothing reads. Held loosely (the tables
    are the source, so the derived list is exact by construction); what is
    pinned is that every declared id is a real bank entry."""

    def test_every_declared_read_is_a_bank_entry(self, shipped):
        known = set(bank.meta())
        for record in shipped.values():
            reads = record.get("reads")
            assert reads, f'{record["id"]} declares no reads'
            stray = set(reads) - known
            assert not stray, (record["id"], sorted(stray))

    def test_the_qualitative_questions_are_declared_where_asked(self,
                                                                shipped):
        qualitative = {eid for eid, m in bank.meta().items()
                       if m.get("kind") == "qualitative"}
        assert set(shipped["buffett"]["reads"]) >= qualitative
