import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agentfit_ai import quote_evaluation as module

class ModelComparisonTests(unittest.TestCase):
    def test_model_reaches_transport_and_plan(self):
        for model in ("solar-mini4","solar-pro4"):
            with tempfile.TemporaryDirectory() as root:
                cases=Path(root)/"cases.json"
                cases.write_text(json.dumps([{"id":"test","document":"Meeting at noon.","expected":[]}]))
                output=Path(root)/"run"
                with patch.object(module,"CASES",cases), patch.object(module,"load_api_key",return_value="fake"), patch.object(module,"SectionAnalyzer") as factory:
                    def response(payload,names,**kwargs):
                        self.assertEqual(payload["model"],model)
                        text=json.loads(payload["messages"][1]["content"])
                        return ({"sections":[{"sectionId":s["sectionId"],"facts":[]} for s in text["sections"]]},model,1,1)
                    factory.return_value._send_payload.side_effect=response
                    with patch("sys.argv",["probe","--live","--model",model,"--output",str(output)]),contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(module.main(),1)  # One synthetic test row cannot pass six-case gate.
                    self.assertEqual(factory.call_args.kwargs["model"],model)
                    self.assertEqual(json.loads((output/"plan.json").read_text())["model"],model)
