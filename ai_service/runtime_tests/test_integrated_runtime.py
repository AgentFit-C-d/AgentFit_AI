"""Installed SDK smoke tests; no extractor replacement or external API calls."""

import json
import unittest

import langextract  # Required: a missing optional installation must fail this suite.

from agentfit_ai.candidate_analysis_pipeline import analyze_integrated_candidates
from agentfit_ai.candidate_first_profile import CandidatePipelineError, freeze_candidates
from agentfit_ai.langextract_solar_trial import extract_candidates


SOLAR_KEY, NVIDIA_KEY = 'unit-solar-secret', 'unit-nvidia-secret'
FIELDS = ['project_name', 'project_type', 'domain', 'frontend', 'backend', 'ai',
          'database', 'deployment', 'features', 'external_integrations']
FACTS = [('TestApp', 'project_name'), ('web app', 'project_type'), ('records', 'domain'),
         ('React', 'frontend'), ('Go', 'backend'), ('ModelX', 'ai'),
         ('SQLite', 'database'), ('CloudZ', 'deployment'), ('MailSvc', 'external_integrations'),
         ('기록 저장', 'features')]
DOCUMENT = '\n'.join(value for value, _ in FACTS)


def response(body, model):
    return json.dumps({'model': model, 'choices': [{
        'message': {'content': json.dumps(body, ensure_ascii=False)},
        'finish_reason': 'stop'}]}, ensure_ascii=False).encode('utf-8')


class ProviderTransport:
    """Replace only the remote generation, preserving real SDK/parser/projection."""
    def __init__(self, *, malformed=False):
        self.names = []
        self.malformed = malformed

    def __call__(self, payload, key, timeout):
        name = payload['response_format']['json_schema']['name']
        self.names.append(name)
        assert timeout == 600
        assert key == (SOLAR_KEY if payload['model'] == 'solar-pro4' else NVIDIA_KEY)
        if name == 'agentfit_langextract_candidates':
            assert payload['max_tokens'] == 8192
            assert DOCUMENT in payload['messages'][1]['content']
            if self.malformed:
                return b'not-json-unit-private-response'
            body = {'extractions': [{'candidate': value,
                'candidate_attributes': {'anchor': value}} for value, _ in FACTS]}
        else:
            data = json.loads(payload['messages'][1]['content'])
            if name == 'agentfit_operation_candidates':
                body = {'mentions': [{'quote': '기록 저장', 'anchor': '기록 저장'}]}
            elif name == 'agentfit_candidate_labels':
                fields = dict(FACTS)
                body = {'labels': [{'id': row['id'], 'field': fields[row['value']],
                                    'status': 'confirmed'} for row in data['candidates']]}
            elif name == 'agentfit_candidate_label_review':
                body = {'checkedCandidateIds': [r['id'] for r in data['selections']],
                        'wrongCandidateIds': [], 'rejectionReasons': []}
            elif name == 'agentfit_candidate_source_coverage':
                body = {'checkedFields': FIELDS, 'missingFields': []}
            else:
                raise AssertionError('unexpected provider schema')
        return response(body, payload['model'])

    def run(self, document=DOCUMENT, **options):
        return analyze_integrated_candidates(document, 'DOC', SOLAR_KEY, NVIDIA_KEY,
            solar_transport=self, nvidia_transport=self, **options)


class InstalledRuntimeTests(unittest.TestCase):
    def test_default_sdk_path_returns_grounded_ten_field_profile(self):
        provider, trace = ProviderTransport(), []
        result = provider.run(call_trace=trace)
        self.assertEqual(result['outcome'], 'candidate_profile')
        self.assertEqual(result['candidateCount'], 10)
        self.assertEqual(result['profile']['data'], {
            'project_name': 'TestApp', 'project_type': 'web app', 'domain': 'records',
            'frontend': ['React'], 'backend': ['Go'], 'ai': ['ModelX'],
            'database': 'SQLite', 'deployment': 'CloudZ',
            'features': ['기록 저장'], 'external_integrations': ['MailSvc']})
        self.assertEqual(result['profile']['evidence']['project_name'],
                         [{'documentId': 'DOC', 'start': 0, 'end': 7}])
        self.assertEqual(result['profile']['evidence']['features'],
                         [{'documentId': 'DOC', 'start': 62, 'end': 67}])
        self.assertEqual(provider.names, ['agentfit_langextract_candidates',
            'agentfit_operation_candidates', 'agentfit_candidate_labels',
            'agentfit_candidate_label_review', 'agentfit_candidate_source_coverage'])
        self.assertEqual([row['call_index'] for row in trace], [1, 2, 3, 4, 5])

    def test_sdk_preserves_repeated_quote_anchors_and_distinct_positions(self):
        calls = []
        def transport(payload, key, timeout):
            calls.append(payload['model'])
            self.assertEqual((key, timeout), (SOLAR_KEY, 600))
            return response({'extractions': [
                {'candidate': 'Y', 'candidate_attributes': {'anchor': 'Y 제안.'}},
                {'candidate': 'Y', 'candidate_attributes': {'anchor': 'Y 확정.'}},
            ]}, 'solar-pro4')
        items = extract_candidates('Y 제안.\nY 확정.', SOLAR_KEY, transport=transport)
        self.assertEqual([item.attributes for item in items],
                         [{'anchor': 'Y 제안.'}, {'anchor': 'Y 확정.'}])
        self.assertEqual(freeze_candidates('Y 제안.\nY 확정.', list(items)), {
            'candidates': [{'id': 'C000', 'start': 0, 'end': 1},
                           {'id': 'C001', 'start': 6, 'end': 7}], 'rejected': []})
        self.assertEqual(calls, ['solar-pro4'])

    def test_malformed_reply_fails_before_other_stages_without_raw_error(self):
        provider, trace = ProviderTransport(malformed=True), []
        with self.assertRaises(CandidatePipelineError) as caught:
            provider.run(call_trace=trace)
        self.assertEqual(caught.exception.stage, 'EXTRACTION_FAILED')
        self.assertEqual(str(caught.exception), 'EXTRACTION_FAILED')
        self.assertEqual(provider.names, ['agentfit_langextract_candidates'])
        self.assertEqual(len(trace), 1)
        self.assertNotIn('unit-private-response', json.dumps(trace))

    def test_sdk_chunking_obeys_shared_budget_before_second_transport(self):
        provider, trace = ProviderTransport(), []
        document = DOCUMENT + '\n' + ('설명 문장.\n' * 900)
        with self.assertRaises(CandidatePipelineError) as caught:
            provider.run(document, max_calls=1, call_trace=trace)
        self.assertEqual((caught.exception.stage, caught.exception.detail),
                         ('EXTRACTION_FAILED', 'CALL_BUDGET_EXCEEDED'))
        self.assertEqual(provider.names, ['agentfit_langextract_candidates'])
        self.assertEqual(len(trace), 1)


if __name__ == '__main__':
    unittest.main()
