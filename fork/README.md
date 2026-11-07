# Patched Apple Silicon builds

Version `v0.2.12-p1` is based on upstream `v0.2.12` (commit
`146df3c468739147f520ac3816de806f71232571`), with engine `0.1.58.1-metal`.
It retains p5's parallel request identifiers, including image requests, the
Responses namespace fix and automatic declared-name masking without mask ENV.
The speculative-generation merge preserves both the mask boundary and upstream's
forced-continuation log-probability handling.

[Release verification and limits](evaluation/P1-0212-REGRESSION-RESULTS.md).
Historical real-model measurements describe p3 and are not measurements of this
release. Packages support Apple Silicon Macs with macOS 15 or newer; Intel Macs
are not a target of this fork release.

This fork tracks an official release plus a numbered patch: `v0.2.11-p1`, then
`v0.2.11-p2` for another fix on the same release, or `v0.2.12-p1` for a new base.
Published tags and archives are immutable. Numeric engine and Control package
versions (for example `0.1.57.1`) remain compatible with Strata's updater.

Install the ready-made Terminal and Metal engine on an Apple Silicon Mac with
macOS 15 or newer:

```sh
curl -fL https://raw.githubusercontent.com/tuhochi/Strata/patched/fork/install.sh -o install-strata-fork.sh
sh install-strata-fork.sh
~/.local/bin/strata-fork --version
```

To install this exact release, add `--version v0.2.12-p1`. Without it, installation
and subsequent `strata-fork update` follow this fork's signed stable feed.
An exact-version installation keeps its feed pinned to that release. Model
weights are not included; use `strata-fork launch --help` to select a model or
reuse existing model files. Existing upstream installations are kept separate.
`STRATA_FORK_DATA_DIR` and `STRATA_FORK_BIN_DIR` select installation locations.

The installer downloads prebuilt archives, verifies the update feed's signature,
and installs the Metal component through Strata's normal hash and signature
checks. Runtime Python and dependencies are included. No compiler, Homebrew or
system Python is needed on the target Mac. These are command-line packages, not
an Apple-notarized desktop app. The fork feed's public key is in
`strata_control/update_keys.json`; the private key is kept on the release owner’s
machine, outside Git and outside the builder.

## Tool-name patch

The base is ncphri's PRs [3800](https://github.com/Niko1221/Strata/pull/3800) and
[4222](https://github.com/Niko1221/Strata/pull/4222), pinned in `release.json`.
Their commits and authorship remain in the fork history.
Our additions apply masks to Metal's separate sampling path, wire requests
without a JSON response format, and keep a byte-level name guard active through
prose, thinking, and repeated Qwen XML calls. Speculative masks are computed
against each draft prefix without advancing the live state.

Starting with p3, the Python server activates the persistent name guard automatically
when a request offers `tools`. No mask environment variables are required, whether
started by the fork launcher or a custom service profile. `tool_choice: "none"`
removes the tools and leaves ordinary text unconstrained. JSON masking continues
to follow `response_format` or Responses' `text.format` independently.

The guard requires a token-mask engine and llguidance and refuses unsupported
configurations instead of silently decoding freely. It covers Qwen XML function
names, not DeepSeek DSML or arbitrary JSON tool-call spellings. Literal
`<function=...>` examples in generated text are also constrained. Arguments and
the semantic choice among valid tools are not guaranteed by name masking.

Only the optional server override `STRATA_TOOL_MASK_STRICT=0` disables this extra
name guard for diagnostics; unset or `1` keeps request-driven protection active.
It does not disable JSON masking requested by the client. The older
`STRATA_TOOL_MASK` and `STRATA_TOOL_NAME_ENUM` activation flags are no longer read.
The installer wrapper sets none of these flags. CUDA, HIP and SYCL are not claimed
hardware-tested by this Mac release.

## Maintain on bolder, build on atlas

```sh
python3 fork/update.py --upstream v0.2.12 --patch 1
# Review conflicts and the source diff; never discard upstream changes blindly.
python3 fork/patch.py --check
python3 -m unittest serve.test_tool_name_constraint serve.test_constrain serve.test_structured
python3 -m pytest tests/terminal
# Commit the reviewed source before the build.
python3 fork/release.py build --builder atlas
python3 fork/release.py stage --artifacts ~/.cache/strata-fork/SOURCE_COMMIT/artifacts \
  --key ~/.config/strata-fork/tuhochi/feed-key.json
```

The builder uses an isolated Python environment, pinned runtime/build requirements,
a pinned llama.cpp commit and hash-verified metal-cpp headers. It builds portable
arm64 code with a macOS 15 deployment target, includes the picture reader and kernel
resources, and verifies relocation and CLI imports without starting any server or model on atlas. Atlas never receives
the feed signing key. The package's `BUILD.json` identifies the source commit,
upstream/patch revisions, SDK and compiler. `release.py stage` checks that Control
and engine came from the same source commit before signing.

Real-model acceptance checks run on macstudio, never on atlas.
Run `python3 fork/hardware_probe.py --help` there for those checks.
Then test the installer on a clean Mac installation prefix, including a package
start with the build tree unavailable. Record actual outcomes in the release's
validation report. A successful compile alone is not a model test.

After verification, commit the archives and reports on bolder, tag the artifact
commit, and push the distribution branch and tag:

```sh
git add releases fork/LATEST
git commit -m '[Other] publish verified macOS fork packages'
git tag -a v0.2.12-p1 -m 'Upstream v0.2.12 plus patch 1'
git push origin HEAD:patched v0.2.12-p1
```

`main` remains the upstream branch. The `patched` branch publishes the stable feed;
archives live under `releases/<tag>/` and their feed URLs use immutable release tags.
GitHub Release assets can mirror those same archives. Private signing keys,
models and build directories must never be committed. A future upstream pull
request should contain only relevant source changes and tests, without this
fork's distribution tooling or binary archives.

Independent Mac baseline, frozen stress/control suite, performance protocol and manual switch instructions: [evaluation/README.md](evaluation/README.md). The evidence credits the original contributor and keeps original-PR verification separate from fork verification.

The separate [JSON comparison](evaluation/json/COMPARISON-20261106.md) found
partial improvement, with a remaining array length/uniqueness violation and
mask-width errors for automatic tools plus a JSON schema and for final JSON after
a tool result. The successful tool-name tests do not establish full JSON Schema
or JSON-with-tools correctness.

Patch revision p2 corrects the name/schema mask-width composition, with a failing-then-passing real-llguidance regression test. See the [source audit](evaluation/json/AUDIT-20261106.md). It does not add uniqueItems support; its Mac API comparison must be recorded separately from p1.

The [p3 Mac hardware benchmark](evaluation/P3-HARDWARE-20261106.md) now verifies the frozen name tests and all three JSON-plus-tools cases. One schema array case remains invalid. These results are for this Mac/model; other GPU backends remain unverified.
