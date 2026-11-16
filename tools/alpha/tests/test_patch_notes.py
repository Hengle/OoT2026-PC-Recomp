from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA / 'launcher'))
sys.path.insert(0, str(ALPHA))
import patch_notes as notes
import engine_mark

BODY = '''**Ocarina Reborn v9.9.9 — Test Update**

**⚡ First part**
- Plain line with **Bold words** in it and **more**.
- Second.

## ℹ️ Second part
- Only **one**.

Thanks for testing! \U0001f499

[Ocarina Reborn](https://example.invalid/)

SHA-256: `0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef`
'''


def measure(text, bold):
    return len(text) * (11 if bold else 10)


class PatchNotesTests(unittest.TestCase):
    def test_parse_keeps_structure_and_drops_symbols_links_and_hash(self):
        title, sections = notes.parse(BODY)
        self.assertEqual(title, 'Ocarina Reborn v9.9.9 — Test Update')
        self.assertEqual([s[0] for s in sections], ['First part', 'Second part'])
        first = sections[0][1]
        self.assertEqual(first[0], (True, [('Plain line with ', False), ('Bold words', True), (' in it and ', False),
                                           ('more', True), ('.', False)]))
        self.assertEqual(sections[1][1][-1], (False, [('Thanks for testing!', False)]))
        flat = repr(sections)
        for gone in ('SHA', '0123456789abcdef', 'example.invalid', '\U0001f499', '**'):
            self.assertNotIn(gone, flat)

    def test_wrap_fits_width_and_keeps_every_word_and_space(self):
        body = notes.runs('New **Streaming and memory** modes: **Balanced** and **Lower memory**. Lower memory reduces cache sizes.')
        for width in (120, 260, 400, 5000):
            lines = notes.wrap(body, width, measure)
            for line in lines:
                if sum(len(t.split()) for t, _ in line) > 1:
                    self.assertLessEqual(sum(measure(t, b) for t, b in line), width)
                for a, b in zip(line, line[1:]):
                    self.assertNotEqual(a[1], b[1])   # (neighbours of one weight are one piece)
            text = ' '.join(''.join(t for t, _ in line) for line in lines)
            self.assertEqual(text, 'New Streaming and memory modes: Balanced and Lower memory. Lower memory reduces cache sizes.')

    def test_pages_fit_keep_titles_with_items_and_lose_nothing(self):
        text = (ALPHA / 'PATCHNOTES-1.1.1.md').read_text(encoding='utf-8')
        _, sections = notes.parse(text)
        rows = notes.blocks(sections, 900, measure, 28, 34, 6, 20)
        for height in (150, 300, 420, 700, 5000):
            pages = notes.paginate(rows, height)
            self.assertEqual([r for page in pages for r in page], rows)
            for page in pages:
                self.assertTrue(page)
                self.assertNotEqual(page[-1][0], 'head')
                if len(page) > 1:
                    self.assertLessEqual(sum(r[-1] for r in page), height)
            if len(pages) > 1:   # (about equally full: the last page is not a lone line)
                self.assertGreater(sum(r[-1] for r in pages[-1]), 0.3 * max(sum(r[-1] for r in p) for p in pages))
        self.assertEqual(len(notes.paginate(rows, 5000)), 1)
        self.assertEqual(notes.paginate([], 100), [[]])

    def test_shown_once_after_each_update_and_not_on_a_new_installation(self):
        self.assertFalse(notes.due('1.1.2', None, False))       # (a first installation)
        self.assertTrue(notes.due('1.1.2', None, True))         # (updated from a version that did not keep it)
        self.assertTrue(notes.due('1.1.3', '1.1.2', True))
        self.assertFalse(notes.due('1.1.3', '1.1.3', True))
        self.assertFalse(notes.due('1.1.3-alpha', '1.1.3', True))
        self.assertTrue(notes.due('1.1.2', '1.1.3', True))      # (an older installer over a newer one: its notes are new here)

    def test_launcher_ships_the_notes_of_its_version(self):
        version = (ALPHA / 'VERSION').read_text().strip()
        release = (ALPHA / f'PATCHNOTES-{version}.md').read_text(encoding='utf-8').strip()
        self.assertEqual(notes.bundled(), release)
        title, sections = notes.parse(release)
        self.assertIn(version, title)
        self.assertGreaterEqual(len(sections), 2)

    def test_reset_all_settings_keeps_what_was_shown(self):
        import settings_reset
        self.assertIn('notes_seen_version', settings_reset.KEEP)


class MenuMarkTests(unittest.TestCase):
    FILES = ('vk_imgui.cpp', 'vk_imgui.h', 'vk_ui.h', 'vk_menu.cpp')

    def test_patch_reproduces_authored_engine_and_repeats(self):
        with tempfile.TemporaryDirectory() as tmp:
            vk = Path(tmp) / 'gpu/vk'
            vk.mkdir(parents=True)
            for name in self.FILES:   # (v1.1.1 as released: the engine before the mark)
                (vk / name).write_bytes(subprocess.check_output(['git', 'show', '8b92903:engine/gpu/vk/' + name], cwd=ROOT))
            for _ in range(2):
                engine_mark.apply(tmp)
                for name in self.FILES + ('ocr_mark_rgba.h',):
                    # Later staging passes may also touch the menu. Compare the
                    # mark itself here; portrait has its own patch/roundtrip tests.
                    import engine_portrait
                    import engine_rupee_hud
                    import engine_tester_fixes
                    expected = engine_tester_fixes.pre_perf_text('gpu/vk/' + name) if (ROOT / 'engine/gpu/vk' / name).exists() else ''
                    for rel, old, new in reversed(engine_rupee_hud.CHANGES):
                        if rel == 'gpu/vk/' + name:
                            expected = expected.replace(new, old)
                    for rel, old, new in reversed(engine_portrait.CHANGES):
                        if rel == 'gpu/vk/' + name:
                            expected = expected.replace(new, old)
                    self.assertEqual((vk / name).read_text(encoding='utf-8'),
                                     expected, name)
            ui = (vk / 'vk_ui.h').read_text(encoding='utf-8')
            self.assertNotIn('PathFillConvex(kGold)', ui)   # (the concave outline filled as convex: the broken mark)

    def test_header_is_the_launchers_picture(self):
        try:
            import PIL  # noqa: F401
        except ImportError:
            self.skipTest('Pillow not available')
        self.assertEqual(engine_mark.header_text(), engine_mark.HEADER.read_text(encoding='utf-8'))
        text = engine_mark.HEADER.read_text(encoding='utf-8')
        self.assertIn('ocr_mark_w = %d, ocr_mark_h = %d' % (engine_mark.SIZE, engine_mark.SIZE), text)
        self.assertIn('ocr_mark_rgba[%d]' % (engine_mark.SIZE ** 2 * 4), text)


if __name__ == '__main__':
    unittest.main()
