# Strata v0.2.11-p4 for Apple Silicon

Fixes the p3 regression that rejected Codex Responses namespace tools such as
`multi_agent_v1.wait_agent`. Exact declared-name masking stays active; namespace
dots are literal characters, not regex wildcards. No enabling ENV is required.

This continues ncphri's original contributions in upstream PRs #3800 and #4222,
with this fork's Metal integration and regression fixes.

## Install on your Mac

```sh
curl -fsSL https://raw.githubusercontent.com/tuhochi/Strata/v0.2.11-p4/fork/install.sh -o /tmp/install-strata-p4.sh
sh /tmp/install-strata-p4.sh --version v0.2.11-p4
```

Then restart your service using the installed fork and your existing model and
launch profile. The installer does not replace the code of an already running
Python process. Expected Terminal version: `0.2.11-p4`; engine: `0.1.57.4-metal`.
No additional mask ENV is required. Models are separate from these packages.

## Validation and limits

135 focused regressions passed, including namespace HTTP calls and results with
JSON and SSE. All 13 signed ARM installation checks passed in a fresh prefix,
including the namespace guard and literal regex dots without mask ENV.
The real Codex client also passed against a local CPU mock of the corrected API.

No model was started for build or installer validation. Real-model p4 acceptance
on the owner's Mac is pending manual installation and restart. The prior p3 model
measurements are not presented as p4 hardware results. The known uniqueItems
schema limitation is unchanged. See REGRESSION-VALIDATION.json and
INSTALLATION-VALIDATION.json for the actual scope.

This is an explicitly versioned release. The existing default stable channel is
not promoted by this publication. Install with the --version argument above.
