import unittest
import json

from agentfit_ai.section_feature_review import (
    split_feature_sections, validate_section_coverage,
    section_review_payload, normalize_section_review, merge_section_issues)
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.semantic_review import ReviewValidationError


DOCUMENT = "# Alpha\n## Features\n- registration\n## Other\n- checkout"


def profile():
    data = dict.fromkeys(FIELDS)
    data["features"] = ["registration", "checkout"]
    evidence = {field: [] for field in FIELDS}
    evidence["features"] = [
        {"start": DOCUMENT.index(value), "end": DOCUMENT.index(value) + len(value)}
        for value in data["features"]]
    return validate_profile(DOCUMENT, "doc", {"data": data, "evidence": evidence})


class SectionSplitTests(unittest.TestCase):
    def test_headings_and_blank_lines_cover_every_line_once(self):
        document = "intro\r\n# A\r\nitem\r\n\r\n## B\r\nlast"
        chunks = split_feature_sections(document, max_lines=3)
        self.assertEqual(chunks, ((1, 1), (2, 4), (5, 6)))
        validate_section_coverage(chunks, 6)

    def test_unheaded_840_and_841_lines_cross_seven_chunk_boundary(self):
        for count, expected in ((840, 7), (841, 8)):
            chunks = split_feature_sections("x\n" * count)
            self.assertEqual(len(chunks), expected)
            self.assertEqual(chunks[0], (1, 120))
            self.assertEqual(chunks[-1][1], count)
            validate_section_coverage(chunks, count)

    def test_long_heading_section_splits_without_gap(self):
        chunks = split_feature_sections("# A\n" + "x\n" * 240)
        self.assertEqual(chunks, ((1, 120), (121, 240), (241, 241)))

    def test_coverage_validator_rejects_gaps_overlap_and_large_chunks(self):
        for chunks, count in (
            (((1, 2), (4, 4)), 4),
            (((1, 2), (2, 4)), 4),
            (((1, 121),), 121),
        ):
            with self.subTest(chunks=chunks), self.assertRaises(ValueError):
                validate_section_coverage(chunks, count)


class SectionReviewContractTests(unittest.TestCase):
    def test_payload_sends_only_local_feature_and_readonly_heading_context(self):
        payload = section_review_payload(DOCUMENT, profile(), (3, 3),
                                         model="solar-pro4", effort="medium")
        content = payload["messages"][1]["content"]
        self.assertIn("[L3] - registration", content)
        self.assertIn("[L1] # Alpha", content)
        self.assertIn("[L2] ## Features", content)
        self.assertNotIn("[L5] - checkout", content)
        draft = json.loads(content.split("Draft to review (untrusted data):\n", 1)[1])
        self.assertEqual(draft["data"]["features"], ["registration"])
        self.assertEqual(draft["itemIds"]["features"], ["I0001"])
        self.assertEqual(payload["max_tokens"], 8192)
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]), {"checkedRange", "issues"})
        self.assertEqual(schema["properties"]["issues"]["items"]["properties"]
                         ["sourceLineIds"]["items"]["minimum"], 3)

    def test_existing_issue_is_normalized_only_for_local_target(self):
        reply = {"checkedRange": {"start": 3, "end": 3}, "issues": [
            {"field": "features", "kind": "overbroad", "targetId": "I0001",
             "sourceLineIds": []}]}
        actual = normalize_section_review(reply, profile(), DOCUMENT, (3, 3))
        self.assertEqual(actual["issues"][0]["itemIndex"], 0)
        self.assertEqual(actual["issues"][0]["evidenceLineIds"], [3])

    def test_outside_range_and_other_feature_are_rejected(self):
        base = {"checkedRange": {"start": 3, "end": 3}, "issues": []}
        bad_replies = [
            {**base, "checkedRange": {"start": 2, "end": 3}},
            {**base, "issues": [{"field": "features", "kind": "missing",
                                  "targetId": None, "sourceLineIds": [5]}]},
            {**base, "issues": [{"field": "features", "kind": "overbroad",
                                  "targetId": "I0002", "sourceLineIds": []}]},
            {**base, "checkedRange": {"start": True, "end": 3}},
            {**base, "issues": [{"field": "features", "kind": "overbroad",
                                  "targetId": [], "sourceLineIds": []}]},
            {**base, "issues": [{"field": "features", "kind": "missing",
                                  "targetId": None, "sourceLineIds": [3]}] * 2},
        ]
        for reply in bad_replies:
            with self.subTest(reply=reply), self.assertRaises(ReviewValidationError):
                normalize_section_review(reply, profile(), DOCUMENT, (3, 3))

    def test_merge_repeated_target_or_conflicting_kinds(self):
        issue = {"field": "features", "kind": "overbroad", "itemIndex": 0,
                 "evidenceLineIds": [3]}
        self.assertEqual(merge_section_issues([[issue], [issue]]), [issue])
        with self.assertRaises(ReviewValidationError):
            merge_section_issues([[issue], [{**issue, "kind": "wrong_role"}]])

    def test_item_is_not_owned_by_another_items_longer_evidence(self):
        document = "- checkout\n- checkout settings"
        data = dict.fromkeys(FIELDS)
        data["features"] = ["checkout", "checkout settings"]
        evidence = {field: [] for field in FIELDS}
        evidence["features"] = [
            {"start": document.index("checkout"),
             "end": document.index("checkout") + len("checkout")},
            {"start": document.index("checkout settings"),
             "end": document.index("checkout settings") + len("checkout settings")},
        ]
        candidate = validate_profile(document, "doc", {"data": data,
                                                       "evidence": evidence})
        payload = section_review_payload(document, candidate, (2, 2),
                                         model="solar-pro4", effort="medium")
        content = payload["messages"][1]["content"]
        draft = json.loads(content.split("Draft to review (untrusted data):\n", 1)[1])
        self.assertEqual(draft["itemIds"]["features"], ["I0002"])
        reply = {"checkedRange": {"start": 2, "end": 2}, "issues": [
            {"field": "features", "kind": "unsupported", "targetId": "I0001",
             "sourceLineIds": []}]}
        with self.assertRaises(ReviewValidationError):
            normalize_section_review(reply, candidate, document, (2, 2))


if __name__ == "__main__":
    unittest.main()
