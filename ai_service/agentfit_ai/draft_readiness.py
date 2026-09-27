"""Numeric pilot gates over reviewed counts; does not certify dataset provenance."""
import argparse
import json
import math
import statistics
from pathlib import Path
from .profile import FIELDS

def number(value, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        raise ValueError("INVALID_METRIC")
    if value < 0 or (type(value) is float and not math.isfinite(value)):
        raise ValueError("INVALID_METRIC")
    return value

def ratios(tp, fp, fn):
    return {"precision": tp/(tp+fp) if tp+fp else None,
            "recall": tp/(tp+fn) if tp+fn else None}

def p95(values):
    return sorted(values)[math.ceil(len(values)*.95)-1] if values else None

def quality(counts):
    return counts["precision"] is not None and counts["recall"] is not None and counts["precision"]>=.95 and counts["recall"]>=.90

def assess(rows):
    if type(rows) is not list:
        raise ValueError("INVALID_ROWS")
    totals={f:dict(tp=0,fp=0,fn=0,evidence_valid=0) for f in FIELDS}
    seen=set();docs={};latencies=[];reviews=[];errors=0;critical=0;each=True;gold_by_doc={}
    for row in rows:
        if type(row) is not dict or set(row)!={"document_id","run","elapsed_seconds","failed","critical_errors","fields","review"}:
            raise ValueError("INVALID_ROW")
        doc=row["document_id"];run=row["run"]
        if type(doc) is not str or not doc or type(run) is not int or run not in (0,1,2) or (doc,run) in seen:
            raise ValueError("INVALID_RUN")
        seen.add((doc,run));docs.setdefault(doc,set()).add(run)
        if type(row["failed"]) is not bool or type(row["fields"]) is not dict or set(row["fields"])!=set(FIELDS):
            raise ValueError("INVALID_FIELDS")
        latencies.append(number(row["elapsed_seconds"]))
        errors+=row["failed"];critical+=number(row["critical_errors"],True)
        tp=fp=fn=0;gold={}
        for field, counts in row["fields"].items():
            if type(counts) is not dict or set(counts)!={"tp","fp","fn","evidence_valid"}:
                raise ValueError("INVALID_COUNTS")
            for value in counts.values():number(value,True)
            if counts["evidence_valid"]>counts["tp"]+counts["fp"]:
                raise ValueError("INVALID_EVIDENCE_COUNT")
            if row["failed"] and (counts["tp"] or counts["fp"] or counts["evidence_valid"]):
                raise ValueError("FAILED_RUN_HAS_OUTPUT")
            for key,value in counts.items():totals[field][key]+=value
            tp+=counts["tp"];fp+=counts["fp"];fn+=counts["fn"]
            gold[field]=counts["tp"]+counts["fn"]
        if doc in gold_by_doc and gold_by_doc[doc]!=gold:
            raise ValueError("GOLD_CHANGED_BETWEEN_RUNS")
        gold_by_doc[doc]=gold
        each = each and not row["failed"] and quality(ratios(tp,fp,fn))
        review=row["review"]
        if run!=0 and review is not None:
            raise ValueError("REVIEW_MUST_USE_FIRST_RUN")
        if review is not None:
            if type(review) is not dict or set(review)!={"edits","seconds"}:
                raise ValueError("INVALID_REVIEW")
            edits=number(review["edits"],True);seconds=number(review["seconds"])
            reviews.append((edits/(tp+fn) if tp+fn else (0 if edits==0 else 1),seconds))
    by_field={f:ratios(c["tp"],c["fp"],c["fn"]) for f,c in totals.items()}
    total={key:sum(c[key] for c in totals.values()) for key in ("tp","fp","fn","evidence_valid")}
    overall=ratios(total["tp"],total["fp"],total["fn"])
    failure_rate=errors/len(rows) if rows else None
    edit_rate=statistics.mean(r[0] for r in reviews) if reviews else None
    median_review=statistics.median(r[1] for r in reviews) if reviews else None
    review_p95=p95([r[1] for r in reviews]);latency_p95=p95(latencies)
    checks={
        "sample_size":len(docs)>=10 and all(runs=={0,1,2} for runs in docs.values()),
        "overall_quality":quality(overall),
        "field_quality":all(quality(c) for c in by_field.values()),
        "each_run_quality":bool(rows) and each,
        "failure_rate":failure_rate is not None and failure_rate<=.05,
        "evidence":bool(rows) and total["tp"]+total["fp"]>0 and total["evidence_valid"]==total["tp"]+total["fp"],
        "critical_errors":bool(rows) and critical==0,
        "human_review_complete":bool(docs) and len(reviews)==len(docs),
        "edit_rate":edit_rate is not None and edit_rate<=.10,
        "review_time":median_review is not None and median_review<=120 and review_p95<=300,
        "latency":latency_p95 is not None and latency_p95<=60,
    }
    return {"revision":1,"scope":"numeric_only_requires_dataset_and_human_audit",
            "passed":all(checks.values()),"checks":checks,"documents":len(docs),"runs":len(rows),
            "overall":overall,"by_field":by_field,"failure_rate":failure_rate,
            "critical_errors":critical,"edit_rate":edit_rate,"review_median_seconds":median_review,
            "review_p95_seconds":review_p95,"latency_p95_seconds":latency_p95}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path)
    args=parser.parse_args()
    result=assess(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["passed"] else 1

if __name__=="__main__":
    raise SystemExit(main())
