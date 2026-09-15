/** Drives the browser protocol client against a real extractor process.
 *
 *  The transport is swapped for one that talks to tools/dev-server.py over
 *  HTTP, so the code under test is exactly the client that ships in the bundle:
 *  request correlation, job snapshot broadcasting and the polling loop.
 *
 *  Run with: node tests/client.integration.mjs
 */

import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";

import { ExtractorClient } from "../src/extractor/client.js";

const DEV_SERVER = "http://127.0.0.1:8091";
const MEDIA_SERVER_PORT = 8097;
const SLOW_SERVER_PORT = 8098;

let failures = 0;

function check(name, condition, detail = "") {
  if (condition) {
    console.log(`  ok   ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${name} ${detail}`);
  }
}

class HttpChannel {
  constructor() {
    this.consumed = 0;
  }

  async start() {
    const response = await fetch(`${DEV_SERVER}/start`, { method: "POST" });
    const { lines } = await response.json();

    this.consumed = lines;
  }

  async send(payload) {
    await this.start();

    const response = await fetch(`${DEV_SERVER}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`send failed: ${response.status}`);
    }
  }

  async readNewLines() {
    const response = await fetch(`${DEV_SERVER}/output?from=${this.consumed}`);
    const { output } = await response.json();

    this.consumed += output.length;

    return output;
  }

  get shouldReclaim() {
    return false;
  }

  async reclaim() {}
}

function waitFor(predicate, timeoutMs, label) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;

    const tick = () => {
      const value = predicate();

      if (value) {
        resolve(value);
      } else if (Date.now() > deadline) {
        reject(new Error(`timed out waiting for ${label}`));
      } else {
        setTimeout(tick, 50);
      }
    };

    tick();
  });
}

/** A short clip served over loopback. Using a real file keeps the test honest:
 *  yt-dlp really resolves it and really downloads it. */
function createClip(directory) {
  execFileSync("ffmpeg", [
    "-loglevel", "error", "-y",
    "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15:duration=4",
    "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-shortest",
    join(directory, "clip.mp4")
  ]);
}

async function main() {
  const workspace = mkdtempSync(join(tmpdir(), "fetchtube-client-"));
  const mediaDirectory = mkdtempSync(join(tmpdir(), "fetchtube-media-"));

  try {
    createClip(mediaDirectory);
    writeFileSync(join(mediaDirectory, "large.mp4"), randomBytes(8 * 1024 * 1024));
  } catch {
    console.log("ffmpeg is required to generate the test clip. Skipping.");
    process.exit(0);
  }

  const mediaServer = spawn(
    "python3",
    ["-m", "http.server", String(MEDIA_SERVER_PORT), "--bind", "127.0.0.1"],
    { cwd: mediaDirectory, stdio: "ignore" }
  );

  // Rate limited so cancellation can act while the transfer is still running.
  const slowServer = spawn(
    "python3",
    [
      "tests/slow-media-server.py",
      String(SLOW_SERVER_PORT),
      join(mediaDirectory, "large.mp4"),
      String(256 * 1024)
    ],
    { cwd: new URL("..", import.meta.url).pathname, stdio: "ignore" }
  );

  const devServer = spawn("python3", ["tools/dev-server.py"], {
    cwd: new URL("..", import.meta.url).pathname,
    stdio: "ignore",
    env: { ...process.env, FETCHTUBE_DEV_WORKSPACE: workspace }
  });

  const stop = () => {
    mediaServer.kill();
    slowServer.kill();
    devServer.kill();
  };

  process.on("exit", stop);

  await new Promise(resolve => setTimeout(resolve, 1800));

  const client = new ExtractorClient(new HttpChannel());
  const jobs = [];

  client.onJob(job => {
    const index = jobs.findIndex(existing => existing.id === job.id);

    if (index < 0) {
      jobs.push(job);
    } else {
      jobs.splice(index, 1, job);
    }
  });

  client.start();

  const url = `http://127.0.0.1:${MEDIA_SERVER_PORT}/clip.mp4`;

  console.log("environment");
  const startingLibrary = await client.library();
  check("the run starts from an empty library", startingLibrary.length === 0,
    JSON.stringify(startingLibrary.map(entry => entry.filename)));

  const environment = await client.probe();
  check("probe returns a yt-dlp version", Boolean(environment.ytDlpVersion), JSON.stringify(environment));

  console.log("resolve");
  const media = await client.resolve(url);
  check("media has a title", Boolean(media.title));
  check("media has at least one format", media.formats.length > 0);
  check("a format is marked playable", media.formats.some(track => track.playable));

  console.log("invalid input");
  let rejected = null;
  await client.resolve("ftp://example.com/a").catch(error => {
    rejected = error;
  });
  check("a non-http link is rejected by code", rejected?.code === "invalid_url", rejected?.code);

  console.log("download");
  const jobId = await client.startDownload({
    jobId: "integration-job",
    url,
    title: "Integration Clip",
    formatLabel: "mp4",
    videoFormatId: media.formats[0].id,
    audioFormatId: null
  });
  check("download is accepted with the requested id", jobId === "integration-job", jobId);

  const completed = await waitFor(
    () => jobs.find(job => job.id === "integration-job" && job.state === "completed"),
    60000,
    "the download to finish"
  );
  check("the finished job reports a stored filename", Boolean(completed.filename), completed.filename);
  check("the finished job reports a data-relative path",
    completed.relativePath?.startsWith("downloads/"), completed.relativePath);
  check("the finished job reports a real size", completed.sizeBytes > 0);

  console.log("cancellation");
  await client.startDownload({
    jobId: "cancel-job",
    url: `http://127.0.0.1:${SLOW_SERVER_PORT}/large.mp4`,
    title: "Cancelled Clip",
    formatLabel: "mp4",
    videoFormatId: "mp4",
    audioFormatId: null
  });

  await waitFor(
    () =>
      jobs.find(
        job => job.id === "cancel-job" && job.state === "downloading" && job.downloadedBytes > 0
      ),
    30000,
    "the cancellable download to report progress"
  );

  await client.cancel("cancel-job");

  const cancelled = await waitFor(
    () => jobs.find(job => job.id === "cancel-job" && job.state !== "downloading"),
    30000,
    "the download to stop"
  );
  check("a cancelled download reports cancelled, not completed",
    cancelled.state === "cancelled", cancelled.state);
  check("a cancelled download stores no file", !cancelled.filename, cancelled.filename);

  const afterCancel = await client.library();
  check("a partial file never reaches the library",
    afterCancel.every(entry => !entry.filename.includes("Cancelled")),
    JSON.stringify(afterCancel.map(entry => entry.filename)));

  let secondCancel = null;
  await client.cancel("cancel-job").catch(error => {
    secondCancel = error;
  });
  check("cancelling a finished job is refused", secondCancel?.code === "job_not_active",
    secondCancel?.code);

  await client.forget("cancel-job");

  console.log("library");
  const library = await client.library();
  check("the stored file appears in the library",
    library.some(entry => entry.filename === completed.filename));

  console.log("cleanup");
  await client.deleteFile(completed.filename);
  const afterDelete = await client.library();
  check("the deleted file is gone", afterDelete.length === 0);

  let deleteError = null;
  await client.deleteFile("../../app.json").catch(error => {
    deleteError = error;
  });
  check("a path outside the library is refused", deleteError?.code === "file_not_found", deleteError?.code);

  client.stop();
  stop();

  console.log(failures === 0 ? "\nAll client integration checks passed." : `\n${failures} check(s) failed.`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
