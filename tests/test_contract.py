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
                  "reason": {"rule": "always", "summary": "By design."}}})
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
        """Every value ships a default; something the user must supply is
        an input wearing the wrong hat."""
        errors = contract.validate_declaration(decl(values=[
            {"id": "pace", "label": "Pace", "type": "number",
             "required": True, "explain": "A confused declaration."}]))
        assert any("input, not a value" in e for e in errors)

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
