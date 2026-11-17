"""Managed HUD install, rollback and range-download checks; no game assets/network."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import classic_ui as mod
import mods_manager


class MemoryArchive(mod.Archive):
    def __init__(self, resource_table=False):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('padding.zs', b'X' * 300000)
            for logo, _, folder in mod.LOGOS:
                for style, _, hud in mod.STYLES:
                    for n in range(4):
                        archive.writestr(f'{folder}/{hud}/romfs/UI/item{n}.zs', f'{logo}-{style}-{n}'.encode())
                    if resource_table:
                        archive.writestr(f'{folder}/{hud}/romfs/System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs', b'table')
        self.data = stream.getvalue()
        self.spec = {'id': 123, 'bytes': len(self.data), 'tail_sha256': hashlib.sha256(self.data[-mod.TAIL:]).hexdigest()}
        self.reads = []

    def open_range(self, start, size):
        self.reads.append((start, size))
        return io.BytesIO(self.data[start:start+size])


class ClassicUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game'
        self.original = self.game / 'romfs/UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.blarc.zs'
        self.original.parent.mkdir(parents=True)
        self.original.write_bytes(b'original-game-file')
        self.save = self.game / 'user/save/account.sav'
        self.save.parent.mkdir(parents=True)
        self.save.write_bytes(b'players-save')
        self.other = self.game / 'mods/OtherHUD/romfs/custom.zs'
        self.other.parent.mkdir(parents=True)
        self.other.write_bytes(b'other-mod')
        self.cache = self.root / 'cache'
        self.archive = MemoryArchive()
        self.running = patch('save_manager.game_running', return_value=False)
        self.running.start()
        self.addCleanup(self.running.stop)

    def install(self, **kwargs):
        return mod.install(self.game, self.cache, kwargs.pop('selection', dict(mod.DEFAULT)),
                           archive=self.archive, **kwargs)

    def preserved(self):
        self.assertEqual(self.original.read_bytes(), b'original-game-file')
        self.assertEqual(self.save.read_bytes(), b'players-save')
        self.assertEqual(self.other.read_bytes(), b'other-mod')

    def test_all_twelve_variants_are_separate(self):
        entries = self.archive.entries()
        for logo, _, _ in mod.LOGOS:
            for style, _, _ in mod.STYLES:
                chosen = mod.selected_entries(entries, dict(controller='switch', logo=logo, style=style))
                self.assertEqual(len(chosen), 4)
                self.assertEqual([rel for _, rel in chosen], [f'romfs/UI/item{n}.zs' for n in range(4)])

    def test_install_off_on_and_variant_replacement_preserve_other_files(self):
        result = self.install()
        self.assertTrue(result['complete'] and result['enabled'])
        self.assertEqual((result['path'] / 'romfs/UI/item0.zs').read_bytes(), b'vanilla-black-0')
        self.assertFalse(mod.set_enabled(self.game, False)['enabled'])
        self.assertTrue(mod.set_enabled(self.game, True)['enabled'])
        result = self.install(selection=dict(mod.DEFAULT, style='blue'))
        self.assertEqual((result['path'] / 'romfs/UI/item0.zs').read_bytes(), b'vanilla-blue-0')
        self.assertEqual(len(mods_manager.list_mods(self.game / 'mods')), 2)
        self.assertFalse(list((self.game / 'mods').glob('_classic-ui-*')))
        self.preserved()

    def test_cached_members_need_no_network_and_are_rechecked(self):
        info = mod.selected_entries(self.archive.entries(), mod.DEFAULT)[0][0]
        cached = self.archive.fetch(info, self.cache, None, lambda n: None)
        with patch.object(self.archive, 'open_range', side_effect=AssertionError('network')):
            self.assertEqual(self.archive.fetch(info, self.cache, None, lambda n: None), cached)
        cached.write_bytes(b'X' * info.file_size)
        self.archive.fetch(info, self.cache, None, lambda n: None)
        self.assertTrue(mod.verify_member(cached, info))

    def test_tampered_directory_rejected(self):
        self.archive.data = self.archive.data[:-1] + b'!'
        with self.assertRaisesRegex(mod.ModError, 'archive has changed'):
            self.install()
        self.preserved()

    def test_corrupt_member_rejected_before_install(self):
        chosen = mod.selected_entries(self.archive.entries(), mod.DEFAULT)
        info = chosen[0][0]
        offset = info.header_offset + 30 + len(info.filename.encode())
        self.archive.data = self.archive.data[:offset] + b'!' + self.archive.data[offset+1:]
        with patch.object(self.archive, 'entries', return_value=[i for i, _ in chosen]):
            with self.assertRaisesRegex(mod.ModError, 'checksum'):
                self.install()
        self.assertFalse(mod.state(self.game)['installed'])
        self.preserved()

    def test_cancel_during_download_keeps_existing_variant(self):
        old = self.install()
        event = threading.Event()
        with self.assertRaises(mod.Cancelled):
            self.install(selection=dict(mod.DEFAULT, style='blue'), cancel=event,
                         progress=lambda *_: event.set())
        self.assertEqual(mod.state(self.game)['selection'], old['selection'])
        self.preserved()

    def test_swap_failure_restores_disabled_previous_variant(self):
        self.install()
        mod.set_enabled(self.game, False)
        original_rename = Path.rename
        def fail_staged(path, target):
            if path.parent.name.startswith('_classic-ui-install-'):
                raise OSError('simulated destination failure')
            return original_rename(path, target)
        with patch.object(Path, 'rename', fail_staged):
            with self.assertRaisesRegex(OSError, 'simulated'):
                self.install(selection=dict(mod.DEFAULT, style='blue'))
        result = mod.state(self.game)
        self.assertFalse(result['enabled'])
        self.assertEqual(result['selection'], mod.DEFAULT)
        self.preserved()

    def test_unmanaged_name_collision_is_not_overwritten(self):
        collision = self.game / 'mods' / mod.NAME
        collision.mkdir()
        (collision / 'private.txt').write_text('keep')
        with self.assertRaises(mod.ModError):
            self.install()
        self.assertEqual((collision / 'private.txt').read_text(), 'keep')

    def test_missing_file_can_be_repaired_but_not_enabled(self):
        result = self.install()
        result = mod.set_enabled(self.game, False)
        (result['path'] / 'romfs/UI/item0.zs').unlink()
        with self.assertRaisesRegex(mod.ModError, 'repair'):
            mod.set_enabled(self.game, True)
        self.assertTrue(self.install()['complete'])

    def test_manifest_traversal_rejected(self):
        result = self.install()
        manifest = result['path'] / mod.MARKER
        content = json.loads(manifest.read_text())
        content['files'][0]['path'] = '../other.zs'
        manifest.write_text(json.dumps(content))
        with self.assertRaises(mod.ModError):
            mod.state(self.game)
        self.preserved()

    def test_resource_version_checked_before_download(self):
        self.archive = MemoryArchive(resource_table=True)
        with patch.object(self.archive, 'fetch', side_effect=AssertionError('must not download')):
            with self.assertRaisesRegex(mod.ModError, 'resource-size table'):
                self.install()

    def test_same_game_folder_lock_blocks_toggle_then_releases(self):
        self.install()
        with mod.edit_lock(self.game):
            with self.assertRaises(mod.ModError):
                mod.set_enabled(self.game, False)
        self.assertFalse(mod.set_enabled(self.game, False)['enabled'])

    def test_running_older_game_blocks_changes(self):
        with patch('save_manager.game_running', return_value=True):
            with self.assertRaisesRegex(mod.ModError, 'Close the game'):
                self.install()
        self.assertFalse(mod.state(self.game)['installed'])

    def test_unsafe_paths_rejected(self):
        for name in ('/file', '../file', 'C:/file', 'romfs/../file', 'romfs\\file', 'romfs/x. ', 'romfs//x'):
            with self.subTest(name=name), self.assertRaises(mod.ModError):
                mod.safe_relative(name)

    def test_download_host_restricted(self):
        self.assertTrue(mod.allowed_url('https://filecache41.gamebanana.com/mods/test.zip'))
        for url in ('http://gamebanana.com/a', 'https://gamebanana.com.bad/a', 'https://gamebanana.com@bad/a', 'https://bad.com/a'):
            self.assertFalse(mod.allowed_url(url))

    def test_wrong_range_or_whole_archive_response_is_rejected(self):
        archive = mod.Archive('switch')
        for status, content_range in ((200, None), (206, 'bytes 1-4/100')):
            response = io.BytesIO(b'1234')
            response.status, response.url, response.headers = status, archive.url, {'Content-Range': content_range}
            with patch.object(archive.opener, 'open', return_value=response):
                with self.assertRaisesRegex(mod.ModError, 'requested file part'):
                    archive.open_range(0, 4)
                self.assertTrue(response.closed)


if __name__ == '__main__':
    unittest.main()
