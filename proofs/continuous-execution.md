# Composition under continuous arrivals and interruptible commitments

This is a composition result for the retained fixed-plan theorem and the inherited
urgent-reference-first invariant. It is not a new general transfer theorem or an
optimal batching claim. All handlers in this execution model are preemptible at
unit slot boundaries. There is no switching, observation, or checking overhead.

## Boundary state and admission

At boundary t, refill the monitor, admit the offered work against its tokens and
reference-queue headroom, and only then take a snapshot. Maintain actual q_i,
reference D_i, and lead ell_i=D_i-q_i; never reset the reference at a batch boundary.
Admissions add the same amount to both queues and preserve the identity. The next
refill distance recorded in a snapshot is strictly positive. Current arrivals are
already included in q_i; an arrival at offset zero must not be inserted again.

A proposal consists solely of current actual backlog, has distinct tenant names
within each column, and respects the core count. For each named tenant, the total
number of named units is no greater than its current q_i. Thus every named future
unit remains executable while this proposal's prefix is followed: arrivals can
only increase its actual queue, and no other dispatch can consume that queue
without terminating the proposal.

## Prefix composition proposition

Start in a valid, isolated state. At every subsequent decision boundary, choose
one of (a) a nonempty certified safe prefix of a current-backlog-only proposal or
(b) one urgent-reference-first slot. A prefix can be terminated at any boundary,
provided the remaining proposal is discarded and the complete current state is
used for subsequent decisions. Then every execution prefix is isolated.

Proof. Induct over executed slots. The initial state is valid. During a retained
segment, the actual admission sequence is one of the continuations quantified by
the fixed-plan theorem, so its next prefix is safe. The capacity and executability
conditions hold by the proposal restrictions. If the certificate's first failure
has offset s>0, the prefix of length s is safe because no earlier pair fails; if
s=0, no proposal slot is accepted. A valid urgent-reference-first step instead
preserves lead by the one-slot result. The event equations preserve D_i-q_i=ell_i;
nonnegative lead implies q_i<=D_i<=Q_i. The physical calendar is unchanged except
for advancing phase, and token/refill state advances rather than resetting.
Therefore the next snapshot satisfies all hypotheses, regardless of whether the
old segment is continued, exhausted, or terminated. Induction proves the claim.
The theorem is semantic; the Python executor/checker connection is tested, not
mechanically refined.

## Work-conserving interruption corollary

After each slot's admissions, let k=min(m, number of nonempty actual tenant queues).
Before executing the next retained column, count its named units. If the number is
less than k, discard the remainder and execute urgent-reference-first instead.
Otherwise execute the column. A newly proposed prefix is formed by repeatedly
choosing up to m nonempty current queues, so its first column already has k names;
a rejected-at-zero proposal takes the urgent fallback. This policy is both
isolated and raw work-conserving at each slot.

Proof. Interruption is permitted by prefix composition. Every named unit in a
retained column is still available, and it has at most k names by capacity and
seriality. If it has k, no ready tenant/core opportunity is left avoidably unused.
If it has fewer, urgent-first serves all mandatory owners and fills the remaining
cores up to k. The same property holds for a new proposal's first column or an
immediate fallback. Thus each slot executes exactly k units and is safe.

This rule still observes arrivals and readiness every slot. Fewer proposal calls
cannot be interpreted as fewer observations, fewer interrupts, lower CPU cost,
or better throughput on a physical runtime. A positive switching cost changes
the model and would need a new feasibility analysis.

## Safe non-work-conserving commitment

Let m=1 and calendar=(tenant 0, idle, idle, tenant 1). Both actual/reference queues
are initially empty. Tenant 0 has no token and its next refill is at eight. Tenant
1 has one token and buffer/bucket capacity one; its next refill is also at eight.
At offset zero propose three idle slots. They are safe: no legal tenant-0 work can
arrive before its next reference opportunity, and tenant 1's next opportunity is
at offset three, beyond the proposed segment. Now admit one tenant-1 unit at
slot one. The immutable plan stays isolated while leaving ready work idle at
slots one and two. The interrupting policy serves it at slot one and carries its
positive lead forward. This is exercised by test_safe_immutable_commitment_can_idle.

## Independent finite evidence

The continuous protocol freezes five workload families, eight evaluation seeds,
three (tenant,core) layouts, four batch lengths and six policies. Every policy gets
the same offered stream, and reference-based admissions are checked to coincide.
The executor uses the existing producer and independent certificate checker;
a separately written event replayer imports neither. It reconstructs refills,
admissions, queues, service and lead for the entire log, including after an unsafe
prefix. It returns safety/utilization metrics and rejects malformed histories.
It does not reconstruct policy decisions or authenticate producer counter fields.

All finite outcomes, including both incomplete negative controls, are archived.
Equality of useful work for the urgent and interrupting policies on this grid is
an observation, not an optimality or per-tenant latency theorem. No learned model
is used; workload and parameter selection remain external-validity limitations.
