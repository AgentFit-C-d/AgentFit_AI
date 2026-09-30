"""NVIDIA-only child through public mock draft, user confirmation and recovery."""

import json
import unittest

import httpx

from test_core_flow_runtime import core_flow, analyze, confirm
from test_integrated_service import Provider
from test_integrated_runtime import NVIDIA_KEY, SOLAR_KEY
from contract_mock.schema import check


class NvidiaCoreFlowTests(unittest.TestCase):
    def test_single_key_draft_confirmation_failure_recovery_conflict_and_delete(self):
        provider = Provider(missing=True)
        with core_flow(provider, analysis_mode='integrated-nvidia') as (http, p, store, processes, options, _):
            output = analyze(http, p, provider.document)
            self.assertEqual(output.status_code, 200)
            check('AnalysisResponse', output.json())
            draft = output.json()['draft']
            self.assertEqual(draft['data']['frontend'], ['React'])
            self.assertEqual(draft['evidence']['frontend'][0]['start'], 24)
            detail = http.get(f'/api/projects/{p}').json()
            self.assertIsNone(detail['confirmed'])
            self.assertEqual(detail['project']['version'], 0)
            self.assertEqual(store._entries[p]['review']['fieldStates']['frontend'], 'unresolved')
            saved, payload = confirm(http, p, draft, frontend=['Vue'], ai=[], domain=None)
            self.assertEqual(saved.status_code, 200)
            check('SaveProfileResponse', saved.json())
            confirmed = saved.json()['confirmed']
            self.assertEqual(confirmed['data']['frontend'], ['Vue'])
            self.assertEqual(confirmed['data']['ai'], [])
            self.assertIsNone(confirmed['data']['domain'])
            self.assertEqual(confirmed['sources']['frontend'], 'USER')
            self.assertEqual(confirmed['sources']['domain'], 'UNKNOWN')

            provider.failure_status = 429
            failed = analyze(http, p, provider.document)
            self.assertEqual((failed.status_code, failed.json()['error']['code']), (502, 'AI_UNAVAILABLE'))
            detail = http.get(f'/api/projects/{p}').json()
            self.assertEqual(detail['latestAttempt']['status'], 'FAILED')
            self.assertEqual(detail['confirmed'], confirmed)
            self.assertEqual(detail['draft'], draft)
            self.assertEqual(len(processes), 2)
            self.assertEqual(len(provider.kinds), 6)  # Five successful stages plus one failed call.
            for secret in (NVIDIA_KEY, SOLAR_KEY, 'synthetic-private-provider-error'):
                self.assertNotIn(secret, failed.text + json.dumps(detail) + repr(store.__dict__))

            provider.failure_status = None
            recovered = analyze(http, p, provider.document)
            self.assertEqual(recovered.status_code, 200)
            with httpx.Client(**options) as reopened:
                detail = reopened.get(f'/api/projects/{p}').json()
                check('ProjectDetailResponse', detail)
                self.assertEqual(detail['confirmed'], confirmed)
                self.assertEqual(detail['project']['version'], 1)
                duplicate = reopened.patch(f'/api/projects/{p}/profile', json=payload)
                self.assertEqual((duplicate.status_code, duplicate.json()['error']['code']), (409, 'VERSION_CONFLICT'))
                self.assertEqual(reopened.get(f'/api/projects/{p}').json(), detail)
                deleted = reopened.request('DELETE', f'/api/projects/{p}', json={'confirmation': True})
                self.assertEqual(deleted.status_code, 204)
                self.assertEqual(reopened.get(f'/api/projects/{p}').status_code, 404)
            self.assertEqual(len(processes), 3)
            self.assertTrue(all(p.returncode is not None for p in processes))
            self.assertEqual(provider.kinds, ['nvidia'] * 11)
            self.assertEqual(provider.errors, [])


if __name__ == '__main__':
    unittest.main()
