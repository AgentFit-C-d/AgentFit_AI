"""The field-local reviewer runs through the real pipeline and shared budget."""
import json
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_analysis_pipeline import analyze_nvidia_candidates
from agentfit_ai.candidate_first_profile import CandidatePipelineError
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from tests.test_capability_candidate_pipeline import Fixture, MODEL, NVIDIA
from tests.test_candidate_split_review import response

class FieldFixture(Fixture):
    def __init__(self, *, late_invalid=False, unavailable=False, foreign=False):
        super().__init__()
        self.coverage=[]
        self.late_invalid,self.unavailable,self.foreign=late_invalid,unavailable,foreign
        self.extraction_count=0

    def extractor(self,*args,**kwargs):
        self.extraction_count+=1
        return super().extractor(*args,**kwargs)

    def transport(self,payload,key,timeout):
        name=payload['response_format']['json_schema']['name']
        if name not in ('agentfit_field_candidate_review','agentfit_field_source_coverage'):
            return super().transport(payload,key,timeout)
        self.names.append(name)
        data=json.loads(payload['messages'][1]['content'])
        if name=='agentfit_field_candidate_review':
            if self.unavailable:
                raise AnalysisError('PROVIDER_UNAVAILABLE')
            wrong=['C003'] if self.foreign else []
            body={'checkedCandidateIds':[c['id'] for c in data['selections']],
                  'wrongCandidateIds':wrong,
                  'rejectionReasons':[{'id':i,'reason':'not_current'} for i in wrong]}
        else:
            self.coverage.append(data['targetField'])
            body={'field':data['targetField'],
                  'missing':1 if self.late_invalid and data['targetField']==FIELDS[-1] else False}
        return response(body,model=payload['model'])

class FieldPipelineTests(unittest.TestCase):
    def test_all_ten_fields_reviewed_before_profile_with_same_grounded_evidence(self):
        case,calls=FieldFixture(),[]
        result=case.run(capability_candidates=True,field_local_review=True,call_trace=calls)
        self.assertEqual(list(FIELDS),case.coverage)
        self.assertEqual(['search'],result['profile']['data']['features'])
        self.assertEqual([{'documentId':'DOC','start':17,'end':23}],result['profile']['evidence']['features'])
        self.assertEqual(4,result['candidateCount'])
        self.assertEqual(14,len(calls))
        self.assertEqual(['COVERAGE_REVIEW_FAILED']*12,[r['stage'] for r in calls[2:]])

    def test_default_false_is_the_existing_mixed_review(self):
        cases=[FieldFixture(),FieldFixture()]
        results=[cases[0].run(capability_candidates=True),
                 cases[1].run(capability_candidates=True,field_local_review=False)]
        self.assertEqual(results[0],results[1])
        self.assertEqual(cases[0].names,cases[1].names)
        self.assertTrue(all('agentfit_field_source_coverage' not in c.names for c in cases))

    def test_invalid_option_is_rejected_before_extraction_and_network(self):
        for value in (None,0,1,'true',[],{}):
            case=FieldFixture()
            with self.subTest(value=value),self.assertRaises(ValueError):
                case.run(field_local_review=value)
            self.assertEqual(0,case.extraction_count)
            self.assertEqual([],case.names)

    def test_last_field_failure_never_returns_partial_profile(self):
        case,calls=FieldFixture(late_invalid=True),[]
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(field_local_review=True,capability_candidates=True,call_trace=calls)
        self.assertEqual('COVERAGE_REVIEW_FAILED',caught.exception.stage)
        self.assertEqual(list(FIELDS),case.coverage)
        self.assertEqual(14,len(calls))

    def test_foreign_id_is_rejected_before_any_coverage_call(self):
        case=FieldFixture(foreign=True)
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(field_local_review=True,capability_candidates=True)
        self.assertEqual('COVERAGE_REVIEW_FAILED',caught.exception.stage)
        self.assertEqual([],case.coverage)
        self.assertEqual(3,len(case.names))

    def test_field_calls_cannot_bypass_shared_budget(self):
        case,calls=FieldFixture(),[]
        with self.assertRaises(CandidatePipelineError) as caught:
            case.run(field_local_review=True,capability_candidates=True,max_calls=10,call_trace=calls)
        self.assertEqual(('COVERAGE_REVIEW_FAILED','CALL_BUDGET_EXCEEDED'),
                         (caught.exception.stage,caught.exception.detail))
        self.assertEqual(10,len(calls))
        self.assertLess(len(case.coverage),10)

    def test_nvidia_wrapper_forwards_option_and_first_provider_error_stops(self):
        for unavailable in (False,True):
            case,calls=FieldFixture(unavailable=unavailable),[]
            with patch('agentfit_ai.langextract_solar_trial.extract_candidates',case.extractor):
                def run():
                    return analyze_nvidia_candidates(case.document,'DOC',NVIDIA,review_model=MODEL,
                        nvidia_transport=case.transport,capability_candidates=True,
                        field_local_review=True,call_trace=calls)
                if unavailable:
                    with self.assertRaises(CandidatePipelineError) as caught:
                        run()
                    self.assertEqual(('COVERAGE_REVIEW_FAILED','PROVIDER_UNAVAILABLE'),
                                     (caught.exception.stage,caught.exception.provider_code))
                    self.assertEqual(3,len(calls))
                    self.assertEqual([],case.coverage)
                else:
                    self.assertEqual(['search'],run()['profile']['data']['features'])
                    self.assertEqual(list(FIELDS),case.coverage)
            self.assertEqual({'nvidia'},{r['provider'] for r in calls})
            self.assertTrue(all(r['attempt']==1 for r in calls))

if __name__=='__main__':
    unittest.main()
