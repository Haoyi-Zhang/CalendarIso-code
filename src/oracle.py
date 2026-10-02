"""Independent exact finite oracle; does not import or call the admission test.

For each displaced tenant, enumerate all legal arrival amounts at every slot,
merging identical (queue, token, service) states. Product independence is
separately validated by the joint oracle in the test suite.
"""
from __future__ import annotations
from typing import Any

def exhaustive(state: dict[str, Any], borrower: int, length: int) -> tuple[bool, int]:
    cal, phase = state['calendar'], state['phase']
    explored = 0
    for i, t in enumerate(state['tenants']):
        if i == borrower:
            continue
        frontier = {(t['backlog'] + t['lead'], t['tokens'], 0)}
        for s in range(length):
            nxt = set()
            for q, x, done in frontier:
                if s:
                    if s >= t['refill'] and (s - t['refill']) % t['period'] == 0:
                        x = min(t['bucket'], x + 1)
                    choices = range(min(x, t['capacity'] - q) + 1)
                else:
                    choices = (0,)
                for a in choices:
                    explored += 1
                    q2, x2, done2 = q + a, x - a, done
                    if cal[(phase + s) % len(cal)] == i and q2 > 0:
                        q2 -= 1
                        done2 += 1
                    if done2 > t['lead']:
                        return False, explored
                    nxt.add((q2, x2, done2))
            frontier = nxt
    return True, explored


def one_arrival_check(state: dict[str, Any], borrower: int, length: int) -> tuple[bool, int | None]:
    """Replay zero/one arrival at EVERY offset; different implementation from producer.

This reduced checker relies on the general single-arrival theorem. The exhaustive
oracle above does not rely on that theorem. Return earliest violating offset.
"""
    bad = []
    for i, t in enumerate(state['tenants']):
        if i == borrower:
            continue
        for release in [None, *range(1, length)]:
            q, x, served = t['backlog'] + t['lead'], t['tokens'], 0
            legal = True
            earliest = None
            for s in range(length):
                if s and s >= t['refill'] and (s - t['refill']) % t['period'] == 0:
                    x = min(t['bucket'], x + 1)
                if s == release:
                    if not x or q == t['capacity']:
                        legal = False
                        break
                    q += 1
                    x -= 1
                if state['calendar'][(state['phase'] + s) % len(state['calendar'])] == i and q:
                    q -= 1
                    served += 1
                if served > t['lead'] and earliest is None:
                    earliest = s
            if legal and earliest is not None:
                bad.append(earliest)
    return (not bad, min(bad) if bad else None)


def replay_witness(state: dict[str, Any], certificate: dict[str, Any]) -> bool:
    """Validate one rejected single-core certificate's explicit witness prefix.

    This checker is independent of :mod:`admission`: it validates the serialized
    snapshot, the rejection fields that control replay, and the complete witness
    prefix through the declared first failure.  It does *not* prove that a safe
    verdict is globally correct; ``exhaustive`` and ``one_arrival_check`` serve
    that separate purpose.

    A witness is prefix-scoped: every listed arrival must occur no later than the
    declared violation offset.  This prevents accepting an invalid event hidden
    after an early failure.  Exact ``type(...) is int`` checks deliberately reject
    booleans, which compare equal to zero or one in Python.
    """
    try:
        if type(state) is not dict or set(state) != {'calendar', 'phase', 'tenants'}:
            return False
        calendar, tenants = state['calendar'], state['tenants']
        if type(calendar) not in (list, tuple) or not calendar:
            return False
        if type(tenants) not in (list, tuple) or not tenants:
            return False
        if (type(state['phase']) is not int or
                not 0 <= state['phase'] < len(calendar) or
                any(type(owner) is not int or not -1 <= owner < len(tenants)
                    for owner in calendar)):
            return False
        fields = {'backlog', 'lead', 'capacity', 'tokens', 'bucket', 'period', 'refill'}
        for t in tenants:
            if type(t) is not dict or set(t) != fields or any(type(v) is not int for v in t.values()):
                return False
            if (min(t['backlog'], t['lead'], t['tokens']) < 0 or
                    min(t['capacity'], t['bucket'], t['period'], t['refill']) < 1 or
                    t['backlog'] + t['lead'] > t['capacity'] or
                    t['tokens'] > t['bucket'] or t['refill'] > t['period']):
                return False

        if (type(certificate) is not dict or
                set(certificate) != {'borrower', 'length', 'safe', 'rows', 'witness'}):
            return False
        borrower, length = certificate['borrower'], certificate['length']
        if (type(borrower) is not int or not 0 <= borrower < len(tenants) or
                type(length) is not int or not 1 <= length <= tenants[borrower]['backlog'] or
                type(certificate['safe']) is not bool or certificate['safe']):
            return False

        rows = certificate['rows']
        if type(rows) is not list or len(rows) != len(tenants) - 1:
            return False
        uncovered: dict[int, int | None] = {}
        for row in rows:
            if type(row) is not dict or set(row) != {'tenant', 'uncovered'}:
                return False
            tenant, offset = row['tenant'], row['uncovered']
            if (type(tenant) is not int or not 0 <= tenant < len(tenants) or
                    tenant == borrower or tenant in uncovered):
                return False
            if offset is not None and (type(offset) is not int or not 0 <= offset < length):
                return False
            uncovered[tenant] = offset
        if set(uncovered) != set(range(len(tenants))) - {borrower}:
            return False

        w = certificate['witness']
        if type(w) is not dict or set(w) != {'tenant', 'violation_offset', 'arrivals'}:
            return False
        tenant, violation = w['tenant'], w['violation_offset']
        if (type(tenant) is not int or not 0 <= tenant < len(tenants) or tenant == borrower or
                type(violation) is not int or not 0 <= violation < length or
                uncovered.get(tenant) != violation):
            return False
        if min((offset, i) for i, offset in uncovered.items() if offset is not None) != (violation, tenant):
            return False

        arrivals = w['arrivals']
        if type(arrivals) is not list or len(arrivals) > 1:
            return False
        if arrivals:
            event = arrivals[0]
            if (type(event) is not list or len(event) != 3 or
                    any(type(v) is not int for v in event) or
                    event[1:] != [tenant, 1] or
                    not 1 <= event[0] <= violation):
                return False

        t = tenants[tenant]
        q, x, done = t['backlog'] + t['lead'], t['tokens'], 0
        first_failure = None
        for s in range(violation + 1):
            if s and s >= t['refill'] and (s - t['refill']) % t['period'] == 0:
                x = min(t['bucket'], x + 1)
            if arrivals and arrivals[0][0] == s:
                if not x or q >= t['capacity']:
                    return False
                q += 1
                x -= 1
            if calendar[(state['phase'] + s) % len(calendar)] == tenant and q:
                q -= 1
                done += 1
            if done > t['lead'] and first_failure is None:
                first_failure = s
        return first_failure == violation
    except (TypeError, ValueError, KeyError, IndexError):
        return False
