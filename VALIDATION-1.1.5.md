# Ocarina Reborn 1.1.5 validation

Validated November 22, 2026 on Windows x64. This packages the tested private 1.1.4-22 gameplay/engine code with public release metadata.

- All 65 host C translation units compiled; the Vulkan renderer linked. The complete local game executable also built successfully. Game data and generated game code are excluded from distribution.
- Native regression coverage includes ocarina ownership/actor ABI and deferred switching, amiibo cooldown scope, capture-pool physical RAM/commit limits, synchronization table growth, stalled controller polling, corrupted build metadata and settings persistence.
- Launcher suite: 254/255 initially passed. The remaining FSR test lacked VULKAN_HEADERS; after configuring the installed SDK, all four affected FSR checks passed.
- A 12.6-minute isolated gameplay check exercised both ocarinas with child and adult Link. Song recognition, deferred switching and Original restoration worked.
- Using the same amiibo file, a repeated scan was blocked with the option off, two more rewards were allowed with it on, and switching off restored the limit.
- The isolated test exited normally; 18 original save, settings and binary files remained unchanged by hash.

This was not a controlled performance A/B benchmark. Long-session memory use and lower-end hardware still require feedback. No universal FPS uplift, complete stutter fix or memory-leak elimination is claimed.

Release packaging additionally checks source/payload hashes, distribution exclusions, the public profiling guard and launcher update discovery. Corresponding source and installer checksums accompany the release.
