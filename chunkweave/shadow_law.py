"""Exact callback-shadow law for a declared data-only, LF-terminated profile.

These functions inspect bytes/partitions, never a tested implementation. U+FEFF
and U+FFFD are excluded from payloads to separate BOM ownership and replacement
character ambiguity from this particular theorem. General corpus tests do not
have these exclusions.
"""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass
from math import comb
from fractions import Fraction
from .oracle import slices

@dataclass(frozen=True)
class DataProfile:
    size: int
    dispatches: tuple[int, ...]
    interiors: frozenset[int]


def profile(raw: bytes) -> DataProfile:
    if not isinstance(raw, bytes):
        raise TypeError('raw must be bytes')
    if not raw or len(raw) > 65536:
        raise ValueError('nonempty bounded stream required')
    text = raw.decode('utf-8', 'strict')
    if '\r' in text or '\ufeff' in text or '\ufffd' in text:
        raise ValueError('outside the LF data-only shadow-law profile')
    if not text.endswith('\n\n'):
        raise ValueError('each data event must end with LF LF')
    parts = text[:-2].split('\n\n')
    offset = 0
    dispatches = []
    interiors = set()
    for block in parts:
        if not block.startswith('data:') or '\n' in block:
            raise ValueError('exactly one colon-delimited data line per event')
        for ch in block + '\n\n':
            width = len(ch.encode('utf-8'))
            interiors.update(range(offset + 1, offset + width))
            offset += width
        dispatches.append(offset)
    return DataProfile(len(raw), tuple(dispatches), frozenset(interiors))


def predicts_failure(raw: bytes, cuts: list[int] | tuple[int, ...]) -> bool:
    p = profile(raw)
    slices(raw, cuts)  # validate schedule at the public boundary
    previous = 0
    for end in cuts:
        j = bisect_right(p.dispatches, end) - 1
        if j >= 0 and end in p.interiors and previous < p.dispatches[j]:
            return True
        previous = end
    return False


def _convolve(a: list[int], b: list[int]) -> list[int]:
    out = [0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                out[i+j] += x*y
    return out


def failure_spectrum(raw: bytes, *, max_bytes: int = 256) -> list[int]:
    """Coefficient k = number of failing partitions with exactly k cuts.

    First-cut events in disjoint dispatch-to-dispatch regions factor. Integer
    arithmetic is exact; the byte cap limits polynomial construction costs.
    """
    p = profile(raw)
    if len(raw) > max_bytes:
        raise ValueError('polynomial construction byte cap')
    # Interior positions before the first event's dispatch cannot lose a prefix.
    prefix = p.dispatches[0] - 1
    passing = [comb(prefix, k) for k in range(prefix+1)]
    for left, right in zip(p.dispatches, p.dispatches[1:]):
        length = right - left
        region = [0] * (length+1)
        region[0] = 1  # no cut in this region
        for first in range(left, right):
            if first in p.interiors:
                continue
            tail = right - first - 1
            for k in range(tail+1):
                region[k+1] += comb(tail, k)
        passing = _convolve(passing, region)
    assert len(passing) == p.size
    return [comb(p.size-1, k)-passing[k] for k in range(p.size)]


def failure_probability(raw: bytes, probability: Fraction) -> Fraction:
    """Independent Bernoulli cut choices, not a network distribution."""
    p = profile(raw)
    probability = Fraction(probability)
    if not 0 <= probability <= 1:
        raise ValueError('cut probability must be in [0,1]')
    q = 1 - probability
    passing = Fraction(1)
    for left, right in zip(p.dispatches, p.dispatches[1:]):
        region_failure = sum((probability * q**(b-left)
                              for b in p.interiors if left < b < right), Fraction(0))
        passing *= 1 - region_failure
    return 1 - passing
