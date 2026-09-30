"""Strict source-free diagnostics across the real worker protocol boundary."""
import asyncio
from copy import deepcopy
import importlib
import importlib.util
import json
import sys
import unittest
from unittest.mock import patch


MODEL = 'deepseek-ai/deepseek-v4.1-flash'
VERSION = 'analysis-call-metadata-v1'


def call(index=1, **changes):
    return dict(stage='EXTRACTION_FAILED', provider='nvidia', requested_model=MODEL,
                call_index=index, elapsed_ms=123, response_bytes=None,
                transport_completed=False, attempt=1, retry_of_call_index=None,
                provider_error='PROVIDER_UNAVAILABLE', **changes)


class MetadataContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('agentfit_ai.analysis_call_metadata'))
        self.api = importlib.import_module('agentfit_ai.analysis_call_metadata')

    def test_available_and_unavailable_have_distinct_call_evidence(self):
        row = call()
        report = self.api.build_metadata([row], 'EXTRACTION_FAILED')
        self.assertEqual(report, {'version': VERSION, 'status': 'available', 'unavailableReason': None,
                                 'failureStage': 'EXTRACTION_FAILED', 'calls': [row]})
        checked = self.api.validate_metadata(report)
        checked['calls'][0]['elapsed_ms'] = 0
        self.assertEqual(report['calls'][0]['elapsed_ms'], 123)
        missing = self.api.unavailable_metadata('ANALYSIS_DEADLINE_EXCEEDED')
        self.assertEqual(missing, {'version': VERSION, 'status': 'unavailable',
            'unavailableReason': 'ANALYSIS_DEADLINE_EXCEEDED', 'failureStage': None, 'calls': []})
        self.assertEqual(self.api.validate_metadata(missing), missing)

    def test_rejects_unknown_fields_private_values_and_inconsistent_types(self):
        report = self.api.build_metadata([call()], 'EXTRACTION_FAILED')
        mutations = [({'raw': 'private-document'}, None), ({'status': 'private-error'}, None),
            ({'failureStage': 'private-error'}, None), ({'unavailableReason': 'NOT_RETURNED'}, None),
            ({'version': 'bad'}, None)]
        mutations += [(None, changes) for changes in (
            {'raw': 'private-document'}, {'requested_model': 'private-key'}, {'provider': 'solar'},
            {'stage': 'private-error'}, {'call_index': True}, {'call_index': 2},
            {'elapsed_ms': -1}, {'elapsed_ms': float('nan')}, {'elapsed_ms': True},
            {'response_bytes': -1}, {'attempt': 2}, {'retry_of_call_index': 1},
            {'provider_error': 'private-error'}, {'transport_completed': 1},
            {'transport_completed': True}, {'response_bytes': 12})]
        for top, row in mutations:
            value = deepcopy(report)
            (value if top is not None else value['calls'][0]).update(top or row)
            with self.subTest(change=top or row), self.assertRaisesRegex(ValueError, '^INVALID_CALL_METADATA$'):
                self.api.validate_metadata(value)
        for reason in ('private-error', None):
            with self.assertRaisesRegex(ValueError, '^INVALID_CALL_METADATA$'):
                self.api.unavailable_metadata(reason)

    def test_call_limit_sequence_and_unavailable_cannot_claim_records(self):
        # Completed transport can precede a semantic parser failure.
        rows = [dict(call(i), transport_completed=True, response_bytes=200, provider_error=None)
                for i in range(1, 65)]
        self.assertEqual(len(self.api.build_metadata(rows)['calls']), 64)
        for calls in (rows + [dict(rows[-1], call_index=65)], [rows[0], rows[0]]):
            with self.assertRaisesRegex(ValueError, '^INVALID_CALL_METADATA$'):
                self.api.build_metadata(calls)
        missing = self.api.unavailable_metadata('NOT_RETURNED')
        missing['calls'] = [call()]
        with self.assertRaisesRegex(ValueError, '^INVALID_CALL_METADATA$'):
            self.api.validate_metadata(missing)


class WorkerMetadataTests(unittest.TestCase):
    def test_optional_worker_envelope_preserves_failure_stage_and_requested_model(self):
        from agentfit_ai.analysis_worker import execute_request
        from agentfit_ai.candidate_first_profile import CandidatePipelineError
        def fail(*args, **options):
            if options.get('call_trace') is not None:
                options['call_trace'].append(call())
            raise CandidatePipelineError('EXTRACTION_FAILED', 'PROVIDER_UNAVAILABLE')
        request = {'document': 'synthetic source', 'documentId': 'DOC', 'key': 'synthetic-key',
                   'mode': 'integrated-nvidia'}
        with patch('agentfit_ai.candidate_service_worker.find_spec', return_value=object()), patch(
                'agentfit_ai.candidate_service_worker.analyze_nvidia_candidates', side_effect=fail):
            plain = json.loads(execute_request(json.dumps(request).encode()))
            wrapped = json.loads(execute_request(json.dumps(dict(request, diagnostics=VERSION)).encode()))
        self.assertEqual(plain, {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_UNAVAILABLE'})
        self.assertEqual(set(wrapped), {'version', 'result', 'diagnostics'})
        self.assertEqual(wrapped['result'], plain)
        self.assertEqual(wrapped['diagnostics']['failureStage'], 'EXTRACTION_FAILED')
        self.assertEqual(wrapped['diagnostics']['calls'], [call()])
        for private in ('synthetic source', 'synthetic-key'):
            self.assertNotIn(private, json.dumps(wrapped))

    def test_worker_rejects_diagnostics_for_other_modes_before_analysis(self):
        from agentfit_ai.analysis_worker import execute_request, FAILED
        for mode, tag in ((None, VERSION), ('recoverable-solar', VERSION),
                          ('integrated-candidates', VERSION), ('integrated-nvidia', 'wrong')):
            request = {'document': 'source', 'documentId': 'DOC', 'key': 'key', 'diagnostics': tag}
            if mode is not None:
                request['mode'] = mode
            with self.subTest(mode=mode):
                self.assertEqual(execute_request(json.dumps(request).encode()), FAILED)


class ParentMetadataTests(unittest.IsolatedAsyncioTestCase):
    def command(self, body):
        return [sys.executable, '-c', 'import sys; sys.stdin.buffer.read(); sys.stdout.write(' + repr(json.dumps(body)) + ')']

    def envelope(self):
        from agentfit_ai.analysis_call_metadata import build_metadata
        return {'version': VERSION,
                'result': {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_UNAVAILABLE'},
                'diagnostics': build_metadata([call()], 'EXTRACTION_FAILED')}

    async def test_parent_accepts_valid_diagnostics_without_changing_public_result(self):
        from agentfit_ai.analysis_process import run_analysis_process
        report, body = {}, self.envelope()
        result = await run_analysis_process('source', 'DOC', 'key', asyncio.get_running_loop().time()+5,
            nvidia_only=True, call_diagnostics=report, command=self.command(body))
        self.assertEqual(result, body['result'])
        self.assertEqual(report, body['diagnostics'])

    async def test_parent_rejects_invalid_envelope_diagnostics_and_result_without_partial_trace(self):
        from agentfit_ai.analysis_process import run_analysis_process, AnalysisProcessError
        original = self.envelope()
        invalid = [original['result'], dict(original, extra='private'), dict(original, version='wrong'),
                   dict(original, result={'secret': 'private'})]
        for changed in ({'raw': 'private'}, {'failureStage': 'private'}, {'calls': [dict(call(), requested_model='key')]}):
            invalid.append(dict(original, diagnostics=dict(original['diagnostics'], **changed)))
        for body in invalid:
            report = {}
            with self.subTest(body=body), self.assertRaises(AnalysisProcessError):
                await run_analysis_process('source', 'DOC', 'key', asyncio.get_running_loop().time()+5,
                    nvidia_only=True, call_diagnostics=report, command=self.command(body))
            self.assertEqual(report['status'], 'unavailable')
            self.assertEqual(report['calls'], [])
            self.assertNotIn('private', json.dumps(report))
        with self.assertRaises(AnalysisProcessError):
            await run_analysis_process('source', 'DOC', 'key', asyncio.get_running_loop().time()+5,
                nvidia_only=True, command=self.command(original))

    async def test_invalid_collector_does_not_spawn_or_mutate_and_deadline_is_unknown(self):
        from agentfit_ai.analysis_process import run_analysis_process, AnalysisProcessError
        for collector, nvidia in (([], True), ({'keep': 'value'}, True), ({}, False)):
            before = deepcopy(collector)
            with patch('asyncio.create_subprocess_exec', side_effect=AssertionError('spawned')):
                with self.assertRaises(AnalysisProcessError):
                    await run_analysis_process('source', 'DOC', 'key', asyncio.get_running_loop().time()+5,
                        nvidia_only=nvidia, call_diagnostics=collector)
            self.assertEqual(collector, before)
        report = {}
        with self.assertRaisesRegex(AnalysisProcessError, '^ANALYSIS_DEADLINE_EXCEEDED$'):
            await run_analysis_process('source', 'DOC', 'key', asyncio.get_running_loop().time()+.2,
                nvidia_only=True, call_diagnostics=report,
                command=[sys.executable, '-c', 'import time; time.sleep(10)'])
        self.assertEqual(report['status'], 'unavailable')
        self.assertEqual(report['unavailableReason'], 'ANALYSIS_DEADLINE_EXCEEDED')
        self.assertEqual(report['calls'], [])


if __name__ == '__main__':
    unittest.main()
