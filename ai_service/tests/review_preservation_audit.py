"""Reproduce frozen-response comparison offline; never scores new model behavior.

Run from ai_service: python tests/review_preservation_audit.py OUTPUT_DIR [--suite]
"""
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
import inspect
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_preservation_fixture import load, offline, replay


def audit():
    before, after = replay(), replay('confirmation-v3')
    assert before == load('result.json')
    assert all(before[k] == after[k] for k in before if k != 'contract')
    records = {r['id']: r for r in after['modelDecisions']}
    rejected = {r['candidateId']: r for r in after['reviewDispositions']}
    held_before = {r['id'] for r in before['modelDecisions'] if r['decision'] == 'needs_confirmation'}
    held_after = held_before | set(rejected)
    document = load('document.txt')
    bindings = []
    for cid, disposition in rejected.items():
        record = records[cid]
        span = record['candidate']
        assert record['sourceValue'] == document[span['start']:span['end']]
        assert dict(documentId=record['documentId'], **span) not in after['profile']['evidence'][record['field']]
        bindings.append(dict(disposition, sourceValue=record['sourceValue'], candidate=span,
                             documentId=record['documentId'], rawDecision=record['decision'],
                             rawModelStatus=record['modelStatus'], userConfirmed=False))
    meanings = []
    for row in load('meaning-audit.json'):
        linked = sorted({c['candidateId'] for c in row['candidateEvidence']} & set(rejected))
        # Reuse the frozen human mapping. No new lexical or semantic matching.
        state = 'held' if row['finalJudgment'] == 'missing' and linked else row['finalJudgment']
        meanings.append(dict(id=row['id'], meaning=row['meaning'], before=row['finalJudgment'],
                             after=state, newlyLinkedReviewCandidates=linked,
                             sourceEvidence=row['sourceEvidence']))
    counts = {k: dict(Counter(m[k] for m in meanings)) for k in ('before', 'after')}
    assert counts['before'] == dict(preserved=26, held=9, missing=3, human_review=2)
    assert counts['after'] == dict(preserved=26, held=11, missing=1, human_review=2)
    false_count = load('audit-summary.json')['finalPositiveClaimAudit']['falseMeanings']
    summary = dict(v2ExactlyMatchesSaved=True, originalModelDecisionsIdentical=True,
        profileIdentical=True, normalMeanings=counts, positiveFalseMeanings={'before': false_count, 'after': false_count},
        pendingCandidates={'before': len(held_before), 'after': len(held_after)},
        questionCount={'before': len(before['questions']) + len(before.get('unassignedQuestions', [])),
                       'after': len(after['questions']) + len(after.get('unassignedQuestions', []))},
        acceptedOccurrences=27, unreviewedOccurrences=112, originalPending=52,
        newReviewPending=len(rejected), rawModelDecisions=len(records), newModelCalls=0, retries=0,
        transport='in-memory replay / ASGI / child stdin-stdout; application sockets blocked',
        generalExtractionReplay='saved general_extracted objects; no LangExtract provider invocation',
        operationGroundingReplay='saved operations_grounded; excludes newly recovered spans from semantic replay',
        providerRequestReplay='saved requests 4..25 exactly matched; responses replayed locally',
        evaluationScope='v3 regression on frozen candidates, not quality of current upstream extraction',
        modelAccuracyGainClaimed=False, realSpringVerified=False, deployed=False)
    return {'summary.json': summary, 'v2-result.json': before, 'v3-result.json': after,
            'meaning-comparison.json': meanings, 'retained-review-evidence.json': bindings}


def full_suite(out):
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent))
    def leaves(node):
        for child in node:
            if isinstance(child, unittest.TestSuite):
                yield from leaves(child)
            else:
                yield child
    cases = list(leaves(suite))
    def uses_tcp(test):
        source = inspect.getsource(getattr(type(test), test._testMethodName))
        return (test.__class__.__module__.endswith('test_nvidia_response_diagnostics') or
                any(token in source for token in ('local_provider(', 'ThreadingHTTPServer(',
                                                  'test_tcp_disconnect_cancels_running_analysis')))
    omitted = [t.id() for t in cases if uses_tcp(t)]
    # Existing loopback TCP/provider tests intentionally send network bytes,
    # including from children. Exclude rather than merely guarding the parent.
    selected = unittest.TestSuite(t for t in cases if t.id() not in omitted)
    # Existing transport tests replace their network boundary themselves and
    # assert callable identity. Keep those real parser functions, block sockets.
    with (out / 'unit-tests.txt').open('w', encoding='utf-8') as log, \
            redirect_stdout(log), redirect_stderr(log), offline(block_providers=False):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(selected)
    value = dict(testsRun=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                 skipped=[(t.id(), reason) for t, reason in result.skipped],
                 intentionallyNotRunNetworkTests=omitted,
                 failureDetails=[(t.id(), detail) for t, detail in result.failures + result.errors])
    (out / 'test-summary.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in value.items() if k != 'failureDetails'}, ensure_ascii=False))
    return result.wasSuccessful()


if __name__ == '__main__':
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name, value in audit().items():
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    passed = full_suite(output) if '--suite' in sys.argv[2:] else True
    print(json.dumps({'output': str(output), 'passed': passed, 'newModelCalls': 0}, ensure_ascii=False))
    sys.exit(0 if passed else 1)
