# JSON response-format baseline, 6 November 2026

This is an independent measurement relevant to ncphri's original
[JSON constraint PR #3800](https://github.com/Niko1221/Strata/pull/3800) and
[tool-call PR #4222](https://github.com/Niko1221/Strata/pull/4222).
The completed fork comparison is in [COMPARISON-20261106.md](COMPARISON-20261106.md):
9/10 format stress cases pass, one array case and two JSON-with-tools cases
remain unresolved. The observations below describe the original baseline. No upstream PR, issue or comment has
been published. A future test of the published fork must remain separate from a
direct verification of the original contributor's PR alone.

The owner manually restored the unpatched service. Before any JSON measurement,
the existing tool suite was rerun against API engine `0.1.57-metal`:
**10/10** targeted unknown-name failures, **3/5** additional failures and
**0/10** unknown names in normal controls. All 58 requests completed; the service
counter increased by 58 and reported identity stayed stable. Full tool recheck:
[metadata](../results/unpatched-recheck-20261106/metadata.json),
[summary](../results/unpatched-recheck-20261106/summary.json).

The new JSON suite, client and offline scorer checks were committed at
`6cb78c4b` **before the first JSON request**. No cases were selected or discarded
after observing this run. The suite hashes and exact evaluator/transport hashes
are saved with the raw evidence.

## Scope and method

These are **JSON-formatted model answers via `/v1/chat/completions`**, not tests
of the separate `/v1/responses` API. All are non-streaming HTTP requests.
Same model ID: `qwen3.8-flash-next-unsloth-ud-q4_k_xl`; hardware reported as
Apple M1 Ultra, 128 GiB RAM; context limit 262144, one serving slot. The status
reports constrained decoding unavailable. API engine version is not an independent
attestation of server source or model-file hashes.

Sampling: temperature 0, seed 123, reasoning none, max output 192, no logit bias,
no retries, serial execution. The **client** independently validates against the
requested JSON Schema using `jsonschema 4.26.0`, including required properties,
types, enums, extra fields and nested/array constraints. The API does not attest
whether the **server** has the optional `jsonschema` package installed; client
package metadata must not be mistaken for server dependency evidence. No root
cause is inferred solely from that missing attestation.

The suite contains ten adversarial cases, six ordinary controls, three
JSON-with-tools integration cases and three invalid-request controls. Three
performance workloads have one excluded warmup and ten measured repeats each:
**55 HTTP requests total**. The server counter rose by 49; six HTTP 400 rejections
were not counted as generated requests. Identity stayed stable. No tool was
executed and the client never restarted or reconfigured the service.

## Observed results

| Targeted case | HTTP | Independent result |
| --- | ---: | --- |
| Ask for Markdown fences | 200 | Valid JSON object; passed |
| Ask for an array instead of an object | 502 | `structured_output_failed`; no successful answer |
| Omit required property | 200 | Schema violation: `{}` |
| String instead of integer | 200 | Schema violation: `{"result":"forty-two"}` |
| Value outside enum | 200 | Schema violation: `{"status":"FAIL"}` |
| Forbidden extra property | 200 | Schema violation: `{"result":42,"debug":true}` |
| Wrong nested type | 200 | Schema violation: `user.active` is string `"yes"` |
| Array length/uniqueness | 200 | Schema violation: `[1,1]` instead of three unique integers |
| Contradict string pattern | 200 | Schema honored; returned `ABC` |
| Contradict numeric bounds | 200 | Schema honored; returned `5` |

Thus **7/10 targeted requests fail**: **six successful HTTP responses violate the
schema**, one request ends with an HTTP 502 error. There were no successful
responses with invalid JSON syntax in these ten cases. The three passing cases
are kept as controls for the same frozen comparison, not replaced to inflate the
reproduction rate. These deliberately adversarial cases are not a production
incidence estimate.

All six ordinary controls passed. All three JSON-with-tools requests were
rejected with HTTP 400: `structured response_format with tools/MCP is not
supported`. This is an observed integration limitation, not malformed generated
JSON. Cases cover automatic tool choice, required tool choice, and a final answer
after a **synthetic** prior tool result. The latter is a fixed history fixture,
not an executed end-to-end tool round trip.

The three deliberately invalid requests (missing schema name, nonobject root,
remote reference) were all rejected with HTTP 400 as expected. They are passing
negative controls, not part of the JSON failure count.

## Small measured reproduction

Only the `result` integer property is allowed and required. The prompt deliberately
asks for `{}`. The original service actually returns HTTP 200 with content `{}`.

The exact measured request is [reproduce-required.json](reproduce-required.json):

```sh
curl -sS "$STRATA_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  --data-binary @fork/evaluation/json/reproduce-required.json
```

Use the existing Authorization header if necessary. Do not publish its value.

## Performance baseline

All thirty measured performance requests succeeded with the expected JSON value.
Each workload has ten repetitions after a separate warmup; medians below are
**warm-cache**, client end-to-end latency and server-reported decode speed.

| Workload | Total median | Decode median | Output tokens | Cached tokens |
| --- | ---: | ---: | ---: | ---: |
| Text instruction, no response format | 0.838 s | 61.1 tok/s | 41 | 55 |
| `json_object` | 1.903 s | 60.35 tok/s | 105 | 126 |
| `json_schema` | 1.911 s | 60.3 tok/s | 105 | 186 |

The format cases produce more whitespace/output tokens than the text case.
Those total times therefore **do not measure pure JSON overhead**. Compare each
workload to itself after the switch and inspect token counts, cache hits and
draft acceptance. Record output changes separately from speed changes.
Non-streaming totals include buffering and validation; no TTFT is claimed.
Ten repeats are exploratory; confirm suspected regressions with larger same-day
A/B/A runs before causal or general performance claims. No cold-cache claim.

## Repeat after the owner switches back to the fork

Keep suite and sampling unchanged. Preserve the same model files, context, KV,
vision, concurrency, drafting/MTP and effective tuned engine parameters. The
Python server must receive the mask variables, not just the native engine's env:

```sh
STRATA_TOOL_MASK=1
STRATA_TOOL_NAME_ENUM=1
STRATA_TOOL_MASK_STRICT=1
```

Once the owner has manually restarted the fork and the API is ready, run from
bolder or another API client (never run a model/server on atlas):

```sh
python3 fork/evaluate_json.py run \
  --url "$STRATA_URL" --label patched-json \
  --expect-engine 0.1.57.1-metal --repeats 10 \
  --out /path/to/new/json-patched-run

python3 fork/evaluate_json.py compare \
  --baseline fork/evaluation/json/results/unpatched-20261106 \
  --candidate /path/to/new/json-patched-run \
  --out /path/to/json-comparison.json
```

Use the same client `jsonschema` version, recorded in metadata. On bolder, add
the local `--tailscale` executable and `--tailscale-socket` options as in the
existing tool runner. Use `--api-key-env` if needed. Never store credentials in
committed commands. The comparator refuses different model IDs, suite hashes,
client schema-validator versions, request bodies or repeat counts. It reports
outcomes; it does not automatically declare a universal fix or no-regression
verdict. A fast HTTP error is never included in successful-request speed metrics.

Evidence: [raw requests/responses](results/unpatched-20261106/requests.jsonl),
[summary](results/unpatched-20261106/summary.json),
[metadata](results/unpatched-20261106/metadata.json),
[checksums](results/SHA256SUMS). Exported evidence was checked for personal paths,
private addresses, credentials, device serials and hardware identifiers. General
chip/RAM characteristics remain for reproducibility. Eight offline scorer tests
verify classification independently of real-model behavior.

The later [p3 hardware comparison](../P3-HARDWARE-20261106.md) verifies all three JSON-plus-tools cases on the owner-managed Mac; the array case remains unresolved. Earlier p1 measurements above and their raw data remain unchanged.
