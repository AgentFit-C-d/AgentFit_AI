"""Split review must verify every batch before permitting projection."""

import json
from types import SimpleNamespace
import unittest

from agentfit_ai.candidate_first_profile import analyze_candidate_first, CandidatePipelineError
from agentfit_ai.profile import FIELDS


def response(content, *, finish="stop", model="solar-pro4-260806"):
    return json.dumps({"model": model, "choices": [{"finish_reason": finish,
                      "message": {"content": json.dumps(content)}}], "usage": {}}).encode()


def fixture(count=21):
    document = " ".join(["Go"] * count) + " Python"
    candidates = [{"id": f"C{i:03}", "start": i * 3, "end": i * 3 + 2}
                  for i in range(count)]
    candidates.append({"id": "T", "start": len(document) - 6, "end": len(document)})
    labels = [{"id": row["id"], "field": "backend", "status": "confirmed"}
              for row in candidates[:-1]]
    labels.append({"id": "T", "field": "backend", "status": "tentative"})
    return document, {"candidates": candidates, "rejected": []}, labels


class CandidateSplitReviewTests(unittest.TestCase):
    def test_all_batches_keep_occurrences_then_coverage_deduplicates_safe_values(self):
        from agentfit_ai.candidate_split_review import review_candidates_separately
        document, frozen, labels = fixture()
        requests = []
        def transport(payload, key, timeout):
            data = json.loads(payload["messages"][1]["content"])
            requests.append(data)
            if "selections" in data:
                ids = [row["id"] for row in data["selections"]]
                return response({"checkedCandidateIds": ids,
                                 "wrongCandidateIds": ["C020"] if "C020" in ids else []})
            return response({"checkedFields": list(FIELDS), "missingFields": ["features"]})
        result = review_candidates_separately(document, frozen, labels, "fake", transport=transport)
        self.assertEqual([len(r["selections"]) for r in requests[:-1]], [20, 1])
        self.assertEqual(requests[1]["selections"][0]["start"], 60)
        self.assertEqual(requests[1]["selections"][0]["value"], "Go")
        self.assertEqual(requests[1]["selections"][0]["after"], " Python")
        self.assertEqual(requests[-1]["confirmedValues"]["backend"], ["Go"])
        self.assertEqual(requests[-1]["document"], document)
        self.assertNotIn("Python", json.dumps(requests[-1]["confirmedValues"]))
        self.assertEqual(result, {"checkedFields": list(FIELDS), "missingFields": ["features"],
                                  "wrongCandidateIds": ["C020"]})

    def test_invalid_batch_never_reaches_coverage(self):
        from agentfit_ai.candidate_split_review import review_candidates_separately
        document, frozen, labels = fixture()
        ids = [f"C{i:03}" for i in range(20)]
        bads = [({"checkedCandidateIds": ids[:-1], "wrongCandidateIds": []}, {}),
                ({"checkedCandidateIds": ids[::-1], "wrongCandidateIds": []}, {}),
                ({"checkedCandidateIds": ids, "wrongCandidateIds": ["C020"]}, {}),
                ({"checkedCandidateIds": ids, "wrongCandidateIds": ["C000", "C000"]}, {}),
                ({"checkedCandidateIds": ids, "wrongCandidateIds": []}, {"finish": "length"}),
                ({"checkedCandidateIds": ids, "wrongCandidateIds": []}, {"model": "other"})]
        for content, kwargs in bads:
            calls = []
            def transport(payload, key, timeout):
                calls.append(payload)
                return response(content, **kwargs)
            with self.subTest(content=content, kwargs=kwargs), self.assertRaises(Exception):
                review_candidates_separately(document, frozen, labels, "fake", transport=transport)
            self.assertEqual(len(calls), 1)

    def test_empty_candidates_still_require_complete_source_coverage(self):
        from agentfit_ai.candidate_split_review import review_candidates_separately
        for content in ({"checkedFields": [], "missingFields": []},
                        {"checkedFields": list(FIELDS), "missingFields": ["backend", "backend"]},
                        {"checkedFields": list(FIELDS), "missingFields": ["unknown"]}):
            def transport(payload, key, timeout):
                data = json.loads(payload["messages"][1]["content"])
                self.assertTrue(all(not values for values in data["confirmedValues"].values()))
                return response(content)
            with self.subTest(content=content), self.assertRaises(ValueError):
                review_candidates_separately("Alpha", {"candidates": [], "rejected": []}, [],
                                             "fake", transport=transport)

    def test_pipeline_removes_wrong_value_before_coverage_and_defers(self):
        def extractor(document, key, **kwargs):
            return [SimpleNamespace(extraction_class="candidate", extraction_text="Go",
                                    attributes=None, char_interval=None)]
        def transport(payload, key, timeout):
            name = payload["response_format"]["json_schema"]["name"]
            if name == "agentfit_candidate_labels":
                return response({"labels": [{"id": "C000", "field": "backend", "status": "confirmed"}]})
            data = json.loads(payload["messages"][1]["content"])
            if "selections" in data:
                return response({"checkedCandidateIds": ["C000"], "wrongCandidateIds": ["C000"]})
            self.assertEqual(data["confirmedValues"]["backend"], [])
            return response({"checkedFields": list(FIELDS), "missingFields": []})
        result = analyze_candidate_first("Go is rejected", "test", "fake", extractor=extractor,
                                         transport=transport, source_occurrences=True, split_review=True)
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertIsNone(result["profile"]["data"]["backend"])
        self.assertEqual(result["unresolvedFields"], ["backend"])

    def test_late_review_failure_never_projects(self):
        events = []
        def extractor(document, key, **kwargs):
            return [SimpleNamespace(extraction_class="candidate", extraction_text="Alpha",
                                    attributes=None, char_interval=None)]
        def transport(payload, key, timeout):
            name = payload["response_format"]["json_schema"]["name"]
            if name == "agentfit_candidate_labels":
                return response({"labels": [{"id": "C000", "field": "project_name", "status": "confirmed"}]})
            if "selections" in json.loads(payload["messages"][1]["content"]):
                return response({"checkedCandidateIds": ["C000"], "wrongCandidateIds": []})
            return response({}, finish="length")
        with self.assertRaises(CandidatePipelineError) as caught:
            analyze_candidate_first("Alpha", "test", "fake", extractor=extractor,
                                    transport=transport, source_occurrences=True, split_review=True,
                                    observer=lambda stage, state: events.append(stage))
        self.assertEqual(caught.exception.stage, "COVERAGE_REVIEW_FAILED")
        self.assertEqual(events, ["grounded", "classified"])
