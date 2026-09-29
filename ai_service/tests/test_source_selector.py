import unittest

from agentfit_ai.evidence import EvidenceError
from agentfit_ai.profile import FIELDS
from agentfit_ai.source_selector import selector_schema, selector_to_profile, source_span


def candidate(field, value):
    return dict(dict.fromkeys(FIELDS), **{field: value})


def confirmed(line_id, selector, role="product_fact"):
    return {"state": "confirmed", "items": [
        {"lineId": line_id, "selector": selector, "role": role}]}


class SourceSelectorTests(unittest.TestCase):
    def test_source_spans_are_exact_in_crlf_unicode_markdown(self):
        document = "😀\r\n# Cedar — App\r\n- [ ] **재고 알림** 전송\n| DB | **`node:sqlite`** |\n"
        cases = ((2, "BEFORE_DASH", "Cedar"),
                 (3, "BOLD_1", "재고 알림"),
                 (4, "CODE_1", "node:sqlite"),
                 (4, "CELL_2", "**`node:sqlite`**"))
        for line_id, selector, value in cases:
            with self.subTest(selector=selector):
                actual, span = source_span(document, line_id, selector)
                self.assertEqual(actual, value)
                self.assertEqual(document[span["start"]:span["end"]], value)

    def test_body_and_rhs_selectors_keep_exact_source(self):
        document = "- [ ] 제품별 목표 가격 설정\n* **프레임워크:** Next.js, Vercel\n"
        cases = ((1, "BODY", "제품별 목표 가격 설정"),
                 (2, "AFTER_COLON", "Next.js, Vercel"))
        for line_id, selector, value in cases:
            actual, span = source_span(document, line_id, selector)
            self.assertEqual(actual, value)
            self.assertEqual(document[span["start"]:span["end"]], value)

    def test_missing_selector_and_empty_table_cell_fail_closed(self):
        for document, selector in (("plain", "BOLD_1"),
                                   ("| A || B |", "CELL_2"),
                                   ("x" * 201, "BODY")):
            with self.subTest(selector=selector), self.assertRaises(EvidenceError):
                source_span(document, 1, selector)
        with self.assertRaises(EvidenceError):
            source_span("Go", 2, "BODY")

    def test_projection_uses_selected_occurrence_without_model_value(self):
        document = "Go and Go\n"
        profile = selector_to_profile(document, "doc", candidate(
            "backend", confirmed(1, "BODY")))
        self.assertEqual(profile["data"]["backend"], ["Go and Go"])
        self.assertEqual(profile["evidence"]["backend"][0]["start"], 0)
        self.assertEqual(profile["evidence"]["backend"][0]["end"], 9)

    def test_wrong_role_and_invalid_selector_report_field_and_index(self):
        for entry, reason in ((confirmed(1, "BODY", "user_action"), "WRONG_ROLE"),
                              (confirmed(1, "CELL_1"), "INVALID_SELECTOR")):
            with self.subTest(entry=entry), self.assertRaises(EvidenceError) as caught:
                selector_to_profile("Go", "doc", candidate("backend", entry))
            self.assertEqual((caught.exception.reason, caught.exception.field,
                              caught.exception.index), (reason, "backend", 0))

    def test_schema_contains_no_model_generated_value(self):
        item = selector_schema(3)["properties"]["backend"]["anyOf"][1]["properties"]["items"]["items"]
        self.assertEqual(set(item["properties"]), {"lineId", "selector", "role"})
        self.assertEqual(item["properties"]["lineId"]["maximum"], 3)
