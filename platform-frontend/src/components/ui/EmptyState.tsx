import type { ReactNode } from "react";

import { cx } from "@/lib/cx";

import styles from "./EmptyState.module.css";

interface Props {
  /** Short, plain-language statement of what is absent. */
  title: string;
  /** Optional follow-up telling the user how to fill the space. */
  hint?: string;
  icon?: ReactNode;
  className?: string;
}

/** Replaces the bare, unstyled `<p>No … yet.</p>` empty states with a
 *  consistent, centred panel. Copy is passed in by the caller so wording stays
 *  owned by the feature. */
export function EmptyState({ title, hint, icon, className }: Props) {
  return (
    <div className={cx(styles.empty, className)}>
      <span className={styles.icon} aria-hidden="true">
        {icon ?? (
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
            <path
              d="M4 7.5A2.5 2.5 0 0 1 6.5 5h4l2 2.5h5A2.5 2.5 0 0 1 20 10v6.5A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5v-9Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>
      <p className={styles.title}>{title}</p>
      {hint ? <p className={styles.hint}>{hint}</p> : null}
    </div>
  );
}
