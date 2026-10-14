"""Owned, deliberately inconsistent oracle stubs: never scientific measurements.

Run the real campaign entry points on a one-column menu under both interpreters.
These tests require rejection before a result is written, even with Python -O.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import itertools, sys, types
from pathlib import Path
# Windows has no resource module. This stub is ONLY an owned gate-test fixture;
# it does not run or certify a bounded/memory-measured experiment.
sys.modules['resource'] = types.SimpleNamespace(
    RLIMIT_AS=0, RLIMIT_CPU=1, RUSAGE_SELF=0,
    setrlimit=lambda *a: None, getrusage=lambda *a: types.SimpleNamespace(ru_maxrss=0))
sys.path.insert(0, str(Path(sys.argv[1]) / 'src'))
import os
os.sched_getaffinity = lambda *a: {0}
os.sched_setaffinity = lambda *a: None
module = __import__(sys.argv[2])
module.configure = lambda **kw: None
original_product = itertools.product
module.itertools = types.SimpleNamespace(product=lambda *a, **kw: iter([next(original_product(*a, **kw))]))
if sys.argv[2] == 'plan_pilot':
    module.certify_plan = lambda *a: {'safe': True, 'first_failure': [0, 0], 'witness': None}
    module.full_oracle = lambda *a: (None, 0)
    module.reduced_oracle = lambda *a: None
    module.check_certificate = lambda *a: False
    module.joint_oracle = lambda *a: None
else:
    module.certify_atomic = lambda *a: {'safe': True}
    module.game = lambda *a: {'safe': False, 'states': 1, 'schedule_edges': 1}
    module.capacity_oracle = lambda *a: (False, 1)
sys.argv = [sys.argv[2], '--output-dir', sys.argv[3]]
module.main()
'''


class EvidenceGates(unittest.TestCase):
    def check_gate(self, module):
        import tempfile
        # Tests do not touch retained result files. The enclosing runner owns
        # TMP/TEMP and records this output; scientific campaigns use fresh paths.
        with tempfile.TemporaryDirectory(prefix='owned-gate-') as folder:
            for optimized in (False, True):
                command = [sys.executable, '-B'] + (['-O'] if optimized else [])
                command += ['-c', SCRIPT, str(ROOT), module, folder]
                result = subprocess.run(command, text=True, capture_output=True,
                                        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=10)
                with self.subTest(module=module, optimized=optimized):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn('AssertionError', result.stderr)
                    self.assertFalse(list(Path(folder).glob('*.json')))

    def test_plan_oracle_disagreement_cannot_publish(self):
        self.check_gate('plan_pilot')

    def test_atomic_oracle_disagreement_cannot_publish(self):
        self.check_gate('atomic_pilot')


if __name__ == '__main__':
    unittest.main(verbosity=2)
