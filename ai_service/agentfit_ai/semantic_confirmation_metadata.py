"""Consistency checks at AI and storage boundaries; not a semantic oracle."""
import re
from .candidate_semantic_assessment import check_decision_records
from .profile import FIELDS, MAX_TEXT_CODE_POINTS
from .source_name_expressions import source_name_expression


def unresolved_decision_fields(records):
    fields = set()
    for row in records:
        if row['decision'] == 'needs_confirmation' and row['field'] != 'other':
            fields.add(row['field'])
    return fields


def unassigned_decision_questions(records):
    ids = [r['id'] for r in records if r['decision'] == 'needs_confirmation' and r['field'] == 'other']
    return [{'questionId': 'review_unassigned', 'candidateIds': ids}] if ids else []


def check_unassigned_questions(records, questions):
    if type(questions) is not list or questions != unassigned_decision_questions(records):
        raise ValueError('UNASSIGNED_REVIEW_OBLIGATION_MISSING')


def check_decision_profile(profile, records, *, document=None, document_id=None, states=None):
    if type(records) is not list or any(type(r) is not dict for r in records):
        raise ValueError('INVALID_SEMANTIC_ASSESSMENT')
    bindings = {'sourceValue', 'documentId'}
    checked = check_decision_records([{k: v for k, v in r.items() if k not in bindings}
                                      for r in records], document=document)
    if any(re.fullmatch(r'C\d{3}', r['id'], flags=re.ASCII) is None for r in checked):
        raise ValueError('INVALID_SEMANTIC_CANDIDATE_ID')
    for row, incoming in zip(checked, records):
        if bool(set(incoming) & bindings) and not bindings <= set(incoming):
            raise ValueError('INVALID_SEMANTIC_SOURCE_BINDING')
        span = row['candidate']
        if document is not None:
            value, source_id = document[span['start']:span['end']], document_id
            if (bindings <= set(incoming) and
                    (incoming['sourceValue'] != value or incoming['documentId'] != source_id)):
                raise ValueError('INVALID_SEMANTIC_SOURCE_BINDING')
        else:
            value, source_id = incoming.get('sourceValue'), incoming.get('documentId')
        if (type(value) is not str or not value.strip() or not 1 <= len(value) <= MAX_TEXT_CODE_POINTS or
                len(value) != span['end'] - span['start'] or type(source_id) is not str or
                not source_id or len(source_id) > 200):
            raise ValueError('INVALID_SEMANTIC_SOURCE_BINDING')
        value.encode('utf-8'); source_id.encode('utf-8')
        row.update(sourceValue=value, documentId=source_id)
    if len({r['documentId'] for r in checked}) > 1:
        raise ValueError('INVALID_SEMANTIC_SOURCE_BINDING')
    if states is not None and any(states.get(f) != 'unresolved' for f in unresolved_decision_fields(checked)):
        raise ValueError('SEMANTIC_REVIEW_OBLIGATION_MISSING')
    for field in FIELDS:
        value, spans = profile['data'][field], profile['evidence'][field]
        if value is None:
            if spans: raise ValueError('UNSUPPORTED_SEMANTIC_PROFILE')
            continue
        candidates = [r for r in checked if r['field'] == field and r['decision'] == 'supported']
        values = value if type(value) is list else [value]
        covered = set()
        for span in spans:
            matches = [r for r in candidates if r['candidate'] == {k: span[k] for k in ('start', 'end')}
                       and r['documentId'] == span['documentId'] and r['sourceValue'] in values]
            if not matches:
                # Preserve only the existing source-written parenthetical-name rule.
                if field != 'project_name' or type(value) is not str or len(spans) != 1:
                    raise ValueError('UNSUPPORTED_SEMANTIC_PROFILE')
                entries = [(r['sourceValue'], {'start': r['candidate']['start'] - span['start'],
                                               'end': r['candidate']['end'] - span['start']})
                           for r in candidates if r['documentId'] == span['documentId'] and
                           span['start'] <= r['candidate']['start'] < r['candidate']['end'] <= span['end']]
                if (span['end'] - span['start'] != len(value) or
                        source_name_expression(value, entries) != (value, {'start': 0, 'end': len(value)}) or
                        states is not None and states[field] != 'unresolved'):
                    raise ValueError('UNSUPPORTED_SEMANTIC_PROFILE')
                covered.add(value)
            else:
                covered.update(r['sourceValue'] for r in matches)
        if not values or covered != set(values):
            raise ValueError('UNSUPPORTED_SEMANTIC_PROFILE')
    return checked
