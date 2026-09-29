import unittest

from agentfit_ai.section_feature_review import (
    split_feature_sections, validate_section_coverage)


class SectionSplitTests(unittest.TestCase):
    def test_headings_and_blank_lines_cover_every_line_once(self):
        document = "intro\r\n# A\r\nitem\r\n\r\n## B\r\nlast"
        chunks = split_feature_sections(document, max_lines=3)
        self.assertEqual(chunks, ((1, 1), (2, 4), (5, 6)))
        validate_section_coverage(chunks, 6)

    def test_unheaded_840_and_841_lines_cross_seven_chunk_boundary(self):
        for count, expected in ((840, 7), (841, 8)):
            chunks = split_feature_sections("x\n" * count)
            self.assertEqual(len(chunks), expected)
            self.assertEqual(chunks[0], (1, 120))
            self.assertEqual(chunks[-1][1], count)
            validate_section_coverage(chunks, count)

    def test_long_heading_section_splits_without_gap(self):
        chunks = split_feature_sections("# A\n" + "x\n" * 240)
        self.assertEqual(chunks, ((1, 120), (121, 240), (241, 241)))

    def test_coverage_validator_rejects_gaps_overlap_and_large_chunks(self):
        for chunks, count in (
            (((1, 2), (4, 4)), 4),
            (((1, 2), (2, 4)), 4),
            (((1, 121),), 121),
        ):
            with self.subTest(chunks=chunks), self.assertRaises(ValueError):
                validate_section_coverage(chunks, count)


if __name__ == "__main__":
    unittest.main()
