"""Exercise real relation requests; replace only the external provider boundary."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from agentfit_ai.feature_relation_evaluation import prepare_case, load_cases, evaluate_cases
from agentfit_ai.solar import AnalysisError
from test_candidate_feature_curation import response, sender


def case():
    return {'id': 'FR01', 'document': '잠금 별칭 잠금 검토 부정',
            'representative': {'quote': '잠금', 'occurrence': 0},
            'member': {'quote': '잠금', 'occurrence': 1},
            'distractors': [{'quote': '검토', 'occurrence': 0, 'status': 'tentative'},
                            {'quote': '부정', 'occurrence': 0, 'status': 'negated'}],
            'expected': 'covered'}


def reply(status):
    return response({'assessments': [{'memberId': 'C001',
        'representativeId': 'C000', 'coverage': status}]})


class FeatureRelationEvaluationTests(unittest.TestCase):
    def test_repeated_and_overlapping_quotes_keep_specific_occurrence(self):
        prepared = prepare_case(case())
        self.assertEqual(prepared['frozen']['candidates'][:2], [
            {'id': 'C000', 'start': 0, 'end': 2},
            {'id': 'C001', 'start': 6, 'end': 8}])
        overlapping = case()
        overlapping.update(document='가가가', distractors=[])
        overlapping['representative'] = {'quote': '가가', 'occurrence': 0}
        overlapping['member'] = {'quote': '가가', 'occurrence': 1}
        self.assertEqual(prepare_case(overlapping)['frozen']['candidates'][1],
                         {'id': 'C001', 'start': 1, 'end': 3})

    def test_invalid_case_shape_anchors_and_limits_are_rejected(self):
        bads = [None, {}, {**case(), 'extra': True}]
        for name, value in [('id', '../secret'), ('id', True), ('document', ' '),
                            ('document', '가' * 100001), ('expected', 'uncertain'),
                            ('expected', []), ('distractors', {}),
                            ('distractors', case()['distractors'] * 120)]:
            bads.append({**case(), name: value})
        for selector in [None, {}, {'quote': '', 'occurrence': 0},
                         {'quote': '없음', 'occurrence': 0},
                         {'quote': '잠금', 'occurrence': True},
                         {'quote': '잠금', 'occurrence': -1},
                         {'quote': '잠금', 'occurrence': 2},
                         {'quote': '잠금', 'occurrence': 1, 'extra': 3}]:
            bads.append({**case(), 'member': selector})
        bads.append({**case(), 'member': case()['representative']})
        for status in ['confirmed', 'irrelevant', [], None]:
            bads.append({**case(), 'distractors': [
                {'quote': '검토', 'occurrence': 0, 'status': status}]})
        bads.append({**case(), 'document': '가' * 201 + ' 나', 'distractors': [],
                     'representative': {'quote': '가' * 201, 'occurrence': 0},
                     'member': {'quote': '나', 'occurrence': 0}})
        for bad in bads:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                prepare_case(bad)

    def test_corpus_hash_uses_normalized_bytes_and_validates_all_cases(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cases.json'
            raw = json.dumps({'cases': [case()]}, ensure_ascii=False, indent=2).encode()
            digest = hashlib.sha256(raw).hexdigest()
            path.write_bytes(raw.replace(b'\n', b'\r\n'))
            self.assertEqual(load_cases(path, digest), [case()])
            for expected_hash in ['0' * 64, '', None, True]:
                with self.subTest(expected_hash=expected_hash), self.assertRaises(ValueError):
                    load_cases(path, expected_hash)
            for data in [{'cases': []}, {'cases': [case(), case()]},
                         {'cases': [case()], 'extra': True}, {'cases': [case(), {}]}]:
                raw = json.dumps(data).encode()
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    load_cases(path, hashlib.sha256(raw).hexdigest())

    def test_real_requests_preserve_positions_and_hide_gold_and_distractors(self):
        cases = [case()]
        original = copy.deepcopy(cases)
        requests, snapshots = [], []
        report = evaluate_cases(cases, 'PRIVATE_KEY', transport=sender([
            reply('covered'), reply('not_covered'), reply('covered'), reply('covered')], requests),
            checkpoint=lambda value: snapshots.append(copy.deepcopy(value)))
        self.assertEqual(cases, original)
        self.assertEqual(len(requests), 4)
        for index, payload in enumerate(requests):
            data = json.loads(payload['messages'][1]['content'])
            self.assertEqual(set(data), {'document', 'candidates', 'relations'})
            self.assertEqual(data['relations'], [{'memberId': 'C001', 'representativeId': 'C000'}])
            self.assertEqual([item['id'] for item in data['candidates']],
                             ['C000', 'C001'] if index < 2 else ['C001', 'C000'])
            by_id = {item['id']: item for item in data['candidates']}
            self.assertEqual((by_id['C001']['start'], by_id['C001']['end']), (6, 8))
        self.assertEqual({key: report[key] for key in (
            'planned', 'completed', 'matched', 'false_covered', 'false_uncovered',
            'uncertain', 'failed', 'gate_passed')},
            {'planned': 4, 'completed': 4, 'matched': 3, 'false_covered': 0,
             'false_uncovered': 1, 'uncertain': 0, 'failed': 0, 'gate_passed': False})
        self.assertEqual(report['order_consistency'], {'matched': 1, 'planned': 2})
        self.assertEqual(report['repeat_consistency'], {'matched': 1, 'planned': 2})
        self.assertEqual([r['completed'] for r in snapshots], [1, 2, 3, 4])
        self.assertTrue(all(r['planned'] == 4 for r in snapshots))
        for text in ['PRIVATE_KEY', '잠금', '별칭', '검토', '부정']:
            self.assertNotIn(text, json.dumps(report, ensure_ascii=False))

    def test_failures_and_uncertain_remain_in_denominator_and_not_consistency(self):
        requests = []
        replies = [AnalysisError('PRIVATE_ERROR'), response({'assessments': []}),
                   reply('uncertain'), reply('covered')]
        report = evaluate_cases([case()], 'PRIVATE_KEY', transport=sender(replies, requests))
        self.assertEqual([report[k] for k in ('planned', 'completed', 'matched', 'failed', 'uncertain')],
                         [4, 4, 1, 2, 1])
        self.assertEqual(report['order_consistency'], {'matched': 0, 'planned': 2})
        self.assertEqual(report['repeat_consistency'], {'matched': 0, 'planned': 2})
        self.assertNotIn('PRIVATE_ERROR', json.dumps(report))
        self.assertEqual([r['actual'] for r in report['rows']],
                         ['failed', 'failed', 'uncertain', 'covered'])
        failed = evaluate_cases([case()], 'fake', transport=sender([
            AnalysisError('PROVIDER_UNAVAILABLE')] * 4, []))
        self.assertEqual(failed['order_consistency']['matched'], 0)
        self.assertEqual(failed['repeat_consistency']['matched'], 0)

    def test_one_repeat_and_false_covered_are_counted_without_trivial_repeat_success(self):
        item = {**case(), 'expected': 'not_covered'}
        report = evaluate_cases([item], 'fake', repeats=1,
            transport=sender([reply('covered'), reply('not_covered')], []))
        self.assertEqual(report['false_covered'], 1)
        self.assertEqual(report['matched'], 1)
        self.assertEqual(report['repeat_consistency'], {'matched': 0, 'planned': 0})
        perfect = evaluate_cases([item], 'fake', repeats=1,
            transport=sender([reply('not_covered')] * 2, []))
        self.assertTrue(perfect['gate_passed'])

    def test_all_options_and_cases_are_validated_before_any_provider_call(self):
        for options in [{'repeats': True}, {'repeats': 0}, {'repeats': 4},
                        {'model': 'solar-pro4'}, {'model': []}, {'checkpoint': []}]:
            requests = []
            with self.subTest(options=options), self.assertRaises(ValueError):
                evaluate_cases([case()], 'fake', transport=sender([], requests), **options)
            self.assertEqual(requests, [])
        for items, key in [([case()], ''), ([case()], None), ([case()], ' '),
                           ([], 'fake'), ([case(), {}], 'fake'), ([case()] * 2, 'fake'),
                           ([{**case(), 'id': f'FR{i:02d}'} for i in range(25)], 'fake')]:
            requests = []
            with self.subTest(key=key), self.assertRaises(ValueError):
                evaluate_cases(items, key, transport=sender([], requests))
            self.assertEqual(requests, [])
        with self.assertRaises(ValueError):
            evaluate_cases([case()], 'fake', transport=True)

    def test_checkpoint_failure_stops_before_next_call(self):
        requests = []
        def fail(_):
            raise OSError('disk full')
        with self.assertRaises(OSError):
            evaluate_cases([case()], 'fake', transport=sender([reply('covered')] * 4, requests),
                           checkpoint=fail)
        self.assertEqual(len(requests), 1)


if __name__ == '__main__':
    unittest.main()
