"""Read-only post-run audit; no transport, credentials, or model calls."""
import json
from pathlib import Path
import hashlib

OUTPUT=Path('E:/AgentFit/output/localsend-model-comparison-v1')


def read(path):
    return json.loads(path.read_bytes())


def audit(output=OUTPUT):
    frozen=read(output/'freeze.json')
    identity=dict(frozen['sha256']) | frozen['preserved_prior_files']
    for filename, expected in identity.items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==expected, filename
    package=read(output/'package.json')
    prior=read(Path('E:/AgentFit/output/status-model-comparison-v1/package.json'))
    assert package['documents']['LS']==prior['documents']['LS']
    assert package['jobs']==[j for j in prior['jobs'] if j['docId']=='LS']
    calls=[read(p) for p in sorted((output/'calls').glob('*-finished.json'))]
    assert len(calls)<=4 and all(c['docId']=='LS' for c in calls)
    summary=read(output/'summary.json')
    assert len(calls)==summary['calls_started']
    failure_seen=False
    raw_checks=0
    for i,call in enumerate(calls,1):
        assert not failure_seen, 'CALL_AFTER_FAILURE'
        job=package['jobs'][i-1]
        assert (call['arm'],call['batch'])==(job['arm'],job['batch'])
        assert read(output/'calls'/f'{i:02d}-request.json')==job['payload']
        assert read(output/'calls'/f'{i:02d}-wire-request.json')==dict(job['payload'],stream=True)
        if call['error'] is not None:
            failure_seen=True
            assert not (output/'calls'/f'{i:02d}-response.json').exists()
            continue
        raw=read(output/'calls'/f'{i:02d}-response.json')
        reply=json.loads(raw['choices'][0]['message']['content'])['decisions']
        validated=read(output/f"LS-{call['arm']}-{call['batch']:02d}-validated.json")
        rows={r['id']:r for r in validated['records']}
        for decision in reply:
            row=rows[decision['id']]
            assert (row['raw_field'],row['raw_status'])==(decision['field'],decision['status'])
            raw_checks+=1
    independent={}
    for arm,result in summary['documents']['LS'].items():
        expected={g['candidateId']:g for g in package['documents']['LS']['gold']}
        metrics=dict(observed=0, scored_observed=0, raw_false_confirmed=0,false_supported=0,
            positive_observed=0,normal_missing_observed=0,correct_excluded=0,
            excluded_gold_observed=0,held_observed=0,held_scored_observed=0,citation_defects=0)
        for row in result['records']:
            g=expected[row['id']]
            metrics['observed']+=1
            metrics['scored_observed']+=int(g['scored'])
            held=row['verdict']=='needs_confirmation'
            metrics['held_observed']+=int(held)
            metrics['held_scored_observed']+=int(held and g['scored'])
            if not g['scored']:
                continue
            correct=(row['raw_field'],row['raw_status'])==(g['expectedField'],g['expectedStatus'])
            false=row['raw_field']!='other' and row['raw_status']=='confirmed' and not correct
            metrics['raw_false_confirmed']+=int(false)
            metrics['false_supported']+=int(false and row['verdict']=='supported')
            if g['expectedStatus']=='confirmed':
                metrics['positive_observed']+=1
                metrics['normal_missing_observed']+=int(not(correct and row['verdict']=='supported'))
            if g['expectedVerdict']=='excluded':
                metrics['excluded_gold_observed']+=1
                metrics['correct_excluded']+=int(correct and row['verdict']=='excluded')
        metrics['citation_defects']=sum(e['citationDefect'] for e in result['evidence'])
        for key in ('raw_false_confirmed','false_supported','correct_excluded','citation_defects'):
            assert metrics[key]==result['metrics'][key]
        if result['complete']:
            assert metrics['normal_missing_observed']==result['metrics']['normal_missing']
        metrics['complete']=result['complete']
        metrics['unassessable']=16-metrics['observed']
        independent[arm]=metrics
    report={'frozen_and_prior_hashes_verified':len(identity),'input_and_gold_unchanged':True,
        'exact_payloads_verified':len(calls),'raw_field_status_preserved':raw_checks,
        'calls':len(calls),'retries':0,'fluent_reader_calls':0,'stopped_on_first_failure':failure_seen,
        'observed_only_metrics':independent,'whole_document_comparable':summary['comparable'],
        'metrics_note':'Unreturned candidates are unassessable, not observed normal omissions.',
        'model_calls_by_this_audit':0}
    with (output/'audit.json').open('x',encoding='utf-8') as handle:
        json.dump(report,handle,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': audit()
