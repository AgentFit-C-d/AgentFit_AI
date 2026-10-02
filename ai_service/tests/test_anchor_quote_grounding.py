"""Offline location recovery only; no saved semantic judgment for new candidates."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agentfit_ai.anchored_grounding import ground_anchored_extractions
from agentfit_ai.operation_candidates import extract_operation_candidates
from agentfit_ai.deepseek_evaluation import MODEL
from review_preservation_fixture import load, offline


def extraction(quote, anchor):
    return SimpleNamespace(extraction_class='candidate', extraction_text=quote, attributes={'anchor': anchor})


def saved_operations():
    call = load('trace.json')['calls'][2]
    body = json.loads(json.loads(call['response']['text'])['choices'][0]['message']['content'])
    return call, body['mentions']


def resolve(document, mentions):
    def transport(payload, key, timeout):
        assert json.loads(payload['messages'][1]['content'])['document'] == document
        return json.dumps({'model': MODEL, 'choices': [{'finish_reason': 'stop',
            'message': {'content': json.dumps({'mentions': mentions}, ensure_ascii=False)}}]}).encode()
    with offline():
        return extract_operation_candidates(document, 'OFFLINE-NONCREDENTIAL', transport=transport)


class AnchorQuoteGroundingTests(unittest.TestCase):
    def test_saved_cause_is_quote_style_not_absent_candidate(self):
        document = load('document.txt')
        _, mentions = saved_operations()
        mention = mentions[18]
        row, = ground_anchored_extractions(document, [extraction(mention['quote'], mention['anchor'])])
        self.assertEqual(row, {'status': 'review', 'start': None, 'end': None, 'reason': 'ambiguous_anchor'})
        self.assertNotIn(mention['anchor'], document)
        self.assertEqual(document[1890:1913], mention['quote'])
        self.assertEqual(document.count(mention['anchor'].translate(str.maketrans({'“': '"', '”': '"'}))), 1)

    def test_saved_operation_response_recovers_location_without_downstream_calls(self):
        document, trace = load('document.txt'), load('trace.json')
        call, mentions = saved_operations()
        calls = []
        def transport(payload, key, timeout):
            self.assertEqual(payload, call['request'])
            calls.append(payload)
            return call['response']['text'].encode()
        with offline(), patch('agentfit_ai.candidate_analysis_pipeline.classify_grounded_candidates',
                               side_effect=AssertionError('NO_DOWNSTREAM_JUDGMENT')):
            frozen = extract_operation_candidates(document, 'OFFLINE-NONCREDENTIAL', transport=transport)
        self.assertEqual(len(calls), 1)  # One locally replayed response, zero API calls.
        self.assertIn({'id': 'C018', 'start': 1890, 'end': 1913}, frozen['candidates'])
        self.assertNotIn({'index': 18, 'reason': 'ambiguous_anchor'}, frozen['rejected'])
        self.assertTrue(all(c in frozen['candidates'] for c in trace['stages']['operations_grounded']['candidates']))
        self.assertEqual(document[1890:1913], 'PDF · Markdown · 텍스트 입력')

    def test_unique_quotes_restore_crlf_korean_emoji_original_indices(self):
        for document, anchor in (
            ('😀 머리말\r\n현재 "내역 📚 조회"를 제공한다.\r\n끝', '현재 “내역 📚 조회”를 제공한다.'),
            ('😀 머리말\r\n현재 “내역 📚 조회”를 제공한다.\r\n끝', '현재 "내역 📚 조회"를 제공한다.')):
            mention = {'quote': '내역 📚 조회', 'anchor': anchor}
            original = deepcopy(mention)
            frozen = resolve(document, [mention])
            with self.subTest(document=document):
                self.assertEqual(frozen['rejected'], [])
                span = frozen['candidates'][0]
                self.assertEqual((span['start'], span['end']), (document.index(mention['quote']),
                                  document.index(mention['quote']) + len(mention['quote'])))
                self.assertEqual(document[span['start']:span['end']], mention['quote'])
                self.assertEqual(mention, original)

    def test_exact_match_has_priority_over_normalized_alternative(self):
        document = '현재 "조회" 제공.\n현재 “조회” 제공.'
        frozen = resolve(document, [{'quote': '조회', 'anchor': '현재 “조회” 제공.'}])
        self.assertEqual(frozen['candidates'], [{'id': 'C000', 'start': document.rindex('조회'),
                                                'end': document.rindex('조회') + 2}])

    def test_multiple_normalized_anchors_or_values_remain_ambiguous(self):
        cases = [ ('"조회" 제공. "조회" 제공.', '조회', '“조회” 제공.'),
                  ('"조회" 제공. “조회” 제공.', '조회', '”조회“ 제공.'),
                  ('"조회"와 "조회"를 제공.', '조회', '“조회”와 “조회”를 제공.') ]
        for doc, quote, anchor in cases:
            with self.subTest(doc=doc):
                frozen = resolve(doc, [{'quote': quote, 'anchor': anchor}])
                self.assertEqual(frozen['candidates'], [])
                self.assertEqual(frozen['rejected'], [{'index': 0, 'reason': 'ambiguous_anchor'}])

    def test_same_quote_in_multiple_contexts_resolves_only_unique_anchor(self):
        doc = '이전 "조회"는 없다.\r\n현재 "조회"를 제공한다.'
        frozen = resolve(doc, [{'quote': '조회', 'anchor': '현재 “조회”를 제공한다.'}])
        self.assertEqual(frozen['candidates'], [{'id': 'C000', 'start': doc.rindex('조회'),
                                                'end': doc.rindex('조회') + 2}])

    def test_absent_quote_wrong_context_and_non_quote_differences_are_not_repaired(self):
        for quote, anchor in (('조회', '현재 “취소” 제공.'), ('삭제', '현재 “조회” 제공.'),
                              ('조회', '예정 “조회” 제공.'), ('조회', '현재  “조회” 제공.'),
                              ('조회', '현재 ‘조회’ 제공.'), ('조회', '현재 `조회` 제공.'),
                              ('조회', '현재 “조회” 제공!'), ('“조회”', '현재 “조회” 제공.')):
            with self.subTest(quote=quote, anchor=anchor):
                frozen = resolve('현재 "조회" 제공.', [{'quote': quote, 'anchor': anchor}])
                self.assertEqual(frozen['candidates'], [])
                self.assertEqual(frozen['rejected'], [{'index': 0, 'reason': 'ambiguous_anchor'}])

    def test_exact_and_variant_duplicate_same_span_still_rejected(self):
        doc = '"조회" 제공.'
        frozen = resolve(doc, [{'quote': '조회', 'anchor': doc}, {'quote': '조회', 'anchor': '“조회” 제공.'}])
        self.assertEqual(frozen['candidates'], [])
        self.assertEqual(frozen['rejected'], [{'index': 0, 'reason': 'duplicate_span'},
                                             {'index': 1, 'reason': 'duplicate_span'}])

    def test_negative_and_other_project_context_kept_without_semantic_labels(self):
        doc = '우리 제품은 "일괄 삭제"를 지원하지 않는다. 다른 제품은 "문서 공유"를 제공한다.'
        mentions = [{'quote': '일괄 삭제', 'anchor': '우리 제품은 “일괄 삭제”를 지원하지 않는다.'},
                    {'quote': '문서 공유', 'anchor': '다른 제품은 “문서 공유”를 제공한다.'}]
        frozen = resolve(doc, mentions)
        self.assertEqual(frozen['rejected'], [])
        self.assertEqual([doc[c['start']:c['end']] for c in frozen['candidates']], ['일괄 삭제', '문서 공유'])
        self.assertTrue(all(set(c) == {'id', 'start', 'end'} for c in frozen['candidates']))
        exact = resolve(doc, [{**m, 'anchor': m['anchor'].replace('“', '"').replace('”', '"')} for m in mentions])
        self.assertEqual(frozen, exact)

    def test_original_interval_conflict_is_not_overridden_by_quote_fallback(self):
        item = extraction('조회', '“조회” 제공.')
        item.char_interval = SimpleNamespace(start_pos=0, end_pos=2)
        row, = ground_anchored_extractions('"조회" 제공.', [item], allow_quote_variants=True)
        self.assertEqual(row['reason'], 'alignment_conflict')

    def test_fallback_is_not_enabled_for_other_default_grounding_callers(self):
        row, = ground_anchored_extractions('"조회" 제공.', [extraction('조회', '“조회” 제공.')])
        self.assertEqual(row['reason'], 'ambiguous_anchor')
        row, = ground_anchored_extractions('"조회" 제공.', [extraction('조회', '“조회” 제공.')],
                                          allow_quote_variants=True)
        self.assertEqual(row, {'status': 'exact', 'start': 1, 'end': 3, 'reason': 'anchor_quote_variant'})

    def test_non_quote_unicode_normalization_is_not_enabled(self):
        for doc, quote, anchor in [('"café" ready.', 'café', '“cafe\u0301” ready.'),
                                  ('"Ａ" ready.', 'A', '“A” ready.'),
                                  ('"가" ready.', '가', '“가” ready.')]:
            with self.subTest(doc=doc):
                self.assertEqual(resolve(doc, [{'quote': quote, 'anchor': anchor}])['candidates'], [])


if __name__ == '__main__':
    unittest.main()
