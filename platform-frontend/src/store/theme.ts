import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

/** Kept in sync with the pre-paint inline script in index.html, which reads the
 *  same key to set data-theme before first paint (avoiding a flash of the wrong
 *  theme). Change one, change the other. */
export const THEME_STORAGE_KEY = "platform-theme";

/** Dark is the app's default, so an environment without matchMedia (jsdom in
 *  tests, SSR) resolves to dark rather than throwing. */
export function systemTheme(): ResolvedTheme {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function resolveTheme(mode: ThemeMode): ResolvedTheme {
  return mode === "system" ? systemTheme() : mode;
}

/** Writes the resolved theme onto <html>. tokens.css keys both palettes off
 *  data-theme only — "system" is always resolved to a concrete value here, so
 *  the OS preference and the in-app toggle share one code path. */
export function applyTheme(theme: ResolvedTheme): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

interface ThemeState {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
}

/**
 * Only the theme preference is persisted — no user data. Mirrors the
 * persist + onRehydrateStorage pattern already used by src/store/auth.ts so the
 * DOM is re-synced when the value is restored from localStorage on startup.
 */
export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      mode: "system",
      setMode: (mode) => {
        applyTheme(resolveTheme(mode));
        set({ mode });
      },
    }),
    {
      name: THEME_STORAGE_KEY,
      partialize: (state) => ({ mode: state.mode }),
      onRehydrateStorage: () => (state) => {
        applyTheme(resolveTheme(state?.mode ?? "system"));
      },
    },
  ),
);
