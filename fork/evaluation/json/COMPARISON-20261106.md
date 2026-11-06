# Frozen JSON comparison on the owner's Mac

**Partial improvement, not a complete JSON fix.** The enabled fork passes 9/10
format stress cases versus 3/10 originally. Five of the six successful-but-schema-
violating responses are corrected. One array constraint case still violates its
schema. Two of three JSON-with-tools cases still fail and take about 64 seconds.

The original constraint proposals are ncphri's
[#3800](https://github.com/Niko1221/Strata/pull/3800) and
[#4222](https://github.com/Niko1221/Strata/pull/4222). This is independent Mac
measurement of the published fork with extra integration, not a passing claim
for the original PR alone. No upstream PR, issue or comment has been posted.

## Setup and validity

Unpatched API engine `0.1.57-metal`; patched API engine `0.1.57.1-metal`.
Same reported model `qwen3.8-flash-next-unsloth-ud-q4_k_xl`, Apple M1 Ultra,
128 GiB RAM, 262144 context limit and one serving slot. Owner performed both
service switches. No client SSH, restart or configuration mutation occurred.

The suite and evaluator were committed at `6cb78c4b` before the baseline.
All 55 serialized requests have identical hashes and order across both runs,
including sampling, JSON formats and the fixed synthetic tool history. Evaluator,
transport, suite and client schema-validator version are unchanged. Each run
contains 22 functional requests, three excluded warmups and 30 measured repeats.

A separate pre-run diagnostic verifies actual strict-gate behavior: the patched
server rejects an unused tool name containing a dot with HTTP 400 and
`strict tool names must be unique ASCII identifiers`. This is stronger evidence
of activation than the API's capability flag alone. It is outside the 55-case
run. The server must receive the three mask variables as the string `1`, not
`true`, in its own environment.

Both runs preserve reported identity. The original server request counter rose
by 49, the patched one by 52; each client recorded 55 HTTP requests. Rejections
occur at different stages and do not all increment the generation counter.
Raw statuses and all HTTP outcomes are retained. No equality of counters across
versions is asserted as a prerequisite for request-body equality.

## JSON-format stress results

| Case | Original | Enabled fork |
| --- | --- | --- |
| Markdown fences requested | Valid JSON object | Valid JSON object |
| Array requested under `json_object` | HTTP 502 | Valid JSON object containing an explanatory error string |
| Required `result` omitted | HTTP 200 `{}`; invalid | HTTP 200 `{"result":0}`; valid |
| Integer requested, prompt asks for string | String value; invalid | Integer value; valid |
| Enum | `FAIL`; invalid | `OK`; valid |
| Additional property forbidden | Extra `debug`; invalid | Extra property absent; valid |
| Nested boolean | String `"yes"`; invalid | Boolean `true`; valid |
| Three unique array integers | `[1,1]`; invalid | **Still `[1,1]`; invalid** |
| String pattern | Valid `ABC` | Valid `ABC` |
| Numeric bounds | Valid `5` | Valid `5` |

Thus targeted failures fall from **7/10 to 1/10**. Successful HTTP responses that
violate the requested schema fall from **6 to 1**. Both minItems=3 and
uniqueItems=true are still violated in the remaining array case; the cause has
not been established. This result does not justify claiming full JSON Schema
support.

The root-array case is a format-only pass: its contradictory prompt asks for an
array while the API requires an object. The patched model returns
`{"error":"Invalid request: root must be an array, not an object."}`. This satisfies
`json_object`; it is not proof of a substantively useful answer. Likewise the
integer stress cases test type/structure, not whether a value such as 0 or 2 is
an appropriate business answer.

All six ordinary controls pass in both versions. Their content, calls and finish
reasons are unchanged according to the frozen comparator. The three deliberately
invalid-request controls still receive the expected HTTP 400 responses.

## JSON plus tools: important remaining failures

| Case | Original | Enabled fork |
| --- | --- | --- |
| Automatic tool choice with JSON schema | HTTP 400, unsupported | HTTP 400, mask-width mismatch after **64.419 s** |
| Required tool choice with JSON schema | HTTP 400, unsupported | Valid `sql_query` call after **12.447 s** |
| Final JSON after synthetic tool result | HTTP 400, unsupported | HTTP 400, mask-width mismatch after **63.875 s** |

The exact new error is:

```text
tool-name mask vocabulary width differs from schema mask
```

The fork source raises this at the name-guard/schema-mask intersection when mask
byte lengths differ (`serve/constrain.py`, `ToolNameConstraint._intersect`). The
observed error is established; the precise reason for the differing widths has
not been diagnosed. This guard integration is an additional fork change and must
not be attributed to the original contributor's PR without a direct test.

The required-call case accepts `SELECT 1;` as the same intended synthetic query
as `SELECT 1`. No SQL was executed. The final-answer fixture contains a fixed
synthetic prior tool result; this is not a successful end-to-end tool round trip.
Overall JSON-plus-tools improves from **0/3 to 1/3**, and remains incomplete.
The 12–64 second single-request timings include setup/cold effects and are not
repeatable warm-cache speed estimates. They are nevertheless observed latency
problems and must not disappear behind the successful-workload averages.

## Warm-cache performance

Thirty successful measured requests per version, ten repeats per workload after
one excluded warmup each. Medians:

| Workload | Original total | Fork total | Change | Original decode | Fork decode |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text, no format | 0.838 s | 0.855 s | +1.98% | 61.1 tok/s | 61.1 tok/s |
| `json_object` | 1.903 s | 1.938 s | +1.88% | 60.35 tok/s | 59.8 tok/s |
| `json_schema` | 1.911 s | 1.984 s | +3.82% | 60.3 tok/s | 59.35 tok/s |

Output and cached-token counts match within each workload: 41/55 for text,
105/126 for json_object and 105/186 for json_schema. Actual performance-answer
content and finish reasons are unchanged. Draft acceptance differs slightly;
full measurements are retained. Failed JSON-plus-tools requests are excluded
from these successful-request speed metrics and are reported separately above.

These are small observed median differences under the initial review thresholds,
not proof of zero overhead or universal performance equivalence. Ten repeats,
non-streaming replies, warm caches and unverified full launch parameters limit
causal claims. No cold-cache, other-model, streaming, `/v1/responses` or general
JSON Schema guarantee is inferred.

## Evidence

- [Frozen comparison output](results/patched-strict-20261106/comparison-with-unpatched.json).
- [Patched raw requests and responses](results/patched-strict-20261106/requests.jsonl).
- [Patched summary](results/patched-strict-20261106/summary.json).
- [Patched metadata](results/patched-strict-20261106/metadata.json).
- [Strict activation diagnostic](results/patched-strict-20261106/activation-diagnostic.json).
- [Original baseline](README.md).
- [Evidence checksums](results/SHA256SUMS).

The five corrected schema cases and remaining array violation were additionally
checked directly from raw response values independently of the generic scorer.
Public evidence was checked for personal paths, private addresses, credentials,
serial numbers and hardware identifiers before publication in the owner's fork.
No code fix or new binary deployment was made during this evaluation.
