"""Whole-path contracts, using source fixtures and fake provider transports."""

from copy import deepcopy
import unittest

from agentfit_ai.candidate_first_profile import apply_candidate_review
from agentfit_ai.candidate_analysis_pipeline import _merge_occurrences
from agentfit_ai.profile import FIELDS


class CandidateMergeTests(unittest.TestCase):
    def test_union_deduplicates_positions_but_preserves_repeated_words(self):
        # Same phrase at another position must retain independent certainty.
        first = {'candidates': [{'id': 'C009', 'start': 2, 'end': 3},
                                {'id': 'C008', 'start': 0, 'end': 1}],
                 'rejected': [{'index': 8, 'reason': 'source_quote_absent'}]}
        second = {'candidates': [{'id': 'C009', 'start': 0, 'end': 1},
                                 {'id': 'C001', 'start': 4, 'end': 5}],
                  'rejected': [{'index': 9, 'reason': 'invalid_anchor'}]}
        before = deepcopy((first, second))
        merged = _merge_occurrences('A A B', first, second)
        self.assertEqual(merged, {
            'candidates': [{'id': 'C000', 'start': 0, 'end': 1},
                           {'id': 'C001', 'start': 2, 'end': 3},
                           {'id': 'C002', 'start': 4, 'end': 5}],
            'rejected': [{'index': 0, 'reason': 'source_quote_absent'},
                         {'index': 1, 'reason': 'invalid_anchor'}]})
        merged['candidates'][0]['start'] = 99
        merged['rejected'][0]['reason'] = 'invalid_candidate'
        self.assertEqual((first, second), before)

    def test_invalid_positions_and_rejections_fail_instead_of_disappearing(self):
        for candidate in ({'id': 'C000', 'start': -1, 'end': 1},
                          {'id': 'C000', 'start': False, 'end': 1},
                          {'id': 'C000', 'start': 0, 'end': 2}):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                _merge_occurrences('A', {'candidates': [candidate], 'rejected': []})
        with self.assertRaises(ValueError):
            _merge_occurrences('A', {'candidates': [], 'rejected': [
                {'index': 0, 'reason': 'not_a_reason'}]})
        with self.assertRaises(ValueError):
            _merge_occurrences('A')

    def test_union_limit_rejects_without_silent_truncation(self):
        first = {'candidates': [{'id': f'C{i:03}', 'start': i, 'end': i + 1}
                                for i in range(240)], 'rejected': []}
        last = {'candidates': [{'id': 'C000', 'start': 240, 'end': 241}],
                'rejected': []}
        self.assertEqual(len(_merge_occurrences('A' * 241, first)['candidates']), 240)
        with self.assertRaises(ValueError):
            _merge_occurrences('A' * 241, first, last)


class CandidateReviewApplicationTests(unittest.TestCase):
    def setUp(self):
        self.frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 1},
                                      {'id': 'C001', 'start': 2, 'end': 3}],
                       'rejected': []}
        self.labels = [{'id': 'C000', 'field': 'features', 'status': 'confirmed'},
                       {'id': 'C001', 'field': 'backend', 'status': 'tentative'}]
        self.review = {'checkedFields': list(FIELDS), 'missingFields': ['domain'],
                       'wrongCandidateIds': ['C000']}

    def test_only_rejected_status_changes_and_all_output_labels_are_copies(self):
        before = deepcopy((self.frozen, self.labels, self.review))
        result = apply_candidate_review(self.frozen, self.labels, self.review)
        self.assertEqual(result, [
            {'id': 'C000', 'field': 'features', 'status': 'irrelevant'},
            {'id': 'C001', 'field': 'backend', 'status': 'tentative'}])
        result[0]['field'] = 'other'
        result[1]['status'] = 'confirmed'
        self.assertEqual((self.frozen, self.labels, self.review), before)

    def test_incomplete_duplicate_or_foreign_review_never_applies(self):
        mutations = [('checkedFields', list(FIELDS)[:-1]),
                     ('checkedFields', list(reversed(FIELDS))),
                     ('missingFields', ['domain', 'domain']),
                     ('missingFields', ['other']),
                     ('wrongCandidateIds', ['C000', 'C000']),
                     ('wrongCandidateIds', ['C999']),
                     ('wrongCandidateIds', 'C000')]
        for key, value in mutations:
            review = {**self.review, key: value}
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                apply_candidate_review(self.frozen, self.labels, review)
        for review in (None, {}, {**self.review, 'extra': True}):
            with self.subTest(review=review), self.assertRaises(ValueError):
                apply_candidate_review(self.frozen, self.labels, review)

    def test_invalid_input_labels_cannot_be_sanitized_by_review(self):
        with self.assertRaises(ValueError):
            apply_candidate_review(self.frozen, self.labels[:1], self.review)


if __name__ == '__main__':
    unittest.main()
