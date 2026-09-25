import unittest
from unittest.mock import Mock
from agentfit_ai.source_candidates import source_candidates, CandidateLimitError
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import cited_to_profile, AnalysisError, SolarAnalyzer

class SourceCandidateTests(unittest.TestCase):
    def test_exact_offsets_unicode_and_crlf(self):
        doc = chr(0x1f600) + " 회원 승인을\r\n야간 백업이다."
        tokens = source_candidates(doc)
        self.assertEqual([t["id"] for t in tokens], list(range(1, len(tokens)+1)))
        for t in tokens:
            self.assertEqual(doc[t["start"]:t["end"]], t["text"])
        self.assertIn("승인", [t["text"] for t in tokens])
        self.assertIn("백업", [t["text"] for t in tokens])
        backup = next(t for t in tokens if t["text"] == "백업")
        self.assertEqual(backup["lineId"], 2)
        self.assertEqual(backup["start"], doc.index("백업"))
        self.assertEqual(tokens, source_candidates(doc))

    def test_repeated_words_have_distinct_ids_and_positions(self):
        tokens = source_candidates("backup then backup")
        self.assertEqual([(t["id"], t["start"]) for t in tokens if t["text"] == "backup"], [(1,0),(3,12)])

    def test_limit_rejected_without_truncation_or_provider_call(self):
        with self.assertRaises(CandidateLimitError):
            source_candidates("x " * 12001)
        transport = Mock()
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key",transport=transport).analyze("x " * 12001,"doc")
        self.assertEqual(caught.exception.code,"SOURCE_CANDIDATE_LIMIT")
        transport.assert_not_called()

    def test_only_whitespace_is_not_a_candidate(self):
        self.assertEqual(source_candidates("  \r\n\t"), [])

class CandidateProjectionTests(unittest.TestCase):
    def fields(self, start, end, line=1):
        fields = dict.fromkeys(FIELDS)
        fields["features"] = {"spans":[{"lineId":line,"startId":start,"endId":end,"role":"user_action"}],"absenceLineIds":[]}
        return fields

    def test_selected_repeated_occurrence_comes_from_id(self):
        r=cited_to_profile("backup then backup","doc",self.fields(3,3))
        self.assertEqual(r["data"]["features"],["backup"])
        self.assertEqual(r["evidence"]["features"][0]["start"],12)

    def test_unicode_range_preserves_internal_spaces(self):
        doc=chr(0x1f600)+" 장소  확인과 후보 선택"
        r=cited_to_profile(doc,"doc",self.fields(2,3))
        self.assertEqual(r["data"]["features"],["장소  확인"])
        self.assertEqual(r["evidence"]["features"][0]["start"],2)

    def test_invalid_ids_order_lines_and_extra_keys_are_rejected(self):
        for start,end,line in [(0,1,1),(1,99,1),(True,1,1),(2,1,1),(1,2,1),(1,1,2)]:
            with self.subTest(start=start,end=end,line=line),self.assertRaises(AnalysisError):
                cited_to_profile("search\nbackup","doc",self.fields(start,end,line))
        fields=self.fields(1,1)
        fields["features"]["spans"][0]["quote"]="search"
        with self.assertRaises(AnalysisError):
            cited_to_profile("search","doc",fields)

    def test_duplicate_range_and_oversized_range_rejected(self):
        fields=self.fields(1,1)
        fields["features"]["spans"]*=2
        with self.assertRaises(AnalysisError):
            cited_to_profile("search","doc",fields)
        with self.assertRaises(AnalysisError):
            cited_to_profile("x"*201,"doc",self.fields(1,1))

class CandidateRequestTests(unittest.TestCase):
    def test_candidates_and_bounds_only_in_feature_calls_including_repair(self):
        from test_staged_analysis import response, core, features
        transport=Mock(side_effect=[response(core()),response(features(99)),response(features())])
        result=SolarAnalyzer("synthetic-key",transport=transport).analyze("Alpha registration","doc")
        payloads=[call.args[0] for call in transport.call_args_list]
        self.assertNotIn("Server source candidates",payloads[0]["messages"][1]["content"])
        for payload in payloads[1:]:
            self.assertIn('T2 L1 "registration"',payload["messages"][1]["content"])
            item=payload["response_format"]["json_schema"]["schema"]["properties"]["features"]["anyOf"][1]["properties"]["spans"]["items"]
            self.assertEqual(set(item["properties"]),{"lineId","startId","endId","role"})
            self.assertEqual(item["properties"]["endId"]["maximum"],2)
        self.assertEqual(result.profile["data"]["features"],["registration"])

    def test_candidate_bounds_do_not_leak_between_documents(self):
        from test_staged_analysis import response, core, features
        transport=Mock(side_effect=[response(core()),response(features()),
                                   response(core()),response(features(token=3))])
        analyzer=SolarAnalyzer("synthetic-key",transport=transport)
        analyzer.analyze("Alpha registration","doc1")
        analyzer.analyze("Alpha Python registration","doc2")
        for idx, count in [(1,2),(3,3)]:
            schema=transport.call_args_list[idx].args[0]["response_format"]["json_schema"]["schema"]
            self.assertEqual(schema["properties"]["features"]["anyOf"][1]["properties"]["spans"]["items"]["properties"]["startId"]["maximum"],count)

    def test_candidate_limit_retains_safe_diagnostic_code(self):
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key",transport=Mock()).analyze("x "*12001,"doc")
        self.assertEqual(caught.exception.diagnostics["error"],"SOURCE_CANDIDATE_LIMIT")
