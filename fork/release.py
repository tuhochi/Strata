#!/usr/bin/env python3
"""Build on a Mac over SSH, retrieve artifacts, and sign an immutable release on bolder.

Build: python fork/release.py build --builder atlas
Stage: python fork/release.py stage --artifacts ~/.cache/strata-fork/<source>/artifacts --key ~/.config/strata-fork/tuhochi/feed-key.json
Publish only after testing: git add releases fork/LATEST; git commit; git tag vX-pN; git push origin HEAD:patched vX-pN
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'packaging'))
import feed_tool
from strata_control import engine_component, feed, signing


def metadata():
    d = json.loads((ROOT / 'fork/release.json').read_text())
    if not re.fullmatch(r'v[0-9]+(?:\.[0-9]+){2,3}-p[1-9][0-9]*', d['release']):
        raise SystemExit('Invalid release label')
    feed.version_key(d['component_version'])
    return d


def source_commit():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def build(builder):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', builder):
        raise SystemExit('Use an SSH host alias')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise SystemExit('Commit the exact source before building')
    sha = source_commit()
    remote = f'builds/strata-fork/sources/{sha}'
    subprocess.run(['ssh', builder, 'mkdir -p "$HOME/' + remote + '"'], check=True)
    archive = subprocess.Popen(['git', 'archive', sha], cwd=ROOT, stdout=subprocess.PIPE)
    subprocess.run(['ssh', builder, 'tar -x -C "$HOME/' + remote + '"'], stdin=archive.stdout, check=True)
    archive.stdout.close()
    if archive.wait():
        raise SystemExit('Source archive failed')
    command = f'STRATA_SOURCE_COMMIT={sha} bash "$HOME/{remote}/fork/build-macos.sh"'
    subprocess.run(['ssh', builder, command], check=True)
    local = pathlib.Path.home() / '.cache/strata-fork' / sha / 'artifacts'
    local.mkdir(parents=True, exist_ok=True)
    subprocess.run(['rsync', '-az', f'{builder}:builds/strata-fork/artifacts/{sha}/', str(local) + '/'], check=True)
    print('Retrieved verified build outputs:', local)


def stage(artifacts, key_path):
    meta = metadata()
    version, label = meta['component_version'], meta['release']
    engine = artifacts / 'engine' / f'{version}-macos-arm64-metal'
    provenance = json.loads((engine / 'BUILD.json').read_text())
    sha = source_commit()
    if provenance['source_commit'] != sha:
        raise SystemExit('Artifacts do not match the current source commit')
    dsv41 = artifacts / 'dsv41' / f'{version}-macos-arm64-metal'
    if not dsv41.is_dir():
        raise SystemExit(f'Missing DeepSeek engine package: {dsv41}')
    dsv41_component = engine_component.read_manifest(dsv41)
    if (dsv41_component.version, dsv41_component.platform, dsv41_component.backend, dsv41_component.build_id) != (
            version, 'macos-arm64', 'metal', sha):
        raise SystemExit('DeepSeek engine does not match this release version, platform, backend and source commit')
    if dsv41_component.entrypoint != 'strata-dsv41':
        raise SystemExit('DeepSeek package entrypoint must be strata-dsv41')
    target = ROOT / 'releases' / label
    if target.exists():
        raise SystemExit('Release folder already exists; releases are immutable')
    key = feed_tool._load_key(key_path)
    trusted = signing.load_trusted_keys(ROOT / 'strata_control/update_keys.json', environ={})
    if key['key_id'] not in trusted:
        raise SystemExit('Signing key is not trusted by this Control build')
    previous = ROOT / 'releases/stable/strata-feed.json'
    sequence = json.loads(previous.read_text())['sequence'] + 1 if previous.exists() else 1
    cache = pathlib.Path.home() / '.cache/strata-fork'
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sign-release-', dir=cache) as tmp:
        work = pathlib.Path(tmp)
        release = work / 'release'
        release.mkdir()
        signed_engine = work / 'engine'
        shutil.copytree(engine, signed_engine)
        feed_tool.sign_package(signed_engine, key)
        prefix = f'https://raw.githubusercontent.com/{meta["repository"]}/{label}/releases/{label}/'
        e = feed_tool.pack_engine(signed_engine, release / 'engine', url_prefix=prefix + 'engine/')
        signed_dsv41 = work / 'dsv41'
        shutil.copytree(dsv41, signed_dsv41)
        feed_tool.sign_package(signed_dsv41, key)
        ds = feed_tool.pack_engine(signed_dsv41, release / 'dsv41', url_prefix=prefix + 'dsv41/', prefix='strata-dsv41')
        archive = artifacts / 'control' / f'strata-terminal-{version}-darwin-arm64.tar.gz'
        unpack = work / 'control'
        unpack.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(unpack, filter='data')
        bundle = unpack / f'strata-terminal-{version}-darwin-arm64'
        if (bundle / 'COMMIT').read_text().strip() != sha:
            raise SystemExit('Control and engine came from different commits')
        c = feed_tool.pack_control(bundle, release / 'control', version=version, platform='macos-arm64', url_prefix=prefix + 'control/')
        doc = feed_tool.build_feed(release, key=key, sequence=sequence, engine_dir=release / 'engine',
                                   dsv41_dir=release / 'dsv41', control_dir=release / 'control')
        if len(doc.get('dsv41', {}).get('packages', [])) != 1:
            raise SystemExit('The signed feed must contain the DeepSeek engine package')
        shutil.copy2(ROOT / 'packaging/install.sh', release / 'install.sh')
        shutil.copy2(ROOT / 'fork/install.sh', release / 'install-fork.sh')
        report = {'release': label, 'source_commit': sha, 'provenance': provenance,
                  'component_version': version, 'feed_sequence': sequence, 'engine': e, 'dsv41': ds, 'control': c,
                  'models': ['Qwen3.8-Flash-Next', 'Qwen3.6-35B-A3B', 'DeepSeekV4.1-Flash-1017'],
                  'scope': 'Apple Silicon macOS 15+; Qwen3.8 and Qwen3.6 share the Metal engine; DeepSeek V4.1 is a separate Metal engine package. No CUDA/HIP/SYCL runtime claim.'}
        (release / 'BUILD-REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
        lines = []
        for p in sorted(release.rglob('*')):
            if p.is_file():
                lines.append(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(release).as_posix())
        (release / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
        feed.fetch(str(release), trusted)
        target.parent.mkdir(exist_ok=True)
        shutil.copytree(release, target)
    stable = ROOT / 'releases/stable'
    stable.mkdir(exist_ok=True)
    for name in ['strata-feed.json', 'strata-feed.json.sig', 'install-manifest.txt']:
        shutil.copy2(target / name, stable / name)
    (ROOT / 'fork/LATEST').write_text(label + '\n')
    print('Staged immutable signed release:', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build'); b.add_argument('--builder', default='atlas')
    s = sub.add_parser('stage'); s.add_argument('--artifacts', type=pathlib.Path, required=True); s.add_argument('--key', type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.cmd == 'build': build(args.builder)
    else: stage(args.artifacts.resolve(), args.key.resolve())
