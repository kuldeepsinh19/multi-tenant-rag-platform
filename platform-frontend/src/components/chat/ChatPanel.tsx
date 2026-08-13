import { useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { streamChat } from "@/api/chat";
import { isDoneEvent } from "@/api/sse";
import { ChatBanner } from "@/components/chat/ChatBanner";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ChatMessageList } from "@/components/chat/ChatMessageList";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import type { ChatBannerState, ChatMessage } from "@/components/chat/types";

import styles from "./ChatPanel.module.css";

interface Props {
  businessId: string;
}

let idCounter = 0;
function nextId(): string {
  idCounter += 1;
  return `msg-${idCounter}`;
}

function ChatPanelInner({ businessId }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [banner, setBanner] = useState<ChatBannerState>({ kind: "none" });
  const [lastMessage, setLastMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const conversationIdRef = useRef<string | undefined>(undefined);

  const runStream = async (message: string) => {
    setBanner({ kind: "none" });
    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: message }]);

    const assistantId = nextId();
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    try {
      await streamChat(
        { business_id: businessId, message, conversation_id: conversationIdRef.current },
        (event) => {
          if (isDoneEvent(event)) {
            // Adopt the server's conversation id so the next turn continues this thread.
            // Guarded: a blocked turn sends null, which must not clear an existing id.
            if (event.conversation_id) {
              conversationIdRef.current = event.conversation_id;
            }
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, citations: event.citations, escalated: event.escalated }
                  : msg,
              ),
            );
            return;
          }
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantId ? { ...msg, content: msg.content + event.token } : msg,
            ),
          );
        },
        controller.signal,
      );
    } catch (error) {
      if (controller.signal.aborted) {
        // User-initiated stop: keep whatever partial content arrived, no banner.
        return;
      }
      if (error instanceof ApiError) {
        if (error.status === 429) {
          setBanner({ kind: "rate-limited" });
        } else if (error.status === 503) {
          setBanner({ kind: "unavailable" });
        } else {
          setBanner({ kind: "error", message: error.message });
        }
      } else {
        setBanner({
          kind: "error",
          message: "Something went wrong while talking to the assistant. Please try again.",
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const handleSend = (message: string) => {
    setLastMessage(message);
    void runStream(message);
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleRetry = () => {
    if (lastMessage) void runStream(lastMessage);
  };

  return (
    <section className={styles.panel} aria-label="Chat">
      <ChatMessageList messages={messages} isStreaming={isStreaming} />
      <ChatBanner banner={banner} onRetry={handleRetry} />
      <ChatComposer
        onSend={handleSend}
        onStop={handleStop}
        disabled={isStreaming}
        isStreaming={isStreaming}
      />
    </section>
  );
}

/** Public entry point — wrapped in its own ErrorBoundary so a render error in
 * the streaming subtree doesn't take down the whole dashboard. */
export function ChatPanel(props: Props) {
  return (
    <ErrorBoundary>
      <ChatPanelInner {...props} />
    </ErrorBoundary>
  );
}
