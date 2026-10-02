"""Benign contract tests and metamorphic checks; no external target or service."""
import copy
import itertools
import json
import random
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from admission import Tenant, State, certify
from commitment import Snapshot, certify_plan
from plan_oracle import check_certificate, full_oracle, reduced_oracle, joint_oracle, validate_input
from atomic import certify_atomic, choose_atomic
from atomic_oracle import check_atomic_witness, capacity_oracle, game
from oracle import replay_witness


def state_for(calendar, plan, tails=None, leads=None, tokens=None, period=3, refill=2):
    n=max([i for col in (*calendar,*plan) for i in col]+[1])+1
    tails=[0]*n if tails is None else tails
    leads=[0]*n if leads is None else leads
    tokens=[1]*n if tokens is None else tokens
    used=[sum(i in col for col in plan) for i in range(n)]
    ts=tuple(Tenant(used[i]+tails[i],leads[i],max(1,used[i]+tails[i]+leads[i]),
                    tokens[i],max(1,tokens[i]),period,refill) for i in range(n))
    return Snapshot(tuple(calendar),0,ts)


class SingleCoreReplayTests(unittest.TestCase):
    def test_replay_rejects_boolean_violation_offset(self):
        # The valid failure is at integer offset 1.  Python's True == 1 must not
        # let a boolean-mutated certificate pass.
        state = State((0, 1), 0, (
            Tenant(2, 0, 2, 0, 1, 3, 3),
            Tenant(0, 0, 1, 1, 1, 3, 2),
        ))
        cert = certify(state, borrower=0, length=2)
        self.assertEqual(cert['witness']['violation_offset'], 1)
        self.assertTrue(replay_witness(state.to_dict(), cert))
        mutations = []
        for path, value in (
                (('witness', 'violation_offset'), True),
                (('witness', 'violation_offset'), -1),
                (('witness', 'tenant'), True),
                (('borrower',), True),
                (('length',), True),
                (('safe',), 0),
                (('witness', 'arrivals'), [[True, 1, 1]])):
            mutated = copy.deepcopy(cert)
            target = mutated
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append(mutated)
        for mutated in mutations:
            with self.subTest(mutated=mutated):
                self.assertFalse(replay_witness(state.to_dict(), mutated))

    def test_replay_rejects_illegal_event_after_first_failure(self):
        # The queued tenant already fails at offset 0.  An offset-1 arrival has
        # no token and is outside the witness prefix; an early return used to
        # hide that malformed suffix.
        state = State((1,), 0, (
            Tenant(2, 0, 2, 0, 1, 4, 4),
            Tenant(1, 0, 1, 0, 1, 4, 4),
        ))
        cert = certify(state, borrower=0, length=2)
        self.assertEqual(cert['witness']['violation_offset'], 0)
        self.assertTrue(replay_witness(state.to_dict(), cert))
        mutated = copy.deepcopy(cert)
        mutated['witness']['arrivals'] = [[1, 1, 1]]
        self.assertFalse(replay_witness(state.to_dict(), mutated))


class IndependentPlanInputTests(unittest.TestCase):
    def test_calendar_plan_alias_is_role_stable(self):
        state = {
            'calendar': [[0]],
            'phase': 0,
            'tenants': [{
                'backlog': 1, 'lead': 0, 'capacity': 1, 'tokens': 0,
                'bucket': 1, 'period': 1, 'refill': 1,
            }],
        }
        alias = state['calendar']
        copied = copy.deepcopy(alias)
        equal_tuple = ((0,),)
        safe = {'safe': True, 'first_failure': None, 'witness': None}
        for plan in (alias, copied, equal_tuple):
            with self.subTest(plan_type=type(plan).__name__, alias=plan is alias):
                validate_input(state, plan)
                self.assertTrue(check_certificate(state, plan, safe))
        with self.assertRaises(ValueError):
            validate_input(state, [[0], [0]])
        self.assertFalse(check_certificate(state, [[0], [0]], safe))


class FixedCommitmentTests(unittest.TestCase):
    def verify(self,s,p):
        c=certify_plan(s,p);d=s.to_dict();truth,_=full_oracle(d,p)
        self.assertEqual(c['first_failure'],list(truth) if truth is not None else None)
        self.assertEqual(truth,reduced_oracle(d,p))
        self.assertTrue(check_certificate(d,p,c))
        return c

    def test_future_arrival_and_quiet_countercontrol(self):
        fixtures=json.loads((Path(__file__).resolve().parents[1]/'inputs/neutral-cases.json').read_text())
        for item in fixtures['cases'][:3]:
            with self.subTest(neutral_case=item['id']):
                snap=Snapshot.from_dict(item['snapshot'])
                plan=tuple(tuple(col) for col in item['plan'])
                self.assertEqual(self.verify(snap,plan)['safe'],item['expected_safe'])
        p=((0,),(0,));s=state_for(((0,),(1,)),p)
        c=self.verify(s,p)
        self.assertFalse(c['safe']);self.assertEqual(c['first_failure'],[1,1])
        self.assertEqual(c['witness']['arrivals'],[[1,1,1]])
        ts=list(s.tenants);t=ts[1]
        ts[1]=Tenant(t.backlog,t.lead,t.capacity,0,1,3,3)
        self.assertTrue(self.verify(Snapshot(s.calendar,0,tuple(ts)),p)['safe'])

    def test_full_shadow_buffer_then_one_arrival(self):
        p=((0,),(0,),(0,));s=state_for(((1,),),p,leads=[0,1])
        c=self.verify(s,p)
        self.assertEqual(c['first_failure'],[1,1])
        self.assertEqual(c['witness']['arrivals'],[[1,1,1]])

    def test_queued_witness_needs_no_arrival(self):
        p=((0,),);s=state_for(((1,),),p,tails=[0,1])
        c=self.verify(s,p)
        self.assertEqual(c['first_failure'],[0,1]);self.assertEqual(c['witness']['arrivals'],[])

    def test_service_lead_is_not_transferable(self):
        p=((0,),);s=state_for(((1,),),p,tails=[0,1],leads=[5,0])
        self.assertFalse(self.verify(s,p)['safe'])

    def test_overhead_is_charged_not_productive(self):
        p=((-2,),);s=state_for(((1,),),p,tails=[0,1])
        self.assertFalse(self.verify(s,p)['safe'])

    def test_empty_reference_is_safe_not_work_conservation(self):
        p=((-1,),(-1,));s=state_for(((-1,),),p,tails=[2,0])
        self.assertTrue(self.verify(s,p)['safe'])

    def test_invalid_states_and_plans(self):
        p=((0,),);s=state_for(((1,),),p)
        bad=[]
        for key,value in (('tokens',True),('lead',-1),('refill',0),('capacity',0),('period',0)):
            d=s.to_dict();d['tenants'][1][key]=value;bad.append(d)
        d=s.to_dict();d['phase']=True;bad.append(d)
        d=s.to_dict();d['calendar']=[[99]];bad.append(d)
        for d in bad:
            with self.assertRaises((ValueError,TypeError)):Snapshot.from_dict(d)
            self.assertFalse(check_certificate(d,p,{'safe':True,'first_failure':None,'witness':None}))
        for plan in (((0,),(0,)),((True,),),((-3,),)):
            with self.assertRaises((ValueError,TypeError)):certify_plan(s,plan)
        two=state_for(((0,1),),((0,1),))
        with self.assertRaises(ValueError):certify_plan(two,((0,0),))

    def test_certificate_mutations(self):
        p=((0,),(0,));s=state_for(((0,),(1,)),p);c=certify_plan(s,p)
        mutations=[]
        def change(path,value):
            d=copy.deepcopy(c);o=d
            for k in path[:-1]:o=o[k]
            o[path[-1]]=value;mutations.append(d)
        change(['safe'],True);change(['safe'],0);change(['first_failure'],[0,1])
        change(['first_failure'],[True,True]);change(['first_failure'],(1,1))
        change(['witness','arrivals'],[[0,1,1]]);change(['witness','arrivals'],[[1,1,2]])
        change(['witness','arrivals'],[[1,0,1]]);change(['witness','arrivals'],[])
        change(['witness','kind'],'queued');change(['witness','arrivals'],[[True,1,1]])
        d=copy.deepcopy(c);d['extra']='not permitted';mutations.append(d)
        for d in mutations:self.assertFalse(check_certificate(s.to_dict(),p,d),d)

    def test_seeded_general_plans_and_metamorphisms(self):
        # Fixed before this test is executed. Not an independent held-out workload.
        rng=random.Random(731203)
        for case in range(300):
            n=rng.randint(2,5);m=rng.randint(1,min(3,n));P=rng.randint(1,5);L=rng.randint(1,6)
            def column(overhead=False):
                owners=rng.sample(range(n),rng.randint(0,m))
                return tuple(owners+[rng.choice((-2,-1)) if overhead else -1]*(m-len(owners)))
            cal=tuple(column() for _ in range(P));p=tuple(column(True) for _ in range(L))
            q=[sum(i in col for col in p)+rng.randint(0,2) for i in range(n)]
            ell=[rng.randint(0,2) for _ in range(n)]
            ts=[]
            for i in range(n):
                b=rng.randint(1,3);T=rng.randint(1,4)
                ts.append(Tenant(q[i],ell[i],max(1,q[i]+ell[i]+rng.randint(0,2)),rng.randint(0,b),b,T,rng.randint(1,T)))
            s=Snapshot(cal,rng.randrange(P),tuple(ts));c=self.verify(s,p)
            perm=list(range(n));rng.shuffle(perm);inverse=[perm.index(i) for i in range(n)]
            mp=lambda col:tuple(perm[i] if i>=0 else i for i in col)
            ss=Snapshot(tuple(map(mp,cal)),s.phase,tuple(s.tenants[inverse[i]] for i in range(n)))
            cp=self.verify(ss,tuple(map(mp,p)))
            self.assertEqual(c['safe'],cp['safe'])
            if not c['safe']:self.assertEqual(c['first_failure'][0],cp['first_failure'][0])
            # Core permutation and calendar rotation preserve every opportunity set.
            sr=Snapshot(tuple(tuple(reversed(col)) for col in cal),s.phase,s.tenants)
            self.assertEqual(c,certify_plan(sr,tuple(tuple(reversed(col)) for col in p)))
            rotated=cal[s.phase:]+cal[:s.phase]
            self.assertEqual(c,certify_plan(Snapshot(rotated,0,s.tenants),p))
            if case<20:self.assertEqual(joint_oracle(s.to_dict(),p),full_oracle(s.to_dict(),p)[0])


class AtomicTests(unittest.TestCase):
    def test_empty_calendar_and_unit_handlers(self):
        self.assertTrue(certify_atomic(((-1,),),(2,2),(2,2),(2,2))['safe'])
        self.assertTrue(certify_atomic(((0,),(1,)),(1,1),(2,2),(2,2))['safe'])
        self.assertTrue(certify_atomic(((0,),(1,)),(2,2),(1,1),(2,2))['safe'])
        self.assertTrue(certify_atomic(((0,),(1,)),(2,2),(2,2),(1,1))['safe'])

    def test_two_slot_obstruction(self):
        cal=((0,1),);costs=(1,1,2);bs=(2,2,2)
        c=certify_atomic(cal,costs,bs,bs)
        self.assertFalse(c['safe']);self.assertTrue(check_atomic_witness(cal,costs,bs,bs,c))
        self.assertEqual(c['witness']['blockers'],[2]);self.assertEqual(c['witness']['urgent'],[0,1])
        self.assertFalse(game(cal,costs,2,2,2)['safe'])

    def test_rotating_reference_and_partial_columns(self):
        cases=[(((0,1),(1,2)),(2,2,2),False),
               (((0,-1),(1,-1)),(2,2,1),True),
               (((0,-1),(2,-1)),(2,2,1),False)]
        for cal,costs,expected in cases:
            b=(2,)*3;c=certify_atomic(cal,costs,b,b)
            self.assertEqual(c['safe'],expected)
            self.assertEqual(c['safe'],capacity_oracle(cal,costs,b,b)[0])

    def test_validate_entire_calendar_before_early_rejection(self):
        with self.assertRaises(ValueError):
            certify_atomic(((0,), (True,)),(2,2),(2,2),(2,2))

    def test_atomic_certificate_mutations(self):
        cal=((0,),);c=certify_atomic(cal,(2,2),(2,2),(2,2))
        mutations=[]
        for key,value in (('safe',0),('safe',True),('failure_phase',False),('long_tenants',[0,True])):
            d=copy.deepcopy(c);d[key]=value;mutations.append(d)
        for key,value in (('start_phase',False),('compelled_at_failure',1),('blockers',[0]),
                          ('urgent',[1]),('arrivals',[[0,1,1],[1,0,1]])):
            d=copy.deepcopy(c);d['witness'][key]=value;mutations.append(d)
        for d in mutations:self.assertFalse(check_atomic_witness(cal,(2,2),(2,2),(2,2),d))

    def test_policy_prioritizes_urgent_owner_then_fills(self):
        self.assertEqual(choose_atomic([[1],[2],[1]],[False,True,False],[1,2,3],(0,-1),2),[0,1])
        with self.assertRaises(RuntimeError):
            choose_atomic([[1],[1],[1]],[False,False,True],[1,1,1],(0,1),2)


if __name__=='__main__':unittest.main(verbosity=2)
