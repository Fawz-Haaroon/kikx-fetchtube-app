# KIKS FetchTube

A KIKX application that resolves a media URL, shows available formats, plays
browser-compatible files, and downloads the selected format.

It is not part of KIKX core and not a standalone Android app. KIKX installs
and launches it.

## Requirements

- KIKX 0.4.0
- Node 20+ for building the UI
- `yt-dlp` on the KIKX host (Termux: `pkg install yt-dlp` or `pip install yt-dlp`)

## Develop

```bash
pnpm install
python3 scripts/dev-extractor.py
pnpm dev
```

The Vite app proxies `/dev-extractor` to the local helper. That helper is only
for development. Inside KIKX the UI talks to the `extractor` micro service.

```bash
python3 -m unittest discover -s tests -v
pnpm build
```

`pnpm build` writes the web root to `www/`.

## Install into KIKX

Package layout expected by KPM:

```
app/
  app.json
  public/icon.png
  www/
  micro/extractor/main.py
```

The GitHub release workflow builds `app.kikx` (a zip of that tree). Install that
package with KIKX KPM, or copy a built tree and install from disk.

Requested KIKX services:

- `micro` — persistent Python extractor (`stdout` captured, JSON-lines I/O)
- `kv` — local history

Downloads are written to `$KIKX_APP_DATA_PATH/downloads`. Temporary files live
under `$KIKX_APP_CACHE_PATH/tmp` and are removed after success, failure, or
cancel.

## Extraction

The UI never runs yt-dlp. The micro process accepts JSON commands on stdin:

- `resolve` — `yt-dlp --dump-single-json --no-playlist`
- `download` — `yt-dlp -f <id>` with progress lines
- `cancel` — terminate the download process

URLs are validated as http(s) before any process starts. Arguments are passed
as a list; they are not interpolated into a shell.

## Limitations

- Playback uses the browser `<video>` element. HLS/DASH and video-only tracks
  are not treated as playable.
- There is no DRM, login, or paywall bypass.
- Long downloads depend on the KIKX micro process remaining alive.
- Termux must provide Python and yt-dlp; FetchTube does not vendor them.
