import unittest

from agentfit_ai.repair_context_options import build_repair_context_options


class RepairContextOptionsTests(unittest.TestCase):
    @staticmethod
    def candidate(quote="Atlas"):
        return {"project_name": {"state": "confirmed", "items": [
            {"value": "Atlas", "quote": quote, "context": None, "role": "product_fact"}]}}

    @staticmethod
    def errors(reason="AMBIGUOUS_QUOTE"):
        return [{"field": "project_name", "code": "INVALID_EVIDENCE",
                 "detail": {"reason": reason, "itemIndex": 0}}]

    def test_repeated_name_has_distinct_exact_context_options(self):
        document = "이번 Atlas는 일정 앱이다.\r\n비교 제품 Atlas는 게임이다.\r\n"
        options = build_repair_context_options(document, self.errors(), self.candidate())
        self.assertEqual(options["project_name"]["itemIndex"], 0)
        pairs = options["project_name"]["options"]
        self.assertEqual(len(pairs), 2)
        self.assertEqual([pair["quote"] for pair in pairs], ["Atlas", "Atlas"])
        self.assertEqual(len({pair["context"] for pair in pairs}), 2)
        for pair in pairs:
            self.assertEqual(document.count(pair["context"]), 1)
            self.assertEqual(pair["context"].count("Atlas"), 1)
        self.assertIn("이번", pairs[0]["context"])
        self.assertIn("비교", pairs[1]["context"])

    def test_unresolvable_or_non_location_error_has_no_options(self):
        examples = [
            ("다른 이름", self.errors(), self.candidate()),
            (" ".join(["Atlas"] * 9), self.errors(), self.candidate()),
            ("Atlas\nAtlas\n", self.errors(), self.candidate()),
            ("이번 Atlas와 비교 Atlas", self.errors("VALUE_NOT_IN_QUOTE"),
             self.candidate()),
        ]
        for document, errors, previous in examples:
            with self.subTest(document=document, reason=errors[0]["detail"]["reason"]):
                self.assertEqual(build_repair_context_options(document, errors, previous), {})

    def test_bad_item_index_and_absent_candidate_are_ignored(self):
        errors = self.errors()
        errors[0]["detail"]["itemIndex"] = 1
        self.assertEqual(build_repair_context_options("Atlas here", errors,
                                                       self.candidate()), {})
        self.assertEqual(build_repair_context_options("Atlas here", self.errors(),
                                                       {"project_name": None}), {})


if __name__ == "__main__":
    unittest.main()
