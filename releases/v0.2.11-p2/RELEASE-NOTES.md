# Strata v0.2.11-p2

Fixes the fork-added JSON/schema and persistent tool-name mask composition at
32-token vocabulary boundaries. Uses every real token bit, ignores only extra
out-of-vocabulary words, and still rejects truncated or unaligned schema masks.

Three new regression tests failed before the fix and pass afterward. All 94
relevant fork tests and 21 package/version tests pass. The signed installed ARM
package passes the mask-composition regression and all 12 installation checks.

This release does not add uniqueItems support or full JSON post-validation when
the optional jsonschema package is absent. Actual-model JSON-plus-tools comparison
on the owner's macstudio remains pending. No model or server was run on atlas.
The original JSON/tool constraint proposals belong to ncphri (#3800, #4222);
this correction fixes the additional fork integration.

Install explicitly for verification using install-fork.sh --version v0.2.11-p2.
The stable branch is promoted separately after the owner's model test.
