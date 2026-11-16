"""Exercise input expiry, startup residency and the scoped Intel experiment."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile, unittest

ALPHA=Path(__file__).resolve().parents[1]
ROOT=ALPHA.parents[1]
sys.path.insert(0,str(ALPHA))
import engine_tester_fixes

def function(text,marker):
    start=text.index(marker);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

class TesterFixTests(unittest.TestCase):
    def compile_run(self,code,cpp=False,envs=None):
        compiler=shutil.which('clang++' if cpp else 'clang')
        self.assertIsNotNone(compiler)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);src=p/('test.cpp' if cpp else 'test.c');exe=p/'test.exe'
            src.write_text(code,encoding='utf-8')
            result=subprocess.run([compiler,'-std=c++17' if cpp else '-std=c11','-O2','-static',
                '-I'+str(ROOT/'engine/host'),'-I'+str(ROOT/'engine/gpu/vk'),str(src),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            for updates in envs or [{}]:
                env=os.environ.copy()
                for k,v in updates.items():
                    if v is None:env.pop(k,None)
                    else:env[k]=v
                result=subprocess.run([str(exe)],cwd=p,env=env,capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,str(updates)+'\n'+result.stdout+result.stderr)

    def test_real_pad_read_expires_stale_sticks_buttons_and_motion(self):
        source=(ROOT/'engine/host/pad_sdl.c').read_text()
        actual=function(source,'int hos_sdl_pads(')+'\n'+function(source,'int hos_sdl_motion_history(')
        self.compile_run(r'''
#include <windows.h>
#include <stdint.h>
#include <assert.h>
#include "ocr_input_state.h"
#define HOS_MOTION_HISTORY 8
typedef struct {int value;} HosMotionSample;
static SRWLOCK state_lock=SRWLOCK_INIT;
static int state_count=1,motion_live=1,motion_count=1,motion_head=0,starts=0;
static int64_t state_sample_ns=1000000000LL,now=1004000000LL;
static uint64_t state_buttons=2;
static int32_t state_stick[4]={123,456,27000,-25000};
static HosMotionSample motion_hist[8]={{42}};
static int64_t hos_now_ns(void){return now;}
static int env_on(const char *p){return 0;}
static int hos_sdl_load(void){return 1;}
static void hos_log(const char *p){}
#define CreateThread(a,b,c,d,e,f) (++starts)
/* ACTUAL */
int main(void){
 uint64_t buttons=4;int32_t stick[4]={0};HosMotionSample motion[2]={{0}};
 assert(hos_sdl_pads(&buttons,stick)==1 && starts==1);
 assert(buttons==6 && stick[2]==27000 && stick[3]==-25000);
 assert(hos_sdl_motion_history(motion,2)==1 && motion[0].value==42);
 now=1500000000LL;buttons=0;stick[2]=0;hos_sdl_pads(&buttons,stick);assert(buttons==2);
 now++;buttons=4;memset(stick,0,sizeof stick);stick[0]=32000;
 assert(hos_sdl_pads(&buttons,stick)==1); // no duplicate XInput takeover
 assert(buttons==4 && stick[0]==32000 && stick[2]==0 && stick[3]==0);
 assert(hos_sdl_motion_history(motion,2)==0);
 now+=9000000000LL;buttons=0;hos_sdl_pads(&buttons,stick);assert(buttons==0);
 state_sample_ns=now;hos_sdl_pads(&buttons,stick);assert(buttons==2 && stick[2]==27000);
 assert(hos_sdl_motion_history(motion,2)==1 && starts==1);
 state_count=0;state_buttons=0;memset(state_stick,0,sizeof state_stick);memset(stick,0,sizeof stick);buttons=0;
 assert(hos_sdl_pads(&buttons,stick)==0 && !buttons && !stick[2]);
 assert(!ocr_pad_sample_fresh(0,now) && !ocr_pad_sample_fresh(now+1,now));
}
'''.replace('/* ACTUAL */',actual))

    def test_startup_policy_preserves_overrides_and_safety_markers(self):
        self.compile_run(r'''
#include <cassert>
#include "ocr_prepare_policy.h"
using namespace ocr_prepare;
int main(){
 for(bool native:{false,true}){
  assert(startup_choice(nullptr,native,false,false,16*1024*MiB,false).create);
  assert(startup_choice(nullptr,native,true,true,16*1024*MiB,false).create);
  assert(!startup_choice(nullptr,native,true,false,16*1024*MiB,false).create);
  assert(!startup_choice("start",native,false,false,16*1024*MiB,false).create);
  assert(startup_choice("create",native,true,false,16*1024*MiB,false).create);
  assert(!startup_choice(nullptr,native,false,false,16*1024*MiB,true).create);
  assert(!startup_choice(nullptr,native,true,true,32*1024*MiB,false).create);
  assert(startup_choice(nullptr,native,false,false,64*1024*MiB,false).create==native);
  assert(startup_choice(nullptr,native,false,false,0,false).create==native);
 }
}
''',cpp=True)

    def test_intel_pipeline_trial_is_scoped_and_can_be_disabled(self):
        source=(ROOT/'engine/gpu/vk/vk_draw.cpp').read_text()
        actual=function(source,'VkComputePipelineCreateInfo compute_pipeline_info(')
        self.compile_run(r'''
#include <cstdint>
#include <atomic>
#include <cassert>
#include <initializer_list>
#include "compat/ocarina_reborn_env.h"
using VkDriverId=unsigned;
constexpr VkDriverId VK_DRIVER_ID_INTEL_PROPRIETARY_WINDOWS=5;
#include "ocr_intel_compute.h"
constexpr int VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO=1,VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO=2;
constexpr int VK_SHADER_STAGE_COMPUTE_BIT=4,VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT=8;
struct Stage{int sType=0,stage=0,module=0;const char* pName=nullptr;};
struct VkComputePipelineCreateInfo{int sType=0;Stage stage;int layout=0,flags=0;};
struct Program{Stage stages[1]{};unsigned workgroup[1]{32};int layout=99;uint64_t key=0;};
struct {struct {uint32_t vendorID=0;} props;VkDriverId driver_id=0;} dev;
void pin_subgroup(Stage&,unsigned){}
template<class... T> void logf(const char*,T...){}
/* ACTUAL */
int main(){
 const char* setting=getenv("OCR_INTEL_FOREST_COMPAT");
 const bool enabled=!setting||!env_value_off(setting);
 for(uint32_t vendor:{0x8086u,0x1002u,0x10deu})for(unsigned driver:{5u,6u})
 for(uint64_t key:{0x685adb41edc19de7ull,0x6637ac1d052d22d4ull,0x592079442d7129daull,0x499dbfd0721d2858ull,0xabccf81b45c5eb50ull,0x123ull,0x435a0138b9013040ull})for(bool noopt:{false,true}){
  dev.props.vendorID=vendor;dev.driver_id=driver;Program p;p.key=key;p.stages[0].module=81;
  const auto ci=compute_pipeline_info(p,noopt);
  const bool expected=(noopt&&env_on("RX_VK_NOOPT"))||(enabled&&vendor==0x8086&&driver==5&&key!=0x123&&key!=0x435a0138b9013040ull);
  assert(bool(ci.flags&VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT)==expected);
  assert(ci.stage.module==81&&ci.layout==99&&ci.stage.stage==VK_SHADER_STAGE_COMPUTE_BIT);
 }
}
'''.replace('/* ACTUAL */',actual),cpp=True,envs=[
            {'OCR_INTEL_FOREST_COMPAT':v,'RX_VK_NOOPT':n}
            for v in (None,'0','OFF','','1') for n in (None,'1')])

    def test_lasting_driver_fault_list_only_on_amd(self):
        self.compile_run(r'''
#include <cassert>
#include <initializer_list>
#include "ocr_fault_policy.h"
int main(){
 for(int mode:{0,1,2}){
  assert(ocr_faults::keep_earlier_faults(0x1002,mode));
  assert(ocr_faults::keep_earlier_faults(0x10de,mode)==(mode==2));
  assert(ocr_faults::keep_earlier_faults(0x8086,mode)==(mode==2));
 }
}
''',cpp=True)
        source=(ROOT/'engine/gpu/vk/vk_draw.cpp').read_text()
        load=source.index('auto keys = driver_faults::parse(')
        self.assertLess(source.index('ocr_faults::keep_earlier_faults(dev.props.vendorID, driver_faults_mode())',load),
                        source.index('q.load(keys);',load))

    def test_fresh_and_repeat_staging_match_checked_source(self):
        names={rel for rel,_,_ in engine_tester_fixes.CHANGES}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for rel in names:
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(subprocess.run(['git','show','457c544:engine/'+rel],cwd=ROOT,capture_output=True,check=True).stdout)
            engine_tester_fixes.apply(root)
            first={r:(root/r).read_bytes() for r in names}
            engine_tester_fixes.apply(root)
            self.assertEqual(first,{r:(root/r).read_bytes() for r in names})
            for rel in names:self.assertEqual((root/rel).read_text(),(ROOT/'engine'/rel).read_text())
            for rel in ('host/ocr_input_state.h','gpu/vk/ocr_intel_compute.h','gpu/vk/ocr_prepare_policy.h','gpu/vk/ocr_fault_policy.h'):
                self.assertEqual((root/rel).read_bytes(),(ROOT/'engine'/rel).read_bytes())

if __name__=='__main__':unittest.main()
