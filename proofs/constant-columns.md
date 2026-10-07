# Constant-column run-length admission

Use the unchanged snapshot and event order in `model-and-results.md`. The
proposed run repeats one valid multicore column for L positive slots. Every
selected tenant has at least L units already queued; selected tenants are
distinct. Idle and charged-overhead entries are permitted but do not serve work.

For each tenant i, index its reference positions within one phase-aligned period
as r_i[0] < ... < r_i[v_i-1]. A serial reference has at most one opportunity per
tenant in a slot. A selected tenant receives one unit every slot, hence its
actual service plus nonnegative initial lead always dominates its reference.

For an unselected tenant, actual committed service is zero. If v_i=0 it cannot
fail. Otherwise write initial lead ell_i = a*v_i+b. The first reference
opportunity whose cumulative count exceeds ell_i is c_i=a*P+r_i[b]. A queued
tenant can fail there with no future arrivals. An empty tenant can fail only
at a reference opportunity at or after both c_i and its first future-token
offset e_i. Since cumulative opportunity count is monotone, the earliest such
opportunity is obtained by one quotient/remainder and lower-bound lookup in
r_i. The exact fixed-plan theorem proves necessity and sufficiency of this
condition. Taking the smallest (offset, tenant) gives the same first failure
as expanding all L columns.

An empty tenant's one-unit witness is released at e_i unless its reference
buffer initially equals capacity. In that case the first reference service
creates headroom, so release is delayed until the following slot. The failing
opportunity is strictly after the initial lead opportunities. Capacity is
positive, so this delay cannot pass the reported failure. The token is retained
by saturation until that release. This is the same witness convention as the
explicit-column producer, including lexicographic ties.

Calendar and snapshot validation plus indexing take O(n+mP) arithmetic
operations; successor lookups take O(n log P). Storage is O(n+mP). L changes
integer widths but not the number of scanned slots: arithmetic bit complexity
still depends on the encoded magnitudes. This applies to constant-column runs,
not arbitrary changing plans or online arrival-reactive policies.

`tests/test_constant_columns.py` compares all 7,776 declared small cases,
including idle runs, phase rotation, unavailable tokens and full buffers.
`constant_campaign.py` adds 2,000 deterministic random cases and one encoded
10^12-slot case. The paired elapsed-time study retains nine alternating pairs
on all twelve declared configurations. The long safe runs have large initial
lead by construction; their speed ratios are admission-kernel measurements,
not production dataplane throughput or a scheduling advantage over urgent-first.
