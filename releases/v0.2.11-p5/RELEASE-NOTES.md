# Strata v0.2.11-p5 for Apple Silicon

Fixes the four parallel-request regressions reproduced against pristine upstream:
the generation command keeps its request identifier when adding token constraints.
Both text and image command paths have regression coverage. P4's Codex Responses
namespace compatibility and automatic declared-name masking remain enabled.

Also keeps save actions visible when long storage paths wrap in a small terminal.
The checksum-pinned patch payload is preserved across Git line-ending settings,
and its committed bytes are checked before replay.

This continues ncphri's original contributions in upstream PRs #3800 and #4222,
with this fork's Metal integration and regression fixes.

## Install on your Mac

```sh
curl -fsSL https://raw.githubusercontent.com/tuhochi/Strata/v0.2.11-p5/fork/install.sh -o /tmp/install-strata-p5.sh
sh /tmp/install-strata-p5.sh --version v0.2.11-p5
```

Restart your service using the installed fork, your existing model and launch
profile. Expected Terminal version: `0.2.11-p5`; engine: `0.1.57.5-metal`.
No mask ENV is required. The installer does not restart an existing service.

## Validation and limits

See REGRESSION-VALIDATION.json for the full server, Terminal/setup, app-host and
focused constraint results, and INSTALLATION-VALIDATION.json for signed Mac
package checks. Minimal runtime and optional JSON Schema validation are tested
separately; optional validation is not made a new runtime dependency.

Test fixtures now specify platform, terminal capabilities, available helper
programs and simulated destination space explicitly. Private signing-key tests
run outside Git repositories; the key safety check is preserved.

No model was started on the builder. Real-model p5 acceptance on the owner's Mac
is pending manual installation and restart. P3 model measurements are not p5
hardware results. The known uniqueItems limitation and inherited grammar fallback
remain unchanged, as requested. CUDA/HIP/SYCL builds and hardware are unverified.

This explicitly versioned release does not promote the existing default stable
channel. Install with the --version argument above.
