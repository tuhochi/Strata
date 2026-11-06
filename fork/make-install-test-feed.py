#!/usr/bin/env python3
"""Sign a loopback-only installer fixture on bolder; private key never reaches the Mac."""
import argparse
import json
import pathlib
import shutil
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'packaging'))
import feed_tool
from strata_control import signing, feed

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--release', type=pathlib.Path, required=True)
p.add_argument('--out', type=pathlib.Path, required=True)
p.add_argument('--origin', required=True)
p.add_argument('--key', type=pathlib.Path, required=True)
a = p.parse_args()
u = urllib.parse.urlsplit(a.origin)
if u.scheme != 'http' or u.hostname != '127.0.0.1' or u.path not in ('', '/'):
    raise SystemExit('Installer fixtures must use an explicit loopback HTTP origin')
if a.out.exists(): raise SystemExit('Fixture destination already exists')
shutil.copytree(a.release, a.out)
doc = json.loads((a.out / 'strata-feed.json').read_text())
for kind in ['control', 'engine']:
    for package in doc[kind]['packages']:
        package['url'] = a.origin.rstrip('/') + '/' + kind + '/' + package['url'].rsplit('/', 1)[-1]
payload = json.dumps(doc, indent=1).encode() + b'\n'
key = feed_tool._load_key(a.key)
(a.out / 'strata-feed.json').write_bytes(payload)
(a.out / 'strata-feed.json.sig').write_text(json.dumps(signing.sign_bytes(key, payload)) + '\n')
lines = [' '.join([x['platform'], doc['control']['version'], x['url'], x['sha256'], str(x['size'])]) for x in doc['control']['packages']]
(a.out / 'install-manifest.txt').write_text('\n'.join(lines) + '\n')
trusted = signing.load_trusted_keys(ROOT / 'strata_control/update_keys.json', environ={})
feed.fetch(str(a.out), trusted)
print('Signed loopback fixture:', a.out)
