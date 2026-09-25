import json
import unittest
from unittest.mock import Mock
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import SolarAnalyzer,AnalysisError

def response(fields):
    return json.dumps({"model":"solar-pro4-260806","choices":[{"finish_reason":"stop","message":{"content":json.dumps(fields)}}],"usage":{"prompt_tokens":10,"completion_tokens":20}}).encode()
def core():
    fields={f:None for f in FIELDS if f!="features"}
    fields["project_name"]={"value":"Alpha","evidenceLineIds":[1]}
    return fields
def features(line=1):
    return {"features":{"spans":[{"lineId":line,"startText":"registration","endText":"registration"}],"absenceLineIds":[]}}

class StagedAnalysisTests(unittest.TestCase):
    def test_two_calls_without_repair(self):
        transport=Mock(side_effect=[response(core()),response(features())])
        r=SolarAnalyzer("synthetic-key",transport=transport).analyze("Alpha registration","doc-1")
        self.assertEqual(transport.call_count,2)
        self.assertEqual(r.provider_calls,2)
        self.assertTrue(r.first_pass_validated)
        self.assertEqual(r.repaired_fields,())
        self.assertEqual(r.prompt_tokens,20)
        self.assertEqual(r.profile["data"]["features"],["registration"])
    def test_only_invalid_field_gets_one_repair(self):
        transport=Mock(side_effect=[response(core()),response(features(0)),response(features())])
        r=SolarAnalyzer("synthetic-key",transport=transport).analyze("Alpha registration","doc-1")
        self.assertEqual(transport.call_count,3)
        repair=transport.call_args_list[2].args[0]
        self.assertEqual(repair["response_format"]["json_schema"]["schema"]["required"],["features"])
        self.assertEqual(r.provider_calls,3)
        self.assertFalse(r.first_pass_validated)
        self.assertEqual(r.repaired_fields,("features",))
    def test_bad_repair_stops_at_three_calls(self):
        transport=Mock(side_effect=[response(core()),response(features(0)),response(features(0))])
        with self.assertRaises(AnalysisError) as caught:
            SolarAnalyzer("synthetic-key",transport=transport).analyze("Alpha registration","doc-1")
        self.assertEqual(transport.call_count,3)
        self.assertEqual(caught.exception.field,"features")
        self.assertEqual(caught.exception.provider_calls,3)
        self.assertFalse(caught.exception.first_pass_validated)
    def test_network_failure_is_not_retried(self):
        transport=Mock(side_effect=AnalysisError("PROVIDER_TIMEOUT"))
        with self.assertRaises(AnalysisError):
            SolarAnalyzer("synthetic-key",transport=transport).analyze("Alpha","doc-1")
        self.assertEqual(transport.call_count,1)


    def test_multiple_invalid_fields_share_one_repair_and_preserve_valid_fields(self):
        bad = core()
        bad["backend"] = {"value": ["Python"], "evidenceLineIds": [99]}
        repair = features()
        repair["backend"] = {"value": ["Python"], "evidenceLineIds": [1]}
        transport = Mock(side_effect=[response(bad), response(features(0)), response(repair)])
        result = SolarAnalyzer("synthetic-key", transport=transport).analyze("Alpha Python registration", "doc-1")
        self.assertEqual(transport.call_count, 3)
        self.assertEqual(set(result.repaired_fields), {"backend", "features"})
        self.assertEqual(result.profile["data"]["project_name"], "Alpha")
        self.assertEqual(result.profile["data"]["backend"], ["Python"])
        self.assertEqual(result.prompt_tokens, 30)
        self.assertEqual(result.completion_tokens, 60)

    def test_unknown_usage_does_not_become_zero(self):
        incomplete = json.loads(response(core()))
        incomplete.pop("usage")
        transport = Mock(side_effect=[json.dumps(incomplete).encode(), response(features())])
        result = SolarAnalyzer("synthetic-key", transport=transport).analyze("Alpha registration", "doc-1")
        self.assertIsNone(result.prompt_tokens)
        self.assertIsNone(result.completion_tokens)
