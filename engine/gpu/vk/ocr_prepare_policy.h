// SPDX-License-Identifier: GPL-3.0-or-later
// Memory-aware preparation policy; independent of the shader translator/cache format.
#pragma once
#include <algorithm>
#include <cstdint>
namespace ocr_prepare {
constexpr uint64_t MiB = 1024ull * 1024;
inline unsigned workers(unsigned requested, unsigned cpus, uint64_t available, uint64_t commit) {
    // Leave one logical CPU and 1 GiB of headroom. A driver compiler can allocate
    // hundreds of MiB per worker; more workers under paging are usually slower.
    const uint64_t free = std::min(available, commit);
    const unsigned memory = free > 1024 * MiB ? unsigned(std::min<uint64_t>(8, (free - 1024 * MiB) / (768 * MiB))) : 1;
    return std::max(1u, std::min({requested, cpus > 1 ? cpus - 1 : 1u, std::max(1u, memory)}));
}
inline bool avoid_resident_fallback(bool native_mesh, bool marker, uint64_t total) {
    return native_mesh && marker && total && total <= 20ull * 1024 * MiB;
}
}
