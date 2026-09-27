import unittest
from agentfit_ai.atomic_verdict import atomic_schema, classify_atomic, validate_verdicts, LABELS
from agentfit_ai.anchored_candidates import units, validate_quotes
from agentfit_ai.profile import ARRAY_FIELDS
from agentfit_ai.solar import AnalysisError, _json

def pool_for(doc,quotes):
    batch=units(doc)
    reply={"units":[{"unitId":u.id,"quotes":[q for q in quotes if q in u.text]} for u in batch]}
    return validate_quotes(reply,batch,0,expand_occurrences=True)

class AtomicVerdictTests(unittest.TestCase):
    def test_all_labels_schema_and_profile_mapping(self):
        self.assertEqual(len(LABELS),18)
        pool=pool_for("Fact",["Fact"])
        schema=atomic_schema(pool)
        self.assertEqual(set(schema["properties"]["decisions"]["properties"]["F0001"]["enum"]),set(LABELS))
        self.assertFalse(schema["properties"]["decisions"]["additionalProperties"])
        for label in LABELS:
            if label in ("omit","conflict"):continue
            profile=classify_atomic({"decisions":{"F0001":label}},pool,"Fact","test")
            field=label.split(":")[1]
            if field.startswith("features_"):field="features"
            expected=[] if label.startswith("absent:") else ["Fact"] if field in ARRAY_FIELDS else "Fact"
            self.assertEqual(profile["data"][field],expected,label)
            self.assertEqual(profile["evidence"][field],[{"documentId":"test","start":0,"end":4}],label)

    def test_shape_validated_before_conflict_and_unknown_labels_rejected(self):
        pool=pool_for("A B",["A","B"])
        for decisions in ({},{"F0001":"omit"},{"F0001":"conflict","F0002":"bad"},
                          {"F0001":"omit","F0002":{}},{"F0001":"omit","F0002":"omit","F0003":"omit"}):
            with self.assertRaises(AnalysisError) as error:validate_verdicts({"decisions":decisions},pool)
            self.assertEqual(error.exception.code,"ANCHORED_JUDGMENT")
        with self.assertRaises(AnalysisError):_json(b'{"decisions":{"F0001":"omit","F0001":"conflict"}}')

    def test_conflict_fails_atomically_and_omit_does_not_become_absence(self):
        pool=pool_for("A B",["A","B"])
        with self.assertRaises(AnalysisError) as error:
            classify_atomic({"decisions":{"F0001":"value:ai","F0002":"conflict"}},pool,"A B","test")
        self.assertEqual(error.exception.code,"SEMANTIC_REJECTED")
        result=classify_atomic({"decisions":{"F0001":"omit","F0002":"omit"}},pool,"A B","test")
        self.assertTrue(all(v is None for v in result["data"].values()))
        self.assertTrue(all(not e for e in result["evidence"].values()))

    def test_existing_duplicate_count_and_absence_conflict_guards(self):
        for doc,quotes,labels,reason in (
            ("A A",["A"],["value:ai","value:ai"],"DUPLICATE_VALUE"),
            ("A B",["A","B"],["value:database","value:database"],"SELECTED_COUNT"),
            ("A B",["A","B"],["value:ai","absent:ai"],"CONFLICTING_FACTS")):
            pool=pool_for(doc,quotes)
            with self.assertRaises(AnalysisError) as error:
                classify_atomic({"decisions":dict(zip([p["id"] for p in pool],labels))},pool,doc,"test")
            self.assertEqual(error.exception.merge_detail["reason"],reason)

    def test_pipeline_initial_and_semantic_repair_share_atomic_contract(self):
        from unittest.mock import Mock
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        from test_staged_analysis import response
        from test_semantic_review import verdict
        seen=[]
        def transport(payload,*args):
            schema=payload["response_format"]["json_schema"]["schema"]
            props=schema["properties"]
            if "units" in props:return response({"units":[{"unitId":"U0001","quotes":["Raven"]}]})
            if "decisions" in props:
                seen.append(schema)
                return response({"decisions":{"F0001":"omit" if len(seen)==1 else "value:ai"}})
            return response(verdict([{"field":"ai","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}])
                if len(seen)==1 else verdict())
        analyzer=AnchoredAnalyzer("synthetic-key",transport=Mock(side_effect=transport),prompt_revision="v2",
            candidate_occurrences=True,atomic_verdict=True)
        result=analyzer.analyze("Raven","test")
        self.assertEqual(result.profile["data"]["ai"],["Raven"])
        self.assertEqual(result.provider_calls,5)
        self.assertEqual(seen[0],seen[1])
        self.assertEqual(seen[0]["properties"]["decisions"]["properties"]["F0001"]["type"],"string")
        self.assertIn("atomic-verdict-v1",result.prompt_version)
        for config in ({},{"prompt_revision":"v2"},{"prompt_revision":"v2","candidate_occurrences":True,"selected_constraints":True}):
            with self.assertRaises(ValueError):AnchoredAnalyzer("synthetic-key",atomic_verdict=True,**config)
