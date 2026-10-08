from __future__ import annotations
import argparse,gzip,json,statistics,csv
from collections import defaultdict
from pathlib import Path
import numpy as np
from chunkweave.strategies import STRATEGIES
NEW={'parser_per_event','decoder_per_retry','parser_per_retry'}

def readlines(path):
 with gzip.open(path,'rt') as f:
  for line in f:yield json.loads(line)
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='results/study');a=p.parse_args();out=Path(a.out)
 bases={r['case']:r for r in json.load(gzip.open(out/'baselines.json.gz','rt'))}
 observations=defaultdict(list);metadata={};clean=0;cleanbad=0
 for r in readlines(out/'campaigns.jsonl.gz'):
  for mode,trials in r['modes'].items():
   if mode=='bom_owned':
    clean+=len(trials['event_ok']);cleanbad+=sum(not(a and b) for a,b in zip(trials['event_ok'],trials['control_ok']));continue
   if not bases[r['case']]['eligible'][mode]:continue
   k=(r['case'],mode,r['strategy'])
   observations[k].append(any(trials['changed']))
   metadata[(r['case'],mode)]={'family':r['family'],'cohort':r['cohort'],'newmode':mode in NEW}
 units=[]
 for (case,mode),meta in metadata.items():
  units.append(dict(case=case,mode=mode,**meta,values={s:statistics.mean(observations[(case,mode,s)]) for s in STRATEGIES}))
 cohorts={'all':units,'old-input-old-action':[u for u in units if u['cohort']!='structural' and not u['newmode']],
  'new-input-old-action':[u for u in units if u['cohort']=='structural' and not u['newmode']],
  'old-input-new-action':[u for u in units if u['cohort']!='structural' and u['newmode']],
  'new-input-new-action':[u for u in units if u['cohort']=='structural' and u['newmode']],
  'new-input-all-action':[u for u in units if u['cohort']=='structural']}
 summary={}
 rng=np.random.default_rng(202610042)
 for name,uu in cohorts.items():
  rate={s:statistics.mean(u['values'][s] for u in uu)*100 for s in STRATEGIES}
  groups=defaultdict(list)
  for u in uu:groups[u['family']].append(u['values']['callback-aware']-u['values']['fixed'])
  vals=list(groups.values());diff=statistics.mean(x for g in vals for x in g)*100
  samples=[]
  for _ in range(2000):
   ix=rng.integers(0,len(vals),len(vals));samples.append(statistics.mean(x for i in ix for x in vals[i])*100)
  summary[name]={'units':len(uu),'families':len(vals),'rates':rate,'callback-aware_minus_fixed_pp':diff,'family_bootstrap_95':np.quantile(samples,[.025,.975]).tolist()}
 src=defaultdict(lambda:{'streams':0,'checks':0,'whole_mismatch':0,'changed_streams':0,'changed_checks':0})
 for r in readlines(out/'sources.jsonl.gz'):
  g=src[r['adapter']];g['streams']+=1;g['checks']+=r['tests'];g['whole_mismatch']+=not r['whole_ok'];g['changed_streams']+=any(t['changed'] for t in r['trials']);g['changed_checks']+=sum(bool(t['changed']) for t in r['trials'])
 modeinfo={}
 for m in sorted(set(u['mode'] for u in units)):
  subset=[u for u in units if u['mode']==m]
  modeinfo[m]={'units':len(subset),'rates':{s:statistics.mean(u['values'][s] for u in subset)*100 for s in STRATEGIES}}
 data={'cohorts':summary,'source':dict(src),'controls':modeinfo,'clean_campaign_checks':clean,'clean_campaign_mismatches':cleanbad}
 analysis=out/'analysis';analysis.mkdir(exist_ok=True)
 (analysis/'summary.json').write_text(json.dumps(data,indent=2)+'\n')
 with (analysis/'units.jsonl.gz').open('wb') as f:
  with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as g:
   for u in units:g.write((json.dumps(u)+'\n').encode())
 with (analysis/'detection.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['cohort','units','strategy','detection_percent'])
  for c,r in summary.items():
   for s,v in r['rates'].items():w.writerow([c,r['units'],s,v])
 print(json.dumps(data,indent=2))
if __name__=='__main__':main()
