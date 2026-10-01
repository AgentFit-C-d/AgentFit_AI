"""Semantic support and human approval are different assertions."""
from copy import deepcopy
import json
import unittest

from agentfit_ai.candidate_semantic_assessment import validate_assessments, semantic_labels
from agentfit_ai.candidate_semantic_assessment import classify_grounded_candidates
from agentfit_ai.solar import AnalysisError
from test_candidate_feature_curation import response


DOCUMENT = 'Cedar uses React for its web client. Cedar does not use Redis. Redis is under review.'
FROZEN = {'candidates': [{'id': 'C000', 'start': 11, 'end': 16}], 'rejected': []}


def assessment(**changes):
    row = {'id': 'C000', 'field': 'frontend', 'modelStatus': 'confirmed',
           'scope': 'target', 'time': 'current', 'polarity': 'positive',
           'commitment': 'adopted', 'role': 'product_fact', 'conflictsChecked': True,
           'support': [{'quote': 'Cedar uses React for its web client.', 'occurrence': 0}],
           'counterEvidence': []}
    return dict(row, **changes)


class SemanticGuardTests(unittest.TestCase):
    def test_supported_fact_remains_model_confirmed_but_never_user_confirmed(self):
        rows = validate_assessments(DOCUMENT, FROZEN, [assessment()])
        self.assertEqual(rows[0]['decision'], 'supported')
        self.assertEqual(rows[0]['modelStatus'], 'confirmed')
        self.assertNotIn('userConfirmed', rows[0])
        self.assertEqual(semantic_labels(rows), [{'id': 'C000', 'field': 'frontend', 'status': 'confirmed'}])

    def test_unsupported_or_conflicting_model_confirmed_is_held_not_promoted(self):
        for changes in ({'scope': 'unclear'}, {'time': 'unclear'}, {'polarity': 'unclear'},
                        {'commitment': 'unclear'}, {'role': 'unclear'}, {'support': []},
                        {'conflictsChecked': False},
                        {'counterEvidence': [{'quote': 'Cedar does not use Redis.', 'occurrence': 0}]},
                        {'support': [{'quote': 'React', 'occurrence': 9}]},
                        {'support': [{'quote': 'Redis', 'occurrence': 0}]}):
            with self.subTest(changes=changes):
                rows = validate_assessments(DOCUMENT, FROZEN, [assessment(**changes)])
                self.assertEqual(rows[0]['decision'], 'needs_confirmation')
                self.assertEqual(semantic_labels(rows)[0]['status'], 'tentative')

    def test_clear_negative_scope_or_proposal_is_not_a_current_fact(self):
        for changes in ({'scope': 'other'}, {'time': 'historical'}, {'time': 'future'},
                        {'polarity': 'negative'}, {'commitment': 'proposed'},
                        {'role': 'non_product'}, {'field': 'other', 'role': 'non_product'}):
            with self.subTest(changes=changes):
                rows = validate_assessments(DOCUMENT, FROZEN, [assessment(**changes)])
                self.assertNotEqual(semantic_labels(rows)[0]['status'], 'confirmed')

    def test_model_not_confirmed_is_never_promoted_by_positive_axes(self):
        for status in ('tentative', 'irrelevant', 'negated'):
            rows = validate_assessments(DOCUMENT, FROZEN, [assessment(modelStatus=status)])
            self.assertNotEqual(semantic_labels(rows)[0]['status'], 'confirmed')

    def test_proven_out_of_domain_item_does_not_require_deciding_its_adoption(self):
        row = assessment(field='other', role='non_product', modelStatus='irrelevant', commitment='unclear')
        self.assertEqual(validate_assessments(DOCUMENT, FROZEN, [row])[0]['decision'], 'excluded')
        for changes in ({'support': []}, {'role': 'unclear'}, {'modelStatus': 'confirmed'},
                        {'field': 'features'}, {'conflictsChecked': False},
                        {'counterEvidence': [{'quote': DOCUMENT, 'occurrence': 0}]}):
            with self.subTest(changes=changes):
                checked = validate_assessments(DOCUMENT, FROZEN, [dict(row, **changes)])
                self.assertEqual(checked[0]['decision'], 'needs_confirmation')

    def test_duplicate_missing_foreign_ids_and_forged_approval_fail(self):
        for rows in ([], [assessment(), assessment()], [assessment(id='C999')],
                     [assessment(userConfirmed=True)], [assessment(conflictsChecked=1)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_assessments(DOCUMENT, FROZEN, rows)

    def test_repeated_support_must_cover_the_selected_occurrence(self):
        document = 'React. React.'
        frozen = {'candidates': [{'id': 'C057', 'start': 7, 'end': 12}], 'rejected': []}
        row = assessment(id='C057', support=[{'quote': 'React.', 'occurrence': 0}])
        self.assertEqual(validate_assessments(document, frozen, [row])[0]['decision'], 'needs_confirmation')
        row['support'][0]['occurrence'] = 1
        before = deepcopy(row)
        result = validate_assessments(document, frozen, [row])[0]
        self.assertEqual(result['decision'], 'supported')
        self.assertEqual(result['support'], [{'start': 7, 'end': 13}])
        self.assertEqual(row, before)

    def test_last_batch_failure_never_returns_partial_confirmations(self):
        document = '\n'.join('Client uses React.' for _ in range(9))
        frozen = {'candidates': [{'id': f'C{i:03}', 'start': i * 19 + 12, 'end': i * 19 + 17}
                                 for i in range(9)], 'rejected': []}
        for defect in ('missing', 'duplicate', 'provider'):
            calls = []
            def transport(payload, key, timeout):
                candidates = json.loads(payload['messages'][1]['content'])['candidates']
                calls.append(len(candidates))
                rows = [assessment(id=r['id'], support=[{'quote': 'Client uses React.',
                      'occurrence': r['start'] // 19}]) for r in candidates]
                if len(calls) == 2:
                    if defect == 'provider': raise AnalysisError('PROVIDER_RATE_LIMIT')
                    if defect == 'missing': rows = []
                    if defect == 'duplicate': rows += rows
                return response({'assessments': rows}, model=payload['model'])
            with self.subTest(defect=defect), self.assertRaises((ValueError, AnalysisError)):
                classify_grounded_candidates(document, frozen, 'test-key', transport=transport)
            self.assertEqual(calls, [8, 1])

    def test_relabeling_ids_does_not_change_server_decisions(self):
        for candidate_id in ('C000', 'C077', 'C239'):
            frozen = deepcopy(FROZEN); frozen['candidates'][0]['id'] = candidate_id
            for role, expected in [('product_fact', 'supported'), ('non_product', 'excluded')]:
                row = assessment(id=candidate_id, role=role)
                self.assertEqual(validate_assessments(DOCUMENT, frozen, [row])[0]['decision'], expected)


if __name__ == '__main__':
    unittest.main()
