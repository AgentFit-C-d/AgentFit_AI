"""Grounding-only saved response audit. No downstream calls or gold judgments."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentfit_ai.anchored_grounding import ground_anchored_extractions
from agentfit_ai.operation_candidates import extract_operation_candidates
from review_preservation_fixture import load, offline, DIRECTORY
from review_preservation_audit import full_suite


def audit():
    manifest = json.loads((DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
    for name in manifest['files']:
        load(name)  # Verify original bytes including unchanged source, trace and gold.
    document, trace = load('document.txt'), load('trace.json')
    call = trace['calls'][2]
    mentions = json.loads(json.loads(call['response']['text'])['choices'][0]['message']['content'])['mentions']
    extractions = [SimpleNamespace(extraction_class='candidate', extraction_text=m['quote'],
                                   attributes={'anchor': m['anchor']}) for m in mentions]
    before_rows = ground_anchored_extractions(document, extractions)
    before = {'candidates': [{'id': f'C{i:03}', 'start': r['start'], 'end': r['end']}
                             for i, r in enumerate(before_rows) if r['status'] == 'exact'],
              'rejected': [{'index': i, 'reason': r['reason']} for i, r in enumerate(before_rows)
                           if r['status'] != 'exact']}
    assert before == trace['stages']['operations_grounded']
    replayed = []
    def transport(payload, key, timeout):
        assert payload == call['request']
        replayed.append(call['index'])
        return call['response']['text'].encode('utf-8')
    with offline(), patch('agentfit_ai.candidate_analysis_pipeline.classify_grounded_candidates',
                           side_effect=AssertionError('DOWNSTREAM_FORBIDDEN')):
        after = extract_operation_candidates(document, 'OFFLINE-NONCREDENTIAL', transport=transport)
    assert replayed == [3]
    after_rows = ground_anchored_extractions(document, extractions, allow_quote_variants=True)
    recovered, lost = [], []
    for i, (old, new) in enumerate(zip(before_rows, after_rows)):
        if old['status'] == 'exact':
            if old != new:
                lost.append(i)
            continue
        if new['status'] == 'exact':
            value = document[new['start']:new['end']]
            assert value == mentions[i]['quote']
            recovered.append({'operationMentionIndex': i, 'documentId': trace['documentId'],
                              'sourceValue': value, 'start': new['start'], 'end': new['end'],
                              'before': old, 'after': new, 'savedAnchor': mentions[i]['anchor']})
    assert not lost
    baseline_positions = {(c['start'], c['end']) for c in trace['stages']['grounded']['candidates']}
    additional_positions = {(r['start'], r['end']) for r in recovered} - baseline_positions
    summary = {'baseCode': 'e5ec802', 'fixtureHashes': manifest['files'],
               'mentionCount': len(mentions), 'groundedBefore': len(before['candidates']),
               'groundedAfter': len(after['candidates']), 'rejectedBefore': len(before['rejected']),
               'rejectedAfter': len(after['rejected']), 'recoveredCount': len(recovered),
               'existingExactLinksChanged': lost, 'newUniquePositionsAfterUnion': len(additional_positions),
               'originalMergedCandidateCount': len(baseline_positions),
               'candidatePositionsIfMerged': len(baseline_positions | additional_positions),
               'modelRequests': 0, 'savedOperationResponsesReplayed': replayed,
               'classificationOrReviewOfNewCandidates': 'not_measured',
               'finalProfileMeaningPreservation': 'not_measured', 'normal40MissingAfter': None,
               'serviceApplied': False, 'bigGoal': 'paused'}
    return {'summary.json': summary, 'recovered-locations.json': recovered,
            'before-operations.json': before, 'after-operations.json': after}


if __name__ == '__main__':
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = audit()
    for name, value in results.items():
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    success = full_suite(output) if '--suite' in sys.argv[2:] else True
    print(json.dumps(results['summary.json'], ensure_ascii=False))
    sys.exit(0 if success else 1)
