import react from "@vitejs/plugin-react";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, URL } from "node:url";
// Imported from "vitest/config" rather than "vite" so the `test` block below
// (coverage in particular) is typed. Vite's own defineConfig has no `test` key.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 5173,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
    // widget/ is an independent build target (own package.json, tsconfig, vite
    // config; eslint ignores it and the root tsconfig excludes it). We reach into
    // it *for tests only* so its deliberately-duplicated SSE parser is covered
    // without installing a second test runner. Its build/lint/typecheck
    // isolation is untouched. Widget tests must use relative imports — the "@"
    // alias resolves to src/ and widget code may not depend on app code.
    include: ["src/**/*.test.{ts,tsx}", "widget/src/**/*.test.ts"],
    // Each test file spins up its own jsdom. Unbounded parallelism starved the
    // event loop on a modest dev box badly enough that a 0.5s test blocked for
    // 190s and tripped the default 5s timeout — a flake caused purely by
    // scheduling, not by the code under test. Capping workers and allowing more
    // headroom per test makes the suite deterministic (and no slower overall).
    minWorkers: 1,
    maxWorkers: 4,
    testTimeout: 15000,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      // Reports are written to the OS temp dir rather than into the repo. This
      // project lives on a OneDrive-synced path, and OneDrive keeps handles on
      // freshly created directories long enough that the v8 provider's cleanup
      // of its own scratch dir fails with EPERM and fails the whole run — even
      // though every test passed. The text reporter still prints the summary to
      // the terminal; the HTML report path is logged at the end of the run.
      reportsDirectory: join(tmpdir(), "platform-frontend-coverage"),
      include: ["src/**/*.{ts,tsx}", "widget/src/**/*.ts"],
      exclude: [
        "src/test/**",
        "**/*.test.{ts,tsx}",
        "src/main.tsx",
        "src/vite-env.d.ts",
        "**/*.module.css",
      ],
    },
  },
});
