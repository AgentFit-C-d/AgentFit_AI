"""Operation extraction preserves source positions before semantic judgment."""
from copy import deepcopy
import json
import unittest

from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.solar import AnalysisError
from tests.test_candidate_split_review import response


class OperationCandidateTests(unittest.TestCase):
    def test_exact_repeated_unicode_quotes_keep_distinct_anchors_without_semantic_filter(self):
        from agentfit_ai.operation_candidates import extract_operation_candidates
        document = '🚀 주문 조회를 제공한다. 주문 조회는 검토 중이다.'
        def transport(payload, key, timeout):
            self.assertEqual(payload['model'], MODEL)
            self.assertEqual(key, 'nvidia-secret')
            self.assertEqual(json.loads(payload['messages'][1]['content'])['document'], document)
            return response({'mentions': [{'quote': '주문 조회', 'anchor': '주문 조회를 제공한다.'},
                                           {'quote': '주문 조회', 'anchor': '주문 조회는 검토 중이다.'}]}, model=MODEL)
        frozen = extract_operation_candidates(document, 'nvidia-secret', transport=transport)
        self.assertEqual([item['start'] for item in frozen['candidates']], [2, document.rindex('주문 조회')])
        self.assertEqual(frozen['rejected'], [])
        self.assertNotIn('quote', str(frozen))

    def test_absent_ambiguous_and_duplicate_spans_remain_rejected(self):
        from agentfit_ai.operation_candidates import extract_operation_candidates
        document = '조회 조회. 예약 취소.'
        mentions = [{'quote': '조회', 'anchor': '조회'}, {'quote': '없는 기능', 'anchor': '없는 기능'},
                    {'quote': '예약 취소', 'anchor': '예약 취소.'}, {'quote': '예약 취소', 'anchor': '예약 취소.'}]
        frozen = extract_operation_candidates(document, 'secret',
            transport=lambda *a: response({'mentions': mentions}, model=MODEL))
        self.assertEqual(frozen['candidates'], [])
        self.assertEqual(len(frozen['rejected']), 4)

    def test_invalid_shapes_limits_and_provider_responses_fail(self):
        from agentfit_ai.operation_candidates import extract_operation_candidates
        for mentions in (None, [{'quote': 'X', 'anchor': 'X', 'status': 'confirmed'}],
                         [{'quote': 'X' * 201, 'anchor': 'X' * 201}],
                         [{'quote': 'X', 'anchor': 'X' * 1001}],
                         [{'quote': 'X', 'anchor': 'X'}] * 61):
            with self.subTest(mentions=str(mentions)[:30]), self.assertRaises(ValueError):
                extract_operation_candidates('X', 'secret', transport=lambda *a: response({'mentions': mentions}, model=MODEL))
        for kwargs in ({'model': 'wrong'}, {'model': MODEL, 'finish': 'length'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(AnalysisError):
                extract_operation_candidates('X', 'secret', transport=lambda *a: response({'mentions': []}, **kwargs))

    def test_bad_model_or_secret_in_source_prevents_transport(self):
        from agentfit_ai.operation_candidates import extract_operation_candidates
        for document, key, model in (('contains secret', 'secret', MODEL), ('X', '', MODEL), ('X', 'key', 'bad')):
            with self.assertRaises(ValueError):
                extract_operation_candidates(document, key, model=model,
                    transport=lambda *a: self.fail('invalid input reached provider'))

    def test_classification_is_separate_batched_and_uses_full_semantics(self):
        from agentfit_ai.operation_candidates import classify_operation_candidates
        from agentfit_ai.candidate_field_semantics import field_semantics_instructions
        document = ' '.join(f'기능{i}' for i in range(31))
        candidates = []
        for i in range(31):
            start = document.index(f'기능{i} ' if i < 30 else f'기능{i}')
            candidates.append({'id': f'C{i:03}', 'start': start, 'end': start + len(f'기능{i}')})
        sizes = []
        def transport(payload, key, timeout):
            self.assertIn(field_semantics_instructions('explicit-v1'), payload['messages'][0]['content'])
            batch = json.loads(payload['messages'][1]['content'])['candidates']
            sizes.append(len(batch))
            return response({'labels': [{'id': item['id'], 'field': 'features',
                'status': 'tentative' if item['id'] == 'C030' else 'confirmed'} for item in reversed(batch)]}, model=MODEL)
        labels = classify_operation_candidates(document, {'candidates': candidates, 'rejected': []},
                                                 'secret', transport=transport)
        self.assertEqual(sizes, [30, 1])
        self.assertEqual(next(row for row in labels if row['id'] == 'C030')['status'], 'tentative')

    def test_merge_deduplicates_positions_rekeys_and_keeps_rejections(self):
        from agentfit_ai.operation_candidates import merge_candidate_sets
        document = '조회 취소'
        left = ({'candidates': [{'id': 'C000', 'start': 3, 'end': 5}],
                 'rejected': [{'index': 0, 'reason': 'snapshot_rejected'}]},
                [{'id': 'C000', 'field': 'features', 'status': 'confirmed'}])
        right = ({'candidates': [{'id': 'C000', 'start': 0, 'end': 2}, {'id': 'C001', 'start': 3, 'end': 5}],
                  'rejected': []}, [{'id': 'C000', 'field': 'features', 'status': 'negated'},
                                   {'id': 'C001', 'field': 'features', 'status': 'confirmed'}])
        original = deepcopy((left, right))
        frozen, labels = merge_candidate_sets(document, left, right)
        self.assertEqual(frozen['candidates'], [{'id': 'C000', 'start': 0, 'end': 2}, {'id': 'C001', 'start': 3, 'end': 5}])
        self.assertEqual(labels[0]['status'], 'negated')
        self.assertEqual(len(frozen['rejected']), 1)
        self.assertEqual((left, right), original)
        right[1][1]['status'] = 'tentative'
        with self.assertRaises(ValueError):
            merge_candidate_sets(document, left, right)

    def test_merge_rejects_bad_bounds_and_overall_candidate_limit(self):
        from agentfit_ai.operation_candidates import merge_candidate_sets
        document = 'x' * 241
        frozen = {'candidates': [{'id': f'C{i:03}', 'start': i, 'end': i+1} for i in range(241)], 'rejected': []}
        labels = [{'id': row['id'], 'field': 'features', 'status': 'confirmed'} for row in frozen['candidates']]
        with self.assertRaises(ValueError):
            merge_candidate_sets(document, (frozen, labels))
        frozen['candidates'] = [{'id': 'C000', 'start': True, 'end': 2}]
        with self.assertRaises(ValueError):
            merge_candidate_sets(document, (frozen, labels[:1]))

    def test_merge_preserves_individually_addressable_rejections(self):
        from agentfit_ai.operation_candidates import merge_candidate_sets
        left = ({'candidates': [], 'rejected': [{'index': 0, 'reason': 'ambiguous_anchor'},
                                               {'index': 1, 'reason': 'duplicate_span'}]}, [])
        right = ({'candidates': [], 'rejected': [{'index': 0, 'reason': 'invalid_candidate'}]}, [])
        frozen, _ = merge_candidate_sets('문서', left, right)
        self.assertEqual(frozen['rejected'], [{'index': 0, 'reason': 'ambiguous_anchor'},
                                            {'index': 1, 'reason': 'duplicate_span'},
                                            {'index': 2, 'reason': 'invalid_candidate'}])

    def test_other_normalization_cannot_hide_invalid_provider_status(self):
        from agentfit_ai.operation_candidates import classify_operation_candidates
        frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 2}], 'rejected': []}
        invalid = [{'id': 'C000', 'field': 'other'},
                   *[{'id': 'C000', 'field': 'other', 'status': status}
                     for status in ('unsupported', None, [], True)]]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError):
                classify_operation_candidates('조회', frozen, 'secret',
                    transport=lambda *a: response({'labels': [row]}, model=MODEL))
        result = classify_operation_candidates('조회', frozen, 'secret', transport=lambda *a:
            response({'labels': [{'id': 'C000', 'field': 'other', 'status': 'tentative'}]}, model=MODEL))
        self.assertEqual(result, [{'id': 'C000', 'field': 'other', 'status': 'irrelevant'}])
