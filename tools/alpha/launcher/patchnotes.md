**Ocarina Reborn v1.1.6 — Texture Transfer Fix**

**Performance**
- Texture reads and writes now release their virtual CPU core while waiting for the graphics backend, allowing other game threads to continue.
- Applies to both graphics backends when virtual-core scheduling is active.

**Updating**
- Update the launcher, then let it update the game once. Saves and settings stay.
- Keep existing shader caches. No uninstall or game-file reimport is needed.

**Testing status**
- This update has not undergone regression tests or gameplay testing. No FPS improvement has been measured for this change.
- If you notice a problem, press Ctrl+F8, close the game and send a fresh Debug Package in #post-your-logs-here with the area and what happened.
