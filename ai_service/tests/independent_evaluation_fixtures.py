"""Synthetic ten-family preflight fixture, independent of real/public documents."""
import hashlib
import json
from pathlib import Path

from agentfit_ai.profile import FIELDS

SETTINGS = {'mode': 'integrated-candidates', 'contract': 'confirmation-v2', 'request_timeout_seconds': 1800,
            'extraction_model': 'solar-pro4', 'classification_model': 'solar-pro4', 'review_model': 'z-ai/glm-5.3',
            'feature_model': 'deepseek-ai/deepseek-v4.1-flash', 'candidate_batch_size': 20,
            'max_calls': 64, 'nvidia_retry_limit': 1}
MODULES = ('independent_evaluation_corpus.py', 'independent_profile_evaluation.py',
           'independent_evaluation_protocol.py', 'independent_evaluation_worker.py',
           'independent_evaluation_inputs.py', 'independent_evaluation_runner.py')


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def make_evaluation(root):
    root = Path(root)
    spec = root / 'specs/ai-developer/04-analysis-provider/independent-profile-evaluation'
    prior = spec.parent / 'public-holdout-corpus'
    code = root / 'ai_service/agentfit_ai'
    sources = root / 'source'
    for path in (spec, prior, code, sources): path.mkdir(parents=True)
    (code / 'base.py').write_bytes(b'# frozen production\n')
    for name in MODULES: (code / name).write_bytes(b'# evaluator ' + name.encode())
    cases, golds = [], []
    for number in (1, 2, 3, 6, 7, 8, 9, 10, 11, 12):
        ident = f'PUBLIC-{number:02}'
        document = f'React synthetic document {number}'
        (sources / (ident + '.md')).write_bytes(document.encode())
        digest = hashlib.sha256(document.encode()).hexdigest()
        family = f'official/project{number}'
        cases.append({'id': ident, 'family': family, 'commit': 'a'*40, 'path': 'README.md', 'sha256': digest,
            'bytes': len(document.encode()), 'characters': len(document),
            'source': f'https://github.com/{family}/blob/{"a"*40}/README.md', 'local_file': ident+'.md',
            'acquisition': 'public_official_repository', 'content_reviewed': False, 'model_outputs_seen': False,
            'human_reviewed': False, 'model_pretraining_exposure': 'unknown'})
        fields = {f: {'assessment': 'unspecified', 'units': []} for f in FIELDS}
        fields['frontend'] = {'assessment': 'enumerated', 'units': [
            {'id': 'U001', 'kind': 'present', 'spans': [{'start': 0, 'end': 5}]}]}
        golds.append({'case_id': ident, 'source_sha256': digest, 'human_reviewed': False,
                      'fields': fields, 'exclusions': [], 'ambiguities': []})
    corpus = {'version': 'independent-profile-v1', 'cases': cases,
              'excluded_reserved_ids': ['PUBLIC-04', 'PUBLIC-05'], 'authoring_stage': 'before_gold_and_model_results'}
    write_json(spec / 'corpus.json', corpus)
    write_json(sources / 'gold.json', {'version': 'independent-profile-gold-v1', 'annotation_author': 'agent',
        'human_reviewed': False, 'model_outputs_seen': False, 'cases': golds})
    write_json(spec / 'gold-summary.json', {'gold_sha256': hashlib.sha256((sources / 'gold.json').read_bytes()).hexdigest()})
    write_json(prior / 'manifest.json', {'cases': []})
    write_json(spec / 'freeze.json', {'version': 'independent-profile-v1',
        'code_revision': '9af3f2a9bcd47d5e3bb40860fe674434787b442a', 'content_read': False,
        'model_outputs_seen': False, 'settings': SETTINGS,
        'lf_normalized_files': {'ai_service/agentfit_ai/base.py': hashlib.sha256(b'# frozen production\n').hexdigest()}})
    return spec / 'corpus.json', sources / 'gold.json', spec / 'freeze.json'
