**IMPORTANT — Ocarina Reborn v1.1.5: PLEASE READ THE PATCH NOTES**

**Ocarina Reborn v1.1.5 — Performance & Gameplay Update**

**⚙️ Performance and memory**
- Improved reuse and cleanup of graphics buffers to reduce repeated allocations and time spent waiting during gameplay.
- Unused buffers are released more aggressively when RAM or Windows memory capacity runs low. Fixed a case where small unused buffers were kept for too long.
- Frequently used game code now receives the intended compiler optimizations in player builds.
- Improved texture-upload scheduling and reduced unnecessary renderer waiting.
- Slow controller-driver checks no longer block the game thread. Stale input is discarded after a stalled check.
- More detailed memory and stutter information in Debug Packages.

These changes target specific causes of stutters and memory pressure. Results vary by PC and area; some loading stutters can still happen.

**🎵 Choose your ocarina**
- Choose **Original**, **Fairy Ocarina** or **Ocarina of Time** in **Launcher Settings → Gameplay** or **F1 → Gameplay**.
- Both instruments work with **child and adult Link**, once you own an ocarina.
- Put the instrument away and close F1 to apply a change. **Original** restores the normal selection.

**Unlimited amiibo**
- New optional toggle in both Gameplay menus to remove the daily scan limit for your own amiibo files.
- **Off by default.** Supported-figure, location and story requirements still apply. Turning it off restores the normal limit.

**🛠️ Build fixes**
- Builds can recover from incomplete or corrupted cached compilation metadata.
- Public builds ignore leftover private-test profiling markers, preventing unintended slow recording builds.
- Fixed initial mouse handling on the build screen.

**ℹ️ Updating**
- Restart the launcher and use **Update**, or install the new setup over your current installation.
- Let the launcher update the game once. The first start may prepare shaders; **do not delete working shader caches**.
- **No uninstall or game-file reimport needed. Saves and settings stay.**

If you notice stutters, press **Ctrl+F8** when they happen, then close the game and create a fresh **Debug Package**. After a crash, reopen the launcher to create it.
Send it in **#post-your-logs-here** with the area and what happened. Reports from lower-end PCs are especially helpful.

Thanks for testing and supporting Ocarina Reborn! 💙
