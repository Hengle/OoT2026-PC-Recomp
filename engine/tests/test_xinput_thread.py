"""Run production XInput polling with real Windows threads and a fake slow driver.

Checks empty-slot stalls, hot-plug, unplug, expired input, SDL takeover while the
driver is blocked, and retry after thread creation failure. No controller is read.
Based on Longshot c5e1421d213b1be07f86c2b102b757993d4d7df3 (GPL-3.0-or-later).
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from srccut import block

PRELUDE = r'''
#include <windows.h>
#include <xinput.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
static DWORD game_thread;
static volatile LONG on_game, elsewhere, connected, sdl_count, block_driver, block_empty;
static volatile LONG held = 1;
static HANDLE driver_entered, driver_release, empty_entered, empty_release;
static int fail_start = 1, start_calls;
static HANDLE test_CreateThread(LPSECURITY_ATTRIBUTES a, SIZE_T n, LPTHREAD_START_ROUTINE fn,
                               LPVOID arg, DWORD flags, LPDWORD id) {
    ++start_calls;
    if (fail_start) { fail_start = 0; return NULL; }
    return CreateThread(a, n, fn, arg, flags, id);
}
#define CreateThread test_CreateThread
typedef DWORD(WINAPI *XInputGetStateFn)(DWORD, XINPUT_STATE *);
static DWORD WINAPI fake_xinput(DWORD slot, XINPUT_STATE *s) {
    if (GetCurrentThreadId() == game_thread) InterlockedIncrement(&on_game);
    else InterlockedIncrement(&elsewhere);
    const int has = slot == 0 && InterlockedCompareExchange(&connected, 0, 0);
    if (slot == 0 && InterlockedCompareExchange(&block_driver, 0, 0)) {
        SetEvent(driver_entered);
        CHECK(WaitForSingleObject(driver_release, 4000) == WAIT_OBJECT_0);
    }
    if (slot == 1 && InterlockedCompareExchange(&block_empty, 0, 0)) {
        SetEvent(empty_entered);
        CHECK(WaitForSingleObject(empty_release, 4000) == WAIT_OBJECT_0);
    }
    if (!has) { Sleep(20); return ERROR_DEVICE_NOT_CONNECTED; }
    memset(s, 0, sizeof *s);
    if (InterlockedCompareExchange(&held, 0, 0)) {
        s->Gamepad.wButtons = XINPUT_GAMEPAD_A;
        s->Gamepad.sThumbLX = 20000;
    }
    return ERROR_SUCCESS;
}
static XInputGetStateFn xinput_get = fake_xinput;
void hos_host_thread_register_self(const char *name) { (void)name; }
static void hos_log(const char *format, ...) { (void)format; }
static int64_t hos_now_ns(void) {
    LARGE_INTEGER q, f;
    QueryPerformanceCounter(&q); QueryPerformanceFrequency(&f);
    return q.QuadPart / f.QuadPart * 1000000000LL + q.QuadPart % f.QuadPart * 1000000000LL / f.QuadPart;
}
int rx_option(int id, int otherwise) { return id == 11 || id == 16 || id == 17 ? 0 : otherwise; }
int hos_sdl_pads(uint64_t *buttons, int32_t stick[4]) {
    (void)buttons; (void)stick; return InterlockedCompareExchange(&sdl_count, 0, 0);
}
static void binds_load(void) {}
static SRWLOCK pad_bind_lock = SRWLOCK_INIT;
static int pad_bind[HOS_SW_N][2];
static uint64_t oc_consumed_pads;
'''

MAIN = r'''
static uint64_t read_pad(int32_t stick[4]) {
    uint64_t b = 0;
    memset(stick, 0, 4 * sizeof *stick);
    pads_read(&b, stick);
    CHECK(pad_raw_game == (uint64_t)(uint32_t)pad_raw_now);
    return b;
}
static int await_button(int down, int ms) {
    const int64_t until = hos_now_ns() + (int64_t)ms * 1000000;
    do {
        int32_t stick[4];
        const uint64_t b = read_pad(stick);
        if (!!(b & (1ULL << HOS_SW_B)) == down) {
            if (down) CHECK(stick[0] == 20000);
            return 1;
        }
        Sleep(3);
    } while (hos_now_ns() < until);
    return 0;
}
static int await_driver(HANDLE event, int ms) {
    const int64_t until = hos_now_ns() + (int64_t)ms * 1000000;
    do {
        int32_t stick[4]; read_pad(stick);
        if (WaitForSingleObject(event, 1) == WAIT_OBJECT_0) return 1;
    } while (hos_now_ns() < until);
    return 0;
}
int main(void) {
    game_thread = GetCurrentThreadId();
    driver_entered = CreateEventA(NULL, TRUE, FALSE, NULL);
    driver_release = CreateEventA(NULL, TRUE, FALSE, NULL);
    empty_entered = CreateEventA(NULL, TRUE, FALSE, NULL);
    empty_release = CreateEventA(NULL, TRUE, FALSE, NULL);
    CHECK(driver_entered && driver_release && empty_entered && empty_release);
    for (int i = 0; i < HOS_SW_N; ++i) pad_bind[i][0] = pad_default[i], pad_bind[i][1] = -1;
    int32_t stick[4];
    CHECK(read_pad(stick) == 0 && start_calls == 1 && !xinput_started);
    Sleep(3); CHECK(read_pad(stick) == 0 && start_calls == 1);
    AcquireSRWLockExclusive(&xinput_lock); xinput_start_retry = 0; ReleaseSRWLockExclusive(&xinput_lock);
    const int64_t until = hos_now_ns() + 1300000000LL;
    while (hos_now_ns() < until) { CHECK(read_pad(stick) == 0); Sleep(3); }
    CHECK(start_calls == 2 && on_game == 0 && elsewhere >= 8);
    InterlockedExchange(&connected, 1);
    CHECK(await_button(1, 2000));

    /* A poll in the driver must not hold the snapshot lock or republish after SDL takes over. */
    InterlockedExchange(&block_driver, 1);
    CHECK(WaitForSingleObject(driver_entered, 2000) == WAIT_OBJECT_0);
    InterlockedExchange(&sdl_count, 1);
    Sleep(3); CHECK(read_pad(stick) == 0 && stick[0] == 0);
    InterlockedExchange(&block_driver, 0); SetEvent(driver_release);
    Sleep(150); CHECK(read_pad(stick) == 0 && hos_xinput_pads() == 0);
    InterlockedExchange(&sdl_count, 0);
    CHECK(await_button(1, 2000));

    /* A stuck driver must not leave movement/buttons held indefinitely. */
    ResetEvent(driver_entered); ResetEvent(driver_release);
    InterlockedExchange(&block_driver, 1);
    CHECK(WaitForSingleObject(driver_entered, 2000) == WAIT_OBJECT_0);
    Sleep(150); CHECK(read_pad(stick) == 0 && stick[0] == 0);
    InterlockedExchange(&block_driver, 0); SetEvent(driver_release);
    CHECK(await_button(1, 2000));

    /* Slot 0 is sampled BEFORE a later empty slot stalls. Keep requesting input
       throughout the stall so only sample age (not request expiry) rejects it. */
    InterlockedExchange(&block_empty, 1);
    CHECK(await_driver(empty_entered, 2000));
    const int64_t stale_until = hos_now_ns() + 150000000LL;
    while (hos_now_ns() < stale_until) { read_pad(stick); Sleep(2); }
    CHECK(read_pad(stick) == 0 && stick[0] == 0);
    InterlockedExchange(&held, 0);
    ResetEvent(driver_entered); ResetEvent(driver_release);
    InterlockedExchange(&block_driver, 1);
    InterlockedExchange(&block_empty, 0); SetEvent(empty_release);
    CHECK(await_driver(driver_entered, 2000)); /* next sample not acquired yet */
    CHECK(read_pad(stick) == 0 && stick[0] == 0);
    InterlockedExchange(&block_driver, 0); SetEvent(driver_release);
    CHECK(await_button(0, 2000));
    InterlockedExchange(&held, 1);
    CHECK(await_button(1, 2000));
    InterlockedExchange(&connected, 0);
    CHECK(await_button(0, 1000));
    CHECK(on_game == 0);
    puts("PASS: slow XInput stays off game thread; hot-plug, unplug, SDL takeover, expiry and start retry");
    return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    args = p.parse_args()
    if sys.platform != "win32":
        print("SKIP: Windows XInput regression uses real Win32 thread/lock primitives")
        return
    hid = (ROOT / "host/nn_hid.c").read_text(encoding="utf-8")
    api = (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8")
    state = hid[hid.index("static volatile LONG pad_raw_now;"):hid.index("uint32_t hos_pad_raw(")]
    xinput = hid[hid.index("static volatile int xinput_pads_now;"):hid.index("static void pads_read(")]
    code = "\n".join((
        block(api, "enum { HOS_SW_A") + ";", block(api, "enum { HOS_PAD_SOUTH") + ";",
        PRELUDE,
        block(hid, "static const signed char pad_default[HOS_SW_N] =") + ";",
        block(hid, "static void stick_max("), block(hid, "static uint64_t bound_pad_buttons("), state,
        block(hid, "void hos_filter_stick("), xinput, block(hid, "static void pads_read("), MAIN))
    with tempfile.TemporaryDirectory(prefix="reborn-xinput-") as folder:
        src, exe = Path(folder) / "t.c", Path(folder) / "t.exe"
        src.write_text(code, encoding="utf-8")
        subprocess.run([args.cc, "-std=c11", "-include", str(ROOT / "gpu/vk/compat/ocarina_reborn_env.h"),
                        "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-unused-variable",
                        "-o", str(exe), str(src)], check=True)
        subprocess.run([str(exe)], check=True, timeout=15)


if __name__ == "__main__":
    main()
