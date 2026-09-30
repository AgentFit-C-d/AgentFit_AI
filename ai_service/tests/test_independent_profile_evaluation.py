"""Scoring must preserve uncertainty, denominators and source provenance."""
from copy import deepcopy
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.profile import FIELDS, validate_profile

DOCUMENT = 'React ok. React removed. Vue. No AI.'


def gold_fixture():
    fields = {f: {'assessment': 'unspecified', 'units': []} for f in FIELDS}
    for f, ident, start, end in [('frontend', 'U001', 0, 5), ('backend', 'U002', 25, 28)]:
        fields[f] = {'assessment': 'enumerated', 'units': [
            {'id': ident, 'kind': 'present', 'spans': [{'start': start, 'end': end}]}]}
    return {'case_id': 'PUBLIC-01', 'source_sha256': hashlib.sha256(DOCUMENT.encode()).hexdigest(),
            'human_reviewed': False, 'fields': fields,
            'exclusions': [{'id': 'X001', 'fields': ['frontend'], 'reason': 'negated',
                            'spans': [{'start': 10, 'end': 15}]}], 'ambiguities': []}


def outcome_fixture(field=None, value=None, spans=None, document=DOCUMENT):
    data = dict.fromkeys(FIELDS)
    evidence = {f: [] for f in FIELDS}
    if field:
        data[field] = value
        evidence[field] = [{'start': s, 'end': e} for s, e in spans]
    profile = validate_profile(document, 'PUBLIC-01', {'data': data, 'evidence': evidence})
    return project_candidate_confirmation(document, 'PUBLIC-01', {
        'outcome': 'candidate_profile', 'profile': profile, 'unresolvedFields': [],
        'candidateCount': 2, 'rejectedCandidateCount': 0, 'rejectedReasons': {}, 'reviewIssueCount': 0})


class EvaluationTest(unittest.TestCase):
    def setUp(self):
        name = 'agentfit_ai.independent_profile_evaluation'
        self.assertIsNotNone(importlib.util.find_spec(name), 'independent evaluation API is not implemented')
        self.api = importlib.import_module(name)
        self.gold = gold_fixture()

    def score(self, outcome, gold=None, document=DOCUMENT):
        return self.api.score_confirmation(document, 'PUBLIC-01', gold or self.gold, outcome)

    def test_exact_registered_source_counts_once_without_raw_content(self):
        result = self.score(outcome_fixture('frontend', ['React'], [(0, 5)]))
        self.assertEqual(result['fields']['frontend'], {
            'assessment': 'enumerated', 'gold': 1, 'produced': 1, 'matched': 1,
            'missing': 0, 'known_wrong': 0, 'duplicates': 0, 'unassessed': 0})
        self.assertEqual(result['fields']['backend']['missing'], 1)
        self.assertEqual(result['items'][0]['occurrences'], [{'start': 0, 'end': 5}])
        self.assertEqual(result['items'][0]['unit_id'], 'U001')
        self.assertFalse(result['human_reviewed'])
        self.assertFalse(result['release_gate_passed'])
        self.assertNotIn('React', json.dumps(result))

    def test_duplicate_outputs_do_not_increase_recall(self):
        result = self.score(outcome_fixture('frontend', ['React', 'React'], [(0, 5)]))
        self.assertEqual(result['fields']['frontend']['matched'], 1)
        self.assertEqual(result['fields']['frontend']['duplicates'], 1)
        self.assertEqual(result['fields']['frontend']['produced'], 2)

    def test_repeated_positive_and_negative_in_broad_evidence_is_unassessed(self):
        result = self.score(outcome_fixture('frontend', ['React'], [(0, 24)]))
        self.assertEqual(result['fields']['frontend']['matched'], 0)
        self.assertEqual(result['fields']['frontend']['unassessed'], 1)
        self.assertEqual(result['fields']['frontend']['missing'], 1)

    def test_exclusion_position_is_known_wrong(self):
        result = self.score(outcome_fixture('frontend', ['React'], [(10, 15)]))
        self.assertEqual(result['fields']['frontend']['known_wrong'], 1)

    def test_explicitly_registered_wrong_role_is_known_wrong(self):
        self.gold['exclusions'].append({'id': 'X002', 'fields': ['frontend'], 'reason': 'wrong_role',
                                        'spans': [{'start': 25, 'end': 28}]})
        result = self.score(outcome_fixture('frontend', ['Vue'], [(25, 28)]))
        self.assertEqual(result['fields']['frontend']['known_wrong'], 1)
        self.assertEqual(result['fields']['backend']['missing'], 1)

    def test_registration_elsewhere_does_not_prove_semantic_wrong_role(self):
        result = self.score(outcome_fixture('frontend', ['Vue'], [(25, 28)]))
        self.assertEqual(result['fields']['frontend']['known_wrong'], 0)
        self.assertEqual(result['fields']['frontend']['unassessed'], 1)

    def test_partial_token_gets_no_substring_credit(self):
        result = self.score(outcome_fixture('frontend', ['Re'], [(0, 5)]))
        self.assertEqual(result['fields']['frontend']['matched'], 0)
        self.assertEqual(result['fields']['frontend']['unassessed'], 1)

    def test_compound_output_does_not_fill_multiple_units(self):
        result = self.score(outcome_fixture('frontend', [DOCUMENT[:28]], [(0, 28)]))
        self.assertEqual(result['fields']['frontend']['unassessed'], 1)
        self.assertEqual(sum(f['matched'] for f in result['fields'].values()), 0)

    def test_repeated_registered_aliases_of_same_unit_are_one_match(self):
        self.gold['exclusions'] = []
        self.gold['fields']['frontend']['units'][0]['spans'].append({'start': 10, 'end': 15})
        result = self.score(outcome_fixture('frontend', ['React'], [(0, 24), (0, 5)]))
        self.assertEqual(result['fields']['frontend']['matched'], 1)
        self.assertEqual(len(result['items'][0]['occurrences']), 2)

    def test_repeated_aliases_of_different_units_are_unassessed(self):
        self.gold['exclusions'] = []
        self.gold['fields']['frontend']['units'].append(
            {'id': 'U003', 'kind': 'present', 'spans': [{'start': 10, 'end': 15}]})
        result = self.score(outcome_fixture('frontend', ['React'], [(0, 24)]))
        self.assertEqual(result['fields']['frontend']['matched'], 0)
        self.assertEqual(result['fields']['frontend']['missing'], 2)

    def test_unknown_fields_preserve_gold_denominator(self):
        result = self.score(outcome_fixture())
        self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 2)
        self.assertEqual(sum(f['produced'] for f in result['fields'].values()), 0)
        self.assertEqual(result['field_states'], {'suggested': 0, 'unknown': 10, 'unresolved': 0})

    def test_failed_run_preserves_entire_gold(self):
        result = self.score({'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'})
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 2)
        self.assertEqual(result['items'], [])

    def test_malformed_outcome_and_unsafe_error_are_invalid(self):
        valid = outcome_fixture('frontend', ['React'], [(0, 5)])
        valid['profile']['evidence']['frontend'][0]['documentId'] = 'wrong'
        for outcome in (valid, {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'private secret'},
                        {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT', 'raw': 'secret'}):
            with self.subTest(outcome_type=len(outcome)):
                result = self.score(outcome)
                self.assertEqual(result['status'], 'invalid')
                self.assertEqual(result['evidence_invalid'], 1)
                self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 2)
                self.assertNotIn('secret', json.dumps(result))

    def test_empty_array_requires_explicit_absence_gold(self):
        outcome = outcome_fixture('ai', [], [(30, 36)])
        self.assertEqual(self.score(outcome)['fields']['ai']['unassessed'], 1)
        self.gold['fields']['ai'] = {'assessment': 'enumerated', 'units': [
            {'id': 'U003', 'kind': 'explicit_absence', 'spans': [{'start': 30, 'end': 36}]}]}
        result = self.score(outcome)
        self.assertEqual(result['fields']['ai']['matched'], 1)
        self.assertIsNone(result['items'][0]['value_sha256'])

    def test_ambiguity_overrides_wrong_field_inference(self):
        self.gold['fields']['frontend']['assessment'] = 'partial'
        self.gold['ambiguities'] = [{'id': 'A001', 'fields': ['frontend'], 'reason': 'role_not_explicit',
                                     'spans': [{'start': 25, 'end': 28}]}]
        result = self.score(outcome_fixture('frontend', ['Vue'], [(25, 28)]))
        self.assertEqual(result['fields']['frontend']['unassessed'], 1)
        self.assertEqual(result['fields']['frontend']['known_wrong'], 0)

    def test_overlapping_occurrences_and_overflow_never_pick_first(self):
        document = 'a' * 132
        gold = gold_fixture()
        gold['source_sha256'] = hashlib.sha256(document.encode()).hexdigest()
        gold['exclusions'] = []
        gold['fields'] = {f: {'assessment': 'unspecified', 'units': []} for f in FIELDS}
        gold['fields']['frontend'] = {'assessment': 'enumerated', 'units': [
            {'id': 'U001', 'kind': 'present', 'spans': [{'start': 0, 'end': 2}]}]}
        result = self.score(outcome_fixture('frontend', ['aa'], [(0, 132)], document), gold, document)
        self.assertEqual(result['fields']['frontend']['unassessed'], 1)
        self.assertTrue(result['items'][0]['occurrence_overflow'])
        self.assertEqual(result['items'][0]['occurrences'], [])

    def test_gold_rejects_hash_type_id_span_conflict_and_false_human_claim(self):
        mutations = [
            lambda g: g.update(source_sha256='0'*64),
            lambda g: g.update(human_reviewed=True),
            lambda g: g['fields']['frontend']['units'][0]['spans'][0].update(start=False),
            lambda g: g['fields']['frontend']['units'][0]['spans'][0].update(end=100),
            lambda g: g['fields']['backend']['units'][0].update(id='U001'),
            lambda g: g['fields']['frontend']['units'][0]['spans'].append({'start': 0, 'end': 5}),
            lambda g: g['exclusions'][0].update(spans=[{'start': 0, 'end': 5}]),
            lambda g: g['fields']['frontend'].update(assessment='unspecified'),
            lambda g: g.update(raw='not allowed'),
        ]
        for mutate in mutations:
            with self.subTest(index=mutations.index(mutate)):
                candidate = deepcopy(self.gold)
                mutate(candidate)
                with self.assertRaisesRegex(ValueError, '^INVALID_GOLD$'):
                    self.api.validate_gold(DOCUMENT, candidate)

    def test_gold_returns_copy_and_checks_document_identity_before_failure(self):
        result = self.api.validate_gold(DOCUMENT, self.gold)
        result['fields']['frontend']['units'].clear()
        self.assertEqual(len(self.gold['fields']['frontend']['units']), 1)
        with self.assertRaisesRegex(ValueError, '^INVALID_GOLD$'):
            self.api.score_confirmation(DOCUMENT, 'PUBLIC-02', self.gold, {'outcome': 'failed'})


class CorpusTest(unittest.TestCase):
    setUp = EvaluationTest.setUp

    def corpus(self, root, ident='PUBLIC-01', family='official/example', body=b'Synthetic source'):
        (root / (ident + '.md')).write_bytes(body)
        return {'id': ident, 'family': family, 'commit': 'a'*40, 'path': 'README.md',
                'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body), 'characters': len(body.decode()),
                'source': f'https://github.com/{family}/blob/{"a"*40}/README.md',
                'local_file': ident + '.md', 'acquisition': 'public_official_repository',
                'content_reviewed': False, 'model_outputs_seen': False, 'human_reviewed': False,
                'model_pretraining_exposure': 'unknown'}

    def test_verified_corpus_is_copied(self):
        with tempfile.TemporaryDirectory() as temp:
            row = self.corpus(Path(temp))
            result = self.api.verify_corpus([row], [], Path(temp))
            self.assertEqual(result, [row])
            result[0]['family'] = 'modified/value'
            self.assertEqual(row['family'], 'official/example')

    def test_prior_hash_or_family_overrides_unseen_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            row = self.corpus(Path(temp), family='calcom/cal.com')
            for prior in ([{'repo': 'CALCOM/cal.diy', 'sha256': '0'*64}],
                          [{'repo': 'other/product', 'sha256': row['sha256']}]):
                with self.assertRaisesRegex(ValueError, '^INVALID_CORPUS$'):
                    self.api.verify_corpus([row], prior, Path(temp))

    def test_duplicate_family_and_hash_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one = self.corpus(root)
            two = self.corpus(root, 'PUBLIC-02', body=b'Different source')
            with self.assertRaisesRegex(ValueError, '^INVALID_CORPUS$'):
                self.api.verify_corpus([one, two], [], root)
            two = self.corpus(root, 'PUBLIC-02', family='another/product')
            with self.assertRaisesRegex(ValueError, '^INVALID_CORPUS$'):
                self.api.verify_corpus([one, two], [], root)

    def test_corpus_rejects_path_source_hash_and_false_types(self):
        mutations = [lambda r: r.update(local_file='../PUBLIC-01.md'),
                     lambda r: r.update(source='https://example.org/README.md'),
                     lambda r: r.update(sha256='0'*64), lambda r: r.update(bytes=True),
                     lambda r: r.update(characters=100), lambda r: r.update(commit='HEAD'),
                     lambda r: r.update(raw='secret'), lambda r: r.update(model_outputs_seen=True)]
        with tempfile.TemporaryDirectory() as temp:
            row = self.corpus(Path(temp))
            for mutate in mutations:
                candidate = deepcopy(row)
                mutate(candidate)
                with self.assertRaisesRegex(ValueError, '^INVALID_CORPUS$'):
                    self.api.verify_corpus([candidate], [], Path(temp))


if __name__ == '__main__':
    unittest.main()
