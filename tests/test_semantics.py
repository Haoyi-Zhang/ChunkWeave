import itertools,unittest
from chunkweave.oracle import evaluate,slices
from chunkweave.model import IncrementalModel
from chunkweave.adapters import NodeWorker,httpx_source_adapter
from chunkweave.corpus import records
from chunkweave.schedules import trace,generate
from chunkweave.reduce import minimize

class Semantics(unittest.TestCase):
 def test_all_corpus_oracles(self):
  for c in records():
   raw=c['text'].encode();m=IncrementalModel()
   for chunk in slices(raw,range(3,len(raw),3)):m.feed(chunk)
   self.assertEqual(m.finish(),evaluate(raw),c['id'])
 def test_three_byte_single_vs_pair(self):
  raw='data:中\n\n'.encode();expected=evaluate(raw)
  with NodeWorker() as w:
   single=w.run(raw,[[]]+[[i] for i in range(1,len(raw))],['empty_reset'])
   self.assertTrue(all(r['empty_reset']['events']==expected['events'] for r in single))
   pair=w.run(raw,[[6,7]],['empty_reset','correct'])[0]
   self.assertNotEqual(pair['empty_reset']['events'],expected['events'])
   self.assertEqual(pair['correct']['events'],expected['events'])
 def test_reference_contracts(self):
  with NodeWorker() as w:
   for c in records():
    if c['cohort']!='conformance':continue
    raw=c['text'].encode();expected=evaluate(raw);cuts=list(range(1,len(raw)))
    js=w.run(raw,[[],cuts])
    for r in js:self.assertEqual({k:r['correct'][k] for k in expected},expected,c['id'])
    py=httpx_source_adapter(raw,cuts)
    self.assertEqual({k:py[k] for k in expected},expected,c['id'])
 def test_partition_validation(self):
  for bad in ([0],[3],[2,1],[1,1]):
   with self.assertRaises(ValueError):slices(b'abc',bad)
 def test_reducer(self):
  r=minimize([1,2,3,4],lambda p:2 in p and 4 in p)
  self.assertEqual(r['reduced_cuts'],[2,4]);self.assertTrue(r['one_minimal'])
 def test_scheduler_boundaries(self):
  raw='data: 中\r\n\r\n'.encode();t=trace(raw)
  for kind in ('critical','no-decoder','no-parser','no-interaction'):
   schedules=generate(raw,kind,t=t)
   self.assertLessEqual(len(schedules),16)
   for cuts in schedules:
    self.assertEqual(b''.join(slices(raw,cuts)),raw)
    if kind=='no-interaction':self.assertLessEqual(len(cuts),1)
    if kind=='no-decoder':self.assertTrue(all(t.states[p][0]==0 for p in cuts))
if __name__=='__main__':unittest.main()
