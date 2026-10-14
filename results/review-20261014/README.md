# Current bounded candidate evidence, 2026-10-14

This folder is a new receipt, not a replacement for any historical result.
`normal/` and `optimized/` contain complete current reproductions with all 59
tests, 66,858 core instances, 32,766 transfer instances, 2,880 execution histories,
720 malformed-log rejections, compact admission, and same-input workflow costs.
Large JSONL inputs/results are losslessly gzip-compressed during packaging.
Decompress a copy for consumers requiring an uncompressed pathname. Raw decoded
histories and all deterministic record characters (apart from host newline)
match the original evidence. Timing is not an equality target.

The primary paper timing source is `normal/workflow-cost/summary.json` from the
first complete full-output run of the final code, not a selected best run:
120 identical inputs, three alternating pairs, 720 full measured model outputs,
all work ties, elapsed ratio 6.126584219933761 (range 3.34585860299419 to
8.882151374763563), aggregate sampled CPU ratio 6.523076923076923. The optimized
rerun is a robustness/reproduction check, not a new workload population.
Earlier local summary-only timings are retained privately and do not replace
this current primary raw-output measurement.

The comparator is the owned urgent-first CPython scheduler with exactly the same
information/admitted stream and common validation/replay/serialization costs.
Certification additionally pays for proposals and its existing independent
sparse checker. Disk I/O is untimed. Process CPU samples are aggregated because
short Windows observations may round to zero. No physical cost is charged to
discrete model slots. No native OS/dataplane, IX, upstream transfer runtime,
device, concurrent commit or crash-recovery implementation was run.

`red/` retains two controlled inconsistent-oracle regressions that passed wrongly
under -O before the fix, plus the original successful 52-method coverage within
the failing 54-method red suite. Resource/oracle stubs exist only in owned tests;
they are not research measurements. `failed-first-attempt.txt` preserves the
first Windows reproduction's CRLF/LF mismatch instead of relabeling it success.

Current host: CPython 3.12.14, Windows 11 build 28000, verified process affinity
mask 1, one child at a time, 42-second child wall deadlines. Linux CPU/address
space limits, child CPU totals and Linux RSS are unavailable and recorded null.
The original Linux-enforced default remains; portable mode is explicit.

Safe reproduction from the flat artifact root, using NEW empty output paths:

```sh
python -B reproduce.py --portable --output-dir fresh-normal
python -B -O reproduce.py --portable --output-dir fresh-optimized
# Linux: omit --portable for enforced CPU/address-space limits.
```

No scientific acceptance is asserted. Main installation, public CI/sync,
human-independent proof/code review, native integration and venue/fulltext
completion remain open. See the private P036 handoff for full read scope,
exact commands, hashes, before/after delta and PDF QA.
