"""An optional resource-cache query allowance must never change actual page accounting."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MB (1ull << 20)
#define LOCK() ((void)0)
#define UNLOCK() ((void)0)
#define HOS_TRACE_CALL(x) ((void)0)
#define ARG(i) args[i]
#define RET(x) (result = (x))
#define CHECK(x) do { if (!(x)) { printf("FAIL %d: %s\n", __LINE__, #x); return 1; } } while (0)
static uint64_t hos_total_memory, hos_heap_size, mapped_bytes, args[2];
static unsigned result;
static int logs;
static void hos_log(const char *fmt, ...) { (void)fmt; ++logs; }
static int env_on(const char *name) { const char *s=getenv(name); return s && strcmp(s,"1")==0; }
static int hos_guest_range(uint64_t a, uint64_t n) { return n && a+n>=a; }
static int64_t pages_count_locked(uint64_t a, uint64_t n, int map) { (void)a; (void)map; return (int64_t)n; }
static void pages_report_locked(void) {}
/* QUERY */
static void allocate_pages(void) {
/* ALLOCATION_CHECK */
    (void)end;
    RET(0);
}
int main(int argc, char **argv) {
    CHECK(argc==2);
    const uint64_t slack = strtoull(argv[1],NULL,10)*MB;
    const uint64_t base=128*MB;
    hos_total_memory=9809*MB; hos_heap_size=6894*MB; mapped_bytes=2500*MB;
    const uint64_t expected=base+hos_heap_size+mapped_bytes-slack;
    CHECK(hos_used_memory(base)==expected);
    CHECK(logs==1);
    CHECK(hos_used_memory(base)==expected && logs==1);
    CHECK(mapped_bytes==2500*MB && hos_heap_size==6894*MB && hos_total_memory==9809*MB);
    // At startup there are no mapped cache pages: the heap-sizing answer is unchanged.
    mapped_bytes=0; CHECK(hos_used_memory(base)==base+hos_heap_size);
    mapped_bytes=64*MB;
    CHECK(hos_used_memory(base)==base+hos_heap_size+(64*MB>slack ? 64*MB-slack : 0));
    mapped_bytes=8*1024*MB; CHECK(hos_used_memory(base)==hos_total_memory);
    // Exercise the real AllocateMemoryPages budget check. Query slack must not permit this request.
    mapped_bytes=2800*MB; args[0]=0x100000000ull; args[1]=256*MB;
    (void)hos_used_memory(base);
    allocate_pages(); CHECK(result==0xCA01 && mapped_bytes==2800*MB);
    args[1]=64*MB; allocate_pages(); CHECK(result==0 && mapped_bytes==2864*MB);
    CHECK(hos_heap_size==6894*MB && hos_total_memory==9809*MB);
    puts("query allowance, startup heap, accounting, saturation and allocation budget passed");
    return 0;
}
'''


class GuestMemoryQueryTests(unittest.TestCase):
    def test_query_allowance_preserves_allocation_accounting(self):
        compiler = shutil.which('clang')
        if not compiler:
            self.skipTest('clang required')
        source = (ROOT / 'engine/host/hos_mem.c').read_text(encoding='utf-8')
        start = source.index('uint64_t hos_used_memory(uint64_t base) {')
        query = source[start:source.index('\n}\n', start)+3]
        start = source.index('HLE(_ZN2nn2os19AllocateMemoryPagesEmm) {')
        start = source.index('\n', start)+1
        allocation = source[start:source.index('    static int zero_all', start)]
        harness = HARNESS.replace('/* QUERY */', query).replace('/* ALLOCATION_CHECK */', allocation)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'test.c').write_text(harness, encoding='utf-8')
            built = subprocess.run([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-static',
                                    str(path / 'test.c'), '-o', str(path / 'test.exe')], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout+built.stderr)
            for raw, expected in ((None, 0), ('0', 0), ('512', 512), ('1024', 1024), ('-1', 0),
                                  ('1025', 0), ('bad', 0), ('256MB', 0), ('999999999999999999999', 0)):
                with self.subTest(setting=raw):
                    env = dict(os.environ, HOS_PAGES_LIMIT='1')
                    env.pop('HOS_MEMINFO_OLD', None)
                    env.pop('HOS_MEM_QUERY_SLACK_MB', None)
                    if raw is not None:
                        env['HOS_MEM_QUERY_SLACK_MB'] = raw
                    ran = subprocess.run([str(path / 'test.exe'), str(expected)], env=env,
                                         capture_output=True, text=True, timeout=10)
                    self.assertEqual(ran.returncode, 0, ran.stdout+ran.stderr)


if __name__ == '__main__':
    unittest.main()
