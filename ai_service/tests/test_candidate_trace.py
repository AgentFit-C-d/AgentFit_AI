"""Position-only diagnostics must preserve the real candidate pipeline's boundaries."""
from copy import deepcopy
import importlib
import json
import unittest

from agentfit_ai.candidate_first_profile import finalize_candidate_analysis
from agentfit_ai.profile import FIELDS, validate_profile


def trace_module():
    try:
        return importlib.import_module('diagnostic_tools.candidate_trace')
    except ModuleNotFoundError as error:
        if error.name not in ('diagnostic_tools', 'diagnostic_tools.candidate_trace'):
            raise
        raise AssertionError('candidate provenance trace is not implemented') from None


def frozen(spans, rejected=None):
    return {'candidates': [{'id': f'C{index:03}', 'start': start, 'end': end}
                           for index, (start, end) in enumerate(spans)],
            'rejected': [] if rejected is None else rejected}


def labels(count):
    return [{'id': f'C{index:03}', 'field': 'features', 'status': 'confirmed'}
            for index in range(count)]


def completed_trace(document, occurrences, selections, wrong=None):
    trace = trace_module().CandidateTrace(document, 'PUBLIC-01')
    trace.observe('grounded', occurrences)
    trace.observe('classified', {'frozen': occurrences, 'labels': selections})
    result = finalize_candidate_analysis(document, 'PUBLIC-01', occurrences, selections,
        {'checkedFields': list(FIELDS), 'missingFields': [], 'wrongCandidateIds': wrong or []},
        observer=trace.observe)
    trace.finish(result)
    return trace, result


class CandidateTraceTests(unittest.TestCase):
    def test_stage_labels_locate_exclusion(self):
        # Losing the reviewed label transition would wrongly blame extraction.
        source = 'Export CSV'
        trace, result = completed_trace(source, frozen([(0, 10)]), labels(1), ['C000'])
        report = trace.summary()
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['stages']['classified']['labels'][0]['status'], 'confirmed')
        self.assertEqual(report['stages']['reviewed']['labels'][0]['status'], 'irrelevant')
        self.assertEqual(report['stages']['projected']['fields']['features']['state'], 'null')
        self.assertEqual(report['analysis']['unresolvedFields'], ['features'])
        self.assertIsNone(result['profile']['data']['features'])
        for private in (source, 'Export', 'CSV'):
            self.assertNotIn(private, json.dumps(report))

    def test_long_value_explains_projection_hold(self):
        # A UTF-16 length check or missing length metadata misdiagnoses this boundary.
        for length, expected_count, overlength in ((200, 2, []), (201, 0, ['C001'])):
            with self.subTest(length=length):
                source = 'Export CSV ' + '\U0001f642' * length
                trace, result = completed_trace(source, frozen([(0, 10), (11, 11 + length)]), labels(2))
                report = trace.summary()
                details = report['stages']['reviewed']['fields']['features']
                self.assertEqual(details['confirmedCount'], 2)
                self.assertEqual(details['uniqueCount'], 2)
                self.assertEqual(details['overlengthIds'], overlength)
                self.assertEqual(report['stages']['projected']['fields']['features']['valueCount'], expected_count)
                self.assertEqual(result['unresolvedFields'], ['features'] if length == 201 else [])
                self.assertNotIn('\U0001f642', json.dumps(report, ensure_ascii=False))

    def test_repeated_positions_stay_distinct(self):
        source = 'Export CSV then Export CSV'
        trace, _ = completed_trace(source, frozen([(0, 10), (16, 26)]), labels(2))
        report = trace.summary()
        self.assertEqual(report['stages']['grounded']['candidates'], [
            {'id': 'C000', 'start': 0, 'end': 10}, {'id': 'C001', 'start': 16, 'end': 26}])
        self.assertEqual(report['stages']['reviewed']['fields']['features']['uniqueCount'], 1)
        self.assertEqual(report['stages']['projected']['fields']['features']['evidence'],
                         [{'start': 0, 'end': 10}, {'start': 16, 'end': 26}])

    def test_missing_stage_is_none_and_cannot_be_mutated_by_caller(self):
        source = 'Export CSV'
        trace = trace_module().CandidateTrace(source, 'PUBLIC-01')
        trace.observe('grounded', frozen([(0, 10)]))
        report = trace.summary()
        self.assertEqual(report['status'], 'partial')
        self.assertIsNone(report['stages']['reviewed'])
        self.assertIsNone(report['stages']['projected'])
        self.assertIsNone(report['analysis'])
        report['stages']['grounded']['candidates'].clear()
        self.assertEqual(len(trace.summary()['stages']['grounded']['candidates']), 1)

    def test_null_and_explicit_empty_are_distinct(self):
        source = 'No integrations.'
        trace = trace_module().CandidateTrace(source, 'PUBLIC-01')
        empty = frozen([])
        trace.observe('grounded', empty)
        trace.observe('classified', {'frozen': empty, 'labels': []})
        trace.observe('reviewed', {'frozen': empty, 'labels': []})
        data, evidence = dict.fromkeys(FIELDS), {field: [] for field in FIELDS}
        data['external_integrations'] = []
        evidence['external_integrations'] = [{'start': 0, 'end': 16}]
        profile = validate_profile(source, 'PUBLIC-01', {'data': data, 'evidence': evidence})
        trace.observe('projected', profile)
        fields = trace.summary()['stages']['projected']['fields']
        self.assertEqual(fields['external_integrations']['state'], 'empty')
        self.assertEqual(fields['features']['state'], 'null')

    def test_global_confirmation_escalation_retains_reason(self):
        trace, result = completed_trace('Export CSV', frozen([(0, 10)],
            [{'index': 0, 'reason': 'source_quote_absent'}]), labels(1))
        report = trace.summary()
        self.assertEqual(result['profile']['data']['features'], ['Export CSV'])
        self.assertEqual(report['analysis']['confirmationScope'], 'all_fields')
        self.assertIn('REJECTED_CANDIDATES', report['analysis']['allFieldsReasons'])
        self.assertEqual(report['analysis']['rejectedCandidateCount'], 1)

    def test_malformed_observation_is_rejected_before_it_is_recorded(self):
        module = trace_module()
        bad = [frozen([(False, 10)]), frozen([(0, 99)]), frozen([(0, 10), (0, 10)]),
               frozen([(0, 10)]), frozen([(index, index + 1) for index in range(241)])]
        bad[3]['candidates'][0]['raw_response'] = 'private-provider-body'
        for value in bad:
            with self.subTest(value_count=len(value['candidates'])):
                trace = module.CandidateTrace('Export CSV' if len(value['candidates']) < 241 else 'x' * 241, 'PUBLIC-01')
                with self.assertRaises(ValueError):
                    trace.observe('grounded', value)
                self.assertIsNone(trace.summary()['stages']['grounded'])
        trace = module.CandidateTrace('Export CSV', 'PUBLIC-01')
        with self.assertRaises(ValueError):
            trace.observe('classified', {'frozen': frozen([(0, 10)]), 'labels': labels(1)})
        trace.observe('grounded', frozen([(0, 10)]))
        for field, status in (('private-model-field', 'confirmed'), ('features', 'private-model-status')):
            with self.assertRaises(ValueError):
                trace.observe('classified', {'frozen': frozen([(0, 10)]),
                    'labels': [{'id': 'C000', 'field': field, 'status': status}]})

    def test_untrusted_trace_rejects_extra_keys_ranges_and_false_identity(self):
        module = trace_module()
        trace, _ = completed_trace('Export CSV', frozen([(0, 10)]), labels(1))
        report = trace.summary()
        self.assertEqual(module.validate_trace('Export CSV', 'PUBLIC-01', report), report)
        corruptions = []
        corrupt = deepcopy(report)
        corrupt['raw'] = 'private-provider-body'
        corruptions.append(corrupt)
        corrupt = deepcopy(report)
        corrupt['stages']['grounded']['candidates'][0]['start'] = True
        corruptions.append(corrupt)
        corrupt = deepcopy(report)
        corrupt['stages']['reviewed']['fields']['features']['uniqueCount'] = 7
        corruptions.append(corrupt)
        corrupt = deepcopy(report)
        corrupt['sourceSha256'] = '0' * 64
        corruptions.append(corrupt)
        for value in corruptions:
            with self.assertRaises(ValueError) as raised:
                module.validate_trace('Export CSV', 'PUBLIC-01', value)
            self.assertNotIn('private-provider-body', str(raised.exception))
        with self.assertRaises(ValueError):
            module.validate_trace('Export CSV', 'PUBLIC-02', report)


if __name__ == '__main__':
    unittest.main()
