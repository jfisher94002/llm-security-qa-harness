"""Regression checks for CLI summaries and refusal to summarize corrupt evidence."""
import contextlib,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from course05.lab2_demo_summary import show_summary
class SummaryTests(unittest.TestCase):
 def test_cli_text_and_json(self):
  for name,expected in [('missing','Actual result: refused'),('approved','Actual result: accepted locally'),('supersession','The retry added no refund.')]:
   with tempfile.TemporaryDirectory() as td:
    args=[sys.executable,'-m','course05.lab2','run','--case',name,'--output-dir',td]
    r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True)
    self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn(expected,r.stdout)
    r=subprocess.run(args+['--json-summary'],cwd=ROOT,capture_output=True,text=True)
    self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout.splitlines()[0])['display_label'],'PASS')
 def test_corrupt_saved_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   r=subprocess.run([sys.executable,'-m','course05.lab2','run','--case','missing','--output-dir',td],cwd=ROOT,capture_output=True,text=True)
   self.assertEqual(r.returncode,0)
   p=Path(td)/'missing.json';d=json.loads(p.read_text());d['calls'][1]['after']['ledger'].append({'amount_cents':4000});p.write_text(json.dumps(d))
   out=io.StringIO()
   with contextlib.redirect_stdout(out):ok=show_summary(p)
   self.assertFalse(ok);self.assertNotIn('Security test: PASS',out.getvalue())
if __name__=='__main__':unittest.main()
