import unittest
from copy import deepcopy
from unittest.mock import Mock
from agentfit_ai.source_repair import apply_repairs
from agentfit_ai.anchored_candidates import units
from agentfit_ai.profile import FIELDS,validate_profile
from agentfit_ai.solar import AnalysisError
from agentfit_ai.anchored_analysis import AnchoredAnalyzer
from test_staged_analysis import response
from test_semantic_review import verdict

def empty(document):
 return validate_profile(document,"doc",{"data":dict.fromkeys(FIELDS),"evidence":{f:[] for f in FIELDS}})
def fact(quote,role="user_action",status="confirmed",unitId="U0001",context=None):
 return dict(unitId=unitId,quote=quote,context=context,role=role,status=status,scope="current")
def reply(field,facts):
 return {"repairs":{field:{"facts":facts}}}

class SourceRepairTests(unittest.TestCase):
 def test_new_source_facts_split_actions_and_preserve_other_fields(self):
  doc="Alpha: search, reserve"
  old=empty(doc);old["data"]["project_name"]="Alpha";old["sources"]["project_name"]="DOCUMENT"
  old["evidence"]["project_name"]=[{"documentId":"doc","start":0,"end":5}];old["unknownFields"].remove("project_name")
  before=deepcopy(old)
  result=apply_repairs(doc,"doc",old,units(doc),("features",),reply("features",[fact("search"),fact("reserve")]))
  self.assertEqual(result["data"]["features"],["search","reserve"])
  self.assertEqual(result["data"]["project_name"],"Alpha")
  self.assertEqual(result["evidence"]["project_name"],old["evidence"]["project_name"])
  self.assertEqual(old,before)

 def test_absence_and_unknown_remain_distinct(self):
  doc="No external integrations."
  old=empty(doc)
  result=apply_repairs(doc,"doc",old,units(doc),("external_integrations",),reply("external_integrations",[fact(doc,"named_service","absent")]))
  self.assertEqual(result["data"]["external_integrations"],[])
  self.assertEqual(result["sources"]["external_integrations"],"DOCUMENT")
  result=apply_repairs(doc,"doc",old,units(doc),("external_integrations",),reply("external_integrations",[]))
  self.assertIsNone(result["data"]["external_integrations"])
  self.assertEqual(result["evidence"]["external_integrations"],[])

 def test_unrequested_fields_and_ambiguous_or_invented_quotes_fail_atomically(self):
  doc="search search"
  old=empty(doc);before=deepcopy(old)
  for payload in (reply("ai",[]),reply("features",[fact("search")]),reply("features",[fact("invented")]),
                  reply("features",[fact(doc,unitId="U9999")])):
   with self.subTest(payload=payload):
    with self.assertRaises(AnalysisError):apply_repairs(doc,"doc",old,units(doc),("features",),payload)
    self.assertEqual(old,before)

 def test_context_disambiguates_and_excluded_status_not_selected(self):
  doc="first search; next search"
  result=apply_repairs(doc,"doc",empty(doc),units(doc),("features",),reply("features",[fact("search",context="next search")]))
  self.assertEqual(result["evidence"]["features"][0]["start"],19)
  result=apply_repairs(doc,"doc",empty(doc),units(doc),("features",),reply("features",[fact("search",status="tentative",context="next search")]))
  self.assertIsNone(result["data"]["features"])

 def test_duplicate_and_invalid_role_rejected(self):
  doc="search"
  for facts in ([fact(doc),fact(doc)],[fact(doc,role="operating_model")]):
   with self.assertRaises(AnalysisError):apply_repairs(doc,"doc",empty(doc),units(doc),("features",),reply("features",facts))

 def test_empty_pool_can_be_repaired_and_rechecked_within_four_calls(self):
  doc="search"
  issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
  t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
                     response(verdict(issues)),response(reply("features",[fact("search")])),response(verdict())])
  r=AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True).analyze(doc,"doc")
  self.assertEqual(r.profile["data"]["features"],["search"])
  self.assertEqual(r.provider_calls,4)
  self.assertEqual(r.repaired_fields,("features",))
  self.assertEqual(r.diagnostics["calls"][2]["stage"],"source_repair")
  self.assertFalse(r.first_pass_validated)

 def test_missing_unchanged_fails_before_recheck(self):
  issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
  t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
                     response(verdict(issues)),response(reply("features",[])),response(verdict())])
  with self.assertRaises(AnalysisError) as cm:
   AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True).analyze("search","doc")
  self.assertEqual(cm.exception.code,"ANCHORED_MISSING_CANDIDATE")
  self.assertEqual(t.call_count,3)

 def test_two_batches_and_existing_judgment_stay_within_six_calls(self):
  import json
  issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[4]}]
  reviews=[verdict(issues),verdict()]
  def transport(payload,*args):
   schema=payload["response_format"]["json_schema"]["schema"]["properties"]
   content=json.loads(payload["messages"][1]["content"]) if "checkedFields" not in schema else None
   if "units" in schema:
    return response({"units":[{"unitId":u["unitId"],"quotes":["Alpha"] if "Alpha" in u["text"] else []} for u in content["units"]]})
   if "decisions" in schema:
    return response({"decisions":{c["id"]:{"field":"project_name","role":"product_fact","status":"confirmed","scope":"current","decision":"selected"} for c in content["candidates"]}})
   if "repairs" in schema:
    unit=next(u for u in content["units"] if "search" in u["text"])
    return response(reply("features",[fact("search",unitId=unit["unitId"])]))
   return response(reviews.pop(0))
  t=Mock(side_effect=transport)
  r=AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True).analyze("# Name\nAlpha\n# Actions\nsearch","doc")
  self.assertEqual(r.provider_calls,6)
  self.assertEqual(r.profile["data"]["project_name"],"Alpha")
  self.assertEqual(r.profile["data"]["features"],["search"])

 def test_recheck_rejects_wrong_repair(self):
  issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
  recheck=[{"field":"features","kind":"wrong_role","itemIndex":0,"evidenceLineIds":[1]}]
  t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
                     response(verdict(issues)),response(reply("features",[fact("search")])),response(verdict(recheck))])
  with self.assertRaises(AnalysisError) as cm:
   AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True).analyze("search","doc")
  self.assertEqual(cm.exception.code,"SEMANTIC_REJECTED")
  self.assertEqual(cm.exception.diagnostics["calls"][2]["outcome"],"semantic_failed")

 def test_repair_consuming_deadline_cannot_return_success(self):
  now=[0.0]
  issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
  responses=[{"units":[{"unitId":"U0001","quotes":[]}]},verdict(issues),reply("features",[fact("search")])]
  calls=[]
  def transport(payload,*args):
   calls.append(payload)
   if len(calls)==3:now[0]=61.0
   return response(responses[len(calls)-1])
  with self.assertRaises(AnalysisError) as cm:
   AnchoredAnalyzer("synthetic-key",transport=transport,clock=lambda:now[0],source_repair=True).analyze("search","doc")
  self.assertEqual(cm.exception.code,"ANALYSIS_DEADLINE")
  self.assertEqual(len(calls),3)

 def test_unchanged_repair_is_retained_as_failure_with_target_fields(self):
  issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
  t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
                     response(verdict(issues)),response(reply("features",[]))])
  store=Mock()
  with self.assertRaises(AnalysisError) as cm:
   AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True,diagnostics_store=store).analyze("search","doc")
  self.assertEqual(cm.exception.repaired_fields,("features",))
  self.assertEqual(cm.exception.diagnostics["calls"][2]["outcome"],"semantic_failed")
  self.assertEqual([r["call"] for r in store.write.call_args.args[1]],[2,3])

 def test_repair_and_retained_fields_share_candidate_limit(self):
  values=[f"item{i}" for i in range(121)]
  doc="|".join(values);old=empty(doc)
  for index,field in enumerate(("frontend","backend","ai","features")):
   selected=values[index*30:(index+1)*30]
   old["data"][field]=selected;old["sources"][field]="DOCUMENT"
   old["evidence"][field]=[{"documentId":"doc","start":doc.index(v+"|"),"end":doc.index(v+"|")+len(v)} for v in selected]
   old["unknownFields"].remove(field)
  with self.assertRaises(AnalysisError):
   apply_repairs(doc,"doc",old,units(doc),("external_integrations",),reply("external_integrations",[fact("item120","named_service")]))

 def test_examples_option_is_sent_only_to_repair(self):
  missing={"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}
  payloads=[]
  def transport(payload,*args):
   payloads.append(payload)
   values=[{"units":[{"unitId":"U0001","quotes":[]}]},verdict([missing]),reply("features",[fact("search")]),verdict()]
   return response(values[len(payloads)-1])
  r=AnchoredAnalyzer("synthetic-key",transport=transport,source_repair=True,repair_examples=True).analyze("search","doc")
  self.assertEqual(r.profile["data"]["features"],["search"])
  self.assertIn("repair-examples-v1",r.prompt_version)
  self.assertIn("Helios",payloads[2]["messages"][0]["content"])
  self.assertNotIn("Helios",payloads[0]["messages"][0]["content"])
  self.assertNotIn("Helios",payloads[1]["messages"][0]["content"])

class ValueBoundaryOptionTests(unittest.TestCase):
    def test_requires_source_repair_and_preserves_default(self):
        from agentfit_ai.anchored_analysis import AnchoredAnalyzer
        with self.assertRaises(ValueError):
            AnchoredAnalyzer("synthetic-key",repair_value_boundary=True)
        from unittest.mock import Mock
        from test_staged_analysis import response
        from test_semantic_review import verdict
        for enabled in (False,True):
            issues=[{"field":"features","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}]
            t=Mock(side_effect=[response({"units":[{"unitId":"U0001","quotes":[]}]}),
                response(verdict(issues)),response(reply("features",[fact("search")])),response(verdict())])
            result=AnchoredAnalyzer("synthetic-key",transport=t,source_repair=True,repair_value_boundary=enabled).analyze("search","doc")
            self.assertEqual("value-boundary-v2" in result.prompt_version,enabled)
            prompts=[c.args[0]["messages"][0]["content"] for c in t.call_args_list]
            self.assertEqual("최종 사용자에게 표시할 값" in prompts[2],enabled)
            self.assertNotIn("최종 사용자에게 표시할 값",prompts[0])
            self.assertEqual(result.profile["data"]["features"],["search"])
