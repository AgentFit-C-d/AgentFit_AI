import copy
import json
import unittest
from pathlib import Path

from agentfit_ai.profile import ProfileValidationError, validate_profile


FIXTURES = Path(__file__).resolve().parents[2] / "specs" / "ai-developer" / "02-evaluation-fixtures" / "starter-cases.json"


def candidate_from_case(case):
    document = case["document"]
    evidence = {field: [] for field in case["expected"]}
    for field, quotes in case["evidenceQuotes"].items():
        for quote in quotes:
            start = document.index(quote)
            evidence[field].append({"start": start, "end": start + len(quote)})
    return {"data": copy.deepcopy(case["expected"]), "evidence": evidence}


class ProfileValidationTests(unittest.TestCase):
    def test_starter_cases_have_valid_structure_and_evidence(self):
        cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 3)
        for case in cases:
            with self.subTest(case=case["id"]):
                result = validate_profile(case["document"], case["id"], candidate_from_case(case))
                self.assertEqual(result["data"], case["expected"])
                self.assertEqual(
                    result["unknownFields"],
                    [field for field, value in case["expected"].items() if value is None],
                )
                for field, value in case["expected"].items():
                    self.assertEqual(result["sources"][field], "UNKNOWN" if value is None else "DOCUMENT")

    def test_missing_profile_field_is_rejected(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        del candidate["data"]["database"]
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "INVALID_PROFILE_SHAPE")

    def test_wrong_type_and_blank_string_are_rejected(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        for bad_value in (42, "   "):
            with self.subTest(bad_value=bad_value):
                candidate = candidate_from_case(case)
                candidate["data"]["project_name"] = bad_value
                with self.assertRaises(ProfileValidationError) as caught:
                    validate_profile(case["document"], case["id"], candidate)
                self.assertEqual(caught.exception.code, "INVALID_PROFILE_VALUE")

    def test_empty_array_is_known_and_requires_evidence(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        candidate["data"]["external_integrations"] = []
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "MISSING_EVIDENCE")

        candidate["evidence"]["external_integrations"] = candidate["evidence"]["backend"]
        result = validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(result["sources"]["external_integrations"], "DOCUMENT")
        self.assertNotIn("external_integrations", result["unknownFields"])

    def test_string_and_array_limits(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        candidate["data"]["backend"] = ["Spring Boot"] * 30
        self.assertEqual(len(validate_profile(case["document"], case["id"], candidate)["data"]["backend"]), 30)

        candidate = candidate_from_case(case)
        candidate["data"]["project_name"] = "x" * 201
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "INVALID_PROFILE_VALUE")

        candidate = candidate_from_case(case)
        for field in candidate["data"]:
            candidate["data"][field] = None
            candidate["evidence"][field] = []
        candidate["data"]["project_name"] = "x" * 200
        candidate["evidence"]["project_name"] = [{"start": 0, "end": 200}]
        self.assertEqual(
            validate_profile("x" * 200, case["id"], candidate)["data"]["project_name"],
            "x" * 200,
        )

        candidate = candidate_from_case(case)
        candidate["data"]["backend"] = ["Spring Boot"] * 31
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "INVALID_PROFILE_VALUE")

    def test_known_value_requires_evidence(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        candidate["evidence"]["backend"] = []
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "MISSING_EVIDENCE")

    def test_value_must_appear_in_its_evidence_span(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        candidate["evidence"]["backend"] = candidate["evidence"]["frontend"]
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "EVIDENCE_MISMATCH")

    def test_unknown_value_cannot_keep_evidence(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        candidate["evidence"]["database"] = copy.deepcopy(candidate["evidence"]["backend"])
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "UNKNOWN_HAS_EVIDENCE")

    def test_out_of_range_evidence_is_rejected_without_document_in_error(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        candidate["evidence"]["backend"] = [{"start": 0, "end": len(case["document"]) + 1}]
        with self.assertRaises(ProfileValidationError) as caught:
            validate_profile(case["document"], case["id"], candidate)
        self.assertEqual(caught.exception.code, "INVALID_EVIDENCE_RANGE")
        self.assertNotIn(case["document"], str(caught.exception))

    def test_unicode_positions_count_code_points(self):
        case = json.loads(FIXTURES.read_text(encoding="utf-8"))[0]
        candidate = candidate_from_case(case)
        document = "😀" + case["document"]
        for spans in candidate["evidence"].values():
            for span in spans:
                span["start"] += 1
                span["end"] += 1
        result = validate_profile(document, case["id"], candidate)
        self.assertEqual(result["evidence"]["backend"][0]["start"], document.index("Spring Boot"))


if __name__ == "__main__":
    unittest.main()
