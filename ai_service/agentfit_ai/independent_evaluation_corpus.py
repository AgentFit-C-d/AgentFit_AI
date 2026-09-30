"""Bounded provenance and preregistered position-only gold validation."""
from copy import deepcopy
import hashlib
from pathlib import Path
import re

from .profile import ARRAY_FIELDS, FIELDS

_CASE_KEYS = frozenset(('id', 'family', 'commit', 'path', 'sha256', 'bytes', 'characters', 'source',
                        'local_file', 'acquisition', 'content_reviewed', 'model_outputs_seen',
                        'human_reviewed', 'model_pretraining_exposure'))
_EXCLUSIONS = frozenset(('negated', 'tentative', 'other_product', 'development_only', 'community_only', 'wrong_role'))
_AMBIGUITIES = frozenset(('role_not_explicit', 'development_scope', 'database_host_only', 'provider_not_named',
                         'integration_or_library', 'static_asset_or_api', 'demo_host_only'))


def _matches(pattern, value):
    return type(value) is str and re.fullmatch(pattern, value) is not None


def _family(value):
    name = value.casefold()
    return 'calcom/cal.com' if name == 'calcom/cal.diy' else name


def verify_corpus(cases: list[dict], prior: list[dict], root: Path) -> list[dict]:
    """Verify local immutable official sources; exposure flags cannot erase history."""
    try:
        if type(cases) is not list or not 1 <= len(cases) <= 10 or type(prior) is not list:
            raise ValueError
        root = Path(root).resolve(strict=True)
        previous_families, previous_hashes = set(), set()
        for old in prior:
            if (type(old) is not dict or not _matches(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', old.get('repo'))
                    or not _matches(r'[0-9a-f]{64}', old.get('sha256'))):
                raise ValueError
            previous_families.add(_family(old['repo']))
            previous_hashes.add(old['sha256'])
        ids, families, hashes = set(), set(), set()
        for row in cases:
            if (type(row) is not dict or set(row) != _CASE_KEYS
                    or not _matches(r'PUBLIC-[0-9]{2}', row['id'])
                    or not _matches(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', row['family'])
                    or not _matches(r'[0-9a-f]{40}', row['commit'])
                    or not _matches(r'[0-9a-f]{64}', row['sha256'])
                    or row['path'] != 'README.md' or row['local_file'] != row['id'] + '.md'
                    or row['source'] != f'https://github.com/{row["family"]}/blob/{row["commit"]}/README.md'
                    or row['acquisition'] != 'public_official_repository'
                    or any(row[k] is not False for k in ('content_reviewed', 'model_outputs_seen', 'human_reviewed'))
                    or row['model_pretraining_exposure'] != 'unknown'
                    or any(type(row[k]) is not int or not 0 < row[k] <= 100000 for k in ('bytes', 'characters'))):
                raise ValueError
            family = _family(row['family'])
            if (row['id'] in ids or family in families | previous_families
                    or row['sha256'] in hashes | previous_hashes):
                raise ValueError
            path = root / row['local_file']
            if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != root:
                raise ValueError
            with path.open('rb') as handle:
                body = handle.read(100001)
            document = body.decode('utf-8')
            if (len(body) != row['bytes'] or len(document) != row['characters']
                    or hashlib.sha256(body).hexdigest() != row['sha256'] or not document.strip()):
                raise ValueError
            ids.add(row['id'])
            families.add(family)
            hashes.add(row['sha256'])
        return deepcopy(cases)
    except (ValueError, TypeError, KeyError, OSError, UnicodeError):
        raise ValueError('INVALID_CORPUS') from None


def _positions(spans, length, max_span=None):
    if type(spans) is not list or not 1 <= len(spans) <= 10000:
        raise ValueError
    positions = set()
    for span in spans:
        if type(span) is not dict or set(span) != {'start', 'end'}:
            raise ValueError
        start, end = span['start'], span['end']
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= length
                or (max_span is not None and end - start > max_span) or (start, end) in positions):
            raise ValueError
        positions.add((start, end))
    return positions


def validate_gold(document: str, gold: dict) -> dict:
    """Reject ambiguous annotation contracts, not ambiguous source material."""
    try:
        if (type(document) is not str or not document.strip() or len(document) > 100000
                or len(document.encode('utf-8')) > 100000 or type(gold) is not dict
                or set(gold) != {'case_id', 'source_sha256', 'human_reviewed', 'fields', 'exclusions', 'ambiguities'}
                or not _matches(r'PUBLIC-[0-9]{2}', gold['case_id']) or gold['human_reviewed'] is not False
                or gold['source_sha256'] != hashlib.sha256(document.encode('utf-8')).hexdigest()
                or type(gold['fields']) is not dict or set(gold['fields']) != set(FIELDS)):
            raise ValueError
        ids, assigned, total = set(), {f: set() for f in FIELDS}, 0
        for field, entry in gold['fields'].items():
            if (type(entry) is not dict or set(entry) != {'assessment', 'units'}
                    or type(entry['assessment']) is not str
                    or entry['assessment'] not in ('enumerated', 'partial', 'unspecified')
                    or type(entry['units']) is not list
                    or len(entry['units']) > (30 if field in ARRAY_FIELDS else 1)
                    or (entry['assessment'] == 'unspecified' and entry['units'])
                    or (entry['assessment'] == 'enumerated' and not entry['units'])):
                raise ValueError
            for unit in entry['units']:
                if (type(unit) is not dict or set(unit) != {'id', 'kind', 'spans'}
                        or not _matches(r'U[0-9]{3}', unit['id']) or unit['id'] in ids
                        or type(unit['kind']) is not str or unit['kind'] not in ('present', 'explicit_absence')
                        or (unit['kind'] == 'explicit_absence' and (field not in ARRAY_FIELDS or len(entry['units']) != 1))):
                    raise ValueError
                positions = _positions(unit['spans'], len(document), 200 if unit['kind'] == 'present' else None)
                if assigned[field] & positions:
                    raise ValueError
                assigned[field].update(positions)
                total += len(positions)
                ids.add(unit['id'])
        for key, prefix, reasons in (('exclusions', 'X', _EXCLUSIONS), ('ambiguities', 'A', _AMBIGUITIES)):
            if type(gold[key]) is not list or len(gold[key]) > 1000:
                raise ValueError
            for item in gold[key]:
                if (type(item) is not dict or set(item) != {'id', 'fields', 'reason', 'spans'}
                        or not _matches(prefix + r'[0-9]{3}', item['id']) or item['id'] in ids
                        or type(item['reason']) is not str or item['reason'] not in reasons
                        or type(item['fields']) is not list or not 1 <= len(item['fields']) <= 10
                        or any(type(f) is not str or f not in FIELDS for f in item['fields'])
                        or len(set(item['fields'])) != len(item['fields'])):
                    raise ValueError
                positions = _positions(item['spans'], len(document))
                for field in item['fields']:
                    if assigned[field] & positions:
                        raise ValueError
                    assigned[field].update(positions)
                total += len(positions)
                ids.add(item['id'])
        if total > 10000:
            raise ValueError
        return deepcopy(gold)
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ValueError('INVALID_GOLD') from None
