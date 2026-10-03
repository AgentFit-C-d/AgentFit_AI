"""Historical role errors and schema expressiveness; no new model responses.

Expected failures describe immutable historical model mistakes, not instructions
to relax the server. Synthetic rows only exercise server rules, never accuracy.
"""
import hashlib
import json
from pathlib import Path
import unittest
import zipfile

from agentfit_ai.candidate_semantic_assessment import (
    assessment_payload, validate_assessments, semantic_labels,
)
from agentfit_ai.candidate_mention_roles import MENTION_KINDS
from agentfit_ai.profile import FIELDS
from review_preservation_fixture import load as v2_load, offline

FIXTURE=Path(__file__).parent/'fixtures/review_recovery'
ROLES={field:('product_operation' if field=='features' else
             'external_service' if field=='external_integrations' else 'other') for field in FIELDS}


def stored_run(version):
    if version=='v2':
        return v2_load('document.txt'),v2_load('trace.json')
    seal=json.loads((FIXTURE/'manifest.json').read_text(encoding='utf-8'))
    archive=(FIXTURE/'records.zip').read_bytes()
    assert hashlib.sha256(archive).hexdigest()==seal['archiveSha256']
    with zipfile.ZipFile(FIXTURE/'records.zip') as z:
        data={n:z.read(n) for n in ('document.txt','trace.json')}
    assert all(hashlib.sha256(raw).hexdigest()==seal['files'][n] for n,raw in data.items())
    return data['document.txt'].decode('utf-8'),json.loads(data['trace.json'])


def recorded_batches(version):
    document,trace=stored_run(version)
    rows=[]
    for call in trace['calls']:
        request=call['request']
        if request.get('response_format',{}).get('json_schema',{}).get('name')!='agentfit_semantic_assessment':
            continue
        data=json.loads(request['messages'][1]['content'])
        frozen={'candidates':[{k:c[k] for k in ('id','start','end')} for c in data['candidates']],'rejected':[]}
        raw=json.loads(json.loads(call['response']['text'])['choices'][0]['message']['content'])['assessments']
        rows.append({'document':document,'trace':trace,'call':call,'input':data,'frozen':frozen,'raw':raw})
    return rows


def saved(version,start):
    for batch in recorded_batches(version):
        candidate=next((c for c in batch['frozen']['candidates'] if c['start']==start),None)
        if candidate:
            row=next(r for r in batch['raw'] if r['id']==candidate['id'])
            record=validate_assessments(batch['document'],{'candidates':[candidate],'rejected':[]},[row],require_mention_kind=True)[0]
            return batch,candidate,row,record
    raise AssertionError('missing retained candidate')


def synthetic(document,value,field,kind,*,start=None,**changes):
    start=document.index(value) if start is None else start
    candidate={'id':'C000','start':start,'end':start+len(value)}
    row={'id':'C000','field':field,'mentionKind':kind,'modelStatus':'confirmed',
         'scope':'target','time':'current','polarity':'positive','commitment':'adopted',
         'role':'product_fact','conflictsChecked':True,
         'support':[{'quote':document,'occurrence':0}],'counterEvidence':[],**changes}
    return validate_assessments(document,{'candidates':[candidate],'rejected':[]},[row],require_mention_kind=True)[0]


class MentionRoleCauseTests(unittest.TestCase):
    def setUp(self):
        guard=offline()
        guard.__enter__()
        self.addCleanup(guard.__exit__,None,None,None)

    def test_focus_saved_raw_responses_reproduce_original_server_records(self):
        for version in ('v2','v3'):
            for position in (2,137,168,1857,3570,4020,5122,7266):
                batch,candidate,raw,record=saved(version,position)
                original=next(r for r in batch['trace']['stages']['semantic_assessed']['modelDecisions'] if r['id']==candidate['id'])
                with self.subTest(version=version,position=position):
                    self.assertEqual(record,original)
                    self.assertEqual(raw['modelStatus'],record['modelStatus'])

    def test_current_builder_differs_from_historical_requests_only_by_role_block(self):
        from tentative_proposed_fixture import load
        old, new = load('D1/A-role-instruction.txt'), load('D1/B-role-instruction.txt')
        for version in ('v2','v3'):
            for batch in recorded_batches(version):
                with self.subTest(version=version,call=batch['call']['index']):
                    generated=assessment_payload(batch['document'],batch['frozen']['candidates'])
                    historical = batch['call']['request']['messages']
                    self.assertEqual(historical[0]['content'].count(old), 1)
                    self.assertEqual(historical[0]['content'].replace(old, new), generated['messages'][0]['content'])
                    self.assertEqual(historical[1:], generated['messages'][1:])
                    self.assertEqual(batch['call']['request']['response_format'],generated['response_format'])
                    self.assertEqual(batch['input']['document'],batch['document'])

    def test_all_ten_positive_fields_have_an_accepted_existing_role(self):
        for field in FIELDS:
            with self.subTest(field=field):
                row=synthetic('현재 대상 제품의 명시된 사실은 Value다.','Value',field,ROLES[field])
                self.assertEqual(row['decision'],'supported')
                self.assertEqual(row['modelStatus'],'confirmed')

    def test_wrong_roles_are_not_overridden_by_an_otherwise_correct_field(self):
        for field in FIELDS:
            for kind in MENTION_KINDS:
                with self.subTest(field=field,kind=kind):
                    row=synthetic('명시된 사실 Value.','Value',field,kind)
                    self.assertEqual(row['decision'],'supported' if kind==ROLES[field] else 'needs_confirmation')

    def test_target_identity_and_other_project_are_separate(self):
        doc='대상 제품은 LumaDock이다. 비교 사례인 EchoNote의 구조를 설명한다.'
        self.assertEqual(synthetic(doc,'LumaDock','project_name','other')['decision'],'supported')
        self.assertEqual(synthetic(doc,'EchoNote','project_name','other',scope='other',modelStatus='irrelevant')['decision'],'excluded')

    def test_example_identity_does_not_inherit_target_project_adoption(self):
        doc='본 기획의 제품 이름은 LumaDock이다. 사용자 입력 예시: 프로젝트명 EchoNote, 유형 모바일 앱.'
        example=synthetic(doc,'EchoNote','project_name','other',scope='other',modelStatus='irrelevant')
        self.assertEqual(example['decision'],'excluded')
        self.assertEqual(example['scope'],'other')

    def test_same_name_client_and_auth_service_depend_on_the_occurrence(self):
        doc='Kora용 설정 파일을 내보낸다. 사용자 신원은 Kora 인증 API로 검증한다.'
        client=synthetic(doc,'Kora','other','other',modelStatus='irrelevant',role='non_product')
        service=synthetic(doc,'Kora','external_integrations','external_service',start=doc.rindex('Kora'))
        self.assertEqual(client['decision'],'excluded')
        self.assertEqual(service['decision'],'supported')
        self.assertNotEqual(client['candidate'],service['candidate'])

    def test_normal_login_with_unrelated_permission_negation_is_preserved(self):
        row=synthetic('GitHub 로그인만 제공하고 저장소 권한은 요청하지 않는다.','GitHub','external_integrations','external_service')
        self.assertEqual(row['decision'],'supported')

    def test_negation_preserves_raw_status_and_excludes_positive_adoption(self):
        row=synthetic('AtlasID 연동은 사용하지 않는다.','AtlasID','external_integrations','external_service',modelStatus='negated',polarity='negative')
        self.assertEqual(row['decision'],'excluded')
        self.assertEqual(row['modelStatus'],'negated')

    def test_unclear_relation_is_held_in_plausible_field(self):
        row=synthetic('Kora 관련 지원은 미정이다.','Kora','external_integrations','unclear',modelStatus='tentative',commitment='unclear')
        self.assertEqual(row['decision'],'needs_confirmation')
        self.assertEqual(semantic_labels([row])[0]['status'],'tentative')

    def test_conflicting_evidence_is_held_even_when_model_says_confirmed(self):
        doc='AtlasID 인증을 제공한다. 같은 배포에서 AtlasID 인증을 제공하지 않는다. 두 요구는 미해결이다.'
        row=synthetic(doc,'AtlasID','external_integrations','external_service',counterEvidence=[{'quote':'같은 배포에서 AtlasID 인증을 제공하지 않는다.','occurrence':0}])
        self.assertEqual(row['decision'],'needs_confirmation')
        self.assertEqual(row['modelStatus'],'confirmed')

    def test_quote_errors_are_separate_from_the_role_gate(self):
        for version,position in [('v2',2),('v2',168),('v2',5122),('v3',3570),('v3',5122)]:
            _,_,_,row=saved(version,position)
            with self.subTest(version=version,position=position):
                self.assertFalse(row['groundingValid'])
                self.assertEqual(row['decision'],'needs_confirmation')

    def test_complete_v2_review_missed_codex_while_v3_has_no_review_result(self):
        _,trace=stored_run('v2')
        _,candidate,_,_=saved('v2',4020)
        self.assertNotIn(candidate['id'],trace['stages']['review_completed']['review']['wrongCandidateIds'])
        self.assertIn('Codex',trace['stages']['final_response']['profile']['data']['external_integrations'])
        self.assertIsNone(trace['stages']['final_response']['profile']['data']['project_name'])
        _,trace=stored_run('v3')
        self.assertNotIn('review_completed',trace['stages'])
        self.assertEqual(trace['stages']['final_response']['outcome'],'failed')

    # Immutable past model errors: these intentionally remain failing. A prompt
    # proposal cannot change their bytes and the server must not excuse wrong roles.
    @unittest.expectedFailure
    def test_historical_v2_target_name_meets_semantic_role_expectation(self):
        self.assertEqual(saved('v2',2)[2]['mentionKind'],'other')

    @unittest.expectedFailure
    def test_historical_v3_target_name_meets_semantic_role_expectation(self):
        self.assertEqual(saved('v3',2)[2]['mentionKind'],'other')

    @unittest.expectedFailure
    def test_historical_v2_client_is_not_an_adopted_outside_provider(self):
        self.assertNotEqual(saved('v2',4020)[3]['decision'],'supported')

    @unittest.expectedFailure
    def test_historical_v3_client_is_not_an_adopted_outside_provider(self):
        self.assertNotEqual(saved('v3',4020)[3]['decision'],'supported')

    def test_separate_proposed_in_scope_fact_remains_pending(self):
        row=synthetic('AtlasID 연동을 검토 중이며 채택은 미정이다.','AtlasID','external_integrations','external_service',modelStatus='tentative',commitment='proposed')
        self.assertEqual(row['decision'],'needs_confirmation')


if __name__=='__main__':
    unittest.main()
