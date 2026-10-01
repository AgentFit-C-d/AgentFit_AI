"""Stored real responses distinguish citation failures without changing verdicts."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / 'work/harness/evidence-relation-repair'
sys.path.insert(0, str(HARNESS))
from source_registry import build_registry, SourceContractError

spec = importlib.util.spec_from_file_location('legacy_evidence_audit', HARNESS / 'legacy_audit.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FIXTURE = Path(__file__).parent / 'fixtures/evidence_audit/saved_pair.json'


def one_record(document, start, end, support, counter=None, verdict='needs_confirmation'):
    raw = {'id': 'C000', 'field': 'features', 'status': 'confirmed',
           'support': support, 'counterEvidence': counter or []}
    saved = {'id': 'C000', 'raw_field': 'features', 'raw_status': 'confirmed',
             'verdict': verdict, 'candidate': {'start': start, 'end': end},
             'sourceValue': document[start:end], 'support': [], 'counterEvidence': [],
             'groundingValid': False}
    registry = build_registry(document, {'candidates': [{'id': 'C000', 'start': start, 'end': end}],
                                         'rejected': []})
    return registry, raw, saved


class LegacyEvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
        cls.files = cls.fixture['files']
        cls.inputs = json.loads(cls.files['inputs.json'])
        cls.summary = json.loads(cls.files['summary.json'])
        cls.expected = json.loads((ROOT / 'specs/ai-developer/evidence-relation-repair/audit.json').read_text(encoding='utf-8'))
        cls.registry = build_registry(cls.inputs['document'], cls.inputs['frozen'])
        cls.rows = {'A': {}, 'B': {}}
        for name, text in cls.files.items():
            if not name.endswith('-response.json'):
                continue
            arm = name.split('-')[-2]
            content = json.loads(json.loads(text)['choices'][0]['message']['content'])
            for row in content['assessments' if arm == 'A' else 'decisions']:
                cls.rows[arm][row['id']] = row

    def audit(self, arm, index):
        return module.audit_legacy_record(self.inputs['document'], self.registry,
                                          self.rows[arm][f'C{index:03}'], self.summary['arms'][arm]['records'][index])

    def test_fixture_has_exact_original_bytes_and_all_response_envelopes(self):
        for name, text in self.files.items():
            self.assertEqual(hashlib.sha256(text.encode('utf-8')).hexdigest(),
                             self.expected['input_sha256'][name.replace('/', '\\')])
        self.assertEqual(len(self.files), 20)
        self.assertEqual(len(self.rows['A']), 68)
        self.assertEqual(len(self.rows['B']), 68)

    def test_heading_support_keeps_both_wrong_and_normal_features_held(self):
        for index in (4, 5, 6, 7):
            with self.subTest(candidate=index):
                result = self.audit('B', index)
                self.assertEqual(result.get('legacyCitationStatus'), 'exact_elsewhere')
                self.assertTrue(result['mentionLocated'])
                self.assertTrue(result['contextAvailable'])
                self.assertEqual(result['supportSpans'], [{'start': 504, 'end': 525}])
                self.assertEqual(result['originalRecord'], self.summary['arms']['B']['records'][index])
                self.assertEqual(result['originalResponse'], self.rows['B'][f'C{index:03}'])
                self.assertEqual(result['originalRecord']['verdict'], 'needs_confirmation')

    def test_html_entities_and_joined_newlines_are_not_normalized_into_quotes(self):
        for arm, index in [('A', 22), ('A', 35), ('B', 35), ('B', 36), ('B', 37), ('B', 38)]:
            with self.subTest(arm=arm, candidate=index):
                result = self.audit(arm, index)
                self.assertEqual(result['legacyCitationStatus'], 'quote_not_found')
                self.assertEqual(result['supportSpans'], [])
                self.assertEqual(result['originalResponse'], self.rows[arm][f'C{index:03}'])
                self.assertTrue(result['mentionLocated'])

    def test_wrong_repeated_sentence_keeps_its_original_occurrence(self):
        for arm in ('A', 'B'):
            result = self.audit(arm, 66)
            self.assertEqual(result['legacyCitationStatus'], 'exact_elsewhere')
            self.assertEqual(result['supportSpans'], [{'start': 3466, 'end': 3523}])
            self.assertEqual(result['candidatePointer']['mentionSpan'], {'start': 4504, 'end': 4512})
            self.assertEqual(result['originalRecord']['verdict'], 'needs_confirmation')

    def test_valid_citations_do_not_reclassify_either_normal_or_semantic_errors(self):
        for arm, index, verdict in [('A', 1, 'needs_confirmation'), ('A', 32, 'needs_confirmation'),
                                   ('B', 1, 'supported'), ('B', 32, 'supported'),
                                   ('B', 62, 'supported'), ('A', 10, 'supported'), ('B', 10, 'supported'),
                                   ('A', 13, 'supported'), ('B', 13, 'supported')]:
            with self.subTest(arm=arm, candidate=index):
                result = self.audit(arm, index)
                self.assertEqual(result['legacyCitationStatus'], 'valid_covering')
                self.assertEqual(result['originalRecord']['verdict'], verdict)
                self.assertEqual(result['originalRecord'], self.summary['arms'][arm]['records'][index])

    def test_all_136_records_reproduce_fixed_defects_and_preserve_every_decision(self):
        result = module.audit_saved_files(self.files)
        self.assertEqual(result.get('registry', {}).get('document'), self.inputs['document'])
        self.assertEqual(result['registry']['originalFrozen'], self.inputs['frozen'])
        self.assertEqual(result['originalInputs'], self.inputs)
        self.assertEqual(result['originalSummary'], self.summary)
        for arm, defect_count in [('A', 12), ('B', 22)]:
            audited = result['arms'][arm]
            self.assertEqual(len(audited['records']), 68)
            self.assertEqual(audited['counts']['citationDefects'], defect_count)
            self.assertEqual(audited['quoteNotFoundIds'], self.expected['arms'][arm]['quote_not_found_ids'])
            self.assertEqual(audited['exactElsewhereIds'], self.expected['arms'][arm]['exact_but_wrong_occurrence_ids'])
            self.assertEqual(audited['citationDefectIds'], self.expected['arms'][arm]['citation_defect_ids'])
            self.assertEqual(audited['heldWithValidCitationIds'], self.expected['arms'][arm]['held_with_valid_citation_ids'])
            self.assertEqual([r['originalRecord'] for r in audited['records']], self.summary['arms'][arm]['records'])
            self.assertEqual([r['originalResponse'] for r in audited['records']], list(self.rows[arm].values()))
        self.assertEqual(result['newModelCalls'], 0)
        self.assertFalse(result['serviceApplied'])

    def test_input_and_saved_record_mismatches_cannot_be_silently_repaired(self):
        raw = self.rows['B']['C010']
        original = self.summary['arms']['B']['records'][10]
        for key, value in [('id', 'C011'), ('raw_field', 'features'), ('raw_status', 'tentative'),
                           ('candidate', {'start': 0, 'end': 1}), ('sourceValue', 'changed'),
                           ('support', []), ('groundingValid', False)]:
            saved = copy.deepcopy(original)
            saved[key] = value
            with self.subTest(key=key), self.assertRaises(SourceContractError):
                module.audit_legacy_record(self.inputs['document'], self.registry, raw, saved)
        with self.assertRaises(SourceContractError):
            module.audit_legacy_record(self.inputs['document'] + '\n', self.registry, raw, original)

    def test_results_are_defensive_copies_of_all_original_fields(self):
        result = self.audit('B', 5)
        result['originalRecord']['candidate']['start'] = 999
        result['originalResponse']['support'][0]['quote'] = 'changed'
        result['candidatePointer']['value'] = 'changed'
        again = self.audit('B', 5)
        self.assertEqual(again['originalRecord']['candidate']['start'], 565)
        self.assertEqual(again['originalResponse']['support'][0]['quote'], '**Feature Overview:**')
        self.assertEqual(again['candidatePointer']['value'], 'Organize bookmarks with tags')

    def test_all_concurrent_defects_survive_with_quote_failure_primary(self):
        doc = '# H\nAct now.\n'
        reg, raw, saved = one_record(doc, 4, 7, [{'quote': '# H', 'occurrence': 0},
                                                {'quote': 'Act later.', 'occurrence': 0}],
                                     [{'quote': 'missing conflict', 'occurrence': 0}])
        saved['support'] = [{'start': 0, 'end': 3}]
        result = module.audit_legacy_record(doc, reg, raw, saved)
        self.assertEqual(result['legacyCitationStatus'], 'quote_not_found')
        self.assertEqual({i['code'] for i in result['issues']}, {'quote_not_found', 'candidate_not_covered'})
        self.assertEqual(sum(i['code'] == 'quote_not_found' for i in result['issues']), 2)
        self.assertEqual(result['originalResponse']['counterEvidence'], raw['counterEvidence'])

    def test_overlapping_occurrences_are_exact_and_counterevidence_is_preserved(self):
        doc = 'ababa\nNo approval.\n'
        reg, raw, saved = one_record(doc, 2, 5, [{'quote': 'aba', 'occurrence': 1}],
                                     [{'quote': 'No approval.', 'occurrence': 0}])
        saved.update(support=[{'start': 2, 'end': 5}], counterEvidence=[{'start': 6, 'end': 18}], groundingValid=True)
        result = module.audit_legacy_record(doc, reg, raw, saved)
        self.assertEqual(result['legacyCitationStatus'], 'valid_covering')
        self.assertEqual(result['counterSpans'], [{'start': 6, 'end': 18}])
        self.assertEqual(result['originalRecord']['verdict'], 'needs_confirmation')

    def test_missing_occurrence_and_empty_support_stay_explicitly_unresolved(self):
        for supports, expected in [([{'quote': 'Act', 'occurrence': 1}], 'quote_not_found'),
                                    ([], 'incomplete_context')]:
            reg, raw, saved = one_record('Act', 0, 3, supports)
            saved['groundingValid'] = not supports
            result = module.audit_legacy_record('Act', reg, raw, saved)
            self.assertEqual(result['legacyCitationStatus'], expected)
            self.assertEqual(result['originalRecord']['verdict'], 'needs_confirmation')

    def test_oversized_context_is_incomplete_even_with_exact_support(self):
        doc = 'Act\n' + 'x' * 24000
        reg, raw, saved = one_record(doc, 0, 3, [{'quote': 'Act', 'occurrence': 0}])
        saved.update(support=[{'start': 0, 'end': 3}], groundingValid=True)
        result = module.audit_legacy_record(doc, reg, raw, saved)
        self.assertEqual(result['legacyCitationStatus'], 'incomplete_context')
        self.assertTrue(result['mentionLocated'])
        self.assertFalse(result['contextAvailable'])
        self.assertEqual(reg['document'], doc)

    def test_malformed_quotes_are_contract_errors_not_missing_evidence(self):
        for quote in [{'quote': 'Act', 'occurrence': True}, {'quote': '', 'occurrence': 0},
                      {'quote': 'Act', 'occurrence': -1}, {'quote': 'Act', 'occurrence': 100000},
                      {'quote': 'x' * 2001, 'occurrence': 0}, {'quote': 'Act'},
                      {'quote': 'Act', 'occurrence': 0, 'extra': 'ignored?'}]:
            reg, raw, saved = one_record('Act', 0, 3, [quote])
            with self.subTest(quote=quote), self.assertRaises(SourceContractError):
                module.audit_legacy_record('Act', reg, raw, saved)

    def test_replay_rejects_missing_duplicate_or_foreign_response_candidates(self):
        for operation in ('missing_file', 'duplicate', 'foreign'):
            files = dict(self.files)
            name = 'calls/10-B-response.json'
            if operation == 'missing_file':
                del files[name]
            else:
                envelope = json.loads(files[name])
                body = json.loads(envelope['choices'][0]['message']['content'])
                body['decisions'][0]['id'] = 'C001' if operation == 'duplicate' else 'foreign'
                envelope['choices'][0]['message']['content'] = json.dumps(body)
                files[name] = json.dumps(envelope)
            with self.subTest(operation=operation), self.assertRaises(SourceContractError):
                module.audit_saved_files(files)

    def _write_snapshot(self, folder):
        source = folder / 'source'
        source.mkdir()
        for name, text in self.files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode('utf-8'))
        manifest = copy.deepcopy(self.expected)
        manifest['input_sha256'] = {name: digest for name, digest in manifest['input_sha256'].items()
                                    if name.replace('\\', '/') in self.files}
        manifest_path = folder / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        return source, manifest_path

    def test_file_replay_preserves_bytes_and_refuses_overwrite_without_network(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source, manifest = self._write_snapshot(folder)
            output = folder / 'result'
            with patch('socket.create_connection', side_effect=AssertionError('offline only')):
                report = module.replay(source, manifest, output)
            self.assertTrue(report['preservation']['originalFilesUnchanged'])
            self.assertEqual(report['preservation']['copiedFiles'], 20)
            self.assertEqual(report['arms']['A']['counts']['citationDefects'], 12)
            self.assertEqual(report['arms']['B']['counts']['citationDefects'], 22)
            for name, text in self.files.items():
                self.assertEqual((output / 'originals' / name).read_bytes(), text.encode('utf-8'))
                self.assertEqual((source / name).read_bytes(), text.encode('utf-8'))
            self.assertEqual(json.loads((output / 'audit.json').read_text(encoding='utf-8')), report)
            saved_report = (output / 'audit.json').read_bytes()
            with self.assertRaises(FileExistsError):
                module.replay(source, manifest, output)
            self.assertEqual((output / 'audit.json').read_bytes(), saved_report)

    def test_manifest_hash_mismatch_or_escaping_path_fails_before_writing(self):
        for failure in ('hash', 'path', 'counts'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                folder = Path(temp)
                source, manifest_path = self._write_snapshot(folder)
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                if failure == 'hash':
                    manifest['input_sha256']['inputs.json'] = 'bad'
                elif failure == 'path':
                    manifest['input_sha256']['../outside.json'] = 'bad'
                else:
                    manifest['arms']['A']['records'] = 67
                manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
                output = folder / 'result'
                with self.assertRaises(SourceContractError):
                    module.replay(source, manifest_path, output)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
