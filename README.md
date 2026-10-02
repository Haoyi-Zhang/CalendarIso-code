# Isolation-preserving work-conserving schedules

A standalone **research evidence checkpoint**, not a completed or submitted TPDS paper.
This repository contains original mathematical proofs, small exact scheduling
oracles, certificate producers/checkers, and bounded finite tests. No paper source,
private data, external service, device, solver or downloaded dependency is required
to run it. Publication novelty and systems significance remain unresolved.

## What is established in the stated model

`proofs/model-and-results.md` gives complete prose arguments for:

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

This runs the three exact pilots and 18 contract-test methods, checks fresh results
against all retained deterministic scientific fields, and prints a structured
summary. Temporary fresh outputs are deleted by default; retained evidence is not
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
A longer-running systems simulation study, current strongest-work comparison and
the specified journal calibration remain unfinished. No packet, production RPC,
NIC, kernel-bypass, real-time device, bandwidth or tail-latency advantage is claimed.

The scientific novelty/venue gate remains open. The standalone repository does
not depend on paper-side files; a separately packaged main manuscript may describe
these results, but its existence does not close the literature or systems-evidence
hold. The repository must not be
advertised as an independently reviewed, deployment-ready or published system.
See `PROVENANCE.md` for substantive AI contribution and external-use conditions.
