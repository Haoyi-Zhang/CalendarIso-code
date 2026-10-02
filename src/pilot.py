"""One-worker, exhaustive pilot with negative controls and measured bounds."""
from __future__ import annotations
import itertools, json, os, resource, time
from pathlib import Path
from admission import State, Tenant, certify
from oracle import exhaustive, one_arrival_check, replay_witness


def run() -> dict:
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (35, 40))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    start, cpu = time.perf_counter(), time.process_time()
    count = safe = denied = edges = mutations = 0
    saved = []
    for p in range(1, 4):
        for cal in itertools.product((-1, 0, 1), repeat=p):
            for q, lead, x in itertools.product(range(3), repeat=3):
                for period in range(1, 4):
                    for refill in range(1, period + 1):
                        for length in range(1, 6):
                            state = State(cal, 0, (Tenant(length, 0, 8, 0, 2, 3, 3),
                                      Tenant(q, lead, max(1, q + lead), x, 2, period, refill)))
                            cert = certify(state, 0, length)
                            payload = state.to_dict()
                            truth, explored = exhaustive(payload, 0, length)
                            alt, when = one_arrival_check(payload, 0, length)
                            count += 1; edges += explored
                            if cert['safe'] != truth or alt != truth:
                                raise AssertionError((payload, cert, truth, alt))
                            if truth:
                                safe += 1
                            else:
                                denied += 1
                                if not replay_witness(payload, cert):
                                    raise AssertionError(('bad witness', payload, cert))
                                if when != cert['witness']['violation_offset']:
                                    raise AssertionError('not earliest witness')
                            if len(saved) < 8 and not truth and cert['witness']['arrivals']:
                                saved.append({'state': payload, 'certificate': cert})
    # Null lead/current-empty negative control: queued k blocks a future i arrival.
    state = State((0, 1), 0, (Tenant(2, 0, 4, 0, 1, 4, 4), Tenant(0, 0, 2, 1, 1, 4, 4)))
    cert = certify(state, 0, 2)
    assert not cert['safe'] and not exhaustive(state.to_dict(), 0, 2)[0]
    # Counterexample to counting all slots as demanded: no new token until offset 3.
    quiet = State((0, 1), 0, (Tenant(2, 0, 4, 0, 1, 4, 4), Tenant(0, 0, 2, 0, 1, 4, 3)))
    assert certify(quiet, 0, 2)['safe']
    # Full shadow buffer cannot disable the one-arrival witness permanently.
    full = State((1, 1, 1), 0, (Tenant(3, 0, 4, 0, 1, 4, 4), Tenant(0, 1, 1, 1, 1, 4, 4)))
    cf = certify(full, 0, 3)
    assert not cf['safe'] and cf['witness']['arrivals'] == [[1, 1, 1]]
    return {'cases': count, 'safe': safe, 'denied': denied, 'oracle_transitions': edges,
            'disagreements': 0, 'witness_failures': 0,
            'negative_controls': {'ignore_future_arrivals': 'refuted', 'count_all_slots': 'overconservative',
                                  'full_buffer_hides_violation': 'refuted'},
            'limits': {'calendar_lengths': [1, 2, 3], 'calendar_alphabet': [-1,0,1],
                       'other_backlog': [0,1,2], 'other_lead': [0,1,2], 'residual_tokens': [0,1,2],
                       'refill_periods': [1,2,3], 'all_refill_phases': True, 'batch_lengths': [1,2,3,4,5],
                       'other_capacity': 'max(1,backlog+lead)', 'workers': 1, 'randomness': 'none'},
            'cpu_seconds': time.process_time()-cpu, 'wall_seconds': time.perf_counter()-start,
            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'examples': saved}

if __name__ == '__main__':
    result = run()
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1]/'results')
    args=ap.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    out = args.output_dir/'pilot.json'
    out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'examples'}, indent=2))
