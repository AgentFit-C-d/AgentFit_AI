"""Deterministic source ranges for opt-in feature review."""

import re

from .solar import source_lines


_HEADING = re.compile(r"^ {0,3}#{1,3}(?:\s|$)")


def split_feature_sections(document: str, *, max_lines: int = 120) -> tuple[tuple[int, int], ...]:
    if type(max_lines) is not int or max_lines < 1:
        raise ValueError("invalid section size")
    lines = source_lines(document)
    if not lines:
        return ()
    starts = [1]
    starts.extend(line["id"] for line in lines[1:] if _HEADING.match(line["text"]))
    units = [(start, next_start - 1) for start, next_start in
             zip(starts, starts[1:] + [len(lines) + 1])]
    chunks = []
    for start, end in units:
        while start <= end:
            if chunks and start == chunks[-1][1] + 1 and end - chunks[-1][0] + 1 <= max_lines:
                chunks[-1] = (chunks[-1][0], end)
                break
            last = min(end, start + max_lines - 1)
            chunks.append((start, last))
            start = last + 1
    return tuple(chunks)


def validate_section_coverage(chunks: tuple[tuple[int, int], ...], line_count: int) -> None:
    if type(line_count) is not int or line_count < 0 or type(chunks) is not tuple:
        raise ValueError("invalid section coverage")
    next_line = 1
    for chunk in chunks:
        if (type(chunk) is not tuple or len(chunk) != 2 or
                any(type(item) is not int for item in chunk) or
                chunk[0] != next_line or chunk[1] < chunk[0] or
                chunk[1] - chunk[0] + 1 > 120):
            raise ValueError("invalid section coverage")
        next_line = chunk[1] + 1
    if next_line != line_count + 1:
        raise ValueError("invalid section coverage")
