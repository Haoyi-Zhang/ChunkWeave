"""Bounded byte schedules and declared model-obligation coverage.

Coverage is a finite engineering criterion, NOT a bisimulation quotient and NOT
an implementation-completeness theorem. Pair obligations refer to consecutive
cuts at most WINDOW bytes apart in the same or an adjacent event block.
"""
from __future__ import annotations
from dataclasses import dataclass
import random
from .model import IncrementalModel

WINDOW=32
BUDGET=16
FIXED=(1,2,3,4,5,7,8,11,16,23,32,47,64,97,128,257)

@dataclass
class Trace:
    states:list
    chars:list[int]
    lines:list[int]
    epochs:list[int]
    n:int

    def pair(self,a:int,b:int):
        if not(0<a<b<self.n) or b-a>WINDOW or self.epochs[b]-self.epochs[a]>1:
            return None
        sa,sb=self.states[a],self.states[b]
        if self.chars[a]==self.chars[b]: kind='silent'
        elif self.epochs[a]!=self.epochs[b]: kind='block-crossing'
        elif self.lines[a]!=self.lines[b]: kind='line-crossing'
        else: kind='within-line'
        # Observable interaction class, no concrete payload or event ID values.
        return ('pair',kind,sa[2],sb[2],bool(sa[0]),bool(sb[0]),sa[3],sa[5])

    def features(self,cuts):
        f={('seam',self.states[p]) for p in cuts}
        for a,b in zip(cuts,cuts[1:]):
            pair=self.pair(a,b)
            if pair is not None:f.add(pair)
        return f

    def universe(self):
        f={('seam',s) for s in self.states[1:-1]}
        for a in range(1,self.n):
            for b in range(a+1,min(self.n,a+WINDOW+1)):
                p=self.pair(a,b)
                if p is not None:f.add(p)
        return f

def trace(raw:bytes)->Trace:
    m=IncrementalModel();states=[None];chars=[0];lines=[0];epochs=[0]
    for byte in raw:
        m.feed(bytes([byte]));s=m.boundary_state()
        states.append(s+(bool(m.events),m.first))
        chars.append(m.characters);lines.append(m.line_number);epochs.append(m.epoch)
    m.finish()
    return Trace(states,chars,lines,epochs,len(raw))

def distinct(items,budget=BUDGET):
    result=[];seen=set()
    for x in items:
        t=tuple(sorted(set(x)))
        if t not in seen:
            seen.add(t);result.append(list(t))
            if len(result)==budget:break
    return result

def candidates(t:Trace,decoder=True,parser=True,interactions=True):
    groups={}
    for p in range(1,t.n):
        s=t.states[p]
        if not decoder and s[0]:continue
        if not parser and not(s[0] or s[1]):continue
        key=s if parser else (s[0],s[1],s[-1])
        groups.setdefault(key,[]).append(p)
    reps=set()
    for positions in groups.values():
        reps.update([positions[0],positions[len(positions)//2],positions[-1]])
    # Bound candidate construction independently of stream length.
    reps=sorted(reps)
    if len(reps)>192:
        reps=sorted(set(reps[i*(len(reps)-1)//191] for i in range(192)))
    result={(p,) for p in reps}
    if interactions:
        for i,a in enumerate(reps):
            for b in reps[i+1:i+4]:
                if t.pair(a,b) is not None:result.add((a,b))
        # Consecutive interior seams in one scalar can produce empty text while
        # a field is pending. Retain one first/middle/last witness per context.
        silent={}
        if decoder:
            for a in range(1,t.n-1):
                p=t.pair(a,a+1)
                if p and p[1]=='silent':silent.setdefault(p,[]).append((a,a+1))
            for pairs in silent.values():
                result.update([pairs[0],pairs[len(pairs)//2],pairs[-1]])
    return sorted(result,key=lambda x:(len(x),x))

def choose(t:Trace,budget=BUDGET,decoder=True,parser=True,interactions=True):
    pool=candidates(t,decoder,parser,interactions)
    def project(features):
        if parser:return features
        # Decoder-only ablation deliberately cannot distinguish parser states.
        return {('seam',x[1][0],x[1][1],x[1][-1]) if x[0]=='seam' else
                ('pair',x[1],x[4],x[5]) for x in features}
    fs={p:project(t.features(p)) for p in pool}
    used=set();result=[]
    for _ in range(min(budget,len(pool))):
        best=max(pool,key=lambda p:(len(fs[p]-used),-len(p),tuple(-i for i in p)))
        result.append(list(best));used.update(fs[best]);pool.remove(best)
    # Deterministic ASCII controls/fallback; no outcome-driven resampling.
    eligible=[p for p in range(1,t.n) if decoder or t.states[p][0]==0]
    filler=[[eligible[min(len(eligible)-1,i*len(eligible)//(budget+1))]] for i in range(1,budget+1)] if eligible else []
    return distinct(result+filler,budget)

def generate(raw:bytes,kind:str,seed:int=1729,t:Trace|None=None,budget=BUDGET):
    n=len(raw)
    if n<=1:return [[]]
    if kind=='whole':return [[]]
    if kind=='fixed':return distinct((range(k,n,k) for k in FIXED),budget)
    if kind=='single-16':return distinct(([max(1,min(n-1,(2*i+1)*n//(2*budget)))] for i in range(budget)),budget)
    if kind=='all-single':return [[i] for i in range(1,n)]
    if kind in ('uniform','sparse-random'):
        rng=random.Random(seed);out=[];seen=set();attempts=0
        while len(out)<budget and attempts<budget*20:
            if kind=='uniform':cuts=tuple(i for i in range(1,n) if rng.getrandbits(1))
            else:cuts=tuple(sorted(rng.sample(range(1,n),min(n-1,rng.randint(1,3)))))
            attempts+=1
            if cuts not in seen:out.append(list(cuts));seen.add(cuts)
        return out
    if t is None:t=trace(raw)
    options={'critical':(True,True,True),'no-decoder':(False,True,True),
             'no-parser':(True,False,True),'no-interaction':(True,True,False)}
    if kind not in options:raise ValueError(kind)
    d,p,i=options[kind]
    return choose(t,budget,d,p,i)

KINDS=('fixed','uniform','sparse-random','single-16','critical','no-decoder','no-parser','no-interaction')
