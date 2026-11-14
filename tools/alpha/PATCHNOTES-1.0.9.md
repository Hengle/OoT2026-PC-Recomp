**Ocarina Reborn v1.0.9 — Performance & Loading Update**

**⚙️ Performance and memory**
- Reused background workers for texture uploads to reduce CPU overhead.
- Improved reuse of temporary render targets, reducing unnecessary image allocations.
- Smaller temporary RAM buffers when processing large textures, including on CPUs with fewer available threads.
- Adjusted texture uploads to avoid certain costly memory operations that caused loading stutters.
- Unused graphics buffers are released earlier when system memory is tight, with smoother memory-budget adjustments.
- Improved handling of captured texture data while uploads are processed in smaller chunks.

These changes target smoother loading and lower CPU/RAM overhead on both modest and powerful PCs. Results depend on your hardware and the scene; broader hardware testing is still ongoing.

**🛠️ Fixes and launcher**
- Fixed game builds stopping when an optional performance-profile file was missing. The build now continues without that profile.
- Added a **Navi on/off** button in the launcher header. Your choice is remembered after restarting.

**ℹ️ Updating**
- Restart the launcher, choose **Update**, and install over your existing version. Then let the launcher update the game components.
- **No complete reinstall or game-file reimport is needed.** Your saves, settings and local voice mods stay. Existing caches are kept; shader preparation may still be needed depending on your previous build.

**📊 Help us improve**
- If you notice stutters or crashes, press **Ctrl+F8** when the problem happens, then close the game and create a fresh **Debug Package**.
- Send it in **#post-your-logs-here**, together with the area and what happened. Reports from lower-end PCs are especially helpful.

Thanks for testing and sharing your logs! 💙

[Ocarina Reborn](https://ocarina-pc-native-build.github.io/)
