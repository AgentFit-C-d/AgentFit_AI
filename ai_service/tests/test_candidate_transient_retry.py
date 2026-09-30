"""Provider faults must not erase progress or turn quality failures into resampling."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.solar import AnalysisError
from test_candidate_analysis_pipeline import ProviderFixture, NVIDIA_KEY, SOLAR_KEY
from test_candidate_feature_curation import response


OPERATION = 'agentfit_operation_candidates'
COVERAGE = 'agentfit_candidate_source_coverage'


class FaultTransport:
    def __init__(self, case, schema, faults, *, mutate=False):
        self.case, self.schema, self.faults = case, schema, list(faults)
        self.mutate, self.failed, self.attempts = mutate, 0, []

    def __call__(self, payload, key, timeout):
        self.attempts.append((deepcopy(payload), key, timeout))
        name = payload['response_format']['json_schema']['name']
        if name == self.schema and self.faults:
            fault = self.faults.pop(0)
            self.failed += 1
            if self.mutate:
                payload['messages'][0]['content'] = 'changed by transport'
                payload['model'] = 'changed-model'
                payload['response_format']['json_schema']['schema'].clear()
            raise fault if isinstance(fault, Exception) else AnalysisError(fault)
        return self.case.transport(payload, key, timeout)


class NvidiaTransientRetryTests(unittest.TestCase):
    def setUp(self):
        # Waiting is an external clock boundary, not model-generation behavior.
        timer = patch('agentfit_ai.candidate_analysis_pipeline.sleep', create=True)
        self.wait = timer.start()
        self.addCleanup(timer.stop)

    def test_every_nvidia_stage_recovers_once_without_changing_profile(self):
        expected = ProviderFixture().run()
        for schema in (OPERATION, 'agentfit_candidate_label_review', COVERAGE,
                       'agentfit_feature_grouping', 'agentfit_feature_relations',
                       'agentfit_feature_regrouping'):
            with self.subTest(schema=schema):
                self.wait.reset_mock()
                case, trace = ProviderFixture(), []
                send = FaultTransport(case, schema, ['PROVIDER_UNAVAILABLE'])
                result = case.run(nvidia_transport=send, call_trace=trace)
                self.assertEqual(result, expected)
                retries = [row for row in trace if row['attempt'] == 2]
                self.assertEqual(len(retries), 1)
                retried = retries[0]
                first = trace[retried['retry_of_call_index'] - 1]
                self.assertEqual(first['provider_error'], 'PROVIDER_UNAVAILABLE')
                self.assertFalse(first['transport_completed'])
                self.assertTrue(retried['transport_completed'])
                self.assertIsNone(retried['provider_error'])
                self.assertEqual(retried['stage'], first['stage'])
                self.assertEqual(retried['requested_model'], first['requested_model'])
                self.assertEqual([row['call_index'] for row in trace], list(range(1, len(trace) + 1)))
                self.assertEqual(len(trace), len(case.requests) + 1)
                self.wait.assert_called_once_with(2.0)

    def test_late_coverage_failure_replays_only_that_request_and_preserves_prior_collector(self):
        case, trace = ProviderFixture(1), [{'prior': True}]
        send = FaultTransport(case, COVERAGE, ['PROVIDER_UNAVAILABLE'])
        result = case.run(nvidia_transport=send, call_trace=trace)
        self.assertEqual(result['outcome'], 'candidate_profile')
        names = [row[0]['response_format']['json_schema']['name'] for row in send.attempts]
        self.assertEqual(names, [OPERATION, 'agentfit_candidate_label_review', COVERAGE, COVERAGE])
        self.assertEqual(send.attempts[-2], send.attempts[-1])
        self.assertEqual(trace[0], {'prior': True})
        self.assertEqual([row['call_index'] for row in trace[1:]], [1, 2, 3, 4, 5])
        self.assertEqual([row['attempt'] for row in trace[1:]], [1, 1, 1, 1, 2])
        self.assertEqual([row['retry_of_call_index'] for row in trace[1:]], [None] * 4 + [4])
        self.assertEqual(sum(p['response_format']['json_schema']['name'] == 'agentfit_candidate_labels'
                             for p in case.requests), 1)

    def test_second_failure_stops_and_preserves_both_attempts(self):
        for second in ('PROVIDER_UNAVAILABLE', 'PROVIDER_AUTH'):
            with self.subTest(second=second):
                self.wait.reset_mock()
                case, trace = ProviderFixture(1), []
                send = FaultTransport(case, OPERATION, ['PROVIDER_UNAVAILABLE', second])
                with self.assertRaises(CandidatePipelineError) as caught:
                    case.run(nvidia_transport=send, call_trace=trace)
                self.assertEqual(caught.exception.provider_code, second)
                self.assertEqual(len(send.attempts), 2)
                self.assertEqual([r['provider_error'] for r in trace], ['PROVIDER_UNAVAILABLE', second])
                self.assertFalse(any(r['transport_completed'] for r in trace))
                self.wait.assert_called_once_with(2.0)

    def test_noneligible_errors_and_solar_do_not_retry(self):
        for code in ('PROVIDER_AUTH', 'PROVIDER_RATE_LIMIT', 'PROVIDER_TIMEOUT',
                     'PROVIDER_NETWORK', 'PROVIDER_REDIRECT', 'PROVIDER_MODEL',
                     'INVALID_RESPONSE', 'INCOMPLETE_RESPONSE', 'RESPONSE_TOO_LARGE',
                     'PROVIDER_FAILURE'):
            with self.subTest(code=code):
                case = ProviderFixture(1)
                send = FaultTransport(case, OPERATION, [code])
                with self.assertRaises(CandidatePipelineError):
                    case.run(nvidia_transport=send)
                self.assertEqual(len(send.attempts), 1)
        case = ProviderFixture(1)
        send = FaultTransport(case, 'agentfit_candidate_labels', ['PROVIDER_UNAVAILABLE'])
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(solar_transport=send)
        self.assertEqual(caught.exception.stage, 'CLASSIFICATION_FAILED')
        self.assertEqual(len(send.attempts), 1)
        self.wait.assert_not_called()

    def test_disable_and_invalid_configuration_do_not_start_extra_io(self):
        case = ProviderFixture(1)
        send = FaultTransport(case, OPERATION, ['PROVIDER_UNAVAILABLE'])
        with self.assertRaises(CandidatePipelineError):
            case.run(nvidia_transport=send, nvidia_retry_limit=0)
        self.assertEqual(len(send.attempts), 1)
        for invalid in (True, False, -1, 2, 1.0, None, '1'):
            case = ProviderFixture(1)
            touched = []
            def extractor(*args, **kwargs):
                touched.append(True)
                raise AssertionError('must reject before extraction')
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                case.run(extractor=extractor, nvidia_retry_limit=invalid)
            self.assertEqual(touched, [])
            self.assertEqual(case.requests, [])
        self.wait.assert_not_called()

    def test_budget_counts_failed_and_retried_attempts_and_never_waits_without_budget(self):
        for limit, schema, stage, waits in (
            (1, OPERATION, 'OPERATION_EXTRACTION_FAILED', 0),
            (2, OPERATION, 'CLASSIFICATION_FAILED', 1),
            (4, COVERAGE, 'COVERAGE_REVIEW_FAILED', 0)):
            with self.subTest(limit=limit):
                self.wait.reset_mock()
                case, trace = ProviderFixture(1), []
                send = FaultTransport(case, schema, ['PROVIDER_UNAVAILABLE'])
                with self.assertRaises(CandidatePipelineError) as caught:
                    case.run(nvidia_transport=send, max_calls=limit, call_trace=trace)
                self.assertEqual((caught.exception.stage, caught.exception.detail),
                                 (stage, 'CALL_BUDGET_EXCEEDED'))
                self.assertEqual(len(trace), limit)
                self.assertEqual(len(case.requests) + send.failed, limit)
                self.assertEqual(self.wait.call_count, waits)
        case, trace = ProviderFixture(1), []
        send = FaultTransport(case, COVERAGE, ['PROVIDER_UNAVAILABLE'])
        self.assertEqual(case.run(nvidia_transport=send, max_calls=5, call_trace=trace)['outcome'],
                         'candidate_profile')
        self.assertEqual(len(trace), 5)

    def test_transport_mutation_cannot_change_retry_request(self):
        case = ProviderFixture(1)
        send = FaultTransport(case, OPERATION, ['PROVIDER_UNAVAILABLE'], mutate=True)
        result = case.run(nvidia_transport=send)
        self.assertEqual(result['outcome'], 'candidate_profile')
        self.assertEqual(send.attempts[0], send.attempts[1])

    def test_invalid_output_and_semantic_findings_are_not_resampled(self):
        case = ProviderFixture(1, fail_name=COVERAGE, fail_reply=response(
            {'checkedFields': [], 'missingFields': []}, model='z-ai/glm-5.3'))
        trace = []
        with self.assertRaises(CandidatePipelineError):
            case.run(call_trace=trace)
        self.assertEqual(len(case.requests), 4)
        self.assertTrue(trace[-1]['transport_completed'])
        case = ProviderFixture(1, missing=['domain'])
        self.assertEqual(case.run()['outcome'], 'needs_confirmation')
        self.assertEqual(len(case.requests), 4)
        self.wait.assert_not_called()

    def test_unknown_errors_never_expose_secrets_or_trigger_retry(self):
        for fault in (AnalysisError('private ' + NVIDIA_KEY), RuntimeError(SOLAR_KEY)):
            case, trace = ProviderFixture(1), []
            send = FaultTransport(case, OPERATION, [fault])
            with self.assertRaises(CandidatePipelineError):
                case.run(nvidia_transport=send, call_trace=trace)
            self.assertEqual(len(send.attempts), 1)
            serialized = json.dumps(trace)
            for forbidden in (NVIDIA_KEY, SOLAR_KEY, 'private', 'TestApp'):
                self.assertNotIn(forbidden, serialized)
        self.wait.assert_not_called()

    def test_interruption_during_backoff_does_not_send_again(self):
        case, trace = ProviderFixture(1), []
        send = FaultTransport(case, OPERATION, ['PROVIDER_UNAVAILABLE'])
        self.wait.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            case.run(nvidia_transport=send, call_trace=trace)
        self.assertEqual(len(send.attempts), 1)
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]['provider_error'], 'PROVIDER_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
