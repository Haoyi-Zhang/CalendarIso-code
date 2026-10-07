"""Exact run-length admission for a constant multicore commitment.

The monitor and admissible arrivals are unchanged. Calendar positions are indexed
once; no column of the proposed run is materialized or scanned.
"""
from __future__ import annotations
from bisect import bisect_left
from commitment import Snapshot, _validate_column


def certify_constant(snapshot: Snapshot, column: tuple[int, ...], length: int) -> dict:
    snapshot.validate()
    if type(length) is not int or length < 1:
        raise ValueError('positive integer run length required')
    _validate_column(column, len(snapshot.calendar[0]), len(snapshot.tenants), -2)
    chosen = {i for i in column if i >= 0}
    if any(snapshot.tenants[i].backlog < length for i in chosen):
        raise ValueError('commitment relies on work that has not arrived')
    period = len(snapshot.calendar)
    positions = [[] for _ in snapshot.tenants]
    for offset in range(period):
        for i in snapshot.calendar[(snapshot.phase + offset) % period]:
            if i >= 0:
                positions[i].append(offset)
    failures = []
    for i, (tenant, slots) in enumerate(zip(snapshot.tenants, positions)):
        if i in chosen or not slots:
            continue
        # The first reference opportunity after consuming all initial lead.
        cycle, index = divmod(tenant.lead, len(slots))
        crossing = cycle * period + slots[index]
        eligible = 0 if tenant.backlog else (1 if tenant.tokens else tenant.refill)
        threshold = max(crossing, eligible)
        cycle, residue = divmod(threshold, period)
        index = bisect_left(slots, residue)
        offset = cycle * period + slots[index] if index < len(slots) else (cycle + 1) * period + slots[0]
        if offset < length:
            failures.append((offset, i))
    if not failures:
        return {'safe': True, 'first_failure': None, 'witness': None}
    offset, i = min(failures)
    tenant = snapshot.tenants[i]
    if tenant.backlog:
        witness = {'kind': 'queued', 'arrivals': []}
    else:
        release = 1 if tenant.tokens else tenant.refill
        if tenant.lead == tenant.capacity:
            release = max(release, positions[i][0] + 1)
        if release > offset:
            raise AssertionError('arrival witness precedes the failing opportunity')
        witness = {'kind': 'future', 'arrivals': [[release, i, 1]]}
    return {'safe': False, 'first_failure': [offset, i], 'witness': witness}
