// Ocarina Reborn: which spare capture buffers to keep ready, and how many (vk_memory.cpp's capture pool).
// A capture is a submission's snapshot of the guest pages it wrote; at a scene load one is 16 to 256 MB, and a new buffer made on
// the submitting thread cost 10-63 ms there (2026-11-17, 9800X3D + RX 7900 XTX: 61 "capture pool miss" lines, 964 ms in all, in
// three runs). The spares were limited to 256 MB on a 32 GB PC, so the 32 + 64 + 128 MB made at the start filled it and a 192 or
// 256 MB buffer was never kept or made ahead; and only one spare of a class was made again, while a load takes several of a
// class within a second or two (a capture is kept until 24 newer ones are, so what a burst takes is what it holds at once).
// Pure policy, no Vulkan: tools/alpha/tests/test_capture_pool_policy.py runs it.
#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>

namespace ocr_cap_pool {
constexpr uint64_t MB = 1ull << 20;
constexpr int kClasses = 6;
constexpr uint64_t kClassMb[kClasses] = {16, 32, 64, 128, 192, 256};   // (cap_buf_size's classes from 16 MB up)
constexpr uint64_t kDemandMs = 60000;   // (a class asked for in the last minute is wanted: kept, made again when taken)
constexpr uint64_t kBurstMs = 3000;     // (takes of a class this close together are one load's: as many are kept ready)
constexpr int kMaxPerClass = 3;
constexpr size_t kMaxSpares = 16;

inline int class_of(uint64_t size) {
    for (int i = 0; i < kClasses; ++i) if (size == kClassMb[i] * MB) return i;
    return -1;
}

/// the spares' room in all, those being made counted too: 32 MB on a card of 6.5 GB or less (its memory is what they take),
/// else by RAM. 768 MB on 32 GB holds one of every class (688 MB) with room for a second small one; the RAM guard
/// (ocr_resources::idle_limit) still takes it down to 64 and 32 MB when RAM or commit run short
inline uint64_t spare_budget(uint64_t ram, bool small_vram) {
    if (small_vram) return 32 * MB;
    if (!ram || ram <= (9ull << 30)) return 64 * MB;
    if (ram <= (17ull << 30)) return 128 * MB;
    if (ram <= (33ull << 30)) return 768 * MB;
    return 1024 * MB;
}

/// what the loads asked for, by class (the pool's mutex held by the caller)
struct Demand {
    uint64_t asked_ms[kClasses] = {};
    uint64_t burst_start_ms[kClasses] = {};
    int burst[kClasses] = {};
    int peak[kClasses] = {};
    uint64_t peak_ms[kClasses] = {};
    // (when a take of the class found no spare of it left, or the start expected it: only then are spares made ahead. A class
    // whose buffers come back as fast as they are taken (a 16 MB capture every frame) needs none made: 1.1.4-6 made 17,000 and
    // destroyed 198,000 in 12 minutes, each given back while a fresh one waited)
    uint64_t ran_out_ms[kClasses] = {};
    void ran_out(int c, uint64_t now) { if (c >= 0 && c < kClasses && now) ran_out_ms[c] = now; }
    void ask(int c, uint64_t now) {
        if (c < 0 || c >= kClasses || !now) return;
        asked_ms[c] = now;
        if (!burst_start_ms[c] || now - burst_start_ms[c] > kBurstMs) burst_start_ms[c] = now, burst[c] = 0;
        ++burst[c];
        if (!peak_ms[c] || now - peak_ms[c] > kDemandMs) peak[c] = 0;   // (the biggest burst of a minute ago no longer counts)
        if (burst[c] >= peak[c]) peak[c] = burst[c], peak_ms[c] = now;
    }
    /// a class made ready ahead without being asked for yet (the start's spares): wanted for a minute, one of it
    void expect(int c, uint64_t now) {
        if (c < 0 || c >= kClasses || !now || asked_ms[c]) return;
        asked_ms[c] = now, peak[c] = std::max(peak[c], 1), peak_ms[c] = now, ran_out_ms[c] = now;
    }
    bool wanted(int c, uint64_t now) const {
        return c >= 0 && c < kClasses && asked_ms[c] && now >= asked_ms[c] && now - asked_ms[c] < kDemandMs;
    }
    /// how many spares of the class to keep ready
    int target(int c, uint64_t now) const {
        if (!wanted(c, now) || !ran_out_ms[c] || now - ran_out_ms[c] >= kDemandMs) return 0;
        return std::clamp(now - peak_ms[c] > kDemandMs ? 1 : peak[c], 1, kMaxPerClass);
    }
};

/// the spare for a capture of `need` bytes whose class is `target`: the smallest one of need..target (a 2 MB capture never takes
/// the 128 MB a load will ask for); when there is none and the capture is a load's (16 MB and more), the smallest bigger one,
/// instead of a new buffer made on the submitting thread. -1: none. `bigger` says which it was
inline int pick(const uint64_t* sizes, size_t n, uint64_t need, uint64_t target, bool allow_bigger, bool* bigger) {
    int best = -1;
    for (size_t i = 0; i < n; ++i)
        if (sizes[i] >= need && sizes[i] <= target && (best < 0 || sizes[i] < sizes[best])) best = (int)i;
    if (bigger) *bigger = false;
    if (best >= 0 || need < 16 * MB || !allow_bigger) return best;
    for (size_t i = 0; i < n; ++i)
        if (sizes[i] >= need && (best < 0 || sizes[i] < sizes[best])) best = (int)i;
    if (bigger) *bigger = best >= 0;
    return best;
}

/// the spare to give up first: a size of no class, then the class asked for longest ago, the bigger of two equally old ones.
/// `only_unwanted`: never one of a class still wanted (-1 then, when every spare is wanted)
inline int least_wanted(const uint64_t* sizes, size_t n, const Demand& d, uint64_t now, bool only_unwanted) {
    int best = -1;
    uint64_t best_at = ~0ull;
    for (size_t i = 0; i < n; ++i) {
        const int c = class_of(sizes[i]);
        if (only_unwanted && d.wanted(c, now)) continue;
        const uint64_t at = c < 0 ? 0 : d.asked_ms[c];
        if (best < 0 || at < best_at || (at == best_at && sizes[i] > sizes[best])) best = (int)i, best_at = at;
    }
    return best;
}

/// the class whose spares are furthest short of its target (counting those being made), the bigger one first between equals
/// (it costs the submitting thread most); -1: none short
inline int most_short(const int* have, const Demand& d, uint64_t now) {
    int best = -1, best_short = 0;
    for (int c = kClasses - 1; c >= 0; --c) {
        const int s = d.target(c, now) - have[c];
        if (s > best_short) best = c, best_short = s;
    }
    return best;
}
} // namespace ocr_cap_pool
