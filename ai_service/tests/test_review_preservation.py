from copy import deepcopy
import unittest

from agentfit_ai.candidate_confirmation import project_candidate_confirmation, validate_candidate_confirmation
from review_preservation_fixture import DIRECTORY, load, offline, replay, synthetic_result
from agentfit_ai.candidate_review_dispositions import build_review_dispositions
from contract_mock.schema import check_review, ContractError

V3 = 'confirmation-v3'


class ReviewPreservation(unittest.TestCase):
    def test_v2_replay_is_exactly_the_frozen_result(self):
        self.assertEqual(replay(), load('result.json'))

    def test_R1_R2_R3_six_rejections_have_exact_source_and_reason(self):
        out = replay(V3)
        expected = {'C052': 'not_current', 'C055': 'not_current', 'C077': 'not_product_fact',
                    'C079': 'not_product_fact', 'C120': 'insufficient_evidence', 'C121': 'insufficient_evidence'}
        self.assertEqual({r['candidateId']: r['reason'] for r in out['reviewDispositions']}, expected)
        rows = {r['id']: r for r in out['modelDecisions']}
        doc = load('document.txt')
        for disposition in out['reviewDispositions']:
            row = rows[disposition['candidateId']]
            self.assertEqual(disposition['disposition'], 'needs_confirmation')
            self.assertEqual(row['decision'], 'supported')
            self.assertEqual(row['sourceValue'], doc[row['candidate']['start']:row['candidate']['end']])
            self.assertEqual(row['documentId'], load('trace.json')['documentId'])
            self.assertNotIn(dict(documentId=row['documentId'], **row['candidate']),
                             out['profile']['evidence'][row['field']])

    def test_R4_R5_R6_profile_raw_records_and_existing_obligations_unchanged(self):
        out, saved = replay(V3), load('result.json')
        for key in ('profile', 'modelDecisions', 'questions', 'unassignedQuestions', 'fieldStates'):
            self.assertEqual(out[key], saved[key], key)
        self.assertEqual(sum(r['decision'] == 'needs_confirmation' for r in out['modelDecisions']), 52)
        self.assertEqual(len(out['questions']) + len(out['unassignedQuestions']), 11)
        self.assertEqual(out['profile']['data']['external_integrations'], ['GitHub', 'Codex'])
        self.assertIsNone(out['profile']['data']['project_name'])

    def test_synthetic_correct_rejection_is_held_never_restored(self):
        document, result = synthetic_result()
        with offline():
            out = project_candidate_confirmation(document, 'synthetic', result, contract=V3)
        self.assertIsNone(out['profile']['data']['features'])
        self.assertEqual(out['modelDecisions'][0]['decision'], 'supported')
        self.assertEqual(out['reviewDispositions'], result['reviewDispositions'])

    def test_same_value_independent_source_allowed_but_rejected_occurrence_forbidden(self):
        document, result = synthetic_result(independent=True)
        out = project_candidate_confirmation(document, 'synthetic', result, contract=V3)
        self.assertEqual(out['profile']['data']['features'], ['bulk export'])
        out['profile']['evidence']['features'].append(dict(documentId='synthetic',
                                                          **out['modelDecisions'][0]['candidate']))
        with self.assertRaises(ValueError):
            validate_candidate_confirmation(document, 'synthetic', out, contract=V3)

    def test_all_fixture_hashes_and_40_meanings_remain_frozen(self):
        import json
        for name in json.loads((DIRECTORY / 'manifest.json').read_text())['files']:
            load(name)
        out = replay(V3)
        pending = {r['id'] for r in out['modelDecisions'] if r['decision'] == 'needs_confirmation'}
        pending.update(r['candidateId'] for r in out['reviewDispositions'])
        self.assertEqual(len(pending), 58)
        from collections import Counter
        meanings = load('meaning-audit.json')
        counts = Counter(r['finalJudgment'] for r in meanings)
        self.assertEqual(counts, dict(preserved=26, held=9, missing=3, human_review=2))
        changed = []
        for meaning in meanings:
            linked = {c['candidateId'] for c in meaning['candidateEvidence']} & pending
            if meaning['finalJudgment'] == 'missing' and linked:
                changed.append(meaning['id'])
                counts['missing'] -= 1
                counts['held'] += 1
        self.assertEqual(changed, ['F04.03', 'F10.04'])
        self.assertEqual(counts, dict(preserved=26, held=11, missing=1, human_review=2))

    def test_R4_R5_accepted_27_unreviewed_112_not_reclassified(self):
        from agentfit_ai.candidate_first_profile import apply_candidate_review
        stages = load('trace.json')['stages']
        before = stages['classified']['labels']
        after = apply_candidate_review(stages['classified']['frozen'], before, stages['review_completed']['review'])
        by_id = {r['id']: r for r in after}
        unreviewed = [r for r in before if r['status'] != 'confirmed']
        self.assertEqual(len(unreviewed), 112)
        self.assertTrue(all(r == by_id[r['id']] for r in unreviewed))
        accepted = [r for r in after if r['status'] == 'confirmed']
        self.assertEqual(len(accepted), 27)
        out = replay(V3)
        frozen = {c['id']: c for c in stages['classified']['frozen']['candidates']}
        for label in accepted:
            candidate = frozen[label['id']]
            self.assertIn(dict(documentId=load('trace.json')['documentId'],
                **{k: candidate[k] for k in ('start', 'end')}), out['profile']['evidence'][label['field']])

    def test_invalid_dispositions_are_rejected_by_ai_and_mock(self):
        document, result = synthetic_result()
        valid = project_candidate_confirmation(document, 'synthetic', result, contract=V3)
        for change in ({'candidateId': 'C999'}, {'candidateId': []}, {'reason': 'invented'},
                       {'reason': []}, {'disposition': 'confirmed'}, {'extra': True}):
            bad = deepcopy(valid)
            bad['reviewDispositions'][0].update(change)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_candidate_confirmation(document, 'synthetic', bad, contract=V3)
                with self.assertRaises(ContractError):
                    check_review(bad['profile'], {k: v for k, v in bad.items() if k not in ('profile', 'outcome', 'error')})
        bads = []
        bad = deepcopy(valid); bad['reviewDispositions'] *= 2; bads.append(bad)
        bad = deepcopy(valid); del bad['reviewDispositions']; bads.append(bad)
        bad = deepcopy(valid); del bad['modelDecisions']; bads.append(bad)
        bad = deepcopy(valid); bad['reviewDispositions'] = None; bads.append(bad)
        bad = deepcopy(valid); bad['fieldStates']['features'] = 'unknown'; bad['questions'] = []; bads.append(bad)
        for bad in bads:
            with self.subTest(bad=bad.keys()), self.assertRaises(ValueError):
                validate_candidate_confirmation(document, 'synthetic', bad, contract=V3)

    def test_invalid_source_bindings_rejected(self):
        document, result = synthetic_result()
        valid = project_candidate_confirmation(document, 'synthetic', result, contract=V3)
        for change in ({'sourceValue': 'fake export'}, {'documentId': 'another-document'},
                       {'candidate': {'start': 1000, 'end': 1011}},
                       {'candidate': {'start': 0, 'end': 11}}, {'groundingValid': False}):
            bad = deepcopy(valid); bad['modelDecisions'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_candidate_confirmation(document, 'synthetic', bad, contract=V3)

    def test_v2_cannot_leak_v3_metadata_and_unknown_contract_rejected(self):
        valid = replay(V3)
        for contract in ('confirmation-v2', 'confirmation-v4', None):
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                validate_candidate_confirmation(load('document.txt'), load('trace.json')['documentId'], valid,
                                                contract=contract)
        valid['contract'] = 'confirmation-v2'
        with self.assertRaises(ValueError):
            validate_candidate_confirmation(load('document.txt'), load('trace.json')['documentId'], valid)

    def test_reason_collector_must_cover_exact_rejected_set_once(self):
        review = {'wrongCandidateIds': ['C000']}
        for reasons in ([], [{'id': 'C001', 'reason': 'not_current'}],
                        [{'id': 'C000', 'reason': 'not_current'}] * 2,
                        [{'id': 'C000', 'reason': 'invented'}]):
            with self.subTest(reasons=reasons), self.assertRaises(ValueError):
                build_review_dispositions(review, reasons)
        self.assertEqual(build_review_dispositions({'wrongCandidateIds': []}, []), [])

    def test_combined_name_cannot_reuse_a_rejected_exact_span(self):
        from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
        from agentfit_ai.profile import FIELDS
        document = 'Alpha (Beta)'
        candidates = [{'id': 'C000', 'start': 0, 'end': 5},
                      {'id': 'C001', 'start': 0, 'end': 12},
                      {'id': 'C002', 'start': 7, 'end': 11}]
        labels = [{'id': c['id'], 'field': 'project_name', 'status': 'confirmed'} for c in candidates]
        review = {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': ['C001']}
        result = finalize_candidate_analysis(document, 'synthetic', {'candidates': candidates, 'rejected': []},
                                             labels, review)
        template = synthetic_result()[1]['modelDecisions'][0]
        template.pop('mentionKind')
        result['modelDecisions'] = [dict(template, id=c['id'], field='project_name',
            support=[{'start': 0, 'end': 12}], candidate={k: c[k] for k in ('start', 'end')}) for c in candidates]
        result['reviewDispositions'] = [{'candidateId': 'C001', 'disposition': 'needs_confirmation', 'reason': 'not_current'}]
        self.assertEqual(result['profile']['data']['project_name'], document)
        with self.assertRaisesRegex(ValueError, 'REVIEW_HELD_EVIDENCE'):
            project_candidate_confirmation(document, 'synthetic', result, contract=V3)


if __name__ == '__main__':
    unittest.main()
