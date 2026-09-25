import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import cited_to_profile, AnalysisError

class RoleProjectionTests(unittest.TestCase):
    def test_feature_roles_keep_actions_and_exclude_development(self):
        fields = dict.fromkeys(FIELDS)
        fields["features"] = {"spans": [
            {"lineId": 1, "occurrence": 1, "quote": "search", "role": "user_action"},
            {"lineId": 2, "occurrence": 1, "quote": "backup", "role": "operational_action"},
            {"lineId": 3, "occurrence": 1, "quote": "write tests", "role": "development_task"},
            {"lineId": 4, "occurrence": 1, "quote": "server directory", "role": "technical_description"},
        ], "absenceLineIds": []}
        result = cited_to_profile("search\nbackup\nwrite tests\nserver directory", "doc", fields)
        self.assertEqual(result["data"]["features"], ["search", "backup"])
        self.assertEqual(len(result["evidence"]["features"]), 2)

    def test_only_excluded_candidates_means_unknown_not_explicit_none(self):
        fields = dict.fromkeys(FIELDS)
        fields["features"] = {"spans": [
            {"lineId": 1, "occurrence": 1, "quote": "write tests", "role": "development_task"},
        ], "absenceLineIds": []}
        result = cited_to_profile("write tests", "doc", fields)
        self.assertIsNone(result["data"]["features"])
        self.assertEqual(result["evidence"]["features"], [])

    def test_selected_action_still_needs_exact_evidence(self):
        fields = dict.fromkeys(FIELDS)
        fields["features"] = {"spans": [
            {"lineId": 1, "occurrence": 1, "quote": "invented", "role": "user_action"},
        ], "absenceLineIds": []}
        with self.assertRaises(AnalysisError):
            cited_to_profile("search", "doc", fields)

    def test_external_roles_exclude_clients_and_generic_sources(self):
        fields = dict.fromkeys(FIELDS)
        fields["external_integrations"] = {"value": {
            "authentication": [{"name": "Acme", "role": "named_service"}],
            "notifications": [], "storage": [],
            "other": [{"name": "ChatClient", "role": "client"},
                      {"name": "traffic API", "role": "generic_source"}],
        }, "evidenceLineIds": [1], "absenceQuote": None}
        result = cited_to_profile("Acme ChatClient traffic API", "doc", fields)
        self.assertEqual(result["data"]["external_integrations"], ["Acme"])

    def test_no_identified_external_service_is_unknown(self):
        fields = dict.fromkeys(FIELDS)
        fields["external_integrations"] = {"value": {
            "authentication": [], "notifications": [], "storage": [],
            "other": [{"name": "traffic API", "role": "generic_source"}],
        }, "evidenceLineIds": [1], "absenceQuote": None}
        result = cited_to_profile("traffic API", "doc", fields)
        self.assertIsNone(result["data"]["external_integrations"])
        self.assertEqual(result["evidence"]["external_integrations"], [])

    def test_unknown_role_is_rejected(self):
        fields = dict.fromkeys(FIELDS)
        fields["features"] = {"spans": [
            {"lineId": 1, "occurrence": 1, "quote": "search", "role": "unrecognized"},
        ], "absenceLineIds": []}
        with self.assertRaises(AnalysisError):
            cited_to_profile("search", "doc", fields)


class ExplicitEvidenceTests(unittest.TestCase):
    def test_explicit_occurrence_selects_repeated_quote(self):
        fields = dict.fromkeys(FIELDS)
        fields["features"] = {"spans": [
            {"lineId": 1, "role": "user_action", "quote": "backup", "occurrence": 2},
        ], "absenceLineIds": []}
        result = cited_to_profile("backup then backup", "doc", fields)
        self.assertEqual(result["evidence"]["features"][0]["start"], 12)

    def test_invalid_occurrence_is_rejected(self):
        for occurrence in (0, 3, True):
            fields = dict.fromkeys(FIELDS)
            fields["features"] = {"spans": [
                {"lineId": 1, "role": "user_action", "quote": "backup", "occurrence": occurrence},
            ], "absenceLineIds": []}
            with self.subTest(occurrence=occurrence), self.assertRaises(AnalysisError):
                cited_to_profile("backup then backup", "doc", fields)

    def test_empty_candidates_without_absence_quote_mean_unknown(self):
        fields = dict.fromkeys(FIELDS)
        fields["external_integrations"] = {"value": {
            "authentication": [], "notifications": [], "storage": [], "other": [],
        }, "evidenceLineIds": [1], "absenceQuote": None}
        result = cited_to_profile("traffic provider undecided", "doc", fields)
        self.assertIsNone(result["data"]["external_integrations"])

    def test_explicit_absence_requires_literal_quote(self):
        fields = dict.fromkeys(FIELDS)
        fields["external_integrations"] = {"value": {
            "authentication": [], "notifications": [], "storage": [], "other": [],
        }, "evidenceLineIds": [1], "absenceQuote": "No external integrations"}
        result = cited_to_profile("No external integrations", "doc", fields)
        self.assertEqual(result["data"]["external_integrations"], [])
        fields["external_integrations"]["absenceQuote"] = "invented"
        with self.assertRaises(AnalysisError):
            cited_to_profile("No external integrations", "doc", fields)
