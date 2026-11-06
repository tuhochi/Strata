#!/usr/bin/env python3
"""Prepare the next official release plus our patches; stop for review on conflicts."""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

root = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--upstream', help='official tag; omitted: latest published release')
parser.add_argument('--patch', type=int, default=1)
args = parser.parse_args()
if args.patch < 1: raise SystemExit('Patch revision must be positive')
if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root):
    raise SystemExit('Commit or resolve the current work before updating')
release = args.upstream
if not release:
    with urllib.request.urlopen('https://api.github.com/repos/Niko1221/Strata/releases/latest', timeout=30) as response:
        release = json.load(response)['tag_name']
if not re.fullmatch(r'v[0-9]+(?:\.[0-9]+){2,3}', release): raise SystemExit('Invalid upstream tag')
label = release + '-p' + str(args.patch)
subprocess.run(['git', 'fetch', '--no-tags', 'https://github.com/Niko1221/Strata.git', 'refs/tags/' + release], cwd=root, check=True)
upstream = subprocess.check_output(['git', 'rev-parse', 'FETCH_HEAD^{commit}'], cwd=root, text=True).strip()
subprocess.run(['git', 'switch', '-c', 'fork/' + label], cwd=root, check=True)
result = subprocess.run(['git', 'merge', '--no-commit', '--no-ff', upstream], cwd=root)
if result.returncode:
    raise SystemExit('Resolve and review the upstream merge conflicts before building. No release was published.')
meta_path = root / 'fork/release.json'
meta = json.loads(meta_path.read_text())
engine = re.search(r'project\(strata VERSION ([0-9.]+)', (root / 'CMakeLists.txt').read_text()).group(1)
meta.update(release=label, upstream_release=release, upstream_commit=upstream, patch_revision=args.patch,
            component_version=engine + '.' + str(args.patch))
meta_path.write_text(json.dumps(meta, indent=2) + '\n')
p = root / 'strata_cli/__init__.py'
p.write_text(re.sub(r'PRODUCT_VERSION = "[^"]+"', 'PRODUCT_VERSION = "' + label[1:] + '"', p.read_text()))
subprocess.run([sys.executable, str(root / 'fork/refresh-patch.py')], cwd=root, check=True)
print('Prepared', label, 'from', upstream)
print('Review and test the merge, update the macOS wheel lock if required, commit the source, then run fork/release.py build.')
