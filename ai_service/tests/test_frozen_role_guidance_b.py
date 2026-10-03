"""Current B payload integration, using retained replies only; no quality claim."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import unittest

from agentfit_ai.candidate_mention_roles import MENTION_ROLE_INSTRUCTION
from agentfit_ai.candidate_semantic_assessment import classify_grounded_candidates, validate_assessments
from review_preservation_fixture import offline
from tentative_proposed_fixture import case, load, unreviewed_boundary


class FrozenRoleGuidanceBTests(unittest.TestCase):
    def setUp(self):
        guard = offline()
        guard.__enter__()
        self.addCleanup(guard.__exit__, None, None, None)

    def test_actual_classification_transport_matches_entire_frozen_b_request(self):
        suite = load('suite.json')
        for name, item in suite['documents'].items():
            with self.subTest(document=name):
                expected = item['payloads']['B']
                seen = []

                def transport(payload, key, timeout):
                    seen.append((deepcopy(payload), timeout))
                    return json.dumps(load(f'{name}/B-response.json')).encode('utf-8')

                actual = classify_grounded_candidates(item['document'], item['frozen'],
                    'OFFLINE-NONCREDENTIAL', model=expected['model'], transport=transport)
                document, frozen, raw, _ = case(name, 'B')
                self.assertEqual(actual['modelDecisions'],
                    validate_assessments(document, frozen, raw, require_mention_kind=True))
                self.assertEqual(seen, [(expected, 600)])

    def test_exact_b_block_and_only_role_block_differs_from_a(self):
        self.assertEqual(hashlib.sha256(MENTION_ROLE_INSTRUCTION.encode()).hexdigest(),
            'f6c4265d4f459babee04e5ed010b9ac81525dcbe3c77ba784ebd54dbb0229523')
        for name, item in load('suite.json')['documents'].items():
            a, b = deepcopy(item['payloads']['A']), item['payloads']['B']
            old = load(f'{name}/A-role-instruction.txt')
            new = load(f'{name}/B-role-instruction.txt')
            self.assertEqual(MENTION_ROLE_INSTRUCTION, new)
            self.assertEqual(a['messages'][0]['content'].count(old), 1)
            a['messages'][0]['content'] = a['messages'][0]['content'].replace(old, new)
            self.assertEqual(a, b)  # Includes all options, schema, full source and context.

    def test_saved_b_normal_facts_exclusions_and_raw_errors_are_preserved(self):
        expected = {
            'D1': ['supported']*3 + ['excluded']*2 + ['supported']*2 + ['excluded'],
            'D2': ['supported']*3 + ['excluded']*2 + ['supported'] + ['needs_confirmation']*2,
        }
        totals = Counter()
        raw_errors = []
        for name in ('D1', 'D2'):
            document, frozen, raw, old = case(name, 'B')
            original = deepcopy(raw)
            rows = validate_assessments(document, frozen, raw, require_mention_kind=True)
            self.assertEqual([r['decision'] for r in rows], expected[name])
            self.assertEqual(raw, original)
            for before, after in zip(old, rows, strict=True):
                self.assertEqual({k:v for k,v in before.items() if k != 'decision'},
                                 {k:v for k,v in after.items() if k != 'decision'})
                totals[after['decision']] += 1
                if after['modelStatus'] == 'confirmed' and (
                        after['field'] == 'other' or after['scope'] == 'other' or
                        after['polarity'] == 'negative'):
                    self.assertEqual(after['decision'], 'excluded')
                    raw_errors.append((name, after['id']))
            for index, field in enumerate(('project_name', 'project_type', 'domain')):
                self.assertEqual(rows[index]['field'], field)
                self.assertEqual(rows[index]['mentionKind'], 'other')
            for index in ([5, 6] if name == 'D1' else [5]):
                self.assertEqual(rows[index]['field'], 'external_integrations')
                self.assertEqual(rows[index]['mentionKind'], 'external_service')
        self.assertEqual(totals, {'supported':9, 'excluded':5, 'needs_confirmation':2})
        self.assertEqual(raw_errors, [('D1','C003'),('D1','C004'),('D1','C007'),('D2','C004')])

    def test_saved_proposal_and_conflict_remain_explicit_in_unreviewed_boundary(self):
        document, frozen, raw, _ = case('D2', 'B')
        rows = validate_assessments(document, frozen, raw, require_mention_kind=True)
        held = [r for r in rows if r['decision'] == 'needs_confirmation']
        self.assertEqual([r['id'] for r in held], ['C006', 'C007'])
        self.assertEqual(held[0]['modelStatus'], 'tentative')
        self.assertEqual(held[0]['commitment'], 'proposed')
        self.assertTrue(held[1]['counterEvidence'])
        for contract in ('confirmation-v2', 'confirmation-v3'):
            out = unreviewed_boundary(document, held, contract)
            self.assertEqual(out['outcome'], 'needs_confirmation')
            self.assertIsNone(out['profile']['data']['external_integrations'])
            self.assertEqual(len(out['modelDecisions']), 2)
            for saved, row in zip(held, out['modelDecisions'], strict=True):
                self.assertEqual(row['decision'], 'needs_confirmation')
                for key in ('modelStatus', 'support', 'counterEvidence', 'candidate'):
                    self.assertEqual(row[key], saved[key])
                self.assertEqual(row['sourceValue'],
                    document[row['candidate']['start']:row['candidate']['end']])
            self.assertTrue(any(q['field'] == 'external_integrations' for q in out['questions']))


if __name__ == '__main__':
    unittest.main()
