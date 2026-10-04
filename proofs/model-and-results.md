# Calendar-relative service isolation


## Attribution to the transfer-schedulability framework

`proofs/transfer-schedulability.md` supplies the explicit reduction to the generic
known-online-cost criterion in Willemsen et al., TECS 2025, DOI 10.1145/3763236.
Reference-relative preservation and the per-trace critical-interval condition
are prior results. CRSI is their FIFO unit-job instance, including initial lead;
serial multicore executions project tenantwise after capacity validation.
Arbitrary legal arrival sequences are permitted by that generic theorem.
Theorem 1 below establishes the additional model-specific elimination of the
monitor continuation quantifier, not a new general transfer theorem. Theorem 2's
service invariant and FIFO completion are specializations/corollaries; its
work-conservation proof checks physical capacity. Theorem 3 additionally proves
causal atomic-policy existence and adversarial necessity. Its safety invariant
is inherited from the unit-job specialization. None of these prose reductions
is an executed Rocq proof or a firstness claim over all scheduling literature.

## Model and event order

Time and work are nonnegative integers. There are n serial tenants and m identical
cores. Each core provides one work unit in a slot. The periodic reference calendar
has P columns, each with m entries: a tenant identifier or an unreserved entry. A
tenant occurs at most once in a column. There are no affinity restrictions,
self-suspensions, cross-tenant dependencies, or shared-lock delays.

Both reference and implementation process the same admitted per-tenant FIFO work
stream. Work can represent successive units of a known-cost FIFO handler. Work
progress, not just completed jobs, is the isolation observable. A trusted monitor
owns the queue and accounting state. Capability/namespace protection and exact
progress/preemption enforcement are assumptions, not security results.

At each absolute slot: (1) replenish admission tokens, (2) admit arrivals using the
reference-queue headroom and the tenant's token balance, (3) choose/continue actual
service, (4) execute actual and reference service, (5) update both queues and lead.
A decision snapshot is after the current slot's arrivals. Thus future arrivals have
strictly positive offsets. Subsequent arrivals use the same monitor in all policies;
a scheduling decision cannot change the offered/admitted reference stream.

Tenant i has actual queue q_i >= 0, lead ell_i >= 0, and reference queue
D_i = q_i + ell_i <= Q_i, where Q_i >= 1. The lead is cumulative actual service
minus cumulative reference service. Admission uses integer work tokens x_i in
[0,b_i], b_i >= 1, with one token replenished every T_i slots and next positive
refill offset r_i in [1,T_i]. At a future slot, any integer amount between zero and
min(tokens, Q_i - reference_queue) may be admitted. An admitted unit consumes one
token. In the atomic-handler extension, an admitted known-cost job consumes its
entire work cost at admission and must fit the same headroom. The cost of each
arriving job is revealed at admission and is the same in both worlds.

A finite fixed commitment of length L lists one service/idle/explicit-overhead
entry per core and slot. No column serves a tenant twice. Total committed service
to i is at most the *current* q_i. This is not a policy tree: no part of its promised
productive service relies on an unseen arrival. If a handler is atomic, its
non-preemptive execution must additionally be respected by the supplied plan.
Overhead entries consume core slots without productive work; their costs are inputs,
not measurements. Let Y_i(h) count committed service and C_i(h) count reference
opportunities over the first h slots, for 1 <= h <= L. Define

    e_i = 1 if x_i > 0, and e_i = r_i otherwise.

An admissible continuation is any stream allowed by the above stateful admission
rules, not a statistical workload model. A plan is safe when actual cumulative
service is at least reference cumulative service for every tenant after every slot,
under *every* admissible continuation.

## Theorem 1: exact fixed-commitment admission

A valid commitment is unsafe if and only if some reference opportunity for tenant i
at offset s in [0,L-1] satisfies both

    C_i(s+1) > ell_i + Y_i(s+1),
    Y_i(s+1) < q_i  OR  s >= e_i.                       (1)

The earliest such offset is the earliest achievable violation. Among simultaneous
failures, tenant identifiers provide a deterministic tie break; this order is not a
scheduling priority or a fairness requirement.

### Proof: sufficiency of rejection and sparse witnesses

Fix a pair (s,i) satisfying (1). First suppose Y_i(s+1) < q_i. Admit no future work.
The reference then completes min(D_i,C_i(s+1)) work units by that prefix. Both
arguments of this minimum exceed ell_i + Y_i(s+1), so this continuation violates
isolation.

Otherwise Y_i(s+1) = q_i, since no commitment can exceed q_i. Hence
C_i(s+1) > D_i. Because a serial reference offers at most one unit in a slot,
C_i(s) >= D_i. Under the continuation with no arrivals before s, the initial
reference queue is therefore empty before service at s. Condition s >= e_i ensures
that at least one token is available at s under no prior admissions; Q_i >= 1
ensures room. Admit exactly one unit to i at s and no other future work. The
reference executes this unit in its opportunity at s and has completed D_i+1
units. The implementation has completed q_i committed units at this prefix, in
addition to its initial ell_i lead. Its allowed comparison total is D_i, so it lags
by one. This proves the one-future-unit witness without assuming that an initially
full reference queue had admission headroom.

The implementation may instead emit the earliest legal one-unit admission u <= s
(as its producer does). If the reference initially drains before u, the new unit
is served by the first later i-opportunity, which is no later than s. If the initial
queue has not drained before u, it stays busy until all D_i+1 units have been served;
C_i(s+1)>D_i suffices. Thus this earlier witness is also valid.

### Proof: necessity and earliest prefix

Consider the first violating offset s of any legal continuation and a violated
tenant i. Its lead can decrease only when the reference serves it, so i has a
reference opportunity at s. Reference service is at most C_i(s+1), and violation
requires service strictly greater than ell_i+Y_i(s+1), giving the first inequality.
If Y_i(s+1)<q_i, the second condition holds. In the remaining case Y_i(s+1)=q_i,
reference service exceeds D_i. At least one future unit must therefore have been
admitted and served by s. No future admission occurs before offset 1, and with
initial tokens zero none occurs before r_i. Thus s>=e_i. Every first violation
satisfies (1), and every detected pair has a witness. The first detected offset is
therefore exact. All other tenants can admit no future work, so separate per-tenant
witnesses are also legal joint continuations. QED.

### Cardinality boundary

A witness uses zero or one future admitted work unit. When Y_i(s+1)=q_i, zero future
units cannot violate the comparison for this particular (i,s), because the reference
has only D_i initial units. This is a minimum-cardinality statement at the selected
prefix and tenant, not a claim of globally minimum arrivals among all later failures
of all tenants. The fixed-commitment restriction is essential.

### Complexity and checker boundary

A scan increments Y for actual core entries and C for reference core entries and
checks only reference owners. After validation it takes O(n+mL) integer arithmetic
operations and O(n) mutable counters. Standalone validation also reads the P*m
calendar entries, giving O(n+m(P+L)) operations overall. Producing a sparse witness
adds O(mL) scanning in the implementation. Counters require O(log(L+q_max+ell_max+1))
bits; these are arithmetic-operation counts, not bit-operation or hardware timing
claims. The separate checker explicitly replays all zero/one future-unit cases. It
uses the theorem for completeness and is slower (quadratic in L); the exhaustive
DP oracle does not use that reduction and enumerates all legal admission amounts.
Neither code separation nor finite agreement constitutes independent human review
or a mechanized proof of this theorem.  The single-core sparse replay helper has a
narrow contract: it checks a rejected certificate's complete explicit prefix
through the declared first violation.  It uses exact integer-type and range checks,
rejects any listed event after that prefix, and does not certify safe verdicts.
The multicore input checker treats calendar and plan as explicit roles rather than
inferring a role from Python object identity; aliasing, copying and equal-valued
sequences therefore have the same semantics, while actual plan service is still
bounded by current backlog.

## Corollary 1: a consecutive one-core batch

On a single core, a borrower k receiving one unit in each of L consecutive slots,
L<=q_k, cannot fall behind its own serial reference. For every other tenant i with
q_i>0, its first dangerous offset is the (ell_i+1)-th reference opportunity. For
q_i=0 it is the first i-opportunity at or after e_i whose cumulative opportunity
count exceeds ell_i. The batch is safe exactly when all such offsets are >=L.
This is an exact acceptance test for a supplied batch, not an optimal selection of
batches, a general task-system schedulability test, or a maximum-throughput theorem.

## Theorem 2: composition and unit-preemptive work conservation

Assume slot-boundary preemption at no unmodeled cost. At each boundary, include all
currently nonempty, zero-lead tenants whose reference has an opportunity in that
slot. Then fill spare cores with other distinct nonempty tenants. This one-slot
commitment is safe and uses min(m,number of nonempty tenants) cores. Repeating it,
or replacing any consecutive segment by a safe fixed commitment, preserves service
isolation. A safe replacement is also work conserving if it occupies every core
with initially queued productive work throughout its duration. Otherwise the
one-slot urgent-first rule, followed by a new snapshot, remains work conserving.
A certificate alone does not establish work conservation of an arbitrary idle plan.

### Proof

The urgent tenants fit because reference owners in a column are distinct and at
most m. A reference owner with positive actual work and zero lead is served. A
nonserved owner with positive lead can lose at most one unit of lead. A nonserved
owner with zero actual work has reference backlog equal to its lead, so either it
is idle or can also lose at most one existing lead. Thus every lead stays
nonnegative. Filling the remaining cores proves raw capacity-relative work
conservation under the serial-tenant constraint. The plan is valid because it
serves only currently queued work.

At any later commitment boundary, both queues receive identical arrivals; their
difference remains the lead, and the state has the same form. Theorem 1 preserves
all intermediate prefixes. Induction over commitment boundaries proves composition.
If all cores are occupied with initially queued work, no future arrival can create
an avoidably idle core. When a full-core commitment is unavailable, the one-slot
rule instead makes a maximal productive assignment and resnapshots after the next
arrivals. No sufficiency claim is made for an arbitrary plan containing idle entries. QED.

### FIFO completion and starvation

For the same known positive-integer FIFO job costs in both schedules, cumulative
work dominance implies no job completes later than in the reference: completion
of job j occurs when cumulative work reaches the sum of the first j costs. If every
tenant has at least one reference opportunity per period P and Q_i is finite, each
admitted unit has at most Q_i-1 reference work units before it and is served within
at most Q_i*P slots after admission (a conservative bound including phase). No
subsequent FIFO arrival can move ahead of it. Consequently admitted work cannot
starve in a dominant implementation. A tenant with no reserved opportunity needs an
additional fairness mechanism; raw work conservation alone does not imply its
starvation freedom. No external deadline is guaranteed unless the reference meets it.

## Theorem 3: universal atomic-handler boundary

Extend the model to FIFO handlers with revealed costs in {1,...,H_i}, with
H_i>=1, and no preemption within a handler. A tenant remains serial. Admission
consumes cost-many tokens and reference-queue work units. Define

    B = {i : min(H_i,b_i,Q_i) >= 2}.

These are precisely the tenants able to admit an atomic handler of cost at least
two. A scheduler must accept the same independently admissible arrivals as the
reference; it may not drop a legal arrival merely to repair its scheduling choice.
The reference itself remains the unit-granularity calendar and need not obey the
implementation's non-preemption restriction. Initial state is quiescent, and the
claim ranges over all legal arrivals after arbitrary quiescent time.

There exists an online non-preemptive scheduler that is raw work conserving and
preserves all reference service prefixes for all such arrivals if and only if, for
every calendar column with nonempty owner set R,

    |B union R| <= m.                                  (2)

Empty columns impose no condition. Calendar cores are interchangeable: the theorem
does not cover affinity restrictions, migration overhead, parallel jobs, or locks.

### Necessity and a two-slot witness

Suppose a nonempty column has r=|R| and |B\R|>m-r. Select m-r+1 distinct tenants
from B\R. At the preceding slot, after sufficiently long quiescence that all token
buckets are full, release one cost-two handler for each selected tenant and nothing
else. Each admission fits its bucket and reference queue. There are at most m
ready serial handlers; raw work conservation forces every one to start. Their
first units cannot cause isolation loss, because any reference demand is from these
same ready tenants and they all run. Their second units must run in the next slot.

At that next slot, release one cost-one handler to every owner in R. These tenants
were quiescent and disjoint from the blockers, so they have full tokens, empty queues,
and zero service lead. Each gets a reference unit immediately. The m-r+1 running
blockers leave only r-1 cores for r newly urgent owners. At least one owner falls
behind. No scheduling choice avoids this. Waiting for the desired phase after a
long silent interval is legal for every finite positive token-refill period.

The witness has m+1 distinct handlers and two slots. At the failing boundary its
m+1 simultaneous compulsory unit obligations cannot be met on m cores. For this
zero-lead, two-slot forced-contention construction, fewer than m+1 distinct serial
obligations cannot give a capacity obstruction; cost two is the shortest blocking
handler. This does not assert that all possible overload witnesses in richer models
have this form.

### Sufficiency

Continue every already-running atomic handler. Let A be their distinct tenants;
A is a subset of B. Give available cores to every currently queued zero-lead
reference owner not in A, before assigning remaining cores to any other distinct
ready tenants. At a nonempty calendar column, A union R fits because it is contained
in B union R. At an empty column there is no reference obligation, and at most m
atomic handlers are already running. Thus every urgent owner can be served. The
same one-slot lead argument as in Theorem 2 preserves isolation; every idle core is
filled whenever another distinct ready tenant exists. Newly started long handlers
also belong to B, so the argument applies at the next slot. Induction proves
universal correctness. This online construction does not require future arrivals.
QED.

### Interpretation and limits

With a fully occupied calendar column, all long-capable tenants must occur in it.
Thus a full calendar that rotates more long-capable tenants than there are cores
cannot support the universal contract merely by choosing a clever work-conserving
non-preemptive policy. Upper arrival envelopes alone do not remove this obstruction:
silence restores tokens. A stricter phase-aware admission contract, preemption,
weaker isolation, or non-work-conserving waiting changes the premises. Theorem 1
still permits many finite safe long commitments when (2) fails; it uses the current
queues, leads, and next-admission timing rather than promising universal atomic
feasibility.
