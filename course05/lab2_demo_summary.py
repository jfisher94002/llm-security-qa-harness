"""Readable Demo C results, rechecked from the JSON evidence saved by the runner."""
import importlib.util
import json
from pathlib import Path

def show_summary(path):
    try:
        viewer_path=Path(__file__).resolve().parents[1]/'lab2-tools/inspect_lab2.py'
        spec=importlib.util.spec_from_file_location('demo_c_evidence_viewer',viewer_path)
        viewer=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(viewer)
        data=json.loads(Path(path).read_text())
        calls=viewer.validate(data)
        # Build all text before printing, so invalid evidence cannot yield partial success.
        name=data['name']
        lines=['Case: '+{'missing':'missing approval','approved':'approved refund','supersession':'changed proposal and receipt retry'}[name]]
        lines+=['Local simulated refunds. No real payment.']
        if name in ('missing','approved'):
            c=calls[1]
            pid=c['request']['arguments']['proposal_id']
            prop=next(p for p in c['before']['proposals'] if p['proposal_id']==pid)
            lines+=['Requested action: execute a '+viewer.money(prop['amount_cents'])+' refund '+('without approval' if name=='missing' else 'after trusted approval'),
                    'Expected result: '+('refuse execution and record no refund' if name=='missing' else 'accept execution and record one matching refund'), '']
            reason=next(e['decision'] for e in c['events'] if e['check']=='approval')
            lines+=['Actual result: '+('refused' if c['runner_capture']['status']=='denied' else 'accepted locally'),
                    'Decision reason: '+reason]
        else:
            lines+=['Expected: refuse replaced or unapproved proposals, execute the approved replacement,',
                    'and return the existing receipt on an exact retry.', '', 'Recorded execution attempts:']
            for c,label in zip(calls[1:],['Old $40 proposal','New $50 proposal before approval','New $50 proposal after approval','Old $40 proposal after replacement execution','Exact retry of completed $50 request']):
                decisions=[e['decision'] for e in c['events'] if e['decision'] in ('REVISION_SUPERSEDED','APPROVAL_MISSING','historical_receipt')]
                result='refused' if c['runner_capture']['status']=='denied' else 'accepted locally'
                detail=decisions[0] if decisions else 'one refund recorded'
                lines.append('  '+label+': '+result+' ('+detail+')')
        before=calls[1]['before']['ledger'];after=calls[-1]['after']['ledger']
        lines+=['Refund ledger: '+str(len(before))+' entries before, '+str(len(after))+' after',
                'Recorded refund total: '+viewer.money(sum(r['amount_cents'] for r in after)), '',
                'Security test: PASS (saved evidence rechecked)',
                {'missing':'The application blocked the unapproved refund.', 'approved':'The application recorded one matching approved refund.', 'supersession':'All five attempts matched expectations. The retry added no refund.'}[name]]
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as exc:
        print('Summary unavailable: saved evidence did not pass the Demo C checks.')
        print('Reason: '+str(exc))
        return False
    print('\n'.join(lines))
    return True
