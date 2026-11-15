"""FSR 3.1.6 staging, settings compatibility and native menu navigation."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile, unittest

ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
sys.path.insert(0, str(ALPHA/'launcher'))
import engine_fsr316, game_settings

def block(text, start):
    at = text.index(start)
    end = text.index('{', at) + 1
    depth = 1
    while depth:
        depth += (text[end]=='{') - (text[end]=='}')
        end += 1
    return text[at:end]


class Fsr316Tests(unittest.TestCase):
    def test_fresh_upgrade_and_repeated_staging(self):
        names = sorted({rel for rel, _, _ in engine_fsr316.CHANGES})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in names:
                p = root/rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(subprocess.run(['git','show','88e42ea:engine/'+rel], cwd=ROOT, capture_output=True, check=True).stdout)
            engine_fsr316.apply(root)
            for rel in names:
                self.assertEqual((root/rel).read_text(encoding='utf-8'), (ROOT/'engine'/rel).read_text(encoding='utf-8'))
            before = {rel:(root/rel).read_bytes() for rel in names}
            engine_fsr316.apply(root)
            self.assertEqual(before, {rel:(root/rel).read_bytes() for rel in names})

    def test_launcher_roundtrip_preserves_existing_options(self):
        row = next(row for _, _, rows in game_settings.SECTIONS for row in rows if row[0]=='dlss')
        self.assertIn((7,'AMD FSR 3.1.6','AMD FSR 3.1.6'), row[3])
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            p = game_settings.ini_file(game)
            p.write_text('dlss=4\nresolution=3\nframe_generation=2\nvolume=55\nkey_a=69,0\n', encoding='utf-8')
            game_settings.write(game, {'dlss':7})
            data = game_settings.read(game)
            self.assertEqual(game_settings.current(data, 'dlss', row[3])[0], 7)
            self.assertEqual(data['volume'], '55')
            self.assertEqual(data['key_a'], '69,0')
            self.assertEqual(data['frame_generation'], '2')
            game_settings.write(game, {'dlss':4})
            self.assertEqual(game_settings.read(game)['dlss'], '4')

    def test_native_upscaler_navigation(self):
        compiler = shutil.which('clang++')
        self.assertIsNotNone(compiler, 'native compiler required')
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp)/'rows.exe'
            subprocess.run([compiler,'-std=c++20','-O2','-static',str(ROOT/'engine/tests/test_upscaler_rows.cpp'),'-o',str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, timeout=10)

    def test_native_provider_context_and_deferred_release(self):
        compiler = shutil.which('clang++')
        headers = os.environ.get('VULKAN_HEADERS')
        self.assertTrue(compiler and headers, 'native compiler and VULKAN_HEADERS required')
        text = (ROOT/'engine/gpu/vk/vk_fsr4.cpp').read_text(encoding='utf-8')
        production = '\n'.join(block(text,m)+suffix for m,suffix in [
            ('struct Library {',';'),('Library& lib()',''),('struct Context {',';'),
            ('struct State {',';'),('template<bool Fsr316> State& st()',''),
            ('template<bool Fsr316> std::shared_ptr<Context> make_context(',''),
            ('template<bool Fsr316> void release()','')])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            cpp=p/'contexts.cpp'; exe=p/'contexts.exe'
            cpp.write_text(CONTEXTS.replace('// PRODUCTION',production),encoding='utf-8')
            result=subprocess.run([compiler,'-std=c++20','-O2','-static','-I'+headers,
                '-I'+str(ROOT/'engine/third_party/fidelityfx'),str(cpp),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            subprocess.run([str(exe)],check=True,timeout=10)


CONTEXTS=r'''
#define NOMINMAX
#include <windows.h>
#include <chrono>
#include <memory>
#include <mutex>
#include <functional>
#include <vector>
#include <cstdio>
#include <cstring>
#include <cassert>
#include "api/include/ffx_api.h"
#include "api/include/vk/ffx_api_vk.h"
#include "upscalers/include/ffx_upscale.h"
extern "C" VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL vkGetDeviceProcAddr(VkDevice,const char*) {return nullptr;}
VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL tuned_proc(VkDevice,const char*) {return nullptr;}
void logf(const char*,...) {}
int env_switch(const char*) {return 1;}
uint64_t texture_frame_no(){return 1;}
template<bool> void on_message(uint32_t,const wchar_t*) {}
std::vector<std::function<void()>> retired;
void temporal_later(std::function<void()> f){retired.push_back(std::move(f));}
// PRODUCTION
int destroyed=0;
uint32_t made_flags=0;
uint64_t made_version=0;
PFN_vkGetDeviceProcAddr made_proc=nullptr;
bool wrong_provider=false,missing_provider=false;
ffxReturnCode_t create_mock(ffxContext* ctx,ffxCreateContextDescHeader* desc,const ffxAllocationCallbacks*) {
    auto* upscale=reinterpret_cast<ffxCreateContextDescUpscale*>(desc);
    auto* backend=reinterpret_cast<ffxCreateBackendVKDesc*>(desc->pNext);
    auto* version=reinterpret_cast<ffxOverrideVersion*>(backend->header.pNext);
    assert(upscale->header.type==FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE);
    assert(backend->header.type==FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK);
    assert(version->header.type==FFX_API_DESC_TYPE_OVERRIDE_VERSION);
    auto* api=reinterpret_cast<ffxCreateContextDescUpscaleVersion*>(version->header.pNext);
    assert(api && api->header.type==FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE_VERSION && api->version==FFX_UPSCALER_VERSION);
    made_version=version->versionId; made_proc=backend->deviceContext.vkDeviceProcAddr; made_flags=upscale->flags;
    *ctx=new uint64_t(made_version);return FFX_API_RETURN_OK;
}
ffxReturnCode_t destroy_mock(ffxContext* ctx,const ffxAllocationCallbacks*) {
    assert(*ctx);delete static_cast<uint64_t*>(*ctx);*ctx=nullptr;++destroyed;return FFX_API_RETURN_OK;
}
ffxReturnCode_t query_mock(ffxContext* ctx,ffxQueryDescHeader* desc) {
    if(desc->type==FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION) {
        if(missing_provider)return FFX_API_RETURN_ERROR;
        auto* p=reinterpret_cast<ffxQueryGetProviderVersion*>(desc);
        p->versionName=wrong_provider?"3.1.5":*static_cast<uint64_t*>(*ctx)==316?"3.1.6":"4.1.2";
    }
    return FFX_API_RETURN_OK;
}
int main() {
    auto& l=lib();l.create=create_mock;l.destroy=destroy_mock;l.query=query_mock;
    l.version_id=412;l.version316_id=316;l.device_context.vkDeviceProcAddr=tuned_proc;
    auto a=make_context<true>(1920,1080,true);
    assert(a && made_version==316 && made_proc==vkGetDeviceProcAddr);
    assert((made_flags&FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE) && (made_flags&FFX_UPSCALE_ENABLE_AUTO_EXPOSURE));
    assert(!(made_flags&FFX_UPSCALE_ENABLE_NON_LINEAR_COLORSPACE));
    auto b=make_context<false>(1920,1080,false);
    assert(b && made_version==412 && made_proc==tuned_proc);
    assert(!(made_flags&FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE) && (made_flags&FFX_UPSCALE_ENABLE_NON_LINEAR_COLORSPACE));
    st<true>().context=a;st<false>().context=b;a.reset();b.reset();
    release<true>();assert(!st<true>().context && st<false>().context && destroyed==0 && retired.size()==1);
    retired.clear();assert(destroyed==1);
    release<false>();assert(!st<false>().context && destroyed==1);retired.clear();assert(destroyed==2);
    wrong_provider=true;assert(!make_context<true>(1920,1080,true) && destroyed==3);
    wrong_provider=false;missing_provider=true;assert(!make_context<true>(1920,1080,true) && destroyed==4);
    puts("FSR contexts: pinned providers, separate state, linear colour, untuned 3.1.6 and deferred release passed");
}
'''
