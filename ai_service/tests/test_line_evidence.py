import unittest

from agentfit_ai.evidence import EvidenceError
from agentfit_ai.line_evidence import line_schema, line_to_profile
from agentfit_ai.profile import FIELDS


def candidate(field, value):
    return dict(dict.fromkeys(FIELDS), **{field: value})


def fact(value, line_id, role="product_fact"):
    return {"value": value, "lineId": line_id, "role": role}


def confirmed(*items):
    return {"state": "confirmed", "items": list(items)}


class LineEvidenceTests(unittest.TestCase):
    def test_unique_value_uses_original_unicode_crlf_offsets(self):
        document = "😀\r\n# Alpha\r\nbackend: Go\n"
        fields = dict.fromkeys(FIELDS)
        fields["project_name"] = confirmed(fact("Alpha", 2))
        fields["backend"] = confirmed(fact("Go", 3))
        profile = line_to_profile(document, "doc", fields)
        for field, value in (("project_name", "Alpha"), ("backend", "Go")):
            span = profile["evidence"][field][0]
            self.assertEqual((span["start"], span["end"]),
                             (document.index(value), document.index(value) + len(value)))
            self.assertEqual(profile["data"][field],
                             [value] if field == "backend" else value)

    def test_repeated_value_within_selected_line_is_not_guessed(self):
        with self.assertRaises(EvidenceError) as caught:
            line_to_profile("Go and Go", "doc", candidate("backend", confirmed(fact("Go", 1))))
        self.assertEqual(caught.exception.reason, "AMBIGUOUS_VALUE_IN_LINE")
        self.assertEqual(caught.exception.field, "backend")
        self.assertEqual(caught.exception.index, 0)
        self.assertEqual(caught.exception.match_count, 2)

    def test_value_must_occur_in_selected_line_exactly(self):
        with self.assertRaises(EvidenceError) as caught:
            line_to_profile("Go\nPython", "doc", candidate("backend", confirmed(fact("Go", 2))))
        self.assertEqual(caught.exception.reason, "VALUE_NOT_IN_LINE")
        self.assertEqual(caught.exception.field, "backend")

    def test_invalid_line_role_state_and_duplicate_fail_closed(self):
        invalid = (
            confirmed(fact("Go", 0)),
            confirmed(fact("Go", 2)),
            confirmed(fact("Go", 1, role="user_action")),
            confirmed(fact("Go", 1), fact("Go", 1)),
            {"state": "confirmed", "items": []},
            {"state": "unknown", "items": [fact("Go", 1)]},
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(EvidenceError):
                line_to_profile("Go", "doc", candidate("backend", value))

    def test_absence_remains_distinct_from_unknown(self):
        profile = line_to_profile("외부 연동 없음", "doc", candidate(
            "external_integrations", {"state": "absent", "lineId": 1}))
        self.assertEqual(profile["data"]["external_integrations"], [])
        self.assertIsNone(profile["data"]["backend"])
        self.assertEqual(profile["evidence"]["external_integrations"][0]["start"], 0)
        with self.assertRaises(EvidenceError):
            line_to_profile("없음", "doc", candidate("database", {"state": "absent", "lineId": 1}))

    def test_schema_bounds_line_ids_to_actual_document(self):
        schema = line_schema(3)
        item = schema["properties"]["backend"]["anyOf"][1]["properties"]["items"]["items"]
        self.assertEqual(item["properties"]["lineId"]["maximum"], 3)
        with self.assertRaises(ValueError):
            line_schema(0)
