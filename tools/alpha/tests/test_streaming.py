"""Native tests of the production worker batch and completed-image pool."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest, sys, ctypes, _ctypes
ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
import engine_resource_memory, engine_streaming

def section(text, signature):
    a=text.index(signature); b=text.index('{',a)+1; depth=1
    while depth:
        depth+=(text[b]=='{')-(text[b]=='}'); b+=1
    return text[a:b]

class StreamingTests(unittest.TestCase):
    def native(self, source):
        compiler=shutil.which('clang++')
        if not compiler: self.fail('native compiler required for renderer changes')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'test.cpp').write_text(source,encoding='utf-8')
            result=subprocess.run([compiler,'-std=c++20','-O2','-static',
                '-I'+str(ROOT/'engine/gpu/vk'),str(p/'test.cpp'),'-o',str(p/'test.exe')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result=subprocess.run([str(p/'test.exe')],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            print(result.stdout)

    def test_batch_lifetime_reentrancy_errors_and_concurrent_callers(self):
        self.native(WORKERS)

    def test_completed_target_pool_recency_limits_and_unlock(self):
        text=(ROOT/'engine/gpu/vk/vk_texture.cpp').read_text(encoding='utf-8')
        code=section(text,'struct Pooled {')+';\n'
        code+='\n'.join(section(text,name) for name in ('bool pool_take(', 'void pool_destroy(', 'void pool_put(', 'size_t pool_trim('))
        self.native(POOL.replace('/* PRODUCTION */',code))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows DLL lifecycle')
    def test_worker_dll_can_unload_and_reload(self):
        code='''#include "ocr_upload_batch.h"
extern "C" __declspec(dllexport) int exercise() {
    std::atomic<int> n{0};auto fn=[&](unsigned){++n;};
    for(int i=0;i<100;++i)ocr_upload::run(8,fn);
    return n;
}'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'worker.cpp').write_text(code)
            subprocess.run([shutil.which('clang++'),'-std=c++20','-O2','-shared','-static',
                '-I'+str(ROOT/'engine/gpu/vk'),str(p/'worker.cpp'),'-o',str(p/'worker.dll')],check=True,capture_output=True)
            # Separate process so the timeout also detects a loader-lock deadlock.
            script='''import ctypes,_ctypes,sys
for i in range(20):
    module=ctypes.CDLL(sys.argv[1])
    assert module.exercise()==800
    _ctypes.FreeLibrary(module._handle)
'''
            subprocess.run([sys.executable,'-c',script,str(p/'worker.dll')],check=True,timeout=20,capture_output=True)

    def test_generator_on_baseline_and_already_patched(self):
        current=(ROOT/'engine/gpu/vk/vk_texture.cpp').read_bytes()
        # Source ZIPs do not contain Git history; still verify repeat application and the header.
        baseline=current
        if shutil.which('git'):
            result=subprocess.run(['git','show','2d3598d:engine/gpu/vk/vk_texture.cpp'],cwd=ROOT,capture_output=True)
            if result.returncode==0: baseline=result.stdout
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'gpu/vk').mkdir(parents=True)
            target=root/'gpu/vk/vk_texture.cpp';target.write_bytes(baseline)
            engine_streaming.apply(root)
            self.assertEqual(target.read_bytes(),current)
            before=target.read_bytes();engine_streaming.apply(root)
            self.assertEqual(before,target.read_bytes())
            self.assertEqual((root/'gpu/vk/ocr_upload_batch.h').read_bytes(),(ROOT/'engine/gpu/vk/ocr_upload_batch.h').read_bytes())

WORKERS=r'''
#include <windows.h>
bool fail_pool=false,fail_workers=false,fail_work=false;
PTP_POOL make_pool(void* p){return fail_pool?nullptr:CreateThreadpool(p);}
BOOL make_workers(PTP_POOL p,DWORD n){return fail_workers?FALSE:SetThreadpoolThreadMinimum(p,n);}
PTP_WORK make_work(PTP_WORK_CALLBACK callback,void* context,PTP_CALLBACK_ENVIRON environment){
    return fail_work?nullptr:CreateThreadpoolWork(callback,context,environment);
}
#define CreateThreadpool make_pool
#define SetThreadpoolThreadMinimum make_workers
#define CreateThreadpoolWork make_work
#include "ocr_upload_batch.h"
#include <cstdio>
#include <stdexcept>
#define CHECK(x) do { if (!(x)) { printf("FAIL %d: %s\n",__LINE__,#x); return 1; } } while(0)
int main() {
    using namespace ocr_upload;
    for(int failure=0;failure<3;++failure){
        fail_pool=failure==0;fail_workers=failure==1;fail_work=failure==2;
        Pool pool(16);unsigned hits=0;auto fn=[&](unsigned){++hits;};run_on(pool,8,fn);
        CHECK(hits==8);
    }
    fail_pool=fail_workers=fail_work=false;
    for (unsigned cpus : {1u,2u,4u,16u,64u}) {
        Pool pool(cpus);
        CHECK(pool.helpers() <= std::clamp(cpus/2,1u,8u)-1);
        for (unsigned count=0; count<=8; ++count) {
            std::array<std::atomic<unsigned>,8> hits{};
            auto work=[&](unsigned i){ ++hits[i]; };
            for (int loop=0;loop<100;++loop) run_on(pool,count,work);
            for (unsigned i=0;i<8;++i) CHECK(hits[i]==(i<count?100:0));
        }
        // All successful and throwing callbacks have ended before the exception returns.
        std::atomic<unsigned> finished{0}; bool caught=false;
        auto bad=[&](unsigned i){ ++finished; if(i==3) throw std::runtime_error("expected"); };
        try { run_on(pool,8,bad); } catch(const std::runtime_error&) { caught=true; }
        CHECK(caught && finished==(pool.helpers()?8:4));
        std::atomic<unsigned> nested{0};
        auto outer=[&](unsigned){ auto inner=[&](unsigned){++nested;};run_on(pool,8,inner); };
        run_on(pool,8,outer); CHECK(nested==64);
        std::array<std::atomic<unsigned>,8> totals{};
        std::vector<std::thread> callers;
        for(unsigned c=0;c<8;++c) callers.emplace_back([&,c]{
            auto job=[&](unsigned){++totals[c];};
            for(int i=0;i<100;++i) run_on(pool,8,job);
        });
        for(auto& t:callers)t.join();
        for(auto& total:totals)CHECK(total==800);
    } // pool teardown after all callbacks; recreate repeatedly
    puts("workers: exact-once, 1/2/4/16/64 CPUs, concurrent callers, nested jobs, exceptions and teardown passed");
}
'''

POOL=r'''
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <cstdlib>
#define CHECK(x) do { if (!(x)) { printf("FAIL %d: %s\n",__LINE__,#x); return 1; } } while(0)
using VkImage=uint64_t;using VkImageView=uint64_t;using VmaAllocation=uint64_t;
constexpr uint64_t MB=1ull<<20;
struct Dead { uint64_t image,allocation,bytes,pool_key;std::unordered_map<uint64_t,VkImageView> view_map; };
struct Pooled;
std::mutex pool_mu;
std::unordered_map<uint64_t,std::vector<Pooled>> target_pool;
uint64_t pool_bytes=0,pool_n=0,st_pool_reused=0,st_pool_made=0,st_pool_destroyed=0,pool_order=0;
uint64_t ocr_idle_cap=UINT64_MAX,configured_cap=2*MB,now_ms=0,frame_no=0;
bool pool_pressed=false;
uint64_t pool_cap(){return configured_cap;} uint64_t pool_now_ms(){return now_ms;}
struct {int device;} dev;
std::unordered_set<uint64_t> destroyed;
void vkDestroyImageView(int,VkImageView,std::nullptr_t){}
void destroy_image(VkImage i,VmaAllocation) {
    bool available=false;
    std::thread probe([&]{available=pool_mu.try_lock();if(available)pool_mu.unlock();});probe.join();
    if(!available || !destroyed.insert(i).second)std::abort();
}
/* PRODUCTION */
void put(uint64_t key,uint64_t id,uint64_t bytes=MB){Dead d{id,id,bytes,key,{{1,id}}};pool_put(d);}
bool take(uint64_t key){VkImage i;VmaAllocation a;std::unordered_map<uint64_t,VkImageView> views;return pool_take(key,i,a,views);}
int main(){
    put(3,1);++now_ms;put(1,2);++now_ms;put(2,3);
    CHECK(pool_trim()==1 && destroyed.count(1));
    CHECK(take(1) && take(2) && !take(3) && pool_bytes==0 && pool_n==0);
    put(4,4);frame_no+=10000;now_ms+=1999;CHECK(pool_trim()==0);
    now_ms+=2;CHECK(pool_trim()==1 && destroyed.count(4));
    put(1,5);put(1,6);CHECK(take(1)); // newest matching shape reused first
    now_ms+=2001;CHECK(pool_trim()==1 && destroyed.count(5) && !destroyed.count(6));
    for(unsigned i=0;i<70;++i)put(i%9,100+i,1);
    pool_pressed=true;CHECK(pool_trim()==64 && pool_n==6);CHECK(pool_trim()==6);
    pool_pressed=false;ocr_idle_cap=MB;put(1,200);put(2,201);
    CHECK(pool_trim()==1 && destroyed.count(200) && pool_bytes==MB);
    CHECK(take(2) && pool_n==0 && pool_bytes==0 && target_pool.empty());
    puts("targets: global oldest eviction, newest reuse, 2-second lifetime, pressure limits, accounting and frees outside lock passed");
}
'''
