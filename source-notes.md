# Scientific sources and transfer comparison

## What is attributed

Reference-relative preservation is not introduced by this project. Willemsen,
Günzel, Brandenburg, von der Brüggen, Lin and Chen, *Transfer Schedulability in
Periodic Real-Time Systems*, TECS 24(5s), Article 132 (2025), DOI
10.1145/3763236, is the central theoretical source. Its generic formal companion
is available at:
https://people.mpi-sws.org/~bbb/papers/details/emsoft25/spec/transfer.transfer_schedulability.html

The task-free core explicitly permits arbitrary valid arrival sequences and
separate reference/online job costs. Exact-online-cost necessity and sufficiency
are inspected at their definitions, hypotheses, proof argument and final theorem
statements. The paper-level model is distinguished from this generic core.
The inaccessible ACM and MPG full-article endpoints are not credited as a full
25-page reading. No upstream artifact or Rocq proof was built or executed.

## Explicit reduction, not a terminology-based distinction

`proofs/transfer-schedulability.md` proves that cumulative work dominance is
completion transfer on FIFO unit milestones. Nonzero initial lead is represented
by leading reference-cost-one/online-cost-zero jobs. Serial tenants allow
projection from a feasible multicore execution; capacity validation is not
provided by that projection. The universal arrival parameter admits monitor-legal
continuations. Consequently cumulative work, unknown arrivals and multiple cores
are not claimed as independent theoretical separations.

The residual model-specific obligation is exact elimination of the continuation
language for current-backlog-only plans. The drain-before-witness proof gives a
zero/one-unit witness and linear scan; the monitor statistic is a corollary.
Urgent-first service and FIFO completion are specializations. Atomic feasibility
additionally proves one causal work-conserving policy exists for all inputs,
using a separate nonpreemption capacity argument. The mathematical comparison
closes that attribution question, not priority over every publication.

## Other sources and reading extent

IX is the retained fully inspected substantive historical source: OSDI 2014,
pp.49–65, architecture/batching/protection, Section 4.1 allocation-policy boundary,
and evaluation limitations. No IX measurement or protection theorem is inherited.
Shenango and Caladan are used at their official description level for core
reallocation motivation. Offline Equivalence is used only at the inspected reference/model level. Exact
non-preemptive analysis and semi-partitioned reservations have now been read in
full; the additional TPDS global-interference paper has a full accepted-manuscript
reading. Their distinct premises are reflected in the manuscript. SPR is
compared for reservation-management mechanisms and its different overhead scope.
Semi-partitioned reservations, global non-preemptive response-time analysis,
strong/weak sustainability, Prosa and RefinedProsa support narrowly stated model
and assurance comparisons. Entry-specific locations and metadata are recorded
in the paper-side citation audit and `external_resources.csv`.

No partially inspected paper or abstract is counted as a full calibration item.
The separately requested 12/5/5 full-paper calibration is not complete:
1/12 TPDS, 1/5 influential, 2/5 adjacent, with no overlap credit.
The full-reading matrix is `literature-calibration.md`; it distinguishes accepted
PDFs from final publisher layouts and records the actual scope of each reading.
The remaining calibration concerns source-reading coverage; the supplied
reduction already expresses work prefixes in Transfer Schedulability.

## Reuse

No external scientific code, data set or solver is integrated into the runnable
artifact. The independent transfer interpretation is written for this project
and uses the generic predicate as a specification. External PDFs and proof code
are not redistributed. The exact consumed experimental inputs are the deterministic
generators, neutral cases, transfer protocol and complete per-case JSONL records.
Finite experiments run offline without fetching any literature.

Continuous execution uses the inherited transfer invariant and fixed-plan
prefix closure. Its interruption proof in `proofs/continuous-execution.md` is
labelled a composition corollary, not a newly discovered scheduling principle.
