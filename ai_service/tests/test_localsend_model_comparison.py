"""LS-only bounded experiment. All transports are synthetic/offline."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from test_status_model_comparison import load, ROOT, HARNESS


class LocalSendComparisonTests(unittest.TestCase):
    def setUp(self):
        path = ROOT/'work/harness/localsend-model-comparison/evaluate.py'
        self.assertTrue(path.exists(), 'LS-only runner is missing')
        self.m = load(path, 'ls_comparison_test')
        old = self.m.base.experiment
        self.prior = old.build_model_pair(old.status.prepare_package(
            old.status.previous.prepare_package(old.status.previous.SPEC)))
        self.package = self.m.localsend_package(self.prior)

    def approval(self):
        now = datetime.now(timezone.utc)
        return self.m.approval(now)

    def gate(self, tmp, transport):
        return self.m.LocalSendGate(tmp, self.package['jobs'], check_identity=lambda: None,
                                    check_free=lambda: 5400, transport=transport)

    def test_only_ls_payloads_identical_to_saved_original_and_order_fixed(self):
        self.assertEqual(set(self.package['documents']), {'LS'})
        self.assertEqual(self.package['documents']['LS'], self.prior['documents']['LS'])
        self.assertEqual(self.package['jobs'], [j for j in self.prior['jobs'] if j['docId']=='LS'])
        self.assertEqual([(j['arm'],j['batch']) for j in self.package['jobs']],
                         [('D',1),('G',1),('G',2),('D',2)])

    def test_four_calls_max_and_no_fr_can_enter_gate(self):
        sent = []
        with tempfile.TemporaryDirectory() as tmp:
            gate = self.gate(tmp, lambda p,k,t: sent.append(p) or b'{}')
            for job in self.package['jobs']:
                gate(job['payload'], 'synthetic', 600)
            with self.assertRaises(ValueError):
                gate(self.package['jobs'][0]['payload'], 'synthetic', 600)
            self.assertEqual(gate.started, 4)
            self.assertEqual(len(sent), 4)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            self.m.LocalSendGate(tmp, self.prior['jobs'], check_identity=lambda: None,
                                check_free=lambda: 5400, transport=lambda *a: self.fail('network'))

    def test_first_failure_preserves_diagnostic_and_prevents_every_next_call(self):
        def failed(*args):
            error = self.m.base.experiment.AnalysisError('INVALID_RESPONSE')
            error.response_diagnostic = {'http_status':200,'content_type':'text/event-stream',
                                         'error_location':'sse.json','sse_event':None}
            raise error
        with tempfile.TemporaryDirectory() as tmp:
            gate = self.gate(tmp, failed)
            with self.assertRaises(self.m.base.experiment.AnalysisError):
                gate(self.package['jobs'][0]['payload'], 'synthetic', 600)
            with self.assertRaises(ValueError):
                gate(self.package['jobs'][1]['payload'], 'synthetic', 600)
            self.assertEqual(gate.started, 1)
            self.assertEqual(json.loads((Path(tmp)/'01-finished.json').read_bytes())
                             ['response_diagnostic']['error_location'], 'sse.json')

    def test_approval_is_new_four_call_only_and_rejects_expiry_paid_or_model_drift(self):
        valid = self.approval()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'approval.json'
            p.write_text(json.dumps(valid), encoding='utf-8')
            self.assertGreater(self.m.check_approval(p), 0)
            for changes in ({'max_calls':8}, {'no_paid_fallback':False}, {'retries':1},
                {'models':['wrong']}, {'endpoint':'https://wrong.example'},
                {'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}):
                with self.subTest(changes=changes):
                    p.write_text(json.dumps(dict(valid, **changes)), encoding='utf-8')
                    with self.assertRaises(ValueError): self.m.check_approval(p)

    def test_report_uses_four_total_and_marks_failed_batches_unassessable(self):
        def failed(*args): raise self.m.base.experiment.AnalysisError('INVALID_RESPONSE')
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)
            gate=self.gate(output/'calls',failed)
            report=self.m.base.run_package(output,self.package,gate,
                self.m.base.experiment.FixedPayloadSender('synthetic',gate))
            self.assertEqual(report['calls_started'],1)
            self.assertEqual(report['unstarted_calls'],3)
            self.assertFalse(report['comparable'])
            self.assertEqual(set(report['documents']),{'LS'})
            for arm in ('D','G'):
                self.assertIsNone(report['documents']['LS'][arm]['comparison_metrics'])
                self.assertTrue(report['documents']['LS'][arm]['diagnostics']['special_cases']['LS15']['unassessable'])


if __name__ == '__main__': unittest.main()
