"""Run unchanged pinned Python tests, recording an unavailable optional module."""
from __future__ import annotations
import argparse,json,subprocess,os,sys,importlib.util,xml.etree.ElementTree as ET
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',default='results/study');a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 root=Path('upstream-tests/httpx-sse-0.4.3');cmd=[sys.executable,'-m','pytest',str(root),'-q','--junitxml='+str(out/'upstream-tests.xml')];excluded=[]
 if importlib.util.find_spec('sse_starlette') is None:
  cmd+=['--ignore='+str(root/'test_asgi.py')];excluded.append({'file':'test_asgi.py','tests':1,'reason':'optional sse_starlette dependency is unavailable'})
 env=dict(os.environ,PYTHONPATH=os.pathsep.join(['vendor','.']));r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30);(out/'upstream-tests.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError('upstream test run failed; see log')
 tree=ET.parse(out/'upstream-tests.xml');suites=list(tree.getroot().iter('testsuite'))
 report={'status':'passed_available_tests' if excluded else 'passed_full_tests','tests':sum(int(s.attrib.get('tests',0)) for s in suites),'failures':sum(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0)) for s in suites),'excluded':excluded,'command':cmd,'source':'unchanged pinned httpx-sse 0.4.3 tests'}
 (out/'upstream-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
if __name__=='__main__':main()
