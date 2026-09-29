"""Evaluation-only gold reachability; never provide gold to a model request."""
from copy import deepcopy

from .real_document_holdout import _checks, score_profile


STAGES = ('grounded', 'classified', 'reviewed', 'projected')


class CandidateStageDiagnostics:
    def __init__(self, document: str, checks: list[dict]):
        if type(document) is not str:
            raise ValueError('invalid diagnostic document')
        self._document = document
        self._checks = deepcopy(_checks(checks))
        self._rows = [{
            'check_id': check['id'], 'field': check['field'],
            **dict.fromkeys(STAGES)} for check in self._checks]

    def observe(self, stage: str, state: dict) -> None:
        if stage not in STAGES:
            raise ValueError('invalid diagnostic stage')
        if stage == 'projected':
            for row, check in zip(self._rows, self._checks):
                row[stage] = score_profile(state, [check])['matched'] == 1
            return
        frozen = state if stage == 'grounded' else state['frozen']
        labels = {} if stage == 'grounded' else {
            item['id']: item for item in state['labels']}
        for row, check in zip(self._rows, self._checks):
            if 'expect_null' in check:
                continue
            matched = False
            for item in frozen['candidates']:
                value = self._document[item['start']:item['end']]
                if stage != 'grounded':
                    label = labels[item['id']]
                    if label['field'] != check['field'] or label['status'] != 'confirmed':
                        continue
                if any(term.casefold() in value.casefold() for term in check['contains_any']):
                    matched = True
                    break
            row[stage] = matched

    def summary(self) -> list[dict]:
        result = deepcopy(self._rows)
        for row, check in zip(result, self._checks):
            row['first_unmatched_stage'] = 'none'
            stages = ('projected',) if 'expect_null' in check else STAGES
            for stage in stages:
                if row[stage] is None:
                    row['first_unmatched_stage'] = 'unobserved'
                    break
                if row[stage] is False:
                    row['first_unmatched_stage'] = stage
                    break
        return result
