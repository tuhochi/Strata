"""Exercise patch replay and installer refusal paths without network or model downloads."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseTools(unittest.TestCase):
    @unittest.skipUnless((ROOT / '.git').exists(), 'requires developer Git checkout')
    def test_patch_replays_idempotently_and_rejects_modified_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / 'upstream'
            subprocess.run(['git', 'worktree', 'add', '--detach', str(target), 'v0.2.11'], cwd=ROOT, check=True, capture_output=True)
            try:
                command = [sys.executable, str(ROOT / 'fork/patch.py'), '--target', str(target)]
                subprocess.run(command + ['--check'], check=True, capture_output=True)
                self.assertFalse(subprocess.check_output(['git', 'diff', '--binary'], cwd=target))
                subprocess.run(command, check=True, capture_output=True)
                first = subprocess.check_output(['git', 'diff', '--binary'], cwd=target)
                self.assertTrue(first)
                subprocess.run(command, check=True, capture_output=True)
                self.assertEqual(first, subprocess.check_output(['git', 'diff', '--binary'], cwd=target))
                copy = pathlib.Path(tmp) / 'tools'
                copy.mkdir()
                shutil.copy2(ROOT / 'fork/patch.py', copy / 'patch.py')
                shutil.copytree(ROOT / 'fork/patches', copy / 'patches')
                with (copy / 'patches/tool-constraints.patch').open('ab') as stream:
                    stream.write(b'corrupted patch')
                result = subprocess.run([sys.executable, str(copy / 'patch.py'), '--target', str(target)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('checksum', result.stderr)
                self.assertEqual(first, subprocess.check_output(['git', 'diff', '--binary'], cwd=target))
            finally:
                subprocess.run(['git', 'worktree', 'remove', '--force', str(target)], cwd=ROOT, check=True, capture_output=True)

    def test_invalid_install_requests_fail_before_any_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            marker = root / 'network-attempted'
            for name, script in {
                'uname': 'case "$1" in -s) echo Darwin;; -m) echo arm64;; esac',
                'sw_vers': 'echo 15.0',
                'curl': 'touch "' + str(marker) + '"; exit 90',
            }.items():
                p = bin_dir / name
                p.write_text('#!/bin/sh\n' + script + '\n')
                p.chmod(0o755)
            env = {**os.environ, 'PATH': str(bin_dir) + os.pathsep + os.defpath,
                   'STRATA_FORK_DATA_DIR': str(root / 'install')}
            for args in [['--repo', 'https://example.org/not-github', '--version', 'v0.2.11-p1'],
                         ['--version', 'v0.2.11-p0'], ['--version', '../../untrusted']]:
                result = subprocess.run(['sh', str(ROOT / 'fork/install.sh'), *args], env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(marker.exists())
            result = subprocess.run(['sh', str(ROOT / 'fork/install.sh'), '--help'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertFalse(marker.exists())


if __name__ == '__main__': unittest.main()
