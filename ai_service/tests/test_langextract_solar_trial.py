import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agentfit_ai.langextract_solar_trial import candidate_payload, score_case, main, run_case


def extraction(text, start, end, anchor=None, alignment_status=None):
    return SimpleNamespace(extraction_class="candidate", extraction_text=text,
                           char_interval=(SimpleNamespace(start_pos=start, end_pos=end)
                                          if start is not None and end is not None
                                          else None),
                           attributes={"anchor": anchor} if anchor is not None else None,
                           alignment_status=alignment_status)


class LangExtractSolarTrialTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("langextract"),
                         "optional LangExtract trial dependency unavailable")
    def test_real_parser_keeps_anchor_without_example_alignment_warning(self):
        from agentfit_ai import langextract_solar_trial as trial

        document = "후보 DB는 NoriDB다. 운영 DB는 NoriDB로 확정했다."
        reply = {"extractions": [
            {"candidate": "NoriDB", "candidate_attributes": {
                "anchor": "후보 DB는 NoriDB다."}},
            {"candidate": "NoriDB", "candidate_attributes": {
                "anchor": "운영 DB는 NoriDB로 확정했다."}}]}
        envelope = {"model": "solar-pro4", "choices": [{
            "finish_reason": "stop", "message": {
                "content": json.dumps(reply, ensure_ascii=False)}}]}

        def transport(payload, key, timeout):
            return json.dumps(envelope, ensure_ascii=False).encode("utf-8")

        with patch("langextract.prompt_validation.logging.warning") as warnings:
            rows = trial.extract_candidates(document, "synthetic-key",
                                            transport=transport)
        self.assertEqual([row.attributes["anchor"] for row in rows], [
            "후보 DB는 NoriDB다.", "운영 DB는 NoriDB로 확정했다."])
        warnings.assert_not_called()

    def test_payload_keeps_candidate_schema_and_bounded_model(self):
        payload = candidate_payload("example prompt")
        self.assertEqual(payload["model"], "solar-pro4")
        self.assertEqual(payload["messages"][1]["content"], "example prompt")
        self.assertEqual(payload["response_format"]["json_schema"]["schema"]
                         ["properties"]["extractions"]["items"]["properties"]
                         ["candidate"], {"type": "string"})
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["reasoning_effort"], "none")
        item = payload["response_format"]["json_schema"]["schema"]\
            ["properties"]["extractions"]["items"]
        self.assertEqual(set(item["required"]),
                         {"candidate", "candidate_attributes"})
        self.assertEqual(item["properties"]["candidate_attributes"]
                         ["properties"]["anchor"], {"type": "string"})

    def test_score_requires_exact_gold_span_and_candidate_local_rule(self):
        document = "팀 채팅은 검토안이다. 팀 채팅을 출시 기능으로 확정했다."
        quote = "팀 채팅"
        first, second = document.index(quote), document.rindex(quote)
        case = {"id": "T01", "document": document,
                "candidate": {"field": "features", "state": "present",
                              "start": first, "end": first + len(quote)},
                "expected_decision": "review"}
        row = score_case(case, [
            extraction(quote, first, first + len(quote), "팀 채팅은 검토안이다."),
            extraction(quote, second, second + len(quote),
                       "팀 채팅을 출시 기능으로 확정했다.")])
        self.assertEqual(row["decision"], "review")
        self.assertTrue(row["evidence_exact"])
        self.assertEqual(row["false_auto_confirmation"], 0)
        self.assertNotIn(document, json.dumps(row, ensure_ascii=False))
        self.assertNotIn(quote, json.dumps(row, ensure_ascii=False))

    def test_single_repeated_quote_cannot_autoconfirm_later_occurrence(self):
        document = "후보는 PineDB다. 운영 DB는 PineDB로 확정했다."
        quote = "PineDB"
        second = document.rindex(quote)
        case = {"id": "T02", "document": document,
                "candidate": {"field": "database", "state": "present",
                              "start": second, "end": second + len(quote)},
                "expected_decision": "allow"}
        first = document.index(quote)
        row = score_case(case, [extraction(quote, first, first + len(quote))])
        self.assertEqual(row["decision"], "review")
        self.assertEqual(row["missed_allow"], 1)

    def test_distinct_anchor_scores_confirmed_repeat_without_confirming_proposal(self):
        document = "후보 DB는 PinoDB다. 운영 DB는 PinoDB로 확정했다."
        items = [extraction("PinoDB", None, None, "후보 DB는 PinoDB다."),
                 extraction("PinoDB", None, None,
                            "운영 DB는 PinoDB로 확정했다.")]
        first = {"id": "A01", "document": document, "candidate": {
            "field": "database", "state": "present", "start": 7, "end": 13},
            "expected_decision": "review"}
        second = {"id": "A02", "document": document, "candidate": {
            "field": "database", "state": "present", "start": 23, "end": 29},
            "expected_decision": "allow"}
        self.assertEqual(score_case(first, items)["decision"], "review")
        self.assertEqual(score_case(second, items)["decision"], "allow")
        self.assertEqual(score_case(second, items)["evidence_exact"], True)

    def test_repeated_same_anchor_cannot_score_confirmed_repeat(self):
        document = "후보 DB는 PinoDB다. 운영 DB는 PinoDB로 확정했다."
        case = {"id": "A03", "document": document, "candidate": {
            "field": "database", "state": "present", "start": 23, "end": 29},
            "expected_decision": "allow"}
        items = [extraction("PinoDB", None, None, "후보 DB는 PinoDB다."),
                 extraction("PinoDB", None, None, "후보 DB는 PinoDB다.")]
        row = score_case(case, items)
        self.assertNotEqual(row["decision"], "allow")
        self.assertFalse(row["evidence_exact"])

    def test_partial_library_alignment_recovered_by_anchor_is_counted(self):
        document = "실시간 알림을 제공한다."
        case = {"id": "A04", "document": document, "candidate": {
            "field": "features", "state": "present", "start": 0, "end": 6},
            "expected_decision": "allow"}
        row = score_case(case, [extraction(
            "실시간 알림", 0, 3, "실시간 알림을 제공한다.",
            SimpleNamespace(value="match_lesser"))])
        self.assertTrue(row["evidence_exact"])
        self.assertEqual(row["source_recovered_count"], 1)

    def test_duplicate_span_is_reported_separately_from_missing_candidate(self):
        document = "Alpha를 사용한다."
        case = {"id": "T03", "document": document,
                "candidate": {"field": "features", "state": "present",
                              "start": 0, "end": 5},
                "expected_decision": "allow"}
        row = score_case(case, [extraction("Alpha", 0, 5),
                                extraction("Alpha", 0, 5)])
        self.assertEqual(row["decision"], "review")
        self.assertEqual(row["duplicate_span_count"], 1)
        self.assertEqual(row["missing_candidate"], 0)

    def test_unlocated_repeated_mentions_remain_ambiguous(self):
        document = "운영 DB 후보는 MallowDB다. 운영 DB는 MallowDB로 확정했다."
        quote = "MallowDB"
        first, second = document.index(quote), document.rindex(quote)
        case = {"id": "T04", "document": document,
                "candidate": {"field": "database", "state": "present",
                              "start": second, "end": second + len(quote)},
                "expected_decision": "allow"}
        items = [extraction(quote, None, None), extraction(quote, None, None)]
        row = score_case(case, items)
        self.assertEqual(row["decision"], "review")
        self.assertEqual(row["resolver_exact_count"], 0)
        self.assertEqual(row["exact_count"], 0)
        self.assertEqual(row["ambiguous_alignment"], 1)
        self.assertEqual(row["missed_allow"], 1)
        case["candidate"] = {"field": "database", "state": "present",
                             "start": first, "end": first + len(quote)}
        case["expected_decision"] = "review"
        self.assertEqual(score_case(case, items)["decision"], "review")

    def test_only_unique_unlocated_quote_can_recover_exact_location(self):
        document = "실시간 알림을 제공한다."
        quote = "실시간 알림"
        case = {"id": "T06", "document": document,
                "candidate": {"field": "features", "state": "present",
                              "start": 0, "end": len(quote)},
                "expected_decision": "allow"}
        row = score_case(case, [extraction(quote, None, None)])
        self.assertEqual(row["decision"], "allow")
        self.assertEqual(row["resolver_exact_count"], 0)
        self.assertEqual(row["exact_count"], 1)
        self.assertEqual(row["source_recovered_count"], 1)

    def test_single_unlocated_repeat_is_not_assigned_to_an_occurrence(self):
        document = "MallowDB는 후보. MallowDB로 확정."
        second = document.rindex("MallowDB")
        case = {"id": "T05", "document": document,
                "candidate": {"field": "database", "state": "present",
                              "start": second, "end": second + 8},
                "expected_decision": "allow"}
        row = score_case(case, [extraction("MallowDB", None, None)])
        self.assertEqual(row["decision"], "review")
        self.assertEqual(row["ambiguous_alignment"], 1)
        self.assertEqual(row["resolver_exact_count"], 0)
        self.assertEqual(row["exact_count"], 0)

    def test_live_transport_uses_bounded_subprocess_path(self):
        from agentfit_ai import langextract_solar_trial as trial

        self.assertIs(trial.run_case.__kwdefaults__["transport"], trial.post_solar)
        self.assertGreater(trial.CALL_TIMEOUT_SECONDS, 120)

    def test_cli_requires_live_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result.json"
            with patch.object(sys, "argv", ["trial", "--case-id", "R01",
                                                "--output", str(output)]):
                with self.assertRaises(SystemExit):
                    main()
            output.write_text("existing", encoding="utf-8")
            with patch.object(sys, "argv", ["trial", "--live", "--case-id",
                                                "R01", "--output", str(output)]):
                with self.assertRaises(SystemExit):
                    main()
            self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_all_mode_reuses_paired_extractions_and_keeps_failed_pairs(self):
        from agentfit_ai import langextract_solar_trial as trial

        paired = "후보 DB는 PinoDB다. 운영 DB는 PinoDB로 확정했다."
        cases = [{"id": "T01", "document": paired, "candidate": {
            "field": "database", "state": "present", "start": 7, "end": 13},
            "expected_decision": "review"},
                 {"id": "T02", "document": paired, "candidate": {
                     "field": "database", "state": "present", "start": 23, "end": 29},
                     "expected_decision": "allow"},
                 {"id": "T03", "document": "Secret Beta", "candidate": {
                     "field": "features", "state": "present", "start": 7, "end": 11},
                     "expected_decision": "review"},
                 {"id": "T04", "document": "Secret Beta", "candidate": {
                     "field": "features", "state": "present", "start": 7, "end": 11},
                     "expected_decision": "review"}]
        cases.extend({"id": f"T{index:02d}", "document": f"Synthetic {index}",
                      "candidate": {"field": "features", "state": "present",
                                    "start": 0, "end": 1},
                      "expected_decision": "allow"}
                     for index in range(5, 19))
        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "cases.json"
            output = Path(temp) / "result.json"
            fixture.write_text(json.dumps({"version": "document-grounding-adversarial-v1",
                                           "cases": cases}), encoding="utf-8")
            def fake_extract(document, key, *, telemetry):
                if document == "Secret Beta":
                    raise RuntimeError("Secret Beta upstream failure")
                if document == paired:
                    return [extraction("PinoDB", None, None,
                                       "후보 DB는 PinoDB다."),
                            extraction("PinoDB", None, None,
                                       "운영 DB는 PinoDB로 확정했다.")]
                return [extraction(document[0], None, None, document)]
            with (patch.object(trial, "CASES_PATH", fixture),
                  patch.object(trial, "CASES_SHA256", hashlib.sha256(
                      fixture.read_bytes()).hexdigest()),
                  patch.object(trial, "load_key", return_value="synthetic-key"),
                  patch.object(trial, "extract_candidates",
                               side_effect=fake_extract) as extractor,
                  patch.object(sys, "argv", ["trial", "--live", "--all", "--output",
                                              str(output)])):
                self.assertEqual(trial.main(), 1)
            saved = output.read_text(encoding="utf-8")
            self.assertNotIn(paired, saved)
            self.assertNotIn("Secret Beta", saved)
            self.assertNotIn("synthetic-key", saved)
            self.assertNotIn("후보 DB는 PinoDB다.", saved)
            report = json.loads(saved)
            self.assertEqual(len(report["rows"]), 18)
            self.assertEqual(report["failed"], 2)
            self.assertEqual(report["provider_calls"], 16)
            self.assertEqual(report["unique_extracted_candidates"], 16)
            self.assertEqual(extractor.call_count, 16)
            self.assertEqual(report["rows"][0]["decision"], "review")
            self.assertEqual(report["rows"][1]["decision"], "allow")
            self.assertEqual(report["ambiguous_alignments"], 0)
            self.assertEqual(report["source_recovered"], 18)

    def test_modified_fixture_is_rejected_before_loading_api_key(self):
        from agentfit_ai import langextract_solar_trial as trial

        with tempfile.TemporaryDirectory() as temp:
            fixture = Path(temp) / "cases.json"
            output = Path(temp) / "result.json"
            fixture.write_text(json.dumps({
                "version": "document-grounding-adversarial-v1",
                "cases": [{"id": "R01", "document": "private document"}] * 18}),
                encoding="utf-8")
            with (patch.object(trial, "CASES_PATH", fixture),
                  patch.object(trial, "load_key") as load_key,
                  patch.object(sys, "argv", ["trial", "--live", "--case-id",
                                              "R01", "--output", str(output)])):
                with self.assertRaises(SystemExit):
                    trial.main()
            load_key.assert_not_called()
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
