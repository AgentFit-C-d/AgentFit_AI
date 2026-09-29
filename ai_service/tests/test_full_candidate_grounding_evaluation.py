"""All-candidate scoring must find off-target auto confirmations."""

from types import SimpleNamespace
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from agentfit_ai.document_extraction import ExtractedDocument
from agentfit_ai.docling_structured_trial import StructuredDocument


def document(text):
    return ExtractedDocument(
        "PDF", text, 20, len(text), 1,
        [{"page": 1, "start": 0, "end": len(text)}])


def candidate(quote, anchor):
    return SimpleNamespace(
        extraction_class="candidate", extraction_text=quote,
        attributes={"anchor": anchor}, char_interval=None,
        alignment_status=None)


def gold(text, quote, *, field="features", occurrence=0):
    starts = [index for index in range(len(text)) if text.startswith(quote, index)]
    start = starts[occurrence]
    return {"start": start, "end": start + len(quote),
            "field": field, "page": 1}


class FullCandidateGroundingTests(unittest.TestCase):
    def test_all_fixed_gold_positions_survive_real_docling_pdf(self):
        import importlib.util
        if not (importlib.util.find_spec("docling") and
                importlib.util.find_spec("reportlab")):
            self.skipTest("optional experiment dependencies unavailable")
        from agentfit_ai.full_candidate_grounding_evaluation import load_cases
        from agentfit_ai.docling_grounding_evaluation import (
            locate_gold, render_structured_pdf, render_synthetic_pdf)
        from agentfit_ai.docling_structured_trial import convert_structured_pdf_bytes

        total_gold = 0
        for case in load_cases():
            with self.subTest(case=case["id"]):
                renderer = (render_structured_pdf if case["layout"] == "structured"
                            else render_synthetic_pdf)
                converted = convert_structured_pdf_bytes(renderer(case["lines"]))
                if case["layout"] == "structured":
                    self.assertEqual((converted.heading_count,
                                      converted.table_count), (1, 1))
                for item in case["expected"]:
                    start, end, page = locate_gold(
                        converted.extracted, item["anchor"], item["quote"])
                    self.assertEqual(page, 1)
                    self.assertEqual(converted.extracted.text[start:end],
                                     item["quote"])
                    total_gold += 1
        self.assertEqual(total_gold, 5)

    def test_pinned_cases_preflight_and_line_endings(self):
        from agentfit_ai import full_candidate_grounding_evaluation as trial

        original = trial.CASES_PATH.read_bytes()
        self.assertEqual(len(trial.load_cases()), 4)
        with patch.object(Path, "read_bytes", return_value=original.replace(
                b"\n", b"\r\n")):
            self.assertEqual(len(trial.load_cases()), 4)
        with patch.object(trial, "CASES_SHA256", "wrong"):
            with self.assertRaises(ValueError):
                trial.load_cases()

    def test_evaluate_scores_all_mentions_without_source_output(self):
        from agentfit_ai.full_candidate_grounding_evaluation import evaluate_documents

        text = "검색을 제공한다. 채팅 알림을 제공한다."
        cases = [{"id": "D01", "category": "repeat", "layout": "plain",
                  "lines": [text], "expected": [{"anchor": "검색", "quote": "검색",
                                               "field": "features"}]}]
        report = evaluate_documents(
            cases, "synthetic-key",
            converter=lambda raw: StructuredDocument(document(text), 0, 0),
            extractor=lambda source, key: [
                candidate("검색", "검색을 제공한다."),
                candidate("채팅 알림", "채팅 알림을 제공한다.")],
            classifier=lambda source, items, key: [
                {"field": "features", "status": "confirmed"}] * 2,
            plain_renderer=lambda lines: b"%PDF-synthetic")
        self.assertEqual(report["false_auto_confirmations"], 1)
        self.assertEqual(report["missed_allows"], 0)
        self.assertEqual(report["rows"][0]["candidate_count"], 2)
        saved = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("채팅", saved)
        self.assertNotIn("synthetic-key", saved)

    def test_cli_rejects_unpinned_fixture_before_key_loading(self):
        from agentfit_ai import full_candidate_grounding_evaluation as trial

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            with (patch.object(sys, "argv", ["trial", "--live", "--output",
                                                   str(output)]),
                  patch.object(trial, "CASES_SHA256", "wrong"),
                  patch.object(trial, "load_key", side_effect=AssertionError(
                      "key must not be loaded"))):
                with self.assertRaises(SystemExit):
                    trial.main()
            self.assertFalse(output.exists())

    def test_extra_auto_candidate_is_a_false_confirmation(self):
        from agentfit_ai.full_candidate_grounding_evaluation import score_document

        text = "검색을 제공한다. 채팅 알림을 제공한다."
        first, second = text.split(". ")
        result = score_document(
            document(text), [candidate("검색", first + "."),
                             candidate("채팅 알림", second)],
            [{"field": "features", "status": "confirmed"}] * 2,
            [gold(text, "검색")])
        self.assertEqual(result["allowed_candidates"], 2)
        self.assertEqual(result["false_auto_confirmations"], 1)
        self.assertEqual(result["missed_allows"], 0)
        self.assertEqual(result["exact_allowed_positions"], 2)
        self.assertNotIn("채팅", str(result))

    def test_same_name_proposal_does_not_replace_confirmed_occurrence(self):
        from agentfit_ai.full_candidate_grounding_evaluation import score_document

        lines = ["검토 DB는 CedarDB다.", "운영 DB는 CedarDB로 확정했다."]
        text = "\n".join(lines)
        result = score_document(
            document(text), [candidate("CedarDB", line) for line in lines],
            [{"field": "database", "status": "tentative"},
             {"field": "database", "status": "confirmed"}],
            [gold(text, "CedarDB", field="database", occurrence=1)])
        self.assertEqual((result["allowed_candidates"],
                          result["false_auto_confirmations"],
                          result["missed_allows"]), (1, 0, 0))

    def test_wrong_field_counts_false_auto_and_missing_gold(self):
        from agentfit_ai.full_candidate_grounding_evaluation import score_document

        text = "검색을 제공한다."
        result = score_document(
            document(text), [candidate("검색", text)],
            [{"field": "database", "status": "confirmed"}],
            [gold(text, "검색")])
        self.assertEqual((result["false_auto_confirmations"],
                          result["missed_allows"]), (1, 1))

    def test_duplicate_span_is_not_auto_confirmed(self):
        from agentfit_ai.full_candidate_grounding_evaluation import score_document

        text = "검색을 제공한다."
        result = score_document(
            document(text), [candidate("검색", text), candidate("검색", text)],
            [{"field": "features", "status": "confirmed"}] * 2,
            [gold(text, "검색")])
        self.assertEqual(result["allowed_candidates"], 0)
        self.assertEqual(result["missed_allows"], 1)

    def test_missed_gold_reports_stage_without_source(self):
        from agentfit_ai.full_candidate_grounding_evaluation import score_document

        text = "요금 계산 자동화를 제공한다."
        result = score_document(
            document(text), [candidate("요금 계산 자동화", text)],
            [{"field": "features", "status": "tentative"}],
            [gold(text, "요금 계산 자동화")])
        self.assertEqual(result["missed_reasons"], {"status_not_confirmed": 1})
        self.assertNotIn("요금", str(result))


if __name__ == "__main__":
    unittest.main()
