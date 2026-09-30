"""Failures remain failures while diagnostics identify only safe contract causes."""

from copy import deepcopy
import json
import unittest

from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.candidate_split_review import review_candidates_separately
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from test_candidate_analysis_pipeline import ProviderFixture, GLM
from test_candidate_split_review import fixture, response


PRIVATE = 'PRIVATE_VALUE_SENTINEL'


class ReviewContractDiagnosticTests(unittest.TestCase):
    def assert_bad_reply(self, reply, expected, *, coverage=False, reasoned=True):
        document, frozen, labels = fixture(2)
        if coverage:
            frozen, labels = {'candidates': [], 'rejected': []}, []
        prior = {'prior': True}
        calls, requests, reasons = [deepcopy(prior)], [], []
        original = deepcopy((frozen, labels, reply))

        def transport(payload, key, timeout):
            requests.append(deepcopy(payload))
            return response(reply, model=GLM)

        with self.assertRaises(ValueError) as caught:
            review_candidates_separately(document, frozen, labels, 'fake',
                transport=transport, review_calls=calls, review_reasons=reasons,
                review_model=GLM, reasoned_review=reasoned)
        self.assertIs(type(caught.exception), ValueError)
        self.assertEqual(str(caught.exception), 'invalid split review contract')
        self.assertEqual(len(requests), 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], prior)
        self.assertFalse(calls[1]['validated'])
        self.assertEqual(calls[1]['error'], 'INVALID_REVIEW_CONTRACT')
        self.assertEqual(calls[1].get('contract_issue', 'ABSENT'), expected)
        self.assertEqual(reasons, [])
        self.assertEqual((frozen, labels, reply), original)
        for secret in (PRIVATE, document, 'fake', 'C000', 'C001'):
            self.assertNotIn(secret, json.dumps(calls))

    def test_candidate_list_violations_are_distinct(self):
        # Collapsing all mismatches to one code hides the next corrective action.
        cases = [
            ('checkedCandidateIds', None, 'CHECKED_CANDIDATE_IDS_TYPE'),
            ('checkedCandidateIds', ['C000', {}], 'CHECKED_CANDIDATE_IDS_MEMBER'),
            ('checkedCandidateIds', [PRIVATE], 'CHECKED_CANDIDATE_IDS_MEMBER'),
            ('checkedCandidateIds', ['C000', 'C000'], 'CHECKED_CANDIDATE_IDS_DUPLICATE'),
            ('checkedCandidateIds', ['C000'], 'CHECKED_CANDIDATE_IDS_MISSING'),
            ('checkedCandidateIds', ['C001', 'C000'], 'CHECKED_CANDIDATE_IDS_ORDER'),
            ('wrongCandidateIds', {}, 'WRONG_CANDIDATE_IDS_TYPE'),
            ('wrongCandidateIds', [[]], 'WRONG_CANDIDATE_IDS_MEMBER'),
            ('wrongCandidateIds', [PRIVATE], 'WRONG_CANDIDATE_IDS_MEMBER'),
            ('wrongCandidateIds', ['C000', 'C000'], 'WRONG_CANDIDATE_IDS_DUPLICATE'),
        ]
        for reasoned in (False, True):
            for field, value, expected in cases:
                with self.subTest(reasoned=reasoned, issue=expected, value=value):
                    reply = {'checkedCandidateIds': ['C000', 'C001'], 'wrongCandidateIds': []}
                    if reasoned:
                        reply['rejectionReasons'] = []
                    reply[field] = value
                    self.assert_bad_reply(reply, expected, reasoned=reasoned)

    def test_rejection_reason_violations_are_distinct(self):
        cases = [
            (['C000'], None, 'REJECTION_REASONS_TYPE'),
            (['C000'], [], 'REJECTION_REASONS_COUNT'),
            (['C000'], [None], 'REJECTION_REASONS_ROW_SHAPE'),
            (['C000'], [{'id': 'C000'}], 'REJECTION_REASONS_ROW_SHAPE'),
            (['C000'], [{'id': 'C000', 'reason': 'not_current', 'extra': PRIVATE}],
             'REJECTION_REASONS_ROW_SHAPE'),
            (['C000'], [{'id': {}, 'reason': 'not_current'}], 'REJECTION_REASONS_ID_MEMBER'),
            (['C000'], [{'id': 'C001', 'reason': 'not_current'}], 'REJECTION_REASONS_ID_MEMBER'),
            (['C000'], [{'id': 'C000', 'reason': {}}], 'REJECTION_REASONS_REASON_VALUE'),
            (['C000'], [{'id': 'C000', 'reason': PRIVATE}], 'REJECTION_REASONS_REASON_VALUE'),
            (['C000', 'C001'], [{'id': 'C000', 'reason': 'not_current'},
                              {'id': 'C000', 'reason': 'wrong_field'}],
             'REJECTION_REASONS_DUPLICATE_ID'),
        ]
        for wrong, rows, expected in cases:
            with self.subTest(issue=expected, rows=rows):
                self.assert_bad_reply({'checkedCandidateIds': ['C000', 'C001'],
                    'wrongCandidateIds': wrong, 'rejectionReasons': rows}, expected)

    def test_coverage_violations_are_distinct(self):
        cases = [
            ('checkedFields', {}, 'CHECKED_FIELDS_TYPE'),
            ('checkedFields', [False], 'CHECKED_FIELDS_MEMBER'),
            ('checkedFields', [PRIVATE], 'CHECKED_FIELDS_MEMBER'),
            ('checkedFields', ['backend', 'backend'], 'CHECKED_FIELDS_DUPLICATE'),
            ('checkedFields', [], 'CHECKED_FIELDS_MISSING'),
            ('checkedFields', list(reversed(FIELDS)), 'CHECKED_FIELDS_ORDER'),
            ('missingFields', None, 'MISSING_FIELDS_TYPE'),
            ('missingFields', [[]], 'MISSING_FIELDS_MEMBER'),
            ('missingFields', [PRIVATE], 'MISSING_FIELDS_MEMBER'),
            ('missingFields', ['backend', 'backend'], 'MISSING_FIELDS_DUPLICATE'),
        ]
        for field, value, expected in cases:
            with self.subTest(issue=expected, value=value):
                reply = {'checkedFields': list(FIELDS), 'missingFields': []}
                reply[field] = value
                self.assert_bad_reply(reply, expected, coverage=True)

    def test_first_violation_wins_without_leaking_other_bad_values(self):
        self.assert_bad_reply({'checkedCandidateIds': ['C001', 'C000'],
            'wrongCandidateIds': [PRIVATE], 'rejectionReasons': PRIVATE},
            'CHECKED_CANDIDATE_IDS_ORDER')
        self.assert_bad_reply({'checkedCandidateIds': ['C000', 'C001'],
            'wrongCandidateIds': ['C000', 'C001'], 'rejectionReasons': [
                {'id': 'C000', 'reason': PRIVATE}, {'id': 'C001'}]},
            'REJECTION_REASONS_ROW_SHAPE')

    def test_valid_collector_is_observational(self):
        document, frozen, labels = fixture(2)
        for model in ('solar-pro4', GLM):
            for reasoned in (False, True):
                runs = []
                for collector in (None, [], [{'prior': True}]):
                    requests, reasons = [], []
                    def transport(payload, key, timeout):
                        requests.append(deepcopy(payload))
                        data = json.loads(payload['messages'][1]['content'])
                        if 'selections' in data:
                            reply = {'checkedCandidateIds': ['C000', 'C001'],
                                     'wrongCandidateIds': ['C001', 'C000']}
                            if reasoned:
                                reply['rejectionReasons'] = [
                                    {'id': 'C000', 'reason': 'wrong_field'},
                                    {'id': 'C001', 'reason': 'not_current'}]
                        else:
                            reply = {'checkedFields': list(FIELDS),
                                     'missingFields': ['features', 'backend']}
                        return response(reply, model=model)
                    result = review_candidates_separately(document, frozen, labels, 'fake',
                        transport=transport, review_calls=collector, review_reasons=reasons,
                        review_model=model, reasoned_review=reasoned)
                    runs.append((requests, result, reasons))
                    self.assertEqual(len(requests), 2)
                    if collector is not None:
                        for row in collector[-2:]:
                            self.assertTrue(row['validated'])
                            self.assertIn('contract_issue', row)
                            self.assertIsNone(row['contract_issue'])
                        if len(collector) == 3:
                            self.assertEqual(collector[0], {'prior': True})
                self.assertEqual(runs[0], runs[1])
                self.assertEqual(runs[0], runs[2])

    def test_provider_and_parser_failures_keep_original_error(self):
        document, frozen, labels = fixture(2)
        body = {'checkedCandidateIds': ['C000', 'C001'], 'wrongCandidateIds': [],
                'rejectionReasons': []}
        bad_json = json.dumps({'model': GLM, 'choices': [{'finish_reason': 'stop',
            'message': {'content': '{'}}]}).encode()
        cases = [(response({}, model=GLM), 'INVALID_RESPONSE'),
                 (response({**body, 'extra': PRIVATE}, model=GLM), 'INVALID_RESPONSE'),
                 (bad_json, 'INVALID_RESPONSE'),
                 (response(body, model='other'), 'PROVIDER_MODEL'),
                 (response(body, model=GLM, finish='length'), 'INCOMPLETE_RESPONSE'),
                 (AnalysisError('PROVIDER_UNAVAILABLE'), 'PROVIDER_UNAVAILABLE')]
        for raw, expected in cases:
            with self.subTest(error=expected):
                calls, requests = [], []
                def transport(payload, key, timeout):
                    requests.append(payload)
                    if isinstance(raw, Exception):
                        raise raw
                    return raw
                with self.assertRaises(AnalysisError) as caught:
                    review_candidates_separately(document, frozen, labels, 'fake',
                        transport=transport, review_calls=calls, review_model=GLM,
                        reasoned_review=True)
                self.assertEqual(caught.exception.code, expected)
                self.assertEqual(len(requests), 1)
                self.assertEqual(calls[0]['error'], expected)
                self.assertIn('contract_issue', calls[0])
                self.assertIsNone(calls[0]['contract_issue'])
                self.assertNotIn(PRIVATE, json.dumps(calls))

    def test_late_failure_stops_integrated_pipeline(self):
        case = ProviderFixture(32)
        calls, events, traces = [], [], []
        def transport(payload, key, timeout):
            raw = case.transport(payload, key, timeout)
            if payload['response_format']['json_schema']['name'] == 'agentfit_candidate_label_review':
                data = json.loads(payload['messages'][1]['content'])
                if data['selections'][0]['id'] == 'C020':
                    return response({'checkedCandidateIds': [row['id'] for row in data['selections']],
                        'wrongCandidateIds': ['C020'], 'rejectionReasons': []}, model=GLM)
            return raw
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(nvidia_transport=transport, review_calls=calls, call_trace=traces,
                     observer=lambda stage, state: events.append(stage))
        self.assertEqual(caught.exception.stage, 'COVERAGE_REVIEW_FAILED')
        self.assertEqual(events, ['grounded', 'classified'])
        self.assertEqual(len(case.requests), 5)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0]['validated'])
        self.assertFalse(calls[1]['validated'])
        self.assertTrue(all(row['attempt'] == 1 for row in traces))
        self.assertEqual(calls[1]['error'], 'INVALID_REVIEW_CONTRACT')
        self.assertEqual(calls[1].get('contract_issue', 'ABSENT'), 'REJECTION_REASONS_COUNT')
