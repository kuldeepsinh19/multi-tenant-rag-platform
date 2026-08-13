import type { ChatBannerState } from "@/components/chat/types";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./ChatBanner.module.css";

interface Props {
  banner: ChatBannerState;
  onRetry: () => void;
}

/** Friendly, distinct copy per failure mode — never a raw error object. */
export function ChatBanner({ banner, onRetry }: Props) {
  if (banner.kind === "none") return null;

  const { toneClass, message } =
    banner.kind === "rate-limited"
      ? {
          toneClass: styles.rateLimited,
          message: "You're sending messages a bit too fast. Please wait a moment and try again.",
        }
      : banner.kind === "unavailable"
        ? {
            toneClass: styles.unavailable,
            message: "The assistant is temporarily unavailable. Please try again shortly.",
          }
        : { toneClass: styles.error, message: banner.message };

  return (
    <div role="alert" className={cx(styles.banner, toneClass)}>
      <span className={styles.icon} aria-hidden="true">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
          <circle cx="8" cy="8" r="6.25" stroke="currentColor" strokeWidth="1.5" />
          <path d="M8 5.25v3.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          <circle cx="8" cy="11" r="0.9" fill="currentColor" />
        </svg>
      </span>
      <p className={styles.message}>{message}</p>
      <button type="button" className={cx(ui.btn, ui.btnGhost, ui.btnSm)} onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
