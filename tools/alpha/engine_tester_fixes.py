"""Private follow-up: input freshness, smaller startup residency, Intel trial.

Apply after engine_prepare to a staged engine. No game files or cache changes.
"""
from pathlib import Path
import shutil
from engine_stability import replace_once

CHANGES = []
def change(path, old, new):
    CHANGES.append((path, old, new))

change('host/pad_sdl.c', '#include "steam_pads.h"',
       '#include "steam_pads.h"\n#include "ocr_input_state.h"')
change('host/pad_sdl.c', 'static int state_count;', '''static int state_count;
static int64_t state_sample_ns;
static OcrPadDiagnostic state_diagnostic;''')
change('host/pad_sdl.c', '        uint64_t b = 0;\n        int32_t s[4] = {0};', '''        uint64_t b = 0;
        OcrPadDiagnostic diagnostic = {0};
        int32_t s[4] = {0};''')
change('host/pad_sdl.c', '''            if (!gc) continue;
            /* (hookshot) a real Valve pad''', '''            // Do not keep a disconnected device's input until the one-second rescan.
            if (!gc || !hos_sdl_pad_connected(gc)) continue;
            /* (hookshot) a real Valve pad''')
change('host/pad_sdl.c', '''            hos_filter_stick(hos_sdl_pad_axis(gc, AX_LX), hos_sdl_pad_axis(gc, AX_LY), z, v);
            hos_filter_stick(hos_sdl_pad_axis(gc, AX_RX), hos_sdl_pad_axis(gc, AX_RY), z, v + 2);''', '''            const int16_t raw_right[2] = {hos_sdl_pad_axis(gc, AX_RX), hos_sdl_pad_axis(gc, AX_RY)};
            hos_filter_stick(hos_sdl_pad_axis(gc, AX_LX), hos_sdl_pad_axis(gc, AX_LY), z, v);
            hos_filter_stick(raw_right[0], raw_right[1], z, v + 2);''')
change('host/pad_sdl.c', '''            if (inv_y) v[3] = -v[3];
            for (int k = 0; k < 4; k++)''', '''            if (inv_y) v[3] = -v[3];
            if (diagnostic.sampled_pads < 2) {
                const int at = diagnostic.sampled_pads++;
                diagnostic.raw_right[at][0] = raw_right[0];
                diagnostic.raw_right[at][1] = raw_right[1];
                diagnostic.rested[at] = pads[i].rested;
            }
            diagnostic.zone = z, diagnostic.invert_x = inv_x, diagnostic.invert_y = inv_y;
            for (int k = 0; k < 4; k++)''')
change('host/pad_sdl.c', '        state_count = count;', '''        state_count = count;
        state_sample_ns = now; // when polling began; a blocked device call cannot publish a fresh old sample
        state_diagnostic = diagnostic;''')
change('host/pad_sdl.c', '''    *buttons |= state_buttons;
    for (int k = 0; k < 4; k++)
        if ((state_stick[k] < 0 ? -state_stick[k] : state_stick[k]) > (stick[k] < 0 ? -stick[k] : stick[k]))
            stick[k] = state_stick[k];''', '''    if (ocr_pad_sample_fresh(state_sample_ns, hos_now_ns())) {
        *buttons |= state_buttons;
        for (int k = 0; k < 4; k++)
            if ((state_stick[k] < 0 ? -state_stick[k] : state_stick[k]) > (stick[k] < 0 ? -stick[k] : stick[k]))
                stick[k] = state_stick[k];
    }
    // Keep the device count while stale so XInput does not take over the same pad.''')
change('host/pad_sdl.c', '    const int n = !motion_live ? 0 : motion_count < max ? motion_count : max;',
       '    const int n = !motion_live || !ocr_pad_sample_fresh(state_sample_ns, hos_now_ns()) ? 0 : motion_count < max ? motion_count : max;')
change('host/pad_sdl.c', '/* (motion) the latest readings for nn_hid.c', '''/* Diagnostic reads never query SDL on the writer thread or wait for its poller.
   Two device models' axes at most, no serials, button history or text input. */
void hos_sdl_camera_snapshot(char *out, size_t cap) {
    if (!cap) return;
    if (!TryAcquireSRWLockShared(&state_lock)) { snprintf(out, cap, "sdl=busy"); return; }
    const int64_t now = hos_now_ns();
    snprintf(out, cap, "sdl=%d age_ms=%.1f fresh=%d right=%d,%d raw0=%d,%d rest0=%x raw1=%d,%d rest1=%x sampled=%d zone=%d inv=%d,%d",
        state_count, state_sample_ns ? (now-state_sample_ns)/1e6 : -1.0,
        ocr_pad_sample_fresh(state_sample_ns, now), state_stick[2], state_stick[3],
        state_diagnostic.raw_right[0][0], state_diagnostic.raw_right[0][1], state_diagnostic.rested[0],
        state_diagnostic.raw_right[1][0], state_diagnostic.raw_right[1][1], state_diagnostic.rested[1],
        state_diagnostic.sampled_pads, state_diagnostic.zone, state_diagnostic.invert_x, state_diagnostic.invert_y);
    ReleaseSRWLockShared(&state_lock);
}

/* (motion) the latest readings for nn_hid.c''')
change('host/nn_hid.c', 'static void read_input(uint64_t *buttons, int32_t stick[4]) {',
       'static void read_input_impl(uint64_t *buttons, int32_t stick[4]) {')
change('host/nn_hid.c', '#include "hos.h"', '#include "hos.h"\n#include "ocr_diagnostics.h"')
change('host/nn_hid.c', 'static void vibration_send(uint64_t handle, uint64_t value);', '''// Only the most recent camera output is kept, for the bounded diagnostic timeline.
static SRWLOCK input_diagnostic_lock = SRWLOCK_INIT;
static int32_t input_diagnostic_right[2];
static int64_t input_diagnostic_ns;
static void read_input(uint64_t *buttons, int32_t stick[4]) {
    read_input_impl(buttons, stick);
    if (ocr_diag_enabled() && TryAcquireSRWLockExclusive(&input_diagnostic_lock)) {
        input_diagnostic_right[0] = stick[2], input_diagnostic_right[1] = stick[3];
        input_diagnostic_ns = hos_now_ns();
        ReleaseSRWLockExclusive(&input_diagnostic_lock);
    }
}
void hos_input_snapshot(char *out, size_t cap) {
    void hos_sdl_camera_snapshot(char *out, size_t cap);
    if (!cap) return;
    hos_sdl_camera_snapshot(out, cap);
    const size_t at = strlen(out);
    if (at >= cap || !TryAcquireSRWLockShared(&input_diagnostic_lock)) return;
    // Observe the OS window only; game_in_front has input-thread state and logging.
    DWORD foreground_pid = 0;
    HWND foreground = GetForegroundWindow();
    if (foreground) GetWindowThreadProcessId(foreground, &foreground_pid);
    snprintf(out+at, cap-at, " final=%d,%d final_age_ms=%.1f front_os=%d mouse_mode=%d gyro=%d",
        input_diagnostic_right[0], input_diagnostic_right[1],
        input_diagnostic_ns ? (hos_now_ns()-input_diagnostic_ns)/1e6 : -1.0,
        foreground_pid == GetCurrentProcessId(), rx_option(6,0), rx_option(HOS_OPT_GYRO,1));
    ReleaseSRWLockShared(&input_diagnostic_lock);
}

static void vibration_send(uint64_t handle, uint64_t value);''')
change('host/ocr_diagnostics.c', 'void ocr_diag_mark(void) {\n', '''extern void hos_input_snapshot(char *out, size_t cap);
static void camera_input_event(void) {
    char detail[350];
    hos_input_snapshot(detail, sizeof detail);
    ocr_diag_event("camera_input", detail);
}
void ocr_diag_mark(void) {
''')
change('host/ocr_diagnostics.c', '''    ocr_diag_event("user_marker", "Player marked a problem (Ctrl+F8). Add room/boss/song details when exporting.");''', '''    ocr_diag_event("user_marker", "Player marked a problem (Ctrl+F8). Add room/boss/song details when exporting.");
    camera_input_event();''')
change('host/ocr_diagnostics.c', '        if(now<=active_until || seq%5==0) write_line(line);', '''        if(now<=active_until || seq%5==0) write_line(line);
        if(seq%5==0) camera_input_event();''')

change('gpu/vk/vk_programs.cpp', '''    bool marker = load_default::marker_there(load_fallback_path());
    MEMORYSTATUSEX memory{}; memory.dwLength = sizeof memory;
    if (!getenv("RX_VK_LOAD") && GlobalMemoryStatusEx(&memory) &&
        ocr_prepare::avoid_resident_fallback(native_mesh,
            marker && ocr_prepare::slow_load_marker(load_fallback_path()), memory.ullTotalPhys)) {
        marker = false;
        logf("vk: memory-aware startup: keeping lazy program loads on a <=20 GiB PC; a previous slow-load marker would retain every listed program");
    }
    const load_default::Choice c = load_default::choose(getenv("RX_VK_LOAD"), native_mesh, marker,
                                                        env_on("RX_VK_PROGRAM_CACHE_ZSTD"));''', '''    const bool marker = load_default::marker_there(load_fallback_path());
    MEMORYSTATUSEX memory{}; memory.dwLength = sizeof memory;
    const uint64_t ram = GlobalMemoryStatusEx(&memory) ? memory.ullTotalPhys : 0;
    const auto c = ocr_prepare::startup_choice(getenv("RX_VK_LOAD"), native_mesh, marker,
        marker && ocr_prepare::slow_load_marker(load_fallback_path()), ram, env_on("RX_VK_PROGRAM_CACHE_ZSTD"));
    // precompile_at_create still prepares every mesh-fallback compute pipeline.
    // Only unrelated graphics/compute programs wait until the game creates them.''')
change('gpu/vk/vk_draw.cpp', '#include "warm_bounded.h"',
       '#include "warm_bounded.h"\n#include "ocr_intel_compute.h"')
change('gpu/vk/vk_draw.cpp', '''    if (noopt && noopt_on) ci.flags |= VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT;
    return ci;''', '''    static const bool intel_trial = [] {
        const char *value = getenv("OCR_INTEL_FOREST_COMPAT");
        return !value || !env_value_off(value);
    }();
    const bool forest = ocr_intel::forest_compute(dev.props.vendorID,
        dev.driver_id == VK_DRIVER_ID_INTEL_PROPRIETARY_WINDOWS, q.key, intel_trial);
    if ((noopt && noopt_on) || forest) ci.flags |= VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT;
    if (forest) {
        static std::atomic<unsigned> said{0};
        if (said.fetch_add(1, std::memory_order_relaxed) < 2)
            logf("[OcarinaReborn/GPU] Intel forest compatibility trial: program %016llx, optimization disabled; not a confirmed fix (OCR_INTEL_FOREST_COMPAT=0 restores default)", (unsigned long long)q.key);
    }
    return ci;''')
change('gpu/vk/vk_draw.cpp', '''        VkComputePipelineCreateInfo ci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO};
        ci.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
        ci.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
        ci.stage.module = p.stages[0].module;
        ci.stage.pName = "main";
        pin_subgroup(ci.stage, p.workgroup[0]);
        ci.layout = p.layout;
        if (env_on("RX_VK_NOOPT")) ci.flags |= VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT;''',
       '''        // Use the same Intel trial policy during warming and actual play.
        const VkComputePipelineCreateInfo ci = compute_pipeline_info(p, true);''')

change('gpu/vk/vk_draw.cpp', '#include "ocr_intel_compute.h"',
       '#include "ocr_intel_compute.h"\n#include "ocr_fault_policy.h"')
change('gpu/vk/vk_draw.cpp', '''        const auto keys = driver_faults::parse(text, dev.props.vendorID, dev.props.driverVersion);
        q.load(keys);''', '''        auto keys = driver_faults::parse(text, dev.props.vendorID, dev.props.driverVersion);
        if (!keys.empty() && !ocr_faults::keep_earlier_faults(dev.props.vendorID, driver_faults_mode())) {
            logf("vk: %zu programs the driver faulted on in earlier runs are tried again (only AMD keeps them out; RX_VK_DRIVER_FAULTS=2: every driver)",
                 keys.size());
            keys.clear();
        }
        q.load(keys);''')

change('host/nn_vi.c', '''            if (gpu_us > budget * 1.05f && cur > 0.5f) cur = cur - 0.1f < 0.5f ? 0.5f : cur - 0.1f;''', '''            /* OCARINA_FPS_TARGET_MIN=<percent>: the lowest render scale (the launcher's weak-PC choice: 33) */
            static float floor_scale = -1.0f;
            if (floor_scale < 0.0f) {
                const char *m = getenv("OCARINA_FPS_TARGET_MIN");
                const int pct = m ? atoi(m) : 50;
                floor_scale = (pct < 25 ? 25 : pct > 100 ? 100 : pct) / 100.0f;
            }
            if (gpu_us > budget * 1.05f && cur > floor_scale) cur = cur - 0.1f < floor_scale ? floor_scale : cur - 0.1f;''')

# ---- Shader modules let go after their programs' listed pipelines are made (low-RAM PCs) ----
# A graphics program loaded at its create call keeps one VkShaderModule a stage; the driver keeps the SPIR-V
# with it. On an 8 GB tester PC (package 20261115-160915) 8,400 programs and 1.4 GB of code were read in play
# and never let go. Once every pipeline the lists name for the program is made, its modules are destroyed and
# where their code is in the program cache is kept; a later new pipeline reads the code and makes them again.
change('gpu/vk/vk_shader.h', '    VkShaderModule module = VK_NULL_HANDLE;\n    Shader::Info info;',
       '''    mutable VkShaderModule module = VK_NULL_HANDLE;   // (Ocarina Reborn: made again on demand, stage_modules_ready)
    Shader::Info info;''')
change('gpu/vk/vk_shader.h', '    mutable uint32_t phis = 0;\n};', '''    mutable uint32_t phis = 0;
    // (Ocarina Reborn) where this stage's SPIR-V is in ocarina_reborn_programs.bin (0 words: unknown). With no module, it was
    // let go after the program's listed pipelines were made (program_modules_drop) and stage_modules_ready reads it again
    int64_t code_at = 0;
    uint64_t code_words = 0;
};''')
change('gpu/vk/vk_shader.h', 'bool program_cache_complete(Program& p);', '''bool program_cache_complete(Program& p);
/// (Ocarina Reborn) a graphics program's modules let go (its pipelines are made); false: kept (no place in the file to read them from)
bool program_modules_drop(Program& p);
/// (Ocarina Reborn) every stage has its module again (read from the program cache); false: one could not be made
bool stage_modules_ready(const Program& p);
/// (Ocarina Reborn) OCR_SHADER_MODULE_DROP: 1 on, 0 off; default on with 20 GiB of RAM or less
bool program_modules_drop_on();
extern std::atomic<int64_t> modules_dropped, modules_remade;''')
change('gpu/vk/vk_progcache.cpp', '''            std::vector<uint32_t> spirv;
            r.list(spirv);
            r.list(st.c1);
            get_info(r, st.info);
            if (r.bad || spirv.empty()) {
                ok = false;
                break;
            }
            st.module = make_module(spirv);''', '''            std::vector<uint32_t> spirv;
            const size_t code_pos = (size_t)(r.p - payload) + 8;   // (after the list's count: the words themselves)
            r.list(spirv);
            r.list(st.c1);
            get_info(r, st.info);
            if (r.bad || spirv.empty()) {
                ok = false;
                break;
            }
            // (an uncompressed record: its code can be read again by position, program_modules_drop)
            if (payload == data.data() + head_size) st.code_at = d.at + (int64_t)code_pos, st.code_words = spirv.size();
            st.module = make_module(spirv);''')
change('gpu/vk/vk_progcache.cpp', '''bool program_cache_complete(Program& p) {
    std::lock_guard lk(light_mu);
    return complete_from(p, disk_in, &disk_mu);
}''', '''bool program_cache_complete(Program& p) {
    std::lock_guard lk(light_mu);
    return complete_from(p, disk_in, &disk_mu);
}
std::atomic<int64_t> modules_dropped{0}, modules_remade{0};
bool program_modules_drop_on() {
    static const bool on = [] {
        if (const char* v = getenv("OCR_SHADER_MODULE_DROP")) return atoi(v) != 0;
        MEMORYSTATUSEX m{};
        m.dwLength = sizeof m;
        return GlobalMemoryStatusEx(&m) && m.ullTotalPhys <= (20ull << 30);
    }();
    return on;
}
bool program_modules_drop(Program& p) {
    // (graphics programs only: a compute program has its own light path, and the mesh fallback's dispatches use its modules)
    if (p.compute || p.fallback || p.stages.empty()) return false;
    for (const Stage& st : p.stages)
        if (!st.module || !st.code_words) return false;
    for (Stage& st : p.stages) vkDestroyShaderModule(dev.device, st.module, nullptr), st.module = VK_NULL_HANDLE;
    modules_dropped.fetch_add((int64_t)p.stages.size(), std::memory_order_relaxed);
    return true;
}
bool stage_modules_ready(const Program& p) {
    // (code_at and code_words never change once the program is published; a module is only ever set again, under light_mu)
    bool missing = false;
    for (const Stage& st : p.stages)
        missing = missing || (st.code_words && !std::atomic_ref<VkShaderModule>(st.module).load(std::memory_order_acquire));
    if (!missing) return true;
    std::lock_guard lk(light_mu);   // (one thread makes them; a module once made again stays)
    for (const Stage& st : p.stages) {
        if (st.module || !st.code_words) continue;
        std::vector<uint32_t> spirv((size_t)st.code_words);
        disk_init();
        bool ok = disk_in != nullptr;
        if (ok) {
            std::lock_guard dk(disk_mu);
            _fseeki64(disk_in, st.code_at, SEEK_SET);
            ok = fread(spirv.data(), 4, spirv.size(), disk_in) == spirv.size();
        }
        const VkShaderModule made = ok ? make_module(spirv) : VK_NULL_HANDLE;
        if (made) std::atomic_ref<VkShaderModule>(st.module).store(made, std::memory_order_release);
        if (!made) {
            static std::atomic<int> logged{0};
            if (logged++ < 20)
                logf("vk: program cache: the code of program %016llx at %lld did not read again: that pipeline is left out",
                     (unsigned long long)p.key, (long long)st.code_at);
            return false;
        }
        modules_remade.fetch_add(1, std::memory_order_relaxed);
    }
    return true;
}''')
change('gpu/vk/vk_draw.cpp', '''    if (at.n < 0 || at.n > 8) return VK_NULL_HANDLE;   // (hookshot: at most 8 colour targets)
    const Shader::Info& vs = *vertex_info(p);''', '''    if (at.n < 0 || at.n > 8) return VK_NULL_HANDLE;   // (hookshot: at most 8 colour targets)
    if (!stage_modules_ready(p)) return VK_NULL_HANDLE;   // (Ocarina Reborn: modules let go after the listed pipelines)
    const Shader::Info& vs = *vertex_info(p);''')
change('gpu/vk/vk_programs.cpp', '''            } else if (notes != index_notes.end()) {
                for (const NoteAt& n : notes->second) {
                    if (n.variant != p->variant || !pipe_note_at(notes_in, n.at, note.get())) continue;
                    bytes += (int64_t)sizeof(PipeNote);
                    if (const VkPipeline pl = source.graphics(*p, *note)) census.load_pipes += pipeline_keep_ready(n.key, pl);
                    else census.load_pipes_cold++;   // (its first draw makes it, as before)
                }
            }''', '''            } else if (notes != index_notes.end()) {
                bool listed = false, all_made = true;
                for (const NoteAt& n : notes->second) {
                    if (n.variant != p->variant || !pipe_note_at(notes_in, n.at, note.get())) continue;
                    bytes += (int64_t)sizeof(PipeNote);
                    listed = true;
                    // (OCR_SHADER_MODULE_DROP=3, a test: the made pipeline is not kept, so its first draw makes it again from
                    // modules read back from the program cache)
                    static const bool rebuild = getenv("OCR_SHADER_MODULE_DROP") && atoi(getenv("OCR_SHADER_MODULE_DROP")) == 3;
                    if (const VkPipeline pl = rebuild ? VK_NULL_HANDLE : source.graphics(*p, *note)) census.load_pipes += pipeline_keep_ready(n.key, pl);
                    else census.load_pipes_cold++, all_made = false;   // (its first draw makes it, as before)
                }
                // (Ocarina Reborn) every listed pipeline made, and no other thread has the program yet: its modules go, and
                // a new pipeline of it later reads its code again (stage_modules_ready)
                // (OCR_SHADER_MODULE_DROP=2, a test: let them go even with a pipeline still to make, so its draw reads them again)
                static const bool always = getenv("OCR_SHADER_MODULE_DROP") && atoi(getenv("OCR_SHADER_MODULE_DROP")) >= 2;
                if (listed && (all_made || always) && program_modules_drop_on()) program_modules_drop(*p);
            }''')
change('gpu/vk/vk_programs.cpp', '''    if (ids_on.load(std::memory_order_acquire))
        logf("vk: module identifiers (%s)''', '''    if (program_modules_drop_on())
        logf("vk: shader modules let go after their listed pipelines (%s): %lld, made again for a new pipeline %lld "
             "(OCR_SHADER_MODULE_DROP=0: kept)", when, n(modules_dropped.load()), n(modules_remade.load()));
    if (ids_on.load(std::memory_order_acquire))
        logf("vk: module identifiers (%s)''')

def apply(root, perf=True):
    root = Path(root)
    pending = {}
    for rel, old, new in CHANGES:
        text = pending.get(rel, (root / rel).read_text(encoding='utf-8'))
        pending[rel] = replace_once(text, old, new)
    # Validate every anchor before writing any source file.
    for rel, text in pending.items():
        (root / rel).write_text(text, encoding='utf-8', newline='\n')
    here = Path(__file__).parent / 'hud'
    shutil.copy2(here / 'ocr_input_state.h', root / 'host/ocr_input_state.h')
    shutil.copy2(here / 'ocr_intel_compute.h', root / 'gpu/vk/ocr_intel_compute.h')
    shutil.copy2(here / 'ocr_prepare_policy.h', root / 'gpu/vk/ocr_prepare_policy.h')
    shutil.copy2(here / 'ocr_fault_policy.h', root / 'gpu/vk/ocr_fault_policy.h')
    if perf:
        apply_perf(root)


PERF = Path(__file__).parent / 'engine-perf.patch'


def apply_perf(root):
    """Renderer and host performance work on top of the fixes above (engine-perf.patch): threaded rendering (explicit
    OCR_THREADED_RENDERING=1 only until capture ordering is validated), the game's occlusion queries, sparse VRAM
    mirrors, late GPU copies that preserve newer CPU writes, CPU targeting and guarded native float regions,
    renderer PGO, per-draw costs, quick pipelines, and Intel compiler guards"""
    import os
    import subprocess
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(Path(root).resolve().parent))
    r = subprocess.run(['git', 'apply', '-p1', '--whitespace=nowarn', str(PERF)], cwd=str(root), capture_output=True,
                       text=True, env=env)
    if r.returncode:
        raise SystemExit('engine performance patch did not apply: ' + r.stderr[:400])
    if not (Path(root) / 'gpu/vk/threaded_rendering.h').is_file():
        raise SystemExit('engine performance patch: git apply said yes, but the engine is unchanged')
    import engine_startup_guard
    engine_startup_guard.apply(root)


def pre_perf_text(rel, engine=None):
    """(the checks of the earlier patches) an engine file as it was before engine-perf.patch: that patch reversed on a copy"""
    import os
    import subprocess
    import tempfile
    engine = Path(engine) if engine else Path(__file__).resolve().parents[2] / 'engine'
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / 'e' / rel
        dst.parent.mkdir(parents=True)
        dst.write_bytes((engine / rel).read_bytes())
        env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(Path(tmp)))
        r = subprocess.run(['git', 'apply', '-R', '-p1', '--whitespace=nowarn', '--include=' + rel, str(PERF)],
                           cwd=str(Path(tmp) / 'e'), capture_output=True, text=True, env=env)
        if r.returncode:
            raise RuntimeError('engine-perf.patch did not reverse on ' + rel + ': ' + r.stderr[:300])
        return dst.read_text(encoding='utf-8')
