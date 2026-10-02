"""Independent finite oracles and explicit certificate checking for multicore plans.

This module does not import the producer, its model, or its transition functions.
It implements arrival-before-service transitions directly from serialized inputs.
"""
from __future__ import annotations
import itertools
from typing import Any


def validate_input(state: dict[str, Any], plan: list | tuple) -> None:
    if type(state) is not dict or set(state) != {'calendar', 'phase', 'tenants'}:
        raise ValueError('invalid snapshot object')
    tenants, calendar = state['tenants'], state['calendar']
    if not tenants or not calendar or not calendar[0] or not plan:
        raise ValueError('empty input')
    m, n = len(calendar[0]), len(tenants)
    if type(state['phase']) is not int or not 0 <= state['phase'] < len(calendar):
        raise ValueError('invalid phase')
    fields = {'backlog','lead','capacity','tokens','bucket','period','refill'}
    for t in tenants:
        if type(t) is not dict or set(t) != fields or any(type(v) is not int for v in t.values()):
            raise ValueError('invalid tenant structure')
        if (min(t['backlog'],t['lead'],t['tokens']) < 0 or
                min(t['capacity'],t['bucket'],t['period'],t['refill']) < 1 or
                t['backlog']+t['lead'] > t['capacity'] or
                t['tokens'] > t['bucket'] or t['refill'] > t['period']):
            raise ValueError('invalid tenant bounds')
    # Validate the two serialized roles explicitly.  Object identity is not a role:
    # callers may intentionally pass the very same list object as both calendar
    # and plan.  Only plan service is charged against current actual backlog.
    for col in calendar:
        if len(col) != m or any(type(i) is not int or not -1 <= i < n for i in col):
            raise ValueError('invalid calendar column')
        nonidle = [i for i in col if i >= 0]
        if len(nonidle) != len(set(nonidle)):
            raise ValueError('duplicate tenant')

    use = [0] * n
    for col in plan:
        if len(col) != m or any(type(i) is not int or not -2 <= i < n for i in col):
            raise ValueError('invalid plan column')
        nonidle = [i for i in col if i >= 0]
        if len(nonidle) != len(set(nonidle)):
            raise ValueError('duplicate tenant')
        for i in nonidle:
            use[i] += 1
    if any(v > t['backlog'] for v,t in zip(use,tenants)):
        raise ValueError('future work in plan')


def full_oracle(state: dict[str, Any], plan: list | tuple) -> tuple[tuple[int,int] | None,int]:
    """All arrival amounts, per-tenant DP. Return exact earliest violation."""
    failures, transitions = [], 0
    for i, t in enumerate(state['tenants']):
        frontier = {(t['backlog']+t['lead'],t['tokens'],0)}
        actual = 0
        for s, col in enumerate(plan):
            actual += int(i in col)
            next_states = set()
            failure = False
            for q,x,done in frontier:
                if s:
                    if s >= t['refill'] and (s-t['refill']) % t['period'] == 0:
                        x = min(t['bucket'],x+1)
                    possible = range(min(x,t['capacity']-q)+1)
                else:
                    possible = (0,)
                for a in possible:
                    transitions += 1
                    q2,x2,d2 = q+a,x-a,done
                    if i in state['calendar'][(state['phase']+s)%len(state['calendar'])] and q2:
                        q2 -= 1; d2 += 1
                    if d2 > t['lead']+actual:
                        failure = True
                    else:
                        next_states.add((q2,x2,d2))
            if failure:
                failures.append((s,i))
                break
            frontier = next_states
    return min(failures) if failures else None, transitions


def reduced_oracle(state: dict[str, Any], plan: list | tuple) -> tuple[int,int] | None:
    """Explicit zero/one release replay. Uses the single-arrival reduction theorem."""
    failures = []
    for i,t in enumerate(state['tenants']):
        for release in [None,*range(1,len(plan))]:
            q,x,r,a = t['backlog']+t['lead'],t['tokens'],0,0
            failure = None
            legal = True
            for s,col in enumerate(plan):
                if s and s >= t['refill'] and (s-t['refill'])%t['period']==0:
                    x=min(t['bucket'],x+1)
                if release == s:
                    if x==0 or q==t['capacity']:
                        legal=False;break
                    q+=1;x-=1
                if i in state['calendar'][(state['phase']+s)%len(state['calendar'])] and q:
                    q-=1;r+=1
                a+=int(i in col)
                if r>t['lead']+a and failure is None:
                    failure=(s,i)
            if legal and failure is not None:
                failures.append(failure)
    return min(failures) if failures else None


def joint_oracle(state: dict[str, Any], plan: list | tuple) -> tuple[int,int] | None:
    """All JOINT arrival vectors. Only used for very small cross-checks."""
    ts=state['tenants'];n=len(ts)
    frontier={(tuple(t['backlog']+t['lead'] for t in ts),tuple(t['tokens'] for t in ts),(0,)*n)}
    actual=[0]*n
    for s,col in enumerate(plan):
        for i in col:
            if i>=0:actual[i]+=1
        nxt=set();bad=[]
        for q0,x0,d0 in frontier:
            x=list(x0)
            if s:
                for i,t in enumerate(ts):
                    if s>=t['refill'] and (s-t['refill'])%t['period']==0:
                        x[i]=min(t['bucket'],x[i]+1)
                choices=[range(min(x[i],t['capacity']-q0[i])+1) for i,t in enumerate(ts)]
            else:choices=[(0,)]*n
            for arr in itertools.product(*choices):
                q=[u+a for u,a in zip(q0,arr)]
                xx=[u-a for u,a in zip(x,arr)]
                d=list(d0)
                for i in state['calendar'][(state['phase']+s)%len(state['calendar'])]:
                    if i>=0 and q[i]:q[i]-=1;d[i]+=1
                violations=[i for i in range(n) if d[i]>ts[i]['lead']+actual[i]]
                if violations:bad.extend((s,i) for i in violations)
                else:nxt.add((tuple(q),tuple(xx),tuple(d)))
        if bad:return min(bad)
        frontier=nxt
    return None


def check_certificate(state: dict[str, Any], plan: list | tuple, cert: dict[str, Any]) -> bool:
    """Reject malformed inputs, wrong verdicts, altered offsets and illegal witnesses."""
    try:
        validate_input(state,plan)
        if type(cert) is not dict or set(cert)!={'safe','first_failure','witness'} or type(cert['safe']) is not bool:
            return False
        expected=reduced_oracle(state,plan)
        if cert['safe'] != (expected is None):return False
        if expected is None:
            return cert['first_failure'] is None and cert['witness'] is None
        first = cert['first_failure']
        if (type(first) is not list or len(first) != 2 or
                any(type(v) is not int for v in first) or first != list(expected)):
            return False
        w=cert['witness']
        if type(w) is not dict or set(w)!={'kind','arrivals'} or w['kind'] not in ('queued','future'):
            return False
        arrivals=w['arrivals'];s_bad,i_bad=expected
        if type(arrivals) is not list or len(arrivals)>1:return False
        if w['kind']=='queued' and arrivals:return False
        if w['kind']=='future' and len(arrivals)!=1:return False
        if arrivals:
            row=arrivals[0]
            if (type(row) is not list or len(row)!=3 or any(type(v) is not int for v in row) or
                    not 1<=row[0]<=s_bad or row[1:]!=[i_bad,1]):return False
        # Direct joint replay of the supplied sparse input path.
        ts=state['tenants'];q=[t['backlog']+t['lead'] for t in ts]
        x=[t['tokens'] for t in ts];r=[0]*len(ts);a=[0]*len(ts)
        for s,col in enumerate(plan):
            if s:
                for i,t in enumerate(ts):
                    if s>=t['refill'] and (s-t['refill'])%t['period']==0:
                        x[i]=min(t['bucket'],x[i]+1)
            if arrivals and arrivals[0][0]==s:
                if not x[i_bad] or q[i_bad]>=ts[i_bad]['capacity']:return False
                q[i_bad]+=1;x[i_bad]-=1
            for i in state['calendar'][(state['phase']+s)%len(state['calendar'])]:
                if i>=0 and q[i]:q[i]-=1;r[i]+=1
            for i in col:
                if i>=0:a[i]+=1
            bad=[i for i in range(len(ts)) if r[i]>ts[i]['lead']+a[i]]
            if bad:return (s,min(bad))==expected
        return False
    except (TypeError,ValueError,KeyError,IndexError):
        return False
