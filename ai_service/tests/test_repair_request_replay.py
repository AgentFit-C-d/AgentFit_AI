import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agentfit_ai import repair_request_replay as probe
from test_source_repair import fact, reply

class RepairRequestReplayTests(unittest.TestCase):
    def test_exact_request_replay_and_no_raw_persistence(self):
        self.check_replay()

    def test_pro4_changes_only_model(self):
        self.check_replay("solar-pro4")

    def check_replay(self,replay_model=None):
        doc="모델 Orion은 채택하지 않는다. 서비스 운영 모델로 Lyra를 확정했다."
        sections=probe.units(doc)
        previous=probe.validate_profile(doc,"N-004",{"data":dict.fromkeys(probe.FIELDS),"evidence":{f:[] for f in probe.FIELDS}})
        content={"document":doc,"requestedFields":["ai"],"previous":previous,
            "issues":[{"field":"ai","kind":"missing","itemIndex":None,"evidenceLineIds":[1]}],
            "units":[{"unitId":s.id,"text":s.text,"headingPath":list(s.path)} for s in sections]}
        payload={"model":"solar-mini4","messages":[{"content":probe.SOURCE_REPAIR_PROMPT+probe.REPAIR_EXAMPLES+probe.VALUE_BOUNDARY_V2+probe.STATE_GROUNDING_V2},
            {"content":json.dumps(content,ensure_ascii=False)}],
            "response_format":{"json_schema":{"schema":probe.repair_schema(["ai"],sections)}}}
        sent=[]
        class Fake:
            def _send_payload(self,p,names,**kwargs):
                sent.append(copy.deepcopy(p))
                kwargs.get("_trace",{})["raw"]=b"PRIVATE_RESPONSE_SENTINEL"
                return reply("ai",[fact("Lyra","operating_model",unitId=sections[0].id)]),"solar-mini4",10,20
        fake=Fake()
        def observe(a,*args):
            a._send_payload(payload,("repairs",),_trace={},timeout=40)
            return {"passed":True}
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"result"
            argv=["probe","--live","--output",str(output)]
            if replay_model:argv.extend(["--replay-model",replay_model])
            with patch.object(probe,"load_api_key",return_value="PRIVATE_KEY_SENTINEL"),patch.object(probe,"AnchoredAnalyzer",return_value=fake),patch.object(probe,"observe_run",side_effect=observe),patch.object(probe.time,"sleep"),patch.object(sys,"argv",argv),patch("sys.stdout",new=io.StringIO()):
                self.assertEqual(probe.main(),0)
            stored="".join(p.read_text() for p in output.iterdir())
            self.assertNotIn("PRIVATE_RESPONSE_SENTINEL",stored)
            self.assertNotIn("PRIVATE_KEY_SENTINEL",stored)
            self.assertNotIn(doc,stored)
            result=json.loads((output/"results.json").read_text())
            self.assertTrue(all(result["comparison"].values()))
            self.assertEqual(len(result["replays"]),3)
            self.assertEqual(len(sent),4)
            self.assertEqual(sent[0],payload)
            expected=copy.deepcopy(payload)
            if replay_model:expected["model"]=replay_model
            self.assertTrue(all(p==expected for p in sent[1:]))
            self.assertEqual(result["original_request_timeouts"],[40])
