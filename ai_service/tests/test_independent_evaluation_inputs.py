import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from tests.independent_evaluation_fixtures import make_evaluation, write_json


class InputTests(unittest.TestCase):
    def setUp(self):
        name = 'agentfit_ai.independent_evaluation_inputs'
        self.assertIsNotNone(importlib.util.find_spec(name), 'evaluation preflight not implemented')
        self.api = importlib.import_module(name)

    def test_all_ten_inputs_prepared_with_typed_metadata(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(self.api, 'ROOT', Path(temp)):
            prepared = self.api.prepare_evaluation(*make_evaluation(temp))
            self.assertEqual(len(prepared['cases']), 10)
            self.assertEqual(prepared['metadata']['runs_per_case'], 3)
            self.assertNotIn('React', json.dumps(prepared['metadata']))
            self.assertEqual(prepared['cases'][0]['document'], 'React synthetic document 1')

    def test_modified_source_gold_code_and_missing_case_fail_preflight(self):
        for part in ('source', 'gold', 'code', 'case', 'settings', 'freeze_coverage'):
            with self.subTest(part=part), tempfile.TemporaryDirectory() as temp, patch.object(self.api, 'ROOT', Path(temp)):
                paths = make_evaluation(temp)
                if part == 'source': (Path(temp)/'source/PUBLIC-01.md').write_text('changed')
                elif part == 'gold': paths[1].write_text('{}')
                elif part == 'code': (Path(temp)/'ai_service/agentfit_ai/base.py').write_text('changed')
                elif part == 'case':
                    corpus = json.loads(paths[0].read_text()); corpus['cases'].pop(); write_json(paths[0], corpus)
                elif part == 'settings':
                    freeze = json.loads(paths[2].read_text()); freeze['settings']['max_calls'] = 6; write_json(paths[2], freeze)
                else:
                    freeze = json.loads(paths[2].read_text()); freeze['lf_normalized_files'] = {}; write_json(paths[2], freeze)
                with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_PREFLIGHT$'):
                    self.api.prepare_evaluation(*paths)

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'bad.json'
            path.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError): self.api.read_json(path)

    def test_env_keys_are_explicit_unique_and_not_filled_from_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'env'
            path.write_text('UPSTAGE_API_KEY="unit-solar-secret"\nNVIDIA_API_KEY=unit-nvidia-secret\n')
            self.assertEqual(self.api.load_keys(path), ('unit-solar-secret', 'unit-nvidia-secret'))
            for text in ('UPSTAGE_API_KEY=one\n', 'UPSTAGE_API_KEY=one\nUPSTAGE_API_KEY=two\nNVIDIA_API_KEY=three\n'):
                path.write_text(text)
                with patch.dict('os.environ', {'NVIDIA_API_KEY': 'must-not-use'}):
                    with self.assertRaisesRegex(ValueError, '^INVALID_EVALUATION_KEYS$'):
                        self.api.load_keys(path)
