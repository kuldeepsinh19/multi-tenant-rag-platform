import { useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./EmbedSnippet.module.css";

interface Props {
  publicKey: string | undefined;
  apiBase: string;
}

function buildSnippet(publicKey: string, apiBase: string): string {
  return `<script src="${apiBase}/widget.js" data-public-key="${publicKey}" data-api-base="${apiBase}"></script>`;
}

/** Shows the embed snippet for a business's most recently created widget key,
 * with a copy-to-clipboard button. */
export function EmbedSnippet({ publicKey, apiBase }: Props) {
  const [copied, setCopied] = useState(false);

  if (!publicKey) {
    return <EmptyState title="No widget key yet." hint="Create a widget key above to get an embed snippet." />;
  }

  const snippet = buildSnippet(publicKey, apiBase);

  const handleCopy = () => {
    void navigator.clipboard.writeText(snippet).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={styles.wrap}>
      <div className={ui.field}>
        <label className={ui.label} htmlFor="embed-snippet-textarea">
          Embed snippet
        </label>
        <textarea
          id="embed-snippet-textarea"
          className={cx(ui.input, ui.textarea, ui.inputMono, styles.snippet)}
          readOnly
          value={snippet}
          rows={3}
        />
      </div>
      <button
        type="button"
        className={cx(ui.btn, ui.btnGhost, ui.btnSm, styles.copy)}
        onClick={handleCopy}
      >
        {copied ? (
          <>
            <span className={styles.pop} aria-hidden="true">
              <svg viewBox="0 0 16 16" width="13" height="13" fill="none" aria-hidden="true">
                <path
                  d="M13.5 4.5 6.5 11.5 3 8"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            Copied!
          </>
        ) : (
          <>
            <svg viewBox="0 0 16 16" width="13" height="13" fill="none" aria-hidden="true">
              <rect
                x="5.75"
                y="5.75"
                width="7.5"
                height="7.5"
                rx="1.5"
                stroke="currentColor"
                strokeWidth="1.4"
              />
              <path
                d="M10.25 3.75A1.5 1.5 0 0 0 8.75 2.25h-5a1.5 1.5 0 0 0-1.5 1.5v5a1.5 1.5 0 0 0 1.5 1.5"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
            </svg>
            Copy
          </>
        )}
      </button>
    </div>
  );
}
