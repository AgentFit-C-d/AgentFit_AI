import importlib
import json
from types import SimpleNamespace
import unittest

from agentfit_ai.candidate_first_profile import analyze_candidate_first
from agentfit_ai.profile import FIELDS


def diagnostics(document, checks):
    try:
        module = importlib.import_module('agentfit_ai.candidate_stage_diagnostics')
    except ImportError:
        raise AssertionError('stage diagnostics are not implemented') from None
    return module.CandidateStageDiagnostics(document, checks)


class CandidateStageDiagnosticsTests(unittest.TestCase):
    def test_first_missing_stage_is_identified_without_source_values(self):
        source = 'Alpha secret-feature'
        checks = [{'id': 'C01', 'field': 'project_name', 'contains_any': ['Alpha']},
                  {'id': 'C02', 'field': 'features', 'contains_any': ['secret-feature']},
                  {'id': 'C03', 'field': 'database', 'contains_any': ['missing-db']}]
        trace = diagnostics(source, checks)
        frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 5},
                                 {'id': 'C001', 'start': 6, 'end': len(source)}], 'rejected': []}
        labels = [{'id': 'C000', 'field': 'project_name', 'status': 'confirmed'},
                  {'id': 'C001', 'field': 'features', 'status': 'confirmed'}]
        trace.observe('grounded', frozen)
        trace.observe('classified', {'frozen': frozen, 'labels': labels})
        trace.observe('reviewed', {'frozen': frozen, 'labels': [
            labels[0], {**labels[1], 'status': 'irrelevant'}]})
        trace.observe('projected', {'data': {'project_name': 'Alpha'}})
        rows = trace.summary()
        self.assertEqual([r['first_unmatched_stage'] for r in rows], ['none', 'reviewed', 'grounded'])
        self.assertTrue(rows[1]['classified'])
        self.assertFalse(rows[1]['reviewed'])
        for private in ('Alpha', 'secret-feature', 'missing-db', source):
            self.assertNotIn(private, json.dumps(rows))

    def test_null_and_unobserved_stages_are_not_scored_as_failures(self):
        trace = diagnostics('Alpha', [
            {'id': 'C01', 'field': 'project_name', 'contains_any': ['Alpha']},
            {'id': 'C02', 'field': 'database', 'expect_null': True}])
        trace.observe('grounded', {'candidates': [{'id': 'C000', 'start': 0, 'end': 5}], 'rejected': []})
        rows = trace.summary()
        self.assertIsNone(rows[0]['classified'])
        self.assertEqual(rows[0]['first_unmatched_stage'], 'unobserved')
        self.assertIsNone(rows[1]['grounded'])
        trace.observe('projected', {'data': {'project_name': 'Alpha', 'database': None}})
        rows = trace.summary()
        self.assertTrue(rows[1]['projected'])
        self.assertEqual(rows[1]['first_unmatched_stage'], 'none')

    def test_observer_cannot_mutate_profile_or_model_input(self):
        def extractor(source, key, **kwargs):
            return [SimpleNamespace(extraction_class='candidate', extraction_text='Alpha')]
        def transport(payload, key, timeout):
            self.assertNotIn('private-gold', json.dumps(payload))
            is_label = payload['response_format']['json_schema']['name'] == 'agentfit_candidate_labels'
            body = ({'labels': [{'id': 'C000', 'field': 'project_name', 'status': 'confirmed'}]}
                    if is_label else {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
            return json.dumps({'model': 'solar-pro4-260806', 'choices': [{
                'finish_reason': 'stop', 'message': {'content': json.dumps(body)}}]}).encode()
        observed = []
        def observer(stage, state):
            observed.append(stage)
            state.clear()
            state['private-gold'] = True
        result = analyze_candidate_first('Alpha', 'doc', 'fake-key',
            extractor=extractor, transport=transport, source_occurrences=True, observer=observer)
        self.assertEqual(result['outcome'], 'candidate_profile')
        self.assertEqual(result['profile']['data']['project_name'], 'Alpha')
        self.assertEqual(observed, ['grounded', 'classified', 'reviewed', 'projected'])


if __name__ == '__main__':
    unittest.main()
