## Problem and approach

Requests could return undeclared tool names or schema-invalid JSON even when the
request provided tools or a response format. Combining tools and JSON constraints
also exposed a mask-width mismatch on Metal.

This builds on ncphri's upstream work (#3800 and #4222), which provide the
original constraint implementation. This branch adds:

- Metal integration for token masks and speculative verification.
- Persistent declared-name protection across prose and multiple tool calls.
- Fixes for mask-width composition and the thinking-to-JSON boundary.
- Request-driven activation without additional enabling ENV variables.

The architectural reference is llama.cpp: constrain tokens before emission, then
stream accepted output. Identical behavior in every case is not claimed.

This branch now rebases those fixes onto **upstream `v0.2.12`** and is published
as the signed fork release **[v0.2.12-p1](https://github.com/tuhochi/Strata/releases/tag/v0.2.12-p1)**
(Apple Silicon, macOS 15+, engine `0.1.58.1-metal`). It is installable on any
Apple Silicon Mac via:

```sh
sh - "$(curl -fsSL https://raw.githubusercontent.com/tuhochi/Strata/v0.2.12-p1/fork/install-fork.sh)"
```

## Verification (this release, no regressions)

All runs use a private bundled Python runtime; no model or live Strata service
was started on the builder. The full corpus passes with zero failures; suites
overlap, so counts are not summed as unique tests.

| Suite | Passed | Skipped | Failed |
| --- | ---: | ---: | ---: |
| Terminal / setup / tools / fork corpus (main + TUI walk) | 4,881 | 108 | 0 |
| Server, pinned minimal Python runtime | 1,576 | 14 | 0 |
| Automatic constraints, no mask ENV | 90 | 2 | 0 |
| Constraints with optional jsonschema | 92 | 0 | 0 |
| App host, Node 24 | 1,503 | 110 | 0 |
| Signed ARM installation checks | 13 | 0 | 0 |
| CPU native diagnostics (builder) | 93 | 4 | 0 |

- Full corpus: 4,989 collected tests, 0 failures. TUI walk: 11 tests, 90 subtests.
- Server suite previously reported failures; a fully passing run is now recorded
  (1,576/1,590). The earlier partial failures were a test-environment issue, not a
  regression in these constraints.
- CPU native diagnostics: 93 passed, 4 skipped (missing external packs), 0 failed.
- Synthetic Metal probe on an Apple M1 Ultra ran `runtime_hello` and passed; it
  does not execute a real model.

Full results, exact commands, snapshots and CI links:
[REGRESSION-VALIDATION.json](https://github.com/tuhochi/Strata/blob/v0.2.12-p1/releases/v0.2.12-p1/REGRESSION-VALIDATION.json)
and [installation checks](https://github.com/tuhochi/Strata/blob/v0.2.12-p1/releases/v0.2.12-p1/INSTALLATION-VALIDATION.json).

## Historical real-model measurements (p3, not this release)

The latency/benchmark table below is from an earlier p3 integration and is **not**
a measurement of this `v0.2.12-p1` release. It is kept for history only:

| Check | Unpatched | Patched |
| --- | ---: | ---: |
| Undeclared tool names — targeted stress | 10/10 | 0/10 |
| Undeclared tool names — additional variants | 3/5 | 0/5 |
| JSON stress cases passing | 3/10 | 9/10 |
| Tools + JSON integration cases passing | 0/3 | 3/3 |

Across 113 requests ordinary control outputs were unchanged; warm median latency
changed by +0.4–0.7% for tool workloads and −0.7–+2.5% for JSON workloads. See
the [historical p3 measurement doc](https://github.com/tuhochi/Strata/blob/07544207d16993c31f5dda2067b2c0671b33be40/fork/evaluation/P3-HARDWARE-20261106.md).

## Remaining limits

- `uniqueItems` is not enforced; it makes `llguidance` compilation fail and the
  existing fallback drops the mask. `llama.cpp` behaves the same. No stricter
  runtime JSON rejection was added.
- CUDA, HIP and SYCL builds and GPU hardware execution are not included.
- Real-model acceptance requires manual installation and restart on the owner's
  Mac; none was run on the builder.
- Apple Silicon macOS 15+ only; Intel Macs are not a target of this fork release.

## Upstream CI

This is a fork pull request. GitHub does not run workflow checks on fork PRs until
the repository maintainer approves them, so **no CI checks have run yet** on head
`0c622181`. Merge approval and the subsequent CI run require a maintainer. The
constraint logic upstream is credited to ncphri (#3800, #4222).
