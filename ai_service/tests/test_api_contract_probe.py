import copy
import unittest
from agentfit_ai.api_contract_probe import CASES, CONFIGS, build_request, score, summarize

class ProbeTests(unittest.TestCase):
    def test_one_factor_and_no_gold(self):
        case=CASES[0]
        base=build_request(case,CONFIGS[0])
        self.assertEqual(base["model"],"solar-mini4")
        for config in CONFIGS[1:]:
            other=build_request(case,config)
            self.assertEqual(base["messages"],other["messages"])
            changed={k for k in base if base[k]!=other[k]}
            self.assertEqual(changed,{"reasoning_effort"} if config=="schema-low" else {"response_format"})
        mutated=copy.deepcopy(case);mutated["expected"]={"role":"WRONG"}
        self.assertEqual(base,build_request(mutated,CONFIGS[0]))
    def test_enum_order_only(self):
        a=build_request(CASES[0],CONFIGS[0])["response_format"]
        b=build_request(CASES[0],CONFIGS[1])["response_format"]
        for field in ("role","status"):
            a["json_schema"]["schema"]["properties"][field]["enum"].reverse()
        self.assertEqual(a,b)
    def test_score(self):
        case=CASES[0];good={"quote":case["document"],**case["expected"]}
        self.assertTrue(score(case,good)["passed"])
        for bad in ({**good,"extra":1},{**good,"role":[]},{**good,"quote":"invented"}):
            self.assertFalse(score(case,bad)["passed"])
    def test_errors_not_consistent(self):
        rows=[{"id":"a","config":CONFIGS[0],"repeat":i,"error":"TIMEOUT","passed":False} for i in (0,1)]
        self.assertEqual(summarize(rows)[CONFIGS[0]]["consistent"],0)
        self.assertEqual(summarize(rows)[CONFIGS[0]]["calls"],2)

    def test_quote_reasoning_argument(self):
        from agentfit_ai.quote_evaluation import reasoning_effort
        self.assertEqual(reasoning_effort("low"),"low")
        self.assertEqual(reasoning_effort("none"),"none")
        with self.assertRaises(ValueError): reasoning_effort("invalid")
