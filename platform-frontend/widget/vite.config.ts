import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

// Standalone build target for the embeddable chat widget — deliberately
// separate from the root app's vite.config.ts/tsconfig.json so this bundle
// never pulls React (or anything else from the dashboard) into a customer's
// page, and so the root project's tsc -b / eslint / vite build never touch
// this directory. Produces a single IIFE a customer embeds via a <script> tag.
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
    lib: {
      entry: fileURLToPath(new URL("./src/main.ts", import.meta.url)),
      name: "PlatformChatWidget",
      formats: ["iife"],
      fileName: () => "widget.js",
    },
    minify: true,
  },
});
