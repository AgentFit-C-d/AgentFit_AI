"""A rejection must have one validated reason before it can affect a Profile."""
import copy
import json
import unittest

from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.candidate_split_review import review_candidates_separately
from agentfit_ai.profile import FIELDS
from agentfit_ai.solar import AnalysisError
from test_candidate_split_review import fixture, response


class CandidateRejectionReasonsTests(unittest.TestCase):
    def test_reasons_map_to_rejected_ids_and_preserve_supported_source(self):
        document, frozen, labels = fixture(3)
        reasons, calls = [], []
        def transport(payload, key, timeout):
            data = json.loads(payload['messages'][1]['content'])
            if 'selections' in data:
                self.assertEqual([row['value'] for row in data['selections']], ['Go'] * 3)
                return response({'checkedCandidateIds': ['C000','C001','C002'],
                    'wrongCandidateIds': ['C001','C002'], 'rejectionReasons': [
                        {'id':'C002','reason':'not_current'},
                        {'id':'C001','reason':'wrong_field'}]})
            self.assertEqual(data['confirmedValues']['backend'], ['Go'])
            return response({'checkedFields':list(FIELDS),'missingFields':[]})
        verdict = review_candidates_separately(document, frozen, labels, 'PRIVATE_KEY',
            transport=transport, reasoned_review=True, review_reasons=reasons, review_calls=calls)
        self.assertEqual(verdict, {'checkedFields':list(FIELDS),'missingFields':[],
                                 'wrongCandidateIds':['C001','C002']})
        projected = finalize_candidate_analysis(document, 'case', frozen, labels, verdict)
        self.assertEqual(projected['profile']['data']['backend'], ['Go'])
        self.assertEqual(projected['profile']['evidence']['backend'], [{'documentId':'case','start':0,'end':2}])
        self.assertEqual(projected['outcome'], 'needs_confirmation')
        self.assertEqual(reasons, [
            {'batch_index':1,'sub_batch_index':None,'id':'C002','reason':'not_current'},
            {'batch_index':1,'sub_batch_index':None,'id':'C001','reason':'wrong_field'}])
        self.assertNotIn('PRIVATE_KEY',json.dumps(reasons))
        self.assertNotIn('Go',json.dumps(reasons))
        self.assertTrue(all(row['validated'] for row in calls))

    def test_malformed_reasons_fail_before_source_coverage(self):
        document, frozen, labels = fixture(2)
        base = {'checkedCandidateIds':['C000','C001'], 'wrongCandidateIds':['C001'],
                'rejectionReasons':[{'id':'C001','reason':'not_current'}]}
        bads = [None, {}, [], [{'id':'C001','reason':'unknown'}],
                [{'id':'C000','reason':'not_current'}],
                [{'id':'T','reason':'not_current'}],
                [{'id':'C001','reason':'not_current'}]*2,
                [{'id':'C001','reason':[]}], [{'id':True,'reason':'wrong_field'}],
                [{'id':'C001','reason':'wrong_field','quote':'PRIVATE'}],
                [{'id':'C001'}], ['C001']]
        for bad in bads:
            collector, requests, traces = [], [], []
            def transport(payload, key, timeout):
                requests.append(payload)
                return response({**base, 'rejectionReasons':bad})
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                review_candidates_separately(document,frozen,labels,'fake',transport=transport,
                    reasoned_review=True,review_reasons=collector,review_calls=traces)
            self.assertEqual(len(requests),1)
            self.assertEqual(collector,[])
            self.assertFalse(traces[0]['validated'])

    def test_missing_reason_property_and_extra_top_level_property_fail(self):
        document, frozen, labels = fixture(1)
        for reply in [
            {'checkedCandidateIds':['C000'],'wrongCandidateIds':[]},
            {'checkedCandidateIds':['C000'],'wrongCandidateIds':[],'rejectionReasons':[], 'private':'text'}]:
            def transport(payload,key,timeout):
                return response(reply)
            with self.subTest(reply=reply), self.assertRaises((AnalysisError, ValueError)):
                review_candidates_separately(document,frozen,labels,'fake',transport=transport,reasoned_review=True)

    def test_explicit_false_and_collector_do_not_change_default_requests(self):
        document, frozen, labels = fixture(1)
        runs = []
        for options in ({}, {'reasoned_review':False, 'review_reasons':[]}):
            requests = []
            def transport(payload,key,timeout):
                requests.append(copy.deepcopy(payload))
                data = json.loads(payload['messages'][1]['content'])
                return response({'checkedCandidateIds':['C000'],'wrongCandidateIds':[]} if 'selections' in data
                                else {'checkedFields':list(FIELDS),'missingFields':[]})
            review_candidates_separately(document,frozen,labels,'fake',transport=transport,**options)
            runs.append(requests)
        self.assertEqual(runs[0],runs[1])
        self.assertNotIn('rejectionReasons',json.dumps(runs[1]))

    def test_bad_configuration_never_calls_provider(self):
        document,frozen,labels=fixture(1)
        for options in ({'reasoned_review':1},{'reasoned_review':'yes'},
                        {'reasoned_review':None},{'review_reasons':{}},{'review_reasons':()}):
            requests=[]
            def transport(*args):
                requests.append(args)
                raise AssertionError('provider must not be called')
            with self.subTest(options=options), self.assertRaises(ValueError):
                review_candidates_separately(document,frozen,labels,'fake',transport=transport,**options)
            self.assertEqual(requests,[])

    def test_prior_batch_diagnostics_survive_late_failure_without_projection(self):
        document,frozen,labels=fixture(21)
        reasons,requests=[],[]
        def transport(payload,key,timeout):
            data=json.loads(payload['messages'][1]['content'])
            requests.append(data)
            ids=[row['id'] for row in data['selections']]
            return response({'checkedCandidateIds':ids,'wrongCandidateIds':[ids[0]],
                             'rejectionReasons':[{'id':ids[0],'reason':'not_product_fact'}] if len(ids)==20 else []})
        with self.assertRaises(ValueError):
            review_candidates_separately(document,frozen,labels,'fake',transport=transport,
                                         reasoned_review=True,review_reasons=reasons)
        self.assertEqual(len(requests),2)
        self.assertEqual(reasons,[{'batch_index':1,'sub_batch_index':None,
                                  'id':'C000','reason':'not_product_fact'}])

    def test_every_batch_is_checked_without_extra_calls(self):
        document,frozen,labels=fixture(21)
        reasons,requests=[],[]
        def transport(payload,key,timeout):
            data=json.loads(payload['messages'][1]['content'])
            requests.append(data)
            if 'selections' in data:
                ids=[row['id'] for row in data['selections']]
                return response({'checkedCandidateIds':ids,'wrongCandidateIds':[ids[-1]],
                                 'rejectionReasons':[{'id':ids[-1],'reason':'insufficient_evidence'}]})
            return response({'checkedFields':list(FIELDS),'missingFields':[]})
        result=review_candidates_separately(document,frozen,labels,'fake',transport=transport,
                                           reasoned_review=True,review_reasons=reasons)
        self.assertEqual(result['wrongCandidateIds'],['C019','C020'])
        self.assertEqual([row['batch_index'] for row in reasons],[1,2])
        self.assertEqual(len(requests),3)

    def test_empty_candidates_only_call_unchanged_coverage(self):
        requests=[]
        def transport(payload,key,timeout):
            requests.append(payload)
            return response({'checkedFields':list(FIELDS),'missingFields':['features']})
        result=review_candidates_separately('private document',{'candidates':[],'rejected':[]},[],
            'fake',transport=transport,reasoned_review=True)
        self.assertEqual(result['wrongCandidateIds'],[])
        self.assertEqual(len(requests),1)
        self.assertNotIn('rejectionReasons',json.dumps(requests))
