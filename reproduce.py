#!/usr/bin/env python3
"""Reproduce retained finite evidence without changing the reference results.

Python standard library only. Linux resource enforcement; one child at a time.
No network, model service, device access, deployment or repository dependency.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent
PERFORMANCE={'cpu_seconds','wall_seconds','peak_rss_kib'}

def scientific(result):
    return {k:v for k,v in result.items() if k not in PERFORMANCE}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,help='Keep fresh measurements and command output here; default uses a disposable directory.')
    args=ap.parse_args()
    if not sys.platform.startswith('linux') or not hasattr(os,'sched_setaffinity'):
        raise SystemExit('This measured runner requires Linux CPU affinity and resource limits; no unbounded fallback is used.')
    resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    temp=None
    if args.output_dir is None:
        temp=tempfile.TemporaryDirectory(prefix='isolation-reproduction-')
        out=Path(temp.name)
    else:
        out=args.output_dir.resolve()
        if out == (ROOT/'results').resolve():
            raise SystemExit('Use a separate output directory; retained reference results must not be overwritten.')
        if out.exists() and any(out.iterdir()):
            raise SystemExit('The reproduction output directory must be empty.')
        out.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    commands=[]
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0'}
    try:
        for program,filename in [('pilot.py','pilot.json'),('plan_pilot.py','multicore-pilot.json'),('atomic_pilot.py','atomic-pilot.json')]:
            cmd=[sys.executable,str(ROOT/'src'/program),'--output-dir',str(out)]
            result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
            (out/(program+'.txt')).write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(f'{program} exited {result.returncode}: {result.stderr[-1000:]}')
            fresh=json.loads((out/filename).read_text())
            retained=json.loads((ROOT/'results'/filename).read_text())
            if scientific(fresh)!=scientific(retained):
                raise RuntimeError(f'{filename}: scientific results do not match retained evidence')
            commands.append({'program':program,'exit_code':0,'cases':fresh['cases'],'scientific_fields_match':True})
        cmd=[sys.executable,str(ROOT/'tests/test_contracts.py')]
        result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
        (out/'tests.txt').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Contract tests failed: '+result.stderr[-2000:])
        if 'Ran 18 tests' not in result.stderr:raise RuntimeError('Unexpected contract test count')
        after=resource.getrusage(resource.RUSAGE_CHILDREN)
        summary={'status':'finite_reproduction_passed','scientific_completion':False,
                 'programs':commands,'unit_test_methods':18,'seeded_general_plan_instances':300,
                 'seed':731203,'child_processes_concurrent':1,
                 'measured_child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                 'wall_seconds':time.perf_counter()-started,
                 'max_child_rss_kib':after.ru_maxrss,
                 'meaning':'Agreement of finite checks and tests; not a proof-assistant result or publication-readiness decision.'}
        (out/'reproduction.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
    except (subprocess.TimeoutExpired,RuntimeError,OSError,ValueError) as exc:
        (out/'reproduction-error.txt').write_text(str(exc)+'\n')
        raise SystemExit(str(exc))
    finally:
        if temp is not None:temp.cleanup()

if __name__=='__main__':main()
