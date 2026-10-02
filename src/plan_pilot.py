from __future__ import annotations
import itertools,json,os,resource,time
from pathlib import Path
from admission import Tenant
from commitment import Snapshot,certify_plan
from plan_oracle import full_oracle,reduced_oracle,joint_oracle,check_certificate


def main():
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(35,40))
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    begin,cpu=time.perf_counter(),time.process_time()
    cols=[c for c in itertools.product((-1,0,1,2),repeat=2) if len([i for i in c if i>=0])==len(set(i for i in c if i>=0))]
    cases=states=safe=joint=0
    for cal in cols:
        for plan in itertools.product(cols,repeat=2):
            used=[sum(i in col for col in plan) for i in range(3)]
            for p in range(16):
                ts=tuple(Tenant(used[i]+((p>>(i+1))&1),(p>>i)&1,
                                max(1,used[i]+((p>>(i+1))&1)+((p>>i)&1)),
                                (p>>(2-i))&1,1,3,1+(p+i)%3) for i in range(3))
                snap=Snapshot((cal,),0,ts);payload=snap.to_dict()
                cert=certify_plan(snap,plan)
                truth,edges=full_oracle(payload,plan)
                alt=reduced_oracle(payload,plan)
                assert cert['first_failure']==(list(truth) if truth else None),(payload,plan,cert,truth)
                assert truth==alt
                assert check_certificate(payload,plan,cert)
                if p==0:
                    assert joint_oracle(payload,plan)==truth
                    joint+=1
                cases+=1;states+=edges;safe+=cert['safe']
    result={'cases':cases,'safe':safe,'denied':cases-safe,'oracle_transitions':states,
            'joint_oracle_cases':joint,'disagreements':0,
            'definition':{'cores':2,'tenants':3,'reference_period':1,'plan_length':2,
                          'valid_columns':len(cols),'state_patterns':16,'pattern_selection':'explicit bit/phase formulas in source'},
            'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-begin,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[1]/'results')
    args=ap.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    out=args.output_dir/'multicore-pilot.json'
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
