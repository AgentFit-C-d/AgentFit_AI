import unittest

class ClassificationEvaluationTests(unittest.TestCase):
    def test_required_values_do_not_hide_extra_forbidden_items(self):
        from agentfit_ai.classification_eval import mismatches
        case = {"exact": {}, "contains": {"features": ["backup"]},
                "forbidden": {"features": ["tests/"]}}
        self.assertEqual(mismatches({"features": ["backup", "tests/ folder"]}, case),
                         ["features:forbidden:tests/"])

    def test_unknown_is_not_explicitly_empty(self):
        from agentfit_ai.classification_eval import mismatches
        self.assertEqual(mismatches({"ai": []}, {"exact": {"ai": None}}), ["ai"])

    def test_array_order_is_irrelevant_but_extra_values_fail(self):
        from agentfit_ai.classification_eval import mismatches
        case = {"exact": {"backend": ["Python", "Falcon"]}}
        self.assertEqual(mismatches({"backend": ["Falcon", "Python"]}, case), [])
        self.assertEqual(mismatches({"backend": ["Falcon", "Python", "Fly.io"]}, case), ["backend"])
