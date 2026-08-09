"""The declared-values chain: per-value merging through ordered layers, the
journal always winning, and every unknown or mistyped key failing loudly
with the file and key named — all of them at once."""

from engine import strategy_values


def record():
    return {
        "id": "fixture", "name": "Fixture",
        "values": [
            {"id": "patience", "label": "Patience", "type": "integer",
             "min": 1, "max": 40, "explain": "How long to wait."},
            {"id": "pace", "label": "Pace", "type": "number",
             "min": 0, "max": 100, "explain": "How fast to go."},
            {"id": "strict", "label": "Strict", "type": "boolean",
             "explain": "Whether to be strict."},
        ],
        "defaults": {"patience": 4, "pace": 50.0, "strict": True},
    }


class TestTheChain:
    def test_defaults_stand_when_no_layer_touches_them(self):
        out = strategy_values.resolve(record(), [])
        assert out["values"] == {"patience": 4, "pace": 50.0, "strict": True}
        assert set(out["sources"].values()) == {"shipped default"}
        assert out["errors"] == []

    def test_merging_is_per_value_and_later_layers_win(self):
        out = strategy_values.resolve(record(), [
            ("machine settings", {"pace": 30.0, "patience": 10}),
            ("journal override", {"pace": 20.0}),
        ])
        assert out["values"] == {"patience": 10, "pace": 20.0, "strict": True}
        assert out["sources"] == {"patience": "machine settings",
                                  "pace": "journal override",
                                  "strict": "shipped default"}

    def test_a_new_value_reaches_a_journal_that_overrides_something_else(self):
        """The strategy gained `strict` after this journal overrode `pace`;
        the shipped default must arrive anyway."""
        out = strategy_values.resolve(record(), [
            ("journal override", {"pace": 10.0})])
        assert out["values"]["strict"] is True

    def test_an_unknown_key_names_the_layer_key_and_near_miss(self):
        out = strategy_values.resolve(record(), [
            ("journal override", {"pateince": 9})])
        [error] = out["errors"]
        assert "journal override" in error
        assert "pateince" in error
        assert "patience" in error
        assert "pateince" not in out["values"]

    def test_a_mistyped_value_says_expected_and_got(self):
        out = strategy_values.resolve(record(), [
            ("journal override", {"patience": "soon"})])
        [error] = out["errors"]
        assert "patience" in error and "whole number" in error
        assert out["values"]["patience"] == 4  # the default is not clobbered

    def test_a_boolean_is_not_a_number(self):
        out = strategy_values.resolve(record(), [
            ("journal override", {"pace": True})])
        assert any("pace" in e for e in out["errors"])

    def test_out_of_range_is_refused_with_the_bound(self):
        out = strategy_values.resolve(record(), [
            ("journal override", {"patience": 99})])
        [error] = out["errors"]
        assert "at most 40" in error

    def test_every_problem_reports_at_once(self):
        out = strategy_values.resolve(record(), [
            ("journal override", {"pateince": 9, "pace": "fast",
                                  "mystery": 1})])
        assert len(out["errors"]) == 3


class TestShippedDefaults:
    def test_a_declared_value_without_a_default_is_refused(self):
        errors = strategy_values.check_defaults(
            record(), {"version": 1, "values": {"patience": 4, "pace": 1.0}},
            "fixture/values.yaml")
        assert any('"strict"' in e and "default" in e for e in errors)

    def test_a_missing_file_with_declared_values_is_refused(self):
        errors = strategy_values.check_defaults(record(), None,
                                                "fixture/values.yaml")
        assert errors and "missing" in errors[0]

    def test_no_values_declared_and_no_file_is_fine(self):
        rec = {"id": "bare", "name": "Bare", "values": [], "defaults": {}}
        assert strategy_values.check_defaults(rec, None,
                                              "bare/values.yaml") == []

    def test_an_unversioned_file_is_refused(self):
        errors = strategy_values.check_defaults(
            record(),
            {"values": {"patience": 4, "pace": 1.0, "strict": False}},
            "fixture/values.yaml")
        assert any("version" in e for e in errors)

    def test_unknown_top_level_keys_fail_loudly(self):
        errors = strategy_values.check_defaults(
            record(),
            {"version": 1, "thresholds": {},
             "values": {"patience": 4, "pace": 1.0, "strict": False}},
            "fixture/values.yaml")
        assert any("thresholds" in e for e in errors)
