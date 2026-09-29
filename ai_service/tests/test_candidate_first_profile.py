"""Candidate-first Profile projection uses only verified source positions."""

from types import SimpleNamespace
import json
import unittest

from agentfit_ai.candidate_first_profile import (
    freeze_candidates, validate_candidate_labels, project_candidate_profile,
    candidate_label_payload, classify_profile_candidates,
    extract_profile_candidates, coverage_review_payload,
    review_candidate_coverage, analyze_candidate_first)
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.candidate_first_profile import CandidateContractError
from agentfit_ai.profile import FIELDS


def extraction(quote, anchor=None):
    attributes = None if anchor is None else {"anchor": anchor}
    return SimpleNamespace(extraction_class="candidate", extraction_text=quote,
                           attributes=attributes, char_interval=None)


class CandidateFirstProfileTests(unittest.TestCase):
    def test_label_and_review_requests_identify_each_repeated_occurrence(self):
        document = "이전 제품은 Go를 쓴다.\r\n🚀 현재 제품은 Go를 검토 중이다."
        first = document.index("Go")
        second = document.rindex("Go")
        # IDs and order deliberately do not encode source order.
        frozen = {"candidates": [
            {"id": "C000", "start": second, "end": second + 2},
            {"id": "C001", "start": first, "end": first + 2}], "rejected": []}
        labels = [{"id": item["id"], "field": "backend", "status": "tentative"}
                  for item in frozen["candidates"]]
        label_request = json.loads(candidate_label_payload(
            document, frozen["candidates"])["messages"][1]["content"])
        review_request = json.loads(coverage_review_payload(
            document, frozen, labels)["messages"][1]["content"])
        for rows in (label_request["candidates"], review_request["selections"]):
            for row, source in zip(rows, frozen["candidates"]):
                self.assertEqual(row.get("start"), source["start"])
                self.assertEqual(row.get("end"), source["end"])
                self.assertEqual(row["value"], "Go")
                self.assertEqual(row.get("before"), document[:source["start"]])
                self.assertEqual(row.get("after"), document[source["end"]:])

    def test_mention_context_is_bounded_exact_source_without_normalization(self):
        document = "가" * 300 + "🚀\r\nGo\r\n" + "나" * 300
        start = document.index("Go")
        request = json.loads(candidate_label_payload(document, [
            {"id": "C000", "start": start, "end": start + 2}])[
                "messages"][1]["content"])
        item = request["candidates"][0]
        self.assertEqual(item.get("before"), document[start - 240:start])
        self.assertEqual(item.get("after"), document[start + 2:start + 242])

    def test_coverage_request_rejects_invalid_candidate_positions(self):
        labels = [{"id": "C000", "field": "backend", "status": "confirmed"}]
        for start, end in ((-1, 1), (0, 9), (2, 1), (True, 2)):
            frozen = {"candidates": [{"id": "C000", "start": start,
                                      "end": end}], "rejected": []}
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                coverage_review_payload("Go", frozen, labels)

    def test_repeated_mentions_get_stable_ids_and_exact_positions(self):
        document = "Go는 검토 중이다. Go를 서버로 확정했다."
        frozen = freeze_candidates(document, [
            extraction("Go", "Go는 검토 중이다."),
            extraction("Go", "Go를 서버로 확정했다.")])
        self.assertEqual([item["id"] for item in frozen["candidates"]],
                         ["C000", "C001"])
        self.assertEqual([document[item["start"]:item["end"]]
                          for item in frozen["candidates"]], ["Go", "Go"])
        self.assertNotEqual(frozen["candidates"][0]["start"],
                            frozen["candidates"][1]["start"])
        self.assertEqual(frozen["rejected"], [])

    def test_ambiguous_or_duplicate_candidates_do_not_pass(self):
        document = "Go와 Go"
        frozen = freeze_candidates(document, [
            extraction("Go"), extraction("Go", "Go와 Go")])
        self.assertEqual(frozen["candidates"], [])
        self.assertEqual(len(frozen["rejected"]), 2)

    def test_labels_must_cover_each_candidate_id_exactly_once(self):
        document = "Alpha 검색"
        frozen = freeze_candidates(document, [extraction("Alpha"),
                                              extraction("검색")])
        labels = [{"id": "C000", "field": "project_name",
                   "status": "confirmed"},
                  {"id": "C001", "field": "features",
                   "status": "confirmed"}]
        self.assertEqual(validate_candidate_labels(frozen, labels), labels)
        for bad in (labels[:1], labels + labels[:1],
                    [{**labels[0], "id": "C999"}, labels[1]],
                    [{**labels[0], "field": "unknown"}, labels[1]],
                    [{**labels[0], "status": "unknown"}, labels[1]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_candidate_labels(frozen, bad)
        with self.assertRaises(CandidateContractError) as caught:
            validate_candidate_labels(frozen, labels[:1])
        self.assertEqual(caught.exception.code, "LABEL_COUNT_MISMATCH")

    def test_confirmed_candidates_project_exact_profile_with_unknowns(self):
        document = "Alpha는 검색을 제공한다. Go는 검토 중이다."
        frozen = freeze_candidates(document, [
            extraction("Alpha"), extraction("검색"), extraction("Go")])
        labels = [{"id": "C000", "field": "project_name",
                   "status": "confirmed"},
                  {"id": "C001", "field": "features", "status": "confirmed"},
                  {"id": "C002", "field": "backend", "status": "tentative"}]
        result = project_candidate_profile(document, "doc", frozen, labels,
                                           coverage_verified=True)
        self.assertEqual(result["outcome"], "candidate_profile")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(result["profile"]["data"]["features"], ["검색"])
        self.assertIsNone(result["profile"]["data"]["backend"])
        span = result["profile"]["evidence"]["features"][0]
        self.assertEqual(document[span["start"]:span["end"]], "검색")

    def test_no_automatic_completion_without_coverage_or_with_conflicts(self):
        document = "Alpha 또는 Beta"
        frozen = freeze_candidates(document, [extraction("Alpha"),
                                              extraction("Beta")])
        labels = [{"id": "C000", "field": "project_name",
                   "status": "confirmed"},
                  {"id": "C001", "field": "project_name",
                   "status": "confirmed"}]
        result = project_candidate_profile(document, "doc", frozen, labels,
                                           coverage_verified=True)
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["unresolvedFields"], ["project_name"])
        self.assertIsNone(result["profile"]["data"]["project_name"])
        one = project_candidate_profile(document, "doc", frozen,
                                        [labels[0], {**labels[1],
                                                     "status": "irrelevant"}],
                                        coverage_verified=False)
        self.assertEqual(one["outcome"], "needs_confirmation")
        self.assertEqual(one["profile"]["data"]["project_name"], "Alpha")

    def test_classifier_returns_only_id_field_status_for_all_ten_fields(self):
        document = "Alpha 검색"
        frozen = freeze_candidates(document, [extraction("Alpha"),
                                              extraction("검색")])
        payload = candidate_label_payload(document, frozen["candidates"])
        self.assertEqual(payload["reasoning_effort"], "medium")
        item_schema = payload["response_format"]["json_schema"]["schema"][
            "properties"]["labels"]["items"]
        self.assertEqual(set(item_schema["properties"]), {"id", "field", "status"})
        self.assertIn("external_integrations",
                      item_schema["properties"]["field"]["enum"])
        self.assertNotIn("quote", item_schema["properties"])

        labels = [{"id": "C000", "field": "project_name", "status": "confirmed"},
                  {"id": "C001", "field": "features", "status": "confirmed"}]
        def transport(request, key, timeout):
            self.assertEqual(key, "synthetic-key")
            self.assertEqual(timeout, 600)
            return json.dumps({"model": "solar-pro4-260806", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "labels": labels})}}], "usage": {}}).encode()
        self.assertEqual(classify_profile_candidates(
            document, frozen, "synthetic-key", transport=transport), labels)

    def test_classifier_rejects_missing_id_in_model_response(self):
        document = "Alpha 검색"
        frozen = freeze_candidates(document, [extraction("Alpha"),
                                              extraction("검색")])
        def transport(request, key, timeout):
            return json.dumps({"model": "solar-pro4-260806", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "labels": [{"id": "C000", "field": "project_name",
                                "status": "confirmed"}]})}}], "usage": {}}).encode()
        with self.assertRaises(ValueError):
            classify_profile_candidates(document, frozen, "synthetic-key",
                                        transport=transport)

    def test_classifier_discards_status_for_other_field(self):
        document = "내부 메모"
        frozen = freeze_candidates(document, [extraction("내부 메모")])
        def transport(request, key, timeout):
            return json.dumps({"model": "solar-pro4-260806", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "labels": [{"id": "C000", "field": "other",
                                "status": "confirmed"}]})}}], "usage": {}}).encode()
        labels = classify_profile_candidates(document, frozen,
                                             "synthetic-key", transport=transport)
        self.assertEqual(labels[0], {"id": "C000", "field": "other",
                                     "status": "irrelevant"})

    def test_profile_extractor_requests_all_field_facts_without_status_decision(self):
        captured = {}
        def extractor(document, key, *, prompt_description, max_tokens):
            captured["prompt"] = prompt_description
            captured["max_tokens"] = max_tokens
            return [extraction("Alpha")]
        result = extract_profile_candidates("Alpha", "synthetic-key",
                                            extractor=extractor)
        self.assertEqual(len(result), 1)
        self.assertIn("project name", captured["prompt"])
        self.assertIn("product capabilities", captured["prompt"])
        self.assertIn("tentative", captured["prompt"])
        self.assertEqual(captured["max_tokens"], 8192)

    def test_coverage_review_checks_every_field_and_known_ids(self):
        document = "Alpha 검색"
        frozen = freeze_candidates(document, [extraction("Alpha"),
                                              extraction("검색")])
        labels = [{"id": "C000", "field": "project_name",
                   "status": "confirmed"},
                  {"id": "C001", "field": "features", "status": "confirmed"}]
        payload = coverage_review_payload(document, frozen, labels)
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]),
                         {"checkedFields", "missingFields", "wrongCandidateIds"})

        def transport(request, key, timeout):
            self.assertEqual(timeout, 600)
            return json.dumps({"model": "solar-pro4-260806", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "checkedFields": list(FIELDS), "missingFields": [],
                    "wrongCandidateIds": []})}}], "usage": {}}).encode()
        review = review_candidate_coverage(document, frozen, labels,
                                           "synthetic-key", transport=transport)
        self.assertEqual(review["missingFields"], [])
        self.assertEqual(review["checkedFields"], list(FIELDS))

    def test_coverage_review_rejects_incomplete_field_check(self):
        document = "Alpha"
        frozen = freeze_candidates(document, [extraction("Alpha")])
        labels = [{"id": "C000", "field": "project_name",
                   "status": "confirmed"}]
        def transport(request, key, timeout):
            return json.dumps({"model": "solar-pro4-260806", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps({
                    "checkedFields": list(FIELDS[:-1]), "missingFields": [],
                    "wrongCandidateIds": []})}}], "usage": {}}).encode()
        with self.assertRaises(ValueError):
            review_candidate_coverage(document, frozen, labels,
                                      "synthetic-key", transport=transport)

    def test_pipeline_builds_profile_after_complete_review(self):
        document = "Alpha는 검색을 제공한다."
        calls = []
        def extractor(source, key, *, prompt_description, max_tokens):
            return [extraction("Alpha"), extraction("검색")]
        def transport(request, key, timeout):
            name = request["response_format"]["json_schema"]["name"]
            calls.append(name)
            body = ({"labels": [
                {"id": "C000", "field": "project_name", "status": "confirmed"},
                {"id": "C001", "field": "features", "status": "confirmed"}]}
                if name == "agentfit_candidate_labels" else
                {"checkedFields": list(FIELDS), "missingFields": [],
                 "wrongCandidateIds": []})
            return json.dumps({"model": "solar-pro4-260806", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps(body)}}],
                "usage": {}}).encode()
        result = analyze_candidate_first(document, "doc", "synthetic-key",
                                         extractor=extractor, transport=transport)
        self.assertEqual(result["outcome"], "candidate_profile")
        self.assertEqual(result["profile"]["data"]["features"], ["검색"])
        self.assertEqual(calls, ["agentfit_candidate_labels",
                                 "agentfit_candidate_coverage"])

    def test_review_wrong_id_clears_suggestion_and_blocks_completion(self):
        document = "Alpha"
        def extractor(source, key, *, prompt_description, max_tokens):
            return [extraction("Alpha")]
        def transport(request, key, timeout):
            name = request["response_format"]["json_schema"]["name"]
            body = ({"labels": [{"id": "C000", "field": "project_name",
                                 "status": "confirmed"}]}
                    if name == "agentfit_candidate_labels" else
                    {"checkedFields": list(FIELDS), "missingFields": [],
                     "wrongCandidateIds": ["C000"]})
            return json.dumps({"model": "solar-pro4-260806", "choices": [{
                "finish_reason": "stop", "message": {"content": json.dumps(body)}}],
                "usage": {}}).encode()
        result = analyze_candidate_first(document, "doc", "synthetic-key",
                                         extractor=extractor, transport=transport)
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertIsNone(result["profile"]["data"]["project_name"])
        self.assertEqual(result["unresolvedFields"], ["project_name"])

    def test_pipeline_failure_reports_stage_without_private_exception(self):
        def extractor(source, key, *, prompt_description, max_tokens):
            raise RuntimeError("private model response")
        with self.assertRaises(CandidatePipelineError) as caught:
            analyze_candidate_first("Alpha", "doc", "synthetic-key",
                                    extractor=extractor)
        self.assertEqual(caught.exception.stage, "EXTRACTION_FAILED")
        self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
