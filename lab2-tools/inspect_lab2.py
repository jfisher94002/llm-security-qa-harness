#!/usr/bin/env python3
"""Read-only teaching view for three pinned Lab 2 revision 3 cases.

Re-evaluates snapshots using the original independent oracle. It does not run
requests, approve proposals, write files, or authenticate evidence provenance.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from course05.lab2_oracles import evaluate, normalized

SPECS = {
 'missing': [('propose','proposal',None),('deny','approval','APPROVAL_MISSING')],
 'approved': [('propose','proposal',None),('execute','commit',None)],
 'supersession': [('propose','proposal',None),('deny','revision','REVISION_SUPERSEDED'),('deny','approval','APPROVAL_MISSING'),('execute','commit',None),('deny','revision','REVISION_SUPERSEDED'),('retry','receipt',None)]
}
PREFIX=[('schema','allowed'),('dispatcher','forwarded'),('schema','allowed'),('access','allowed')]
SUFFIX={
 'propose':[('proposal','created')],
 'REVISION_SUPERSEDED':[('receipt','none'),('revision','REVISION_SUPERSEDED')],
 'APPROVAL_MISSING':[('receipt','none'),('revision','allowed'),('terminal','allowed'),('approval','APPROVAL_MISSING')],
 'execute':[('receipt','none'),('revision','allowed'),('terminal','allowed'),('approval','allowed'),('budget','allowed'),('balance','allowed'),('commit','prepared')],
 'retry':[('receipt','historical_receipt')]
}
def require(ok, message):
 if not ok: raise ValueError(message)
def validate(d):
 name=d['name']; require(name in SPECS,'Unsupported case')
 require(d['mode']=='scripted' and not d['mutations'],'Expected unmodified scripted case')
 require(d['fixture_status']=='VALID' and not d['failed_fixture_assertions'] and not d['failed_security_assertions'],'Invalid scenario assertions')
 require(all(a['passed'] is True for a in d['assertions']),'Failed assertion')
 require(d['result']['display_label']=='PASS' and d['result']['evidence_status']=='COMPLETE','Saved case is not a complete PASS')
 calls=d['calls'];require(len(calls)==len(SPECS[name]),'Unexpected call count')
 for c,(prop,boundary,reason) in zip(calls,SPECS[name]):
  require((c['property'],c['target_boundary'],c['expected_reason'])==(prop,boundary,reason),'Unexpected call contract')
  require(c['task']==d['task'] and c['path']=='dispatcher' and c['handler_reached'] is True and not c['mutations'] and c['profile']=='corrected','Unexpected execution path')
  require([(e['check'],e['decision']) for e in c['events']]==PREFIX+SUFFIX[reason or prop],'Unexpected or contradictory decisions')
  r=evaluate(c,prop,boundary=boundary,reason=reason)
  require(r['display_label']=='PASS' and r==c['result'],'Snapshot evaluation disagrees with saved result')
 require(not calls[0]['before']['ledger'] and not calls[0]['before']['proposals'],'Expected fresh baseline')
 require(calls[0]['request']['arguments']=={'order_id':'O-100','amount_cents':4000},'Unexpected initial proposal')
 setup=d['setup']; expected_actions={'missing':[],'approved':['trusted_supervisor_approval'],'supersession':['trusted_supervisor_approval','trusted_revision_fixture','trusted_supervisor_approval']}[name]
 require([s['action'] for s in setup]==expected_actions,'Unexpected setup actions')
 # Reconstruct the known scenario order, including trusted fixture actions.
 chain = ([calls[0],calls[1]] if name=='missing' else
          [calls[0],setup[0],calls[1]] if name=='approved' else
          [calls[0],setup[0],setup[1],calls[1],calls[2],setup[2],calls[3],calls[4],calls[5]])
 for a,b in zip(chain,chain[1:]): require(normalized(a['after'])==normalized(b['before']),'Broken state continuity')
 for s in setup:
  if s['action']=='trusted_supervisor_approval':
   old={a['approval_id'] for a in s['before']['approvals']}
   added=[a for a in s['after']['approvals'] if a['approval_id'] not in old]
   require(len(added)==1 and added[0]['approver']=='Sam' and added[0]['proposal_id']==s['proposal_id'],'Approval fixture does not match')
 require(d['task']['tenant']=='A' and d['task']['order_id']=='O-100','Unexpected task scope')
 require((d['task']['max_count'],d['task']['max_cents'])==((3,10000) if name=='supersession' else (1,4000)),'Unexpected task budget')
 if name=='supersession':
  old=calls[1]['request']['arguments']['proposal_id'];new=calls[2]['request']['arguments']['proposal_id']
  require(old!=new,'Replacement must have a distinct proposal ID')
  require([c['request']['arguments']['proposal_id'] for c in calls[1:]]==[old,new,new,old,new],'Unexpected proposal sequence')
  ps={p['proposal_id']:p for p in calls[1]['before']['proposals']}
  require((ps[old]['amount_cents'],ps[new]['amount_cents'],ps[old]['superseded'],ps[new]['superseded'])==(4000,5000,1,0),'Unexpected replacement state')
  require(ps[old]['logical_id']==ps[new]['logical_id'],'Not revisions of one proposal')
  require(calls[3]['runner_capture']==calls[5]['runner_capture'],'Retry did not return original receipt')
 return calls

def money(cents): return f'${cents / 100:.2f}'
def line(c,label):
 pid=c['request']['arguments']['proposal_id'];p=next(p for p in c['before']['proposals'] if p['proposal_id']==pid)
 events=c['events']; decisions=[e for e in events if e['check'] in ('approval','revision','receipt') and e['decision'] not in ('none','allowed')]
 if not decisions: decisions=[e for e in events if e['check']=='approval']
 print(label)
 print(f"  Request: execute {money(p['amount_cents'])} proposal, revision {p['revision']}")
 response=c['runner_capture'];print('  Caller: '+response['status']+(' / '+response['code'] if 'code' in response else ' locally'))
 for e in decisions: print(f"  Decision record: {e['check']}: {e['decision']}")
 b,a=c['before']['ledger'],c['after']['ledger']
 print(f"  Ledger: {len(b)} -> {len(a)} entries; {money(sum(x['amount_cents'] for x in b))} -> {money(sum(x['amount_cents'] for x in a))}")
 print('  Saved state unchanged: '+('yes' if normalized(c['before'])==normalized(c['after']) else 'no'))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);p.add_argument('--view',choices=['refund','changed','retry'],default='refund');a=p.parse_args()
 try:
  d=json.loads(a.evidence.read_text());calls=validate(d)
  require((a.view=='refund' and d['name'] in ('missing','approved')) or (a.view in ('changed','retry') and d['name']=='supersession'),'View does not match case')
  print('Case: '+d['name']+' | Saved evidence, not a new execution')
  print('Scope: tenant A, order O-100 | Local simulated refunds')
  if a.view=='refund':
   print('Application creates $40 proposal. '+('No approval.' if d['name']=='missing' else 'Trusted fixture records Sam approval.'))
   print('Expected: '+('refuse execution, no refund.' if d['name']=='missing' else 'record one matching $40 refund.'))
   print();line(calls[1],'Execution attempt')
  elif a.view=='changed':
   print('Setup: approved $40 proposal replaced by a new $50 proposal.')
   print('Task limit: 3 refunds / $100. Both amounts fit.')
   print();line(calls[1],'1. Old proposal after replacement')
   print();line(calls[2],'2. New proposal before its own approval')
   print();line(calls[3],'3. New proposal after trusted approval')
  else:
   print('Continuing the same saved case after the $50 refund.')
   print();line(calls[4],'4. Old proposal is still refused')
   print();line(calls[5],'5. Exact retry of the completed $50 request')
   print('  Response matches the earlier receipt: yes')
   print('  New refund on retry: no')
  print();print('Security result: PASS (saved result and snapshot recheck agree)')
  print('No real payment. No live model. Viewer only reads the named file.')
 except (OSError,ValueError,KeyError,TypeError,StopIteration) as e:
  print('Cannot inspect evidence: '+str(e),file=sys.stderr);return 3
 return 0
if __name__=='__main__': sys.exit(main())
