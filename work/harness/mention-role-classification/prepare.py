"""Create immutable, narrowly scoped evaluation inputs before changing production code."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path('E:/AgentFit/output/mention-role-classification-v1')
OUT.mkdir(exist_ok=True)
for name in ('candidate_first_profile', 'candidate_semantic_assessment'):
    raw = (ROOT / 'ai_service/agentfit_ai' / (name + '.py')).read_bytes()
    with (OUT / ('baseline_' + name + '.py')).open('xb') as f: f.write(raw)


def case(name, document, mentions):
    candidates, gold = [], []
    for i, (quote, kind, constraint, field) in enumerate(mentions):
        start = document.index(quote)
        candidates.append({'id': f'C{i:03}', 'start': start, 'end': start + len(quote)})
        gold.append({'id': f'C{i:03}', 'kind': kind, 'constraint': constraint, 'field': field})
    return {'id': name, 'document': document, 'sourceSha256': hashlib.sha256(document.encode()).hexdigest(),
            'frozen': {'candidates': candidates, 'rejected': []}, 'gold': gold}


public = Path('E:/AgentFit/output/independent-profile-v1/PUBLIC-01.md').read_text(encoding='utf-8')
assert hashlib.sha256(public.encode()).hexdigest() == '5d26fe9a49507c3937d1a7950e0c4e620b1db08c741f8a36b98a83c90529e87b'
cases = [
    case('original-relation', public, [('Stripe', 'external_service', 'positive', 'external_integrations'),
                                     ('Payments', 'role_description', 'not_external', 'features')]),
    case('renamed-dash', 'Atlas adopts this external service: Aurapay — Payment processing. Customers can pay for orders.',
         [('Aurapay', 'external_service', 'positive', 'external_integrations'),
          ('Payment processing', 'role_description', 'not_external', 'features'),
          ('pay for orders', 'product_operation', 'positive', 'features')]),
    case('reversed-relation', 'Payment processing: provided by our adopted external service Meridia. Customers can complete checkout.',
         [('Payment processing', 'role_description', 'not_external', 'features'),
          ('Meridia', 'external_service', 'positive', 'external_integrations'),
          ('complete checkout', 'product_operation', 'positive', 'features')]),
    case('korean-order', '사용자는 주문 대금을 결제한다. 채택하여 연동한 외부 서비스는 토스페이먼츠다. 서비스 용도: 결제 처리.',
         [('주문 대금을 결제한다', 'product_operation', 'positive', 'features'),
          ('토스페이먼츠', 'external_service', 'positive', 'external_integrations'),
          ('결제 처리', 'role_description', 'not_external', 'features')]),
    case('common-word-service', 'Our adopted external service is named Payments. Its role is billing. Users can download invoices.',
         [('Payments', 'external_service', 'positive', 'external_integrations'),
          ('billing', 'role_description', 'not_external', 'features'),
          ('download invoices', 'product_operation', 'positive', 'features')]),
    case('normal-and-unclear', 'Selected external provider: Stripe. The checkout feature lets users pay for orders. '
         'Our notes mention Relay with no stated role. Simple and seamless is a tagline, not a service name or operation.',
         [('Stripe', 'external_service', 'positive', 'external_integrations'),
          ('pay for orders', 'product_operation', 'positive', 'features'),
          ('Relay', 'unclear', 'hold', 'other'),
          ('Simple and seamless', 'description', 'not_confirmed', 'other')]),
]
target = ROOT / 'ai_service/tests/fixtures/mention_role_cases.json'
with target.open('x', encoding='utf-8', newline='\n') as f:
    json.dump({'scope': 'user-confirmed role distinction; explicit counterfactual facts; no self-hosting or edition gates',
               'human_reviewed': False, 'cases': cases}, f, ensure_ascii=False, indent=2)
    f.write('\n')
with (OUT / 'inputs.json').open('x', encoding='utf-8') as f:
    json.dump({'fixtureSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
               'baselineSha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('baseline_*.py')}}, f)
print(json.dumps({'cases': len(cases), 'candidates': sum(len(c['gold']) for c in cases),
                  'positive': sum(g['constraint'] == 'positive' for c in cases for g in c['gold'])}))
