"""Exact partition-count spectrum in a full-snapshot deterministic model.

This is ordinary topological dynamic programming. It counts every path, rather
than treating one state representative as one partition. Model transitions are
not extracted from a third-party package. Exhausted resource bounds return
UNKNOWN with no unearned final spectrum.
"""
from __future__ import annotations
from collections import defaultdict
import time
from math import comb
from .quotient import Snapshot, advance, finish, MODES
from .oracle import evaluate


def count(raw: bytes, mode: str = 'correct', *, max_bytes: int = 96,
          max_nodes: int = 50000, max_edges: int = 500000,
          max_seconds: float = 30.) -> dict:
    if mode not in MODES:
        raise ValueError('unknown model mode')
    if max_bytes < 1 or max_nodes < 1 or max_edges < 0 or max_seconds <= 0:
        raise ValueError('invalid resource bound')
    expected = evaluate(raw)
    n = len(raw)
    start = time.perf_counter()
    def result(status, **kwargs):
        return dict(status=status, mode=mode, bytes=n,
                    elapsed_ms=1000*(time.perf_counter()-start), **kwargs)
    if n > max_bytes:
        return result('UNKNOWN',reason='byte cap',nodes=0,edges=0)
    if n == 0:
        return result('EXACT',nodes=1,edges=0,total=[1],failures=[0])
    layers = [dict() for _ in range(n)]
    layers[0][Snapshot()] = [1]+[0]*(n-1)
    nodes=1; edges=0
    failures=[0]*n; total=[0]*n
    for offset in range(n):
        for state, counts in layers[offset].items():
            for end in range(offset+1,n+1):
                if edges >= max_edges or time.perf_counter()-start >= max_seconds:
                    return result('UNKNOWN',reason='edge or time cap',nodes=nodes,edges=edges)
                nxt=advance(state,raw[offset:end],mode,had_feed=offset>0);edges+=1
                if end==n:
                    bad=finish(nxt,mode)!=expected
                    for k,v in enumerate(counts):
                        total[k]+=v
                        if bad:failures[k]+=v
                else:
                    if nxt not in layers[end]:
                        if nodes >= max_nodes:
                            return result('UNKNOWN',reason='node cap',nodes=nodes,edges=edges)
                        layers[end][nxt]=[0]*n;nodes+=1
                    dest=layers[end][nxt]
                    for k,v in enumerate(counts[:-1]):
                        dest[k+1]+=v
    assert total == [comb(n-1,k) for k in range(n)], 'path mass was not conserved'
    return result('EXACT',nodes=nodes,edges=edges,total=total,failures=failures)
