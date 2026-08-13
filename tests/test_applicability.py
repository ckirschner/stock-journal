"""A measure that cannot describe this filer refuses, on its own terms.

The failure this file exists to prevent is the one the bank documented for as
long as it existed and nothing ever read. `roic_median_5y` and
`altman_z_score` both said "the company is a bank or an insurer" in prose,
flagged untestable, and every one of these computed anyway: a lender's debt
against equity read 1.4x while its assets were seven times its equity, because
deposits are not tagged as debt; its accruals ratio came out near zero because
the denominator is the loan book; and had capital expenditure resolved, its
owner-earnings yield would have read around 36% against a 5% floor. Every one
of those is a confident number in the passing direction.

Three guarantees are pinned here, and each is structural rather than
procedural:

1. The condition is a declared key the host evaluates, not prose. Prose that
   names a kind of company is refused at load, so the failure above cannot be
   re-created by writing a sentence.
2. The refusal happens BEFORE the formula runs, in the one place every
   reading passes through — live, reconstructed, and per filing alike. An
   author cannot forget it at the top of a function because there is no
   function to forget it in.
3. A measure built on a refused measure is refused at least as widely, checked
   at load. Nobody adding a gate to a leaf measure has to go and find the four
   entries that consume it.

And the state is kept apart from absence everywhere it travels. `absent` says
go and look; this says these accounts were never what the measure describes.
Rendering the second as the first would put a permanent item in the list of
things to go and do, which is how that list stops being read.
"""

import ast
import pathlib

import pytest
from conftest import (balance_face, dur, filer, filing, inst, journal_for,
                      symbols,
                      no_filer)

from engine import (bank, compute, context, contract, dataview, facts_store,
                    industry, strategy_loader)

DEPOSIT, INSURE, PROPERTY = ("depository-lending", "insurance", "real-estate")

# Codes, from the SEC's published list. 6022 is a state commercial bank, 6798
# a real estate investment trust, 6199 the code the host cannot classify
# (American Express and Synchrony file under it, and so do payment
# processors), and 7372 prepackaged software — an ordinary operating business.
BANK_SIC, REIT_SIC, AMBIGUOUS_SIC, ORDINARY_SIC = "6022", "6798", "6199", "7372"


def _filings():
    """Two fiscal years of a company that computes something, with no view
    about what kind of company it is. The figures are invented."""
    out = []
    for year, (fy_start, fy_end, filed) in enumerate((
            ("2023-01-01", "2023-12-31", "2024-02-20"),
            ("2024-01-01", "2024-12-31", "2025-02-20"))):
        out.append(filing(f"A-{year}", "10-K", filed, fy_end, [
            dur("us-gaap:Revenues", fy_start, fy_end, 1000.0),
            dur("us-gaap:NetIncomeLoss", fy_start, fy_end, 120.0),
        ] + balance_face(fy_end, assets=2000.0, extra=[
            inst("us-gaap:AssetsCurrent", fy_end, 600.0),
            inst("us-gaap:LiabilitiesCurrent", fy_end, 300.0),
            inst("us-gaap:LongTermDebtNoncurrent", fy_end, 400.0),
            inst("us-gaap:StockholdersEquity", fy_end, 800.0),
        ])))
    return out


@pytest.fixture
def company():
    """A stored filer whose class the test chooses. Returns a setter."""
    cik = 4242

    def make(sic, description="", observed=None):
        for f in _filings():
            f["cik"] = cik
            facts_store.save_filing(cik, f)
        filer(cik, "A company", sic, description, observed=observed)
        dataview.invalidate(cik)
        return cik
    return make


def results(cik, ids, as_of=None):
    if as_of:
        return dataview.asof_results(cik, ["TEST"], ids, as_of)
    return dataview.computed_results(cik, ["TEST"], ids)


# ---------------------------------------------------------------------------
# the declaration
# ---------------------------------------------------------------------------

class TestTheConditionIsDeclaredAndNotProse:
    """The whole point of the change. A condition the host evaluates is a key
    with a closed vocabulary; a condition nothing evaluates cannot be written
    in the place that looks like it is evaluated."""

    def _bank(self, tmp_path, entries):
        path = tmp_path / "probe.yaml"
        import io

        from ruamel.yaml import YAML
        y = YAML()
        buf = io.StringIO()
        y.dump({"schema": "ledger.metric-bank/1", "version": 1,
                "changelog": {1: "The first release of this probe."},
                "entries": entries}, buf)
        path.write_text(buf.getvalue(), encoding="utf-8")
        return path

    def _entry(self, eid="probe", nmw=None, inputs=None):
        e = {"id": eid, "kind": "computed",
             "estimator": {"kind": "instant"},
             "label": "Probe", "unit": "ratio",
             "inputs": {"filings": [], "prices": [], "entries": inputs or []}}
        if nmw is not None:
            e["not_meaningful_when"] = nmw
        return e

    def _load(self, tmp_path, entries, monkeypatch):
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        self._bank(tmp_path, entries)
        return bank.load_bank("probe")

    def test_a_well_formed_industry_condition_loads(self, tmp_path,
                                                    monkeypatch):
        doc = self._load(tmp_path, [self._entry(nmw=[
            {"industry": [DEPOSIT], "because": "a reason"}])], monkeypatch)
        assert doc["entries"][0]["not_meaningful_when"][0]["industry"] \
            == [DEPOSIT]

    def test_the_old_prose_shape_is_refused(self, tmp_path, monkeypatch):
        """`test:` is what every condition used to be, and what nothing ever
        read. It is not accepted with a warning; the file does not load."""
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[
                {"test": "the company is a bank", "because": "x"}])],
                monkeypatch)
        assert "found test" in str(e.value)

    def test_a_class_the_host_does_not_name_is_refused(self, tmp_path,
                                                       monkeypatch):
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[
                {"industry": ["conglomerates"], "because": "x"}])],
                monkeypatch)
        assert "conglomerates" in str(e.value)

    def test_a_condition_with_no_reason_is_refused(self, tmp_path,
                                                   monkeypatch):
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[
                {"industry": [DEPOSIT]}])], monkeypatch)
        assert "because" in str(e.value)

    def test_both_forms_at_once_is_refused(self, tmp_path, monkeypatch):
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[
                {"industry": [DEPOSIT], "data": "x", "because": "y"}])],
                monkeypatch)
        assert "Never two of them" in str(e.value)

    def test_the_same_class_twice_is_refused(self, tmp_path, monkeypatch):
        """Two reasons for one class means one of them is never shown."""
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[
                {"industry": [DEPOSIT], "because": "one"},
                {"industry": [DEPOSIT, INSURE], "because": "two"}])],
                monkeypatch)
        assert "already declared" in str(e.value)

    def test_an_empty_list_is_refused_rather_than_ignored(self, tmp_path,
                                                          monkeypatch):
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[])], monkeypatch)
        assert "non-empty" in str(e.value)

    def test_a_data_condition_naming_a_kind_of_company_is_refused(
            self, tmp_path, monkeypatch):
        """The hole this would leave is the one the change closes. `data` is
        prose the formula owns and nothing here checks; a kind of company
        written into it is the old bug with a new key."""
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[
                {"data": "the company is a bank or an insurer",
                 "because": "x"}])], monkeypatch)
        assert "names a kind of company" in str(e.value)

    def test_every_class_the_host_names_is_reachable_from_that_check(self):
        """The check above works off a written-out list of nouns, so a class
        added to the host later could slip past it silently. This is what
        stops that: every class the host names has to be nameable in prose
        the check would catch."""
        missed = [cid for cid, spec in contract.INDUSTRY_CLASSES.items()
                  if not any(bank._names_a_kind(spec["noun"].lower(), w)
                             for w in bank._CLASSIFIABLE_WORDS)]
        assert missed == [], missed

    def test_a_data_condition_that_merely_reads_like_one_is_not_refused(
            self, tmp_path, monkeypatch):
        """Whole words only. "blank" contains "bank"."""
        self._load(tmp_path, [self._entry(nmw=[
            {"data": "the filer reports a blank cover page",
             "because": "x"}])], monkeypatch)

    def test_an_undetected_condition_must_say_what_would_settle_it(
            self, tmp_path, monkeypatch):
        """A gap with no sentence about closing it is a shrug."""
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [self._entry(nmw=[
                {"undetected": "the company has a captive finance arm",
                 "because": "x"}])], monkeypatch)
        assert "needs" in str(e.value)
        self._load(tmp_path, [self._entry(nmw=[
            {"undetected": "the company has a captive finance arm",
             "because": "x", "needs": "segment facts nobody reads"}])],
            monkeypatch)

    def test_an_entry_built_on_a_gated_entry_must_be_gated_too(
            self, tmp_path, monkeypatch):
        """The check nobody performs by hand on the day they add the
        fifty-ninth measure."""
        leaf = self._entry("leaf", nmw=[{"industry": [DEPOSIT],
                                         "because": "a reason"}])
        with pytest.raises(ValueError) as e:
            self._load(tmp_path, [leaf, self._entry("built", inputs=["leaf"])],
                       monkeypatch)
        assert "built is built on leaf" in str(e.value)
        # Declaring it is what makes it load. Declaring MORE is fine — an
        # entry may be out of scope for a class its ingredients handle.
        self._load(tmp_path, [leaf, self._entry(
            "built", nmw=[{"industry": [DEPOSIT, INSURE],
                           "because": "its own reason"}],
            inputs=["leaf"])], monkeypatch)


class TestTheShippedBankSaysWhatItMeans:
    def test_it_loads(self):
        assert bank.load_bank()["entries"]

    def test_no_condition_is_left_in_the_old_prose_shape(self):
        """Belt and braces against the loader being weakened later: the
        shipped file itself carries no `test:` anywhere."""
        stale = [e["id"] for e in bank.load_bank()["entries"]
                 for item in (e.get("not_meaningful_when") or [])
                 if "test" in item]
        assert stale == [], stale

    def test_the_measures_the_report_named_are_all_gated_for_a_lender(self):
        """The five the commissioning report measured on a real lender. Each
        one computed a confident number in the passing direction."""
        gated = bank.applicability()

        def classes(eid):
            return {c for cs, _ in gated.get(eid, []) for c in cs}
        for eid in ("debt_to_equity", "accruals_ratio",
                    "goodwill_intangibles_to_assets", "owner_earnings_yield",
                    "altman_z_score"):
            assert DEPOSIT in classes(eid), eid

    def test_every_class_refusal_explains_itself_to_a_non_expert(self):
        """A refusal a reader cannot understand teaches them the tool is
        broken, and "this measure does not apply to banks" is that refusal.
        Asked of the class conditions only: a formula guard says a fact about
        arithmetic ("negative working capital makes the ratio undefined") and
        needs a sentence, where a whole kind of company needs a paragraph."""
        thin = [(e["id"], str(item.get("because") or "")[:40])
                for e in bank.load_bank()["entries"]
                for item in (e.get("not_meaningful_when") or [])
                if (item.get("industry") or item.get("undetected"))
                and len(str(item.get("because") or "").split()) < 25]
        assert thin == [], thin

    def test_the_view_resolves_class_ids_into_what_they_are_called(self):
        """The screen renders labels, and the labels are the host's. A view
        holding its own table of them is a table that drifts."""
        named = [item for e in bank.bank_view()["entries"]
                 for item in (e.get("not_meaningful_when") or [])
                 if item.get("industry")]
        assert named
        for item in named:
            for c in item["industry"]:
                assert c["label"] == contract.INDUSTRY_CLASSES[c["id"]][
                    "label"]

    def test_every_form_the_loader_accepts_arrives_with_its_sentence(self):
        """The word and what it means to a reader are one object.

        They were two. The loader accepted three forms and the Metrics page
        held a two-way branch, so `undetected` — the form where nothing
        refuses and nothing can — rendered as "refused by the calculation
        itself, from the figures", with its own text blank beside it. A
        reader was told the program had checked something it cannot check.

        This is the pairing, and it cannot grow quietly: a fourth form added
        to `_NMW_FORMS` without a sentence fails here, and one added anywhere
        else is not a form the loader accepts."""
        forms = {f for e in bank.bank_view()["entries"]
                 for item in (e.get("not_meaningful_when") or [])
                 if (f := item["form"]["id"])}
        assert forms == set(bank._NMW_FORMS), (
            "the shipped bank does not exercise every form the loader "
            "accepts, so one of them renders untested")
        for item in (i for e in bank.bank_view()["entries"]
                     for i in (e.get("not_meaningful_when") or [])):
            means = item["form"]["means"]
            assert len(means.split()) >= 8, item

    def test_a_condition_carries_its_own_text_where_the_host_cannot_settle_it(
            self):
        """An industry condition renders from its class list; the other two
        render their own prose, and it has to survive the trip. `t.data` was
        read on an undetected item, which is undefined — so the sentence
        saying what the reader should go and check rendered as nothing."""
        for e in bank.bank_view()["entries"]:
            for item in (e.get("not_meaningful_when") or []):
                if item["form"]["id"] == "industry":
                    assert item["industry"]
                else:
                    assert item["states"].strip(), (e["id"], item)

    def test_only_an_undetected_condition_owes_anything(self):
        """`needs` is what it would take to settle a condition nobody can
        settle, and the view renders it wherever it appears. On a refused
        condition it would print a standing request against the host for a
        question the host already answers — so it is refused at load, for
        every form but the one it belongs to."""
        for e in bank.bank_view()["entries"]:
            for item in (e.get("not_meaningful_when") or []):
                if item["form"]["id"] == "undetected":
                    assert str(item.get("needs") or "").strip(), e["id"]
                else:
                    assert "needs" not in item, e["id"]


# ---------------------------------------------------------------------------
# the other form — the one the host cannot evaluate
# ---------------------------------------------------------------------------
#
# `industry` is settled before the formula runs, so the host can be made to
# perform it and is. `data` is a reading of the figures, so only the formula
# can — which left the declaration in one file and the enforcement in another
# with nothing joining them. Both directions of that join had failed:
#
#   declared, never performed    A payout ratio the bank itself calls
#                                uninterpretable was served with a caution
#                                beside it. A cash conversion divided through
#                                a loss. A ROIC gate switched itself off for
#                                exactly the filers it was written for.
#   performed, never declared    Two formulas refused citing "the bank's own
#                                test" for a test their entry does not state,
#                                so a reader following the sentence to the
#                                Metrics page found nothing there.
#
# The second direction is checkable and is checked, here and at run time. The
# first is not, and the honest reason is below.
# ---------------------------------------------------------------------------

def _cited_conditions():
    """Every (entry, condition) pair engine/compute.py refuses on, read out of
    the source rather than by running it.

    Statically, because the point is coverage: a branch nobody's filings
    reach is exactly the branch a test would not exercise, and it is where a
    refusal citing a test nobody declared would sit undisturbed. `condition`
    is always a literal at the call — that is what makes this readable, and
    it is why the helper takes the sentence rather than an id.

    Two shapes are collected. A formula refusing for itself names both; a
    formula refusing through a helper that serves several entries hands the
    pair down, and the pair is still a literal at the entry's own function.
    """
    tree = ast.parse(pathlib.Path(compute.__file__).read_text(
        encoding="utf-8"))

    def literals(call, where):
        out = []
        for i in where:
            if i >= len(call.args):
                return None
            try:
                got = ast.literal_eval(call.args[i])
            except Exception:                             # noqa: BLE001
                return None
            if not isinstance(got, str):
                return None
            out.append(" ".join(got.split()))
        return tuple(out)

    # A helper that hands two of its own parameters to not_meaningful passes
    # the question on rather than answering it, so the pair to read is at the
    # call one level out — where the entry it is being asked for is known.
    forwards = {"not_meaningful": (0, 1)}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        params = [a.arg for a in fn.args.args]
        for call in ast.walk(fn):
            if isinstance(call, ast.Call) \
                    and getattr(call.func, "id", None) == "not_meaningful" \
                    and len(call.args) >= 2:
                named = [getattr(a, "id", None) for a in call.args[:2]]
                if all(n in params for n in named):
                    forwards[fn.name] = tuple(params.index(n) for n in named)

    pairs = set()
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call):
            continue
        where = forwards.get(getattr(call.func, "id", None))
        if where is None:
            continue
        got = literals(call, where)
        if got:
            pairs.add(got)
    return pairs


# Conditions performed by machinery shared between several entries, where the
# refusal is built once and the entry it is being built for is not a literal
# anywhere — a compound-rate window, a gross margin, a component that came
# back absent. They are enforced; what they are not is checkable from here.
#
# This is a list and not a rule, and it is the honest shape of the thing: the
# declaration-to-enforcement direction cannot be proved, because "the formula
# refuses on this" is a statement about arithmetic and no signature carries
# it. What the list buys is that it cannot grow quietly — a condition added
# to the bank and performed nowhere fails this file, and the author is asked
# which of the two it is. It should shrink.
ENFORCED_BY_SHARED_MACHINERY = {
    # _cagr and _appeared_rather_than_grew, over four windows and two inputs
    ("revenue_cagr_5y", "mean revenue over the three base years is zero or negative"),
    ("revenue_cagr_5y", "fewer than eight fiscal years of revenue are available on one accounting basis"),
    ("revenue_cagr_3y", "mean revenue over the three base years is zero or negative"),
    ("revenue_cagr_3y", "fewer than six fiscal years of revenue are available on one accounting basis"),
    ("net_income_cagr_5y", "mean net income over the three base years is zero or negative"),
    ("net_income_cagr_5y", "fewer than eight fiscal years of net income are available on one accounting basis"),
    ("net_income_cagr_5y", "mean net income over the three base years is at most a tenth of the mean over the three end years, AND the base years' net margin is under half the end years'"),
    ("eps_cagr_5y", "mean diluted EPS over the three base years is zero or negative"),
    ("eps_cagr_5y", "fewer than eight fiscal years of diluted EPS are available on one accounting basis"),
    ("eps_cagr_5y", "mean net income over the three base years is at most a tenth of the mean over the three end years, AND the base years' net margin is under half the end years'"),
    ("earnings_base_share_5y", "fewer than eight fiscal years of net income are available on one accounting basis"),
    ("net_margin_base_share_5y", "fewer than eight fiscal years of revenue or of net income are available on one accounting basis"),
    ("eps_growth_10y", "fewer than ten fiscal years of EPS are available"),
    ("eps_growth_10y", "mean net income over the three base years is at most a tenth of the mean over the three end years, AND the base years' net margin is under half the end years'"),
    # the gross-margin helpers, over five entries reading one input
    ("gross_margin_ttm", "the company does not report cost of revenue separately"),
    ("gross_margin_range_5y", "the company does not report cost of revenue separately"),
    ("gross_margin_range_relative_5y", "the company does not report cost of revenue separately"),
    ("gross_margin_change_3y", "the company does not report cost of revenue separately"),
    ("gross_margin_vs_3y_median", "the company does not report cost of revenue separately"),
    # a consumed entry came back absent and its own reason is passed straight
    # on, so the sentence a reader gets is the one that entry refused with
    ("eps_minus_revenue_cagr_spread_5y", "either component CAGR is not meaningful"),
    ("dividend_adjusted_peg", "the five-year EPS CAGR is not meaningful"),
    ("dividend_adjusted_peg", "P/E (TTM) is not meaningful"),
    ("peg_trailing", "P/E (TTM) is not meaningful"),
    # a window too short to read, refused where windows are assembled
    ("ev_ebit_to_own_5y_median", "fewer than 20 trailing quarters of EV/EBIT are available"),
    ("pe_to_own_5y_median_pe", "fewer than 20 trailing quarters of P/E are available"),
    ("profitable_years_10y", "fewer than ten fiscal years of filings are available"),
    ("incremental_roic_5y", "fewer than eight fiscal years are available on one accounting basis"),
    ("incremental_roic_5y", "invested capital did not grow across the window"),
    ("incremental_roic_5y", "pre-tax income in any year of the window is zero or negative"),
    ("goodwill_impairment_to_equity_5y", "any year in the window has no resolvable impairment figure"),
    ("consecutive_capital_return_years", "a year in the run paid no dividend and has no resolvable repurchase figure"),
    # no such data source is ingested, so the entry is absent for everyone
    ("insider_net_buying_6m", "no Form 4 filings exist for the issuer in the window"),
    ("institutional_ownership_pct", "13F holdings have not been aggregated for the ticker"),
}


# Every way a formula can attribute a sentence to the metric bank. Matched
# case-insensitively against the string constants in engine/compute.py that a
# reader could be shown. Widening this list is cheap and narrowing it is not:
# each phrase names the bank as the authority for a claim, in a sentence
# written where the bank cannot correct it.
#
# What is deliberately NOT here is the bare phrase "not meaningful for". A
# `data` condition's own text is passed to compute.not_meaningful as the thing
# being cited — "either side is not meaningful for this company" is the
# citation key, not a restatement of it — and a scan that caught those would
# be refusing the very mechanism it exists to require.
_CLAIMS_THE_BANK = ("the bank's own test", "the bank marks", "the bank says",
                    "the bank calls", "the bank states", "the bank declares",
                    "the bank considers", "the bank treats")


def _docstrings(tree) -> set:
    """Every docstring node in a module, by identity.

    Excluded from the scan below because a docstring is prose about the code,
    addressed to whoever edits it. This file's own explanation of how the bank
    is consulted says "a measure the bank says cannot describe this filer" —
    which is a true sentence in the right place, and would be a defect in a
    reason string."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is None:
                continue
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value,
                                                          ast.Constant):
                out.add(id(first.value))
    return out


class TestADataConditionAndItsEnforcementAreTheSameThing:

    def declared(self):
        return {(eid, c) for eid, cs in bank.data_conditions().items()
                for c in cs}

    def test_nothing_claims_the_banks_authority_without_citing_it(self):
        """The phrase is the claim, so the phrase has one home. A formula
        writing it into a sentence of its own is a citation nothing checked —
        which is how two of them came to name a test that did not exist.

        Every way of saying it, not only the one phrase that was caught the
        first time. `altman_z_score` narrated the bank's applicability in
        words of its own — "the bank marks this not meaningful for financial
        companies; whether this company is one is a judgement the data cannot
        make" — and sat outside a scan looking for six particular words while
        the host had long since started making exactly that judgement. A
        formula speaking for the bank is the defect; which synonym it reaches
        for is not the test."""
        tree = ast.parse(pathlib.Path(compute.__file__).read_text(
            encoding="utf-8"))
        helper = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef)
                      and n.name == "not_meaningful")
        mine = {id(n) for n in ast.walk(helper)} | _docstrings(tree)
        stray = [n.value[:60] for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and any(p in n.value.lower() for p in _CLAIMS_THE_BANK)
                 and id(n) not in mine]
        assert stray == [], (
            "engine/compute.py speaks for the metric bank in a sentence of "
            "its own: " + str(stray) + ". Cite the condition through "
            "compute.not_meaningful; the sentence has one home, and an "
            "applicability rule the host now enforces needs no narration.")

    def test_every_refusal_names_a_condition_the_bank_states(self):
        assert _cited_conditions() - self.declared() == set()

    def test_naming_one_the_bank_does_not_state_is_refused_at_the_call(self):
        """The static check above is for coverage; this is the one that fires
        whatever a scanner can read."""
        with pytest.raises(ValueError) as e:
            compute.not_meaningful("pe_ttm", "the moon is in the wrong house")
        assert "not one of the `data` conditions" in str(e.value)
        with pytest.raises(ValueError) as e:
            compute.not_meaningful("market_cap", "anything at all")
        assert "it declares none" in str(e.value)

    def test_the_sentence_a_reader_gets_is_the_banks_own(self):
        """One copy. A formula that restated the condition could restate it
        wrongly, and the reader has no way to tell which of the two is the
        rule."""
        stated = bank.data_conditions()["pe_ttm"][0]
        got = compute.not_meaningful("pe_ttm", stated, "diluted EPS is -0.44")
        assert got["status"] == "absent"
        assert stated in got["reason"]
        assert "diluted EPS is -0.44" in got["reason"]

    def test_no_condition_is_declared_and_performed_nowhere(self):
        """The direction that cannot be proved, pinned so it cannot grow
        quietly. A condition that is neither cited nor on the list is one
        nobody has said is enforced — which is exactly how a payout ratio
        came to be served with a warning instead of refused."""
        orphans = self.declared() - _cited_conditions() \
            - ENFORCED_BY_SHARED_MACHINERY
        assert orphans == set(), (
            "declared in the metric bank and performed nowhere this file can "
            "see: " + str(sorted(orphans)))

    def test_the_list_of_the_unprovable_ones_does_not_outlive_them(self):
        """And it shrinks. An entry left on it after its condition became
        citable is the list turning into decoration."""
        stale = ENFORCED_BY_SHARED_MACHINERY - self.declared()
        assert stale == set(), stale
        assert not (ENFORCED_BY_SHARED_MACHINERY & _cited_conditions())


# ---------------------------------------------------------------------------
# what the gate does
# ---------------------------------------------------------------------------

class TestTheGateRefusesBeforeTheFormulaRuns:
    def test_an_ordinary_company_computes(self, company):
        cik = company(ORDINARY_SIC)
        r = results(cik, ["debt_to_equity"])["debt_to_equity"]
        assert r["status"] == "computed"
        assert r["value"] == pytest.approx(0.5)

    def test_a_lender_is_inapplicable_and_never_computes(self, company):
        cik = company(BANK_SIC)
        r = results(cik, ["debt_to_equity"])["debt_to_equity"]
        assert r["status"] == "inapplicable"
        assert "value" not in r
        assert r["industry"] == DEPOSIT

    def test_the_refusal_says_which_class_and_which_code(self, company):
        cik = company(BANK_SIC, "State Commercial Banks")
        r = results(cik, ["debt_to_equity"])["debt_to_equity"]
        assert "deposits" in r["reason"]
        assert "Depository and lending" in r["reason"]
        assert "6022" in r["reason"]

    def test_a_class_a_measure_does_not_name_still_computes(self, company):
        """Gating is per measure and per class, never per kind of filer. A
        property company's debt against its equity is the ratio it says it
        is; what differs is the level, and levels are a strategy's."""
        cik = company(REIT_SIC)
        assert results(cik, ["debt_to_equity"])["debt_to_equity"]["status"] \
            == "computed"
        assert results(cik, ["current_ratio"])["current_ratio"]["status"] \
            == "inapplicable"

    def test_the_formula_is_never_reached(self, company, monkeypatch):
        """Structural, not procedural. The gate is not a branch inside the
        computation that a later edit could get above."""
        cik = company(BANK_SIC)

        def boom(ctx):
            raise AssertionError("the formula ran for a declined class")
        monkeypatch.setitem(compute.REGISTRY, "debt_to_equity", boom)
        assert results(cik, ["debt_to_equity"])["debt_to_equity"]["status"] \
            == "inapplicable"

    def test_a_filer_with_no_code_at_all_computes(self, company):
        """Silence is not an accusation. A journal driven by hand has no
        code, and refusing every measure in one on the chance the company
        might be a bank would refuse the whole program."""
        cik = company("")
        assert results(cik, ["debt_to_equity"])["debt_to_equity"]["status"] \
            == "computed"

    def test_an_unclassifiable_code_is_absent_and_not_inapplicable(
            self, company):
        """The Synchrony case, and the asymmetry that makes it different from
        a bank. A published code the host cannot act on is evidence — the SEC
        has said something that points where these measures do not go — so
        the measure refuses. But it refuses as a gap and not as a boundary:
        the code may be reassigned and the host may learn to read it, and
        calling that permanent would tell a reader a fixable thing was not."""
        cik = company(AMBIGUOUS_SIC, "Finance Services")
        r = results(cik, ["debt_to_equity"])["debt_to_equity"]
        assert r["status"] == "absent"
        assert "6199" in r["reason"]
        assert "banks and lenders" in r["reason"]

    def test_an_unclassifiable_code_does_not_touch_ungated_measures(
            self, company):
        """It refuses the measures that named a class, and only those. A
        payment processor filing under the same code still gets everything
        that never depended on the answer."""
        cik = company(AMBIGUOUS_SIC)
        assert results(cik, ["market_cap"])["market_cap"]["status"] != \
            "inapplicable"


class TestItReachesEveryReading:
    """One chokepoint, or it is not a guarantee. A reconstruction and a
    per-filing series are separate contexts built in separate modules, and a
    gate that caught only the live view would leave a purchase snapshot and
    an exit's confirmation history reading numbers the screen refuses."""

    def test_a_reconstruction_refuses_too(self, company):
        cik = company(BANK_SIC)
        r = results(cik, ["debt_to_equity"], as_of="2025-06-30")
        assert r["debt_to_equity"]["status"] == "inapplicable"

    def test_the_per_filing_series_refuses_at_every_boundary(self, company):
        cik = company(BANK_SIC)
        h = dataview.confirmation_history(cik, ["TEST"], "debt_to_equity")
        assert h["readings"]
        assert all(r["value"] is None for r in h["readings"])
        assert all("Depository and lending" in r["reason"]
                   for r in h["readings"])

    def test_a_context_must_say_what_kind_of_filer_it_is_computing_for(self):
        """No default. A context built by somebody who has not read any of
        this is refused rather than silently ungated."""
        with pytest.raises(TypeError):
            compute.Ctx([], None, symbols("SYN"))   # noqa: no industry
        compute.Ctx([], None, symbols("SYN"), industry=no_filer())


class TestTheClassIsReadOnTheDayBeingAsked:
    def test_a_reconstruction_before_a_reclassification_computes(self,
                                                                 company):
        """A company that reclassifies part way through a holding is the case
        a single reading would hide. The measure meant something in 2024 and
        does not now, and a record of 2024 has to say the first."""
        cik = company(ORDINARY_SIC, observed="2024-03-01")
        filer(cik, "A company", BANK_SIC, observed="2025-09-01")
        dataview.invalidate(cik)
        assert results(cik, ["debt_to_equity"],
                       as_of="2024-06-30")["debt_to_equity"]["status"] \
            == "computed"
        assert results(cik, ["debt_to_equity"])["debt_to_equity"]["status"] \
            == "inapplicable"


# ---------------------------------------------------------------------------
# where it travels
# ---------------------------------------------------------------------------

@pytest.fixture
def indifferent(strategies):
    """A strategy that declines nothing, so a declined class still reaches
    the measure layer. Both shipped strategies refuse these companies before
    any measure is read, which is exactly why they cannot exercise this."""
    strategies("verdicts")
    loaded, reports = strategy_loader.discover()
    assert "verdicts" in loaded, [r["errors"] for r in reports if not r["ok"]]
    return loaded["verdicts"]


class TestItTravelsWithoutBecomingAbsence:
    def test_the_context_hands_a_strategy_the_third_state(self, company,
                                                          indifferent):
        cik = company(BANK_SIC)
        journal_for("verdicts")
        security = {"ticker": "TEST", "name": "A company", "cik": cik}
        ctx = context.build_context(security, [security], {}, {},
                                    record=indifferent)
        cur = ctx["measures"]["debt_to_equity"]["current"]
        assert cur["status"] == "inapplicable"
        assert cur["industry"] == DEPOSIT

    def test_a_cited_measure_can_never_test_as_a_pass(self, company,
                                                      indifferent):
        """The one thing that must be true whatever else changes. An
        inapplicable figure is not a small figure and not a large one."""
        cik = company(BANK_SIC)
        journal_for("verdicts")
        security = {"ticker": "TEST", "name": "A company", "cik": cik}
        ctx = context.build_context(security, [security], {}, {},
                                    record=indifferent)
        for comparator, limit in (("at_most", 99999.0), ("at_least", -1.0)):
            assert contract.test(ctx, {"measure": "debt_to_equity",
                                       "comparator": comparator,
                                       "threshold": limit}) == contract.UNKNOWN

    def test_the_evidence_row_says_which_kind_of_absence_it_is(
            self, company, indifferent):
        """It used to flatten to `absent` here, which drew a permanent
        boundary as a missing figure — and froze it that way into any
        purchase made on the day."""
        cik = company(BANK_SIC)
        journal_for("verdicts")
        security = {"ticker": "TEST", "name": "A company", "cik": cik}
        ctx = context.build_context(security, [security], {}, {},
                                    record=indifferent)
        rows, errors = contract.resolve_evidence(
            indifferent, ctx, [{"measure": "debt_to_equity",
                                "comparator": "at_most", "threshold": 1.0}])
        assert errors == []
        assert rows[0]["observed"]["status"] == "inapplicable"
        assert rows[0]["outcome"] == contract.UNKNOWN

    def test_the_coverage_screen_can_count_it_apart_from_a_gap(self,
                                                              company):
        cik = company(BANK_SIC)
        meta = bank.meta()
        cov = dataview.coverage(cik, ["TEST"], list(meta), meta)
        rows = {r["id"]: r for r in cov["entries"]}
        assert rows["debt_to_equity"]["status"] == "inapplicable"
        assert rows["debt_to_equity"]["industry"] == DEPOSIT

    def test_a_hand_entered_figure_does_not_override_it(self, company,
                                                        indifferent):
        """A typed number cannot make a measure applicable. Whatever it is,
        it is a different quantity wearing this measure's name and unit, and
        it would feed a verdict."""
        from engine import hand_entered, journals
        cik = company(BANK_SIC)
        journal, _ = journal_for("verdicts")
        doc = journals.load(journal["id"])
        security = {"ticker": "TEST", "name": "A company", "cik": cik}
        doc["securities"].append(security)
        hand_entered.record(security, "debt_to_equity", 0.4)
        journals.save(doc)
        assert hand_entered.reading(
            security, "debt_to_equity")["status"] == "known"
        ctx = context.build_context(security, [security], {}, {},
                                    record=indifferent)
        cur = ctx["measures"]["debt_to_equity"]["current"]
        assert cur["status"] == "inapplicable"

    def test_it_is_never_frozen_into_a_purchase_snapshot(self, company):
        """Principle 3 makes this the one that cannot be undone. A snapshot is
        written once and never rewritten, so a figure captured here is a
        category error nobody can correct afterwards.

        The computed layer alone would not put one there — it only freezes
        what computed, and this did not. The overlay is the hole: a
        hand-entered number lands on top of any measure, so a refused one has
        to be barred before the overlays rather than after."""
        from engine import hand_entered
        cik = company(BANK_SIC)
        security = {"ticker": "TEST", "name": "A company", "cik": cik}
        hand_entered.record(security, "debt_to_equity", 0.4)
        hand_entered.record(security, "dividend_yield", 3.0)
        computed = results(cik, list(bank.meta()))
        values = dataview.merged_values(security, computed)
        assert "debt_to_equity" not in values
        # And the overlay still works where the measure does apply, so this
        # is a bar on one thing rather than the overlay quietly switched off.
        assert values["dividend_yield"]["value"] == 3.0


class TestTheShippedStrategiesAreUnaffected:
    """Both decline all three classes outright, so a declined company never
    reaches a measure at all. If that ever stops being true, this goes red
    before anybody ships a verdict built on a refused figure."""

    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    @pytest.mark.parametrize("sic", [BANK_SIC, REIT_SIC])
    def test_a_declined_company_is_refused_before_any_measure_is_read(
            self, sid, sic, company):
        cik = company(sic)
        journal, record = journal_for(sid)
        security = {"ticker": "TEST", "name": "A company", "cik": cik}
        ctx = context.build_context(security, [security], {}, {},
                                    record=record)
        verdict = contract.evaluate(record, ctx)
        assert verdict["render"] == "inapplicable"
        assert verdict["state"]["id"] == "host:not-evaluated"

    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    def test_every_measure_a_shipped_strategy_cites_is_one_it_can_read(
            self, sid, strategies):
        """The finding this would surface: a strategy that evaluates a class
        while resting on a measure declared out of scope for it would fail
        every such test with `unknown` and never say why. Both decline all
        three today, so the set is empty — and it stays checked."""
        loaded, _ = strategy_loader.discover()
        record = loaded[sid]
        declined = set(contract.declined_classes(record))
        gated = bank.applicability()
        evaluated = set(contract.INDUSTRY_CLASSES) - declined
        clashes = sorted(
            (eid, sorted(cs & evaluated))
            for eid, rules in gated.items() for cs, _ in rules
            if cs & evaluated and _cites(record, eid))
        assert clashes == [], clashes


def _cites(record, measure_id) -> bool:
    """Whether a strategy names a measure anywhere in its bundle.

    Read off the bundle's own source rather than its declaration, because a
    citation lives inside `decide` and never appears in the declaration at
    all. Coarse on purpose — a false positive costs a reviewer one look, and
    a false negative is a test that passes against anything, which is what
    the first version of this was.
    """
    from pathlib import Path
    text = "".join(f.read_text(encoding="utf-8")
                   for f in sorted(Path(record["dir"]).rglob("*"))
                   if f.is_file() and f.suffix in (".py", ".yaml", ".json"))
    return f'"{measure_id}"' in text
