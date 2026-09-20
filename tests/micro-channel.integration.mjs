/** Drives the shipped MicroChannel + ExtractorClient against KIKX's actual
 *  micro-service HTTP routes and asyncio process management -- the exact
 *  transport used inside KIKX, not the development stand-in tools/dev-server.py
 *  talks to.
 *
 *  This exists because a real, user-facing bug reached production without it:
 *  when the extractor process failed to start, the client had no way to find
 *  out and simply waited out its full request timeout, reporting "The
 *  extractor did not respond" regardless of the actual cause. test:client
 *  alone could not have caught this, because it never exercises MicroChannel
 *  or a real KIKX server at all.
 *
 *  Requires a local KIKX source checkout. Set KIKX_SOURCE_PATH to it, or place
 *  one at ../kikx relative to this repo. Skipped (exit 0) if neither is found,
 *  or if the .kikx package has not been built yet.
 */
import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { MicroChannel } from "../src/kikx/microChannel.js";
import { ExtractorClient } from "../src/extractor/client.js";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const HEALTHY_PORT = 8391;
const BROKEN_PORT = 8392;

function findKikxSource() {
  const candidates = [process.env.KIKX_SOURCE_PATH, join(REPO_ROOT, "..", "kikx")].filter(Boolean);

  return candidates.find(path => existsSync(join(path, "kikx", "kikx.py"))) || null;
}

function findPackage() {
  const manifest = JSON.parse(readFileSync(join(REPO_ROOT, "app.json"), "utf8"));
  const path = join(REPO_ROOT, "build", `${manifest.name}-${manifest.version}.kikx`);

  return existsSync(path) ? path : null;
}

function buildBrokenPackage(healthyPackagePath, workspace) {
  const stagingDir = join(workspace, "broken-app");

  rmSync(stagingDir, { recursive: true, force: true });
  execFileSync("unzip", ["-q", healthyPackagePath, "-d", stagingDir]);

  const mainPyPath = join(stagingDir, "app", "micro", "extractor", "main.py");
  const original = readFileSync(mainPyPath, "utf8");

  writeFileSync(mainPyPath, "raise RuntimeError('simulated startup failure for testing')\n" + original);

  const brokenPackagePath = join(workspace, "broken.kikx");

  execFileSync("zip", ["-qr", brokenPackagePath, "app"], { cwd: stagingDir });

  return brokenPackagePath;
}

function fakeApp(port) {
  return {
    getAppID: () => "test-app",
    getUrl: path => `http://127.0.0.1:${port}${path}`,
    system: {},
  };
}

function startServer(kikxSource, packagePath, port) {
  const server = spawn(
    "python3",
    [join(REPO_ROOT, "tests", "real-micro-server.py"), kikxSource, packagePath, String(port)],
    { stdio: ["ignore", "pipe", "inherit"] }
  );

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`server on port ${port} did not report ready`)), 15000);

    server.stdout.on("data", chunk => {
      if (chunk.toString().includes("ready")) {
        clearTimeout(timer);
        resolve(server);
      }
    });

    server.on("exit", code => {
      if (code !== null && code !== 0) {
        clearTimeout(timer);
        reject(new Error(`server on port ${port} exited with code ${code}`));
      }
    });
  });
}

async function timeIt(fn) {
  const start = Date.now();
  const result = await fn().catch(error => ({ __error: error }));

  return { result, elapsedMs: Date.now() - start };
}

let failures = 0;

function check(name, condition, detail = "") {
  console.log(`  ${condition ? "ok  " : "FAIL"} ${name} ${detail}`);

  if (!condition) {
    failures += 1;
  }
}

async function main() {
  const kikxSource = findKikxSource();
  const healthyPackagePath = findPackage();

  if (!kikxSource) {
    console.log("No local KIKX checkout found (set KIKX_SOURCE_PATH). Skipping.");
    process.exit(0);
  }

  if (!healthyPackagePath) {
    console.log("No built .kikx package found. Run `npm run build && npm run package` first. Skipping.");
    process.exit(0);
  }

  const workspace = mkdtempSync(join(tmpdir(), "fetchtube-micro-channel-"));
  const brokenPackagePath = buildBrokenPackage(healthyPackagePath, workspace);

  const healthyServer = await startServer(kikxSource, healthyPackagePath, HEALTHY_PORT);
  const brokenServer = await startServer(kikxSource, brokenPackagePath, BROKEN_PORT);

  const stop = () => {
    healthyServer.kill();
    brokenServer.kill();
    rmSync(workspace, { recursive: true, force: true });
  };

  process.on("exit", stop);

  console.log("healthy extractor");
  {
    const client = new ExtractorClient(new MicroChannel(new MicroServiceStub(fakeApp(HEALTHY_PORT))));

    client.start();

    const { result, elapsedMs } = await timeIt(() => client.probe());

    check("probe succeeds", !result?.__error, result?.__error?.message);
    check("probe returns a yt-dlp version", Boolean(result?.ytDlpVersion));
    check(`is not penalised by the liveness check (${elapsedMs}ms)`, elapsedMs < 3000);

    client.stop();
  }

  console.log("extractor that crashes on startup");
  {
    const client = new ExtractorClient(new MicroChannel(new MicroServiceStub(fakeApp(BROKEN_PORT))));

    client.start();

    const { result, elapsedMs } = await timeIt(() => client.probe());

    check("probe rejects instead of hanging", Boolean(result?.__error));
    check(`fails within a few seconds, not the 20s default timeout (${elapsedMs}ms)`, elapsedMs < 6000);
    check("reports the specific crash code", result?.__error?.code === "extractor_crashed", result?.__error?.code);
    check(
      "surfaces the real Python failure text",
      result?.__error?.message?.includes("simulated startup failure for testing")
    );

    client.stop();
  }

  stop();

  console.log(failures === 0 ? "\nAll checks passed." : `\n${failures} check(s) failed.`);
  process.exit(failures === 0 ? 0 : 1);
}

// A tiny stand-in for kikx-sdk's MicroService: MicroChannel only ever calls
// start/output/send/list/stop, each a thin wrapper over Service.request with
// the same endpoint names and body shapes the real class uses.
class MicroServiceStub {
  constructor(app) {
    this.app = app;
  }

  async request(endpoint, { method = "GET", body, params = {} } = {}) {
    const url = new URL(this.app.getUrl(`/service/micro/${endpoint}`));

    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, String(value)));

    const response = await fetch(url, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).catch(error => ({ __networkError: error }));

    if (response.__networkError) {
      return { data: null, error: { status: null, message: response.__networkError.message } };
    }

    const data = await response.json();

    return response.ok ? { data, error: null } : { data: null, error: { status: response.status, message: data?.detail } };
  }

  start = name => this.request("start", { params: { name } });
  output = name => this.request("output", { params: { name } });
  send = (name, data) => this.request("send", { method: "POST", body: { name, data } });
  list = () => this.request("list");
  stop = name => this.request("stop", { params: { name } });
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
