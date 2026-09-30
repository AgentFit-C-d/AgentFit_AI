import importlib
import importlib.util
import asyncio
import io
import json
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.independent_evaluation_fixtures import write_json
from tests.nvidia_evaluation_fixtures import make_variant, make_access


class NvidiaPreflightTests(unittest.TestCase):
    def setUp(self):
        name = 'agentfit_ai.nvidia_evaluation_inputs'
        self.assertIsNotNone(importlib.util.find_spec(name), 'NVIDIA preflight is not implemented')
        self.api = importlib.import_module(name)

    def test_preflight_preserves_ten_documents_and_never_claims_new_holdout(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(self.api, 'ROOT', Path(temp)):
            paths = make_variant(temp)
            before = [p.read_bytes() for p in paths]
            result = self.api.prepare_evaluation(*paths)
            self.assertEqual(len(result['cases']), 10)
            self.assertEqual(sum(len(f['units']) for c in result['cases'] for f in c['gold']['fields'].values()), 10)
            meta = result['metadata']
            self.assertEqual(meta['version'], 'nvidia-only-evaluation-run-v1')
            self.assertEqual(meta['runs_per_case'], 3)
            self.assertEqual(meta['settings']['extraction_model'], 'deepseek-ai/deepseek-v4.1-flash')
            self.assertEqual(meta['settings']['nvidia_retry_limit'], 0)
            self.assertEqual(meta['baseline_status'], 'incomplete')
            self.assertFalse(meta['new_holdout'])
            self.assertFalse(meta['human_reviewed'])
            self.assertFalse(meta['release_gate_passed'])
            self.assertNotIn('React', json.dumps(meta))
            self.assertEqual(before, [p.read_bytes() for p in paths])
            self.assertEqual(self.api.build_freeze(paths[0], paths[1]), self.api.read_json(paths[2]))

    def test_code_source_gold_and_settings_drift_are_rejected(self):
        for kind in ('code', 'added', 'removed', 'source', 'gold', 'corpus', 'settings', 'file-set'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp, patch.object(self.api, 'ROOT', Path(temp)):
                paths = make_variant(temp)
                root = Path(temp)
                if kind == 'code': (root/'ai_service/agentfit_ai/base.py').write_text('changed')
                elif kind == 'added': (root/'ai_service/agentfit_ai/new.py').write_text('new')
                elif kind == 'removed': (root/'ai_service/agentfit_ai/base.py').unlink()
                elif kind == 'source': (root/'source/PUBLIC-01.md').write_text('changed')
                elif kind == 'gold': paths[1].write_text('{}')
                elif kind == 'corpus':
                    data = self.api.read_json(paths[0]); data['cases'].reverse(); write_json(paths[0], data)
                else:
                    data = self.api.read_json(paths[2])
                    if kind == 'settings': data['settings']['nvidia_retry_limit'] = 1
                    else: data['lf_normalized_files'].pop('ai_service/agentfit_ai/base.py')
                    write_json(paths[2], data)
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
                    self.api.prepare_evaluation(*paths)

    def test_only_nvidia_key_is_required_and_invalid_keys_are_not_echoed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'keys.env'
            path.write_text('UPSTAGE_API_KEY=\nNVIDIA_API_KEY="synthetic-nvidia-secret"\n')
            self.assertEqual(self.api.load_nvidia_key(path), 'synthetic-nvidia-secret')
            for content in ('UPSTAGE_API_KEY=unused', 'NVIDIA_API_KEY=\n',
                            'NVIDIA_API_KEY=secret\nNVIDIA_API_KEY=other', 'NVIDIA_API_KEY="broken'):
                path.write_text(content)
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_KEYS$'):
                    self.api.load_nvidia_key(path)

    def test_free_access_requires_exact_current_no_charge_scope_and_budget(self):
        now = datetime.now(timezone.utc)
        invalid = ({'confirmed_no_additional_charge': False}, {'confirmed_no_additional_charge': 1},
            {'endpoint': 'https://paid.example.com/v1/chat/completions'}, {'models': ['solar-pro4']},
            {'models': ['z-ai/glm-5.3', 'z-ai/glm-5.3']}, {'max_model_calls': True},
            {'max_model_calls': 63}, {'max_model_calls': 1921}, {'expires_at': 'broken'},
            {'expires_at': (now - timedelta(seconds=1)).isoformat()}, {'expires_at': '2099-01-01T00:00:00'},
            {'evidence': ''}, {'extra': 'not allowed'})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'access.json'
            make_access(path, max_model_calls=64)
            self.api.validate_free_access(path, reserved_calls=64, now=now)
            with self.assertRaisesRegex(ValueError, '^FREE_ACCESS_BUDGET_EXHAUSTED$'):
                self.api.validate_free_access(path, reserved_calls=128, now=now)
            for changes in invalid:
                make_access(path, **changes)
                with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, '^FREE_ACCESS_UNCONFIRMED$'):
                    self.api.validate_free_access(path, reserved_calls=64, now=now)


class NvidiaCliTests(unittest.TestCase):
    def setUp(self):
        name = 'agentfit_ai.nvidia_evaluation_runner'
        self.assertIsNotNone(importlib.util.find_spec(name), 'NVIDIA evaluator is not implemented')
        self.api = importlib.import_module(name)

    def test_default_preflight_does_not_read_keys_write_results_or_run_models(self):
        from agentfit_ai import nvidia_evaluation_inputs as inputs
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            paths = make_variant(temp)
            args = [piece for name, path in zip(('corpus', 'gold', 'freeze'), paths) for piece in ('--'+name, str(path))]
            out = io.StringIO()
            with patch.object(self.api, 'load_nvidia_key', side_effect=AssertionError('keys read')):
                with patch.object(self.api, 'evaluate', side_effect=AssertionError('live called')):
                    with redirect_stdout(out): code = self.api.main(args)
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertEqual(result['mode'], 'preflight')
            self.assertEqual(result['cases'], 10)
            self.assertEqual(result['expected'], 30)
            self.assertFalse(result['release_gate_passed'])
            self.assertNotIn('React', out.getvalue())

    def test_live_without_free_confirmation_never_reads_key(self):
        from agentfit_ai import nvidia_evaluation_inputs as inputs
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            paths = make_variant(temp)
            args = ['--live', '--env-file', 'MISSING', '--output', str(Path(temp)/'out')]
            args += [piece for name, path in zip(('corpus', 'gold', 'freeze'), paths) for piece in ('--'+name, str(path))]
            with patch.object(self.api, 'load_nvidia_key', side_effect=AssertionError('keys read')):
                out = io.StringIO()
                with redirect_stdout(out): code = self.api.main(args)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out.getvalue()), {'error': 'FREE_ACCESS_UNCONFIRMED'})
            self.assertFalse((Path(temp)/'out').exists())


class NvidiaCheckpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        name = 'agentfit_ai.nvidia_evaluation_runner'
        self.assertIsNotNone(importlib.util.find_spec(name), 'NVIDIA evaluator is not implemented')
        self.api = importlib.import_module(name)
        self.inputs = importlib.import_module('agentfit_ai.nvidia_evaluation_inputs')

    async def success(self, document, document_id, gold, key):
        from agentfit_ai.candidate_confirmation import project_candidate_confirmation
        from agentfit_ai.profile import FIELDS, validate_profile
        from agentfit_ai.independent_profile_evaluation import score_confirmation
        self.assertEqual(key, 'synthetic-nvidia-secret')
        data, evidence = dict.fromkeys(FIELDS), {f: [] for f in FIELDS}
        data['frontend'], evidence['frontend'] = ['React'], [{'start': 0, 'end': 5}]
        profile = validate_profile(document, document_id, {'data': data, 'evidence': evidence})
        outcome = project_candidate_confirmation(document, document_id, {'outcome': 'candidate_profile',
            'profile': profile, 'unresolvedFields': [], 'candidateCount': 1, 'rejectedCandidateCount': 0,
            'rejectedReasons': {}, 'reviewIssueCount': 0})
        return score_confirmation(document, document_id, gold, outcome)

    async def test_thirty_scores_and_resume_preserve_denominator_without_text_or_keys(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(self.inputs, 'ROOT', Path(temp)):
            prepared = self.inputs.prepare_evaluation(*make_variant(temp))
            access = make_access(Path(temp)/'access.json')
            output = Path(temp)/'results'
            with patch.object(self.api, 'run_scored_process', side_effect=self.success) as calls:
                result = await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
            self.assertEqual(calls.call_count, 30)
            self.assertEqual(result['completed'], 30)
            self.assertEqual(result['fields']['frontend']['matched'], 30)
            self.assertEqual(result['fields']['frontend']['gold'], 30)
            self.assertEqual(result['reserved_model_calls_upper_bound'], 1920)
            self.assertFalse(result['release_gate_passed'])
            snapshots = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertEqual(len(snapshots), 61)
            for value in ('React', 'synthetic-nvidia-secret', 'SYNTHETIC TEST ONLY'):
                self.assertNotIn(value, repr(snapshots))
            with patch.object(self.api, 'run_scored_process', side_effect=AssertionError('replayed')):
                resumed = await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
            self.assertEqual(result, resumed)
            self.assertEqual(snapshots, {p.name: p.read_bytes() for p in output.iterdir()})

    async def test_provider_failure_is_saved_and_stops_this_and_resumed_evaluation(self):
        from agentfit_ai.independent_profile_evaluation import score_confirmation
        for code in ('PROVIDER_RATE_LIMIT', 'PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT'):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temp, patch.object(self.inputs, 'ROOT', Path(temp)):
                prepared = self.inputs.prepare_evaluation(*make_variant(temp))
                access = make_access(Path(temp)/'access.json')
                output = Path(temp)/'results'
                async def failed(doc, ident, gold, key):
                    return score_confirmation(doc, ident, gold, {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': code})
                with patch.object(self.api, 'run_scored_process', side_effect=failed) as calls:
                    with self.assertRaisesRegex(ValueError, '^EVALUATION_PROVIDER_STOPPED$'):
                        await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                self.assertEqual(calls.call_count, 1)
                saved = json.loads((output/'PUBLIC-01-run-0.json').read_text())
                self.assertEqual(saved['score']['error'], code)
                self.assertEqual(saved['score']['fields']['frontend']['missing'], 1)
                before = {p.name: p.read_bytes() for p in output.iterdir()}
                with patch.object(self.api, 'run_scored_process', side_effect=AssertionError('replayed')):
                    with self.assertRaisesRegex(ValueError, '^EVALUATION_PROVIDER_STOPPED$'):
                        await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    async def test_reservation_budget_expiry_and_input_drift_stop_before_next_request(self):
        for kind, expected in (('budget', 'FREE_ACCESS_BUDGET_EXHAUSTED'),
                ('expiry', 'FREE_ACCESS_UNCONFIRMED'), ('source', 'INVALID_EVALUATION_PREFLIGHT')):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp, patch.object(self.inputs, 'ROOT', Path(temp)):
                prepared = self.inputs.prepare_evaluation(*make_variant(temp))
                access = make_access(Path(temp)/'access.json', max_model_calls=64 if kind=='budget' else 1920)
                output = Path(temp)/'results'
                async def provider(*args):
                    score = await self.success(*args)
                    if kind == 'expiry': make_access(access, expires_at='2000-01-01T00:00:00+00:00')
                    if kind == 'source': (Path(temp)/'source/PUBLIC-12.md').write_text('changed')
                    return score
                with patch.object(self.api, 'run_scored_process', side_effect=provider) as calls:
                    with self.assertRaisesRegex(ValueError, '^'+expected+'$'):
                        await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                self.assertEqual(calls.call_count, 1)
                self.assertTrue((output/'PUBLIC-01-run-0.json').exists())
                self.assertFalse((output/'PUBLIC-01-run-1.started.json').exists())

    async def test_interrupted_mixed_or_corrupt_results_cannot_launch(self):
        for kind in ('interrupted', 'mixed', 'corrupt'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp, patch.object(self.inputs, 'ROOT', Path(temp)):
                prepared = self.inputs.prepare_evaluation(*make_variant(temp))
                access = make_access(Path(temp)/'access.json')
                output = Path(temp)/'results'
                if kind == 'mixed':
                    output.mkdir(); write_json(output/'experiment.json', {'version': 'independent-evaluation-run-v1'})
                elif kind == 'interrupted':
                    with patch.object(self.api, 'run_scored_process', side_effect=asyncio.CancelledError):
                        with self.assertRaises(asyncio.CancelledError):
                            await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                else:
                    make_access(access, max_model_calls=64)
                    with patch.object(self.api, 'run_scored_process', side_effect=self.success):
                        with self.assertRaises(ValueError):
                            await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                    saved = output/'PUBLIC-01-run-0.json'
                    row = json.loads(saved.read_text()); row['score']['raw'] = 'forbidden'; write_json(saved, row)
                before = {p.name: p.read_bytes() for p in output.iterdir()}
                with patch.object(self.api, 'run_scored_process', side_effect=AssertionError('launched')):
                    with self.assertRaises(ValueError):
                        await self.api.evaluate(prepared, output, 'synthetic-nvidia-secret', access)
                self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})

    async def test_invalid_gold_key_or_timeout_is_rejected_before_spawn(self):
        from tests.test_independent_profile_evaluation import DOCUMENT, gold_fixture
        for key, timeout in (('', 1800), ('React', 1800), ('synthetic-nvidia-secret', True),
                             ('synthetic-nvidia-secret', 1801), ('synthetic-nvidia-secret', float('nan'))):
            with self.subTest(key=key, timeout=timeout), patch.object(asyncio, 'create_subprocess_exec', side_effect=AssertionError('spawned')):
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_INPUT$'):
                    await self.api.run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(), key, timeout_seconds=timeout)
        with patch.object(asyncio, 'create_subprocess_exec', side_effect=AssertionError('spawned')):
            with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_INPUT$'):
                await self.api.run_scored_process(DOCUMENT, 'PUBLIC-99', gold_fixture(), 'synthetic-nvidia-secret')
