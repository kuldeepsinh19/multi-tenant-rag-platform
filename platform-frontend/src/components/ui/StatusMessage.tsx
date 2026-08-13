import type { ReactNode } from "react";

import { cx } from "@/lib/cx";

import styles from "./StatusMessage.module.css";

type Tone = "error" | "success" | "info" | "warning";

interface Props {
  tone: Tone;
  children: ReactNode;
  /**
   * ARIA role stays the caller's decision: "alert" interrupts and is right for
   * failures, "status" is polite and right for confirmations. Defaults from the
   * tone, which covers every current call site.
   */
  role?: "alert" | "status";
  className?: string;
}

/* CSS Module members are typed through an index signature, so under
   `noUncheckedIndexedAccess` they widen to `string | undefined`. cx() already
   drops falsy entries, so the union is carried rather than asserted away. */
const toneClass: Record<Tone, string | undefined> = {
  error: styles.error,
  success: styles.success,
  info: styles.info,
  warning: styles.warning,
};

/**
 * A styled inline status line.
 *
 * This component exists to fix a real bug: the old stylesheet styled
 * `[role="alert"]` and `[role="status"]` globally as full-width tinted blocks.
 * ARIA roles are semantics, not presentation, so any element that legitimately
 * needed a role inherited a banner it never asked for — most visibly
 * DocumentList's inline error, which became a red block wedged into a flex row.
 * Presentation now comes from a class; the role stays purely semantic.
 */
export function StatusMessage({ tone, children, role, className }: Props) {
  const resolvedRole = role ?? (tone === "error" ? "alert" : "status");

  return (
    <p className={cx(styles.message, toneClass[tone], className)} role={resolvedRole}>
      <span className={styles.icon} aria-hidden="true">
        {tone === "success" ? (
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
            <path
              d="M13.5 4.5 6.5 11.5 3 8"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.5" />
            <path
              d="M8 5.25v3.5"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <circle cx="8" cy="11" r="0.9" fill="currentColor" />
          </svg>
        )}
      </span>
      <span className={styles.body}>{children}</span>
    </p>
  );
}
