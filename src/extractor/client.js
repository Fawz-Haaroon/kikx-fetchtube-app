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

// A process that is going to fail usually does so within its first second or
// two (Python interpreter startup, then an import or syntax error). Waiting
// this many empty polls -- once, per stall -- catches that quickly without
// adding a check to every poll of a legitimately slow operation.
const CRASH_CHECK_AFTER_EMPTY_POLLS = 2;

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
    this.emptyPollStreak = 0;
    this.livenessCheckedThisStall = false;
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

      throw new ProtocolError(
        error?.code || "service_unavailable",
        error?.message || "The extractor is not reachable."
      );
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

    if (lines.length > 0 || this.pending.size === 0) {
      this.emptyPollStreak = 0;
      this.livenessCheckedThisStall = false;
    } else {
      this.emptyPollStreak += 1;
      await this.checkForCrash();
    }

    this.schedule();
  }

  /** Nothing has arrived while at least one caller is waiting. If the extractor
   *  process has actually died -- it never started, or it started and exited
   *  almost immediately -- polling for output would otherwise wait out each
   *  pending request's own timeout (up to 190 seconds for a resolve) with no
   *  indication of why. Checked once per stall, not on every poll, so a
   *  legitimately slow operation against a healthy process is not penalised. */
  async checkForCrash() {
    if (this.livenessCheckedThisStall || this.emptyPollStreak < CRASH_CHECK_AFTER_EMPTY_POLLS) {
      return;
    }

    this.livenessCheckedThisStall = true;

    if (!this.channel.checkLiveness) {
      return;
    }

    let error;

    try {
      error = await this.channel.checkLiveness();
    } catch {
      return;
    }

    if (error) {
      this.failAllPending(new ProtocolError(error.code, error.message));
    }
  }

  failAllPending(error) {
    for (const entry of this.pending.values()) {
      clearTimeout(entry.timer);
      entry.reject(error);
    }

    this.pending.clear();
    this.emptyPollStreak = 0;
    this.livenessCheckedThisStall = false;
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
