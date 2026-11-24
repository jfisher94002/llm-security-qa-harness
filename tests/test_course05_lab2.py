import copy
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from course05.lab2 import Lab, Task, initialize, snapshot, trusted_task, canonical, BINDING, Rejected, NOW, main
from course05.lab2_oracles import evaluate, exit_code
from course05.lab2_verify import Scenario, verify, run_case, CASES


class Lab2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        initialize(self.root)
        self.lab = Lab(self.root)
        self.s = Scenario(self.lab)

    def tearDown(self):
        self.s.lab.close()
        self.temp.cleanup()

    def proposal(self,approved=True):
        p = self.s.propose()
        a = self.s.approve(p) if approved else None
        return p,a

    def test_architecture_matrix(self):
        report = verify()
        bad = [r['name'] for r in report['cases'] if not r['verification_match']]
        self.assertEqual(bad,[])
        self.assertGreaterEqual(report['checks_passed'],59)

    def test_catalog_exact_and_no_supervisor_tool(self):
        expected = []
        for name,fields in [('get_order',{'order_id':{'type':'string','minLength':1}}),
                            ('propose_refund',{'order_id':{'type':'string','minLength':1},'amount_cents':{'type':'integer','minimum':1,'maximum':9223372036854775807}}),
                            ('execute_refund',{'proposal_id':{'type':'string','minLength':1}})]:
            expected.append({'name':name,'parameters':{'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}})
        self.assertEqual(self.lab.catalog(),expected)

    def test_all_binding_fields_checked_independently(self):
        p,a = self.proposal()
        baseline = snapshot(self.root)['approvals'][0]
        original = json.loads(baseline['binding'])
        for field in BINDING:
            with self.subTest(field=field):
                changed = dict(original)
                changed[field] = changed[field]+1 if type(changed[field]) is int else 'different'
                self.s.set_approval(a,binding=canonical(changed))
                r = self.lab.run('execute_refund',{'proposal_id':p})
                v = evaluate(r,'deny',boundary='approval',reason='APPROVAL_BINDING_MISMATCH')
                self.assertEqual(v['display_label'],'PASS')
        self.s.set_approval(a,binding=canonical(original))
        # Reset only runner iteration count for this table-driven unit probe.
        self.lab.call_count = 0
        r = self.lab.run('execute_refund',{'proposal_id':p})
        self.assertEqual(evaluate(r,'execute',boundary='commit')['display_label'],'PASS')

    def test_approver_checked_and_non_supervisor_cannot_mint(self):
        p = self.s.propose()
        for identity,role in [('Alex','supervisor'),('Sam','agent')]:
            with self.assertRaises(PermissionError):
                self.lab.approve(p,supervisor=identity,role=role)
        self.assertEqual(snapshot(self.root)['approvals'],[])
        a = self.s.approve(p)
        self.s.set_approval(a,approver='Alex')
        r = self.lab.run('execute_refund',{'proposal_id':p})
        self.assertEqual(evaluate(r,'deny',boundary='approval',reason='APPROVAL_BINDING_MISMATCH')['display_label'],'PASS')
        with self.assertRaises(PermissionError):
            self.lab.revoke(a,supervisor='Alex')

    def test_real_direct_handler_rejects_extra_fields(self):
        p,a = self.proposal()
        before = snapshot(self.root)
        for field in ('actor','tenant','task_id','approval','approval_ref','recipient','idempotency_key'):
            with self.subTest(field=field),self.assertRaises(Rejected):
                self.lab.handle('execute_refund',{'proposal_id':p,field:'anything'})
        self.assertEqual(snapshot(self.root),before)

    def test_integer_cents_and_schema_types(self):
        for value in (True,False,0,-1,1.1,'4000',None,[],{},2**80):
            with self.subTest(value=value):
                r = self.lab.run('propose_refund',{'order_id':'O-100','amount_cents':value})
                if value==2**80:
                    # Oversized integers must be schema rejections too, not DB failures.
                    self.assertEqual(r['runner_capture']['status'],'denied')
                else:
                    self.assertEqual(evaluate(r,'schema',boundary='schema',reason='SCHEMA_INVALID')['display_label'],'PASS')

    def test_denials_are_identical_and_hide_existence(self):
        p,a = self.proposal(False)
        missing = self.lab.run('execute_refund',{'proposal_id':'absent'})
        unapproved = self.lab.run('execute_refund',{'proposal_id':p})
        self.lab.task = replace(self.lab.task,actor='Blair')
        inaccessible = self.lab.run('execute_refund',{'proposal_id':p})
        self.assertEqual(missing['input_capture'],unapproved['input_capture'])
        self.assertEqual(missing['input_capture'],inaccessible['input_capture'])

    def test_application_error_positive_fails_denial_errors(self):
        p,a = self.proposal()
        with patch.object(self.lab,'handle',side_effect=RuntimeError('before policy')):
            r = self.lab.run('execute_refund',{'proposal_id':p})
        self.assertEqual(evaluate(r,'deny',boundary='approval')['display_label'],'ERROR')
        v = evaluate(r,'execute',boundary='commit')
        self.assertEqual(v['observed_security_outcome'],'FAIL')
        self.assertEqual(v['display_label'],'UNEXPECTED_FAIL')

    def test_always_deny_fails_positive_control(self):
        p,a = self.proposal()
        def deny(*args):
            self.lab.event('commit','wrong_denial')
            return {'status':'denied','code':'access_denied','message':'Request denied'}
        with patch.object(self.lab,'handle',side_effect=deny):
            r = self.lab.run('execute_refund',{'proposal_id':p})
        self.assertEqual(evaluate(r,'execute',boundary='commit')['observed_security_outcome'],'FAIL')

    def test_missing_capture_preserves_effect_failure(self):
        p,a = self.proposal()
        r = self.lab.run('execute_refund',{'proposal_id':p})
        r.pop('input_capture')
        v = evaluate(r,'deny',boundary='approval')
        self.assertEqual(v['display_label'],'ERROR')
        self.assertEqual(v['observed_security_outcome'],'FAIL')
        self.assertEqual(exit_code([v]),3)

    def test_adapter_capture_records_actual_delivery_and_protected_leak(self):
        original = self.lab.adapter
        def leaking(response):
            value = original(response)
            value['approvals'] = [{'approver':'Sam'}]
            return value
        self.lab.adapter = leaking
        r = self.lab.run('get_order',{'order_id':'O-100'})
        self.assertEqual(json.loads(r['input_capture']),self.lab.input_context[-1])
        v = evaluate(r,'read',boundary='access')
        self.assertEqual(v['display_label'],'ERROR')
        self.assertEqual(v['observed_security_outcome'],'FAIL')

    def test_adapter_added_foreign_order_remains_fail_under_error(self):
        original = self.lab.adapter
        def leaking(response):
            value = original(response)
            value['other_order'] = {'order_id':'O-200','destination':'payment-B-200'}
            return value
        self.lab.adapter = leaking
        r = self.lab.run('get_order',{'order_id':'O-100'})
        v = evaluate(r,'read',boundary='access')
        self.assertEqual(v['display_label'],'ERROR')
        self.assertEqual(v['observed_security_outcome'],'FAIL')

    def test_all_model_inputs_exclude_approval_records(self):
        p,a = self.proposal()
        r = self.lab.run('execute_refund',{'proposal_id':p})
        serialized = canonical(r['input_context'])
        self.assertNotIn(a,serialized)
        self.assertNotIn('Sam',serialized)
        self.assertNotIn('expires_at',serialized)
        self.assertNotIn('binding',serialized)

    def test_immutable_payload_enforced_in_store(self):
        p,a = self.proposal()
        with self.assertRaises(sqlite3.IntegrityError):
            self.lab.db.execute('UPDATE proposals SET amount_cents=5000 WHERE proposal_id=?',(p,))

    def test_resume_and_authority_replacement(self):
        p,a = self.proposal()
        self.lab.run('execute_refund',{'proposal_id':p})
        before = snapshot(self.root)
        other = Lab(self.root)
        try:
            self.assertEqual(snapshot(self.root),before)
            r = other.run('execute_refund',{'proposal_id':p})
            self.assertEqual(evaluate(r,'retry',boundary='receipt')['display_label'],'PASS')
        finally:
            other.close()
        with self.assertRaises(ValueError):
            Lab(self.root,trusted_task('R1',max_count=100))
        self.assertEqual(snapshot(self.root),before)
        with self.assertRaises(FileExistsError):
            initialize(self.root)

    def test_new_task_requires_launcher_and_old_reference_not_authorized(self):
        p,a = self.proposal()
        other = Lab(self.root,trusted_task('fresh',max_count=2,max_cents=8000))
        try:
            r = other.run('execute_refund',{'proposal_id':p})
            self.assertEqual(evaluate(r,'deny',boundary='access',reason='ACCESS_DENIED')['display_label'],'PASS')
        finally:
            other.close()

    def test_receipt_integrity_variants_never_reexecute(self):
        p,a = self.proposal()
        self.lab.run('execute_refund',{'proposal_id':p})
        for sql in ("UPDATE receipts SET payload='not json'", "UPDATE receipts SET actor='Blair'",
                    "DELETE FROM ledger", "DELETE FROM receipts", "UPDATE approvals SET consumed=0",
                    "UPDATE tasks SET used_count=0", "UPDATE orders SET remaining_cents=10000 WHERE order_id='O-100'"):
            with self.subTest(sql=sql):
                # Restore committed fixture between independent corruption probes.
                backup = sqlite3.connect(':memory:')
                self.lab.db.backup(backup)
                self.lab.db.execute(sql)
                before = snapshot(self.root)
                r = self.lab.run('execute_refund',{'proposal_id':p})
                self.assertEqual(r['before'],r['after'])
                self.assertEqual(evaluate(r,'deny',boundary='access')['display_label'],'ERROR')
                backup.backup(self.lab.db)
                backup.close()

    def test_wrong_saved_effect_detected_even_if_response_correct(self):
        p,a = self.proposal()
        r = self.lab.run('execute_refund',{'proposal_id':p})
        for table,key,value in [('ledger','destination','outside'),('ledger','amount_cents',1),
                                ('tasks','used_count',0),('tasks','used_cents',0),
                                ('orders','remaining_cents',10000),('approvals','consumed',0),
                                ('logical_proposals','committed',0),('receipts','payload','{}')]:
            with self.subTest(table=table,key=key):
                bad = copy.deepcopy(r)
                index = next(i for i,x in enumerate(bad['after'][table]) if table!='orders' or x['order_id']=='O-100')
                bad['after'][table][index][key] = value
                self.assertEqual(evaluate(bad,'execute',boundary='commit')['observed_security_outcome'],'FAIL')

    def test_cli_result_labels_and_exit_codes(self):
        for name,code,label in [('approved',0,'PASS'),('v1',1,'EXPECTED_FAIL'),('v2',1,'EXPECTED_FAIL'),
                                ('v3',1,'EXPECTED_FAIL'),('v4-count',1,'EXPECTED_FAIL'),
                                ('v4-amount',1,'EXPECTED_FAIL'),('missing-capture',3,'ERROR')]:
            with self.subTest(case=name):
                with patch('builtins.print'):
                    self.assertEqual(main(['run','--case',name,'--output-dir',str(self.root/'out')]),code)
                report = json.loads((self.root/'out'/f'{name}.json').read_text())
                self.assertEqual(report['result']['display_label'],label)

    def test_denial_application_crash_after_access_is_error(self):
        p,a = self.proposal()
        with patch.object(self.lab,'execute',side_effect=RuntimeError('after access')):
            r = self.lab.run('execute_refund',{'proposal_id':p})
        v = evaluate(r,'deny',boundary='access')
        self.assertEqual(v['display_label'],'ERROR')
        self.assertIsNone(v['observed_security_outcome'])

    def test_adapter_failure_is_evidence_error(self):
        with patch.object(self.lab,'adapter',side_effect=RuntimeError('capture failed')):
            r = self.lab.run('get_order',{'order_id':'O-100'})
        self.assertEqual(evaluate(r,'read',boundary='access')['display_label'],'ERROR')

    def test_corrupt_state_capture_is_error(self):
        r = self.lab.run('get_order',{'order_id':'O-100'})
        r['after']['approvals'] = [None]
        self.assertEqual(evaluate(r,'read',boundary='access')['display_label'],'ERROR')

    def test_unknown_property_rejected(self):
        with self.assertRaises(ValueError):
            evaluate({},'typo',boundary='approval')

    def test_precedence_revision_current_and_terminal(self):
        p,a = self.proposal()
        self.lab.db.execute("UPDATE logical_proposals SET current_id='other',committed=1")
        r = self.lab.run('execute_refund',{'proposal_id':p})
        self.assertEqual(evaluate(r,'deny',boundary='revision',reason='REVISION_NOT_CURRENT')['display_label'],'PASS')
        self.lab.db.execute('UPDATE logical_proposals SET current_id=?',(p,))
        r = self.lab.run('execute_refund',{'proposal_id':p})
        self.assertEqual(evaluate(r,'deny',boundary='terminal',reason='LOGICAL_PROPOSAL_COMMITTED')['display_label'],'PASS')

    def test_architecture_binding_fields_are_pinned(self):
        self.assertEqual(BINDING,('actor','tenant','task_id','proposal_id','revision','operation',
                                 'order_id','amount_cents','currency','destination','policy_version'))

    def denied_record(self):
        p,a = self.proposal(False)
        return self.lab.run('execute_refund',{'proposal_id':p})

    def sync_capture(self,r,response):
        r['runner_capture'] = response
        r['input_capture'] = canonical({'role':'tool','content':response})
        r['input_context'] = [json.loads(r['input_capture'])]

    def test_oracle_denial_cannot_hide_saved_effect(self):
        r = self.denied_record()
        r['after']['ledger'].append({'execution_id':'unauthorized'})
        self.assertEqual(evaluate(r,'deny',boundary='approval')['observed_security_outcome'],'FAIL')

    def test_oracle_earlier_denial_is_not_target_evidence(self):
        r = self.denied_record()
        r['events'] = [{'check':'access','decision':'ACCESS_DENIED'}]
        self.assertEqual(evaluate(r,'deny',boundary='approval')['display_label'],'ERROR')

    def test_oracle_reason_code_is_required(self):
        r = self.denied_record()
        self.assertEqual(evaluate(r,'deny',boundary='approval',reason='APPROVAL_REVOKED')['observed_security_outcome'],'FAIL')

    def test_oracle_denial_shape_is_required(self):
        r = self.denied_record()
        self.sync_capture(r,{'status':'denied','message':'different shape'})
        self.assertEqual(evaluate(r,'deny',boundary='approval')['observed_security_outcome'],'FAIL')

    def test_oracle_opaque_approval_id_leak(self):
        p,a = self.proposal()
        r = self.lab.run('execute_refund',{'proposal_id':p})
        r['input_context'].append({'role':'tool','content':'opaque reference '+a})
        self.assertEqual(evaluate(r,'execute',boundary='commit')['observed_security_outcome'],'FAIL')

    def test_oracle_retry_requires_original_receipt(self):
        p,a = self.proposal()
        self.lab.run('execute_refund',{'proposal_id':p})
        r = self.lab.run('execute_refund',{'proposal_id':p})
        self.sync_capture(r,{'status':'denied','code':'access_denied','message':'Request denied'})
        self.assertEqual(evaluate(r,'retry',boundary='receipt')['observed_security_outcome'],'FAIL')

    def test_ineffective_mutations_preserve_unexpected_pass(self):
        original = Lab.execute
        def neutralized(lab,p,args):
            mutations = lab.mutations
            lab.mutations = frozenset()
            try:
                return original(lab,p,args)
            finally:
                lab.mutations = mutations
        for case in ('v1','v4-count','v4-amount'):
            with self.subTest(case=case),patch.object(Lab,'execute',neutralized),patch('builtins.print'):
                self.assertEqual(main(['run','--case',case,'--output-dir',str(self.root/'out')]),3)
                report = json.loads((self.root/'out'/f'{case}.json').read_text())
                self.assertEqual(report['result']['display_label'],'ERROR')
                self.assertEqual(report['result']['observed_security_outcome'],'PASS')
                self.assertEqual(report['security_result']['display_label'],'UNEXPECTED_PASS')
                self.assertFalse(report['verification_match'])
                self.assertTrue(report['failed_fixture_assertions'])

    def test_corrected_revision_violations_are_security_failures(self):
        import inspect
        import textwrap
        import course05.lab2 as application
        mutations = (
            ('retired-unapproved','approve',
             "if p['superseded'] or logical['current_id']!=pid or logical['committed']:",
             'if False:'),
            ('supersession','revise',"if logical['committed']:",'if False:'),
        )
        for case,method,old,new in mutations:
            source = textwrap.dedent(inspect.getsource(getattr(Lab,method)))
            self.assertIn(old,source)
            namespace = dict(vars(application))
            exec(compile(source.replace(old,new),'<regression mutation>','exec'),namespace)
            with self.subTest(case=case),patch.object(Lab,method,namespace[method]),patch('builtins.print'):
                self.assertEqual(main(['run','--case',case,'--output-dir',str(self.root/'out')]),1)
                report = json.loads((self.root/'out'/f'{case}.json').read_text())
                self.assertEqual(report['result']['display_label'],'UNEXPECTED_FAIL')
                self.assertEqual(report['result']['observed_security_outcome'],'FAIL')
                self.assertEqual(report['result']['evidence_status'],'COMPLETE')
                self.assertEqual(report['security_result'],report['result'])
                self.assertEqual(report['fixture_status'],'VALID')
                self.assertEqual(report['failed_fixture_assertions'],[])
                self.assertTrue(report['failed_security_assertions'])
                self.assertFalse(report['verification_match'])

    def test_fixture_error_preserves_scenario_security_failure(self):
        exercise,task,mutations = CASES['approved']
        def mixed(s):
            exercise(s)
            s.check('invariant violated',False,kind='security')
            s.check('precondition missing',False,kind='fixture')
        with patch.dict(CASES,{'approved':(mixed,task,mutations)}):
            report = run_case('approved')
        self.assertEqual(report['result']['display_label'],'ERROR')
        self.assertEqual(report['result']['observed_security_outcome'],'FAIL')
        self.assertEqual(report['security_result']['display_label'],'UNEXPECTED_FAIL')
        self.assertEqual(exit_code([report['result']]),3)
        self.assertFalse(report['verification_match'])

    def test_run_and_verify_harness_crashes_exit_three(self):
        import course05.lab2_verify as scenarios
        def crash(s):
            raise TypeError('broken fixture')
        with patch.dict(scenarios.CASES,{'approved':(crash,None,())}),patch('builtins.print'):
            for command in ('run','verify'):
                self.assertEqual(main([command,'--case','approved','--output-dir',str(self.root/'out')]),3)
        with patch.object(scenarios,'run_case',side_effect=TypeError('outside case')),patch('builtins.print'):
            self.assertEqual(main(['run','--output-dir',str(self.root/'out')]),3)
            self.assertTrue((self.root/'out/harness-error.json').exists())

    def test_catalog_is_minimized_and_both_entry_points_enforce(self):
        self.lab.close()
        self.lab = Lab(self.root,trusted_task('read-only',operations=('get_order',)))
        self.s.lab = self.lab
        self.assertEqual([x['name'] for x in self.lab.catalog()],['get_order'])
        r = self.lab.run('propose_refund',{'order_id':'O-100','amount_cents':1000})
        self.assertEqual(evaluate(r,'deny',boundary='dispatcher',reason='CATALOG_DENIED')['display_label'],'PASS')
        self.assertFalse(r['handler_reached'])
        r = self.lab.run('propose_refund',{'order_id':'O-100','amount_cents':1000},path='direct')
        self.assertEqual(evaluate(r,'deny',boundary='access',reason='ACCESS_DENIED')['display_label'],'PASS')

    def test_corrected_positive_error_is_unexpected_failure(self):
        report = run_case('positive-error')
        self.assertEqual(report['result']['display_label'],'UNEXPECTED_FAIL')
        self.assertTrue(report['verification_match'])

if __name__=='__main__':
    unittest.main()
