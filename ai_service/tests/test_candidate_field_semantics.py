"""The opt-in meaning contract reaches every candidate decision boundary."""
import json
from types import SimpleNamespace
import unittest

from agentfit_ai import candidate_first_profile as first
from agentfit_ai.candidate_split_review import review_candidates_separately
from agentfit_ai.profile import FIELDS
from tests.test_candidate_split_review import fixture, response


class CandidateFieldSemanticsTests(unittest.TestCase):
    def test_default_and_explicit_legacy_payloads_are_identical(self):
        document, frozen, labels = fixture(1)
        self.assertEqual(first.candidate_label_payload(document, frozen['candidates']),
                         first.candidate_label_payload(document, frozen['candidates'], field_semantics='legacy'))
        self.assertEqual(first.coverage_review_payload(document, frozen, labels),
                         first.coverage_review_payload(document, frozen, labels, field_semantics='legacy'))

    def test_policy_names_and_all_fields_are_explicit(self):
        from agentfit_ai.candidate_field_semantics import field_semantics_instructions
        self.assertEqual(field_semantics_instructions('legacy'), '')
        instruction = field_semantics_instructions('explicit-v1')
        for field in FIELDS:
            self.assertIn(field + ':', instruction)
        for policy in ('unknown', None, True, [], {}):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                field_semantics_instructions(policy)

    def test_full_pipeline_carries_same_contract_to_every_semantic_call(self):
        from agentfit_ai.candidate_field_semantics import field_semantics_instructions
        instruction = field_semantics_instructions('explicit-v1')
        for split in (False, True):
            seen = []
            def transport(payload, key, timeout):
                name = payload['response_format']['json_schema']['name']
                seen.append(name)
                self.assertIn(instruction, payload['messages'][0]['content'])
                if name == 'agentfit_candidate_labels':
                    return response({'labels': [{'id': 'C000', 'field': 'backend', 'status': 'confirmed'}]})
                if name == 'agentfit_candidate_label_review':
                    return response({'checkedCandidateIds': ['C000'], 'wrongCandidateIds': []})
                verdict = {'checkedFields': list(FIELDS), 'missingFields': []}
                if name == 'agentfit_candidate_coverage':
                    verdict['wrongCandidateIds'] = []
                return response(verdict)
            result = first.analyze_candidate_first('Go', 'test', 'fake',
                extractor=lambda *a, **k: [SimpleNamespace(extraction_class='candidate', extraction_text='Go')],
                transport=transport, source_occurrences=True, split_review=split,
                field_semantics='explicit-v1')
            self.assertEqual(result['profile']['data']['backend'], ['Go'])
            self.assertEqual(len(seen), 3 if split else 2)

    def test_legacy_split_review_requests_remain_identical(self):
        document, frozen, labels = fixture(1)
        requests = []
        def transport(payload, key, timeout):
            requests.append(payload)
            if 'selections' in json.loads(payload['messages'][1]['content']):
                return response({'checkedCandidateIds': ['C000'], 'wrongCandidateIds': []})
            return response({'checkedFields': list(FIELDS), 'missingFields': []})
        review_candidates_separately(document, frozen, labels, 'fake', transport=transport)
        review_candidates_separately(document, frozen, labels, 'fake', transport=transport, field_semantics='legacy')
        self.assertEqual(requests[:2], requests[2:])

    def test_invalid_policy_is_rejected_before_extraction_or_transport(self):
        document, frozen, labels = fixture(1)
        def forbidden(*a, **k):
            self.fail('invalid policy reached external operation')
        for call in (
            lambda: first.analyze_candidate_first(document, 'test', 'fake', extractor=forbidden, field_semantics='bad'),
            lambda: first.classify_profile_candidates(document, frozen, 'fake', transport=forbidden, field_semantics='bad'),
            lambda: first.review_candidate_coverage(document, frozen, labels, 'fake', transport=forbidden, field_semantics='bad'),
            lambda: review_candidates_separately(document, frozen, labels, 'fake', transport=forbidden, field_semantics='bad')):
            with self.assertRaises(ValueError):
                call()
