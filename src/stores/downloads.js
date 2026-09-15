import { defineStore } from "pinia";

import { codeOf, describe, detailOf } from "@/extractor/messages.js";
import { needsMerge, qualityLabel } from "@/media/format.js";
import { extractor, runtime } from "./session.js";

const ACTIVE_STATES = new Set(["queued", "downloading", "merging", "storing"]);

// KIKX treats an expose expiry as minutes (kikx/services/fs/expose.py). Long
// enough for the browser to finish writing a large file, short enough that the
// link does not outlive the reason it was created.
const EXPOSE_MINUTES = 10;

function labelFor(track) {
  return [qualityLabel(track), track.ext.toUpperCase(), needsMerge(track) ? "merged" : null]
    .filter(Boolean)
    .join(" · ");
}

/** KIKX shows an app's alert in the host UI, which is where the user is if a
 *  long download finished while they were elsewhere. Requires the "alerts"
 *  system permission in app.json. */
async function announce(job) {
  const system = runtime()?.app?.system;

  if (!system) {
    return;
  }

  if (job.state === "completed") {
    await system.alert(`Saved ${job.title}`, { type: "success" });
  } else if (job.state === "failed") {
    await system.alert(`${job.title} failed to download`, { type: "error" });
  }
}

function newJobId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `job-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export const useDownloadStore = defineStore("downloads", {
  state: () => ({
    jobs: [],
    library: [],
    failure: null
  }),

  getters: {
    active: state => state.jobs.filter(job => ACTIVE_STATES.has(job.state)),
    finished: state => state.jobs.filter(job => !ACTIVE_STATES.has(job.state)),
    hasActive() {
      return this.active.length > 0;
    }
  },

  actions: {
    /** Snapshots replace by id, so a reconnect or a missed poll converges
     *  without replaying anything. */
    applySnapshot(job) {
      const index = this.jobs.findIndex(existing => existing.id === job.id);
      const previous = index < 0 ? null : this.jobs[index];

      if (index < 0) {
        this.jobs = [job, ...this.jobs];
      } else {
        this.jobs.splice(index, 1, job);
      }

      extractor().setBusy(this.hasActive);

      if (job.state === "completed") {
        void this.loadLibrary();
      }

      if (previous && previous.state !== job.state) {
        void announce(job);
      }

      if (!ACTIVE_STATES.has(job.state)) {
        void this.reclaimIfIdle();
      }
    },

    async attach() {
      extractor().onJob(job => this.applySnapshot(job));

      // The extractor is persistent, so downloads started before this page
      // loaded may still be running.
      this.jobs = await extractor().jobs();

      extractor().setBusy(this.hasActive);

      await this.loadLibrary();
    },

    async loadLibrary() {
      this.failure = null;

      try {
        this.library = await extractor().library();
      } catch (error) {
        this.failure = { code: codeOf(error), message: describe(error) };
      }
    },

    async start({ media, track, audioTrack }) {
      this.failure = null;

      try {
        await extractor().startDownload({
          jobId: newJobId(),
          url: media.requestedUrl,
          title: media.title,
          formatLabel: labelFor(track),
          videoFormatId: track.id,
          audioFormatId: needsMerge(track) ? audioTrack?.id || null : null
        });

        extractor().setBusy(true);
      } catch (error) {
        this.failure = {
          code: codeOf(error),
          message: describe(error),
          detail: detailOf(error)
        };
      }
    },

    async cancel(jobId) {
      this.failure = null;

      try {
        await extractor().cancel(jobId);
      } catch (error) {
        this.failure = { code: codeOf(error), message: describe(error) };
      }
    },

    async dismiss(jobId) {
      this.jobs = this.jobs.filter(job => job.id !== jobId);

      try {
        await extractor().forget(jobId);
      } catch {
        // The list is already correct; the extractor drops it on restart.
      }

      await this.reclaimIfIdle();
    },

    async remove(filename) {
      this.failure = null;

      try {
        await extractor().deleteFile(filename);

        this.library = this.library.filter(entry => entry.filename !== filename);
        this.jobs = this.jobs.filter(job => job.filename !== filename);
      } catch (error) {
        this.failure = { code: codeOf(error), message: describe(error) };
      }
    },

    /** KIKX re-sends a micro service's entire stdout buffer on every poll. When
     *  it has grown and nothing is running, restarting the service empties it.
     *  Jobs live in this store and files live on disk, so nothing is lost. */
    async reclaimIfIdle() {
      try {
        const client = extractor();

        if (this.hasActive || !client.channel.shouldReclaim) {
          return;
        }

        await client.channel.reclaim();
      } catch {
        // Reclaiming is an optimisation; failing to do it changes nothing.
      }
    },

    /** Hands a stored file to the browser so it lands in the device's own
     *  downloads folder. KIKX's fs service exposes a path under a one-time uid
     *  and serves it as an attachment (kikx/services/fs/main.py). */
    async deviceUrlFor(relativePath) {
      this.failure = null;

      const fs = runtime()?.fs;

      if (!fs) {
        return null;
      }

      const { data, error } = await fs.expose(`data://${relativePath}`, EXPOSE_MINUTES);

      if (error || !data?.uid) {
        this.failure = {
          code: "storage_failure",
          message: describe({ code: "storage_failure" })
        };

        return null;
      }

      return fs.getServeAbsUrl(data.uid);
    }
  }
});
