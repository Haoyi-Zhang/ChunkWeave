from __future__ import annotations
import itertools,unittest
from dataclasses import replace
from chunkweave.oracle import evaluate,slices
from chunkweave.model import IncrementalModel
from chunkweave.quotient import Snapshot,execute,search,advance,finish
from chunkweave.fast_schedules import fast_trace,portfolio,lazy_portfolio
from chunkweave.schedules import trace
from chunkweave.validation_corpus import all_cases,extensions
from chunkweave.adapters import NodeWorker,httpx_source_adapter
from chunkweave.reduce import minimize

class CoreTests(unittest.TestCase):
 def test_unique_corpus(self):
  c=all_cases();self.assertEqual(len(c),len({x['text'] for x in c}));self.assertEqual(len(c),393)
 def test_manual_truth_table(self):
  truths=[x for x in extensions() if 'manual_expected' in x];self.assertEqual(len(truths),24)
  for c in truths:self.assertEqual(evaluate(c['text'].encode()),c['manual_expected'],c['id'])
 def test_fast_trace_exact(self):
  for c in all_cases():
   b=c['text'].encode();d=fast_trace(b)
   if c['family']=='validation-long-single-field' and len(b)>4096:
    # Avoid rerunning the quadratic reference tracer as a smoke test.
    # Check 65 sampled exact states against its underlying independent model.
    m=IncrementalModel();a=0
    for end in sorted({len(b)*i//64 for i in range(1,65)}):
     m.feed(b[a:end]);a=end
     self.assertEqual(d.states[end],m.boundary_state()+(bool(m.events),m.first))
     self.assertEqual((d.chars[end],d.lines[end],d.epochs[end]),(m.characters,m.line_number,m.epoch))
   else:
    a=trace(b)
    for key in ('states','chars','lines','epochs'):self.assertEqual(getattr(a,key),getattr(d,key),(c['id'],key))
 def test_three_independent_evaluations(self):
  for c in all_cases():
   b=c['text'].encode();m=IncrementalModel()
   for part in slices(b,list(range(5,len(b),5))):m.feed(part)
   self.assertEqual(m.finish(),c['expected'],c['id'])
   self.assertEqual(execute(b,list(range(7,len(b),7))),c['expected'],c['id'])
 def test_retry_bounds(self):
  for text in ('retry: 0000000\n\n','retry: 60001\n\n'):
   b=text.encode()
   with self.assertRaises(ValueError):evaluate(b)
   with self.assertRaises(ValueError):m=IncrementalModel();m.feed(b)
   with self.assertRaises(ValueError):execute(b,[])
 def test_noninteger_cuts(self):
  for cuts in ([True],[1.0],['1'],[-1],[0],[3],[2,1],[1,1]):
   with self.assertRaises(ValueError):slices(b'abc',cuts)
 def test_invalid_utf8(self):
  for f in (evaluate,fast_trace):
   with self.assertRaises(UnicodeError):f(b'\xff')
  with self.assertRaises(UnicodeError):execute(b'\xff',[])
 def test_size_bound(self):
  for f in (evaluate,fast_trace):
   with self.assertRaises(ValueError):f(b'x'*65537)
  with self.assertRaises(ValueError):execute(b'x'*65537,[])
 def test_empty_stream(self):
  self.assertEqual(execute(b'',[]),evaluate(b''));self.assertEqual(search(b'')['status'],'CERTIFIED')
 def test_snapshot_retains_text(self):
  a=Snapshot(line='data:a',decoder_flag=0);b=replace(a,line='data:b')
  self.assertNotEqual(a,b)
  self.assertNotEqual(finish(advance(a,b'\n\n')),finish(advance(b,b'\n\n')))
 def test_snapshot_restore(self):
  raw='id:7\ndata:中\r\n\r\n'.encode();s=Snapshot()
  for i,part in enumerate(slices(raw,[4,12,13])):s=advance(s,part,had_feed=i>0)
  self.assertEqual(finish(s),evaluate(raw))
 def test_shortest_witness(self):
  raw='data:中\n\n'.encode();r=search(raw,'empty_reset')
  self.assertEqual(r['minimum_cuts'],2)
  self.assertTrue(all(execute(raw,[i],'empty_reset')==evaluate(raw) for i in range(1,len(raw))))
 def test_model_verdict_scope_and_caps(self):
  b=b'data:x\n\n';self.assertEqual(search(b)['status'],'CERTIFIED')
  self.assertEqual(search(b,max_edges=1)['status'],'UNKNOWN')
  self.assertEqual(search(b,max_nodes=1)['status'],'UNKNOWN')
 def test_large_unknown_count_serialization(self):
  r=search(b'data:'+b'x'*60000+b'\n\n',max_edges=0)
  self.assertEqual(r['status'],'UNKNOWN');self.assertTrue(r['partition_count'].startswith('2^'))
 def test_partition_graph_edges(self):
  n=32;r=search(b'data:'+b'x'*(n-7)+b'\n\n')
  self.assertEqual(r['edges'],n*(n+1)//2);self.assertEqual(int(r['partition_count']),1<<(n-1))
 def test_portfolio_lazy_equivalence(self):
  for text in ('data:hello\n\n','data:中\r\n\r\n','x'):
   b=text.encode();self.assertEqual(list(lazy_portfolio(b)),portfolio(b))
 def test_portfolio_schedules(self):
  b='data:中\r\n\r\n'.encode();p=portfolio(b)
  self.assertEqual(p[0],list(range(1,len(b))));self.assertLessEqual(len(p),16)
  for cuts in p:self.assertEqual(b''.join(slices(b,cuts)),b)
 def test_bom_ownership_repair(self):
  b='\ufeff\ufeffdata:hidden\n\ndata:visible\n\n'.encode();expected=evaluate(b)
  with NodeWorker() as w:
   for r in w.run(b,[[],list(range(1,len(b)))],['correct','bom_owned']):
    self.assertNotEqual(r['correct']['events'],expected['events'])
    self.assertEqual({k:r['bom_owned'][k] for k in expected},expected)
 def test_python_retry_observation(self):
  r=httpx_source_adapter(b'retry:5\nretry:bogus\ndata:x\n\n',[])
  self.assertEqual(r['retries'],[5])
 def test_azure_payload_not_repaired(self):
  b=b'data:\ndata:x\n\n'
  with NodeWorker('azure_worker.mjs') as w:
   a=w.run(b,[[],list(range(1,len(b)))])
   self.assertEqual(a[0]['correct']['events'],a[1]['correct']['events'])
   self.assertNotEqual(a[0]['correct']['events'],evaluate(b)['events'])
 def test_reducer_preconditions(self):
  with self.assertRaises(ValueError):minimize([1],lambda x:True)
  with self.assertRaises(ValueError):minimize([1],lambda x:False)
  with self.assertRaises(ValueError):minimize([1],lambda x:bool(x),budget=1)
  with self.assertRaises(ValueError):minimize([2,1],lambda x:bool(x))
 def test_reducer_budget_honesty(self):
  r=minimize([1,2,3,4],lambda s:1 in s and 4 in s,budget=2)
  self.assertTrue(r['budget_limited']);self.assertFalse(r['one_minimal'])
if __name__=='__main__':unittest.main()
