import json
import unittest
from unittest.mock import Mock

from agentfit_ai.profile import FIELDS
from agentfit_ai.grouped_review import GROUPS
from agentfit_ai.source_selector_analysis import SourceSelectorSolarAnalyzer
from test_semantic_review import verdict
from test_staged_analysis import response


def confirmed(line_id, selector="BODY", role="product_fact"):
    return {"state": "confirmed", "items": [
        {"lineId": line_id, "selector": selector, "role": role}]}


def core(selector="BODY"):
    fields = {field: None for field in FIELDS if field != "features"}
    fields["project_name"] = confirmed(1, selector)
    return fields


def features():
    return {"features": confirmed(2, role="user_action")}


class SourceSelectorAnalysisTests(unittest.TestCase):
    def test_section_extraction_has_own_1200_second_timeout_cap(self):
        options = {"grouped_review": True, "group_review_max_tokens": 8192,
                   "section_feature_review": True, "section_feature_extraction": True,
                   "experimental_long_timeout": True}
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", analysis_timeout_seconds=1200, **options)
        self.assertEqual(analyzer._analysis_timeout_seconds, 1200)
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer(
                "synthetic-key", analysis_timeout_seconds=1201, **options)
        options["section_feature_extraction"] = False
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer(
                "synthetic-key", analysis_timeout_seconds=1200, **options)

    def test_section_extraction_merges_two_chunks_before_review(self):
        document = "# Alpha\n- registration\n" + "context\n" * 118 + "# Next\n- checkout"
        group_replies = [{"checkedFields": list(group), "issues": []}
                         for group in GROUPS[:2]]
        section_replies = [{"checkedRange": {"start": start, "end": end},
                            "issues": []} for start, end in ((1, 120), (121, 122))]
        transport = Mock(side_effect=[
            response(core()), response(features()),
            response({"features": confirmed(122, role="user_action")}),
            *(response(item) for item in group_replies + section_replies),
        ])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["features"],
                         ["registration", "checkout"])
        self.assertEqual(transport.call_count, 7)
        self.assertNotIn("[L122] - checkout", transport.call_args_list[1].args[0]
                         ["messages"][1]["content"])

    def test_section_extraction_last_chunk_failure_is_not_partial_complete(self):
        document = "# Alpha\n- registration\n" + "context\n" * 118 + "# Next\n- checkout"
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response({"features": confirmed(2, role="user_action")})])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["error"], "INVALID_EVIDENCE")
        self.assertEqual(transport.call_count, 3)

    def test_section_extraction_requires_section_review(self):
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer("synthetic-key", grouped_review=True,
                                        group_review_max_tokens=8192,
                                        section_feature_extraction=True)

    def test_section_extraction_uses_eighteen_calls_with_repair_and_seven_chunks(self):
        document = "# Alpha\n- registration\n" + "context\n" * 838
        feature_chunks = [features(), *({"features": None} for _ in range(6))]
        groups = [{"checkedFields": list(group), "issues": []} for group in GROUPS[:2]]
        reviews = [{"checkedRange": {"start": start, "end": start + 119},
                    "issues": []} for start in range(1, 841, 120)]
        transport = Mock(side_effect=[
            response(core("BOLD_1")),
            *(response(item) for item in feature_chunks),
            response({"project_name": confirmed(1)}),
            *(response(item) for item in groups + reviews),
        ])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 18)

    def test_section_feature_review_completes_only_after_all_ranges(self):
        document = "# Alpha\n- registration\n" + "context\n" * 118 + "# Next\n- checkout"
        replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS[:2]]
        sections = [{"checkedRange": {"start": start, "end": end}, "issues": []}
                    for start, end in ((1, 120), (121, 122))]
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in replies + sections)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192,
            section_feature_review=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 6)
        self.assertEqual([call.args[0]["max_tokens"] for call in transport.call_args_list],
                         [4096, 4096, 8192, 8192, 8192, 8192])

    def test_section_feature_review_holds_on_last_invalid_range(self):
        document = "# Alpha\n- registration\n" + "context\n" * 118 + "# Next\n- checkout"
        replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS[:2]]
        sections = [{"checkedRange": {"start": 1, "end": 120}, "issues": []},
                    {"checkedRange": {"start": 120, "end": 122}, "issues": []}]
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in replies + sections)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192,
            section_feature_review=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "SEMANTIC_REVIEW_INVALID")

    def test_eight_sections_are_rejected_before_any_provider_call(self):
        transport = Mock()
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192,
            section_feature_review=True).analyze_recoverable(
                "# Alpha\n" + "x\n" * 840, "doc")
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["error"], "CALL_LIMIT")
        transport.assert_not_called()

    def test_section_review_requires_eight_k_grouped_mode(self):
        for options in ({}, {"grouped_review": True},
                        {"group_review_max_tokens": 8192}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                SourceSelectorSolarAnalyzer("synthetic-key",
                                            section_feature_review=True, **options)

    def test_section_issue_holds_draft_after_all_ranges(self):
        replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS[:2]]
        section = {"checkedRange": {"start": 1, "end": 2}, "issues": [
            {"field": "features", "kind": "overbroad", "targetId": "I0001",
             "sourceLineIds": []}]}
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in replies + [section])])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192,
            section_feature_review=True).analyze_recoverable(
                "# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "SEMANTIC_REJECTED")
        self.assertEqual(transport.call_count, 5)

    def test_seven_sections_use_twelve_calls_after_evidence_repair(self):
        document = "# Alpha\n- registration\n" + "context\n" * 838
        replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS[:2]]
        sections = [{"checkedRange": {"start": start, "end": start + 119},
                     "issues": []} for start in range(1, 841, 120)]
        transport = Mock(side_effect=[
            response(core("BOLD_1")), response(features()),
            response({"project_name": confirmed(1)}),
            *(response(item) for item in replies + sections),
        ])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192,
            section_feature_review=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 12)

    def test_grouped_eight_k_limit_changes_only_review_calls(self):
        group_replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS]
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in group_replies)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192).analyze_recoverable(
                "# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual([call.args[0]["max_tokens"] for call in transport.call_args_list],
                         [4096, 4096, 8192, 8192, 8192])
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer("synthetic-key", group_review_max_tokens=8192)

    def test_grouped_review_completes_only_after_three_valid_groups(self):
        group_replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS]
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in group_replies)])
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 5)
        for group, call in zip(GROUPS, transport.call_args_list[2:]):
            schema = call.args[0]["response_format"]["json_schema"]["schema"]
            self.assertEqual(schema["properties"]["checkedFields"]["items"]["enum"],
                             list(group))

    def test_grouped_issue_holds_draft_without_semantic_repair(self):
        replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS]
        replies[-1]["issues"] = [{"field": "features", "kind": "overbroad",
                                  "targetId": "I0001", "sourceLineIds": []}]
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in replies)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True).analyze_recoverable(
                "# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "SEMANTIC_REJECTED")
        self.assertEqual(transport.call_count, 5)

    def test_grouped_last_response_failure_never_auto_completes(self):
        transport = Mock(side_effect=[
            response(core()), response(features()),
            response({"checkedFields": list(GROUPS[0]), "issues": []}),
            response({"checkedFields": list(GROUPS[1]), "issues": []}),
            response({"checkedFields": [], "issues": []}),
        ])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True).analyze_recoverable(
                "# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "SEMANTIC_REVIEW_INVALID")
        self.assertEqual(transport.call_count, 5)

    def test_grouped_review_uses_sixth_and_last_call_after_evidence_repair(self):
        replies = [{"checkedFields": list(group), "issues": []} for group in GROUPS]
        transport = Mock(side_effect=[
            response(core("BOLD_1")), response(features()),
            response({"project_name": confirmed(1)}),
            *(response(item) for item in replies),
        ])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True).analyze_recoverable(
                "# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 6)

    def test_compact_review_empty_issues_completes_without_full_checked_fields(self):
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response({"issues": []})])
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, compact_review=True)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        review_payload = transport.call_args_list[2].args[0]
        schema = review_payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(schema["required"], ["issues"])
        self.assertEqual(review_payload["max_tokens"], 4096)

    def test_compact_review_low_effort_changes_only_review_request(self):
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response({"issues": []})])
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, compact_review=True,
            compact_review_effort="low")
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_args_list[0].args[0]["reasoning_effort"],
                         transport.call_args_list[1].args[0]["reasoning_effort"])
        self.assertEqual(transport.call_args_list[2].args[0]["reasoning_effort"], "low")
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer("synthetic-key", compact_review_effort="low")

    def test_compact_review_issue_reaches_semantic_repair_with_server_evidence(self):
        issue = {"field": "features", "kind": "overbroad",
                 "targetId": "I0001", "sourceLineIds": []}
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response({"issues": [issue]}),
                                      response(features()), response({"issues": []})])
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, compact_review=True)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        correction = transport.call_args_list[3].args[0]["messages"][1]["content"]
        self.assertIn('"itemIndex": 0', correction)
        self.assertIn('"evidenceLineIds": [2]', correction)

    def test_compact_review_invalid_target_is_not_auto_confirmed(self):
        issue = {"field": "features", "kind": "overbroad",
                 "targetId": "I9999", "sourceLineIds": []}
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response({"issues": [issue]})])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, compact_review=True).analyze_recoverable(
                "# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "SEMANTIC_REVIEW_INVALID")
        self.assertEqual(transport.call_count, 3)

    def test_first_pass_selects_server_owned_spans_without_value(self):
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response(verdict())])
        analyzer = SourceSelectorSolarAnalyzer("synthetic-key", transport=transport)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["project_name"], "Alpha")
        self.assertEqual(result["profile"]["data"]["features"], ["registration"])
        self.assertEqual(transport.call_count, 3)
        for call in transport.call_args_list[:2]:
            payload = call.args[0]
            self.assertIn("[L1] # Alpha", payload["messages"][1]["content"])
            schema = payload["response_format"]["json_schema"]["schema"]
            self.assertNotIn("value", json.dumps(schema))
            self.assertIn("selector", json.dumps(schema))

    def test_invalid_selector_repairs_without_model_value(self):
        transport = Mock(side_effect=[response(core("BOLD_1")), response(features()),
                                      response({"project_name": confirmed(1)}),
                                      response(verdict())])
        analyzer = SourceSelectorSolarAnalyzer("synthetic-key", transport=transport)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 4)
        payload = transport.call_args_list[2].args[0]
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]["required"],
                         ["project_name"])
        self.assertIn("INVALID_SELECTOR", payload["messages"][1]["content"])
        self.assertEqual(analyzer._contract_version(), "source-selector-v1")

    def test_experimental_field_timeout_reaches_provider_call(self):
        transport = Mock(side_effect=[response(core()), response(features()),
                                      response(verdict())])
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, analysis_timeout_seconds=300,
            field_call_timeout_seconds=120, experimental_long_timeout=True)
        original = analyzer._request_fields
        analyzer._request_fields = Mock(wraps=original)
        result = analyzer.analyze_recoverable("# Alpha\n- registration", "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(analyzer._request_fields.call_args_list[0].kwargs["timeout"], 120)
