#!/usr/bin/env python3
"""Reaggregate the complete frozen grid; optionally replay every archived event log.

Does not trust campaign summaries for run metrics. Counter fields are producer
instrumentation, not independently reconstructed algorithm authentication.
"""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent/'src'))
from runtime_replay import replay
ROOT = Path(__file__).resolve().parent
METRICS = ('actual_work','reference_work','admitted_work','final_backlog',
           'avoidable_idle_core_slots','core_slots')
COUNTERS = ('proposal_calls','checker_calls','interrupted_batches','fallback_slots')


def merge(rows):
    groups = {}
    for row in rows:
        k = f"{row['policy']}:{row['batch']}"
        g = groups.setdefault(k, dict(runs=0, violating_runs=0, violation_slots=0,
                                     **{k:0 for k in METRICS + COUNTERS}))
        g['runs'] += 1
        g['violating_runs'] += int(row['metrics']['prefix_violation_slots'] > 0)
        g['violation_slots'] += row['metrics']['prefix_violation_slots']
        for name in METRICS: g[name] += row['metrics'][name]
        for name in COUNTERS: g[name] += row['control'][name]
    return groups


def summarize(directory, replay_all=False):
    protocol = json.loads((ROOT/'inputs/runtime-protocol.json').read_text())
    rows = []; trace_ids = set(); mutations = 0; survivors = 0
    replayed = 0; paired = True
    for family in protocol['families']:
        folder = directory/family
        inputs = [json.loads(line) for line in (folder/'inputs.jsonl').read_text().splitlines()]
        configs = {r['trace_id']:r['config'] for r in inputs}
        if len(configs) != len(inputs): raise ValueError('Duplicate input identifier')
        expected_traces = {f'{family}-n{n}-m{m}-s{s}' for n,m in protocol['layouts']
                           for s in protocol['evaluation_seeds']}
        if configs.keys() != expected_traces: raise ValueError('Input grid differs from protocol')
        trace_ids.update(configs)
        local = [json.loads(line) for line in (folder/'runs.jsonl').read_text().splitlines()]
        keyed = {(r['trace_id'],r['policy'],r['batch']):r for r in local}
        expected = {(t,p,b) for t in configs for p in protocol['policies'] for b in protocol['batch_lengths']}
        if len(keyed) != len(local) or keyed.keys() != expected: raise ValueError('Run grid differs from protocol')
        for r in local:
            n,m = r['tenants'],r['cores']
            if r['family']!=family or [n,m] not in protocol['layouts'] or r['seed'] not in protocol['evaluation_seeds']:
                raise ValueError('Invalid experiment cell')
            if r['trace_id'] != f"{family}-n{n}-m{m}-s{r['seed']}": raise ValueError('Cell identity mismatch')
        saved = json.loads((folder/'summary.json').read_text())
        if saved['groups'] != merge(local): raise ValueError('Shard summary does not match raw rows')
        if saved['trace_count'] != len(configs) or saved['run_count'] != len(local): raise ValueError('Shard count mismatch')
        if saved['domain'] != 'evaluation': raise ValueError('Development data in evaluation')
        if replay_all:
            seen=set();admissions={}
            with gzip.open(folder/'executions.jsonl.gz','rt') as handle:
                for line in handle:
                    record = json.loads(line);log = record['log'];t = record['trace_id']
                    k=(t,log['policy'],log['batch'])
                    if k not in keyed or k in seen: raise ValueError('Duplicate or extra event log')
                    seen.add(k)
                    metrics=replay(configs[t],log)
                    if metrics!=keyed[k]['metrics'] or log['control']!=keyed[k]['control']:
                        raise ValueError('Replayed result differs from archived row')
                    admitted=[e['admitted'] for e in log['events']]
                    if t in admissions: paired &= admissions[t]==admitted
                    else:admissions[t]=admitted
                    replayed+=1
            if seen != expected: raise ValueError('Missing event log')
        rows.extend(local)
        mutations += saved['mutations'];survivors += saved['mutation_survivors']
        paired &= saved['paired_admissions']
    groups=merge(rows)
    safety=[(r['trace_id'],r['policy'],r['batch']) for r in rows
            if r['policy'] in ('reservation','urgent','certified','certified-interrupt') and r['metrics']['prefix_violation_slots']]
    wc=[(r['trace_id'],r['policy'],r['batch']) for r in rows
        if r['policy'] in ('urgent','certified-interrupt') and r['metrics']['avoidable_idle_core_slots']]
    cells=[dict(family=f,tenants=n,cores=m,groups=merge([r for r in rows if r['family']==f and
            r['tenants']==n and r['cores']==m and r['batch']==protocol['main_batch_length']]))
           for f in protocol['families'] for n,m in protocol['layouts']]
    # Matched unit-work outcomes are descriptive; they are not a new optimality theorem.
    main={(r['trace_id'],r['policy']):r for r in rows if r['batch']==protocol['main_batch_length']}
    paired_work={}
    for policy in protocol['policies']:
        deltas=[main[(t,policy)]['metrics']['actual_work']-main[(t,'urgent')]['metrics']['actual_work'] for t in sorted(trace_ids)]
        paired_work[policy]=dict(lower=sum(x<0 for x in deltas),equal=sum(x==0 for x in deltas),higher=sum(x>0 for x in deltas),sum_delta=sum(deltas))
    result=dict(protocol_complete=True,traces=len(trace_ids),runs=len(rows),main_runs=len(main),
                executed_slots=sum(r['metrics']['horizon'] for r in rows),groups=groups,per_cell=cells,
                paired_work_against_urgent=paired_work,paired_admissions=paired,
                safety_failures=safety,work_conservation_failures=wc,mutations=mutations,mutation_survivors=survivors,
                interpretation='Complete frozen finite synthetic protocol; exact descriptive aggregates; no device or statistical-population claim.')
    if safety or wc or survivors or not paired: raise ValueError('Invariant failed')
    return result,replayed


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results-dir',type=Path,default=ROOT/'results/runtime')
    ap.add_argument('--output',type=Path)
    ap.add_argument('--replay-all',action='store_true')
    a=ap.parse_args();summary,count=summarize(a.results_dir,a.replay_all)
    if a.output:a.output.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('groups','per_cell')},indent=2))
    if a.replay_all:print('Complete archived logs independently replayed:',count)
if __name__=='__main__':main()
