"""Consumer assertions against the existing public OpenAPI, using synthetic data."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import unittest

from agentfit_ai.profile import FIELDS, validate_profile
from contract_mock.schema import ContractError, check
from contract_mock.store import MockStore


DOCUMENT = 'MockPlan uses React. No AI.'


def data(**changes):
    return dict(dict.fromkeys(FIELDS), **changes)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 30, tzinfo=timezone.utc)
        self.store = MockStore(clock=lambda: self.now)
        self.created = self.store.create('owner-a', '  Test plan  ')
        self.project_id = self.created['project']['id']

    def assert_error(self, status, code, callback):
        with self.assertRaises(ContractError) as caught:
            callback()
        self.assertEqual((caught.exception.status, caught.exception.code), (status, code))
        self.assertEqual(str(caught.exception), code)

    def draft(self, *, store=None, owner='owner-a', project_id=None):
        store = store or self.store
        project_id = project_id or self.project_id
        attempt = store.begin(owner, project_id, {'kind': 'TEXT', 'displayName': None,
            'byteSize': len(DOCUMENT.encode()), 'characterCount': len(DOCUMENT), 'pageCount': None})
        values = data(project_name='MockPlan', frontend=['React'], ai=[])
        spans = {f: [] for f in FIELDS}
        spans.update(project_name=[{'start': 0, 'end': 8}], frontend=[{'start': 14, 'end': 19}],
                     ai=[{'start': 21, 'end': 26}])
        profile = validate_profile(DOCUMENT, attempt['document']['id'], {'data': values, 'evidence': spans})
        states = {f: 'unknown' if values[f] is None else 'suggested' for f in FIELDS}
        review = {'contract': 'confirmation-v2', 'fieldStates': states,
                  'questions': [{'field': f, 'reason': 'CONFIRM_SUGGESTION', 'questionId': 'confirm_' + f}
                                for f in FIELDS if states[f] == 'suggested']}
        result = store.finish(owner, project_id, attempt['id'], profile, review)
        check('AnalysisResponse', result)
        return result['draft']

    def test_create_manual_save_and_detail_match_existing_schema(self):
        check('CreateProjectResponse', self.created)
        self.assertEqual(self.created['project']['name'], 'Test plan')
        self.assertEqual(self.created['project']['version'], 0)
        result = self.store.save('owner-a', self.project_id, {'expectedVersion': 0,
            'data': data(frontend=['Vue'], ai=[])})
        check('SaveProfileResponse', result)
        self.assertEqual(result['project']['version'], 1)
        self.assertEqual(result['confirmed']['sources']['frontend'], 'USER')
        self.assertEqual(result['confirmed']['evidence']['frontend'], [])
        self.assertEqual(result['confirmed']['data']['ai'], [])
        self.assertNotIn('ai', result['confirmed']['unknownFields'])
        detail = self.store.detail('owner-a', self.project_id)
        check('ProjectDetailResponse', detail)
        self.assertEqual(detail['confirmed'], result['confirmed'])
        self.assertIsNone(detail['draft'])
        check('ProjectListResponse', self.store.list('owner-a'))

    def test_draft_confirmation_preserves_equal_values_and_marks_edits_and_null(self):
        draft = self.draft()
        changed = deepcopy(draft['data']); changed['project_name'] = 'My plan'; changed['ai'] = None
        result = self.store.save('owner-a', self.project_id, {'expectedVersion': 0, 'data': changed,
            'draftId': draft['id'], 'draftVersion': draft['version']})
        confirmed = result['confirmed']
        self.assertEqual(confirmed['sources']['frontend'], 'DOCUMENT')
        self.assertEqual(confirmed['evidence']['frontend'], draft['evidence']['frontend'])
        self.assertEqual(confirmed['sources']['project_name'], 'USER')
        self.assertEqual(confirmed['evidence']['project_name'], [])
        self.assertEqual(confirmed['sources']['ai'], 'UNKNOWN')
        self.assertEqual(confirmed['evidence']['ai'], [])
        self.assertEqual(self.store.detail('owner-a', self.project_id)['draft'], draft)
        check('SaveProfileResponse', result)

    def test_reanalysis_never_overwrites_confirmed_and_old_draft_conflicts(self):
        old = self.draft()
        saved = self.store.save('owner-a', self.project_id, {'expectedVersion': 0, 'data': data(domain='manual')})
        new = self.draft()
        self.assertEqual(new['id'], old['id'])
        self.assertEqual(new['version'], old['version'] + 1)
        self.assertEqual(self.store.detail('owner-a', self.project_id)['confirmed'], saved['confirmed'])
        self.assert_error(409, 'VERSION_CONFLICT', lambda: self.store.save('owner-a', self.project_id,
            {'expectedVersion': 1, 'data': data(), 'draftId': old['id'], 'draftVersion': old['version']}))

    def test_invalid_save_shape_and_types_leave_state_unchanged(self):
        original = self.store.detail('owner-a', self.project_id)
        variants = [{'expectedVersion': 0, 'data': {}},
                    {'expectedVersion': True, 'data': data()},
                    {'expectedVersion': 0, 'data': data(), 'ownerId': 'owner-b'},
                    {'expectedVersion': 0, 'data': data(frontend=['  '])},
                    {'expectedVersion': 0, 'data': data(), 'draftId': 'one-sided'},
                    {'expectedVersion': 0, 'data': data(), 'acknowledgedQuestionIds': []}]
        for payload in variants:
            with self.subTest(payload=payload):
                self.assert_error(422, 'INVALID_INPUT', lambda: self.store.save('owner-a', self.project_id, payload))
                self.assertEqual(self.store.detail('owner-a', self.project_id), original)

    def test_ownership_and_cross_project_draft_do_not_leak(self):
        self.assert_error(404, 'PROJECT_NOT_FOUND', lambda: self.store.detail('owner-b', self.project_id))
        self.assert_error(404, 'PROJECT_NOT_FOUND', lambda: self.store.detail('owner-a', 'missing'))
        foreign = self.store.create('owner-a', 'second')['project']['id']
        draft = self.draft(project_id=foreign)
        self.assert_error(404, 'PROJECT_NOT_FOUND', lambda: self.store.save('owner-a', self.project_id,
            {'expectedVersion': 0, 'data': data(), 'draftId': draft['id'], 'draftVersion': 1}))

    def test_two_concurrent_saves_have_one_winner(self):
        def save(_):
            try:
                self.store.save('owner-a', self.project_id, {'expectedVersion': 0, 'data': data(domain='value')})
                return 200
            except ContractError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(save, range(2))), [200, 409])
        detail = self.store.detail('owner-a', self.project_id)
        self.assertEqual(detail['project']['version'], 1)
        self.assertEqual(detail['confirmed']['version'], 1)

    def test_failed_write_does_not_change_any_public_state(self):
        old = self.store.detail('owner-a', self.project_id)
        self.store.fail_next_write = True
        self.assert_error(503, 'STORAGE_UNAVAILABLE', lambda: self.store.save('owner-a', self.project_id,
            {'expectedVersion': 0, 'data': data(frontend=['React'])}))
        self.assertEqual(self.store.detail('owner-a', self.project_id), old)

    def test_returned_data_is_not_a_mutable_handle_into_storage(self):
        result = self.store.save('owner-a', self.project_id, {'expectedVersion': 0, 'data': data(frontend=['React'])})
        result['confirmed']['data']['frontend'].append('mutated')
        self.assertEqual(self.store.detail('owner-a', self.project_id)['confirmed']['data']['frontend'], ['React'])

    def test_schema_rejects_unagreed_public_review_extension(self):
        detail = self.store.detail('owner-a', self.project_id)
        detail['draftReview'] = {'questions': []}
        self.assert_error(422, 'INVALID_INPUT', lambda: check('ProjectDetailResponse', detail))
