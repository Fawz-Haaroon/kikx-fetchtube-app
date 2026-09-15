/** The FetchTube extraction protocol.
 *
 *  One JSON object per line in each direction. Replies carry the id of the
 *  request that caused them; job snapshots arrive unsolicited and are broadcast
 *  to listeners. The transport is injected so the same protocol runs over the
 *  KIKX micro service and over the development helper.
 */

const RESOLVE_TIMEOUT_MS = 190000;
const DEFAULT_TIMEOUT_MS = 20000;

const ACTIVE_POLL_MS = 700;
const IDLE_POLL_MS = 2500;

function newRequestId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export class ProtocolError extends Error {
  constructor(code, message) {
    super(message || code);
    this.code = code;
  }
}

export class ExtractorClient {
  constructor(channel) {
    this.channel = channel;
    this.pending = new Map();
    this.jobListeners = new Set();
    this.timer = null;
    this.busy = false;
  }

  onJob(listener) {
    this.jobListeners.add(listener);

    return () => this.jobListeners.delete(listener);
  }

  // ---------------------- Requests
  async request(operation, payload = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
    const id = newRequestId();

    const settled = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new ProtocolError("no_response", "The extractor did not respond."));
      }, timeoutMs);

      this.pending.set(id, { resolve, reject, timer });
    });

    try {
      await this.channel.send({ id, op: operation, ...payload });
    } catch (error) {
      const entry = this.pending.get(id);

      if (entry) {
        clearTimeout(entry.timer);
        this.pending.delete(id);
      }

      throw new ProtocolError("service_unavailable", error?.message || "The extractor is not reachable.");
    }

    this.poll();

    return settled;
  }

  probe() {
    return this.request("probe").then(message => message.environment);
  }

  resolve(url) {
    return this.request("resolve", { url }, RESOLVE_TIMEOUT_MS).then(message => message.media);
  }

  startDownload(request) {
    return this.request("download", request).then(message => message.jobId);
  }

  cancel(jobId) {
    return this.request("cancel", { jobId });
  }

  forget(jobId) {
    return this.request("forget", { jobId });
  }

  jobs() {
    return this.request("jobs").then(message => message.jobs);
  }

  library() {
    return this.request("library").then(message => message.entries);
  }

  deleteFile(filename) {
    return this.request("delete", { filename });
  }

  // ---------------------- Polling
  /** Poll quickly while work is outstanding and slowly otherwise. The KIKX
   *  micro output endpoint returns the whole buffer every time, so polling
   *  faster than necessary costs real bandwidth on a phone. */
  setBusy(busy) {
    this.busy = busy;
    this.schedule();
  }

  start() {
    this.schedule();
  }

  stop() {
    clearTimeout(this.timer);
    this.timer = null;
  }

  schedule() {
    clearTimeout(this.timer);

    const interval = this.busy || this.pending.size > 0 ? ACTIVE_POLL_MS : IDLE_POLL_MS;

    this.timer = setTimeout(() => this.poll(), interval);
  }

  async poll() {
    let lines = [];

    try {
      lines = await this.channel.readNewLines();
    } catch {
      // A dropped poll is not a failure; the next one returns the same lines
      // because the cursor only advances on success.
    }

    for (const line of lines) {
      this.dispatch(line);
    }

    this.schedule();
  }

  dispatch(line) {
    const text = typeof line === "string" ? line.trim() : "";

    if (!text) {
      return;
    }

    let message;

    try {
      message = JSON.parse(text);
    } catch {
      return;
    }

    if (message.type === "job" && message.job) {
      for (const listener of this.jobListeners) {
        listener(message.job);
      }

      return;
    }

    const entry = message.id ? this.pending.get(message.id) : null;

    if (!entry) {
      return;
    }

    clearTimeout(entry.timer);
    this.pending.delete(message.id);

    if (message.type === "error") {
      entry.reject(new ProtocolError(message.code, message.message));
    } else {
      entry.resolve(message);
    }
  }
}
