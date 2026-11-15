// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>

/* A stalled poller must not replay a held stick/button indefinitely. This is
   sample age, not unchanged-value detection: a real held stick stays valid. */
static inline int ocr_pad_sample_fresh(int64_t sampled, int64_t now) {
    return sampled > 0 && now >= sampled && now - sampled <= 500000000LL;
}

typedef struct OcrPadDiagnostic {
    int32_t raw_right[2][2];
    unsigned rested[2];
    int sampled_pads, zone, invert_x, invert_y;
} OcrPadDiagnostic;
