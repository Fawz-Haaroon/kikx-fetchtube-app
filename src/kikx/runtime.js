import { FileSystemService, KVService, MicroService, createApp } from "kikx-sdk";

let connection = null;

/** KIKX serves an app at /app/<app-id>/index.html inside an iframe, and the SDK
 *  reads the id back out of that path. Outside a frame there is no id and no
 *  runtime. Evaluated on demand so this module stays importable off-browser. */
export function isEmbedded() {
  return typeof window !== "undefined" && window.parent !== window;
}

async function connect() {
  const app = createApp();

  await app.run();

  return {
    app,
    micro: new MicroService(app),
    kv: new KVService(app),
    fs: new FileSystemService(app),
    appId: app.getAppID()
  };
}

/** Resolves to the connected runtime, or null when FetchTube is not running
 *  inside KIKX. Callers branch on null rather than catching. */
export function useRuntime() {
  if (!isEmbedded()) {
    return Promise.resolve(null);
  }

  if (connection === null) {
    connection = connect().catch(() => null);
  }

  return connection;
}

/** KIKX serves an app's own data directory back to it at this path
 *  (kikx/kikx.py app_data_file). Range requests are supported, so the result is
 *  usable as a <video> source for a file FetchTube has already downloaded. */
export function appDataUrl(appId, relativePath) {
  const segments = relativePath.split("/").map(encodeURIComponent).join("/");

  return `/app-data/${appId}/${segments}`;
}
