#!/usr/bin/env python3
"""Install signed packages from a loopback fixture, without starting Strata servers or models."""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request


def verify(feed, port, prefix, output):
    if sys.platform != 'darwin': raise SystemExit('Run installer verification on the Apple Silicon builder')
    if (prefix / 'terminal/current').exists(): raise SystemExit('Use a fresh installer test prefix')
    prefix.mkdir(parents=True, exist_ok=True)
    for name in ['install', 'bin', 'profiles', 'presets', 'runtime']:
        (prefix / name).mkdir(exist_ok=True)
    origin = 'http://127.0.0.1:' + str(port)
    env = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'STRATA_FEED': origin,
           'STRATA_DATA_DIR': str(prefix), 'STRATA_BIN_DIR': str(prefix / 'bin'),
           'STRATA_COMPONENTS_DIR': str(prefix / 'components'), 'STRATA_INSTALL_DIR': str(prefix / 'install'),
           'STRATA_PROFILE_DIR': str(prefix / 'profiles'), 'STRATA_RUNTIME_DIR': str(prefix / 'runtime'),
           'STRATA_LAUNCH_PRESET_DIR': str(prefix / 'presets'), 'XDG_STATE_HOME': str(prefix / 'state')}
    for key in ['PYTHONHOME', 'PYTHONPATH', 'STRATA_PYTHON', 'STRATA_UPDATE_TRUSTED_KEYS',
                'STRATA_TOOL_MASK', 'STRATA_TOOL_NAME_ENUM', 'STRATA_TOOL_MASK_STRICT']:
        env.pop(key, None)
    checks = []
    def check(case, passed):
        if not passed: raise AssertionError(case)
        checks.append({'case': case, 'passed': True})
        print('PASS', case, flush=True)
    def command(args, cwd=None):
        result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
        if result.returncode:
            print(result.stdout, result.stderr, flush=True)
            result.check_returncode()
        return result.stdout
    server = subprocess.Popen([sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1', '--directory', str(feed)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(origin + '/strata-feed.json', timeout=1).close(); break
            except Exception: time.sleep(.1)
        text = command(['sh', str(feed / 'install.sh')])
        check('feed signature verified with bundled fork public key', 'Signature ok.' in text)
        bundle = (prefix / 'terminal/current').resolve()
        python = bundle / 'python/bin/python3'
        cli = prefix / 'bin/strata'
        command([str(python), '-c', 'from strata_control.updater import discover_run_config; assert discover_run_config() is None'], cwd=bundle)
        check('empty isolated model registry before engine installation', True)
        data = json.loads(command([str(cli), 'update', '--yes', '--no-control', '--feed', origin, '--output', 'json']))
        def modes(value):
            if isinstance(value, dict):
                if 'mode' in value: yield value['mode']
                for v in value.values(): yield from modes(v)
            elif isinstance(value, list):
                for v in value: yield from modes(v)
        check('engine installation tested version only, no model or server start', 'binary-only' in list(modes(data)))
        version = command([str(cli), '--version'])
        check('private bundled Python runtime', str(bundle / 'python') in version)
        guard_probe = ('from serve import constrain as c; from serve.server import ByteTokenizer; '
                       't=ByteTokenizer(); v=c.Vocab(t,set(t.encode("<|im_end|>",parse_special=True))); '
                       'g=c.ToolNameConstraint(v,["sql_query"]); '
                       '[g.feed(x) for x in t.encode("<function=")]; '
                       'assert not c.Constraint.allowed(g.mask(),ord("m")); '
                       'assert c.Constraint.allowed(g.mask(),ord("s"))')
        command([str(python), '-c', guard_probe], cwd=bundle)
        check('packaged ARM llguidance and name guard reject undeclared prefix', True)
        composition_probe = """import base64
from serve import constrain as c
from serve.server import ByteTokenizer, Service
from types import SimpleNamespace
import os
assert not any(k in os.environ for k in ('STRATA_TOOL_MASK', 'STRATA_TOOL_NAME_ENUM', 'STRATA_TOOL_MASK_STRICT'))
class Padded(ByteTokenizer):
    n_vocab = 320
    types = [1] * 256 + [3] * 6 + [0] * 58
    def token_bytes(self, token):
        return bytes([token]) if token < 256 else self.SPECIALS[token - 256].encode() if token < 262 else b''
t = Padded()
v = c.Vocab(t, set(t.encode('<|im_end|>', parse_special=True)))
app = Service.__new__(Service)
app.engine = SimpleNamespace(supports_mask=True)
app.tok, app.stop_ids, app._llg_vocab = t, set(t.encode('<|im_end|>', parse_special=True)), v
g = app._with_constraint({'response_format': {'type': 'json_object'}}, [{'name': 'sql_query'}], False)[c.KEY]
assert isinstance(g, c.ToolNameConstraint)
assert len(g.mask()) == 40
before = g.mask()
r = g.reply(list(b'{"a')).split()
assert r[:2] == ['MKN', '4']
assert all(len(base64.b64decode(row)) == 40 for row in r[2:])
assert g.mask() == before
"""
        command([str(python), '-c', composition_probe], cwd=bundle)
        check('packaged ARM request-driven tool guard and JSON composition work without mask ENV', True)

        manifest = next((prefix / 'components').rglob('engine-component.json'))
        engine = manifest.parent
        script = ('from pathlib import Path; from strata_control import signing, engine_component as ec; '
                  'signing.install_component_verifier(signing.load_trusted_keys()); '
                  'c=ec.read_manifest(Path(__import__("sys").argv[1])); '
                  'ec.verify_signature(c,{ec.ENV_REQUIRE_SIGNED:"1"}); ec.verify(c,full=True)')
        command([str(python), '-c', script, str(engine)], cwd=bundle)
        check('engine signature and every package file verified', True)
        source = (bundle / 'COMMIT').read_text().strip()
        build = json.loads((engine / 'BUILD.json').read_text())
        check('Control and engine share the exact source commit', source == build['source_commit'])
        check('fork release version is visible', build['release'][1:] in version)
        engine_version = command([str(engine / 'strata'), '--version'])
        check('portable Metal binary loads outside build tree', build['component_version'] + '-metal' in engine_version)
        resources = [engine / 'metal/engine-msl/mtp.metal', engine / 'metal/data/draft_vocab.bin',
                     engine / 'metal/kernels/quant.metal', engine / 'metal/ggml-common.h', engine / 'strata-vision']
        check('runtime kernels, vocabulary and picture reader included', all(p.is_file() for p in resources))
        check('prefix with spaces works without compiler or system Python', ' ' in str(prefix))
        output.write_text(json.dumps({'source_commit': source, 'platform': 'macos-arm64', 'checks': checks,
                                      'model_execution': 'not run on atlas by owner instruction; installer starts no models',
                                      'scope': 'signed loopback fixture containing the exact release archives'}, indent=2) + '\n')
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--feed', type=pathlib.Path, required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--prefix', type=pathlib.Path, required=True)
    p.add_argument('--out', type=pathlib.Path, required=True)
    a = p.parse_args()
    verify(a.feed.resolve(), a.port, a.prefix.resolve(), a.out.resolve())
