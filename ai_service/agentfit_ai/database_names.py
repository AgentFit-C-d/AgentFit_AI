"""Conservative database identity for deduplication, not semantic admission."""
import re


_POSTGRES_NAME = re.compile(
    r'(?:postgresql|postgres(?:[ \t]+sql)?)'
    r'(?:[ \t]+v?(?P<version>[0-9]+(?:\.[0-9]+)*))?'
    r'(?:[ \t]+(?:database|db))?',
    flags=re.IGNORECASE | re.ASCII,
)
_OMITTED_VERSION = re.compile(
    r'^[ \t]*(?:[()*_`:=~<>^+-][ \t]*)*'
    r'(?:(?:version[ \t]+|v)[ \t]*)?[0-9]',
    flags=re.IGNORECASE | re.ASCII,
)
# These qualified product names are not registered PostgreSQL aliases.
_QUALIFIED_PREFIX = re.compile(
    r'\b(?:aurora|alloydb|rds|cloud[ \t]+sql|azure[ \t]+database)'
    r'[ \t]+(?:for[ \t]+)?(?:[*_`][ \t]*)*$',
    flags=re.IGNORECASE | re.ASCII,
)


def database_identity(value: str) -> tuple[str, str | None]:
    """Recognize only explicit aliases; keep unspecified and exact versions apart."""
    matched = _POSTGRES_NAME.fullmatch(value.strip(' \t'))
    if matched is None:
        return ('literal', value)
    return ('postgresql', matched.group('version'))


def complete_database_mention(document: str, span: dict) -> bool:
    """Veto obvious truncated tokens, adjacent versions and qualified DB names.

    This is a conservative boundary check, not an inference of missing versions
    or a substitute for upstream semantic review of the complete document.
    """
    start, end = span['start'], span['end']
    if start and (document[start - 1].isalnum() or document[start - 1] in '_-/'):
        return False
    if _QUALIFIED_PREFIX.search(document[max(0, start - 80):start]):
        return False
    tail = document[end:end + 80]
    if tail and (tail[0].isalnum() or tail[0] == '_' or
                 len(tail) > 1 and tail[0] in '-./' and tail[1].isalnum()):
        return False
    return _OMITTED_VERSION.match(tail) is None
