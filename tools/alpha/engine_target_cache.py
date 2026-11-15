"""Strict completed-target cache bounds; apply after engine_streaming."""
from pathlib import Path
import shutil
from engine_stability import replace_once

HERE = Path(__file__).parent

PUT = '''void pool_put(Dead& d) {
    // OCR_TARGET_CACHE_BOUND: admission is bounded, not just the later trim.
    // This function is reached only after the existing GPU-completion gate.
    Pooled item{d.image, d.allocation, std::move(d.view_map), d.bytes, pool_now_ms(), 0};
    std::vector<Pooled> release;
    {
        std::lock_guard lk(pool_mu);
        const uint64_t cap = pool_pressed ? 0 : std::min(pool_cap(), ocr_idle_cap);
        // Also bound metadata for tiny targets. Subtraction avoids integer overflow.
        if (item.bytes && item.bytes <= cap) {
            // Keep the newest shapes useful to the current scene. Rejecting every
            // arrival at a full cache would pin stale shapes until their age timeout.
            while (!target_pool.empty() && (pool_bytes > cap - item.bytes || pool_n >= 512)) {
                auto oldest = target_pool.begin();
                for (auto it = target_pool.begin(); it != target_pool.end(); ++it)
                    if (it->second.front().order < oldest->second.front().order) oldest = it;
                auto& entries = oldest->second;
                release.push_back(std::move(entries.front()));
                pool_bytes -= std::min(pool_bytes, release.back().bytes);
                --pool_n;
                entries.erase(entries.begin());
                if (entries.empty()) target_pool.erase(oldest);
            }
            item.order = ++pool_order;
            target_pool[d.pool_key].push_back(std::move(item));
            pool_bytes += d.bytes;
            ++pool_n;
        } else release.push_back(std::move(item));
    }
    // No driver call while holding the lock needed by parallel texture lookup.
    for (auto& image : release) pool_destroy(image);
}
'''


def apply(root):
    root = Path(root)
    shutil.copy2(HERE/'hud/ocr_streaming_policy.h', root/'gpu/vk/ocr_streaming_policy.h')
    p = root/'gpu/vk/vk_texture.cpp'
    text = p.read_text(encoding='utf-8')
    text = replace_once(text, '''void pool_put(Dead& d) {
    std::lock_guard lk(pool_mu);
    target_pool[d.pool_key].push_back(Pooled{d.image, d.allocation, std::move(d.view_map), d.bytes, pool_now_ms(), ++pool_order});
    pool_bytes += d.bytes, pool_n++;
}
''', PUT)
    text = replace_once(text, '        while (release.size() < most && !target_pool.empty()) {',
        '''        // OCR_TARGET_CACHE_BOUND: a lower cap must take effect in this pass.
        // The count budget applies only to optional age-based cleanup.
        while (!target_pool.empty() && (pool_bytes > cap || release.size() < most)) {''')
    text = replace_once(text, '    return mb << 20;\n}\nuint64_t pool_key_of(',
        '    return ocr_streaming::target_cache_limit(mb << 20, ocr_streaming::mode());\n}\nuint64_t pool_key_of(')
    p.write_text(text, encoding='utf-8', newline='\n')
    p = root/'gpu/vk/vk_vma.cpp'
    text = p.read_text(encoding='utf-8')
    text = replace_once(text, '#include "vram_compact.h"\n', '#include "vram_compact.h"\n#include "ocr_streaming_policy.h"\n')
    text = replace_once(text,
        '    return (size_t)vram_compact::blocks_at_start(heap, kImageBlock, holds_textures);',
        '''    // Lower-memory mode reserves less unused memory at startup. The pool
    // may still grow when needed; explicit RX_VK_IMAGE_PREALLOC above wins.
    return ocr_streaming::preallocated_blocks(
        (size_t)vram_compact::blocks_at_start(heap, kImageBlock, holds_textures),
        kImageBlock, ocr_streaming::mode());''')
    p.write_text(text, encoding='utf-8', newline='\n')
