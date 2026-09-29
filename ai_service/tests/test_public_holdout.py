import hashlib
import unittest

from agentfit_ai.public_holdout import load_manifest, score_profile, verify_document
from agentfit_ai.public_holdout_evaluation import evaluate_case, summarize


class PublicHoldoutTests(unittest.TestCase):
    def test_frozen_manifest_has_three_distinct_sources(self):
        cases = load_manifest()
        self.assertEqual([case["id"] for case in cases],
                         ["actual-product", "mealie-readme", "immich-readme"])

    def setUp(self):
        self.document = "# Acme\nVue powers the frontend.\nUsers can import recipes.\n"
        self.case = {
            "id": "public-acme",
            "repo": "example/acme",
            "commit": "a" * 40,
            "path": "README.md",
            "sha256": hashlib.sha256(self.document.encode()).hexdigest(),
            "checks": {
                "project_name": [{"aliases": ["Acme"], "quote": "# Acme"}],
                "frontend": [{"aliases": ["Vue"], "quote": "Vue powers the frontend"}],
                "features": [{"aliases": ["import recipes", "recipe imports"],
                              "quote": "Users can import recipes"}],
            },
        }

    def test_document_hash_and_quotes_must_match_before_scoring(self):
        self.assertEqual(verify_document(self.case, self.document.encode()), self.document)
        with self.assertRaises(ValueError):
            verify_document(self.case, self.document.replace("Vue", "React").encode())
        bad = {**self.case, "checks": {"frontend": [
            {"aliases": ["Vue"], "quote": "React powers the frontend"}]}}
        with self.assertRaises(ValueError):
            verify_document(bad, self.document.encode())

    def test_unsupported_url_and_oversized_document_are_rejected(self):
        bad = {**self.case, "repo": "../private"}
        with self.assertRaises(ValueError):
            verify_document(bad, self.document.encode())
        with self.assertRaises(ValueError):
            verify_document(self.case, b"x" * 100001)

    def test_partial_score_separates_value_evidence_and_unassessed_fields(self):
        document = verify_document(self.case, self.document.encode())
        data = {field: None for field in (
            "project_name", "project_type", "domain", "frontend", "backend",
            "ai", "database", "deployment", "features", "external_integrations")}
        data.update(project_name="Acme", frontend=["Vue"],
                    features=["import recipes", "shopping list"])
        evidence = {field: [] for field in data}
        evidence["project_name"] = [self.span(document, "# Acme")]
        evidence["frontend"] = [self.span(document, "Vue powers the frontend")]
        evidence["features"] = [self.span(document, "Users can import recipes")]
        result = score_profile(self.case, document, {"data": data, "evidence": evidence})
        self.assertEqual(result["matched_checks"], 3)
        self.assertEqual(result["wrong_evidence_checks"], 0)
        self.assertEqual(result["unassessed_values"], 1)

    def test_wrong_evidence_is_distinct_from_missing_alias(self):
        document = verify_document(self.case, self.document.encode())
        data = {field: None for field in (
            "project_name", "project_type", "domain", "frontend", "backend",
            "ai", "database", "deployment", "features", "external_integrations")}
        data.update(project_name="Acme", frontend=["Vue"], features=["recipe imports"])
        evidence = {field: [] for field in data}
        evidence["project_name"] = [self.span(document, "# Acme")]
        evidence["frontend"] = [self.span(document, "# Acme")]
        evidence["features"] = [self.span(document, "Users can import recipes")]
        result = score_profile(self.case, document, {"data": data, "evidence": evidence})
        self.assertEqual(result["matched_checks"], 2)
        self.assertEqual(result["wrong_evidence_checks"], 1)
        self.assertEqual(result["missing_alias_checks"], 0)

    def test_evaluation_retains_counts_without_profile_or_source(self):
        document = verify_document(self.case, self.document.encode())
        data = {field: None for field in (
            "project_name", "project_type", "domain", "frontend", "backend",
            "ai", "database", "deployment", "features", "external_integrations")}
        data["project_name"] = "Acme"
        evidence = {field: [] for field in data}
        evidence["project_name"] = [self.span(document, "# Acme")]

        class FakeAnalyzer:
            def analyze_recoverable(self, text, case_id):
                assert text == document and case_id == "public-acme"
                return {"outcome": "needs_confirmation", "error": "PROVIDER_TIMEOUT",
                        "profile": {"data": data, "evidence": evidence},
                        "fieldStates": {}, "questions": []}

        row = evaluate_case(self.case, document, FakeAnalyzer())
        self.assertEqual(row["matched_checks"], 1)
        self.assertEqual(row["missing_alias_checks"], 2)
        self.assertNotIn("profile", row)
        self.assertNotIn("document", row)
        summary = summarize([row], planned=3)
        self.assertEqual(summary["needs_confirmation_cases"], 1)
        self.assertFalse(summary["release_gate_passed"])

    @staticmethod
    def span(document, quote):
        start = document.index(quote)
        return {"documentId": "public-acme", "start": start, "end": start + len(quote)}


if __name__ == "__main__":
    unittest.main()
