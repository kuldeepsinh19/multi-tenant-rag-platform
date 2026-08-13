import type { ReactElement } from "react";

import { cx } from "@/lib/cx";
import { useThemeStore, type ThemeMode } from "@/store/theme";

import styles from "./ThemeToggle.module.css";

const SunIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="4.25" stroke="currentColor" strokeWidth="1.6" />
    <path
      d="M12 2.75v2M12 19.25v2M2.75 12h2M19.25 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M18.5 5.5l-1.4 1.4M6.9 17.1 5.5 18.5"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    />
  </svg>
);

const MoonIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
    <path
      d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinejoin="round"
    />
  </svg>
);

const SystemIcon = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
    <rect x="3" y="4.5" width="18" height="12" rx="2" stroke="currentColor" strokeWidth="1.6" />
    <path d="M9 20h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

const OPTIONS: Array<{ mode: ThemeMode; label: string; Icon: () => ReactElement }> = [
  { mode: "light", label: "Light", Icon: SunIcon },
  { mode: "dark", label: "Dark", Icon: MoonIcon },
  { mode: "system", label: "System", Icon: SystemIcon },
];

/** Three-state segmented control. Real <button>s with aria-pressed, so the
 *  selected state is exposed to assistive tech rather than implied by colour. */
export function ThemeToggle() {
  const mode = useThemeStore((state) => state.mode);
  const setMode = useThemeStore((state) => state.setMode);

  return (
    <div className={styles.group} role="group" aria-label="Colour theme">
      {OPTIONS.map(({ mode: optionMode, label, Icon }) => (
        <button
          key={optionMode}
          type="button"
          className={cx(styles.option, mode === optionMode && styles.optionActive)}
          aria-pressed={mode === optionMode}
          onClick={() => setMode(optionMode)}
        >
          <Icon />
          <span className="sr-only">{label} theme</span>
        </button>
      ))}
    </div>
  );
}
