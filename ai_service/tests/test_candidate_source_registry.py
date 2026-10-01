"""Offline evidence links must retain exact occurrences without deciding meaning."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[2] / 'work/harness/evidence-relation-repair/source_registry.py'
spec = importlib.util.spec_from_file_location('candidate_source_registry', PATH)
registry_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry_module)
build_registry = registry_module.build_registry
resolve_units = registry_module.resolve_units
SourceContractError = registry_module.SourceContractError


def frozen(*spans):
    return {'candidates': [{'id': f'C{i:03}', 'start': start, 'end': end}
                           for i, (start, end) in enumerate(spans)],
            'rejected': [{'reason': 'original rejection', 'raw': 'keep me'}]}


class CandidateSourceRegistryTests(unittest.TestCase):
    def test_unicode_crlf_tabs_and_multiline_spans_are_not_normalized(self):
        document = '# H\r\n😀\t가\r\n끝'
        original = frozen((5, 11))
        result = build_registry(document, original)
        self.assertEqual(result.get('document'), document)
        self.assertEqual(result['sourceDigest'], hashlib.sha256(document.encode()).hexdigest())
        self.assertEqual([(u['start'], u['end'], u['text']) for u in result['units']],
                         [(0, 5, '# H\r\n'), (5, 10, '😀\t가\r\n'), (10, 11, '끝')])
        candidate = result['candidates'][0]
        self.assertEqual(candidate['value'], '😀\t가\r\n끝')
        self.assertEqual(candidate['mentionSpan'], {'start': 5, 'end': 11})
        self.assertEqual(candidate['localUnitIds'], [u['unitId'] for u in result['units'][1:]])
        self.assertEqual(result['originalFrozen'], original)
        original['rejected'].clear()
        self.assertEqual(len(result['originalFrozen']['rejected']), 1)

    def test_identical_names_keep_distinct_occurrences_and_table_rows(self):
        document = '| Aurora | adopted |\n| Aurora | rejected |\n'
        result = build_registry(document, frozen((2, 8), (23, 29)))
        left, right = result['candidates']
        self.assertEqual(left['value'], right['value'])
        self.assertNotEqual(left['localUnitIds'], right['localUnitIds'])
        self.assertEqual(len(result['units']), 2)
        linked = resolve_units(result, 'C001', left['localUnitIds'], [])
        self.assertFalse(linked['candidateCovered'])
        self.assertFalse(linked['contextSufficient'])

    def test_heading_only_does_not_replace_multiline_candidate(self):
        document = '# Actions\nDo this\nand that\n'
        result = build_registry(document, frozen((10, 26)))
        candidate = result['candidates'][0]
        heading, first, second = [u['unitId'] for u in result['units']]
        self.assertEqual(candidate['headingUnitIds'], [heading])
        self.assertFalse(resolve_units(result, 'C000', [heading], [])['contextSufficient'])
        self.assertFalse(resolve_units(result, 'C000', [first], [])['candidateCovered'])
        self.assertTrue(resolve_units(result, 'C000', [first, second], [])['candidateCovered'])
        self.assertFalse(resolve_units(result, 'C000', [], [])['contextSufficient'])

    def test_fenced_heading_does_not_become_section_context(self):
        document = '# Real\n```txt\n# example\n```\nAction\n'
        start = document.index('Action')
        result = build_registry(document, frozen((start, start + 6)))
        self.assertEqual([u['text'] for u in result['units'] if u['kind'] == 'heading'], ['# Real\n'])
        self.assertEqual(result['candidates'][0]['headingUnitIds'], [result['units'][0]['unitId']])

    def test_remote_negative_is_available_without_semantic_decision(self):
        document = '# Current\nLumen is proposed.\n' + ('padding\n' * 40) + 'Lumen was rejected.\n'
        result = build_registry(document, frozen((10, 15)))
        candidate = result['candidates'][0]
        remote = result['units'][-1]['unitId']
        linked = resolve_units(result, 'C000', candidate['localUnitIds'], [remote])
        self.assertEqual(linked['counterUnits'][0]['text'], 'Lumen was rejected.\n')
        self.assertEqual(candidate['context'], {'start': 0, 'end': 255, 'text': document[:255]})
        self.assertEqual(result['document'], document)
        self.assertTrue(linked['contextSufficient'])  # structural availability only
        for forbidden in ('field', 'status', 'verdict', 'confirmed'):
            self.assertNotIn(forbidden, linked)

    def test_unit_ids_change_with_source_identity_and_are_repeatable(self):
        first = build_registry('same\n', frozen((0, 4)))
        self.assertEqual(first, build_registry('same\n', frozen((0, 4))))
        changed = build_registry('same\nextra', frozen((0, 4)))
        self.assertNotEqual(first['units'][0]['unitId'], changed['units'][0]['unitId'])
        with self.assertRaises(SourceContractError):
            resolve_units(first, 'C000', [changed['units'][0]['unitId']], [])

    def test_invalid_offsets_and_duplicate_candidates_are_contract_errors(self):
        for start, end in [(-1, 2), (0, 99), (2, 2), (True, 2), (0, 1.5)]:
            with self.subTest(span=(start, end)), self.assertRaises(SourceContractError):
                build_registry('abc', frozen((start, end)))
        value = frozen((0, 1), (1, 2))
        value['candidates'][1]['id'] = 'C000'
        with self.assertRaises(SourceContractError):
            build_registry('abc', value)

    def test_registry_tampering_is_rejected_before_resolving(self):
        registry = build_registry('# H\nvalue\n', frozen((4, 9)))
        for target, key, value in [('root', 'sourceDigest', 'bad'),
                                   ('root', 'document', '# H\nother\n'),
                                   ('unit', 'text', 'forged'),
                                   ('candidate', 'value', 'forged')]:
            damaged = copy.deepcopy(registry)
            dest = damaged if target == 'root' else damaged['units' if target == 'unit' else 'candidates'][0]
            dest[key] = value
            with self.subTest(target=target, key=key), self.assertRaises(SourceContractError):
                resolve_units(damaged, 'C000', [], [])

    def test_caps_mark_incomplete_without_dropping_original_data(self):
        for document in ['x' * 24001, 'x\n' * 1001]:
            value = frozen((0, 1))
            result = build_registry(document, value)
            self.assertFalse(result['complete'])
            self.assertEqual(result['document'], document)
            self.assertEqual(result['originalFrozen'], value)
            self.assertEqual(len(result['candidates']), 1)
            linked = resolve_units(result, 'C000', [], [])
            self.assertFalse(linked['contextAvailable'])
        self.assertTrue(build_registry('x' * 24000, frozen((0, 1)))['complete'])
        self.assertTrue(build_registry('x\n' * 1000, frozen((0, 1)))['complete'])

    def test_selection_limits_unknown_and_duplicate_ids_fail_closed(self):
        result = build_registry('x\n' * 9, frozen((0, 1)))
        ids = [u['unitId'] for u in result['units']]
        self.assertTrue(resolve_units(result, 'C000', ids[:8], [])['candidateCovered'])
        for supports, counters in [(ids, []), ([], ids), ([ids[0], ids[0]], []),
                                   ([], [ids[0], ids[0]]), (['unknown'], []), ([], ['unknown'])]:
            with self.subTest(supports=supports, counters=counters), self.assertRaises(SourceContractError):
                resolve_units(result, 'C000', supports, counters)
        with self.assertRaises(SourceContractError):
            resolve_units(result, 'missing-candidate', [], [])
        for size, allowed in [(4000, True), (4001, False)]:
            long = build_registry('x' * size, frozen((0, 1)))
            ids = [long['units'][0]['unitId']]
            if allowed:
                self.assertTrue(resolve_units(long, 'C000', ids, [])['candidateCovered'])
            else:
                with self.assertRaises(SourceContractError):
                    resolve_units(long, 'C000', ids, [])
                with self.assertRaises(SourceContractError):
                    resolve_units(long, 'C000', [], ids)


if __name__ == '__main__':
    unittest.main()
