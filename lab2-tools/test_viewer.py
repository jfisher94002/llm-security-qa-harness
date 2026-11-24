"""Run after generating the three Demo C cases. Mutations use temporary copies."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ViewerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  missing=[n for n in ('missing','approved','supersession') if not (ROOT/'tmp_results/course05-lab2'/f'{n}.json').is_file()]
  if missing:
   raise unittest.SkipTest('Generate Demo C captures first using COMMANDS.txt. Missing cases: '+', '.join(missing))
 def run_view(self,d,view='refund'):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'case.json';p.write_text(json.dumps(d))
   return subprocess.run([sys.executable,str(ROOT/'lab2-tools/inspect_lab2.py'),str(p),'--view',view],capture_output=True,text=True)
 def load(self,name):return json.loads((ROOT/'tmp_results/course05-lab2'/f'{name}.json').read_text())
 def test_valid_views(self):
  for name,view in [('missing','refund'),('approved','refund'),('supersession','changed'),('supersession','retry')]:
   r=self.run_view(self.load(name),view);self.assertEqual(r.returncode,0,r.stderr)
   self.assertLessEqual(max(map(len,r.stdout.splitlines())),110)
   self.assertLessEqual(len(r.stdout.splitlines()),30)
 def test_reject_corruptions(self):
  edits=[lambda d:d['calls'][1].pop('after'),lambda d:d['calls'][1].update(input_capture='bad json'),lambda d:d['calls'][1]['events'].append({'check':'approval','decision':'allowed'}),lambda d:d['calls'][1]['after']['ledger'].append({'amount_cents':4000}),lambda d:d['calls'][1]['request']['arguments'].update(proposal_id='unknown'),lambda d:d['result'].update(display_label='ERROR'),lambda d:d.update(mutations=['V1']),lambda d:d['calls'].pop(),lambda d:d['calls'][0]['request']['arguments'].update(amount_cents=5000)]
  for edit in edits:
   d=self.load('missing');edit(d);r=self.run_view(d)
   self.assertEqual(r.returncode,3,r.stdout);self.assertNotIn('Security result: PASS',r.stdout)
 def test_wrong_view(self):self.assertEqual(self.run_view(self.load('approved'),'retry').returncode,3)
 def test_retry_corruption(self):
  d=self.load('supersession');d['calls'][5]['runner_capture']['receipt_id']='other'
  self.assertEqual(self.run_view(d,'retry').returncode,3)
if __name__=='__main__':unittest.main()
