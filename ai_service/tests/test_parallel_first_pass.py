import threading
import unittest

from agentfit_ai.recoverable_solar_analysis import RecoverableSolarAnalyzer
from test_semantic_review import verdict
from test_staged_analysis import core, features, response


def payload_stage(payload):
    required = payload["response_format"]["json_schema"]["schema"]["required"]
    return ("review" if "checkedFields" in required else
            "features" if required == ["features"] else "core")


class ParallelFirstPassTests(unittest.TestCase):
    def test_opt_in_overlaps_independent_calls_and_preserves_result(self):
        entered = threading.Barrier(2, timeout=5)
        stages = []

        def transport(payload, key, timeout):
            stage = payload_stage(payload)
            stages.append(stage)
            if stage != "review":
                entered.wait()
            return response({"core": core, "features": features,
                             "review": verdict}[stage]())

        class RecordingAnalyzer(RecoverableSolarAnalyzer):
            def _save_diagnostic(self, diagnostic, raw_responses):
                self.stages = [call["stage"] for call in diagnostic["calls"]]

        analyzer = RecordingAnalyzer(
            "synthetic-key", evidence_contract=False, transport=transport,
            parallel_first_pass=True)
        result = analyzer.analyze_recoverable("Alpha registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["features"], ["registration"])
        self.assertEqual(set(stages[:2]), {"core", "features"})
        self.assertEqual(stages[2], "review")
        self.assertEqual(analyzer.stages, ["core", "features", "semantic_review"])

    def test_opt_out_keeps_sequential_call_order(self):
        stages = []

        def transport(payload, key, timeout):
            stage = payload_stage(payload)
            stages.append(stage)
            return response({"core": core, "features": features,
                             "review": verdict}[stage]())

        result = RecoverableSolarAnalyzer(
            "synthetic-key", evidence_contract=False, transport=transport,
            parallel_first_pass=False).analyze_recoverable(
                "Alpha registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(stages, ["core", "features", "review"])

    def test_opt_in_waits_for_other_first_call_after_failure(self):
        both_started = threading.Barrier(2, timeout=5)
        active = 0
        guard = threading.Lock()
        stages = []

        def transport(payload, key, timeout):
            nonlocal active
            stage = payload_stage(payload)
            with guard:
                active += 1
                stages.append(stage)
            try:
                both_started.wait()
                if stage == "core":
                    raise TimeoutError("private provider detail")
                return response(features())
            finally:
                with guard:
                    active -= 1

        result = RecoverableSolarAnalyzer(
            "synthetic-key", evidence_contract=False, transport=transport,
            parallel_first_pass=True).analyze_recoverable(
                "Alpha registration", "doc")
        self.assertEqual(result, {"outcome": "failed", "error": "PROVIDER_TIMEOUT"})
        self.assertEqual(active, 0)
        self.assertEqual(set(stages), {"core", "features"})

    def test_option_requires_boolean(self):
        with self.assertRaisesRegex(ValueError, "parallel_first_pass"):
            RecoverableSolarAnalyzer("synthetic-key", parallel_first_pass="true")


if __name__ == "__main__":
    unittest.main()
