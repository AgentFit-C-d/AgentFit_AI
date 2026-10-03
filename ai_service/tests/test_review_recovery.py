"""Run every historical recovery assertion in its matching isolated runtime."""
import unittest

from recovery_version_fixture import preserved_case_names, run_preserved_suite


class PreservedRecoveryVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = run_preserved_suite()


def preserved_case(name):
    def check(self):
        result = self.results[name]
        if result['status'] == 'skip':
            self.skipTest(result['detail'])
        if result['status'] == 'error':
            raise RuntimeError(result['detail'])
        self.assertEqual(result['status'], 'success', result['detail'])
    check.__name__ = name
    return check


for name in preserved_case_names():
    setattr(PreservedRecoveryVersionTests, name, preserved_case(name))


if __name__ == '__main__':
    unittest.main()
