"""Opt-in field meanings shared by candidate classification and review."""

FIELD_SEMANTICS_POLICIES = ('legacy', 'explicit-v1')

_EXPLICIT = """Field semantics explicit-v1. These definitions replace shorthand field descriptions above.
project_name: the explicitly named product, including source-written name variants.
project_type: the delivery form, such as a web dashboard, Web SaaS, mobile app or CLI. A product-specific noun phrase that explicitly contains the form is valid; it need not equal a canonical taxonomy label.
domain: the product's explicitly described business or problem area.
frontend: adopted client-side implementation languages, frameworks or runtimes, not generic UI features.
backend: adopted server-side implementation languages, frameworks or runtimes. A generic protocol, internal application module, repository name or user-uploaded technology example is not sufficient.
ai: a concrete model or AI API adopted for operating the product. Generic AI, an SDK/client, development-only tooling or a demo candidate does not establish an operating model.
database: a selected concrete database/storage engine. Generic data, a ledger concept or an outside storage provider does not establish an engine.
deployment: adopted hosting, cloud, runtime container or deployment environment. A technology mentioned inside user content is not the product's deployment choice.
features: specific user or product operations. A concise noun phrase is valid when its occurrence context explicitly establishes the operation; an infinitive or complete sentence is not required. A branded capability can qualify if the source defines what it does. Do not infer operations from a bare tool/component/input-document name or team task.
external_integrations: concrete outside services or providers the product integrates with, including authentication, notifications and backup storage. An internal module, open-source repository or generic standard is not an outside provider just because its name is concrete.
Certainty and scope: confirmed means explicitly required, adopted or provided in the document's target product scope. This is a planning document: confirmed requirements may be unimplemented. Do not demand an existing deployment or implementation evidence. Optional choices, undecided proposals, rejected choices and explicitly later expansion outside the target scope are not current confirmed facts. Distinguish such roadmap expansion from a required feature whose implementation is merely pending.
Judge the exact occurrence in its surrounding section and whole-document context. Repetition, a name variant or equivalent wording alone does not make an occurrence false. Review factual field/status correctness, not stylistic preferences or output deduplication. Do not delete a valid candidate merely because another candidate says the same thing; final projection handles identical values. Wrong field or wrong certainty still requires rejection. More rejections are not a better review.
"""


def field_semantics_instructions(policy):
    if type(policy) is not str or policy not in FIELD_SEMANTICS_POLICIES:
        raise ValueError('invalid field semantics policy')
    return '' if policy == 'legacy' else _EXPLICIT
