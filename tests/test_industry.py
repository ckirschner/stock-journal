"""What kind of company a filer is, and what a strategy is allowed to do
about it.

The failure this file exists to prevent is the one the whole change was
commissioned about, and it is worth stating in full because every test below
is a piece of it. For a bank, cash from operations is dominated by the
period's change in loans and deposits. Free cash flow, owner earnings, cash
conversion and the yields built on them therefore do not come back grey for a
lender — they come back large, and a *shrinking* bank produces the largest
figures of all. That is the one place in this repository where a financial
company produced a confident wrong pass rather than an honest absence, and a
confident wrong pass is the thing this program exists to not do.

Three guarantees are pinned here, and each of them is structural rather than
procedural:

1. The classification is read from the SEC's published list, code by code,
   and the list itself is a fixture read from the SEC — not a range somebody
   reasoned their way to. Every range an ordinary reading suggests is wrong
   somewhere, and the tests below name the companies each one gets wrong.
2. A code that cannot say what kind of company a filer is comes back absent
   and never "ordinary". There is no third answer to invent.
3. A declined company never reaches `decide` at all. That is the difference
   between a boundary and a habit: an author cannot forget it, and a later
   edit cannot get above it.
"""

import json
from pathlib import Path

import pytest
from conftest import filer, journal_for, tie

from engine import context, contract, industry, strategy_loader

PUBLISHED = json.loads(
    (Path(__file__).parent / "fixtures" / "groundtruth" / "sec-sic-6xxx.json")
    .read_text(encoding="utf-8"))

DEPOSIT, INSURE, PROPERTY = ("depository-lending", "insurance", "real-estate")


def sec(cik=None, ticker="TEST"):
    return {"ticker": ticker, "name": "A company", "cik": cik}


def ctx_for(record, security, as_of=None):
    values = {v["id"]: record["defaults"][v["id"]]
              for v in record.get("values") or []}
    return context.build_context(security, [security], values, {},
                                 as_of=as_of, record=record)


@pytest.fixture
def indifferent(strategies):
    """A fixture strategy that declines nothing, so the branch where the gate
    does NOT fire stays exercised against real data.

    It used to be `strategies/proof/`, which shipped. Nothing shipped holds
    no view any more: both real strategies decline lenders, insurers and
    property companies, and a scaffold kept in the picker so a test had
    something neutral to point at was rendering verdicts that meant nothing
    to anyone who chose it.
    """
    strategies("verdicts")
    loaded, reports = strategy_loader.discover()
    assert "verdicts" in loaded, [r["errors"] for r in reports
                                  if not r["ok"]]
    return loaded["verdicts"]


@pytest.fixture
def picky(strategies):
    """A fixture strategy declining lenders and property companies, and
    evaluating insurers and everything else."""
    strategies("picky")
    loaded, reports = strategy_loader.discover()
    assert "picky" in loaded, [r["errors"] for r in reports if not r["ok"]]
    return loaded["picky"]


# ---------------------------------------------------------------------------
# against the published list
# ---------------------------------------------------------------------------

class TestTheTableIsThePublishedList:
    """Read from the SEC, not reasoned about. The band is a closed set of
    forty-one codes, which is the whole reason this is a table and not a
    range: a range is a statement about codes that do not exist."""

    def test_every_published_code_is_in_the_table(self):
        missing = sorted(set(PUBLISHED) - set(industry.SIC))
        assert missing == [], missing

    def test_the_table_invents_no_codes(self):
        extra = sorted(set(industry.SIC) - set(PUBLISHED))
        assert extra == [], extra

    def test_every_title_is_the_sec_s_own(self):
        """Cased for reading and otherwise verbatim. A title this program
        made up would be a citation nobody could check."""
        wrong = [(code, industry.SIC[code][1], PUBLISHED[code]["title"])
                 for code in PUBLISHED
                 if industry.SIC[code][1].upper() != PUBLISHED[code]["title"]]
        assert wrong == [], wrong

    def test_every_class_named_is_one_the_host_declares(self):
        named = {cls for cls, _title in industry.SIC.values()} - {None}
        assert named <= set(contract.INDUSTRY_CLASSES), named

    def test_every_ambiguous_code_is_published_and_classes_to_nothing(self):
        for code in industry.AMBIGUOUS:
            assert code in PUBLISHED, code
            assert industry.SIC[code][0] is None, code


class TestWhatARangeWouldHaveGotWrong:
    """Each of these is a company that would have been evaluated badly or
    refused wrongly by the ranges an ordinary reading suggests. They are the
    evidence for the table being code by code, so they are pinned as facts
    rather than left in a comment."""

    def test_broker_dealers_sit_above_the_band_that_looks_like_banks(self):
        """6020–6199 stops one code short of them. Bear Stearns files at
        6211 and would have read as an ordinary industrial."""
        for code in ("6200", "6211", "6221"):
            assert industry.classify(code)[0] != DEPOSIT
            assert industry.classify(code)[1] is not None, code

    def test_insurance_brokers_are_not_insurers(self):
        """6311–6411 sweeps in 6411, which is Marsh and Aon: fee businesses
        with no reserves and no float, and nothing here misreads them."""
        assert industry.classify("6411") == (None, None)

    def test_a_blank_cheque_shell_is_not_real_estate(self):
        """6500–6798 contains 6770. A SPAC is not a property company, and
        classifying it as one would decline it for the wrong reason."""
        assert industry.classify("6770")[0] != PROPERTY

    def test_royalty_vehicles_are_not_real_estate(self):
        for code in ("6792", "6795"):
            assert industry.classify(code) == (None, None), code

    def test_estate_agents_acting_for_others_are_ordinary(self):
        assert industry.classify("6531") == (None, None)

    def test_investment_vehicles_sit_above_the_band_that_looks_like_property(
            self):
        """6799 is one past 6798 — closed-end funds, BDCs and investment
        holding companies, whose operating cash flow is their investing."""
        assert industry.classify("6799")[1] is not None


class TestSynchronyIsTheCaseThisWasCommissionedAbout:
    """Synchrony Financial, CIK 1601712, is published under SIC 6199. That is
    the code an exception list would have exempted as an asset manager, and
    it is the company the whole change was commissioned about — see
    fixtures/groundtruth/sec-sic-6xxx-notes.md, where it was read off EDGAR's
    own company search alongside American Express."""

    def test_the_code_it_files_under_cannot_be_classified(self):
        cls, why = industry.classify("6199")
        assert cls is None
        assert why is not None
        assert "6199" in why

    def test_and_is_therefore_absent_rather_than_ordinary(self):
        filer(1_601_712, "Synchrony Financial", "6199", "Finance Services")
        node = industry.observation(sec(1_601_712, "SYF"))
        assert node["status"] == "absent"
        assert node["unclassifiable"] is True
        assert node["sic"] == "6199"

    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    def test_neither_shipped_strategy_evaluates_it(self, sid):
        loaded, _ = strategy_loader.discover()
        record = loaded[sid]
        filer(1_601_712, "Synchrony Financial", "6199", "Finance Services")
        security = sec(1_601_712, "SYF")
        result = contract.evaluate(record, ctx_for(record, security))
        assert result["produced_by"] == "host"
        assert result["state"]["id"] == "host:industry-unknown"
        assert result["render"] == "unknown"


# ---------------------------------------------------------------------------
# the classification as a host fact
# ---------------------------------------------------------------------------

class TestReadingAFilersClass:
    def test_a_savings_institution_is_a_lender(self):
        filer(701, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        node = industry.observation(sec(701))
        assert node["status"] == "known"
        assert node["class"] == DEPOSIT
        assert node["value"] == "Depository and lending"
        assert "6035" in node["provenance"][0]

    def test_an_insurer_is_an_insurer(self):
        filer(702, "Thrapston Mutual", "6331",
              "Fire, Marine & Casualty Insurance")
        assert industry.observation(sec(702))["class"] == INSURE

    def test_a_reit_is_a_property_company(self):
        filer(703, "Pelham Yards Trust", "6798",
              "Real Estate Investment Trusts")
        assert industry.observation(sec(703))["class"] == PROPERTY

    def test_an_ordinary_business_is_a_real_answer_and_not_an_absence(self):
        """"Nothing special about this one" is an answer. Serving it as
        absence would put every manufacturer in the same bucket as a filer
        whose code nobody could read."""
        filer(704, "Vantrell Machining", "3559",
              "Special Industry Machinery, NEC")
        node = industry.observation(sec(704))
        assert node["status"] == "known"
        assert node["class"] is None
        assert node["value"] == "Ordinary operating business"

    def test_an_unrecognised_financial_code_is_refused_not_assumed(self):
        """The band is where every failure is, so a code the SEC adds must
        not read as an ordinary business by default. Loud and absent beats
        quiet and wrong."""
        filer(705, "Something New", "6045", "A code invented for this test")
        node = industry.observation(sec(705))
        assert node["status"] == "absent"
        assert node["unclassifiable"] is True

    def test_an_unrecognised_code_outside_the_band_is_ordinary(self):
        filer(706, "Something Else", "8742", "Management Consulting Services")
        assert industry.observation(sec(706))["class"] is None

    def test_a_code_that_arrived_as_a_number_still_reads(self):
        """EDGAR has served it both ways. A code that arrived as 6021 rather
        than "6021" must not read as a company nobody has heard of."""
        filer(707, "Numeric Bank", 6021, "National Commercial Banks")
        assert industry.observation(sec(707))["class"] == DEPOSIT

    def test_a_security_with_no_company_is_absent_but_not_a_problem(self):
        """A hand-driven journal ties nothing to EDGAR. That is not evidence
        of anything and must not read as one."""
        node = industry.observation(sec(None))
        assert node["status"] == "absent"
        assert "unclassifiable" not in node

    def test_a_filer_with_no_code_stored_is_absent_but_not_a_problem(self):
        filer(708, "Unfetched Co", "", None)
        node = industry.observation(sec(708))
        assert node["status"] == "absent"
        assert "unclassifiable" not in node

    def test_the_published_code_is_reported_beside_the_class(self):
        filer(709, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        report = industry.report(sec(709))
        assert report["sic"]["status"] == "known"
        assert report["sic"]["value"].startswith("6035 — ")

    def test_the_code_is_still_reported_when_it_cannot_be_classified(self):
        """A reader looking at an absent classification should be able to see
        the thing that could not be classified."""
        filer(710, "Ambiguous Co", "6199", "Finance Services")
        report = industry.report(sec(710))
        assert report["sic"]["status"] == "known"
        assert report["industry"]["status"] == "absent"


class TestTheHandBuiltShapeMatchesTheRealOne:
    """Half the strategy tests build a context by hand rather than driving
    fifteen measures through the compute layer, and the whole arrangement
    only holds while the hand-built shape is the real one. This is the node
    that arrived last, so it is the one most likely to drift."""

    @pytest.mark.parametrize("cls", [None, DEPOSIT, INSURE, PROPERTY])
    def test_the_helper_produces_what_the_host_produces(self, cls):
        from conftest import industry_node
        code = {None: "3559", DEPOSIT: "6035", INSURE: "6331",
                PROPERTY: "6798"}[cls]
        filer(760, "A company", code, "A title")
        real = industry.observation(sec(760))
        built = industry_node(cls, sic=code, title="A title")
        assert set(built) == set(real)
        for key in ("status", "value", "class", "sic", "title", "source"):
            assert built[key] == real[key], key


class TestAReclassificationIsVisible:
    """A company that changes kind part way through a holding is a real case,
    and the identity record is append-only, so the change is on record."""

    def test_the_current_class_wins_and_says_the_move_happened(self):
        filer(720, "Meridian Group", "3559", "Special Industry Machinery, NEC",
              observed="2024-02-01")
        filer(720, "Meridian Group", "6022", "State Commercial Banks",
              observed="2026-02-01")
        node = industry.observation(sec(720))
        assert node["class"] == DEPOSIT
        assert any("ordinary operating business" in c for c in node["cautions"])

    def test_a_reconstruction_sees_the_class_in_force_on_its_day(self):
        filer(721, "Meridian Group", "3559", "Special Industry Machinery, NEC",
              observed="2024-02-01")
        filer(721, "Meridian Group", "6022", "State Commercial Banks",
              observed="2026-02-01")
        assert industry.observation(sec(721), "2025-06-01")["class"] is None
        assert industry.observation(sec(721), "2026-06-01")["class"] == DEPOSIT

    def test_a_day_before_the_first_observation_says_so_rather_than_refusing(
            self):
        """The one place this reaches across a date, and it says which
        observation it used. Refusing would not be more honest — the SEC
        publishes no history to consult — it would only refuse every
        backdated evaluation in every journal over a fact that rarely moves.
        """
        filer(722, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered",
              observed="2026-02-01")
        node = industry.observation(sec(722), "2020-01-01")
        assert node["class"] == DEPOSIT
        assert "2020-01-01" in node["provenance"][0]
        assert "earliest observation" in node["provenance"][0]

    def test_a_code_change_that_does_not_change_the_class_is_not_a_caution(
            self):
        """6021 to 6022 changes which regulator chartered it and nothing
        about how its accounts read. A caution on every such move would be
        noise on the node a reader most needs to trust."""
        filer(723, "Okell Bank", "6021", "National Commercial Banks",
              observed="2024-02-01")
        filer(723, "Okell Bank", "6022", "State Commercial Banks",
              observed="2026-02-01")
        assert industry.observation(sec(723))["cautions"] == []


class TestItReachesAStrategyAsAnOrdinaryFact:
    def test_the_context_carries_both_nodes(self, indifferent):
        filer(730, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        record = indifferent
        ctx = ctx_for(record, sec(730))
        assert ctx["security"]["industry"]["class"] == DEPOSIT
        assert ctx["security"]["sic"]["value"].startswith("6035")

    def test_a_strategy_can_test_it_and_the_host_answers(self, indifferent):
        filer(731, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        record = indifferent
        ctx = ctx_for(record, sec(731))
        item = {"fact": "security.industry", "comparator": "equals",
                "threshold": "Depository and lending"}
        assert contract.test(ctx, item) == contract.PASS

    def test_an_unclassifiable_filer_never_tests_as_a_pass(self,
                                                           indifferent):
        """Absence resolves to unknown, here as everywhere. A rule reading
        "this is not a bank" must not come out true because nobody could
        say what it was."""
        filer(732, "Ambiguous Co", "6199", "Finance Services")
        record = indifferent
        ctx = ctx_for(record, sec(732))
        item = {"fact": "security.industry", "comparator": "not_equals",
                "threshold": "Depository and lending"}
        assert contract.test(ctx, item) == contract.UNKNOWN


# ---------------------------------------------------------------------------
# what a strategy declares, and what the host does with it
# ---------------------------------------------------------------------------

def decl(**over):
    d = {
        "id": "x", "name": "X", "summary": "A declaration.",
        "version": 1, "contract": contract.CONTRACT_VERSION,
        "changelog": {1: "First."},
        "states": [{"id": "s", "name": "S", "render": "hold",
                    "description": "Does nothing."}],
    }
    d.update(over)
    return d


class TestDeclaringWhatYouWillNotEvaluate:
    def test_a_well_formed_declines_list_passes(self):
        assert contract.validate_declaration(decl(declines=[
            {"class": DEPOSIT, "because": "A stated reason."}])) == []

    def test_a_class_the_host_does_not_name_is_refused(self):
        errors = contract.validate_declaration(decl(declines=[
            {"class": "utilities", "because": "A stated reason."}]))
        assert any("never invents one" in e for e in errors)

    def test_a_refusal_with_no_reason_is_refused(self):
        """A kind of company quietly not evaluated is indistinguishable from
        a gap nobody has got to yet, and only the author knows which."""
        errors = contract.validate_declaration(decl(declines=[
            {"class": DEPOSIT, "because": "  "}]))
        assert any("needs a `because`" in e for e in errors)

    def test_declining_the_same_class_twice_is_refused(self):
        errors = contract.validate_declaration(decl(declines=[
            {"class": DEPOSIT, "because": "One."},
            {"class": DEPOSIT, "because": "Two."}]))
        assert any("declined twice" in e for e in errors)

    def test_an_empty_list_is_refused_rather_than_ignored(self):
        errors = contract.validate_declaration(decl(declines=[]))
        assert any("declines nothing" in e for e in errors)

    def test_leaving_it_out_declines_nothing_and_is_fine(self):
        assert contract.validate_declaration(decl()) == []
        assert contract.declined_classes(decl()) == {}

    def test_extra_keys_are_refused(self):
        errors = contract.validate_declaration(decl(declines=[
            {"class": DEPOSIT, "because": "A reason.", "since": "2026"}]))
        assert any("must be exactly" in e for e in errors)


class TestSayingWhatTheMethodDoesNotPromise:
    """`limits` — prose the host renders and never reads.

    It is checked as hard as anything else declared, for one reason: a
    heading with nothing under it tells a reader there is something they are
    not being told, which is worse than not raising the subject.
    """

    LIMIT = {"title": "It is a portfolio method",
             "body": "An expected rate of losers is built in."}

    def test_a_well_formed_list_passes(self):
        assert contract.validate_declaration(decl(limits=[self.LIMIT])) == []

    def test_leaving_it_out_is_fine(self):
        assert contract.validate_declaration(decl()) == []

    def test_an_empty_list_is_refused_rather_than_ignored(self):
        errors = contract.validate_declaration(decl(limits=[]))
        assert any("claims there is nothing" in e for e in errors)

    def test_a_heading_with_nothing_under_it_is_refused(self):
        errors = contract.validate_declaration(decl(
            limits=[{"title": "Something you should know", "body": ""}]))
        assert any("needs a `body`" in e for e in errors)

    def test_a_body_with_no_heading_is_refused(self):
        errors = contract.validate_declaration(decl(
            limits=[{"title": "", "body": "Some prose."}]))
        assert any("needs a `title`" in e for e in errors)

    def test_extra_keys_are_refused(self):
        errors = contract.validate_declaration(decl(
            limits=[{**self.LIMIT, "severity": "high"}]))
        assert any("must be exactly" in e for e in errors)

    def test_the_same_heading_twice_is_refused(self):
        errors = contract.validate_declaration(decl(
            limits=[self.LIMIT, {**self.LIMIT, "body": "Different prose."}]))
        assert any("declared twice" in e for e in errors)

    def test_it_reaches_no_verdict_and_gates_nothing(self, indifferent):
        """The guarantee that makes this safe to add: it is prose. A limit
        that changed what a strategy did would be a rule nobody could test,
        living in the one field written for things that cannot be rules."""
        filer(760, "Ordinary Manufacturing", "3711", "Motor Vehicles")
        plain = contract.evaluate(indifferent,
                                  ctx_for(indifferent, sec(760)))
        with_limits = dict(indifferent)
        with_limits["limits"] = [self.LIMIT]
        limited = contract.evaluate(with_limits,
                                    ctx_for(with_limits, sec(760)))
        assert limited["state"] == plain["state"]
        assert limited["render"] == plain["render"]
        assert limited["produced_by"] == plain["produced_by"]


class TestBothShippedStrategiesSayWhatTheyDoNotPromise:
    """Every method these strategies draw on is a portfolio method with an
    expected rate of losers, and every one of their authors said so. A screen
    rendering a verdict on ONE security is quietly promising something none
    of them promised, and nothing contradicts it unless the strategy says so.

    Pinned because it is the kind of claim that gets dropped by whoever adds
    the third strategy, and nothing would notice.
    """

    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    def test_it_says_it_is_a_portfolio_method(self, sid):
        loaded, _ = strategy_loader.discover()
        limits = loaded[sid].get("limits") or []
        assert limits, sid
        assert any("portfolio method" in l["title"]
                   or "portfolio method" in l["body"] for l in limits), sid
        assert any("one security" in l["body"] for l in limits), sid

    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    def test_every_limit_carries_enough_prose_to_be_worth_reading(self, sid):
        loaded, _ = strategy_loader.discover()
        for lim in loaded[sid]["limits"]:
            assert len(lim["body"]) > 300, (sid, lim["title"])

    def test_graham_says_an_empty_screen_is_the_method_working(self):
        """The one most likely to be experienced as the tool being broken.
        Graham's rules sat inside a bond allocation and he was explicit that
        an expensive market should produce no candidates — the signal to hold
        more bonds rather than to relax anything. This program does not
        implement that allocation, so without it said, a strategy correctly
        returning nothing for a year reads as broken. A reader who concludes
        the tool is broken loosens the tool."""
        loaded, _ = strategy_loader.discover()
        body = " ".join(l["body"] for l in loaded["graham"]["limits"])
        assert "bonds" in body
        assert "years at a time" in body
        assert "faithful" in body

    def test_every_document_a_value_names_as_its_source_is_in_the_repo(self):
        """A `source` exists so a reader can go and check the number against
        the thing it came from. One naming a path that is not in a fresh
        clone is worse than one naming nothing: it looks checkable.

        This is not hypothetical. The two documents behind these strategies
        sat under an ignore rule for the whole directory, and the moment
        twelve declared values started citing one of them by path, that rule
        made a claim in the repository that a fresh clone could not honour.
        """
        import re
        from pathlib import Path
        import subprocess
        root = Path(__file__).resolve().parent.parent
        tracked = set(subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True,
            check=True).stdout.split())
        loaded, _ = strategy_loader.discover()
        named = set()
        for record in loaded.values():
            for v in record["values"]:
                named |= set(re.findall(r"[\w./-]+\.(?:md|ya?ml)",
                                        v["source"]["name"]))
        assert named, "no value names a document at all"
        missing = sorted(p for p in named if p not in tracked)
        assert missing == [], missing

    def test_it_reaches_the_screen_that_offers_a_strategy(self):
        """On the offer and not only on the stamped strategy. What a method
        does not promise is knowable before a journal exists, and finding out
        afterwards is finding out too late to choose differently."""
        from app import Api
        offers = Api()._strategy_offer(strategy_loader.discover()[0]["graham"])
        assert offers["limits"] == list(
            strategy_loader.discover()[0]["graham"]["limits"])


class TestOnlyTheHostSaysInapplicable:
    def test_a_strategy_declaring_the_render_type_is_refused(self):
        """A permanent verdict reached by a branch nobody outside the bundle
        can see is indistinguishable from a missing figure, which is the one
        substitution this whole arrangement exists to make impossible."""
        errors = contract.validate_declaration(decl(states=[
            {"id": "nope", "name": "Not covered", "render": "inapplicable",
             "description": "Reached by a branch."}]))
        assert any("only the host produces" in e for e in errors)
        assert any("`declines`" in e for e in errors)

    def test_the_host_state_is_the_one_that_carries_it(self):
        r = contract.host_result("host:not-evaluated", "Out of scope.")
        assert r["render"] == "inapplicable"
        assert r["tier"] == "scope"


class TestTheGate:
    def test_a_declined_company_is_refused_with_the_strategys_own_reason(
            self, picky):
        filer(740, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        result = contract.evaluate(picky, ctx_for(picky, sec(740)))
        assert result["state"]["id"] == "host:not-evaluated"
        assert result["render"] == "inapplicable"
        assert "no current section" in result["reason"]["summary"]

    def test_the_refusal_cites_what_it_rested_on(self, picky):
        filer(741, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        result = contract.evaluate(picky, ctx_for(picky, sec(741)))
        cited = {r["subject"]["id"] for r in result["reason"]["evidence"]}
        assert cited == {"security.industry", "security.sic"}
        row = next(r for r in result["reason"]["evidence"]
                   if r["subject"]["id"] == "security.industry")
        assert row["observed"]["value"] == "Depository and lending"

    def test_a_class_it_does_not_decline_is_evaluated_normally(self, picky):
        """Two of three declined on purpose: a fixture that declined
        everything could not tell "the gate fired" from "it always fires"."""
        filer(742, "Thrapston Mutual", "6331",
              "Fire, Marine & Casualty Insurance")
        result = contract.evaluate(picky, ctx_for(picky, sec(742)))
        assert result["produced_by"] == "strategy"
        assert result["state"]["id"] == "fixture-hold"

    def test_an_ordinary_business_is_evaluated_normally(self, picky):
        filer(743, "Vantrell Machining", "3559",
              "Special Industry Machinery, NEC")
        result = contract.evaluate(picky, ctx_for(picky, sec(743)))
        assert result["produced_by"] == "strategy"

    def test_an_unclassifiable_code_is_unknown_and_not_inapplicable(
            self, picky):
        """A code that does not settle it may be reassigned; a bank will not
        stop being a bank. Reporting the first as permanent would tell a
        reader a fixable gap will never change."""
        filer(744, "Ambiguous Co", "6199", "Finance Services")
        result = contract.evaluate(picky, ctx_for(picky, sec(744)))
        assert result["state"]["id"] == "host:industry-unknown"
        assert result["render"] == "unknown"
        assert contract.RENDER_TYPES["unknown"]["attention"] is True

    def test_no_code_at_all_is_evaluated_normally(self, picky):
        """Refusing every verdict in a hand-driven journal on the chance an
        unnamed company might be a bank would be treating silence as an
        accusation."""
        result = contract.evaluate(picky, ctx_for(picky, sec(None)))
        assert result["produced_by"] == "strategy"

    def test_a_strategy_that_declines_nothing_is_untouched(self, indifferent):
        filer(745, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        record = indifferent
        result = contract.evaluate(record, ctx_for(record, sec(745)))
        assert result["produced_by"] == "strategy"

    def test_it_answers_before_the_setup_screen_is_looked_at(self, strategies):
        """Asking somebody to finish a setup screen for a company that will
        never be evaluated is a dead end one screen further along. The
        answer does not depend on anything the journal has been told, so it
        does not wait for it."""
        strategies("picky", "sound")
        loaded, _ = strategy_loader.discover()
        record = dict(loaded["sound"])          # has a required input
        record["declines"] = [{"class": DEPOSIT, "because": "A reason."}]
        filer(746, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        ctx = ctx_for(record, sec(746))
        ctx["inputs"] = {}
        result = contract.evaluate(record, ctx)
        assert result["state"]["id"] == "host:not-evaluated"

    def test_the_declined_company_never_reaches_decide(self, picky):
        """The structural half. A boundary that depended on the bundle
        remembering to check would be a habit, not a guarantee."""
        called = []
        record = dict(picky)
        record["decide"] = lambda ctx: called.append(1)
        filer(747, "Pelham Yards Trust", "6798",
              "Real Estate Investment Trusts")
        contract.evaluate(record, ctx_for(record, sec(747)))
        assert called == []


class TestTheShippedStrategiesDecline:
    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    @pytest.mark.parametrize("cls", [DEPOSIT, INSURE, PROPERTY])
    def test_every_class_is_declined_with_a_reason(self, sid, cls):
        loaded, _ = strategy_loader.discover()
        declined = contract.declined_classes(loaded[sid])
        assert cls in declined
        assert len(declined[cls]) > 80, declined[cls]

    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    def test_a_bank_gets_a_refusal_rather_than_a_verdict(self, sid):
        loaded, _ = strategy_loader.discover()
        record = loaded[sid]
        filer(750, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        result = contract.evaluate(record, ctx_for(record, sec(750)))
        assert result["render"] == "inapplicable"
        assert result["produced_by"] == "host"

    @pytest.mark.parametrize("sid", ["graham", "buffett"])
    def test_an_asset_manager_is_not_refused(self, sid):
        """A refusal aimed at everything financial-sounding would decline
        companies these strategies can perfectly well judge."""
        loaded, _ = strategy_loader.discover()
        record = loaded[sid]
        filer(751, "Brentmoor Advisers", "6282", "Investment Advice")
        result = contract.evaluate(record, ctx_for(record, sec(751)))
        assert result["produced_by"] == "strategy"

    def test_everything_shipped_declines_the_same_three(self):
        """There is no longer a shipped bundle that declines nothing, and
        that is deliberate: the scaffold that used to play that part was
        offered in the create-journal picker and rendered verdicts that meant
        nothing to whoever chose it. The branch where the gate does not fire
        is exercised by a fixture bundle instead — see `indifferent`."""
        loaded, _ = strategy_loader.discover()
        assert sorted(loaded) == ["buffett", "graham"]
        for record in loaded.values():
            assert set(contract.declined_classes(record)) == {
                DEPOSIT, INSURE, PROPERTY}

    def test_the_refusal_still_lets_a_purchase_be_recorded(self):
        """Principle 2. The tool records decisions and never blocks them,
        and a verdict saying these rules do not cover the company is not a
        gate."""
        import app as app_mod
        journal_for("graham")
        api = app_mod.Api()
        assert api.add_security("TRUST", "Kingsbridge Savings")["ok"]
        filer(752, "Kingsbridge Savings", "6035",
              "Savings Institution, Federally Chartered")
        tie("TRUST", 752)
        state = api.get_state()
        verdict = next(s for s in state["securities"]
                       if s["ticker"] == "TRUST")["_decision"]
        assert verdict["render"] == "inapplicable"
        bought = api.open_position("TRUST", 10, 25.0, None,
                                   "These rules do not cover it and I want "
                                   "it anyway.")
        assert bought["ok"], bought
        after = api.get_state()
        held = next(s for s in after["securities"] if s["ticker"] == "TRUST")
        assert held["_lots"], "the purchase was not recorded"
