from pathlib import Path
import importlib.util, json, shutil, subprocess, sys, tempfile, unittest
from unittest.mock import patch
ALPHA=Path(__file__).resolve().parents[1]
ROOT=ALPHA.parents[1]
sys.path.insert(0,str(ALPHA));sys.path.insert(0,str(ALPHA/'launcher'))
import engine_prepare, performance, advisor

class PreparationTests(unittest.TestCase):
    def test_policy_and_real_compute_selection(self):
        compiler=shutil.which('clang++')
        self.assertIsNotNone(compiler,'clang++ required')
        t=(ROOT/'engine/gpu/vk/vk_draw.cpp').read_text(encoding='utf-8')
        code=t[t.index('struct ComputePlan {'):t.index('std::mutex state_mu;')]
        harness=r'''
#include <unordered_set>
#include <string>
#include <vector>
#include <cstring>
#include <cstdio>
#include "ocr_prepare_policy.h"
using namespace ocr_prepare;
std::unordered_set<uint64_t> learned;
std::vector<uint64_t> shipped;
auto computes_read(){return learned;}
std::string state_list_path(const char* p){return p;}
auto state_list_computes(const std::string&){return shipped;}
/* PRODUCTION */
#define CHECK(x) do {if(!(x)){printf("line %d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(){
 CHECK(workers(64,64,1024*MiB,64000*MiB)==1);
 CHECK(workers(16,16,16000*MiB,2048*MiB)==1);
 CHECK(workers(16,16,16000*MiB,32000*MiB)==8);
 CHECK(workers(2,16,16000*MiB,32000*MiB)==2);
 CHECK(workers(16,1,16000*MiB,32000*MiB)==1);
 CHECK(avoid_resident_fallback(true,true,16ull*1024*MiB));
 CHECK(!avoid_resident_fallback(true,true,32ull*1024*MiB));
 CHECK(!avoid_resident_fallback(false,true,16ull*1024*MiB));
 auto p=computes_plan(nullptr,true); CHECK(!p.all && p.keys.empty());
 shipped={11,22,22};p=computes_plan(nullptr,true);CHECK(!p.all && p.keys.size()==2 && p.shipped==2);
 learned={22,33};p=computes_plan(nullptr,true);CHECK(!p.all && p.keys.size()==3 && p.fresh==1);
 p=computes_plan("all",true);CHECK(p.all);
 p=computes_plan("none",true);CHECK(p.none && !p.all);
 p=computes_plan("learned",true);CHECK(p.keys.size()==2 && !p.keys.count(11) && !p.all);
 p=computes_plan(nullptr,false);CHECK(p.keys.size()==2 && !p.all);
 learned.clear();p=computes_plan("learned",true);CHECK(p.keys.empty() && !p.all);
 puts("worker memory limits and real compute selection passed");
}'''.replace('/* PRODUCTION */',code)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(harness)
            r=subprocess.run([compiler,'-std=c++17','-O2','-static','-I'+str(ROOT/'engine/gpu/vk'),str(p/'test.cpp'),'-o',str(p/'test.exe')],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            r=subprocess.run([str(p/'test.exe')],capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_fresh_and_repeat_generator(self):
        names={rel for rel,_,_ in engine_prepare.CHANGES}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for rel in names:
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(subprocess.run(['git','show','517b661:engine/'+rel],cwd=ROOT,capture_output=True,check=True).stdout)
            engine_prepare.apply(root)
            for rel in names:
                self.assertEqual((root/rel).read_text(encoding='utf-8'),(ROOT/'engine'/rel).read_text(encoding='utf-8'))
            before={r:(root/r).read_bytes() for r in names}
            engine_prepare.apply(root)
            self.assertEqual(before,{r:(root/r).read_bytes() for r in names})

    def test_progress_does_not_invent_completed_shader_counts(self):
        spec=importlib.util.spec_from_file_location('prepare',ALPHA/'ocarina_prepare.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        messages=[]
        with patch.object(m,'out',side_effect=lambda **kw:messages.append(kw)):
            p=m.Progress();p.programs=38809;p.line('@@stage shaders');p.line('@@progress 0.8')
        last=messages[-1];self.assertNotIn('count',last);self.assertLess(last['total_pct'],100)

    def test_real_precompile_counts_compute_work_and_releases_pipelines(self):
        # Run the production warm pass with a deterministic driver. Regression:
        # graphics reached 100% and left the watchdog frozen while compute work
        # was still progressing. Also check filtered work and temporary lifetime.
        draw=(ROOT/'engine/gpu/vk/vk_draw.cpp').read_text(encoding='utf-8')
        a=draw.index('void precompile_warm(void (*progress)(size_t done, size_t total)) {')
        function=draw[a:draw.index('\n}\n',a)+2]
        harness=r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include "warm_bounded.h"
using VkPipeline=unsigned long long;
using VkPrimitiveTopology=int;
constexpr VkPipeline VK_NULL_HANDLE=0;
constexpr int VK_SUCCESS=0;
struct VkComputePipelineCreateInfo {};
struct {int device=1;} dev;
struct Stage {int module=1;};
struct Program {bool fallback=false,compute=false,failed=false;unsigned variant=1;uint64_t key=0;std::vector<Stage> stages{{}};std::vector<VkPipeline> fallback_compute;};
struct NoteRef {uint64_t prog;unsigned variant;size_t at;};
struct PipeNote {int s=0,topo=0;};
struct ComputePlan {bool all=false,none=false;std::unordered_set<uint64_t> keys{200,201};};
std::vector<std::pair<size_t,size_t>> progress_values;
std::atomic<unsigned> destroyed=0,computed=0,borrowed=0;
unsigned saved=0,marked=0;
std::string precompile_built_path(){return "built";}
void pcache_init(){}
std::vector<NoteRef> pipe_notes_refs(){return {{100,1,0},{101,1,1}};}
void precompile_built_write(size_t){marked++;}
template<class... T>void logf(const char*,T...){}
ComputePlan computes_plan(const char*,bool){return {};}
bool env_on(const char* name){return std::string(name)=="HOOKSHOT_PREPARE_ONLY";}
std::vector<uint64_t> program_cache_compute_keys(){return {200,201,999};}
std::string pipe_notes_path(){return "notes";}
unsigned usable_cpus(){return 4;}
unsigned ocr_shader_workers(unsigned){return 1;}
void ub_thread_off(){}
bool prepare_stopped(){return false;}
template<class F>void program_cache_borrow(uint64_t key,F callback){
    assert(key!=999);borrowed++;Program p;p.key=key;p.fallback=key==100;p.compute=key>=200;callback(p);assert(p.fallback_compute.empty());
}
void ensure_layout(Program&){}
void fallback_compute_pipelines(Program& p){p.fallback_compute.push_back(88);}
bool pipe_note_at(FILE*,size_t,PipeNote*){return true;}
int note_targets(const PipeNote&){return 0;}
VkPipeline build_graphics(Program&,int,int,int){return 77;}
void vkDestroyPipeline(int,VkPipeline p,void*){assert(p);destroyed++;}
template<class... T>void prepare_progress_log(T...){}
bool taau_key(uint64_t){return false;}
VkComputePipelineCreateInfo compute_pipeline_info(Program&,bool){return {};}
int cached_compute(const VkComputePipelineCreateInfo*,VkPipeline* out){
    std::this_thread::sleep_for(std::chrono::milliseconds(75));computed++;*out=99;return VK_SUCCESS;
}
void pipeline_cache_save(bool){assert(computed==2);saved++;}
/* PRODUCTION */
int main(){
    FILE* f=fopen("notes","wb");assert(f);fclose(f);
    precompile_warm([](size_t done,size_t total){progress_values.emplace_back(done,total);});
    assert(borrowed==4 && computed==2 && destroyed==5 && saved==1 && marked==0);
    assert(!progress_values.empty());
    size_t last=0;bool compute_advance=false;
    for(size_t i=0;i<progress_values.size();i++){
        auto [done,total]=progress_values[i];assert(total==4 && done>=last && done<=total);
        if(done==3)compute_advance=true;
        if(i+1<progress_values.size())assert(done<total);
        last=done;
    }
    assert(last==4 && compute_advance);
}'''.replace('/* PRODUCTION */',function)
        compiler=shutil.which('clang++');self.assertIsNotNone(compiler)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(harness)
            r=subprocess.run([compiler,'-std=c++20','-O2','-static','-I'+str(ROOT/'engine/gpu/vk'),str(p/'test.cpp'),'-o',str(p/'test.exe')],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            r=subprocess.run([str(p/'test.exe')],cwd=p,capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode,0,r.stderr)

    def test_low_ram_is_not_an_allocation_failure(self):
        lines=['[hos Presentation Thread] [OcarinaReborn/MEM] system: commit free 407 MB, RAM free 331 MB, reserve 3072 MB']
        self.assertEqual(performance.memory_events(lines),0)
        result=performance.memory_pressure(lines)
        self.assertEqual(result['memory_pressure_events'],1)
        self.assertEqual(result['ram_free_min_mb'],331)
        self.assertIn('Low available RAM',advisor.diagnose(lines,de=False)[0][1])
        self.assertEqual(performance.memory_pressure(['system: RAM free 1 MB'])['memory_pressure_events'],0)

if __name__=='__main__':unittest.main()
