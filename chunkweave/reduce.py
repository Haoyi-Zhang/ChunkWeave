"""Cut-only ddmin with a final deletion audit. Bytes NEVER change."""
from __future__ import annotations
import time

def minimize(cuts, fails, budget:int=512):
    if budget < 2:raise ValueError('reduction budget must permit witness and baseline checks')
    if any(type(x) is not int or x <= 0 for x in cuts) or list(cuts) != sorted(set(cuts)):
        raise ValueError('cuts must be increasing positive integers')
    start=time.perf_counter();calls=0;cache={}
    def check(seq):
        nonlocal calls
        key=tuple(seq)
        if key in cache:return cache[key]
        if calls>=budget:raise TimeoutError('reduction execution budget')
        calls+=1;cache[key]=bool(fails(list(seq)));return cache[key]
    current=list(cuts)
    if not check(current):raise ValueError('initial schedule is not a witness')
    if check([]):raise ValueError('whole-buffer discrepancy is not segmentation-induced')
    n=2;limited=False
    try:
        while len(current)>=2:
            width=(len(current)+n-1)//n;reduced=False
            for start_at in range(0,len(current),width):
                trial=current[:start_at]+current[start_at+width:]
                if check(trial):current=trial;n=max(2,n-1);reduced=True;break
            if not reduced:
                if n>=len(current):break
                n=min(len(current),2*n)
        changed=True
        while changed:
            changed=False
            for i in range(len(current)):
                trial=current[:i]+current[i+1:]
                if check(trial):current=trial;changed=True;break
        one_minimal=all(not check(current[:i]+current[i+1:]) for i in range(len(current)))
    except TimeoutError:
        limited=True;one_minimal=False
    return {'original_cuts':list(cuts),'reduced_cuts':current,'oracle_calls':calls,
            'one_minimal':one_minimal,'budget_limited':limited,
            'elapsed_ms':1000*(time.perf_counter()-start),'bytes_unchanged':True}
