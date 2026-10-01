"""One isolated B quote versus unit-ID experiment; never imported by services."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'ai_service'))
sys.path.insert(0, str(ROOT / 'work/harness/direct-field-comparison'))
sys.path.insert(0, str(ROOT / 'work/harness/evidence-relation-repair'))
from comparison import (CallGate, MODEL, score_rows, validate_direct, build_payload,
                        AnalysisError, write_json, error_code)
from source_registry import build_registry, resolve_units, validate_registry, SourceContractError
from legacy_audit import audit_legacy_record
from agentfit_ai.deepseek_evaluation import NvidiaAnalyzer
from agentfit_ai.candidate_semantic_assessment import STATUSES
from agentfit_ai.operation_candidates import _validate_frozen
from agentfit_ai.profile import FIELDS


# This is the evidence-only portion of the previous B instruction. The full
# classification prefix and field semantics suffix remain byte-for-byte equal.
QUOTE_INSTRUCTION = (
    'Support describes the occurrence even for excluded/negative cases. Return exact '
    'continuous quotes containing the establishing sentence/bullet and scope, not just a '
    'token. At least one support quote must contain the selected occurrence. Include remote '
    'evidence when needed. occurrence is the zero-based occurrence of that EXACT quote in '
    'the entire document, including overlaps. Include conflicting evidence even if it '
    'contradicts your preferred answer. '
)
UNIT_INSTRUCTION = (
    'Support describes the occurrence even for excluded/negative cases. Select existing '
    'sourceRegistry unitId strings in supportUnitIds and counterUnitIds for the establishing '
    'sentence/bullet and scope, not just a token. Support units together must cover the '
    'entire selected candidate occurrence and include its non-heading line; a heading '
    'alone is insufficient. Include remote evidence when needed. Use only exact unitId '
    'strings from this source; no duplicates or invented IDs. Each support/counter list '
    'allows at most 8 units and at most 4000 source characters in total. Include conflicting '
    'evidence even if it contradicts your preferred answer. '
)
ARM_MAP = {'Q': 'A', 'U': 'B'}
LOCAL_CODES = {'INVALID_UNIT_DECISIONS', 'UNIT_SOURCE_INCOMPLETE', 'INVALID_ARM', 'BATCH_SOURCE_MISMATCH'}


def build_pair(document, frozen):
    registry = build_registry(document, frozen)
    if not registry['complete']:
        raise ValueError('UNIT_SOURCE_INCOMPLETE')
    payloads = {'Q': [], 'U': []}
    for offset in range(0, len(frozen['candidates']), 8):
        batch = frozen['candidates'][offset:offset+8]
        quote = build_payload('B', document, batch)
        body = json.loads(quote['messages'][1]['content'])
        body['sourceRegistry'] = {'sourceDigest': registry['sourceDigest'], 'units': registry['units'],
                                  'candidates': registry['candidates'][offset:offset+8]}
        quote['messages'][1]['content'] = json.dumps(body, ensure_ascii=False)
        unit = deepcopy(quote)
        instruction = unit['messages'][0]['content']
        if instruction.count(QUOTE_INSTRUCTION) != 1:
            raise ValueError('EVIDENCE_INSTRUCTION_BOUNDARY_CHANGED')
        unit['messages'][0]['content'] = instruction.replace(QUOTE_INSTRUCTION, UNIT_INSTRUCTION)
        schema = unit['response_format']['json_schema']
        schema['name'] = 'agentfit_direct_field_units'
        item = schema['schema']['properties']['decisions']['items']
        properties = item['properties']
        del properties['support'], properties['counterEvidence']
        for name in ('supportUnitIds', 'counterUnitIds'):
            properties[name] = {'type': 'array', 'maxItems': 8, 'items': {'type': 'string'}}
        item['required'] = list(properties)
        payloads['Q'].append(quote)
        payloads['U'].append(unit)
    return {'registry': registry, 'payloads': payloads}


def _unit_rows(document, registry, batch, rows):
    expected_ids = [c['id'] for c in batch]
    by_id = {}
    if not isinstance(rows, list) or len(rows) != len(batch):
        raise ValueError('INVALID_UNIT_DECISIONS')
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'id', 'field', 'status', 'supportUnitIds', 'counterUnitIds'}
                or not isinstance(row['id'], str) or row['id'] in by_id
                or not isinstance(row['field'], str) or row['field'] not in (*FIELDS, 'other')
                or not isinstance(row['status'], str) or row['status'] not in STATUSES
                or any(not isinstance(row[key], list) or any(not isinstance(v, str) for v in row[key])
                       for key in ('supportUnitIds', 'counterUnitIds'))):
            raise ValueError('INVALID_UNIT_DECISIONS')
        by_id[row['id']] = row
    if set(by_id) != set(expected_ids):
        raise ValueError('INVALID_UNIT_DECISIONS')
    records, diagnostics = [], []
    for candidate in batch:
        row = by_id[candidate['id']]
        support, counter, issues = [], [], []
        valid, sufficient = False, False
        try:
            linked = resolve_units(registry, row['id'], row['supportUnitIds'], row['counterUnitIds'])
            support = [{k: u[k] for k in ('start', 'end')} for u in linked['supportUnits']]
            counter = [{k: u[k] for k in ('start', 'end')} for u in linked['counterUnits']]
            valid, sufficient = True, linked['contextSufficient']
            issues = linked['issues']
        except SourceContractError as exc:
            # Keep the proposal and raw IDs even when citation references fail.
            issues = [str(exc)]
        verdict = 'needs_confirmation'
        if valid and sufficient and not counter:
            if row['field'] != 'other' and row['status'] == 'confirmed':
                verdict = 'supported'
            elif row['status'] == 'negated' or (row['field'] == 'other' and row['status'] == 'irrelevant'):
                verdict = 'excluded'
        records.append({'id': row['id'], 'raw_field': row['field'], 'raw_status': row['status'],
                        'verdict': verdict, 'candidate': {k: candidate[k] for k in ('start', 'end')},
                        'sourceValue': document[candidate['start']:candidate['end']],
                        'support': support, 'counterEvidence': counter, 'groundingValid': valid})
        diagnostics.append({'id': row['id'], 'citationDefect': not (valid and sufficient),
                            'kind': 'invalid_unit_reference' if not valid else
                                    'insufficient_unit_context' if not sufficient else 'valid_covering',
                            'issues': issues, 'originalResponse': deepcopy(row)})
    return records, diagnostics


def normalize(arm, document, registry, batch, rows):
    validate_registry(registry)
    _validate_frozen(document, {'candidates': batch, 'rejected': []})
    original = {c['id']: c for c in registry['originalFrozen']['candidates']}
    if document != registry['document'] or any(original.get(c['id']) != c for c in batch):
        raise ValueError('BATCH_SOURCE_MISMATCH')
    if arm == 'U':
        return _unit_rows(document, registry, batch, rows)
    if arm != 'Q':
        raise ValueError('INVALID_ARM')
    records = validate_direct(document, {'candidates': batch, 'rejected': []}, rows)
    raw = {r['id']: r for r in rows}
    diagnostics = []
    for record in records:
        audit = audit_legacy_record(document, registry, raw[record['id']], record)
        diagnostics.append({'id': record['id'], 'citationDefect': audit['legacyCitationStatus'] != 'valid_covering',
                            'kind': audit['legacyCitationStatus'], 'issues': audit['issues'],
                            'originalResponse': audit['originalResponse']})
    return records, diagnostics


def _safe_error(exc):
    return str(exc) if type(exc) is ValueError and str(exc) in LOCAL_CODES else error_code(exc)


def run_pair(output, inputs, pair, gate, sender):
    document, frozen, gold = inputs['document'], inputs['frozen'], inputs['gold']['cases']
    expected_ids = [c['id'] for c in frozen['candidates']]
    arms, stopped = {}, False
    for arm, gate_arm in ARM_MAP.items():
        if stopped:
            arms[arm] = {'complete': False, 'error': 'NOT_STARTED_AFTER_FAILURE', 'metrics': None,
                         'calls': 0, 'records': [], 'evidence': []}
            continue
        gate.begin_arm(gate_arm)
        start = time.monotonic()
        records, evidence, batches = [], [], []
        local_seconds, error, metrics = 0.0, None, None
        try:
            for index, payload in enumerate(pair['payloads'][arm]):
                batch = frozen['candidates'][index*8:index*8+8]
                trace = {}
                print(json.dumps({'arm': arm, 'batch': index+1, 'event': 'starting',
                                  'calls_started': gate.started}), flush=True)
                reply, model, pt, ct = sender._send_payload(payload, ('decisions',), _trace=trace, timeout=600)
                if model != MODEL or set(reply) != {'decisions'}:
                    raise ValueError('INVALID_REPLY_ROOT')
                checkpoint = time.monotonic()
                normalized, diagnostic = normalize(arm, document, pair['registry'], batch, reply['decisions'])
                local_seconds += time.monotonic() - checkpoint
                records.extend(normalized)
                evidence.extend(diagnostic)
                result = {'batch': index+1, 'records': normalized, 'evidence': diagnostic,
                          'prompt_tokens': pt, 'completion_tokens': ct,
                          'trace': {k: trace.get(k) for k in ('model', 'finish_reason', 'prompt_tokens',
                              'completion_tokens', 'provider_elapsed_ms', 'request_bytes', 'response_bytes')}}
                batches.append(result)
                write_json(output / f'{arm}-batch-{index+1:02d}.json', result)
                print(json.dumps({'arm': arm, 'batch': index+1, 'event': 'validated',
                                  'records': len(records), 'calls_started': gate.started}), flush=True)
            metrics = score_rows(records, gold, expected_ids)
            metrics['citation_defects'] = sum(d['citationDefect'] for d in evidence)
            metrics['citation_kinds'] = dict(Counter(d['kind'] for d in evidence))
            metrics['citation_defect_ids'] = [d['id'] for d in evidence if d['citationDefect']]
        except Exception as exc:
            error = gate.stop_reason or _safe_error(exc)
            gate.stopped, stopped = True, True
            metrics = None
        calls = [c for c in gate.completed if c['arm'] == gate_arm]
        arms[arm] = {'complete': error is None, 'error': error, 'records': records, 'evidence': evidence,
                     'metrics': metrics, 'calls': len(list(gate.output.glob(f'*-{gate_arm}-started.json'))),
                     'responses_returned': sum(c['returned'] for c in calls),
                     'provider_failures': sum(not c['returned'] for c in calls), 'retries': 0,
                     'model_seconds': sum(c['seconds'] for c in calls), 'wall_seconds': time.monotonic()-start,
                     'local_validation_seconds': local_seconds, 'batches': batches}
        write_json(output / f'{arm}-result.json', arms[arm])
    report = {'comparable': all(a['complete'] for a in arms.values()), 'arms': arms,
              'calls_started': gate.started, 'retries': 0, 'gate_arm_map': ARM_MAP,
              'free_basis': 'unexpired user confirmation; no independent account billing inspection',
              'service_applied': False, 'large_goal_resumed': False}
    write_json(output / 'summary.json', report)
    print(json.dumps({'comparable': report['comparable'], 'calls_started': gate.started,
                      'errors': {a: r['error'] for a, r in arms.items()}}), flush=True)
    return report
