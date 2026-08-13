import { Component, type ErrorInfo, type ReactNode } from "react";

import { cx } from "@/lib/cx";
import ui from "@/styles/primitives.module.css";

import styles from "./ErrorBoundary.module.css";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/** Wraps the app (and risky subtrees like the chat stream) so a render error shows a
 * recoverable fallback instead of a white screen. See react-frontend-standards. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled UI error", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className={styles.fallback} role="alert">
          <span className={styles.icon} aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
              <path
                d="M12 3.5 21 19H3l9-15.5Z"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <path d="M12 9.5v4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <circle cx="12" cy="16.4" r="1" fill="currentColor" />
            </svg>
          </span>
          <h2 className={styles.title}>Something went wrong</h2>
          <p className={styles.body}>
            This part of the page failed to render. Reloading usually clears it.
          </p>
          {/* The standards call for a *recoverable* fallback — previously this
              told the user to refresh but gave them nothing to click. */}
          <button
            type="button"
            className={cx(ui.btn, ui.btnPrimary)}
            onClick={() => window.location.reload()}
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
