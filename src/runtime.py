"""Continuous CRSI execution; certification is not assumed to imply utilization.

Only this executor depends on the producer. runtime_replay imports neither.
A snapshot is taken after each slot's refill and reference-gated admissions.
Every retained commitment uses only the current actual backlog. No future offer
is passed to the dispatcher. Negative controls may violate lead; such runs are
retained and must never feed an invalid snapshot to the producer.
"""
from __future__ import annotations
from collections import deque
from typing import Any
from admission import Tenant
from commitment import Snapshot, certify_plan
from plan_oracle import check_certificate

POLICIES = ('reservation', 'urgent', 'naive', 'snapshot', 'certified', 'certified-interrupt')


def validate_config(config: dict) -> None:
    if type(config) is not dict or set(config) != {'calendar', 'phase', 'tenants', 'offers'}:
        raise ValueError('unexpected runtime input fields')
    tenants = config['tenants']
    if type(tenants) is not list or not tenants:
        raise ValueError('empty tenant set')
    for v in tenants:
        if type(v) is not dict or set(v) != {'capacity', 'bucket', 'period', 'refill', 'tokens'}:
            raise ValueError('invalid monitor fields')
        Tenant(0, 0, **v).validate()
    Snapshot.from_dict({'calendar': config['calendar'], 'phase': config['phase'],
                        'tenants': [dict(backlog=0, lead=0, **v) for v in tenants]}).validate()
    if type(config['offers']) is not list or not config['offers']:
        raise ValueError('empty offer stream')
    for a in config['offers']:
        if type(a) is not list or len(a) != len(tenants) or any(type(x) is not int or x < 0 for x in a):
            raise ValueError('invalid offered vector')


def urgent_column(q: list[int], lead: list[int], owners: list[int], m: int) -> tuple[int, ...]:
    urgent = [i for i in owners if i >= 0 and q[i] > 0 and lead[i] == 0]
    rest = sorted((i for i, v in enumerate(q) if v > 0 and i not in urgent), key=lambda i: (-q[i], i))
    chosen = urgent + rest[:m-len(urgent)]
    return tuple(chosen + [-1] * (m-len(chosen)))


def propose(q: list[int], m: int, length: int) -> tuple[tuple[int, ...], ...]:
    """Largest-current-backlog-first proposal; the same rule serves all controls."""
    remaining = q[:]
    cols = []
    for _ in range(length):
        chosen = sorted((i for i, v in enumerate(remaining) if v > 0), key=lambda i: (-remaining[i], i))[:m]
        for i in chosen:
            remaining[i] -= 1
        cols.append(tuple(chosen + [-1] * (m-len(chosen))))
    return tuple(cols)


def snapshot_first_failure(q: list[int], refq: list[int], lead: list[int], calendar, phase: int, plan) -> int | None:
    """Intentionally incomplete zero-future-arrival negative control."""
    a, r, l = q[:], refq[:], lead[:]
    for s, col in enumerate(plan):
        for i in col:
            if i >= 0:
                a[i] -= 1
                l[i] += 1
        for i in calendar[(phase+s) % len(calendar)]:
            if i >= 0 and r[i] > 0:
                r[i] -= 1
                l[i] -= 1
        if min(l) < 0:
            return s
    return None


def execute(config: dict[str, Any], policy: str, batch: int) -> dict[str, Any]:
    validate_config(config)
    if policy not in POLICIES or type(batch) is not int or batch < 1:
        raise ValueError('invalid policy or batch length')
    calendar, monitors = config['calendar'], config['tenants']
    n, m, horizon = len(monitors), len(calendar[0]), len(config['offers'])
    q, refq, lead = [0]*n, [0]*n, [0]*n
    tokens = [v['tokens'] for v in monitors]
    next_refill = [v['refill'] for v in monitors]
    pending: deque[tuple[int, ...]] = deque()
    events = []
    control = {'proposal_calls': 0, 'checker_calls': 0, 'rejected_proposals': 0,
               'fallback_slots': 0, 'interrupted_batches': 0, 'accepted_prefix_slots': 0}
    for t, offer in enumerate(config['offers']):
        for i, v in enumerate(monitors):
            if t == next_refill[i]:
                tokens[i] = min(v['bucket'], tokens[i]+1)
                next_refill[i] += v['period']
        admitted = [min(offer[i], tokens[i], monitors[i]['capacity']-refq[i]) for i in range(n)]
        for i, a in enumerate(admitted):
            tokens[i] -= a
            q[i] += a
            refq[i] += a
        phase = (config['phase'] + t) % len(calendar)
        owners = calendar[phase]
        if policy == 'reservation':
            col = tuple(i if i >= 0 and q[i] else -1 for i in owners)
        elif policy == 'urgent':
            col = urgent_column(q, lead, owners, m)
        else:
            interrupted = False
            if policy == 'certified-interrupt' and pending:
                named = sum(i >= 0 for i in pending[0])
                if named < min(m, sum(v > 0 for v in q)):
                    pending.clear()
                    control['interrupted_batches'] += 1
                    interrupted = True
            if interrupted:
                col = urgent_column(q, lead, owners, m)
                control['fallback_slots'] += 1
            else:
                if not pending:
                    length = min(batch, horizon-t)
                    plan = propose(q, m, length)
                    control['proposal_calls'] += 1
                    failure = None
                    if policy.startswith('certified'):
                        state = {'calendar': calendar, 'phase': phase, 'tenants': [
                            dict(backlog=q[i], lead=lead[i], capacity=v['capacity'], tokens=tokens[i],
                                 bucket=v['bucket'], period=v['period'], refill=next_refill[i]-t)
                            for i, v in enumerate(monitors)]}
                        cert = certify_plan(Snapshot.from_dict(state), plan)
                        control['checker_calls'] += 1
                        if not check_certificate(state, plan, cert):
                            raise RuntimeError('independent checker rejected producer output')
                        if not cert['safe']:
                            failure = cert['first_failure'][0]
                    elif policy == 'snapshot':
                        failure = snapshot_first_failure(q, refq, lead, calendar, phase, plan)
                    if failure is None:
                        pending.extend(plan)
                        control['accepted_prefix_slots'] += len(plan)
                    elif failure > 0:
                        pending.extend(plan[:failure])
                        control['rejected_proposals'] += 1
                        control['accepted_prefix_slots'] += failure
                    else:
                        pending.append(urgent_column(q, lead, owners, m))
                        control['rejected_proposals'] += 1
                        control['fallback_slots'] += 1
                col = pending.popleft()
        for i in col:
            if i >= 0:
                if q[i] <= 0:
                    raise RuntimeError('plan executed an empty tenant')
                q[i] -= 1
                lead[i] += 1
        for i in owners:
            if i >= 0 and refq[i] > 0:
                refq[i] -= 1
                lead[i] -= 1
        if any(refq[i]-q[i] != lead[i] for i in range(n)):
            raise RuntimeError('queue identity broken')
        events.append({'time': t, 'admitted': admitted, 'served': list(col),
                       'queue': q[:], 'reference_queue': refq[:], 'lead': lead[:], 'tokens': tokens[:]})
    return {'policy': policy, 'batch': batch, 'events': events, 'control': control}
