// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>

namespace ocr_intel {
// Experimental workaround for the two compute programs bracketing repeated
// forest hangs in tester package 20261115-180150. A checkpoint is not proof of
// a compiler bug. Keep shader semantics and all dispatches; request the driver's
// unoptimized path only for these programs, on Intel's Windows driver.
inline bool forest_compute(uint32_t vendor, bool intel_windows, uint64_t key, bool enabled) {
    return enabled && vendor == 0x8086 && intel_windows &&
        (key == 0x685adb41edc19de7ull || key == 0x6637ac1d052d22d4ull);
}
}
