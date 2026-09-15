import { defineStore } from "pinia";
import { getExtractor } from "@/services/extractor.js";
import { errorFromUnknown } from "@/media/errors.js";

export const useDownloadStore = defineStore("downloads", {
  state: () => ({
    items: []
  }),
  getters: {
    active: state => state.items.filter(item =>
      ["queued", "starting", "downloading"].includes(item.status)
    )
  },
  actions: {
    async start({ url, format, title }) {
      const id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
      const item = {
        id,
        url,
        title,
        formatId: format.id,
        formatLabel: [format.kind, format.ext, format.height ? `${format.height}p` : null]
          .filter(Boolean)
          .join(" · "),
        status: "starting",
        percent: null,
        downloaded: null,
        total: format.filesize || null,
        speed: null,
        eta: null,
        filename: null,
        path: null,
        error: null
      };
      this.items.unshift(item);

      try {
        const extractor = await getExtractor();
        item.status = "downloading";
        const result = await extractor.startDownload({
          url,
          formatId: format.id,
          title,
          jobId: id,
          onProgress: progress => {
            item.status = "downloading";
            item.percent = progress.percent ?? item.percent;
            item.downloaded = progress.downloaded ?? item.downloaded;
            item.total = progress.total ?? item.total;
            item.speed = progress.speed ?? item.speed;
            item.eta = progress.eta ?? item.eta;
          }
        });
        item.status = "completed";
        item.percent = 100;
        item.filename = result.filename;
        item.path = result.path;
      } catch (error) {
        const mapped = errorFromUnknown(error);
        item.status = mapped.code === "cancelled" ? "cancelled" : "failed";
        item.error = mapped;
      }
    },
    async cancel(id) {
      const item = this.items.find(entry => entry.id === id);
      if (!item) return;
      try {
        const extractor = await getExtractor();
        await extractor.cancel(id);
        item.status = "cancelled";
      } catch (error) {
        item.error = errorFromUnknown(error);
      }
    }
  }
});
