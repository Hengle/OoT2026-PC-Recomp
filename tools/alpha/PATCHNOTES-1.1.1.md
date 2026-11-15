**Ocarina Reborn v1.1.1 — Shader, Memory & Settings Update**

**⚡ Shader preparation**
- First-time preparation now focuses on recorded pipelines instead of compiling tens of thousands of speculative pipeline variants.
- Temporary pipelines are released during preparation, and shader worker counts adapt to available RAM and Windows commit headroom.
- Preparation reuses existing caches. New effects can still cause brief stutters on first use; preparation time depends on your CPU and driver.
- Fixed misleading shader counts and false stall warnings while compute pipelines are still being prepared.

**🛠️ Performance and stability**
- New **Streaming and memory** modes: **Balanced** and **Lower memory**. Lower memory reduces cache sizes and startup reservations without changing texture quality.
- Improved cleanup of completed rendering resources and limited retained render targets to reduce memory growth and long cleanup pauses.
- Improved texture-budget behavior during loading.
- PCs with up to 20 GB RAM and native mesh shaders keep loading programs as needed, even if an earlier slow-loading session requested loading every recorded program at startup.
- Better reports for low available RAM, GPU hangs and graphics-startup failures. A failed graphics start is detected even when the game exits with code 0.

**🎨 Upscaling and interface**
- Added **AMD FSR 3.1.6** as a separate upscaler in the launcher and F1 menu. The required AMD runtime is included; existing FSR options remain available.
- The F1 menu now uses the launcher's card design and shared custom interface colours.
- Added a startup reminder explaining how to report issues, with **Don't show again**.

**⚙️ Settings**
- New **Reset all settings** button: resets graphics, audio, controls, difficulty, cheats, colours and launcher preferences. A settings backup is created first; saves, installed files and shader caches stay.
- **RAM guard** now has **Off**, and **Largest textures** has **Off (no dimension limit)**. Normal texture-memory and GPU limits still apply.
- The separate **Reset graphics** button remains available.

**ℹ️ Updating**
- Restart the launcher, select **Update**, and install over your existing version. Then let the launcher update the game components.
- **No complete reinstall or game-file reimport is needed.** Saves, settings and private voice files stay. Updating does not press the new reset button for you.
- Existing compatible shader caches are kept. A different graphics driver or older renderer can still require preparation.

**📊 Help us improve**
- If you notice stutters or crashes, press **Ctrl+F8** when the problem happens, then close the game and create a fresh **Debug Package**.
- Send it in **#post-your-logs-here** on Discord with the area and what happened. Reports from lower-end PCs are especially helpful.

Thanks for testing! 💙

[Ocarina Reborn](https://ocarina-pc-native-build.github.io/)
