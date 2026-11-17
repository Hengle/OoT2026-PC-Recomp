"""The capture pool's policy (engine/gpu/vk/ocr_capture_pool_policy.h): how much room the spares get, how many of a class a load
takes at once, which spare a capture takes, which one is given up. The failures it answers, from 2026-11-17's runs (9800X3D + RX
7900 XTX, 32 GB): 61 capture buffers of 16-256 MB made on the submitting threads, 10-63 ms each, because the room (256 MB) never
held a 192 or 256 MB spare and only one spare of a class was made again while a load took several."""
from pathlib import Path
import re, shutil, subprocess, tempfile, unittest

ROOT = Path(__file__).resolve().parents[3]
VK = ROOT / 'engine/gpu/vk'

HARNESS = r'''
#include "ocr_capture_pool_policy.h"
#include <cstdio>
#include <vector>
using namespace ocr_cap_pool;
static int failed = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAILED line %d: %s\n", __LINE__, #x); failed = 1; } } while (0)
int main() {
    const uint64_t G = 1ull << 30;
    // room: one spare of every class fits on 32 GB (the run's PC); small cards and small RAM keep their old limits
    uint64_t all = 0; for (int c = 0; c < kClasses; ++c) all += kClassMb[c] * MB;
    CHECK(spare_budget(31849ull * MB, false) >= all);
    CHECK(spare_budget(31849ull * MB, false) <= 1024 * MB);
    CHECK(spare_budget(16 * G, false) == 128 * MB);
    CHECK(spare_budget(8 * G, false) == 64 * MB);
    CHECK(spare_budget(64 * G, true) == 32 * MB);
    CHECK(class_of(192 * MB) == 4 && class_of(16 * MB) == 0 && class_of(100 * MB) == -1);

    // demand: the start expects one of each class for a minute; nothing asked for after that: none kept
    Demand d;
    uint64_t t = 1000;
    for (int c = 0; c < kClasses; ++c) d.expect(c, t);
    for (int c = 0; c < kClasses; ++c) CHECK(d.target(c, t + 1000) == 1);
    CHECK(d.target(4, t + kDemandMs + 1) == 0);
    // a load takes three 32 MB buffers within a second: three kept ready; a fourth take of the burst stays capped at 3
    Demand e;
    e.ask(1, 5000); e.ask(1, 5400); e.ask(1, 5900);
    CHECK(e.target(1, 6000) == 0);   // (asked, but never ran out: buffers came back in time, none made)
    e.ran_out(1, 5900);
    CHECK(e.target(1, 6000) == 3);
    e.ask(1, 6100);
    CHECK(e.target(1, 6200) == kMaxPerClass);
    // later loads take one at a time: the peak holds for a minute after it was reached, then one is enough
    e.ask(1, 30000);
    CHECK(e.target(1, 30001) == 3);
    e.ask(1, 6100 + kDemandMs + 5000); e.ran_out(1, 6100 + kDemandMs + 5000);
    CHECK(e.target(1, 6100 + kDemandMs + 5001) == 1);

    // pick: an exact class first, never a big spare for a small capture, a bigger spare rather than a new buffer for a load
    std::vector<uint64_t> spares = {256 * MB, 32 * MB, 128 * MB};
    bool bigger = true;
    CHECK(pick(spares.data(), spares.size(), 20 * MB, 32 * MB, true, &bigger) == 1 && !bigger);
    CHECK(pick(spares.data(), spares.size(), 2 * MB, 2 * MB, true, &bigger) == -1);           // (a frame's 2 MB: no 32 MB spare)
    CHECK(pick(spares.data(), spares.size(), 150 * MB, 192 * MB, true, &bigger) == 0 && bigger);   // (no 192: the 256 one)
    CHECK(pick(spares.data(), spares.size(), 150 * MB, 192 * MB, false, &bigger) == -1);       // (RX_VK_CAPTURE_KEEP_OLD: as before)
    CHECK(pick(spares.data(), spares.size(), 300 * MB, 300 * MB, true, &bigger) == -1);

    // least wanted: a size of no class first, then the class asked for longest ago; wanted ones only when allowed
    Demand w;
    w.ask(5, 10000);   // 256 asked at 10 s
    w.ask(1, 20000);   // 32 asked at 20 s
    std::vector<uint64_t> kept = {256 * MB, 32 * MB, 100 * MB};
    CHECK(least_wanted(kept.data(), kept.size(), w, 21000, false) == 2);
    std::vector<uint64_t> kept2 = {256 * MB, 32 * MB};
    CHECK(least_wanted(kept2.data(), kept2.size(), w, 21000, false) == 0);
    CHECK(least_wanted(kept2.data(), kept2.size(), w, 21000, true) == -1);   // (both wanted: neither given up)
    CHECK(least_wanted(kept2.data(), kept2.size(), w, 10000 + kDemandMs + 1, true) == 0);   // (256 no longer wanted)

    // refill order: the class furthest short, the bigger between equals; none when every target is met
    Demand r;
    for (int c = 0; c < kClasses; ++c) r.expect(c, 1000);
    int have[kClasses] = {1, 1, 1, 1, 0, 0};
    CHECK(most_short(have, r, 2000) == 5);
    have[5] = 1;
    CHECK(most_short(have, r, 2000) == 4);
    have[4] = 1;
    CHECK(most_short(have, r, 2000) == -1);
    r.ask(1, 3000); r.ask(1, 3100); r.ran_out(1, 3100);
    CHECK(most_short(have, r, 3200) == 1);
    if (!failed) std::puts("capture pool policy: room, demand, pick, give-up order and refill order passed");
    return failed;
}
'''


class CapturePoolPolicy(unittest.TestCase):
    def test_policy(self):
        compiler = shutil.which('clang++')
        if not compiler:
            self.skipTest('clang++ required')
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / 'test.cpp').write_text(HARNESS, encoding='utf-8')
            build = subprocess.run([compiler, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-static', '-I' + str(VK),
                                    str(p / 'test.cpp'), '-o', str(p / 'test.exe')], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            run = subprocess.run([str(p / 'test.exe')], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_engine_uses_the_policy(self):
        src = (VK / 'vk_memory.cpp').read_text(encoding='utf-8')
        self.assertIn('ocr_cap_pool::spare_budget(', src)
        get = src[src.index('bool cap_buf_get('):src.index('// OCR_CAPTURE_POOL_END')]
        self.assertIn('ocr_cap_pool::pick(', get)
        self.assertIn('cap_demand.ask(', get)
        # a spare is only ever a buffer no submission reads: cap_buf_free is reached from retirement, never from the take path
        self.assertNotIn('cap_buf_free(buffer', get)
        worker = src[src.index('void ocr_cap_worker()'):src.index('void cap_prewarm_kick()')]
        self.assertIn('cap_inflight_bytes = bytes', worker)          # (the one being made counts against the room)
        self.assertRegex(worker, r'cap_next_refill\(now\)')          # (the shortfall worked out again before each refill)
        self.assertEqual(len(re.findall(r'std::thread\(ocr_cap_worker\)', src)), 1)


if __name__ == '__main__':
    unittest.main()
