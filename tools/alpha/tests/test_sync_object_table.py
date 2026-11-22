"""Exercise production synchronization-object lifetime and rehash without reading cold objects."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]

HARNESS = r'''
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct HosThread HosThread;
static int64_t hos_now_ns(void) { return 1000000000; }
static void hos_vcore_checkpoint(void) {}
static int env_on(const char *name) { const char *v=getenv(name); return v && strcmp(v,"1")==0; }
#define CHECK(x) do { if (!(x)) { printf("FAIL %d: %s\n", __LINE__, #x); return 1; } } while(0)
/* PRODUCTION */
static int lifecycle(void) {
    const uint64_t key=0x20000;
    Obj *a=obj(key,K_EVENT);
    a->signaled=1; a->gen=42;
    CHECK(find_locked(key)==a && find_unlocked(key,K_EVENT)==a);
    drop(key); CHECK(!find_locked(key) && !find_unlocked(key,K_EVENT));
    CHECK(find_slot_locked(key,0)!=~0ull && a->kind==0);
    CHECK(obj(key,K_EVENT)==a && a->signaled==0 && a->gen==0);
    CHECK(obj(key,K_SEMA)==a && a->kind==K_SEMA); // address reused for another object kind
    CHECK(find_slot_locked(key,1)!=~0ull && !find_unlocked(key,K_EVENT));
    a->sem=7; CHECK(fresh(key,K_SEMA)==a && a->sem==0);
    const uint64_t first_slot=slot_of(key,cap);
    uint64_t collision=key+1;
    while(slot_of(collision,cap)!=first_slot) ++collision;
    drop(key);
    Obj *b=obj(collision,K_MUTEX);
    CHECK(b!=a && find_locked(collision)==b && !find_locked(key));
    CHECK(grave_count==1); // replaced tombstone is deferred, not freed beneath caches
    CHECK(obj(key,K_EVENT)!=b && find_locked(key)->kind==K_EVENT);
    CHECK(find_unlocked(collision,K_MUTEX)==b);
    return 0;
}
static int rehash(void) {
    const uint64_t n=32768;
    const SIZE_T bytes=(SIZE_T)n*sizeof(Obj);
    Obj *objects=VirtualAlloc(NULL,bytes,MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);
    CHECK(objects);
    AcquireSRWLockExclusive(&table_lock);
    for(uint64_t k=0;k<n;k++) {
        objects[k].key=0x1000000+k*16;
        objects[k].kind=K_EVENT;
        insert_locked(&objects[k]);
    }
    ReleaseSRWLockExclusive(&table_lock);
    CHECK(cap==65536 && used==n);
    for(uint64_t k=0;k<16;k++) drop(objects[k].key);
    Table *old_table=live;
    DWORD was;
    CHECK(VirtualProtect(objects,bytes,PAGE_NOACCESS,&was));
    Obj extra={0}; extra.key=0x90000000; extra.kind=K_MUTEX;
    AcquireSRWLockExclusive(&table_lock);
    insert_locked(&extra); // crashes if rehash reads Obj::key/kind instead of contiguous metadata
    ReleaseSRWLockExclusive(&table_lock);
    CHECK(cap==131072 && used==n-16+1 && grave_count==16 && live!=old_table);
    CHECK(find_locked(extra.key)==&extra);
    CHECK(VirtualProtect(objects,bytes,PAGE_READWRITE,&was));
    for(uint64_t k=0;k<n;k++) {
        if(k<16) CHECK(!find_locked(objects[k].key));
        else CHECK(find_locked(objects[k].key)==&objects[k] && find_unlocked(objects[k].key,K_EVENT)==&objects[k]);
    }
    // Previously published tables remain valid for readers already holding them.
    CHECK(old_table->cap==65536);
    CHECK(obj(objects[0].key,K_EVENT)!=NULL);
    return 0;
}
static volatile LONG stop_reader, reader_failed, reader_passes;
static DWORD WINAPI reader(void *arg) {
    (void)arg;
    while(!InterlockedCompareExchange(&stop_reader,0,0)) {
        for(uint64_t k=0;k<128;k++) {
            Obj *o=obj_nockpt(0x3000000+k*16,K_EVENT);
            if(!o || o->key!=0x3000000+k*16 || o->kind!=K_EVENT) InterlockedExchange(&reader_failed,1);
        }
        InterlockedIncrement(&reader_passes);
    }
    return 0;
}
static int concurrent(void) {
    for(uint64_t k=0;k<128;k++) obj(0x3000000+k*16,K_EVENT);
    HANDLE thread=CreateThread(NULL,0,reader,NULL,0,NULL); CHECK(thread);
    for(uint64_t k=0;k<80000;k++) {
        const uint64_t key=0x5000000+k*16;
        obj(key,K_MUTEX);
        if(k%19==0) drop(key);
    }
    InterlockedExchange(&stop_reader,1);
    CHECK(WaitForSingleObject(thread,5000)==WAIT_OBJECT_0);
    CloseHandle(thread);
    CHECK(!reader_failed && reader_passes>0 && cap>=131072);
    for(uint64_t i=0;i<cap;i++) if(table[i]) CHECK(table_alive[i]==(table[i]->kind!=0));
    return 0;
}
int main(int argc,char **argv) {
    CHECK(argc==2);
    if(strcmp(argv[1],"lifecycle")==0) return lifecycle();
    if(strcmp(argv[1],"rehash")==0) return rehash();
    if(strcmp(argv[1],"concurrent")==0) return concurrent();
    return 2;
}
'''


class SyncObjectTableTests(unittest.TestCase):
    def test_lifecycle_cold_growth_and_concurrent_readers(self):
        compiler = shutil.which('clang')
        if not compiler or os.name != 'nt':
            self.skipTest('Windows and clang required')
        text = (ROOT / 'engine/host/nn_os_sync.c').read_text(encoding='utf-8')
        begin = text.index('enum { K_MUTEX = 1,')
        end = text.index('/* Wait on o->cv until', begin)
        production = text[begin:end].replace('static int wake_lat_on(void);', '')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path/'test.c').write_text(HARNESS.replace('/* PRODUCTION */', production), encoding='utf-8')
            built = subprocess.run([compiler, '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-static',
                                    str(path/'test.c'), '-o', str(path/'test.exe')], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stdout+built.stderr)
            env = dict(os.environ)
            for key in ('HOS_KEEP_DEAD_OBJECTS', 'HOS_NO_OBJ_CACHE', 'HOS_SYNC_TABLE_LOCK'):
                env.pop(key, None)
            for mode in ('lifecycle', 'rehash', 'concurrent'):
                for locked in ('0', '1'):
                    with self.subTest(mode=mode, locked_reads=locked):
                        run = subprocess.run([str(path/'test.exe'), mode], env=dict(env,HOS_SYNC_TABLE_LOCK=locked),
                                             capture_output=True, text=True, timeout=15)
                        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)


if __name__ == '__main__':
    unittest.main()
