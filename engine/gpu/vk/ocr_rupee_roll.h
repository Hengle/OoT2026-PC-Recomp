// Presentation only: the real wallet is never modified by this animation.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace ocr_hud {
struct RupeeRoll {
    double shown = -1, last_time = 0, speed = 0;
    int target = -1;
    uint64_t epoch = 0;

    void reset() { shown = -1; target = -1; speed = 0; }

    double update(int value, double now, uint64_t generation) {
        if (value < 0 || value > 9999 || !std::isfinite(now)) { reset(); return -1; }
        // Save loading, a hidden HUD, or a suspended window must not replay an old wallet.
        if (shown < 0 || epoch != generation || now < last_time || now - last_time > 2.0) {
            shown = target = value; speed = 0; epoch = generation; last_time = now;
            return shown;
        }
        const double step = speed * (now - last_time);
        if (target > shown) shown = std::min(double(target), shown + step);
        else if (target < shown) shown = std::max(double(target), shown - step);
        last_time = now;
        if (target != value) {
            target = value;
            const double gap = std::abs(target - shown);
            speed = gap / std::clamp(0.12 + gap * 0.025, 0.12, 0.50);
        }
        return shown;
    }
};

struct RupeeDigit { int lower, upper; double fraction; bool blank_lower; };
inline RupeeDigit rupee_digit(double shown, int place) {
    // Higher wheels turn only during the carry: 19 -> 20, 99 -> 100, etc.
    const int whole = int(std::floor(shown / place));
    const double fraction = std::clamp(shown - (whole + 1.0) * place + 1.0, 0.0, 1.0);
    return {whole % 10, (whole + 1) % 10, fraction, place > 1 && shown < place};
}
} // namespace ocr_hud
