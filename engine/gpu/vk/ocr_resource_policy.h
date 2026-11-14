// Ocarina Reborn: bounded CPU uploads and pressure-sensitive idle reserves.
#pragma once
#include <algorithm>
#include <cstdint>

namespace ocr_resources {
constexpr uint64_t MB = 1ull << 20;
inline unsigned upload_threads(uint64_t bytes, unsigned rows, unsigned depth,
                               unsigned tile_depth, unsigned cpus, uint64_t threshold = 4 * MB) {
    // Leave CPU capacity for the game. Small jobs and 3D layouts stay serial.
    if (bytes < threshold || depth != 1 || tile_depth || rows < 2) return 1;
    return std::max(1u, std::min({cpus / 2, 8u, rows,
        static_cast<unsigned>(std::min<uint64_t>(bytes / (2 * MB), 8))}));
}
inline uint64_t idle_limit(uint64_t normal, uint64_t commit_free, uint64_t ram_free, uint64_t reserve) {
    const uint64_t physical_reserve = std::max(reserve, 1536 * MB);
    if (commit_free < reserve || ram_free < physical_reserve) return std::min(normal, 32 * MB);
    if (commit_free < reserve + 512 * MB || ram_free < physical_reserve + 512 * MB)
        return std::min(normal, 64 * MB);
    return normal;
}
struct IdleReserve {
    uint64_t limit = UINT64_MAX, recover_at = 0;
    uint64_t update(uint64_t candidate, uint64_t now_ms) {
        // Shrink immediately, but only grow after five seconds without renewed pressure.
        if (candidate <= limit) { limit = candidate; recover_at = now_ms + 5000; }
        else if (now_ms >= recover_at) { limit = candidate; recover_at = now_ms + 5000; }
        return limit;
    }
};
} // namespace ocr_resources
