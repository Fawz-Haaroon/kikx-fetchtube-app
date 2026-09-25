# FetchTube

A media fetching application for [KIKX](https://github.com/luvbyte/kikx) 0.4.0.

Paste a link, see what it actually contains, then play it or download it. Files
are stored in the app's own KIKX storage and can be played back there or handed
to the device.

FetchTube is an independent KIKX application. It does not modify KIKX or KIKX
MUI, and it is not a native Android application.

## Architecture

```
Android → Termux → KIKX runtime → KIKX MUI → FetchTube
                                              ├── www/    Vue frontend, served by KIKX at /app/<app-id>/
                                              └── micro/  extraction service, one persistent Python process
```

The frontend never runs yt-dlp. It sends JSON commands to a KIKX **micro
service**, which owns every subprocess and returns normalized results. One JSON
object per line in each direction:

| Command | Effect |
| --- | --- |
| `probe` | Reports the yt-dlp version, whether ffmpeg is present, and the Python version |
| `resolve` | Runs yt-dlp metadata extraction and returns normalized media |
| `download` | Starts a download job; job snapshots follow |
| `cancel` | Stops a running job and its child processes |
| `jobs` | Current job table, used to re-attach after the app reopens |
| `library` | Files currently stored in app data |
| `delete` | Removes one stored file |
| `forget` | Drops a finished job from the table |

Every state change publishes a complete job snapshot rather than a delta, so a
client that reloads mid-download converges on the truth without replaying
anything.

### Why micro rather than tasker

KIKX offers both. Micro was chosen because:

- Commands travel over stdin as structured JSON. Tasker builds a command string
  from a template, so a URL would have to be interpolated into text.
- `persistent: true` keeps the service alive when the app closes, so downloads
  continue. Tasker tasks are killed on `app:close`.
- One supervised process handles every job instead of one process per task.

## Requirements

| Requirement | Why | How to get it |
| --- | --- | --- |
| KIKX 0.4.0 | The runtime | `luvbyte/kikx` |
| Python 3 | Runs the micro service | Included with KIKX |
| yt-dlp | All extraction and downloading | `pkg install yt-dlp` (Termux) or `pip install yt-dlp` |
| ffmpeg | Only for merging separate video and audio streams | `pkg install ffmpeg` (Termux) |

FetchTube looks for a `yt-dlp` binary on `PATH` first, then falls back to
`python -m yt_dlp` in the interpreter running the service. If neither is
present, the app says so on the Fetch tab instead of failing silently.

Without ffmpeg, video-only formats are shown but not selectable, with the reason
on the row. Formats that already carry both streams still work.

## KIKX services and permissions

Declared in `app.json`:

- `micro` — the extraction service (`micro/extractor/main.py`, persistent, stdout captured)
- `kv` — resolve history
- `fs` — only to expose a stored file so the device can save it
- `system.access: ["alerts"]` — a notification when a download finishes or fails

The iframe sandbox is `allow-scripts allow-downloads`. `allow-same-origin` is
deliberately **not** requested: combined with `allow-scripts` it makes the
sandbox escapable, and nothing here needs it. One consequence is that the app
runs on an opaque origin, so `localStorage` is unavailable and all persistence
goes through KIKX KV.

No `fs` storage grants are requested. The `data://` protocol reaches only the
app's own data directory, which is all FetchTube writes to.

## Storage and downloads

```
user picks a format
  → micro service runs yt-dlp into <app cache>/jobs/<job id>/
  → on success the single produced file moves to <app data>/downloads/
  → the UI lists it and can play it from /app-data/<app-id>/downloads/<file>
  → "Save to device" exposes it through fs and lets the browser download it
```

- Downloads land in the app's KIKX data directory. That is the only location
  KIKX sanctions for an app, and it is not a user-visible media folder.
- To get a file onto the device, FetchTube calls `fs.expose("data://…")` and
  opens the returned serve URL, which KIKX sends with an attachment
  disposition. The WebView then writes it wherever it writes downloads. There is
  no Android MediaStore integration and none is claimed.
- Each job downloads into its own cache directory, so a partial transfer is
  never visible as a finished file. Cancelled and failed jobs store nothing and
  their directory is discarded. Anything left behind by a runtime crash is
  cleared at the next service start.
- Two downloads run at once; further jobs wait in `queued`.
- Progress comes from yt-dlp's own `--progress-template` output. When yt-dlp
  does not report a total size, speed, or ETA, the UI omits it rather than
  estimating.

## Playback

Playback uses the browser `<video>` element only.

A format is offered for in-app playback when it carries audio, uses a container
a WebView can open, and is served over plain HTTP. HLS, DASH and video-only
tracks are not, and the UI says so instead of offering a player that would show
a black frame or play silently. Downloaded files play from KIKX's `/app-data/`
route, which supports range requests.

## Development

```bash
npm install
npm run extractor   # terminal 1: runs the micro service behind a dev transport
npm run dev         # terminal 2: Vite on http://127.0.0.1:8080
```

The dev transport exposes the same three operations KIKX's micro service does,
so the protocol client in the browser is the same code either way. KV is not
available outside KIKX, so history does not persist in development and the
History tab says so.

Development storage lives in `.dev/`. Set `FETCHTUBE_DEV_WORKSPACE` to move it.

## Build and package

```bash
npm run build      # Vite → www/
npm run package    # → build/com.kikx.fetchtube-<version>.kikx
```

`www/` is build output and is not committed. `tools/package.mjs` copies
`app.json` plus every entry in its `include` list into a single top-level `app/`
directory and zips it, which is the layout KIKX's installer requires.

Install by uploading the `.kikx` file through KIKX, or by pointing KIKX at a
GitHub release carrying a `.kikx` asset. The release workflow builds, tests,
packages and attaches it on a `v*` tag.

Note that `app.json` contains `include`, which KIKX accepts in an installation
manifest but rejects in an installed one. Install through KPM; copying the
source tree into `apps/` by hand will not work.

## Tests

```bash
npm test           # extractor unit and protocol tests (Python)
npm run test:render  # server-renders the component tree
npm run test:client  # protocol client against a real extractor process
npm run test:micro   # MicroChannel against KIKX's real micro-service routes
```

`test:client` generates a short clip with ffmpeg, serves it over loopback, and
drives resolve, download, cancellation, library listing and deletion through the
same client that ships in the bundle. It skips itself if ffmpeg is missing.

`test:micro` is the one that matters most for KIKX integration: it drives the
real `MicroChannel` against KIKX's actual asyncio `Micro` class and HTTP routes
(only the auth layer is stubbed), for both a healthy extractor and one that
raises on its first line, and asserts the second case fails within a few
seconds with the real reason rather than after the full request timeout.
`test:client` cannot catch a bug in `MicroChannel` itself, since it talks to
`tools/dev-server.py` — a development stand-in with its own separate transport
class — not KIKX's real micro service. Set `KIKX_SOURCE_PATH` to a local KIKX
checkout, or place one at `../kikx`; it skips itself if neither is found.

## Known limitations

These are real and were not worked around:

- **Requires a KIKX build with the `Micro.demote`/`QTask.demote` fix.** On
  Termux, starting the extractor failed with `PermissionError` from
  `preexec_fn`, confirmed from a real device traceback: KIKX unconditionally
  tries to `setuid`/`setgid` the process to the identity already running it
  before every micro-service and tasker launch, and Android's per-app SELinux
  policy (`untrusted_app`) denies that syscall outright even though it would
  not change anything. This is not something `app.json` or FetchTube's own
  code can opt out of — it happens in KIKX core, before `main.py` runs. The fix
  (skip the syscalls when the target identity already matches the current one)
  needs to be applied to the KIKX checkout itself; see the project's own
  changelog for the exact patch. Confirmed against real KIKX server code that
  it does not change behaviour for a genuine privilege drop (root demoting a
  non-sudo app to `nobody`), only skips the no-op case that was failing.
- **The UI has not been run in a WebView inside KIKX.** It builds, server-renders
  and passes protocol tests, but no browser rendering was performed.
- **Playback of remote streams inside the KIKX iframe is unverified.** The
  playability rules follow container and protocol, not a capability probe.
- **"Save to device" is verified against the KIKX API contract, not against a
  real WebView download.**
- **KIKX re-sends a micro service's entire stdout buffer on every poll.** There is
  no cursor in KIKX 0.4.0. FetchTube limits progress output and restarts the
  service to reclaim the buffer when it has grown and nothing is running. A
  cursor parameter upstream would remove the need for this.
- **Long sessions with many downloads poll more data than necessary** for the same
  reason.
- **Live streams are not supported.** They are detected and reported.
- **Playlists are not supported.** If a link resolves to one, the first entry is
  used.

## Licence

Apache License 2.0. See [LICENCE](LICENCE).
