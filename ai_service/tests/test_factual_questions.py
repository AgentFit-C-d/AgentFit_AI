import unittest
from agentfit_ai.factual_questions import build_request,decide,baseline_decision,summarize
from agentfit_ai.solar import AnalysisError

class FactualQuestionTests(unittest.TestCase):
    def test_only_explicit_positive_combination_is_adopted(self):
        a=dict(current="yes",adopted="yes",rejected="no",development_only="no")
        self.assertEqual(decide(a),"adopt")
        for key in a:
            b=dict(a);b[key]="unknown"
            self.assertEqual(decide(b),"unknown")
    def test_contradictions_are_not_adopted_or_silently_excluded(self):
        for a in [dict(current="yes",adopted="yes",rejected="yes",development_only="no"),
                  dict(current="no",adopted="yes",rejected="no",development_only="no"),
                  dict(current="yes",adopted="yes",rejected="no",development_only="yes")]:
            self.assertEqual(decide(a),"unknown")
    def test_known_exclusions_and_baseline_mapping(self):
        self.assertEqual(decide(dict(current="yes",adopted="no",rejected="yes",development_only="unknown")),"exclude")
        self.assertEqual(baseline_decision("development","confirmed"),"exclude")
        self.assertEqual(baseline_decision("operating_technology","tentative"),"unknown")
    def test_invalid_answers_fail_closed(self):
        for a in [{},dict(current="yes",adopted="yes",rejected="no",development_only=True)]:
            with self.assertRaises(AnalysisError):decide(a)
    def test_request_whitelists_source_only(self):
        a=build_request(dict(document="NoriDB is used",quote="NoriDB",context=None,expected_decision="adopt",role="bad"),False)
        self.assertEqual(set(a["state"]),{"document","quote","context"})
        self.assertEqual(set(a["questions"]),{"current","adopted","rejected","development_only"})
    def test_empty_evaluation_cannot_pass(self):
        self.assertFalse(summarize([])["gate_passed"])

    def test_frozen_gold_matches_server_policy_and_exact_source(self):
        import json
        from agentfit_ai.factual_questions import CASES
        cases=json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(len({c["id"] for c in cases}),12)
        for case in cases:
            self.assertEqual(decide(case["expected_answers"]),case["expected_decision"])
            build_request(case)
    def test_parser_rejects_invalid_probability(self):
        from agentfit_ai.factual_questions import parse_response,QUESTIONS,CRITERIA
        def raw():
            return {"model":"solar-jev","answers":{key:{"type":"choice","choice":"yes",
                "probabilities":{v:float(v=="yes") for v in CRITERIA},"confidence":0.8} for key in QUESTIONS}}
        for value in [True,10**400,float("nan"),float("inf"),-1]:
            envelope=raw();envelope["answers"]["current"]["confidence"]=value
            with self.subTest(value=value),self.assertRaises(AnalysisError):parse_response(envelope)
        envelope=raw();del envelope["answers"]["current"]
        with self.assertRaises(AnalysisError):parse_response(envelope)
    def test_more_abstentions_cannot_pass_improvement_gate(self):
        rows=[]
        for i in range(12):
            for order in ("forward","reverse"):
                for mode in ("baseline","factual"):
                    rows.append(dict(id=str(i),order=order,mode=mode,expected_decision="adopt",
                        decision="adopt" if mode=="baseline" else "unknown",
                        passed=mode=="baseline",elapsed_ms=1,question_correct=4))
        result=summarize(rows)
        self.assertEqual(result["factual"]["false_adopted"],0)
        self.assertFalse(result["gate_passed"])
