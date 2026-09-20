# Changelog

## 1.0.0

First working release. The inherited implementation could not install into KIKX
and several of its integration assumptions did not match the runtime, so the
extraction service and the frontend were rebuilt against the KIKX 0.4.0 source.

### Fixed

- The client had no way to tell a healthy extractor from one that failed to
  start at all. KIKX's micro `start()` reply already reports whether the
  process is running and why not if it isn't, but the SDK's
  `MicroService.start()` discards that body. Every startup failure was
  therefore invisible: the output list simply never received anything, and the
  UI reported a generic 20-second timeout regardless of the actual cause.
  `MicroChannel` now checks the same per-service status through `list()`, once
  right after starting and once more if a request stalls with nothing
  arriving, and the client fails immediately with the specific reason instead
  of waiting out the full timeout. Verified against KIKX's real micro-service
  routes and asyncio process handling — not a reimplementation — for both a
  healthy start and a process that raises on its first line.
- The package could never install: `app.json` listed `public` in `include` but
  the directory did not exist, so KIKX's installer raised `FileNotFoundError`
  on every attempt. Added `public/icon.png`.
- History silently never persisted. KIKX's KV `get` returns
  `{ key, exists, value }`, and the old code tested the envelope itself for an
  array, which is never true.
- The development bridge redeclared a destructured parameter, so the module did
  not parse.
- Codec fields were read as three-valued when yt-dlp reports them as three
  distinct cases. A `null` codec means "not reported", not "stream absent";
  treating them alike made direct media links report no usable formats.
- Output from concurrent download threads was written to stdout without a lock,
  which could interleave JSON lines.
- `resolve` ran on the stdin reader thread, blocking every other command,
  including cancellation, for the length of a network call.
- Cancellation raced the job table and could emit both a cancelled and a failed
  result for the same job.
- A 404 was classified as a network failure.
- The development extractor ignored its workspace setting, so files from one run
  leaked into the next.
- The release workflow used `pnpm install --frozen-lockfile` with no
  `pnpm-lock.yaml`, and packaged the app with a second, separate implementation
  of the packaging step.

### Added

- Download jobs with real state transitions, progress taken from yt-dlp's
  `--progress-template`, and working cancellation that stops child processes by
  process group so ffmpeg is stopped too.
- A per-job cache workspace, so a partial transfer is never visible as a
  finished file and cleanup is the removal of one directory.
- Clean shutdown: on stdin close or `SIGTERM` the service stops running
  downloads instead of orphaning them, and stale workspaces are cleared at
  start.
- Stored file library with local playback through KIKX's `/app-data/` route and
  "Save to device" through `fs.expose`.
- Environment probe surfaced in the UI, so a missing yt-dlp is reported and
  formats needing ffmpeg are shown as unselectable with the reason.
- Alerts on download completion and failure.
- Fetch, Downloads and History tabs.
- Format-id validation, so nothing can reach yt-dlp's `--format` expression
  language.
- Caps on resolve payload size, keeping one stdout line clear of the 10 MB limit
  KIKX reads with.
- Protocol, unit, render and end-to-end integration tests.

### Changed

- `micro` is used for extraction rather than tasker: structured stdin commands
  instead of a command-string template, and a persistent process so downloads
  survive the app closing.
- One protocol client over a swappable transport replaces the two divergent
  bridges, so KIKX and development run the same code.
- Removed `allow-same-origin` from the iframe sandbox. With `allow-scripts` it
  makes the sandbox escapable, and nothing in the app requires it.
- Added the `fs` service, used only to expose a stored file for saving.
- Packaging moved into `tools/package.mjs`, used by both the workflow and local
  builds.
