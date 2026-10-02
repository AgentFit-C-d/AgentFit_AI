"""Hand-reviewed semantic alignment, independent of wording or list counts."""
from copy import deepcopy
import importlib
import unittest

from agentfit_ai.profile import FIELDS


def scoring():
    try:
        return importlib.import_module('diagnostic_tools.document_profile_scoring')
    except ModuleNotFoundError as error:
        if error.name != 'diagnostic_tools.document_profile_scoring':
            raise
        raise AssertionError('semantic preservation scorer is missing') from None


STAGES = ('extracted', 'grounded', 'classified', 'reviewed', 'curated', 'projected', 'final')
REFS = dict(zip(STAGES, ['/stages/general_extracted/0', '/stages/grounded',
    '/stages/classified', '/stages/review_completed', '/stages/feature_curated',
    '/stages/projected', '/stages/final_response/profile']))


def fixture():
    gold = {'source': {'sha256': 'source-hash'}, 'fields': [
        {'id': 'P09', 'field': 'features', 'expectedState': 'stated', 'value': ['등록·조회']},
        {'id': 'P07', 'field': 'database', 'expectedState': 'unknown', 'value': None}],
        'featureGroups': [{'id': 'F01', 'field': 'features', 'value': '등록·조회',
                           'requiredMeaning': ['자료 추가', '저장한 자료 열람'], 'evidence': []}],
        'guards': []}
    data = dict.fromkeys(FIELDS)
    data['features'] = ['항목을 추가하고 목록을 읽는다']
    profile = {'data': data}
    trace = {'version': 'document-profile-trace-v1', 'sourceSha256': 'source-hash',
             'status': 'complete', 'observationErrors': [], 'calls': [], 'elapsedMs': 123,
             'stages': {'general_extracted': [{'extraction_text': '새 자료를 등록한다'}],
                        'operations_grounded': {'candidates': []}, 'grounded': {}, 'classified': {},
                        'semantic_assessed': {'modelDecisions': []},
                        'review_completed': {}, 'feature_curated': {'curation': None},
                        'projected': profile, 'final_response': {'profile': profile,
                          'outcome': 'needs_confirmation', 'questions': [
                            {'field': 'features', 'reason': 'CONFIRM_SUGGESTION'}]}}}
    return trace, gold


def judge_all(template, state='preserved'):
    for unit in template['units']:
        for stage in STAGES:
            unit['judgments'][stage] = {'state': state, 'refs': [REFS[stage]],
                                        'note': '원문 동작과 해당 단계의 의미를 직접 대조했다.'}
    return template


class DocumentProfileScoringTests(unittest.TestCase):
    def test_two_meanings_in_one_paraphrased_feature_count_as_two(self):
        module = scoring()
        trace, gold = fixture()
        aligned = judge_all(module.make_alignment_template(trace, gold))
        result = module.score_document_trace(trace, gold, aligned)
        self.assertEqual(result['featureMeaning'], {'total': 2, 'preserved': 2,
            'missing': 0, 'held': 0, 'unjudged': 0})
        self.assertEqual(result['fieldStates']['matched'], 2)
        self.assertEqual(result['questions']['ordinaryApproval'], 1)
        self.assertEqual(result['questions']['uncertainty'], 0)

    def test_extraction_classification_and_postprocessing_losses_are_not_double_counted(self):
        module = scoring()
        trace, gold = fixture()
        gold['featureGroups'][0]['requiredMeaning'] = ['등록', '열람', '수정', '삭제', '공유']
        aligned = judge_all(module.make_alignment_template(trace, gold))
        starts = ('extracted', 'classified', 'reviewed', 'curated', 'final')
        for row, start in zip(aligned['units'], starts):
            for stage in STAGES[STAGES.index(start):]:
                row['judgments'][stage] = {'state': 'wrong' if stage == 'classified' else 'missing',
                                          'refs': [], 'note': '해당 의미가 이 단계에서 사라짐.'}
        result = module.score_document_trace(trace, gold, aligned)
        self.assertEqual(result['firstMismatchCounts'], {
            'extracted': 1, 'classified': 1, 'reviewed': 1, 'curated': 1, 'final': 1})
        self.assertEqual(result['candidateExtractionOmissions'], 1)
        self.assertEqual(result['classificationErrors'], 1)
        self.assertEqual(result['postprocessingOmissions'], 3)
        self.assertEqual(result['featureMeaning']['missing'], 5)

    def test_unobserved_and_unreviewed_are_not_success_or_zero_loss(self):
        module = scoring()
        trace, gold = fixture()
        trace['stages'].pop('grounded')
        trace['status'] = 'partial'
        template = module.make_alignment_template(trace, gold)
        result = module.score_document_trace(trace, gold, template)
        self.assertFalse(result['complete'])
        self.assertEqual(result['featureMeaning']['unjudged'], 2)
        self.assertIsNone(result['candidateExtractionOmissions'])
        self.assertEqual(result['stageLedger'][0]['stages']['grounded'], 'unobserved')

    def test_alignment_cannot_be_reused_after_trace_or_gold_changes(self):
        module = scoring()
        trace, gold = fixture()
        template = module.make_alignment_template(trace, gold)
        changed = deepcopy(trace)
        changed['elapsedMs'] = 999
        with self.assertRaisesRegex(ValueError, 'ALIGNMENT_IDENTITY_MISMATCH'):
            module.score_document_trace(changed, gold, template)
        changed_gold = deepcopy(gold)
        changed_gold['featureGroups'][0]['requiredMeaning'][0] = '다른 요구'
        with self.assertRaisesRegex(ValueError, 'ALIGNMENT_IDENTITY_MISMATCH'):
            module.score_document_trace(trace, changed_gold, template)

    def test_failed_first_call_cannot_turn_unobserved_audits_into_zero(self):
        module = scoring()
        trace, gold = fixture()
        trace.update(status='partial', calls=[{'outcome': 'failed'}], stages={
            'final_response': {'outcome': 'failed', 'error': 'PROVIDER_ERROR'}})
        aligned = module.make_alignment_template(trace, gold)
        aligned.update(claimAuditComplete=True, citationAuditComplete=True)
        result = module.score_document_trace(trace, gold, aligned)
        for metric in ('modelFalseConfirmations', 'modelFalseConfirmationOccurrences',
                       'serverFalseConfirmations', 'citationDefects', 'overHeldKnownMeanings'):
            self.assertIsNone(result[metric], metric)
        self.assertEqual(result['questions'], dict.fromkeys(('total', 'ordinaryApproval', 'uncertainty')))
        self.assertEqual(result['provisionalFalseConfirmations'], {'model': None, 'server': None})
        self.assertFalse(result['claimAuditComplete'])
        self.assertFalse(result['complete'])

    def test_model_audit_can_complete_before_unobserved_final_output(self):
        module = scoring()
        trace, gold = fixture()
        trace.update(status='partial', stages={
            'semantic_assessed': {'modelDecisions': []},
            'final_response': {'outcome': 'failed', 'error': 'REVIEW_FAILED'}})
        aligned = module.make_alignment_template(trace, gold)
        aligned.update(claimAuditComplete=True, citationAuditComplete=True)
        result = module.score_document_trace(trace, gold, aligned)
        self.assertEqual(result['modelFalseConfirmations'], 0)
        self.assertIsNone(result['serverFalseConfirmations'])
        self.assertIsNone(result['citationDefects'])
        self.assertFalse(result['claimAuditComplete'])

    def test_first_loss_attribution_does_not_complete_unreviewed_later_stage(self):
        module = scoring()
        trace, gold = fixture()
        aligned = judge_all(module.make_alignment_template(trace, gold))
        aligned.update(claimAuditComplete=True, citationAuditComplete=True, claims=[{
            'id': 'normal', 'expectedState': 'stated', 'meaning': '등록·조회',
            'note': '정상 기능을 대조했다.', 'modelConfirmedRefs': [],
            'finalPositiveRefs': ['/stages/final_response/profile/data/features/0']}])
        self.assertTrue(module.score_document_trace(trace, gold, aligned)['complete'])
        aligned['units'][0]['judgments']['extracted'] = {
            'state': 'missing', 'refs': [], 'note': '초기 추출에서 빠짐.'}
        aligned['units'][0]['judgments']['classified'] = None
        result = module.score_document_trace(trace, gold, aligned)
        self.assertTrue(result['attributionComplete'])
        self.assertEqual(result['candidateExtractionOmissions'], 1)
        self.assertTrue(result['stageLedger'][0]['recovered'])
        self.assertFalse(result['complete'])

    def test_preservation_requires_real_stage_reference_and_review_note(self):
        module = scoring()
        trace, gold = fixture()
        for refs, note in ((['/stages/absent'], '검토'), ([], '검토'), ([REFS['final']], '')):
            template = judge_all(module.make_alignment_template(trace, gold))
            template['units'][0]['judgments']['final'].update(refs=refs, note=note)
            with self.assertRaises(ValueError):
                module.score_document_trace(trace, gold, template)

    def test_held_known_fact_is_visible_as_omission_and_confirmation_burden(self):
        module = scoring()
        trace, gold = fixture()
        aligned = judge_all(module.make_alignment_template(trace, gold))
        row = aligned['units'][1]
        for stage in STAGES[2:]:
            row['judgments'][stage].update(state='held')
        result = module.score_document_trace(trace, gold, aligned)
        self.assertEqual(result['featureMeaning']['preserved'], 1)
        self.assertEqual(result['featureMeaning']['held'], 1)
        self.assertEqual(result['finalNormalOmissions'], 1)
        self.assertEqual(result['overHeldKnownMeanings'], 1)

    def test_arbitrary_extra_claims_are_audited_separately_from_normal_coverage(self):
        module = scoring()
        trace, gold = fixture()
        trace['stages']['semantic_assessed'] = {'modelDecisions': [
            {'modelStatus': 'confirmed', 'field': 'features'}]}
        aligned = judge_all(module.make_alignment_template(trace, gold))
        aligned['claims'] = [{'id': 'extra-1', 'expectedState': 'unknown',
            'meaning': '이름만 언급된 미채택 기능', 'note': '긍정 채택 근거 없음',
            'modelConfirmedRefs': ['/stages/semantic_assessed/modelDecisions/0'],
            'finalPositiveRefs': ['/stages/final_response/profile/data/features/0']}]
        aligned['claimAuditComplete'] = True
        result = module.score_document_trace(trace, gold, aligned)
        self.assertEqual(result['modelFalseConfirmations'], 1)
        self.assertEqual(result['serverFalseConfirmations'], 1)
        self.assertEqual(result['featureMeaning']['preserved'], 2)

    def test_claim_audit_cannot_claim_zero_false_positives_without_covering_output(self):
        module = scoring()
        trace, gold = fixture()
        aligned = judge_all(module.make_alignment_template(trace, gold))
        aligned['claimAuditComplete'] = True
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_CLAIM_AUDIT'):
            module.score_document_trace(trace, gold, aligned)

    def test_model_claim_reference_must_point_to_an_actual_confirmed_decision(self):
        module = scoring()
        trace, gold = fixture()
        trace['stages']['semantic_assessed'] = {'modelDecisions': [
            {'modelStatus': 'tentative', 'field': 'features'}]}
        aligned = judge_all(module.make_alignment_template(trace, gold))
        aligned['claims'] = [{'id': 'bad-ref', 'expectedState': 'unknown',
            'meaning': '선택 기능', 'note': '확정 아님',
            'modelConfirmedRefs': ['/stages/semantic_assessed/modelDecisions/0'],
            'finalPositiveRefs': []}]
        with self.assertRaisesRegex(ValueError, 'INVALID_CONFIRMED_REFERENCE'):
            module.score_document_trace(trace, gold, aligned)


if __name__ == '__main__':
    unittest.main()
