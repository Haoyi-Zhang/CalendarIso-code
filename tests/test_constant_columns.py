import itertools
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from admission import Tenant
from commitment import Snapshot, certify_plan
from constant_columns import certify_constant


class ConstantColumnsTests(unittest.TestCase):
    def test_all_small_constant_runs(self):
        # Includes full buffers, unavailable tokens, phase rotation and idle runs.
        count = 0
        for owners in itertools.product((-1, 0, 1), repeat=2):
            for column in ((-1,), (0,), (1,)):
                for phase, length, lead, tokens, refill in itertools.product(range(2), (1, 2, 5), range(3), range(2), (1, 2)):
                    for tails in itertools.product(range(2), repeat=2):
                        q = [length if i in column else tails[i] for i in range(2)]
                        snap = Snapshot(tuple((i,) for i in owners), phase,
                                        tuple(Tenant(q[i], lead, max(1, q[i] + lead), tokens, 1, 2, refill) for i in range(2)))
                        self.assertEqual(certify_constant(snap, column, length), certify_plan(snap, (column,) * length))
                        count += 1
        self.assertEqual(count, 7776)

    def test_large_encoded_length(self):
        snap = Snapshot(((1,),), 0, (Tenant(10**12, 0, 10**12, 1, 1, 1, 1),
                                     Tenant(0, 10**12 - 1, 10**12, 1, 1, 1, 1)))
        self.assertEqual(certify_constant(snap, (0,), 10**12)['first_failure'], [10**12 - 1, 1])

    def test_backlog_and_columns(self):
        snap = Snapshot(((0, 1),), 0, (Tenant(3, 0, 3, 1, 1, 1, 1), Tenant(3, 0, 3, 1, 1, 1, 1)))
        self.assertTrue(certify_constant(snap, (1, 0), 3)['safe'])
        for column, length in (((0, 0), 1), ((0, 1), 4), ((0, 1), True), ((0, 1), 0)):
            with self.assertRaises(ValueError):
                certify_constant(snap, column, length)


if __name__ == '__main__':
    unittest.main()
