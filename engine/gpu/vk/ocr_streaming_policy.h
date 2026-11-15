// Ocarina Reborn: leave host-memory headroom and spread optional cleanup across frames.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdlib>

namespace ocr_streaming {
constexpr uint64_t MiB = 1ull << 20;
inline int mode() {
    static const int value = [] {
        const char* e = std::getenv("OCR_STREAMING_MODE");
        return e ? std::clamp(std::atoi(e), 0, 2) : 1;
    }();
    return value;
}
inline uint64_t texture_limit(uint64_t normal, uint64_t ram, int policy) {
    if (!policy || !ram) return normal;
    // Texture caches also consume driver/host bookkeeping. This is a cache limit,
    // never a texture-resolution change. GPU-only images retain their existing guards.
    const uint64_t share = policy == 2 ? ram / 8 : ram / 5;
    const uint64_t ceiling = policy == 2 ? 4096 * MiB : 12288 * MiB;
    const uint64_t rounded = share / (256 * MiB) * (256 * MiB);
    return std::min(normal, std::clamp(rounded, 1024 * MiB, ceiling));
}
inline uint64_t target_cache_limit(uint64_t normal, int policy) {
    return policy == 2 ? std::min(normal, 64 * MiB) : normal;
}
inline size_t preallocated_blocks(size_t normal, uint64_t block_bytes, int policy) {
    if (policy != 2 || !block_bytes) return normal;
    return std::min(normal, static_cast<size_t>((256 * MiB) / block_bytes));
}
inline bool defer_cleanup(unsigned retired, int64_t elapsed_us, size_t pending, uint64_t pending_bytes,
                          bool pressure, int policy) {
    // Always make progress, and drain promptly under pressure or a growing backlog.
    // One individual driver destruction may still exceed the time budget.
    return policy && !pressure && pending < 1024 && pending_bytes <= 256 * MiB && retired &&
           (retired >= 64 || elapsed_us >= 1500);
}
} // namespace ocr_streaming
