import unittest
import json
from unittest.mock import patch

from agentfit_ai.embedding_section_evaluation import (
    QUERY_TEXTS, load_cases, cosine, rank_sections, recall_at_k,
    validate_embedding_reply, gold_spans,
    candidate_recall,
)


class EmbeddingSectionEvaluationTests(unittest.TestCase):
    def test_new_cases_have_exact_unambiguous_gold_locations(self):
        cases, _ = load_cases()
        self.assertEqual(len(cases), 8)
        self.assertEqual(len(QUERY_TEXTS), 10)
        for case in cases:
            self.assertEqual(len(case["sections"]), 6)
            spans = gold_spans(case)
            self.assertEqual(len(spans), len(case["gold"]))
            for gold, span in zip(case["gold"], spans):
                self.assertEqual(case["document"][span[0]:span[1]], gold["quote"])

    def test_ranking_and_recall_do_not_use_gold_to_choose_sections(self):
        queries = [[1.0, 0.0], [0.0, 1.0]]
        passages = [[1.0, 0.0], [0.8, 0.2], [0.0, -1.0]]
        self.assertEqual(rank_sections(queries, passages, 2), [0, 1])
        self.assertEqual(recall_at_k([0, 2], [0, 1]), (1, 2))
        self.assertAlmostEqual(cosine([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_embedding_reply_rejects_missing_nonfinite_and_reordered_vectors(self):
        valid = {"model": "nvidia/nemotron-3-embed-1b", "data": [
            {"index": 0, "embedding": [1.0, 0.0]},
            {"index": 1, "embedding": [0.0, 1.0]},
        ]}
        self.assertEqual(validate_embedding_reply(valid, 2, dimension=2), [[1.0, 0.0], [0.0, 1.0]])
        for changed in [
            {**valid, "model": "other/model"},
            {**valid, "data": valid["data"][:1]},
            {**valid, "data": list(reversed(valid["data"]))},
            {**valid, "data": [{"index": 0, "embedding": [float("nan"), 0.0]}, valid["data"][1]]},
        ]:
            with self.assertRaises(ValueError):
                validate_embedding_reply(changed, 2, dimension=2)

    def test_candidate_recall_counts_exact_spans_and_discards_partial_invalid_batch(self):
        case = load_cases()[0][0]
        quotes = {"U0001": ["물결 노트"], "U0003": ["Ktor"],
                  "U0005": ["달빛 2"], "U0006": ["파도ID"]}
        class FakeAnalyzer:
            def __init__(self, *args, **kwargs):
                self.calls = 0
            def _send_payload(self, payload, names, **kwargs):
                self.calls += 1
                content = json.loads(payload["messages"][1]["content"])
                return {"units": [{"unitId": unit["unitId"],
                                    "quotes": quotes.get(unit["unitId"], [])}
                                   for unit in content["units"]]}, "solar-pro4", 1, 1
        with patch("agentfit_ai.embedding_section_evaluation.SolarAnalyzer", FakeAnalyzer):
            result = candidate_recall(case, "dummy")
        self.assertEqual((result["matched"], result["total"], result["calls"]), (4, 4, 2))
        quotes["U0005"] = ["not in source"]
        with patch("agentfit_ai.embedding_section_evaluation.SolarAnalyzer", FakeAnalyzer):
            result = candidate_recall(case, "dummy")
        self.assertEqual((result["matched"], result["error"], result["calls"]),
                         (0, "ANCHORED_CANDIDATE", 2))
        quotes["U0001"] = ["not in source"]
        with patch("agentfit_ai.embedding_section_evaluation.SolarAnalyzer", FakeAnalyzer):
            result = candidate_recall(case, "dummy")
        self.assertEqual((result["matched"], result["error"], result["calls"]),
                         (0, "ANCHORED_CANDIDATE", 1))


if __name__ == "__main__":
    unittest.main()
