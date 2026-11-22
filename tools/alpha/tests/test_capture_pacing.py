"""Exercise the production recording-wait path with a controlled GPU timeline."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile, unittest

ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
import engine_capture_pacing
from engine_tester_fixes import pre_perf_text

class CapturePacingTests(unittest.TestCase):
    def test_gpu_dependencies(self):
        compiler = shutil.which('clang++')
        if not compiler: self.skipTest('clang++ required')
        source = (ROOT/'engine/gpu/vk/vk_replay.cpp').read_text(encoding='utf-8')
        start = source.index('// Ocarina Reborn: a capture only needs')
        end = source.index('uint64_t fence();', start)
        cpp = HARNESS.replace('/* PRODUCTION */', source[start:end])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); (p/'test.cpp').write_text(cpp, encoding='utf-8')
            build = subprocess.run([compiler, '-std=c++17', '-O2', '-static', str(p/'test.cpp'), '-o', str(p/'test.exe')], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stdout+build.stderr)
            for enabled in ('1', '0'):
                result = subprocess.run([str(p/'test.exe')], env=dict(os.environ, OCR_CAPTURE_PART_WAIT=enabled), capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_stage_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('vk_memory.cpp', 'vk_internal.h', 'vk_replay.cpp'):
                dest = root/'gpu/vk'/name; dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(pre_perf_text('gpu/vk/'+name), encoding='utf-8', newline='\n')
            engine_capture_pacing.apply(root)
            before = {p.name:p.read_bytes() for p in (root/'gpu/vk').iterdir()}
            engine_capture_pacing.apply(root)
            self.assertEqual(before, {p.name:p.read_bytes() for p in (root/'gpu/vk').iterdir()})

HARNESS = r'''
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <mutex>
#define CHECK(x) do { if (!(x)) { printf("FAIL %d: %s\n", __LINE__, #x); return 1; } } while(0)
bool rec_timeline = true, asynchronous = false, sync_waits = true, fences_off = false;
uint64_t done = 5, in_place = 0, waited_seq = 0, waited_ns = 0;
int waits = 0, succeeded = 1;
std::mutex rec_map_mu;
std::map<uint64_t,uint64_t> part_rec;
bool async_on() { return asynchronous; }
bool sync_waits_on() { return sync_waits; }
bool per_queue_fences_off() { return fences_off; }
uint64_t completed() { return done; }
uint64_t memory_in_place_part() { return in_place; }
void wait_rec_seq(uint64_t seq, uint64_t ns, int* ok) { ++waits; waited_seq = seq; waited_ns = ns; *ok = succeeded; }
void logf(const char*, ...) {}
/* PRODUCTION */
int main() {
    constexpr uint64_t timeout = 20000000;
    part_rec[11] = 21;
    if (atoi(getenv("OCR_CAPTURE_PART_WAIT")) == 0) {
        CHECK(!capture_wait_part(9,11,0,timeout)); CHECK(waits==0); return 0;
    }
    // Whole submission 9 is still blocked, but the mirrored pages were written by recording 21.
    CHECK(capture_wait_part(9,11,0,timeout)); CHECK(waits==1 && waited_seq==21 && waited_ns==timeout);
    CHECK(!capture_wait_part(9,0,0,timeout)); // no mirrored-page dependency
    CHECK(!capture_wait_part(9,12,0,timeout)); // mapping not submitted; MUST NOT wait for its publication
    CHECK(!capture_wait_part(9,11,6,timeout)); // direct writes still pending
    CHECK(waits==1);
    CHECK(capture_wait_part(9,11,5,timeout)); // direct writes are complete
    in_place=12; CHECK(!capture_wait_part(9,11,0,timeout));
    in_place=11; CHECK(capture_wait_part(9,11,0,timeout));
    in_place=0;
    asynchronous=true; CHECK(!capture_wait_part(9,11,0,timeout)); asynchronous=false;
    sync_waits=false; CHECK(!capture_wait_part(9,11,0,timeout)); sync_waits=true;
    fences_off=true; CHECK(!capture_wait_part(9,11,0,timeout)); fences_off=false;
    rec_timeline=false; CHECK(!capture_wait_part(9,11,0,timeout)); rec_timeline=true;
    CHECK(capture_wait_part(9,11,0,250000000)); CHECK(waited_ns==250000000); // explicit legacy wait budget
    const int before=waits;
    succeeded=0; CHECK(capture_wait_part(9,11,0,timeout)); CHECK(waits==before+1 && waited_ns==timeout);
    puts("Known recording, missing mapping, direct writes, in-place reads, alternate replay and timeout: passed");
}
'''
