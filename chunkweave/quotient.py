"""Exact bounded partition search for an explicitly snapshot-able local model.

This is NOT a state extractor or a completeness claim for third-party software.
A node is (byte offset, full future-sufficient snapshot). Edges feed one nonempty
slice. BFS yields a globally minimum-cut witness; exhausted search establishes
agreement over every partition of this ONE input in THIS model. Capped searches
return UNKNOWN, never PASS. The algorithm is ordinary finite-state reachability.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, replace
import codecs
import time
from .oracle import evaluate

MODES = ('correct', 'stateless_utf8', 'reset_parser', 'empty_reset',
         'leading_trim', 'newline_each_feed', 'crlf_chunk_normalize',
         'id_per_chunk', 'decoder_per_event')
JS_SPACE = '\u0009\u000b\u000c\u0020\u00a0\ufeff\u000a\u000d\u2028\u2029\u1680' + ''.join(chr(c) for c in range(0x2000,0x200b)) + '\u202f\u205f\u3000'

@dataclass(frozen=True)
class Snapshot:
    decoder_bytes: bytes = b''
    decoder_flag: int = 1  # utf-8-sig's not-yet-checked initial BOM
    line: str = ''
    skip_lf: bool = False
    data: tuple[str, ...] = ()
    event: str = ''
    pending_id: str | None = None
    last: str = ''
    events: tuple[tuple[str, str, str], ...] = ()
    retries: tuple[int, ...] = ()


def observation(s: Snapshot) -> dict:
    return {'events': [dict(type=t, data=d, id=i) for t,d,i in s.events],
            'retries': list(s.retries), 'last_event_id': s.last}


def _reset(s: Snapshot) -> Snapshot:
    return replace(s, line='', skip_lf=False, data=(), event='', pending_id=None)


def _text(s: Snapshot, text: str) -> tuple[Snapshot, bool]:
    # Functional SSE interpretation, distinct from the regexp whole-input oracle.
    line=s.line; skip=s.skip_lf; data=list(s.data); event=s.event
    pending=s.pending_id; last=s.last; events=list(s.events); retries=list(s.retries)
    delivered=False
    for ch in text:
        if skip:
            skip=False
            if ch=='\n':
                continue
        if ch not in '\r\n':
            line+=ch
            continue
        skip=(ch=='\r')
        if line=='':
            if pending is not None:
                last=pending
            if data:
                events.append((event or 'message','\n'.join(data),last))
                delivered=True
            pending=None; data=[]; event=''
        elif not line.startswith(':'):
            k,sep,v=line.partition(':')
            if not sep:v=''
            elif v.startswith(' '):v=v[1:]
            if k=='data':data.append(v)
            elif k=='event':event=v
            elif k=='id' and '\0' not in v:pending=v
            elif k=='retry' and v and all('0'<=c<='9' for c in v):
                if len(v)>6 or int(v)>60000:
                    raise ValueError('retry outside bounded profile')
                retries.append(int(v))
        line=''
    return replace(s,line=line,skip_lf=skip,data=tuple(data),event=event,
                   pending_id=pending,last=last,events=tuple(events),retries=tuple(retries)), delivered


def advance(s: Snapshot, chunk: bytes, mode: str='correct', *, had_feed: bool=False) -> Snapshot:
    if mode not in MODES:raise ValueError('unknown model mode')
    if not chunk:raise ValueError('partition edges must have nonempty byte slices')
    if mode=='reset_parser' and had_feed:s=_reset(s)
    if mode=='id_per_chunk' and had_feed:s=replace(s,last='')
    decoder=codecs.getincrementaldecoder('utf-8-sig')('replace')
    decoder.setstate((s.decoder_bytes,s.decoder_flag))
    if mode=='stateless_utf8':
        text=chunk.decode('utf-8-sig','replace')
    else:text=decoder.decode(chunk,final=False)
    if mode=='empty_reset' and not text:s=_reset(s)
    if mode=='leading_trim' and had_feed:text=text.lstrip(JS_SPACE)
    if mode=='crlf_chunk_normalize':text=text.replace('\r\n','\n').replace('\r','\n')
    if mode=='newline_each_feed':text+='\n'
    s,delivered=_text(s,text)
    if mode=='decoder_per_event' and delivered:
        decoder=codecs.getincrementaldecoder('utf-8-sig')('replace')
    buf,flag=decoder.getstate()
    return replace(s,decoder_bytes=buf,decoder_flag=flag)


def finish(s: Snapshot, mode: str='correct') -> dict:
    if mode!='stateless_utf8':
        decoder=codecs.getincrementaldecoder('utf-8-sig')('replace')
        decoder.setstate((s.decoder_bytes,s.decoder_flag))
        s,_=_text(s,decoder.decode(b'',final=True))
    # An unterminated line and pending event data are not forcibly dispatched.
    return observation(s)


def execute(raw:bytes,cuts:list[int]|tuple[int,...],mode:str='correct') -> dict:
    from .oracle import slices
    raw.decode('utf-8','strict')
    if len(raw)>65536:raise ValueError('bounded input limit')
    s=Snapshot()
    for i,chunk in enumerate(slices(raw,cuts)):
        if chunk:s=advance(s,chunk,mode,had_feed=i>0)
    return finish(s,mode)


def search(raw:bytes,mode:str='correct',*,max_nodes:int=100_000,max_edges:int=1_000_000,
           max_seconds:float=10.0) -> dict:
    if max_nodes<1 or max_edges<0 or max_seconds<=0:raise ValueError('invalid search bound')
    expected=evaluate(raw);n=len(raw);start=time.perf_counter()
    initial=Snapshot();todo=deque([(0,initial,())]);seen={(0,initial)};edges=0;terminals=0
    def result(status,**kw):
        return dict(status=status,model=mode,bytes=n,nodes=len(seen),edges=edges,
                    terminal_edges=terminals,partition_count=(str(1 << max(0,n-1)) if n<=4096 else f'2^{n-1}'),
                    partition_count_exponent=max(0,n-1),
                    elapsed_ms=1000*(time.perf_counter()-start),**kw)
    if n==0:return result('CERTIFIED',minimum_cuts=None,witness=None)
    while todo:
        a,state,path=todo.popleft()
        for b in range(a+1,n+1):
            if edges>=max_edges or time.perf_counter()-start>=max_seconds:
                return result('UNKNOWN',reason='edge or elapsed-time cap',witness=None)
            next_state=advance(state,raw[a:b],mode,had_feed=a>0);edges+=1
            if b==n:
                terminals+=1;actual=finish(next_state,mode)
                if actual!=expected:
                    cuts=list(path)
                    assert execute(raw,cuts,mode)==actual
                    return result('COUNTEREXAMPLE',minimum_cuts=len(cuts),witness=cuts,
                                  expected=expected,actual=actual)
                continue
            key=(b,next_state)
            if key not in seen:
                if len(seen)>=max_nodes:
                    return result('UNKNOWN',reason='node cap',witness=None)
                seen.add(key);todo.append((b,next_state,path+(b,)))
    return result('CERTIFIED',minimum_cuts=None,witness=None)
