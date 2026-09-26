import unittest
from agentfit_ai.independent_classification import build_request,parse_response,CRITERIA
from agentfit_ai.solar import AnalysisError
from agentfit_ai.evidence import EvidenceError

def response():
    return {"model":"solar-jev","answers":{axis:{"type":"choice","choice":next(iter(options)),
        "probabilities":{k:float(k==next(iter(options))) for k in options},"confidence":0.9}
        for axis,options in CRITERIA.items()}}

class IndependentClassificationTests(unittest.TestCase):
    def test_request_omits_existing_labels_and_expected(self):
        case=dict(document="Arin is used.",quote="Arin",context=None,
                  role="wrong",status="wrong",field="wrong",scope="wrong",
                  expected_role="development",expected_status="confirmed")
        a=build_request(case,False);b=build_request(case,True)
        self.assertEqual(set(a["state"]),{"document","quote","context"})
        self.assertEqual(set(a["questions"]),{"role","status"})
        for axis in CRITERIA:
            self.assertEqual(list(a["questions"][axis]["criteria"]),
                             list(reversed(b["questions"][axis]["criteria"])))
    def test_invalid_quote_is_rejected_before_request(self):
        with self.assertRaises(EvidenceError):
            build_request(dict(document="Arin",quote="Missing",context=None),False)
    def test_both_axes_are_required(self):
        raw=response()
        self.assertEqual(set(parse_response(raw)["answers"]),{"role","status"})
        del raw["answers"]["status"]
        with self.assertRaises(AnalysisError):parse_response(raw)
    def test_invalid_numbers_and_unknown_choices_rejected(self):
        for value in [10**400,True,-1,float("nan"),float("inf")]:
            raw=response();raw["answers"]["role"]["confidence"]=value
            with self.subTest(value=value),self.assertRaises(AnalysisError):parse_response(raw)
        raw=response();raw["answers"]["role"]["choice"]="not-an-option"
        with self.assertRaises(AnalysisError):parse_response(raw)

    def test_gate_requires_joint_accuracy_consistency_and_no_false_adoption(self):
        import copy
        from agentfit_ai.independent_classification import summarize
        good={"expected_role":"development","expected_status":"confirmed",
              "answers":{"role":{"choice":"development"},"status":{"choice":"confirmed"}},
              "role_correct":True,"status_correct":True,"passed":True}
        rows=[copy.deepcopy(good) for _ in range(24)]
        self.assertTrue(summarize(rows,24)["gate_passed"])
        rows[0]["answers"]["role"]["choice"]="operating_technology"
        rows[0].update(role_correct=False,passed=False)
        summary=summarize(rows,24)
        self.assertEqual(summary["passed"],23)
        self.assertEqual(summary["consistent_pairs"],11)
        self.assertEqual(summary["false_adopted"],1)
        self.assertFalse(summary["gate_passed"])
        self.assertFalse(summarize([],24)["gate_passed"])
    def test_ambiguous_citation_needs_exact_unique_context(self):
        from agentfit_ai.evidence import EvidenceError
        case=dict(document="old Arin new Arin",quote="Arin",context=None)
        with self.assertRaises(EvidenceError):build_request(case)
        case["context"]="new Arin"
        self.assertEqual(build_request(case)["state"]["context"],"new Arin")
