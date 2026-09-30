"""Recovery must recheck changed assignments without erasing unresolved work."""
import copy
import json
import unittest

from agentfit_ai.candidate_feature_regrouping import repair_feature_curation
from agentfit_ai.candidate_feature_curation import curate_reviewed_features
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from test_candidate_feature_curation import (
    fixture, partition, coverage, relation_response, response, sender)


def split_partition():
    return {'groups': [
        {'representativeId': 'C000', 'memberIds': ['C000', 'C001']},
        {'representativeId': 'C002', 'memberIds': ['C002', 'C003']}],
        'unrepresentedIds': []}


def split_review(*, first='covered', second='covered'):
    return {'assessments': [
        {'memberId': 'C001', 'representativeId': 'C000', 'coverage': first},
        {'memberId': 'C003', 'representativeId': 'C002', 'coverage': second}]}


class CandidateFeatureRegroupingTests(unittest.TestCase):
    def test_full_flow_repairs_once_and_keeps_final_uncertainty(self):
        data = fixture(31)
        proposed = {'groups': [partition(30)['groups'][0],
                               {'representativeId': 'C030', 'memberIds': ['C030']}],
                    'unrepresentedIds': []}
        for remaining in ([], ['C001']):
            final_review = relation_response(30)
            if remaining:
                final_review['assessments'][0]['coverage'] = 'uncertain'
            requests, traces = [], []
            result = curate_reviewed_features(*data, 'fake', transport=sender([
                response(partition()), response(relation_response(uncovered=['C030'])),
                response(proposed), response(final_review)], requests), call_trace=traces)
            self.assertEqual(len(requests), 4)
            self.assertEqual(result, {**proposed, **coverage(uncovered=remaining)})
            self.assertEqual([row['stage'] for row in traces], [
                'feature_grouping', 'feature_relations', 'feature_regrouping', 'feature_relations'])
            verdict = {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []}
            final = finalize_candidate_analysis(data[0], 'case', data[1], data[2], verdict,
                                                 feature_curation=result)
            self.assertEqual(final['outcome'], 'needs_confirmation' if remaining else 'candidate_profile')
            self.assertEqual(final['featureCuration']['uncoveredCount'], len(remaining))

    def test_initial_singleton_partition_can_recover_in_three_calls(self):
        data = fixture(31)
        first = {'groups': [{'representativeId': f'C{i:03d}', 'memberIds': [f'C{i:03d}']}
                            for i in range(30)], 'unrepresentedIds': ['C030']}
        requests, traces = [], []
        result = curate_reviewed_features(*data, 'fake', transport=sender([
            response(first), response(partition()), response(relation_response())], requests),
            call_trace=traces)
        self.assertEqual(len(requests), 3)
        self.assertEqual(result, {**partition(), **coverage()})
        self.assertEqual([row['stage'] for row in traces],
                         ['feature_grouping', 'feature_regrouping', 'feature_relations'])

    def test_full_flow_does_not_hide_repair_failure(self):
        data = fixture(31)
        for failure in (AnalysisError('PROVIDER_UNAVAILABLE'), response({'groups': []})):
            requests, traces = [], []
            with self.subTest(failure=type(failure)), self.assertRaises((AnalysisError, ValueError)):
                curate_reviewed_features(*data, 'fake', transport=sender([
                    response(partition()), response(relation_response(uncovered=['C030'])),
                    failure], requests), call_trace=traces)
            self.assertEqual(len(requests), 3)
            self.assertFalse(traces[-1]['validated'])

    def test_complete_receipt_returns_independent_copy_without_calls(self):
        data = fixture(4)
        prior = {**partition(4), **coverage(4)}
        original = copy.deepcopy(prior)
        requests, traces = [], []
        result = repair_feature_curation(*data, prior, 'fake',
            transport=sender([], requests), call_trace=traces)
        self.assertEqual(result, original)
        self.assertEqual(requests, [])
        self.assertEqual(traces, [])
        result['groups'][0]['memberIds'].pop()
        self.assertEqual(prior, original)

    def test_unchanged_assignments_ignore_order_and_preserve_missing_union(self):
        data = fixture(5)
        prior = {'groups': [
            {'representativeId': 'C000', 'memberIds': ['C000', 'C001']},
            {'representativeId': 'C002', 'memberIds': ['C002']}],
            'unrepresentedIds': ['C003', 'C004'], **coverage(5)}
        proposed = {'groups': [
            {'representativeId': 'C002', 'memberIds': ['C002']},
            {'representativeId': 'C000', 'memberIds': ['C001', 'C000']}],
            'unrepresentedIds': ['C004', 'C003']}
        original = copy.deepcopy(prior)
        requests = []
        result = repair_feature_curation(*data, prior, 'fake',
            transport=sender([response(proposed)], requests))
        self.assertEqual(len(requests), 1)
        self.assertEqual(result, {**original, 'uncoveredIds': ['C003', 'C004']})
        self.assertEqual(prior, original)

    def test_repair_reviews_all_new_pairs_and_preserves_inputs(self):
        data = fixture(4, extras=(('Go', 'backend', 'confirmed'),
                                 ('선택 기능', 'features', 'tentative')))
        prior = {**partition(4), **coverage(4, uncovered=['C003'])}
        original = copy.deepcopy((data, prior))
        requests, traces = [], []
        result = repair_feature_curation(*data, prior, 'PRIVATE_KEY',
            transport=sender([response(split_partition()), response(split_review())], requests),
            call_trace=traces)
        self.assertEqual(result, {**split_partition(), **coverage(4)})
        self.assertEqual(len(requests), 2)
        grouping = json.loads(requests[0]['messages'][1]['content'])
        self.assertEqual(requests[0]['response_format']['json_schema']['name'],
                         'agentfit_feature_regrouping')
        self.assertEqual(grouping['document'], data[0])
        self.assertEqual([row['id'] for row in grouping['candidates']],
                         ['C000', 'C001', 'C002', 'C003'])
        self.assertEqual(grouping['previousCuration'], {
            'groups': prior['groups'], 'unrepresentedIds': [], 'uncoveredIds': ['C003']})
        reviewed = json.loads(requests[1]['messages'][1]['content'])
        self.assertEqual(reviewed['relations'], [
            {'memberId': 'C001', 'representativeId': 'C000'},
            {'memberId': 'C003', 'representativeId': 'C002'}])
        for row in reviewed['candidates']:
            source = next(item for item in data[1]['candidates'] if item['id'] == row['id'])
            self.assertEqual(row['value'], data[0][source['start']:source['end']])
        self.assertEqual((data, prior), original)
        self.assertEqual([row['stage'] for row in traces], ['feature_regrouping', 'feature_relations'])
        self.assertTrue(all(row['validated'] for row in traces))
        self.assertNotIn('PRIVATE_KEY', json.dumps(traces))
        self.assertNotIn('기록 검색', json.dumps(traces, ensure_ascii=False))

    def test_recheck_can_reject_previously_covered_members_without_retry(self):
        data = fixture(4, extras=(('Go', 'backend', 'confirmed'),))
        prior = {**partition(4), **coverage(4, uncovered=['C003'])}
        requests = []
        repaired = repair_feature_curation(*data, prior, 'fake', transport=sender([
            response(split_partition()), response(split_review(first='uncertain'))], requests))
        self.assertEqual(len(requests), 2)
        self.assertEqual(repaired['uncoveredIds'], ['C001'])
        verdict = {'checkedFields': list(FIELDS), 'missingFields': ['domain'],
                   'wrongCandidateIds': []}
        baseline = finalize_candidate_analysis(*data[:1], 'case', *data[1:], verdict)
        final = finalize_candidate_analysis(*data[:1], 'case', *data[1:], verdict,
                                             feature_curation=repaired)
        self.assertEqual(final['outcome'], 'needs_confirmation')
        self.assertEqual(final['unresolvedFields'], ['domain', 'features'])
        self.assertEqual(final['featureCuration']['uncoveredCount'], 1)
        for kind in ('data', 'evidence'):
            for field in FIELDS:
                if field != 'features':
                    self.assertEqual(final['profile'][kind][field], baseline['profile'][kind][field])

    def test_repeated_value_occurrences_are_coalesced_then_reviewed(self):
        data = fixture(3, extras=(('기록 검색', 'features', 'confirmed'),))
        prior = {'groups': [{'representativeId': 'C001',
                             'memberIds': ['C000', 'C001', 'C002', 'C003']}],
                 'unrepresentedIds': [], **coverage(4, uncovered=['C003'])}
        proposed = {'groups': [partition(3)['groups'][0],
                               {'representativeId': 'C003', 'memberIds': ['C003']}],
                    'unrepresentedIds': []}
        judged = {'assessments': [
            {'memberId': 'C001', 'representativeId': 'C000', 'coverage': 'covered'},
            {'memberId': 'C002', 'representativeId': 'C000', 'coverage': 'covered'},
            {'memberId': 'C003', 'representativeId': 'C000', 'coverage': 'uncertain'}]}
        requests = []
        result = repair_feature_curation(*data, prior, 'fake',
            transport=sender([response(proposed), response(judged)], requests))
        self.assertEqual(len(requests), 2)
        self.assertEqual(result, {**partition(4), **coverage(4, uncovered=['C003'])})

    def test_changed_singletons_need_no_semantic_call(self):
        data = fixture(4)
        prior = {**partition(4), **coverage(4, uncovered=['C003'])}
        proposed = {'groups': [
            {'representativeId': 'C000', 'memberIds': ['C000']},
            {'representativeId': 'C001', 'memberIds': ['C001']},
            {'representativeId': 'C002', 'memberIds': ['C002']}],
            'unrepresentedIds': ['C003']}
        requests = []
        result = repair_feature_curation(*data, prior, 'fake',
            transport=sender([response(proposed)], requests))
        self.assertEqual(len(requests), 1)
        self.assertEqual(result, {**proposed, **coverage(4, uncovered=['C003'])})

    def test_invalid_inputs_do_not_call_provider(self):
        data = fixture(4)
        prior = {**partition(4), **coverage(4, uncovered=['C003'])}
        bad = copy.deepcopy(prior)
        bad['checkedCandidateIds'].pop()
        cases = [(data, bad, 'fake', {}), (data, prior, ' ', {}),
                 (data, prior, 'fake', {'model': 'unknown'}),
                 (data, prior, 'fake', {'call_trace': {}}),
                 ((data[0], data[1], data[2][:-1]), prior, 'fake', {}),
                 (('x' * 100001, data[1], data[2]), prior, 'fake', {})]
        for inputs, receipt, key, options in cases:
            requests = []
            with self.subTest(options=options), self.assertRaises(ValueError):
                repair_feature_curation(*inputs, receipt, key,
                    transport=sender([], requests), **options)
            self.assertEqual(requests, [])

    def test_invalid_repair_partitions_fail_before_review(self):
        data = fixture(4)
        prior = {**partition(4), **coverage(4, uncovered=['C003'])}
        bads = [None, {}, {'groups': [], 'unrepresentedIds': ['C000', 'C001', 'C002', 'C003']},
                partition(3), {**partition(4), 'unrepresentedIds': ['C003']},
                {**partition(4), 'extra': 'private'},
                {'groups': [{'representativeId': 'UNKNOWN',
                             'memberIds': ['C000', 'C001', 'C002', 'C003']}],
                 'unrepresentedIds': []}]
        cases = [(data, prior, bad) for bad in bads]
        large = fixture(31)
        too_many = {'groups': [{'representativeId': f'C{i:03d}', 'memberIds': [f'C{i:03d}']}
                               for i in range(31)], 'unrepresentedIds': []}
        cases.append((large, {**partition(31), **coverage(31, uncovered=['C030'])}, too_many))
        long_value = fixture(4, first='가' * 201)
        valid_prior = {'groups': [{'representativeId': 'C001',
                                  'memberIds': ['C000', 'C001', 'C002', 'C003']}],
                       'unrepresentedIds': [], **coverage(4, uncovered=['C000'])}
        cases.append((long_value, valid_prior, partition(4)))
        for inputs, receipt, proposed in cases:
            requests, traces = [], []
            with self.subTest(proposed=proposed), self.assertRaises(ValueError):
                repair_feature_curation(*inputs, receipt, 'fake',
                    transport=sender([response(proposed)], requests), call_trace=traces)
            self.assertEqual(len(requests), 1)
            self.assertFalse(traces[0]['validated'])

    def test_provider_and_relation_errors_are_not_hidden(self):
        data = fixture(4)
        prior = {**partition(4), **coverage(4, uncovered=['C003'])}
        cases = [([AnalysisError('PROVIDER_UNAVAILABLE')], AnalysisError, 1),
                 ([response(split_partition(), model='other')], AnalysisError, 1),
                 ([response(split_partition(), finish='length')], AnalysisError, 1),
                 ([response(split_partition()), AnalysisError('PROVIDER_UNAVAILABLE')], AnalysisError, 2),
                 ([response(split_partition()), response({'assessments': []})], ValueError, 2)]
        for replies, error, count in cases:
            requests, traces = [], []
            with self.subTest(count=count, error=error), self.assertRaises(error):
                repair_feature_curation(*data, prior, 'PRIVATE_KEY',
                    transport=sender(replies, requests), call_trace=traces)
            self.assertEqual(len(requests), count)
            self.assertFalse(traces[-1]['validated'])
            self.assertNotIn('PRIVATE_KEY', json.dumps(traces))
            self.assertNotIn('기록 검색', json.dumps(traces, ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
