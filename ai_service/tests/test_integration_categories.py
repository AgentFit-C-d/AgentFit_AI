import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError, cited_to_profile, output_schema

CATEGORIES = ("authentication", "notifications", "storage", "other")

class IntegrationCategoriesTests(unittest.TestCase):
    def fields(self, value):
        fields = dict.fromkeys(FIELDS)
        fields["external_integrations"] = {"value": value, "evidenceLineIds": [1], "absenceQuote": None}
        return fields

    def groups(self, **values):
        return {name: [{"name": item, "role": "named_service"} for item in values.get(name, [])]
                if type(values.get(name, [])) is list else values[name] for name in CATEGORIES}

    def test_categories_merge_deduplicate_and_preserve_public_array(self):
        result = cited_to_profile("Google Discord Cloud Storage", "doc-1",
            self.fields(self.groups(authentication=["Google", "Discord"],
                                    storage=["Cloud Storage"], other=["Google"])))
        self.assertEqual(result["data"]["external_integrations"],
                         ["Google", "Discord", "Cloud Storage"])

    def test_schema_requires_all_categories(self):
        value = output_schema(1)["properties"]["external_integrations"]["anyOf"][1]["properties"]["value"]
        self.assertEqual(value["type"], "object")
        self.assertEqual(value["required"], list(CATEGORIES))
        self.assertFalse(value["additionalProperties"])

    def test_malformed_categories_are_rejected(self):
        cases = [[], {}, self.groups(storage="Storage"), self.groups(storage=[1]),
                 self.groups(storage=[" "]), self.groups(storage=["x"*201]),
                 self.groups(storage=["x"]*31), dict(self.groups(), extra=[])]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(AnalysisError):
                cited_to_profile("Storage", "doc-1", self.fields(value))

    def test_unsupported_service_is_rejected_after_merge(self):
        with self.assertRaises(AnalysisError):
            cited_to_profile("Google", "doc-1", self.fields(self.groups(storage=["Invented"])))

    def test_empty_and_unknown_remain_distinct(self):
        fields = self.fields(self.groups())
        fields["external_integrations"]["absenceQuote"] = "No external integrations."
        empty = cited_to_profile("No external integrations.", "doc-1", fields)
        unknown = cited_to_profile("Undecided.", "doc-1", dict.fromkeys(FIELDS))
        self.assertEqual(empty["data"]["external_integrations"], [])
        self.assertTrue(empty["evidence"]["external_integrations"])
        self.assertIsNone(unknown["data"]["external_integrations"])

    def test_total_limit_is_checked_after_merging(self):
        values = [str(i) for i in range(31)]
        with self.assertRaises(AnalysisError):
            cited_to_profile(" ".join(values), "doc-1",
                self.fields(self.groups(authentication=values[:20], storage=values[20:])))
