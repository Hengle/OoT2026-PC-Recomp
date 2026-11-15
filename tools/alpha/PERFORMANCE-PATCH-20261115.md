# Private performance test patch, 2026-11-15

Based on 72d7876. Not a public release; launcher version remains 1.0.9.

## Changes

- Captures remember their mirrored-page recording dependencies. A known recording can be waited on without waiting for the end of an unrelated/stopped submission. Direct-memory writes, later in-place reads, alternate replay modes and missing recording mappings retain the existing whole-submission path. No waiting for a mapping to be published on the replay thread; no second 250 ms wait after a timeout. `OCR_CAPTURE_PART_WAIT=0` restores the old capture wait path.
- Completed texture-resource retirement is spread across frames (up to 64 resources or 1.5 ms before deferring more). Each resource's GPU completion check stays in place. Low host-memory reserves, GPU pressure, more than 1,024 queued resources or over 256 MiB of tracked pending resources bypass deferral. Individual driver frees can exceed 1.5 ms; this is not a hard frame-time guarantee.
- Launcher **Settings > Memory > Streaming and memory**: Legacy, Balanced (default), Lower memory. Auto texture-cache ceilings use approximately 20% or 12.5% of system RAM, rounded down to 256 MiB, within existing hardware/preset limits. Explicit texture-memory settings remain authoritative. This does not reduce texture resolution. A smaller cache can require more reloading when revisiting areas.
- Skip the recently-used-texture scan when there is neither a pressure hold nor host-memory pressure.
- Private installer also includes the preceding 72d7876 GPU-watchdog diagnosis fix, which had not yet been installed in the launcher.

## Validation

- Renderer build: success, 4 compiler jobs, Vulkan/FSR enabled.
- Native recording-wait tests: mirrored dependency, direct-write dependency, later in-place read, missing mapping, alternate replay, bounded timeout and disabled switch.
- Native cleanup tests execute the production loop: GPU-in-flight resources survive, completed resources make progress, pressure drains immediately, backlog limits override deferral, pooled targets retain the reuse path.
- Memory/resource tests (8), stability tests (7), shader-stamp/cache tests (10), new capture/streaming tests (5), production shader-stamp-input test (1): passed.
- Fresh staging patches applied to HEAD reproduce the checked-in renderer; repeated application is unchanged.
- All 250 shader-stamp input files match the installed engine after the existing newline normalization. No shader ABI bump or cache deletion.
- Real launcher dropdown/callback tested with an isolated hidden profile at 1100x620 and 1440x810 in German and English.
- Installer: all 11 payload hashes, exact backups, rejection of wrong game build/missing launcher/repeated installation, rollback refusal after a newer file, exact restore including newly added files, and preservation of saves/settings/private voices/caches verified in a fixture. Live installation untouched by these tests.

## Runtime measurements and limits

Private copied save and game executable, read-only asset junction, copied caches. Market_Child, six camera sweeps to warm up and another six to measure. Frame generation off. AMD RX 7900 XTX and Ryzen 7 9800X3D; no real NVIDIA/low-end GPU validation. Headless screenshots are 1280x720 despite the requested high-profile output resolution, so these are not a verified 1440p/4K benchmark.

| Comparison | Old | Patched |
| --- | ---: | ---: |
| Warm-cache high-profile actual FPS | 65.96 | 67.15 |
| Worst measured frame, high profile | 42.56 ms | 52.30 ms |
| CPU-budget profile actual FPS | 57.90 | 58.47 |
| Renderer time/frame, CPU-budget profile | 11.24 ms | 10.26 ms |
| Worst measured frame, CPU-budget profile | 49.43 ms | 49.85 ms |

CPU-budget profile uses the first eight logical processors, 60 FPS cap, lower scene detail, and Lower memory in the patched run. It is not a simulation of a specific low-end PC. Windows free memory, camera phase and cache/driver state vary. These short runs show no large FPS improvement and do not establish elimination of the reported 200–870 ms exploration hitches or the late-session GPU hang. No crash occurred in the comparison runs. Peak VRAM/process memory was not materially reduced in the short CPU-budget scene; a cache ceiling cannot free currently needed or GPU-only protected images.

The patch needs Pascal's longer route through the well and repeated area changes before public release. Keep Frame Generation unchanged for an initial apples-to-apples user comparison; use a separate FG-off run to isolate the old GPU hang if it recurs. Ctrl+F8 on a hitch, close the game, export a new debug package.

Artifacts are in the sibling workspace `work/performance-20261115`: benchmark logs/timelines, per-run metrics, build log, UI verification, installer manifest and installer verification. Private installer SHA-256: `506002eb30d22fc05419c3f32c0a4e01da22969a1291708efd77678f132a0d6a`.
