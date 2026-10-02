"""Multicore fixed-commitment producer. No code from an external scheduler.

A calendar column and a plan column contain one entry per core. Nonnegative
entries denote tenant service. Calendar -1 means unreserved; plan -1 means idle
and -2 means explicitly charged control/switch overhead. A tenant is serial:
no column may name that tenant twice. Each plan serves only work already queued.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from admission import Tenant

@dataclass(frozen=True)
class Snapshot:
    calendar: tuple[tuple[int, ...], ...]
    phase: int
    tenants: tuple[Tenant, ...]

    def validate(self) -> None:
        if not self.calendar or not self.tenants or not self.calendar[0]:
            raise ValueError('empty calendar, core set or tenant set')
        if type(self.phase) is not int or not 0 <= self.phase < len(self.calendar):
            raise ValueError('invalid calendar phase')
        for t in self.tenants:
            t.validate()
        for col in self.calendar:
            _validate_column(col, len(self.calendar[0]), len(self.tenants), -1)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> 'Snapshot':
        if set(obj) != {'calendar', 'phase', 'tenants'}:
            raise ValueError('unexpected snapshot fields')
        v = Snapshot(tuple(tuple(c) for c in obj['calendar']), obj['phase'],
                     tuple(Tenant(**t) for t in obj['tenants']))
        v.validate()
        return v


def _validate_column(col, m: int, n: int, lower: int) -> None:
    if len(col) != m or any(type(i) is not int or not lower <= i < n for i in col):
        raise ValueError('invalid core column')
    named = [i for i in col if i >= 0]
    if len(named) != len(set(named)):
        raise ValueError('concurrent use of a serial tenant')


def validate_plan(snapshot: Snapshot, plan: tuple[tuple[int, ...], ...]) -> None:
    snapshot.validate()
    if not plan:
        raise ValueError('empty commitment')
    used = [0] * len(snapshot.tenants)
    for col in plan:
        _validate_column(col, len(snapshot.calendar[0]), len(used), -2)
        for i in col:
            if i >= 0:
                used[i] += 1
    if any(c > t.backlog for c, t in zip(used, snapshot.tenants)):
        raise ValueError('commitment relies on work that has not arrived')


def certify_plan(snapshot: Snapshot, plan: tuple[tuple[int, ...], ...]) -> dict[str, Any]:
    """O(n + m*(P+L)) operations including validation; O(n) mutable workspace.

The admitted-plan scan alone uses O(n+m*L) arithmetic operations.

Returns earliest bad (offset, tenant), with lexicographic tenant tie break.
No hash or history authentication is asserted; the monitor owns the snapshot.
"""
    validate_plan(snapshot, plan)
    n = len(snapshot.tenants)
    served, reserved = [0] * n, [0] * n
    for s, col in enumerate(plan):
        for i in col:
            if i >= 0:
                served[i] += 1
        ref = snapshot.calendar[(snapshot.phase + s) % len(snapshot.calendar)]
        bad = []
        for i in ref:
            if i < 0:
                continue
            reserved[i] += 1
            t = snapshot.tenants[i]
            earliest = 1 if t.tokens else t.refill
            if (reserved[i] > t.lead + served[i] and
                    (served[i] < t.backlog or s >= earliest)):
                bad.append(i)
        if bad:
            i = min(bad)
            t = snapshot.tenants[i]
            arrivals = []
            kind = 'queued'
            if served[i] == t.backlog:
                kind = 'future'
                q, x = t.backlog + t.lead, t.tokens
                found = False
                for u in range(s + 1):
                    if u:
                        if u >= t.refill and (u - t.refill) % t.period == 0:
                            x = min(t.bucket, x + 1)
                        if x and q < t.capacity:
                            arrivals = [[u, i, 1]]
                            found = True
                            break
                    if i in snapshot.calendar[(snapshot.phase + u) % len(snapshot.calendar)] and q:
                        q -= 1
                if not found:
                    raise AssertionError('single-arrival lemma failed')
            return {'safe': False, 'first_failure': [s, i],
                    'witness': {'kind': kind, 'arrivals': arrivals}}
    return {'safe': True, 'first_failure': None, 'witness': None}
