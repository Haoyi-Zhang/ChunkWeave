"""Study policies: strong baselines plus callback-aware obligations."""
from __future__ import annotations

from .obligations import iterate as obligation_partitions
from .strategy_baselines import RANDOM, SEEDS, iterate as baseline_partitions

STRATEGIES = (
    'fixed',
    'bytewise',
    'uniform',
    'bytewise-sparse',
    'state-feature',
    'state-feature-no-parser',
    'callback-aware',
    'two-obligation',
    'no-shadow',
)


def iterate(raw: bytes, kind: str, seed: int = 1729, budget: int = 16):
    if kind == 'callback-aware':
        yield from obligation_partitions(raw, budget=budget)
    elif kind == 'two-obligation':
        yield from obligation_partitions(raw, budget=budget, two_only=True)
    elif kind == 'no-shadow':
        yield from obligation_partitions(raw, budget=budget, shadows=False)
    elif kind in STRATEGIES:
        yield from baseline_partitions(raw, kind, seed, budget)
    else:
        raise ValueError('unknown strategy')
