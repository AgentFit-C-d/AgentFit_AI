import importlib
from types import SimpleNamespace
import unittest


def ground(document, extractions):
    try:
        module = importlib.import_module("agentfit_ai.anchored_grounding")
    except ImportError:
        raise AssertionError("anchored grounding is not implemented") from None
    return module.ground_anchored_extractions(document, extractions)


def candidate(quote, anchor=None, interval=None):
    attributes = {"anchor": anchor} if anchor is not None else None
    char_interval = (SimpleNamespace(start_pos=interval[0], end_pos=interval[1])
                     if interval is not None else None)
    return SimpleNamespace(extraction_class="candidate", extraction_text=quote,
                           attributes=attributes, char_interval=char_interval)


class AnchoredGroundingTests(unittest.TestCase):
    def test_distinct_source_anchors_resolve_repeated_korean_name(self):
        document = "후보 DB는 PinoDB다. 운영 DB는 PinoDB로 확정했다."
        rows = ground(document, [
            candidate("PinoDB", "후보 DB는 PinoDB다."),
            candidate("PinoDB", "운영 DB는 PinoDB로 확정했다.")])
        self.assertEqual([(row["status"], row["start"], row["end"])
                          for row in rows],
                         [("exact", 7, 13), ("exact", 23, 29)])

    def test_duplicate_anchor_cannot_confirm_second_occurrence(self):
        document = "후보 DB는 PinoDB다. 운영 DB는 PinoDB로 확정했다."
        rows = ground(document, [candidate("PinoDB", "후보 DB는 PinoDB다."),
                                 candidate("PinoDB", "후보 DB는 PinoDB다.")])
        self.assertEqual([row["status"] for row in rows], ["review", "review"])

    def test_anchor_repeated_in_document_is_ambiguous(self):
        document = "PinoDB 사용. PinoDB 사용."
        row, = ground(document, [candidate("PinoDB", "PinoDB 사용.")])
        self.assertEqual(row["status"], "review")

    def test_quote_repeated_inside_anchor_is_ambiguous(self):
        row, = ground("PinoDB와 PinoDB를 검토한다.", [
            candidate("PinoDB", "PinoDB와 PinoDB를 검토한다.")])
        self.assertEqual(row["status"], "review")

    def test_mismatched_library_interval_never_overrides_anchor(self):
        document = "후보 DB는 PinoDB다. 운영 DB는 PinoDB로 확정했다."
        row, = ground(document, [candidate(
            "PinoDB", "운영 DB는 PinoDB로 확정했다.", (7, 13))])
        self.assertEqual(row["status"], "review")

    def test_invalid_anchor_blocks_unique_quote_fallback(self):
        row, = ground("실시간 알림을 제공한다.", [
            candidate("실시간 알림", "알림을 제공하기로 했다.")])
        self.assertEqual(row["status"], "review")

    def test_unique_quote_without_anchor_uses_exact_source(self):
        row, = ground("실시간 알림을 제공한다.", [candidate("실시간 알림")])
        self.assertEqual((row["status"], row["start"], row["end"]),
                         ("exact", 0, 6))

    def test_repeated_quote_without_anchor_stays_unresolved(self):
        rows = ground("PinoDB 후보. PinoDB 확정.", [
            candidate("PinoDB"), candidate("PinoDB")])
        self.assertEqual([row["status"] for row in rows], ["review", "review"])

    def test_overlapping_occurrences_are_not_treated_as_unique(self):
        row, = ground("aaaa", [candidate("aaa")])
        self.assertEqual(row["status"], "review")

    def test_nonliteral_quote_is_not_grounded(self):
        row, = ground("실시간 알림을 제공한다.", [
            candidate("실시간 통지", "실시간 알림을 제공한다.")])
        self.assertEqual(row["status"], "review")


if __name__ == "__main__":
    unittest.main()
