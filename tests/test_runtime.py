#!/usr/bin/env python3
"""Small composition/negative-control regressions; no workload tuning."""
import ast
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from runtime import execute, propose
from runtime_replay import replay


def config(offers, calendar=None):
    n = len(offers[0])
    return {'calendar': calendar or [[i] for i in range(n)], 'phase': 0,
            'tenants': [dict(capacity=8, bucket=8, tokens=8, period=2, refill=1) for _ in range(n)],
            'offers': offers}


class RuntimeContracts(unittest.TestCase):
    def test_no_arrival_all_policies(self):
        c = config([[0,0]]*8)
        for p in ('reservation','urgent','naive','snapshot','certified','certified-interrupt'):
            m = replay(c, execute(c,p,4))
            self.assertEqual(m['actual_work'],0)
            self.assertEqual(m['prefix_violation_slots'],0)

    def test_late_arrival_isolation_and_idle_interrupt(self):
        c = config([[0],[1],[0],[0]], [[0]])
        safe = replay(c,execute(c,'certified',4))
        self.assertEqual(safe['prefix_violation_slots'],0)
        self.assertEqual(safe['actual_work'],1)
        urgent = replay(c,execute(c,'urgent',4))
        self.assertEqual(urgent['avoidable_idle_core_slots'],0)

    def test_safe_immutable_commitment_can_idle(self):
        # Tenant 1's next reference slot is late. Its new work can legally wait
        # in an immutable all-idle prefix even though an idle core is available.
        c=config([[0,0],[0,1],[0,0],[0,0]], [[0],[0],[0],[1]])
        c['tenants'][0].update(tokens=0, period=8, refill=8)
        fixed=replay(c,execute(c,'certified',4))
        interrupt=replay(c,execute(c,'certified-interrupt',4))
        self.assertEqual(fixed['prefix_violation_slots'],0)
        self.assertGreater(fixed['avoidable_idle_core_slots'],0)
        self.assertEqual(interrupt['avoidable_idle_core_slots'],0)
        self.assertEqual(interrupt['prefix_violation_slots'],0)

    def test_naive_and_snapshot_negative_controls(self):
        c=config([[0,0],[0,1],[0,0],[0,0]], [[0],[1]])
        for p in ('naive','snapshot'):
            self.assertGreater(replay(c,execute(c,p,4))['prefix_violation_slots'],0)
        for p in ('urgent','certified','certified-interrupt'):
            self.assertEqual(replay(c,execute(c,p,4))['prefix_violation_slots'],0)

    def test_refill_and_reference_gate_pairing(self):
        c=config([[8,8]]*16)
        c['tenants'][0].update(capacity=2,bucket=3, tokens=3,period=3,refill=2)
        logs=[execute(c,p,4) for p in ('reservation','urgent','naive','snapshot','certified','certified-interrupt')]
        expected=[e['admitted'] for e in logs[0]['events']]
        for log in logs:
            replay(c,log)
            self.assertEqual([e['admitted'] for e in log['events']],expected)

    def test_strict_boolean_fields(self):
        c=config([[1,1],[0,0]])
        for key in ('phase',):
            bad=copy.deepcopy(c);bad[key]=True
            with self.assertRaises(ValueError): execute(bad,'certified',2)
        log=execute(c,'urgent',2)
        for key in ('time','queue','lead','served','admitted','tokens'):
            bad=copy.deepcopy(log)
            if key=='time':bad['events'][0][key]=False
            else:bad['events'][0][key][0]=True
            with self.assertRaises(ValueError):replay(c,bad)
        with self.assertRaises(ValueError):execute(c,'urgent',True)

    def test_illegal_suffix_not_hidden_by_early_failure(self):
        c=config([[0,0],[0,1],[0,0],[0,0]], [[0],[1]])
        bad=execute(c,'naive',4)
        self.assertGreater(replay(c,bad)['prefix_violation_slots'],0)
        bad['events'][-1]['admitted'][0]=100
        with self.assertRaises(ValueError):replay(c,bad)

    def test_full_log_required(self):
        c=config([[1,1]]*4)
        log=execute(c,'urgent',2)
        log['events'].pop()
        with self.assertRaises(ValueError):replay(c,log)

    def test_shared_calendar_alias_not_modified(self):
        c=config([[2,1]]*4)
        before=copy.deepcopy(c)
        for p in ('certified','certified-interrupt'):
            execute(c,p,4)
            self.assertEqual(c,before)

    def test_proposals_do_not_rely_on_future(self):
        p=propose([1,2,0],2,4)
        self.assertLessEqual(sum(0 in c for c in p),1)
        self.assertLessEqual(sum(1 in c for c in p),2)
        self.assertEqual(sum(2 in c for c in p),0)
        self.assertTrue(all(len([i for i in c if i>=0])==len(set(i for i in c if i>=0)) for c in p))

    def test_exact_prefix_replanning_keeps_state(self):
        c=config([[2,0],[0,2],[1,0],[0,1],[3,0],[0,3]]*4)
        for p in ('urgent','certified','certified-interrupt'):
            log=execute(c,p,4)
            m=replay(c,log)
            self.assertEqual(m['prefix_violation_slots'],0)
            for e in log['events']:
                self.assertEqual([r-q for r,q in zip(e['reference_queue'],e['queue'])],e['lead'])

    def test_uniprocessor_and_multicore_work_conservation(self):
        for calendar in ([[0],[1],[2]], [[0,1],[2,-1]]):
            c=config([[2,3,1],[0,0,0],[1,0,2],[0,2,0]]*5,calendar)
            for p in ('urgent','certified-interrupt'):
                m=replay(c,execute(c,p,8))
                self.assertEqual(m['prefix_violation_slots'],0)
                self.assertEqual(m['avoidable_idle_core_slots'],0)

    def test_replayer_import_separation(self):
        path=Path(__file__).resolve().parents[1]/'src/runtime_replay.py'
        tree=ast.parse(path.read_text())
        imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        self.assertTrue(imports <= {'__future__','collections'})

    def test_bad_service_rejected(self):
        c=config([[1,1],[0,0]], [[0,1]])
        log=execute(c,'urgent',2)
        log['events'][0]['served']=[0,0]
        with self.assertRaises(ValueError):replay(c,log)

if __name__=='__main__':unittest.main(verbosity=2)
