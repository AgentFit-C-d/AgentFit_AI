import json
import unittest
from inspect import signature
from unittest.mock import Mock

from agentfit_ai.profile import FIELDS
from agentfit_ai.grouped_review import GROUPS
from agentfit_ai import grouped_review
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
    def test_fine_review_uses_smaller_review_ranges_without_changing_extraction(self):
        self.assertIn("fine_feature_review", signature(SourceSelectorSolarAnalyzer).parameters)
        document = "# Alpha\n- registration\n" + "context\n" * 118
        groups = [{"checkedFields": list(group), "issues": []}
                  for group in grouped_review.FIELDWISE_GROUPS[:-1]]
        ranges = ((1, 50), (51, 100), (101, 120))
        sections = [{"checkedRange": {"start": start, "end": end}, "issues": []}
                    for start, end in ranges]
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in groups + sections)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True, section_feature_curation=True,
            fieldwise_review=True, fine_feature_review=True).analyze_recoverable(
                document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 10)
        extraction = transport.call_args_list[1].args[0]
        line_rule = extraction["response_format"]["json_schema"]["schema"]
        line_rule = line_rule["properties"]["features"]["anyOf"][1]
        line_rule = line_rule["properties"]["items"]["items"]["properties"]["lineId"]
        self.assertEqual((line_rule["minimum"], line_rule["maximum"]), (1, 120))
        for (start, end), call in zip(ranges, transport.call_args_list[7:]):
            schema = call.args[0]["response_format"]["json_schema"]["schema"]
            checked = schema["properties"]["checkedRange"]["properties"]
            self.assertEqual(checked["start"]["enum"], [start])
            self.assertEqual(checked["end"]["enum"], [end])

    def test_fine_review_rejects_twenty_two_ranges_before_provider_calls(self):
        self.assertIn("fine_feature_review", signature(SourceSelectorSolarAnalyzer).parameters)
        document = "".join(f"# Section {number}\n" + "context\n" * 29
                           for number in range(22))
        transport = Mock()
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True, section_feature_curation=True,
            fieldwise_review=True, fine_feature_review=True).analyze_recoverable(
                document, "doc")
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["error"], "CALL_LIMIT")
        transport.assert_not_called()

    def test_fine_review_allows_only_explicit_twenty_four_hundred_second_window(self):
        self.assertIn("fine_feature_review", signature(SourceSelectorSolarAnalyzer).parameters)
        options = {"grouped_review": True, "group_review_max_tokens": 8192,
                   "section_feature_review": True, "section_feature_extraction": True,
                   "section_feature_curation": True, "fieldwise_review": True,
                   "fine_feature_review": True, "experimental_long_timeout": True}
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", analysis_timeout_seconds=2400, **options)
        self.assertEqual(analyzer._analysis_timeout_seconds, 2400)
        self.assertEqual(analyzer._max_provider_calls(), 36)
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer(
                "synthetic-key", analysis_timeout_seconds=2401, **options)
        options["fine_feature_review"] = False
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer(
                "synthetic-key", analysis_timeout_seconds=2400, **options)

    def test_fine_review_last_range_failure_cannot_complete(self):
        self.assertIn("fine_feature_review", signature(SourceSelectorSolarAnalyzer).parameters)
        document = "# Alpha\n- registration\n" + "context\n" * 118
        groups = [{"checkedFields": list(group), "issues": []}
                  for group in grouped_review.FIELDWISE_GROUPS[:-1]]
        sections = [{"checkedRange": {"start": start, "end": end}, "issues": []}
                    for start, end in ((1, 50), (51, 100))]
        sections.append({"checkedRange": {"start": 101, "end": 119}, "issues": []})
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in groups + sections)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True, section_feature_curation=True,
            fieldwise_review=True, fine_feature_review=True).analyze_recoverable(
                document, "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "SEMANTIC_REVIEW_INVALID")

    def test_fieldwise_review_requires_curation_and_reserves_twenty_two_calls(self):
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer("synthetic-key", fieldwise_review=True)
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", grouped_review=True, group_review_max_tokens=8192,
            section_feature_review=True, section_feature_extraction=True,
            section_feature_curation=True, fieldwise_review=True)
        self.assertEqual(analyzer._max_provider_calls(), 22)

    def test_fieldwise_review_completes_after_each_core_field_and_feature_section(self):
        document = "# Alpha\n- registration"
        self.assertTrue(hasattr(grouped_review, "FIELDWISE_GROUPS"))
        groups = grouped_review.FIELDWISE_GROUPS[:-1]
        replies = [{"checkedFields": list(group), "issues": []} for group in groups]
        section = {"checkedRange": {"start": 1, "end": 2}, "issues": []}
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in replies + [section])])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True, section_feature_curation=True,
            fieldwise_review=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 8)
        for group, call in zip(groups, transport.call_args_list[2:7]):
            schema = call.args[0]["response_format"]["json_schema"]["schema"]
            self.assertEqual(schema["properties"]["checkedFields"]["items"]["enum"],
                             list(group))

    def test_fieldwise_review_holds_on_last_core_field_or_feature_section(self):
        document = "# Alpha\n- registration"
        self.assertTrue(hasattr(grouped_review, "FIELDWISE_GROUPS"))
        groups = grouped_review.FIELDWISE_GROUPS[:-1]
        valid = [{"checkedFields": list(group), "issues": []} for group in groups]
        section = {"checkedRange": {"start": 1, "end": 2}, "issues": []}
        for replies in (valid[:-1] + [{"checkedFields": [], "issues": []}],
                        valid + [{"checkedRange": {"start": 1, "end": 1},
                                  "issues": []}]):
            with self.subTest(replies=replies):
                transport = Mock(side_effect=[response(core()), response(features()),
                                              *(response(item) for item in replies),
                                              response(section)])
                result = SourceSelectorSolarAnalyzer(
                    "synthetic-key", transport=transport, grouped_review=True,
                    group_review_max_tokens=8192, section_feature_review=True,
                    section_feature_extraction=True, section_feature_curation=True,
                    fieldwise_review=True).analyze_recoverable(document, "doc")
                self.assertEqual(result["outcome"], "needs_confirmation")

    def test_fieldwise_review_collects_early_issue_before_final_hold(self):
        document = "# Alpha\n- registration"
        groups = grouped_review.FIELDWISE_GROUPS[:-1]
        replies = [{"checkedFields": list(group), "issues": []} for group in groups]
        replies[0]["issues"] = [{"field": "project_name", "kind": "unsupported",
                                  "targetId": None, "sourceLineIds": []}]
        section = {"checkedRange": {"start": 1, "end": 2}, "issues": []}
        transport = Mock(side_effect=[response(core()), response(features()),
                                      *(response(item) for item in replies + [section])])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True, section_feature_curation=True,
            fieldwise_review=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "needs_confirmation")
        self.assertEqual(result["error"], "SEMANTIC_REJECTED")
        self.assertEqual(transport.call_count, 8)

    def test_fieldwise_review_can_use_last_reserved_call_for_seventh_section(self):
        document = ("# Alpha\n" +
                    "".join(f"- feature {number}\n" for number in range(1, 31)) +
                    "context\n" * 89 + "# Next\n- feature 31\n" +
                    "context\n" * 718)
        first = {"features": {"state": "confirmed", "items": [
            {"lineId": line, "selector": "BODY", "role": "user_action"}
            for line in range(2, 32)]}}
        feature_chunks = [first,
                          {"features": confirmed(122, role="user_action")},
                          *({"features": None} for _ in range(5))]
        groups = [{"checkedFields": list(group), "issues": []}
                  for group in grouped_review.FIELDWISE_GROUPS[:-1]]
        sections = [{"checkedRange": {"start": start, "end": start + 119},
                     "issues": []} for start in range(1, 841, 120)]
        transport = Mock(side_effect=[
            response(core("BOLD_1")),
            *(response(item) for item in feature_chunks),
            response({"selectedIds": ["F0001", "F0031"]}),
            response({"project_name": confirmed(1)}),
            *(response(item) for item in groups + sections)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True, section_feature_curation=True,
            fieldwise_review=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 22)

    def test_section_curation_requires_extraction_and_has_nineteen_call_cap(self):
        with self.assertRaises(ValueError):
            SourceSelectorSolarAnalyzer("synthetic-key", grouped_review=True,
                                        group_review_max_tokens=8192,
                                        section_feature_review=True,
                                        section_feature_curation=True)
        analyzer = SourceSelectorSolarAnalyzer(
            "synthetic-key", grouped_review=True, group_review_max_tokens=8192,
            section_feature_review=True, section_feature_extraction=True,
            section_feature_curation=True)
        self.assertEqual(analyzer._max_provider_calls(), 19)

    def test_section_curation_selects_overflow_ids_before_review(self):
        document = ("# Alpha\n" +
                    "".join(f"- feature {number}\n" for number in range(1, 31)) +
                    "context\n" * 89 + "# Next\n- feature 31")
        first = {"features": {"state": "confirmed", "items": [
            {"lineId": line, "selector": "BODY", "role": "user_action"}
            for line in range(2, 32)]}}
        groups = [{"checkedFields": list(group), "issues": []} for group in GROUPS[:2]]
        sections = [{"checkedRange": {"start": start, "end": end}, "issues": []}
                    for start, end in ((1, 120), (121, 122))]
        transport = Mock(side_effect=[
            response(core()), response(first),
            response({"features": confirmed(122, role="user_action")}),
            response({"selectedIds": ["F0031", "F0001"]}),
            *(response(item) for item in groups + sections)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True,
            section_feature_curation=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(result["profile"]["data"]["features"],
                         ["feature 1", "feature 31"])
        self.assertEqual(transport.call_count, 8)

    def test_section_curation_rejects_unknown_id_without_profile(self):
        document = ("# Alpha\n" +
                    "".join(f"- feature {number}\n" for number in range(1, 31)) +
                    "context\n" * 89 + "# Next\n- feature 31")
        first = {"features": {"state": "confirmed", "items": [
            {"lineId": line, "selector": "BODY", "role": "user_action"}
            for line in range(2, 32)]}}
        transport = Mock(side_effect=[
            response(core()), response(first),
            response({"features": confirmed(122, role="user_action")}),
            response({"selectedIds": ["F9999"]})])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True,
            section_feature_curation=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "failed")
        self.assertEqual(result["error"], "INVALID_EVIDENCE")
        self.assertEqual(transport.call_count, 4)

    def test_section_curation_skips_extra_call_for_thirty_or_fewer(self):
        document = "# Alpha\n- registration\n" + "context\n" * 118 + "# Next\n- checkout"
        groups = [{"checkedFields": list(group), "issues": []} for group in GROUPS[:2]]
        sections = [{"checkedRange": {"start": start, "end": end}, "issues": []}
                    for start, end in ((1, 120), (121, 122))]
        transport = Mock(side_effect=[
            response(core()), response(features()),
            response({"features": confirmed(122, role="user_action")}),
            *(response(item) for item in groups + sections)])
        result = SourceSelectorSolarAnalyzer(
            "synthetic-key", transport=transport, grouped_review=True,
            group_review_max_tokens=8192, section_feature_review=True,
            section_feature_extraction=True,
            section_feature_curation=True).analyze_recoverable(document, "doc")
        self.assertEqual(result["outcome"], "complete")
        self.assertEqual(transport.call_count, 7)

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
