"""Validate the complete preregistered experiment before any provider access."""
import hashlib
import json
from pathlib import Path

from .independent_evaluation_corpus import validate_gold, verify_corpus

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = 'specs/ai-developer/04-analysis-provider/independent-profile-evaluation'
MODULES = ('independent_evaluation_corpus.py', 'independent_profile_evaluation.py',
           'independent_evaluation_protocol.py', 'independent_evaluation_worker.py',
           'independent_evaluation_inputs.py', 'independent_evaluation_runner.py')
SETTINGS = {'mode': 'integrated-candidates', 'contract': 'confirmation-v2', 'request_timeout_seconds': 1800,
            'extraction_model': 'solar-pro4', 'classification_model': 'solar-pro4', 'review_model': 'z-ai/glm-5.3',
            'feature_model': 'deepseek-ai/deepseek-v4.1-flash', 'candidate_batch_size': 20,
            'max_calls': 64, 'nvidia_retry_limit': 1}


def digest_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf-8')).hexdigest()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('INVALID_JSON')
        result[key] = value
    return result


def _invalid_constant(_value):
    raise ValueError('INVALID_JSON')


def decode_json(raw):
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=_invalid_constant)


def read_bytes(path, limit=8_000_000):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('INVALID_INPUT_FILE')
    with path.open('rb') as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('INVALID_INPUT_FILE')
    return raw


def read_json(path):
    return decode_json(read_bytes(path))


def load_keys(env_file):
    try:
        values = {}
        for line in read_bytes(env_file, 65536).decode('utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            name = name.strip()
            if name not in ('UPSTAGE_API_KEY', 'NVIDIA_API_KEY'):
                continue
            if not separator or name in values:
                raise ValueError
            value = value.strip()
            if value.startswith(('"', "'")):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError
                value = value[1:-1]
            if not value or len(value) > 4096 or value.strip() != value or any(ord(c) < 32 for c in value):
                raise ValueError
            values[name] = value
        if set(values) != {'UPSTAGE_API_KEY', 'NVIDIA_API_KEY'} or len(set(values.values())) != 2:
            raise ValueError
        return values['UPSTAGE_API_KEY'], values['NVIDIA_API_KEY']
    except (ValueError, OSError, UnicodeError):
        raise ValueError('INVALID_EVALUATION_KEYS') from None


def prepare_evaluation(corpus_file: Path, gold_file: Path, freeze_file: Path) -> dict:
    try:
        corpus, freeze = read_json(corpus_file), read_json(freeze_file)
        if (type(corpus) is not dict or set(corpus) != {'version', 'cases', 'excluded_reserved_ids', 'authoring_stage'}
                or corpus['version'] != 'independent-profile-v1'
                or corpus['excluded_reserved_ids'] != ['PUBLIC-04', 'PUBLIC-05']
                or corpus['authoring_stage'] != 'before_gold_and_model_results'
                or type(corpus['cases']) is not list or len(corpus['cases']) != 10
                or any(row.get('id') in corpus['excluded_reserved_ids'] for row in corpus['cases'])):
            raise ValueError
        if (type(freeze) is not dict or set(freeze) != {'version', 'code_revision', 'content_read', 'model_outputs_seen', 'settings', 'lf_normalized_files'}
                or freeze['version'] != 'independent-profile-v1'
                or freeze['code_revision'] != '9af3f2a9bcd47d5e3bb40860fe674434787b442a'
                or freeze['content_read'] is not False or freeze['model_outputs_seen'] is not False
                or type(freeze['settings']) is not dict or set(freeze['settings']) != set(SETTINGS)
                or any(type(freeze['settings'][k]) is not type(v) or freeze['settings'][k] != v for k, v in SETTINGS.items())
                or type(freeze['lf_normalized_files']) is not dict):
            raise ValueError
        code = ROOT / 'ai_service'
        original_paths = {p.relative_to(ROOT).as_posix() for p in (code/'agentfit_ai').glob('*.py') if p.name not in MODULES}
        original_paths.update(p.relative_to(ROOT).as_posix() for p in code.glob('requirements*.txt'))
        if not original_paths or set(freeze['lf_normalized_files']) != original_paths:
            raise ValueError
        for name, digest in freeze['lf_normalized_files'].items():
            if hashlib.sha256(read_bytes(ROOT/name).replace(b'\r\n', b'\n')).hexdigest() != digest:
                raise ValueError
        evaluator_hash = digest_json({name: hashlib.sha256(read_bytes(code/'agentfit_ai'/name).replace(b'\r\n', b'\n')).hexdigest() for name in MODULES})
        prior = read_json(ROOT/'specs/ai-developer/04-analysis-provider/public-holdout-corpus/manifest.json')
        rows = verify_corpus(corpus['cases'], prior['cases'], Path(gold_file).resolve().parent)
        raw_gold = read_bytes(gold_file)
        gold_digest = hashlib.sha256(raw_gold).hexdigest()
        if gold_digest != read_json(ROOT/SPEC_PATH/'gold-summary.json')['gold_sha256']:
            raise ValueError
        all_gold = decode_json(raw_gold)
        if (type(all_gold) is not dict or set(all_gold) != {'version', 'annotation_author', 'human_reviewed', 'model_outputs_seen', 'cases'}
                or all_gold['version'] != 'independent-profile-gold-v1' or all_gold['annotation_author'] != 'agent'
                or all_gold['human_reviewed'] is not False or all_gold['model_outputs_seen'] is not False
                or type(all_gold['cases']) is not list or len(all_gold['cases']) != 10):
            raise ValueError
        cases = []
        for row, gold in zip(rows, all_gold['cases'], strict=True):
            document = read_bytes(Path(gold_file).resolve().parent / row['local_file'], 100000).decode('utf-8')
            checked = validate_gold(document, gold)
            if checked['case_id'] != row['id'] or checked['source_sha256'] != row['sha256']:
                raise ValueError
            cases.append({'case_id': row['id'], 'document': document, 'gold': checked,
                          'source_sha256': row['sha256'], 'gold_sha256': digest_json(checked)})
        metadata = {'version': 'independent-evaluation-run-v1', 'runs_per_case': 3, 'settings': dict(SETTINGS),
                    'freeze_sha256': digest_json(freeze), 'corpus_sha256': digest_json(corpus),
                    'prior_sha256': digest_json(prior), 'gold_file_sha256': gold_digest,
                    'evaluator_sha256': evaluator_hash,
                    'cases': [{k: c[k] for k in ('case_id', 'source_sha256', 'gold_sha256')} for c in cases],
                    'human_reviewed': False, 'release_gate_passed': False}
        return {'cases': cases, 'metadata': metadata,
                'paths': [str(Path(p).resolve()) for p in (corpus_file, gold_file, freeze_file)]}
    except (ValueError, TypeError, KeyError, AttributeError, OSError, UnicodeError, RecursionError):
        raise ValueError('INVALID_EVALUATION_PREFLIGHT') from None
