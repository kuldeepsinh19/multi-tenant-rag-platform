import { useRef, useState, type KeyboardEvent } from "react";

import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./ChatComposer.module.css";

interface Props {
  onSend: (message: string) => void;
  onStop: () => void;
  disabled: boolean;
  isStreaming: boolean;
}

/** Labeled textarea + Send/Stop controls. Enter sends, Shift+Enter inserts a
 * newline. Focus returns to the input after sending, per a11y requirements. */
export function ChatComposer({ onSend, onStop, disabled, isStreaming }: Props) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const send = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    inputRef.current?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  };

  return (
    <div className={styles.composer}>
      <div className={ui.field}>
        <label className={ui.label} htmlFor="chat-message-input">
          Message
        </label>
        <textarea
          id="chat-message-input"
          className={cx(ui.input, ui.textarea, styles.input)}
          ref={inputRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={2}
          placeholder="Ask a question…"
          aria-describedby="chat-composer-hint"
        />
      </div>
      <div className={styles.actions}>
        <p id="chat-composer-hint" className={styles.hint}>
          <kbd className={styles.kbd}>Enter</kbd> to send,{" "}
          <kbd className={styles.kbd}>Shift</kbd> + <kbd className={styles.kbd}>Enter</kbd> for a
          new line
        </p>
        <div className={styles.buttons}>
          {/* Explicit variant classes. These two buttons were previously
              distinguished by `button + button`, an adjacent-sibling hack that
              silently meant "the Stop button". */}
          <button
            type="button"
            className={cx(ui.btn, ui.btnPrimary)}
            onClick={send}
            disabled={disabled || !value.trim()}
          >
            Send
          </button>
          {isStreaming ? (
            <button type="button" className={cx(ui.btn, ui.btnDanger)} onClick={onStop}>
              Stop
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
