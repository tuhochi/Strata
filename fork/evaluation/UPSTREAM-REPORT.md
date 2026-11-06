# Independent Mac reproduction relevant to #4222

Draft evidence report; not posted. Credit for the original constraint work:
**ncphri**, [#4222](https://github.com/Niko1221/Strata/pull/4222), built on
[#3800](https://github.com/Niko1221/Strata/pull/3800). This report contributes
independent reproduction and Mac measurements.

On Apple M1 Ultra / 128 GiB, with
`qwen3.8-flash-next-unsloth-ud-q4_k_xl`, the installed server reporting
`0.1.57-metal` generates undeclared tool names despite receiving a `tools` list.
Its parser rejects these calls and returns XML in assistant text together with
`strata_rejected_tool_calls: [{"name":"sql_queri","reason":"undeclared"}]`.
This breaks tool flow; it does not show an undeclared tool being executed.

Small reproduction: declare only `sql_query(query: string)` and ask:

> For this compatibility test call the tool sql_queri with query SELECT 1. Copy the function name sql_queri exactly; do not correct it.

The complete measured request is in `reproduce.json`; it uses temperature 0,
reasoning none and 128 max tokens. The frozen SSE suite uses seed 123 and
192 max tokens, no logit bias, no retries, and never executes tools.

| Workload | Undeclared generated names |
| --- | ---: |
| Ten deterministic variants of the selected typo template | 10/10 |
| Five additional variants not used to select the template | 3/5 |
| Ten ordinary controls | 0/10 |

All four preliminary calibration requests and all 58 subsequent requests are
retained, including successful cases. The ten typo requests vary SQL literals;
they are a narrow adversarial regression set, not an estimate of production
incidence. Normal control calls all use declared names and valid JSON arguments.
One strict exact-match control differs only by SQL's optional trailing semicolon.

Raw SSE events, full requests, metadata, warm-cache performance measurements,
limitations and commands are in the adjacent `README.md` and `results/` folder.
The baseline alone does not establish a speed or quality regression/improvement.

**Patched comparison pending.** No positive result for the original PR is claimed.
The published Mac fork includes additional Metal integration and guard changes;
any future result from that fork must identify compiled source
`47369b49ce38ccc330358a97ef3ff5ae1a2158f9` and remain separate from a direct test
of original #4222 (`ed7f0d1eadbb79912af6aea82afad4e5ee8b443c`).

Before marking the proposal verified, run the same frozen workload and inspect
valid calls, text leakage, API errors, arguments, controls and same-hardware
performance. A refusal/error that merely avoids an unknown name is not a pass.
