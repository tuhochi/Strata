#!/usr/bin/env python3
"""Refresh the reviewed source patch after resolving an upstream update."""
import hashlib
import json
import pathlib
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
meta = json.loads((root / 'fork/release.json').read_text())
paths = ['.github/workflows/terminal-minimal-server.yml', 'apps/host/tests/component-updates.test.mjs', 'tests/desktop/test_tester_readme.py', 'tests/terminal/launch_support.py', 'tests/terminal/test_launch_dsv41.py', 'tests/terminal/test_launch_tui.py', 'tests/terminal/test_launch_tui_walk.py', 'tests/terminal/test_sycl_package.py', 'tests/terminal/test_update_with_model_ds.py', 'tests/terminal/test_tuiqa_wizard.py', 'tests/terminal/test_bench_stop.py', 'strata_cli/launch/screens.py', 'docs/DETAILS.md', 'include/strata/core/token_mask.hpp', 'include/strata/core/verify.hpp',
         'tools/test_docker_entrypoint.py', 'tools/test_setup_download.py', 'tools/test_setup_unsloth.py', 'requirements.txt', 'serve/constrain.py', 'serve/fake_mask_engine.py', 'serve/responses.py',
         'serve/server.py', 'serve/structured.py', 'serve/test_constrain.py', 'serve/test_ds_parallel.py', 'serve/test_server.py', 'serve/test_structured.py',
         'serve/test_tool_name_constraint.py', 'setup.py', 'src/core/verify.cpp', 'src/program/generate.cpp',
         'sycl/include/strata/core/verify.hpp', 'sycl/src/core/verify.cpp', 'sycl/src/program/generate.cpp',
         'metal/src/engine/window.cpp', 'metal/CMakeLists.txt']
patch = subprocess.check_output(['git', 'diff', '--binary', meta['upstream_commit'], '--', *paths], cwd=root)
if not patch: raise SystemExit('No source changes found')
(root / 'fork/patches/tool-constraints.patch').write_bytes(patch)
manifest = {'upstream_release': meta['upstream_release'], 'upstream_commit': meta['upstream_commit'],
            'upstream_patches': meta['upstream_patches'], 'paths': paths, 'sha256': hashlib.sha256(patch).hexdigest()}
(root / 'fork/patches/manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Refreshed reviewed patch:', manifest['sha256'])
