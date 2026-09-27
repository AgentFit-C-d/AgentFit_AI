"""Lossless, bounded repair-only source units; no semantic classification."""
import re
from .sections import Section, SectionError

_BREAK = re.compile(r"(?<=[.!?。！？])[ \t]+|\r\n|\r|\n")
MAX_REPAIR_UNITS = 400

def split_repair_units(sections):
    result=[]
    for section in sections:
        cursor=0
        ends=[match.end() for match in _BREAK.finditer(section.text)]
        if not ends or ends[-1]!=len(section.text):ends.append(len(section.text))
        for end in ends:
            if end<=cursor:continue
            if len(result)>=MAX_REPAIR_UNITS:raise SectionError("SECTION_LIMIT")
            result.append(Section("U"+str(len(result)+1).zfill(4),
                section.start+cursor,section.start+end,section.path,section.text[cursor:end]))
            cursor=end
    return result
