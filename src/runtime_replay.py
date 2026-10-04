"""Independent continuous-execution replayer, importing no CRSI model or scheduler.

Checks one complete finite log against its externally supplied offer stream.
Accepting a log means well-formed legal execution, NOT isolation: violations
are computed and returned even for well-formed negative-control runs. It does
not attest to the policy label, proposal counters, admission fairness, code
identity, or a real device. Missing events and illegal suffixes are rejected.
"""
from __future__ import annotations
from collections import deque


def _integer(x, minimum=0):
    if type(x) is not int or x < minimum:
        raise ValueError('strict nonnegative integer required')
    return x


def _vector(v, n, minimum=0):
    if type(v) is not list or len(v) != n:
        raise ValueError('invalid vector shape')
    for x in v:
        _integer(x, minimum)


def replay(config: dict, log: dict) -> dict:
    if type(config) is not dict or set(config) != {'calendar', 'phase', 'tenants', 'offers'}:
        raise ValueError('invalid input record')
    monitors, calendar, offers = config['tenants'], config['calendar'], config['offers']
    if type(monitors) is not list or not monitors or type(calendar) is not list or not calendar:
        raise ValueError('empty model')
    n = len(monitors)
    if type(calendar[0]) is not list or not calendar[0]:
        raise ValueError('empty cores')
    m = len(calendar[0])
    for col in calendar:
        _vector(col, m, -1)
        if any(i >= n for i in col) or len([i for i in col if i >= 0]) != len(set(i for i in col if i >= 0)):
            raise ValueError('illegal calendar column')
    phase = _integer(config['phase'])
    if phase >= len(calendar):
        raise ValueError('phase outside calendar')
    for v in monitors:
        if type(v) is not dict or set(v) != {'capacity', 'bucket', 'period', 'refill', 'tokens'}:
            raise ValueError('invalid monitor')
        for k in ('capacity', 'bucket', 'period', 'refill'):
            _integer(v[k], 1)
        _integer(v['tokens'])
        if v['tokens'] > v['bucket'] or v['refill'] > v['period']:
            raise ValueError('monitor outside range')
    if type(offers) is not list or not offers:
        raise ValueError('empty input')
    for a in offers:
        _vector(a, n)
    if type(log) is not dict or set(log) != {'policy', 'batch', 'events', 'control'}:
        raise ValueError('invalid log record')
    if type(log['policy']) is not str or not log['policy']:
        raise ValueError('invalid policy label')
    _integer(log['batch'], 1)
    counters = {'proposal_calls','checker_calls','rejected_proposals','fallback_slots','interrupted_batches','accepted_prefix_slots'}
    if type(log['control']) is not dict or set(log['control']) != counters:
        raise ValueError('invalid control counters')
    for value in log['control'].values():
        _integer(value)
    if type(log['events']) is not list or len(log['events']) != len(offers):
        raise ValueError('incomplete execution log')
    actual = [deque() for _ in monitors]
    reference = [0] * n
    token = [v['tokens'] for v in monitors]
    credited = [0] * n
    consumed = [0] * n
    total_admitted = 0
    delays = []
    violations = 0
    idle = 0
    first = None
    for t, event in enumerate(log['events']):
        if type(event) is not dict or set(event) != {'time','admitted','served','queue','reference_queue','lead','tokens'}:
            raise ValueError('unexpected event fields')
        if type(event['time']) is not int or event['time'] != t:
            raise ValueError('noncanonical time')
        for key in ('admitted','queue','reference_queue','tokens'):
            _vector(event[key], n)
        if type(event['lead']) is not list or len(event['lead']) != n or any(type(x) is not int for x in event['lead']):
            raise ValueError('invalid lead')
        _vector(event['served'], m, -1)
        names = [i for i in event['served'] if i >= 0]
        if any(i >= n for i in names) or len(names) != len(set(names)):
            raise ValueError('seriality/capacity violation')
        for i, v in enumerate(monitors):
            if t >= v['refill'] and (t-v['refill']) % v['period'] == 0:
                token[i] = min(v['bucket'], token[i]+1)
            amount = min(offers[t][i], token[i], v['capacity']-reference[i])
            if event['admitted'][i] != amount:
                raise ValueError('reference admission mismatch')
            total_admitted += amount
            token[i] -= amount
            reference[i] += amount
            actual[i].extend([t]*amount)
        ready = sum(bool(q) for q in actual)
        idle += min(m, ready) - len(names)
        for i in names:
            if not actual[i]:
                raise ValueError('executing nonready work')
            delays.append(t+1-actual[i].popleft())
            consumed[i] += 1
        for i in calendar[(phase+t) % len(calendar)]:
            if i >= 0 and reference[i]:
                reference[i] -= 1
                credited[i] += 1
        lead = [consumed[i]-credited[i] for i in range(n)]
        if any(x < 0 for x in lead):
            violations += 1
            if first is None:
                first = t
        expected = {'queue': [len(q) for q in actual], 'reference_queue': reference, 'lead': lead, 'tokens': token}
        for key, value in expected.items():
            if event[key] != value:
                raise ValueError('execution mismatch: '+key)
    actual_work = sum(consumed)
    final_backlog = sum(len(q) for q in actual)
    if actual_work + final_backlog != total_admitted:
        raise AssertionError('accounting identity')
    return {'prefix_violation_slots': violations, 'first_violation_slot': first,
            'avoidable_idle_core_slots': idle, 'actual_work': actual_work, 'reference_work': sum(credited),
            'admitted_work': total_admitted, 'final_backlog': final_backlog,
            'completed_unit_delay_sum': sum(delays), 'completed_units': len(delays),
            'horizon': len(offers), 'core_slots': m*len(offers)}
