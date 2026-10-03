"""Offline server-rule regression, never a model-accuracy evaluation."""
from copy import deepcopy
from itertools import product
import unittest

from agentfit_ai.candidate_semantic_assessment import (
    AXES, STATUSES, _decision, validate_assessments, semantic_labels, assessment_payload,
)
from agentfit_ai.candidate_mention_roles import MENTION_KINDS, MENTION_ROLE_INSTRUCTION
from agentfit_ai.candidate_confirmation import validate_candidate_confirmation
from agentfit_ai.profile import FIELDS
from review_preservation_fixture import offline
from tentative_proposed_fixture import case, load, legacy_decision, unreviewed_boundary

ROLES={f:'product_operation' if f=='features' else 'external_service' if f=='external_integrations' else 'other' for f in FIELDS}


class TentativeProposedTests(unittest.TestCase):
    def setUp(self):
        guard=offline(); guard.__enter__()
        self.addCleanup(guard.__exit__,None,None,None)
        self.document,self.frozen,self.raw,self.before=case('D2','A')
        self.candidate=next(c for c in self.frozen['candidates'] if c['id']=='C006')
        self.occurrence=deepcopy(next(r for r in self.raw if r['id']==self.candidate['id']))
        self.legacy=legacy_decision()

    def checked(self,**changes):
        raw={**deepcopy(self.occurrence),**changes}
        return validate_assessments(self.document,{'candidates':[self.candidate],'rejected':[]},[raw],require_mention_kind=True)[0]

    def test_saved_relaywave_both_arms_retained_without_supported_promotion(self):
        for arm in ('A','B'):
            doc,frozen,raw,old=case('D2',arm)
            records=validate_assessments(doc,frozen,raw,require_mention_kind=True)
            current=next(r for r in records if r['id']=='C006')
            previous=next(r for r in old if r['id']=='C006')
            self.assertEqual(previous['decision'],'excluded')
            self.assertEqual(current['decision'],'needs_confirmation')
            self.assertEqual({k:v for k,v in current.items() if k!='decision'},
                             {k:v for k,v in previous.items() if k!='decision'})
            self.assertEqual(semantic_labels([current]),[{'id':'C006','field':'external_integrations','status':'tentative'}])

    def test_same_32_rows_only_two_server_decisions_change_and_raw_input_is_unmodified(self):
        differences=[]
        supported_before=supported_after=0
        for doc in ('D1','D2'):
            for arm in ('A','B'):
                source,frozen,raw,old=case(doc,arm)
                snapshot=deepcopy(raw)
                new=validate_assessments(source,frozen,raw,require_mention_kind=True)
                self.assertEqual(raw,snapshot)
                for a,b in zip(old,new,strict=True):
                    supported_before+=a['decision']=='supported'
                    supported_after+=b['decision']=='supported'
                    self.assertEqual({k:v for k,v in a.items() if k!='decision'},
                                     {k:v for k,v in b.items() if k!='decision'})
                    if a!=b: differences.append((doc,arm,a['id'],a['decision'],b['decision']))
        self.assertEqual(differences,[('D2','A','C006','excluded','needs_confirmation'),
                                     ('D2','B','C006','excluded','needs_confirmation')])
        self.assertEqual(supported_before,13)
        self.assertEqual(supported_after,13)

    def test_positive_confirmed_adopted_stays_supported_for_every_field(self):
        for field,kind in ROLES.items():
            r=self.checked(field=field,mentionKind=kind,modelStatus='confirmed',commitment='adopted')
            self.assertEqual(r['decision'],'supported')

    def test_tentative_proposed_valid_roles_all_fields_only_become_pending(self):
        for field,kind in ROLES.items():
            r=self.checked(field=field,mentionKind=kind)
            self.assertEqual(r['decision'],'needs_confirmation')
            self.assertEqual(r['modelStatus'],'tentative')

    def test_explicit_exclusion_conditions_are_not_bypassed_by_tentative(self):
        for change in ({'polarity':'negative'},{'scope':'other'},{'time':'historical'},
                       {'time':'future'},{'role':'non_product'}, {'field':'other','mentionKind':'other'},
                       {'modelStatus':'negated'},{'modelStatus':'irrelevant'},
                       {'scope':'other','polarity':'negative','time':'historical'}):
            with self.subTest(change=change):
                r=self.checked(**change)
                self.assertEqual(self.legacy(r),'excluded')
                self.assertEqual(r['decision'],'excluded')

    def test_grounding_role_and_conflict_guards_keep_original_priority(self):
        for change in ({'support':[]},{'support':[{'quote':'not in source','occurrence':0}]},
                       {'support':[{'quote':self.occurrence['support'][0]['quote'],'occurrence':3}]},
                       {'mentionKind':'other'}, {'mentionKind':'product_operation'},
                       {'mentionKind':'description'}, {'mentionKind':'unclear'},
                       {'conflictsChecked':False}, {'scope':'unclear'}, {'commitment':'unclear'},
                       {'counterEvidence':deepcopy(self.occurrence['support'])},
                       {'scope':'other','support':[]}, {'polarity':'negative','mentionKind':'other'}):
            with self.subTest(change=change):
                r=self.checked(**change)
                self.assertEqual(self.legacy(r),'needs_confirmation')
                self.assertEqual(r['decision'],'needs_confirmation')

    def test_raw_status_errors_are_never_admitted_by_this_change(self):
        for change in ({'field':'other','mentionKind':'other','modelStatus':'confirmed','commitment':'adopted'},
                       {'modelStatus':'confirmed','polarity':'negative','commitment':'adopted'},
                       {'modelStatus':'confirmed','commitment':'proposed'}):
            r=self.checked(**change)
            self.assertEqual(r['decision'],'excluded')
            self.assertEqual(r['modelStatus'],'confirmed')

    def test_missing_legacy_mention_kind_does_not_receive_new_exception(self):
        raw=deepcopy(self.occurrence); del raw['mentionKind']
        row=validate_assessments(self.document,{'candidates':[self.candidate],'rejected':[]},[raw])[0]
        self.assertEqual(row['decision'],'excluded')

    def test_all_enum_combinations_only_change_the_ten_intended_role_field_pairs(self):
        template=deepcopy(next(r for r in self.before if r['id']=='C006'))
        changes=0
        combinations=0
        for field,kind,status,scope,when,polarity,commitment,role in product(
                (*FIELDS,'other'),(*MENTION_KINDS,None),STATUSES,AXES['scope'],AXES['time'],
                AXES['polarity'],AXES['commitment'],AXES['role']):
            r={**template,'field':field,'mentionKind':kind,'modelStatus':status,'scope':scope,'time':when,
               'polarity':polarity,'commitment':commitment,'role':role}
            before=self.legacy(r); after=_decision(r)
            intended=(field in ROLES and kind==ROLES[field] and status=='tentative' and
                      scope=='target' and when=='current' and polarity=='positive' and
                      commitment=='proposed' and role=='product_fact')
            expected='needs_confirmation' if intended else before
            if after!=expected: self.fail(str((r,before,after,expected)))
            changes+=before!=after; combinations+=1
        self.assertEqual(combinations,99792)
        self.assertEqual(changes,10)

    def test_v2_v3_final_boundary_retains_value_span_document_id_and_question(self):
        for arm in ('A','B'):
            doc,frozen,raw,_=case('D2',arm)
            row=next(r for r in validate_assessments(doc,frozen,raw,require_mention_kind=True) if r['id']=='C006')
            for contract in ('confirmation-v2','confirmation-v3'):
                out=unreviewed_boundary(doc,[row],contract)
                bound=out['modelDecisions'][0]
                self.assertEqual(bound['decision'],'needs_confirmation')
                self.assertEqual(bound['sourceValue'],'RelayWave')
                self.assertEqual(bound['candidate'],{'start':356,'end':365})
                self.assertEqual(bound['sourceValue'],doc[356:365])
                self.assertEqual(bound['documentId'],'SYNTHETIC-BOUNDARY-D2')
                self.assertEqual(bound['modelStatus'],'tentative')
                self.assertEqual(bound['commitment'],'proposed')
                self.assertEqual(bound['support'],[{'start':347,'end':401}])
                self.assertEqual(bound['counterEvidence'],[])
                self.assertEqual(out['outcome'],'needs_confirmation')
                self.assertIsNone(out['profile']['data']['external_integrations'])
                self.assertEqual(out['profile']['evidence']['external_integrations'],[])
                self.assertEqual(out['fieldStates']['external_integrations'],'unresolved')
                self.assertIn({'field':'external_integrations','questionId':'confirm_external_integrations','reason':'REVIEW_ISSUE'},out['questions'])
                self.assertEqual(validate_candidate_confirmation(doc,'SYNTHETIC-BOUNDARY-D2',out,contract=contract),out)
                if contract=='confirmation-v3': self.assertEqual(out['reviewDispositions'],[])
                else: self.assertNotIn('reviewDispositions',out)

    def test_pending_candidate_cannot_back_positive_profile_or_user_approval(self):
        row=self.checked()
        for contract in ('confirmation-v2','confirmation-v3'):
            out=unreviewed_boundary(self.document,[row],contract)
            bad=deepcopy(out)
            bad['profile']['data']['external_integrations']=['RelayWave']
            bad['profile']['evidence']['external_integrations']=[{'documentId':'SYNTHETIC-BOUNDARY-D2','start':356,'end':365}]
            with self.assertRaises(ValueError): validate_candidate_confirmation(self.document,'SYNTHETIC-BOUNDARY-D2',bad,contract=contract)
            bad=deepcopy(out); bad['modelDecisions'][0]['decision']='user_confirmed'
            with self.assertRaises(ValueError): validate_candidate_confirmation(self.document,'SYNTHETIC-BOUNDARY-D2',bad,contract=contract)

    def test_current_service_prompt_and_schema_match_frozen_b(self):
        suite=load('suite.json')
        for doc,p in suite['documents'].items():
            generated=assessment_payload(p['document'],p['frozen']['candidates'])
            self.assertEqual(generated['messages'],p['payloads']['B']['messages'])
            self.assertEqual(generated['response_format'],p['payloads']['B']['response_format'])
            self.assertEqual(MENTION_ROLE_INSTRUCTION,load(f'{doc}/B-role-instruction.txt'))
            self.assertNotEqual(MENTION_ROLE_INSTRUCTION,load(f'{doc}/A-role-instruction.txt'))


if __name__=='__main__': unittest.main(verbosity=2)
