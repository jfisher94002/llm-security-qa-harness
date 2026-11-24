"""Offline refund lab. Protected fixture APIs are not model tools."""
from contextlib import contextmanager, closing
from dataclasses import asdict, dataclass
from pathlib import Path
import argparse
import copy
import json
import sqlite3
import tempfile
import uuid

POLICY = 'refund-v1'
NOW = 1800000000
DENIAL = {'status':'denied','code':'access_denied','message':'Request denied'}
SPECS = {'get_order':{'order_id':str}, 'propose_refund':{'order_id':str,'amount_cents':int}, 'execute_refund':{'proposal_id':str}}
TABLES = ('orders','tasks','logical_proposals','proposals','approvals','ledger','receipts')
BINDING = ('actor','tenant','task_id','proposal_id','revision','operation','order_id','amount_cents','currency','destination','policy_version')

@dataclass(frozen=True)
class Task:
    task_id: str = 'R1'
    actor: str = 'Alex'
    tenant: str = 'A'
    order_id: str = 'O-100'
    max_count: int = 1
    max_cents: int = 4000
    operations: tuple = ('get_order','propose_refund','execute_refund')

def trusted_task(name='R1', **changes):
    """Launcher-only authority creation. Never called from model arguments."""
    values = {'task_id':name,'max_count':2 if name == 'R2' else 1}
    values.update(changes)
    return Task(**values)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'))

def initialize(root):
    root = Path(root)
    root.mkdir(parents=True,exist_ok=True)
    path = root / 'refund.sqlite'
    if path.exists():
        raise FileExistsError('Refusing to reset an existing lab')
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript('''
        CREATE TABLE orders(order_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, paid_cents INTEGER NOT NULL,
          remaining_cents INTEGER NOT NULL, currency TEXT NOT NULL, destination TEXT NOT NULL);
        CREATE TABLE tasks(task_id TEXT PRIMARY KEY, actor TEXT NOT NULL, tenant TEXT NOT NULL, order_id TEXT NOT NULL,
          max_count INTEGER NOT NULL, max_cents INTEGER NOT NULL, operations TEXT NOT NULL, used_count INTEGER NOT NULL, used_cents INTEGER NOT NULL);
        CREATE TABLE logical_proposals(logical_id TEXT PRIMARY KEY, current_id TEXT NOT NULL, committed INTEGER NOT NULL);
        CREATE TABLE proposals(proposal_id TEXT PRIMARY KEY, logical_id TEXT NOT NULL, revision INTEGER NOT NULL,
          actor TEXT NOT NULL, tenant TEXT NOT NULL, task_id TEXT NOT NULL, operation TEXT NOT NULL, order_id TEXT NOT NULL,
          amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, destination TEXT NOT NULL, policy_version TEXT NOT NULL,
          superseded INTEGER NOT NULL, UNIQUE(logical_id,revision));
        CREATE TRIGGER immutable_payload BEFORE UPDATE OF proposal_id,logical_id,revision,actor,tenant,task_id,
          operation,order_id,amount_cents,currency,destination,policy_version ON proposals
          BEGIN SELECT RAISE(ABORT, 'immutable proposal'); END;
        CREATE TABLE approvals(approval_id TEXT PRIMARY KEY, proposal_id TEXT UNIQUE NOT NULL, approver TEXT NOT NULL,
          binding TEXT NOT NULL, expires_at INTEGER NOT NULL, revoked INTEGER NOT NULL, usable INTEGER NOT NULL, consumed INTEGER NOT NULL);
        CREATE TABLE ledger(execution_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, actor TEXT NOT NULL, tenant TEXT NOT NULL,
          task_id TEXT NOT NULL, revision INTEGER NOT NULL, order_id TEXT NOT NULL, amount_cents INTEGER NOT NULL,
          currency TEXT NOT NULL, destination TEXT NOT NULL);
        CREATE TABLE receipts(execution_id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, actor TEXT NOT NULL,
          task_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL);
        INSERT INTO orders VALUES('O-100','A',10000,10000,'USD','payment-A-100');
        INSERT INTO orders VALUES('O-200','B',10000,10000,'USD','payment-B-200');
        ''')

def snapshot(root):
    """Independent observer, never the service's write connection."""
    with closing(sqlite3.connect((Path(root).resolve()/'refund.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory = sqlite3.Row
        return {t:[dict(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY 1')] for t in TABLES}

class Rejected(Exception):
    pass

class IntegrityFailure(Exception):
    pass

class Lab:
    def __init__(self,root,task=None,mutations=(),now=NOW):
        self.root = Path(root).resolve()
        self.task = task or trusted_task()
        self.mutations = frozenset(mutations)
        if not self.mutations <= {'V1','V2','V3','V4','ignore_revision_binding','disable_supersession'}:
            raise ValueError('Unknown mutation')
        self.now = now
        self.db = sqlite3.connect(self.root/'refund.sqlite',isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.events, self.calls, self.input_context = [], [], []
        self.call_count, self.fault, self.handler_reached = 0, None, False
        self.catalog_capture = copy.deepcopy(self.catalog())
        self.script_catalog = json.loads(canonical(self.catalog_capture))
        try:
            self._install_task()
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise

    def _install_task(self):
        t = self.task
        if type(t.max_count) is not int or type(t.max_cents) is not int or min(t.max_count,t.max_cents)<0:
            raise ValueError('Invalid launcher budget')
        config = (t.actor,t.tenant,t.order_id,t.max_count,t.max_cents,canonical(t.operations))
        with self.transaction():
            row = self.db.execute('SELECT * FROM tasks WHERE task_id=?',(t.task_id,)).fetchone()
            if row:
                if tuple(row[k] for k in ('actor','tenant','order_id','max_count','max_cents','operations')) != config:
                    raise ValueError('Existing task authority cannot be replaced')
            else:
                self.db.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?)',(t.task_id,*config,0,0))

    def event(self,check,decision='allowed'):
        self.events.append({'check':check,'decision':decision})

    def deny(self,check,reason):
        self.event(check,reason)
        raise Rejected(reason)

    def spec(self,tool):
        fields = dict(SPECS.get(tool,{}))
        if tool == 'execute_refund' and 'V1' in self.mutations:
            fields['approval'] = str
        if tool == 'execute_refund' and 'V2' in self.mutations:
            fields['approval_ref'] = str
        return fields

    def catalog(self):
        return [{'name':tool,'parameters':{'type':'object','properties':{
            k:({'type':'integer','minimum':1,'maximum':9223372036854775807} if v is int else {'type':'string','minLength':1})
            for k,v in self.spec(tool).items()},'required':list(self.spec(tool)),'additionalProperties':False}}
            for tool in SPECS if tool in self.task.operations]

    def validate(self,tool,args):
        spec = self.spec(tool)
        valid = (tool in SPECS and isinstance(args,dict) and set(args)==set(spec) and
                 all(type(args[k]) is v and (0<args[k]<=9223372036854775807 if v is int else bool(args[k].strip())) for k,v in spec.items()))
        self.event('schema','allowed' if valid else 'SCHEMA_INVALID')
        if not valid:
            raise Rejected('SCHEMA_INVALID')

    def _order(self,order_id,operation):
        t = self.task
        row = self.db.execute('SELECT * FROM orders WHERE order_id=?',(order_id,)).fetchone()
        if operation not in t.operations or not row or row['tenant']!=t.tenant or order_id!=t.order_id:
            self.deny('access','ACCESS_DENIED')
        self.event('access')
        return dict(row)

    def _proposal(self,pid,operation='execute_refund'):
        p = self.db.execute('SELECT * FROM proposals WHERE proposal_id=?',(pid,)).fetchone()
        t = self.task
        if (not p or operation not in t.operations or
            (p['actor'],p['tenant'],p['task_id'],p['order_id'])!=(t.actor,t.tenant,t.task_id,t.order_id)):
            self.deny('access','ACCESS_DENIED')
        self.event('access')
        return dict(p)

    def _new_proposal(self,order,cents,logical_id=None,revision=1):
        pid, lid = 'P-'+uuid.uuid4().hex, logical_id or 'L-'+uuid.uuid4().hex
        p = dict(proposal_id=pid,logical_id=lid,revision=revision,actor=self.task.actor,tenant=self.task.tenant,
                 task_id=self.task.task_id,operation='refund',order_id=order['order_id'],amount_cents=cents,
                 currency=order['currency'],destination=order['destination'],policy_version=POLICY,superseded=0)
        self.db.execute('INSERT INTO proposals VALUES('+','.join('?' for _ in p)+')',tuple(p.values()))
        if logical_id:
            self.db.execute('UPDATE logical_proposals SET current_id=? WHERE logical_id=?',(pid,lid))
        else:
            self.db.execute('INSERT INTO logical_proposals VALUES(?,?,0)',(lid,pid))
        return p

    def revise(self,pid,cents):
        """Trusted fixture revision action, outside the model catalog."""
        if type(cents) is not int or not 0<cents<=9223372036854775807:
            raise ValueError('Positive integer cents required')
        with self.transaction():
            p = self._proposal(pid,'propose_refund')
            logical = self.db.execute('SELECT * FROM logical_proposals WHERE logical_id=?',(p['logical_id'],)).fetchone()
            if logical['committed']:
                self.deny('terminal','LOGICAL_PROPOSAL_COMMITTED')
            if logical['current_id']!=pid:
                self.deny('revision','REVISION_NOT_CURRENT')
            self.db.execute('UPDATE proposals SET superseded=1 WHERE logical_id=?',(p['logical_id'],))
            self.db.execute('UPDATE approvals SET usable=0 WHERE proposal_id IN (SELECT proposal_id FROM proposals WHERE logical_id=?)',(p['logical_id'],))
            return self._new_proposal(self._order(p['order_id'],'propose_refund'),cents,p['logical_id'],p['revision']+1)['proposal_id']

    def approve(self,pid,*,supervisor='Sam',role='supervisor',expires_at=None):
        """Protected fixture action simulating authentication, not a login system."""
        if supervisor!='Sam' or role!='supervisor':
            raise PermissionError('Supervisor required')
        with self.transaction():
            p = self._proposal(pid)
            logical = self.db.execute('SELECT * FROM logical_proposals WHERE logical_id=?',(p['logical_id'],)).fetchone()
            if p['superseded'] or logical['current_id']!=pid or logical['committed']:
                raise PermissionError('Proposal is not approvable')
            aid = 'A-'+uuid.uuid4().hex
            self.db.execute('INSERT INTO approvals VALUES(?,?,?,?,?,0,1,0)',
                (aid,pid,supervisor,canonical({k:p[k] for k in BINDING}),self.now+3600 if expires_at is None else expires_at))
            return aid

    def revoke(self,aid,*,supervisor='Sam',role='supervisor'):
        if supervisor!='Sam' or role!='supervisor':
            raise PermissionError('Supervisor required')
        with self.transaction():
            self.db.execute('UPDATE approvals SET revoked=1 WHERE approval_id=?',(aid,))

    def _fault(self,point):
        if self.fault==point:
            raise RuntimeError('Injected application exception: '+point)

    @staticmethod
    def receipt_payload(p,identity):
        return {'status':'accepted','receipt_id':identity,'proposal_id':p['proposal_id'],
                'order_id':p['order_id'],'amount_cents':p['amount_cents'],'currency':p['currency']}

    def execute(self,p,args):
        # BEGIN IMMEDIATE spans receipt lookup, authorization, and every write.
        identity = canonical([p['actor'],p['task_id'],p['proposal_id'],p['revision']])
        receipt = self.db.execute('SELECT * FROM receipts WHERE execution_id=?',(identity,)).fetchone()
        if receipt and 'V3' not in self.mutations:
            ledger = self.db.execute('SELECT * FROM ledger WHERE execution_id=?',(identity,)).fetchone()
            logical = self.db.execute('SELECT * FROM logical_proposals WHERE logical_id=?',(p['logical_id'],)).fetchone()
            fields = ('proposal_id','actor','tenant','task_id','revision','order_id','amount_cents','currency','destination')
            try:
                payload = json.loads(receipt['payload'])
            except (ValueError, TypeError) as exc:
                raise IntegrityFailure('invalid_receipt_payload') from exc
            if (not ledger or any(ledger[k]!=p[k] for k in fields) or not logical['committed'] or
                payload!=self.receipt_payload(p,identity) or
                any(receipt[k]!=p[k] for k in ('proposal_id','actor','task_id','revision'))):
                raise IntegrityFailure('receipt_state_inconsistent')
            approval = self.db.execute('SELECT * FROM approvals WHERE proposal_id=?',(p['proposal_id'],)).fetchone()
            task = self.db.execute('SELECT * FROM tasks WHERE task_id=?',(p['task_id'],)).fetchone()
            order = self.db.execute('SELECT * FROM orders WHERE order_id=?',(p['order_id'],)).fetchone()
            totals = self.db.execute('SELECT COUNT(*),COALESCE(SUM(amount_cents),0) FROM ledger WHERE task_id=?',(p['task_id'],)).fetchone()
            refunded = self.db.execute('SELECT COALESCE(SUM(amount_cents),0) FROM ledger WHERE order_id=?',(p['order_id'],)).fetchone()[0]
            if (not approval or not approval['consumed'] or not task or not order or
                (task['used_count'],task['used_cents'])!=tuple(totals) or
                order['remaining_cents']!=order['paid_cents']-refunded):
                raise IntegrityFailure('receipt_accounting_inconsistent')
            self.event('receipt','historical_receipt')
            return payload
        if not receipt and self.db.execute('SELECT 1 FROM ledger WHERE execution_id=?',(identity,)).fetchone():
            raise IntegrityFailure('ledger_without_receipt')
        self.event('receipt','none' if not receipt else 'V3_replay_bypass')
        logical = self.db.execute('SELECT * FROM logical_proposals WHERE logical_id=?',(p['logical_id'],)).fetchone()
        if 'disable_supersession' not in self.mutations:
            if p['superseded']:
                self.deny('revision','REVISION_SUPERSEDED')
            if logical['current_id']!=p['proposal_id']:
                self.deny('revision','REVISION_NOT_CURRENT')
        self.event('revision')
        if logical['committed'] and 'V3' not in self.mutations:
            self.deny('terminal','LOGICAL_PROPOSAL_COMMITTED')
        self.event('terminal')
        a = self.db.execute('SELECT * FROM approvals WHERE proposal_id=?',(p['proposal_id'],)).fetchone()
        if 'V2' in self.mutations:
            a = self.db.execute('SELECT * FROM approvals WHERE approval_id=?',(args['approval_ref'],)).fetchone()
        if 'ignore_revision_binding' in self.mutations and not a:
            a = self.db.execute('SELECT a.* FROM approvals a JOIN proposals p ON p.proposal_id=a.proposal_id WHERE p.logical_id=? ORDER BY p.revision LIMIT 1',(p['logical_id'],)).fetchone()
        claimed = 'V1' in self.mutations and args.get('approval')=='approved'
        if not a and not claimed:
            self.deny('approval','APPROVAL_MISSING')
        if a:
            try:
                binding = json.loads(a['binding'])
            except (ValueError, TypeError) as exc:
                raise IntegrityFailure('invalid_approval_binding') from exc
            if ('V2' not in self.mutations and 'ignore_revision_binding' not in self.mutations and
                (binding!={k:p[k] for k in BINDING} or a['approver']!='Sam')):
                self.deny('approval','APPROVAL_BINDING_MISMATCH')
            if not a['usable'] and not ({'ignore_revision_binding','disable_supersession'} & self.mutations):
                self.deny('approval','APPROVAL_UNUSABLE')
            if a['consumed'] and 'V3' not in self.mutations:
                self.deny('approval','APPROVAL_CONSUMED')
            if self.now>=a['expires_at']:
                self.deny('approval','APPROVAL_EXPIRED')
            if a['revoked']:
                self.deny('approval','APPROVAL_REVOKED')
        self.event('approval','V1_claim_accepted' if claimed else 'allowed')
        task = self.db.execute('SELECT * FROM tasks WHERE task_id=?',(p['task_id'],)).fetchone()
        order = self.db.execute('SELECT * FROM orders WHERE order_id=?',(p['order_id'],)).fetchone()
        if 'V4' not in self.mutations:
            if task['used_count']+1>task['max_count']:
                self.deny('budget','TASK_COUNT_EXCEEDED')
            if task['used_cents']+p['amount_cents']>task['max_cents']:
                self.deny('budget','TASK_AMOUNT_EXCEEDED')
        self.event('budget')
        if p['amount_cents']>order['remaining_cents']:
            self.deny('balance','ORDER_BALANCE_EXCEEDED')
        self.event('balance')
        if 'V3' in self.mutations and receipt:
            identity += ':duplicate:'+uuid.uuid4().hex
        fields = ('proposal_id','actor','tenant','task_id','revision','order_id','amount_cents','currency','destination')
        self.db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?,?,?)',(identity,*(p[k] for k in fields)))
        self._fault('after_ledger')
        if a:
            self.db.execute('UPDATE approvals SET consumed=1 WHERE approval_id=?',(a['approval_id'],))
        self.db.execute('UPDATE logical_proposals SET committed=1 WHERE logical_id=?',(p['logical_id'],))
        self.db.execute('UPDATE orders SET remaining_cents=remaining_cents-? WHERE order_id=?',(p['amount_cents'],p['order_id']))
        self.db.execute('UPDATE tasks SET used_count=used_count+1,used_cents=used_cents+? WHERE task_id=?',(p['amount_cents'],p['task_id']))
        payload = self.receipt_payload(p,identity)
        self.db.execute('INSERT INTO receipts VALUES(?,?,?,?,?,?)',(identity,p['proposal_id'],p['actor'],p['task_id'],p['revision'],canonical(payload)))
        self._fault('before_commit')
        self.event('commit','prepared')
        return payload

    def handle(self,tool,args):
        self.validate(tool,args)  # direct entry enforces the same schema
        self.handler_reached = True
        with self.transaction():
            if tool=='get_order':
                return {'status':'ok','order':self._order(args['order_id'],tool)}
            if tool=='propose_refund':
                p = self._new_proposal(self._order(args['order_id'],tool),args['amount_cents'])
                self.event('proposal','created')
                return {'status':'proposed','proposal_id':p['proposal_id'],'revision':p['revision'],
                        'order_id':p['order_id'],'amount_cents':p['amount_cents'],'currency':p['currency']}
            return self.execute(self._proposal(args['proposal_id']),args)

    def adapter(self,response):
        return {'role':'tool','content':copy.deepcopy(response)}

    def deliver(self,serialized):
        self.input_context.append(json.loads(serialized))

    def run(self,tool,args,*,path='dispatcher'):
        if path not in ('dispatcher','direct'):
            raise ValueError('Unknown entry point')
        self.events, self.handler_reached = [], False
        record = {'mode':'scripted','profile':'vulnerable' if self.mutations else 'corrected',
                  'mutations':sorted(self.mutations),'task':asdict(self.task),'catalog_capture':copy.deepcopy(self.catalog_capture),
                  'catalog_input_capture':copy.deepcopy(self.script_catalog),
                  'request':{'tool':tool,'arguments':copy.deepcopy(args)},'path':path,
                  'before':snapshot(self.root),'application_error':None,'integrity_error':None}
        self.call_count += 1
        try:
            if self.call_count>12:
                self.deny('loop','LOOP_LIMIT')
            if path=='dispatcher':
                self.validate(tool,args)
                if tool not in self.task.operations:
                    self.deny('dispatcher','CATALOG_DENIED')
                self.event('dispatcher','forwarded')
            response = self.handle(tool,args)
        except Rejected:
            response = dict(DENIAL)
        except IntegrityFailure as exc:
            record['integrity_error'] = str(exc)
            response = {'status':'error','code':'evidence_integrity_error'}
        except Exception as exc:
            record['application_error'] = type(exc).__name__+': '+str(exc)
            response = {'status':'error','code':'application_error'}
        record['runner_capture'] = copy.deepcopy(response)
        try:
            serialized = canonical(self.adapter(response))
            record['input_capture'] = serialized  # after adapter, immediately before script receives it
            self.deliver(serialized)
        except Exception as exc:
            record['input_capture'] = None
            record['integrity_error'] = 'delivery_capture_error: '+type(exc).__name__
        record['input_context'] = copy.deepcopy(self.input_context)
        record['events'] = copy.deepcopy(self.events)
        record['handler_reached'] = self.handler_reached
        try:
            record['after'] = snapshot(self.root)
        except Exception as exc:
            record['after'] = None
            record['integrity_error'] = 'state_capture_error: '+type(exc).__name__
        self.calls.append(record)
        return record

def _main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('verify','run'))
    parser.add_argument('--case',default='approved')
    parser.add_argument('--output-dir',type=Path,default=Path('tmp_results/course05-lab2'))
    parser.add_argument('--json-summary',action='store_true',help='Print the original machine-readable run summary')
    args = parser.parse_args(argv)
    from .lab2_verify import verify, run_case, CASES
    from .lab2_oracles import exit_code
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.command=='verify':
        report = verify()
        name = 'verification'
        code = (3 if any(not c['verification_match'] and c['result']['evidence_status']=='ERROR' for c in report['cases'])
                else 0 if report['fixture_verification']=='PASS' else 1)
        print('CASE | EXPECTED | OBSERVED | DISPLAY')
        for c in report['cases']:
            r = c['result']
            print(f"{c['name']} | {r['expected_outcome']} | {r['observed_security_outcome']} | {r['display_label']}")
        print(f"Fixture verification: {report['fixture_verification']} ({len(report['cases'])} cases)")
    else:
        if args.case not in CASES:
            parser.error('Unknown case. Choose: '+', '.join(CASES))
        report = run_case(args.case)
        name, code = args.case, exit_code([report['result']])
    target = args.output_dir/(name+'.json')
    target.write_text(json.dumps(report,indent=2)+'\n')
    if args.command=='run':
        if args.case in ('missing','approved','supersession') and not args.json_summary:
            from .lab2_demo_summary import show_summary
            if not show_summary(target):
                code = code or 3
        else:
            print(canonical({**report['result'],'verification_match':report['verification_match'],
                             'failed_fixture_assertions':report['failed_fixture_assertions'],
                             'security_display_label':report['security_result']['display_label']}))
    print('Evidence: '+str(target))
    return code

def main(argv=None):
    try:
        return _main(argv)
    except Exception as exc:
        from .lab2_oracles import result
        report = {'result':result(None,False,diagnostics=['harness_error: '+type(exc).__name__+': '+str(exc)]),
                  'verification_match':False,'fixture_status':'ERROR'}
        print(canonical(report['result']))
        # Best-effort error artifact even when failure preceded normal run output.
        import sys
        tokens = list(sys.argv[1:] if argv is None else argv)
        try:
            out = Path(tokens[tokens.index('--output-dir')+1]) if '--output-dir' in tokens else Path('tmp_results/course05-lab2')
            out.mkdir(parents=True,exist_ok=True)
            (out/'harness-error.json').write_text(json.dumps(report,indent=2)+'\n')
        except Exception:
            pass
        return 3

if __name__=='__main__':
    raise SystemExit(main())
