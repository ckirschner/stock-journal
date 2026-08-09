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
