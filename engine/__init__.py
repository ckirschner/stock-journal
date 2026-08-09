"""Ledger engine. Nothing in here imports from ui/.

Everything here is plain Python over plain dicts — including the boundary to
strategies, which receive one plain dict and return one plain dict. The
screening funnel built later imports the same contract rather than
reimplementing scoring, which is why the host must stay free of strategy
assumptions and strategies free of fetching.
"""
from .expected_value import DEFAULT_SETTINGS, EV_METHODS, EVError
from .expected_value import compute as compute_ev
from .portfolio import EXIT_REASONS
from . import backup, bank, journals, judgements, portfolio, store
from . import contract, context, strategy_loader, strategy_values

__all__ = [
    "EV_METHODS", "EXIT_REASONS", "DEFAULT_SETTINGS", "compute_ev", "EVError",
    "backup", "bank", "journals", "judgements", "portfolio", "store",
    "contract", "context", "strategy_loader", "strategy_values",
]
