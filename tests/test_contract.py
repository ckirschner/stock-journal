"""The contract itself: the closed render-type set, declaration validation
without running logic, decision validation per render type, and evaluation
that contains every failure as an error in place."""

import pytest

from engine import contract


def decl(**over):
    """A minimal well-formed declaration; tests break one thing at a time."""
    d = {
        "id": "fixture",
        "name": "Fixture",
        "summary": "A test declaration.",
        "version": 1,
        "contract": contract.CONTRACT_VERSION,
        "changelog": {1: "First version."},
        "states": [
            {"id": "sit", "name": "Sit", "render": "hold",
             "description": "Do nothing."},
        ],
    }
    d.update(over)
    return d


def record(**over):
    """A loaded-strategy record shaped like the loader's output."""
    r = decl()
    r.update({"inputs": r.get("inputs", []), "values": r.get("values", []),
              "defaults": {}, "values_version": 1, "dir": "/nowhere",
              "decide": lambda ctx: {
                  "state": "sit", "payload": {},
                  "reason": {"rule": "always", "summary": "By design.",
                             "evidence": [{"label": "A stated figure",
                                           "unit": "count", "actual": 1}]}}})
    r.update(over)
    return r


class TestRenderTypes:
    def test_exactly_six_with_their_tiers(self):
        assert set(contract.RENDER_TYPES) == {
            "commit", "hold", "reduce", "close", "blocked", "unknown"}
        tiers = {k: v["tier"] for k, v in contract.RENDER_TYPES.items()}
        assert tiers == {"commit": "position", "hold": "position",
                         "reduce": "position", "close": "position",
                         "blocked": "evaluation", "unknown": "evaluation"}

    def test_the_set_is_closed_by_construction(self):
        """Nothing outside the host can add a type or retune one."""
        with pytest.raises(TypeError):
            contract.RENDER_TYPES["surge"] = {}
        with pytest.raises(TypeError):
            contract.RENDER_TYPES["hold"]["attention"] = True

    def test_a_strategy_cannot_name_a_new_render_type(self):
        errors = contract.validate_declaration(decl(states=[
            {"id": "s", "name": "S", "render": "surge",
             "description": "An invented display type."}]))
        assert any("six types" in e for e in errors)


class TestDeclarationValidation:
    def test_a_well_formed_declaration_passes(self):
        assert contract.validate_declaration(decl()) == []

    def test_unknown_top_level_keys_fail_loudly(self):
        errors = contract.validate_declaration(decl(surprise=1))
        assert any("surprise" in e for e in errors)

    def test_a_version_without_a_changelog_entry_is_refused(self):
        errors = contract.validate_declaration(decl(version=2))
        assert any("changelog" in e and "2" in e for e in errors)

    def test_the_wrong_contract_version_is_refused(self):
        errors = contract.validate_declaration(decl(contract=99))
        assert any("contract" in e.lower() for e in errors)

    def test_more_states_than_the_cap_is_refused(self):
        states = [{"id": f"s{i}", "name": f"S{i}", "render": "hold",
                   "description": "One of too many."}
                  for i in range(contract.MAX_STATES + 1)]
        errors = contract.validate_declaration(decl(states=states))
        assert any("cap" in e for e in errors)

    def test_duplicate_state_ids_are_refused(self):
        s = {"id": "same", "name": "Same", "render": "hold",
             "description": "Twice."}
        errors = contract.validate_declaration(decl(states=[s, dict(s)]))
        assert any("twice" in e for e in errors)

    def test_the_host_namespace_cannot_be_impersonated(self):
        """Host states are "host:..." — a colon the id alphabet excludes,
        so a strategy structurally cannot declare one."""
        errors = contract.validate_declaration(decl(states=[
            {"id": "host:sneaky", "name": "Sneaky", "render": "hold",
             "description": "Pretends to be the host."}]))
        assert errors
        assert all(":" not in s for s in ("host-sneaky",))  # valid ids exist
        assert any("lowercase letters, digits and hyphens" in e
                   for e in errors)

    def test_a_field_without_an_explanation_is_incomplete(self):
        errors = contract.validate_declaration(decl(inputs=[
            {"id": "cash", "label": "Cash", "type": "number"}]))
        assert any("explain" in e for e in errors)

    def test_a_value_may_not_be_required(self):
        """Every value ships a default. The refusal must teach the test
        that settles it, not merely restate the rule."""
        errors = contract.validate_declaration(decl(values=[
            {"id": "pace", "label": "Pace", "type": "number",
             "required": True, "explain": "A confused declaration."}]))
        assert any("ship a sensible default" in e for e in errors)
        assert any("account balance" in e for e in errors)

    def test_an_id_shared_by_input_and_value_is_refused(self):
        field = {"id": "pace", "label": "Pace", "type": "number",
                 "explain": "Fine on its own."}
        errors = contract.validate_declaration(
            decl(inputs=[dict(field)], values=[dict(field)]))
        assert any("both an input and a value" in e for e in errors)


class TestDecisionValidation:
    def check(self, states, decision):
        return contract.validate_decision(record(states=states), decision)

    def test_an_undeclared_state_is_refused(self):
        errors = self.check(decl()["states"],
                            {"state": "moon", "payload": {},
                             "reason": {"rule": "r", "summary": "s"}})
        assert any("not a state this strategy declared" in e for e in errors)

    def test_a_commit_without_size_is_a_bare_word(self):
        states = [{"id": "buy-in", "name": "Buy in", "render": "commit",
                   "description": "d"}]
        errors = self.check(states, {"state": "buy-in", "payload": {},
                                     "reason": {"rule": "r", "summary": "s"}})
        assert any("size" in e for e in errors)

    def test_a_close_without_a_date_is_refused(self):
        states = [{"id": "out", "name": "Out", "render": "close",
                   "description": "d"}]
        errors = self.check(states, {"state": "out",
                                     "payload": {"when": "someday"},
                                     "reason": {"rule": "r", "summary": "s"}})
        assert any("YYYY-MM-DD" in e for e in errors)

    def test_a_reduce_names_the_level_to_reduce_to(self):
        states = [{"id": "trim", "name": "Trim", "render": "reduce",
                   "description": "d"}]
        errors = self.check(states, {"state": "trim",
                                     "payload": {"to": {"unit": "weight",
                                                        "value": -1}},
                                     "reason": {"rule": "r", "summary": "s"}})
        assert any("level to reduce to" in e for e in errors)

    def test_payload_keys_outside_the_render_type_are_refused(self):
        errors = self.check(decl()["states"],
                            {"state": "sit", "payload": {"vibe": "calm"},
                             "reason": {"rule": "r", "summary": "s"}})
        assert any("vibe" in e for e in errors)

    def test_a_reason_must_name_its_rule(self):
        errors = self.check(decl()["states"],
                            {"state": "sit", "payload": {},
                             "reason": {"summary": "Because."}})
        assert any("rule" in e for e in errors)

    def test_a_blocked_state_says_what_is_owed(self):
        states = [{"id": "ask", "name": "Ask", "render": "blocked",
                   "description": "d"}]
        errors = self.check(states, {"state": "ask", "payload": {"needs": []},
                                     "reason": {"rule": "r", "summary": "s"}})
        assert any("owed" in e for e in errors)


class TestEvaluate:
    def ctx(self, **over):
        c = {"contract": 1, "today": "2026-08-08", "inputs": {}, "values": {}}
        c.update(over)
        return c

    def test_the_happy_path_envelope(self):
        result = contract.evaluate(record(), self.ctx())
        assert result["render"] == "hold"
        assert result["tier"] == "position"
        assert result["state"]["id"] == "sit"
        assert result["produced_by"] == "strategy"
        assert result["strategy"]["id"] == "fixture"
        assert result["reason"]["rule"] == "always"

    def test_a_missing_required_input_blocks_and_names_the_field(self):
        rec = record(inputs=[
            {"id": "account-value", "label": "Account value",
             "type": "number", "required": True,
             "explain": "The total value of the account."}])
        result = contract.evaluate(rec, self.ctx())
        assert result["render"] == "blocked"
        assert result["produced_by"] == "host"
        assert result["state"]["id"] == "host:inputs-missing"
        assert any("Account value" in n for n in result["payload"]["needs"])

    def test_a_mistyped_input_blocks_legibly(self):
        rec = record(inputs=[
            {"id": "account-value", "label": "Account value",
             "type": "number", "required": True,
             "explain": "The total value of the account."}])
        result = contract.evaluate(
            rec, self.ctx(inputs={"account-value": "lots"}))
        assert result["render"] == "blocked"
        assert any("a number" in n for n in result["payload"]["needs"])

    def test_a_throwing_strategy_is_an_error_in_place(self):
        def boom(ctx):
            raise ZeroDivisionError("division by zero")
        result = contract.evaluate(record(decide=boom), self.ctx())
        assert result["render"] == "unknown"
        assert result["produced_by"] == "host"
        assert result["state"]["id"] == "host:strategy-error"
        assert "ZeroDivisionError" in result["reason"]["summary"]

    def test_an_invented_state_is_refused_not_rendered(self):
        def invent(ctx):
            return {"state": "moon", "payload": {},
                    "reason": {"rule": "r", "summary": "s"}}
        result = contract.evaluate(record(decide=invent), self.ctx())
        assert result["state"]["id"] == "host:invalid-decision"
        assert "moon" in result["reason"]["summary"]

    def test_a_non_dict_return_is_contained(self):
        result = contract.evaluate(record(decide=lambda ctx: "hold"),
                                   self.ctx())
        assert result["state"]["id"] == "host:invalid-decision"

    def test_a_strategy_calling_sys_exit_cannot_end_the_program(self):
        import sys

        def quit_(ctx):
            sys.exit(3)
        result = contract.evaluate(record(decide=quit_), self.ctx())
        assert result["state"]["id"] == "host:strategy-error"
        assert "SystemExit" in result["reason"]["summary"]

    def test_evaluate_never_raises_for_any_hostile_return(self):
        """Every one of these escaped as an uncaught TypeError before the
        checks were made total — a plugin author's one-character mistake
        must never crash the host."""
        class Weird:
            def __repr__(self):
                return "weird"

        hostile = [
            Weird(),
            "hold",
            None,
            {"state": ["sit"], "payload": {},
             "reason": {"rule": "r", "summary": "s"}},
            {"state": {"id": "sit"}, "payload": {},
             "reason": {"rule": "r", "summary": "s"}},
            {"state": "sit", "payload": {1: "a", "b": 2},
             "reason": {"rule": "r", "summary": "s"}},
            {"state": "sit", "payload": {}, "reason": {1: "a", "b": 2,
                                                       "rule": "r",
                                                       "summary": "s"}},
            {"state": "sit", "payload": {}, "reason": {"rule": "r",
                                                       "summary": "s"},
             1: "x", "z": "y"},
        ]
        for bad in hostile:
            result = contract.evaluate(record(decide=lambda ctx, b=bad: b),
                                       self.ctx())
            assert result["produced_by"] == "host", bad
            assert result["render"] in ("unknown", "blocked"), bad


class TestEvidenceShape:
    """A citation's own form, before anything is resolved."""

    def cited(self, item, rec=None):
        return contract.validate_decision(rec or record(), {
            "state": "sit", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": [item]}})

    def test_a_verdict_about_the_security_must_cite_something(self):
        errors = contract.validate_decision(record(), {
            "state": "sit", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": []}})
        assert any("has to say what it rested on" in e for e in errors)

    def test_an_evaluation_tier_state_may_cite_nothing(self):
        rec = record(states=[{"id": "dark", "name": "Dark",
                              "render": "unknown", "description": "d"}])
        assert contract.validate_decision(rec, {
            "state": "dark", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": []}}) == []

    def test_exactly_one_subject_is_named(self):
        assert any("exactly one subject" in e
                   for e in self.cited({"measure": "fcf_ttm",
                                        "fact": "position.weight"}))
        assert any("exactly one subject" in e for e in self.cited({}))

    def test_a_strategy_never_restates_a_figure_the_host_knows(self):
        errors = self.cited({"measure": "fcf_ttm", "actual": 999})
        assert any("remove `actual`" in e for e in errors)
        assert any("a restatement can be wrong" in e for e in errors)

    def test_a_stated_figure_must_carry_a_value_or_say_why_not(self):
        errors = self.cited({"label": "Days held", "unit": "days"})
        assert any("exactly one of `actual`" in e for e in errors)

    def test_a_stated_figure_cannot_invent_a_unit(self):
        errors = self.cited({"label": "Vibe", "unit": "vibes", "actual": 1})
        assert any("never invents a rendering" in e for e in errors)

    def test_a_comparator_and_threshold_come_together(self):
        errors = self.cited({"measure": "fcf_ttm", "comparator": "at_least"})
        assert any("come together or not at all" in e for e in errors)

    def test_an_unknown_comparator_is_refused(self):
        errors = self.cited({"measure": "fcf_ttm", "comparator": "vibes_with",
                             "threshold": 1})
        assert any("`comparator` must be one of" in e for e in errors)

    def test_threshold_from_must_name_a_declared_setting(self):
        rec = record(values=[{"id": "cap", "label": "Cap", "type": "number",
                              "explain": "e"}])
        assert self.cited({"measure": "fcf_ttm", "comparator": "at_most",
                           "threshold": 5, "threshold_from": "cap"}, rec) == []
        errors = self.cited({"measure": "fcf_ttm", "comparator": "at_most",
                             "threshold": 5, "threshold_from": "nope"}, rec)
        assert any("neither a value nor an input" in e for e in errors)

    def test_at_only_means_something_for_a_measure(self):
        errors = self.cited({"fact": "position.weight", "at": "2024-12-31"})
        assert any("only means something alongside `measure`" in e
                   for e in errors)


class TestEvidenceResolution:
    """What the host answers. The strategy asked; these are the facts."""

    def ctx(self, **over):
        c = {"contract": 1, "today": "2026-08-08", "inputs": {}, "values": {},
             "measures": {"fcf_ttm": {
                 "current": {"status": "known", "value": 150.0,
                             "source": "computed", "cautions": ["stale"],
                             "provenance": ["10-K S-1"]},
                 "series": {"cadence": "quarterly", "truncated": False,
                            "note": None, "points": [
                                {"period_end": "2023-12-31",
                                 "filed": "2024-02-20", "form": "10-K",
                                 "accession": "S-1", "value": 120.0,
                                 "reason": None}]}}},
             "position": {"weight": {"status": "absent",
                                     "reason": "the journal records no "
                                               "account value"},
                          "shares": 10.0},
             "portfolio": {"slots": {"occupied": 3}}}
        c.update(over)
        return c

    def resolve(self, items, rec=None, ctx=None):
        return contract.resolve_evidence(rec or record(), ctx or self.ctx(),
                                         items)

    def test_a_measure_resolves_to_the_banks_label_and_unit(self):
        [item], errors = self.resolve([{"measure": "fcf_ttm"}])
        assert errors == []
        assert item["subject"]["label"] == \
            "Free cash flow, trailing twelve months"
        assert item["subject"]["unit"] == "usd"
        assert item["observed"]["value"] == 150.0
        assert item["observed"]["cautions"] == ["stale"]

    def test_the_outcome_is_derived_never_claimed(self):
        [passed], _ = self.resolve([{"measure": "fcf_ttm",
                                     "comparator": "at_least",
                                     "threshold": 100}])
        [failed], _ = self.resolve([{"measure": "fcf_ttm",
                                     "comparator": "at_least",
                                     "threshold": 200}])
        assert passed["outcome"] == "pass"
        assert failed["outcome"] == "fail"

    def test_an_absent_value_can_never_come_out_as_a_pass(self):
        ctx = self.ctx()
        ctx["measures"]["fcf_ttm"]["current"] = {
            "status": "absent", "reason": "no filings are stored"}
        for threshold in (-1e9, 0, 1e9):
            [item], _ = self.resolve([{"measure": "fcf_ttm",
                                       "comparator": "at_least",
                                       "threshold": threshold}], ctx=ctx)
            assert item["outcome"] == "unknown"
            assert item["observed"]["reason"] == "no filings are stored"

    def test_an_item_with_no_test_is_noted_not_passed(self):
        [item], _ = self.resolve([{"measure": "fcf_ttm"}])
        assert item["outcome"] == "noted"
        assert item["test"] is None

    def test_a_past_reading_is_cited_by_its_period_end(self):
        [item], errors = self.resolve([{"measure": "fcf_ttm",
                                        "at": "2023-12-31"}])
        assert errors == []
        assert item["observed"]["value"] == 120.0
        assert "10-K" in item["observed"]["provenance"][0]

    def test_a_reading_that_is_not_on_record_says_which_are(self):
        [item], _ = self.resolve([{"measure": "fcf_ttm", "at": "1999-12-31"}])
        assert item["observed"]["status"] == "absent"
        assert "2023-12-31" in item["observed"]["reason"]

    def test_a_host_fact_answers_with_the_hosts_own_reason(self):
        """The weight gap renders honestly without the strategy inventing a
        sentence about it."""
        [item], errors = self.resolve([{"fact": "position.weight"}])
        assert errors == []
        assert item["subject"]["label"] == "Position weight"
        assert item["observed"]["status"] == "absent"
        assert item["observed"]["reason"] == \
            "the journal records no account value"

    def test_a_bare_host_fact_resolves_to_its_figure(self):
        [item], _ = self.resolve([{"fact": "portfolio.slots_occupied"}])
        assert item["observed"]["value"] == 3
        assert item["subject"]["unit"] == "count"

    def test_an_unknown_measure_is_a_request_against_the_host(self):
        _, errors = self.resolve([{"measure": "vibes_5y"}])
        assert any("not in the metric bank" in e for e in errors)
        assert any("request against the host" in e for e in errors)

    def test_an_unknown_host_fact_lists_what_is_reported(self):
        _, errors = self.resolve([{"fact": "portfolio.alpha"}])
        assert any("does not report" in e for e in errors)

    def test_comparing_a_number_against_a_date_is_refused(self):
        _, errors = self.resolve([{"measure": "fcf_ttm",
                                   "comparator": "at_least",
                                   "threshold": "2024-01-01"}])
        assert any("same kind of thing" in e for e in errors)

    def test_ordering_comparators_are_refused_for_yes_no(self):
        _, errors = self.resolve([{"label": "Falsifier fired",
                                   "unit": "yes_no", "actual": True,
                                   "comparator": "at_least",
                                   "threshold": False}])
        assert any("only means something for numbers and dates"
                   in e for e in errors)

    def test_dates_compare_chronologically(self):
        [item], errors = self.resolve([{"label": "Exit due", "unit": "date",
                                        "actual": "2026-12-01",
                                        "comparator": "at_most",
                                        "threshold": "2026-08-08"}])
        assert errors == []
        assert item["outcome"] == "fail"     # December is after August

    def test_a_declared_setting_renders_with_its_own_label(self):
        rec = record(values=[{"id": "cap", "label": "Position cap",
                              "type": "number", "unit": "percent",
                              "explain": "How large a position may get."}])
        [item], errors = self.resolve([{"value": "cap"}], rec=rec,
                                      ctx=self.ctx(values={"cap": 5}))
        assert errors == []
        assert item["subject"]["label"] == "Position cap"
        assert item["subject"]["unit"] == "percent"
        assert item["observed"]["value"] == 5
        assert item["subject"]["explain"]

    def test_a_threshold_says_whose_limit_it_is(self):
        rec = record(values=[{"id": "cap", "label": "Position cap",
                              "type": "number", "unit": "percent",
                              "explain": "e"}])
        [item], _ = self.resolve([{"fact": "position.weight",
                                   "comparator": "at_most", "threshold": 5,
                                   "threshold_from": "cap"}], rec=rec)
        assert item["test"]["threshold_from"] == {
            "kind": "value", "id": "cap", "label": "Position cap"}


class TestEvidenceUnitsTrackTheBank:
    def test_every_bank_unit_can_be_rendered(self):
        """The bank names units; evidence has to be able to render each of
        them, or a measure becomes uncitable the day it is added."""
        from engine import profiles
        bank = profiles.load_bank("metric-bank")
        used = {str(e.get("unit")) for e in bank["entries"]
                if e.get("unit") is not None}
        assert used <= set(contract.EVIDENCE_UNITS)


class TestHostResults:
    def test_blocked_without_an_explicit_needs_list_still_carries_one(self):
        r = contract.host_result("host:strategy-missing",
                                 "The strategy is not on this machine.")
        assert r["render"] == "blocked"
        assert r["payload"]["needs"]

    def test_two_tiers_are_never_conflated(self):
        """Host-produced results land on the evaluation tier — a data or
        setup problem must never count as a portfolio fact."""
        for sid in contract.HOST_STATES:
            r = contract.host_result(sid, "Something is owed.")
            assert r["tier"] == "evaluation"
