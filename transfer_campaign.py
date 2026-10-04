#!/usr/bin/env python3
"""Bounded exact comparison with the known-cost transfer criterion.

Run `python transfer_campaign.py --output-dir DIRECTORY`; the directory must be
new or empty. Inputs and all positive/negative outcomes are retained. --pilot
runs a deterministic prefix of each domain and is never counted as full evidence.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import itertools
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'src'))
from admission import Tenant
from commitment import Snapshot, certify_plan
from transfer_oracle import certify_by_transfer, tenant_traces, evaluate

PROFILES = ((1,1,1,1),(1,2,3,2),(2,2,3,3),(0,1,2,2),(0,2,3,2),(0,2,3,3))


def state(cal, phase, q, lead, profiles, headroom):
    ts = []
    for i, (x,b,T,r) in enumerate(profiles):
        ts.append(Tenant(q[i], lead[i], max(1, q[i]+lead[i])+headroom,
                         x,b,T,r))
    return Snapshot(tuple(cal), phase, tuple(ts))


def one_core():
    for H in (3,4):
        for word in itertools.product((-1,0), repeat=2):
            cal = tuple((v,) for v in word)
            for phase in range(2):
                for w in itertools.product((-1,0), repeat=H):
                    plan = tuple((v,) for v in w)
                    for q in range(w.count(0), H+1):
                        for lead in range(3):
                            for p in PROFILES:
                                for room in (0,1):
                                    yield state(cal,phase,[q],[lead],[p],room),plan


def two_core():
    cols = tuple(c for c in itertools.product((-1,0,1,2), repeat=2)
                 if len([x for x in c if x>=0]) == len(set(x for x in c if x>=0)))
    for ci, col in enumerate(cols):
        for nonconstant in (False,True):
            cal = (col, cols[(ci+5) % len(cols)]) if nonconstant else (col,)
            for p0, p1 in itertools.product(cols, repeat=2):
                plan = (p0,p1)
                use = [sum(i in c for c in plan) for i in range(3)]
                for variant in range(3):
                    q = [use[i]+int((variant+i)%3==1) for i in range(3)]
                    lead = [(variant+i)%3 for i in range(3)]
                    ps = [PROFILES[(variant+2*i)%len(PROFILES)] for i in range(3)]
                    yield state(cal, variant%len(cal), q, lead, ps, variant%2),plan


def saturated(s,plan):
    actual = [t.lead for t in s.tenants]
    ref = [0]*len(actual)
    for h,col in enumerate(plan):
        for i in col:
            if i>=0: actual[i]+=1
        for i in s.calendar[(s.phase+h)%len(s.calendar)]:
            if i>=0: ref[i]+=1
        if any(r>a for r,a in zip(ref,actual)): return False
    return True


def snapshot_only(s,plan):
    q = [t.backlog+t.lead for t in s.tenants]
    a = [t.lead for t in s.tenants]; r = [0]*len(q)
    for h,col in enumerate(plan):
        for i in col:
            if i>=0: a[i]+=1
        for i in s.calendar[(s.phase+h)%len(s.calendar)]:
            if i>=0 and q[i]: q[i]-=1;r[i]+=1
        if any(x>y for x,y in zip(r,a)):return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--pilot',type=int,default=0)
    args=ap.parse_args()
    if args.pilot<0: ap.error('--pilot must be nonnegative')
    out=args.output_dir.resolve()
    if out.exists() and any(out.iterdir()):ap.error('output directory must be empty')
    out.mkdir(parents=True,exist_ok=True)
    if sys.platform.startswith('linux'):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
        resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
        resource.setrlimit(resource.RLIMIT_CPU,(240,245))
    start=time.perf_counter();cpu=time.process_time()
    totals={};groups={};comparisons=0;examples={}
    with (out/'cases.jsonl').open('w') as stream:
        for name, iterator in (('single_core',one_core()),('two_core',two_core())):
            c=defaultdict(int)
            for index,(s,p) in enumerate(iterator):
                if args.pilot and index>=args.pilot:break
                d=s.to_dict();cert=certify_plan(s,p);ts=certify_by_transfer(d,p)
                if cert['safe']!=ts['safe']:
                    raise AssertionError(json.dumps({'state':d,'plan':p,'cert':cert,'ts':ts}))
                snap=snapshot_only(s,p);sat=saturated(s,p)
                if sat and not ts['safe']:raise AssertionError('conservative control unsafe')
                if ts['safe'] and not snap:raise AssertionError('zero arrival not legal')
                c['cases']+=1;c['safe']+=int(ts['safe']);c['denied']+=int(not ts['safe'])
                for k in ('traces','intervals','slackless','unsafe_traces'):c[k]+=ts[k]
                c['snapshot_false_accepts']+=int(snap and not ts['safe'])
                c['saturated_false_rejects']+=int(not sat and ts['safe'])
                key=(s.calendar,s.phase,p,tuple((t.backlog,t.lead,1 if t.tokens else t.refill) for t in s.tenants))
                if key in groups:
                    comparisons+=1
                    if groups[key]!=(cert['safe'],cert['first_failure']):raise AssertionError('monitor abstraction mismatch')
                else:
                    # The earliest pair is invariant; a producer's concrete witness
                    # time need not be. Store verdict and first pair only below.
                    groups[key]=(cert['safe'],cert['first_failure'])
                row={'domain':name,'case':index,'snapshot':d,'plan':p,'producer':cert,
                     'transfer':ts,'snapshot_only':snap,'saturated_calendar':sat}
                stream.write(json.dumps(row,separators=(',',':'))+'\n')
                for k,cond in (('snapshot_false_accept',snap and not ts['safe']),
                               ('saturated_false_reject',not sat and ts['safe'])):
                    if cond and k not in examples:examples[k]=row
            c['disagreements']=0
            totals[name]=dict(c)
    # Snapshot abstraction compares the accepted set/first failure, never
    # assumes equality of the underlying arrival languages.
    summary={'campaign':'transfer-reduction','full_campaign':not bool(args.pilot),
             'domains':totals,'total_cases':sum(v['cases'] for v in totals.values()),
             'monitor_equivalence_comparisons':comparisons,'disagreements':0,
             'examples':examples,'cpu_seconds':time.process_time()-cpu,
             'wall_seconds':time.perf_counter()-start,
             'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'interpretation':'Independent finite TS-predicate implementation, not upstream SPT runtime or a Rocq proof'}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='examples'},indent=2))

if __name__=='__main__':main()
