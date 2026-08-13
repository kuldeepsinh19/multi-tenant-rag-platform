// @ts-check
/**
 * Generates widget/src/generated/tokens.ts from src/styles/tokens.css.
 *
 * The widget is an independent build target and must not import app source, so
 * its CSS custom properties are *copied* rather than shared. This script is what
 * makes that copy safe: the values have exactly one author (tokens.css) and a
 * drift test (../src/generated/tokens.drift.test.ts) fails the build if the
 * committed output no longer matches the source.
 *
 * Plain .mjs on purpose: Node 20 cannot execute TypeScript, and nothing imports
 * this module (the drift test spawns it as a CLI), so there is no .d.mts and no
 * tsconfig entry.
 *
 * Usage:
 *   node scripts/gen-tokens.mjs            write ../src/generated/tokens.ts
 *   node scripts/gen-tokens.mjs --stdout   print the file to stdout
 *   node scripts/gen-tokens.mjs --check    exit 1 if the committed file is stale
 */

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Paths are resolved from import.meta.url, never cwd: this runs from widget/
// (npm script), from the repo root (npm --prefix passthrough) and from a vitest
// worker, all with different working directories.
const HERE = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(HERE, "../../src/styles/tokens.css");
const TARGET = resolve(HERE, "../src/generated/tokens.ts");
const SOURCE_LABEL = "src/styles/tokens.css";
const REGEN_CMD = "npm run gen:tokens";

/** Tokens taken from the base `:root` block — identical in both themes. */
const STATIC_TOKENS = [
  "r-xs",
  "r-sm",
  "r-lg",
  "r-full",
  "fs-xs",
  "fs-sm",
  "fs-base",
  "dur-fast",
  "dur",
  "ease-out",
  "ease-spring",
  "tap",
];

/**
 * Themed tokens, as [source name, widget suffix]. `text-muted` -> `muted` is the
 * only non-identity rename; everything else just drops `--` and gains `--pcw-`.
 */
const THEMED_TOKENS = [
  ["accent", "accent"],
  ["accent-hover", "accent-hover"],
  ["accent-ink", "accent-ink"],
  ["surface", "surface"],
  ["surface-2", "surface-2"],
  ["surface-3", "surface-3"],
  ["text", "text"],
  ["text-muted", "muted"],
  ["border", "border"],
  ["border-control", "border-control"],
  ["warning", "warning"],
  ["warning-bg", "warning-bg"],
  ["warning-border", "warning-border"],
  ["danger", "danger"],
  ["danger-bg", "danger-bg"],
  ["danger-border", "danger-border"],
  ["ring", "ring"],
];

/**
 * The type scale is the ONE place the widget deliberately diverges from
 * tokens.css's unit strategy: `rem` inside the widget resolves against the HOST
 * PAGE's :root, not the widget's, so a customer page with `html{font-size:62.5%}`
 * would shrink the entire widget to 62.5% of its intended size. px is immune.
 * Only these three are converted — `--pcw-tap` is already 44px and everything
 * else is unitless or a duration.
 */
const REM_TO_PX_TOKENS = new Set(["fs-xs", "fs-sm", "fs-base"]);

/** Error type thrown for every actionable generator failure. */
class TokenGenerationError extends Error {
  /** @param {string} message */
  constructor(message) {
    super(message);
    this.name = "TokenGenerationError";
  }
}

/**
 * Strips `/* ... *\/` comments. Done before parsing because values carry WCAG
 * ratio annotations (`--text-muted: #a3b1af; /* 8.08:1 *\/`) that would otherwise
 * leak into the emitted CSS.
 * @param {string} css
 * @returns {string}
 */
function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

/**
 * Splits the stylesheet into top-level rules using brace-depth tracking rather
 * than a regex. tokens.css nests a `:root` inside `@media (min-width: 48rem)`;
 * a depth-unaware matcher would find that nested block and clobber the real base
 * one. At-rules are skipped entirely, so only depth-0 plain rules are collected.
 * @param {string} css
 * @returns {Map<string, string>} normalized selector -> declaration body
 */
function parseTopLevelRules(css) {
  /** @type {Map<string, string>} */
  const rules = new Map();
  let depth = 0;
  let selectorStart = 0;
  let selector = "";
  let bodyStart = 0;

  for (let i = 0; i < css.length; i += 1) {
    const ch = css[i];
    if (ch === "{") {
      if (depth === 0) {
        selector = css.slice(selectorStart, i);
        bodyStart = i + 1;
      }
      depth += 1;
    } else if (ch === "}") {
      depth -= 1;
      if (depth < 0) {
        throw new TokenGenerationError(
          `Unbalanced "}" at offset ${i} in ${SOURCE_LABEL}. Fix the stylesheet, then run \`${REGEN_CMD}\`.`,
        );
      }
      if (depth === 0) {
        const normalized = normalizeSelector(selector);
        // At-rules (@media, @supports) carry their own nested selectors; the
        // widget only mirrors unconditional declarations.
        if (!normalized.startsWith("@")) {
          rules.set(normalized, css.slice(bodyStart, i));
        }
        selectorStart = i + 1;
      }
    }
  }

  if (depth !== 0) {
    throw new TokenGenerationError(
      `Unclosed block in ${SOURCE_LABEL}. Fix the stylesheet, then run \`${REGEN_CMD}\`.`,
    );
  }
  return rules;
}

/**
 * Collapses all whitespace (including the newline in `:root,\n:root[...]`) so
 * selectors can be matched literally.
 * @param {string} selector
 * @returns {string}
 */
function normalizeSelector(selector) {
  return selector.replace(/\s+/g, " ").trim();
}

/**
 * @param {string} body
 * @returns {Map<string, string>} custom property name (without `--`) -> value
 */
function parseDeclarations(body) {
  /** @type {Map<string, string>} */
  const declarations = new Map();
  for (const raw of body.split(";")) {
    const decl = raw.trim();
    if (!decl.startsWith("--")) continue;
    const colon = decl.indexOf(":");
    if (colon === -1) continue;
    const name = decl.slice(2, colon).trim();
    const value = decl.slice(colon + 1).replace(/\s+/g, " ").trim();
    if (name && value) declarations.set(name, value);
  }
  return declarations;
}

/**
 * @param {Map<string, string>} declarations
 * @param {string} name
 * @param {string} blockLabel
 * @returns {string}
 */
function require_(declarations, name, blockLabel) {
  const value = declarations.get(name);
  if (value === undefined) {
    throw new TokenGenerationError(
      `Token \`--${name}\` is missing from the \`${blockLabel}\` block of ${SOURCE_LABEL}. ` +
        `Either re-add it there, or remove it from the allowlist in widget/scripts/gen-tokens.mjs ` +
        `(and from the widget CSS that consumes it). Then run \`${REGEN_CMD}\`.`,
    );
  }
  return value;
}

/**
 * Converts a bare `rem` value to px (16px root). Whole numbers format as
 * integers; anything else keeps its decimals.
 * @param {string} value
 * @param {string} name
 * @returns {string}
 */
function remToPx(value, name) {
  const match = /^(-?\d*\.?\d+)rem$/.exec(value);
  if (!match) {
    throw new TokenGenerationError(
      `Token \`--${name}\` was expected to be a single rem value for the px conversion, got \`${value}\`. ` +
        `Update the conversion in widget/scripts/gen-tokens.mjs, then run \`${REGEN_CMD}\`.`,
    );
  }
  // Number formatting already yields "12" for whole values and "12.5" otherwise.
  return `${Number(match[1]) * 16}px`;
}

/**
 * @param {Map<string, string>} declarations
 * @param {string} blockLabel
 * @param {string} indent
 * @returns {string[]}
 */
function staticLines(declarations, blockLabel, indent) {
  return STATIC_TOKENS.map((name) => {
    const raw = require_(declarations, name, blockLabel);
    const value = REM_TO_PX_TOKENS.has(name) ? remToPx(raw, name) : raw;
    return `${indent}--pcw-${name}: ${value};`;
  });
}

/**
 * @param {Map<string, string>} declarations
 * @param {string} blockLabel
 * @param {string} indent
 * @returns {string[]}
 */
function themedLines(declarations, blockLabel, indent) {
  return THEMED_TOKENS.map(
    ([source, target]) =>
      `${indent}--pcw-${target}: ${require_(declarations, source, blockLabel)};`,
  );
}

/** @returns {string} the CSS text to embed */
function buildCss() {
  const css = stripComments(readFileSync(SOURCE, "utf8"));
  const rules = parseTopLevelRules(css);

  // THEME INVERSION. tokens.css is a dark-first app stylesheet: it declares DARK
  // on `:root, :root[data-theme="dark"]` and LIGHT on `:root[data-theme="light"]`,
  // because the app always resolves the OS preference to an explicit data-theme
  // attribute. The widget has no such runtime — it is injected into a customer's
  // page — so it inverts the arrangement: LIGHT values are emitted
  // unconditionally on `.pcw-root`, and the DARK values are layered on top inside
  // `@media (prefers-color-scheme: dark)`. Same palette, opposite default.
  const BASE_SELECTOR = ":root";
  const DARK_SELECTOR = ':root, :root[data-theme="dark"]';
  const LIGHT_SELECTOR = ':root[data-theme="light"]';

  /** @type {(selector: string) => Map<string, string>} */
  const block = (selector) => {
    const body = rules.get(selector);
    if (body === undefined) {
      throw new TokenGenerationError(
        `Expected a top-level \`${selector}\` rule in ${SOURCE_LABEL} but found none. ` +
          `If the selector was renamed, update it in widget/scripts/gen-tokens.mjs, then run \`${REGEN_CMD}\`.`,
      );
    }
    return parseDeclarations(body);
  };

  const base = block(BASE_SELECTOR);
  const dark = block(DARK_SELECTOR);
  const light = block(LIGHT_SELECTOR);

  const lines = [
    ".pcw-root {",
    ...staticLines(base, BASE_SELECTOR, "  "),
    "",
    ...themedLines(light, LIGHT_SELECTOR, "  "),
    "}",
    "",
    "@media (prefers-color-scheme: dark) {",
    "  .pcw-root {",
    ...themedLines(dark, DARK_SELECTOR, "    "),
    "  }",
    "}",
  ];

  const out = lines.join("\n");
  assertTemplateSafe(out);
  return out;
}

/**
 * The CSS is interpolated into a template literal downstream, so any backtick,
 * `${` or backslash would either break the generated module or silently execute.
 * @param {string} css
 */
function assertTemplateSafe(css) {
  /** @type {Array<[string, string]>} */
  const forbidden = [
    ["`", "backtick"],
    ["${", "template-literal interpolation `${`"],
    ["\\", "backslash"],
  ];
  for (const [needle, label] of forbidden) {
    const at = css.indexOf(needle);
    if (at !== -1) {
      throw new TokenGenerationError(
        `Generated CSS contains a ${label} at offset ${at}, which cannot be embedded in a template literal. ` +
          `Remove it from ${SOURCE_LABEL} (near: ${JSON.stringify(css.slice(Math.max(0, at - 40), at + 40))}), then run \`${REGEN_CMD}\`.`,
      );
    }
  }
}

/** @returns {string} the full contents of the generated module */
function buildModule() {
  return [
    "/**",
    " * GENERATED — DO NOT EDIT.",
    " *",
    ` * Source:     ${SOURCE_LABEL}`,
    " * Generator:  widget/scripts/gen-tokens.mjs",
    ` * Regenerate: ${REGEN_CMD}`,
    " *",
    " * Hand edits will be overwritten, and the drift test",
    " * (./tokens.drift.test.ts) fails whenever this file and the source disagree.",
    " */",
    "",
    "export const TOKENS_CSS = `",
    buildCss(),
    "`;",
    "",
  ].join("\n");
}

function main() {
  const args = process.argv.slice(2);
  const contents = buildModule();

  if (args.includes("--stdout")) {
    process.stdout.write(contents);
    return;
  }

  if (args.includes("--check")) {
    let committed;
    try {
      committed = readFileSync(TARGET, "utf8");
    } catch {
      console.error(
        `[gen-tokens] ${TARGET} does not exist. Run \`${REGEN_CMD}\` and commit the result.`,
      );
      process.exitCode = 1;
      return;
    }
    if (committed.replace(/\r\n/g, "\n") !== contents) {
      console.error(
        `[gen-tokens] widget/src/generated/tokens.ts is stale — it no longer matches ${SOURCE_LABEL}.\n` +
          `Run \`${REGEN_CMD}\` and commit the result.`,
      );
      process.exitCode = 1;
    }
    return;
  }

  mkdirSync(dirname(TARGET), { recursive: true });
  writeFileSync(TARGET, contents, "utf8");
  console.error(`[gen-tokens] wrote ${TARGET}`);
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? `${error.name}: ${error.message}` : String(error));
  process.exitCode = 1;
}
