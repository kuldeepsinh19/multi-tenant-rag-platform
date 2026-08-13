import { useEffect, useRef } from "react";

import DOMPurify from "dompurify";

import type { ChatMessage } from "@/components/chat/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { cx } from "@/lib/cx";

import styles from "./ChatMessageList.module.css";

interface Props {
  messages: ChatMessage[];
  isStreaming: boolean;
}

/** How close to the bottom counts as "following the conversation". */
const FOLLOW_THRESHOLD_PX = 80;

/**
 * Renders the conversation. Assistant content is untrusted model output —
 * sanitized with DOMPurify before dangerouslySetInnerHTML, per
 * react-frontend-standards. The wrapping region is aria-live="polite" so
 * screen readers announce new/updated messages without stealing focus.
 */
export function ChatMessageList({ messages, isStreaming }: Props) {
  const listRef = useRef<HTMLUListElement>(null);

  /* Keep the newest content in view as tokens stream in — the widget already
     did this, the dashboard didn't. Deliberately does NOT scroll when the user
     has scrolled up to read history, so it can't hijack their position. */
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;

    const distanceFromBottom = list.scrollHeight - list.scrollTop - list.clientHeight;
    if (distanceFromBottom > FOLLOW_THRESHOLD_PX) return;

    const prefersReducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Jump instantly while tokens are arriving; glide for a settled message.
    const behavior: ScrollBehavior = prefersReducedMotion || isStreaming ? "auto" : "smooth";

    // Element.scrollTo is absent in jsdom, so fall back to the property.
    if (typeof list.scrollTo === "function") {
      list.scrollTo({ top: list.scrollHeight, behavior });
    } else {
      list.scrollTop = list.scrollHeight;
    }
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return (
      <EmptyState
        title="No messages yet."
        hint="Ask a question to get started."
        icon={
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
            <path
              d="M4.5 6.5A2 2 0 0 1 6.5 4.5h11a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H10l-4 3.5v-3.5H6.5a2 2 0 0 1-2-2v-7Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        }
      />
    );
  }

  return (
    <ul
      ref={listRef}
      className={styles.list}
      aria-live="polite"
      aria-relevant="additions text"
    >
      {messages.map((message) => (
        <li
          key={message.id}
          className={cx(
            styles.message,
            message.role === "user" ? styles.user : styles.assistant,
          )}
        >
          <span className={styles.role}>{message.role === "user" ? "You" : "Assistant"}</span>
          {message.role === "assistant" ? (
            // Sanitized immediately above with DOMPurify — safe to render as HTML.
            <span dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(message.content) }} />
          ) : (
            <span>{message.content}</span>
          )}
          {message.escalated ? (
            <p className={styles.escalated} role="status">
              <svg viewBox="0 0 16 16" width="13" height="13" fill="none" aria-hidden="true">
                <path
                  d="M8 2.75 14.5 13.5h-13L8 2.75Z"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinejoin="round"
                />
                <path d="M8 6.75v2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                <circle cx="8" cy="11.2" r="0.8" fill="currentColor" />
              </svg>
              This conversation has been escalated to a human agent.
            </p>
          ) : null}
          {message.citations && message.citations.length > 0 ? (
            /* The "Sources" label used to be CSS ::before content, which screen
               readers announce inconsistently. It is real text now — grounded
               answers are the point of this product, so the attribution should
               reach every user. */
            <div className={styles.citations}>
              <p className={styles.citationsLabel}>Sources</p>
              <ul className={styles.citationList}>
                {message.citations.map((citation) => (
                  <li key={citation.doc_id} className={styles.citation}>
                    {citation.title}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </li>
      ))}
      {isStreaming ? (
        <li className={styles.generating} aria-hidden="true">
          <span className={styles.dot} />
          <span className={styles.dot} />
          <span className={styles.dot} />
        </li>
      ) : null}
    </ul>
  );
}
