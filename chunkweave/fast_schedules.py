"""Linear reference-state trace and a bytewise-sentinel / sparse-gap portfolio.

No SUT executions or outcomes enter schedule construction. Greedy coverage is
only coverage of the declared finite candidate pool, not semantic completeness.
The previous selector remains a reported comparator; results are not overwritten.
"""
from __future__ import annotations
from .schedules import Trace, BUDGET, candidates, distinct, FIXED
KEYS=('data','event','id','retry')


def fast_trace(raw:bytes)->Trace:
    # Validate the declared input domain once. No library parser is consulted.
    raw.decode('utf-8','strict')
    if len(raw)>65536:raise ValueError('bounded input limit')
    states=[None];chars=[0];lines=[0];epochs=[0]
    need=code=0;first=True;skip=False
    line_len=0;key='';colon=False;comment=False;vstage=0;vcount=0;nul=False
    has_data=has_kind=has_id=has_events=False;nc=nl=ne=0
    for byte in raw:
        ch=None
        if need:
            code=(code<<6)|(byte&63);need-=1
            if not need:ch=chr(code)
        elif byte<128:ch=chr(byte)
        elif byte<224:need=1;code=byte&31
        elif byte<240:need=2;code=byte&15
        else:need=3;code=byte&7
        if ch is not None:
            if first:
                first=False
                if ch=='\ufeff':ch=None
            if ch is not None:
                nc+=1
                swallowed=skip and ch=='\n'
                skip=False
                if not swallowed:
                    if ch in '\r\n':
                        if line_len==0:
                            if has_data:has_events=True
                            has_data=has_kind=False;ne+=1
                        elif not comment:
                            if key=='data':has_data=True
                            elif key=='event':has_kind=vcount>0
                            elif key=='id' and not nul:has_id=vcount>0
                        nl+=1;skip=(ch=='\r')
                        line_len=0;key='';colon=comment=False;vstage=vcount=0;nul=False
                    else:
                        if line_len==0 and ch==':':comment=True
                        line_len+=1
                        if not comment:
                            if not colon and ch==':':colon=True
                            elif not colon:
                                key=key+ch if len(key)<6 else '!unknown'
                            else:
                                if vstage==0 and ch==' ':vstage=1
                                else:vstage=2;vcount+=1
                                nul=nul or ch=='\0'
        if line_len==0:phase='empty'
        elif comment:phase='comment'
        elif colon:
            phase=('value-'+key) if key in KEYS else 'other'
            if vstage<2:phase+='-start'
        elif any(k.startswith(key) for k in KEYS):phase='field-prefix'
        else:phase='other'
        states.append((need,int(skip),phase,has_data,has_kind,has_id,has_events,first))
        chars.append(nc);lines.append(nl);epochs.append(ne)
    return Trace(states,chars,lines,epochs,len(raw))


def portfolio(raw:bytes,budget:int=BUDGET,*,sentinel:bool=True,
              decoder:bool=True,parser:bool=True,interactions:bool=True)->list[list[int]]:
    if budget<1:raise ValueError('budget must be positive')
    n=len(raw)
    if n<2:return [[]]
    t=fast_trace(raw)
    pool=candidates(t,decoder=decoder,parser=parser,interactions=interactions)
    def project(features):
        if parser:return features
        return {('seam',x[1][0],x[1][1],x[1][-1]) if x[0]=='seam' else
                ('pair',x[1],x[4],x[5]) for x in features}
    selected=[list(range(1,n))] if sentinel else []
    used=project(t.features(selected[0])) if selected else set()
    pool=[p for p in pool if list(p) not in selected]
    fs={p:project(t.features(p)) for p in pool}
    while pool and len(selected)<budget:
        best=max(pool,key=lambda p:(len(fs[p]-used),-len(p),tuple(-i for i in p)))
        selected.append(list(best));used.update(fs[best]);pool.remove(best)
    # Fill duplicate-reduced very short inputs without claiming 16 unique tests.
    fillers=[list(range(k,n,k)) for k in FIXED]
    return distinct(selected+fillers,budget)


def lazy_portfolio(raw:bytes,budget:int=BUDGET,**kwargs):
    """Yield the cheap sentinel before paying for a state trace.

    This changes time-to-first-detection, not the final schedule sequence. The
    rest of the portfolio is constructed only if the consumer requests it.
    """
    if budget<1:raise ValueError('budget must be positive')
    first=list(range(1,len(raw)))
    yield first
    if budget>1:
        rest=portfolio(raw,budget=budget,**kwargs)
        if rest[0]!=first:raise AssertionError('sentinel sequence invariant')
        yield from rest[1:]
