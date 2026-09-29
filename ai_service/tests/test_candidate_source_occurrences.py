import importlib
import json
from types import SimpleNamespace
import unittest

from agentfit_ai.candidate_first_profile import (
    analyze_candidate_first, CandidatePipelineError, CandidateContractError)
from agentfit_ai.profile import FIELDS


def candidate(quote, **changes):
    return SimpleNamespace(**dict(
        {'extraction_class': 'candidate', 'extraction_text': quote,
         'attributes': {'anchor': 'not copied from the document'},
         'char_interval': SimpleNamespace(start_pos=999, end_pos=1000)}, **changes))


def freeze(document, candidates):
    module = importlib.import_module('agentfit_ai.candidate_first_profile')
    operation = getattr(module, 'freeze_candidate_occurrences', None)
    if operation is None:
        raise AssertionError('source occurrence grounding is not implemented')
    return operation(document, candidates)


class CandidateSourceOccurrenceTests(unittest.TestCase):
    def test_all_positions_survive_incorrect_anchor_and_library_alignment(self):
        document = 'Go는 검토 중이다. Go를 채택했다.'
        result = freeze(document, [candidate('Go')])
        self.assertEqual(result['candidates'], [
            {'id': 'C000', 'start': 0, 'end': 2},
            {'id': 'C001', 'start': 12, 'end': 14}])
        self.assertEqual(result['rejected'], [])

    def test_ids_are_source_ordered_and_duplicate_proposals_do_not_change_them(self):
        document = 'Alpha Go Alpha'
        first = freeze(document, [candidate('Go'), candidate('Alpha')])
        second = freeze(document, [candidate('Alpha'), candidate('Go'), candidate('Alpha')])
        self.assertEqual(first, second)
        self.assertEqual([row['start'] for row in first['candidates']], [0, 6, 9])

    def test_absent_or_invalid_quote_is_not_invented_or_normalized(self):
        result = freeze('Alpha\r\nGo', [candidate('Alpha Go'), candidate(' '),
                                       candidate('Go', extraction_class='other')])
        self.assertEqual(result['candidates'], [])
        self.assertEqual([row['reason'] for row in result['rejected']],
                         ['source_quote_absent', 'invalid_candidate', 'invalid_candidate'])

    def test_unicode_crlf_and_overlapping_positions_are_exact(self):
        document = '🚀\r\naaaa'
        result = freeze(document, [candidate('aaa'), candidate('🚀')])
        self.assertEqual([(row['start'], row['end']) for row in result['candidates']],
                         [(0, 1), (3, 6), (4, 7)])

    def test_expansion_limit_is_checked_after_deduplication(self):
        self.assertEqual(len(freeze('x' * 240, [candidate('x'), candidate('x')])[
            'candidates']), 240)
        with self.assertRaises(CandidateContractError) as caught:
            freeze('x' * 241, [candidate('x')])
        self.assertEqual(caught.exception.code, 'CANDIDATE_OCCURRENCE_LIMIT')

    def test_absent_quote_blocks_completion_even_when_review_reports_no_issue(self):
        def extractor(source, key, **kwargs):
            return [candidate('Alpha'), candidate('invented')]
        def transport(payload, key, timeout):
            is_label = payload['response_format']['json_schema']['name'] == 'agentfit_candidate_labels'
            response = ({'labels': [{'id': 'C000', 'field': 'project_name', 'status': 'confirmed'}]}
                        if is_label else {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []})
            return json.dumps({'model': 'solar-pro4-260806', 'choices': [{
                'finish_reason': 'stop', 'message': {'content': json.dumps(response)}}]}).encode()
        result = analyze_candidate_first('Alpha', 'doc', 'fake-key',
            source_occurrences=True, extractor=extractor, transport=transport)
        self.assertEqual(result['outcome'], 'needs_confirmation')
        self.assertEqual(result['rejectedReasons'], {'source_quote_absent': 1})

    def test_overflow_fails_before_any_judgment_call(self):
        def extractor(source, key, **kwargs):
            return [candidate('x')]
        def transport(*args, **kwargs):
            self.fail('oversized candidate pool reached the provider')
        with self.assertRaises(CandidatePipelineError) as caught:
            analyze_candidate_first('x' * 241, 'doc', 'fake-key',
                source_occurrences=True, extractor=extractor, transport=transport)
        self.assertEqual(caught.exception.stage, 'GROUNDING_FAILED')
        self.assertEqual(caught.exception.detail, 'CANDIDATE_OCCURRENCE_LIMIT')


if __name__ == '__main__':
    unittest.main()
