import unittest

from agentfit_ai.evidence import EvidenceError
from agentfit_ai.section_feature_extraction import (
    section_extraction_payload, normalize_section_features,
    merge_section_features)


def confirmed(*lines):
    return {"features": {"state": "confirmed", "items": [
        {"lineId": line, "selector": "BODY", "role": "user_action"}
        for line in lines]}}


class SectionFeatureExtractionTests(unittest.TestCase):
    def test_payload_limits_selector_ids_to_local_lines(self):
        payload = section_extraction_payload("# Alpha\n- checkout\n# Next", (2, 2),
                                             model="solar-pro4")
        content = payload["messages"][1]["content"]
        self.assertIn("[L2] - checkout", content)
        self.assertIn("[L1] # Alpha", content)
        self.assertNotIn("[L3] # Next", content)
        self.assertEqual(payload["max_tokens"], 4096)
        schema = payload["response_format"]["json_schema"]["schema"]
        variants = schema["properties"]["features"]["anyOf"]
        line_id = variants[1]["properties"]["items"]["items"]["properties"]["lineId"]
        self.assertEqual(line_id, {"type": "integer", "minimum": 2, "maximum": 2})
        self.assertEqual(variants[2]["properties"]["lineId"], line_id)

    def test_outside_line_and_heading_context_are_rejected(self):
        document = "# Alpha\n- checkout"
        for reply in (confirmed(1), confirmed(3),
                      {"features": {"state": "absent", "lineId": 1}}):
            with self.subTest(reply=reply), self.assertRaises(EvidenceError):
                normalize_section_features(document, (2, 2), reply)

    def test_exact_duplicate_merges_but_substring_feature_remains(self):
        document = "- checkout\n- checkout settings\n- checkout"
        chunks = ((1, 1), (2, 2), (3, 3))
        replies = [confirmed(1), confirmed(2), confirmed(3)]
        result = merge_section_features(document, chunks, replies)
        self.assertEqual([item["lineId"] for item in result["items"]], [1, 2])

    def test_confirmed_and_absent_conflict_or_thirty_one_values_fail(self):
        with self.assertRaises(EvidenceError):
            merge_section_features("- checkout\n- no features", ((1, 1), (2, 2)),
                                   [confirmed(1), {"features": {"state": "absent",
                                                                "lineId": 2}}])
        document = "\n".join(f"- feature {number}" for number in range(1, 32))
        with self.assertRaises(EvidenceError):
            merge_section_features(document, ((1, 30), (31, 31)),
                                   [confirmed(*range(1, 31)), confirmed(31)])

    def test_merge_rejects_uncovered_source_line(self):
        with self.assertRaises(EvidenceError):
            merge_section_features("- checkout\n- missing\n- settings",
                                   ((1, 1), (3, 3)), [confirmed(1), confirmed(3)])


if __name__ == "__main__":
    unittest.main()
