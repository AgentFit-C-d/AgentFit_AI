import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agentfit_ai.langextract_solar_trial import candidate_payload, score_case, main, run_case


def extraction(text, start, end):
    return SimpleNamespace(extraction_class="candidate", extraction_text=text,
                           char_interval=SimpleNamespace(start_pos=start, end_pos=end))


class LangExtractSolarTrialTests(unittest.TestCase):
    def test_payload_keeps_candidate_schema_and_bounded_model(self):
        payload = candidate_payload("example prompt")
        self.assertEqual(payload["model"], "solar-pro4")
        self.assertEqual(payload["messages"][1]["content"], "example prompt")
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]
                         ["properties"]["extractions"]["items"]["properties"],
                         {"candidate": {"type": "string"}})
        self.assertEqual(payload["max_tokens"], 4096)

    def test_score_requires_exact_gold_span_and_candidate_local_rule(self):
        document = "팀 채팅은 검토안이다. 팀 채팅을 출시 기능으로 확정했다."
        quote = "팀 채팅"
        first, second = document.index(quote), document.rindex(quote)
        case = {"id": "T01", "document": document,
                "candidate": {"field": "features", "state": "present",
                              "start": first, "end": first + len(quote)},
                "expected_decision": "review"}
        row = score_case(case, [extraction(quote, first, first + len(quote)),
                                extraction(quote, second, second + len(quote))])
        self.assertEqual(row["decision"], "review")
        self.assertTrue(row["evidence_exact"])
        self.assertEqual(row["false_auto_confirmation"], 0)
        self.assertNotIn(document, json.dumps(row, ensure_ascii=False))
        self.assertNotIn(quote, json.dumps(row, ensure_ascii=False))

    def test_single_repeated_quote_cannot_autoconfirm_later_occurrence(self):
        document = "후보는 PineDB다. 운영 DB는 PineDB로 확정했다."
        quote = "PineDB"
        second = document.rindex(quote)
        case = {"id": "T02", "document": document,
                "candidate": {"field": "database", "state": "present",
                              "start": second, "end": second + len(quote)},
                "expected_decision": "allow"}
        first = document.index(quote)
        row = score_case(case, [extraction(quote, first, first + len(quote))])
        self.assertEqual(row["decision"], "missing")
        self.assertEqual(row["missed_allow"], 1)

    def test_duplicate_span_is_reported_separately_from_missing_candidate(self):
        document = "Alpha를 사용한다."
        case = {"id": "T03", "document": document,
                "candidate": {"field": "features", "state": "present",
                              "start": 0, "end": 5},
                "expected_decision": "allow"}
        row = score_case(case, [extraction("Alpha", 0, 5),
                                extraction("Alpha", 0, 5)])
        self.assertEqual(row["decision"], "review")
        self.assertEqual(row["duplicate_span_count"], 1)
        self.assertEqual(row["missing_candidate"], 0)

    def test_live_transport_uses_bounded_subprocess_path(self):
        from agentfit_ai import langextract_solar_trial as trial

        self.assertIs(trial.run_case.__kwdefaults__["transport"], trial.post_solar)
        self.assertGreater(trial.CALL_TIMEOUT_SECONDS, 120)

    def test_cli_requires_live_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            with patch.object(sys, "argv", ["trial", "--case-id", "R01",
                                                "--output", str(output)]):
                with self.assertRaises(SystemExit):
                    main()
            output.write_text("existing", encoding="utf-8")
            with patch.object(sys, "argv", ["trial", "--live", "--case-id",
                                                "R01", "--output", str(output)]):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_all_mode_writes_only_safe_counts_and_keeps_failed_cases(self):
        from agentfit_ai import langextract_solar_trial as trial

        cases = [{"id": "T01", "document": "Secret Alpha", "candidate": {
            "field": "features", "state": "present", "start": 7, "end": 12},
            "expected_decision": "allow"},
                 {"id": "T02", "document": "Secret Beta", "candidate": {
                     "field": "features", "state": "present", "start": 7, "end": 11},
                     "expected_decision": "review"}]
        cases.extend({"id": f"T{index:02d}", "document": f"Synthetic {index}",
                      "candidate": {"field": "features", "state": "present",
                                    "start": 0, "end": 1},
                      "expected_decision": "allow"}
                     for index in range(3, 19))
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "cases.json"
            output = Path(temp) / "result.json"
            fixture.write_text(json.dumps({"version": "document-grounding-adversarial-v1",
                                           "cases": cases}), encoding="utf-8")
            def fake_run(case, key, *, telemetry):
                if case["id"] == "T02":
                    raise RuntimeError("Secret Beta upstream failure")
                return {"case_id": case["id"], "decision": "allow",
                        "false_auto_confirmation": 0, "missed_allow": 0,
                        "missing_candidate": 0, "evidence_exact": True}
            with (patch.object(trial, "CASES_PATH", fixture),
                  patch.object(trial, "CASES_SHA256", hashlib.sha256(
                      fixture.read_bytes()).hexdigest()),
                  patch.object(trial, "load_key", return_value="synthetic-key"),
                  patch.object(trial, "run_case", side_effect=fake_run),
                  patch.object(sys, "argv", ["trial", "--live", "--all", "--output",
                                              str(output)])):
                self.assertEqual(trial.main(), 1)
            saved = output.read_text(encoding="utf-8")
            self.assertNotIn("Secret Alpha", saved)
            self.assertNotIn("Secret Beta", saved)
            self.assertNotIn("synthetic-key", saved)
            report = json.loads(saved)
            self.assertEqual(len(report["rows"]), 18)
            self.assertEqual(report["failed"], 1)

    def test_modified_fixture_is_rejected_before_loading_api_key(self):
        from agentfit_ai import langextract_solar_trial as trial

        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "cases.json"
            output = Path(temp) / "result.json"
            fixture.write_text(json.dumps({
                "version": "document-grounding-adversarial-v1",
                "cases": [{"id": "R01", "document": "private document"}] * 18}),
                encoding="utf-8")
            with (patch.object(trial, "CASES_PATH", fixture),
                  patch.object(trial, "load_key") as load_key,
                  patch.object(sys, "argv", ["trial", "--live", "--case-id",
                                              "R01", "--output", str(output)])):
                with self.assertRaises(SystemExit):
                    trial.main()
            load_key.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
