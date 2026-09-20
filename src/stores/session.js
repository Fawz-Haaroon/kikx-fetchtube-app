import { defineStore } from "pinia";

import { ExtractorClient } from "@/extractor/client.js";
import { DevChannel } from "@/kikx/devChannel.js";
import { MicroChannel } from "@/kikx/microChannel.js";
import { appDataUrl, useRuntime } from "@/kikx/runtime.js";
import { codeOf, describe, detailOf } from "@/extractor/messages.js";

let client = null;
let runtimeRef = null;

export function extractor() {
  if (client === null) {
    throw new Error("The session has not been started yet.");
  }

  return client;
}

export function runtime() {
  return runtimeRef;
}

export const useSessionStore = defineStore("session", {
  state: () => ({
    status: "starting",
    appId: null,
    environment: null,
    failure: null
  }),

  getters: {
    hasYtDlp: state => Boolean(state.environment?.ytDlpVersion),
    hasFfmpeg: state => Boolean(state.environment?.hasFfmpeg),
    canSaveToDevice: state => Boolean(state.appId)
  },

  actions: {
    async start() {
      runtimeRef = await useRuntime();
      this.appId = runtimeRef?.appId || null;

      client = new ExtractorClient(
        runtimeRef ? new MicroChannel(runtimeRef.micro) : new DevChannel()
      );

      client.start();

      try {
        this.environment = await client.probe();
        this.status = "ready";
      } catch (error) {
        this.status = "failed";
        this.failure = { code: codeOf(error), message: describe(error), detail: detailOf(error) };
      }
    },

    localUrlFor(relativePath) {
      return this.appId ? appDataUrl(this.appId, relativePath) : null;
    }
  }
});
