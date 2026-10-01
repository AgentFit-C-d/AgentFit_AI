"""Opt-in review with field-bounded candidate IDs and ten separate coverage checks."""
from .candidate_field_semantics import field_semantics_instructions
from .candidate_first_profile import _MENTION_INSTRUCTION, _source_mention, validate_candidate_labels
from .candidate_split_review import _payload, _unique_subset, _valid_rejection_reasons, _REJECTION_INSTRUCTION
from .deepseek_evaluation import MODEL
from .diagnostics import safe_code
from .operation_candidates import _sender, _validate_frozen
from .profile import FIELDS
from .solar import AnalysisError, _reject_sensitive


_RUNTIME_PURPOSE = (
    'Runtime purpose clarification. Judge the exact selected span, not just the heading of its section. '
    'A technology/adopted-stack list can explicitly state two different facts: the name of a tool and '
    'the runtime operation it provides for the target product. If the selected words name that explicitly '
    'stated product operation, they can belong to features even when the same bullet also names an '
    'implementation technology. Do not move the operation into a technology field or reject it solely '
    'because it occurs in a stack list. Conversely, a bare library/provider name does not establish a '
    "feature. Require the source to state the operation; never infer a tool's usual capabilities from "
    'outside knowledge. Development-only tasks (linting, testing, formatting, building code), '
    'deployment/self-hosting instructions, marketing benefits and invitations to try/sign up are not '
    'runtime product features. A technology-purpose association does not override scope or certainty: '
    'optional, rejected, explicitly later or other-product operations remain unconfirmed. Apply the same '
    'distinction when checking coverage. Supported user-visible or internal product operations can '
    'qualify; software-development workflow is not a product operation merely because it contains a verb.'
)


def review_candidates_by_field(document, frozen, labels, key, *, transport=None,
                               review_model=MODEL, review_calls=None, review_reasons=None):
    """Return the existing review contract only after every field is checked.

    At most 21 candidate batches plus ten coverage calls. Callers own the shared
    analysis budget and process deadline; this function never retries or falls back.
    """
    if any(value is not None and type(value) is not list for value in (review_calls, review_reasons)):
        raise ValueError('invalid field review collector')
    sender = _sender(document, key, review_model, transport)
    _reject_sensitive(document, key)
    _validate_frozen(document, frozen)
    validate_candidate_labels(frozen, labels)
    semantics = field_semantics_instructions('explicit-v1')
    spans = {item['id']: _source_mention(document, item) for item in frozen['candidates']}
    grouped = {field: [] for field in FIELDS}
    for label in labels:
        if label['status'] == 'confirmed' and label['field'] in grouped:
            grouped[label['field']].append({**spans[label['id']], **label})

    def instruction(text, field):
        value = text + '\n' + semantics
        return value + ('\n' + _RUNTIME_PURPOSE if field == 'features' else '')

    def send(payload, stage, field, validate, *, batch_index=None, candidate_count=None):
        row = {'stage': stage, 'field': field, 'batch_index': batch_index,
               'candidate_count': candidate_count, 'validated': False, 'error': None}
        try:
            required = tuple(payload['response_format']['json_schema']['schema']['required'])
            reply, returned_model, _, _ = sender._send_payload(payload, required, timeout=600)
            if returned_model != review_model:
                raise AnalysisError('PROVIDER_MODEL')
            if not validate(reply):
                raise ValueError('invalid field review contract')
            row['validated'] = True
            return reply
        except AnalysisError as error:
            row['error'] = safe_code(error.code)
            raise
        except Exception:
            row['error'] = 'INVALID_REVIEW_CONTRACT'
            raise
        finally:
            if review_calls is not None:
                review_calls.append(row)

    wrong, batch_index = [], 0
    for field in FIELDS:
        for offset in range(0, len(grouped[field]), 20):
            batch_index += 1
            batch = grouped[field][offset:offset+20]
            ids = [item['id'] for item in batch]
            array = {'type': 'array', 'maxItems': len(ids), 'items': {'type': 'string', 'enum': ids}}
            properties = {
                'checkedCandidateIds': {**array, 'minItems': len(ids)}, 'wrongCandidateIds': array,
                'rejectionReasons': {'type': 'array', 'maxItems': len(ids), 'items': {
                    'type': 'object', 'properties': {'id': {'type': 'string', 'enum': ids},
                    'reason': {'type': 'string', 'enum': ['wrong_field', 'not_current',
                                                       'not_product_fact', 'insufficient_evidence']}},
                    'required': ['id', 'reason'], 'additionalProperties': False}}}
            payload = _payload('agentfit_field_candidate_review', instruction(
                'Verify only the supplied confirmed candidates for targetField against the whole '
                'document. Reject a candidate whose claimed field or certainty is unsupported. '
                'Other fields are not under review in this request. Check every supplied ID in order; '
                'wrongCandidateIds may contain only supplied IDs. Do not check omissions here, '
                'invent values or deduplicate valid occurrences. ' + _MENTION_INSTRUCTION +
                _REJECTION_INSTRUCTION, field),
                {'document': document, 'targetField': field, 'selections': batch}, properties)
            reply = send(payload, 'candidate_batch', field, lambda result: (
                result['checkedCandidateIds'] == ids and
                _unique_subset(result['wrongCandidateIds'], ids) and _valid_rejection_reasons(result)),
                batch_index=batch_index, candidate_count=len(batch))
            wrong.extend(reply['wrongCandidateIds'])
            if review_reasons is not None:
                review_reasons.extend({'field': field, 'batch_index': batch_index, **reason}
                                      for reason in reply['rejectionReasons'])

    rejected, checked, missing = set(wrong), [], []
    for field in FIELDS:
        values = list(dict.fromkeys(item['value'] for item in grouped[field] if item['id'] not in rejected))
        payload = _payload('agentfit_field_source_coverage', instruction(
            'Check omissions for targetField only against the whole document. Set missing to true '
            'when an explicitly confirmed current-product fact in that field is not represented '
            'by confirmedValues. An empty list does not imply that the source lacks a fact. '
            'Do not require tentative, negative, historical, example or other-product claims. '
            'A representative feature can cover equivalent descriptions of that operation. '
            'Do not invent technologies from generic features. Return the exact targetField and '
            'a boolean missing; do not emit values, quotes, IDs or other fields.', field),
            {'document': document, 'targetField': field, 'confirmedValues': values},
            {'field': {'type': 'string', 'enum': [field]}, 'missing': {'type': 'boolean'}})
        reply = send(payload, 'source_coverage', field, lambda result: (
            set(result) == {'field', 'missing'} and result['field'] == field and type(result['missing']) is bool))
        checked.append(reply['field'])
        if reply['missing']:
            missing.append(field)
    return {'checkedFields': checked, 'missingFields': missing, 'wrongCandidateIds': wrong}
