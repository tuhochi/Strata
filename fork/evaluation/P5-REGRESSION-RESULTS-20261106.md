# P5 regression verification

Release `v0.2.11-p5`, engine `0.1.57.5-metal`.
Build source: `b24b86d02fee859d2a4942a22609ce53d8ac6232`.

The four fork regressions reproduced in the [earlier audit](CI-AUDIT-20261106.md)
are fixed. An added generation-header assignment discarded parallel request IDs;
P5 preserves them for GEN and GENI. Text, images, concurrent requests and
cancellation have regression coverage. The original tool/JSON work remains
credited to ncphri's upstream PRs [#3800](https://github.com/Niko1221/Strata/pull/3800)
and [#4222](https://github.com/Niko1221/Strata/pull/4222).

Full validation also exposed a real save-screen layout bug. A deterministic
long-path test failed before the fix: wrapped storage text pushed actions outside
an 80x24 terminal. Measuring rendered rows fixes it; the existing wizard sizes
and the new explicit long-path case pass.

Other corrections isolate simulated hardware, helpers, disk space, terminal
capabilities and platform/version expectations. The process-stop fixture could
misclassify dead or collected tasks as alive: both cases were reproduced with
controlled OS observations. Thirty actual parent/child stop repetitions pass.
Assertions that descendants end and an unrelated process survives remain.

Git also converted patch line endings after its checksum was generated. The
committed-payload check failed before correction. The payload is now preserved
byte for byte. Committed checksums, clean-upstream replay, corruption refusal and
idempotence pass with both tested Git line-ending settings.

| Suite | Passed | Skipped | Failed |
| --- | ---: | ---: | ---: |
| Terminal, setup, tools and fork corpus | 4,747 | 108 | 0 |
| Server, pinned minimal Python runtime | 1,511 | 19 | 0 |
| Automatic constraints, no mask ENV | 90 | 2 | 0 |
| Constraints with optional jsonschema | 92 | 0 | 0 |
| App host, Node 24 | 1,502 | 110 | 0 |
| Signed ARM installation checks | 13 | 0 | 0 |

Suites overlap; do not add their counts as unique tests. The Python corpus is
4,855 collected tests, split into independent main and TUI-walk runs. The report
records snapshots and verifies unchanged runtime dependencies. The strengthened
committed-export test was rerun after the packaging-only commit. Seven critical
files in the signed archive match the tested source byte for byte.

[Actual results, commands, snapshots and CI links](../../releases/v0.2.11-p5/REGRESSION-VALIDATION.json).
[Signed installation checks](../../releases/v0.2.11-p5/INSTALLATION-VALIDATION.json).

Skipped platform, model, optional-dependency and external-Harness tests are not
counted as passed. No real model or Strata service ran on the builder. P5 model
acceptance on the owner's Mac needs manual installation and restart; previous p3
model results are not p5 measurements. CUDA/HIP/SYCL builds and GPU execution are
unverified. The uniqueItems limitation and inherited grammar fallback remain;
no stricter runtime JSON rejection was added.
