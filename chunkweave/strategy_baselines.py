"""Count-matched baseline partition generators used by the study."""
from __future__ import annotations

import random

from .fast_schedules import lazy_portfolio
from .schedules import FIXED

STRATEGIES = (
    'fixed',
    'bytewise',
    'uniform',
    'bytewise-sparse',
    'state-feature',
    'state-feature-no-parser',
)
RANDOM = {'uniform', 'bytewise-sparse'}
SEEDS = (1729, 2718, 3141)


def iterate(raw: bytes, kind: str, seed: int = 1729, budget: int = 16):
    """Yield at most ``budget`` distinct byte partitions for ``kind``."""
    if kind not in STRATEGIES:
        raise ValueError('unknown strategy')
    if type(budget) is not int or budget < 1:
        raise ValueError('positive integer schedule cap required')
    n = len(raw)
    if n < 2:
        yield []
        return
    if kind == 'bytewise':
        yield list(range(1, n))
        return
    if kind == 'fixed':
        seen: set[tuple[int, ...]] = set()
        for width in FIXED[:budget]:
            cuts = tuple(range(width, n, width))
            if cuts not in seen:
                seen.add(cuts)
                yield list(cuts)
        return
    if kind in RANDOM:
        rng = random.Random(seed)
        seen: set[tuple[int, ...]] = set()
        count = attempts = 0
        if kind == 'bytewise-sparse':
            bytewise = tuple(range(1, n))
            seen.add(bytewise)
            count = 1
            yield list(bytewise)
        while count < budget and attempts < budget * 30:
            if kind == 'bytewise-sparse':
                cuts = tuple(sorted(rng.sample(range(1, n), min(n - 1, rng.randint(1, 3)))))
            else:
                cuts = tuple(i for i in range(1, n) if rng.getrandbits(1))
            attempts += 1
            if cuts not in seen:
                seen.add(cuts)
                count += 1
                yield list(cuts)
        return
    yield from lazy_portfolio(
        raw,
        budget=budget,
        interactions=True,
        parser=kind != 'state-feature-no-parser',
        decoder=True,
    )
