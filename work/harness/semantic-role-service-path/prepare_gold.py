"""Pre-register explicit facts and disputed items before any live output is seen."""
import json
from pathlib import Path

OUT = Path('E:/AgentFit/output/semantic-role-service-path-v1')
docs = {name: (OUT / (name + '.md')).read_text(encoding='utf-8') for name in ('documenso', 'linkding')}


def fact(field, *aliases):
    return {'field': field, 'aliases': list(aliases)}


gold = {
    'documenso': {
        'positive': [fact('project_name', 'Documenso'), fact('frontend', 'React Router'),
            fact('frontend', 'Tailwind'), fact('frontend', 'shadcn/ui'), fact('frontend', 'Radix UI'),
            fact('backend', 'Hono'), fact('database', 'Postgres', 'postgres'),
            fact('external_integrations', 'Stripe'), fact('features', 'Signing documents', 'document-signing')],
        'forbidden': [
            {'aliases': ['Payments'], 'fields': ['external_integrations', 'domain']},
            {'aliases': ['DocuSign', 'Discord', 'Cal.com', 'Product Hunt'], 'fields': ['external_integrations']},
            {'aliases': ['Stripe'], 'fields': ['frontend', 'backend', 'database', 'deployment', 'domain']},
            {'aliases': ['TypeScript', 'React Router', 'Hono', 'Prisma', 'Tailwind', 'shadcn/ui', 'Radix UI',
                         'react-email', 'Lingui', 'tRPC', 'pdf.js', '@libpdf/core', '@cantoo/pdf-lib', 'Biome',
                         'Playwright'], 'fields': ['external_integrations']},
            {'aliases': ['Fork', 'clone', 'npm run', 'contribut', 'Join', 'Tell us', 'Contact us',
                         'Open detailed', 'signing up'], 'fields': ['features']}],
        'humanReview': [
            {'aliases': ['self-host', 'Docker', 'docker', 'Deployment'], 'reason': 'self-hosting and local setup versus adopted deployment'},
            {'aliases': ['Prisma', 'tRPC', 'TypeScript', 'react-email', 'Lingui', 'PDF', 'pdf', 'S3', 'Vercel', 'Railway', 'render'],
             'reason': 'library purpose, field granularity or development/deployment context requires review'},
            {'aliases': ['Payments'], 'reason': 'independent feature status of purpose-only wording; external/domain are forbidden above'},
            {'aliases': ['web', 'SaaS', 'document', 'signature', 'signing'], 'reason': 'delivery form/domain and broad capability granularity'}]},
    'linkding': {
        'positive': [fact('project_name', 'linkding'), fact('backend', 'Django'),
            fact('frontend', 'JavaScript'), fact('project_type', 'Progressive Web App', 'PWA'),
            fact('external_integrations', 'Internet Archive'),
            fact('features', 'Organize bookmarks', 'tags'), fact('features', 'Bulk editing'),
            fact('features', 'Markdown notes'), fact('features', 'read it later'),
            fact('features', 'Share bookmarks'), fact('features', 'titles'), fact('features', 'descriptions'),
            fact('features', 'icons'), fact('features', 'archive websites'),
            fact('features', 'Import and export', 'Import', 'export'), fact('features', 'Extensions', 'bookmarklet'),
            fact('features', 'SSO', 'OIDC'), fact('features', 'REST API'), fact('features', 'Admin panel')],
        'forbidden': [
            {'aliases': ['Node.js'], 'fields': ['backend', 'deployment']},
            {'aliases': ['Django', 'Python', 'Node.js', 'OIDC', 'REST API', 'Netscape', 'Firefox', 'Chrome', 'Markdown',
                         'uv', 'pytest', 'ruff', 'djlint', 'prettier'], 'fields': ['external_integrations']},
            {'aliases': ['Clean UI', 'minimal', 'fast', 'readability', 'setup', 'make ', 'createsuperuser',
                         'submit a PR', 'Run tests', 'Linting', 'Formatting', 'contribut'], 'fields': ['features']}],
        'humanReview': [
            {'aliases': ['self-host', 'host yourself', 'Docker', 'docker', 'DevContainers'],
             'reason': 'supported install method versus adopted production deployment'},
            {'aliases': ['Python', 'Django templates', 'bookmark manager', 'bookmarks', 'HTML'],
             'reason': 'runtime versus prerequisites, delivery form/domain, capability granularity'},
            {'aliases': ['Internet Archive'], 'reason': 'provided integration is explicit, deployment usage is not; other fields require review'}]}
}
for name, entry in gold.items():
    for group in ('positive', 'forbidden', 'humanReview'):
        for row in entry[group]:
            # A rule can include variants; at least one must be grounded in source.
            assert any(alias.casefold() in docs[name].casefold() for alias in row['aliases']), (name, row)
    for index, row in enumerate(entry['positive']):
        row['id'] = f'{name}-fact-{index+1:02}'
payload = {'version': 'role-service-document-v1', 'authoring': 'before any live response',
    'human_reviewed': False,
    'scoring': 'Count matching explicit facts once; false output proposals include forbidden role/field claims. Uncovered outputs are human-review, never presumed correct. Comparisons use final Profile proposals, not human approval.',
    'documents': gold}
with (OUT / 'gold.json').open('x', encoding='utf-8') as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)
print(json.dumps({name: len(entry['positive']) for name, entry in gold.items()}))
