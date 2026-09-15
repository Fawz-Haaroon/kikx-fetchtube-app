/** Builds the installable KIKX package.
 *
 *  KPM accepts a .kikx archive containing exactly one top-level directory
 *  (kikx/core/setup/pkg.py extract_package). That directory holds app.json plus
 *  every entry named in its "include" list.
 */

import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const staging = join(root, "build");
const appDirectory = join(staging, "app");

const manifest = JSON.parse(readFileSync(join(root, "app.json"), "utf8"));

rmSync(staging, { recursive: true, force: true });
mkdirSync(appDirectory, { recursive: true });

cpSync(join(root, "app.json"), join(appDirectory, "app.json"));

for (const entry of manifest.include) {
  const source = join(root, entry);

  if (!existsSync(source)) {
    throw new Error(
      `app.json includes "${entry}" but it does not exist. ` +
        (entry === "www" ? "Run the build first." : "")
    );
  }

  cpSync(source, join(appDirectory, entry), {
    recursive: true,
    filter: path => !path.endsWith("__pycache__") && !path.includes("__pycache__")
  });
}

const archive = join(staging, `${manifest.name}-${manifest.version}.kikx`);

execFileSync("zip", ["-qr", archive, "app"], { cwd: staging });

console.log(archive);
