"""Real decoder equivalence for the renderer's parallel row path, plus pool pressure limits."""
from pathlib import Path
import os, shutil, subprocess, tempfile, unittest, sys
ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
import engine_resource_memory

class ResourceMemoryTests(unittest.TestCase):
    def test_upload_lookup_never_imports_or_waits(self):
        compiler = shutil.which('clang++')
        if not compiler: self.skipTest('clang++ required')
        text = (ROOT/'engine/gpu/vk/vk_memory.cpp').read_text(encoding='utf-8')
        def body(signature):
            start=text.index(signature); end=text.index('{',start)+1; depth=1
            while depth:
                depth += (text[end]=='{')-(text[end]=='}'); end+=1
            return text[start:end]
        cpp=LOOKUP.replace('/* POOL */',body('Pool* pool_of(')).replace('/* BUFFER */',body('BufferRef gpu_buffer('))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(cpp,encoding='utf-8')
            build=subprocess.run([compiler,'-std=c++17','-O2','-static',str(p/'test.cpp'),'-o',str(p/'test.exe')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            run=subprocess.run([str(p/'test.exe')],capture_output=True,text=True,timeout=5)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_patch_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n in ('vk_memory.cpp', 'vk_texture.cpp', 'vk_internal.h'):
                p = root / 'gpu/vk' / n
                p.parent.mkdir(parents=True, exist_ok=True)
                from engine_tester_fixes import historical_engine_bytes
                p.write_bytes(historical_engine_bytes('gpu/vk/' + n))
            engine_resource_memory.apply(root)
            before = {p.relative_to(root):p.read_bytes() for p in (root/'gpu/vk').rglob('*') if p.is_file()}
            engine_resource_memory.apply(root)
            self.assertEqual(before, {p.relative_to(root):p.read_bytes() for p in (root/'gpu/vk').rglob('*') if p.is_file()})

    def test_parallel_decoder_and_pressure(self):
        compiler = shutil.which('clang++')
        if not compiler: self.skipTest('clang++ required')
        vk = ROOT/'engine/gpu/vk'
        gpu = ROOT/'engine/gpu'
        source = (vk/'vk_texture.cpp').read_text(encoding='utf-8')
        start = source.index('                        const uint64_t out_row =')
        end = source.index('                        static const bool check =', start)
        # Compile the actual production partitioning, gathering and thread/join code.
        cpp = HARNESS.replace('/* PARALLEL */',source[start:end])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'test.cpp').write_text(cpp,encoding='utf-8')
            result = subprocess.run([compiler,'-std=c++20','-O2','-static','-DNDEBUG',
                '-I'+str(vk),'-I'+str(vk/'compat'),'-I'+str(gpu/'compat'),'-I'+str(gpu/'third_party/suyu'),
                str(p/'test.cpp'),str(gpu/'third_party/suyu/video_core/textures/decoders.cpp'),
                '-o',str(p/'test.exe')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            result = subprocess.run([str(p/'test.exe')],capture_output=True,text=True,timeout=40)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            print(result.stdout)

HARNESS = r'''
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <span>
#include <thread>
#include <vector>
#include <atomic>
#include <new>
#include "ocr_resource_policy.h"
#include "ocr_upload_batch.h"
#include "video_core/textures/decoders.h"
std::atomic<size_t> peak_allocation{0};
std::atomic<bool> track_allocations{false};
void* operator new(size_t n) {
    if (track_allocations) { size_t old=peak_allocation;while(old<n && !peak_allocation.compare_exchange_weak(old,n)){} }
    if(void* p=malloc(n?n:1))return p;throw std::bad_alloc();
}
void operator delete(void* p) noexcept {free(p);}
void operator delete(void* p,size_t) noexcept {free(p);}
#define CHECK(x) do { if (!(x)) { printf("FAIL %d: %s\n", __LINE__, #x); return 1; } } while(0)
struct Host {
    const uint8_t* data;
    void gpu_read(uint64_t offset, void* out, uint64_t count) { memcpy(out,data+offset,count); }
};
const uint8_t* memory_as_submitted(uint64_t at, const uint8_t* p, uint64_t n, std::vector<uint8_t>& scratch) {
    // Simulate a captured page whose live backing was rewritten since submission.
    if (at <= 8192 && at+n > 8192) scratch[8192-at] = 71;
    return p;
}
int main() {
    using namespace ocr_resources;
    CHECK(upload_threads(14*MB,23,1,0,16)==7);
    CHECK(upload_threads(14*MB,23,1,0,6)==3);
    CHECK(upload_threads(14*MB,23,1,0,1)==1);
    CHECK(upload_threads(14*MB,23,1,0,0)==1);
    CHECK(upload_threads(3*MB,23,1,0,16)==1);
    CHECK(upload_threads(14*MB,23,2,0,16)==1);
    CHECK(upload_threads(14*MB,23,1,1,16)==1);
    CHECK(upload_threads(14*MB,2,1,0,16)==2);
    CHECK(idle_limit(256*MB,512*MB,8*1024*MB,1024*MB)==32*MB);
    CHECK(idle_limit(256*MB,1300*MB,8*1024*MB,1024*MB)==64*MB);
    CHECK(idle_limit(256*MB,8*1024*MB,1000*MB,1024*MB)==32*MB);
    CHECK(idle_limit(16*MB,0,0,1024*MB)==16*MB);
    CHECK(idle_limit(256*MB,8*1024*MB,8*1024*MB,1024*MB)==256*MB);
    CHECK(eviction_target(4096*MB,1536*MB,true,false)==4032*MB);
    CHECK(eviction_target(4096*MB,4080*MB,true,false)==4080*MB);
    CHECK(eviction_target(32*MB,16*MB,true,false)==16*MB);
    CHECK(eviction_target(4096*MB,1536*MB,true,true)==1344*MB);
    CHECK(eviction_target(4096*MB,2048*MB,false,false)==1792*MB);
    IdleReserve reserve;
    CHECK(reserve.update(256*MB,0)==256*MB);
    CHECK(reserve.update(32*MB,100)==32*MB);
    CHECK(reserve.update(256*MB,5099)==32*MB);
    CHECK(reserve.update(32*MB,5100)==32*MB); // renewed pressure delays recovery
    CHECK(reserve.update(256*MB,10099)==32*MB);
    CHECK(reserve.update(256*MB,10100)==256*MB);
    for (auto dims : {std::pair{2560u,1440u}, {1536u,864u}, {1920u,1080u}, {1027u,1031u}})
    for (unsigned src_bpb : {1u,2u,4u,8u,16u})
    for (unsigned tile_h : {0u,2u,4u}) {
        struct { unsigned tw, tile_h; } g{dims.first,tile_h};
        const uint32_t rows_per=8u<<tile_h;
        const uint64_t row_bytes=((uint64_t)g.tw*src_bpb+63)/64*(512ull<<tile_h);
        const unsigned nrows=(dims.second+rows_per-1)/rows_per;
        std::vector<uint8_t> input(row_bytes*nrows);
        uint32_t random=7;
        for (auto& v:input) { random=random*1664525+1013904223; v=uint8_t(random>>24); }
        Host host_value{input.data()}; auto* host=&host_value;
        struct {uint64_t gpu;} tex{0};
        const uint64_t full_size=input.size();
        for (bool truncated : {false, true}) {
        const uint64_t total=full_size-(truncated ? row_bytes/2 : 0);
        auto reference_input=input;
        std::fill(reference_input.begin()+total,reference_input.end(),0);
        reference_input[8192]=71;
        for (unsigned row0 : {0u,nrows/2}) for (bool gather_parts : {false,true}) for (unsigned cpus : {1u,16u}) {
            if (truncated && !gather_parts) continue;
            const unsigned nrow=nrows-row0, th=dims.second-row0*rows_per;
            const uint64_t from=(uint64_t)row0*row_bytes, need=full_size-from;
            const uint64_t bytes=(uint64_t)g.tw*th*src_bpb;
            const unsigned nthreads=upload_threads(bytes,nrow,1,0,cpus);
            std::vector<uint8_t> reference(bytes), output(bytes+64,0xcc);
            auto* blocks=output.data(); const auto* src=reference_input.data()+from;
            Tegra::Texture::UnswizzleTexture(reference, std::span<const uint8_t>(src,need),src_bpb,g.tw,th,1,tile_h,0,1);
            /* PARALLEL */
            CHECK(!memcmp(reference.data(),blocks,bytes));
            CHECK(std::all_of(output.begin()+bytes,output.end(),[](auto c){return c==0xcc;}));
        }
    }
    }
    {
        const struct {unsigned tw,tile_h;}g{8192,4};
        const unsigned src_bpb=4,rows_per=128,th=11168,nrow=(th+127)/128,nthreads=1;
        const uint64_t row_bytes=4*MB,from=0,need=nrow*row_bytes,total=need,bytes=(uint64_t)g.tw*th*src_bpb;
        std::vector<uint8_t> input(need), output(bytes);
        for(uint64_t i=0;i<need;++i)input[i]=uint8_t((i*13+i/1237)%251);
        input[8192]=71;
        Host host_value{input.data()};auto* host=&host_value;const struct {uint64_t gpu;}tex{0};
        auto* blocks=output.data();const auto* src=input.data();const bool gather_parts=true;
        Tegra::Texture::UnswizzleTexture(output,input,src_bpb,g.tw,th,1,g.tile_h,0,1);
        auto checksum=[&]{uint64_t hash=0;for(auto c:output)hash=hash*131+c;return hash;};
        const auto expected=checksum();std::fill(output.begin(),output.end(),0);
        peak_allocation=0;track_allocations=true;
        /* PARALLEL */
        track_allocations=false;
        CHECK(checksum()==expected);
        CHECK(peak_allocation<=8*MB);
        printf("349 MiB single-worker decode: largest scratch allocation %zu MiB (old full-span scratch: %llu MiB)\n",
            size_t(peak_allocation/MB),(unsigned long long)(need/MB));
    }
    puts("decoder: exact bytes and bounds for full/partial rows, direct/gathered data, odd dimensions and 5 pixel sizes; pressure limits passed");
}
'''

LOOKUP = r'''
#include <algorithm>
#include <cstdint>
#include <map>
#include <mutex>
#include <cstdio>
#define CHECK(x) do { if (!(x)) { printf("FAIL %d: %s\n", __LINE__, #x); return 1; } } while(0)
struct Pool { uint64_t lo,hi,last_value,buffer,address; };
std::map<uint64_t,Pool> imported;
Pool* last_pool=nullptr;
Pool* pool_cache[4096]{};
int imports=0,reads=0;
Pool* pool_lookup(uint64_t guest,uint64_t size) {
    ++imports;
    auto& p=imported[guest];p={guest,guest+size,0,17,9000};return &p;
}
/* POOL */
struct BufferRef {
    uint64_t buffer,offset,size,address;
    explicit operator bool() const { return buffer!=0; }
};
struct Host { bool valid=true; uint64_t available=0x10000;
    const char* gpu_ptr(uint64_t,uint64_t* avail){*avail=available;return valid?"data":nullptr;}
    uint64_t gpu_guest(uint64_t gpu){return gpu;}
} h;
Host* host=&h;
std::mutex pools_mu;
uint64_t mem_rec_value=22;
void note_in_place_read(){++reads;}
/* BUFFER */
int main(){
    CHECK(!gpu_buffer(0x10000,0x8000,true));
    CHECK(imports==0 && reads==0);
    imported[0x10000]={0x10000,0x18000,2,5,7000};
    CHECK(!gpu_buffer(0x14000,0x8000,true)); // partial coverage must not expand an import
    CHECK(imports==0);
    auto b=gpu_buffer(0x12000,0x4000,true);
    CHECK(b && b.buffer==5 && b.offset==0x2000 && b.address==7000+0x2000);
    CHECK(imported.begin()->second.last_value==22 && reads==1 && imports==0);
    CHECK(gpu_buffer(0x12000,0x1000,true)); // remembered pool
    CHECK(!pool_of(UINT64_MAX-5,10,true));
    CHECK(!pool_of(0x12000,0,true));
    CHECK(gpu_buffer(0x20000,0x8000,false)); // ordinary callers still import
    CHECK(imports==1 && reads==3);
    last_pool=nullptr;std::fill(std::begin(pool_cache),std::end(pool_cache),nullptr);
    imported.clear(); // retirement invalidates the same caches in the real engine
    CHECK(!gpu_buffer(0x12000,0x4000,true) && imports==1);
    h.valid=false;
    CHECK(!gpu_buffer(0x12000,0x4000,false) && imports==1);
    puts("existing import lookup: exact coverage, GPU lifetime pin, overflow, retirement and no allocation/wait passed");
}
'''
