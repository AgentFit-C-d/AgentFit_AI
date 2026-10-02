"""Offline semantic-preservation accounting from a human-reviewed alignment.

No keyword matcher, model judge, old candidates, or Profile mutation. References
point into immutable observations; semantic equivalence remains an explicit
human decision rather than an invented automatic score.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

STAGES = ('extracted', 'grounded', 'classified', 'reviewed', 'curated', 'projected', 'final')
OBSERVATIONS = {'extracted': ('general_extracted', 'operations_grounded'),
                'grounded': ('grounded',), 'classified': ('classified',),
                'reviewed': ('review_completed',), 'curated': ('feature_curated',),
                'projected': ('projected',), 'final': ('final_response',)}
STATES = ('preserved', 'missing', 'wrong', 'held', 'human_review')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def meaning_units(gold):
    units = [{'id': row['id'], 'field': row['field'], 'kind': 'fact',
              'meaning': row['value'], 'evidence': row.get('evidence', [])}
             for row in gold['fields']
             if row['expectedState'] == 'stated' and row['field'] != 'features']
    for group in gold['featureGroups']:
        units.extend({'id': f"{group['id']}.{i:02}", 'field': 'features',
                      'kind': 'feature_meaning', 'meaning': meaning,
                      'evidence': group.get('evidence', [])}
                     for i, meaning in enumerate(group['requiredMeaning'], 1))
    if len({row['id'] for row in units}) != len(units):
        raise ValueError('DUPLICATE_MEANING_ID')
    return units


def make_alignment_template(trace: dict, gold: dict) -> dict:
    if trace.get('sourceSha256') != gold['source']['sha256']:
        raise ValueError('SOURCE_IDENTITY_MISMATCH')
    return {'version': 'document-profile-alignment-v1',
            'traceSha256': digest(trace), 'goldSha256': digest(gold),
            'units': [dict(row, judgments=dict.fromkeys(STAGES)) for row in meaning_units(gold)],
            'guards': [{'id': row['id'], 'expectedState': row['expectedState'],
                        'extracted': None, 'judgment': None} for row in gold.get('guards', [])],
            'claims': [], 'claimAuditComplete': False,
            'citationDefects': [], 'citationAuditComplete': False}


def _pointer(value, pointer):
    if type(pointer) is not str or not pointer.startswith('/'):
        raise ValueError('INVALID_ALIGNMENT_REFERENCE')
    try:
        for part in pointer.split('/')[1:]:
            key = part.replace('~1', '/').replace('~0', '~')
            value = value[int(key)] if type(value) is list else value[key]
        return value
    except (ValueError, IndexError, KeyError, TypeError):
        raise ValueError('INVALID_ALIGNMENT_REFERENCE') from None


def _judgment(trace, value, *, stage=None):
    if value is None:
        return 'human_review'
    if (type(value) is not dict or set(value) != {'state', 'refs', 'note'} or
            value['state'] not in STATES or type(value['refs']) is not list or
            type(value['note']) is not str or not value['note'].strip()):
        raise ValueError('INVALID_SEMANTIC_JUDGMENT')
    if value['state'] in ('preserved', 'held') and not value['refs']:
        raise ValueError('MISSING_SEMANTIC_REFERENCE')
    for ref in value['refs']:
        _pointer(trace, ref)
        if stage is not None:
            allowed = ['/stages/' + name for name in OBSERVATIONS[stage]]
            if stage == 'extracted':
                allowed.append('/calls')
            if not any(ref == prefix or ref.startswith(prefix + '/') for prefix in allowed):
                raise ValueError('WRONG_STAGE_REFERENCE')
    return value['state']


def _available(trace, stage):
    if not all(key in trace.get('stages', {}) for key in OBSERVATIONS[stage]):
        return False
    if stage == 'final':
        result = trace['stages']['final_response']
        return type(result) is dict and 'profile' in result and result.get('outcome') != 'failed'
    return True


def _field_states(trace, gold):
    if not _available(trace, 'final'):
        return {'total': len(gold['fields']), 'matched': None, 'rows': []}
    data = trace['stages']['final_response']['profile']['data']
    rows = []
    for field in gold['fields']:
        value = data.get(field['field'])
        actual = 'unknown' if value is None else 'explicit_none' if value == [] else 'stated'
        rows.append({'field': field['field'], 'expected': field['expectedState'],
                     'actual': actual, 'matched': actual == field['expectedState']})
    return {'total': len(rows), 'matched': sum(row['matched'] for row in rows), 'rows': rows}


def _claim_references(trace):
    stages = trace.get('stages', {})
    model = {f'/stages/semantic_assessed/modelDecisions/{i}'
             for i, row in enumerate(stages.get('semantic_assessed', {}).get('modelDecisions', []))
             if row.get('modelStatus') == 'confirmed'}
    final = set()
    for field, value in stages.get('final_response', {}).get('profile', {}).get('data', {}).items():
        base = '/stages/final_response/profile/data/' + field
        if isinstance(value, list):
            final.update(f'{base}/{i}' for i in range(len(value)))
        elif value is not None:
            final.add(base)
    return model, final


def score_document_trace(trace: dict, gold: dict, alignment: dict) -> dict:
    if (alignment.get('traceSha256') != digest(trace) or alignment.get('goldSha256') != digest(gold)
            or trace.get('sourceSha256') != gold['source']['sha256']):
        raise ValueError('ALIGNMENT_IDENTITY_MISMATCH')
    units = meaning_units(gold)
    if [r.get('id') for r in alignment['units']] != [r['id'] for r in units]:
        raise ValueError('MEANING_UNIT_SET_MISMATCH')
    ledger = []
    for expected, row in zip(units, alignment['units']):
        if set(row['judgments']) != set(STAGES):
            raise ValueError('INVALID_STAGE_SET')
        states = {}
        for stage in STAGES:
            judgment = row['judgments'][stage]
            if not _available(trace, stage):
                if judgment is not None:
                    raise ValueError('UNOBSERVED_STAGE_JUDGED')
                states[stage] = 'unobserved'
            else:
                states[stage] = _judgment(trace, judgment, stage=stage)
        first = next((s for s in STAGES if states[s] != 'preserved'), None)
        cause = (None if first is None else states[first]
                 if states[first] in ('human_review', 'unobserved') else first)
        ledger.append({'id': expected['id'], 'kind': expected['kind'], 'field': expected['field'],
            'meaning': expected['meaning'], 'stages': states, 'firstMismatchStage': cause,
            'recovered': cause in STAGES and states['final'] == 'preserved'})
    counts = Counter(row['firstMismatchStage'] for row in ledger if row['firstMismatchStage'] in STAGES)
    attribution_complete = all(row['firstMismatchStage'] not in ('human_review', 'unobserved') for row in ledger)
    stages_reviewed = all(state not in ('human_review', 'unobserved')
                          for row in ledger for state in row['stages'].values())
    feature = [r for r in ledger if r['kind'] == 'feature_meaning']

    def final_counts(rows):
        c = Counter(row['stages']['final'] for row in rows)
        return {'total': len(rows), 'preserved': c['preserved'],
                'missing': c['missing'] + c['wrong'], 'held': c['held'],
                'unjudged': c['human_review'] + c['unobserved']}

    claims = alignment.get('claims', [])
    claim_ids, false_model, false_final, uncertain_claims = set(), 0, 0, 0
    expected_model_refs, expected_final_refs = _claim_references(trace)
    audited_model_refs, audited_final_refs = set(), set()
    false_model_occurrences = set()
    for row in claims:
        if (type(row) is not dict or not row.get('id') or row['id'] in claim_ids
                or not row.get('meaning') or not row.get('note') or
                row.get('expectedState') not in ('stated', 'unknown', 'explicit_none', 'out_of_scope', 'human_review')):
            raise ValueError('INVALID_CLAIM_AUDIT')
        claim_ids.add(row['id'])
        for name in ('modelConfirmedRefs', 'finalPositiveRefs'):
            if type(row.get(name)) is not list:
                raise ValueError('INVALID_CLAIM_AUDIT')
            for ref in row[name]:
                _pointer(trace, ref)
                allowed = expected_model_refs if name == 'modelConfirmedRefs' else expected_final_refs
                if ref not in allowed:
                    raise ValueError('INVALID_CONFIRMED_REFERENCE')
        audited_model_refs.update(row['modelConfirmedRefs'])
        audited_final_refs.update(row['finalPositiveRefs'])
        if row['expectedState'] == 'human_review':
            uncertain_claims += 1
        elif row['expectedState'] != 'stated':
            false_model += bool(row['modelConfirmedRefs'])
            false_final += bool(row['finalPositiveRefs'])
            false_model_occurrences.update(row['modelConfirmedRefs'])
    if (alignment.get('claimAuditComplete') is True and
            (audited_model_refs != expected_model_refs or audited_final_refs != expected_final_refs)):
        raise ValueError('INCOMPLETE_CLAIM_AUDIT')
    audited = alignment.get('claimAuditComplete') is True and not uncertain_claims
    model_observed = isinstance(trace.get('stages', {}).get('semantic_assessed', {}).get('modelDecisions'), list)
    final_observed = _available(trace, 'final')
    model_audited, final_audited = audited and model_observed, audited and final_observed
    citations_audited = (alignment.get('citationAuditComplete') is True
                        and all(_available(trace, stage) for stage in STAGES)
                        and not trace.get('observationErrors'))
    guards = []
    if [r.get('id') for r in alignment.get('guards', [])] != [r['id'] for r in gold.get('guards', [])]:
        raise ValueError('GUARD_SET_MISMATCH')
    for expected, row in zip(gold.get('guards', []), alignment.get('guards', [])):
        if row['extracted'] is not None and type(row['extracted']) is not bool:
            raise ValueError('INVALID_GUARD_AUDIT')
        guards.append({'id': expected['id'], 'expectedState': expected['expectedState'],
                       'extracted': row['extracted'], 'judgment': _judgment(trace, row['judgment'])})
    for defect in alignment.get('citationDefects', []):
        if defect.get('kind') not in ('quote_mismatch', 'wrong_occurrence', 'wrong_context') or not defect.get('note'):
            raise ValueError('INVALID_CITATION_AUDIT')
        _pointer(trace, defect['ref'])
    final = trace.get('stages', {}).get('final_response', {})
    questions = final.get('questions', [])
    final_metrics = final_counts(ledger)
    final_complete = final_metrics['unjudged'] == 0
    return {'version': 'document-profile-score-v1', 'kind': 'human_aligned_semantic_score',
        'traceSha256': digest(trace), 'goldSha256': digest(gold),
        'complete': trace.get('status') == 'complete' and not trace.get('observationErrors')
                    and stages_reviewed and final_complete
                    and model_audited and final_audited and citations_audited
                    and all(r['judgment'] != 'human_review' for r in guards),
        'featureMeaning': final_counts(feature), 'allPositiveMeaning': final_metrics,
        'fieldStates': _field_states(trace, gold), 'firstMismatchCounts': dict(counts),
        'attributionComplete': attribution_complete,
        'candidateExtractionOmissions': counts['extracted'] if attribution_complete else None,
        'groundingOrMergeOmissions': counts['grounded'] if attribution_complete else None,
        'classificationErrors': counts['classified'] if attribution_complete else None,
        'postprocessingOmissions': sum(counts[s] for s in STAGES[3:]) if attribution_complete else None,
        'finalNormalOmissions': final_metrics['missing'] + final_metrics['held'] if final_complete else None,
        'overHeldKnownMeanings': final_metrics['held'] if final_complete else None,
        'modelFalseConfirmations': false_model if model_audited else None,
        'modelFalseConfirmationOccurrences': len(false_model_occurrences) if model_audited else None,
        'serverFalseConfirmations': false_final if final_audited else None,
        'provisionalFalseConfirmations': {'model': false_model if model_observed else None,
                                          'server': false_final if final_observed else None},
        'unreviewedClaims': uncertain_claims, 'claimAuditComplete': model_audited and final_audited,
        'guardJudgments': guards, 'citationDefects': (len(alignment.get('citationDefects', []))
            if citations_audited else None),
        'questions': {'total': len(questions),
            'ordinaryApproval': sum(r.get('reason') == 'CONFIRM_SUGGESTION' for r in questions),
            'uncertainty': sum(r.get('reason') != 'CONFIRM_SUGGESTION' for r in questions)}
            if final_observed else dict.fromkeys(('total', 'ordinaryApproval', 'uncertainty')),
        'calls': len(trace.get('calls', [])), 'elapsedMs': trace.get('elapsedMs'),
        'recordingMs': trace.get('recordingMs'), 'stageLedger': ledger}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--gold', type=Path, required=True)
    parser.add_argument('--alignment', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    trace, gold = (json.loads(path.read_text(encoding='utf-8')) for path in (args.trace, args.gold))
    result = (make_alignment_template(trace, gold) if args.alignment is None else
              score_document_trace(trace, gold, json.loads(args.alignment.read_text(encoding='utf-8'))))
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


if __name__ == '__main__':
    main()
