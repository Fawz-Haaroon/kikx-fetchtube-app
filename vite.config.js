import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "",
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url))
    }
  },
  build: {
    outDir: "www",
    emptyOutDir: true
  },
  server: {
    host: "0.0.0.0",
    port: 8080,
    proxy: {
      "/dev-extractor": {
        target: "http://127.0.0.1:8091",
        rewrite: path => path.replace(/^\/dev-extractor/, "")
      }
    }
  }
});
