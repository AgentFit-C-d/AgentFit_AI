import unittest
from agentfit_ai.profile import FIELDS
from agentfit_ai.candidate_occurrence_evaluation import score_alternatives, error_diagnostics

class EvidenceAlternativesTests(unittest.TestCase):
    def profile(self, spans):
        return {"evidence":{f:spans if f=="ai" else [] for f in FIELDS}}
    def test_complete_alternatives_not_union_or_containment(self):
        a={"start":34,"end":50};b={"start":24,"end":50}
        alternatives=[{"ai":[a]},{"ai":[b]}]
        for span in (a,b):
            self.assertTrue(score_alternatives(self.profile([span]),alternatives)["evidence_matched"])
        for spans in ([a,b],[{"start":0,"end":50}],[{"start":0,"end":16}],[]):
            self.assertFalse(score_alternatives(self.profile(spans),alternatives)["evidence_matched"])
    def test_unexpected_other_field_evidence_fails(self):
        profile=self.profile([])
        self.assertTrue(score_alternatives(profile,[{}])["evidence_matched"])
        profile["evidence"]["backend"]=[{"start":1,"end":2}]
        self.assertFalse(score_alternatives(profile,[{}])["evidence_matched"])

    def test_none_diagnostics_does_not_interrupt_evaluation(self):
        from agentfit_ai.solar import AnalysisError
        self.assertEqual(error_diagnostics(AnalysisError("SECTION_MERGE")), {"calls":[]})

    def test_frozen_cases_and_judgment_payload_exclude_gold(self):
        import json
        from pathlib import Path
        from unittest.mock import Mock
        from agentfit_ai.candidate_occurrence_evaluation import fixed_pool, judge
        path=Path(__file__).resolve().parents[2]/"specs/ai-developer/04-analysis-provider/candidate-occurrence-expansion/evaluation-cases.json"
        cases=json.loads(path.read_text(encoding="utf-8"))["cases"]
        self.assertEqual(len(cases),27)
        for case in cases:
            sections,pool=fixed_pool(case)
            for focus in (False,True):
                analyzer=Mock()
                captured=[]
                def reply(payload,keys,**kwargs):
                    captured.append(payload)
                    kwargs["_trace"]["raw"]="private response must not persist"
                    return {"decisions":{p["id"]:{"decision":"irrelevant"} for p in pool}},"solar-pro4",1,1
                analyzer._send_payload.side_effect=reply
                profile,diagnostic=judge(analyzer,case,focus)
                content=json.loads(captured[0]["messages"][1]["content"])
                self.assertEqual(set(content),{"document","candidates"})
                self.assertEqual(content["document"],case["document"])
                self.assertEqual(len(content["candidates"]),len(case["expected_occurrences"]))
                self.assertTrue(all(("focus" in c)==focus for c in content["candidates"]))
                self.assertTrue(all("span" not in c for c in content["candidates"]))

    def test_judgment_failure_retains_numeric_usage_without_raw_response(self):
        from unittest.mock import Mock
        from agentfit_ai.candidate_occurrence_evaluation import judge
        from agentfit_ai.solar import AnalysisError
        case={"id":"synthetic","document":"Raven",
            "fixed_extraction_reply":{"units":[{"unitId":"U0001","quotes":["Raven"]}]},
            "expected_occurrences":[{"unitId":"U0001","quote":"Raven","start":0,"end":5}]}
        analyzer=Mock()
        def respond(payload,keys,**kwargs):
            kwargs["_trace"]["raw"]="PRIVATE_MODEL_RESPONSE"
            return {"decisions":{}},"solar-pro4",37,11
        analyzer._send_payload.side_effect=respond
        with self.assertRaises(AnalysisError) as caught:judge(analyzer,case,True)
        diagnostic=error_diagnostics(caught.exception)
        self.assertEqual(diagnostic["calls"][0]["prompt_tokens"],37)
        self.assertEqual(diagnostic["calls"][0]["completion_tokens"],11)
        self.assertEqual(diagnostic["calls"][0]["call"],1)
        self.assertNotIn("PRIVATE_MODEL_RESPONSE",str(diagnostic))
        self.assertEqual(caught.exception.diagnostics["candidate_count"],1)
