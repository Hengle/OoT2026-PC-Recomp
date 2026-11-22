"""The optional daily-limit override: native context preservation and build guards.

Fixtures contain invented registers/flags, never game content or amiibo dumps.
"""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rules = load('amiibo_rules_test', ROOT / 'engine/nx2/ocr_amiibo_rules.py')
settings = load('amiibo_settings_test', ROOT / 'tools/alpha/launcher/game_settings.py')


class AmiiboRulesTests(unittest.TestCase):
    def test_unknown_build_and_every_changed_anchor_leave_lifter_untouched(self):
        expected = dict(rules.CHECKS)
        for build, damaged in [("unknown", None)] + [(rules.BUILD, pc) for pc in expected]:
            words = dict(expected)
            if damaged is not None:
                words[damaged] ^= 1
            lifter = SimpleNamespace(after={0x8328c870: 'existing hook'})
            image = SimpleNamespace(word=lambda pc: words.get(pc, 0))
            self.assertEqual(rules.install(lifter, image, build), 0)
            self.assertEqual(lifter.after, {0x8328c870: 'existing hook'})

    def test_guards_install_both_entries_without_losing_existing_hooks(self):
        words = dict(rules.CHECKS)
        lifter = SimpleNamespace(after={0x8328c870: 'existing hook'})
        image = SimpleNamespace(word=lambda pc: words.get(pc, 0))
        self.assertEqual(rules.install(lifter, image, rules.BUILD), 1)
        self.assertTrue(lifter.after[0x8328c870].startswith('existing hook\n'))
        once = dict(lifter.after)
        self.assertEqual(rules.install(lifter, image, rules.BUILD), 1)
        self.assertEqual(lifter.after, once)
        self.assertEqual(set(lifter.after), {pc for pc, _ in rules.HOOKS})

    def test_launcher_defaults_persistence_and_graphics_reset(self):
        row = next(r for r in settings.ROWS if r[0] == 'unlimited_amiibo')
        self.assertEqual(settings.current({}, row[0], row[3])[0], 0)
        with tempfile.TemporaryDirectory() as tmp:
            settings.write(tmp, {'unlimited_amiibo': 1, 'volume': 65})
            self.assertEqual(settings.current(settings.read(tmp), row[0], row[3])[0], 1)
            settings.reset(tmp)  # Reset graphics must not silently disable gameplay options.
            self.assertEqual(settings.read(tmp)['unlimited_amiibo'], '1')
            self.assertEqual(settings.read(tmp)['volume'], '65')
            settings.write(tmp, {'unlimited_amiibo': 0})
            self.assertEqual(settings.current(settings.read(tmp), row[0], row[3])[0], 0)

    def test_native_override_and_real_hook_text_preserve_guest_context(self):
        compiler = shutil.which('clang') or shutil.which('gcc')
        if not compiler:
            self.skipTest('C compiler required')
        words = dict(rules.CHECKS)
        lifter = SimpleNamespace(after={})
        rules.install(lifter, SimpleNamespace(word=words.__getitem__), rules.BUILD)
        with tempfile.TemporaryDirectory(prefix='amiibo-rules-') as tmp:
            folder = Path(tmp)
            # Compile production runtime code; substitute only the guest context boundary.
            for name in ('ocr_amiibo_rules.c', 'ocr_amiibo_rules.h'):
                shutil.copy2(ROOT / 'engine/host' / name, folder / name)
            (folder / 'hos.h').write_text(
                '#include <stdint.h>\n'
                'typedef struct { uint64_t x[32], flags[4]; } Ctx;\n')
            body = (ROOT / 'tools/alpha/tests/amiibo_rules_test.c').read_text()
            body = body.replace('/* CLOCK_HOOK */', lifter.after[0x8328c870])
            body = body.replace('/* DATE_HOOK */', lifter.after[0x8328cd30])
            (folder / 'test.c').write_text(body)
            binary = folder / ('test.exe' if os.name == 'nt' else 'test')
            for command in ([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                             str(folder / 'test.c'), '-o', str(binary)], [str(binary)]):
                result = subprocess.run(command, cwd=folder, capture_output=True, text=True,
                                        timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
