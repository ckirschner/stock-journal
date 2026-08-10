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


def field(fid="f", **over):
    f = {"id": fid, "label": fid.title(), "type": "number",
         "explain": "What it means, in plain language."}
    f.update(over)
    return f


class TestInputRoles:
    """A role is how a declared input becomes a figure the host reports. The
    host has no journal-level fields of its own — deciding which ones a
    journal collects would be the host deciding how strategies work."""

    def test_the_role_list_is_closed_and_says_what_it_offers(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("beta", role="volatility", unit="ratio")]))
        assert any("`role` must be one of" in e and "cash" in e
                   for e in errors)
        assert any("request against the host" in e for e in errors)

    def test_the_set_is_closed_by_construction(self):
        with pytest.raises(TypeError):
            contract.INPUT_ROLES["leverage"] = {}

    def test_a_role_must_arrive_in_the_unit_the_host_reports_it_in(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("c", role="cash", unit="percent")]))
        assert any("unit: usd" in e for e in errors)
        errors = contract.validate_declaration(decl(inputs=[
            field("c", role="cash", unit="usd", type="text")]))
        assert any("type: number" in e for e in errors)

    def test_two_inputs_cannot_claim_the_same_role(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("c1", role="cash", unit="usd"),
            field("c2", role="cash", unit="usd")]))
        assert any("both claim" in e and "no way to know" in e
                   for e in errors)

    def test_a_value_can_never_carry_a_role(self):
        """A role is a fact about the user's account. A value ships a
        default, and no strategy can ship a default for someone's cash."""
        errors = contract.validate_declaration(decl(values=[
            field("c", role="cash", unit="usd")]))
        assert any("only an input can" in e for e in errors)
        assert any("account balance" in e for e in errors)

    def test_a_claimed_role_resolves_to_the_answer_on_record(self):
        rec = record(inputs=[field("free-cash", role="cash", unit="usd")])
        roles = contract.input_roles(rec, {"free-cash": 5000.0})
        assert roles["cash"] == {"id": "free-cash", "label": "Free-Cash",
                                "value": 5000.0}
        unanswered = contract.input_roles(rec, {})
        assert "Free-Cash" in unanswered["cash"]["reason"]
        assert "value" not in unanswered["cash"]


class TestChoices:
    def test_a_choice_outside_the_offered_set_is_refused(self):
        spec = field("stance", type="text", options=[
            {"value": "in", "label": "Building"},
            {"value": "out", "label": "Paused"}])
        rec = record(inputs=[spec])
        _, problems = contract.check_inputs(rec, {"stance": "sideways"})
        assert any("must be one of: Building, Paused" in p for p in problems)
        assert contract.check_inputs(rec, {"stance": "out"})[0] == \
            {"stance": "out"}

    def test_options_must_fit_the_type_they_are_declared_under(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("n", type="integer", options=[
                {"value": "many", "label": "Many"}])]))
        assert any("a whole number" in e for e in errors)

    def test_options_and_bounds_cannot_both_constrain_one_field(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("n", min=1, options=[{"value": 1, "label": "One"}])]))
        assert any("already say exactly what is allowed" in e for e in errors)

    def test_a_yes_no_answer_is_a_boolean_not_a_two_item_list(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("b", type="boolean", options=[
                {"value": True, "label": "Yes"}])]))
        assert any("already a boolean" in e for e in errors)

    def test_two_options_offering_the_same_answer_are_refused(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("t", type="text", options=[{"value": "a", "label": "A"},
                                             {"value": "a", "label": "Also A"}])]))
        assert any("two options offer" in e for e in errors)


class TestConditionalFields:
    """A question that cannot mean anything must not be asked, and must not
    be answered on the user's behalf either."""

    def gated(self):
        return record(inputs=[
            field("keeps-reserve", type="boolean"),
            field("reserve", required=True,
                  when={"input": "keeps-reserve", "is": True})])

    def test_an_unmet_gate_makes_a_required_field_not_owed(self):
        effective, problems = contract.check_inputs(
            self.gated(), {"keeps-reserve": False})
        assert problems == []
        assert effective == {"keeps-reserve": False}

    def test_a_met_gate_makes_it_owed_again(self):
        _, problems = contract.check_inputs(self.gated(),
                                            {"keeps-reserve": True})
        assert any("Reserve" in p for p in problems)

    def test_a_stale_answer_to_a_gated_off_question_is_never_served(self):
        """Handing over an answer to a question that no longer applies is
        worse than handing over nothing: the strategy cannot tell them
        apart."""
        effective, problems = contract.check_inputs(
            self.gated(), {"keeps-reserve": False, "reserve": 500})
        assert problems == []
        assert "reserve" not in effective

    def test_a_stale_answer_is_still_checked_so_it_cannot_lie_in_wait(self):
        _, problems = contract.check_inputs(
            self.gated(), {"keeps-reserve": False, "reserve": "lots"})
        assert any("expects a number" in p for p in problems)

    def test_an_unanswered_gate_leaves_everything_below_it_unasked(self):
        effective, problems = contract.check_inputs(self.gated(), {})
        assert problems == []
        assert effective == {}

    def test_the_activity_reason_says_what_would_make_it_apply(self):
        """The screen has to be able to say why a field is not being asked,
        in terms of the answer that would bring it back."""
        state = contract.input_activity(self.gated(),
                                        {"keeps-reserve": False})
        assert state["keeps-reserve"] is None
        assert state["reserve"] == \
            'it only applies when "Keeps-Reserve" is yes'
        assert contract.input_activity(self.gated(), {})["reserve"] == \
            'it only applies once "Keeps-Reserve" is answered'

    def test_running_the_check_on_its_own_output_changes_nothing(self):
        """The defensive pass before every decision runs on what the first
        pass returned. If the two disagreed, a journal that saved cleanly
        would then refuse to produce a verdict."""
        rec = self.gated()
        first, _ = contract.check_inputs(rec, {"keeps-reserve": False,
                                               "reserve": 500})
        second, problems = contract.check_inputs(rec, first)
        assert (second, problems) == (first, [])

    def test_a_gate_on_a_choice_fires_on_that_choice(self):
        rec = record(inputs=[
            field("stance", type="text", options=[
                {"value": "in", "label": "Building"},
                {"value": "out", "label": "Paused"}]),
            field("size", when={"input": "stance", "is": "in"})])
        assert contract.check_inputs(rec, {"stance": "in", "size": 4})[0] == \
            {"stance": "in", "size": 4}
        assert contract.check_inputs(rec, {"stance": "out", "size": 4})[0] == \
            {"stance": "out"}

    def several(self):
        """A field that applies under any of several answers — the shape a
        single equality test could not express."""
        return record(inputs=[
            field("stance", type="text", options=[
                {"value": "growth", "label": "Growth"},
                {"value": "blend", "label": "Blend"},
                {"value": "income", "label": "Income"}]),
            field("size", when={"input": "stance", "is": ["growth", "blend"]})])

    def test_a_gate_can_accept_any_of_several_answers(self):
        rec = self.several()
        for answer in ("growth", "blend"):
            assert contract.check_inputs(rec, {"stance": answer,
                                               "size": 4})[0] == \
                {"stance": answer, "size": 4}
        assert contract.check_inputs(rec, {"stance": "income", "size": 4})[0] \
            == {"stance": "income"}
        assert contract.validate_declaration(
            decl(inputs=rec["inputs"])) == []

    def test_the_reason_names_every_answer_that_would_apply(self):
        state = contract.input_activity(self.several(), {"stance": "income"})
        assert state["size"] == \
            'it only applies when "Stance" is Growth or Blend'

    def test_a_list_gate_still_runs_the_check_on_its_own_output(self):
        rec = self.several()
        first, _ = contract.check_inputs(rec, {"stance": "growth", "size": 4})
        second, problems = contract.check_inputs(rec, first)
        assert (second, problems) == (first, [])

    def test_one_bad_answer_in_the_list_refuses_the_whole_gate(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("b", type="boolean"),
            field("a", when={"input": "b", "is": [True, "maybe"]})]))
        assert any("could give" in e for e in errors)

    def test_an_empty_list_is_a_gate_nothing_could_meet(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("b", type="boolean"),
            field("a", when={"input": "b", "is": []})]))
        assert any("empty list" in e for e in errors)

    def test_the_same_answer_twice_is_refused(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("b", type="boolean"),
            field("a", when={"input": "b", "is": [True, True]})]))
        assert any("twice" in e for e in errors)

    def test_a_yes_no_gate_is_not_satisfied_by_a_number(self):
        """Python's `in` compares with `==`, under which 1 equals True. A
        gate listing yes would then open on a 1 from somewhere else, asking
        a question that does not apply."""
        rec = record(inputs=[
            field("b", type="boolean"),
            field("a", when={"input": "b", "is": [True]})])
        assert contract.input_activity(rec, {"b": 1})["a"] is not None

    def test_a_gate_naming_something_undeclared_is_refused(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("a", when={"input": "nowhere", "is": True})]))
        assert any("does not declare as an input" in e for e in errors)

    def test_a_gate_on_an_answer_the_other_field_could_never_give(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("b", type="boolean"),
            field("a", when={"input": "b", "is": "maybe"})]))
        assert any("could give" in e for e in errors)

    def test_a_circle_of_gates_is_refused_once(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("a", type="boolean", when={"input": "b", "is": True}),
            field("b", type="boolean", when={"input": "c", "is": True}),
            field("c", type="boolean", when={"input": "a", "is": True})]))
        circles = [e for e in errors if "circle" in e]
        assert len(circles) == 1, circles

    def test_a_value_can_never_be_conditional(self):
        errors = contract.validate_declaration(decl(
            inputs=[field("b", type="boolean")],
            values=[field("v", when={"input": "b", "is": True})]))
        assert any("only an input can" in e for e in errors)


class TestBoundsThatNameAnotherField:
    def test_a_bound_reads_the_other_answer_and_names_it(self):
        rec = record(inputs=[field("free-cash", role="cash", unit="usd"),
                             field("reserve", max_from="free-cash", min=0)])
        effective, problems = contract.check_inputs(
            rec, {"free-cash": 1000.0, "reserve": 5000.0})
        assert any("at most your Free-Cash (1000)" in p for p in problems)
        assert "reserve" not in effective
        assert contract.check_inputs(
            rec, {"free-cash": 9000.0, "reserve": 5000.0})[1] == []

    def test_a_bound_can_name_a_declared_value(self):
        rec = record(inputs=[field("first-buy", max_from="cap")],
                     values=[field("cap")])
        _, problems = contract.check_inputs(rec, {"first-buy": 20},
                                            values={"cap": 8})
        assert any("at most your Cap (8)" in p for p in problems)

    def test_an_absent_other_answer_is_not_a_failed_bound(self):
        """Absence is never treated as failure. Refusing an answer because a
        different question is unanswered would be inventing a comparison."""
        rec = record(inputs=[field("free-cash", role="cash", unit="usd"),
                             field("reserve", max_from="free-cash")])
        effective, problems = contract.check_inputs(rec, {"reserve": 5000.0})
        assert problems == []
        assert effective == {"reserve": 5000.0}

    def test_a_bound_naming_something_that_is_not_a_number_is_refused(self):
        errors = contract.validate_declaration(decl(
            inputs=[field("a", max_from="note"),
                    field("note", type="text")]))
        assert any("does not declare as a number" in e for e in errors)

    def test_a_bound_naming_itself_is_refused(self):
        errors = contract.validate_declaration(decl(inputs=[
            field("a", max_from="a")]))
        assert any("names itself" in e for e in errors)


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
                   "fix": "settings", "description": "d"}]
        errors = self.check(states, {"state": "ask", "payload": {"needs": []},
                                     "reason": {"rule": "r", "summary": "s"}})
        assert any("owed" in e for e in errors)


class TestABlockedVerdictCannotBecomeADeadEnd:
    """The one state that stops the program has to say how it is started
    again, and the saying has to be something the host can render.

    Two halves, refused in two places, and the split is the point. A state
    that names no way out at all is wrong the moment it is written, so it is
    refused at load, before a journal is ever stamped with it. A state whose
    way out is built from the decision's own citations can only be wrong for
    one particular decision, so it is refused where the decision is — and
    both refusals land on the author rather than on the reader.
    """

    def blocked(self, **over):
        s = {"id": "ask", "name": "Ask", "render": "blocked",
             "fix": "judgement", "description": "d"}
        s.update(over)
        return s

    # -- at load ---------------------------------------------------------
    def test_a_blocked_state_that_names_no_way_out_is_refused_at_load(self):
        s = self.blocked()
        s.pop("fix")
        errors = contract.validate_declaration(decl(states=[s]))
        assert any("nothing to click" in e for e in errors), errors

    def test_a_way_out_the_host_does_not_have_is_refused(self):
        errors = contract.validate_declaration(
            decl(states=[self.blocked(fix="ring-the-author")]))
        assert any("ring-the-author" not in e and "must set `fix`" in e
                   for e in errors), errors

    def test_a_state_that_does_not_stop_cannot_carry_a_way_out(self):
        """A key that silently does nothing is worse than one that refuses,
        and a hold has nothing for a button to resolve."""
        errors = contract.validate_declaration(decl(states=[
            {"id": "sit", "name": "Sit", "render": "hold",
             "fix": "settings", "description": "d"}]))
        assert any("only a `blocked` state" in e for e in errors), errors

    def test_every_way_out_the_host_names_itself_is_on_the_list(self):
        """The host's own states pick from the same table a strategy does,
        so the view can draw either without knowing whose state it has."""
        for sid, state in contract.HOST_STATES.items():
            fix = state["fix"]
            assert fix is None or fix in contract.STATE_FIXES, sid

    def test_the_list_is_closed_by_construction(self):
        with pytest.raises(TypeError):
            contract.STATE_FIXES["email-support"] = {}
        with pytest.raises(TypeError):
            contract.STATE_FIXES["judgement"]["cites"] = None

    # -- at evaluation ---------------------------------------------------
    def evaluated(self, evidence, ctx=None, fix="judgement"):
        rec = record(
            states=[self.blocked(fix=fix)],
            decide=lambda c: {
                "state": "ask",
                "payload": {"needs": ["Answer the moat question."]},
                "reason": {"rule": "owed", "summary": "Something is owed.",
                           "evidence": evidence}})
        return contract.evaluate(rec, ctx or {
            "contract": contract.CONTRACT_VERSION, "today": "2026-08-08",
            "inputs": {}, "values": {},
            "measures": {"moat_durability": {
                "current": {"status": "absent",
                            "reason": "nothing is recorded yet"},
                "series": {"cadence": None, "points": []}}}})

    def test_a_block_that_cites_its_question_stands(self):
        result = self.evaluated([{"measure": "moat_durability"}])
        assert result["render"] == "blocked"
        assert result["produced_by"] == "strategy"
        assert result["state"]["fix"] == "judgement"

    def test_a_block_that_names_its_question_only_in_prose_is_refused(self):
        """The exact failure this exists to close: the verdict says three
        questions are owed, the section that asks them is built from
        citations, and the strategy cited none — so the reader is told
        something is needed and offered nowhere to give it."""
        result = self.evaluated([])
        assert result["state"]["id"] == "host:invalid-decision"
        assert "without citing anything" in result["reason"]["summary"]

    def test_citing_a_figure_is_not_citing_a_question(self):
        """A judgement is a judgement because the bank says so, never
        because the strategy called it one — so a block cannot satisfy this
        by citing the numbers it happened to read."""
        result = self.evaluated([{"label": "Tests passed", "unit": "count",
                                  "actual": 7}])
        assert result["state"]["id"] == "host:invalid-decision"

    def test_a_fixed_screen_owes_no_citation(self):
        """Only a destination built out of citations can be emptied by the
        absence of one. The settings screen is there whatever was cited."""
        result = self.evaluated([], fix="settings")
        assert result["render"] == "blocked"
        assert result["state"]["fix"] == "settings"


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

    def test_a_comparator_needs_a_limit(self):
        errors = self.cited({"measure": "fcf_ttm", "comparator": "at_least"})
        assert any("exactly one of `threshold`" in e for e in errors)

    def test_a_limit_with_no_comparator_says_nothing(self):
        errors = self.cited({"measure": "fcf_ttm", "threshold": 1})
        assert any("no `comparator`" in e for e in errors)

    def test_an_unknown_comparator_is_refused(self):
        errors = self.cited({"measure": "fcf_ttm", "comparator": "vibes_with",
                             "threshold": 1})
        assert any("`comparator` must be one of" in e for e in errors)

    def capped(self):
        return record(values=[{"id": "cap", "label": "Cap", "type": "number",
                               "explain": "e"}])

    def test_a_limit_is_stated_or_cited_and_never_both(self):
        """The misquote the evidence split exists to prevent, at the one
        place it had a hole. Supplying the number AND naming the setting is
        what let "at most your position cap of 5" be written over a cap
        holding 20 — so the pair is unrepresentable rather than compared."""
        errors = self.cited({"measure": "fcf_ttm", "comparator": "at_most",
                             "threshold": 5, "threshold_from": "cap"},
                            self.capped())
        assert any("exactly one of `threshold`" in e for e in errors)
        assert any("a setting that does not hold it" in e for e in errors)

    def test_naming_the_setting_alone_is_the_way_to_attribute_a_limit(self):
        assert self.cited({"measure": "fcf_ttm", "comparator": "at_most",
                           "threshold_from": "cap"}, self.capped()) == []

    def test_threshold_from_must_name_a_declared_setting(self):
        errors = self.cited({"measure": "fcf_ttm", "comparator": "at_most",
                             "threshold_from": "nope"}, self.capped())
        assert any("neither a value nor an input" in e for e in errors)

    def test_threshold_from_needs_a_comparator_to_be_a_limit_at_all(self):
        errors = self.cited({"measure": "fcf_ttm", "threshold_from": "cap"},
                            self.capped())
        assert any("no `comparator`" in e for e in errors)

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
                                 "reason": None,
                                 "cautions": ["a class with no close"],
                                 "provenance": ["shares from the cover"]}]}}},
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

    def test_a_past_reading_carries_its_own_qualification(self):
        """Citing a measure at a past period used to be the one route that
        returned a number with its cautions filed off — the same figure read
        today came back qualified. A screen and a frozen snapshot have no
        other source for it."""
        [item], _ = self.resolve([{"measure": "fcf_ttm", "at": "2023-12-31"}])
        assert item["observed"]["cautions"] == ["a class with no close"]
        # the filing anchors the reading; how it was built follows it
        assert "10-K" in item["observed"]["provenance"][0]
        assert "shares from the cover" in item["observed"]["provenance"]

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

    def capped(self, **over):
        spec = {"id": "cap", "label": "Position cap", "type": "number",
                "unit": "percent", "explain": "e"}
        spec.update(over)
        return record(values=[spec])

    def test_a_cited_limit_is_read_out_of_the_setting_not_the_strategy(self):
        """The whole point. The strategy names which setting; the host reads
        the number. A strategy cannot state a limit and attribute it to a
        setting holding something else, because it never states one."""
        ctx = self.ctx(values={"cap": 5})
        ctx["position"] = {"weight": {"status": "known", "value": 4.0,
                                      "source": "computed", "cautions": [],
                                      "provenance": []}}
        [item], errors = self.resolve(
            [{"fact": "position.weight", "comparator": "at_most",
              "threshold_from": "cap"}], rec=self.capped(), ctx=ctx)
        assert errors == []
        assert item["test"]["threshold"] == 5
        assert item["outcome"] == "pass"

        # …and the same citation against a different setting reads the
        # different number, with nothing in the strategy changed.
        ctx["values"]["cap"] = 3
        [item], _ = self.resolve(
            [{"fact": "position.weight", "comparator": "at_most",
              "threshold_from": "cap"}], rec=self.capped(), ctx=ctx)
        assert item["test"]["threshold"] == 3
        assert item["outcome"] == "fail"

    def test_a_cited_limit_says_whose_it_is_and_how_it_reads(self):
        [item], _ = self.resolve([{"fact": "position.weight",
                                   "comparator": "at_most",
                                   "threshold_from": "cap"}],
                                 rec=self.capped(),
                                 ctx=self.ctx(values={"cap": 5}))
        assert item["test"]["threshold_from"] == {
            "kind": "value", "id": "cap", "label": "Position cap",
            "unit": "percent"}

    def test_a_limit_nobody_answered_is_unknown_and_never_a_pass(self):
        """An optional input sets no limit until it is answered. A test with
        no limit has not been passed — it has not been run."""
        rec = record(inputs=[{"id": "floor", "label": "Your floor",
                              "type": "number", "unit": "usd",
                              "explain": "e"}])
        [item], errors = self.resolve(
            [{"fact": "portfolio.slots_occupied", "comparator": "at_least",
              "threshold_from": "floor"}], rec=rec, ctx=self.ctx(inputs={}))
        assert errors == []
        assert item["outcome"] == "unknown"
        assert item["test"]["threshold"] is None
        assert "Your floor" in item["test"]["absent"]
        # the figure itself was there; it is the limit that was missing
        assert item["observed"]["status"] == "known"

    def test_a_stated_limit_is_never_absent(self):
        [item], _ = self.resolve([{"measure": "fcf_ttm",
                                   "comparator": "at_least",
                                   "threshold": 100}])
        assert item["test"]["absent"] is None
        assert item["test"]["threshold_from"] is None
        assert item["outcome"] == "pass"


class TestOneComputationNotTwo:
    """The failure v5 exists for. A strategy has to choose its state before
    any evidence is resolved, so it used to compare the figures itself — and
    nothing checked that its answer and the host's agreed. A commit could be
    returned beside a citation the host resolved as failed, and both
    rendered, with nothing on screen saying which was wrong."""

    def ctx(self, **over):
        c = TestEvidenceResolution().ctx()
        c.update(over)
        return c

    ITEMS = [
        {"measure": "fcf_ttm", "comparator": "at_least", "threshold": 100},
        {"measure": "fcf_ttm", "comparator": "at_least", "threshold": 200},
        {"measure": "fcf_ttm", "comparator": "above", "threshold": 150},
        {"measure": "fcf_ttm", "at": "2023-12-31", "comparator": "at_most",
         "threshold": 130},
        {"measure": "fcf_ttm", "at": "1999-12-31", "comparator": "at_most",
         "threshold": 130},
        {"measure": "fcf_ttm"},
        {"fact": "portfolio.slots_occupied", "comparator": "below",
         "threshold": 5},
        {"fact": "position.weight", "comparator": "at_most", "threshold": 5},
        {"label": "Worked out here", "unit": "count", "actual": 4,
         "comparator": "at_least", "threshold": 4},
        {"label": "Nothing to read", "unit": "count",
         "absent": "no reason to have one"},
    ]

    def test_test_and_resolve_evidence_always_agree(self):
        """The guarantee, stated the only way it can be: whatever a strategy
        is told while deciding is what the reader is shown afterwards."""
        rec, ctx = record(), self.ctx()
        rendered, errors = contract.resolve_evidence(rec, ctx, self.ITEMS)
        assert errors == []
        assert len(rendered) == len(self.ITEMS)
        for item, row in zip(self.ITEMS, rendered):
            assert contract.test(ctx, item) == row["outcome"], item

    def test_a_cited_limit_reaches_both_sides(self):
        rec = record(values=[{"id": "cap", "label": "Cap", "type": "number",
                              "unit": "percent",
                              "source": {"name": "a fixture",
                                         "reasoning": True},
                              "explain": "e"}])
        item = {"fact": "portfolio.slots_occupied", "comparator": "at_most",
                "threshold_from": "cap"}
        for cap, want in ((5, "pass"), (2, "fail")):
            ctx = self.ctx(values={"cap": cap})
            [row], _ = contract.resolve_evidence(rec, ctx, [item])
            assert row["outcome"] == want
            assert contract.test(ctx, item) == want

    def test_an_absent_figure_is_unknown_and_never_a_pass(self):
        for threshold in (-1e9, 0, 1e9):
            assert contract.test(self.ctx(), {
                "fact": "position.weight", "comparator": "at_least",
                "threshold": threshold}) == "unknown"

    def test_an_unanswered_limit_is_unknown_and_never_a_pass(self):
        assert contract.test(self.ctx(), {
            "fact": "portfolio.slots_occupied", "comparator": "at_least",
            "threshold_from": "never-declared"}) == "unknown"

    def test_an_item_with_no_comparator_is_noted(self):
        assert contract.test(self.ctx(), {"measure": "fcf_ttm"}) == "noted"

    def test_a_citation_the_host_cannot_answer_is_loud(self):
        """Not "unknown". A misspelled measure id reading as a missing
        figure would be a fault in the strategy wearing the clothes of a
        fact about the security."""
        for bad in ({"measure": "vibes_5y"},
                    {"fact": "portfolio.alpha"},
                    {"measure": "fcf_ttm", "comparator": "vibes_with",
                     "threshold": 1},
                    {"measure": "fcf_ttm", "comparator": "at_least",
                     "threshold": "2024-01-01"},
                    {"measure": "fcf_ttm", "fact": "position.weight"},
                    "not an item"):
            with pytest.raises(ValueError):
                contract.test(self.ctx(), bad)

    def test_a_strategy_cannot_write_to_what_it_was_handed(self):
        """`test` and the resolution afterwards read the same context, so
        they can only stay in step if nothing between them can edit it."""
        seen = {}

        def peek(ctx):
            seen["ctx"] = ctx
            return {"state": "sit", "payload": {},
                    "reason": {"rule": "r", "summary": "s",
                               "evidence": [{"measure": "fcf_ttm"}]}}

        contract.evaluate(record(decide=peek), self.ctx())
        ctx = seen["ctx"]
        with pytest.raises(TypeError):
            ctx["values"] = {"anything": 1}
        with pytest.raises(TypeError):
            ctx["measures"]["fcf_ttm"]["current"]["value"] = 1
        with pytest.raises(AttributeError):
            ctx["measures"]["fcf_ttm"]["series"]["points"].append({})
        # …and it still reads exactly as a plain context does.
        assert ctx["measures"]["fcf_ttm"]["current"]["value"] == 150.0
        assert len(ctx["measures"]["fcf_ttm"]["series"]["points"]) == 1
        assert ctx.get("today") == "2026-08-08"


class TestGroups:
    """A group says which citations were requirements. That is what lets the
    host count a rollup for itself, and what lets it refuse a decision to
    buy that its own evidence contradicts."""

    def rec(self, **over):
        r = record(values=[{"id": "need", "label": "Core tests needed",
                            "type": "integer",
                            "source": {"name": "a fixture",
                                       "reasoning": True},
                            "explain": "e"}])
        r.update(over)
        return r

    def ctx(self, **over):
        c = TestEvidenceResolution().ctx(values={"need": 2})
        c.update(over)
        return c

    def cited(self, groups, evidence, rec=None):
        return contract.validate_decision(rec or self.rec(), {
            "state": "sit", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": evidence,
                       "groups": groups}})

    # -- the declaration ---------------------------------------------------

    def test_a_row_cannot_name_a_heading_that_does_not_exist(self):
        errors = self.cited([{"id": "a", "name": "A"}],
                            [{"measure": "fcf_ttm", "group": "b"}])
        assert any("does not declare" in e for e in errors)

    def test_a_heading_over_no_rows_is_refused(self):
        errors = self.cited([{"id": "a", "name": "A"},
                             {"id": "b", "name": "B"}],
                            [{"measure": "fcf_ttm", "group": "a"}])
        assert any("nothing is cited under it" in e for e in errors)

    def test_the_rows_of_one_group_have_to_be_together(self):
        """A heading a screen would have to reopen halfway down the list is
        not a thing a reader can follow."""
        errors = self.cited(
            [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
            [{"measure": "fcf_ttm", "group": "a"},
             {"fact": "position.shares", "group": "b"},
             {"fact": "portfolio.slots_occupied", "group": "a"}])
        assert any("are not together" in e for e in errors)

    def test_an_invented_requirement_is_refused(self):
        errors = self.cited([{"id": "a", "name": "A", "requires": "mostly"}],
                            [{"measure": "fcf_ttm", "group": "a"}])
        assert any("`requires` must be one of" in e for e in errors)

    def test_leaving_requires_out_means_all(self):
        """The strict reading, deliberately. An author who says nothing gets
        the rule that refuses a contradiction, not the one that allows it."""
        assert self.cited([{"id": "a", "name": "A"}],
                          [{"measure": "fcf_ttm", "group": "a"}]) == []
        [g] = contract.resolve_groups(
            self.rec(), self.ctx(), [{"id": "a", "name": "A"}],
            contract.resolve_evidence(
                self.rec(), self.ctx(),
                [{"measure": "fcf_ttm", "comparator": "at_least",
                  "threshold": 999, "group": "a"}])[0])
        assert g["requires"] == "all"
        assert g["outcome"] == "fail"

    def test_a_counted_bar_is_stated_or_cited_and_never_both(self):
        errors = self.cited(
            [{"id": "a", "name": "A", "requires": "at_least",
              "threshold": 2, "threshold_from": "need"}],
            [{"measure": "fcf_ttm", "group": "a"}])
        assert any("exactly one of `threshold`" in e for e in errors)

    def test_a_bar_only_means_something_where_something_is_counted(self):
        errors = self.cited(
            [{"id": "a", "name": "A", "requires": "noted", "threshold": 2}],
            [{"measure": "fcf_ttm", "group": "a"}])
        assert any("sets no limit" in e for e in errors)

    def test_a_counted_bar_counts_rows_and_not_dollars(self):
        errors = self.cited(
            [{"id": "a", "name": "A", "requires": "at_least",
              "threshold": 2.5}], [{"measure": "fcf_ttm", "group": "a"}])
        assert any("whole number" in e for e in errors)

    # -- the rollup --------------------------------------------------------

    def rollup(self, group, items):
        rec, ctx = self.rec(), self.ctx()
        rendered, errors = contract.resolve_evidence(rec, ctx, items)
        assert errors == []
        [g] = contract.resolve_groups(rec, ctx, [group], rendered)
        return g

    def rows(self, *thresholds):
        """One citation per threshold; 999 fails, 1 passes, None is a figure
        the host could not observe."""
        out = []
        for t in thresholds:
            out.append({"measure": "fcf_ttm", "comparator": "at_least",
                        "threshold": t, "group": "a"}
                       if t is not None else
                       {"fact": "position.weight", "comparator": "at_least",
                        "threshold": 1, "group": "a"})
        return out

    def test_the_host_counts_the_passes_itself(self):
        g = self.rollup({"id": "a", "name": "A", "requires": "at_least",
                         "threshold_from": "need"},
                        self.rows(1, 1, 999))
        assert (g["passed"], g["failed"], g["unknown"]) == (2, 1, 0)
        assert g["tested"] == 3
        assert g["outcome"] == "pass"
        assert g["test"]["threshold"] == 2
        assert g["test"]["threshold_from"]["label"] == "Core tests needed"

    def test_short_of_the_bar_with_nothing_left_to_read_is_a_failure(self):
        g = self.rollup({"id": "a", "name": "A", "requires": "at_least",
                         "threshold_from": "need"},
                        self.rows(1, 999, 999))
        assert g["outcome"] == "fail"

    def test_short_of_the_bar_with_a_row_unread_is_undecided(self):
        """Absence is not a verdict in the rollup either. One pass, one
        failure and one unreadable against a bar of two could still get
        there, so nothing is claimed."""
        g = self.rollup({"id": "a", "name": "A", "requires": "at_least",
                         "threshold_from": "need"},
                        self.rows(1, 999, None))
        assert (g["passed"], g["unknown"]) == (1, 1)
        assert g["outcome"] == "unknown"

    def test_a_bar_nobody_answered_leaves_the_group_undecided(self):
        rec = record(inputs=[{"id": "floor", "label": "Your floor",
                              "type": "integer", "explain": "e"}])
        rendered, _ = contract.resolve_evidence(rec, self.ctx(),
                                                self.rows(1, 1))
        [g] = contract.resolve_groups(
            rec, self.ctx(inputs={}),
            [{"id": "a", "name": "A", "requires": "at_least",
              "threshold_from": "floor"}], rendered)
        assert g["outcome"] == "unknown"
        assert g["test"]["absent"]

    def test_a_noted_group_is_counted_and_never_judged(self):
        g = self.rollup({"id": "a", "name": "A", "requires": "noted"},
                        self.rows(999, 999))
        assert g["outcome"] == "noted"
        assert (g["passed"], g["failed"]) == (0, 2)

    def test_rows_with_no_test_are_not_counted_against_a_requirement(self):
        g = self.rollup({"id": "a", "name": "A", "requires": "all"},
                        self.rows(1) + [{"measure": "fcf_ttm", "group": "a"}])
        assert g["members"] == 2
        assert g["tested"] == 1
        assert g["outcome"] == "pass"


class TestACommitCannotContradictItsOwnEvidence:
    """The backstop. `contract.test` means a strategy has no reason to
    compare a figure itself; this is what happens when one does anyway."""

    STATES = [{"id": "buy-in", "name": "Buy in", "render": "commit",
               "description": "d"},
              {"id": "sit", "name": "Sit", "render": "hold",
               "description": "d"}]

    def ctx(self, **over):
        c = TestEvidenceResolution().ctx(values={"need": 2})
        c.update(over)
        return c

    def verdict(self, evidence, groups=None, state="buy-in"):
        payload = ({"size": {"unit": "weight", "value": 5}, "condition": None}
                   if state == "buy-in" else {})
        reason = {"rule": "r", "summary": "s", "evidence": evidence}
        if groups:
            reason["groups"] = groups
        rec = record(states=self.STATES,
                     values=[{"id": "need", "label": "Core tests needed",
                              "type": "integer",
                              "source": {"name": "a fixture",
                                         "reasoning": True},
                              "explain": "e"}],
                     decide=lambda ctx: {"state": state, "payload": payload,
                                         "reason": reason})
        return contract.evaluate(rec, self.ctx())

    FAILS = {"measure": "fcf_ttm", "comparator": "at_least",
             "threshold": 999}
    PASSES = {"measure": "fcf_ttm", "comparator": "at_least", "threshold": 1}

    def test_a_buy_beside_a_failed_row_is_refused(self):
        r = self.verdict([self.FAILS])
        assert r["state"]["id"] == "host:invalid-decision"
        assert "put capital in against its own evidence" in \
            r["reason"]["summary"]

    def test_the_same_row_under_a_hold_is_perfectly_fine(self):
        """A hold may legitimately cite failures — that is often why it is a
        hold — so the check is narrow by necessity."""
        r = self.verdict([self.FAILS], state="sit")
        assert r["state"]["id"] == "sit"
        assert r["reason"]["evidence"][0]["outcome"] == "fail"

    def test_a_buy_beside_a_clean_row_stands(self):
        r = self.verdict([self.PASSES])
        assert r["state"]["id"] == "buy-in"

    def test_a_failure_inside_a_group_that_demands_all_is_refused(self):
        r = self.verdict([{**self.PASSES, "group": "a"},
                          {**self.FAILS, "group": "a"}],
                         [{"id": "a", "name": "Knockouts", "requires": "all"}])
        assert r["state"]["id"] == "host:invalid-decision"
        assert "Knockouts" in r["reason"]["summary"]

    def test_short_of_a_counted_bar_is_refused(self):
        r = self.verdict([{**self.PASSES, "group": "a"},
                          {**self.FAILS, "group": "a"},
                          {**self.FAILS, "group": "a"}],
                         [{"id": "a", "name": "Core", "requires": "at_least",
                           "threshold_from": "need"}])
        assert r["state"]["id"] == "host:invalid-decision"
        assert "needed 2 of its 3 tests" in r["reason"]["summary"]

    def test_meeting_a_counted_bar_stands_even_with_failures_under_it(self):
        """Six of eight is a real rule, and the two that failed are exactly
        what the group exists to permit."""
        r = self.verdict([{**self.PASSES, "group": "a"},
                          {**self.PASSES, "group": "a"},
                          {**self.FAILS, "group": "a"}],
                         [{"id": "a", "name": "Core", "requires": "at_least",
                           "threshold_from": "need"}])
        assert r["state"]["id"] == "buy-in"

    def test_a_requirement_nobody_could_evaluate_is_refused(self):
        """The strategy said all of these must pass. One of them was never
        checked, so it has not been met — and a buy standing on it is
        absence read as success."""
        unreadable = {"fact": "position.weight", "comparator": "at_least",
                      "threshold": 1, "group": "a"}
        r = self.verdict([{**self.PASSES, "group": "a"}, unreadable],
                         [{"id": "a", "name": "Knockouts", "requires": "all"}])
        assert r["state"]["id"] == "host:invalid-decision"
        assert "could not be worked out" in r["reason"]["summary"]

    def test_a_noted_group_may_fail_freely(self):
        r = self.verdict([{**self.FAILS, "group": "b"}],
                         [{"id": "b", "name": "Bonus", "requires": "noted"}])
        assert r["state"]["id"] == "buy-in"

    def test_an_ungrouped_row_nobody_could_read_is_not_a_contradiction(self):
        """Nothing declared it a requirement. A rule that reads "respect the
        reserve, if you keep one" cites the test honestly and reports the
        limit as unset, and refusing that would forbid a true thing."""
        r = self.verdict([{"fact": "position.weight",
                           "comparator": "at_least", "threshold": 1}])
        assert r["state"]["id"] == "buy-in"
        assert r["reason"]["evidence"][0]["outcome"] == "unknown"


class TestADeclaredValueSaysWhereItsNumberCameFrom:
    def value(self, **over):
        v = {"id": "cap", "label": "Cap", "type": "number",
             "source": {"name": "The Intelligent Investor, ch. 14",
                        "reasoning": True},
             "explain": "How large a position may get."}
        v.update(over)
        return contract.validate_declaration(decl(values=[v]))

    def test_a_well_formed_source_passes(self):
        assert self.value() == []
        assert self.value(source={"name": "an expert report",
                                  "reasoning": False}) == []

    def test_a_value_with_no_source_is_refused(self):
        v = {"id": "cap", "label": "Cap", "type": "number", "explain": "e"}
        errors = contract.validate_declaration(decl(values=[v]))
        assert any("needs a `source`" in e for e in errors)

    def test_the_source_has_to_name_something(self):
        errors = self.value(source={"name": "  ", "reasoning": True})
        assert any("`source.name` must name" in e for e in errors)

    def test_whose_reasoning_it_is_has_to_be_answered(self):
        """The distinction the prose version kept losing: a level with
        borrowed authority and homemade reasoning is the case worth being
        able to tell apart."""
        errors = self.value(source={"name": "a report"})
        assert any("exactly" in e for e in errors)
        errors = self.value(source={"name": "a report", "reasoning": "yes"})
        assert any("must be true or false" in e for e in errors)

    def test_an_input_has_no_number_of_its_own_to_attribute(self):
        errors = contract.validate_declaration(decl(inputs=[
            {"id": "cash", "label": "Cash", "type": "number",
             "source": {"name": "you", "reasoning": True},
             "explain": "e"}]))
        assert any("only a value can" in e for e in errors)


class TestEveryHostFactExplainsItself:
    def test_all_of_them_carry_plain_language(self):
        """A number on a screen the reader cannot find out the meaning of is
        an incomplete number, and a host fact has no bank entry and no
        author's `explain` to fall back on."""
        for fid, spec in contract.HOST_FACTS.items():
            assert isinstance(spec["explain"], str), fid
            assert len(spec["explain"]) > 120, fid

    def test_the_explanation_reaches_the_resolved_citation(self):
        [item], _ = contract.resolve_evidence(
            record(), TestEvidenceResolution().ctx(),
            [{"fact": "portfolio.slots_occupied"}])
        assert item["subject"]["explain"] == \
            contract.HOST_FACTS["portfolio.slots_occupied"]["explain"]


class TestMonthsHeldIsAHostFact:
    def test_it_is_reported_and_renders_as_months(self):
        spec = contract.HOST_FACTS["position.months_held"]
        assert spec["unit"] == "months"
        assert "months" in contract.EVIDENCE_UNITS

    def test_it_resolves_and_compares(self):
        ctx = TestEvidenceResolution().ctx()
        ctx["position"]["months_held"] = 26
        [item], errors = contract.resolve_evidence(record(), ctx, [
            {"fact": "position.months_held", "comparator": "below",
             "threshold": 24}])
        assert errors == []
        assert item["observed"]["value"] == 26
        assert item["subject"]["unit"] == "months"
        assert item["outcome"] == "fail"

    def test_no_holding_is_absence_and_never_nought(self):
        """Nought months held is a confident answer about a position that
        does not exist, which is worse than admitting there is nothing to
        count."""
        ctx = TestEvidenceResolution().ctx()
        ctx["position"]["months_held"] = None
        [item], _ = contract.resolve_evidence(record(), ctx, [
            {"fact": "position.months_held", "comparator": "below",
             "threshold": 24}])
        assert item["observed"]["status"] == "absent"
        assert item["outcome"] == "unknown"

    def test_the_context_builds_it_the_way_the_host_counts(self, tmp_path):
        from engine import context
        security = {"ticker": "ARBR", "name": "Arbor Mills",
                    "lots": [{"id": "L1", "kind": "buy",
                              "date": "2024-02-29", "shares": 10.0,
                              "price": 5.0,
                              "recorded": "2024-02-29T00:00:00+00:00"}]}
        ctx = context.build_context(security, [security], {}, {},
                                    as_of="2026-02-28")
        assert ctx["position"]["opened"] == "2024-02-29"
        assert ctx["position"]["months_held"] == 24

    def test_a_security_you_do_not_own_has_no_count_and_not_a_nought(self):
        """Nought is a confident answer, and a rule reading "held fewer than
        twenty-four months" would find an idea nobody owns comfortably
        inside its holding period."""
        from engine import context
        idea = {"ticker": "NONE", "name": "Never Bought", "lots": []}
        ctx = context.build_context(idea, [idea], {}, {})
        assert ctx["position"]["held"] is False
        assert ctx["position"]["months_held"] is None
        [item], _ = contract.resolve_evidence(record(), ctx, [
            {"fact": "position.months_held", "comparator": "below",
             "threshold": 24}])
        assert item["outcome"] == "unknown"


class TestEvidenceUnitsTrackTheBank:
    def test_every_bank_unit_can_be_rendered(self):
        """The bank names units; evidence has to be able to render each of
        them, or a measure becomes uncitable the day it is added."""
        from engine import bank as bank_mod
        bank = bank_mod.load_bank()
        used = {str(e.get("unit")) for e in bank["entries"]
                if e.get("unit") is not None}
        assert used <= set(contract.EVIDENCE_UNITS)


class TestMonthArithmetic:
    """Month arithmetic is the host's, and both directions come out of one
    function so they cannot drift. Every expected value below was worked out
    on a calendar, never through the code under test."""

    def test_adding_months_clamps_to_a_shorter_month(self):
        assert contract.months_after("2024-05-15", 24) == "2026-05-15"
        assert contract.months_after("2024-02-29", 24) == "2026-02-28"
        assert contract.months_after("2025-01-31", 1) == "2025-02-28"
        assert contract.months_after("2024-01-31", 1) == "2024-02-29"
        assert contract.months_after("2025-12-31", 24) == "2027-12-31"
        assert contract.months_after("2025-01-31", 0) == "2025-01-31"

    def test_counting_months_agrees_with_the_calendar(self):
        assert contract.months_between("2024-05-15", "2026-05-14") == 23
        assert contract.months_between("2024-05-15", "2026-05-15") == 24
        # The clamped case. Opened 29 February, due 28 February two years
        # later: on that day the position has been held 24 months, and any
        # count that says 23 closes a position while reporting its holding
        # period as unfinished.
        assert contract.months_between("2024-02-29", "2026-02-28") == 24
        assert contract.months_between("2024-02-29", "2026-02-27") == 23

    def test_neither_invents_an_answer(self):
        assert contract.months_after("not a day", 3) is None
        assert contract.months_after("2024-05-15", None) is None
        assert contract.months_after("2024-05-15", True) is None
        assert contract.months_between(None, "2026-05-15") is None
        assert contract.months_between("2024-05-15", "") is None

    def test_the_two_directions_can_never_disagree(self):
        """`months_held >= n` has to be exactly `today >= the due date`, or a
        clock fires on a day its own evidence calls early. Swept over every
        start date in four years against every holding period a strategy is
        likely to set, because the disagreement only appeared on month ends.
        """
        from datetime import date, timedelta
        start = date(2024, 1, 1)
        for days in range(0, 4 * 365):
            opened = start + timedelta(days=days)
            for limit in (1, 6, 18, 24, 36):
                due = date.fromisoformat(
                    contract.months_after(opened.isoformat(), limit))
                for probe in (due - timedelta(days=1), due,
                              due + timedelta(days=1)):
                    counted = contract.months_between(
                        opened.isoformat(), probe.isoformat()) >= limit
                    assert (probe >= due) == counted, (opened, limit, probe)


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


class TestAStrategyCannotRestateTheHostsFigures:
    """The whole point of the evidence split is that a strategy asks the
    question and the host answers it, so a strategy cannot misquote the
    host's own numbers. That only holds if the context the host resolves
    against is not the same object the strategy just had its hands on."""

    def _record(self):
        from pathlib import Path
        from engine import strategy_loader
        root = Path(__file__).resolve().parent / "fixtures" / "strategies"
        strategies, reports = strategy_loader.discover([root])
        assert "tamper" in strategies, [r["errors"] for r in reports]
        return strategies["tamper"]

    def _ctx(self):
        return {
            "contract": contract.CONTRACT_VERSION,
            "today": "2026-08-08",
            "security": {"ticker": "SYN", "name": "Synthetic", "cik": 1},
            "measures": {"fcf_ttm": {
                "current": {"status": "absent",
                            "reason": "no filing data is stored"},
                "series": {"cadence": "annual", "points": [], "note": None,
                           "truncated": False}}},
            "price": {"latest": {"status": "absent", "reason": "none"},
                      "closes": [], "events": []},
            "position": {"held": True, "lots": [], "shares": 3.0,
                         "cost_basis": 10.0,
                         "market_value": {"status": "absent",
                                          "reason": "none"},
                         "weight": {"status": "absent", "reason": "none"}},
            "portfolio": {"cash": {"status": "absent", "reason": "none"},
                          "account_value": {"status": "absent",
                                            "reason": "none"},
                          "slots": {"occupied": 1}, "holdings": []},
            "values": {}, "inputs": {},
        }

    def test_what_the_host_reports_is_what_the_host_computed(self):
        ctx = self._ctx()
        result = contract.evaluate(self._record(), ctx)
        assert result["state"]["id"] == "said-so"
        by_id = {e["subject"]["id"]: e for e in result["reason"]["evidence"]}
        # the measure the strategy tried to invent a value for is still absent
        assert by_id["fcf_ttm"]["observed"]["status"] == "absent"
        assert by_id["fcf_ttm"]["observed"]["reason"] == \
            "no filing data is stored"
        # and the host fact it tried to inflate still reads what was recorded
        assert by_id["position.shares"]["observed"]["value"] == 3.0

    def test_the_caller_gets_its_context_back_unharmed(self):
        """The journal and the caches are protected by the deep copy on the
        way in; this is the other half — one evaluation cannot change what
        the next one sees."""
        ctx = self._ctx()
        contract.evaluate(self._record(), ctx)
        assert ctx["measures"]["fcf_ttm"]["current"]["status"] == "absent"
        assert ctx["position"]["shares"] == 3.0
        assert ctx["values"] == {}
