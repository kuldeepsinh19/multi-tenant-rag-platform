import DOMPurify from "dompurify";

import { isDoneEvent, type Citation } from "./sse";
import { streamWidgetChat, WidgetChatError, type WidgetChatConfig } from "./chat";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  escalated?: boolean;
}

type BannerTone = "error" | "warning" | "neutral";

/**
 * The widget cannot import the dashboard's CSS (separate bundle, and it must not
 * leak styles into or inherit them from a customer's page), so the design tokens
 * are inlined here. The values are identical to src/styles/tokens.css, so both
 * surfaces share one brand and one set of WCAG-verified contrast pairs.
 *
 * Everything is scoped under .pcw-root and defensively reset, because the host
 * page's stylesheet is unknown and may target bare elements. Custom properties
 * are declared on .pcw-root rather than :root for the same reason — writing to
 * :root could collide with the host page's own variables.
 */
const STYLE = `
.pcw-root {
  --pcw-accent: #0f766e;
  --pcw-accent-hover: #115e59;
  --pcw-accent-ink: #ffffff;
  --pcw-surface: #ffffff;
  --pcw-surface-2: #f4f6f6;
  --pcw-surface-3: #e9eeed;
  --pcw-text: #0d1413;
  --pcw-muted: #55635f;
  --pcw-border: rgba(13, 20, 19, 0.10);
  --pcw-border-control: #767f7d;
  --pcw-warning: #b45309;
  --pcw-warning-bg: #fffbeb;
  --pcw-warning-border: #fde68a;
  --pcw-danger: #be123c;
  --pcw-danger-bg: #fff1f2;
  --pcw-danger-border: #fecdd3;
  --pcw-shadow: 0 18px 44px -16px rgba(13, 20, 19, 0.35);
  --pcw-ring: rgba(15, 118, 110, 0.32);
}

/* The widget follows the visitor's OS preference — there is no in-widget toggle,
   since it lives on someone else's page. */
@media (prefers-color-scheme: dark) {
  .pcw-root {
    --pcw-accent: #2dd4bf;
    --pcw-accent-hover: #5eead4;
    --pcw-accent-ink: #04201d;
    --pcw-surface: #12181a;
    --pcw-surface-2: #181f21;
    --pcw-surface-3: #202a2c;
    --pcw-text: #e6eceb;
    --pcw-muted: #a3b1af;
    --pcw-border: rgba(255, 255, 255, 0.10);
    --pcw-border-control: #667573;
    --pcw-warning: #fbbf24;
    --pcw-warning-bg: rgba(251, 191, 36, 0.14);
    --pcw-warning-border: rgba(251, 191, 36, 0.34);
    --pcw-danger: #fb7185;
    --pcw-danger-bg: rgba(251, 113, 133, 0.14);
    --pcw-danger-border: rgba(251, 113, 133, 0.34);
    --pcw-shadow: 0 18px 44px -16px rgba(0, 0, 0, 0.7);
    --pcw-ring: rgba(45, 212, 191, 0.45);
  }
}

.pcw-root *,
.pcw-root *::before,
.pcw-root *::after { box-sizing: border-box; }

.pcw-bubble {
  position: fixed; bottom: 16px; right: 16px;
  display: flex; align-items: center; justify-content: center;
  width: 56px; height: 56px; padding: 0;
  border-radius: 50%; border: none; cursor: pointer;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
  box-shadow: var(--pcw-shadow);
  z-index: 2147483000;
  transition: transform 180ms cubic-bezier(0.2, 0.8, 0.2, 1), background-color 180ms ease;
  animation: pcw-bubble-in 320ms cubic-bezier(0.22, 1.2, 0.36, 1) both;
}
.pcw-bubble:hover { background: var(--pcw-accent-hover); transform: scale(1.06); }
.pcw-bubble:active { transform: scale(0.96); }
.pcw-bubble:focus-visible { outline: 2px solid var(--pcw-accent); outline-offset: 3px; }

.pcw-panel {
  position: fixed; bottom: 84px; right: 16px;
  /* Was a fixed 320px + 20px offset, which overflowed a 320px viewport. */
  width: min(360px, calc(100vw - 32px));
  max-height: min(70vh, 560px);
  display: flex; flex-direction: column;
  color: var(--pcw-text); background: var(--pcw-surface);
  border: 1px solid var(--pcw-border);
  border-radius: 14px;
  box-shadow: var(--pcw-shadow);
  overflow: hidden;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  font-size: 14px; line-height: 1.5;
  z-index: 2147483000;
  transform-origin: bottom right;
  animation: pcw-panel-in 200ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
/* Any author-origin display value beats the UA sheet's [hidden] rule, so every
   element this widget toggles via the hidden property needs the guard restated.
   Declared once for the whole subtree rather than per element: .pcw-panel and
   .pcw-generating both set display, and the next one added would silently
   ignore hidden too. */
.pcw-root [hidden] { display: none !important; }

.pcw-header {
  display: flex; justify-content: space-between; align-items: center; gap: 8px;
  padding: 10px 12px;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
}
.pcw-header-title { font-weight: 600; letter-spacing: -0.01em; }
.pcw-header button {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; padding: 0;
  background: none; border: none; border-radius: 6px;
  color: inherit; cursor: pointer;
  transition: background-color 180ms ease;
}
.pcw-header button:hover { background: rgba(255, 255, 255, 0.18); }
.pcw-header button:focus-visible { outline: 2px solid var(--pcw-accent-ink); outline-offset: 1px; }

.pcw-messages {
  flex: 1; min-height: 0;
  display: flex; flex-direction: column; gap: 10px;
  overflow-y: auto; overscroll-behavior: contain;
  padding: 12px;
}
.pcw-empty { color: var(--pcw-muted); text-align: center; padding: 20px 8px; margin: 0; }

.pcw-message {
  max-width: 85%;
  padding: 8px 11px;
  border-radius: 14px;
  overflow-wrap: anywhere;
  animation: pcw-message-in 180ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
.pcw-message__role {
  display: block; margin-bottom: 2px;
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  opacity: 0.75;
}
.pcw-message--user {
  align-self: flex-end;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
  border-bottom-right-radius: 5px;
}
.pcw-message--assistant {
  align-self: flex-start;
  background: var(--pcw-surface-2);
  border: 1px solid var(--pcw-border);
  border-bottom-left-radius: 5px;
}

.pcw-citations {
  list-style: none; display: flex; flex-wrap: wrap; gap: 4px;
  margin: 8px 0 0; padding: 0;
}
.pcw-citations-label {
  margin: 8px 0 4px;
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--pcw-muted);
}
.pcw-citations li {
  padding: 2px 8px; font-size: 11px;
  color: var(--pcw-muted); background: var(--pcw-surface-3);
  border: 1px solid var(--pcw-border); border-radius: 999px;
}
.pcw-message--user .pcw-citations-label { color: inherit; opacity: 0.85; }
.pcw-message--user .pcw-citations li {
  color: inherit;
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(255, 255, 255, 0.28);
}

.pcw-escalated {
  display: flex; align-items: center; gap: 6px;
  margin: 8px 0 0; padding: 6px 8px;
  font-size: 12px;
  color: var(--pcw-warning); background: var(--pcw-warning-bg);
  border: 1px solid var(--pcw-warning-border); border-radius: 6px;
}

/* Tone variants: a 429 rate-limit is not an error and no longer renders red. */
.pcw-banner {
  margin: 0 12px 8px; padding: 8px 10px;
  font-size: 13px; border: 1px solid; border-radius: 8px;
  animation: pcw-banner-in 180ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}
.pcw-banner--error {
  color: var(--pcw-danger); background: var(--pcw-danger-bg); border-color: var(--pcw-danger-border);
}
.pcw-banner--warning {
  color: var(--pcw-warning); background: var(--pcw-warning-bg); border-color: var(--pcw-warning-border);
}
.pcw-banner--neutral {
  color: var(--pcw-muted); background: var(--pcw-surface-2); border-color: var(--pcw-border);
}

.pcw-generating { display: flex; align-items: center; gap: 4px; padding: 0 12px 10px; }
.pcw-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--pcw-accent);
  animation: pcw-dot 1.2s ease-in-out infinite;
}
.pcw-dot:nth-child(2) { animation-delay: 160ms; }
.pcw-dot:nth-child(3) { animation-delay: 320ms; }

.pcw-composer {
  display: flex; gap: 6px; align-items: flex-end;
  padding: 8px; border-top: 1px solid var(--pcw-border);
  background: var(--pcw-surface);
}
.pcw-composer textarea {
  flex: 1; min-width: 0; resize: none;
  padding: 7px 9px;
  font: inherit; color: var(--pcw-text);
  background: var(--pcw-surface-2);
  /* Was #ccc at 1.61:1 — below the 3:1 WCAG 1.4.11 minimum for a control
     boundary. This value measures 4.12:1 on white. */
  border: 1px solid var(--pcw-border-control);
  border-radius: 8px;
  transition: border-color 180ms ease, box-shadow 180ms ease;
}
.pcw-composer textarea::placeholder { color: var(--pcw-muted); }
.pcw-composer textarea:focus-visible {
  outline: none;
  border-color: var(--pcw-accent);
  box-shadow: 0 0 0 3px var(--pcw-ring);
}
.pcw-composer button {
  flex: none;
  min-height: 34px; padding: 0 12px;
  font: inherit; font-weight: 600;
  border: 1px solid transparent; border-radius: 8px;
  cursor: pointer;
  color: var(--pcw-accent-ink); background: var(--pcw-accent);
  transition: background-color 180ms ease, transform 120ms ease;
}
.pcw-composer button:hover:not(:disabled) { background: var(--pcw-accent-hover); }
.pcw-composer button:active:not(:disabled) { transform: scale(0.97); }
.pcw-composer button:disabled { opacity: 0.5; cursor: not-allowed; }
.pcw-composer button:focus-visible { outline: 2px solid var(--pcw-accent); outline-offset: 2px; }
.pcw-stop {
  color: var(--pcw-danger) !important;
  background: transparent !important;
  border-color: var(--pcw-danger-border) !important;
}

/* Clip-based visually-hidden. Replaces a left:-9999px label, which forces
   assistive tech to handle an off-canvas box and breaks under RTL. */
.pcw-sr-only {
  position: absolute !important;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0); clip-path: inset(50%);
  white-space: nowrap; border: 0;
}

@keyframes pcw-bubble-in {
  from { opacity: 0; transform: scale(0.6); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes pcw-panel-in {
  from { opacity: 0; transform: scale(0.94) translate3d(0, 8px, 0); }
  to { opacity: 1; transform: scale(1) translate3d(0, 0, 0); }
}
@keyframes pcw-message-in {
  from { opacity: 0; transform: translate3d(0, 6px, 0); }
  to { opacity: 1; transform: translate3d(0, 0, 0); }
}
@keyframes pcw-banner-in {
  from { opacity: 0; transform: translate3d(0, -6px, 0); }
  to { opacity: 1; transform: translate3d(0, 0, 0); }
}
@keyframes pcw-dot {
  0%, 80%, 100% { transform: translate3d(0, 0, 0); opacity: 0.45; }
  40% { transform: translate3d(0, -4px, 0); opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .pcw-root *,
  .pcw-root *::before,
  .pcw-root *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  .pcw-dot { opacity: 1; }
}
`;

/* Author-controlled markup constants — no dynamic or user data is interpolated,
   so these are the one place innerHTML is used without sanitization. Anything
   originating from the model or the visitor still goes through DOMPurify or
   textContent below. */
const CHAT_ICON_SVG = `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" aria-hidden="true">
  <path d="M4.5 6.5A2 2 0 0 1 6.5 4.5h11a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H10l-4 3.5v-3.5H6.5a2 2 0 0 1-2-2v-7Z"
    stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
</svg>`;

const CLOSE_ICON_SVG = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
  <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
</svg>`;

const WARNING_ICON_SVG = `<svg viewBox="0 0 16 16" width="13" height="13" fill="none" aria-hidden="true">
  <path d="M8 2.75 14.5 13.5h-13L8 2.75Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
  <path d="M8 6.75v2.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="8" cy="11.2" r="0.8" fill="currentColor"/>
</svg>`;

/** Minimal floating chat bubble widget: vanilla DOM, no framework, so it
 * stays tiny and can't clash with a host page's React version. Mirrors the
 * dashboard ChatPanel's UI states (empty/streaming/error/rate-limited/
 * unavailable/escalated) with the same DOMPurify sanitization discipline. */
export function mountWidget(config: WidgetChatConfig): void {
  const style = document.createElement("style");
  style.textContent = STYLE;
  document.head.appendChild(style);

  /* Single scoping container so the design tokens live on .pcw-root instead of
     :root, where they could collide with the host page's variables. The bubble
     and panel remain position: fixed, so the wrapper doesn't affect layout. */
  const root = document.createElement("div");
  root.className = "pcw-root";

  const bubble = document.createElement("button");
  bubble.className = "pcw-bubble";
  bubble.type = "button";
  bubble.setAttribute("aria-label", "Open chat");
  bubble.setAttribute("aria-expanded", "false");
  bubble.innerHTML = CHAT_ICON_SVG;

  const panel = document.createElement("section");
  panel.className = "pcw-panel";
  panel.hidden = true;
  /* Intentionally NOT aria-modal: this is a non-modal floating widget, and the
     visitor can still use the host page while it's open. Claiming modality
     would hide the rest of the page from assistive tech, and trapping focus
     would stop keyboard users reaching the page behind it. Escape-to-close and
     focus restoration give the keyboard affordances without that cost. */
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", "Chat with us");

  const header = document.createElement("div");
  header.className = "pcw-header";
  const title = document.createElement("span");
  title.className = "pcw-header-title";
  title.textContent = "Chat";
  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.setAttribute("aria-label", "Close chat");
  closeButton.innerHTML = CLOSE_ICON_SVG;
  header.append(title, closeButton);

  const messagesEl = document.createElement("div");
  messagesEl.className = "pcw-messages";
  messagesEl.setAttribute("aria-live", "polite");
  messagesEl.setAttribute("aria-relevant", "additions text");

  const bannerEl = document.createElement("div");
  bannerEl.className = "pcw-banner";
  bannerEl.setAttribute("role", "alert");
  bannerEl.hidden = true;

  /* Three bouncing dots instead of the words "Generating…". Kept aria-hidden:
     the messages region above is already an aria-live region, so the streamed
     tokens are announced without a second, redundant announcement. */
  const generatingEl = document.createElement("div");
  generatingEl.className = "pcw-generating";
  generatingEl.hidden = true;
  generatingEl.setAttribute("aria-hidden", "true");
  for (let index = 0; index < 3; index += 1) {
    const dot = document.createElement("span");
    dot.className = "pcw-dot";
    generatingEl.appendChild(dot);
  }

  const composer = document.createElement("div");
  composer.className = "pcw-composer";
  const label = document.createElement("label");
  label.htmlFor = "pcw-input";
  label.className = "pcw-sr-only";
  label.textContent = "Message";
  const textarea = document.createElement("textarea");
  textarea.id = "pcw-input";
  textarea.rows = 1;
  textarea.placeholder = "Ask a question…";
  const sendButton = document.createElement("button");
  sendButton.type = "button";
  sendButton.textContent = "Send";
  const stopButton = document.createElement("button");
  stopButton.type = "button";
  stopButton.className = "pcw-stop";
  stopButton.textContent = "Stop";
  stopButton.hidden = true;
  composer.append(label, textarea, sendButton, stopButton);

  panel.append(header, messagesEl, bannerEl, generatingEl, composer);
  root.append(bubble, panel);
  document.body.append(root);

  let messages: Message[] = [];
  let abortController: AbortController | null = null;
  let conversationId: string | undefined;

  function renderMessages(): void {
    messagesEl.textContent = "";
    if (messages.length === 0) {
      const empty = document.createElement("p");
      empty.className = "pcw-empty";
      empty.textContent = "No messages yet. Ask a question to get started.";
      messagesEl.appendChild(empty);
      return;
    }
    for (const message of messages) {
      const item = document.createElement("div");
      item.className = `pcw-message pcw-message--${message.role}`;

      const roleLabel = document.createElement("span");
      roleLabel.className = "pcw-message__role";
      roleLabel.textContent = message.role === "user" ? "You" : "Assistant";
      item.appendChild(roleLabel);

      if (message.role === "assistant") {
        const body = document.createElement("span");
        body.innerHTML = DOMPurify.sanitize(message.content);
        item.appendChild(body);
      } else {
        const body = document.createElement("span");
        body.textContent = message.content;
        item.appendChild(body);
      }

      if (message.escalated) {
        const escalated = document.createElement("p");
        escalated.className = "pcw-escalated";
        escalated.setAttribute("role", "status");
        escalated.innerHTML = WARNING_ICON_SVG;
        escalated.append("This conversation has been escalated to a human agent.");
        item.appendChild(escalated);
      }

      if (message.citations && message.citations.length > 0) {
        const citationsLabel = document.createElement("p");
        citationsLabel.className = "pcw-citations-label";
        citationsLabel.textContent = "Sources";
        item.appendChild(citationsLabel);

        const list = document.createElement("ul");
        list.className = "pcw-citations";
        for (const citation of message.citations) {
          const li = document.createElement("li");
          li.textContent = citation.title;
          list.appendChild(li);
        }
        item.appendChild(list);
      }

      messagesEl.appendChild(item);
    }
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showBanner(text: string | null, tone: BannerTone = "error"): void {
    if (!text) {
      bannerEl.hidden = true;
      bannerEl.textContent = "";
      return;
    }
    bannerEl.className = `pcw-banner pcw-banner--${tone}`;
    bannerEl.hidden = false;
    bannerEl.textContent = text;
  }

  function setStreaming(streaming: boolean): void {
    generatingEl.hidden = !streaming;
    stopButton.hidden = !streaming;
    sendButton.disabled = streaming;
    textarea.disabled = streaming;
  }

  async function send(message: string): Promise<void> {
    showBanner(null);
    messages = [...messages, { role: "user", content: message }];
    const assistantIndex = messages.length;
    messages = [...messages, { role: "assistant", content: "" }];
    renderMessages();

    const controller = new AbortController();
    abortController = controller;
    setStreaming(true);

    try {
      await streamWidgetChat(config, message, conversationId, (event) => {
        if (isDoneEvent(event)) {
          // Adopt the server's conversation id so the next turn continues this thread.
          // Guarded: a blocked turn sends null, which must not clear an existing id.
          if (event.conversation_id) {
            conversationId = event.conversation_id;
          }
          const current = messages[assistantIndex];
          if (current) {
            messages = messages.map((msg, index) =>
              index === assistantIndex
                ? { ...msg, citations: event.citations, escalated: event.escalated }
                : msg,
            );
          }
          renderMessages();
          return;
        }
        const current = messages[assistantIndex];
        if (!current) return;
        messages = messages.map((msg, index) =>
          index === assistantIndex ? { ...msg, content: msg.content + event.token } : msg,
        );
        renderMessages();
      }, controller.signal);
    } catch (error) {
      if (controller.signal.aborted) {
        // User pressed Stop — keep partial content, no error banner.
      } else if (error instanceof WidgetChatError && error.status === 429) {
        showBanner(
          "You're sending messages a bit too fast. Please wait a moment and try again.",
          "warning",
        );
      } else if (error instanceof WidgetChatError && error.status === 503) {
        showBanner("The assistant is temporarily unavailable. Please try again shortly.", "neutral");
      } else if (error instanceof WidgetChatError) {
        showBanner(error.message, "error");
      } else {
        showBanner(
          "Something went wrong while talking to the assistant. Please try again.",
          "error",
        );
      }
    } finally {
      setStreaming(false);
      abortController = null;
    }
  }

  function handleSend(): void {
    const text = textarea.value.trim();
    if (!text) return;
    textarea.value = "";
    void send(text);
    textarea.focus();
  }

  sendButton.addEventListener("click", handleSend);
  stopButton.addEventListener("click", () => abortController?.abort());
  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  });

  function openPanel(): void {
    panel.hidden = false;
    bubble.setAttribute("aria-expanded", "true");
    bubble.setAttribute("aria-label", "Close chat");
    textarea.focus();
  }
  function closePanel(): void {
    panel.hidden = true;
    bubble.setAttribute("aria-expanded", "false");
    bubble.setAttribute("aria-label", "Open chat");
    bubble.focus();
  }

  bubble.addEventListener("click", () => {
    if (panel.hidden) openPanel();
    else closePanel();
  });
  closeButton.addEventListener("click", closePanel);

  /* Escape closes the panel from anywhere inside it and returns focus to the
     bubble — the expected keyboard affordance for a dialog, and previously
     absent entirely. Scoped to the panel so it can't swallow the host page's
     own Escape handling. */
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      closePanel();
    }
  });

  renderMessages();
}
