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
