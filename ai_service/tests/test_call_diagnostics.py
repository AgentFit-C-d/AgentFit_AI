import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from agentfit_ai.solar import SolarAnalyzer, AnalysisError
from test_staged_analysis import response, core, features

class CallDiagnosticsTests(unittest.TestCase):
    def test_success_has_scoped_metadata_without_source(self):
        transport = Mock(side_effect=[response(core()), response(features())])
        result = SolarAnalyzer("synthetic-key", transport=transport).analyze("Alpha registration", "private-document")
        d = result.diagnostics
        self.assertEqual([c["stage"] for c in d["calls"]], ["core", "features"])
        self.assertTrue(all(c["outcome"] == "validated" for c in d["calls"]))
        self.assertEqual(d["input_codepoints"], 18)
        self.assertEqual(d["calls"][0]["prompt_tokens"], 10)
        for call in d["calls"]:
            self.assertGreater(call["request_bytes"], 0)
            self.assertGreaterEqual(call["elapsed_ms"], call["provider_elapsed_ms"])
        text = json.dumps(d)
        for secret in ("Alpha", "registration", "private-document", "synthetic-key"):
            self.assertNotIn(secret, text)

    def test_second_call_timeout_identifies_stage_without_retry(self):
        transport = Mock(side_effect=[response(core()), TimeoutError("private detail")])
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key", transport=transport).analyze("Alpha registration", "doc")
        d = caught.exception.diagnostics
        self.assertEqual(transport.call_count, 2)
        self.assertEqual(d["calls"][1]["stage"], "features")
        self.assertEqual(d["calls"][1]["error"], "PROVIDER_TIMEOUT")
        self.assertNotIn("private detail", json.dumps(d))

    def test_repaired_success_never_persists_raw(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        with tempfile.TemporaryDirectory() as folder:
            store = LocalDiagnosticsStore(Path(folder))
            transport = Mock(side_effect=[response(core()), response(features(99)), response(features())])
            r = SolarAnalyzer("synthetic-key", transport=transport, diagnostics_store=store).analyze("Alpha registration", "doc")
            self.assertEqual(r.diagnostics["calls"][1]["outcome"], "validation_failed")
            self.assertEqual(r.diagnostics["calls"][2]["stage"], "repair")
            saved = json.loads(next(Path(folder).glob("*.json")).read_text())
            self.assertEqual(saved["failed_responses"], [])
            self.assertNotIn("registration", json.dumps(saved))

    def test_final_failure_stores_only_failed_responses(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        with tempfile.TemporaryDirectory() as folder:
            store = LocalDiagnosticsStore(Path(folder))
            transport = Mock(side_effect=[response(core()), response(features(99)), response(features(99))])
            with self.assertRaises(AnalysisError):
                SolarAnalyzer("synthetic-key", transport=transport, diagnostics_store=store).analyze("Alpha registration", "doc")
            saved = json.loads(next(Path(folder).glob("*.json")).read_text())
            self.assertEqual([x["call"] for x in saved["failed_responses"]], [2, 3])
            self.assertNotIn("Alpha", json.dumps(saved))

    def test_sensitive_response_is_not_saved(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        with tempfile.TemporaryDirectory() as folder:
            transport = Mock(return_value=response({"secret": "synthetic-key"}))
            with self.assertRaises(AnalysisError):
                SolarAnalyzer("synthetic-key", transport=transport,
                    diagnostics_store=LocalDiagnosticsStore(Path(folder))).analyze("Alpha", "doc")
            saved = next(Path(folder).glob("*.json")).read_text()
            self.assertNotIn("synthetic-key", saved)
            self.assertEqual(json.loads(saved)["failed_responses"], [])

    def test_store_failure_preserves_success(self):
        store = Mock()
        store.write.side_effect = OSError("private path")
        transport = Mock(side_effect=[response(core()), response(features())])
        r = SolarAnalyzer("synthetic-key", transport=transport, diagnostics_store=store).analyze("Alpha registration", "doc")
        self.assertEqual(r.profile["data"]["project_name"], "Alpha")
        self.assertEqual(r.diagnostics["storage"], "failed")
        self.assertNotIn("private path", json.dumps(r.diagnostics))

    def test_incomplete_response_retains_usage_metadata(self):
        payload = json.loads(response(core()))
        payload["choices"][0]["finish_reason"] = "length"
        transport = Mock(return_value=json.dumps(payload).encode())
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key", transport=transport).analyze("Alpha", "doc")
        call = caught.exception.diagnostics["calls"][0]
        self.assertEqual(call.get("completion_tokens"), 20)
        self.assertEqual(call["error"], "INCOMPLETE_RESPONSE")

    def test_store_failure_preserves_original_analysis_error(self):
        store = Mock()
        store.write.side_effect = OSError("private path")
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key", transport=Mock(side_effect=TimeoutError()),
                          diagnostics_store=store).analyze("Alpha", "doc")
        self.assertEqual(caught.exception.code, "PROVIDER_TIMEOUT")
        self.assertEqual(caught.exception.diagnostics["storage"], "failed")

    def test_concurrent_runs_do_not_share_calls(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier = Barrier(2)
        def transport(payload, key, timeout):
            names = payload["response_format"]["json_schema"]["schema"]["required"]
            if "project_name" in names:
                barrier.wait(timeout=5)
                return response(core())
            return response(features())
        analyzer = SolarAnalyzer("synthetic-key", transport=transport)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda i: analyzer.analyze("Alpha registration", "doc-" + str(i)), range(2)))
        self.assertNotEqual(results[0].diagnostics["run_id"], results[1].diagnostics["run_id"])
        self.assertIsNot(results[0].diagnostics["calls"], results[1].diagnostics["calls"])
        self.assertEqual([len(r.diagnostics["calls"]) for r in results], [2, 2])

    def test_nested_escaped_key_and_invalid_json_are_omitted(self):
        from agentfit_ai.diagnostics import LocalDiagnosticsStore
        encoded_key = "".join("\\u%04x" % ord(c) for c in "synthetic-key")
        inner = '{"secret":"' + encoded_key + '"}'
        payload = {"choices": [{"finish_reason": "length", "message": {"content": inner}}]}
        for raw in (json.dumps(payload).encode(), b"not-json"):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(AnalysisError):
                    SolarAnalyzer("synthetic-key", transport=Mock(return_value=raw),
                        diagnostics_store=LocalDiagnosticsStore(Path(folder))).analyze("Alpha", "doc")
                saved = json.loads(next(Path(folder).glob("*.json")).read_text())
                self.assertEqual(saved["failed_responses"], [])

    def test_preflight_failure_has_no_provider_calls_or_storage(self):
        store = Mock()
        transport = Mock()
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key", transport=transport, diagnostics_store=store).analyze("", "doc")
        self.assertEqual(caught.exception.provider_calls, 0)
        transport.assert_not_called()
        store.write.assert_not_called()
