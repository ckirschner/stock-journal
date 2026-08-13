"""The metric bank: what ships, and the gloss that has to ship with it.

The failure this file exists to prevent is a bank that grows a measure with
no plain-language explanation. Nothing crashes; the measure simply appears on
screen as a bare number, in a program whose entire premise is that a
non-expert can find out what a number means without leaving the page. A
missing explanation is incomplete, not a follow-up ticket, and prose saying
so decays where a failing test does not.
"""

import pytest

from engine import bank


class TestShippedContent:
    def test_every_measure_has_a_label_and_a_plain_explanation(self):
        missing = []
        for e in bank.load_bank().get("entries") or []:
            eid = str(e.get("id"))
            plain = ((e.get("explanation") or {}).get("plain") or "")
            if not str(e.get("label") or "").strip():
                missing.append(f"{eid}: no label")
            if not str(plain).strip():
                missing.append(f"{eid}: no plain-language explanation")
        assert missing == [], missing

    def test_every_measure_says_how_it_is_derived_or_what_it_asks(self):
        """A computed measure carries its formula; a qualitative one carries
        the question the user is answering. One or the other, always —
        otherwise the screen can show a value it cannot account for."""
        missing = []
        for e in bank.load_bank().get("entries") or []:
            if not (e.get("derivation") or e.get("question")):
                missing.append(str(e.get("id")))
        assert missing == [], missing

    def test_no_two_measures_share_an_id(self):
        """bank_index keys a dict, so a duplicate silently loses one entry
        and every strategy citing it reads the wrong definition."""
        ids = [str(e.get("id")) for e in bank.load_bank().get("entries") or []]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        assert dupes == []
        assert len(bank.bank_index(bank.load_bank())) == len(ids)

    def test_no_thresholds_live_in_the_bank(self):
        """The bank says what a value IS. Every level belongs to a strategy,
        because the same host serves strategies that contradict each other."""
        forbidden = {"buy", "sell", "flag", "tier", "threshold", "min_green",
                     "requires"}
        offenders = []
        for e in bank.load_bank().get("entries") or []:
            hit = forbidden & set(e)
            if hit:
                offenders.append((str(e.get("id")), sorted(hit)))
        assert offenders == []


class TestMeta:
    def test_meta_carries_what_a_screen_needs_to_render_a_measure(self):
        meta = bank.meta()
        assert meta, "the bank produced no measures"
        for eid, m in meta.items():
            assert set(m) == {"label", "unit", "format", "kind", "polarity",
                              "plain"}, eid

    def test_nothing_framework_shaped_crosses_the_boundary(self):
        """The engine hands plain data over, always. A ruamel scalar reaching
        the UI serialises in ways nothing downstream expects."""
        for m in bank.meta().values():
            for v in m.values():
                assert v is None or type(v) in (str, int, float, bool), v

    def test_a_bank_that_does_not_declare_its_schema_is_refused(self,
                                                                tmp_path,
                                                                monkeypatch):
        (tmp_path / "impostor.yaml").write_text("entries: []\n",
                                                encoding="utf-8")
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        with pytest.raises(ValueError):
            bank.load_bank("impostor")

    def test_a_missing_bank_is_a_named_absence_not_an_empty_one(self,
                                                               tmp_path,
                                                               monkeypatch):
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        with pytest.raises(FileNotFoundError):
            bank.load_bank("nothing-here")


class TestWhatAnswersAMeasureAndHowItRenders:
    """`kind`, `unit` and `format` decide what a reader is shown, and none of
    the three was read at load.

    `estimator.kind` beside them was checked by name, which is what made the
    gap visible: one word in an entry refused a typo and the word next to it
    accepted anything. A mistyped `kind` moves an entry between two surfaces —
    a formula in engine/compute.py, or a question the user answers — and the
    measure comes back "this host has no computation for it", which is an
    absence pointing at a missing formula for a question nobody was asked.

    The unit half is the same failure one column over. The bank's own header
    states that a qualitative entry carries a pass or a fail, and nothing read
    it: a fourth judgement declaring `unit: percent` would render a moat
    assessment as "100.0%", and a `format` over a yes/no prints a 1.
    """

    def entry(self, eid, **over):
        import copy
        idx = {e["id"]: e for e in bank.to_plain(bank.load_bank())["entries"]}
        e = copy.deepcopy(idx[eid])
        e.update(over)
        return e

    def test_the_shipped_bank_passes_its_own_check(self):
        """The control, and the reason the rest of this class means
        anything."""
        assert [p for e in bank.load_bank()["entries"]
                for p in bank._check_rendering(e)] == []

    def test_a_kind_this_host_has_no_surface_for_is_refused(self):
        out = bank._check_rendering(self.entry("pe_ttm", kind="computd"))
        assert out and "not one of computed, qualitative" in out[0]

    def test_a_judgement_declared_computed_is_refused(self):
        """The pairing, and the whole reason `kind` needs no separate list to
        be checked against: `qualitative` and `estimator: assessed` are one
        fact said twice, so either one alone is a contradiction the file can
        see."""
        out = bank._check_rendering(
            self.entry("moat_durability", kind="computed"))
        assert out and "read by a \"assessed\" estimator" in out[0]

    def test_a_computed_measure_declared_qualitative_is_refused(self):
        out = bank._check_rendering(self.entry("pe_ttm", kind="qualitative"))
        assert out and "`qualitative`" in out[0]

    def test_the_estimators_a_computed_measure_may_use_are_not_a_second_list(
            self):
        """Derived from engine/contract.ESTIMATORS with `assessed` reserved,
        so a kind added to the host is usable without being written down here
        as well. A copy of that list is the thing this check exists against."""
        from engine import contract
        assert bank._reads("computed") | {"assessed"} == set(
            contract.ESTIMATORS)
        assert bank._reads("qualitative") == {"assessed"}

    def test_an_entry_with_no_unit_is_refused(self):
        out = bank._check_rendering(self.entry("pe_ttm", unit=None))
        assert out and "declares no `unit`" in out[0]

    def test_a_unit_the_host_cannot_render_is_refused(self):
        out = bank._check_rendering(self.entry("pe_ttm", unit="furlongs"))
        assert out and "host change in engine/contract.py" in out[0]

    def test_a_judgement_carrying_anything_but_a_mark_is_refused(self):
        out = bank._check_rendering(
            self.entry("moat_durability", unit="percent"))
        assert out and "unit `yes_no`" in out[0]

    def test_a_format_over_a_yes_no_is_refused(self):
        """Not decoration. A boolean run through "0.0%" prints 1 — a moat
        read rendering as a hundred per cent of something."""
        out = bank._check_rendering(
            self.entry("moat_durability", format="0.0%"))
        assert out and "prints a 1" in out[0]

    def test_the_unit_a_mark_renders_in_is_named_where_it_is_made_true(self):
        """engine/judgements._AS_VALUE turns a mark into a boolean, so that
        module owns the word — and the bank refuses against it rather than
        against a copy."""
        from engine import judgements
        assert judgements.UNIT == "yes_no"
        assert set(judgements._AS_VALUE.values()) == {True, False}
        for e in bank.load_bank()["entries"]:
            if str(e.get("kind")) == "qualitative":
                assert str(e.get("unit")) == judgements.UNIT


class TestTheBankSaysWhatChangedWhenItChanges:
    """A measure definition is a rule, and this is the half of that claim the
    bank itself has to carry.

    Editing a formula here changes what every exit in every journal demands,
    exactly as editing a threshold in a strategy does — and the strategy had a
    version, a changelog, and a loader that refused a version saying nothing.
    The bank had none of it. What that cost was not that a change went
    unrecorded: a journal stamps the definitions and catches an edit either
    way. It was that there was no way to tell an author's release from
    somebody's edit in place, and therefore no way to know who was owed the
    sentence explaining it.
    """

    def _write(self, tmp_path, monkeypatch, text):
        (tmp_path / "probe.yaml").write_text(
            "schema: ledger.metric-bank/1\n" + text, encoding="utf-8")
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        bank._definitions_cache.clear()

    def test_a_bank_with_no_version_is_refused(self, tmp_path, monkeypatch):
        self._write(tmp_path, monkeypatch, "entries: []\n")
        with pytest.raises(ValueError, match="`version` must be a whole "
                                             "number"):
            bank.load_bank("probe")

    def test_a_version_that_does_not_say_what_changed_is_refused(
            self, tmp_path, monkeypatch):
        """The whole point of the number. A release that says nothing is a
        release a journal cannot quote, which leaves it recording that the
        measures moved and unable to say why — the exact hole the strategy
        contract already refuses to leave open."""
        self._write(tmp_path, monkeypatch,
                    "version: 2\nchangelog:\n  1: first\nentries: []\n")
        with pytest.raises(ValueError, match="version 2 has no changelog"):
            bank.load_bank("probe")

    def test_a_changelog_entry_with_no_sentence_is_refused(self, tmp_path,
                                                           monkeypatch):
        self._write(tmp_path, monkeypatch,
                    "version: 1\nchangelog:\n  1: '   '\nentries: []\n")
        with pytest.raises(ValueError, match="non-empty text"):
            bank.load_bank("probe")

    def test_the_shipped_bank_passes_its_own_release_check(self):
        """The control, and the reason the rest of this class means
        anything."""
        assert bank._check_release(bank.load_bank()) == []
        assert bank.definitions()["version"] in bank.changelog()


class TestEveryFieldOfAMeasureHasBeenDecidedAbout:
    """The failure this prevents is the quiet one: somebody adds a key to an
    entry — a second window, a switch the formula reads — and it reaches every
    journal's verdicts while sitting on no record, because the code that
    builds a definition simply never looked at it.

    A list of what IS recorded cannot catch that. Only a list of everything,
    checked against what the file actually carries, can.
    """

    def _keys(self):
        return {str(k) for e in bank.load_bank()["entries"] for k in e}

    def test_every_key_a_shipped_entry_carries_has_been_placed(self):
        unplaced = sorted(self._keys() - set(bank.ACCOUNTED_FOR))
        assert unplaced == [], (
            f"{unplaced} reach a verdict and no journal would record them "
            "moving. Add each to bank.ACCOUNTED_FOR, saying where a change to "
            "it lands — on the record under a name, or nowhere and why.")

    def test_nothing_is_accounted_for_that_no_entry_carries(self):
        """A sentence about a field that no longer exists is a sentence
        nobody can check, and it reads as coverage."""
        stale = sorted(set(bank.ACCOUNTED_FOR) - self._keys()
                       - {"parameters"})
        assert stale == [], stale

    def test_the_two_halves_say_different_kinds_of_thing(self):
        """`states` carries values a reader can act on; `restates` carries
        fingerprints of arithmetic nobody can read back. Mixing them is how a
        record comes to claim it knows what a changed formula now demands."""
        d = bank.definitions()["entries"]["roic_median_5y"]
        assert d["states"]["observations read"] == 5
        assert d["states"]["does not describe"] == [
            "depository-lending", "insurance", "real-estate"]
        assert set(d["restates"]) == {
            "how it is worked out", "what the formula refuses on",
            "what nothing here can settle", "the question you answer"}
        assert all(isinstance(v, str) and len(v) == 12
                   for v in d["restates"].values())

    def test_re_wrapping_a_formula_is_not_a_change_to_what_it_demands(self):
        """A digest over whitespace would report a column being re-flowed to
        every journal as a change to what an exit demands, which is how a
        record fills with things nobody was worried about."""
        assert bank._digest("a  b\n c") == bank._digest("a b c")
        assert bank._digest("a b") != bank._digest("a c")

    def test_a_prose_edit_moves_nothing_and_an_arithmetic_edit_does(self):
        """The line this record draws, on one entry, both ways."""
        import copy
        e = copy.deepcopy(bank.to_plain(
            bank.bank_index(bank.load_bank())["roic_median_5y"]))
        before = bank._definition(e)
        e["explanation"]["plain"] = "Something else entirely."
        assert bank._definition(e) == before
        e["derivation"]["formula"] = "value = 1"
        assert bank._definition(e)["restates"][
            "how it is worked out"] != before["restates"][
            "how it is worked out"]


class TestEveryRecordedFieldComesFromSomewhere:
    """The other half of the pairing above, and the failure it prevents is the
    inverse one: a field is named on the record, and nothing under it is
    actually read — so a measure's definition moves and the record says
    nothing, in the one place that looks like it is watched.

    Asserted against one entry carrying every key an entry can carry, so the
    table below has to grow when the definition does, and cannot quietly stop
    covering something.
    """

    def entry(self):
        return {
            "id": "probe", "kind": "computed", "label": "Probe",
            "unit": "percent", "format": "0.0%",
            "polarity": "higher_is_better",
            "estimator": {"kind": "median", "observations": 5,
                          "window": {"statistic": "averaged",
                                     "observations": 3}},
            "inputs": {"filings": ["revenue"], "prices": [],
                       "entries": ["fcf_ttm"]},
            "parameters": [{"id": "discount_rate", "unit": "percent"}],
            "derivation": {"formula": "value = 1", "window": "one year"},
            "question": "Does it hold?",
            "response": {"prose": "required", "marks": ["pass", "fail"],
                         "unmarked": "unassessed"},
            "not_meaningful_when": [
                {"industry": ["insurance"], "because": "they do not"},
                {"data": "revenue is negative", "because": "it inverts"},
                {"undetected": "a captive finance arm",
                 "needs": "segment data", "because": "nothing can tell"}],
            "explanation": {"plain": "p", "misfires": "m",
                            "attribution": "a"},
            "polarity_note": "n",
        }

    # What each recorded field is read from. One row per field, so a field
    # added to a definition with nothing under it fails here rather than
    # reaching a journal as a name that never moves.
    MOVES = {
        "name": lambda e: e.update(label="Renamed"),
        "answered by": lambda e: e.update(kind="qualitative"),
        "unit": lambda e: e.update(unit="ratio"),
        "format": lambda e: e.update(format="0.00%"),
        "favourable direction": lambda e: e.update(polarity="none"),
        "how it is read": lambda e: e["estimator"].update(kind="averaged"),
        "observations read": lambda e: e["estimator"].update(observations=4),
        "judged against":
            lambda e: e["estimator"]["window"].update(statistic="median"),
        "observations judged against":
            lambda e: e["estimator"]["window"].update(observations=5),
        "built on": lambda e: e["inputs"].update(entries=["pe_ttm"]),
        "parameters": lambda e: e["parameters"].append({"id": "rate"}),
        "does not describe":
            lambda e: e["not_meaningful_when"][0].update(
                industry=["insurance", "real-estate"]),
        "marks it accepts":
            lambda e: e["response"].update(marks=["pass", "fail", "maybe"]),
        "prose": lambda e: e["response"].update(prose="optional"),
        "unmarked reads as": lambda e: e["response"].update(unmarked="none"),
        "how it is worked out":
            lambda e: e["derivation"].update(formula="value = 2"),
        "what the formula refuses on":
            lambda e: e["not_meaningful_when"][1].update(data="revenue is 0"),
        "what nothing here can settle":
            lambda e: e["not_meaningful_when"][2].update(needs="a filing"),
        "the question you answer": lambda e: e.update(question="Does it?"),
    }

    def test_every_recorded_field_moves_when_its_source_moves(self):
        import copy
        before = bank._definition(self.entry())
        for field, break_it in self.MOVES.items():
            e = self.entry()
            break_it(e)
            after = bank._definition(e)
            half = "states" if field in before["states"] else "restates"
            assert after[half].get(field) != before[half].get(field), (
                f"{field} is on the record and nothing under it is read — a "
                "measure could move here and no journal would say so.")
            # and it is the ONLY thing that moved, so a field is not quietly
            # standing in for a neighbour
            moved = {k for h in ("states", "restates")
                     for k in set(before[h]) | set(after[h])
                     if before[h].get(k) != after[h].get(k)}
            assert moved == {field}, (field, moved)
        assert before == bank._definition(self.entry())  # nothing mutated

    def test_the_table_covers_every_field_a_definition_produces(self):
        d = bank._definition(self.entry())
        produced = set(d["states"]) | set(d["restates"])
        assert produced == set(self.MOVES), produced ^ set(self.MOVES)

    def test_prose_a_reader_reads_moves_nothing(self):
        """The stated line, checked rather than asserted in a comment."""
        for edit in (lambda e: e["explanation"].update(plain="rewritten"),
                     lambda e: e["explanation"].update(misfires="rewritten"),
                     lambda e: e["explanation"].update(attribution="someone"),
                     lambda e: e.update(polarity_note="rewritten"),
                     lambda e: e["inputs"].update(filings=["net income"]),
                     lambda e: e["not_meaningful_when"][0].update(
                         because="a different sentence")):
            e = self.entry()
            edit(e)
            assert bank._definition(e) == bank._definition(self.entry())


class TestWhichFieldsSurviveAComparison:
    """Whether a change to a field leaves two readings of the measure
    comparable is a claim about arithmetic, and it decides whether a rule that
    measures back to a purchase goes on working. Written out in full so that
    moving one is a decision somebody makes and argues for, rather than a
    line edited while doing something else.

    It is deliberately NOT the recording split. That one asks whether the host
    can state what moved; this one asks whether two readings are of the same
    thing, and the two cut the fields in different places — see the table in
    engine/bank.py.
    """

    # field -> whether a move in it leaves a frozen reading and a live one
    # comparable, with the reason where it is not obvious.
    COMPARES = {
        # A different window, a different statistic, a different formula, a
        # different unit, a different set of ingredients, a different surface
        # answering it: each one makes the two numbers answers to different
        # questions.
        "answered by": bank.INCOMPARABLE,
        "unit": bank.INCOMPARABLE,
        "how it is read": bank.INCOMPARABLE,
        "observations read": bank.INCOMPARABLE,
        "built on": bank.INCOMPARABLE,
        "parameters": bank.INCOMPARABLE,
        "marks it accepts": bank.INCOMPARABLE,
        "how it is worked out": bank.INCOMPARABLE,
        "the question you answer": bank.INCOMPARABLE,
        # What a measure is called, how it prints, which way is favourable,
        # and what a judgement asks of the reader beside its mark: none of
        # them is in the arithmetic.
        "name": bank.COMPARABLE,
        "format": bank.COMPARABLE,
        "favourable direction": bank.COMPARABLE,
        "prose": bank.COMPARABLE,
        "unmarked reads as": bank.COMPARABLE,
        # The window a reading is JUDGED against, which decides what a
        # leave-one-out re-read means — and a leave-one-out is worked out
        # live from today's filings, never against a frozen figure.
        "judged against": bank.COMPARABLE,
        "observations judged against": bank.COMPARABLE,
        # The three that decide WHEN a value is absent rather than what it is
        # when present. Either one side is absent already, or both were
        # worked out by the same arithmetic — there is no case where both are
        # present and differently derived.
        "does not describe": bank.COMPARABLE,
        "what the formula refuses on": bank.COMPARABLE,
        "what nothing here can settle": bank.COMPARABLE,
    }

    def test_every_field_says_whether_it_survives_a_comparison(self):
        declared = {field: compares for field, _, _, compares in bank._FIELDS}
        assert declared == self.COMPARES

    def test_the_narrow_list_is_the_one_that_is_written_down(self):
        """Fail closed. A field added to the table and not thought about is
        treated as breaking a comparison, which shows up as a drift figure
        saying why it cannot be worked out — noticed. The other default
        subtracts two different measures and is not."""
        assert bank.COMPARABLE_FIELDS == {
            f for f, c in self.COMPARES.items() if c == bank.COMPARABLE}
        assert "a field from some later build" not in bank.COMPARABLE_FIELDS

    def test_the_two_splits_are_not_the_same_split(self):
        """If they were, the gate could have reused the recording one — and
        it would have missed the case that put it there. Asserted in both
        directions, because either overlap would mean one of the two tables
        is answering the other's question."""
        recorded = {field: half for field, _, half, _ in bank._FIELDS}
        stated_but_incomparable = {
            f for f, half in recorded.items()
            if half == bank.STATED and f not in bank.COMPARABLE_FIELDS}
        restated_but_comparable = {
            f for f, half in recorded.items()
            if half == bank.RESTATED and f in bank.COMPARABLE_FIELDS}
        assert "observations read" in stated_but_incomparable
        assert "what the formula refuses on" in restated_but_comparable
