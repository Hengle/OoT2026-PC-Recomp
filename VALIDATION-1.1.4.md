# Full v1.1.4 validation

This replaces the withdrawn first v1.1.4 package. The shipped engine is
v2.3.2-reborn; the previous package used the older v2.2 tree.

Verified on Windows:

- 227 launcher and Ocarina Reborn tests passed.
- All 63 Windows host compilation units compiled.
- The Vulkan renderer compiled and linked successfully.
- Native tests passed for FSR uniform ownership (both coherent and noncoherent
  memory), FSR image retirement, render-target reuse, readback rules, and save
  backup/restore. These use synthetic resources and temporary save folders.
- Tracked Python source byte-compilation passed after the source import was
  committed.

The complete imported engine suite is **not all green**. Its initial run had
575 passes, 87 failures and 47 skips. Follow-up checks resolved five of those
failures: tracked-file byte compilation and the FSR ownership/retirement,
target-image reuse and readback fixtures. The remaining failures include
upstream launcher/workflow paths that this distribution does not ship, missing
.NET SDK fixtures, Linux assumptions on Windows, and fixtures/source assertions
that do not account for Reborn-specific instrumentation, options and branding.
They remain visible rather than being removed or marked as passing. The save
backup test, skipped by the generic Windows runner, was run separately with the
Windows C compiler and passed.

No new full-game playthrough, GPU visual test, or cross-vendor performance
benchmark was performed for this packaging pass. Classic UI visual validation
and Intel-specific graphics validation remain open. Compilation and synthetic
tests do not establish that every gameplay or driver problem is resolved.

Historical alpha patch-recipe tests use the pinned earlier source fixture.
Current runtime tests and packaged sources use the authored v2.3.2 engine.
