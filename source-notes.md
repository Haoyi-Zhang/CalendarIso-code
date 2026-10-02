# Scientific source notes and comparison boundary

Read-state labels are literal: retrieving a PDF address is not a full read. No
unavailable or partially read paper is counted as a full calibration paper. The
external resource ledger supplies scholarly/official addresses and access dates.
These notes retain source attribution, not private coordination material.

## IX: full substantive historical source

Adam Belay, George Prekas, Ana Klimovic, Samuel Grossman, Christos Kozyrakis and
Edouard Bugnion, OSDI 2014, pp. 49–65. Author order and historical affiliations
appear on the first substantive page. All substantive sections and the relevant
PDF figures/tables were inspected; no source-system experiment was reproduced.

Precise passages: Section 3 describes coarse control-plane provisioning and
bounded batches; Section 4.1 explicitly leaves allocation policies to future work
and describes dedicated elastic threads; Section 4.4 discusses ownership and
protection; Section 5 evaluates actual networking/application implementations;
Section 6 lists implementation limitations and future dynamic-resource work.
The paper's general interrupt-control discussion and later prototype caveats must
not be compressed into a blanket claim that fine-grained preemptive sharing was
implemented. Legitimate reuse is the architectural motivation and those qualified
source facts. The present reference calendar, ghost/reference queue, universal
arrival quantifier, proofs and Python validation are new project work, not IX
results. Its measured speedups are not evidence for this project.

## Transfer schedulability: indispensable unresolved comparison

The author publication records identify Lars Willemsen, Mario Günzel, Björn
Brandenburg, Georg von der Brüggen, Ching-Chi Lin and Jian-Jia Chen, *Transfer
Schedulability in Periodic Real-Time Systems*, TECS / EMSOFT 2025, DOI
10.1145/3763236. ACM full text and a retrieved MPG repository component returned
403 responses in this session. The article is not recorded as fully read.

Its primary Prosa companion source explicitly defines preservation as no job
finishing later than in a reference. In the ideal uniprocessor formalization,
critical jobs and slackless intervals yield a transfer criterion. The generic
formal core is not restricted to periodic tasks, even though the article title
mentions them. We cannot claim originality of reference-relative preservation or
of an exact transfer condition. We inspected the central formal definitions and
statements, but did not execute or independently verify the upstream mechanization.

Candidate delta, not a novelty certification: this project demands work-prefix
dominance (stronger than final job completion), universally quantifies unseen
stateful token-admissible arrivals, checks a fixed known-backlog multicore plan,
and characterizes universal atomic feasibility using possible long handlers. A
complete comparison to the full published mechanism, reclamation literature and
other strongest work is still required before claiming a worthwhile new paper.

## Other partial sources

Selected passages of Offline Equivalence concern recreating an offline
non-preemptive table with an online mechanism and include a hardware evaluation.
This project neither recreates that implementation nor equates table recreation
with prefix-service dominance. The author-hosted listing records an RTAS 2017
Outstanding Paper Award, but without a full read it earns no award-calibration
credit here.

Shenango, Caladan, SigmaOS, SPR, exact non-preemptive analysis and two TPDS sharing
papers were located but not fully read. Their titles are comparison candidates,
not evidence that a research gap exists. A search candidate called
*Non-Preemptive Real-Time Multiprocessor Scheduling Beyond Work-Conserving* is RTSS
2020, not TPDS. No title-only source or abstract counts toward the required sample.

Completed calibration count: 0 of 12 TPDS, 0 of 5 influential/award, 1 of 5
adjacent full papers. No overlap is credited. This remains a scientific-readiness
hold, not merely a formatting task.

## Reuse and exact inputs

No external scientific code, workload or solver is integrated into the runnable
artifact. The consumed scientific inputs are original deterministic generators
and explicit toy cases, retained locally. Public source papers support the
historical comparison, not the finite result counts. Their exact PDF bytes are
not redistributed because broad redistribution permission was not established.
The local artifact reproduces its own mathematical finite checks without fetching
any literature. It does not claim to reproduce the external systems or preserve
a complete mirror of the literature corpus.
