import { useEffect } from "react";

import { applyTheme, resolveTheme, useThemeStore } from "@/store/theme";

/**
 * Keeps <html data-theme> in sync with the stored preference, and follows live
 * OS changes while the mode is "system" (so switching the OS appearance updates
 * the app immediately without a reload).
 */
export function useThemeSync(): void {
  const mode = useThemeStore((state) => state.mode);

  useEffect(() => {
    applyTheme(resolveTheme(mode));

    if (mode !== "system") return;
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;

    const query = window.matchMedia("(prefers-color-scheme: light)");
    const handleChange = () => applyTheme(resolveTheme("system"));
    query.addEventListener("change", handleChange);
    return () => query.removeEventListener("change", handleChange);
  }, [mode]);
}
