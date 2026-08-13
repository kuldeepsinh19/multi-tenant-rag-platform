/**
 * The theme is resolved in two places that must agree: this store, and the
 * pre-paint inline script in index.html which reads the same localStorage key to
 * set data-theme before first paint. If they diverge the user gets a flash of
 * the wrong theme on every load, so the storage key and the DOM attributes
 * written are asserted literally here as a drift guard.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  applyTheme,
  resolveTheme,
  systemTheme,
  THEME_STORAGE_KEY,
  useThemeStore,
} from "@/store/theme";

/** jsdom ships no matchMedia, so the light branch has to be stubbed in. */
function stubMatchMedia(prefersLight: boolean): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({ matches: prefersLight }),
  );
}

beforeEach(() => {
  useThemeStore.setState({ mode: "system" });
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
});

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("THEME_STORAGE_KEY", () => {
  it("matches the literal key hardcoded in index.html's pre-paint script", () => {
    expect(THEME_STORAGE_KEY).toBe("platform-theme");
  });
});

describe("systemTheme", () => {
  it("falls back to dark when matchMedia is unavailable", () => {
    // jsdom and SSR both hit this branch; dark is the app default.
    expect(systemTheme()).toBe("dark");
  });

  it("returns light when the OS prefers a light scheme", () => {
    stubMatchMedia(true);

    expect(systemTheme()).toBe("light");
  });

  it("returns dark when the OS does not prefer a light scheme", () => {
    stubMatchMedia(false);

    expect(systemTheme()).toBe("dark");
  });
});

describe("resolveTheme", () => {
  it("passes explicit light through untouched", () => {
    expect(resolveTheme("light")).toBe("light");
  });

  it("passes explicit dark through untouched", () => {
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("resolves system against the OS preference", () => {
    stubMatchMedia(true);

    expect(resolveTheme("system")).toBe("light");
  });

  it("never leaks the literal string system to callers", () => {
    // tokens.css keys both palettes off a concrete data-theme value only.
    expect(["light", "dark"]).toContain(resolveTheme("system"));
  });
});

describe("applyTheme", () => {
  it("writes both data-theme and colorScheme onto the document element", () => {
    applyTheme("light");

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
  });

  it("overwrites a previously applied theme", () => {
    applyTheme("light");
    applyTheme("dark");

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });
});

describe("useThemeStore", () => {
  it("starts in system mode", () => {
    expect(useThemeStore.getState().mode).toBe("system");
  });

  it("setMode updates state and applies the resolved theme to the DOM in one step", () => {
    useThemeStore.getState().setMode("light");

    expect(useThemeStore.getState().mode).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("setMode('system') stores system but applies a concrete resolved theme", () => {
    stubMatchMedia(true);

    useThemeStore.getState().setMode("system");

    expect(useThemeStore.getState().mode).toBe("system");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("persists only the mode under the shared storage key", () => {
    useThemeStore.getState().setMode("dark");

    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw as string).state).toEqual({ mode: "dark" });
  });
});
