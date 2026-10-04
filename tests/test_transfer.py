"""Regression and boundary cases for the mathematical TS embedding.

No upstream code is imported. These tests do not claim Rocq proof checking.
"""
import copy
from dataclasses import replace
import itertools
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from commitment import Snapshot,certify_plan
from transfer_oracle import UnitTrace,certify_by_transfer,evaluate,tenant_traces,validate


def snapshot(q=0,lead=0,tokens=1,bucket=1,period=3,refill=3,Q=None,cal=((0,),),phase=0):
    return {'calendar':cal,'phase':phase,'tenants':[
        dict(backlog=q,lead=lead,capacity=max(1,q+lead) if Q is None else Q,
             tokens=tokens,bucket=bucket,period=period,refill=refill)]}


class TransferReductionTests(unittest.TestCase):
    def compare(self,s,p):
        exact=certify_by_transfer(s,p)
        prod=certify_plan(Snapshot.from_dict(s),tuple(tuple(x) for x in p))
        self.assertEqual(exact['safe'],prod['safe'])
        return exact

    def test_unseen_unit_is_not_a_fixed_arrival_exemption(self):
        s=snapshot(cal=((-1,),(0,)))
        result=self.compare(s,((-1,),(-1,)))
        self.assertFalse(result['safe'])
        self.assertGreater(result['unsafe_traces'],0)
        zero=next(t for t in tenant_traces(s,((-1,),(-1,)),0) if not any(t.arrivals))
        self.assertTrue(evaluate(zero)['criterion'])

    def test_initial_backlog_requires_no_future_arrival(self):
        self.assertFalse(self.compare(snapshot(q=1,tokens=0),((-1,),))['safe'])

    def test_nonzero_lead_uses_already_completed_unit_jobs(self):
        s=snapshot(lead=2,tokens=0,period=4,refill=4)
        result=self.compare(s,((-1,),)*3)
        self.assertTrue(result['safe'])
        trace=next(tenant_traces(s,((-1,),)*3,0))
        self.assertEqual(trace.online_cost,(0,0))
        self.assertTrue(evaluate(trace)['criterion'])
        worked = UnitTrace((0,0,3),(0,1,1),(0,None,1,2),(1,None,None,None),1,(0,0,0,1))
        self.assertFalse(evaluate(worked)['criterion'])
        self.assertEqual(evaluate(worked)['first_bad_interval'],[3,4])

    def test_completion_of_whole_handler_is_weaker_without_refinement(self):
        trace=UnitTrace((0,0),(1,1),(0,None,1),(None,0,1),0,(0,0,0))
        self.assertEqual(sum(x is not None for x in trace.reference),2)
        self.assertEqual(sum(x is not None for x in trace.actual),2)
        self.assertFalse(evaluate(trace)['criterion'])
        self.assertFalse(evaluate(trace)['prefix'])

    def test_multicore_core_permutation_changes_no_projection(self):
        s=snapshot(q=2,tokens=0,period=3,refill=3)
        s['tenants']*=2
        s['calendar']=((0,1),(1,0))
        p=((0,1),(1,0))
        result=self.compare(s,p)
        s2=copy.deepcopy(s);s2['calendar']=tuple(tuple(reversed(c)) for c in s['calendar'])
        p2=tuple(tuple(reversed(c)) for c in p)
        self.assertEqual(result,self.compare(s2,p2))

    def test_equal_abstraction_does_not_mean_equal_arrival_languages(self):
        a=snapshot(period=1,refill=1)
        b=snapshot(period=2,refill=1)
        p=((-1,),)*3
        aa={t.arrivals for t in tenant_traces(a,p,0)}
        bb={t.arrivals for t in tenant_traces(b,p,0)}
        self.assertIn((0,1,1),aa)
        self.assertNotIn((0,1,1),bb)
        self.assertEqual(self.compare(a,p)['safe'],self.compare(b,p)['safe'])

    def test_two_arrivals_needed_outside_current_backlog_plan_contract(self):
        s=snapshot(tokens=2,bucket=2,period=4,refill=4,Q=2)
        p=((-1,),)*3
        rejected_two=single=0
        for t in tenant_traces(s,p,0):
            actual=[None]*3
            if t.release:
                actual[t.release[0]]=0  # serve only the first ever arriving unit
            reactive=replace(t,actual=tuple(actual))
            result=evaluate(reactive)
            if sum(t.arrivals)<=1:
                single+=1
                self.assertTrue(result['criterion'])
            elif not result['criterion']:
                rejected_two+=1
        self.assertGreater(single,0)
        self.assertGreater(rejected_two,0)
        with self.assertRaises(ValueError):
            validate(s,((-1,),(0,),(-1,)))

    def test_full_reference_buffer_does_not_preclude_sparse_witness(self):
        s=snapshot(q=1,tokens=1,Q=1)
        p=((0,),(-1,))
        self.assertFalse(self.compare(s,p)['safe'])
        paths=list(tenant_traces(s,p,0))
        self.assertTrue(any(t.arrivals==(0,1) and not evaluate(t)['criterion'] for t in paths))

    def test_equal_and_aliased_calendar_plans(self):
        s=snapshot(q=1,tokens=0,cal=[[0]],period=1,refill=1)
        results=[self.compare(s,p) for p in (s['calendar'],copy.deepcopy(s['calendar']),((0,),))]
        self.assertEqual(results[0],results[1]);self.assertEqual(results[1],results[2])

    def test_parser_rejects_bool_and_true_overbacklog(self):
        s=snapshot(q=1,tokens=0)
        for field in ('backlog','lead','tokens','capacity','period','refill','bucket'):
            bad=copy.deepcopy(s);bad['tenants'][0][field]=True
            with self.subTest(field=field),self.assertRaises(ValueError):validate(bad,((0,),))
        with self.assertRaises(ValueError):validate(s,((0,),(0,)))
        with self.assertRaises(ValueError):validate(s,((True,),))

    def test_one_slot_urgent_set_is_exact(self):
        # Every feasible action set is checked, not just the selected policy.
        count=0
        for n,m in ((2,1),(3,2)):
            subsets=[set(v) for k in range(m+1) for v in itertools.combinations(range(n),k)]
            for owners in subsets:
                for q in itertools.product(range(2),repeat=n):
                    for lead in itertools.product(range(2),repeat=n):
                        ready={i for i in range(n) if q[i]}
                        urgent={i for i in owners if q[i] and lead[i]==0}
                        for action in subsets:
                            if not action<=ready:continue
                            ref={i for i in owners if q[i]+lead[i]>0}
                            safe=all(lead[i]+int(i in action)-int(i in ref)>=0 for i in range(n))
                            self.assertEqual(safe,urgent<=action)
                            count+=1
        self.assertGreater(count,1000)

    def test_trace_rejects_execution_of_completed_or_unreleased_units(self):
        for trace in (UnitTrace((0,),(1,),(0,0),(None,None),0,(0,0)),
                      UnitTrace((1,),(1,),(0,None),(None,None),0,(0,1)),
                      UnitTrace((0,),(0,),(0,None),(0,None),1,(0,0))):
            with self.subTest(trace=trace),self.assertRaises(ValueError):evaluate(trace)
        valid = UnitTrace((0,), (1,), (0,None), (0,None), 0, (0,0))
        for bad in (replace(valid, lead=False),
                    replace(valid, online_cost=(True,)),
                    replace(valid, release=(False,)),
                    replace(valid, arrivals=(False,0)),
                    replace(valid, lead=1),
                    replace(valid, arrivals=(0,1)),
                    UnitTrace((0,0),(1,1),(1,None),(None,None),0,(0,0))):
            with self.subTest(metadata=bad),self.assertRaises(ValueError):evaluate(bad)


if __name__=='__main__':unittest.main(verbosity=2)
