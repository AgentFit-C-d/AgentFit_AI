import json
import unittest

from agentfit_ai.grouped_review import GROUPS, group_review_payload, normalize_group_review
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.semantic_review import ReviewValidationError


DOCUMENT = "# Alpha\n- registration"


def profile():
    data = dict.fromkeys(FIELDS)
    data["project_name"] = "Alpha"
    data["features"] = ["registration"]
    evidence = {field: [] for field in FIELDS}
    evidence["project_name"] = [{"start": 2, "end": 7}]
    evidence["features"] = [{"start": 10, "end": 22}]
    return validate_profile(DOCUMENT, "doc", {"data": data, "evidence": evidence})


class GroupedReviewTests(unittest.TestCase):
    def test_groups_cover_each_public_field_once(self):
        self.assertEqual(len(GROUPS), 3)
        self.assertEqual([len(group) for group in GROUPS], [5, 4, 1])
        self.assertEqual(sorted(field for group in GROUPS for field in group),
                         sorted(FIELDS))

    def test_payload_restricts_checked_and_issue_fields(self):
        payload = group_review_payload(DOCUMENT, profile(), GROUPS[2],
                                       model="solar-pro4", effort="medium")
        schema = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(set(schema["properties"]), {"checkedFields", "issues"})
        self.assertEqual(schema["properties"]["checkedFields"]["items"]["enum"],
                         ["features"])
        self.assertEqual(schema["properties"]["issues"]["items"]["anyOf"][0]
                         ["properties"]["field"]["enum"], ["features"])
        self.assertEqual(payload["max_tokens"], 4096)
        draft = json.loads(payload["messages"][1]["content"].split(
            "Draft to review (untrusted data):\n", 1)[1])
        self.assertEqual(set(draft["data"]), {"features"})
        self.assertEqual(set(draft["itemIds"]), {"features"})
        self.assertEqual(set(draft["evidenceLines"]), {"features"})
        prompt = payload["messages"][0]["content"]
        self.assertIn('"checkedFields"', prompt)
        self.assertNotIn('출력은 {"issues"', prompt)
        self.assertNotIn("10개 필드를 모두 검토", prompt)

    def test_schema_restricts_target_ids_by_field(self):
        identity = group_review_payload(DOCUMENT, profile(), GROUPS[0],
                                        model="solar-pro4", effort="medium")
        variants = identity["response_format"]["json_schema"]["schema"]["properties"]
        variants = variants["issues"]["items"]["anyOf"]
        scalar = next(item for item in variants
                      if item["properties"]["field"]["enum"] == ["project_name"])
        self.assertEqual(scalar["properties"]["targetId"], {"type": "null"})
        feature = group_review_payload(DOCUMENT, profile(), GROUPS[2],
                                       model="solar-pro4", effort="medium")
        variants = feature["response_format"]["json_schema"]["schema"]["properties"]
        variants = variants["issues"]["items"]["anyOf"]
        self.assertEqual(variants[0]["properties"]["targetId"]["anyOf"][1]["enum"],
                         ["I0001"])

    def test_optional_output_limit_is_eight_k_only(self):
        payload = group_review_payload(DOCUMENT, profile(), GROUPS[0],
                                       model="solar-pro4", effort="medium",
                                       max_tokens=8192)
        self.assertEqual(payload["max_tokens"], 8192)
        for invalid in (0, 8193, "8192", True):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                group_review_payload(DOCUMENT, profile(), GROUPS[0],
                                     model="solar-pro4", effort="medium",
                                     max_tokens=invalid)

    def test_existing_and_missing_issues_are_server_normalized(self):
        reply = {"checkedFields": ["features"], "issues": [
            {"field": "features", "kind": "overbroad", "targetId": "I0001",
             "sourceLineIds": []},
            {"field": "features", "kind": "missing", "targetId": None,
             "sourceLineIds": [2]},
        ]}
        normalized = normalize_group_review(reply, profile(), DOCUMENT, GROUPS[2])
        self.assertEqual(normalized["checkedFields"], ["features"])
        self.assertEqual(normalized["issues"][0]["itemIndex"], 0)
        self.assertEqual(normalized["issues"][0]["evidenceLineIds"], [2])
        self.assertEqual(normalized["issues"][1]["itemIndex"], None)

    def test_invalid_checked_fields_and_out_of_group_issue_fail(self):
        for checked in ([], ["features", "features"], ["project_name"]):
            with self.subTest(checked=checked), self.assertRaises(ReviewValidationError):
                normalize_group_review({"checkedFields": checked, "issues": []},
                                       profile(), DOCUMENT, GROUPS[2])
        with self.assertRaises(ReviewValidationError):
            normalize_group_review({"checkedFields": ["features"], "issues": [
                {"field": "project_name", "kind": "unsupported", "targetId": None,
                 "sourceLineIds": []}]}, profile(), DOCUMENT, GROUPS[2])

    def test_invalid_target_duplicate_and_missing_without_line_fail(self):
        for issues in (
            [{"field": "features", "kind": "overbroad", "targetId": "I9999",
              "sourceLineIds": []}],
            [{"field": "features", "kind": "overbroad", "targetId": "I0001",
              "sourceLineIds": []}] * 2,
            [{"field": "features", "kind": "missing", "targetId": None,
              "sourceLineIds": []}],
        ):
            with self.subTest(issues=issues), self.assertRaises(ReviewValidationError):
                normalize_group_review({"checkedFields": ["features"], "issues": issues},
                                       profile(), DOCUMENT, GROUPS[2])
