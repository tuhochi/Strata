# P1 (v0.2.12-p1) regression verification

Release `v0.2.12-p1`, engine `0.1.58.1-metal`.
Fork base: upstream `v0.2.12` (`146df3c468739147f520ac3816de806f71232571`).
Build source: `8e610b8fd2f810226b6877bb14485ca342fcd6a2`.

`v0.2.12-p1` rebases the p5 fixes onto a fresh upstream `0.2.12` base and keeps
the fork's three tool/JSON constraints. An earlier generation-header assignment
discarded parallel request identifiers; `p1` preserves them for `GEN` and `GENI`,
including image requests. The `Responses` namespace fix and automatic
declared-name masking work without `STRATA_TOOL_MASK`. The speculative-generation
merge preserves both the mask boundary and upstream's forced-continuation
log-probability handling. The original tool/JSON work is credited to the upstream
contributions behind
[PR #5398](https://github.com/Niko1221/Strata/pull/5398).

The fork rebase was validated against the same corpus used for the earlier
patches, with no regressions. The Python corpus is collected into independent
main and TUI-walk runs; the suites overlap, so their counts are not added as
unique tests. Seven files in the signed archive match the tested source byte for
byte, and the committed payload export gate passes with both tested Git
line-ending settings.

| Suite | Passed | Skipped | Failed |
| --- | ---: | ---: | ---: |
| Terminal, setup, tools and fork corpus (main + TUI walk) | 4,881 | 108 | 0 |
| Server, pinned minimal Python runtime | 1,576 | 14 | 0 |
| Automatic constraints, no mask ENV | 90 | 2 | 0 |
| Constraints with optional jsonschema | 92 | 0 | 0 |
| App host, Node 24 | 1,503 | 110 | 0 |
| Signed ARM installation checks | 13 | 0 | 0 |

The Python corpus is 4,989 collected tests, split into independent main and
TUI-walk runs (TUI walk reports 90 subtests). CPU native diagnostics run on the
builder: 93 passed, 4 skipped, 0 failed. A synthetic Metal probe on an Apple M1
Ultra ran `runtime_hello` and passed; it does not execute a real model.

[Actual results, commands, snapshots and CI links](../../releases/v0.2.12-p1/REGRESSION-VALIDATION.json).
[Signed installation checks](../../releases/v0.2.12-p1/INSTALLATION-VALIDATION.json).

Skipped platform, model, optional-dependency and external-Harness tests are not
counted as passed. No real model or Strata service ran on the builder; real-model
acceptance for `v0.2.12-p1` needs manual installation and restart on the owner's
Mac, and previous p3 model results are not `v0.2.12-p1` measurements. CUDA/HIP/SYCL
builds and GPU execution are unverified. The `uniqueItems` limitation and inherited
grammar fallback remain; no stricter runtime JSON rejection was added. Apple
Silicon macOS 15+ only; Intel Macs are not a target of this fork release.
