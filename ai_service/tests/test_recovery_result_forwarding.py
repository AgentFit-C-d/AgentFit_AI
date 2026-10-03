"""A failing isolated test must remain failing in the parent regression run."""
import io
import unittest

from recovery_preserved_worker import RecordedResult
from test_review_recovery import preserved_case


class RecoveryResultForwardingTests(unittest.TestCase):
    def test_child_success_failure_error_skip_and_subtests_are_forwarded_exactly(self):
        class ChildCases(unittest.TestCase):
            def test_success(self):
                self.assertEqual(1, 1)

            def test_failure(self):
                self.fail('intentional assertion sentinel')

            def test_error(self):
                raise ValueError('intentional exception sentinel')

            def test_skip(self):
                self.skipTest('intentional compatibility sentinel')

            def test_subtest_failure(self):
                with self.subTest(part='first'):
                    self.fail('intentional subtest assertion')
                with self.subTest(part='second'):
                    self.fail('intentional second assertion')

            def test_subtest_error(self):
                with self.subTest(part='first'):
                    raise ValueError('intentional subtest exception')

        child = unittest.TextTestRunner(stream=io.StringIO(), resultclass=RecordedResult).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(ChildCases))
        self.assertEqual(child.testsRun, 6)
        self.assertFalse(child.wasSuccessful())
        self.assertEqual(child.duplicates, [])
        self.assertEqual({name: row['status'] for name, row in child.cases.items()}, {
            'test_success': 'success', 'test_failure': 'failure', 'test_error': 'error',
            'test_skip': 'skip', 'test_subtest_failure': 'failure', 'test_subtest_error': 'error'})
        class ParentCases(unittest.TestCase):
            results = child.cases
        for name in child.cases:
            setattr(ParentCases, name, preserved_case(name))
        parent = unittest.TextTestRunner(stream=io.StringIO()).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(ParentCases))
        self.assertEqual(parent.testsRun, 6)
        self.assertEqual(len(parent.failures), 2)
        self.assertEqual(len(parent.errors), 2)
        self.assertEqual(len(parent.skipped), 1)
        self.assertFalse(parent.wasSuccessful())
