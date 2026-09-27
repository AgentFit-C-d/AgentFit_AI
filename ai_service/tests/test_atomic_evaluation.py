import unittest
from agentfit_ai.atomic_evaluation import conflict_recognized, false_confirmations, evaluate_case
from agentfit_ai.profile import FIELDS, validate_profile
from test_atomic_verdict import pool_for

class AtomicEvaluationTests(unittest.TestCase):
    def test_conflict_requires_all_expected_candidates_and_correct_legacy_facts(self):
        pool=pool_for("A B",["A","B"])
        facts={p["id"]:{"field":"database","role":"product_fact","status":"confirmed","scope":"current","decision":"conflict"} for p in pool}
        case={"document":"A B","id":"conflict","conflict_candidate_ids":["F0001","F0002"],
              "expected_conflict_decisions":facts}
        self.assertTrue(conflict_recognized({"decisions":facts},pool,case,False))
        self.assertTrue(conflict_recognized({"decisions":{"F0001":"conflict","F0002":"conflict"}},pool,case,True))
        self.assertFalse(conflict_recognized({"decisions":{"F0001":"conflict","F0002":"omit"}},pool,case,True))
        changed={key:dict(value) for key,value in facts.items()}
        changed["F0002"]["field"]="deployment"
        self.assertFalse(conflict_recognized({"decisions":changed},pool,case,False))

    def test_false_confirmation_counts_unsupported_evidence_not_pure_omission(self):
        doc="A A B";data=dict.fromkeys(FIELDS);data["ai"]=["A"]
        evidence={f:[] for f in FIELDS};evidence["ai"]=[{"start":2,"end":3}]
        profile=validate_profile(doc,"test",{"data":data,"evidence":evidence})
        case={"gold":{"ai":[["A"],["B"]]},"accepted_evidence_sets":[{"ai":[{"start":2,"end":3},{"start":4,"end":5}]}]}
        self.assertEqual(false_confirmations(profile,case),[])
        profile["evidence"]["ai"]=[{"start":0,"end":1}]
        self.assertEqual(false_confirmations(profile,case),["ai"])
        profile["data"]["ai"]=[]
        self.assertEqual(false_confirmations(profile,case),["ai"])

    def test_evaluation_never_sends_gold_and_records_failures_safely(self):
        import json
        from unittest.mock import Mock
        case={"id":"one","document":"Raven","gold":{},"accepted_evidence_sets":[{}],
            "fixed_extraction_reply":{"units":[{"unitId":"U0001","quotes":["Raven"]}]},
            "expected_occurrences":[{"unitId":"U0001","quote":"Raven","start":0,"end":5}]}
        captured=[]
        def reply(payload,names,**kwargs):
            captured.append(json.loads(payload["messages"][1]["content"]))
            kwargs["_trace"]["raw"]="PRIVATE RAW RESPONSE"
            return {"decisions":{"F0001":"not-an-enum"}},"solar-pro4",10,5
        analyzer=Mock();analyzer._send_payload.side_effect=reply
        row=evaluate_case(analyzer,case,True)
        self.assertEqual(set(captured[0]),{"document","candidates"})
        self.assertEqual(row["error"],"ANCHORED_JUDGMENT")
        self.assertEqual(row["prompt_tokens"],10)
        self.assertEqual(row["completion_tokens"],5)
        self.assertNotIn("PRIVATE RAW RESPONSE",str(row))
