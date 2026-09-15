import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  // KIKX serves an app from /app/<app-id>/, so asset URLs must be relative.
  base: "",

  // "public" here is the KIKX package directory holding the app icon, not a
  // web asset root, so Vite must not copy it into the web build.
  publicDir: false,

  plugins: [vue(), tailwindcss()],

  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url))
    }
  },

  // The render smoke test builds in SSR mode, where Node would otherwise
  // resolve kikx-sdk to its CommonJS entry and lose the named exports.
  ssr: {
    noExternal: ["kikx-sdk"]
  },

  build: {
    // app.json declares "web": "www" by default, and the package includes www.
    outDir: "www",
    emptyOutDir: true
  },

  server: {
    host: "127.0.0.1",
    port: 8080,
    proxy: {
      "/dev-extractor": {
        target: "http://127.0.0.1:8091",
        rewrite: path => path.replace(/^\/dev-extractor/, "")
      }
    }
  }
});
