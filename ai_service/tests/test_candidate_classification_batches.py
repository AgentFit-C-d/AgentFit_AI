"""Batch boundaries must preserve occurrence IDs and reject partial classifications."""
from copy import deepcopy
import json
import unittest

from agentfit_ai.candidate_first_profile import (CandidateContractError,
                                                classify_profile_candidates)
from agentfit_ai.solar import AnalysisError
from test_candidate_feature_curation import response


class ClassificationBatchTests(unittest.TestCase):
    def fixture(self, count):
        # Equal words at different offsets must keep independent IDs/statuses.
        return 'A ' * count, {'candidates': [
            {'id': f'C{i:03}', 'start': i * 2, 'end': i * 2 + 1}
            for i in range(count)], 'rejected': []}

    def test_default_and_selected_batches_preserve_every_occurrence_and_source(self):
        for count, options, sizes in ((31, {}, [30, 1]),
                (31, {'batch_size': 15}, [15, 15, 1]),
                (240, {'batch_size': 15}, [15] * 16),
                (240, {'batch_size': 30}, [30] * 8)):
            document, frozen = self.fixture(count)
            before, requests = deepcopy(frozen), []
            def transport(payload, key, timeout):
                self.assertEqual((key, timeout), ('test-key', 600))
                data = json.loads(payload['messages'][1]['content'])
                self.assertEqual(data['document'], document)
                requests.append(data['candidates'])
                return response({'labels': [{'id': row['id'], 'field': 'features',
                    'status': 'tentative' if row['start'] == 30 else 'confirmed'}
                    for row in reversed(data['candidates'])]}, model='solar-pro4')
            with self.subTest(count=count, options=options):
                labels = classify_profile_candidates(document, frozen, 'test-key',
                    transport=transport, **options)
                self.assertEqual([len(rows) for rows in requests], sizes)
                self.assertEqual([row['id'] for rows in requests for row in rows],
                                 [f'C{i:03}' for i in range(count)])
                self.assertEqual([(row['start'], row['end'], row['value'])
                    for rows in requests for row in rows],
                    [(i * 2, i * 2 + 1, 'A') for i in range(count)])
                self.assertEqual(len(labels), count)
                self.assertEqual({r['id']: r['status'] for r in labels}['C015'], 'tentative')
                self.assertEqual(frozen, before)

    def test_bad_batch_is_rejected_before_send_including_empty_candidates(self):
        calls = []
        for size in (0, 1, 14, 16, 31, True, False, 15.0, '15', None, []):
            for count in (0, 1):
                document, frozen = self.fixture(count)
                with self.subTest(size=size, count=count), self.assertRaises(ValueError):
                    classify_profile_candidates(document or 'A', frozen, 'test-key',
                        batch_size=size, transport=lambda *args: calls.append(True))
        self.assertEqual(calls, [])
        self.assertEqual(classify_profile_candidates('A', {'candidates': [], 'rejected': []},
                         'test-key', batch_size=15, transport=lambda *a: calls.append(True)), [])
        self.assertEqual(calls, [])

    def test_last_batch_missing_duplicate_or_foreign_id_never_returns_partial_labels(self):
        for defect in ('missing', 'duplicate', 'foreign'):
            document, frozen = self.fixture(17)
            calls = []
            def transport(payload, key, timeout):
                rows = json.loads(payload['messages'][1]['content'])['candidates']
                labels = [{'id': r['id'], 'field': 'features', 'status': 'confirmed'} for r in rows]
                calls.append(True)
                if len(calls) == 2:
                    if defect == 'missing': labels.pop()
                    elif defect == 'duplicate': labels[1]['id'] = labels[0]['id']
                    else: labels[1]['id'] = 'C000'
                return response({'labels': labels}, model='solar-pro4')
            with self.subTest(defect=defect), self.assertRaises(CandidateContractError):
                classify_profile_candidates(document, frozen, 'test-key',
                                            batch_size=15, transport=transport)
            self.assertEqual(len(calls), 2)

    def test_provider_failure_stops_later_batches_and_preserves_safe_error(self):
        document, frozen = self.fixture(31)
        calls = []
        def transport(payload, key, timeout):
            rows = json.loads(payload['messages'][1]['content'])['candidates']
            calls.append(True)
            if len(calls) == 2:
                raise AnalysisError('PROVIDER_RATE_LIMIT')
            return response({'labels': [{'id': r['id'], 'field': 'features',
                                        'status': 'confirmed'} for r in rows]}, model='solar-pro4')
        with self.assertRaises(AnalysisError) as caught:
            classify_profile_candidates(document, frozen, 'test-key',
                                        batch_size=15, transport=transport)
        self.assertEqual(caught.exception.code, 'PROVIDER_RATE_LIMIT')
        self.assertEqual(len(calls), 2)


if __name__ == '__main__':
    unittest.main()
