import asyncio
import importlib
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import unittest

from tests.test_independent_profile_evaluation import DOCUMENT, gold_fixture
from tests.independent_evaluation_fixtures import make_evaluation, write_json
from agentfit_ai.candidate_confirmation import project_candidate_confirmation
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.independent_profile_evaluation import score_confirmation
from agentfit_ai import independent_evaluation_inputs as inputs


class EvaluationCliTests(unittest.TestCase):
    def test_live_opt_in_precedes_all_input_and_secret_reads(self):
        from agentfit_ai import independent_evaluation_runner as api
        args = [part for name in ('env-file', 'corpus', 'gold', 'freeze', 'output')
                for part in ('--' + name, 'missing-file')]
        output = io.StringIO()
        with patch.object(api, 'prepare_evaluation') as prepare, patch.object(api, 'load_keys') as keys:
            with redirect_stdout(output):
                code = api.main(args)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(output.getvalue()), {'error': 'LIVE_REQUIRED'})
            prepare.assert_not_called()
            keys.assert_not_called()


class ScoredProcessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        name = 'agentfit_ai.independent_evaluation_runner'
        self.assertIsNotNone(importlib.util.find_spec(name), 'scored process not implemented')
        self.api = importlib.import_module(name)

    async def run_child(self, mode, timeout=10):
        command = [sys.executable, str(Path(__file__).parent / 'fixtures/independent_evaluation_child.py'), mode]
        return await self.api.run_scored_process(DOCUMENT, 'PUBLIC-01', gold_fixture(),
            'unit-solar-secret', 'unit-nvidia-secret', timeout_seconds=timeout, command=command)

    async def test_real_child_uses_stdin_secrets_and_returns_only_score(self):
        result = await self.run_child('valid')
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['fields']['frontend']['matched'], 1)

    async def test_bad_or_dead_child_becomes_failed_row_with_gold_missing(self):
        for mode in ('malformed', 'oversized', 'exit'):
            with self.subTest(mode=mode):
                result = await self.run_child(mode)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['error'], 'ANALYSIS_FAILURE')
                self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 2)

    async def test_timeout_reaps_actual_child_and_preserves_denominator(self):
        original, children = asyncio.create_subprocess_exec, []
        async def create(*args, **kwargs):
            child = await original(*args, **kwargs)
            children.append(child)
            return child
        with patch.object(asyncio, 'create_subprocess_exec', side_effect=create):
            result = await self.run_child('hang', 0.3)
        self.assertEqual(result['error'], 'ANALYSIS_DEADLINE')
        self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 2)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].returncode)

    async def test_cancellation_reaps_actual_child(self):
        original, children, ready = asyncio.create_subprocess_exec, [], asyncio.Event()
        async def create(*args, **kwargs):
            child = await original(*args, **kwargs)
            children.append(child)
            ready.set()
            return child
        with patch.object(asyncio, 'create_subprocess_exec', side_effect=create):
            task = asyncio.create_task(self.run_child('hang'))
            await asyncio.wait_for(ready.wait(), 5)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNotNone(children[0].returncode)

    async def test_invalid_request_cannot_launch_a_child(self):
        with patch.object(asyncio, 'create_subprocess_exec') as create:
            with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_INPUT$'):
                await self.api.run_scored_process(DOCUMENT, 'PUBLIC-99', gold_fixture(),
                    'unit-solar-secret', 'unit-nvidia-secret')
            create.assert_not_called()


class CheckpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api = importlib.import_module('agentfit_ai.independent_evaluation_runner')
        self.assertTrue(hasattr(self.api, 'evaluate'), 'checkpoint evaluation not implemented')

    async def success(self, document, document_id, gold, solar_key, nvidia_key):
        self.assertEqual(solar_key, 'unit-solar-secret')
        data, evidence = dict.fromkeys(FIELDS), {f: [] for f in FIELDS}
        data['frontend'], evidence['frontend'] = ['React'], [{'start': 0, 'end': 5}]
        profile = validate_profile(document, document_id, {'data': data, 'evidence': evidence})
        outcome = project_candidate_confirmation(document, document_id, {
            'outcome': 'candidate_profile', 'profile': profile, 'unresolvedFields': [],
            'candidateCount': 2, 'rejectedCandidateCount': 0, 'rejectedReasons': {}, 'reviewIssueCount': 0})
        return score_confirmation(document, document_id, gold, outcome)

    async def test_thirty_rows_include_failure_and_resume_without_calls_or_raw_output(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            prepared = self.api.prepare_evaluation(*make_evaluation(temp))
            calls = []
            async def provider(*args):
                calls.append(args[1])
                if len(calls) == 1:
                    return score_confirmation(args[0], args[1], args[2],
                        {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'PROVIDER_TIMEOUT'})
                return await self.success(*args)
            output = Path(temp)/'results'
            with patch.object(self.api, 'run_scored_process', side_effect=provider):
                result = await self.api.evaluate(prepared, output, 'unit-solar-secret', 'unit-nvidia-secret')
            self.assertEqual(len(calls), 30)
            self.assertEqual(result['completed'], 30)
            self.assertEqual(result['failed'], 1)
            self.assertEqual(result['fields']['frontend']['gold'], 30)
            self.assertEqual(result['fields']['frontend']['matched'], 29)
            self.assertEqual(result['fields']['frontend']['missing'], 1)
            self.assertFalse(result['release_gate_passed'])
            self.assertEqual(len(list(output.glob('*.json'))), 61)
            originals = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertNotIn('unit-solar-secret', repr(originals))
            self.assertNotIn('React', repr(originals))
            with patch.object(self.api, 'run_scored_process') as provider:
                resumed = await self.api.evaluate(prepared, output, 'unit-solar-secret', 'unit-nvidia-secret')
                provider.assert_not_called()
            self.assertEqual(resumed, result)
            self.assertEqual(originals, {p.name: p.read_bytes() for p in output.iterdir()})

    async def test_interrupted_started_record_refuses_rerun(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            prepared = self.api.prepare_evaluation(*make_evaluation(temp))
            output = Path(temp)/'results'
            with patch.object(self.api, 'run_scored_process', side_effect=asyncio.CancelledError):
                with self.assertRaises(asyncio.CancelledError):
                    await self.api.evaluate(prepared, output, 'unit-solar-secret', 'unit-nvidia-secret')
            self.assertTrue((output/'PUBLIC-01-run-0.started.json').exists())
            self.assertFalse((output/'PUBLIC-01-run-0.json').exists())
            with patch.object(self.api, 'run_scored_process') as provider:
                with self.assertRaisesRegex(ValueError, '^INCOMPLETE_RUN$'):
                    await self.api.evaluate(prepared, output, 'unit-solar-secret', 'unit-nvidia-secret')
                provider.assert_not_called()

    async def test_corrupt_final_checkpoint_is_rejected_before_any_new_call(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            prepared = self.api.prepare_evaluation(*make_evaluation(temp))
            output = Path(temp)/'results'
            with patch.object(self.api, 'run_scored_process', side_effect=self.success):
                await self.api.evaluate(prepared, output, 'unit-solar-secret', 'unit-nvidia-secret')
            final = output/'PUBLIC-12-run-2.json'
            row = json.loads(final.read_text()); row['score']['raw'] = 'SECRET'; write_json(final, row)
            with patch.object(self.api, 'run_scored_process') as provider:
                with self.assertRaisesRegex(ValueError, '^INVALID_CHECKPOINT$'):
                    await self.api.evaluate(prepared, output, 'unit-solar-secret', 'unit-nvidia-secret')
                provider.assert_not_called()

    async def test_settings_mismatch_and_source_drift_do_not_launch(self):
        for change in ('manifest', 'source'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
                prepared = self.api.prepare_evaluation(*make_evaluation(temp))
                output = Path(temp)/'results'; output.mkdir()
                if change == 'manifest': write_json(output/'experiment.json', {'wrong': True})
                else: (Path(temp)/'source/PUBLIC-01.md').write_text('changed')
                with patch.object(self.api, 'run_scored_process') as provider:
                    with self.assertRaises(ValueError):
                        await self.api.evaluate(prepared, output, 'unit-solar-secret', 'unit-nvidia-secret')
                    provider.assert_not_called()

    async def test_source_changed_after_one_call_stops_remaining_calls(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(inputs, 'ROOT', Path(temp)):
            prepared = self.api.prepare_evaluation(*make_evaluation(temp))
            async def provider(*args):
                result = await self.success(*args)
                (Path(temp)/'source/PUBLIC-12.md').write_text('changed')
                return result
            with patch.object(self.api, 'run_scored_process', side_effect=provider) as calls:
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
                    await self.api.evaluate(prepared, Path(temp)/'results', 'unit-solar-secret', 'unit-nvidia-secret')
                self.assertEqual(calls.call_count, 1)
