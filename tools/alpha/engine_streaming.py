"""Bounded upload workers, 2D scratch and idle render-target reuse; after resource_memory."""
from pathlib import Path
import shutil
from engine_stability import replace_once
HERE = Path(__file__).parent
CHANGES = [('#include "ocr_resource_policy.h"', '#include "ocr_resource_policy.h"\n#include "ocr_upload_batch.h"'),
 ('    uint64_t bytes, since;', '    uint64_t bytes, since, order;'),
 ('uint64_t pool_bytes, pool_n, st_pool_reused, st_pool_made, st_pool_destroyed;',
  'uint64_t pool_bytes, pool_n, st_pool_reused, st_pool_made, st_pool_destroyed;\n'
  'uint64_t pool_order;\n'
  'uint64_t pool_now_ms() {\n'
  '    return (uint64_t)std::chrono::duration_cast<std::chrono::milliseconds>(\n'
  '        std::chrono::steady_clock::now().time_since_epoch()).count();\n'
  '}'),
 ('120 presents is destroyed, at most 16 a present',
  'two seconds is destroyed, at most 16 a present, globally oldest first'),
 ('std::move(d.view_map), d.bytes, frame_no}',
  'std::move(d.view_map), d.bytes, pool_now_ms(), ++pool_order}'),
 ('/// (texture_frame, each present) the pool over its bound, or all of it while VRAM is short, and what '
  'waits in it unused for 120\n'
  '/// presents: destroyed, at most 16 a present (64 while VRAM is short). Returns how many\n'
  'size_t pool_trim() {\n'
  '    std::lock_guard lk(pool_mu);\n'
  '    const uint64_t cap = pool_pressed ? 0 : std::min(pool_cap(), ocr_idle_cap);\n'
  '    const size_t most = pool_pressed ? 64 : 16;\n'
  '    size_t n = 0;\n'
  '    for (auto it = target_pool.begin(); it != target_pool.end() && n < most;) {\n'
  '        auto& v = it->second;\n'
  '        for (size_t i = 0; i < v.size() && n < most;) {   // (the oldest of a shape first: the front)\n'
  '            if (pool_bytes <= cap && frame_no - v[i].since <= 120) {\n'
  '                ++i;\n'
  '                continue;\n'
  '            }\n'
  '            pool_destroy(v[i]);\n'
  '            pool_bytes -= std::min(pool_bytes, v[i].bytes), pool_n--, n++;\n'
  '            v.erase(v.begin() + (ptrdiff_t)i);\n'
  '        }\n'
  '        it = v.empty() ? target_pool.erase(it) : std::next(it);\n'
  '    }\n'
  '    return n;\n'
  '}\n',
  '/// Completed images only: keep recent shapes within the existing memory cap.\n'
  '/// Age is wall time, so a 120 FPS display does not halve cache lifetime.\n'
  'size_t pool_trim() {\n'
  '    std::vector<Pooled> release;\n'
  '    {\n'
  '        std::lock_guard lk(pool_mu);\n'
  '        const uint64_t cap = pool_pressed ? 0 : std::min(pool_cap(), ocr_idle_cap);\n'
  '        const size_t most = pool_pressed ? 64 : 16;\n'
  '        const uint64_t now = pool_now_ms();\n'
  '        while (release.size() < most && !target_pool.empty()) {\n'
  '            auto oldest = target_pool.end();\n'
  '            // Each shape is insertion ordered; only its first entry can be globally oldest.\n'
  '            for (auto it = target_pool.begin(); it != target_pool.end(); ++it)\n'
  '                if (oldest == target_pool.end() || it->second.front().order < '
  'oldest->second.front().order)\n'
  '                    oldest = it;\n'
  '            auto& entries = oldest->second;\n'
  '            const auto& first = entries.front();\n'
  '            if (pool_bytes <= cap && now - first.since <= 2000) break;\n'
  '            release.push_back(std::move(entries.front()));\n'
  '            pool_bytes -= std::min(pool_bytes, release.back().bytes);\n'
  '            --pool_n;\n'
  '            entries.erase(entries.begin());\n'
  '            if (entries.empty()) target_pool.erase(oldest);\n'
  '        }\n'
  '    }\n'
  '    // Driver frees must not hold the lock used by parallel texture lookup/creation.\n'
  '    for (auto& image : release) pool_destroy(image);\n'
  '    return release.size();\n'
  '}\n'),
 ('        const uint64_t per = ((n + nt - 1) / nt + 0xFFFF) & ~0xFFFFull;\n'
  '        std::vector<std::thread> pool;\n'
  '        auto part =',
  '        const uint64_t per = ((n + nt - 1) / nt + 0xFFFF) & ~0xFFFFull;\n        auto part ='),
 ('        for (uint32_t t = 1; t < nt; t++) pool.emplace_back(part, t);\n'
  '        part(0);\n'
  '        for (std::thread& t : pool) t.join();',
  '        ocr_upload::run(nt, part);'),
 ('    if (nthreads > 1) {\n'
  '        std::vector<std::thread> th;\n'
  '        for (uint32_t t = 1; t < nthreads; t++) th.emplace_back(part, t);\n'
  '        part(0);\n'
  '        for (auto& x : th) x.join();\n'
  '    } else {\n'
  '        part(0);\n'
  '    }',
  '    ocr_upload::run(nthreads, part);'),
 ('                    const bool gather_parts = nthreads > 1 && !(direct && avail >= need) && from < total;',
  '                    // Bound sparse/truncated 2D scratch even on a single CPU worker.\n'
  '                    const bool gather_parts = g.td == 1 && !g.tile_d &&\n'
  '                        !(direct && avail >= need && from < total && total - from >= need);'),
 ('                    if (nthreads > 1) {\n                        const uint64_t out_row',
  '                    if (nthreads > 1 || gather_parts) {\n                        const uint64_t out_row'),
 ('                        std::vector<std::thread> pool;\n'
  '                        for (uint32_t t = 1; t < nthreads; t++) pool.emplace_back(part, t);\n'
  '                        part(0);\n'
  '                        for (std::thread& t : pool) t.join();',
  '                        ocr_upload::run(nthreads, part);'),
 ('                                    rows = mine.data();',
  '                                    rows = mine.data();\n'
  '                                    // Preserve the submission snapshot, including gathered pages.\n'
  '                                    if (tex.gpu + at < (1ull << 40) && at < total)\n'
  '                                        rows = memory_as_submitted(tex.gpu + at, rows,\n'
  '                                            std::min(rows_n, total - at), mine);')]

def apply(root):
    root = Path(root)
    shutil.copy2(HERE/'hud/ocr_upload_batch.h', root/'gpu/vk/ocr_upload_batch.h')
    p = root/'gpu/vk/vk_texture.cpp'
    text = p.read_text(encoding='utf-8')
    for old, new in CHANGES: text = replace_once(text, old, new)
    p.write_text(text, encoding='utf-8', newline='\n')
