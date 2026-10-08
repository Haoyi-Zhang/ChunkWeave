"""Bounded exact law checks. No production input, remote endpoint or malformed byte stream."""
from __future__ import annotations
import argparse,gzip,json,random,time
from pathlib import Path
from fractions import Fraction
from math import comb
from chunkweave.shadow_law import profile,predicts_failure,failure_spectrum,failure_probability
from chunkweave.spectrum import count
from chunkweave.quotient import execute
from chunkweave.adapters import NodeWorker
from chunkweave.oracle import evaluate

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='results/study/shadow-law.json');a=p.parse_args()
 start=time.perf_counter();rows=[];checks=0;model_checks=0;rng=random.Random(314159)
 # Exhaustive two-event families: 16/17/18 bytes, including the empty data event.
 short=['data:\n\ndata:'+ch+'\n\n' for ch in ('é','中','🌍')]
 extended=['data:a\n\ndata:é\n\ndata:z中\n\n',
           'data:é\n\ndata:中🌍\n\ndata:xé\n\n',
           'data:a\n\ndata:x🌍z\n\ndata:\n\ndata:中\n\n',
           'data:ascii\n\ndata:more ascii\n\n']
 with NodeWorker() as w:
  for text in short+extended:
   raw=text.encode();n=len(raw);expected=evaluate(raw);exhaustive=text in short
   analytic=failure_spectrum(raw);graph=count(raw,'decoder_per_event')
   assert graph['status']=='EXACT' and analytic==graph['failures']
   for q in (Fraction(0),Fraction(1,64),Fraction(1,8),Fraction(1,2),Fraction(1)):
    mass=sum(Fraction(v)*q**k*(1-q)**(n-1-k) for k,v in enumerate(analytic))
    assert mass==failure_probability(raw,q)
   histogram=[0]*n;tested=0;failures=0
   schedules=([i+1 for i in range(n-1) if mask>>i&1] for mask in range(1<<(n-1))) if exhaustive else iter(
      [[]]+[list(range(1,n))]+[[i] for i in range(1,n)]+[[i for i in range(1,n) if rng.random()<q] for q in (0.02,0.1,0.5,0.9) for _ in range(512)])
   batch=[]
   def consume(batch):
    nonlocal checks,model_checks,tested,failures
    actual=w.run(raw,batch,['decoder_per_event'],expected=expected)
    for cuts,r in zip(batch,actual):
     bad=not (r['decoder_per_event']['event_ok'] and r['decoder_per_event']['control_ok'])
     pred=predicts_failure(raw,cuts)
     assert bad==pred,(text,cuts,bad,pred)
     # Separate functional transition replay on a deterministic subsample. The
     # graph independently represents all partitions, including unsampled paths.
     if tested%97==0:
      assert (execute(raw,cuts,'decoder_per_event')!=expected)==bad;model_checks+=1
     tested+=1;checks+=1
     if bad:histogram[len(cuts)]+=1;failures+=1
   for cuts in schedules:
    batch.append(cuts)
    if len(batch)==256:consume(batch);batch=[]
   if batch:consume(batch)
   if exhaustive:assert histogram==analytic
   rows.append(dict(text=text,bytes=n,exhaustive_source=exhaustive,source_checks=tested,observed_failures=failures,
    analytic_spectrum=analytic,source_spectrum=histogram if exhaustive else None,graph=graph,
    fair_cut_failure_probability=str(failure_probability(raw,Fraction(1,2)))))
   print(n,tested,failures,flush=True)
 out=dict(status='passed',rows=rows,source_checks=checks,extra_model_replays=model_checks,
  exhaustive_partitions=sum(r['source_checks'] for r in rows if r['exhaustive_source']),
  independent_claim='independent implementations in one workflow, not independent human audit',
  wall_seconds=time.perf_counter()-start)
 path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 print({k:v for k,v in out.items() if k!='rows'})
if __name__=='__main__':main()
