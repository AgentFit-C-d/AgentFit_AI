"""Only non-reflexive, assigned feature occurrences require semantic judgment."""
import copy
import json
import unittest

from agentfit_ai.candidate_feature_relations import review_feature_relations
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from test_candidate_feature_curation import MODEL, fixture, response, sender


def mixed_partition():
    return {'groups': [
        {'representativeId': 'C000', 'memberIds': ['C000', 'C001']},
        {'representativeId': 'C002', 'memberIds': ['C002', 'C003']},
        *[{'representativeId': f'C{i:03d}', 'memberIds': [f'C{i:03d}']}
          for i in range(4, 30)]], 'unrepresentedIds': ['C030']}


def assessments():
    return {'assessments': [
        {'memberId': 'C003', 'representativeId': 'C002', 'coverage': 'not_covered'},
        {'memberId': 'C001', 'representativeId': 'C000', 'coverage': 'covered'}]}


class CandidateFeatureRelationsTests(unittest.TestCase):
    def test_relations_only_review_nonself_members(self):
        data, partition = fixture(), mixed_partition()
        original = copy.deepcopy((data, partition))
        requests, traces = [], []
        result = review_feature_relations(*data, partition, 'PRIVATE_KEY',
            transport=sender([response(assessments())], requests), call_trace=traces)
        self.assertEqual(len(requests), 1)
        prompt = json.loads(requests[0]['messages'][1]['content'])
        self.assertEqual(prompt['document'], data[0])
        self.assertEqual(prompt['relations'], [
            {'memberId': 'C001', 'representativeId': 'C000'},
            {'memberId': 'C003', 'representativeId': 'C002'}])
        self.assertEqual([row['id'] for row in prompt['candidates']],
                         ['C000', 'C001', 'C002', 'C003'])
        self.assertEqual(result, {**partition,
            'checkedCandidateIds': [f'C{i:03d}' for i in range(31)],
            'uncoveredIds': ['C003', 'C030']})
        self.assertEqual((data, partition), original)
        self.assertEqual(traces[0]['relation_count'], 2)
        self.assertEqual(traces[0]['server_covered_count'], 28)
        self.assertEqual(traces[0]['unrepresented_count'], 1)
        self.assertTrue(traces[0]['validated'])
        result['groups'][0]['memberIds'].clear()
        self.assertEqual((data, partition), original)

    def test_server_only_partition_uses_no_calls(self):
        data = fixture()
        partition = {'groups': [
            {'representativeId': f'C{i:03d}', 'memberIds': [f'C{i:03d}']}
            for i in range(30)], 'unrepresentedIds': ['C030']}
        requests, traces = [], []
        result = review_feature_relations(*data, partition, 'fake',
            transport=sender([], requests), call_trace=traces)
        self.assertEqual(requests, [])
        self.assertEqual(traces, [])
        self.assertEqual(result['uncoveredIds'], ['C030'])
        self.assertEqual(result['checkedCandidateIds'], [f'C{i:03d}' for i in range(31)])
        final = finalize_candidate_analysis(data[0], 'case', data[1], data[2], {
            'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []},
            feature_curation=result)
        self.assertEqual(final['outcome'], 'needs_confirmation')
        self.assertEqual(final['featureCuration']['uncoveredCount'], 1)

    def test_identical_text_at_distinct_positions_is_reviewed(self):
        data = fixture(extras=(('기록 검색', 'features', 'confirmed'),))
        partition = {'groups': [
            {'representativeId': 'C000', 'memberIds': ['C000', 'C031']},
            {'representativeId': 'C001', 'memberIds': ['C001', 'C002']},
            *[{'representativeId': f'C{i:03d}', 'memberIds': [f'C{i:03d}']}
              for i in range(3, 31)]], 'unrepresentedIds': []}
        reply = {'assessments': [
            {'memberId': 'C002', 'representativeId': 'C001', 'coverage': 'covered'},
            {'memberId': 'C031', 'representativeId': 'C000', 'coverage': 'uncertain'}]}
        requests = []
        result = review_feature_relations(*data, partition, 'fake',
            transport=sender([response(reply)], requests))
        prompt = json.loads(requests[0]['messages'][1]['content'])
        self.assertIn({'memberId': 'C031', 'representativeId': 'C000'}, prompt['relations'])
        self.assertEqual(result['uncoveredIds'], ['C031'])

    def test_invalid_assessments_fail_closed(self):
        good = assessments()
        invalids = [None, {}, {'assessments': None}, {'assessments': []},
                    {'assessments': good['assessments'][:1]},
                    {'assessments': good['assessments'] * 2},
                    {**good, 'quote': 'PRIVATE_TEXT'}]
        for field, value in (('memberId', 'C000'), ('memberId', 'C030'),
                ('memberId', 'UNKNOWN'), ('memberId', []), ('memberId', True),
                ('representativeId', 'C000'), ('representativeId', None),
                ('coverage', True), ('coverage', None), ('coverage', 'yes')):
            bad = copy.deepcopy(good)
            bad['assessments'][0][field] = value
            invalids.append(bad)
        bad = copy.deepcopy(good)
        bad['assessments'][0]['explanation'] = 'PRIVATE_TEXT'
        invalids.append(bad)
        for bad in invalids:
            requests, traces = [], []
            with self.subTest(reply=bad), self.assertRaises(ValueError):
                review_feature_relations(*fixture(), mixed_partition(), 'fake',
                    transport=sender([response(bad)], requests), call_trace=traces)
            self.assertEqual(len(requests), 1)
            self.assertFalse(traces[0]['validated'])
            self.assertNotIn('PRIVATE_TEXT', json.dumps(traces))

    def test_invalid_input_does_not_call_provider(self):
        document, frozen, labels = fixture()
        bad_partitions = [None, {}, {**mixed_partition(), 'extra': 1},
            {**mixed_partition(), 'unrepresentedIds': []},
            {**mixed_partition(), 'unrepresentedIds': ['C000', 'C030']}]
        for part in bad_partitions:
            requests = []
            with self.subTest(part=part), self.assertRaises(ValueError):
                review_feature_relations(document, frozen, labels, part, 'fake',
                    transport=sender([], requests))
            self.assertEqual(requests, [])
        for doc, status, key, options in (
                (' ', labels, 'fake', {}), (document, labels[:-1], 'fake', {}),
                (document, labels, '', {}), (document, labels, 'fake', {'model': 'bad'}),
                (document, labels, 'fake', {'call_trace': {}})):
            requests = []
            with self.subTest(options=options), self.assertRaises(ValueError):
                review_feature_relations(doc, frozen, status, mixed_partition(), key,
                    transport=sender([], requests), **options)
            self.assertEqual(requests, [])

    def test_provider_errors_and_diagnostics(self):
        for reply in (response(assessments(), model='wrong/model'),
                      response(assessments(), finish='length'),
                      AnalysisError('PROVIDER_UNAVAILABLE')):
            requests, traces = [], []
            with self.subTest(), self.assertRaises(AnalysisError):
                review_feature_relations(*fixture(), mixed_partition(), 'PRIVATE_KEY',
                    transport=sender([reply], requests), call_trace=traces)
            self.assertEqual(len(requests), 1)
            self.assertFalse(traces[0]['validated'])
            diagnostic = json.dumps(traces, ensure_ascii=False)
            self.assertNotIn('PRIVATE_KEY', diagnostic)
            self.assertNotIn('기록 검색', diagnostic)
            self.assertNotIn('raw', diagnostic)


if __name__ == '__main__':
    unittest.main()
