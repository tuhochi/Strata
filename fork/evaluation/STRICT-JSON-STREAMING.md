# Strict JSON streaming follow-up after p3

The decoding principle remains the one used by llama.cpp: constrain candidate
tokens before emission, then stream accepted output. This change does not add
whole-answer buffering, retries, or a replacement grammar library.

A regression reproduced the p3 failure: llguidance 1.9.1 rejects uniqueItems,
and Service._with_constraint returned sampling without a constraint even for
json_schema.strict=true. That compilation fallback now raises ValueError for
strict schemas before engine.generate is invoked. It does not fabricate support
for uniqueItems. The existing tools-plus-JSON branch already propagates compiler
errors. Non-strict fallback behavior is unchanged.

This is source work after the immutable p3 release. No new Mac package has been
built or installed, and no new model benchmark is claimed. The prior p3 package
still has its recorded behavior.

Validation: the new unsupported-schema regression failed on p3 and passed after
the change. A supported strict array schema rejects an early closing bracket
at token selection and permits completion with three values. All 19 tool-name
constraint tests pass with real llguidance; 68 legacy constraint/structured-output
tests pass with the documented explicit tool-name opt-out for fake engines.

Limits: this is not full JSON Schema support or byte-identical llama.cpp behavior.
The inherited JSON-only no-capability fallback and runtime matcher-failure
fallbacks remain separate paths. Complete post-validation is still optional in
the installed p3 package. A stream can fail after its HTTP headers or partial
content; this change does not promise HTTP 400 for every protocol/stream path.
