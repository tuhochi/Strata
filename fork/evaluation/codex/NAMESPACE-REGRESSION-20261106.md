# Codex namespace regression in p3 — 2026-11-06

## Observed results

Client: Codex CLI 0.166.0, invoked on the user's Linux workstation. Existing
owner-managed model services were used; no service was started, stopped or
reconfigured. Tests used an isolated temporary directory and read-only sandbox.

| Probe | Result |
| --- | --- |
| `codex-atlas-coder`: respond OK, no tools used | Pass: OK |
| Same launcher: read a synthetic probe.txt through actual tools | Pass: shell listing and file read; correct marker returned |
| `codexnext`: respond OK, no tools used | Fail: strict tool names must be unique ASCII identifiers; retries exhausted |
| Atlas launcher, only invocation-level `features.multi_agent=true` added | Fail: same strict-name error; no agent was spawned |
| Atlas Responses API: ordinary function diagnostic_ping | HTTP 200, completed, OK |
| Same API: namespace diagnostic containing function ping | HTTP 500, same strict-name error |

The last two requests use reasoning effort none and max_output_tokens 64.
Sanitized results are in `namespace-comparison-20261106.json`. This is a
compatibility reproduction, not a performance benchmark.

## Evidence chain

1. A temporary localhost-only diagnostic receiver captured only tool types and
   names from a Codex request. No headers, credentials, conversation text, or
   tool arguments were persisted by that receiver. It was stopped afterwards.
2. The failing launcher advertises namespace tools, including multi_agent_v1
   and MCP namespaces. The simpler Atlas profile disables multi_agent and has
   no MCP servers configured. The same Atlas profile fails when multi_agent
   is enabled for that invocation, without changing server configuration.
3. `serve/responses.py:request_tools` already flattens namespace members to
   `namespace.name`; a CPU-only call reproduced multi_agent_v1.wait_agent.
4. `serve/constrain.py:safe_tool_names` filters using `[A-Za-z0-9_-]+`, which
   rejects the dot. `Service._with_constraint` then rejects the request because
   the accepted-name count differs from the declared-tool count.
5. This happens even when the user asks for no tool use: the definitions are
   still present in the request. A smaller coding model is not an explanation
   for this validation failure.

## Follow-up needed

Support exact internally qualified namespace names without weakening the
persistent declared-name guard. Simply permitting a dot in the shared regex
is not a complete reviewed fix: grammar name alternatives currently rely on
that regex excluding regex metacharacters, so literal escaping and namespace
round-trip behavior need regression coverage as well.

No production code, launcher configuration, server ENV, release tags or
upstream PRs were changed in this investigation. Other client warnings about
model metadata and MCP transports occurred in the full profile; this report
isolates the namespace failure and does not claim those other warnings fixed.
