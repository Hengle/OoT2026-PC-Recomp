// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>

namespace ocr_intel {
// Experimental workaround for the compute programs at repeated forest hangs on
// one Intel Arc PC: 685adb41/6637ac1d (package 20261115-180150), 592079442d7129da
// (device lost at the Kokiri Sword chest, 20261115-182745), 499dbfd0721d2858
// (device lost, 1.0.9) and abccf81b45c5eb50 (compute mesh path). A checkpoint is
// not proof of a compiler bug. Keep shader semantics and all dispatches; request
// the driver's unoptimized path only for these programs, on Intel's Windows driver.
inline bool forest_compute(uint32_t vendor, bool intel_windows, uint64_t key, bool enabled) {
    return enabled && vendor == 0x8086 && intel_windows &&
        (key == 0x685adb41edc19de7ull || key == 0x6637ac1d052d22d4ull ||
         key == 0x592079442d7129daull || key == 0x499dbfd0721d2858ull ||
         key == 0xabccf81b45c5eb50ull);
}
}
