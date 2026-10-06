"""Owned in-memory protocol regressions; no files or external programs needed."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from runtime import execute
from runtime_replay import replay
import runtime_summary


def records(actual_horizon=2, actual_layout=(2, 1), mutations=6, survivors=0):
    """A small complete protocol, with optional self-consistent wrong inputs."""
    protocol = dict(families=['toy'], layouts=[[2, 1]], evaluation_seeds=[101],
                    horizon=2, batch_lengths=[1], main_batch_length=1,
                    policies=['reservation', 'urgent', 'naive', 'snapshot',
                              'certified', 'certified-interrupt'])
    n, m = actual_layout
    config = dict(calendar=[list(range(m))], phase=0,
                  tenants=[dict(capacity=2, bucket=2, tokens=2, period=1, refill=1)
                           for _ in range(n)], offers=[[0]*n for _ in range(actual_horizon)])
    trace_id = 'toy-n2-m1-s101'
    rows, logs = [], []
    for policy in protocol['policies']:
        log = execute(config, policy, 1)
        rows.append(dict(trace_id=trace_id, family='toy', tenants=2, cores=1,
                         seed=101, policy=policy, batch=1,
                         metrics=replay(config, log), control=log['control']))
        logs.append(dict(trace_id=trace_id, log=log))
    summary = dict(groups=runtime_summary.merge(rows), trace_count=1, run_count=6,
                   domain='evaluation', mutations=mutations, mutation_survivors=survivors,
                   paired_admissions=True)
    files = {'runtime-protocol.json': json.dumps(protocol),
             'inputs.jsonl': json.dumps(dict(trace_id=trace_id, config=config)),
             'runs.jsonl': '\n'.join(map(json.dumps, rows)),
             'summary.json': json.dumps(summary)}
    return files, '\n'.join(map(json.dumps, logs))


def summarize_fixture(files, logs):
    # Only I/O is mocked. The actual grid validator and independent replayer run.
    with patch.object(Path, 'read_text', lambda path, **kw: files[path.name]), \
         patch.object(runtime_summary.gzip, 'open', lambda *a, **kw: io.StringIO(logs)):
        return runtime_summary.summarize(Path('owned-memory-fixture'), replay_all=True)


class RuntimeGridContracts(unittest.TestCase):
    def test_complete_small_grid_is_replayed(self):
        result, count = summarize_fixture(*records())
        self.assertEqual((result['traces'], result['runs'], count), (1, 6, 6))
        self.assertEqual(result['executed_slots'], 12)
        self.assertEqual(result['mutations'], 6)
        # A reported zero-survivor count cannot stand in for actually rejected
        # variants: six unchanged legal histories must expose the discrepancy.
        with patch.object(runtime_summary, 'malformed_logs', lambda log, n: iter([log]*6)):
            with self.assertRaises(ValueError):
                summarize_fixture(*records())

    def test_self_consistent_short_horizon_rejected(self):
        with self.assertRaises(ValueError):
            summarize_fixture(*records(actual_horizon=1))

    def test_self_consistent_wrong_resource_dimensions_rejected(self):
        for layout in ((3, 1), (2, 2)):
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                summarize_fixture(*records(actual_layout=layout))

    def test_missing_mutation_attempts_rejected(self):
        for count in (0, 5, True):
            with self.subTest(count=count), self.assertRaises(ValueError):
                summarize_fixture(*records(mutations=count))

    def test_invalid_mutation_survivor_counts_rejected(self):
        for count in (-1, True, 7):
            with self.subTest(count=count), self.assertRaises(ValueError):
                summarize_fixture(*records(survivors=count))


if __name__ == '__main__':
    unittest.main(verbosity=2)
