"""Small same-information comparator controls, not a generated cost campaign."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow_cost import workflow, paired_check


class WorkflowCostTests(unittest.TestCase):
    def fixture(self):
        return {'calendar':[[0],[1]],'phase':0,
                'tenants':[dict(capacity=3,bucket=3,tokens=3,period=3,refill=2) for _ in range(2)],
                'offers':[[2,0],[0,2],[0,0],[0,0]]}

    def test_real_paths_and_pairing(self):
        config=self.fixture();before=copy.deepcopy(config)
        results={p:workflow(config,p) for p in ('urgent','certified-interrupt')}
        self.assertEqual(paired_check(config,results),0)
        self.assertEqual(config,before)
        for p in results:self.assertEqual(results[p][2],workflow(config,p)[2])

    def test_different_information_rejected(self):
        config=self.fixture()
        results={p:workflow(config,p) for p in ('urgent','certified-interrupt')}
        results['certified-interrupt'][0]['events'][0]['admitted'][0]+=1
        with self.assertRaises(AssertionError):paired_check(config,results)


if __name__=='__main__':unittest.main(verbosity=2)
