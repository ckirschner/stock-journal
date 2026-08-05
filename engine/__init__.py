"""Ledger engine. Nothing in here imports from ui/.

Everything here is plain Python over plain dicts, so the screening funnel you
build later can import the same evaluator instead of reimplementing it.
"""
from .schema import DEFAULT_SCHEMA, EV_METHODS, EXIT_REASONS, flat_metrics, metric_by_id
from .rules import RuleBook, default_ruleset
from .evaluate import evaluate, state_of, format_value, failure_labels
from .expected_value import compute as compute_ev, EVError
from . import store, portfolio, backup

__all__ = [
    "DEFAULT_SCHEMA", "EV_METHODS", "EXIT_REASONS", "flat_metrics", "metric_by_id",
    "RuleBook", "default_ruleset", "evaluate", "state_of", "format_value",
    "failure_labels", "compute_ev", "EVError", "store", "portfolio", "backup",
]
