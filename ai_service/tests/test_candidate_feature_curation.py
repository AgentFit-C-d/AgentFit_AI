"""Representative selection must not hide unrepresented or unreviewed operations."""
import copy
import json
import unittest

from agentfit_ai.candidate_feature_curation import (
    curate_reviewed_features, validate_feature_curation)
from agentfit_ai.solar import AnalysisError


MODEL = 'deepseek-ai/deepseek-v4.1-flash'


def fixture(count=31, *, extras=(), first='기록 검색'):
    values = [first] + [f'조건 {index:02d}로 기록 검색' for index in range(1, count)] if count else []
    records = [(value, 'features', 'confirmed') for value in values] + list(extras)
    document = '\n'.join(row[0] for row in records) or '기능은 미정'
    candidates, labels, offset = [], [], 0
    for index, (value, field, status) in enumerate(records):
        candidate_id = f'C{index:03d}'
        candidates.append({'id': candidate_id, 'start': offset, 'end': offset + len(value)})
        labels.append({'id': candidate_id, 'field': field, 'status': status})
        offset += len(value) + 1
    return document, {'candidates': candidates, 'rejected': []}, labels


def partition(count=31):
    return {'groups': [{'representativeId': 'C000',
                        'memberIds': [f'C{index:03d}' for index in range(count)]}],
            'unrepresentedIds': []}


def coverage(count=31, *, uncovered=()):
    return {'checkedCandidateIds': [f'C{index:03d}' for index in range(count)],
            'uncoveredIds': list(uncovered)}


def response(body, *, model=MODEL, finish='stop'):
    return json.dumps({'model': model, 'choices': [{'finish_reason': finish,
        'message': {'role': 'assistant', 'content': json.dumps(body, ensure_ascii=False)}}],
        'usage': {'prompt_tokens': 11, 'completion_tokens': 7}}).encode('utf-8')


def sender(replies, requests):
    queue = list(replies)
    def transport(payload, key, timeout):
        requests.append(copy.deepcopy(payload))
        if not queue:
            raise AssertionError('Unexpected extra provider call')
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    return transport


class CandidateFeatureCurationTests(unittest.TestCase):
    def test_overflow_builds_partition_and_checks_every_member(self):
        document, frozen, labels = fixture(extras=(
            ('기록 검색', 'features', 'negated'),
            ('기록 검색', 'features', 'tentative'), ('Go', 'backend', 'confirmed')))
        original = copy.deepcopy((frozen, labels))
        requests, traces = [], []
        result = curate_reviewed_features(document, frozen, labels, 'PRIVATE_KEY',
            transport=sender([response(partition()), response(coverage())], requests),
            call_trace=traces)
        self.assertEqual(result, {**partition(), **coverage()})
        self.assertEqual(validate_feature_curation(document, frozen, labels, result), {
            'selectedIds': ['C000'], 'uncoveredIds': [], 'candidateCount': 31})
        self.assertEqual(len(requests), 2)
        first, second = [json.loads(payload['messages'][1]['content']) for payload in requests]
        self.assertEqual(first['document'], document)
        self.assertEqual([row['id'] for row in first['candidates']],
                         [f'C{index:03d}' for index in range(31)])
        self.assertEqual(first['candidates'][0]['value'], '기록 검색')
        self.assertEqual(second['groups'], partition()['groups'])
        self.assertEqual(second['candidates'], first['candidates'])
        self.assertEqual((frozen, labels), original)
        self.assertEqual([trace['validated'] for trace in traces], [True, True])
        self.assertNotIn('PRIVATE_KEY', json.dumps(traces))
        self.assertNotIn('기록 검색', json.dumps(traces, ensure_ascii=False))
        self.assertNotIn('raw', json.dumps(traces))

    def test_no_overflow_uses_no_calls(self):
        for count, extras in ((0, ()), (1, ()), (30, ()),
                              (30, (('기록 검색', 'features', 'confirmed'),))):
            document, frozen, labels = fixture(count, extras=extras)
            requests = []
            result = curate_reviewed_features(document, frozen, labels, 'fake',
                                              transport=sender([], requests))
            self.assertIsNone(result)
            self.assertEqual(requests, [])

    def test_invalid_partitions_fail_before_review(self):
        document, frozen, labels = fixture(extras=(
            ('기록 검색', 'features', 'negated'), ('Go', 'backend', 'confirmed')))
        good = partition()
        bads = [None, {}, {'groups': [], 'unrepresentedIds': coverage()['checkedCandidateIds']},
                {'groups': good['groups'], 'unrepresentedIds': ['C000']},
                {'groups': good['groups'] * 2, 'unrepresentedIds': []},
                {'groups': good['groups'], 'unrepresentedIds': None},
                {'groups': good['groups'], 'unrepresentedIds': [], 'quote': 'private'},
                {'groups': [{'representativeId': f'C{i:03d}', 'memberIds': [f'C{i:03d}']}
                            for i in range(31)], 'unrepresentedIds': []}]
        for member_ids in ([], ['C000'], ['C000'] * 31,
                           coverage()['checkedCandidateIds'] + ['C031'],
                           coverage()['checkedCandidateIds'] + ['C032'],
                           coverage()['checkedCandidateIds'] + ['UNKNOWN'], [True], None):
            bads.append({'groups': [{'representativeId': 'C000', 'memberIds': member_ids}],
                         'unrepresentedIds': []})
        for rep in (True, [], None, 'C031', 'C032', 'UNKNOWN'):
            bads.append({'groups': [{'representativeId': rep,
                                    'memberIds': coverage()['checkedCandidateIds']}],
                         'unrepresentedIds': []})
        bads.append({'groups': [{'representativeId': 'C000',
                                'memberIds': coverage()['checkedCandidateIds'][1:]}],
                     'unrepresentedIds': ['C000']})
        for bad in bads:
            requests, traces = [], []
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                curate_reviewed_features(document, frozen, labels, 'fake',
                    transport=sender([response(bad)], requests), call_trace=traces)
            self.assertEqual(len(requests), 1)
            self.assertFalse(traces[0]['validated'])

    def test_duplicate_or_oversized_representative_values_fail(self):
        duplicated = fixture(extras=(('기록 검색', 'features', 'confirmed'),))
        duplicate_groups = {'groups': [partition()['groups'][0],
                                      {'representativeId': 'C031', 'memberIds': ['C031']}],
                            'unrepresentedIds': []}
        for data, selected in ((duplicated, duplicate_groups),
                                (fixture(first='가' * 201), partition())):
            requests = []
            with self.subTest(), self.assertRaises(ValueError):
                curate_reviewed_features(*data, 'fake',
                    transport=sender([response(selected)], requests))
            self.assertEqual(len(requests), 1)

    def test_invalid_review_and_provider_fail_closed(self):
        data = fixture()
        good = coverage()
        reviews = [{**good, 'checkedCandidateIds': list(reversed(good['checkedCandidateIds']))},
                   {**good, 'checkedCandidateIds': good['checkedCandidateIds'][:-1]},
                   {**good, 'uncoveredIds': ['C000', 'C000']},
                   {**good, 'uncoveredIds': ['C031']}, {**good, 'uncoveredIds': [True]},
                   {**good, 'uncoveredIds': {}}, {**good, 'extra': 'private'}, None]
        for bad in reviews:
            requests, traces = [], []
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                curate_reviewed_features(*data, 'fake', call_trace=traces,
                    transport=sender([response(partition()), response(bad)], requests))
            self.assertEqual(len(requests), 2)
            self.assertEqual([x['validated'] for x in traces], [True, False])
        for replies, expected_calls in (
                ([response(partition(), model='wrong/model')], 1),
                ([response(partition(), finish='length')], 1),
                ([response(partition()), AnalysisError('PROVIDER_UNAVAILABLE')], 2)):
            requests = []
            with self.subTest(replies=replies), self.assertRaises(AnalysisError):
                curate_reviewed_features(*data, 'fake', transport=sender(replies, requests))
            self.assertEqual(len(requests), expected_calls)

    def test_unrepresented_and_uncovered_are_preserved(self):
        data = fixture()
        groups = partition(30)
        groups['unrepresentedIds'] = ['C030']
        requests = []
        result = curate_reviewed_features(*data, 'fake', transport=sender([
            response(groups), response(coverage(uncovered=['C030', 'C012']))], requests))
        summary = validate_feature_curation(*data, result)
        self.assertEqual(summary, {'selectedIds': ['C000'],
                                  'uncoveredIds': ['C012', 'C030'], 'candidateCount': 31})

    def test_coverage_reply_cannot_replace_proposed_partition(self):
        for replacement in ({'groups': partition()['groups']}, {'unrepresentedIds': []}):
            requests = []
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                curate_reviewed_features(*fixture(), 'fake', transport=sender([
                    response(partition()), response({**coverage(), **replacement})], requests))
            self.assertEqual(len(requests), 2)

    def test_invalid_inputs_fail_before_provider(self):
        document, frozen, labels = fixture()
        cases = [(document, frozen, labels, {'model': 'not-a-model'}),
                 (document, frozen, labels, {'call_trace': {}}),
                 (' ', frozen, labels, {}), ('x' * 100001, frozen, labels, {}),
                 (document, {'candidates': frozen['candidates'] * 8, 'rejected': []}, labels * 8, {}),
                 (document, frozen, labels[:-1], {})]
        for doc, candidates, statuses, options in cases:
            requests = []
            with self.subTest(options=options), self.assertRaises(ValueError):
                curate_reviewed_features(doc, candidates, statuses, 'fake',
                    transport=sender([], requests), **options)
            self.assertEqual(requests, [])


if __name__ == '__main__':
    unittest.main()
