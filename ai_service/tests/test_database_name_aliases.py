"""Source-preserving DB alias projection, including saved model decisions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.candidate_first_profile import project_candidate_profile, finalize_candidate_analysis
from agentfit_ai.candidate_semantic_assessment import validate_assessments, semantic_labels
from agentfit_ai.profile import FIELDS, check_profile_snapshot


FIXTURE = Path(__file__).parent / 'fixtures/database_name_aliases.json'
# Independent expected outcomes; do not derive gold with the alias implementation.
CASES = [
    ('plain_alias', ['Postgres', 'PostgreSQL'], 'Postgres'),
    ('canonical_first', ['PostgreSQL', 'Postgres'], 'PostgreSQL'),
    ('case', ['POSTGRESQL', 'postgres'], 'POSTGRESQL'),
    ('description', ['Postgres SQL Database', 'postgres database'], 'Postgres SQL Database'),
    ('spaces_and_db', ['Postgres  SQL DB', 'PostgreSQL'], 'Postgres  SQL DB'),
    ('same_major', ['Postgres 16', 'PostgreSQL 16'], 'Postgres 16'),
    ('same_minor', ['PostgreSQL v16.1 Database', 'Postgres 16.1'], 'PostgreSQL v16.1 Database'),
    ('identical_other_database', ['MySQL', 'MySQL'], 'MySQL'),
    ('different_major', ['Postgres 15', 'PostgreSQL 16'], None),
    ('different_minor', ['Postgres 16.1', 'PostgreSQL 16.2'], None),
    ('version_precision', ['Postgres 16', 'PostgreSQL 16.0'], None),
    ('version_unknown', ['Postgres', 'PostgreSQL 16'], None),
    ('version_range', ['Postgres >=16', 'PostgreSQL 16'], None),
    ('version_latest', ['Postgres latest', 'PostgreSQL'], None),
    ('version_leading_zero', ['Postgres 016', 'PostgreSQL 16'], None),
    ('other_database', ['Postgres', 'MySQL'], None),
    ('fork', ['MySQL', 'MariaDB'], None),
    ('compatible', ['Postgres', 'PostgreSQL-compatible'], None),
    ('managed_variant', ['Aurora PostgreSQL', 'PostgreSQL'], None),
    ('separate_product', ['CockroachDB', 'Postgres'], None),
    ('compound', ['Postgres / MySQL', 'PostgreSQL'], None),
    ('unknown_alias', ['PG', 'Postgres'], None),
    ('other_version_product', ['SQLite', 'SQLite3'], None),
    ('deployment_qualifier', ['self-hosted PostgreSQL', 'Postgres'], None),
    ('planned_text', ['planned PostgreSQL', 'Postgres'], None),
    ('negative_text', ['not PostgreSQL', 'Postgres'], None),
]


def inputs(values, *, field='database', statuses=None):
    document = '\n'.join(values)
    frozen = {'candidates': [], 'rejected': []}
    labels = []
    start = 0
    for i, value in enumerate(values):
        identity = f'C{i:03}'
        frozen['candidates'].append({'id': identity, 'start': start, 'end': start + len(value)})
        labels.append({'id': identity, 'field': field, 'status': statuses[i] if statuses else 'confirmed'})
        start += len(value) + 1
    return document, frozen, labels


class DatabaseNameAliasTests(unittest.TestCase):
    def test_saved_response_restores_database_with_its_original_evidence(self):
        fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        before = deepcopy(fixture)
        result = project_candidate_profile(fixture['document'], fixture['documentId'],
            fixture['frozen'], fixture['labels'], coverage_verified=True)
        self.assertEqual(result['profile']['data']['database'], 'Postgres SQL Database')
        self.assertNotIn('database', result['unresolvedFields'])
        self.assertEqual(result['outcome'], 'candidate_profile')
        self.assertEqual(check_profile_snapshot(fixture['document'], fixture['documentId'], result['profile']), result['profile'])
        self.assertEqual(fixture, before)
        spans = result['profile']['evidence']['database']
        self.assertEqual([fixture['document'][s['start']:s['end']] for s in spans], ['Postgres SQL Database'])

    def test_aliases_merge_but_versions_and_different_products_do_not(self):
        for name, values, expected in CASES:
            with self.subTest(case=name):
                document, frozen, labels = inputs(values)
                result = project_candidate_profile(document, 'DOC', frozen, labels, coverage_verified=True)
                self.assertEqual(result['profile']['data']['database'], expected)
                self.assertEqual('database' in result['unresolvedFields'], expected is None)
                self.assertEqual(result['outcome'], 'needs_confirmation' if expected is None else 'candidate_profile')
                self.assertEqual(check_profile_snapshot(document, 'DOC', result['profile']), result['profile'])

    def test_candidate_order_does_not_change_source_representative(self):
        document, frozen, labels = inputs(['PostgreSQL', 'Postgres', 'PostgreSQL'])
        frozen['candidates'].reverse()
        labels.reverse()
        result = project_candidate_profile(document, 'DOC', frozen, labels, coverage_verified=True)
        self.assertEqual(result['profile']['data']['database'], 'PostgreSQL')
        self.assertEqual(len(result['profile']['evidence']['database']), 2)

    def test_version_omitted_from_candidate_does_not_license_alias_merge(self):
        for document in ('Postgres 15\nPostgreSQL 16', 'Postgres (15)\nPostgreSQL (16)',
                         'Postgres v15\nPostgreSQL v16', 'Postgres >=15\nPostgreSQL 16',
                         'Postgres version 15\nPostgreSQL version 16',
                         '**Postgres** 15\n**PostgreSQL** 16',
                         'Postgres\nPostgreSQL-compatible', 'xPostgres\nPostgreSQL',
                         'Primary: Aurora PostgreSQL. Reporting: Postgres.',
                         'Primary: Amazon RDS for PostgreSQL. Reporting: Postgres.'):
            with self.subTest(document=document):
                frozen = {'candidates': [{'id': f'C{i:03}', 'start': document.index(name),
                                         'end': document.index(name) + len(name)}
                                        for i, name in enumerate(('Postgres', 'PostgreSQL'))], 'rejected': []}
                labels = [{'id': c['id'], 'field': 'database', 'status': 'confirmed'} for c in frozen['candidates']]
                result = project_candidate_profile(document, 'DOC', frozen, labels, coverage_verified=True)
                self.assertIsNone(result['profile']['data']['database'])
                self.assertIn('database', result['unresolvedFields'])

    def test_sentence_punctuation_is_not_a_version_or_token_suffix(self):
        document = 'Uses Postgres. Also uses (PostgreSQL).'
        frozen = {'candidates': [{'id': f'C{i:03}', 'start': document.index(name),
                                 'end': document.index(name) + len(name)}
                                for i, name in enumerate(('Postgres', 'PostgreSQL'))], 'rejected': []}
        labels = [{'id': c['id'], 'field': 'database', 'status': 'confirmed'} for c in frozen['candidates']]
        result = project_candidate_profile(document, 'DOC', frozen, labels, coverage_verified=True)
        self.assertEqual(result['profile']['data']['database'], 'Postgres')

    def test_same_start_candidates_choose_the_fullest_source_spelling(self):
        document = 'Postgres SQL Database'
        candidates = [{'id': 'C000', 'start': 0, 'end': 8}, {'id': 'C001', 'start': 0, 'end': len(document)}]
        labels = [{'id': c['id'], 'field': 'database', 'status': 'confirmed'} for c in candidates]
        for ordered in (candidates, list(reversed(candidates))):
            result = project_candidate_profile(document, 'DOC', {'candidates': ordered, 'rejected': []},
                                               labels, coverage_verified=True)
            self.assertEqual(result['profile']['data']['database'], 'Postgres SQL Database')

    def test_every_occurrence_is_checked_for_an_omitted_version(self):
        document = 'Postgres\nPostgres 16\nPostgreSQL'
        frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 8},
                                {'id': 'C001', 'start': 9, 'end': 17},
                                {'id': 'C002', 'start': 21, 'end': 31}], 'rejected': []}
        labels = [{'id': c['id'], 'field': 'database', 'status': 'confirmed'} for c in frozen['candidates']]
        result = project_candidate_profile(document, 'DOC', frozen, labels, coverage_verified=True)
        self.assertIsNone(result['profile']['data']['database'])
        self.assertIn('database', result['unresolvedFields'])

    def test_other_fields_and_unconfirmed_candidates_are_not_normalized_or_promoted(self):
        document, frozen, labels = inputs(['Postgres', 'PostgreSQL'], field='backend')
        result = project_candidate_profile(document, 'DOC', frozen, labels, coverage_verified=True)
        self.assertEqual(result['profile']['data']['backend'], ['Postgres', 'PostgreSQL'])
        for status in ('tentative', 'negated', 'irrelevant'):
            with self.subTest(status=status):
                document, frozen, labels = inputs(['Postgres', 'PostgreSQL'], statuses=[status, status])
                result = project_candidate_profile(document, 'DOC', frozen, labels, coverage_verified=True)
                self.assertIsNone(result['profile']['data']['database'])

    def test_existing_review_obligation_is_not_cleared_by_alias_merge(self):
        document, frozen, labels = inputs(['Postgres', 'PostgreSQL'])
        result = finalize_candidate_analysis(document, 'DOC', frozen, labels,
            {'checkedFields': list(FIELDS), 'missingFields': ['database'], 'wrongCandidateIds': []})
        draft = project_candidate_confirmation(document, 'DOC', result)
        self.assertEqual(draft['profile']['data']['database'], 'Postgres')
        self.assertEqual(draft['fieldStates']['database'], 'unresolved')
        self.assertEqual(draft['questions'], [{'field': 'database', 'reason': 'REVIEW_ISSUE', 'questionId': 'confirm_database'}])

    def test_alias_records_survive_confirmation_without_becoming_user_approval(self):
        document, frozen, _ = inputs(['Postgres', 'PostgreSQL'])
        assessments = [dict(id=c['id'], field='database', modelStatus='confirmed', mentionKind='other',
            scope='target', time='current', polarity='positive', commitment='adopted', role='product_fact',
            conflictsChecked=True, support=[{'quote': document[c['start']:c['end']], 'occurrence': 0}],
            counterEvidence=[]) for c in frozen['candidates']]
        records = validate_assessments(document, frozen, assessments)
        result = finalize_candidate_analysis(document, 'DOC', frozen, semantic_labels(records),
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
        result['modelDecisions'] = records
        original = deepcopy(result)
        draft = project_candidate_confirmation(document, 'DOC', result)
        self.assertEqual(draft['profile']['data']['database'], 'Postgres')
        self.assertEqual([r['sourceValue'] for r in draft['modelDecisions']], ['Postgres', 'PostgreSQL'])
        self.assertEqual([r['decision'] for r in draft['modelDecisions']], ['supported', 'supported'])
        self.assertEqual(draft['fieldStates']['database'], 'suggested')
        self.assertEqual(draft['questions'], [{'field': 'database', 'reason': 'CONFIRM_SUGGESTION', 'questionId': 'confirm_database'}])
        self.assertEqual(draft['outcome'], 'needs_confirmation')
        self.assertEqual(result, original)


if __name__ == '__main__':
    unittest.main()
