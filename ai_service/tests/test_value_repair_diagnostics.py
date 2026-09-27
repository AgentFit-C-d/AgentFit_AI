import unittest
from agentfit_ai.value_repair_evaluation import quote_observations
from agentfit_ai.anchored_candidates import units

class QuoteObservationTests(unittest.TestCase):
    def test_ambiguous_quote_is_visible_without_text(self):
        doc="First secret; second secret."
        reply={"repairs":{"ai":{"facts":[{"unitId":"U0001","quote":"secret","context":doc}]}}}
        result=quote_observations(reply,"ai",units(doc))
        self.assertEqual(result,[{"known_unit":True,"quote_matches":2,"context_matches":1,"quote_in_context_matches":2}])
        self.assertNotIn("secret",str(result))
        reply["repairs"]["ai"]["facts"][0]["context"]="second secret."
        self.assertEqual(quote_observations(reply,"ai",units(doc))[0]["quote_in_context_matches"],1)

    def test_malformed_facts_do_not_leak_or_crash_diagnostics(self):
        reply={"repairs":{"ai":{"facts":[{"unitId":[],"quote":{"secret":"value"},"context":[]}]}}}
        result=quote_observations(reply,"ai",units("source"))
        self.assertEqual(result,[{"known_unit":False,"quote_matches":None,"context_matches":None,"quote_in_context_matches":None}])
        self.assertEqual(quote_observations({},"ai",units("source")),[])

    def test_response_format_diagnostics_never_return_content(self):
        import json
        from agentfit_ai.value_repair_evaluation import response_format_observation
        content='{"repairs":{"frontend":{},"frontend":{"secret":"do-not-record"}}}'
        raw=json.dumps({"choices":[{"message":{"content":content}}]}).encode()
        result=response_format_observation(raw)
        self.assertEqual(result,{"reason":"DUPLICATE_CONTENT_KEYS","duplicate_count":1})
        self.assertNotIn("do-not-record",str(result))
        raw=json.dumps({"choices":[{"message":{"content":"private invalid text"}}]}).encode()
        self.assertEqual(response_format_observation(raw),{"reason":"CONTENT_JSON_INVALID"})
