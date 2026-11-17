**IMPORTANT — Ocarina Reborn v1.1.4: PLEASE READ THE PATCH NOTES**

**🚀 Engine & Performance Update**

**This update includes the new engine. Let the launcher update/rebuild the game and prepare shaders before playing. The first start can take longer while the new shaders and pipelines are prepared. Keep your existing caches; do not delete them manually.**

**⚡ Performance & memory**
- Updated the engine to **v2.3.2**, with further CPU, renderer and memory improvements.
- Improved CPU-thread coordination to avoid missed wake-ups and unnecessary waiting.
- Rendering work takes priority over background shader preparation, helping background work interfere less with gameplay.
- Improved reuse and cleanup of graphics memory, with fewer repeated allocations and safer release of resources still used by the GPU.
- Added recovery headroom for memory-allocation failures under Windows memory pressure. This reduces one crash risk; it does not replace having enough RAM and page-file space.
- Better cleanup of temporary shader resources, including when shader preparation fails.

**🖥️ Rendering & Frame Generation**
- Built-in Frame Generation now limits extra frames to what your display can show and drops late generated frames instead of holding up the next real frame.
- Improved HDR/upscaler handling, graphics-data synchronization and shader translation, including Intel compatibility fixes.
- Improved ultrawide menus and loading transitions.
- Optional **CRT filters** in F1 for a retro display style. Off by default; Native HDR bypasses them.
- The engine now supports **Intel XeSS / XeSS Native AA** on compatible Windows systems with Intel's runtime installed. It is optional and not bundled with this installer.

**💾 Saves & stability**
- Automatic save backups are kept outside the game folder. The newest backup can be restored automatically when the save folder is empty; existing saves are not overwritten.
- Improved audio-device recovery and crash reporting.
- Protection against two game or shader-preparation processes using the same game folder and conflicting over the cache.
- Debug reports now distinguish failed starts from older sessions, so old FPS measurements are not blamed on a new launch.

**🎨 Classic UI — optional**
- Open **Launcher → Mods → Choose Classic UI**.
- Choose **Switch, Xbox or PlayStation button icons**, including swapped-button variants, **four HUD styles** and **three title-screen logos**.
- Click **Install and enable**. Only your chosen version is downloaded — around **80 MB**. After installation, the on/off switch also works offline.
- Changes apply at the next game start. Classic UI itself does not require a game rebuild.
- Classic UI by **kuledawg**, downloaded directly from [GameBanana](https://gamebanana.com/mods/737280). Other HUD mods may conflict. Installation and switching are tested; in-game visual testing is still ongoing.

**🛠️ Launcher**
- **Open launcher** returns to the launcher after a game build/update instead of immediately starting the game.
- The installer's final option now clearly says **Launch Ocarina Reborn Launcher**.

**ℹ️ Updating**
- Restart the launcher and click **Update**. Install over your existing version, then let the launcher update the game.
- **No uninstall or game-file reimport is needed. Saves and settings stay.**
- If you already installed the earlier, withdrawn **1.1.4**, download the installer again from the website. The version number is unchanged, so that launcher will not offer it automatically.
- Performance depends on your hardware and the scene. This update does not promise to eliminate every stutter or graphics issue.

**📊 Help us improve**
- If you notice stutters, press **Ctrl+F8**, close the game and create a fresh **Debug Package**. After a crash, reopen the launcher to create it.
- Send it in **#post-your-logs-here** with the area and what happened. Reports from lower-end PCs are especially helpful.

Thanks for testing! 💙

[Ocarina Reborn](https://ocarina-pc-native-build.github.io/)
