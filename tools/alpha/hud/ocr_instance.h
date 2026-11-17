/* One Windows game or shader-preparation process per game folder. The OS releases
   the handle on normal exit and on a crash; a leftover file does not hold a lock.
   Acquire before opening logs, caches or saves. Crash helpers bypass this entry. */
#ifndef OCR_INSTANCE_H
#define OCR_INSTANCE_H
#ifdef _WIN32
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

/* Reserved startup results, also recognized by launcher/diagnostics.py. */
#define OCR_INSTANCE_BUSY 73
#define OCR_INSTANCE_ERROR 74

static int ocr_instance_acquire(const wchar_t *exe, HANDLE *held, DWORD *error) {
    wchar_t path[32768];
    const size_t n = wcslen(exe);
    size_t dir = n;
    while (dir && exe[dir - 1] != L'\\' && exe[dir - 1] != L'/') --dir;
    const wchar_t suffix[] = L".ocarina-reborn.instance.lock";
    *held = INVALID_HANDLE_VALUE;
    if (!dir || dir + sizeof suffix / sizeof *suffix > sizeof path / sizeof *path) {
        *error = ERROR_BAD_PATHNAME;
        return OCR_INSTANCE_ERROR;
    }
    memcpy(path, exe, dir * sizeof *path);
    memcpy(path + dir, suffix, sizeof suffix);
    /* Not inheritable, and never deleted: deleting a lock file introduces a race.
       Windows resolves case, junctions and path aliases to the same locked file. */
    *held = CreateFileW(path, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ, NULL,
                       OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    *error = *held == INVALID_HANDLE_VALUE ? GetLastError() : ERROR_SUCCESS;
    if (*held != INVALID_HANDLE_VALUE) return 0;
    return *error == ERROR_SHARING_VIOLATION || *error == ERROR_LOCK_VIOLATION
               ? OCR_INSTANCE_BUSY : OCR_INSTANCE_ERROR;
}

static void ocr_instance_wait_restart(void) {
    /* Restart now spawns its successor before ExitProcess. Wait before taking
       the folder lock, not merely before rotating the old run's log. */
    const char *of = getenv("HOS_RESTART_OF");
    if (of && *of) {
        char *end = NULL;
        unsigned long pid = strtoul(of, &end, 10);
        if (pid && end && !*end && pid != GetCurrentProcessId()) {
            HANDLE before = OpenProcess(SYNCHRONIZE, FALSE, (DWORD)pid);
            if (before) {
                WaitForSingleObject(before, 10000);
                CloseHandle(before);
            }
        }
        SetEnvironmentVariableA("HOS_RESTART_OF", NULL);
        _putenv("HOS_RESTART_OF=");
    }
}

static int ocr_instance_enter(int argc, char **argv) {
    static HANDLE held = INVALID_HANDLE_VALUE; /* retained until process exit */
    wchar_t exe[32768];
    ocr_instance_wait_restart();
    DWORD n = GetModuleFileNameW(NULL, exe, sizeof exe / sizeof *exe);
    DWORD error = n ? ERROR_FILENAME_EXCED_RANGE : GetLastError();
    const int result = n && n < sizeof exe / sizeof *exe
                           ? ocr_instance_acquire(exe, &held, &error) : OCR_INSTANCE_ERROR;
    if (!result) return 0;
    const char *message = result == OCR_INSTANCE_BUSY
        ? "Ocarina Reborn or shader preparation is already running in this game folder. Close it or wait for it to finish, then try again. Your shader caches have not been changed."
        : "Ocarina Reborn could not reserve this game folder. Check that the folder is writable and accessible, then try again.";
    fprintf(stderr, "[OcarinaReborn/START] %s (Windows error %lu)\n", message, (unsigned long)error);
    const char *headless = getenv("HOS_HEADLESS");
    int quiet = headless && *headless && strcmp(headless, "0");
    for (int i = 1; i < argc; ++i)
        if (!strcmp(argv[i], "--prepare-shaders")) quiet = 1;
    if (quiet) {
        printf("@@error %s\n", message);
        fflush(stdout);
    } else {
        MessageBoxW(NULL, result == OCR_INSTANCE_BUSY
            ? L"Ocarina Reborn or shader preparation is already running in this game folder.\n\nClose it or wait for it to finish, then try again. Your shader caches have not been changed."
            : L"Ocarina Reborn could not reserve this game folder.\n\nCheck that the folder is writable and accessible, then try again.",
            L"Ocarina Reborn", MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
    }
    return result;
}
#endif
#endif
