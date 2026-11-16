**Ocarina Reborn v1.1.3 — Performance Preview**

**⚡ Memory and performance**
- Reduced unnecessary memory retention and improved shared RAM/VRAM budgets.
- More efficient CPU calculations, graphics processing and renderer builds.
- Shader modules can be released after their recorded pipelines have been prepared.
- New **Low-end 60 FPS** preset to make settings easier on weaker PCs. 60 FPS is a target, not a guarantee.

**🛠️ Fixes**
- Fixed one cause of continuously spinning cameras after input stops.
- Corrected shader calculations and the ordering of graphics-data updates.
- Improved recovery of missing effects after graphics-driver errors. Intel-specific changes still need more tester feedback.
- Asynchronous threaded rendering remains disabled by default while visual compatibility is being tested.

**📊 What to expect**
- In a short matched Market test, memory use fell from about **10.6 GB to 8.4 GB**. FPS rose only slightly, from about **69 to 71**.
- This is a performance preview. Results depend on your PC, settings and location; stutters and visual issues are not all resolved.

**ℹ️ Updating**
- Restart the launcher, select **Update**, and install over your existing version. Let the launcher update the game components afterwards.
- **No complete reinstall or game-file reimport is needed.** Saves, settings and private voice imports stay.
- Changed shader calculations can require shader preparation on the first start. Compatible cache entries are kept.

**💬 Help us improve**
- When you notice stutters, press **Ctrl+F8**, then close the game and create a fresh **Debug Package**. After a crash, reopen the launcher to create the package.
- Send it in **#post-your-logs-here** with the area and what happened. Reports from lower-end PCs are especially helpful.

Thanks for testing! 💙

[Ocarina Reborn](https://ocarina-pc-native-build.github.io/)
