"""Discovery and defensive loading: broken bundles are skipped with legible
messages, versions are checked, declarations are read without running any
decision logic, and one bad plugin can never sink the rest."""

from pathlib import Path

import pytest

from engine import contract, strategy_loader

FIXTURES = Path(__file__).parent / "fixtures" / "strategies"


def load():
    return strategy_loader.discover([FIXTURES])


def report_for(reports, dirname):
    return next(r for r in reports if Path(r["dir"]).name == dirname)


class TestDiscovery:
    def test_the_sound_bundle_loads_among_the_broken(self):
        strategies, _ = load()
        assert "sound" in strategies
        assert strategies["sound"]["version"] == 2
        assert strategies["sound"]["values_version"] == 3
        assert strategies["sound"]["defaults"] == {"first-stage": 40}

    def test_every_bundle_gets_a_report(self):
        _, reports = load()
        assert {Path(r["dir"]).name for r in reports} >= {
            "sound", "broken-syntax", "wrong-contract", "silent-version",
            "mistyped-values", "eager", "invents", "twin-a", "twin-b",
            "corrupt-values", "shipped-data"}

    def test_a_missing_root_is_simply_empty(self):
        strategies, reports = strategy_loader.discover(
            [FIXTURES / "no-such-dir"])
        assert strategies == {} and reports == []

    def test_the_shipped_strategies_are_discovered_by_default(self):
        """The default root, with no argument. What ships is exactly the two
        real strategies — the contract scaffold that used to sit beside them
        is gone, because it was offered in the create-journal picker and a
        journal created against it rendered verdicts built on one invented
        threshold."""
        strategies, _ = strategy_loader.discover()
        assert sorted(strategies) == ["buffett", "graham"]


class TestRefusals:
    def test_a_syntax_error_is_skipped_with_the_file_named(self):
        strategies, reports = load()
        r = report_for(reports, "broken-syntax")
        assert not r["ok"]
        assert any("broken-syntax/strategy.py" in e for e in r["errors"])
        assert "sound" in strategies  # the others still load

    def test_the_wrong_contract_version_is_refused(self):
        strategies, reports = load()
        r = report_for(reports, "wrong-contract")
        assert not r["ok"]
        assert any("contract" in e.lower() for e in r["errors"])
        assert "wrong-contract" not in strategies

    def test_a_version_that_does_not_say_what_changed_is_refused(self):
        _, reports = load()
        r = report_for(reports, "silent-version")
        assert not r["ok"]
        assert any("changelog" in e for e in r["errors"])

    def test_a_mistyped_default_names_file_key_and_near_miss(self):
        _, reports = load()
        r = report_for(reports, "mistyped-values")
        assert not r["ok"]
        joined = " ".join(r["errors"])
        assert "mistyped-values/values.yaml" in joined
        assert "pateince" in joined
        assert "patience" in joined  # the suggestion

    def test_a_corrupt_values_file_says_so_never_that_it_is_missing(self):
        _, reports = load()
        r = report_for(reports, "corrupt-values")
        assert not r["ok"]
        joined = " ".join(r["errors"])
        assert "could not be read as YAML" in joined
        assert "missing" not in joined   # the file is right there

    def test_an_empty_values_file_names_the_real_fix(self, tmp_path):
        bundle = tmp_path / "empty-values"
        bundle.mkdir()
        (bundle / "strategy.py").write_text(
            "STRATEGY = {'id': 'empty-values', 'name': 'E', 'summary': 's',"
            f" 'version': 1, 'contract': {contract.CONTRACT_VERSION},"
            " 'changelog': {1: 'f'},"
            " 'states': [{'id': 's', 'name': 'n', 'render': 'hold',"
            " 'description': 'd'}],"
            " 'values': [{'id': 'v', 'label': 'V', 'type': 'number',"
            " 'source': {'name': 'a fixture', 'reasoning': True},"
            " 'explain': 'e'}]}\ndef decide(ctx): pass\n")
        (bundle / "values.yaml").write_text("# nothing but a comment\n")
        _, reports = strategy_loader.discover([tmp_path])
        [r] = reports
        assert not r["ok"]
        assert any("is empty" in e for e in r["errors"])
        assert not any("missing" in e for e in r["errors"])

    def test_twin_ids_refuse_both_claimants(self):
        strategies, reports = load()
        assert "twin" not in strategies
        for name in ("twin-a", "twin-b"):
            r = report_for(reports, name)
            assert not r["ok"]
            assert any("twin-a" in e and "twin-b" in e for e in r["errors"])


class TestLogicIsNeverRunAtLoad:
    def test_the_eager_bundle_loads_and_its_declaration_is_readable(self):
        """eager's decide raises unconditionally. If loading executed any
        decision logic, discovery itself would fail — instead the record
        exposes states and inputs for the setup screen."""
        strategies, _ = load()
        rec = strategies["eager"]
        assert [s["id"] for s in rec["states"]] == ["unreachable"]
        assert rec["inputs"][0]["id"] == "a-number"

    def test_when_its_logic_does_run_the_failure_stays_in_place(self):
        strategies, _ = load()
        result = contract.evaluate(strategies["eager"],
                                   {"inputs": {}, "values": {}})
        assert result["render"] == "unknown"
        assert result["state"]["id"] == "host:strategy-error"
        assert "decide must never run at load time" \
            in result["reason"]["summary"]
        assert "strategy.py line" in result["reason"]["summary"]

    def test_invented_vocabulary_is_refused_at_evaluation(self):
        strategies, _ = load()
        result = contract.evaluate(strategies["invents"],
                                   {"inputs": {}, "values": {}})
        assert result["state"]["id"] == "host:invalid-decision"
        assert "moon-shot" in result["reason"]["summary"]


class TestShippedReferenceData:
    """The third channel: static data a bundle ships, which the host loads
    so a strategy never opens a file itself."""

    def test_declared_files_are_loaded_and_handed_back(self):
        strategies, _ = load()
        rec = strategies["shipped-data"]
        assert set(rec["reference"]) == {"sectors.yaml"}
        assert rec["reference"]["sectors.yaml"]["sectors"]["SYN"] \
            == "Industrials"

    def test_reference_data_reaches_the_decision(self):
        strategies, _ = load()
        ctx = {"contract": 1, "today": "2026-08-08", "inputs": {},
               "values": {}, "security": {"ticker": "SYN"}}
        result = contract.evaluate(strategies["shipped-data"], ctx)
        assert result["state"]["id"] == "known-sector"
        assert "Industrials" in result["reason"]["summary"]

    def test_a_strategy_cannot_rewrite_what_it_ships(self):
        """One evaluation must not change what the next one reads."""
        strategies, _ = load()
        rec = strategies["shipped-data"]
        with pytest.raises(TypeError):
            rec["reference"]["sectors.yaml"]["sectors"]["SYN"] = "Utilities"

    def test_reference_is_always_present_even_when_none_is_shipped(self):
        """Reading it is never a surprise, so a strategy that grows a table
        later does not have to guard the key."""
        strategies, _ = load()
        seen = {}
        rec = dict(strategies["sound"])
        rec["decide"] = lambda ctx: seen.update(ctx) or {
            "state": "stage-in",
            "payload": {"size": {"unit": "weight", "value": 1.0},
                        "condition": None},
            "reason": {"rule": "r", "summary": "s",
                       "evidence": [{"input": "target-weight"}]}}
        contract.evaluate(rec, {"contract": 1, "today": "2026-08-08",
                                "inputs": {"target-weight": 10},
                                "values": {"first-stage": 40}})
        assert seen["reference"] == {}

    def test_shipped_data_is_shared_not_copied_per_security(self):
        """A sector map copied for every holding on every refresh would be
        real cost; frozen data can be handed out by reference instead."""
        strategies, _ = load()
        rec = strategies["shipped-data"]
        seen = []
        probe = dict(rec)
        probe["decide"] = lambda ctx: seen.append(ctx["reference"]) or {
            "state": "unknown-sector", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": []}}
        base = {"contract": 1, "today": "2026-08-08", "inputs": {},
                "values": {}, "security": {"ticker": "NOPE"}}
        contract.evaluate(probe, dict(base))
        contract.evaluate(probe, dict(base))
        assert seen[0] is seen[1] is rec["reference"]

    def test_a_declared_file_that_is_missing_refuses_the_bundle(self,
                                                                tmp_path):
        bundle = tmp_path / "no-table"
        bundle.mkdir()
        (bundle / "strategy.py").write_text(
            "STRATEGY = {'id': 'no-table', 'name': 'N', 'summary': 's',"
            f" 'version': 1, 'contract': {contract.CONTRACT_VERSION},"
            " 'changelog': {1: 'f'},"
            " 'reference': ['sectors.yaml'],"
            " 'states': [{'id': 's', 'name': 'n', 'render': 'hold',"
            " 'description': 'd'}]}\ndef decide(ctx): pass\n")
        _, reports = strategy_loader.discover([tmp_path])
        [r] = reports
        assert not r["ok"]
        assert any("is not in the bundle" in e for e in r["errors"])

    def test_a_path_out_of_the_bundle_is_refused(self):
        errors = contract.validate_declaration({
            "id": "sneaky", "name": "S", "summary": "s", "version": 1,
            "contract": 1, "changelog": {1: "f"},
            "reference": ["../../secrets.yaml"],
            "states": [{"id": "s", "name": "n", "render": "hold",
                        "description": "d"}]})
        assert any("plain file name inside the bundle" in e for e in errors)


class TestDiscoveryNeverRaises:
    """Whatever a bundle contains, discovery reports and moves on. A plugin
    the host does not control must not be able to end the program."""

    BUNDLES = {
        "empty-file": "",
        "no-strategy": "x = 1\n",
        "strategy-not-a-dict": "STRATEGY = [1]\ndef decide(c): pass\n",
        "exits-at-import": "import sys\nsys.exit(3)\n",
        "raises-at-import": "raise MemoryError('import bomb')\n",
        "loops-into-recursion": ("def f():\n    return f()\nSTRATEGY = f()\n"),
    }

    def test_hostile_bundles_are_reported_never_raised(self, tmp_path):
        for name, body in self.BUNDLES.items():
            d = tmp_path / name
            d.mkdir()
            (d / "strategy.py").write_text(body)
        strategies, reports = strategy_loader.discover([tmp_path])
        assert strategies == {}
        assert len(reports) == len(self.BUNDLES)
        for r in reports:
            assert not r["ok"] and r["errors"]

    def test_an_unreadable_bundle_is_reported_not_raised(self, tmp_path):
        import os
        d = tmp_path / "unreadable"
        d.mkdir()
        py = d / "strategy.py"
        py.write_text("STRATEGY = {}\n")
        os.chmod(py, 0)
        try:
            _, reports = strategy_loader.discover([tmp_path])
            [r] = reports
            assert not r["ok"]
            assert any("failed to load" in e for e in r["errors"])
        finally:
            os.chmod(py, 0o644)


class TestEndToEnd:
    def test_the_sound_strategy_produces_a_conforming_commit(self):
        strategies, _ = load()
        rec = strategies["sound"]
        ctx = {"contract": 1, "today": "2026-08-08",
               "inputs": {"target-weight": 10},
               "values": {"first-stage": 40}}
        result = contract.evaluate(rec, ctx)
        assert result["render"] == "commit"
        assert result["produced_by"] == "strategy"
        assert result["payload"]["size"] == {"unit": "weight", "value": 4.0}
        assert result["strategy"]["values_version"] == 3
