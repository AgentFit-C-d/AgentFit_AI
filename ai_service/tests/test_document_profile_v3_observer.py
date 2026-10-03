"""Evaluation observer contract selection; all model/provider calls are replayed."""
import json
from contextlib import contextmanager
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from diagnostic_tools.document_profile_worker import observe_request, execute_observed_request
from agentfit_ai import analysis_worker
from review_preservation_fixture import load, offline, replay_providers


@contextmanager
def observed_replay(*, historical_classification=False):
    # Recreate the SDK interval objects from the saved observation serialization.
    def extract(*args, **kwargs):
        output = []
        for row in load('trace.json')['stages']['general_extracted']:
            interval = row.get('char_interval')
            output.append(SimpleNamespace(**{**row, 'char_interval': None if interval is None else
                SimpleNamespace(start_pos=interval['start'], end_pos=interval['end'])}))
        return output
    with replay_providers(historical_classification=historical_classification), patch(
            'agentfit_ai.langextract_solar_trial.extract_candidates', side_effect=extract):
        yield


class DocumentProfileV3ObserverTests(unittest.TestCase):
    def request(self, contract=None):
        value = dict(document=load('document.txt'), documentId='PUBLIC-01',
                     key='OFFLINE-NONCREDENTIAL', mode='integrated-nvidia')
        if contract is not None:
            value['contract'] = contract
        return json.dumps(value, ensure_ascii=False).encode()

    def test_v3_worker_response_and_dispositions_are_recorded_without_loss(self):
        with TemporaryDirectory() as folder, observed_replay():
            target = Path(folder).resolve()/'trace.json'
            raw = execute_observed_request(self.request('confirmation-v3'), target)
            result = json.loads(raw)
            self.assertEqual(result.get('contract'), 'confirmation-v3')
            self.assertEqual(len(result['reviewDispositions']), 6)
            trace = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(trace['stages']['final_response'], result)
            self.assertEqual(trace['observationErrors'], [])
            self.assertEqual(trace['status'], 'complete')
            # Current replay begins after classification; historical A's 22
            # requests are separately checked in the sealed historical runtime.
            self.assertEqual(len(trace['calls']), 3)
            self.assertEqual([c['request'] for c in trace['calls']],
                             [c['request'] for c in load('trace.json')['calls'][-3:]])

    def test_default_and_explicit_v2_preserve_frozen_result(self):
        for contract in (None, 'confirmation-v2'):
            with self.subTest(contract=contract), observed_replay():
                raw, trace = observe_request(self.request(contract))
                self.assertEqual(json.loads(raw), load('result.json'))
                self.assertEqual(trace['observationErrors'], [])
                self.assertEqual(trace['status'], 'complete')

    def test_unsupported_contract_types_rejected_before_worker(self):
        for contract in ('confirmation-v4', '', None, 3, True, [], {}):
            value = json.loads(self.request())
            value['contract'] = contract
            with self.subTest(contract=contract), offline(), patch.object(
                    analysis_worker, 'execute_request', side_effect=AssertionError('WORKER_MUST_NOT_RUN')):
                with self.assertRaisesRegex(ValueError, 'INVALID_EVALUATION_REQUEST'):
                    observe_request(json.dumps(value).encode())


if __name__ == '__main__':
    unittest.main()
