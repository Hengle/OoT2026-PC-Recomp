**Ocarina Reborn v1.1.2 — Memory, Portrait & HUD Update**

**💎 Animated rupee counter**
- **Classic counters (N64)** now uses a small animated rainbow crystal.
- The rupee number rolls quickly through the values when you gain or spend rupees, instead of jumping straight to the new total.
- Loading a save shows the correct amount immediately.

**📱 9:16 portrait support**
- Added portrait resolutions in the **launcher and F1 menu**: 720×1280, 1080×1920, 1440×2560 and 2160×3840.
- The camera supports the portrait view. The HUD keeps its proportions in a centered area; this is not a fully rearranged portrait HUD.
- **Requested by a supporter on Buy Me a Coffee.** Thank you for the suggestion!

**⚡ Memory improvements**
- Fixed cleanup of old, overwritten rendering targets that could remain allocated even after their contents were no longer needed.
- This reduces unnecessary RAM and VRAM usage without lowering texture quality. The improvement depends on the scene and hardware.

**🔊 Audio and diagnostics**
- Fixed audio commands being processed out of order when the audio queue cannot allocate more memory.
- Debug Packages now include clearer audio status information to help investigate silent audio and music that keeps playing. No audio recordings are collected.
- This addresses one possible failure path; the remaining reports of stuck battle music still need testing.

**🛠️ Launcher and F1 menu**
- Patch notes now open in a proper launcher page with sections, page buttons, mouse-wheel and controller navigation.
- After an update, the notes appear once automatically and remain available offline.
- Improved how launcher settings are saved and fixed an update-news timing issue.
- Fixed the distorted ocarina image in the F1 menu header.

**ℹ️ Updating**
- Restart the launcher, select **Update**, and install over your existing version. Then let the launcher update the game components.
- **No complete reinstall or game-file reimport is needed.** Saves, settings and compatible shader caches are kept.

**📊 Help us improve**
- If you notice stutters or crashes, press **Ctrl+F8** when the problem happens, then close the game and create a fresh **Debug Package**.
- Send it in **#post-your-logs-here** on Discord with the area and what happened. Reports from lower-end PCs are especially helpful.

Thanks for testing! 💙

[Ocarina Reborn](https://ocarina-pc-native-build.github.io/)
