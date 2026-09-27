import unittest

from agentfit_ai.anchored_candidates import units
from agentfit_ai.sections import batch_sections
from agentfit_ai.embedding_section_evaluation import load_cases
from agentfit_ai.candidate_occurrences import candidate_views
from agentfit_ai.solar import AnalysisError
from agentfit_ai.candidate_unit_contract import (
    keyed_candidate_schema, KEYED_CANDIDATE_PROMPT, normalize_keyed_candidates,
)


class CandidateUnitContractTests(unittest.TestCase):
    def assert_candidate_error(self, replies, batches, source_units, reason):
        with self.assertRaises(AnalysisError) as caught:
            normalize_keyed_candidates(replies, batches, source_units)
        self.assertEqual(caught.exception.code, "ANCHORED_CANDIDATE")
        self.assertEqual(caught.exception.candidate_detail, {"reason": reason})

    def test_keyed_schema_requires_every_batch_unit_once(self):
        case = load_cases()[0][0]
        batch = batch_sections(units(case["document"]))[1]
        schema = keyed_candidate_schema(batch)
        groups = schema["properties"]["units"]
        self.assertEqual(set(groups["properties"]), {"U0004", "U0005", "U0006"})
        self.assertEqual(groups["required"], ["U0004", "U0005", "U0006"])
        self.assertIs(groups["additionalProperties"], False)
        quote_list = groups["properties"]["U0004"]
        self.assertEqual(quote_list["maxItems"], 30)
        self.assertEqual(quote_list["items"], {"type": "string", "minLength": 1, "maxLength": 2000})

    def test_keyed_prompt_requests_id_properties_instead_of_array_groups(self):
        self.assertIn('{"units":{"U0001":', KEYED_CANDIDATE_PROMPT)
        self.assertNotIn('{"units":[', KEYED_CANDIDATE_PROMPT)
        self.assertIn("previous/next/제목 문맥에서 가져오지 않는다", KEYED_CANDIDATE_PROMPT)

    def test_missing_and_extra_keys_are_rejected(self):
        source = units("Alpha")
        for reply in ({"units": {}}, {"units": {"U0001": ["Alpha"], "U9999": []}}):
            self.assert_candidate_error([reply], [source], source, "missing_or_extra_unit")

    def test_wrong_unit_quote_moves_to_unique_source_and_deduplicates(self):
        case = next(case for case in load_cases()[0] if case["id"] == "E03")
        source = units(case["document"])
        batches = batch_sections(source)
        replies = [
            {"units": {"U0001": [], "U0002": ["도서 예약 서비스"], "U0003": ["Fly.io"]}},
            {"units": {"U0004": ["Fly.io"], "U0005": ["좌석을 예약하고"], "U0006": []}},
        ]
        pool, metrics = normalize_keyed_candidates(replies, batches, source)
        self.assertEqual(metrics, {"remapped": 1, "deduplicated": 1})
        self.assertEqual([(item["unitId"], item["quote"]) for item in pool],
                         [("U0002", "도서 예약 서비스"), ("U0004", "Fly.io"),
                          ("U0005", "좌석을 예약하고")])
        self.assertEqual([item["id"] for item in pool], ["F0001", "F0002", "F0003"])
        for item in pool:
            self.assertEqual(case["document"][item["span"]["start"]:item["span"]["end"]], item["quote"])
        focused = candidate_views(pool, source, focus=True)
        self.assertEqual(focused[1]["focus"]["selected"], "Fly.io")

    def test_ambiguous_wrong_unit_quote_is_rejected(self):
        source = units("Alpha\n\nAlpha\n\nBeta")
        self.assert_candidate_error(
            [{"units": {"U0001": [], "U0002": [], "U0003": ["Alpha"]}}],
            [source], source, "ambiguous_unit")

    def test_quote_absent_from_whole_document_is_rejected(self):
        source = units("Alpha")
        self.assert_candidate_error([{"units": {"U0001": ["Beta"]}}],
                                    [source], source, "not_in_source")

    def test_repeated_occurrences_in_one_unit_are_preserved(self):
        source = units("aaaa")
        pool, metrics = normalize_keyed_candidates(
            [{"units": {"U0001": ["aa"]}}], [source], source)
        self.assertEqual([item["span"]["start"] for item in pool], [0, 1, 2])
        self.assertEqual(metrics, {"remapped": 0, "deduplicated": 0})

    def test_over_120_expanded_occurrences_fail_atomically(self):
        source = units("a" * 121)
        with self.assertRaises(AnalysisError) as caught:
            normalize_keyed_candidates([{"units": {"U0001": ["a"]}}], [source], source)
        self.assertEqual(caught.exception.code, "SECTION_LIMIT")

    def test_second_batch_failure_does_not_return_partial_candidates(self):
        source = units("Alpha\n\nBeta")
        batches = batch_sections(source)
        self.assert_candidate_error(
            [{"units": {"U0001": ["Alpha"]}}, {"units": {"U0002": ["fabricated"]}}],
            batches, source, "not_in_source")

    def test_invalid_shapes_and_quote_limits_are_rejected(self):
        source = units("Alpha")
        self.assert_candidate_error([{"units": []}], [source], source, "invalid_shape")
        for quotes in ([" "], ["Alpha", "Alpha"], ["x" * 2001], ["Alpha"] * 31):
            self.assert_candidate_error([{"units": {"U0001": quotes}}],
                                        [source], source, "invalid_quote")


if __name__ == "__main__":
    unittest.main()
