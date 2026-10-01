"""Status-text-only comparison. Existing service, gate and scoring are unchanged."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT/'specs/ai-developer/status-definition-unification'
_spec = importlib.util.spec_from_file_location('status_previous_evaluation',
    ROOT/'work/harness/classification-instruction-evaluation/evaluate.py')
previous = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(previous)
compare, MODEL = previous.compare, previous.MODEL
ARMS = ('UC', 'US')


def unify_status(system):
    edits = json.loads((SPEC/'status-edits.json').read_bytes().decode('utf-8'))
    definition = (SPEC/'status-definition.txt').read_bytes().decode('utf-8')
    if not definition.strip() or '\r' in definition:
        raise ValueError('INVALID_STATUS_DEFINITION')
    for i, edit in enumerate(edits):
        if system.count(edit['old']) != 1 or system.count(edit['old']+edit['anchor']) != 1:
            raise ValueError('STATUS_BOUNDARY_CHANGED')
        system = system.replace(edit['old'], definition if i == 0 else '', 1)
    return system


def prepare_package(prior):
    documents, jobs = {}, []
    if set(prior['documents']) != {'FR','LS'}:
        raise ValueError('INVALID_DOCUMENTS')
    for doc_id in ('FR','LS'):
        source = prior['documents'][doc_id]
        uc = deepcopy(source['pair']['payloads']['U+C'])
        if len(uc) != 2 or len(source['frozen']['candidates']) != 16 or len(source['gold']) != 16:
            raise ValueError('INVALID_PACKAGE')
        us = deepcopy(uc)
        for payload in us:
            payload['messages'][0]['content'] = unify_status(payload['messages'][0]['content'])
        documents[doc_id] = {k:deepcopy(source[k]) for k in ('document','frozen','gold')}
        documents[doc_id]['pair'] = {'registry':deepcopy(source['pair']['registry']),
                                     'payloads':{'UC':uc,'US':us}}
        for arm in (ARMS if doc_id=='FR' else ARMS[::-1]):
            for i,payload in enumerate(documents[doc_id]['pair']['payloads'][arm],1):
                jobs.append({'docId':doc_id,'arm':arm,'batch':i,'payload':payload})
    return {'documents':documents,'jobs':jobs,'arm_labels':{
        'UC':'original U+C system from saved requests','US':'U+C with one unified status definition'}}


def diagnostics(records, gold, document):
    by_id = {r['id']:r for r in records}
    scored = {g['candidateId'] for g in gold if g['scored']}
    other = [r for r in records if r['raw_field']=='other' and r['raw_status']=='confirmed']
    special = {}
    lines = document.splitlines(keepends=True)
    for g in gold:
        if g['scored'] and g['expectedStatus'] != 'negated':
            continue
        row = by_id.get(g['candidateId'])
        if row is None:
            special[g['caseId']] = {'unassessable':True}
            continue
        entry = deepcopy(row)
        entry['scored'] = g['scored']
        entry['support_text'] = [document[s['start']:s['end']] for s in row['support']]
        entry['counter_text'] = [document[s['start']:s['end']] for s in row['counterEvidence']]
        entry['review_lines'] = []
        for line in g['reviewContextLines']:
            start = sum(map(len,lines[:line-1]))
            end = start+len(lines[line-1])
            entry['review_lines'].append({'line':line,'start':start,'end':end,'text':lines[line-1],
                'selected_as_support':any(s['start']<=start and s['end']>=end for s in row['support']),
                'selected_as_counter':any(s['start']<=start and s['end']>=end for s in row['counterEvidence'])})
        special[g['caseId']] = entry
    return {'other_confirmed_total':len(other),
            'other_confirmed_scored':sum(r['id'] in scored for r in other),
            'special_cases':special}
