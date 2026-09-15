import { errorFromUnknown } from "@/media/errors.js";
import { getMicro, hasKikx } from "./runtime.js";

const DEV_BASE = "/dev-extractor";

function newId() {
  return crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
}

class KikxBridge {
  constructor() {
    this.micro = null;
    this.seen = 0;
    this.waiters = new Map();
    this.listeners = [];
    this.polling = false;
  }

  async ensure() {
    if (this.micro) {
      return;
    }
    const service = getMicro();
    if (!service) {
      throw { code: "runtime", message: "KIKX micro service is not available." };
    }
    this.micro = await service.start("extractor");
    this.startPoll();
  }

  startPoll() {
    if (this.polling) {
      return;
    }
    this.polling = true;
    const tick = async () => {
      try {
        const { data, error } = await getMicro().output("extractor");
        if (!error && Array.isArray(data)) {
          const next = data.slice(this.seen);
          this.seen = data.length;
          for (const line of next) {
            this.dispatch(line);
          }
        }
      } catch {
        // The next tick retries. Losing one poll must not kill the session.
      }
      if (this.polling) {
        this.timer = setTimeout(tick, 400);
      }
    };
    tick();
  }

  dispatch(line) {
    const text = typeof line === "string" ? line.trim() : "";
    if (!text) return;
    let message;
    try {
      message = JSON.parse(text);
    } catch {
      return;
    }
    for (const listener of this.listeners) {
      listener(message);
    }
    if (message.id && this.waiters.has(message.id)) {
      this.waiters.get(message.id)(message);
    }
  }

  onMessage(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(item => item !== listener);
    };
  }

  async send(payload) {
    await this.ensure();
    const id = payload.id || newId();
    await this.micro.send(JSON.stringify({ ...payload, id }));
    return id;
  }

  waitFor(id, match) {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.waiters.delete(id);
        reject({ code: "network", message: "The extractor did not respond." });
      }, 200000);

      this.waiters.set(id, message => {
        if (!match(message)) {
          return;
        }
        clearTimeout(timeout);
        this.waiters.delete(id);
        if (message.type === "error") {
          reject(errorFromUnknown(message));
        } else {
          resolve(message);
        }
      });
    });
  }

  async resolve(url) {
    const id = await this.send({ op: "resolve", url });
    const result = await this.waitFor(id, message =>
      message.id === id && (message.type === "result" || message.type === "error")
    );
    return result.media;
  }

  async startDownload({ url, formatId, title, jobId, onProgress }) {
    const id = jobId || newId();
    const off = this.onMessage(message => {
      if (message.id !== id && message.jobId !== id) return;
      if (message.type === "progress" && onProgress) {
        onProgress(message);
      }
    });
    const pending = this.waitFor(id, message =>
      message.id === id && (message.type === "complete" || message.type === "error")
    );
    await this.send({ id, op: "download", url, formatId, title, jobId: id });
    try {
      const result = await pending;
      return { jobId: id, ...result };
    } finally {
      off();
    }
  }

  async cancel(jobId) {
    await this.send({ op: "cancel", jobId });
  }
}

class DevBridge {
  async resolve(url) {
    const response = await fetch(`${DEV_BASE}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw errorFromUnknown(payload);
    }
    return payload.media;
  }

  async startDownload({ url, formatId, title, jobId, onProgress }) {
    const start = await fetch(`${DEV_BASE}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, formatId, title, jobId })
    });
    const body = await start.json();
    if (!start.ok) {
      throw errorFromUnknown(body);
    }
    const jobId = body.jobId;

    while (true) {
      await new Promise(resolve => setTimeout(resolve, 500));
      const status = await fetch(`${DEV_BASE}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId })
      });
      const snapshot = await status.json();
      if (snapshot.error) {
        throw errorFromUnknown(snapshot.error);
      }
      if (snapshot.progress && onProgress) {
        onProgress(snapshot.progress);
      }
      if (snapshot.result) {
        return { jobId, ...snapshot.result };
      }
    }
  }

  async cancel(jobId) {
    await fetch(`${DEV_BASE}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId })
    });
  }
}

let bridge = null;

export async function getExtractor() {
  if (bridge) {
    return bridge;
  }
  bridge = hasKikx() ? new KikxBridge() : new DevBridge();
  return bridge;
}
