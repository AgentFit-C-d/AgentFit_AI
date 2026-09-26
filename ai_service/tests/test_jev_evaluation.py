import unittest
from agentfit_ai.jev_evaluation import build_request,parse_answer,EvaluationError,CRITERIA

class JevEvaluationTests(unittest.TestCase):
    def test_request_does_not_send_expected_and_reverses_only_choices(self):
        case={"document":"Synthetic text","candidate":"Arin","expected":"production"}
        a=build_request(case,False);b=build_request(case,True)
        self.assertEqual(a["state"],b["state"])
        self.assertNotIn("expected",a["state"])
        self.assertEqual(list(a["questions"]["role"]["criteria"]),list(reversed(b["questions"]["role"]["criteria"])))

    def test_valid_answer_preserves_probability_and_choice(self):
        probabilities=dict.fromkeys(CRITERIA,0.0);probabilities["development"]=1.0
        raw={"model":"solar-jev","answers":{"role":{"type":"choice","choice":"development",
             "probabilities":probabilities,"confidence":0.8}}}
        self.assertEqual(parse_answer(raw)["choice"],"development")
        self.assertEqual(parse_answer(raw)["confidence"],0.8)

    def test_bad_answers_fail_closed(self):
        for raw in [{},{"model":"other","answers":{}},
                    {"model":"solar-jev","answers":{"role":{"type":"choice","choice":"invented"}}}]:
            with self.subTest(raw=raw),self.assertRaises(EvaluationError):parse_answer(raw)

    def test_invalid_probabilities_are_rejected(self):
        for value in [True,-0.1,1.1,float("nan")]:
            probabilities=dict.fromkeys(CRITERIA,0.0);probabilities["production"]=value
            raw={"model":"solar-jev","answers":{"role":{"type":"choice","choice":"production",
                 "probabilities":probabilities,"confidence":0.8}}}
            with self.subTest(value=value),self.assertRaises(EvaluationError):parse_answer(raw)
