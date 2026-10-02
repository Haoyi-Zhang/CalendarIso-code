"""Independent finite alternating arrival/scheduler game for atomic handlers.

This module imports neither the static producer nor its state/transition functions.
For each arrival choice it existentially searches all work-conserving schedules.
"""
from __future__ import annotations
from functools import lru_cache
from itertools import product, combinations


def game(calendar, costs, bucket, capacity, horizon, phase=0, period=1):
    n=len(costs);m=len(calendar[0]);expanded=0;edges=0
    @lru_cache(None)
    def sequences(i,space):
        result=[()]
        for c in range(1,min(costs[i],space)+1):
            result.extend((c,)+tail for tail in sequences(i,space-c))
        return tuple(result)
    @lru_cache(None)
    def win(t,actual,ref,tokens,active):
        nonlocal expanded,edges
        expanded+=1
        if t==horizon:return True
        tok=tuple(min(bucket,x+int(t>0 and t%period==0)) for x in tokens)
        menus=[sequences(i,min(tok[i],capacity-ref[i])) for i in range(n)]
        for incoming in product(*menus):
            added=tuple(sum(a) for a in incoming)
            q=tuple(actual[i]+incoming[i] for i in range(n))
            rq=tuple(ref[i]+added[i] for i in range(n))
            tx=tuple(tok[i]-added[i] for i in range(n))
            forced={i for i in range(n) if active[i]}
            ready={i for i in range(n) if q[i]}
            fill=min(m,len(ready))-len(forced)
            response=False
            for extra in combinations(sorted(ready-forced),fill):
                chosen=forced|set(extra);edges+=1
                qq=list(q); rr=list(rq);aa=list(active)
                for i in chosen:
                    if qq[i][0]==1:
                        qq[i]=qq[i][1:];aa[i]=False
                    else:
                        qq[i]=(qq[i][0]-1,)+qq[i][1:];aa[i]=True
                for i in calendar[(phase+t)%len(calendar)]:
                    if i>=0 and rr[i]:rr[i]-=1
                if any(rr[i]<sum(qq[i]) for i in range(n)):continue
                if win(t+1,tuple(qq),tuple(rr),tx,tuple(aa)):
                    response=True;break
            if not response:return False
        return True
    verdict=win(0,((),)*n,(0,)*n,(bucket,)*n,(False,)*n)
    return {'safe':verdict,'states':expanded,'schedule_edges':edges}


def capacity_oracle(calendar,costs,buckets,capacities):
    n=len(costs);m=len(calendar[0]);L=[i for i in range(n) if min(costs[i],buckets[i],capacities[i])>=2]
    checks=0
    for col in calendar:
        R={i for i in col if i>=0}
        for k in range(min(m,len(L))+1):
            for running in combinations(L,k):
                checks+=1
                # Explicitly count already occupied cores and new urgent owners.
                if len(running)+sum(i not in running for i in R)>m:
                    return False,checks
    return True,checks


def check_atomic_witness(calendar,costs,buckets,capacities,cert):
    """Validate a two-slot capacity obstruction, without calling the producer.

    This is a bounded witness checker, not a proof checker for the universal
    theorem. The checked witness starts from empty queues and full token buckets.
    """
    try:
        n=len(costs)
        if not n or not calendar or not calendar[0] or len(buckets)!=n or len(capacities)!=n:
            return False
        if any(type(v) is not int or v<1 for row in (costs,buckets,capacities) for v in row):
            return False
        m=len(calendar[0])
        for col in calendar:
            if len(col)!=m or any(type(i) is not int or not -1<=i<n for i in col):return False
            owners=[i for i in col if i>=0]
            if len(owners)!=len(set(owners)):return False
        if (type(cert) is not dict or set(cert)!={'safe','long_tenants','failure_phase','witness'}
                or cert['safe'] is not False):return False
        p=cert['failure_phase']
        if type(p) is not int or not 0<=p<len(calendar):return False
        long=cert['long_tenants']
        if (type(long) is not list or any(type(i) is not int for i in long)
                or long != [i for i in range(n) if min(costs[i],buckets[i],capacities[i])>=2]):return False
        w=cert['witness']
        if type(w) is not dict or set(w)!={'start_phase','arrivals','blockers','urgent','compelled_at_failure'}:
            return False
        if type(w['start_phase']) is not int or w['start_phase']!=(p-1)%len(calendar):return False
        if type(w['compelled_at_failure']) is not int:return False
        for name in ('blockers','urgent'):
            if type(w[name]) is not list or any(type(i) is not int for i in w[name]):return False
        entries=w['arrivals'];q=[[] for _ in range(n)];tokens=list(buckets)
        if type(entries) is not list:return False
        if any(type(row) is not list or len(row)!=3 or any(type(v) is not int for v in row) for row in entries):return False
        for t,i,c in entries:
            if t not in (0,1) or not 0<=i<n or c<1 or c>costs[i]:return False
            if tokens[i]<c or sum(q[i])+c>capacities[i]:return False
            tokens[i]-=c;q[i].append(c)
        first=sorted({i for t,i,c in entries if t==0})
        second=sorted({i for t,i,c in entries if t==1})
        if len(first)>m or set(first)&set(second):return False
        if any(q[i] != [2] for i in first) or any(q[i] != [1] for i in second):return False
        R={i for i in calendar[p] if i>=0}
        if set(second)!=R or not R or any(i in R for i in first):return False
        # At t=0 every ready tenant is forced to start; all still run at t=1.
        return (len(first)+len(second)==m+1 and w['blockers']==first and
                w['urgent']==second and w['compelled_at_failure']==m+1)
    except (KeyError,ValueError,IndexError,TypeError):
        return False
