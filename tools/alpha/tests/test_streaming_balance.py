from pathlib import Path
import ast, shutil, subprocess, sys, tempfile, unittest
ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
import engine_streaming_balance

class StreamingBalanceTests(unittest.TestCase):
    def test_cleanup_and_memory_policy(self):
        compiler = shutil.which('clang++')
        if not compiler: self.skipTest('clang++ required')
        source=(ROOT/'engine/gpu/vk/vk_texture.cpp').read_text(encoding='utf-8')
        start=source.index('    const auto cleanup_start =')
        end=source.index('    pool_trim();',start)
        cpp=HARNESS.replace('/* CLEANUP */',source[start:end])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(cpp,encoding='utf-8')
            build=subprocess.run([compiler,'-std=c++17','-O2','-static','-I'+str(ROOT/'engine/gpu/vk'),str(p/'test.cpp'),'-o',str(p/'test.exe')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            run=subprocess.run([str(p/'test.exe')],capture_output=True,text=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_launcher_roundtrip(self):
        tree=ast.parse((ALPHA/'launcher/launcher.py').read_text(encoding='utf-8'))
        nodes=[]
        for node in tree.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('LOW_END_ROWS','LOW_END_DEFAULTS','LAUNCHER_KEYS') for t in node.targets): nodes.append(node)
            elif isinstance(node,ast.AugAssign) and isinstance(node.target,ast.Name) and node.target.id=='LOW_END_ROWS': nodes.append(node)
            elif isinstance(node,ast.FunctionDef) and node.name=='low_end_env':nodes.append(node)
        scope={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'launcher settings','exec'),scope)
        self.assertIn('streaming_mode',scope['LAUNCHER_KEYS'])
        self.assertEqual(scope['low_end_env']({})['OCR_STREAMING_MODE'],'1')
        for value in (0,1,2,-4,9):
            cfg={'streaming_mode':value,'ram_guard':2,'low_spec':1}
            env=scope['low_end_env'](cfg)
            self.assertEqual(env['OCR_STREAMING_MODE'],str(max(0,min(value,2))))
            self.assertEqual(env['OCR_RAM_RESERVE_MB'],'3072')
            self.assertEqual(env['RX_VK_LOW_SPEC'],'1')
        row=next(r for r in scope['LOW_END_ROWS'] if r[0]=='streaming_mode')
        self.assertEqual(len(row[3]),3);self.assertEqual(len(row[4]),3)

    def test_generator_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'gpu/vk/vk_texture.cpp';p.parent.mkdir(parents=True)
            shutil.copy2(ROOT/'engine/gpu/vk/vk_texture.cpp',p)
            engine_streaming_balance.apply(root)
            before=p.read_bytes();engine_streaming_balance.apply(root)
            self.assertEqual(before,p.read_bytes())
            self.assertEqual((root/'gpu/vk/ocr_streaming_policy.h').read_bytes(),(ALPHA/'hud/ocr_streaming_policy.h').read_bytes())

HARNESS=r'''
#include <chrono>
#include <deque>
#include <vector>
#include <cstdio>
#include "ocr_streaming_policy.h"
#define CHECK(x) do {if(!(x)){printf("FAIL %d: %s\n",__LINE__,#x);return 1;}}while(0)
using namespace ocr_streaming;
using VkImageView=int;using VkDeviceMemory=int;
struct Resource {uint64_t value=0,bytes=MiB,pool_key=0;int image=1,allocation=1,buffer=0,buffer_alloc=0;std::vector<int> views,memory;};
std::deque<Resource> dead;
struct {bool in_pass=false;}compact;
struct {int device=0;}dev;
uint64_t ocr_idle_cap=UINT64_MAX,rec_value=0;
bool pool_pressed=false;
int destroyed=0,pooled=0;
void pool_put(const Resource&){++pooled;}
void vkDestroyImageView(int,int,void*){}
void destroy_image(int,int){++destroyed;}
void destroy_buffer(int,int){}
void vkFreeMemory(int,int,void*){}
// The merged renderer defers Vulkan destruction through its reaper. This
// policy harness runs the already-completed retirement callbacks immediately.
template<class F>void reap(F f){f();}
void cleanup(uint64_t completed){
/* CLEANUP */
}
void fill(unsigned n,uint64_t value=10){dead.clear();destroyed=pooled=0;for(unsigned i=0;i<n;++i){Resource r;r.value=value;dead.push_back(r);}}
int main(){
    CHECK(texture_limit(12*1024*MiB,16*1024*MiB,1)==3072*MiB);
    CHECK(texture_limit(24*1024*MiB,32*1024*MiB,1)==6400*MiB);
    CHECK(texture_limit(24*1024*MiB,64*1024*MiB,1)==12288*MiB);
    CHECK(texture_limit(24*1024*MiB,16*1024*MiB,2)==2048*MiB);
    CHECK(texture_limit(24*1024*MiB,32*1024*MiB,2)==4096*MiB);
    CHECK(texture_limit(512*MiB,8*1024*MiB,1)==512*MiB);
    CHECK(texture_limit(12*1024*MiB,16*1024*MiB,0)==12*1024*MiB);
    CHECK(!defer_cleanup(0,9999,500,0,false,1));
    CHECK(defer_cleanup(1,1500,500,0,false,1));
    CHECK(!defer_cleanup(64,1500,500,0,true,1));
    CHECK(!defer_cleanup(64,1500,1024,0,false,1));
    CHECK(!defer_cleanup(64,1500,500,257*MiB,false,1));
    fill(128);cleanup(9);CHECK(destroyed==0 && dead.size()==128); // all in flight
    cleanup(10);CHECK(destroyed>0 && destroyed<=64 && !dead.empty());
    while(!dead.empty())cleanup(10);CHECK(destroyed==128);
    fill(128);pool_pressed=true;cleanup(10);CHECK(dead.empty() && destroyed==128);pool_pressed=false;
    fill(128);ocr_idle_cap=32*MiB;cleanup(10);CHECK(dead.empty());ocr_idle_cap=UINT64_MAX;
    fill(500);cleanup(10);CHECK(dead.size()<=256 && destroyed>=244);
    fill(128);for(auto& r:dead)r.pool_key=1;cleanup(10);CHECK(pooled>0 && pooled<=64 && destroyed==0);
    fill(128);compact.in_pass=true;cleanup(10);CHECK(destroyed==0);compact.in_pass=false;
    puts("RAM tiers, completed GPU lifetime, bounded cleanup, emergency drain and pool reuse: passed");
}
'''
