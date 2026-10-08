import unittest
from fractions import Fraction
from math import comb
from chunkweave.shadow_law import profile, predicts_failure, failure_spectrum, failure_probability
from chunkweave.spectrum import count
from chunkweave.quotient import execute
from chunkweave.obligations import iterate, landmarks
from chunkweave.oracle import evaluate, slices
from chunkweave.adapters import NodeWorker
from chunkweave.corpus_extensions import new_cases, cases

class Shadow(unittest.TestCase):
 def test_profile_boundaries(self):
  raw='data:\n\ndata:é\n\n'.encode();p=profile(raw)
  self.assertEqual(p.dispatches,(7,16));self.assertEqual(p.interiors,frozenset({13}))
 def test_rejected_law_profiles(self):
  for s in ('','data:a\n','data:a\r\n\r\n','data:\ufeff\n\n','data:\ufffd\n\n','event:x\n\n','data:a\ndata:b\n\n'):
   with self.subTest(s=s),self.assertRaises(ValueError):profile(s.encode())
 def test_spectrum_known_values(self):
  for ch,expected in [('é',256),('中',768),('🌍',1792)]:
   raw=('data:\n\ndata:'+ch+'\n\n').encode();a=failure_spectrum(raw)
   self.assertEqual(sum(a),expected);self.assertEqual(a[0],0);self.assertEqual(a[-1],0)
   self.assertEqual(a[1],len(ch.encode())-1)
 def test_graph_mass_and_analytical_spectrum(self):
  for s in ('data:\n\ndata:é\n\n','data:a\n\ndata:中\n\n','data:é\n\ndata:中🌍\n\ndata:xé\n\n'):
   raw=s.encode();g=count(raw,'decoder_per_event')
   self.assertEqual(g['status'],'EXACT');self.assertEqual(g['total'],[comb(len(raw)-1,k) for k in range(len(raw))]);self.assertEqual(g['failures'],failure_spectrum(raw))
 def test_correct_graph_no_failure(self):
  g=count('data:中\n\n'.encode());self.assertEqual(g['status'],'EXACT');self.assertFalse(any(g['failures']))
 def test_unknown_is_not_pass(self):
  raw=b'data:a\n\n'
  for kwargs in ({'max_bytes':3},{'max_edges':0},{'max_nodes':1}):
   g=count(raw,**kwargs);self.assertEqual(g['status'],'UNKNOWN');self.assertNotIn('failures',g)
 def test_probability_comes_from_mass(self):
  raw='data:a\n\ndata:é\n\ndata:中\n\n'.encode();coeffs=failure_spectrum(raw)
  for q in (Fraction(0),Fraction(1,64),Fraction(1,8),Fraction(1,2),Fraction(1)):
   self.assertEqual(failure_probability(raw,q),sum(Fraction(v)*q**k*(1-q)**(len(raw)-1-k) for k,v in enumerate(coeffs)))
 def test_cut_predecessor_matters(self):
  raw='data:a\n\ndata:中\n\n'.encode()
  self.assertTrue(predicts_failure(raw,[14]));self.assertFalse(predicts_failure(raw,[8,14]));self.assertFalse(predicts_failure(raw,list(range(1,len(raw)))))
 def test_two_tests_cover_declared_families(self):
  with NodeWorker() as w:
   for ch in ('é','中','🌍'):
    for text,mode in [('data:'+ch+'\n\n','empty_reset'),('data:\n\ndata:'+ch+'\n\n','decoder_per_event')]:
     raw=text.encode();schedule=list(iterate(raw,two_only=True));rr=w.run(raw,schedule,[mode],expected=evaluate(raw))
     self.assertLessEqual(len(schedule),2);self.assertTrue(any(not r[mode]['event_ok'] for r in rr))
 def test_benign_skip_empty_preserves_source_semantics(self):
  with NodeWorker() as w:
   for s in ('data:é\n\n','\ufeffdata:中\r\n\r\n','data:\ufeff\ufffd🌍\n\n'):
    raw=s.encode();rr=w.run(raw,[[],list(range(1,len(raw)))],['bom_owned','skip_empty'],expected=evaluate(raw))
    self.assertTrue(all(v['event_ok'] and v['control_ok'] for r in rr for v in r.values()))
 def test_schedule_budget_and_validity(self):
  raw='retry:10\n\ndata:a\n\ndata:中é🌍\n\n'.encode()
  for budget in (1,2,4,16):
   cs=list(iterate(raw,budget=budget));self.assertLessEqual(len(cs),budget);self.assertEqual(len({tuple(c) for c in cs}),len(cs))
   for cuts in cs:self.assertEqual(b''.join(slices(raw,cuts)),raw)
  self.assertTrue(landmarks(raw)['shadow'])
 def test_schedule_rejects_bad_inputs(self):
  for raw in (b'\xff',b'x'*65537):
   with self.assertRaises(ValueError):list(iterate(raw))
  for cap in (0,-1,True,1.2):
   with self.assertRaises(ValueError):list(iterate(b'data:a\n\n',budget=cap))
 def test_structural_cohort_separation(self):
  allc=cases();cc=new_cases()
  self.assertEqual(len(cc),144);self.assertEqual(len(allc),537)
  self.assertEqual(len({c['text'].encode() for c in allc}),537)
  self.assertEqual(len({c['family'] for c in cc}),8)
  for c in cc:self.assertEqual(c['expected'],evaluate(c['text'].encode()))
 def test_new_boundary_actions_execute(self):
  raw='retry:10\n\ndata:a\n\ndata:中\n\n'.encode()
  with NodeWorker() as w:
   rr=w.run(raw,[[],[len(raw)-3]],['parser_per_event','decoder_per_retry','parser_per_retry'])
  self.assertEqual(set(rr[0]),{'parser_per_event','decoder_per_retry','parser_per_retry'})
  for mode in rr[0]:self.assertEqual(rr[0][mode]['events'],evaluate(raw)['events'])

if __name__=='__main__':unittest.main()

class ProjectionChecks(unittest.TestCase):
 def test_projection_preserves_callback_landmarks(self):
  from chunkweave.landmark_projection import LandmarkProjection
  from chunkweave.model import IncrementalModel
  for text in ('\ufeffdata: 中\r\nretry: 12\n\ndata\n\n','data:a\r\rdata:é\r\n\r\n','retry:  2\nretry:０\ndata:\ufeff\n\n','data:\n:\n\n'):
   q=LandmarkProjection();m=IncrementalModel()
   for b in text.encode():
    q.feed_byte(b);m.feed(bytes((b,)))
    self.assertEqual((q.need,q.events,q.retries,q.prefix),(m.need,len(m.events),len(m.retries),''.join(m.line[:6])))
 def test_projection_has_bounded_text_state(self):
  from chunkweave.landmark_projection import LandmarkProjection
  q=LandmarkProjection()
  for b in b'data:'+b'a'*60000+b'\n\n':
   q.feed_byte(b);self.assertLessEqual(len(q.prefix),6);self.assertLessEqual(len(q.field_name),6)
  self.assertEqual(q.events,1);self.assertEqual(q.retries,0)
 def test_cli_semantic_and_partition_statuses(self):
  from chunkweave.audit import audit
  self.assertEqual(audit(b'data:x\n\n')['status'],'NO_DISCREPANCY_IN_TEST_SET')
  self.assertEqual(audit(b'data\n\n',adapter='azure')['status'],'WHOLE_SEMANTIC_DIFFERENCE')
 def test_projection_rejects_incomplete_final_scalar(self):
  from chunkweave.landmark_projection import LandmarkProjection
  q=LandmarkProjection();q.feed_byte(0xe4)
  with self.assertRaises(ValueError):q.finish()
