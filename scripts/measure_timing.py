"""Order-balanced warm discovery measurements, with non-detections retained."""
from __future__ import annotations
import argparse,gzip,json,random,time,platform,statistics
try:
 import resource
except ImportError:
 resource = None
from pathlib import Path
from collections import defaultdict
from chunkweave.corpus_extensions import cases
from chunkweave.adapters import NodeWorker
from chunkweave.strategies import STRATEGIES,SEEDS,iterate
from study import CONTROLS,obs

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='results/study/timing.jsonl.gz');p.add_argument('--repeats',type=int,default=5);a=p.parse_args()
 if not 1<=a.repeats<=9:raise ValueError('repeats must be between 1 and 9')
 groups=defaultdict(list)
 for c in cases():
  if c['cohort'] in ('main','structural') or (c['cohort']=='validation' and c['family']!='validation-long-single-field'):groups[c['family']].append(c)
 # Deterministic input-only sampling, without inspecting method detection rates.
 chosen=[]
 for fam,cc in sorted(groups.items()):
  cc.sort(key=lambda x:x['id']);chosen += [cc[0],cc[len(cc)//2],cc[-1]]
 chosen=list({c['id']:c for c in chosen}.values())
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
 rows=0;unitkeys=set();start=time.perf_counter();rng=random.Random(202610043);limit=50.;block_index=0;base_order=list(STRATEGIES)
 with NodeWorker() as w,gzip.open(path,'wt') as f:
  for _ in range(30):w.run('data:warmé\n\n'.encode(),[[6]],CONTROLS)
  for c in chosen:
   raw=c['text'].encode();expected=c['expected'];base=w.run(raw,[[]],CONTROLS)[0]
   modes=[m for m in CONTROLS if obs(base[m])==expected]
   units=[(m,rep) for m in modes for rep in range(a.repeats)];rng.shuffle(units)
   for mi,(mode,rep) in enumerate(units):
    # Latin rotations: each complete group of nine blocks places every policy
    # in every rank exactly once; shuffle the base permutation between groups.
    shift=block_index%len(STRATEGIES)
    if shift==0:rng.shuffle(base_order)
    order=base_order[shift:]+base_order[:shift];block_index+=1
    for rank,kind in enumerate(order):
     t=time.perf_counter();detect=None;schedules=0;feeds=0;done=False
     for cuts in iterate(raw,kind,SEEDS[rep%len(SEEDS)]):
      if (time.perf_counter()-t)*1000>=limit:break
      r=w.run(raw,[cuts],[mode],expected=expected)[0][mode]
      schedules+=1;feeds+=r['feed_count'];elapsed=(time.perf_counter()-t)*1000
      if not(r['event_ok'] and r['control_ok']):
       if elapsed<=limit:detect=elapsed
       break
      if elapsed>=limit:break
     else:done=True
     elapsed=(time.perf_counter()-t)*1000
     row=dict(case=c['id'],family=c['family'],cohort=c['cohort'],mode=mode,repeat=rep,seed=SEEDS[rep%len(SEEDS)],strategy=kind,order_rank=rank,block_index=block_index-1,
        detected_ms=detect,total_ms=elapsed,schedules=schedules,feeds=feeds,exhausted_policy=done,budget_ms=limit)
     f.write(json.dumps(row,separators=(',',':'))+'\n');rows+=1
    unitkeys.add((c['id'],mode))
   print(c['id'],rows,round(time.perf_counter()-start,2),flush=True)
 summary=dict(status='completed',cases=len(chosen),units=len(unitkeys),repeats=a.repeats,rows=rows,strategies=list(STRATEGIES),wall_seconds=time.perf_counter()-start,
  python=platform.python_version(),peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
  excluded='runtime startup, common whole-input prechecks, and oracle computation',included='lazy policy construction, warm IPC, and source execution',
  sample_rule='first, middle, last by case id within each eligible authored family; deduplicated',
  random_seed_rule='three fixed seeds selected by repeat modulo three; repeated random timing is not three-seed-independent statistical replication',
  thresholds='nested observations of the same 50-ms trace; over-budget completion is never detected')
 path.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(summary)
if __name__=='__main__':main()
