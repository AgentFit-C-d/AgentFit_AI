"""In-process AI HTTP connection; no remote endpoint or credential configuration."""
import httpx

from agentfit_ai.profile import FIELDS
from .schema import ContractError, check_review

MEDIA = {'TEXT': 'text/plain', 'MARKDOWN': 'text/markdown', 'PDF': 'application/pdf'}


def synthetic_analysis(document, document_id):
    """Fixed synthetic fixture, deliberately not a general document analyzer."""
    if document.strip() != 'MockPlan uses React.':
        return {'contract': 'confirmation-v2', 'outcome': 'failed', 'error': 'ANALYSIS_FAILURE'}
    data = dict.fromkeys(FIELDS)
    data.update(project_name='MockPlan', frontend=['React'])
    evidence = {f: [] for f in FIELDS}
    for field, text in [('project_name', 'MockPlan'), ('frontend', 'React')]:
        start = document.index(text)
        evidence[field] = [{'documentId': document_id, 'start': start, 'end': start + len(text)}]
    return {'contract': 'confirmation-v2', 'outcome': 'needs_confirmation',
            'profile': {'data': data, 'sources': {f: 'UNKNOWN' if data[f] is None else 'DOCUMENT' for f in FIELDS},
                        'evidence': evidence, 'unknownFields': [f for f in FIELDS if data[f] is None]},
            'fieldStates': {f: 'unknown' if data[f] is None else 'suggested' for f in FIELDS},
            'questions': [{'field': f, 'reason': 'CONFIRM_SUGGESTION', 'questionId': 'confirm_' + f}
                          for f in FIELDS if data[f] is not None],
            'error': 'REVIEW_CONFIRMATION_REQUIRED'}


class LocalAnalysisGateway:
    def __init__(self, ai_app):
        self.ai_app = ai_app

    async def analyze(self, kind, body, document_id, request_id):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.ai_app, raise_app_exceptions=False),
                                     base_url='http://mock-ai.invalid', trust_env=False) as client:
            response = await client.post('/internal/v1/analyze', content=body, headers={
                'Authorization': 'Bearer mock-internal', 'Content-Type': MEDIA[kind],
                'X-Document-Id': document_id, 'X-Document-Kind': kind,
                'X-Request-Id': request_id, 'X-AgentFit-Analysis-Contract': 'confirmation-v2'})
        try:
            if len(response.content) > 1_500_000:
                raise ValueError
            result = response.json()
            if type(result) is not dict:
                raise ValueError
        except (ValueError, UnicodeError):
            raise ContractError(502, 'AI_INVALID_OUTPUT') from None
        if response.status_code != 200:
            code = result.get('error')
            if code in ('DOCUMENT_TOO_LARGE', 'DOCUMENT_TOO_LONG', 'PDF_TOO_MANY_PAGES'):
                raise ContractError(413, 'INPUT_TOO_LARGE')
            if code == 'DOCUMENT_EMPTY':
                raise ContractError(422, 'EMPTY_DOCUMENT')
            if code == 'PDF_PARTIAL_TEXT':
                raise ContractError(422, 'PARTIAL_EXTRACTION')
            if code in ('DOCUMENT_INVALID_UTF8', 'PDF_INVALID', 'PDF_LOCKED'):
                raise ContractError(422, 'UNREADABLE_DOCUMENT')
            if code == 'INVALID_ANALYSIS_RESULT':
                raise ContractError(502, 'AI_INVALID_OUTPUT')
            if response.status_code in (408, 504):
                raise ContractError(504, 'ANALYSIS_TIMEOUT')
            raise ContractError(503 if response.status_code == 503 else 502, 'AI_UNAVAILABLE')
        if result.get('requestId') != request_id or result.get('contract') != 'confirmation-v2':
            raise ContractError(502, 'AI_INVALID_OUTPUT')
        if set(result) == {'contract', 'outcome', 'error', 'requestId'} and result['outcome'] == 'failed':
            raise ContractError(502, 'AI_UNAVAILABLE')
        if (set(result) != {'contract', 'outcome', 'error', 'requestId', 'profile', 'fieldStates', 'questions'}
                or result['outcome'] != 'needs_confirmation' or result['error'] != 'REVIEW_CONFIRMATION_REQUIRED'):
            raise ContractError(502, 'AI_INVALID_OUTPUT')
        review = {k: result[k] for k in ('contract', 'fieldStates', 'questions')}
        check_review(result['profile'], review)
        return {'profile': result['profile'], 'review': review}
