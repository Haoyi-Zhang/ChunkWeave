from __future__ import annotations
import argparse,gzip,json,time,random,platform,subprocess
try:
 import resource
except ImportError:
 resource = None
from pathlib import Path
from chunkweave.corpus_extensions import cases
from chunkweave.adapters import NodeWorker,httpx_source_adapter
from chunkweave.quotient import MODES
from chunkweave.strategies import STRATEGIES,SEEDS,RANDOM,iterate
from chunkweave.schedules import distinct
CONTROLS=tuple(m for m in MODES if m!='correct')+('parser_per_event','decoder_per_retry','parser_per_retry')
KEYS=('events','retries','last_event_id')
def obs(x):return {k:x[k] for k in KEYS}
def write(path, obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='results/study');p.add_argument('--smoke',action='store_true');a=p.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);cc=cases()
 if a.smoke:cc=[c for c in cc if c['id'] in ('task-zh-00','truth-double-leading-bom','structural-retry-cycles-01','structural-callback-tail-02','structural-unicode-planes-05')]
 started=time.perf_counter();rng=random.Random(202610041)
 stats={'case_records':len(cc),'scheduled_control_mode_runs':0,'campaign_records':0,'source_checks':0}
 baselines=[];differences=[]
 with NodeWorker() as w,NodeWorker('azure_worker.mjs') as az, \
     gzip.open(out/'campaigns.jsonl.gz','wt') as f, gzip.open(out/'sources.jsonl.gz','wt') as sf:
  for _ in range(20):w.run('data:warmé\n\n'.encode(),[[6]],list(CONTROLS)+['bom_owned','skip_empty'])
  for ci,c in enumerate(cc):
   if time.perf_counter()-started>900:raise TimeoutError('900 s bounded evaluation cap')
   raw=c['text'].encode();expected=c['expected']
   base=w.run(raw,[[]],list(CONTROLS)+['bom_owned','skip_empty'])[0]
   eligible={m:obs(base[m])==expected for m in CONTROLS}
   baselines.append(dict(case=c['id'],family=c['family'],cohort=c['cohort'],eligible=eligible,observations=base))
   controlled=c['cohort'] in ('main','structural') or (c['cohort']=='validation' and c['family']!='validation-long-single-field')
   if controlled:
    variants=[(s,seed) for s in STRATEGIES for seed in (SEEDS if s in RANDOM else SEEDS[:1])]
    rng.shuffle(variants)
    for kind,seed in variants:
     t=time.perf_counter();schedules=list(iterate(raw,kind,seed));construction=1000*(time.perf_counter()-t)
     trial=w.run(raw,schedules,list(CONTROLS)+['bom_owned'],expected,base)
     cols={m:{key:[r[m][key] for r in trial] for key in ('event_ok','control_ok','changed','elapsed_ms','feed_count')} for m in CONTROLS+('bom_owned',)}
     f.write(json.dumps(dict(case=c['id'],family=c['family'],cohort=c['cohort'],strategy=kind,seed=seed,
       bytes=len(raw),tests=len(schedules),construction_ms=construction,modes=cols),separators=(',',':'))+'\n')
     stats['campaign_records']+=1;stats['scheduled_control_mode_runs']+=len(trial)*(len(CONTROLS)+1)
   # Identical partitions across source families; empty-output skipping is a fifth,
   # benign JS integration configuration, not a fourth implementation family.
   schedules=distinct([[]]+list(iterate(raw,'fixed'))+list(iterate(raw,'callback-aware')),33)
   schedules=[cs for cs in schedules if len(cs)+1<=4096 or len(raw)<=4096]
   js=w.run(raw,schedules,['correct','bom_owned','skip_empty'],expected)
   azbase=az.run(raw,[[]])[0]['correct'];azz=az.run(raw,schedules,expected=expected,baselines={'correct':azbase})
   pybase=httpx_source_adapter(raw,[]);pr=[]
   for cs in schedules:
    t=time.perf_counter();r=httpx_source_adapter(raw,cs)
    pr.append(dict(event_ok=r['events']==expected['events'],control_ok=all(r[k]==expected[k] for k in KEYS[1:]),
      changed=obs(r)!=obs(pybase),elapsed_ms=1000*(time.perf_counter()-t),feed_count=len(cs)+1))
   default=w.run(raw,[[]],['correct'])[0]['correct']
   fams={'js-default':(default,[r['correct'] for r in js]),'js-single-bom-owner':(base['bom_owned'],[r['bom_owned'] for r in js]),
         'js-skip-empty':(base['skip_empty'],[r['skip_empty'] for r in js]),'azure-source':(azbase,[r['correct'] for r in azz]),'python-source':(pybase,pr)}
   # JS compact comparison above has no baseline; retain a second comparison only
   # where whole semantics differs, instead of incorrectly equating it to change.
   for name,(b,rr) in fams.items():
    if name.startswith('js-'):
     mode={'js-default':'correct','js-single-bom-owner':'bom_owned','js-skip-empty':'skip_empty'}[name]
     if obs(b)==expected:
      for t in rr:t['changed']=not(t['event_ok'] and t['control_ok'])
     else:
      rr=[r[mode] for r in w.run(raw,schedules,[mode],expected,baselines={mode:b})]
    row=dict(case=c['id'],family=c['family'],cohort=c['cohort'],adapter=name,bytes=len(raw),tests=len(rr),
      whole_ok=obs(b)==expected,trials=rr)
    sf.write(json.dumps(row,separators=(',',':'))+'\n');stats['source_checks']+=len(rr)
    if not row['whole_ok'] or any(r['changed'] for r in rr):
     differences.append(dict(case=c['id'],adapter=name,expected=expected,whole=b,changed_indices=[i for i,r in enumerate(rr) if r['changed']]))
   if ci%40==0:print(f'{ci+1}/{len(cc)} {time.perf_counter()-started:.1f}s',flush=True)
 for name,data in [('baselines.json.gz',baselines),('source-differences.json.gz',differences)]:
  with gzip.open(out/name,'wt',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False)
 stats.update(status='completed',wall_seconds=time.perf_counter()-started,controls=list(CONTROLS),strategies=list(STRATEGIES),
  python=platform.python_version(),node=subprocess.check_output(['node','--version'],text=True).strip(),
  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
  child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss if resource else None,
  peak_rss_source='resource.getrusage' if resource else 'unavailable on this platform',
  clock_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
 write(out/'resources.json',stats);print(stats)
if __name__=='__main__':main()
