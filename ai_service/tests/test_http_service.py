"""Observable internal HTTP boundary behavior using the real ASGI application."""

import unittest

from fastapi.testclient import TestClient

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


if __name__ == "__main__":
    unittest.main()
