# Request-driven protection in v0.2.11-p3

The owner explicitly requested automatic activation like the normal llama.cpp
request workflow. Starting with this fork revision, clients do not need a mask
ENV, new request field or a special launcher to enable supported Qwen tool-name
protection. This is an intentional fork default change, not a claim that all
llama.cpp model/template behavior is identical.

| Request / configuration | Behavior |
| --- | --- |
| `tools`, no `response_format`, no mask ENV | Persistent declared-name guard |
| `tools` plus JSON `response_format` | Name guard intersected with JSON mask |
| Responses tools plus `text.format` | Same shared guard / JSON path |
| Anthropic tools | Same shared name guard |
| `tool_choice: "none"` | Offered tools removed; normal text remains free |
| JSON format, no tools | JSON masking follows the request independently |
| No tools and no JSON format | Existing plain text path unchanged |
| Optional `STRATA_TOOL_MASK_STRICT=0` in Python server | Extra name guard disabled for diagnostics; requested JSON remains active |
| `STRATA_TOOL_MASK_STRICT` unset or `1` | Request-driven protection active |

The older STRATA_TOOL_MASK and STRATA_TOOL_NAME_ENUM activation flags are no
longer read. The installer wrapper does not export any of the three variables.
Existing profiles that set them to 1 remain compatible; new profiles can omit
them all. Setting a variable only in the native engine's child env is unnecessary
for the new default; the optional explicit opt-out still belongs to Python's env.

With declared tools, an unsupported engine, missing llguidance, unsupported
DeepSeek DSML or unusable/duplicate names is rejected instead of silently
claiming constrained execution. This release still covers Qwen XML names;
semantic tool selection and arbitrary argument correctness are not guaranteed.
The inherited unsupported-JSON-schema fallback and missing optional jsonschema
post-validator remain separate known limitations; no uniqueItems fix is claimed.

## Regression coverage

Before the activation change, new tests failed because no constraint was created
without ENV and an unsupported engine did not fail closed. After the change,
real llguidance tests prove activation without ENV, legacy flag independence,
explicit opt-out with JSON still constrained, plain-text identity and missing
capability rejection.

HTTP tests remove all three mask variables and verify Chat Completions, SSE,
Responses and Anthropic tool calls. A prose prefix does not release the guard;
`tool_choice: none` produces normal prose without a tool constraint.

A pre-existing multi-row test additionally revealed that the persistent guard
ignored the inner JSON matcher's `MF cut=...` while thinking. It could accept
speculative tokens beyond `</think>` before JSON became active. A new direct
regression test failed with 17 mask rows where only 12 were safe. The guard now
preserves that boundary, so the next token window uses the armed JSON mask.
Both the direct regression and the existing multi-row HTTP tool/answer test pass.

Compatibility tests for the legacy unmasked fake engine run with an explicit
opt-out. The CI separately runs automatic-constraint tests with all mask ENV
removed and checks llguidance is available; the opt-out lane is not presented
as proof of default automatic protection.

The built ARM installer verification also clears all three variables and invokes
the installed server constraint method with a 320-ID tokenizer. It checks both
request-driven activation and the p2 JSON-mask-width regression without starting
any model or Strata API server on atlas. Actual-model testing on the owner's macstudio
requires a separate manual p3 installation/start and is not implied by CPU tests.

Original JSON/tool grammar contributions remain credited to ncphri (#3800,
#4222). This activation/default policy and the persistent guard are additional
fork changes. No official upstream PR or comment has been published.

Executed validation: 103 targeted regressions, 21 package/version checks and 109
focused legacy parser tests passed. The full legacy suite ran 1522 tests with
1503 passes, 14 skips and five failures/errors. Those same five failures
(DeepSeek fake-engine parallelism and HIP GPU ordering) were reproduced in an
unmodified p2 checkout before publication; they are not reported as new p3
regressions or hidden by a green full-suite claim. Signed ARM installation checks
verify request-driven composition with all mask ENV absent. See the p3 release's
REGRESSION-VALIDATION.json for counts and exact failing case names.

The owner-managed [p3 Mac hardware comparison](P3-HARDWARE-20261106.md) is now recorded: no unknown names in 15 stress/additional cases and all three JSON-plus-tools cases pass. The known array violation remains. Environment absence is owner-managed rather than remotely introspected.
