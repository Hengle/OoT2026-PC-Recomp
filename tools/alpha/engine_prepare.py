"""Bound first preparation work and retain lazy loads on memory-constrained PCs."""
from pathlib import Path
import shutil
from engine_stability import replace_once
CHANGES = [('gpu/vk/vk_draw.cpp',
  '    const bool listed = which && !strcmp(which, "listed");\n'
  '    plan.all = which && !plan.learned_only && !listed ? !strcmp(which, "all") : listed ? plan.keys.empty() : '
  '!plan.learned;',
  '    // Default to programs observed in real play, not every speculative variant.\n'
  '    // An empty list is valid: first dispatch builds a missing program normally.\n'
  '    plan.all = which && !strcmp(which, "all");'),
 ('gpu/vk/vk_draw.cpp',
  '    const bool libraries = gpl_wanted() && !env_on("RX_VK_NO_WARM");',
  '    // The regular preparation translates all shaders and warms recorded pipelines.\n'
  '    // Full speculative warming is optional: it took hours on compute-fallback GPUs.\n'
  '    const bool full_prepare = env_on("RX_VK_PREPARE_FULL");\n'
  '    const bool libraries = full_prepare && gpl_wanted() && !env_on("RX_VK_NO_WARM");'),
 ('gpu/vk/vk_draw.cpp',
  '    bool warm_cs = !env_on("RX_VK_NO_WARM") && !background;',
  '    bool warm_cs = full_prepare && !env_on("RX_VK_NO_WARM") && !background;'),
 ('gpu/vk/vk_draw.cpp',
  '    if (notes.empty() || env_on("RX_VK_NO_PREDICT")) {',
  '    if (notes.empty() || env_on("RX_VK_NO_PREDICT") || !env_on("RX_VK_PREPARE_FULL")) {\n'
  '        if (!notes.empty() && !env_on("RX_VK_PREPARE_FULL"))\n'
  '            logf("vk: preparation: recorded pipelines only; speculative prediction is optional '
  '(RX_VK_PREPARE_FULL=1)");'),
 ('gpu/vk/vk_draw.cpp',
  '    const unsigned threads = std::min(usable_cpus(), 16u);',
  '    const unsigned threads = ocr_shader_workers(std::min(usable_cpus(), 16u));'),
 ('gpu/vk/vk_draw.cpp',
  '        program_cache_borrow(progs[i], [&](Program& p) {\n            ensure_layout(p);',
  '        program_cache_borrow(progs[i], [&](Program& p) {\n'
  '            ensure_layout(p);\n'
  '            // Warm the recorded mesh-fallback compute stages too. Borrowed objects\n'
  '            // are private to this worker; release every temporary pipeline below.\n'
  '            if (p.fallback) fallback_compute_pipelines(p);'),
 ('gpu/vk/vk_draw.cpp',
  '                (made ? built : failed)++;\n            }\n        });',
  '                (made ? built : failed)++;\n'
  '            }\n'
  '            for (VkPipeline pl : p.fallback_compute) if (pl) vkDestroyPipeline(dev.device, pl, nullptr);\n'
  '            p.fallback_compute.clear();\n'
  '        });'),
 ('gpu/vk/vk_draw.cpp',
  'void precompile_run(void (*progress)(size_t done, size_t total)) {\n',
  'void precompile_run(void (*progress)(size_t done, size_t total)) {\n'
  '    // A builder process never plays. Keeping tens of thousands of pipelines alive\n'
  '    // until exit needlessly exhausts RAM, especially on compute-fallback GPUs.\n'
  '    if (env_on("HOOKSHOT_PREPARE_ONLY")) {\n'
  '        precompile_warm(progress);\n'
  '        return;\n'
  '    }\n'),
 ('gpu/vk/vk_programs.cpp',
  '    const load_default::Choice c = load_default::choose(getenv("RX_VK_LOAD"), native_mesh, '
  'load_default::marker_there(load_fallback_path()),\n'
  '                                                        env_on("RX_VK_PROGRAM_CACHE_ZSTD"));',
  '    bool marker = load_default::marker_there(load_fallback_path());\n'
  '    MEMORYSTATUSEX memory{}; memory.dwLength = sizeof memory;\n'
  '    if (!getenv("RX_VK_LOAD") && GlobalMemoryStatusEx(&memory) &&\n'
  '        ocr_prepare::avoid_resident_fallback(native_mesh,\n'
  '            marker && ocr_prepare::slow_load_marker(load_fallback_path()), memory.ullTotalPhys)) {\n'
  '        marker = false;\n'
  '        logf("vk: memory-aware startup: keeping lazy program loads on a <=20 GiB PC; a previous slow-load '
  'marker would retain every listed program");\n'
  '    }\n'
  '    const load_default::Choice c = load_default::choose(getenv("RX_VK_LOAD"), native_mesh, marker,\n'
  '                                                        env_on("RX_VK_PROGRAM_CACHE_ZSTD"));'),
 ('gpu/vk/vk_programs.cpp',
  '#include "load_default.h"',
  '#include "load_default.h"\n#include "ocr_prepare_policy.h"'),
 ('gpu/vk/vk_draw.cpp',
  '    const std::vector<uint64_t> computes = done == total && !prepare_stopped() ? program_cache_compute_keys() '
  ': std::vector<uint64_t>{};\n'
  '    std::atomic<size_t> computes_done{0}, computes_built{0}, computes_failed{0};',
  '    // Count compute work too: a live compiler must keep the watchdog moving.\n'
  '    std::atomic<size_t> computes_done{0}, computes_built{0}, computes_failed{0};'),
 ('gpu/vk/vk_draw.cpp',
  '    const size_t total = refs.size();\n    std::atomic<size_t> done{0}, built{0}, failed{0}, no_program{0};',
  '    const size_t total = refs.size();\n'
  '    const ComputePlan plan = computes_plan(getenv("RX_VK_PRECOMPILE_COMPUTES"), '
  '!env_on("RX_VK_NO_STATE_LIST"));\n'
  '    std::vector<uint64_t> computes = program_cache_compute_keys();\n'
  '    if (!plan.all) computes.erase(std::remove_if(computes.begin(), computes.end(),\n'
  '        [&](uint64_t key) { return plan.none || !plan.keys.count(key); }), computes.end());\n'
  '    const size_t progress_total = total + computes.size();\n'
  '    std::atomic<size_t> done{0}, built{0}, failed{0}, no_program{0};'),
 ('gpu/vk/vk_draw.cpp',
  '        if (progress) progress(done.load(), total);\n'
  '        prepare_progress_log("noted pipelines", done.load(), total, t0, log_at);',
  '        if (progress) progress(done.load(), progress_total);\n'
  '        prepare_progress_log("noted pipelines", done.load(), total, t0, log_at);'),
 ('gpu/vk/vk_draw.cpp',
  '        if (progress) progress(total, total);\n'
  '        prepare_progress_log("compute pipelines", computes_done.load(), computes.size(), c0, log_at);',
  '        if (progress) progress(total + computes_done.load(), progress_total);\n'
  '        prepare_progress_log("compute pipelines", computes_done.load(), computes.size(), c0, log_at);')]

def apply(root):
    root=Path(root)
    shutil.copy2(Path(__file__).parent/'hud/ocr_prepare_policy.h',root/'gpu/vk/ocr_prepare_policy.h')
    for rel,old,new in CHANGES:
        p=root/rel
        p.write_text(replace_once(p.read_text(encoding='utf-8'),old,new),encoding='utf-8',newline='\n')
