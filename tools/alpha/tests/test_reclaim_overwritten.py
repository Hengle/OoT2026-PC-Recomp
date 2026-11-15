"""Run the production eviction gate over age-ordered live/dead texture mixtures."""
from pathlib import Path
import shutil, subprocess, sys, tempfile, unittest

ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA))
import engine_resource_memory


class ReclaimTests(unittest.TestCase):
    def compile_run(self, source):
        start = source.index('    for (auto& [last, tex] : order) {', source.index('const uint64_t ocr_target ='))
        end = source.index('        // (hookshot, RX_VK_COMPACT: the hold\'s pass, above.', start)
        gate = source[start:end]
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p/'test.cpp').write_text(HARNESS.replace('/* GATE */', gate), encoding='utf-8')
            result = subprocess.run([shutil.which('clang++'), '-std=c++17', '-O2', '-static',
                '-I'+str(ROOT/'engine/gpu/vk'), str(p/'test.cpp'), '-o', str(p/'test.exe')],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            return subprocess.run([str(p/'test.exe')], capture_output=True, text=True)

    def test_reclaims_later_dead_targets_without_evicting_live_content(self):
        source = (ROOT/'engine/gpu/vk/vk_texture.cpp').read_text(encoding='utf-8')
        fixed = engine_resource_memory.reclaim_overwritten(source)
        result = self.compile_run(fixed)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        previous = fixed
        for old, new in reversed(engine_resource_memory.RECLAIM_CHANGES):
            previous = previous.replace(new, old, 1)
        self.assertEqual(engine_resource_memory.reclaim_overwritten(previous), fixed)
        self.assertNotEqual(self.compile_run(previous).returncode, 0, 'Regression must fail with the old early break')
        self.assertEqual(engine_resource_memory.reclaim_overwritten(fixed), fixed)


HARNESS = r'''
#include <algorithm>
#include <cstdint>
#include <vector>
#include <utility>
#include <cstdio>
#include "keep_rendered.h"
bool env_on(const char*) { return false; }
struct Texture {uint64_t last_frame,last_value,bytes; bool shifted,overwritten;};
struct Result {std::vector<Texture*> gone;uint64_t bytes=0;};
Result select(std::vector<std::pair<uint64_t,Texture*>> order, bool sweep, bool by_hold,
              uint64_t total_bytes=300, uint64_t ocr_target=200) {
    const uint64_t frame_no=1000,need_dead=3,need_unused=60,completed=8,used=0,allowed=1000;
    const bool known=true;
    uint64_t pending_bytes=0;
    auto drawn_over_shifted=[](Texture* t){return t->shifted;};
    auto drawn_over=[](Texture* t){return t->overwritten;};
    Result result;
    /* GATE */
        if (sweep && !overwritten) continue;
        result.gone.push_back(tex);pending_bytes+=tex->bytes;
    }
    result.bytes=pending_bytes;
    return result;
}
#define CHECK(x) do{if(!(x)){printf("FAIL line %d: %s\n",__LINE__,#x);return 1;}}while(0)
int main() {
    Texture live{100,8,100,false,false},live2{110,8,100,false,false};
    Texture dead{120,8,80,true,false},same{130,8,80,false,true};
    Texture busy{140,9,80,true,false},young{999,8,80,true,false};
    std::vector<std::pair<uint64_t,Texture*>> order;
    for(auto* t:{&live,&live2,&dead,&same,&busy,&young}) order.push_back({t->last_frame,t});
    auto r=select(order,false,false);
    CHECK(r.gone.size()==3 && r.gone[0]==&live && r.gone[1]==&dead && r.gone[2]==&same);
    CHECK(r.bytes==260); // budget reached by the first live texture, both later dead targets still reclaimed
    r=select(order,false,false,50,50); // budget already met; never evict a live texture
    CHECK(r.gone.size()==2 && r.gone[0]==&dead && r.gone[1]==&same);
    r=select(order,true,false);
    CHECK(r.gone.size()==2);
    r=select(order,false,true);
    CHECK(r.gone.size()==4); // the separate hold policy still gets candidates
    // Very large indivisible images may put pending beyond total; no unsigned wrap.
    live.bytes=400;
    r=select(order,false,false);
    CHECK(r.gone.size()==3 && r.gone[2]==&same);
    puts("PASS: live budget, later overwritten targets, GPU completion, age, sweep/hold and saturating accounting");
}
'''
