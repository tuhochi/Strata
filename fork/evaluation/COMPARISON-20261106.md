# Same-Mac comparison, 6 November 2026

**The enabled fork resolves the reproduced undeclared-tool-name failures in this
frozen Qwen test set.** The original constraint proposals are ncphri's
[#4222](https://github.com/Niko1221/Strata/pull/4222) and
[#3800](https://github.com/Niko1221/Strata/pull/3800). This report contributes
independent Mac measurements. It does not claim authorship of those proposals or
verification of the original PR alone: the tested fork contains extra Metal and
guard integration.

Three full runs are retained:

| Run | API engine | Strict masking in Python server | Stress errors | Extra-case errors |
| --- | --- | --- | ---: | ---: |
| Original baseline | `0.1.57-metal` | Unavailable | 10/10 | 3/5 |
| First fork launch | `0.1.57.1-metal` | Disabled, confirmed by owner | 10/10 | 3/5 |
| Corrected fork launch | `0.1.57.1-metal` | Enabled, confirmed by owner and diagnostic | **0/10** | **0/5** |

Each run uses the same 58 serialized request bodies, with the same canonical
request hashes, suite hash and evaluator hash. Model ID, GPU name (Apple M1
Ultra), reported RAM capacity, context limit and one serving slot match.
Within each run identity stayed stable and the server request counter increased
by exactly 58. Those 58 include 25 functional cases, three warmups and 30 measured
performance requests. All completed, without API errors or truncation.

## Functional result

In the active run all fifteen stress/extra cases returned one usable, declared
function call with valid JSON arguments. No undeclared names, rejected tool calls,
raw XML call markup, missing calls or silent refusals were observed.

The ten stress cases all returned `sql_query`, even when the prompt requested
`sql_queri`. Five strict string comparisons fail only because the generated SQL
has an optional trailing semicolon. The raw scorer remains unchanged at 5/10
exact matches. An additional explicit review confirms the same `SELECT integer`
operation in every case; it accepts only one trailing semicolon, not arbitrary
SQL transformations. All five extra cases match their expected JSON exactly.
See [operation-review.json](results/patched-strict-20261106/operation-review.json).

The ten normal controls and all thirty measured performance answers are
**byte-for-byte equal in content, reasoning, function names/arguments and finish
reason** to the original baseline, ignoring transport IDs/timestamps. The normal
controls stay at 9/10 strict matches because of the pre-existing SQL semicolon.
The copying workloads' pre-existing exact-output failures also remain unchanged.
No answer-quality improvement or universal semantic-equivalence claim is inferred.

## Warm-cache performance

Ten repeats after one excluded warmup for each workload. Client latency includes
Tailscale transport. Values below are medians; the full individual measurements,
token counts, cache hits and draft acceptance are retained.

| Workload | Original total | Enabled fork total | Total change | Original decode | Enabled fork decode |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text, no tools | 0.985 s | 0.993 s | +0.80% | 70.7 tok/s | 70.2 tok/s |
| Normal call, four tools | 0.689 s | 0.682 s | −1.01% | 56.9 tok/s | 56.8 tok/s |
| Longer context, no tools | 1.268 s | 1.273 s | +0.38% | 71.05 tok/s | 70.65 tok/s |

Median decode differences are −0.71%, −0.18% and −0.56%. Median first-output
latency changes are −1.36%, −2.46% and −6.14%. Completion counts (57, 29, 77)
and cached prompt counts (79, 421, 1434) match in these workload medians. Draft
acceptance differs slightly; inspect the full distributions before assigning a
cause. No relevant slowdown was observed in this warm-cache sample under the
proposed initial 5% decode/10% latency review thresholds.

The first, mask-disabled fork run showed approximately 13–14% slower text decode;
its answers were otherwise identical. That observation is preserved. The later
enabled run returned close to baseline speed. Thus the earlier slowdown cannot
be presented as measured strict-mask overhead. Machine state and complete launch
parameters were not independently controlled or attested, and no A/B/A restart
sequence was performed.

The first request of the enabled run took 3.298 s with zero cached tokens; the
baseline first request took 1.698 s with 289 cached tokens. Those are unequal
initial conditions, not a controlled cold-start comparison. No cold-start
performance claim is made.

## Activation diagnosis

The initial fork process reported mask **capability** in `/v1/status`, but that
did not mean strict tool-name masking was active. The owner found the three mask
variables only in the native engine configuration's `env`, rather than in the
Python server's environment. The owner corrected the start profile and restarted
the service manually. No client SSH or service control was used.

A separate diagnostic submits an unused name containing a dot,
`diagnostic.invalid`. With masking disabled it reached generation (HTTP 200).
After correction it fails before generation with HTTP 400 and the exact strict
gate message: `strict tool names must be unique ASCII identifiers`. This agrees
with the source gate and independently corroborates activation. These deliberately
invalid diagnostic requests are outside the frozen 58-request runs.

For the configured protection, the **Python server process** must receive:

```sh
STRATA_TOOL_MASK=1
STRATA_TOOL_NAME_ENUM=1
STRATA_TOOL_MASK_STRICT=1
```

Putting them only into the native engine's child environment is insufficient.
The published `strata-fork` wrapper exports them; custom service/start profiles
must pass them to the server too. Support flags in `/v1/status` are not an active
policy attestation.

## Evidence and limits

- [Original baseline](results/unpatched-20261106/summary.json).
- [First fork run, masking disabled](results/patched-mask-disabled-20261106/INTERPRETATION.json).
- [Active fork raw requests and SSE events](results/patched-strict-20261106/requests.jsonl).
- [Machine/configuration metadata](results/patched-strict-20261106/metadata.json).
- [Unmodified comparator output](results/patched-strict-20261106/comparison-with-unpatched.json).
- [Strict activation diagnostic](results/patched-strict-20261106/strict-gate-diagnostic.json).
- [Evidence SHA-256 checksums](results/SHA256SUMS).

The API reports engine version; the owner installed fork `v0.2.11-p1`, whose
packaged build provenance identifies compiled source
`47369b49ce38ccc330358a97ef3ff5ae1a2158f9`. Runtime source/weight/tokenizer hashes
and every effective tuning flag are not independently attested by this API.

The ten typo prompts are related adversarial variants, not random production
traffic. These results cover streamed Chat Completions, Qwen XML names,
reasoning disabled and serial requests on this Mac/model. They do not establish
natural production incidence, all model/API/reasoning modes, argument correctness
in arbitrary tasks, or absence of every performance regression. CUDA/HIP/SYCL
and the original PR alone remain unverified here. Larger same-day A/B/A samples,
cold-cache measurements and realistic long multi-turn workloads are separate
follow-up work.
