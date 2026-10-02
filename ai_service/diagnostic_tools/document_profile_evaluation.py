"""Offline document baseline preparation. No key loading or live execution CLI."""
import argparse
import hashlib
import json
from pathlib import Path

from agentfit_ai.deepseek_evaluation import MODEL
from agentfit_ai.document_extraction import extract_document

LIMITS = {'maxCalls': 64, 'totalSeconds': 1800, 'perCallSeconds': 600, 'retries': 0}
REVIEW_MODEL = 'z-ai/glm-5.3'


def prepare_document(source: Path) -> dict:
    raw = source.read_bytes()
    extracted = extract_document('MARKDOWN', raw)
    return {'kind': 'MARKDOWN', 'sourceSha256': hashlib.sha256(raw).hexdigest(),
            'textSha256': hashlib.sha256(extracted.text.encode('utf-8')).hexdigest(),
            'byteSize': len(raw), 'characterCount': len(extracted.text),
            'document': extracted.text}


def estimate_calls(extraction_chunks: int, candidates: int, confirmed: int,
                   feature_curation: bool) -> dict:
    """A scenario, not a prediction of model-generated candidate counts."""
    if (type(extraction_chunks) is not int or extraction_chunks < 1 or
            type(candidates) is not int or not 0 <= candidates <= 240 or
            type(confirmed) is not int or not 0 <= confirmed <= candidates or
            type(feature_curation) is not bool):
        raise ValueError('INVALID_CALL_SCENARIO')
    stages = [
        {'stage': 'general_extraction', 'model': MODEL, 'calls': extraction_chunks},
        {'stage': 'operation_extraction', 'model': MODEL, 'calls': 1},
        {'stage': 'semantic_classification', 'model': MODEL, 'calls': (candidates + 7) // 8},
        {'stage': 'candidate_review', 'model': REVIEW_MODEL, 'calls': (confirmed + 19) // 20},
        {'stage': 'source_coverage', 'model': REVIEW_MODEL, 'calls': 1},
        {'stage': 'feature_curation', 'model': MODEL, 'calls': 4 if feature_curation else 0},
    ]
    total = sum(row['calls'] for row in stages)
    return {'stages': stages, 'total': total, 'withinCallLimit': total <= LIMITS['maxCalls'],
            'candidateCountIsAssumed': True,
            'curationCallsAreUpperBound': feature_curation}


def run_document_evaluation(source: Path, output: Path, *, execute: bool = False) -> dict:
    if execute is not False:
        raise ValueError('LIVE_EXECUTION_NOT_APPROVED')
    prepared = prepare_document(source)
    output.mkdir(parents=True, exist_ok=False)
    # Keep bytes, including BOM/CRLF, separate from parser-produced text offsets.
    with (output / 'source.md').open('xb') as handle:
        handle.write(source.read_bytes())
    with (output / 'document.txt').open('x', encoding='utf-8', newline='') as handle:
        handle.write(prepared.pop('document'))
    result = {'version': 'document-profile-baseline-v1', 'status': 'prepared_not_executed',
              'analysisMode': 'integrated-nvidia', 'semanticAssessment': True,
              'models': {'extraction': MODEL, 'classification': MODEL,
                         'review': REVIEW_MODEL, 'features': MODEL},
              'limits': dict(LIMITS), 'document': prepared, 'actualModelCalls': 0,
              'goldProvidedToAnalysis': False, 'oldCandidatesProvided': False,
              'liveAuthorization': 'required_separately', 'freeAccess': 'not_rechecked',
              'observedRuntimeDeployment': False}
    with (output / 'preflight.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_document_evaluation(args.source, args.output), ensure_ascii=False))


if __name__ == '__main__':
    main()
