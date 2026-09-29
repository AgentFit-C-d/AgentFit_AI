"""Token-limited parent reviews may be replaced only by complete child coverage."""

import json
import unittest
from types import SimpleNamespace

from agentfit_ai.candidate_first_profile import analyze_candidate_first
from agentfit_ai.candidate_split_review import review_candidates_separately
from agentfit_ai.solar import AnalysisError
from agentfit_ai.profile import FIELDS
from tests.test_candidate_split_review import fixture, response


class CandidateAdaptiveReviewTests(unittest.TestCase):
    def test_pipeline_only_completes_after_recovered_batch_and_coverage(self):
        calls, reviewed = [], []
        def extractor(document, key, **kwargs):
            return [SimpleNamespace(extraction_class="candidate", extraction_text="Go")]
        def transport(payload, key, timeout):
            if payload["response_format"]["json_schema"]["name"] == "agentfit_candidate_labels":
                return response({"labels": [{"id": f"C{i:03}", "field": "backend", "status": "confirmed"}
                                            for i in range(6)]})
            data = json.loads(payload["messages"][1]["content"])
            if "selections" not in data:
                self.assertEqual(reviewed, [6, 5, 1])
                return response({"checkedFields": list(FIELDS), "missingFields": []})
            ids = [row["id"] for row in data["selections"]]
            reviewed.append(len(ids))
            return response({}, finish="length") if len(ids) == 6 else response({
                "checkedCandidateIds": ids, "wrongCandidateIds": []})
        result = analyze_candidate_first("Go " * 6, "test", "fake", extractor=extractor,
                                         transport=transport, source_occurrences=True, split_review=True,
                                         adaptive_review=True, review_calls=calls)
        self.assertEqual(result["outcome"], "candidate_profile")
        self.assertEqual(result["profile"]["data"]["backend"], ["Go"])
        self.assertTrue(calls[0]["recovered"])
        self.assertEqual(calls[-1]["stage"], "source_coverage")

    def test_length_parent_is_replaced_by_all_children_before_coverage(self):
        document, frozen, labels = fixture(21)
        batches, calls, documents = [], [], []
        def transport(payload, key, timeout):
            data = json.loads(payload["messages"][1]["content"])
            documents.append(data["document"])
            if "selections" not in data:
                self.assertEqual(len(batches), 6)
                return response({"checkedFields": list(FIELDS), "missingFields": []})
            ids = [row["id"] for row in data["selections"]]
            batches.append(ids)
            if len(batches) == 1:
                return response({}, finish="length")
            return response({"checkedCandidateIds": ids,
                             "wrongCandidateIds": ["C007"] if "C007" in ids else []})
        result = review_candidates_separately(document, frozen, labels, "fake", transport=transport,
                                             adaptive_review=True, review_calls=calls)
        self.assertEqual([len(batch) for batch in batches], [20, 5, 5, 5, 5, 1])
        self.assertEqual([item for batch in batches[1:5] for item in batch], batches[0])
        self.assertEqual(batches[-1], ["C020"])
        self.assertEqual(result["wrongCandidateIds"], ["C007"])
        self.assertTrue(all(value == document for value in documents))
        self.assertFalse(calls[0]["validated"])
        self.assertTrue(calls[0]["recovered"])
        self.assertEqual([row["sub_batch_index"] for row in calls[1:5]], [1, 2, 3, 4])

    def test_failed_child_stops_without_coverage_or_recursive_retry(self):
        document, frozen, labels = fixture(20)
        calls, requests = [], []
        def transport(payload, key, timeout):
            data = json.loads(payload["messages"][1]["content"])
            requests.append(data)
            ids = [row["id"] for row in data["selections"]]
            if len(requests) == 2:
                return response({"checkedCandidateIds": ids, "wrongCandidateIds": []})
            return response({}, finish="length")
        with self.assertRaises(AnalysisError):
            review_candidates_separately(document, frozen, labels, "fake", transport=transport,
                                         adaptive_review=True, review_calls=calls)
        self.assertEqual(len(requests), 3)
        self.assertFalse(calls[0]["recovered"])
        self.assertEqual(calls[-1]["sub_batch_index"], 2)

    def test_no_retry_for_other_failures_small_batches_or_default_mode(self):
        for mode, count, finish, model, timeout_error in (
                (False, 20, "length", "solar-pro4-260806", False),
                (True, 5, "length", "solar-pro4-260806", False),
                (True, 20, "stop", "solar-pro4-260806", False),
                (True, 20, "length", "other-model", False),
                (True, 20, "stop", "solar-pro4-260806", True)):
            document, frozen, labels = fixture(count)
            requests = []
            def transport(payload, key, timeout):
                requests.append(payload)
                if timeout_error:
                    raise TimeoutError()
                return response({"checkedCandidateIds": [], "wrongCandidateIds": []},
                                finish=finish, model=model)
            with self.subTest(mode=mode, count=count, finish=finish, model=model, timeout=timeout_error):
                with self.assertRaises((AnalysisError, ValueError)):
                    review_candidates_separately(document, frozen, labels, "fake", transport=transport,
                                                 adaptive_review=mode)
                self.assertEqual(len(requests), 1)

    def test_source_coverage_length_is_not_split(self):
        requests = []
        def transport(payload, key, timeout):
            requests.append(payload)
            return response({}, finish="length")
        with self.assertRaises(AnalysisError):
            review_candidates_separately("Alpha", {"candidates": [], "rejected": []}, [], "fake",
                                         transport=transport, adaptive_review=True)
        self.assertEqual(len(requests), 1)
