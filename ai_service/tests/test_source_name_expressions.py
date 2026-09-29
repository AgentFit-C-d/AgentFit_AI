"""Preserve source-written names without making an alias certainty claim."""

from copy import deepcopy
from types import SimpleNamespace
import unittest

from agentfit_ai.candidate_first_profile import project_candidate_profile


def project(document, selections, *, field='project_name', coverage=True):
    candidates, labels = [], []
    for index, selection in enumerate(selections):
        value, start, status = selection
        candidate_id = f'C{index:03}'
        candidates.append({'id': candidate_id, 'start': start, 'end': start + len(value)})
        labels.append({'id': candidate_id, 'field': field, 'status': status})
    return project_candidate_profile(document, 'test', {'candidates': candidates, 'rejected': []},
                                     labels, coverage_verified=coverage)


class SourceNameExpressionTests(unittest.TestCase):
    def test_bilingual_source_name_keeps_full_literal_and_needs_confirmation(self):
        document = '🚀 제품명: Orbit (오빗). Orbit 출시.'
        result = project(document, [('Orbit', document.index('Orbit'), 'confirmed'),
                                    ('오빗', document.index('오빗'), 'confirmed'),
                                    ('Orbit', document.rindex('Orbit'), 'confirmed')])
        profile = result['profile']
        self.assertEqual(profile['data']['project_name'], 'Orbit (오빗)')
        self.assertEqual(profile['evidence']['project_name'], [
            {'documentId': 'test', 'start': document.index('Orbit'),
             'end': document.index('오빗') + len('오빗)')}])
        self.assertNotIn('project_name', profile['unknownFields'])
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertEqual(result['unresolvedFields'], ['project_name'])

    def test_reversed_fullwidth_and_spaced_forms_remain_source_exact(self):
        for expression in ('오빗（Orbit）', 'Orbit(오빗)', 'Orbit\t( 오빗 )'):
            with self.subTest(expression=expression):
                result = project(expression, [('Orbit', expression.index('Orbit'), 'confirmed'),
                                               ('오빗', expression.index('오빗'), 'confirmed')])
                self.assertEqual(result['profile']['data']['project_name'], expression)

    def test_whole_expression_candidates_and_spacing_variants_are_supported(self):
        document = 'Orbit (오빗). Orbit(오빗).'
        selections = [('Orbit', 0, 'confirmed'), ('오빗', 7, 'confirmed'),
                      ('Orbit (오빗)', 0, 'confirmed'),
                      ('Orbit', document.rindex('Orbit'), 'confirmed'),
                      ('오빗', document.rindex('오빗'), 'confirmed'),
                      ('Orbit(오빗)', document.rindex('Orbit'), 'confirmed')]
        result = project(document, selections)
        self.assertEqual(result['profile']['data']['project_name'], 'Orbit (오빗)')

    def test_third_name_and_non_alias_text_are_not_merged(self):
        for document, values in (
                ('Orbit (오빗), Nova.', ['Orbit', '오빗', 'Nova']),
                ('Orbit 또는 오빗', ['Orbit', '오빗']),
                ('Orbit\n(오빗)', ['Orbit', '오빗']),
                ('Orbit (후보: 오빗)', ['Orbit', '오빗']),
                ('Orbit（오빗)', ['Orbit', '오빗'])):
            with self.subTest(document=document):
                result = project(document, [(value, document.index(value), 'confirmed') for value in values])
                self.assertIsNone(result['profile']['data']['project_name'])
                self.assertEqual(result['unresolvedFields'], ['project_name'])

    def test_example_relationship_at_other_positions_cannot_resolve_current_names(self):
        document = '예시: Orbit(오빗). 현재: Orbit, 오빗.'
        result = project(document, [('Orbit', document.rindex('Orbit'), 'confirmed'),
                                    ('오빗', document.rindex('오빗'), 'confirmed')])
        self.assertIsNone(result['profile']['data']['project_name'])

    def test_unconfirmed_alias_is_not_added_and_other_scalars_are_unchanged(self):
        document = 'Orbit (오빗)'
        for status in ('negated', 'tentative', 'irrelevant'):
            result = project(document, [('Orbit', 0, 'confirmed'), ('오빗', 7, status)])
            self.assertEqual(result['profile']['data']['project_name'], 'Orbit')
            self.assertEqual(result['outcome'], 'candidate_profile')
        result = project(document, [('Orbit', 0, 'confirmed'), ('오빗', 7, 'confirmed')], field='database')
        self.assertIsNone(result['profile']['data']['database'])

    def test_combined_name_over_200_codepoints_is_left_unresolved(self):
        left, right = 'A' * 100, '가' * 100
        document = left + '(' + right + ')'
        result = project(document, [(left, 0, 'confirmed'), (right, 101, 'confirmed')])
        self.assertIsNone(result['profile']['data']['project_name'])

    def test_pure_resolver_rejects_forged_values_and_preserves_entries(self):
        from agentfit_ai.source_name_expressions import source_name_expression
        document = 'Orbit(오빗)'
        entries = [('Orbit', {'start': 0, 'end': 5}), ('오빗', {'start': 6, 'end': 8})]
        original = deepcopy(entries)
        self.assertEqual(source_name_expression(document, entries),
                         (document, {'start': 0, 'end': len(document)}))
        self.assertEqual(entries, original)
        with self.assertRaises(ValueError):
            source_name_expression(document, [('Nova', {'start': 0, 'end': 5})])

    def test_comparison_reports_preserved_expression_without_exposing_it(self):
        from agentfit_ai.candidate_paired_review import evaluate_paired
        from agentfit_ai.profile import FIELDS
        from agentfit_ai.real_document_holdout import PreparedCase
        document = 'Orbit(오빗)'
        case = PreparedCase('sample', document,
            [{'id': 'C01', 'field': 'project_name', 'contains_any': ['Orbit']}],
            'a' * 64, 'b' * 64, None, 0, 0)
        def extractor(*args, **kwargs):
            return [SimpleNamespace(extraction_class='candidate', extraction_text=value)
                    for value in ('Orbit', '오빗')]
        def classifier(document, frozen, key):
            return [{'id': item['id'], 'field': 'project_name', 'status': 'confirmed'}
                    for item in frozen['candidates']]
        result = evaluate_paired(case, 'solar-secret', 'nvidia-secret', ['solar-pro4'],
            extractor=extractor, classifier=classifier,
            reviewer=lambda *a, **k: {'checkedFields': list(FIELDS), 'missingFields': [],
                                      'wrongCandidateIds': []})
        row = result['models'][0]
        self.assertEqual(row['outcome'], 'needs_confirmation')
        self.assertEqual(row['suggestion_matched'], 1)
        self.assertEqual(row['fields']['project_name']['projection_reason'], 'source_name_expression')
        self.assertFalse(row['fields']['project_name']['projected_null'])
        self.assertNotIn(document, str(result))


if __name__ == '__main__':
    unittest.main()
