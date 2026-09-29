"""Reuse validated source references without rerunning extraction or leaking values."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest

from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.profile import FIELDS
from agentfit_ai.real_document_holdout import PreparedCase
from agentfit_ai.solar import AnalysisError


class CandidateReviewReplayTests(unittest.TestCase):
    def setUp(self):
        self.text = 'Orbit 웹 대시보드. 사용자는 주문 조회를 한다.'
        self.case = PreparedCase('synthetic', self.text,
            [{'id': 'C01', 'field': 'project_type', 'contains_any': ['웹 대시보드']}],
            'a' * 64, hashlib.sha256(self.text.encode()).hexdigest(), None, 0, 0)
        self.snapshot = {'state': 'finished', 'case_id': self.case.id,
            'source_sha256': self.case.source_sha256, 'redacted_sha256': self.case.redacted_sha256,
            'candidate_count': 1, 'rejected_candidate_count': 2,
            'classification_refs': [{'id': 'C000', 'start': 0, 'end': 12,
                                      'field': 'project_type', 'status': 'confirmed'}]}

    def test_restore_verifies_positions_and_keeps_rejection_count_without_invented_reason(self):
        from agentfit_ai.candidate_review_replay import restore_snapshot
        original = deepcopy(self.snapshot)
        frozen, labels = restore_snapshot(self.case, self.snapshot)
        self.assertEqual(len(frozen['rejected']), 2)
        self.assertTrue(all(row['reason'] == 'snapshot_rejected' for row in frozen['rejected']))
        self.assertEqual(labels, [{'id': 'C000', 'field': 'project_type', 'status': 'confirmed'}])
        frozen['candidates'].clear()
        self.assertEqual(self.snapshot, original)

    def test_bad_snapshot_and_stale_source_are_rejected(self):
        from agentfit_ai.candidate_review_replay import restore_snapshot
        for key, value in (('state', 'running'), ('case_id', 'wrong'), ('source_sha256', 'b' * 64),
                           ('redacted_sha256', 'b' * 64), ('candidate_count', 2),
                           ('candidate_count', True), ('rejected_candidate_count', -1),
                           ('rejected_candidate_count', True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                restore_snapshot(self.case, {**self.snapshot, key: value})
        for key, value in (('id', 'PRIVATE ID'), ('start', True), ('start', -1),
                           ('end', 1000), ('field', 'unknown'), ('status', 'unknown')):
            bad = deepcopy(self.snapshot)
            bad['classification_refs'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                restore_snapshot(self.case, bad)
        with self.assertRaises(ValueError):
            restore_snapshot(replace(self.case, text=self.text + ' changed'), self.snapshot)

    def test_duplicate_id_and_source_span_are_rejected(self):
        from agentfit_ai.candidate_review_replay import restore_snapshot
        for duplicate_id in (True, False):
            bad = deepcopy(self.snapshot)
            second = {**bad['classification_refs'][0], 'id': 'C000' if duplicate_id else 'C001'}
            bad['classification_refs'].append(second)
            bad['candidate_count'] = 2
            with self.assertRaises(ValueError):
                restore_snapshot(self.case, bad)

    def test_each_policy_gets_same_inputs_and_rejections_prevent_completion(self):
        from agentfit_ai.candidate_review_replay import evaluate_review_policies
        seen, updates = [], []
        def reviewer(document, frozen, labels, key, **kwargs):
            seen.append(deepcopy((document, frozen, labels)))
            self.assertEqual(key, 'nvidia-secret')
            self.assertEqual(kwargs['review_model'], MODEL)
            self.assertEqual(kwargs['field_semantics'], ('legacy', 'explicit-v1')[len(seen)-1])
            return {'checkedFields': list(FIELDS), 'missingFields': [],
                    'wrongCandidateIds': ['C000'] if len(seen) == 1 else []}
        result = evaluate_review_policies(self.case, self.snapshot, 'nvidia-secret', MODEL,
            reviewer=reviewer, on_update=lambda result: updates.append(deepcopy(result)))
        self.assertEqual(seen[0], seen[1])
        self.assertEqual([row['suggestion_matched'] for row in result['policies']], [0, 1])
        self.assertTrue(all(row['outcome'] == 'needs_confirmation' for row in result['policies']))
        self.assertEqual([row['state'] for row in updates], ['running', 'running', 'finished'])
        self.assertEqual(result['rejected_candidate_count'], 2)
        self.assertFalse(result['rejected_details_available'])
        for private in (self.text, 'Orbit', '웹 대시보드', 'nvidia-secret'):
            self.assertNotIn(private, json.dumps(result, ensure_ascii=False))

    def test_failure_and_mutation_do_not_hide_arm_or_poison_next_policy(self):
        from agentfit_ai.candidate_review_replay import evaluate_review_policies
        count = 0
        def reviewer(document, frozen, labels, key, **kwargs):
            nonlocal count
            count += 1
            self.assertEqual(len(frozen['candidates']), 1)
            if count == 1:
                frozen['candidates'].clear()
                labels.clear()
                raise AnalysisError('PROVIDER_TIMEOUT')
            return {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []}
        result = evaluate_review_policies(self.case, self.snapshot, 'nvidia-secret', MODEL, reviewer=reviewer)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(len(result['policies']), 2)
        self.assertEqual(result['policies'][0]['provider_error'], 'PROVIDER_TIMEOUT')
        self.assertEqual(result['state'], 'finished')

    def test_invalid_model_policy_or_key_never_reaches_provider(self):
        from agentfit_ai.candidate_review_replay import evaluate_review_policies
        def forbidden(*a, **k):
            self.fail('invalid input reached provider')
        for options in ({'model': 'bad'}, {'policies': ('legacy', 'legacy')},
                        {'policies': ('bad',)}, {'policies': ()}, {'key': ''}, {'key': 'Orbit'}):
            args = {'case': self.case, 'snapshot': self.snapshot, 'key': 'nvidia-secret',
                    'model': MODEL, 'reviewer': forbidden, **options}
            with self.subTest(options=options), self.assertRaises(ValueError):
                evaluate_review_policies(**args)
