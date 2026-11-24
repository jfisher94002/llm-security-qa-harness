"""Small, offline examples for the Course 5 automation lesson.

Each test starts from a fresh database. Negative tests check three things
separately: the caller's response, the application's decision record and the
saved state. Positive tests check that permitted work still succeeds.
"""
import tempfile
import unittest
from pathlib import Path

from course05.lab2 import Lab, initialize, snapshot, trusted_task
from course05.lab2_verify import Scenario


class RefundBoundaryTests(unittest.TestCase):
    def setUp(self, task=None):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        initialize(self.root)
        self.lab = Lab(self.root, task=task)
        self.scenario = Scenario(self.lab)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.lab.close)

    def assertNoErrors(self, result):
        # A broken fixture or crash is an ERROR, not a security pass.
        self.assertIsNone(result['application_error'])
        self.assertIsNone(result['integrity_error'])

    def test_missing_approval_has_no_refund(self):
        proposal = self.scenario.propose()
        before = snapshot(self.root)
        result = self.lab.run('execute_refund', {'proposal_id': proposal})
        self.assertNoErrors(result)
        self.assertEqual(result['runner_capture']['status'], 'denied')                       # caller response
        self.assertIn({'check': 'approval', 'decision': 'APPROVAL_MISSING'}, result['events'])  # decision record
        self.assertEqual(snapshot(self.root)['ledger'], before['ledger'])                     # saved state

    def test_catalog_follows_task_operations(self):
        # Offered functionality: a propose-only task must not be offered execution.
        self.lab.close()
        self.setUp(task=trusted_task(operations=('get_order', 'propose_refund')))
        names = {tool['name'] for tool in self.lab.catalog()}
        self.assertEqual(names, {'get_order', 'propose_refund'})

    def test_cannot_read_another_tenants_order(self):
        # The task names O-200, so only the tenant check can refuse this read.
        self.lab.close()
        self.setUp(task=trusted_task(order_id='O-200'))
        result = self.lab.run('get_order', {'order_id': 'O-200'})
        self.assertNoErrors(result)
        self.assertEqual(result['runner_capture']['status'], 'denied')
        self.assertIn({'check': 'access', 'decision': 'ACCESS_DENIED'}, result['events'])
        self.assertNotIn('payment-B-200', result['input_capture'])

    def test_matching_approval_records_one_refund(self):
        proposal = self.scenario.propose()
        self.scenario.approve(proposal)
        before = snapshot(self.root)
        result = self.lab.run('execute_refund', {'proposal_id': proposal})
        after = snapshot(self.root)
        self.assertNoErrors(result)
        self.assertEqual(result['runner_capture']['status'], 'accepted')
        self.assertEqual(result['runner_capture']['proposal_id'], proposal)
        self.assertIn({'check': 'approval', 'decision': 'allowed'}, result['events'])
        self.assertEqual(len(after['ledger']) - len(before['ledger']), 1)
        self.assertEqual(after['ledger'][0]['proposal_id'], proposal)
        self.assertEqual(after['ledger'][0]['amount_cents'], 4000)

    def test_old_approval_does_not_authorize_a_revision(self):
        old = self.scenario.propose()
        self.scenario.approve(old)
        new = self.scenario.revise(old, 5000)
        before = snapshot(self.root)
        result = self.lab.run('execute_refund', {'proposal_id': new})
        self.assertNoErrors(result)
        self.assertEqual(result['runner_capture']['status'], 'denied')
        self.assertIn({'check': 'approval', 'decision': 'APPROVAL_MISSING'}, result['events'])
        self.assertEqual(snapshot(self.root)['ledger'], before['ledger'])

    def test_exact_retry_does_not_create_a_second_refund(self):
        proposal = self.scenario.propose()
        self.scenario.approve(proposal)
        first = self.lab.run('execute_refund', {'proposal_id': proposal})
        self.assertNoErrors(first)
        before_retry = snapshot(self.root)
        second = self.lab.run('execute_refund', {'proposal_id': proposal})
        after_retry = snapshot(self.root)
        self.assertNoErrors(second)
        self.assertEqual(first['runner_capture']['status'], 'accepted')
        self.assertEqual(second['runner_capture'], first['runner_capture'])
        self.assertIn({'check': 'receipt', 'decision': 'historical_receipt'}, second['events'])
        self.assertEqual(len(before_retry['ledger']), 1)
        self.assertEqual(after_retry['ledger'], before_retry['ledger'])
        self.assertEqual(after_retry['receipts'], before_retry['receipts'])


if __name__ == '__main__':
    unittest.main()
