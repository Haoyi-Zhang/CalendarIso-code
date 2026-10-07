"""Run-length certificate agreement and paired elapsed timings on fixed inputs."""
from __future__ import annotations
import argparse
import ctypes
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from admission import Tenant
from commitment import Snapshot, certify_plan
from constant_columns import certify_constant


def run(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetProcessAffinityMask(ctypes.windll.kernel32.GetCurrentProcess(), 1)
    rng = random.Random(360071)
    checks = 0
    for case in range(2000):
        n = rng.randrange(2, 7)
        m = rng.randrange(1, min(n, 3) + 1)
        length = rng.randrange(1, 25)
        period = rng.randrange(1, 9)
        calendar = tuple(tuple(rng.sample(range(n), m)) for _ in range(period))
        column = tuple(rng.sample(range(n), m)) if case % 3 else tuple([-1] * m)
        tenants = []
        for i in range(n):
            backlog = length + rng.randrange(4) if i in column else rng.randrange(3)
            lead = rng.randrange(7)
            refill = rng.randrange(1, 5)
            tenants.append(Tenant(backlog, lead, backlog + lead + rng.randrange(3),
                                  rng.randrange(2), 1, 4, refill))
        # A zero occupancy tenant still has a positive buffer capacity.
        tenants = tuple(Tenant(v.backlog, v.lead, max(1, v.capacity), v.tokens, v.bucket, v.period, v.refill) for v in tenants)
        snap = Snapshot(calendar, rng.randrange(period), tenants)
        old = certify_plan(snap, (column,) * length)
        new = certify_constant(snap, column, length)
        if new != old:
            raise AssertionError((case, snap.to_dict(), column, length, new, old))
        checks += 1
    huge = Snapshot(((1,),), 0, (Tenant(10**12, 0, 10**12, 1, 1, 1, 1),
                                  Tenant(0, 10**12 - 1, 10**12, 1, 1, 1, 1)))
    assert certify_constant(huge, (0,), 10**12)['first_failure'] == [10**12 - 1, 1]
    rows = []
    samples = []
    for n in (8, 64):
        for m in (1, 4):
            for length in (64, 4096, 65536):
                period = 16
                column = tuple(range(m))
                calendar = tuple(tuple((t * m + j) % n for j in range(m)) for t in range(period))
                tenants = tuple(Tenant(length + 1 if i < m else 1, length, 2 * length + 2, 1, 1, 1, 1) for i in range(n))
                snap = Snapshot(calendar, 3, tenants)
                # Expansion belongs to the explicit-column comparator. Both
                # timers include their own validation and witness decisions.
                for mode in ('explicit', 'run-length'):
                    result = certify_plan(snap, (column,) * length) if mode == 'explicit' else certify_constant(snap, column, length)
                    assert result['safe']
                paired = []
                for pair in range(9):
                    values = {}
                    for mode in (('explicit', 'run-length') if pair % 2 == 0 else ('run-length', 'explicit')):
                        repeats = 32 if length == 64 else 4 if length == 4096 else 1
                        start = time.perf_counter_ns()
                        for _ in range(repeats):
                            result = certify_plan(snap, (column,) * length) if mode == 'explicit' else certify_constant(snap, column, length)
                        elapsed = time.perf_counter_ns() - start
                        assert result['safe']
                        values[mode] = elapsed
                        samples.append({'tenants': n, 'cores': m, 'period': period, 'length': length,
                                        'pair': pair, 'mode': mode, 'elapsed_ns': elapsed, 'repeats': repeats})
                    paired.append(values['explicit'] / max(1, values['run-length']))
                rows.append({'tenants': n, 'cores': m, 'period': period, 'length': length,
                             'median_paired_explicit_over_run_length': statistics.median(paired)})
    env = {'python': sys.version, 'platform': platform.platform(), 'processor': platform.processor(),
           'timer': 'perf_counter_ns', 'pairs': 9, 'affinity_mask': 1, 'seed': 360071}
    (output / 'summary.json').write_text(json.dumps({'agreement_cases': checks, 'large_integer_case': True,
                                                   'rows': rows, 'environment': env}, indent=2) + '\n')
    (output / 'samples.json').write_text(json.dumps(samples, indent=2) + '\n')
    print(json.dumps({'agreement_cases': checks, 'rows': rows}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
