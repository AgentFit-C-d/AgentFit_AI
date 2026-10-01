"""Offline source position registry; never assigns semantic decisions."""
from copy import deepcopy
import hashlib
import re


MAX_SOURCE_CHARS = 24000
MAX_UNITS = 1000
MAX_SELECTION_UNITS = 8
MAX_SELECTION_CHARS = 4000


class SourceContractError(ValueError):
    """Invalid source identity, offsets, or references; no fallback is allowed."""


def _validate_frozen(document, frozen):
    if not isinstance(document, str) or not isinstance(frozen, dict):
        raise SourceContractError('invalid_source_input')
    if not isinstance(frozen.get('candidates'), list) or not isinstance(frozen.get('rejected'), list):
        raise SourceContractError('invalid_frozen_input')
    seen = set()
    for candidate in frozen['candidates']:
        if not isinstance(candidate, dict):
            raise SourceContractError('invalid_candidate')
        cid, start, end = candidate.get('id'), candidate.get('start'), candidate.get('end')
        if not isinstance(cid, str) or not cid or cid in seen:
            raise SourceContractError('invalid_or_duplicate_candidate_id')
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(document):
            raise SourceContractError('invalid_candidate_span')
        seen.add(cid)


def _make_units(document, digest):
    units, offset, fence = [], 0, None
    for line in document.splitlines(keepends=True):
        end = offset + len(line)
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\r\n'))
        heading = None
        if fence is None:
            if marker:
                fence = (marker[1][0], len(marker[1]))
            else:
                heading = re.match(r'^ {0,3}(#{1,6})(?:[ \t]+|$)', line)
        elif marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
            fence = None
        unit = {'unitId': f'{digest}:{offset}:{end}', 'start': offset, 'end': end,
                'text': line, 'kind': 'heading' if heading else 'line'}
        if heading:
            unit['level'] = len(heading[1])
        units.append(unit)
        offset = end
    return units


def build_registry(document: str, frozen: dict) -> dict:
    """Keep the full source/frozen input and derive exact, source-bound line links.

    Offsets count Unicode code points. Oversized sources remain intact, but no
    partial unit index is advertised as complete. Headings are structural ATX
    metadata only; they never replace a candidate's original occurrence.
    """
    _validate_frozen(document, frozen)
    digest = hashlib.sha256(document.encode('utf-8')).hexdigest()
    issues = []
    if len(document) > MAX_SOURCE_CHARS:
        issues.append('source_char_limit')
    if len(document.splitlines(keepends=True)) > MAX_UNITS:
        issues.append('source_unit_limit')
    units = [] if issues else _make_units(document, digest)
    candidates = []
    for original in frozen['candidates']:
        start, end = original['start'], original['end']
        local = [u['unitId'] for u in units if u['start'] < end and start < u['end']]
        headings = []
        for unit in units:
            if unit['start'] > start:
                break
            if unit['kind'] == 'heading':
                headings = [h for h in headings if h['level'] < unit['level']]
                headings.append(unit)
        context_start, context_end = max(0, start - 240), min(len(document), end + 240)
        candidates.append({'candidateId': original['id'], 'mentionSpan': {'start': start, 'end': end},
                           'value': document[start:end], 'localUnitIds': local,
                           'headingUnitIds': [h['unitId'] for h in headings],
                           'context': {'start': context_start, 'end': context_end,
                                       'text': document[context_start:context_end]}})
    return {'version': 'source-registry-v1', 'document': document, 'sourceDigest': digest,
            'originalFrozen': deepcopy(frozen), 'units': units, 'candidates': candidates,
            'complete': not issues, 'issues': issues}


def validate_registry(registry: dict) -> None:
    """Detect stale or edited source links before they can be consumed."""
    if not isinstance(registry, dict):
        raise SourceContractError('invalid_registry')
    expected = build_registry(registry.get('document'), registry.get('originalFrozen'))
    if registry != expected:
        raise SourceContractError('registry_identity_or_content_mismatch')


def _select(registry, ids):
    if not isinstance(ids, list) or len(ids) > MAX_SELECTION_UNITS:
        raise SourceContractError('selection_unit_limit_or_type')
    if any(not isinstance(uid, str) for uid in ids) or len(set(ids)) != len(ids):
        raise SourceContractError('invalid_or_duplicate_unit_id')
    index = {u['unitId']: u for u in registry['units']}
    if any(uid not in index for uid in ids):
        raise SourceContractError('unknown_or_foreign_unit_id')
    selected = [index[uid] for uid in ids]
    if sum(len(u['text']) for u in selected) > MAX_SELECTION_CHARS:
        raise SourceContractError('selection_char_limit')
    return selected


def _covers(units, span):
    cursor = span['start']
    for unit in sorted(units, key=lambda u: u['start']):
        if unit['start'] > cursor:
            break
        cursor = max(cursor, unit['end'])
        if cursor >= span['end']:
            return True
    return False


def resolve_units(registry: dict, candidate_id: str,
                  support_ids: list[str], counter_ids: list[str]) -> dict:
    """Resolve selected units mechanically. Sufficient context is not a verdict."""
    validate_registry(registry)
    candidate = next((c for c in registry['candidates'] if c['candidateId'] == candidate_id), None)
    if candidate is None:
        raise SourceContractError('unknown_candidate_id')
    supports, counters = _select(registry, support_ids), _select(registry, counter_ids)
    covered = _covers(supports, candidate['mentionSpan'])
    issues = list(registry['issues'])
    if not supports:
        issues.append('empty_support')
    if not covered:
        issues.append('candidate_not_covered')
    nonheading = any(u['kind'] != 'heading' and u['start'] < candidate['mentionSpan']['end']
                     and candidate['mentionSpan']['start'] < u['end'] for u in supports)
    if supports and not nonheading:
        issues.append('no_candidate_line_context')
    return deepcopy({'sourceDigest': registry['sourceDigest'], 'candidate': candidate,
                     'supportUnits': supports, 'counterUnits': counters,
                     'candidateCovered': covered, 'contextAvailable': registry['complete'],
                     'contextSufficient': registry['complete'] and covered and nonheading,
                     'issues': issues})
