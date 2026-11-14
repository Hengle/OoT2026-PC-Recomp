// Bounded synchronous texture jobs. No dependency on the shader compilation queue.
#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <exception>
#include <thread>
#include <vector>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace ocr_upload {
inline unsigned available_cpus() {
    unsigned count = std::max(1u, std::thread::hardware_concurrency());
#if defined(_WIN32)
    DWORD_PTR process = 0, system = 0;
    if (GetProcessAffinityMask(GetCurrentProcess(), &process, &system) && process) {
        unsigned allowed = 0;
        for (; process; process &= process - 1) ++allowed;
        count = std::min(count, allowed);
    }
#endif
    return count;
}

#if defined(_WIN32)
// Windows owns idle worker threads; all callbacks finish before run() returns.
// Unlike detached C++ workers, no callback waits inside this DLL during unload.
class Pool {
    TP_CALLBACK_ENVIRON environment_{};
    PTP_POOL pool_ = nullptr;
    unsigned helpers_ = 0;
public:
    explicit Pool(unsigned cpus = available_cpus()) {
        InitializeThreadpoolEnvironment(&environment_);
        const unsigned total = std::clamp(cpus / 2, 1u, 8u);
        if (total > 1 && (pool_ = CreateThreadpool(nullptr))) {
            helpers_ = total - 1;
            SetThreadpoolThreadMaximum(pool_, helpers_);
            if (SetThreadpoolThreadMinimum(pool_, helpers_)) {
                SetThreadpoolCallbackPool(&environment_, pool_);
            } else {
                // Memory/thread exhaustion: do the batch on the caller, never wait for workers
                // which the OS could not create.
                CloseThreadpool(pool_);
                pool_ = nullptr;
                helpers_ = 0;
            }
        }
    }
    ~Pool() {
        if (pool_) CloseThreadpool(pool_);
        DestroyThreadpoolEnvironment(&environment_);
    }
    Pool(const Pool&) = delete;
    Pool& operator=(const Pool&) = delete;
    unsigned helpers() const { return helpers_; }
    PTP_CALLBACK_ENVIRON environment() { return &environment_; }
};
inline thread_local bool inside_batch = false;
struct Batch {
    void* context;
    void (*call)(void*, unsigned);
    unsigned count;
    std::atomic<unsigned> next{0};
    std::array<std::exception_ptr, 8> errors{};
    void drain() noexcept {
        const bool previous = inside_batch;
        inside_batch = true;
        for (unsigned i; (i = next.fetch_add(1, std::memory_order_relaxed)) < count;) {
            try { call(context, i); }
            catch (...) { errors[i] = std::current_exception(); }
        }
        inside_batch = previous;
    }
    static void CALLBACK callback(PTP_CALLBACK_INSTANCE, void* context, PTP_WORK) {
        static_cast<Batch*>(context)->drain();
    }
};
template<class F> void run_on(Pool& pool, unsigned count, F& fn) {
    if (count < 2 || count > 8 || !pool.helpers() || inside_batch) {
        for (unsigned i = 0; i < count; ++i) fn(i);
        return;
    }
    Batch batch{&fn, [](void* context, unsigned i) { (*static_cast<F*>(context))(i); }, count};
    PTP_WORK work = CreateThreadpoolWork(Batch::callback, &batch, pool.environment());
    if (!work) {
        for (unsigned i = 0; i < count; ++i) fn(i);
        return;
    }
    for (unsigned i = 0; i < std::min(count - 1, pool.helpers()); ++i) SubmitThreadpoolWork(work);
    batch.drain(); // the requesting thread also works; no queue behind shader compilation
    WaitForThreadpoolWorkCallbacks(work, FALSE);
    CloseThreadpoolWork(work);
    for (const auto& error : batch.errors) if (error) std::rethrow_exception(error);
}
inline Pool& shared_pool() { static Pool pool; return pool; }
#endif

template<class F> void run(unsigned count, F& fn) {
    if (count < 2) { if (count) fn(0); return; }
#if defined(_WIN32)
    run_on(shared_pool(), count, fn);
#else
    // Preserve the portable path. Joining also happens after a callback/creation failure.
    std::vector<std::thread> threads;
    std::vector<std::exception_ptr> errors(count);
    auto invoke = [&](unsigned i) { try { fn(i); } catch (...) { errors[i] = std::current_exception(); } };
    unsigned i = 1;
    try { for (; i < count; ++i) threads.emplace_back(invoke, i); }
    catch (...) { for (; i < count; ++i) invoke(i); }
    invoke(0);
    for (auto& thread : threads) thread.join();
    for (const auto& error : errors) if (error) std::rethrow_exception(error);
#endif
}
} // namespace ocr_upload
