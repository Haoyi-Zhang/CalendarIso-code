#!/usr/bin/env python3
"""Reproduce retained finite evidence without changing the reference results.

Python standard library only. Linux resource enforcement; one child at a time.
No network, model service, device access, deployment or repository dependency.
"""
from __future__ import annotations
import argparse
import filecmp
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parent/'src'))
from experiment_env import configure, environment

ROOT=Path(__file__).resolve().parent
PERFORMANCE={'cpu_seconds','wall_seconds','peak_rss_kib'}

def scientific(result):
    return {k:v for k,v in result.items() if k not in PERFORMANCE}


def same_record_text(fresh, retained):
    # Text-mode JSONL writers use host line endings. Normalize only CRLF/LF
    # through universal-newline decoding; compare every other literal character.
    # No dropped fields, numeric coercion, reordering, or tolerance is applied.
    return fresh.read_text(encoding='utf-8') == retained.read_text(encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,help='Keep fresh measurements and command output here; default uses a disposable directory.')
    ap.add_argument('--portable',action='store_true',help='Explicit non-Linux run: checked affinity where available; no Linux CPU/address-space/RSS claim. Child wall deadlines remain enforced.')
    args=ap.parse_args()
    if not args.portable and (not sys.platform.startswith('linux') or not hasattr(os,'sched_setaffinity')):
        raise SystemExit('This measured runner requires Linux CPU affinity and resource limits; no unbounded fallback is used.')
    if args.portable:
        os.environ['CALENDARISO_PORTABLE']='1'
    resource_mode=configure(cpu_soft=600,cpu_hard=605)
    resource=None
    if sys.platform.startswith('linux'):
        import resource
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
    started=time.perf_counter();before=resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    commands=[]
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0'}
    python=[sys.executable,'-B']+(['-O'] if sys.flags.optimize else [])
    try:
        for program,filename in [('pilot.py','pilot.json'),('plan_pilot.py','multicore-pilot.json'),('atomic_pilot.py','atomic-pilot.json')]:
            cmd=python+[str(ROOT/'src'/program),'--output-dir',str(out)]
            result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
            (out/(program+'.txt')).write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(f'{program} exited {result.returncode}: {result.stderr[-1000:]}')
            fresh=json.loads((out/filename).read_text())
            retained=json.loads((ROOT/'results'/filename).read_text())
            if scientific(fresh)!=scientific(retained):
                raise RuntimeError(f'{filename}: scientific results do not match retained evidence')
            commands.append({'program':program,'exit_code':0,'cases':fresh['cases'],'scientific_fields_match':True})
        test_counts={}
        for test_file,expected in [('test_contracts.py',18),('test_transfer.py',12),('test_runtime.py',14),('test_runtime_grid.py',5),('test_constant_columns.py',3),('test_evidence_gates.py',2),('test_environment.py',3),('test_workflow_cost.py',2)]:
            result=subprocess.run(python+[str(ROOT/'tests'/test_file)],
                                  cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
            (out/(test_file+'.txt')).write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(test_file+' failed: '+result.stderr[-2000:])
            if f'Ran {expected} tests' not in result.stderr:
                raise RuntimeError('Unexpected test count in '+test_file)
            test_counts[test_file]=expected
        result=subprocess.run(python+[str(ROOT/'transfer_campaign.py'),
                               '--output-dir',str(out/'transfer')],
                              cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
        (out/'transfer_campaign.txt').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise RuntimeError('Transfer campaign failed: '+result.stderr[-2000:])
        transfer=json.loads((out/'transfer/summary.json').read_text())
        expected_transfer=json.loads((ROOT/'results/transfer/summary.json').read_text())
        if scientific(transfer)!=scientific(expected_transfer):
            raise RuntimeError('Transfer scientific fields do not match retained results')
        if not same_record_text(out/'transfer/cases.jsonl',ROOT/'results/transfer/cases.jsonl'):
            raise RuntimeError('Transfer per-case records do not match')
        protocol=json.loads((ROOT/'inputs/runtime-protocol.json').read_text())
        runtime_shards=[]
        for family in protocol['families']:
            fresh_dir=out/'runtime'/family
            result=subprocess.run(python+[str(ROOT/'runtime_campaign.py'),
                                   '--family',family,'--output-dir',str(fresh_dir)],
                                  cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
            (out/(family+'-runtime.txt')).write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(family+' runtime campaign failed: '+result.stderr[-2000:])
            retained_dir=ROOT/'results/runtime'/family
            a=json.loads((fresh_dir/'summary.json').read_text())
            b=json.loads((retained_dir/'summary.json').read_text())
            if scientific(a)!=scientific(b):raise RuntimeError(family+' summary differs')
            for name in ('inputs.jsonl','runs.jsonl'):
                if not same_record_text(fresh_dir/name,retained_dir/name):
                    raise RuntimeError(family+' '+name+' differs')
            # Compare decompressed records, not implementation-specific gzip bytes.
            with gzip.open(fresh_dir/'executions.jsonl.gz','rb') as a_log, gzip.open(retained_dir/'executions.jsonl.gz','rb') as b_log:
                while True:
                    a_block,b_block=a_log.read(1024*1024),b_log.read(1024*1024)
                    if a_block!=b_block:raise RuntimeError(family+' execution records differ')
                    if not a_block:break
            runtime_shards.append(family)
        result=subprocess.run(python+[str(ROOT/'runtime_summary.py'),
                               '--results-dir',str(out/'runtime'),'--replay-all',
                               '--output',str(out/'runtime/summary.json')],
                              cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
        (out/'runtime_summary.txt').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Full runtime log replay failed: '+result.stderr[-2000:])
        runtime=json.loads((out/'runtime/summary.json').read_text())
        if runtime!=json.loads((ROOT/'results/runtime/summary.json').read_text()):
            raise RuntimeError('Merged runtime results differ')
        for program,option,folder in [('constant_campaign.py','--output','constant-columns'),('workflow_cost.py','--output-dir','workflow-cost')]:
            result=subprocess.run(python+[str(ROOT/program),option,str(out/folder)],
                                  cwd=ROOT,env=env,text=True,capture_output=True,timeout=42)
            (out/(program+'.txt')).write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(program+' failed: '+result.stderr[-2000:])
            commands.append({'program':program,'exit_code':0,'scope':'local model cost/agreement; not historical timing equality'})
        after=resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
        summary={'status':'finite_reproduction_passed','scientific_completion':False,
                 'programs':commands,'unit_test_methods':sum(test_counts.values()),'test_files':test_counts,
                 'retained_finite_cases':66858,'transfer_comparison_cases':transfer['total_cases'],
                 'runtime_shards':runtime_shards,'runtime_traces':runtime['traces'],'runtime_runs':runtime['runs'],
                 'runtime_full_log_records_match':True,'runtime_mutations':runtime['mutations'],
                 'transfer_scientific_fields_match':True,'transfer_case_records_match':True,'seeded_general_plan_instances':300,
                 'seed':731203,'child_processes_concurrent':1,
                  'measured_child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime if resource else None,
                 'wall_seconds':time.perf_counter()-started,
                  'max_child_rss_kib':after.ru_maxrss if resource else None,
                  'environment':environment(),'resource_mode':resource_mode,
                  'child_wall_timeout_seconds':42,'optimized_children':bool(sys.flags.optimize),
                 'meaning':'Agreement of finite checks and tests; not proof-assistant verification.'}
        (out/'reproduction.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
    except (subprocess.TimeoutExpired,RuntimeError,OSError,ValueError) as exc:
        (out/'reproduction-error.txt').write_text(str(exc)+'\n')
        raise SystemExit(str(exc))
    finally:
        if temp is not None:temp.cleanup()

if __name__=='__main__':main()
