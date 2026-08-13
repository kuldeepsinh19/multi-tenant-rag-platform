/**
 * ./tokens.ts is generated from src/styles/tokens.css by
 * widget/scripts/gen-tokens.mjs, but it is *committed* — the widget's vite build
 * does not run the generator as a plugin, and the file has to be readable and
 * reviewable in a diff. A committed generated file rots the moment someone edits
 * the source without regenerating, so this test re-runs the generator and
 * asserts the committed bytes still match.
 *
 * It spawns the CLI rather than importing the module on purpose: that covers the
 * real entry point — argument handling, path resolution from import.meta.url,
 * and utf8 encoding — which an in-process import would silently bypass.
 *
 * Lives under widget/ rather than src/ so the root tsconfig (include: ["src"])
 * never pulls widget code into the app's typecheck. Imports are relative for the
 * same reason — the "@" alias points at src/ and is off-limits here.
 */

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Resolved from import.meta.url, never cwd: vitest runs from the repo root while
// the npm script runs from widget/.
const HERE = dirname(fileURLToPath(import.meta.url));
const GENERATOR = resolve(HERE, "../../scripts/gen-tokens.mjs");
const COMMITTED = resolve(HERE, "./tokens.ts");

describe("generated widget tokens", () => {
  it("matches a fresh run of the generator", () => {
    const regenerated = execFileSync(process.execPath, [GENERATOR, "--stdout"], {
      encoding: "utf8",
    });
    // Defensive: git autocrlf could have checked the committed file out with
    // CRLF endings even though the generator only ever writes "\n".
    const committed = readFileSync(COMMITTED, "utf8").replace(/\r\n/g, "\n");

    expect(
      committed,
      'widget/src/generated/tokens.ts is out of date with src/styles/tokens.css. Run "npm run gen:tokens" and commit the result.',
    ).toBe(regenerated);
  });
});
