"""Role/field consistency, not word lists, limits model confirmations."""
import unittest
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agentfit_ai.candidate_semantic_assessment import validate_assessments, semantic_labels, classify_grounded_candidates
from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.semantic_confirmation_metadata import unresolved_decision_fields
from agentfit_ai.profile import FIELDS
from agentfit_ai.candidate_analysis_pipeline import analyze_integrated_candidates
from test_candidate_feature_curation import response


def row(kind, field='external_integrations', **changes):
    return dict({'id': 'C017', 'field': field, 'mentionKind': kind, 'modelStatus': 'confirmed',
        'scope': 'target', 'time': 'current', 'polarity': 'positive', 'commitment': 'adopted',
        'role': 'product_fact', 'conflictsChecked': True, 'support': [{'quote': 'Term', 'occurrence': 0}],
        'counterEvidence': []}, **changes)


FROZEN = {'candidates': [{'id': 'C017', 'start': 0, 'end': 4}], 'rejected': []}


class MentionRoleTests(unittest.TestCase):
    def test_wrong_field_or_ambiguous_role_is_preserved_without_confirmation(self):
        for kind, field in [('product_operation', 'external_integrations'),
                            ('external_service', 'features'), ('role_description', 'external_integrations'),
                            ('role_description', 'domain'), ('description', 'features'),
                            ('unclear', 'other'), ('other', 'features')]:
            with self.subTest(kind=kind, field=field):
                records = validate_assessments('Term', FROZEN, [row(kind, field)])
                self.assertEqual(records[0]['decision'], 'needs_confirmation')
                self.assertEqual(records[0]['modelStatus'], 'confirmed')
                self.assertEqual(records[0]['mentionKind'], kind)

    def test_normal_provider_operation_and_unrelated_technology_remain_supported(self):
        for kind, field in [('external_service', 'external_integrations'),
                            ('product_operation', 'features'), ('other', 'frontend')]:
            with self.subTest(kind=kind):
                self.assertEqual(validate_assessments('Term', FROZEN, [row(kind, field)])[0]['decision'], 'supported')

    def test_names_and_ids_cannot_decide_role(self):
        for value in ('Stripe', 'Payments', 'Meridia', '결제', 'ExternalProvider'):
            for candidate_id in ('C001', 'C139'):
                frozen = {'candidates': [{'id': candidate_id, 'start': 0, 'end': len(value)}], 'rejected': []}
                for kind, want in [('external_service', 'supported'), ('role_description', 'needs_confirmation')]:
                    record = row(kind, id=candidate_id, support=[{'quote': value, 'occurrence': 0}])
                    self.assertEqual(validate_assessments(value, frozen, [record])[0]['decision'], want)

    def test_ambiguous_candidates_keep_exact_source_and_question(self):
        for field in ('external_integrations', 'other'):
            records = validate_assessments('Term', FROZEN, [row('unclear', field)])
            result = finalize_candidate_analysis('Term', 'DOC', FROZEN, semantic_labels(records),
                {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
            result.update(modelDecisions=records, outcome='needs_confirmation', reviewIssueCount=1,
                          unresolvedFields=[f for f in FIELDS if f in unresolved_decision_fields(records)])
            draft = project_candidate_confirmation('Term', 'DOC', result)
            self.assertEqual(draft['modelDecisions'][0]['sourceValue'], 'Term')
            self.assertEqual(len(draft['questions']) + len(draft.get('unassignedQuestions', [])), 1)
            self.assertIsNone(draft['profile']['data']['external_integrations'])

    def test_old_records_remain_readable_but_new_provider_responses_need_a_role(self):
        old = row('external_service'); old.pop('mentionKind')
        self.assertEqual(validate_assessments('Term', FROZEN, [old])[0]['decision'], 'supported')
        def transport(payload, key, timeout):
            return response({'assessments': [old]}, model=payload['model'])
        with self.assertRaises(ValueError):
            classify_grounded_candidates('Term', FROZEN, 'test-key', transport=transport)

    def test_pipeline_preserves_ambiguous_source_and_question_alongside_normal_service(self):
        document = 'The product integrates Stripe. Relay is mentioned without a stated role.'
        for field in ('external_integrations', 'other'):
            def transport(payload, key, timeout):
                name = payload['response_format']['json_schema']['name']
                if name == 'agentfit_operation_candidates':
                    body = {'mentions': []}
                elif name == 'agentfit_semantic_assessment':
                    body = {'assessments': [
                        row('external_service', id='C000', support=[{'quote': document, 'occurrence': 0}]),
                        row('unclear', field, id='C001', support=[{'quote': document, 'occurrence': 0}])]}
                else:
                    raise AssertionError(name)
                return response(body, model=payload['model'])
            # The independent reviewer is fixed; classification, projection and
            # confirmation run normally, without manually patching their result.
            review = {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []}
            with self.subTest(field=field), patch(
                    'agentfit_ai.candidate_analysis_pipeline.review_candidates_separately', return_value=review):
                result = analyze_integrated_candidates(document, 'DOC', None, 'test-key',
                    candidate_model='deepseek-ai/deepseek-v4.1-flash', nvidia_retry_limit=0,
                    semantic_assessment=True, nvidia_transport=transport,
                    extractor=lambda *a, **k: [SimpleNamespace(extraction_class='candidate', extraction_text=value)
                                              for value in ('Stripe', 'Relay')])
                draft = project_candidate_confirmation(document, 'DOC', result)
                self.assertEqual(draft['profile']['data']['external_integrations'], ['Stripe'])
                self.assertEqual(draft['modelDecisions'][0]['decision'], 'supported')
                held = draft['modelDecisions'][1]
                self.assertEqual((held['sourceValue'], held['mentionKind'], held['modelStatus'], held['decision']),
                                 ('Relay', 'unclear', 'confirmed', 'needs_confirmation'))
                if field == 'other':
                    self.assertEqual(draft['unassignedQuestions'][0]['candidateIds'], ['C001'])
                else:
                    self.assertEqual(draft['fieldStates'][field], 'unresolved')
                    self.assertEqual(draft['questions'][0]['reason'], 'REVIEW_ISSUE')

    def test_invalid_role_or_extra_approval_cannot_enter_records(self):
        for changes in ({'mentionKind': 'service_because_capitalized'}, {'mentionKind': None},
                        {'userConfirmed': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_assessments('Term', FROZEN, [dict(row('external_service'), **changes)])

    def test_same_relation_with_renamed_reordered_and_normal_mentions(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/mention_role_cases.json').read_text(encoding='utf-8'))['cases']
        for case in cases:
            for gold, candidate in zip(case['gold'], case['frozen']['candidates']):
                with self.subTest(case=case['id'], candidate=gold['id']):
                    value = case['document'][candidate['start']:candidate['end']]
                    positive = gold['constraint'] == 'positive'
                    reply = row(gold['kind'], gold['field'] if positive else 'external_integrations',
                        id=gold['id'], support=[{'quote': case['document'], 'occurrence': 0}])
                    # Keep a bounded exact contextual quote for the full real README.
                    if len(case['document']) > 2000:
                        line_start = case['document'].rfind('\n', 0, candidate['start']) + 1
                        line_end = case['document'].find('\n', candidate['end'])
                        reply['support'] = [{'quote': case['document'][line_start:line_end], 'occurrence': 0}]
                    records = validate_assessments(case['document'], {'candidates': [candidate], 'rejected': []}, [reply])
                    self.assertEqual(records[0]['decision'], 'supported' if positive else 'needs_confirmation')
                    self.assertEqual(case['document'][records[0]['candidate']['start']:records[0]['candidate']['end']], value)


if __name__ == '__main__': unittest.main()
