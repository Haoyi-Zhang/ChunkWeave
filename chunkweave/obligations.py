"""Callback-aware, bounded decoder/callback boundary obligations.

The construction observes only the independent reference model, never the
system under test or its outcomes. Outside the proved profiles it is a sampler.
"""
from __future__ import annotations
from collections import defaultdict
from .landmark_projection import LandmarkProjection
from .schedules import FIXED


def landmarks(raw: bytes) -> dict:
    if len(raw) > 65536:
        raise ValueError('bounded input limit')
    model = LandmarkProjection()
    callbacks = {'event': 0, 'retry': 0}
    shadows: dict[str, dict[tuple, int]] = defaultdict(dict)
    silent: dict[tuple, tuple[int, int]] = {}
    previous_events = previous_retries = 0
    scalar_start = scalar_width = 0
    for end, byte in enumerate(raw, 1):
        if byte >= 0xC0:
            scalar_start = end-1
            scalar_width = 2 if byte < 0xE0 else 3 if byte < 0xF0 else 4
        model.feed_byte(byte)
        if model.events > previous_events:
            callbacks['event'] = end
        if model.retries > previous_retries:
            callbacks['retry'] = end
        previous_events = model.events
        previous_retries = model.retries
        if not model.need:
            continue
        # A bounded prefix, never a join of the whole partial line.
        prefix = model.prefix
        field = next((key for key in ('data', 'id', 'event', 'retry')
                      if prefix.startswith(key+':')), 'other')
        for kind, left in callbacks.items():
            if 0 < left < end:
                key = (scalar_width, model.need, field)
                shadows[kind].setdefault(key, end)
        if scalar_start > 0:
            key = (scalar_width, model.need, field)
            silent.setdefault(key, (scalar_start, end))
    model.finish()
    # Prefer data-bearing residuals, then other contexts; round robin callback kinds.
    buckets = {}
    for kind, entries in shadows.items():
        buckets[kind] = [end for key,end in sorted(entries.items(),
                        key=lambda kv:(kv[0][2]!='data', kv[0][0],kv[0][1],kv[1]))]
    cuts = []
    for i in range(max(map(len,buckets.values()), default=0)):
        for kind in ('event','retry'):
            if i < len(buckets.get(kind, [])):
                cuts.append([buckets[kind][i]])
    return {'shadow': cuts, 'silent': [list(pair) for key,pair in sorted(
        silent.items(), key=lambda kv:(kv[0][2]!='data',kv[0],kv[1]))]}


def iterate(raw: bytes, *, budget: int = 16, shadows: bool = True,
            two_only: bool = False):
    if type(budget) is not int or budget < 1:
        raise ValueError('positive integer schedule cap required')
    if not isinstance(raw, bytes):
        raise TypeError('raw must be bytes')
    raw.decode('utf-8', 'strict')
    if len(raw) > 65536:
        raise ValueError('bounded input limit')
    n = len(raw)
    if n < 2:
        yield []
        return
    seen = set()
    first = tuple(range(1, n))
    seen.add(first)
    yield list(first)
    if budget == 1:
        return
    marks = landmarks(raw)
    # At most eight representative shadow tests and four silent-gap tests.
    candidates = (marks['shadow'][:8] if shadows else []) + marks['silent'][:4]
    if two_only:
        candidates = (marks['shadow'] if shadows else marks['silent'])[:1]
    else:
        candidates += [list(range(k, n, k)) for k in FIXED]
    for cuts in candidates:
        key = tuple(cuts)
        if key not in seen:
            seen.add(key)
            yield cuts
            if len(seen) >= (min(2, budget) if two_only else budget):
                return
