/** Development transport.
 *
 *  `pnpm dev` runs the extractor behind tools/dev-server.py, which speaks the
 *  same three operations KIKX's micro service does — start, send a line, read
 *  the stdout buffer — so the protocol layer above is the same code that runs
 *  inside KIKX. Only the transport differs.
 */

const BASE = "/dev-extractor";

async function call(path, options) {
  const response = await fetch(`${BASE}${path}`, options);

  if (!response.ok) {
    throw new Error(`Development extractor returned ${response.status}`);
  }

  return response.json();
}

export class DevChannel {
  constructor() {
    this.consumed = 0;
  }

  async start() {
    const { lines } = await call("/start", { method: "POST" });

    this.consumed = lines;
  }

  async send(payload) {
    await call("/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  }

  async readNewLines() {
    const { output } = await call(`/output?from=${this.consumed}`);

    this.consumed += output.length;

    return output;
  }

  get shouldReclaim() {
    return false;
  }

  async reclaim() {}
}
