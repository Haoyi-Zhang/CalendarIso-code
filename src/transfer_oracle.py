"""Independent, finite executable interpretation of transfer schedulability.

This is NOT the authors' implementation and not a Rocq extraction. It imports no
CRSI producer, checker or transition code. It enumerates legal arrivals, labels
FIFO unit jobs, and evaluates the published exact known-cost critical-interval
predicate. See proofs/transfer-schedulability.md for the mathematical embedding.
All time intervals are [t,d); boundary h is after slots 0,...,h-1.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator

FIELDS = {'backlog', 'lead', 'capacity', 'tokens', 'bucket', 'period', 'refill'}


def _nat(x: object, name: str, minimum: int = 0) -> int:
    if type(x) is not int or x < minimum:
        raise ValueError(f'{name}: expected integer >= {minimum}')
    return x


def validate(state: dict, plan: list | tuple) -> None:
    if type(state) is not dict or set(state) != {'calendar', 'phase', 'tenants'}:
        raise ValueError('invalid snapshot')
    ts, cal = state['tenants'], state['calendar']
    if not isinstance(ts, (list, tuple)) or not ts:
        raise ValueError('empty tenant sequence')
    if (not isinstance(cal, (list, tuple)) or not cal or
            not isinstance(cal[0], (list, tuple)) or not cal[0]):
        raise ValueError('empty calendar')
    if not isinstance(plan, (list, tuple)) or not plan:
        raise ValueError('empty plan')
    if _nat(state['phase'], 'phase') >= len(cal):
        raise ValueError('phase out of range')
    n, m = len(ts), len(cal[0])
    for row in ts:
        if type(row) is not dict or set(row) != FIELDS:
            raise ValueError('invalid tenant')
        for k, v in row.items():
            _nat(v, k, 0 if k in ('backlog', 'lead', 'tokens') else 1)
        if (row['backlog'] + row['lead'] > row['capacity'] or
                row['tokens'] > row['bucket'] or row['refill'] > row['period']):
            raise ValueError('tenant bounds')
    used = [0] * n
    for is_plan, sequence in ((False, cal), (True, plan)):
        for col in sequence:
            if not isinstance(col, (tuple, list)) or len(col) != m:
                raise ValueError('column width')
            if any(type(i) is not int or not (-2 if is_plan else -1) <= i < n for i in col):
                raise ValueError('column entry')
            productive = [i for i in col if i >= 0]
            if len(productive) != len(set(productive)):
                raise ValueError('seriality')
            if is_plan:
                for i in productive:
                    used[i] += 1
    if any(used[i] > ts[i]['backlog'] for i in range(n)):
        raise ValueError('plan depends on future work')


@dataclass(frozen=True)
class UnitTrace:
    """FIFO unit IDs are indices into release/online_cost; None means idle."""
    release: tuple[int, ...]
    online_cost: tuple[int, ...]
    reference: tuple[int | None, ...]
    actual: tuple[int | None, ...]
    lead: int
    arrivals: tuple[int, ...]


def tenant_traces(state: dict, plan: list | tuple, tenant: int) -> Iterator[UnitTrace]:
    """All full-length legal per-tenant arrival paths, including unsafe suffixes.

    Factorization is mathematically justified only for the independent CRSI
    monitor. This routine does not assume that one future unit is sufficient.
    Its caller must validate the joint snapshot and plan first.
    """
    t = state['tenants'][tenant]
    horizon = len(plan)
    d0 = t['backlog'] + t['lead']
    # State: reference FIFO, token balance, release labels, reference trace, arrivals.
    def walk(s, queue, tokens, release, reftrace, arrtrace):
        if s == horizon:
            pos = t['lead']
            actual = []
            for col in plan:
                if tenant in col:
                    actual.append(pos)
                    pos += 1
                else:
                    actual.append(None)
            yield UnitTrace(tuple(release), (0,) * t['lead'] + (1,) * (len(release)-t['lead']),
                            tuple(reftrace), tuple(actual), t['lead'], tuple(arrtrace))
            return
        if s and s >= t['refill'] and (s-t['refill']) % t['period'] == 0:
            tokens = min(t['bucket'], tokens+1)
        amounts = range(min(tokens, t['capacity']-len(queue))+1) if s else (0,)
        for amount in amounts:
            first = len(release)
            q = queue + tuple(range(first, first+amount))
            labels = release + (s,) * amount
            owner = tenant in state['calendar'][(state['phase']+s) % len(state['calendar'])]
            job = q[0] if owner and q else None
            q2 = q[1:] if job is not None else q
            yield from walk(s+1, q2, tokens-amount, labels,
                            reftrace+(job,), arrtrace+(amount,))
    yield from walk(0, tuple(range(d0)), t['tokens'], (0,)*d0, (), ())


def evaluate(trace: UnitTrace) -> dict:
    """Check exact critical intervals directly with explicit job identities.

    Also compare with cumulative dominance and the scalar specialization.
    The input contract is the FIFO unit-job encoding, not arbitrary task traces.
    Metadata, event counts, and FIFO execution are validated first.
    A rejected predicate is evidence about this full trace, not a universal
    admission decision. No producer verdict is read by this function.
    """
    if not isinstance(trace, UnitTrace):
        raise ValueError('expected UnitTrace')
    for field in ('release', 'online_cost', 'reference', 'actual', 'arrivals'):
        if type(getattr(trace, field)) is not tuple:
            raise ValueError('trace fields must be immutable tuples')
    H = len(trace.reference)
    if not H or H != len(trace.actual) or H != len(trace.arrivals):
        raise ValueError('trace length')
    J = len(trace.release)
    lead = _nat(trace.lead, 'lead')
    if lead > J or len(trace.online_cost) != J:
        raise ValueError('job metadata')
    if any(type(c) is not int or c not in (0, 1) for c in trace.online_cost):
        raise ValueError('unit costs')
    if trace.online_cost != (0,)*lead + (1,)*(J-lead):
        raise ValueError('initial-lead unit encoding')
    if any(type(r) is not int or not 0 <= r < H for r in trace.release):
        raise ValueError('release range')
    if tuple(sorted(trace.release)) != trace.release or any(trace.release[j] for j in range(lead)):
        raise ValueError('FIFO release order')
    if any(type(a) is not int or a < 0 for a in trace.arrivals) or trace.arrivals[0] != 0:
        raise ValueError('arrival amount')
    if any(trace.arrivals[h] != trace.release.count(h) for h in range(1, H)):
        raise ValueError('release labels do not match future arrivals')
    rdone, adone = [set()], [{j for j in range(J) if trace.online_cost[j] == 0}]
    for s, (r, a) in enumerate(zip(trace.reference, trace.actual)):
        rs, ac = set(rdone[-1]), set(adone[-1])
        for job, done, cost in ((r, rs, (1,)*J), (a, ac, trace.online_cost)):
            if job is not None:
                if type(job) is not int or not 0 <= job < J or trace.release[job] > s:
                    raise ValueError('unreleased or invalid job')
                if job in done or cost[job] != 1:
                    raise ValueError('execution after completion')
                if job != len(done):
                    raise ValueError('non-FIFO unit execution')
                done.add(job)
        rdone.append(rs); adone.append(ac)
    prefix = all(rdone[h] <= adone[h] for h in range(H+1))
    cumulative = all(sum(x is not None for x in trace.reference[:h]) <=
                     trace.lead+sum(x is not None for x in trace.actual[:h]) for h in range(H+1))
    criterion = True
    intervals = slackless = 0
    first_bad = None
    for d in range(1, H+1):
        for t in range(d):
            intervals += 1
            critical = rdone[d] - adone[t]
            remaining = sum(trace.online_cost[j] for j in critical)
            scalar = max(0, len(rdone[d])-trace.lead-sum(x is not None for x in trace.actual[:t]))
            if remaining != scalar:
                raise AssertionError('unit-job scalar reduction mismatch')
            if remaining == d-t:
                slackless += 1
                if trace.actual[t] not in critical:
                    criterion = False
                    if first_bad is None:
                        first_bad = [t, d]
    return {'prefix': prefix, 'cumulative': cumulative, 'criterion': criterion,
            'intervals': intervals, 'slackless': slackless, 'first_bad_interval': first_bad}


def certify_by_transfer(state: dict, plan: list | tuple) -> dict:
    """Exact finite baseline: enumerate all arrivals, evaluate all TS intervals."""
    validate(state, plan)
    safe = True
    counts = dict(traces=0, intervals=0, slackless=0, unsafe_traces=0)
    for tenant in range(len(state['tenants'])):
        for trace in tenant_traces(state, plan, tenant):
            result = evaluate(trace)
            if not result['prefix'] == result['cumulative'] == result['criterion']:
                raise AssertionError('transfer embedding mismatch')
            counts['traces'] += 1
            counts['intervals'] += result['intervals']
            counts['slackless'] += result['slackless']
            if not result['criterion']:
                counts['unsafe_traces'] += 1
                safe = False
    return {'safe': safe, **counts}
