import unittest
from agentfit_ai.anchored_candidates import judgment_schema
from agentfit_ai.evidence import ROLES
from agentfit_ai.profile import FIELDS, ARRAY_FIELDS
from agentfit_ai.section_analysis import ALL_ROLES, STATUSES, SCOPES

POOL=[{"id":"F0001"}]
def allows(schema, values):
    branches=schema["properties"]["decisions"]["properties"]["F0001"]["anyOf"]
    return any(set(values)==set(b["properties"]) and all(
        value in b["properties"][key]["enum"] for key,value in values.items()) for b in branches)

class SelectedDecisionTests(unittest.TestCase):
    def test_selected_matches_existing_server_eligibility(self):
        schema=judgment_schema(POOL,selected_constraints=True)
        for field in FIELDS:
            for role in ALL_ROLES:
                for status in STATUSES:
                    for scope in SCOPES:
                        values=dict(field=field,role=role,status=status,scope=scope,decision="selected")
                        expected=role in ROLES[field] and scope=="current" and (
                            status=="confirmed" or status=="absent" and field in ARRAY_FIELDS)
                        self.assertEqual(allows(schema,values),expected,values)
    def test_legacy_unchanged_and_exclusions_preserved(self):
        from agentfit_ai.section_analysis import EXCLUSIONS
        legacy=judgment_schema(POOL)
        strict=judgment_schema(POOL,selected_constraints=True)
        bad=dict(field="ai",role="operating_model",status="tentative",scope="current",decision="selected")
        self.assertTrue(allows(legacy,bad))
        self.assertFalse(allows(strict,bad))
        for decision in EXCLUSIONS:
            self.assertTrue(allows(strict,dict(bad,decision=decision)))
        self.assertTrue(allows(strict,{"decision":"irrelevant"}))

    def test_pipeline_uses_constraint_without_extra_calls(self):
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response
        from test_semantic_review import verdict
        captured=[]
        def transport(payload,*args):
            schema=payload["response_format"]["json_schema"]["schema"]
            props=schema["properties"]
            if "units" in props:
                return response({"units":[{"unitId":"U0001","quotes":["Raven"]}]})
            if "decisions" in props:
                captured.append(schema)
                return response({"decisions":{"F0001":{"field":"ai","role":"operating_model",
                    "status":"confirmed","scope":"current","decision":"selected"}}})
            return response(verdict())
        result=AnchoredAnalyzer("synthetic-key",transport=Mock(side_effect=transport),
            prompt_revision="v2",selected_constraints=True).analyze("Raven","case")
        self.assertEqual(result.profile["data"]["ai"],["Raven"])
        self.assertEqual(result.provider_calls,3)
        self.assertIn("selected-constraints-v1",result.prompt_version)
        self.assertFalse(allows(captured[0],dict(field="ai",role="operating_model",
            status="tentative",scope="current",decision="selected")))
        with self.assertRaises(ValueError):AnchoredAnalyzer("synthetic-key",selected_constraints=True)

    def test_false_confirmation_includes_false_absence(self):
        from agentfit_ai.candidate_occurrence_evaluation import unknown_confirmations
        profile={"data":dict.fromkeys(FIELDS)}
        self.assertEqual(unknown_confirmations(profile,{}),[])
        profile["data"]["ai"]=[]
        self.assertEqual(unknown_confirmations(profile,{}),["ai"])
        self.assertEqual(unknown_confirmations(profile,{"ai":[]}),[])
