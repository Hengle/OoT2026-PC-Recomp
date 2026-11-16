"""Real Windows process exclusion, release on exit/crash, and restart handoff."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ALPHA = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'nt', 'Windows startup guard')
class InstanceGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('x86_64-w64-mingw32-clang') or shutil.which('clang')
        if not cc:
            raise unittest.SkipTest('Windows clang needed')
        cls.build = tempfile.TemporaryDirectory()
        cls.exe = Path(cls.build.name) / 'guard.exe'
        subprocess.run([cc, '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I' + str(ALPHA.parents[1] / 'engine/host'),
                        str(ALPHA / 'tests/instance_guard_test.c'), '-luser32', '-o', str(cls.exe)],
                       check=True, capture_output=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, HOS_HEADLESS='1')
        self.env.pop('HOS_RESTART_OF', None)
        self.a = self.copy('Grüße-日本')

    def copy(self, name):
        folder = self.root / name
        folder.mkdir()
        exe = folder / 'game.exe'
        shutil.copyfile(self.exe, exe)
        return exe

    def probe(self, exe=None, *args):
        return subprocess.run([str(exe or self.a), *args], env=self.env,
                              capture_output=True, timeout=10)

    def hold(self, exe=None):
        p = subprocess.Popen([str(exe or self.a), '--hold'], env=self.env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=10)
        self.addCleanup(cleanup)
        self.assertEqual(p.stdout.readline().strip(), b'acquired')
        return p

    def test_same_folder_blocks_game_and_shader_preparation(self):
        self.hold()
        renamed = self.a.with_name('renamed.exe')
        shutil.copyfile(self.exe, renamed)
        for exe, args in ((self.a, ()), (renamed, ()), (self.a, ('--prepare-shaders',))):
            with self.subTest(exe=exe, args=args):
                result = self.probe(exe, *args)
                self.assertEqual(result.returncode, 73)
                self.assertIn(b'already running', result.stderr)
                self.assertIn(b'@@error', result.stdout)

    def test_separate_game_folder_can_run(self):
        self.hold()
        self.assertEqual(self.probe(self.copy('separate')).returncode, 0)

    def test_normal_exit_and_stale_file_allow_next_start(self):
        owner = self.hold()
        owner.communicate(b'\n', timeout=10)
        self.assertEqual(owner.returncode, 0)
        self.assertTrue((self.a.parent / '.ocarina-reborn.instance.lock').is_file())
        self.assertEqual(self.probe().returncode, 0)
        self.assertEqual(self.probe().returncode, 0)

    def test_killed_process_releases_lock(self):
        owner = self.hold()
        owner.kill()
        owner.communicate(timeout=10)
        self.assertEqual(self.probe().returncode, 0)

    def test_restart_waits_for_previous_process(self):
        owner = self.hold()
        env = dict(self.env, HOS_RESTART_OF=str(owner.pid))
        successor = subprocess.Popen([str(self.a)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(.2)
            self.assertIsNone(successor.poll())
            owner.communicate(b'\n', timeout=10)
            stdout, stderr = successor.communicate(timeout=10)
            self.assertEqual(successor.returncode, 0, stderr)
            self.assertEqual(stdout.strip(), b'acquired')
        finally:
            if successor.poll() is None:
                successor.kill()
            successor.communicate(timeout=10)

    def test_missing_restart_parent_does_not_block(self):
        self.env['HOS_RESTART_OF'] = '0'
        self.assertEqual(self.probe().returncode, 0)

    def test_inaccessible_lock_is_not_misreported_as_another_game(self):
        (self.a.parent / '.ocarina-reborn.instance.lock').mkdir()
        result = self.probe()
        self.assertEqual(result.returncode, 74)
        self.assertIn(b'could not reserve', result.stderr)
        self.assertNotIn(b'already running', result.stderr)


if __name__ == '__main__':
    unittest.main()
