"""Evaluation boundary with installed LangExtract and real local HTTP/SSE."""
import asyncio
import hashlib
import json
import os
import sys
import unittest
from unittest.mock import patch

from agentfit_ai.independent_evaluation_runner import run_scored_process
from test_integrated_runtime import DOCUMENT, FACTS, NVIDIA_KEY, SOLAR_KEY
from test_integrated_service import Provider, SHIM, provider_server


def gold_fixture():
    fields = {}
    for index, (value, field) in enumerate(FACTS):
        start = DOCUMENT.index(value)
        fields[field] = {'assessment': 'enumerated', 'units': [
            {'id': f'U{index:03}', 'kind': 'present',
             'spans': [{'start': start, 'end': start + len(value)}]}]}
    return {'case_id': 'PUBLIC-01', 'source_sha256': hashlib.sha256(DOCUMENT.encode()).hexdigest(),
            'human_reviewed': False, 'fields': fields, 'exclusions': [], 'ambiguities': []}


class EvaluationRuntimeTests(unittest.TestCase):
    def run_provider(self, provider):
        with provider_server(provider) as endpoint, patch.dict(os.environ, {
                'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
            return asyncio.run(run_scored_process(
                DOCUMENT, 'PUBLIC-01', gold_fixture(), SOLAR_KEY, NVIDIA_KEY,
                timeout_seconds=30, command=[sys.executable, str(SHIM), endpoint, 'evaluation']))

    def test_installed_sdk_and_real_http_emit_ten_scores_without_source_or_secrets(self):
        provider = Provider()
        result = self.run_provider(provider)
        self.assertEqual(result['status'], 'valid')
        self.assertEqual(result['questions'], 10)
        self.assertEqual(sum(f['matched'] for f in result['fields'].values()), 10)
        self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 0)
        self.assertFalse(result['release_gate_passed'])
        self.assertEqual(provider.names, ['agentfit_langextract_candidates',
            'agentfit_operation_candidates', 'agentfit_candidate_labels',
            'agentfit_candidate_label_review', 'agentfit_candidate_source_coverage'])
        self.assertEqual(provider.errors, [])
        for forbidden in (DOCUMENT, SOLAR_KEY, NVIDIA_KEY, 'TestApp', 'React'):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_malformed_remote_extraction_retains_all_gold_as_missing(self):
        class MalformedProvider(Provider):
            def reply(self, payload):
                super().reply(payload)
                return {'private_model_response': 'unit-private-model-text'}
        provider = MalformedProvider()
        result = self.run_provider(provider)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(sum(f['gold'] for f in result['fields'].values()), 10)
        self.assertEqual(sum(f['missing'] for f in result['fields'].values()), 10)
        self.assertEqual(provider.names, ['agentfit_langextract_candidates'])
        self.assertEqual(provider.errors, [])
        self.assertNotIn('unit-private-model-text', json.dumps(result))
