#!/usr/bin/env python3
"""Verify a relocated Mac Terminal bundle without starting any server or model."""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import tarfile
import tempfile


def verify(archive):
    with tempfile.TemporaryDirectory(prefix='strata-fork-installer-check-') as tmp:
        root = pathlib.Path(tmp)
        with tarfile.open(archive) as tar:
            tar.extractall(root, filter='data')
        bundle = next(p for p in root.iterdir() if p.is_dir())
        command = bundle / 'bin/strata'
        env = {**os.environ, 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'PYTHONNOUSERSITE': '1',
               'STRATA_DATA_DIR': str(root / 'data'), 'STRATA_COMPONENTS_DIR': str(root / 'components')}
        for key in ['PYTHONHOME', 'PYTHONPATH', 'STRATA_PYTHON']:
            env.pop(key, None)
        version = subprocess.check_output([str(command), '--version'], cwd='/tmp', env=env, text=True)
        assert '-p' in version, version
        for args in [['--help'], ['serve', '--help'], ['update', '--help']]:
            subprocess.run([str(command), *args], cwd='/tmp', env=env, check=True, stdout=subprocess.DEVNULL)
        python = bundle / 'python/bin/python3'
        subprocess.run([str(python), '-c',
                        'import llguidance, numpy; from serve.constrain import ToolNameConstraint; '
                        'from strata_control.signing import load_trusted_keys; '
                        'assert load_trusted_keys(); print("Relocated runtime, constraint module and trust key verified")'],
                       cwd=bundle, env=env, check=True)
        print(version.strip())
        print('Installer/bundle checks passed; no server or model was started.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=pathlib.Path)
    verify(p.parse_args().archive)
