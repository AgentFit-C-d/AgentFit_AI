"""Mention roles are assertions about a referent, never a lexicon of names."""

MENTION_KINDS = ('external_service', 'product_operation', 'role_description', 'description', 'unclear', 'other')

MENTION_ROLE_INSTRUCTION = (
    'Identify what the exact candidate refers to before choosing its field. '
    'An external_service is the named outside provider/service itself, not its purpose. '
    'A product_operation is an explicitly stated action performed by the target product or its users. '
    'A role_description says what a tool/provider is used for; it is not the provider name. '
    'A description is a modifier, benefit or tagline, not a named service or operation. '
    'Read subject/action/provider relationships in sentences, lists and tables independently of '
    'their order. In a provider-purpose relationship, never copy the provider field onto its purpose. '
    'The purpose may support a feature only if its context explicitly establishes a product operation; '
    'otherwise retain it as tentative rather than inventing that operation. '
    'Determine roles from context, not capitalization, known brands or a word blacklist: even an '
    'ordinary action word may be a service name when the source explicitly names a service that way. '
    'Role uncertainty is not irrelevance. Preserve a relevant ambiguous candidate as tentative '
    'in its plausible field; never mark it confirmed or silently discard it. '
    'Other Profile fields keep their existing definitions. '
)
