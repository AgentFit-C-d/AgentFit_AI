"""Select source representatives without hiding unrepresented feature candidates."""

from .candidate_first_profile import _source_mention, validate_candidate_labels
from .candidate_split_review import _payload, _unique_subset
from .deepseek_evaluation import MODEL, NVIDIA_REVIEW_MODELS, NvidiaAnalyzer, post_nvidia
from .diagnostics import safe_code
from .profile import MAX_ARRAY_ITEMS, MAX_TEXT_CODE_POINTS
from .solar import AnalysisError, SolarAnalyzer, post_solar


def _feature_candidates(document, frozen, labels):
    if (type(document) is not str or not document.strip() or len(document) > 100_000 or
            type(frozen) is not dict or type(frozen.get('candidates')) is not list or
            len(frozen['candidates']) > 240 or type(frozen.get('rejected')) is not list):
        raise ValueError('invalid feature curation input')
    try:
        validate_candidate_labels(frozen, labels)
    except (KeyError, TypeError):
        raise ValueError('invalid feature curation labels') from None
    by_id = {label['id']: label for label in labels}
    candidates = []
    for item in frozen['candidates']:
        mention = _source_mention(document, item)
        label = by_id[item['id']]
        if label['field'] == 'features' and label['status'] == 'confirmed':
            candidates.append(mention)
    return candidates


def _validate_partition(candidates, partition, *, allow_duplicate_values=False):
    if type(partition) is not dict or set(partition) != {'groups', 'unrepresentedIds'}:
        raise ValueError('invalid feature partition')
    groups, unrepresented = partition['groups'], partition['unrepresentedIds']
    by_id = {item['id']: item for item in candidates}
    if (type(groups) is not list or not 1 <= len(groups) <= MAX_ARRAY_ITEMS or
            not _unique_subset(unrepresented, by_id)):
        raise ValueError('invalid feature partition')
    assigned = set(unrepresented)
    representatives, values = set(), set()
    for group in groups:
        if type(group) is not dict or set(group) != {'representativeId', 'memberIds'}:
            raise ValueError('invalid feature group')
        representative, members = group['representativeId'], group['memberIds']
        if (type(representative) is not str or not _unique_subset(members, by_id) or
                not members or representative not in members or assigned.intersection(members)):
            raise ValueError('invalid feature group')
        value = by_id[representative]['value']
        if (not value.strip() or len(value) > MAX_TEXT_CODE_POINTS or
                (value in values and not allow_duplicate_values)):
            raise ValueError('invalid feature representative')
        assigned.update(members)
        representatives.add(representative)
        values.add(value)
    if assigned != set(by_id):
        raise ValueError('incomplete feature partition')
    return [item['id'] for item in candidates if item['id'] in representatives]


def _coalesce_representatives(candidates, partition):
    """Combine only identical source values after validating all assignments."""
    order = {item['id']: index for index, item in enumerate(candidates)}
    by_id = {item['id']: item for item in candidates}
    by_value = {}
    for group in sorted(partition['groups'], key=lambda row: order[row['representativeId']]):
        representative = group['representativeId']
        value = by_id[representative]['value']
        combined = by_value.setdefault(value, {
            'representativeId': representative, 'memberIds': []})
        combined['memberIds'].extend(group['memberIds'])
    normalized = {'groups': list(by_value.values()),
                  'unrepresentedIds': list(partition['unrepresentedIds'])}
    for group in normalized['groups']:
        group['memberIds'].sort(key=order.__getitem__)
    _validate_partition(candidates, normalized)
    return normalized


def validate_feature_curation(document, frozen, reviewed_labels, curation):
    """Revalidate a complete curation against the current reviewed source positions."""
    candidates = _feature_candidates(document, frozen, reviewed_labels)
    if type(curation) is not dict or set(curation) != {
            'groups', 'unrepresentedIds', 'checkedCandidateIds', 'uncoveredIds'}:
        raise ValueError('invalid feature curation')
    selected = _validate_partition(candidates, {
        name: curation[name] for name in ('groups', 'unrepresentedIds')})
    ids = [item['id'] for item in candidates]
    if (curation['checkedCandidateIds'] != ids or
            not _unique_subset(curation['uncoveredIds'], ids) or
            set(selected).intersection(curation['uncoveredIds'])):
        raise ValueError('invalid feature coverage')
    uncovered = set(curation['unrepresentedIds']) | set(curation['uncoveredIds'])
    return {'selectedIds': selected, 'uncoveredIds': [cid for cid in ids if cid in uncovered],
            'candidateCount': len(ids)}


def _propose_feature_partition(document, candidates, key, *, model, transport,
                               call_trace, previous_curation=None):
    """Generate and strictly normalize a complete partition in one request."""
    ids = [item['id'] for item in candidates]
    id_array = {'type': 'array', 'maxItems': len(ids),
                'items': {'type': 'string', 'enum': ids}}
    solar = model == 'solar-pro4'
    analyzer = (SolarAnalyzer(key, transport=transport or post_solar) if solar else
                NvidiaAnalyzer(key, model=model, transport=transport or post_nvidia))

    def request(payload, stage, validate):
        trace = {}
        row = {'stage': stage, 'candidate_count': len(ids), 'validated': False}
        try:
            required = tuple(payload['response_format']['json_schema']['schema']['required'])
            reply, actual_model, _, _ = analyzer._send_payload(
                payload, required, timeout=600, _trace=trace)
            if not (actual_model.startswith('solar-pro4') if solar else actual_model == model):
                raise AnalysisError('PROVIDER_MODEL')
            validate(reply)
            row['validated'] = True
            return reply
        except AnalysisError as error:
            row['error'] = safe_code(error.code)
            raise
        except ValueError:
            row['error'] = 'INVALID_FEATURE_CURATION'
            raise
        finally:
            if call_trace is not None:
                for name in ('model', 'finish_reason', 'prompt_tokens', 'completion_tokens',
                             'provider_elapsed_ms', 'request_bytes', 'response_bytes'):
                    row[name] = trace.get(name)
                call_trace.append(row)

    instructions = (
        'Select up to 30 representative feature occurrences from these already-reviewed '
        'current-product operations. Return only supplied IDs, never new wording or offsets. '
        'Group equivalent descriptions, repeated names and suboperations only when the '
        'representative phrase in its source context actually covers their capabilities. '
        'Prefer concrete product actions to bare labels. Do not force independent capabilities '
        'into a group just to reach 30. Put candidates not represented in unrepresentedIds. '
        'Every supplied candidate must occur exactly once, either in one memberIds array '
        'or in unrepresentedIds. Every representativeId must belong to its own memberIds. '
        'Representatives must have different source values and each value must be at most '
        '200 Unicode code points. Source context clarifies an occurrence; it does not '
        'authorize selecting a different occurrence or inventing a broader capability.')
    data = {'document': document, 'candidates': candidates}
    stage = 'feature_grouping'
    if previous_curation is not None:
        from .candidate_feature_relations import _VALUE_CONTEXT_INSTRUCTION
        instructions += (
            ' A prior complete partition and its unresolved occurrence IDs are provided '
            'as previousCuration. Rebuild the partition once to address those gaps. '
            'Consider every supplied occurrence, including previously represented ones. '
            'The prior review is feedback, not ground truth: you may change representatives '
            'and split or merge groups when the source supports it. Preserve valid '
            'relationships where appropriate, but do not invent broader capabilities or '
            'force distinct operations together to erase unresolved IDs. Keep occurrences '
            'in unrepresentedIds when no valid source representative fits the 30-item limit. '
            + _VALUE_CONTEXT_INSTRUCTION)
        data['previousCuration'] = {name: previous_curation[name]
                                   for name in ('groups', 'unrepresentedIds', 'uncoveredIds')}
        stage = 'feature_regrouping'
    grouping = _payload('agentfit_' + stage, instructions, data,
        {'groups': {'type': 'array', 'minItems': 1, 'maxItems': MAX_ARRAY_ITEMS, 'items': {
            'type': 'object', 'properties': {
                'representativeId': {'type': 'string', 'enum': ids},
                'memberIds': {**id_array, 'minItems': 1}},
            'required': ['representativeId', 'memberIds'], 'additionalProperties': False}},
         'unrepresentedIds': id_array})
    partition = request(grouping, stage,
        lambda reply: _validate_partition(candidates, reply, allow_duplicate_values=True))
    return _coalesce_representatives(candidates, partition)


def curate_reviewed_features(document, frozen, reviewed_labels, key, *,
                             model=MODEL, transport=None, call_trace=None):
    """Use at most two calls to select and verify source representatives on overflow."""
    if (type(key) is not str or not key.strip() or
            type(model) is not str or model not in ('solar-pro4', *NVIDIA_REVIEW_MODELS) or
            (transport is not None and not callable(transport)) or
            (call_trace is not None and type(call_trace) is not list)):
        raise ValueError('invalid feature curation options')
    candidates = _feature_candidates(document, frozen, reviewed_labels)
    if len({item['value'] for item in candidates}) <= MAX_ARRAY_ITEMS:
        return None
    partition = _propose_feature_partition(document, candidates, key,
        model=model, transport=transport, call_trace=call_trace)
    from .candidate_feature_relations import review_feature_relations
    return review_feature_relations(document, frozen, reviewed_labels, partition, key,
        model=model, transport=transport, call_trace=call_trace)
