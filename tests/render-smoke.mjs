/** Runs the server-rendered component tree built by `npm run test:render`. */

import process from "node:process";

const { render } = await import("../.dev/ssr/render-smoke.entry.js");

const html = await render();

const checks = [
  ["the component tree renders", html.length > 100],
  ["the shell markup is present", html.includes("<div")],
  [
    "all three tabs render",
    html.includes("Fetch") && html.includes("Downloads") && html.includes("History")
  ]
];

let failures = 0;

for (const [name, passed] of checks) {
  console.log(`  ${passed ? "ok  " : "FAIL"} ${name}`);

  if (!passed) {
    failures += 1;
  }
}

console.log(failures === 0 ? "Render smoke passed." : `${failures} render check(s) failed.`);
process.exit(failures === 0 ? 0 : 1);
