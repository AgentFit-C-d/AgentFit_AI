"""Lossless Markdown/text sections; no semantic filtering or source rewriting."""
from dataclasses import dataclass
import re

class SectionError(ValueError):
    pass

@dataclass(frozen=True)
class Section:
    id: str
    start: int
    end: int
    path: tuple[str, ...]
    text: str

_ATX = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+[ \t]*)?$")
_SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

def split_sections(document, max_chars=12000):
    if type(document) is not str or not document.strip() or type(max_chars) is not int or max_chars<1:
        raise SectionError("SECTION_LIMIT")
    lines=document.splitlines(keepends=True)
    offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line))
    heading_cache={}
    def paragraph_line(line):
        stripped=line.rstrip("\r\n")
        compact=stripped.replace(" ","").replace("\t","")
        thematic=len(compact)>=3 and any(set(compact)=={marker} for marker in "-*_")
        return (bool(stripped.strip()) and not stripped.startswith(("    ","\t","|"))
                and not re.match(r"^ {0,3}(?:[-+*][ \t]+|[0-9]{1,9}[.)][ \t]+|>)",stripped)
                and not _ATX.match(stripped) and not _FENCE.match(stripped) and not thematic)
    def heading(i):
        if i in heading_cache:return heading_cache[i]
        line=lines[i].rstrip("\r\n")
        m=_ATX.match(line)
        if m:
            result=(len(m[1]),m[2],1);heading_cache[i]=result;return result
        if not paragraph_line(lines[i]):
            heading_cache[i]=None;return None
        j=i+1
        while j<len(lines):
            m=_SETEXT.match(lines[j].rstrip("\r\n"))
            if m:
                title="\n".join(x.rstrip("\r\n") for x in lines[i:j]).strip()
                result=((1 if m[1][0]=="=" else 2),title,j-i+1)
                heading_cache[i]=result;return result
            if not paragraph_line(lines[j]):break
            j+=1
        for n in range(i,j):heading_cache[n]=None
        return None
    blocks=[];i=0
    while i<len(lines):
        first=i;h=heading(i)
        fence=_FENCE.match(lines[i].rstrip("\r\n"))
        if fence:
            marker=fence[1];i+=1
            while i<len(lines):
                closing=_FENCE.match(lines[i].rstrip("\r\n"));i+=1
                if closing and closing[1][0]==marker[0] and len(closing[1])>=len(marker) and not closing[2].strip():break
            h=None
        elif h:i+=h[2]
        elif lines[i].startswith(("    ","\t")):
            i+=1
            while i<len(lines) and (not lines[i].strip() or lines[i].startswith(("    ","\t"))):i+=1
        else:
            i+=1
            while i<len(lines) and not heading(i) and not _FENCE.match(lines[i].rstrip("\r\n")):
                if not lines[i].strip():
                    i+=1;break
                if not lines[i-1].strip():break
                i+=1
        blocks.append((offsets[first],offsets[i],h))
    result=[];stack=[];start=None;end=None;path=()
    def flush():
        if start is not None:
            result.append(Section("S"+str(len(result)+1).zfill(4),start,end,path,document[start:end]))
    for a,b,h in blocks:
        if b-a>max_chars:raise SectionError("SECTION_LIMIT")
        if h:
            flush();start=None
            while stack and stack[-1][0]>=h[0]:stack.pop()
            stack.append((h[0],h[1]))
        if start is not None and b-start>max_chars:
            flush();start=None
        if start is None:start=a;path=tuple(title for _,title in stack)
        end=b
    flush()
    if not result or "".join(s.text for s in result)!=document:raise SectionError("SECTION_COVERAGE")
    return result

def batch_sections(sections, max_chars=12000):
    if not sections or type(max_chars) is not int or max_chars<1:
        raise SectionError("SECTION_LIMIT")
    sizes=[len(s.text) for s in sections]
    if any(n>max_chars for n in sizes) or sum(sizes)>2*max_chars:
        raise SectionError("SECTION_LIMIT")
    if len(sections)==1:return [list(sections)]
    candidates=[];left=0;total=sum(sizes)
    for i,n in enumerate(sizes[:-1],1):
        left+=n;right=total-left
        if max(left,right)<=max_chars:candidates.append((abs(left-right),i))
    if not candidates:raise SectionError("SECTION_LIMIT")
    cut=min(candidates)[1]
    return [list(sections[:cut]),list(sections[cut:])]
