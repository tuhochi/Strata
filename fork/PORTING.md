# Porting the fork to a newer Strata release

This is the checklist for taking the fork's patches onto a newer
[Niko1221/Strata](https://github.com/Niko1221/Strata) release and shipping a new
patched version (`v0.2.13-p1`, `v0.2.13-p2`, ...). It is written to be followed in
order. Every step says what to run, what to look at and what must be true before
you go on.

Maintenance happens on **bolder** (this checkout). Building happens on **atlas**
(the Apple Silicon Mac, reached over SSH). Real-model acceptance happens on
**macstudio**. Nothing that signs or publishes ever runs on a builder.

## Branch model

| Branch | Role |
| --- | --- |
| `main` | Pure upstream. Only `git fetch` of `Niko1221/Strata` lands here. |
| `fork/vX.Y.Z-pN` | One official tag plus this fork's patches. Work happens here. |
| `patched` | The published stable feed. Only verified releases land here. |

`releases/<tag>/` is immutable once pushed. The signing key, models and build
directories never enter Git.

## Before you start

- [ ] The worktree is clean. `fork/update.py` refuses a dirty one on purpose.
- [ ] `git fetch --no-tags https://github.com/Niko1221/Strata.git` works (network).
- [ ] Python test dependencies are installed: `python -m pip install -r requirements.txt`
      (the suites need at least `regex`, `llguidance`, `jsonschema`, `pytest`).
- [ ] The app dependencies are in place: `npm ci --ignore-scripts` in `apps/host`.
- [ ] The signing key is on this machine and outside Git:
      `~/.config/strata-fork/tuhochi/feed-key.json`.
- [ ] `ssh atlas` answers. `fork/release.py build` drives it over SSH.
- [ ] You know the upstream tag you are porting to. It must match
      `v<numbers>` with two or three dot groups (`v0.2.13`, `v0.2.13.1`).

## 1. Prepare the new branch

```sh
python3 fork/update.py --upstream v0.2.13 --patch 1
```

Without `--upstream` the script takes the latest published upstream release.
What it does: creates `fork/v0.2.13-p1`, merges the tag with `--no-commit
--no-ff`, and **stops for your review if the merge conflicts**. No release exists
yet at that point. On a clean merge it then

- writes `fork/release.json` (`release`, `upstream_release`, `upstream_commit`,
  `patch_revision`, `component_version` = the CMake engine version with the patch
  as the fourth group),
- rewrites `PRODUCT_VERSION` in `strata_cli/__init__.py`,
- regenerates `fork/patches/tool-constraints.patch` and its SHA256 manifest.

## 2. Resolve the conflicts

Read the upstream side first. Never discard an upstream change to make the merge
go away: the fork's own commits say `keep-both` for exactly this reason, and every
past merge records what was kept on each side.

These paths are the known hotspots, because upstream has changed them while the
fork's patches sit in them:

- **Engine**: `src/program/generate.cpp`, `src/core/verify.cpp`,
  `sycl/src/program/generate.cpp`, `sycl/src/core/verify.cpp`,
  `metal/src/engine/window.cpp`, `metal/CMakeLists.txt`
- **Server**: `serve/server.py`, `serve/test_server.py`, `setup.py`,
  `docs/DETAILS.md`
- **TUI**: `strata_cli/launch/screens.py`
- **Tests**: `tests/terminal/test_bench_stop.py`, `test_launch_tui*.py`,
  `test_launch_dsv41.py`, `test_sycl_package.py`, `test_tui2_023*.py`,
  `test_tuiqa_*.py`, `test_update_with_model_ds.py`, `test_drafting_tuned.py`,
  `launch_support.py`, `tests/desktop/test_tester_readme.py`,
  `tools/test_docker_entrypoint.py`, `tools/test_setup_download.py`,
  `tools/test_setup_unsloth.py`, `apps/host/tests/component-updates.test.mjs`

Rules that resolved every earlier conflict:

- The mask machinery (`mask=1`, the `MQ` exchange, `token_mask.hpp`) rides
  **beside** upstream's own decode changes in `generate.cpp` and `verify.cpp`.
  Upstream's guards, window rules and forced-continuation handling keep their
  place.
- Version and feed assertions in tests come from `fork/release.json`, never from
  a hard-coded upstream number (`test_tui2_023_versions.py`,
  `test_tui2_023_old_launcher.py`, `test_drafting_tuned.py`,
  `test_tuiqa_version.py` strips the `-pN` suffix).
- Fork-only paths stay fork-only. `main` must still look like upstream.

## 3. Refresh and check the patch

```sh
python3 fork/refresh-patch.py     # after every conflict resolution
python3 fork/patch.py --check     # applies to a pristine upstream checkout
```

`refresh-patch.py` diffs `git diff <upstream_commit> -- <paths>` over a
**hard-coded path list**. If this port adds, renames or deletes a fork file, add
that path to the list first. A missing path leaves the file out of the patch
without an error; only an entirely empty diff fails.

The manifest's SHA256 must match the committed patch bytes. `fork/test_release_tools.py`
checks both, with and without `core.autocrlf`.

## 4. Check the version plumbing

- [ ] `fork/release.json`: `release`, `upstream_release`, `upstream_commit`,
      `patch_revision`, `component_version` all point at this port.
- [ ] `strata_cli/__init__.py` `PRODUCT_VERSION` is the release without the `v`.
- [ ] `metal/CMakeLists.txt` still builds `STRATA_VERSION="${STRATA_FORK_ENGINE_VERSION}-metal"`.
- [ ] `strata_control/update_keys.json` carries the fork's public key.
- [ ] `fork/README.md` names the new base commit and the new component version.

## 5. Run the tests

All of these run on bolder unless they say otherwise. `TMPDIR` must be outside
any Git repository.

```sh
# main corpus (Terminal, setup, tools, fork)
TMPDIR=/var/tmp STRATA_TOOL_MASK_STRICT=0 python -m pytest tests tools/test_*.py \
  tools/dsv41/test_prompt_skip.py fork/test*.py \
  --ignore=tests/terminal/test_launch_tui_walk.py --junitxml=main.xml -q

# the TUI walk, on its own
STRATA_TOOL_MASK_STRICT=0 python -m pytest tests/terminal/test_launch_tui_walk.py -v

# server suites
STRATA_TOOL_MASK_STRICT=0 python -m unittest discover -s serve -p "test_*.py"

# constraints without any mask environment variable
env -u STRATA_TOOL_MASK -u STRATA_TOOL_NAME_ENUM -u STRATA_TOOL_MASK_STRICT \
  python -m unittest serve.test_tool_name_constraint serve.test_constrain serve.test_structured

# the same three suites with optional jsonschema
STRATA_TOOL_MASK_STRICT=0 python -m unittest serve.test_constrain serve.test_structured \
  serve.test_tool_name_constraint

# the patch export gate, twice
python -m pytest fork/test_release_tools.py -q
git -c core.autocrlf=false -c core.safecrlf=false checkout-index -f --prefix=/tmp/export-check/ -- .
python -m pytest fork/test_release_tools.py -q     # from the export, if you use one

# app host (Node)
cd apps/host && npm ci --ignore-scripts && npm test && cd ../..

# native CPU engine diagnostics (needs a pinned llama.cpp tree)
cmake -S . -B BUILD -DSTRATA_BUILD_TESTS=ON -DSTRATA_NATIVE_EXPERTS=ON -DSTRATA_GGML_DIR=$PINNED_LLAMA
cmake --build BUILD && ctest --test-dir BUILD --output-on-failure
```

On **atlas**: `python3 fork/hardware_probe.py --help` lists the Mac checks.
`python3 fork/verify_terminal.py` and `python3 fork/verify_installation.py`
verify a bundle without starting a server or a model.

Record every number you actually produced in `releases/<tag>/REGRESSION-VALIDATION.json`.
The v0.2.12-p1 file is the template: suites, passed/skipped/failed, the exact
commands, `environment`, `not_run` and `limitations`. Skipped tests are not
passed tests. Nothing goes in that file that you did not run.

## 6. Build on atlas

```sh
python3 fork/release.py build --builder atlas
```

The builder uses an isolated Python environment, pinned runtime and build
requirements, a pinned llama.cpp commit and hash-verified metal-cpp headers. It
builds portable arm64 code for macOS 15+, verifies relocation and CLI imports,
and never starts a server or a model. The artifacts land in
`~/.cache/strata-fork/<SOURCE_COMMIT>/artifacts`. The package's `BUILD.json`
names the source commit, the upstream and patch revisions, the SDK and the
compiler.

## 7. Sign the release

```sh
python3 fork/release.py stage \
  --artifacts ~/.cache/strata-fork/<SOURCE_COMMIT>/artifacts \
  --key ~/.config/strata-fork/tuhochi/feed-key.json
```

`stage` refuses to sign when Control and the engine did not come from the same
source commit. Atlas never receives the key.

## 8. Accept the release on real hardware

Real-model acceptance runs on **macstudio**, never on the builder. Install the
signed packages on a clean prefix, start a model, and record what happened. Then
test the installer with the build tree unavailable. Write the outcome into the
release's validation report. A successful compile is not a model test.

- [ ] `releases/<tag>/REGRESSION-VALIDATION.json` (bolder suites, atlas probes)
- [ ] `releases/<tag>/INSTALLATION-VALIDATION.json` (every `checks[].passed` true)
- [ ] `releases/<tag>/BUILD-REPORT.json`
- [ ] `releases/<tag>/SHA256SUMS` covers every file in the folder

## 9. Publish

```sh
git add releases fork/LATEST
git commit -m '[Other] publish verified v0.2.13-p1 Apple Silicon packages'
git tag -a v0.2.13-p1 -m 'Upstream v0.2.13 plus patch 1'
git push origin HEAD:patched v0.2.13-p1
```

`fork/LATEST` must contain the tag. The tag pattern is `v<major>.<minor>.<patch>-p<N>`.

## 10. Verify the CI

Open <https://github.com/tuhochi/Strata/actions> or query the API:

```sh
curl -s "https://api.github.com/repos/tuhochi/Strata/actions/runs?per_page=10" \
  | jq -r '.workflow_runs[] | [.name,.head_branch,.status,(.conclusion//"-"),.created_at] | @tsv'
```

Three workflows matter:

| Workflow | File | What it proves |
| --- | --- | --- |
| Publish verified fork packages | `.github/workflows/fork-release.yml` | `SHA256SUMS`, the feed signature, and every `INSTALLATION-VALIDATION.json` check passed, before the release and its assets exist |
| Server regressions and minimal runtime | `.github/workflows/terminal-minimal-server.yml` | the server suite on the pushed source |
| Portable monitor client | `.github/workflows/terminal-portable-monitor.yml` | the portable monitor build |

Judge the **final** conclusion of the run for your tag, not the first attempt: a
tag can be re-run, and an earlier run of the same name may belong to another ref.

## Rules that do not bend

- The signing key, model weights and build trees are never committed.
- Published tags and archives are immutable. A fix means a new `-pN`.
- A future upstream pull request contains only the source changes and their
  tests. No `fork/` tooling, no `releases/` archives, no distribution metadata.
- A change that touches an engine file must be built for every backend it
  affects (CUDA, HIP, SYCL) before it is offered upstream.
- Every measurement in a report is one you produced, on the hardware you name.
  Mark anything you only read in the code as unconfirmed.

## One-page checklist

```text
[ ] clean worktree, deps installed, ssh atlas answers, key present
[ ] python3 fork/update.py --upstream vX.Y.Z --patch N
[ ] conflicts resolved keep-both, upstream side read first
[ ] python3 fork/refresh-patch.py  &&  python3 fork/patch.py --check
[ ] release.json / PRODUCT_VERSION / metal version / README checked
[ ] pytest main corpus + TUI walk + unittest serve + constraint suites
[ ] npm test in apps/host; native CPU ctest if the engine changed
[ ] fork/release.py build --builder atlas
[ ] fork/release.py stage --artifacts ... --key ...
[ ] real-model acceptance on macstudio; validation JSONs complete and green
[ ] commit releases + fork/LATEST, tag vX-pN, push origin HEAD:patched vX-pN
[ ] all three CI workflows green for that tag
```
