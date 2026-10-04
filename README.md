# Isolation-preserving work-conserving schedules

A standalone research artifact for Calendar-Relative Service Isolation. It contains
mathematical derivations, exact scheduling oracles, certificate producers/checkers,
an independent unit-job transfer interpreter, continuous model execution and
full-log replay, and finite regression evidence. It
requires no paper directory, private data, external service, device, solver, or
downloaded dependency. The separately supplied main manuscript is an internal
research draft, not a submitted or externally certified TPDS publication.

## What is established in the stated model

`proofs/model-and-results.md` gives the model and complete prose arguments.
`proofs/transfer-schedulability.md` establishes the exact relation to Willemsen et
al. (TECS 2025): the isolation property and per-trace invariant are inherited
unit-job specializations; the contribution under examination is the model-specific
quantifier elimination and atomic-policy feasibility argument. Results include:

- exact admission of a supplied finite multicore service commitment against every
  admissible future work arrival, with an earliest zero/one-arrival witness;
- a compositional urgent-reference-first, unit-preemptive work-conserving policy,
  plus FIFO completion/nonstarvation implications for positively reserved tenants;
- an iff universal atomic-handler boundary and a two-slot capacity witness.

These are mathematical arguments, not proof-assistant-checked general theorems.
Finite executable checks corroborate the statements on their recorded domains.
All algorithms and checks were written by the same AI research executor; separate
implementations and clean reruns are not independent human review.

## Reproduce from a clean extraction

Requires Linux and Python 3.10 or later with its standard library. The minimum
syntax requirement is 3.10; only the available interpreter was actually executed.
No dependency installation or network access is required.

```sh
python reproduce.py
```

This runs the three retained exact pilots, the additional 32,766-case transfer
comparison, 18 retained contract tests, 12 transfer-specific tests, 14 runtime
tests, and the complete 120-input / 2,880-run continuous campaign in five shards. It checks
all deterministic scientific fields, every transfer record, all runtime inputs
and run rows, and the decoded full execution histories. Independent aggregation
replays all 2,880 logs before the structured summary is printed. Temporary fresh outputs are deleted by default; retained evidence is not
modified. One child runs at a time, pinned to one available CPU. Each child is
bounded by a 42-second wall timeout; the three pilots additionally use 35/40 CPU
second limits and a 3 GiB address-space limit. The project requires enough memory
for both the runner and one child; recorded use is in `results/reproduction.json`.

To retain fresh measurements, use an empty, separate output directory:

```sh
python reproduce.py --output-dir fresh-results
```

Expected main enumeration counts are **31,590**, **35,152**, and **116**, with no
producer/oracle disagreement. The tests additionally use 300 fixed-seed general
plan instances and metamorphic checks; they are not added to a misleading single
"workload count." Timing and peak RSS may vary. No statistical performance claim
is inferred from these CPU measurements.

Individual checks:

```sh
python src/pilot.py --output-dir fresh-single
python src/plan_pilot.py --output-dir fresh-plans
python src/atomic_pilot.py --output-dir fresh-atomic
python tests/test_contracts.py
python tests/test_transfer.py
python tests/test_runtime.py
python transfer_campaign.py --output-dir fresh-transfer
python runtime_campaign.py --family steady --output-dir fresh-steady
python runtime_summary.py --replay-all
python export_runtime_tables.py > runtime-tables.tex
```

Each named output directory may be created by its individual program. The top-level
reproducer intentionally refuses to overwrite the retained `results/` directory.

## Model and event order

A column in a periodic reference calendar has one entry per interchangeable core.
A nonnegative entry is a tenant; `-1` is unreserved. No tenant can use two cores in
one slot. A fixed plan uses the same format and additionally permits `-2` for an
explicitly charged overhead slot. Plans cannot depend on future work: the total
service assigned to a tenant is at most its current actual backlog.

For each tenant, `backlog` is actual queued work, `lead` is actual-minus-reference
cumulative service, `capacity` bounds the reference queue, `tokens` is the current
admission balance, `bucket` its capacity, `period` the time between one-token
refills, and `refill` the next positive refill offset. The reference queue equals
`backlog + lead`. Snapshot offset zero is **after arrivals**. Future slots first
refill, then admit, then execute actual and reference service. Admission consumes
work tokens and **reference-queue** headroom, making the input stream independent
of the tested schedule. This is not the usual implementation-dependent actual
queue admission rule.

The monitor must own and trust the snapshot, enforce per-tenant namespace/queue
ownership and exact progress, and obey the event order. These mechanisms are
assumptions, not proved security properties. Integer work, serial FIFO tenants,
known costs, no affinities, no suspensions/locks and no uncharged scheduling costs
are essential. The atomic theorem compares a non-preemptive implementation to a
unit-granularity reference and permits every job cost in `1..H_i` that admission can
accommodate. It does not compare two arbitrary non-preemptive schedulers.

## Inspect or use the implementation

`src/commitment.py` is the general producer. `src/plan_oracle.py` has independently
implemented state transitions, a full admission-amount DP, a joint-arrival oracle
and a sparse-replay checker. The checker relies on the proved zero/one-arrival
reduction; the full DP does not. Neither imports the producer. The atomic game in
`src/atomic_oracle.py` alternates all legal FIFO arrival compositions with all
work-conserving scheduler choices over the stated finite horizon.

Example, with the repository root as current directory:

```python
import sys
sys.path.insert(0, 'src')
from admission import Tenant
from commitment import Snapshot, certify_plan
from plan_oracle import check_certificate

snapshot = Snapshot(((0,), (1,)), 0, (
    Tenant(2, 0, 2, 0, 1, 3, 3),
    Tenant(0, 0, 1, 1, 1, 3, 3),
))
plan = ((0,), (0,))
certificate = certify_plan(snapshot, plan)
assert certificate['first_failure'] == [1, 1]
assert check_certificate(snapshot.to_dict(), plan, certificate)
```

`admission.py` and `oracle.py` retain the simpler single-core experiment. Its
`replay_witness` routine is an independent, strict checker for a *rejected
certificate's explicit prefix through the declared first failure*. It validates
serialized state, exact integer (not Boolean) fields, certificate structure and
arrival legality on that prefix. It does not validate a safe verdict, prove global
minimality or replace the exhaustive and zero/one-arrival oracles. Core algorithm routines assume finite caller-supplied dimensions;
resource enforcement is provided by the measured runners, not arbitrary unlimited
API calls. `choose_atomic` assumes valid, monitor-owned queue state.

## Transfer-criterion interpretation and exact records

`src/transfer_oracle.py` imports neither `commitment` nor any earlier checker.
It validates a FIFO unit-job trace, including strict integer metadata, initial
zero-cost lead jobs, release counts and no repeated/unreleased/non-FIFO execution.
It evaluates the exact known-online-cost critical-interval predicate using job
identities. Its domain is the unit-job embedding, not arbitrary task traces.
`tenant_traces` assumes joint snapshot/plan validation, which
`certify_by_transfer` performs. Direct low-level callers must respect that boundary.

`inputs/transfer-protocol.json` specifies selection before the campaign.
`results/transfer/cases.jsonl` contains all 32,766 snapshot/plan records and outcomes.
`results/transfer/summary.json` records 131,410 full tenant paths, 885,822 intervals,
zero mismatches, 1,586 zero-arrival false accepts and 2,386 saturated-calendar
false rejects. Those controls are not the prior authors' runtime algorithms.
The 14,688 repeated abstraction-key comparisons preserve verdict and earliest
failure, not necessarily the serialized witness or full arrival language.

The implementation is original executable interpretation, not upstream code,
SPT runtime, Rocq extraction, or mechanized refinement. The additional cases are
kept separate from the original 66,858 cases and the 300 seeded regression plans.

## Continuous execution and observable limits

`src/runtime.py` executes repeated refill, common reference-gated admission,
proposal, certification, prefix execution and resnapshotting without resetting
lead. Proposals use only current backlog. The six policies are reservation-only,
urgent-first, naive batching, zero-future-arrival snapshot checking, exact immutable
certification, and exact certification with readiness-triggered interruption.
`proofs/continuous-execution.md` proves the latter's composition under unit-slot
preemption and zero checking/observation/switching cost.

`src/runtime_replay.py` has no scheduler, producer, or checker imports. Its contract
is a **complete finite execution** for an external offer stream, unlike the
single-core checker's **declared rejected prefix**. A legal unsafe log is accepted
and reported as unsafe; illegal suffixes and truncated histories are rejected.
The replayer does not authenticate a policy label or instrumented proposal counts.
Low-level APIs require bounded caller input; the runner enforces campaign limits.

`inputs/runtime-protocol.json` fixes five families, eight evaluation seeds, three
layouts, four batches and six policies. Development seeds are separate. All 120
inputs, 2,880 run rows, and full histories are retained by family in
`results/runtime/`; gzip is storage compression only. `runtime_summary.py` verifies
the full protocol grid and reconstructs every history. No run is excluded for a
negative outcome. The primary table is batch four; all other batches remain
reported. This is not production-distribution inference or an optimality study.

Safe immutable batches need not be work conserving: the primary evaluation records
1,211 avoidably idle core slots. Interruption records zero, but requires observing
every slot. Its proposal reduction is not a CPU-cost measurement. No queue admission
is altered to help a policy, and unsafe controls retain excess actual backlog
rather than silently dropping work. Recorded unit-delay sums are right-censored by
unfinished work; they are not used alone to claim latency improvements.

`export_runtime_tables.py` emits the manuscript's two data tables from the checked
summary. The standalone artifact does not require or write the paper directory.
The generator seed convention is recorded and exact generated inputs are supplied;
cross-version Python PRNG equality is checked, not assumed. All policies can also
be replayed directly against the retained exact inputs.

## Evidence and limits

`claim_evidence_ledger.csv` maps each result to the proof, checker, raw record and
maturity. `external_resources.csv` and `source-notes.md` distinguish fully read,
partially inspected and inaccessible literature. External PDFs and unexecuted
upstream code are not redistributed. The exact synthetic inputs are deterministic
generators and the neutral cases in `inputs/`; there is no unseen cache.

`results/atomic-pilot.json` retains every atomic game result. The other pilot files
record exact enumeration domains, aggregates and representative sparse witnesses.
Generated-instance counts are theorem-validation coverage, not practical workload
breadth, and zero failures do not prove the general statements or prove novelty.
The explicit comparison to the generic transfer theorem is in the proof record:
initial-lead embedding, critical-interval equivalence, monitor abstraction and its
non-bisimulation counterexample, and a reactive-policy counterexample to an
unrestricted sparse-witness claim. The full-paper 12/5/5 calibration and broader
priority assessment are not certified. Only zero-overhead model-execution outcomes are reported, not systems performance. No packet, production RPC,
NIC, kernel-bypass, real-time device, bandwidth or tail-latency advantage is claimed.

The scientific novelty/venue gate remains open. The standalone repository does
not depend on paper-side files; a separately packaged main manuscript may describe
these results, but its existence does not certify overall publication priority, venue-policy
compliance, or a deployed systems result. The repository must not be
advertised as an independently reviewed, deployment-ready or published system.
Scientific scope limits and the distinction from independent external validation are stated in the manuscript and proof supplement. Upstream rights and licenses remain unchanged.
