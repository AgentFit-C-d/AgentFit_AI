"""Disposable offline test child; no live transport or recovery entry point."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import unittest


def forbid_external(event, args):
    if event in ('socket.connect', 'socket.sendto', 'socket.getaddrinfo',
                 'socket.gethostbyname', 'socket.gethostbyaddr'):
        raise OSError('PRESERVED_NETWORK_FORBIDDEN')
    if event in ('subprocess.Popen', 'os.system'):
        raise OSError('PRESERVED_PROCESS_FORBIDDEN')


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = {}
        self.duplicates = []

    def record(self, test, status, detail=''):
        name = test._testMethodName
        if name in self.cases:
            self.duplicates.append(name)
        self.cases[name] = {'status': status, 'detail': detail}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, 'success')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, 'failure', self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, 'error', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.record(test, 'skip', reason)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            name = test._testMethodName
            status = 'failure' if issubclass(err[0], test.failureException) else 'error'
            row = self.cases.setdefault(name, {'status': status, 'detail': ''})
            if status == 'error':
                row['status'] = 'error'
            row['detail'] += self._exc_info_to_string(err, subtest)


if __name__ == '__main__':
    # Installed before importing any analysis or optional SDK module.
    sys.addaudithook(forbid_external)
    try:
        socket.getaddrinfo('example.invalid', 443)
    except OSError:
        blocked = True
    else:
        raise AssertionError('offline guard missing')
    import recovery_preserved_cases as cases
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(cases.ReviewRecoveryTests)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    runtime = Path(__file__).resolve().parents[2]
    inspector = runtime/'ai_service/diagnostic_tools/review_recovery.py'
    report = {'testsRun': result.testsRun, 'cases': result.cases, 'duplicates': result.duplicates,
              'runtime': str(runtime), 'networkBlocked': blocked,
              'inspectorSha256': hashlib.sha256(inspector.read_bytes()).hexdigest(),
              'modelCalls': 0, 'liveResume': False}
    with Path(sys.argv[1]).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
