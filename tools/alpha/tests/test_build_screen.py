"""The build screen's progress: ocarina_prepare.py's messages (file counts, steps an update does not have) and how
build_screen.py turns them into rows, counter and bar; the artwork pack and its provenance."""
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ALPHA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ALPHA / 'launcher'))
import build_screen  # noqa: E402


def prepare_module():
    spec = importlib.util.spec_from_file_location('prepare_for_screen', ALPHA / 'ocarina_prepare.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def feed(lines):
    m = prepare_module()
    messages = []
    with patch.object(m, 'out', side_effect=lambda **kw: messages.append(kw)):
        p = m.Progress()
        for line in lines:
            p.line(line)
    return messages


class PrepareProgress(unittest.TestCase):
    def test_file_count_runs_to_all_files_of_an_update(self):
        # "@@plan <rebuilt> <all>": every file reports one @@file line; counting against <rebuilt> showed 761 / 382
        lines = ['@@stage read x', '@@stage lift x', '@@stage compile x', '@@plan 2 4']
        lines += [f'@@file f{i}.c 1.0 {"new" if i < 2 else "cached"}' for i in range(4)]
        counts = [(m['count'], m['total']) for m in feed(lines) if 'count' in m]
        self.assertEqual(counts[-1], (4, 4))
        self.assertTrue(all(c <= t for c, t in counts))

    def test_a_file_built_again_is_not_counted_twice(self):
        lines = ['@@stage compile x', '@@plan 2 2', '@@file a.c 1.0 new', '@@file b.c 1.0 failed', '@@file b.c 3.0 again']
        counts = [(m['count'], m['total']) for m in feed(lines) if 'count' in m]
        self.assertEqual(counts[-1], (2, 2))

    def test_a_step_never_started_is_skipped_not_done(self):
        # an update starts at "read": no NUP check ran, so it must not be ticked off
        messages = feed(['@@stage read x', '@@stage lift x'])
        self.assertIn({'skip': 'nup'}, messages)
        self.assertNotIn({'done': 'nup'}, messages)
        self.assertIn({'done': 'extract'}, messages)

    def test_a_full_build_ticks_off_the_nup_check(self):
        messages = feed(['@@check ok Ocarina of Time 1.0', '@@stage read x'])
        self.assertIn({'done': 'nup'}, messages)
        self.assertNotIn({'skip': 'nup'}, messages)


class FakeScreen(build_screen.BuildScreen):
    """BuildScreen's message handling without a window"""
    def __init__(self, cmd=()):
        self.cmd, self.de = list(cmd), True
        self.T = lambda d, e: d
        self.state = {s: 'wait' for s, _ in build_screen.STEPS}
        self.step_frac = {s: 0.0 for s, _ in build_screen.STEPS}
        self.measured = {s: False for s, _ in build_screen.STEPS}
        self.done_at, self.counter, self.target, self.phase, self.error, self.note = {}, '', 0.0, 'run', '', ''
        self.log_lines, self.finished_at, self.closing_app, self.proc = [], None, False, None

    def write_log(self, text):
        self.log_lines.append(text)


class ScreenState(unittest.TestCase):
    def test_counter_never_exceeds_its_total(self):
        s = FakeScreen()
        s.handle({'step': 'build', 'frac': 1.0, 'total_pct': 70, 'count': 761, 'total': 760, 'unit': 'files'})
        self.assertEqual(s.counter, '760 / 760 Dateien')

    def test_overall_value_only_grows_and_stays_within_0_100(self):
        s = FakeScreen()
        s.handle({'step': 'build', 'frac': 0.5, 'total_pct': 50})
        s.handle({'step': 'build', 'frac': 0.4, 'total_pct': 40})
        self.assertEqual(s.target, 50)
        s.handle({'step': 'shaders', 'frac': 1.0, 'total_pct': 130})
        self.assertEqual(s.target, 100)

    def test_unmeasured_step_shows_no_percentage(self):
        s = FakeScreen()
        s.handle({'step': 'finish', 'frac': 0.0, 'total_pct': 70})
        self.assertEqual(s.state['finish'], 'run')
        self.assertFalse(s.measured['finish'])   # (indeterminate: the spinner, no invented %)
        s.handle({'step': 'shaders', 'frac': 0.25, 'total_pct': 79})
        self.assertTrue(s.measured['shaders'])

    def test_skipped_step_is_not_completed_by_the_finish(self):
        s = FakeScreen()
        s.handle({'skip': 'nup'})
        s.handle({'step': 'extract', 'frac': 0.1, 'total_pct': 4})
        s.handle({'finished': True})
        self.assertEqual(s.state['nup'], 'skipped')
        self.assertEqual(s.state['extract'], 'done')
        self.assertEqual((s.phase, s.target), ('done', 100.0))

    def test_error_marks_its_step_failed(self):
        s = FakeScreen()
        s.handle({'step': 'build', 'frac': 0.3, 'total_pct': 40})
        s.handle({'error': 'failed: the compiler stopped', 'step': 'build'})
        self.assertEqual((s.phase, s.state['build'], s.error), ('failed', 'failed', 'the compiler stopped'))

    def test_exit_without_finish_is_a_failure(self):
        s = FakeScreen()
        s.handle({'exit': 3})
        self.assertEqual(s.phase, 'failed')

    def test_nothing_changes_after_a_cancel(self):
        s = FakeScreen()
        s.handle({'step': 'build', 'frac': 0.3, 'total_pct': 40})
        s.cancel_now()
        s.handle({'finished': True})
        self.assertEqual((s.phase, s.state['build']), ('cancelled', 'cancelled'))

    def test_build_log_path_follows_the_command(self):
        self.assertEqual(build_screen.BuildScreen.find_build_log(['p', '--logs', 'X']), Path('X') / 'build.log')
        self.assertEqual(build_screen.BuildScreen.find_build_log(['p', '--replay', 'R.log']), Path('R.log'))


class Artwork(unittest.TestCase):
    def test_pack_loads_with_the_reference_layout(self):
        arrays, geom = build_screen.load_pack(ALPHA / 'launcher' / 'assets' / 'build-forest.pack')
        self.assertEqual(arrays['bg'].shape, (941, 1672, 3))
        self.assertEqual(geom['size'], [1672, 941])
        self.assertEqual(len(geom['rows']), len(build_screen.STEPS))

    def test_pack_and_reference_are_recorded(self):
        manifest = json.loads((ALPHA / 'MEDIA-PROVENANCE.json').read_text(encoding='utf-8'))
        for rel in ('tools/alpha/launcher/assets/build-forest.pack', 'tools/alpha/art-src/build-forest-reference.png'):
            digest = hashlib.sha256((ALPHA.parents[1] / rel).read_bytes()).hexdigest()
            self.assertEqual(manifest['files'].get(rel), digest, rel)

    def test_png_writer_round_trips_through_tk(self):
        import numpy as np
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest('no display')
        try:
            a = np.zeros((3, 4, 4), np.uint8)
            a[1, 2] = (10, 20, 30, 128)
            img = build_screen.to_photo(root, a)
            self.assertEqual((img.width(), img.height()), (4, 3))
            self.assertEqual(tuple(img.get(2, 1))[:3], (10, 20, 30))
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
