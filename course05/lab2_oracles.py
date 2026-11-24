"""Independent snapshot assertions. Does not call authorization or execution code."""
import copy
import json

TABLES = ('orders','tasks','logical_proposals','proposals','approvals','ledger','receipts')
DENIAL = {'status':'denied','code':'access_denied','message':'Request denied'}


def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'))


def result(observed,evidence_ok=True,expected='PASS',diagnostics=()):
    label = ('ERROR' if not evidence_ok else 'EXPECTED_FAIL' if observed==expected=='FAIL'
             else 'UNEXPECTED_PASS' if expected=='FAIL' and observed=='PASS'
             else 'UNEXPECTED_FAIL' if expected=='PASS' and observed=='FAIL' else observed)
    return dict(expected_outcome=expected,observed_security_outcome=observed,
                evidence_status='COMPLETE' if evidence_ok else 'ERROR',
                expectation_match=evidence_ok and observed==expected,display_label=label,diagnostics=list(diagnostics))


def exit_code(results):
    if any(r['evidence_status']=='ERROR' for r in results):
        return 3
    if any(r['observed_security_outcome']=='FAIL' for r in results):
        return 1
    if any(r['observed_security_outcome']=='INCONCLUSIVE' for r in results):
        return 2
    return 0


def normalized(state):
    return {k:sorted(v,key=canonical) for k,v in state.items()}


def has_protected(value):
    if isinstance(value,dict):
        return bool(set(value)&{'approval','approval_ref','approvals','binding','approver','trusted_task','max_count','max_cents'}) or any(has_protected(v) for v in value.values())
    if isinstance(value,list):
        return any(has_protected(v) for v in value)
    if isinstance(value,str):
        try:
            parsed = json.loads(value)
        except (ValueError,TypeError):
            return False
        return has_protected(parsed) if isinstance(parsed,(dict,list)) else False
    return False


def foreign_order(value,allowed_order):
    if allowed_order is None:
        return False
    if isinstance(value,dict):
        return ('order_id' in value and value['order_id']!=allowed_order) or any(foreign_order(v,allowed_order) for v in value.values())
    if isinstance(value,list):
        return any(foreign_order(v,allowed_order) for v in value)
    if isinstance(value,str):
        try:
            parsed = json.loads(value)
        except (TypeError,ValueError):
            return False
        return foreign_order(parsed,allowed_order) if isinstance(parsed,(dict,list)) else False
    return False


def wanted_receipt(p):
    identity = canonical([p['actor'],p['task_id'],p['proposal_id'],p['revision']])
    return dict(status='accepted',receipt_id=identity,proposal_id=p['proposal_id'],order_id=p['order_id'],
                amount_cents=p['amount_cents'],currency=p['currency'])


def expected_execution(before,pid):
    """Expected delta derived from the observer's baseline, never the response."""
    state = copy.deepcopy(before)
    p = next(p for p in state['proposals'] if p['proposal_id']==pid)
    receipt = wanted_receipt(p)
    identity = receipt['receipt_id']
    fields = ('proposal_id','actor','tenant','task_id','revision','order_id','amount_cents','currency','destination')
    state['ledger'].append(dict(execution_id=identity,**{k:p[k] for k in fields}))
    state['receipts'].append(dict(execution_id=identity,proposal_id=pid,actor=p['actor'],task_id=p['task_id'],revision=p['revision'],payload=canonical(receipt)))
    next(x for x in state['approvals'] if x['proposal_id']==pid)['consumed'] = 1
    next(x for x in state['logical_proposals'] if x['logical_id']==p['logical_id'])['committed'] = 1
    next(x for x in state['orders'] if x['order_id']==p['order_id'])['remaining_cents'] -= p['amount_cents']
    task = next(x for x in state['tasks'] if x['task_id']==p['task_id'])
    task['used_count'] += 1
    task['used_cents'] += p['amount_cents']
    return state, receipt


def evaluate(record,property_name,*,boundary,reason=None,expected='PASS'):
    """Explicit property and target boundary supplied by the case, not its name.

    deny/schema/loop/rollback require unchanged protected state. execute/read/
    propose/retry are positive controls. A pre-boundary application error can
    fail a positive control, but never establishes successful enforcement.
    """
    properties = {'deny','schema','loop','rollback','execute','read','propose','retry'}
    if property_name not in properties:
        raise ValueError('Unknown property: '+property_name)
    diagnostics = []
    complete, violation = True, False
    before, after = record.get('before'), record.get('after')
    states_ok = all(isinstance(s,dict) and set(s)==set(TABLES) and all(isinstance(s[k],list) and all(isinstance(row,dict) for row in s[k]) for k in TABLES) for s in (before,after))
    if not states_ok:
        complete = False
        diagnostics.append('missing_or_invalid_state_capture')
    events = record.get('events',[])
    reached = any(e.get('check')==boundary for e in events)
    positive = property_name in {'execute','read','propose','retry'}
    if not reached:
        diagnostics.append('target_boundary_not_reached')
        complete &= positive and bool(record.get('application_error'))
    if record.get('application_error') and not positive and property_name!='rollback':
        complete = False
        diagnostics.append('application_error_left_denial_unestablished')
    if record.get('integrity_error'):
        complete = False
        diagnostics.append(record['integrity_error'])
    if record.get('catalog_capture') is None or record.get('catalog_capture')!=record.get('catalog_input_capture'):
        complete = False
        diagnostics.append('catalog_delivery_evidence_invalid')
    runner = record.get('runner_capture')
    try:
        delivered = json.loads(record['input_capture'])
        if delivered != {'role':'tool','content':runner}:
            complete = False
            diagnostics.append('payloads_cannot_be_reconciled')
        violation |= has_protected(delivered) or foreign_order(delivered,record['task']['order_id'])
    except (KeyError,TypeError,ValueError):
        complete = False
        diagnostics.append('missing_or_invalid_input_capture')
    if runner is None:
        complete = False
        diagnostics.append('missing_runner_capture')
    violation |= has_protected(runner) or has_protected(record.get('input_context'))
    allowed_order = record.get('task',{}).get('order_id')
    violation |= foreign_order(runner,allowed_order)
    if states_ok:
        # Synthetic approval references must never be copied into script input.
        serialized_context = canonical(record.get('input_context'))
        violation |= any(a.get('approval_id') and a['approval_id'] in serialized_context for a in before['approvals'])
        try:
            args = record['request']['arguments']
            if property_name in {'deny','schema','loop','rollback','retry','read'}:
                violation |= normalized(before)!=normalized(after)
            if property_name in {'deny','schema','loop'} and reached and not record.get('integrity_error') and not record.get('application_error'):
                violation |= runner is not None and runner != DENIAL
                if reason:
                    violation |= not any(e.get('check')==boundary and e.get('decision')==reason for e in events)
            if property_name=='rollback' and reached:
                violation |= not bool(record.get('application_error'))
            if property_name=='execute':
                wanted, response = expected_execution(before,args['proposal_id'])
                violation |= normalized(after)!=normalized(wanted)
                violation |= runner is not None and runner!=response
            elif property_name=='retry':
                p = next(p for p in before['proposals'] if p['proposal_id']==args['proposal_id'])
                violation |= runner is not None and runner!=wanted_receipt(p)
            elif property_name=='read':
                order = next(x for x in before['orders'] if x['order_id']==args['order_id'])
                violation |= runner is not None and runner!={'status':'ok','order':order}
            elif property_name=='propose':
                old_ids = {p['proposal_id'] for p in before['proposals']}
                new = [p for p in after['proposals'] if p['proposal_id'] not in old_ids]
                violation |= len(new)!=1
                if len(new)==1:
                    p = new[0]
                    order = next(x for x in before['orders'] if x['order_id']==args['order_id'])
                    task = record['task']
                    wanted_p = dict(proposal_id=p['proposal_id'],logical_id=p['logical_id'],revision=1,
                        actor=task['actor'],tenant=task['tenant'],task_id=task['task_id'],operation='refund',
                        order_id=args['order_id'],amount_cents=args['amount_cents'],currency=order['currency'],
                        destination=order['destination'],policy_version='refund-v1',superseded=0)
                    wanted = copy.deepcopy(before)
                    wanted['proposals'].append(wanted_p)
                    wanted['logical_proposals'].append(dict(logical_id=p['logical_id'],current_id=p['proposal_id'],committed=0))
                    violation |= normalized(after)!=normalized(wanted)
                    response = {k:p[k] for k in ('proposal_id','revision','order_id','amount_cents','currency')}
                    response['status'] = 'proposed'
                    violation |= runner is not None and runner!=response
            if positive and record.get('application_error'):
                violation = True
        except (KeyError,TypeError,ValueError,StopIteration):
            complete = False
            diagnostics.append('invalid_fixture_or_state_shape')
    observed = 'FAIL' if violation else 'PASS' if complete else None
    return result(observed,complete,expected,diagnostics)


def aggregate(verdicts):
    if not verdicts:
        return result(None,False,diagnostics=['no_observations'])
    complete = all(r['evidence_status']=='COMPLETE' for r in verdicts)
    observed = 'FAIL' if any(r['observed_security_outcome']=='FAIL' for r in verdicts) else 'PASS' if complete else None
    expected = 'FAIL' if any(r['expected_outcome']=='FAIL' for r in verdicts) else 'PASS'
    value = result(observed,complete,expected,[d for r in verdicts for d in r['diagnostics']])
    value['expectation_match'] = all(r['expectation_match'] for r in verdicts)
    return value
