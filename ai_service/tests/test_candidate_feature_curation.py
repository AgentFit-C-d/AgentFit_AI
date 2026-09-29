"""Representative selection must not hide unrepresented or unreviewed operations."""
import copy
import json
import unittest

from agentfit_ai.candidate_feature_curation import (
    curate_reviewed_features, validate_feature_curation)
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.profile import FIELDS
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


def relation_response(count=31, *, uncovered=()):
    return {'assessments': [
        {'memberId': f'C{index:03d}', 'representativeId': 'C000',
         'coverage': 'not_covered' if f'C{index:03d}' in uncovered else 'covered'}
        for index in range(1, count)]}


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
            transport=sender([response(partition()), response(relation_response())], requests),
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
        self.assertEqual(second['relations'], [
            {'memberId': f'C{index:03d}', 'representativeId': 'C000'}
            for index in range(1, 31)])
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


    def verdict(self, *, wrong=(), missing=()):
        return {'checkedFields': list(FIELDS), 'missingFields': list(missing),
                'wrongCandidateIds': list(wrong)}

    def test_projection_keeps_representatives_and_nine_fields(self):
        data = fixture(extras=(('TestApp', 'project_name', 'confirmed'),
            ('web app', 'project_type', 'confirmed'), ('records', 'domain', 'confirmed'),
            ('React', 'frontend', 'confirmed'), ('Go', 'backend', 'confirmed'),
            ('ModelX', 'ai', 'confirmed'), ('SQLite', 'database', 'confirmed'),
            ('CloudZ', 'deployment', 'confirmed'), ('MailSvc', 'external_integrations', 'confirmed')))
        document, frozen, labels = data
        baseline = finalize_candidate_analysis(document, 'case', frozen, labels, self.verdict())
        self.assertIsNone(baseline['profile']['data']['features'])
        curated = finalize_candidate_analysis(document, 'case', frozen, labels, self.verdict(),
                                              feature_curation={**partition(), **coverage()})
        self.assertEqual(curated['profile']['data']['features'], ['기록 검색'])
        self.assertEqual(curated['profile']['evidence']['features'], [
            {'documentId': 'case', 'start': 0, 'end': 5}])
        self.assertEqual(curated['featureCuration'], {
            'candidateCount': 31, 'selectedCount': 1, 'uncoveredCount': 0})
        self.assertEqual(curated['outcome'], 'candidate_profile')
        self.assertEqual(curated['unresolvedFields'], [])
        for field in FIELDS:
            if field != 'features':
                self.assertEqual(curated['profile']['data'][field], baseline['profile']['data'][field])
                self.assertEqual(curated['profile']['evidence'][field], baseline['profile']['evidence'][field])

    def test_projection_keeps_unresolved_and_reviewed_labels(self):
        document, frozen, labels = fixture(extras=(('Go', 'backend', 'confirmed'),))
        frozen['rejected'] = [{'index': 40, 'reason': 'ambiguous_anchor'}]
        verdict = self.verdict(wrong=['C031'], missing=['domain'])
        groups = partition(30)
        groups['unrepresentedIds'] = ['C030']
        curation = {**groups, **coverage(uncovered=['C030', 'C020'])}
        original = copy.deepcopy((frozen, labels, verdict, curation))
        observed = {}
        def observer(stage, value):
            if stage == 'reviewed':
                observed.update(value)
        result = finalize_candidate_analysis(document, 'case', frozen, labels, verdict,
            observer=observer, feature_curation=curation)
        self.assertEqual(result['profile']['data']['features'], ['기록 검색'])
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertEqual(result['unresolvedFields'], ['domain', 'backend', 'features'])
        self.assertEqual(result['reviewIssueCount'], 4)
        self.assertEqual(result['featureCuration']['uncoveredCount'], 2)
        self.assertEqual(observed['labels'][1]['status'], 'confirmed')
        self.assertEqual(observed['labels'][-1]['status'], 'irrelevant')
        self.assertEqual((frozen, labels, verdict, curation), original)

    def test_projection_rejects_stale_or_foreign_curation(self):
        document, frozen, labels = fixture(extras=(
            ('기록 검색', 'features', 'negated'), ('Go', 'backend', 'confirmed')))
        complete = {**partition(), **coverage()}
        invalids = [(self.verdict(wrong=['C000']), complete)]
        for wrong_id in ('C031', 'C032', 'UNKNOWN'):
            bad = copy.deepcopy(complete)
            bad['groups'][0]['memberIds'][-1] = wrong_id
            invalids.append((self.verdict(), bad))
        for verdict, curation in invalids:
            with self.subTest(verdict=verdict), self.assertRaises(ValueError):
                finalize_candidate_analysis(document, 'case', frozen, labels, verdict,
                                             feature_curation=curation)

    def test_default_projection_retains_existing_overflow_behavior(self):
        document, frozen, labels = fixture()
        before = finalize_candidate_analysis(document, 'case', frozen, labels, self.verdict())
        explicit = finalize_candidate_analysis(document, 'case', frozen, labels, self.verdict(),
                                                feature_curation=None)
        self.assertEqual(before, explicit)
        self.assertIsNone(explicit['profile']['data']['features'])
        self.assertEqual(explicit['unresolvedFields'], ['features'])
        self.assertEqual(explicit['outcome'], 'needs_confirmation')

    def test_final_curation_rejects_self_uncovered(self):
        data = fixture()
        curation = {**partition(), **coverage(uncovered=['C000'])}
        with self.assertRaises(ValueError):
            validate_feature_curation(*data, curation)
        with self.assertRaises(ValueError):
            finalize_candidate_analysis(data[0], 'case', data[1], data[2], self.verdict(),
                                         feature_curation=curation)

    def test_singleton_partition_skips_semantic_provider(self):
        data = fixture()
        proposed = {'groups': [
            {'representativeId': f'C{i:03d}', 'memberIds': [f'C{i:03d}']}
            for i in range(30)], 'unrepresentedIds': ['C030']}
        requests, traces = [], []
        result = curate_reviewed_features(*data, 'fake',
            transport=sender([response(proposed)], requests), call_trace=traces)
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(traces), 1)
        self.assertEqual(result, {**proposed, **coverage(uncovered=['C030'])})

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

    def test_duplicate_final_or_oversized_proposed_values_fail(self):
        duplicated = fixture(extras=(('기록 검색', 'features', 'confirmed'),))
        duplicate_groups = {'groups': [partition()['groups'][0],
                                      {'representativeId': 'C031', 'memberIds': ['C031']}],
                            'unrepresentedIds': []}
        with self.assertRaises(ValueError):
            validate_feature_curation(*duplicated, {**duplicate_groups, **coverage(32)})
        requests = []
        with self.assertRaises(ValueError):
            curate_reviewed_features(*fixture(first='가' * 201), 'fake',
                transport=sender([response(partition())], requests))
        self.assertEqual(len(requests), 1)

    def test_repeated_representatives_keep_every_occurrence_for_coverage(self):
        data = fixture(extras=(('기록 검색', 'features', 'confirmed'),))
        groups = [partition()['groups'][0],
                  {'representativeId': 'C031', 'memberIds': ['C031']}]
        for proposed_groups in (groups, list(reversed(groups))):
            proposed = {'groups': proposed_groups, 'unrepresentedIds': []}
            original = copy.deepcopy((data, proposed))
            requests = []
            # The second occurrence has a different context; the independent
            # reviewer says the chosen occurrence cannot represent it.
            result = curate_reviewed_features(*data, 'fake', transport=sender([
                response(proposed), response(relation_response(32, uncovered=['C031']))], requests))
            self.assertEqual(len(requests), 2)
            reviewed_partition = json.loads(requests[1]['messages'][1]['content'])
            self.assertEqual(reviewed_partition['relations'], [
                {'memberId': f'C{i:03d}', 'representativeId': 'C000'} for i in range(1, 32)])
            self.assertEqual(result, {**partition(32), **coverage(32, uncovered=['C031'])})
            final = finalize_candidate_analysis(data[0], 'case', data[1], data[2],
                self.verdict(), feature_curation=result)
            self.assertEqual(final['profile']['data']['features'], ['기록 검색'])
            self.assertEqual(final['featureCuration'], {
                'candidateCount': 32, 'selectedCount': 1, 'uncoveredCount': 1})
            self.assertEqual(final['outcome'], 'needs_confirmation')
            self.assertIn('features', final['unresolvedFields'])
            self.assertEqual((data, proposed), original)

    def test_repeated_representatives_still_require_valid_partition_and_review(self):
        data = fixture(extras=(('기록 검색', 'features', 'confirmed'),))
        proposed = {'groups': [partition()['groups'][0],
            {'representativeId': 'C031', 'memberIds': ['C031']}], 'unrepresentedIds': []}
        requests = []
        with self.assertRaises(AnalysisError):
            curate_reviewed_features(*data, 'fake', transport=sender([
                response(proposed), AnalysisError('PROVIDER_UNAVAILABLE')], requests))
        self.assertEqual(len(requests), 2)
        for wrong_member in ('C000', 'UNKNOWN'):
            bad = copy.deepcopy(proposed)
            bad['groups'][1]['memberIds'].append(wrong_member)
            requests = []
            with self.subTest(wrong_member=wrong_member), self.assertRaises(ValueError):
                curate_reviewed_features(*data, 'fake',
                    transport=sender([response(bad)], requests))
            self.assertEqual(len(requests), 1)

    def test_invalid_review_and_provider_fail_closed(self):
        data = fixture()
        good = relation_response()
        reviews = [coverage(), {'assessments': good['assessments'][:-1]},
                   {'assessments': good['assessments'] + good['assessments'][:1]},
                   {'assessments': [True]}, {'assessments': {}},
                   {**good, 'extra': 'private'}, None]
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
            response(groups), response(relation_response(30, uncovered=['C012']))], requests))
        summary = validate_feature_curation(*data, result)
        self.assertEqual(summary, {'selectedIds': ['C000'],
                                  'uncoveredIds': ['C012', 'C030'], 'candidateCount': 31})

    def test_coverage_reply_cannot_replace_proposed_partition(self):
        for replacement in ({'groups': partition()['groups']}, {'unrepresentedIds': []}):
            requests = []
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                curate_reviewed_features(*fixture(), 'fake', transport=sender([
                    response(partition()), response({**relation_response(), **replacement})], requests))
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
