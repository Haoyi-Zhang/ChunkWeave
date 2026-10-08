"""Positive-only byte-preserving diagnostics; not a discovery-rate experiment."""
from __future__ import annotations
import argparse,json,gzip,time
from pathlib import Path
from collections import defaultdict
from chunkweave.corpus_extensions import cases
from chunkweave.adapters import NodeWorker
from chunkweave.reduce import minimize
from chunkweave.strategies import iterate

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='results/study');a=p.parse_args();out=Path(a.out)
 cc={c['id']:c for c in cases()};base={c['case']:c for c in json.load(gzip.open(out/'baselines.json.gz','rt'))};groups=defaultdict(list)
 with gzip.open(out/'campaigns.jsonl.gz','rt') as f:
  for line in f:
   r=json.loads(line)
   if r['strategy']!='callback-aware':continue
   for m,z in r['modes'].items():
    if m=='bom_owned' or not base[r['case']]['eligible'][m]:continue
    if any(z['changed']):groups[r['cohort'],m].append((r['case'],z['changed'].index(True)))
 chosen=[(co,m,c,i) for (co,m),rows in sorted(groups.items()) for c,i in sorted(rows)[:2]];results=[];start=time.perf_counter()
 with NodeWorker() as w:
  for co,m,c,i in chosen:
   raw=cc[c]['text'].encode();expected=cc[c]['expected'];cuts=list(iterate(raw,'callback-aware'))[i]
   def fails(q):
    actual=w.run(raw,[q],[m])[0][m];return {k:actual[k] for k in expected}!=expected
   r=minimize(cuts,fails,budget=2000);q=r['reduced_cuts']
   assert r['one_minimal'] and not r['budget_limited'];assert fails(q) and not fails([])
   assert all(not fails(q[:j]+q[j+1:]) for j in range(len(q)))
   results.append(dict(case=c,cohort=co,mode=m,bytes=len(raw),**r,expected=expected,actual=w.run(raw,[q],[m])[0][m]))
   if time.perf_counter()-start>120:raise TimeoutError('diagnostic time budget')
 result=dict(status='passed',rows=results,wall_seconds=time.perf_counter()-start,scope='two lexicographically selected previously detected units per cohort/action; fixed bytes, fresh deletion-1 replay, no global minimality claim')
 (out/'reduction.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(len(results),result['wall_seconds'])
if __name__=='__main__':main()
