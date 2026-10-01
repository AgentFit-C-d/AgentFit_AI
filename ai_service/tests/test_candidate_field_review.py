"""Field boundaries and full coverage are enforced independently of model quality."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from agentfit_ai.candidate_field_review import review_candidates_by_field
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from tests.test_candidate_split_review import response

MODEL='deepseek-ai/deepseek-v4.1-flash'
KEY='unit-only-credential'

def fixture(fields=('features','deployment','features'), statuses=None):
    document=' '.join(['same']*len(fields)) or 'No selected facts.'
    frozen={'candidates':[{'id':f'C{i:03}','start':i*5,'end':i*5+4} for i in range(len(fields))], 'rejected':[]}
    labels=[{'id':c['id'],'field':field,'status':statuses[i] if statuses else 'confirmed'}
            for i,(c,field) in enumerate(zip(frozen['candidates'],fields))]
    return document,frozen,labels

class Model:
    def __init__(self, *, reject=(), missing=(), mutate=None):
        self.requests=[]
        self.reject=set(reject)
        self.missing=set(missing)
        self.mutate=mutate

    def __bool__(self):
        return False

    def __call__(self,payload,key,timeout):
        self.requests.append(deepcopy(payload))
        data=json.loads(payload['messages'][1]['content'])
        if 'selections' in data:
            ids=[r['id'] for r in data['selections']]
            wrong=[i for i in ids if i in self.reject]
            body={'checkedCandidateIds':ids,'wrongCandidateIds':wrong,
                  'rejectionReasons':[{'id':i,'reason':'wrong_field'} for i in wrong]}
        else:
            body={'field':data['targetField'],'missing':data['targetField'] in self.missing}
        if self.mutate:
            self.mutate(data,body)
        return response(body,model=payload['model'])

def request_data(sender):
    return [json.loads(p['messages'][1]['content']) for p in sender.requests]

class FieldReviewTests(unittest.TestCase):
    def test_each_confirmed_occurrence_once_and_feature_prompt_is_field_local(self):
        doc,frozen,labels=fixture(statuses=['confirmed','confirmed','negated'])
        sender=Model(missing=['project_name'])
        calls,reasons=[],[]
        result=review_candidates_by_field(doc,frozen,labels,KEY,transport=sender,
                                          review_calls=calls,review_reasons=reasons)
        data=request_data(sender)
        batches=[r for r in data if 'selections' in r]
        self.assertEqual(['deployment','features'],[r['targetField'] for r in batches])
        self.assertEqual(['C001','C000'],[c['id'] for r in batches for c in r['selections']])
        self.assertEqual([5,0],[c['start'] for r in batches for c in r['selections']])
        for payload,row in zip(sender.requests,data):
            self.assertEqual(row['targetField']=='features',
                'Runtime purpose clarification.' in payload['messages'][0]['content'])
            if 'selections' in row:
                self.assertEqual({row['targetField']},{c['field'] for c in row['selections']})
        coverage=[r for r in data if 'selections' not in r]
        self.assertEqual(list(FIELDS),[r['targetField'] for r in coverage])
        self.assertEqual({'checkedFields':list(FIELDS),'missingFields':['project_name'],'wrongCandidateIds':[]},result)
        self.assertEqual(12,len(calls))
        self.assertTrue(all(c['validated'] for c in calls))
        self.assertNotIn(doc,json.dumps(calls))
        self.assertNotIn(KEY,json.dumps(calls))

    def test_review_excludes_wrong_ids_before_field_coverage_and_deduplicates_values(self):
        doc,frozen,labels=fixture(('features','features','features'))
        sender=Model(reject=['C000'])
        reasons=[]
        result=review_candidates_by_field(doc,frozen,labels,KEY,transport=sender,review_reasons=reasons)
        coverage=next(d for d in request_data(sender) if d.get('targetField')=='features' and 'confirmedValues' in d)
        self.assertEqual(['same'],coverage['confirmedValues'])
        self.assertEqual(['C000'],result['wrongCandidateIds'])
        self.assertEqual([{'field':'features','batch_index':1,'id':'C000','reason':'wrong_field'}],reasons)
        self.assertEqual(['confirmed']*3,[r['status'] for r in labels])

    def test_empty_candidates_still_check_all_ten_fields(self):
        sender=Model(missing=['project_name','features'])
        result=review_candidates_by_field(*fixture(()),KEY,transport=sender)
        self.assertEqual(10,len(sender.requests))
        self.assertEqual(list(FIELDS),[d['targetField'] for d in request_data(sender)])
        self.assertTrue(all(d['confirmedValues']==[] for d in request_data(sender)))
        self.assertEqual(['project_name','features'],result['missingFields'])

    def test_foreign_id_reordered_check_or_invalid_reason_stops_before_coverage(self):
        def foreign(data,body):
            body['wrongCandidateIds']=['C002']
            body['rejectionReasons']=[{'id':'C002','reason':'wrong_field'}]
        def reversed_ids(data,body):
            body['checkedCandidateIds'].reverse()
        def invalid_reason(data,body):
            body['wrongCandidateIds']=['C000']
            body['rejectionReasons']=[{'id':'C000','reason':'PRIVATE MODEL TEXT'}]
        for mutate in (foreign,reversed_ids,invalid_reason):
            sender=Model(mutate=mutate)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):
                review_candidates_by_field(*fixture(('frontend','frontend','features')),KEY,transport=sender)
            self.assertEqual(1,len(sender.requests))

    def test_last_field_invalid_boolean_field_or_extra_key_never_returns_partial(self):
        for bad in ('field',1,'false','extra'):
            def mutate(data,body):
                if data['targetField']==FIELDS[-1]:
                    if bad=='field': body['field']='features'
                    elif bad=='extra': body['private']='untrusted response'
                    else: body['missing']=bad
            sender=Model(mutate=mutate)
            with self.subTest(bad=bad),self.assertRaises((ValueError,AnalysisError)):
                review_candidates_by_field(*fixture(()),KEY,transport=sender)
            self.assertEqual(10,len(sender.requests))

    def test_falsey_transport_is_used_and_invalid_inputs_make_no_calls(self):
        sender=Model()
        with patch('agentfit_ai.operation_candidates.post_nvidia',side_effect=AssertionError('no real network')):
            review_candidates_by_field(*fixture(()),KEY,transport=sender)
            self.assertEqual(10,len(sender.requests))
            for kwargs in ({'transport':False},{'review_calls':{}},{'review_reasons':{}},{'review_model':'solar-pro4'}):
                with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                    review_candidates_by_field(*fixture(()),KEY,**kwargs)
        doc,frozen,labels=fixture()
        labels[0]['id']='not-a-candidate'
        sender=Model()
        with self.assertRaises(ValueError):
            review_candidates_by_field(doc,frozen,labels,KEY,transport=sender)
        self.assertEqual([],sender.requests)

    def test_provider_error_stops_and_diagnostics_do_not_keep_error_text(self):
        seen,calls=[],[]
        def fail(*args):
            seen.append(1)
            raise AnalysisError('PROVIDER_UNAVAILABLE')
        with self.assertRaises(AnalysisError):
            review_candidates_by_field(*fixture(()),KEY,transport=fail,review_calls=calls)
        self.assertEqual([1],seen)
        self.assertEqual('PROVIDER_UNAVAILABLE',calls[0]['error'])
        self.assertFalse(calls[0]['validated'])
        self.assertNotIn(KEY,json.dumps(calls))

    def test_worst_distribution_has_31_calls_and_every_id_exactly_once(self):
        fields=[FIELDS[0]]*231+list(FIELDS[1:])
        self.assertEqual(240,len(fields))
        sender=Model()
        review_candidates_by_field(*fixture(fields),KEY,transport=sender)
        data=request_data(sender)
        batches=[r for r in data if 'selections' in r]
        self.assertEqual(31,len(data))
        self.assertEqual(21,len(batches))
        self.assertTrue(all(1<=len(r['selections'])<=20 for r in batches))
        ids=[c['id'] for r in batches for c in r['selections']]
        self.assertEqual([f'C{i:03}' for i in range(240)],ids)

if __name__=='__main__':
    unittest.main()
