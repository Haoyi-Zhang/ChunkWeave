"""Discovery-only curve and output-boundary regressions, without experiments."""
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from matplotlib.figure import Figure

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts/generate_paper.py'
spec=importlib.util.spec_from_file_location('discovery_renderer',SCRIPT)
renderer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
STRATEGIES=('fixed','state-feature-no-parser','callback-aware','two-obligation')


class DiscoveryPlot(unittest.TestCase):
 def test_curve_values_keep_non_detections_scales_labels_and_tight_output(self):
  data={name:[{'detected_ms':.1},{'detected_ms':1.0},{'detected_ms':None}] for name in STRATEGIES}
  close=renderer.plt.close
  with patch.object(Figure,'savefig') as save,patch.object(renderer.plt,'close') as closing:
   renderer.draw_discovery(data,Path('discovery.pdf'))
   fig=closing.call_args.args[0];axis=fig.axes[0]
   try:
    self.assertEqual(axis.get_xscale(),'log')
    self.assertEqual(axis.get_xlim(),(.04,50));self.assertEqual(axis.get_ylim(),(0,100))
    self.assertEqual(axis.get_ylabel(),'Detected eligible repeats (%)')
    for line,name in zip(axis.lines,STRATEGIES):
     expected_x=np.geomspace(.04,50,220)
     expected_y=[100*sum(r['detected_ms'] is not None and r['detected_ms']<=t for r in data[name])/len(data[name]) for t in expected_x]
     np.testing.assert_array_equal(line.get_xdata(),expected_x)
     np.testing.assert_array_equal(line.get_ydata(),expected_y)
     self.assertEqual(line.get_label(),renderer.LABEL[name])
     self.assertAlmostEqual(line.get_ydata()[-1],200/3)
    self.assertEqual(save.call_args.kwargs,{'bbox_inches':'tight','pad_inches':.08})
   finally:close(fig)

 def test_cli_writes_only_discovery_from_minimal_retained_records(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);source=root/'inputs';source.mkdir();paper=root/'paper'
   path=source/'timing.jsonl.gz'
   with gzip.open(path,'wt',encoding='utf-8') as f:
    for name in STRATEGIES:
     for value in (.1,1.0,None):f.write(json.dumps({'strategy':name,'detected_ms':value})+'\n')
   before=path.read_bytes();env=dict(os.environ,PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
   run=subprocess.run([sys.executable,'-B',str(SCRIPT),'--discovery-only','--out',str(source),'--paper',str(paper)],
                      env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
   self.assertEqual(run.returncode,0,run.stdout+run.stderr)
   self.assertEqual({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()},
                    {'inputs/timing.jsonl.gz','paper/figures/discovery.pdf'})
   self.assertEqual(path.read_bytes(),before)
   self.assertTrue((paper/'figures/discovery.pdf').read_bytes().startswith(b'%PDF-'))


if __name__=='__main__':unittest.main()
