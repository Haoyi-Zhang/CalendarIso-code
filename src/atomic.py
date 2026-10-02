"""Static universal atomic-handler criterion and a minimal capacity witness.

No external scheduling implementation is used. All processors are interchangeable.
The guarantee is against a unit-service reference calendar, not an atomic reference.
"""
from __future__ import annotations


def certify_atomic(calendar, max_cost, buckets, capacities):
    n = len(max_cost)
    if (not n or not calendar or not calendar[0] or len(buckets) != n or
            len(capacities) != n):
        raise ValueError('empty or inconsistent dimensions')
    if any(type(x) is not int or x < 1 for arr in (max_cost,buckets,capacities) for x in arr):
        raise ValueError('cost and admission bounds must be positive integers')
    m = len(calendar[0]); long = {i for i in range(n) if min(max_cost[i],buckets[i],capacities[i]) >= 2}
    for col in calendar:
        if len(col) != m or any(type(i) is not int or i < -1 or i >= n for i in col):
            raise ValueError('invalid calendar column')
        owners = [i for i in col if i >= 0]
        if len(owners) != len(set(owners)):
            raise ValueError('a reference tenant cannot use two cores concurrently')
    for p,col in enumerate(calendar):
        R = {i for i in col if i >= 0}
        if R and len(long | R) > m:
            blockers = sorted(long-R)[:m-len(R)+1]
            return {'safe':False, 'long_tenants':sorted(long), 'failure_phase':p,
                    'witness':{'start_phase':(p-1)%len(calendar),
                    'arrivals':[[0,i,2] for i in blockers]+[[1,i,1] for i in sorted(R)],
                    'blockers':blockers,'urgent':sorted(R), 'compelled_at_failure':m+1}}
    return {'safe':True,'long_tenants':sorted(long),'failure_phase':None,'witness':None}


def choose_atomic(queues, active, reference_queue, owners, m, cursor=0):
    """Continue atomic handlers, then urgent reference owners, then cyclic fill.

queues contain FIFO remaining costs. Raises if the current state cannot provide
all urgent service; it never silently idles or drops an admitted handler.
"""
    n=len(queues); selected=set(i for i in range(n) if active[i])
    urgent={i for i in owners if i>=0 and queues[i] and reference_queue[i] == sum(queues[i])}
    selected |= urgent
    if len(selected)>m:
        raise RuntimeError('atomic continuations conflict with urgent reference service')
    for off in range(n):
        i=(cursor+off)%n
        if queues[i] and i not in selected and len(selected)<m:
            selected.add(i)
    return sorted(selected)
