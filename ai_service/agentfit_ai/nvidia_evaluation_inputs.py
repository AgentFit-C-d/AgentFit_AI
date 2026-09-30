"""Offline registration and explicit free-access scope for NVIDIA evaluation."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from .independent_evaluation_corpus import validate_gold, verify_corpus
from .independent_evaluation_inputs import decode_json, digest_json, read_bytes, read_json
from .analysis_call_metadata import METADATA_VERSION

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = 'specs/ai-developer/04-analysis-provider/independent-profile-evaluation'
SETTINGS = {'mode': 'integrated-nvidia', 'contract': 'confirmation-v2', 'request_timeout_seconds': 1800,
    'extraction_model': 'deepseek-ai/deepseek-v4.1-flash', 'classification_model': 'deepseek-ai/deepseek-v4.1-flash',
    'review_model': 'z-ai/glm-5.3', 'feature_model': 'deepseek-ai/deepseek-v4.1-flash',
    'candidate_batch_size': 20, 'max_calls': 64, 'nvidia_retry_limit': 0}
EVALUATOR_MODULES = ('independent_evaluation_corpus.py', 'independent_profile_evaluation.py',
    'independent_evaluation_protocol.py', 'independent_evaluation_inputs.py', 'independent_evaluation_runner.py',
    'nvidia_evaluation_inputs.py', 'nvidia_evaluation_runner.py')
MODELS = frozenset(('deepseek-ai/deepseek-v4.1-flash', 'z-ai/glm-5.3'))
ENDPOINT = 'https://integrate.api.nvidia.com/v1/chat/completions'


def _data(corpus_file, gold_file):
    corpus = read_json(corpus_file)
    if (type(corpus) is not dict or set(corpus) != {'version', 'cases', 'excluded_reserved_ids', 'authoring_stage'}
            or corpus != read_json(ROOT/SPEC_PATH/'corpus.json')
            or corpus['version'] != 'independent-profile-v1'
            or corpus['excluded_reserved_ids'] != ['PUBLIC-04', 'PUBLIC-05']
            or corpus['authoring_stage'] != 'before_gold_and_model_results'
            or type(corpus['cases']) is not list or len(corpus['cases']) != 10
            or [row['id'] for row in corpus['cases']] != [f'PUBLIC-{n:02}' for n in (1,2,3,6,7,8,9,10,11,12)]):
        raise ValueError
    prior = read_json(ROOT/'specs/ai-developer/04-analysis-provider/public-holdout-corpus/manifest.json')
    rows = verify_corpus(corpus['cases'], prior['cases'], Path(gold_file).resolve().parent)
    raw_gold = read_bytes(gold_file)
    gold_digest = hashlib.sha256(raw_gold).hexdigest()
    if gold_digest != read_json(ROOT/SPEC_PATH/'gold-summary.json')['gold_sha256']:
        raise ValueError
    gold = decode_json(raw_gold)
    if (type(gold) is not dict or set(gold) != {'version', 'annotation_author', 'human_reviewed', 'model_outputs_seen', 'cases'}
            or gold['version'] != 'independent-profile-gold-v1' or gold['annotation_author'] != 'agent'
            or gold['human_reviewed'] is not False or gold['model_outputs_seen'] is not False
            or type(gold['cases']) is not list or len(gold['cases']) != 10):
        raise ValueError
    cases = []
    for row, item in zip(rows, gold['cases'], strict=True):
        document = read_bytes(Path(gold_file).resolve().parent/row['local_file'], 100000).decode('utf-8')
        checked = validate_gold(document, item)
        if checked['case_id'] != row['id'] or checked['source_sha256'] != row['sha256']:
            raise ValueError
        cases.append({'case_id': row['id'], 'document': document, 'gold': checked,
                      'source_sha256': row['sha256'], 'gold_sha256': digest_json(checked)})
    return cases, {'corpus_sha256': digest_json(corpus), 'gold_file_sha256': gold_digest,
                   'prior_sha256': digest_json(prior)}


def _code_hashes():
    paths = list((ROOT/'ai_service/agentfit_ai').glob('*.py')) + list((ROOT/'ai_service').glob('requirements*.txt'))
    if not paths:
        raise ValueError
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(read_bytes(p).replace(b'\r\n', b'\n')).hexdigest()
            for p in sorted(paths)}


def _experiment(call_diagnostics):
    if type(call_diagnostics) is not bool:
        raise ValueError
    settings = dict(SETTINGS)
    if call_diagnostics:
        settings['call_diagnostics'] = METADATA_VERSION
    return ('nvidia-call-diagnostics' if call_diagnostics else 'nvidia-only'), settings


def build_freeze(corpus_file, gold_file, *, call_diagnostics=False):
    """Build an offline snapshot; caller must save it once before live output."""
    try:
        variant, settings = _experiment(call_diagnostics)
        _, identity = _data(corpus_file, gold_file)
        return {'version': variant+'-freeze-v1', 'variant': variant+'-v1',
                'settings': settings, **identity, 'lf_normalized_files': _code_hashes()}
    except (ValueError, TypeError, KeyError, AttributeError, OSError, UnicodeError, RecursionError):
        raise ValueError('INVALID_EVALUATION_PREFLIGHT') from None


def prepare_evaluation(corpus_file, gold_file, freeze_file, *, call_diagnostics=False):
    try:
        variant, settings = _experiment(call_diagnostics)
        freeze = read_json(freeze_file)
        expected = build_freeze(corpus_file, gold_file, call_diagnostics=call_diagnostics)
        if (type(freeze) is not dict or freeze != expected
                or type(freeze['settings']) is not dict
                or any(type(freeze['settings'][k]) is not type(v) for k,v in settings.items())):
            raise ValueError
        cases, identity = _data(corpus_file, gold_file)
        modules = EVALUATOR_MODULES + (('analysis_call_metadata.py',) if call_diagnostics else ())
        evaluator = {name: expected['lf_normalized_files']['ai_service/agentfit_ai/'+name] for name in modules}
        metadata = {'version': variant+'-evaluation-run-v1', 'variant': variant+'-v1',
            'runs_per_case': 3, 'settings': settings, **identity, 'freeze_sha256': digest_json(freeze),
            'evaluator_sha256': digest_json(evaluator),
            'cases': [{k: c[k] for k in ('case_id', 'source_sha256', 'gold_sha256')} for c in cases],
            'baseline_status': 'incomplete', 'new_holdout': False, 'human_reviewed': False, 'release_gate_passed': False}
        return {'cases': cases, 'metadata': metadata,
                'paths': [str(Path(p).resolve()) for p in (corpus_file, gold_file, freeze_file)]}
    except (ValueError, TypeError, KeyError, AttributeError, OSError, UnicodeError, RecursionError):
        raise ValueError('INVALID_EVALUATION_PREFLIGHT') from None


def load_nvidia_key(env_file):
    try:
        found = []
        for line in read_bytes(env_file, 65536).decode('utf-8-sig').splitlines():
            name, separator, value = line.partition('=')
            if name.strip() != 'NVIDIA_API_KEY':
                continue
            value = value.strip()
            if value.startswith(('"', "'")):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError
                value = value[1:-1]
            if (not separator or not value or len(value) > 4096 or value != value.strip()
                    or any(ord(c) < 32 for c in value)):
                raise ValueError
            found.append(value)
        if len(found) != 1:
            raise ValueError
        return found[0]
    except (ValueError, TypeError, OSError, UnicodeError):
        raise ValueError('INVALID_EVALUATION_KEYS') from None


def validate_free_access(path, *, reserved_calls, now=None):
    """Validate a human-confirmed scope, not account status or provider pricing."""
    try:
        record = read_json(path)
        if (type(record) is not dict or set(record) != {'version', 'confirmed_no_additional_charge',
                'endpoint', 'models', 'expires_at', 'max_model_calls', 'evidence'}
                or record['version'] != 'nvidia-free-access-v1'
                or record['confirmed_no_additional_charge'] is not True or record['endpoint'] != ENDPOINT
                or type(record['models']) is not list or len(record['models']) != 2
                or any(type(model) is not str for model in record['models']) or set(record['models']) != MODELS
                or type(record['max_model_calls']) is not int or not 64 <= record['max_model_calls'] <= 1920
                or type(reserved_calls) is not int or not 0 <= reserved_calls <= 1920
                or type(record['evidence']) is not str or not 1 <= len(record['evidence'].strip()) <= 200
                or any(ord(c) < 32 for c in record['evidence']) or type(record['expires_at']) is not str):
            raise ValueError
        expires = datetime.fromisoformat(record['expires_at'].replace('Z', '+00:00'))
        current = datetime.now(timezone.utc) if now is None else now
        if expires.tzinfo is None or expires.utcoffset().total_seconds() != 0 or expires <= current:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError, OSError, UnicodeError, RecursionError, OverflowError):
        raise ValueError('FREE_ACCESS_UNCONFIRMED') from None
    if reserved_calls > record['max_model_calls']:
        raise ValueError('FREE_ACCESS_BUDGET_EXHAUSTED')
    return record
