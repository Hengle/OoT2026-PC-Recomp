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

def apply(root):
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
