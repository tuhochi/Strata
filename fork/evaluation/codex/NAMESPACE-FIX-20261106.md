# Namespace compatibility fix after p3

Source fix: `876810e2` (`[Engine] preserve exact tool-name masks for Responses namespaces`).
This is source work after the immutable p3 package, not a new p3 installer.

## Change

Allow exact qualified ASCII tool names made of non-empty segments separated by
literal dots. The persistent byte automaton continues to allow only names the
request declared. Duplicate names, empty segments, non-ASCII and grammar/XML
metacharacters remain rejected. Both grammar regex alternations now escape
names, so `diagnostic.ping` cannot also accept `diagnosticXping`.

The existing Responses conversion and namespace/member output mapping are
preserved. No disabling ENV or launcher feature workaround is needed by the fix.
The native engine protocol and C++/Metal code are unchanged.

## Verification

- Before the fix, new regressions failed on namespace activation and both regex
  grammar paths; Responses HTTP round trips were rejected.
- After the fix, 135 focused constraint, JSON and Responses tests passed.
  The legacy fake-engine cases use the documented explicit guard opt-out;
  the new namespace HTTP cases clear the environment and exercise the default.
- Final focused run: all 24 tool-name/namespace tests passed, including literal
  dots with hyphens, custom-call grammar, rejection of malformed names and
  duplicates, persistent exact-name masks, and speculative lookahead rollback.
- Nonstreaming and SSE HTTP tests cover a namespaced call, its arguments, its
  tool result, then a final schema-constrained JSON answer. No native model is
  involved in these fixtures.
- Real `codexnext` CLI against the patched loopback mock returned OK (exit 0),
  where its real-service p3 request had failed the strict-name gate. See
  `fixed-client-mock-20261106.json`. No real model was loaded by this test.
- Refreshed patch applies to pristine v0.2.11 and a second application leaves
  the entire checkout byte-identical.

## Deployment limits

No production service was restarted, no existing installation was altered,
and no release tag, immutable archive or stable channel was moved. The local
mock was stopped. Installed p3 still has the original failure; a new versioned
package and real-model Codex regression run are required before claiming the
hardware installation fixed. The existing uniqueItems/schema fallback is
unchanged. Model metadata and MCP connectivity warnings are separate issues.
