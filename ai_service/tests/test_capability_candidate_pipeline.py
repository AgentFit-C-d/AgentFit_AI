"""Real candidate pipeline; only model generation uses deterministic responses."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_analysis_pipeline import analyze_integrated_candidates, analyze_nvidia_candidates
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from tests.test_candidate_split_review import response


MODEL = 'deepseek-ai/deepseek-v4.1-flash'
SOLAR, NVIDIA = 'unit-solar-secret', 'unit-nvidia-secret'


class Fixture:
    def __init__(self, quotes=None, *, fail=False):
        self.document = 'UnitApp\nCurrent: search.\nRejected: search.\nOther product: search.'
        self.quotes = ['search'] if quotes is None else quotes
        self.names, self.fail = [], fail

    def extractor(self, *args, **kwargs):
        return [SimpleNamespace(extraction_class='candidate', extraction_text='UnitApp')]

    def transport(self, payload, key, timeout):
        name = payload['response_format']['json_schema']['name']
        self.names.append(name)
        data = json.loads(payload['messages'][1]['content'])
        if name == 'agentfit_capability_quotes':
            if self.fail:
                raise AnalysisError('PROVIDER_UNAVAILABLE')
            body = {'quotes': self.quotes}
        elif name == 'agentfit_operation_candidates':
            body = {'mentions': [{'quote': 'search', 'anchor': 'Current: search.'}]}
        elif name == 'agentfit_candidate_labels':
            body = {'labels': [{'id': item['id'],
                'field': 'project_name' if item['value'] == 'UnitApp' else 'features',
                'status': {35: 'negated', 58: 'irrelevant'}.get(item['start'], 'confirmed')}
                for item in data['candidates']]}
        elif name == 'agentfit_candidate_label_review':
            body = {'checkedCandidateIds': [item['id'] for item in data['selections']],
                    'wrongCandidateIds': [], 'rejectionReasons': []}
        elif name == 'agentfit_candidate_source_coverage':
            body = {'checkedFields': list(FIELDS), 'missingFields': []}
        else:
            raise AssertionError('unexpected request')
        return response(body, model=payload['model'])

    def run(self, **options):
        return analyze_integrated_candidates(self.document, 'DOC', SOLAR, NVIDIA,
            extractor=self.extractor, solar_transport=self.transport, nvidia_transport=self.transport,
            **{'nvidia_retry_limit': 0, **options})


class CapabilityPipelineTests(unittest.TestCase):
    def test_each_context_is_classified_and_only_confirmed_occurrence_is_projected(self):
        case, events, calls = Fixture(), [], []
        result = case.run(capability_candidates=True, observer=lambda stage, state: events.append((stage, state)),
                          call_trace=calls)
        self.assertEqual(result['profile']['data']['features'], ['search'])
        self.assertEqual(result['profile']['evidence']['features'], [{'documentId': 'DOC', 'start': 17, 'end': 23}])
        self.assertEqual(result['candidateCount'], 4)
        self.assertEqual(events[0][1]['candidates'], [
            {'id': 'C000', 'start': 0, 'end': 7}, {'id': 'C001', 'start': 17, 'end': 23},
            {'id': 'C002', 'start': 35, 'end': 41}, {'id': 'C003', 'start': 58, 'end': 64}])
        self.assertEqual([item['status'] for item in events[1][1]['labels']],
                         ['confirmed', 'confirmed', 'negated', 'irrelevant'])
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[0]['stage'], 'OPERATION_EXTRACTION_FAILED')
        self.assertNotIn(NVIDIA, json.dumps(calls))

    def test_default_and_false_keep_existing_operation_path(self):
        for options in ({}, {'capability_candidates': False}):
            case = Fixture()
            result = case.run(**options)
            self.assertEqual(result['candidateCount'], 2)
            self.assertEqual(result['profile']['data']['features'], ['search'])
            self.assertEqual(case.names[0], 'agentfit_operation_candidates')

    def test_absent_quote_remains_visible_as_confirmation_requirement(self):
        result = Fixture(['search', 'not written here']).run(capability_candidates=True)
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertEqual(result['rejectedReasons'], {'source_quote_absent': 1})
        self.assertEqual(result['profile']['data']['features'], ['search'])

    def test_option_must_be_a_boolean_before_any_provider_call(self):
        for value in (None, 1, 'true', [], {}):
            case = Fixture()
            with self.subTest(value=value), self.assertRaises(ValueError):
                case.run(capability_candidates=value)
            self.assertEqual(case.names, [])

    def test_occurrence_overflow_is_reported_at_extraction_without_partial_profile(self):
        case, calls = Fixture(['A']), []
        case.document = 'A' * 241
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(capability_candidates=True, call_trace=calls)
        self.assertEqual((caught.exception.stage, caught.exception.detail),
                         ('OPERATION_EXTRACTION_FAILED', 'CANDIDATE_OCCURRENCE_LIMIT'))
        self.assertEqual(len(calls), 1)

    def test_provider_failure_has_no_fallback_and_stays_inside_existing_meter(self):
        case, calls = Fixture(fail=True), []
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(capability_candidates=True, call_trace=calls)
        self.assertEqual((caught.exception.stage, caught.exception.provider_code),
                         ('OPERATION_EXTRACTION_FAILED', 'PROVIDER_UNAVAILABLE'))
        self.assertEqual(len(calls), 1)
        self.assertEqual(case.names, ['agentfit_capability_quotes'])

    def test_shared_call_budget_blocks_classification_instead_of_bypassing_capability_call(self):
        case, calls = Fixture(), []
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(capability_candidates=True, max_calls=1, call_trace=calls)
        self.assertEqual((caught.exception.stage, caught.exception.detail),
                         ('CLASSIFICATION_FAILED', 'CALL_BUDGET_EXCEEDED'))
        self.assertEqual(len(calls), 1)

    def test_nvidia_wrapper_forwards_option_and_returns_same_source_evidence(self):
        case, calls = Fixture(), []
        with patch('agentfit_ai.langextract_solar_trial.extract_candidates', case.extractor):
            result = analyze_nvidia_candidates(case.document, 'DOC', NVIDIA, review_model=MODEL,
                nvidia_transport=case.transport, capability_candidates=True, call_trace=calls)
        self.assertEqual(result['candidateCount'], 4)
        self.assertEqual(result['profile']['data']['features'], ['search'])
        self.assertEqual(result['profile']['evidence']['features'], [{'documentId': 'DOC', 'start': 17, 'end': 23}])
        self.assertEqual({row['provider'] for row in calls}, {'nvidia'})
        self.assertTrue(all(row['attempt'] == 1 for row in calls))


if __name__ == '__main__':
    unittest.main()
