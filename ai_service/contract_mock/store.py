"""In-memory Spring contract simulation. No real database or source persistence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from agentfit_ai.profile import FIELDS, _validate_value, ProfileValidationError
from .schema import ContractError, check, check_review, schemas, reject_sensitive


def identifier(prefix):
    return prefix + '_' + uuid4().hex


def _data(value):
    check('ProfileData', value)
    reject_sensitive(value)
    try:
        for field in FIELDS:
            _validate_value(field, value[field])
    except ProfileValidationError:
        raise ContractError(422, 'INVALID_INPUT') from None


class MockStore:
    def __init__(self, clock=None):
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = RLock()
        self._entries = {}
        self._diagnostics = {}
        self.fail_next_write = False

    def _now(self):
        return self.clock().astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    def _owned(self, owner, project_id):
        item = self._entries.get(project_id)
        if item is None or item['owner'] != owner:
            raise ContractError(404, 'PROJECT_NOT_FOUND')
        return item

    def _write_gate(self):
        if self.fail_next_write:
            self.fail_next_write = False
            raise ContractError(503, 'STORAGE_UNAVAILABLE')

    def _audit(self, item, event):
        item['audit'].append({'projectId': item['project']['id'], 'event': event, 'at': self._now()})

    def create(self, owner, name):
        check('CreateProjectRequest', {'name': name})
        reject_sensitive(name)
        if not 1 <= len(name.strip()) <= 100:
            raise ContractError(422, 'INVALID_INPUT')
        with self._lock:
            now = self._now()
            project = {'id': identifier('prj'), 'name': name.strip(), 'version': 0,
                       'createdAt': now, 'updatedAt': now}
            response = {'project': project}
            check('CreateProjectResponse', response)
            self._write_gate()
            item = {'owner': owner, 'project': project, 'draft': None, 'confirmed': None,
                    'latestAttempt': None, 'attempts': {}, 'review': None, 'audit': []}
            self._entries[project['id']] = item
            self._audit(item, 'PROJECT_CREATED')
            return deepcopy(response)

    def list(self, owner):
        with self._lock:
            rows = [i['project'] for i in self._entries.values() if i['owner'] == owner]
            rows = sorted(sorted(rows, key=lambda p: p['id']), key=lambda p: p['updatedAt'], reverse=True)
            return deepcopy({'projects': rows})

    def detail(self, owner, project_id):
        with self._lock:
            item = self._owned(owner, project_id)
            self._expire(item)
            return deepcopy({k: item[k] for k in ('project', 'confirmed', 'draft', 'latestAttempt')})

    def _expire(self, item):
        attempt = item['latestAttempt']
        if (attempt and attempt['status'] == 'PROCESSING'
                and self.clock() >= datetime.fromisoformat(attempt['deadlineAt'])):
            self.fail(item['owner'], item['project']['id'], attempt['id'], 'INTERRUPTED')

    def save(self, owner, project_id, payload):
        with self._lock:
            item = self._owned(owner, project_id)
            check('SaveProfileRequest', payload)
            if (type(payload['expectedVersion']) is not int or
                    'draftVersion' in payload and type(payload['draftVersion']) is not int):
                raise ContractError(422, 'INVALID_INPUT')
            values = deepcopy(payload['data'])
            _data(values)
            reference = item['confirmed']
            if 'draftId' in payload:
                reference = item['draft']
                if reference is None or reference['id'] != payload['draftId']:
                    raise ContractError(404, 'PROJECT_NOT_FOUND')
                if reference['version'] != payload['draftVersion']:
                    raise ContractError(409, 'VERSION_CONFLICT')
            if item['project']['version'] != payload['expectedVersion']:
                raise ContractError(409, 'VERSION_CONFLICT')
            sources, evidence = {}, {}
            for field, value in values.items():
                if value is None:
                    sources[field], evidence[field] = 'UNKNOWN', []
                elif reference is not None and value == reference['data'][field]:
                    sources[field], evidence[field] = reference['sources'][field], deepcopy(reference['evidence'][field])
                else:
                    sources[field], evidence[field] = 'USER', []
            previous, now = item['confirmed'], self._now()
            confirmed = {'id': previous['id'] if previous else identifier('prof'), 'kind': 'CONFIRMED',
                         'data': values, 'sources': sources, 'evidence': evidence,
                         'unknownFields': [f for f in FIELDS if values[f] is None],
                         'version': previous['version'] + 1 if previous else 1, 'updatedAt': now}
            project = dict(item['project'], version=item['project']['version'] + 1, updatedAt=now)
            response = {'project': project, 'confirmed': confirmed}
            check('SaveProfileResponse', response)
            self._write_gate()
            item['project'], item['confirmed'] = project, confirmed
            self._audit(item, 'PROFILE_CONFIRMED')
            return deepcopy(response)

    def begin(self, owner, project_id, document, *, timeout_seconds=2):
        with self._lock:
            item = self._owned(owner, project_id)
            for entry in self._entries.values():
                self._expire(entry)
            active = [i for i in self._entries.values()
                      if i['latestAttempt'] is not None and i['latestAttempt']['status'] == 'PROCESSING']
            if item in active:
                raise ContractError(409, 'ANALYSIS_BUSY')
            if len(active) >= 2 or any(i['owner'] == owner for i in active):
                raise ContractError(429, 'RATE_LIMITED')
            if type(document) is not dict or set(document) != {'kind', 'displayName', 'byteSize', 'characterCount', 'pageCount'}:
                raise ContractError(422, 'INVALID_INPUT')
            now = self._now()
            summary = dict(deepcopy(document), id=identifier('doc'), createdAt=now)
            attempt = {'id': identifier('attempt'), 'document': summary, 'status': 'PROCESSING',
                       'errorCode': None, 'startedAt': now,
                       'deadlineAt': (self.clock() + timedelta(seconds=timeout_seconds)).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
                       'finishedAt': None}
            check('AnalysisAttempt', attempt)
            self._write_gate()
            item['latestAttempt'] = attempt
            item['attempts'][attempt['id']] = attempt
            self._audit(item, 'ANALYSIS_STARTED')
            return deepcopy(attempt)

    def finish(self, owner, project_id, attempt_id, profile, review):
        with self._lock:
            item = self._owned(owner, project_id)
            self._expire(item)
            attempt = item['latestAttempt']
            if attempt is None or attempt['id'] != attempt_id or attempt['status'] != 'PROCESSING':
                raise ContractError(409, 'VERSION_CONFLICT')
            if type(profile) is not dict or set(profile) != {'data', 'sources', 'evidence', 'unknownFields'}:
                raise ContractError(502, 'AI_INVALID_OUTPUT')
            previous, now = item['draft'], self._now()
            draft = dict(deepcopy(profile), id=previous['id'] if previous else identifier('prof'), kind='DRAFT',
                         version=previous['version'] + 1 if previous else 1, updatedAt=now)
            try:
                check('Profile', draft)
                _data(draft['data'])
                if draft['unknownFields'] != [f for f in FIELDS if draft['data'][f] is None]:
                    raise ValueError
                for field, value in draft['data'].items():
                    spans = draft['evidence'][field]
                    if draft['sources'][field] != ('UNKNOWN' if value is None else 'DOCUMENT'):
                        raise ValueError
                    if bool(spans) != (value is not None):
                        raise ValueError
                    for span in spans:
                        if (set(span) != {'documentId', 'start', 'end'} or span['documentId'] != attempt['document']['id']
                                or type(span['start']) is not int or type(span['end']) is not int
                                or not 0 <= span['start'] < span['end']):
                            raise ValueError
                        count = attempt['document']['characterCount']
                        if count is not None and span['end'] > count:
                            raise ValueError
                check_review(profile, review)
            except (ValueError, KeyError, TypeError, ContractError):
                raise ContractError(502, 'AI_INVALID_OUTPUT') from None
            finished = dict(attempt, status='SUCCEEDED', finishedAt=now)
            response = {'draft': draft, 'attempt': finished}
            check('AnalysisResponse', response)
            self._write_gate()
            item['draft'], item['latestAttempt'], item['review'] = draft, finished, deepcopy(review)
            item['attempts'][attempt_id] = finished
            self._audit(item, 'DRAFT_STORED')
            return deepcopy(response)

    def fail(self, owner, project_id, attempt_id, error_code):
        with self._lock:
            item = self._owned(owner, project_id)
            attempt = item['latestAttempt']
            if attempt is None or attempt['id'] != attempt_id or attempt['status'] != 'PROCESSING':
                return
            allowed = schemas()['AnalysisAttempt']['properties']['errorCode']['anyOf'][0]['enum']
            code = error_code if type(error_code) is str and error_code in allowed else 'INTERNAL_ERROR'
            failed = dict(attempt, status='FAILED', errorCode=code, finishedAt=self._now())
            item['latestAttempt'] = failed
            item['attempts'][attempt_id] = failed
            self._audit(item, 'ANALYSIS_FAILED')

    def delete(self, owner, project_id):
        with self._lock:
            self._owned(owner, project_id)
            self._write_gate()
            del self._entries[project_id]
            for key in list(self._diagnostics):
                if key[0] == project_id:
                    del self._diagnostics[key]

    def record_failed_diagnostic(self, owner, project_id, attempt_id, payload):
        """Test-only synthetic injection. No HTTP ingestion or diagnostic read API."""
        with self._lock:
            item = self._owned(owner, project_id)
            attempt = item['attempts'].get(attempt_id)
            if (not attempt or attempt['status'] != 'FAILED' or type(payload) is not bytes
                    or not 0 < len(payload) <= 1_048_576):
                raise ContractError(422, 'INVALID_INPUT')
            expires = datetime.fromisoformat(attempt['finishedAt']) + timedelta(days=7)
            self.purge_diagnostics()
            if self.clock() >= expires:
                raise ContractError(422, 'INVALID_INPUT')
            self._diagnostics[(project_id, attempt_id)] = {'payload': payload, 'expires': expires}

    def purge_diagnostics(self):
        with self._lock:
            expired = [key for key, value in self._diagnostics.items() if self.clock() >= value['expires']]
            for key in expired:
                del self._diagnostics[key]
            return len(expired)

    def diagnostic_count(self):
        with self._lock:
            self.purge_diagnostics()
            return len(self._diagnostics)
