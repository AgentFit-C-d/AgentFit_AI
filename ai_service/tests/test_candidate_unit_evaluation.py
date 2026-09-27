import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentfit_ai.embedding_section_evaluation import load_cases
from agentfit_ai.solar import AnalysisError
from agentfit_ai.candidate_unit_evaluation import main, new_candidate_recall


class CandidateUnitEvaluationTests(unittest.TestCase):
    def test_new_arm_recovers_wrong_unit_quote_with_two_calls(self):
        case = next(case for case in load_cases()[0] if case["id"] == "E03")

        class FakeAnalyzer:
            def __init__(self, *args, **kwargs):
                self.calls = 0

            def _send_payload(self, payload, names, **kwargs):
                self.calls += 1
                self.assert_payload(payload)
                content = json.loads(payload["messages"][1]["content"])
                quotes = {"U0002": ["도서 예약 서비스"], "U0003": ["Fly.io"],
                          "U0004": ["Fly.io"], "U0005": ["좌석을 예약하고"]}
                return {"units": {unit["unitId"]: quotes.get(unit["unitId"], [])
                                  for unit in content["units"]}}, "solar-pro4", 1, 1

            @staticmethod
            def assert_payload(payload):
                assert payload["model"] == "solar-pro4"
                assert payload["max_tokens"] == 4096
                assert payload["temperature"] == 0
                assert payload["response_format"]["json_schema"]["strict"] is True

        with patch("agentfit_ai.candidate_unit_evaluation.SolarAnalyzer", FakeAnalyzer):
            result = new_candidate_recall(case, "private-dummy-credential")
        self.assertEqual((result["matched"], result["total"], result["calls"]), (3, 3, 2))
        self.assertEqual((result["remapped"], result["deduplicated"]), (1, 1))
        self.assertNotIn("error", result)

    def test_first_and_second_batch_errors_report_actual_calls_without_partial_result(self):
        case = next(case for case in load_cases()[0] if case["id"] == "E03")
        for fail_at in (1, 2):
            class FakeAnalyzer:
                def __init__(self, *args, **kwargs):
                    self.calls = 0

                def _send_payload(self, payload, names, **kwargs):
                    self.calls += 1
                    if self.calls == fail_at:
                        raise AnalysisError("PROVIDER_FAILURE")
                    content = json.loads(payload["messages"][1]["content"])
                    return {"units": {unit["unitId"]: ["도서 예약 서비스"]
                                      if unit["unitId"] == "U0002" else []
                                      for unit in content["units"]}}, "solar-pro4", 1, 1

            with patch("agentfit_ai.candidate_unit_evaluation.SolarAnalyzer", FakeAnalyzer):
                result = new_candidate_recall(case, "private-dummy-credential")
            self.assertEqual((result["matched"], result["calls"], result["error"]),
                             (0, fail_at, "PROVIDER_FAILURE"))
            self.assertNotIn("candidate_count", result)

    def test_cli_writes_only_safe_metrics_and_requires_live_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run"
            with patch.object(sys, "argv", ["eval", "--output", str(output)]), \
                 patch("agentfit_ai.candidate_unit_evaluation.load_key") as load_key:
                with self.assertRaises(SystemExit):
                    main()
                load_key.assert_not_called()
            def success(case, _key, **_kwargs):
                count = len(case["gold"])
                return {"matched": count, "total": count, "candidate_count": count,
                        "calls": 2, "elapsed_ms": 100}
            with patch.object(sys, "argv", ["eval", "--live", "--output", str(output)]), \
                 patch("agentfit_ai.candidate_unit_evaluation.load_key", return_value="private-dummy-credential"), \
                 patch("agentfit_ai.candidate_unit_evaluation.candidate_recall", side_effect=success), \
                 patch("agentfit_ai.candidate_unit_evaluation.new_candidate_recall", side_effect=success):
                self.assertEqual(main(), 0)
            files = list(output.iterdir())
            self.assertEqual({file.name for file in files}, {"plan.json", "results.json", "summary.json"})
            written = "\n".join(file.read_text(encoding="utf-8") for file in files)
            self.assertNotIn("private-dummy-credential", written)
            self.assertNotIn('"document"', written)
            self.assertNotIn('"sections"', written)
            self.assertNotIn('"quote"', written)


if __name__ == "__main__":
    unittest.main()
