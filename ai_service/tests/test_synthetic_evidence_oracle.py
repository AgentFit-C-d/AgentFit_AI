import json
import tempfile
import unittest
from pathlib import Path

from agentfit_ai.keyed_profile_evaluation import load_profile_cases
from agentfit_ai.profile import FIELDS, validate_profile
from agentfit_ai.synthetic_evidence_oracle import assess_profile, load_oracle


def candidate(case, values, quotes):
    document = case["document"]
    data = dict.fromkeys(FIELDS)
    evidence = {field: [] for field in FIELDS}
    for field, value in values.items():
        data[field] = value
        evidence[field] = [{"start": document.index(quote),
                            "end": document.index(quote) + len(quote)}
                           for quote in quotes[field]]
    return validate_profile(document, case["id"],
                            {"data": data, "evidence": evidence})


class SyntheticEvidenceOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, _ = load_profile_cases()
        cls.by_id = {case["id"]: case for case in cls.cases}
        cls.oracle = load_oracle(cls.cases)

    def test_oracle_covers_every_frozen_case(self):
        self.assertEqual(set(self.oracle), set(self.by_id))

    def test_oracle_rejects_quote_outside_source(self):
        from agentfit_ai.synthetic_evidence_oracle import ORACLE_PATH
        source = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
        source["cases"]["Q-001"]["evidence"]["features"][0] = "not-in-source"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "oracle.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_oracle(self.cases, path)

    def test_repeated_member_approval_without_roles_is_a_wrong_value(self):
        case = self.by_id["Q-002"]
        profile = candidate(case, {"features": ["회원 승인", "회원 승인"]},
                            {"features": ["회원 승인", "회원 승인"]})
        score = assess_profile(case, profile, self.oracle)
        self.assertEqual(score["wrong_value_fields"], 1)

    def test_short_quote_without_product_context_is_insufficient_evidence(self):
        case = self.by_id["E02"]
        profile = candidate(case, {"project_type": "CLI"},
                            {"project_type": ["CLI"]})
        score = assess_profile(case, profile, self.oracle)
        self.assertEqual(score["wrong_value_fields"], 0)
        self.assertEqual(score["wrong_evidence_fields"], 1)

    def test_historical_technology_is_a_wrong_suggestion(self):
        case = self.by_id["E01"]
        profile = candidate(case, {"backend": ["Spring Boot"]},
                            {"backend": ["Spring Boot"]})
        score = assess_profile(case, profile, self.oracle)
        self.assertEqual(score["wrong_value_fields"], 1)
        self.assertEqual(score["unassessed_suggested_fields"], 0)

    def test_unannotated_focus_field_stays_unassessed(self):
        case = self.by_id["E01"]
        profile = candidate(case, {"project_type": "서비스"},
                            {"project_type": ["서비스"]})
        score = assess_profile(case, profile, self.oracle)
        self.assertEqual(score["unassessed_suggested_fields"], 1)


if __name__ == "__main__":
    unittest.main()
