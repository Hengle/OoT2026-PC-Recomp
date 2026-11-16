// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>

namespace ocr_faults {
// Whether faults recorded in earlier runs keep a program out of the driver for good.
// The lasting list exists for AMD's Windows driver, where a faulted compile left later builds
// of that program waiting forever (driver_faults.h, issue 996). Elsewhere one fault, for example
// under memory pressure, removed a program for every later run: tester package
// 20261115-150320 (NVIDIA) lost about two draws a frame and showed wrong colours. On other
// drivers the program is tried again each run; a new fault still keeps it out for that run.
// RX_VK_DRIVER_FAULTS=2 keeps the lasting list on every driver.
inline bool keep_earlier_faults(uint32_t vendor, int mode) {
    return mode == 2 || vendor == 0x1002;
}
}
