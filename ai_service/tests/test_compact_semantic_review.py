import unittest

from agentfit_ai.compact_review import (
    compact_review_schema, item_ids, normalize_compact_review, review_payload,
)
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.semantic_review import ReviewValidationError


def profile_for(document, data, evidence):
    return validate_profile(document, "doc", {
        "data": {**dict.fromkeys(FIELDS), **data},
        "evidence": {**{field: [] for field in FIELDS}, **evidence},
    })


class CompactReviewTests(unittest.TestCase):
    def setUp(self):
        self.document = "Alpha 기능이다.\nBeta 기능이다.\nGamma가 없다."
        alpha = self.document.index("Alpha")
        beta = self.document.index("Beta")
        gamma = self.document.index("Gamma")
        self.profile = profile_for(self.document,
            {"features": ["Alpha", "Beta"], "external_integrations": []},
            {"features": [{"start": alpha, "end": alpha + 5}, {"start": beta, "end": beta + 4}],
             "external_integrations": [{"start": gamma, "end": len(self.document)}]})

    def test_existing_issue_uses_item_id_and_server_evidence_lines(self):
        ids = item_ids(self.profile)
        self.assertEqual(len(ids["features"]), 2)
        response = {"issues": [{"field": "features", "kind": "wrong_role",
                                "targetId": ids["features"][1], "sourceLineIds": []}]}
        issues = normalize_compact_review(response, self.profile, self.document)
        self.assertEqual(issues, [{"field": "features", "kind": "wrong_role",
                                   "itemIndex": 1, "evidenceLineIds": [2]}])

    def test_missing_requires_model_selected_source_line(self):
        response = {"issues": [{"field": "ai", "kind": "missing",
                                "targetId": None, "sourceLineIds": [3]}]}
        self.assertEqual(normalize_compact_review(response, self.profile, self.document)[0]["evidenceLineIds"], [3])
        for refs in ([], [0], [4], [True]):
            response["issues"][0]["sourceLineIds"] = refs
            with self.subTest(refs=refs), self.assertRaises(ReviewValidationError):
                normalize_compact_review(response, self.profile, self.document)

    def test_reject_wrong_field_target_and_model_supplied_existing_lines(self):
        ids = item_ids(self.profile)
        invalid = [
            {"field": "external_integrations", "kind": "wrong_role", "targetId": ids["features"][0], "sourceLineIds": []},
            {"field": "features", "kind": "wrong_role", "targetId": "I9999", "sourceLineIds": []},
            {"field": "features", "kind": "wrong_role", "targetId": ids["features"][0], "sourceLineIds": [1]},
            {"field": "features", "kind": "missing", "targetId": ids["features"][0], "sourceLineIds": [1]},
        ]
        for issue in invalid:
            with self.subTest(issue=issue), self.assertRaises(ReviewValidationError):
                normalize_compact_review({"issues": [issue]}, self.profile, self.document)

    def test_duplicate_target_is_rejected(self):
        target = item_ids(self.profile)["features"][0]
        response = {"issues": [
            {"field": "features", "kind": "wrong_role", "targetId": target, "sourceLineIds": []},
            {"field": "features", "kind": "duplicate", "targetId": target, "sourceLineIds": []},
        ]}
        with self.assertRaises(ReviewValidationError) as caught:
            normalize_compact_review(response, self.profile, self.document)
        self.assertEqual(caught.exception.reason, "DUPLICATE_TARGET")

    def test_long_valid_evidence_is_bounded_to_source_anchor(self):
        document = "X\n" * 31
        profile = profile_for(document, {"project_name": "X"},
                              {"project_name": [{"start": 0, "end": len(document)}]})
        issue = {"field": "project_name", "kind": "wrong_scope",
                 "targetId": None, "sourceLineIds": []}
        result = normalize_compact_review({"issues": [issue]}, profile, document)
        self.assertEqual(result[0]["evidenceLineIds"], [1])
        self.assertTrue(review_payload(document, profile, model="solar-pro4", effort="medium")
                        ["messages"][1]["content"])

    def test_scalar_and_absent_evidence_is_calculated(self):
        response = {"issues": [{"field": "external_integrations", "kind": "uncertainty",
                                "targetId": None, "sourceLineIds": []}]}
        issue = normalize_compact_review(response, self.profile, self.document)[0]
        self.assertEqual(issue["itemIndex"], None)
        self.assertEqual(issue["evidenceLineIds"], [3])

    def test_schema_and_payload_are_compact_and_source_is_not_mutated(self):
        schema = compact_review_schema(self.profile, len(self.document.splitlines()))
        self.assertEqual(set(schema["properties"]), {"issues"})
        payload = review_payload(self.document, self.profile, model="solar-pro4", effort="medium")
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertIn("I0002", payload["messages"][1]["content"])
        self.assertNotIn("checkedFields", str(schema))
