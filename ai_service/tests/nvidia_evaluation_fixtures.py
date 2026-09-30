"""Synthetic evaluation registration and free-access records, never real consent."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

from tests.independent_evaluation_fixtures import make_evaluation, write_json

SETTINGS = {'mode': 'integrated-nvidia', 'contract': 'confirmation-v2', 'request_timeout_seconds': 1800,
    'extraction_model': 'deepseek-ai/deepseek-v4.1-flash', 'classification_model': 'deepseek-ai/deepseek-v4.1-flash',
    'review_model': 'z-ai/glm-5.3', 'feature_model': 'deepseek-ai/deepseek-v4.1-flash',
    'candidate_batch_size': 20, 'max_calls': 64, 'nvidia_retry_limit': 0}


def make_variant(root):
    from agentfit_ai.independent_evaluation_inputs import digest_json, read_json
    root = Path(root)
    corpus, gold, _ = make_evaluation(root)
    for name in ('nvidia_evaluation_inputs.py', 'nvidia_evaluation_runner.py'):
        (root/'ai_service/agentfit_ai'/name).write_text('# synthetic evaluator', encoding='utf-8')
    prior = root/'specs/ai-developer/04-analysis-provider/public-holdout-corpus/manifest.json'
    hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
              for p in (root/'ai_service/agentfit_ai').glob('*.py')}
    freeze = root/'nvidia-freeze.json'
    write_json(freeze, {'version': 'nvidia-only-freeze-v1', 'variant': 'nvidia-only-v1', 'settings': SETTINGS,
        'corpus_sha256': digest_json(read_json(corpus)), 'gold_file_sha256': hashlib.sha256(gold.read_bytes()).hexdigest(),
        'prior_sha256': digest_json(read_json(prior)), 'lf_normalized_files': hashes})
    return corpus, gold, freeze


def make_access(path, **changes):
    record = {'version': 'nvidia-free-access-v1', 'confirmed_no_additional_charge': True,
        'endpoint': 'https://integrate.api.nvidia.com/v1/chat/completions',
        'models': ['deepseek-ai/deepseek-v4.1-flash', 'z-ai/glm-5.3'],
        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        'max_model_calls': 1920, 'evidence': 'SYNTHETIC TEST ONLY'}
    record.update(changes)
    write_json(path, record)
    return path
