#!/usr/bin/env python3
"""Frozen paired continuous-run protocol. Single-process and standard library only."""
from __future__ import annotations
import argparse
import copy
import gzip
import json
from pathlib import Path
import random
import resource
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parent/'src'))
from runtime import execute
from runtime_replay import replay
ROOT=Path(__file__).resolve().parent


def workload(family: str, n: int, m: int, seed: int, horizon: int) -> dict:
    # RNG draws are independent of scheduler outcomes and chosen batch length.
    family_id=['steady','bursty','phase','alternating','heterogeneous'].index(family)
    rng=random.Random(seed*1000003 + family_id*1009+n*17+m)
    calendar=[[(p*m+j)%n for j in range(m)] for p in range(n)]
    phase=rng.randrange(len(calendar))
    monitors=[]
    for i in range(n):
        period=1+i%max(2,n//m)
        bucket=2+2*(i%3)
        monitors.append(dict(capacity=8+4*(i%3),bucket=bucket,tokens=bucket,period=period,refill=rng.randint(1,period)))
    offers=[]
    for t in range(horizon):
        col=[]
        for i in range(n):
            if family=='steady': amount=int(rng.randrange(10)<4)
            elif family=='bursty': amount=rng.randrange(1,5) if t%16<3 and rng.randrange(4)>0 else 0
            elif family=='phase':
                nxt=calendar[(phase+t+1)%len(calendar)]
                amount=rng.randrange(1,4) if i in nxt and rng.randrange(4)>0 else int(rng.randrange(40)==0)
            elif family=='alternating':
                active=(i<n//2)==((t//12)%2==0)
                amount=rng.randrange(1,4) if active and rng.randrange(3)==0 else 0
            else:
                amount=rng.randrange(1,5) if rng.randrange(n+1)<i+1 else 0
            col.append(amount)
        offers.append(col)
    return dict(calendar=calendar,phase=phase,tenants=monitors,offers=offers)


def aggregate(rows):
    groups={}
    for row in rows:
        key=f"{row['policy']}:{row['batch']}"
        if key not in groups:
            groups[key]=dict(runs=0,violating_runs=0,violation_slots=0,actual_work=0,reference_work=0,
                             admitted_work=0,final_backlog=0,avoidable_idle_core_slots=0,core_slots=0,
                             proposal_calls=0,checker_calls=0,interrupted_batches=0,fallback_slots=0)
        g=groups[key];g['runs']+=1
        g['violating_runs']+=int(row['metrics']['prefix_violation_slots']>0)
        g['violation_slots']+=row['metrics']['prefix_violation_slots']
        for k in ('actual_work','reference_work','admitted_work','final_backlog','avoidable_idle_core_slots','core_slots'):
            g[k]+=row['metrics'][k]
        for k in ('proposal_calls','checker_calls','interrupted_batches','fallback_slots'):
            g[k]+=row['control'][k]
    return groups


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--development',action='store_true')
    ap.add_argument('--family',choices=['steady','bursty','phase','alternating','heterogeneous'],help='Bounded family shard; selection is logistical, not outcome-based.')
    args=ap.parse_args()
    out=args.output_dir
    if out.exists() and any(out.iterdir()): raise SystemExit('Output directory must be empty.')
    out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((ROOT/'inputs/runtime-protocol.json').read_text())
    seeds=protocol['development_seeds'] if args.development else protocol['evaluation_seeds']
    families=[args.family] if args.family else protocol['families']
    before=time.process_time();wall=time.perf_counter()
    rows=[];trace_count=0;mutation_count=0;mutation_survivors=0;paired_admissions=True
    with (out/'inputs.jsonl').open('w') as inputs, (out/'runs.jsonl').open('w') as results, \
         (out/'executions.jsonl.gz').open('wb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=1) as logs:
        for family in families:
            for n,m in protocol['layouts']:
                for seed in seeds:
                    trace_id=f'{family}-n{n}-m{m}-s{seed}'
                    config=workload(family,n,m,seed,protocol['horizon'])
                    inputs.write(json.dumps(dict(trace_id=trace_id,config=config),sort_keys=True,separators=(',',':'))+'\n')
                    trace_count+=1
                    expected_admissions=None
                    for batch in protocol['batch_lengths']:
                        for policy in protocol['policies']:
                            log=execute(config,policy,batch)
                            metrics=replay(config,log)
                            admissions=[e['admitted'] for e in log['events']]
                            if expected_admissions is None:expected_admissions=admissions
                            paired_admissions &= admissions==expected_admissions
                            record=dict(trace_id=trace_id, family=family,tenants=n,cores=m,seed=seed,
                                        policy=policy,batch=batch,metrics=metrics,control=log['control'])
                            rows.append(record)
                            results.write(json.dumps(record,sort_keys=True,separators=(',',':'))+'\n')
                            logs.write((json.dumps(dict(trace_id=trace_id,log=log),sort_keys=True,separators=(',',':'))+'\n').encode())
                            if batch==protocol['main_batch_length'] and policy=='certified-interrupt':
                                for mutation in range(6):
                                    bad=copy.deepcopy(log)
                                    if mutation==0:bad['events'][0]['time']=False
                                    elif mutation==1:bad['events'][-1]['admitted'][0]+=1
                                    elif mutation==2:bad['events'][-1]['queue'][0]+=1
                                    elif mutation==3:bad['events'].pop()
                                    elif mutation==4:bad['events'][-1]['served'][0]=n
                                    else:bad['events'][-1]['tokens'][0]+=1
                                    mutation_count+=1
                                    try:replay(config,bad)
                                    except ValueError:pass
                                    else:mutation_survivors+=1
    groups=aggregate(rows)
    safety_failures=[(r['trace_id'],r['policy'],r['batch']) for r in rows
                     if r['policy'] in ('reservation','urgent','certified','certified-interrupt') and r['metrics']['prefix_violation_slots']]
    wc_failures=[(r['trace_id'],r['policy'],r['batch']) for r in rows
                 if r['policy'] in ('urgent','certified-interrupt') and r['metrics']['avoidable_idle_core_slots']]
    pairs=[]
    for family in families:
        for n,m in protocol['layouts']:
            selected=[r for r in rows if r['family']==family and r['tenants']==n and r['cores']==m and r['batch']==protocol['main_batch_length']]
            pairs.append(dict(family=family,tenants=n,cores=m,groups=aggregate(selected)))
    summary=dict(domain='development' if args.development else 'evaluation',
                 trace_count=trace_count,run_count=len(rows),main_runs=sum(r['batch']==protocol['main_batch_length'] for r in rows),
                 executed_slots=len(rows)*protocol['horizon'],groups=groups,per_cell=pairs,
                 paired_admissions=paired_admissions,safety_failures=safety_failures,work_conservation_failures=wc_failures,
                 mutations=mutation_count,mutation_survivors=mutation_survivors,
                 cpu_seconds=time.process_time()-before,wall_seconds=time.perf_counter()-wall,
                 peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 interpretation='Finite synthetic protocol only; zero-overhead discrete time; no hardware or population inference.')
    (out/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('groups','per_cell')},indent=2))
    if safety_failures or wc_failures or mutation_survivors or not paired_admissions:
        raise SystemExit('Declared continuous-execution invariant failed; inspect raw results.')

if __name__=='__main__':main()
