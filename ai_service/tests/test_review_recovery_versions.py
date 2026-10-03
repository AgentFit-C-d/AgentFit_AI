"""Current code must reject old versions without migrating historical records."""
from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from diagnostic_tools import review_recovery as recovery
from agentfit_ai.candidate_semantic_assessment import check_decision_records, validate_assessments
from review_preservation_fixture import offline
from recovery_version_fixture import ROOT, digest, unpack_origin, save_artifact, run_preserved_suite
from tentative_proposed_fixture import case


class CurrentRecoveryVersionTests(unittest.TestCase):
    def test_preserved_suite_needs_no_path_installed_launcher(self):
        # CI installs Python dependencies, not the developer's RTK utility.
        with patch.dict(os.environ, {'PATH': ''}):
            results = run_preserved_suite()
        self.assertEqual(len(results), 24)  # Original 20 recovery cases + 4 historical A checks.
        self.assertTrue(all(row['status'] in ('success', 'skip') for row in results.values()))

    def test_current_runtime_rejects_historical_execution_with_exact_code_mismatch(self):
        with TemporaryDirectory(prefix='agentfit-version-rejection-') as temporary, offline():
            origin = Path(temporary)/'origin'
            origin.mkdir()
            seal = unpack_origin(origin)
            freeze = json.loads((origin/'freeze.json').read_bytes())
            name = 'ai_service/agentfit_ai/candidate_semantic_assessment.py'
            self.assertNotEqual(digest(ROOT/name), freeze['actualWorkingFileHashes'][name])
            with self.assertRaisesRegex(recovery.RecoveryRefused, '^CODE_MISMATCH$'):
                recovery.inspect_run(origin, seal, ROOT, source=origin/'source.md')
            # A matching on-disk snapshot cannot stand in for the loaded code.
            with self.assertRaisesRegex(recovery.RecoveryRefused, '^LOADED_RUNTIME_MISMATCH$'):
                recovery.verify_runtime(origin, seal, origin/'code-snapshot')

    def test_old_derived_decisions_refused_and_raw_reassessment_saved_separately(self):
        with TemporaryDirectory(prefix='agentfit-decision-version-') as temporary, offline():
            folder = Path(temporary)
            for arm in ('A', 'B'):
                with self.subTest(arm=arm):
                    document, frozen, raw, previous = case('D2', arm)
                    saved_raw = deepcopy(raw)
                    original = folder/(arm+'-old-derived.json')
                    original.write_text(json.dumps(previous), encoding='utf-8')
                    original_hash = digest(original)
                    with self.assertRaisesRegex(ValueError, '^INVALID_SEMANTIC_ASSESSMENT$'):
                        check_decision_records(previous, document=document)
                    current = validate_assessments(document, frozen, raw, require_mention_kind=True)
                    self.assertEqual(check_decision_records(current, document=document), current)
                    self.assertEqual(raw, saved_raw)
                    self.assertEqual(digest(original), original_hash)
                    changes = []
                    for before, after in zip(previous, current, strict=True):
                        self.assertEqual({k:v for k,v in before.items() if k!='decision'},
                                         {k:v for k,v in after.items() if k!='decision'})
                        if before['decision'] != after['decision']:
                            changes.append((after['id'], before['decision'], after['decision']))
                    self.assertEqual(changes, [('C006', 'excluded', 'needs_confirmation')])
                    output = {'kind': 'offline-current-code-reassessment', 'historicalRawUnchanged': True,
                              'oldDerivedSha256': original_hash, 'arm': arm, 'before': previous,
                              'after': current, 'modelCalls': 0, 'automaticMigration': False}
                    encoded = json.dumps(output, ensure_ascii=False, indent=2).encode('utf-8')
                    with (folder/(arm+'-new-derived.json')).open('xb') as stream:
                        stream.write(encoded)
                    save_artifact(arm+'-raw-reassessment.json', encoded)
                    self.assertEqual(digest(original), original_hash)


if __name__ == '__main__':
    unittest.main()
