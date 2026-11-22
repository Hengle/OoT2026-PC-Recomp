"""Regression checks for a missing/stale RX_PGO from an older installation."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('engine_build_profile', ROOT / 'tools/alpha/engine_build_profile.py')
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class BuildProfileTests(unittest.TestCase):
    def setUp(self):
        text = (ROOT / 'engine/nx2/build.py').read_text(encoding='utf-8')
        tree = ast.parse(text)
        helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'profile_use_flags')
        self.namespace = {'hashlib': hashlib}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), 'build.py', 'exec'), self.namespace)
        self.flags = self.namespace['profile_use_flags']

    def test_deleted_profile_preserves_normal_optimisation(self):
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as output:
            path = Path(folder) / 'old builder' / 'ocarina-reborn_pieces.prof'
            self.assertEqual(['-O2'] + self.flags(str(path)), ['-O2'])
        self.assertIn('building without PGO', output.getvalue())
        self.assertIn('ocarina-reborn_pieces.prof', output.getvalue())

    def test_unreadable_profile_also_falls_back(self):
        with mock.patch('builtins.open', side_effect=PermissionError('locked profile')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.flags('locked.prof'), [])
        self.assertIn('locked profile', output.getvalue())

    def test_valid_profile_is_used_and_content_changes_invalidate_object_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile with spaces.prof'
            path.write_bytes(b'authored profile one')
            first = self.flags(str(path))
            self.assertEqual(first[0], '-fprofile-instr-use=' + str(path))
            self.assertEqual(first[1], '-DHOOKSHOT_PROFILE_SHA1=' + hashlib.sha1(path.read_bytes()).hexdigest()[:16])
            path.write_bytes(b'authored profile two')
            self.assertNotEqual(self.flags(str(path)), first)

    def test_generator_handles_original_files_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'nx2').mkdir()
            build = (ROOT / 'engine/nx2/build.py').read_text(encoding='utf-8')
            make = (ROOT / 'engine/nx2/make_game.py').read_text(encoding='utf-8')
            old_build = build.replace(patch.PROFILE_HELPER, '').replace(patch.NEW_USE, patch.OLD_USE)
            old_make = make.replace(patch.ENV_OVERRIDE, '')
            self.assertNotEqual(build, old_build)
            self.assertNotEqual(make, old_make)
            (root / 'nx2/build.py').write_text(old_build, encoding='utf-8')
            (root / 'nx2/make_game.py').write_text(old_make, encoding='utf-8')
            patch.apply(root)
            self.assertEqual((root / 'nx2/build.py').read_text(encoding='utf-8'), build)
            self.assertEqual((root / 'nx2/make_game.py').read_text(encoding='utf-8'), make)
            before = {p: p.read_bytes() for p in (root / 'nx2').iterdir()}
            patch.apply(root)
            self.assertEqual(before, {p: p.read_bytes() for p in (root / 'nx2').iterdir()})

    def test_unknown_source_is_rejected_before_either_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'nx2').mkdir()
            build = (ROOT / 'engine/nx2/build.py').read_text(encoding='utf-8')
            build = build.replace(patch.PROFILE_HELPER, '').replace(patch.NEW_USE, patch.OLD_USE)
            (root / 'nx2/build.py').write_text(build, encoding='utf-8')
            (root / 'nx2/make_game.py').write_text('unknown = True\n', encoding='utf-8')
            before = {p: p.read_bytes() for p in (root / 'nx2').iterdir()}
            with self.assertRaises(ValueError):
                patch.apply(root)
            self.assertEqual(before, {p: p.read_bytes() for p in (root / 'nx2').iterdir()})


class ProfileRecordingTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((ROOT / 'engine/nx2/make_game.py').read_text(encoding='utf-8'))
        helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'game_profile_recording')
        namespace = {'os': os, 'json': json, 'ROOT': str(ROOT / 'engine')}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), 'make_game.py', 'exec'), namespace)
        self.recording = namespace['game_profile_recording']
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.install = Path(self.folder.name) / 'installation'
        self.install.mkdir()
        self.manifest = self.install / 'build-info.json'
        self.root = str(self.install / 'engine')
        self.local = Path(self.folder.name) / 'local'
        self.flag = self.local / 'Ocarina Reborn/pgo-gen.flag'
        self.flag.parent.mkdir(parents=True)
        self.env = {'LOCALAPPDATA': str(self.local)}

    def test_private_flag_enables_recording_only_when_present(self):
        self.manifest.write_text(json.dumps({'release_type': 'private-test'}), encoding='utf-8-sig')
        self.assertFalse(self.recording(self.env, self.root))
        self.flag.touch()
        self.assertTrue(self.recording(self.env, self.root))

    def test_public_flag_is_ignored_without_deleting_recording_control(self):
        self.manifest.write_text(json.dumps({'release_type': 'public'}), encoding='utf-8')
        self.flag.touch()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertFalse(self.recording(self.env, self.root))
        self.assertIn('not a private test build', output.getvalue())
        self.assertTrue(self.flag.exists())

    def test_missing_or_invalid_manifest_does_not_enable_recording(self):
        self.flag.touch()
        for contents in (None, 'not json', '[]', 'null', '{}', '{"release_type": "preview"}'):
            with self.subTest(manifest=contents), contextlib.redirect_stdout(io.StringIO()):
                if contents is None:
                    self.manifest.unlink(missing_ok=True)
                else:
                    self.manifest.write_text(contents, encoding='utf-8')
                self.assertFalse(self.recording(self.env, self.root))

    def test_explicit_recording_request_overrides_manifest_and_needs_no_flag(self):
        for contents in (None, 'not json', '{"release_type": "public"}', '{"release_type": "private-test"}'):
            with self.subTest(manifest=contents):
                if contents is None:
                    self.manifest.unlink(missing_ok=True)
                else:
                    self.manifest.write_text(contents, encoding='utf-8')
                self.assertTrue(self.recording({'OCARINA_PGO_GEN': '1'}, self.root))
        self.assertFalse(self.recording({'OCARINA_PGO_GEN': '0'}, self.root))


if __name__ == '__main__':
    unittest.main()
