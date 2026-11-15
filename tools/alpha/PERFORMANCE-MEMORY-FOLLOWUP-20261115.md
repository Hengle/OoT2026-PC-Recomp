# Completed-target memory follow-up, 2026-11-15

Private follow-up to `348200b`; public version remains 1.0.9. Do not publish this test installer as a release.

## Evidence from the new user run

Own-PC debug package `OcarinaReborn-Debug-TEST-OFFLINE-20261115-065628.zip`, run `20261115-065210-4f5300fc`, description "stadt test": Ryzen 7 9800X3D, Radeon RX 7900 XTX 24 GB, 32 GB system RAM. The 206-second run ended normally. The included performance report covers 145.31 seconds and 8,249 frames: 56.77 FPS, worst frame 636.5 ms, 22 frames over 50 ms and five over 100 ms. Frame generation was already off. No device-lost, host-OOM or GPU-hang result in this run.

The larger hitches coincide with texture upload activity and low Windows commit headroom. Pipeline waits are zero at the recorded spikes. A missing shader cache is not supported by these measurements. Process private commit peaked at approximately 32.33 GiB; physical working set peaked at approximately 17.50 GiB. These are different quantities: the 32.33 GiB figure is not resident RAM use. Recorded VRAM peaked around 14.05 GiB. This does not prove one exclusive cause for every hitch.

The completed-render-target reuse cache sometimes retained about 1,010 MiB, above its normal 256 MiB limit and the lower pressure limits. Its old admission path accepted everything; subsequent count-limited trimming could lag behind arrivals.

The user's settings included FSR 4 Native AA at 100% resolution and Ultra texture detail. FSR 4.1.2 actually initialized on this GPU. Native AA does not reduce the internal render resolution.

## Implementation

- Enforce the completed-target byte limit at admission. Retain the newest useful target shapes by evicting the oldest completed entries until the arriving image fits. Reject an individually oversized image. Bound tiny-image metadata to 512 entries.
- When the memory cap falls, trim to that cap in the current pass; retain the count budget for optional age-based eviction. Driver calls happen outside the mutex used by parallel lookups.
- Preserve GPU-completion gates, live-texture protection, the compaction exclusion and image/view ownership. This patch does not free images still in flight. Individual driver frees may still exceed a desired frame-time budget.
- **Lower memory** caps this completed-target cache at 64 MiB and the initial unused image-pool reservation at 256 MiB. On the tested GPU this changes startup preallocation from 24 to four 64 MiB blocks. Pools can grow when necessary. Explicit `RX_VK_IMAGE_PREALLOC` remains authoritative. **Balanced** retains its previous startup reservation.
- Update English/German launcher help. Smaller caches can cause more loading when revisiting areas; this is not a hard cap on all process RAM or VRAM.
- Keep generated/staged engine sources consistent with the checked-in implementation. Fresh upgrades and repeated staging are checked.

## Validation

- Renderer build successful, four compiler jobs. Game executable unchanged.
- 19 distinct targeted tests passed across `test_streaming`, `test_target_cache`, `test_streaming_balance`, `test_resource_memory`, `test_memory_guard` and `test_capture_pacing`.
- Native cache tests execute production functions: repeated 2,000-image bursts, immediate pressure-cap reductions, reuse order, age expiry, oversized entries, metadata limits, accounting, no double-free, and driver frees outside the mutex. Existing native completion/dependency and upload-worker lifetime tests also pass.
- Launcher/staging Python compilation and fresh/repeated staging passed.
- All 250 shader-stamp input files match the installed engine after the existing newline normalization: `1cd445ea9d3fb649`. No shader-cache invalidation, cache deletion, or complete game rebuild is required by this patch.
- Private installer fixture: all 12 payload hashes, complete backups, rejection of incompatible game builds/missing launcher/repeated installation, rollback refusal after unrelated newer changes, exact restore, and preservation of saves/settings/private voices/caches passed. Tests did not install into the live game.

## Runtime scope

Tests use a private game copy, copied saves and a read-only asset junction. Market_Child, four camera sweeps to warm up and another four to measure. Requested settings: FSR 4 upscaling, 67% render resolution, High textures, 60 FPS cap, Strong RAM guard, same settings for each comparison. Hardware is the user's AMD system; no real low-end or NVIDIA hardware is available here.

The comparative runs are headless: although the options select frame generation 2x, the renderer disables interpolation offscreen. Requested output is 1440p, control reports a 1920x1080 window, and captured screenshots are 1280x720. Therefore these are renderer comparisons, not verified 1440p/4K presentation or frame-generation benchmarks. Windows memory pressure, driver state and camera phase vary between runs. Short single-route results cannot establish removal of the longer exploration hitches.

| Measured headless run | Base FPS | Worst frame | Frames >50 ms | Peak private commit | Peak VRAM |
| --- | ---: | ---: | ---: | ---: | ---: |
| Previous renderer / Balanced | 59.82 | 44.23 ms | 0 | 30.31 GiB | 13.24 GiB |
| Final patch / Balanced | 59.76 | 47.41 ms | 0 | 28.96 GiB | 11.30 GiB |
| Final patch / Lower memory | 59.81 | 60.46 ms | 1 | 29.73 GiB | 12.67 GiB |
| Previous renderer / Balanced, repeat | 59.81 | 47.16 ms | 0 | 31.41 GiB | 14.23 GiB |

The final Balanced run used 1.94–2.93 GiB less peak VRAM and 1.35–2.45 GiB less private commit than the two previous-renderer runs. This is a short observation under varying system conditions, not a guaranteed saving for other scenes or PCs. The FPS cap prevents an uncapped throughput claim. Lower memory did not beat Balanced's active-game memory peak in this scene, despite its verified smaller startup reservation. Balanced remains the own-PC recommendation.

The earlier reject-on-full prototype was superseded by the final oldest-entry replacement implementation. Its measurements remain in the artifact directory for traceability and are excluded from the table.

Separate windowed smoke test (`final-window-fg2`): FSR 4.1.2 reported 1707x960 input to 2560x1440 output, a 2560x1421 window swapchain, and active 2x frame interpolation. The warmed measurement covered 1,139 base frames at 59.93 FPS; worst frame 37.55 ms, zero over 50 ms, peak private commit 28.53 GiB and peak VRAM 11.44 GiB. Display-thread logs reported approximately 600 shown frames per five seconds with predominantly 7–9 ms spacing. The screenshot showed the scene and HUD without an obvious new rendering error. No crash occurred; the private game quit normally.

This smoke test has no paired windowed baseline and is not evidence of a 4K improvement. Loading/teleport before the measured interval still produced 523 ms and 245 ms frames. Those pauses remain unresolved; a longer exploration and area-change route is still required. Existing cached shader-failure counts also occur with the preceding renderer; they are not claimed fixed here. The patch is a bounded-memory correction, not a promise to eliminate all stutters.

## Private delivery

Artifact directory: workspace `work/performance-memory-20261115`, including benchmark logs, timelines, metrics, images, shader-stamp verification, installer manifest and fixture results.

- Renderer SHA-256: `931713e1abc3492955f962e84535b18dc47c63bdb5af810d5100a47201be7b40`.
- Installer: `Ocarina-Reborn-Test-Patch-Memory-20261115.exe`, private version `1.0.9-test-memory-cache-20261115`.
- Installer SHA-256: `aef72112f41c902ee0beecafddb2a86a6ac459bee268c466a0ed42b866360e38`.
- Installer backs up the exact replaced files and includes a guarded restore. It does not silently close the user's running game or install itself.

Suggested own-PC starting settings: FSR 4 upscaling / 67% Quality, High texture detail, 60 FPS base cap, frame generation 2x, Balanced streaming, Auto texture memory, Strong 3 GB RAM guard. Keep original view/grass/shadow distances and Low-spec mode off. Lower memory remains available for tighter memory budgets, but lower active-game peaks or fewer hitches are not guaranteed.
