"""Exact candidate-batch test for counterfactual calendar service.

All offsets are slots. State is observed AFTER the arrivals of offset zero.
Future refills and arrivals occur before service, beginning at offset one.
No simulation, I/O, third-party package or external service is used here.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

@dataclass(frozen=True)
class Tenant:
    backlog: int
    lead: int
    capacity: int
    tokens: int
    bucket: int
    period: int
    refill: int

    def validate(self) -> None:
        if any(type(v) is not int for v in asdict(self).values()):
            raise ValueError('tenant fields must be integers, not booleans')
        if not (0 <= self.backlog and 0 <= self.lead
                and self.backlog + self.lead <= self.capacity
                and self.capacity >= 1 and self.bucket >= 1
                and 0 <= self.tokens <= self.bucket and self.period >= 1
                and 1 <= self.refill <= self.period):
            raise ValueError('invalid tenant state')

@dataclass(frozen=True)
class State:
    calendar: tuple[int, ...]
    phase: int
    tenants: tuple[Tenant, ...]

    def validate(self) -> None:
        if not self.tenants or not self.calendar:
            raise ValueError('empty tenant set or calendar')
        if type(self.phase) is not int or not 0 <= self.phase < len(self.calendar):
            raise ValueError('invalid phase')
        if any(type(v) is not int or not -1 <= v < len(self.tenants)
               for v in self.calendar):
            raise ValueError('invalid calendar owner')
        for t in self.tenants:
            t.validate()

    def owner(self, offset: int) -> int:
        return self.calendar[(self.phase + offset) % len(self.calendar)]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> 'State':
        if set(obj) != {'calendar', 'phase', 'tenants'}:
            raise ValueError('unexpected state field')
        s = State(tuple(obj['calendar']), obj['phase'],
                  tuple(Tenant(**v) for v in obj['tenants']))
        s.validate()
        return s


def certify(state: State, borrower: int, length: int) -> dict[str, Any]:
    """Produce a horizon-limited certificate. None means no violation in the batch."""
    state.validate()
    if type(borrower) is not int or not 0 <= borrower < len(state.tenants):
        raise ValueError('invalid borrower')
    if type(length) is not int or not 1 <= length <= state.tenants[borrower].backlog:
        raise ValueError('batch must be positive and already queued')
    counts = [0] * len(state.tenants)
    first: list[int | None] = [None] * len(state.tenants)
    for s in range(length):
        i = state.owner(s)
        if i < 0:
            continue
        counts[i] += 1
        t = state.tenants[i]
        eligible = 0 if t.backlog else (1 if t.tokens else t.refill)
        if (i != borrower and first[i] is None and
                counts[i] > t.lead and s >= eligible):
            first[i] = s
    rows = [{'tenant': i, 'uncovered': first[i]} for i in range(len(first))
            if i != borrower]
    bad = [(v, i) for i, v in enumerate(first) if v is not None]
    witness: dict[str, Any] | None = None
    if bad:
        stop, i = min(bad)
        t = state.tenants[i]
        release = None
        if t.backlog == 0:
            q, x = t.lead, t.tokens
            for s in range(stop + 1):
                if s > 0:
                    if s >= t.refill and (s - t.refill) % t.period == 0:
                        x = min(t.bucket, x + 1)
                    if x > 0 and q < t.capacity:
                        release = s
                        break
                if state.owner(s) == i and q:
                    q -= 1
            if release is None:
                raise AssertionError('proved single-arrival witness was not constructible')
        witness = {'tenant': i, 'violation_offset': stop,
                   'arrivals': [] if release is None else [[release, i, 1]]}
    return {'borrower': borrower, 'length': length, 'safe': not bad,
            'rows': rows, 'witness': witness}
