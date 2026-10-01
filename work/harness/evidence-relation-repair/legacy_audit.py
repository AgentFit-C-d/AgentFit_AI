"""Offline audit of saved evidence; does not repair or reclassify decisions."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import time

from source_registry import SourceContractError, validate_registry, build_registry


def _ground(document, quotes, role):
    """Locate only the requested exact occurrence, including overlaps."""
    if not isinstance(quotes, list) or len(quotes) > 4:
        raise SourceContractError('invalid_legacy_quotes')
    spans, issues = [], []
    for index, quote in enumerate(quotes):
        if (not isinstance(quote, dict) or set(quote) != {'quote', 'occurrence'}
                or not isinstance(quote['quote'], str) or not 1 <= len(quote['quote']) <= 2000
                or not quote['quote'].strip() or type(quote['occurrence']) is not int
                or not 0 <= quote['occurrence'] < 100000):
            raise SourceContractError('invalid_legacy_quote')
        start = -1
        for _ in range(quote['occurrence'] + 1):
            start = document.find(quote['quote'], start + 1)
            if start < 0:
                break
        if start < 0:
            issues.append({'code': 'quote_not_found', 'role': role, 'index': index,
                           'rawQuote': deepcopy(quote)})
        else:
            spans.append({'start': start, 'end': start + len(quote['quote'])})
    return spans, issues


def _match_record(candidate, raw, saved):
    if not isinstance(raw, dict) or not isinstance(saved, dict):
        raise SourceContractError('invalid_record')
    status_keys = [key for key in ('status', 'modelStatus') if key in raw]
    span = saved.get('candidate')
    if (len(status_keys) != 1 or raw.get('id') != candidate['candidateId']
            or saved.get('id') != candidate['candidateId']
            or not isinstance(raw.get('field'), str) or not raw['field']
            or not isinstance(raw.get(status_keys[0]), str) or not raw[status_keys[0]]
            or saved.get('raw_field') != raw['field'] or saved.get('raw_status') != raw[status_keys[0]]
            or not isinstance(span, dict) or set(span) != {'start', 'end'}
            or any(type(span[k]) is not int for k in span) or span != candidate['mentionSpan']
            or saved.get('sourceValue') != candidate['value']
            or not isinstance(saved.get('verdict'), str) or not saved['verdict']):
        raise SourceContractError('raw_saved_candidate_mismatch')


def audit_legacy_record(document: str, registry: dict, raw_row: dict, saved_record: dict) -> dict:
    """Add evidence diagnostics, never a replacement field/status/verdict.

    contextAvailable means the entire registry is available. It does not mean
    the model selected enough context, checked conflicts, or judged semantics.
    """
    validate_registry(registry)
    if document != registry['document']:
        raise SourceContractError('source_identity_mismatch')
    if not isinstance(saved_record, dict):
        raise SourceContractError('invalid_saved_record')
    candidate = next((c for c in registry['candidates'] if c['candidateId'] == saved_record.get('id')), None)
    if candidate is None:
        raise SourceContractError('unknown_candidate_id')
    _match_record(candidate, raw_row, saved_record)
    support, support_issues = _ground(document, raw_row.get('support'), 'support')
    counter, counter_issues = _ground(document, raw_row.get('counterEvidence'), 'counterEvidence')
    grounded = not support_issues and not counter_issues
    # Validate history, do not silently replace a mismatching normalized record.
    if (saved_record.get('support') != support or saved_record.get('counterEvidence') != counter
            or type(saved_record.get('groundingValid')) is not bool
            or saved_record['groundingValid'] != grounded):
        raise SourceContractError('raw_saved_evidence_mismatch')
    span = candidate['mentionSpan']
    covered = any(s['start'] <= span['start'] and span['end'] <= s['end'] for s in support)
    issues = [*support_issues, *counter_issues]
    if not covered:
        issues.append({'code': 'candidate_not_covered', 'role': 'support'})
    if not raw_row['support']:
        issues.append({'code': 'empty_support', 'role': 'support'})
    issues.extend({'code': issue, 'role': 'registry'} for issue in registry['issues'])
    if not registry['complete']:
        status = 'incomplete_context'
    elif not grounded:
        status = 'quote_not_found'
    elif not raw_row['support']:
        status = 'incomplete_context'
    elif not covered:
        status = 'exact_elsewhere'
    else:
        status = 'valid_covering'
    return deepcopy({'originalRecord': saved_record, 'originalResponse': raw_row,
                     'candidatePointer': candidate, 'mentionLocated': True,
                     'contextAvailable': registry['complete'], 'legacyCitationStatus': status,
                     'supportSpans': support, 'counterSpans': counter,
                     'sourceDigest': registry['sourceDigest'], 'issues': issues})


def _unique_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SourceContractError('duplicate_json_key')
            result[key] = value
        return result
    def invalid_constant(_):
        raise SourceContractError('invalid_json_constant')
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (TypeError, json.JSONDecodeError) as exc:
        raise SourceContractError('invalid_json') from exc


def _response_rows(files):
    rows = {'A': [], 'B': []}
    for name in sorted(files):
        match = re.fullmatch(r'calls/\d+-([AB])-response\.json', name)
        if not match:
            if name.endswith('-response.json'):
                raise SourceContractError('unknown_response_file')
            continue
        arm = match[1]
        envelope = _unique_json(files[name])
        try:
            choices = envelope['choices']
            if len(choices) != 1 or choices[0]['finish_reason'] != 'stop':
                raise SourceContractError('incomplete_saved_response')
            content = _unique_json(choices[0]['message']['content'])
            key = 'assessments' if arm == 'A' else 'decisions'
            if set(content) != {key} or not isinstance(content[key], list):
                raise SourceContractError('invalid_saved_response_rows')
            rows[arm].extend(content[key])
        except (KeyError, IndexError, TypeError) as exc:
            raise SourceContractError('invalid_saved_response') from exc
    return rows


def _ids(records):
    if not isinstance(records, list) or any(not isinstance(r, dict) or not isinstance(r.get('id'), str)
                                            for r in records):
        raise SourceContractError('invalid_record_list')
    return [r['id'] for r in records]


def audit_saved_files(files: dict[str, str]) -> dict:
    """Audit a complete saved pair with all original inputs and rows preserved.

    The file-reading CLI separately authenticates bytes against a frozen manifest.
    This function has no filesystem, model, service, or environment dependencies.
    """
    try:
        inputs = _unique_json(files['inputs.json'])
        summary = _unique_json(files['summary.json'])
        document = inputs['document']
        registry = build_registry(document, inputs['frozen'])
        if summary['comparable'] is not True or set(summary['arms']) != {'A', 'B'}:
            raise SourceContractError('incomplete_saved_pair')
        raw_rows = _response_rows(files)
        expected_ids = [c['candidateId'] for c in registry['candidates']]
        arms = {}
        for arm in ('A', 'B'):
            saved = summary['arms'][arm]['records']
            if (summary['arms'][arm]['complete'] is not True or _ids(saved) != expected_ids
                    or _ids(raw_rows[arm]) != expected_ids):
                raise SourceContractError('missing_duplicate_reordered_or_foreign_candidate')
            records = [audit_legacy_record(document, registry, raw, record)
                       for raw, record in zip(raw_rows[arm], saved)]
            by_status = {status: [r['originalRecord']['id'] for r in records if r['legacyCitationStatus'] == status]
                         for status in ('quote_not_found', 'exact_elsewhere', 'incomplete_context', 'valid_covering')}
            defects = [r['originalRecord']['id'] for r in records
                       if r['legacyCitationStatus'] in ('quote_not_found', 'exact_elsewhere')]
            arms[arm] = {'records': records, 'quoteNotFoundIds': by_status['quote_not_found'],
                         'exactElsewhereIds': by_status['exact_elsewhere'], 'citationDefectIds': defects,
                         'heldWithValidCitationIds': [r['originalRecord']['id'] for r in records
                             if r['legacyCitationStatus'] == 'valid_covering'
                             and r['originalRecord']['verdict'] == 'needs_confirmation'],
                         'counts': {'records': len(records), 'rawResponses': len(raw_rows[arm]),
                                    'citationDefects': len(defects),
                                    **{k: len(v) for k, v in by_status.items()}}}
    except (KeyError, TypeError) as exc:
        raise SourceContractError('invalid_saved_pair') from exc
    return {'version': 'legacy-evidence-audit-v1', 'registry': registry, 'arms': arms,
            'originalInputs': deepcopy(inputs), 'originalSummary': deepcopy(summary),
            'newModelCalls': 0, 'serviceApplied': False}


def _safe_relative(name):
    if not isinstance(name, str):
        raise SourceContractError('invalid_manifest_path')
    value = PurePosixPath(name.replace('\\', '/'))
    if value.is_absolute() or '..' in value.parts or ':' in name or value.suffix != '.json':
        raise SourceContractError('invalid_manifest_path')
    return value.as_posix()


def _check_expected(report, manifest):
    if report['registry']['sourceDigest'] != manifest['source_sha256']:
        raise SourceContractError('source_digest_mismatch')
    mappings = {'quoteNotFoundIds': 'quote_not_found_ids',
                'exactElsewhereIds': 'exact_but_wrong_occurrence_ids',
                'citationDefectIds': 'citation_defect_ids',
                'heldWithValidCitationIds': 'held_with_valid_citation_ids'}
    for arm in ('A', 'B'):
        actual, expected = report['arms'][arm], manifest['arms'][arm]
        if actual['counts']['records'] != expected['records']:
            raise SourceContractError('expected_record_count_mismatch')
        for new_key, old_key in mappings.items():
            if actual[new_key] != expected[old_key]:
                raise SourceContractError(f'expected_citation_audit_mismatch:{arm}:{new_key}')


def replay(source: Path, manifest_path: Path, output: Path) -> dict:
    """Hash-check originals, audit, and write a NEW directory without overwrites.

    audit.json is written last; a partial filesystem write cannot look complete.
    No credential, provider, service, or network module is loaded by this runner.
    """
    started = time.perf_counter()
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if output.is_relative_to(source):
        raise SourceContractError('output_must_be_outside_originals')
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = _unique_json(manifest_bytes.decode('utf-8'))
    originals, hashes = {}, {}
    for raw_name, expected_digest in manifest['input_sha256'].items():
        name = _safe_relative(raw_name)
        path = (source / name).resolve()
        if name in originals or not path.is_relative_to(source):
            raise SourceContractError('duplicate_or_escaping_manifest_path')
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected_digest:
            raise SourceContractError(f'input_hash_mismatch:{name}')
        originals[name], hashes[name] = content, digest
    report = audit_saved_files({name: content.decode('utf-8') for name, content in originals.items()})
    _check_expected(report, manifest)
    output.mkdir(parents=True, exist_ok=False)
    for name, content in originals.items():
        destination = output / 'originals' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as handle:
            handle.write(content)
        if destination.read_bytes() != content or (source / name).read_bytes() != content:
            raise SourceContractError('original_or_archive_bytes_changed')
    with (output / 'manifest.json').open('xb') as handle:
        handle.write(manifest_bytes)
    report['preservation'] = {'originalFilesUnchanged': True, 'copiedFiles': len(originals),
                              'sha256': hashes, 'candidateRecordsChanged': 0, 'rawRowsLost': 0}
    report['offlineSeconds'] = time.perf_counter() - started
    with (output / 'audit.json').open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = replay(args.source, args.manifest, args.output)
    print(json.dumps({'arms': {arm: value['counts'] for arm, value in result['arms'].items()},
                      'preservation': {k: v for k, v in result['preservation'].items() if k != 'sha256'},
                      'newModelCalls': result['newModelCalls'], 'serviceApplied': result['serviceApplied'],
                      'offlineSeconds': result['offlineSeconds']}, ensure_ascii=True))


if __name__ == '__main__':
    main()
