import json
import unittest
from unittest.mock import Mock

from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from agentfit_ai.solar import AnalysisError
from test_semantic_review import verdict
from test_staged_analysis import response


class KeyedProfileIntegrationTests(unittest.TestCase):
    def test_option_requires_v2_and_occurrence_expansion(self):
        for options in ({}, {"prompt_revision": "v2"}):
            with self.assertRaises(ValueError):
                AnchoredAnalyzer("synthetic-key", keyed_candidates=True, **options)
        AnchoredAnalyzer("synthetic-key", prompt_revision="v2",
                         candidate_occurrences=True, keyed_candidates=True)

    def test_two_batches_normalize_before_judgment(self):
        document = "\n".join(f"# H{i}\nValue{i}" for i in range(1, 7))
        seen = []

        def transport(payload, *args):
            schema = payload["response_format"]["json_schema"]["schema"]
            if "checkedFields" in schema["properties"]:
                return response(verdict())
            content = json.loads(payload["messages"][1]["content"])
            if "units" in content:
                self.assertEqual(schema["properties"]["units"]["type"], "object")
                seen.extend(unit["unitId"] for unit in content["units"])
                return response({"units": {unit["unitId"]: ["Value6"] if "Value6" in unit["text"] else []
                                           for unit in content["units"]}})
            if "candidates" in content:
                self.assertEqual(len(seen), 12)
                candidates = content["candidates"]
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0]["quote"], "Value6")
                return response({"decisions": {candidates[0]["id"]: {
                    "field": "project_name", "role": "product_fact", "status": "confirmed",
                    "scope": "current", "decision": "selected"}}})
            self.fail("unexpected stage")

        analyzer = AnchoredAnalyzer("synthetic-key", transport=Mock(side_effect=transport),
                                   prompt_revision="v2", candidate_occurrences=True,
                                   keyed_candidates=True)
        result = analyzer.analyze(document, "doc")
        self.assertEqual(result.provider_calls, 4)
        self.assertEqual(result.profile["data"]["project_name"], "Value6")
        self.assertEqual(result.diagnostics["sections_covered"], 12)

    def test_second_batch_failure_has_no_partial_profile(self):
        document = "\n".join(f"# H{i}\nValue{i}" for i in range(1, 7))
        calls = []

        def transport(payload, *args):
            content = json.loads(payload["messages"][1]["content"])
            calls.append(content)
            if len(calls) == 1:
                return response({"units": {unit["unitId"]: [] for unit in content["units"]}})
            return response({"units": {unit["unitId"]: ["invented"] if i == 0 else []
                                       for i, unit in enumerate(content["units"])}})

        analyzer = AnchoredAnalyzer("synthetic-key", transport=Mock(side_effect=transport),
                                   prompt_revision="v2", candidate_occurrences=True,
                                   keyed_candidates=True)
        with self.assertRaises(AnalysisError) as caught:
            analyzer.analyze(document, "doc")
        self.assertEqual(caught.exception.code, "ANCHORED_CANDIDATE")
        self.assertEqual(len(calls), 2)
        self.assertEqual(caught.exception.diagnostics["sections_covered"], 0)
