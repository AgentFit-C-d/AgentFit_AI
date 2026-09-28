import unittest

from agentfit_ai.keyed_profile_evaluation import load_profile_cases
from agentfit_ai.profile import FIELDS

try:
    from agentfit_ai.false_complete_scoring import diagnose_case, load_gold_evidence
except ImportError:
    diagnose_case = load_gold_evidence = None


def profile(features):
    data = {field: None for field in FIELDS}
    data["features"] = features
    sources = {field: None for field in FIELDS}
    sources["features"] = "DOCUMENT"
    evidence = {field: [] for field in FIELDS}
    return {"data": data, "sources": sources, "evidence": evidence}


def observation(candidates, judgment, final=None, reviews=None):
    profiles = [("judgment", judgment)]
    if final is not None:
        profiles.append(("semantic_repair", final))
    return {"candidates": candidates, "profiles": profiles,
            "reviews": reviews if reviews is not None else [("semantic_review", [])]}


class FalseCompleteScoringTests(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "Q-001", "kind": "full", "document": "장소 확인 후보 선택",
                     "gold": {"features": [["장소 확인"], ["후보 선택"]]}}
        self.correct = profile(["장소 확인", "후보 선택"])
        self.wrong = profile(["장소 확인"])
        self.gold = {"Q-001": {"features": [(0, 5), (6, 11)]}}
        self.both = [{"id": "F0001", "start": 0, "end": 5},
                     {"id": "F0002", "start": 6, "end": 11}]

    def test_missing_annotated_support_is_candidate_gap(self):
        self.assertIsNotNone(diagnose_case)
        trace = observation(self.both[:1], self.wrong)
        rows = diagnose_case(self.case, {"outcome": "complete", "profile": self.wrong},
                             trace, self.gold)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["field"], "features")
        self.assertEqual(rows[0]["first_observed_divergence"], "candidate_gap")
        self.assertEqual(rows[0]["review_detected"], False)
        self.assertEqual(rows[0]["candidate_ids"], ["F0001"])
        self.assertNotIn("장소 확인", str(rows))

    def test_wrong_first_judgment_and_empty_review(self):
        self.assertIsNotNone(diagnose_case)
        rows = diagnose_case(self.case, {"outcome": "complete", "profile": self.wrong},
                             observation(self.both, self.wrong), self.gold)
        self.assertEqual(rows[0]["first_observed_divergence"], "judgment_mismatch")
        self.assertEqual(rows[0]["review_detected"], False)

    def test_repair_regression_uses_recheck_issue(self):
        self.assertIsNotNone(diagnose_case)
        reviews = [("semantic_review", [{"field": "ai", "kind": "missing"}]),
                   ("semantic_recheck", [{"field": "features", "kind": "overbroad"}])]
        rows = diagnose_case(self.case, {"outcome": "complete", "profile": self.wrong},
                             observation(self.both, self.correct, self.wrong, reviews),
                             self.gold)
        self.assertEqual(rows[0]["first_observed_divergence"], "repair_regression")
        self.assertEqual(rows[0]["review_detected"], True)

    def test_unannotated_and_unreviewed_are_not_guessed(self):
        self.assertIsNotNone(diagnose_case)
        rows = diagnose_case(self.case, {"outcome": "complete", "profile": self.wrong},
                             observation(self.both, self.wrong, reviews=[]), {})
        self.assertEqual(rows[0]["first_observed_divergence"], "undetermined")
        self.assertIsNone(rows[0]["review_detected"])
        self.assertEqual(diagnose_case(self.case,
            {"outcome": "needs_confirmation", "profile": self.wrong},
            observation(self.both, self.wrong), self.gold), [])

    def test_checked_in_annotations_resolve_unique_synthetic_spans(self):
        self.assertIsNotNone(load_gold_evidence)
        cases, _ = load_profile_cases()
        gold = load_gold_evidence(cases)
        self.assertEqual(len(gold["Q-001"]["features"]), 2)
        self.assertEqual(len(gold["N-004"]["ai"]), 1)
        q = next(case for case in cases if case["id"] == "Q-001")
        start, end = gold["Q-001"]["features"][0]
        self.assertEqual(q["document"][start:end], "장소 확인")
        altered = [dict(case, document=case["document"] + " 장소 확인")
                   if case["id"] == "Q-001" else case for case in cases]
        with self.assertRaises(ValueError):
            load_gold_evidence(altered)

    def test_focus_forbidden_in_multiple_fields_is_unattributed(self):
        self.assertIsNotNone(diagnose_case)
        focus = {"id": "E99", "kind": "focus", "document": "Bad",
                 "gold": [], "forbidden": ["Bad"]}
        final = profile(["Bad"])
        final["data"]["project_name"] = "Bad"
        trace = observation([{"id": "F0001", "start": 0, "end": 3}], final)
        rows = diagnose_case(focus, {"outcome": "complete", "profile": final},
                             trace, {})
        self.assertEqual(rows, [{"field": None,
                                 "first_observed_divergence": "undetermined",
                                 "review_detected": None,
                                 "candidate_ids": [], "evidence_spans": []}])


if __name__ == "__main__":
    unittest.main()
