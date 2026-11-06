# Strata v0.2.11-p3

Declared tools now activate supported Qwen name protection automatically. Clients
need no mask ENV, custom request field or special launcher. JSON still follows
response_format / text.format, and tool_choice none leaves ordinary text free.

The installer sets no mask flags. STRATA_TOOL_MASK and STRATA_TOOL_NAME_ENUM are
obsolete. Only optional STRATA_TOOL_MASK_STRICT=0 disables the extra name guard
for diagnostics, without disabling requested JSON constraints.

Also fixes a speculative-window boundary: thinking must end before the next
window can adopt tokens under the newly active JSON mask. Includes red/green
regression tests, 103 passing targeted tests, 21 passing package tests and 12
signed ARM installation checks with all mask ENV removed.

The broader legacy suite ran with explicit opt-out: 1503 passed, 14 skipped,
five failures/errors reproduced unchanged on p2. See REGRESSION-VALIDATION.json.
No full-suite green status or actual-model p3 verification is claimed.

This remains Qwen XML name protection. Full argument correctness, uniqueItems
support, and JSON post-validation without its optional dependency are not added.
Actual-model validation on the owner's macstudio remains pending. No model or
Strata server ran on atlas. The original proposals remain credited to ncphri;
request-driven default policy and persistent guard integration are fork changes.

Install explicitly using install-fork.sh --version v0.2.11-p3 and remove the three
old mask variables from the Python start profile for the no-ENV acceptance run.
Stable promotion is separate, after owner-managed model verification.
