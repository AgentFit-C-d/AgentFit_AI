import unittest
from types import SimpleNamespace

from agentfit_ai.langextract_grounding import validate_alignment


def extraction(index, text, start=None, end=None):
    interval = None if start is None else SimpleNamespace(start_pos=start, end_pos=end)
    return SimpleNamespace(extraction_index=index, extraction_text=text,
                           char_interval=interval)


class LangExtractGroundingTests(unittest.TestCase):
    def test_repeated_single_quote_is_ambiguous(self):
        document = "Alpha X. Beta X."
        self.assertEqual(validate_alignment(document, ["X"],
                                            [extraction(0, "X", 6, 7)]),
                         ({"status": "review", "start": None, "end": None},))

    def test_two_repeated_quotes_get_distinct_exact_offsets(self):
        document = "Alpha X. Beta X."
        self.assertEqual(validate_alignment(document, ["X", "X"], [
            extraction(0, "X", 6, 7), extraction(1, "X", 14, 15)]),
            ({"status": "exact", "start": 6, "end": 7},
             {"status": "exact", "start": 14, "end": 15}))

    def test_fuzzy_or_missing_source_is_review(self):
        self.assertEqual(validate_alignment("Alpha X.", ["X"], [
            extraction(0, "X", 0, 1)]),
            ({"status": "review", "start": None, "end": None},))
        self.assertEqual(validate_alignment("Alpha X.", ["Y"], [
            extraction(0, "Y")]),
            ({"status": "review", "start": None, "end": None},))

    def test_alignment_cannot_change_or_drop_candidates(self):
        with self.assertRaises(ValueError):
            validate_alignment("Alpha X.", ["X"], [])
        with self.assertRaises(ValueError):
            validate_alignment("Alpha X.", ["X"], [extraction(0, "Y", 6, 7)])
        with self.assertRaises(ValueError):
            validate_alignment("Alpha X.", ["X"], [extraction(1, "X", 6, 7)])


if __name__ == "__main__":
    unittest.main()
