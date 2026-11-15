"""Checked renderer changes; apply after engine_stability on a fresh engine."""
from pathlib import Path
import shutil
from engine_stability import replace_once

HERE = Path(__file__).parent

def apply(root):
    root = Path(root)
    shutil.copy2(HERE / 'hud/ocr_resource_policy.h', root / 'gpu/vk/ocr_resource_policy.h')
    # v1.0.8's distributed engine hashes this UNUSED legacy header. Keep its exact bytes for
    # cache continuity; nothing includes/calls it. Do not re-enable its retired visual workaround.
    legacy = root / 'gpu/vk/eden/shader_recompiler/ir_opt/oot_visual_workaround.h'
    legacy.parent.mkdir(parents=True, exist_ok=True)
    if not legacy.exists():
        shutil.copy2(HERE / 'hud/ocr_legacy_shader_stamp.h', legacy)
    memory = root / 'gpu/vk/vk_memory.cpp'
    text = memory.read_text(encoding='utf-8')
    text = replace_once(text, '#include "vk_internal.h"\n', '#include "vk_internal.h"\n#include "ocr_resource_policy.h"\n')
    text = replace_once(text, '    return v;\n}\nvoid cap_buf_free(', '''    // All callers hold cap_free_mu. Sample at most four times a second.
    static auto next = std::chrono::steady_clock::time_point{};
    static ocr_resources::IdleReserve state;
    static uint64_t limit = v;
    const auto now = std::chrono::steady_clock::now();
    if (now >= next) {
        next = now + std::chrono::milliseconds(250);
        MEMORYSTATUSEX ms{}; ms.dwLength = sizeof(ms);
        const char* e = getenv("OCR_RAM_RESERVE_MB");
        const uint64_t reserve = (uint64_t)std::max(512, e ? atoi(e) : 1024) << 20;
        const uint64_t candidate = GlobalMemoryStatusEx(&ms) ? ocr_resources::idle_limit(v, ms.ullAvailPageFile, ms.ullAvailPhys, reserve) : limit;
        limit = state.update(candidate, (uint64_t)std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count());
    }
    return limit;
}
void cap_buf_free(''')
    text = replace_once(text, '    std::lock_guard lk(cap_free_mu);\n    if (from_worker', '    std::unique_lock lk(cap_free_mu);\n    if (from_worker')
    text = replace_once(text, '    } else {\n        destroy_buffer(buffer, alloc);\n    }\n}\nvoid cap_buf_retire',
                        '    } else {\n        lk.unlock(); // Driver frees must not block capture pool access.\n        destroy_buffer(buffer, alloc);\n    }\n}\nvoid cap_buf_retire')
    text = replace_once(text, 'Pool* pool_of(uint64_t guest, uint64_t size) {',
                        'Pool* pool_of(uint64_t guest, uint64_t size, bool existing_only = false) {')
    text = replace_once(text, '    Pool* found = pool_lookup(guest, size);', '''    if (existing_only) {
        // Do not wait for background imports or pin/merge new guest memory for a one-off upload.
        auto it = imported.upper_bound(guest);
        if (it == imported.begin()) return nullptr;
        --it;
        if (it->second.lo > guest || it->second.hi < guest + size) return nullptr;
        return last_pool = slot = &it->second;
    }
    Pool* found = pool_lookup(guest, size);''')
    text = replace_once(text, 'BufferRef gpu_buffer(uint64_t gpu, uint64_t size) {',
                        'BufferRef gpu_buffer(uint64_t gpu, uint64_t size, bool existing_only) {')
    start = text.index('BufferRef gpu_buffer(')
    end = text.index('\nvoid memory_pool_created', start)
    body = replace_once(text[start:end], 'Pool* p = pool_of(guest, size);',
                        'Pool* p = pool_of(guest, size, existing_only);')
    text = text[:start] + body + text[end:]
    memory.write_text(text, encoding='utf-8', newline='\n')
    internal = root / 'gpu/vk/vk_internal.h'
    text = internal.read_text(encoding='utf-8')
    text = replace_once(text, 'BufferRef gpu_buffer(uint64_t gpu, uint64_t size);',
                        'BufferRef gpu_buffer(uint64_t gpu, uint64_t size, bool existing_only = false);')
    internal.write_text(text, encoding='utf-8', newline='\n')

    texture = root / 'gpu/vk/vk_texture.cpp'
    text = texture.read_text(encoding='utf-8')
    text = replace_once(text, '#include "vk_texture.h"\n', '#include "vk_texture.h"\n#include "ocr_resource_policy.h"\n')
    # Only this GPU decode path: ASTC uploads and storage-buffer binds keep their import behavior.
    text = replace_once(text, '''    if (!unswizzle_ready()) return false;
    const BufferRef src = gpu_buffer(tex.gpu, total);''', '''    if (!unswizzle_ready()) return false;
    // Importing a ~15 MB upload pinned/merged 40-72 MB on AMD and stalled replay for 20-40 ms.
    // Existing imports are still used; modest uploads otherwise take the bounded parallel CPU path.
    static const uint64_t cpu_max = (uint64_t)(getenv("OCR_UPLOAD_NO_IMPORT_MB")
        ? std::max(0, atoi(getenv("OCR_UPLOAD_NO_IMPORT_MB"))) : 32) << 20;
    const BufferRef src = gpu_buffer(tex.gpu, total, total <= cpu_max);
    if (!src && total <= cpu_max) {
        static std::atomic<unsigned> avoided{0};
        const unsigned n = ++avoided;
        if (n <= 4 || n % 128 == 0) logf("[OcarinaReborn/LOAD] upload without new host import: %llu KB (%u so far)",
            (unsigned long long)(total >> 10), n);
    }''')
    text = replace_once(text, '''                    const uint32_t nthreads = block_bytes >= (16u << 20) && g.td == 1 && !g.tile_d
                                                  ? std::clamp(std::thread::hardware_concurrency() / 2, 1u, 8u) : 1u;''', '''                    // 1440p RGBA uploads (~14 MB) previously missed the 16 MB parallel threshold.
                    static const uint64_t parallel_min = (uint64_t)(getenv("RX_VK_UPLOAD_PARALLEL_MB")
                        ? std::max(1, atoi(getenv("RX_VK_UPLOAD_PARALLEL_MB"))) : 4) << 20;
                    const uint32_t nthreads = ocr_resources::upload_threads(block_bytes, nrow, g.td, g.tile_d,
                        std::thread::hardware_concurrency(), parallel_min);''')
    text = replace_once(text, 'bool pool_pressed;   //', 'uint64_t ocr_idle_cap = UINT64_MAX; // renderer thread, refreshed before trimming completed resources\nbool pool_pressed;   //')
    text = replace_once(text, 'const uint64_t cap = pool_pressed ? 0 : pool_cap();',
                        'const uint64_t cap = pool_pressed ? 0 : std::min(pool_cap(), ocr_idle_cap);')
    text = replace_once(text, '    drawn_writeback_frame();\n', '''    drawn_writeback_frame();
    // Release optional reserves before squeezing live textures. GPU-in-flight checks below are unchanged.
    static auto memory_check = std::chrono::steady_clock::time_point{};
    static ocr_resources::IdleReserve idle_reserve;
    const auto memory_now = std::chrono::steady_clock::now();
    if (memory_now >= memory_check) {
        memory_check = memory_now + std::chrono::milliseconds(250);
        MEMORYSTATUSEX ms{}; ms.dwLength = sizeof(ms);
        const char* e = getenv("OCR_RAM_RESERVE_MB");
        const uint64_t reserve = (uint64_t)std::max(512, e ? atoi(e) : 1024) << 20;
        const uint64_t candidate = GlobalMemoryStatusEx(&ms)
            ? ocr_resources::idle_limit(UINT64_MAX, ms.ullAvailPageFile, ms.ullAvailPhys, reserve) : ocr_idle_cap;
        const uint64_t cap = idle_reserve.update(candidate, (uint64_t)std::chrono::duration_cast<std::chrono::milliseconds>(memory_now.time_since_epoch()).count());
        if (cap != ocr_idle_cap) logf("[OcarinaReborn/MEM] idle reserves: %s (commit free %llu MB, RAM free %llu MB)",
            cap == UINT64_MAX ? "normal" : cap <= (32ull << 20) ? "low (32 MB targets/captures)" : "reduced (64 MB)",
            (unsigned long long)(ms.ullAvailPageFile >> 20), (unsigned long long)(ms.ullAvailPhys >> 20));
        ocr_idle_cap = cap;
    }
''')
    text = replace_once(text, 'kept + it->size > keep || stale',
                        'kept + it->size > std::min(keep, std::max(kArena, ocr_idle_cap)) || stale')
    text = replace_once(text, '    for (auto& [last, tex] : order) {\n        // (total_bytes can have drifted', '    // Host-pressure eviction must not retire gigabytes in one render frame.\n    // Dead targets still use the existing sweep path; GPU lifetime/flush guards stay below.\n    const uint64_t ocr_target = ocr_resources::eviction_target(total_bytes, budget, ocr_ram_limited, ocr_ram_urgent);\n    for (auto& [last, tex] : order) {\n        // (total_bytes can have drifted')
    text = replace_once(text, 'total_bytes - pending_bytes <= budget / 8 * 7',
                        'total_bytes - pending_bytes <= ocr_target')
    texture.write_text(text, encoding='utf-8', newline='\n')
