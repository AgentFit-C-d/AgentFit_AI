import json
from pathlib import Path
import unittest

from agentfit_ai.document_grounding_rules import evaluate_cases, guard_candidate


CASES_PATH = (Path(__file__).resolve().parents[2] /
              "specs/ai-developer/04-analysis-provider/document-grounding-evaluation/adversarial-cases.json")
TARGETS = {"r1": "MallowDB", "r2": "WillowAI", "r3": "CedarPay",
           "n1": "실시간 알림", "n2": "AmberAI", "n3": "외부 저장소 연동",
           "p1": "팀 채팅", "p2": "경로 추천", "p3": "파일 공유"}


class DocumentGroundingRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]

    def test_gold_has_nine_pairs_and_exact_codepoint_spans(self):
        self.assertEqual(len(self.cases), 18)
        pairs = {}
        for case in self.cases:
            pairs.setdefault(case["pair"], []).append(case)
            span = case["candidate"]
            self.assertEqual(case["document"][span["start"]:span["end"]],
                             TARGETS[case["pair"]])
        self.assertEqual(len(pairs), 9)
        self.assertTrue(all(len(group) == 2 for group in pairs.values()))
        self.assertEqual({category: sum(c["category"] == category for c in self.cases)
                          for category in ("repeat", "negation", "proposal")},
                         {"repeat": 6, "negation": 6, "proposal": 6})

    def test_guard_distinguishes_repeated_negative_and_proposed_mentions(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(guard_candidate(case["document"], **case["candidate"]),
                                 case["expected_decision"])

    def test_guard_rejects_bad_offsets_and_states(self):
        with self.assertRaises(ValueError):
            guard_candidate("ABC", field="ai", state="present", start=3, end=4)
        with self.assertRaises(ValueError):
            guard_candidate("ABC", field="ai", state="maybe", start=0, end=1)

    def test_conflicting_confirmed_mentions_are_held_for_review(self):
        document = ("운영 AI는 WillowAI를 사용한다. "
                    "운영 AI는 WillowAI를 사용하지 않기로 확정했다.")
        first = document.index("WillowAI")
        self.assertEqual(guard_candidate(document, field="ai", state="present",
                                         start=first, end=first + len("WillowAI")),
                         "review")

    def test_evaluation_counts_false_confirmations_and_omissions_without_sources(self):
        baseline = evaluate_cases(self.cases, {case["id"]: "allow"
                                               for case in self.cases})
        self.assertEqual(baseline["false_auto_confirmations"], 9)
        self.assertEqual(baseline["missed_allows"], 0)
        guarded = evaluate_cases(self.cases, {case["id"]: guard_candidate(
            case["document"], **case["candidate"]) for case in self.cases})
        self.assertEqual(guarded["false_auto_confirmations"], 0)
        self.assertEqual(guarded["missed_allows"], 0)
        self.assertEqual(guarded["total"], 18)
        serialized = json.dumps(guarded, ensure_ascii=False)
        for case in self.cases:
            self.assertNotIn(case["document"], serialized)
        with self.assertRaises(ValueError):
            evaluate_cases(self.cases, {})


if __name__ == "__main__":
    unittest.main()
