"""Fixed model replies, real SDK + request child + HTTP; no external network."""
import json
from pathlib import Path
import unittest

from test_integrated_service import Provider, service, send


CASES = json.loads((Path(__file__).parents[1] / 'tests/fixtures/mention_role_cases.json').read_text(encoding='utf-8'))['cases']


class RoleProvider(Provider):
    def __init__(self, case):
        super().__init__()
        self.case = case
        self.document = case['document']
        self.facts = [(self.document[c['start']:c['end']], g['field'] if g['constraint'] == 'positive'
                       else 'external_integrations') for c, g in zip(case['frozen']['candidates'], case['gold'])]

    def reply(self, payload):
        if payload['response_format']['json_schema']['name'] == 'agentfit_langextract_candidates':
            self.names.append('agentfit_langextract_candidates')
            chunk = payload['messages'][1]['content']
            return {'extractions': [{'candidate': value, 'candidate_attributes': {'anchor': value}}
                                    for value, _ in self.facts if value in chunk]}
        if payload['response_format']['json_schema']['name'] == 'agentfit_candidate_labels':
            body = super().reply(payload)
            unclear = {self.document[c['start']:c['end']] for c, g in
                       zip(self.case['frozen']['candidates'], self.case['gold']) if g['constraint'] == 'hold'}
            data = json.loads(payload['messages'][1]['content'])
            for label, candidate in zip(body['labels'], data['candidates']):
                if candidate['value'] in unclear:
                    label.update(field='other', status='tentative')
            return body
        if payload['response_format']['json_schema']['name'] != 'agentfit_semantic_assessment':
            return super().reply(payload)
        self.names.append('agentfit_semantic_assessment')
        data = json.loads(payload['messages'][1]['content'])
        by_span = {(c['start'], c['end']): g for c, g in zip(self.case['frozen']['candidates'], self.case['gold'])}
        rows = []
        for candidate in data['candidates']:
            gold = by_span[(candidate['start'], candidate['end'])]
            start = self.document.rfind('\n', 0, candidate['start']) + 1
            end = self.document.find('\n', candidate['end'])
            quote = self.document[start:end if end >= 0 else len(self.document)]
            occurrence = sum(self.document.startswith(quote, p) for p in range(start))
            rows.append({'id': candidate['id'], 'mentionKind': gold['kind'],
                'field': gold['field'] if gold['constraint'] in ('positive', 'hold') else 'external_integrations',
                'modelStatus': 'confirmed', 'scope': 'target', 'time': 'current', 'polarity': 'positive',
                'commitment': 'adopted', 'role': 'product_fact', 'conflictsChecked': True,
                'support': [{'quote': quote, 'occurrence': occurrence}], 'counterEvidence': []})
        return {'assessments': rows}


class RoleServiceTests(unittest.TestCase):
    def test_all_regressions_preserve_normal_facts_and_hold_wrong_roles_through_real_http(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                provider = RoleProvider(case)
                with service(provider, analysis_mode='integrated-nvidia') as (_, url, processes):
                    response = send(url, case['document'])
                    self.assertEqual(response.status_code, 200, response.text)
                    result = response.json()
                    self.assertEqual(result['contract'], 'confirmation-v2')
                    self.assertEqual(result['outcome'], 'needs_confirmation')
                    self.assertIn('modelDecisions', result)
                    by_span = {(r['candidate']['start'], r['candidate']['end']): r for r in result['modelDecisions']}
                    self.assertEqual(len(by_span), len(case['gold']))
                    for candidate, gold in zip(case['frozen']['candidates'], case['gold']):
                        record = by_span[(candidate['start'], candidate['end'])]
                        positive = gold['constraint'] == 'positive'
                        self.assertEqual(record['decision'], 'supported' if positive else 'needs_confirmation')
                        self.assertEqual(record['sourceValue'], case['document'][candidate['start']:candidate['end']])
                        if positive:
                            self.assertIn(record['sourceValue'], result['profile']['data'][gold['field']])
                        elif gold['constraint'] == 'hold':
                            self.assertIn(record['id'], result['unassignedQuestions'][0]['candidateIds'])
                        else:
                            self.assertIn('confirm_external_integrations', [q['questionId'] for q in result['questions']])
                    self.assertEqual(provider.errors, [])
                    self.assertEqual(processes[0].returncode, 0)


if __name__ == '__main__': unittest.main()
