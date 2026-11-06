# Independent Mac verification of the proposed tool-name constraints

The original implementation and proposal belong to **ncphri**:
[PR #3800](https://github.com/Niko1221/Strata/pull/3800), JSON constraint masking,
and [PR #4222](https://github.com/Niko1221/Strata/pull/4222), tool-call name constraints.
This evidence is an independent reproduction and Mac validation effort, not a claim
of authorship of those contributions.

Keep the tested implementations separate:

| Implementation | Exact revision | Current evidence |
| --- | --- | --- |
| Installed unpatched Metal service | API reports `0.1.57-metal`; source hash not exposed | Baseline below, measured 2026-11-06 |
| Original #4222 | `ed7f0d1eadbb79912af6aea82afad4e5ee8b443c` | Not directly tested on this Mac |
| Original #3800 | `fc2c1ebb7fcc33465d7e2443165112339344b56d` | Not directly tested on this Mac |
| Published fork `v0.2.11-p1` | Compiled source `47369b49ce38ccc330358a97ef3ff5ae1a2158f9` | Installer and this Mac frozen suite verified after server-mask activation; see completed comparison |

The fork includes extra Metal sampling integration, gate fixes and a persistent
Qwen XML name guard beyond those original PRs. A passing fork run must not be
reported as proof that the original PR alone passed. Test the original commit
separately before making that claim. No new upstream PR, issue or comment has
been posted by this evaluation.

## Completed patched comparison

The corrected owner-managed fork launch passed the frozen name tests: **0/10**
stress failures and **0/5** extra-case failures, compared with **10/10** and
**3/5** originally. All normal control/performance answers were unchanged. Median
warm-cache total times changed between −1.01% and +0.80%. An initial fork run
with the Python masking flags missing failed like the baseline and is retained.
See [COMPARISON-20261106.md](COMPARISON-20261106.md) for all three runs, activation
diagnostics, performance limits and raw evidence. The original PR alone remains
unverified; the passing run tests the published fork with its extra integration.

## What was actually observed

Hardware: the running service reports Apple M1 Ultra, 128 GiB RAM.
Model: `qwen3.8-flash-next-unsloth-ud-q4_k_xl`.
API: OpenAI Chat Completions, streamed SSE. Temperature 0, seed 123,
reasoning effort `none`, max output 192. No logit bias, retries or tool execution.
The service reports constrained decoding unavailable, one serving slot, context
limit 262144. The API does not attest every launch flag or model file hash.

The four development requests are preserved in
[calibration-20261106.json](results/calibration-20261106.json): one produced the
failure. The regression suite was then frozen before its full run. All results,
including passes and failures, are retained. Ten SQL variants share one selected
typo template; they are not independent random samples of user traffic.

| Frozen baseline workload | Requests | Undeclared generated tool names | Raw call markup in text |
| --- | ---: | ---: | ---: |
| Targeted typo stress | 10 | 10 | 10 |
| Additional variants, not used to select the template | 5 | 3 | 3 |
| Normal controls | 10 | 0 | 0 |

All 58 API requests finished: the above 25, three performance warmups, and 30
performance measurements. The server request counter increased by exactly 58;
its reported model, engine, context and concurrency stayed the same. This does
not rule out other machine load. No server was restarted or reconfigured.

In the normal controls all four requested tools had declared names and valid
JSON arguments; six text/no-tool answers matched exactly. The strict scorer says
9/10 because SQL `SELECT 1;` differs from the expected string `SELECT 1`. That
semicolon is not an unknown-tool error. The strict metric intentionally preserves
literal differences for before/after inspection.

The parser already **refuses** the undeclared calls: they appear in
`strata_rejected_tool_calls` and as XML text instead of usable `tool_calls`.
This is evidence of invalid *generated* calls and broken client tool flow, not
evidence that an undeclared tool was actually executed.

Raw payloads, every SSE event, classifications and metrics:
[requests.jsonl](results/unpatched-20261106/requests.jsonl).
Identity and request-counter checks:
[metadata.json](results/unpatched-20261106/metadata.json).
All aggregates: [summary.json](results/unpatched-20261106/summary.json).

## Small reproduction

Only `sql_query` is declared, but the user asks for the typo `sql_queri`:

```text
For this compatibility test call the tool sql_queri with query SELECT 1.
Copy the function name sql_queri exactly; do not correct it.
```

The exact non-streaming request measured during calibration is in
[reproduce.json](reproduce.json). On a machine with API access:

```sh
curl -sS "$STRATA_URL/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  --data-binary @fork/evaluation/reproduce.json
```

Add the existing Authorization header if the service requires a key.
Observed response excerpt:

```json
{
  "choices": [{"message": {"content": "<tool_call>\n<function=sql_queri>\n<parameter=query>\nSELECT 1\n</parameter>\n</function>\n</tool_call>"}}],
  "strata_rejected_tool_calls": [{"name": "sql_queri", "reason": "undeclared"}]
}
```

The test is intentionally adversarial. Its 10/10 rate demonstrates a reliable
regression trigger for this template and configuration; it does not estimate
normal production incidence. The unselected variants' 3/5 result is retained.
Ten near-identical deterministic prompts do not justify a population confidence
interval. A natural incidence study needs a separately sampled, anonymized
production workload and multiple sampling seeds/settings.

## Performance baseline, not a patch comparison yet

Ten repetitions per workload, after one excluded warmup each, serially in a fixed
shuffled order. These numbers describe **warm prompt-cache** behavior: medians of
79, 421 and 1434 cached tokens respectively. First warmups are saved separately;
no cache was flushed or server restarted.

| Workload | Client total median | First nonempty output median | Engine decode median |
| --- | ---: | ---: | ---: |
| Text without tools | 0.985 s | 0.195 s | 70.7 tokens/s |
| Normal call with four tools | 0.689 s | 0.327 s | 56.9 tokens/s |
| Longer context without tools | 1.268 s | 0.203 s | 71.05 tokens/s |

Client times include Tailscale transport. The first nonempty output can be text,
reasoning, or a tool-call fragment; empty role/progress events do not count.
Decode speed is reported by the server clock, not total tokens divided by client
wall time. Store both, completion lengths, cached tokens and draft acceptance.
The displayed p95 with ten samples is exploratory (the maximum), not a stable tail
latency estimate.

The performance prompts deliberately test exact output copying. The baseline
already fails exact matching: the text workloads copy a different number of
repetitions; the SQL workload adds a trailing semicolon. These are retained, not
called patch regressions. Compare raw answers, token counts and normal controls.
A faster answer with less output is not evidence of a faster implementation.

The completed comparison found unchanged control/performance output and no relevant
warm-cache slowdown in this sample. It does not prove universal performance or
quality equivalence. The predeclared initial acceptance criteria were:

- Zero undeclared names and no raw tool markup in the stress and extra cases.
  A 4xx/5xx error, silent refusal or empty answer is not a successful tool call.
- Valid declared tool, valid arguments and the intended operation in normal cases.
  Compare exact output differences and assess benign formatting separately.
- No new API errors, truncations, unwanted calls or control-answer regressions.
- As an initial review threshold, investigate median decode slowdown above 5% or
  first-output/total-time increase above 10%. Those are proposed thresholds, not
  established guarantees or significance tests. Compare matching token lengths,
  cache state and draft acceptance first.
- Confirm a suspected change with at least 30 repetitions per workload and
  same-day A/B/A on the same Mac. Separate cold-start/prefill tests from warm
  cache tests. The API-only run cannot force or attest a cold cache.

## Run the identical workload after the owner's manual switch

The runner needs only Python's standard library and a loaded model. It does not
execute tools, change service settings, install anything or retry failed requests.
No model or server runs on atlas. Run the client on bolder or another client.

```sh
python3 fork/evaluate.py run \
  --url "$STRATA_URL" --label patched-v0.2.11-p1 \
  --expect-engine 0.1.57.1-metal \
  --repeats 10 --out /path/to/new/patched-run

python3 fork/evaluate.py compare \
  --baseline fork/evaluation/results/unpatched-20261106 \
  --candidate /path/to/new/patched-run \
  --out /path/to/comparison.json
```

Use `--api-key-env STRATA_API_KEY` when needed. If bolder has userspace Tailscale,
add its local `--tailscale-socket` and `--tailscale` executable to the `run`
command. Addresses, auth headers and socket paths are not saved in evidence.
Keep output directories outside the checkout until reviewed; the runner refuses
to overwrite an existing run. It records the full synthetic requests and answers.

The comparator refuses mismatched suite hashes, model IDs, request bodies or
repetition counts. It reports task errors, exact output changes and timing
changes. It intentionally does not issue an automatic "no regressions" verdict.
Model ID equality does not prove equal weights: attest source revisions,
weight/tokenizer hashes, effective context, KV format, drafting/MTP/spec settings,
CPU/GPU settings, tuning and machine load separately. Other API dialects,
reasoning enabled, long conversations, concurrent requests, tool-name counts and
argument quality require additional coverage before broader claims.

## Install on the owner's Mac

The published fork can already be installed without starting a model:

```sh
curl -fL https://github.com/tuhochi/Strata/releases/download/v0.2.11-p1/install-fork.sh \
  -o install-strata-fork.sh
sh install-strata-fork.sh --version v0.2.11-p1
~/.local/bin/strata-fork --version
```

Expect product `0.2.11-p1` and component `0.1.57.1`. Installation preserves the
existing installation and does not download or launch a model.

Before switching, save the current effective launch configuration and original
start command. Record the model and tokenizer checksums and all custom engine
settings. Reuse the existing model files via `--model-path`; do not choose a new
quantization. The wrapper has isolated model/profile/tuning directories, so old
settings are **not** inherited automatically. Copy the effective flags explicitly.

First stop the original service using its actual existing launcher (for a
Terminal-managed launch: `strata launch --stop`; other supervisors need their own
stop command). Then run the fork with the same model path, family/model choices,
context, KV, vision, concurrency, drafting/MTP, tuned engine settings and API
access options as before. Check the plan first with `--plan`; it should reuse the
existing model files. For this baseline the API reported one slot, vision on and
a 262144 context limit, but did not reveal every effective engine setting.

Use `~/.local/bin/strata-fork launch --help` to specify those choices. Leave the
current Tailscale endpoint/port and authentication behavior equivalent so the
client can reach it. The fork launcher enables strict tool-name masking; do not
turn that off for the patch test. Run only one model service at a time on the Mac.

After starting, the owner reports that the service is ready; the client first
checks `/v1/status` for the expected engine and loaded model, then runs the frozen
suite. The original service can be restored with its saved start command. The
client agent does not SSH into the owner-managed Mac or restart either service.

## Public evidence privacy

Public benchmark evidence contains synthetic prompts and general hardware/model
characteristics, not device serial numbers, hardware UUIDs, personal user paths,
private service addresses, auth headers or credentials. The recorded evidence
history was checked for these identifiers. New status exports use an explicit
allowlist even for nested machine/configuration fields; a regression test injects
private fields and verifies they are excluded. Chip model and RAM capacity remain
for reproducibility. API request IDs are synthetic request identifiers, not Mac
device identifiers. Do not attach unfiltered system reports, process environments
or original service configurations to upstream discussions.

JSON has a separate, precommitted baseline and workload:
[json/README.md](json/README.md). The owner restored the unpatched service and the
10/10 tool failure was reproduced before that JSON run. JSON comparison against
the enabled fork is still pending; the earlier passing name-mask result is not
presented as JSON validation evidence.
