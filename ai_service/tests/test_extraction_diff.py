import json
import unittest
from agentfit_ai.extraction_diff import diagnose

def fact(value="x",field="features",role="user_action",status="confirmed",scope="current",start=0):
    return dict(value=value,field=field,role=role,status=status,scope=scope,span={"start":start,"end":start+1})

def case(rows):
    return {"document":"x y","expected":rows}

class DiffTests(unittest.TestCase):
    def test_role_only(self):
        r=diagnose([fact(role="product_fact")],case([["features","x","user_action","confirmed","current"]]))
        self.assertEqual(r["counts"]["role"],1)
        self.assertEqual(r["counts"]["missing_exact"],0)
        self.assertEqual(r["counts"]["field"],0)

    def test_duplicate_and_order(self):
        c=case([["features","x",role,"confirmed","current"] for role in ("user_action","operational_action")])
        a=[fact(role="operational_action"),fact()]
        self.assertEqual(diagnose(a,c)["counts"]["role"],0)
        self.assertEqual(diagnose(a[::-1],c)["counts"],diagnose(a,c)["counts"])
        self.assertEqual(diagnose(a[:1],c)["counts"]["missing_exact"],1)

    def test_mismatched_text_not_guessed(self):
        r=diagnose([fact("paraphrase")],case([["features","x","user_action","confirmed","current"]]))
        self.assertEqual(r["counts"]["missing_exact"],1)
        self.assertEqual(r["counts"]["extra_exact"],1)
        self.assertEqual(r["counts"]["role"],0)

    def test_partial_gold(self):
        c={"document":"x","expected_roles":{"x":"client"},"forbidden_confirmed_fields":["ai"]}
        r=diagnose([fact(field="ai",role="client")],c)
        self.assertEqual(r["counts"]["forbidden_confirmed"],1)
        self.assertEqual(r["evaluated_dimensions"],["role"])
        self.assertNotIn("status",r["counts"])

    def test_absence(self):
        c={"document":"x","expected_absent":["external_integrations"]}
        r=diagnose([fact(None,"external_integrations","product_fact","confirmed")],c)
        self.assertEqual(r["counts"]["role"],1)
        self.assertEqual(r["counts"]["status"],1)
        self.assertEqual(r["counts"]["absence_value"],0)

    def test_context_and_privacy(self):
        c=case([["features","x","user_action","confirmed","current"]])
        c["expected_contexts"]=[{"field":"features","value":"x","role":"user_action","context":"x"}]
        r=diagnose([fact(start=2)],c)
        self.assertEqual(r["counts"]["context"],1)
        secret="PRIVATE_SENTENCE_123"
        r=diagnose([fact(secret)],case([]))
        self.assertNotIn(secret,json.dumps(r))
        self.assertEqual(r["counts"]["extra_exact"],1)


    def test_field_status_scope_independent(self):
        c=case([["features","x","user_action","confirmed","current"]])
        r=diagnose([fact(field="ai",status="tentative",scope="other")],c)
        self.assertEqual([r["counts"][k] for k in ("field","status","scope")],[1,1,1])
        self.assertEqual(r["counts"]["role"],0)

    def test_diagnostics_preserve_score_and_input(self):
        import copy
        from agentfit_ai.quote_evaluation import score
        c=case([["features","x","user_action","confirmed","current"]])
        pool=[fact(role="product_fact")]
        before=copy.deepcopy((pool,c))
        passed=score(pool,c)
        diagnose(pool,c)
        self.assertEqual((pool,c),before)
        self.assertEqual(score(pool,c),passed)

    def test_no_arbitrary_label_serialization(self):
        text="PRIVATE_LABEL_SENTENCE"
        r=diagnose([fact(text,field=text,role=text,status=text,scope=text)],case([]))
        self.assertNotIn(text,json.dumps(r))
