"""Counter timing/carry/lifecycle and reproducible GIF integration, without game data."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
import engine_rupee_hud as patch


class RupeeHudTests(unittest.TestCase):
    def test_gif_atlas_preserves_transparency_timing_and_stays_small(self):
        atlas, durations, w, h, cw, ch, cols = patch.atlas_data()
        self.assertEqual(durations, [170] * 9)
        self.assertLess(len(atlas.tobytes()), 320 * 1024)
        self.assertEqual(atlas.getpixel((0, 0))[3], 0)
        for i in range(9):
            cell = atlas.crop(((i % cols) * cw, (i // cols) * ch,
                               (i % cols + 1) * cw, (i // cols + 1) * ch))
            self.assertIsNotNone(cell.getchannel('A').getbbox())
        self.assertEqual(patch.HEADER.read_text(encoding='utf-8'), patch.header_text())

    def test_fresh_patch_and_idempotence(self):
        files = sorted(set(rel for rel, _, _ in patch.CHANGES))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for rel in files:
                authored = (ROOT / 'engine' / rel).read_text(encoding='utf-8')
                before = authored
                for changed, old, new in reversed(patch.CHANGES):
                    if changed == rel:
                        self.assertEqual(before.count(new), 1, rel)
                        before = before.replace(new, old, 1)
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(before, encoding='utf-8')
            for _ in range(2):
                patch.apply(root)
                for rel in files:
                    self.assertEqual((root / rel).read_text(encoding='utf-8'),
                                     (ROOT / 'engine' / rel).read_text(encoding='utf-8'))

    def test_native_roll_carry_reverse_retarget_and_lifecycle(self):
        compiler = shutil.which('clang++')
        if not compiler:
            self.skipTest('clang++ required')
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / 'test.cpp').write_text(HARNESS, encoding='utf-8')
            exe = p / ('test.exe' if os.name == 'nt' else 'test')
            built = subprocess.run([compiler, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                                    '-I', str(ALPHA / 'hud'), str(p / 'test.cpp'), '-o', str(exe)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


HARNESS = r'''
#include "ocr_rupee_roll.h"
#include <cassert>
#include <limits>
using namespace ocr_hud;
int main() {
    RupeeRoll r;
    assert(r.update(10, 0, 0) == 10); // first load never rolls from zero
    assert(r.update(20, 0.1, 0) == 10);
    const double halfway = r.update(20, 0.285, 0);
    assert(halfway > 14.9 && halfway < 15.1);
    assert(r.update(20, 0.6, 0) == 20);
    r.update(0, 0.7, 0);
    const double down = r.update(0, 0.9, 0);
    assert(down > 0 && down < 20);
    assert(r.update(50, 0.9, 0) == down); // mid-flight target cannot jump
    assert(r.update(50, 1.5, 0) == 50);
    assert(r.update(7, 1.6, 1) == 7); // new save, even if -1 was not rendered
    r.reset(); assert(r.update(300, 1.7, 1) == 300);
    r.update(400, 1.8, 1);
    assert(r.update(400, 5.0, 1) == 400); // paused window catches up
    assert(r.update(10000, 5.1, 1) == -1);
    assert(r.update(0, 5.2, 1) == 0);
    assert(r.update(-1, 5.3, 1) == -1);
    assert(r.update(90, 5.4, 1) == 90);
    assert(r.update(90, std::numeric_limits<double>::quiet_NaN(), 1) == -1);
    auto d = rupee_digit(19.5, 10);
    assert(d.lower == 1 && d.upper == 2 && d.fraction == 0.5);
    d = rupee_digit(19.5, 1);
    assert(d.lower == 9 && d.upper == 0 && d.fraction == 0.5);
    d = rupee_digit(99.5, 100);
    assert(d.blank_lower && d.upper == 1 && d.fraction == 0.5);
    d = rupee_digit(10, 1); assert(d.lower == 0 && d.fraction == 0);
    d = rupee_digit(90, 10); assert(d.lower == 9 && d.fraction == 0);
    for (int fps : {15, 30, 60, 144, 240}) {
        RupeeRoll a; a.update(0, 0, 0); a.update(9999, 0, 0);
        double prev = 0;
        for (int i = 1; i <= fps; ++i) {
            double v = a.update(9999, double(i) / fps, 0);
            assert(v >= prev && v <= 9999); prev = v;
            if (i == fps) assert(v == 9999);
        }
    }
}
'''


if __name__ == '__main__':
    unittest.main()
