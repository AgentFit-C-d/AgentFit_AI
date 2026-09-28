import unittest

from agentfit_ai.anchored_candidates import units, validate_quotes
from agentfit_ai.recoverable_judgment import salvage_judgment


def candidates(document, quotes):
    unit = units(document)[0]
    return validate_quotes({"units": [{"unitId": unit.id, "quotes": quotes}]}, [unit], 0)


def selected(field, role="product_fact", status="confirmed"):
    return {"field": field, "role": role, "status": status,
            "scope": "current", "decision": "selected"}


class RecoverableJudgmentTests(unittest.TestCase):
    def test_invalid_selection_does_not_discard_independent_field(self):
        document = "Atlas uses Solar."
        pool = candidates(document, ["Atlas", "Solar"])
        reply = {"decisions": {"F0001": selected("project_name"),
                               "F0002": selected("ai", "operating_model", "tentative")}}
        profile, unresolved = salvage_judgment(document, "doc", pool, reply)
        self.assertEqual(profile["data"]["project_name"], "Atlas")
        self.assertEqual(profile["evidence"]["project_name"][0]["start"], 0)
        self.assertIsNone(profile["data"]["ai"])
        self.assertEqual(unresolved, {"ai": "JUDGMENT_INVALID"})

    def test_conflict_and_wrong_role_are_isolated(self):
        document = "Atlas Beta Solar"
        pool = candidates(document, ["Atlas", "Beta", "Solar"])
        reply = {"decisions": {"F0001": selected("project_name"),
                               "F0002": selected("project_name"),
                               "F0003": selected("ai", "client")}}
        profile, unresolved = salvage_judgment(document, "doc", pool, reply)
        self.assertIsNone(profile)
        self.assertEqual(unresolved, {"project_name": "JUDGMENT_INVALID",
                                      "ai": "JUDGMENT_INVALID"})

    def test_explicit_absence_survives_unrelated_failure(self):
        document = "외부 연동은 없다. Atlas"
        pool = candidates(document, ["외부 연동은 없다.", "Atlas"])
        reply = {"decisions": {"F0001": selected("external_integrations", "named_service", "absent"),
                               "F0002": selected("project_name", status="tentative")}}
        profile, unresolved = salvage_judgment(document, "doc", pool, reply)
        self.assertEqual(profile["data"]["external_integrations"], [])
        self.assertEqual(profile["sources"]["external_integrations"], "DOCUMENT")
        self.assertEqual(unresolved, {"project_name": "JUDGMENT_INVALID"})

    def test_malformed_decision_keys_or_ids_fail_whole_salvage(self):
        document = "Atlas Solar"
        pool = candidates(document, ["Atlas", "Solar"])
        bad = [
            {"decisions": {"F0001": selected("project_name")}},
            {"decisions": {"F0001": selected("project_name"), "F9999": selected("ai", "operating_model")}},
            {"decisions": {"F0001": {**selected("project_name"), "extra": "x"},
                           "F0002": selected("ai", "operating_model")}},
        ]
        for reply in bad:
            with self.subTest(reply=reply):
                profile, _ = salvage_judgment(document, "doc", pool, reply)
                self.assertIsNone(profile)

    def test_invalid_source_span_and_all_fields_failed_return_none(self):
        document = "Atlas Solar"
        pool = candidates(document, ["Atlas", "Solar"])
        pool[0]["span"] = {"start": 6, "end": 11}
        reply = {"decisions": {"F0001": selected("project_name"),
                               "F0002": selected("ai", "operating_model", "tentative")}}
        profile, unresolved = salvage_judgment(document, "doc", pool, reply)
        self.assertIsNone(profile)
        self.assertEqual(unresolved, {"project_name": "JUDGMENT_INVALID",
                                      "ai": "JUDGMENT_INVALID"})


if __name__ == "__main__":
    unittest.main()
