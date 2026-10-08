"""Check every byte prefix and every selected partition against the old model."""
import argparse,json,time,itertools
from pathlib import Path
from chunkweave.landmark_projection import LandmarkProjection
from chunkweave.model import IncrementalModel
from chunkweave.corpus_extensions import cases
from chunkweave.obligations import iterate
from chunkweave.obligations_reference import iterate as reference

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='results/study/projection-audit.json');a=p.parse_args()
 data=[c['text'].encode() for c in cases()]
 # Small syntax combinations complement long authored streams. Invalid retry
 # values are valid ignored SSE fields; all byte strings remain valid UTF-8.
 blocks=['data\n','data:\n','data: x\n','data: 中\n','retry: 0\n','retry: 1a\n','retry: １２\n','retry:  2\n','retry\n',': comment\n','id: x\n','unknown: a\n','\n']
 data += [''.join(parts).encode() for parts in itertools.product(blocks,repeat=3)]
 start=time.perf_counter();prefixes=plans=0
 for raw in data:
  q=LandmarkProjection();m=IncrementalModel()
  for b in raw:
   q.feed_byte(b);m.feed(bytes((b,)));prefixes+=1
   assert(q.need,q.events,q.retries,q.prefix)==(m.need,len(m.events),len(m.retries),''.join(m.line[:6])),(raw,b,q.prefix,m.line)
  q.finish()
  for opts in ({},{'two_only':True},{'shadows':False}):
   a1=list(iterate(raw,**opts));a2=list(reference(raw,**opts));assert a1==a2,(raw,opts);plans+=len(a1)
 out={'status':'passed','streams':len(data),'byte_prefixes':prefixes,'same_selected_schedules':plans,
      'corpus_streams':537,'syntax_combinations':len(blocks)**3,'wall_seconds':time.perf_counter()-start,
      'scope':'every byte prefix on this finite audit; exact projection proof is separate'}
 Path(a.out).write_text(json.dumps(out,indent=2)+'\n');print(out)
if __name__=='__main__':main()
