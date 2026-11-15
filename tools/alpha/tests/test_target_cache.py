from pathlib import Path
import shutil, subprocess, sys, tempfile, unittest
ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
import engine_streaming, engine_target_cache, engine_settings_reset, engine_resource_memory


class TargetCacheTests(unittest.TestCase):
    def test_fresh_upgrade_and_repeated_staging(self):
        names = ['vk_texture.cpp', 'vk_vma.cpp']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'gpu/vk').mkdir(parents=True)
            for name in names:
                result = subprocess.run(['git','show','348200b:engine/gpu/vk/'+name],
                    cwd=ROOT, capture_output=True, check=True)
                (root/'gpu/vk'/name).write_bytes(result.stdout)
            engine_streaming.apply(root)
            engine_target_cache.apply(root)
            engine_settings_reset.apply(root)
            texture = root/'gpu/vk/vk_texture.cpp'
            texture.write_text(engine_resource_memory.reclaim_overwritten(texture.read_text()), encoding='utf-8', newline='\n')
            for name in names:
                self.assertEqual((root/'gpu/vk'/name).read_text(), (ROOT/'engine/gpu/vk'/name).read_text())
            before = {p.name:p.read_bytes() for p in (root/'gpu/vk').iterdir()}
            engine_streaming.apply(root)
            engine_target_cache.apply(root)
            engine_settings_reset.apply(root)
            self.assertEqual(before, {p.name:p.read_bytes() for p in (root/'gpu/vk').iterdir()})

    def test_lower_memory_reservations(self):
        compiler=shutil.which('clang++')
        self.assertIsNotNone(compiler, 'native compiler required')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            (p/'test.cpp').write_text('''#include "ocr_streaming_policy.h"
#include <cassert>
using namespace ocr_streaming;
int main() {
    assert(target_cache_limit(256*MiB,1)==256*MiB);
    assert(target_cache_limit(256*MiB,2)==64*MiB);
    assert(target_cache_limit(32*MiB,2)==32*MiB);
    assert(target_cache_limit(0,2)==0);
    assert(preallocated_blocks(24,64*MiB,1)==24);
    assert(preallocated_blocks(24,64*MiB,2)==4);
    assert(preallocated_blocks(2,64*MiB,2)==2);
    assert(preallocated_blocks(8,512*MiB,2)==0);
    assert(preallocated_blocks(0,64*MiB,2)==0);
}''')
            subprocess.run([compiler,'-std=c++17','-O2','-static','-I'+str(ROOT/'engine/gpu/vk'),
                str(p/'test.cpp'),'-o',str(p/'test.exe')],check=True,capture_output=True)
            subprocess.run([str(p/'test.exe')],check=True,timeout=10)
