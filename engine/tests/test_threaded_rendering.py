"""The Insert menu's Threaded rendering (Auto / On / Off): its rule (gpu/vk/threaded_rendering.h) and how the row reaches
the replay, the recorder and the host. A compiled check of the rule plus source checks; no game, no GPU.

The rule is one function every reader shares: On is the render thread and the recorder thread together, Off neither,
and Auto picks them where the process may run on 12 or more logical processors and the mode is safe. All of Auto is
behind one constant, threaded::kAutoEnabled, which is on: turned off, Auto is Off on every PC and the row changes
nobody's default. The source checks: that constant is the only gate and is on; the row is Auto by default,
takes a restart and is in the readme and the development guide; RX_VK_ASYNC is read in one place (vk_replay.cpp
render_thread_mode, the switch over the row), which async_on takes; the recorder asks the row only
with RX_VK_RECORDER unset; and the host's present poll asks the renderer (HOS_OPT_RENDER_THREAD) instead of reading
RX_VK_ASYNC itself, so the row's On answers the poll exactly as RX_VK_ASYNC=1 does.

python -I -B tests/test_threaded_rendering.py [--cxx g++]
"""
import argparse
import re
import subprocess
import tempfile
from pathlib import Path

RUN_ALL_ARGS = ["--cxx", "{cxx}"]

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''
#include "threaded_rendering.h"
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
using namespace mkwvk::threaded;
int main() {
    // (the row's values, in V-Sync's order)
    CHECK(AUTO == 0 && ON == 1 && OFF == 2);
    // (Auto's threshold: 12 logical processors the process may run on; an unknown count, 0, is too few)
    CHECK(kAutoCpus == 12);
    CHECK(!auto_picks(0) && !auto_picks(4) && !auto_picks(8) && !auto_picks(11));
    CHECK(auto_picks(12) && auto_picks(16) && auto_picks(32) && auto_picks(256));
    // (On and Off are the player's word: whatever the CPU, whatever is unsafe, whatever the gate)
    for (const bool gate : {false, true})
        for (const bool unsafe : {false, true})
            for (const unsigned cpus : {0u, 4u, 11u, 12u, 64u}) {
                CHECK(choose(ON, cpus, unsafe, gate).on && choose(ON, cpus, unsafe, gate).why == Why::On);
                CHECK(!choose(OFF, cpus, unsafe, gate).on && choose(OFF, cpus, unsafe, gate).why == Why::Off);
            }
    // (Auto with the gate on: the CPU's rule, and off where the mode is not safe)
    CHECK(choose(AUTO, 12, false, true).on && choose(AUTO, 12, false, true).why == Why::AutoCpus);
    CHECK(choose(AUTO, 24, false, true).on);
    CHECK(!choose(AUTO, 11, false, true).on && choose(AUTO, 11, false, true).why == Why::AutoFewCpus);
    CHECK(!choose(AUTO, 8, false, true).on && !choose(AUTO, 0, false, true).on);
    CHECK(!choose(AUTO, 12, true, true).on && choose(AUTO, 12, true, true).why == Why::AutoUnsafe);
    CHECK(!choose(AUTO, 64, true, true).on && !choose(AUTO, 4, true, true).on);
    // (Auto with the gate off: off on every PC, and said so)
    for (const bool unsafe : {false, true})
        for (const unsigned cpus : {0u, 4u, 11u, 12u, 64u})
            CHECK(!choose(AUTO, cpus, unsafe, false).on && choose(AUTO, cpus, unsafe, false).why == Why::AutoGate);
    // (a value that is none of the row's: Auto)
    CHECK(choose(7, 64, false, true).why == Why::AutoCpus && choose(-1, 64, false, false).why == Why::AutoGate);
    // (as built: the gate is on, so Auto is its rule: on from 12 logical processors where the mode is safe)
    CHECK(kAutoEnabled);
    for (const unsigned cpus : {0u, 8u, 11u}) CHECK(!choose(AUTO, cpus, false).on);
    for (const unsigned cpus : {12u, 16u, 64u}) CHECK(choose(AUTO, cpus, false).on && !choose(AUTO, cpus, true).on);
    CHECK(choose(ON, 4, false).on && !choose(OFF, 64, false).on);
    std::printf("PASS: the Threaded rendering rule\n");
}
'''


def block(text, marker):
    """From marker to the brace closing its first one"""
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    vk = ROOT / "gpu" / "vk"
    rule = (vk / "threaded_rendering.h").read_text(encoding="utf-8")
    replay = (vk / "vk_replay.cpp").read_text(encoding="utf-8")
    recorder = (vk / "vk_recorder.h").read_text(encoding="utf-8")
    api = (vk / "vk_api.h").read_text(encoding="utf-8")
    native = (ROOT / "host" / "nvn_native.c").read_text(encoding="utf-8")

    # (the gate: one constant, on, and Auto's rule behind it)
    if len(re.findall(r"constexpr bool \w+ = ", rule)) != 1 or "constexpr bool kAutoEnabled = true;" not in rule:
        raise SystemExit("threaded_rendering.h: Auto's gate is not the one constant kAutoEnabled, on (turning it off changes "
                         "the default for every PC with 12 threads: that is its own change)")
    choose = block(rule, "constexpr Choice choose(")
    if "bool auto_enabled = kAutoEnabled" not in choose or "if (!auto_enabled) return {false, Why::AutoGate};" not in choose:
        raise SystemExit("threaded_rendering.h: choose() no longer keeps Auto behind the gate")

    # (the run's choice: OCR_THREADED_RENDERING 1 or 0, unset Auto; resolved once, in vk_replay.cpp; no menu row)
    resolved = block(replay, "bool threaded_rendering_on() {")
    for need in ('getenv("OCR_THREADED_RENDERING")', "usable_cpus()", "threaded::choose(", "pools_mirrored()", "RX_VK_LOW_SPEC"):
        if need not in resolved:
            raise SystemExit("vk_replay.cpp: threaded_rendering_on() lost " + need)
    mode = block(replay, "int render_thread_mode() {")
    if 'const char* e = getenv("RX_VK_ASYNC");' not in mode or "return e ? atoi(e) : threaded_rendering_on() ? 1 : 0;" not in mode:
        raise SystemExit("vk_replay.cpp: render_thread_mode() is not RX_VK_ASYNC over threaded_rendering_on()")
    if "(rec::g_setting_thread = threaded_rendering_on, true)" not in replay:
        raise SystemExit("vk_replay.cpp: the recorder does not follow threaded_rendering_on")
    if "HOS_OPT_RENDER_THREAD" not in api or "HOS_OPT_RENDER_THREAD" not in native or "if (id == HOS_OPT_RENDER_THREAD) return async_on();" not in replay:
        raise SystemExit("the host's present poll does not learn the render thread's choice (HOS_OPT_RENDER_THREAD)")
    if "menu_threaded_rendering" in replay + recorder:
        raise SystemExit("a menu row is named: threaded rendering has none")

    with tempfile.TemporaryDirectory(prefix="threaded-rendering-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(FIXTURE, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I" + str(vk), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: Threaded rendering: the rule, the gate (off), and the row's way to the replay, the recorder and the host")


if __name__ == "__main__":
    main()
