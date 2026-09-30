"""Quote-only extraction keeps all exact occurrences for later classification."""
import json
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_first_profile import CandidateContractError
from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.solar import AnalysisError
from tests.test_candidate_split_review import response


class CapabilityCandidatesTests(unittest.TestCase):
    def extract(self, document, quotes, **options):
        from agentfit_ai.capability_candidates import extract_capability_candidates
        return extract_capability_candidates(document, 'unit-nvidia-secret',
            transport=lambda *args: response({'quotes': quotes}, model=MODEL), **options)

    def test_repeated_unicode_quotes_expand_without_model_written_anchors(self):
        frozen = self.extract('🚀 주문 조회를 제공한다. 주문 조회는 검토 중이다.', ['주문 조회', '주문 조회'])
        self.assertEqual(frozen, {'candidates': [
            {'id': 'C000', 'start': 2, 'end': 7}, {'id': 'C001', 'start': 15, 'end': 20}], 'rejected': []})
        self.assertNotIn('주문', json.dumps(frozen, ensure_ascii=False))

    def test_absent_quotes_remain_rejected_and_no_normalization_is_invented(self):
        frozen = self.extract('A-B; A–B; A-B', ['A-B', 'A B', 'missing'])
        self.assertEqual(frozen, {'candidates': [
            {'id': 'C000', 'start': 0, 'end': 3}, {'id': 'C001', 'start': 10, 'end': 13}],
            'rejected': [{'index': 1, 'reason': 'source_quote_absent'},
                         {'index': 2, 'reason': 'source_quote_absent'}]})

    def test_overlapping_occurrences_are_retained_and_241_positions_fail(self):
        self.assertEqual(self.extract('AAA', ['AA'])['candidates'], [
            {'id': 'C000', 'start': 0, 'end': 2}, {'id': 'C001', 'start': 1, 'end': 3}])
        self.assertEqual(len(self.extract('A' * 240, ['A'])['candidates']), 240)
        with self.assertRaises(CandidateContractError) as caught:
            self.extract('A' * 241, ['A'])
        self.assertEqual(caught.exception.code, 'CANDIDATE_OCCURRENCE_LIMIT')

    def test_quote_length_count_empty_and_malformed_boundaries(self):
        self.assertEqual(self.extract('x', []), {'candidates': [], 'rejected': []})
        self.assertEqual(len(self.extract('x' * 200, ['x' * 200])['candidates']), 1)
        self.assertEqual(len(self.extract('x', ['x'] * 60)['candidates']), 1)
        for quotes in (None, {}, 'x', [None], [True], [''], ['  '], ['x' * 201], ['x'] * 61):
            with self.subTest(kind=type(quotes).__name__), self.assertRaises(ValueError):
                self.extract('x', quotes)

    def test_full_document_only_and_no_fields_or_gold_in_generation_request(self):
        from agentfit_ai.capability_candidates import extract_capability_candidates
        seen = []
        def transport(payload, key, timeout):
            seen.append(payload)
            self.assertEqual(json.loads(payload['messages'][1]['content']), {'document': 'A features: search'})
            self.assertEqual((key, timeout, payload['model']), ('unit-nvidia-secret', 600, MODEL))
            return response({'quotes': ['search']}, model=MODEL)
        result = extract_capability_candidates('A features: search', 'unit-nvidia-secret', transport=transport)
        self.assertEqual(result['candidates'], [{'id': 'C000', 'start': 12, 'end': 18}])
        self.assertEqual(len(seen), 1)

    def test_extra_fields_and_provider_format_errors_fail(self):
        from agentfit_ai.capability_candidates import extract_capability_candidates
        for body in ({'quotes': ['X'], 'status': 'confirmed'}, {'mentions': []}):
            with self.subTest(body=body), self.assertRaises(AnalysisError):
                extract_capability_candidates('X', 'secret',
                    transport=lambda *args: response(body, model=MODEL))
        for options in ({'model': 'wrong'}, {'model': MODEL, 'finish': 'length'}):
            with self.subTest(options=options), self.assertRaises(AnalysisError):
                extract_capability_candidates('X', 'secret',
                    transport=lambda *args: response({'quotes': []}, **options))

    def test_invalid_input_never_reaches_provider(self):
        from agentfit_ai.capability_candidates import extract_capability_candidates
        for document, key, model in (('', 'secret', MODEL), ('secret here', 'secret', MODEL),
                                     ('x', '', MODEL), ('x', 'secret', 'bad')):
            with self.subTest(model=model), self.assertRaises(ValueError):
                extract_capability_candidates(document, key, model=model,
                    transport=lambda *args: self.fail('invalid request reached provider'))

    def test_falsey_callable_transport_is_used_instead_of_default_network(self):
        from agentfit_ai.capability_candidates import extract_capability_candidates
        class FalseyTransport:
            def __bool__(self):
                return False
            def __call__(self, *args):
                return response({'quotes': ['X']}, model=MODEL)
        with patch('agentfit_ai.operation_candidates.post_nvidia',
                   return_value=response({'quotes': []}, model=MODEL)):
            result = extract_capability_candidates('X', 'secret', transport=FalseyTransport())
        self.assertEqual(result['candidates'], [{'id': 'C000', 'start': 0, 'end': 1}])

    def test_non_callable_transport_is_rejected_without_default_network(self):
        from agentfit_ai.capability_candidates import extract_capability_candidates
        with patch('agentfit_ai.operation_candidates.post_nvidia',
                   return_value=response({'quotes': []}, model=MODEL)) as default:
            for value in (False, 0, '', [], {}):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    extract_capability_candidates('X', 'secret', transport=value)
            self.assertEqual(default.call_count, 0)


if __name__ == '__main__':
    unittest.main()
