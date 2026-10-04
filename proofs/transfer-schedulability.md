# Transfer schedulability: reduction, attribution, and residual obligations

## Source and scope

Willemsen, Guenzel, Brandenburg, von der Brueggen, Lin, and Chen,
*Transfer Schedulability in Periodic Real-Time Systems*, ACM TECS 24(5s),
Article 132, 2025, DOI 10.1145/3763236, and the authors' accompanying
`transfer.transfer_schedulability` and `transfer.paper_model` developments:

- https://people.mpi-sws.org/~bbb/papers/details/emsoft25/spec/transfer.transfer_schedulability.html
- https://people.mpi-sws.org/~bbb/papers/details/emsoft25/spec/transfer.paper_model.html

The checked generic development has no task assumption and explicitly quantifies
over arbitrary valid arrival sequences. The paper-model development separately
adds precedence/delay constraints, evolutions and scheduler interfaces. The
known-online-cost criterion has both a sufficiency and a necessity theorem;
using the reference-cost bound provides a sufficient criterion. These facts
must not be replaced by an assertion that the theory only covers fixed periodic
arrivals or only provides a sufficient condition.

The cited proof files were read, not compiled into this artifact. The reduction
below is a mathematical instantiation and its Python validation is independently
written. No mechanized proof assurance is inherited by this project.

The published article identifies the transfer criterion as Definition 11,
sufficiency as Theorem 12, and clairvoyant necessity as Theorem 13. The formal
companion's exact-online-cost hypotheses, rather than the fixed-period wording
of the application model, determine the instantiation used below. The source
inspection does not claim reproduction of the article's runtime mechanisms.

## 1. Embedding a CRSI execution

Fix a legal admitted continuation alpha, a tenant i, and a finite horizon H.
Both actual and reference service are FIFO and have rate at most one per slot.
Write D=q+ell for initial reference backlog. Label its work units 1,...,D in
FIFO order; append each later admitted unit in order at its actual admission
time (use a fixed tie ordering). Give every unit reference cost one. Give the
first ell initial units online cost zero and every other unit online cost one.
All initial units arrive at time zero. These zero-cost units encode work done
before the snapshot; they are never executed in the online projection.

At each slot project the physical multicore schedule to tenant i: retain its
executed unit or idle. Reference projection similarly retains the calendar's
unit if reference backlog is nonempty. This yields two ideal uniprocessor
schedules. Seriality, FIFO, common arrivals, no execution before arrival, and no
execution after completion establish the generic development's hypotheses.
The reference cost dominates online cost, including the leading zero-cost jobs.
Both schedules can be extended by idle after H for this finite comparison.
The auxiliary zero-cost jobs are a proof encoding, not zero-cost handlers in
the CRSI runtime. They are permissible in the generic development, whose cost
hypotheses do not require positivity.

Let A(h),R(h) count actual and reference work since the snapshot. In the
embedding, the completed job labels at boundary h are exactly the first
ell+A(h) online and first R(h) in the reference, respectively. Therefore

  (forall h <= H: ell+A(h) >= R(h))
      iff
  (forall unit jobs j, h <= H: ref_complete(j,h) -> online_complete(j,h)).

Proof: if the inequality holds, every reference-completed label is among the
online-completed labels. If it fails, label ell+A(h)+1 is reference-complete but
online-incomplete. This argument covers initial lead, not just empty starts.
Apply it separately to every tenant. Projection does not create a globally
feasible schedule; physical capacity and seriality must already hold. Thus
"multicore rather than uniprocessor" is not by itself a new isolation result.

Since alpha was arbitrary, universal CRSI is the conjunction of these transfer
properties over all legal alpha and all tenants. The universal arrival-sequence
parameter in the existing theorem permits these instantiations. It does not,
by itself, give an efficient representation or decision procedure for a
state-dependent set of continuations.

## 2. Specializing the exact slackless criterion

The generic critical set at (t,d), t<d, consists of jobs completed by d in the
reference but not by t online. With known online unit costs, every critical job
has remaining cost one. Its cardinality is

  M(t,d) = max(0, R(d) - ell - A(t)).

The zero-cost leading jobs are already complete and do not enter the set.
A slackless interval has M(t,d)=d-t. The exact criterion requires the online
projection to execute one of these critical jobs at t. FIFO implies that any
productive service at t, when M(t,d)>0, executes the earliest such unit.

For completeness, the finite specialization can be proved directly. If prefix
isolation holds and a slackless interval is idle at t, the remaining d-t-1 slots
cannot complete its d-t unfinished units, contradicting isolation at d. In the
reverse direction, take the first violating boundary d. In slot t=d-1 the
reference executes, actual does not, and the previous lead is zero. Thus its
critical set has cardinality one, [t,d) is slackless, and the criterion fails.
This is a specialization of the existing transfer theorem, not a new general
slackless-interval theorem.

Checking original handler completion alone is weaker: one cost-two handler with
reference service (1,0,1) and actual service (0,1,1) finishes at time three in
both schedules but violates work dominance at time one. Unit-job refinement
removes this distinction. It is not a reason to claim the existing theorem
cannot express prefix isolation.

## 3. What still needs a model-specific proof

Fix a plan that serves only the work already present: total Y_i(H)<=q_i.
With C_i(h) the calendar opportunities, the retained theorem proves that
universal transfer of every unit job is equivalent to excluding all pairs (i,s)
with

  C_i(s+1) > ell_i+Y_i(s+1)
  and (Y_i(s+1)<q_i or s>=e_i),

where e_i=1 if a token exists and e_i=r_i otherwise.

The nontrivial extra step is eliminating the continuation quantifier, not
introducing reference-relative isolation. Generic slacklessness is evaluated
for a realized reference schedule R^alpha, whereas the above test uses calendar
opportunities C and the snapshot. Merely replacing R by C is conservative and
can reject legal safe plans. Merely checking alpha=0 is unsound for unknown
arrivals. The backlog restriction, reference-based admission and drain-before-
witness argument establish an exact middle ground.

The retained proof has two indispensable cases. If Y<q, no-arrival reference
service min(q+ell,C) already exceeds ell+Y. If Y=q and C>q+ell, the reference has
drained all initial work by the beginning of s. Provided s>=e, one token and
one unit of headroom exist; a single arrival at s produces a violation. If the
producer places this unit at an earlier legal slot, it is also served by s.
Conversely, any first violation with Y=q requires at least one future unit by s,
hence s>=e. This proves the zero/one witness and the exact finite scan. The
proof is recorded in full in model-and-results.md and the main manuscript.

The source transfer theorem supplies the semantic property and per-trace
criterion; it does not state this CRSI monitor abstraction, sparse witness, or
O(n+m(P+H)) validator. Their proofs use extra hypotheses and are presented as
model-specific derivations, not as a claim that they cannot follow from a more
general formal theory. No exhaustive priority claim across all literature is
made.

### Exact monitor abstraction (corollary, not an additional independent invention)

For valid snapshots with identical (calendar, phase, q_i, ell_i, e_i), the set of
accepted current-backlog-only plans and every earliest failure pair coincide,
even if buffer capacities, bucket sizes, token counts, later refill periods and
later arrivals differ. This follows by substitution into the exact test.
Witness legality is checked against each concrete monitor separately.

This is property-specific equivalence, not a bisimulation of the monitors.
For example, use q=ell=0, one unit of buffer and bucket capacity, one token
initially available, a calendar serving the tenant every slot, and next refill
one. Compare refill periods one and two. Both monitors have e=1. The stream
admitting one unit at offsets 1 and 2 is legal only for the period-one monitor:
after the token is used at 1, the period-two monitor does not refill until 3.
Both monitors nevertheless classify every eligible current-backlog-only plan
identically.

Dropping the fixed-current-backlog restriction invalidates a general sparse
reduction. Consider a single tenant with q=ell=0, a unit reference opportunity
every slot, bucket and buffer capacity two, two initial tokens, and no refill
within a three-slot horizon. A reactive controller serves the first unit that
arrives, whenever that occurs, but no further units. It is safe for every legal
zero/one-unit input in this horizon. Two units arriving at offset 1 make the
reference serve in slots 1 and 2, but the controller serves only in slot 1. The
failure requires two arrivals. This controller is outside the fixed-plan
contract; it relies on work not present at the snapshot. The example delimits
the reduction, not the generic transfer theorem, which detects its violating
execution correctly.

## 4. Online dispatch and atomic policy existence

At a safe snapshot, a reference owner with positive actual backlog and zero
lead must be served this slot; omitting it creates a unit-job transfer failure.
Serving every such owner is also sufficient for one-slot safety. This is the
one-slot specialization/induction underlying the inherited urgent-first rule.
The ready mandatory owners fit because the calendar is feasible. Filling other
cores proves capacity-aware work conservation. FIFO handler completion and its
calendar-based delay bound are corollaries, not separate transfer innovations.

Non-preemptive handlers couple successive unit jobs: after a handler starts,
its remaining units are mandatory even when they are not currently critical.
The reduction above still characterizes the safety of an actual execution but
does not construct a resource-feasible atomic policy. For B={i:min(H_i,b_i,Q_i)
>=2}, the retained theorem proves feasibility of one causal, raw work-conserving
policy for every legal input exactly if |B union R|<=m for every nonempty
calendar column R. Its necessity uses a two-slot arrival adversary after a
quiet interval: m-|R|+1 cost-two borrowers outside R must start, then |R| new
owners must receive service, demanding m+1 distinct tenants. Sufficiency uses
running-set A subset B, serves urgent owners, and fills spare capacity.

The existence and adversarial-necessity argument is a separate model-specific
obligation. The sufficient service invariant is inherited from the unit-job
transfer specialization. Neither the union cardinality calculation nor the
invariant alone is presented as a general new non-preemptive scheduling theorem.

## 5. Attribution summary

- Reference-relative guarantee: prior concept, instantiated here.
- Prefix-work observable: equivalent to transfer on FIFO unit jobs, with an
  explicit proof encoding for initial lead.
- Serial multicore setting: tenantwise projection; global capacity still checked.
- Unknown arrivals: allowed by generic theorem; monitor quantifier elimination
  is the residual algorithmic obligation.
- Urgent-first service and FIFO completion: specialization/corollaries.
- Current-backlog-only certificate and zero/one witness: model-specific exact
  reduction; separately proved and tested against the prior criterion.
- Monitor sufficient statistic: corollary of that reduction, not a new main result.
- Atomic universal existence boundary: separate causal-policy feasibility proof;
  service invariant inherited, necessity uses an extra nonpreemption argument.
- Runtime implementation correctness: testing only here; no Rocq-to-Python
  refinement or hardware result is asserted.
