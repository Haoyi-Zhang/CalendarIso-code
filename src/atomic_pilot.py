"""Bounded measured pilot of the new universal atomic-handler obligation."""
import itertools,json,time,resource,os
from pathlib import Path
from atomic import certify_atomic
from atomic_oracle import game,capacity_oracle,check_atomic_witness


def main():
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(35,40))
    cpu=time.process_time();wall=time.perf_counter()
    records=[];cases=states=edges=bad=0
    for m,n,h in ((1,2,3),(2,3,2)):
        columns=[x for x in itertools.product(range(-1,n),repeat=m) if len([i for i in x if i>=0])==len(set(i for i in x if i>=0))]
        for col in columns:
            for costs in itertools.product((1,2),repeat=n):
                cert=certify_atomic((col,),costs,[2]*n,[2]*n)
                exact=game((col,),costs,2,2,h)
                independent,c=capacity_oracle((col,),costs,[2]*n,[2]*n)
                assert cert['safe']==exact['safe']==independent,(col,costs,cert,exact)
                if not cert['safe']:
                    assert check_atomic_witness((col,),costs,[2]*n,[2]*n,cert)
                    bad+=1
                cases+=1;states+=exact['states'];edges+=exact['schedule_edges']
                records.append({'cores':m,'tenants':n,'calendar':[col],'costs':costs,'horizon':h,**exact})
    result={'cases':cases,'denied':bad,'states':states,'schedule_edges':edges,'disagreements':0,
            'method':'all FIFO arrival compositions, forall arrivals / exists work-conserving dispatch, initially empty with full buckets',
            'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.perf_counter()-wall,
            'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1,'records':records}
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,default=Path(__file__).resolve().parents[1]/'results')
    args=ap.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'atomic-pilot.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))

if __name__=='__main__':main()
