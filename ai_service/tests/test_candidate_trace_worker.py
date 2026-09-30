"""The probe must preserve the ordinary worker result and isolate sidecar failures."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai import candidate_service_worker as service
from agentfit_ai.analysis_call_metadata import METADATA_VERSION
from agentfit_ai.analysis_worker import FAILED, execute_request
from agentfit_ai.candidate_first_profile import CandidatePipelineError, finalize_candidate_analysis
from agentfit_ai.profile import FIELDS
from diagnostic_tools.candidate_trace import CandidateTrace
from tests.test_analysis_call_metadata import call

MODEL = 'deepseek-ai/deepseek-v4.1-flash'
SOURCE, KEY = 'Export CSV', 'unit-nvidia-secret'


def worker_module():
    try:
        return importlib.import_module('diagnostic_tools.candidate_trace_worker')
    except ModuleNotFoundError as error:
        if error.name != 'diagnostic_tools.candidate_trace_worker':
            raise
        raise AssertionError('candidate trace worker is not implemented') from None


def packet(**changes):
    return json.dumps({'document': SOURCE, 'documentId': 'PUBLIC-01', 'key': KEY,
        'mode': 'integrated-nvidia', 'diagnostics': METADATA_VERSION, 'reviewModel': MODEL,
        **changes}).encode()


def fake_pipeline(invocations, fail=False):
    # Replace external model work only; worker validation/projection/metadata stay real.
    def analyze(document, document_id, key, *, observer=None, call_trace=None, **options):
        invocations.append((document_id, options.get('review_model')))
        frozen = {'candidates': [{'id': 'C000', 'start': 0, 'end': 10}], 'rejected': []}
        labels = [{'id': 'C000', 'field': 'features', 'status': 'confirmed'}]
        if observer:
            observer('grounded', deepcopy(frozen))
            observer('classified', {'frozen': deepcopy(frozen), 'labels': deepcopy(labels)})
        if fail:
            call_trace.append(dict(call(), stage='COVERAGE_REVIEW_FAILED'))
            raise CandidatePipelineError('COVERAGE_REVIEW_FAILED', 'PROVIDER_UNAVAILABLE')
        call_trace.append(dict(call(), provider_error=None, transport_completed=True, response_bytes=17))
        return finalize_candidate_analysis(document, document_id, frozen, labels,
            {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': []}, observer=observer)
    return analyze


class TraceWorkerTests(unittest.TestCase):
    def test_worker_preserves_result_and_restores_original_callable(self):
        api, invoked = worker_module(), []
        original = fake_pipeline(invoked)
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', original):
            baseline = execute_request(packet())
            path = Path(folder) / 'trace.json'
            actual = api.execute_probe_request(packet(), path)
            self.assertEqual(actual, baseline)
            self.assertIs(service.analyze_nvidia_candidates, original)
            self.assertEqual(len(invoked), 2)
            report = api.validate_probe_report(SOURCE, 'PUBLIC-01', json.loads(path.read_text(encoding='utf-8')))
            self.assertEqual((report['status'], report['error'], report['trace']['status']), ('available', None, 'complete'))
            self.assertEqual(report['trace']['analysis']['candidateCount'], 1)
            for private in (SOURCE, KEY, 'Export', 'CSV'):
                self.assertNotIn(private, json.dumps(report))

    def test_observation_error_is_unavailable_and_does_not_change_result(self):
        api, invoked = worker_module(), []
        original = fake_pipeline(invoked)
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', original):
            baseline = execute_request(packet())
            path = Path(folder) / 'trace.json'
            with patch.object(CandidateTrace, 'observe', side_effect=ValueError('private-provider-response')):
                actual = api.execute_probe_request(packet(), path)
            self.assertEqual(actual, baseline)
            self.assertIs(service.analyze_nvidia_candidates, original)
            report = api.validate_probe_report(SOURCE, 'PUBLIC-01', json.loads(path.read_text()))
            self.assertEqual((report['status'], report['error'], report['trace']),
                             ('unavailable', 'OBSERVATION_FAILED', None))
            self.assertNotIn('private-provider-response', json.dumps(report))

    def test_partial_provider_failure_preserves_observed_prefix(self):
        api = worker_module()
        original = fake_pipeline([], fail=True)
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', original):
            baseline = execute_request(packet())
            path = Path(folder) / 'trace.json'
            self.assertEqual(api.execute_probe_request(packet(), path), baseline)
            report = api.validate_probe_report(SOURCE, 'PUBLIC-01', json.loads(path.read_text()))
            self.assertEqual(report['trace']['status'], 'partial')
            self.assertIsNotNone(report['trace']['stages']['classified'])
            self.assertIsNone(report['trace']['stages']['reviewed'])
            self.assertIsNone(report['trace']['stages']['projected'])
            self.assertIs(service.analyze_nvidia_candidates, original)

    def test_invalid_provider_scope_and_existing_file_never_enter_analysis(self):
        api, invoked = worker_module(), []
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', fake_pipeline(invoked)):
            path = Path(folder) / 'trace.json'
            for raw in (packet(mode='recoverable-solar'), packet(reviewModel='z-ai/glm-5.3'),
                        packet(diagnostics='unknown'), packet(documentId='private-id'), b'{}', b'not-json'):
                self.assertEqual(api.execute_probe_request(raw, path), FAILED)
                self.assertFalse(path.exists())
            path.write_bytes(b'existing-evidence')
            self.assertEqual(api.execute_probe_request(packet(), path), FAILED)
            self.assertEqual(path.read_bytes(), b'existing-evidence')
            self.assertEqual(invoked, [])

    def test_symlink_target_is_preserved_without_analysis(self):
        api, invoked = worker_module(), []
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', fake_pipeline(invoked)):
            root = Path(folder)
            target, link = root / 'evidence.json', root / 'linked.json'
            target.write_bytes(b'existing-evidence')
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('platform cannot create symlinks')
            self.assertEqual(api.execute_probe_request(packet(), link), FAILED)
            self.assertEqual(target.read_bytes(), b'existing-evidence')
            self.assertEqual(invoked, [])

    def test_write_failure_preserves_worker_stdout_and_callable(self):
        api, invoked = worker_module(), []
        original, path_open = fake_pipeline(invoked), Path.open
        class FailingWrite:
            def __init__(self, handle):
                self.handle = handle
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.handle.close()
            def write(self, data):
                raise OSError('private-disk-error')
        def broken_open(path, *args, **options):
            return FailingWrite(path_open(path, *args, **options))
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', original):
            baseline = execute_request(packet())
            path = Path(folder) / 'trace.json'
            with patch.object(Path, 'open', broken_open):
                actual = api.execute_probe_request(packet(), path)
            self.assertEqual(actual, baseline)
            self.assertFalse(path.exists())
            self.assertEqual(path.with_name(path.name + '.staged').read_bytes(), b'')
            self.assertIs(service.analyze_nvidia_candidates, original)

    def test_sensitive_input_guard_never_produces_source_trace(self):
        api, invoked = worker_module(), []
        source = SOURCE + KEY
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', fake_pipeline(invoked)):
            path = Path(folder) / 'trace.json'
            result = json.loads(api.execute_probe_request(packet(document=source), path))
            self.assertEqual(result['result']['error'], 'SENSITIVE_CONTENT')
            report = api.validate_probe_report(source, 'PUBLIC-01', json.loads(path.read_text()))
            self.assertEqual((report['status'], report['error'], report['trace']), ('unavailable', 'NOT_INVOKED', None))
            self.assertEqual(invoked, [])
            self.assertNotIn(KEY, json.dumps(report))

    def test_report_validator_rejects_forged_identity_or_raw_error(self):
        api = worker_module()
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', fake_pipeline([])):
            path = Path(folder) / 'trace.json'
            api.execute_probe_request(packet(), path)
            report = json.loads(path.read_text())
        for key, value in (('error', 'private-response'), ('sourceSha256', '0' * 64), ('documentId', 'PUBLIC-02'),
                           ('raw', 'private-response'), ('status', 'unavailable')):
            with self.assertRaises(ValueError):
                api.validate_probe_report(SOURCE, 'PUBLIC-01', {**report, key: value})

    def test_fsync_and_close_failures_never_publish_a_readable_trace(self):
        api = worker_module()
        original, path_open = fake_pipeline([]), Path.open
        class FailedClose:
            def __init__(self, handle):
                self.handle = handle
            def __enter__(self):
                return self.handle
            def __exit__(self, *args):
                self.handle.close()
                raise OSError('private-close-error')
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', original):
            expected = execute_request(packet())
            for kind in ('fsync', 'close'):
                with self.subTest(kind=kind):
                    path = Path(folder) / (kind + '.json')
                    failure = (patch.object(api.os, 'fsync', side_effect=OSError('private-fsync-error')) if kind == 'fsync'
                               else patch.object(Path, 'open', lambda p, *a, **kw: FailedClose(path_open(p, *a, **kw))))
                    with failure:
                        actual = api.execute_probe_request(packet(), path)
                    self.assertEqual(actual, expected)
                    self.assertIs(service.analyze_nvidia_candidates, original)
                    self.assertFalse(path.exists(), 'undurable trace was published as complete')

    def test_existing_staged_file_prevents_analysis_and_is_preserved(self):
        api, invoked = worker_module(), []
        with tempfile.TemporaryDirectory() as folder, patch.object(service, 'find_spec', return_value=object()), patch.object(
                service, 'analyze_nvidia_candidates', fake_pipeline(invoked)):
            path = Path(folder) / 'trace.json'
            staged = path.with_name(path.name + '.staged')
            staged.write_bytes(b'prior-incomplete-evidence')
            self.assertEqual(api.execute_probe_request(packet(), path), FAILED)
            self.assertEqual(staged.read_bytes(), b'prior-incomplete-evidence')
            self.assertFalse(path.exists())
            self.assertEqual(invoked, [])


if __name__ == '__main__':
    unittest.main()
