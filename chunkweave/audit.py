"""Audit a bounded local SSE fixture with actual pinned source integrations.

Examples:
    python -m chunkweave.audit --text 'data:hello\n\n' --adapter js
    python -m chunkweave.audit --file examples/progress.sse --adapter python
This command accepts local bytes only. It never contacts a server.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .oracle import evaluate
from .obligations import iterate
from .adapters import NodeWorker,httpx_source_adapter

FIELDS=('events','retries','last_event_id')
def project(observation):return {k:observation[k] for k in FIELDS}
def audit(raw:bytes,adapter:str='js',budget:int=16)->dict:
 if not isinstance(raw,bytes):raise TypeError('input must be bytes')
 expected=evaluate(raw)
 plans=[[]]+list(iterate(raw,budget=budget));plans=list(dict.fromkeys(tuple(p) for p in plans))
 if adapter=='python':observed=[httpx_source_adapter(raw,list(p)) for p in plans]
 elif adapter in ('js','js-skip-empty','azure'):
  worker='azure_worker.mjs' if adapter=='azure' else 'node_worker.mjs'
  mode={'js':'bom_owned','js-skip-empty':'skip_empty','azure':'correct'}[adapter]
  with NodeWorker(worker) as w:observed=[r[mode] for r in w.run(raw,[list(p) for p in plans],[mode])]
 else:raise ValueError('unknown adapter')
 base=project(observed[0]);whole_ok=base==expected
 differences=[{'cuts':list(p),'whole_equal':project(o)==base,'semantic_equal':project(o)==expected,'actual':project(o)}
              for p,o in zip(plans,observed) if project(o)!=expected or project(o)!=base]
 changed=any(project(o)!=base for o in observed[1:])
 status='SEGMENTATION_DIFFERENCE' if changed else 'WHOLE_SEMANTIC_DIFFERENCE' if not whole_ok else 'NO_DISCREPANCY_IN_TEST_SET'
 return dict(status=status,adapter=adapter,bytes=len(raw),tests=len(plans),whole_semantics_equal=whole_ok,partition_changed=changed,
  expected=expected,differences=differences,scope='Exact slices of this local byte stream; a sampled source audit, not universal library certification.')
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
 g.add_argument('--file',type=Path);g.add_argument('--text',help='literal text; use actual newline characters')
 p.add_argument('--adapter',choices=('js','js-skip-empty','python','azure'),default='js');p.add_argument('--budget',type=int,default=16)
 p.add_argument('--out',type=Path);a=p.parse_args()
 try:
  if not 1<=a.budget<=64:raise ValueError('budget must be between 1 and 64')
  if a.file:
   with a.file.open('rb') as f:raw=f.read(65537)
  else:raw=a.text.encode('utf-8')
  result=audit(raw,a.adapter,a.budget)
  text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
  if a.out:a.out.write_text(text,encoding='utf-8')
  else:print(text,end='')
  return 0 if result['status']=='NO_DISCREPANCY_IN_TEST_SET' else 1
 except (OSError,ValueError,TypeError,RuntimeError) as e:
  print(json.dumps({'status':'ERROR','error':str(e)}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
