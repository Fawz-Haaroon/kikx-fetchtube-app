/** Line transport over a KIKX micro service.
 *
 *  KIKX exposes a micro process as: start it, POST a line to its stdin, and GET
 *  the whole stdout buffer so far. There is no cursor, so the buffer is re-sent
 *  in full on every poll and only grows. Two things follow, and both are
 *  handled here rather than leaking into the protocol layer: the caller tracks
 *  how many lines it has consumed, and the buffer is reclaimed by restarting
 *  the process when it is large and nothing is running.
 */

const SERVICE_NAME = "extractor";

// Restarting is only safe when no job is running, so this is a ceiling the
// buffer is allowed to reach rather than a hard limit.
const LINES_BEFORE_RECLAIM = 500;

export class MicroChannel {
  constructor(micro) {
    this.micro = micro;
    this.consumed = 0;
    this.started = false;
  }

  async start() {
    if (this.started) {
      return;
    }

    await this.micro.start(SERVICE_NAME);

    // The service is persistent (app.json service_config), so it may already be
    // running with output from before this page loaded. Skipping what is
    // already buffered avoids replaying a finished download's progress.
    const { data } = await this.micro.output(SERVICE_NAME);

    this.consumed = Array.isArray(data) ? data.length : 0;
    this.started = true;
  }

  async send(payload) {
    await this.start();
    await this.micro.send(SERVICE_NAME, JSON.stringify(payload));
  }

  /** Every line written since the last call. */
  async readNewLines() {
    if (!this.started) {
      return [];
    }

    const { data, error } = await this.micro.output(SERVICE_NAME);

    if (error || !Array.isArray(data)) {
      return [];
    }

    if (data.length < this.consumed) {
      // The process restarted underneath us; its buffer began again at zero.
      this.consumed = 0;
    }

    const fresh = data.slice(this.consumed);

    this.consumed = data.length;

    return fresh;
  }

  get shouldReclaim() {
    return this.consumed >= LINES_BEFORE_RECLAIM;
  }

  /** Stop and restart the service to empty its stdout buffer. Only call this
   *  with no active jobs: restarting kills whatever is downloading. */
  async reclaim() {
    await this.micro.stop(SERVICE_NAME);

    this.started = false;
    this.consumed = 0;

    await this.start();
  }
}
