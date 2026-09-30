"""File input through real parsers/SDK/child and public mock; loopback only."""

from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from urllib.parse import quote

import httpx
from pypdf import PdfWriter

from test_core_flow_runtime import core_flow, confirm
from test_integrated_service import Provider
from test_integrated_runtime import NVIDIA_KEY, SOLAR_KEY
from contract_mock.schema import check

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from test_document_extraction import sample_pdf


MARKDOWN = '# 기획 😀\r\nTestApp\r\nReact\r\n기록 저장'
PDF_TEXT = 'TestApp\nReact Save records'


def file_provider(*, pdf=False):
    provider = Provider()
    provider.document = PDF_TEXT if pdf else MARKDOWN
    provider.facts = [('TestApp', 'project_name'), ('React', 'frontend'),
                      ('Save records' if pdf else '기록 저장', 'features')]
    return provider


def upload(http, project, raw, media, name):
    return http.post(f'/api/projects/{project}/analysis', content=raw,
                     headers={'Content-Type': media, 'X-Document-Name': quote(name)})


class DocumentInputRuntimeTests(unittest.TestCase):
    def assert_saved_and_deleted(self, http, p, body, store, processes, options, provider):
        check('AnalysisResponse', body)
        draft = body['draft']
        before = http.get(f'/api/projects/{p}').json()
        self.assertIsNone(before['confirmed'])
        self.assertEqual(before['project']['version'], 0)
        self.assertEqual(draft['kind'], 'DRAFT')
        self.assertEqual(body['attempt']['status'], 'SUCCEEDED')
        saved, payload = confirm(http, p, draft, frontend=['Vue'])
        self.assertEqual(saved.status_code, 200)
        check('SaveProfileResponse', saved.json())
        confirmed = saved.json()['confirmed']
        self.assertEqual(confirmed['sources']['frontend'], 'USER')
        self.assertEqual(confirmed['evidence']['frontend'], [])
        self.assertEqual(confirmed['data']['frontend'], ['Vue'])
        self.assertEqual(confirmed['sources']['features'], 'DOCUMENT')
        self.assertEqual(confirmed['evidence']['features'], draft['evidence']['features'])
        with httpx.Client(**options) as reopened:
            detail = reopened.get(f'/api/projects/{p}').json()
            check('ProjectDetailResponse', detail)
            self.assertEqual(detail['confirmed'], confirmed)
            self.assertEqual(detail['project']['version'], 1)
            duplicate = reopened.patch(f'/api/projects/{p}/profile', json=payload)
            self.assertEqual((duplicate.status_code, duplicate.json()['error']['code']),
                             (409, 'VERSION_CONFLICT'))
            self.assertEqual(reopened.get(f'/api/projects/{p}').json(), detail)
            state = json.dumps(store.__dict__, ensure_ascii=False, default=str)
            for private in (provider.document, NVIDIA_KEY, SOLAR_KEY):
                self.assertNotIn(private, state)
            deleted = reopened.request('DELETE', f'/api/projects/{p}', json={'confirmation': True})
            self.assertEqual(deleted.status_code, 204)
            self.assertEqual(reopened.get(f'/api/projects/{p}').status_code, 404)
            self.assertNotIn(p, store._entries)
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].returncode, 0)
        self.assertEqual(provider.errors, [])
        self.assertEqual(provider.kinds, ['nvidia'] * 5)

    def test_markdown_unicode_bom_crlf_survives_confirmation(self):
        # Catches BOM retention, newline normalization and byte-based evidence offsets.
        provider = file_provider()
        raw = b'\xef\xbb\xbf' + MARKDOWN.encode('utf-8')
        with core_flow(provider, analysis_mode='integrated-nvidia') as (http, p, store, processes, options, _):
            response = upload(http, p, raw, 'text/markdown', '기획서.md')
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            doc = body['attempt']['document']
            self.assertEqual((doc['kind'], doc['displayName'], doc['characterCount'], doc['byteSize']),
                             ('MARKDOWN', '기획서.md', 29, 47))
            self.assertIsNone(doc['pageCount'])
            self.assertEqual(body['draft']['data']['features'], ['기록 저장'])
            self.assertEqual(body['draft']['evidence']['frontend'],
                             [{'documentId': doc['id'], 'start': 17, 'end': 22}])
            self.assertEqual(body['draft']['evidence']['features'],
                             [{'documentId': doc['id'], 'start': 24, 'end': 29}])
            self.assert_saved_and_deleted(http, p, body, store, processes, options, provider)

    def test_two_page_pdf_evidence_survives_confirmation(self):
        # Catches skipping PDF extraction, dropped page separators, or lost saved evidence.
        provider = file_provider(pdf=True)
        raw = sample_pdf(['TestApp', 'React Save records'])
        with core_flow(provider, analysis_mode='integrated-nvidia') as (http, p, store, processes, options, _):
            response = upload(http, p, raw, 'application/pdf', 'plan.pdf')
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            doc = body['attempt']['document']
            self.assertEqual((doc['kind'], doc['displayName'], doc['byteSize']), ('PDF', 'plan.pdf', len(raw)))
            # Current AI contract does not return these measurements to the mock.
            self.assertIsNone(doc['pageCount'])
            self.assertIsNone(doc['characterCount'])
            self.assertEqual(body['draft']['data']['features'], ['Save records'])
            self.assertEqual(body['draft']['evidence']['frontend'],
                             [{'documentId': doc['id'], 'start': 8, 'end': 13}])
            self.assertEqual(body['draft']['evidence']['features'],
                             [{'documentId': doc['id'], 'start': 14, 'end': 26}])
            self.assert_saved_and_deleted(http, p, body, store, processes, options, provider)

    def test_invalid_documents_preserve_saved_profile_without_model_calls(self):
        # Catches partial-file analysis, parsing failures clearing saved data, and slot leaks.
        sentinel = 'synthetic-private-source-only'
        writer = PdfWriter(BytesIO(sample_pdf([sentinel])))
        writer.encrypt('synthetic-password')
        encrypted = BytesIO()
        writer.write(encrypted)
        cases = [
            (b'\xff' + sentinel.encode(), 'text/markdown', 422, 'UNREADABLE_DOCUMENT', False),
            (b'\xef\xbb\xbf \r\n\t', 'text/markdown', 422, 'EMPTY_DOCUMENT', False),
            (b'x' * 100001, 'text/markdown', 413, 'INPUT_TOO_LARGE', False),
            (b'%PDF-1.4\n' + sentinel.encode(), 'application/pdf', 422, 'UNREADABLE_DOCUMENT', True),
            (encrypted.getvalue(), 'application/pdf', 422, 'UNREADABLE_DOCUMENT', True),
            (sample_pdf(['']), 'application/pdf', 422, 'EMPTY_DOCUMENT', True),
            (sample_pdf([sentinel, '']), 'application/pdf', 422, 'PARTIAL_EXTRACTION', True),
            (sample_pdf([''] * 101), 'application/pdf', 413, 'INPUT_TOO_LARGE', True),
        ]
        provider = file_provider()
        with core_flow(provider, analysis_mode='integrated-nvidia') as (http, p, store, processes, _, __):
            initial = upload(http, p, MARKDOWN.encode(), 'text/markdown', 'plan.md')
            self.assertEqual(initial.status_code, 200, initial.text)
            draft = initial.json()['draft']
            saved, _ = confirm(http, p, draft)
            self.assertEqual(saved.status_code, 200)
            for raw, media, status, code, attempted in cases:
                with self.subTest(media=media, code=code, bytes=len(raw)):
                    response = upload(http, p, raw, media, 'bad.pdf' if media == 'application/pdf' else 'bad.md')
                    self.assertEqual((response.status_code, response.json()['error']['code']), (status, code))
                    detail = http.get(f'/api/projects/{p}').json()
                    self.assertEqual(detail['draft'], draft)
                    self.assertEqual(detail['confirmed'], saved.json()['confirmed'])
                    self.assertEqual(detail['project']['version'], 1)
                    if attempted:
                        self.assertEqual(detail['latestAttempt']['status'], 'FAILED')
                        self.assertEqual(detail['latestAttempt']['errorCode'], code)
                    self.assertEqual(len(processes), 1)
                    self.assertEqual(len(provider.kinds), 5)
                    stored = json.dumps(store.__dict__, ensure_ascii=False, default=str)
                    for private in (sentinel, 'synthetic-password', NVIDIA_KEY, SOLAR_KEY):
                        self.assertNotIn(private, response.text + stored)
            recovered = upload(http, p, MARKDOWN.encode(), 'text/markdown', 'retry.md')
            self.assertEqual(recovered.status_code, 200, recovered.text)
            self.assertEqual(recovered.json()['draft']['version'], 2)
            self.assertEqual(http.get(f'/api/projects/{p}').json()['confirmed'], saved.json()['confirmed'])
            self.assertEqual(len(processes), 2)
            self.assertTrue(all(process.returncode == 0 for process in processes))
            self.assertEqual(provider.kinds, ['nvidia'] * 10)
            self.assertEqual(provider.errors, [])


if __name__ == '__main__':
    unittest.main()
