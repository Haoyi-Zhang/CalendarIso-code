"""Same-input full model workflow cost, retaining the absence of useful-work gain.

No OS/dataplane scheduler is emulated or benchmarked. The two paths are owned
CPython schedulers; both include validation, dispatch, events, independent replay,
and canonical JSON serialization. Disk I/O and model-overhead charging are not
timed. The certificate path includes its existing independent sparse checker.
The exact 120 retained inputs are used, never a new generated favorable matrix.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from runtime import execute
from runtime_replay import replay
from experiment_env import configure, environment

ROOT=Path(__file__).resolve().parent


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':')).encode('utf-8')


def workflow(config,policy):
    log=execute(config,policy,4)
    metrics=replay(config,log)
    encoded=canonical({'log':log,'metrics':metrics})
    return log,metrics,hashlib.sha256(encoded).hexdigest()


def paired_check(config,results):
    a,b=results['urgent'],results['certified-interrupt']
    if [e['admitted'] for e in a[0]['events']] != [e['admitted'] for e in b[0]['events']]:
        raise AssertionError('comparator did not receive the same admitted work')
    for _,metrics,_ in (a,b):
        if metrics['prefix_violation_slots'] or metrics['avoidable_idle_core_slots']:
            raise AssertionError('required model invariant failed')
    # Equality is an observation on this protocol, not an assumed universal
    # ordering. Different per-tenant allocations and right-censored delays remain.
    return b[1]['actual_work']-a[1]['actual_work']


def run(output):
    if output.exists(): raise ValueError('fresh output path required')
    mode=configure(cpu_soft=240,cpu_hard=245)
    inputs=[]
    protocol=json.loads((ROOT/'inputs/runtime-protocol.json').read_text())
    for family in protocol['families']:
        inputs.extend(json.loads(s) for s in (ROOT/'results/runtime'/family/'inputs.jsonl').read_text().splitlines())
    if len(inputs)!=120 or len({v['trace_id'] for v in inputs})!=120:
        raise ValueError('the retained 120-input denominator is required')
    output.mkdir(parents=True)
    samples=[];decisions=[]
    raw=gzip.open(output/'executions.jsonl.gz','wt',encoding='utf-8')
    for item in inputs:
        hashes={};ratios=[];last=None
        for pair in range(3):
            results={};timings={}
            order=('urgent','certified-interrupt') if pair%2==0 else ('certified-interrupt','urgent')
            for policy in order:
                wall,cpu=time.perf_counter_ns(),time.process_time_ns()
                result=workflow(item['config'],policy)
                elapsed_cpu=time.process_time_ns()-cpu
                elapsed_wall=time.perf_counter_ns()-wall
                results[policy]=result;timings[policy]=(elapsed_wall,elapsed_cpu)
                if policy in hashes and hashes[policy]!=result[2]:
                    raise AssertionError('repeated model result changed')
                hashes[policy]=result[2]
                samples.append({'trace_id':item['trace_id'],'pair':pair,'policy':policy,
                                'wall_ns':elapsed_wall,'cpu_ns':elapsed_cpu,'output_sha256':result[2]})
                # Retain the timed output itself, outside both timers. The hash
                # binds this full log/metrics pair to its measured sample.
                raw.write(json.dumps({'trace_id':item['trace_id'],'pair':pair,
                                      'policy':policy,'log':result[0],'metrics':result[1]},
                                     sort_keys=True,separators=(',',':'))+'\n')
            delta=paired_check(item['config'],results)
            ratios.append(timings['certified-interrupt'][0]/max(1,timings['urgent'][0]))
            last=results
        decisions.append({'trace_id':item['trace_id'],'input_sha256':hashlib.sha256(canonical(item['config'])).hexdigest(),
                          'work_delta':delta,'wall_ratio_median':statistics.median(ratios),
                          'policies':{p:{'metrics':r[1],'control':r[0]['control'],'output_sha256':r[2]} for p,r in last.items()}})
    raw.close()
    summary={'inputs':120,'pairs_per_input':3,'workflow_executions':len(samples),
             'higher_work':sum(d['work_delta']>0 for d in decisions),'equal_work':sum(d['work_delta']==0 for d in decisions),
             'lower_work':sum(d['work_delta']<0 for d in decisions),
             'median_per_input_wall_ratio':statistics.median(d['wall_ratio_median'] for d in decisions),
             'wall_ratio_range':[min(d['wall_ratio_median'] for d in decisions),max(d['wall_ratio_median'] for d in decisions)],
             'cpu_ns_by_policy':{p:sum(s['cpu_ns'] for s in samples if s['policy']==p) for p in ('urgent','certified-interrupt')},
             'environment':environment(),'resource_mode':mode,
             'cost_scope':'validation, scheduling/proposals, certification and independent sparse checker when used, event construction, full independent replay, JSON serialization and SHA256; no disk I/O or physical overhead charged to model slots',
             'native_os_or_dataplane_scheduler':False,'scientific_acceptance':False}
    cpu=summary['cpu_ns_by_policy']
    summary['aggregate_cpu_ratio']=cpu['certified-interrupt']/cpu['urgent'] if cpu['urgent'] else None
    summary['cpu_scope']='sum of per-workflow process CPU samples; short Windows samples may round to zero, so no per-input CPU ratio is claimed'
    for name,obj in [('inputs.json',inputs),('samples.json',samples),('decisions.json',decisions),('summary.json',summary)]:
        (output/name).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    run(parser.parse_args().output_dir)
