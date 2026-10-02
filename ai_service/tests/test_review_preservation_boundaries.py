import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
from agentfit_ai.analysis_process import run_analysis_process, AnalysisProcessError
from agentfit_ai.analysis_worker import execute_request, FAILED
from agentfit_ai.http_service import create_app
from contract_mock.gateway import LocalAnalysisGateway
from contract_mock.schema import check_review, ContractError
from contract_mock.server import create_mock_app
from contract_mock.store import MockStore
from review_preservation_fixture import load, offline, replay, replay_providers

V3 = 'confirmation-v3'
V2 = 'confirmation-v2'
COMMAND = [sys.executable, '-X', 'utf8', str(Path(__file__).parent / 'fixtures/review_preservation_worker.py')]


class ReviewBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load('document.txt')
        cls.ident = load('trace.json')['documentId']

    def test_worker_explicit_v3_serializes_all_preserved_metadata(self):
        request = dict(document=self.doc, documentId=self.ident, key='OFFLINE-NONCREDENTIAL',
                       mode='integrated-nvidia', contract=V3)
        with replay_providers():
            actual = json.loads(execute_request(json.dumps(request).encode()))
        self.assertEqual(actual, replay(V3))

    def test_worker_rejects_unknown_version_option_and_wrong_mode_before_analysis(self):
        base = dict(document=self.doc, documentId=self.ident, key='OFFLINE-NONCREDENTIAL', mode='integrated-nvidia')
        changes = [{'contract': 'confirmation-v4'}, {'contract': ''}, {'preserveReview': 'true'},
                   {'contract': V3, 'mode': 'recoverable-solar'},
                   {'contract': V3, 'mode': 'integrated-candidates', 'nvidiaKey': 'OFFLINE-NONCREDENTIAL'}]
        with offline(), patch('agentfit_ai.candidate_service_worker.execute_nvidia_analysis') as call:
            for change in changes:
                with self.subTest(change=change):
                    self.assertEqual(execute_request(json.dumps({**base, **change}).encode()), FAILED)
            call.assert_not_called()

    def test_pipe_process_v3_and_legacy_v2(self):
        async def run(contract):
            opts = {} if contract == V2 else {'contract': contract}
            return await run_analysis_process(self.doc, self.ident, 'OFFLINE-NONCREDENTIAL',
                asyncio.get_running_loop().time() + 20, nvidia_only=True, command=COMMAND, **opts)
        with offline():
            self.assertEqual(asyncio.run(run(V2)), load('result.json'))
            self.assertEqual(asyncio.run(run(V3)), replay(V3))

    def test_http_default_worker_and_mock_gateway_forward_selected_version(self):
        async def worker(*args, **kwargs):
            return await run_analysis_process(*args, command=COMMAND, **kwargs)
        async def run(contract):
            app = create_app(internal_token='mock-internal', analysis_mode='integrated-nvidia')
            gateway = LocalAnalysisGateway(app, contract=contract)
            return await gateway.analyze('MARKDOWN', self.doc.encode(), self.ident, 'offline-request')
        with offline(), patch.dict('os.environ', {'NVIDIA_API_KEY': 'OFFLINE-NONCREDENTIAL'}), \
                patch('agentfit_ai.http_service.run_analysis_process', side_effect=worker):
            for contract in (V2, V3):
                with self.subTest(contract=contract):
                    result = asyncio.run(run(contract))
                    expected = load('result.json') if contract == V2 else replay(V3)
                    self.assertEqual(result['profile'], expected['profile'])
                    self.assertEqual(result['review'], {k: v for k, v in expected.items()
                        if k not in ('profile', 'outcome', 'error')})

    def test_http_rejects_unknown_duplicate_wrong_mode_and_response_version(self):
        async def run():
            for mode, contract, response_contract, status in (
                ('integrated-nvidia', 'confirmation-v4', V2, 428),
                ('integrated-candidates', V3, V2, 428),
                ('integrated-nvidia', V3, V2, 502),
                ('integrated-nvidia', V2, V3, 502),
                ('default', V3, V3, 428),
                ('default', 'confirmation-v4', V2, 428),
                ('integrated-nvidia', None, V2, 428)):
                output = load('result.json')
                output['contract'] = response_contract
                app = create_app(internal_token='mock-internal', analysis_mode=mode, analyze=lambda *_: output)
                headers = {'authorization': 'Bearer mock-internal', 'content-type': 'text/plain',
                           'x-document-id': self.ident, 'x-document-kind': 'TEXT', 'x-request-id': 'offline'}
                if contract:
                    headers['x-agentfit-analysis-contract'] = contract
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline.invalid') as client:
                    response = await client.post('/internal/v1/analyze', content=self.doc.encode(), headers=headers)
                    self.assertEqual(response.status_code, status, (mode, contract, response.text))
                    response = await client.post('/internal/v1/analyze', content=self.doc.encode(),
                        headers=[(k, v) for k, v in headers.items() if k != 'x-agentfit-analysis-contract'] +
                                [('x-agentfit-analysis-contract', V2), ('x-agentfit-analysis-contract', V3)])
                    self.assertEqual(response.status_code, 428)
        with offline():
            asyncio.run(run())

    def test_mock_v3_final_response_forwards_review_without_user_confirmation(self):
        saved = replay(V3)
        def analysis(document, document_id):
            self.assertEqual(document, self.doc)
            out = deepcopy(saved)
            for row in out['modelDecisions']:
                row['documentId'] = document_id
            for spans in out['profile']['evidence'].values():
                for span in spans:
                    span['documentId'] = document_id
            return out
        async def run():
            store = MockStore()
            ai = create_app(internal_token='mock-internal', analysis_mode='integrated-nvidia', analyze=analysis)
            app = create_mock_app(store=store, ai_app=ai, analysis_contract=V3)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline.invalid',
                                         headers={'Cookie': 'better-auth.session_token=mock-session-a', 'Origin': 'http://127.0.0.1:8765'}) as client:
                response = await client.post('/api/projects', json={'name': 'offline review'})
                self.assertEqual(response.status_code, 201, response.text)
                pid = response.json()['project']['id']
                response = await client.post(f'/api/projects/{pid}/analysis', content=self.doc.encode(),
                                              headers={'content-type': 'text/markdown'})
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(body['review']['reviewDispositions'], saved['reviewDispositions'])
                provenance = store.confirmation_provenance('owner-a', pid)
                self.assertEqual(provenance['draftReview'], body['review'])
                self.assertEqual(provenance['confirmations'], [])
                self.assertIsNone(store.detail('owner-a', pid)['confirmed'])
                for row in body['review']['modelDecisions']:
                    self.assertEqual(row['documentId'], body['attempt']['document']['id'])
                    self.assertEqual(row['sourceValue'], self.doc[row['candidate']['start']:row['candidate']['end']])
        with offline():
            asyncio.run(run())


if __name__ == '__main__':
    unittest.main()
