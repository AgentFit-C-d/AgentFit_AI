import copy
import unittest
from agentfit_ai.draft_readiness import assess
from agentfit_ai.profile import FIELDS

def rows():
    return [dict(document_id=str(i),run=r,elapsed_seconds=1,failed=False,
        critical_errors=0,fields={f:dict(tp=10,fp=0,fn=0,evidence_valid=10) for f in FIELDS},
        review=dict(edits=0,seconds=30) if r==0 else None) for i in range(10) for r in range(3)]

class ReadinessTests(unittest.TestCase):
    def test_complete(self):
        self.assertTrue(assess(rows())["passed"])
    def test_empty_and_small_never_pass(self):
        self.assertFalse(assess([])["passed"])
        self.assertFalse(assess(rows()[:3])["passed"])
    def test_missing_human_review(self):
        data=rows();data[0]["review"]=None
        self.assertFalse(assess(data)["passed"])
    def test_duplicate_rejected(self):
        data=rows();data.append(copy.deepcopy(data[0]))
        with self.assertRaises(ValueError):assess(data)
    def test_failure_counted_as_misses(self):
        data=rows();data[0]["failed"]=True
        for field in data[0]["fields"].values():
            field.update(tp=0,fn=10,evidence_valid=0)
        self.assertFalse(assess(data)["passed"])
        data[0]["fields"]["ai"]["tp"]=1
        with self.assertRaises(ValueError):assess(data)
    def test_evidence_and_critical_errors(self):
        for key in ("evidence","critical"):
            data=rows()
            if key=="evidence":data[0]["fields"]["ai"]["evidence_valid"]=9
            else:data[0]["critical_errors"]=1
            self.assertFalse(assess(data)["passed"])
    def test_invalid_numeric(self):
        for v in (True,-1,float("nan"),float("inf")):
            data=rows();data[0]["elapsed_seconds"]=v
            with self.assertRaises(ValueError):assess(data)
    def test_unassessed_field(self):
        data=rows()
        for row in data:row["fields"]["ai"]=dict(tp=0,fp=0,fn=0,evidence_valid=0)
        self.assertFalse(assess(data)["passed"])

    def test_bad_field_not_hidden_by_other_fields(self):
        data=rows()
        for row in data:row["fields"]["ai"].update(tp=9,fp=1,fn=1)
        result=assess(data)
        self.assertTrue(result["checks"]["overall_quality"])
        self.assertFalse(result["checks"]["field_quality"])
        self.assertFalse(result["passed"])

    def test_review_and_latency_limits(self):
        data=rows()
        for row in data:
            row["elapsed_seconds"]=61
            if row["run"]==0:row["review"]={"edits":11,"seconds":301}
        result=assess(data)
        for key in ("edit_rate","review_time","latency"):
            self.assertFalse(result["checks"][key])

    def test_gold_cannot_change_between_repetitions(self):
        data=rows();data[1]["fields"]["features"]["fn"]=1
        with self.assertRaises(ValueError):assess(data)
