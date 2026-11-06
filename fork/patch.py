#!/usr/bin/env python3
"""Apply the reviewed, hash-pinned constraint patch to a pristine upstream checkout."""
import argparse
import hashlib
import json
import pathlib
import subprocess


def apply(target, check=False):
    here = pathlib.Path(__file__).resolve().parent
    patch = here / 'patches/tool-constraints.patch'
    lock = json.loads((here / 'patches/manifest.json').read_text())
    if hashlib.sha256(patch.read_bytes()).hexdigest() != lock['sha256']:
        raise SystemExit('Patch checksum differs from reviewed manifest')
    def git(*args):
        return subprocess.run(['git', '-C', str(target), 'apply', *args, str(patch)], capture_output=True, text=True)
    if git('--reverse', '--check').returncode == 0:
        print('Already patched; no files changed.')
        return
    probe = git('--check')
    if probe.returncode:
        raise SystemExit('Patch conflicts with this source version; nothing applied.\n' + probe.stderr)
    if check:
        print('Patch applies cleanly; no files changed.')
        return
    result = git()
    if result.returncode:
        raise SystemExit(result.stderr)
    print('Applied reviewed constraint patch.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    apply(args.target, args.check)
