"""Whole-path contracts, using source fixtures and fake provider transports."""

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_first_profile import apply_candidate_review, CandidatePipelineError
from agentfit_ai.candidate_analysis_pipeline import _merge_occurrences, analyze_integrated_candidates
from agentfit_ai.profile import FIELDS
from test_candidate_feature_curation import response


SOLAR_KEY, NVIDIA_KEY = 'unit-solar-secret', 'unit-nvidia-secret'
DEEPSEEK, GLM, KIMI = ('deepseek-ai/deepseek-v4.1-flash', 'z-ai/glm-5.3',
                       'moonshotai/kimi-k3')
FACTS = [('TestApp', 'project_name'), ('web app', 'project_type'), ('records', 'domain'),
         ('React', 'frontend'), ('Go', 'backend'), ('ModelX', 'ai'),
         ('SQLite', 'database'), ('CloudZ', 'deployment'), ('MailSvc', 'external_integrations')]


def extraction(value):
    return SimpleNamespace(extraction_class='candidate', extraction_text=value)


class ProviderFixture:
    """Only external generation is faked; all application stages are real."""
    def __init__(self, count=32, *, wrong=(), missing=(), same_partition=False,
                 fail_name=None, fail_reply=None, extractions=None):
        self.values = [f'기록 작업 {i:02}' for i in range(count)]
        self.document = '\n'.join([row[0] for row in FACTS] + self.values)
        self.wrong, self.missing = list(wrong), list(missing)
        self.same_partition = same_partition
        self.fail_name, self.fail_reply = fail_name, fail_reply
        self.extractions = extractions
        self.requests, self.relations = [], 0

    def extractor(self, document, key, **options):
        assert document == self.document and key == SOLAR_KEY
        assert options['max_tokens'] == 8192
        return (self.extractions if self.extractions is not None else
                [extraction(value) for value, _ in FACTS] + [extraction(self.values[0])])

    def transport(self, payload, key, timeout):
        name = payload.get('response_format', {}).get('json_schema', {}).get('name')
        model = payload['model']
        assert key == (SOLAR_KEY if model == 'solar-pro4' else NVIDIA_KEY)
        assert timeout == 600
        self.requests.append(deepcopy(payload))
        if name == self.fail_name and name is not None:
            if self.fail_reply is not None:
                return self.fail_reply
            raise RuntimeError('private provider content ' + key)
        if name is None:  # LangExtract adapter boundary test.
            return b'{}'
        data = json.loads(payload['messages'][1]['content'])
        if name == 'agentfit_operation_candidates':
            body = {'mentions': [{'quote': value, 'anchor': value}
                                  for value in reversed(self.values)]}
        elif name == 'agentfit_candidate_labels':
            fields = dict(FACTS)
            body = {'labels': [{'id': row['id'], 'field': fields.get(row['value'], 'features'),
                                'status': 'confirmed'} for row in data['candidates']]}
        elif name == 'agentfit_candidate_label_review':
            ids = [row['id'] for row in data['selections']]
            wrong = [item for item in ids if item in self.wrong]
            body = {'checkedCandidateIds': ids, 'wrongCandidateIds': wrong,
                    'rejectionReasons': [{'id': item, 'reason': 'not_current'} for item in wrong]}
        elif name == 'agentfit_candidate_source_coverage':
            body = {'checkedFields': list(FIELDS), 'missingFields': self.missing}
        elif name in ('agentfit_feature_grouping', 'agentfit_feature_regrouping'):
            ids = [row['id'] for row in data['candidates']]
            split = name == 'agentfit_feature_regrouping' and not self.same_partition
            body = {'groups': [{'representativeId': ids[0], 'memberIds': ids[:-1] if split else ids}],
                    'unrepresentedIds': []}
            if split:
                body['groups'].append({'representativeId': ids[-1], 'memberIds': [ids[-1]]})
        elif name == 'agentfit_feature_relations':
            self.relations += 1
            body = {'assessments': [{**row, 'coverage': 'not_covered'
                    if self.relations == 1 and index == len(data['relations']) - 1 else 'covered'}
                    for index, row in enumerate(data['relations'])]}
        else:
            raise AssertionError('unexpected provider schema')
        return response(body, model=model)

    def run(self, **options):
        return analyze_integrated_candidates(self.document, 'DOC', SOLAR_KEY, NVIDIA_KEY,
            **dict({'extractor': self.extractor, 'solar_transport': self.transport,
                    'nvidia_transport': self.transport}, **options))


class IntegratedCandidateTests(unittest.TestCase):
    def test_whole_pipeline_repairs_features_and_preserves_nine_fields_and_review_gates(self):
        case = ProviderFixture(wrong=['C040'], missing=['domain'])
        events, calls, reviews = [], [], []
        result = case.run(observer=lambda stage, state: events.append((stage, state)),
                          call_trace=calls, review_calls=reviews)
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertEqual(result['unresolvedFields'], ['domain', 'features'])
        self.assertEqual(result['candidateCount'], 41)
        self.assertEqual(result['reviewIssueCount'], 2)
        self.assertEqual(result['featureCuration'], {
            'candidateCount': 31, 'selectedCount': 2, 'uncoveredCount': 0})
        self.assertEqual(result['profile']['data'], {
            'project_name': 'TestApp', 'project_type': 'web app', 'domain': 'records',
            'frontend': ['React'], 'backend': ['Go'], 'ai': ['ModelX'],
            'database': 'SQLite', 'deployment': 'CloudZ',
            'features': ['기록 작업 00', '기록 작업 30'], 'external_integrations': ['MailSvc']})
        self.assertEqual(result['profile']['evidence']['project_name'],
                         [{'documentId': 'DOC', 'start': 0, 'end': 7}])
        self.assertEqual([item[0] for item in events], ['grounded', 'classified', 'reviewed', 'projected'])
        self.assertEqual(events[0][1]['candidates'][9], {'id': 'C009', 'start': 62, 'end': 70})
        self.assertEqual(events[2][1]['labels'][-1]['status'], 'irrelevant')
        self.assertEqual(sum(row['status'] == 'confirmed' for row in events[2][1]['labels']), 40)
        self.assertEqual(len(case.requests), 11)
        self.assertEqual([row['call_index'] for row in calls], list(range(1, 12)))
        self.assertTrue(all(row['transport_completed'] for row in calls))
        self.assertEqual(len(reviews), 4)
        self.assertTrue(all(row['validated'] for row in reviews))
        for payload in case.requests:
            name = payload['response_format']['json_schema']['name']
            data = json.loads(payload['messages'][1]['content'])
            if name in ('agentfit_candidate_labels', 'agentfit_candidate_label_review',
                        'agentfit_candidate_source_coverage'):
                self.assertIn('Field semantics explicit-v1', payload['messages'][0]['content'])
            if name.startswith('agentfit_feature_'):
                self.assertNotIn('C040', [row['id'] for row in data['candidates']])
        serialized = json.dumps(calls, ensure_ascii=False)
        for forbidden in (SOLAR_KEY, NVIDIA_KEY, '기록 작업', 'TestApp'):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(set(calls[0]), {'stage', 'provider', 'requested_model', 'call_index',
            'elapsed_ms', 'response_bytes', 'transport_completed'})

    def test_small_feature_set_does_not_trigger_curation_and_models_can_be_selected(self):
        case = ProviderFixture(1)
        calls = [{'prior': True}]
        result = case.run(review_model=KIMI, feature_model=GLM, call_trace=calls)
        self.assertEqual(result['outcome'], 'candidate_profile')
        self.assertEqual(result['profile']['data']['features'], ['기록 작업 00'])
        self.assertNotIn('featureCuration', result)
        self.assertEqual([p['model'] for p in case.requests], [GLM, 'solar-pro4', KIMI, KIMI])
        self.assertEqual([r['call_index'] for r in calls[1:]], [1, 2, 3, 4])

    def test_unchanged_repair_partition_keeps_uncovered_gate_without_resampling(self):
        case = ProviderFixture(31, same_partition=True)
        result = case.run()
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertEqual(result['unresolvedFields'], ['features'])
        self.assertEqual(result['featureCuration']['uncoveredCount'], 1)
        self.assertEqual(case.relations, 1)
        self.assertEqual(case.requests[-1]['response_format']['json_schema']['name'],
                         'agentfit_feature_regrouping')

    def test_extraction_rejections_are_not_hidden_by_successful_review(self):
        case = ProviderFixture(1, extractions=[extraction('not in source')])
        result = case.run()
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertEqual(result['rejectedReasons'], {'source_quote_absent': 1})

    def test_bad_configuration_is_rejected_before_extraction_or_transport(self):
        calls = []
        def forbidden(*args, **kwargs):
            calls.append(True)
            raise AssertionError('network or extraction before validation')
        bad = [('document', ''), ('document', 'x' * 100001), ('document', SOLAR_KEY),
               ('document', NVIDIA_KEY), ('document_id', ' '), ('document_id', SOLAR_KEY),
               ('document_id', NVIDIA_KEY), ('solar_key', ''), ('nvidia_key', None),
               ('review_model', 'solar-pro4'), ('feature_model', []), ('max_calls', True),
               ('max_calls', 0), ('max_calls', 65), ('max_calls', 1.5),
               ('extractor', False), ('observer', 'bad'), ('solar_transport', 1),
               ('nvidia_transport', []), ('call_trace', {}), ('review_calls', ())]
        for name, value in bad:
            options = dict(document='test document', document_id='DOC', solar_key=SOLAR_KEY,
                nvidia_key=NVIDIA_KEY, extractor=forbidden, solar_transport=forbidden,
                nvidia_transport=forbidden)
            options[name] = value
            with self.subTest(name=name, value=type(value).__name__), self.assertRaises(ValueError):
                analyze_integrated_candidates(**options)
        self.assertEqual(calls, [])

    def test_transport_failures_report_fixed_stage_and_never_raw_error_or_secrets(self):
        for schema, stage in (
            ('agentfit_operation_candidates', 'OPERATION_EXTRACTION_FAILED'),
            ('agentfit_candidate_labels', 'CLASSIFICATION_FAILED'),
            ('agentfit_candidate_label_review', 'COVERAGE_REVIEW_FAILED'),
            ('agentfit_candidate_source_coverage', 'COVERAGE_REVIEW_FAILED'),
            ('agentfit_feature_grouping', 'FEATURE_CURATION_FAILED')):
            case, trace = ProviderFixture(fail_name=schema), []
            with self.subTest(schema=schema), self.assertRaises(CandidatePipelineError) as caught:
                case.run(call_trace=trace)
            self.assertEqual(caught.exception.stage, stage)
            self.assertEqual(caught.exception.provider_code, 'PROVIDER_FAILURE')
            self.assertEqual(str(caught.exception), stage)
            self.assertFalse(trace[-1]['transport_completed'])
            self.assertEqual(case.requests[-1]['response_format']['json_schema']['name'], schema)

    def test_invalid_response_is_not_semantic_success_even_if_transport_completed(self):
        case = ProviderFixture(1, fail_name='agentfit_candidate_labels',
                               fail_reply=response({'labels': []}, model='solar-pro4'))
        trace = []
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(call_trace=trace)
        self.assertEqual(caught.exception.stage, 'CLASSIFICATION_FAILED')
        self.assertEqual(caught.exception.detail, 'LABEL_COUNT_MISMATCH')
        self.assertTrue(trace[-1]['transport_completed'])

    def test_shared_budget_blocks_next_provider_without_sending(self):
        for limit, stage in ((1, 'CLASSIFICATION_FAILED'), (2, 'COVERAGE_REVIEW_FAILED'),
                             (3, 'COVERAGE_REVIEW_FAILED')):
            case, trace = ProviderFixture(1), []
            with self.subTest(limit=limit), self.assertRaises(CandidatePipelineError) as caught:
                case.run(max_calls=limit, call_trace=trace)
            self.assertEqual((caught.exception.stage, caught.exception.detail),
                             (stage, 'CALL_BUDGET_EXCEEDED'))
            self.assertEqual(len(case.requests), limit)
            self.assertEqual(len(trace), limit)

    def test_observers_get_copies_and_cannot_mutate_final_result(self):
        case = ProviderFixture(1)
        def mutate(stage, state):
            state.clear()
        result = case.run(observer=mutate)
        self.assertEqual(result['outcome'], 'candidate_profile')
        self.assertEqual(result['profile']['data']['project_name'], 'TestApp')

    def test_observer_failure_stops_further_calls_in_each_stage(self):
        for stage, sent in (('grounded', 1), ('classified', 2), ('reviewed', 4), ('projected', 4)):
            case = ProviderFixture(1)
            def fail(event, state):
                if stage == event:
                    raise RuntimeError(NVIDIA_KEY)
            with self.subTest(stage=stage), self.assertRaises(CandidatePipelineError) as caught:
                case.run(observer=fail)
            self.assertEqual(caught.exception.stage, 'DIAGNOSTIC_FAILED')
            self.assertEqual(len(case.requests), sent)

    def test_default_extractor_receives_metered_transport_and_preserves_extraction_policy(self):
        case, trace = ProviderFixture(1), []
        def library_adapter(document, key, *, transport, prompt_description, max_tokens):
            self.assertEqual(max_tokens, 8192)
            self.assertIn('without deciding their status', prompt_description)
            transport({'model': 'solar-pro4'}, key, 600)
            return [extraction('TestApp')]
        with patch('agentfit_ai.langextract_solar_trial.extract_candidates', library_adapter):
            result = case.run(extractor=None, call_trace=trace)
        self.assertEqual(result['candidateCount'], 2)
        self.assertEqual(len(trace), 5)
        self.assertEqual(trace[0]['stage'], 'EXTRACTION_FAILED')
        self.assertEqual(trace[0]['provider'], 'solar')

    def test_budget_is_not_bypassed_if_extraction_library_swallows_transport_error(self):
        case, trace = ProviderFixture(1), []
        def swallowing_adapter(document, key, *, transport, **options):
            transport({'model': 'solar-pro4'}, key, 600)
            try:
                transport({'model': 'solar-pro4'}, key, 600)
            except Exception:
                pass
            return [extraction('TestApp')]
        with patch('agentfit_ai.langextract_solar_trial.extract_candidates', swallowing_adapter):
            with self.assertRaises(CandidatePipelineError) as caught:
                case.run(extractor=None, max_calls=1, call_trace=trace)
        self.assertEqual((caught.exception.stage, caught.exception.detail),
                         ('EXTRACTION_FAILED', 'CALL_BUDGET_EXCEEDED'))
        self.assertEqual(len(case.requests), 1)
        self.assertEqual(len(trace), 1)

    def test_extractor_and_grounding_failures_have_distinct_stages(self):
        case = ProviderFixture(1)
        def broken(*args, **kwargs):
            raise RuntimeError(SOLAR_KEY)
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(extractor=broken)
        self.assertEqual(caught.exception.stage, 'EXTRACTION_FAILED')
        case.document = 'A' * 241
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(extractor=lambda *args, **kwargs: [extraction('A')])
        self.assertEqual((caught.exception.stage, caught.exception.detail),
                         ('GROUNDING_FAILED', 'CANDIDATE_OCCURRENCE_LIMIT'))
        self.assertEqual(case.requests, [])


class CandidateMergeTests(unittest.TestCase):
    def test_union_deduplicates_positions_but_preserves_repeated_words(self):
        # Same phrase at another position must retain independent certainty.
        first = {'candidates': [{'id': 'C009', 'start': 2, 'end': 3},
                                {'id': 'C008', 'start': 0, 'end': 1}],
                 'rejected': [{'index': 8, 'reason': 'source_quote_absent'}]}
        second = {'candidates': [{'id': 'C009', 'start': 0, 'end': 1},
                                 {'id': 'C001', 'start': 4, 'end': 5}],
                  'rejected': [{'index': 9, 'reason': 'invalid_anchor'}]}
        before = deepcopy((first, second))
        merged = _merge_occurrences('A A B', first, second)
        self.assertEqual(merged, {
            'candidates': [{'id': 'C000', 'start': 0, 'end': 1},
                           {'id': 'C001', 'start': 2, 'end': 3},
                           {'id': 'C002', 'start': 4, 'end': 5}],
            'rejected': [{'index': 0, 'reason': 'source_quote_absent'},
                         {'index': 1, 'reason': 'invalid_anchor'}]})
        merged['candidates'][0]['start'] = 99
        merged['rejected'][0]['reason'] = 'invalid_candidate'
        self.assertEqual((first, second), before)

    def test_invalid_positions_and_rejections_fail_instead_of_disappearing(self):
        for candidate in ({'id': 'C000', 'start': -1, 'end': 1},
                          {'id': 'C000', 'start': False, 'end': 1},
                          {'id': 'C000', 'start': 0, 'end': 2}):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                _merge_occurrences('A', {'candidates': [candidate], 'rejected': []})
        with self.assertRaises(ValueError):
            _merge_occurrences('A', {'candidates': [], 'rejected': [
                {'index': 0, 'reason': 'not_a_reason'}]})
        with self.assertRaises(ValueError):
            _merge_occurrences('A')

    def test_union_limit_rejects_without_silent_truncation(self):
        first = {'candidates': [{'id': f'C{i:03}', 'start': i, 'end': i + 1}
                                for i in range(240)], 'rejected': []}
        last = {'candidates': [{'id': 'C000', 'start': 240, 'end': 241}],
                'rejected': []}
        self.assertEqual(len(_merge_occurrences('A' * 241, first)['candidates']), 240)
        with self.assertRaises(ValueError):
            _merge_occurrences('A' * 241, first, last)


class CandidateReviewApplicationTests(unittest.TestCase):
    def setUp(self):
        self.frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 1},
                                      {'id': 'C001', 'start': 2, 'end': 3}],
                       'rejected': []}
        self.labels = [{'id': 'C000', 'field': 'features', 'status': 'confirmed'},
                       {'id': 'C001', 'field': 'backend', 'status': 'tentative'}]
        self.review = {'checkedFields': list(FIELDS), 'missingFields': ['domain'],
                       'wrongCandidateIds': ['C000']}

    def test_only_rejected_status_changes_and_all_output_labels_are_copies(self):
        before = deepcopy((self.frozen, self.labels, self.review))
        result = apply_candidate_review(self.frozen, self.labels, self.review)
        self.assertEqual(result, [
            {'id': 'C000', 'field': 'features', 'status': 'irrelevant'},
            {'id': 'C001', 'field': 'backend', 'status': 'tentative'}])
        result[0]['field'] = 'other'
        result[1]['status'] = 'confirmed'
        self.assertEqual((self.frozen, self.labels, self.review), before)

    def test_incomplete_duplicate_or_foreign_review_never_applies(self):
        mutations = [('checkedFields', list(FIELDS)[:-1]),
                     ('checkedFields', list(reversed(FIELDS))),
                     ('missingFields', ['domain', 'domain']),
                     ('missingFields', ['other']),
                     ('wrongCandidateIds', ['C000', 'C000']),
                     ('wrongCandidateIds', ['C999']),
                     ('wrongCandidateIds', 'C000')]
        for key, value in mutations:
            review = {**self.review, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                apply_candidate_review(self.frozen, self.labels, review)
        for review in (None, {}, {**self.review, 'extra': True}):
            with self.subTest(review=review), self.assertRaises(ValueError):
                apply_candidate_review(self.frozen, self.labels, review)

    def test_invalid_input_labels_cannot_be_sanitized_by_review(self):
        with self.assertRaises(ValueError):
            apply_candidate_review(self.frozen, self.labels[:1], self.review)


if __name__ == '__main__':
    unittest.main()
