import DOMPurify from "dompurify";

import { isDoneEvent, type Citation } from "./sse";
import { streamWidgetChat, WidgetChatError, type WidgetChatConfig } from "./chat";
import { STYLE } from "./styles";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  escalated?: boolean;
}

type BannerTone = "error" | "warning" | "neutral";

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
