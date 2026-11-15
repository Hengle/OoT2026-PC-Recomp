"""Bound cache growth and amortize completed-resource cleanup without changing shader ABI."""
from pathlib import Path
import shutil
from engine_stability import replace_once

HERE = Path(__file__).parent
def apply(root):
    root = Path(root)
    shutil.copy2(HERE/'hud/ocr_streaming_policy.h', root/'gpu/vk/ocr_streaming_policy.h')
    path = root/'gpu/vk/vk_texture.cpp'
    text = path.read_text(encoding='utf-8')
    text = replace_once(text, '#include "ocr_resource_policy.h"\n',
        '#include "ocr_resource_policy.h"\n#include "ocr_streaming_policy.h"\n')
    text = replace_once(text, '    for (auto it = dead.begin(); it != dead.end();) {\n', '''    // Completed resources are safe to destroy, but hundreds of driver frees in
    // one frame cause a periodic hitch. Spread optional cleanup; low-memory and
    // GPU-pressure conditions still drain immediately. Never relax last_value.
    const auto cleanup_start = std::chrono::steady_clock::now();
    unsigned cleanup_retired = 0;
    uint64_t cleanup_pending_bytes = 0;
    for (const auto& resource : dead) cleanup_pending_bytes += resource.bytes;
    const bool cleanup_pressure = ocr_idle_cap <= (64ull << 20) || pool_pressed;
    for (auto it = dead.begin(); it != dead.end();) {
        if (ocr_streaming::defer_cleanup(cleanup_retired,
            std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - cleanup_start).count(),
            dead.size(), cleanup_pending_bytes, cleanup_pressure, ocr_streaming::mode())) break;
''')
    text = replace_once(text, '''        if (it->pool_key) {   // (a render target's image: kept for the next of its shape, above)
''', '''        ++cleanup_retired;
        cleanup_pending_bytes -= std::min(cleanup_pending_bytes, it->bytes);
        if (it->pool_key) {   // (a render target's image: kept for the next of its shape, above)
''')
    text = replace_once(text, '            if (frame_no % 600 == 0)\n                logf("[OcarinaReborn/MEM] system:', '''            // Explicit texture-memory selections keep their meaning. Auto leaves
            // headroom before the reactive RAM guard has to evict under pressure.
            if (!ocr_texture_budget_gb() && !getenv("RX_VK_TEX_MAX_MB") && !vram_env) {
                const uint64_t before = budget;
                budget = ocr_streaming::texture_limit(budget, ms.ullTotalPhys, ocr_streaming::mode());
                ocr_ram_limited = budget < before;
                static bool reported = false;
                if (!reported) {
                    reported = true;
                    logf("[OcarinaReborn/PERF] streaming mode %d: Auto texture budget %llu -> %llu MB, system RAM %llu MB",
                        ocr_streaming::mode(), (unsigned long long)(before >> 20), (unsigned long long)(budget >> 20),
                        (unsigned long long)(ms.ullTotalPhys >> 20));
                }
            }
            if (frame_no % 600 == 0)
                logf("[OcarinaReborn/MEM] system:''')
    text = replace_once(text, 'ocr_ram_limited = held < budget;', 'ocr_ram_limited = ocr_ram_limited || held < budget;')
    # Avoid scanning every texture in roomy frames when no hold needs adjustment.
    text = replace_once(text, '            if (!ocr_ram_urgent && ms.ullAvailPhys >= (1024ull << 20)',
        '            if ((held || short_commit || short_phys) && !ocr_ram_urgent && ms.ullAvailPhys >= (1024ull << 20)')
    path.write_text(text, encoding='utf-8', newline='\n')
