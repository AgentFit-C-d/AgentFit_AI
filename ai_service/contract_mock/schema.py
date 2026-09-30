"""Validate mock traffic against the repository's unmodified public contract."""
from functools import lru_cache
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from agentfit_ai.profile import FIELDS


class ContractError(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code
        super().__init__(code)


def reject_sensitive(value):
    """Known credential patterns only; not a comprehensive data-loss scanner."""
    if isinstance(value, dict):
        for child in value.values():
            reject_sensitive(child)
    elif isinstance(value, list):
        for child in value:
            reject_sensitive(child)
    elif isinstance(value, str) and re.search(
            r'(?i)(?:api[_-]?key|password|access[_-]?token|secret)\s*[:=]\s*[\"\']?[^\s\"\']{8,}'
            r'|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', value):
        raise ContractError(422, 'SENSITIVE_INPUT')


@lru_cache(maxsize=1)
def schemas():
    source = Path(__file__).resolve().parents[2] / 'Docs/api/openapi.phase1.json'
    document = json.loads(source.read_text(encoding='utf-8'))
    def local_refs(value):
        if isinstance(value, dict):
            if '$ref' in value and not value['$ref'].startswith('#/'):
                raise ValueError('EXTERNAL_SCHEMA_REFERENCE')
            for child in value.values():
                local_refs(child)
        elif isinstance(value, list):
            for child in value:
                local_refs(child)
    local_refs(document)
    return document['components']['schemas']


@lru_cache(maxsize=32)
def _validator(name):
    if name not in schemas():
        raise ContractError(422, 'INVALID_INPUT')
    schema = {'$ref': '#/components/schemas/' + name, 'components': {'schemas': schemas()}}
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _check_unicode(value):
    # JSON escape syntax can decode to a lone surrogate that cannot be sent as UTF-8.
    if isinstance(value, str):
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ContractError(422, 'INVALID_INPUT') from None
    elif isinstance(value, dict):
        for key, child in value.items():
            _check_unicode(key)
            _check_unicode(child)
    elif isinstance(value, list):
        for child in value:
            _check_unicode(child)


def check(name: str, value: object) -> None:
    _check_unicode(value)
    if next(_validator(name).iter_errors(value), None) is not None:
        raise ContractError(422, 'INVALID_INPUT')


def check_review(profile, review):
    """Structural v2 metadata validation; no claim of semantic correctness."""
    try:
        if type(review) is not dict or set(review) != {'contract', 'fieldStates', 'questions'}:
            raise ValueError
        states, questions = review['fieldStates'], review['questions']
        if (review['contract'] != 'confirmation-v2' or type(states) is not dict or set(states) != set(FIELDS)
                or any(type(v) is not str or v not in ('unknown', 'suggested', 'unresolved') for v in states.values())
                or type(questions) is not list or len(questions) > 10):
            raise ValueError
        seen = set()
        for field, state in states.items():
            if (state == 'suggested' and profile['data'][field] is None
                    or state == 'unknown' and profile['data'][field] is not None):
                raise ValueError
        for question in questions:
            if type(question) is not dict or set(question) != {'field', 'reason', 'questionId'}:
                raise ValueError
            field, reason = question['field'], question['reason']
            if (type(field) is not str or field not in FIELDS or field in seen
                    or type(reason) is not str or question['questionId'] != 'confirm_' + field
                    or not (states[field] == 'suggested' and reason == 'CONFIRM_SUGGESTION'
                            or states[field] == 'unresolved' and reason in ('REVIEW_ISSUE', 'CANDIDATE_MISSING'))):
                raise ValueError
            seen.add(field)
        if seen != {f for f in FIELDS if states[f] != 'unknown'}:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ContractError(502, 'AI_INVALID_OUTPUT') from None
