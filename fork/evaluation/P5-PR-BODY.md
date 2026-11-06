Metal requests could return undeclared Qwen tools or violate supported JSON
response constraints. This applies token masks during Metal verification and
activates them from `tools` / `response_format`, without extra ENV.

Based on **ncphri's #3800 and #4222**, following llama.cpp's request-driven approach.

Fixes the integration regressions found during verification: Responses namespace
names and discarded GEN/GENI request IDs. Full-suite verification also found a
save-screen wrapping bug and environment-dependent test assumptions; those fixes
are separate commits.

Fork release verification:

| Suite | Passed | Skipped | Failed |
| --- | ---: | ---: | ---: |
| Server | 1,511 | 19 | 0 |
| Terminal/setup/tools/fork corpus | 4,747 | 108 | 0 |
| App host | 1,502 | 110 | 0 |

Also passes 13 signed ARM installer checks, plus minimal-runtime and optional
JSON-validator modes. [Evidence and reproduction commands](https://github.com/tuhochi/Strata/blob/v0.2.11-p5/fork/evaluation/P5-REGRESSION-RESULTS-20261106.md).

No stricter JSON postvalidation is forced: uniqueItems/fallback limits remain
explicit. Current-head Mac model acceptance is pending owner installation;
previous Mac measurements are labelled p3. No CUDA/HIP/SYCL hardware claim.
