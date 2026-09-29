"""Observable internal HTTP boundary behavior using the real ASGI application."""

import unittest
import asyncio
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import uvicorn

from agentfit_ai.http_service import create_app
from agentfit_ai.profile import FIELDS, validate_profile
from test_document_extraction import sample_pdf


class InternalAnalysisHttpTests(unittest.TestCase):
    def setUp(self):
        self.documents = []

        def analyze(text, document_id):
            self.documents.append((text, document_id))
            return {"outcome": "failed", "error": "REVIEW_CONFIRMATION_REQUIRED"}

        self.client = TestClient(create_app(internal_token="local-secret", analyze=analyze))

    def send(self, body=b"AgentFit product", *, kind="TEXT", media="text/plain",
             headers=None):
        supplied = {"Authorization": "Bearer local-secret",
                    "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                    "X-Document-Kind": kind, "Content-Type": media}
        supplied.update(headers or {})
        return self.client.post("/internal/v1/analyze", content=body, headers=supplied)

    def test_invalid_service_token_never_processes_document(self):
        response = self.send(headers={"Authorization": "Bearer wrong"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"error": "UNAUTHORIZED"})
        self.assertEqual(self.documents, [])

    def test_duplicate_authorization_headers_are_rejected(self):
        response = self.client.post("/internal/v1/analyze", content=b"private-source",
                                    headers=[("Authorization", "Bearer local-secret"),
                                             ("Authorization", "Bearer wrong"),
                                             ("X-Document-Id", "doc_1"),
                                             ("X-Request-Id", "req_1"),
                                             ("X-Document-Kind", "TEXT"),
                                             ("Content-Type", "text/plain")])
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.documents, [])

    def test_missing_token_configuration_fails_closed(self):
        service = TestClient(create_app(internal_token="", analyze=lambda *_: None))
        response = service.post("/internal/v1/analyze", content=b"private")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "SERVICE_NOT_CONFIGURED"})

    def test_stream_limit_uses_actual_size_even_with_false_content_length(self):
        response = self.send(b"x" * 10_485_761,
                             headers={"Content-Length": "1"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json(), {"error": "DOCUMENT_TOO_LARGE"})
        self.assertEqual(self.documents, [])

    def test_text_document_reaches_analyzer_as_decoded_utf8(self):
        response = self.send("한글 문서".encode("utf-8"), media="text/plain; charset=utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"requestId": "req_1", "outcome": "failed",
                                           "error": "REVIEW_CONFIRMATION_REQUIRED"})
        self.assertEqual(self.documents, [("한글 문서", "doc_1")])

    def test_markdown_bytes_are_extracted_before_analysis(self):
        response = self.send(b"\xef\xbb\xbf# AgentFit", kind="MARKDOWN", media="text/markdown")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.documents, [("# AgentFit", "doc_1")])

    def test_pdf_bytes_are_extracted_before_analysis(self):
        response = self.send(sample_pdf(["AgentFit"]), kind="PDF", media="application/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.documents, [("AgentFit", "doc_1")])

    def test_complete_returns_only_revalidated_profile(self):
        source = "AgentFit"
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        data["project_name"] = "AgentFit"
        evidence["project_name"] = [{"start": 0, "end": 8}]
        profile = validate_profile(source, "doc_1", {"data": data, "evidence": evidence})
        service = TestClient(create_app(internal_token="local-secret",
                          analyze=lambda *_: {"outcome": "complete", "profile": profile}))
        response = service.post("/internal/v1/analyze", content=source.encode(),
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT", "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"requestId": "req_1", "outcome": "complete",
                                           "profile": profile})

    def test_malformed_analyzer_profile_cannot_echo_raw_source(self):
        service = TestClient(create_app(internal_token="local-secret",
                          analyze=lambda *_: {"outcome": "complete",
                                              "profile": {"raw": "private-source"}}))
        response = service.post("/internal/v1/analyze", content=b"private-source",
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT", "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "INVALID_PROFILE_SHAPE"})
        self.assertNotIn("private-source", response.text)

    def test_confirmation_questions_cannot_contain_analyzer_raw_text(self):
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        data["project_name"] = "AgentFit"
        evidence["project_name"] = [{"start": 0, "end": 8}]
        profile = validate_profile("AgentFit", "doc_1",
                                   {"data": data, "evidence": evidence})
        service = TestClient(create_app(internal_token="local-secret",
                          analyze=lambda *_: {"outcome": "needs_confirmation",
                                              "profile": profile,
                                              "fieldStates": {field: "unknown" for field in FIELDS},
                                              "questions": [{"raw": "private-source"}],
                                              "error": "REVIEW_CONFIRMATION_REQUIRED"}))
        response = service.post("/internal/v1/analyze", content=b"AgentFit",
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT", "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "INVALID_ANALYSIS_RESULT"})
        self.assertNotIn("private-source", response.text)

    def test_enormous_content_length_is_rejected_without_server_error(self):
        response = self.send(headers={"Content-Length": "9" * 5000})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "INVALID_CONTENT_LENGTH"})
        self.assertEqual(self.documents, [])

    def test_confirmation_cannot_mark_a_known_value_unknown(self):
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        data["project_name"] = "AgentFit"
        evidence["project_name"] = [{"start": 0, "end": 8}]
        profile = validate_profile("AgentFit", "doc_1",
                                   {"data": data, "evidence": evidence})
        service = TestClient(create_app(internal_token="local-secret",
                          analyze=lambda *_: {"outcome": "needs_confirmation",
                                              "profile": profile,
                                              "fieldStates": {field: "unknown" for field in FIELDS},
                                              "questions": [],
                                              "error": "REVIEW_CONFIRMATION_REQUIRED"}))
        response = service.post("/internal/v1/analyze", content=b"AgentFit",
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT", "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "INVALID_ANALYSIS_RESULT"})

    def test_confirmation_accepts_normalized_unresolved_reason(self):
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        data["project_name"] = "AgentFit"
        evidence["project_name"] = [{"start": 0, "end": 8}]
        profile = validate_profile("AgentFit", "doc_1",
                                   {"data": data, "evidence": evidence})
        states = {field: "unknown" for field in FIELDS}
        states["project_name"] = "suggested"
        states["domain"] = "unresolved"
        service = TestClient(create_app(internal_token="local-secret",
                          analyze=lambda *_: {"outcome": "needs_confirmation",
                                              "profile": profile, "fieldStates": states,
                                              "questions": [{"field": "domain",
                                                             "reason": "ANALYSIS_UNRESOLVED",
                                                             "questionId": "confirm_domain"}],
                                              "error": "REVIEW_CONFIRMATION_REQUIRED"}))
        response = service.post("/internal/v1/analyze", content=b"AgentFit",
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT", "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["questions"],
                         [{"field": "domain", "reason": "ANALYSIS_UNRESOLVED",
                           "questionId": "confirm_domain"}])

    def test_confirmation_accepts_review_unavailable_question_for_suggested_value(self):
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        data["project_name"] = "AgentFit"
        evidence["project_name"] = [{"start": 0, "end": 8}]
        profile = validate_profile("AgentFit", "doc_1",
                                   {"data": data, "evidence": evidence})
        states = {field: "unknown" for field in FIELDS}
        states["project_name"] = "suggested"
        question = {"field": "project_name", "reason": "REVIEW_UNAVAILABLE",
                    "questionId": "confirm_project_name"}

        def send_question(item):
            service = TestClient(create_app(internal_token="local-secret",
                analyze=lambda *_: {"outcome": "needs_confirmation", "profile": profile,
                                   "fieldStates": states, "questions": [item],
                                   "error": "PROVIDER_TIMEOUT"}))
            return service.post("/internal/v1/analyze", content=b"AgentFit",
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT",
                                         "Content-Type": "text/plain"})

        response = send_question(question)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["questions"], [question])
        self.assertEqual(response.json()["outcome"], "needs_confirmation")

        for invalid in (dict(question, reason="REVIEW_ISSUE"),
                        {"field": "database", "reason": "REVIEW_UNAVAILABLE",
                         "questionId": "confirm_database"}):
            with self.subTest(invalid=invalid):
                response = send_question(invalid)
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {"error": "INVALID_ANALYSIS_RESULT"})

    def test_recoverable_mode_requires_question_for_every_suggested_value(self):
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        data["project_name"] = "AgentFit"
        evidence["project_name"] = [{"start": 0, "end": 8}]
        profile = validate_profile("AgentFit", "doc_1",
                                   {"data": data, "evidence": evidence})
        states = {field: "unknown" for field in FIELDS}
        states["project_name"] = "suggested"

        def send(questions):
            service = TestClient(create_app(
                internal_token="local-secret", analysis_mode="recoverable-solar",
                analyze=lambda *_: {"outcome": "needs_confirmation",
                                   "profile": profile, "fieldStates": states,
                                   "questions": questions,
                                   "error": "SEMANTIC_REJECTED"}))
            return service.post("/internal/v1/analyze", content=b"AgentFit",
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT",
                                         "X-AgentFit-Analysis-Contract": "confirmation-v1",
                                         "Content-Type": "text/plain"})

        self.assertEqual(send([]).status_code, 502)
        question = {"field": "project_name", "reason": "CONFIRM_SUGGESTION",
                    "questionId": "confirm_project_name"}
        self.assertEqual(send([question]).status_code, 200)
        self.assertEqual(send([dict(question, reason="REVIEW_ISSUE")]).status_code, 502)

    def test_invalid_document_id_is_rejected_before_analysis(self):
        response = self.send(headers={"X-Document-Id": "../../other"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "INVALID_DOCUMENT_ID"})
        self.assertEqual(self.documents, [])

    def test_invalid_utf8_error_does_not_echo_input(self):
        response = self.send(b"\xffprivate-source")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"error": "DOCUMENT_INVALID_UTF8"})
        self.assertNotIn("private-source", response.text)
        self.assertEqual(self.documents, [])

    def test_unexpected_analyzer_failure_does_not_expose_exception(self):
        def leak(*_):
            raise RuntimeError("private-source provider-secret")

        service = TestClient(create_app(internal_token="local-secret", analyze=leak))
        response = service.post("/internal/v1/analyze", content=b"private-source",
                                headers={"Authorization": "Bearer local-secret",
                                         "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                         "X-Document-Kind": "TEXT", "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"error": "INTERNAL_ERROR"})
        self.assertNotIn("private-source", response.text)
        self.assertNotIn("provider-secret", response.text)

    def test_health_does_not_claim_provider_readiness(self):
        self.assertEqual(self.client.get("/healthz").json(), {"status": "alive"})

    def test_busy_service_rejects_second_request_before_analysis(self):
        started = Event()
        release = Event()
        analyzed = []

        def analyze(text, document_id):
            analyzed.append(document_id)
            if document_id == "first":
                started.set()
                release.wait(timeout=3)
            return {"outcome": "failed", "error": "REVIEW_CONFIRMATION_REQUIRED"}

        app = create_app(internal_token="local-secret", analyze=analyze, max_inflight=1)
        first_client = TestClient(app)
        second_client = TestClient(app)
        headers = {"Authorization": "Bearer local-secret", "X-Request-Id": "req_1",
                   "X-Document-Kind": "TEXT", "Content-Type": "text/plain"}
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(first_client.post, "/internal/v1/analyze", content=b"Alpha",
                                headers=dict(headers, **{"X-Document-Id": "first"}))
            try:
                self.assertTrue(started.wait(timeout=2))
                def forbidden_body():
                    raise AssertionError("busy request body was consumed")
                    yield b"Beta"

                busy = second_client.post("/internal/v1/analyze", content=forbidden_body(),
                                          headers=dict(headers, **{"X-Document-Id": "second"}))
                self.assertEqual(busy.status_code, 503)
                self.assertEqual(busy.json(), {"error": "SERVICE_BUSY"})
                self.assertEqual(busy.headers["retry-after"], "1")
                self.assertEqual(analyzed, ["first"])
            finally:
                release.set()
            self.assertEqual(first.result(timeout=2).status_code, 200)
        after = second_client.post("/internal/v1/analyze", content=b"Gamma",
                                   headers=dict(headers, **{"X-Document-Id": "third"}))
        self.assertEqual(after.status_code, 200)
        self.assertEqual(analyzed, ["first", "third"])

    def test_slow_body_times_out_and_releases_slot(self):
        analyzed = []

        def analyze(text, document_id):
            analyzed.append(text)
            return {"outcome": "failed", "error": "REVIEW_CONFIRMATION_REQUIRED"}

        app = create_app(internal_token="local-secret", analyze=analyze,
                         max_inflight=1, upload_timeout_seconds=1)
        headers = {"Authorization": "Bearer local-secret", "X-Document-Id": "doc_1",
                   "X-Request-Id": "req_1", "X-Document-Kind": "TEXT",
                   "Content-Type": "text/plain"}

        async def run():
            async def slow():
                yield b"Alpha"
                await asyncio.sleep(1.2)
                yield b"Beta"

            async with AsyncClient(transport=ASGITransport(app=app),
                                   base_url="http://test") as client:
                timeout = await client.post("/internal/v1/analyze", content=slow(),
                                            headers=headers)
                accepted = await client.post("/internal/v1/analyze", content=b"Gamma",
                                             headers=headers)
            return timeout, accepted

        timeout, accepted = asyncio.run(run())
        self.assertEqual(timeout.status_code, 408)
        self.assertEqual(timeout.json(), {"error": "DOCUMENT_UPLOAD_TIMEOUT"})
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(analyzed, ["Gamma"])

    def test_unexpected_analysis_error_releases_slot(self):
        calls = 0

        def analyze(*_):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("private failure")
            return {"outcome": "failed", "error": "REVIEW_CONFIRMATION_REQUIRED"}

        client = TestClient(create_app(internal_token="local-secret", analyze=analyze,
                                       max_inflight=1))
        headers = {"Authorization": "Bearer local-secret", "X-Document-Id": "doc_1",
                   "X-Request-Id": "req_1", "X-Document-Kind": "TEXT",
                   "Content-Type": "text/plain"}
        first = client.post("/internal/v1/analyze", content=b"Alpha", headers=headers)
        second = client.post("/internal/v1/analyze", content=b"Beta", headers=headers)
        self.assertEqual(first.status_code, 500)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(calls, 2)

    def test_invalid_runtime_limits_fail_at_startup(self):
        for name, value in (("AGENTFIT_MAX_INFLIGHT_ANALYSES", "0"),
                            ("AGENTFIT_UPLOAD_TIMEOUT_SECONDS", "31")):
            with self.subTest(name=name), patch.dict("os.environ", {name: value}):
                with self.assertRaises(ValueError):
                    create_app(internal_token="local-secret", analyze=lambda *_: None)

    def test_slot_remains_held_until_asgi_response_send_finishes(self):
        app = create_app(internal_token="local-secret", max_inflight=1,
                         analyze=lambda *_: {"outcome": "failed",
                                             "error": "REVIEW_CONFIRMATION_REQUIRED"})

        async def run():
            sending = asyncio.Event()
            finish_send = asyncio.Event()

            async def invoke(document_id, block_send=False):
                scope = {"type": "http", "asgi": {"version": "3.0"},
                         "http_version": "1.1", "method": "POST", "scheme": "http",
                         "path": "/internal/v1/analyze", "raw_path": b"/internal/v1/analyze",
                         "query_string": b"", "client": ("127.0.0.1", 10000),
                         "server": ("127.0.0.1", 8000),
                         "headers": [(b"authorization", b"Bearer local-secret"),
                                     (b"x-document-id", document_id.encode()),
                                     (b"x-request-id", b"req_1"),
                                     (b"x-document-kind", b"TEXT"),
                                     (b"content-type", b"text/plain")]}
                messages = []

                async def receive():
                    return {"type": "http.request", "body": b"AgentFit", "more_body": False}

                async def send(message):
                    if block_send and message["type"] == "http.response.body":
                        sending.set()
                        await finish_send.wait()
                    messages.append(message)

                await app(scope, receive, send)
                return messages

            first = asyncio.create_task(invoke("first", block_send=True))
            try:
                await asyncio.wait_for(sending.wait(), timeout=2)
                second = await invoke("second")
            finally:
                finish_send.set()
                await first
            third = await invoke("third")
            return second, third

        busy, accepted = asyncio.run(run())
        self.assertEqual(busy[0]["status"], 503)
        self.assertEqual(accepted[0]["status"], 200)

    def test_default_analysis_uses_request_worker(self):
        async def worker(document, document_id, key, deadline):
            self.assertEqual((document, document_id, key),
                             ("AgentFit", "doc_1", "test-key"))
            self.assertGreater(deadline, asyncio.get_running_loop().time())
            return {"error": "PROVIDER_TIMEOUT"}

        with patch.dict("os.environ", {"UPSTAGE_API_KEY": "test-key"}), patch(
                "agentfit_ai.http_service.run_analysis_process", side_effect=worker):
            client = TestClient(create_app(internal_token="local-secret"))
            response = client.post("/internal/v1/analyze", content=b"AgentFit",
                                   headers={"Authorization": "Bearer local-secret",
                                            "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                            "X-Document-Kind": "TEXT",
                                            "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "PROVIDER_TIMEOUT"})

    def test_recoverable_service_mode_delivers_confirmable_draft(self):
        data = {field: None for field in FIELDS}
        evidence = {field: [] for field in FIELDS}
        data["project_name"] = "AgentFit"
        evidence["project_name"] = [{"start": 0, "end": 8}]
        profile = validate_profile("AgentFit", "doc_1", {"data": data,
                                                          "evidence": evidence})
        states = {field: "unknown" for field in FIELDS}
        states["project_name"] = "suggested"
        question = {"field": "project_name", "reason": "REVIEW_UNAVAILABLE",
                    "questionId": "confirm_project_name"}

        async def worker(document, document_id, key, deadline, *, recoverable_solar):
            self.assertTrue(recoverable_solar)
            self.assertEqual((document, document_id, key), ("AgentFit", "doc_1", "test-key"))
            return {"outcome": "needs_confirmation", "profile": profile,
                    "fieldStates": states, "questions": [question],
                    "error": "PROVIDER_TIMEOUT"}

        with patch.dict("os.environ", {"UPSTAGE_API_KEY": "test-key",
                                    "AGENTFIT_ANALYSIS_MODE": "recoverable-solar"}), patch(
                "agentfit_ai.http_service.run_analysis_process", side_effect=worker):
            client = TestClient(create_app(internal_token="local-secret"))
            response = client.post("/internal/v1/analyze", content=b"AgentFit",
                                   headers={"Authorization": "Bearer local-secret",
                                            "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                            "X-Document-Kind": "TEXT",
                                            "X-AgentFit-Analysis-Contract": "confirmation-v1",
                                            "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["questions"], [question])

    def test_unknown_analysis_mode_fails_at_app_creation(self):
        with self.assertRaises(ValueError):
            create_app(internal_token="local-secret", analysis_mode="unknown")

    def test_recoverable_mode_requires_explicit_confirmation_contract(self):
        documents = []
        client = TestClient(create_app(internal_token="local-secret",
                                       analysis_mode="recoverable-solar",
                                       analyze=lambda *args: documents.append(args)))
        base = [("Authorization", "Bearer local-secret"),
                ("X-Document-Id", "doc_1"), ("X-Request-Id", "req_1"),
                ("X-Document-Kind", "TEXT"), ("Content-Type", "text/plain")]
        variants = ([], [("X-AgentFit-Analysis-Contract", "other")],
                    [("X-AgentFit-Analysis-Contract", "confirmation-v1"),
                     ("X-AgentFit-Analysis-Contract", "confirmation-v1")])
        for extra in variants:
            with self.subTest(extra=extra):
                response = client.post("/internal/v1/analyze", content=b"AgentFit",
                                       headers=base + extra)
                self.assertEqual(response.status_code, 428)
                self.assertEqual(response.json(),
                                 {"error": "CONFIRMATION_CONTRACT_REQUIRED"})
        self.assertEqual(documents, [])

    def test_recoverable_mode_runs_through_real_child_process_without_provider(self):
        import sys
        from agentfit_ai.analysis_process import run_analysis_process

        child_code = """
import agentfit_ai.analysis_worker as worker
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.recoverable_draft import project_draft

class LocalAnalyzer:
    def __init__(self, *args, **kwargs):
        pass

    def analyze_recoverable(self, document, document_id):
        data = dict.fromkeys(FIELDS)
        evidence = {field: [] for field in FIELDS}
        data['project_name'] = document
        evidence['project_name'] = [{'start': 0, 'end': len(document)}]
        profile = validate_profile(document, document_id,
                                   {'data': data, 'evidence': evidence})
        return project_draft(document, document_id, profile, unresolved={},
                             review_complete=False, error_code='PROVIDER_TIMEOUT',
                             ask_suggested_when_unreviewed=True,
                             ask_unknown_when_unreviewed=False)

worker.RecoverableSolarAnalyzer = LocalAnalyzer
worker.main()
"""

        async def child(document, document_id, key, deadline, *, recoverable_solar):
            return await run_analysis_process(
                document, document_id, key, deadline,
                recoverable_solar=recoverable_solar,
                command=[sys.executable, "-c", child_code])

        with patch.dict("os.environ", {"UPSTAGE_API_KEY": "test-key"}), patch(
                "agentfit_ai.http_service.run_analysis_process", side_effect=child):
            client = TestClient(create_app(internal_token="local-secret",
                                           analysis_mode="recoverable-solar"))
            response = client.post("/internal/v1/analyze", content=b"AgentFit",
                                   headers={"Authorization": "Bearer local-secret",
                                            "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                            "X-Document-Kind": "TEXT",
                                            "X-AgentFit-Analysis-Contract": "confirmation-v1",
                                            "Content-Type": "text/plain"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["outcome"], "needs_confirmation")
        self.assertEqual(response.json()["profile"]["data"]["project_name"], "AgentFit")
        self.assertEqual(response.json()["questions"],
                         [{"field": "project_name", "reason": "REVIEW_UNAVAILABLE",
                           "questionId": "confirm_project_name"}])

    def test_default_worker_deadline_returns_504_and_releases_slot(self):
        async def worker(*_):
            await asyncio.sleep(10)

        with patch.dict("os.environ", {"UPSTAGE_API_KEY": "test-key"}), patch(
                "agentfit_ai.http_service.run_analysis_process", side_effect=worker):
            client = TestClient(create_app(internal_token="local-secret", max_inflight=1,
                                           request_timeout_seconds=1))
            headers = {"Authorization": "Bearer local-secret", "X-Document-Id": "doc_1",
                       "X-Request-Id": "req_1", "X-Document-Kind": "TEXT",
                       "Content-Type": "text/plain"}
            first = client.post("/internal/v1/analyze", content=b"AgentFit", headers=headers)
            second = client.post("/internal/v1/analyze", content=b"AgentFit", headers=headers)
        self.assertEqual(first.status_code, 504)
        self.assertEqual(first.json(), {"error": "ANALYSIS_DEADLINE_EXCEEDED"})
        self.assertEqual(second.status_code, 504)

    def test_pdf_is_not_started_when_less_than_its_worker_limit_remains(self):
        client = TestClient(create_app(internal_token="local-secret",
                                       analyze=lambda *_: None,
                                       request_timeout_seconds=1))
        with patch("agentfit_ai.http_service.extract_document") as extract:
            response = client.post("/internal/v1/analyze", content=sample_pdf(["AgentFit"]),
                                   headers={"Authorization": "Bearer local-secret",
                                            "X-Document-Id": "doc_1", "X-Request-Id": "req_1",
                                            "X-Document-Kind": "PDF",
                                            "Content-Type": "application/pdf"})
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json(), {"error": "ANALYSIS_DEADLINE_EXCEEDED"})
        extract.assert_not_called()

    def test_disconnected_default_request_cancels_worker_and_releases_slot(self):
        started = asyncio.Event()
        stopped = asyncio.Event()
        disconnected = asyncio.Event()

        async def worker(*_):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                stopped.set()

        app = create_app(internal_token="local-secret", max_inflight=1)

        async def run():
            scope = {"type": "http", "asgi": {"version": "3.0"},
                     "http_version": "1.1", "method": "POST", "scheme": "http",
                     "path": "/internal/v1/analyze", "raw_path": b"/internal/v1/analyze",
                     "query_string": b"", "client": ("127.0.0.1", 10000),
                     "server": ("127.0.0.1", 8000),
                     "headers": [(b"authorization", b"Bearer local-secret"),
                                 (b"x-document-id", b"doc_1"),
                                 (b"x-request-id", b"req_1"),
                                 (b"x-document-kind", b"TEXT"),
                                 (b"content-type", b"text/plain")]}
            sent = []
            received = 0

            async def receive():
                nonlocal received
                received += 1
                if received == 1:
                    return {"type": "http.request", "body": b"AgentFit", "more_body": False}
                await disconnected.wait()
                return {"type": "http.disconnect"}

            async def send(message):
                sent.append(message)

            task = asyncio.create_task(app(scope, receive, send))
            await asyncio.wait_for(started.wait(), timeout=2)
            disconnected.set()
            await asyncio.wait_for(task, timeout=2)
            self.assertTrue(stopped.is_set())
            self.assertEqual(sent, [])

        with patch.dict("os.environ", {"UPSTAGE_API_KEY": "test-key"}), patch(
                "agentfit_ai.http_service.run_analysis_process", side_effect=worker):
            asyncio.run(run())

    def test_already_disconnected_request_does_not_start_worker(self):
        called = []

        async def worker(*_):
            called.append(True)
            return {"error": "PROVIDER_TIMEOUT"}

        app = create_app(internal_token="local-secret", max_inflight=1)

        async def run():
            scope = {"type": "http", "asgi": {"version": "3.0"},
                     "http_version": "1.1", "method": "POST", "scheme": "http",
                     "path": "/internal/v1/analyze", "raw_path": b"/internal/v1/analyze",
                     "query_string": b"", "client": ("127.0.0.1", 10000),
                     "server": ("127.0.0.1", 8000),
                     "headers": [(b"authorization", b"Bearer local-secret"),
                                 (b"x-document-id", b"doc_1"),
                                 (b"x-request-id", b"req_1"),
                                 (b"x-document-kind", b"TEXT"),
                                 (b"content-type", b"text/plain")]}
            received = 0
            sent = []

            async def receive():
                nonlocal received
                received += 1
                return ({"type": "http.request", "body": b"AgentFit", "more_body": False}
                        if received == 1 else {"type": "http.disconnect"})

            async def send(message):
                sent.append(message)

            await app(scope, receive, send)
            return sent

        with patch.dict("os.environ", {"UPSTAGE_API_KEY": "test-key"}), patch(
                "agentfit_ai.http_service.run_analysis_process", side_effect=worker):
            sent = asyncio.run(run())
        self.assertEqual(called, [])
        self.assertEqual(sent, [])

    def test_tcp_disconnect_cancels_running_analysis(self):
        started = Event()
        cancelled = Event()

        async def worker(*_):
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        app = create_app(internal_token="local-secret", max_inflight=1)
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=0, access_log=False, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        with patch.dict("os.environ", {"UPSTAGE_API_KEY": "test-key"}), patch(
                "agentfit_ai.http_service.run_analysis_process", side_effect=worker):
            thread.start()
            try:
                for _ in range(100):
                    if server.started and server.servers:
                        break
                    time.sleep(.05)
                self.assertTrue(server.started)
                port = server.servers[0].sockets[0].getsockname()[1]
                with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                    client.sendall(
                        b"POST /internal/v1/analyze HTTP/1.1\r\n"
                        b"Host: 127.0.0.1\r\nAuthorization: Bearer local-secret\r\n"
                        b"X-Document-Id: doc_1\r\nX-Request-Id: req_1\r\n"
                        b"X-Document-Kind: TEXT\r\nContent-Type: text/plain\r\n"
                        b"Content-Length: 8\r\n\r\nAgentFit")
                    self.assertTrue(started.wait(timeout=2))
                self.assertTrue(cancelled.wait(timeout=2))
            finally:
                server.should_exit = True
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
